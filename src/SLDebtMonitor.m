#import <UIKit/UIKit.h>
#import "SLDebtMonitor.h"
#import "SLDebtTracker.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import "SLBetDecisionLogger.h"

// ---------------------------------------------------------------------------
//  SLDebtTile — one draggable UIWindow for a single tracker (ACC or SPN)
// ---------------------------------------------------------------------------
@interface SLDebtTile : NSObject
@property (nonatomic, strong) UIWindow *window;
@property (nonatomic, strong) UIView *container;
@property (nonatomic, strong) UIView *progressBar;        // accum_pct background bar (under rateLabel)
@property (nonatomic, strong) UILabel *spinLabel;
@property (nonatomic, strong) UILabel *rateLabel;
@property (nonatomic, strong) UILabel *phaseLabel;
@property (nonatomic, strong) UILabel *missionBadge;      // top-right "M37" badge
@property (nonatomic, strong) SLDebtTracker *tracker;
@property (nonatomic, copy)   NSString *emoji;
@property (nonatomic, copy)   NSString *symbolName;       // which symbol to count
@property (nonatomic, copy)   NSString *defaultsKey;
@property (nonatomic, copy)   NSString *posXKey;
@property (nonatomic, copy)   NSString *posYKey;
@property (nonatomic, assign) BOOL compact;
@property (nonatomic, assign) BOOL glowing;
@property (nonatomic, strong) UIColor *glowColor;
@property (nonatomic, strong) UIColor *watchBorderColor;
// Latest GAE state from spin (for display, not used in rules)
@property (nonatomic, assign) NSInteger latestMission;
@property (nonatomic, assign) double    latestAccumPct;
@end

@implementation SLDebtTile
@end

// ---------------------------------------------------------------------------
//  SLDebtMonitor
// ---------------------------------------------------------------------------
@interface SLDebtMonitor ()
@property (nonatomic, strong) SLDebtTile *accTile;
@property (nonatomic, strong) SLDebtTile *spnTile;
@property (nonatomic, copy)   NSString *lastEventID;
@property (nonatomic, copy)   NSString *lastMission;
@property (nonatomic, strong) UIImpactFeedbackGenerator *haptic;
@property (nonatomic, strong) UIWindow *settingsWindow; // full-screen window for presenting alerts
// Bet decision logging counters
@property (nonatomic, assign) NSInteger accGapIdx;        // increments on each ACC triple (per session)
@property (nonatomic, assign) NSInteger accSpinInGap;     // resets on each ACC triple
@end

@implementation SLDebtMonitor

+ (instancetype)shared {
    static SLDebtMonitor *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _haptic = [[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleHeavy];
        _lastEventID = [[NSUserDefaults standardUserDefaults] stringForKey:@"Speeder_DebtEventID"];
        _lastMission = [[NSUserDefaults standardUserDefaults] stringForKey:@"Speeder_DebtMission"];
    }
    return self;
}

#pragma mark - Install

- (void)install {
    UIWindowScene *scene = nil;
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            if (s.activationState == UISceneActivationStateForegroundActive) break;
        }
    }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;

    self.accTile = [self buildTileInScene:scene
                                    emoji:@"\u2B50"
                               symbolName:kSLSymbolAccumulation
                                glowColor:[UIColor colorWithRed:0.2 green:1.0 blue:0.3 alpha:1.0]
                         watchBorderColor:[UIColor colorWithRed:1.0 green:0.75 blue:0.0 alpha:0.8]
                                  tracker:[[SLDebtTracker alloc] initWithConfig:[SLDebtTrackerConfig accEnsembleDefaults]]
                              defaultsKey:@"Speeder_DebtACC"
                                  posXKey:@"Speeder_DebtACCX"
                                  posYKey:@"Speeder_DebtACCY"
                               defaultPos:CGPointMake(screen.size.width - 100, screen.size.height * 0.3)
                              windowLevel:UIWindowLevelAlert + 260];

    self.spnTile = [self buildTileInScene:scene
                                    emoji:@"\U0001F48A"
                               symbolName:kSLSymbolSpins
                                glowColor:[UIColor colorWithRed:0.2 green:0.5 blue:1.0 alpha:1.0]
                         watchBorderColor:[UIColor colorWithRed:1.0 green:0.75 blue:0.0 alpha:0.8]
                                  tracker:[[SLDebtTracker alloc] initWithConfig:[SLDebtTrackerConfig spnDefaults]]
                              defaultsKey:@"Speeder_DebtSPN"
                                  posXKey:@"Speeder_DebtSPNX"
                                  posYKey:@"Speeder_DebtSPNY"
                               defaultPos:CGPointMake(screen.size.width - 100, screen.size.height * 0.3 + 70)
                              windowLevel:UIWindowLevelAlert + 261];

    [self restoreState];
    [self updateTileUI:self.accTile];
    [self updateTileUI:self.spnTile];

    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification object:nil];

    NSLog(@"[SpinLogger] DebtMonitor installed — ACC: %lu rules ensemble, SPN: %lu rule(s)",
          (unsigned long)self.accTile.tracker.config.rules.count,
          (unsigned long)self.spnTile.tracker.config.rules.count);
}

