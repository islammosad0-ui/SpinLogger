#import <Foundation/Foundation.h>
#import "SLDebtTracker.h"

@interface SLDebtMonitor : NSObject
@property (nonatomic, readonly) SLDebtTracker *accTracker;
@property (nonatomic, readonly) SLDebtTracker *spnTracker;
+ (instancetype)shared;
- (void)install;
- (void)show;
- (void)hide;
- (void)resetAccTracker;
- (void)resetSpnTracker;
@end
