#import "SLNetworkInterceptor.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import "SLNetworkStore.h"
#import <objc/runtime.h>

// ---------------------------------------------------------------------------
//  Network Interceptor — DUAL approach matching One.dylib (KEDCui):
//
//  Layer 1: NSURLProtocol subclass (SLURLProtocol)
//    - Registered globally → catches ALL HTTP including Unity
//    - Sees raw uncompressed request body before Content-Encoding
//    - Forwards requests transparently (no modification)
//
//  Layer 2: NSURLSession swizzle (backup)
//    - Catches requests that bypass NSURLProtocol
//    - uploadTaskWithRequest:fromData: for explicit body data
//
//  Data flow (matching One.dylib):
//    NSURLProtocol intercept → extract body → check for /strack
//    → parse NDJSON → post NetShearsSpinEvent notification
// ---------------------------------------------------------------------------

static NSString *const kSLProtocolHandledKey = @"SLURLProtocolHandled";

#pragma mark - Helpers

static BOOL SLIsStrack(NSURL *url) {
    return url && [url.absoluteString containsString:@"/strack"];
}

static void SLTryParseBody(NSData *data) {
    if (!data || data.length == 0) return;

    // HTTPBody from NSURLProtocol is raw uncompressed NDJSON
    NSString *str = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];

    // Fallback: try gzip decompression if plain text fails
    if (!str) {
        @try {
            NSData *d = [data decompressedDataUsingAlgorithm:NSDataCompressionAlgorithmZlib error:nil];
            if (d) str = [[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding];
        } @catch (NSException *e) {}
    }

    if (!str || ![str containsString:@"\"spin\""]) return;

    NSLog(@"[SpinLogger] Found spin data (%lu bytes)", (unsigned long)data.length);
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        SLParseStrackBody(str);
    });
}

static NSData *SLExtractBody(NSURLRequest *request) {
    NSData *body = request.HTTPBody;
    if (body && body.length > 0) return body;

    if (request.HTTPBodyStream) {
        NSInputStream *stream = request.HTTPBodyStream;
        [stream open];
        NSMutableData *acc = [NSMutableData data];
        uint8_t buf[16384];
        NSInteger len;
        while ((len = [stream read:buf maxLength:sizeof(buf)]) > 0) {
            [acc appendBytes:buf length:(NSUInteger)len];
        }
        [stream close];
        if (acc.length > 0) return acc;
    }
    return nil;
}

#pragma mark - SLURLProtocol (Layer 1: NSURLProtocol)

@interface SLURLProtocol () <NSURLSessionDataDelegate>
@property (nonatomic, strong) NSURLSession *session;
@property (nonatomic, strong) NSURLSessionDataTask *dataTask;
@property (nonatomic, strong) NSMutableData *responseData;
@property (nonatomic, strong) NSURLResponse *response;
@end

@implementation SLURLProtocol

+ (BOOL)canInitWithRequest:(NSURLRequest *)request {
    // Don't handle requests we've already tagged (prevent infinite loop)
    if ([NSURLProtocol propertyForKey:kSLProtocolHandledKey inRequest:request]) {
        return NO;
    }
    // Intercept ALL HTTP/HTTPS requests
    NSString *scheme = request.URL.scheme.lowercaseString;
    return [scheme isEqualToString:@"http"] || [scheme isEqualToString:@"https"];
}

+ (NSURLRequest *)canonicalRequestForRequest:(NSURLRequest *)request {
    return request;
}

- (void)startLoading {
    NSMutableURLRequest *mutableRequest = [self.request mutableCopy];
    [NSURLProtocol setProperty:@YES forKey:kSLProtocolHandledKey inRequest:mutableRequest];

    // === INTERCEPT: Extract and parse strack body BEFORE forwarding ===
    if (SLIsStrack(mutableRequest.URL)) {
        NSData *body = SLExtractBody(mutableRequest);
        if (body) {
            NSLog(@"[SpinLogger] STRACK intercepted via NSURLProtocol (%lu bytes)", (unsigned long)body.length);
            SLTryParseBody(body);
        } else {
            NSLog(@"[SpinLogger] STRACK intercepted but NO body (URL: %@)", mutableRequest.URL.absoluteString);
        }
    }

    // Log to network store
    SLCapturedRequest *cap = [[SLCapturedRequest alloc] init];
    cap.requestId = [[NSUUID UUID] UUIDString];
    cap.url = mutableRequest.URL.absoluteString ?: @"";
    cap.host = mutableRequest.URL.host ?: @"";
    cap.method = mutableRequest.HTTPMethod ?: @"GET";
    cap.date = [NSDate date];
    cap.isFinished = NO;
    [[SLNetworkStore shared] addRequest:cap];

    // Forward the request transparently
    NSURLSessionConfiguration *config = [NSURLSessionConfiguration defaultSessionConfiguration];
    self.session = [NSURLSession sessionWithConfiguration:config delegate:self delegateQueue:nil];
    self.dataTask = [self.session dataTaskWithRequest:mutableRequest];
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
     completionHandler:(void (^)(NSURLSessionResponseDisposition))completionHandler {
    self.response = response;
    [self.client URLProtocol:self didReceiveResponse:response cacheStoragePolicy:NSURLCacheStorageNotAllowed];
    completionHandler(NSURLSessionResponseAllow);
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
    } else {
        // Also try to parse response body for spin data (some endpoints return it)
        if (SLIsStrack(task.originalRequest.URL) && self.responseData.length > 0) {
            SLTryParseBody(self.responseData);
        }
        [self.client URLProtocolDidFinishLoading:self];
    }
}