#pragma mark - Build Tile

- (SLDebtTile *)buildTileInScene:(UIWindowScene *)scene
                           emoji:(NSString *)emoji
                      symbolName:(NSString *)symbolName
                       glowColor:(UIColor *)glowColor
                watchBorderColor:(UIColor *)watchBorderColor
                         tracker:(SLDebtTracker *)tracker
                     defaultsKey:(NSString *)defaultsKey
                         posXKey:(NSString *)posXKey
                         posYKey:(NSString *)posYKey
                      defaultPos:(CGPoint)defaultPos
                     windowLevel:(UIWindowLevel)windowLevel {

    SLDebtTile *tile = [[SLDebtTile alloc] init];
    tile.tracker = tracker;
    tile.emoji = emoji;
    tile.symbolName = symbolName;
    tile.glowColor = glowColor;
    tile.watchBorderColor = watchBorderColor;
    tile.defaultsKey = defaultsKey;
    tile.posXKey = posXKey;
    tile.posYKey = posYKey;
    tile.compact = NO;
    tile.glowing = NO;

    CGFloat tileW = 90, tileH = 60;

    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    CGFloat x = [ud doubleForKey:posXKey];
    CGFloat y = [ud doubleForKey:posYKey];
    if (x == 0 && y == 0) { x = defaultPos.x; y = defaultPos.y; }

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, y, tileW, tileH);
    win.windowLevel = windowLevel;
    win.backgroundColor = [UIColor clearColor];

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    UIView *container = [[UIView alloc] initWithFrame:CGRectMake(0, 0, tileW, tileH)];
    container.backgroundColor = [UIColor colorWithRed:0.06 green:0.08 blue:0.14 alpha:0.94];
    container.layer.cornerRadius = 12;
    container.layer.borderWidth = 1.0;
    container.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.06].CGColor;
    container.clipsToBounds = YES;  // clip the progress bar to rounded corners
    [vc.view addSubview:container];
    tile.container = container;

    // accum_pct progress bar (under rate label, layered behind it)
    UIView *progressBar = [[UIView alloc] initWithFrame:CGRectMake(4, 20, 0, 16)];
    progressBar.backgroundColor = [UIColor colorWithRed:0.2 green:0.5 blue:0.3 alpha:0.20];
    progressBar.layer.cornerRadius = 2;
    [container addSubview:progressBar];
    tile.progressBar = progressBar;

    // Spin label (top) — emoji + spin count / MIN threshold
    UILabel *spinLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 2, tileW - 8, 18)];
    spinLabel.font = [UIFont boldSystemFontOfSize:13];
    spinLabel.textColor = [UIColor whiteColor];
    spinLabel.textAlignment = NSTextAlignmentCenter;
    [container addSubview:spinLabel];
    tile.spinLabel = spinLabel;

    // Mission badge (top-right corner, tiny)
    UILabel *missionBadge = [[UILabel alloc] initWithFrame:CGRectMake(tileW - 28, 1, 26, 10)];
    missionBadge.font = [UIFont monospacedDigitSystemFontOfSize:8 weight:UIFontWeightMedium];
    missionBadge.textColor = [UIColor colorWithWhite:0.55 alpha:1.0];
    missionBadge.textAlignment = NSTextAlignmentRight;
    missionBadge.hidden = YES;
    [container addSubview:missionBadge];
    tile.missionBadge = missionBadge;

    // Rate label (middle) — acc rate (and spn rate if COMBO)
    UILabel *rateLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 20, tileW - 8, 16)];
    rateLabel.font = [UIFont monospacedDigitSystemFontOfSize:11 weight:UIFontWeightMedium];
    rateLabel.textColor = [UIColor colorWithWhite:0.7 alpha:1.0];
    rateLabel.textAlignment = NSTextAlignmentCenter;
    rateLabel.backgroundColor = [UIColor clearColor];
    [container addSubview:rateLabel];
    tile.rateLabel = rateLabel;

    // Phase label (bottom)
    UILabel *phaseLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 38, tileW - 8, 18)];
    phaseLabel.font = [UIFont boldSystemFontOfSize:12];
    phaseLabel.textAlignment = NSTextAlignmentCenter;
    [container addSubview:phaseLabel];
    tile.phaseLabel = phaseLabel;

    // Pan gesture
    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc]
        initWithTarget:self action:@selector(handlePan:)];
    [vc.view addGestureRecognizer:pan];

    // Tap gesture — toggle compact/expanded
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc]
        initWithTarget:self action:@selector(handleTap:)];
    [vc.view addGestureRecognizer:tap];

    // Long press — config menu
    UILongPressGestureRecognizer *longPress = [[UILongPressGestureRecognizer alloc]
        initWithTarget:self action:@selector(handleLongPress:)];
    [vc.view addGestureRecognizer:longPress];

    // Tag: 0 = ACC, 1 = SPN
    vc.view.tag = [emoji isEqualToString:@"\u2B50"] ? 0 : 1;

    win.hidden = NO;
    tile.window = win;
    return tile;
}

