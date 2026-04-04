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
//  SPEEDER ELITE — Complete UI System
//
//  Single WKWebView that manages all states:
//  - Collapsed: floating icon
//  - Expanded: main panel with speed controls
//  - Settings: two tabs (Tris Monitor / Spin Counter)
//
//  All in one panel that transforms between states.
// ---------------------------------------------------------------------------

static UIWindow *sPanelWindow = nil;
static WKWebView *sPanelWebView = nil;
BOOL sNetworkLocked = NO;  // non-static — accessed by SLNetworkInterceptor via extern

// Forward declarations
static void SLShowPanel(void);
static void SLHidePanel(void);
static NSString *SLPanelHTML(void);

@interface SLPanelHandler : NSObject <WKScriptMessageHandler>
@end

@implementation SLPanelHandler

- (void)userContentController:(WKUserContentController *)uc
      didReceiveScriptMessage:(WKScriptMessage *)message {
    NSDictionary *msg = nil;
    if ([message.body isKindOfClass:[NSDictionary class]]) {
        msg = message.body;
    } else {
        // Simple string message
        NSString *body = [message.body description];
        msg = @{@"action": body};
    }

    NSString *action = msg[@"action"] ?: @"";

    // --- Panel state ---
    if ([action isEqualToString:@"collapse"]) {
        SLHidePanel();
    }
    // --- Speed ---
    else if ([action isEqualToString:@"play"]) {
        double cur = SLSpeedControllerGetMultiplier();
        if (cur > 1.01) {
            SLSpeedControllerSetMultiplier(1.0);
        } else {
            double saved = [[NSUserDefaults standardUserDefaults] doubleForKey:@"Speeder_SavedSpeed"];
            SLSpeedControllerSetMultiplier(saved > 1.0 ? saved : 10.0);
        }
        [self syncSpeed];
    }
    else if ([action isEqualToString:@"minus"]) {
        double cur = SLSpeedControllerGetMultiplier();
        SLSpeedControllerSetMultiplier(MAX(1.0, cur - 1.0));
        [self syncSpeed];
    }
    else if ([action isEqualToString:@"plus"]) {
        double cur = SLSpeedControllerGetMultiplier();
        [[NSUserDefaults standardUserDefaults] setDouble:cur + 1.0 forKey:@"Speeder_SavedSpeed"];
        SLSpeedControllerSetMultiplier(MIN(50.0, cur + 1.0));
        [self syncSpeed];
    }
    else if ([action isEqualToString:@"speed"]) {
        double val = [msg[@"value"] doubleValue];
        if (val >= 1.0) {
            [[NSUserDefaults standardUserDefaults] setDouble:val forKey:@"Speeder_SavedSpeed"];
            SLSpeedControllerSetMultiplier(val);
        }
    }
    // --- Features ---
    else if ([action isEqualToString:@"reset"]) {
        [[SLCounterOverlay shared] resetAllCounters];
    }
    else if ([action isEqualToString:@"skip"]) {
        [SLTrisController shared].skipEnabled = ![SLTrisController shared].skipEnabled;
    }
    else if ([action isEqualToString:@"trisMonitor"]) {
        BOOL on = [msg[@"value"] boolValue];
        if (on) [[SLTrisController shared] showTrisMonitor];
        else [[SLTrisController shared] hideTrisMonitor];
    }
    else if ([action isEqualToString:@"network"]) {
        [[SLNetworkMonitor shared] show];
    }
    else if ([action isEqualToString:@"lockTarget"]) {
        NSString *sym = msg[@"symbol"];
        NSString *current = [SLTrisController shared].lockTarget;
        if ([sym isEqualToString:current]) {
            [SLTrisController shared].lockTarget = nil;  // deselect
        } else {
            [SLTrisController shared].lockTarget = sym;
        }
    }
    else if ([action isEqualToString:@"toggleCounter"]) {
        NSString *sym = msg[@"symbol"];
        [[NSNotificationCenter defaultCenter]
            postNotificationName:@"SLToggleCounterSymbol"
                          object:nil
                        userInfo:@{@"symbol": sym ?: @""}];
    }
    else if ([action isEqualToString:@"networkToggle"]) {
        BOOL on = [msg[@"value"] boolValue];
        sNetworkLocked = !on;
        NSLog(@"[SpinLogger] Network %@", sNetworkLocked ? @"BLOCKED" : @"RESTORED");
    }
    else if ([action isEqualToString:@"networkLockResume"]) {
        sNetworkLocked = NO;
    }
    else if ([action isEqualToString:@"targetSpinSave"]) {
        NSString *sym = msg[@"symbol"];
        NSInteger maxSpins = [msg[@"maxSpins"] integerValue];
        BOOL active = [msg[@"active"] boolValue];
        [SLSpinTarget shared].targetSpinCount = maxSpins;
        [SLTrisController shared].lockTarget = sym;
        NSLog(@"[SpinLogger] Target Spin: %@ within %ld spins (active=%d)", sym, (long)maxSpins, active);
    }
    else if ([action isEqualToString:@"targetSpinPower"]) {
        // Toggle target spin monitoring on/off
        BOOL active = [msg[@"active"] boolValue];
        NSLog(@"[SpinLogger] Target Spin power: %@", active ? @"ON" : @"OFF");
    }
    else if ([action isEqualToString:@"showAllCounters"]) {
        [[SLCounterOverlay shared] show];
    }
    else if ([action isEqualToString:@"hideAllCounters"]) {
        [[SLCounterOverlay shared] hide];
    }
    // --- Presets (from settings gear → action sheet) ---
    else if ([action isEqualToString:@"settings"]) {
        [self showSettingsAlert];
    }
}

