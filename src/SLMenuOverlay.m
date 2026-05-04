#import "SLMenuOverlay.h"
#import "SLConstants.h"
#import "SLSpinStore.h"
#import "SLBetDecisionLogger.h"
#import "SLAccountID.h"
#import "SLSpeedController.h"
#import "SLSpinTarget.h"
#import "SLTrisController.h"
#import "SLPresetManager.h"
#import "SLCounterOverlay.h"
#import "SLNetworkMonitor.h"
#import "SLDebtMonitor.h"
#import "SLSignalPanel.h"
#import "SLV4Panel.h"
#import <UIKit/UIKit.h>

// Panel-visibility NSUserDefaults keys (shared with SLV4Panel / SLSignalPanel).
static NSString *const kSLV4PanelVisibleKey  = @"SLV4Panel.visible";
static NSString *const kSLSigPanelVisibleKey = @"SLSignalPanel.visible";

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

static UIButton *sSpeedBadgeBtn = nil;
static UIButton *sRefreshBtn = nil;
static UIButton *sNetBtn = nil;
static UIButton *sPreset2Btn = nil;
static UIButton *sV4Btn = nil;
static UIButton *sSigBtn = nil;
static UIButton *sTrisBtn = nil;
static BOOL sCountersVisible = YES;

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
+ (void)networkToggle;
+ (void)trisMonitor;
+ (void)toggleV4Panel;
+ (void)toggleSignalPanel;
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
static UIView *sDebtContent = nil;
static UIButton *sTabTris = nil;
static UIButton *sTabCounter = nil;
static UIButton *sTabDebt = nil;
static BOOL sTrisMonitorActive = NO;
static BOOL sDebtMonitorActive = NO;
static UIWindow *sDebtTableWindow = nil;

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
    CGFloat pw = MIN(screen.size.width * 0.78, 300);
    CGFloat ph = 280;
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
    blur.layer.cornerRadius = 16;
    blur.clipsToBounds = YES;
    blur.alpha = 0.96;
    blur.userInteractionEnabled = YES;
    UIPanGestureRecognizer *settingsPan = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(dragSettings:)];
    [blur addGestureRecognizer:settingsPan];
    [vc.view addSubview:blur];
    UIView *content = blur.contentView;

    CGFloat pad = 12;

    // Tab bar — 3 tabs with shorter labels at font 9
    CGFloat tabW = (pw - pad * 2 - 36) / 3;
    sTabTris = SLMakeBtn(@"TRIS", tabW, 30, SLAccent(), [UIColor blackColor], 9);
    sTabTris.frame = CGRectMake(pad, 8, tabW, 30);
    [sTabTris addTarget:self action:@selector(switchToTrisTab) forControlEvents:UIControlEventTouchUpInside];
    [content addSubview:sTabTris];

    sTabCounter = SLMakeBtn(@"COUNTER", tabW, 30, SLBtnBg(), SLMuted(), 9);
    sTabCounter.frame = CGRectMake(pad + tabW + 4, 8, tabW, 30);
    [sTabCounter addTarget:self action:@selector(switchToCounterTab) forControlEvents:UIControlEventTouchUpInside];
    [content addSubview:sTabCounter];

    sTabDebt = SLMakeBtn(@"DEBT", tabW, 30, SLBtnBg(), SLMuted(), 9);
    sTabDebt.frame = CGRectMake(pad + 2 * (tabW + 4), 8, tabW, 30);
    [sTabDebt addTarget:self action:@selector(switchToDebtTab) forControlEvents:UIControlEventTouchUpInside];
    [content addSubview:sTabDebt];

    // Close X
    UIButton *closeBtn = SLMakeBtn(@"✕", 28, 30, [UIColor colorWithWhite:1 alpha:0.12], [UIColor whiteColor], 13);
    closeBtn.frame = CGRectMake(pw - pad - 28, 8, 28, 30);
    closeBtn.layer.cornerRadius = 14;
    [closeBtn addTarget:self action:@selector(settingsClose) forControlEvents:UIControlEventTouchUpInside];
    [content addSubview:closeBtn];

    // === TRIS MONITOR content ===
    sTrisContent = [[UIView alloc] initWithFrame:CGRectMake(0, 42, pw, ph - 42)];
    [content addSubview:sTrisContent];

    // ACTIVE MONITOR row
    UILabel *amLabel = [[UILabel alloc] initWithFrame:CGRectMake(pad, 6, 150, 22)];
    amLabel.text = @"ACTIVE MONITOR";
    amLabel.font = [UIFont boldSystemFontOfSize:12];
    amLabel.textColor = SLAccent();
    [sTrisContent addSubview:amLabel];

    UISwitch *amSwitch = [[UISwitch alloc] initWithFrame:CGRectMake(pw - pad - 51, 3, 51, 31)];
    amSwitch.onTintColor = SLAccent();
    amSwitch.transform = CGAffineTransformMakeScale(0.85, 0.85);
    amSwitch.on = sTrisMonitorActive;
    [amSwitch addTarget:self action:@selector(trisMonitorToggle:) forControlEvents:UIControlEventValueChanged];
    [sTrisContent addSubview:amSwitch];

    // LOCK TARGET row
    UILabel *ltLabel = [[UILabel alloc] initWithFrame:CGRectMake(pad, 32, 150, 22)];
    ltLabel.text = @"LOCK TARGET";
    ltLabel.font = [UIFont boldSystemFontOfSize:12];
    ltLabel.textColor = SLAccent();
    [sTrisContent addSubview:ltLabel];

    NSArray *syms = @[@"🔨", @"🐷", @"💊", @"🛡", @"⭐", @"🧪"];
    NSArray *keys = @[@"attack", @"steal", @"spins", @"shield", @"accumulation", @"potion"];
    CGFloat symSize = 36;
    CGFloat symGap = 4;
    CGFloat symStartX = pad;
    NSString *curLock = [SLTrisController shared].lockTarget;

    for (NSUInteger i = 0; i < syms.count; i++) {
        UIButton *sb = [UIButton buttonWithType:UIButtonTypeCustom];
        sb.frame = CGRectMake(symStartX + i * (symSize + symGap), 56, symSize, symSize);
        sb.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
        sb.layer.cornerRadius = 10;
        sb.layer.borderWidth = 2;
        sb.layer.borderColor = [curLock isEqualToString:keys[i]] ? SLAccent().CGColor : [UIColor clearColor].CGColor;
        [sb setTitle:syms[i] forState:UIControlStateNormal];
        sb.titleLabel.font = [UIFont systemFontOfSize:18];
        sb.tag = 300 + i;
        sb.showsTouchWhenHighlighted = YES;
        [sb addTarget:self action:@selector(lockTargetTap:) forControlEvents:UIControlEventTouchUpInside];
        [sTrisContent addSubview:sb];
    }

    // SHOW COLUMNS row — toggle which columns appear in the Tris Monitor (7 columns incl. VT)
    UILabel *scColLabel = [[UILabel alloc] initWithFrame:CGRectMake(pad, 100, 150, 22)];
    scColLabel.text = @"SHOW COLUMNS";
    scColLabel.font = [UIFont boldSystemFontOfSize:12];
    scColLabel.textColor = SLAccent();
    [sTrisContent addSubview:scColLabel];

    NSArray *colSyms = @[@"🔨", @"🐷", @"💊", @"🛡", @"⭐", @"🧪", @"🎯"];
    NSUInteger colBits[7] = {kSLTrisColAttack, kSLTrisColSteal, kSLTrisColSpins,
                              kSLTrisColShield, kSLTrisColAccum, kSLTrisColPotion, kSLTrisColVT};
    CGFloat colSymSize = 32;
    CGFloat colSymGap  = 3;
    NSUInteger visCols = [SLTrisController shared].visibleColumns;
    for (NSUInteger i = 0; i < colSyms.count; i++) {
        UIButton *cb = [UIButton buttonWithType:UIButtonTypeCustom];
        cb.frame = CGRectMake(symStartX + i * (colSymSize + colSymGap), 124, colSymSize, colSymSize);
        cb.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
        cb.layer.cornerRadius = 9;
        cb.layer.borderWidth = 2;
        BOOL visible = (visCols & colBits[i]) != 0;
        cb.layer.borderColor = visible ? SLAccent().CGColor : [UIColor clearColor].CGColor;
        cb.alpha = visible ? 1.0 : 0.35;
        [cb setTitle:colSyms[i] forState:UIControlStateNormal];
        cb.titleLabel.font = [UIFont systemFontOfSize:16];
        cb.tag = 500 + i;  // 500-506 for column toggles
        cb.showsTouchWhenHighlighted = YES;
        [cb addTarget:self action:@selector(columnVisibilityTap:) forControlEvents:UIControlEventTouchUpInside];
        [sTrisContent addSubview:cb];
    }

    // === SPIN COUNTER content (hidden by default) ===
    sCounterContent = [[UIView alloc] initWithFrame:CGRectMake(0, 42, pw, ph - 42)];
    sCounterContent.hidden = YES;
    [content addSubview:sCounterContent];

    UILabel *scLabel = [[UILabel alloc] initWithFrame:CGRectMake(pad, 8, 200, 22)];
    scLabel.text = @"SHOW / HIDE COUNTERS";
    scLabel.font = [UIFont boldSystemFontOfSize:12];
    scLabel.textColor = SLAccent();
    [sCounterContent addSubview:scLabel];

    NSArray *counterSyms = @[@"🔨", @"🐷", @"💊", @"🛡", @"⭐", @"🧪", @"🔢"];
    NSArray *counterKeys = @[@"attack", @"steal", @"spins", @"shield", @"accumulation", @"potion", @"spinCount"];
    CGFloat counterSymSize = 32;
    CGFloat counterSymGap  = 3;
    for (NSUInteger i = 0; i < counterSyms.count; i++) {
        UIButton *sb = [UIButton buttonWithType:UIButtonTypeCustom];
        sb.frame = CGRectMake(symStartX + i * (counterSymSize + counterSymGap), 36, counterSymSize, counterSymSize);
        sb.backgroundColor = [UIColor colorWithWhite:0.15 alpha:1];
        sb.layer.cornerRadius = 9;
        sb.layer.borderWidth = 2;
        BOOL symVis = [[SLCounterOverlay shared] isSymbolVisible:counterKeys[i]];
        sb.layer.borderColor = symVis ? SLAccent().CGColor : [UIColor clearColor].CGColor;
        sb.alpha = symVis ? 1.0 : 0.4;
        [sb setTitle:counterSyms[i] forState:UIControlStateNormal];
        sb.titleLabel.font = [UIFont systemFontOfSize:16];
        sb.tag = 400 + i;
        sb.showsTouchWhenHighlighted = YES;
        [sb addTarget:self action:@selector(counterVisibilityTap:) forControlEvents:UIControlEventTouchUpInside];
        [sCounterContent addSubview:sb];
    }

    // Spin counter target — 🔢 tile auto-resets when reaching this number, double-tap to reset manually
    NSString *targetTitle = [NSString stringWithFormat:@"🔢 SPIN TILE TARGET: %ld",
                             (long)[[SLCounterOverlay shared] spinTileTargetValue]];
    UIButton *targetBtn = SLMakeBtn(targetTitle, pw - pad * 2, 30,
        [UIColor colorWithWhite:0.15 alpha:1], SLAccent(), 11);
    targetBtn.frame = CGRectMake(pad, 76, pw - pad * 2, 30);
    targetBtn.tag = 411;
    [targetBtn addTarget:self action:@selector(spinTileTargetTap) forControlEvents:UIControlEventTouchUpInside];
    [sCounterContent addSubview:targetBtn];

    // Reset positions button
    UIButton *resetPosBtn = SLMakeBtn(@"RESET POSITIONS", pw - pad * 2, 30,
        [UIColor colorWithWhite:0.15 alpha:1], SLAccent(), 11);
    resetPosBtn.frame = CGRectMake(pad, 114, pw - pad * 2, 30);
    [resetPosBtn addTarget:self action:@selector(counterResetPositions) forControlEvents:UIControlEventTouchUpInside];
    [sCounterContent addSubview:resetPosBtn];

    // Account name button — tags log files (spin_history & bet_decisions) per account
    NSString *curAcct = SLAccountLabel();
    NSString *acctTitle = [NSString stringWithFormat:@"ACCOUNT: %@", curAcct];
    UIButton *acctBtn = SLMakeBtn(acctTitle, pw - pad * 2, 30,
        [UIColor colorWithWhite:0.15 alpha:1], SLAccent(), 11);
    acctBtn.frame = CGRectMake(pad, 152, pw - pad * 2, 30);
    acctBtn.tag = 410;
    [acctBtn addTarget:self action:@selector(accountNameTap) forControlEvents:UIControlEventTouchUpInside];
    [sCounterContent addSubview:acctBtn];

    // === DEBT TRACKER content (hidden by default) ===
    sDebtContent = [[UIView alloc] initWithFrame:CGRectMake(0, 42, pw, ph - 42)];
    sDebtContent.hidden = YES;
    [content addSubview:sDebtContent];

    CGFloat rowH = 28, rowY = 4;

    // Row 1: SHOW / HIDE tiles
    UILabel *showLabel = [[UILabel alloc] initWithFrame:CGRectMake(pad, rowY + 4, 180, 20)];
    showLabel.text = @"SHOW / HIDE TILES";
    showLabel.font = [UIFont boldSystemFontOfSize:12];
    showLabel.textColor = SLAccent();
    [sDebtContent addSubview:showLabel];

    UISwitch *showSwitch = [[UISwitch alloc] init];
    showSwitch.onTintColor = SLAccent();
    showSwitch.transform = CGAffineTransformMakeScale(0.78, 0.78);
    showSwitch.on = YES;
    showSwitch.frame = CGRectMake(pw - pad - 51, rowY, 51, 28);
    showSwitch.tag = 500;
    [showSwitch addTarget:self action:@selector(debtShowToggle:) forControlEvents:UIControlEventValueChanged];
    [sDebtContent addSubview:showSwitch];
    rowY += rowH + 4;

    // Row 2: ACTIVE MONITOR (live stats table)
    UILabel *monLabel = [[UILabel alloc] initWithFrame:CGRectMake(pad, rowY + 4, 180, 20)];
    monLabel.text = @"ACTIVE MONITOR";
    monLabel.font = [UIFont boldSystemFontOfSize:12];
    monLabel.textColor = SLAccent();
    [sDebtContent addSubview:monLabel];

    UISwitch *monSwitch = [[UISwitch alloc] init];
    monSwitch.onTintColor = SLAccent();
    monSwitch.transform = CGAffineTransformMakeScale(0.78, 0.78);
    monSwitch.on = sDebtMonitorActive;
    monSwitch.frame = CGRectMake(pw - pad - 51, rowY, 51, 28);
    monSwitch.tag = 502;
    [monSwitch addTarget:self action:@selector(debtMonitorToggle:) forControlEvents:UIControlEventValueChanged];
    [sDebtContent addSubview:monSwitch];
    rowY += rowH + 8;

    // Divider
    UIView *div = [[UIView alloc] initWithFrame:CGRectMake(pad, rowY, pw - pad * 2, 1)];
    div.backgroundColor = [UIColor colorWithWhite:1 alpha:0.08];
    [sDebtContent addSubview:div];
    rowY += 6;

    // Row 4: Reset buttons
    CGFloat btnW = (pw - pad * 2 - 8) / 2;
    UIButton *resetAcc = SLMakeBtn(@"RESET ⭐", btnW, 32, [UIColor colorWithRed:0.7 green:0.1 blue:0.1 alpha:0.7], [UIColor whiteColor], 11);
    resetAcc.frame = CGRectMake(pad, rowY, btnW, 32);
    [resetAcc addTarget:self action:@selector(debtResetAcc) forControlEvents:UIControlEventTouchUpInside];
    [sDebtContent addSubview:resetAcc];

    UIButton *resetSpn = SLMakeBtn(@"RESET 💊", btnW, 32, [UIColor colorWithRed:0.7 green:0.1 blue:0.1 alpha:0.7], [UIColor whiteColor], 11);
    resetSpn.frame = CGRectMake(pad + btnW + 8, rowY, btnW, 32);
    [resetSpn addTarget:self action:@selector(debtResetSpn) forControlEvents:UIControlEventTouchUpInside];
    [sDebtContent addSubview:resetSpn];

    win.hidden = NO;
    sSettingsWindow = win;
}

