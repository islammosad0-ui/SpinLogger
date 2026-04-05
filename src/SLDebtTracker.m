#import "SLDebtTracker.h"
#import "SLSpinParser.h"

@implementation SLDebtTrackerConfig

+ (instancetype)accDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    c.target = 100; c.floorBase = 80; c.floorMin = 20;
    c.quietMin = 3; c.quietMax = 7; c.betWindow = 8;
    return c;
}

+ (instancetype)spnDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    c.target = 87; c.floorBase = 65; c.floorMin = 20;
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
@end

@implementation SLDebtTracker

- (instancetype)initWithConfig:(SLDebtTrackerConfig *)config {
    self = [super init];
    if (self) {
        _config = config;
        _debt = 0; _saSpins = 0; _quietSpins = 0;
        _inQuietZone = NO; _quietTriggered = NO;
        _betSpinsUsed = 0; _phase = SLDebtPhaseWaiting;
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
        self.debt += (gap - self.config.target);
        self.saSpins = 0;
        self.quietSpins = 0;
        self.quietTriggered = NO;
        self.inQuietZone = NO;
        self.betSpinsUsed = 0;
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
}

- (NSDictionary *)stateDictionary {
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
}

@end
