#import "SLV4Features.h"
#import "SLV4Model.h"
#import <math.h>

// ---------------------------------------------------------------------------
//  Identifying triples + event labels from a spin
//
//  The CSV pipeline uses columns `is_triple`, `reel_1/2/3`, `spin_result`.
//  Live, we have SLSpinResult with reel1/2/3 strings. A "real" triple is
//  three identical value-bearing reels — the Python code treats coin/goldsack
//  reel matches as *cosmetic* triples (is_triple == false, but they still
//  bump `cum_coin_triple` / `cum_gs_triple`).
//
//  Mapping:
//    reel1 == reel2 == reel3 → triple of that symbol
//      "accumulation" → ACC (is_acc, is_vt, is_triple, "T_ACC")
//      "spins"        → SPN (is_spn, is_vt, is_triple, "T_SPN")
//      "attack"       → T_attack (cooldown event, is_triple)
//      "shield"       → T_shield (cooldown event, is_triple)
//      "steal"        → T_steal (cooldown event, is_triple)
//      "coin"         → TRIPLE_COIN (cosmetic — NOT is_triple)
//      "goldsack"     → TRIPLE_GOLDSACK (cosmetic — NOT is_triple)
//      anything else  → treat as MIXED / OTHER
// ---------------------------------------------------------------------------

typedef enum {
    SLV4EventNone = 0,
    SLV4EventACC,          // accumulation triple
    SLV4EventSPN,          // spins triple
    SLV4EventAttack,       // attack triple (cooldown)
    SLV4EventShield,       // shield triple (cooldown)
    SLV4EventSteal,        // steal triple  (cooldown)
    SLV4EventCoinTriple,   // cosmetic coin reel-match
    SLV4EventGSTriple,     // cosmetic goldsack reel-match
} SLV4EventKind;

// Tuple categories — MUST match TUPLE_CATS in Python:
//   0 TRIPLE_ACCUMULATION, 1 TRIPLE_SPINS, 2 TRIPLE_ATTACK, 3 TRIPLE_SHIELD,
//   4 TRIPLE_STEAL, 5 TRIPLE_COIN, 6 TRIPLE_GOLDSACK,
//   7 PAIR_ACCUMULATION, 8 PAIR_SPINS, 9 PAIR_ATTACK, 10 PAIR_SHIELD,
//   11 PAIR_STEAL, 12 PAIR_COIN, 13 PAIR_GOLDSACK,
//   14 MIXED, 15 OTHER
static int SLV4_TupleCatId(NSString *r1, NSString *r2, NSString *r3) {
    if (!r1) r1 = @"";
    if (!r2) r2 = @"";
    if (!r3) r3 = @"";

    if ([r1 isEqualToString:r2] && [r2 isEqualToString:r3] && r1.length > 0) {
        NSString *u = [r1 uppercaseString];
        if ([u isEqualToString:@"ACCUMULATION"]) return 0;
        if ([u isEqualToString:@"SPINS"])        return 1;
        if ([u isEqualToString:@"ATTACK"])       return 2;
        if ([u isEqualToString:@"SHIELD"])       return 3;
        if ([u isEqualToString:@"STEAL"])        return 4;
        if ([u isEqualToString:@"COIN"])         return 5;
        if ([u isEqualToString:@"GOLDSACK"])     return 6;
        return 15; // OTHER
    }

    NSString *pair = nil;
    if ([r1 isEqualToString:r2] && r1.length > 0) pair = r1;
    else if ([r2 isEqualToString:r3] && r2.length > 0) pair = r2;
    else if ([r1 isEqualToString:r3] && r1.length > 0) pair = r1;

    if (pair) {
        NSString *u = [pair uppercaseString];
        if ([u isEqualToString:@"ACCUMULATION"]) return 7;
        if ([u isEqualToString:@"SPINS"])        return 8;
        if ([u isEqualToString:@"ATTACK"])       return 9;
        if ([u isEqualToString:@"SHIELD"])       return 10;
        if ([u isEqualToString:@"STEAL"])        return 11;
        if ([u isEqualToString:@"COIN"])         return 12;
        if ([u isEqualToString:@"GOLDSACK"])     return 13;
        return 15;
    }
    return 14; // MIXED
}

