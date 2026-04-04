#import <Foundation/Foundation.h>

@interface SLTrisController : NSObject
@property (nonatomic, copy) NSString *lockTarget;
@property (nonatomic, assign) BOOL skipEnabled;
+ (instancetype)shared;
- (void)install;
- (void)showTrisMonitor;
- (void)hideTrisMonitor;
- (void)addSpinToHistory:(NSArray<NSString *> *)reels;
@end
