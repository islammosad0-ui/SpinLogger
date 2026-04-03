#import <UIKit/UIKit.h>

@interface SLCounterOverlay : NSObject
+ (instancetype)shared;
- (void)install;
- (void)show;
- (void)hide;
- (void)resetAllCounters;
- (void)resetCounterForSymbol:(NSString *)symbol;
- (NSDictionary<NSString *, NSNumber *> *)currentCounts;
@end
