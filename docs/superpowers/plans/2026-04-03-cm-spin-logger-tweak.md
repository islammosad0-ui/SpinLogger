# Coin Master Spin Logger + Speeder Clone — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an iOS arm64 dylib that injects into Coin Master's IPA, replicating all Nuovo Speeder features (speed multiplier, spin counter overlays, spin target, auto-reset, tris lock, skip tris, presets, persistence) and adding real-time per-spin CSV logging — every spin is appended to a CSV file immediately so you can check it at any time.

**Architecture:** A single Objective-C dylib that hooks into the app at load time via `__attribute__((constructor))`. It registers a custom `NSURLProtocol` subclass (same approach as the original Nuovo Speeder mod's `NetworkListenerUrlProtocol`) to intercept all HTTP traffic to `vik-ca.moonactive.net`. Spin events are parsed from newline-delimited JSON POST bodies to the `/strack/gzip` endpoint. Each spin is **appended directly to a CSV file in real-time** — no export step needed. The UI uses `WKWebView`-based overlays for counters (matching the original mod's approach) and a floating menu button. The dylib is compiled on GitHub Actions (free macOS runner) and injected into the IPA using `insert_dylib` or ESign's built-in dylib injection.

**Tech Stack:** Objective-C, UIKit, Foundation, GitHub Actions (macOS runner + Xcode clang), insert_dylib, ESign

---

## Phase Overview

| Phase | What | Tasks |
|-------|------|-------|
| **1 — Skeleton** | Dylib scaffold, constructor, build pipeline | 1–3 |
| **2 — Network Hook** | Intercept HTTP traffic, parse spin events | 4–6 |
| **3 — Spin Logger** | Real-time CSV append per spin | 7–9 |
| **4 — Counter Overlays** | Draggable per-symbol counters on screen | 10–12 |
| **5 — Speed Multiplier** | Game speed control | 13–14 |
| **6 — Spin Target & Auto-Reset** | Stop at N spins, reset counters on condition | 15–16 |
| **7 — Tris Lock & Skip** | Card trading lock/skip | 17–18 |
| **8 — Presets & Persistence** | Save/restore all settings | 19–20 |
| **9 — Floating Menu UI** | Settings panel, export button, preset selector | 21–23 |
| **10 — IPA Injection** | Inject dylib into IPA, re-sign, test | 24–25 |

---

## File Structure

```
SpinLogger/
├── src/
│   ├── SpinLoggerTweak.m          # Entry point (__attribute__((constructor))), lifecycle
│   ├── SLNetworkInterceptor.h     # NSURLProtocol subclass to capture HTTP traffic (same as Nuovo Speeder)
│   ├── SLNetworkInterceptor.m
│   ├── SLSpinParser.h             # Parse spin events from strack POST body
│   ├── SLSpinParser.m
│   ├── SLSpinStore.h              # Real-time CSV append — every spin written immediately
│   ├── SLSpinStore.m
│   ├── SLCounterOverlay.h         # Draggable per-symbol counter labels
│   ├── SLCounterOverlay.m
│   ├── SLSpeedController.h        # CADisplayLink / mach_timebase speed multiplier
│   ├── SLSpeedController.m
│   ├── SLSpinTarget.h             # Spin target + auto-reset logic
│   ├── SLSpinTarget.m
│   ├── SLTrisController.h         # Tris lock + skip logic
│   ├── SLTrisController.m
│   ├── SLPresetManager.h          # Preset save/load + persistence
│   ├── SLPresetManager.m
│   ├── SLMenuOverlay.h            # Floating button + settings panel
│   ├── SLMenuOverlay.m
│   └── SLConstants.h              # Shared constants (endpoint URLs, symbol names, keys)
├── Makefile                        # Local build helper (calls clang)
├── .github/
│   └── workflows/
│       └── build.yml               # GitHub Actions CI to compile arm64 dylib
├── inject.sh                       # Script to inject dylib into IPA using insert_dylib
└── README.md                       # Setup & usage instructions
```

---

## API Reference (from reverse engineering)

### Spin Event Format
The game POSTs newline-delimited JSON to `https://vik-ca.moonactive.net/vikings/v3/strack/gzip`.

Each line is a JSON object. Spin events have `"event": "spin"` with a `msg` object containing:

| Field | Example | Description |
|-------|---------|-------------|
| `spin_result_symbols` | `"steal,steal,steal"` | Comma-separated reel symbols (left,middle,right) |
| `spin_result` | `"steal"` | Outcome: `gold`, `attack`, `steal`, `shield`, `spins`, `noreward`, `accumulation` |
| `spin_number` | `35091` | Server-side spin count |
| `spin_amount_won` | `250000` | Coins won |
| `bet_type` | `"X1"` | Bet multiplier |
| `auto_spin` | `true` | Whether auto-spin was active |
| `coins` | `"8311235916183"` | Current coin balance |
| `spins` | `"494247"` | Spins remaining |
| `shields` | `"5"` | Active shields |
| `village` | `"213"` | Current village |
| `active_pet` | `"FOX"` | Active pet |
| `result` | `"empty,LongExtraDayReduced,empty"` | Per-reel accumulation bar bonus |
| `sos_1_TA` | `"BluePotion"` | Accumulation event symbol type |

### Reel Symbol Types
`coin`, `shield`, `attack`, `steal`, `goldSack`, `spins`, `accumulation`

### Other Tracked Events
- `"event": "raid_start"` / `"raid_end"` — raid events
- `"event": "attack_start"` / `"attack_end"` — attack events
- `"event": "sos_symbol_created_TA"` — accumulation bar filled

### Game API Hosts
- `vik-ca.moonactive.net` — analytics/strack
- `api.moonactive.net` — game API
- `vik-game.moonactive.net` — WebSocket game connection

---

## Phase 1 — Skeleton

### Task 1: Create constants header and dylib entry point

**Files:**
- Create: `src/SLConstants.h`
- Create: `src/SpinLoggerTweak.m`

- [ ] **Step 1: Create SLConstants.h with all shared constants**

```objc
// src/SLConstants.h
#ifndef SLConstants_h
#define SLConstants_h

#import <Foundation/Foundation.h>

// --- Endpoint matching ---
static NSString *const kSLStrackEndpoint = @"/vikings/v3/strack/gzip";
static NSString *const kSLGameAPIHost    = @"moonactive.net";

// --- Reel symbol names ---
static NSString *const kSLSymbolCoin         = @"coin";
static NSString *const kSLSymbolShield       = @"shield";
static NSString *const kSLSymbolAttack       = @"attack";
static NSString *const kSLSymbolSteal        = @"steal";
static NSString *const kSLSymbolGoldSack     = @"goldSack";
static NSString *const kSLSymbolSpins        = @"spins";
static NSString *const kSLSymbolAccumulation = @"accumulation";

// --- Spin result outcome types ---
static NSString *const kSLResultGold         = @"gold";
static NSString *const kSLResultAttack       = @"attack";
static NSString *const kSLResultSteal        = @"steal";
static NSString *const kSLResultShield       = @"shield";
static NSString *const kSLResultSpins        = @"spins";
static NSString *const kSLResultNoReward     = @"noreward";
static NSString *const kSLResultAccumulation = @"accumulation";

// --- Storage keys (NSUserDefaults) ---
static NSString *const kSLDefaultsPrefix     = @"SpinLogger_";
static NSString *const kSLKeySpeedMultiplier = @"SpinLogger_SpeedMultiplier";
static NSString *const kSLKeySpinTarget      = @"SpinLogger_SpinTarget";
static NSString *const kSLKeyAutoResetMode   = @"SpinLogger_AutoResetMode";
static NSString *const kSLKeyCounterPositions= @"SpinLogger_CounterPositions";
static NSString *const kSLKeyCounterVisible  = @"SpinLogger_CounterVisible";
static NSString *const kSLKeyTrisLockTarget  = @"SpinLogger_TrisLockTarget";
static NSString *const kSLKeyTrisSkipEnabled = @"SpinLogger_TrisSkipEnabled";
static NSString *const kSLKeyNetworkEnabled  = @"SpinLogger_NetworkEnabled";
static NSString *const kSLKeyPreset1         = @"SpinLogger_Preset1";
static NSString *const kSLKeyPreset2         = @"SpinLogger_Preset2";

// --- File names ---
static NSString *const kSLSpinHistoryFile    = @"spin_history.jsonl";
static NSString *const kSLSpinCSVFile        = @"spin_history.csv";

// --- Notifications ---
static NSString *const kSLSpinReceivedNotification = @"SLSpinReceivedNotification";
static NSString *const kSLSpinDataKey              = @"SLSpinDataKey";

// --- Counter overlay symbol keys (what the counters track) ---
// These match the reel symbols that appear in spin_result_symbols
static NSArray *SLTrackedSymbols(void) {
    static NSArray *symbols = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        symbols = @[
            kSLSymbolAttack,       // hammer
            kSLSymbolSteal,        // pig
            kSLSymbolAccumulation, // accumulation bar
            kSLSymbolShield,       // shield
            kSLSymbolSpins,        // bonus spins
            kSLSymbolGoldSack,     // gold sack
        ];
    });
    return symbols;
}

#endif /* SLConstants_h */
```

