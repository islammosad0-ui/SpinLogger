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

// ---------------------------------------------------------------------------
//  SPEEDER ELITE — 100% Native UIKit (no WKWebView)
//
//  WKWebView onclick was broken on iOS. Native UIButton always works.
//  UIVisualEffectView for glassmorphism blur.
// ---------------------------------------------------------------------------

BOOL sNetworkLocked = NO;

static UIWindow *sIconWindow = nil;
static UIWindow *sPanelWindow = nil;
static UISlider *sSlider = nil;

// Forward declarations
static void SLShowPanel(void);
static void SLHidePanel(void);

#pragma mark - Colors

static UIColor *SLAccent(void) { return [UIColor colorWithRed:0 green:0.9 blue:1.0 alpha:1]; }
static UIColor *SLBtnBg(void) { return [UIColor colorWithRed:1 green:1 blue:1 alpha:0.08]; }
static UIColor *SLBtnActive(void) { return [UIColor colorWithRed:0 green:0.79 blue:0.86 alpha:1]; }
static UIColor *SLMuted(void) { return [UIColor colorWithRed:0.48 green:0.54 blue:0.62 alpha:1]; }

#pragma mark - Button factory

static UIButton *sSpeedBadgeBtn = nil;  // need reference to update title

static UIButton *SLMakeBtn(NSString *title, CGFloat w, CGFloat h, UIColor *bg, UIColor *fg, CGFloat fontSize) {
    UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
    btn.frame = CGRectMake(0, 0, w, h);
    btn.backgroundColor = bg;
    btn.layer.cornerRadius = h > 38 ? 14 : 11;
    btn.clipsToBounds = YES;
    [btn setTitle:title forState:UIControlStateNormal];
    [btn setTitleColor:fg forState:UIControlStateNormal];
    btn.titleLabel.font = [UIFont boldSystemFontOfSize:fontSize];
    // Press feedback: dim on highlight
    [btn setTitleColor:[fg colorWithAlphaComponent:0.5] forState:UIControlStateHighlighted];
    btn.adjustsImageWhenHighlighted = YES;
    [btn addTarget:btn action:@selector(setNeedsDisplay) forControlEvents:UIControlEventTouchDown];
    btn.showsTouchWhenHighlighted = YES;
    return btn;
}

#pragma mark - Actions

@interface SLActions : NSObject
+ (void)collapse;
+ (void)play;
+ (void)minus;
+ (void)plus;
+ (void)sliderChanged:(UISlider *)slider;
+ (void)speedBadgeTap;
+ (void)gearTap;
+ (void)resetCounters;
+ (void)targetSpin;
+ (void)networkToggle;
+ (void)trisMonitor;
@end

@implementation SLActions

+ (void)collapse { SLHidePanel(); }

+ (void)play {
    double cur = SLSpeedControllerGetMultiplier();
    if (cur > 1.01) {
        SLSpeedControllerSetMultiplier(1.0);
    } else {
        double saved = [[NSUserDefaults standardUserDefaults] doubleForKey:@"Speeder_SavedSpeed"];
        SLSpeedControllerSetMultiplier(saved > 1.0 ? saved : 10.0);
    }
    [self syncUI];
}

+ (void)minus {
    SLSpeedControllerSetMultiplier(MAX(1.0, SLSpeedControllerGetMultiplier() - 1.0));
    [self syncUI];
}

+ (void)plus {
    double v = SLSpeedControllerGetMultiplier() + 1.0;
    [[NSUserDefaults standardUserDefaults] setDouble:v forKey:@"Speeder_SavedSpeed"];
    SLSpeedControllerSetMultiplier(MIN(50.0, v));
    [self syncUI];
}

+ (void)sliderChanged:(UISlider *)slider {
    double v = slider.value;
    [[NSUserDefaults standardUserDefaults] setDouble:v forKey:@"Speeder_SavedSpeed"];
    SLSpeedControllerSetMultiplier(v);
    [sSpeedBadgeBtn setTitle:[NSString stringWithFormat:@"%.2fx", v] forState:UIControlStateNormal];
}

+ (void)speedBadgeTap {
    UIAlertController *a = [UIAlertController alertControllerWithTitle:@"Speed" message:nil preferredStyle:UIAlertControllerStyleAlert];
    [a addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.keyboardType = UIKeyboardTypeDecimalPad;
        tf.text = [NSString stringWithFormat:@"%.1f", SLSpeedControllerGetMultiplier()];
    }];
    [a addAction:[UIAlertAction actionWithTitle:@"Set" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        double v = a.textFields.firstObject.text.doubleValue;
        if (v >= 1.0) { SLSpeedControllerSetMultiplier(MIN(50,v)); [self syncUI]; }
    }]];
    [a addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [[self topVC] presentViewController:a animated:YES completion:nil];
}

