# IL2CPP Trace Decoder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the broken live IL2CPP signal scanner with a trace-mode scanner that dumps raw IL2CPP state each poll to JSONL, plus an offline Python analyzer that reverse-engineers the true memory layouts against the game's own `spin_history.csv` ground truth and produces a layout report for a future scanner rewrite.

**Architecture:** Keep Phases 0–3 of the existing scanner state machine (API resolution, class finding, offset caching, instance watching) untouched. Replace only Phase 4 (`ScanPhaseActive`) with a `traceScan` method that fires every 250 ms, enumerates every field on every known class (β), dumps targeted raw hex windows around suspect structures (γ), and writes one JSONL record per tick on a background dispatch queue. Offline analyzer runs six stages: load+segment, payline sanity gate, field change-map, strip decoder, pity counter hunt, report.

**Tech Stack:** Objective-C + MobileSubstrate tweak, IL2CPP runtime API (`il2cpp_class_get_fields`, `il2cpp_field_get_offset`, etc.), GCD for thread separation, `NSJSONSerialization` for encoding; Python 3.10+ with pandas, numpy, pytest.

**Design doc:** [2026-04-11-il2cpp-trace-decoder-design.md](2026-04-11-il2cpp-trace-decoder-design.md)

**Build reality:** Actual device builds run on GitHub Actions, not locally on Windows. Obj-C iteration loop is: push → CI builds `.dylib` → deploy to device → run game → inspect JSONL output. For that reason each Obj-C task ends with "commit + push" and verification happens after multiple tasks land in CI, not per-task. Python tasks run pytest locally.

---

## Prerequisites

Before starting:

1. Read the [design doc](2026-04-11-il2cpp-trace-decoder-design.md) in full.
2. Current branch is `main`; design doc already committed at `20b9bb8`. Implementation commits go on top.
3. Confirm a Python venv with `pandas`, `numpy`, `pytest` is available. The existing analysis scripts in `analysis/nuclear/` already use pandas, so the project venv should work. If pytest is missing: `pip install pytest`.
4. Do **not** touch phases 0–3 of `src/SLMemoryScanner.m` (the `resolveAPIs`, `findClasses`, `cacheOffsets`, `ScanPhaseWaitInstance` paths). They already work and are the foundation the trace mode reuses.
5. The ground-truth CSV for the first capture session will be whatever `data/Islam/spin_history_<capture_date>.csv` the network monitor generates during the trace run. Make sure `SLNetworkMonitor` is still installed in `SpinLoggerTweak.m` (it is) so both streams are produced simultaneously.

---

## Phase 1 — Trace mode scanner (Objective-C)

### Task 1.1: Add trace mode constants

**Files:**
- Modify: `src/SLConstants.h`

**Step 1: Read the current state of `src/SLConstants.h`** to confirm line numbers.

**Step 2: Add trace constants below the existing file-name block (after line 69, `kSLSignalCSVFile`).**

```objc
// IL2CPP trace mode (replaces signal CSV during reverse-engineering session)
static NSString *const kSLTraceJSONLPrefix    = @"il2cpp_trace_";
static NSString *const kSLTraceJSONLExtension = @".jsonl";
#define kSLTraceHexWindowBar     256    // bytes per slotBar instance
#define kSLTraceHexWindowResult  128    // bytes for currentSlotResult
#define kSLTraceHexArrayMaxBytes 2048   // cap raw array payload dump
#define kSLTracePointerFollowMaxDepth 1  // follow pointers one level only
```

**Step 3: Commit.**

```bash
git add src/SLConstants.h
git commit -m "feat: add IL2CPP trace mode constants"
```

---

### Task 1.2: Expose trace counters on `SLMemoryScanner` interface

**Files:**
- Modify: `src/SLMemoryScanner.h`

**Step 1: Read `src/SLMemoryScanner.h`** to confirm the interface layout.

**Step 2: Replace the `SLMemoryScanner` interface block (currently lines ~46–59) with this version, keeping `SLScanSnapshot` above untouched:**

```objc
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
```

**Step 3: Commit.**

```bash
git add src/SLMemoryScanner.h
git commit -m "feat: expose trace counters on SLMemoryScanner"
```

---

### Task 1.3: Add trace-mode ivars and background queue to scanner

**Files:**
- Modify: `src/SLMemoryScanner.m`

**Step 1: Read the full scanner file** to locate the `@interface SLMemoryScanner ()` extension block near line 132.

**Step 2: Replace the private extension block with this version:**

```objc
@interface SLMemoryScanner ()
@property (nonatomic, strong) NSTimer *scanTimer;
@property (nonatomic, assign) ScanPhase phase;
@property (nonatomic, assign) void *domain;
@property (nonatomic, assign) BOOL prevSpinning;
@property (nonatomic, strong, readwrite) SLScanSnapshot *latestSnapshot;

// Trace mode state
@property (nonatomic, strong) dispatch_queue_t traceWriteQueue;
@property (nonatomic, strong) NSFileHandle *traceFileHandle;
@property (nonatomic, copy, readwrite) NSString *traceFilePath;
@property (nonatomic, assign) uint64_t traceStartMs;
@property (nonatomic, assign) int64_t spinsSeen;
@property (nonatomic, assign) int64_t snapshotsWritten;
@property (nonatomic, assign) int64_t bytesWritten;
@property (nonatomic, copy, readwrite) NSString *currentPhaseName;
@end
```

**Step 3:** In `+ shared` / `- init` — no changes needed; properties initialize to zero.

**Step 4: Modify `startScanning` (currently around line 150)** to open the trace file and create the background queue. Replace the method body with:

```objc
- (void)startScanning {
    if (self.scanTimer) return;
    self.phase = ScanPhaseResolveAPIs;
    self.prevSpinning = NO;
    self.currentPhaseName = @"resolveAPIs";
    self.traceStartMs = [self monotonicMillis];

    // Create serial background queue for file I/O
    self.traceWriteQueue = dispatch_queue_create("com.spinlogger.trace.write",
                                                  DISPATCH_QUEUE_SERIAL);

    // Create trace file with timestamped filename
    NSDateFormatter *fmt = [[NSDateFormatter alloc] init];
    fmt.dateFormat = @"yyyyMMdd_HHmmss";
    NSString *stamp = [fmt stringFromDate:[NSDate date]];
    NSString *fileName = [NSString stringWithFormat:@"%@%@%@",
                          kSLTraceJSONLPrefix, stamp, kSLTraceJSONLExtension];
    NSString *docs = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory,
                                                          NSUserDomainMask, YES).firstObject;
    self.traceFilePath = [docs stringByAppendingPathComponent:fileName];

    [[NSFileManager defaultManager] createFileAtPath:self.traceFilePath
                                            contents:nil
                                          attributes:nil];
    self.traceFileHandle = [NSFileHandle fileHandleForWritingAtPath:self.traceFilePath];

    self.scanTimer = [NSTimer scheduledTimerWithTimeInterval:0.25
                                                     target:self
                                                   selector:@selector(tick)
                                                   userInfo:nil
                                                    repeats:YES];
    NSLog(@"[SpinLogger] IL2CPP Trace Scanner started → %@", self.traceFilePath);
}
```