- (void)syncSpeed {
    NSString *js = [NSString stringWithFormat:
        @"if(window.setSpeed)window.setSpeed(%.2f)", SLSpeedControllerGetMultiplier()];
    [sPanelWebView evaluateJavaScript:js completionHandler:nil];
}

- (void)showSettingsAlert {
    UIViewController *top = [self topVC];
    if (!top) return;

    UIAlertController *sheet =
        [UIAlertController alertControllerWithTitle:@"SPEEDER Settings"
                                            message:nil
                                     preferredStyle:UIAlertControllerStyleActionSheet];

    [sheet addAction:[UIAlertAction actionWithTitle:@"Share CSV" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        NSURL *url = [NSURL fileURLWithPath:SLSpinStoreCSVPath()];
        UIActivityViewController *avc = [[UIActivityViewController alloc] initWithActivityItems:@[url] applicationActivities:nil];
        UIViewController *p = [self topVC];
        avc.popoverPresentationController.sourceView = p.view;
        [p presentViewController:avc animated:YES completion:nil];
    }]];

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
        if ([sc isKindOfClass:[UIWindowScene class]] && sc.activationState == UISceneActivationStateForegroundActive) { s = (UIWindowScene *)sc; break; }
    }
    UIWindow *kw = nil;
    for (UIWindow *w in s.windows) { if (w.isKeyWindow) { kw = w; break; } }
    UIViewController *vc = kw.rootViewController;
    while (vc.presentedViewController) vc = vc.presentedViewController;
    return vc;
}

@end

// ---------------------------------------------------------------------------
//  Drag handler
// ---------------------------------------------------------------------------
@interface SLPanelHandler (Drag)
- (void)handlePan:(UIPanGestureRecognizer *)pan;
@end

