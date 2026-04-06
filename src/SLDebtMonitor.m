#import <UIKit/UIKit.h>
#import "SLDebtMonitor.h"
#import "SLDebtTracker.h"
#import "SLConstants.h"
#import "SLSpinParser.h"

// ---------------------------------------------------------------------------
//  SLDebtTile — one draggable UIWindow for a single tracker (ACC or SPN)
// ---------------------------------------------------------------------------
@interface SLDebtTile : NSObject
@property (nonatomic, strong) UIWindow *window;
@property (nonatomic, strong) UIView *container;
@property (nonatomic, strong) UILabel *spinLabel;
@property (nonatomic, strong) UILabel *rateLabel;
@property (nonatomic, strong) UILabel *phaseLabel;
@property (nonatomic, strong) SLDebtTracker *tracker;
@property (nonatomic, copy)   NSString *emoji;
@property (nonatomic, copy)   NSString *symbolName;  // which symbol to count (accumulation/spins)
@property (nonatomic, copy)   NSString *defaultsKey;
@property (nonatomic, copy)   NSString *posXKey;
@property (nonatomic, copy)   NSString *posYKey;
@property (nonatomic, assign) BOOL compact;
@property (nonatomic, assign) BOOL glowing;
@property (nonatomic, strong) UIColor *glowColor;
@property (nonatomic, strong) UIColor *watchBorderColor;
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
                                  tracker:[[SLDebtTracker alloc] initWithConfig:[SLDebtTrackerConfig accDefaults]]
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

    NSLog(@"[SpinLogger] DebtMonitor installed (ACC thresh=%ld gate=%.2f, SPN thresh=%ld gate=%.2f)",
          (long)self.accTile.tracker.config.spinThreshold,
          self.accTile.tracker.config.rateGate,
          (long)self.spnTile.tracker.config.spinThreshold,
          self.spnTile.tracker.config.rateGate);
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
    container.clipsToBounds = NO;
    [vc.view addSubview:container];
    tile.container = container;

    // Spin label (top) — emoji + spin count / threshold
    UILabel *spinLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 2, tileW - 8, 18)];
    spinLabel.font = [UIFont boldSystemFontOfSize:13];
    spinLabel.textColor = [UIColor whiteColor];
    spinLabel.textAlignment = NSTextAlignmentCenter;
    [container addSubview:spinLabel];
    tile.spinLabel = spinLabel;

    // Rate label (middle) — accum rate / gate
    UILabel *rateLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 20, tileW - 8, 16)];
    rateLabel.font = [UIFont monospacedDigitSystemFontOfSize:11 weight:UIFontWeightMedium];
    rateLabel.textColor = [UIColor colorWithWhite:0.7 alpha:1.0];
    rateLabel.textAlignment = NSTextAlignmentCenter;
    [container addSubview:rateLabel];
    tile.rateLabel = rateLabel;

    // Phase label (bottom) — WAIT / WATCH / BET NOW
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
        NSLog(@"[DebtMonitor] Event changed: %@ -> %@, reset trackers", self.lastEventID, eventID);
    }
    if (eventID.length > 0) {
        self.lastEventID = eventID;
        [[NSUserDefaults standardUserDefaults] setObject:eventID forKey:@"Speeder_DebtEventID"];
    }

    // --- Mission change detection (GAE level reset) ---
    NSString *mission = [NSString stringWithFormat:@"%ld", (long)result.accumMissionIndex];
    if (mission.length > 0 && self.lastMission.length > 0 &&
        ![mission isEqualToString:self.lastMission]) {
        [self.accTile.tracker reset];
        [self.spnTile.tracker reset];
        NSLog(@"[DebtMonitor] Mission changed: %@ -> %@, reset trackers", self.lastMission, mission);
    }
    if (mission.length > 0) {
        self.lastMission = mission;
        [[NSUserDefaults standardUserDefaults] setObject:mission forKey:@"Speeder_DebtMission"];
    }

    // --- Detect triples ---
    BOOL isTriple = (result.reel1 && [result.reel1 isEqualToString:result.reel2] &&
                     [result.reel2 isEqualToString:result.reel3]);
    BOOL isAccTriple = isTriple && [result.reel1 isEqualToString:kSLSymbolAccumulation];
    BOOL isSpnTriple = isTriple && [result.reel1 isEqualToString:kSLSymbolSpins];

    // --- Count symbols per reel ---
    NSArray *reels = @[result.reel1 ?: @"", result.reel2 ?: @"", result.reel3 ?: @""];
    NSInteger accSymbols = 0;
    NSInteger spnSymbols = 0;
    for (NSString *r in reels) {
        if ([r isEqualToString:kSLSymbolAccumulation]) accSymbols++;
        if ([r isEqualToString:kSLSymbolSpins])        spnSymbols++;
    }

    // --- Feed trackers ---
    SLDebtPhase prevAccPhase = self.accTile.tracker.phase;
    [self.accTile.tracker onSpinWithTargetHit:isAccTriple symbolCount:accSymbols];

    SLDebtPhase prevSpnPhase = self.spnTile.tracker.phase;
    [self.spnTile.tracker onSpinWithTargetHit:isSpnTriple symbolCount:spnSymbols];

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
    NSInteger thresh = t.config.spinThreshold;

    // Top: emoji + spins / threshold
    tile.spinLabel.text = [NSString stringWithFormat:@"%@ %ld/%ld",
                           tile.emoji, (long)t.saSpins, (long)thresh];

    // Middle: accum rate / gate
    double rate = [t accumRate];
    if (t.config.rateGate > 0.0) {
        tile.rateLabel.text = [NSString stringWithFormat:@"%.2f / %.2f", rate, t.config.rateGate];
        if (rate >= t.config.rateGate) {
            tile.rateLabel.textColor = [UIColor colorWithRed:0.3 green:0.9 blue:0.3 alpha:1.0];
        } else {
            tile.rateLabel.textColor = [UIColor colorWithWhite:0.5 alpha:1.0];
        }
    } else {
        tile.rateLabel.text = [NSString stringWithFormat:@"rate: %.2f", rate];
        tile.rateLabel.textColor = [UIColor colorWithWhite:0.5 alpha:1.0];
    }
    tile.rateLabel.hidden = tile.compact;

    // Bottom: phase
    switch (t.phase) {
        case SLDebtPhaseWaiting:
            tile.phaseLabel.text = @"WAIT";
            tile.phaseLabel.textColor = [UIColor colorWithRed:0.3 green:0.7 blue:0.3 alpha:1.0];
            tile.container.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.06].CGColor;
            tile.container.layer.borderWidth = 1.0;
            break;
        case SLDebtPhaseWatch:
            tile.phaseLabel.text = @"ALERT";
            tile.phaseLabel.textColor = [UIColor colorWithRed:1.0 green:0.75 blue:0.0 alpha:1.0];
            tile.container.layer.borderColor = tile.watchBorderColor.CGColor;
            tile.container.layer.borderWidth = 1.5;
            break;
        case SLDebtPhaseBetNow:
            tile.phaseLabel.text = @"BET NOW";
            tile.phaseLabel.textColor = tile.glowColor;
            tile.container.layer.borderColor = tile.glowColor.CGColor;
            tile.container.layer.borderWidth = 2.0;
            break;
    }

    CGRect f = tile.window.frame;
    f.size.height = tile.compact ? 30 : 60;
    f.size.width  = tile.compact ? 56 : 90;
    tile.window.frame = f;
    tile.container.frame = CGRectMake(0, 0, f.size.width, f.size.height);
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

