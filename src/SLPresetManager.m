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

#pragma mark - Helpers

- (NSString *)keyForSlot:(NSInteger)slot {
    switch (slot) {
        case 1:  return kSLDefaultsPreset1;
        case 2:  return kSLDefaultsPreset2;
        default: return kSLDefaultsPreset1;
    }
}

#pragma mark - Save / Load

- (void)savePreset:(NSInteger)slot {
    NSString *lockTarget = [SLTrisController shared].lockTarget ?: @"";

    NSDictionary *dict = @{
        @"speed":           @(SLSpeedControllerGetMultiplier()),
        @"spinTarget":      @([SLSpinTarget shared].targetSpinCount),
        @"autoResetMode":   [SLSpinTarget shared].autoResetMode ?: @"",
        @"trisLockTarget":  lockTarget,
        @"trisSkipEnabled": @([SLTrisController shared].skipEnabled)
    };

    NSString *key = [self keyForSlot:slot];
    [[NSUserDefaults standardUserDefaults] setObject:dict forKey:key];
    [[NSUserDefaults standardUserDefaults] synchronize];

    NSLog(@"[SpinLogger] Saved preset %ld -> %@", (long)slot, key);
}

- (void)loadPreset:(NSInteger)slot {
    NSString *key = [self keyForSlot:slot];
    NSDictionary *dict = [[NSUserDefaults standardUserDefaults] dictionaryForKey:key];
    if (!dict) {
        NSLog(@"[SpinLogger] No preset found for slot %ld", (long)slot);
        return;
    }

    SLSpeedControllerSetMultiplier([dict[@"speed"] doubleValue]);
    [SLSpinTarget shared].targetSpinCount = [dict[@"spinTarget"] integerValue];
    [SLSpinTarget shared].autoResetMode   = dict[@"autoResetMode"] ?: @"";
    [SLTrisController shared].lockTarget  = dict[@"trisLockTarget"] ?: @"";
    [SLTrisController shared].skipEnabled = [dict[@"trisSkipEnabled"] boolValue];

    NSLog(@"[SpinLogger] Loaded preset %ld <- %@", (long)slot, key);
}

#pragma mark - Summary

- (NSString *)presetSummary:(NSInteger)slot {
    NSString *key = [self keyForSlot:slot];
    NSDictionary *dict = [[NSUserDefaults standardUserDefaults] dictionaryForKey:key];
    if (!dict) {
        return @"(empty)";
    }

    double speed       = [dict[@"speed"] doubleValue];
    NSInteger target   = [dict[@"spinTarget"] integerValue];
    NSString *mode     = dict[@"autoResetMode"] ?: @"";

    return [NSString stringWithFormat:@"Speed: %.0fx | Target: %ld | Reset: %@",
            speed, (long)target, mode];
}

@end
