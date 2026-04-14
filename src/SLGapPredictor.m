#import "SLGapPredictor.h"
#import <UIKit/UIKit.h>

// ---------------------------------------------------------------------------
//  Empirical lookup tables from 54,770 spins / 1,110 VTs / 3 accounts
//  Built by analysis/gap_predictor.py — walk-forward validated
// ---------------------------------------------------------------------------

/// 1-gap lookup: previous gap bucket (10-spin) -> {p10, p25, median, p75, p90, hotLo}
typedef struct {
    int p10, p25, median, p75, p90, hotLo;
} SLGapBucketEntry;

// Index = prev_gap / 10 (0 = gap 0-9, 1 = gap 10-19, etc.)
// Last entry (14) covers 140+
static const SLGapBucketEntry kSingleGapTable[] = {
    /* 0:  0- 9 */ { 8,  34, 70, 91,  128, 77},
    /* 1: 10-19 */ {14,  34, 57, 83,  110, 37},
    /* 2: 20-29 */ { 8,  28, 46, 73,  110, 21},
    /* 3: 30-39 */ { 5,  20, 40, 68,   98,  5},
    /* 4: 40-49 */ { 9,  23, 43, 76,   91,  3},
    /* 5: 50-59 */ {10,  26, 41, 62,   83, 34},
    /* 6: 60-69 */ { 4,  13, 33, 59,   79,  4},
    /* 7: 70-79 */ { 4,  14, 28, 48,   77,  5},
    /* 8: 80-89 */ { 5,  19, 33, 57,   72, 24},
    /* 9: 90-99 */ { 3,  11, 38, 52,   74,  2},
    /*10:100-109*/ { 5,   8, 27, 58,   83,  0},
    /*11:110-119*/ { 4,   8, 14, 20,   27, 11},
    /*12:120-129*/ { 3,  10, 16, 34,   46,  4},
    /*13:130-139*/ { 3,   8, 20, 40,   60,  2},
    /*14:140+   */ { 2,   6, 18, 35,   55,  1},
};
static const int kSingleGapTableSize = 15;

/// 2-gap class lookup: (prevPrev class, prev class) -> {p25, median, p75, hotLo}
/// Classes: VS=0 (1-20), S=1 (21-35), M=2 (36-55), L=3 (56-80), VL=4 (81+)
typedef struct {
    int cls2, cls1;  // prevPrev, prev class indices
    int p25, median, p75, hotLo;
    int n;           // sample size (for confidence)
} SLDoubleGapEntry;

static const SLDoubleGapEntry kDoubleGapTable[] = {
    // Sorted by median (fastest rebounds first)
    {4, 3,   12, 18, 30,  5,  30},  // VL->L:  median 18
    {0, 4,    8, 26, 53,  2,  96},  // VS->VL: median 26
    {1, 4,   15, 27, 51,  7,  31},  // S->VL:  median 27
    {4, 4,   17, 28, 35, 24,  12},  // VL->VL: median 28
    {3, 3,   19, 29, 37, 28,  28},  // L->L:   median 29
    {3, 1,   23, 30, 50, 21,  44},  // L->S:   median 30
    {2, 4,   13, 34, 44,  4,  48},  // M->VL:  median 34
    {2, 2,   19, 35, 75, 15,  53},  // M->M:   median 35
    {0, 3,   13, 35, 60,  0,  54},  // VS->L:  median 35
    {2, 3,   13, 36, 58,  5,  47},  // M->L:   median 36
    {3, 4,   25, 38, 58, 16,  15},  // L->VL:  median 38
    {4, 1,   21, 41, 55, 30,  36},  // VL->S:  median 41
    {0, 2,   28, 42, 86, 33,  60},  // VS->M:  median 42
    {3, 2,   22, 42, 70, 34,  43},  // L->M:   median 42
    {4, 2,   32, 42, 58, 30,  44},  // VL->M:  median 42
    {2, 1,   17, 43, 74,  6,  43},  // M->S:   median 43
    {1, 3,   26, 44, 60, 22,  36},  // S->L:   median 44
    {1, 1,   22, 46, 68, 44,  41},  // S->S:   median 46
    {4, 0,   31, 48, 81, 28,  80},  // VL->VS: median 48
    {1, 2,   18, 56, 77,  0,  42},  // S->M:   median 56
    {0, 0,   42, 63, 84, 37,  43},  // VS->VS: median 63
    {1, 0,   22, 68, 83,  2,  40},  // S->VS:  median 68
    {0, 1,   33, 69, 86, 65,  26},  // VS->S:  median 69
    {3, 0,   44, 70, 89, 83,  64},  // L->VS:  median 70
    {2, 0,   50, 79,106, 85,  51},  // M->VS:  median 79
};
static const int kDoubleGapTableSize = 25;