- (void)showConfigMenuForTile:(SLDebtTile *)tile {
    SLDebtTracker *t = tile.tracker;
    SLDebtTrackerConfig *cfg = t.config;
    NSString *title = (tile == self.accTile) ? @"ACC Tracker" : @"SPN Tracker";

    double rate = [t accumRate];
    NSString *stats = [NSString stringWithFormat:
        @"Spins: %ld / %ld\nRate: %.3f / %.2f\nPhase: %@",
        (long)t.saSpins, (long)cfg.spinThreshold,
        rate, cfg.rateGate,
        (t.phase == SLDebtPhaseBetNow ? @"BET NOW" :
         t.phase == SLDebtPhaseWatch ? @"WATCH" : @"WAIT")];

    UIAlertController *sheet = [UIAlertController alertControllerWithTitle:title
                                                                   message:stats
                                                            preferredStyle:UIAlertControllerStyleActionSheet];

    UIWindow *presWin = [self settingsPresentationWindowForScene:
                         (UIWindowScene *)tile.window.windowScene];

    void (^dismiss)(void) = ^{ self.settingsWindow.hidden = YES; };

    [sheet addAction:[UIAlertAction actionWithTitle:@"Edit Thresholds"
                                             style:UIAlertActionStyleDefault
                                           handler:^(UIAlertAction *a) {
        dismiss();
        [self showThresholdEditorForTile:tile];
    }]];

    [sheet addAction:[UIAlertAction actionWithTitle:@"Reset Tracker"
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

- (void)showThresholdEditorForTile:(SLDebtTile *)tile {
    SLDebtTrackerConfig *cfg = tile.tracker.config;
    NSString *title = (tile == self.accTile) ? @"ACC Thresholds" : @"SPN Thresholds";

    UIAlertController *alert = [UIAlertController alertControllerWithTitle:title
                                                                  message:@"Spin threshold + rate gate"
                                                           preferredStyle:UIAlertControllerStyleAlert];

    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Spin Threshold";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.spinThreshold];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Rate Gate (0.30)";
        tf.text = [NSString stringWithFormat:@"%.2f", cfg.rateGate];
        tf.keyboardType = UIKeyboardTypeDecimalPad;
    }];

    UIWindow *presWin = [self settingsPresentationWindowForScene:
                         (UIWindowScene *)tile.window.windowScene];

    void (^dismiss)(void) = ^{ self.settingsWindow.hidden = YES; };

    [alert addAction:[UIAlertAction actionWithTitle:@"Save" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) {
        cfg.spinThreshold = [alert.textFields[0].text integerValue];
        cfg.rateGate      = [alert.textFields[1].text doubleValue];
        [self updateTileUI:tile];
        [self saveState];
        dismiss();
    }]];

    [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:^(UIAlertAction *a) {
        dismiss();
    }]];

    [presWin.rootViewController presentViewController:alert animated:YES completion:nil];
}

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
