#import "SLSpeedController.h"
#import "SLConstants.h"
#import <objc/runtime.h>
#import <QuartzCore/QuartzCore.h>

// ---------------------------------------------------------------------------
//  Static state
// ---------------------------------------------------------------------------
static double sSpeedMultiplier = 1.0;

// ---------------------------------------------------------------------------
//  Original IMPs
// ---------------------------------------------------------------------------
typedef NSTimer *(*OrigScheduledTimerIMP)(id, SEL, NSTimeInterval, id, SEL, id, BOOL);
static OrigScheduledTimerIMP sOrigScheduledTimer = NULL;

typedef void (*OrigAddToRunLoopIMP)(id, SEL, NSRunLoop *, NSRunLoopMode);
static OrigAddToRunLoopIMP sOrigAddToRunLoop = NULL;

// ---------------------------------------------------------------------------
//  Swizzled +[NSTimer scheduledTimerWithTimeInterval:target:selector:userInfo:repeats:]
// ---------------------------------------------------------------------------
static NSTimer *SL_scheduledTimer(id self, SEL _cmd,
                                  NSTimeInterval interval,
                                  id target, SEL selector,
                                  id userInfo, BOOL repeats) {
    if (sSpeedMultiplier > 1.0 && interval > 0.01) {
        interval /= sSpeedMultiplier;
    }
    return sOrigScheduledTimer(self, _cmd, interval, target, selector, userInfo, repeats);
}

// ---------------------------------------------------------------------------
//  Swizzled -[CADisplayLink addToRunLoop:forMode:]
// ---------------------------------------------------------------------------
static void SL_addToRunLoop(id self, SEL _cmd,
                            NSRunLoop *runLoop,
                            NSRunLoopMode mode) {
    if (sSpeedMultiplier > 1.0) {
        NSInteger fps = (NSInteger)(60.0 * sSpeedMultiplier);
        if (fps > 240) fps = 240;   // cap to avoid insane values
        [(CADisplayLink *)self setPreferredFramesPerSecond:fps];
    }
    sOrigAddToRunLoop(self, _cmd, runLoop, mode);
}

// ---------------------------------------------------------------------------
//  Public API
// ---------------------------------------------------------------------------
void SLSpeedControllerInstall(void) {
    // Restore saved multiplier
    double saved = [[NSUserDefaults standardUserDefaults] doubleForKey:kSLDefaultsSpeedMultiplier];
    if (saved >= 1.0) {
        sSpeedMultiplier = saved;
        if (sSpeedMultiplier > 50.0) sSpeedMultiplier = 50.0;
    }

    // Swizzle +[NSTimer scheduledTimerWithTimeInterval:target:selector:userInfo:repeats:]
    {
        SEL sel = @selector(scheduledTimerWithTimeInterval:target:selector:userInfo:repeats:);
        Method m = class_getClassMethod([NSTimer class], sel);
        if (m) {
            sOrigScheduledTimer = (OrigScheduledTimerIMP)method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_scheduledTimer);
        }
    }

    // Swizzle -[CADisplayLink addToRunLoop:forMode:]
    {
        SEL sel = @selector(addToRunLoop:forMode:);
        Method m = class_getInstanceMethod([CADisplayLink class], sel);
        if (m) {
            sOrigAddToRunLoop = (OrigAddToRunLoopIMP)method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_addToRunLoop);
        }
    }

    NSLog(@"[SpinLogger] SLSpeedController installed — multiplier: %.1fx", sSpeedMultiplier);
}

void SLSpeedControllerSetMultiplier(double multiplier) {
    if (multiplier < 1.0)  multiplier = 1.0;
    if (multiplier > 50.0) multiplier = 50.0;
    sSpeedMultiplier = multiplier;

    [[NSUserDefaults standardUserDefaults] setDouble:sSpeedMultiplier
                                              forKey:kSLDefaultsSpeedMultiplier];
    [[NSUserDefaults standardUserDefaults] synchronize];

    NSLog(@"[SpinLogger] Speed multiplier set to %.1fx", sSpeedMultiplier);
}

double SLSpeedControllerGetMultiplier(void) {
    return sSpeedMultiplier;
}
