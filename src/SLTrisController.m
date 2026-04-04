#import "SLTrisController.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>

// ---------------------------------------------------------------------------
//  SLTrisController — Tris Monitor with WKWebView columns
//  Shows symbol count history in 5 colored columns (like One.dylib)
// ---------------------------------------------------------------------------

@interface SLTrisController () <WKScriptMessageHandler>
@property (nonatomic, strong) UIWindow *trisWindow;
@property (nonatomic, strong) WKWebView *trisWebView;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histAttack;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histSteal;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histAccum;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histShield;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histPotion;
@property (nonatomic, assign) NSInteger totalSpins;
// Running counters (reset each 3-of-a-kind or manual reset)
@property (nonatomic, assign) NSInteger cntAttack;
@property (nonatomic, assign) NSInteger cntSteal;
@property (nonatomic, assign) NSInteger cntAccum;
@property (nonatomic, assign) NSInteger cntShield;
@property (nonatomic, assign) NSInteger cntPotion;
@end

@implementation SLTrisController

+ (instancetype)shared {
    static SLTrisController *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        NSUserDefaults *d = [NSUserDefaults standardUserDefaults];
        _lockTarget  = [d stringForKey:kSLDefaultsTrisLockTarget];
        _skipEnabled = [d boolForKey:@"Speeder_TrisSkip"];
        _histAttack = [NSMutableArray array];
        _histSteal  = [NSMutableArray array];
        _histAccum  = [NSMutableArray array];
        _histShield = [NSMutableArray array];
        _histPotion = [NSMutableArray array];
        _totalSpins = 0;
    }
    return self;
}

- (void)install {
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification object:nil];
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onShowTris:)
                                                 name:@"SLShowTrisMonitor" object:nil];
}

#pragma mark - Spin handling

- (void)onSpinReceived:(NSNotification *)note {
    SLSpinResult *r = note.userInfo[SLSpinDataKey];
    if (!r) return;

    self.totalSpins++;

    // Count each reel symbol
    for (NSString *sym in @[r.reel1 ?: @"", r.reel2 ?: @"", r.reel3 ?: @""]) {
        if ([sym isEqualToString:kSLSymbolAttack])       self.cntAttack++;
        else if ([sym isEqualToString:kSLSymbolSteal])   self.cntSteal++;
        else if ([sym isEqualToString:kSLSymbolAccumulation]) self.cntAccum++;
        else if ([sym isEqualToString:kSLSymbolShield])  self.cntShield++;
        else if ([sym isEqualToString:kSLSymbolGoldSack]) self.cntPotion++;
    }

    // On 3-of-a-kind: save counts to history and reset
    if (r.reel1 && [r.reel1 isEqualToString:r.reel2] && [r.reel2 isEqualToString:r.reel3]) {
        [self.histAttack addObject:@(self.cntAttack)];
        [self.histSteal  addObject:@(self.cntSteal)];
        [self.histAccum  addObject:@(self.cntAccum)];
        [self.histShield addObject:@(self.cntShield)];
        [self.histPotion addObject:@(self.cntPotion)];

        // Keep last 50 entries
        if (self.histAttack.count > 50) {
            [self.histAttack removeObjectAtIndex:0];
            [self.histSteal  removeObjectAtIndex:0];
            [self.histAccum  removeObjectAtIndex:0];
            [self.histShield removeObjectAtIndex:0];
            [self.histPotion removeObjectAtIndex:0];
        }

        self.cntAttack = self.cntSteal = self.cntAccum = self.cntShield = self.cntPotion = 0;

        // Update tris monitor if visible
        if (self.trisWindow && !self.trisWindow.hidden) {
            [self refreshTrisHTML];
        }
    }
}

- (void)addSpinToHistory:(NSArray<NSString *> *)reels {
    // External API for adding from other sources
}

#pragma mark - Tris Monitor UI

- (void)onShowTris:(NSNotification *)note {
    [self showTrisMonitor];
}