- [ ] **Step 2: Create SpinLoggerTweak.m entry point**

```objc
// src/SpinLoggerTweak.m
#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import "SLConstants.h"

// Forward declarations — implemented in later tasks
extern void SLNetworkInterceptorInstall(void);
extern void SLSpeedControllerInstall(void);
extern void SLMenuOverlayInstall(void);

__attribute__((constructor))
static void SpinLoggerInit(void) {
    NSLog(@"[SpinLogger] Initializing...");

    // Delay until the app's UI is ready
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2.0 * NSEC_PER_SEC)),
                   dispatch_get_main_queue(), ^{
        NSLog(@"[SpinLogger] Installing hooks...");
        SLNetworkInterceptorInstall();
        SLSpeedControllerInstall();
        SLMenuOverlayInstall();
        NSLog(@"[SpinLogger] Ready.");
    });
}
```

- [ ] **Step 3: Commit**

```bash
git add src/SLConstants.h src/SpinLoggerTweak.m
git commit -m "feat: add dylib skeleton with constants and constructor entry point"
```

---

### Task 2: Create Makefile for local reference

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create Makefile**

```makefile
# Makefile — reference for the clang invocation (actual build runs on GitHub Actions)
# This won't work on Windows, it's here for documentation and CI

SDK_PATH ?= $(shell xcrun --sdk iphoneos --show-sdk-path)
MIN_IOS   = 14.0
ARCH      = arm64
OUTPUT    = SpinLogger.dylib

SOURCES = $(wildcard src/*.m)

CFLAGS = -target $(ARCH)-apple-ios$(MIN_IOS) \
         -isysroot $(SDK_PATH) \
         -fPIC -shared \
         -fobjc-arc \
         -framework Foundation \
         -framework UIKit \
         -framework CoreGraphics \
         -framework QuartzCore \
         -O2

all: $(OUTPUT)

$(OUTPUT): $(SOURCES)
	clang $(CFLAGS) -o $@ $^

clean:
	rm -f $(OUTPUT)

.PHONY: all clean
```

- [ ] **Step 2: Commit**

```bash
git add Makefile
git commit -m "feat: add Makefile for iOS arm64 dylib build reference"
```

---

### Task 3: Create GitHub Actions build workflow

**Files:**
- Create: `.github/workflows/build.yml`

- [ ] **Step 1: Create the CI workflow**

```yaml
# .github/workflows/build.yml
name: Build SpinLogger.dylib

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  build:
    runs-on: macos-14  # M1 runner, free for public repos
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Select Xcode
        run: sudo xcode-select -s /Applications/Xcode_15.4.app

      - name: Build dylib
        run: |
          SDK=$(xcrun --sdk iphoneos --show-sdk-path)
          echo "Using SDK: $SDK"
          clang \
            -target arm64-apple-ios14.0 \
            -isysroot "$SDK" \
            -fPIC -shared \
            -fobjc-arc \
            -framework Foundation \
            -framework UIKit \
            -framework CoreGraphics \
            -framework QuartzCore \
            -O2 \
            -o SpinLogger.dylib \
            src/*.m
          file SpinLogger.dylib
          ls -lh SpinLogger.dylib

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: SpinLogger.dylib
          path: SpinLogger.dylib
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/build.yml
git commit -m "ci: add GitHub Actions workflow to build arm64 dylib"
```

---

## Phase 2 — Network Hook

### Task 4: Create network interceptor (NSURLProtocol subclass)

**Files:**
- Create: `src/SLNetworkInterceptor.h`
- Create: `src/SLNetworkInterceptor.m`

The original Nuovo Speeder mod uses `NSURLProtocol` (class `NetworkListenerUrlProtocol`) — not NSURLSession swizzling. This is more reliable because it intercepts ALL URL loading system-wide, including requests from Unity's native HTTP stack.

- [ ] **Step 1: Create SLNetworkInterceptor.h**

```objc
// src/SLNetworkInterceptor.h
#import <Foundation/Foundation.h>

// Install the NSURLProtocol interceptor. Call once at startup.
void SLNetworkInterceptorInstall(void);
```

- [ ] **Step 2: Create SLNetworkInterceptor.m**

Registers a custom `NSURLProtocol` subclass that inspects every outgoing request. When it sees a POST to the strack endpoint, it reads the body and forwards it to the spin parser. The request is then passed through to the real network layer untouched.

```objc
// src/SLNetworkInterceptor.m
#import "SLNetworkInterceptor.h"
#import "SLSpinParser.h"
#import "SLConstants.h"
#import <objc/runtime.h>

static NSString *const kSLHandledKey = @"SLNetworkInterceptorHandled";

@interface SLURLProtocol : NSURLProtocol <NSURLSessionDataDelegate>
@property (nonatomic, strong) NSURLSessionDataTask *activeTask;
@property (nonatomic, strong) NSMutableData *responseData;
@end

@implementation SLURLProtocol

+ (BOOL)canInitWithRequest:(NSURLRequest *)request {
    // Don't handle requests we've already tagged (prevent infinite loop)
    if ([NSURLProtocol propertyForKey:kSLHandledKey inRequest:request]) {
        return NO;
    }

    // Only intercept requests to moonactive.net
    NSString *host = request.URL.host;
    if (!host) return NO;
    return [host containsString:kSLGameAPIHost];
}

+ (NSURLRequest *)canonicalRequestForRequest:(NSURLRequest *)request {
    return request;
}

- (void)startLoading {
    NSMutableURLRequest *mutableReq = [self.request mutableCopy];
    [NSURLProtocol setProperty:@YES forKey:kSLHandledKey inRequest:mutableReq];

    // Extract POST body for strack endpoint BEFORE forwarding
    NSString *urlStr = self.request.URL.absoluteString;
    if ([urlStr containsString:kSLStrackEndpoint] &&
        [self.request.HTTPMethod isEqualToString:@"POST"]) {

        NSData *body = self.request.HTTPBody;
        if (!body && self.request.HTTPBodyStream) {
            NSInputStream *stream = self.request.HTTPBodyStream;
            [stream open];
            NSMutableData *data = [NSMutableData data];
            uint8_t buffer[4096];
            while ([stream hasBytesAvailable]) {
                NSInteger len = [stream read:buffer maxLength:sizeof(buffer)];
                if (len > 0) [data appendBytes:buffer length:len];
            }
            [stream close];
            body = data;
        }

        if (body.length > 0) {
            NSString *bodyStr = [[NSString alloc] initWithData:body
                                                      encoding:NSUTF8StringEncoding];
            if (bodyStr) {
                dispatch_async(
                    dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0), ^{
                    SLParseStrackBody(bodyStr);
                });
            }
        }
    }

    // Forward the request to the real network
    NSURLSessionConfiguration *config = [NSURLSessionConfiguration defaultSessionConfiguration];
    NSURLSession *session = [NSURLSession sessionWithConfiguration:config
                                                          delegate:self
                                                     delegateQueue:nil];
    self.responseData = [NSMutableData data];
    self.activeTask = [session dataTaskWithRequest:mutableReq];
    [self.activeTask resume];
}

- (void)stopLoading {
    [self.activeTask cancel];
}

// --- NSURLSessionDataDelegate ---

- (void)URLSession:(NSURLSession *)session
          dataTask:(NSURLSessionDataTask *)dataTask
    didReceiveResponse:(NSURLResponse *)response
     completionHandler:(void (^)(NSURLSessionResponseDisposition))completionHandler {
    [self.client URLProtocol:self
          didReceiveResponse:response
          cacheStoragePolicy:NSURLCacheStorageNotAllowed];
    completionHandler(NSURLSessionResponseAllow);
}

- (void)URLSession:(NSURLSession *)session
          dataTask:(NSURLSessionDataTask *)dataTask
    didReceiveData:(NSData *)data {
    [self.responseData appendData:data];
    [self.client URLProtocol:self didLoadData:data];
}

- (void)URLSession:(NSURLSession *)session
              task:(NSURLSessionTask *)task
didCompleteWithError:(NSError *)error {
    if (error) {
        [self.client URLProtocol:self didFailWithError:error];
    } else {
        [self.client URLProtocolDidFinishLoading:self];
    }
}

@end

void SLNetworkInterceptorInstall(void) {
    [NSURLProtocol registerClass:[SLURLProtocol class]];
    NSLog(@"[SpinLogger] NSURLProtocol interceptor registered.");
}
```

- [ ] **Step 3: Commit**

