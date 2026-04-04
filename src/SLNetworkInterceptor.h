#import <Foundation/Foundation.h>

void SLNetworkInterceptorInstall(void);

// NSURLProtocol subclass — registered to intercept all HTTP traffic
@interface SLURLProtocol : NSURLProtocol
@end
