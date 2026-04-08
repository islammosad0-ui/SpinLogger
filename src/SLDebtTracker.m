#import "SLDebtTracker.h"
#import <string.h>

// ============================================================================
//  SLDebtRule
// ============================================================================
@implementation SLDebtRule

+ (instancetype)ruleWithName:(NSString *)name bitIndex:(NSInteger)bitIndex {
    SLDebtRule *r = [[self alloc] init];
    r.name = name;
    r.bitIndex = bitIndex;
    r.spinThreshold = 999;  // disabled by default
    r.spinCap = 0;          // no cap by default
    r.rateGate = 0.0;
    r.spnRateGate = 0.0;
    r.minSlope = 0.0;
    r.slopeWindow = 10;
    r.quietZoneWindow = 0;
    r.quietZoneMax = 0;
    r.smlSBound = 0;
    r.smlSThreshold = 0;
    r.smlSGate = 0.0;
    r.smlLBound = 0;
    r.smlLThreshold = 0;
    r.smlLGate = 0.0;
    r.requiredPrevTriple = @"";
    r.requiredPrevClassMask = 0;
    return r;
}

@end

// ============================================================================
//  SLDebtTrackerConfig — preset factories
// ============================================================================
@implementation SLDebtTrackerConfig

- (instancetype)init {
    self = [super init];
    if (self) {
        _rules = [NSMutableArray array];
        _cooldownAfter = kSLDefaultCooldownAfter;
        _cooldownLen = kSLDefaultCooldownLen;
    }
    return self;
}

+ (instancetype)accCausalDefaults {
    // v5 DEFAULT — 7 rules from the real causal hunt (2026-04-08).
    // Verified: 45/271 @ ~28 mb/hit on 271-gap validation set.
    // See analysis/nuclear/NUCLEAR_FINDINGS.md "RECOMMENDED ENSEMBLE".
    SLDebtTrackerConfig *c = [[self alloc] init];

    // Rule 1 — STEAL t=65 g=0.34 (S-window precision): 4/271 @ 16.5 mb
    SLDebtRule *r1 = [SLDebtRule ruleWithName:@"STEAL t65 g0.34" bitIndex:0];
    r1.requiredPrevTriple = @"steal";
    r1.spinThreshold = 65;
    r1.spinCap = 105;   // S-window cap
    r1.rateGate = 0.34;
    [c.rules addObject:r1];

    // Rule 2 — STEAL t=130 g=0.28 (volume workhorse): 14/271 @ 15.0 mb
    SLDebtRule *r2 = [SLDebtRule ruleWithName:@"STEAL t130 g0.28" bitIndex:1];
    r2.requiredPrevTriple = @"steal";
    r2.spinThreshold = 130;
    r2.rateGate = 0.28;
    [c.rules addObject:r2];

    // Rule 3 — STEAL t=150 g=0.30 (L-window gem): 5/271 @ 6.2 mb, 17x lift
    SLDebtRule *r3 = [SLDebtRule ruleWithName:@"STEAL t150 g0.30" bitIndex:2];
    r3.requiredPrevTriple = @"steal";
    r3.spinThreshold = 150;
    r3.rateGate = 0.30;
    [c.rules addObject:r3];

    // Rule 4 — SHIELD t=150 g=0.30: 8/271 @ 18.4 mb
    SLDebtRule *r4 = [SLDebtRule ruleWithName:@"SHIELD t150 g0.30" bitIndex:3];
    r4.requiredPrevTriple = @"shield";
    r4.spinThreshold = 150;
    r4.rateGate = 0.30;
    [c.rules addObject:r4];

    // Rule 5 — Quiet-zone suppression: 7/271 @ 19.4 mb
    // The game reduces total symbol output in the ~10 spins before a triple.
    SLDebtRule *r5 = [SLDebtRule ruleWithName:@"Quiet-zone last10<=10 t130" bitIndex:4];
    r5.spinThreshold = 130;
    r5.quietZoneWindow = 10;
    r5.quietZoneMax = 10;
    [c.rules addObject:r5];

    // Rule 6 — Double-gate t=130 capped at 155 acc>=0.28 spn>=0.24
    // Capping at 155 avoids the long-gap bleed that pushes union mb/hit from ~18 to ~30.
    // Verified: capped DG adds 9 catches over precision-only at only +6 mb/hit overhead.
    SLDebtRule *r6 = [SLDebtRule ruleWithName:@"DG t130 cap155 acc0.28 spn0.24" bitIndex:5];
    r6.spinThreshold = 130;
    r6.spinCap = 155;
    r6.rateGate = 0.28;
    r6.spnRateGate = 0.24;
    [c.rules addObject:r6];

    // Rule 7 — Early S-window trigger (user's "predict S then fire" idea)
    // Only fires when prev gap was M or L (predicting next is S, 50-55% probability).
    // Window: sa_spins in [60..105] with quiet-zone suppression.
    // Causal: 4/271 @ 24.8 mb — Nick 1 @ 12 mb, Ahmed 2 @ 22 mb, Islam 1 @ 44 mb.
    SLDebtRule *r7 = [SLDebtRule ruleWithName:@"prev=M/L early S window supp<=10" bitIndex:6];
    r7.spinThreshold = 60;
    r7.spinCap = 105;
    r7.quietZoneWindow = 10;
    r7.quietZoneMax = 10;
    // requiredPrevClassMask: M=4, L=8 → 4|8=12
    r7.requiredPrevClassMask = (1 << SLGapClassM) | (1 << SLGapClassL);
    [c.rules addObject:r7];

    // Cooldown disabled for v5 — didn't help the real ensemble
    c.cooldownAfter = 0;
    c.cooldownLen = 0;

    return c;
}

