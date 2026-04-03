#import "SLSpeedController.h"
#import "SLConstants.h"
#import <objc/runtime.h>
#import <QuartzCore/QuartzCore.h>

static double sSpeedMultiplier = 1.0;

typedef NSTimer *(*OrigScheduledTimerIMP)(id, SEL, NSTimeInterval, id, SEL, id, BOOL);
static OrigScheduledTimerIMP sOrigScheduledTimer = NULL;

typedef void (*OrigAddToRunLoopIMP)(id, SEL, NSRunLoop *, NSRunLoopMode);
static OrigAddToRunLoopIMP sOrigAddToRunLoop = NULL;

static NSTimer *SL_scheduledTimer(id self, SEL _cmd,
                                  NSTimeInterval interval,
                                  id target, SEL selector,
                                  id userInfo, BOOL repeats) {
    if (sSpeedMultiplier > 1.0 && interval > 0.001) {
        interval /= sSpeedMultiplier;
    }
    return sOrigScheduledTimer(self, _cmd, interval, target, selector, userInfo, repeats);
}

static void SL_addToRunLoop(id self, SEL _cmd,
                            NSRunLoop *runLoop,
                            NSRunLoopMode mode) {
    if (sSpeedMultiplier > 1.0) {
        NSInteger fps = (NSInteger)(60.0 * sSpeedMultiplier);
        if (fps > 240) fps = 240;
        [(CADisplayLink *)self setPreferredFramesPerSecond:fps];
    }
    sOrigAddToRunLoop(self, _cmd, runLoop, mode);
}

void SLSpeedControllerInstall(void) {
    double saved = [[NSUserDefaults standardUserDefaults] doubleForKey:kSLDefaultsSpeedMultiplier];
    if (saved >= 1.0) {
        sSpeedMultiplier = saved;
        if (sSpeedMultiplier > 50.0) sSpeedMultiplier = 50.0;
    }

    {
        SEL sel = @selector(scheduledTimerWithTimeInterval:target:selector:userInfo:repeats:);
        Method m = class_getClassMethod([NSTimer class], sel);
        if (m) {
            sOrigScheduledTimer = (OrigScheduledTimerIMP)method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_scheduledTimer);
        }
    }

    {
        SEL sel = @selector(addToRunLoop:forMode:);
        Method m = class_getInstanceMethod([CADisplayLink class], sel);
        if (m) {
            sOrigAddToRunLoop = (OrigAddToRunLoopIMP)method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_addToRunLoop);
        }
    }

    NSLog(@"[SpinLogger] Speed controller installed — %.1fx", sSpeedMultiplier);
}

void SLSpeedControllerSetMultiplier(double multiplier) {
    if (multiplier < 1.0)  multiplier = 1.0;
    if (multiplier > 50.0) multiplier = 50.0;
    sSpeedMultiplier = multiplier;
    [[NSUserDefaults standardUserDefaults] setDouble:sSpeedMultiplier
                                              forKey:kSLDefaultsSpeedMultiplier];
    [[NSUserDefaults standardUserDefaults] synchronize];
    NSLog(@"[SpinLogger] Speed set to %.1fx", sSpeedMultiplier);
}

double SLSpeedControllerGetMultiplier(void) {
    return sSpeedMultiplier;
}
