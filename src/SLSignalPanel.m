#import "SLSignalPanel.h"
#import "SLMemoryScanner.h"
#import "SLIdxStrategy.h"
#import "SLConstants.h"

// ---------------------------------------------------------------------------
//  Panel layout constants
// ---------------------------------------------------------------------------
static const CGFloat kPanelW = 200;
static const CGFloat kHeaderH = 28;
static const CGFloat kRowH = 20;
static const int kTypeCount = 4;   // ACC+SP, SHIELD, ATTACK, STEAL
static const CGFloat kReasonRowH = 16;
static const CGFloat kExpandedH = 28 + (20 * 4) + 16 + 24;  // header + 4 rows + reason + idx footer

// Heat bar colors
static UIColor *colorForHeat(int score, int maxScore) {
    if (maxScore <= 0) return [UIColor colorWithWhite:0.4 alpha:1];
    float ratio = (float)score / (float)maxScore;
    if (ratio >= 0.5)  return [UIColor colorWithRed:1.0 green:0.25 blue:0.25 alpha:1];  // hot red
    if (ratio >= 0.25) return [UIColor colorWithRed:1.0 green:0.55 blue:0.0 alpha:1];   // orange
    if (ratio > 0)     return [UIColor colorWithRed:1.0 green:0.85 blue:0.0 alpha:1];   // yellow
    if (ratio >= -0.15) return [UIColor colorWithWhite:0.5 alpha:1];                      // gray neutral
    return [UIColor colorWithRed:0.3 green:0.5 blue:0.9 alpha:1];                        // cold blue
}

// Tier -> short color for the main recommendation
static UIColor *tierColor(SLBetTier tier) {
    switch (tier) {
        case SLBetTierMAX:    return [UIColor colorWithRed:1.0 green:0.25 blue:0.25 alpha:1];
        case SLBetTierBIG:    return [UIColor colorWithRed:1.0 green:0.55 blue:0.0 alpha:1];
        case SLBetTierNORMAL: return [UIColor colorWithWhite:0.7 alpha:1];
        case SLBetTierSMALL:  return [UIColor colorWithRed:0.4 green:0.65 blue:1.0 alpha:1];
        case SLBetTierMIN:    return [UIColor colorWithWhite:0.4 alpha:1];
    }
    return [UIColor whiteColor];
}

// ---------------------------------------------------------------------------
//  SLSignalPanel — Per-type heat HUD
// ---------------------------------------------------------------------------
@interface SLSignalPanel ()
@property (nonatomic, strong) UIWindow *window;
@property (nonatomic, strong) UIView *container;
@property (nonatomic, strong) UIView *headerBar;
@property (nonatomic, strong) UIView *bodyView;
@property (nonatomic, assign) BOOL expanded;

// Header
@property (nonatomic, strong) UILabel *headerLabel;

// Per-type rows: label + heat bar + score label
@property (nonatomic, strong) NSArray<UILabel *> *typeLabels;
@property (nonatomic, strong) NSArray<UIView *> *heatBars;
@property (nonatomic, strong) NSArray<UIView *> *heatBarFills;
@property (nonatomic, strong) NSArray<UILabel *> *scoreLabels;

// Reason + footer
@property (nonatomic, strong) UILabel *reasonLabel;
@property (nonatomic, strong) UILabel *idxLabel;

// Settings overlay
@property (nonatomic, strong) UIView *settingsView;
@property (nonatomic, strong) UILabel *scorerValueLabel;
@property (nonatomic, strong) UILabel *profileValueLabel;
@property (nonatomic, assign) BOOL settingsShown;

@end

@implementation SLSignalPanel

