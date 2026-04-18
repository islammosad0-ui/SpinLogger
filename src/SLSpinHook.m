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
#include <sys/mman.h>
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
//  Hook originals (4 hooks — TrySetNexSpinHitRecord is just `return false`,
//  not worth hooking).
// ---------------------------------------------------------------------------
static void *orig_OnSpinResultReceived       = NULL;
static void *orig_SetFreezeResolve           = NULL;
static void *orig_activateWinSequence        = NULL;
static void *orig_ContainsAccumulationResult = NULL;

// ---------------------------------------------------------------------------
//  Hook bodies.
//  IL2CPP ABI: trailing `void *methodInfo` parameter.
// ---------------------------------------------------------------------------

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
//  Focused arm64 inline hook.
//
//  All 4 target functions have clean prologues (STP/SUB/ADD, no PC-relative
//  instructions in the first 16 bytes). Verified by dumping actual bytes.
//
//  Approach:
//    1. Allocate RWX trampoline page.
//    2. Copy first 16 bytes of target → trampoline.
//    3. Append absolute jump (LDR X17, [PC,#8]; BR X17; .quad addr) to
//       trampoline → target+16.
//    4. Patch target's first 16 bytes with absolute jump → hook function.
//    5. Return trampoline as the "orig" pointer.
//
//  Uses vm_protect to make __TEXT writable, then restores RX.
// ---------------------------------------------------------------------------
#define PATCH_SIZE 16  // 4 arm64 instructions

static void buildAbsJump(uint8_t *dst, uint64_t addr) {
    // LDR X17, [PC, #8]  → 0x58000051
    dst[0] = 0x51; dst[1] = 0x00; dst[2] = 0x00; dst[3] = 0x58;
    // BR X17              → 0xD61F0220
    dst[4] = 0x20; dst[5] = 0x02; dst[6] = 0x1F; dst[7] = 0xD6;
    // .quad absolute target
    memcpy(dst + 8, &addr, 8);
}

static int inlineHook(void *target, void *replacement, void **outOrig,
                      const char *name) {
    if (!target || !replacement) return -1;

    // Validate: reject if any of the first 4 instructions is RET (function
    // too short) — safety net in case we're called on TrySetNexSpinHitRecord.
    uint32_t *insns = (uint32_t *)target;
    for (int i = 0; i < 4; i++) {
        if (insns[i] == 0xD65F03C0) {  // RET
            char bc[128];
            snprintf(bc, sizeof bc, "REJECT %s: RET at word %d", name, i);
            breadcrumb(bc);
            return -5;
        }
    }

    // 1. Allocate trampoline (RWX page).
    uint8_t *tramp = (uint8_t *)mmap(NULL, 4096,
                                      PROT_READ | PROT_WRITE | PROT_EXEC,
                                      MAP_ANON | MAP_PRIVATE, -1, 0);
    if (tramp == MAP_FAILED) {
        // Fallback: RW then mprotect.
        tramp = (uint8_t *)mmap(NULL, 4096,
                                 PROT_READ | PROT_WRITE,
                                 MAP_ANON | MAP_PRIVATE, -1, 0);
        if (tramp == MAP_FAILED) {
            breadcrumb("mmap FAILED");
            return -2;
        }
    }

    // 2. Copy original 16 bytes → trampoline.
    memcpy(tramp, target, PATCH_SIZE);

    // 3. Append absolute jump back to target + 16.
    buildAbsJump(tramp + PATCH_SIZE,
                 (uint64_t)((uint8_t *)target + PATCH_SIZE));

    // Make trampoline executable.
    mprotect(tramp, 4096, PROT_READ | PROT_EXEC);
    sys_icache_invalidate(tramp, PATCH_SIZE + 16);

    // 4. Build the redirect stub for the target.
    uint8_t stub[PATCH_SIZE];
    buildAbsJump(stub, (uint64_t)replacement);

    // 5. Make target writable, patch, restore RX.
    const vm_address_t PAGE_MASK = 0x3FFF;  // 16KB iOS pages
    vm_address_t pageStart = (vm_address_t)target & ~PAGE_MASK;
    vm_size_t pageSpan = (((vm_address_t)target + PATCH_SIZE) - pageStart
                          + PAGE_MASK) & ~PAGE_MASK;

    kern_return_t kr = vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
                                  VM_PROT_READ | VM_PROT_WRITE);
    if (kr != KERN_SUCCESS) {
        kr = vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
                        VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY);
    }
    {
        char bc[128];
        snprintf(bc, sizeof bc, "VMPROTECT %s kr=%d page=%p span=%zu",
                 name, (int)kr, (void *)pageStart, (size_t)pageSpan);
        breadcrumb(bc);
    }
    if (kr != KERN_SUCCESS) {
        munmap(tramp, 4096);
        return -3;
    }

    memcpy(target, stub, PATCH_SIZE);

    // Restore RX.
    vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
               VM_PROT_READ | VM_PROT_EXECUTE);

    sys_icache_invalidate(target, PATCH_SIZE);

    if (outOrig) *outOrig = tramp;

    {
        char bc[128];
        snprintf(bc, sizeof bc, "PATCHED %s tramp=%p", name, tramp);
        breadcrumb(bc);
    }
    return 0;
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
//  Installer — targeted inline hooks on 4 functions with verified-safe
//  prologues. TrySetNexSpinHitRecord skipped (just `return false`).
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

    #define TRY_HOOK(NAME, ARGC, IDX)                                             \
        do {                                                                      \
            if (!s_hookEnabled[(IDX)]) {                                          \
                breadcrumb("SKIP " #NAME);                                        \
                break;                                                            \
            }                                                                     \
            breadcrumb("FIND " #NAME);                                            \
            void *m = findMethod(klassMgr, #NAME, (ARGC));                        \
            if (!m) {                                                             \
                breadcrumb("NOTFOUND " #NAME " (method)");                        \
                break;                                                            \
            }                                                                     \
            void *fp = methodNativePointer(m);                                    \
            if (!fp) {                                                            \
                breadcrumb("NOTFOUND " #NAME " (fp)");                            \
                break;                                                            \
            }                                                                     \
            /* Dump prologue */                                                   \
            {                                                                     \
                uint32_t *w = (uint32_t *)fp;                                     \
                char pd[256];                                                     \
                snprintf(pd, sizeof pd,                                           \
                    "PROLOGUE " #NAME " @%p: "                                    \
                    "%08x %08x %08x %08x",                                        \
                    fp, w[0], w[1], w[2], w[3]);                                  \
                breadcrumb(pd);                                                   \
            }                                                                     \
            breadcrumb("HOOK " #NAME);                                            \
            int r = inlineHook(fp, (void *)&hook_##NAME, &orig_##NAME, #NAME);    \
            char bc[128];                                                         \
            snprintf(bc, sizeof bc, "HOOK " #NAME " rc=%d orig=%p",               \
                     r, orig_##NAME);                                             \
            breadcrumb(bc);                                                       \
            if (r == 0) {                                                         \
                installed++;                                                      \
                breadcrumb("OK " #NAME);                                          \
            } else {                                                              \
                breadcrumb("FAIL " #NAME " rc=" #IDX);                            \
            }                                                                     \
        } while (0)

    TRY_HOOK(OnSpinResultReceived,       1, 0);
    TRY_HOOK(SetFreezeResolve,           0, 1);
    TRY_HOOK(activateWinSequence,        1, 2);
    TRY_HOOK(ContainsAccumulationResult, 1, 3);

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
