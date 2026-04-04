# One.dylib (Nuovo_Speeder_Level) -- Full Reverse Engineering Report

> **Binary**: `One.dylib` (Mach-O 64-bit ARM64 dynamically linked shared library)  
> **Size**: 664,272 bytes  
> **Total symbols**: 1182  
> **Module symbols**: 449  
> **Unique entities**: 25  
> **Module name**: `Nuovo_Speeder_Level` (19 chars)  
> **Swift mangling prefix**: `$s19Nuovo_Speeder_Level`  

---

## 1. Binary Structure -- Segments and Sections

### Segment: `__TEXT`
- VM Address: `0x0`, VM Size: `0x6c000` (442,368 bytes)
- File Offset: `0x0`, File Size: `0x6c000` (442,368 bytes)

| Section | Offset | Size | Type |
|---------|--------|------|------|
| `__text` | `0x4000` | `0x47b90` (293,776) | TYPE.REGULAR |
| `__stubs` | `0x4bb90` | `0x1410` (5,136) | TYPE.SYMBOL_STUBS |
| `__objc_stubs` | `0x4cfa0` | `0x20a0` (8,352) | TYPE.REGULAR |
| `__init_offsets` | `0x4f040` | `0xc` (12) | TYPE.INIT_FUNC_OFFSETS |
| `__objc_methlist` | `0x4f050` | `0x1dec` (7,660) | TYPE.REGULAR |
| `__const` | `0x50e40` | `0x7548` (30,024) | TYPE.REGULAR |
| `__cstring` | `0x58390` | `0x2e37` (11,831) | TYPE.CSTRING_LITERALS |
| `__swift5_typeref` | `0x5b1c8` | `0xe5b` (3,675) | TYPE.REGULAR |
| `__objc_methname` | `0x5c023` | `0x540e` (21,518) | TYPE.CSTRING_LITERALS |
| `__swift5_capture` | `0x61434` | `0x368` (872) | TYPE.REGULAR |
| `__swift5_reflstr` | `0x617a0` | `0x3f` (63) | TYPE.REGULAR |
| `__swift5_assocty` | `0x617e0` | `0x98` (152) | TYPE.REGULAR |
| `__constg_swiftt` | `0x61878` | `0x12c8` (4,808) | TYPE.REGULAR |
| `__swift5_fieldmd` | `0x62b40` | `0x10f8` (4,344) | TYPE.REGULAR |
| `__swift5_builtin` | `0x63c38` | `0x28` (40) | TYPE.REGULAR |
| `__swift5_protos` | `0x63c60` | `0x2c` (44) | TYPE.REGULAR |
| `__swift5_proto` | `0x63c8c` | `0x254` (596) | TYPE.REGULAR |
| `__swift5_types` | `0x63ee0` | `0x120` (288) | TYPE.REGULAR |
| `__objc_classname` | `0x64000` | `0x22c` (556) | TYPE.CSTRING_LITERALS |
| `__objc_methtype` | `0x6422c` | `0x1eb6` (7,862) | TYPE.CSTRING_LITERALS |
| `__gcc_except_tab` | `0x660e4` | `0x2b0` (688) | TYPE.REGULAR |
| `__unwind_info` | `0x66394` | `0x1308` (4,872) | TYPE.REGULAR |
| `__eh_frame` | `0x676a0` | `0xde4` (3,556) | TYPE.COALESCED |

### Segment: `__DATA_CONST`
- VM Address: `0x6c000`, VM Size: `0x8000` (32,768 bytes)
- File Offset: `0x6c000`, File Size: `0x8000` (32,768 bytes)

| Section | Offset | Size | Type |
|---------|--------|------|------|
| `__got` | `0x6c000` | `0x12e8` (4,840) | TYPE.NON_LAZY_SYMBOL_POINTERS |
| `__const` | `0x6d2e8` | `0x3238` (12,856) | TYPE.REGULAR |
| `__cfstring` | `0x70520` | `0x1560` (5,472) | TYPE.REGULAR |
| `__objc_classlist` | `0x71a80` | `0x1b0` (432) | TYPE.REGULAR |
| `__objc_catlist` | `0x71c30` | `0x8` (8) | TYPE.REGULAR |
| `__objc_protolist` | `0x71c38` | `0xe0` (224) | TYPE.REGULAR |
| `__objc_imageinfo` | `0x71d18` | `0x8` (8) | TYPE.REGULAR |
| `__objc_protorefs` | `0x71d20` | `0x68` (104) | TYPE.REGULAR |
| `__objc_superrefs` | `0x71d88` | `0x38` (56) | TYPE.REGULAR |
| `__objc_arraydata` | `0x71dc0` | `0x208` (520) | TYPE.REGULAR |
| `__objc_arrayobj` | `0x71fc8` | `0x210` (528) | TYPE.REGULAR |

### Segment: `__DATA`
- VM Address: `0x74000`, VM Size: `0x10000` (65,536 bytes)
- File Offset: `0x74000`, File Size: `0xc000` (49,152 bytes)

| Section | Offset | Size | Type |
|---------|--------|------|------|
| `__objc_const` | `0x74000` | `0x34d0` (13,520) | TYPE.REGULAR |
| `__objc_selrefs` | `0x774d0` | `0x1808` (6,152) | TYPE.LITERAL_POINTERS |
| `__objc_ivar` | `0x78cd8` | `0x54` (84) | TYPE.REGULAR |
| `__objc_data` | `0x78d30` | `0x1f70` (8,048) | TYPE.REGULAR |
| `__data` | `0x7aca0` | `0x18a0` (6,304) | TYPE.REGULAR |
| `__bss` | `0x0` | `0x4ea8` (20,136) | TYPE.ZEROFILL |
| `__common` | `0x0` | `0xe0` (224) | TYPE.ZEROFILL |

### Segment: `__LINKEDIT`
- VM Address: `0x84000`, VM Size: `0x24000` (147,456 bytes)
- File Offset: `0x80000`, File Size: `0x222d0` (139,984 bytes)

## 2. Linked Libraries

| Library | Category |
|---------|----------|
| `out/arm64-apple-ios/iQG.dylib` | Custom (self-reference) |
| `/usr/lib/libc++.1.dylib` | System Runtime |
| `/System/Library/Frameworks/Foundation.framework/Foundation` | Framework |
| `/System/Library/Frameworks/UIKit.framework/UIKit` | Framework |
| `/System/Library/Frameworks/WebKit.framework/WebKit` | Framework |
| `/System/Library/Frameworks/SwiftUI.framework/SwiftUI` | Swift Runtime |
| `/System/Library/Frameworks/Security.framework/Security` | Framework |
| `/System/Library/Frameworks/SpriteKit.framework/SpriteKit` | Framework |
| `/usr/lib/libobjc.A.dylib` | System Runtime |
| `/usr/lib/libSystem.B.dylib` | System Runtime |
| `/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation` | Framework |
| `/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics` | Framework |
| `/System/Library/Frameworks/CryptoKit.framework/CryptoKit` | Framework |
| `/System/Library/Frameworks/SafariServices.framework/SafariServices` | Framework |
| `/usr/lib/swift/libswiftCore.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftCoreFoundation.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftCoreImage.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftDispatch.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftMetal.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftOSLog.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftObjectiveC.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftQuartzCore.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftSpatial.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftUniformTypeIdentifiers.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftXPC.dylib` | Swift Runtime |
| `/usr/lib/swift/libswift_Builtin_float.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftos.dylib` | Swift Runtime |
| `/usr/lib/swift/libswiftsimd.dylib` | Swift Runtime |

## 3. Full Class Hierarchy (Demangled)

### Legend
- Class names like `GajlCdZgJ` are **obfuscated** Swift names (scrambled at build time)
- Properties and methods retain their **original names** in most cases
- ObjC name format: `_TtC19Nuovo_Speeder_Level{len}{Name}`

### `D4083JN5T` (class)
- **ObjC Name**: `_TtC19Nuovo_Speeder_Level9D4083JN5T`
- **Purpose**: Settings/Config singleton (networkEnabled, skipTrisEnabled, trisLockEnabled)
- **Symbol count**: 38

**Properties:**

| Property | Type |
|----------|------|
| `networkEnabled` | `Bool` |
| `networkRequestInterceptor` | `inferred` |
| `shared` | `inferred` |
| `skipTrisEnabled` | `Bool` |
| `trisLockEnabled` | `Bool` |

### `EgsDJayPT` (class)
- **ObjC Name**: `_TtC19Nuovo_Speeder_Level9EgsDJayPT`
- **Purpose**: Request Broadcast Delegate hub (shared, setDelegate, removeDelegate)
- **Symbol count**: 13

**Properties:**

| Property | Type |
|----------|------|
| `delegate` | `inferred` |
| `shared` | `inferred` |

**Methods:**

- `removeDelegate()`
- `setDelegate()`

### `GajlCdZgJ` (class)
- **ObjC Name**: `_TtC19Nuovo_Speeder_Level9GajlCdZgJ`
- **Purpose**: Main ViewModel / SharedManager (spin counter, tris monitor, counter WebViews)
- **Symbol count**: 52

**Properties:**

| Property | Type |
|----------|------|
| `autoresetConfig` | `Dictionary<String, Any>` |
| `autoresetEnabled` | `inferred` |
| `autoresetMode` | `String?` |
| `counterWebViews` | `inferred` |
| `currentSessionSpinCount` | `inferred` |
| `lastAnalysisTime` | `inferred` |
| `mainWebView` | `inferred` |
| `pendingRequests` | `inferred` |
| `shared` | `inferred` |
| `spinTarget` | `inferred` |
| `stateQueue` | `inferred` |
| `targetEndpointPattern` | `String?` |
| `targetLockTriggered` | `inferred` |
| `targetSpinResetMode` | `inferred` |
| `trisLockTarget` | `String?` |
| `trisWebView` | `inferred` |

**Methods:**

- `configure()`
- `configureAutoreset()`
- `handleGlobalReset()`
- `handleManualReset()`
- `newRequestArrived()`
- `resumeFromTargetSpin()`
- `setCounterWebView()`
- `setMainWebView()`
- `setSpinTarget()`
- `setTrisLockTarget()`
- `setTrisWebView()`
- `startMonitoring()`
- `stopMonitoring()`

### `Ji7SfZ` (class)
- **ObjC Name**: `_TtC19Nuovo_Speeder_Level6Ji7SfZ`
- **Purpose**: Startup initializer (initializeAtStartup)
- **Symbol count**: 7

**Methods:**

- `initializeAtStartup()`

### `KEDCui` (class)
- **ObjC Name**: `_TtC19Nuovo_Speeder_Level6KEDCui`
- **Purpose**: NetShears main controller (logger, listener, interceptor, modifier)
- **Symbol count**: 50

**Properties:**

| Property | Type |
|----------|------|
| `bodyExportDelegate` | `inferred` |
| `ignore` | `inferred` |
| `interceptorEnable` | `Bool` |
| `listenerEnable` | `Bool` |
| `loggerEnable` | `Bool` |
| `networkRequestInterceptor` | `inferred` |
| `shared` | `inferred` |
| `swizzled` | `Bool` |
| `taskProgressDelegate` | `inferred` |

**Methods:**

- `HWu1bjL()`
- `K8CGHq()`
- `WVYSns()`
- `addGRPC()`
- `modifiedList()`
- `modify()`
- `presentNetworkMonitor()`
- `removeModifier()`
- `startGestureRecognizer()`
- `startListener()`
- `startLogger()`
- `stopInterceptor()`
- `stopListener()`
- `stopLogger()`
- `view()`

### `PersistenceManager` (class)
- **ObjC Name**: `_TtC19Nuovo_Speeder_Level18PersistenceManager`
- **Purpose**: State persistence to disk (JSON state, file I/O)
- **Symbol count**: 15

**Properties:**

| Property | Type |
|----------|------|
| `fileName` | `inferred` |
| `masterState` | `Dictionary<String, Any>` |
| `queue` | `inferred` |
| `shared` | `inferred` |

**Methods:**

- `getJSONState()`
- `updateState()`

### `QYsl7dpn` (class)
- **ObjC Name**: `_TtC19Nuovo_Speeder_Level8QYsl7dpn`
- **Purpose**: Decryptor class (decrypt method)
- **Symbol count**: 7

**Methods:**

- `decrypt()`

### `Z6qATBJJWZ` (class)
- **ObjC Name**: `_TtC19Nuovo_Speeder_Level10Z6qATBJJWZ`
- **Purpose**: HTTP Request Model (url, method, headers, body, response, duration, cookies)
- **Symbol count**: 87

**Properties:**

| Property | Type |
|----------|------|
| `code` | `Int` |
| `cookies` | `String?` |
| `credentials` | `Dictionary<String, String>` |
| `dataResponse` | `Foundation.Data?` |
| `date` | `Foundation.Date` |
| `duration` | `Double?` |
| `errorClientDescription` | `String?` |
| `headers` | `Dictionary<String, String>` |
| `host` | `String?` |
| `httpBody` | `Foundation.Data?` |
| `id` | `String` |
| `isFinished` | `Bool` |
| `method` | `String` |
| `port` | `Int?` |
| `responseHeaders` | `Dictionary<String, String>` |
| `scheme` | `String?` |
| `url` | `String` |

**Methods:**

- `encode()`
- `from()`

### `HTTPResponseModifyModel` (struct)
- **Purpose**: Response modifier model (url, data, method, statusCode, headers)
- **Symbol count**: 24

**Properties:**

| Property | Type |
|----------|------|
| `data` | `inferred` |
| `headers` | `Dictionary<String, String>` |
| `httpMethod` | `String` |
| `httpVersion` | `String?` |
| `response` | `inferred` |
| `statusCode` | `Int` |
| `url` | `String` |

**Methods:**

- `__derived_struct_equals()`
- `encode()`
- `from()`
- `url()`

### `HeaderModifyModel` (struct)
- **Purpose**: Header modifier data model (key, value)
- **Symbol count**: 14

**Properties:**

| Property | Type |
|----------|------|
| `key` | `String` |
| `value` | `String` |

**Methods:**

- `__derived_struct_equals()`
- `encode()`
- `from()`
- `key()`

### `NetshearsFlowView` (struct)
- **Purpose**: SwiftUI wrapper (UIViewControllerRepresentable)
- **Symbol count**: 8

**Methods:**

