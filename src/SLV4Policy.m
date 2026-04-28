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
// Extended t-window: catches cycles ending at t<15 or t>100 that the old
// [15,100] window missed. ~10% of cycles end early, ~5% end late — both
// previously uncatchable.
static const int kWinLo = 10;
static const int kWinHi = 130;

// Anomaly proxy: when the average of the last 3 VT-to-VT gaps exceeds this,
// we suspect the current cycle will also be long. Used by the BALANCED mode
// to raise its fire threshold and avoid bleeding bets.
static const double kAnomVtMean3 = 60.0;

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
//   v3 — {head, K, default_mode, schedules:{bundled,tuned}}    (legacy 2-mode)
//   v4 — {head, K, default_mode, schedules:{cheap,balanced,aggressive}}
//        (current — three flat-thr modes)
// We accept all four. For v1/v2 the value is mirrored across all three modes.
// For v3 (bundled/tuned): bundled→balanced, tuned→aggressive, cheap=tuned.
static NSDictionary<NSString *, NSDictionary *> *gPerAccountConfigs;

static NSString *const kSLV4ModeCheap      = @"cheap";
static NSString *const kSLV4ModeBalanced   = @"balanced";
static NSString *const kSLV4ModeAggressive = @"aggressive";

// User's per-account mode override (NSUserDefaults). Key:
//   SLV4Policy.mode.<accountLabel> → "cheap" / "balanced" / "aggressive"
// If unset, fall back to default_mode from the JSON.
static NSString *SLV4_ModeKey(NSString *acct) {
    return [NSString stringWithFormat:@"SLV4Policy.mode.%@", acct ?: @"_"];
}