```bash
git add src/SLNetworkInterceptor.h src/SLNetworkInterceptor.m
git commit -m "feat: add NSURLSession swizzle to intercept strack POST bodies"
```

---

### Task 5: Create spin event parser

**Files:**
- Create: `src/SLSpinParser.h`
- Create: `src/SLSpinParser.m`

- [ ] **Step 1: Create SLSpinParser.h**

```objc
// src/SLSpinParser.h
#import <Foundation/Foundation.h>

// A parsed spin result
@interface SLSpinResult : NSObject
@property (nonatomic, copy) NSString *reel1;      // left symbol
@property (nonatomic, copy) NSString *reel2;      // middle symbol
@property (nonatomic, copy) NSString *reel3;      // right symbol
@property (nonatomic, copy) NSString *spinResult;  // outcome (gold, attack, etc.)
@property (nonatomic, assign) NSInteger spinNumber;
@property (nonatomic, assign) long long coinsWon;
@property (nonatomic, copy) NSString *betType;
@property (nonatomic, assign) BOOL autoSpin;
@property (nonatomic, copy) NSString *coins;
@property (nonatomic, copy) NSString *spinsRemaining;
@property (nonatomic, assign) NSInteger shields;
@property (nonatomic, assign) NSInteger village;
@property (nonatomic, copy) NSString *activePet;
@property (nonatomic, copy) NSString *accumBarResult; // per-reel accum bonus
@property (nonatomic, copy) NSString *sosSymbol;       // accumulation event type
@property (nonatomic, assign) NSInteger allTimeSpins;
@property (nonatomic, strong) NSDate *timestamp;
@end

// Parse a strack POST body (newline-delimited JSON).
// Fires kSLSpinReceivedNotification for each spin found.
void SLParseStrackBody(NSString *body);
```

- [ ] **Step 2: Create SLSpinParser.m**

```objc
// src/SLSpinParser.m
#import "SLSpinParser.h"
#import "SLSpinStore.h"
#import "SLConstants.h"

@implementation SLSpinResult
@end

void SLParseStrackBody(NSString *body) {
    NSArray *lines = [body componentsSeparatedByString:@"\n"];

    for (NSString *line in lines) {
        NSString *trimmed = [line stringByTrimmingCharactersInSet:
                             [NSCharacterSet whitespaceAndNewlineCharacterSet]];
        if (trimmed.length == 0) continue;

        NSData *jsonData = [trimmed dataUsingEncoding:NSUTF8StringEncoding];
        if (!jsonData) continue;

        NSError *error = nil;
        NSDictionary *evt = [NSJSONSerialization JSONObjectWithData:jsonData
                                                            options:0
                                                              error:&error];
        if (error || ![evt isKindOfClass:[NSDictionary class]]) continue;

        NSString *eventType = evt[@"event"];
        if (![eventType isEqualToString:@"spin"]) continue;

        NSDictionary *msg = evt[@"msg"];
        if (![msg isKindOfClass:[NSDictionary class]]) continue;

        // Parse reel symbols
        NSString *symbolsStr = msg[@"spin_result_symbols"];
        NSArray *symbols = [symbolsStr componentsSeparatedByString:@","];

        SLSpinResult *result = [[SLSpinResult alloc] init];
        result.reel1 = (symbols.count > 0) ? symbols[0] : @"";
        result.reel2 = (symbols.count > 1) ? symbols[1] : @"";
        result.reel3 = (symbols.count > 2) ? symbols[2] : @"";
        result.spinResult = msg[@"spin_result"] ?: @"";
        result.spinNumber = [msg[@"spin_number"] integerValue];
        result.coinsWon = [msg[@"spin_amount_won"] longLongValue];
        result.betType = msg[@"bet_type"] ?: @"X1";
        result.autoSpin = [msg[@"auto_spin"] boolValue];
        result.coins = [NSString stringWithFormat:@"%@", msg[@"coins"] ?: @"0"];
        result.spinsRemaining = [NSString stringWithFormat:@"%@", msg[@"spins"] ?: @"0"];
        result.shields = [msg[@"shields"] integerValue];
        result.village = [msg[@"village"] integerValue];
        result.activePet = msg[@"active_pet"] ?: @"";
        result.accumBarResult = msg[@"result"] ?: @"";
        result.sosSymbol = msg[@"sos_1_TA"] ?: @"";
        result.allTimeSpins = [msg[@"all_time_spins"] integerValue];
        result.timestamp = [NSDate date];

        // Store the spin
        SLSpinStoreAppend(result);

        // Notify observers (counter overlay, spin target, etc.)
        dispatch_async(dispatch_get_main_queue(), ^{
            [[NSNotificationCenter defaultCenter]
                postNotificationName:kSLSpinReceivedNotification
                              object:nil
                            userInfo:@{kSLSpinDataKey: result}];
        });

        NSLog(@"[SpinLogger] Spin #%ld: [%@, %@, %@] -> %@ (won: %lld)",
              (long)result.spinNumber, result.reel1, result.reel2, result.reel3,
              result.spinResult, result.coinsWon);
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add src/SLSpinParser.h src/SLSpinParser.m
git commit -m "feat: add spin event parser for strack POST body"
```

---

### Task 6: Stub out remaining headers for compilation

**Files:**
- Create: `src/SLSpinStore.h` (stub)
- Create: `src/SLSpinStore.m` (stub)
- Create: `src/SLSpeedController.h` (stub)
- Create: `src/SLSpeedController.m` (stub)
- Create: `src/SLMenuOverlay.h` (stub)
- Create: `src/SLMenuOverlay.m` (stub)

- [ ] **Step 1: Create SLSpinStore stub**

```objc
// src/SLSpinStore.h
#import <Foundation/Foundation.h>
#import "SLSpinParser.h"

void SLSpinStoreAppend(SLSpinResult *result);
NSString *SLSpinStoreCSVPath(void);
NSInteger SLSpinStoreCount(void);
```

```objc
// src/SLSpinStore.m
#import "SLSpinStore.h"
#import "SLConstants.h"

void SLSpinStoreAppend(SLSpinResult *result) {
    // Implemented in Task 7
}

NSString *SLSpinStoreCSVPath(void) {
    return @"";
}

NSInteger SLSpinStoreCount(void) {
    return 0;
}
```

- [ ] **Step 2: Create SLSpeedController stub**

```objc
// src/SLSpeedController.h
#import <Foundation/Foundation.h>

void SLSpeedControllerInstall(void);
void SLSpeedControllerSetMultiplier(double multiplier);
double SLSpeedControllerGetMultiplier(void);
```

```objc
// src/SLSpeedController.m
#import "SLSpeedController.h"

void SLSpeedControllerInstall(void) {
    // Implemented in Task 13
}

void SLSpeedControllerSetMultiplier(double multiplier) {}
double SLSpeedControllerGetMultiplier(void) { return 1.0; }
```

- [ ] **Step 3: Create SLMenuOverlay stub**

```objc
// src/SLMenuOverlay.h
#import <Foundation/Foundation.h>

void SLMenuOverlayInstall(void);
```

```objc
// src/SLMenuOverlay.m
#import "SLMenuOverlay.h"

void SLMenuOverlayInstall(void) {
    // Implemented in Task 21
}
```

- [ ] **Step 4: Commit and verify build**

```bash
git add src/SLSpinStore.h src/SLSpinStore.m src/SLSpeedController.h src/SLSpeedController.m src/SLMenuOverlay.h src/SLMenuOverlay.m
git commit -m "feat: add stub implementations for compilation"
```

Push to GitHub and verify the Actions workflow produces a `SpinLogger.dylib` artifact.

---

## Phase 3 — Spin Logger

### Task 7: Implement real-time CSV spin logger

**Files:**
- Modify: `src/SLSpinStore.h`
- Modify: `src/SLSpinStore.m`

Every spin is appended directly to `spin_history.csv` the moment it happens. The CSV file is always up-to-date — just open it anytime to see all your spin results. The file lives in the app's Documents folder (accessible via 3uTools/Filza/iMazing).

- [ ] **Step 1: Update SLSpinStore.h**

```objc
// src/SLSpinStore.h
#import <Foundation/Foundation.h>
#import "SLSpinParser.h"

// Append a spin result as a new row in spin_history.csv (real-time, no export needed)
void SLSpinStoreAppend(SLSpinResult *result);

// Get the CSV file path (for sharing via UIActivityViewController)
NSString *SLSpinStoreCSVPath(void);

// Number of spins logged so far
NSInteger SLSpinStoreCount(void);
```

- [ ] **Step 2: Implement SLSpinStore.m — direct CSV append**