+ (instancetype)accEnsembleDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];

    // Rule 1 — COMBO: t>=110, acc>=0.28, spn>=0.20, slope10>=0.010
    SLDebtRule *r1 = [SLDebtRule ruleWithName:@"COMBO" bitIndex:0];
    r1.spinThreshold = 110;
    r1.rateGate = 0.28;
    r1.spnRateGate = 0.20;
    r1.minSlope = 0.010;
    r1.slopeWindow = 10;
    [c.rules addObject:r1];

    // Rule 2 — Ideal RA: t>=110, acc>=0.30, slope8>=0.006
    SLDebtRule *r2 = [SLDebtRule ruleWithName:@"Ideal RA" bitIndex:1];
    r2.spinThreshold = 110;
    r2.rateGate = 0.30;
    r2.minSlope = 0.006;
    r2.slopeWindow = 8;
    [c.rules addObject:r2];

    // Rule 3 — RA t130: t>=130, acc>=0.28, slope10>=0.010
    SLDebtRule *r3 = [SLDebtRule ruleWithName:@"RA t130" bitIndex:2];
    r3.spinThreshold = 130;
    r3.rateGate = 0.28;
    r3.minSlope = 0.010;
    r3.slopeWindow = 10;
    [c.rules addObject:r3];

    // Rule 4 — FLAT 150/0.32
    SLDebtRule *r4 = [SLDebtRule ruleWithName:@"FLAT 150/0.32" bitIndex:3];
    r4.spinThreshold = 150;
    r4.rateGate = 0.32;
    [c.rules addObject:r4];

    // Rule 5 — SML L>=120 tL=130 g=0.32
    // Base disabled (999), L override active when prev_gap >= 120
    SLDebtRule *r5 = [SLDebtRule ruleWithName:@"SML L>=120 g=0.32" bitIndex:4];
    r5.spinThreshold = 999;
    r5.rateGate = 0.32;
    r5.smlLBound = 120;
    r5.smlLThreshold = 130;
    r5.smlLGate = 0.32;
    [c.rules addObject:r5];

    // Rule 6 — SML L>=120 tL=130 g=0.30
    SLDebtRule *r6 = [SLDebtRule ruleWithName:@"SML L>=120 g=0.30" bitIndex:5];
    r6.spinThreshold = 999;
    r6.rateGate = 0.30;
    r6.smlLBound = 120;
    r6.smlLThreshold = 130;
    r6.smlLGate = 0.30;
    [c.rules addObject:r6];

    // Rule 7 — SML S100 L120 tM=180 tL=130 g=0.32
    // S<100: t=150, M(100..120): t=180, L>=120: t=130
    SLDebtRule *r7 = [SLDebtRule ruleWithName:@"SML S100 L120 tM=180" bitIndex:6];
    r7.spinThreshold = 180;     // M bucket
    r7.rateGate = 0.32;
    r7.smlSBound = 100;
    r7.smlSThreshold = 150;
    r7.smlSGate = 0.32;
    r7.smlLBound = 120;
    r7.smlLThreshold = 130;
    r7.smlLGate = 0.32;
    [c.rules addObject:r7];

    // Rule 8 — SML S100 L120 tM=110 tL=130 g=0.32
    SLDebtRule *r8 = [SLDebtRule ruleWithName:@"SML S100 L120 tM=110" bitIndex:7];
    r8.spinThreshold = 110;
    r8.rateGate = 0.32;
    r8.smlSBound = 100;
    r8.smlSThreshold = 150;
    r8.smlSGate = 0.32;
    r8.smlLBound = 120;
    r8.smlLThreshold = 130;
    r8.smlLGate = 0.32;
    [c.rules addObject:r8];

    // Rule 9 — SML S100 L130 tM=130 tL=100 g=0.32
    SLDebtRule *r9 = [SLDebtRule ruleWithName:@"SML S100 L130 tM=130" bitIndex:8];
    r9.spinThreshold = 130;
    r9.rateGate = 0.32;
    r9.smlSBound = 100;
    r9.smlSThreshold = 150;
    r9.smlSGate = 0.32;
    r9.smlLBound = 130;
    r9.smlLThreshold = 100;
    r9.smlLGate = 0.32;
    [c.rules addObject:r9];

    // Rule 10 — SML S50 L130 tM=150 tL=100 g=0.32
    SLDebtRule *r10 = [SLDebtRule ruleWithName:@"SML S50 L130 tM=150" bitIndex:9];
    r10.spinThreshold = 150;
    r10.rateGate = 0.32;
    r10.smlSBound = 50;
    r10.smlSThreshold = 100;
    r10.smlSGate = 0.32;
    r10.smlLBound = 130;
    r10.smlLThreshold = 100;
    r10.smlLGate = 0.32;
    [c.rules addObject:r10];

    // Rule 11 — SML S50 L130 tS=80 tM=150 tL=100 g=0.32
    SLDebtRule *r11 = [SLDebtRule ruleWithName:@"SML S50 L130 tS=80" bitIndex:10];
    r11.spinThreshold = 150;
    r11.rateGate = 0.32;
    r11.smlSBound = 50;
    r11.smlSThreshold = 80;
    r11.smlSGate = 0.32;
    r11.smlLBound = 130;
    r11.smlLThreshold = 100;
    r11.smlLGate = 0.32;
    [c.rules addObject:r11];

    // Rule 12 — SHIELD-cond 110/0.32
    SLDebtRule *r12 = [SLDebtRule ruleWithName:@"SHIELD-cond 110/0.32" bitIndex:11];
    r12.spinThreshold = 110;
    r12.rateGate = 0.32;
    r12.requiredPrevTriple = @"shield";
    [c.rules addObject:r12];

    // Rule 13 — SHIELD-cond 120/0.32
    SLDebtRule *r13 = [SLDebtRule ruleWithName:@"SHIELD-cond 120/0.32" bitIndex:12];
    r13.spinThreshold = 120;
    r13.rateGate = 0.32;
    r13.requiredPrevTriple = @"shield";
    [c.rules addObject:r13];

    // Rule 14 — SHIELD-cond 130/0.32
    SLDebtRule *r14 = [SLDebtRule ruleWithName:@"SHIELD-cond 130/0.32" bitIndex:13];
    r14.spinThreshold = 130;
    r14.rateGate = 0.32;
    r14.requiredPrevTriple = @"shield";
    [c.rules addObject:r14];

    // Rule 15 — SHIELD-cond 140/0.32
    SLDebtRule *r15 = [SLDebtRule ruleWithName:@"SHIELD-cond 140/0.32" bitIndex:14];
    r15.spinThreshold = 140;
    r15.rateGate = 0.32;
    r15.requiredPrevTriple = @"shield";
    [c.rules addObject:r15];

    // Rule 16 — FLAT 150/0.37 (extreme precision: 1.3 mb/hit, 76x lift)
    SLDebtRule *r16 = [SLDebtRule ruleWithName:@"FLAT 150/0.37" bitIndex:15];
    r16.spinThreshold = 150;
    r16.rateGate = 0.37;
    [c.rules addObject:r16];

    return c;
}

