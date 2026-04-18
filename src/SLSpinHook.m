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
#include <sys/sysctl.h>
#include <mach-o/dyld.h>
#include <mach-o/loader.h>

// csops syscall for checking code-signing status.
#define CS_OPS_STATUS       0
#define CS_VALID            0x00000001
#define CS_HARD             0x00000100
#define CS_KILL             0x00000200
#define CS_ENFORCEMENT      0x00001000
#define CS_REQUIRE_LV       0x00002000
#define CS_RUNTIME          0x00010000
#define CS_DEBUGGED          0x10000000

extern int csops(pid_t pid, unsigned int ops, void *useraddr, size_t usersize);

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
//  DIAGNOSTIC: test each primitive operation in isolation.
//
//  This runs INSTEAD of actual hooking. It probes exactly which low-level
//  operation kills the process, logging a breadcrumb before and after each
//  step. The last breadcrumb written tells us which step crashed.
//
//  Tests (on ONE target only — activateWinSequence):
//   D1: read original bytes (should never crash)
//   D2: query vm_region for current page protection
//   D3: vm_protect → RWX (just change perms, don't write)
//   D4: memcpy 1 byte (identical byte — write same value back)
//   D5: vm_protect → RX (restore perms)
//   D6: sys_icache_invalidate
//   D7: vm_protect → RWX + memcpy actual patch byte + vm_protect → RX
//   D8: read back to verify write stuck
//   D9: restore original byte
//   D10: vm_write (kernel copy, no permission change)
//   D11: vm_write actual patch byte
//   D12: restore via vm_write
//
//  If we get past all of these, the modification itself doesn't crash.
//  The crash would be when the modified code is *executed* (code-sign check).
// ---------------------------------------------------------------------------

static void diagQueryProtection(vm_address_t addr) {
    vm_address_t region_addr = addr;
    vm_size_t region_size = 0;
    vm_region_basic_info_data_64_t info;
    mach_msg_type_number_t count = VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t obj_name;

    kern_return_t kr = vm_region_64(mach_task_self(),
                                    &region_addr, &region_size,
                                    VM_REGION_BASIC_INFO_64,
                                    (vm_region_info_t)&info, &count,
                                    &obj_name);
    char bc[256];
    if (kr == KERN_SUCCESS) {
        snprintf(bc, sizeof bc,
                 "D2: vm_region kr=0 prot=%d max_prot=%d shared=%d addr=0x%llx size=0x%llx",
                 info.protection, info.max_protection, info.shared,
                 (unsigned long long)region_addr, (unsigned long long)region_size);
    } else {
        snprintf(bc, sizeof bc, "D2: vm_region kr=%d", (int)kr);
    }
    breadcrumb(bc);
}

static void diagCheckCSFlags(void) {
    uint32_t flags = 0;
    int rc = csops(getpid(), CS_OPS_STATUS, &flags, sizeof(flags));
    char bc[256];
    snprintf(bc, sizeof bc,
             "DIAG CS_FLAGS: rc=%d flags=0x%08x "
             "VALID=%d HARD=%d KILL=%d ENFORCE=%d REQUIRE_LV=%d RUNTIME=%d DEBUGGED=%d",
             rc, flags,
             !!(flags & CS_VALID),
             !!(flags & CS_HARD),
             !!(flags & CS_KILL),
             !!(flags & CS_ENFORCEMENT),
             !!(flags & CS_REQUIRE_LV),
             !!(flags & CS_RUNTIME),
             !!(flags & CS_DEBUGGED));
    breadcrumb(bc);
}