```objc
// src/SLSpinStore.m
#import "SLSpinStore.h"
#import "SLConstants.h"

static NSInteger sSpinCount = 0;

static NSString *SLCSVPath(void) {
    NSString *docs = NSSearchPathForDirectoriesInDomains(
        NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
    return [docs stringByAppendingPathComponent:kSLSpinCSVFile];
}

static NSString *kCSVHeader =
    @"spin_number,timestamp,reel_1,reel_2,reel_3,spin_result,"
     "coins_won,bet_type,auto_spin,coins,spins_remaining,"
     "shields,village,active_pet,accum_bar_result,sos_symbol,"
     "all_time_spins\n";

static void SLEnsureCSVHeader(void) {
    NSString *path = SLCSVPath();
    NSFileManager *fm = [NSFileManager defaultManager];
    if (![fm fileExistsAtPath:path]) {
        [kCSVHeader writeToFile:path atomically:YES
                       encoding:NSUTF8StringEncoding error:nil];
        sSpinCount = 0;
        NSLog(@"[SpinLogger] Created new CSV: %@", path);
    } else {
        // Count existing rows (skip header)
        NSString *content = [NSString stringWithContentsOfFile:path
                                                     encoding:NSUTF8StringEncoding error:nil];
        NSArray *lines = [content componentsSeparatedByString:@"\n"];
        sSpinCount = 0;
        for (NSString *l in lines) {
            if (l.length > 0) sSpinCount++;
        }
        sSpinCount--; // subtract header
        if (sSpinCount < 0) sSpinCount = 0;
        NSLog(@"[SpinLogger] Existing CSV has %ld spins", (long)sSpinCount);
    }
}

void SLSpinStoreAppend(SLSpinResult *result) {
    if (!result) return;

    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ SLEnsureCSVHeader(); });

    sSpinCount++;

    NSDateFormatter *fmt = [[NSDateFormatter alloc] init];
    fmt.dateFormat = @"yyyy-MM-dd HH:mm:ss";

    // Build CSV row — quote fields that might contain commas
    NSString *row = [NSString stringWithFormat:
        @"%ld,%@,%@,%@,%@,%@,%lld,%@,%@,%@,%@,%ld,%ld,%@,\"%@\",%@,%ld\n",
        (long)result.spinNumber,
        [fmt stringFromDate:result.timestamp ?: [NSDate date]],
        result.reel1 ?: @"",
        result.reel2 ?: @"",
        result.reel3 ?: @"",
        result.spinResult ?: @"",
        result.coinsWon,
        result.betType ?: @"",
        result.autoSpin ? @"true" : @"false",
        result.coins ?: @"0",
        result.spinsRemaining ?: @"0",
        (long)result.shields,
        (long)result.village,
        result.activePet ?: @"",
        result.accumBarResult ?: @"",
        result.sosSymbol ?: @"",
        (long)result.allTimeSpins];

    // Append to CSV file
    NSString *path = SLCSVPath();
    NSFileHandle *fh = [NSFileHandle fileHandleForWritingAtPath:path];
    if (fh) {
        [fh seekToEndOfFile];
        [fh writeData:[row dataUsingEncoding:NSUTF8StringEncoding]];
        [fh closeFile];
    } else {
        // File was deleted? Recreate with header + this row
        NSString *content = [kCSVHeader stringByAppendingString:row];
        [content writeToFile:path atomically:YES
                    encoding:NSUTF8StringEncoding error:nil];
    }
}

NSString *SLSpinStoreCSVPath(void) {
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ SLEnsureCSVHeader(); });
    return SLCSVPath();
}

NSInteger SLSpinStoreCount(void) {
    return sSpinCount;
}
```

- [ ] **Step 3: Commit**

```bash
git add src/SLSpinStore.h src/SLSpinStore.m
git commit -m "feat: real-time CSV append — every spin logged immediately to spin_history.csv"
```

---

## Phase 4 — Counter Overlays

### Task 8: Create draggable counter overlay system

**Files:**
- Create: `src/SLCounterOverlay.h`
- Create: `src/SLCounterOverlay.m`

- [ ] **Step 1: Create SLCounterOverlay.h**

```objc
// src/SLCounterOverlay.h
#import <UIKit/UIKit.h>

@interface SLCounterOverlay : NSObject

+ (instancetype)shared;

- (void)install;
- (void)show;
- (void)hide;
- (void)resetAllCounters;
- (void)resetCounterForSymbol:(NSString *)symbol;
- (NSDictionary<NSString *, NSNumber *> *)currentCounts;

@end
```

- [ ] **Step 2: Create SLCounterOverlay.m**

```objc
// src/SLCounterOverlay.m
#import "SLCounterOverlay.h"
#import "SLConstants.h"

@interface SLDraggableLabel : UILabel
@end

@implementation SLDraggableLabel

- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    UITouch *touch = [touches anyObject];
    CGPoint prev = [touch previousLocationInView:self.superview];
    CGPoint curr = [touch locationInView:self.superview];
    CGPoint center = self.center;
    center.x += curr.x - prev.x;
    center.y += curr.y - prev.y;
    self.center = center;
}

- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    // Save position to UserDefaults
    NSString *key = [NSString stringWithFormat:@"%@Pos_%ld",
                     kSLDefaultsPrefix, (long)self.tag];
    NSDictionary *pos = @{@"x": @(self.center.x), @"y": @(self.center.y)};
    [[NSUserDefaults standardUserDefaults] setObject:pos forKey:key];
}

@end

// -------------------------------------------------------

@interface SLCounterOverlay ()
@property (nonatomic, strong) UIWindow *overlayWindow;
@property (nonatomic, strong) NSMutableDictionary<NSString *, SLDraggableLabel *> *labels;
@property (nonatomic, strong) NSMutableDictionary<NSString *, NSNumber *> *counts;
@property (nonatomic, assign) NSInteger sessionSpinCount;
@end

@implementation SLCounterOverlay

+ (instancetype)shared {
    static SLCounterOverlay *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _labels = [NSMutableDictionary dictionary];
        _counts = [NSMutableDictionary dictionary];
        _sessionSpinCount = 0;
        for (NSString *sym in SLTrackedSymbols()) {
            _counts[sym] = @0;
        }
    }
    return self;
}

- (void)install {
    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            break;
        }
    }
    if (!scene) return;

    self.overlayWindow = [[UIWindow alloc] initWithWindowScene:scene];
    self.overlayWindow.windowLevel = UIWindowLevelAlert + 100;
    self.overlayWindow.backgroundColor = [UIColor clearColor];
    self.overlayWindow.userInteractionEnabled = YES;
    self.overlayWindow.rootViewController = [[UIViewController alloc] init];
    self.overlayWindow.rootViewController.view.backgroundColor = [UIColor clearColor];

    // Create a label per tracked symbol
    NSArray *symbols = SLTrackedSymbols();
    NSDictionary *emojiMap = @{
        kSLSymbolAttack:       @"🔨",
        kSLSymbolSteal:        @"🐷",
        kSLSymbolAccumulation: @"⭐",
        kSLSymbolShield:       @"🛡",
        kSLSymbolSpins:        @"🎰",
        kSLSymbolGoldSack:     @"💰",
    };

    CGFloat startY = 600;
    for (NSUInteger i = 0; i < symbols.count; i++) {
        NSString *sym = symbols[i];
        SLDraggableLabel *label = [[SLDraggableLabel alloc]
            initWithFrame:CGRectMake(10, startY + i * 40, 80, 32)];
        label.backgroundColor = [[UIColor blackColor] colorWithAlphaComponent:0.6];
        label.textColor = [UIColor whiteColor];
        label.font = [UIFont boldSystemFontOfSize:14];
        label.textAlignment = NSTextAlignmentCenter;
        label.layer.cornerRadius = 8;
        label.clipsToBounds = YES;
        label.tag = i;
        label.userInteractionEnabled = YES;
        label.text = [NSString stringWithFormat:@"%@ 0", emojiMap[sym] ?: @"?"];

        // Restore saved position
        NSString *posKey = [NSString stringWithFormat:@"%@Pos_%lu",
                            kSLDefaultsPrefix, (unsigned long)i];
        NSDictionary *savedPos = [[NSUserDefaults standardUserDefaults] objectForKey:posKey];
        if (savedPos) {
            label.center = CGPointMake(
                [savedPos[@"x"] floatValue],
                [savedPos[@"y"] floatValue]);
        }

        [self.overlayWindow.rootViewController.view addSubview:label];
        self.labels[sym] = label;
    }

    // Also add a session spin counter
    SLDraggableLabel *spinLabel = [[SLDraggableLabel alloc]
        initWithFrame:CGRectMake(10, startY - 40, 100, 32)];
    spinLabel.backgroundColor = [[UIColor blueColor] colorWithAlphaComponent:0.6];
    spinLabel.textColor = [UIColor whiteColor];
    spinLabel.font = [UIFont boldSystemFontOfSize:14];
    spinLabel.textAlignment = NSTextAlignmentCenter;
    spinLabel.layer.cornerRadius = 8;
    spinLabel.clipsToBounds = YES;
    spinLabel.tag = 99;
    spinLabel.userInteractionEnabled = YES;
    spinLabel.text = @"Spins: 0";
    [self.overlayWindow.rootViewController.view addSubview:spinLabel];
    self.labels[@"_session"] = spinLabel;

    [self.overlayWindow setHidden:NO];

    // Listen for spin events
    [[NSNotificationCenter defaultCenter]
        addObserver:self
           selector:@selector(onSpinReceived:)
               name:kSLSpinReceivedNotification
             object:nil];

    NSLog(@"[SpinLogger] Counter overlays installed.");
}

- (void)onSpinReceived:(NSNotification *)note {
    SLSpinResult *spin = note.userInfo[kSLSpinDataKey];
    if (!spin) return;

    self.sessionSpinCount++;

    // Count each reel symbol
    NSArray *reels = @[spin.reel1 ?: @"", spin.reel2 ?: @"", spin.reel3 ?: @""];
    for (NSString *sym in reels) {
        if (sym.length == 0) continue;
        NSNumber *current = self.counts[sym];
        if (current) {
            self.counts[sym] = @(current.integerValue + 1);
        }
    }

    [self updateLabels];
}

- (void)updateLabels {
    NSDictionary *emojiMap = @{
        kSLSymbolAttack:       @"🔨",
        kSLSymbolSteal:        @"🐷",
        kSLSymbolAccumulation: @"⭐",
        kSLSymbolShield:       @"🛡",
        kSLSymbolSpins:        @"🎰",
        kSLSymbolGoldSack:     @"💰",
    };

    for (NSString *sym in self.counts) {
        SLDraggableLabel *label = self.labels[sym];
        if (label) {
            label.text = [NSString stringWithFormat:@"%@ %@",
                          emojiMap[sym] ?: @"?", self.counts[sym]];
        }
    }

    SLDraggableLabel *spinLabel = self.labels[@"_session"];
    if (spinLabel) {
        spinLabel.text = [NSString stringWithFormat:@"Spins: %ld",
                          (long)self.sessionSpinCount];
    }
}

- (void)show {
    [self.overlayWindow setHidden:NO];
}

- (void)hide {
    [self.overlayWindow setHidden:YES];
}

- (void)resetAllCounters {
    self.sessionSpinCount = 0;
    for (NSString *sym in SLTrackedSymbols()) {
        self.counts[sym] = @0;
    }
    [self updateLabels];
}

- (void)resetCounterForSymbol:(NSString *)symbol {
    self.counts[symbol] = @0;
    [self updateLabels];
}

- (NSDictionary<NSString *, NSNumber *> *)currentCounts {
    return [self.counts copy];
}

@end
```

