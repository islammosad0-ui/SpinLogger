#import "SLSpinHook.h"
#include <dlfcn.h>
#include <string.h>
#include <stdint.h>
#include <stdio.h>
#include <stdbool.h>
#include <sys/time.h>
#include <pthread.h>
#include <mach/mach.h>
#include <mach/vm_map.h>
#include <libkern/OSCacheControl.h>

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
}

// ---------------------------------------------------------------------------
//  Crash breadcrumb.
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
//  Hot-patch inline hook — NO trampoline needed.
//
//  Problem: iOS blocks executing from mmap'd anonymous pages (JIT
//  restriction), so trampoline-based hooks crash when calling orig.
//
//  Solution: when the hook fires, temporarily restore the original 16 bytes,
//  call the original function directly, then re-patch. Unity's main thread
//  is single-threaded so this is safe.
//
//  Each hook entry stores:
//    - target: the function address being hooked
//    - saved[16]: the original 16 bytes
//    - stub[16]: the redirect stub (LDR X17/BR X17/addr)
//    - pageStart, pageSpan: cached vm_protect parameters
// ---------------------------------------------------------------------------
#define PATCH_SIZE 16
#define MAX_HOOKS  8

typedef struct {
    void       *target;
    uint8_t     saved[PATCH_SIZE];
    uint8_t     stub[PATCH_SIZE];
    vm_address_t pageStart;
    vm_size_t    pageSpan;
    bool         active;
} HookEntry;

static HookEntry s_hooks[MAX_HOOKS];
static int s_hookCount = 0;
static pthread_mutex_t s_patchMu = PTHREAD_MUTEX_INITIALIZER;

static void buildAbsJump(uint8_t *dst, uint64_t addr) {
    // LDR X17, [PC, #8]
    dst[0] = 0x51; dst[1] = 0x00; dst[2] = 0x00; dst[3] = 0x58;
    // BR X17
    dst[4] = 0x20; dst[5] = 0x02; dst[6] = 0x1F; dst[7] = 0xD6;
    memcpy(dst + 8, &addr, 8);
}

static void patchBytes(void *target, const void *bytes, size_t n,
                       vm_address_t pageStart, vm_size_t pageSpan) {
    vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
               VM_PROT_READ | VM_PROT_WRITE);
    memcpy(target, bytes, n);
    vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
               VM_PROT_READ | VM_PROT_EXECUTE);
    sys_icache_invalidate(target, n);
}

// Temporarily restore original bytes, call through, re-patch.
// Returns the hook entry index so the hook body knows which entry to use.
static int findHookIdx(void *target) {
    for (int i = 0; i < s_hookCount; i++) {
        if (s_hooks[i].target == target) return i;
    }
    return -1;
}

static void unpatch(int idx) {
    HookEntry *h = &s_hooks[idx];
    patchBytes(h->target, h->saved, PATCH_SIZE, h->pageStart, h->pageSpan);
}

static void repatch(int idx) {
    HookEntry *h = &s_hooks[idx];
    patchBytes(h->target, h->stub, PATCH_SIZE, h->pageStart, h->pageSpan);
}