- `SwiftUI()`
- `makeUIViewController()`
- `updateUIViewController()`

### `RedirectedRequestModel` (struct)
- **Purpose**: Redirect model (originalUrl, redirectUrl)
- **Symbol count**: 14

**Properties:**

| Property | Type |
|----------|------|
| `originalUrl` | `String` |
| `redirectUrl` | `String` |

**Methods:**

- `__derived_struct_equals()`
- `encode()`
- `from()`
- `originalUrl()`

### `RequestEvaluatorModifierEndpoint` (struct)
- **Purpose**: Endpoint-based request evaluator (with redirect)
- **Symbol count**: 26

**Properties:**

| Property | Type |
|----------|------|
| `redirected` | `inferred` |
| `storeFileName` | `String` |

**Methods:**

- `__derived_struct_equals()`
- `encode()`
- `from()`
- `isActionAllowed()`
- `modify()`
- `redirected()`

### `RequestEvaluatorModifierHeader` (struct)
- **Purpose**: Header-based request evaluator
- **Symbol count**: 26

**Properties:**

| Property | Type |
|----------|------|
| `header` | `inferred` |
| `storeFileName` | `String` |

**Methods:**

- `__derived_struct_equals()`
- `encode()`
- `from()`
- `header()`
- `isActionAllowed()`
- `modify()`

### `RequestEvaluatorModifierResponse` (struct)
- **Purpose**: Response-based request evaluator
- **Symbol count**: 26

**Properties:**

| Property | Type |
|----------|------|
| `response` | `inferred` |
| `storeFileName` | `String` |

**Methods:**

- `__derived_struct_equals()`
- `encode()`
- `from()`
- `isActionAllowed()`
- `modify()`
- `response()`

### `BodyExportType` (enum)
- **Purpose**: Enum for body export format
- **Symbol count**: 3

### `Ignore` (enum)
- **Purpose**: Enum for ignore rules
- **Symbol count**: 3

### `BodyExporterDelegate` (protocol)
- **Purpose**: Protocol for body export callbacks
- **Symbol count**: 4

### `Modifier` (protocol)
- **Purpose**: Protocol for request modification
- **Symbol count**: 6

### `RequestActionModifier` (protocol)
- **Purpose**: Protocol for request action modification
- **Symbol count**: 3

### `RequestBroadcastDelegate` (protocol)
- **Purpose**: Protocol for request broadcast callbacks
- **Symbol count**: 2

### `RequestModifier` (protocol)
- **Purpose**: Protocol for request modification (extends Modifier)
- **Symbol count**: 3

### `RequestModifierStorage` (protocol)
- **Purpose**: Protocol for modifier storage
- **Symbol count**: 2

### `Svtj2s5frM` (protocol)
- **Purpose**: Protocol (unknown)
- **Symbol count**: 2

### `TaskProgressDelegate` (protocol)
- **Purpose**: Protocol for task progress callbacks
- **Symbol count**: 2

## 4. Complete Entity Reference Table

| Obfuscated Name | Type | ObjC Name | Purpose |
|-----------------|------|-----------|---------|
| `D4083JN5T` | class | `_TtC19Nuovo_Speeder_Level9D4083JN5T` | Settings/Config singleton (networkEnabled, skipTrisEnabled, trisLockEnabled) |
| `EgsDJayPT` | class | `_TtC19Nuovo_Speeder_Level9EgsDJayPT` | Request Broadcast Delegate hub (shared, setDelegate, removeDelegate) |
| `GajlCdZgJ` | class | `_TtC19Nuovo_Speeder_Level9GajlCdZgJ` | Main ViewModel / SharedManager (spin counter, tris monitor, counter WebViews) |
| `Ji7SfZ` | class | `_TtC19Nuovo_Speeder_Level6Ji7SfZ` | Startup initializer (initializeAtStartup) |
| `KEDCui` | class | `_TtC19Nuovo_Speeder_Level6KEDCui` | NetShears main controller (logger, listener, interceptor, modifier) |
| `PersistenceManager` | class | `_TtC19Nuovo_Speeder_Level18PersistenceManager` | State persistence to disk (JSON state, file I/O) |
| `QYsl7dpn` | class | `_TtC19Nuovo_Speeder_Level8QYsl7dpn` | Decryptor class (decrypt method) |
| `Z6qATBJJWZ` | class | `_TtC19Nuovo_Speeder_Level10Z6qATBJJWZ` | HTTP Request Model (url, method, headers, body, response, duration, cookies) |
| `HTTPResponseModifyModel` | struct | `--` | Response modifier model (url, data, method, statusCode, headers) |
| `HeaderModifyModel` | struct | `--` | Header modifier data model (key, value) |
| `NetshearsFlowView` | struct | `--` | SwiftUI wrapper (UIViewControllerRepresentable) |
| `RedirectedRequestModel` | struct | `--` | Redirect model (originalUrl, redirectUrl) |
| `RequestEvaluatorModifierEndpoint` | struct | `--` | Endpoint-based request evaluator (with redirect) |
| `RequestEvaluatorModifierHeader` | struct | `--` | Header-based request evaluator |
| `RequestEvaluatorModifierResponse` | struct | `--` | Response-based request evaluator |
| `BodyExportType` | enum | `--` | Enum for body export format |
| `Ignore` | enum | `--` | Enum for ignore rules |
| `BodyExporterDelegate` | protocol | `--` | Protocol for body export callbacks |
| `Modifier` | protocol | `--` | Protocol for request modification |
| `RequestActionModifier` | protocol | `--` | Protocol for request action modification |
| `RequestBroadcastDelegate` | protocol | `--` | Protocol for request broadcast callbacks |
| `RequestModifier` | protocol | `--` | Protocol for request modification (extends Modifier) |
| `RequestModifierStorage` | protocol | `--` | Protocol for modifier storage |
| `Svtj2s5frM` | protocol | `--` | Protocol (unknown) |
| `TaskProgressDelegate` | protocol | `--` | Protocol for task progress callbacks |

## 5. Interception Mechanism

### 5.1 NSURLSession Swizzling

The dylib hooks into network traffic through **ObjC method swizzling** of NSURLSession delegate methods.

- `URLProtocol:didFailWithError:`
- `URLProtocol:didLoadData:`
- `URLProtocol:didReceiveResponse:cacheStoragePolicy:`
- `URLProtocol:wasRedirectedToRequest:redirectResponse:`
- `URLProtocolDidFinishLoading:`
- `URLSession:dataTask:didBecomeDownloadTask:`
- `URLSession:dataTask:didBecomeStreamTask:`
- `URLSession:dataTask:didReceiveData:`
- `URLSession:dataTask:didReceiveResponse:completionHandler:`
- `URLSession:dataTask:willCacheResponse:completionHandler:`
- `URLSession:didBecomeInvalidWithError:`
- `URLSession:didCreateTask:`
- `URLSession:didReceiveChallenge:completionHandler:`
- `URLSession:task:didCompleteWithError:`
- `URLSession:task:didFinishCollectingMetrics:`
- `URLSession:task:didReceiveChallenge:completionHandler:`
- `URLSession:task:didReceiveInformationalResponse:`
- `URLSession:task:didSendBodyData:totalBytesSent:totalBytesExpectedToSend:`
- `URLSession:task:needNewBodyStream:`
- `URLSession:task:needNewBodyStreamFromOffset:completionHandler:`
- `URLSession:task:willBeginDelayedRequest:completionHandler:`
- `URLSession:task:willPerformHTTPRedirection:newRequest:completionHandler:`
- `URLSession:taskIsWaitingForConnectivity:`

### 5.2 NSURLProtocol Registration

Custom NSURLProtocol subclass (class `YpnMQu`). Key selectors:

- `canInitWithRequest:`
- `canonicalRequestForRequest:`
- `startLoading`
- `stopLoading`
- `propertyForKey:inRequest:`
- `setProperty:forKey:inRequest:`
- `fakeProcotolClasses`

The string `NetworkListenerUrlProtocol` confirms the protocol class name.

### 5.3 Swizzled UIKit Selectors (Decoy System)

**`UIView`**:
  - `layoutSubviews`
  - `drawRect:`
  - `hitTest:withEvent:`
**`UIViewController`**:
  - `viewDidLoad`
  - `viewWillAppear:`
  - `viewDidAppear:`
  - `viewWillDisappear:`
  - `viewDidDisappear:`
**`UINavigationController`**:
  - `pushViewController:animated:`
  - `popViewControllerAnimated:`
**`UITableView`**:
  - `reloadData`
  - `cellForRowAtIndexPath:`
**`UICollectionView`**:
  - `reloadData`
  - `cellForRowAtIndexPath:`
**`UIWindow`**:
  - `makeKeyAndVisible`
  - `becomeKeyWindow`
**`UIApplication`**:
  - `sendEvent:`
  - `sendAction:to:from:forEvent:`
**`UIResponder`**:
  - `touchesBegan:withEvent:`
  - `touchesMoved:withEvent:`
  - `touchesEnded:withEvent:`

### 5.4 Data Flow: Interception to UI

```
1. NSURLSession/NSURLProtocol intercepts HTTP request
2. Id5dyJX (NSURLSessionDataDelegate) captures request/response data
3. Z6qATBJJWZ model object created with: url, method, headers, body, response, duration
4. EgsDJayPT (RequestBroadcastDelegate) broadcasts to observers
5. GajlCdZgJ (shared ViewModel) receives via newRequestArrived()
6. GajlCdZgJ analyzes the request against targetEndpointPattern
7. WKWebView instances updated via JavaScript injection:
   - Spin counter: window.increment(), window.incrementSpin()
   - Tris monitor: window.registerTris(symbol)
   - Counter reset: window.reset(), window.manualResetSymbol(id)
8. Notification 'NetShearsSpinEvent' / 'Name.NetShearsNewRequest' posted
```

## 6. String Analysis

### 6.1 JavaScript Injection Strings

```javascript
if(window.setValue) { var v = parseInt(document.getElementById('value').textContent) - 1; if(v >= 0) window.setValue(v); }
```
```javascript
if(window.manualResetSymbol) window.manualResetSymbol('
```
```javascript
if(window.registerTris) window.registerTris('
```
```javascript
if(window.incrementSpin) window.incrementSpin();
```
```javascript
if(window.increment) window.increment();
```
```javascript
if(window.showTargetSpinAlert) window.showTargetSpinAlert(
```
```javascript
if(window.reset) window.reset();
```
```javascript
if(window.showLockScreen) window.showLockScreen();
```
```javascript
window.restorePrefs(%@);
```
```javascript
window.NS_PRELOADED_STATE = %@;
```
```javascript
if(window.restoreStateFromNative) window.restoreStateFromNative(%@);
```

### 6.2 UI/Alert Strings

- `Choose an option`
- `Share (request as cURL)`
- `Share as Postman Collection`
- `Save to the desktop`
- `Request Start Time`
- `Network disabled by user`
- `Request blocked by Tris Lock`
- `No data received`
- `No data received for spin counter`
- `Tris Monitor file not found`
- `Invalid URL`
- `Decryption failed`
- `Security Violation: Unencrypted Content Rejected`
- `Invalid content`
- `Authentication failed`
- `Authentication expired`
- `Invalid challenge response`
- `Fatal error`
- `Could not create URL for specified directory!`
- `Local cache missing despite 304`

### 6.3 HTML Strings

- `<span class="title">SPEEDER</span>`
- `<span class="title">SPEEDER%@</span>`
- `>SPEEDER<`
- `>SPEEDER%@<`
- `</title>`
- ` LOC</title>`

### 6.4 NSUserDefaults Keys

| Key | Purpose |
|-----|---------|
| `com.speeder.persistence` | Main persistence suite name |
| `com.g3r7.speeder` | Developer bundle/group identifier |
| `persistentUUID` | Device unique ID persisted across sessions |
| `Speeder_LastSpeed` | Last speed multiplier value |
| `Speeder_Preset1` | Saved preset slot 1 |
| `Speeder_Preset2` | Saved preset slot 2 |
| `Speeder_TrisLock` | Tris lock target configuration |
| `Speeder_SpinCounter` | Spin counter state |
| `Speeder_Network` | Network monitoring toggle state |
| `Speeder_AutoresetMode` | Auto-reset mode configuration |
| `Speeder_CounterPositions` | Saved counter WebView positions on screen |
| `Speeder_CounterVis_%@` | Counter visibility per-counter (format string) |
| `Speeder_TrisMonitor` | Tris monitor state |

### 6.5 URL / Endpoint Patterns

| String | Purpose |
|--------|---------|
| `https://jsoneditoronline.org/#left=json.` | JSON validator URL |
| `/heartbeat` | Server heartbeat endpoint |
| `/index.html` | Main frontend entry point |
| `%@/counter/%@` | Counter WebView URL pattern |
| `/../tris_monitor.html` | Tris monitor HTML resource |
| `spin_counter.html` | Spin counter HTML resource |
| `tris_monitor.html` | Tris monitor HTML resource |
| `frontend_cache.dat` | Cached frontend binary data |
| `frontend_meta.plist` | Frontend metadata (hash, tier) |

### 6.6 Notification Names

| Name | Purpose |
|------|---------|
| `NetShearsSpinEvent` | Posted when a spin event is detected |
| `Name.NetShearsNewRequest` | Posted for each new HTTP request |

## 7. Security / Anti-Tamper System

### 7.1 Jailbreak Detection Paths

- `/Applications/Cydia.app`
- `/Applications/Installer.app`
- `/Applications/Sileo.app`
- `/Applications/Zebra.app`
- `/Library/MobileSubstrate/DynamicLibraries`
- `/Library/MobileSubstrate/MobileSubstrate.dylib`
- `/System/Library/LaunchDaemons/com.saurik.Cydia.Startup.plist`
- `/bin/bash`
- `/bin/sh`
- `/etc/apt`
- `/private/var/lib/apt/`
- `/private/var/lib/cydia`
- `/private/var/stash`
- `/private/var/tmp/cydia.log`
- `/usr/arm-apple-darwin9`
- `/usr/bin/cycript`
- `/usr/bin/frida-server`
- `/usr/include`
- `/usr/lib/frida`
- `/usr/lib/libcycript.dylib`
- `/usr/libexec`
- `/usr/libexec/cydia`
- `/usr/local/bin/cycript`
- `/usr/local/bin/frida-server`
- `/usr/sbin/frida-server`
- `/usr/sbin/sshd`
- `/usr/share`
- `/var/cache/apt`
- `/var/lib/cydia`
- `/var/log/syslog`
- `/var/run/frida`

