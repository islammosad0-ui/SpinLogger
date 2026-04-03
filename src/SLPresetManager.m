#import "SLPresetManager.h"

@implementation SLPresetManager
+ (instancetype)shared {
    static SLPresetManager *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}
- (void)savePreset:(NSInteger)slot {}
- (void)loadPreset:(NSInteger)slot {}
- (NSString *)presetSummary:(NSInteger)slot { return @"(empty)"; }
@end
