#import "SLMenuOverlay.h"
#import "SLConstants.h"
#import "SLSpinStore.h"
#import "SLSpeedController.h"
#import "SLSpinTarget.h"
#import "SLTrisController.h"
#import "SLPresetManager.h"
#import "SLCounterOverlay.h"
#import "SLNetworkMonitor.h"
#import "SLNetworkStore.h"
#import <UIKit/UIKit.h>

// ---------------------------------------------------------------------------
//  Forward declarations
// ---------------------------------------------------------------------------
static UIViewController *SLTopVC(void);
static void SLShowSettingsMenu(void);

static UIWindow *sMenuWindow = nil;
static BOOL sCountersVisible = YES;

// ---------------------------------------------------------------------------
//  Menu button target
// ---------------------------------------------------------------------------
@interface SLMenuButtonTarget : NSObject
+ (void)tapped;
+ (void)handlePan:(UIPanGestureRecognizer *)recognizer;
@end

@implementation SLMenuButtonTarget

+ (void)tapped {
    SLShowSettingsMenu();
}

+ (void)handlePan:(UIPanGestureRecognizer *)recognizer {
    UIWindow *window = sMenuWindow;
    if (!window) return;
    if (recognizer.state == UIGestureRecognizerStateBegan ||
        recognizer.state == UIGestureRecognizerStateChanged) {
        CGPoint translation = [recognizer translationInView:recognizer.view.superview];
        CGRect frame = window.frame;
        frame.origin.x += translation.x;
        frame.origin.y += translation.y;
        window.frame = frame;
        [recognizer setTranslation:CGPointZero inView:recognizer.view.superview];
    }
}

@end

// ---------------------------------------------------------------------------
//  SLTopVC
// ---------------------------------------------------------------------------
static UIViewController *SLTopVC(void) {
    UIWindowScene *activeScene = nil;
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if ([scene isKindOfClass:[UIWindowScene class]] &&
            scene.activationState == UISceneActivationStateForegroundActive) {
            activeScene = (UIWindowScene *)scene;
            break;
        }
    }
    if (!activeScene) return nil;

    UIWindow *keyWindow = nil;
    for (UIWindow *w in activeScene.windows) {
        if (w.isKeyWindow) { keyWindow = w; break; }
    }
    if (!keyWindow) return nil;

    UIViewController *vc = keyWindow.rootViewController;
    while (vc.presentedViewController) vc = vc.presentedViewController;
    return vc;
}

