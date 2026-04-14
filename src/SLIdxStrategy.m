#import "SLIdxStrategy.h"
#import "SLSpinStore.h"
#import "SLConstants.h"
#import "SLGapPredictor.h"

// ---------------------------------------------------------------------------
//  Ring buffer for Layer 2 window scoring
// ---------------------------------------------------------------------------
#define kSLHistoryMax 20

typedef struct {
    int32_t r1, r2, r3;
    int32_t symR1;      // raw symbol code for reel 1 (4=steal)
} SLSpinRecord;

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
@property (nonatomic, readwrite) NSInteger layer1Score;
@property (nonatomic, readwrite) NSInteger layer2Score;
@property (nonatomic, readwrite, copy) NSString *signalReason;

// Threshold profile
@property (nonatomic, readwrite) SLThresholdProfile thresholdProfile;
@property (nonatomic, readwrite, copy) NSString *profileName;

// Scorer config
@property (nonatomic, readwrite) SLScorerConfig scorerConfig;
@property (nonatomic, readwrite, copy) NSString *scorerName;

// Last settled idx
@property (nonatomic, readwrite) int32_t lastR1Idx;
@property (nonatomic, readwrite) int32_t lastR2Idx;
@property (nonatomic, readwrite) int32_t lastR3Idx;
@end

@implementation SLIdxStrategy {
    SLSpinRecord _history[kSLHistoryMax];
    int _historyCount;   // total spins pushed (may exceed kSLHistoryMax)
    int _historyHead;    // next write position (circular)
}

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
        _layer1Score = 0;
        _layer2Score = 0;
        _signalReason = @"no data";
        _lastR1Idx = -1;
        _lastR2Idx = -1;
        _lastR3Idx = -1;

        _historyCount = 0;
        _historyHead = 0;
        memset(_history, 0, sizeof(_history));

        // Load saved threshold profile
        NSInteger saved = [[NSUserDefaults standardUserDefaults]
                           integerForKey:kSLDefaultsThreshProfile];
        if (saved >= 0 && saved < SLThresholdProfileCount) {
            _thresholdProfile = (SLThresholdProfile)saved;
        } else {
            _thresholdProfile = SLThresholdProfileBalanced;
        }
        _profileName = [self nameForProfile:_thresholdProfile];

        // Load saved scorer config
        NSInteger savedScorer = [[NSUserDefaults standardUserDefaults]
                                  integerForKey:kSLDefaultsScorerConfig];
        if (savedScorer >= 0 && savedScorer < SLScorerConfigCount) {
            _scorerConfig = (SLScorerConfig)savedScorer;
        } else {
            _scorerConfig = SLScorerConfigV1;
        }
        _scorerName = [self nameForScorer:_scorerConfig];

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

    // Push into ring buffer for Layer 2 window scoring
    int32_t symR1 = self.pendingResult ? (int32_t)self.pendingResult.rawR1 : -1;
    [self pushHistoryR1:r1 r2:r2 r3:r3 symR1:symR1];

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

        // Feed gap predictor (before computing signals so panel sees both)
        [[SLGapPredictor shared] recordSpinIsVT:isValuable];

        // Compute combined L1+L2 strategy for NEXT spin
        [self computeAllSignals];

        // Attach strategy recommendation to result
        self.pendingResult.isValuableTriple = isValuable;
        self.pendingResult.strategyTier = self.betTierString;
        self.pendingResult.strategyScore = self.compositeScore;
        self.pendingResult.l1Score = self.layer1Score;
        self.pendingResult.l2Score = self.layer2Score;
        self.pendingResult.scorerCfg = self.scorerName;

        SLSpinStoreAppend(self.pendingResult);
        self.pendingResult = nil;
    } else {
        NSLog(@"[SLIdxStrategy] Scanner settled but no pending result");
        // Still count as a non-VT spin for gap tracking
        [[SLGapPredictor shared] recordSpinIsVT:NO];
        [self computeAllSignals];
    }
}

// ---------------------------------------------------------------------------
//  Ring buffer management
// ---------------------------------------------------------------------------
- (void)pushHistoryR1:(int32_t)r1 r2:(int32_t)r2 r3:(int32_t)r3 symR1:(int32_t)sym {
    _history[_historyHead] = (SLSpinRecord){r1, r2, r3, sym};
    _historyHead = (_historyHead + 1) % kSLHistoryMax;
    _historyCount++;
}

