#import "SLMemoryScanner.h"
#import "SLIdxStrategy.h"
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
static void* s_klass_BoardMgr    = NULL;  // SlotMachine.BoardManager (legacy)

// Scanner v2 — pre-commitment state classes
static void* s_klass_Board3D     = NULL;  // SlotMachine.Dice.Board3DManager
static void* s_klass_ReplSvc     = NULL;  // SlotSymbolReplacementService (singleton)
static void* s_klass_BarRepl     = NULL;  // SlotBarSymbolReplacer (per-reel)
static void* s_klass_WinComp     = NULL;  // SlotMachineWinBehaviourComposite
static void* s_klass_ScenBhv     = NULL;  // ScenarioSlotMachineWinBehaviour
static void* s_klass_DataProv    = NULL;  // SlotDataProvider
static void* s_klass_PvpSlots    = NULL;  // PvpBaseCompetitorSlotsController (RNG ref)
static void* s_klass_BaseSymCtrl = NULL;  // BaseSlotSymbolController (back-ref path)

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
static size_t fo_slotObjects         = 0;      // slotObjects (GameObject[] alt strip access)
static size_t fo_symbolReplacer      = 0;      // m_SymbolReplacer → SlotBarSymbolReplacer

// SlotBarSymbolInfo
static size_t fo_slotSymbolBacking   = 0;      // <SlotSymbol>k__BackingField

// BoardManager
static size_t fo_diceWinDict         = 0;      // m_DiceWinResultDictionary

// Scanner v2 — new Manager fields
static size_t fo_specialEvents       = 0;      // m_SpecialEventsContainers
static size_t fo_animSpeedBacking    = 0;      // <SlotMachineAnimationSpeed>k__BackingField
static size_t fo_winBehaviours       = 0;      // m_WinBehaviours (on Manager, if present)

// Board3DManager fields
static size_t fo_nearWinSymbol       = 0;      // m_NearWinSymbol
static size_t fo_throwScenarios      = 0;      // m_ThrowDiceScenarios
static size_t fo_nearWinScenarios    = 0;      // m_DiceNearWinThrowScenarios

// SlotBarSymbolReplacer fields
static size_t fo_replMap             = 0;      // m_Replacements
static size_t fo_replBarMgr          = 0;      // m_BarManager (back-ref to which reel)

// SlotSymbolReplacementService
static void*  fh_ReplSvcInstance     = NULL;   // static Instance handle
static size_t fo_persistentRepl      = 0;      // persistentReplacements

// SlotMachineWinBehaviourComposite
static size_t fo_compWinBehaviours   = 0;      // m_WinBehaviours

// ScenarioSlotMachineWinBehaviour
static size_t fo_scenScenario        = 0;      // m_Scenario

// SlotDataProvider
static size_t fo_dataProvFailCounter = 0;      // SpinFailedCounter (alt ref)

// PvpBaseCompetitorSlotsController — RNG reference
static size_t fo_pvpRandom           = 0;      // m_Random

// BaseSlotSymbolController — back-ref from symbol controllers up to Manager
static size_t fo_baseSymMgrRef       = 0;      // m_SlotMachineManager