**Step 5: Modify `stopScanning`** to flush and close the trace file:

```objc
- (void)stopScanning {
    [self.scanTimer invalidate];
    self.scanTimer = nil;
    dispatch_sync(self.traceWriteQueue, ^{
        [self.traceFileHandle synchronizeFile];
        [self.traceFileHandle closeFile];
        self.traceFileHandle = nil;
    });
    NSLog(@"[SpinLogger] IL2CPP Trace stopped. %lld snapshots, %lld bytes to %@",
          self.snapshotsWritten, self.bytesWritten, self.traceFilePath);
}
```

**Step 6: Add a `monotonicMillis` helper** anywhere in the file (e.g. just above `tick`):

```objc
- (uint64_t)monotonicMillis {
    static mach_timebase_info_data_t tb;
    if (tb.denom == 0) mach_timebase_info(&tb);
    uint64_t nanos = mach_absolute_time() * tb.numer / tb.denom;
    return nanos / 1000000ULL;
}
```

Add `#include <mach/mach_time.h>` near the top of the file alongside the other system includes.

**Step 7: Delete the old CSV helpers** — remove `csvPath`, `writeCSVHeader`, `writeCSVRow`, and the `csvHeaderWritten` property from the class. These are replaced by JSONL helpers in Task 1.5.

**Step 8: Commit.**

```bash
git add src/SLMemoryScanner.m
git commit -m "feat: add trace mode ivars, file lifecycle, mach_time helper"
```

---

### Task 1.4: Add field-enumeration IL2CPP API resolution

**Files:**
- Modify: `src/SLMemoryScanner.m`

**Step 1:** The existing scanner already resolves most IL2CPP APIs (`class_get_fields`, `field_get_name`, `field_get_offset`). We need to add one more — `il2cpp_class_get_fields` returns fields via iterator, but we also need access to the raw instance bytes for the hex windows. No new API needed for that (raw `memcpy` via pointer works). Nothing to add here — confirm existing `RESOLVE` block in `resolveAPIs` already has everything.

**Step 2:** Read the `resolveAPIs` method. Confirm the following are already resolved: `class_get_fields`, `field_get_name`, `field_get_offset`. They are — lines ~184–186. No code change needed.

**Step 3:** No commit (no change).

---

### Task 1.5: Add JSONL serialization helpers

**Files:**
- Modify: `src/SLMemoryScanner.m`

**Step 1: Add a helper to check if an address looks like a valid heap pointer** (used for pointer-follow decisions). Add below `arrayElementPtr`:

```objc
/// Heuristic: does this pointer look like a valid IL2CPP heap address?
/// ARM64 user-space heap is typically in 0x100000000–0x7FFFFFFFFF range.
static inline BOOL looksLikeHeapPointer(void *p) {
    uintptr_t addr = (uintptr_t)p;
    if (addr < 0x100000000ULL) return NO;       // too low (nil / small int)
    if (addr > 0x7FFFFFFFFFULL) return NO;      // too high (kernel / garbage)
    if (addr & 0x7) return NO;                  // misaligned (not an object)
    return YES;
}
```

**Step 2: Add a helper to dump raw hex bytes as an NSString.**

```objc
/// Convert a byte buffer to lowercase hex string, no separators.
static NSString *hexString(const void *buf, size_t len) {
    if (!buf || len == 0) return @"";
    static const char hexChars[] = "0123456789abcdef";
    char *out = malloc(len * 2 + 1);
    const uint8_t *in = (const uint8_t *)buf;
    for (size_t i = 0; i < len; i++) {
        out[i*2]     = hexChars[(in[i] >> 4) & 0xF];
        out[i*2 + 1] = hexChars[in[i] & 0xF];
    }
    out[len*2] = 0;
    NSString *s = [NSString stringWithUTF8String:out];
    free(out);
    return s;
}
```

**Step 3: Add a helper to enumerate all fields on a class and return them as a dict of {offset, u64, i32, ptr}.**

```objc
/// Enumerate all fields on a class and read their raw 8 bytes from an instance.
/// Returns an NSDictionary keyed by field name, each value a dict
/// with keys "off" (NSNumber), "u64" (NSNumber), "i32" (NSNumber), "ptr" (NSString "0x...").
static NSDictionary *dumpClassFields(void *klass, void *instance) {
    if (!klass || !instance) return @{};
    NSMutableDictionary *out = [NSMutableDictionary dictionary];
    void *iter = NULL;
    void *field = NULL;
    while ((field = _class_get_fields(klass, &iter)) != NULL) {
        const char *nm = _field_get_name(field);
        if (!nm) continue;
        size_t off = _field_get_offset(field);
        if (off == 0) continue;  // static or invalid
        uint64_t u64 = *(uint64_t *)((uint8_t *)instance + off);
        int32_t  i32 = *(int32_t  *)((uint8_t *)instance + off);
        void    *ptr = *(void   **)((uint8_t *)instance + off);
        out[[NSString stringWithUTF8String:nm]] = @{
            @"off": @(off),
            @"u64": @(u64),
            @"i32": @(i32),
            @"ptr": [NSString stringWithFormat:@"0x%lx", (unsigned long)ptr]
        };
    }
    return out;
}
```

**Step 4: Commit.**

```bash
git add src/SLMemoryScanner.m
git commit -m "feat: add hex + field-enumeration helpers for trace mode"
```

---

### Task 1.6: Implement `buildTraceRecord` — assemble one snapshot dict

**Files:**
- Modify: `src/SLMemoryScanner.m`

**Step 1: Add this method on the scanner, below the existing `readSnapshotFromInstance`:**