+ (void)switchToTrisTab {
    sTabTris.backgroundColor    = SLAccent();  [sTabTris    setTitleColor:[UIColor blackColor] forState:UIControlStateNormal];
    sTabCounter.backgroundColor = SLBtnBg();   [sTabCounter setTitleColor:SLMuted()            forState:UIControlStateNormal];
    sTabDebt.backgroundColor    = SLBtnBg();   [sTabDebt    setTitleColor:SLMuted()            forState:UIControlStateNormal];
    sTrisContent.hidden = NO; sCounterContent.hidden = YES; sDebtContent.hidden = YES;
}

+ (void)switchToCounterTab {
    sTabCounter.backgroundColor = SLAccent();  [sTabCounter setTitleColor:[UIColor blackColor] forState:UIControlStateNormal];
    sTabTris.backgroundColor    = SLBtnBg();   [sTabTris    setTitleColor:SLMuted()            forState:UIControlStateNormal];
    sTabDebt.backgroundColor    = SLBtnBg();   [sTabDebt    setTitleColor:SLMuted()            forState:UIControlStateNormal];
    sCounterContent.hidden = NO; sTrisContent.hidden = YES; sDebtContent.hidden = YES;
}

+ (void)switchToDebtTab {
    sTabDebt.backgroundColor    = SLAccent();  [sTabDebt    setTitleColor:[UIColor blackColor] forState:UIControlStateNormal];
    sTabTris.backgroundColor    = SLBtnBg();   [sTabTris    setTitleColor:SLMuted()            forState:UIControlStateNormal];
    sTabCounter.backgroundColor = SLBtnBg();   [sTabCounter setTitleColor:SLMuted()            forState:UIControlStateNormal];
    sDebtContent.hidden = NO; sTrisContent.hidden = YES; sCounterContent.hidden = YES;
}

