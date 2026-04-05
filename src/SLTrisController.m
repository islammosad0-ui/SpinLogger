#import "SLTrisController.h"
#import "SLCounterOverlay.h"
#import "SLSpinStore.h"
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
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histSpins;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histShield;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histAccum;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histGold;
@property (nonatomic, assign) NSInteger totalSpins;
@property (nonatomic, assign) BOOL symbolCountMode;  // NO=spins between triples, YES=symbols between triples
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistAttack;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistSteal;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistSpins;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistShield;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistAccum;
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
        _histSpins  = [NSMutableArray array];
        _histShield = [NSMutableArray array];
        _histAccum  = [NSMutableArray array];
        _histGold   = [NSMutableArray array];
        _symHistAttack = [NSMutableArray array];
        _symHistSteal  = [NSMutableArray array];
        _symHistSpins  = [NSMutableArray array];
        _symHistShield = [NSMutableArray array];
        _symHistAccum  = [NSMutableArray array];
        _symHistGold   = [NSMutableArray array];
        _totalSpins = 0;
        _symbolCountMode = NO;
        [self restoreState];
    }
    return self;
}

#pragma mark - Persistence

- (void)saveState {
    NSDictionary *state = @{
        @"totalSpins": @(_totalSpins),
        @"histAttack": _histAttack, @"histSteal": _histSteal, @"histSpins": _histSpins,
        @"histShield": _histShield, @"histAccum": _histAccum, @"histGold": _histGold,
        @"symHistAttack": _symHistAttack, @"symHistSteal": _symHistSteal, @"symHistSpins": _symHistSpins,
        @"symHistShield": _symHistShield, @"symHistAccum": _symHistAccum, @"symHistGold": _symHistGold,
    };
    [[NSUserDefaults standardUserDefaults] setObject:state forKey:@"Speeder_TrisState"];
}

- (void)restoreState {
    NSDictionary *state = [[NSUserDefaults standardUserDefaults] dictionaryForKey:@"Speeder_TrisState"];
    if (!state) return;
    _totalSpins = [state[@"totalSpins"] integerValue];
    NSArray *keys = @[@"histAttack", @"histSteal", @"histSpins", @"histShield", @"histAccum", @"histGold",
                      @"symHistAttack", @"symHistSteal", @"symHistSpins", @"symHistShield", @"symHistAccum", @"symHistGold"];
    NSArray *arrays = @[_histAttack, _histSteal, _histSpins, _histShield, _histAccum, _histGold,
                        _symHistAttack, _symHistSteal, _symHistSpins, _symHistShield, _symHistAccum, _symHistGold];
    for (NSUInteger i = 0; i < keys.count; i++) {
        NSArray *saved = state[keys[i]];
        if ([saved isKindOfClass:[NSArray class]]) {
            [arrays[i] addObjectsFromArray:saved];
        }
    }
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
    if (hist) [hist addObject:@(distance)];
    NSMutableArray *symHist = [self symbolHistoryForSymbol:symbol];
    if (symHist) [symHist addObject:@(symCount)];

    [self saveState];

    // Update tris view if visible
    if (self.trisWindow && !self.trisWindow.hidden) {
        [self refreshTrisHTML];
    }
}

- (NSMutableArray *)historyForSymbol:(NSString *)sym {
    if ([sym isEqualToString:kSLSymbolAttack])       return self.histAttack;
    if ([sym isEqualToString:kSLSymbolSteal])        return self.histSteal;
    if ([sym isEqualToString:kSLSymbolSpins])        return self.histSpins;
    if ([sym isEqualToString:kSLSymbolShield])       return self.histShield;
    if ([sym isEqualToString:kSLSymbolAccumulation]) return self.histAccum;
    if ([sym isEqualToString:kSLSymbolGoldSack] || [sym isEqualToString:@"potion"]) return self.histGold;
    return nil;
}

- (NSMutableArray *)symbolHistoryForSymbol:(NSString *)sym {
    if ([sym isEqualToString:kSLSymbolAttack])       return self.symHistAttack;
    if ([sym isEqualToString:kSLSymbolSteal])        return self.symHistSteal;
    if ([sym isEqualToString:kSLSymbolSpins])        return self.symHistSpins;
    if ([sym isEqualToString:kSLSymbolShield])       return self.symHistShield;
    if ([sym isEqualToString:kSLSymbolAccumulation]) return self.symHistAccum;
    if ([sym isEqualToString:kSLSymbolGoldSack] || [sym isEqualToString:@"potion"]) return self.symHistGold;
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
    CGFloat w = MIN(screen.size.width - 20, 300);
    CGFloat h = screen.size.height * 0.25;
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
        [self.histSpins  removeAllObjects];
        [self.histShield removeAllObjects];
        [self.histAccum  removeAllObjects];
        [self.histGold   removeAllObjects];
        [self.symHistAttack removeAllObjects];
        [self.symHistSteal  removeAllObjects];
        [self.symHistSpins  removeAllObjects];
        [self.symHistShield removeAllObjects];
        [self.symHistAccum  removeAllObjects];
        [self.symHistGold   removeAllObjects];
        self.totalSpins = 0;
        [self saveState];
        // Also reset counter overlay + rotate to new CSV session
        [[SLCounterOverlay shared] resetAllCounters];
        SLSpinStoreRotateCSV();
        [self refreshTrisHTML];
    }
}