+ (instancetype)accBaselineDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    SLDebtRule *r = [SLDebtRule ruleWithName:@"Baseline 130/0.30" bitIndex:0];
    r.spinThreshold = 130;
    r.rateGate = 0.30;
    [c.rules addObject:r];
    return c;
}

+ (instancetype)accComboOnlyDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    SLDebtRule *r = [SLDebtRule ruleWithName:@"COMBO" bitIndex:0];
    r.spinThreshold = 110;
    r.rateGate = 0.28;
    r.spnRateGate = 0.20;
    r.minSlope = 0.010;
    r.slopeWindow = 10;
    [c.rules addObject:r];
    return c;
}

+ (instancetype)spnDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    // SPN Sniper: ss_spins>=120 AND ss_spn/ss_spins>=0.25 (22/213, 9.5 mb/hit)
    SLDebtRule *r = [SLDebtRule ruleWithName:@"SPN Sniper 120/0.25" bitIndex:0];
    r.spinThreshold = 120;
    r.rateGate = 0.25;
    [c.rules addObject:r];
    // SPN doesn't need cooldown (single rule rarely fires consecutively that long)
    c.cooldownAfter = 0;
    c.cooldownLen = 0;
    return c;
}

@end

// ============================================================================
//  SLDebtTracker
// ============================================================================
@interface SLDebtTracker () {
    double _rateHistory[kSLSlopeWindowMax + 1];
    // Ring buffer of ALL-symbols delta per spin (for quiet-zone rule).
    // _allSymHistory[k] = total symbols (atk+stl+shd+spn+acc) landed on the k-th spin.
    // We store up to kSLQuietZoneMax+1 slots.
    NSInteger _allSymHistory[kSLQuietZoneMax + 1];
}
@property (nonatomic, assign, readwrite) NSInteger saSpins;
@property (nonatomic, assign, readwrite) NSInteger saSymbols;
@property (nonatomic, assign, readwrite) NSInteger saSpnSymbols;
@property (nonatomic, assign, readwrite) NSInteger prevGapLength;
@property (nonatomic, copy,   readwrite) NSString *prevRealTriple;
@property (nonatomic, assign, readwrite) SLGapClass prevGapClass;
@property (nonatomic, assign, readwrite) SLDebtPhase phase;
@property (nonatomic, assign, readwrite) NSInteger firingRuleCount;
@property (nonatomic, assign, readwrite) NSUInteger firingRuleBitmask;
@property (nonatomic, assign, readwrite) NSInteger consecBets;
@property (nonatomic, assign, readwrite) NSInteger cooldownRemaining;
@property (nonatomic, assign, readwrite) NSInteger gapBetCount;
@end

