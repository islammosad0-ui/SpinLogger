#import "SLBetDecisionLogger.h"
#import "SLConstants.h"
#import "SLAccountID.h"

// ---------------------------------------------------------------------------
//  bet_decisions CSV — writes one row per spin with full ACC tracker state
//  for offline analysis and self-tuning.
// ---------------------------------------------------------------------------

static BOOL sHeaderEnsured = NO;
static NSString *sSessionDate = nil;

// Schema header — must stay in sync with the rule bit indices (see SLDebtTracker.m)
static NSString *const kBetDecisionsHeader =
    @"seq,timestamp,session_date,gap_idx,spin_in_gap,"
     "prev_gap_length,prev_real_triple,bet_level,bet_mult,"
     "sa_spins,sa_acc,sa_spn,acc_rate,spn_rate,slope_8,slope_10,"
     "r01_combo,r02_ideal_ra,r03_ra_t130,r04_flat_150_32,"
     "r05_sml_l120_g32,r06_sml_l120_g30,"
     "r07_sml_s100_l120_m180,r08_sml_s100_l120_m110,r09_sml_s100_l130_m130,"
     "r10_sml_s50_l130_m150,r11_sml_s50_l130_s80,"
     "r12_shield_110,r13_shield_120,r14_shield_130,r15_shield_140,"
     "r16_flat_150_37,"
     "rules_count,rules_bitmask,phase,cooldown_remaining,consec_bets,gap_bets_so_far,"
     "is_triple,triple_type,target_caught,"
     "gae_segment,gae_grand_prize,gae_last_mission,"
     "accum_mission,accum_current,accum_total,accum_pct,accum_delta";

static NSString *SLBetSessionDate(void) {
    if (!sSessionDate) {
        sSessionDate = [[NSUserDefaults standardUserDefaults] stringForKey:@"Speeder_BetDecisionsDate"];
        if (!sSessionDate) {
            NSDateFormatter *df = [[NSDateFormatter alloc] init];
            df.dateFormat = @"yyyy-MM-dd";
            df.locale = [[NSLocale alloc] initWithLocaleIdentifier:@"en_US_POSIX"];
            sSessionDate = [df stringFromDate:[NSDate date]];
            [[NSUserDefaults standardUserDefaults] setObject:sSessionDate forKey:@"Speeder_BetDecisionsDate"];
        }
    }
    return sSessionDate;
}

