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
@end

void SLParseStrackBody(NSString *body);