@implementation SLDebtTracker

- (instancetype)initWithConfig:(SLDebtTrackerConfig *)config {
    self = [super init];
    if (self) {
        _config = config;
        [self reset];
    }
    return self;
}

#pragma mark - State accessors

- (double)accumRate {
    if (self.saSpins == 0) return 0.0;
    return (double)self.saSymbols / (double)self.saSpins;
}

- (double)spnRate {
    if (self.saSpins == 0) return 0.0;
    return (double)self.saSpnSymbols / (double)self.saSpins;
}

- (double)slopeForWindow:(NSInteger)win {
    if (win <= 0 || win > kSLSlopeWindowMax) return 0.0;
    if (self.saSpins <= win) return 0.0;
    double rateNow = [self accumRate];
    double ratePrev = _rateHistory[(self.saSpins - win) % (kSLSlopeWindowMax + 1)];
    return rateNow - ratePrev;
}

- (NSInteger)symbolsInLastWindow:(NSInteger)N {
    if (N <= 0 || N > kSLQuietZoneMax) return -1;
    if (self.saSpins < N) return -1;  // not enough history
    NSInteger sum = 0;
    // _allSymHistory[k] was written on spin k (1..saSpins). We want last N spins.
    // So indices: saSpins - N + 1 .. saSpins
    for (NSInteger k = self.saSpins - N + 1; k <= self.saSpins; k++) {
        sum += _allSymHistory[k % (kSLQuietZoneMax + 1)];
    }
    return sum;
}

