#import "SLV4Model.h"
#import <math.h>
#import <stdlib.h>

// ---------------------------------------------------------------------------
//  Tree node representation
//
//  A LightGBM tree is a binary tree with internal nodes that hold a split
//  feature + threshold, and leaves that hold a scalar raw score. We pack it
//  into one flat array where negative indices mean "leaf" and non-negative
//  mean "internal". This lets the walker be a tight while-loop with no
//  recursion and no NSDictionary lookups per spin.
//
//  Layout:
//    - Internal node i: splits[i] describes the split;
//          splits[i].left  = child index (positive → internal, negative →
//                           ~leaf index, i.e. (-leaf - 1))
//          splits[i].right = same convention
//    - Leaf value table: leafValues[j] for leaf j.
// ---------------------------------------------------------------------------

typedef struct SLV4SplitNode {
    int splitFeature;      // feature index into the 49-dim vector
    double threshold;      // split threshold
    int left;              // >= 0 internal idx, < 0 means leaf at ~left
    int right;             // same convention
    unsigned char defaultLeft;  // which side to take for NaN inputs
    unsigned char decisionLE;   // 1 = "<=", 0 = "<"
} SLV4SplitNode;

typedef struct SLV4Tree {
    SLV4SplitNode *splits;
    int splitCount;
    double *leafValues;
    int leafCount;
} SLV4Tree;

// ---------------------------------------------------------------------------
//  Flattener — walks the nested NSDictionary tree and packs into arrays.
// ---------------------------------------------------------------------------
@interface SLV4TreeBuilder : NSObject {
@public
    SLV4SplitNode *splits;
    int splitCap, splitCount;
    double *leafValues;
    int leafCap, leafCount;
}
@end

@implementation SLV4TreeBuilder

- (instancetype)init {
    if (self = [super init]) {
        splitCap = 8;
        splits = (SLV4SplitNode *)calloc(splitCap, sizeof(SLV4SplitNode));
        leafCap = 8;
        leafValues = (double *)calloc(leafCap, sizeof(double));
    }
    return self;
}

- (void)dealloc {
    // Not freed here — ownership transfers to SLV4Horizon on build.
    // Callers responsible for freeing splits/leafValues via SLV4_FreeTree().
}

- (int)addLeaf:(double)v {
    if (leafCount >= leafCap) {
        leafCap *= 2;
        leafValues = (double *)realloc(leafValues, leafCap * sizeof(double));
    }
    leafValues[leafCount] = v;
    return leafCount++;
}

- (int)addSplit {
    if (splitCount >= splitCap) {
        splitCap *= 2;
        splits = (SLV4SplitNode *)realloc(splits, splitCap * sizeof(SLV4SplitNode));
    }
    // Zero-init the new slot
    memset(&splits[splitCount], 0, sizeof(SLV4SplitNode));
    return splitCount++;
}

// Returns encoded child index (positive for internal, negative-offset for leaf).
// A leaf at index j is returned as -(j + 1).
- (int)flatten:(NSDictionary *)node {
    NSNumber *leafVal = node[@"leaf_value"];
    if (leafVal != nil) {
        int idx = [self addLeaf:leafVal.doubleValue];
        return -(idx + 1);
    }

    // Internal node — reserve slot first, then recurse
    int myIdx = [self addSplit];
    int splitFeature = [node[@"split_feature"] intValue];
    double threshold = [node[@"threshold"] doubleValue];
    NSString *decision = node[@"decision_type"] ?: @"<=";
    BOOL defaultLeft = [node[@"default_left"] boolValue];

    int leftIdx = [self flatten:node[@"left_child"]];
    int rightIdx = [self flatten:node[@"right_child"]];

    splits[myIdx].splitFeature = splitFeature;
    splits[myIdx].threshold = threshold;
    splits[myIdx].left = leftIdx;
    splits[myIdx].right = rightIdx;
    splits[myIdx].defaultLeft = defaultLeft ? 1 : 0;
    splits[myIdx].decisionLE = [decision isEqualToString:@"<="] ? 1 : 0;
    return myIdx;
}

@end

// ---------------------------------------------------------------------------
//  Walker — single tree
// ---------------------------------------------------------------------------
static inline double SLV4_WalkTree(const SLV4Tree *t, const double *feat) {
    int idx = 0;  // root is always index 0
    while (idx >= 0) {
        const SLV4SplitNode *n = &t->splits[idx];
        double v = feat[n->splitFeature];
        int goLeft;
        if (isnan(v)) {
            goLeft = n->defaultLeft;
        } else if (n->decisionLE) {
            goLeft = (v <= n->threshold);
        } else {
            goLeft = (v < n->threshold);
        }
        int next = goLeft ? n->left : n->right;
        if (next < 0) {
            int leafIdx = -(next + 1);
            return t->leafValues[leafIdx];
        }
        idx = next;
    }
    return 0.0;  // unreachable
}

// ---------------------------------------------------------------------------
//  Isotonic interpolation (mirrors sklearn IsotonicRegression behaviour
//  with out_of_bounds="clip").
// ---------------------------------------------------------------------------
static double SLV4_ApplyIso(double p, const double *xs, const double *ys, int n) {
    if (n == 0) return p;
    if (p <= xs[0]) return ys[0];
    if (p >= xs[n - 1]) return ys[n - 1];

    int lo = 0, hi = n - 1;
    while (lo + 1 < hi) {
        int mid = (lo + hi) >> 1;
        if (xs[mid] <= p) lo = mid; else hi = mid;
    }
    double x0 = xs[lo], x1 = xs[hi];
    double y0 = ys[lo], y1 = ys[hi];
    if (x1 == x0) return y0;
    return y0 + (y1 - y0) * (p - x0) / (x1 - x0);
}

