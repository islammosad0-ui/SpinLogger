#import "SLV4Policy.h"
#import "SLV4Model.h"
#import "SLV4Features.h"
#import "SLAccountID.h"
#import <dlfcn.h>

// ---------------------------------------------------------------------------
//  dyn_aggr threshold schedule
//
//  Per-account schedules tuned via analysis/tail_risk_v4_hazard_plus.py +
//  configs/dyn_aggr_schedules.json (see step-2 of v4 tuning workflow).
//  If no schedule file is found OR the current account isn't in the bundle,
//  fall back to the pooled schedule (same numbers as the original hardcode).
// ---------------------------------------------------------------------------
static const int kWinLo = 15;
static const int kWinHi = 100;

static double SLV4_PooledThreshold(int t) {
    if (t > 100) return 0.10;
    if (t >= 70) return 0.03;
    if (t >= 50) return 0.04;
    if (t >= 30) return 0.05;
    if (t >= 15) return 0.08;
    return 0.99;  // outside [15,100] window — no fire (caller also gates on window)
}

// Anchor symbol so dladdr() can find the dylib path (mirrors SLV4Model).
__attribute__((visibility("default"))) extern void SpinLoggerV4Policy_anchor(void);
void SpinLoggerV4Policy_anchor(void) {}

// Per-account config: head ∈ {"ACC","ANY_VT"}, K ∈ {3,5,10}, plus 4-band
// schedule. Schemas:
//   v1 — array of bands per account                   (legacy)
//   v2 — {head, K, schedule}                          (single schedule)
//   v3 — {head, K, default_mode, schedules:{bundled,tuned}}  (current)
// We accept all three. For v1/v2 the "tuned" mode mirrors the only schedule.
static NSDictionary<NSString *, NSDictionary *> *gPerAccountConfigs;

// User's per-account mode override (NSUserDefaults). Key:
//   SLV4Policy.mode.<accountLabel> → "bundled" or "tuned"
// If unset, fall back to default_mode from the JSON.
static NSString *SLV4_ModeKey(NSString *acct) {
    return [NSString stringWithFormat:@"SLV4Policy.mode.%@", acct ?: @"_"];
}

static void SLV4_LoadSchedulesIfNeeded(void) {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        NSMutableArray *candidates = [NSMutableArray array];
        Dl_info info = {0};
        if (dladdr((const void *)&SpinLoggerV4Policy_anchor, &info) && info.dli_fname) {
            NSString *dir = [@(info.dli_fname) stringByDeletingLastPathComponent];
            [candidates addObject:[dir stringByAppendingPathComponent:@"dyn_aggr_schedules.json"]];
        }
        NSString *exec = [[NSBundle mainBundle] executablePath];
        if (exec) {
            NSString *dir = [exec stringByDeletingLastPathComponent];
            [candidates addObject:[dir stringByAppendingPathComponent:@"dyn_aggr_schedules.json"]];
        }
        NSString *docs = NSSearchPathForDirectoriesInDomains(
            NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
        if (docs) {
            [candidates addObject:[docs stringByAppendingPathComponent:@"dyn_aggr_schedules.json"]];
        }

        NSFileManager *fm = [NSFileManager defaultManager];
        for (NSString *path in candidates) {
            if (![fm fileExistsAtPath:path]) continue;
            NSData *data = [NSData dataWithContentsOfFile:path];
            if (!data) continue;
            NSError *err = nil;
            NSDictionary *bundle = [NSJSONSerialization JSONObjectWithData:data options:0 error:&err];
            if (![bundle isKindOfClass:[NSDictionary class]]) {
                NSLog(@"[SLV4Policy] schedules JSON parse failed at %@: %@", path, err);
                continue;
            }
            NSDictionary *accounts = bundle[@"accounts"];
            if (![accounts isKindOfClass:[NSDictionary class]]) continue;

            // Normalize: each account becomes a dict with
            //   {head, K, default_mode, schedules:{bundled,tuned}}
            // v1 (array of bands)         → both modes share the same schedule
            // v2 ({head, K, schedule})    → both modes share the same schedule
            // v3 ({head, K, default_mode, schedules:{bundled,tuned}}) → as-is
            NSMutableDictionary *normalized = [NSMutableDictionary dictionary];
            for (NSString *acct in accounts) {
                id v = accounts[acct];
                NSArray *bundled = nil, *tuned = nil;
                NSString *head = @"ACC", *defaultMode = @"bundled";
                NSNumber *K = @5;

                if ([v isKindOfClass:[NSArray class]]) {
                    bundled = tuned = (NSArray *)v;
                } else if ([v isKindOfClass:[NSDictionary class]]) {
                    NSDictionary *d = v;
                    head = d[@"head"] ?: @"ACC";
                    K = d[@"K"] ?: @5;
                    defaultMode = d[@"default_mode"] ?: @"bundled";
                    NSDictionary *scheds = d[@"schedules"];
                    if ([scheds isKindOfClass:[NSDictionary class]]) {
                        bundled = scheds[@"bundled"];
                        tuned   = scheds[@"tuned"];
                    } else if ([d[@"schedule"] isKindOfClass:[NSArray class]]) {
                        bundled = tuned = d[@"schedule"];
                    }
                }
                if (![bundled isKindOfClass:[NSArray class]]) bundled = @[];
                if (![tuned   isKindOfClass:[NSArray class]]) tuned   = bundled;

                normalized[acct] = @{
                    @"head":         head,
                    @"K":            K,
                    @"default_mode": defaultMode,
                    @"schedules":    @{@"bundled": bundled, @"tuned": tuned},
                };
            }
            gPerAccountConfigs = [normalized copy];
            NSLog(@"[SLV4Policy] loaded per-account configs from %@ (%lu accounts)",
                  path, (unsigned long)gPerAccountConfigs.count);
            return;
        }
        NSLog(@"[SLV4Policy] dyn_aggr_schedules.json not found — using pooled ACC schedule");
    });
}