```objc
/// Assemble one full trace record as an NSDictionary, ready for JSON encoding.
/// Runs on the scanner thread — keep it fast (memcpy only, no formatting).
- (NSDictionary *)buildTraceRecordForInstance:(void *)inst {
    NSMutableDictionary *rec = [NSMutableDictionary dictionary];

    // Top-level quick-filter fields
    rec[@"t"] = [[NSISO8601DateFormatter new] stringFromDate:[NSDate date]];
    rec[@"mono_ms"] = @([self monotonicMillis] - self.traceStartMs);
    rec[@"spin_num"] = @(readInt32(inst, fo_currentSpinNumber));
    rec[@"spinning"] = @(readBool(inst, fo_spinning) != 0);
    rec[@"bet_state"] = @(readInt32(inst, fo_betState));
    rec[@"phase"] = self.currentPhaseName ?: @"?";
    rec[@"instance_ptr"] = [NSString stringWithFormat:@"0x%lx", (unsigned long)inst];

    // ----- β: field enumeration section -----
    NSMutableDictionary *fields = [NSMutableDictionary dictionary];

    // SlotMachineManager — direct
    fields[@"SlotMachineManager"] = dumpClassFields(s_klass_Manager, inst);

    // Follow currentSlotResult pointer one level
    void *slotResult = readPtr(inst, fo_currentSlotResult);
    if (looksLikeHeapPointer(slotResult) && s_klass_Result) {
        NSString *key = [NSString stringWithFormat:@"SlotResult@0x%lx", (unsigned long)slotResult];
        fields[key] = dumpClassFields(s_klass_Result, slotResult);

        // Follow slotSymbols (SlotSymbol3) one more level — exception to depth=1
        // because SlotResult is effectively a pass-through wrapper
        void *sym3 = readPtr(slotResult, fo_slotSymbols);
        if (looksLikeHeapPointer(sym3) && s_klass_Symbol3) {
            NSString *sk = [NSString stringWithFormat:@"SlotSymbol3@0x%lx", (unsigned long)sym3];
            fields[sk] = dumpClassFields(s_klass_Symbol3, sym3);
        }
    }

    // Follow each slot bar pointer one level
    void *bars[3] = {
        readPtr(inst, fo_slotBar1),
        readPtr(inst, fo_slotBar2),
        readPtr(inst, fo_slotBar3)
    };
    for (int i = 0; i < 3; i++) {
        if (looksLikeHeapPointer(bars[i]) && s_klass_BarManager) {
            NSString *key = [NSString stringWithFormat:@"SlotBarManager_%d@0x%lx",
                             i + 1, (unsigned long)bars[i]];
            fields[key] = dumpClassFields(s_klass_BarManager, bars[i]);
        }
    }

    // Follow BoardManager
    void *board = readPtr(inst, fo_boardManager);
    if (looksLikeHeapPointer(board) && s_klass_BoardMgr) {
        NSString *key = [NSString stringWithFormat:@"BoardManager@0x%lx", (unsigned long)board];
        fields[key] = dumpClassFields(s_klass_BoardMgr, board);
    }

    rec[@"fields"] = fields;

    // ----- γ: targeted hex windows -----
    NSMutableDictionary *hex = [NSMutableDictionary dictionary];

    // Raw bytes at each bar instance
    for (int i = 0; i < 3; i++) {
        if (looksLikeHeapPointer(bars[i])) {
            NSString *key = [NSString stringWithFormat:@"slotBar%d@0x%lx",
                             i + 1, (unsigned long)bars[i]];
            hex[key] = hexString(bars[i], kSLTraceHexWindowBar);
        }
    }

    // Raw bytes at each bar's m_SymbolElements array payload
    for (int i = 0; i < 3; i++) {
        if (!looksLikeHeapPointer(bars[i])) continue;
        void *elements = readPtr(bars[i], fo_symbolElements);
        if (!looksLikeHeapPointer(elements)) continue;
        int64_t len = *(int64_t *)((uint8_t *)elements + kArrayLengthOffset);
        if (len <= 0 || len > 256) continue;   // sanity bound
        size_t totalBytes = kArrayHeaderSize + (size_t)len * sizeof(void *);
        // Also try a wider dump in case elements are larger structs
        size_t dumpBytes = MIN(kSLTraceHexArrayMaxBytes, totalBytes + 128);
        NSString *key = [NSString stringWithFormat:@"slotBar%d.m_SymbolElements@0x%lx",
                         i + 1, (unsigned long)elements];
        hex[key] = @{
            @"array_len": @(len),
            @"header_size": @(kArrayHeaderSize),
            @"bytes": hexString(elements, dumpBytes)
        };
    }

    // Raw bytes at currentSlotResult
    if (looksLikeHeapPointer(slotResult)) {
        NSString *key = [NSString stringWithFormat:@"currentSlotResult@0x%lx",
                         (unsigned long)slotResult];
        hex[key] = hexString(slotResult, kSLTraceHexWindowResult);
    }

    rec[@"hex"] = hex;
    return rec;
}
```

**Step 2: Commit.**

```bash
git add src/SLMemoryScanner.m
git commit -m "feat: implement buildTraceRecord — β fields + γ hex windows"
```

---

### Task 1.7: Wire `traceScan` into the state machine and write JSONL

**Files:**
- Modify: `src/SLMemoryScanner.m`

**Step 1: Replace the `activeScan` method with `traceScan`.** Delete the current `activeScan` body (which includes the old CSV write and `spinEnded` edge detection), and add:

```objc
- (void)traceScan {
    // Read instance singleton
    void *instance = NULL;
    _field_static_get_value(fh_Instance, &instance);
    if (!instance) return;

    // Build record on scanner thread (fast, memcpy-only)
    NSDictionary *rec = [self buildTraceRecordForInstance:instance];

    // Track spin-end for counter purposes
    BOOL isSpinning = [rec[@"spinning"] boolValue];
    BOOL spinEnded = (self.prevSpinning && !isSpinning);
    self.prevSpinning = isSpinning;
    if (spinEnded) self.spinsSeen++;

    // Populate latestSnapshot minimally for HUD compatibility
    if (spinEnded) {
        SLScanSnapshot *snap = [[SLScanSnapshot alloc] init];
        snap.timestamp = [NSDate date];
        snap.spinNumber = [rec[@"spin_num"] intValue];
        snap.betState = [rec[@"bet_state"] intValue];
        snap.spinning = isSpinning;
        self.latestSnapshot = snap;
    }

    // Hand off to background queue for JSON encoding + file write
    dispatch_async(self.traceWriteQueue, ^{
        NSError *err = nil;
        NSData *jsonData = [NSJSONSerialization dataWithJSONObject:rec
                                                           options:0
                                                             error:&err];
        if (!jsonData) {
            NSLog(@"[SpinLogger] Trace JSON encode failed: %@", err);
            return;
        }
        NSMutableData *line = [jsonData mutableCopy];
        [line appendBytes:"\n" length:1];
        @try {
            [self.traceFileHandle writeData:line];
            self.snapshotsWritten++;
            self.bytesWritten += line.length;
        } @catch (NSException *ex) {
            NSLog(@"[SpinLogger] Trace write failed: %@", ex);
        }
    });
}
```

**Step 2: Update the `tick` method** to call `traceScan` in the active phase and to set `currentPhaseName`:

```objc
- (void)tick {
    switch (self.phase) {
        case ScanPhaseResolveAPIs:
            self.currentPhaseName = @"resolveAPIs";
            if ([self resolveAPIs]) self.phase = ScanPhaseFindClasses;
            return;

        case ScanPhaseFindClasses:
            self.currentPhaseName = @"findClasses";
            if ([self findClasses]) self.phase = ScanPhaseCacheOffsets;
            return;

        case ScanPhaseCacheOffsets:
            self.currentPhaseName = @"cacheOffsets";
            if ([self cacheOffsets]) self.phase = ScanPhaseWaitInstance;
            return;

        case ScanPhaseWaitInstance: {
            self.currentPhaseName = @"waitInstance";
            void *instance = NULL;
            if (fh_Instance && _field_static_get_value) {
                _field_static_get_value(fh_Instance, &instance);
            }
            if (instance) {
                NSLog(@"[SpinLogger] SlotMachineManager.Instance acquired: %p", instance);
                self.phase = ScanPhaseActive;
            }
            return;
        }

        case ScanPhaseActive:
            self.currentPhaseName = @"active";
            [self traceScan];
            return;
    }
}
```

