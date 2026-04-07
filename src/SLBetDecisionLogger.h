#import <Foundation/Foundation.h>
#import "SLSpinParser.h"
#import "SLDebtTracker.h"

// ---------------------------------------------------------------------------
//  SLBetDecisionLogger
//
//  Writes a row per spin to bet_decisions_YYYY-MM-DD.csv with the full state
//  of the ACC tracker (rule firings, phase, gap context, GAE state). The CSV
//  is consumed by analysis scripts (chunk 12_self_tune.py and beyond) for
//  drift detection and self-tuning.
//
//  Schema (~51 columns) — see NUCLEAR_FINDINGS.md "Per-rule logging" section.
//  Each rule has a fixed bit index in `rules_bitmask` AND a binary column.
// ---------------------------------------------------------------------------

void SLBetDecisionLoggerAppend(SLSpinResult *result,
                                SLDebtTracker *accTracker,
                                NSInteger gapIdx,
                                NSInteger spinInGap);

NSString *SLBetDecisionLoggerCSVPath(void);

// Rotate to a new bet_decisions CSV file (called on reset / new session).
void SLBetDecisionLoggerRotate(void);
