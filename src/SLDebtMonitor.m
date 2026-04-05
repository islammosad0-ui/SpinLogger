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
@property (nonatomic, strong) UILabel *debtLabel;
@property (nonatomic, strong) UILabel *progressLabel;
@property (nonatomic, strong) UILabel *phaseLabel;
@property (nonatomic, strong) SLDebtTracker *tracker;
@property (nonatomic, copy)   NSString *emoji;
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
@property (nonatomic, strong) UIImpactFeedbackGenerator *haptic;
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

    NSLog(@"[SpinLogger] DebtMonitor installed (ACC target=%ld, SPN target=%ld)",
          (long)self.accTile.tracker.config.target,
          (long)self.spnTile.tracker.config.target);
}

#pragma mark - Build Tile

- (SLDebtTile *)buildTileInScene:(UIWindowScene *)scene
                           emoji:(NSString *)emoji
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

    // Debt label (top) — emoji + debt
    UILabel *debtLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 2, tileW - 8, 18)];
    debtLabel.font = [UIFont boldSystemFontOfSize:13];
    debtLabel.textColor = [UIColor whiteColor];
    debtLabel.textAlignment = NSTextAlignmentCenter;
    debtLabel.text = [NSString stringWithFormat:@"%@ 0", emoji];
    [container addSubview:debtLabel];
    tile.debtLabel = debtLabel;

    // Progress label (middle) — saSpins / watchPoint
    UILabel *progressLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 20, tileW - 8, 16)];
    progressLabel.font = [UIFont monospacedDigitSystemFontOfSize:11 weight:UIFontWeightMedium];
    progressLabel.textColor = [UIColor colorWithWhite:0.7 alpha:1.0];
    progressLabel.textAlignment = NSTextAlignmentCenter;
    progressLabel.text = @"0 / 80";
    [container addSubview:progressLabel];
    tile.progressLabel = progressLabel;

    // Phase label (bottom) — WAIT / WATCH / BET NOW
    UILabel *phaseLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 38, tileW - 8, 18)];
    phaseLabel.font = [UIFont boldSystemFontOfSize:12];
    phaseLabel.textAlignment = NSTextAlignmentCenter;
    phaseLabel.text = @"WAIT";
    phaseLabel.textColor = [UIColor colorWithWhite:0.4 alpha:1.0];
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

    // --- Detect triples ---
    BOOL isTriple = (result.reel1 && [result.reel1 isEqualToString:result.reel2] &&
                     [result.reel2 isEqualToString:result.reel3]);
    BOOL isAccTriple = isTriple && [result.reel1 isEqualToString:kSLSymbolAccumulation];
    BOOL isSpnTriple = isTriple && [result.reel1 isEqualToString:kSLSymbolSpins];
    BOOL isCombatTriple = isTriple && ([result.reel1 isEqualToString:kSLSymbolAttack] ||
                                       [result.reel1 isEqualToString:kSLSymbolSteal] ||
                                       [result.reel1 isEqualToString:kSLSymbolShield] ||
                                       [result.reel1 isEqualToString:kSLSymbolSpins]);

    // ACC tracker: target = accumulation triple, other = any combat/spins triple
    SLDebtPhase prevAccPhase = self.accTile.tracker.phase;
    [self.accTile.tracker onSpin:result
                  isTargetTriple:isAccTriple
                  isOtherTriple:(isCombatTriple && !isAccTriple)];

    // SPN tracker: target = spins triple, other = any combat triple (not spins itself)
    SLDebtPhase prevSpnPhase = self.spnTile.tracker.phase;
    BOOL isNonSpnCombat = isTriple && ([result.reel1 isEqualToString:kSLSymbolAttack] ||
                                       [result.reel1 isEqualToString:kSLSymbolSteal] ||
                                       [result.reel1 isEqualToString:kSLSymbolShield] ||
                                       [result.reel1 isEqualToString:kSLSymbolAccumulation]);
    [self.spnTile.tracker onSpin:result
                  isTargetTriple:isSpnTriple
                  isOtherTriple:isNonSpnCombat];

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
}

#pragma mark - UI Update

- (void)updateTileUI:(SLDebtTile *)tile {
    SLDebtTracker *t = tile.tracker;
    NSInteger wp = [t watchPoint];

    NSString *debtSign = (t.debt >= 0) ? @"+" : @"";
    tile.debtLabel.text = [NSString stringWithFormat:@"%@ %@%ld", tile.emoji, debtSign, (long)t.debt];

    tile.progressLabel.text = [NSString stringWithFormat:@"%ld / %ld", (long)t.saSpins, (long)wp];
    tile.progressLabel.hidden = tile.compact;

    switch (t.phase) {
        case SLDebtPhaseWaiting:
            tile.phaseLabel.text = @"WAIT";
            tile.phaseLabel.textColor = [UIColor colorWithWhite:0.4 alpha:1.0];
            tile.container.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.06].CGColor;
            tile.container.layer.borderWidth = 1.0;
            break;
        case SLDebtPhaseWatch:
            tile.phaseLabel.text = @"WATCH";
            tile.phaseLabel.textColor = [UIColor colorWithRed:1.0 green:0.75 blue:0.0 alpha:1.0];
            tile.container.layer.borderColor = tile.watchBorderColor.CGColor;
            tile.container.layer.borderWidth = 1.5;
            break;
        case SLDebtPhaseBetNow:
            tile.phaseLabel.text = @"BET NOW";
            tile.phaseLabel.textColor = tile.glowColor;
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

- (void)showConfigMenuForTile:(SLDebtTile *)tile {
    SLDebtTrackerConfig *cfg = tile.tracker.config;
    NSString *title = (tile == self.accTile) ? @"ACC Config" : @"SPN Config";

    UIAlertController *alert = [UIAlertController alertControllerWithTitle:title
                                                                  message:nil
                                                           preferredStyle:UIAlertControllerStyleAlert];

    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Target (gap)";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.target];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Floor Base";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.floorBase];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Floor Min";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.floorMin];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Quiet Min";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.quietMin];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Quiet Max";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.quietMax];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Bet Window";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.betWindow];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];

    [alert addAction:[UIAlertAction actionWithTitle:@"Save" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) {
        cfg.target    = [alert.textFields[0].text integerValue];
        cfg.floorBase = [alert.textFields[1].text integerValue];
        cfg.floorMin  = [alert.textFields[2].text integerValue];
        cfg.quietMin  = [alert.textFields[3].text integerValue];
        cfg.quietMax  = [alert.textFields[4].text integerValue];
        cfg.betWindow = [alert.textFields[5].text integerValue];
        [self updateTileUI:tile];
        [self saveState];
    }]];

    [alert addAction:[UIAlertAction actionWithTitle:@"Reset Tracker" style:UIAlertActionStyleDestructive handler:^(UIAlertAction *a) {
        [tile.tracker reset];
        [self stopGlow:tile];
        tile.glowing = NO;
        [self updateTileUI:tile];
        [self saveState];
    }]];

    [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];

    [tile.window.rootViewController presentViewController:alert animated:YES completion:nil];
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

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
