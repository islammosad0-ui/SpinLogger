#import "SLNetworkInterceptor.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import "SLNetworkStore.h"
#import <objc/runtime.h>

// ---------------------------------------------------------------------------
//  Network Interceptor — catches the REAL-TIME spin API response
//
//  CRITICAL DISCOVERY: One.dylib intercepts the game server API, NOT strack.
//  - Spin API: POST https://vik-game.moonactive.net/api/v1/users/{id}/spin
//  - Returns JSON with r1, r2, r3 (numeric symbol IDs), reward, pay, etc.
//  - This fires INSTANTLY per spin (strack is batched analytics, delayed)
//
//  Approach: NSURLProtocol to intercept ALL HTTP, match /spin endpoint,
//  parse the RESPONSE body for spin results.
// ---------------------------------------------------------------------------

static NSString *const kSLProtocolHandledKey = @"SLURLProtocolHandled";

#pragma mark - URL matching

static BOOL SLIsSpinAPI(NSURL *url) {
    if (!url) return NO;
    NSString *path = url.path;
    // Match: /api/v1/users/{userId}/spin
    return path && [path hasSuffix:@"/spin"] && [path containsString:@"/users/"];
}

static BOOL SLIsMoonactive(NSURL *url) {
    return url && [url.host containsString:@"moonactive"];
}

#pragma mark - SLURLProtocol

@interface SLURLProtocol () <NSURLSessionDataDelegate>
@property (nonatomic, strong) NSURLSession *session;
@property (nonatomic, strong) NSURLSessionDataTask *dataTask;
@property (nonatomic, strong) NSMutableData *responseData;
@property (nonatomic, strong) NSURLResponse *capturedResponse;
@end

@implementation SLURLProtocol

+ (BOOL)canInitWithRequest:(NSURLRequest *)request {
    if ([NSURLProtocol propertyForKey:kSLProtocolHandledKey inRequest:request]) return NO;
    NSString *scheme = request.URL.scheme.lowercaseString;
    return [scheme isEqualToString:@"http"] || [scheme isEqualToString:@"https"];
}

+ (NSURLRequest *)canonicalRequestForRequest:(NSURLRequest *)request {
    return request;
}

- (void)startLoading {
    NSMutableURLRequest *req = [self.request mutableCopy];
    [NSURLProtocol setProperty:@YES forKey:kSLProtocolHandledKey inRequest:req];

    NSURLSessionConfiguration *config = [NSURLSessionConfiguration defaultSessionConfiguration];
    self.session = [NSURLSession sessionWithConfiguration:config delegate:self delegateQueue:nil];
    self.dataTask = [self.session dataTaskWithRequest:req];
    self.responseData = [NSMutableData data];
    [self.dataTask resume];
}

- (void)stopLoading {
    [self.dataTask cancel];
    self.session = nil;
}

#pragma mark NSURLSessionDataDelegate

- (void)URLSession:(NSURLSession *)session
          dataTask:(NSURLSessionDataTask *)dataTask
    didReceiveResponse:(NSURLResponse *)response
     completionHandler:(void (^)(NSURLSessionResponseDisposition))handler {
    self.capturedResponse = response;
    [self.client URLProtocol:self didReceiveResponse:response cacheStoragePolicy:NSURLCacheStorageNotAllowed];
    handler(NSURLSessionResponseAllow);
}

- (void)URLSession:(NSURLSession *)session
          dataTask:(NSURLSessionDataTask *)dataTask
    didReceiveData:(NSData *)data {
    [self.responseData appendData:data];
    [self.client URLProtocol:self didLoadData:data];
}

- (void)URLSession:(NSURLSession *)session
              task:(NSURLSessionTask *)task
    didCompleteWithError:(NSError *)error {
    if (error) {
        [self.client URLProtocol:self didFailWithError:error];
        return;
    }

    // === INTERCEPT SPIN API RESPONSE ===
    NSURL *url = task.originalRequest.URL;
    if (SLIsSpinAPI(url) && self.responseData.length > 0) {
        NSLog(@"[SpinLogger] SPIN API response intercepted! (%lu bytes) %@",
              (unsigned long)self.responseData.length, url.path);

        NSData *respCopy = [self.responseData copy];
        dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
            SLParseSpinAPIResponse(respCopy);
        });
    }

    // Log to network store
    if (SLIsMoonactive(url)) {
        SLCapturedRequest *cap = [[SLCapturedRequest alloc] init];
        cap.requestId = [[NSUUID UUID] UUIDString];
        cap.url = url.absoluteString ?: @"";
        cap.host = url.host ?: @"";
        cap.method = task.originalRequest.HTTPMethod ?: @"GET";
        cap.date = [NSDate date];
        cap.responseData = self.responseData;
        cap.isFinished = YES;
        if ([self.capturedResponse isKindOfClass:[NSHTTPURLResponse class]]) {
            cap.statusCode = ((NSHTTPURLResponse *)self.capturedResponse).statusCode;
        }
        [[SLNetworkStore shared] addRequest:cap];
    }

    [self.client URLProtocolDidFinishLoading:self];
}

- (void)URLSession:(NSURLSession *)session
              task:(NSURLSessionTask *)task
    willPerformHTTPRedirection:(NSHTTPURLResponse *)response
            newRequest:(NSURLRequest *)request
     completionHandler:(void (^)(NSURLRequest *))handler {
    NSMutableURLRequest *redir = [request mutableCopy];
    [NSURLProtocol removePropertyForKey:kSLProtocolHandledKey inRequest:redir];
    [self.client URLProtocol:self wasRedirectedToRequest:redir redirectResponse:response];
    handler(redir);
}

@end

#pragma mark - Install

void SLNetworkInterceptorInstall(void) {
    // Register NSURLProtocol
    [NSURLProtocol registerClass:[SLURLProtocol class]];

    // Inject into default + ephemeral session configs
    Class configCls = [NSURLSessionConfiguration class];

    SEL selDefault = @selector(defaultSessionConfiguration);
    Method mDefault = class_getClassMethod(configCls, selDefault);
    if (mDefault) {
        IMP orig = method_getImplementation(mDefault);
        method_setImplementation(mDefault, imp_implementationWithBlock(^NSURLSessionConfiguration *(id self2, SEL cmd2) {
            NSURLSessionConfiguration *c = ((NSURLSessionConfiguration *(*)(id, SEL))orig)(self2, cmd2);
            NSMutableArray *p = [c.protocolClasses mutableCopy] ?: [NSMutableArray array];
            if (![p containsObject:[SLURLProtocol class]]) [p insertObject:[SLURLProtocol class] atIndex:0];
            c.protocolClasses = p;
            return c;
        }));
    }

    SEL selEph = @selector(ephemeralSessionConfiguration);
    Method mEph = class_getClassMethod(configCls, selEph);
    if (mEph) {
        IMP orig = method_getImplementation(mEph);
        method_setImplementation(mEph, imp_implementationWithBlock(^NSURLSessionConfiguration *(id self2, SEL cmd2) {
            NSURLSessionConfiguration *c = ((NSURLSessionConfiguration *(*)(id, SEL))orig)(self2, cmd2);
            NSMutableArray *p = [c.protocolClasses mutableCopy] ?: [NSMutableArray array];
            if (![p containsObject:[SLURLProtocol class]]) [p insertObject:[SLURLProtocol class] atIndex:0];
            c.protocolClasses = p;
            return c;
        }));
    }

    NSLog(@"[SpinLogger] Interceptor installed — targeting /api/v1/users/*/spin responses");
}
