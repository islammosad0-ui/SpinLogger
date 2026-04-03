#import "SLSpinTarget.h"
#import "SLConstants.h"
#import "SLCounterOverlay.h"
#import "SLSpinParser.h"
#import <UIKit/UIKit.h>

@implementation SLSpinTarget

+ (instancetype)shared {
    static SLSpinTarget *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
        _targetSpinCount = [defaults integerForKey:kSLDefaultsSpinTarget];
        NSString *mode = [defaults stringForKey:kSLDefaultsAutoResetMode];
        _autoResetMode = [mode copy] ?: @"none";
        _currentSessionSpins = 0;
    }
    return self;
}

#pragma mark - Custom Setters

- (void)setTargetSpinCount:(NSInteger)targetSpinCount {
    _targetSpinCount = targetSpinCount;
    [[NSUserDefaults standardUserDefaults] setInteger:targetSpinCount
                                               forKey:kSLDefaultsSpinTarget];
}

- (void)setAutoResetMode:(NSString *)autoResetMode {
    _autoResetMode = [autoResetMode copy];
    [[NSUserDefaults standardUserDefaults] setObject:autoResetMode
                                              forKey:kSLDefaultsAutoResetMode];
}

#pragma mark - Install

- (void)install {
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification
                                               object:nil];
}

#pragma mark - Notification Handler

- (void)onSpinReceived:(NSNotification *)notification {
    self.currentSessionSpins++;

    SLSpinResult *result = notification.userInfo[SLSpinDataKey];

    // Auto-reset logic for 3-of-a-kind
    if (result && [result.reel1 isEqualToString:result.reel2] &&
        [result.reel2 isEqualToString:result.reel3]) {
        if ([self.autoResetMode isEqualToString:@"symbol"]) {
            [[SLCounterOverlay shared] resetCounterForSymbol:result.reel1];
        } else if ([self.autoResetMode isEqualToString:@"global"]) {
            [[SLCounterOverlay shared] resetAllCounters];
        }
    }

    // Target reached check
    if (self.targetSpinCount > 0 &&
        self.currentSessionSpins >= self.targetSpinCount) {
        [self showTargetReachedAlert];
    }
}

#pragma mark - Alert

- (void)showTargetReachedAlert {
    NSString *message = [NSString stringWithFormat:@"You have completed %ld spins.",
                         (long)self.currentSessionSpins];

    UIAlertController *alert =
        [UIAlertController alertControllerWithTitle:@"Spin Target Reached"
                                            message:message
                                     preferredStyle:UIAlertControllerStyleAlert];

    __weak typeof(self) weakSelf = self;
    UIAlertAction *resetAction =
        [UIAlertAction actionWithTitle:@"Reset & Continue"
                                 style:UIAlertActionStyleDefault
                               handler:^(UIAlertAction *action) {
            __strong typeof(weakSelf) strongSelf = weakSelf;
            [[SLCounterOverlay shared] resetAllCounters];
            strongSelf.currentSessionSpins = 0;
        }];

    UIAlertAction *stopAction =
        [UIAlertAction actionWithTitle:@"Stop"
                                 style:UIAlertActionStyleCancel
                               handler:nil];

    [alert addAction:resetAction];
    [alert addAction:stopAction];

    UIViewController *topVC = [self topViewController];
    if (topVC) {
        [topVC presentViewController:alert animated:YES completion:nil];
    }
}

#pragma mark - Top View Controller

- (UIViewController *)topViewController {
    UIWindowScene *activeScene = nil;
    for (UIScene *scene in [UIApplication sharedApplication].connectedScenes) {
        if ([scene isKindOfClass:[UIWindowScene class]] &&
            scene.activationState == UISceneActivationStateForegroundActive) {
            activeScene = (UIWindowScene *)scene;
            break;
        }
    }

    UIWindow *keyWindow = nil;
    for (UIWindow *window in activeScene.windows) {
        if (window.isKeyWindow) {
            keyWindow = window;
            break;
        }
    }

    UIViewController *vc = keyWindow.rootViewController;
    while (vc.presentedViewController) {
        vc = vc.presentedViewController;
    }
    return vc;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