@implementation SLPanelHandler (Drag)
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
//  HTML — Complete SPEEDER ELITE UI
// ---------------------------------------------------------------------------
static NSString *SLPanelHTML(void) {
    double speed = SLSpeedControllerGetMultiplier();

    return [NSString stringWithFormat:@
    "<!doctype html><html><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1,user-scalable=no'>"
    "<style>"
    ":root{"
    "--bg:rgba(16,22,36,0.94);"
    "--bg2:rgba(22,30,48,0.92);"
    "--accent:#00e5ff;"
    "--accent2:#00b8d4;"
    "--btn:rgba(255,255,255,0.07);"
    "--btn-active:linear-gradient(135deg,#00c9db,#009aaa);"
    "--text:#fff;"
    "--muted:#7a8a9e;"
    "--radius:16px;"
    "}"
    "*{margin:0;padding:0;box-sizing:border-box;-webkit-user-select:none;-webkit-tap-highlight-color:transparent}"
    "body{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display',sans-serif;"
    "background:transparent;overflow:hidden}"

    /* === PANEL === */
    "#panel{border-radius:var(--radius);"
    "background:var(--bg);backdrop-filter:blur(40px);-webkit-backdrop-filter:blur(40px);"
    "border:1px solid rgba(255,255,255,0.08);overflow:hidden;"
    "box-shadow:0 8px 40px rgba(0,0,0,0.5)}"

    /* Top bar */
    ".top{display:flex;align-items:center;gap:8px;padding:10px 12px 6px}"
    ".logo{width:38px;height:38px;background:linear-gradient(135deg,#0891b2,#06b6d4);"
    "border-radius:12px;display:flex;align-items:center;justify-content:center;"
    "font-size:18px;color:#fff}"
    ".title{flex:1;font-size:15px;font-weight:700;color:var(--text);letter-spacing:0.5px}"
    ".title em{font-style:normal;color:var(--accent)}"
    ".speed-badge{background:rgba(0,229,255,0.12);border:1.5px solid var(--accent);"
    "border-radius:10px;padding:4px 12px;font-size:16px;font-weight:700;"
    "color:var(--accent);min-width:62px;text-align:center}"
    ".gear{width:38px;height:38px;background:rgba(255,255,255,0.08);border-radius:50%%;"
    "border:none;display:flex;align-items:center;justify-content:center;"
    "font-size:18px;color:var(--muted);cursor:pointer}"
    ".gear:active{background:rgba(255,255,255,0.15)}"

    /* Controls row */
    ".controls{display:flex;align-items:center;gap:5px;"
    "background:rgba(0,0,0,0.25);border-radius:14px;padding:5px 7px;margin:0 10px}"
    ".cbtn{width:42px;height:42px;border-radius:12px;border:none;display:flex;"
    "align-items:center;justify-content:center;font-size:18px;cursor:pointer;"
    "color:var(--text);background:var(--btn);transition:all .15s}"
    ".cbtn:active{transform:scale(0.92)}"
    ".cbtn-play{background:var(--btn-active);width:46px;height:46px;border-radius:14px;"
    "font-size:20px}"
    ".cbtn-collapse{color:var(--muted);font-size:20px}"
    ".slider-wrap{flex:1;padding:0 6px}"
    "input[type=range]{-webkit-appearance:none;width:100%%;height:5px;"
    "background:rgba(255,255,255,0.12);border-radius:3px;outline:none}"
    "input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:22px;height:22px;"
    "background:#fff;border-radius:50%%;cursor:pointer;"
    "box-shadow:0 2px 8px rgba(0,0,0,0.3)}"

    /* Action row */
    ".actions{display:flex;gap:5px;padding:6px 10px 10px}"
    ".abtn{height:42px;border-radius:12px;border:none;font-size:13px;font-weight:700;"
    "cursor:pointer;color:#fff;padding:0 14px;display:flex;align-items:center;"
    "justify-content:center;transition:all .15s}"
    ".abtn:active{transform:scale(0.93)}"
    ".abtn-on{background:var(--btn-active)}"
    ".abtn-off{background:var(--btn);color:var(--muted)}"
    ".abtn-skip{min-width:60px;font-size:14px;letter-spacing:1px}"

    /* === SETTINGS VIEW === */
    "#settings{display:none;padding:0}"
    ".tabs{display:flex;padding:10px 10px 0;gap:0;position:relative}"
    ".tab{flex:1;padding:10px 0;text-align:center;font-size:13px;font-weight:700;"
    "color:var(--muted);cursor:pointer;border-radius:10px 10px 0 0;transition:all .2s}"
    ".tab.active{color:var(--accent);background:rgba(0,229,255,0.08)}"
    ".tab-close{width:40px;height:40px;background:rgba(255,255,255,0.1);"
    "border-radius:20px;border:none;font-size:18px;color:#fff;cursor:pointer;"
    "display:flex;align-items:center;justify-content:center}"
    ".tab-body{padding:12px 14px}"
    ".setting-row{display:flex;align-items:center;justify-content:space-between;"
    "padding:8px 0}"
    ".setting-label{font-size:13px;font-weight:700;color:var(--accent);letter-spacing:1px}"
    /* Toggle switch */
    ".toggle{width:48px;height:26px;border-radius:13px;background:rgba(255,255,255,0.15);"
    "position:relative;cursor:pointer;transition:background .2s}"
    ".toggle.on{background:var(--accent)}"
    ".toggle-knob{width:22px;height:22px;border-radius:11px;background:#fff;"
    "position:absolute;top:2px;left:2px;transition:left .2s;box-shadow:0 1px 4px rgba(0,0,0,0.3)}"
    ".toggle.on .toggle-knob{left:24px}"
    /* Symbol selector */
    ".sym-row{display:flex;gap:8px;padding:8px 0}"
    ".sym-btn{width:48px;height:48px;border-radius:14px;background:rgba(255,255,255,0.06);"
    "border:2px solid transparent;display:flex;align-items:center;justify-content:center;"
    "font-size:24px;cursor:pointer;transition:all .2s;opacity:0.5}"
    ".sym-btn.active{opacity:1;border-color:var(--accent);"
    "background:rgba(0,229,255,0.1);box-shadow:0 0 12px rgba(0,229,255,0.2)}"
    ".sym-btn:active{transform:scale(0.9)}"

    "</style></head><body>"

    "<div id='panel'>"
    /* Main view */
    "<div id='mainView'>"
    "<div class='top'>"
    "<div class='logo'>✈</div>"
    "<div class='title'>SPEEDER <em>ELITE</em></div>"
    "<div class='speed-badge' id='speedBadge' onclick='promptSpeed()'>%.2fx</div>"
    "<button class='gear' onclick='showSettings()'>⚙</button>"
    "</div>"
    "<div class='controls'>"
    "<button class='cbtn cbtn-play' onclick='msg({action:\"play\"})'>▶</button>"
    "<button class='cbtn' onclick='msg({action:\"minus\"})'>−</button>"
    "<div class='slider-wrap'>"
    "<input type='range' id='slider' min='1' max='50' step='0.5' value='%.1f'"
    " oninput='onSlide(this.value)'>"
    "</div>"
    "<button class='cbtn' onclick='msg({action:\"plus\"})'>+</button>"
    "<button class='cbtn cbtn-collapse' onclick='collapse()'>✕</button>"
    "</div>"
    "<div class='actions'>"
    "<button class='abtn abtn-on' onclick='toggleAllCounters()'>↺</button>"
    "<button class='abtn abtn-off abtn-skip'>SKIP</button>"
    "<button class='abtn abtn-on' onclick='showTargetSpin()'>∞</button>"
    "<button class='abtn abtn-on' id='netBtn' onclick='toggleNet()'>📶</button>"
    "<button class='abtn abtn-off'>+</button>"
    "<button class='abtn abtn-off'>+</button>"
    "</div>"
    "</div>"

    /* Settings view (hidden by default) */
    "<div id='settings'>"
    "<div class='tabs'>"
    "<div class='tab active' id='tabTris' onclick='switchTab(\"tris\")'>TRIS MONITOR</div>"
    "<div class='tab' id='tabCounter' onclick='switchTab(\"counter\")'>SPIN COUNTER</div>"
    "<button class='tab-close' onclick='hideSettings()'>✕</button>"
    "</div>"
    /* Tris tab content */
    "<div class='tab-body' id='trisContent'>"
    "<div class='setting-row'>"
    "<span class='setting-label'>ACTIVE MONITOR</span>"
    "<div class='toggle' id='trisToggle' onclick='toggleTris()'><div class='toggle-knob'></div></div>"
    "</div>"
    "<div class='setting-label' style='padding-top:8px'>LOCK TARGET</div>"
    "<div class='sym-row' id='lockRow'>"
    "<div class='sym-btn' data-sym='attack' onclick='lockTarget(\"attack\")'>🔨</div>"
    "<div class='sym-btn' data-sym='steal' onclick='lockTarget(\"steal\")'>🐷</div>"
    "<div class='sym-btn' data-sym='accumulation' onclick='lockTarget(\"accumulation\")'>💊</div>"
    "<div class='sym-btn' data-sym='shield' onclick='lockTarget(\"shield\")'>🛡</div>"
    "<div class='sym-btn' data-sym='goldSack' onclick='lockTarget(\"goldSack\")'>🧪</div>"
    "</div>"
    "</div>"
    /* Counter tab content */
    "<div class='tab-body' id='counterContent' style='display:none'>"
    "<div class='setting-label'>SHOW / HIDE COUNTERS</div>"
    "<div class='sym-row' id='counterRow'>"
    "<div class='sym-btn active' data-sym='attack' onclick='toggleCounterSym(\"attack\")'>🔨</div>"
    "<div class='sym-btn active' data-sym='steal' onclick='toggleCounterSym(\"steal\")'>🐷</div>"
    "<div class='sym-btn active' data-sym='accumulation' onclick='toggleCounterSym(\"accumulation\")'>💊</div>"
    "<div class='sym-btn active' data-sym='shield' onclick='toggleCounterSym(\"shield\")'>🛡</div>"
    "<div class='sym-btn active' data-sym='goldSack' onclick='toggleCounterSym(\"goldSack\")'>🧪</div>"
    "</div>"
    "</div>"

    /* Target Spin view */
    "<div id='targetSpin' style='display:none;padding:12px 14px'>"
    "<div class='setting-label' style='font-size:15px;color:#0f0;padding-bottom:10px'>TARGET SPIN</div>"
    "<div style='display:flex;align-items:center;gap:10px;padding-bottom:12px'>"
    "<div class='speed-badge' style='flex:1;font-size:18px;cursor:pointer;border-color:#0f0;color:#0f0'"
    " id='targetInput' onclick='promptTarget()'>∞</div>"
    "</div>"
    "<div class='sym-row' id='targetSymRow'>"
    "<div class='sym-btn' data-sym='attack' onclick='selectTargetSym(\"attack\")'>🔨</div>"
    "<div class='sym-btn' data-sym='steal' onclick='selectTargetSym(\"steal\")'>🐷</div>"
    "<div class='sym-btn' data-sym='accumulation' onclick='selectTargetSym(\"accumulation\")'>💊</div>"
    "<div class='sym-btn' data-sym='shield' onclick='selectTargetSym(\"shield\")'>🛡</div>"
    "<div class='sym-btn' data-sym='goldSack' onclick='selectTargetSym(\"goldSack\")'>🧪</div>"
    "</div>"
    "<div style='display:flex;gap:8px;padding-top:10px;align-items:center'>"
    "<button class='cbtn' id='targetPower' onclick='toggleTargetPower()'"
    " style='width:36px;height:36px;border-radius:18px;font-size:16px;color:#f44'>⏻</button>"
    "<button class='abtn abtn-off' style='flex:1' onclick='hideTargetSpin()'>BACK</button>"
    "<button class='abtn' style='flex:1;background:#0f0;color:#000;font-weight:800'"
    " onclick='saveTarget()'>SAVE</button>"
    "</div>"
    "</div>"

    "</div>"
    "</div>"

    "<script>"
    "function msg(o){window.webkit.messageHandlers.sl.postMessage(o)}"
    "function collapse(){msg({action:'collapse'})}"
    "function onSlide(v){document.getElementById('speedBadge').textContent="
    "parseFloat(v).toFixed(2)+'x';msg({action:'speed',value:parseFloat(v)})}"
    "window.setSpeed=function(v){document.getElementById('speedBadge').textContent="
    "v.toFixed(2)+'x';document.getElementById('slider').value=v}"

    /* Settings */
    "function showSettings(){document.getElementById('mainView').style.display='none';"
    "document.getElementById('settings').style.display='block'}"
    "function hideSettings(){document.getElementById('settings').style.display='none';"
    "document.getElementById('mainView').style.display='block'}"
    "function switchTab(t){var tris=t==='tris';"
    "document.getElementById('tabTris').className='tab'+(tris?' active':'');"
    "document.getElementById('tabCounter').className='tab'+(!tris?' active':'');"
    "document.getElementById('trisContent').style.display=tris?'block':'none';"
    "document.getElementById('counterContent').style.display=!tris?'block':'none'}"

    /* Tris toggle */
    "var trisOn=false;"
    "function toggleTris(){trisOn=!trisOn;"
    "document.getElementById('trisToggle').className='toggle'+(trisOn?' on':'');"
    "msg({action:'trisMonitor',value:trisOn})}"

    /* Lock target */
    "var lockedSym=null;"
    "function lockTarget(s){var btns=document.querySelectorAll('#lockRow .sym-btn');"
    "if(lockedSym===s){lockedSym=null;btns.forEach(function(b){b.className='sym-btn'})}"
    "else{lockedSym=s;btns.forEach(function(b){"
    "b.className='sym-btn'+(b.dataset.sym===s?' active':'')})}"
    "msg({action:'lockTarget',symbol:lockedSym})}"

    /* Counter visibility toggles */
    "function toggleCounterSym(s){var btn=document.querySelector('#counterRow [data-sym=\"'+s+'\"]');"
    "btn.classList.toggle('active');msg({action:'toggleCounter',symbol:s})}"

    /* Speed manual input */
    "function promptSpeed(){var v=prompt('Enter speed (1-50):',document.getElementById('slider').value);"
    "if(v&&parseFloat(v)>=1){onSlide(parseFloat(v));document.getElementById('slider').value=parseFloat(v)}}"

    /* Toggle all counters visibility */
    "var allCountersVisible=true;"
    "function toggleAllCounters(){allCountersVisible=!allCountersVisible;"
    "msg({action:allCountersVisible?'showAllCounters':'hideAllCounters'})}"

    /* Network manual kill switch */
    "var netOff=false;"
    "function toggleNet(){netOff=!netOff;"
    "var btn=document.getElementById('netBtn');"
    "btn.className='abtn '+(netOff?'abtn-off':'abtn-on');"
    "btn.style.opacity=netOff?'0.5':'1';"
    "msg({action:'networkToggle',value:!netOff})}"

    /* Target Spin */
    "var targetSym=null,targetCount=0,targetActive=false;"
    "function showTargetSpin(){document.getElementById('mainView').style.display='none';"
    "document.getElementById('settings').style.display='none';"
    "document.getElementById('targetSpin').style.display='block'}"
    "function hideTargetSpin(){document.getElementById('targetSpin').style.display='none';"
    "document.getElementById('mainView').style.display='block'}"
    "function promptTarget(){var v=prompt('Max spins before cutoff:',targetCount||'');"
    "if(v&&parseInt(v)>0){targetCount=parseInt(v);"
    "document.getElementById('targetInput').textContent=targetCount}}"
    "function selectTargetSym(s){targetSym=s;"
    "document.querySelectorAll('#targetSymRow .sym-btn').forEach(function(b){"
    "b.className='sym-btn'+(b.dataset.sym===s?' active':'')})}"
    "function toggleTargetPower(){targetActive=!targetActive;"
    "var btn=document.getElementById('targetPower');"
    "btn.style.color=targetActive?'#0f0':'#f44';"
    "msg({action:'targetSpinPower',active:targetActive})}"
    "function saveTarget(){if(targetSym&&targetCount>0){"
    "msg({action:'targetSpinSave',symbol:targetSym,maxSpins:targetCount,active:targetActive});"
    "hideTargetSpin()}else{alert('Select a symbol and set max spins')}}"
    "</script></body></html>",
    speed, speed];
}