+ (instancetype)shared {
    static SLSignalPanel *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (void)install {
    UIWindowScene *scene = nil;
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            if (s.activationState == UISceneActivationStateForegroundActive) break;
        }
    }
    if (!scene) return;

    self.expanded = NO;

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat startX = screen.size.width - kPanelW - 8;
    CGFloat startY = 60;

    // Window
    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(startX, startY, kPanelW, kHeaderH);
    win.windowLevel = UIWindowLevelAlert + 200;
    win.backgroundColor = [UIColor clearColor];
    win.clipsToBounds = YES;
    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    // Container — starts at header-only height, resizes on expand
    UIView *container = [[UIView alloc] initWithFrame:CGRectMake(0, 0, kPanelW, kHeaderH)];
    container.backgroundColor = [UIColor colorWithRed:0.05 green:0.07 blue:0.12 alpha:0.95];
    container.layer.cornerRadius = 10;
    container.layer.borderWidth = 1;
    container.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.08].CGColor;
    container.clipsToBounds = YES;
    [vc.view addSubview:container];
    self.container = container;

    // Header bar
    UIView *header = [[UIView alloc] initWithFrame:CGRectMake(0, 0, kPanelW, kHeaderH)];
    header.backgroundColor = [UIColor colorWithRed:0.08 green:0.10 blue:0.16 alpha:1];
    [container addSubview:header];
    self.headerBar = header;

    // Header: "[V2/SNP] MAX  L1:+8 L2:+3 =+11"
    UILabel *headerLbl = [self makeLbl:CGRectMake(8, 0, kPanelW - 30, kHeaderH)
                                  size:11 bold:YES color:[UIColor colorWithWhite:0.7 alpha:1]];
    headerLbl.text = @"--- | 0";
    headerLbl.adjustsFontSizeToFitWidth = YES;
    headerLbl.minimumScaleFactor = 0.7;
    [header addSubview:headerLbl];
    self.headerLabel = headerLbl;

    UILabel *arrow = [self makeLbl:CGRectMake(kPanelW - 22, 0, 18, kHeaderH)
                              size:9 bold:NO color:[UIColor colorWithWhite:0.5 alpha:1]];
    arrow.text = @"\u25BC";
    arrow.tag = 99;
    [header addSubview:arrow];

    // Tap / long-press / pan gestures
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(toggleExpand)];
    [header addGestureRecognizer:tap];
    UILongPressGestureRecognizer *longPress = [[UILongPressGestureRecognizer alloc]
                                                initWithTarget:self action:@selector(toggleSettings:)];
    longPress.minimumPressDuration = 0.5;
    [header addGestureRecognizer:longPress];
    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(handlePan:)];
    [vc.view addGestureRecognizer:pan];

    // Body: per-type rows
    UIView *body = [[UIView alloc] initWithFrame:CGRectMake(0, kHeaderH, kPanelW, kExpandedH - kHeaderH)];
    [container addSubview:body];
    self.bodyView = body;
    body.hidden = YES;

    NSArray *typeNames = @[@"ACC+SP", @"SHIELD", @"ATTACK", @"STEAL"];
    NSMutableArray *tLabels = [NSMutableArray array];
    NSMutableArray *bars = [NSMutableArray array];
    NSMutableArray *fills = [NSMutableArray array];
    NSMutableArray *sLabels = [NSMutableArray array];

    CGFloat barX = 56;
    CGFloat barW = 80;
    CGFloat barH = 10;

    for (int i = 0; i < kTypeCount; i++) {
        CGFloat y = i * kRowH + 2;

        // Type name label
        UILabel *tl = [self makeLbl:CGRectMake(6, y, 48, kRowH)
                               size:9 bold:YES color:[UIColor colorWithWhite:0.6 alpha:1]];
        tl.text = typeNames[i];
        [body addSubview:tl];
        [tLabels addObject:tl];

        // Heat bar background
        UIView *barBg = [[UIView alloc] initWithFrame:CGRectMake(barX, y + 5, barW, barH)];
        barBg.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
        barBg.layer.cornerRadius = 3;
        barBg.clipsToBounds = YES;
        [body addSubview:barBg];
        [bars addObject:barBg];

        // Heat bar fill (starts at center for bidirectional)
        UIView *fill = [[UIView alloc] initWithFrame:CGRectMake(barW / 2, 0, 0, barH)];
        fill.backgroundColor = [UIColor colorWithWhite:0.5 alpha:1];
        fill.layer.cornerRadius = 2;
        [barBg addSubview:fill];
        [fills addObject:fill];

        // Center line marker
        UIView *center = [[UIView alloc] initWithFrame:CGRectMake(barW / 2 - 0.5, 0, 1, barH)];
        center.backgroundColor = [UIColor colorWithWhite:0.35 alpha:1];
        [barBg addSubview:center];

        // Score label
        UILabel *sl = [self makeLbl:CGRectMake(barX + barW + 4, y, 50, kRowH)
                               size:9 bold:NO color:[UIColor colorWithWhite:0.5 alpha:1]];
        sl.text = @"0";
        [body addSubview:sl];
        [sLabels addObject:sl];
    }

    self.typeLabels = tLabels;
    self.heatBars = bars;
    self.heatBarFills = fills;
    self.scoreLabels = sLabels;

    // Reason row: which signals fired
    CGFloat reasonY = kTypeCount * kRowH + 2;
    self.reasonLabel = [self makeLbl:CGRectMake(6, reasonY, kPanelW - 12, kReasonRowH)
                                size:8 bold:NO color:[UIColor colorWithWhite:0.4 alpha:1]];
    self.reasonLabel.text = @"-";
    self.reasonLabel.adjustsFontSizeToFitWidth = YES;
    self.reasonLabel.minimumScaleFactor = 0.6;
    [body addSubview:self.reasonLabel];

    // Footer: idx display
    CGFloat footerY = reasonY + kReasonRowH + 2;
    self.idxLabel = [self makeLbl:CGRectMake(6, footerY, kPanelW - 12, 20)
                             size:9 bold:NO color:[UIColor colorWithWhite:0.4 alpha:1]];
    self.idxLabel.text = @"idx: (-,-,-)";
    [body addSubview:self.idxLabel];

    // Settings overlay (hidden by default, shown on long-press)
    CGFloat settingsH = 2 * kRowH + 12;
    UIView *settings = [[UIView alloc] initWithFrame:CGRectMake(0, kHeaderH, kPanelW, settingsH)];
    settings.backgroundColor = [UIColor colorWithRed:0.10 green:0.08 blue:0.18 alpha:0.98];
    settings.hidden = YES;
    [container addSubview:settings];
    self.settingsView = settings;
    self.settingsShown = NO;

    // Settings row 1: Scorer
    UILabel *scorerLbl = [self makeLbl:CGRectMake(10, 4, 70, kRowH)
                                   size:10 bold:YES color:[UIColor colorWithWhite:0.55 alpha:1]];
    scorerLbl.text = @"SCORER";
    [settings addSubview:scorerLbl];

    UILabel *scorerVal = [self makeLbl:CGRectMake(kPanelW - 60, 4, 50, kRowH)
                                   size:10 bold:YES color:[UIColor colorWithRed:0.5 green:0.8 blue:1.0 alpha:1]];
    scorerVal.text = [SLIdxStrategy shared].scorerName ?: @"V1";
    scorerVal.textAlignment = NSTextAlignmentRight;
    scorerVal.userInteractionEnabled = YES;
    [settings addSubview:scorerVal];
    self.scorerValueLabel = scorerVal;

    UITapGestureRecognizer *tapScorer = [[UITapGestureRecognizer alloc]
                                          initWithTarget:self action:@selector(settingsTapScorer)];
    [scorerVal addGestureRecognizer:tapScorer];

    // Settings row 2: Profile
    UILabel *profileLbl = [self makeLbl:CGRectMake(10, 4 + kRowH, 70, kRowH)
                                    size:10 bold:YES color:[UIColor colorWithWhite:0.55 alpha:1]];
    profileLbl.text = @"PROFILE";
    [settings addSubview:profileLbl];

    UILabel *profileVal = [self makeLbl:CGRectMake(kPanelW - 60, 4 + kRowH, 50, kRowH)
                                    size:10 bold:YES color:[UIColor colorWithRed:1.0 green:0.7 blue:0.3 alpha:1]];
    profileVal.text = [SLIdxStrategy shared].profileName ?: @"BAL";
    profileVal.textAlignment = NSTextAlignmentRight;
    profileVal.userInteractionEnabled = YES;
    [settings addSubview:profileVal];
    self.profileValueLabel = profileVal;

    UITapGestureRecognizer *tapProfile = [[UITapGestureRecognizer alloc]
                                           initWithTarget:self action:@selector(settingsTapProfile)];
    [profileVal addGestureRecognizer:tapProfile];

    // Separator line
    UIView *sep = [[UIView alloc] initWithFrame:CGRectMake(10, kRowH + 3, kPanelW - 20, 0.5)];
    sep.backgroundColor = [UIColor colorWithWhite:0.25 alpha:1];
    [settings addSubview:sep];

    win.hidden = NO;
    self.window = win;

    // Instant refresh on strategy update — no polling delay
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(refreshLabels)
                                                 name:SLStrategyUpdatedNotification
                                               object:nil];

    NSLog(@"[SpinLogger] Signal Panel installed (notification-driven refresh)");
}