static UIWindow *sSettingsWindow = nil;
static UIView *sTrisContent = nil;
static UIView *sCounterContent = nil;
static UIButton *sTabTris = nil;
static UIButton *sTabCounter = nil;
static BOOL sTrisMonitorActive = NO;

+ (void)gearTap {
    [self showSettingsOverlay];
}

+ (void)showSettingsOverlay {
    if (sSettingsWindow) { sSettingsWindow.hidden = NO; return; }

    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes)
        if ([s isKindOfClass:[UIWindowScene class]]) { scene = (UIWindowScene *)s; break; }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat pw = MIN(screen.size.width * 0.78, 320);
    CGFloat ph = 200;
    CGFloat x = (screen.size.width - pw) / 2;
    CGFloat y = (screen.size.height - ph) / 2;

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, y, pw, ph);
    win.windowLevel = UIWindowLevelAlert + 450;
    win.backgroundColor = [UIColor clearColor];

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    UIVisualEffectView *blur = [[UIVisualEffectView alloc] initWithEffect:[UIBlurEffect effectWithStyle:UIBlurEffectStyleDark]];
    blur.frame = CGRectMake(0, 0, pw, ph);
    blur.layer.cornerRadius = 18;
    blur.clipsToBounds = YES;
    blur.alpha = 0.95;
    [vc.view addSubview:blur];
    UIView *content = blur.contentView;

    CGFloat pad = 12;

    // Tab bar
    CGFloat tabW = (pw - pad * 2 - 46) / 2;
    sTabTris = SLMakeBtn(@"TRIS MONITOR", tabW, 32, SLAccent(), [UIColor blackColor], 12);
    sTabTris.frame = CGRectMake(pad, 8, tabW, 32);
    [sTabTris addTarget:self action:@selector(switchToTrisTab) forControlEvents:UIControlEventTouchUpInside];
    [content addSubview:sTabTris];

    sTabCounter = SLMakeBtn(@"SPIN COUNTER", tabW, 32, SLBtnBg(), SLMuted(), 12);
    sTabCounter.frame = CGRectMake(pad + tabW + 4, 8, tabW, 32);
    [sTabCounter addTarget:self action:@selector(switchToCounterTab) forControlEvents:UIControlEventTouchUpInside];
    [content addSubview:sTabCounter];

    // Close X
    UIButton *closeBtn = SLMakeBtn(@"✕", 36, 32, [UIColor colorWithWhite:1 alpha:0.15], [UIColor whiteColor], 16);
    closeBtn.frame = CGRectMake(pw - pad - 36, 8, 36, 32);
    closeBtn.layer.cornerRadius = 16;
    [closeBtn addTarget:self action:@selector(settingsClose) forControlEvents:UIControlEventTouchUpInside];
    [content addSubview:closeBtn];

    // === TRIS MONITOR content ===
    sTrisContent = [[UIView alloc] initWithFrame:CGRectMake(0, 46, pw, ph - 46)];
    [content addSubview:sTrisContent];

    // ACTIVE MONITOR row
    UILabel *amLabel = [[UILabel alloc] initWithFrame:CGRectMake(pad, 8, 150, 24)];
    amLabel.text = @"ACTIVE MONITOR";
    amLabel.font = [UIFont boldSystemFontOfSize:13];
    amLabel.textColor = SLAccent();
    [sTrisContent addSubview:amLabel];

    UISwitch *amSwitch = [[UISwitch alloc] initWithFrame:CGRectMake(pw - pad - 51, 4, 51, 31)];
    amSwitch.onTintColor = SLAccent();
    amSwitch.on = sTrisMonitorActive;
    [amSwitch addTarget:self action:@selector(trisMonitorToggle:) forControlEvents:UIControlEventValueChanged];
    [sTrisContent addSubview:amSwitch];

    // LOCK TARGET row
    UILabel *ltLabel = [[UILabel alloc] initWithFrame:CGRectMake(pad, 40, 150, 24)];
    ltLabel.text = @"LOCK TARGET";
    ltLabel.font = [UIFont boldSystemFontOfSize:13];
    ltLabel.textColor = SLAccent();
    [sTrisContent addSubview:ltLabel];

    NSArray *syms = @[@"🔨", @"🐷", @"💊", @"🛡", @"⭐", @"🧪"];
    NSArray *keys = @[@"attack", @"steal", @"spins", @"shield", @"accumulation", @"goldSack"];
    CGFloat symSize = 38;
    CGFloat symGap = 5;
    CGFloat symStartX = pad;
    NSString *curLock = [SLTrisController shared].lockTarget;

    for (NSUInteger i = 0; i < syms.count; i++) {
        UIButton *sb = [UIButton buttonWithType:UIButtonTypeCustom];
        sb.frame = CGRectMake(symStartX + i * (symSize + symGap), 68, symSize, symSize);
        sb.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
        sb.layer.cornerRadius = 12;
        sb.layer.borderWidth = 2;
        sb.layer.borderColor = [curLock isEqualToString:keys[i]] ? SLAccent().CGColor : [UIColor clearColor].CGColor;
        [sb setTitle:syms[i] forState:UIControlStateNormal];
        sb.titleLabel.font = [UIFont systemFontOfSize:20];
        sb.tag = 300 + i;
        sb.showsTouchWhenHighlighted = YES;
        [sb addTarget:self action:@selector(lockTargetTap:) forControlEvents:UIControlEventTouchUpInside];
        [sTrisContent addSubview:sb];
    }

    // === SPIN COUNTER content (hidden by default) ===
    sCounterContent = [[UIView alloc] initWithFrame:CGRectMake(0, 46, pw, ph - 46)];
    sCounterContent.hidden = YES;
    [content addSubview:sCounterContent];

    UILabel *scLabel = [[UILabel alloc] initWithFrame:CGRectMake(pad, 8, 200, 24)];
    scLabel.text = @"SHOW / HIDE COUNTERS";
    scLabel.font = [UIFont boldSystemFontOfSize:13];
    scLabel.textColor = SLAccent();
    [sCounterContent addSubview:scLabel];

    for (NSUInteger i = 0; i < syms.count; i++) {
        UIButton *sb = [UIButton buttonWithType:UIButtonTypeCustom];
        sb.frame = CGRectMake(symStartX + i * (symSize + symGap), 40, symSize, symSize);
        sb.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
        sb.layer.cornerRadius = 12;
        sb.layer.borderWidth = 2;
        sb.layer.borderColor = SLAccent().CGColor;  // all visible by default
        [sb setTitle:syms[i] forState:UIControlStateNormal];
        sb.titleLabel.font = [UIFont systemFontOfSize:20];
        sb.tag = 400 + i;
        sb.showsTouchWhenHighlighted = YES;
        [sb addTarget:self action:@selector(counterVisibilityTap:) forControlEvents:UIControlEventTouchUpInside];
        [sCounterContent addSubview:sb];
    }

    win.hidden = NO;
    sSettingsWindow = win;
}

