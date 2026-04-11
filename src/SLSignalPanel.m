#import "SLSignalPanel.h"
#import "SLMemoryScanner.h"
#import "SLConstants.h"

// ---------------------------------------------------------------------------
//  Symbol enum → emoji mapping (matches SlotSymbol C# enum order)
// ---------------------------------------------------------------------------
static NSString *emojiForSymbol(int32_t sym) {
    switch (sym) {
        case 0:  return @"⬜";  // none
        case 1:  return @"🪙";  // coin
        case 2:  return @"💰";  // goldSack
        case 3:  return @"🔨";  // attack
        case 4:  return @"🐷";  // steal
        case 5:  return @"🛡";  // shield
        case 6:  return @"⚡";  // spins
        case 7:  return @"🃏";  // mystic
        case 8:  return @"🐾";  // petxp
        case 9:  return @"🦴";  // petfood
        case 10: return @"📦";  // woodenchest
        case 11: return @"✨";  // goldenchest
        case 12: return @"🔮";  // magicalchest
        case 13: return @"⭐";  // accumulation
        case 14: return @"🎰";  // freeSpins
        case 15: return @"🎯";  // betBonanza
        default: return @"❓";
    }
}

// ---------------------------------------------------------------------------
//  Color helpers
// ---------------------------------------------------------------------------
static UIColor *pityColor(float progress) {
    if (progress >= 0.8f) return [UIColor colorWithRed:0.96 green:0.26 blue:0.21 alpha:1]; // red
    if (progress >= 0.6f) return [UIColor colorWithRed:1.00 green:0.76 blue:0.03 alpha:1]; // yellow
    return [UIColor colorWithRed:0.30 green:0.69 blue:0.31 alpha:1];                       // green
}

static UIColor *tellColor(BOOL active) {
    return active
        ? [UIColor colorWithRed:0.96 green:0.26 blue:0.21 alpha:1]   // red
        : [UIColor colorWithWhite:0.35 alpha:1];                       // dim gray
}

// ---------------------------------------------------------------------------
//  Panel constants
// ---------------------------------------------------------------------------
static const CGFloat kPanelW = 185;
static const CGFloat kHeaderH = 28;
static const CGFloat kExpandedH = 230;

// ---------------------------------------------------------------------------
//  SLSignalPanel
// ---------------------------------------------------------------------------
@interface SLSignalPanel ()
@property (nonatomic, strong) UIWindow *window;
@property (nonatomic, strong) UIView *container;
@property (nonatomic, strong) UIView *headerBar;
@property (nonatomic, strong) UIView *bodyView;
@property (nonatomic, assign) BOOL expanded;

