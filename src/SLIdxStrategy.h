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

// ------ Overall recommendation (based on acc+spins, primary target) ------

@property (nonatomic, readonly) SLBetTier betTier;
@property (nonatomic, readonly, copy) NSString *betTierString;
@property (nonatomic, readonly) NSInteger compositeScore;
@property (nonatomic, readonly, copy) NSString *signalReason;

// ------ Last settled idx (for display / logging) ------

@property (nonatomic, readonly) int32_t lastR1Idx;
@property (nonatomic, readonly) int32_t lastR2Idx;
@property (nonatomic, readonly) int32_t lastR3Idx;

@end