+ (SLGapClass)classifyGapLength:(NSInteger)length {
    if (length <= 0) return SLGapClassUnknown;
    if (length <= kSLGapXsMax)  return SLGapClassXS;
    if (length <= kSLGapSMax)   return SLGapClassS;
    if (length <= kSLGapMMax)   return SLGapClassM;
    return SLGapClassL;
}

+ (NSString *)classAbbreviation:(SLGapClass)cls {
    switch (cls) {
        case SLGapClassXS: return @"XS";
        case SLGapClassS:  return @"S";
        case SLGapClassM:  return @"M";
        case SLGapClassL:  return @"L";
        default:           return @"?";
    }
}

- (NSString *)predictedNextWindow {
    // Based on transition matrix from chunk 17 analysis:
    //   M -> S at 50% (M window size 106-160, S window 40-105)
    //   L -> S at 55% (L >160, S 40-105)
    //   S -> M at 45%
    //   XS -> M/L mixed
    switch (self.prevGapClass) {
        case SLGapClassM:  return @"S(50%)";
        case SLGapClassL:  return @"S(55%)";
        case SLGapClassS:  return @"M(45%)";
        case SLGapClassXS: return @"M/L";
        default:           return @"?";
    }
}

#pragma mark - Rule resolution

// Resolve a rule's effective threshold and gate based on current prev_gap_length context.
// Returns YES if the rule has any chance of firing for this gap (i.e., it's not blocked by
// a missing prev_real_triple or unreachable threshold).
- (BOOL)resolveRule:(SLDebtRule *)r threshold:(NSInteger *)outThresh gate:(double *)outGate {
    // Conditional: requires specific prev_real_triple
    if (r.requiredPrevTriple.length > 0) {
        if (!self.prevRealTriple || ![self.prevRealTriple isEqualToString:r.requiredPrevTriple]) {
            return NO;
        }
    }

    NSInteger thresh = r.spinThreshold;
    double    gate   = r.rateGate;

    // SML S-bucket override
    if (r.smlSBound > 0 && self.prevGapLength >= 0 && self.prevGapLength < r.smlSBound) {
        thresh = r.smlSThreshold;
        gate   = r.smlSGate;
    }
    // SML L-bucket override
    else if (r.smlLBound > 0 && self.prevGapLength >= 0 && self.prevGapLength >= r.smlLBound) {
        thresh = r.smlLThreshold;
        gate   = r.smlLGate;
    }

    if (thresh >= 999) return NO;  // unreachable

    if (outThresh) *outThresh = thresh;
    if (outGate)   *outGate   = gate;
    return YES;
}

- (BOOL)evaluateRule:(SLDebtRule *)r {
    NSInteger thresh; double gate;
    if (![self resolveRule:r threshold:&thresh gate:&gate]) return NO;

    // Prev-gap class condition: bitmask must include current prevGapClass
    if (r.requiredPrevClassMask > 0) {
        NSInteger classBit = 1 << (NSInteger)self.prevGapClass;
        if (!(r.requiredPrevClassMask & classBit)) return NO;
    }

    if (self.saSpins < thresh) return NO;
    // Spin cap: rule only fires if sa_spins <= cap (0 = no cap)
    if (r.spinCap > 0 && self.saSpins > r.spinCap) return NO;
    if (gate > 0.0 && [self accumRate] < gate) return NO;
    if (r.spnRateGate > 0.0 && [self spnRate] < r.spnRateGate) return NO;
    if (r.minSlope > 0.0 && [self slopeForWindow:r.slopeWindow] < r.minSlope) return NO;
    // Quiet-zone gate: total symbols in last-N spins must be <= max
    if (r.quietZoneWindow > 0) {
        NSInteger sum = [self symbolsInLastWindow:r.quietZoneWindow];
        if (sum < 0) return NO;  // not enough history yet
        if (sum > r.quietZoneMax) return NO;
    }
    return YES;
}

- (BOOL)isRuleSoon:(SLDebtRule *)r {
    NSInteger thresh; double gate;
    if (![self resolveRule:r threshold:&thresh gate:&gate]) return NO;

    // Within 25 spins of threshold AND rate at least 85% of gate
    if (self.saSpins < thresh - 25) return NO;
    if (gate > 0.0 && [self accumRate] < gate * 0.85) return NO;
    return YES;
}

