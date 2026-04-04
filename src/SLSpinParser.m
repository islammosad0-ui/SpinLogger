#import "SLSpinParser.h"
#import "SLSpinStore.h"
#import "SLConstants.h"

@implementation SLSpinResult
@end

// ---------------------------------------------------------------------------
//  SLParseStrackBody — split newline-delimited JSON, extract spin events
//
//  From HAR analysis: all values in msg are STRINGS (not numbers).
//  "spin_number": "35091", "auto_spin": "false", "shields": "5", etc.
//  "village" doesn't exist — use "level" instead.
// ---------------------------------------------------------------------------
void SLParseStrackBody(NSString *body) {
    if (!body.length) return;

    NSArray<NSString *> *lines = [body componentsSeparatedByCharactersInSet:
                                  [NSCharacterSet newlineCharacterSet]];

    NSInteger parsedCount = 0;

    for (NSString *line in lines) {
        if (line.length == 0) continue;

        NSData *data = [line dataUsingEncoding:NSUTF8StringEncoding];
        if (!data) continue;

        NSError *error = nil;
        NSDictionary *json = [NSJSONSerialization JSONObjectWithData:data
                                                             options:0
                                                               error:&error];
        if (error || ![json isKindOfClass:[NSDictionary class]]) continue;

        NSString *event = json[@"event"];
        if (![event isEqualToString:@"spin"]) continue;

        NSDictionary *msg = json[@"msg"];
        if (![msg isKindOfClass:[NSDictionary class]]) continue;

        NSString *symbols = msg[@"spin_result_symbols"];
        if (!symbols) continue;  // Not a valid spin event

        NSArray<NSString *> *reels = [symbols componentsSeparatedByString:@","];

        SLSpinResult *result = [[SLSpinResult alloc] init];
        result.reel1           = (reels.count > 0) ? reels[0] : @"";
        result.reel2           = (reels.count > 1) ? reels[1] : @"";
        result.reel3           = (reels.count > 2) ? reels[2] : @"";
        result.spinResult      = msg[@"spin_result"]      ?: @"";
        result.spinNumber      = [[msg[@"spin_number"] description] integerValue];
        result.coinsWon        = [[msg[@"spin_amount_won"] description] longLongValue];
        result.betType         = msg[@"bet_type"]          ?: @"";
        // "auto_spin" is string "true"/"false"
        result.autoSpin        = [[msg[@"auto_spin"] description] isEqualToString:@"true"];
        result.coins           = [msg[@"coins"] description]  ?: @"0";
        result.spinsRemaining  = [msg[@"spins"] description]  ?: @"0";
        result.shields         = [[msg[@"shields"] description] integerValue];
        // "village" doesn't exist in strack — use "level"
        result.village         = [[msg[@"level"] description] integerValue];
        result.activePet       = msg[@"active_pet"]        ?: @"";
        result.accumBarResult  = msg[@"result"]            ?: @"";
        result.sosSymbol       = msg[@"sos_1_TA"]          ?: @"";
        result.allTimeSpins    = [[msg[@"all_time_spins"] description] integerValue];
        result.timestamp       = [NSDate date];

        SLSpinStoreAppend(result);
        parsedCount++;

        dispatch_async(dispatch_get_main_queue(), ^{
            [[NSNotificationCenter defaultCenter]
                postNotificationName:SLSpinReceivedNotification
                              object:nil
                            userInfo:@{ SLSpinDataKey: result }];
        });
    }

    if (parsedCount > 0) {
        NSLog(@"[SpinLogger] Parsed %ld spin events from strack", (long)parsedCount);
    }
}
