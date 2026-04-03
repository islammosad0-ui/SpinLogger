#ifndef SLConstants_h
#define SLConstants_h

#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  Endpoint matching
// ---------------------------------------------------------------------------
static NSString *const kSLStrackEndpoint = @"/vikings/v3/strack/gzip";
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
//  NSUserDefaults storage keys (all prefixed SpinLogger_)
// ---------------------------------------------------------------------------
static NSString *const kSLDefaultsSpeedMultiplier  = @"SpinLogger_SpeedMultiplier";
static NSString *const kSLDefaultsSpinTarget       = @"SpinLogger_SpinTarget";
static NSString *const kSLDefaultsAutoResetMode    = @"SpinLogger_AutoResetMode";
static NSString *const kSLDefaultsCounterPositions = @"SpinLogger_CounterPositions";
static NSString *const kSLDefaultsCounterVisible   = @"SpinLogger_CounterVisible";
static NSString *const kSLDefaultsTrisLockTarget   = @"SpinLogger_TrisLockTarget";
static NSString *const kSLDefaultsTrisSkipEnabled  = @"SpinLogger_TrisSkipEnabled";
static NSString *const kSLDefaultsNetworkEnabled   = @"SpinLogger_NetworkEnabled";
static NSString *const kSLDefaultsPreset1          = @"SpinLogger_Preset1";
static NSString *const kSLDefaultsPreset2          = @"SpinLogger_Preset2";

// ---------------------------------------------------------------------------
//  File names
// ---------------------------------------------------------------------------
static NSString *const kSLSpinHistoryFile = @"spin_history.csv";

// ---------------------------------------------------------------------------
//  NSNotification names & userInfo keys
// ---------------------------------------------------------------------------
static NSString *const SLSpinReceivedNotification = @"SLSpinReceivedNotification";
static NSString *const SLSpinDataKey              = @"SLSpinDataKey";

// ---------------------------------------------------------------------------
//  SLTrackedSymbols — symbols that counters track
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