- (void)URLSession:(NSURLSession *)session
              task:(NSURLSessionTask *)task
    willPerformHTTPRedirection:(NSHTTPURLResponse *)response
            newRequest:(NSURLRequest *)request
     completionHandler:(void (^)(NSURLRequest *))completionHandler {
    NSMutableURLRequest *redirectRequest = [request mutableCopy];
    [NSURLProtocol removePropertyForKey:kSLProtocolHandledKey inRequest:redirectRequest];
    [self.client URLProtocol:self wasRedirectedToRequest:redirectRequest redirectResponse:response];
    completionHandler(redirectRequest);
}

@end

#pragma mark - Layer 2: NSURLSession swizzle (backup for Unity)

static IMP sOrig_uploadTaskDataHandler = NULL;
static IMP sOrig_dataTaskReqHandler = NULL;

static NSURLSessionUploadTask *
SL_uploadTaskDataHandler(id self, SEL _cmd, NSURLRequest *request,
                          NSData *bodyData,
                          void (^handler)(NSData *, NSURLResponse *, NSError *))
{
    // Upload tasks pass body as separate param — NSURLProtocol might miss it
    if (SLIsStrack(request.URL) && bodyData) {
        NSLog(@"[SpinLogger] STRACK via uploadTask swizzle (%lu bytes)", (unsigned long)bodyData.length);
        SLTryParseBody(bodyData);
    }
    typedef NSURLSessionUploadTask *(*Orig)(id, SEL, NSURLRequest *, NSData *, id);
    return ((Orig)sOrig_uploadTaskDataHandler)(self, _cmd, request, bodyData, handler);
}

static NSURLSessionDataTask *
SL_dataTaskReqHandler(id self, SEL _cmd, NSURLRequest *request,
                      void (^handler)(NSData *, NSURLResponse *, NSError *))
{
    // Backup: catch strack in dataTask too
    if (SLIsStrack(request.URL)) {
        NSData *body = SLExtractBody(request);
        if (body) {
            NSLog(@"[SpinLogger] STRACK via dataTask swizzle (%lu bytes)", (unsigned long)body.length);
            SLTryParseBody(body);
        }
    }
    typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *, id);
    return ((Orig)sOrig_dataTaskReqHandler)(self, _cmd, request, handler);
}

#pragma mark - Install

void SLNetworkInterceptorInstall(void) {
    // Layer 1: Register NSURLProtocol (catches ALL HTTP like One.dylib)
    [NSURLProtocol registerClass:[SLURLProtocol class]];
    NSLog(@"[SpinLogger] NSURLProtocol registered (Layer 1)");

    // Also inject into shared session config so Unity's custom sessions pick it up
    NSURLSessionConfiguration *defaultConfig = [NSURLSessionConfiguration defaultSessionConfiguration];
    NSMutableArray *protocols = [defaultConfig.protocolClasses mutableCopy] ?: [NSMutableArray array];
    if (![protocols containsObject:[SLURLProtocol class]]) {
        [protocols insertObject:[SLURLProtocol class] atIndex:0];
    }
    defaultConfig.protocolClasses = protocols;

    // Swizzle the config getter so new sessions inherit our protocol
    {
        SEL sel = @selector(defaultSessionConfiguration);
        Method m = class_getClassMethod([NSURLSessionConfiguration class], sel);
        if (m) {
            IMP origImp = method_getImplementation(m);
            IMP newImp = imp_implementationWithBlock(^NSURLSessionConfiguration *(id _self, SEL _cmd2) {
                NSURLSessionConfiguration *config = ((NSURLSessionConfiguration *(*)(id, SEL))origImp)(_self, _cmd2);
                NSMutableArray *protos = [config.protocolClasses mutableCopy] ?: [NSMutableArray array];
                if (![protos containsObject:[SLURLProtocol class]]) {
                    [protos insertObject:[SLURLProtocol class] atIndex:0];
                }
                config.protocolClasses = protos;
                return config;
            });
            method_setImplementation(m, newImp);
        }
    }

    // Also swizzle ephemeralSessionConfiguration
    {
        SEL sel = @selector(ephemeralSessionConfiguration);
        Method m = class_getClassMethod([NSURLSessionConfiguration class], sel);
        if (m) {
            IMP origImp = method_getImplementation(m);
            IMP newImp = imp_implementationWithBlock(^NSURLSessionConfiguration *(id _self, SEL _cmd2) {
                NSURLSessionConfiguration *config = ((NSURLSessionConfiguration *(*)(id, SEL))origImp)(_self, _cmd2);
                NSMutableArray *protos = [config.protocolClasses mutableCopy] ?: [NSMutableArray array];
                if (![protos containsObject:[SLURLProtocol class]]) {
                    [protos insertObject:[SLURLProtocol class] atIndex:0];
                }
                config.protocolClasses = protos;
                return config;
            });
            method_setImplementation(m, newImp);
        }
    }

    NSLog(@"[SpinLogger] Session config swizzled (Layer 1b)");

    // Layer 2: Swizzle upload/data tasks as backup
    Class cls = [NSURLSession class];
    {
        SEL sel = @selector(uploadTaskWithRequest:fromData:completionHandler:);
        Method m = class_getInstanceMethod(cls, sel);
        if (m) {
            sOrig_uploadTaskDataHandler = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_uploadTaskDataHandler);
        }
    }
    {
        SEL sel = @selector(dataTaskWithRequest:completionHandler:);
        Method m = class_getInstanceMethod(cls, sel);
        if (m) {
            sOrig_dataTaskReqHandler = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_dataTaskReqHandler);
        }
    }

    NSLog(@"[SpinLogger] Network interceptor installed (NSURLProtocol + swizzle backup)");
}
