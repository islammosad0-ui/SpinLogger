#import "SLNetworkInterceptor.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import "SLNetworkStore.h"
#import <objc/runtime.h>

// ---------------------------------------------------------------------------
//  Network Interceptor — NSURLProtocol with FIXED infinite loop
//
//  Previous NSURLProtocol attempt broke the game because:
//  - We swizzled defaultSessionConfiguration to inject our protocol
//  - Our protocol created a forwarding session using defaultSessionConfiguration
//  - That triggered our protocol again → infinite loop → game hung
//
//  FIX: Don't swizzle session configs. Instead:
//  1. Register protocol globally (catches shared session)
//  2. Swizzle session CREATION to inject protocol into custom sessions
//  3. Forwarding session uses a PRIVATE clean config (no protocol)
//
//  Why NSURLProtocol? Unity uses delegate-based NSURLSession (no completion
//  handlers), so completion-handler swizzles catch NOTHING.
// ---------------------------------------------------------------------------

static NSString *const kSLHandledKey = @"SL_Handled";

// Extern: set by SLMenuOverlay when network kill switch is active
extern BOOL sNetworkLocked;

#pragma mark - URL matching

static BOOL SLIsSpinAPI(NSURLRequest *request) {
    NSString *path = request.URL.path;
    return (path && [path hasSuffix:@"/spin"] && [path containsString:@"/users/"]);
}

#pragma mark - SLURLProtocol

@interface SLURLProtocol : NSURLProtocol <NSURLSessionDataDelegate>
@property (nonatomic, strong) NSURLSession *internalSession;
@property (nonatomic, strong) NSURLSessionDataTask *internalTask;
@property (nonatomic, strong) NSMutableData *accumulatedData;
@property (nonatomic, assign) NSInteger capturedBet;  // extracted from request body in startLoading
@end

// A private clean config for forwarding (NO protocol injection)
static NSURLSessionConfiguration *SLCleanConfig(void) {
    NSURLSessionConfiguration *config = [NSURLSessionConfiguration ephemeralSessionConfiguration];
    // Strip ALL custom protocols to guarantee no recursion
    config.protocolClasses = @[];
    return config;
}

@implementation SLURLProtocol

+ (BOOL)canInitWithRequest:(NSURLRequest *)request {
    // Only intercept if not already handled
    if ([NSURLProtocol propertyForKey:kSLHandledKey inRequest:request]) return NO;
    NSString *scheme = request.URL.scheme.lowercaseString;
    if (![scheme isEqualToString:@"http"] && ![scheme isEqualToString:@"https"]) return NO;
    return YES;
}

+ (NSURLRequest *)canonicalRequestForRequest:(NSURLRequest *)request {
    return request;
}

- (void)startLoading {
    // Network kill switch — block game requests when locked
    if (sNetworkLocked && [self.request.URL.host containsString:@"moonactive"]) {
        NSError *blocked = [NSError errorWithDomain:NSURLErrorDomain
                                               code:NSURLErrorNotConnectedToInternet
                                           userInfo:@{NSLocalizedDescriptionKey: @"Network locked by SpinLogger"}];
        [self.client URLProtocol:self didFailWithError:blocked];
        return;
    }

    NSMutableURLRequest *tagged = [self.request mutableCopy];
    [NSURLProtocol setProperty:@YES forKey:kSLHandledKey inRequest:tagged];

    // Capture bet value from request body here — HTTPBody may be nil by didCompleteWithError
    // Unity sometimes sends bodies as HTTPBodyStream (consumed after forwarding)
    self.capturedBet = 1;
    if (SLIsSpinAPI(self.request)) {
        NSData *body = self.request.HTTPBody;
        if (!body && self.request.HTTPBodyStream) {
            // Read stream into data and replace on tagged so forwarding still works
            NSInputStream *stream = self.request.HTTPBodyStream;
            [stream open];
            NSMutableData *streamData = [NSMutableData data];
            uint8_t buf[4096];
            NSInteger len;
            while ((len = [stream read:buf maxLength:sizeof(buf)]) > 0) {
                [streamData appendBytes:buf length:len];
            }
            [stream close];
            body = streamData;
            tagged.HTTPBody = body;
            tagged.HTTPBodyStream = nil;
        }
        if (body) {
            NSString *bodyStr = [[NSString alloc] initWithData:body encoding:NSUTF8StringEncoding];
            for (NSString *pair in [bodyStr componentsSeparatedByString:@"&"]) {
                if ([pair hasPrefix:@"bet="]) {
                    // bet value IS the actual multiplier (e.g. bet=15 → 15x)
                    self.capturedBet = [[pair substringFromIndex:4] integerValue];
                    break;
                }
            }
        }
    }

    // Forward through a CLEAN session (no protocol → no recursion)
    self.internalSession = [NSURLSession sessionWithConfiguration:SLCleanConfig()
                                                         delegate:self
                                                    delegateQueue:nil];
    self.accumulatedData = [NSMutableData data];
    self.internalTask = [self.internalSession dataTaskWithRequest:tagged];
    [self.internalTask resume];
}

- (void)stopLoading {
    [self.internalTask cancel];
    [self.internalSession invalidateAndCancel];
}

