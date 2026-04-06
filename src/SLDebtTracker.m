#import "SLDebtTracker.h"

@implementation SLDebtTrackerConfig

+ (instancetype)accDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    c.spinThreshold = 130;
    c.rateGate = 0.30;
    c.pulseSkip = 0;  // off by default
    return c;
}

+ (instancetype)spnDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    c.spinThreshold = 87;
    c.rateGate = 0.25;
    c.pulseSkip = 0;  // off by default
    return c;
}

@end

@interface SLDebtTracker ()
@property (nonatomic, assign, readwrite) NSInteger saSpins;
@property (nonatomic, assign, readwrite) NSInteger saSymbols;
@property (nonatomic, assign, readwrite) SLDebtPhase phase;
@property (nonatomic, assign, readwrite) NSInteger pulseRemaining;
@end

@implementation SLDebtTracker

- (instancetype)initWithConfig:(SLDebtTrackerConfig *)config {
    self = [super init];
    if (self) {
        _config = config;
        _saSpins = 0;
        _saSymbols = 0;
        _phase = SLDebtPhaseWaiting;
        _pulseRemaining = 0;
    }
    return self;
}

- (double)accumRate {
    if (self.saSpins == 0) return 0.0;
    return (double)self.saSymbols / (double)self.saSpins;
}

- (void)onSpinWithTargetHit:(BOOL)isTarget otherTriple:(BOOL)isOther symbolCount:(NSInteger)symbols {
    self.saSpins++;
    self.saSymbols += symbols;

    if (isTarget) {
        self.saSpins = 0;
        self.saSymbols = 0;
        self.phase = SLDebtPhaseWaiting;
        self.pulseRemaining = 0;
        return;
    }

    // Phase: two conditions must BOTH be true for BET NOW
    if (self.saSpins < self.config.spinThreshold) {
        self.phase = SLDebtPhaseWaiting;
        self.pulseRemaining = 0;
        return;
    }

    if (self.config.rateGate > 0.0 && [self accumRate] < self.config.rateGate) {
        self.phase = SLDebtPhaseWatch;
        self.pulseRemaining = 0;
        return;
    }

    // We're in BET NOW territory — check pulse
    if (self.config.pulseSkip > 0) {
        // Non-target real triple in BET NOW zone: start pulse skip
        if (isOther) {
            self.pulseRemaining = self.config.pulseSkip;
        }

        if (self.pulseRemaining > 0) {
            self.pulseRemaining--;
            self.phase = SLDebtPhaseWatch;  // drop to 1x during pulse
            return;
        }
    }

    self.phase = SLDebtPhaseBetNow;
}

- (void)reset {
    self.saSpins = 0;
    self.saSymbols = 0;
    self.phase = SLDebtPhaseWaiting;
    self.pulseRemaining = 0;
}

- (NSDictionary *)stateDictionary {
    return @{
        @"saSpins":        @(self.saSpins),
        @"saSymbols":      @(self.saSymbols),
        @"phase":          @(self.phase),
        @"spinThreshold":  @(self.config.spinThreshold),
        @"rateGate":       @(self.config.rateGate),
        @"pulseSkip":      @(self.config.pulseSkip),
        @"pulseRemaining": @(self.pulseRemaining),
    };
}

- (void)restoreFromDictionary:(NSDictionary *)dict {
    if (!dict) return;
    self.saSpins   = [dict[@"saSpins"] integerValue];
    self.saSymbols = [dict[@"saSymbols"] integerValue];
    self.phase     = (SLDebtPhase)[dict[@"phase"] integerValue];
    self.pulseRemaining = [dict[@"pulseRemaining"] integerValue];
    if (dict[@"spinThreshold"]) self.config.spinThreshold = [dict[@"spinThreshold"] integerValue];
    if (dict[@"rateGate"])      self.config.rateGate      = [dict[@"rateGate"] doubleValue];
    if (dict[@"pulseSkip"])     self.config.pulseSkip     = [dict[@"pulseSkip"] integerValue];
}

@end