static NSString *SLBetCSVPath(void) {
    NSString *docs = NSSearchPathForDirectoriesInDomains(
        NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
    // Filename format: bet_decisions_{account}_{YYYY-MM-DD}.csv
    NSString *filename = [NSString stringWithFormat:@"bet_decisions_%@_%@.csv",
                          SLAccountLabel(), SLBetSessionDate()];
    return [docs stringByAppendingPathComponent:filename];
}

void SLBetDecisionLoggerInvalidateHeader(void) {
    sHeaderEnsured = NO;
}

static void SLBetEnsureHeader(void) {
    if (sHeaderEnsured) return;
    sHeaderEnsured = YES;

    NSFileManager *fm = [NSFileManager defaultManager];
    NSString *path = SLBetCSVPath();

    if (![fm fileExistsAtPath:path]) {
        NSString *headerLine = [kBetDecisionsHeader stringByAppendingString:@"\n"];
        [headerLine writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:nil];
    }
}

NSString *SLBetDecisionLoggerCSVPath(void) {
    SLBetEnsureHeader();
    return SLBetCSVPath();
}

void SLBetDecisionLoggerRotate(void) {
    NSDateFormatter *df = [[NSDateFormatter alloc] init];
    df.dateFormat = @"yyyy-MM-dd";
    df.locale = [[NSLocale alloc] initWithLocaleIdentifier:@"en_US_POSIX"];
    sSessionDate = [df stringFromDate:[NSDate date]];
    [[NSUserDefaults standardUserDefaults] setObject:sSessionDate forKey:@"Speeder_BetDecisionsDate"];
    sHeaderEnsured = NO;
    NSLog(@"[SpinLogger] bet_decisions rotated -> bet_decisions_%@_%@.csv", SLAccountLabel(), sSessionDate);
}

static NSString *PhaseString(SLDebtPhase p) {
    switch (p) {
        case SLDebtPhaseWaiting: return @"WAIT";
        case SLDebtPhaseSoon:    return @"SOON";
        case SLDebtPhaseWatch:   return @"ALERT";
        case SLDebtPhaseBetNow:  return @"BET";
        case SLDebtPhaseRest:    return @"REST";
    }
    return @"?";
}

static NSString *DecisionString(SLDebtTracker *t) {
    if (t.firingRuleCount > 0 && t.cooldownRemaining == 0) return @"BET";
    if (t.cooldownRemaining > 0) return @"SKIP_COOLDOWN";
    if (t.phase == SLDebtPhaseSoon || t.phase == SLDebtPhaseWatch) return @"SKIP_NO_RULE";
    return @"WAIT_THRESHOLD";
}

void SLBetDecisionLoggerAppend(SLSpinResult *result,
                                SLDebtTracker *t,
                                NSInteger gapIdx,
                                NSInteger spinInGap) {
    if (!result || !t) return;
    SLBetEnsureHeader();

    static NSDateFormatter *fmt = nil;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        fmt = [[NSDateFormatter alloc] init];
        fmt.dateFormat = @"yyyy-MM-dd HH:mm:ss";
        fmt.locale = [[NSLocale alloc] initWithLocaleIdentifier:@"en_US_POSIX"];
    });
    NSString *ts = result.timestamp ? [fmt stringFromDate:result.timestamp] : @"";

    // ---- Decode bitmask into per-rule binary columns ----
    // CAUSAL: use the prior-snapshot bitmask (state going INTO this spin), not the
    // post-spin bitmask. Otherwise the triple's own 3 acc symbols bump the rate past
    // the gate and we log a phantom catch on the spin we were trying to predict.
    NSUInteger bm = t.priorFiringRuleBitmask;
    int r[16];
    for (int i = 0; i < 16; i++) r[i] = (bm >> i) & 1;

    // ---- Triple detection ----
    BOOL isTriple = (result.rawR1 == result.rawR2 && result.rawR2 == result.rawR3 && result.rawR1 != 0);
    NSString *tripleType = @"";
    if (isTriple) {
        if      ([result.reel1 isEqualToString:kSLSymbolAccumulation]) tripleType = @"accumulation";
        else if ([result.reel1 isEqualToString:kSLSymbolSpins])        tripleType = @"spins";
        else if ([result.reel1 isEqualToString:kSLSymbolAttack])       tripleType = @"attack";
        else if ([result.reel1 isEqualToString:kSLSymbolSteal])        tripleType = @"steal";
        else if ([result.reel1 isEqualToString:kSLSymbolShield])       tripleType = @"shield";
    }
    BOOL isAcc = isTriple && [result.reel1 isEqualToString:kSLSymbolAccumulation];
    // CAUSAL: target_caught means "tracker was telling us to bet on the spin that just
    // landed the triple" — i.e. firing state going INTO this spin, not after the triple's
    // own symbols inflated the rate.
    BOOL targetCaught = (isAcc && t.priorFiringRuleCount > 0);

    // ---- accum_pct + delta from result ----
    double accumPct = 0.0;
    if (result.accumTotal > 0) {
        accumPct = (double)result.accumCurrent / (double)result.accumTotal * 100.0;
    }
    // Note: accum_delta is computed in SLSpinStore — we don't have direct access here.
    // We'll log 0 as a placeholder; the join with spin_history.csv via seq gives the real value.
    NSInteger accumDelta = 0;

    NSString *prevTriple = t.prevRealTriple ?: @"";
    NSString *phase = PhaseString(t.phase);
    NSString *decision = DecisionString(t);

    NSString *row = [NSString stringWithFormat:
        @"%ld,%@,%@,%ld,%ld,"
         "%ld,%@,%ld,%ld,"
         "%ld,%ld,%ld,%.4f,%.4f,%.4f,%.4f,"
         "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,"
         "%ld,0x%04lx,%@,%ld,%ld,%ld,"
         "%d,%@,%d,"
         "%@,%ld,%ld,"
         "%ld,%ld,%ld,%.2f,%ld\n",
        (long)result.seq, ts, SLBetSessionDate(), (long)gapIdx, (long)spinInGap,
        (long)t.prevGapLength, prevTriple, (long)result.betLevel, (long)result.betMultiplier,
        (long)t.saSpins, (long)t.saSymbols, (long)t.saSpnSymbols,
        [t accumRate], [t spnRate], [t slopeForWindow:8], [t slopeForWindow:10],
        r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],
        r[8],r[9],r[10],r[11],r[12],r[13],r[14],r[15],
        (long)t.priorFiringRuleCount, (unsigned long)t.priorFiringRuleBitmask,
        phase, (long)t.cooldownRemaining, (long)t.consecBets, (long)t.gapBetCount,
        isTriple ? 1 : 0, tripleType, targetCaught ? 1 : 0,
        result.gaeSegment ?: @"", (long)result.gaeGrandPrize, (long)result.gaeLastMission,
        (long)result.accumMissionIndex, (long)result.accumCurrent, (long)result.accumTotal,
        accumPct, (long)accumDelta];

    NSString *path = SLBetCSVPath();
    NSFileManager *fm = [NSFileManager defaultManager];
    if (![fm fileExistsAtPath:path]) {
        NSString *full = [NSString stringWithFormat:@"%@\n%@", kBetDecisionsHeader, row];
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
