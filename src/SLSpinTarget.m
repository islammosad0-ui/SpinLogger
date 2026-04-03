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

- (void)install {
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification
                                               object:nil];
}

- (void)onSpinReceived:(NSNotification *)notification {
    self.currentSessionSpins++;

    SLSpinResult *result = notification.userInfo[SLSpinDataKey];

    // Auto-reset on 3-of-a-kind
    if (result && [result.reel1 isEqualToString:result.reel2] &&
        [result.reel2 isEqualToString:result.reel3]) {
        if ([self.autoResetMode isEqualToString:@"symbol"]) {
            [[SLCounterOverlay shared] resetCounterForSymbol:result.reel1];
        } else if ([self.autoResetMode isEqualToString:@"global"]) {
            [[SLCounterOverlay shared] resetAllCounters];
        }
    }

    if (self.targetSpinCount > 0 &&
        self.currentSessionSpins >= self.targetSpinCount) {
        [self showTargetReachedAlert];
    }
}

- (void)showTargetReachedAlert {
    NSString *message = [NSString stringWithFormat:@"You have completed %ld spins.",
                         (long)self.currentSessionSpins];

    UIAlertController *alert =
        [UIAlertController alertControllerWithTitle:@"Spin Target Reached"
                                            message:message
                                     preferredStyle:UIAlertControllerStyleAlert];

    __weak typeof(self) weakSelf = self;
    [alert addAction:[UIAlertAction actionWithTitle:@"Reset & Continue"
                                              style:UIAlertActionStyleDefault
                                            handler:^(UIAlertAction *_) {
        weakSelf.currentSessionSpins = 0;
        [[SLCounterOverlay shared] resetAllCounters];
    }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Stop"
                                              style:UIAlertActionStyleCancel
                                            handler:nil]];

    UIViewController *top = [self topViewController];
    if (top) [top presentViewController:alert animated:YES completion:nil];
}

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
        if (window.isKeyWindow) { keyWindow = window; break; }
    }
    UIViewController *vc = keyWindow.rootViewController;
    while (vc.presentedViewController) vc = vc.presentedViewController;
    return vc;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