/// Hazard rate by gap zone (from conditional hazard analysis)
typedef struct {
    int lo, hi;
    float lift;  // vs base rate
} SLHazardZone;

static const SLHazardZone kHazardZones[] = {
    {  0, 10, 0.69f},
    { 10, 20, 0.73f},
    { 20, 30, 0.83f},
    { 30, 40, 1.03f},
    { 40, 50, 1.09f},
    { 50, 60, 1.18f},
    { 60, 70, 1.15f},
    { 70, 80, 1.61f},
    { 80,100, 2.02f},
    {100,150, 1.27f},
    {150,999, 1.49f},
};
static const int kHazardZoneCount = 11;

// ---------------------------------------------------------------------------
//  UserDefaults keys for persistence across restarts
// ---------------------------------------------------------------------------
static NSString *const kGapPredGapPos    = @"SLGapPred_GapPos";
static NSString *const kGapPredPrevGap   = @"SLGapPred_PrevGap";
static NSString *const kGapPredPrevPrev  = @"SLGapPred_PrevPrev";
static NSString *const kGapPredVTCount   = @"SLGapPred_VTCount";

// ---------------------------------------------------------------------------
//  Implementation
// ---------------------------------------------------------------------------
@interface SLGapPredictor ()
@property (nonatomic, readwrite) SLGapPrediction prediction;
@property (nonatomic, readwrite) NSInteger vtCount;
@property (nonatomic, readwrite, copy) NSString *displayString;
@property (nonatomic, readwrite, strong) UIColor *actionColor;
@property (nonatomic, readwrite, copy) NSString *actionLabel;

@property (nonatomic, assign) NSInteger gapPos;
@property (nonatomic, assign) NSInteger prevGap;
@property (nonatomic, assign) NSInteger prevPrevGap;
@end

@implementation SLGapPredictor

+ (instancetype)shared {
    static SLGapPredictor *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        // Restore persisted state
        NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
        _gapPos     = [ud integerForKey:kGapPredGapPos];
        _prevGap    = [ud objectForKey:kGapPredPrevGap] ? [ud integerForKey:kGapPredPrevGap] : -1;
        _prevPrevGap = [ud objectForKey:kGapPredPrevPrev] ? [ud integerForKey:kGapPredPrevPrev] : -1;
        _vtCount    = [ud integerForKey:kGapPredVTCount];

        _displayString = @"GAP --";
        _actionLabel = @"---";
        _actionColor = [UIColor colorWithWhite:0.5 alpha:1];

        [self recompute];
    }
    return self;
}

// ---------------------------------------------------------------------------
//  Public: call after every spin settles
// ---------------------------------------------------------------------------
- (void)recordSpinIsVT:(BOOL)isVT {
    if (isVT) {
        // This gap just ended
        NSInteger completedGap = self.gapPos;

        // Shift gap history
        self.prevPrevGap = self.prevGap;
        self.prevGap = completedGap;
        self.gapPos = 0;
        self.vtCount++;

        NSLog(@"[SLGapPredictor] VT! Gap=%ld, prevGap=%ld, prevPrev=%ld, vtCount=%ld",
              (long)completedGap, (long)self.prevGap, (long)self.prevPrevGap, (long)self.vtCount);
    } else {
        self.gapPos++;
    }

    [self recompute];
    [self persist];
}