+ (void)switchToTrisTab {
    sTabTris.backgroundColor = SLAccent();
    [sTabTris setTitleColor:[UIColor blackColor] forState:UIControlStateNormal];
    sTabCounter.backgroundColor = SLBtnBg();
    [sTabCounter setTitleColor:SLMuted() forState:UIControlStateNormal];
    sTrisContent.hidden = NO;
    sCounterContent.hidden = YES;
}

+ (void)switchToCounterTab {
    sTabCounter.backgroundColor = SLAccent();
    [sTabCounter setTitleColor:[UIColor blackColor] forState:UIControlStateNormal];
    sTabTris.backgroundColor = SLBtnBg();
    [sTabTris setTitleColor:SLMuted() forState:UIControlStateNormal];
    sCounterContent.hidden = NO;
    sTrisContent.hidden = YES;
}

+ (void)settingsClose {
    sSettingsWindow.hidden = YES;
}

+ (void)trisMonitorToggle:(UISwitch *)sw {
    sTrisMonitorActive = sw.on;
    if (sw.on) [[SLTrisController shared] showTrisMonitor];
    else [[SLTrisController shared] hideTrisMonitor];
}

+ (void)lockTargetTap:(UIButton *)btn {
    NSArray *keys = @[@"attack", @"steal", @"spins", @"shield", @"accumulation", @"goldSack"];
    NSUInteger idx = btn.tag - 300;
    if (idx >= keys.count) return;

    NSString *cur = [SLTrisController shared].lockTarget;
    if ([cur isEqualToString:keys[idx]]) {
        [SLTrisController shared].lockTarget = nil;
    } else {
        [SLTrisController shared].lockTarget = keys[idx];
    }

    // Update borders
    NSString *newLock = [SLTrisController shared].lockTarget;
    for (NSUInteger i = 0; i < keys.count; i++) {
        UIButton *sb = [sSettingsWindow.rootViewController.view viewWithTag:(300 + i)];
        sb.layer.borderColor = [newLock isEqualToString:keys[i]] ? SLAccent().CGColor : [UIColor clearColor].CGColor;
    }
}