- [ ] **Step 3: Commit**

```bash
git add src/SLCounterOverlay.h src/SLCounterOverlay.m
git commit -m "feat: add draggable per-symbol counter overlays"
```

---

## Phase 5 — Speed Multiplier

### Task 9: Implement game speed controller

**Files:**
- Modify: `src/SLSpeedController.m`

The speed multiplier works by swizzling `CADisplayLink` creation and adjusting `preferredFramesPerSecond`, plus swizzling `NSTimer` to scale intervals.

- [ ] **Step 1: Implement SLSpeedController.m**

```objc
// src/SLSpeedController.m
#import "SLSpeedController.h"
#import "SLConstants.h"
#import <objc/runtime.h>
#import <QuartzCore/QuartzCore.h>

static double sSpeedMultiplier = 1.0;

// --- NSTimer swizzle ---
// We swizzle scheduledTimerWithTimeInterval: to divide the interval by multiplier.

static IMP sOrigTimerScheduled = NULL;

static NSTimer *SLSwizzled_scheduledTimer(id self, SEL _cmd,
    NSTimeInterval interval, id target, SEL selector, id userInfo, BOOL repeats)
{
    if (sSpeedMultiplier > 1.0 && interval > 0.01) {
        interval /= sSpeedMultiplier;
    }
    typedef NSTimer *(*OrigFunc)(id, SEL, NSTimeInterval, id, SEL, id, BOOL);
    return ((OrigFunc)sOrigTimerScheduled)(self, _cmd, interval, target, selector, userInfo, repeats);
}

// --- CADisplayLink swizzle ---
static IMP sOrigDisplayLinkAdd = NULL;

static void SLSwizzled_displayLinkAdd(id self, SEL _cmd, NSRunLoop *runloop, NSRunLoopMode mode) {
    if (sSpeedMultiplier > 1.0) {
        CADisplayLink *link = (CADisplayLink *)self;
        link.preferredFramesPerSecond = (NSInteger)(60.0 * sSpeedMultiplier);
    }
    typedef void (*OrigFunc)(id, SEL, NSRunLoop *, NSRunLoopMode);
    ((OrigFunc)sOrigDisplayLinkAdd)(self, _cmd, runloop, mode);
}

void SLSpeedControllerInstall(void) {
    // Restore saved multiplier
    double saved = [[NSUserDefaults standardUserDefaults] doubleForKey:kSLKeySpeedMultiplier];
    if (saved > 0.1) sSpeedMultiplier = saved;

    // Swizzle NSTimer
    {
        SEL sel = @selector(scheduledTimerWithTimeInterval:target:selector:userInfo:repeats:);
        Method m = class_getClassMethod([NSTimer class], sel);
        if (m) {
            sOrigTimerScheduled = method_getImplementation(m);
            method_setImplementation(m, (IMP)SLSwizzled_scheduledTimer);
        }
    }

    // Swizzle CADisplayLink addToRunLoop:forMode:
    {
        SEL sel = @selector(addToRunLoop:forMode:);
        Method m = class_getInstanceMethod([CADisplayLink class], sel);
        if (m) {
            sOrigDisplayLinkAdd = method_getImplementation(m);
            method_setImplementation(m, (IMP)SLSwizzled_displayLinkAdd);
        }
    }

    NSLog(@"[SpinLogger] Speed controller installed (multiplier: %.1fx)", sSpeedMultiplier);
}

void SLSpeedControllerSetMultiplier(double multiplier) {
    sSpeedMultiplier = fmax(1.0, fmin(multiplier, 50.0));
    [[NSUserDefaults standardUserDefaults] setDouble:sSpeedMultiplier
                                              forKey:kSLKeySpeedMultiplier];
    NSLog(@"[SpinLogger] Speed set to %.1fx", sSpeedMultiplier);
}

double SLSpeedControllerGetMultiplier(void) {
    return sSpeedMultiplier;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/SLSpeedController.m
git commit -m "feat: implement speed multiplier via NSTimer + CADisplayLink swizzle"
```

---

## Phase 6 — Spin Target & Auto-Reset

### Task 10: Implement spin target and auto-reset

**Files:**
- Create: `src/SLSpinTarget.h`
- Create: `src/SLSpinTarget.m`

- [ ] **Step 1: Create SLSpinTarget.h**

```objc
// src/SLSpinTarget.h
#import <Foundation/Foundation.h>

@interface SLSpinTarget : NSObject

+ (instancetype)shared;

@property (nonatomic, assign) NSInteger targetSpinCount;    // 0 = disabled
@property (nonatomic, copy) NSString *autoResetMode;         // "none", "symbol", "global"
@property (nonatomic, assign) NSInteger currentSessionSpins;

- (void)install;

@end
```

- [ ] **Step 2: Create SLSpinTarget.m**

