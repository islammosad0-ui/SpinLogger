#import "SLMenuOverlay.h"
#import "SLConstants.h"
#import "SLSpinStore.h"
#import "SLSpeedController.h"
#import "SLSpinTarget.h"
#import "SLTrisController.h"
#import "SLPresetManager.h"
#import "SLCounterOverlay.h"
#import "SLNetworkMonitor.h"
#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>

// ---------------------------------------------------------------------------
//  SPEEDER ELITE — WKWebView-based floating panel
//  Matches One.dylib's dark glassmorphism UI with speed slider + buttons
// ---------------------------------------------------------------------------

static UIWindow *sMenuWindow = nil;
static UIWindow *sPanelWindow = nil;
static WKWebView *sPanelWebView = nil;

@interface SLMenuHandler : NSObject <WKScriptMessageHandler>
@end

@implementation SLMenuHandler

- (void)userContentController:(WKUserContentController *)uc didReceiveScriptMessage:(WKScriptMessage *)message {
    NSString *body = [message.body description];

    if ([body isEqualToString:@"close"]) {
        sPanelWindow.hidden = YES;
    }
    else if ([body hasPrefix:@"speed:"]) {
        double val = [[body substringFromIndex:6] doubleValue];
        if (val >= 1.0) SLSpeedControllerSetMultiplier(val);
        [self refreshPanel];
    }
    else if ([body isEqualToString:@"play"]) {
        // Toggle between 1x and saved speed
        double cur = SLSpeedControllerGetMultiplier();
        if (cur > 1.01) {
            SLSpeedControllerSetMultiplier(1.0);
        } else {
            double saved = [[NSUserDefaults standardUserDefaults] doubleForKey:@"Speeder_SavedSpeed"];
            SLSpeedControllerSetMultiplier(saved > 1.0 ? saved : 10.0);
        }
        [self refreshPanel];
    }
    else if ([body isEqualToString:@"minus"]) {
        double cur = SLSpeedControllerGetMultiplier();
        SLSpeedControllerSetMultiplier(MAX(1.0, cur - 1.0));
        [self refreshPanel];
    }
    else if ([body isEqualToString:@"plus"]) {
        double cur = SLSpeedControllerGetMultiplier();
        [[NSUserDefaults standardUserDefaults] setDouble:cur + 1.0 forKey:@"Speeder_SavedSpeed"];
        SLSpeedControllerSetMultiplier(MIN(50.0, cur + 1.0));
        [self refreshPanel];
    }
    else if ([body isEqualToString:@"reset"]) {
        [[SLCounterOverlay shared] resetAllCounters];
        [SLSpinTarget shared].currentSessionSpins = 0;
    }
    else if ([body isEqualToString:@"skip"]) {
        [SLTrisController shared].skipEnabled = ![SLTrisController shared].skipEnabled;
        [self refreshPanel];
    }
    else if ([body isEqualToString:@"network"]) {
        [[SLNetworkMonitor shared] show];
    }
    else if ([body isEqualToString:@"tris"]) {
        // Post notification to show tris monitor
        [[NSNotificationCenter defaultCenter] postNotificationName:@"SLShowTrisMonitor" object:nil];
    }
    else if ([body isEqualToString:@"counters"]) {
        [[NSNotificationCenter defaultCenter] postNotificationName:@"SLToggleCounters" object:nil];
    }
    else if ([body isEqualToString:@"settings"]) {
        [self showSettingsAlert];
    }
}

- (void)refreshPanel {
    if (!sPanelWebView || sPanelWindow.hidden) return;
    NSString *js = [NSString stringWithFormat:
        @"updateSpeed(%.2f)", SLSpeedControllerGetMultiplier()];
    [sPanelWebView evaluateJavaScript:js completionHandler:nil];
}

