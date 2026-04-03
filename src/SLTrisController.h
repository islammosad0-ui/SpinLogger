#import <Foundation/Foundation.h>

@interface SLTrisController : NSObject
+ (instancetype)shared;
@property (nonatomic, copy) NSString *lockTarget;
@property (nonatomic, assign) BOOL skipEnabled;
- (void)install;
@end
