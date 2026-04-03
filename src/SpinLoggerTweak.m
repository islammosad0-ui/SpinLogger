#import <Foundation/Foundation.h>
#import "SLConstants.h"
#import "SLCounterOverlay.h"
#import "SLSpinTarget.h"

// ---------------------------------------------------------------------------
//  Forward declarations — implemented in other translation units
// ---------------------------------------------------------------------------
extern void SLNetworkInterceptorInstall(void);
extern void SLSpeedControllerInstall(void);
extern void SLMenuOverlayInstall(void);

// ---------------------------------------------------------------------------
//  Constructor — called automatically when the dylib is loaded
// ---------------------------------------------------------------------------
__attribute__((constructor))
static void SpinLoggerInit(void) {
    dispatch_after(
        dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2.0 * NSEC_PER_SEC)),
        dispatch_get_main_queue(),
        ^{
            SLNetworkInterceptorInstall();
            SLSpeedControllerInstall();
            [[SLCounterOverlay shared] install];
            [[SLSpinTarget shared] install];
            SLMenuOverlayInstall();
        }
    );
}