+ (void)counterVisibilityTap:(UIButton *)btn {
    NSArray *keys = @[@"attack", @"steal", @"spins", @"shield", @"accumulation", @"goldSack"];
    NSUInteger idx = btn.tag - 400;
    if (idx >= keys.count) return;

    // Toggle border (visible = cyan border, hidden = no border)
    BOOL isActive = (btn.layer.borderColor != [UIColor clearColor].CGColor);
    btn.layer.borderColor = isActive ? [UIColor clearColor].CGColor : SLAccent().CGColor;
    btn.alpha = isActive ? 0.4 : 1.0;

    [[NSNotificationCenter defaultCenter] postNotificationName:@"SLToggleCounterSymbol" object:nil
                                                      userInfo:@{@"symbol": keys[idx]}];
}

+ (void)resetCounters {
    // Toggle all counters show/hide (NOT reset)
    [[NSNotificationCenter defaultCenter] postNotificationName:@"SLToggleCounters" object:nil];
}

+ (void)targetSpin {
    [self showTargetSpinOverlay];
}

static UIWindow *sTargetWindow = nil;
static NSString *sTargetSymbol = nil;
static NSInteger sTargetMaxSpins = 0;
static BOOL sTargetActive = NO;

+ (void)showTargetSpinOverlay {
    if (sTargetWindow) { sTargetWindow.hidden = NO; return; }

    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes)
        if ([s isKindOfClass:[UIWindowScene class]]) { scene = (UIWindowScene *)s; break; }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat pw = MIN(screen.size.width * 0.75, 300);
    CGFloat ph = 180;
    CGFloat x = (screen.size.width - pw) / 2;
    CGFloat y = (screen.size.height - ph) / 2;

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, y, pw, ph);
    win.windowLevel = UIWindowLevelAlert + 500;
    win.backgroundColor = [UIColor clearColor];

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    // Dark background with green border (matching screenshot)
    UIView *bg = [[UIView alloc] initWithFrame:CGRectMake(0, 0, pw, ph)];
    bg.backgroundColor = [UIColor colorWithRed:0.08 green:0.12 blue:0.1 alpha:0.95];
    bg.layer.cornerRadius = 18;
    bg.layer.borderWidth = 1.5;
    bg.layer.borderColor = [UIColor colorWithRed:0 green:0.8 blue:0 alpha:0.6].CGColor;
    bg.clipsToBounds = YES;
    [vc.view addSubview:bg];

    CGFloat pad = 14;

    // Title: TARGET SPIN
    UILabel *title = [[UILabel alloc] initWithFrame:CGRectMake(pad, 10, 140, 28)];
    title.text = @"TARGET SPIN";
    title.font = [UIFont boldSystemFontOfSize:16];
    title.textColor = [UIColor colorWithRed:0 green:0.9 blue:0 alpha:1];
    [bg addSubview:title];

    // ∞ input box
    UIButton *inputBox = [UIButton buttonWithType:UIButtonTypeCustom];
    inputBox.frame = CGRectMake(pw - pad - 100, 8, 100, 32);
    inputBox.backgroundColor = [UIColor colorWithWhite:0.1 alpha:1];
    inputBox.layer.cornerRadius = 8;
    [inputBox setTitle:(sTargetMaxSpins > 0 ? [NSString stringWithFormat:@"%ld", (long)sTargetMaxSpins] : @"∞") forState:UIControlStateNormal];
    [inputBox setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    inputBox.titleLabel.font = [UIFont boldSystemFontOfSize:16];
    inputBox.showsTouchWhenHighlighted = YES;
    [inputBox addTarget:self action:@selector(targetInputTap) forControlEvents:UIControlEventTouchUpInside];
    inputBox.tag = 999;
    [bg addSubview:inputBox];

    // Symbol buttons row
    CGFloat symY = 48;
    CGFloat symSize = 40;
    CGFloat symGap = 6;
    NSArray *syms = @[@"🔨", @"🐷", @"💊", @"🛡", @"⭐", @"🧪"];
    NSArray *keys = @[@"attack", @"steal", @"spins", @"shield", @"accumulation", @"goldSack"];
    CGFloat totalSymW = syms.count * symSize + (syms.count - 1) * symGap;
    CGFloat symStartX = (pw - totalSymW) / 2;

    for (NSUInteger i = 0; i < syms.count; i++) {
        UIButton *sb = [UIButton buttonWithType:UIButtonTypeCustom];
        sb.frame = CGRectMake(symStartX + i * (symSize + symGap), symY, symSize, symSize);
        sb.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
        sb.layer.cornerRadius = 12;
        sb.layer.borderWidth = 2;
        sb.layer.borderColor = [UIColor clearColor].CGColor;
        [sb setTitle:syms[i] forState:UIControlStateNormal];
        sb.titleLabel.font = [UIFont systemFontOfSize:22];
        sb.tag = 100 + i;
        sb.showsTouchWhenHighlighted = YES;
        [sb addTarget:self action:@selector(targetSymbolTap:) forControlEvents:UIControlEventTouchUpInside];

        // Highlight if already selected
        if ([sTargetSymbol isEqualToString:keys[i]]) {
            sb.layer.borderColor = [UIColor colorWithRed:0 green:0.9 blue:0 alpha:1].CGColor;
            sb.backgroundColor = [UIColor colorWithRed:0 green:0.2 blue:0 alpha:1];
        }
        [bg addSubview:sb];
    }

    // Bottom row: Power, BACK, SAVE
    CGFloat btnY = symY + symSize + 14;

    // Power button
    UIButton *power = [UIButton buttonWithType:UIButtonTypeCustom];
    power.frame = CGRectMake(pad, btnY, 36, 36);
    power.layer.cornerRadius = 18;
    power.layer.borderWidth = 2;
    power.layer.borderColor = [UIColor redColor].CGColor;
    power.backgroundColor = [UIColor clearColor];
    [power setTitle:@"⏻" forState:UIControlStateNormal];
    [power setTitleColor:(sTargetActive ? [UIColor greenColor] : [UIColor redColor]) forState:UIControlStateNormal];
    power.titleLabel.font = [UIFont systemFontOfSize:16];
    power.tag = 200;
    power.showsTouchWhenHighlighted = YES;
    [power addTarget:self action:@selector(targetPowerTap:) forControlEvents:UIControlEventTouchUpInside];
    [bg addSubview:power];

    // BACK button
    UIButton *back = SLMakeBtn(@"BACK", 90, 36, [UIColor colorWithWhite:0.2 alpha:1], [UIColor whiteColor], 14);
    back.frame = CGRectMake(pad + 44, btnY, 90, 36);
    back.showsTouchWhenHighlighted = YES;
    [back addTarget:self action:@selector(targetBack) forControlEvents:UIControlEventTouchUpInside];
    [bg addSubview:back];

    // SAVE button (green)
    UIButton *save = SLMakeBtn(@"SAVE", 90, 36, [UIColor colorWithRed:0 green:0.85 blue:0 alpha:1], [UIColor blackColor], 14);
    save.frame = CGRectMake(pw - pad - 90, btnY, 90, 36);
    save.showsTouchWhenHighlighted = YES;
    [save addTarget:self action:@selector(targetSave) forControlEvents:UIControlEventTouchUpInside];
    [bg addSubview:save];

    win.hidden = NO;
    sTargetWindow = win;
}

