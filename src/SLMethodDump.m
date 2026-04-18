#import "SLMethodDump.h"
#include <dlfcn.h>
#include <string.h>

// ---------------------------------------------------------------------------
//  IL2CPP function-pointer types (method iteration + type inspection).
// ---------------------------------------------------------------------------
typedef void*       (*fn_class_get_methods)(void *klass, void **iter);
typedef const char* (*fn_method_get_name)(void *method);
typedef uint32_t    (*fn_method_get_param_count)(void *method);
typedef void*       (*fn_method_get_param)(void *method, uint32_t index);
typedef const char* (*fn_method_get_param_name)(void *method, uint32_t index);
typedef void*       (*fn_method_get_return_type)(void *method);
typedef char*       (*fn_type_get_name)(void *type);
typedef uint32_t    (*fn_method_get_flags)(void *method, uint32_t *iflags);
typedef void        (*fn_free)(void *ptr);

static fn_class_get_methods       _class_get_methods;
static fn_method_get_name         _method_get_name;
static fn_method_get_param_count  _method_get_param_count;
static fn_method_get_param        _method_get_param;
static fn_method_get_param_name   _method_get_param_name;
static fn_method_get_return_type  _method_get_return_type;
static fn_type_get_name           _type_get_name;
static fn_method_get_flags        _method_get_flags;
static fn_free                    _il2cpp_free;

static BOOL s_didDump = NO;

static BOOL resolveAPIs(void) {
    void *h = RTLD_DEFAULT;
    #define R(nm) _ ## nm = (fn_ ## nm)dlsym(h, "il2cpp_" #nm)
    R(class_get_methods);
    R(method_get_name);
    R(method_get_param_count);
    R(method_get_param);
    R(method_get_param_name);
    R(method_get_return_type);
    R(type_get_name);
    R(method_get_flags);
    #undef R
    _il2cpp_free = (fn_free)dlsym(h, "il2cpp_free");
    return _class_get_methods && _method_get_name && _method_get_return_type && _type_get_name;
}

// IL2CPP MethodInfo.methodPointer lives at offset 0 on arm64 Unity builds.
static inline void *methodNativePointer(void *method) {
    if (!method) return NULL;
    return *(void **)method;
}

// Caller owns the returned C-string (il2cpp_type_get_name mallocs). We dup
// into an NSString so ARC handles lifetime for us.
static NSString *typeName(void *type) {
    if (!type || !_type_get_name) return @"<?>";
    char *raw = _type_get_name(type);
    if (!raw) return @"<?>";
    NSString *s = [NSString stringWithUTF8String:raw];
    if (_il2cpp_free) _il2cpp_free(raw); else free(raw);
    return s ?: @"<?>";
}

static void dumpOneClass(NSFileHandle *out, const SLMDClassEntry *e) {
    NSMutableString *buf = [NSMutableString stringWithCapacity:4096];
    [buf appendFormat:@"\n===== %s  (klass=%p) =====\n",
                      e->label ?: "(unlabeled)", e->klass];
    if (!e->klass) {
        [buf appendString:@"  <class pointer is NULL — not resolved>\n"];
        [out writeData:[buf dataUsingEncoding:NSUTF8StringEncoding]];
        return;
    }

    void *iter = NULL;
    void *m = NULL;
    int count = 0;
    while ((m = _class_get_methods(e->klass, &iter))) {
        const char *nm = _method_get_name(m);
        NSString *ret = typeName(_method_get_return_type(m));
        uint32_t pc = _method_get_param_count ? _method_get_param_count(m) : 0;

        NSMutableString *params = [NSMutableString string];
        for (uint32_t i = 0; i < pc; i++) {
            void *pt = _method_get_param ? _method_get_param(m, i) : NULL;
            const char *pn = _method_get_param_name ? _method_get_param_name(m, i) : NULL;
            if (i) [params appendString:@", "];
            [params appendFormat:@"%@ %s", typeName(pt), pn ? pn : "_"];
        }

        void *fp = methodNativePointer(m);
        [buf appendFormat:@"  %@ %s(%@)  mp=%p\n",
                           ret, nm ? nm : "?", params, fp];
        count++;
    }
    [buf appendFormat:@"  -- %d methods --\n", count];
    [out writeData:[buf dataUsingEncoding:NSUTF8StringEncoding]];
}

void SLMethodDump_Run(const SLMDClassEntry *entries, size_t count) {
    if (s_didDump) return;
    s_didDump = YES;
    if (!resolveAPIs()) {
        NSLog(@"[SLMethodDump] IL2CPP method APIs not resolvable — skipping");
        return;
    }
    if (!entries || count == 0) return;

    NSString *docs = NSSearchPathForDirectoriesInDomains(
        NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
    NSString *path = [docs stringByAppendingPathComponent:@"il2cpp_methods.txt"];

    // Fresh file each launch — a stale dump from an older build is worse
    // than no dump.
    [[NSFileManager defaultManager] createFileAtPath:path contents:nil attributes:nil];
    NSFileHandle *out = [NSFileHandle fileHandleForWritingAtPath:path];
    if (!out) {
        NSLog(@"[SLMethodDump] cannot open %@ for writing", path);
        return;
    }

    NSString *hdr = [NSString stringWithFormat:@"IL2CPP method dump — %@\n\n", [NSDate date]];
    [out writeData:[hdr dataUsingEncoding:NSUTF8StringEncoding]];

    for (size_t i = 0; i < count; i++) dumpOneClass(out, &entries[i]);

    [out closeFile];
    NSLog(@"[SLMethodDump] wrote %@", path);
}
