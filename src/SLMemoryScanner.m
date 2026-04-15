#import "SLMemoryScanner.h"
#import "SLIdxStrategy.h"
#import "SLConstants.h"
#include <dlfcn.h>
#include <string.h>
#include <mach/mach_time.h>
#include <mach/mach.h>

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
typedef int         (*fn_class_array_element_size)(void* klass);
typedef unsigned    (*fn_class_instance_size)(void* klass);

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
static fn_class_array_element_size   _class_array_element_size;
static fn_class_instance_size        _class_instance_size;

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

// Scanner v3 — comprehensive diagnostic classes
static void* s_klass_SymMgr      = NULL;  // SlotMachine.SymbolManager (per-reel state)
static void* s_klass_SlotMgr     = NULL;  // SlotMachine.SlotManager (secondary bar refs)
static void* s_klass_ErrResults   = NULL;  // SlotMachine.SlotMachineErrorResults
static void* s_klass_SpinAnimSpd  = NULL;  // SlotMachineSpinAnimationSpeed
static void* s_klass_AddSlotsSvc  = NULL;  // AdditionalSlotsService
static void* s_klass_SecondSlotCtrl = NULL; // SecondSlotSymbolController
static void* s_klass_FreeSpinsReels = NULL; // FreeSpinsReelsHandler
static void* s_klass_SlotSymToWS   = NULL;  // SlotSymbolToWeightedScenario

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

// SlotResult — slotSymbols is a REFERENCE to SlotSymbol3 object
static size_t fo_slotSymbols         = 0;
static size_t fo_barSymbols          = 0;      // barSymbols (SlotSymbol[] on Manager)

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
static int    s_barSymInfoElemSize   = 0;      // array element size for value-type arrays

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

// Scanner v3 — new field offsets/handles
// SlotResult — win field
static size_t fo_slotResultWin       = 0;      // win (int32)

// SlotMachine.SymbolManager — per-reel spin state
static size_t fo_smResultSymIdx      = 0;      // <ResultSymbolIndex>k__BackingField
static size_t fo_smSpinning          = 0;      // spinning
static size_t fo_smEndSpinning       = 0;      // endSpinning
static size_t fo_smReadyToStop       = 0;      // readyToStop
static size_t fo_smEndAnimating      = 0;      // endAnimating

// SlotMachine.SlotMachineErrorResults
static void*  fh_ErrSlotSymbols      = NULL;   // <SlotSymbolsOnError>k__BackingField (static)

// SlotMachineManager — additional fields
static size_t fo_lastResult          = 0;      // lastResult (SlotResult)
static size_t fo_isReadyToProcess    = 0;      // isReadyToProcessSpinResult
static size_t fo_spinAnimEnded       = 0;      // spinAnimationEnded
static size_t fo_spinButtonState     = 0;      // spinButtonState

// SlotMachine.SlotMachineSpinAnimationSpeed
static size_t fo_spinSpeedMult       = 0;      // m_SpinAnimationSpeedMultiplier
static size_t fo_spinSpeedMultAuto   = 0;      // m_SpinAnimationSpeedMultiplierAutoSpin

// SecondSlotSymbolController — second slot results
static size_t fo_secSlotSpinResult   = 0;      // m_SecondSlotSpinResult
static size_t fo_secSlotResultSeq    = 0;      // m_ResultSeq

// One-shot diagnostic flag
static BOOL s_diagDumped = NO;

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