// Labels
@property (nonatomic, strong) UILabel *headerLabel;
@property (nonatomic, strong) UILabel *pityLabel;
@property (nonatomic, strong) UIView  *pityBarBg;
@property (nonatomic, strong) UIView  *pityBarFill;
@property (nonatomic, strong) UILabel *failLabel;
@property (nonatomic, strong) UILabel *stateLabel;
@property (nonatomic, strong) UILabel *gridTopLabel;
@property (nonatomic, strong) UILabel *gridMidLabel;
@property (nonatomic, strong) UILabel *gridBotLabel;
@property (nonatomic, strong) UILabel *stripLabel;
@property (nonatomic, strong) UILabel *tellLabel;
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
    container.layer.cornerRadius = 12;
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

    UILabel *headerLbl = [self makeLabel:CGRectMake(8, 0, kPanelW - 30, kHeaderH)
                                    size:11 bold:YES color:[UIColor colorWithWhite:0.7 alpha:1]];
    headerLbl.text = @"🎰 SIGNALS";
    [header addSubview:headerLbl];
    self.headerLabel = headerLbl;

    UILabel *arrow = [self makeLabel:CGRectMake(kPanelW - 25, 0, 20, kHeaderH)
                                size:10 bold:NO color:[UIColor colorWithWhite:0.5 alpha:1]];
    arrow.text = @"▼";
    arrow.tag = 99;
    [header addSubview:arrow];

    // Tap to toggle
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(toggleExpand)];
    [header addGestureRecognizer:tap];

    // Drag gesture
    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(handlePan:)];
    [vc.view addGestureRecognizer:pan];

    // Body (hidden when collapsed)
    CGFloat y = kHeaderH + 4;
    UIView *body = [[UIView alloc] initWithFrame:CGRectMake(0, kHeaderH, kPanelW, kExpandedH - kHeaderH)];
    [container addSubview:body];
    self.bodyView = body;
    body.hidden = YES;

    // — PITY progress bar —
    CGFloat bx = 8, bw = kPanelW - 16;
    self.pityLabel = [self makeLabel:CGRectMake(bx, 4, bw, 14) size:10 bold:YES
                              color:[UIColor colorWithRed:0.30 green:0.69 blue:0.31 alpha:1]];
    self.pityLabel.text = @"PITY ░░░░░░░░ 0%";
    [body addSubview:self.pityLabel];

    UIView *barBg = [[UIView alloc] initWithFrame:CGRectMake(bx, 20, bw, 6)];
    barBg.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
    barBg.layer.cornerRadius = 3;
    [body addSubview:barBg];
    self.pityBarBg = barBg;

    UIView *barFill = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 0, 6)];
    barFill.backgroundColor = [UIColor colorWithRed:0.30 green:0.69 blue:0.31 alpha:1];
    barFill.layer.cornerRadius = 3;
    [barBg addSubview:barFill];
    self.pityBarFill = barFill;

    // — Fail counter —
    self.failLabel = [self makeLabel:CGRectMake(bx, 30, bw, 14) size:9 bold:NO
                              color:[UIColor colorWithWhite:0.5 alpha:1]];
    self.failLabel.text = @"FAIL: 0/0 (session: 0)";
    [body addSubview:self.failLabel];

    // — State: bet, spin#, shields —
    self.stateLabel = [self makeLabel:CGRectMake(bx, 46, bw, 14) size:9 bold:NO
                               color:[UIColor colorWithRed:0.53 green:0.81 blue:0.98 alpha:1]];
    self.stateLabel.text = @"BET×1  #0  🛡0";
    [body addSubview:self.stateLabel];

    // — 3×3 Grid —
    UIView *gridSep = [[UIView alloc] initWithFrame:CGRectMake(bx, 64, bw, 1)];
    gridSep.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
    [body addSubview:gridSep];

    self.gridTopLabel = [self makeLabel:CGRectMake(bx, 68, bw, 18) size:14 bold:NO
                                 color:[UIColor colorWithWhite:0.6 alpha:1]];
    self.gridTopLabel.textAlignment = NSTextAlignmentCenter;
    self.gridTopLabel.text = @"❓ ❓ ❓";
    [body addSubview:self.gridTopLabel];

    self.gridMidLabel = [self makeLabel:CGRectMake(bx, 86, bw, 20) size:16 bold:YES
                                 color:[UIColor whiteColor]];
    self.gridMidLabel.textAlignment = NSTextAlignmentCenter;
    self.gridMidLabel.text = @"❓ ❓ ❓";
    [body addSubview:self.gridMidLabel];

    self.gridBotLabel = [self makeLabel:CGRectMake(bx, 106, bw, 18) size:14 bold:NO
                                 color:[UIColor colorWithWhite:0.6 alpha:1]];
    self.gridBotLabel.textAlignment = NSTextAlignmentCenter;
    self.gridBotLabel.text = @"❓ ❓ ❓";
    [body addSubview:self.gridBotLabel];

    // — Strip positions —
    UIView *stripSep = [[UIView alloc] initWithFrame:CGRectMake(bx, 128, bw, 1)];
    stripSep.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
    [body addSubview:stripSep];

    self.stripLabel = [self makeLabel:CGRectMake(bx, 132, bw, 14) size:9 bold:NO
                               color:[UIColor colorWithWhite:0.45 alpha:1]];
    self.stripLabel.text = @"STRIP: -/- -/- -/-";
    [body addSubview:self.stripLabel];

    // — Tell indicators —
    UIView *tellSep = [[UIView alloc] initWithFrame:CGRectMake(bx, 150, bw, 1)];
    tellSep.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
    [body addSubview:tellSep];

    self.tellLabel = [self makeLabel:CGRectMake(bx, 154, bw, 38) size:9 bold:NO
                              color:[UIColor colorWithWhite:0.4 alpha:1]];
    self.tellLabel.numberOfLines = 2;
    self.tellLabel.text = @"DYN:❌ NEAR:❌\nFRZ:❌ SWAP:❌";
    [body addSubview:self.tellLabel];

    win.hidden = NO;
    self.window = win;

    // Listen for scan notifications
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onScanUpdate:)
                                                 name:SLMemoryScanNotification
                                               object:nil];

    NSLog(@"[SpinLogger] Signal Panel installed");
}