- (void)showSettingsAlert {
    UIViewController *top = [self topVC];
    if (!top) return;

    UIAlertController *sheet =
        [UIAlertController alertControllerWithTitle:@"SPEEDER Settings"
                                            message:nil
                                     preferredStyle:UIAlertControllerStyleActionSheet];

    // Share CSV
    [sheet addAction:[UIAlertAction actionWithTitle:@"Share CSV" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        NSURL *url = [NSURL fileURLWithPath:SLSpinStoreCSVPath()];
        UIActivityViewController *avc = [[UIActivityViewController alloc] initWithActivityItems:@[url] applicationActivities:nil];
        UIViewController *p = [self topVC];
        avc.popoverPresentationController.sourceView = p.view;
        avc.popoverPresentationController.sourceRect = CGRectMake(CGRectGetMidX(p.view.bounds), CGRectGetMidY(p.view.bounds), 0, 0);
        [p presentViewController:avc animated:YES completion:nil];
    }]];

    // Set Spin Target
    [sheet addAction:[UIAlertAction actionWithTitle:@"Set Spin Target" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        UIAlertController *a = [UIAlertController alertControllerWithTitle:@"Spin Target" message:nil preferredStyle:UIAlertControllerStyleAlert];
        [a addTextFieldWithConfigurationHandler:^(UITextField *tf) {
            tf.keyboardType = UIKeyboardTypeNumberPad;
            tf.text = [NSString stringWithFormat:@"%ld", (long)[SLSpinTarget shared].targetSpinCount];
        }];
        [a addAction:[UIAlertAction actionWithTitle:@"Set" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
            [SLSpinTarget shared].targetSpinCount = a.textFields.firstObject.text.integerValue;
        }]];
        [a addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
        [[self topVC] presentViewController:a animated:YES completion:nil];
    }]];

    // Auto-Reset Mode
    NSString *mode = [SLSpinTarget shared].autoResetMode ?: @"none";
    [sheet addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Auto-Reset: %@", mode] style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        UIAlertController *m = [UIAlertController alertControllerWithTitle:@"Auto-Reset" message:nil preferredStyle:UIAlertControllerStyleActionSheet];
        for (NSString *opt in @[@"none", @"symbol", @"global"]) {
            [m addAction:[UIAlertAction actionWithTitle:opt style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
                [SLSpinTarget shared].autoResetMode = opt;
            }]];
        }
        [m addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
        UIViewController *p = [self topVC];
        m.popoverPresentationController.sourceView = p.view;
        m.popoverPresentationController.sourceRect = CGRectMake(CGRectGetMidX(p.view.bounds), CGRectGetMidY(p.view.bounds), 0, 0);
        [p presentViewController:m animated:YES completion:nil];
    }]];

    // Save/Load Presets
    [sheet addAction:[UIAlertAction actionWithTitle:@"Save Preset 1" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) { [[SLPresetManager shared] savePreset:1]; }]];
    [sheet addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Load P1 (%@)", [[SLPresetManager shared] presetSummary:1]] style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) { [[SLPresetManager shared] loadPreset:1]; }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Save Preset 2" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) { [[SLPresetManager shared] savePreset:2]; }]];
    [sheet addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Load P2 (%@)", [[SLPresetManager shared] presetSummary:2]] style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) { [[SLPresetManager shared] loadPreset:2]; }]];

    [sheet addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    sheet.popoverPresentationController.sourceView = top.view;
    sheet.popoverPresentationController.sourceRect = CGRectMake(CGRectGetMidX(top.view.bounds), CGRectGetMidY(top.view.bounds), 0, 0);
    [top presentViewController:sheet animated:YES completion:nil];
}

- (UIViewController *)topVC {
    UIWindowScene *s = nil;
    for (UIScene *sc in UIApplication.sharedApplication.connectedScenes) {
        if ([sc isKindOfClass:[UIWindowScene class]] && sc.activationState == UISceneActivationStateForegroundActive) {
            s = (UIWindowScene *)sc; break;
        }
    }
    UIWindow *kw = nil;
    for (UIWindow *w in s.windows) { if (w.isKeyWindow) { kw = w; break; } }
    UIViewController *vc = kw.rootViewController;
    while (vc.presentedViewController) vc = vc.presentedViewController;
    return vc;
}

@end

// ---------------------------------------------------------------------------
//  HTML for SPEEDER ELITE panel
// ---------------------------------------------------------------------------
static NSString *SLPanelHTML(void) {
    double speed = SLSpeedControllerGetMultiplier();
    BOOL skipOn = [SLTrisController shared].skipEnabled;

    return [NSString stringWithFormat:@
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1,user-scalable=no'>"
    "<style>"
    "*{margin:0;padding:0;box-sizing:border-box;-webkit-user-select:none}"
    "body{font-family:-apple-system,sans-serif;background:transparent;overflow:hidden}"
    ".panel{background:rgba(18,25,40,0.92);border-radius:20px;padding:12px 14px;"
    "backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);"
    "border:1px solid rgba(255,255,255,0.08)}"
    /* Top row: icon + title + speed badge + gear */
    ".top{display:flex;align-items:center;gap:8px;margin-bottom:10px}"
    ".logo{width:36px;height:36px;background:linear-gradient(135deg,#00c9db,#0099aa);"
    "border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}"
    ".title{flex:1;font-size:15px;font-weight:700;color:#fff;letter-spacing:1px}"
    ".title span{color:#00e5ff}"
    ".speed-badge{background:rgba(0,229,255,0.15);border:1.5px solid #00e5ff;"
    "border-radius:10px;padding:4px 12px;font-size:16px;font-weight:700;color:#00e5ff;"
    "min-width:65px;text-align:center}"
    ".gear{width:36px;height:36px;background:rgba(255,255,255,0.1);border-radius:50%%;"
    "display:flex;align-items:center;justify-content:center;font-size:18px;color:#aaa;"
    "cursor:pointer;border:none}"
    /* Middle row: play, minus, slider, plus, close */
    ".controls{display:flex;align-items:center;gap:6px;background:rgba(0,0,0,0.3);"
    "border-radius:14px;padding:6px 8px;margin-bottom:10px}"
    ".btn{width:40px;height:40px;border-radius:12px;border:none;display:flex;"
    "align-items:center;justify-content:center;font-size:18px;cursor:pointer;"
    "color:#fff;background:rgba(255,255,255,0.08)}"
    ".btn-play{background:linear-gradient(135deg,#00c9db,#009aaa);width:44px;height:44px}"
    ".btn-close{color:#aaa;font-size:22px}"
    ".slider-wrap{flex:1;padding:0 4px}"
    "input[type=range]{-webkit-appearance:none;width:100%%;height:6px;"
    "background:rgba(255,255,255,0.15);border-radius:3px;outline:none}"
    "input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:22px;height:22px;"
    "background:#fff;border-radius:50%%;cursor:pointer;box-shadow:0 2px 6px rgba(0,0,0,0.3)}"
    /* Bottom row: action buttons */
    ".actions{display:flex;gap:6px}"
    ".abtn{height:42px;border-radius:12px;border:none;font-size:13px;font-weight:700;"
    "cursor:pointer;color:#fff;padding:0 14px;display:flex;align-items:center;justify-content:center}"
    ".abtn-active{background:linear-gradient(135deg,#00c9db,#009aaa)}"
    ".abtn-dim{background:rgba(255,255,255,0.08);color:#aaa}"
    ".abtn-skip{min-width:58px;font-size:14px;letter-spacing:1px}"
    ".flex1{flex:1}"
    "</style></head><body>"
    "<div class='panel'>"
    /* Top row */
    "<div class='top'>"
    "<div class='logo'>✈</div>"
    "<div class='title'>SPEEDER <span>ELITE</span></div>"
    "<div class='speed-badge' id='speedBadge'>%.2fx</div>"
    "<button class='gear' onclick='msg(\"settings\")'>⚙</button>"
    "</div>"
    /* Controls row */
    "<div class='controls'>"
    "<button class='btn btn-play' onclick='msg(\"play\")'>▶</button>"
    "<button class='btn' onclick='msg(\"minus\")'>−</button>"
    "<div class='slider-wrap'>"
    "<input type='range' id='slider' min='1' max='50' step='0.5' value='%.1f'"
    " oninput='onSlide(this.value)'>"
    "</div>"
    "<button class='btn' onclick='msg(\"plus\")'>+</button>"
    "<button class='btn btn-close' onclick='msg(\"close\")'>✕</button>"
    "</div>"
    /* Action buttons */
    "<div class='actions'>"
    "<button class='abtn abtn-active' onclick='msg(\"reset\")'>↺</button>"
    "<button class='abtn %@ abtn-skip' onclick='msg(\"skip\")'>SKIP</button>"
    "<button class='abtn abtn-active' onclick='msg(\"tris\")'>∞</button>"
    "<button class='abtn abtn-active' onclick='msg(\"network\")'>📶</button>"
    "<button class='abtn abtn-dim' onclick='msg(\"counters\")'>▦</button>"
    "<button class='abtn abtn-dim' onclick='msg(\"settings\")'>+</button>"
    "</div>"
    "</div>"
    "<script>"
    "function msg(s){window.webkit.messageHandlers.sl.postMessage(s)}"
    "function onSlide(v){document.getElementById('speedBadge').textContent=parseFloat(v).toFixed(2)+'x';msg('speed:'+v)}"
    "function updateSpeed(v){document.getElementById('speedBadge').textContent=v.toFixed(2)+'x';"
    "document.getElementById('slider').value=v}"
    "</script></body></html>",
    speed, speed, skipOn ? @"abtn-active" : @"abtn-dim"];
}

// ---------------------------------------------------------------------------
//  Show/Hide Panel
// ---------------------------------------------------------------------------
static SLMenuHandler *sHandler = nil;

static void SLShowPanel(void) {
    if (sPanelWindow) {
        sPanelWindow.hidden = !sPanelWindow.hidden;
        if (!sPanelWindow.hidden) {
            [sPanelWebView loadHTMLString:SLPanelHTML() baseURL:nil];
        }
        return;
    }

    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            if (s.activationState == UISceneActivationStateForegroundActive) break;
        }
    }
    if (!scene) return;

    sHandler = [[SLMenuHandler alloc] init];

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat panelW = MIN(screen.size.width - 20, 380);
    CGFloat panelH = 170;
    CGFloat x = (screen.size.width - panelW) / 2;
    CGFloat y = 50;  // top of screen with safe area

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, y, panelW, panelH);
    win.windowLevel = UIWindowLevelAlert + 300;
    win.backgroundColor = [UIColor clearColor];

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    // Add pan gesture to the window for dragging
    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:sHandler action:@selector(handlePan:)];
    [vc.view addGestureRecognizer:pan];

    WKWebViewConfiguration *config = [[WKWebViewConfiguration alloc] init];
    [config.userContentController addScriptMessageHandler:sHandler name:@"sl"];

    WKWebView *wv = [[WKWebView alloc] initWithFrame:CGRectMake(0, 0, panelW, panelH) configuration:config];
    wv.backgroundColor = [UIColor clearColor];
    wv.opaque = NO;
    wv.scrollView.scrollEnabled = NO;
    wv.scrollView.bounces = NO;
    [wv loadHTMLString:SLPanelHTML() baseURL:nil];
    [vc.view addSubview:wv];
    sPanelWebView = wv;

    win.hidden = NO;
    sPanelWindow = win;
}