/// Safely test if `size` bytes starting at `addr` are readable.
/// Uses vm_read_overwrite to avoid SIGSEGV on unmapped memory.
static inline BOOL safeReadable(const void *addr, size_t size) {
    if (!addr) return NO;
    vm_size_t outSize = 0;
    uint8_t buf[64];  // small stack buffer — only used for the probe
    if (size > sizeof(buf)) size = sizeof(buf);
    kern_return_t kr = vm_read_overwrite(
        mach_task_self(),
        (vm_address_t)addr,
        (vm_size_t)size,
        (vm_address_t)buf,
        &outSize
    );
    return (kr == KERN_SUCCESS && outSize >= size);
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
@property (nonatomic, assign) int32_t lastSettledSpinNum;
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
    RESOLVE(class_array_element_size);
    RESOLVE(class_instance_size);
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
            // Scanner v3 — comprehensive diagnostic classes
            else if (strcmp(name, "SymbolManager") == 0 && strcmp(ns, "SlotMachine") == 0)
                s_klass_SymMgr = klass;
            else if (strcmp(name, "SlotManager") == 0 && strcmp(ns, "SlotMachine") == 0)
                s_klass_SlotMgr = klass;
            else if (strcmp(name, "SlotMachineErrorResults") == 0 && strcmp(ns, "SlotMachine") == 0)
                s_klass_ErrResults = klass;
            else if (strcmp(name, "SlotMachineSpinAnimationSpeed") == 0 && !s_klass_SpinAnimSpd)
                s_klass_SpinAnimSpd = klass;
            else if (strcmp(name, "AdditionalSlotsService") == 0 && !s_klass_AddSlotsSvc)
                s_klass_AddSlotsSvc = klass;
            else if (strcmp(name, "SecondSlotSymbolController") == 0 && !s_klass_SecondSlotCtrl)
                s_klass_SecondSlotCtrl = klass;
            else if (strcmp(name, "FreeSpinsReelsHandler") == 0 && !s_klass_FreeSpinsReels)
                s_klass_FreeSpinsReels = klass;
            else if (strcmp(name, "SlotSymbolToWeightedScenario") == 0 && !s_klass_SlotSymToWS)
                s_klass_SlotSymToWS = klass;
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
        NSLog(@"[SpinLogger] v3 classes:  SymMgr=%p SlotMgr=%p ErrRes=%p SpinSpd=%p AddSlots=%p SecSlot=%p FreeSpin=%p SymToWS=%p",
              s_klass_SymMgr, s_klass_SlotMgr, s_klass_ErrResults, s_klass_SpinAnimSpd,
              s_klass_AddSlotsSvc, s_klass_SecondSlotCtrl, s_klass_FreeSpinsReels, s_klass_SlotSymToWS);
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
    fo_barSymbols        = offsetFor(s_klass_Manager, "barSymbols",                   "SlotMachineManager");
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
        // Get element size for value-type arrays
        if (_class_array_element_size) {
            s_barSymInfoElemSize = _class_array_element_size(s_klass_BarSymInfo);
            NSLog(@"[SpinLogger] BarSymInfo: elemSize=%d backingOff=%zu", s_barSymInfoElemSize, fo_slotSymbolBacking);
        }
        if (s_barSymInfoElemSize <= 0 && _class_instance_size) {
            // Fallback: instance_size includes object header (16 bytes on arm64)
            unsigned isize = _class_instance_size(s_klass_BarSymInfo);
            s_barSymInfoElemSize = (int)(isize > 16 ? isize - 16 : isize);
            NSLog(@"[SpinLogger] BarSymInfo: instanceSize=%u -> elemSize=%d", isize, s_barSymInfoElemSize);
        }
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

    // Scanner v3 — SlotResult.win
    fo_slotResultWin = offsetFor(s_klass_Result, "win", "SlotResult");

    // Scanner v3 — additional Manager fields
    fo_lastResult        = offsetFor(s_klass_Manager, "lastResult",                   "SlotMachineManager");
    fo_isReadyToProcess  = offsetFor(s_klass_Manager, "isReadyToProcessSpinResult",   "SlotMachineManager");
    fo_spinAnimEnded     = offsetFor(s_klass_Manager, "spinAnimationEnded",           "SlotMachineManager");
    fo_spinButtonState   = offsetFor(s_klass_Manager, "spinButtonState",              "SlotMachineManager");

    // Scanner v3 — SymbolManager (per-reel state machine)
    if (s_klass_SymMgr) {
        fo_smResultSymIdx = offsetFor(s_klass_SymMgr, "<ResultSymbolIndex>k__BackingField", "SymbolManager");
        fo_smSpinning     = offsetFor(s_klass_SymMgr, "spinning",      "SymbolManager");
        fo_smEndSpinning  = offsetFor(s_klass_SymMgr, "endSpinning",   "SymbolManager");
        fo_smReadyToStop  = offsetFor(s_klass_SymMgr, "readyToStop",   "SymbolManager");
        fo_smEndAnimating = offsetFor(s_klass_SymMgr, "endAnimating",  "SymbolManager");
    }

    // Scanner v3 — SlotMachineErrorResults (static fallback symbols)
    if (s_klass_ErrResults) {
        fh_ErrSlotSymbols = fieldHandleFor(s_klass_ErrResults,
                                           "<SlotSymbolsOnError>k__BackingField");
        if (_runtime_class_init) _runtime_class_init(s_klass_ErrResults);
    }

    // Scanner v3 — SlotMachineSpinAnimationSpeed
    if (s_klass_SpinAnimSpd) {
        fo_spinSpeedMult     = offsetFor(s_klass_SpinAnimSpd,
                                         "m_SpinAnimationSpeedMultiplier",          "SpinAnimSpeed");
        fo_spinSpeedMultAuto = offsetFor(s_klass_SpinAnimSpd,
                                         "m_SpinAnimationSpeedMultiplierAutoSpin",  "SpinAnimSpeed");
    }

    // Scanner v3 — SecondSlotSymbolController
    if (s_klass_SecondSlotCtrl) {
        fo_secSlotSpinResult = offsetFor(s_klass_SecondSlotCtrl,
                                         "m_SecondSlotSpinResult",  "SecondSlotSymbolCtrl");
        fo_secSlotResultSeq  = offsetFor(s_klass_SecondSlotCtrl,
                                         "m_ResultSeq",            "SecondSlotSymbolCtrl");
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
    NSLog(@"[SpinLogger] STRIP DIAG: fo_symbolElements=%zu fo_slotSymbolBacking=%zu "
          "fo_symbolReplacer=%zu fo_replMap=%zu fo_numberOfSymbols=%zu "
          "BarSymInfo=%p BarRepl=%p",
          fo_symbolElements, fo_slotSymbolBacking,
          fo_symbolReplacer, fo_replMap, fo_numberOfSymbols,
          s_klass_BarSymInfo, s_klass_BarRepl);
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
//  Strip reading helpers
// ============================================================

/// Read array length as int32 (this Unity build uses uint32 for il2cpp_array_size_t)
static inline int32_t arrayLength32(void *array) {
    if (!array) return 0;
    return *(int32_t *)((uint8_t *)array + kArrayLengthOffset);
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
    int32_t spinNum = readInt32(instance, fo_currentSpinNumber);

    BOOL spinEnded = NO;

    // Primary: spinning YES → NO (authoritative — reels have stopped)
    if (self.prevSpinning && !isSpinning) {
        spinEnded = YES;
    }

    // Fallback: spinNum changed — covers autospin where spinning
    // transitions faster than our 250ms poll.
    // BUT: skip when a manual spin is just starting (prevSpinning=NO,
    // isSpinning=YES). At that point reels are still animating and
    // resultSymbolIndex holds stale/intermediate values.
    if (!spinEnded && self.prevSpinNumber > 0 && spinNum != self.prevSpinNumber) {
        BOOL spinJustStarted = (!self.prevSpinning && isSpinning);
        if (!spinJustStarted) {
            spinEnded = YES;
        }
    }

    self.prevSpinning = isSpinning;
    self.prevSpinNumber = spinNum;

    // Guard: never double-settle the same spin number
    if (spinEnded && spinNum == self.lastSettledSpinNum) {
        spinEnded = NO;
    }

    if (spinEnded) {
        self.lastSettledSpinNum = spinNum;
        self.spinsSeen++;
    }

    if (spinEnded) {
        // Read strip idx from each bar's resultSymbolIndex
        void *bar1 = readPtr(instance, fo_slotBar1);
        void *bar2 = readPtr(instance, fo_slotBar2);
        void *bar3 = readPtr(instance, fo_slotBar3);

        int32_t idx1 = (bar1 && fo_resultSymbolIndex) ? readInt32(bar1, fo_resultSymbolIndex) : -1;
        int32_t idx2 = (bar2 && fo_resultSymbolIndex) ? readInt32(bar2, fo_resultSymbolIndex) : -1;
        int32_t idx3 = (bar3 && fo_resultSymbolIndex) ? readInt32(bar3, fo_resultSymbolIndex) : -1;

        // ══════════════════════════════════════════════════════════
        //  ONE-SHOT COMPREHENSIVE DIAGNOSTIC (first spin only)
        // ══════════════════════════════════════════════════════════
        if (!s_diagDumped) {
            s_diagDumped = YES;
            NSLog(@"[SpinLogger] ═══ COMPREHENSIVE DIAGNOSTIC DUMP ═══");

            // §1 — Weight tables (WEIGHTS_IDENTICAL / NON_IDENTICAL)
            if (fh_WeightsIdentical && _field_static_get_value) {
                void *wIdent = NULL;
                _field_static_get_value(fh_WeightsIdentical, &wIdent);
                if (wIdent && looksLikeHeapPointer(wIdent)
                    && safeReadable(wIdent, kArrayHeaderSize + 4)) {
                    int32_t wLen = arrayLength32(wIdent);
                    NSMutableString *ws = [NSMutableString stringWithFormat:
                                           @"WEIGHTS_IDENT[%d]:", wLen];
                    uint8_t *wData = (uint8_t *)wIdent + kArrayHeaderSize;
                    int wRead = (wLen > 30) ? 30 : wLen;
                    if (safeReadable(wData, (size_t)wRead * 4)) {
                        for (int w = 0; w < wRead; w++)
                            [ws appendFormat:@" %d", *(int32_t *)(wData + w * 4)];
                    }
                    NSLog(@"[SpinLogger] %@", ws);
                } else {
                    NSLog(@"[SpinLogger] WEIGHTS_IDENT: unreadable (ptr=%p)", wIdent);
                }
            }
            if (fh_WeightsNonIdentical && _field_static_get_value) {
                void *wNon = NULL;
                _field_static_get_value(fh_WeightsNonIdentical, &wNon);
                if (wNon && looksLikeHeapPointer(wNon)
                    && safeReadable(wNon, kArrayHeaderSize + 4)) {
                    int32_t wLen = arrayLength32(wNon);
                    NSMutableString *ws = [NSMutableString stringWithFormat:
                                           @"WEIGHTS_NON_IDENT[%d]:", wLen];
                    uint8_t *wData = (uint8_t *)wNon + kArrayHeaderSize;
                    int wRead = (wLen > 30) ? 30 : wLen;
                    if (safeReadable(wData, (size_t)wRead * 4)) {
                        for (int w = 0; w < wRead; w++)
                            [ws appendFormat:@" %d", *(int32_t *)(wData + w * 4)];
                    }
                    NSLog(@"[SpinLogger] %@", ws);
                } else {
                    NSLog(@"[SpinLogger] WEIGHTS_NON_IDENT: unreadable (ptr=%p)", wNon);
                }
            }

            // §2 — SlotMachineErrorResults.SlotSymbolsOnError (fallback symbols)
            if (fh_ErrSlotSymbols && _field_static_get_value) {
                void *errSyms = NULL;
                _field_static_get_value(fh_ErrSlotSymbols, &errSyms);
                if (errSyms && looksLikeHeapPointer(errSyms)
                    && safeReadable(errSyms, kArrayHeaderSize + 4)) {
                    int32_t eLen = arrayLength32(errSyms);
                    NSMutableString *es = [NSMutableString stringWithFormat:
                                            @"ErrorFallbackSymbols[%d]:", eLen];
                    uint8_t *eData = (uint8_t *)errSyms + kArrayHeaderSize;
                    int eRead = (eLen > 10) ? 10 : eLen;
                    if (safeReadable(eData, (size_t)eRead * 4)) {
                        for (int e = 0; e < eRead; e++)
                            [es appendFormat:@" %d", *(int32_t *)(eData + e * 4)];
                    }
                    NSLog(@"[SpinLogger] %@", es);
                } else {
                    NSLog(@"[SpinLogger] ErrorFallbackSymbols: %p (unreadable or NULL)", errSyms);
                }
            } else {
                NSLog(@"[SpinLogger] ErrorResults class: %s",
                      s_klass_ErrResults ? "found but no field handle" : "NOT FOUND");
            }

            // §3 — Manager state fields
            NSLog(@"[SpinLogger] Manager: isReadyToProcess=%d spinAnimEnded=%d spinBtnState=%d",
                  fo_isReadyToProcess ? readInt32(instance, fo_isReadyToProcess) : -1,
                  fo_spinAnimEnded    ? readInt32(instance, fo_spinAnimEnded) : -1,
                  fo_spinButtonState  ? readInt32(instance, fo_spinButtonState) : -1);

            // §4 — lastResult (previous spin's SlotResult — compare with currentSlotResult)
            if (fo_lastResult) {
                void *lastRes = readPtr(instance, fo_lastResult);
                if (lastRes && looksLikeHeapPointer(lastRes)
                    && fo_slotSymbols && safeReadable(lastRes, fo_slotSymbols + 8)) {
                    void *lrSym = readPtr(lastRes, fo_slotSymbols);
                    int32_t lrW = fo_slotResultWin ? readInt32(lastRes, fo_slotResultWin) : -1;
                    if (lrSym && looksLikeHeapPointer(lrSym)
                        && safeReadable(lrSym, fo_symbol3 + 4)) {
                        int32_t ls1 = *(int32_t *)((uint8_t *)lrSym + fo_symbol1);
                        int32_t ls2 = *(int32_t *)((uint8_t *)lrSym + fo_symbol2);
                        int32_t ls3 = *(int32_t *)((uint8_t *)lrSym + fo_symbol3);
                        NSLog(@"[SpinLogger] lastResult: sym=(%d,%d,%d) win=%d", ls1, ls2, ls3, lrW);
                    }
                } else {
                    NSLog(@"[SpinLogger] lastResult: NULL or unreadable");
                }
            }

            // §5 — Board3DManager: nearWinSymbol
            if (s_klass_Board3D && fo_nearWinSymbol && fo_boardManager) {
                void *boardMgr = readPtr(instance, fo_boardManager);
                if (boardMgr && looksLikeHeapPointer(boardMgr)) {
                    // Board3DManager is nested — try reading from BoardManager
                    // fo_nearWinSymbol is on Board3DManager, but we may have it on BoardManager
                    // Try direct read first
                    int32_t nws = readInt32(boardMgr, fo_nearWinSymbol);
                    NSLog(@"[SpinLogger] Board3D nearWinSymbol=%d (from boardMgr+%zu)", nws, fo_nearWinSymbol);
                }
            }

            // §6 — SpinAnimationSpeed (if the object is reachable from Manager)
            if (fo_animSpeedBacking) {
                void *animSpd = readPtr(instance, fo_animSpeedBacking);
                if (animSpd && looksLikeHeapPointer(animSpd) && s_klass_SpinAnimSpd) {
                    if (fo_spinSpeedMult && safeReadable(animSpd, fo_spinSpeedMult + 4)) {
                        // These are float fields
                        float spd = *(float *)((uint8_t *)animSpd + fo_spinSpeedMult);
                        float spdAuto = fo_spinSpeedMultAuto
                            ? *(float *)((uint8_t *)animSpd + fo_spinSpeedMultAuto) : -1.0f;
                        NSLog(@"[SpinLogger] SpinAnimSpeed: mult=%.3f autoMult=%.3f", spd, spdAuto);
                    }
                } else {
                    NSLog(@"[SpinLogger] SpinAnimSpeed: ptr=%p (animSpeedBacking)", animSpd);
                }
            }

            // §7 — SymbolManager per-reel state (via bar1/2/3)
            if (s_klass_SymMgr && fo_smSpinning) {
                void *bars[3] = {bar1, bar2, bar3};
                const char *names[3] = {"bar1", "bar2", "bar3"};
                for (int b = 0; b < 3; b++) {
                    if (!bars[b]) continue;
                    // SymbolManager is the component on the SlotBarManager game object
                    // SlotBarManager IS the SymbolManager in some builds, or it's a
                    // separate component. The fields we cached (fo_sm*) are SymbolManager
                    // offsets. SlotBarManager has the same fields (resultSymbolIndex etc.)
                    // but SymbolManager has the property-backed version.
                    // Try reading from the bar directly using SymbolManager offsets:
                    NSLog(@"[SpinLogger] %s: smSpinning=%d smEndSpin=%d smReady=%d smEndAnim=%d smResIdx=%d",
                          names[b],
                          fo_smSpinning     ? readInt32(bars[b], fo_smSpinning) : -1,
                          fo_smEndSpinning  ? readInt32(bars[b], fo_smEndSpinning) : -1,
                          fo_smReadyToStop  ? readInt32(bars[b], fo_smReadyToStop) : -1,
                          fo_smEndAnimating ? readInt32(bars[b], fo_smEndAnimating) : -1,
                          fo_smResultSymIdx ? readInt32(bars[b], fo_smResultSymIdx) : -1);
                }
            }

            // §8 — PvpBaseCompetitorSlotsController.m_Random
            if (s_klass_PvpSlots && fo_pvpRandom) {
                NSLog(@"[SpinLogger] PvpSlots: class=%p fo_pvpRandom=%zu (need instance to read)",
                      s_klass_PvpSlots, fo_pvpRandom);
            }

            // §9 — SlotSymbolToWeightedScenario (just log if found)
            NSLog(@"[SpinLogger] SlotSymbolToWeightedScenario: %s",
                  s_klass_SlotSymToWS ? "FOUND" : "not found");

            // §10 — FreeSpinsReelsHandler
            if (s_klass_FreeSpinsReels) {
                NSLog(@"[SpinLogger] FreeSpinsReelsHandler: FOUND (class=%p)", s_klass_FreeSpinsReels);
            }

            // §11 — Hex dump first 128 bytes of Manager instance (field layout discovery)
            if (safeReadable(instance, 128)) {
                NSMutableString *hex = [NSMutableString stringWithString:@"Manager hex[0..127]: "];
                uint8_t *p = (uint8_t *)instance;
                for (int h = 0; h < 128; h++) {
                    [hex appendFormat:@"%02x", p[h]];
                    if ((h & 7) == 7) [hex appendString:@" "];
                }
                NSLog(@"[SpinLogger] %@", hex);
            }

            // §12 — Enumerate all fields on resolved classes (once)
            void* diagClasses[] = {
                s_klass_Manager, s_klass_Result, s_klass_SymMgr,
                s_klass_ErrResults, s_klass_SpinAnimSpd, s_klass_SecondSlotCtrl,
                s_klass_SlotSymToWS, s_klass_AddSlotsSvc
            };
            const char* diagNames[] = {
                "SlotMachineManager", "SlotResult", "SymbolManager",
                "ErrorResults", "SpinAnimSpeed", "SecondSlotCtrl",
                "SymToWeightedScen", "AddSlotsService"
            };
            for (int ci = 0; ci < 8; ci++) {
                if (!diagClasses[ci] || !_class_get_fields || !_field_get_name || !_field_get_offset)
                    continue;
                NSMutableString *fields = [NSMutableString stringWithFormat:
                                            @"Fields[%s]:", diagNames[ci]];
                void *iter = NULL;
                void *field;
                int fc = 0;
                while ((field = _class_get_fields(diagClasses[ci], &iter)) && fc < 50) {
                    const char *fn = _field_get_name(field);
                    size_t off = _field_get_offset(field);
                    [fields appendFormat:@" %s@%zu", fn ? fn : "?", off];
                    fc++;
                }
                NSLog(@"[SpinLogger] %@", fields);
            }

            NSLog(@"[SpinLogger] ═══ END DIAGNOSTIC DUMP ═══");
        }

        // ══════════════════════════════════════════════════════════
        //  PER-SPIN READS (every spin)
        // ══════════════════════════════════════════════════════════

        // ── SlotResult.win (reward amount) ──────────────────────
        int32_t spinWin = 0;
        if (fo_currentSlotResult && fo_slotResultWin) {
            void *sr = readPtr(instance, fo_currentSlotResult);
            if (sr && looksLikeHeapPointer(sr) && safeReadable(sr, fo_slotResultWin + 4)) {
                spinWin = readInt32(sr, fo_slotResultWin);
            }
        }

        // ── DynamicSlotResults (pre-pushed future spins) ────────
        if (fo_dynamicResults) {
            void *dynResults = readPtr(instance, fo_dynamicResults);
            if (dynResults && looksLikeHeapPointer(dynResults)) {
                if (safeReadable(dynResults, kArrayHeaderSize + 8)) {
                    int32_t dynLen = arrayLength32(dynResults);
                    NSLog(@"[SpinLogger] DynSlotResults: ptr=%p arrLen=%d", dynResults, dynLen);
                    int readCount = (dynLen > 10) ? 10 : dynLen;
                    for (int d = 0; d < readCount; d++) {
                        void *dynSR = *(void **)((uint8_t *)dynResults + kArrayHeaderSize + d * 8);
                        if (dynSR && looksLikeHeapPointer(dynSR)
                            && fo_slotSymbols && fo_symbol1
                            && safeReadable(dynSR, fo_slotSymbols + 8)) {
                            void *dynSym3 = readPtr(dynSR, fo_slotSymbols);
                            int32_t dWin = fo_slotResultWin ? readInt32(dynSR, fo_slotResultWin) : -1;
                            if (dynSym3 && looksLikeHeapPointer(dynSym3)
                                && safeReadable(dynSym3, fo_symbol3 + 4)) {
                                int32_t ds1 = *(int32_t *)((uint8_t *)dynSym3 + fo_symbol1);
                                int32_t ds2 = *(int32_t *)((uint8_t *)dynSym3 + fo_symbol2);
                                int32_t ds3 = *(int32_t *)((uint8_t *)dynSym3 + fo_symbol3);
                                NSLog(@"[SpinLogger]   Dyn[%d]: sym=(%d,%d,%d) win=%d",
                                      d, ds1, ds2, ds3, dWin);
                            } else {
                                NSLog(@"[SpinLogger]   Dyn[%d]: sym3 unreadable (sr=%p)", d, dynSR);
                            }
                        } else if (d == 0) {
                            // Try List<T> layout: _items@16, _size@24
                            void *items = readPtr(dynResults, 16);
                            int32_t size = readInt32(dynResults, 24);
                            NSLog(@"[SpinLogger]   DynResults List<T>?: _items=%p _size=%d", items, size);
                            if (items && looksLikeHeapPointer(items) && size > 0
                                && safeReadable(items, kArrayHeaderSize + 8)) {
                                int32_t itemsLen = arrayLength32(items);
                                int listRead = (size > 10) ? 10 : size;
                                for (int li = 0; li < listRead; li++) {
                                    void *listSR = *(void **)((uint8_t *)items
                                                               + kArrayHeaderSize + li * 8);
                                    if (listSR && looksLikeHeapPointer(listSR)
                                        && fo_slotSymbols && safeReadable(listSR, fo_slotSymbols + 8)) {
                                        void *lSym3 = readPtr(listSR, fo_slotSymbols);
                                        int32_t lW = fo_slotResultWin ? readInt32(listSR, fo_slotResultWin) : -1;
                                        if (lSym3 && looksLikeHeapPointer(lSym3)
                                            && safeReadable(lSym3, fo_symbol3 + 4)) {
                                            int32_t ls1 = *(int32_t *)((uint8_t *)lSym3 + fo_symbol1);
                                            int32_t ls2 = *(int32_t *)((uint8_t *)lSym3 + fo_symbol2);
                                            int32_t ls3 = *(int32_t *)((uint8_t *)lSym3 + fo_symbol3);
                                            NSLog(@"[SpinLogger]   DynList[%d]: sym=(%d,%d,%d) win=%d",
                                                  li, ls1, ls2, ls3, lW);
                                        }
                                    }
                                }
                            }
                            break;
                        }
                    }
                } else {
                    NSLog(@"[SpinLogger] DynSlotResults: ptr=%p (unreadable)", dynResults);
                }
            } else {
                NSLog(@"[SpinLogger] DynSlotResults: NULL");
            }
        }

        // ── Weight tables (per-spin — detect drift) ─────────────
        // Only log compact summary, not full array
        if (fh_WeightsIdentical && _field_static_get_value) {
            void *wI = NULL;
            _field_static_get_value(fh_WeightsIdentical, &wI);
            void *wN = NULL;
            if (fh_WeightsNonIdentical)
                _field_static_get_value(fh_WeightsNonIdentical, &wN);
            // Log just pointer + first 3 values as drift sentinel
            if (wI && looksLikeHeapPointer(wI) && safeReadable(wI, kArrayHeaderSize + 12)) {
                uint8_t *d = (uint8_t *)wI + kArrayHeaderSize;
                int32_t v0 = *(int32_t *)(d), v1 = *(int32_t *)(d+4), v2 = *(int32_t *)(d+8);
                NSLog(@"[SpinLogger] W_ID ptr=%p head=[%d,%d,%d]", wI, v0, v1, v2);
            }
            if (wN && looksLikeHeapPointer(wN) && safeReadable(wN, kArrayHeaderSize + 12)) {
                uint8_t *d = (uint8_t *)wN + kArrayHeaderSize;
                int32_t v0 = *(int32_t *)(d), v1 = *(int32_t *)(d+4), v2 = *(int32_t *)(d+8);
                NSLog(@"[SpinLogger] W_NI ptr=%p head=[%d,%d,%d]", wN, v0, v1, v2);
            }
        }


        // Read strip lengths
        int32_t len1 = (bar1 && fo_numberOfSymbols) ? readInt32(bar1, fo_numberOfSymbols) : -1;
        int32_t len2 = (bar2 && fo_numberOfSymbols) ? readInt32(bar2, fo_numberOfSymbols) : -1;
        int32_t len3 = (bar3 && fo_numberOfSymbols) ? readInt32(bar3, fo_numberOfSymbols) : -1;

        // Read actual symbols via two independent methods:
        // Method 1: barSymbols — SlotSymbol[] array on Manager (3 elements = reel 1,2,3)
        int32_t memSym1 = -1, memSym2 = -1, memSym3 = -1;
        if (fo_barSymbols) {
            void *barSymArr = readPtr(instance, fo_barSymbols);
            if (barSymArr && looksLikeHeapPointer(barSymArr)
                && safeReadable(barSymArr, kArrayHeaderSize + 12)) {
                int32_t bsLen = arrayLength32(barSymArr);
                uint8_t *bsData = (uint8_t *)barSymArr + kArrayHeaderSize;
                if (bsLen >= 3 && safeReadable(bsData, (size_t)bsLen * 4)) {
                    memSym1 = *(int32_t *)(bsData);
                    memSym2 = *(int32_t *)(bsData + 4);
                    memSym3 = *(int32_t *)(bsData + 8);
                }
            }
        }

        // Method 2: currentSlotResult → slotSymbols (ptr) → symbol1/2/3
        int32_t resSym1 = -1, resSym2 = -1, resSym3 = -1;
        if (fo_currentSlotResult && fo_slotSymbols && fo_symbol1) {
            void *sr = readPtr(instance, fo_currentSlotResult);
            if (sr && looksLikeHeapPointer(sr) && safeReadable(sr, fo_slotSymbols + 8)) {
                void *sym3 = readPtr(sr, fo_slotSymbols);
                if (sym3 && looksLikeHeapPointer(sym3) && safeReadable(sym3, fo_symbol3 + 4)) {
                    resSym1 = *(int32_t *)((uint8_t *)sym3 + fo_symbol1);
                    resSym2 = *(int32_t *)((uint8_t *)sym3 + fo_symbol2);
                    resSym3 = *(int32_t *)((uint8_t *)sym3 + fo_symbol3);
                }
            }
        }

        // Build symbol strings for CSV/snapshot (prefer barSymbols, fallback to result)
        NSString *symStr = [NSString stringWithFormat:@"%d,%d,%d", memSym1, memSym2, memSym3];
        NSString *resSymStr = [NSString stringWithFormat:@"%d,%d,%d", resSym1, resSym2, resSym3];

        // Populate snapshot
        SLScanSnapshot *snap = [[SLScanSnapshot alloc] init];
        snap.timestamp = [NSDate date];
        snap.spinNumber = readInt32(instance, fo_currentSpinNumber);
        snap.betState = readInt32(instance, fo_betState);
        snap.spinning = isSpinning;
        snap.stripIdx1 = idx1;
        snap.stripIdx2 = idx2;
        snap.stripIdx3 = idx3;
        snap.stripLen1 = len1;
        snap.stripLen2 = len2;
        snap.stripLen3 = len3;
        snap.fullStrip1 = symStr;     // reuse strip fields for mem-read symbols
        snap.fullStrip2 = resSymStr;  // reuse for result-read symbols
        snap.fullStrip3 = nil;
        snap.replMap1 = nil;
        snap.replMap2 = nil;
        snap.replMap3 = nil;
        snap.hasReplacements = NO;
        self.latestSnapshot = snap;

        // Settle pending result on main thread (triggers CSV write + strategy compute)
        dispatch_async(dispatch_get_main_queue(), ^{
            [[SLIdxStrategy shared] settlePendingWithSnapshot:snap];
        });

        NSLog(@"[SpinLogger] Spin settled: idx=(%d,%d,%d) barSym=(%d,%d,%d) resSym=(%d,%d,%d) win=%d",
              idx1, idx2, idx3, memSym1, memSym2, memSym3, resSym1, resSym2, resSym3, spinWin);
    }
}

@end
