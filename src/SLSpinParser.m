#import "SLSpinParser.h"
#import "SLSpinStore.h"
#import "SLIdxStrategy.h"
#import "SLConstants.h"
#import "SLV4Features.h"
#import "SLV4Panel.h"

@implementation SLSpinResult
@end

// ---------------------------------------------------------------------------
//  Symbol ID mapping — from HAR cross-reference:
//  Spin API returns numeric IDs (r1, r2, r3)
//  Strack uses string names (spin_result_symbols)
//
//  ID → Symbol mapping (verified from HAR data):
//    1 = coin        (3x → reward=1, pay=250000)
//    2 = goldSack    (appears in 150k combos)
//    3 = attack      (3x → reward=2, pay=0)
//    4 = steal/pig   (3x → reward=4)
//    5 = shield      (3x → reward=3, pay=1)
//    6 = spins       (rare)
//    30 = accumulation (special symbol)
//
//  Reward types: 1=gold, 2=attack, 3=shield, 4=steal, 5=spins
// ---------------------------------------------------------------------------

static NSString *SLSymbolName(NSInteger symbolId) {
    switch (symbolId) {
        case 1:  return kSLSymbolCoin;
        case 2:  return kSLSymbolGoldSack;
        case 3:  return kSLSymbolAttack;
        case 4:  return kSLSymbolSteal;
        case 5:  return kSLSymbolShield;
        case 6:  return kSLSymbolSpins;
        case 30: return kSLSymbolAccumulation;
        default: return kSLSymbolCoin;
    }
}

static NSString *SLRewardName(NSInteger reward) {
    switch (reward) {
        case 1:  return kSLOutcomeGold;
        case 2:  return kSLOutcomeAttack;
        case 3:  return kSLOutcomeShield;
        case 4:  return kSLOutcomeSteal;
        case 5:  return kSLOutcomeSpins;
        default: return kSLOutcomeGold;
    }
}

// ---------------------------------------------------------------------------
//  SLParseSpinAPIResponse — parse real-time spin API JSON response
//  This is called INSTANTLY per spin (not batched like strack)
// ---------------------------------------------------------------------------
void SLParseSpinAPIResponse(NSData *responseData) {
    SLParseSpinAPIResponseWithBet(responseData, 0);
}

