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
@property (nonatomic, assign) int32_t prevSpinNumber;
@property (nonatomic, strong, readwrite) SLScanSnapshot *latestSnapshot;

@property (nonatomic, assign) int64_t spinsSeen;
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
    self.prevSpinNumber = 0;
    self.currentPhaseName = @"resolveAPIs";

    self.scanTimer = [NSTimer scheduledTimerWithTimeInterval:0.08
                                                     target:self
                                                   selector:@selector(tick)
                                                   userInfo:nil
                                                    repeats:YES];
    NSLog(@"[SpinLogger] Memory scanner started");
}

- (void)stopScanning {
    [self.scanTimer invalidate];
    self.scanTimer = nil;
    NSLog(@"[SpinLogger] Memory scanner stopped. %lld spins seen.", self.spinsSeen);
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

    // Track spin-end — read idx from bars and settle strategy engine
    BOOL isSpinning = (readBool(instance, fo_spinning) != 0);
    BOOL spinEnded = (self.prevSpinning && !isSpinning);
    self.prevSpinning = isSpinning;

    // Fallback: during autospin the spinning flag may never appear as NO
    // (transitions faster than our 250ms poll). Detect via spin number change.
    int32_t spinNum = readInt32(instance, fo_currentSpinNumber);
    if (!spinEnded && self.prevSpinNumber > 0 && spinNum != self.prevSpinNumber) {
        spinEnded = YES;
    }
    self.prevSpinNumber = spinNum;

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
}

@end
