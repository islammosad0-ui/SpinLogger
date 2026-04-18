#import "SLInlineHook.h"
#include <mach/mach.h>
#include <mach/vm_map.h>
#include <libkern/OSCacheControl.h>
#include <sys/mman.h>
#include <stdint.h>
#include <string.h>

// ---------------------------------------------------------------------------
//  arm64 stub: absolute branch via scratch register.
//      LDR X17, [PC, #8]    58000051
//      BR  X17              d61f0220
//      .quad <absolute addr>
//  Total = 16 bytes (4 instructions + 8-byte literal).
// ---------------------------------------------------------------------------

#define STUB_BYTES 16

static void buildAbsoluteJump(uint8_t *dst, uint64_t absAddr) {
    // LDR X17, [PC, #8]  (little-endian encoding 0x58000051)
    dst[0] = 0x51; dst[1] = 0x00; dst[2] = 0x00; dst[3] = 0x58;
    // BR X17            (0xD61F0220)
    dst[4] = 0x20; dst[5] = 0x02; dst[6] = 0x1F; dst[7] = 0xD6;
    // 8-byte absolute target
    memcpy(dst + 8, &absAddr, 8);
}

// Reject any instruction whose semantics depend on PC — moving these into
// the trampoline would silently change their target.
static int isPCRelative(uint32_t insn) {
    // ADR / ADRP: bits [28:24] = 10000, differ only in bit 31
    if (((insn >> 24) & 0x1F) == 0x10) return 1;
    // B / BL (unconditional immediate): bits [30:26] = 00101
    uint32_t top6 = (insn >> 26) & 0x3F;
    if (top6 == 0x05 || top6 == 0x25) return 1;
    // CBZ / CBNZ: bits [30:25] = 011010
    if (((insn >> 25) & 0x3F) == 0x1A) return 1;
    // TBZ / TBNZ: bits [30:25] = 011011
    if (((insn >> 25) & 0x3F) == 0x1B) return 1;
    // B.cond: bits [31:24] = 01010100
    if (((insn >> 24) & 0xFF) == 0x54) return 1;
    // LDR (literal): bits [31:24] = 0x18 / 0x58 / 0x98
    uint32_t t = (insn >> 24) & 0xBF;
    if (t == 0x18) return 1;
    return 0;
}

// Allocate a page of executable memory for one trampoline. Uses mmap RWX.
// If RWX is denied (some hardened configs), falls back to RW + mprotect(RX).
static uint8_t *allocTrampoline(void) {
    const size_t sz = 4096;
    void *p = mmap(NULL, sz,
                   PROT_READ | PROT_WRITE | PROT_EXEC,
                   MAP_ANON | MAP_PRIVATE, -1, 0);
    if (p != MAP_FAILED) return (uint8_t *)p;

    p = mmap(NULL, sz,
             PROT_READ | PROT_WRITE,
             MAP_ANON | MAP_PRIVATE, -1, 0);
    if (p == MAP_FAILED) return NULL;
    // Caller must mprotect to RX after writing.
    return (uint8_t *)p;
}

// Make `n` bytes at `target` temporarily writable, invoke `writer`, restore RX,
// flush icache. Returns 0 on success.
static int patchTarget(void *target, const void *src, size_t n) {
    vm_address_t pageStart = (vm_address_t)target & ~(vm_address_t)0xFFF;
    vm_size_t    pageSpan  = (((vm_address_t)target + n) - pageStart + 0xFFF)
                             & ~(vm_size_t)0xFFF;

    kern_return_t kr = vm_protect(mach_task_self(),
                                  pageStart, pageSpan, FALSE,
                                  VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY);
    if (kr != KERN_SUCCESS) {
        NSLog(@"[SLInlineHook] vm_protect(RW+COPY) failed: kr=%d page=%p span=%zu",
              kr, (void *)pageStart, (size_t)pageSpan);
        return -1;
    }

    memcpy(target, src, n);

    kr = vm_protect(mach_task_self(),
                    pageStart, pageSpan, FALSE,
                    VM_PROT_READ | VM_PROT_EXECUTE);
    if (kr != KERN_SUCCESS) {
        NSLog(@"[SLInlineHook] vm_protect(RX) restore failed: kr=%d", kr);
        // Not fatal — target got patched, but page protections didn't restore.
    }

    sys_icache_invalidate(target, n);
    return 0;
}

int SLInlineHook_Install(void *target, void *replacement, void **outTrampoline) {
    if (!target || !replacement) return -1;

    // 1. Vet the first 4 instructions — any PC-relative op kills the trampoline.
    uint32_t *insns = (uint32_t *)target;
    for (int i = 0; i < 4; i++) {
        if (isPCRelative(insns[i])) {
            NSLog(@"[SLInlineHook] PC-relative insn at word %d of %p: 0x%08x",
                  i, target, insns[i]);
            return -2;
        }
    }

    // 2. Build the trampoline page: saved 16 bytes + abs jump back to target+16.
    uint8_t *tramp = allocTrampoline();
    if (!tramp) { NSLog(@"[SLInlineHook] trampoline alloc failed"); return -3; }

    memcpy(tramp, target, STUB_BYTES);
    buildAbsoluteJump(tramp + STUB_BYTES,
                      (uint64_t)((uint8_t *)target + STUB_BYTES));

    // If the page isn't already executable, upgrade it now.
    if (mprotect(tramp, 4096, PROT_READ | PROT_EXEC) != 0) {
        // mprotect may fail on RWX pages (already exec) — ignore in that case.
    }
    sys_icache_invalidate(tramp, STUB_BYTES * 2);

    // 3. Patch the target with an absolute jump to `replacement`.
    uint8_t stub[STUB_BYTES];
    buildAbsoluteJump(stub, (uint64_t)replacement);
    if (patchTarget(target, stub, STUB_BYTES) != 0) {
        // Can't undo the trampoline alloc cleanly — leaking one 4 KB page is
        // acceptable for a permanent hook failure.
        return -4;
    }

    if (outTrampoline) *outTrampoline = tramp;
    return 0;
}