static SLV4EventKind SLV4_EventFromSpin(SLSpinResult *s) {
    NSString *r1 = s.reel1 ?: @"";
    NSString *r2 = s.reel2 ?: @"";
    NSString *r3 = s.reel3 ?: @"";
    if (!([r1 isEqualToString:r2] && [r2 isEqualToString:r3] && r1.length > 0)) {
        return SLV4EventNone;
    }
    NSString *u = [r1 uppercaseString];
    if ([u isEqualToString:@"ACCUMULATION"]) return SLV4EventACC;
    if ([u isEqualToString:@"SPINS"])        return SLV4EventSPN;
    if ([u isEqualToString:@"ATTACK"])       return SLV4EventAttack;
    if ([u isEqualToString:@"SHIELD"])       return SLV4EventShield;
    if ([u isEqualToString:@"STEAL"])        return SLV4EventSteal;
    if ([u isEqualToString:@"COIN"])         return SLV4EventCoinTriple;
    if ([u isEqualToString:@"GOLDSACK"])     return SLV4EventGSTriple;
    return SLV4EventNone;
}

// ---------------------------------------------------------------------------

// Session-level VT gap stream (both ACC and SPN combined — and the two
// individual streams — used for carry lag features at cycle start).
@interface SLV4GapStream : NSObject
@property (nonatomic, strong) NSMutableArray<NSNumber *> *gaps;  // array of last few gap values
@property (nonatomic, assign) long lastSeq;                      // seq of last event (-1 if none)
@end

@implementation SLV4GapStream
- (instancetype)init {
    if (self = [super init]) {
        _gaps = [NSMutableArray array];
        _lastSeq = -1;
    }
    return self;
}
- (void)observeSeq:(long)seq {
    if (_lastSeq >= 0) {
        [_gaps addObject:@((double)(seq - _lastSeq))];
        if (_gaps.count > 8) [_gaps removeObjectAtIndex:0];
    }
    _lastSeq = seq;
}
- (double)lagAt:(int)n {  // 1-based; returns NaN if unavailable
    if ((int)_gaps.count < n) return NAN;
    return _gaps[_gaps.count - n].doubleValue;
}
- (double)mean3 {
    double sum = 0.0; int cnt = 0;
    for (int k = 1; k <= 3; k++) {
        double v = [self lagAt:k];
        if (!isnan(v)) { sum += v; cnt++; }
    }
    return cnt ? (sum / cnt) : NAN;
}
- (double)std3 {
    double m = [self mean3];
    if (isnan(m)) return NAN;
    double sq = 0.0; int cnt = 0;
    for (int k = 1; k <= 3; k++) {
        double v = [self lagAt:k];
        if (!isnan(v)) { double d = v - m; sq += d * d; cnt++; }
    }
    return cnt >= 2 ? sqrt(sq / cnt) : NAN;
}
@end

// ---------------------------------------------------------------------------

@interface SLV4Features () {
    // Stable storage for the emitted vector (reallocated on model-load).
    double *_feat;
    int _featCount;

    // Current-cycle state (reset on each VT close).
    int _t;                          // spins into current cycle (pre-spin)
    int _cumAny, _cumAcc, _cumSpn, _cumAtk, _cumShd, _cumStl;
    int _cumCoinTriple, _cumGSTriple;
    int _lastAnyOffset, _lastRealOffset;  // <0 if never
    int _lastAccOffset, _lastSpnOffset;
    int _lastAtkOffset, _lastShdOffset, _lastStlOffset;
    int _lastCoinTripleOffset, _lastGsTripleOffset;
    int _lastCooldownOffset;

    // Rolling trailing-window buffers — booleans stored as ints (0/1)
    // sized to max window (10)
    int _trWinLen;
    int _trWinHead;
    int _trTripleRing[10];
    int _trCoolRing[10];

