#import <Foundation/Foundation.h>

@interface SLSpinTarget : NSObject
+ (instancetype)shared;
@property (nonatomic, assign) NSInteger targetSpinCount;
@property (nonatomic, copy) NSString *autoResetMode;
@property (nonatomic, assign) NSInteger currentSessionSpins;
- (void)install;
@end
