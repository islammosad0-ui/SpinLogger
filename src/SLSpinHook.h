#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLSpinHook
//
//  Hooks four SlotMachineManager methods via arm64 inline hot-patching:
//
//      1. OnSpinResultReceived(NetworkResponse) → raw server response dump
//      2. SetFreezeResolve()                    → freeze-resolve gate
//      3. activateWinSequence(SlotResult)       → finalized spin result
//      4. ContainsAccumulationResult(SlotSymbol)→ accumulation foreknowledge
//
//  Every hook writes one line to ~/Documents/hook_events.csv with columns:
//      timestamp, hook, arg1, arg2, ret, notes
//
//  DIAGNOSTIC MODE: write "DIAG" in ~/Documents/hook_config.txt.
//  Probes __TEXT page operations step-by-step without installing hooks,
//  logs to hook_breadcrumb.txt so we can identify exactly which operation
//  causes the crash. Also checks iOS code-signing flags (csops).
//
//  Call SLSpinHook_InstallAll once IL2CPP class pointers are resolved. Safe
//  to call multiple times — subsequent calls are no-ops.
// ---------------------------------------------------------------------------

/// Install hooks (or run diagnostics if DIAG mode). Returns the number of
/// hooks successfully installed (0..4).
int SLSpinHook_InstallAll(void *klassSlotMachineManager, void *klassSlotResult);
