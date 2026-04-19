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

// ---------------------------------------------------------------------------
//  SLSpinHook — hook installation for LiveContainer.
//
//  LC runs guest apps under iOS CS_HARD | CS_KILL enforcement, which SIGKILLs
//  the process if any __TEXT page is dirtied. Runtime inline hookers that use
//  vm_remap/vm_protect (Dobby, raw mprotect patchers) trip this and get us
//  killed — even when the hook itself reports failure, because the page-state
//  damage is already done.
//
//  The only survivable paths inside LC are:
//    1. ELLEKIT (MSHookFunction) — ships inside LC's bundle as
//       Frameworks/CydiaSubstrate.framework/CydiaSubstrate. Uses a BRK+Mach
//       exception-port trick for far branches, so CS_KILL doesn't fire.
//       LC's TweakLoader dlopens it with RTLD_GLOBAL before loading tweaks.
//    2. HOOKSLOT — pre-patched binary: offline patcher writes B-trampolines
//       into the target prologues before signing, so the running image never
//       dirties a page. Kept as a last-resort fallback for the v69 workflow.
//    3. DIAG — discovery-only; writes hook_discovery.txt for the offline
//       patcher. Set `DIAG` in Documents/hook_config.txt to force this mode.
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
//  LC's TweakLoader dlopens CydiaSubstrate.framework (which is ElleKit
//  behind a canonical Substrate name) with RTLD_LAZY | RTLD_GLOBAL before
//  loading any tweak dylibs. When tweaks are loaded via LC's Tweaks folder,
//  MSHookFunction is already in RTLD_DEFAULT scope by the time our install
//  runs.
//
//  Defensive: if we get loaded via direct LC_LOAD_DYLIB injection in the
//  guest's main binary instead of through LC's Tweaks folder, TweakLoader's
//  constructor may not have fired yet. We explicitly dlopen CydiaSubstrate
//  ourselves from the known LC path before resolving MSHookFunction. This
//  way both deployment modes work.
// ---------------------------------------------------------------------------
typedef void  (*fn_MSHookFunction)(void *target, void *replacement, void **orig);
typedef void *(*fn_EKHookFunction)(void *target, void *replacement, bool skipChecks);
typedef void  (*fn_MSHookMemory)(void *target, const uint8_t *code, uint64_t size);

static void forceLoadCydiaSubstrate(void) {
    // Try the most likely paths ElleKit lives at, in order of plausibility.
    // LC ships CydiaSubstrate.framework inside the LC app bundle; for guests
    // running in-process the framework is mapped through rpath.
    const char *candidates[] = {
        "@rpath/CydiaSubstrate.framework/CydiaSubstrate",
        "@executable_path/Frameworks/CydiaSubstrate.framework/CydiaSubstrate",
        "@loader_path/../Frameworks/CydiaSubstrate.framework/CydiaSubstrate",
        "/Library/Frameworks/CydiaSubstrate.framework/CydiaSubstrate",
        NULL
    };
    for (int i = 0; candidates[i]; i++) {
        void *h = dlopen(candidates[i], RTLD_LAZY | RTLD_GLOBAL);
        if (h) {
            char bc[256];
            snprintf(bc, sizeof bc, "ELLEKIT: dlopen ok %s", candidates[i]);
            breadcrumb(bc);
            return;
        }
    }

    // Last resort: walk already-loaded images and dlopen the CydiaSubstrate
    // binary directly by its loaded path.
    uint32_t n = _dyld_image_count();
    for (uint32_t i = 0; i < n; i++) {
        const char *name = _dyld_get_image_name(i);
        if (name && strstr(name, "CydiaSubstrate")) {
            void *h = dlopen(name, RTLD_LAZY | RTLD_GLOBAL);
            if (h) {
                char bc[384];
                snprintf(bc, sizeof bc, "ELLEKIT: dlopen ok (scan) %s", name);
                breadcrumb(bc);
            }
            return;
        }
    }
    breadcrumb("ELLEKIT: CydiaSubstrate not dlopen-able via any candidate path");
}

