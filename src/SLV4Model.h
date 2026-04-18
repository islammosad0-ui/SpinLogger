#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLV4Model
//
//  Loads the exported V4 bundle (assets/v4_model.json) which holds:
//    - Three LightGBM ACC models (K=3 / K=5 / K=10), one set of trees each.
//    - An isotonic-regression calibrator per model (x/y knots).
//    - The ordered feature-column list the trees expect.
//    - PVT class names (which pvt_* one-hots to emit).
//    - Tuple-category → id map used by the feature extractor.
//
//  Given a 49-dim feature vector, produces p_acc_nextK for K ∈ {3, 5, 10}.
//  Uses a C-struct tree representation (splits + leaves as packed arrays) so
//  inference is fast enough to run synchronously from the spin-settle path.
// ---------------------------------------------------------------------------

typedef struct SLV4Horizon {
    int K;                              // 3, 5, or 10
    struct SLV4Tree *trees;             // allocated array
    int treeCount;
    // Isotonic calibration knots (sorted by x). If isoCount==0, no calibration.
    double *isoX;
    double *isoY;
    int isoCount;
} SLV4Horizon;

@interface SLV4Model : NSObject

+ (instancetype)shared;

/// Load the bundle from the given path. Returns NO on failure.
- (BOOL)loadFromPath:(NSString *)path error:(NSError **)error;

/// Convenience: look up `v4_model.json` beside the app binary.
- (BOOL)loadFromAppBundle;

@property (nonatomic, readonly) BOOL isLoaded;

/// Ordered feature-column names. Count = featureCount.
@property (nonatomic, readonly, copy) NSArray<NSString *> *featureCols;
@property (nonatomic, readonly) int featureCount;

/// ["ACC","SPN"] etc — pvt_* one-hots present in the training frame, in the
/// same order they appear in featureCols.
@property (nonatomic, readonly, copy) NSArray<NSString *> *pvtClasses;

/// "TRIPLE_ACCUMULATION" → 0, ...  Maps tuple-category string to cat id feature.
@property (nonatomic, readonly, copy) NSDictionary<NSString *, NSNumber *> *tupleCatIdx;

/// Run inference for the three horizons. feat is a double array of length
/// featureCount. Returns calibrated P(next-K ACC) in out[0..2] for K=3,5,10.
/// NaN features route by `default_left`.
- (void)predict:(const double *)feat out:(double *)outP3 p5:(double *)outP5 p10:(double *)outP10;

@end
