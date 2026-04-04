# SpinLogger — Discoveries & Technical Notes

## Strack Endpoint

- **URL**: `POST https://vik-ca.moonactive.net/vikings/v3/strack/gzip`
- **Content-Type**: `application/octet-stream`
- **Body format**: Newline-delimited JSON (NDJSON) — **NOT actually gzip compressed** despite the URL
- **Response**: `{"code":200,"errors":null,"data":{"status":"OK"}}` (always 200 OK)
- The game sends analytics events TO this endpoint (request body), spin results are NOT in the response

## Spin Event Format

Each line in the strack body is a JSON object. Spin events have `"event": "spin"`.

### Key fields in `msg`:
| Field | Example | Notes |
|-------|---------|-------|
| spin_number | "35091" | **String**, not integer |
| spin_result | "steal" | gold, attack, steal, shield, spins, accumulation |
| spin_result_symbols | "steal,steal,steal" | Comma-separated reel symbols |
| spin_amount_won | "0" | **String** |
| auto_spin | "false" | **String** "true"/"false" |
| bet_type | "X1" | X1, X2, X3, etc. |
| coins | "8311235916183" | Current coin balance |
| spins | "494247" | Spins remaining |
| shields | "5" | Shield count (string in some versions) |
| village | N/A | Found as `level` = "11" |
| active_pet | "FOX" | FOX, TIGER, RHINO |
| all_time_spins | "35092" | Total lifetime spins |
| sos_1_TA | "BluePotion" | SOS symbol |
| result | "empty,LongExtraDayReduced,empty" | Accumulation bar result |

### Important: All values are STRINGS, not numbers!

## Other Strack Events (in same request)
- `device_info` — always first line
- `spin` — spin results
- `raid_start` / `raid_end` — steal events
- `attack_end` — attack results
- `chest_found` — chest opens
- `sos_symbol_created_TA` — SOS events
- `accumulation_event_id` — accumulation bar events

## One.dylib (Nuovo Speeder Level) Analysis

### Module name: `Nuovo_Speeder_Level`
### Size: 649KB (Swift + ObjC)
### Signed by: Apple Development: Cali Mitchell (BVQSNR6HVW)

### NSUserDefaults Keys (Speeder_* prefix):
| Key | Example Value | Purpose |
|-----|--------------|---------|
| Speeder_AutoresetMode | "symbol" | none / symbol / global |
| Speeder_CounterPositions | dict {hammer:{x,y}, pig:{x,y}, ...} | Counter position persistence |
| Speeder_LastSpeed | 10.8 | Speed multiplier |
| Speeder_Network | True | Network logging enabled |
| Speeder_SpinCounter | True | Counter visible |
| Speeder_Preset1 | dict | Saved preset 1 |
| Speeder_Preset2 | dict | Saved preset 2 |
| Speeder_TrisLock | string | Tris lock target |
| Speeder_TrisMonitor | bool | Tris monitor enabled |

### Symbol key mapping (for counter positions):
| Game Symbol | Speeder Key | Emoji | Color |
|------------|-------------|-------|-------|
| attack | hammer | 🔨 | Cyan #00e5ff |
| steal | pig | 🐷 | Pink #ff69b4 |
| accumulation | pills | 💊 | Cyan #00bcd4 |
| shield | plant (?) | 🌱 | Purple/Yellow |
| goldSack | potion | 🧪 | Green #4caf50 |
| spins | symbol | 🎰 | — |

### Jailbreak Detection Paths (33 total):
Checks for: Cydia, Sileo, Zebra, frida, cycript, sshd, MobileSubstrate, etc.
Full list in `SLJailbreakBypass.m`.

### UI Architecture:
- Uses WKWebView for counter display and tris monitor
- SwiftUI for network flow view (NetshearsFlowView)
- Custom UIKit panels with glassmorphism dark theme
- HTML-based counter columns with color-coded numbers

## Network Architecture
- Game uses UnityWebRequest (UWR) which maps to NSURLSession on iOS
- Analytics go to `vik-ca.moonactive.net` (strack)
- Game API at `api.moonactive.net` with fallback
- **Strack body IS gzip compressed** (`Content-Encoding: gzip`, Content-Length: 844 for ~4000 chars decoded)
- HAR files show decoded content, but the actual wire bytes are gzip
- `X-Unity-Version: 2022.3.59f1` header present
- `x-compress: true` header also set
- Request `Content-Type: application/octet-stream`

## How One.dylib Extracts Data
- Uses `NetworkListenerUrlProtocol` (NSURLProtocol subclass) to intercept ALL HTTP
- NSURLProtocol sees the raw request BEFORE Content-Encoding is applied
- So One.dylib sees the **uncompressed NDJSON** directly from the HTTPBody
- Also uses NSURLSession delegate methods as backup
- Parses the body for `"event":"spin"` lines
- Feeds parsed data to WKWebView counters and tris monitor

## Key Insight: NSURLSession Swizzle vs NSURLProtocol
- When swizzling `-[NSURLSession dataTaskWithRequest:completionHandler:]`, the `request.HTTPBody` contains the **raw uncompressed** body
- The gzip compression happens at the transport layer AFTER our swizzle
- So our interceptor SHOULD see plain NDJSON in `request.HTTPBody`
- If `HTTPBody` is nil, the body might be in `HTTPBodyStream` instead (Unity sometimes uses streams)
- The stream ALSO contains uncompressed data

---

## Ghidra Decompilation Results (3,523 functions, 85K lines)

Full decompiled source: `C:\Users\Islam\Desktop\ghidra_out\decompiled.c`

### Class Map (demangled from Swift symbols)

