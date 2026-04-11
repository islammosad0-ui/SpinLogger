#import "SLMemoryScanner.h"
#import "SLConstants.h"
#include <dlfcn.h>
#include <string.h>
#include <mach/mach_time.h>

// ============================================================
//  IL2CPP API Type Definitions
// ============================================================
typedef void*       (*fn_domain_get)(void);
typedef void**      (*fn_domain_get_assemblies)(void* domain, size_t* size);
typedef void*       (*fn_assembly_get_image)(void* assembly);
typedef const char* (*fn_image_get_name)(void* image);
typedef size_t      (*fn_image_get_class_count)(void* image);
typedef void*       (*fn_image_get_class)(void* image, size_t index);
typedef const char* (*fn_class_get_name)(void* klass);
typedef const char* (*fn_class_get_namespace)(void* klass);
typedef void*       (*fn_class_get_field_from_name)(void* klass, const char* name);
typedef void*       (*fn_class_get_fields)(void* klass, void** iter);
typedef const char* (*fn_field_get_name)(void* field);
typedef size_t      (*fn_field_get_offset)(void* field);
typedef void        (*fn_field_static_get_value)(void* field, void* value);
typedef void        (*fn_runtime_class_init)(void* klass);

// ============================================================
//  Cached IL2CPP function pointers
// ============================================================
static fn_domain_get                 _domain_get;
static fn_domain_get_assemblies      _domain_get_assemblies;
static fn_assembly_get_image         _assembly_get_image;
static fn_image_get_name             _image_get_name;
static fn_image_get_class_count      _image_get_class_count;
static fn_image_get_class            _image_get_class;
static fn_class_get_name             _class_get_name;
static fn_class_get_namespace        _class_get_namespace;
static fn_class_get_field_from_name  _class_get_field_from_name;
static fn_class_get_fields           _class_get_fields;
static fn_field_get_name             _field_get_name;
static fn_field_get_offset           _field_get_offset;
static fn_field_static_get_value     _field_static_get_value;
static fn_runtime_class_init         _runtime_class_init;

// ============================================================
//  Cached class pointers
// ============================================================
static void* s_klass_Manager     = NULL;  // SlotMachineManager
static void* s_klass_Result      = NULL;  // SlotResult
static void* s_klass_Symbol3     = NULL;  // SlotSymbol3
static void* s_klass_BarManager  = NULL;  // SlotBarManager
static void* s_klass_BarSymInfo  = NULL;  // SlotBarSymbolInfo
static void* s_klass_BoardMgr   = NULL;  // SlotMachine.BoardManager

// ============================================================
//  Cached field handles & offsets
//  Convention: fh_ = field handle, fo_ = field offset
// ============================================================

// SlotMachineManager
static void*  fh_Instance            = NULL;   // static field → use static_get_value
static size_t fo_spinning            = 0;
static size_t fo_betState            = 0;
static size_t fo_currentSpinNumber   = 0;
static size_t fo_currentSlotResult   = 0;
static size_t fo_failCounter         = 0;
static size_t fo_failCounterGlobal   = 0;
static size_t fo_failThreshold       = 0;      // m_SpinFailedAnalyticThreshold
static size_t fo_dynamicResults      = 0;
static size_t fo_freezeCtx           = 0;
static size_t fo_lastBalShields      = 0;
static size_t fo_slotBar1            = 0;
static size_t fo_slotBar2            = 0;
static size_t fo_slotBar3            = 0;
static size_t fo_boardManager        = 0;      // m_BoardManager

// SlotResult
static size_t fo_slotSymbols         = 0;

// SlotSymbol3
static size_t fo_symbol1             = 0;
static size_t fo_symbol2             = 0;
static size_t fo_symbol3             = 0;

// SlotBarManager
static size_t fo_resultSymbolIndex   = 0;
static size_t fo_numberOfSymbols     = 0;
static size_t fo_symbolElements      = 0;      // m_SymbolElements array

// SlotBarSymbolInfo
static size_t fo_slotSymbolBacking   = 0;      // <SlotSymbol>k__BackingField

// BoardManager
static size_t fo_diceWinDict         = 0;      // m_DiceWinResultDictionary

// ============================================================
//  IL2CPP array layout constants (arm64)
// ============================================================
#define kArrayHeaderSize   32   // vtable(8) + monitor(8) + bounds(8) + length(8)
#define kArrayLengthOffset 24

// Read pointer element from IL2CPP reference-type array
static inline void* arrayElementPtr(void* array, int32_t index) {
    if (!array) return NULL;
    int64_t len = *(int64_t*)((uint8_t*)array + kArrayLengthOffset);
    if (index < 0 || index >= len) return NULL;
    return *(void**)((uint8_t*)array + kArrayHeaderSize + index * sizeof(void*));
}

