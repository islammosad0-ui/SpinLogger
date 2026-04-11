#import "SLMemoryScanner.h"
#import "SLCounterOverlay.h"
#include <dlfcn.h>
#include <objc/runtime.h>

// IL2CPP Type Definitions
typedef void* (*il2cpp_domain_get_fn)();
typedef void** (*il2cpp_domain_get_assemblies_fn)(void* domain, size_t* size);
typedef void* (*il2cpp_assembly_get_image_fn)(void* assembly);
typedef size_t (*il2cpp_image_get_class_count_fn)(void* image);
typedef void* (*il2cpp_image_get_class_fn)(void* image, size_t index);
typedef const char* (*il2cpp_class_get_name_fn)(void* klass);
typedef const char* (*il2cpp_class_get_namespace_fn)(void* klass);
typedef void* (*il2cpp_class_get_fields_fn)(void* klass, void** iter);
typedef const char* (*il2cpp_field_get_name_fn)(void* field);

@interface SLMemoryScanner()
@property (nonatomic, strong) NSTimer *scanTimer;
@property (nonatomic, assign) void* domain;
@property (nonatomic, assign) BOOL hasDumped;
@end

@implementation SLMemoryScanner

// API function pointers
static il2cpp_domain_get_fn il2cpp_domain_get = NULL;
static il2cpp_domain_get_assemblies_fn il2cpp_domain_get_assemblies = NULL;
static il2cpp_assembly_get_image_fn il2cpp_assembly_get_image = NULL;
static il2cpp_image_get_class_count_fn il2cpp_image_get_class_count = NULL;
static il2cpp_image_get_class_fn il2cpp_image_get_class = NULL;
static il2cpp_class_get_name_fn il2cpp_class_get_name = NULL;
static il2cpp_class_get_namespace_fn il2cpp_class_get_namespace = NULL;
static il2cpp_class_get_fields_fn il2cpp_class_get_fields = NULL;
static il2cpp_field_get_name_fn il2cpp_field_get_name = NULL;

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
    self.hasDumped = NO;
    
    // Resolve dynamic IL2CPP symbols
    void *handle = RTLD_DEFAULT;
    il2cpp_domain_get = (il2cpp_domain_get_fn)dlsym(handle, "il2cpp_domain_get");
    il2cpp_domain_get_assemblies = (il2cpp_domain_get_assemblies_fn)dlsym(handle, "il2cpp_domain_get_assemblies");
    il2cpp_assembly_get_image = (il2cpp_assembly_get_image_fn)dlsym(handle, "il2cpp_assembly_get_image");
    il2cpp_image_get_class_count = (il2cpp_image_get_class_count_fn)dlsym(handle, "il2cpp_image_get_class_count");
    il2cpp_image_get_class = (il2cpp_image_get_class_fn)dlsym(handle, "il2cpp_image_get_class");
    il2cpp_class_get_name = (il2cpp_class_get_name_fn)dlsym(handle, "il2cpp_class_get_name");
    il2cpp_class_get_namespace = (il2cpp_class_get_namespace_fn)dlsym(handle, "il2cpp_class_get_namespace");
    il2cpp_class_get_fields = (il2cpp_class_get_fields_fn)dlsym(handle, "il2cpp_class_get_fields");
    il2cpp_field_get_name = (il2cpp_field_get_name_fn)dlsym(handle, "il2cpp_field_get_name");
    
    if (!il2cpp_domain_get || !il2cpp_domain_get_assemblies) {
        NSLog(@"[SpinLogger] CRITICAL: Failed to resolve IL2CPP APIs via dlsym!");
        return;
    }
    
    self.domain = il2cpp_domain_get();
    NSLog(@"[SpinLogger] IL2CPP Domain Acquired: %p", self.domain);
    
    // Start GCD or NSTimer loop
    dispatch_async(dispatch_get_main_queue(), ^{
        self.scanTimer = [NSTimer scheduledTimerWithTimeInterval:3.0 
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
    if (self.hasDumped) return;
    self.hasDumped = YES;
    
    NSLog(@"[SpinLogger] Starting IL2CPP Discovery Sweep...");
    
    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_BACKGROUND, 0), ^{
        NSMutableString *dump = [NSMutableString string];
        [dump appendString:@"IL2CPP Slot Matrix Discovery Dump\n"];
        [dump appendString:@"=================================\n\n"];
        
        size_t assembliesCount = 0;
        void** assemblies = il2cpp_domain_get_assemblies(self.domain, &assembliesCount);
        if (!assemblies) {
            NSLog(@"[SpinLogger] Failed to get assemblies");
            return;
        }
        
        for (size_t i = 0; i < assembliesCount; i++) {
            void* assembly = assemblies[i];
            if (!assembly) continue;
            
            void* image = il2cpp_assembly_get_image ? il2cpp_assembly_get_image(assembly) : NULL;
            if (!image) continue;
            
            size_t classCount = il2cpp_image_get_class_count ? il2cpp_image_get_class_count(image) : 0;
            for (size_t j = 0; j < classCount; j++) {
                void* klass = il2cpp_image_get_class(image, j);
                if (!klass) continue;
                
                const char* cName = il2cpp_class_get_name ? il2cpp_class_get_name(klass) : NULL;
                if (!cName) continue;
                
                NSString *className = [NSString stringWithUTF8String:cName];
                NSString *lowerName = [className lowercaseString];
                
                // Filter for any class that sounds like it holds the 3x3 array or slot machine
                if ([lowerName containsString:@"slot"] || 
                    [lowerName containsString:@"reel"] || 
                    [lowerName containsString:@"machine"] || 
                    [lowerName containsString:@"matrix"] || 
                    [lowerName containsString:@"board"] ||
                    [lowerName containsString:@"symbol"] ||
                    [lowerName containsString:@"grid"]) {
                    
                    const char* cNs = il2cpp_class_get_namespace ? il2cpp_class_get_namespace(klass) : NULL;
                    NSString *ns = (cNs && strlen(cNs) > 0) ? [NSString stringWithUTF8String:cNs] : @"<NoNamespace>";
                    
                    [dump appendFormat:@"Class: %@.%@\n", ns, className];
                    
                    if (il2cpp_class_get_fields && il2cpp_field_get_name) {
                        void* iter = NULL;
                        void* field = NULL;
                        while ((field = il2cpp_class_get_fields(klass, &iter)) != NULL) {
                            const char* fName = il2cpp_field_get_name(field);
                            NSString *fieldName = fName ? [NSString stringWithUTF8String:fName] : @"?";
                            [dump appendFormat:@"  - %@\n", fieldName];
                        }
                    }
                    [dump appendString:@"\n"];
                }
            }
        }
        
        NSString *docs = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
        NSString *path = [docs stringByAppendingPathComponent:@"il2cpp_slot_discovery.txt"];
        [dump writeToFile:path atomically:YES encoding:NSUTF8StringEncoding error:nil];
        
        NSLog(@"[SpinLogger] IL2CPP Discovery Dump complete! Saved to %@", path);
    });
}

@end
