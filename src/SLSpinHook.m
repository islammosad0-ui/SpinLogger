#import "SLSpinHook.h"
#include <dlfcn.h>
#include <string.h>
#include <stdint.h>
#include <stdio.h>
#include <stdbool.h>
#include <sys/time.h>
#include <pthread.h>

// ---------------------------------------------------------------------------
//  Dobby inline-hook API (static lib linked at build time).
// ---------------------------------------------------------------------------
extern int DobbyHook(void *address, void *replace_call, void **origin_call);

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
//  NSLog + NSString on the hot callback path starves the Unity main thread
//  enough to trip the iOS launch watchdog. This path uses a single FILE*,
//  line-buffered, fflushed every write.
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
//  Hook bodies.
//  All follow the same shape:
//    1. Log ENTER (so we can tell if a crash is in trampoline vs hook body).
//    2. Call orig (never delay the game's own path).
//    3. Log EXIT with return value / extracted fields.
//
//  IL2CPP ABI: every method receives a trailing `void *methodInfo` parameter
//  that MUST be forwarded to the original.
// ---------------------------------------------------------------------------

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
// ---------------------------------------------------------------------------
//  Crash breadcrumb: writes current step to Documents/hook_breadcrumb.txt
//  with fflush so it survives a crash. After a crash, open this file to see
//  exactly which hook killed the app.
// ---------------------------------------------------------------------------
static FILE *s_bcFp = NULL;

static void breadcrumb(const char *msg) {
    if (!s_bcFp) {
        NSString *docs = NSSearchPathForDirectoriesInDomains(
            NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
        NSString *path = [docs stringByAppendingPathComponent:@"hook_breadcrumb.txt"];
        s_bcFp = fopen(path.fileSystemRepresentation, "w");
        if (!s_bcFp) return;
    }
    fprintf(s_bcFp, "%s\n", msg);
    fflush(s_bcFp);
}

// ---------------------------------------------------------------------------
//  Hook enable config: reads Documents/hook_config.txt to decide which hooks
//  to install. If the file doesn't exist, ALL hooks are enabled by default.
//
//  Format — one hook name per line to ENABLE, e.g.:
//      activateWinSequence
//      ContainsAccumulationResult
//
//  Or write "NONE" to disable all hooks (test that Dobby linking alone is ok).
//  Or write "ALL" (or just don't create the file) to enable everything.
// ---------------------------------------------------------------------------
static bool s_hookEnabled[5] = { true, true, true, true, true };
static const char *s_hookNames[5] = {
    "TrySetNexSpinHitRecord",
    "OnSpinResultReceived",
    "SetFreezeResolve",
    "activateWinSequence",
    "ContainsAccumulationResult",
};

static void loadHookConfig(void) {
    NSString *docs = NSSearchPathForDirectoriesInDomains(
        NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
    NSString *path = [docs stringByAppendingPathComponent:@"hook_config.txt"];
    FILE *f = fopen(path.fileSystemRepresentation, "r");
    if (!f) {
        NSLog(@"[SLHook] No hook_config.txt — all 5 hooks enabled");
        return;
    }
    // If file exists, default all to OFF, then enable listed ones.
    for (int i = 0; i < 5; i++) s_hookEnabled[i] = false;

    char line[128];
    while (fgets(line, sizeof line, f)) {
        // Strip newline.
        size_t len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) line[--len] = 0;
        if (len == 0) continue;
        if (strcmp(line, "ALL") == 0) {
            for (int i = 0; i < 5; i++) s_hookEnabled[i] = true;
            break;
        }
        if (strcmp(line, "NONE") == 0) break;
        for (int i = 0; i < 5; i++) {
            if (strcmp(line, s_hookNames[i]) == 0) s_hookEnabled[i] = true;
        }
    }
    fclose(f);
    for (int i = 0; i < 5; i++) {
        NSLog(@"[SLHook] hook_config: %s = %s",
              s_hookNames[i], s_hookEnabled[i] ? "ON" : "OFF");
    }
}

int SLSpinHook_InstallAll(void *klassMgr, void *klassResult) {
    if (s_installed) return 0;

    breadcrumb("STEP 0: entry");

    if (!klassMgr) {
        NSLog(@"[SLHook] klassMgr is NULL — aborting install");
        breadcrumb("ABORT: klassMgr NULL");
        return 0;
    }

    breadcrumb("STEP 1: resolveIL2CPP");
    if (!resolveIL2CPP()) {
        NSLog(@"[SLHook] IL2CPP method APIs unresolvable — aborting");
        breadcrumb("ABORT: IL2CPP unresolvable");
        return 0;
    }

    breadcrumb("STEP 2: resolveSlotResultOffsets");
    resolveSlotResultOffsets(klassResult);

    breadcrumb("STEP 3: openEventLog");
    openEventLog();
    logLine("INSTALL_BEGIN", "", "", "", "");

    breadcrumb("STEP 4: loadHookConfig");
    loadHookConfig();

    int installed = 0;
    int hookIdx = 0;

    #define TRY_HOOK(NAME, ARGC, IDX)                                             \
        do {                                                                      \
            if (!s_hookEnabled[(IDX)]) {                                          \
                breadcrumb("SKIP " #NAME " (disabled)");                          \
                NSLog(@"[SLHook] %s: SKIPPED (disabled in hook_config.txt)",      \
                      #NAME);                                                     \
                break;                                                            \
            }                                                                     \
            breadcrumb("FIND " #NAME);                                            \
            void *m = findMethod(klassMgr, #NAME, (ARGC));                        \
            void *fp = methodNativePointer(m);                                    \
            if (!fp) {                                                            \
                NSLog(@"[SLHook] %s: MethodInfo not found", #NAME);               \
                breadcrumb("NOTFOUND " #NAME);                                    \
                break;                                                            \
            }                                                                     \
            breadcrumb("DOBBY " #NAME " target=" #NAME);                          \
            int r = DobbyHook(fp, (void *)&hook_##NAME, &orig_##NAME);            \
            NSLog(@"[SLHook] %s: dobby=%d target=%p trampoline=%p",               \
                  #NAME, r, fp, orig_##NAME);                                     \
            if (r == 0) {                                                         \
                installed++;                                                      \
                breadcrumb("OK " #NAME);                                          \
            } else {                                                              \
                breadcrumb("FAIL " #NAME);                                        \
            }                                                                     \
        } while (0)

    TRY_HOOK(TrySetNexSpinHitRecord,     0, 0);
    TRY_HOOK(OnSpinResultReceived,       1, 1);
    TRY_HOOK(SetFreezeResolve,           0, 2);
    TRY_HOOK(activateWinSequence,        1, 3);
    TRY_HOOK(ContainsAccumulationResult, 1, 4);

    #undef TRY_HOOK

    s_installed = (installed > 0);
    NSLog(@"[SLHook] installed %d/5 hooks (Dobby)", installed);
    char ri[8];
    snprintf(ri, sizeof ri, "%d", installed);
    logLine("INSTALL_END", "", "", ri, "session-start");

    char done[64];
    snprintf(done, sizeof done, "DONE: %d/5 installed", installed);
    breadcrumb(done);
    return installed;
}