// ---------------------------------------------------------------------------
//  Drag handler (category on SLMenuHandler)
// ---------------------------------------------------------------------------
@implementation SLMenuHandler (Drag)

- (void)handlePan:(UIPanGestureRecognizer *)pan {
    if (pan.state == UIGestureRecognizerStateBegan ||
        pan.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [pan translationInView:pan.view];
        CGRect f = sPanelWindow.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        sPanelWindow.frame = f;
        [pan setTranslation:CGPointZero inView:pan.view];
    }
}

@end

// ---------------------------------------------------------------------------
//  Floating "SL" button
// ---------------------------------------------------------------------------
@interface SLMenuButton : NSObject
+ (void)tapped;
+ (void)handlePan:(UIPanGestureRecognizer *)r;
@end

@implementation SLMenuButton

+ (void)tapped { SLShowPanel(); }

+ (void)handlePan:(UIPanGestureRecognizer *)r {
    if (r.state == UIGestureRecognizerStateBegan ||
        r.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [r translationInView:r.view.superview];
        CGRect f = sMenuWindow.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        sMenuWindow.frame = f;
        [r setTranslation:CGPointZero inView:r.view.superview];
    }
}

@end

// ---------------------------------------------------------------------------
//  Install
// ---------------------------------------------------------------------------
void SLMenuOverlayInstall(void) {
    if (sMenuWindow) return;

    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]] &&
            s.activationState == UISceneActivationStateForegroundActive) {
            scene = (UIWindowScene *)s; break;
        }
    }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat sz = 50;
    CGFloat x = screen.size.width - sz - 8;
    CGFloat y = screen.size.height / 2 - sz / 2;

    UIWindow *w = [[UIWindow alloc] initWithWindowScene:scene];
    w.frame = CGRectMake(x, y, sz, sz);
    w.windowLevel = UIWindowLevelAlert + 400;
    w.backgroundColor = [UIColor clearColor];

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    w.rootViewController = vc;

    UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
    btn.frame = CGRectMake(0, 0, sz, sz);
    btn.backgroundColor = [UIColor colorWithRed:0 green:0.79 blue:0.86 alpha:1];
    btn.layer.cornerRadius = sz / 2;
    btn.clipsToBounds = YES;
    [btn setTitle:@"SL" forState:UIControlStateNormal];
    [btn setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    btn.titleLabel.font = [UIFont boldSystemFontOfSize:16];
    [btn addTarget:[SLMenuButton class] action:@selector(tapped) forControlEvents:UIControlEventTouchUpInside];

    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:[SLMenuButton class] action:@selector(handlePan:)];
    [btn addGestureRecognizer:pan];
    [vc.view addSubview:btn];

    w.hidden = NO;
    sMenuWindow = w;
}
