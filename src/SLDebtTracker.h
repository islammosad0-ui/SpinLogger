#import <Foundation/Foundation.h>

@class SLSpinResult;

typedef NS_ENUM(NSInteger, SLDebtPhase) {
    SLDebtPhaseWaiting,   // below floor — no action
    SLDebtPhaseWatch,     // above floor — paying attention
    SLDebtPhaseBetNow     // above floor + quiet zone — MAX BET
};

@interface SLDebtTrackerConfig : NSObject
@property (nonatomic, assign) NSInteger target;      // expected gap (ACC=100, SPN=87)
@property (nonatomic, assign) NSInteger floorBase;   // base floor (ACC=80, SPN=65)
@property (nonatomic, assign) NSInteger floorMin;    // absolute min floor (20)
@property (nonatomic, assign) NSInteger quietMin;    // min silence spins (3)
@property (nonatomic, assign) NSInteger quietMax;    // max silence spins (7)
@property (nonatomic, assign) NSInteger betWindow;   // max bet spins (8)
+ (instancetype)accDefaults;
+ (instancetype)spnDefaults;
@end

@interface SLDebtTracker : NSObject
@property (nonatomic, strong) SLDebtTrackerConfig *config;
@property (nonatomic, assign, readonly) NSInteger debt;
@property (nonatomic, assign, readonly) NSInteger saSpins;
@property (nonatomic, assign, readonly) NSInteger quietSpins;
@property (nonatomic, assign, readonly) BOOL inQuietZone;
@property (nonatomic, assign, readonly) BOOL quietTriggered;
@property (nonatomic, assign, readonly) NSInteger betSpinsUsed;
@property (nonatomic, assign, readonly) SLDebtPhase phase;
@property (nonatomic, strong, readonly) NSMutableArray<NSNumber *> *gapHistory;
@property (nonatomic, assign, readonly) BOOL calibrated;
@property (nonatomic, assign) NSInteger calibrationThreshold; // gaps needed (default 5)
@property (nonatomic, assign, readonly) NSInteger lastGap;
@property (nonatomic, assign) NSInteger catches;   // BET NOW when triple hit
@property (nonatomic, assign) NSInteger misses;    // triple hit outside BET NOW
- (instancetype)initWithConfig:(SLDebtTrackerConfig *)config;
- (void)onSpin:(SLSpinResult *)spin isTargetTriple:(BOOL)isTarget isOtherTriple:(BOOL)isOther;
- (NSInteger)watchPoint;
- (void)reset;
- (NSDictionary *)stateDictionary;
- (void)restoreFromDictionary:(NSDictionary *)dict;
@end
