#import <Foundation/Foundation.h>
#import "SLSpinParser.h"

// ---------------------------------------------------------------------------
//  SLIdxStrategy — Per-triple-type idx-based strategy engine
//
//  Reads strip idx values from the IL2CPP memory scanner after each spin
//  settles, then computes per-type heat scores for the NEXT spin.
//
//  Each triple type has its own CV-validated signals (1,107 spins):
//    ACC+SPINS: r2=7(5/5), r1=7(4/5), r2=3(4/5), r1=3(4/5)
//    SHIELD:    r2=4(4/5), r3=5(4/5), r1=4(4/5)
//    ATTACK:    r3=4(4/5), r1=1(4/5), r2=6(4/5), r2=8(4/5), r1=0(4/5)
//    STEAL:     r1=1(4/5), r2=3(4/5), r2=1(4/5), r2=8(4/5), r2=2(4/5), r1=7(4/5)
//    COIN:      r1=4(5/5), r2=0(4/5), r2=8(4/5), r1=5(4/5), r1=0(4/5), r2=4(4/5)
//    GOLDSACK:  r2=6(4/5), r3=0(5/5), r2=0(4/5)
// ---------------------------------------------------------------------------

typedef NS_ENUM(NSInteger, SLBetTier) {
    SLBetTierMIN = 0,
    SLBetTierSMALL,
    SLBetTierNORMAL,
    SLBetTierBIG,
    SLBetTierMAX
};

/// Threshold profiles for combined (L1+L2) scoring.
/// Each profile trades catch-rate for precision.
typedef NS_ENUM(NSInteger, SLThresholdProfile) {
    SLThresholdProfileBalanced = 0,   // >=4 MAX, >=2 BIG  (74% caught, 18 bets/VT)
    SLThresholdProfileTight,          // >=6 MAX, >=3 BIG  (60% caught, 13 bets/VT)
    SLThresholdProfileUltra,          // >=8 MAX, >=4 BIG  (34% caught, 10.5 bets/VT)
    SLThresholdProfileSniper,         // >=10 MAX, >=6 BIG (20% caught, 6.7 bets/VT)
    SLThresholdProfileCount
};

/// Scorer configuration: V1 (original 1,107-spin), V2 (enhanced 3,864-spin)
typedef NS_ENUM(NSInteger, SLScorerConfig) {
    SLScorerConfigV1 = 0,   // original signals from 1,107 spins
    SLScorerConfigV2,        // enhanced: merged 3,864 spins + multi-lag + dead tuples
    SLScorerConfigCount
};

/// Per-type heat score + signal info
typedef struct {
    int score;        // composite score (higher = hotter)
    int maxScore;     // max possible score for this type
} SLTypeHeat;

@interface SLIdxStrategy : NSObject

+ (instancetype)shared;

// ------ Pending result (deferred CSV write) ------

/// Queue a spin result for deferred CSV write. Called by network parser.
- (void)queueResult:(SLSpinResult *)result;

/// Settle the pending result with idx from the scanner. Writes CSV,
/// feeds strategy engine, clears pending.
- (void)settlePendingWithR1Idx:(int32_t)r1 r2Idx:(int32_t)r2 r3Idx:(int32_t)r3;

// ------ Per-type heat scores (for the NEXT spin) ------

@property (nonatomic, readonly) SLTypeHeat heatAccSpins;
@property (nonatomic, readonly) SLTypeHeat heatShield;
@property (nonatomic, readonly) SLTypeHeat heatAttack;
@property (nonatomic, readonly) SLTypeHeat heatSteal;
@property (nonatomic, readonly) SLTypeHeat heatCoin;
@property (nonatomic, readonly) SLTypeHeat heatGoldSack;

// ------ Overall recommendation (combined L1+L2 scoring) ------

@property (nonatomic, readonly) SLBetTier betTier;
@property (nonatomic, readonly, copy) NSString *betTierString;
@property (nonatomic, readonly) NSInteger compositeScore;   // L1 + L2 combined
@property (nonatomic, readonly) NSInteger layer1Score;      // single-spin idx signals
@property (nonatomic, readonly) NSInteger layer2Score;      // 10-spin window patterns
@property (nonatomic, readonly, copy) NSString *signalReason;

// ------ Threshold profile (configurable from HUD) ------

@property (nonatomic, readonly) SLThresholdProfile thresholdProfile;
@property (nonatomic, readonly, copy) NSString *profileName;  // BAL/TGT/ULT/SNP

/// Cycle to the next threshold profile (persisted to UserDefaults)
- (void)cycleProfile;

// ------ Scorer config (V1 / V2, configurable from HUD) ------

@property (nonatomic, readonly) SLScorerConfig scorerConfig;
@property (nonatomic, readonly, copy) NSString *scorerName;  // V1/V2

/// Cycle to the next scorer config (persisted to UserDefaults)
- (void)cycleScorer;

// ------ Last settled idx (for display / logging) ------

@property (nonatomic, readonly) int32_t lastR1Idx;
@property (nonatomic, readonly) int32_t lastR2Idx;
@property (nonatomic, readonly) int32_t lastR3Idx;

@end