### 7.2 Debug/Hooking Tool Detection

- `FridaGadget`
- `debugserver`
- `lldb`
- `gdb`
- `frida`
- `cycript`
- `iproxy`
- `usbmuxd`
- `remotedebugger`
- `frida-agent`
- `libfrida`
- `127.0.0.1`

### 7.3 Tweak/Bypass Detection

- `SSLKillSwitch`
- `SSLKillSwitch2`
- `Liberty`
- `Shadow`
- `HideJB`
- `FlyJB`
- `KernBypass`
- `SSL-Killswitch`
- `TrustMe`
- `SSLBypass`
- `vnodebypass`
- `A-Bypass`
- `Hestia`

### 7.4 Runtime Checks (low-level)

- `sysctl`
- `sysctlbyname`
- `task_get_exception_ports`
- `task_set_exception_ports`
- `task_set_state`
- `task_threads`
- `thread_info`
- `thread_set_state`
- `getpid`
- `getppid`
- `getrusage`
- `hw.optional.breakpoint`

## 8. Decoy / Anti-Analysis System

The binary contains an extensive **decoy system** designed to confuse static and dynamic analysis.

### 8.1 Decoy Class Names (registered at runtime)

- `LicenseValidator_v4`
- `DRMValidator`
- `SignatureVerifier`
- `CertificatePinner`
- `IntegrityChecker_v2`
- `AntiTamperModule`
- `SecurePayload`
- `EncryptedConfig`
- `RemoteAttestation`
- `JailbreakDetector_v3`
- `DebuggerBlocker`
- `HookDetector`
- `RuntimeProtection`
- `CodeSignValidator`
- `BinaryScanner`
- `MemoryGuard`
- `StackProtector`
- `HeapValidator`
- `PointerAuth`
- `ControlFlowGuard`
- `SandboxVerifier`
- `EntitlementChecker`
- `ProvisioningValidator`
- `TeamIDVerifier`
- `AppIDChecker`
- `BundleValidator`
- `ResourceScanner`
- `AssetProtector`
- `KeychainGuard`
- `SecureEnclave`

### 8.2 Decoy Method Names

- `validateLicense()`
- `checkSignature()`
- `verifyIntegrity()`
- `decryptPayload()`
- `authenticateUser()`
- `refreshToken()`
- `scanForJailbreak()`
- `detectDebugger()`
- `blockHooks()`
- `protectRuntime()`
- `validateCodeSign()`
- `scanBinary()`
- `guardMemory()`
- `protectStack()`
- `validateHeap()`
- `authPointers()`
- `guardControlFlow()`
- `verifySandbox()`
- `checkEntitlements()`
- `validateProvisioning()`
- `verifyTeamID()`
- `checkAppID()`
- `validateBundle()`
- `scanResources()`
- `protectAssets()`
- `guardKeychain()`
- `accessSecureEnclave()`
- `rotateKeys()`
- `refreshCertificate()`
- `updateCRL()`
- `checkOCSP()`
- `validateChain()`
- `pinCertificate()`
- `verifyHost()`
- `checkTrust()`
- `validateSSL()`
- `decryptConfig()`
- `loadSecureData()`
- `parseEncrypted()`
- `verifyMAC()`
- `checkHMAC()`
- `validateSHA()`
- `computeHash()`
- `signData()`
- `verifySignedData()`
- `encryptPayload()`
- `wrapKey()`
- `unwrapKey()`
- `deriveKey()`
- `generateIV()`

### 8.3 Decoy NSUserDefaults Keys

- `com.app.antitamper.clear`
- `com.app.attestation.passed`
- `com.app.binary.scanned`
- `com.app.certificate.pinned`
- `com.app.code.signed`
- `com.app.debug.blocked`
- `com.app.drm.check.complete`
- `com.app.entitlement.checked`
- `com.app.hook.detected`
- `com.app.integrity.passed`
- `com.app.jailbreak.scan.done`
- `com.app.license.validated`
- `com.app.memory.protected`
- `com.app.payload.decrypted`
- `com.app.runtime.protected`
- `com.app.sandbox.verified`
- `com.app.session.validated`
- `com.app.signature.verified`
- `com.app.stack.verified`
- `com.app.token.refreshed`

### 8.4 Decoy Infrastructure Methods

- `setupAllDecoys`
- `setupDecoyBlocks`
- `setupDecoyObservers`
- `setupDecoySwizzling`
- `setupDecoyTimers`
- `setupDecoyWindows`
- `registerDecoyClasses`
- `handleDecoyNotification:`
- `scheduleDecoyTimer:`

### 8.5 Fake Security Alert Methods

- `blockPiratedContent`
- `disableFeatures`
- `forceExit`
- `hideAllOverlays`
- `hideOverlay`
- `hideSecurityOverlay`
- `showCertificateError`
- `showDRMWarning`
- `showDebuggerWarning`
- `showHookWarning`
- `showIntegrityViolation`
- `showJailbreakDetected`
- `showLicensePrompt`
- `showOverlay`
- `showOverlay:`
- `showPaymentRequired`
- `showSecurityAlert:`
- `showSecurityOverlay`
- `showSubscriptionExpired`
- `triggerKillSwitch`

### 8.6 Decoy Exported C Functions

- `__DRM_check_signature`
- `__analytics_send_event`
- `__anti_debug_check`
- `__api_key_rotate`
- `__blockUserInterface`
- `__certificate_pin_check`
- `__checkSubscriptionStatus`
- `__crashlytics_log`
- `__dismissLicenseScreen`
- `__establishSecureChannel`
- `__hideSecurityOverlay`
- `__initSecureConnection`
- `__jailbreak_detection_v3`
- `__license_verify_v2`
- `__presentLicenseScreen`
- `__processInAppPurchase`
- `__receiveEncryptedResponse`
- `__refreshSecurityContext`
- `__remote_attestation_init`
- `__revokeSecurityContext`
- `__sendEncryptedPayload`
- `__showDRMWarning`
- `__showPaymentRequired`
- `__showSecurityOverlay`
- `__ssl_pinning_verify`
- `__unblockUserInterface`
- `__validateReceipt`
- `__validateServerResponse`
- `__validate_receipt`
- `__verifyPurchase`
- `__verifyServerCertificate`

### 8.7 Decoy Properties

| Property | Type | Purpose |
|----------|------|---------|
| `decoyRequests` | `NSMutableArray` | Fake network request objects |
| `decoyProperties` | `NSMutableArray` | Fake property list |
| `decoyWindows` | `NSMutableArray` | Fake UIWindow instances |
| `decoySession` | `NSURLSession` | Fake URL session |
| `decoyIdentifier` | `NSString` | Fake identifier string |
| `encryptedPayload` | `NSData` | Fake encrypted data |
| `overlayWindow` | `UIWindow` | Security overlay window |
| `protectionTimer` | `NSTimer` | Timer for security checks |
| `heartbeatTimer` | `NSTimer` | Timer for heartbeat pings |
| `pendingCallbacks` | `NSMutableDictionary` | Queued callback blocks |
| `isSecurityOverlay` | `Bool` | Whether security overlay is shown |
| `isAuthValid` | `Bool` | Whether auth token is valid |
| `hasReceivedTrisMonitorState` | `Bool` | Whether tris state was received |
| `pendingTrisMonitorState` | `Bool` | Pending tris state flag |
| `lastAuthTimestamp` | `Double` | Timestamp of last auth |

## 9. Cryptography and Encryption

### Imported Crypto Functions

| Symbol | Purpose |
|--------|---------|
| `CCCrypt` | CommonCrypto symmetric encryption (AES) |
| `CC_SHA256` / `CC_SHA256_Init/Update/Final` | SHA-256 hashing |
| `SecItemAdd` / `SecItemCopyMatching` / `SecItemDelete` | Keychain access |

### CryptoKit Usage (from Swift symbols)

- `AES.GCM.open()` -- AES-GCM decryption
- `AES.GCM.seal()` -- AES-GCM encryption
- `SHA256` -- SHA-256 hashing
- `SymmetricKey` -- Key management
- `AES.GCM.Nonce` -- Nonce generation
- `AES.GCM.SealedBox.combined` -- Combined ciphertext format

### Key Derivation / Hashing Methods

| Method | Details |
|--------|---------|
| `deriveKey:salt:iterations:` | PBKDF-style key derivation |
| `computeHMAC:withKey:` | HMAC computation |
| `calculateHash:` | Hash calculation |
| `calculateHashWithNonce:` | Hash with nonce for challenge-response |
| `sha256:` | Direct SHA-256 |
| `SPEEDER_LEVEL_SECURE_SALT_v2_LOCAL_ONLY` | Hardcoded salt constant |

### Embedded Encrypted Hex Payload

```
2343453635021768305523525c27685f5d33335938435c2728165b282e1921445e28695b572b2f532843582928174e756d0765071e2529545422204222585f682c4b5729
```
Decoded via `resolveBunkerString:length:` method.

## 10. Server Communication

### Heartbeat System (class `Z2hXqVH7Y`)

| Feature | Details |
|---------|---------|
| Endpoint | `/heartbeat` (POST) |
| Content-Type | `application/octet-stream` |
| PoW Headers | `X-PoW-Challenge`, `X-PoW-Nonce`, `X-PoW-Difficulty` |
| Response | JSON with `token`, `wait`, `nonce` fields |
| Challenge | `solvePoW:difficulty:` -- Proof-of-Work solver |
| Auth | `performChallengeResponseWithCompletion:` |

### Content Delivery

| Feature | Details |
|---------|---------|
| Cache headers | `X-Cache-Version`, `X-Cache-Tier` |
| Encryption header | `x-encrypted` |
| Tier header | `X-Tier` |
| Cache files | `frontend_cache.dat`, `frontend_meta.plist` |
| Content validation | Checks for `<!doctype` / `<html` prefixes |
| Decryption | `decryptPayload:withKey:` for encrypted responses |

## 11. WebView JavaScript Bridge

Script message handler name: `nativeBridge`

### JavaScript to Native Messages

| Message | Purpose |
|---------|---------|
| `toggleCounterVisibility` | Show/hide a specific counter |
| `toggleNetwork` | Enable/disable network monitoring |
| `toggleTrisMonitor` | Enable/disable tris monitor |
| `setTrisLockTarget` | Set the tris lock target symbol |
| `unlockNetwork` | Resume network after lock |
| `manualReset` | Manually reset a counter |
| `globalReset` | Reset all counters |
| `resizeWebView` | Resize a WebView (width, height) |
| `savePrefs` | Save preferences to NSUserDefaults |
| `loadPrefs` | Load preferences from NSUserDefaults |
| `setSpinTarget` | Set a spin target count |
| `resumeFromTargetSpin` | Resume after reaching spin target |
| `saveStatePartial` | Persist partial state to disk |

### Native to JavaScript Injection

| JS Call | Purpose |
|---------|---------|
| `window.increment()` | Increment the spin counter |
| `window.incrementSpin()` | Increment spin count |
| `window.setValue(v)` | Set counter to specific value |
| `window.reset()` | Reset counter to zero |
| `window.registerTris('symbol')` | Register a tris symbol |
| `window.manualResetSymbol('id')` | Reset a specific symbol counter |
| `window.showTargetSpinAlert(n)` | Show alert when spin target reached |
| `window.showLockScreen()` | Show the tris lock screen |
| `window.restorePrefs(json)` | Restore preferences from JSON |
| `window.restoreStateFromNative(json)` | Restore full state from native |
| `window.NS_PRELOADED_STATE = json` | Preload state before page load |

### Tris Monitor Symbols

- `combined`
- `hammer`
- `pig`
- `pills`
- `symbol`
- `potion`
- `x`
- `y`

## 12. Counter / WebView System

- `mainWebView` -- Primary WebView for the main UI/frontend
- `trisWebView` -- Dedicated WebView for tris (3-of-a-kind) monitoring
- `counterWebViews` -- Dictionary of `[String: WKWebView]` for individual symbol counters
- `spinWebView` -- WebView for spin display

### Counter Operations

- `createAllCounterWebViews`
- `destroyAllCounterWebViews`
- `createSingleCounterWebView:atPosition:size:`
- `createSpinWebView`
- `createTrisWebView`
- `loadAllCounterContent`
- `loadSpinWebViewContent`
- `loadTrisContent`
- `loadContent`
- `showAllCounters:`
- `toggleCounterVisibility:visible:`
- `saveCounterPositions`
- `restoreCounterPositions`
- `handleCounterPan:`
- `handlePan:`
- `destroySpinWebView`
- `showSpinWebView:`
- `setCounterWebView:forId:`
- `fetchSingleCounterWithId:completion:`
- `fetchSpinCounterWithCompletion:`
- `fetchSpinCounterWithStaticHashCompletion:`
- `fetchTrisMonitorWithCompletion:`
- `fetchFrontendWithCompletion:`

## 13. Tris Lock / Spin Target System

### Tris Lock

- Enabled via `D4083JN5T.shared.trisLockEnabled`
- Target set via `GajlCdZgJ.setTrisLockTarget(target:)`
- When active and target matched: `window.showLockScreen()` injected
- Network blocked: `"Request blocked by Tris Lock"` returned
- Skip tris available: `D4083JN5T.shared.skipTrisEnabled`

### Spin Target

- `GajlCdZgJ.spinTarget` -- The target spin count
- `GajlCdZgJ.currentSessionSpinCount` -- Current session count
- `GajlCdZgJ.targetLockTriggered` -- Whether target was reached
- `GajlCdZgJ.targetSpinResetMode` -- How to reset after target
- `GajlCdZgJ.resumeFromTargetSpin()` -- Resume after target reached

### Auto-Reset

- `GajlCdZgJ.autoresetEnabled`
- `GajlCdZgJ.autoresetMode`
- `GajlCdZgJ.autoresetConfig`
- `configureAutoresetWithEnabled:mode:endpoint:config:`

## 14. Initialization and Entry Points

The `__init_offsets` section (12 bytes = 3 function pointers) means 3 constructors run at load.

### Startup Sequence (inferred)

