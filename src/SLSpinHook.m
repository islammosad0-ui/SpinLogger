#import "SLSpinHook.h"
#include <dlfcn.h>
#include <string.h>
#include <stdint.h>
#include <stdio.h>
#include <stdbool.h>
#include <sys/time.h>
#include <pthread.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>

#ifdef SPINHOOK_HAS_DOBBY
#include "dobby.h"
#endif

// ---------------------------------------------------------------------------
//  SLSpinHook — hook installation for LiveContainer.
//
//  Modes (tried in this order):
//    1. ELLEKIT — dlsym MSHookFunction (only works if user installed
//       ElleKit in LC's LiveContainer.app/Frameworks/CydiaSubstrate.framework).
//    2. DOBBY   — statically linked jmpews/Dobby, always available.
//       Uses vm_remap to clone the target page, patches the clone, and
//       remaps RX — bypasses CS_KILL on signed __TEXT pages, handles arm64e
//       PAC, and has a battle-tested PC-relative instruction vetter.
//    3. HOOKSLOT — if binary was pre-patched with offline_patcher.py
//       (magic marker in __DATA). Keeps v69 workflow alive as a last resort.
//    4. DIAG    — discovery-only; writes hook_discovery.txt. Set `DIAG` in
//       Documents/hook_config.txt to force this mode.
//
//  Everything routes through the same four hook bodies. Originals are
//  stored in s_origFn[0..3] regardless of which mode populated them.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
//  IL2CPP APIs.
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
//  Event log.
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
//  Breadcrumb (install-flow diagnostics).
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
//  Method resolution.
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
//  Originals (populated by ElleKit or HOOKSLOT).
// ---------------------------------------------------------------------------
static void *s_origFn[4] = {NULL, NULL, NULL, NULL};

// ---------------------------------------------------------------------------
//  Hook bodies.
//
//  These are identical regardless of which mode installed the hook — both
//  ElleKit and HOOKSLOT deliver `orig` through s_origFn[N].
// ---------------------------------------------------------------------------
static void hook_OnSpinResultReceived(void *self, void *response, void *methodInfo) {
    typedef void (*fn_t)(void *, void *, void *);
    char a1[24], a2[24];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%p", response);
    logLine("OnSpinResultReceived", a1, a2, "", "enter");

    if (s_origFn[0]) ((fn_t)s_origFn[0])(self, response, methodInfo);

    logLine("OnSpinResultReceived", a1, a2, "", "exit");
}

static void hook_SetFreezeResolve(void *self, void *methodInfo) {
    typedef void (*fn_t)(void *, void *);
    char a1[24]; snprintf(a1, sizeof a1, "%p", self);
    logLine("SetFreezeResolve", a1, "", "", "enter");

    if (s_origFn[1]) ((fn_t)s_origFn[1])(self, methodInfo);

    logLine("SetFreezeResolve", a1, "", "", "exit");
}

static void hook_activateWinSequence(void *self, void *slotResult, void *methodInfo) {
    typedef void (*fn_t)(void *, void *, void *);
    char a1[24], a2[24];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%p", slotResult);
    logLine("activateWinSequence", a1, a2, "", "enter");

    if (s_origFn[2]) ((fn_t)s_origFn[2])(self, slotResult, methodInfo);

    logLine("activateWinSequence", a1, a2, "", "exit");
}

static int32_t hook_ContainsAccumulationResult(void *self, int32_t defaultIcon, void *methodInfo) {
    typedef int32_t (*fn_t)(void *, int32_t, void *);
    char a1[24], a2[16];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%d", defaultIcon);
    logLine("ContainsAccumulationResult", a1, a2, "", "enter");

    int32_t ret = 0;
    if (s_origFn[3]) ret = ((fn_t)s_origFn[3])(self, defaultIcon, methodInfo);

    char r[16]; snprintf(r, sizeof r, "%d", ret);
    logLine("ContainsAccumulationResult", a1, a2, r, "exit");
    return ret;
}

// ---------------------------------------------------------------------------
//  MODE 1 — ELLEKIT (MSHookFunction via dlsym).
//
//  LiveContainer's TweakLoader loads ElleKit before the guest's injected
//  dylib constructors run, so MSHookFunction is resolvable via RTLD_DEFAULT.
//  ElleKit uses vm_remap to clone the target page, patches the clone, and
//  re-maps it RX — this bypasses CS_KILL on signed __TEXT pages, handles
//  arm64e PAC, and has a battle-tested PC-relative instruction vetter.
// ---------------------------------------------------------------------------
typedef void (*fn_MSHookFunction)(void *target, void *replacement, void **orig);

