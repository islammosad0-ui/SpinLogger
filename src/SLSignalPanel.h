#import <UIKit/UIKit.h>

@interface SLSignalPanel : NSObject
+ (instancetype)shared;
- (void)install;
- (void)show;
- (void)hide;
@end