// Translate legacy mode tags to the v4 vocabulary.
static NSString *SLV4_NormalizeMode(NSString *m) {
    if ([m isEqualToString:@"tuned"])   return kSLV4ModeAggressive;
    if ([m isEqualToString:@"bundled"]) return kSLV4ModeBalanced;
    if ([m isEqualToString:kSLV4ModeCheap])      return kSLV4ModeCheap;
    if ([m isEqualToString:kSLV4ModeBalanced])   return kSLV4ModeBalanced;
    if ([m isEqualToString:kSLV4ModeAggressive]) return kSLV4ModeAggressive;
    return nil;  // unknown
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
            //   {head, K, default_mode, schedules:{cheap,balanced,aggressive}}
            // v1 array              → all 3 modes share the same schedule
            // v2 single schedule    → all 3 modes share the same schedule
            // v3 bundled/tuned      → bundled→balanced, tuned→aggressive,
            //                         cheap = tuned (no separate cheap defined)
            // v4 cheap/balanced/aggressive → as-is
            NSMutableDictionary *normalized = [NSMutableDictionary dictionary];
            for (NSString *acct in accounts) {
                id v = accounts[acct];
                NSArray *cheap = nil, *balanced = nil, *aggressive = nil;
                NSString *head = @"ANY_VT", *defaultMode = kSLV4ModeBalanced;
                NSNumber *K = @5;

                if ([v isKindOfClass:[NSArray class]]) {
                    cheap = balanced = aggressive = (NSArray *)v;
                } else if ([v isKindOfClass:[NSDictionary class]]) {
                    NSDictionary *d = v;
                    head = d[@"head"] ?: @"ANY_VT";
                    K = d[@"K"] ?: @5;
                    NSString *raw = d[@"default_mode"];
                    NSString *norm = raw ? SLV4_NormalizeMode(raw) : nil;
                    defaultMode = norm ?: kSLV4ModeBalanced;
                    NSDictionary *scheds = d[@"schedules"];
                    if ([scheds isKindOfClass:[NSDictionary class]]) {
                        cheap      = scheds[kSLV4ModeCheap];
                        balanced   = scheds[kSLV4ModeBalanced]   ?: scheds[@"bundled"];
                        aggressive = scheds[kSLV4ModeAggressive] ?: scheds[@"tuned"];
                        if (!cheap) cheap = aggressive ?: balanced;
                    } else if ([d[@"schedule"] isKindOfClass:[NSArray class]]) {
                        cheap = balanced = aggressive = d[@"schedule"];
                    }
                }
                if (![cheap      isKindOfClass:[NSArray class]]) cheap      = @[];
                if (![balanced   isKindOfClass:[NSArray class]]) balanced   = cheap;
                if (![aggressive isKindOfClass:[NSArray class]]) aggressive = balanced;

                normalized[acct] = @{
                    @"head":         head,
                    @"K":            K,
                    @"default_mode": defaultMode,
                    @"schedules":    @{
                        kSLV4ModeCheap:      cheap,
                        kSLV4ModeBalanced:   balanced,
                        kSLV4ModeAggressive: aggressive,
                    },
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

// Mode for the current account: NSUserDefaults override (normalized),
// else cfg.default_mode, else "balanced". Returns one of the v4 mode names.
static NSString *SLV4_ActiveMode(void) {
    SLV4_LoadSchedulesIfNeeded();
    NSString *acct = SLAccountLabel();
    NSString *override = [[NSUserDefaults standardUserDefaults] stringForKey:SLV4_ModeKey(acct)];
    NSString *norm = override ? SLV4_NormalizeMode(override) : nil;
    if (norm) return norm;
    NSDictionary *cfg = gPerAccountConfigs[acct];
    norm = SLV4_NormalizeMode(cfg[@"default_mode"]);
    return norm ?: kSLV4ModeBalanced;
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
    NSString *mode = SLV4_ActiveMode();
    double p3 = 0, p5 = 0, p10 = 0;
    if (m.isLoaded) {
        [m predictHead:head feat:[f currentFeatureVector] p3:&p3 p5:&p5 p10:&p10];
    }
    double vtMean3 = [f currentVtGapMean3];
    BOOL anomalySuspected = (!isnan(vtMean3)) && (vtMean3 > kAnomVtMean3);

    int t = snap.t;
    BOOL windowOk = (t >= kWinLo && t <= kWinHi);

    SLV4PolicyState s = {0};
    s.p3 = p3; s.p5 = p5; s.p10 = p10;
    s.t = t;
    s.activeKind = (int)self.activePolicy;

    // ----- K5 dyn_aggr — mode-aware rules (no schedule lookup) -----
    // Rules picked for best Pareto frontier under strict and W10 catch metrics:
    //   cheap     : p3 >= 0.07 in [10,130]   (~40-48% strict catch / ~30 B/VT)
    //   balanced  : p5 >= 0.05 normally, raises to 0.10 when last-3-cycle mean
    //               gap > 60 (anomaly proxy)  (~78-81% strict / ~40-43 B/VT)
    //   aggressive: p10 >= 0.15 in [10,130]   (~70-76% W10 catch / ~27-30 B/VT)
    BOOL fireMode = NO;
    double thrDisplay = 0.0;
    if ([mode isEqualToString:@"cheap"]) {
        fireMode = (p3 >= 0.07);
        thrDisplay = 0.07;
    } else if ([mode isEqualToString:@"aggressive"]) {
        fireMode = (p10 >= 0.15);
        thrDisplay = 0.15;
    } else {  // balanced (default)
        double thr = anomalySuspected ? 0.10 : 0.05;
        fireMode = (p5 >= thr);
        thrDisplay = thr;
    }
    SLV4_DebugDumpActiveConfigOnce(head, thrDisplay, t);

    s.thr[SLV4PolicyK5Dyn] = thrDisplay;
    s.on[SLV4PolicyK5Dyn] = windowOk && fireMode;

    // (2) Triple intersection: p3 >= .04 AND p5 >= .05 AND p10 >= .10
    s.thr[SLV4PolicyTriple] = 0.0;
    s.on[SLV4PolicyTriple] = windowOk && (p3 >= 0.04) && (p5 >= 0.05) && (p10 >= 0.10);

    // (3) K10 dyn_aggr — keeps a bare K=10 head with a single threshold
    s.thr[SLV4PolicyK10Dyn] = 0.15;
    s.on[SLV4PolicyK10Dyn] = windowOk && (p10 >= 0.15);

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
    NSString *cur = SLV4_ActiveMode();
    NSString *next = kSLV4ModeBalanced;
    if      ([cur isEqualToString:kSLV4ModeCheap])      next = kSLV4ModeBalanced;
    else if ([cur isEqualToString:kSLV4ModeBalanced])   next = kSLV4ModeAggressive;
    else if ([cur isEqualToString:kSLV4ModeAggressive]) next = kSLV4ModeCheap;
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
