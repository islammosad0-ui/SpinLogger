#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLV4Model
//
//  Loads the exported V4 bundle (assets/v4_model.json). Schema v2 nests by
//  head: models[head][K] (head ∈ {"ACC","ANY_VT"}, K ∈ {3,5,10}). Schema v1
//  was flat models[K] and is implicitly treated as the ACC head.
//
//  Per head/horizon: LightGBM tree set + isotonic calibrator. Inference uses
//  a C-struct tree representation (splits + leaves as packed arrays) so it
//  runs fast enough from the spin parse-time path.
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

/// Heads available in the loaded bundle. Always non-empty when isLoaded.
/// E.g. @[@"ACC", @"ANY_VT"]. v1 bundles return @[@"ACC"].
@property (nonatomic, readonly, copy) NSArray<NSString *> *heads;

/// Ordered feature-column names. Count = featureCount.
@property (nonatomic, readonly, copy) NSArray<NSString *> *featureCols;
@property (nonatomic, readonly) int featureCount;

/// ["ACC","SPN"] etc — pvt_* one-hots present in the training frame, in the
/// same order they appear in featureCols.
@property (nonatomic, readonly, copy) NSArray<NSString *> *pvtClasses;

/// "TRIPLE_ACCUMULATION" → 0, ...  Maps tuple-category string to cat id feature.
@property (nonatomic, readonly, copy) NSDictionary<NSString *, NSNumber *> *tupleCatIdx;

/// Run inference for K ∈ {3,5,10} on the given head ("ACC" or "ANY_VT").
/// If the head isn't loaded, falls back to the first available head (typically ACC).
/// NaN features route by `default_left`.
- (void)predictHead:(NSString *)head
                feat:(const double *)feat
                 p3:(double *)outP3
                 p5:(double *)outP5
                p10:(double *)outP10;

/// Legacy ACC-only predict (kept for callers that pre-date multi-head).
/// Equivalent to predictHead:@"ACC" ...
- (void)predict:(const double *)feat out:(double *)outP3 p5:(double *)outP5 p10:(double *)outP10;

@end
