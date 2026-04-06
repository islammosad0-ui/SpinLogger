#import "SLDebtTracker.h"
#import "SLSpinParser.h"

static const CGFloat kFloorRatio = 1.33;

@implementation SLDebtTrackerConfig

+ (instancetype)accDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    c.target = 100; c.floorBase = 133; c.floorMin = 20;
    c.quietMin = 3; c.quietMax = 7; c.betWindow = 8;
    return c;
}

+ (instancetype)spnDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    c.target = 87; c.floorBase = 116; c.floorMin = 20;
    c.quietMin = 3; c.quietMax = 7; c.betWindow = 8;
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

        // Auto-calibrate: after enough gaps, lock the target
        if (!self.calibrated && (NSInteger)self.gapHistory.count >= self.calibrationThreshold) {
            NSInteger sum = 0;
            for (NSNumber *g in self.gapHistory) sum += g.integerValue;
            self.config.target = sum / (NSInteger)self.gapHistory.count;
            self.config.floorBase = (NSInteger)(self.config.target * kFloorRatio);
            self.calibrated = YES;
            self.debt = 0;
            NSLog(@"[DebtTracker] Calibrated: target=%ld floorBase=%ld from %ld gaps",
                  (long)self.config.target, (long)self.config.floorBase,
                  (long)self.gapHistory.count);
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

    // --- Handle non-target triple (combat/spins/gold) ---
    if (isOther) {
        self.quietTriggered = YES;
        self.quietSpins = 0;
        self.inQuietZone = NO;
    }

    // --- Quiet zone tracking ---
    if (self.quietTriggered) {
        if (!isOther) {
            self.quietSpins++;
        }
        self.inQuietZone = (self.quietSpins >= self.config.quietMin &&
                            self.quietSpins <= self.config.quietMax);
    }

    // --- Phase computation ---
    NSInteger wp = [self watchPoint];

    if (self.saSpins < wp) {
        self.phase = SLDebtPhaseWaiting;
        self.betSpinsUsed = 0;
    } else if (self.inQuietZone && self.betSpinsUsed < self.config.betWindow) {
        if (self.phase != SLDebtPhaseBetNow) {
            self.betSpinsUsed = 0;
        }
        self.phase = SLDebtPhaseBetNow;
        self.betSpinsUsed++;
    } else {
        self.phase = SLDebtPhaseWatch;
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
