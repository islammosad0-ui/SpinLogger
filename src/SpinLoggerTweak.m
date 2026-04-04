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
    // === IMMEDIATE — must run BEFORE Unity creates its NSURLSession ===
    SLJailbreakBypassInstall();
    SLNetworkInterceptorInstall();  // NSURLProtocol + session swizzle MUST be first
    SLSpeedControllerInstall();

    NSLog(@"[SpinLogger] Network interceptor + speed controller installed (immediate)");

    // === DELAYED — UI components need a window scene ===
    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2.0 * NSEC_PER_SEC)),
        dispatch_get_main_queue(),
        ^{
            [[SLCounterOverlay shared] install];
            [[SLSpinTarget shared] install];
            [[SLTrisController shared] install];
            [[SLNetworkMonitor shared] install];
            SLMenuOverlayInstall();

            NSLog(@"[SpinLogger] UI components initialized");
        }
    );
}