    // Reel-dup streak
    NSString *_prevR1, *_prevR2, *_prevR3;
    int _dupStreak;

    // Tuple-category lag history within cycle (up to 3)
    int _catLag1, _catLag2, _catLag3;

    // Fires in current cycle
    int _firesInCycle;

    // 1-based cycle index
    int _cycleIndex;

    // Session-level prev_vt_type — "ACC" / "SPN" / "UNK" (unknown before 1st VT)
    NSString *_prevVtType;

    // Session-level gap lag streams
    SLV4GapStream *_accStream;
    SLV4GapStream *_spnStream;
    SLV4GapStream *_vtStream;

    // Index lookup of feature column name → slot in _feat (built on load)
    NSDictionary<NSString *, NSNumber *> *_featIndex;

    // Precomputed slot indices (-1 if missing)
    int _ixT;
    int _ixCumAny, _ixCumAcc, _ixCumSpn, _ixCumAtk, _ixCumShd, _ixCumStl;
    int _ixCumCoin, _ixCumGs;
    int _ixLastAny, _ixLastReal, _ixLastAcc, _ixLastSpn;
    int _ixLastAtk, _ixLastShd, _ixLastStl, _ixLastCoin, _ixLastGs;
    int _ixCooldownAge, _ixDensity5, _ixDensity10, _ixCool5, _ixCool10;
    int _ixDupLast, _ixDupStreak;
    int _ixCurCat, _ixCatLag1, _ixCatLag2, _ixCatLag3;
    int _ixAccLag1, _ixAccLag2, _ixAccLag3, _ixAccLag4;
    int _ixSpnLag1, _ixSpnLag2, _ixSpnLag3, _ixSpnLag4;
    int _ixVtLag1, _ixVtLag2, _ixVtLag3, _ixVtLag4;
    int _ixAccMean3, _ixAccStd3, _ixSpnMean3, _ixSpnStd3, _ixVtMean3, _ixVtStd3;
    int _ixPvtACC, _ixPvtSPN, _ixPvtUNK;

    // For carry features (only recomputed at cycle start and held throughout)
    double _carryAccLag1, _carryAccLag2, _carryAccLag3, _carryAccLag4;
    double _carrySpnLag1, _carrySpnLag2, _carrySpnLag3, _carrySpnLag4;
    double _carryVtLag1, _carryVtLag2, _carryVtLag3, _carryVtLag4;
    double _carryAccMean3, _carryAccStd3;
    double _carrySpnMean3, _carrySpnStd3;
    double _carryVtMean3, _carryVtStd3;

    dispatch_queue_t _q;
}
@end

static int IDX(NSDictionary *idx, NSString *k) {
    NSNumber *v = idx[k];
    return v ? v.intValue : -1;
}

@implementation SLV4Features

+ (instancetype)shared {
    static SLV4Features *inst;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ inst = [[self alloc] init]; });
    return inst;
}

- (instancetype)init {
    if (self = [super init]) {
        _q = dispatch_queue_create("com.spinlogger.v4features", DISPATCH_QUEUE_SERIAL);
        [self reset];
    }
    return self;
}