static fn_MSHookFunction resolveMSHookFunction(void) {
    // Try canonical Substrate/ElleKit name first, then ElleKit-native.
    fn_MSHookFunction fn = (fn_MSHookFunction)dlsym(RTLD_DEFAULT, "MSHookFunction");
    if (!fn) fn = (fn_MSHookFunction)dlsym(RTLD_DEFAULT, "EKHookFunction");
    return fn;
}

static void logLoadedHookImages(void) {
    // Diagnostic: log any loaded image that looks like a hooking framework so
    // we can see whether TweakLoader / ElleKit actually got injected.
    uint32_t n = _dyld_image_count();
    for (uint32_t i = 0; i < n; i++) {
        const char *name = _dyld_get_image_name(i);
        if (!name) continue;
        if (strstr(name, "ElleKit")     || strstr(name, "ellekit")     ||
            strstr(name, "TweakLoader") || strstr(name, "Substrate")   ||
            strstr(name, "Substitute")  || strstr(name, "Dobby")       ||
            strstr(name, "CydiaSubstrate")) {
            char bc[512];
            snprintf(bc, sizeof bc, "IMG: %s", name);
            breadcrumb(bc);
        }
    }
}

static int installViaElleKit(void *klassMgr) {
    fn_MSHookFunction mshook = resolveMSHookFunction();
    if (!mshook) {
        breadcrumb("ELLEKIT: MSHookFunction not resolvable via dlsym");
        return 0;
    }
    breadcrumb("ELLEKIT: MSHookFunction resolved");

    struct { const char *name; int argc; int idx; void *replacement; } targets[] = {
        {"OnSpinResultReceived",        1, 0, (void *)hook_OnSpinResultReceived},
        {"SetFreezeResolve",            0, 1, (void *)hook_SetFreezeResolve},
        {"activateWinSequence",         1, 2, (void *)hook_activateWinSequence},
        {"ContainsAccumulationResult",  1, 3, (void *)hook_ContainsAccumulationResult},
    };

    int installed = 0;
    for (int i = 0; i < 4; i++) {
        void *m = findMethod(klassMgr, targets[i].name, targets[i].argc);
        if (!m) {
            char bc[128];
            snprintf(bc, sizeof bc, "ELLEKIT: method not found: %s", targets[i].name);
            breadcrumb(bc);
            continue;
        }
        void *fp = methodNativePointer(m);
        if (!fp) {
            char bc[128];
            snprintf(bc, sizeof bc, "ELLEKIT: no native ptr: %s", targets[i].name);
            breadcrumb(bc);
            continue;
        }

        char bc[256];
        snprintf(bc, sizeof bc, "ELLEKIT: hooking %s at %p", targets[i].name, fp);
        breadcrumb(bc);

        void *orig = NULL;
        mshook(fp, targets[i].replacement, &orig);
        s_origFn[targets[i].idx] = orig;

        if (orig) {
            installed++;
            snprintf(bc, sizeof bc, "ELLEKIT: %s hooked, orig=%p", targets[i].name, orig);
            breadcrumb(bc);

            char fpStr[24], origStr[24];
            snprintf(fpStr, sizeof fpStr, "%p", fp);
            snprintf(origStr, sizeof origStr, "%p", orig);
            logLine(targets[i].name, fpStr, origStr, "", "hooked-ellekit");
        } else {
            snprintf(bc, sizeof bc, "ELLEKIT: %s hook FAILED (orig=NULL)", targets[i].name);
            breadcrumb(bc);
        }
    }
    return installed;
}