// ── Debt tab actions ──────────────────────────────────────────────────────────

+ (void)debtShowToggle:(UISwitch *)sw {
    if (sw.on) [[SLDebtMonitor shared] show];
    else       [[SLDebtMonitor shared] hide];
}

// Lock target removed — formula uses fixed spinThreshold + rateGate

+ (void)debtMonitorToggle:(UISwitch *)sw {
    sDebtMonitorActive = sw.on;
    if (sw.on) [self showDebtTableWindow];
    else {
        sDebtTableWindow.hidden = YES;
    }
}

+ (void)debtResetAcc {
    [[SLDebtMonitor shared] resetAccTracker];
}

+ (void)debtResetSpn {
    [[SLDebtMonitor shared] resetSpnTracker];
}

// ── Debt gap-history table window ─────────────────────────────────────────────

+ (void)showDebtTableWindow {
    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes)
        if ([s isKindOfClass:[UIWindowScene class]]) { scene = (UIWindowScene *)s; break; }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat pw = MIN(screen.size.width * 0.82, 310);
    CGFloat ph = 360;
    CGFloat x  = (screen.size.width - pw) / 2;
    CGFloat y  = MAX(60, (screen.size.height - ph) / 2);

    if (!sDebtTableWindow) {
        UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
        win.frame = CGRectMake(x, y, pw, ph);
        win.windowLevel = UIWindowLevelAlert + 460;
        win.backgroundColor = [UIColor clearColor];
        UIViewController *vc = [[UIViewController alloc] init];
        vc.view.backgroundColor = [UIColor clearColor];
        win.rootViewController = vc;

        UIVisualEffectView *blur = [[UIVisualEffectView alloc] initWithEffect:[UIBlurEffect effectWithStyle:UIBlurEffectStyleDark]];
        blur.frame = CGRectMake(0, 0, pw, ph);
        blur.layer.cornerRadius = 16;
        blur.clipsToBounds = YES;
        blur.alpha = 0.97;
        blur.userInteractionEnabled = YES;
        UIPanGestureRecognizer *dpan = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(dragDebtTable:)];
        [blur addGestureRecognizer:dpan];
        [vc.view addSubview:blur];

        // Title bar
        UILabel *title = [[UILabel alloc] initWithFrame:CGRectMake(12, 8, pw - 56, 22)];
        title.text = @"LIVE TRACKER";
        title.font = [UIFont boldSystemFontOfSize:13];
        title.textColor = SLAccent();
        [blur.contentView addSubview:title];

        UIButton *closeX = SLMakeBtn(@"✕", 28, 24, [UIColor colorWithWhite:1 alpha:0.12], [UIColor whiteColor], 12);
        closeX.frame = CGRectMake(pw - 36, 6, 28, 24);
        closeX.layer.cornerRadius = 12;
        [closeX addTarget:self action:@selector(closeDebtTable) forControlEvents:UIControlEventTouchUpInside];
        [blur.contentView addSubview:closeX];

        // Divider
        UIView *hdiv = [[UIView alloc] initWithFrame:CGRectMake(0, 34, pw, 1)];
        hdiv.backgroundColor = [UIColor colorWithWhite:1 alpha:0.1];
        [blur.contentView addSubview:hdiv];

        // Scroll view (tag 600 for easy lookup)
        UIScrollView *sv = [[UIScrollView alloc] initWithFrame:CGRectMake(0, 36, pw, ph - 36)];
        sv.tag = 600;
        sv.showsVerticalScrollIndicator = YES;
        sv.backgroundColor = [UIColor clearColor];
        [blur.contentView addSubview:sv];

        sDebtTableWindow = win;

        // Refresh table on every spin
        [[NSNotificationCenter defaultCenter] addObserverForName:@"SLDebtSpinDidProcess"
                                                          object:nil
                                                           queue:[NSOperationQueue mainQueue]
                                                      usingBlock:^(NSNotification *_) {
            [SLActions refreshDebtTable];
        }];
    }

    sDebtTableWindow.hidden = NO;
    [self refreshDebtTable];
}