// ---------------------------------------------------------------------------
//  Per-type signal computation — all CV-validated
//  Combined scoring: Layer 1 (single-spin idx) + Layer 2 (10-spin window)
//  Scorer V1 (1,107-spin) vs V2 (3,864-spin enhanced + multi-lag)
// ---------------------------------------------------------------------------

- (void)computeAllSignals {
    int32_t r1 = self.lastR1Idx;
    int32_t r2 = self.lastR2Idx;
    int32_t r3 = self.lastR3Idx;

    BOOL v2 = (self.scorerConfig == SLScorerConfigV2);

    // Per-type heat bars (Layer 1 only — for individual display)
    self.heatAccSpins  = v2 ? [self scoreAccSpinsV2R1:r1 r2:r2 r3:r3]
                            : [self scoreAccSpinsR1:r1 r2:r2 r3:r3];
    self.heatShield    = [self scoreShieldR1:r1 r2:r2 r3:r3];
    self.heatAttack    = [self scoreAttackR1:r1 r2:r2 r3:r3];
    self.heatSteal     = [self scoreStealR1:r1 r2:r2 r3:r3];

    // Layer 1: acc+spins single-spin score
    NSInteger l1 = self.heatAccSpins.score;

    // Multi-lag + sequence + pattern bonuses (V2 only): read from ring buffer
    NSInteger multiLag = 0;
    BOOL patA = NO, patD = NO, patF = NO;
    if (v2) {
        // Pattern D: sum of current idx == 15 (no history needed)
        if (r1 + r2 + r3 == 15) { multiLag += 1; patD = YES; }

        int available = MIN(_historyCount, kSLHistoryMax);
        if (available >= 2) {
            // prev = previous spin (head-1 is current, head-2 is previous)
            int idxPrev = (_historyHead - 2 + kSLHistoryMax) % kSLHistoryMax;
            SLSpinRecord prev = _history[idxPrev];

            // Sequence patterns (prev r3 -> current r3)
            if (prev.r3 == r3)              multiLag += 1;   // dr3=+0: back-to-back same r3, 1.6x lift
            if (prev.r3 == 5 && r3 == 5)    multiLag += 1;   // r3:(5,5) 4.4x lift (stacks with dr3=+0)
            if (prev.r3 == 8 && r3 == 5)    multiLag += 1;   // r3:(8,5) 2.7x lift

            // Pattern A: back-to-back same r1
            if (prev.r1 == r1) { multiLag += 1; patA = YES; }

            // Pattern F: cross-reel prev.r2==7 -> current r3==8
            if (prev.r2 == 7 && r3 == 8) { multiLag += 1; patF = YES; }

            // Lag-2 penalties
            if (prev.r3 == 6)  multiLag -= 1;   // lag-2 r3=6: dead (0/57, 5/5 CV)
            if (prev.r3 == 2)  multiLag -= 1;   // lag-2 r3=2: -1.76pp, 5/5 CV
            if (prev.r1 == 2)  multiLag -= 1;   // lag-2 r1=2: -1.56pp, 5/5 CV
        }
        if (available >= 3) {
            int idx3 = (_historyHead - 3 + kSLHistoryMax) % kSLHistoryMax;
            SLSpinRecord prev3 = _history[idx3];
            if (prev3.r3 == 4)  multiLag += 1;   // lag-3 r3=4: +2.68pp, 4/5 CV
            if (prev3.r1 == 8)  multiLag -= 1;   // lag-3 r1=8: dead (0/39, 5/5 CV)
        }
        l1 += multiLag;
    }

    // Layer 2: 10-spin window patterns
    NSInteger l2 = v2 ? [self scoreLayer2V2] : [self scoreLayer2];

    // Combined
    NSInteger combined = l1 + l2;

    self.layer1Score = l1;
    self.layer2Score = l2;
    self.compositeScore = combined;

    // Tier from combined score using active profile thresholds
    int maxThresh, bigThresh;
    switch (self.thresholdProfile) {
        case SLThresholdProfileBalanced: maxThresh = 4;  bigThresh = 2;  break;
        case SLThresholdProfileTight:    maxThresh = 6;  bigThresh = 3;  break;
        case SLThresholdProfileUltra:    maxThresh = 8;  bigThresh = 4;  break;
        case SLThresholdProfileSniper:   maxThresh = 10; bigThresh = 6;  break;
        default:                         maxThresh = 4;  bigThresh = 2;  break;
    }

    SLBetTier tier;
    NSString *tierStr;
    if (combined >= maxThresh)      { tier = SLBetTierMAX;    tierStr = @"MAX"; }
    else if (combined >= bigThresh) { tier = SLBetTierBIG;    tierStr = @"BIG"; }
    else if (combined <= -3)        { tier = SLBetTierMIN;    tierStr = @"MIN"; }
    else if (combined <= -1)        { tier = SLBetTierSMALL;  tierStr = @"SMALL"; }
    else                            { tier = SLBetTierNORMAL; tierStr = @"NORMAL"; }

    self.betTier = tier;
    self.betTierString = tierStr;

    // Build reason string
    NSMutableString *reason = [NSMutableString string];
    if (v2) {
        if (r2 == 7) [reason appendString:@"r2=7* "];
        if (r1 == 7) [reason appendString:@"r1=7 "];
        if (r2 == 3) [reason appendString:@"r2=3 "];
        if (r1 == 3) [reason appendString:@"r1=3 "];
        if (r3 == 3) [reason appendString:@"r3=3 "];
        if (r3 == 8) [reason appendString:@"r3=8 "];
        if (r1 == 7 && r2 == 7) [reason appendString:@"77P "];
        if (r1 == 7 && r2 == 3) [reason appendString:@"73P "];
        if (r3 == 1) [reason appendString:@"r3=1X "];
        if (r2 == 5) [reason appendString:@"r2=5X "];
        if (patA) [reason appendString:@"A "];
        if (patD) [reason appendString:@"D "];
        if (patF) [reason appendString:@"F "];
        if (multiLag != 0) [reason appendFormat:@"ML%+ld ", (long)multiLag];
    } else {
        if (r2 == 7) [reason appendString:@"r2=7\u2605 "];
        if (r1 == 7) [reason appendString:@"r1=7 "];
        if (r2 == 3) [reason appendString:@"r2=3 "];
        if (r1 == 3) [reason appendString:@"r1=3 "];
        if (r1 == 7 && r2 == 7) [reason appendString:@"77P "];
        if (r3 == 1) [reason appendString:@"r3=1\u2717 "];
        if (r2 == 0) [reason appendString:@"r2=0\u2717 "];
    }
    if (l2 != 0) [reason appendFormat:@"W%+ld ", (long)l2];
    self.signalReason = reason.length > 0 ? [reason stringByTrimmingCharactersInSet:
                        [NSCharacterSet whitespaceCharacterSet]] : @"-";

    if (v2) {
        NSLog(@"[SLIdxStrategy] idx=(%d,%d,%d) L1=%+ld ML=%+ld%s%s%s L2=%+ld =%+ld [%@/%@] -> %@",
              r1, r2, r3, (long)(l1 - multiLag), (long)multiLag,
              patA ? "+A" : "", patD ? "+D" : "", patF ? "+F" : "",
              (long)l2, (long)combined, self.scorerName, self.profileName, tierStr);
    } else {
        NSLog(@"[SLIdxStrategy] idx=(%d,%d,%d) L1=%+ld L2=%+ld =%+ld [%@/%@] -> %@",
              r1, r2, r3, (long)l1, (long)l2, (long)combined,
              self.scorerName, self.profileName, tierStr);
    }

    // Notify HUD immediately — no polling delay
    [[NSNotificationCenter defaultCenter] postNotificationName:SLStrategyUpdatedNotification
                                                        object:self];
}

