#import "SLIdxStrategy.h"
#import "SLSpinStore.h"
#import "SLConstants.h"

@interface SLIdxStrategy ()
@property (nonatomic, strong) SLSpinResult *pendingResult;
@property (nonatomic, strong) NSTimer *flushTimer;

// Per-type heat (readwrite internally)
@property (nonatomic, readwrite) SLTypeHeat heatAccSpins;
@property (nonatomic, readwrite) SLTypeHeat heatShield;
@property (nonatomic, readwrite) SLTypeHeat heatAttack;
@property (nonatomic, readwrite) SLTypeHeat heatSteal;
@property (nonatomic, readwrite) SLTypeHeat heatCoin;
@property (nonatomic, readwrite) SLTypeHeat heatGoldSack;

// Overall recommendation
@property (nonatomic, readwrite) SLBetTier betTier;
@property (nonatomic, readwrite, copy) NSString *betTierString;
@property (nonatomic, readwrite) NSInteger compositeScore;
@property (nonatomic, readwrite, copy) NSString *signalReason;

// Last settled idx
@property (nonatomic, readwrite) int32_t lastR1Idx;
@property (nonatomic, readwrite) int32_t lastR2Idx;
@property (nonatomic, readwrite) int32_t lastR3Idx;
@end

@implementation SLIdxStrategy

+ (instancetype)shared {
    static SLIdxStrategy *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _betTier = SLBetTierNORMAL;
        _betTierString = @"NORMAL";
        _compositeScore = 0;
        _signalReason = @"no data";
        _lastR1Idx = -1;
        _lastR2Idx = -1;
        _lastR3Idx = -1;

        SLTypeHeat zero = {0, 0};
        _heatAccSpins = zero;
        _heatShield = zero;
        _heatAttack = zero;
        _heatSteal = zero;
        _heatCoin = zero;
        _heatGoldSack = zero;
    }
    return self;
}

// ---------------------------------------------------------------------------
//  Deferred CSV write — queue / settle / flush
// ---------------------------------------------------------------------------

- (void)queueResult:(SLSpinResult *)result {
    if (self.pendingResult) {
        NSLog(@"[SLIdxStrategy] Flushing unsettled pending result (seq=%ld)",
              (long)self.pendingResult.seq);
        self.pendingResult.r1Idx = -1;
        self.pendingResult.r2Idx = -1;
        self.pendingResult.r3Idx = -1;
        SLSpinStoreAppend(self.pendingResult);
    }

    self.pendingResult = result;

    [self.flushTimer invalidate];
    self.flushTimer = [NSTimer scheduledTimerWithTimeInterval:5.0
                                                       target:self
                                                     selector:@selector(flushTimeout)
                                                     userInfo:nil
                                                      repeats:NO];
}

- (void)flushTimeout {
    if (!self.pendingResult) return;
    NSLog(@"[SLIdxStrategy] Flush timeout — writing without idx (seq=%ld)",
          (long)self.pendingResult.seq);
    self.pendingResult.r1Idx = -1;
    self.pendingResult.r2Idx = -1;
    self.pendingResult.r3Idx = -1;
    SLSpinStoreAppend(self.pendingResult);
    self.pendingResult = nil;
}