// ---------------------------------------------------------------------------
//  Settings menu — enhanced with Network Monitor + cURL export
// ---------------------------------------------------------------------------
static void SLShowSettingsMenu(void) {
    UIViewController *top = SLTopVC();
    if (!top) return;

    NSString *message = [NSString stringWithFormat:
        @"Spins: %ld  |  Speed: %.1fx  |  Net Requests: %lu",
        (long)SLSpinStoreCount(),
        SLSpeedControllerGetMultiplier(),
        (unsigned long)[[SLNetworkStore shared] allRequests].count];

    UIAlertController *sheet =
        [UIAlertController alertControllerWithTitle:@"SPEEDER"
                                            message:message
                                     preferredStyle:UIAlertControllerStyleActionSheet];

    // ---- Share CSV ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"Share CSV"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        NSURL *fileURL = [NSURL fileURLWithPath:SLSpinStoreCSVPath()];
        UIActivityViewController *avc =
            [[UIActivityViewController alloc] initWithActivityItems:@[fileURL]
                                             applicationActivities:nil];
        UIViewController *presenter = SLTopVC();
        if (presenter) {
            avc.popoverPresentationController.sourceView = presenter.view;
            avc.popoverPresentationController.sourceRect =
                CGRectMake(CGRectGetMidX(presenter.view.bounds),
                           CGRectGetMidY(presenter.view.bounds), 0, 0);
            [presenter presentViewController:avc animated:YES completion:nil];
        }
    }]];

    // ---- Set Speed ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"Set Speed"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        UIAlertController *alert =
            [UIAlertController alertControllerWithTitle:@"Speed Multiplier"
                                               message:@"Enter value (1.0 - 50.0)"
                                        preferredStyle:UIAlertControllerStyleAlert];
        [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
            tf.keyboardType = UIKeyboardTypeDecimalPad;
            tf.text = [NSString stringWithFormat:@"%.1f", SLSpeedControllerGetMultiplier()];
        }];
        [alert addAction:[UIAlertAction actionWithTitle:@"Set"
                                                  style:UIAlertActionStyleDefault
                                                handler:^(UIAlertAction *_) {
            double mult = alert.textFields.firstObject.text.doubleValue;
            if (mult > 0) SLSpeedControllerSetMultiplier(mult);
        }]];
        [alert addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                                  style:UIAlertActionStyleCancel handler:nil]];
        UIViewController *p = SLTopVC();
        if (p) [p presentViewController:alert animated:YES completion:nil];
    }]];

    // ---- Set Spin Target ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"Set Spin Target"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        UIAlertController *alert =
            [UIAlertController alertControllerWithTitle:@"Spin Target"
                                               message:nil
                                        preferredStyle:UIAlertControllerStyleAlert];
        [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
            tf.keyboardType = UIKeyboardTypeNumberPad;
            tf.text = [NSString stringWithFormat:@"%ld",
                       (long)[SLSpinTarget shared].targetSpinCount];
        }];
        [alert addAction:[UIAlertAction actionWithTitle:@"Set"
                                                  style:UIAlertActionStyleDefault
                                                handler:^(UIAlertAction *_) {
            [SLSpinTarget shared].targetSpinCount = alert.textFields.firstObject.text.integerValue;
        }]];
        [alert addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                                  style:UIAlertActionStyleCancel handler:nil]];
        UIViewController *p = SLTopVC();
        if (p) [p presentViewController:alert animated:YES completion:nil];
    }]];

    // ---- Auto-Reset Mode ----
    {
        NSString *current = [SLSpinTarget shared].autoResetMode ?: @"none";
        NSString *title = [NSString stringWithFormat:@"Auto-Reset: %@", current];
        [sheet addAction:[UIAlertAction actionWithTitle:title
                                                  style:UIAlertActionStyleDefault
                                                handler:^(UIAlertAction *_) {
            UIAlertController *modeSheet =
                [UIAlertController alertControllerWithTitle:@"Auto-Reset Mode"
                                                   message:nil
                                            preferredStyle:UIAlertControllerStyleActionSheet];
            for (NSString *mode in @[@"none", @"symbol", @"global"]) {
                NSString *label = [mode isEqualToString:current] ?
                    [NSString stringWithFormat:@"> %@", mode] : mode;
                [modeSheet addAction:[UIAlertAction actionWithTitle:label
                                                              style:UIAlertActionStyleDefault
                                                            handler:^(UIAlertAction *_) {
                    [SLSpinTarget shared].autoResetMode = mode;
                }]];
            }
            [modeSheet addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                                          style:UIAlertActionStyleCancel handler:nil]];
            UIViewController *p = SLTopVC();
            if (p) {
                modeSheet.popoverPresentationController.sourceView = p.view;
                modeSheet.popoverPresentationController.sourceRect =
                    CGRectMake(CGRectGetMidX(p.view.bounds), CGRectGetMidY(p.view.bounds), 0, 0);
                [p presentViewController:modeSheet animated:YES completion:nil];
            }
        }]];
    }

    // ---- Network Monitor ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"Network Monitor"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        [[SLNetworkMonitor shared] show];
    }]];

    // ---- Export Last Request as cURL ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"Copy Last cURL"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        NSArray *reqs = [[SLNetworkStore shared] allRequests];
        if (reqs.count == 0) return;
        NSString *curl = [[SLNetworkStore shared] curlForRequest:reqs.lastObject];
        [UIPasteboard generalPasteboard].string = curl;
    }]];

    // ---- Toggle Counters ----
    [sheet addAction:[UIAlertAction actionWithTitle:sCountersVisible ? @"Hide Counters" : @"Show Counters"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        sCountersVisible = !sCountersVisible;
        sCountersVisible ? [[SLCounterOverlay shared] show] : [[SLCounterOverlay shared] hide];
    }]];

    // ---- Reset Counters ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"Reset Counters"
                                              style:UIAlertActionStyleDestructive
                                            handler:^(UIAlertAction *_) {
        [[SLCounterOverlay shared] resetAllCounters];
    }]];

    // ---- Presets ----
    NSString *p1 = [[SLPresetManager shared] presetSummary:1];
    [sheet addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Save Preset 1"]
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        [[SLPresetManager shared] savePreset:1];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Load P1 (%@)", p1]
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        [[SLPresetManager shared] loadPreset:1];
    }]];

    NSString *p2 = [[SLPresetManager shared] presetSummary:2];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Save Preset 2"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        [[SLPresetManager shared] savePreset:2];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:[NSString stringWithFormat:@"Load P2 (%@)", p2]
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        [[SLPresetManager shared] loadPreset:2];
    }]];

    // ---- Close ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"Close"
                                              style:UIAlertActionStyleCancel handler:nil]];

    sheet.popoverPresentationController.sourceView = top.view;
    sheet.popoverPresentationController.sourceRect =
        CGRectMake(CGRectGetMidX(top.view.bounds), CGRectGetMidY(top.view.bounds), 0, 0);

    [top presentViewController:sheet animated:YES completion:nil];
}

