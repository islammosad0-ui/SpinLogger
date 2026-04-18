#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLMethodDump
//
//  One-shot IL2CPP method dumper. Walks each passed class and writes every
//  method (name, return type, param list, method pointer) to
//
//      ~/Documents/il2cpp_methods.txt
//
//  Intended use: identify the Unity method that finalises a spin so we can
//  install an inline hook on it (replaces polling in SLMemoryScanner).
// ---------------------------------------------------------------------------

typedef struct {
    void *klass;
    const char *label;    // human-readable header written above the method list
} SLMDClassEntry;

/// Write methods for each entry to Documents/il2cpp_methods.txt. Safe to call
/// once per process (no-ops on subsequent calls in the same session).
void SLMethodDump_Run(const SLMDClassEntry *entries, size_t count);
