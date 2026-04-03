#import "SLSpinStore.h"
#import "SLConstants.h"

// ---------------------------------------------------------------------------
//  Static state
// ---------------------------------------------------------------------------
static NSInteger sSpinCount = 0;
static BOOL sHeaderEnsured = NO;

// ---------------------------------------------------------------------------
//  CSV header — one row, all 17 columns
// ---------------------------------------------------------------------------
static NSString *const kCSVHeader =
    @"spin_number,timestamp,reel_1,reel_2,reel_3,spin_result,coins_won,"
     "bet_type,auto_spin,coins,spins_remaining,shields,village,active_pet,"
     "accum_bar_result,sos_symbol,all_time_spins";

// ---------------------------------------------------------------------------
//  SLCSVPath — Documents/spin_history.csv
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
//  SLEnsureCSVHeader — create file with header if missing; count rows if present
// ---------------------------------------------------------------------------
static void SLEnsureCSVHeader(void) {
    if (sHeaderEnsured) return;
    sHeaderEnsured = YES;

    NSFileManager *fm = [NSFileManager defaultManager];
    NSString *path = SLCSVPath();

    if (![fm fileExistsAtPath:path]) {
        // Create brand-new file with just the header line
        NSString *headerLine = [kCSVHeader stringByAppendingString:@"\n"];
        [headerLine writeToFile:path
                     atomically:YES
                       encoding:NSUTF8StringEncoding
                          error:nil];
        sSpinCount = 0;
    } else {
        // File already exists — count data rows (total lines minus the header)
        NSString *contents = [NSString stringWithContentsOfFile:path
                                                      encoding:NSUTF8StringEncoding
                                                         error:nil];
        if (contents.length > 0) {
            NSArray *lines = [contents componentsSeparatedByString:@"\n"];
            NSInteger nonEmpty = 0;
            for (NSString *line in lines) {
                if (line.length > 0) nonEmpty++;
            }
            // Subtract 1 for the header row
            sSpinCount = (nonEmpty > 1) ? (nonEmpty - 1) : 0;
        } else {
            sSpinCount = 0;
        }
    }
}

// ---------------------------------------------------------------------------
//  SLSpinStoreAppend — format one CSV row and append to file
// ---------------------------------------------------------------------------
void SLSpinStoreAppend(SLSpinResult *result) {
    if (!result) return;

    SLEnsureCSVHeader();
    sSpinCount++;

    // Date formatter (reused via static)
    static NSDateFormatter *fmt = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        fmt = [[NSDateFormatter alloc] init];
        fmt.dateFormat = @"yyyy-MM-dd HH:mm:ss";
        fmt.locale = [[NSLocale alloc] initWithLocaleIdentifier:@"en_US_POSIX"];
    });

    NSString *ts = result.timestamp ? [fmt stringFromDate:result.timestamp] : @"";

    // Quote accum_bar_result because it may contain commas
    NSString *quotedAccum = [NSString stringWithFormat:@"\"%@\"",
        [result.accumBarResult ?: @""
            stringByReplacingOccurrencesOfString:@"\"" withString:@"\"\""]];

    NSString *row = [NSString stringWithFormat:
        @"%ld,%@,%@,%@,%@,%@,%lld,%@,%@,%@,%@,%ld,%ld,%@,%@,%@,%ld\n",
        (long)result.spinNumber,
        ts,
        result.reel1        ?: @"",
        result.reel2        ?: @"",
        result.reel3        ?: @"",
        result.spinResult   ?: @"",
        result.coinsWon,
        result.betType      ?: @"",
        result.autoSpin ? @"true" : @"false",
        result.coins        ?: @"",
        result.spinsRemaining ?: @"",
        (long)result.shields,
        (long)result.village,
        result.activePet    ?: @"",
        quotedAccum,
        result.sosSymbol    ?: @"",
        (long)result.allTimeSpins];

    NSString *path = SLCSVPath();
    NSFileManager *fm = [NSFileManager defaultManager];

    // If the file was deleted out from under us, recreate with header + row
    if (![fm fileExistsAtPath:path]) {
        NSString *full = [NSString stringWithFormat:@"%@\n%@", kCSVHeader, row];
        [full writeToFile:path
               atomically:YES
                 encoding:NSUTF8StringEncoding
                    error:nil];
        return;
    }

    // Append via NSFileHandle — seekToEndOfFile + writeData
    NSFileHandle *fh = [NSFileHandle fileHandleForWritingAtPath:path];
    if (fh) {
        [fh seekToEndOfFile];
        [fh writeData:[row dataUsingEncoding:NSUTF8StringEncoding]];
        [fh closeFile];
    }
}

// ---------------------------------------------------------------------------
//  SLSpinStoreCSVPath — public accessor; ensures header on first call
// ---------------------------------------------------------------------------
NSString *SLSpinStoreCSVPath(void) {
    SLEnsureCSVHeader();
    return SLCSVPath();
}

// ---------------------------------------------------------------------------
//  SLSpinStoreCount — returns total spins appended so far
// ---------------------------------------------------------------------------
NSInteger SLSpinStoreCount(void) {
    return sSpinCount;
}
