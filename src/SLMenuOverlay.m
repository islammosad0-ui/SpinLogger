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
static UILabel *sSpeedLabel = nil;
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

static UIButton *SLMakeBtn(NSString *title, CGFloat w, CGFloat h, UIColor *bg, UIColor *fg, CGFloat fontSize) {
    UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
    btn.frame = CGRectMake(0, 0, w, h);
    btn.backgroundColor = bg;
    btn.layer.cornerRadius = h > 38 ? 14 : 11;
    btn.clipsToBounds = YES;
    [btn setTitle:title forState:UIControlStateNormal];
    [btn setTitleColor:fg forState:UIControlStateNormal];
    btn.titleLabel.font = [UIFont boldSystemFontOfSize:fontSize];
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
    sSpeedLabel.text = [NSString stringWithFormat:@"%.2fx", v];
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

+ (void)gearTap {
    UIAlertController *sheet = [UIAlertController alertControllerWithTitle:@"SPEEDER Settings" message:nil preferredStyle:UIAlertControllerStyleActionSheet];

    [sheet addAction:[UIAlertAction actionWithTitle:@"Tris Monitor" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        [[SLTrisController shared] showTrisMonitor];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Share CSV" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        NSURL *url = [NSURL fileURLWithPath:SLSpinStoreCSVPath()];
        UIActivityViewController *avc = [[UIActivityViewController alloc] initWithActivityItems:@[url] applicationActivities:nil];
        UIViewController *p = [self topVC];
        avc.popoverPresentationController.sourceView = p.view;
        [p presentViewController:avc animated:YES completion:nil];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Toggle Counters" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) {
        [[NSNotificationCenter defaultCenter] postNotificationName:@"SLToggleCounters" object:nil];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Save Preset 1" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) { [[SLPresetManager shared] savePreset:1]; }]];
    [sheet addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Load P1 (%@)", [[SLPresetManager shared] presetSummary:1]] style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) { [[SLPresetManager shared] loadPreset:1]; [self syncUI]; }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Save Preset 2" style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) { [[SLPresetManager shared] savePreset:2]; }]];
    [sheet addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Load P2 (%@)", [[SLPresetManager shared] presetSummary:2]] style:UIAlertActionStyleDefault handler:^(UIAlertAction *_) { [[SLPresetManager shared] loadPreset:2]; [self syncUI]; }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];

    UIViewController *top = [self topVC];
    sheet.popoverPresentationController.sourceView = top.view;
    sheet.popoverPresentationController.sourceRect = CGRectMake(CGRectGetMidX(top.view.bounds), CGRectGetMidY(top.view.bounds), 0, 0);
    [top presentViewController:sheet animated:YES completion:nil];
}

+ (void)resetCounters { [[SLCounterOverlay shared] resetAllCounters]; }

+ (void)targetSpin {
    [[NSNotificationCenter defaultCenter] postNotificationName:@"SLShowTrisMonitor" object:nil];
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
    sSpeedLabel.text = [NSString stringWithFormat:@"%.2fx", v];
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
    sSpeedLabel = speedBadge.titleLabel;
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