static fn_MSHookFunction resolveMSHookFunction(void) {
    fn_MSHookFunction fn = (fn_MSHookFunction)dlsym(RTLD_DEFAULT, "MSHookFunction");
    if (fn) return fn;

    // Not resolved — force-load ElleKit ourselves and retry.
    forceLoadCydiaSubstrate();
    fn = (fn_MSHookFunction)dlsym(RTLD_DEFAULT, "MSHookFunction");
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

// Two-pass installer. iOS 26 CS_HARD causes ElleKit's rawHook to fail the
// restore-to-RX vm_protect on the FIRST modification of any __TEXT page,
// which makes MSHookFunction return orig=NULL even though the patch bytes
// committed. The failed restore leaves the page in RW state, so any
// subsequent hook on that same page succeeds because ElleKit skips both
// vm_protect calls (info.protection already shows RW).
//
// Pass 1: snapshot 16 bytes of each target's prologue, then call
//         MSHookFunction as usual. Orig is recorded; pages get warmed.
// Pass 2: for targets where pass 1 returned orig=NULL, restore the saved
//         bytes via MSHookMemory (which handles any residual protection
//         quirks) and re-hook with EKHookFunction(..., skipChecks=true).
//         skipChecks bypasses ElleKit's hooks[target] dedup (which would
//         otherwise recurse into hook(replacement, replacement)) and also
//         bypasses the always-disabled Trampoline path.
static int installViaElleKit(void *klassMgr) {
    fn_MSHookFunction mshook = resolveMSHookFunction();
    if (!mshook) {
        breadcrumb("ELLEKIT: MSHookFunction not resolvable via dlsym");
        return 0;
    }
    breadcrumb("ELLEKIT: MSHookFunction resolved");

    fn_EKHookFunction ekhook =
        (fn_EKHookFunction)dlsym(RTLD_DEFAULT, "EKHookFunction");
    fn_MSHookMemory   mshookmem =
        (fn_MSHookMemory)  dlsym(RTLD_DEFAULT, "MSHookMemory");
    if (ekhook && mshookmem) {
        breadcrumb("ELLEKIT: EKHookFunction + MSHookMemory resolved (two-pass available)");
    } else {
        breadcrumb("ELLEKIT: EKHook/MSHookMemory not resolvable (single-pass only)");
    }

    struct TargetInfo {
        const char *name;
        int         argc;
        int         idx;
        void       *replacement;
        void       *fp;
        uint8_t     saved[16];
        bool        attempted;
    };
    struct TargetInfo targets[] = {
        {"OnSpinResultReceived",        1, 0, (void *)hook_OnSpinResultReceived,        NULL, {0}, false},
        {"SetFreezeResolve",            0, 1, (void *)hook_SetFreezeResolve,            NULL, {0}, false},
        {"activateWinSequence",         1, 2, (void *)hook_activateWinSequence,         NULL, {0}, false},
        {"ContainsAccumulationResult",  1, 3, (void *)hook_ContainsAccumulationResult,  NULL, {0}, false},
    };

    // Resolve methods + snapshot prologue bytes BEFORE any patching.
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
        targets[i].fp = fp;
        memcpy(targets[i].saved, fp, sizeof targets[i].saved);
    }

    // Pass 1: MSHookFunction on each resolved target.
    for (int i = 0; i < 4; i++) {
        if (!targets[i].fp) continue;

        char bc[256];
        snprintf(bc, sizeof bc, "ELLEKIT[p1]: hooking %s at %p",
                 targets[i].name, targets[i].fp);
        breadcrumb(bc);

        // Prologue dump — useful if hooks still fail after two-pass.
        {
            uint32_t w[8];
            memcpy(w, targets[i].fp, sizeof w);
            char hex[8 * 9 + 1];
            int off = 0;
            for (int k = 0; k < 8; k++) {
                off += snprintf(hex + off, sizeof(hex) - off, "%08x ", w[k]);
            }
            snprintf(bc, sizeof bc, "ELLEKIT[p1]: %s prologue=%s",
                     targets[i].name, hex);
            breadcrumb(bc);
        }

        void *orig = NULL;
        mshook(targets[i].fp, targets[i].replacement, &orig);
        targets[i].attempted = true;
        s_origFn[targets[i].idx] = orig;

        if (orig) {
            snprintf(bc, sizeof bc, "ELLEKIT[p1]: %s hooked, orig=%p",
                     targets[i].name, orig);
            breadcrumb(bc);

            char fpStr[24], origStr[24];
            snprintf(fpStr, sizeof fpStr, "%p", targets[i].fp);
            snprintf(origStr, sizeof origStr, "%p", orig);
            logLine(targets[i].name, fpStr, origStr, "", "hooked-ellekit-p1");
        } else {
            snprintf(bc, sizeof bc, "ELLEKIT[p1]: %s FAILED (orig=NULL) — will retry",
                     targets[i].name);
            breadcrumb(bc);
        }
    }

    // Pass 2: for any target still without an orig, restore original bytes
    // and re-hook via EKHookFunction(..., skipChecks=true).
    if (ekhook && mshookmem) {
        for (int i = 0; i < 4; i++) {
            if (!targets[i].attempted) continue;
            if (s_origFn[targets[i].idx]) continue;

            char bc[256];
            snprintf(bc, sizeof bc, "ELLEKIT[p2]: restoring %s bytes at %p",
                     targets[i].name, targets[i].fp);
            breadcrumb(bc);

            // Restore the original prologue so EKHookFunction's getOriginal
            // reads clean bytes into its new orig trampoline. MSHookMemory
            // handles page protection if needed; after a pass-1 failure the
            // page is already RW so it reduces to a plain memcpy+icache.
            mshookmem(targets[i].fp, targets[i].saved, (uint64_t)sizeof targets[i].saved);

            void *orig = ekhook(targets[i].fp, targets[i].replacement, true);
            s_origFn[targets[i].idx] = orig;

            if (orig) {
                snprintf(bc, sizeof bc, "ELLEKIT[p2]: %s hooked, orig=%p",
                         targets[i].name, orig);
                breadcrumb(bc);

                char fpStr[24], origStr[24];
                snprintf(fpStr, sizeof fpStr, "%p", targets[i].fp);
                snprintf(origStr, sizeof origStr, "%p", orig);
                logLine(targets[i].name, fpStr, origStr, "", "hooked-ellekit-p2");
            } else {
                snprintf(bc, sizeof bc, "ELLEKIT[p2]: %s STILL FAILED (orig=NULL)",
                         targets[i].name);
                breadcrumb(bc);
            }
        }
    }

    int installed = 0;
    for (int i = 0; i < 4; i++) {
        if (s_origFn[targets[i].idx]) installed++;
    }
    return installed;
}

