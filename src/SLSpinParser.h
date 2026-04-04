#import <Foundation/Foundation.h>

@interface SLSpinResult : NSObject
@property (nonatomic, copy) NSString *reel1;
@property (nonatomic, copy) NSString *reel2;
@property (nonatomic, copy) NSString *reel3;
@property (nonatomic, copy) NSString *spinResult;
@property (nonatomic, assign) NSInteger spinNumber;
@property (nonatomic, assign) long long coinsWon;
@property (nonatomic, copy) NSString *betType;
@property (nonatomic, assign) BOOL autoSpin;
@property (nonatomic, copy) NSString *coins;
@property (nonatomic, copy) NSString *spinsRemaining;
@property (nonatomic, assign) NSInteger shields;
@property (nonatomic, assign) NSInteger village;
@property (nonatomic, copy) NSString *activePet;
@property (nonatomic, copy) NSString *accumBarResult;
@property (nonatomic, copy) NSString *sosSymbol;
@property (nonatomic, assign) NSInteger allTimeSpins;
@property (nonatomic, strong) NSDate *timestamp;
// Raw numeric IDs from spin API
@property (nonatomic, assign) NSInteger r1;
@property (nonatomic, assign) NSInteger r2;
@property (nonatomic, assign) NSInteger r3;
@property (nonatomic, assign) NSInteger reward;
@end

// Parse real-time spin API response (JSON with r1/r2/r3 numeric IDs)
void SLParseSpinAPIResponse(NSData *responseData);

// Parse strack NDJSON body (legacy/backup)
void SLParseStrackBody(NSString *body);
