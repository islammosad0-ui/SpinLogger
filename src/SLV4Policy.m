#import "SLV4Policy.h"
#import "SLV4Model.h"
#import "SLV4Features.h"

// Mirror of `_dyn_aggr_threshold(t)` from tail_risk_v4_horizon_stack.py:31-39.
// Schedule is piecewise-constant on cycle-position t.
static double SLV4_DynAggrThreshold(int t) {
    if (t > 100) return 0.10;
    if (t >= 70) return 0.03;
    if (t >= 50) return 0.04;
    if (t >= 30) return 0.05;
    if (t >= 15) return 0.08;
    return 0.05;
}

// Cycle-position gate — policies are OFF outside this window.
static const int kWinLo = 15;
static const int kWinHi = 100;

@interface SLV4Policy () {
    SLV4PolicyState _state;
}
@end

@implementation SLV4Policy

+ (instancetype)shared {
    static SLV4Policy *inst;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ inst = [[self alloc] init]; });
    return inst;
}

- (instancetype)init {
    if (self = [super init]) {
        _activePolicy = SLV4PolicyK5Dyn;
    }
    return self;
}

- (SLV4PolicyState)evaluate {
    SLV4Model *m = [SLV4Model shared];
    SLV4Features *f = [SLV4Features shared];
    SLV4Snapshot snap = [f snapshot];

    double p3 = 0, p5 = 0, p10 = 0;
    if (m.isLoaded) {
        [m predict:[f currentFeatureVector] out:&p3 p5:&p5 p10:&p10];
    }

    int t = snap.t;
    BOOL windowOk = (t >= kWinLo && t <= kWinHi);

    double thr_dyn = SLV4_DynAggrThreshold(t);

    SLV4PolicyState s = {0};
    s.p3 = p3; s.p5 = p5; s.p10 = p10;
    s.t = t;
    s.activeKind = (int)self.activePolicy;

    // (1) K5 dyn_aggr
    s.thr[SLV4PolicyK5Dyn] = thr_dyn;
    s.on[SLV4PolicyK5Dyn] = windowOk && (p5 >= thr_dyn);

    // (2) Triple intersection: p3 >= .04 AND p5 >= .05 AND p10 >= .10
    s.thr[SLV4PolicyTriple] = 0.0;  // not a single threshold — leave 0 for display
    s.on[SLV4PolicyTriple] = windowOk && (p3 >= 0.04) && (p5 >= 0.05) && (p10 >= 0.10);

    // (3) K10 dyn_aggr
    s.thr[SLV4PolicyK10Dyn] = thr_dyn;
    s.on[SLV4PolicyK10Dyn] = windowOk && (p10 >= thr_dyn);

    int agree = 0;
    for (int i = 0; i < SLV4PolicyCount; i++) if (s.on[i]) agree++;
    s.agreement = agree;
    s.anyOn = (agree > 0) ? 1 : 0;

    if (s.on[self.activePolicy]) {
        [f notePolicyFire];
    }

    _state = s;
    return s;
}

- (SLV4PolicyState)currentState { return _state; }

+ (NSString *)nameForKind:(SLV4PolicyKind)kind {
    switch (kind) {
        case SLV4PolicyK5Dyn:  return @"K=5 dyn_aggr (champion)";
        case SLV4PolicyTriple: return @"K=3/5/10 intersection";
        case SLV4PolicyK10Dyn: return @"K=10 dyn_aggr (widest)";
        default: return @"?";
    }
}

+ (NSString *)shortNameForKind:(SLV4PolicyKind)kind {
    switch (kind) {
        case SLV4PolicyK5Dyn:  return @"K5";
        case SLV4PolicyTriple: return @"TRI";
        case SLV4PolicyK10Dyn: return @"K10";
        default: return @"?";
    }
}

@end
