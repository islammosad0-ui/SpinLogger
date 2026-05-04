#import "SLTrisController.h"
#import "SLCounterOverlay.h"
#import "SLSpinStore.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>

// ---------------------------------------------------------------------------
//  SLTrisController — Tris Monitor (WKWebView)
//  6 independent scrollable columns, one per symbol.
// ---------------------------------------------------------------------------

@interface SLTrisController () <WKScriptMessageHandler>
@property (nonatomic, strong) UIWindow   *trisWindow;
@property (nonatomic, strong) WKWebView  *trisWebView;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histAttack;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histSteal;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histSpins;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histShield;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histAccum;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histGold;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histVt;      // combined ACC+SPN VT-to-VT gaps
@property (nonatomic, assign) NSInteger totalSpins;
@property (nonatomic, assign) NSInteger lastVtTotalSpins;              // -1 = no VT seen yet
@property (nonatomic, assign) BOOL symbolCountMode;
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
        _histAttack = [NSMutableArray array]; _histSteal  = [NSMutableArray array];
        _histSpins  = [NSMutableArray array]; _histShield = [NSMutableArray array];
        _histAccum  = [NSMutableArray array]; _histGold   = [NSMutableArray array];
        _histVt     = [NSMutableArray array];
        _symHistAttack = [NSMutableArray array]; _symHistSteal  = [NSMutableArray array];
        _symHistSpins  = [NSMutableArray array]; _symHistShield = [NSMutableArray array];
        _symHistAccum  = [NSMutableArray array]; _symHistGold   = [NSMutableArray array];
        _totalSpins = 0;
        _lastVtTotalSpins = -1;
        _symbolCountMode = NO;
        NSUInteger saved = [[NSUserDefaults standardUserDefaults] integerForKey:@"Speeder_TrisVisibleCols"];
        _visibleColumns = (saved != 0) ? saved : kSLTrisColAll;
        [self restoreState];
    }
    return self;
}

#pragma mark - Persistence

- (void)saveState {
    NSDictionary *state = @{
        @"totalSpins":    @(_totalSpins),
        @"lastVtSpins":   @(_lastVtTotalSpins),
        @"histAttack":    _histAttack,   @"histSteal":    _histSteal,
        @"histSpins":     _histSpins,    @"histShield":   _histShield,
        @"histAccum":     _histAccum,    @"histGold":     _histGold,
        @"histVt":        _histVt,
        @"symHistAttack": _symHistAttack,@"symHistSteal": _symHistSteal,
        @"symHistSpins":  _symHistSpins, @"symHistShield":_symHistShield,
        @"symHistAccum":  _symHistAccum, @"symHistGold":  _symHistGold,
    };
    [[NSUserDefaults standardUserDefaults] setObject:state forKey:@"Speeder_TrisState"];
}

- (void)restoreState {
    NSDictionary *state = [[NSUserDefaults standardUserDefaults] dictionaryForKey:@"Speeder_TrisState"];
    if (!state) return;
    _totalSpins = [state[@"totalSpins"] integerValue];
    NSNumber *savedVtSpins = state[@"lastVtSpins"];
    _lastVtTotalSpins = savedVtSpins ? savedVtSpins.integerValue : -1;
    NSArray *keys   = @[@"histAttack",@"histSteal",@"histSpins",@"histShield",@"histAccum",@"histGold",@"histVt",
                        @"symHistAttack",@"symHistSteal",@"symHistSpins",@"symHistShield",@"symHistAccum",@"symHistGold"];
    NSArray *arrays = @[_histAttack,_histSteal,_histSpins,_histShield,_histAccum,_histGold,_histVt,
                        _symHistAttack,_symHistSteal,_symHistSpins,_symHistShield,_symHistAccum,_symHistGold];
    for (NSUInteger i = 0; i < keys.count; i++) {
        NSArray *saved = state[keys[i]];
        if ([saved isKindOfClass:[NSArray class]]) [arrays[i] addObjectsFromArray:saved];
    }
}

- (void)savePosition {
    if (!self.trisWindow) return;
    [[NSUserDefaults standardUserDefaults] setDouble:self.trisWindow.frame.origin.x forKey:@"Speeder_TrisX"];
    [[NSUserDefaults standardUserDefaults] setDouble:self.trisWindow.frame.origin.y forKey:@"Speeder_TrisY"];
}

#pragma mark - Notifications

- (void)install {
    [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification object:nil];
    [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(onShowTris:)
                                                 name:@"SLShowTrisMonitor" object:nil];
}

