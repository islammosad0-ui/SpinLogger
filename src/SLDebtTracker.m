#import "SLDebtTracker.h"
#import "SLSpinParser.h"

static const CGFloat kFloorRatio = 1.33;

@implementation SLDebtTrackerConfig

+ (instancetype)accDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    c.target = 100; c.floorBase = 133; c.floorMin = 20;
    c.quietMin = 3; c.quietMax = 3; c.betWindow = 8; // pulse: skip 3, bet 3
    return c;
}

+ (instancetype)spnDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    c.target = 87; c.floorBase = 116; c.floorMin = 20;
    c.quietMin = 3; c.quietMax = 3; c.betWindow = 8; // pulse: skip 3, bet 3
    return c;
}

@end

@interface SLDebtTracker ()
@property (nonatomic, assign, readwrite) NSInteger debt;
@property (nonatomic, assign, readwrite) NSInteger saSpins;
@property (nonatomic, assign, readwrite) NSInteger quietSpins;
@property (nonatomic, assign, readwrite) BOOL inQuietZone;
@property (nonatomic, assign, readwrite) BOOL quietTriggered;
@property (nonatomic, assign, readwrite) NSInteger betSpinsUsed;
@property (nonatomic, assign, readwrite) SLDebtPhase phase;
@property (nonatomic, strong, readwrite) NSMutableArray<NSNumber *> *gapHistory;
@property (nonatomic, assign, readwrite) BOOL calibrated;
@property (nonatomic, assign, readwrite) NSInteger lastGap;
@end

@implementation SLDebtTracker

- (instancetype)initWithConfig:(SLDebtTrackerConfig *)config {
    self = [super init];
    if (self) {
        _config = config;
        _calibrationThreshold = 5;
        _gapHistory = [NSMutableArray array];
        _calibrated = NO;
        _debt = 0; _saSpins = 0; _quietSpins = 0;
        _inQuietZone = NO; _quietTriggered = NO;
        _betSpinsUsed = 0; _phase = SLDebtPhaseWaiting;
        _lastGap = 0; _catches = 0; _misses = 0;
    }
    return self;
}

- (NSInteger)watchPoint {
    return MAX(self.config.floorMin, self.config.floorBase - self.debt);
}

- (void)onSpin:(SLSpinResult *)spin isTargetTriple:(BOOL)isTarget isOtherTriple:(BOOL)isOther {
    self.saSpins++;

    // --- Handle target triple hit ---
    if (isTarget) {
        NSInteger gap = self.saSpins;
        self.lastGap = gap;
        [self.gapHistory addObject:@(gap)];

        // Track catch/miss (only after calibration)
        if (self.calibrated) {
            if (self.phase == SLDebtPhaseBetNow) {
                self.catches++;
            } else {
                self.misses++;
            }
            self.debt += (gap - self.config.target);
        }

        // Running median calibration: recalculate target on every gap
        if (!self.config.targetLocked &&
            (NSInteger)self.gapHistory.count >= self.calibrationThreshold) {
            NSArray *sorted = [self.gapHistory sortedArrayUsingSelector:@selector(compare:)];
            NSUInteger mid = sorted.count / 2;
            NSInteger newTarget;
            if (sorted.count % 2 == 0) {
                newTarget = ([sorted[mid - 1] integerValue] + [sorted[mid] integerValue]) / 2;
            } else {
                newTarget = [sorted[mid] integerValue];
            }
            self.config.target = newTarget;
            self.config.floorBase = (NSInteger)(newTarget * kFloorRatio);
            if (!self.calibrated) {
                self.calibrated = YES;
                self.debt = 0;
                NSLog(@"[DebtTracker] Initial calibration (median): target=%ld from %ld gaps",
                      (long)newTarget, (long)self.gapHistory.count);
            }
        }

        // Reset per-gap state
        self.saSpins = 0;
        self.quietSpins = 0;
        self.quietTriggered = NO;
        self.inQuietZone = NO;
        self.betSpinsUsed = 0;
        self.phase = SLDebtPhaseWaiting;
        return;
    }

    // Not calibrated yet — don't compute phases
    if (!self.calibrated) {
        self.phase = SLDebtPhaseWaiting;
        return;
    }

    // --- Hazard-based pulse betting (110% threshold + skip/bet pulse) ---
    // Past 110%: each non-ACC triple starts a pulse cycle:
    //   skip quietMin spins (1x) → bet quietMax spins (MAX) → 1x until next triple
    // Triples cluster every ~5 spins. Skipping 3 after a triple then betting 3
    // concentrates max bets where the NEXT triple is most likely to land.
    // Simulated: 23.5 spins/hit on Account 1 (vs 38.9 without pulse).
    NSInteger threshold = (NSInteger)(self.config.target * 1.1); // 110% of median
    NSInteger alertPoint = (NSInteger)(self.config.target * 0.7); // 70% of median

    if (self.saSpins >= threshold) {
        if (isOther) {
            // Non-ACC triple resets the pulse cycle
            self.quietTriggered = YES;
            self.quietSpins = 0; // pulse counter: 0 = just saw triple
        }

        if (!self.quietTriggered) {
            self.phase = SLDebtPhaseWatch; // armed, waiting for first triple
        } else {
            self.quietSpins++;
            if (self.quietSpins <= self.config.quietMin) {
                // Skip phase: 1x bet (dead spins right after triple)
                self.phase = SLDebtPhaseWatch;
            } else if (self.quietSpins <= self.config.quietMin + self.config.quietMax) {
                // Bet phase: MAX bet (next triple is due here)
                self.phase = SLDebtPhaseBetNow;
            } else {
                // Past pulse window: 1x until next non-ACC triple resets
                self.phase = SLDebtPhaseWatch;
            }
        }
    } else if (self.saSpins >= alertPoint) {
        self.phase = SLDebtPhaseWatch;
    } else {
        self.phase = SLDebtPhaseWaiting;
    }
}