#pragma mark - Spin Handling

- (void)onSpinReceived:(NSNotification *)note {
    SLSpinResult *result = note.userInfo[SLSpinDataKey];
    if (!result) return;

    // --- Event change detection ---
    NSString *eventID = result.gaeSegment;
    if (eventID.length > 0 && self.lastEventID.length > 0 &&
        ![eventID isEqualToString:self.lastEventID]) {
        [self.accTile.tracker reset];
        [self.spnTile.tracker reset];
        // Reset bet decision counters too
        self.accGapIdx = 0;
        self.accSpinInGap = 0;
        SLBetDecisionLoggerRotate();
        NSLog(@"[DebtMonitor] Event changed: %@ -> %@, reset trackers", self.lastEventID, eventID);
    }
    if (eventID.length > 0) {
        self.lastEventID = eventID;
        [[NSUserDefaults standardUserDefaults] setObject:eventID forKey:@"Speeder_DebtEventID"];
    }

    // --- Mission change detection (log only, do NOT reset trackers) ---
    // The game's pity timer does NOT reset on mission level-up,
    // only on ACC/SPN triple. Resetting here caused false resets.
    NSString *mission = [NSString stringWithFormat:@"%ld", (long)result.accumMissionIndex];
    if (mission.length > 0 && self.lastMission.length > 0 &&
        ![mission isEqualToString:self.lastMission]) {
        NSLog(@"[DebtMonitor] Mission changed: %@ -> %@ (no reset)", self.lastMission, mission);
    }
    if (mission.length > 0) {
        self.lastMission = mission;
        [[NSUserDefaults standardUserDefaults] setObject:mission forKey:@"Speeder_DebtMission"];
    }

    // --- Detect triples and classify type ---
    BOOL isTriple = (result.reel1 && [result.reel1 isEqualToString:result.reel2] &&
                     [result.reel2 isEqualToString:result.reel3]);
    BOOL isAccTriple = isTriple && [result.reel1 isEqualToString:kSLSymbolAccumulation];
    BOOL isSpnTriple = isTriple && [result.reel1 isEqualToString:kSLSymbolSpins];

    // Determine the real triple type string for prev_real_triple tracking.
    // Only "real" triples count: attack/steal/shield/spins/accumulation (not coin/goldSack).
    NSString *realTripleType = nil;
    if (isTriple) {
        NSString *r1 = result.reel1;
        if ([r1 isEqualToString:kSLSymbolAccumulation] ||
            [r1 isEqualToString:kSLSymbolSpins]        ||
            [r1 isEqualToString:kSLSymbolAttack]       ||
            [r1 isEqualToString:kSLSymbolSteal]        ||
            [r1 isEqualToString:kSLSymbolShield]) {
            realTripleType = r1;
        }
    }

    // --- Count symbols per reel ---
    NSArray *reels = @[result.reel1 ?: @"", result.reel2 ?: @"", result.reel3 ?: @""];
    NSInteger accSymbols = 0;
    NSInteger spnSymbols = 0;
    for (NSString *r in reels) {
        if ([r isEqualToString:kSLSymbolAccumulation]) accSymbols++;
        if ([r isEqualToString:kSLSymbolSpins])        spnSymbols++;
    }

    // --- Latest GAE state for tile display ---
    self.accTile.latestMission = result.accumMissionIndex;
    self.spnTile.latestMission = result.accumMissionIndex;
    double accumPct = 0.0;
    if (result.accumTotal > 0) {
        accumPct = (double)result.accumCurrent / (double)result.accumTotal * 100.0;
    }
    self.accTile.latestAccumPct = accumPct;
    self.spnTile.latestAccumPct = accumPct;

    // --- Feed trackers ---
    // ACC: primary=accSymbols (sa_acc), secondary=spnSymbols (sa_spn for COMBO second gate)
    SLDebtPhase prevAccPhase = self.accTile.tracker.phase;
    self.accSpinInGap++;
    [self.accTile.tracker onSpin:isAccTriple
                  realTripleType:realTripleType
                         primary:accSymbols
                       secondary:spnSymbols];

    // --- Log this spin's bet decision (BEFORE the gap_idx increments on triple) ---
    // The CSV row reflects the state AFTER the spin was processed (including catch detection).
    SLBetDecisionLoggerAppend(result, self.accTile.tracker, self.accGapIdx, self.accSpinInGap);

    // If this spin was the ACC triple, advance gap counter and reset spin-in-gap
    if (isAccTriple) {
        self.accGapIdx++;
        self.accSpinInGap = 0;
    }

    // SPN: primary=spnSymbols (ss_spn), no secondary gate
    SLDebtPhase prevSpnPhase = self.spnTile.tracker.phase;
    [self.spnTile.tracker onSpin:isSpnTriple
                  realTripleType:realTripleType
                         primary:spnSymbols
                       secondary:0];

    // --- Update UI ---
    [self updateTileUI:self.accTile];
    [self updateTileUI:self.spnTile];

    // --- Haptic on phase transition to BetNow ---
    if ((self.accTile.tracker.phase == SLDebtPhaseBetNow && prevAccPhase != SLDebtPhaseBetNow) ||
        (self.spnTile.tracker.phase == SLDebtPhaseBetNow && prevSpnPhase != SLDebtPhaseBetNow)) {
        [self.haptic impactOccurred];
    }

    // --- Glow control ---
    [self updateGlow:self.accTile];
    [self updateGlow:self.spnTile];

    [self saveState];

    // Refresh debt table if it's open
    [[NSNotificationCenter defaultCenter] postNotificationName:@"SLDebtSpinDidProcess" object:nil];
}