// ---------------------------------------------------------------------------
//  Install — Native button for icon, WKWebView for panel
// ---------------------------------------------------------------------------
static SLPanelHandler *sHandler = nil;
static UIWindow *sIconWindow = nil;

@interface SLIconTarget : NSObject
+ (void)tapped;
+ (void)handleIconPan:(UIPanGestureRecognizer *)r;
@end

@implementation SLIconTarget
+ (void)tapped {
    SLShowPanel();
}
+ (void)handleIconPan:(UIPanGestureRecognizer *)r {
    if (r.state == UIGestureRecognizerStateBegan ||
        r.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [r translationInView:r.view.superview];
        CGRect f = sIconWindow.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        sIconWindow.frame = f;
        [r setTranslation:CGPointZero inView:r.view.superview];
    }
}
@end

static void SLShowPanel(void) {
    sIconWindow.hidden = YES;

    if (sPanelWindow) {
        // Reload HTML to get fresh speed value
        [sPanelWebView loadHTMLString:SLPanelHTML() baseURL:nil];
        sPanelWindow.hidden = NO;
        return;
    }

    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) { scene = (UIWindowScene *)s; break; }
    }
    if (!scene) return;

    sHandler = [[SLPanelHandler alloc] init];

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat pw = MIN(screen.size.width - 20, 380);
    CGFloat ph = 195;
    CGFloat x = (screen.size.width - pw) / 2;

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, 50, pw, ph);
    win.windowLevel = UIWindowLevelAlert + 400;
    win.backgroundColor = [UIColor clearColor];

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc]
        initWithTarget:sHandler action:@selector(handlePan:)];
    [vc.view addGestureRecognizer:pan];

    WKWebViewConfiguration *config = [[WKWebViewConfiguration alloc] init];
    [config.userContentController addScriptMessageHandler:sHandler name:@"sl"];

    WKWebView *wv = [[WKWebView alloc] initWithFrame:CGRectMake(0, 0, pw, ph)
                                        configuration:config];
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

