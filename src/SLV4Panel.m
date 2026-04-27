#import "SLV4Panel.h"
#import "SLV4Policy.h"
#import "SLV4Features.h"
#import "SLV4Model.h"

NSString *const SLV4PanelRefreshNotification = @"SLV4PanelRefreshNotification";

// Persistence keys
static NSString *const kSLV4PanelOriginKey  = @"SLV4Panel.origin";
static NSString *const kSLV4PanelVisibleKey = @"SLV4Panel.visible";

// ---------------------------------------------------------------------------
//  Layout — deliberately minimal. Collapsed row shows everything you need to
//  act on (pos / predicted window / fire verdict); expanded reveals a simple
//  3-row policy selector.
// ---------------------------------------------------------------------------
static const CGFloat kW          = 220;
static const CGFloat kHeaderH    = 32;
static const CGFloat kRowH       = 20;
static const CGFloat kFooterH    = 20;
static const int     kRowCount   = 3;
static const CGFloat kCollapsedH = 32;
static const CGFloat kExpandedH  = 32 + (20 * 3) + 20;

static UIColor *colorFireBg(void)   { return [UIColor colorWithRed:0.05 green:0.14 blue:0.08 alpha:0.96]; }
static UIColor *colorWaitBg(void)   { return [UIColor colorWithRed:0.07 green:0.09 blue:0.13 alpha:0.96]; }
static UIColor *colorGreen(void)    { return [UIColor colorWithRed:0.30 green:0.90 blue:0.45 alpha:1]; }
static UIColor *colorAmber(void)    { return [UIColor colorWithRed:1.00 green:0.72 blue:0.22 alpha:1]; }
static UIColor *colorRed(void)      { return [UIColor colorWithRed:1.00 green:0.32 blue:0.32 alpha:1]; }
static UIColor *colorDim(void)      { return [UIColor colorWithWhite:0.50 alpha:1]; }
static UIColor *colorMuted(void)    { return [UIColor colorWithWhite:0.32 alpha:1]; }

@interface SLV4Panel ()
@property (nonatomic, strong) UIWindow *window;
@property (nonatomic, strong) UIView *container;
@property (nonatomic, strong) UIView *headerBar;
@property (nonatomic, strong) UIView *body;
@property (nonatomic, assign) BOOL expanded;

// Header:  K5dyn     POS 34   PRED ≤5    [FIRE]
@property (nonatomic, strong) UILabel *labelCfg;      // active policy shortname
@property (nonatomic, strong) UILabel *labelPos;      // "POS 34"
@property (nonatomic, strong) UILabel *labelPred;     // "≤5" / ">10"
@property (nonatomic, strong) UILabel *labelVerdict;  // "[FIRE]" / "[WAIT]"

// 3 simple rows: [arrow][NAME][status]
@property (nonatomic, strong) NSMutableArray<UIView *> *rows;
@property (nonatomic, strong) NSMutableArray<UILabel *> *rowNames;
@property (nonatomic, strong) NSMutableArray<UILabel *> *rowStatus;
@property (nonatomic, strong) NSMutableArray<UILabel *> *rowArrow;

// Footer: session stats
@property (nonatomic, strong) UILabel *footerLabel;

// Per-session counters
@property (nonatomic, assign) NSInteger firesTotal;
@property (nonatomic, assign) NSInteger catchesTotal;
@property (nonatomic, assign) NSInteger cyclesFiredIn;
@property (nonatomic, assign) BOOL firedThisCycle;
@property (nonatomic, assign) int lastT;

// Haptic transition tracking
@property (nonatomic, assign) BOOL wasOn;
@end

@implementation SLV4Panel