- (void)settlePendingWithR1Idx:(int32_t)r1 r2Idx:(int32_t)r2 r3Idx:(int32_t)r3 {
    [self.flushTimer invalidate];
    self.flushTimer = nil;

    self.lastR1Idx = r1;
    self.lastR2Idx = r2;
    self.lastR3Idx = r3;

    if (self.pendingResult) {
        self.pendingResult.r1Idx = r1;
        self.pendingResult.r2Idx = r2;
        self.pendingResult.r3Idx = r3;

        // Detect valuable triple: accumulation(30) or spins(6)
        BOOL isTriple = (self.pendingResult.rawR1 == self.pendingResult.rawR2 &&
                         self.pendingResult.rawR2 == self.pendingResult.rawR3 &&
                         self.pendingResult.rawR1 != 0);
        BOOL isValuable = isTriple && (self.pendingResult.rawR1 == 30 ||
                                        self.pendingResult.rawR1 == 6);

        // Compute per-type strategy for NEXT spin
        [self computeAllSignals];

        // Attach strategy recommendation to result
        self.pendingResult.isValuableTriple = isValuable;
        self.pendingResult.strategyTier = self.betTierString;
        self.pendingResult.strategyScore = self.compositeScore;

        SLSpinStoreAppend(self.pendingResult);
        self.pendingResult = nil;
    } else {
        NSLog(@"[SLIdxStrategy] Scanner settled but no pending result");
        [self computeAllSignals];
    }
}

// ---------------------------------------------------------------------------
//  Per-type signal computation — all CV-validated from 62_per_type_signals.py
// ---------------------------------------------------------------------------

- (void)computeAllSignals {
    int32_t r1 = self.lastR1Idx;
    int32_t r2 = self.lastR2Idx;
    int32_t r3 = self.lastR3Idx;

    self.heatAccSpins  = [self scoreAccSpinsR1:r1 r2:r2 r3:r3];
    self.heatShield    = [self scoreShieldR1:r1 r2:r2 r3:r3];
    self.heatAttack    = [self scoreAttackR1:r1 r2:r2 r3:r3];
    self.heatSteal     = [self scoreStealR1:r1 r2:r2 r3:r3];
    self.heatCoin      = [self scoreCoinR1:r1 r2:r2 r3:r3];
    self.heatGoldSack  = [self scoreGoldSackR1:r1 r2:r2 r3:r3];

    // Overall tier based on acc+spins (primary target)
    NSInteger score = self.heatAccSpins.score;
    self.compositeScore = score;

    SLBetTier tier;
    NSString *tierStr;
    if (score >= 4)       { tier = SLBetTierMAX;    tierStr = @"MAX"; }
    else if (score >= 2)  { tier = SLBetTierBIG;    tierStr = @"BIG"; }
    else if (score <= -3) { tier = SLBetTierMIN;    tierStr = @"MIN"; }
    else if (score <= -1) { tier = SLBetTierSMALL;  tierStr = @"SMALL"; }
    else                  { tier = SLBetTierNORMAL;  tierStr = @"NORMAL"; }

    self.betTier = tier;
    self.betTierString = tierStr;

    // Build reason string from acc+spins signals
    NSMutableString *reason = [NSMutableString string];
    if (r2 == 7) [reason appendString:@"r2=7★ "];
    if (r1 == 7) [reason appendString:@"r1=7 "];
    if (r2 == 3) [reason appendString:@"r2=3 "];
    if (r1 == 3) [reason appendString:@"r1=3 "];
    if (r1 == 7 && r2 == 7) [reason appendString:@"77P "];
    if (r3 == 1) [reason appendString:@"r3=1✗ "];
    if (r2 == 0) [reason appendString:@"r2=0✗ "];
    self.signalReason = reason.length > 0 ? [reason stringByTrimmingCharactersInSet:
                        [NSCharacterSet whitespaceCharacterSet]] : @"-";

    NSLog(@"[SLIdxStrategy] idx=(%d,%d,%d) accSp=%d shld=%d atk=%d stl=%d coin=%d gold=%d -> %@",
          r1, r2, r3,
          self.heatAccSpins.score, self.heatShield.score,
          self.heatAttack.score, self.heatSteal.score,
          self.heatCoin.score, self.heatGoldSack.score,
          tierStr);
}