+ (void)targetInputTap {
    UIAlertController *a = [UIAlertController alertControllerWithTitle:@"Max Spins" message:@"Cut internet after this many spins" preferredStyle:UIAlertControllerStyleAlert];
    [a addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.keyboardType = UIKeyboardTypeNumberPad;
        if (sTargetMaxSpins > 0) tf.text = [NSString stringWithFormat:@"%ld", (long)sTargetMaxSpins];
    }];
    [a addAction:[UIAlertAction actionWithTitle:@"Set" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        sTargetMaxSpins = a.textFields.firstObject.text.integerValue;
        // Update button text
        UIButton *box = [sTargetWindow.rootViewController.view viewWithTag:999];
        [box setTitle:(sTargetMaxSpins > 0 ? [NSString stringWithFormat:@"%ld", (long)sTargetMaxSpins] : @"∞") forState:UIControlStateNormal];
    }]];
    [a addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [[self topVC] presentViewController:a animated:YES completion:nil];
}

+ (void)targetSymbolTap:(UIButton *)btn {
    NSArray *keys = @[@"attack", @"steal", @"spins", @"shield", @"accumulation", @"goldSack"];
    NSUInteger idx = btn.tag - 100;
    if (idx >= keys.count) return;

    sTargetSymbol = keys[idx];

    // Update borders — highlight selected, clear others
    for (NSUInteger i = 0; i < keys.count; i++) {
        UIButton *sb = [sTargetWindow.rootViewController.view viewWithTag:(100 + i)];
        if (i == idx) {
            sb.layer.borderColor = [UIColor colorWithRed:0 green:0.9 blue:0 alpha:1].CGColor;
            sb.backgroundColor = [UIColor colorWithRed:0 green:0.2 blue:0 alpha:1];
        } else {
            sb.layer.borderColor = [UIColor clearColor].CGColor;
            sb.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
        }
    }
}