static void runDiagnostics(void *target, const char *name) {
    char bc[256];
    const vm_address_t PAGE_MASK = 0x3FFF;
    vm_address_t pageStart = (vm_address_t)target & ~PAGE_MASK;
    vm_size_t pageSpan = ((((vm_address_t)target + 16) - pageStart) + PAGE_MASK) & ~PAGE_MASK;

    // -- D1: read original bytes --
    uint8_t orig[16];
    memcpy(orig, target, 16);
    snprintf(bc, sizeof bc,
             "D1: read 16 bytes at %p = %02x %02x %02x %02x %02x %02x %02x %02x "
             "%02x %02x %02x %02x %02x %02x %02x %02x",
             target,
             orig[0], orig[1], orig[2],  orig[3],  orig[4],  orig[5],  orig[6],  orig[7],
             orig[8], orig[9], orig[10], orig[11], orig[12], orig[13], orig[14], orig[15]);
    breadcrumb(bc);

    // -- D2: query vm_region --
    breadcrumb("D2: querying vm_region...");
    diagQueryProtection((vm_address_t)target);

    // -- D3: vm_protect → RWX (no write yet) --
    breadcrumb("D3: vm_protect RWX (no write)...");
    kern_return_t kr = vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
                                  VM_PROT_READ | VM_PROT_WRITE | VM_PROT_EXECUTE);
    snprintf(bc, sizeof bc, "D3: vm_protect RWX kr=%d page=0x%llx span=0x%llx",
             (int)kr, (unsigned long long)pageStart, (unsigned long long)pageSpan);
    breadcrumb(bc);

    // -- D3b: query protection again after RWX --
    breadcrumb("D3b: re-query vm_region after RWX...");
    diagQueryProtection((vm_address_t)target);

    // -- D4: memcpy same byte (no-op write) --
    if (kr == KERN_SUCCESS) {
        breadcrumb("D4: memcpy same byte (no-op)...");
        uint8_t same = orig[0];
        memcpy(target, &same, 1);
        breadcrumb("D4: memcpy done (survived)");
    } else {
        breadcrumb("D4: SKIPPED (vm_protect failed)");
    }

    // -- D5: vm_protect → RX (restore) --
    breadcrumb("D5: vm_protect RX (restore)...");
    kr = vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
                    VM_PROT_READ | VM_PROT_EXECUTE);
    snprintf(bc, sizeof bc, "D5: vm_protect RX kr=%d", (int)kr);
    breadcrumb(bc);

    // -- D6: sys_icache_invalidate --
    breadcrumb("D6: sys_icache_invalidate...");
    sys_icache_invalidate(target, 16);
    breadcrumb("D6: icache invalidated (survived)");

    // -- D7: RWX + write actual different byte + RX --
    breadcrumb("D7: vm_protect RWX + write diff byte...");
    kr = vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
                    VM_PROT_READ | VM_PROT_WRITE | VM_PROT_EXECUTE);
    snprintf(bc, sizeof bc, "D7a: vm_protect RWX kr=%d", (int)kr);
    breadcrumb(bc);
    if (kr == KERN_SUCCESS) {
        // NOP = 0xD503201F. Write a NOP over first instruction.
        uint32_t nop = 0xD503201F;
        breadcrumb("D7b: memcpy NOP over first insn...");
        memcpy(target, &nop, 4);
        breadcrumb("D7b: memcpy done (survived)");

        breadcrumb("D7c: vm_protect RX...");
        vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
                   VM_PROT_READ | VM_PROT_EXECUTE);
        breadcrumb("D7c: perms restored (survived)");

        breadcrumb("D7d: icache invalidate...");
        sys_icache_invalidate(target, 4);
        breadcrumb("D7d: icache done (survived)");
    } else {
        breadcrumb("D7: SKIPPED (RWX failed)");
    }

    // -- D8: read back --
    breadcrumb("D8: reading back modified bytes...");
    uint8_t check[4];
    memcpy(check, target, 4);
    snprintf(bc, sizeof bc, "D8: readback = %02x %02x %02x %02x (expect 1f 20 03 d5 for NOP)",
             check[0], check[1], check[2], check[3]);
    breadcrumb(bc);

    // -- D9: restore original bytes via RWX + memcpy --
    breadcrumb("D9: restoring original bytes...");
    kr = vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
                    VM_PROT_READ | VM_PROT_WRITE | VM_PROT_EXECUTE);
    if (kr == KERN_SUCCESS) {
        memcpy(target, orig, 16);
        vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
                   VM_PROT_READ | VM_PROT_EXECUTE);
        sys_icache_invalidate(target, 16);
        breadcrumb("D9: original restored (survived)");
    } else {
        snprintf(bc, sizeof bc, "D9: vm_protect kr=%d CANNOT RESTORE", (int)kr);
        breadcrumb(bc);
    }

    // -- D10: vm_write same bytes (kernel copy, no perm change) --
    breadcrumb("D10: vm_write same bytes...");
    kr = vm_write(mach_task_self(), (vm_address_t)target,
                  (vm_offset_t)orig, 16);
    snprintf(bc, sizeof bc, "D10: vm_write same kr=%d", (int)kr);
    breadcrumb(bc);

    // -- D11: vm_write NOP (different byte, no perm change) --
    breadcrumb("D11: vm_write NOP...");
    uint8_t nopBytes[16];
    memcpy(nopBytes, orig, 16);
    uint32_t nop2 = 0xD503201F;
    memcpy(nopBytes, &nop2, 4);
    kr = vm_write(mach_task_self(), (vm_address_t)target,
                  (vm_offset_t)nopBytes, 16);
    snprintf(bc, sizeof bc, "D11: vm_write NOP kr=%d", (int)kr);
    breadcrumb(bc);
    if (kr == KERN_SUCCESS) {
        breadcrumb("D11b: icache invalidate...");
        sys_icache_invalidate(target, 16);
        breadcrumb("D11b: done (survived)");
    }

    // -- D12: restore via vm_write --
    breadcrumb("D12: vm_write restore original...");
    kr = vm_write(mach_task_self(), (vm_address_t)target,
                  (vm_offset_t)orig, 16);
    snprintf(bc, sizeof bc, "D12: vm_write restore kr=%d", (int)kr);
    breadcrumb(bc);
    if (kr == KERN_SUCCESS) {
        sys_icache_invalidate(target, 16);
    }

    breadcrumb("DIAG COMPLETE — all steps survived");
}