// ---------------------------------------------------------------------------
//  MODE 2 — DOBBY (statically linked).
//
//  DobbyHook takes (target, replacement, out_origCallee). Returns 0 on
//  success. We link Dobby as a static .a at build time (see build.yml),
//  so no runtime dlsym / dependency on LC's tweak framework.
// ---------------------------------------------------------------------------
#ifdef SPINHOOK_HAS_DOBBY
static int installViaDobby(void *klassMgr) {
    breadcrumb("DOBBY: using statically-linked jmpews/Dobby");

    struct { const char *name; int argc; int idx; void *replacement; } targets[] = {
        {"OnSpinResultReceived",        1, 0, (void *)hook_OnSpinResultReceived},
        {"SetFreezeResolve",            0, 1, (void *)hook_SetFreezeResolve},
        {"activateWinSequence",         1, 2, (void *)hook_activateWinSequence},
        {"ContainsAccumulationResult",  1, 3, (void *)hook_ContainsAccumulationResult},
    };

    int installed = 0;
    for (int i = 0; i < 4; i++) {
        void *m = findMethod(klassMgr, targets[i].name, targets[i].argc);
        if (!m) {
            char bc[128];
            snprintf(bc, sizeof bc, "DOBBY: method not found: %s", targets[i].name);
            breadcrumb(bc);
            continue;
        }
        void *fp = methodNativePointer(m);
        if (!fp) {
            char bc[128];
            snprintf(bc, sizeof bc, "DOBBY: no native ptr: %s", targets[i].name);
            breadcrumb(bc);
            continue;
        }

        char bc[256];
        snprintf(bc, sizeof bc, "DOBBY: hooking %s at %p", targets[i].name, fp);
        breadcrumb(bc);

        void *orig = NULL;
        int rc = DobbyHook(fp, targets[i].replacement, &orig);
        if (rc == 0 && orig) {
            s_origFn[targets[i].idx] = orig;
            installed++;
            snprintf(bc, sizeof bc, "DOBBY: %s hooked, orig=%p", targets[i].name, orig);
            breadcrumb(bc);

            char fpStr[24], origStr[24];
            snprintf(fpStr, sizeof fpStr, "%p", fp);
            snprintf(origStr, sizeof origStr, "%p", orig);
            logLine(targets[i].name, fpStr, origStr, "", "hooked-dobby");
        } else {
            snprintf(bc, sizeof bc, "DOBBY: %s hook FAILED (rc=%d orig=%p)",
                     targets[i].name, rc, orig);
            breadcrumb(bc);
        }
    }
    return installed;
}
#endif // SPINHOOK_HAS_DOBBY

// ---------------------------------------------------------------------------
//  MODE 3 — HOOKSLOT (pre-patched binary via offline_patcher.py).
//
//  Fallback kept so that v69's flow (prologue-patched IPA + hookslot table
//  in __DATA) still works even if ElleKit isn't present.
// ---------------------------------------------------------------------------
#define HOOKSLOT_MAGIC0 0xDEADBEEF5350494EULL
#define HOOKSLOT_MAGIC1 0x484F4F4B534C4F54ULL

static int installViaHookslots(void) {
    for (uint32_t img = 0; img < _dyld_image_count(); img++) {
        const struct mach_header_64 *hdr =
            (const struct mach_header_64 *)_dyld_get_image_header(img);
        if (!hdr || hdr->magic != MH_MAGIC_64) continue;
        intptr_t slide = _dyld_get_image_vmaddr_slide(img);

        const uint8_t *p = (const uint8_t *)(hdr + 1);
        for (uint32_t c = 0; c < hdr->ncmds; c++) {
            const struct load_command *lc = (const struct load_command *)p;
            if (lc->cmd == LC_SEGMENT_64) {
                const struct segment_command_64 *seg =
                    (const struct segment_command_64 *)p;
                if (strncmp(seg->segname, "__DATA", 6) == 0) {
                    uintptr_t base = seg->vmaddr + slide;
                    uint64_t *scan = (uint64_t *)base;
                    uint64_t *end  = (uint64_t *)(base + seg->vmsize - 80);
                    for (; scan < end; scan++) {
                        if (scan[0] == HOOKSLOT_MAGIC0 &&
                            scan[1] == HOOKSLOT_MAGIC1) {
                            char bc[128];
                            snprintf(bc, sizeof bc,
                                     "HOOKSLOT: magic at %p (img %d slide 0x%llx)",
                                     (void *)scan, img, (unsigned long long)slide);
                            breadcrumb(bc);

                            uint64_t *hookslots = &scan[2]; // [0..3]
                            uint64_t *origVAs   = &scan[6]; // [0..3]

                            void *hooks[] = {
                                (void *)hook_OnSpinResultReceived,
                                (void *)hook_SetFreezeResolve,
                                (void *)hook_activateWinSequence,
                                (void *)hook_ContainsAccumulationResult
                            };

                            int count = 0;
                            for (int i = 0; i < 4; i++) {
                                uint64_t origVA = origVAs[i];
                                if (!origVA) continue;
                                s_origFn[i] = (void *)(origVA + slide);
                                hookslots[i] = (uint64_t)hooks[i];
                                count++;
                                snprintf(bc, sizeof bc,
                                         "HOOKSLOT[%d]: hook=%p orig=%p",
                                         i, hooks[i], s_origFn[i]);
                                breadcrumb(bc);
                            }
                            return count;
                        }
                    }
                }
            }
            p += lc->cmdsize;
        }
    }
    breadcrumb("HOOKSLOT: magic marker not found (binary not patched)");
    return 0;
}