// SlotMachineManager — static weight tables
// Stored as field handles (not offsets) since they are static fields read
// via _field_static_get_value into a pointer target.
static void*  fh_WeightsIdentical    = NULL;   // WEIGHTS_IDENTICAL_SYMBOLS
static void*  fh_WeightsNonIdentical = NULL;   // WEIGHTS_NON_IDENTICAL_SYMBOLS

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
            // Scanner v2 — pre-commitment state classes.
            // For these we don't know the exact namespace for sure; take the
            // first match by name. If there are multiple CM-owned classes with
            // the same name (unlikely for these specific names), we'll pick
            // one deterministically by iteration order.
            else if (strcmp(name, "Board3DManager") == 0 && !s_klass_Board3D)
                s_klass_Board3D = klass;
            else if (strcmp(name, "SlotSymbolReplacementService") == 0 && !s_klass_ReplSvc)
                s_klass_ReplSvc = klass;
            else if (strcmp(name, "SlotBarSymbolReplacer") == 0 && !s_klass_BarRepl)
                s_klass_BarRepl = klass;
            else if (strcmp(name, "SlotMachineWinBehaviourComposite") == 0 && !s_klass_WinComp)
                s_klass_WinComp = klass;
            else if (strcmp(name, "ScenarioSlotMachineWinBehaviour") == 0 && !s_klass_ScenBhv)
                s_klass_ScenBhv = klass;
            else if (strcmp(name, "SlotDataProvider") == 0 && !s_klass_DataProv)
                s_klass_DataProv = klass;
            else if (strcmp(name, "PvpBaseCompetitorSlotsController") == 0 && !s_klass_PvpSlots)
                s_klass_PvpSlots = klass;
            else if (strcmp(name, "BaseSlotSymbolController") == 0 && !s_klass_BaseSymCtrl)
                s_klass_BaseSymCtrl = klass;
        }
    }

    BOOL ok = (s_klass_Manager && s_klass_Result && s_klass_Symbol3 && s_klass_BarManager);
    if (ok) {
        NSLog(@"[SpinLogger] Core classes: Manager=%p Result=%p Sym3=%p Bar=%p BarInfo=%p Board=%p",
              s_klass_Manager, s_klass_Result, s_klass_Symbol3,
              s_klass_BarManager, s_klass_BarSymInfo, s_klass_BoardMgr);
        NSLog(@"[SpinLogger] v2 classes:  Board3D=%p ReplSvc=%p BarRepl=%p WinComp=%p ScenBhv=%p DataProv=%p",
              s_klass_Board3D, s_klass_ReplSvc, s_klass_BarRepl,
              s_klass_WinComp, s_klass_ScenBhv, s_klass_DataProv);
        NSLog(@"[SpinLogger] v2 extras:   PvpSlots=%p BaseSymCtrl=%p",
              s_klass_PvpSlots, s_klass_BaseSymCtrl);
    } else {
        NSLog(@"[SpinLogger] Some classes not found, retrying...");
    }
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
    fo_slotObjects       = offsetFor(s_klass_BarManager, "slotObjects",       "SlotBarManager");
    fo_symbolReplacer    = offsetFor(s_klass_BarManager, "m_SymbolReplacer",  "SlotBarManager");

    // SlotBarSymbolInfo (optional)
    if (s_klass_BarSymInfo) {
        // Auto-property backing field uses angle brackets in name
        fo_slotSymbolBacking = offsetFor(s_klass_BarSymInfo, "<SlotSymbol>k__BackingField", "SlotBarSymbolInfo");
    }

    // BoardManager (optional)
    if (s_klass_BoardMgr) {
        fo_diceWinDict = offsetFor(s_klass_BoardMgr, "m_DiceWinResultDictionary", "BoardManager");
    }

    // Scanner v2 — additional Manager fields (all optional; offsetFor returns 0
    // and logs a warning on missing fields, which is fine)
    fo_specialEvents    = offsetFor(s_klass_Manager, "m_SpecialEventsContainers",        "SlotMachineManager");
    fo_animSpeedBacking = offsetFor(s_klass_Manager,
                                    "<SlotMachineAnimationSpeed>k__BackingField",
                                    "SlotMachineManager");
    fo_winBehaviours    = offsetFor(s_klass_Manager, "m_WinBehaviours",                  "SlotMachineManager");

    // Board3DManager fields (only if the class was resolved)
    if (s_klass_Board3D) {
        fo_nearWinSymbol    = offsetFor(s_klass_Board3D, "m_NearWinSymbol",              "Board3DManager");
        fo_throwScenarios   = offsetFor(s_klass_Board3D, "m_ThrowDiceScenarios",         "Board3DManager");
        fo_nearWinScenarios = offsetFor(s_klass_Board3D, "m_DiceNearWinThrowScenarios",  "Board3DManager");
    }

    // SlotBarSymbolReplacer fields
    if (s_klass_BarRepl) {
        fo_replMap    = offsetFor(s_klass_BarRepl, "m_Replacements", "SlotBarSymbolReplacer");
        fo_replBarMgr = offsetFor(s_klass_BarRepl, "m_BarManager",   "SlotBarSymbolReplacer");
    }

    // SlotSymbolReplacementService — singleton with a static Instance handle
    if (s_klass_ReplSvc) {
        fh_ReplSvcInstance = fieldHandleFor(s_klass_ReplSvc, "Instance");
        fo_persistentRepl  = offsetFor(s_klass_ReplSvc, "persistentReplacements",
                                       "SlotSymbolReplacementService");
        if (_runtime_class_init) _runtime_class_init(s_klass_ReplSvc);
    }

    // SlotMachineWinBehaviourComposite
    if (s_klass_WinComp) {
        fo_compWinBehaviours = offsetFor(s_klass_WinComp, "m_WinBehaviours",
                                         "SlotMachineWinBehaviourComposite");
    }

    // ScenarioSlotMachineWinBehaviour
    if (s_klass_ScenBhv) {
        fo_scenScenario = offsetFor(s_klass_ScenBhv, "m_Scenario",
                                    "ScenarioSlotMachineWinBehaviour");
    }

    // SlotDataProvider — alternative fail counter reference
    if (s_klass_DataProv) {
        fo_dataProvFailCounter = offsetFor(s_klass_DataProv, "SpinFailedCounter",
                                           "SlotDataProvider");
    }

    // PvpBaseCompetitorSlotsController — direct RNG instance reference.
    // No reachable instance path from Manager yet; cache the offset so we can
    // dump it if we later find one, and Python can still decode a captured
    // hex window if the class turns up in discovery.
    if (s_klass_PvpSlots) {
        fo_pvpRandom = offsetFor(s_klass_PvpSlots, "m_Random",
                                 "PvpBaseCompetitorSlotsController");
    }

    // BaseSlotSymbolController — back-ref to Manager (useful for future
    // instance-walks from symbol controllers).
    if (s_klass_BaseSymCtrl) {
        fo_baseSymMgrRef = offsetFor(s_klass_BaseSymCtrl, "m_SlotMachineManager",
                                     "BaseSlotSymbolController");
    }

    // SlotMachineManager static weight tables — read as static fields.
    // These are `int[]` (managed arrays), so the static getter fills a void*
    // pointing at the array object, which we then hex-dump in the trace.
    fh_WeightsIdentical    = fieldHandleFor(s_klass_Manager, "WEIGHTS_IDENTICAL_SYMBOLS");
    fh_WeightsNonIdentical = fieldHandleFor(s_klass_Manager, "WEIGHTS_NON_IDENTICAL_SYMBOLS");
    if (!fh_WeightsIdentical) {
        NSLog(@"[SpinLogger] WARNING: WEIGHTS_IDENTICAL_SYMBOLS not found on Manager");
    }
    if (!fh_WeightsNonIdentical) {
        NSLog(@"[SpinLogger] WARNING: WEIGHTS_NON_IDENTICAL_SYMBOLS not found on Manager");
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

    // Follow BoardManager (and try Board3DManager fields too — they may share
    // a base class, or m_BoardManager may actually point at a Board3DManager
    // instance. We dump both sets and let the Python decoder compare.)
    void *board = readPtr(inst, fo_boardManager);
    if (looksLikeHeapPointer(board)) {
        if (s_klass_BoardMgr) {
            NSString *key = [NSString stringWithFormat:@"BoardManager@0x%lx",
                             (unsigned long)board];
            fields[key] = dumpClassFields(s_klass_BoardMgr, board);
        }
        if (s_klass_Board3D) {
            NSString *key = [NSString stringWithFormat:@"Board3DManager@0x%lx",
                             (unsigned long)board];
            fields[key] = dumpClassFields(s_klass_Board3D, board);
        }
    }

    // Scanner v2 — walk each bar's m_SymbolReplacer → SlotBarSymbolReplacer.
    // This is the active replacement map that explains reel 1/3 ambiguity.
    if (s_klass_BarRepl && fo_symbolReplacer) {
        for (int i = 0; i < 3; i++) {
            if (!looksLikeHeapPointer(bars[i])) continue;
            void *repl = readPtr(bars[i], fo_symbolReplacer);
            if (!looksLikeHeapPointer(repl)) continue;
            NSString *key = [NSString stringWithFormat:
                             @"SlotBarSymbolReplacer_%d@0x%lx",
                             i + 1, (unsigned long)repl];
            fields[key] = dumpClassFields(s_klass_BarRepl, repl);
        }
    }

    // Scanner v2 — DynamicSlotResults target object
    if (fo_dynamicResults) {
        void *dyn = readPtr(inst, fo_dynamicResults);
        if (looksLikeHeapPointer(dyn)) {
            // Dump first 128 bytes as hex; we don't know the class yet.
            // Python can inspect via the hex section below.
            fields[[NSString stringWithFormat:@"DynamicSlotResults@0x%lx", (unsigned long)dyn]] =
                @{ @"ptr": [NSString stringWithFormat:@"0x%lx", (unsigned long)dyn] };
        }
    }

    // Scanner v2 — FreezeResolveContext target object
    if (fo_freezeCtx) {
        void *frz = readPtr(inst, fo_freezeCtx);
        if (looksLikeHeapPointer(frz)) {
            fields[[NSString stringWithFormat:@"FreezeResolveContext@0x%lx", (unsigned long)frz]] =
                @{ @"ptr": [NSString stringWithFormat:@"0x%lx", (unsigned long)frz] };
        }
    }

    // Scanner v2 — SpecialEventsContainers target object
    if (fo_specialEvents) {
        void *sp = readPtr(inst, fo_specialEvents);
        if (looksLikeHeapPointer(sp)) {
            fields[[NSString stringWithFormat:@"SpecialEventsContainers@0x%lx", (unsigned long)sp]] =
                @{ @"ptr": [NSString stringWithFormat:@"0x%lx", (unsigned long)sp] };
        }
    }

    // Scanner v2 — SlotSymbolReplacementService singleton
    if (s_klass_ReplSvc && fh_ReplSvcInstance && _field_static_get_value) {
        void *svc = NULL;
        _field_static_get_value(fh_ReplSvcInstance, &svc);
        if (looksLikeHeapPointer(svc)) {
            NSString *key = [NSString stringWithFormat:@"SlotSymbolReplacementService@0x%lx",
                             (unsigned long)svc];
            fields[key] = dumpClassFields(s_klass_ReplSvc, svc);
        }
    }

    // Scanner v2 — walk m_WinBehaviours → WinBehaviourComposite → inner list.
    // This is the path to m_Scenario on ScenarioSlotMachineWinBehaviour.
    if (fo_winBehaviours) {
        void *winBhv = readPtr(inst, fo_winBehaviours);
        if (looksLikeHeapPointer(winBhv)) {
            if (s_klass_WinComp) {
                NSString *key = [NSString stringWithFormat:
                                 @"SlotMachineWinBehaviourComposite@0x%lx",
                                 (unsigned long)winBhv];
                fields[key] = dumpClassFields(s_klass_WinComp, winBhv);

                // Walk the Composite's inner m_WinBehaviours list.
                // C# List<T> has: _items (array ref), _size (int32).
                // We try reading _items first, then fall back to m_WinBehaviours
                // as a direct array reference.
                if (fo_compWinBehaviours) {
                    void *innerList = readPtr(winBhv, fo_compWinBehaviours);
                    if (looksLikeHeapPointer(innerList)) {
                        // Could be a List<T> object — read _items at +16, _size at +24
                        void *items = readPtr(innerList, 16);
                        int32_t listSize = readInt32(innerList, 24);
                        if (looksLikeHeapPointer(items) && listSize > 0 && listSize < 64) {
                            for (int32_t bi = 0; bi < listSize && bi < 16; bi++) {
                                void *bhvItem = arrayElementPtr(items, bi);
                                if (!looksLikeHeapPointer(bhvItem)) continue;
                                if (s_klass_ScenBhv) {
                                    NSString *sk = [NSString stringWithFormat:
                                                    @"ScenarioWinBehaviour[%d]@0x%lx",
                                                    bi, (unsigned long)bhvItem];
                                    fields[sk] = dumpClassFields(s_klass_ScenBhv, bhvItem);
                                }
                            }
                        }
                        // Also try treating innerList itself as an array
                        for (int32_t bi = 0; bi < 8; bi++) {
                            void *bhvItem = arrayElementPtr(innerList, bi);
                            if (!looksLikeHeapPointer(bhvItem)) continue;
                            if (s_klass_ScenBhv) {
                                NSString *sk = [NSString stringWithFormat:
                                                @"ScenarioWinBehaviourDirect[%d]@0x%lx",
                                                bi, (unsigned long)bhvItem];
                                fields[sk] = dumpClassFields(s_klass_ScenBhv, bhvItem);
                            }
                        }
                    }
                }
            }
            // Also try dumping as ScenarioBhv directly (in case WinBehaviours
            // points at a single ScenarioWinBehaviour, not a Composite)
            if (s_klass_ScenBhv) {
                NSString *key = [NSString stringWithFormat:
                                 @"ScenarioSlotMachineWinBehaviour@0x%lx",
                                 (unsigned long)winBhv];
                fields[key] = dumpClassFields(s_klass_ScenBhv, winBhv);
            }
        }
    }

    // Scanner v2 — PvpBaseCompetitorSlotsController and BaseSlotSymbolController
    // are not yet reachable via a known pointer chain from Manager. Record the
    // class metadata (presence + resolved field offset) so the analysis side
    // knows whether the scanner saw the class at startup.
    if (s_klass_PvpSlots) {
        fields[@"PvpBaseCompetitorSlotsController"] = @{
            @"klass_ptr": [NSString stringWithFormat:@"%p", s_klass_PvpSlots],
            @"off_m_Random": @(fo_pvpRandom),
            @"instance": @"none_reachable_from_manager"
        };
    }
    if (s_klass_BaseSymCtrl) {
        fields[@"BaseSlotSymbolController"] = @{
            @"klass_ptr": [NSString stringWithFormat:@"%p", s_klass_BaseSymCtrl],
            @"off_m_SlotMachineManager": @(fo_baseSymMgrRef),
            @"instance": @"none_reachable_from_manager"
        };
    }

    // Diagnostic: record which v2 classes were NOT found so we can debug
    NSMutableArray *missingClasses = [NSMutableArray array];
    if (!s_klass_Board3D)    [missingClasses addObject:@"Board3DManager"];
    if (!s_klass_ReplSvc)    [missingClasses addObject:@"SlotSymbolReplacementService"];
    if (!s_klass_BarRepl)    [missingClasses addObject:@"SlotBarSymbolReplacer"];
    if (!s_klass_WinComp)    [missingClasses addObject:@"SlotMachineWinBehaviourComposite"];
    if (!s_klass_ScenBhv)    [missingClasses addObject:@"ScenarioSlotMachineWinBehaviour"];
    if (!s_klass_DataProv)   [missingClasses addObject:@"SlotDataProvider"];
    if (!s_klass_PvpSlots)   [missingClasses addObject:@"PvpBaseCompetitorSlotsController"];
    if (!s_klass_BaseSymCtrl)[missingClasses addObject:@"BaseSlotSymbolController"];
    if (missingClasses.count > 0) {
        rec[@"v2_missing_classes"] = missingClasses;
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

    // Scanner v2 — hex dump of each bar's SlotBarSymbolReplacer (m_Replacements dict)
    if (fo_symbolReplacer) {
        for (int i = 0; i < 3; i++) {
            if (!looksLikeHeapPointer(bars[i])) continue;
            void *repl = readPtr(bars[i], fo_symbolReplacer);
            if (!looksLikeHeapPointer(repl)) continue;
            NSString *key = [NSString stringWithFormat:@"slotBar%d.SymbolReplacer@0x%lx",
                             i + 1, (unsigned long)repl];
            hex[key] = hexString(repl, 256);

            if (fo_replMap) {
                void *replDict = readPtr(repl, fo_replMap);
                if (looksLikeHeapPointer(replDict)) {
                    NSString *dk = [NSString stringWithFormat:
                                    @"slotBar%d.m_Replacements@0x%lx",
                                    i + 1, (unsigned long)replDict];
                    hex[dk] = hexString(replDict, 512);
                }
            }
        }
    }

    // Scanner v2 — raw bytes at each bar's slotObjects array (GameObject[] —
    // alternative strip access path if m_SymbolElements decode is still flaky).
    if (fo_slotObjects) {
        for (int i = 0; i < 3; i++) {
            if (!looksLikeHeapPointer(bars[i])) continue;
            void *so = readPtr(bars[i], fo_slotObjects);
            if (!looksLikeHeapPointer(so)) continue;
            uint8_t *e = (uint8_t *)so;
            uint64_t len_at16 = *(uint64_t *)(e + 16);
            uint64_t len_at20 = *(uint32_t *)(e + 20);
            uint64_t len_at24 = *(uint64_t *)(e + 24);
            NSString *key = [NSString stringWithFormat:@"slotBar%d.slotObjects@0x%lx",
                             i + 1, (unsigned long)so];
            hex[key] = @{
                @"candidate_len_at16": @(len_at16),
                @"candidate_len_at20": @(len_at20),
                @"candidate_len_at24": @(len_at24),
                @"dump_bytes": @(kSLTraceHexArrayMaxBytes),
                @"bytes": hexString(so, kSLTraceHexArrayMaxBytes)
            };
        }
    }

    // Raw bytes at each bar's m_SymbolElements array payload.
    //
    // v2 change: the old length-gate (`len <= 0 || len > 256`) rejected every
    // array because kArrayHeaderSize/kArrayLengthOffset are wrong for this
    // Coin Master IL2CPP build. Instead, dump a fixed-size window
    // (kSLTraceHexArrayMaxBytes) at the element pointer and let the Python
    // decoder search for the correct header layout offline. Report three
    // candidate length reads (at +16, +20, +24) so the decoder can pick.
    for (int i = 0; i < 3; i++) {
        if (!looksLikeHeapPointer(bars[i])) continue;
        void *elements = readPtr(bars[i], fo_symbolElements);
        if (!looksLikeHeapPointer(elements)) continue;
        uint8_t *e = (uint8_t *)elements;
        uint64_t len_at16 = *(uint64_t *)(e + 16);
        uint64_t len_at20 = *(uint32_t *)(e + 20);
        uint64_t len_at24 = *(uint64_t *)(e + 24);
        NSString *key = [NSString stringWithFormat:@"slotBar%d.m_SymbolElements@0x%lx",
                         i + 1, (unsigned long)elements];
        hex[key] = @{
            @"candidate_len_at16": @(len_at16),
            @"candidate_len_at20": @(len_at20),
            @"candidate_len_at24": @(len_at24),
            @"dump_bytes": @(kSLTraceHexArrayMaxBytes),
            @"bytes": hexString(elements, kSLTraceHexArrayMaxBytes)
        };
    }

    // Raw bytes at currentSlotResult
    if (looksLikeHeapPointer(slotResult)) {
        NSString *key = [NSString stringWithFormat:@"currentSlotResult@0x%lx",
                         (unsigned long)slotResult];
        hex[key] = hexString(slotResult, kSLTraceHexWindowResult);
    }

    // Scanner v2 — raw hex windows on Manager pointer targets so Python can
    // decode the class-of-unknown-layout without forcing the scanner to know it.
    {
        void *dyn = fo_dynamicResults ? readPtr(inst, fo_dynamicResults) : NULL;
        if (looksLikeHeapPointer(dyn)) {
            NSString *key = [NSString stringWithFormat:@"DynamicSlotResults@0x%lx",
                             (unsigned long)dyn];
            hex[key] = hexString(dyn, 256);
        }
        void *frz = fo_freezeCtx ? readPtr(inst, fo_freezeCtx) : NULL;
        if (looksLikeHeapPointer(frz)) {
            NSString *key = [NSString stringWithFormat:@"FreezeResolveContext@0x%lx",
                             (unsigned long)frz];
            hex[key] = hexString(frz, 256);
        }
        void *sp = fo_specialEvents ? readPtr(inst, fo_specialEvents) : NULL;
        if (looksLikeHeapPointer(sp)) {
            NSString *key = [NSString stringWithFormat:@"SpecialEventsContainers@0x%lx",
                             (unsigned long)sp];
            hex[key] = hexString(sp, 256);
        }
        // BoardManager/Board3DManager — dump a wider hex window so Python can
        // decode either class layout.
        if (looksLikeHeapPointer(board)) {
            NSString *key = [NSString stringWithFormat:@"BoardManager@0x%lx",
                             (unsigned long)board];
            hex[key] = hexString(board, 512);
        }
    }

    // Scanner v2 — m_WinBehaviours and inner list hex windows
    if (fo_winBehaviours) {
        void *winBhv = readPtr(inst, fo_winBehaviours);
        if (looksLikeHeapPointer(winBhv)) {
            NSString *key = [NSString stringWithFormat:@"WinBehaviours@0x%lx",
                             (unsigned long)winBhv];
            hex[key] = hexString(winBhv, 512);

            if (s_klass_WinComp && fo_compWinBehaviours) {
                void *innerList = readPtr(winBhv, fo_compWinBehaviours);
                if (looksLikeHeapPointer(innerList)) {
                    NSString *lk = [NSString stringWithFormat:
                                    @"WinBehaviours.innerList@0x%lx",
                                    (unsigned long)innerList];
                    hex[lk] = hexString(innerList, 512);
                }
            }
        }
    }

    // Scanner v2 — static weight tables on SlotMachineManager.
    // Each is an int[] stored as a managed-array pointer in a static field.
    // Read the pointer via field_static_get_value, then hex-dump ~256B at
    // the array object so Python can pull out the length + int32 elements.
    if (_field_static_get_value) {
        if (fh_WeightsIdentical) {
            void *arr = NULL;
            _field_static_get_value(fh_WeightsIdentical, &arr);
            if (looksLikeHeapPointer(arr)) {
                uint8_t *e = (uint8_t *)arr;
                uint64_t len_at16 = *(uint64_t *)(e + 16);
                uint64_t len_at20 = *(uint32_t *)(e + 20);
                uint64_t len_at24 = *(uint64_t *)(e + 24);
                NSString *key = [NSString stringWithFormat:
                                 @"WEIGHTS_IDENTICAL_SYMBOLS@0x%lx",
                                 (unsigned long)arr];
                hex[key] = @{
                    @"candidate_len_at16": @(len_at16),
                    @"candidate_len_at20": @(len_at20),
                    @"candidate_len_at24": @(len_at24),
                    @"dump_bytes": @(256),
                    @"bytes": hexString(arr, 256)
                };
            }
        }
        if (fh_WeightsNonIdentical) {
            void *arr = NULL;
            _field_static_get_value(fh_WeightsNonIdentical, &arr);
            if (looksLikeHeapPointer(arr)) {
                uint8_t *e = (uint8_t *)arr;
                uint64_t len_at16 = *(uint64_t *)(e + 16);
                uint64_t len_at20 = *(uint32_t *)(e + 20);
                uint64_t len_at24 = *(uint64_t *)(e + 24);
                NSString *key = [NSString stringWithFormat:
                                 @"WEIGHTS_NON_IDENTICAL_SYMBOLS@0x%lx",
                                 (unsigned long)arr];
                hex[key] = @{
                    @"candidate_len_at16": @(len_at16),
                    @"candidate_len_at20": @(len_at20),
                    @"candidate_len_at24": @(len_at24),
                    @"dump_bytes": @(256),
                    @"bytes": hexString(arr, 256)
                };
            }
        }
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

    // Track spin-end — read idx from bars and settle strategy engine
    BOOL isSpinning = (readBool(instance, fo_spinning) != 0);
    BOOL spinEnded = (self.prevSpinning && !isSpinning);
    self.prevSpinning = isSpinning;
    if (spinEnded) self.spinsSeen++;

    if (spinEnded) {
        // Read strip idx from each bar's resultSymbolIndex
        void *bar1 = readPtr(instance, fo_slotBar1);
        void *bar2 = readPtr(instance, fo_slotBar2);
        void *bar3 = readPtr(instance, fo_slotBar3);

        int32_t idx1 = (bar1 && fo_resultSymbolIndex) ? readInt32(bar1, fo_resultSymbolIndex) : -1;
        int32_t idx2 = (bar2 && fo_resultSymbolIndex) ? readInt32(bar2, fo_resultSymbolIndex) : -1;
        int32_t idx3 = (bar3 && fo_resultSymbolIndex) ? readInt32(bar3, fo_resultSymbolIndex) : -1;

        // Populate snapshot with idx
        SLScanSnapshot *snap = [[SLScanSnapshot alloc] init];
        snap.timestamp = [NSDate date];
        snap.spinNumber = readInt32(instance, fo_currentSpinNumber);
        snap.betState = readInt32(instance, fo_betState);
        snap.spinning = isSpinning;
        snap.stripIdx1 = idx1;
        snap.stripIdx2 = idx2;
        snap.stripIdx3 = idx3;
        self.latestSnapshot = snap;

        // Settle pending result on main thread (triggers CSV write + strategy compute)
        dispatch_async(dispatch_get_main_queue(), ^{
            [[SLIdxStrategy shared] settlePendingWithR1Idx:idx1 r2Idx:idx2 r3Idx:idx3];
        });

        NSLog(@"[SpinLogger] Spin settled: idx=(%d, %d, %d)", idx1, idx2, idx3);
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