- (void)showTrisMonitor {
    if (self.trisWindow) {
        self.trisWindow.hidden = !self.trisWindow.hidden;
        if (!self.trisWindow.hidden) [self refreshTrisHTML];
        return;
    }

    UIWindowScene *scene = nil;
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            if (s.activationState == UISceneActivationStateForegroundActive) break;
        }
    }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat w = MIN(screen.size.width - 20, 340);
    CGFloat h = 380;
    CGFloat x = (screen.size.width - w) / 2;
    CGFloat y = (screen.size.height - h) / 2;

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, y, w, h);
    win.windowLevel = UIWindowLevelAlert + 250;
    win.backgroundColor = [UIColor clearColor];

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(dragTris:)];
    [vc.view addGestureRecognizer:pan];

    WKWebViewConfiguration *config = [[WKWebViewConfiguration alloc] init];
    [config.userContentController addScriptMessageHandler:self name:@"tris"];

    WKWebView *wv = [[WKWebView alloc] initWithFrame:CGRectMake(0, 0, w, h) configuration:config];
    wv.backgroundColor = [UIColor clearColor];
    wv.opaque = NO;
    wv.scrollView.bounces = NO;
    [vc.view addSubview:wv];
    self.trisWebView = wv;

    win.hidden = NO;
    self.trisWindow = win;

    [self refreshTrisHTML];
}

- (void)hideTrisMonitor {
    self.trisWindow.hidden = YES;
}

- (void)dragTris:(UIPanGestureRecognizer *)pan {
    if (pan.state == UIGestureRecognizerStateBegan ||
        pan.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [pan translationInView:pan.view];
        CGRect f = self.trisWindow.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        self.trisWindow.frame = f;
        [pan setTranslation:CGPointZero inView:pan.view];
    }
}

- (void)userContentController:(WKUserContentController *)uc didReceiveScriptMessage:(WKScriptMessage *)msg {
    NSString *body = [msg.body description];
    if ([body isEqualToString:@"close"]) {
        self.trisWindow.hidden = YES;
    } else if ([body isEqualToString:@"reset"]) {
        [self.histAttack removeAllObjects];
        [self.histSteal  removeAllObjects];
        [self.histAccum  removeAllObjects];
        [self.histShield removeAllObjects];
        [self.histPotion removeAllObjects];
        self.cntAttack = self.cntSteal = self.cntAccum = self.cntShield = self.cntPotion = 0;
        self.totalSpins = 0;
        [self refreshTrisHTML];
    }
}

#pragma mark - Tris HTML