void SLParseSpinAPIResponseWithBet(NSData *responseData, NSInteger betMultiplier) {
    if (!responseData || responseData.length == 0) return;

    NSError *error = nil;
    NSDictionary *json = [NSJSONSerialization JSONObjectWithData:responseData
                                                         options:0
                                                           error:&error];
    if (error || ![json isKindOfClass:[NSDictionary class]]) return;

    // Must have r1, r2, r3 fields
    NSNumber *r1num = json[@"r1"];
    NSNumber *r2num = json[@"r2"];
    NSNumber *r3num = json[@"r3"];
    if (!r1num || !r2num || !r3num) return;

    NSInteger r1 = r1num.integerValue;
    NSInteger r2 = r2num.integerValue;
    NSInteger r3 = r3num.integerValue;

    SLSpinResult *result = [[SLSpinResult alloc] init];

    // --- Core reels ---
    result.rawR1 = r1;
    result.rawR2 = r2;
    result.rawR3 = r3;
    result.reel1 = SLSymbolName(r1);
    result.reel2 = SLSymbolName(r2);
    result.reel3 = SLSymbolName(r3);
    result.rewardCode = [json[@"reward"] integerValue];
    result.spinResult = SLRewardName(result.rewardCode);
    result.seq = [json[@"seq"] integerValue];
    result.spinNumber = result.seq;
    result.coinsWon = [json[@"pay"] longLongValue];
    result.coins = [json[@"coins"] description] ?: @"0";
    result.spinsRemaining = [json[@"spins"] description] ?: @"0";
    result.shields = [json[@"shields"] integerValue];
    result.maxShields = [json[@"maxShields"] integerValue];
    result.timestamp = [NSDate date];
    result.betMultiplier = betMultiplier;

    // --- Bet state (probability segments change by bet level) ---
    // betMultiplier passed in is the actual bet value from request body (e.g. 1, 2, 3, 15, 50...)
    NSDictionary *superBet = json[@"superBet"];
    if ([superBet isKindOfClass:[NSDictionary class]]) {
        result.betLevel = [superBet[@"betLevel"] integerValue];
        NSArray *opts = superBet[@"betOptions"];
        if ([opts isKindOfClass:[NSArray class]]) {
            result.betOptions = [opts componentsJoinedByString:@","];
        }
    }

    // --- Main GAE accumulation bar ---
    NSDictionary *accum = json[@"accumulation"];
    if ([accum isKindOfClass:[NSDictionary class]]) {
        result.accumCurrent      = [accum[@"currentAmount"] integerValue];
        result.accumTotal        = [accum[@"totalAmount"] integerValue];
        result.accumMissionIndex = [accum[@"missionIndex"] integerValue];
        result.accumBarResult    = [NSString stringWithFormat:@"%ld/%ld",
                                    (long)result.accumCurrent, (long)result.accumTotal];

        NSDictionary *accumReward = accum[@"reward"];
        if ([accumReward isKindOfClass:[NSDictionary class]]) {
            for (NSString *key in accumReward) {
                result.accumRewardType   = key;
                result.accumRewardAmount = [accumReward[key] longLongValue];
                break;
            }
        }

        // GAE list identification — segment encodes list tier, lastMission fingerprints the list
        NSDictionary *bonus = accum[@"bonus"];
        if ([bonus isKindOfClass:[NSDictionary class]]) {
            result.gaeSegment = [bonus[@"segment"] description];
        }
        NSDictionary *gaeMap = accum[@"gaeMapData"];
        if ([gaeMap isKindOfClass:[NSDictionary class]]) {
            NSInteger lastIdx = [gaeMap[@"lastMissionIndex"] integerValue];
            result.gaeLastMission = lastIdx;
            NSDictionary *missions = gaeMap[@"missions"];
            if ([missions isKindOfClass:[NSDictionary class]]) {
                NSDictionary *lastMission = missions[[NSString stringWithFormat:@"%ld", (long)lastIdx]];
                if ([lastMission isKindOfClass:[NSDictionary class]]) {
                    NSDictionary *reward = lastMission[@"reward"];
                    if ([reward isKindOfClass:[NSDictionary class]]) {
                        result.gaeGrandPrize = [reward[@"spins"] integerValue];
                    }
                }
            }
        }
    }

    // --- Second slot reels (slot-on-slot: Dove, Cookie, etc.) ---
    NSDictionary *addSlots = json[@"additionalSlots"];
    if ([addSlots isKindOfClass:[NSDictionary class]]) {
        NSDictionary *secondSlot = addSlots[@"second_slot"];
        if ([secondSlot isKindOfClass:[NSDictionary class]]) {
            NSArray *reels = secondSlot[@"reels"];
            if ([reels isKindOfClass:[NSArray class]]) {
                result.slot2Reel1 = (reels.count > 0) ? [reels[0] description] : @"";
                result.slot2Reel2 = (reels.count > 1) ? [reels[1] description] : @"";
                result.slot2Reel3 = (reels.count > 2) ? [reels[2] description] : @"";
            }
        }
    }

    // --- All event bar snapshots (accumulationBarsById) ---
    // Captures any active event bars: Potion Rush, Merge, Expedition, etc.
    // Collects from both top-level AND serializedEvents
    NSMutableDictionary *barSnapshot = [NSMutableDictionary dictionary];
    NSMutableDictionary *barMissions = [NSMutableDictionary dictionary];
    NSMutableDictionary *barAmounts  = [NSMutableDictionary dictionary];

    // Helper block: process a bars dictionary from any source
    void (^processBars)(NSDictionary *) = ^(NSDictionary *bars) {
        for (NSString *barId in bars) {
            NSDictionary *bar = bars[barId];
            if (![bar isKindOfClass:[NSDictionary class]]) continue;
            NSInteger cur = [bar[@"currentAmount"] integerValue];
            NSInteger tot = [bar[@"totalAmount"] integerValue];
            NSInteger mis = [bar[@"missionIndex"] integerValue];
            NSString *shortId = barId.length > 8 ? [barId substringToIndex:8] : barId;
            barSnapshot[shortId] = [NSString stringWithFormat:@"%ld/%ld@m%ld",
                                    (long)cur, (long)tot, (long)mis];
            // Track Potion Rush / Expedition bars for the 🧪 tile
            NSDictionary *rewards = bar[@"rewards"];
            if ([rewards isKindOfClass:[NSDictionary class]] &&
                (rewards[@"progressive_reward_pr_ec"] || rewards[@"generic_currency_expedition_nl_currency"])) {
                barMissions[shortId] = @(mis);
                barAmounts[shortId]  = @(cur);
            }
        }
    };

    // Top-level bars
    NSDictionary *barsById = json[@"accumulationBarsById"];
    if ([barsById isKindOfClass:[NSDictionary class]] && barsById.count > 0) {
        processBars(barsById);
    }

    // serializedEvents bars (slot-on-slot and others)
    NSDictionary *serialized = json[@"serializedEvents"];
    if ([serialized isKindOfClass:[NSDictionary class]]) {
        for (NSDictionary *evt in serialized.allValues) {
            if (![evt isKindOfClass:[NSDictionary class]]) continue;
            NSArray *common = evt[@"commonResponses"];
            if (![common isKindOfClass:[NSArray class]]) continue;
            for (NSDictionary *resp in common) {
                if (![resp isKindOfClass:[NSDictionary class]]) continue;
                NSDictionary *payload = resp[@"payload"];
                if (![payload isKindOfClass:[NSDictionary class]]) continue;
                NSDictionary *innerBars = payload[@"accumulationBarsById"];
                if ([innerBars isKindOfClass:[NSDictionary class]]) {
                    processBars(innerBars);
                }
            }
        }
    }

    if (barSnapshot.count > 0) {
        NSData *barJSON = [NSJSONSerialization dataWithJSONObject:barSnapshot options:0 error:nil];
        if (barJSON) {
            result.eventBars = [[NSString alloc] initWithData:barJSON encoding:NSUTF8StringEncoding];
        }
    }
    result.eventBarMissions = [barMissions copy];
    result.eventBarAmounts  = [barAmounts copy];

    // Feed V4 features at parse-time, NOT at settle-time. The IL2CPP scanner
    // settle path can drop spins under Speeder (Time.timeScale > 1) so v4's
    // cycle counter falls behind the game's actual count. The server JSON
    // arrives once per real spin, and v4's feature set (FEATURE_COLS_BASE in
    // tail_risk_v4_hazard_plus.py) uses only reel SYMBOLS + counters — none
    // of the IL2CPP idx fields — so this is data-equivalent and lag-free.
    [[SLV4Features shared] feedSpin:result];
    [[NSNotificationCenter defaultCenter] postNotificationName:SLV4PanelRefreshNotification object:nil];

    // Defer CSV write — the strategy engine holds the result until the
    // memory scanner settles and provides strip idx values.
    // Queue on main thread so the flush timer works (NSTimer needs a run loop).
    dispatch_async(dispatch_get_main_queue(), ^{
        [[SLIdxStrategy shared] queueResult:result];
    });

    NSLog(@"[SpinLogger] SPIN seq=%ld: r[%ld,%ld,%ld] -> %@ | bet=%ld shields=%ld/%ld accum=%ld/%ld slot2=[%@,%@,%@]",
          (long)result.seq,
          (long)result.rawR1, (long)result.rawR2, (long)result.rawR3,
          result.spinResult, (long)result.betLevel,
          (long)result.shields, (long)result.maxShields,
          (long)result.accumCurrent, (long)result.accumTotal,
          result.slot2Reel1 ?: @"", result.slot2Reel2 ?: @"", result.slot2Reel3 ?: @"");

    // Notify on main queue (UI updates — counters, overlays, etc.)
    dispatch_async(dispatch_get_main_queue(), ^{
        [[NSNotificationCenter defaultCenter]
            postNotificationName:SLSpinReceivedNotification
                          object:nil
                        userInfo:@{ SLSpinDataKey: result }];
    });
}