/// Heuristic: does this pointer look like a valid IL2CPP heap address?
/// ARM64 user-space heap is typically in 0x100000000–0x7FFFFFFFFF range.
static inline BOOL looksLikeHeapPointer(void *p) {
    uintptr_t addr = (uintptr_t)p;
    if (addr < 0x100000000ULL) return NO;       // too low (nil / small int)
    if (addr > 0x7FFFFFFFFFULL) return NO;      // too high (kernel / garbage)
    if (addr & 0x7) return NO;                  // misaligned (not an object)
    return YES;
}

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

// ============================================================
//  SLScanSnapshot implementation
// ============================================================
@implementation SLScanSnapshot
- (float)pityProgress {
    if (self.failThreshold <= 0) return 0;
    float p = (float)self.failCounterGlobal / (float)self.failThreshold;
    return p > 1.0f ? 1.0f : p;
}
@end

// ============================================================
//  Scanner phases
// ============================================================
typedef NS_ENUM(NSInteger, ScanPhase) {
    ScanPhaseResolveAPIs = 0,
    ScanPhaseFindClasses,
    ScanPhaseCacheOffsets,
    ScanPhaseWaitInstance,
    ScanPhaseActive
};

// ============================================================
//  SLMemoryScanner
// ============================================================
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

@implementation SLMemoryScanner

