#import "SLNetworkInterceptor.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import <objc/runtime.h>

// ---------------------------------------------------------------------------
//  NSURLSession swizzle approach — catches ALL HTTP traffic including Unity's
//  UnityWebRequest which bypasses NSURLProtocol entirely.
//
//  We swizzle three methods:
//  1. -[NSURLSession dataTaskWithRequest:completionHandler:]
//  2. -[NSURLSession uploadTaskWithRequest:fromData:completionHandler:]
//  3. -[NSURLSession dataTaskWithRequest:] (no completion handler variant)
// ---------------------------------------------------------------------------

static BOOL SLShouldIntercept(NSURLRequest *request) {
    NSString *url = request.URL.absoluteString;
    return url && [url containsString:kSLStrackEndpoint];
}

static void SLExtractAndParse(NSURLRequest *request, NSData *extraBody) {
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

    if (!body || body.length == 0) return;

    // The endpoint says "gzip" — try decompressing if it looks compressed
    // gzip magic: 1f 8b
    const uint8_t *bytes = body.bytes;
    if (body.length > 2 && bytes[0] == 0x1f && bytes[1] == 0x8b) {
        // Try gzip decompression using NSData+zlib
        NSData *decompressed = nil;
        @try {
            // Use the built-in decompressedDataUsingAlgorithm: (iOS 13+)
            NSError *err = nil;
            decompressed = [body decompressedDataUsingAlgorithm:NSDataCompressionAlgorithmZlib
                                                         error:&err];
            if (!decompressed) {
                // Try lzfse as fallback, or raw inflate
                // Actually the game likely uses standard gzip
                // NSDataCompressionAlgorithmZlib handles both zlib and gzip
            }
        } @catch (NSException *e) {
            // decompression not available or failed
        }
        if (decompressed) body = decompressed;
    }

    NSString *bodyStr = [[NSString alloc] initWithData:body encoding:NSUTF8StringEncoding];
    if (!bodyStr) return;

    dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        SLParseStrackBody(bodyStr);
    });
}

// --- Original IMP storage ---
static IMP sOrig_dataTaskWithRequest_completion = NULL;
static IMP sOrig_uploadTask_fromData_completion = NULL;
static IMP sOrig_dataTaskWithRequest = NULL;

// --- Swizzled: dataTaskWithRequest:completionHandler: ---
static NSURLSessionDataTask *
SL_dataTaskWithRequest_completion(id self, SEL _cmd,
                                  NSURLRequest *request,
                                  void (^handler)(NSData *, NSURLResponse *, NSError *))
{
    if (SLShouldIntercept(request)) {
        SLExtractAndParse(request, nil);
    }
    typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *, id);
    return ((Orig)sOrig_dataTaskWithRequest_completion)(self, _cmd, request, handler);
}

// --- Swizzled: uploadTaskWithRequest:fromData:completionHandler: ---
static NSURLSessionUploadTask *
SL_uploadTask_fromData_completion(id self, SEL _cmd,
                                   NSURLRequest *request,
                                   NSData *bodyData,
                                   void (^handler)(NSData *, NSURLResponse *, NSError *))
{
    if (SLShouldIntercept(request)) {
        SLExtractAndParse(request, bodyData);
    }
    typedef NSURLSessionUploadTask *(*Orig)(id, SEL, NSURLRequest *, NSData *, id);
    return ((Orig)sOrig_uploadTask_fromData_completion)(self, _cmd, request, bodyData, handler);
}

// --- Swizzled: dataTaskWithRequest: (no handler variant) ---
static NSURLSessionDataTask *
SL_dataTaskWithRequest(id self, SEL _cmd, NSURLRequest *request)
{
    if (SLShouldIntercept(request)) {
        SLExtractAndParse(request, nil);
    }
    typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *);
    return ((Orig)sOrig_dataTaskWithRequest)(self, _cmd, request);
}

// ---------------------------------------------------------------------------
//  Also swizzle NSURLConnection for older code paths (Unity sometimes uses it)
// ---------------------------------------------------------------------------
static IMP sOrig_sendSyncRequest = NULL;

static NSData *
SL_sendSyncRequest(id self, SEL _cmd, NSURLRequest *request,
                   NSURLResponse **response, NSError **error)
{
    if (SLShouldIntercept(request)) {
        SLExtractAndParse(request, nil);
    }
    typedef NSData *(*Orig)(id, SEL, NSURLRequest *, NSURLResponse **, NSError **);
    return ((Orig)sOrig_sendSyncRequest)(self, _cmd, request, response, error);
}

// ---------------------------------------------------------------------------
void SLNetworkInterceptorInstall(void) {
    Class sessionCls = [NSURLSession class];

    // 1. dataTaskWithRequest:completionHandler:
    {
        SEL sel = @selector(dataTaskWithRequest:completionHandler:);
        Method m = class_getInstanceMethod(sessionCls, sel);
        if (m) {
            sOrig_dataTaskWithRequest_completion = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_dataTaskWithRequest_completion);
            NSLog(@"[SpinLogger] Hooked dataTaskWithRequest:completionHandler:");
        }
    }

    // 2. uploadTaskWithRequest:fromData:completionHandler:
    {
        SEL sel = @selector(uploadTaskWithRequest:fromData:completionHandler:);
        Method m = class_getInstanceMethod(sessionCls, sel);
        if (m) {
            sOrig_uploadTask_fromData_completion = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_uploadTask_fromData_completion);
            NSLog(@"[SpinLogger] Hooked uploadTaskWithRequest:fromData:completionHandler:");
        }
    }

    // 3. dataTaskWithRequest: (no handler)
    {
        SEL sel = @selector(dataTaskWithRequest:);
        Method m = class_getInstanceMethod(sessionCls, sel);
        if (m) {
            sOrig_dataTaskWithRequest = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_dataTaskWithRequest);
            NSLog(@"[SpinLogger] Hooked dataTaskWithRequest:");
        }
    }

    // 4. Also try NSURLConnection for legacy paths
    {
        SEL sel = @selector(sendSynchronousRequest:returningResponse:error:);
        Method m = class_getClassMethod([NSURLConnection class], sel);
        if (m) {
            sOrig_sendSyncRequest = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_sendSyncRequest);
            NSLog(@"[SpinLogger] Hooked NSURLConnection sendSynchronousRequest:");
        }
    }

    // 5. Also register NSURLProtocol as a fallback
    // (some frameworks route through the URL loading system)
    // We keep a minimal protocol that just observes — no forwarding
    [NSURLProtocol registerClass:NSClassFromString(@"SLPassiveProtocol") ?: [NSObject class]];

    NSLog(@"[SpinLogger] Network interceptor installed (swizzle mode).");
}
