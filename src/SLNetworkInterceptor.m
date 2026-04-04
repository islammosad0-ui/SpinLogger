#import "SLNetworkInterceptor.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import "SLNetworkStore.h"
#import <objc/runtime.h>

// ---------------------------------------------------------------------------
//  Network Interceptor — swizzles NSURLSession to catch Unity HTTP traffic.
//
//  KEY INSIGHT from HAR analysis:
//  - Strack URL: POST .../vikings/v3/strack/gzip
//  - Content-Encoding: gzip (on wire), but NSURLSession's HTTPBody gives us
//    the RAW UNCOMPRESSED NDJSON (gzip happens at transport layer)
//  - So HTTPBody = plain text newline-delimited JSON
//  - Try plain text FIRST, only decompress as fallback
// ---------------------------------------------------------------------------

static BOOL sNetworkEnabled = YES;

#pragma mark - URL matching

static BOOL SLIsStrack(NSURLRequest *request) {
    NSString *url = request.URL.absoluteString;
    if (!url) return NO;
    return [url containsString:@"/strack"];
}

#pragma mark - Body extraction

static NSData *SLExtractBody(NSURLRequest *request, NSData *extraBody) {
    if (extraBody && extraBody.length > 0) return extraBody;

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

#pragma mark - Parse strack body for spin data

static void SLTryParseBody(NSData *data) {
    if (!data || data.length == 0) return;

    // Try as plain UTF-8 first (HTTPBody is pre-compression)
    NSString *str = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];

    // If plain text fails, try gzip decompression
    if (!str) {
        @try {
            NSError *err = nil;
            NSData *decompressed = [data decompressedDataUsingAlgorithm:NSDataCompressionAlgorithmZlib
                                                                  error:&err];
            if (decompressed) {
                str = [[NSString alloc] initWithData:decompressed encoding:NSUTF8StringEncoding];
            }
        } @catch (NSException *e) {}
    }

    if (!str || str.length == 0) return;

    // Quick check: does this contain spin events?
    if (![str containsString:@"\"spin\""]) return;

    NSLog(@"[SpinLogger] Parsing strack body (%lu bytes, has spin events)", (unsigned long)data.length);

    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        SLParseStrackBody(str);
    });
}

#pragma mark - Original IMP storage

static IMP sOrig_dataTaskReqHandler = NULL;
static IMP sOrig_uploadTaskDataHandler = NULL;
static IMP sOrig_dataTaskReq = NULL;
static IMP sOrig_uploadTaskData = NULL;
static IMP sOrig_sendSync = NULL;

#pragma mark - Swizzled: dataTaskWithRequest:completionHandler:

static NSURLSessionDataTask *
SL_dataTaskReqHandler(id self, SEL _cmd, NSURLRequest *request,
                      void (^handler)(NSData *, NSURLResponse *, NSError *))
{
    if (SLIsStrack(request)) {
        NSData *body = SLExtractBody(request, nil);
        if (body) {
            NSLog(@"[SpinLogger] STRACK via dataTask:handler: (%lu bytes)", (unsigned long)body.length);
            SLTryParseBody(body);
        } else {
            NSLog(@"[SpinLogger] STRACK via dataTask:handler: but NO BODY");
        }
    }

    // Wrap handler to capture response (for network monitor)
    if (sNetworkEnabled && handler) {
        __block NSURLRequest *capturedReq = request;
        void (^wrapped)(NSData *, NSURLResponse *, NSError *) =
            ^(NSData *data, NSURLResponse *response, NSError *error) {
                SLCapturedRequest *cap = [[SLCapturedRequest alloc] init];
                cap.requestId = [[NSUUID UUID] UUIDString];
                cap.url = capturedReq.URL.absoluteString ?: @"";
                cap.host = capturedReq.URL.host ?: @"";
                cap.method = capturedReq.HTTPMethod ?: @"GET";
                cap.date = [NSDate date];
                cap.responseData = data;
                cap.isFinished = YES;
                if ([response isKindOfClass:[NSHTTPURLResponse class]]) {
                    cap.statusCode = ((NSHTTPURLResponse *)response).statusCode;
                }
                [[SLNetworkStore shared] addRequest:cap];
                handler(data, response, error);
            };

        typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *, id);
        return ((Orig)sOrig_dataTaskReqHandler)(self, _cmd, request, wrapped);
    }

    typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *, id);
    return ((Orig)sOrig_dataTaskReqHandler)(self, _cmd, request, handler);
}

#pragma mark - Swizzled: uploadTaskWithRequest:fromData:completionHandler:

static NSURLSessionUploadTask *
SL_uploadTaskDataHandler(id self, SEL _cmd, NSURLRequest *request,
                          NSData *bodyData,
                          void (^handler)(NSData *, NSURLResponse *, NSError *))
{
    if (SLIsStrack(request)) {
        NSData *body = bodyData ?: SLExtractBody(request, nil);
        if (body) {
            NSLog(@"[SpinLogger] STRACK via uploadTask:fromData: (%lu bytes)", (unsigned long)body.length);
            SLTryParseBody(body);
        }
    }

    typedef NSURLSessionUploadTask *(*Orig)(id, SEL, NSURLRequest *, NSData *, id);
    return ((Orig)sOrig_uploadTaskDataHandler)(self, _cmd, request, bodyData, handler);
}

#pragma mark - Swizzled: dataTaskWithRequest: (no handler)

static NSURLSessionDataTask *
SL_dataTaskReq(id self, SEL _cmd, NSURLRequest *request)
{
    if (SLIsStrack(request)) {
        NSData *body = SLExtractBody(request, nil);
        if (body) {
            NSLog(@"[SpinLogger] STRACK via dataTask: no-handler (%lu bytes)", (unsigned long)body.length);
            SLTryParseBody(body);
        }
    }

    typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *);
    return ((Orig)sOrig_dataTaskReq)(self, _cmd, request);
}

#pragma mark - Swizzled: uploadTaskWithRequest:fromData: (no handler)

static NSURLSessionUploadTask *
SL_uploadTaskData(id self, SEL _cmd, NSURLRequest *request, NSData *bodyData)
{
    if (SLIsStrack(request)) {
        NSData *body = bodyData ?: SLExtractBody(request, nil);
        if (body) {
            NSLog(@"[SpinLogger] STRACK via uploadTask:fromData: no-handler (%lu bytes)", (unsigned long)body.length);
            SLTryParseBody(body);
        }
    }

    typedef NSURLSessionUploadTask *(*Orig)(id, SEL, NSURLRequest *, NSData *);
    return ((Orig)sOrig_uploadTaskData)(self, _cmd, request, bodyData);
}

#pragma mark - Swizzled: NSURLConnection sendSynchronousRequest:

static NSData *
SL_sendSync(id self, SEL _cmd, NSURLRequest *request,
            NSURLResponse **response, NSError **error)
{
    if (SLIsStrack(request)) {
        NSData *body = SLExtractBody(request, nil);
        if (body) SLTryParseBody(body);
    }

    typedef NSData *(*Orig)(id, SEL, NSURLRequest *, NSURLResponse **, NSError **);
    return ((Orig)sOrig_sendSync)(self, _cmd, request, response, error);
}

#pragma mark - Install

void SLNetworkInterceptorInstall(void) {
    NSNumber *netPref = [[NSUserDefaults standardUserDefaults] objectForKey:kSLDefaultsNetworkEnabled];
    if (netPref) sNetworkEnabled = netPref.boolValue;

    Class cls = [NSURLSession class];

    // 1. dataTaskWithRequest:completionHandler:
    {
        SEL sel = @selector(dataTaskWithRequest:completionHandler:);
        Method m = class_getInstanceMethod(cls, sel);
        if (m) {
            sOrig_dataTaskReqHandler = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_dataTaskReqHandler);
            NSLog(@"[SpinLogger] Hooked dataTaskWithRequest:completionHandler:");
        }
    }

    // 2. uploadTaskWithRequest:fromData:completionHandler:
    {
        SEL sel = @selector(uploadTaskWithRequest:fromData:completionHandler:);
        Method m = class_getInstanceMethod(cls, sel);
        if (m) {
            sOrig_uploadTaskDataHandler = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_uploadTaskDataHandler);
            NSLog(@"[SpinLogger] Hooked uploadTask:fromData:completionHandler:");
        }
    }

    // 3. dataTaskWithRequest: (no handler)
    {
        SEL sel = @selector(dataTaskWithRequest:);
        Method m = class_getInstanceMethod(cls, sel);
        if (m) {
            sOrig_dataTaskReq = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_dataTaskReq);
        }
    }

    // 4. uploadTaskWithRequest:fromData: (no handler)
    {
        SEL sel = @selector(uploadTaskWithRequest:fromData:);
        Method m = class_getInstanceMethod(cls, sel);
        if (m) {
            sOrig_uploadTaskData = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_uploadTaskData);
        }
    }

    // 5. NSURLConnection fallback
    {
        SEL sel = @selector(sendSynchronousRequest:returningResponse:error:);
        Method m = class_getClassMethod([NSURLConnection class], sel);
        if (m) {
            sOrig_sendSync = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_sendSync);
        }
    }

    NSLog(@"[SpinLogger] Network interceptor installed (5 hooks)");
}