// ---------------------------------------------------------------------------
//  ACC+SPINS — 35 hits / 1107 spins (3.16%)
//  Primary target. Positive: r2=7(5/5), r1=7(4/5), r2=3(4/5), r1=3(4/5)
//  Pairs: r1=7,r2=7(4/5), r1=7,r3=8(4/5), r2=7,r3=8(4/5), r2=3,r3=8(4/5),
//         r1=3,r3=8(4/5), r1=3,r2=7(4/5), r1=3,r2=3(4/5)
//  Negative: r3=1(5/5 0-hit), r2=2(4/5), r2=0(5/5), r1=5(4/5), r1=0(4/5)
//  Dead pairs: r1=4,r2=4(0/71), r1=4,r3=4(0/48), r1=7,r3=0(0/60), etc.
// ---------------------------------------------------------------------------
- (SLTypeHeat)scoreAccSpinsR1:(int32_t)r1 r2:(int32_t)r2 r3:(int32_t)r3 {
    int score = 0;
    int maxScore = 10;  // theoretical max if all positives align

    // Individual signals
    if (r2 == 7) score += 2;   // 5/5 CV, +2.2pp (star signal)
    if (r1 == 7) score += 1;   // 4/5 CV, +1.4pp
    if (r2 == 3) score += 1;   // 4/5 CV, +1.2pp
    if (r1 == 3) score += 1;   // 4/5 CV, +1.2pp

    // Negative signals (validated dead zones)
    if (r3 == 1) score -= 2;   // 5/5 CV, 0/100 hits — hard dead zone
    if (r2 == 0) score -= 1;   // 5/5 CV, 2/159 (1.3%, below 3.16% base)
    if (r2 == 2) score -= 1;   // 4/5 CV, 1/87
    if (r1 == 5) score -= 1;   // 4/5 CV, 1/65
    if (r1 == 0) score -= 1;   // 4/5 CV, 2/127

    // Pair bonuses (synergy on top of individuals)
    if (r1 == 7 && r2 == 7) score += 2;   // 4/5 CV, 5/73 (6.8%), +3.7pp
    if (r1 == 7 && r3 == 8) score += 1;   // 4/5 CV, 6/108, +2.4pp
    if (r2 == 7 && r3 == 8) score += 1;   // 4/5 CV, 7/135, +2.0pp
    if (r1 == 3 && r2 == 7) score += 1;   // 4/5 CV, 4/95, +1.0pp
    if (r1 == 3 && r2 == 4) score += 1;   // 3/5 CV, 3/24 (12.5%), +9.3pp — all acc

    // Dead pairs (hard negative)
    if (r1 == 4 && r2 == 4) score -= 2;   // 0/71, 5/5 CV dead
    if (r1 == 7 && r3 == 0) score -= 2;   // 0/60, 5/5 CV dead
    if (r1 == 4 && r3 == 4) score -= 1;   // 0/48, 5/5 CV dead

    return (SLTypeHeat){score, maxScore};
}

// ---------------------------------------------------------------------------
//  SHIELD — 69 hits / 1107 spins (6.23%)
//  Positive: r2=4(4/5,+4.4pp), r3=5(4/5,+3.5pp), r1=4(4/5,+3.5pp)
//  Pairs: r1=4,r2=4(4/5,+3.6pp)
//  Negative: r3=3(4/5,-3.5pp), r2=7(4/5,-3.3pp)
// ---------------------------------------------------------------------------
- (SLTypeHeat)scoreShieldR1:(int32_t)r1 r2:(int32_t)r2 r3:(int32_t)r3 {
    int score = 0;
    int maxScore = 8;

    if (r2 == 4) score += 2;   // 4/5 CV, +4.4pp
    if (r3 == 5) score += 2;   // 4/5 CV, +3.5pp
    if (r1 == 4) score += 1;   // 4/5 CV, +3.5pp

    if (r3 == 3) score -= 1;   // 4/5 CV, -3.5pp
    if (r2 == 7) score -= 1;   // 4/5 CV, -3.3pp

    // Pair bonus
    if (r1 == 4 && r2 == 4) score += 1;  // 4/5 CV, 7/71 (+3.6pp)

    return (SLTypeHeat){score, maxScore};
}

