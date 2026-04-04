#import "SLSpinStore.h"
#import "SLConstants.h"

static NSInteger sSpinCount = 0;
static BOOL sHeaderEnsured = NO;

static NSString *const kCSVHeader =
    @"seq,timestamp,r1,r2,r3,reel_1,reel_2,reel_3,spin_result,reward_code,"
     "coins_won,coins,spins_remaining,shields,"
     "accum_current,accum_total,accum_mission,accum_reward_type,accum_reward_amount,"
     "is_triple,sos_symbol,all_time_spins";

static NSString *SLCSVPath(void) {
    static NSString *path = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        NSString *docs = NSSearchPathForDirectoriesInDomains(
            NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
        path = [docs stringByAppendingPathComponent:kSLSpinHistoryFile];
    });
    return path;
}

static void SLEnsureCSVHeader(void) {
    if (sHeaderEnsured) return;
    sHeaderEnsured = YES;

    NSFileManager *fm = [NSFileManager defaultManager];
    NSString *path = SLCSVPath();

    if (![fm fileExistsAtPath:path]) {
        NSString *headerLine = [kCSVHeader stringByAppendingString:@"\n"];
        [headerLine writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:nil];
        sSpinCount = 0;
    } else {
        NSString *contents = [NSString stringWithContentsOfFile:path
                                                      encoding:NSUTF8StringEncoding
                                                         error:nil];
        if (contents.length > 0) {
            NSArray *lines = [contents componentsSeparatedByString:@"\n"];
            NSInteger nonEmpty = 0;
            for (NSString *line in lines) {
                if (line.length > 0) nonEmpty++;
            }
            sSpinCount = (nonEmpty > 1) ? (nonEmpty - 1) : 0;
        }
    }
}

void SLSpinStoreAppend(SLSpinResult *result) {
    if (!result) return;
    SLEnsureCSVHeader();
    sSpinCount++;

    static NSDateFormatter *fmt = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        fmt = [[NSDateFormatter alloc] init];
        fmt.dateFormat = @"yyyy-MM-dd HH:mm:ss";
        fmt.locale = [[NSLocale alloc] initWithLocaleIdentifier:@"en_US_POSIX"];
    });

    NSString *ts = result.timestamp ? [fmt stringFromDate:result.timestamp] : @"";
    BOOL isTriple = (result.rawR1 == result.rawR2 && result.rawR2 == result.rawR3 && result.rawR1 != 0);

    NSString *row = [NSString stringWithFormat:
        @"%ld,%@,%ld,%ld,%ld,%@,%@,%@,%@,%ld,"
         "%lld,%@,%@,%ld,"
         "%ld,%ld,%ld,%@,%lld,"
         "%@,%@,%ld\n",
        (long)result.seq, ts,
        (long)result.rawR1, (long)result.rawR2, (long)result.rawR3,
        result.reel1 ?: @"", result.reel2 ?: @"", result.reel3 ?: @"",
        result.spinResult ?: @"", (long)result.rewardCode,
        result.coinsWon, result.coins ?: @"", result.spinsRemaining ?: @"",
        (long)result.shields,
        (long)result.accumCurrent, (long)result.accumTotal,
        (long)result.accumMissionIndex,
        result.accumRewardType ?: @"", result.accumRewardAmount,
        isTriple ? @"true" : @"false",
        result.sosSymbol ?: @"", (long)result.allTimeSpins];

    NSString *path = SLCSVPath();
    NSFileManager *fm = [NSFileManager defaultManager];

    if (![fm fileExistsAtPath:path]) {
        NSString *full = [NSString stringWithFormat:@"%@\n%@", kCSVHeader, row];
        [full writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:nil];
        return;
    }

    NSFileHandle *fh = [NSFileHandle fileHandleForWritingAtPath:path];
    if (fh) {
        [fh seekToEndOfFile];
        [fh writeData:[row dataUsingEncoding:NSUTF8StringEncoding]];
        [fh closeFile];
    }
}

NSString *SLSpinStoreCSVPath(void) {
    SLEnsureCSVHeader();
    return SLCSVPath();
}

NSInteger SLSpinStoreCount(void) {
    return sSpinCount;
}