static inline double SLV4_Sigmoid(double x) {
    return 1.0 / (1.0 + exp(-x));
}

// ---------------------------------------------------------------------------
//  Model implementation
// ---------------------------------------------------------------------------
@interface SLV4Model () {
    SLV4Horizon _horizons[3];   // K3, K5, K10
    int _horizonCount;
}
@property (nonatomic, assign) BOOL isLoaded;
@property (nonatomic, copy) NSArray<NSString *> *featureCols;
@property (nonatomic, assign) int featureCount;
@property (nonatomic, copy) NSArray<NSString *> *pvtClasses;
@property (nonatomic, copy) NSDictionary<NSString *, NSNumber *> *tupleCatIdx;
@end

@implementation SLV4Model

+ (instancetype)shared {
    static SLV4Model *inst;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ inst = [[self alloc] init]; });
    return inst;
}

- (BOOL)loadFromAppBundle {
    NSString *exec = [[NSBundle mainBundle] executablePath];
    NSString *bundleDir = [exec stringByDeletingLastPathComponent];
    NSString *path = [bundleDir stringByAppendingPathComponent:@"v4_model.json"];
    NSError *err = nil;
    BOOL ok = [self loadFromPath:path error:&err];
    if (!ok) {
        NSLog(@"[SLV4Model] load failed (path=%@): %@", path, err);
    }
    return ok;
}

- (BOOL)loadFromPath:(NSString *)path error:(NSError **)error {
    NSData *data = [NSData dataWithContentsOfFile:path options:NSDataReadingMappedIfSafe error:error];
    if (!data) return NO;

    NSDictionary *bundle = [NSJSONSerialization JSONObjectWithData:data options:0 error:error];
    if (![bundle isKindOfClass:[NSDictionary class]]) return NO;

    NSArray *cols = bundle[@"feature_cols"];
    self.featureCols = cols;
    self.featureCount = (int)cols.count;
    self.pvtClasses = bundle[@"pvt_classes"];
    self.tupleCatIdx = bundle[@"tuple_cat_idx"];

    NSDictionary *models = bundle[@"models"];
    NSArray *horizonNames = @[@"K3", @"K5", @"K10"];
    _horizonCount = 0;
    for (NSString *name in horizonNames) {
        NSDictionary *m = models[name];
        if (!m) continue;

        SLV4Horizon *h = &_horizons[_horizonCount++];
        h->K = [[name substringFromIndex:1] intValue];

        NSArray *treeDicts = m[@"trees"];
        h->treeCount = (int)treeDicts.count;
        h->trees = (SLV4Tree *)calloc(h->treeCount, sizeof(SLV4Tree));

        for (int i = 0; i < h->treeCount; i++) {
            SLV4TreeBuilder *b = [[SLV4TreeBuilder alloc] init];
            [b flatten:treeDicts[i]];
            h->trees[i].splits = b->splits;
            h->trees[i].splitCount = b->splitCount;
            h->trees[i].leafValues = b->leafValues;
            h->trees[i].leafCount = b->leafCount;
            // detach ownership so dealloc doesn't free them
            b->splits = NULL;
            b->leafValues = NULL;
        }

        BOOL hasIso = [m[@"has_iso"] boolValue];
        if (hasIso) {
            NSArray *xs = m[@"iso_x"];
            NSArray *ys = m[@"iso_y"];
            h->isoCount = (int)xs.count;
            h->isoX = (double *)malloc(h->isoCount * sizeof(double));
            h->isoY = (double *)malloc(h->isoCount * sizeof(double));
            for (int j = 0; j < h->isoCount; j++) {
                h->isoX[j] = [xs[j] doubleValue];
                h->isoY[j] = [ys[j] doubleValue];
            }
        } else {
            h->isoX = NULL;
            h->isoY = NULL;
            h->isoCount = 0;
        }
    }

    NSLog(@"[SLV4Model] loaded %d horizons, %d features, %lu trees total",
          _horizonCount, self.featureCount,
          (unsigned long)(_horizons[0].treeCount + _horizons[1].treeCount + _horizons[2].treeCount));

    self.isLoaded = YES;
    return YES;
}

- (double)predictHorizon:(const SLV4Horizon *)h feat:(const double *)feat {
    double raw = 0.0;
    for (int i = 0; i < h->treeCount; i++) {
        raw += SLV4_WalkTree(&h->trees[i], feat);
    }
    double p = SLV4_Sigmoid(raw);
    if (h->isoCount > 0) {
        p = SLV4_ApplyIso(p, h->isoX, h->isoY, h->isoCount);
    }
    return p;
}

- (void)predict:(const double *)feat out:(double *)outP3 p5:(double *)outP5 p10:(double *)outP10 {
    if (!self.isLoaded) {
        if (outP3) *outP3 = 0;
        if (outP5) *outP5 = 0;
        if (outP10) *outP10 = 0;
        return;
    }
    for (int i = 0; i < _horizonCount; i++) {
        double p = [self predictHorizon:&_horizons[i] feat:feat];
        switch (_horizons[i].K) {
            case 3:  if (outP3)  *outP3  = p; break;
            case 5:  if (outP5)  *outP5  = p; break;
            case 10: if (outP10) *outP10 = p; break;
        }
    }
}

- (void)dealloc {
    for (int i = 0; i < _horizonCount; i++) {
        SLV4Horizon *h = &_horizons[i];
        for (int t = 0; t < h->treeCount; t++) {
            free(h->trees[t].splits);
            free(h->trees[t].leafValues);
        }
        free(h->trees);
        free(h->isoX);
        free(h->isoY);
    }
}

@end
