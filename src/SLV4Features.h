#import <Foundation/Foundation.h>
#import "SLSpinParser.h"

// ---------------------------------------------------------------------------
//  SLV4Features
//
//  Maintains the rolling state needed to compute the 49-dim V4 feature vector
//  live — in-cycle counters, last-seen gaps, session-level VT gap lags,
//  trailing-window densities, tuple-category lag history, reel-dup streak,
//  prev_vt_type.
//
//  Call `feedSpin:` AFTER each spin resolves. It emits the feature vector
//  for the UPCOMING spin (i.e. features representing pre-spin state, which
//  is what the model was trained against). The value is stored on the object
//  — read via `currentFeatureVector`.
//
//  The returned double array is length [SLV4Model shared].featureCount, and
//  is valid until the next feedSpin: call.
// ---------------------------------------------------------------------------

typedef enum {
    SLV4PrevVtUnknown = 0,
    SLV4PrevVtACC,
    SLV4PrevVtSPN,
} SLV4PrevVtType;

typedef struct {
    // Values exposed for the HUD (readable without re-walking the full vector)
    int t;                        // spin index within current cycle
    int firesInCycle;             // how many times policy has said "fire" in this cycle
    int cumAnyInCycle;            // cumulative real-reward triples in this cycle
    int cycleIndex;               // 1-based cycle id this session
    SLV4PrevVtType prevVt;        // ACC / SPN / unknown
} SLV4Snapshot;

@interface SLV4Features : NSObject

+ (instancetype)shared;

/// Reset all state (call on session start / account switch).
- (void)reset;

/// Called AFTER a spin resolves. Updates cycle/session state and recomputes
/// the feature vector for the NEXT spin (as of right now, post-resolution).
/// Safe to call from any thread; internal state is protected by a serial
/// dispatch queue.
- (void)feedSpin:(SLSpinResult *)spin;

/// Current pre-spin feature vector. Length = [SLV4Model shared].featureCount.
/// Values may be NaN when history is insufficient.
- (const double *)currentFeatureVector;

/// Lightweight snapshot for the HUD.
- (SLV4Snapshot)snapshot;

/// Call when policy fires on the CURRENT spin (so firesInCycle counts
/// correctly in the HUD).
- (void)notePolicyFire;

@end
