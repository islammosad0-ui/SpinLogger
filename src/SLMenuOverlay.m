#import "SLMenuOverlay.h"
#import "SLConstants.h"
#import "SLSpinStore.h"
#import "SLSpeedController.h"
#import "SLSpinTarget.h"
#import "SLTrisController.h"
#import "SLPresetManager.h"
#import "SLCounterOverlay.h"
#import <UIKit/UIKit.h>

// ---------------------------------------------------------------------------
//  Forward declarations
// ---------------------------------------------------------------------------
static UIViewController *SLTopVC(void);
static void SLShowSettingsMenu(void);

// ---------------------------------------------------------------------------
//  Static state
// ---------------------------------------------------------------------------
static UIWindow *sMenuWindow = nil;
static BOOL sCountersVisible = YES;

// ---------------------------------------------------------------------------
//  SLMenuButtonTarget — lightweight class so the button has a target
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
    UIView *piece = recognizer.view;
    UIWindow *window = sMenuWindow;
    if (!window) return;

    if (recognizer.state == UIGestureRecognizerStateBegan ||
        recognizer.state == UIGestureRecognizerStateChanged) {
        CGPoint translation = [recognizer translationInView:piece.superview];
        CGRect frame = window.frame;
        frame.origin.x += translation.x;
        frame.origin.y += translation.y;
        window.frame = frame;
        [recognizer setTranslation:CGPointZero inView:piece.superview];
    }
}

@end

// ---------------------------------------------------------------------------
//  SLTopVC — walk the VC hierarchy to find the topmost presented VC
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
        if (w.isKeyWindow) {
            keyWindow = w;
            break;
        }
    }
    if (!keyWindow) return nil;

    UIViewController *vc = keyWindow.rootViewController;
    while (vc.presentedViewController) {
        vc = vc.presentedViewController;
    }
    return vc;
}

// ---------------------------------------------------------------------------
//  SLShowSettingsMenu — the main action sheet
// ---------------------------------------------------------------------------
static void SLShowSettingsMenu(void) {
    UIViewController *top = SLTopVC();
    if (!top) return;

    NSString *message = [NSString stringWithFormat:@"Spins logged: %ld  |  Speed: %.1fx",
                         (long)SLSpinStoreCount(),
                         SLSpeedControllerGetMultiplier()];

    UIAlertController *sheet =
        [UIAlertController alertControllerWithTitle:@"\U0001F3B0 SpinLogger"
                                            message:message
                                     preferredStyle:UIAlertControllerStyleActionSheet];

    // ---- Share CSV ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"\U0001F4E5 Share CSV"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        NSString *path = SLSpinStoreCSVPath();
        NSURL *fileURL = [NSURL fileURLWithPath:path];
        UIActivityViewController *avc =
            [[UIActivityViewController alloc] initWithActivityItems:@[fileURL]
                                             applicationActivities:nil];
        UIViewController *presenter = SLTopVC();
        if (presenter) {
            // iPad popover anchor
            avc.popoverPresentationController.sourceView = presenter.view;
            avc.popoverPresentationController.sourceRect =
                CGRectMake(CGRectGetMidX(presenter.view.bounds),
                           CGRectGetMidY(presenter.view.bounds), 0, 0);
            [presenter presentViewController:avc animated:YES completion:nil];
        }
    }]];

    // ---- Set Speed ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"\u26A1 Set Speed"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        UIAlertController *alert =
            [UIAlertController alertControllerWithTitle:@"Set Speed Multiplier"
                                               message:nil
                                        preferredStyle:UIAlertControllerStyleAlert];
        [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
            tf.keyboardType = UIKeyboardTypeDecimalPad;
            tf.text = [NSString stringWithFormat:@"%.1f", SLSpeedControllerGetMultiplier()];
        }];
        [alert addAction:[UIAlertAction actionWithTitle:@"Set"
                                                  style:UIAlertActionStyleDefault
                                                handler:^(UIAlertAction *_) {
            NSString *val = alert.textFields.firstObject.text;
            double mult = val.doubleValue;
            if (mult > 0) {
                SLSpeedControllerSetMultiplier(mult);
            }
        }]];
        [alert addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                                  style:UIAlertActionStyleCancel
                                                handler:nil]];
        UIViewController *presenter = SLTopVC();
        if (presenter) [presenter presentViewController:alert animated:YES completion:nil];
    }]];

    // ---- Set Spin Target ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"\U0001F3AF Set Spin Target"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        UIAlertController *alert =
            [UIAlertController alertControllerWithTitle:@"Set Spin Target"
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
            NSString *val = alert.textFields.firstObject.text;
            NSInteger target = val.integerValue;
            [SLSpinTarget shared].targetSpinCount = target;
        }]];
        [alert addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                                  style:UIAlertActionStyleCancel
                                                handler:nil]];
        UIViewController *presenter = SLTopVC();
        if (presenter) [presenter presentViewController:alert animated:YES completion:nil];
    }]];

    // ---- Auto-Reset Mode ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"\U0001F504 Auto-Reset Mode"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        NSString *current = [SLSpinTarget shared].autoResetMode ?: @"none";
        UIAlertController *modeSheet =
            [UIAlertController alertControllerWithTitle:@"Auto-Reset Mode"
                                               message:nil
                                        preferredStyle:UIAlertControllerStyleActionSheet];

        NSArray *modes = @[@"none", @"symbol", @"global"];
        for (NSString *mode in modes) {
            NSString *title = mode;
            if ([mode isEqualToString:current]) {
                title = [NSString stringWithFormat:@"\u2713 %@", mode];
            }
            [modeSheet addAction:[UIAlertAction actionWithTitle:title
                                                          style:UIAlertActionStyleDefault
                                                        handler:^(UIAlertAction *_) {
                [SLSpinTarget shared].autoResetMode = mode;
            }]];
        }
        [modeSheet addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                                      style:UIAlertActionStyleCancel
                                                    handler:nil]];

        UIViewController *presenter = SLTopVC();
        if (presenter) {
            modeSheet.popoverPresentationController.sourceView = presenter.view;
            modeSheet.popoverPresentationController.sourceRect =
                CGRectMake(CGRectGetMidX(presenter.view.bounds),
                           CGRectGetMidY(presenter.view.bounds), 0, 0);
            [presenter presentViewController:modeSheet animated:YES completion:nil];
        }
    }]];

    // ---- Reset Counters (destructive) ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"\U0001F5D1 Reset Counters"
                                              style:UIAlertActionStyleDestructive
                                            handler:^(UIAlertAction *_) {
        [[SLCounterOverlay shared] resetAllCounters];
    }]];

    // ---- Toggle Counters ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"\U0001F441 Toggle Counters"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        sCountersVisible = !sCountersVisible;
        if (sCountersVisible) {
            [[SLCounterOverlay shared] show];
        } else {
            [[SLCounterOverlay shared] hide];
        }
    }]];

    // ---- Preset 1: Save / Load ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"\U0001F4BE Save Preset 1"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        [[SLPresetManager shared] savePreset:1];
    }]];

    NSString *p1Summary = [[SLPresetManager shared] presetSummary:1] ?: @"empty";
    NSString *p1Title = [NSString stringWithFormat:@"\U0001F4C2 Load Preset 1 (%@)", p1Summary];
    [sheet addAction:[UIAlertAction actionWithTitle:p1Title
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        [[SLPresetManager shared] loadPreset:1];
    }]];

    // ---- Preset 2: Save / Load ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"\U0001F4BE Save Preset 2"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        [[SLPresetManager shared] savePreset:2];
    }]];

    NSString *p2Summary = [[SLPresetManager shared] presetSummary:2] ?: @"empty";
    NSString *p2Title = [NSString stringWithFormat:@"\U0001F4C2 Load Preset 2 (%@)", p2Summary];
    [sheet addAction:[UIAlertAction actionWithTitle:p2Title
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        [[SLPresetManager shared] loadPreset:2];
    }]];

    // ---- Close ----
    [sheet addAction:[UIAlertAction actionWithTitle:@"Close"
                                              style:UIAlertActionStyleCancel
                                            handler:nil]];

    // iPad popover anchor for the main sheet
    sheet.popoverPresentationController.sourceView = top.view;
    sheet.popoverPresentationController.sourceRect =
        CGRectMake(CGRectGetMidX(top.view.bounds),
                   CGRectGetMidY(top.view.bounds), 0, 0);

    [top presentViewController:sheet animated:YES completion:nil];
}

