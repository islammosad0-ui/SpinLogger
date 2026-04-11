#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLScanSnapshot — One spin's worth of IL2CPP signal data
// ---------------------------------------------------------------------------
@interface SLScanSnapshot : NSObject

// Center payline (SlotSymbol enum raw int values)
@property (nonatomic) int32_t sym1, sym2, sym3;
// Top row (symbol above payline on each reel)
@property (nonatomic) int32_t top1, top2, top3;
// Bottom row (symbol below payline on each reel)
@property (nonatomic) int32_t bot1, bot2, bot3;

// Reel strip data
@property (nonatomic) int32_t stripIdx1, stripIdx2, stripIdx3;   // stop positions
@property (nonatomic) int32_t stripLen1, stripLen2, stripLen3;   // strip lengths

// Pity / fail counters
@property (nonatomic) int32_t failCounter;         // session (resets on restart)
@property (nonatomic) int32_t failCounterGlobal;   // persistent across sessions
@property (nonatomic) int32_t failThreshold;       // configured trigger point

// Game state
@property (nonatomic) int32_t betState;
@property (nonatomic) int32_t spinNumber;
@property (nonatomic) int32_t shields;
@property (nonatomic) BOOL    spinning;

// Tell indicators (YES = active / present)
@property (nonatomic) BOOL hasDynamicResults;      // server-pushed predetermined results
@property (nonatomic) BOOL hasFreezeContext;        // freeze/resolve mode active
@property (nonatomic) BOOL hasNearWin;             // near-miss symbol set
@property (nonatomic) BOOL hasReplacements;        // reel symbols swapped

@property (nonatomic, strong) NSDate *timestamp;

/// Pity progress 0.0–1.0 (failCounterGlobal / failThreshold). 0 if threshold unknown.
- (float)pityProgress;

@end

// ---------------------------------------------------------------------------
//  SLMemoryScanner — IL2CPP trace-mode dumper
// ---------------------------------------------------------------------------
@interface SLMemoryScanner : NSObject

+ (instancetype)shared;

/// Latest spin-end snapshot, kept for HUD compatibility during trace mode.
/// Populated from the most recent settled record.
@property (nonatomic, strong, readonly) SLScanSnapshot *latestSnapshot;

/// Trace mode live counters — updated on scanner thread, read on main.
/// Use these to decide when to stop the capture session.
@property (nonatomic, readonly) int64_t spinsSeen;
@property (nonatomic, readonly) int64_t snapshotsWritten;
@property (nonatomic, readonly) int64_t bytesWritten;
@property (nonatomic, readonly, copy) NSString *currentPhaseName;
@property (nonatomic, readonly, copy) NSString *traceFilePath;

/// Start IL2CPP live scanner in trace mode (250 ms poll)
- (void)startScanning;

/// Stop scanning and flush the trace file
- (void)stopScanning;

@end
