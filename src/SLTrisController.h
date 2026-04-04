#import <Foundation/Foundation.h>

@interface SLTrisController : NSObject
@property (nonatomic, copy) NSString *lockTarget;
@property (nonatomic, assign) BOOL skipEnabled;
+ (instancetype)shared;
- (void)install;
- (void)showTrisMonitor;
- (void)hideTrisMonitor;
// Called by counter overlay when a triple is hit
- (void)recordTriple:(NSString *)symbol distance:(NSInteger)distance;
- (void)recordTriple:(NSString *)symbol distance:(NSInteger)distance symbolCount:(NSInteger)symCount;
@end