```
1. dylib loaded into process
2. Ji7SfZ.initializeAtStartup() called
3. KEDCui.shared initialized (NetShears singleton)
4. D4083JN5T.shared initialized (Settings singleton)
5. GajlCdZgJ.shared initialized (ViewModel singleton)
6. NSURLProtocol subclass registered (YpnMQu)
7. NSURLSession delegate methods swizzled (IS6Edgkv)
8. Decoy classes registered (registerDecoyClasses)
9. Decoy observers/timers/windows set up
10. Heartbeat started (Z2hXqVH7Y)
11. Frontend loaded from cache or fetched from server
12. WKWebViews created for UI
```

## 15. ObjC Protocol Conformances

### Standard

- `UICollectionViewDataSource`
- `UICollectionViewDelegate`
- `UICollectionViewDelegateFlowLayout`
- `UISearchResultsUpdating`
- `UITableViewDataSource`
- `UITableViewDelegate`
- `UISearchBarDelegate`
- `NSURLSessionDataDelegate`
- `NSURLSessionTaskDelegate`
- `NSURLSessionDelegate`
- `NSObject`
- `UIScrollViewDelegate`
- `UIBarPositioningDelegate`
- `WKScriptMessageHandler`
- `WKNavigationDelegate`

### Obfuscated Internal

- `BkI0Ewl`
- `Zq6ez12`
- `OJSzs662`
- `KcvXzcslZU`
- `PnFE0rC`
- `LVaMCop`
- `W3E1s78tG`
- `QFjexCs`
- `L2lJWS`
- `LdLG1Vfm1`
- `BEc8AU4RLg`
- `FKtTSPMQ`
- `OayFFFD`
- `ErsPlVq2`
- `SnR6F8DzWQ`
- `TN5WWG`
- `Le9EvzM`
- `O8xJs4`
- `FrwHR7Sd`
- `UA5urdBzpq`
- `L6NLLUEw`
- `KnMvFu`
- `GnnFwt2sDc`

## 16. Low-Level System Imports

### Dynamic Loader

- `_dyld_get_image_header`
- `_dyld_get_image_name`
- `_dyld_get_image_vmaddr_slide`
- `_dyld_image_count`
- `_dyld_register_func_for_add_image`
- `dladdr`
- `dlopen`
- `dlsym`
- `getsectiondata`

### ObjC Runtime

- `class_addMethod`
- `class_getInstanceMethod`
- `class_getName`
- `class_getSuperclass`
- `method_exchangeImplementations`
- `method_getImplementation`
- `method_setImplementation`
- `objc_allocateClassPair`
- `objc_registerClassPair`
- `objc_copyClassList`
- `objc_getClassList`
- `object_getClass`
- `sel_registerName`

### Network (low-level)

- `socket`
- `connect`
- `setsockopt`
- `inet_addr`
- `inet_pton`

### Filesystem

- `opendir`
- `readdir`
- `closedir`
- `stat`
- `lstat`

### Memory / VM

- `vm_protect`
- `vm_deallocate`
- `malloc`
- `free`
- `malloc_size`
- `memcpy`
- `memmove`
- `memmem`
- `bzero`

## 17. All Module-Exported Symbols (Raw)

<details>
<summary>Click to expand all 449 module symbols</summary>