// ============================================================
//  Refresh — 1 Hz
// ============================================================
- (void)refreshLabels {
    SLIdxStrategy *s = [SLIdxStrategy shared];

    // Copy into individual vars — C arrays can't be captured by blocks
    SLTypeHeat h0 = s.heatAccSpins;
    SLTypeHeat h1 = s.heatShield;
    SLTypeHeat h2 = s.heatAttack;
    SLTypeHeat h3 = s.heatSteal;

    NSString *tier = s.betTierString ?: @"---";
    UIColor *tColor = tierColor(s.betTier);
    NSString *reason = s.signalReason ?: @"-";
    NSString *scorer = s.scorerName ?: @"V1";
    NSString *profile = s.profileName ?: @"BAL";
    NSInteger l1 = s.layer1Score;
    NSInteger l2 = s.layer2Score;
    NSInteger combined = s.compositeScore;
    int32_t r1 = s.lastR1Idx, r2 = s.lastR2Idx, r3 = s.lastR3Idx;

    dispatch_async(dispatch_get_main_queue(), ^{
        SLTypeHeat heats[] = {h0, h1, h2, h3};

        // Header: "[V2/SNP] MAX  L1:+8 L2:+3 =+11"
        self.headerLabel.text = [NSString stringWithFormat:@"[%@/%@] %@  L1:%+ld L2:%+ld =%+ld",
                                  scorer, profile, tier, (long)l1, (long)l2, (long)combined];
        self.headerLabel.textColor = tColor;

        // Per-type heat bars (4 rows: ACC+SP, SHIELD, ATTACK, STEAL)
        CGFloat barW = 80;
        for (int i = 0; i < kTypeCount; i++) {
            SLTypeHeat h = heats[i];
            UIColor *color = colorForHeat(h.score, h.maxScore);

            // Fill bar: bidirectional from center
            CGFloat center = barW / 2.0;
            CGFloat maxFill = center;
            CGFloat fillW = 0;
            CGFloat fillX = center;

            if (h.maxScore > 0 && h.score != 0) {
                float ratio = (float)ABS(h.score) / (float)h.maxScore;
                fillW = ratio * maxFill;
                if (fillW < 3) fillW = 3;  // minimum visible
                if (h.score > 0) {
                    fillX = center;
                } else {
                    fillX = center - fillW;
                }
            }

            UIView *fill = self.heatBarFills[i];
            fill.frame = CGRectMake(fillX, 0, fillW, 10);
            fill.backgroundColor = color;

            // Score text
            self.scoreLabels[i].text = [NSString stringWithFormat:@"%+d", h.score];
            self.scoreLabels[i].textColor = color;

            // Highlight type label if hot
            self.typeLabels[i].textColor = (h.score >= 2) ? color :
                                           [UIColor colorWithWhite:0.5 alpha:1];
        }

        // Reason row: which signals fired
        self.reasonLabel.text = reason;

        // Footer: idx
        self.idxLabel.text = [NSString stringWithFormat:@"idx: (%d,%d,%d)", r1, r2, r3];
    });
}

