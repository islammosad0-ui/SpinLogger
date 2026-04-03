#import "SLSpinParser.h"
#import "SLSpinStore.h"
#import "SLConstants.h"

@implementation SLSpinResult
@end

// ---------------------------------------------------------------------------
//  SLParseStrackBody — split newline-delimited JSON, extract spin events
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
        NSDictionary *json = [NSJSONSerialization JSONObjectWithData:data
                                                             options:0
                                                               error:&error];
        if (error || ![json isKindOfClass:[NSDictionary class]]) continue;

        NSString *event = json[@"event"];
        if (![event isEqualToString:@"spin"]) continue;

        NSDictionary *msg = json[@"msg"];
        if (![msg isKindOfClass:[NSDictionary class]]) continue;

        NSString *symbols = msg[@"spin_result_symbols"];
        NSArray<NSString *> *reels = [symbols componentsSeparatedByString:@","];

        SLSpinResult *result = [[SLSpinResult alloc] init];
        result.reel1           = (reels.count > 0) ? reels[0] : @"";
        result.reel2           = (reels.count > 1) ? reels[1] : @"";
        result.reel3           = (reels.count > 2) ? reels[2] : @"";
        result.spinResult      = msg[@"spin_result"]      ?: @"";
        result.spinNumber      = [msg[@"spin_number"]      integerValue];
        result.coinsWon        = [msg[@"spin_amount_won"]  longLongValue];
        result.betType         = msg[@"bet_type"]          ?: @"";
        result.autoSpin        = [msg[@"auto_spin"]        boolValue];
        result.coins           = [msg[@"coins"]            description] ?: @"0";
        result.spinsRemaining  = [msg[@"spins"]            description] ?: @"0";
        result.shields         = [msg[@"shields"]          integerValue];
        result.village         = [msg[@"village"]          integerValue];
        result.activePet       = msg[@"active_pet"]        ?: @"";
        result.accumBarResult  = msg[@"result"]            ?: @"";
        result.sosSymbol       = msg[@"sos_1_TA"]          ?: @"";
        result.allTimeSpins    = [msg[@"all_time_spins"]   integerValue];
        result.timestamp       = [NSDate date];

        SLSpinStoreAppend(result);

        dispatch_async(dispatch_get_main_queue(), ^{
            [[NSNotificationCenter defaultCenter]
                postNotificationName:SLSpinReceivedNotification
                              object:nil
                            userInfo:@{ SLSpinDataKey: result }];
        });

        NSLog(@"[SpinLogger] Spin #%ld: [%@, %@, %@] -> %@",
              (long)result.spinNumber,
              result.reel1, result.reel2, result.reel3,
              result.spinResult);
    }
}