```
_$s19Nuovo_Speeder_Level10Svtj2s5frMMp
_$s19Nuovo_Speeder_Level10Svtj2s5frMTL
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC10isFinishedSbvM
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC10isFinishedSbvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC10isFinishedSbvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC10isFinishedSbvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC10isFinishedSbvs
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC11credentialsSDyS2SGvM
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC11credentialsSDyS2SGvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC11credentialsSDyS2SGvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC11credentialsSDyS2SGvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC11credentialsSDyS2SGvs
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC12dataResponse10Foundation4DataVSgvM
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC12dataResponse10Foundation4DataVSgvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC12dataResponse10Foundation4DataVSgvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC12dataResponse10Foundation4DataVSgvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC12dataResponse10Foundation4DataVSgvpfi
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC12dataResponse10Foundation4DataVSgvs
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC15responseHeadersSDyS2SGSgvM
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC15responseHeadersSDyS2SGSgvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC15responseHeadersSDyS2SGSgvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC15responseHeadersSDyS2SGSgvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC15responseHeadersSDyS2SGSgvpfi
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC15responseHeadersSDyS2SGSgvs
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC22errorClientDescriptionSSSgvM
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC22errorClientDescriptionSSSgvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC22errorClientDescriptionSSSgvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC22errorClientDescriptionSSSgvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC22errorClientDescriptionSSSgvpfi
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC22errorClientDescriptionSSSgvs
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC2idSSvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC2idSSvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC2idSSvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC3urlSSvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC3urlSSvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC3urlSSvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4codeSivM
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4codeSivg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4codeSivpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4codeSivpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4codeSivs
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4date10Foundation4DateVvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4date10Foundation4DateVvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4date10Foundation4DateVvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4fromACs7Decoder_p_tKcfC
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4fromACs7Decoder_p_tKcfCTq
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4fromACs7Decoder_p_tKcfc
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4hostSSSgvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4hostSSSgvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4hostSSSgvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4portSiSgvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4portSiSgvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC4portSiSgvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC6encode2toys7Encoder_p_tKF
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC6methodSSvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC6methodSSvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC6methodSSvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC6schemeSSSgvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC6schemeSSSgvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC6schemeSSSgvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC7cookiesSSSgvM
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC7cookiesSSSgvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC7cookiesSSSgvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC7cookiesSSSgvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC7cookiesSSSgvpfi
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC7cookiesSSSgvs
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC7headersSDyS2SGvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC7headersSDyS2SGvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC7headersSDyS2SGvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8durationSdSgvM
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8durationSdSgvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8durationSdSgvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8durationSdSgvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8durationSdSgvpfi
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8durationSdSgvs
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8httpBody10Foundation4DataVSgvM
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8httpBody10Foundation4DataVSgvg
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8httpBody10Foundation4DataVSgvpMV
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8httpBody10Foundation4DataVSgvpWvd
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8httpBody10Foundation4DataVSgvpfi
_$s19Nuovo_Speeder_Level10Z6qATBJJWZC8httpBody10Foundation4DataVSgvs
_$s19Nuovo_Speeder_Level10Z6qATBJJWZCMa
_$s19Nuovo_Speeder_Level10Z6qATBJJWZCMm
_$s19Nuovo_Speeder_Level10Z6qATBJJWZCMn
_$s19Nuovo_Speeder_Level10Z6qATBJJWZCN
_$s19Nuovo_Speeder_Level10Z6qATBJJWZCSEAAMc
_$s19Nuovo_Speeder_Level10Z6qATBJJWZCSeAAMc
_$s19Nuovo_Speeder_Level10Z6qATBJJWZCfD
_$s19Nuovo_Speeder_Level10Z6qATBJJWZCfd
_$s19Nuovo_Speeder_Level14BodyExportTypeOMa
_$s19Nuovo_Speeder_Level14BodyExportTypeOMn
_$s19Nuovo_Speeder_Level14BodyExportTypeON
_$s19Nuovo_Speeder_Level15RequestModifierMp
_$s19Nuovo_Speeder_Level15RequestModifierPAA0E0Tb
_$s19Nuovo_Speeder_Level15RequestModifierTL
_$s19Nuovo_Speeder_Level17HeaderModifyModelV23__derived_struct_equalsySbAC_ACtFZ
_$s19Nuovo_Speeder_Level17HeaderModifyModelV3key5valueACSS_SStcfC
_$s19Nuovo_Speeder_Level17HeaderModifyModelV3keySSvg
_$s19Nuovo_Speeder_Level17HeaderModifyModelV3keySSvpMV
_$s19Nuovo_Speeder_Level17HeaderModifyModelV4fromACs7Decoder_p_tKcfC
_$s19Nuovo_Speeder_Level17HeaderModifyModelV5valueSSvg
_$s19Nuovo_Speeder_Level17HeaderModifyModelV5valueSSvpMV
_$s19Nuovo_Speeder_Level17HeaderModifyModelV6encode2toys7Encoder_p_tKF
_$s19Nuovo_Speeder_Level17HeaderModifyModelVMa
_$s19Nuovo_Speeder_Level17HeaderModifyModelVMn
_$s19Nuovo_Speeder_Level17HeaderModifyModelVN
_$s19Nuovo_Speeder_Level17HeaderModifyModelVSEAAMc
_$s19Nuovo_Speeder_Level17HeaderModifyModelVSQAAMc
_$s19Nuovo_Speeder_Level17HeaderModifyModelVSeAAMc
_$s19Nuovo_Speeder_Level17NetshearsFlowViewV20makeUIViewController7contextQr7SwiftUI0hI20RepresentableContextVyACG_tF
_$s19Nuovo_Speeder_Level17NetshearsFlowViewV20makeUIViewController7contextQr7SwiftUI0hI20RepresentableContextVyACG_tFQOMQ
_$s19Nuovo_Speeder_Level17NetshearsFlowViewV22updateUIViewController_7contextyAC04makehI0AEQr7SwiftUI0hI20RepresentableContextVyACG_tFQOy_Qo__AJtF
_$s19Nuovo_Speeder_Level17NetshearsFlowViewV7SwiftUI0F0AAMc
_$s19Nuovo_Speeder_Level17NetshearsFlowViewV7SwiftUI29UIViewControllerRepresentableAAMc
_$s19Nuovo_Speeder_Level17NetshearsFlowViewVMa
_$s19Nuovo_Speeder_Level17NetshearsFlowViewVMn
_$s19Nuovo_Speeder_Level17NetshearsFlowViewVN
_$s19Nuovo_Speeder_Level18PersistenceManagerC11masterState33_3722F3E09EB4B6ED8F5C68392D8621E7LLSDySSypGvpfi
_$s19Nuovo_Speeder_Level18PersistenceManagerC11updateState6module4dataySS_SDySSypGtF
_$s19Nuovo_Speeder_Level18PersistenceManagerC11updateState6module4dataySS_SDySSypGtFTq
_$s19Nuovo_Speeder_Level18PersistenceManagerC12getJSONStateSSyF
_$s19Nuovo_Speeder_Level18PersistenceManagerC12getJSONStateSSyFTq
_$s19Nuovo_Speeder_Level18PersistenceManagerC5queue33_3722F3E09EB4B6ED8F5C68392D8621E7LLSo012OS_dispatch_F0Cvpfi
_$s19Nuovo_Speeder_Level18PersistenceManagerC6sharedACvau
_$s19Nuovo_Speeder_Level18PersistenceManagerC6sharedACvgZ
_$s19Nuovo_Speeder_Level18PersistenceManagerC6sharedACvpZ
_$s19Nuovo_Speeder_Level18PersistenceManagerC6sharedACvpZMV
_$s19Nuovo_Speeder_Level18PersistenceManagerC8fileName33_3722F3E09EB4B6ED8F5C68392D8621E7LLSSvpfi
_$s19Nuovo_Speeder_Level18PersistenceManagerCMa
_$s19Nuovo_Speeder_Level18PersistenceManagerCMn
_$s19Nuovo_Speeder_Level18PersistenceManagerCN
_$s19Nuovo_Speeder_Level18PersistenceManagerCfD
_$s19Nuovo_Speeder_Level20BodyExporterDelegateMp
_$s19Nuovo_Speeder_Level20BodyExporterDelegatePAAE9netShears013exportRequestD3ForAA0D10ExportTypeOAA10Z6qATBJJWZC_tF
_$s19Nuovo_Speeder_Level20BodyExporterDelegatePAAE9netShears014exportResponseD3ForAA0D10ExportTypeOAA10Z6qATBJJWZC_tF
_$s19Nuovo_Speeder_Level20BodyExporterDelegateTL
_$s19Nuovo_Speeder_Level20TaskProgressDelegateMp
_$s19Nuovo_Speeder_Level20TaskProgressDelegateTL
_$s19Nuovo_Speeder_Level21RequestActionModifierMp
_$s19Nuovo_Speeder_Level21RequestActionModifierPAA0F0Tb
_$s19Nuovo_Speeder_Level21RequestActionModifierTL
_$s19Nuovo_Speeder_Level22RedirectedRequestModelV11originalUrl08redirectH0ACSS_SStcfC
_$s19Nuovo_Speeder_Level22RedirectedRequestModelV11originalUrlSSvg
_$s19Nuovo_Speeder_Level22RedirectedRequestModelV11originalUrlSSvpMV
_$s19Nuovo_Speeder_Level22RedirectedRequestModelV11redirectUrlSSvg
_$s19Nuovo_Speeder_Level22RedirectedRequestModelV11redirectUrlSSvpMV
_$s19Nuovo_Speeder_Level22RedirectedRequestModelV23__derived_struct_equalsySbAC_ACtFZ
_$s19Nuovo_Speeder_Level22RedirectedRequestModelV4fromACs7Decoder_p_tKcfC
_$s19Nuovo_Speeder_Level22RedirectedRequestModelV6encode2toys7Encoder_p_tKF
_$s19Nuovo_Speeder_Level22RedirectedRequestModelVMa
_$s19Nuovo_Speeder_Level22RedirectedRequestModelVMn
_$s19Nuovo_Speeder_Level22RedirectedRequestModelVN
_$s19Nuovo_Speeder_Level22RedirectedRequestModelVSEAAMc
_$s19Nuovo_Speeder_Level22RedirectedRequestModelVSQAAMc
_$s19Nuovo_Speeder_Level22RedirectedRequestModelVSeAAMc
_$s19Nuovo_Speeder_Level22RequestModifierStorageMp
_$s19Nuovo_Speeder_Level22RequestModifierStorageTL
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV10httpMethodSSvg
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV10httpMethodSSvpMV
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV10statusCodeSivg
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV10statusCodeSivpMV
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV11httpVersionSSSgvg
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV11httpVersionSSSgvpMV
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV23__derived_struct_equalsySbAC_ACtFZ
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV3url4data10httpMethod10statusCode0I7Version7headersACSS_10Foundation4DataVSSSiSSSgSDyS2SGtcfC
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV3urlSSvg
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV3urlSSvpMV
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV4data10Foundation4DataVvg
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV4data10Foundation4DataVvpMV
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV4fromACs7Decoder_p_tKcfC
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV6encode2toys7Encoder_p_tKF
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV7headersSDyS2SGvg
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV7headersSDyS2SGvpMV
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV8responseSo13NSURLResponseCSgvg
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelV8responseSo13NSURLResponseCSgvpMV
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelVMa
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelVMn
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelVN
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelVSEAAMc
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelVSQAAMc
_$s19Nuovo_Speeder_Level23HTTPResponseModifyModelVSeAAMc
_$s19Nuovo_Speeder_Level24RequestBroadcastDelegateMp
_$s19Nuovo_Speeder_Level24RequestBroadcastDelegateTL
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV13storeFileNameSSvgZ
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV13storeFileNameSSvpZMV
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV15isActionAllowed03urlD0Sb10Foundation10URLRequestV_tF
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV23__derived_struct_equalsySbAC_ACtFZ
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV4fromACs7Decoder_p_tKcfC
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV6encode2toys7Encoder_p_tKF
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV6headerAA0G11ModifyModelVvM
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV6headerAA0G11ModifyModelVvg
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV6headerAA0G11ModifyModelVvpMV
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV6headerAA0G11ModifyModelVvs
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV6headerAcA0G11ModifyModelV_tcfC
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderV6modify7requesty10Foundation10URLRequestVz_tF
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVAA0F0AAMc
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVAA0F0AAWP
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVAA0dF0AAMc
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVAA0dF0AAWP
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVAA0dF7StorageAAMc
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVAA0dF7StorageAAWP
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVAA10Svtj2s5frMAAMc
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVAA10Svtj2s5frMAAWP
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVMa
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVMn
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVN
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVSEAAMc
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVSQAAMc
_$s19Nuovo_Speeder_Level30RequestEvaluatorModifierHeaderVSeAAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV010redirectedD0AA010RedirectedD5ModelVvM
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV010redirectedD0AA010RedirectedD5ModelVvg
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV010redirectedD0AA010RedirectedD5ModelVvpMV
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV010redirectedD0AA010RedirectedD5ModelVvs
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV010redirectedD0AcA010RedirectedD5ModelV_tcfC
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV13storeFileNameSSvgZ
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV13storeFileNameSSvpZMV
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV15isActionAllowed03urlD0Sb10Foundation10URLRequestV_tF
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV23__derived_struct_equalsySbAC_ACtFZ
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV4fromACs7Decoder_p_tKcfC
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV6encode2toys7Encoder_p_tKF
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointV6modify7requesty10Foundation10URLRequestVz_tF
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVAA0F0AAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVAA0F0AAWP
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVAA0dF0AAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVAA0dF0AAWP
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVAA0dF7StorageAAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVAA0dF7StorageAAWP
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVAA10Svtj2s5frMAAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVAA10Svtj2s5frMAAWP
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVMa
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVMn
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVN
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVSEAAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVSQAAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierEndpointVSeAAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV13storeFileNameSSvgZ
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV13storeFileNameSSvpZMV
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV15isActionAllowed03urlD0Sb10Foundation10URLRequestV_tF
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV23__derived_struct_equalsySbAC_ACtFZ
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV4fromACs7Decoder_p_tKcfC
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV6encode2toys7Encoder_p_tKF
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV6modify6client11urlProtocolySo19NSURLProtocolClient_pSg_So0L0CtF
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV8responseAA23HTTPResponseModifyModelVvM
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV8responseAA23HTTPResponseModifyModelVvg
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV8responseAA23HTTPResponseModifyModelVvpMV
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV8responseAA23HTTPResponseModifyModelVvs
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseV8responseAcA23HTTPResponseModifyModelV_tcfC
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVAA0F0AAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVAA0F0AAWP
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVAA0d6ActionF0AAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVAA0d6ActionF0AAWP
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVAA0dF7StorageAAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVAA0dF7StorageAAWP
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVAA10Svtj2s5frMAAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVAA10Svtj2s5frMAAWP
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVMa
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVMn
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVN
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVSEAAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVSQAAMc
_$s19Nuovo_Speeder_Level32RequestEvaluatorModifierResponseVSeAAMc
_$s19Nuovo_Speeder_Level6IgnoreOMa
_$s19Nuovo_Speeder_Level6IgnoreOMn
_$s19Nuovo_Speeder_Level6IgnoreON
_$s19Nuovo_Speeder_Level6Ji7SfZC19initializeAtStartupyyFZ
_$s19Nuovo_Speeder_Level6Ji7SfZCACycfC
_$s19Nuovo_Speeder_Level6Ji7SfZCACycfc
_$s19Nuovo_Speeder_Level6Ji7SfZCMa
_$s19Nuovo_Speeder_Level6Ji7SfZCMn
_$s19Nuovo_Speeder_Level6Ji7SfZCN
_$s19Nuovo_Speeder_Level6Ji7SfZCfD
_$s19Nuovo_Speeder_Level6KEDCuiC10stopLoggeryyF
_$s19Nuovo_Speeder_Level6KEDCuiC11startLoggeryyF
_$s19Nuovo_Speeder_Level6KEDCuiC12loggerEnableSbvpfi
_$s19Nuovo_Speeder_Level6KEDCuiC12modifiedListSayAA8Modifier_pGyF
_$s19Nuovo_Speeder_Level6KEDCuiC12stopListeneryyF
_$s19Nuovo_Speeder_Level6KEDCuiC13startListeneryyF
_$s19Nuovo_Speeder_Level6KEDCuiC14listenerEnableSbvpfi
_$s19Nuovo_Speeder_Level6KEDCuiC14removeModifier2atySi_tF
_$s19Nuovo_Speeder_Level6KEDCuiC15stopInterceptoryyF
_$s19Nuovo_Speeder_Level6KEDCuiC17interceptorEnableSbvpfi
_$s19Nuovo_Speeder_Level6KEDCuiC18bodyExportDelegateAA012BodyExporterG0_pSgvM
_$s19Nuovo_Speeder_Level6KEDCuiC18bodyExportDelegateAA012BodyExporterG0_pSgvg
_$s19Nuovo_Speeder_Level6KEDCuiC18bodyExportDelegateAA012BodyExporterG0_pSgvpMV
_$s19Nuovo_Speeder_Level6KEDCuiC18bodyExportDelegateAA012BodyExporterG0_pSgvpWvd
_$s19Nuovo_Speeder_Level6KEDCuiC18bodyExportDelegateAA012BodyExporterG0_pSgvpfi
_$s19Nuovo_Speeder_Level6KEDCuiC18bodyExportDelegateAA012BodyExporterG0_pSgvs
_$s19Nuovo_Speeder_Level6KEDCuiC20taskProgressDelegateAA04TaskfG0_pSgvM
_$s19Nuovo_Speeder_Level6KEDCuiC20taskProgressDelegateAA04TaskfG0_pSgvg
_$s19Nuovo_Speeder_Level6KEDCuiC20taskProgressDelegateAA04TaskfG0_pSgvpMV
_$s19Nuovo_Speeder_Level6KEDCuiC20taskProgressDelegateAA04TaskfG0_pSgvpWvd
_$s19Nuovo_Speeder_Level6KEDCuiC20taskProgressDelegateAA04TaskfG0_pSgvpfi
_$s19Nuovo_Speeder_Level6KEDCuiC20taskProgressDelegateAA04TaskfG0_pSgvs
_$s19Nuovo_Speeder_Level6KEDCuiC21presentNetworkMonitoryyF
_$s19Nuovo_Speeder_Level6KEDCuiC22startGestureRecognizeryyF
_$s19Nuovo_Speeder_Level6KEDCuiC24$__lazy_storage_$_config33_A71C40053F35ED483E7A6A3BD499DF46LLAA7Ry4K7EVCSgvpfi
_$s19Nuovo_Speeder_Level6KEDCuiC25networkRequestInterceptorAA7AOljeCUCvpfi
_$s19Nuovo_Speeder_Level6KEDCuiC4viewQryF
_$s19Nuovo_Speeder_Level6KEDCuiC4viewQryFQOMQ
_$s19Nuovo_Speeder_Level6KEDCuiC6K8CGHq7payloadySDySSypG_tFZ
_$s19Nuovo_Speeder_Level6KEDCuiC6WVYSnsyyF
_$s19Nuovo_Speeder_Level6KEDCuiC6ignoreAA6IgnoreOvM
_$s19Nuovo_Speeder_Level6KEDCuiC6ignoreAA6IgnoreOvg
_$s19Nuovo_Speeder_Level6KEDCuiC6ignoreAA6IgnoreOvpMV
_$s19Nuovo_Speeder_Level6KEDCuiC6ignoreAA6IgnoreOvpWvd
_$s19Nuovo_Speeder_Level6KEDCuiC6ignoreAA6IgnoreOvpfi
_$s19Nuovo_Speeder_Level6KEDCuiC6ignoreAA6IgnoreOvs
_$s19Nuovo_Speeder_Level6KEDCuiC6modify8modifieryAA8Modifier_p_tF
_$s19Nuovo_Speeder_Level6KEDCuiC6sharedACvau
_$s19Nuovo_Speeder_Level6KEDCuiC6sharedACvgZ
_$s19Nuovo_Speeder_Level6KEDCuiC6sharedACvpZ
_$s19Nuovo_Speeder_Level6KEDCuiC6sharedACvpZMV
_$s19Nuovo_Speeder_Level6KEDCuiC7HWu1bjL3url4host6method13requestObject08responseJ07success10statusCode0M7Message8duration6scheme0I7Headers0kR0ySS_S2S10Foundation4DataVSgATSbSiSSSgSdSgSSSDyS2SGSgAXtF
_$s19Nuovo_Speeder_Level6KEDCuiC7addGRPC3url4host6method13requestObject08responseK07success10statusCode0N7Message8duration19HPACKHeadersRequest0R8ResponseySS_S2S10Foundation4DataVSgASSbSiSSSgSdSgSDyS2SGSgAWtF
_$s19Nuovo_Speeder_Level6KEDCuiC8swizzledSbvpfi
_$s19Nuovo_Speeder_Level6KEDCuiCACycfC
_$s19Nuovo_Speeder_Level6KEDCuiCACycfc
_$s19Nuovo_Speeder_Level6KEDCuiCMa
_$s19Nuovo_Speeder_Level6KEDCuiCMn
_$s19Nuovo_Speeder_Level6KEDCuiCN
_$s19Nuovo_Speeder_Level6KEDCuiCfD
_$s19Nuovo_Speeder_Level8ModifierMp
_$s19Nuovo_Speeder_Level8ModifierPAA07RequestD7StorageTb
_$s19Nuovo_Speeder_Level8ModifierPAA10Svtj2s5frMTb
_$s19Nuovo_Speeder_Level8ModifierPSETb
_$s19Nuovo_Speeder_Level8ModifierPSeTb
_$s19Nuovo_Speeder_Level8ModifierTL
_$s19Nuovo_Speeder_Level8QYsl7dpnC7decrypt_6lengthSSSPys5UInt8VG_SitFZ
_$s19Nuovo_Speeder_Level8QYsl7dpnCACycfC
_$s19Nuovo_Speeder_Level8QYsl7dpnCACycfc
_$s19Nuovo_Speeder_Level8QYsl7dpnCMa
_$s19Nuovo_Speeder_Level8QYsl7dpnCMn
_$s19Nuovo_Speeder_Level8QYsl7dpnCN
_$s19Nuovo_Speeder_Level8QYsl7dpnCfD
_$s19Nuovo_Speeder_Level9D4083JN5TC14networkEnabledSbvM
_$s19Nuovo_Speeder_Level9D4083JN5TC14networkEnabledSbvMTq
_$s19Nuovo_Speeder_Level9D4083JN5TC14networkEnabledSbvg
_$s19Nuovo_Speeder_Level9D4083JN5TC14networkEnabledSbvgTq
_$s19Nuovo_Speeder_Level9D4083JN5TC14networkEnabledSbvpMV
_$s19Nuovo_Speeder_Level9D4083JN5TC14networkEnabledSbvpWvd
_$s19Nuovo_Speeder_Level9D4083JN5TC14networkEnabledSbvpfi
_$s19Nuovo_Speeder_Level9D4083JN5TC14networkEnabledSbvs
_$s19Nuovo_Speeder_Level9D4083JN5TC14networkEnabledSbvsTq
_$s19Nuovo_Speeder_Level9D4083JN5TC15skipTrisEnabledSbvM
_$s19Nuovo_Speeder_Level9D4083JN5TC15skipTrisEnabledSbvMTq
_$s19Nuovo_Speeder_Level9D4083JN5TC15skipTrisEnabledSbvg
_$s19Nuovo_Speeder_Level9D4083JN5TC15skipTrisEnabledSbvgTq
_$s19Nuovo_Speeder_Level9D4083JN5TC15skipTrisEnabledSbvpMV
_$s19Nuovo_Speeder_Level9D4083JN5TC15skipTrisEnabledSbvpWvd
_$s19Nuovo_Speeder_Level9D4083JN5TC15skipTrisEnabledSbvpfi
_$s19Nuovo_Speeder_Level9D4083JN5TC15skipTrisEnabledSbvs
_$s19Nuovo_Speeder_Level9D4083JN5TC15skipTrisEnabledSbvsTq
_$s19Nuovo_Speeder_Level9D4083JN5TC15trisLockEnabledSbvM
_$s19Nuovo_Speeder_Level9D4083JN5TC15trisLockEnabledSbvMTq
_$s19Nuovo_Speeder_Level9D4083JN5TC15trisLockEnabledSbvg
_$s19Nuovo_Speeder_Level9D4083JN5TC15trisLockEnabledSbvgTq
_$s19Nuovo_Speeder_Level9D4083JN5TC15trisLockEnabledSbvpMV
_$s19Nuovo_Speeder_Level9D4083JN5TC15trisLockEnabledSbvpWvd
_$s19Nuovo_Speeder_Level9D4083JN5TC15trisLockEnabledSbvpfi
_$s19Nuovo_Speeder_Level9D4083JN5TC15trisLockEnabledSbvs
_$s19Nuovo_Speeder_Level9D4083JN5TC15trisLockEnabledSbvsTq
_$s19Nuovo_Speeder_Level9D4083JN5TC25networkRequestInterceptorAA7AOljeCUCvpfi
_$s19Nuovo_Speeder_Level9D4083JN5TC6sharedACvau
_$s19Nuovo_Speeder_Level9D4083JN5TC6sharedACvgZ
_$s19Nuovo_Speeder_Level9D4083JN5TC6sharedACvpZ
_$s19Nuovo_Speeder_Level9D4083JN5TC6sharedACvpZMV
_$s19Nuovo_Speeder_Level9D4083JN5TCACycfC
_$s19Nuovo_Speeder_Level9D4083JN5TCACycfc
_$s19Nuovo_Speeder_Level9D4083JN5TCMa
_$s19Nuovo_Speeder_Level9D4083JN5TCMn
_$s19Nuovo_Speeder_Level9D4083JN5TCN
_$s19Nuovo_Speeder_Level9D4083JN5TCfD
_$s19Nuovo_Speeder_Level9EgsDJayPTC11setDelegateyyAA016RequestBroadcastH0_pF
_$s19Nuovo_Speeder_Level9EgsDJayPTC14removeDelegateyyF
_$s19Nuovo_Speeder_Level9EgsDJayPTC6sharedACvau
_$s19Nuovo_Speeder_Level9EgsDJayPTC6sharedACvgZ
_$s19Nuovo_Speeder_Level9EgsDJayPTC6sharedACvpZ
_$s19Nuovo_Speeder_Level9EgsDJayPTC6sharedACvpZMV
_$s19Nuovo_Speeder_Level9EgsDJayPTC8delegateAA7RSSuXwsCyAA24RequestBroadcastDelegate_pSgGvpfi
_$s19Nuovo_Speeder_Level9EgsDJayPTCMa
_$s19Nuovo_Speeder_Level9EgsDJayPTCMm
_$s19Nuovo_Speeder_Level9EgsDJayPTCMn
_$s19Nuovo_Speeder_Level9EgsDJayPTCN
_$s19Nuovo_Speeder_Level9EgsDJayPTCfD
_$s19Nuovo_Speeder_Level9EgsDJayPTCfd
_$s19Nuovo_Speeder_Level9GajlCdZgJC10spinTarget33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSivpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC10stateQueue33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSo17OS_dispatch_queueCvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC11mainWebView33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSo05WKWebI0CSgvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC11trisWebView33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSo05WKWebI0CSgvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC13autoresetMode33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSSSgvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC13setSpinTargetyyypF
_$s19Nuovo_Speeder_Level9GajlCdZgJC13setSpinTargetyyypFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC14setMainWebViewyySo05WKWebJ0CSgF
_$s19Nuovo_Speeder_Level9GajlCdZgJC14setMainWebViewyySo05WKWebJ0CSgFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC14setTrisWebViewyySo05WKWebJ0CSgF
_$s19Nuovo_Speeder_Level9GajlCdZgJC14setTrisWebViewyySo05WKWebJ0CSgFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC14stopMonitoringyyF
_$s19Nuovo_Speeder_Level9GajlCdZgJC14stopMonitoringyyFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC14trisLockTarget33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSSSgvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC15autoresetConfig33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSDySSypGSgvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC15counterWebViews33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSDySSSo9WKWebViewCGvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC15pendingRequests33_FC82F843D9AE3F418EDEFF8AE2BA7681LLShySSGvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC15startMonitoringyyF
_$s19Nuovo_Speeder_Level9GajlCdZgJC15startMonitoringyyFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC16autoresetEnabled33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSbvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC16lastAnalysisTime33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSdvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC17handleGlobalResetyyF
_$s19Nuovo_Speeder_Level9GajlCdZgJC17handleGlobalResetyyFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC17handleManualReset8symbolIdySS_tF
_$s19Nuovo_Speeder_Level9GajlCdZgJC17handleManualReset8symbolIdySS_tFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC17newRequestArrivedyyAA10Z6qATBJJWZCF
_$s19Nuovo_Speeder_Level9GajlCdZgJC17newRequestArrivedyyAA10Z6qATBJJWZCFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC17setCounterWebView_5forIdySo05WKWebJ0CSg_SStF
_$s19Nuovo_Speeder_Level9GajlCdZgJC17setCounterWebView_5forIdySo05WKWebJ0CSg_SStFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC17setTrisLockTarget6targetySSSg_tF
_$s19Nuovo_Speeder_Level9GajlCdZgJC17setTrisLockTarget6targetySSSg_tFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC18configureAutoreset7enabled4mode8endpoint6configySb_SSSgAISDySSypGSgtF
_$s19Nuovo_Speeder_Level9GajlCdZgJC18configureAutoreset7enabled4mode8endpoint6configySb_SSSgAISDySSypGSgtFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC19targetLockTriggered33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSbvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC19targetSpinResetMode33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSSvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC20resumeFromTargetSpinyyF
_$s19Nuovo_Speeder_Level9GajlCdZgJC20resumeFromTargetSpinyyFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJC21targetEndpointPattern33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSSSgvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC22$__lazy_storage_$_keys33_FC82F843D9AE3F418EDEFF8AE2BA7681LLAC7HotKeysAELLVSgvpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC23currentSessionSpinCount33_FC82F843D9AE3F418EDEFF8AE2BA7681LLSivpfi
_$s19Nuovo_Speeder_Level9GajlCdZgJC6sharedACvau
_$s19Nuovo_Speeder_Level9GajlCdZgJC6sharedACvgZ
_$s19Nuovo_Speeder_Level9GajlCdZgJC6sharedACvpZ
_$s19Nuovo_Speeder_Level9GajlCdZgJC6sharedACvpZMV
_$s19Nuovo_Speeder_Level9GajlCdZgJC9configure15endpointPatternySS_tF
_$s19Nuovo_Speeder_Level9GajlCdZgJC9configure15endpointPatternySS_tFTq
_$s19Nuovo_Speeder_Level9GajlCdZgJCAA24RequestBroadcastDelegateAAMc
_$s19Nuovo_Speeder_Level9GajlCdZgJCAA24RequestBroadcastDelegateAAWP
_$s19Nuovo_Speeder_Level9GajlCdZgJCMa
_$s19Nuovo_Speeder_Level9GajlCdZgJCMn
_$s19Nuovo_Speeder_Level9GajlCdZgJCN
_$s19Nuovo_Speeder_Level9GajlCdZgJCfD
_OBJC_CLASS_$__TtC19Nuovo_Speeder_Level18PersistenceManager
_OBJC_CLASS_$__TtC19Nuovo_Speeder_Level6Ji7SfZ
_OBJC_CLASS_$__TtC19Nuovo_Speeder_Level6KEDCui
_OBJC_CLASS_$__TtC19Nuovo_Speeder_Level8QYsl7dpn
_OBJC_CLASS_$__TtC19Nuovo_Speeder_Level9D4083JN5T
_OBJC_CLASS_$__TtC19Nuovo_Speeder_Level9GajlCdZgJ
_OBJC_METACLASS_$__TtC19Nuovo_Speeder_Level18PersistenceManager
_OBJC_METACLASS_$__TtC19Nuovo_Speeder_Level6Ji7SfZ
_OBJC_METACLASS_$__TtC19Nuovo_Speeder_Level6KEDCui
_OBJC_METACLASS_$__TtC19Nuovo_Speeder_Level8QYsl7dpn
_OBJC_METACLASS_$__TtC19Nuovo_Speeder_Level9D4083JN5T
_OBJC_METACLASS_$__TtC19Nuovo_Speeder_Level9GajlCdZgJ
```