// ---------------------------------------------------------------------------
//  cm_balance from strack spin events
// ---------------------------------------------------------------------------
static long long sCmBalance = 0;

long long SLLatestCmBalance(void) {
    return sCmBalance;
}

void SLParseStrackForBalance(NSData *body) {
    if (!body || body.length == 0) return;

    // strack bodies are NDJSON — may arrive gzipped despite HAR showing plain text.
    NSData *plain = nil;

    // Check for gzip magic bytes (0x1f 0x8b)
    if (body.length >= 2) {
        const uint8_t *bytes = body.bytes;
        if (bytes[0] == 0x1f && bytes[1] == 0x8b) {
            // Decompress with NSData+zlib (available via compression framework)
            // Use shell-level zlib: NSInputStream → inflate. Simpler: try NSJSONSerialization
            // directly on the raw bytes — if it fails, it's gzipped and we skip (rare path).
            plain = nil;  // will fall through to raw attempt
        } else {
            plain = body;
        }
    }
    if (!plain) {
        // Try decompressing — use the simpler approach of converting to string
        // (strack in-app is sent as plain NDJSON; gzip is done at HTTP layer
        //  which NSURLProtocol already decompresses for us)
        plain = body;
    }

    NSString *text = [[NSString alloc] initWithData:plain encoding:NSUTF8StringEncoding];
    if (!text.length) return;

    for (NSString *line in [text componentsSeparatedByCharactersInSet:
                            [NSCharacterSet newlineCharacterSet]]) {
        if (line.length == 0) continue;

        NSData *lineData = [line dataUsingEncoding:NSUTF8StringEncoding];
        if (!lineData) continue;

        NSDictionary *json = [NSJSONSerialization JSONObjectWithData:lineData options:0 error:nil];
        if (![json isKindOfClass:[NSDictionary class]]) continue;
        if (![[json[@"event"] description] isEqualToString:@"spin"]) continue;

        NSDictionary *msg = json[@"msg"];
        if (![msg isKindOfClass:[NSDictionary class]]) continue;

        id bal = msg[@"cm_balance"];
        if (bal) {
            long long v = [[bal description] longLongValue];
            if (v > 0) {
                sCmBalance = v;
            }
        }
    }
}