+ (instancetype)shared {
    static SLV4Panel *inst;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ inst = [[self alloc] init]; });
    return inst;
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

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat startX = screen.size.width - kW - 8;
    CGFloat startY = 140;

    // Restore persisted origin (clamped to screen).
    NSDictionary *saved = [[NSUserDefaults standardUserDefaults] dictionaryForKey:kSLV4PanelOriginKey];
    if (saved[@"x"] && saved[@"y"]) {
        CGFloat sx = [saved[@"x"] doubleValue];
        CGFloat sy = [saved[@"y"] doubleValue];
        if (sx > -10 && sy > -10 &&
            sx < screen.size.width - 10 && sy < screen.size.height - 10) {
            startX = sx; startY = sy;
        }
    }

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(startX, startY, kW, kCollapsedH);
    win.windowLevel = UIWindowLevelAlert + 199;
    win.backgroundColor = [UIColor clearColor];
    win.clipsToBounds = YES;
    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    UIView *container = [[UIView alloc] initWithFrame:CGRectMake(0, 0, kW, kCollapsedH)];
    container.backgroundColor = colorWaitBg();
    container.layer.cornerRadius = 10;
    container.layer.borderWidth = 1;
    container.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.08].CGColor;
    container.clipsToBounds = YES;
    [vc.view addSubview:container];
    self.container = container;

    // Header — single row with POS / PRED / verdict
    UIView *header = [[UIView alloc] initWithFrame:CGRectMake(0, 0, kW, kHeaderH)];
    header.backgroundColor = [UIColor colorWithWhite:0 alpha:0.18];
    [container addSubview:header];
    self.headerBar = header;

    //   6      54          48        44         46
    // [cfg]  POS 34     ≤5       [FIRE]
    self.labelCfg = [self lbl:CGRectMake(6, 0, 54, kHeaderH) size:11 bold:YES color:colorAmber()];
    self.labelCfg.text = @"—";
    [header addSubview:self.labelCfg];

    self.labelPos = [self lbl:CGRectMake(60, 0, 54, kHeaderH) size:12 bold:YES color:[UIColor whiteColor]];
    self.labelPos.text = @"POS —";
    [header addSubview:self.labelPos];

    self.labelPred = [self lbl:CGRectMake(114, 0, 44, kHeaderH) size:11 bold:NO color:colorDim()];
    self.labelPred.text = @"—";
    self.labelPred.textAlignment = NSTextAlignmentCenter;
    [header addSubview:self.labelPred];

    self.labelVerdict = [self lbl:CGRectMake(kW - 58, 0, 52, kHeaderH)
                              size:11 bold:YES color:colorDim()];
    self.labelVerdict.text = @"—";
    self.labelVerdict.textAlignment = NSTextAlignmentRight;
    [header addSubview:self.labelVerdict];

    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc]
                                     initWithTarget:self action:@selector(toggleExpand)];
    [header addGestureRecognizer:tap];
    UILongPressGestureRecognizer *lp = [[UILongPressGestureRecognizer alloc]
                                           initWithTarget:self action:@selector(handleLongPress:)];
    lp.minimumPressDuration = 0.6;
    [header addGestureRecognizer:lp];
    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc]
                                      initWithTarget:self action:@selector(handlePan:)];
    [vc.view addGestureRecognizer:pan];

    // Body — 3 rows + footer
    UIView *body = [[UIView alloc] initWithFrame:CGRectMake(0, kHeaderH, kW, kExpandedH - kHeaderH)];
    body.hidden = YES;
    [container addSubview:body];
    self.body = body;

    self.rows = [NSMutableArray array];
    self.rowNames = [NSMutableArray array];
    self.rowStatus = [NSMutableArray array];
    self.rowArrow = [NSMutableArray array];

    for (int i = 0; i < kRowCount; i++) {
        UIView *row = [[UIView alloc] initWithFrame:CGRectMake(0, i * kRowH, kW, kRowH)];
        [body addSubview:row];
        [self.rows addObject:row];

        UILabel *arrow = [self lbl:CGRectMake(6, 0, 14, kRowH) size:10 bold:YES color:[UIColor whiteColor]];
        arrow.text = @"";
        [row addSubview:arrow];
        [self.rowArrow addObject:arrow];

        UILabel *name = [self lbl:CGRectMake(22, 0, 120, kRowH) size:10 bold:NO color:colorDim()];
        name.text = @"—";
        [row addSubview:name];
        [self.rowNames addObject:name];

        UILabel *status = [self lbl:CGRectMake(kW - 60, 0, 54, kRowH) size:10 bold:YES color:colorMuted()];
        status.text = @"—";
        status.textAlignment = NSTextAlignmentRight;
        [row addSubview:status];
        [self.rowStatus addObject:status];

        row.userInteractionEnabled = YES;
        UITapGestureRecognizer *rt = [[UITapGestureRecognizer alloc]
                                         initWithTarget:self action:@selector(handleRowTap:)];
        rt.accessibilityLabel = [NSString stringWithFormat:@"row-%d", i];
        [row addGestureRecognizer:rt];
    }

    UILabel *footer = [self lbl:CGRectMake(6, kRowCount * kRowH + 2, kW - 12, kFooterH - 4)
                             size:9 bold:NO color:colorMuted()];
    footer.text = @"— / —";
    footer.textAlignment = NSTextAlignmentCenter;
    [body addSubview:footer];
    self.footerLabel = footer;

    // Honour persisted visibility pref (default: visible).
    NSUserDefaults *def = [NSUserDefaults standardUserDefaults];
    BOOL wantVisible = [def objectForKey:kSLV4PanelVisibleKey] ? [def boolForKey:kSLV4PanelVisibleKey] : YES;
    win.hidden = !wantVisible;
    self.window = win;

    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onRefreshNotif)
                                                 name:SLV4PanelRefreshNotification
                                               object:nil];
    [self refresh];
    NSLog(@"[SLV4Panel] installed (model loaded: %d)", [SLV4Model shared].isLoaded);
}