// ---------------------------------------------------------------------------
//  Layer 2 V1: 10-spin window pattern scorer (from 65_combined_scorer.py)
//  Signals A-J validated on 1,107 spins with 5-fold CV
// ---------------------------------------------------------------------------
- (NSInteger)scoreLayer2 {
    int available = MIN(_historyCount, kSLHistoryMax);
    if (available < 3) return 0;

    SLSpinRecord win[kSLHistoryMax];
    for (int i = 0; i < available; i++) {
        int bufIdx = (_historyHead - available + i + kSLHistoryMax) % kSLHistoryMax;
        win[i] = _history[bufIdx];
    }

    int windowSize = MIN(available, 10);
    int windowStart = available - windowSize;
    int score = 0;

    // --- Signal A: steal count on reel_1 in 10-spin window ---
    int stealR1Count = 0;
    for (int i = windowStart; i < available; i++) {
        if (win[i].symR1 == 4) stealR1Count++;
    }
    if (stealR1Count >= 2) score += 1;

    // --- Signal B: r3==4 count in 10-spin window (VT 12.0% vs base 6.4%) ---
    int r3_4_count = 0;
    for (int i = windowStart; i < available; i++) {
        if (win[i].r3 == 4) r3_4_count++;
    }
    if (r3_4_count >= 2) score += 1;

    // --- Signal C: r3 bigram (0->8) in window ---
    for (int i = windowStart + 1; i < available; i++) {
        if (win[i-1].r3 == 0 && win[i].r3 == 8) {
            score += 1;
            break;
        }
    }

    // --- Signal D: r3 bigram (8->4) or (4->4) in window ---
    for (int i = windowStart + 1; i < available; i++) {
        if ((win[i-1].r3 == 8 && win[i].r3 == 4) ||
            (win[i-1].r3 == 4 && win[i].r3 == 4)) {
            score += 1;
            break;
        }
    }

    // --- Signal E: r2==6 gap <= 7 (appeared recently = good) ---
    int r2_6_gap = -1;
    for (int lookback = 1; lookback <= available; lookback++) {
        int idx = available - lookback;
        if (win[idx].r2 == 6) {
            r2_6_gap = lookback;
            break;
        }
    }
    if (r2_6_gap > 0 && r2_6_gap <= 7) score += 1;

    // --- Signal F: r3==1 gap > 10 (absent = good for VT) ---
    // --- Signal G: r3==1 gap <= 3 (very recent = BAD) ---
    int r3_1_gap = -1;
    for (int lookback = 1; lookback <= available; lookback++) {
        int idx = available - lookback;
        if (win[idx].r3 == 1) {
            r3_1_gap = lookback;
            break;
        }
    }
    if (r3_1_gap < 0 || r3_1_gap > 10) score += 1;   // F: absent = good
    if (r3_1_gap > 0 && r3_1_gap <= 3)  score -= 2;   // G: very recent = dead zone

    // --- Signal H: tuple (3,6,4) in window ---
    for (int i = windowStart; i < available; i++) {
        if (win[i].r1 == 3 && win[i].r2 == 6 && win[i].r3 == 4) {
            score += 1;
            break;
        }
    }

    // --- Signal I: r3 variety (low dup rate = good) ---
    if (windowSize > 1) {
        int r3_dups = 0;
        for (int i = windowStart + 1; i < available; i++) {
            if (win[i].r3 == win[i-1].r3) r3_dups++;
        }
        float dup_rate = (float)r3_dups / (float)(windowSize - 1);
        if (dup_rate < 0.15f) score += 1;
    }

    // --- Signal J: r1 bigram (3,3) in window ---
    for (int i = windowStart + 1; i < available; i++) {
        if (win[i-1].r1 == 3 && win[i].r1 == 3) {
            score += 1;
            break;
        }
    }

    return score;
}

