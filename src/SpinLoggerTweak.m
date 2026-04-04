#import <Foundation/Foundation.h>
#import "SLConstants.h"
#import "SLCounterOverlay.h"
#import "SLSpinTarget.h"
#import "SLTrisController.h"
#import "SLNetworkMonitor.h"

extern void SLJailbreakBypassInstall(void);
extern void SLNetworkInterceptorInstall(void);
extern void SLSpeedControllerInstall(void);
extern void SLMenuOverlayInstall(void);

__attribute__((constructor))
static void SpinLoggerInit(void) {
    // Jailbreak bypass runs IMMEDIATELY before app checks
    SLJailbreakBypassInstall();

    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2.0 * NSEC_PER_SEC)),
        dispatch_get_main_queue(),
        ^{
            SLNetworkInterceptorInstall();
            SLSpeedControllerInstall();
            [[SLCounterOverlay shared] install];
            [[SLSpinTarget shared] install];
            [[SLTrisController shared] install];
            [[SLNetworkMonitor shared] install];
            SLMenuOverlayInstall();

            NSLog(@"[SpinLogger] SPEEDER ELITE initialized (all components ready)");
        }
    );
}