**Step 3: Delete the old `activeScan`, `readSnapshotFromInstance`, and `readBar:...` methods entirely.** They are no longer used — trace mode does not call them. Also remove the SLScanSnapshot fields that are no longer populated (keep `timestamp`, `spinNumber`, `betState`, `spinning` for HUD compatibility; delete the `top1..3`, `bot1..3`, `stripIdx1..3`, `stripLen1..3`, `failCounter`, `failCounterGlobal`, `failThreshold`, `shields`, `hasDynamicResults`, `hasFreezeContext`, `hasNearWin`, `hasReplacements` properties from `SLScanSnapshot` in `src/SLMemoryScanner.h`).

Wait — the HUD panel (`src/SLSignalPanel.m`) currently reads some of these. Before deleting fields on `SLScanSnapshot`, read `src/SLSignalPanel.m` to see which it reads, and either (a) stub them to return safe defaults, or (b) update the HUD in Task 1.8. Go with (b).

For this task, leave the `SLScanSnapshot` header unchanged and just stop populating the deleted fields. Task 1.8 handles the HUD.

**Step 4: Commit.**

```bash
git add src/SLMemoryScanner.m
git commit -m "feat: wire traceScan into state machine, write JSONL records"
```

---

### Task 1.8: Update HUD panel to display trace counters

**Files:**
- Modify: `src/SLSignalPanel.m`

**Step 1: Read `src/SLSignalPanel.m`** to understand the current layout (368 lines per commit 5dd5a1f).

**Step 2: Replace the snapshot-display block with a trace-counter display.** Locate the method that subscribes to `SLMemoryScanNotification` or reads `SLMemoryScanner.shared.latestSnapshot`. Replace the per-field label updates with a single 2-line summary:

```
IL2CPP TRACE
phase: active · spins: 47 · snaps: 1124 · 42.1 MB
```

Concrete implementation sketch (adapt to the existing label/constraint layout in `SLSignalPanel.m`):

```objc
- (void)refreshTraceLabels {
    SLMemoryScanner *s = [SLMemoryScanner shared];
    self.phaseLabel.text = [NSString stringWithFormat:@"phase: %@", s.currentPhaseName ?: @"?"];
    self.countsLabel.text = [NSString stringWithFormat:
        @"spins: %lld · snaps: %lld · %.1f MB",
        s.spinsSeen, s.snapshotsWritten, s.bytesWritten / 1048576.0];
}
```

And kick off a 1 Hz refresh timer from `- (void)install`:

```objc
[NSTimer scheduledTimerWithTimeInterval:1.0
                                target:self
                              selector:@selector(refreshTraceLabels)
                              userInfo:nil
                               repeats:YES];
```

**Step 3: Remove the labels that showed parsed sym/top/bot/idx fields** from the panel — they were reading garbage anyway. Leave only the phase + counts lines.

**Step 4: Commit.**

```bash
git add src/SLSignalPanel.m
git commit -m "feat: repurpose signal HUD to show trace counters"
```

---

### Task 1.9: Push Phase 1 and verify via CI + device run

**Step 1:** Push all Phase 1 commits:

```bash
git push origin main
```

**Step 2:** Wait for GitHub Actions to produce `SpinLogger.dylib`. Download the artifact, install on device, launch Coin Master, play **3–5 spins** as a smoke test.

**Step 3: Verify on device:**
1. The HUD shows `phase: active` within 10 seconds of app launch.
2. The `snaps:` counter increments continuously (every ~250 ms).
3. The `spins:` counter increments when you finish a spin.
4. `Documents/il2cpp_trace_<timestamp>.jsonl` exists and is growing.

**Step 4: Pull the JSONL off the device** (Filza / iTunes File Sharing / SSH) and open the first few lines. Verify:
1. Each line parses as valid JSON.
2. The top-level keys `t`, `mono_ms`, `spin_num`, `spinning`, `fields`, `hex` are present.
3. `fields.SlotMachineManager` contains an object with many field names (e.g. `spinning`, `betState`, `currentSpinNumber`, etc.) each with `{off, u64, i32, ptr}`.
4. `hex.slotBar1@0x...` is a ~512-char hex string.
5. `fields["SlotResult@0x..."]` exists (pointer follow worked).

If any of these fail, fix in a follow-up task before continuing to Phase 2. Phase 1 is only "done" once this verification passes.

---

## Phase 2 — Offline analyzer (Python, TDD)

### Task 2.1: Set up analyzer skeleton + pytest fixture

**Files:**
- Create: `analysis/nuclear/50_il2cpp_trace_decode.py`
- Create: `analysis/nuclear/tests/__init__.py`
- Create: `analysis/nuclear/tests/test_trace_decode.py`
- Create: `analysis/nuclear/tests/fixtures/tiny_trace.jsonl`
- Create: `analysis/nuclear/tests/fixtures/tiny_spin_history.csv`

**Step 1: Create the test fixture `tests/fixtures/tiny_trace.jsonl`** with 3 fake spins (≈10 snapshots per spin) covering: idle → spinning → settled. Use small but realistic data so stage 2 has something to match. Example structure (one line abbreviated — fill in the rest):

```json
{"t": "2026-04-11T05:13:25", "mono_ms": 0, "spin_num": 64200, "spinning": false, "bet_state": 1, "phase": "active", "instance_ptr": "0x10d8a4200", "fields": {"SlotMachineManager": {"currentSpinNumber": {"off": 416, "u64": 64200, "i32": 64200, "ptr": "0xfac8"}, "m_SpinFailedCounterGlobal": {"off": 484, "u64": 3, "i32": 3, "ptr": "0x3"}}, "SlotResult@0x1": {"slotSymbols": {"off": 16, "u64": 2, "i32": 2, "ptr": "0x2"}}, "SlotSymbol3@0x2": {"symbol1": {"off": 16, "u64": 1, "i32": 1, "ptr": "0x1"}, "symbol2": {"off": 20, "u64": 1, "i32": 1, "ptr": "0x1"}, "symbol3": {"off": 24, "u64": 4, "i32": 4, "ptr": "0x4"}}}, "hex": {"slotBar1.m_SymbolElements@0x10": {"array_len": 9, "header_size": 32, "bytes": "00000000000000000000000000000000000000000000000000000000000000000100000000000000020000000000000003000000000000000400000000000000050000000000000006000000000000001e000000000000000100000000000000"}}}
```

Build it to encode: spin 64200 has payline (1, 1, 4). Include matching rows in `tiny_spin_history.csv`:

```
seq,timestamp,r1,r2,r3,reel_1,reel_2,reel_3,spin_result,is_triple
64200,2026-04-11 05:13:25,1,1,4,coin,coin,steal,gold,false
64201,2026-04-11 05:13:27,30,2,2,accumulation,goldSack,goldSack,gold,false
64202,2026-04-11 05:13:29,3,3,3,attack,attack,attack,attack,true
```