// ============================================================
//  Notification handler — update all labels from snapshot
// ============================================================
- (void)onScanUpdate:(NSNotification *)note {
    SLScanSnapshot *s = note.userInfo[SLScanSnapshotKey];
    if (!s) return;

    dispatch_async(dispatch_get_main_queue(), ^{
        // Pity bar
        float pity = [s pityProgress];
        int pityPct = (int)(pity * 100);
        UIColor *pc = pityColor(pity);
        self.pityLabel.text = [NSString stringWithFormat:@"PITY %d%%", pityPct];
        self.pityLabel.textColor = pc;
        self.pityBarFill.backgroundColor = pc;
        CGFloat fillW = self.pityBarBg.frame.size.width * pity;
        self.pityBarFill.frame = CGRectMake(0, 0, fillW, 6);

        // Fail counters
        self.failLabel.text = [NSString stringWithFormat:@"FAIL: %d/%d (session: %d)",
                               s.failCounterGlobal, s.failThreshold, s.failCounter];

        // State
        self.stateLabel.text = [NSString stringWithFormat:@"BET×%d  #%d  🛡%d",
                                s.betState, s.spinNumber, s.shields];

        // 3×3 Grid
        self.gridTopLabel.text = [NSString stringWithFormat:@"%@ %@ %@",
                                  emojiForSymbol(s.top1), emojiForSymbol(s.top2), emojiForSymbol(s.top3)];
        self.gridMidLabel.text = [NSString stringWithFormat:@"%@ %@ %@",
                                  emojiForSymbol(s.sym1), emojiForSymbol(s.sym2), emojiForSymbol(s.sym3)];
        self.gridBotLabel.text = [NSString stringWithFormat:@"%@ %@ %@",
                                  emojiForSymbol(s.bot1), emojiForSymbol(s.bot2), emojiForSymbol(s.bot3)];

        // Strip positions
        self.stripLabel.text = [NSString stringWithFormat:@"STRIP: %d/%d  %d/%d  %d/%d",
                                s.stripIdx1, s.stripLen1, s.stripIdx2, s.stripLen2, s.stripIdx3, s.stripLen3];

        // Tell indicators
        NSMutableAttributedString *tells = [[NSMutableAttributedString alloc] init];
        [self appendTell:tells label:@"DYN" active:s.hasDynamicResults];
        [tells appendAttributedString:[[NSAttributedString alloc] initWithString:@"  "]];
        [self appendTell:tells label:@"NEAR" active:s.hasNearWin];
        [tells appendAttributedString:[[NSAttributedString alloc] initWithString:@"\n"]];
        [self appendTell:tells label:@"FRZ" active:s.hasFreezeContext];
        [tells appendAttributedString:[[NSAttributedString alloc] initWithString:@"  "]];
        [self appendTell:tells label:@"SWAP" active:s.hasReplacements];
        self.tellLabel.attributedText = tells;

        // Update collapsed header with pity summary
        self.headerLabel.text = [NSString stringWithFormat:@"🎰 P:%d%% #%d", pityPct, s.spinNumber];
        self.headerLabel.textColor = pc;

        // Flash panel border on high-pity
        if (pity >= 0.8f) {
            self.container.layer.borderColor = pc.CGColor;
            self.container.layer.borderWidth = 2;
        } else {
            self.container.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.08].CGColor;
            self.container.layer.borderWidth = 1;
        }
    });
}

- (void)appendTell:(NSMutableAttributedString *)str label:(NSString *)label active:(BOOL)active {
    UIColor *c = tellColor(active);
    NSString *icon = active ? @"🔴" : @"❌";
    NSDictionary *attrs = @{
        NSForegroundColorAttributeName: c,
        NSFontAttributeName: [UIFont systemFontOfSize:9]
    };
    [str appendAttributedString:[[NSAttributedString alloc]
        initWithString:[NSString stringWithFormat:@"%@:%@ ", label, icon] attributes:attrs]];
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
    arrow.text = self.expanded ? @"▲" : @"▼";

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
- (UILabel *)makeLabel:(CGRect)frame size:(CGFloat)size bold:(BOOL)bold color:(UIColor *)color {
    UILabel *lbl = [[UILabel alloc] initWithFrame:frame];
    lbl.font = bold ? [UIFont boldSystemFontOfSize:size] : [UIFont systemFontOfSize:size];
    lbl.textColor = color;
    lbl.backgroundColor = [UIColor clearColor];
    return lbl;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
