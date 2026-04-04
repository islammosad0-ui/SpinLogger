# SpinLogger — Discoveries & Technical Notes

## REAL-TIME Spin API (what One.dylib actually intercepts!)

- **URL**: `POST https://vik-game.moonactive.net/api/v1/users/{userId}/spin`
- **Called**: Once per spin, instantly
- **Response**: ~10KB JSON with spin result
- **THIS is what One.dylib intercepts — NOT strack!**

### Spin API Response Format:
| Field | Example | Type |
|-------|---------|------|
| r1 | 3 | int (symbol ID) |
| r2 | 4 | int (symbol ID) |
| r3 | 2 | int (symbol ID) |
| reward | 1 | int (reward type) |
| pay | 100000 | int (coins won) |
| coins | 11648749247106 | long (balance) |
| spins | 135527 | int (remaining) |
| shields | 5 | int |
| seq | 45439 | int (spin sequence #) |
| accumulation | {...} | dict |

### Symbol ID Mapping (verified from HAR cross-reference):
| ID | Symbol | 3x Reward |
|----|--------|-----------|
| 1 | coin | reward=1, pay=250000 |
| 2 | goldSack | reward=1, pay=150000 |
| 3 | attack | reward=2, pay=0 |
| 4 | steal/pig | reward=4 |
| 5 | shield | reward=3, pay=1 |
| 6 | spins | reward=5 |
| 30 | accumulation | special |

### Reward Types:
| ID | Name |
|----|------|
| 1 | gold |
| 2 | attack |
| 3 | shield |
| 4 | steal |
| 5 | spins |

### Request Body (form-encoded):
```
Device[udid]=...&API_KEY=viki&API_SECRET=coin&seq=45439&auto_spin=False&bet=1&Client[version]=3.5.2470_fbios
```

## Strack Endpoint (batched analytics — NOT real-time)

- **URL**: `POST https://vik-ca.moonactive.net/vikings/v3/strack/gzip`
- **Content-Type**: `application/octet-stream`
- **Body format**: Newline-delimited JSON (NDJSON), gzip on wire
- **Response**: `{"code":200,"errors":null,"data":{"status":"OK"}}` (always 200 OK)
- Batches 20+ spin events at once with delay — NOT suitable for real-time counting
- Only useful as backup/CSV logging

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

## One.dylib Server Communication (from HAR)

### Guard Worker — Anti-piracy heartbeat
- **URL**: `POST https://speeder-guard-worker.g3r7services.workers.dev/heartbeat`
- **Headers**: `X-PoW-Challenge: bcd2a31a`, `X-PoW-Nonce: 78180`
- **Body**: 32 bytes encrypted (application/octet-stream)
- **Response**: `{"status":"OK","wait":12,"token":3735928559}`
- `token = 0xDEADBEEF` (magic number — validates the mod is licensed)
- Called every ~10 seconds
- **If this fails, the mod likely disables itself**

### Monitor Worker — Config + telemetry
- **URL**: `POST https://speeder-monitor.g3r7services.workers.dev/heartbeat`
- **Body**: `{"version":"iOS 26.3.1","status":"online","deviceId":"7BDDCB73-..."}`
- **Response**: `{"status":"Heartbeat Received","serverTime":...,"config":{"auto_reset":true,"autostop":true,"tier":"ELITE"},"monitor":"idle"}`
- `tier: "ELITE"` — determines the UI title (SPEEDER ELITE vs SPEEDER)
- `auto_reset: true` — server controls feature flags
- `monitor: "idle"` — server can send remote commands
- **This is how they control the mod remotely and enforce licensing**

## GAE Event System & List Assignment

### Two Event Types (weekly, resets Monday)

**Standard (10 Symbol Event):**
- ONLY accumulation symbols (r=30) contribute to the GAE bar
- 1 symbol = +1pt, 2 symbols = +2pt, triple = +10pt (all × bet multiplier)

**Mix (10er Mix Symbol Event):**
- Accumulation symbols contribute as above
- PLUS either attack OR steal symbols also contribute (one type per event, not both):
  - 1 symbol = +1pt, 2 symbols = +2pt, triple = +5pt (all × bet multiplier)
- Detection: if `accum_delta > 0` on a spin with `acc_count == 0`, it's a mix event

### Event List Assignment (determined at event start)

At the START of each new event, the player's current spin count determines which reward list (difficulty tier) they get. Higher spins = harder list = more points needed for the same rewards.

| Starting Spins | List Difficulty |
|---|---|
| 0 - 999 | Easiest (300k-500k points) |
| 1k - 4.9k | Low |
| 5k - 9.9k | Mid-low |
| 10k - 19.9k | Mid |
| 20k - 39.9k | Mid-high |
| 40k - 74.9k | High |
| 75k - 149k | Higher |
| 150k - 299k | Highest (1.3M-1.7M points) |
| 300k+ | Max |

### Surprise Events
- Triggered when a player is inactive for ~1 week
- Server assigns an easier list to encourage return (retention mechanic)
- Randomly assigned regardless of spin count
- Same structure but easier point/reward tables

### API Fields for List Identification

From the `accumulation` object in the spin API response:

| Field | Path | Example | Purpose |
|-------|------|---------|---------|
| Segment | `accumulation.bonus.segment` | `bonus_bs15_gae0_no` | Encodes the list tier assignment |
| Last Mission | `accumulation.gaeMapData.lastMissionIndex` | `59` | Total milestones (unique per list) |
| Event ID | `accumulation.id` | `accumulation_2026-01-26T13:05:00.000Z_...` | Event instance + start time |
| Mission Map | `accumulation.gaeMapData.missions` | `{14: {reward: ...}}` | Upcoming milestone rewards |

The `gae_segment` + `gae_last_mission` + `spins_remaining` together uniquely identify which event list the player was assigned.

---

## Potion Rush Bar Detection

The Potion Rush bar (Expedition Cave Progressive) has a UUID that **changes every event rotation**. It CANNOT be detected by a hardcoded bar ID prefix.

**Correct detection:** Identify by the reward key `progressive_reward_pr_ec` inside the bar's `rewards` dictionary in `accumulationBarsById`.

**Bar completion:** Track `missionIndex` changes. When `missionIndex` increases between spins, the bar completed a milestone.

---

## Bet Multiplier Extraction

The `bet` parameter in the spin request body is the **actual multiplier value** (e.g. `bet=15` means 15x), NOT an index into `betOptions`.

Known bet values from HAR: `1, 2, 3, 15, 50, 150, 200, 600`

`betOptions` in the response (`superBet.betOptions`) lists available multipliers: `[1, 2, 3, 15, 50, 150, 200, 600]`. The `betLevel` in the response is a separate server-side level (e.g. always `5`) and does NOT correspond to the per-spin bet choice.

**Important:** The request body may be in `HTTPBodyStream` (not `HTTPBody`) because Unity uses stream-based request bodies. The stream is consumed during forwarding, so the bet value must be captured in `startLoading` before the request is forwarded.

---

## All Progress Bars in Spin API Response

### 3 API fields carry bar data per spin:
| API Field | What It Tracks |
|-----------|----------------|
| `accumulation` | Main GAE only (top-level) |
| `accumulationBarsById` | Potion Rush, Cave Blaster, Merge, Tournament, BBF |
| `serializedEvents` | Slot-on-Slot events (Dove + Cookie, only when 2nd slot has symbols) |

### Complete Bar Map:
| # | In-Game Name | API Field | What Fills It | Points Per Spin |
|---|-------------|-----------|---------------|-----------------|
| 1 | Main GAE (Rabbit Race) | `accumulation` | Accum symbols (r=30) on main slot | varies |
| 2 | Potion Rush (Expedition Cave) | `accumulationBarsById[pr_ec UUID]` | Every spin = +2pts | 2 |
| 3 | Cave Blaster (Expedition) | `accumulationBarsById[blaster UUID]` | Every spin = +1pt | 1 |
| 4 | Easter Dove (Slot-on-Slot) | `serializedEvents[GCEaster26]` | Dove symbols on 2nd slot | 1/2/5 |
| 5 | Easter Cookie (Slot-on-Slot) | `serializedEvents[LongExtraDayReduced]` | Cookie symbols on 2nd slot | 1/2/5 |
| 6 | Merge Energy | `accumulationBarsById[merge UUID]` | Every spin = +1pt | 1 |
| 7 | Bunny Dash (Tournament) | `accumulationBarsById[tournament UUID]` | Raids/Attacks (8/6/5/4pts) | varies |
| 8 | Bring Back Friends | `accumulationBarsById[BBF UUID]` | Friend collects | 0 |
| 9 | Single Reward | `accumulationBarsById[UUID]` | ? | ? |

### Second Slot Symbols (additionalSlots.second_slot.reels[]):
| HAR value | Maps to | Scoring |
|-----------|---------|---------|
| `GCEaster26` | Easter Dove (#4) | 1 sym=+1, 2 sym=+2, 3 sym=+5 (x bet) |
| `LongExtraDayReduced` | Easter Cookie (#5) | 1 sym=+1, 2 sym=+2, 3 sym=+5 (x bet) |
| `""` (empty) | nothing | no points |

### Reward Currency Mapping:
| HAR reward key | In-game name |
|---------------|--------------|
| `progressive_reward_pr_ec` | Potion Rush points |
| `expedition_cave_blaster` | Cave blaster item |
| `generic_currency_egg_currency` | Easter eggs |
| `token_currency_wheel_token_cw_one` | Wheel token |
| `generic_currency_merge_energy` | Merge energy |

### Mini Events Rotation:
- Mini events rotate (unlike main GAE which resets every Monday)
- Potion Rush, Cave Blaster, Merge Energy are common rotating events
- Slot-on-Slot events (Easter Dove/Cookie) are seasonal
- Tournament (Bunny Dash) is periodic

### Encrypted Config Key
From strings: `SPEEDER_LEVEL_SECURE_SALT_v2_LOCAL_ONLY`
Hex key found: `2343453635021768305523525c27685f5d33335938435c2728165b282e1921445e28695b572b2f532843582928174e756d0765071e2529545422204222585f682c4b5729`

## Where One.dylib Gets Its UI (HTML/CSS/JS)

**The UI is NOT hardcoded — it's fetched and cached from an encrypted server.**

### Content Delivery Architecture:
1. `O8xJs4` class (content fetcher) has these methods:
   - `fetchFrontendWithCompletion:` — Fetches the main SPEEDER ELITE panel HTML
   - `fetchSingleCounterWithId:completion:` — Fetches individual counter HTML (loads `index.html` from `%@/counter/%@` URL pattern)
   - `fetchSpinCounterWithCompletion:` — Fetches spin counter HTML
   - `fetchSpinCounterWithStaticHashCompletion:` — Fetches with hash validation
   - `fetchTrisMonitorWithCompletion:` — Fetches tris monitor HTML
2. Content is validated: checks for `<!doctype` or `<html` prefix
3. Cached locally: `frontend_cache.dat` + `frontend_meta.plist` (hash, tier)
4. Encrypted content uses `resolveBunkerString:length:` to decrypt embedded data
5. Some HTML is embedded as encrypted byte arrays (`FUN_0003db40` + encrypted DAT_ blocks)

### HTML Resources:
| Resource | Purpose |
|----------|---------|
| `index.html` | Main frontend entry point |
| `%@/counter/%@` | Individual counter WebView (per symbol) |
| `tris_monitor.html` | Tris monitor with columns |
| `spin_counter.html` | Spin counter display |
| `frontend_cache.dat` | Cached binary frontend data |

### WebView Architecture:
- `mainWebView` — The SPEEDER ELITE panel (fetched frontend)
- `spinWebView` — Spin counter display (separate window)
- `trisWebView` — Tris monitor with 5 columns
- `counterWebViews` — Dict of `[String: WKWebView]`, one per symbol (hammer, pig, pills, potion, symbol)
- Each counter is its own draggable WKWebView window
- All use `nativeBridge` script message handler

### Data Flow (Spin → UI):
1. Strack POST intercepted by NSURLProtocol
2. `KEDCui.K8CGHq(payload:)` posts `NetShearsSpinEvent` notification
3. `GajlCdZgJ.handleSpinNotification:` receives it
4. For counters: `window.increment()` injected into each counter's WKWebView
5. For spin display: `window.incrementSpin()` injected
6. For tris: `window.registerTris('symbol')` injected into trisWebView
7. On 3-of-a-kind: counts snapshot to tris history, counters reset

### KEY INSIGHT: The UI HTML/CSS/JS is NOT in the dylib binary
The polished SPEEDER ELITE look (glassmorphism, gradients, animations) comes from
HTML/CSS/JS that is either:
- Fetched from a remote server (encrypted)
- Embedded as encrypted byte arrays and decrypted at runtime via `resolveBunkerString`
- Cached in `frontend_cache.dat` for offline use

This means we CANNOT extract the exact CSS/HTML from the binary — it's encrypted.
We must recreate the UI from the screenshots.