// ---------------------------------------------------------------------------
//  Layer 2 V2: re-validated on 3,864 spins (merged Ahmed+Nick)
//  Dropped E (2/5 CV), I (2/5 CV). Flipped J to -1 (4/5 CV negative).
// ---------------------------------------------------------------------------
- (NSInteger)scoreLayer2V2 {
    int available = MIN(_historyCount, kSLHistoryMax);
    if (available < 3) return 0;

    SLSpinRecord win[kSLHistoryMax];
    for (int i = 0; i < available; i++) {
        int bufIdx = (_historyHead - available + i + kSLHistoryMax) % kSLHistoryMax;
        win[i] = _history[bufIdx];
    }

    int windowSize = MIN(available, 10);
    int windowStart = available - windowSize;
    int score = 0;

    // --- Signal A: steal count on reel_1 >= 2 (5/5 CV, +2.36pp) ---
    int stealR1Count = 0;
    for (int i = windowStart; i < available; i++) {
        if (win[i].symR1 == 4) stealR1Count++;
    }
    if (stealR1Count >= 2) score += 1;

    // --- Signal B: r3==4 count >= 2 (5/5 CV, +2.36pp) ---
    int r3_4_count = 0;
    for (int i = windowStart; i < available; i++) {
        if (win[i].r3 == 4) r3_4_count++;
    }
    if (r3_4_count >= 2) score += 1;

    // --- Signal C: r3 bigram (0->8) (4/5 CV, +0.21pp) ---
    for (int i = windowStart + 1; i < available; i++) {
        if (win[i-1].r3 == 0 && win[i].r3 == 8) {
            score += 1;
            break;
        }
    }

    // --- Signal D: r3 bigram (8->4) or (4->4) (4/5 CV, +1.62pp) ---
    for (int i = windowStart + 1; i < available; i++) {
        if ((win[i-1].r3 == 8 && win[i].r3 == 4) ||
            (win[i-1].r3 == 4 && win[i].r3 == 4)) {
            score += 1;
            break;
        }
    }

    // Signal E: REMOVED — r2=6 gap (2/5 CV, not validated for VT)

    // --- Signal F: r3==1 absent (4/5 CV, +0.41pp) ---
    // --- Signal G: r3==1 recent (5/5 CV, -0.92pp) ---
    int r3_1_gap = -1;
    for (int lookback = 1; lookback <= available; lookback++) {
        int idx = available - lookback;
        if (win[idx].r3 == 1) {
            r3_1_gap = lookback;
            break;
        }
    }
    if (r3_1_gap < 0 || r3_1_gap > 10) score += 1;   // F: absent = good
    if (r3_1_gap > 0 && r3_1_gap <= 3)  score -= 2;   // G: very recent = dead

    // --- Signal H: tuple (3,6,4) in window (4/5 CV, +1.58pp) ---
    for (int i = windowStart; i < available; i++) {
        if (win[i].r1 == 3 && win[i].r2 == 6 && win[i].r3 == 4) {
            score += 1;
            break;
        }
    }

    // Signal I: REMOVED — r3 variety (2/5 CV, not validated for VT)

    // --- Signal J: r1 bigram (3,3) — FLIPPED to -1 (4/5 CV, -0.06pp) ---
    for (int i = windowStart + 1; i < available; i++) {
        if (win[i-1].r1 == 3 && win[i].r1 == 3) {
            score -= 1;
            break;
        }
    }

    return score;
}

