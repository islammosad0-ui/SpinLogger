#import <Foundation/Foundation.h>

@interface SLSpinTarget : NSObject
@property (nonatomic, assign) NSInteger targetSpinCount;
@property (nonatomic, copy) NSString *autoResetMode;
@property (nonatomic, assign) NSInteger currentSessionSpins;
@property (nonatomic, assign) BOOL enabled;  // power button — target alert only fires when YES
+ (instancetype)shared;
- (void)install;
@end
