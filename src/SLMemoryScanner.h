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

// Full post-replacement strip symbols per reel (e.g. "4,30,2,6,1,3,5,2,4")
@property (nonatomic, copy) NSString *fullStrip1;
@property (nonatomic, copy) NSString *fullStrip2;
@property (nonatomic, copy) NSString *fullStrip3;

// Replacement maps per reel (e.g. "4>30,1>6" meaning sym 4 replaced by 30)
@property (nonatomic, copy) NSString *replMap1;
@property (nonatomic, copy) NSString *replMap2;
@property (nonatomic, copy) NSString *replMap3;

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
//  SLMemoryScanner — IL2CPP memory scanner
// ---------------------------------------------------------------------------
@interface SLMemoryScanner : NSObject

+ (instancetype)shared;

/// Latest spin-end snapshot for HUD display.
@property (nonatomic, strong, readonly) SLScanSnapshot *latestSnapshot;

@property (nonatomic, readonly) int64_t spinsSeen;
@property (nonatomic, readonly, copy) NSString *currentPhaseName;

/// Start IL2CPP live scanner (250 ms poll)
- (void)startScanning;

/// Stop scanning
- (void)stopScanning;

@end