// ---------------------------------------------------------------------------
//  Core prediction logic
// ---------------------------------------------------------------------------
- (void)recompute {
    SLGapPrediction pred;
    pred.gapPos = self.gapPos;
    pred.prevGap = self.prevGap;
    pred.prevPrevGap = self.prevPrevGap;

    // Try 2-gap lookup first
    BOOL found2 = NO;
    if (self.prevGap >= 0 && self.prevPrevGap >= 0) {
        int cls2 = [self classifyGap:self.prevPrevGap];
        int cls1 = [self classifyGap:self.prevGap];

        for (int i = 0; i < kDoubleGapTableSize; i++) {
            if (kDoubleGapTable[i].cls2 == cls2 && kDoubleGapTable[i].cls1 == cls1
                && kDoubleGapTable[i].n >= 12) {
                const SLDoubleGapEntry *e = &kDoubleGapTable[i];
                pred.predP25 = e->p25;
                pred.predMedian = e->median;
                pred.predP75 = e->p75;
                pred.hotLo = e->hotLo;
                pred.hotHi = e->hotLo + 10;
                // Estimate P10/P90 from spread
                int spread = e->p75 - e->p25;
                pred.predP10 = MAX(1, e->p25 - spread / 2);
                pred.predP90 = e->p75 + spread / 2;
                found2 = YES;
                break;
            }
        }
    }

    // Fall back to 1-gap lookup
    if (!found2 && self.prevGap >= 0) {
        int bucket = MIN((int)(self.prevGap / 10), kSingleGapTableSize - 1);
        const SLGapBucketEntry *e = &kSingleGapTable[bucket];
        pred.predP10 = e->p10;
        pred.predP25 = e->p25;
        pred.predMedian = e->median;
        pred.predP75 = e->p75;
        pred.predP90 = e->p90;
        pred.hotLo = e->hotLo;
        pred.hotHi = e->hotLo + 10;
    }

    // No history yet — use unconditional median
    if (self.prevGap < 0) {
        pred.predP10 = 9;
        pred.predP25 = 22;
        pred.predMedian = 41;
        pred.predP75 = 68;
        pred.predP90 = 100;
        pred.hotLo = 20;
        pred.hotHi = 30;
    }

    // Progress toward P75
    pred.progress = (pred.predP75 > 0)
        ? (CGFloat)self.gapPos / (CGFloat)pred.predP75
        : 0.0;

    // Hazard lift for current position
    pred.hazardLift = [self hazardLiftForPosition:self.gapPos];

    // Determine action
    if (self.gapPos < pred.predP10) {
        pred.action = SLGapActionBetLow;
    } else if (self.gapPos < pred.predP25) {
        pred.action = SLGapActionWatch;
    } else if (self.gapPos < pred.predP75) {
        pred.action = SLGapActionBetHigh;
    } else if (self.gapPos < pred.predP90) {
        pred.action = SLGapActionAllIn;
    } else {
        pred.action = SLGapActionOverdue;
    }

    self.prediction = pred;

    // Update display properties
    [self updateDisplay];
}

- (int)classifyGap:(NSInteger)g {
    if (g <= 20) return 0;   // VS
    if (g <= 35) return 1;   // S
    if (g <= 55) return 2;   // M
    if (g <= 80) return 3;   // L
    return 4;                 // VL
}

- (float)hazardLiftForPosition:(NSInteger)pos {
    for (int i = 0; i < kHazardZoneCount; i++) {
        if (pos >= kHazardZones[i].lo && pos < kHazardZones[i].hi) {
            return kHazardZones[i].lift;
        }
    }
    return 1.0f;
}

// ---------------------------------------------------------------------------
//  Display formatting
// ---------------------------------------------------------------------------
- (void)updateDisplay {
    SLGapPrediction p = self.prediction;

    // Action label + color
    switch (p.action) {
        case SLGapActionBetLow:
            self.actionLabel = @"LOW";
            self.actionColor = [UIColor colorWithWhite:0.45 alpha:1];
            break;
        case SLGapActionWatch:
            self.actionLabel = @"WAIT";
            self.actionColor = [UIColor colorWithRed:0.5 green:0.7 blue:1.0 alpha:1];
            break;
        case SLGapActionBetHigh:
            self.actionLabel = @"HIGH";
            self.actionColor = [UIColor colorWithRed:1.0 green:0.7 blue:0.0 alpha:1];
            break;
        case SLGapActionAllIn:
            self.actionLabel = @"ALL IN";
            self.actionColor = [UIColor colorWithRed:1.0 green:0.25 blue:0.25 alpha:1];
            break;
        case SLGapActionOverdue:
            self.actionLabel = @"OVERDUE";
            self.actionColor = [UIColor colorWithRed:1.0 green:0.1 blue:0.4 alpha:1];
            break;
    }

    // Display: "GAP 23 → 30-68"  (position → window range)
    // Arrow changes: → before window, ★ inside, ! past P75
    NSString *arrow;
    if (p.gapPos < p.predP25)      arrow = @"\u2192";   // →
    else if (p.gapPos <= p.predP75) arrow = @"\u2605";   // ★
    else                            arrow = @"!";

    self.displayString = [NSString stringWithFormat:@"GAP %ld %@ %ld-%ld",
                          (long)p.gapPos, arrow,
                          (long)p.predP25, (long)p.predP75];
}

// ---------------------------------------------------------------------------
//  Persistence
// ---------------------------------------------------------------------------
- (void)persist {
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    [ud setInteger:self.gapPos      forKey:kGapPredGapPos];
    [ud setInteger:self.prevGap     forKey:kGapPredPrevGap];
    [ud setInteger:self.prevPrevGap forKey:kGapPredPrevPrev];
    [ud setInteger:self.vtCount     forKey:kGapPredVTCount];
}

@end