- (void)onRefreshNotif {
    [[SLV4Policy shared] evaluate];
    dispatch_async(dispatch_get_main_queue(), ^{ [self refresh]; });
}

// Shortest horizon where p_K clears its threshold — displayed under PRED.
static NSString *SLV4_PredLabel(double p3, double p5, double p10, int t) {
    double thr5 = (t >= 70) ? 0.03
                : (t >= 50) ? 0.04
                : (t >= 30) ? 0.05
                            : 0.08;
    if (p3 >= 0.04)  return @"\u22643";
    if (p5 >= thr5)  return @"\u22645";
    if (p10 >= 0.10) return @"\u226410";
    return @">10";
}

// Short label for the active config — shown in the header so the user always
// knows which policy the FIRE/WAIT verdict reflects. Kept tight so the cfg
// label fits "{policy}·{head}" (e.g. "K5·ANY") without truncating.
static NSString *SLV4_ShortName(SLV4PolicyKind k) {
    switch (k) {
        case SLV4PolicyK5Dyn:   return @"K5";
        case SLV4PolicyTriple:  return @"TRI";
        case SLV4PolicyK10Dyn:  return @"K10";
    }
    return @"?";
}

- (void)refresh {
    SLV4PolicyState s = [[SLV4Policy shared] currentState];
    SLV4Policy *pol = [SLV4Policy shared];
    SLV4Snapshot snap = [[SLV4Features shared] snapshot];
    BOOL loaded = [SLV4Model shared].isLoaded;
    BOOL on = loaded && s.on[pol.activePolicy];

    // ---- Header ----
    // Append head label (e.g. "K5dyn·ANY") so user sees which head is driving.
    NSString *cfgShort = SLV4_ShortName(pol.activePolicy);
    NSString *head = [pol activeHeadName];
    NSString *headTag = [head isEqualToString:@"ANY_VT"] ? @"ANY"
                       : [head isEqualToString:@"SPN"]    ? @"SPN"
                                                          : @"ACC";
    self.labelCfg.text = [NSString stringWithFormat:@"%@\u00b7%@", cfgShort, headTag];
    if (!loaded) {
        self.labelPos.text = @"no model";
        self.labelPos.textColor = colorRed();
        self.labelPred.text = @"";
        self.labelVerdict.text = @"";
    } else {
        self.labelPos.text = [NSString stringWithFormat:@"POS %d", snap.t];
        self.labelPos.textColor = [UIColor whiteColor];

        self.labelPred.text = SLV4_PredLabel(s.p3, s.p5, s.p10, snap.t);
        if (s.p3 >= 0.04)            self.labelPred.textColor = colorGreen();
        else if (s.p5 >= 0.05)       self.labelPred.textColor = colorAmber();
        else if (s.p10 >= 0.10)      self.labelPred.textColor = colorDim();
        else                         self.labelPred.textColor = colorMuted();

        self.labelVerdict.text = on ? @"[FIRE]" : @"[WAIT]";
        self.labelVerdict.textColor = on ? colorGreen() : colorMuted();
    }

    self.container.backgroundColor = on ? colorFireBg() : colorWaitBg();

    // Haptic on FIRE↔WAIT transition
    if (loaded && on != self.wasOn) {
        UIImpactFeedbackStyle style = on ? UIImpactFeedbackStyleHeavy : UIImpactFeedbackStyleLight;
        UIImpactFeedbackGenerator *haptic = [[UIImpactFeedbackGenerator alloc] initWithStyle:style];
        [haptic impactOccurred];
        self.wasOn = on;
    }

    // ---- Rows ----
    SLV4PolicyKind kinds[3] = {SLV4PolicyK5Dyn, SLV4PolicyTriple, SLV4PolicyK10Dyn};
    for (int i = 0; i < kRowCount; i++) {
        SLV4PolicyKind k = kinds[i];
        BOOL rowOn = loaded && s.on[k];
        BOOL isActive = (pol.activePolicy == k);

        UILabel *arrow = self.rowArrow[i];
        UILabel *name = self.rowNames[i];
        UILabel *status = self.rowStatus[i];

        arrow.text = isActive ? @"\u25B6" : @"";  // ▶
        name.text = [SLV4Policy nameForKind:k];
        name.textColor = isActive ? [UIColor whiteColor]
                                  : (rowOn ? colorGreen() : colorDim());
        name.font = isActive ? [UIFont boldSystemFontOfSize:10]
                             : [UIFont systemFontOfSize:10];

        status.text = rowOn ? @"FIRE" : @"WAIT";
        status.textColor = rowOn ? colorGreen() : colorMuted();
    }

    // ---- Footer: catch rate of the active policy ----
    // Cycle-close detection — t drops from >0 back to 0 after a VT lands.
    if (snap.t == 0 && self.lastT > 0) {
        if (self.firedThisCycle) self.catchesTotal++;
        self.firedThisCycle = NO;
    }
    self.lastT = snap.t;

    if (loaded && s.on[pol.activePolicy]) {
        self.firesTotal++;
        if (!self.firedThisCycle) { self.firedThisCycle = YES; self.cyclesFiredIn++; }
    }
    double rate = self.cyclesFiredIn ? (double)self.catchesTotal / (double)self.cyclesFiredIn : 0;
    self.footerLabel.text = [NSString stringWithFormat:@"hits %ld / %ld cycles (%.0f%%)",
                             (long)self.catchesTotal, (long)self.cyclesFiredIn, rate * 100];
}

