#import <Foundation/Foundation.h>

@interface SLDebtMonitor : NSObject
+ (instancetype)shared;
- (void)install;
- (void)show;
- (void)hide;
@end