- (void)_ensureBufferBound {
    SLV4Model *m = [SLV4Model shared];
    if (!m.isLoaded) return;
    int n = m.featureCount;
    if (_featCount == n && _feat && _featIndex) return;

    if (_feat) free(_feat);
    _feat = (double *)calloc(n, sizeof(double));
    _featCount = n;

    NSMutableDictionary *idx = [NSMutableDictionary dictionary];
    for (int i = 0; i < (int)m.featureCols.count; i++) {
        idx[m.featureCols[i]] = @(i);
    }
    _featIndex = idx;

    _ixT            = IDX(idx, @"t");
    _ixCumAny       = IDX(idx, @"cum_any_triples");
    _ixCumAcc       = IDX(idx, @"cum_acc_triples");
    _ixCumSpn       = IDX(idx, @"cum_spn_triples");
    _ixCumAtk       = IDX(idx, @"cum_atk_triples");
    _ixCumShd       = IDX(idx, @"cum_shd_triples");
    _ixCumStl       = IDX(idx, @"cum_stl_triples");
    _ixCumCoin      = IDX(idx, @"cum_coin_triple");
    _ixCumGs        = IDX(idx, @"cum_gs_triple");
    _ixLastAny      = IDX(idx, @"last_any_triple_gap");
    _ixLastReal     = IDX(idx, @"last_real_triple_gap");
    _ixLastAcc      = IDX(idx, @"last_acc_triple_gap");
    _ixLastSpn      = IDX(idx, @"last_spn_triple_gap");
    _ixLastAtk      = IDX(idx, @"last_atk_triple_gap");
    _ixLastShd      = IDX(idx, @"last_shd_triple_gap");
    _ixLastStl      = IDX(idx, @"last_stl_triple_gap");
    _ixLastCoin     = IDX(idx, @"last_coin_triple_gap");
    _ixLastGs       = IDX(idx, @"last_gs_triple_gap");
    _ixCooldownAge  = IDX(idx, @"cooldown_age");
    _ixDensity5     = IDX(idx, @"density_any_last5");
    _ixDensity10    = IDX(idx, @"density_any_last10");
    _ixCool5        = IDX(idx, @"cooldown_last5");
    _ixCool10       = IDX(idx, @"cooldown_last10");
    _ixDupLast      = IDX(idx, @"reel_dup_last");
    _ixDupStreak    = IDX(idx, @"reel_dup_streak");
    _ixCurCat       = IDX(idx, @"cur_cat_id");
    _ixCatLag1      = IDX(idx, @"cat_lag1");
    _ixCatLag2      = IDX(idx, @"cat_lag2");
    _ixCatLag3      = IDX(idx, @"cat_lag3");
    _ixAccLag1      = IDX(idx, @"acc_gap_lag1");
    _ixAccLag2      = IDX(idx, @"acc_gap_lag2");
    _ixAccLag3      = IDX(idx, @"acc_gap_lag3");
    _ixAccLag4      = IDX(idx, @"acc_gap_lag4");
    _ixSpnLag1      = IDX(idx, @"spn_gap_lag1");
    _ixSpnLag2      = IDX(idx, @"spn_gap_lag2");
    _ixSpnLag3      = IDX(idx, @"spn_gap_lag3");
    _ixSpnLag4      = IDX(idx, @"spn_gap_lag4");
    _ixVtLag1       = IDX(idx, @"vt_gap_lag1");
    _ixVtLag2       = IDX(idx, @"vt_gap_lag2");
    _ixVtLag3       = IDX(idx, @"vt_gap_lag3");
    _ixVtLag4       = IDX(idx, @"vt_gap_lag4");
    _ixAccMean3     = IDX(idx, @"acc_gap_mean3");
    _ixAccStd3      = IDX(idx, @"acc_gap_std3");
    _ixSpnMean3     = IDX(idx, @"spn_gap_mean3");
    _ixSpnStd3      = IDX(idx, @"spn_gap_std3");
    _ixVtMean3      = IDX(idx, @"vt_gap_mean3");
    _ixVtStd3       = IDX(idx, @"vt_gap_std3");
    _ixPvtACC       = IDX(idx, @"pvt_ACC");
    _ixPvtSPN       = IDX(idx, @"pvt_SPN");
    _ixPvtUNK       = IDX(idx, @"pvt_UNK");
}

- (void)reset {
    dispatch_async(_q, ^{
        [self _resetCycleLocked];
        self->_prevVtType = @"UNK";
        self->_accStream = [[SLV4GapStream alloc] init];
        self->_spnStream = [[SLV4GapStream alloc] init];
        self->_vtStream = [[SLV4GapStream alloc] init];
        self->_cycleIndex = 0;
        [self _freezeCarryLocked];
        [self _emitFeaturesLocked];
    });
}