</details>

## 18. All ObjC Method Names

<details>
<summary>Click to expand all 815 unique method names</summary>

```
.cxx_destruct
CGColor
CGRectValue
GmyYW7Kf3:nonce:
HTTPAdditionalHeaders
HTTPBody
HTTPCookieStorage
HTTPMethod
HTTPShouldSetCookies
IdBWw44
IdydqS:
Ig0iq3O:
JSONObjectWithData:options:error:
URL
URLByAppendingPathComponent:
URLCredentialStorage
URLForResource:withExtension:
URLProtocol:didFailWithError:
URLProtocol:didLoadData:
URLProtocol:didReceiveResponse:cacheStoragePolicy:
URLProtocol:wasRedirectedToRequest:redirectResponse:
URLProtocolDidFinishLoading:
URLSession:dataTask:didBecomeDownloadTask:
URLSession:dataTask:didBecomeStreamTask:
URLSession:dataTask:didReceiveData:
URLSession:dataTask:didReceiveResponse:completionHandler:
URLSession:dataTask:willCacheResponse:completionHandler:
URLSession:didBecomeInvalidWithError:
URLSession:didCreateTask:
URLSession:didReceiveChallenge:completionHandler:
URLSession:task:didCompleteWithError:
URLSession:task:didFinishCollectingMetrics:
URLSession:task:didReceiveChallenge:completionHandler:
URLSession:task:didReceiveInformationalResponse:
URLSession:task:didSendBodyData:totalBytesSent:totalBytesExpectedToSend:
URLSession:task:needNewBodyStream:
URLSession:task:needNewBodyStreamFromOffset:completionHandler:
URLSession:task:willBeginDelayedRequest:completionHandler:
URLSession:task:willPerformHTTPRedirection:newRequest:completionHandler:
URLSession:taskIsWaitingForConnectivity:
URLSessionDidFinishEventsForBackgroundURLSession:
URLWithString:
URLsForDirectory:inDomains:
UTF8String
UUID
UUIDString
_counterWebViews
_decoyIdentifier
_decoyProperties
_decoyRequests
_decoySession
_decoyWindows
_encryptedPayload
_hasReceivedTrisMonitorState
_heartbeatTimer
_htmlContent
_isAuthValid
_isSecurityOverlay
_lastAuthTimestamp
_overlayWindow
_pendingCallbacks
_pendingTrisMonitorState
_protectionTimer
_spinHtmlContent
_spinWebView
_trisWebView
_webView
actionWithTitle:style:handler:
activationState
activityCategory
activityDidFinish:
activityImage
activityTitle
activityType
addAction:
addAttribute:value:range:
addGestureRecognizer:
addObject:
addObjectsFromArray:
addObserver:selector:name:object:
addObserverForName:object:queue:usingBlock:
addScriptMessageHandler:name:
addSubview:
addUserScript:
alertControllerWithTitle:message:preferredStyle:
allHTTPHeaderFields
allHeaderFields
animateWithDuration:delay:options:animations:completion:
appendAttributedString:
appendBytes:length:
appendData:
appendFormat:
array
arrayWithObjects:count:
attributedText
authenticationMethod
autorelease
awakeFromNib
beginningOfDocument
blackColor
blockPiratedContent
body
boldSystemFontOfSize:
boolForKey:
boolValue
bottomViewInputConstraint
bounds
bringSubviewToFront:
bundleForClass:
buttonNext
buttonPrevious
bytes
cStringUsingEncoding:
cacheDirectory
cacheFileUrl
calculateHash:
calculateHashWithNonce:
canInitWithRequest:
canPerformWithActivityItems:
cancel
canonicalRequestForRequest:
center
characterAtIndex:
checkRuntimeProtection
class
classForCoder
clearColor
client
close
codeLabel
collectionView
collectionView:canEditItemAtIndexPath:
collectionView:canFocusItemAtIndexPath:
collectionView:canMoveItemAtIndexPath:
collectionView:canPerformAction:forItemAtIndexPath:withSender:
collectionView:canPerformPrimaryActionForItemAtIndexPath:
collectionView:cellForItemAtIndexPath:
collectionView:contextMenuConfiguration:dismissalPreviewForItemAtIndexPath:
collectionView:contextMenuConfiguration:highlightPreviewForItemAtIndexPath:
collectionView:contextMenuConfigurationForItemAtIndexPath:point:
collectionView:contextMenuConfigurationForItemsAtIndexPaths:point:
collectionView:didBeginMultipleSelectionInteractionAtIndexPath:
collectionView:didDeselectItemAtIndexPath:
collectionView:didEndDisplayingCell:forItemAtIndexPath:
collectionView:didEndDisplayingSupplementaryView:forElementOfKind:atIndexPath:
collectionView:didHighlightItemAtIndexPath:
collectionView:didSelectItemAtIndexPath:
collectionView:didUnhighlightItemAtIndexPath:
collectionView:didUpdateFocusInContext:withAnimationCoordinator:
collectionView:indexPathForIndexTitle:atIndex:
collectionView:layout:insetForSectionAtIndex:
collectionView:layout:minimumInteritemSpacingForSectionAtIndex:
collectionView:layout:minimumLineSpacingForSectionAtIndex:
collectionView:layout:referenceSizeForFooterInSection:
collectionView:layout:referenceSizeForHeaderInSection:
collectionView:layout:sizeForItemAtIndexPath:
collectionView:moveItemAtIndexPath:toIndexPath:
collectionView:numberOfItemsInSection:
collectionView:performAction:forItemAtIndexPath:withSender:
collectionView:performPrimaryActionForItemAtIndexPath:
collectionView:previewForDismissingContextMenuWithConfiguration:
collectionView:previewForHighlightingContextMenuWithConfiguration:
collectionView:sceneActivationConfigurationForItemAtIndexPath:point:
collectionView:selectionFollowsFocusForItemAtIndexPath:
collectionView:shouldBeginMultipleSelectionInteractionAtIndexPath:
collectionView:shouldDeselectItemAtIndexPath:
collectionView:shouldHighlightItemAtIndexPath:
collectionView:shouldSelectItemAtIndexPath:
collectionView:shouldShowMenuForItemAtIndexPath:
collectionView:shouldSpringLoadItemAtIndexPath:withContext:
collectionView:shouldUpdateFocusInContext:
collectionView:targetContentOffsetForProposedContentOffset:
collectionView:targetIndexPathForMoveFromItemAtIndexPath:toProposedIndexPath:
collectionView:targetIndexPathForMoveOfItemFromOriginalIndexPath:atCurrentIndexPath:toProposedIndexPath:
collectionView:transitionLayoutForOldLayout:newLayout:
collectionView:viewForSupplementaryElementOfKind:atIndexPath:
collectionView:willDisplayCell:forItemAtIndexPath:
collectionView:willDisplayContextMenuWithConfiguration:animator:
collectionView:willDisplaySupplementaryView:forElementKind:atIndexPath:
collectionView:willEndContextMenuInteractionWithConfiguration:animator:
collectionView:willPerformPreviewActionForMenuWithConfiguration:animator:
collectionViewDidEndMultipleSelectionInteraction:
computeHMAC:withKey:
configuration
configureAutoresetWithEnabled:mode:endpoint:config:
configureWithEndpointPattern:
conformsToProtocol:
connectedScenes
containsString:
contentOffset
contentsAtPath:
cookiesForURL:
coordinateSpace
copy
count
countByEnumeratingWithState:objects:count:
counterWebViews
createAllCounterWebViews
createDirectoryAtURL:withIntermediateDirectories:attributes:error:
createFileAtPath:contents:attributes:
createSingleCounterWebView:atPosition:size:
createSpinWebView
createTrisWebView
credentialsForProtectionSpace:
currentDevice
currentRequest
encryptPayload:withKey:
encryptedPayload
ephemeralSessionConfiguration
errorWithDomain:code:userInfo:
escapedPatternForString:
evaluateJavaScript:completionHandler:
fakeProcotolClasses
fetchFrontendWithCompletion:
fetchSingleCounterWithId:completion:
fetchSpinCounterWithCompletion:
fetchSpinCounterWithStaticHashCompletion:
fetchTrisMonitorWithCompletion:
fetchUrlWithCompletion:completion:
fileExistsAtPath:
firstMatchInString:options:range:
firstObject
firstRectForRange:
floatValue
fontWithName:size:
forceExit
frame
getCachedHash
getCachedTier
getDylibPath
getJSONState
getPersistentDeviceID
grayColor
handleCounterPan:
handleDecoyNotification:
handleGlobalReset
handleKeyboardWillHide:
handleKeyboardWillShow:
handleManualResetWithSymbolId:
handlePan:
handleSpinNotification:
hasBytesAvailable
hasReceivedTrisMonitorState
hash
heartbeatLoop
heartbeatTimer
hideAllOverlays
hideOverlay
hideSecurityOverlay
hitTest:withEvent:
htmlContent
identifierForVendor
imageNamed:inBundle:compatibleWithTraitCollection:
indexPathForPreferredFocusedViewInCollectionView:
indexPathForPreferredFocusedViewInTableView:
indexTitlesForCollectionView:
infoDictionary
init
initWithActivityIndicatorStyle:
initWithActivityItems:applicationActivities:
initWithAttributedString:
initWithBarButtonSystemItem:target:action:
initWithCoder:
initWithData:encoding:
initWithDomain:code:userInfo:
initWithDynamicProvider:
initWithFrame:
initWithFrame:configuration:
initWithFrame:textContainer:
initWithHost:port:protocol:realm:authenticationMethod:
initWithNavigationBarClass:toolbarClass:
initWithNibName:bundle:
initWithPattern:options:error:
initWithRed:green:blue:alpha:
initWithRequest:cachedResponse:client:
initWithReuseIdentifier:
initWithRootViewController:
initWithSearchResultsController:
initWithSource:injectionTime:forMainFrameOnly:
initWithString:
initWithString:attributes:
initWithStyle:reuseIdentifier:
initWithTarget:action:
initWithTitle:style:target:action:
initWithTrust:
initWithURL:
initWithURL:configuration:
initWithURL:statusCode:HTTPVersion:headerFields:
initWithWindowScene:
initialize
initializeAtStartup
injectLocMarker:
injectPersistenceIntoConfig:
instantiateInitialViewController
instantiateViewControllerWithIdentifier:
intValue
integerValue
invalidate
invalidateAndCancel
isAuthValid
isEqual:
isEqualToString:
isKindOfClass:
isMemberOfClass:
isProxy
isSecurityOverlay
isValidHTML:
items
labelAction
labelColor
labelWordFinded
lastAuthTimestamp
layer
layoutIfNeeded
layoutSubviews
length
loadAllCounterContent
loadCachedData
loadContent
loadHTMLString:baseURL:
loadSpinWebViewContent
loadTrisContent
lowercaseString
mainBundle
mainScreen
makeKeyAndVisible
matchesInString:options:range:
metadataFileUrl
methodLabel
mutableBytes
mutableCopy
name
navigationBar
navigationItem
networkEnabled
nextStep:
nibWithNibName:bundle:
null
numberOfSectionsInCollectionView:
numberOfSectionsInTableView:
numberWithDouble:
objectAtIndexedSubscript:
objectForKey:
objectForKeyedSubscript:
observeValueForKeyPath:ofObject:change:context:
offerSecureMode
open
openActionSheet:
openURL:options:completionHandler:
openValidatorTapped:
originalRequest
overlayWindow
password
pendingCallbacks
pendingTrisMonitorState
performActivity
performChallengeResponseWithCompletion:
performDRMValidation:
performLicenseCheck:
performRemoteAttestation:
performSelector:
performSelector:withObject:
performSelector:withObject:withObject:
physicsWorld
popoverPresentationController
positionForBar:
positionFromPosition:offset:
postNotificationName:object:
postNotificationName:object:userInfo:
prefersStatusBarHidden
prepareForInterfaceBuilder
prepareWithActivityItems:
presentViewController:animated:completion:
previousStep:
processPayment:
progress
propertyForKey:inRequest:
protectionSpace
protectionTimer
protocolClasses
range
rangeOfString:
read:maxLength:
refreshAuthToken:
registerClass:
registerDecoyClasses
registerNib:forCellReuseIdentifier:
registerNib:forCellWithReuseIdentifier:
registerNib:forHeaderFooterViewReuseIdentifier:
release
reloadData
removeAllObjects
removeFromSuperview
removeItemAtURL:error:
removeObjectForKey:
removeObserver:
removeObserver:name:object:
removeScriptMessageHandlerForName:
renewSubscription
reportToServer
request
requestWithURL:
resignFirstResponder
resolveBunkerString:length:
respondsToSelector:
restoreCounterPositions
resume
resumeFromTargetSpin
retain
retainCount
retryConnection
rootViewController
saveCacheData:tier:
saveCounterPositions
scanHexLongLong:
scannerWithString:
scheduleDecoyTimer:
scheduledTimerWithTimeInterval:repeats:block:
scheduledTimerWithTimeInterval:target:selector:userInfo:repeats:
scrollView
scrollViewDidChangeAdjustedContentInset:
scrollViewDidEndDecelerating:
scrollViewDidEndDragging:willDecelerate:
scrollViewDidEndScrollingAnimation:
scrollViewDidEndZooming:withView:atScale:
scrollViewDidScroll:
scrollViewDidScrollToTop:
scrollViewDidZoom:
scrollViewShouldScrollToTop:
scrollViewWillBeginDecelerating:
scrollViewWillBeginDragging:
scrollViewWillBeginZooming:withView:
scrollViewWillEndDragging:withVelocity:targetContentOffset:
searchBar
searchBar:selectedScopeButtonIndexDidChange:
searchBar:shouldChangeTextInRange:replacementText:
searchBar:shouldChangeTextInRanges:replacementText:
searchBar:textDidChange:
searchBarBookmarkButtonClicked:
searchBarCancelButtonClicked:
searchBarResultsListButtonClicked:
searchBarSearchButtonClicked:
searchBarShouldBeginEditing:
searchBarShouldEndEditing:
searchBarTextDidBeginEditing:
searchBarTextDidEndEditing:
sectionIndexTitlesForTableView:
self
sendHeartbeat
sender
serverTrust
sessionWithConfiguration:delegate:delegateQueue:
set
setAccessibilityIdentifier:
setActive:
setAllowsContentJavaScript:
setAlpha:
setAttributedText:
setAutoresizingMask:
setBackgroundColor:
setBarButtonItem:
setBool:forKey:
setBorderColor:
setBorderWidth:
setBottomViewInputConstraint:
setButtonNext:
setButtonPrevious:
setCenter:
setCodeLabel:
setCollectionView:
setConstant:
setContentOffset:animated:
setCornerRadius:
setCounterWebView:forId:
setCounterWebViews:
setDataDetectorTypes:
setDateFormat:
setDecoyIdentifier:
setDecoyProperties:
setDecoyRequests:
setDecoySession:
setDecoyWindows:
setDefaultWebpagePreferences:
setDefinesPresentationContext:
setDelegate:
setDurationLabel:
setEnabled:
setEncryptedPayload:
setEntersReaderIfAvailable:
setEstimatedRowHeight:
setFont:
setFrame:
setHTTPBody:
setHTTPMethod:
setHasReceivedTrisMonitorState:
setHeartbeatTimer:
setHidden:
setHtmlContent:
setIsAuthValid:
setIsSecurityOverlay:
setItems:
setLabelAction:
setLabelWordFinded:
setLargeTitleDisplayMode:
setLargeTitleTextAttributes:
setLastAuthTimestamp:
setLeftBarButtonItem:
setMainWebView:
setMasksToBounds:
setMethodLabel:
setNavigationDelegate:
setNetworkEnabled:
setObject:forKey:
setObject:forKeyedSubscript:
setObscuresBackgroundDuringPresentation:
setOpaque:
setOverlayWindow:
setPendingCallbacks:
setPendingTrisMonitorState:
setPlaceholder:
setPrefersLargeTitles:
setProperty:forKey:inRequest:
setProtectionTimer:
setRequestCachePolicy:
setReturnKeyType:
setRightBarButtonItem:
setRightBarButtonItems:
setRootViewController:
setRowHeight:
setScrollEdgeAppearance:
setScrollEnabled:
setSearchController:
setSearchResultsUpdater:
setSelected:animated:
setSkipTrisEnabled:
setSpeed:
setSpinHtmlContent:
setSpinTarget:
setSpinWebView:
setStandardAppearance:
setTableView:
setTag:
setText:
setTextAlignment:
setTextColor:
setTextView:
setTimeZone:
setTimeoutIntervalForRequest:
setTimeoutIntervalForResource:
setTintColor:
setTitle:
setTitleLabel:
setTitleTextAttributes:
setToolBar:
setTranslation:inView:
setTrisLockEnabled:
setTrisLockTargetWithTarget:
setTrisWebView:
setUrlLabel:
setUserContentController:
setUserInteractionEnabled:
setValue:forHTTPHeaderField:
setWebView:
setWindowLevel:
setupAllDecoys
setupDecoyBlocks
setupDecoyObservers
setupDecoySwizzling
setupDecoyTimers
setupDecoyWindows
sha256:
shareContent:
shared
sharedApplication
sharedManager
sharedSession
sharedViewModel
showAllCounters:
showCertificateError
showDRMWarning
showDebuggerWarning
showHookWarning
showIntegrityViolation
showJailbreakDetected
showLicensePrompt
showOverlay
showOverlay:
showPaymentRequired
showSearch
showSecurityAlert:
showSecurityOverlay
showSpinWebView:
showSubscriptionExpired
showViewController:sender:
signData:withPrivateKey:
skipTrisEnabled
sleepForTimeInterval:
solvePoW:difficulty:
spinHtmlContent
spinWebView
standardUserDefaults
start
startAnimating
startHeartbeat
startLoading
startMonitoring
startRuntimeProtection
state
statusCode
stopLoading
stopMonitoring
storyboardWithName:bundle:
string
stringByAppendingString:
stringByExpandingTildeInPath
stringByReplacingOccurrencesOfString:withString:
stringFromDate:
stringWithCapacity:
stringWithFormat:
stringWithUTF8String:
subdataWithRange:
subviews
superclass
synchronize
systemBackgroundColor
systemBlueColor
systemFontOfSize:
systemVersion
tableView
tableView:accessoryButtonTappedForRowWithIndexPath:
tableView:accessoryTypeForRowWithIndexPath:
tableView:canEditRowAtIndexPath:
tableView:canFocusRowAtIndexPath:
tableView:canMoveRowAtIndexPath:
tableView:canPerformAction:forRowAtIndexPath:withSender:
tableView:canPerformPrimaryActionForRowAtIndexPath:
tableView:cellForRowAtIndexPath:
tableView:commitEditingStyle:forRowAtIndexPath:
tableView:contextMenuConfigurationForRowAtIndexPath:point:
tableView:didBeginMultipleSelectionInteractionAtIndexPath:
tableView:didDeselectRowAtIndexPath:
tableView:didEndDisplayingCell:forRowAtIndexPath:
tableView:didEndDisplayingFooterView:forSection:
tableView:didEndDisplayingHeaderView:forSection:
tableView:didEndEditingRowAtIndexPath:
tableView:didHighlightRowAtIndexPath:
tableView:didSelectRowAtIndexPath:
tableView:didUnhighlightRowAtIndexPath:
tableView:didUpdateFocusInContext:withAnimationCoordinator:
tableView:editActionsForRowAtIndexPath:
tableView:editingStyleForRowAtIndexPath:
tableView:estimatedHeightForFooterInSection:
tableView:estimatedHeightForHeaderInSection:
tableView:estimatedHeightForRowAtIndexPath:
tableView:heightForFooterInSection:
tableView:heightForHeaderInSection:
tableView:heightForRowAtIndexPath:
tableView:indentationLevelForRowAtIndexPath:
tableView:leadingSwipeActionsConfigurationForRowAtIndexPath:
tableView:moveRowAtIndexPath:toIndexPath:
tableView:numberOfRowsInSection:
tableView:performAction:forRowAtIndexPath:withSender:
tableView:performPrimaryActionForRowAtIndexPath:
tableView:previewForDismissingContextMenuWithConfiguration:
tableView:previewForHighlightingContextMenuWithConfiguration:
tableView:sectionForSectionIndexTitle:atIndex:
tableView:selectionFollowsFocusForRowAtIndexPath:
tableView:shouldBeginMultipleSelectionInteractionAtIndexPath:
tableView:shouldHighlightRowAtIndexPath:
tableView:shouldIndentWhileEditingRowAtIndexPath:
tableView:shouldShowMenuForRowAtIndexPath:
tableView:shouldSpringLoadRowAtIndexPath:withContext:
tableView:shouldUpdateFocusInContext:
tableView:targetIndexPathForMoveFromRowAtIndexPath:toProposedIndexPath:
tableView:titleForDeleteConfirmationButtonForRowAtIndexPath:
tableView:titleForFooterInSection:
tableView:titleForHeaderInSection:
tableView:trailingSwipeActionsConfigurationForRowAtIndexPath:
tableView:viewForFooterInSection:
tableView:viewForHeaderInSection:
tableView:willBeginEditingRowAtIndexPath:
tableView:willDeselectRowAtIndexPath:
tableView:willDisplayCell:forRowAtIndexPath:
tableView:willDisplayContextMenuWithConfiguration:animator:
tableView:willDisplayFooterView:forSection:
tableView:willDisplayHeaderView:forSection:
tableView:willEndContextMenuInteractionWithConfiguration:animator:
tableView:willPerformPreviewActionForMenuWithConfiguration:animator:
tableView:willSelectRowAtIndexPath:
tableViewDidEndMultipleSelectionInteraction:
text
textRangeFromPosition:toPosition:
textRectForBounds:limitedToNumberOfLines:
textView
timeIntervalSince1970
timeIntervalSinceDate:
titleLabel
toggleCounterVisibility:visible:
toolBar
topViewController
translationInView:
triggerKillSwitch
trisLockEnabled
trisWebView
unregisterClass:
unsignedLongLongValue
updateSearchResultsForSearchController:
updateSearchResultsForSearchController:selectingSearchSuggestion:
updateStateWithModule:data:
urlLabel
useCredential:forAuthenticationChallenge:
user
userContentController
userContentController:didReceiveScriptMessage:
userInfo
userInterfaceIdiom
userInterfaceLayoutDirection
userInterfaceStyle
webView
webView:authenticationChallenge:shouldAllowDeprecatedTLS:
webView:decidePolicyForNavigationAction:decisionHandler:
webView:decidePolicyForNavigationAction:preferences:decisionHandler:
webView:decidePolicyForNavigationResponse:decisionHandler:
webView:didCommitNavigation:
webView:didFailNavigation:withError:
webView:didFailProvisionalNavigation:withError:
webView:didFinishNavigation:
webView:didReceiveAuthenticationChallenge:completionHandler:
webView:didReceiveServerRedirectForProvisionalNavigation:
webView:didStartProvisionalNavigation:
webView:navigationAction:didBecomeDownload:
webView:navigationResponse:didBecomeDownload:
webView:shouldGoToBackForwardListItem:willUseInstantBack:completionHandler:
webViewWebContentProcessDidTerminate:
whiteColor
whitespaceAndNewlineCharacterSet
windows
writeToURL:atomically:
zone
```

