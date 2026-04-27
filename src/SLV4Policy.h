#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLV4Policy
//
//  Evaluates the three V4 policy configs on the latest p_acc_next3/5/10
//  predictions. All three use the dyn_aggr threshold schedule + a [15, 100]
//  cycle-position window. The schedule is per-account and loaded from
//  dyn_aggr_schedules.json (alongside v4_model.json); pooled fallback if
//  the file is missing or the active account isn't in the bundle.
//
//    (1) K5_DYN  — p5 >= dyn_aggr_thr(t)                (champion)
//    (2) TRIPLE  — p3 >= 0.04 AND p5 >= 0.05 AND p10 >= 0.10
//    (3) K10_DYN — p10 >= dyn_aggr_thr(t)               (widest net)
//
//  Shared gate for all three: 15 <= t <= 100. Outside that window every
//  policy reports "off" regardless of the raw model output.
// ---------------------------------------------------------------------------

typedef NS_ENUM(NSInteger, SLV4PolicyKind) {
    SLV4PolicyK5Dyn = 0,     // champion
    SLV4PolicyTriple,        // high-conviction intersection
    SLV4PolicyK10Dyn,        // wide-net long horizon
    SLV4PolicyCount,
};

typedef struct {
    BOOL on[SLV4PolicyCount];   // fire state per policy
    double thr[SLV4PolicyCount];// active threshold per policy (dyn_aggr_thr(t))
    double p3;                   // latest p_acc_next3
    double p5;                   // latest p_acc_next5
    double p10;                  // latest p_acc_next10
    int t;                       // cycle position at evaluation
    int activeKind;              // which policy the user picked as driver
    int anyOn;                   // 1 if any of the three fired
    int agreement;               // how many of the three agree (0-3)
} SLV4PolicyState;

@interface SLV4Policy : NSObject

+ (instancetype)shared;

/// Run all three policies using the latest SLV4Features vector + SLV4Model.
/// Records the new state internally. Returns the fresh state by value.
/// Also notifies SLV4FeaturesnotePolicyFire for the active policy if it fired.
- (SLV4PolicyState)evaluate;

/// Last computed state (read without triggering evaluation).
- (SLV4PolicyState)currentState;

/// Predictor head used for the current account ("ACC" or "ANY_VT").
/// Reads from dyn_aggr_schedules.json; defaults to "ACC" if not configured.
- (NSString *)activeHeadName;

/// Active schedule mode for the current account: "bundled" or "tuned".
/// Reads NSUserDefaults override first, then default_mode from JSON.
- (NSString *)activeModeName;

/// Toggle between "bundled" and "tuned" for the current account. The choice is
/// persisted in NSUserDefaults under "SLV4Policy.mode.<accountLabel>".
- (void)toggleActiveMode;

/// Which policy is "active" — the one whose fire-state the user follows.
/// Default: SLV4PolicyK5Dyn.
@property (nonatomic, assign) SLV4PolicyKind activePolicy;

/// Display name for a policy kind.
+ (NSString *)nameForKind:(SLV4PolicyKind)kind;
+ (NSString *)shortNameForKind:(SLV4PolicyKind)kind;

@end