+ (void)refreshDebtTable {
    if (!sDebtTableWindow || sDebtTableWindow.hidden) return;
    UIVisualEffectView *blur = (UIVisualEffectView *)[sDebtTableWindow.rootViewController.view.subviews firstObject];
    UIScrollView *sv = (UIScrollView *)[blur.contentView viewWithTag:600];
    if (!sv) return;

    for (UIView *v in sv.subviews) [v removeFromSuperview];

    CGFloat pw = sDebtTableWindow.bounds.size.width;
    CGFloat pad = 10;
    CGFloat y = 4;

    SLDebtMonitor *dm = [SLDebtMonitor shared];
    SLDebtTracker *trackers[2] = { dm.accTracker, dm.spnTracker };
    NSString *headers[2]       = { @"\u2B50 ACC", @"\U0001F48A SPN" };

    for (int t = 0; t < 2; t++) {
        SLDebtTracker *tr = trackers[t];

        // Section header
        UILabel *sh = [[UILabel alloc] initWithFrame:CGRectMake(pad, y, pw - pad * 2, 18)];
        sh.font = [UIFont boldSystemFontOfSize:11];
        sh.textColor = SLAccent();
        NSString *phaseStr;
        switch (tr.phase) {
            case SLDebtPhaseBetNow: phaseStr = [NSString stringWithFormat:@"BET (%ld/%lu)",
                                                  (long)tr.firingRuleCount, (unsigned long)tr.config.rules.count]; break;
            case SLDebtPhaseSoon:   phaseStr = @"SOON"; break;
            case SLDebtPhaseWatch:  phaseStr = @"ALERT"; break;
            case SLDebtPhaseRest:   phaseStr = [NSString stringWithFormat:@"REST %ld", (long)tr.cooldownRemaining]; break;
            case SLDebtPhaseWaiting:
            default:                phaseStr = @"WAIT"; break;
        }
        sh.text = [NSString stringWithFormat:@"%@  %@", headers[t], phaseStr];
        [sv addSubview:sh];
        y += 20;

        // Spin progress vs MIN effective threshold across all rules
        NSInteger minThresh = [tr minEffectiveThreshold];
        if (minThresh <= 0) minThresh = 110;
        NSInteger pct = (tr.saSpins * 100 / minThresh);
        UILabel *spinRow = [[UILabel alloc] initWithFrame:CGRectMake(pad, y, pw - pad * 2, 14)];
        spinRow.font = [UIFont monospacedSystemFontOfSize:10 weight:UIFontWeightMedium];
        spinRow.text = [NSString stringWithFormat:@"Spins: %ld / %ld  (%ld%%)",
                        (long)tr.saSpins, (long)minThresh, (long)pct];
        spinRow.textColor = (tr.saSpins >= minThresh)
            ? [UIColor colorWithRed:0.3 green:0.9 blue:0.4 alpha:1.0]
            : [UIColor colorWithWhite:0.6 alpha:1.0];
        [sv addSubview:spinRow];
        y += 16;

        // Acc rate (and spn rate if any rule uses spn gate)
        double accRate = [tr accumRate];
        double spnRate = [tr spnRate];
        BOOL anyRuleUsesSpn = NO;
        for (SLDebtRule *r in tr.config.rules) {
            if (r.spnRateGate > 0.0) { anyRuleUsesSpn = YES; break; }
        }
        UILabel *rateRow = [[UILabel alloc] initWithFrame:CGRectMake(pad, y, pw - pad * 2, 14)];
        rateRow.font = [UIFont monospacedSystemFontOfSize:10 weight:UIFontWeightMedium];
        if (anyRuleUsesSpn) {
            rateRow.text = [NSString stringWithFormat:@"acc: %.3f  spn: %.3f", accRate, spnRate];
        } else {
            rateRow.text = [NSString stringWithFormat:@"Rate:  %.3f", accRate];
        }
        // Color green if any rule's primary rate gate is satisfied
        BOOL rateHot = NO;
        for (SLDebtRule *r in tr.config.rules) {
            if (r.rateGate > 0.0 && accRate >= r.rateGate) { rateHot = YES; break; }
        }
        rateRow.textColor = rateHot
            ? [UIColor colorWithRed:0.3 green:0.9 blue:0.4 alpha:1.0]
            : [UIColor colorWithWhite:0.6 alpha:1.0];
        [sv addSubview:rateRow];
        y += 16;

        // Symbols counted + slope info
        UILabel *symRow = [[UILabel alloc] initWithFrame:CGRectMake(pad, y, pw - pad * 2, 14)];
        symRow.font = [UIFont monospacedSystemFontOfSize:9 weight:UIFontWeightRegular];
        symRow.textColor = [UIColor colorWithWhite:0.4 alpha:1.0];
        symRow.text = [NSString stringWithFormat:@"sym: %ld in %ld  slp10: %+.4f  prev: %ld",
                       (long)tr.saSymbols, (long)tr.saSpins,
                       [tr slopeForWindow:10], (long)tr.prevGapLength];
        [sv addSubview:symRow];
        y += 18;

        y += 8; // spacing between sections
    }

    sv.contentSize = CGSizeMake(pw, y + 8);
}