**Step 2: Create `50_il2cpp_trace_decode.py` skeleton** with CLI argparse and stage stubs:

```python
#!/usr/bin/env python3
"""IL2CPP trace decoder — reverse engineer memory layouts against spin_history ground truth.

Six stages:
    1. Load & segment   - group JSONL snapshots by spin_num
    2. Payline sanity   - validate sym1/2/3 chain matches spin_history r1/r2/r3
    3. Field change-map - find fields that correlate with spin_history columns
    4. Strip decoder    - lock (stride, inner_offset) for m_SymbolElements
    5. Pity counter hunt - find offsets for real session + global pity counters
    6. Report           - write layout report to 50_il2cpp_layout_report.md
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class Snapshot:
    t: str
    mono_ms: int
    spin_num: int
    spinning: bool
    bet_state: int
    phase: str
    instance_ptr: str
    fields: dict
    hex: dict


@dataclass
class Spin:
    spin_num: int
    animation: List[Snapshot] = field(default_factory=list)
    settled: Optional[Snapshot] = None


def load_jsonl(path: Path) -> List[Snapshot]:
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out.append(Snapshot(**{k: d.get(k) for k in Snapshot.__dataclass_fields__}))
    return out


def segment_by_spin(snaps: List[Snapshot]) -> Dict[int, Spin]:
    buckets: Dict[int, Spin] = {}
    for s in snaps:
        sp = buckets.setdefault(s.spin_num, Spin(spin_num=s.spin_num))
        if s.spinning:
            sp.animation.append(s)
        else:
            # A settled snapshot supersedes any earlier settled one in this spin
            sp.settled = s
    return buckets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, type=Path, help="Path to JSONL trace file")
    ap.add_argument("--spin-history", required=True, type=Path, help="Ground-truth spin_history CSV")
    ap.add_argument("--report", default=Path("50_il2cpp_layout_report.md"), type=Path)
    args = ap.parse_args()

    snaps = load_jsonl(args.trace)
    buckets = segment_by_spin(snaps)
    print(f"Loaded {len(snaps)} snapshots across {len(buckets)} spins")


if __name__ == "__main__":
    main()
```

**Step 3: Create `tests/test_trace_decode.py` with the first two tests:**

```python
import importlib.util
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"
MOD_PATH = Path(__file__).parent.parent / "50_il2cpp_trace_decode.py"

# importlib because the filename starts with a digit
spec = importlib.util.spec_from_file_location("trace_decode", MOD_PATH)
trace_decode = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace_decode)


def test_load_jsonl_returns_snapshots():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    assert len(snaps) >= 3
    assert all(hasattr(s, "spin_num") for s in snaps)


def test_segment_groups_by_spin_num():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    buckets = trace_decode.segment_by_spin(snaps)
    assert 64200 in buckets
    assert buckets[64200].settled is not None
```

**Step 4: Run the tests.**

```bash
pytest analysis/nuclear/tests/test_trace_decode.py -v
```

Expected: both tests PASS.

**Step 5: Commit.**

```bash
git add analysis/nuclear/50_il2cpp_trace_decode.py analysis/nuclear/tests/
git commit -m "feat: trace decoder skeleton + load/segment + tests"
```

---

### Task 2.2: Implement Stage 2 — payline sanity gate

**Files:**
- Modify: `analysis/nuclear/50_il2cpp_trace_decode.py`
- Modify: `analysis/nuclear/tests/test_trace_decode.py`

**Step 1: Write the failing test first:**

```python
def test_payline_sanity_matches_ground_truth():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    buckets = trace_decode.segment_by_spin(snaps)
    import pandas as pd
    hist = pd.read_csv(FIX / "tiny_spin_history.csv")
    result = trace_decode.stage2_payline_sanity(buckets, hist)
    # Fixture is crafted so all 3 spins match
    assert result["match_rate"] == 1.0
    assert result["n_spins_checked"] == 3
    assert result["mismatches"] == []
```