- (void)onSpinReceived:(NSNotification *)note {
    self.totalSpins++;
    if (self.trisWindow && !self.trisWindow.hidden) {
        NSString *js = [NSString stringWithFormat:
            @"var s=document.getElementById('spinTotal');if(s)s.textContent='SPIN: %ld';",
            (long)self.totalSpins];
        [self.trisWebView evaluateJavaScript:js completionHandler:nil];
    }
    SLSpinResult *result = note.userInfo[SLSpinDataKey];
    if (result) {
        NSString *r1 = result.reel1 ?: @"";
        BOOL isVt = ([r1 isEqualToString:result.reel2] && [r1 isEqualToString:result.reel3] &&
                     ([r1 isEqualToString:kSLSymbolAccumulation] || [r1 isEqualToString:kSLSymbolSpins]));
        if (isVt) {
            if (self.lastVtTotalSpins >= 0) {
                NSInteger gap = self.totalSpins - self.lastVtTotalSpins;
                [self.histVt addObject:@(gap)];
                [self saveState];
                if (self.trisWindow && !self.trisWindow.hidden) [self refreshTrisHTML];
            }
            self.lastVtTotalSpins = self.totalSpins;
        }
    }
}
- (void)onShowTris:(NSNotification *)note     { [self showTrisMonitor]; }

#pragma mark - Data helpers

- (NSMutableArray *)historyForSymbol:(NSString *)sym {
    if ([sym isEqualToString:kSLSymbolAttack])       return self.histAttack;
    if ([sym isEqualToString:kSLSymbolSteal])        return self.histSteal;
    if ([sym isEqualToString:kSLSymbolSpins])        return self.histSpins;
    if ([sym isEqualToString:kSLSymbolShield])       return self.histShield;
    if ([sym isEqualToString:kSLSymbolAccumulation]) return self.histAccum;
    if ([sym isEqualToString:@"potion"]) return self.histGold;
    return nil;
}

- (NSMutableArray *)symbolHistoryForSymbol:(NSString *)sym {
    if ([sym isEqualToString:kSLSymbolAttack])       return self.symHistAttack;
    if ([sym isEqualToString:kSLSymbolSteal])        return self.symHistSteal;
    if ([sym isEqualToString:kSLSymbolSpins])        return self.symHistSpins;
    if ([sym isEqualToString:kSLSymbolShield])       return self.symHistShield;
    if ([sym isEqualToString:kSLSymbolAccumulation]) return self.symHistAccum;
    if ([sym isEqualToString:@"potion"]) return self.symHistGold;
    return nil;
}

#pragma mark - Record triple

- (void)recordTriple:(NSString *)symbol distance:(NSInteger)distance {
    [self recordTriple:symbol distance:distance symbolCount:0];
}

- (void)recordTriple:(NSString *)symbol distance:(NSInteger)distance symbolCount:(NSInteger)symCount {
    NSMutableArray *hist    = [self historyForSymbol:symbol];
    NSMutableArray *symHist = [self symbolHistoryForSymbol:symbol];
    if (hist)    [hist addObject:@(distance)];
    if (symHist) [symHist addObject:@(symCount)];
    [self saveState];
    if (self.trisWindow && !self.trisWindow.hidden) [self refreshTrisHTML];
}

#pragma mark - Show / Hide

- (void)showTrisMonitor {
    if (self.trisWindow) {
        self.trisWindow.hidden = !self.trisWindow.hidden;
        if (!self.trisWindow.hidden) [self refreshTrisHTML];
        return;
    }
    [self buildUI];
}

- (void)hideTrisMonitor { self.trisWindow.hidden = YES; }

- (BOOL)isMonitorVisible {
    return self.trisWindow != nil && !self.trisWindow.hidden;
}

#pragma mark - Build UI

- (void)buildUI {
    UIWindowScene *scene = nil;
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            if (s.activationState == UISceneActivationStateForegroundActive) break;
        }
    }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;
    NSInteger colCount = [self visibleColumnCount];
    CGFloat colW = 53;  // ~320/6 per column
    CGFloat w = colCount * colW + 2;
    CGFloat h = screen.size.height * 0.25;

    // Restore saved position, fallback to center
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    CGFloat savedX = [ud doubleForKey:@"Speeder_TrisX"];
    CGFloat savedY = [ud doubleForKey:@"Speeder_TrisY"];
    CGFloat x = (savedX != 0) ? savedX : (screen.size.width  - w) / 2;
    CGFloat y = (savedY != 0) ? savedY : (screen.size.height - h) / 2;

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, y, w, h);
    win.windowLevel = UIWindowLevelAlert + 250;
    win.backgroundColor = UIColor.clearColor;

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = UIColor.clearColor;
    win.rootViewController = vc;

    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(dragTris:)];
    [vc.view addGestureRecognizer:pan];

    WKWebViewConfiguration *config = [[WKWebViewConfiguration alloc] init];
    [config.userContentController addScriptMessageHandler:self name:@"tris"];

    WKWebView *wv = [[WKWebView alloc] initWithFrame:CGRectMake(0, 0, w, h) configuration:config];
    wv.backgroundColor = UIColor.clearColor;
    wv.opaque = NO;
    wv.scrollView.bounces = NO;
    [vc.view addSubview:wv];
    self.trisWebView = wv;

    win.hidden = NO;
    self.trisWindow = win;
    [self refreshTrisHTML];
}