+ (void)closeDebtTable {
    sDebtTableWindow.hidden = YES;
    sDebtMonitorActive = NO;
    // Turn off the monitor switch in settings if it's visible
    UIVisualEffectView *blur = (UIVisualEffectView *)
        [sSettingsWindow.rootViewController.view.subviews firstObject];
    UISwitch *sw = (UISwitch *)[blur.contentView viewWithTag:502];
    sw.on = NO;
}

+ (void)dragDebtTable:(UIPanGestureRecognizer *)pan {
    if (pan.state == UIGestureRecognizerStateBegan || pan.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [pan translationInView:pan.view];
        CGRect f = sDebtTableWindow.frame;
        f.origin.x += t.x; f.origin.y += t.y;
        sDebtTableWindow.frame = f;
        [pan setTranslation:CGPointZero inView:pan.view];
    }
}

+ (void)settingsClose {
    sSettingsWindow.hidden = YES;
}

+ (void)dragSettings:(UIPanGestureRecognizer *)pan {
    if (pan.state == UIGestureRecognizerStateBegan || pan.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [pan translationInView:pan.view];
        CGRect f = sSettingsWindow.frame;
        f.origin.x += t.x; f.origin.y += t.y;
        sSettingsWindow.frame = f;
        [pan setTranslation:CGPointZero inView:pan.view];
    }
}

