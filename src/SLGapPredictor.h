#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLGapPredictor — VT gap timing predictor
//
//  Tracks spins since last VT, stores last 2 gap lengths, and predicts
//  the window where the next VT will likely land using empirical lookup
//  tables built from 54,770 spins / 1,110 VTs across 3 accounts.
//
//  Core finding: gaps alternate (lag-1 autocorrelation r = -0.258).
//  After a long drought the next gap is short, and vice versa.
//  CV = 0.80 (more regular than random, which would be 1.0).
// ---------------------------------------------------------------------------

/// Action recommendation based on gap position vs prediction
typedef NS_ENUM(NSInteger, SLGapAction) {
    SLGapActionBetLow = 0,   // Too early, VT unlikely
    SLGapActionWatch,         // Approaching window
    SLGapActionBetHigh,       // Inside predicted window
    SLGapActionAllIn,         // Past P75, overdue
    SLGapActionOverdue        // Way past expected, keep pushing
};

/// Prediction snapshot for current state
typedef struct {
    NSInteger gapPos;         // Spins since last VT
    NSInteger prevGap;        // Previous gap length (-1 if unknown)
    NSInteger prevPrevGap;    // Gap before that (-1 if unknown)
    NSInteger predMedian;     // Predicted median gap
    NSInteger predP25;        // 25th percentile
    NSInteger predP75;        // 75th percentile
    NSInteger predP10;        // 10th percentile
    NSInteger predP90;        // 90th percentile
    NSInteger hotLo;          // Best 10-spin window start
    NSInteger hotHi;          // Best 10-spin window end
    CGFloat   progress;       // gapPos / predP75 (0.0 to 1.0+)
    CGFloat   hazardLift;     // Current hazard rate vs base (1.0 = normal)
    SLGapAction action;       // Recommended action
} SLGapPrediction;

@interface SLGapPredictor : NSObject

+ (instancetype)shared;

/// Call after every spin settles. isVT = YES if this spin was ACC or SPN triple.
- (void)recordSpinIsVT:(BOOL)isVT;

/// Current prediction snapshot (read after recordSpin)
@property (nonatomic, readonly) SLGapPrediction prediction;

/// Total VTs seen this session
@property (nonatomic, readonly) NSInteger vtCount;

/// Short string for HUD display: "GAP 23/41 >> HIGH"
@property (nonatomic, readonly, copy) NSString *displayString;

/// Action color for HUD
@property (nonatomic, readonly, strong) UIColor *actionColor;

/// Short action label: "LOW" / "WAIT" / "HIGH" / "ALL IN" / "OVERDUE"
@property (nonatomic, readonly, copy) NSString *actionLabel;

@end