// ---------------------------------------------------------------------------
//  testSegments + ProfileName from client_error request body
// ---------------------------------------------------------------------------
static NSString *sProfileName = nil;
static NSString *sSlotProbSeg = nil;

NSString *SLSessionProfileName(void) {
    return sProfileName ?: @"";
}

NSString *SLSessionSlotProbSeg(void) {
    return sSlotProbSeg ?: @"";
}

void SLParseClientErrorForSegments(NSData *body) {
    if (!body || body.length == 0) return;

    NSString *text = [[NSString alloc] initWithData:body encoding:NSUTF8StringEncoding];
    if (!text.length) return;

    // URL-decode the form body
    NSString *decoded = [text stringByRemovingPercentEncoding];
    if (!decoded) decoded = text;

    // Extract ProfileName
    for (NSString *pair in [decoded componentsSeparatedByString:@"&"]) {
        if ([pair hasPrefix:@"ProfileName="]) {
            NSString *val = [pair substringFromIndex:12];
            if (val.length > 0) {
                sProfileName = [val copy];
                NSLog(@"[SpinLogger] Session profile: %@", sProfileName);
            }
        }
    }

    // Extract testSegments — look for core_slot_prob specifically
    for (NSString *pair in [decoded componentsSeparatedByString:@"&"]) {
        if (![pair containsString:@"testSegments"]) continue;
        // Format: testSegments[N]=segment_tag_xxx
        NSRange eq = [pair rangeOfString:@"="];
        if (eq.location == NSNotFound) continue;
        NSString *val = [pair substringFromIndex:eq.location + 1];

        if ([val containsString:@"core_slot_prob"]) {
            // e.g. "segment_tag_core_slot_prob_nu_29_06_var_a" → extract variant
            sSlotProbSeg = [val copy];
            NSLog(@"[SpinLogger] Slot prob segment: %@", sSlotProbSeg);
        }
    }
}

// ---------------------------------------------------------------------------
//  SLParseStrackBody — legacy strack NDJSON parser (backup)
// ---------------------------------------------------------------------------
void SLParseStrackBody(NSString *body) {
    if (!body.length) return;

    NSArray<NSString *> *lines = [body componentsSeparatedByCharactersInSet:
                                  [NSCharacterSet newlineCharacterSet]];

    for (NSString *line in lines) {
        if (line.length == 0) continue;

        NSData *data = [line dataUsingEncoding:NSUTF8StringEncoding];
        if (!data) continue;

        NSError *error = nil;
        NSDictionary *json = [NSJSONSerialization JSONObjectWithData:data options:0 error:&error];
        if (error || ![json isKindOfClass:[NSDictionary class]]) continue;
        if (![[json[@"event"] description] isEqualToString:@"spin"]) continue;

        NSDictionary *msg = json[@"msg"];
        if (![msg isKindOfClass:[NSDictionary class]]) continue;

        NSString *symbols = msg[@"spin_result_symbols"];
        if (!symbols) continue;
        NSArray<NSString *> *reels = [symbols componentsSeparatedByString:@","];

        SLSpinResult *result = [[SLSpinResult alloc] init];
        result.reel1 = (reels.count > 0) ? reels[0] : @"";
        result.reel2 = (reels.count > 1) ? reels[1] : @"";
        result.reel3 = (reels.count > 2) ? reels[2] : @"";
        result.spinResult = msg[@"spin_result"] ?: @"";
        result.spinNumber = [[msg[@"spin_number"] description] integerValue];
        result.coinsWon = [[msg[@"spin_amount_won"] description] longLongValue];
        result.coins = [msg[@"coins"] description] ?: @"0";
        result.spinsRemaining = [msg[@"spins"] description] ?: @"0";
        result.shields = [[msg[@"shields"] description] integerValue];
        result.village = [[msg[@"level"] description] integerValue];
        result.timestamp = [NSDate date];

        SLSpinStoreAppend(result);

        dispatch_async(dispatch_get_main_queue(), ^{
            [[NSNotificationCenter defaultCenter]
                postNotificationName:SLSpinReceivedNotification
                              object:nil
                            userInfo:@{ SLSpinDataKey: result }];
        });
    }
}
