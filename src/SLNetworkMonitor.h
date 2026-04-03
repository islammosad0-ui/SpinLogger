#import <UIKit/UIKit.h>

@interface SLNetworkMonitor : NSObject
+ (instancetype)shared;
- (void)install;
- (void)show;
- (void)hide;
@end