// ---------------------------------------------------------------------------
//  Hot-patch inline hook — NO trampoline needed.
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

// Write bytes to a code page using vm_write.
static kern_return_t vmWrite(vm_address_t target, const void *data, size_t n) {
    return vm_write(mach_task_self(), target,
                    (vm_offset_t)data, (mach_msg_type_number_t)n);
}

static void patchBytes(void *target, const void *bytes, size_t n,
                       vm_address_t pageStart, vm_size_t pageSpan) {
    kern_return_t kr = vmWrite((vm_address_t)target, bytes, n);
    if (kr != KERN_SUCCESS) {
        vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
                   VM_PROT_READ | VM_PROT_WRITE | VM_PROT_EXECUTE);
        memcpy(target, bytes, n);
        vm_protect(mach_task_self(), pageStart, pageSpan, FALSE,
                   VM_PROT_READ | VM_PROT_EXECUTE);
    }
    sys_icache_invalidate(target, n);
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
    memcpy(h->saved, target, PATCH_SIZE);
    buildAbsJump(h->stub, (uint64_t)replacement);

    const vm_address_t PAGE_MASK = 0x3FFF;
    h->pageStart = (vm_address_t)target & ~PAGE_MASK;
    h->pageSpan  = (((vm_address_t)target + PATCH_SIZE) - h->pageStart
                     + PAGE_MASK) & ~PAGE_MASK;

    kern_return_t kr = vmWrite((vm_address_t)target, h->stub, PATCH_SIZE);
    {
        char bc[128];
        snprintf(bc, sizeof bc, "VMWRITE %s kr=%d", name, (int)kr);
        breadcrumb(bc);
    }

    if (kr != KERN_SUCCESS) {
        kr = vm_protect(mach_task_self(),
                        h->pageStart, h->pageSpan, FALSE,
                        VM_PROT_READ | VM_PROT_WRITE | VM_PROT_EXECUTE);
        if (kr != KERN_SUCCESS) {
            kr = vm_protect(mach_task_self(),
                            h->pageStart, h->pageSpan, FALSE,
                            VM_PROT_READ | VM_PROT_WRITE | VM_PROT_EXECUTE
                            | VM_PROT_COPY);
        }
        {
            char bc2[128];
            snprintf(bc2, sizeof bc2, "VMPROTECT_RWX %s kr=%d", name, (int)kr);
            breadcrumb(bc2);
        }
        if (kr != KERN_SUCCESS) return -3;

        memcpy(target, h->stub, PATCH_SIZE);

        vm_protect(mach_task_self(), h->pageStart, h->pageSpan, FALSE,
                   VM_PROT_READ | VM_PROT_EXECUTE);
    }
    sys_icache_invalidate(target, PATCH_SIZE);

    h->active = true;
    s_hookCount++;

    char bc[128];
    snprintf(bc, sizeof bc, "PATCHED %s idx=%d", name, idx);
    breadcrumb(bc);
    return idx;
}