#pragma mark - Drag

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
    if (pan.state == UIGestureRecognizerStateEnded) {
        [self savePosition];
    }
}

#pragma mark - WKScriptMessageHandler

- (void)userContentController:(WKUserContentController *)uc didReceiveScriptMessage:(WKScriptMessage *)msg {
    NSString *body = [msg.body description];
    if ([body isEqualToString:@"close"]) {
        self.trisWindow.hidden = YES;
    } else if ([body isEqualToString:@"toggleMode"]) {
        self.symbolCountMode = !self.symbolCountMode;
        [self refreshTrisHTML];
    } else if ([body isEqualToString:@"reset"]) {
        [self confirmAndReset];
    }
}

- (void)confirmAndReset {
    UIViewController *vc = self.trisWindow.rootViewController;
    if (!vc) return;
    UIAlertController *ac = [UIAlertController
        alertControllerWithTitle:@"Reset Tris?"
        message:@"This clears all gap history, counters, and rotates the CSV."
        preferredStyle:UIAlertControllerStyleAlert];
    __weak typeof(self) weakSelf = self;
    [ac addAction:[UIAlertAction actionWithTitle:@"Reset" style:UIAlertActionStyleDestructive
        handler:^(UIAlertAction *a){ [weakSelf doReset]; }]];
    [ac addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [vc presentViewController:ac animated:YES completion:nil];
}

- (void)doReset {
    [self.histAttack removeAllObjects]; [self.histSteal  removeAllObjects];
    [self.histSpins  removeAllObjects]; [self.histShield removeAllObjects];
    [self.histAccum  removeAllObjects]; [self.histGold   removeAllObjects];
    [self.histVt     removeAllObjects];
    [self.symHistAttack removeAllObjects]; [self.symHistSteal  removeAllObjects];
    [self.symHistSpins  removeAllObjects]; [self.symHistShield removeAllObjects];
    [self.symHistAccum  removeAllObjects]; [self.symHistGold   removeAllObjects];
    self.totalSpins = 0;
    self.lastVtTotalSpins = -1;
    [self saveState];
    [[SLCounterOverlay shared] resetAllCounters];
    SLSpinStoreRotateCSV();
    [self refreshTrisHTML];
}

#pragma mark - HTML — 6 independent scrollable columns

- (void)refreshTrisHTML {
    NSArray *arrays[7], *symArrays[7];
    arrays[0] = self.histAttack; arrays[1] = self.histSteal; arrays[2] = self.histSpins;
    arrays[3] = self.histShield; arrays[4] = self.histAccum; arrays[5] = self.histGold;
    arrays[6] = self.histVt;
    symArrays[0] = self.symHistAttack; symArrays[1] = self.symHistSteal; symArrays[2] = self.symHistSpins;
    symArrays[3] = self.symHistShield; symArrays[4] = self.symHistAccum; symArrays[5] = self.symHistGold;
    symArrays[6] = self.histVt;  // VT has no sym-count mode; use same array

    NSString *emojis[7] = {@"🔨", @"🐷", @"💊", @"🛡", @"⭐", @"🧪", @"🎯"};
    NSString *colors[7] = {@"#00e5ff", @"#ff69b4", @"#00bcd4", @"#ce93d8", @"#ffd700", @"#4caf50", @"#ff9800"};
    NSString *colKeys[7] = {@"attack", @"steal", @"spins", @"shield", @"accumulation", @"potion", @"vt"};

    NSUInteger colBits[7] = {kSLTrisColAttack, kSLTrisColSteal, kSLTrisColSpins,
                              kSLTrisColShield, kSLTrisColAccum, kSLTrisColPotion, kSLTrisColVT};

    NSMutableString *colHTML = [NSMutableString string];
    for (int c = 0; c < 7; c++) {
        if (!(self.visibleColumns & colBits[c])) continue; // skip hidden columns
        NSArray *arr = (self.symbolCountMode && c < 6) ? symArrays[c] : arrays[c];
        NSMutableString *entries = [NSMutableString string];
        NSInteger gapIdx = 1;
        for (NSNumber *val in arr) {
            [entries appendFormat:@"<div class='e'><b>%ld-</b>%ld</div>",
                (long)gapIdx, (long)val.integerValue];
            gapIdx++;
        }
        BOOL locked = [self.lockTarget isEqualToString:colKeys[c]];
        NSString *lockStyle = locked ? [NSString stringWithFormat:@"border:1.5px solid %@", colors[c]] : @"";
        [colHTML appendFormat:
            @"<div class='col' style='%@'>"
            "<div class='ch' style='color:%@'>%@<div class='hb' style='background:%@'></div></div>"
            "<div class='cb' id='b%d'>%@</div>"
            "</div>",
            lockStyle, colors[c], emojis[c], colors[c], c, entries];
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
        "align-items:center;justify-content:center;font-size:10px;color:#fff;"
        "cursor:pointer;border:none;line-height:1}"
        ".cols{display:flex;flex:1;overflow:hidden;min-height:0}"
        ".col{flex:1;display:flex;flex-direction:column;"
        "border-right:1px solid rgba(255,255,255,0.18);min-width:0;border-radius:0}"
        ".col:last-child{border-right:none}"
        ".ch{text-align:center;font-size:12px;padding:3px 0;flex-shrink:0;"
        "display:flex;flex-direction:column;align-items:center;"
        "border-bottom:1px solid rgba(255,255,255,0.18)}"
        ".hb{height:2px;width:75%%;border-radius:1px;margin-top:1px}"
        ".cb{flex:1;overflow-y:auto;overflow-x:hidden}"
        ".cb::-webkit-scrollbar{display:none}"
        ".e{text-align:center;padding:2px 1px;font-size:10px;font-weight:400;"
        "border-bottom:1px solid rgba(255,255,255,0.03)}"
        ".col:nth-child(1) .e{color:#00e5ff}"
        ".col:nth-child(2) .e{color:#ff69b4}"
        ".col:nth-child(3) .e{color:#00bcd4}"
        ".col:nth-child(4) .e{color:#ce93d8}"
        ".col:nth-child(5) .e{color:#ffd700}"
        ".col:nth-child(6) .e{color:#4caf50}"
        ".col:nth-child(7) .e{color:#ff9800}"
        ".foot{display:flex;justify-content:space-between;padding:5px 8px;"
        "color:#aaa;font-size:10px;font-weight:600;flex-shrink:0;"
        "border-top:1px solid rgba(255,255,255,0.10)}"
        ".foot span{cursor:pointer}"
        "</style></head><body>"
        "<div class='panel'>"
        "<button class='close' onclick='msg(\"close\")'>✕</button>"
        "<div class='cols'>%@</div>"
        "<div class='foot'>"
        "<span onclick='msg(\"reset\")'>RESET</span>"
        "<span onclick='msg(\"toggleMode\")'>%@</span>"
        "<span id='spinTotal'>SPIN: %ld</span>"
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

- (void)toggleColumn:(NSUInteger)colBit {
    _visibleColumns ^= colBit;
    if (_visibleColumns == 0) _visibleColumns = colBit; // don't allow hiding all
    [[NSUserDefaults standardUserDefaults] setInteger:_visibleColumns forKey:@"Speeder_TrisVisibleCols"];
    if (self.trisWindow && !self.trisWindow.hidden) {
        [self resizeToFitColumns];
        [self refreshTrisHTML];
    }
}

- (NSInteger)visibleColumnCount {
    NSInteger count = 0;
    for (int i = 0; i < 7; i++) {
        if (_visibleColumns & (1 << i)) count++;
    }
    return count;
}

- (void)resizeToFitColumns {
    if (!self.trisWindow) return;
    NSInteger count = [self visibleColumnCount];
    CGFloat colW = 53;  // ~320/6 per column
    CGFloat newW = count * colW + 2; // +2 for border
    CGRect f = self.trisWindow.frame;
    f.size.width = newW;
    self.trisWindow.frame = f;
    self.trisWebView.frame = CGRectMake(0, 0, newW, f.size.height);
}

- (void)setLockTarget:(NSString *)lockTarget {
    _lockTarget = [lockTarget copy];
    [[NSUserDefaults standardUserDefaults] setObject:_lockTarget forKey:kSLDefaultsTrisLockTarget];
    // Refresh tris if visible so the locked column highlights update
    if (self.trisWindow && !self.trisWindow.hidden) [self refreshTrisHTML];
}

- (void)setSkipEnabled:(BOOL)skipEnabled {
    _skipEnabled = skipEnabled;
    [[NSUserDefaults standardUserDefaults] setBool:_skipEnabled forKey:@"Speeder_TrisSkip"];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