static void SLHidePanel(void) {
    sPanelWindow.hidden = YES;
    sIconWindow.hidden = NO;
}

void SLMenuOverlayInstall(void) {
    if (sIconWindow) return;

    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]] &&
            s.activationState == UISceneActivationStateForegroundActive) {
            scene = (UIWindowScene *)s; break;
        }
    }
    if (!scene) return;

    // Native floating button
    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat sz = 50;
    CGFloat bx = screen.size.width - sz - 10;
    CGFloat by = screen.size.height / 2 - sz / 2;

    UIWindow *iconWin = [[UIWindow alloc] initWithWindowScene:scene];
    iconWin.frame = CGRectMake(bx, by, sz, sz);
    iconWin.windowLevel = UIWindowLevelAlert + 400;
    iconWin.backgroundColor = [UIColor clearColor];

    UIViewController *iconVC = [[UIViewController alloc] init];
    iconVC.view.backgroundColor = [UIColor clearColor];
    iconWin.rootViewController = iconVC;

    UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
    btn.frame = CGRectMake(0, 0, sz, sz);
    btn.backgroundColor = [UIColor colorWithRed:0 green:0.9 blue:1.0 alpha:1.0];
    btn.layer.cornerRadius = sz / 2;
    btn.clipsToBounds = YES;
    [btn setTitle:@"SL" forState:UIControlStateNormal];
    [btn setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    btn.titleLabel.font = [UIFont boldSystemFontOfSize:18];
    [btn addTarget:[SLIconTarget class] action:@selector(tapped) forControlEvents:UIControlEventTouchUpInside];

    UIPanGestureRecognizer *iconPan = [[UIPanGestureRecognizer alloc]
        initWithTarget:[SLIconTarget class] action:@selector(handleIconPan:)];
    [btn addGestureRecognizer:iconPan];

    [iconVC.view addSubview:btn];
    iconWin.hidden = NO;
    sIconWindow = iconWin;
}