+ (void)targetPowerTap:(UIButton *)btn {
    sTargetActive = !sTargetActive;
    [btn setTitleColor:(sTargetActive ? [UIColor greenColor] : [UIColor redColor]) forState:UIControlStateNormal];
    btn.layer.borderColor = (sTargetActive ? [UIColor greenColor] : [UIColor redColor]).CGColor;
}

+ (void)targetBack {
    sTargetWindow.hidden = YES;
}

+ (void)targetSave {
    if (sTargetSymbol && sTargetMaxSpins > 0) {
        [SLSpinTarget shared].targetSpinCount = sTargetMaxSpins;
        [SLTrisController shared].lockTarget = sTargetSymbol;
        NSLog(@"[SpinLogger] Target: %@ within %ld spins (active=%d)", sTargetSymbol, (long)sTargetMaxSpins, sTargetActive);
        sTargetWindow.hidden = YES;
    }
}

+ (void)networkToggle {
    sNetworkLocked = !sNetworkLocked;
    NSLog(@"[SpinLogger] Network %@", sNetworkLocked ? @"BLOCKED" : @"RESTORED");
}

+ (void)trisMonitor {
    [[SLTrisController shared] showTrisMonitor];
}

+ (void)syncUI {
    double v = SLSpeedControllerGetMultiplier();
    [sSpeedBadgeBtn setTitle:[NSString stringWithFormat:@"%.2fx", v] forState:UIControlStateNormal];
    sSlider.value = (float)v;
}

+ (UIViewController *)topVC {
    UIWindowScene *s = nil;
    for (UIScene *sc in UIApplication.sharedApplication.connectedScenes)
        if ([sc isKindOfClass:[UIWindowScene class]] && sc.activationState == UISceneActivationStateForegroundActive) { s = (UIWindowScene *)sc; break; }
    UIWindow *kw = nil;
    for (UIWindow *w in s.windows) if (w.isKeyWindow) { kw = w; break; }
    UIViewController *vc = kw.rootViewController;
    while (vc.presentedViewController) vc = vc.presentedViewController;
    return vc;
}

@end

#pragma mark - Panel drag

@interface SLPanelDragger : NSObject
+ (void)handlePan:(UIPanGestureRecognizer *)pan;
@end

@implementation SLPanelDragger
+ (void)handlePan:(UIPanGestureRecognizer *)pan {
    if (pan.state == UIGestureRecognizerStateBegan || pan.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [pan translationInView:pan.view];
        CGRect f = sPanelWindow.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        sPanelWindow.frame = f;
        [pan setTranslation:CGPointZero inView:pan.view];
    }
}
@end

#pragma mark - Build Panel UI