#pragma mark - UI Update

- (void)updateTileUI:(SLDebtTile *)tile {
    SLDebtTracker *t = tile.tracker;
    NSInteger ruleCount = (NSInteger)t.config.rules.count;

    // Top row: emoji + sa_spins / MIN effective threshold
    NSInteger minThresh = [t minEffectiveThreshold];
    if (minThresh <= 0) minThresh = 110;  // fallback if no eligible rules
    tile.spinLabel.text = [NSString stringWithFormat:@"%@ %ld/%ld",
                           tile.emoji, (long)t.saSpins, (long)minThresh];

    // Mission badge (top-right, tiny)
    if (tile.latestMission > 0) {
        tile.missionBadge.text = [NSString stringWithFormat:@"M%ld", (long)tile.latestMission];
        tile.missionBadge.hidden = tile.compact;
    } else {
        tile.missionBadge.hidden = YES;
    }

    // Middle row: rate display — acc | spn for ACC ensemble (if any rule uses spn gate),
    // or just acc rate for SPN tracker
    double accRate = [t accumRate];
    double spnRate = [t spnRate];

    BOOL anyRuleUsesSpn = NO;
    for (SLDebtRule *r in t.config.rules) {
        if (r.spnRateGate > 0.0) { anyRuleUsesSpn = YES; break; }
    }

    if (anyRuleUsesSpn) {
        tile.rateLabel.text = [NSString stringWithFormat:@"%.2f|%.2f", accRate, spnRate];
    } else {
        // SPN tile or non-COMBO ACC: show single rate
        tile.rateLabel.text = [NSString stringWithFormat:@"%.2f", accRate];
    }
    tile.rateLabel.hidden = tile.compact;

    // Rate label color: green if any rule's primary gate is met (signal of "rate is hot enough")
    BOOL rateIsHot = NO;
    for (SLDebtRule *r in t.config.rules) {
        if (r.rateGate > 0.0 && accRate >= r.rateGate) { rateIsHot = YES; break; }
    }
    tile.rateLabel.textColor = rateIsHot
        ? [UIColor colorWithRed:0.3 green:0.9 blue:0.3 alpha:1.0]
        : [UIColor colorWithWhite:0.55 alpha:1.0];

    // Background bar: accum_pct fill behind the rate row, color shifts at 60%/80%
    [self updateProgressBar:tile];

    // Phase label
    NSInteger nFiring = t.firingRuleCount;
    switch (t.phase) {
        case SLDebtPhaseWaiting:
            tile.phaseLabel.text = @"WAIT";
            tile.phaseLabel.textColor = [UIColor colorWithRed:0.4 green:0.4 blue:0.4 alpha:1.0];
            tile.container.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.06].CGColor;
            tile.container.layer.borderWidth = 1.0;
            break;
        case SLDebtPhaseSoon:
            tile.phaseLabel.text = @"SOON";
            tile.phaseLabel.textColor = [UIColor colorWithRed:1.0 green:0.55 blue:0.0 alpha:1.0];
            tile.container.layer.borderColor = [UIColor colorWithRed:1.0 green:0.55 blue:0.0 alpha:0.85].CGColor;
            tile.container.layer.borderWidth = 1.5;
            break;
        case SLDebtPhaseWatch:
            tile.phaseLabel.text = @"ALERT";
            tile.phaseLabel.textColor = [UIColor colorWithRed:1.0 green:0.78 blue:0.0 alpha:1.0];
            tile.container.layer.borderColor = tile.watchBorderColor.CGColor;
            tile.container.layer.borderWidth = 1.5;
            break;
        case SLDebtPhaseBetNow: {
            tile.phaseLabel.text = (ruleCount > 1)
                ? [NSString stringWithFormat:@"BET (%ld/%ld)", (long)nFiring, (long)ruleCount]
                : @"BET";
            // Intensity scales with firing rule count
            UIColor *betColor = tile.glowColor;
            if (nFiring >= 8) {
                // Brighter for high confidence
                betColor = [UIColor colorWithRed:0.4 green:1.0 blue:0.5 alpha:1.0];
            }
            tile.phaseLabel.textColor = betColor;
            tile.container.layer.borderColor = betColor.CGColor;
            tile.container.layer.borderWidth = 2.0;
            break;
        }
        case SLDebtPhaseRest:
            tile.phaseLabel.text = [NSString stringWithFormat:@"REST %ld", (long)t.cooldownRemaining];
            tile.phaseLabel.textColor = [UIColor colorWithRed:0.7 green:0.5 blue:0.3 alpha:1.0];
            tile.container.layer.borderColor = [UIColor colorWithRed:0.7 green:0.5 blue:0.3 alpha:0.7].CGColor;
            tile.container.layer.borderWidth = 1.5;
            break;
    }

    // Tile sizing (compact/expanded)
    CGRect f = tile.window.frame;
    f.size.height = tile.compact ? 30 : 60;
    f.size.width  = tile.compact ? 56 : 90;
    tile.window.frame = f;
    tile.container.frame = CGRectMake(0, 0, f.size.width, f.size.height);
}