- (void)refreshTrisHTML {
    NSInteger rows = self.histAttack.count;

    // Build column cells
    NSMutableString *colAttack = [NSMutableString string];
    NSMutableString *colSteal  = [NSMutableString string];
    NSMutableString *colAccum  = [NSMutableString string];
    NSMutableString *colShield = [NSMutableString string];
    NSMutableString *colPotion = [NSMutableString string];

    // Show most recent first (reverse order)
    for (NSInteger i = rows - 1; i >= 0 && i >= rows - 20; i--) {
        [colAttack appendFormat:@"<div class='cell c0'>%ld</div>", (long)self.histAttack[i].integerValue];
        [colSteal  appendFormat:@"<div class='cell c1'>%ld</div>", (long)self.histSteal[i].integerValue];
        [colAccum  appendFormat:@"<div class='cell c2'>%ld</div>", (long)self.histAccum[i].integerValue];
        [colShield appendFormat:@"<div class='cell c3'>%ld</div>", (long)self.histShield[i].integerValue];
        [colPotion appendFormat:@"<div class='cell c4'>%ld</div>", (long)self.histPotion[i].integerValue];
    }

    // Current running counts at top
    NSString *curRow = [NSString stringWithFormat:
        @"<div class='cell c0 cur'>%ld</div>"
        "<div class='cell c1 cur'>%ld</div>"
        "<div class='cell c2 cur'>%ld</div>"
        "<div class='cell c3 cur'>%ld</div>"
        "<div class='cell c4 cur'>%ld</div>",
        (long)self.cntAttack, (long)self.cntSteal, (long)self.cntAccum,
        (long)self.cntShield, (long)self.cntPotion];

    NSString *html = [NSString stringWithFormat:@
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1,user-scalable=no'>"
    "<style>"
    "*{margin:0;padding:0;box-sizing:border-box;-webkit-user-select:none}"
    "body{background:transparent;font-family:-apple-system,sans-serif}"
    ".panel{background:rgba(15,20,35,0.95);border-radius:20px;overflow:hidden;"
    "border:1px solid rgba(255,255,255,0.06)}"
    /* Header icons */
    ".hdr{display:flex;height:60px;align-items:center;padding:0 6px}"
    ".hdr-icon{flex:1;display:flex;flex-direction:column;align-items:center;"
    "justify-content:center;font-size:24px}"
    ".hdr-bar{height:3px;width:80%%;border-radius:2px;margin-top:4px}"
    ".hdr-close{width:40px;height:40px;background:rgba(255,255,255,0.12);"
    "border-radius:20px;display:flex;align-items:center;justify-content:center;"
    "font-size:20px;color:#fff;cursor:pointer;border:none;position:absolute;right:8px;top:8px}"
    /* Grid */
    ".grid{display:grid;grid-template-columns:repeat(5,1fr);gap:0;max-height:260px;overflow-y:auto}"
    ".cell{text-align:center;padding:6px 2px;font-size:16px;font-weight:700;"
    "border-bottom:1px solid rgba(255,255,255,0.04)}"
    ".cur{font-size:18px;font-weight:800;border-bottom:2px solid rgba(255,255,255,0.1)}"
    ".c0{color:#00e5ff}.c1{color:#ff69b4}.c2{color:#00bcd4}.c3{color:#ce93d8}.c4{color:#4caf50}"
    /* Footer */
    ".foot{display:flex;justify-content:space-between;padding:8px 14px;color:#aaa;font-size:13px}"
    ".foot span{cursor:pointer}"
    "</style></head><body>"
    "<div class='panel'>"
    "<button class='hdr-close' onclick='msg(\"close\")'>✕</button>"
    /* Header with icons and color bars */
    "<div class='hdr'>"
    "<div class='hdr-icon'>🔨<div class='hdr-bar' style='background:#00e5ff'></div></div>"
    "<div class='hdr-icon'>🐷<div class='hdr-bar' style='background:#ff69b4'></div></div>"
    "<div class='hdr-icon'>💊<div class='hdr-bar' style='background:#00bcd4'></div></div>"
    "<div class='hdr-icon'>🛡<div class='hdr-bar' style='background:#ce93d8'></div></div>"
    "<div class='hdr-icon'>🧪<div class='hdr-bar' style='background:#4caf50'></div></div>"
    "</div>"
    /* Current counts */
    "<div class='grid'>%@</div>"
    /* History */
    "<div class='grid'>%@%@%@%@%@</div>"
    /* Footer */
    "<div class='foot'>"
    "<span onclick='msg(\"reset\")'>RESET</span>"
    "<span>SPIN: %ld</span>"
    "</div>"
    "</div>"
    "<script>function msg(s){window.webkit.messageHandlers.tris.postMessage(s)}</script>"
    "</body></html>",
    curRow,
    colAttack, colSteal, colAccum, colShield, colPotion,
    (long)self.totalSpins];

    [self.trisWebView loadHTMLString:html baseURL:nil];
}

#pragma mark - Setters

- (void)setLockTarget:(NSString *)lockTarget {
    _lockTarget = [lockTarget copy];
    [[NSUserDefaults standardUserDefaults] setObject:_lockTarget forKey:kSLDefaultsTrisLockTarget];
}

- (void)setSkipEnabled:(BOOL)skipEnabled {
    _skipEnabled = skipEnabled;
    [[NSUserDefaults standardUserDefaults] setBool:_skipEnabled forKey:@"Speeder_TrisSkip"];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