#pragma mark - Tris HTML — 6 independent scrollable columns

- (void)refreshTrisHTML {
    NSArray *arrays[6], *symArrays[6];
    arrays[0] = self.histAttack; arrays[1] = self.histSteal; arrays[2] = self.histSpins;
    arrays[3] = self.histShield; arrays[4] = self.histAccum; arrays[5] = self.histGold;
    symArrays[0] = self.symHistAttack; symArrays[1] = self.symHistSteal; symArrays[2] = self.symHistSpins;
    symArrays[3] = self.symHistShield; symArrays[4] = self.symHistAccum; symArrays[5] = self.symHistGold;

    // Build each column independently — no shared row alignment
    NSString *emojis[6]  = {@"🔨", @"🐷", @"💊", @"🛡", @"⭐", @"🧪"};
    NSString *colors[6]  = {@"#00e5ff", @"#ff69b4", @"#00bcd4", @"#ce93d8", @"#ffd700", @"#4caf50"};

    NSMutableString *colHTML = [NSMutableString string];
    for (int c = 0; c < 6; c++) {
        NSArray *arr = self.symbolCountMode ? symArrays[c] : arrays[c];
        NSMutableString *entries = [NSMutableString string];
        for (NSNumber *val in arr) {
            [entries appendFormat:@"<div class='e'>%ld</div>", (long)val.integerValue];
        }
        [colHTML appendFormat:
            @"<div class='col'>"
            "<div class='ch' style='color:%@'>%@<div class='hb' style='background:%@'></div></div>"
            "<div class='cb' id='b%d'>%@</div>"
            "</div>",
            colors[c], emojis[c], colors[c], c, entries];
    }

    NSString *html = [NSString stringWithFormat:@
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1,user-scalable=no'>"
        "<style>"
        "*{margin:0;padding:0;box-sizing:border-box;-webkit-user-select:none}"
        "body,html{height:100%%;background:transparent;font-family:-apple-system,sans-serif}"
        ".panel{position:relative;background:rgba(15,20,35,0.95);border-radius:14px;overflow:hidden;"
        "border:1px solid rgba(255,255,255,0.05);height:100%%;display:flex;flex-direction:column}"
        ".close{position:absolute;right:5px;top:5px;width:22px;height:22px;z-index:10;"
        "background:rgba(255,255,255,0.10);border-radius:11px;display:flex;"
        "align-items:center;justify-content:center;font-size:11px;color:#fff;"
        "cursor:pointer;border:none}"
        ".cols{display:flex;flex:1;overflow:hidden;min-height:0}"
        ".col{flex:1;display:flex;flex-direction:column;"
        "border-right:1px solid rgba(255,255,255,0.18);min-width:0}"
        ".col:last-child{border-right:none}"
        ".ch{text-align:center;font-size:12px;padding:3px 0;flex-shrink:0;"
        "display:flex;flex-direction:column;align-items:center;border-bottom:1px solid rgba(255,255,255,0.18)}"
        ".hb{height:2px;width:75%%;border-radius:1px;margin-top:1px}"
        ".cb{flex:1;overflow-y:auto;overflow-x:hidden}"
        ".cb::-webkit-scrollbar{display:none}"
        ".e{text-align:center;padding:3px 1px;font-size:11px;font-weight:700;"
        "border-bottom:1px solid rgba(255,255,255,0.03)}"
        ".col:nth-child(1) .e{color:#00e5ff}"
        ".col:nth-child(2) .e{color:#ff69b4}"
        ".col:nth-child(3) .e{color:#00bcd4}"
        ".col:nth-child(4) .e{color:#ce93d8}"
        ".col:nth-child(5) .e{color:#ffd700}"
        ".col:nth-child(6) .e{color:#4caf50}"
        ".foot{display:flex;justify-content:space-between;padding:5px 8px;"
        "color:#aaa;font-size:10px;font-weight:600;flex-shrink:0;"
        "border-top:1px solid rgba(255,255,255,0.05)}"
        ".foot span{cursor:pointer}"
        "</style></head><body>"
        "<div class='panel'>"
        "<button class='close' onclick='msg(\"close\")'>X</button>"
        "<div class='cols'>%@</div>"
        "<div class='foot'>"
        "<span onclick='msg(\"reset\")'>RESET</span>"
        "<span onclick='msg(\"toggleMode\")'>%@</span>"
        "<span>SPIN: %ld</span>"
        "</div>"
        "</div>"
        "<script>"
        "function msg(s){window.webkit.messageHandlers.tris.postMessage(s)}"
        "document.querySelectorAll('.cb').forEach(function(el){el.scrollTop=el.scrollHeight});"
        "</script>"
        "</body></html>",
        colHTML,
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
