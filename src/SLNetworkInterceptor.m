#import "SLNetworkInterceptor.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import "SLNetworkStore.h"
#import <objc/runtime.h>

// ---------------------------------------------------------------------------
//  Network Interceptor — swizzles NSURLSession to capture all HTTP traffic.
//  Mirrors One.dylib's network interception + adds full request logging.
//
//  Hooks:
//  1. -[NSURLSession dataTaskWithRequest:completionHandler:]
//  2. -[NSURLSession uploadTaskWithRequest:fromData:completionHandler:]
//  3. -[NSURLSession dataTaskWithRequest:] (no handler)
//  4. +[NSURLConnection sendSynchronousRequest:returningResponse:error:]
// ---------------------------------------------------------------------------

static BOOL sNetworkEnabled = YES;

#pragma mark - Helpers

static BOOL SLIsStrack(NSURLRequest *request) {
    NSString *url = request.URL.absoluteString;
    return url && [url containsString:kSLStrackEndpoint];
}

static NSData *SLDecompressGzip(NSData *data) {
    if (!data || data.length < 2) return data;
    const uint8_t *bytes = data.bytes;
    if (bytes[0] != 0x1f || bytes[1] != 0x8b) return data;

    @try {
        NSError *err = nil;
        NSData *decompressed = [data decompressedDataUsingAlgorithm:NSDataCompressionAlgorithmZlib
                                                              error:&err];
        if (decompressed) return decompressed;
    } @catch (NSException *e) {}
    return data;
}

static NSData *SLExtractBody(NSURLRequest *request, NSData *extraBody) {
    NSData *body = extraBody;
    if (!body) body = request.HTTPBody;

    if (!body && request.HTTPBodyStream) {
        NSInputStream *stream = request.HTTPBodyStream;
        [stream open];
        NSMutableData *acc = [NSMutableData data];
        uint8_t buf[8192];
        NSInteger len;
        while ((len = [stream read:buf maxLength:sizeof(buf)]) > 0) {
            [acc appendBytes:buf length:(NSUInteger)len];
        }
        [stream close];
        body = acc;
    }
    return body;
}

static SLCapturedRequest *SLCaptureRequest(NSURLRequest *request, NSData *extraBody) {
    SLCapturedRequest *cap = [[SLCapturedRequest alloc] init];
    cap.requestId = [[NSUUID UUID] UUIDString];
    cap.url = request.URL.absoluteString ?: @"";
    cap.host = request.URL.host ?: @"";
    cap.method = request.HTTPMethod ?: @"GET";
    cap.scheme = request.URL.scheme ?: @"https";
    cap.date = [NSDate date];
    cap.statusCode = 0;
    cap.duration = 0;
    cap.isFinished = NO;

    // Copy request headers
    NSMutableDictionary *headers = [NSMutableDictionary dictionary];
    [request.allHTTPHeaderFields enumerateKeysAndObjectsUsingBlock:^(NSString *k, NSString *v, BOOL *stop) {
        headers[k] = v;
    }];
    cap.requestHeaders = headers;

    // Extract body
    cap.requestBody = SLExtractBody(request, extraBody);

    return cap;
}

static void SLProcessForSpinData(NSURLRequest *request, NSData *body) {
    if (!SLIsStrack(request)) return;
    if (!body || body.length == 0) return;

    NSData *decompressed = SLDecompressGzip(body);
    NSString *bodyStr = [[NSString alloc] initWithData:decompressed encoding:NSUTF8StringEncoding];
    if (!bodyStr) return;

    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        SLParseStrackBody(bodyStr);
    });
}

#pragma mark - Original IMP storage

static IMP sOrig_dataTaskWithReqHandler = NULL;
static IMP sOrig_uploadTaskFromDataHandler = NULL;
static IMP sOrig_dataTaskWithReq = NULL;
static IMP sOrig_sendSyncRequest = NULL;

#pragma mark - Swizzled implementations

// dataTaskWithRequest:completionHandler:
static NSURLSessionDataTask *
SL_dataTaskWithReqHandler(id self, SEL _cmd,
                          NSURLRequest *request,
                          void (^handler)(NSData *, NSURLResponse *, NSError *))
{
    NSData *body = SLExtractBody(request, nil);
    SLProcessForSpinData(request, body);

    if (sNetworkEnabled) {
        SLCapturedRequest *cap = SLCaptureRequest(request, nil);
        NSDate *start = [NSDate date];

        void (^wrappedHandler)(NSData *, NSURLResponse *, NSError *) = nil;
        if (handler) {
            wrappedHandler = ^(NSData *data, NSURLResponse *response, NSError *error) {
                cap.duration = -[start timeIntervalSinceNow];
                cap.isFinished = YES;
                if ([response isKindOfClass:[NSHTTPURLResponse class]]) {
                    NSHTTPURLResponse *http = (NSHTTPURLResponse *)response;
                    cap.statusCode = http.statusCode;
                    NSMutableDictionary *rh = [NSMutableDictionary dictionary];
                    [http.allHeaderFields enumerateKeysAndObjectsUsingBlock:^(id k, id v, BOOL *stop) {
                        rh[[k description]] = [v description];
                    }];
                    cap.responseHeaders = rh;
                }
                cap.responseData = data;
                [[SLNetworkStore shared] addRequest:cap];
                handler(data, response, error);
            };
        } else {
            [[SLNetworkStore shared] addRequest:cap];
        }

        typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *, id);
        return ((Orig)sOrig_dataTaskWithReqHandler)(self, _cmd, request, wrappedHandler ?: handler);
    }

    typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *, id);
    return ((Orig)sOrig_dataTaskWithReqHandler)(self, _cmd, request, handler);
}