// ---------------------------------------------------------------------------
//  Hook targets — supports both inline-patch and hookslot modes.
// ---------------------------------------------------------------------------
static void *fp_OnSpinResultReceived       = NULL;
static void *fp_SetFreezeResolve           = NULL;
static void *fp_activateWinSequence        = NULL;
static void *fp_ContainsAccumulationResult = NULL;

static int idx_OnSpinResultReceived       = -1;
static int idx_SetFreezeResolve           = -1;
static int idx_activateWinSequence        = -1;
static int idx_ContainsAccumulationResult = -1;

// Hookslot mode: original function callable stubs (set by installViaHookslots).
// When non-NULL, hooks call original through these instead of unpatch/repatch.
static void *s_origFn[4] = {NULL, NULL, NULL, NULL};

// ---------------------------------------------------------------------------
//  Hook bodies.
//  Supports two call-original modes:
//    1. s_origFn[N] != NULL → hookslot mode, call orig stub directly
//    2. s_origFn[N] == NULL → inline-patch mode, unpatch/call/repatch
// ---------------------------------------------------------------------------

static void hook_OnSpinResultReceived(void *self, void *response, void *methodInfo) {
    typedef void (*fn_t)(void *, void *, void *);
    char a1[24], a2[24];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%p", response);
    logLine("OnSpinResultReceived", a1, a2, "", "enter");

    if (s_origFn[0]) {
        ((fn_t)s_origFn[0])(self, response, methodInfo);
    } else {
        pthread_mutex_lock(&s_patchMu);
        unpatch(idx_OnSpinResultReceived);
        ((fn_t)fp_OnSpinResultReceived)(self, response, methodInfo);
        repatch(idx_OnSpinResultReceived);
        pthread_mutex_unlock(&s_patchMu);
    }

    logLine("OnSpinResultReceived", a1, a2, "", "exit");
}

static void hook_SetFreezeResolve(void *self, void *methodInfo) {
    typedef void (*fn_t)(void *, void *);
    char a1[24]; snprintf(a1, sizeof a1, "%p", self);
    logLine("SetFreezeResolve", a1, "", "", "enter");

    if (s_origFn[1]) {
        ((fn_t)s_origFn[1])(self, methodInfo);
    } else {
        pthread_mutex_lock(&s_patchMu);
        unpatch(idx_SetFreezeResolve);
        ((fn_t)fp_SetFreezeResolve)(self, methodInfo);
        repatch(idx_SetFreezeResolve);
        pthread_mutex_unlock(&s_patchMu);
    }

    logLine("SetFreezeResolve", a1, "", "", "exit");
}