// ---------------------------------------------------------------------------
//  MODE 4 — DISCOVERY (for offline patcher).
// ---------------------------------------------------------------------------
static void dumpDiscovery(void *klassMgr) {
    NSString *docs = NSSearchPathForDirectoriesInDomains(
        NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
    NSString *path = [docs stringByAppendingPathComponent:@"hook_discovery.txt"];
    FILE *df = fopen(path.fileSystemRepresentation, "w");
    if (!df) { breadcrumb("DISCOVERY: cannot open file"); return; }

    const char *names[] = {"OnSpinResultReceived", "SetFreezeResolve",
                           "activateWinSequence", "ContainsAccumulationResult"};
    int argcs[] = {1, 0, 1, 1};

    void *testM  = findMethod(klassMgr, "activateWinSequence", 1);
    void *testFp = testM ? methodNativePointer(testM) : NULL;
    if (!testFp) { breadcrumb("DISCOVERY: cannot find test method"); fclose(df); return; }
    uintptr_t testAddr = (uintptr_t)testFp;

    int targetImg = -1;
    intptr_t slide = 0;
    const struct mach_header_64 *header = NULL;
    const char *imagePath = NULL;

    for (uint32_t i = 0; i < _dyld_image_count(); i++) {
        const struct mach_header_64 *h =
            (const struct mach_header_64 *)_dyld_get_image_header(i);
        if (!h || h->magic != MH_MAGIC_64) continue;
        intptr_t s = _dyld_get_image_vmaddr_slide(i);

        const uint8_t *lcp = (const uint8_t *)(h + 1);
        for (uint32_t j = 0; j < h->ncmds; j++) {
            const struct load_command *lc = (const struct load_command *)lcp;
            if (lc->cmd == LC_SEGMENT_64) {
                const struct segment_command_64 *seg =
                    (const struct segment_command_64 *)lcp;
                uintptr_t sStart = seg->vmaddr + s;
                if (testAddr >= sStart && testAddr < sStart + seg->vmsize) {
                    targetImg  = (int)i;
                    slide      = s;
                    header     = h;
                    imagePath  = _dyld_get_image_name(i);
                    goto disc_found;
                }
            }
            lcp += lc->cmdsize;
        }
    }
disc_found:
    if (targetImg < 0) { breadcrumb("DISCOVERY: cannot find image"); fclose(df); return; }

    fprintf(df, "# SpinLogger Hook Discovery v1\n");
    fprintf(df, "IMAGE_PATH=%s\n", imagePath ? imagePath : "unknown");
    fprintf(df, "IMAGE_IDX=%d\n", targetImg);
    fprintf(df, "ASLR_SLIDE=0x%llx\n", (unsigned long long)slide);

    const uint8_t *lcp = (const uint8_t *)(header + 1);
    for (uint32_t j = 0; j < header->ncmds; j++) {
        const struct load_command *lc = (const struct load_command *)lcp;
        if (lc->cmd == LC_SEGMENT_64) {
            const struct segment_command_64 *seg =
                (const struct segment_command_64 *)lcp;
            fprintf(df, "SEG %.16s VMADDR=0x%llx VMSIZE=0x%llx FILEOFF=0x%llx FILESIZE=0x%llx\n",
                    seg->segname, seg->vmaddr, seg->vmsize, seg->fileoff, seg->filesize);
        }
        lcp += lc->cmdsize;
    }

    for (int i = 0; i < 4; i++) {
        void *m = findMethod(klassMgr, names[i], argcs[i]);
        if (!m) { fprintf(df, "METHOD %s NOTFOUND\n", names[i]); continue; }
        void *fnp = methodNativePointer(m);
        if (!fnp) { fprintf(df, "METHOD %s NOFP\n", names[i]); continue; }

        uintptr_t va = (uintptr_t)fnp;
        uintptr_t unslidVA = va - (uintptr_t)slide;

        uint8_t bytes[32];
        memcpy(bytes, fnp, 32);

        fprintf(df, "METHOD %s ARGC=%d VA=0x%llx UNSLID=0x%llx BYTES=",
                names[i], argcs[i],
                (unsigned long long)va, (unsigned long long)unslidVA);
        for (int b = 0; b < 32; b++) fprintf(df, "%02x", bytes[b]);
        fprintf(df, "\n");
    }

    fclose(df);
    breadcrumb("DISCOVERY: written to hook_discovery.txt");
}

// ---------------------------------------------------------------------------
//  Config.
// ---------------------------------------------------------------------------
static bool s_diagMode = false;

static void loadHookConfig(void) {
    NSString *docs = NSSearchPathForDirectoriesInDomains(
        NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
    NSString *path = [docs stringByAppendingPathComponent:@"hook_config.txt"];
    FILE *f = fopen(path.fileSystemRepresentation, "r");
    if (!f) return; // default: auto (ElleKit -> HOOKSLOT)

    char line[128];
    while (fgets(line, sizeof line, f)) {
        size_t len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) line[--len] = 0;
        if (len == 0) continue;
        if (strcmp(line, "DIAG") == 0) { s_diagMode = true; break; }
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

    breadcrumb("STEP 5: scanning loaded images for hook frameworks");
    logLoadedHookImages();

    // Mode 4: discovery only (forced by hook_config.txt).
    if (s_diagMode) {
        breadcrumb("=== DISCOVERY MODE ===");
        dumpDiscovery(klassMgr);
        logLine("INSTALL_END", "", "", "0", "discovery");
        breadcrumb("DONE: 0/4 installed (DISCOVERY)");
        return 0;
    }

    // Mode 1: ElleKit (if user installed it in LC).
    breadcrumb("STEP 6: trying ElleKit MSHookFunction");
    int n = installViaElleKit(klassMgr);
    if (n > 0) {
        breadcrumb("=== ELLEKIT MODE ===");
        char bc[64];
        snprintf(bc, sizeof bc, "ELLEKIT: %d/4 hooks active", n);
        breadcrumb(bc);
        s_installed = YES;
        snprintf(bc, sizeof bc, "%d", n);
        logLine("INSTALL_END", "", "", bc, "ellekit");
        return n;
    }

    // Mode 2: Dobby (statically linked — always available if compiled in).
#ifdef SPINHOOK_HAS_DOBBY
    breadcrumb("STEP 7: ElleKit unavailable — trying Dobby (static)");
    n = installViaDobby(klassMgr);
    if (n > 0) {
        breadcrumb("=== DOBBY MODE ===");
        char bc[64];
        snprintf(bc, sizeof bc, "DOBBY: %d/4 hooks active", n);
        breadcrumb(bc);
        s_installed = YES;
        snprintf(bc, sizeof bc, "%d", n);
        logLine("INSTALL_END", "", "", bc, "dobby");
        return n;
    }
#else
    breadcrumb("STEP 7: SPINHOOK_HAS_DOBBY not defined at compile time");
#endif

    // Mode 3: HOOKSLOT last resort (pre-patched binary).
    breadcrumb("STEP 8: trying HOOKSLOT (pre-patched binary)");
    n = installViaHookslots();
    if (n > 0) {
        breadcrumb("=== HOOKSLOT MODE ===");
        char bc[64];
        snprintf(bc, sizeof bc, "HOOKSLOT: %d/4 hooks active", n);
        breadcrumb(bc);
        s_installed = YES;
        snprintf(bc, sizeof bc, "%d", n);
        logLine("INSTALL_END", "", "", bc, "hookslot");
        return n;
    }

    breadcrumb("NO HOOKS INSTALLED — check build.yml linked Dobby correctly");
    logLine("INSTALL_END", "", "", "0", "none");
    return 0;
}