+ (void)trisMonitorToggle:(UISwitch *)sw {
    sTrisMonitorActive = sw.on;
    if (sw.on) [[SLTrisController shared] showTrisMonitor];
    else [[SLTrisController shared] hideTrisMonitor];
}

+ (void)lockTargetTap:(UIButton *)btn {
    NSArray *keys = @[@"attack", @"steal", @"spins", @"shield", @"accumulation", @"potion"];
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
    NSArray *keys = @[@"attack", @"steal", @"spins", @"shield", @"accumulation", @"potion", @"spinCount"];
    NSUInteger idx = btn.tag - 400;
    if (idx >= keys.count) return;

    // Toggle border (visible = cyan border, hidden = no border)
    BOOL isActive = (btn.layer.borderColor != [UIColor clearColor].CGColor);
    btn.layer.borderColor = isActive ? [UIColor clearColor].CGColor : SLAccent().CGColor;
    btn.alpha = isActive ? 0.4 : 1.0;

    [[NSNotificationCenter defaultCenter] postNotificationName:@"SLToggleCounterSymbol" object:nil
                                                      userInfo:@{@"symbol": keys[idx]}];
}

+ (void)spinTileTargetTap {
    UIAlertController *a = [UIAlertController
        alertControllerWithTitle:@"🔢 Spin Tile Target"
                         message:@"Counter resets when it reaches this number.\nDouble-tap the tile to reset manually."
                  preferredStyle:UIAlertControllerStyleAlert];
    [a addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.keyboardType = UIKeyboardTypeNumberPad;
        tf.text = [@([[SLCounterOverlay shared] spinTileTargetValue]) stringValue];
    }];
    [a addAction:[UIAlertAction actionWithTitle:@"Set" style:UIAlertActionStyleDefault
        handler:^(UIAlertAction *_) {
            NSInteger n = [a.textFields.firstObject.text integerValue];
            if (n <= 0) return;
            [[SLCounterOverlay shared] setSpinTileTargetValue:n];
            UIButton *btn = (UIButton *)[sCounterContent viewWithTag:411];
            [btn setTitle:[NSString stringWithFormat:@"🔢 SPIN TILE TARGET: %ld", (long)n]
                 forState:UIControlStateNormal];
        }]];
    [a addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [[self topVC] presentViewController:a animated:YES completion:nil];
}