static int installHook(void *target, void *replacement, const char *name) {
    if (!target || !replacement || s_hookCount >= MAX_HOOKS) return -1;

    // Reject tiny functions (RET in first 4 instructions).
    uint32_t *insns = (uint32_t *)target;
    for (int i = 0; i < 4; i++) {
        if (insns[i] == 0xD65F03C0) {
            breadcrumb("REJECT (RET in prologue)");
            return -5;
        }
    }

    int idx = s_hookCount;
    HookEntry *h = &s_hooks[idx];
    h->target = target;

    // Save original bytes.
    memcpy(h->saved, target, PATCH_SIZE);

    // Build redirect stub.
    buildAbsJump(h->stub, (uint64_t)replacement);

    // Cache page params (16KB iOS pages).
    const vm_address_t PAGE_MASK = 0x3FFF;
    h->pageStart = (vm_address_t)target & ~PAGE_MASK;
    h->pageSpan  = (((vm_address_t)target + PATCH_SIZE) - h->pageStart
                     + PAGE_MASK) & ~PAGE_MASK;

    // Initial vm_protect + patch.
    kern_return_t kr = vm_protect(mach_task_self(),
                                  h->pageStart, h->pageSpan, FALSE,
                                  VM_PROT_READ | VM_PROT_WRITE);
    if (kr != KERN_SUCCESS) {
        kr = vm_protect(mach_task_self(),
                        h->pageStart, h->pageSpan, FALSE,
                        VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY);
    }
    {
        char bc[128];
        snprintf(bc, sizeof bc, "VMPROTECT %s kr=%d page=%p",
                 name, (int)kr, (void *)h->pageStart);
        breadcrumb(bc);
    }
    if (kr != KERN_SUCCESS) return -3;

    memcpy(target, h->stub, PATCH_SIZE);

    vm_protect(mach_task_self(), h->pageStart, h->pageSpan, FALSE,
               VM_PROT_READ | VM_PROT_EXECUTE);
    sys_icache_invalidate(target, PATCH_SIZE);

    h->active = true;
    s_hookCount++;

    char bc[128];
    snprintf(bc, sizeof bc, "PATCHED %s idx=%d", name, idx);
    breadcrumb(bc);
    return idx;
}

// ---------------------------------------------------------------------------
//  Hook targets — stored as function pointers so hooks can call originals
//  via unpatch/repatch.
// ---------------------------------------------------------------------------
static void *fp_OnSpinResultReceived       = NULL;
static void *fp_SetFreezeResolve           = NULL;
static void *fp_activateWinSequence        = NULL;
static void *fp_ContainsAccumulationResult = NULL;

static int idx_OnSpinResultReceived       = -1;
static int idx_SetFreezeResolve           = -1;
static int idx_activateWinSequence        = -1;
static int idx_ContainsAccumulationResult = -1;

// ---------------------------------------------------------------------------
//  Hook bodies.
//  Each hook: log ENTER → unpatch → call original → repatch → log EXIT.
//  IL2CPP ABI: trailing void *methodInfo parameter.
// ---------------------------------------------------------------------------

static void hook_OnSpinResultReceived(void *self, void *response, void *methodInfo) {
    typedef void (*fn_t)(void *, void *, void *);
    char a1[24], a2[24];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%p", response);
    logLine("OnSpinResultReceived", a1, a2, "", "enter");

    pthread_mutex_lock(&s_patchMu);
    unpatch(idx_OnSpinResultReceived);
    ((fn_t)fp_OnSpinResultReceived)(self, response, methodInfo);
    repatch(idx_OnSpinResultReceived);
    pthread_mutex_unlock(&s_patchMu);

    logLine("OnSpinResultReceived", a1, a2, "", "exit");
}

static void hook_SetFreezeResolve(void *self, void *methodInfo) {
    typedef void (*fn_t)(void *, void *);
    char a1[24]; snprintf(a1, sizeof a1, "%p", self);
    logLine("SetFreezeResolve", a1, "", "", "enter");

    pthread_mutex_lock(&s_patchMu);
    unpatch(idx_SetFreezeResolve);
    ((fn_t)fp_SetFreezeResolve)(self, methodInfo);
    repatch(idx_SetFreezeResolve);
    pthread_mutex_unlock(&s_patchMu);

    logLine("SetFreezeResolve", a1, "", "", "exit");
}

static void hook_activateWinSequence(void *self, void *slotResult, void *methodInfo) {
    typedef void (*fn_t)(void *, void *, void *);
    char a1[24], a2[24];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%p", slotResult);
    logLine("activateWinSequence", a1, a2, "", "enter");

    pthread_mutex_lock(&s_patchMu);
    unpatch(idx_activateWinSequence);
    ((fn_t)fp_activateWinSequence)(self, slotResult, methodInfo);
    repatch(idx_activateWinSequence);
    pthread_mutex_unlock(&s_patchMu);

    // Read SlotResult fields after original returns.
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

    pthread_mutex_lock(&s_patchMu);
    unpatch(idx_ContainsAccumulationResult);
    int32_t ret = ((fn_t)fp_ContainsAccumulationResult)(self, defaultIcon, methodInfo);
    repatch(idx_ContainsAccumulationResult);
    pthread_mutex_unlock(&s_patchMu);

    char r[16]; snprintf(r, sizeof r, "%d", ret);
    logLine("ContainsAccumulationResult", a1, a2, r, "exit");
    return ret;
}