// ---------------------------------------------------------------------------
//  MODE 2 — HOOKSLOT (pre-patched binary via offline_patcher.py).
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
    if (!f) return; // default: auto (ElleKit -> HOOKSLOT fallback)

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

    breadcrumb("STEP 0: entry (v83-nohook-diag)");

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

    // v83 diagnostic: skip all __TEXT patching. Dylib loads, IL2CPP resolves,
    // log opens, but no MSHookFunction / vm_protect calls are issued. If the
    // game still crashes at UnityFramework+0x2e72130, our hook installation is
    // innocent and the fault lies elsewhere (LC+iOS26+Unity). If it runs
    // cleanly, __TEXT patching is the culprit and we need MethodInfo swap.
    breadcrumb("=== V83 NO-HOOK DIAGNOSTIC: skipping all installers ===");
    logLine("INSTALL_END", "", "", "0", "v83-nohook-diag");
    s_installed = YES;
    return 0;

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

    // Mode 2: HOOKSLOT last resort (pre-patched binary).
    breadcrumb("STEP 7: trying HOOKSLOT (pre-patched binary)");
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

    breadcrumb("NO HOOKS INSTALLED — import SpinLogger.dylib via LC Tweaks tab so ElleKit is resolvable");
    logLine("INSTALL_END", "", "", "0", "none");
    return 0;
}