static void hook_activateWinSequence(void *self, void *slotResult, void *methodInfo) {
    typedef void (*fn_t)(void *, void *, void *);
    char a1[24], a2[24];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%p", slotResult);
    logLine("activateWinSequence", a1, a2, "", "enter");

    if (s_origFn[2]) {
        ((fn_t)s_origFn[2])(self, slotResult, methodInfo);
    } else {
        pthread_mutex_lock(&s_patchMu);
        unpatch(idx_activateWinSequence);
        ((fn_t)fp_activateWinSequence)(self, slotResult, methodInfo);
        repatch(idx_activateWinSequence);
        pthread_mutex_unlock(&s_patchMu);
    }

    // Field reading disabled for hookslot safety validation.
    // TODO: re-enable once hooks are confirmed stable.
    logLine("activateWinSequence", a1, a2, "", "exit");
}

static int32_t hook_ContainsAccumulationResult(void *self, int32_t defaultIcon, void *methodInfo) {
    typedef int32_t (*fn_t)(void *, int32_t, void *);
    char a1[24], a2[16];
    snprintf(a1, sizeof a1, "%p", self);
    snprintf(a2, sizeof a2, "%d", defaultIcon);
    logLine("ContainsAccumulationResult", a1, a2, "", "enter");

    int32_t ret;
    if (s_origFn[3]) {
        ret = ((fn_t)s_origFn[3])(self, defaultIcon, methodInfo);
    } else {
        pthread_mutex_lock(&s_patchMu);
        unpatch(idx_ContainsAccumulationResult);
        ret = ((fn_t)fp_ContainsAccumulationResult)(self, defaultIcon, methodInfo);
        repatch(idx_ContainsAccumulationResult);
        pthread_mutex_unlock(&s_patchMu);
    }

    char r[16]; snprintf(r, sizeof r, "%d", ret);
    logLine("ContainsAccumulationResult", a1, a2, r, "exit");
    return ret;
}

// ---------------------------------------------------------------------------
//  Hookslot scanning + installation.
//
//  After offline binary patching, the CoinMaster Mach-O contains:
//    - Function prologues redirected via B → trampoline
//    - Trampolines that load hook fn addr from __DATA hookslots
//    - Original callable stubs (saved insn + B back)
//    - A hookslot table in __DATA with magic marker:
//        [8B magic0] [8B magic1]
//        [8B hookslot_0..3]    ← dylib writes hook addrs here
//        [8B origVA_0..3]      ← patcher wrote orig stub unslid VAs
// ---------------------------------------------------------------------------
#define HOOKSLOT_MAGIC0 0xDEADBEEF5350494EULL
#define HOOKSLOT_MAGIC1 0x484F4F4B534C4F54ULL

static int installViaHookslots(void) {
    // Find the image that contains our hookslots (same image as IL2CPP code).
    // We look for the magic marker in every __DATA segment.
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
                            // Found it!
                            char bc[128];
                            snprintf(bc, sizeof bc,
                                     "HOOKSLOT: found magic at %p (img %d slide 0x%llx)",
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
//  Discovery dump — writes function addresses + binary info for the
//  offline patcher.
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

    // Find a target to determine which image contains IL2CPP code.
    void *testM = findMethod(klassMgr, "activateWinSequence", 1);
    void *testFp = testM ? methodNativePointer(testM) : NULL;
    if (!testFp) {
        breadcrumb("DISCOVERY: cannot find test method");
        fclose(df);
        return;
    }
    uintptr_t testAddr = (uintptr_t)testFp;

    // Find image containing this address.
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
                    targetImg = (int)i;
                    slide = s;
                    header = h;
                    imagePath = _dyld_get_image_name(i);
                    goto disc_found;
                }
            }
            lcp += lc->cmdsize;
        }
    }