+ (void)columnVisibilityTap:(UIButton *)btn {
    NSUInteger idx = btn.tag - 500;
    if (idx >= 7) return;
    NSUInteger colBits[7] = {kSLTrisColAttack, kSLTrisColSteal, kSLTrisColSpins,
                              kSLTrisColShield, kSLTrisColAccum, kSLTrisColPotion, kSLTrisColVT};
    [[SLTrisController shared] toggleColumn:colBits[idx]];

    // Update all column toggle button visuals
    NSUInteger visCols = [SLTrisController shared].visibleColumns;
    for (NSUInteger i = 0; i < 7; i++) {
        UIButton *cb = (UIButton *)[sSettingsWindow.rootViewController.view viewWithTag:(500 + i)];
        if (!cb) continue;
        BOOL visible = (visCols & colBits[i]) != 0;
        cb.layer.borderColor = visible ? SLAccent().CGColor : [UIColor clearColor].CGColor;
        cb.alpha = visible ? 1.0 : 0.35;
    }
}

+ (void)resetCounters {
    sCountersVisible = !sCountersVisible;
    [[NSNotificationCenter defaultCenter] postNotificationName:@"SLToggleCounters" object:nil];
    sRefreshBtn.backgroundColor = sCountersVisible ? SLBtnActive() : SLBtnBg();
    [sRefreshBtn setTitleColor:sCountersVisible ? [UIColor whiteColor] : SLMuted() forState:UIControlStateNormal];
}

+ (void)counterResetPositions {
    [[SLCounterOverlay shared] resetPositions];
}

+ (void)accountNameTap {
    UIAlertController *a = [UIAlertController
        alertControllerWithTitle:@"Account Name"
                         message:@"Tags log filenames per account.\nLetters, digits, underscores only.\nMax 32 chars."
                  preferredStyle:UIAlertControllerStyleAlert];
    [a addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"e.g. islam, ahmed, nick";
        tf.text = SLAccountLabel();
        tf.autocapitalizationType = UITextAutocapitalizationTypeNone;
        tf.autocorrectionType = UITextAutocorrectionTypeNo;
    }];
    [a addAction:[UIAlertAction actionWithTitle:@"Save" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        NSString *raw = a.textFields.firstObject.text ?: @"";
        SLSetAccountLabel(raw);
        SLSpinStoreInvalidateHeader();
        SLBetDecisionLoggerInvalidateHeader();

        // Refresh the button title with the sanitized label
        UIButton *btn = (UIButton *)[sCounterContent viewWithTag:410];
        [btn setTitle:[NSString stringWithFormat:@"ACCOUNT: %@", SLAccountLabel()]
             forState:UIControlStateNormal];

        NSLog(@"[SpinLogger] Account label set to '%@' — next CSV writes use the new filename", SLAccountLabel());
    }]];
    [a addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [[self topVC] presentViewController:a animated:YES completion:nil];
}

+ (void)networkToggle {
    sNetworkLocked = !sNetworkLocked;
    sNetBtn.backgroundColor = sNetworkLocked ? SLBtnBg() : SLBtnActive();
    [sNetBtn setTitleColor:sNetworkLocked ? SLMuted() : [UIColor whiteColor] forState:UIControlStateNormal];
    NSLog(@"[SpinLogger] Network %@", sNetworkLocked ? @"BLOCKED" : @"RESTORED");
}

+ (void)trisMonitor {
    [[SLTrisController shared] showTrisMonitor];
    BOOL on = [[SLTrisController shared] isMonitorVisible];
    sTrisBtn.backgroundColor = on ? SLBtnActive() : SLBtnBg();
    [sTrisBtn setTitleColor:on ? [UIColor whiteColor] : SLMuted() forState:UIControlStateNormal];
}

+ (void)toggleV4Panel {
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    BOOL wasOn = [ud objectForKey:kSLV4PanelVisibleKey] ? [ud boolForKey:kSLV4PanelVisibleKey] : YES;
    BOOL on = !wasOn;
    if (on) [[SLV4Panel shared] show]; else [[SLV4Panel shared] hide];
    sV4Btn.backgroundColor = on ? SLBtnActive() : SLBtnBg();
    [sV4Btn setTitleColor:on ? [UIColor whiteColor] : SLMuted() forState:UIControlStateNormal];
}

+ (void)toggleSignalPanel {
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    BOOL wasOn = [ud objectForKey:kSLSigPanelVisibleKey] ? [ud boolForKey:kSLSigPanelVisibleKey] : YES;
    BOOL on = !wasOn;
    if (on) [[SLSignalPanel shared] show]; else [[SLSignalPanel shared] hide];
    sSigBtn.backgroundColor = on ? SLBtnActive() : SLBtnBg();
    [sSigBtn setTitleColor:on ? [UIColor whiteColor] : SLMuted() forState:UIControlStateNormal];
}

