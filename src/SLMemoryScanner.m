#import "SLMemoryScanner.h"
#import "SLCounterOverlay.h"
#include <dlfcn.h>
#include <objc/runtime.h>

// IL2CPP Type Definitions
typedef void* (*il2cpp_domain_get_fn)();
typedef void* (*il2cpp_domain_get_assemblies_fn)(void* domain, size_t* size);
typedef void* (*il2cpp_class_from_name_fn)(void* image, const char* namespaze, const char* name);
typedef void* (*il2cpp_class_get_field_from_name_fn)(void* klass, const char* name);
typedef void  (*il2cpp_field_get_value_fn)(void* obj, void* field, void* value);

@interface SLMemoryScanner()
@property (nonatomic, strong) NSTimer *scanTimer;
@property (nonatomic, assign) void* domain;
@end

@implementation SLMemoryScanner

// API function pointers
static il2cpp_domain_get_fn il2cpp_domain_get = NULL;
static il2cpp_domain_get_assemblies_fn il2cpp_domain_get_assemblies = NULL;
static il2cpp_class_from_name_fn il2cpp_class_from_name = NULL;
static il2cpp_class_get_field_from_name_fn il2cpp_class_get_field_from_name = NULL;
static il2cpp_field_get_value_fn il2cpp_field_get_value = NULL;

+ (instancetype)shared {
    static SLMemoryScanner *instance = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        instance = [[SLMemoryScanner alloc] init];
    });
    return instance;
}

- (void)startScanning {
    if (self.scanTimer) return;
    
    // Resolve dynamic IL2CPP symbols
    void *handle = RTLD_DEFAULT;
    il2cpp_domain_get = (il2cpp_domain_get_fn)dlsym(handle, "il2cpp_domain_get");
    il2cpp_domain_get_assemblies = (il2cpp_domain_get_assemblies_fn)dlsym(handle, "il2cpp_domain_get_assemblies");
    il2cpp_class_from_name = (il2cpp_class_from_name_fn)dlsym(handle, "il2cpp_class_from_name");
    il2cpp_class_get_field_from_name = (il2cpp_class_get_field_from_name_fn)dlsym(handle, "il2cpp_class_get_field_from_name");
    il2cpp_field_get_value = (il2cpp_field_get_value_fn)dlsym(handle, "il2cpp_field_get_value");
    
    if (!il2cpp_domain_get || !il2cpp_class_from_name) {
        NSLog(@"[SpinLogger] CRITICAL: Failed to resolve IL2CPP APIs via dlsym!");
        return;
    }
    
    self.domain = il2cpp_domain_get();
    NSLog(@"[SpinLogger] IL2CPP Domain Acquired: %p", self.domain);
    
    // Start GCD or NSTimer loop
    dispatch_async(dispatch_get_main_queue(), ^{
        self.scanTimer = [NSTimer scheduledTimerWithTimeInterval:0.5 
                                                          target:self 
                                                        selector:@selector(performMemoryScan) 
                                                        userInfo:nil 
                                                         repeats:YES];
    });
}

- (void)stopScanning {
    [self.scanTimer invalidate];
    self.scanTimer = nil;
}

- (void)performMemoryScan {
    // 1. Locate the SlotMachineController class
    // TO DO: Iterate through il2cpp_domain_get_assemblies to find the active image, 
    //        then grab the SlotMachineController.
    // 2. Read the Matrix Array field.
    // 3. Write to CSV and trigger UI: [[SLCounterOverlay shared] performSelector:@selector(showTeaserAlert)];
}

@end