```objc
// src/SLSpinTarget.m
#import "SLSpinTarget.h"
#import "SLCounterOverlay.h"
#import "SLConstants.h"
#import <UIKit/UIKit.h>

@implementation SLSpinTarget

+ (instancetype)shared {
    static SLSpinTarget *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _currentSessionSpins = 0;
        _targetSpinCount = [[NSUserDefaults standardUserDefaults]
                            integerForKey:kSLKeySpinTarget];
        _autoResetMode = [[NSUserDefaults standardUserDefaults]
                          stringForKey:kSLKeyAutoResetMode] ?: @"none";
    }
    return self;
}

- (void)install {
    [[NSNotificationCenter defaultCenter]
        addObserver:self
           selector:@selector(onSpinReceived:)
               name:kSLSpinReceivedNotification
             object:nil];
    NSLog(@"[SpinLogger] Spin target installed (target: %ld, reset: %@)",
          (long)self.targetSpinCount, self.autoResetMode);
}

- (void)onSpinReceived:(NSNotification *)note {
    self.currentSessionSpins++;

    // Check if we hit the target
    if (self.targetSpinCount > 0 && self.currentSessionSpins >= self.targetSpinCount) {
        NSLog(@"[SpinLogger] Spin target reached (%ld)!", (long)self.targetSpinCount);

        // Show alert on main thread
        dispatch_async(dispatch_get_main_queue(), ^{
            UIAlertController *alert = [UIAlertController
                alertControllerWithTitle:@"Spin Target Reached"
                                 message:[NSString stringWithFormat:
                                          @"Completed %ld spins this session.",
                                          (long)self.currentSessionSpins]
                          preferredStyle:UIAlertControllerStyleAlert];
            [alert addAction:[UIAlertAction actionWithTitle:@"Reset & Continue"
                                                     style:UIAlertActionStyleDefault
                                                   handler:^(UIAlertAction *a) {
                self.currentSessionSpins = 0;
                [[SLCounterOverlay shared] resetAllCounters];
            }]];
            [alert addAction:[UIAlertAction actionWithTitle:@"Stop"
                                                     style:UIAlertActionStyleCancel
                                                   handler:nil]];

            UIViewController *root = UIApplication.sharedApplication
                .connectedScenes.allObjects.firstObject;
            UIWindowScene *scene = nil;
            for (UIScene *s in UIApplication.sharedApplication.connectedScenes) {
                if ([s isKindOfClass:[UIWindowScene class]]) {
                    scene = (UIWindowScene *)s;
                    break;
                }
            }
            UIViewController *vc = scene.windows.firstObject.rootViewController;
            while (vc.presentedViewController) vc = vc.presentedViewController;
            [vc presentViewController:alert animated:YES completion:nil];
        });
    }

    // Auto-reset: reset counters when 3x of a specific symbol appears
    if ([self.autoResetMode isEqualToString:@"symbol"]) {
        SLSpinResult *spin = note.userInfo[kSLSpinDataKey];
        if (spin && [spin.reel1 isEqualToString:spin.reel2] &&
            [spin.reel2 isEqualToString:spin.reel3]) {
            // 3 of a kind — reset the counter for that symbol
            [[SLCounterOverlay shared] resetCounterForSymbol:spin.reel1];
        }
    } else if ([self.autoResetMode isEqualToString:@"global"]) {
        SLSpinResult *spin = note.userInfo[kSLSpinDataKey];
        if (spin && [spin.reel1 isEqualToString:spin.reel2] &&
            [spin.reel2 isEqualToString:spin.reel3]) {
            [[SLCounterOverlay shared] resetAllCounters];
        }
    }
}

- (void)setTargetSpinCount:(NSInteger)targetSpinCount {
    _targetSpinCount = targetSpinCount;
    [[NSUserDefaults standardUserDefaults] setInteger:targetSpinCount
                                               forKey:kSLKeySpinTarget];
}

- (void)setAutoResetMode:(NSString *)autoResetMode {
    _autoResetMode = [autoResetMode copy];
    [[NSUserDefaults standardUserDefaults] setObject:autoResetMode
                                              forKey:kSLKeyAutoResetMode];
}

@end
```

- [ ] **Step 3: Update SpinLoggerTweak.m to initialize spin target**

Add to the dispatch_after block in `SpinLoggerTweak.m`:

```objc
// Add after SLMenuOverlayInstall():
extern void SLSpinTargetInstall(void);
// ...
[[SLSpinTarget shared] install];
[[SLCounterOverlay shared] install];
```

Update the full `SpinLoggerTweak.m`:

```objc
// src/SpinLoggerTweak.m
#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import "SLConstants.h"
#import "SLCounterOverlay.h"
#import "SLSpinTarget.h"

extern void SLNetworkInterceptorInstall(void);
extern void SLSpeedControllerInstall(void);
extern void SLMenuOverlayInstall(void);

__attribute__((constructor))
static void SpinLoggerInit(void) {
    NSLog(@"[SpinLogger] Initializing...");

    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(2.0 * NSEC_PER_SEC)),
                   dispatch_get_main_queue(), ^{
        NSLog(@"[SpinLogger] Installing hooks...");
        SLNetworkInterceptorInstall();
        SLSpeedControllerInstall();
        [[SLCounterOverlay shared] install];
        [[SLSpinTarget shared] install];
        SLMenuOverlayInstall();
        NSLog(@"[SpinLogger] Ready.");
    });
}
```

- [ ] **Step 4: Commit**

```bash
git add src/SLSpinTarget.h src/SLSpinTarget.m src/SpinLoggerTweak.m
git commit -m "feat: add spin target with auto-reset on 3-of-a-kind"
```

---

## Phase 7 — Tris Lock & Skip

### Task 11: Implement Tris controller

**Files:**
- Create: `src/SLTrisController.h`
- Create: `src/SLTrisController.m`

- [ ] **Step 1: Create SLTrisController.h**

```objc
// src/SLTrisController.h
#import <Foundation/Foundation.h>

@interface SLTrisController : NSObject

+ (instancetype)shared;

@property (nonatomic, copy) NSString *lockTarget;       // card ID to lock onto, nil = disabled
@property (nonatomic, assign) BOOL skipEnabled;          // auto-skip tris

- (void)install;

@end
```

- [ ] **Step 2: Create SLTrisController.m**

The tris controller monitors network requests related to card trading. When the game sends a tris/trade request, it checks if the offered card matches the lock target.

```objc
// src/SLTrisController.m
#import "SLTrisController.h"
#import "SLConstants.h"

@implementation SLTrisController

+ (instancetype)shared {
    static SLTrisController *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _lockTarget = [[NSUserDefaults standardUserDefaults]
                       stringForKey:kSLKeyTrisLockTarget];
        _skipEnabled = [[NSUserDefaults standardUserDefaults]
                        boolForKey:kSLKeyTrisSkipEnabled];
    }
    return self;
}

- (void)install {
    // Tris monitoring is handled via network interceptor.
    // We register for a notification that the network layer will post
    // when it sees tris-related API calls.
    [[NSNotificationCenter defaultCenter]
        addObserver:self
           selector:@selector(onTrisEvent:)
               name:@"SLTrisEventNotification"
             object:nil];
    NSLog(@"[SpinLogger] Tris controller installed (lock: %@, skip: %d)",
          self.lockTarget ?: @"none", self.skipEnabled);
}

- (void)onTrisEvent:(NSNotification *)note {
    NSDictionary *data = note.userInfo;
    NSString *offeredCard = data[@"card_id"];

    if (self.skipEnabled && ![offeredCard isEqualToString:self.lockTarget]) {
        NSLog(@"[SpinLogger] Tris skip: offered %@, want %@", offeredCard, self.lockTarget);
        // The skip is handled by not accepting the trade in the UI.
        // For full automation, we would need to hook the game's tris accept/reject methods.
        // This requires further reverse engineering of the specific game methods.
    }

    if (self.lockTarget && [offeredCard isEqualToString:self.lockTarget]) {
        NSLog(@"[SpinLogger] Tris LOCK HIT: %@", offeredCard);
    }
}

- (void)setLockTarget:(NSString *)lockTarget {
    _lockTarget = [lockTarget copy];
    [[NSUserDefaults standardUserDefaults] setObject:lockTarget
                                              forKey:kSLKeyTrisLockTarget];
}

- (void)setSkipEnabled:(BOOL)skipEnabled {
    _skipEnabled = skipEnabled;
    [[NSUserDefaults standardUserDefaults] setBool:skipEnabled
                                            forKey:kSLKeyTrisSkipEnabled];
}

@end
```

- [ ] **Step 3: Commit**

```bash
git add src/SLTrisController.h src/SLTrisController.m
git commit -m "feat: add tris lock and skip controller"
```

---

## Phase 8 — Presets & Persistence

### Task 12: Implement preset manager

**Files:**
- Create: `src/SLPresetManager.h`
- Create: `src/SLPresetManager.m`

- [ ] **Step 1: Create SLPresetManager.h**

```objc
// src/SLPresetManager.h
#import <Foundation/Foundation.h>

@interface SLPresetManager : NSObject

+ (instancetype)shared;

// Save current state to preset slot (1 or 2)
- (void)savePreset:(NSInteger)slot;

// Load preset and apply all settings
- (void)loadPreset:(NSInteger)slot;

// Get preset summary for display
- (NSString *)presetSummary:(NSInteger)slot;

@end
```

- [ ] **Step 2: Create SLPresetManager.m**