disc_found:
    if (targetImg < 0) {
        breadcrumb("DISCOVERY: cannot find image");
        fclose(df);
        return;
    }

    fprintf(df, "# SpinLogger Hook Discovery v1\n");
    fprintf(df, "IMAGE_PATH=%s\n", imagePath ? imagePath : "unknown");
    fprintf(df, "IMAGE_IDX=%d\n", targetImg);
    fprintf(df, "ASLR_SLIDE=0x%llx\n", (unsigned long long)slide);

    // Dump segment info.
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

    // Dump each target method.
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
//  Hook config.
// ---------------------------------------------------------------------------
static bool s_hookEnabled[4] = { true, true, true, true };
static const char *s_hookNames[4] = {
    "OnSpinResultReceived",
    "SetFreezeResolve",
    "activateWinSequence",
    "ContainsAccumulationResult",
};

// Modes: DIAG = discovery only, HOOKSLOT = offline-patched binary, ALL/NONE/name = legacy.
static bool s_diagMode     = false;
static bool s_hookslotMode = false;

static void loadHookConfig(void) {
    NSString *docs = NSSearchPathForDirectoriesInDomains(
        NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
    NSString *path = [docs stringByAppendingPathComponent:@"hook_config.txt"];
    FILE *f = fopen(path.fileSystemRepresentation, "r");
    if (!f) {
        // No config file → default to DIAG (discovery) since runtime
        // patching is blocked by CS_KILL.
        s_diagMode = true;
        return;
    }
    for (int i = 0; i < 4; i++) s_hookEnabled[i] = false;

    char line[128];
    while (fgets(line, sizeof line, f)) {
        size_t len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) line[--len] = 0;
        if (len == 0) continue;
        if (strcmp(line, "DIAG") == 0) {
            s_diagMode = true;
            break;
        }
        if (strcmp(line, "HOOKSLOT") == 0) {
            s_hookslotMode = true;
            for (int i = 0; i < 4; i++) s_hookEnabled[i] = true;
            break;
        }
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

    // -- Check code-signing flags --
    breadcrumb("STEP 5: checking CS flags");
    diagCheckCSFlags();

    // ---------------------------------------------------------------
    //  AUTO-DETECT: try hookslot mode first (patched binary).
    //  If hookslot magic is found → use hookslots (no config needed).
    //  If not found → fall back to discovery or config-based mode.
    // ---------------------------------------------------------------
    breadcrumb("STEP 6: scanning for hookslot magic...");
    {
        int hsCount = installViaHookslots();
        if (hsCount > 0) {
            breadcrumb("=== HOOKSLOT MODE (auto-detected) ===");
            char bc[64];
            snprintf(bc, sizeof bc, "HOOKSLOT: %d/4 hooks activated", hsCount);
            breadcrumb(bc);
            s_installed = true;
            snprintf(bc, sizeof bc, "%d", hsCount);
            logLine("INSTALL_END", "", "", bc, "hookslot-auto");
            snprintf(bc, sizeof bc, "DONE: %d/4 installed (HOOKSLOT)", hsCount);
            breadcrumb(bc);
            return hsCount;
        }
        breadcrumb("STEP 6: no hookslot magic — not a patched binary");
    }

    // ---------------------------------------------------------------
    //  DISCOVERY MODE: dump function addresses + binary info for the
    //  offline patcher. No __TEXT modification.
    // ---------------------------------------------------------------
    if (s_diagMode) {
        breadcrumb("=== DISCOVERY MODE ===");
        dumpDiscovery(klassMgr);
        breadcrumb("=== DISCOVERY DONE — NO HOOKS INSTALLED ===");
        logLine("INSTALL_END", "", "", "0", "discovery");
        breadcrumb("DONE: 0/4 installed (DISCOVERY)");
        return 0;
    }

    // ---------------------------------------------------------------
    //  HOOKSLOT MODE (explicit config — but magic wasn't found).
    // ---------------------------------------------------------------
    if (s_hookslotMode) {
        breadcrumb("=== HOOKSLOT MODE (config) — but magic not found ===");
        logLine("INSTALL_END", "", "", "0", "hookslot-no-magic");
        breadcrumb("DONE: 0/4 installed (binary not patched)");
        return 0;
    }

    // ---------------------------------------------------------------
    //  NORMAL MODE: install hooks as before.
    // ---------------------------------------------------------------
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