- (NSInteger)minEffectiveThreshold {
    NSInteger best = NSIntegerMax;
    for (SLDebtRule *r in self.config.rules) {
        NSInteger thresh; double gate;
        if (![self resolveRule:r threshold:&thresh gate:&gate]) continue;
        if (thresh < best) best = thresh;
    }
    return (best == NSIntegerMax) ? 0 : best;
}

- (NSArray<SLDebtRule *> *)firingRules {
    NSMutableArray *out = [NSMutableArray array];
    for (SLDebtRule *r in self.config.rules) {
        if ([self evaluateRule:r]) [out addObject:r];
    }
    return out;
}

- (NSArray<SLDebtRule *> *)soonRules {
    NSMutableArray *out = [NSMutableArray array];
    for (SLDebtRule *r in self.config.rules) {
        if ([self evaluateRule:r]) continue;  // already firing
        if ([self isRuleSoon:r]) [out addObject:r];
    }
    return out;
}

- (NSArray<SLDebtRule *> *)dormantRules {
    NSMutableArray *out = [NSMutableArray array];
    for (SLDebtRule *r in self.config.rules) {
        if ([self evaluateRule:r]) continue;
        if ([self isRuleSoon:r]) continue;
        [out addObject:r];
    }
    return out;
}

#pragma mark - Spin processing

- (void)onSpin:(BOOL)isTarget
  realTripleType:(NSString *)realTripleType
        primary:(NSInteger)primary
      secondary:(NSInteger)secondary
  totalSymbols:(NSInteger)totalSymbols {

    self.saSpins++;
    self.saSymbols    += primary;
    self.saSpnSymbols += secondary;

    // Record current acc rate in circular buffer for slope computation
    // Buffer mod is kSLSlopeWindowMax+1, supports any window 1..20
    if (self.saSpins > 0) {
        _rateHistory[self.saSpins % (kSLSlopeWindowMax + 1)] =
            (double)self.saSymbols / (double)self.saSpins;
    }

    // Record total symbols on this spin for quiet-zone rule
    _allSymHistory[self.saSpins % (kSLQuietZoneMax + 1)] = totalSymbols;

    // ---- Update prev_real_triple if this spin was a non-target real triple ----
    // (target triples are handled in the reset block below)
    if (realTripleType && realTripleType.length > 0 && !isTarget) {
        self.prevRealTriple = realTripleType;
    }

    // ---- Cooldown decrements first (gates rule evaluation) ----
    BOOL inCooldown = (self.cooldownRemaining > 0);
    if (inCooldown) {
        self.cooldownRemaining--;
        self.consecBets = 0;
        self.firingRuleCount = 0;
        self.firingRuleBitmask = 0;
        self.phase = SLDebtPhaseRest;
    } else {
        // ---- Evaluate all rules (even on target spin — so the catch is recorded with rule firings) ----
        NSInteger nFiring = 0;
        NSUInteger bitmask = 0;
        for (SLDebtRule *r in self.config.rules) {
            if ([self evaluateRule:r]) {
                nFiring++;
                bitmask |= (1u << (NSUInteger)r.bitIndex);
            }
        }
        self.firingRuleCount = nFiring;
        self.firingRuleBitmask = bitmask;

        if (nFiring > 0) {
            // BET!
            self.consecBets++;
            self.gapBetCount++;
            self.phase = SLDebtPhaseBetNow;

            // Check cooldown trigger: if THIS bet pushes consec to >= cooldownAfter, start rest after this spin
            if (self.config.cooldownAfter > 0 && self.consecBets >= self.config.cooldownAfter) {
                self.cooldownRemaining = self.config.cooldownLen;
                // Note: consec stays at the threshold; will reset to 0 when cooldown decrements next spin
            }
        } else {
            self.consecBets = 0;
        }
    }

    // ---- Target triple? Save state then reset (AFTER rule evaluation) ----
    if (isTarget) {
        self.prevGapLength    = self.saSpins;
        self.prevGapClass     = [SLDebtTracker classifyGapLength:self.saSpins];
        self.prevRealTriple   = realTripleType;  // the target itself
        self.saSpins          = 0;
        self.saSymbols        = 0;
        self.saSpnSymbols     = 0;
        self.phase            = SLDebtPhaseWaiting;
        self.consecBets       = 0;
        self.cooldownRemaining = 0;
        self.gapBetCount      = 0;
        // Note: firingRuleCount and firingRuleBitmask are NOT reset here.
        // They reflect what fired on the catch spin (so the CSV logger records the catch correctly).
        // They'll be recomputed on the next spin.
        memset(_rateHistory, 0, sizeof(_rateHistory));
        memset(_allSymHistory, 0, sizeof(_allSymHistory));
        return;
    }

    // If a rule fired or we're in cooldown, we already set the phase above. Done.
    if (self.firingRuleCount > 0 || inCooldown) return;

    // ---- No rules firing, not in cooldown — determine WAIT / SOON / ALERT ----

    NSInteger minThresh = [self minEffectiveThreshold];

    // ALERT: at/above any rule's threshold but no rule firing (rate too low)
    if (minThresh > 0 && self.saSpins >= minThresh) {
        self.phase = SLDebtPhaseWatch;
        return;
    }

    // SOON: L-bucket pre-warm OR within 25 spins of threshold
    BOOL inLBucketPreWarm = NO;
    for (SLDebtRule *r in self.config.rules) {
        if (r.smlLBound > 0 && self.prevGapLength >= 0 && self.prevGapLength >= r.smlLBound) {
            // L-bucket gap. Show SOON early.
            if (self.saSpins >= 75) {
                inLBucketPreWarm = YES;
                break;
            }
        }
    }

    if (inLBucketPreWarm) {
        self.phase = SLDebtPhaseSoon;
        return;
    }

    // Generic SOON: any rule's threshold within 25 spins AND rate close to gate
    BOOL anyRuleSoon = NO;
    for (SLDebtRule *r in self.config.rules) {
        if ([self isRuleSoon:r]) { anyRuleSoon = YES; break; }
    }
    if (anyRuleSoon) {
        self.phase = SLDebtPhaseSoon;
        return;
    }

    self.phase = SLDebtPhaseWaiting;
}