| Obfuscated Name | Real Purpose | Key Properties |
|-----------------|-------------|----------------|
| `GajlCdZgJ` | **Main Controller** (singleton `shared`) | targetEndpointPattern, counterWebViews, pendingRequests, stateQueue, spinTarget, currentSessionSpinCount, targetSpinResetMode, autoresetEnabled, autoresetMode, autoresetConfig, targetLockTriggered, trisLockTarget, lastAnalysisTime |
| `KEDCui` | **Network Listener** (singleton `shared`) | swizzled, listenerEnable, interceptorEnable, config (lazy) |
| `Ji7SfZ` | **Startup Initializer** | `initializeAtStartup()` — class method, entry point |
| `Z6qATBJJWZ` | **Request Model** | url, host, method, scheme, port, date, code, httpBody, dataResponse, responseHeaders, cookies, duration, isFinished, headers, credentials, errorClientDescription |
| `Ry4K7EV` | **Configuration** (lazy storage on KEDCui) | Network config object |
| `EgsDJayPT` | **Request Broadcaster** (singleton `shared`) | delegate (RequestBroadcastDelegate) |
| `D4083JN5T` | **Persistence Manager** (singleton `shared`) | masterState, queue, fileName |
| `QYsl7dpn` | **Encryption Utility** | `decrypt(_:length:)` static method |
| `PersistenceManager` | **State Persistence** | `updateState(module:data:)`, `getJSONState()` |

### Initialization Flow (from Ghidra)

1. **`Ji7SfZ.initializeAtStartup()`** — Called on dylib load
2. Creates a `DispatchQueue` and schedules work with `asyncAfter(deadline:)` (0.5s delay)
3. The delayed block calls:
   - `GajlCdZgJ.shared.startMonitoring()`
   - Which calls `KEDCui.shared.startListener()` + `KEDCui.shared.WVYSns()` (interceptor enable)
4. `KEDCui.WVYSns()` → calls `FUN_000113b8` which sets `interceptorEnable = true`
5. `KEDCui.startListener()` → calls `FUN_00011504` which sets `listenerEnable = true`
6. `FUN_00017ed8()` — **The Swizzle Function**: checks `KEDCui.swizzled` flag, if false calls `FUN_00011320()` (the actual method swizzling) and sets `swizzled = true`
7. `startMonitoring()` also registers for `NetShearsSpinEvent` notification via `NSNotificationCenter`

### Network Interception (from Ghidra)

One.dylib uses a **dual approach**:

**Layer 1: NSURLProtocol** (`NetworkListenerUrlProtocol`)
- Registered as a custom URL protocol
- Intercepts ALL HTTP at the URL loading system level
- Uses `URLProtocol:didLoadData:`, `URLProtocol:didReceiveResponse:cacheStoragePolicy:`
- Has `RequestEvaluatorModifierResponse` that can MODIFY responses
- Can redirect requests via `RedirectedRequestModel`

**Layer 2: NSURLSession Delegate** (not swizzling!)
- Implements `NSURLSessionDataDelegate`, `NSURLSessionTaskDelegate`, `NSURLSessionDelegate`
- Methods found in decompiled code:
  - `URLSession:dataTask:didReceiveData:` (3 implementations at different addresses!)
  - `URLSession:dataTask:didReceiveResponse:completionHandler:`
  - `URLSession:task:didCompleteWithError:`
  - `URLSession:task:willPerformHTTPRedirection:newRequest:completionHandler:`
  - `URLSession:didBecomeInvalidWithError:`
  - `URLSession:didReceiveChallenge:completionHandler:`
  - `URLSession:task:didSendBodyData:totalBytesSent:totalBytesExpectedToSend:`

**Data Flow:**
1. `NSURLProtocol` or delegate catches request → creates `Z6qATBJJWZ` (Request Model)
2. `KEDCui.K8CGHq(payload:)` — Posts `NetShearsSpinEvent` notification with parsed payload dict
3. `GajlCdZgJ.handleSpinNotification:` — Receives notification
4. `GajlCdZgJ.newRequestArrived(_:Z6qATBJJWZ)` — Processes request on `stateQueue`
5. Checks `targetEndpointPattern` to filter for strack
6. Parses spin data and updates WKWebViews via JS evaluation

### Spin Processing (from Ghidra)

`newRequestArrived` does:
1. Checks if request `isFinished`
2. Matches URL against `targetEndpointPattern`
3. If matched, dispatches to `stateQueue` (serial queue for thread safety)
4. Uses `QYsl7dpn.decrypt(_:length:)` for encrypted payloads
5. Calls `FUN_00008140` which parses the NDJSON body
6. Updates counter WKWebViews and tris monitor
7. Increments `currentSessionSpinCount`
8. Checks `spinTarget` and `targetSpinResetMode` for auto-reset

### Security Features (from Ghidra)

- `QYsl7dpn` class has `decrypt(_:length:)` static method for payload decryption
- `encryptPayload:withKey:` and `decryptPayload:withKey:` for encrypted config
- `__sendEncryptedPayload` for secure communication
- `JailbreakDetector_v3` — checks 33+ filesystem paths
- `HookDetector` — detects Frida/Cycript hooks
- `PointerAuth` — ARM pointer authentication checks
- `KeychainGuard` — keychain-based integrity verification

### Encrypted Config Key
From strings: `SPEEDER_LEVEL_SECURE_SALT_v2_LOCAL_ONLY`
Hex key found: `2343453635021768305523525c27685f5d33335938435c2728165b282e1921445e28695b572b2f532843582928174e756d0765071e2529545422204222585f682c4b5729`