**Step 2: Run it to confirm it fails** (`stage2_payline_sanity` doesn't exist yet).

```bash
pytest analysis/nuclear/tests/test_trace_decode.py::test_payline_sanity_matches_ground_truth -v
```

Expected: FAIL with `AttributeError: module 'trace_decode' has no attribute 'stage2_payline_sanity'`.

**Step 3: Implement the function:**

```python
def _extract_payline_from_settled(snap: Snapshot) -> Optional[tuple]:
    """Walk fields → SlotResult → SlotSymbol3 → symbol1/2/3 → return (s1,s2,s3) or None."""
    for key, cls_fields in snap.fields.items():
        if key.startswith("SlotSymbol3@"):
            try:
                return (
                    cls_fields["symbol1"]["i32"],
                    cls_fields["symbol2"]["i32"],
                    cls_fields["symbol3"]["i32"],
                )
            except KeyError:
                return None
    return None


def stage2_payline_sanity(buckets: Dict[int, Spin], hist: pd.DataFrame) -> dict:
    """Cross-reference memory payline (sym1/2/3) with spin_history r1/r2/r3."""
    checked = 0
    matches = 0
    mismatches = []
    hist_lookup = hist.set_index("seq")[["r1", "r2", "r3"]].to_dict("index")

    for spin_num, spin in buckets.items():
        if spin.settled is None:
            continue
        mem = _extract_payline_from_settled(spin.settled)
        if mem is None:
            continue
        if spin_num not in hist_lookup:
            continue
        checked += 1
        gt = hist_lookup[spin_num]
        if mem == (gt["r1"], gt["r2"], gt["r3"]):
            matches += 1
        else:
            mismatches.append({"spin_num": spin_num, "mem": mem, "hist": gt})

    return {
        "n_spins_checked": checked,
        "n_matches": matches,
        "match_rate": matches / checked if checked else 0.0,
        "mismatches": mismatches,
    }
```

**Step 4: Re-run the test — should PASS.**

```bash
pytest analysis/nuclear/tests/test_trace_decode.py::test_payline_sanity_matches_ground_truth -v
```

Expected: PASS.

**Step 5: Commit.**

```bash
git add analysis/nuclear/50_il2cpp_trace_decode.py analysis/nuclear/tests/test_trace_decode.py
git commit -m "feat: stage 2 payline sanity gate + test"
```

---

### Task 2.3: Implement Stage 3 — field change-map

**Files:**
- Modify: `analysis/nuclear/50_il2cpp_trace_decode.py`
- Modify: `analysis/nuclear/tests/test_trace_decode.py`

**Step 1: Failing test** — the tiny fixture has `m_SpinFailedCounterGlobal` values 3, 4, 0 across the 3 spins (make sure your fixture actually has this pattern, edit if needed). The change-map should classify it as `resetting_counter`.

```python
def test_stage3_classifies_counter_field():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    buckets = trace_decode.segment_by_spin(snaps)
    import pandas as pd
    hist = pd.read_csv(FIX / "tiny_spin_history.csv")
    report = trace_decode.stage3_field_change_map(buckets, hist)
    entry = next(r for r in report if r["field"] == "m_SpinFailedCounterGlobal")
    assert entry["type_guess"] in ("counter_like", "resetting_counter")
    assert entry["unique_count"] >= 2
```

Run: should FAIL.

**Step 2: Implement:**

```python
def stage3_field_change_map(buckets: Dict[int, Spin], hist: pd.DataFrame) -> list:
    """For every (class, field) pair observed in settled snapshots, classify behavior."""
    # Collect time series per (class, field)
    series: Dict[tuple, List[tuple]] = {}  # (class_name, field_name) -> [(spin_num, i32), ...]
    for spin_num in sorted(buckets):
        settled = buckets[spin_num].settled
        if settled is None:
            continue
        for class_key, cls_fields in settled.fields.items():
            class_name = class_key.split("@", 1)[0]
            for fname, fdata in cls_fields.items():
                series.setdefault((class_name, fname), []).append(
                    (spin_num, fdata["i32"], fdata["u64"], fdata["ptr"])
                )

    # Ground truth columns from spin_history for correlation
    hist_lookup = hist.set_index("seq")

    out = []
    for (cls, fname), points in series.items():
        vals = [p[1] for p in points]  # i32 interpretation
        uniq = set(vals)
        is_constant = len(uniq) == 1
        unique_count = len(uniq)

        # Type guess
        if is_constant:
            type_guess = "constant"
        elif all(0 <= v <= 1 for v in vals):
            type_guess = "bool_like"
        elif all(1 <= v <= 50 for v in vals):
            type_guess = "symbol_like"
        elif all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1)):
            type_guess = "counter_like"
        elif any(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
            type_guess = "resetting_counter"
        else:
            type_guess = "unknown"

        # Equality match-rate against r1/r2/r3 and other columns
        correlations = {}
        for col in ("r1", "r2", "r3", "is_triple", "sa_spins", "coins_won", "bet_level"):
            if col not in hist_lookup.columns:
                continue
            matches = 0
            checked = 0
            for spin_num, i32, u64, ptr in points:
                if spin_num not in hist_lookup.index:
                    continue
                checked += 1
                gt = hist_lookup.loc[spin_num, col]
                if gt == i32 or gt == u64:
                    matches += 1
            if checked:
                correlations[col] = matches / checked

        out.append({
            "class": cls,
            "field": fname,
            "is_constant": is_constant,
            "unique_count": unique_count,
            "type_guess": type_guess,
            "correlations": correlations,
        })

    # Sort: most interesting first (not constant, has correlation)
    out.sort(key=lambda r: (
        r["is_constant"],
        -max(r["correlations"].values()) if r["correlations"] else 0,
    ))
    return out
```

**Step 3: Re-run the test — should PASS.**

**Step 4: Commit.**

```bash
git add analysis/nuclear/50_il2cpp_trace_decode.py analysis/nuclear/tests/test_trace_decode.py
git commit -m "feat: stage 3 field change-map + classification + test"
```

---

### Task 2.4: Implement Stage 4 — strip decoder

**Files:**
- Modify: `analysis/nuclear/50_il2cpp_trace_decode.py`
- Modify: `analysis/nuclear/tests/test_trace_decode.py`

**Step 1: Failing test.** In the fixture, craft `slotBar1.m_SymbolElements` hex so that element at index (from some settled snapshot's `resultSymbolIndex`) equals `r1` — use stride=8, inner_offset=0. That way the correct answer is `(8, 0)`.

```python
def test_stage4_decodes_strip_stride_and_offset():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    buckets = trace_decode.segment_by_spin(snaps)
    import pandas as pd
    hist = pd.read_csv(FIX / "tiny_spin_history.csv")
    result = trace_decode.stage4_strip_decoder(buckets, hist, reel=1)
    assert result["stride"] == 8
    assert result["inner_offset"] == 0
    assert result["match_rate"] >= 0.9
```

Run: should FAIL.

**Step 2: Implement:**

```python
def _unpack_array_bytes(hex_blob: dict, stride: int, inner_offset: int, array_len: int) -> List[int]:
    """Return list of ints decoded from the array payload using (stride, inner_offset)."""
    raw = bytes.fromhex(hex_blob["bytes"])
    header = hex_blob["header_size"]
    out = []
    for i in range(array_len):
        start = header + i * stride + inner_offset
        if start + 4 > len(raw):
            out.append(None)
            continue
        out.append(int.from_bytes(raw[start:start + 4], "little", signed=True))
    return out


def stage4_strip_decoder(buckets: Dict[int, Spin], hist: pd.DataFrame, reel: int) -> dict:
    """Find (stride, inner_offset) for m_SymbolElements on bar<reel>."""
    hist_lookup = hist.set_index("seq")
    r_col = f"r{reel}"
    candidates = [(s, o) for s in (4, 8, 12, 16, 24, 32) for o in (0, 4, 8, 12, 16)]

    def score(stride: int, inner_offset: int) -> tuple[int, int]:
        hits = 0
        checked = 0
        for spin_num, spin in buckets.items():
            if spin.settled is None or spin_num not in hist_lookup.index:
                continue
            gt = hist_lookup.loc[spin_num, r_col]
            # Find the m_SymbolElements hex blob for this reel
            hex_key = next(
                (k for k in spin.settled.hex if k.startswith(f"slotBar{reel}.m_SymbolElements@")),
                None,
            )
            if hex_key is None:
                continue
            blob = spin.settled.hex[hex_key]
            if not isinstance(blob, dict):
                continue
            # Find the bar's resultSymbolIndex
            bar_key = next(
                (k for k in spin.settled.fields if k.startswith(f"SlotBarManager_{reel}@")),
                None,
            )
            if bar_key is None:
                continue
            idx = spin.settled.fields[bar_key].get("resultSymbolIndex", {}).get("i32")
            if idx is None:
                continue
            elements = _unpack_array_bytes(blob, stride, inner_offset, blob["array_len"])
            if 0 <= idx < len(elements) and elements[idx] == gt:
                hits += 1
            checked += 1
        return hits, checked

    best = {"stride": None, "inner_offset": None, "match_rate": 0.0, "hits": 0, "checked": 0}
    for stride, inner_offset in candidates:
        hits, checked = score(stride, inner_offset)
        if checked == 0:
            continue
        rate = hits / checked
        if rate > best["match_rate"]:
            best = {
                "stride": stride,
                "inner_offset": inner_offset,
                "match_rate": rate,
                "hits": hits,
                "checked": checked,
            }
    return best
```

**Step 3: Re-run the test — should PASS.**

**Step 4: Commit.**

```bash
git add analysis/nuclear/50_il2cpp_trace_decode.py analysis/nuclear/tests/test_trace_decode.py
git commit -m "feat: stage 4 strip decoder + test"
```

---

### Task 2.5: Implement Stage 5 — pity counter hunt

**Files:**
- Modify: `analysis/nuclear/50_il2cpp_trace_decode.py`
- Modify: `analysis/nuclear/tests/test_trace_decode.py`

**Step 1: Failing test.** Fixture: spin 64200 → counter=3 (non-triple), 64201 → counter=4 (non-triple), 64202 → counter=0 (triple — resets). That matches the `resetting_counter` profile.

```python
def test_stage5_identifies_pity_counter():
    snaps = trace_decode.load_jsonl(FIX / "tiny_trace.jsonl")
    buckets = trace_decode.segment_by_spin(snaps)
    import pandas as pd
    hist = pd.read_csv(FIX / "tiny_spin_history.csv")
    report = trace_decode.stage5_pity_counter_hunt(buckets, hist, fail_threshold=8)
    assert len(report) >= 1
    top = report[0]
    assert top["field"] == "m_SpinFailedCounterGlobal"
    assert top["resets_on_triple"]
    assert top["monotonic_between_triples"]
```

Run: FAIL.

**Step 2: Implement:**

```python
def stage5_pity_counter_hunt(buckets: Dict[int, Spin], hist: pd.DataFrame, fail_threshold: int) -> list:
    """Identify pity counter candidates by monotonic + reset behavior."""
    hist_lookup = hist.set_index("seq")
    # Build ordered spin list with ground-truth is_triple
    ordered = sorted(buckets.keys())
    triple_map = {s: bool(hist_lookup.loc[s, "is_triple"])
                  for s in ordered if s in hist_lookup.index and "is_triple" in hist_lookup.columns}

    # Build per-(class,field) time series from settled i32 values
    series: Dict[tuple, List[tuple]] = {}
    for spin_num in ordered:
        settled = buckets[spin_num].settled
        if settled is None or spin_num not in triple_map:
            continue
        for class_key, cls_fields in settled.fields.items():
            class_name = class_key.split("@", 1)[0]
            for fname, fdata in cls_fields.items():
                series.setdefault((class_name, fname), []).append(
                    (spin_num, fdata["i32"], triple_map[spin_num])
                )

    candidates = []
    for (cls, fname), points in series.items():
        vals = [p[1] for p in points]
        if len(vals) < 3:
            continue
        if len(set(vals)) == 1:
            continue

        # Monotonic between triples: non-triples must be non-decreasing
        non_triple_vals = [v for (_, v, is_tr) in points if not is_tr]
        monotonic = all(non_triple_vals[i] <= non_triple_vals[i + 1]
                        for i in range(len(non_triple_vals) - 1))
        # Resets on triple: whenever is_triple is true, next value drops (or equals 0)
        resets = any(v == 0 for (_, v, is_tr) in points if is_tr)
        max_val = max(vals)
        near_threshold = max_val <= fail_threshold + 2

        if monotonic and resets and near_threshold:
            candidates.append({
                "class": cls,
                "field": fname,
                "monotonic_between_triples": True,
                "resets_on_triple": True,
                "max_value": max_val,
                "n_samples": len(points),
            })

    # Rank by: matches near threshold, then sample size
    candidates.sort(key=lambda c: (-c["n_samples"], abs(c["max_value"] - fail_threshold)))
    return candidates
```

**Step 3: Re-run — should PASS.**

**Step 4: Commit.**

```bash
git add analysis/nuclear/50_il2cpp_trace_decode.py analysis/nuclear/tests/test_trace_decode.py
git commit -m "feat: stage 5 pity counter hunt + test"
```

---

### Task 2.6: Implement Stage 6 — report writer + main wiring

**Files:**
- Modify: `analysis/nuclear/50_il2cpp_trace_decode.py`
- Modify: `analysis/nuclear/tests/test_trace_decode.py`

**Step 1: Add a failing smoke test for `main`.**

```python
def test_end_to_end_writes_report(tmp_path):
    out = tmp_path / "report.md"
    import sys
    sys.argv = [
        "trace_decode",
        "--trace", str(FIX / "tiny_trace.jsonl"),
        "--spin-history", str(FIX / "tiny_spin_history.csv"),
        "--report", str(out),
    ]
    trace_decode.main()
    assert out.exists()
    body = out.read_text()
    assert "# IL2CPP Layout Report" in body
    assert "Stage 2" in body
    assert "Stage 4" in body
```

Run: FAIL (main doesn't call stages or write report).

**Step 2: Implement Stage 6 report writer:**

```python
def stage6_write_report(
    out_path: Path,
    stage2: dict,
    stage3: list,
    stage4_by_reel: Dict[int, dict],
    stage5: list,
) -> None:
    lines = []
    lines.append("# IL2CPP Layout Report")
    lines.append("")
    lines.append("Auto-generated by `50_il2cpp_trace_decode.py`.")
    lines.append("")

    lines.append("## Stage 2 — Payline sanity gate")
    lines.append("")
    lines.append(f"- Spins checked: **{stage2['n_spins_checked']}**")
    lines.append(f"- Matches: **{stage2['n_matches']}**")
    lines.append(f"- Match rate: **{stage2['match_rate']:.1%}**")
    if stage2["mismatches"]:
        lines.append(f"- First 5 mismatches: `{stage2['mismatches'][:5]}`")
    lines.append("")

    lines.append("## Stage 4 — Strip decoder")
    lines.append("")
    for reel, result in stage4_by_reel.items():
        lines.append(f"### Reel {reel}")
        lines.append(f"- stride: `{result['stride']}`")
        lines.append(f"- inner_offset: `{result['inner_offset']}`")
        lines.append(f"- match rate: **{result['match_rate']:.1%}**")
        lines.append(f"- hits: {result['hits']} / {result['checked']}")
        lines.append("")

    lines.append("## Stage 5 — Pity counter candidates")
    lines.append("")
    for c in stage5[:5]:
        lines.append(f"- `{c['class']}.{c['field']}` — max={c['max_value']}, samples={c['n_samples']}")
    lines.append("")

    lines.append("## Stage 3 — Top 20 interesting fields")
    lines.append("")
    for row in stage3[:20]:
        best_corr = max(row["correlations"].items(), key=lambda kv: kv[1], default=("—", 0.0))
        lines.append(
            f"- `{row['class']}.{row['field']}` — "
            f"{row['type_guess']}, unique={row['unique_count']}, "
            f"best match: {best_corr[0]}={best_corr[1]:.0%}"
        )
    lines.append("")

    out_path.write_text("\n".join(lines))
```

**Step 3: Wire into main:**

```python
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, type=Path)
    ap.add_argument("--spin-history", required=True, type=Path)
    ap.add_argument("--report", default=Path("50_il2cpp_layout_report.md"), type=Path)
    ap.add_argument("--fail-threshold", type=int, default=8)
    args = ap.parse_args()

    snaps = load_jsonl(args.trace)
    buckets = segment_by_spin(snaps)
    print(f"Loaded {len(snaps)} snapshots across {len(buckets)} spins")

    hist = pd.read_csv(args.spin_history)

    stage2 = stage2_payline_sanity(buckets, hist)
    print(f"Stage 2 match rate: {stage2['match_rate']:.1%}")

    stage3 = stage3_field_change_map(buckets, hist)
    print(f"Stage 3 profiled {len(stage3)} fields")

    stage4 = {
        reel: stage4_strip_decoder(buckets, hist, reel=reel)
        for reel in (1, 2, 3)
    }
    for reel, r in stage4.items():
        print(f"Stage 4 reel {reel}: stride={r['stride']}, offset={r['inner_offset']}, "
              f"match={r['match_rate']:.1%}")

    stage5 = stage5_pity_counter_hunt(buckets, hist, fail_threshold=args.fail_threshold)
    print(f"Stage 5 found {len(stage5)} pity counter candidates")

    stage6_write_report(args.report, stage2, stage3, stage4, stage5)
    print(f"Report written to {args.report}")
```

**Step 4: Re-run the e2e test — should PASS.**

**Step 5: Commit.**

```bash
git add analysis/nuclear/50_il2cpp_trace_decode.py analysis/nuclear/tests/test_trace_decode.py
git commit -m "feat: stage 6 report writer + end-to-end main wiring"
```

---

### Task 2.7: Push Phase 2

```bash
git push origin main
```

Run the full test suite one more time before pushing:

```bash
pytest analysis/nuclear/tests/ -v
```

All tests should pass. If any fail, fix before pushing.

---

## Phase 3 — Live capture session + analysis

### Task 3.1: Collect a live trace

**Prerequisites:** Phase 1 has been deployed to a device, HUD shows `phase: active` and counters incrementing.

**Step 1:** Close Coin Master if running. Launch it fresh.

**Step 2:** Wait for the HUD to show `phase: active`. Confirm the trace file exists at `Documents/il2cpp_trace_<timestamp>.jsonl`.

**Step 3:** Play at least **150 spins**. Mix of outcomes: aim for at least 3 triples (to validate pity counter reset). Ordinary spins, some wins, some losses. Vary bet levels if comfortable.

**Step 4:** When the `spins:` counter reads ≥150 on the HUD, force-quit Coin Master to close the trace file cleanly (scanner's `dealloc` won't run, but GCD will have flushed most writes; the last 1–2 snapshots may be lost — acceptable).

**Step 5:** Pull the JSONL file and the matching `spin_history_<date>.csv` off the device to the repo working dir:

```
data/Islam/il2cpp_trace_<timestamp>.jsonl
data/Islam/spin_history_<date>.csv
```

**Step 6:** Confirm both files are present and roughly the right sizes (JSONL should be tens to hundreds of MB; spin_history should have ≥150 new rows since the capture start time).

No commit — these are captured data files. Leave them in `data/Islam/` for analysis.

---

### Task 3.2: Run the analyzer on real data

**Step 1:** From repo root:

```bash
python analysis/nuclear/50_il2cpp_trace_decode.py \
    --trace data/Islam/il2cpp_trace_<timestamp>.jsonl \
    --spin-history data/Islam/spin_history_<date>.csv \
    --report analysis/nuclear/50_il2cpp_layout_report.md
```

**Step 2: Read the report output.** Check each gate:

- Stage 2 match rate ≥ 95%. If not:
  - If 0%: scanner is reading the wrong instance or the payline extraction logic is wrong. Inspect `_extract_payline_from_settled` against a real snapshot.
  - If 50–94%: probably stale-memory reads on spin-end. Fix in Task 3.3 by shifting the "settled" snapshot pick forward by 1–2 polls.
- Stage 4 match rate ≥ 90% for all three reels. If not:
  - Widen the `(stride, inner_offset)` candidate grid in `stage4_strip_decoder`. Try strides up to 64 and inner_offsets up to 32.
  - If still failing, fall back: dump one spin's `m_SymbolElements` hex manually and stare at it alongside the known `r1`. This might reveal the layout is a struct-of-structs or has an unexpected header size.
- Stage 5 produces ≥1 candidate with monotonic + reset evidence.

**Step 3:** Commit the report regardless of outcome (it's evidence):

```bash
git add analysis/nuclear/50_il2cpp_layout_report.md
git commit -m "analysis: first IL2CPP trace layout report"
git push origin main
```

---

### Task 3.3: Iterate on gate failures (conditional)

**If Stage 2 or Stage 4 failed in Task 3.2**, this task iterates the trace mode and/or the analyzer and re-runs the capture. Repeat until both gates pass.

Common iterations:

1. **Stale payline** → modify Stage 1 to pick the settled snapshot as "the last snapshot where `spinning=false` AND `currentSlotResult_ptr` has changed from the previous settled snapshot". This catches the case where `spinning` flips false before the result has been updated.

2. **No valid strip decode for all three reels** → widen the candidate grid, or add a new stage 4b that follows the `m_SymbolElements[i]` pointers (if elements are reference types) and reads an int field at every offset within the referenced struct.

3. **Pointer follow missing** → add another class to the known list (e.g. `SpinResultScreen`, `SlotBarAnimator`). The Stage 3 output will often hint at which missing class is needed (a field in `SlotMachineManager` with `type_guess=unknown` and a valid-looking `ptr` that we didn't follow).

Each iteration = push + rebuild + new capture + new report + commit. Track iterations in commit messages: `analysis: trace iteration 2 — fix stale payline`.

---

### Task 3.4: Final sign-off

**Step 1:** Confirm the final report has:
- Stage 2 ≥ 95%
- Stage 4 ≥ 90% for all three reels
- Stage 5 has a confirmed pity counter

**Step 2:** The report's "Stage 4" section contains the numbers needed to rewrite the live scanner. Specifically:
- Confirmed `(stride, inner_offset)` for `m_SymbolElements`
- Confirmed ring-indexing formula for top/bot
- Confirmed pity counter class + field name + offset

**Step 3:** This plan is complete. The next plan (out of scope here) uses these confirmed values to rewrite the live scanner and delete trace mode. Write that follow-up plan with `writing-plans` after reviewing the report.

---

## Summary of deliverables

- **Phase 1 (Obj-C):** 9 commits converting the scanner into trace mode, verified on device.
- **Phase 2 (Python):** 7 commits building and testing the analyzer against a fixture.
- **Phase 3 (capture + analyze):** 1–4 commits depending on iteration count, ending with `50_il2cpp_layout_report.md` committed.

Files touched in the repo:

- `src/SLConstants.h` (modified)
- `src/SLMemoryScanner.h` (modified)
- `src/SLMemoryScanner.m` (heavily modified — phase 4 only)
- `src/SLSignalPanel.m` (modified — HUD repurposed)
- `analysis/nuclear/50_il2cpp_trace_decode.py` (new)
- `analysis/nuclear/tests/__init__.py` (new)
- `analysis/nuclear/tests/test_trace_decode.py` (new)
- `analysis/nuclear/tests/fixtures/tiny_trace.jsonl` (new)
- `analysis/nuclear/tests/fixtures/tiny_spin_history.csv` (new)
- `analysis/nuclear/50_il2cpp_layout_report.md` (new — generated)
- `data/Islam/il2cpp_trace_<timestamp>.jsonl` (new — captured)
- `data/Islam/spin_history_<date>.csv` (new — captured, produced by the game during the session)
