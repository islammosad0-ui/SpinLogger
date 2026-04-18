#import "SLSpinHook.h"
#import "SLInlineHook.h"
#include <dlfcn.h>
#include <string.h>
#include <stdint.h>
#include <stdio.h>
#include <stdbool.h>
#include <sys/time.h>
#include <pthread.h>

// ---------------------------------------------------------------------------
//  IL2CPP method-iteration + field-reading APIs.
// ---------------------------------------------------------------------------
typedef void*       (*fn_class_get_methods)(void *klass, void **iter);
typedef const char* (*fn_method_get_name)(void *method);
typedef uint32_t    (*fn_method_get_param_count)(void *method);
typedef void*       (*fn_class_get_field_from_name)(void *klass, const char *name);
typedef size_t      (*fn_field_get_offset)(void *field);

static fn_class_get_methods          _class_get_methods;
static fn_method_get_name            _method_get_name;
static fn_method_get_param_count     _method_get_param_count;
static fn_class_get_field_from_name  _class_get_field_from_name;
static fn_field_get_offset           _field_get_offset;

static BOOL s_installed = NO;

// ---------------------------------------------------------------------------
//  Lightweight C-stdio event log.
//  NSLog + NSString + NSFileHandle on a hot Obj-C callback path was likely
//  starving the Unity main thread enough to trip the launch watchdog; even if
//  not, buffered NSFileHandle writes got lost on SIGKILL. This path uses a
//  single FILE*, line-buffered, fflushed every write.
// ---------------------------------------------------------------------------
static FILE *s_evtFp = NULL;
static pthread_mutex_t s_evtMu = PTHREAD_MUTEX_INITIALIZER;

