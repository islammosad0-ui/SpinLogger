#ifndef SLConstants_h
#define SLConstants_h

#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  Endpoint matching
// ---------------------------------------------------------------------------
static NSString *const kSLStrackEndpoint = @"/vikings/v3/strack/gzip";
static NSString *const kSLSpinEndpoint   = @"/spin";        // matches /api/v1/users/{id}/spin
static NSString *const kSLGameAPIHost    = @"moonactive.net";

// ---------------------------------------------------------------------------
//  Reel symbol name constants
// ---------------------------------------------------------------------------
static NSString *const kSLSymbolCoin          = @"coin";
static NSString *const kSLSymbolShield        = @"shield";
static NSString *const kSLSymbolAttack        = @"attack";
static NSString *const kSLSymbolSteal         = @"steal";
static NSString *const kSLSymbolGoldSack      = @"goldSack";
static NSString *const kSLSymbolSpins         = @"spins";
static NSString *const kSLSymbolAccumulation  = @"accumulation";

// ---------------------------------------------------------------------------
//  Raw reel value → symbol name mapping (from spin API r1/r2/r3)
// ---------------------------------------------------------------------------
static inline NSString *SLSymbolNameForReelValue(NSInteger val) {
    switch (val) {
        case 1:  return kSLSymbolCoin;
        case 2:  return kSLSymbolGoldSack;
        case 3:  return kSLSymbolAttack;
        case 4:  return kSLSymbolSteal;
        case 5:  return kSLSymbolShield;
        case 6:  return kSLSymbolSpins;
        case 30: return kSLSymbolAccumulation;
        default: return [NSString stringWithFormat:@"unknown_%ld", (long)val];
    }
}

// ---------------------------------------------------------------------------
//  Spin result outcome constants
// ---------------------------------------------------------------------------
static NSString *const kSLOutcomeGold          = @"gold";
static NSString *const kSLOutcomeAttack        = @"attack";
static NSString *const kSLOutcomeSteal         = @"steal";
static NSString *const kSLOutcomeShield        = @"shield";
static NSString *const kSLOutcomeSpins         = @"spins";
static NSString *const kSLOutcomeNoReward      = @"noreward";
static NSString *const kSLOutcomeAccumulation  = @"accumulation";

// ---------------------------------------------------------------------------
//  NSUserDefaults storage keys — use Speeder_ prefix for One.dylib compat
// ---------------------------------------------------------------------------
static NSString *const kSLDefaultsSpeedMultiplier  = @"Speeder_LastSpeed";
static NSString *const kSLDefaultsSpinTarget       = @"Speeder_SpinTarget";
static NSString *const kSLDefaultsAutoResetMode    = @"Speeder_AutoresetMode";
static NSString *const kSLDefaultsCounterPositions = @"Speeder_CounterPositions";
static NSString *const kSLDefaultsSpinCounter      = @"Speeder_SpinCounter";
static NSString *const kSLDefaultsTrisLockTarget   = @"Speeder_TrisLock";
static NSString *const kSLDefaultsTrisMonitor      = @"Speeder_TrisMonitor";
static NSString *const kSLDefaultsNetworkEnabled   = @"Speeder_Network";
static NSString *const kSLDefaultsPreset1          = @"Speeder_Preset1";
static NSString *const kSLDefaultsPreset2          = @"Speeder_Preset2";
static NSString *const kSLDefaultsThreshProfile    = @"Speeder_ThreshProfile";

// ---------------------------------------------------------------------------
//  File names
// ---------------------------------------------------------------------------
static NSString *const kSLSpinHistoryFile = @"spin_history.csv";
static NSString *const kSLSignalCSVFile   = @"il2cpp_signals.csv";

// IL2CPP trace mode (replaces signal CSV during reverse-engineering session)
static NSString *const kSLTraceJSONLPrefix    = @"il2cpp_trace_";
static NSString *const kSLTraceJSONLExtension = @".jsonl";
#define kSLTraceHexWindowBar     256    // bytes per slotBar instance
#define kSLTraceHexWindowResult  128    // bytes for currentSlotResult
#define kSLTraceHexArrayMaxBytes 2048   // cap raw array payload dump
#define kSLTracePointerFollowMaxDepth 1  // follow pointers one level only

// ---------------------------------------------------------------------------
//  NSNotification names & userInfo keys
// ---------------------------------------------------------------------------
static NSString *const SLSpinReceivedNotification  = @"NetShearsSpinEvent";
static NSString *const SLSpinDataKey               = @"SLSpinDataKey";
static NSString *const SLNetworkRequestNotification = @"Name.NetShearsNewRequest";

// Memory scanner notifications
static NSString *const SLMemoryScanNotification    = @"SLMemoryScanEvent";
static NSString *const SLScanSnapshotKey           = @"SLScanSnapshotKey";

// ---------------------------------------------------------------------------
//  SLTrackedSymbols
// ---------------------------------------------------------------------------
static inline NSArray<NSString *> *SLTrackedSymbols(void) {
    return @[
        kSLSymbolAttack,
        kSLSymbolSteal,
        kSLSymbolAccumulation,
        kSLSymbolShield,
        kSLSymbolSpins,
        kSLSymbolGoldSack
    ];
}

#endif /* SLConstants_h */