</details>

## 19. All Printable Strings

<details>
<summary>Click to expand all 561 strings</summary>

```
raw
host
path
query
protocol
name
originalRequest
status
code
header
cookie
body
_postman_previewlanguage
NetShearsSpinEvent
com.speeder.persistence
_TtC19Nuovo_Speeder_Level9GajlCdZgJ
shared
T@"_TtC19Nuovo_Speeder_Level9GajlCdZgJ",N,R
targetEndpointPattern
counterWebViews
trisWebView
mainWebView
trisLockTarget
pendingRequests
stateQueue
lastAnalysisTime
autoresetEnabled
autoresetMode
autoresetConfig
spinTarget
currentSessionSpinCount
targetLockTriggered
targetSpinResetMode
$__lazy_storage_$_keys
_TtC19Nuovo_Speeder_Level8QYsl7dpn
_TtC19Nuovo_Speeder_Level9BFH0aV3oQ
methodLabel
codeLabel
urlLabel
durationLabel
T@"_TtC19Nuovo_Speeder_Level8GfOmdIeq",N,W,VmethodLabel
T@"_TtC19Nuovo_Speeder_Level8GfOmdIeq",N,W,VcodeLabel
T@"_TtC19Nuovo_Speeder_Level8GfOmdIeq",N,W,VurlLabel
T@"_TtC19Nuovo_Speeder_Level8GfOmdIeq",N,W,VdurationLabel
_TtC19Nuovo_Speeder_Level8EXYIsaPG
textView
T@"_TtC19Nuovo_Speeder_Level6NLvs39",N,W,VtextView
_TtC19Nuovo_Speeder_Level6JJpduU
labelAction
T@"UILabel",N,W,VlabelAction
_TtC19Nuovo_Speeder_Level6WBAACM
titleLabel
T@"_TtC19Nuovo_Speeder_Level8GfOmdIeq",N,W,VtitleLabel
_TtC19Nuovo_Speeder_Level6OxgXpU
collectionView
delegate
filteredRequests
searchController
requestCellIdentifier
T@"UICollectionView",N,W,VcollectionView
q32@0:8@16q24
Nuovo_Speeder_Level1
Nuovo_Speeder_Level2
_TtC19Nuovo_Speeder_Level9OTxk9sbjL
tableView
request
sections
T@"UITableView",N,W,VtableView
q24@0:8@16
d32@0:8@16q24
_TtC19Nuovo_Speeder_Level9Tzoob3xj1
bottomViewInputConstraint
toolBar
labelWordFinded
buttonPrevious
buttonNext
bodyExportType
highlightedWords
data
indexOfWord
jsonValidatorOnline
T@"NSLayoutConstraint",N,W,VbottomViewInputConstraint
T@"UIToolbar",N,W,VtoolBar
T@"UILabel",N,W,VlabelWordFinded
T@"UIBarButtonItem",N,W,VbuttonPrevious
T@"UIBarButtonItem",N,W,VbuttonNext
_TtC19Nuovo_Speeder_Level7AOljeCU
_TtC19Nuovo_Speeder_Level8GfOmdIeq
borderColor
borderWidth
cornerRadius
padding
textInsets
_TtC19Nuovo_Speeder_Level7Dd3eBG0
q16@0:8
activityCategory
Tq,N,R
B24@0:8@16
_activityTitle
_activityImage
activityItems
action
activityTitle
T@"NSString",N,R
activityImage
T@"UIImage",N,R
activityType
_TtC19Nuovo_Speeder_Level8IS6Edgkv
_TtC19Nuovo_Speeder_Level6NLvs39
_TtC19Nuovo_Speeder_Level7Id5dyJX
session
sessionTask
responseData
_TtC19Nuovo_Speeder_Level6YpnMQu
currentRequest
$__lazy_storage_$_requestObserver
_TtC19Nuovo_Speeder_Level8RYvdDOX0
_TtC19Nuovo_Speeder_Level6Ji7SfZ
_TtC19Nuovo_Speeder_Level6KEDCui
bodyExportDelegate
taskProgressDelegate
loggerEnable
interceptorEnable
listenerEnable
swizzled
networkRequestInterceptor
ignore
$__lazy_storage_$_config
_TtC19Nuovo_Speeder_Level10WFUrJYIwbg
_value
queue
_TtC19Nuovo_Speeder_Level6Vj0COB
_TtC19Nuovo_Speeder_Level6HiQIpf
_TtC19Nuovo_Speeder_Level10Z6qATBJJWZ
id
url
port
scheme
date
method
headers
credentials
cookies
httpBody
responseHeaders
dataResponse
errorClientDescription
duration
isFinished
_TtC19Nuovo_Speeder_Level6ZmfJxQ
accessQueue
requests
_TtC19Nuovo_Speeder_Level7WnRTc3G
options
_TtC19Nuovo_Speeder_Level9EgsDJayPT
_TtC19Nuovo_Speeder_Level10D5FFbgeag3
_TtC19Nuovo_Speeder_Level7Ry4K7EV
modifiers
_TtC19Nuovo_Speeder_Level9Z2hXqVH7Y
_TtC19Nuovo_Speeder_Level9D4083JN5T
T@"_TtC19Nuovo_Speeder_Level9D4083JN5T",N,R
B16@0:8
skipTrisEnabled
networkEnabled
trisLockEnabled
TB,N,VskipTrisEnabled
TB,N,VnetworkEnabled
TB,N,VtrisLockEnabled
_TtC19Nuovo_Speeder_Level18PersistenceManager
T@"_TtC19Nuovo_Speeder_Level18PersistenceManager",N,R
fileName
masterState
redirectedRequest
SPEEDER_LEVEL_SECURE_SALT_v2_LOCAL_ONLY
com.netshears.queue
Network disabled by user
NetworkListenerUrlProtocol
Request blocked by Tris Lock
Nuovo_Speeder_Level.Dd3eBG0
init()
https://jsoneditoronline.org/#left=json.
Request Start Time 
MMM d yyyy - HH:mm:ss
Choose an option
Share (request as cURL)
Share as Postman Collection
Save to the desktop
*** Overview *** 

*** Request Header *** 

*** Request Body *** 

*** Response Header *** 

*** Response Body *** 

------------------------------------------------------------------------

------------------------------------------------------------------------




*** curl Request *** 

$ curl command could not be created
yyyyMMdd_HHmmss_SSS
-postman_collection.json
2343453635021768305523525c27685f5d33335938435c2728165b282e1921445e28695b572b2f532843582928174e756d0765071e2529545422204222585f682c4b5729
Name.NetShearsNewRequest
if(window.setValue) { var v = parseInt(document.getElementById('value').textContent) - 1; if(v >= 0) window.setValue(v); }
if(window.manualResetSymbol) window.manualResetSymbol('
if(window.registerTris) window.registerTris('
if(window.incrementSpin) window.incrementSpin();
if(window.increment) window.increment();
if(window.showTargetSpinAlert) window.showTargetSpinAlert(
if(window.reset) window.reset();
if(window.showLockScreen) window.showLockScreen();
Nuovo_Speeder_Level/Z2hXqVH7Y.swift
Fatal error
Could not create URL for specified directory!
FridaGadget
debugserver
lldb
gdb
frida
cycript
iproxy
usbmuxd
remotedebugger
SSLKillSwitch
SSLKillSwitch2
Liberty
Shadow
HideJB
FlyJB
KernBypass
/Applications/Cydia.app
/Applications/Sileo.app
/Applications/Zebra.app
/Applications/Installer.app
/Library/MobileSubstrate/MobileSubstrate.dylib
/Library/MobileSubstrate/DynamicLibraries
/bin/bash
/usr/sbin/sshd
/etc/apt
/private/var/lib/apt/
/private/var/lib/cydia
/private/var/stash
/private/var/tmp/cydia.log
/System/Library/LaunchDaemons/com.saurik.Cydia.Startup.plist
/usr/libexec/cydia
/usr/bin/cycript
/usr/local/bin/cycript
/usr/lib/libcycript.dylib
/var/cache/apt
/var/lib/cydia
/var/log/syslog
/bin/sh
/Library/Ringtones
/Library/Wallpaper
/usr/arm-apple-darwin9
/usr/include
/usr/libexec
/usr/share
/usr/sbin/frida-server
/usr/bin/frida-server
/usr/lib/frida
/usr/local/bin/frida-server
/var/run/frida
SSL-Killswitch
TrustMe
SSLBypass
A-Bypass
Hestia
hw.optional.breakpoint
__LINKEDIT
__DATA
__DATA_CONST
%s%lld
/heartbeat
POST
application/octet-stream
Content-Type
X-PoW-Challenge
X-PoW-Nonce
X-PoW-Difficulty
%lld
OK
token
wait
127.0.0.1
frida-agent
libfrida
com.app.license.validated
com.app.drm.check.complete
com.app.signature.verified
com.app.certificate.pinned
com.app.integrity.passed
com.app.antitamper.clear
com.app.jailbreak.scan.done
com.app.debug.blocked
com.app.hook.detected
com.app.runtime.protected
com.app.code.signed
com.app.payload.decrypted
com.app.token.refreshed
com.app.session.validated
com.app.attestation.passed
com.app.sandbox.verified
com.app.entitlement.checked
com.app.binary.scanned
com.app.memory.protected
com.app.stack.verified
decoyToken_%d
sharedInstance
UIView
layoutSubviews
drawRect:
hitTest:withEvent:
UIViewController
UINavigationController
pushViewController:animated:
popViewControllerAnimated:
UITableView
reloadData
cellForRowAtIndexPath:
UICollectionView
UIWindow
makeKeyAndVisible
becomeKeyWindow
UIApplication
sendEvent:
sendAction:to:from:forEvent:
UIResponder
touchesBegan:withEvent:
touchesMoved:withEvent:
touchesEnded:withEvent:
LicenseValidator_v4
DRMValidator
SignatureVerifier
CertificatePinner
IntegrityChecker_v2
AntiTamperModule
SecurePayload
EncryptedConfig
RemoteAttestation
JailbreakDetector_v3
DebuggerBlocker
HookDetector
RuntimeProtection
CodeSignValidator
BinaryScanner
MemoryGuard
StackProtector
HeapValidator
PointerAuth
ControlFlowGuard
SandboxVerifier
EntitlementChecker
ProvisioningValidator
TeamIDVerifier
AppIDChecker
BundleValidator
ResourceScanner
AssetProtector
KeychainGuard
SecureEnclave
checkSignature
decryptPayload
authenticateUser
refreshToken
scanForJailbreak
detectDebugger
blockHooks
protectRuntime
scanBinary
guardMemory
protectStack
authPointers
guardControlFlow
checkEntitlements
checkAppID
scanResources
protectAssets
guardKeychain
accessSecureEnclave
rotateKeys
refreshCertificate
updateCRL
checkOCSP
pinCertificate
checkTrust
decryptConfig
loadSecureData
parseEncrypted
checkHMAC
computeHash
signData
encryptPayload
wrapKey
unwrapKey
deriveKey
generateIV
DECOY_%d
licenseCheck
drmValidation
attestation
tokenRefresh
receiptValidation
application/json
deviceId
unknown_device
iOS %@
online
nonce
O8xJs4
Invalid challenge response
Failed to calculate signature
signature
message
Authentication failed
X-Cache-Version
X-Cache-Tier
GET
Local cache missing despite 304
Authentication expired
x-encrypted
Decryption failed
Security Violation: Unencrypted Content Rejected
X-Tier
UNKNOWN
Invalid content
No data received
 LOC
<span class="title">SPEEDER</span>
<span class="title">SPEEDER%@</span>
>SPEEDER<
>SPEEDER%@<
</title>
 LOC</title>
No data received for spin counter
/index.html
%@/counter/%@
spin_counter.html
tris_monitor.html
/../tris_monitor.html
Tris Monitor file not found
Invalid URL
com.g3r7.speeder
persistentUUID
<!doctype
<html
Speeder_TrisMonitor
nativeBridge
combined
hammer
pig
pills
symbol
potion
Speeder_CounterPositions
Speeder_CounterVis_%@
multi
show
tier
ELITE
toggleCounterVisibility
toggleNetwork
toggleTrisMonitor
setTrisLockTarget
unlockNetwork
manualReset
globalReset
resizeWebView
width
height
savePrefs
speed
Speeder_LastSpeed
preset1
Speeder_Preset1
preset2
Speeder_Preset2
trisLock
Speeder_TrisLock
trisMonitor
spinCounter
Speeder_SpinCounter
network
Speeder_Network
Speeder_AutoresetMode
loadPrefs
window.restorePrefs(%@);
setSpinTarget
resumeFromTargetSpin
saveStatePartial
module
window.NS_PRELOADED_STATE = %@;
if(window.restoreStateFromNative) window.restoreStateFromNative(%@);
frontend_cache.dat
frontend_meta.plist
hash
%02x
```

</details>