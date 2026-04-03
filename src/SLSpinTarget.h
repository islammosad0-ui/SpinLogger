#import <Foundation/Foundation.h>

@interface SLSpinTarget : NSObject
@property (nonatomic, assign) NSInteger targetSpinCount;
@property (nonatomic, copy) NSString *autoResetMode;
@property (nonatomic, assign) NSInteger currentSessionSpins;
+ (instancetype)shared;
- (void)install;
@end