// ---------------------------------------------------------------------------
//  SLMenuOverlayInstall — creates the floating "SL" button window
// ---------------------------------------------------------------------------
void SLMenuOverlayInstall(void) {
    if (sMenuWindow) return;  // already installed

    // Find the active UIWindowScene
    UIWindowScene *activeScene = nil;
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if ([scene isKindOfClass:[UIWindowScene class]] &&
            scene.activationState == UISceneActivationStateForegroundActive) {
            activeScene = (UIWindowScene *)scene;
            break;
        }
    }
    if (!activeScene) return;

    // Compute position: right edge, vertically centered
    CGRect screenBounds = activeScene.coordinateSpace.bounds;
    CGFloat btnSize = 50.0;
    CGFloat x = screenBounds.size.width - btnSize - 8.0;
    CGFloat y = screenBounds.size.height / 2.0 - btnSize / 2.0;
    CGRect windowFrame = CGRectMake(x, y, btnSize, btnSize);

    // Create a small overlay window
    UIWindow *overlay = [[UIWindow alloc] initWithWindowScene:activeScene];
    overlay.frame = windowFrame;
    overlay.windowLevel = UIWindowLevelAlert + 200;
    overlay.backgroundColor = [UIColor clearColor];
    overlay.clipsToBounds = YES;

    // Root view controller to host the button
    UIViewController *rootVC = [[UIViewController alloc] init];
    rootVC.view.backgroundColor = [UIColor clearColor];
    overlay.rootViewController = rootVC;

    // Create the round blue button
    UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
    btn.frame = CGRectMake(0, 0, btnSize, btnSize);
    btn.backgroundColor = [UIColor systemBlueColor];
    btn.layer.cornerRadius = btnSize / 2.0;
    btn.clipsToBounds = YES;

    [btn setTitle:@"SL" forState:UIControlStateNormal];
    [btn setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    btn.titleLabel.font = [UIFont boldSystemFontOfSize:16.0];

    // Tap target
    [btn addTarget:[SLMenuButtonTarget class]
            action:@selector(tapped)
  forControlEvents:UIControlEventTouchUpInside];

    // Pan gesture for dragging
    UIPanGestureRecognizer *pan =
        [[UIPanGestureRecognizer alloc] initWithTarget:[SLMenuButtonTarget class]
                                                action:@selector(handlePan:)];
    [btn addGestureRecognizer:pan];

    [rootVC.view addSubview:btn];

    // Show the window
    overlay.hidden = NO;
    sMenuWindow = overlay;
}