static void SLShowPanel(void) {
    sIconWindow.hidden = YES;

    if (sPanelWindow) {
        [SLActions syncUI];
        sPanelWindow.hidden = NO;
        return;
    }

    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes)
        if ([s isKindOfClass:[UIWindowScene class]]) { scene = (UIWindowScene *)s; break; }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat pw = MIN(screen.size.width * 0.62, 250);
    CGFloat ph = 155;
    CGFloat ix = sIconWindow ? sIconWindow.frame.origin.x : screen.size.width - 60;
    CGFloat iy = sIconWindow ? sIconWindow.frame.origin.y : screen.size.height / 2;
    CGFloat x = MIN(ix, screen.size.width - pw - 10);
    CGFloat y = MAX(40, MIN(iy - 20, screen.size.height - ph - 40));

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, y, pw, ph);
    win.windowLevel = UIWindowLevelAlert + 400;
    win.backgroundColor = [UIColor clearColor];

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    // Glassmorphism background
    UIVisualEffectView *blur = [[UIVisualEffectView alloc] initWithEffect:[UIBlurEffect effectWithStyle:UIBlurEffectStyleDark]];
    blur.frame = CGRectMake(0, 0, pw, ph);
    blur.layer.cornerRadius = 18;
    blur.clipsToBounds = YES;
    blur.alpha = 0.92;
    [vc.view addSubview:blur];

    // Drag gesture on the blur background
    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:[SLPanelDragger class] action:@selector(handlePan:)];
    [blur addGestureRecognizer:pan];
    blur.userInteractionEnabled = YES;

    UIView *content = blur.contentView;
    CGFloat pad = 10;

    // === ROW 1: Logo + Title + Speed Badge + Gear ===
    CGFloat r1y = 8;

    UILabel *logo = [[UILabel alloc] initWithFrame:CGRectMake(pad, r1y, 32, 32)];
    logo.text = @"✈";
    logo.font = [UIFont systemFontOfSize:16];
    logo.textAlignment = NSTextAlignmentCenter;
    logo.backgroundColor = SLBtnActive();
    logo.layer.cornerRadius = 10;
    logo.clipsToBounds = YES;
    [content addSubview:logo];

    UILabel *title = [[UILabel alloc] initWithFrame:CGRectMake(pad + 38, r1y, 130, 32)];
    NSMutableAttributedString *titleAttr = [[NSMutableAttributedString alloc]
        initWithString:@"SPEEDER " attributes:@{NSForegroundColorAttributeName: [UIColor whiteColor], NSFontAttributeName: [UIFont boldSystemFontOfSize:14]}];
    [titleAttr appendAttributedString:[[NSAttributedString alloc]
        initWithString:@"ELITE" attributes:@{NSForegroundColorAttributeName: SLAccent(), NSFontAttributeName: [UIFont boldSystemFontOfSize:14]}]];
    title.attributedText = titleAttr;
    [content addSubview:title];

    UIButton *speedBadge = [UIButton buttonWithType:UIButtonTypeCustom];
    speedBadge.frame = CGRectMake(pw - pad - 38 - 65, r1y + 2, 62, 28);
    speedBadge.backgroundColor = [UIColor colorWithRed:0 green:0.9 blue:1 alpha:0.1];
    speedBadge.layer.cornerRadius = 8;
    speedBadge.layer.borderWidth = 1.5;
    speedBadge.layer.borderColor = SLAccent().CGColor;
    speedBadge.titleLabel.font = [UIFont boldSystemFontOfSize:14];
    [speedBadge setTitleColor:SLAccent() forState:UIControlStateNormal];
    [speedBadge setTitle:[NSString stringWithFormat:@"%.2fx", SLSpeedControllerGetMultiplier()] forState:UIControlStateNormal];
    [speedBadge addTarget:[SLActions class] action:@selector(speedBadgeTap) forControlEvents:UIControlEventTouchUpInside];
    sSpeedBadgeBtn = speedBadge;
    [content addSubview:speedBadge];

    UIButton *gear = SLMakeBtn(@"⚙", 32, 32, [UIColor colorWithWhite:1 alpha:0.1], SLMuted(), 16);
    gear.frame = CGRectMake(pw - pad - 32, r1y, 32, 32);
    gear.layer.cornerRadius = 16;
    [gear addTarget:[SLActions class] action:@selector(gearTap) forControlEvents:UIControlEventTouchUpInside];
    [content addSubview:gear];

    // === ROW 2: Play - Slider + Close ===
    CGFloat r2y = r1y + 38;
    UIView *controlsBg = [[UIView alloc] initWithFrame:CGRectMake(pad - 2, r2y, pw - 2 * pad + 4, 40)];
    controlsBg.backgroundColor = [UIColor colorWithWhite:0 alpha:0.2];
    controlsBg.layer.cornerRadius = 12;
    [content addSubview:controlsBg];

    UIButton *playBtn = SLMakeBtn(@"▶", 38, 36, SLBtnActive(), [UIColor whiteColor], 17);
    playBtn.frame = CGRectMake(3, 2, 38, 36);
    [playBtn addTarget:[SLActions class] action:@selector(play) forControlEvents:UIControlEventTouchUpInside];
    [controlsBg addSubview:playBtn];

    UIButton *minusBtn = SLMakeBtn(@"−", 34, 34, SLBtnBg(), [UIColor whiteColor], 16);
    minusBtn.frame = CGRectMake(44, 3, 34, 34);
    [minusBtn addTarget:[SLActions class] action:@selector(minus) forControlEvents:UIControlEventTouchUpInside];
    [controlsBg addSubview:minusBtn];

    UISlider *slider = [[UISlider alloc] initWithFrame:CGRectMake(82, 5, controlsBg.frame.size.width - 82 - 78, 30)];
    slider.minimumValue = 1.0;
    slider.maximumValue = 50.0;
    slider.value = (float)SLSpeedControllerGetMultiplier();
    slider.minimumTrackTintColor = SLAccent();
    slider.maximumTrackTintColor = [UIColor colorWithWhite:1 alpha:0.12];
    [slider addTarget:[SLActions class] action:@selector(sliderChanged:) forControlEvents:UIControlEventValueChanged];
    sSlider = slider;
    [controlsBg addSubview:slider];

    UIButton *plusBtn = SLMakeBtn(@"+", 34, 34, SLBtnBg(), [UIColor whiteColor], 16);
    plusBtn.frame = CGRectMake(controlsBg.frame.size.width - 74, 3, 34, 34);
    [plusBtn addTarget:[SLActions class] action:@selector(plus) forControlEvents:UIControlEventTouchUpInside];
    [controlsBg addSubview:plusBtn];

    UIButton *closeBtn = SLMakeBtn(@"✕", 34, 34, SLBtnBg(), SLMuted(), 18);
    closeBtn.frame = CGRectMake(controlsBg.frame.size.width - 37, 3, 34, 34);
    [closeBtn addTarget:[SLActions class] action:@selector(collapse) forControlEvents:UIControlEventTouchUpInside];
    [controlsBg addSubview:closeBtn];

    // === ROW 3: Action buttons ===
    CGFloat r3y = r2y + 46;
    CGFloat abtnW = 42, abtnH = 36, agap = 5;
    NSArray *abtnDefs = @[
        @[@"↺", @"resetCounters", @YES],
        @[@"SKIP", @"", @NO],
        @[@"∞", @"targetSpin", @YES],
        @[@"📶", @"networkToggle", @YES],
        @[@"+", @"", @NO],
        @[@"+", @"", @NO],
    ];

    CGFloat ax = pad;
    for (NSArray *def in abtnDefs) {
        CGFloat w = [def[0] isEqualToString:@"SKIP"] ? 52 : abtnW;
        BOOL active = [def[2] boolValue];
        UIButton *abtn = SLMakeBtn(def[0], w, abtnH, active ? SLBtnActive() : SLBtnBg(),
                                    active ? [UIColor whiteColor] : SLMuted(),
                                    [def[0] isEqualToString:@"SKIP"] ? 12 : 14);
        abtn.frame = CGRectMake(ax, r3y, w, abtnH);
        if ([def[1] length] > 0) {
            [abtn addTarget:[SLActions class] action:NSSelectorFromString(def[1]) forControlEvents:UIControlEventTouchUpInside];
        }
        [content addSubview:abtn];
        ax += w + agap;
    }

    win.hidden = NO;
    sPanelWindow = win;
}