// ============================================================
//  Expand / Collapse
// ============================================================
- (void)toggleExpand {
    // If settings are showing, dismiss them first
    if (self.settingsShown) {
        [self dismissSettings];
        return;
    }

    self.expanded = !self.expanded;
    CGFloat h = self.expanded ? kExpandedH : kHeaderH;
    CGRect wf = self.window.frame;
    wf.size.height = h;
    self.bodyView.hidden = !self.expanded;

    UILabel *arrow = [self.headerBar viewWithTag:99];
    arrow.text = self.expanded ? @"\u25B2" : @"\u25BC";

    [UIView animateWithDuration:0.2 animations:^{
        self.window.frame = wf;
        CGRect cf = self.container.frame;
        cf.size.height = h;
        self.container.frame = cf;
    }];
}

// ============================================================
//  Dragging
// ============================================================
- (void)handlePan:(UIPanGestureRecognizer *)pan {
    if (pan.state == UIGestureRecognizerStateBegan ||
        pan.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [pan translationInView:pan.view];
        CGRect f = self.window.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        self.window.frame = f;
        [pan setTranslation:CGPointZero inView:pan.view];
    }
}

// ============================================================
//  Visibility
// ============================================================
- (void)show  { self.window.hidden = NO; }
- (void)hide  { self.window.hidden = YES; }

