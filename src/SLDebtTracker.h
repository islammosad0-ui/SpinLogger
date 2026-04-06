#import <Foundation/Foundation.h>

typedef NS_ENUM(NSInteger, SLDebtPhase) {
    SLDebtPhaseWaiting,   // below spin threshold — no action
    SLDebtPhaseWatch,     // above threshold but accum rate too low — watch
    SLDebtPhaseBetNow     // above threshold + rate gate met — MAX BET
};

@interface SLDebtTrackerConfig : NSObject
@property (nonatomic, assign) NSInteger spinThreshold;  // min spins before betting (ACC=130, SPN=87)
@property (nonatomic, assign) double rateGate;          // min symbol rate to trigger (ACC=0.30)
@property (nonatomic, assign) NSInteger pulseSkip;      // spins to drop to 1x after non-target triple (0=off)
+ (instancetype)accDefaults;
+ (instancetype)spnDefaults;
@end

@interface SLDebtTracker : NSObject
@property (nonatomic, strong) SLDebtTrackerConfig *config;
@property (nonatomic, assign, readonly) NSInteger saSpins;     // spins since last target triple
@property (nonatomic, assign, readonly) NSInteger saSymbols;   // target symbols seen since last triple
@property (nonatomic, assign, readonly) SLDebtPhase phase;
@property (nonatomic, assign, readonly) NSInteger pulseRemaining; // spins left in pulse skip (0=not pulsing)
- (instancetype)initWithConfig:(SLDebtTrackerConfig *)config;
- (void)onSpinWithTargetHit:(BOOL)isTarget otherTriple:(BOOL)isOther symbolCount:(NSInteger)symbols;
- (double)accumRate;  // saSymbols / saSpins (0.0 if saSpins == 0)
- (void)reset;
- (NSDictionary *)stateDictionary;
- (void)restoreFromDictionary:(NSDictionary *)dict;
@end