// ---------------------------------------------------------------------------
//  Install — floating button
// ---------------------------------------------------------------------------
void SLMenuOverlayInstall(void) {
    if (sMenuWindow) return;

    UIWindowScene *activeScene = nil;
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if ([scene isKindOfClass:[UIWindowScene class]] &&
            scene.activationState == UISceneActivationStateForegroundActive) {
            activeScene = (UIWindowScene *)scene;
            break;
        }
    }
    if (!activeScene) return;

    CGRect screenBounds = activeScene.coordinateSpace.bounds;
    CGFloat btnSize = 50.0;
    CGFloat x = screenBounds.size.width - btnSize - 8.0;
    CGFloat y = screenBounds.size.height / 2.0 - btnSize / 2.0;

    UIWindow *overlay = [[UIWindow alloc] initWithWindowScene:activeScene];
    overlay.frame = CGRectMake(x, y, btnSize, btnSize);
    overlay.windowLevel = UIWindowLevelAlert + 200;
    overlay.backgroundColor = [UIColor clearColor];
    overlay.clipsToBounds = YES;

    UIViewController *rootVC = [[UIViewController alloc] init];
    rootVC.view.backgroundColor = [UIColor clearColor];
    overlay.rootViewController = rootVC;

    UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
    btn.frame = CGRectMake(0, 0, btnSize, btnSize);
    btn.backgroundColor = [UIColor systemBlueColor];
    btn.layer.cornerRadius = btnSize / 2.0;
    btn.clipsToBounds = YES;
    [btn setTitle:@"SL" forState:UIControlStateNormal];
    [btn setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    btn.titleLabel.font = [UIFont boldSystemFontOfSize:16.0];

    [btn addTarget:[SLMenuButtonTarget class]
            action:@selector(tapped)
  forControlEvents:UIControlEventTouchUpInside];

    UIPanGestureRecognizer *pan =
        [[UIPanGestureRecognizer alloc] initWithTarget:[SLMenuButtonTarget class]
                                                action:@selector(handlePan:)];
    [btn addGestureRecognizer:pan];
    [rootVC.view addSubview:btn];

    overlay.hidden = NO;
    sMenuWindow = overlay;
}