#pragma mark - Reset & persistence

- (void)reset {
    self.saSpins = 0;
    self.saSymbols = 0;
    self.saSpnSymbols = 0;
    self.prevGapLength = -1;
    self.prevGapClass = SLGapClassUnknown;
    self.prevRealTriple = nil;
    self.phase = SLDebtPhaseWaiting;
    self.consecBets = 0;
    self.cooldownRemaining = 0;
    self.gapBetCount = 0;
    self.firingRuleCount = 0;
    self.firingRuleBitmask = 0;
    memset(_rateHistory, 0, sizeof(_rateHistory));
    memset(_allSymHistory, 0, sizeof(_allSymHistory));
}

- (NSDictionary *)stateDictionary {
    return @{
        @"saSpins":           @(self.saSpins),
        @"saSymbols":         @(self.saSymbols),
        @"saSpnSymbols":      @(self.saSpnSymbols),
        @"prevGapLength":     @(self.prevGapLength),
        @"prevGapClass":      @(self.prevGapClass),
        @"prevRealTriple":    self.prevRealTriple ?: @"",
        @"phase":             @(self.phase),
        @"consecBets":        @(self.consecBets),
        @"cooldownRemaining": @(self.cooldownRemaining),
        @"gapBetCount":       @(self.gapBetCount),
    };
}

- (void)restoreFromDictionary:(NSDictionary *)dict {
    if (!dict) return;
    self.saSpins           = [dict[@"saSpins"]           integerValue];
    self.saSymbols         = [dict[@"saSymbols"]         integerValue];
    self.saSpnSymbols      = [dict[@"saSpnSymbols"]      integerValue];
    self.prevGapClass      = (SLGapClass)[dict[@"prevGapClass"] integerValue];
    self.prevGapLength     = dict[@"prevGapLength"] ? [dict[@"prevGapLength"] integerValue] : -1;
    NSString *prt = dict[@"prevRealTriple"];
    self.prevRealTriple    = (prt.length > 0) ? prt : nil;
    self.phase             = (SLDebtPhase)[dict[@"phase"] integerValue];
    self.consecBets        = [dict[@"consecBets"]        integerValue];
    self.cooldownRemaining = [dict[@"cooldownRemaining"] integerValue];
    self.gapBetCount       = [dict[@"gapBetCount"]       integerValue];
}

@end
