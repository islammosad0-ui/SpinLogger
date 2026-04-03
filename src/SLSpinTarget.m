#import "SLSpinTarget.h"

@implementation SLSpinTarget
+ (instancetype)shared {
    static SLSpinTarget *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}
- (void)install {}
@end