#pragma mark - NSURLSessionDataDelegate

- (void)URLSession:(NSURLSession *)session
          dataTask:(NSURLSessionDataTask *)dataTask
    didReceiveResponse:(NSURLResponse *)response
     completionHandler:(void (^)(NSURLSessionResponseDisposition))handler {
    [self.client URLProtocol:self didReceiveResponse:response
          cacheStoragePolicy:NSURLCacheStorageNotAllowed];
    handler(NSURLSessionResponseAllow);
}

- (void)URLSession:(NSURLSession *)session
          dataTask:(NSURLSessionDataTask *)dataTask
    didReceiveData:(NSData *)data {
    [self.accumulatedData appendData:data];
    [self.client URLProtocol:self didLoadData:data];
}

- (void)URLSession:(NSURLSession *)session
              task:(NSURLSessionTask *)task
    didCompleteWithError:(NSError *)error {
    if (error) {
        [self.client URLProtocol:self didFailWithError:error];
    } else {
        // === INTERCEPT: Check if this is a spin API response ===
        if (SLIsSpinAPI(task.originalRequest) && self.accumulatedData.length > 0) {
            NSData *copy = [self.accumulatedData copy];
            NSInteger betMult = self.capturedBet;  // captured in startLoading before body was consumed

            NSLog(@"[SpinLogger] SPIN response captured! %lu bytes (bet=%ld)",
                  (unsigned long)copy.length, (long)betMult);
            dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
                SLParseSpinAPIResponseWithBet(copy, betMult);
            });
        }

        // Log moonactive requests to network store
        if ([task.originalRequest.URL.host containsString:@"moonactive"]) {
            SLCapturedRequest *cap = [[SLCapturedRequest alloc] init];
            cap.requestId = [[NSUUID UUID] UUIDString];
            cap.url = task.originalRequest.URL.absoluteString ?: @"";
            cap.host = task.originalRequest.URL.host ?: @"";
            cap.method = task.originalRequest.HTTPMethod ?: @"GET";
            cap.date = [NSDate date];
            cap.responseData = self.accumulatedData;
            cap.isFinished = YES;
            if ([task.response isKindOfClass:[NSHTTPURLResponse class]]) {
                cap.statusCode = ((NSHTTPURLResponse *)task.response).statusCode;
            }
            [[SLNetworkStore shared] addRequest:cap];
        }

        [self.client URLProtocolDidFinishLoading:self];
    }
}

- (void)URLSession:(NSURLSession *)session
              task:(NSURLSessionTask *)task
    willPerformHTTPRedirection:(NSHTTPURLResponse *)response
            newRequest:(NSURLRequest *)request
     completionHandler:(void (^)(NSURLRequest *))handler {
    NSMutableURLRequest *redir = [request mutableCopy];
    [NSURLProtocol removePropertyForKey:kSLHandledKey inRequest:redir];
    [self.client URLProtocol:self wasRedirectedToRequest:redir redirectResponse:response];
    handler(redir);
}

- (void)URLSession:(NSURLSession *)session
    didReceiveChallenge:(NSURLAuthenticationChallenge *)challenge
      completionHandler:(void (^)(NSURLSessionAuthChallengeDisposition, NSURLCredential *))handler {
    // Accept all certificates (game handles its own TLS)
    NSURLCredential *cred = [NSURLCredential credentialForTrust:challenge.protectionSpace.serverTrust];
    handler(NSURLSessionAuthChallengeUseCredential, cred);
}

@end

#pragma mark - Swizzle session creation to inject protocol

static IMP sOrig_sessionWithConfig = NULL;

static NSURLSession *
SL_sessionWithConfig(id self, SEL _cmd,
                     NSURLSessionConfiguration *config,
                     id delegate, NSOperationQueue *queue)
{
    // Inject our protocol into every new session's config
    if (config) {
        NSMutableArray *protos = [config.protocolClasses mutableCopy] ?: [NSMutableArray array];
        if (![protos containsObject:[SLURLProtocol class]]) {
            [protos insertObject:[SLURLProtocol class] atIndex:0];
        }
        config.protocolClasses = protos;
    }

    typedef NSURLSession *(*Orig)(id, SEL, NSURLSessionConfiguration *, id, NSOperationQueue *);
    return ((Orig)sOrig_sessionWithConfig)(self, _cmd, config, delegate, queue);
}

#pragma mark - Install

void SLNetworkInterceptorInstall(void) {
    // 1. Register globally (catches shared session)
    [NSURLProtocol registerClass:[SLURLProtocol class]];

    // 2. Swizzle session creation to inject into custom sessions (Unity!)
    {
        SEL sel = @selector(sessionWithConfiguration:delegate:delegateQueue:);
        Method m = class_getClassMethod([NSURLSession class], sel);
        if (m) {
            sOrig_sessionWithConfig = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_sessionWithConfig);
            NSLog(@"[SpinLogger] Hooked sessionWithConfiguration:delegate:delegateQueue:");
        }
    }

    NSLog(@"[SpinLogger] Interceptor ready — NSURLProtocol + session injection (loop-safe)");
}
