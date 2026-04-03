#import <Foundation/Foundation.h>

@interface SLPresetManager : NSObject
+ (instancetype)shared;
- (void)savePreset:(NSInteger)slot;
- (void)loadPreset:(NSInteger)slot;
- (NSString *)presetSummary:(NSInteger)slot;
@end