// ---------------------------------------------------------------------------
//  ATTACK — 117 hits / 1107 spins (10.57%)
//  Positive: r3=4(4/5,+8.9pp), r1=1(4/5,+6.3pp), r2=6(4/5,+4.2pp),
//            r2=8(4/5,+2.4pp), r1=0(4/5,+2.0pp)
//  Pairs: r2=6,r3=4(4/5,+13.6pp), r1=1,r2=8(4/5,+10.8pp),
//         r1=1,r3=8(4/5,+10.8pp), r1=3,r2=3(4/5), r2=8,r3=8(4/5),
//         r1=0,r2=0(4/5), r1=0,r3=0(4/5)
//  Negative: r1=5(5/5,-6.0pp)
//  Dead pairs: r2=4,r3=1(5/5), r1=6,r2=4(4/5)
// ---------------------------------------------------------------------------
- (SLTypeHeat)scoreAttackR1:(int32_t)r1 r2:(int32_t)r2 r3:(int32_t)r3 {
    int score = 0;
    int maxScore = 10;

    if (r3 == 4) score += 2;   // 4/5 CV, +8.9pp
    if (r1 == 1) score += 2;   // 4/5 CV, +6.3pp
    if (r2 == 6) score += 1;   // 4/5 CV, +4.2pp
    if (r2 == 8) score += 1;   // 4/5 CV, +2.4pp
    if (r1 == 0) score += 1;   // 4/5 CV, +2.0pp

    if (r1 == 5) score -= 2;   // 5/5 CV, -6.0pp

    // Pair bonuses
    if (r2 == 6 && r3 == 4) score += 2;   // 4/5 CV, 7/29, +13.6pp
    if (r1 == 1 && r2 == 8) score += 1;   // 4/5 CV, 9/42, +10.8pp
    if (r1 == 1 && r3 == 8) score += 1;   // 4/5 CV, 9/42, +10.8pp

    // Dead pairs
    if (r2 == 4 && r3 == 1) score -= 1;   // 0/34, 5/5 CV

    return (SLTypeHeat){score, maxScore};
}

// ---------------------------------------------------------------------------
//  STEAL — 48 hits / 1107 spins (4.34%)
//  Positive: r1=1(4/5,+3.5pp), r2=3(4/5,+3.1pp), r2=1(4/5,+2.0pp),
//            r2=8(4/5,+1.7pp), r2=2(4/5,+1.4pp), r1=7(4/5,+1.1pp)
//  Pairs: r1=7,r2=3(4/5,+5.5pp), r2=3,r3=8(4/5,+3.5pp),
//         r1=7,r3=8(4/5,+2.1pp), r1=2,r2=2(4/5,+2.1pp),
//         r1=3,r3=0(4/5,+2.0pp), r2=8,r3=8(4/5,+1.7pp)
//  Negative: r2=5(5/5,dead), r1=6(4/5,-3.3pp), r3=4(4/5,-3.1pp),
//            r1=5(4/5,-2.8pp), r2=6(4/5,-2.5pp)
// ---------------------------------------------------------------------------
- (SLTypeHeat)scoreStealR1:(int32_t)r1 r2:(int32_t)r2 r3:(int32_t)r3 {
    int score = 0;
    int maxScore = 10;

    if (r1 == 1) score += 1;   // 4/5 CV, +3.5pp
    if (r2 == 3) score += 1;   // 4/5 CV, +3.1pp
    if (r2 == 1) score += 1;   // 4/5 CV, +2.0pp
    if (r2 == 8) score += 1;   // 4/5 CV, +1.7pp
    if (r1 == 7) score += 1;   // 4/5 CV, +1.1pp

    if (r2 == 5) score -= 2;   // 5/5 CV, 0/63 dead
    if (r1 == 6) score -= 1;   // 4/5 CV, -3.3pp
    if (r3 == 4) score -= 1;   // 4/5 CV, -3.1pp
    if (r1 == 5) score -= 1;   // 4/5 CV, -2.8pp
    if (r2 == 6) score -= 1;   // 4/5 CV, -2.5pp

    // Pair bonuses
    if (r1 == 7 && r2 == 3) score += 1;   // 4/5 CV, 6/61, +5.5pp
    if (r2 == 3 && r3 == 8) score += 1;   // 4/5 CV, 10/128, +3.5pp

    // Dead pairs
    if (r1 == 4 && r3 == 4) score -= 1;   // 0/48, 5/5 CV
    if (r1 == 6 && r3 == 1) score -= 1;   // 0/39, 5/5 CV
    if (r1 == 6 && r2 == 6) score -= 1;   // 0/35, 5/5 CV

    return (SLTypeHeat){score, maxScore};
}

