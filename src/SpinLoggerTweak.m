#import <Foundation/Foundation.h>
#import "SLConstants.h"
#import "SLCounterOverlay.h"
#import "SLSpinTarget.h"
#import "SLTrisController.h"
#import "SLNetworkMonitor.h"
#import "SLDebtMonitor.h"
#import "SLMemoryScanner.h"
#import "SLIdxStrategy.h"
#import "SLSignalPanel.h"
#import "SLV4Model.h"
#import "SLV4Panel.h"

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
            // [[SLDebtMonitor shared] install];  // hidden — not in active use
            [[SLMemoryScanner shared] startScanning];
            [[SLSignalPanel shared] install];

            // V4 hazard HUD — load bundled model and install panel.
            if ([[SLV4Model shared] loadFromAppBundle]) {
                [[SLV4Panel shared] install];
            } else {
                NSLog(@"[SpinLogger] V4 model not found — V4 panel disabled");
            }

            SLMenuOverlayInstall();

            NSLog(@"[SpinLogger] UI components initialized");
        }
    );
}