static void SLHidePanel(void) {
    sPanelWindow.hidden = YES;
    sIconWindow.hidden = NO;
}

#pragma mark - Icon button

@interface SLIconTarget : NSObject
+ (void)tapped;
+ (void)handleIconPan:(UIPanGestureRecognizer *)r;
@end

@implementation SLIconTarget
+ (void)tapped { SLShowPanel(); }
+ (void)handleIconPan:(UIPanGestureRecognizer *)r {
    if (r.state == UIGestureRecognizerStateBegan || r.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [r translationInView:r.view.superview];
        CGRect f = sIconWindow.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        sIconWindow.frame = f;
        [r setTranslation:CGPointZero inView:r.view.superview];
    }
}
@end

#pragma mark - Install

void SLMenuOverlayInstall(void) {
    if (sIconWindow) return;

    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes)
        if ([s isKindOfClass:[UIWindowScene class]] && s.activationState == UISceneActivationStateForegroundActive) { scene = (UIWindowScene *)s; break; }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat sz = 50;

    UIWindow *iconWin = [[UIWindow alloc] initWithWindowScene:scene];
    iconWin.frame = CGRectMake(screen.size.width - sz - 10, screen.size.height / 2 - sz / 2, sz, sz);
    iconWin.windowLevel = UIWindowLevelAlert + 400;
    iconWin.backgroundColor = [UIColor clearColor];

    UIViewController *iconVC = [[UIViewController alloc] init];
    iconVC.view.backgroundColor = [UIColor clearColor];
    iconWin.rootViewController = iconVC;

    UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
    btn.frame = CGRectMake(0, 0, sz, sz);
    btn.backgroundColor = SLAccent();
    btn.layer.cornerRadius = sz / 2;
    btn.clipsToBounds = YES;
    [btn setTitle:@"SL" forState:UIControlStateNormal];
    [btn setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    btn.titleLabel.font = [UIFont boldSystemFontOfSize:18];
    [btn addTarget:[SLIconTarget class] action:@selector(tapped) forControlEvents:UIControlEventTouchUpInside];

    UIPanGestureRecognizer *iconPan = [[UIPanGestureRecognizer alloc] initWithTarget:[SLIconTarget class] action:@selector(handleIconPan:)];
    [btn addGestureRecognizer:iconPan];
    [iconVC.view addSubview:btn];

    iconWin.hidden = NO;
    sIconWindow = iconWin;
}