// ---------------------------------------------------------------------------
//  Profile cycling + persistence
// ---------------------------------------------------------------------------
- (void)cycleProfile {
    NSInteger next = ((NSInteger)self.thresholdProfile + 1) % SLThresholdProfileCount;
    self.thresholdProfile = (SLThresholdProfile)next;
    self.profileName = [self nameForProfile:self.thresholdProfile];

    [[NSUserDefaults standardUserDefaults] setInteger:next forKey:kSLDefaultsThreshProfile];

    // Recompute tier with new thresholds (using existing idx)
    if (self.lastR1Idx >= 0) {
        [self computeAllSignals];
    }

    NSLog(@"[SLIdxStrategy] Profile -> %@ (thresh MAX>=%d BIG>=%d)",
          self.profileName,
          [self maxThreshForProfile:self.thresholdProfile],
          [self bigThreshForProfile:self.thresholdProfile]);
}

- (NSString *)nameForProfile:(SLThresholdProfile)p {
    switch (p) {
        case SLThresholdProfileBalanced: return @"BAL";
        case SLThresholdProfileTight:    return @"TGT";
        case SLThresholdProfileUltra:    return @"ULT";
        case SLThresholdProfileSniper:   return @"SNP";
        default: return @"BAL";
    }
}

- (int)maxThreshForProfile:(SLThresholdProfile)p {
    switch (p) {
        case SLThresholdProfileBalanced: return 4;
        case SLThresholdProfileTight:    return 6;
        case SLThresholdProfileUltra:    return 8;
        case SLThresholdProfileSniper:   return 10;
        default: return 4;
    }
}

- (int)bigThreshForProfile:(SLThresholdProfile)p {
    switch (p) {
        case SLThresholdProfileBalanced: return 2;
        case SLThresholdProfileTight:    return 3;
        case SLThresholdProfileUltra:    return 4;
        case SLThresholdProfileSniper:   return 6;
        default: return 2;
    }
}

// ---------------------------------------------------------------------------
//  Scorer config cycling + persistence
// ---------------------------------------------------------------------------
- (void)cycleScorer {
    NSInteger next = ((NSInteger)self.scorerConfig + 1) % SLScorerConfigCount;
    self.scorerConfig = (SLScorerConfig)next;
    self.scorerName = [self nameForScorer:self.scorerConfig];

    [[NSUserDefaults standardUserDefaults] setInteger:next forKey:kSLDefaultsScorerConfig];

    // Recompute with new scorer (using existing idx)
    if (self.lastR1Idx >= 0) {
        [self computeAllSignals];
    }

    NSLog(@"[SLIdxStrategy] Scorer -> %@", self.scorerName);
}

- (NSString *)nameForScorer:(SLScorerConfig)s {
    switch (s) {
        case SLScorerConfigV1: return @"V1";
        case SLScorerConfigV2: return @"V2";
        default: return @"V1";
    }
}