- (void)updateProgressBar:(SLDebtTile *)tile {
    if (!tile.progressBar) return;
    double pct = MAX(0, MIN(100, tile.latestAccumPct));
    CGFloat fillWidth = (tile.container.frame.size.width - 8) * (pct / 100.0);
    CGRect rateFrame = tile.rateLabel.frame;
    tile.progressBar.frame = CGRectMake(rateFrame.origin.x, rateFrame.origin.y, fillWidth, rateFrame.size.height);
    tile.progressBar.hidden = (tile.compact || pct <= 0);

    // Color: green/yellow/red based on the "gets harder" finding
    UIColor *barColor;
    if (pct >= 80.0) {
        barColor = [UIColor colorWithRed:0.7 green:0.15 blue:0.15 alpha:0.30]; // red — late mission, gaps 40% longer
    } else if (pct >= 60.0) {
        barColor = [UIColor colorWithRed:0.8 green:0.6 blue:0.1 alpha:0.25];   // amber
    } else {
        barColor = [UIColor colorWithRed:0.2 green:0.5 blue:0.3 alpha:0.20];   // green
    }
    tile.progressBar.backgroundColor = barColor;
}

#pragma mark - Glow Animation

- (void)updateGlow:(SLDebtTile *)tile {
    BOOL shouldGlow = (tile.tracker.phase == SLDebtPhaseBetNow);

    if (shouldGlow && !tile.glowing) {
        tile.glowing = YES;
        [self startGlow:tile];
    } else if (!shouldGlow && tile.glowing) {
        tile.glowing = NO;
        [self stopGlow:tile];
    }
}