// Speed preset — tap to activate, long press to set
+ (void)preset2Tap {
    double v = [[NSUserDefaults standardUserDefaults] doubleForKey:@"Speeder_Preset2Speed"];
    if (v > 0) { SLSpeedControllerSetMultiplier(v); [self syncUI]; }
}
+ (void)preset2LongPress:(UILongPressGestureRecognizer *)lp {
    if (lp.state != UIGestureRecognizerStateBegan) return;
    [self setPreset:2 btn:sPreset2Btn key:@"Speeder_Preset2Speed"];
}
+ (void)setPreset:(int)num btn:(UIButton *)btn key:(NSString *)key {
    UIAlertController *a = [UIAlertController alertControllerWithTitle:[NSString stringWithFormat:@"Preset %d", num]
                                                               message:@"Enter speed value"
                                                        preferredStyle:UIAlertControllerStyleAlert];
    [a addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.keyboardType = UIKeyboardTypeDecimalPad;
        double cur = [[NSUserDefaults standardUserDefaults] doubleForKey:key];
        if (cur > 0) tf.text = [NSString stringWithFormat:@"%.0f", cur];
    }];
    [a addAction:[UIAlertAction actionWithTitle:@"Save" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        double v = a.textFields.firstObject.text.doubleValue;
        if (v >= 1.0) {
            [[NSUserDefaults standardUserDefaults] setDouble:v forKey:key];
            [btn setTitle:[NSString stringWithFormat:@"%.0fx", v] forState:UIControlStateNormal];
        }
    }]];
    [a addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [[self topVC] presentViewController:a animated:YES completion:nil];
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
    CGFloat pw = MIN(screen.size.width * 0.80, 300);
    CGFloat ph = 130;
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
    CGFloat r3y = r2y + 44;
    CGFloat abtnW = 40, abtnH = 34, agap = 4;
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    BOOL v4On   = [ud objectForKey:kSLV4PanelVisibleKey]  ? [ud boolForKey:kSLV4PanelVisibleKey]  : YES;
    BOOL sigOn  = [ud objectForKey:kSLSigPanelVisibleKey] ? [ud boolForKey:kSLSigPanelVisibleKey] : YES;
    BOOL trisOn = [[SLTrisController shared] isMonitorVisible];

    NSArray *abtnDefs = @[
        @[@"↺", @"resetCounters", @YES],
        @[@"TRIS", @"trisMonitor", @(trisOn)],
        @[@"V4",  @"toggleV4Panel",     @(v4On)],
        @[@"📶", @"networkToggle", @YES],
        @[@"SIG", @"toggleSignalPanel", @(sigOn)],
        @[@"preset2", @"preset2Tap", @NO],
    ];

    CGFloat ax = pad;
    for (NSArray *def in abtnDefs) {
        BOOL wideLbl = [def[0] isEqualToString:@"TRIS"] || [def[0] isEqualToString:@"preset2"];
        CGFloat w = wideLbl ? 48 : abtnW;
        BOOL active = [def[2] boolValue];
        UIButton *abtn = SLMakeBtn(def[0], w, abtnH, active ? SLBtnActive() : SLBtnBg(),
                                    active ? [UIColor whiteColor] : SLMuted(),
                                    wideLbl ? 11 : 14);
        abtn.frame = CGRectMake(ax, r3y, w, abtnH);
        if ([def[1] length] > 0) {
            [abtn addTarget:[SLActions class] action:NSSelectorFromString(def[1]) forControlEvents:UIControlEventTouchUpInside];
        }
        // Store refs for toggle buttons
        if ([def[0] isEqualToString:@"↺"])  sRefreshBtn = abtn;
        if ([def[0] isEqualToString:@"📶"]) sNetBtn = abtn;
        if ([def[0] isEqualToString:@"V4"])  sV4Btn  = abtn;
        if ([def[0] isEqualToString:@"SIG"]) sSigBtn = abtn;
        if ([def[0] isEqualToString:@"TRIS"]) sTrisBtn = abtn;
        if ([def[0] isEqualToString:@"preset2"]) {
            sPreset2Btn = abtn;
            double v = [ud doubleForKey:@"Speeder_Preset2Speed"];
            [abtn setTitle:(v > 0 ? [NSString stringWithFormat:@"%.0fx", v] : @"+") forState:UIControlStateNormal];
            UILongPressGestureRecognizer *lp = [[UILongPressGestureRecognizer alloc] initWithTarget:[SLActions class] action:@selector(preset2LongPress:)];
            lp.minimumPressDuration = 0.5;
            [abtn addGestureRecognizer:lp];
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
    CGFloat sz = 42;

    UIWindow *iconWin = [[UIWindow alloc] initWithWindowScene:scene];
    iconWin.frame = CGRectMake(screen.size.width - sz - 8, screen.size.height / 2 - sz / 2, sz, sz);
    iconWin.windowLevel = UIWindowLevelAlert + 400;
    iconWin.backgroundColor = [UIColor clearColor];

    UIViewController *iconVC = [[UIViewController alloc] init];
    iconVC.view.backgroundColor = [UIColor clearColor];
    iconWin.rootViewController = iconVC;

    UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
    btn.frame = CGRectMake(0, 0, sz, sz);
    btn.backgroundColor = [UIColor colorWithRed:0 green:0.75 blue:0.85 alpha:0.85];
    btn.layer.cornerRadius = sz / 2;
    btn.clipsToBounds = YES;
    [btn setTitle:@"SL" forState:UIControlStateNormal];
    [btn setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    btn.titleLabel.font = [UIFont boldSystemFontOfSize:15];
    [btn addTarget:[SLIconTarget class] action:@selector(tapped) forControlEvents:UIControlEventTouchUpInside];

    UIPanGestureRecognizer *iconPan = [[UIPanGestureRecognizer alloc] initWithTarget:[SLIconTarget class] action:@selector(handleIconPan:)];
    [btn addGestureRecognizer:iconPan];
    [iconVC.view addSubview:btn];

    iconWin.hidden = NO;
    sIconWindow = iconWin;
}
