#import "SLCounterOverlay.h"

@implementation SLCounterOverlay
+ (instancetype)shared {
    static SLCounterOverlay *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}
- (void)install {}
- (void)show {}
- (void)hide {}
- (void)resetAllCounters {}
- (void)resetCounterForSymbol:(NSString *)symbol {}
- (NSDictionary<NSString *, NSNumber *> *)currentCounts { return @{}; }
@end