// ---------------------------------------------------------------------------
//  COIN — 49 hits / 1107 spins (4.43%)
//  Positive: r1=4(5/5,+4.4pp), r2=0(4/5,+2.5pp), r2=8(4/5,+2.5pp),
//            r1=5(4/5,+1.7pp), r1=0(4/5,+1.1pp), r2=4(4/5,+0.9pp)
//  Pairs: r1=4,r2=4(4/5,+6.8pp), r2=0,r3=0(4/5), r2=8,r3=8(4/5),
//         r1=0,r2=0(4/5), r1=0,r3=0(4/5)
//  Negative: r1=6(5/5,dead)
// ---------------------------------------------------------------------------
- (SLTypeHeat)scoreCoinR1:(int32_t)r1 r2:(int32_t)r2 r3:(int32_t)r3 {
    int score = 0;
    int maxScore = 8;

    if (r1 == 4) score += 2;   // 5/5 CV, +4.4pp
    if (r2 == 0) score += 1;   // 4/5 CV, +2.5pp
    if (r2 == 8) score += 1;   // 4/5 CV, +2.5pp
    if (r1 == 5) score += 1;   // 4/5 CV, +1.7pp
    if (r1 == 0) score += 1;   // 4/5 CV, +1.1pp

    if (r1 == 6) score -= 2;   // 5/5 CV, 0/93 dead

    // Pair bonuses
    if (r1 == 4 && r2 == 4) score += 1;   // 4/5 CV, 8/71, +6.8pp
    if (r2 == 0 && r3 == 0) score += 1;   // 4/5 CV, 11/159, +2.5pp

    // Dead pairs
    if (r1 == 6 && r3 == 1) score -= 1;   // 0/39, 5/5 CV
    if (r1 == 6 && r2 == 6) score -= 1;   // 0/35, 5/5 CV

    return (SLTypeHeat){score, maxScore};
}

// ---------------------------------------------------------------------------
//  GOLDSACK — 58 hits / 1107 spins (5.24%)
//  Positive: r2=6(4/5,+3.1pp), r3=0(5/5,+2.8pp), r2=0(4/5,+1.7pp)
//  Pairs: r1=3,r3=0(4/5,+4.3pp), r2=0,r3=0(4/5,+1.7pp)
//  Negative: r2=3(4/5,-1.5pp)
// ---------------------------------------------------------------------------
- (SLTypeHeat)scoreGoldSackR1:(int32_t)r1 r2:(int32_t)r2 r3:(int32_t)r3 {
    int score = 0;
    int maxScore = 6;

    if (r2 == 6) score += 1;   // 4/5 CV, +3.1pp
    if (r3 == 0) score += 2;   // 5/5 CV, +2.8pp
    if (r2 == 0) score += 1;   // 4/5 CV, +1.7pp

    if (r2 == 3) score -= 1;   // 4/5 CV, -1.5pp

    // Pair bonus
    if (r1 == 3 && r3 == 0) score += 1;   // 4/5 CV, 6/63, +4.3pp

    return (SLTypeHeat){score, maxScore};
}

@end
