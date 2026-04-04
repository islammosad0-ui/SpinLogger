#import "SLSpinStore.h"
#import "SLConstants.h"

static NSInteger sSpinCount = 0;
static BOOL sHeaderEnsured = NO;

// ---------------------------------------------------------------------------
//  Running counters — reset on triple accumulation (sa_) or triple spins (ss_)
//  These track how many of each event happened SINCE the last trigger.
// ---------------------------------------------------------------------------
// Since last 3x accumulation (30,30,30)
static NSInteger sa_spins = 0;
static NSInteger sa_atk = 0;      // total attack symbols (includes triples)
static NSInteger sa_stl = 0;      // total steal symbols
static NSInteger sa_shd = 0;      // total shield symbols
static NSInteger sa_spn = 0;      // total spins symbols (r=6)
static NSInteger sa_acc = 0;      // total accumulation symbols (r=30)
static NSInteger sa_3x_atk = 0;   // how many triple attacks
static NSInteger sa_3x_stl = 0;   // how many triple steals
static NSInteger sa_3x_shd = 0;   // how many triple shields

// Since last 3x spins (6,6,6)
static NSInteger ss_spins = 0;
static NSInteger ss_atk = 0;
static NSInteger ss_stl = 0;
static NSInteger ss_shd = 0;
static NSInteger ss_spn = 0;
static NSInteger ss_acc = 0;
static NSInteger ss_3x_atk = 0;
static NSInteger ss_3x_stl = 0;
static NSInteger ss_3x_shd = 0;

// GAE delta tracking — detect mission boundary changes
static NSInteger sPrevAccumCurrent = -1;
static NSInteger sPrevAccumMission = -1;

static NSString *const kCSVHeader =
    @"seq,timestamp,r1,r2,r3,reel_1,reel_2,reel_3,spin_result,reward_code,is_triple,"
     "coins_won,coins,spins_remaining,"
     "shields,max_shields,bet_multiplier,bet_level,"
     "accum_current,accum_total,accum_mission,accum_delta,accum_pct,"
     "slot2_r1,slot2_r2,slot2_r3,"
     "event_bars,"
     "sa_spins,sa_atk,sa_stl,sa_shd,sa_spn,sa_acc,sa_3x_atk,sa_3x_stl,sa_3x_shd,"
     "ss_spins,ss_atk,ss_stl,ss_shd,ss_spn,ss_acc,ss_3x_atk,ss_3x_stl,ss_3x_shd";

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

    // --- Count symbol appearances on this spin ---
    NSInteger r1 = result.rawR1;
    NSInteger r2 = result.rawR2;
    NSInteger r3 = result.rawR3;
    NSInteger atkCount = (r1 == 3) + (r2 == 3) + (r3 == 3);
    NSInteger stlCount = (r1 == 4) + (r2 == 4) + (r3 == 4);
    NSInteger shdCount = (r1 == 5) + (r2 == 5) + (r3 == 5);
    NSInteger spnCount = (r1 == 6) + (r2 == 6) + (r3 == 6);
    NSInteger accCount = (r1 == 30) + (r2 == 30) + (r3 == 30);

    // --- Update BOTH sets of running counters ---
    sa_spins++;  ss_spins++;
    sa_atk += atkCount;  ss_atk += atkCount;
    sa_stl += stlCount;  ss_stl += stlCount;
    sa_shd += shdCount;  ss_shd += shdCount;
    sa_spn += spnCount;  ss_spn += spnCount;
    sa_acc += accCount;  ss_acc += accCount;
    if (atkCount == 3) { sa_3x_atk++; ss_3x_atk++; }
    if (stlCount == 3) { sa_3x_stl++; ss_3x_stl++; }
    if (shdCount == 3) { sa_3x_shd++; ss_3x_shd++; }

    // --- GAE delta and percentage ---
    NSInteger accumDelta = 0;
    if (sPrevAccumCurrent >= 0 && result.accumCurrent >= sPrevAccumCurrent) {
        accumDelta = result.accumCurrent - sPrevAccumCurrent;
        // If mission changed (bar reset), delta doesn't make sense
        if (sPrevAccumMission >= 0 && result.accumMissionIndex != sPrevAccumMission) {
            accumDelta = 0;  // mission boundary — bar reset
        }
    }
    sPrevAccumCurrent = result.accumCurrent;
    sPrevAccumMission = result.accumMissionIndex;

    // Percentage of current mission completed (0.0 - 100.0)
    double accumPct = 0.0;
    if (result.accumTotal > 0) {
        accumPct = (double)result.accumCurrent / (double)result.accumTotal * 100.0;
    }

    // Quote event_bars JSON (contains commas)
    NSString *quotedBars = @"";
    if (result.eventBars.length > 0) {
        quotedBars = [NSString stringWithFormat:@"\"%@\"",
            [result.eventBars stringByReplacingOccurrencesOfString:@"\"" withString:@"\"\""]];
    }

    NSString *row = [NSString stringWithFormat:
        @"%ld,%@,%ld,%ld,%ld,%@,%@,%@,%@,%ld,%@,"
         "%lld,%@,%@,"
         "%ld,%ld,%ld,%ld,"
         "%ld,%ld,%ld,%ld,%.1f,"
         "%@,%@,%@,"
         "%@,"
         "%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,"
         "%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld,%ld\n",
        (long)result.seq, ts,
        (long)r1, (long)r2, (long)r3,
        result.reel1 ?: @"", result.reel2 ?: @"", result.reel3 ?: @"",
        result.spinResult ?: @"", (long)result.rewardCode,
        isTriple ? @"true" : @"false",
        result.coinsWon, result.coins ?: @"", result.spinsRemaining ?: @"",
        (long)result.shields, (long)result.maxShields, (long)result.betMultiplier, (long)result.betLevel,
        (long)result.accumCurrent, (long)result.accumTotal, (long)result.accumMissionIndex,
        (long)accumDelta, accumPct,
        result.slot2Reel1 ?: @"", result.slot2Reel2 ?: @"", result.slot2Reel3 ?: @"",
        quotedBars,
        // Since last 3x accumulation
        (long)sa_spins, (long)sa_atk, (long)sa_stl, (long)sa_shd,
        (long)sa_spn, (long)sa_acc, (long)sa_3x_atk, (long)sa_3x_stl, (long)sa_3x_shd,
        // Since last 3x spins
        (long)ss_spins, (long)ss_atk, (long)ss_stl, (long)ss_shd,
        (long)ss_spn, (long)ss_acc, (long)ss_3x_atk, (long)ss_3x_stl, (long)ss_3x_shd];

    // --- Reset counters AFTER writing (so the triple row shows the final count) ---
    if (isTriple && r1 == 30) {
        sa_spins = 0; sa_atk = 0; sa_stl = 0; sa_shd = 0;
        sa_spn = 0; sa_acc = 0; sa_3x_atk = 0; sa_3x_stl = 0; sa_3x_shd = 0;
    }
    if (isTriple && r1 == 6) {
        ss_spins = 0; ss_atk = 0; ss_stl = 0; ss_shd = 0;
        ss_spn = 0; ss_acc = 0; ss_3x_atk = 0; ss_3x_stl = 0; ss_3x_shd = 0;
    }

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