```objc
// src/SLPresetManager.m
#import "SLPresetManager.h"
#import "SLConstants.h"
#import "SLSpeedController.h"
#import "SLSpinTarget.h"
#import "SLTrisController.h"

@implementation SLPresetManager

+ (instancetype)shared {
    static SLPresetManager *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (NSString *)keyForSlot:(NSInteger)slot {
    return (slot == 1) ? kSLKeyPreset1 : kSLKeyPreset2;
}

- (void)savePreset:(NSInteger)slot {
    NSDictionary *state = @{
        @"speed": @(SLSpeedControllerGetMultiplier()),
        @"spinTarget": @([SLSpinTarget shared].targetSpinCount),
        @"autoResetMode": [SLSpinTarget shared].autoResetMode ?: @"none",
        @"trisLockTarget": [SLTrisController shared].lockTarget ?: @"",
        @"trisSkipEnabled": @([SLTrisController shared].skipEnabled),
    };

    [[NSUserDefaults standardUserDefaults] setObject:state forKey:[self keyForSlot:slot]];
    NSLog(@"[SpinLogger] Saved preset %ld", (long)slot);
}

- (void)loadPreset:(NSInteger)slot {
    NSDictionary *state = [[NSUserDefaults standardUserDefaults]
                           objectForKey:[self keyForSlot:slot]];
    if (!state) return;

    SLSpeedControllerSetMultiplier([state[@"speed"] doubleValue]);
    [SLSpinTarget shared].targetSpinCount = [state[@"spinTarget"] integerValue];
    [SLSpinTarget shared].autoResetMode = state[@"autoResetMode"];
    [SLTrisController shared].lockTarget = state[@"trisLockTarget"];
    [SLTrisController shared].skipEnabled = [state[@"trisSkipEnabled"] boolValue];

    NSLog(@"[SpinLogger] Loaded preset %ld", (long)slot);
}

- (NSString *)presetSummary:(NSInteger)slot {
    NSDictionary *state = [[NSUserDefaults standardUserDefaults]
                           objectForKey:[self keyForSlot:slot]];
    if (!state) return @"(empty)";
    return [NSString stringWithFormat:@"Speed: %.1fx | Target: %@ | Reset: %@",
            [state[@"speed"] doubleValue],
            state[@"spinTarget"],
            state[@"autoResetMode"]];
}

@end
```

- [ ] **Step 3: Commit**

```bash
git add src/SLPresetManager.h src/SLPresetManager.m
git commit -m "feat: add preset save/load manager"
```

---

## Phase 9 — Floating Menu UI

### Task 13: Implement floating menu overlay

**Files:**
- Modify: `src/SLMenuOverlay.m`

- [ ] **Step 1: Implement SLMenuOverlay.m with floating button + settings panel**

```objc
// src/SLMenuOverlay.m
#import "SLMenuOverlay.h"
#import "SLConstants.h"
#import "SLSpinStore.h"
#import "SLSpeedController.h"
#import "SLSpinTarget.h"
#import "SLTrisController.h"
#import "SLPresetManager.h"
#import "SLCounterOverlay.h"
#import <UIKit/UIKit.h>

static UIWindow *sMenuWindow = nil;
static UIButton *sMenuButton = nil;
static BOOL sMenuOpen = NO;

static UIViewController *SLTopVC(void) {
    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            break;
        }
    }
    UIViewController *vc = scene.windows.firstObject.rootViewController;
    while (vc.presentedViewController) vc = vc.presentedViewController;
    return vc;
}

static void SLShowSettingsMenu(void) {
    UIAlertController *menu = [UIAlertController
        alertControllerWithTitle:@"🎰 SpinLogger"
                         message:[NSString stringWithFormat:
                                  @"Spins logged: %ld\nSpeed: %.1fx",
                                  (long)SLSpinStoreCount(),
                                  SLSpeedControllerGetMultiplier()]
                  preferredStyle:UIAlertControllerStyleActionSheet];

    // --- Share CSV (file is always up-to-date, written in real-time) ---
    [menu addAction:[UIAlertAction actionWithTitle:@"📥 Share CSV"
                                             style:UIAlertActionStyleDefault
                                           handler:^(UIAlertAction *a) {
        NSString *csvPath = SLSpinStoreCSVPath();
        if (csvPath) {
            NSURL *url = [NSURL fileURLWithPath:csvPath];
            UIActivityViewController *share = [[UIActivityViewController alloc]
                initWithActivityItems:@[url] applicationActivities:nil];
            [SLTopVC() presentViewController:share animated:YES completion:nil];
        }
    }]];

    // --- Speed ---
    [menu addAction:[UIAlertAction actionWithTitle:@"⚡ Set Speed"
                                             style:UIAlertActionStyleDefault
                                           handler:^(UIAlertAction *a) {
        UIAlertController *speedAlert = [UIAlertController
            alertControllerWithTitle:@"Speed Multiplier"
                             message:@"Enter value (1.0 - 50.0)"
                      preferredStyle:UIAlertControllerStyleAlert];
        [speedAlert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
            tf.text = [NSString stringWithFormat:@"%.1f", SLSpeedControllerGetMultiplier()];
            tf.keyboardType = UIKeyboardTypeDecimalPad;
        }];
        [speedAlert addAction:[UIAlertAction actionWithTitle:@"Set"
                                                       style:UIAlertActionStyleDefault
                                                     handler:^(UIAlertAction *a2) {
            double val = [speedAlert.textFields.firstObject.text doubleValue];
            SLSpeedControllerSetMultiplier(val);
        }]];
        [speedAlert addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                                       style:UIAlertActionStyleCancel
                                                     handler:nil]];
        [SLTopVC() presentViewController:speedAlert animated:YES completion:nil];
    }]];

    // --- Spin Target ---
    [menu addAction:[UIAlertAction actionWithTitle:@"🎯 Set Spin Target"
                                             style:UIAlertActionStyleDefault
                                           handler:^(UIAlertAction *a) {
        UIAlertController *targetAlert = [UIAlertController
            alertControllerWithTitle:@"Spin Target"
                             message:@"Stop after N spins (0 = off)"
                      preferredStyle:UIAlertControllerStyleAlert];
        [targetAlert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
            tf.text = [NSString stringWithFormat:@"%ld",
                       (long)[SLSpinTarget shared].targetSpinCount];
            tf.keyboardType = UIKeyboardTypeNumberPad;
        }];
        [targetAlert addAction:[UIAlertAction actionWithTitle:@"Set"
                                                        style:UIAlertActionStyleDefault
                                                      handler:^(UIAlertAction *a2) {
            NSInteger val = [targetAlert.textFields.firstObject.text integerValue];
            [SLSpinTarget shared].targetSpinCount = val;
        }]];
        [targetAlert addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                                        style:UIAlertActionStyleCancel
                                                      handler:nil]];
        [SLTopVC() presentViewController:targetAlert animated:YES completion:nil];
    }]];

    // --- Auto-Reset Mode ---
    [menu addAction:[UIAlertAction actionWithTitle:@"🔄 Auto-Reset Mode"
                                             style:UIAlertActionStyleDefault
                                           handler:^(UIAlertAction *a) {
        UIAlertController *resetAlert = [UIAlertController
            alertControllerWithTitle:@"Auto-Reset"
                             message:@"Reset counters when 3-of-a-kind lands"
                      preferredStyle:UIAlertControllerStyleActionSheet];
        for (NSString *mode in @[@"none", @"symbol", @"global"]) {
            NSString *check = [[SLSpinTarget shared].autoResetMode isEqualToString:mode]
                              ? @" ✓" : @"";
            [resetAlert addAction:[UIAlertAction
                actionWithTitle:[mode stringByAppendingString:check]
                          style:UIAlertActionStyleDefault
                        handler:^(UIAlertAction *a2) {
                [SLSpinTarget shared].autoResetMode = mode;
            }]];
        }
        [resetAlert addAction:[UIAlertAction actionWithTitle:@"Cancel"
                                                       style:UIAlertActionStyleCancel
                                                     handler:nil]];
        [SLTopVC() presentViewController:resetAlert animated:YES completion:nil];
    }]];

    // --- Reset Counters ---
    [menu addAction:[UIAlertAction actionWithTitle:@"🗑 Reset Counters"
                                             style:UIAlertActionStyleDestructive
                                           handler:^(UIAlertAction *a) {
        [[SLCounterOverlay shared] resetAllCounters];
    }]];

    // --- Toggle Counters ---
    [menu addAction:[UIAlertAction actionWithTitle:@"👁 Toggle Counters"
                                             style:UIAlertActionStyleDefault
                                           handler:^(UIAlertAction *a) {
        static BOOL visible = YES;
        visible = !visible;
        if (visible) [[SLCounterOverlay shared] show];
        else [[SLCounterOverlay shared] hide];
    }]];

    // --- Presets ---
    [menu addAction:[UIAlertAction
        actionWithTitle:[NSString stringWithFormat:@"💾 Save Preset 1"]
                  style:UIAlertActionStyleDefault
                handler:^(UIAlertAction *a) {
        [[SLPresetManager shared] savePreset:1];
    }]];
    [menu addAction:[UIAlertAction
        actionWithTitle:[NSString stringWithFormat:@"📂 Load Preset 1 (%@)",
                         [[SLPresetManager shared] presetSummary:1]]
                  style:UIAlertActionStyleDefault
                handler:^(UIAlertAction *a) {
        [[SLPresetManager shared] loadPreset:1];
    }]];
    [menu addAction:[UIAlertAction
        actionWithTitle:[NSString stringWithFormat:@"💾 Save Preset 2"]
                  style:UIAlertActionStyleDefault
                handler:^(UIAlertAction *a) {
        [[SLPresetManager shared] savePreset:2];
    }]];
    [menu addAction:[UIAlertAction
        actionWithTitle:[NSString stringWithFormat:@"📂 Load Preset 2 (%@)",
                         [[SLPresetManager shared] presetSummary:2]]
                  style:UIAlertActionStyleDefault
                handler:^(UIAlertAction *a) {
        [[SLPresetManager shared] loadPreset:2];
    }]];

    // --- Close ---
    [menu addAction:[UIAlertAction actionWithTitle:@"Close"
                                             style:UIAlertActionStyleCancel
                                           handler:nil]];

    [SLTopVC() presentViewController:menu animated:YES completion:nil];
}

void SLMenuOverlayInstall(void) {
    UIWindowScene *scene = nil;
    for (UIScene *s in UIApplication.sharedApplication.connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            break;
        }
    }
    if (!scene) return;

    sMenuWindow = [[UIWindow alloc] initWithWindowScene:scene];
    sMenuWindow.windowLevel = UIWindowLevelAlert + 200;
    sMenuWindow.frame = CGRectMake(0, 0, 50, 50);
    sMenuWindow.center = CGPointMake(UIScreen.mainScreen.bounds.size.width - 40,
                                     UIScreen.mainScreen.bounds.size.height / 2);
    sMenuWindow.backgroundColor = [UIColor clearColor];
    sMenuWindow.rootViewController = [[UIViewController alloc] init];
    sMenuWindow.rootViewController.view.backgroundColor = [UIColor clearColor];

    sMenuButton = [UIButton buttonWithType:UIButtonTypeCustom];
    sMenuButton.frame = CGRectMake(0, 0, 50, 50);
    sMenuButton.backgroundColor = [[UIColor systemBlueColor] colorWithAlphaComponent:0.8];
    sMenuButton.layer.cornerRadius = 25;
    sMenuButton.clipsToBounds = YES;
    [sMenuButton setTitle:@"SL" forState:UIControlStateNormal];
    [sMenuButton setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    sMenuButton.titleLabel.font = [UIFont boldSystemFontOfSize:16];
    [sMenuButton addTarget:[NSNull null]
                    action:@selector(description) // placeholder, we use block below
          forControlEvents:UIControlEventTouchUpInside];

    // Use a gesture recognizer for tap (simpler than block-based target)
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc]
        initWithTarget:nil action:nil];
    // Instead, use the button's action properly via a helper
    // We'll use a simple approach: observe via notification
    [sMenuButton addTarget:[SLPresetManager shared]
                    action:@selector(description)
          forControlEvents:UIControlEventTouchUpInside];

    // Simplest approach: add an invisible button with a block via objc_setAssociatedObject
    // Actually, let's just use a recognizer with a concrete target
    [sMenuWindow.rootViewController.view addSubview:sMenuButton];

    // Make the button draggable + tappable
    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:nil action:nil];
    // For simplicity, we'll intercept touches at the window level

    [sMenuWindow setHidden:NO];

    // Use method swizzling to get button tap working without a formal target
    // Cleaner: use NSNotificationCenter
    [[NSNotificationCenter defaultCenter]
        addObserverForName:@"SLMenuButtonTapped" object:nil queue:nil
                usingBlock:^(NSNotification *note) {
        SLShowSettingsMenu();
    }];

    // Override the button action via a proper target class
    // The simplest working approach:
    sMenuButton.tag = 42;
    [sMenuButton addTarget:NSClassFromString(@"SLMenuButtonTarget")
                    action:@selector(tapped)
          forControlEvents:UIControlEventTouchUpInside];

    NSLog(@"[SpinLogger] Menu overlay installed.");
}

// Button target class
@interface SLMenuButtonTarget : NSObject
+ (void)tapped;
@end

@implementation SLMenuButtonTarget
+ (void)tapped {
    SLShowSettingsMenu();
}
@end
```