+ (instancetype)shared {
    static SLMemoryScanner *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

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

- (uint64_t)monotonicMillis {
    static mach_timebase_info_data_t tb;
    if (tb.denom == 0) mach_timebase_info(&tb);
    uint64_t nanos = mach_absolute_time() * tb.numer / tb.denom;
    return nanos / 1000000ULL;
}

// ============================================================
//  Phase 0: Resolve IL2CPP API function pointers
// ============================================================
- (BOOL)resolveAPIs {
    void *h = RTLD_DEFAULT;
    #define RESOLVE(name) _ ## name = (fn_ ## name)dlsym(h, "il2cpp_" #name)
    RESOLVE(domain_get);
    RESOLVE(domain_get_assemblies);
    RESOLVE(assembly_get_image);
    RESOLVE(image_get_name);
    RESOLVE(image_get_class_count);
    RESOLVE(image_get_class);
    RESOLVE(class_get_name);
    RESOLVE(class_get_namespace);
    RESOLVE(class_get_field_from_name);
    RESOLVE(class_get_fields);
    RESOLVE(field_get_name);
    RESOLVE(field_get_offset);
    RESOLVE(field_static_get_value);
    RESOLVE(runtime_class_init);
    #undef RESOLVE

    if (!_domain_get || !_domain_get_assemblies || !_class_get_field_from_name) {
        NSLog(@"[SpinLogger] IL2CPP API resolution failed");
        return NO;
    }
    self.domain = _domain_get();
    NSLog(@"[SpinLogger] IL2CPP APIs resolved, domain=%p", self.domain);
    return YES;
}

// ============================================================
//  Phase 1: Find target classes by iterating assemblies
// ============================================================
- (BOOL)findClasses {
    size_t asmCount = 0;
    void** asms = _domain_get_assemblies(self.domain, &asmCount);
    if (!asms) return NO;

    for (size_t i = 0; i < asmCount; i++) {
        void* image = _assembly_get_image(asms[i]);
        if (!image) continue;
        size_t classCount = _image_get_class_count(image);

        for (size_t j = 0; j < classCount; j++) {
            void* klass = _image_get_class(image, j);
            if (!klass) continue;
            const char* name = _class_get_name(klass);
            const char* ns   = _class_get_namespace ? _class_get_namespace(klass) : "";
            if (!name) continue;

            // Match by exact class name (preferring root namespace classes)
            if (strcmp(name, "SlotMachineManager") == 0 && strlen(ns) == 0)
                s_klass_Manager = klass;
            else if (strcmp(name, "SlotResult") == 0 && strlen(ns) == 0)
                s_klass_Result = klass;
            else if (strcmp(name, "SlotSymbol3") == 0 && strlen(ns) == 0)
                s_klass_Symbol3 = klass;
            else if (strcmp(name, "SlotBarManager") == 0 && strlen(ns) == 0)
                s_klass_BarManager = klass;
            else if (strcmp(name, "SlotBarSymbolInfo") == 0 && strlen(ns) == 0)
                s_klass_BarSymInfo = klass;
            else if (strcmp(name, "BoardManager") == 0 && strcmp(ns, "SlotMachine") == 0)
                s_klass_BoardMgr = klass;
        }
    }

    BOOL ok = (s_klass_Manager && s_klass_Result && s_klass_Symbol3 && s_klass_BarManager);
    if (ok) NSLog(@"[SpinLogger] Core classes found: Manager=%p Result=%p Sym3=%p Bar=%p BarInfo=%p Board=%p",
                  s_klass_Manager, s_klass_Result, s_klass_Symbol3,
                  s_klass_BarManager, s_klass_BarSymInfo, s_klass_BoardMgr);
    else    NSLog(@"[SpinLogger] Some classes not found, retrying...");
    return ok;
}

// ============================================================
//  Phase 2: Cache field offsets
// ============================================================

/// Helper: get offset for a named field on a class, logs warning on failure
static size_t offsetFor(void* klass, const char* fieldName, const char* className) {
    void* field = _class_get_field_from_name(klass, fieldName);
    if (!field) {
        NSLog(@"[SpinLogger] WARNING: Field '%s' not found on %s", fieldName, className);
        return 0;
    }
    return _field_get_offset(field);
}

/// Helper: get field handle (for static fields)
static void* fieldHandleFor(void* klass, const char* fieldName) {
    return _class_get_field_from_name(klass, fieldName);
}

- (BOOL)cacheOffsets {
    // SlotMachineManager fields
    fh_Instance          = fieldHandleFor(s_klass_Manager, "Instance");
    fo_spinning          = offsetFor(s_klass_Manager, "spinning",                     "SlotMachineManager");
    fo_betState          = offsetFor(s_klass_Manager, "betState",                     "SlotMachineManager");
    fo_currentSpinNumber = offsetFor(s_klass_Manager, "currentSpinNumber",            "SlotMachineManager");
    fo_currentSlotResult = offsetFor(s_klass_Manager, "currentSlotResult",            "SlotMachineManager");
    fo_failCounter       = offsetFor(s_klass_Manager, "m_SpinFailedCounter",          "SlotMachineManager");
    fo_failCounterGlobal = offsetFor(s_klass_Manager, "m_SpinFailedCounterGlobal",    "SlotMachineManager");
    fo_failThreshold     = offsetFor(s_klass_Manager, "m_SpinFailedAnalyticThreshold","SlotMachineManager");
    fo_dynamicResults    = offsetFor(s_klass_Manager, "DynamicSlotResults",           "SlotMachineManager");
    fo_freezeCtx         = offsetFor(s_klass_Manager, "m_FreezeResolveContext",       "SlotMachineManager");
    fo_lastBalShields    = offsetFor(s_klass_Manager, "lastBalanceShields",           "SlotMachineManager");
    fo_slotBar1          = offsetFor(s_klass_Manager, "_slotBar1",                    "SlotMachineManager");
    fo_slotBar2          = offsetFor(s_klass_Manager, "_slotBar2",                    "SlotMachineManager");
    fo_slotBar3          = offsetFor(s_klass_Manager, "_slotBar3",                    "SlotMachineManager");
    fo_boardManager      = offsetFor(s_klass_Manager, "m_BoardManager",              "SlotMachineManager");

    // SlotResult fields
    fo_slotSymbols       = offsetFor(s_klass_Result, "slotSymbols", "SlotResult");

    // SlotSymbol3 fields
    fo_symbol1           = offsetFor(s_klass_Symbol3, "symbol1", "SlotSymbol3");
    fo_symbol2           = offsetFor(s_klass_Symbol3, "symbol2", "SlotSymbol3");
    fo_symbol3           = offsetFor(s_klass_Symbol3, "symbol3", "SlotSymbol3");

    // SlotBarManager fields
    fo_resultSymbolIndex = offsetFor(s_klass_BarManager, "resultSymbolIndex", "SlotBarManager");
    fo_numberOfSymbols   = offsetFor(s_klass_BarManager, "m_NumberOfSymbols", "SlotBarManager");
    fo_symbolElements    = offsetFor(s_klass_BarManager, "m_SymbolElements",  "SlotBarManager");

    // SlotBarSymbolInfo (optional)
    if (s_klass_BarSymInfo) {
        // Auto-property backing field uses angle brackets in name
        fo_slotSymbolBacking = offsetFor(s_klass_BarSymInfo, "<SlotSymbol>k__BackingField", "SlotBarSymbolInfo");
    }

    // BoardManager (optional)
    if (s_klass_BoardMgr) {
        fo_diceWinDict = offsetFor(s_klass_BoardMgr, "m_DiceWinResultDictionary", "BoardManager");
    }

    if (!fh_Instance || !fo_spinning || !fo_currentSlotResult) {
        NSLog(@"[SpinLogger] Critical field offsets missing");
        return NO;
    }

    // Initialize the class so static fields are populated
    if (_runtime_class_init) _runtime_class_init(s_klass_Manager);

    NSLog(@"[SpinLogger] Field offsets cached successfully");
    return YES;
}

// ============================================================
//  Read helpers — safe memory reads with null checks
// ============================================================
static inline void* readPtr(void* obj, size_t offset) {
    if (!obj || !offset) return NULL;
    return *(void**)((uint8_t*)obj + offset);
}

static inline int32_t readInt32(void* obj, size_t offset) {
    if (!obj || !offset) return 0;
    return *(int32_t*)((uint8_t*)obj + offset);
}

static inline uint8_t readBool(void* obj, size_t offset) {
    if (!obj || !offset) return 0;
    return *(uint8_t*)((uint8_t*)obj + offset);
}

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

// ============================================================
//  Main timer tick — state machine
// ============================================================
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

@end