- (void)_resetCycleLocked {
    _t = 0;
    _cumAny = _cumAcc = _cumSpn = _cumAtk = _cumShd = _cumStl = 0;
    _cumCoinTriple = _cumGSTriple = 0;
    _lastAnyOffset = _lastRealOffset = -1;
    _lastAccOffset = _lastSpnOffset = -1;
    _lastAtkOffset = _lastShdOffset = _lastStlOffset = -1;
    _lastCoinTripleOffset = _lastGsTripleOffset = -1;
    _lastCooldownOffset = -1;
    _trWinLen = 0; _trWinHead = 0;
    for (int i = 0; i < 10; i++) { _trTripleRing[i] = 0; _trCoolRing[i] = 0; }
    _prevR1 = _prevR2 = _prevR3 = nil;
    _dupStreak = 0;
    _catLag1 = _catLag2 = _catLag3 = -1;
    _firesInCycle = 0;
}

- (void)_freezeCarryLocked {
    _carryAccLag1 = [_accStream lagAt:1];
    _carryAccLag2 = [_accStream lagAt:2];
    _carryAccLag3 = [_accStream lagAt:3];
    _carryAccLag4 = [_accStream lagAt:4];
    _carrySpnLag1 = [_spnStream lagAt:1];
    _carrySpnLag2 = [_spnStream lagAt:2];
    _carrySpnLag3 = [_spnStream lagAt:3];
    _carrySpnLag4 = [_spnStream lagAt:4];
    _carryVtLag1 = [_vtStream lagAt:1];
    _carryVtLag2 = [_vtStream lagAt:2];
    _carryVtLag3 = [_vtStream lagAt:3];
    _carryVtLag4 = [_vtStream lagAt:4];
    _carryAccMean3 = [_accStream mean3]; _carryAccStd3 = [_accStream std3];
    _carrySpnMean3 = [_spnStream mean3]; _carrySpnStd3 = [_spnStream std3];
    _carryVtMean3 = [_vtStream mean3]; _carryVtStd3 = [_vtStream std3];
}

// Write one double into the vector at slot i, guarding index -1.
static inline void W(double *v, int i, double x) {
    if (i >= 0) v[i] = x;
}

- (double)_trailingSum:(int *)ring window:(int)window {
    if (window > _trWinLen) window = _trWinLen;
    int sum = 0;
    // The ring stores up to the last _trWinLen spins; newest at (head-1).
    for (int i = 1; i <= window; i++) {
        int idx = (_trWinHead - i + 10) % 10;
        sum += ring[idx];
    }
    return (double)sum;
}

- (void)_pushTrailingTriple:(int)isTrip cool:(int)isCool {
    _trTripleRing[_trWinHead] = isTrip;
    _trCoolRing[_trWinHead] = isCool;
    _trWinHead = (_trWinHead + 1) % 10;
    if (_trWinLen < 10) _trWinLen++;
}

- (int)_curCatForNextSpin {
    return -1;  // unknown before spin resolves; training uses the SAME row's cat
                // but that's not observable pre-spin — we set -1 and the model
                // handles via default_left. Keep for clarity.
}