- (void)startGlow:(SLDebtTile *)tile {
    CALayer *layer = tile.container.layer;
    layer.shadowColor = tile.glowColor.CGColor;
    layer.shadowOffset = CGSizeZero;
    layer.shadowOpacity = 0.0;
    layer.shadowRadius = 0;

    CABasicAnimation *opacityAnim = [CABasicAnimation animationWithKeyPath:@"shadowOpacity"];
    opacityAnim.fromValue = @(0.3);
    opacityAnim.toValue = @(1.0);
    opacityAnim.duration = 0.6;
    opacityAnim.autoreverses = YES;
    opacityAnim.repeatCount = HUGE_VALF;
    opacityAnim.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionEaseInEaseOut];
    [layer addAnimation:opacityAnim forKey:@"glowOpacity"];

    CABasicAnimation *radiusAnim = [CABasicAnimation animationWithKeyPath:@"shadowRadius"];
    radiusAnim.fromValue = @(4);
    radiusAnim.toValue = @(16);
    radiusAnim.duration = 0.6;
    radiusAnim.autoreverses = YES;
    radiusAnim.repeatCount = HUGE_VALF;
    radiusAnim.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionEaseInEaseOut];
    [layer addAnimation:radiusAnim forKey:@"glowRadius"];
}

- (void)stopGlow:(SLDebtTile *)tile {
    CALayer *layer = tile.container.layer;
    [layer removeAnimationForKey:@"glowOpacity"];
    [layer removeAnimationForKey:@"glowRadius"];
    layer.shadowOpacity = 0;
    layer.shadowRadius = 0;
}

#pragma mark - Gestures

- (SLDebtTile *)tileForView:(UIView *)view {
    return (view.tag == 0) ? self.accTile : self.spnTile;
}

