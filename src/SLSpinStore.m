#import "SLSpinStore.h"
#import "SLConstants.h"

static NSInteger sSpinCount = 0;
static BOOL sHeaderEnsured = NO;

static NSString *const kCSVHeader =
    @"spin_number,timestamp,reel_1,reel_2,reel_3,spin_result,coins_won,"
     "bet_type,auto_spin,coins,spins_remaining,shields,village,active_pet,"
     "accum_bar_result,sos_symbol,all_time_spins";

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
    NSString *quotedAccum = [NSString stringWithFormat:@"\"%@\"",
        [result.accumBarResult ?: @""
            stringByReplacingOccurrencesOfString:@"\"" withString:@"\"\""]];

    NSString *row = [NSString stringWithFormat:
        @"%ld,%@,%@,%@,%@,%@,%lld,%@,%@,%@,%@,%ld,%ld,%@,%@,%@,%ld\n",
        (long)result.spinNumber, ts,
        result.reel1 ?: @"", result.reel2 ?: @"", result.reel3 ?: @"",
        result.spinResult ?: @"", result.coinsWon,
        result.betType ?: @"", result.autoSpin ? @"true" : @"false",
        result.coins ?: @"", result.spinsRemaining ?: @"",
        (long)result.shields, (long)result.village,
        result.activePet ?: @"", quotedAccum,
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