// ---------------------------------------------------------------------------
//  ACC+SPINS V1 — 35 hits / 1107 spins (3.16%)
//  Original scorer from 62_per_type_signals.py
// ---------------------------------------------------------------------------
- (SLTypeHeat)scoreAccSpinsR1:(int32_t)r1 r2:(int32_t)r2 r3:(int32_t)r3 {
    int score = 0;
    int maxScore = 10;

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
//  ACC+SPINS V2 — 86 hits / 3864 spins (2.23%), merged Ahmed+Nick
//  Enhanced: 8.9 bets/hit at >=10, 5.1x lift, p=0.0001
//  + r3 signals, new pairs, dead pairs (n>=50), dead tuples
// ---------------------------------------------------------------------------
- (SLTypeHeat)scoreAccSpinsV2R1:(int32_t)r1 r2:(int32_t)r2 r3:(int32_t)r3 {
    int score = 0;
    int maxScore = 12;

    // --- Individual signals (lag-1) ---
    if (r2 == 7) score += 2;   // 5/5 CV, +1.11pp (star signal)
    if (r1 == 7) score += 1;   // 5/5 CV, +1.03pp
    if (r2 == 3) score += 1;   // 4/5 CV, +1.04pp
    if (r1 == 3) score += 1;   // 4/5 CV, +0.39pp
    if (r3 == 3) score += 1;   // 4/5 CV, +1.80pp
    if (r3 == 5) score += 1;   // 4/5 CV, +0.75pp
    if (r3 == 8) score += 1;   // 5/5 CV, +0.71pp

    // --- Negative signals ---
    if (r3 == 1) score -= 2;   // 5/5 CV, 3/480 (0.6%) — hard dead zone
    if (r2 == 5) score -= 2;   // 5/5 CV, 3/306 (1.0%) — strong negative
    if (r3 == 7) score -= 1;   // 4/5 CV, 1/118 (0.8%)
    if (r2 == 0) score -= 1;   // 5/5 CV
    if (r2 == 2) score -= 1;   // 4/5 CV
    if (r1 == 5) score -= 1;   // 4/5 CV
    if (r1 == 0) score -= 1;   // 4/5 CV

    // --- Pair bonuses ---
    if (r1 == 7 && r2 == 7) score += 2;   // 4/5 CV, 7/201, +1.26pp
    if (r1 == 7 && r3 == 8) score += 1;   // 4/5 CV, 13/309, +1.98pp
    if (r2 == 7 && r3 == 8) score += 1;   // 4/5 CV, 11/330, +1.11pp
    if (r1 == 3 && r2 == 7) score += 1;   // 4/5 CV, 9/279, +1.00pp
    if (r1 == 3 && r2 == 4) score += 1;   // kept from v1 (acc-specific)
    if (r1 == 7 && r2 == 3) score += 2;   // 5/5 CV, 10/238, +1.98pp
    if (r2 == 4 && r3 == 5) score += 1;   // 4/5 CV, 6/105, +3.49pp
    if (r2 == 3 && r3 == 8) score += 1;   // 4/5 CV, 14/375, +1.51pp
    if (r1 == 6 && r3 == 5) score += 1;   // 4/5 CV, 4/117, +1.19pp
    if (r1 == 3 && r3 == 0) score += 1;   // 4/5 CV, 9/332, +0.48pp

    // --- Dead pairs (n>=50, 0 hits) ---
    if (r1 == 4 && r2 == 4) score -= 2;   // 0/71
    if (r1 == 7 && r3 == 0) score -= 2;   // 0/60
    if (r1 == 4 && r3 == 4) score -= 1;   // 0/48
    if (r2 == 5 && r3 == 1) score -= 2;   // 0/105
    if (r1 == 1 && r3 == 1) score -= 1;   // 0/77
    if (r1 == 5 && r2 == 5) score -= 1;   // 0/70
    if (r2 == 3 && r3 == 7) score -= 1;   // 0/60
    if (r1 == 7 && r3 == 7) score -= 1;   // 0/57
    if (r2 == 6 && r3 == 1) score -= 1;   // 0/56
    if (r1 == 6 && r2 == 5) score -= 1;   // 0/53
    if (r1 == 5 && r3 == 1) score -= 1;   // 0/58

    // --- Dead tuples ---
    if (r1 == 4 && r2 == 4 && r3 == 4) score -= 2;   // 0/136 mega-dead
    if (r1 == 7 && r2 == 6 && r3 == 0) score -= 1;   // 0/86
    if (r1 == 6 && r2 == 4 && r3 == 1) score -= 1;   // 0/77
    if (r1 == 1 && r2 == 1 && r3 == 1) score -= 1;   // 0/58

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
