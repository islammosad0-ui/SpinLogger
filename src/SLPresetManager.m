#import "SLPresetManager.h"
#import "SLConstants.h"
#import "SLSpeedController.h"
#import "SLSpinTarget.h"
#import "SLTrisController.h"

@implementation SLPresetManager

+ (instancetype)shared {
    static SLPresetManager *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (NSString *)keyForSlot:(NSInteger)slot {
    return (slot == 2) ? kSLDefaultsPreset2 : kSLDefaultsPreset1;
}

- (void)savePreset:(NSInteger)slot {
    NSDictionary *dict = @{
        @"speed":           @(SLSpeedControllerGetMultiplier()),
        @"spinTarget":      @([SLSpinTarget shared].targetSpinCount),
        @"autoResetMode":   [SLSpinTarget shared].autoResetMode ?: @"none",
        @"trisLockTarget":  [SLTrisController shared].lockTarget ?: @"",
        @"trisSkipEnabled": @([SLTrisController shared].skipEnabled)
    };
    [[NSUserDefaults standardUserDefaults] setObject:dict forKey:[self keyForSlot:slot]];
    [[NSUserDefaults standardUserDefaults] synchronize];
}

- (void)loadPreset:(NSInteger)slot {
    NSDictionary *dict = [[NSUserDefaults standardUserDefaults] dictionaryForKey:[self keyForSlot:slot]];
    if (!dict) return;

    SLSpeedControllerSetMultiplier([dict[@"speed"] doubleValue]);
    [SLSpinTarget shared].targetSpinCount = [dict[@"spinTarget"] integerValue];
    [SLSpinTarget shared].autoResetMode   = dict[@"autoResetMode"] ?: @"none";
    [SLTrisController shared].lockTarget  = dict[@"trisLockTarget"] ?: @"";
    [SLTrisController shared].skipEnabled = [dict[@"trisSkipEnabled"] boolValue];
}

- (NSString *)presetSummary:(NSInteger)slot {
    NSDictionary *dict = [[NSUserDefaults standardUserDefaults] dictionaryForKey:[self keyForSlot:slot]];
    if (!dict) return @"(empty)";
    return [NSString stringWithFormat:@"%.0fx | T:%ld | %@",
            [dict[@"speed"] doubleValue],
            (long)[dict[@"spinTarget"] integerValue],
            dict[@"autoResetMode"] ?: @"none"];
}

@end
