#import "SLSpinHook.h"
#import "SLInlineHook.h"
#include <dlfcn.h>
#include <string.h>
#include <stdint.h>

// ---------------------------------------------------------------------------
//  IL2CPP method-iteration + field-reading APIs (re-resolved here to keep
//  this module independent of SLMemoryScanner).
// ---------------------------------------------------------------------------
typedef void*       (*fn_class_get_methods)(void *klass, void **iter);
typedef const char* (*fn_method_get_name)(void *method);
typedef uint32_t    (*fn_method_get_param_count)(void *method);
typedef void*       (*fn_class_get_field_from_name)(void *klass, const char *name);
typedef size_t      (*fn_field_get_offset)(void *field);

static fn_class_get_methods          _class_get_methods;
static fn_method_get_name            _method_get_name;
static fn_method_get_param_count     _method_get_param_count;
static fn_class_get_field_from_name  _class_get_field_from_name;
static fn_field_get_offset           _field_get_offset;

static BOOL s_installed = NO;

// ---------------------------------------------------------------------------
//  Event log file — one CSV line per hook invocation.
// ---------------------------------------------------------------------------
static NSFileHandle *s_evtFile = nil;

static void openEventLog(void) {
    if (s_evtFile) return;
    NSString *docs = NSSearchPathForDirectoriesInDomains(
        NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
    NSString *path = [docs stringByAppendingPathComponent:@"hook_events.csv"];
    BOOL isNew = ![[NSFileManager defaultManager] fileExistsAtPath:path];
    if (isNew) {
        [@"ts,hook,arg1,arg2,ret,notes\n" writeToFile:path
                                           atomically:YES
                                             encoding:NSUTF8StringEncoding
                                                error:nil];
    }
    s_evtFile = [NSFileHandle fileHandleForWritingAtPath:path];
    [s_evtFile seekToEndOfFile];
    NSString *hdr = [NSString stringWithFormat:@"# session %@\n", [NSDate date]];
    [s_evtFile writeData:[hdr dataUsingEncoding:NSUTF8StringEncoding]];
}

static void logEvent(NSString *hook, NSString *a1, NSString *a2, NSString *ret, NSString *notes) {
    openEventLog();
    double ts = [NSDate date].timeIntervalSince1970;
    NSString *line = [NSString stringWithFormat:@"%.3f,%@,%@,%@,%@,%@\n",
                      ts, hook, a1 ?: @"", a2 ?: @"", ret ?: @"", notes ?: @""];
    NSLog(@"[SLHook] %@", line);
    if (s_evtFile) [s_evtFile writeData:[line dataUsingEncoding:NSUTF8StringEncoding]];
}

// ---------------------------------------------------------------------------
//  Method resolution helpers.
// ---------------------------------------------------------------------------

/// Return MethodInfo for the named method with matching arg count, or NULL.
static void *findMethod(void *klass, const char *name, int wantArgc) {
    if (!klass || !_class_get_methods) return NULL;
    void *iter = NULL, *m = NULL;
    while ((m = _class_get_methods(klass, &iter))) {
        const char *nm = _method_get_name(m);
        if (!nm || strcmp(nm, name) != 0) continue;
        int argc = _method_get_param_count ? (int)_method_get_param_count(m) : -1;
        if (wantArgc < 0 || argc == wantArgc) return m;
    }
    return NULL;
}

/// MethodInfo.methodPointer lives at offset 0 on arm64 IL2CPP builds.
static inline void *methodNativePointer(void *method) {
    return method ? *(void **)method : NULL;
}

static BOOL resolveIL2CPP(void) {
    void *h = RTLD_DEFAULT;
    #define R(sym) _ ## sym = (fn_ ## sym)dlsym(h, "il2cpp_" #sym)
    R(class_get_methods);
    R(method_get_name);
    R(method_get_param_count);
    R(class_get_field_from_name);
    R(field_get_offset);
    #undef R
    return _class_get_methods && _method_get_name;
}

// ---------------------------------------------------------------------------
//  SlotResult field offsets — looked up once.
// ---------------------------------------------------------------------------
static size_t fo_slotResult_symbols   = 0;   // slotSymbols (ref → SlotSymbol3)
static size_t fo_slotResult_win       = 0;   // win (int32)
static void  *s_klassResult           = NULL;

static void resolveSlotResultOffsets(void *klassResult) {
    s_klassResult = klassResult;
    if (!klassResult || !_class_get_field_from_name || !_field_get_offset) return;
    void *f1 = _class_get_field_from_name(klassResult, "slotSymbols");
    void *f2 = _class_get_field_from_name(klassResult, "win");
    if (f1) fo_slotResult_symbols = _field_get_offset(f1);
    if (f2) fo_slotResult_win     = _field_get_offset(f2);
}

// ---------------------------------------------------------------------------
//  Hook originals + trampolines.
//  Each "orig_*" slot stores the pointer Dobby gives us to re-enter the
//  unhooked function body.
// ---------------------------------------------------------------------------
static void *orig_TrySetNexSpinHitRecord     = NULL;
static void *orig_OnSpinResultReceived       = NULL;
static void *orig_SetFreezeResolve           = NULL;
static void *orig_activateWinSequence        = NULL;
static void *orig_ContainsAccumulationResult = NULL;

// ---------------------------------------------------------------------------
//  Hook bodies. IL2CPP instance methods take `self` as the first arg and use
//  the iOS arm64 C ABI, so we can declare them as plain C functions.
// ---------------------------------------------------------------------------

static bool hook_TrySetNexSpinHitRecord(void *self) {
    typedef bool (*fn_t)(void *);
    bool ret = ((fn_t)orig_TrySetNexSpinHitRecord)(self);
    logEvent(@"TrySetNexSpinHitRecord",
             [NSString stringWithFormat:@"%p", self],
             @"",
             ret ? @"true" : @"false",
             @"pre-SendSpinRequest");
    return ret;
}

static void hook_OnSpinResultReceived(void *self, void *response) {
    typedef void (*fn_t)(void *, void *);
    // Dump the first 256 bytes of the response object BEFORE the original
    // consumes it — the game may clear fields during processing.
    NSMutableString *hex = [NSMutableString stringWithCapacity:512];
    if (response) {
        uint8_t *p = (uint8_t *)response;
        for (int i = 0; i < 256; i++) {
            [hex appendFormat:@"%02x", p[i]];
            if ((i & 31) == 31 && i < 255) [hex appendString:@"|"];
        }
    }
    logEvent(@"OnSpinResultReceived",
             [NSString stringWithFormat:@"%p", self],
             [NSString stringWithFormat:@"%p", response],
             @"",
             hex);
    ((fn_t)orig_OnSpinResultReceived)(self, response);
}

static void hook_SetFreezeResolve(void *self) {
    typedef void (*fn_t)(void *);
    logEvent(@"SetFreezeResolve",
             [NSString stringWithFormat:@"%p", self],
             @"", @"", @"pre");
    ((fn_t)orig_SetFreezeResolve)(self);
}

static void hook_activateWinSequence(void *self, void *slotResult) {
    typedef void (*fn_t)(void *, void *);

    // Extract SlotResult fields: slotSymbols (-> SlotSymbol3 ref: s1,s2,s3)
    // and win (int32). SlotSymbol3 is a value-type with three int32 fields
    // at offsets 16, 20, 24 (after object header); when stored in a managed
    // SlotResult field it's boxed as a reference so we chase the pointer.
    NSString *notes = @"";
    if (slotResult && fo_slotResult_symbols) {
        void *sym3Ref = *(void **)((uint8_t *)slotResult + fo_slotResult_symbols);
        int32_t win   = fo_slotResult_win
                            ? *(int32_t *)((uint8_t *)slotResult + fo_slotResult_win)
                            : 0;
        int32_t s1 = 0, s2 = 0, s3 = 0;
        if (sym3Ref) {
            // SlotSymbol3 value-type boxed: 16-byte object header then 3 ints.
            s1 = *(int32_t *)((uint8_t *)sym3Ref + 16);
            s2 = *(int32_t *)((uint8_t *)sym3Ref + 20);
            s3 = *(int32_t *)((uint8_t *)sym3Ref + 24);
        }
        notes = [NSString stringWithFormat:@"s1=%d|s2=%d|s3=%d|win=%d",
                  s1, s2, s3, win];
    }
    logEvent(@"activateWinSequence",
             [NSString stringWithFormat:@"%p", self],
             [NSString stringWithFormat:@"%p", slotResult],
             @"",
             notes);
    ((fn_t)orig_activateWinSequence)(self, slotResult);
}

static int32_t hook_ContainsAccumulationResult(void *self, int32_t defaultIcon) {
    typedef int32_t (*fn_t)(void *, int32_t);
    int32_t ret = ((fn_t)orig_ContainsAccumulationResult)(self, defaultIcon);
    logEvent(@"ContainsAccumulationResult",
             [NSString stringWithFormat:@"%p", self],
             [NSString stringWithFormat:@"%d", defaultIcon],
             [NSString stringWithFormat:@"%d", ret],
             @"");
    return ret;
}

// ---------------------------------------------------------------------------
//  Installer.
// ---------------------------------------------------------------------------
int SLSpinHook_InstallAll(void *klassMgr, void *klassResult) {
    if (s_installed) return 0;
    if (!klassMgr) {
        NSLog(@"[SLHook] klassMgr is NULL — aborting install");
        return 0;
    }
    if (!resolveIL2CPP()) {
        NSLog(@"[SLHook] IL2CPP method APIs unresolvable — aborting");
        return 0;
    }
    resolveSlotResultOffsets(klassResult);

    int installed = 0;

    #define TRY_HOOK(NAME, ARGC)                                                  \
        do {                                                                      \
            void *m = findMethod(klassMgr, #NAME, (ARGC));                        \
            void *fp = methodNativePointer(m);                                    \
            if (!fp) {                                                            \
                NSLog(@"[SLHook] %s: MethodInfo not found", #NAME);               \
                break;                                                            \
            }                                                                     \
            int r = SLInlineHook_Install(fp, (void *)&hook_##NAME,                \
                                         &orig_##NAME);                           \
            NSLog(@"[SLHook] %s: install=%d target=%p trampoline=%p",             \
                  #NAME, r, fp, orig_##NAME);                                     \
            if (r == 0) installed++;                                              \
        } while (0)

    TRY_HOOK(TrySetNexSpinHitRecord,     0);
    TRY_HOOK(OnSpinResultReceived,       1);
    TRY_HOOK(SetFreezeResolve,           0);
    TRY_HOOK(activateWinSequence,        1);
    TRY_HOOK(ContainsAccumulationResult, 1);

    #undef TRY_HOOK

    s_installed = (installed > 0);
    NSLog(@"[SLHook] installed %d/5 hooks", installed);
    openEventLog();
    logEvent(@"INSTALL", @"", @"",
             [NSString stringWithFormat:@"%d", installed],
             @"session-start");
    return installed;
}
