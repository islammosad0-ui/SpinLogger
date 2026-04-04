#import "SLTrisController.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>

// ---------------------------------------------------------------------------
//  SLTrisController — Tris Monitor
//
//  Records the DISTANCE (number of spins) between each 3-of-a-kind.
//  When counter overlay detects a triple, it calls recordTriple:distance:
//  which adds the distance to that symbol's column in the tris monitor.
//
//  Display: 5 colored columns (attack, steal, accum, shield, goldSack)
//  Each row = one triple event, showing how many spins it took.
// ---------------------------------------------------------------------------

@interface SLTrisController () <WKScriptMessageHandler>
@property (nonatomic, strong) UIWindow *trisWindow;
@property (nonatomic, strong) WKWebView *trisWebView;
// Each array stores distances between triples for that symbol
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histAttack;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histSteal;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histAccum;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histShield;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histGold;
@property (nonatomic, assign) NSInteger totalSpins;
@property (nonatomic, assign) BOOL symbolCountMode;  // NO=spins between triples, YES=symbols between triples
// Symbol count histories (how many of that symbol appeared between triples)
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistAttack;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistSteal;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistAccum;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistShield;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistGold;
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
        _lockTarget  = [[NSUserDefaults standardUserDefaults] stringForKey:kSLDefaultsTrisLockTarget];
        _skipEnabled = [[NSUserDefaults standardUserDefaults] boolForKey:@"Speeder_TrisSkip"];
        _histAttack = [NSMutableArray array];
        _histSteal  = [NSMutableArray array];
        _histAccum  = [NSMutableArray array];
        _histShield = [NSMutableArray array];
        _histGold   = [NSMutableArray array];
        _symHistAttack = [NSMutableArray array];
        _symHistSteal  = [NSMutableArray array];
        _symHistAccum  = [NSMutableArray array];
        _symHistShield = [NSMutableArray array];
        _symHistGold   = [NSMutableArray array];
        _totalSpins = 0;
        _symbolCountMode = NO;
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

- (void)onSpinReceived:(NSNotification *)note {
    self.totalSpins++;
}

- (void)onShowTris:(NSNotification *)note {
    [self showTrisMonitor];
}

#pragma mark - Record triple from counter overlay

- (void)recordTriple:(NSString *)symbol distance:(NSInteger)distance {
    [self recordTriple:symbol distance:distance symbolCount:0];
}

- (void)recordTriple:(NSString *)symbol distance:(NSInteger)distance symbolCount:(NSInteger)symCount {
    NSMutableArray *hist = [self historyForSymbol:symbol];
    if (hist) {
        [hist addObject:@(distance)];
        if (hist.count > 50) [hist removeObjectAtIndex:0];
    }
    NSMutableArray *symHist = [self symbolHistoryForSymbol:symbol];
    if (symHist) {
        [symHist addObject:@(symCount)];
        if (symHist.count > 50) [symHist removeObjectAtIndex:0];
    }

    // Update tris view if visible
    if (self.trisWindow && !self.trisWindow.hidden) {
        [self refreshTrisHTML];
    }
}

- (NSMutableArray *)historyForSymbol:(NSString *)sym {
    if ([sym isEqualToString:kSLSymbolAttack])       return self.histAttack;
    if ([sym isEqualToString:kSLSymbolSteal])        return self.histSteal;
    if ([sym isEqualToString:kSLSymbolAccumulation]) return self.histAccum;
    if ([sym isEqualToString:kSLSymbolShield])       return self.histShield;
    if ([sym isEqualToString:kSLSymbolGoldSack])     return self.histGold;
    return nil;
}

- (NSMutableArray *)symbolHistoryForSymbol:(NSString *)sym {
    if ([sym isEqualToString:kSLSymbolAttack])       return self.symHistAttack;
    if ([sym isEqualToString:kSLSymbolSteal])        return self.symHistSteal;
    if ([sym isEqualToString:kSLSymbolAccumulation]) return self.symHistAccum;
    if ([sym isEqualToString:kSLSymbolShield])       return self.symHistShield;
    if ([sym isEqualToString:kSLSymbolGoldSack])     return self.symHistGold;
    return nil;
}

#pragma mark - Tris Monitor UI

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
    CGFloat h = 400;
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
    } else if ([body isEqualToString:@"toggleMode"]) {
        self.symbolCountMode = !self.symbolCountMode;
        [self refreshTrisHTML];
    } else if ([body isEqualToString:@"reset"]) {
        [self.histAttack removeAllObjects];
        [self.histSteal  removeAllObjects];
        [self.histAccum  removeAllObjects];
        [self.histShield removeAllObjects];
        [self.histGold   removeAllObjects];
        self.totalSpins = 0;
        [self refreshTrisHTML];
    }
}

#pragma mark - Tris HTML — 5 columns showing distance history