static void openEventLog(void) {
    if (s_evtFp) return;
    NSString *docs = NSSearchPathForDirectoriesInDomains(
        NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
    NSString *path = [docs stringByAppendingPathComponent:@"hook_events.csv"];
    bool isNew = ![[NSFileManager defaultManager] fileExistsAtPath:path];
    s_evtFp = fopen(path.fileSystemRepresentation, "a");
    if (!s_evtFp) return;
    setvbuf(s_evtFp, NULL, _IOLBF, 0);
    if (isNew) {
        fputs("ts,hook,arg1,arg2,ret,notes\n", s_evtFp);
    }
    struct timeval tv; gettimeofday(&tv, NULL);
    fprintf(s_evtFp, "# session %ld.%06d\n",
            (long)tv.tv_sec, (int)tv.tv_usec);
    fflush(s_evtFp);
}

// Minimal CSV writer. No NSString, no NSLog. Takes preformatted strings.
static void logLine(const char *hook,
                    const char *a1,
                    const char *a2,
                    const char *ret,
                    const char *notes) {
    if (!s_evtFp) return;
    struct timeval tv; gettimeofday(&tv, NULL);
    pthread_mutex_lock(&s_evtMu);
    fprintf(s_evtFp, "%ld.%06d,%s,%s,%s,%s,%s\n",
            (long)tv.tv_sec, (int)tv.tv_usec,
            hook, a1 ? a1 : "", a2 ? a2 : "",
            ret ? ret : "", notes ? notes : "");
    fflush(s_evtFp);
    pthread_mutex_unlock(&s_evtMu);
}

// ---------------------------------------------------------------------------
//  Method resolution helpers.
// ---------------------------------------------------------------------------
static void *findMethod(void *klass, const char *name, int wantArgc) {
    if (!klass || !_class_get_methods) return NULL;
    void *iter = NULL, *m = NULL;
    while ((m = _class_get_methods(klass, &iter))) {
        const char *nm = _method_get_name(m);
        if (!nm || strcmp(nm, name) != 0) continue;
        int argc = _method_get_param_count ? (int)_method_get_param_count(m) : -1;
        if (wantArgc < 0 || argc == wantArgc) return m;
    }
    return NULL;
}

static inline void *methodNativePointer(void *method) {
    return method ? *(void **)method : NULL;
}

static BOOL resolveIL2CPP(void) {
    void *h = RTLD_DEFAULT;
    #define R(sym) _ ## sym = (fn_ ## sym)dlsym(h, "il2cpp_" #sym)
    R(class_get_methods);
    R(method_get_name);
    R(method_get_param_count);
    R(class_get_field_from_name);
    R(field_get_offset);
    #undef R
    return _class_get_methods && _method_get_name;
}

// ---------------------------------------------------------------------------
//  SlotResult field offsets.
// ---------------------------------------------------------------------------
static size_t fo_slotResult_symbols = 0;
static size_t fo_slotResult_win     = 0;

static void resolveSlotResultOffsets(void *klassResult) {
    if (!klassResult || !_class_get_field_from_name || !_field_get_offset) return;
    void *f1 = _class_get_field_from_name(klassResult, "slotSymbols");
    void *f2 = _class_get_field_from_name(klassResult, "win");
    if (f1) fo_slotResult_symbols = _field_get_offset(f1);
    if (f2) fo_slotResult_win     = _field_get_offset(f2);
    NSLog(@"[SLHook] SlotResult offsets: symbols=%zu win=%zu",
          fo_slotResult_symbols, fo_slotResult_win);
}

// ---------------------------------------------------------------------------
//  Hook originals.
// ---------------------------------------------------------------------------
static void *orig_TrySetNexSpinHitRecord     = NULL;
static void *orig_OnSpinResultReceived       = NULL;
static void *orig_SetFreezeResolve           = NULL;
static void *orig_activateWinSequence        = NULL;
static void *orig_ContainsAccumulationResult = NULL;

// ---------------------------------------------------------------------------
//  Hook bodies — all follow the same shape:
//    1. Call orig first (never delay the game's own path).
//    2. Format args with snprintf into stack buffers.
//    3. logLine() writes one line and fflushes.
// ---------------------------------------------------------------------------

// Each hook logs ENTER before calling orig, and EXIT after. Without the ENTER
// row we can't tell whether a crash lives in the hook body or inside the
// trampoline-executed copy of the original prologue. Prior v74/v75 builds put
// the log after orig — so when install succeeded but nothing ever fired, we
// couldn't distinguish "no spin happened" from "trampoline SIGILL on first
// call". ENTER-first breaks that tie.
static bool hook_TrySetNexSpinHitRecord(void *self, void *methodInfo) {
    typedef bool (*fn_t)(void *, void *);
    char a1[24]; snprintf(a1, sizeof a1, "%p", self);
    logLine("TrySetNexSpinHitRecord", a1, "", "", "enter");
    bool ret = ((fn_t)orig_TrySetNexSpinHitRecord)(self, methodInfo);
    logLine("TrySetNexSpinHitRecord", a1, "", ret ? "true" : "false", "exit");
    return ret;
}

static void hook_OnSpinResultReceived(void *self, void *response, void *methodInfo) {
    typedef void (*fn_t)(void *, void *, void *);
    char a1[24], a2[24];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%p", response);
    logLine("OnSpinResultReceived", a1, a2, "", "enter");
    ((fn_t)orig_OnSpinResultReceived)(self, response, methodInfo);
    logLine("OnSpinResultReceived", a1, a2, "", "exit");
}

static void hook_SetFreezeResolve(void *self, void *methodInfo) {
    typedef void (*fn_t)(void *, void *);
    char a1[24]; snprintf(a1, sizeof a1, "%p", self);
    logLine("SetFreezeResolve", a1, "", "", "enter");
    ((fn_t)orig_SetFreezeResolve)(self, methodInfo);
    logLine("SetFreezeResolve", a1, "", "", "exit");
}

static void hook_activateWinSequence(void *self, void *slotResult, void *methodInfo) {
    typedef void (*fn_t)(void *, void *, void *);
    char a1[24], a2[24];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%p", slotResult);
    logLine("activateWinSequence", a1, a2, "", "enter");
    ((fn_t)orig_activateWinSequence)(self, slotResult, methodInfo);

    // Field layout on SlotResult (dumped): symbols=16, win=24.
    // win−symbols=8 → slotSymbols is a reference. SlotSymbol3 boxed object =
    // 16-byte managed header, then 3 int32 fields at 16/20/24.
    char notes[96]; notes[0] = 0;
    if (slotResult && fo_slotResult_symbols) {
        uint8_t *base = (uint8_t *)slotResult;
        void *sym3Ref = *(void **)(base + fo_slotResult_symbols);
        int32_t win = fo_slotResult_win
                        ? *(int32_t *)(base + fo_slotResult_win)
                        : 0;
        int32_t s1 = 0, s2 = 0, s3 = 0;
        if ((uintptr_t)sym3Ref > 0x100000000ULL) {
            s1 = *(int32_t *)((uint8_t *)sym3Ref + 16);
            s2 = *(int32_t *)((uint8_t *)sym3Ref + 20);
            s3 = *(int32_t *)((uint8_t *)sym3Ref + 24);
        }
        snprintf(notes, sizeof notes,
                 "s1=%d|s2=%d|s3=%d|win=%d|ref=%p",
                 s1, s2, s3, win, sym3Ref);
    }
    logLine("activateWinSequence", a1, a2, "", notes);
}

static int32_t hook_ContainsAccumulationResult(void *self, int32_t defaultIcon, void *methodInfo) {
    typedef int32_t (*fn_t)(void *, int32_t, void *);
    char a1[24], a2[16];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%d", defaultIcon);
    logLine("ContainsAccumulationResult", a1, a2, "", "enter");
    int32_t ret = ((fn_t)orig_ContainsAccumulationResult)(self, defaultIcon, methodInfo);
    char r[16]; snprintf(r, sizeof r, "%d", ret);
    logLine("ContainsAccumulationResult", a1, a2, r, "exit");
    return ret;
}

// ---------------------------------------------------------------------------
//  Installer.
// ---------------------------------------------------------------------------
int SLSpinHook_InstallAll(void *klassMgr, void *klassResult) {
    if (s_installed) return 0;
    if (!klassMgr) {
        NSLog(@"[SLHook] klassMgr is NULL — aborting install");
        return 0;
    }
    if (!resolveIL2CPP()) {
        NSLog(@"[SLHook] IL2CPP method APIs unresolvable — aborting");
        return 0;
    }
    resolveSlotResultOffsets(klassResult);
    openEventLog();
    logLine("INSTALL_BEGIN", "", "", "", "");

    int installed = 0;

    #define TRY_HOOK(NAME, ARGC)                                                  \
        do {                                                                      \
            void *m = findMethod(klassMgr, #NAME, (ARGC));                        \
            void *fp = methodNativePointer(m);                                    \
            if (!fp) {                                                            \
                NSLog(@"[SLHook] %s: MethodInfo not found", #NAME);               \
                break;                                                            \
            }                                                                     \
            int r = SLInlineHook_Install(fp, (void *)&hook_##NAME,                \
                                         &orig_##NAME);                           \
            NSLog(@"[SLHook] %s: install=%d target=%p trampoline=%p",             \
                  #NAME, r, fp, orig_##NAME);                                     \
            if (r == 0) installed++;                                              \
        } while (0)

    TRY_HOOK(TrySetNexSpinHitRecord,     0);
    TRY_HOOK(OnSpinResultReceived,       1);
    TRY_HOOK(SetFreezeResolve,           0);
    TRY_HOOK(activateWinSequence,        1);
    TRY_HOOK(ContainsAccumulationResult, 1);

    #undef TRY_HOOK

    s_installed = (installed > 0);
    NSLog(@"[SLHook] installed %d/5 hooks", installed);
    char ri[8];
    snprintf(ri, sizeof ri, "%d", installed);
    logLine("INSTALL_END", "", "", ri, "session-start");
    return installed;
}