// ============================================================
//  Label factory
// ============================================================
- (UILabel *)makeLbl:(CGRect)frame size:(CGFloat)size bold:(BOOL)bold color:(UIColor *)color {
    UILabel *lbl = [[UILabel alloc] initWithFrame:frame];
    lbl.font = bold ? [UIFont boldSystemFontOfSize:size] : [UIFont systemFontOfSize:size];
    lbl.textColor = color;
    lbl.backgroundColor = [UIColor clearColor];
    return lbl;
}

// ============================================================
//  Settings overlay (long-press on header)
// ============================================================
- (void)toggleSettings:(UILongPressGestureRecognizer *)gesture {
    if (gesture.state != UIGestureRecognizerStateBegan) return;

    self.settingsShown = !self.settingsShown;

    if (self.settingsShown) {
        // Sync labels with current values
        SLIdxStrategy *s = [SLIdxStrategy shared];
        self.scorerValueLabel.text = s.scorerName ?: @"V1";
        self.profileValueLabel.text = s.profileName ?: @"BAL";

        // Hide body, show settings
        self.bodyView.hidden = YES;
        self.settingsView.hidden = NO;

        CGFloat settingsH = 2 * kRowH + 12;
        CGFloat totalH = kHeaderH + settingsH;
        CGRect wf = self.window.frame;
        wf.size.height = totalH;

        [UIView animateWithDuration:0.2 animations:^{
            self.window.frame = wf;
            CGRect cf = self.container.frame;
            cf.size.height = totalH;
            self.container.frame = cf;
        }];

        // Flash header purple
        UIView *flash = self.headerBar;
        [UIView animateWithDuration:0.1 animations:^{
            flash.backgroundColor = [UIColor colorWithRed:0.15 green:0.10 blue:0.25 alpha:1];
        } completion:^(BOOL finished) {
            [UIView animateWithDuration:0.3 animations:^{
                flash.backgroundColor = [UIColor colorWithRed:0.08 green:0.10 blue:0.16 alpha:1];
            }];
        }];
    } else {
        [self dismissSettings];
    }
}

- (void)dismissSettings {
    self.settingsShown = NO;
    self.settingsView.hidden = YES;

    // Restore body visibility based on expanded state
    self.bodyView.hidden = !self.expanded;
    CGFloat h = self.expanded ? kExpandedH : kHeaderH;
    CGRect wf = self.window.frame;
    wf.size.height = h;

    [UIView animateWithDuration:0.2 animations:^{
        self.window.frame = wf;
        CGRect cf = self.container.frame;
        cf.size.height = h;
        self.container.frame = cf;
    }];

    [self refreshLabels];
}

- (void)settingsTapScorer {
    SLIdxStrategy *s = [SLIdxStrategy shared];
    [s cycleScorer];
    self.scorerValueLabel.text = s.scorerName;

    // Quick flash
    [UIView animateWithDuration:0.08 animations:^{
        self.scorerValueLabel.alpha = 0.3;
    } completion:^(BOOL finished) {
        [UIView animateWithDuration:0.15 animations:^{
            self.scorerValueLabel.alpha = 1.0;
        }];
    }];
}

- (void)settingsTapProfile {
    SLIdxStrategy *s = [SLIdxStrategy shared];
    [s cycleProfile];
    self.profileValueLabel.text = s.profileName;

    // Quick flash
    [UIView animateWithDuration:0.08 animations:^{
        self.profileValueLabel.alpha = 0.3;
    } completion:^(BOOL finished) {
        [UIView animateWithDuration:0.15 animations:^{
            self.profileValueLabel.alpha = 1.0;
        }];
    }];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
