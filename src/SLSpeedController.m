#import "SLSpeedController.h"
#import "SLConstants.h"
#import <UIKit/UIKit.h>
#import <objc/runtime.h>
#import <dlfcn.h>

// ---------------------------------------------------------------------------
//  Speed Controller — Unity Time.timeScale (the CORRECT approach)
//
//  Android APK analysis confirmed: speed works via Time.timeScale
//  iOS UnityFramework has "UnityEngine.Time::set_timeScale" icall
//
//  Approach: Use il2cpp_resolve_icall to get the set_timeScale function
//  pointer, then call it directly with the multiplier value.
// ---------------------------------------------------------------------------

static double sSpeedMultiplier = 1.0;

// Function pointer types for Unity Time API
typedef void (*SetTimeScaleFn)(float);
typedef float (*GetTimeScaleFn)(void);

static SetTimeScaleFn sSetTimeScale = NULL;
static GetTimeScaleFn sGetTimeScale = NULL;

// il2cpp_resolve_icall resolves Unity internal calls by name
typedef void *(*ResolveICallFn)(const char *);

static void SLResolveUnityTime(void) {
    if (sSetTimeScale) return;  // already resolved

    // Try to find il2cpp_resolve_icall in the loaded UnityFramework
    ResolveICallFn resolveICall = (ResolveICallFn)dlsym(RTLD_DEFAULT, "il2cpp_resolve_icall");
    if (!resolveICall) {
        NSLog(@"[SpinLogger] il2cpp_resolve_icall not found — Unity not loaded yet?");
        return;
    }

    sSetTimeScale = (SetTimeScaleFn)resolveICall("UnityEngine.Time::set_timeScale");
    sGetTimeScale = (GetTimeScaleFn)resolveICall("UnityEngine.Time::get_timeScale");

    if (sSetTimeScale) {
        NSLog(@"[SpinLogger] Resolved Time.set_timeScale at %p", sSetTimeScale);
    } else {
        NSLog(@"[SpinLogger] FAILED to resolve Time.set_timeScale");
    }
    if (sGetTimeScale) {
        NSLog(@"[SpinLogger] Resolved Time.get_timeScale at %p (current: %.2f)", sGetTimeScale, sGetTimeScale());
    }
}

static void SLApplyTimeScale(void) {
    if (!sSetTimeScale) {
        SLResolveUnityTime();
    }
    if (sSetTimeScale) {
        sSetTimeScale((float)sSpeedMultiplier);
    }
}

void SLSpeedControllerInstall(void) {
    double saved = [[NSUserDefaults standardUserDefaults] doubleForKey:kSLDefaultsSpeedMultiplier];
    if (saved >= 1.0) {
        sSpeedMultiplier = saved;
        if (sSpeedMultiplier > 50.0) sSpeedMultiplier = 50.0;
    }

    // Try to resolve immediately (might fail if Unity hasn't loaded yet)
    SLResolveUnityTime();

    // If not resolved, retry after Unity is fully loaded
    if (!sSetTimeScale) {
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(3.0 * NSEC_PER_SEC)),
                       dispatch_get_main_queue(), ^{
            SLResolveUnityTime();
            if (sSetTimeScale && sSpeedMultiplier > 1.0) {
                SLApplyTimeScale();
            }
        });
    }

    // Periodic re-apply (game may reset timeScale on scene transitions)
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(5.0 * NSEC_PER_SEC)),
                   dispatch_get_main_queue(), ^{
        [NSTimer scheduledTimerWithTimeInterval:1.0
                                        repeats:YES
                                          block:^(NSTimer *t) {
            if (sSpeedMultiplier > 1.0) SLApplyTimeScale();
        }];
    });

    NSLog(@"[SpinLogger] Speed controller installed (Unity Time.timeScale) — %.1fx", sSpeedMultiplier);
}

void SLSpeedControllerSetMultiplier(double multiplier) {
    if (multiplier < 1.0)  multiplier = 1.0;
    if (multiplier > 50.0) multiplier = 50.0;
    sSpeedMultiplier = multiplier;
    [[NSUserDefaults standardUserDefaults] setDouble:sSpeedMultiplier forKey:kSLDefaultsSpeedMultiplier];
    [[NSUserDefaults standardUserDefaults] synchronize];
    SLApplyTimeScale();
    NSLog(@"[SpinLogger] Speed set to %.1fx (Time.timeScale)", sSpeedMultiplier);
}

double SLSpeedControllerGetMultiplier(void) {
    return sSpeedMultiplier;
}