// Emit feature vector representing PRE-SPIN state AS OF NOW.
- (void)_emitFeaturesLocked {
    [self _ensureBufferBound];
    if (_featCount == 0 || !_feat) return;

    for (int i = 0; i < _featCount; i++) _feat[i] = NAN;

    W(_feat, _ixT, (double)_t);

    W(_feat, _ixCumAny, (double)_cumAny);
    W(_feat, _ixCumAcc, (double)_cumAcc);
    W(_feat, _ixCumSpn, (double)_cumSpn);
    W(_feat, _ixCumAtk, (double)_cumAtk);
    W(_feat, _ixCumShd, (double)_cumShd);
    W(_feat, _ixCumStl, (double)_cumStl);
    W(_feat, _ixCumCoin, (double)_cumCoinTriple);
    W(_feat, _ixCumGs, (double)_cumGSTriple);

    #define SET_GAP(ix, off) W(_feat, (ix), (off) >= 0 ? (double)(_t - (off)) : NAN)
    SET_GAP(_ixLastAny,  _lastAnyOffset);
    SET_GAP(_ixLastReal, _lastRealOffset);
    SET_GAP(_ixLastAcc,  _lastAccOffset);
    SET_GAP(_ixLastSpn,  _lastSpnOffset);
    SET_GAP(_ixLastAtk,  _lastAtkOffset);
    SET_GAP(_ixLastShd,  _lastShdOffset);
    SET_GAP(_ixLastStl,  _lastStlOffset);
    SET_GAP(_ixLastCoin, _lastCoinTripleOffset);
    SET_GAP(_ixLastGs,   _lastGsTripleOffset);
    SET_GAP(_ixCooldownAge, _lastCooldownOffset);
    #undef SET_GAP

    double d5 = [self _trailingSum:_trTripleRing window:5];
    double d10 = [self _trailingSum:_trTripleRing window:10];
    double c5 = [self _trailingSum:_trCoolRing window:5];
    double c10 = [self _trailingSum:_trCoolRing window:10];
    W(_feat, _ixDensity5, d5);
    W(_feat, _ixDensity10, d10);
    W(_feat, _ixCool5, c5);
    W(_feat, _ixCool10, c10);

    // reel_dup_last / streak describe the CURRENT spin's reels vs previous —
    // we don't know the current reels pre-spin, so default these to 0/0.
    // This is a small drift from training (where the feature uses the same
    // row's tuple) — accepted.
    W(_feat, _ixDupLast, 0.0);
    W(_feat, _ixDupStreak, (double)_dupStreak);

    // cur_cat_id is also a same-row feature → NaN pre-spin, default_left route.
    W(_feat, _ixCurCat, (double)[self _curCatForNextSpin]);
    W(_feat, _ixCatLag1, (double)_catLag1);
    W(_feat, _ixCatLag2, (double)_catLag2);
    W(_feat, _ixCatLag3, (double)_catLag3);

    W(_feat, _ixAccLag1, _carryAccLag1);
    W(_feat, _ixAccLag2, _carryAccLag2);
    W(_feat, _ixAccLag3, _carryAccLag3);
    W(_feat, _ixAccLag4, _carryAccLag4);
    W(_feat, _ixSpnLag1, _carrySpnLag1);
    W(_feat, _ixSpnLag2, _carrySpnLag2);
    W(_feat, _ixSpnLag3, _carrySpnLag3);
    W(_feat, _ixSpnLag4, _carrySpnLag4);
    W(_feat, _ixVtLag1, _carryVtLag1);
    W(_feat, _ixVtLag2, _carryVtLag2);
    W(_feat, _ixVtLag3, _carryVtLag3);
    W(_feat, _ixVtLag4, _carryVtLag4);
    W(_feat, _ixAccMean3, _carryAccMean3);
    W(_feat, _ixAccStd3, _carryAccStd3);
    W(_feat, _ixSpnMean3, _carrySpnMean3);
    W(_feat, _ixSpnStd3, _carrySpnStd3);
    W(_feat, _ixVtMean3, _carryVtMean3);
    W(_feat, _ixVtStd3, _carryVtStd3);

    int acc = [_prevVtType isEqualToString:@"ACC"] ? 1 : 0;
    int spn = [_prevVtType isEqualToString:@"SPN"] ? 1 : 0;
    int unk = (!acc && !spn) ? 1 : 0;
    W(_feat, _ixPvtACC, (double)acc);
    W(_feat, _ixPvtSPN, (double)spn);
    W(_feat, _ixPvtUNK, (double)unk);
}

