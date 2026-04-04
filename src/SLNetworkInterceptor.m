#import "SLNetworkInterceptor.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import "SLNetworkStore.h"
#import <objc/runtime.h>

// ---------------------------------------------------------------------------
//  Network Interceptor — SAFE approach: swizzle completion handlers only
//
//  Problem with NSURLProtocol: it intercepts AND re-forwards requests,
//  which broke the game (infinite loops, corrupted responses).
//
//  New approach: Swizzle NSURLSession methods to WRAP the completion handler.
//  We read the RESPONSE data transparently without touching the request flow.
//  The game works exactly as before — we just peek at the responses.
//
//  Target: POST /api/v1/users/{id}/spin → response has r1,r2,r3,reward,pay
// ---------------------------------------------------------------------------

#pragma mark - URL matching

static BOOL SLIsSpinResponse(NSURLRequest *request) {
    if (!request.URL) return NO;
    NSString *path = request.URL.path;
    // Match: /api/v1/users/{userId}/spin (or /api/v2/...)
    return (path &&
            [path hasSuffix:@"/spin"] &&
            [path containsString:@"/users/"]);
}

#pragma mark - Original IMPs

static IMP sOrig_dataTaskReqHandler = NULL;
static IMP sOrig_uploadTaskDataHandler = NULL;

#pragma mark - Swizzled: dataTaskWithRequest:completionHandler:

static NSURLSessionDataTask *
SL_dataTaskReqHandler(id self, SEL _cmd, NSURLRequest *request,
                      void (^handler)(NSData *, NSURLResponse *, NSError *))
{
    // If no handler or not a spin request, pass through unchanged
    if (!handler || !SLIsSpinResponse(request)) {
        typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *, id);
        return ((Orig)sOrig_dataTaskReqHandler)(self, _cmd, request, handler);
    }

    // Wrap the handler to peek at the response
    void (^wrappedHandler)(NSData *, NSURLResponse *, NSError *) =
        ^(NSData *data, NSURLResponse *response, NSError *error) {
            // Parse spin response (non-blocking, async)
            if (data && data.length > 0 && !error) {
                NSData *copy = [data copy];
                dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
                    SLParseSpinAPIResponse(copy);
                });
            }

            // Network store logging
            if (data && !error) {
                SLCapturedRequest *cap = [[SLCapturedRequest alloc] init];
                cap.requestId = [[NSUUID UUID] UUIDString];
                cap.url = request.URL.absoluteString ?: @"";
                cap.host = request.URL.host ?: @"";
                cap.method = request.HTTPMethod ?: @"POST";
                cap.date = [NSDate date];
                cap.responseData = data;
                cap.isFinished = YES;
                if ([response isKindOfClass:[NSHTTPURLResponse class]]) {
                    cap.statusCode = ((NSHTTPURLResponse *)response).statusCode;
                }
                [[SLNetworkStore shared] addRequest:cap];
            }

            // Always call the original handler — game gets its data untouched
            handler(data, response, error);
        };

    typedef NSURLSessionDataTask *(*Orig)(id, SEL, NSURLRequest *, id);
    return ((Orig)sOrig_dataTaskReqHandler)(self, _cmd, request, wrappedHandler);
}

#pragma mark - Swizzled: uploadTaskWithRequest:fromData:completionHandler:

static NSURLSessionUploadTask *
SL_uploadTaskDataHandler(id self, SEL _cmd, NSURLRequest *request,
                          NSData *bodyData,
                          void (^handler)(NSData *, NSURLResponse *, NSError *))
{
    if (!handler || !SLIsSpinResponse(request)) {
        typedef NSURLSessionUploadTask *(*Orig)(id, SEL, NSURLRequest *, NSData *, id);
        return ((Orig)sOrig_uploadTaskDataHandler)(self, _cmd, request, bodyData, handler);
    }

    void (^wrappedHandler)(NSData *, NSURLResponse *, NSError *) =
        ^(NSData *data, NSURLResponse *response, NSError *error) {
            if (data && data.length > 0 && !error) {
                NSData *copy = [data copy];
                dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
                    SLParseSpinAPIResponse(copy);
                });
            }
            handler(data, response, error);
        };

    typedef NSURLSessionUploadTask *(*Orig)(id, SEL, NSURLRequest *, NSData *, id);
    return ((Orig)sOrig_uploadTaskDataHandler)(self, _cmd, request, bodyData, wrappedHandler);
}

#pragma mark - Install

void SLNetworkInterceptorInstall(void) {
    Class cls = [NSURLSession class];

    // dataTaskWithRequest:completionHandler:
    {
        SEL sel = @selector(dataTaskWithRequest:completionHandler:);
        Method m = class_getInstanceMethod(cls, sel);
        if (m) {
            sOrig_dataTaskReqHandler = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_dataTaskReqHandler);
            NSLog(@"[SpinLogger] Hooked dataTaskWithRequest:completionHandler:");
        }
    }

    // uploadTaskWithRequest:fromData:completionHandler:
    {
        SEL sel = @selector(uploadTaskWithRequest:fromData:completionHandler:);
        Method m = class_getInstanceMethod(cls, sel);
        if (m) {
            sOrig_uploadTaskDataHandler = method_getImplementation(m);
            method_setImplementation(m, (IMP)SL_uploadTaskDataHandler);
            NSLog(@"[SpinLogger] Hooked uploadTask:fromData:completionHandler:");
        }
    }

    NSLog(@"[SpinLogger] Interceptor installed — watching /spin responses (safe swizzle, no NSURLProtocol)");
}
