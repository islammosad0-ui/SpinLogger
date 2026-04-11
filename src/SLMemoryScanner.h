#import <Foundation/Foundation.h>

@interface SLMemoryScanner : NSObject

+ (instancetype)shared;

/// Initializes the dynamic IL2CPP scanner and starts the read timer
- (void)startScanning;

/// Forcefully stops the scanning loop
- (void)stopScanning;

@end
