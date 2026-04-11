#import "SLSignalPanel.h"
#import "SLMemoryScanner.h"
#import "SLConstants.h"

// ---------------------------------------------------------------------------
//  Panel constants
// ---------------------------------------------------------------------------
static const CGFloat kPanelW = 220;
static const CGFloat kHeaderH = 28;
static const CGFloat kExpandedH = 90;

// ---------------------------------------------------------------------------
//  SLSignalPanel — IL2CPP trace counters HUD
// ---------------------------------------------------------------------------
@interface SLSignalPanel ()
@property (nonatomic, strong) UIWindow *window;
@property (nonatomic, strong) UIView *container;
@property (nonatomic, strong) UIView *headerBar;
@property (nonatomic, strong) UIView *bodyView;
@property (nonatomic, assign) BOOL expanded;

// Labels
@property (nonatomic, strong) UILabel *headerLabel;
@property (nonatomic, strong) UILabel *phaseLabel;
@property (nonatomic, strong) UILabel *countsLabel;

// Refresh timer
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
    headerLbl.text = @"IL2CPP TRACE";
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

    // Body
    UIView *body = [[UIView alloc] initWithFrame:CGRectMake(0, kHeaderH, kPanelW, kExpandedH - kHeaderH)];
    [container addSubview:body];
    self.bodyView = body;
    body.hidden = YES;

    CGFloat bx = 8, bw = kPanelW - 16;

    // Phase label
    self.phaseLabel = [self makeLabel:CGRectMake(bx, 6, bw, 16) size:11 bold:YES
                                color:[UIColor colorWithRed:0.53 green:0.81 blue:0.98 alpha:1]];
    self.phaseLabel.text = @"phase: ?";
    [body addSubview:self.phaseLabel];

    // Counts label
    self.countsLabel = [self makeLabel:CGRectMake(bx, 26, bw, 32) size:10 bold:NO
                                 color:[UIColor colorWithWhite:0.85 alpha:1]];
    self.countsLabel.numberOfLines = 2;
    self.countsLabel.text = @"spins: 0 · snaps: 0\n0.0 MB";
    [body addSubview:self.countsLabel];

    win.hidden = NO;
    self.window = win;

    // 1 Hz refresh timer
    self.refreshTimer = [NSTimer scheduledTimerWithTimeInterval:1.0
                                                          target:self
                                                        selector:@selector(refreshTraceLabels)
                                                        userInfo:nil
                                                         repeats:YES];

    NSLog(@"[SpinLogger] Signal Panel installed (trace mode)");
}

// ============================================================
//  Trace counter refresh — 1 Hz from timer
// ============================================================
- (void)refreshTraceLabels {
    SLMemoryScanner *s = [SLMemoryScanner shared];
    NSString *phase = s.currentPhaseName ?: @"?";
    double mb = s.bytesWritten / 1048576.0;

    dispatch_async(dispatch_get_main_queue(), ^{
        self.phaseLabel.text = [NSString stringWithFormat:@"phase: %@", phase];
        self.countsLabel.text = [NSString stringWithFormat:
            @"spins: %lld · snaps: %lld\n%.1f MB",
            s.spinsSeen, s.snapshotsWritten, mb];
        self.headerLabel.text = [NSString stringWithFormat:@"IL2CPP %@", phase];
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
    [self.refreshTimer invalidate];
    self.refreshTimer = nil;
}

@end