- (void)feedSpin:(SLSpinResult *)spin {
    if (!spin) return;
    // Copy fields — we don't retain the SLSpinResult on the queue.
    NSString *r1 = spin.reel1 ? [spin.reel1 copy] : @"";
    NSString *r2 = spin.reel2 ? [spin.reel2 copy] : @"";
    NSString *r3 = spin.reel3 ? [spin.reel3 copy] : @"";
    long seq = (long)spin.seq;
    SLV4EventKind ev = SLV4_EventFromSpin(spin);
    int cat = SLV4_TupleCatId(r1, r2, r3);
    int isTriple = (ev == SLV4EventACC || ev == SLV4EventSPN
                    || ev == SLV4EventAttack || ev == SLV4EventShield
                    || ev == SLV4EventSteal) ? 1 : 0;
    int isCool = (ev == SLV4EventAttack || ev == SLV4EventShield
                  || ev == SLV4EventSteal) ? 1 : 0;
    int isVt = (ev == SLV4EventACC || ev == SLV4EventSPN) ? 1 : 0;

    dispatch_async(_q, ^{
        // reel_dup for the CURRENT spin vs previous
        BOOL dup = self->_prevR1 != nil
                    && [self->_prevR1 isEqualToString:r1]
                    && [self->_prevR2 isEqualToString:r2]
                    && [self->_prevR3 isEqualToString:r3];
        if (dup) self->_dupStreak++; else self->_dupStreak = 0;
        self->_prevR1 = r1; self->_prevR2 = r2; self->_prevR3 = r3;

        // Update cat-lag history (shift)
        self->_catLag3 = self->_catLag2;
        self->_catLag2 = self->_catLag1;
        self->_catLag1 = cat;

        // Update trailing-window ring (CURRENT spin joins the window)
        [self _pushTrailingTriple:isTriple cool:isCool];

        // Update cumulative + last-seen offsets AFTER emitting this spin's
        // features would have. Here we're updating post-spin-resolve, which
        // represents the NEXT spin's pre-state.
        if (isCool) self->_lastCooldownOffset = self->_t;
        if (isTriple) {
            self->_cumAny++;
            self->_lastAnyOffset = self->_t;
            self->_lastRealOffset = self->_t;
            switch (ev) {
                case SLV4EventACC:    self->_cumAcc++; self->_lastAccOffset = self->_t; break;
                case SLV4EventSPN:    self->_cumSpn++; self->_lastSpnOffset = self->_t; break;
                case SLV4EventAttack: self->_cumAtk++; self->_lastAtkOffset = self->_t; break;
                case SLV4EventShield: self->_cumShd++; self->_lastShdOffset = self->_t; break;
                case SLV4EventSteal:  self->_cumStl++; self->_lastStlOffset = self->_t; break;
                default: break;
            }
        }
        if (ev == SLV4EventCoinTriple) {
            self->_cumCoinTriple++;
            self->_lastCoinTripleOffset = self->_t;
        } else if (ev == SLV4EventGSTriple) {
            self->_cumGSTriple++;
            self->_lastGsTripleOffset = self->_t;
        }

        // If this was a VT, close the cycle and start a new one.
        if (isVt) {
            // Session gap streams
            [self->_vtStream observeSeq:seq];
            if (ev == SLV4EventACC) [self->_accStream observeSeq:seq];
            else                    [self->_spnStream observeSeq:seq];

            self->_prevVtType = (ev == SLV4EventACC) ? @"ACC" : @"SPN";
            [self _resetCycleLocked];
            self->_cycleIndex++;
            [self _freezeCarryLocked];
        } else {
            // Normal spin — advance cycle position
            self->_t++;
        }

        [self _emitFeaturesLocked];
    });
}

- (const double *)currentFeatureVector {
    [self _ensureBufferBound];
    return _feat;
}

- (SLV4Snapshot)snapshot {
    __block SLV4Snapshot snap = {0};
    dispatch_sync(_q, ^{
        snap.t = self->_t;
        snap.firesInCycle = self->_firesInCycle;
        snap.cumAnyInCycle = self->_cumAny;
        snap.cycleIndex = self->_cycleIndex;
        if ([self->_prevVtType isEqualToString:@"ACC"]) snap.prevVt = SLV4PrevVtACC;
        else if ([self->_prevVtType isEqualToString:@"SPN"]) snap.prevVt = SLV4PrevVtSPN;
        else snap.prevVt = SLV4PrevVtUnknown;
    });
    return snap;
}

- (void)notePolicyFire {
    dispatch_async(_q, ^{ self->_firesInCycle++; });
}

- (void)dealloc {
    if (_feat) free(_feat);
}

@end
