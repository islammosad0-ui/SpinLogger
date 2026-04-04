#import <Foundation/Foundation.h>

@interface SLSpinResult : NSObject
// --- Core reel data ---
@property (nonatomic, assign) NSInteger rawR1;
@property (nonatomic, assign) NSInteger rawR2;
@property (nonatomic, assign) NSInteger rawR3;
@property (nonatomic, copy) NSString *reel1;
@property (nonatomic, copy) NSString *reel2;
@property (nonatomic, copy) NSString *reel3;
@property (nonatomic, copy) NSString *spinResult;
@property (nonatomic, assign) NSInteger rewardCode;
@property (nonatomic, assign) NSInteger seq;
@property (nonatomic, assign) NSInteger spinNumber;
@property (nonatomic, assign) long long coinsWon;
@property (nonatomic, copy) NSString *coins;
@property (nonatomic, copy) NSString *spinsRemaining;
@property (nonatomic, assign) NSInteger shields;
@property (nonatomic, assign) NSInteger maxShields;
@property (nonatomic, strong) NSDate *timestamp;

// --- Bet state (affects probability segment) ---
@property (nonatomic, assign) NSInteger betLevel;
@property (nonatomic, copy) NSString *betOptions;  // e.g. "1,2,3,15,50,400,1500,6000,20000"

// --- Main GAE accumulation bar ---
@property (nonatomic, assign) NSInteger accumCurrent;
@property (nonatomic, assign) NSInteger accumTotal;
@property (nonatomic, assign) NSInteger accumMissionIndex;
@property (nonatomic, copy) NSString *accumRewardType;
@property (nonatomic, assign) long long accumRewardAmount;
@property (nonatomic, copy) NSString *accumBarResult;

// --- Second slot reels (slot-on-slot events) ---
@property (nonatomic, copy) NSString *slot2Reel1;
@property (nonatomic, copy) NSString *slot2Reel2;
@property (nonatomic, copy) NSString *slot2Reel3;

// --- Event bar snapshots (all accumulationBarsById) ---
@property (nonatomic, copy) NSString *eventBars;  // JSON: {"barId": current/total, ...}

// --- Attack/Steal tracking ---
@property (nonatomic, copy) NSString *attackTarget;  // who was attacked (from messages)
@property (nonatomic, copy) NSString *stealTarget;   // who was raided

// --- Legacy fields (strack compat) ---
@property (nonatomic, copy) NSString *betType;
@property (nonatomic, assign) BOOL autoSpin;
@property (nonatomic, assign) NSInteger village;
@property (nonatomic, copy) NSString *activePet;
@property (nonatomic, copy) NSString *sosSymbol;
@property (nonatomic, assign) NSInteger allTimeSpins;
@end

// Parse real-time spin API response (JSON with r1/r2/r3 numeric IDs)
void SLParseSpinAPIResponse(NSData *responseData);

// Parse strack NDJSON body (legacy/backup)
void SLParseStrackBody(NSString *body);