- (void)handlePan:(UIPanGestureRecognizer *)pan {
    SLDebtTile *tile = [self tileForView:pan.view];
    if (pan.state == UIGestureRecognizerStateBegan ||
        pan.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [pan translationInView:pan.view];
        CGRect f = tile.window.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        tile.window.frame = f;
        [pan setTranslation:CGPointZero inView:pan.view];
    }
    if (pan.state == UIGestureRecognizerStateEnded) {
        [self savePosition:tile];
    }
}

- (void)handleTap:(UITapGestureRecognizer *)tap {
    SLDebtTile *tile = [self tileForView:tap.view];
    tile.compact = !tile.compact;
    [self updateTileUI:tile];
}

- (void)handleLongPress:(UILongPressGestureRecognizer *)lp {
    if (lp.state != UIGestureRecognizerStateBegan) return;
    SLDebtTile *tile = [self tileForView:lp.view];
    [self showConfigMenuForTile:tile];
}


#pragma mark - Config Menu

- (UIWindow *)settingsPresentationWindowForScene:(UIWindowScene *)scene {
    if (!self.settingsWindow || self.settingsWindow.windowScene != scene) {
        UIWindow *sw = [[UIWindow alloc] initWithWindowScene:scene];
        sw.frame = scene.coordinateSpace.bounds;
        sw.windowLevel = UIWindowLevelAlert + 350;
        sw.backgroundColor = [UIColor clearColor];
        UIViewController *vc = [[UIViewController alloc] init];
        vc.view.backgroundColor = [UIColor clearColor];
        sw.rootViewController = vc;
        self.settingsWindow = sw;
    }
    self.settingsWindow.hidden = NO;
    return self.settingsWindow;
}

- (void)applyConfigToTile:(SLDebtTile *)tile config:(SLDebtTrackerConfig *)newConfig {
    tile.tracker.config = newConfig;
    [tile.tracker reset];
    [self stopGlow:tile];
    tile.glowing = NO;
    [self updateTileUI:tile];
    [self saveState];
}