// uploadTaskWithRequest:fromData:completionHandler:
static NSURLSessionUploadTask *
SL_uploadTaskFromDataHandler(id self, SEL _cmd,
                              NSURLRequest *request,
                              NSData *bodyData,
                              void (^handler)(NSData *, NSURLResponse *, NSError *))
{
    SLProcessForSpinData(request, bodyData);

    if (sNetworkEnabled) {
        SLCapturedRequest *cap = SLCaptureRequest(request, bodyData);
        NSDate *start = [NSDate date];

        void (^wrappedHandler)(NSData *, NSURLResponse *, NSError *) = nil;
        if (handler) {
            wrappedHandler = ^(NSData *data, NSURLResponse *response, NSError *error) {
                cap.duration = -[start timeIntervalSinceNow];
                cap.isFinished = YES;
                if ([response isKindOfClass:[NSHTTPURLResponse class]]) {
                    NSHTTPURLResponse *http = (NSHTTPURLResponse *)response;
                    cap.statusCode = http.statusCode;
                }
                cap.responseData = data;
                [[SLNetworkStore shared] addRequest:cap];
                handler(data, response, error);
            };
        } else {
            [[SLNetworkStore shared] addRequest:cap];
        }

        typedef NSURLSessionUploadTask *(*Orig)(id, SEL, NSURLRequest *, NSData *, id);
        return ((Orig)sOrig_uploadTaskFromDataHandler)(self, _cmd, request, bodyData, wrappedHandler ?: handler);
    }

    typedef NSURLSessionUploadTask *(*Orig)(id, SEL, NSURLRequest *, NSData *, id);
    return ((Orig)sOrig_uploadTaskFromDataHandler)(self, _cmd, request, bodyData, handler);
}

// dataTaskWithRequest: (no handler)
static NSURLSessionDataTask *
SL_dataTaskWithReq(id self, SEL _cmd, NSURLRequest *request)
{
    SLProcessForSpinData(request, nil);

    if (sNetworkEnabled) {
        SLCapturedRequest *cap = SLCaptureRequest(request, nil);
        [[SLNetworkStore shared] addRequest:cap];
    }

    typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *);
    return ((Orig)sOrig_dataTaskWithReq)(self, _cmd, request);
}

// NSURLConnection sendSynchronousRequest:
static NSData *
SL_sendSyncRequest(id self, SEL _cmd, NSURLRequest *request,
                   NSURLResponse **response, NSError **error)
{
    SLProcessForSpinData(request, nil);

    typedef NSData *(*Orig)(id, SEL, NSURLRequest *, NSURLResponse **, NSError **);
    NSData *result = ((Orig)sOrig_sendSyncRequest)(self, _cmd, request, response, error);

    if (sNetworkEnabled) {
        SLCapturedRequest *cap = SLCaptureRequest(request, nil);
        cap.isFinished = YES;
        cap.responseData = result;
        if (response && *response && [*response isKindOfClass:[NSHTTPURLResponse class]]) {
            cap.statusCode = ((NSHTTPURLResponse *)*response).statusCode;
        }
        [[SLNetworkStore shared] addRequest:cap];
    }

    return result;
}

#pragma mark - Install

void SLNetworkInterceptorInstall(void) {
    // Restore network logging preference
    NSNumber *netPref = [[NSUserDefaults standardUserDefaults] objectForKey:kSLDefaultsNetworkEnabled];
    if (netPref) {
        sNetworkEnabled = netPref.boolValue;
    }

    Class sessionCls = [NSURLSession class];

    // 1. dataTaskWithRequest:completionHandler:
    {
        SEL sel = @selector(dataTaskWithRequest:completionHandler:);
        Method m = class_getInstanceMethod(sessionCls, sel);
        if (m) {
            sOrig_dataTaskWithReqHandler = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_dataTaskWithReqHandler);
        }
    }

    // 2. uploadTaskWithRequest:fromData:completionHandler:
    {
        SEL sel = @selector(uploadTaskWithRequest:fromData:completionHandler:);
        Method m = class_getInstanceMethod(sessionCls, sel);
        if (m) {
            sOrig_uploadTaskFromDataHandler = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_uploadTaskFromDataHandler);
        }
    }

    // 3. dataTaskWithRequest: (no handler)
    {
        SEL sel = @selector(dataTaskWithRequest:);
        Method m = class_getInstanceMethod(sessionCls, sel);
        if (m) {
            sOrig_dataTaskWithReq = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_dataTaskWithReq);
        }
    }

    // 4. NSURLConnection legacy path
    {
        SEL sel = @selector(sendSynchronousRequest:returningResponse:error:);
        Method m = class_getClassMethod([NSURLConnection class], sel);
        if (m) {
            sOrig_sendSyncRequest = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_sendSyncRequest);
        }
    }

    NSLog(@"[SpinLogger] Network interceptor installed (network logging: %@)",
          sNetworkEnabled ? @"ON" : @"OFF");
}