- (void)handleRowTap:(UITapGestureRecognizer *)g {
    NSString *lbl = g.accessibilityLabel ?: @"";
    int idx = [[lbl substringFromIndex:MIN(4, lbl.length)] intValue];
    SLV4PolicyKind kinds[3] = {SLV4PolicyK5Dyn, SLV4PolicyTriple, SLV4PolicyK10Dyn};
    if (idx < 0 || idx > 2) return;
    [SLV4Policy shared].activePolicy = kinds[idx];
    self.firesTotal = 0;
    self.catchesTotal = 0;
    self.cyclesFiredIn = 0;
    self.firedThisCycle = NO;
    [self refresh];
}

- (void)toggleExpand {
    self.expanded = !self.expanded;
    CGFloat h = self.expanded ? kExpandedH : kCollapsedH;
    self.body.hidden = !self.expanded;

    [UIView animateWithDuration:0.2 animations:^{
        CGRect wf = self.window.frame; wf.size.height = h; self.window.frame = wf;
        CGRect cf = self.container.frame; cf.size.height = h; self.container.frame = cf;
    }];
}

- (void)handleLongPress:(UILongPressGestureRecognizer *)g {
    if (g.state != UIGestureRecognizerStateBegan) return;
    self.window.alpha = (self.window.alpha < 0.5) ? 1.0 : 0.3;
}

- (void)handlePan:(UIPanGestureRecognizer *)p {
    if (p.state == UIGestureRecognizerStateChanged || p.state == UIGestureRecognizerStateBegan) {
        CGPoint t = [p translationInView:p.view];
        CGRect f = self.window.frame;
        f.origin.x += t.x; f.origin.y += t.y;
        self.window.frame = f;
        [p setTranslation:CGPointZero inView:p.view];
    }
    if (p.state == UIGestureRecognizerStateEnded) {
        CGRect f = self.window.frame;
        [[NSUserDefaults standardUserDefaults] setObject:@{@"x": @(f.origin.x), @"y": @(f.origin.y)}
                                                  forKey:kSLV4PanelOriginKey];
    }
}

- (void)show {
    self.window.hidden = NO;
    [[NSUserDefaults standardUserDefaults] setBool:YES forKey:kSLV4PanelVisibleKey];
}
- (void)hide {
    self.window.hidden = YES;
    [[NSUserDefaults standardUserDefaults] setBool:NO forKey:kSLV4PanelVisibleKey];
}

- (UILabel *)lbl:(CGRect)f size:(CGFloat)s bold:(BOOL)b color:(UIColor *)c {
    UILabel *l = [[UILabel alloc] initWithFrame:f];
    l.font = b ? [UIFont boldSystemFontOfSize:s] : [UIFont systemFontOfSize:s];
    l.textColor = c;
    l.backgroundColor = [UIColor clearColor];
    return l;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