// ---------------------------------------------------------------------------
//  Hook config.
// ---------------------------------------------------------------------------
static bool s_hookEnabled[4] = { true, true, true, true };
static const char *s_hookNames[4] = {
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
    if (!f) return;
    for (int i = 0; i < 4; i++) s_hookEnabled[i] = false;

    char line[128];
    while (fgets(line, sizeof line, f)) {
        size_t len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) line[--len] = 0;
        if (len == 0) continue;
        if (strcmp(line, "ALL") == 0) {
            for (int i = 0; i < 4; i++) s_hookEnabled[i] = true;
            break;
        }
        if (strcmp(line, "NONE") == 0) break;
        for (int i = 0; i < 4; i++) {
            if (strcmp(line, s_hookNames[i]) == 0) s_hookEnabled[i] = true;
        }
    }
    fclose(f);
}

// ---------------------------------------------------------------------------
//  Installer.
// ---------------------------------------------------------------------------
int SLSpinHook_InstallAll(void *klassMgr, void *klassResult) {
    if (s_installed) return 0;

    breadcrumb("STEP 0: entry");

    if (!klassMgr) {
        breadcrumb("ABORT: klassMgr NULL");
        return 0;
    }

    breadcrumb("STEP 1: resolveIL2CPP");
    if (!resolveIL2CPP()) {
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

    #define TRY_HOOK(NAME, ARGC, IDX_VAR, FP_VAR)                                \
        do {                                                                      \
            if (!s_hookEnabled[(IDX_VAR##_cfg)]) {                                \
                breadcrumb("SKIP " #NAME);                                        \
                break;                                                            \
            }                                                                     \
            breadcrumb("FIND " #NAME);                                            \
            void *m = findMethod(klassMgr, #NAME, (ARGC));                        \
            if (!m) { breadcrumb("NOTFOUND " #NAME); break; }                     \
            void *fp = methodNativePointer(m);                                    \
            if (!fp) { breadcrumb("NOTFOUND " #NAME " fp"); break; }              \
            FP_VAR = fp;                                                          \
            breadcrumb("HOOK " #NAME);                                            \
            int r = installHook(fp, (void *)&hook_##NAME, #NAME);                 \
            char bc[128];                                                         \
            snprintf(bc, sizeof bc, "HOOK " #NAME " rc=%d", r);                   \
            breadcrumb(bc);                                                       \
            if (r >= 0) {                                                         \
                IDX_VAR = r;                                                      \
                installed++;                                                      \
                breadcrumb("OK " #NAME);                                          \
            } else {                                                              \
                breadcrumb("FAIL " #NAME);                                        \
            }                                                                     \
        } while (0)

    // Config indices for the enabled array.
    const int idx_OnSpinResultReceived_cfg       = 0;
    const int idx_SetFreezeResolve_cfg           = 1;
    const int idx_activateWinSequence_cfg        = 2;
    const int idx_ContainsAccumulationResult_cfg = 3;

    TRY_HOOK(OnSpinResultReceived,       1,
             idx_OnSpinResultReceived,       fp_OnSpinResultReceived);
    TRY_HOOK(SetFreezeResolve,           0,
             idx_SetFreezeResolve,           fp_SetFreezeResolve);
    TRY_HOOK(activateWinSequence,        1,
             idx_activateWinSequence,        fp_activateWinSequence);
    TRY_HOOK(ContainsAccumulationResult, 1,
             idx_ContainsAccumulationResult, fp_ContainsAccumulationResult);

    #undef TRY_HOOK

    s_installed = (installed > 0);
    char ri[64];
    snprintf(ri, sizeof ri, "%d", installed);
    logLine("INSTALL_END", "", "", ri, "session-start");

    char done[64];
    snprintf(done, sizeof done, "DONE: %d/4 installed", installed);
    breadcrumb(done);
    return installed;
}