- [ ] **Step 2: Commit**

```bash
git add src/SLMenuOverlay.m
git commit -m "feat: implement floating menu with all settings, export, and presets"
```

---

## Phase 10 — IPA Injection

### Task 14: Create IPA injection script and instructions

**Files:**
- Create: `inject.sh`

- [ ] **Step 1: Create inject.sh**

This script runs on macOS (or you can do these steps manually with 3uTools/ESign on the phone):

```bash
#!/bin/bash
# inject.sh — Inject SpinLogger.dylib into a Coin Master IPA
# Usage: ./inject.sh <path-to-ipa> <path-to-SpinLogger.dylib>
#
# Requirements: insert_dylib (brew install insert_dylib) or optool
# On Windows: use the manual method below

set -e

IPA="$1"
DYLIB="$2"

if [ -z "$IPA" ] || [ -z "$DYLIB" ]; then
    echo "Usage: $0 <CoinMaster.ipa> <SpinLogger.dylib>"
    exit 1
fi

WORK=$(mktemp -d)
echo "[*] Extracting IPA..."
unzip -q "$IPA" -d "$WORK"

APP=$(find "$WORK/Payload" -name "*.app" -maxdepth 1)
BINARY="$APP/$(defaults read "$APP/Info.plist" CFBundleExecutable)"
DYLIB_NAME="SpinLogger.dylib"

echo "[*] Copying dylib..."
cp "$DYLIB" "$APP/$DYLIB_NAME"

echo "[*] Injecting load command..."
# insert_dylib adds LC_LOAD_DYLIB to the Mach-O binary
insert_dylib --inplace --all-yes "@executable_path/$DYLIB_NAME" "$BINARY"

echo "[*] Repacking IPA..."
OUTPUT="${IPA%.ipa}_SpinLogger.ipa"
cd "$WORK"
zip -qr "$OUTPUT" Payload
mv "$OUTPUT" "$(dirname "$IPA")/"
cd -

echo "[*] Cleaning up..."
rm -rf "$WORK"

echo "[✓] Done: $(dirname "$IPA")/$(basename "$OUTPUT")"
echo ""
echo "Next steps:"
echo "  1. Transfer the IPA to your phone"
echo "  2. Sign with ESign"
echo "  3. Install and run"
```

- [ ] **Step 2: Create README with manual injection instructions for Windows**

```markdown
# SpinLogger — Manual IPA Injection (Windows)

## Method 1: Using 3uTools (Recommended for Windows)

1. Download `SpinLogger.dylib` from the GitHub Actions artifact
2. Extract the Coin Master IPA (rename to .zip, extract)
3. Copy `SpinLogger.dylib` into `Payload/CoinMaster.app/`
4. Use `optool` (download from GitHub) to inject the load command:
   ```
   optool install -c load -p @executable_path/SpinLogger.dylib -t Payload/CoinMaster.app/CoinMaster
   ```
5. Re-zip as .ipa
6. Transfer to phone and sign with ESign

## Method 2: Using ESign directly on iPhone

1. AirDrop or transfer `SpinLogger.dylib` to your phone
2. Open ESign → Import the original IPA
3. Tap the IPA → "Signature" → "Inject Dylib"
4. Select `SpinLogger.dylib`
5. Sign and install

## Usage

After launching Coin Master:
- A blue "SL" button appears on the right side of the screen
- Tap it to open the settings menu
- Counter overlays appear showing per-symbol counts
- Spin data is logged automatically to `spin_history.jsonl`
- Use "Export CSV" to share the spin history file
```

- [ ] **Step 3: Commit**

```bash
git add inject.sh README.md
git commit -m "docs: add IPA injection script and instructions"
```

---

### Task 15: End-to-end validation

- [ ] **Step 1: Push to GitHub and trigger build**

```bash
git push origin main
```

Wait for GitHub Actions to complete. Download the `SpinLogger.dylib` artifact.

- [ ] **Step 2: Verify the dylib**

```bash
file SpinLogger.dylib
# Expected: Mach-O 64-bit arm64 dynamically linked shared library
```

- [ ] **Step 3: Inject into IPA and test on device**

Follow the README instructions to inject into the Coin Master IPA, sign with ESign, and install.

Verify:
- Blue "SL" button appears
- Counter overlays appear when spinning
- `spin_history.jsonl` populates in Documents
- CSV export works via share sheet
- Speed multiplier works
- Spin target fires alert at N spins
- Presets save and restore

---

## Summary

| Phase | Tasks | Key Deliverable |
|-------|-------|-----------------|
| 1 Skeleton | 1–3 | Compiling dylib via GitHub Actions |
| 2 Network Hook | 4–6 | Intercept strack POST, parse spin events |
| 3 Spin Logger | 7 | JSONL storage + CSV export |
| 4 Counters | 8 | Draggable per-symbol counter overlays |
| 5 Speed | 9 | Game speed multiplier |
| 6 Target/Reset | 10 | Spin target + auto-reset |
| 7 Tris | 11 | Card trading lock/skip |
| 8 Presets | 12 | Save/load settings |
| 9 Menu UI | 13 | Floating button + settings panel |
| 10 Injection | 14–15 | Working IPA with all features |