static NSString *SLV4_ActiveHead(void) {
    SLV4_LoadSchedulesIfNeeded();
    NSDictionary *cfg = gPerAccountConfigs[SLAccountLabel()];
    return cfg[@"head"] ?: @"ACC";
}

// Mode for the current account: NSUserDefaults override, else cfg.default_mode,
// else "bundled". Always returns "bundled" or "tuned".
static NSString *SLV4_ActiveMode(void) {
    SLV4_LoadSchedulesIfNeeded();
    NSString *acct = SLAccountLabel();
    NSString *override = [[NSUserDefaults standardUserDefaults] stringForKey:SLV4_ModeKey(acct)];
    if ([override isEqualToString:@"bundled"] || [override isEqualToString:@"tuned"]) {
        return override;
    }
    NSDictionary *cfg = gPerAccountConfigs[acct];
    NSString *def = cfg[@"default_mode"];
    if ([def isEqualToString:@"tuned"]) return @"tuned";
    return @"bundled";
}

static double SLV4_DynAggrThreshold(int t) {
    SLV4_LoadSchedulesIfNeeded();
    NSDictionary *cfg = gPerAccountConfigs[SLAccountLabel()];
    NSDictionary *scheds = cfg[@"schedules"];
    NSArray<NSDictionary *> *bands = scheds[SLV4_ActiveMode()];
    if (!bands.count) bands = scheds[@"bundled"];
    if (!bands.count) return SLV4_PooledThreshold(t);
    for (NSDictionary *b in bands) {
        int lo = [b[@"t_min"] intValue];
        int hi = [b[@"t_max"] intValue];
        if (t >= lo && t <= hi) return [b[@"thr"] doubleValue];
    }
    return 0.99;
}

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

// Once-per-session log + Documents/v4_active.txt write so the user can verify
// which (account, head, mode, schedule) the policy resolved to without needing
// the panel header to fit. Re-emit on first call after launch only.
static void SLV4_DebugDumpActiveConfigOnce(NSString *head, double thr_now, int t) {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        NSString *acct = SLAccountLabel();
        NSString *mode = SLV4_ActiveMode();
        NSDictionary *cfg = gPerAccountConfigs[acct];
        BOOL matched = (cfg != nil);
        NSLog(@"[SLV4Policy] ACTIVE acct=%@ head=%@ mode=%@ matched=%@ t=%d thr=%.3f",
              acct, head, mode, matched ? @"YES" : @"NO", t, thr_now);

        NSString *docs = NSSearchPathForDirectoriesInDomains(
            NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
        if (!docs) return;
        NSMutableString *body = [NSMutableString string];
        [body appendFormat:@"account_label   = %@\n", acct];
        [body appendFormat:@"head            = %@\n", head];
        [body appendFormat:@"mode            = %@\n", mode];
        [body appendFormat:@"matched_bundle  = %@\n", matched ? @"YES" : @"NO (fell back to pooled)"];
        if (matched) {
            [body appendFormat:@"K               = %@\n", cfg[@"K"] ?: @"?"];
            [body appendFormat:@"default_mode    = %@\n", cfg[@"default_mode"] ?: @"?"];
            NSDictionary *scheds = cfg[@"schedules"];
            NSArray *bands = scheds[mode];
            for (NSDictionary *b in bands) {
                [body appendFormat:@"  t in [%@..%@]  thr = %@\n",
                    b[@"t_min"], b[@"t_max"], b[@"thr"]];
            }
        }
        NSString *path = [docs stringByAppendingPathComponent:@"v4_active.txt"];
        [body writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:nil];
        NSLog(@"[SLV4Policy] wrote %@", path);
    });
}

- (SLV4PolicyState)evaluate {
    SLV4Model *m = [SLV4Model shared];
    SLV4Features *f = [SLV4Features shared];
    SLV4Snapshot snap = [f snapshot];

    NSString *head = SLV4_ActiveHead();
    double p3 = 0, p5 = 0, p10 = 0;
    if (m.isLoaded) {
        [m predictHead:head feat:[f currentFeatureVector] p3:&p3 p5:&p5 p10:&p10];
    }
    SLV4_DebugDumpActiveConfigOnce(head, SLV4_DynAggrThreshold(snap.t), snap.t);

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

- (NSString *)activeHeadName { return SLV4_ActiveHead(); }

- (NSString *)activeModeName { return SLV4_ActiveMode(); }

- (void)toggleActiveMode {
    NSString *acct = SLAccountLabel();
    NSString *next = [SLV4_ActiveMode() isEqualToString:@"tuned"] ? @"bundled" : @"tuned";
    [[NSUserDefaults standardUserDefaults] setObject:next forKey:SLV4_ModeKey(acct)];
    NSLog(@"[SLV4Policy] mode for %@ → %@", acct, next);
}

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