- (void)showConfigMenuForTile:(SLDebtTile *)tile {
    SLDebtTracker *t = tile.tracker;
    BOOL isAcc = (tile == self.accTile);
    NSString *title = isAcc ? @"ACC Tracker (16-rule)" : @"SPN Tracker";

    // Build status string with current state
    double accR = [t accumRate];
    double spnR = [t spnRate];
    NSString *phaseStr = @"WAIT";
    switch (t.phase) {
        case SLDebtPhaseWaiting: phaseStr = @"WAIT"; break;
        case SLDebtPhaseSoon:    phaseStr = @"SOON"; break;
        case SLDebtPhaseWatch:   phaseStr = @"ALERT"; break;
        case SLDebtPhaseBetNow:  phaseStr = [NSString stringWithFormat:@"BET (%ld/%lu)",
                                              (long)t.firingRuleCount, (unsigned long)t.config.rules.count]; break;
        case SLDebtPhaseRest:    phaseStr = [NSString stringWithFormat:@"REST %ld", (long)t.cooldownRemaining]; break;
    }
    NSString *stats = [NSString stringWithFormat:
        @"sa_spins: %ld\nacc_rate: %.3f\nspn_rate: %.3f\nslope_8:  %+.4f\nslope_10: %+.4f\nprev_gap: %ld\nprev_triple: %@\nphase: %@\nrules: %lu",
        (long)t.saSpins, accR, spnR,
        [t slopeForWindow:8], [t slopeForWindow:10],
        (long)t.prevGapLength,
        t.prevRealTriple ?: @"(unknown)",
        phaseStr,
        (unsigned long)t.config.rules.count];

    UIAlertController *sheet = [UIAlertController alertControllerWithTitle:title
                                                                   message:stats
                                                            preferredStyle:UIAlertControllerStyleActionSheet];

    UIWindow *presWin = [self settingsPresentationWindowForScene:
                         (UIWindowScene *)tile.window.windowScene];

    void (^dismiss)(void) = ^{ self.settingsWindow.hidden = YES; };

    // --- Presets ---
    if (isAcc) {
        [sheet addAction:[UIAlertAction actionWithTitle:@"Ensemble (16 rules) — 62/178 @ 10.95mb [DEFAULT]"
                                                 style:UIAlertActionStyleDefault
                                               handler:^(UIAlertAction *a) {
            [self applyConfigToTile:tile config:[SLDebtTrackerConfig accEnsembleDefaults]];
            dismiss();
        }]];
        [sheet addAction:[UIAlertAction actionWithTitle:@"COMBO only — 42/178 @ 9.3mb"
                                                 style:UIAlertActionStyleDefault
                                               handler:^(UIAlertAction *a) {
            [self applyConfigToTile:tile config:[SLDebtTrackerConfig accComboOnlyDefaults]];
            dismiss();
        }]];
        [sheet addAction:[UIAlertAction actionWithTitle:@"Baseline 130/0.30 — 31/178 @ 17.1mb"
                                                 style:UIAlertActionStyleDefault
                                               handler:^(UIAlertAction *a) {
            [self applyConfigToTile:tile config:[SLDebtTrackerConfig accBaselineDefaults]];
            dismiss();
        }]];
    } else {
        [sheet addAction:[UIAlertAction actionWithTitle:@"Sniper 120/0.25 — 22/213 @ 9.5mb [DEFAULT]"
                                                 style:UIAlertActionStyleDefault
                                               handler:^(UIAlertAction *a) {
            [self applyConfigToTile:tile config:[SLDebtTrackerConfig spnDefaults]];
            dismiss();
        }]];
    }

    // --- Reset ---
    [sheet addAction:[UIAlertAction actionWithTitle:@"Reset Counter"
                                             style:UIAlertActionStyleDestructive
                                           handler:^(UIAlertAction *a) {
        [t reset];
        [self stopGlow:tile];
        tile.glowing = NO;
        [self updateTileUI:tile];
        [self saveState];
        dismiss();
    }]];

    [sheet addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                             style:UIAlertActionStyleCancel
                                           handler:^(UIAlertAction *a) { dismiss(); }]];

    sheet.popoverPresentationController.sourceView = presWin.rootViewController.view;
    sheet.popoverPresentationController.sourceRect = CGRectMake(
        presWin.bounds.size.width / 2, presWin.bounds.size.height - 40, 1, 1);

    [presWin.rootViewController presentViewController:sheet animated:YES completion:nil];
}

// showThresholdEditorForTile removed: 16-rule ensemble doesn't have a single threshold to edit.
// Future: implement a per-rule editor or "tap-to-expand panel" with rule details.

#pragma mark - Persistence

- (void)saveState {
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    [ud setObject:[self.accTile.tracker stateDictionary] forKey:self.accTile.defaultsKey];
    [ud setObject:[self.spnTile.tracker stateDictionary] forKey:self.spnTile.defaultsKey];
}

- (void)restoreState {
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    [self.accTile.tracker restoreFromDictionary:[ud dictionaryForKey:self.accTile.defaultsKey]];
    [self.spnTile.tracker restoreFromDictionary:[ud dictionaryForKey:self.spnTile.defaultsKey]];
}

- (void)savePosition:(SLDebtTile *)tile {
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    [ud setDouble:tile.window.frame.origin.x forKey:tile.posXKey];
    [ud setDouble:tile.window.frame.origin.y forKey:tile.posYKey];
}

#pragma mark - Show / Hide

- (void)show {
    self.accTile.window.hidden = NO;
    self.spnTile.window.hidden = NO;
}

- (void)hide {
    self.accTile.window.hidden = YES;
    self.spnTile.window.hidden = YES;
}

- (SLDebtTracker *)accTracker { return self.accTile.tracker; }
- (SLDebtTracker *)spnTracker { return self.spnTile.tracker; }

- (void)resetAccTracker {
    [self.accTile.tracker reset];
    [self stopGlow:self.accTile];
    self.accTile.glowing = NO;
    [self updateTileUI:self.accTile];
    [self saveState];
}

- (void)resetSpnTracker {
    [self.spnTile.tracker reset];
    [self stopGlow:self.spnTile];
    self.spnTile.glowing = NO;
    [self updateTileUI:self.spnTile];
    [self saveState];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
