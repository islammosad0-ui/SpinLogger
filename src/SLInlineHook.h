#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLInlineHook
//
//  Minimal arm64 iOS inline hooker. Replaces the first 16 bytes of `target`
//  with an absolute jump to `replacement`, and builds a trampoline (saved
//  prologue + absolute jump back to target+16) that the caller can use to
//  invoke the original implementation.
//
//  Limitations:
//    - target must begin with four non-PC-relative instructions. ADR, ADRP,
//      B, BL, CB, TB, B.cond and LDR-literal in the first 16 bytes are
//      rejected (returns negative, no patch applied).
//    - target's page must be writable via vm_protect (jailbroken iOS, or
//      any process with CS_ALLOW_JIT or equivalent kernel patches).
//
//  Returns 0 on success, negative on failure.
// ---------------------------------------------------------------------------

int SLInlineHook_Install(void *target, void *replacement, void **outTrampoline);
