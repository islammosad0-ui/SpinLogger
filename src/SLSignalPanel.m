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
static const int kTypeCount = 6;
static const CGFloat kExpandedH = 28 + (20 * 6) + 28;  // header + 6 rows + idx footer

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

// Footer: idx display
@property (nonatomic, strong) UILabel *idxLabel;

@property (nonatomic, strong) NSTimer *refreshTimer;
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
    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    // Container
    UIView *container = [[UIView alloc] initWithFrame:CGRectMake(0, 0, kPanelW, kExpandedH)];
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

    // Header: "ACC+SP: [TIER]"
    UILabel *headerLbl = [self makeLbl:CGRectMake(8, 0, kPanelW - 30, kHeaderH)
                                  size:11 bold:YES color:[UIColor colorWithWhite:0.7 alpha:1]];
    headerLbl.text = @"SIGNALS: ---";
    [header addSubview:headerLbl];
    self.headerLabel = headerLbl;

    UILabel *arrow = [self makeLbl:CGRectMake(kPanelW - 22, 0, 18, kHeaderH)
                              size:9 bold:NO color:[UIColor colorWithWhite:0.5 alpha:1]];
    arrow.text = @"\u25BC";
    arrow.tag = 99;
    [header addSubview:arrow];

    // Tap / pan gestures
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(toggleExpand)];
    [header addGestureRecognizer:tap];
    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(handlePan:)];
    [vc.view addGestureRecognizer:pan];

    // Body: per-type rows
    UIView *body = [[UIView alloc] initWithFrame:CGRectMake(0, kHeaderH, kPanelW, kExpandedH - kHeaderH)];
    [container addSubview:body];
    self.bodyView = body;
    body.hidden = YES;

    NSArray *typeNames = @[@"ACC+SP", @"SHIELD", @"ATTACK", @"STEAL", @"COIN", @"GOLD"];
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

    // Footer: idx display
    CGFloat footerY = kTypeCount * kRowH + 4;
    self.idxLabel = [self makeLbl:CGRectMake(6, footerY, kPanelW - 12, 20)
                             size:9 bold:NO color:[UIColor colorWithWhite:0.4 alpha:1]];
    self.idxLabel.text = @"idx: (-,-,-)";
    [body addSubview:self.idxLabel];

    win.hidden = NO;
    self.window = win;

    // 1 Hz refresh
    self.refreshTimer = [NSTimer scheduledTimerWithTimeInterval:1.0
                                                          target:self
                                                        selector:@selector(refreshLabels)
                                                        userInfo:nil
                                                         repeats:YES];

    NSLog(@"[SpinLogger] Signal Panel installed (per-type heat mode)");
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
    SLTypeHeat h4 = s.heatCoin;
    SLTypeHeat h5 = s.heatGoldSack;

    NSString *tier = s.betTierString ?: @"---";
    UIColor *tColor = tierColor(s.betTier);
    NSString *reason = s.signalReason ?: @"-";
    int32_t r1 = s.lastR1Idx, r2 = s.lastR2Idx, r3 = s.lastR3Idx;

    dispatch_async(dispatch_get_main_queue(), ^{
        SLTypeHeat heats[] = {h0, h1, h2, h3, h4, h5};

        // Header: primary target tier
        self.headerLabel.text = [NSString stringWithFormat:@"ACC+SP: %@ | %@", tier, reason];
        self.headerLabel.textColor = tColor;

        // Per-type heat bars
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

        // Footer: idx
        self.idxLabel.text = [NSString stringWithFormat:@"idx: (%d, %d, %d)", r1, r2, r3];
    });
}

// ============================================================
//  Expand / Collapse
// ============================================================
- (void)toggleExpand {
    self.expanded = !self.expanded;
    CGRect f = self.window.frame;
    f.size.height = self.expanded ? kExpandedH : kHeaderH;
    self.bodyView.hidden = !self.expanded;

    UILabel *arrow = [self.headerBar viewWithTag:99];
    arrow.text = self.expanded ? @"\u25B2" : @"\u25BC";

    [UIView animateWithDuration:0.2 animations:^{
        self.window.frame = f;
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

- (void)dealloc {
    [self.refreshTimer invalidate];
    self.refreshTimer = nil;
}

@end