- (void)refreshTrisHTML {
    // Choose which history to show based on mode
    NSArray *ha = self.symbolCountMode ? self.symHistAttack : self.histAttack;
    NSArray *hs = self.symbolCountMode ? self.symHistSteal  : self.histSteal;
    NSArray *hc = self.symbolCountMode ? self.symHistAccum  : self.histAccum;
    NSArray *hh = self.symbolCountMode ? self.symHistShield : self.histShield;
    NSArray *hg = self.symbolCountMode ? self.symHistGold   : self.histGold;

    NSInteger maxRows = ha.count;
    if (hs.count  > maxRows) maxRows = (NSInteger)hs.count;
    if (hc.count  > maxRows) maxRows = (NSInteger)hc.count;
    if (hh.count > maxRows) maxRows = (NSInteger)hh.count;
    if (hg.count   > maxRows) maxRows = (NSInteger)hg.count;

    NSMutableString *rows = [NSMutableString string];
    // Top to bottom = oldest first
    NSInteger startIdx = (maxRows > 25) ? maxRows - 25 : 0;
    for (NSInteger i = startIdx; i < maxRows; i++) {
        NSString *a = (i < (NSInteger)ha.count) ? [NSString stringWithFormat:@"%ld", (long)[ha[i] integerValue]] : @"";
        NSString *s = (i < (NSInteger)hs.count) ? [NSString stringWithFormat:@"%ld", (long)[hs[i] integerValue]] : @"";
        NSString *c = (i < (NSInteger)hc.count) ? [NSString stringWithFormat:@"%ld", (long)[hc[i] integerValue]] : @"";
        NSString *h = (i < (NSInteger)hh.count) ? [NSString stringWithFormat:@"%ld", (long)[hh[i] integerValue]] : @"";
        NSString *g = (i < (NSInteger)hg.count) ? [NSString stringWithFormat:@"%ld", (long)[hg[i] integerValue]] : @"";

        [rows appendFormat:
         @"<div class='c c0'>%@</div>"
         "<div class='c c1'>%@</div>"
         "<div class='c c2'>%@</div>"
         "<div class='c c3'>%@</div>"
         "<div class='c c4'>%@</div>",
         a, s, c, h, g];
    }

    NSString *html = [NSString stringWithFormat:@
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1,user-scalable=no'>"
    "<style>"
    "*{margin:0;padding:0;box-sizing:border-box;-webkit-user-select:none}"
    "body{background:transparent;font-family:-apple-system,sans-serif}"
    ".panel{background:rgba(15,20,35,0.95);border-radius:20px;overflow:hidden;"
    "border:1px solid rgba(255,255,255,0.06);height:100vh;display:flex;flex-direction:column}"
    ".hdr{display:flex;height:56px;align-items:center;padding:0 6px;flex-shrink:0}"
    ".hdr-icon{flex:1;display:flex;flex-direction:column;align-items:center;font-size:24px}"
    ".hdr-bar{height:3px;width:80%%;border-radius:2px;margin-top:4px}"
    ".close{width:36px;height:36px;background:rgba(255,255,255,0.12);border-radius:18px;"
    "display:flex;align-items:center;justify-content:center;font-size:18px;color:#fff;"
    "cursor:pointer;border:none;position:absolute;right:10px;top:10px}"
    ".grid{display:grid;grid-template-columns:repeat(5,1fr);flex:1;overflow-y:auto;"
    "align-content:start}"
    ".c{text-align:center;padding:8px 2px;font-size:17px;font-weight:700;"
    "border-bottom:1px solid rgba(255,255,255,0.04)}"
    ".c0{color:#00e5ff}.c1{color:#ff69b4}.c2{color:#00bcd4}.c3{color:#ce93d8}.c4{color:#4caf50}"
    ".foot{display:flex;justify-content:space-between;padding:10px 16px;"
    "color:#aaa;font-size:14px;font-weight:600;flex-shrink:0;"
    "border-top:1px solid rgba(255,255,255,0.06)}"
    ".foot span{cursor:pointer}"
    "</style></head><body>"
    "<div class='panel'>"
    "<button class='close' onclick='msg(\"close\")'>X</button>"
    "<div class='hdr'>"
    "<div class='hdr-icon'>🔨<div class='hdr-bar' style='background:#00e5ff'></div></div>"
    "<div class='hdr-icon'>🐷<div class='hdr-bar' style='background:#ff69b4'></div></div>"
    "<div class='hdr-icon'>💊<div class='hdr-bar' style='background:#00bcd4'></div></div>"
    "<div class='hdr-icon'>🛡<div class='hdr-bar' style='background:#ce93d8'></div></div>"
    "<div class='hdr-icon'>🧪<div class='hdr-bar' style='background:#4caf50'></div></div>"
    "</div>"
    "<div class='grid'>%@</div>"
    "<div class='foot'>"
    "<span onclick='msg(\"reset\")'>RESET</span>"
    "<span onclick='msg(\"toggleMode\")'>%@</span>"
    "<span>SPIN: %ld</span>"
    "</div>"
    "</div>"
    "<script>function msg(s){window.webkit.messageHandlers.tris.postMessage(s)}</script>"
    "</body></html>",
    rows,
    self.symbolCountMode ? @"[SYM]" : @"[SPIN]",
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
