#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLSpinHook
//
//  Installs inline hooks via Dobby on five SlotMachineManager methods that
//  carry exploitable information:
//
//      1. TrySetNexSpinHitRecord()              → next-spin hit oracle
//      2. OnSpinResultReceived(NetworkResponse) → raw server response dump
//      3. SetFreezeResolve()                    → freeze-resolve gate
//      4. activateWinSequence(SlotResult)       → finalized spin result
//      5. ContainsAccumulationResult(SlotSymbol)→ accumulation foreknowledge
//
//  Every hook writes one line to ~/Documents/hook_events.csv with columns:
//      timestamp, hook, arg1, arg2, ret, notes
//
//  Call SLSpinHook_InstallAll once IL2CPP class pointers are resolved. Safe
//  to call multiple times — subsequent calls are no-ops.
// ---------------------------------------------------------------------------

/// Install all five hooks. Both klass pointers must be non-NULL. Returns the
/// number of hooks successfully installed (0..5).
int SLSpinHook_InstallAll(void *klassSlotMachineManager, void *klassSlotResult);
