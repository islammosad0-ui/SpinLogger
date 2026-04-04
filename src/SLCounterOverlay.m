#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>
#import "SLCounterOverlay.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import "SLTrisController.h"

// ---------------------------------------------------------------------------
//  SLCounterOverlay — Distance-between-triples counter
//
//  Each counter shows: how many spins since the last 3-of-a-kind for that symbol.
//  When you hit 3 pigs, the pig counter resets to 0 and the distance is
//  logged to the tris monitor. Same for all symbols.
// ---------------------------------------------------------------------------

@interface SLCounterOverlay () <WKScriptMessageHandler>
@property (nonatomic, strong) UIWindow *overlayWindow;
@property (nonatomic, strong) WKWebView *webView;
// Distance counters: spins since last triple for each symbol
@property (nonatomic, strong) NSMutableDictionary<NSString *, NSNumber *> *distances;
@property (nonatomic, assign) NSInteger totalSpins;
@property (nonatomic, assign) BOOL visible;
@end

@implementation SLCounterOverlay

+ (instancetype)shared {
    static SLCounterOverlay *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (void)install {
    self.distances = [NSMutableDictionary dictionary];
    self.totalSpins = 0;
    self.visible = YES;

    // All tracked symbols start at 0 distance
    for (NSString *sym in @[kSLSymbolAttack, kSLSymbolSteal, kSLSymbolAccumulation,
                            kSLSymbolShield, kSLSymbolGoldSack]) {
        self.distances[sym] = @0;
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
    CGFloat tileW = 56, gap = 4;
    NSInteger count = 5;
    CGFloat totalW = count * tileW + (count - 1) * gap;
    CGFloat h = 74;
    CGFloat x = (screen.size.width - totalW) / 2;
    CGFloat y = screen.size.height - h - 90;

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, y, totalW, h);
    win.windowLevel = UIWindowLevelAlert + 100;
    win.backgroundColor = [UIColor clearColor];
    win.userInteractionEnabled = YES;

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(handlePan:)];
    [vc.view addGestureRecognizer:pan];

    WKWebViewConfiguration *config = [[WKWebViewConfiguration alloc] init];
    [config.userContentController addScriptMessageHandler:self name:@"counter"];

    WKWebView *wv = [[WKWebView alloc] initWithFrame:CGRectMake(0, 0, totalW, h) configuration:config];
    wv.backgroundColor = [UIColor clearColor];
    wv.opaque = NO;
    wv.scrollView.scrollEnabled = NO;
    wv.scrollView.bounces = NO;
    [vc.view addSubview:wv];
    self.webView = wv;

    win.hidden = NO;
    self.overlayWindow = win;
    [self refreshHTML];

    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification object:nil];
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onToggle:)
                                                 name:@"SLToggleCounters" object:nil];
}

- (void)handlePan:(UIPanGestureRecognizer *)pan {
    if (pan.state == UIGestureRecognizerStateBegan ||
        pan.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [pan translationInView:pan.view];
        CGRect f = self.overlayWindow.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        self.overlayWindow.frame = f;
        [pan setTranslation:CGPointZero inView:pan.view];
    }
}

- (void)userContentController:(WKUserContentController *)uc didReceiveScriptMessage:(WKScriptMessage *)msg {
}

#pragma mark - HTML

- (void)refreshHTML {
    NSArray *symbols = @[
        @[@"attack",       @"🔨", @"#00e5ff"],
        @[@"steal",        @"🐷", @"#ff69b4"],
        @[@"accumulation", @"💊", @"#00bcd4"],
        @[@"shield",       @"🛡",  @"#9c27b0"],
        @[@"goldSack",     @"🧪", @"#4caf50"]
    ];

    NSMutableString *tiles = [NSMutableString string];
    for (NSArray *s in symbols) {
        NSInteger d = [self.distances[s[0]] integerValue];
        [tiles appendFormat:
         @"<div class='tile'>"
         "<div class='icon'>%@</div>"
         "<div class='num' style='color:%@'>%ld</div>"
         "<div class='bar' style='background:%@'></div>"
         "</div>", s[1], s[2], (long)d, s[2]];
    }

    NSString *html = [NSString stringWithFormat:@
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1,user-scalable=no'>"
    "<style>"
    "*{margin:0;padding:0;box-sizing:border-box;-webkit-user-select:none}"
    "body{background:transparent;display:flex;gap:4px;font-family:-apple-system,sans-serif}"
    ".tile{width:56px;height:74px;background:rgba(20,25,35,0.92);border-radius:14px;"
    "display:flex;flex-direction:column;align-items:center;justify-content:center;"
    "position:relative;overflow:hidden}"
    ".icon{font-size:22px;margin-bottom:2px}"
    ".num{font-size:18px;font-weight:800}"
    ".bar{position:absolute;bottom:0;left:4px;right:4px;height:3px;border-radius:2px;opacity:0.8}"
    "</style></head><body>%@</body></html>", tiles];

    [self.webView loadHTMLString:html baseURL:nil];
}

- (void)updateCountsViaJS {
    NSArray *keys = @[kSLSymbolAttack, kSLSymbolSteal, kSLSymbolAccumulation, kSLSymbolShield, kSLSymbolGoldSack];

    NSMutableString *js = [NSMutableString stringWithString:@"(function(){var nums=document.querySelectorAll('.num');"];
    for (NSUInteger i = 0; i < keys.count; i++) {
        NSInteger d = [self.distances[keys[i]] integerValue];
        [js appendFormat:@"if(nums[%lu])nums[%lu].textContent='%ld';", (unsigned long)i, (unsigned long)i, (long)d];
    }
    [js appendString:@"})()"];
    [self.webView evaluateJavaScript:js completionHandler:nil];
}

#pragma mark - Spin handling (distance between triples)

- (void)onSpinReceived:(NSNotification *)note {
    SLSpinResult *result = note.userInfo[SLSpinDataKey];
    if (!result) return;

    self.totalSpins++;

    // Increment ALL distance counters every spin
    for (NSString *sym in self.distances.allKeys) {
        self.distances[sym] = @([self.distances[sym] integerValue] + 1);
    }

    // Check for triple (3-of-a-kind)
    BOOL isTriple = (result.reel1 && [result.reel1 isEqualToString:result.reel2] &&
                     [result.reel2 isEqualToString:result.reel3]);

    if (isTriple && result.reel1.length > 0) {
        NSString *sym = result.reel1;
        NSInteger distance = [self.distances[sym] integerValue];

        // Log distance to tris monitor
        [[SLTrisController shared] recordTriple:sym distance:distance];

        NSLog(@"[SpinLogger] TRIPLE %@ after %ld spins", sym, (long)distance);

        // Reset this symbol's distance counter
        self.distances[sym] = @0;
    }

    [self updateCountsViaJS];
}

- (void)onToggle:(NSNotification *)note {
    self.visible = !self.visible;
    self.overlayWindow.hidden = !self.visible;
}

#pragma mark - Public

- (void)show  { self.overlayWindow.hidden = NO;  self.visible = YES; }
- (void)hide  { self.overlayWindow.hidden = YES; self.visible = NO; }

- (void)resetAllCounters {
    for (NSString *sym in self.distances.allKeys) self.distances[sym] = @0;
    self.totalSpins = 0;
    [self refreshHTML];
}

- (void)resetCounterForSymbol:(NSString *)symbol {
    if (self.distances[symbol]) self.distances[symbol] = @0;
    [self updateCountsViaJS];
}

- (NSDictionary<NSString *, NSNumber *> *)currentCounts {
    return [self.distances copy];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
