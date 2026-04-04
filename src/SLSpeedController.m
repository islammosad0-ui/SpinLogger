#import "SLSpeedController.h"
#import "SLConstants.h"
#import <UIKit/UIKit.h>
#import <objc/runtime.h>
#import <objc/message.h>

// ---------------------------------------------------------------------------
//  Speed Controller — SKScene.speed (like One.dylib)
//
//  Coin Master uses SpriteKit. One.dylib sets SKScene.speed to the multiplier.
//  We swizzle SKScene.didMoveToView: + periodic timer to apply speed.
// ---------------------------------------------------------------------------

static double sSpeedMultiplier = 1.0;
static IMP sOrigDidMoveToView = NULL;

// Forward declaration
static void SLFindAndApplySpeedInView(UIView *view);

static void SLApplySpeed(id scene) {
    if (sSpeedMultiplier > 1.0) {
        SEL sel = @selector(setSpeed:);
        if ([scene respondsToSelector:sel]) {
            typedef void (*Fn)(id, SEL, CGFloat);
            ((Fn)objc_msgSend)(scene, sel, (CGFloat)sSpeedMultiplier);
        }
    }
}

static void SL_didMoveToView(id self, SEL _cmd, id view) {
    if (sOrigDidMoveToView) {
        ((void(*)(id, SEL, id))sOrigDidMoveToView)(self, _cmd, view);
    }
    SLApplySpeed(self);
}

static void SLFindAndApplySpeedInView(UIView *view) {
    Class skViewClass = NSClassFromString(@"SKView");
    if (skViewClass && [view isKindOfClass:skViewClass]) {
        SEL sceneSel = @selector(scene);
        if ([view respondsToSelector:sceneSel]) {
            id scene = ((id(*)(id, SEL))objc_msgSend)(view, sceneSel);
            if (scene) SLApplySpeed(scene);
        }
    }
    for (UIView *sub in view.subviews) {
        SLFindAndApplySpeedInView(sub);
    }
}

static void SLApplySpeedToAllScenes(void) {
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if (![s isKindOfClass:[UIWindowScene class]]) continue;
        for (UIWindow *w in ((UIWindowScene *)s).windows) {
            if (w.rootViewController.view) {
                SLFindAndApplySpeedInView(w.rootViewController.view);
            }
        }
    }
}

void SLSpeedControllerInstall(void) {
    double saved = [[NSUserDefaults standardUserDefaults] doubleForKey:kSLDefaultsSpeedMultiplier];
    if (saved >= 1.0) {
        sSpeedMultiplier = saved;
        if (sSpeedMultiplier > 50.0) sSpeedMultiplier = 50.0;
    }

    // Swizzle SKScene.didMoveToView:
    Class skSceneClass = NSClassFromString(@"SKScene");
    if (skSceneClass) {
        SEL sel = @selector(didMoveToView:);
        Method m = class_getInstanceMethod(skSceneClass, sel);
        if (m) {
            sOrigDidMoveToView = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_didMoveToView);
            NSLog(@"[SpinLogger] Hooked SKScene.didMoveToView: for speed");
        }
    }

    // Periodic timer to re-apply speed (game may reset it on transitions)
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(3.0 * NSEC_PER_SEC)),
                   dispatch_get_main_queue(), ^{
        [NSTimer scheduledTimerWithTimeInterval:2.0
                                        repeats:YES
                                          block:^(NSTimer *t) {
            if (sSpeedMultiplier > 1.0) SLApplySpeedToAllScenes();
        }];
    });

    NSLog(@"[SpinLogger] Speed controller installed (SKScene.speed) — %.1fx", sSpeedMultiplier);
}

void SLSpeedControllerSetMultiplier(double multiplier) {
    if (multiplier < 1.0)  multiplier = 1.0;
    if (multiplier > 50.0) multiplier = 50.0;
    sSpeedMultiplier = multiplier;
    [[NSUserDefaults standardUserDefaults] setDouble:sSpeedMultiplier forKey:kSLDefaultsSpeedMultiplier];
    [[NSUserDefaults standardUserDefaults] synchronize];
    dispatch_async(dispatch_get_main_queue(), ^{ SLApplySpeedToAllScenes(); });
    NSLog(@"[SpinLogger] Speed set to %.1fx", sSpeedMultiplier);
}

double SLSpeedControllerGetMultiplier(void) {
    return sSpeedMultiplier;
}