- (void)reset {
    self.debt = 0; self.saSpins = 0; self.quietSpins = 0;
    self.inQuietZone = NO; self.quietTriggered = NO;
    self.betSpinsUsed = 0; self.phase = SLDebtPhaseWaiting;
    [self.gapHistory removeAllObjects];
    self.calibrated = NO;
    self.lastGap = 0; self.catches = 0; self.misses = 0;
}

- (NSDictionary *)stateDictionary {
    // Convert gapHistory to plain array for serialization
    NSArray *gaps = self.gapHistory ? [self.gapHistory copy] : @[];
    return @{
        @"debt":           @(self.debt),
        @"saSpins":        @(self.saSpins),
        @"quietSpins":     @(self.quietSpins),
        @"quietTriggered": @(self.quietTriggered),
        @"inQuietZone":    @(self.inQuietZone),
        @"betSpinsUsed":   @(self.betSpinsUsed),
        @"phase":          @(self.phase),
        @"target":         @(self.config.target),
        @"floorBase":      @(self.config.floorBase),
        @"floorMin":       @(self.config.floorMin),
        @"quietMin":       @(self.config.quietMin),
        @"quietMax":       @(self.config.quietMax),
        @"betWindow":      @(self.config.betWindow),
        @"gapHistory":     gaps,
        @"calibrated":     @(self.calibrated),
        @"calThreshold":   @(self.calibrationThreshold),
        @"lastGap":        @(self.lastGap),
        @"catches":        @(self.catches),
        @"misses":         @(self.misses),
    };
}

- (void)restoreFromDictionary:(NSDictionary *)dict {
    if (!dict) return;
    self.debt           = [dict[@"debt"] integerValue];
    self.saSpins        = [dict[@"saSpins"] integerValue];
    self.quietSpins     = [dict[@"quietSpins"] integerValue];
    self.quietTriggered = [dict[@"quietTriggered"] boolValue];
    self.inQuietZone    = [dict[@"inQuietZone"] boolValue];
    self.betSpinsUsed   = [dict[@"betSpinsUsed"] integerValue];
    self.phase          = (SLDebtPhase)[dict[@"phase"] integerValue];
    if (dict[@"target"])    self.config.target    = [dict[@"target"] integerValue];
    if (dict[@"floorBase"]) self.config.floorBase = [dict[@"floorBase"] integerValue];
    if (dict[@"floorMin"])  self.config.floorMin  = [dict[@"floorMin"] integerValue];
    if (dict[@"quietMin"])  self.config.quietMin  = [dict[@"quietMin"] integerValue];
    if (dict[@"quietMax"])  self.config.quietMax  = [dict[@"quietMax"] integerValue];
    if (dict[@"betWindow"]) self.config.betWindow = [dict[@"betWindow"] integerValue];
    if (dict[@"gapHistory"]) {
        self.gapHistory = [NSMutableArray arrayWithArray:dict[@"gapHistory"]];
    }
    self.calibrated          = [dict[@"calibrated"] boolValue];
    self.calibrationThreshold = [dict[@"calThreshold"] integerValue] ?: 5;
    self.lastGap             = [dict[@"lastGap"] integerValue];
    self.catches             = [dict[@"catches"] integerValue];
    self.misses              = [dict[@"misses"] integerValue];
}

@end
