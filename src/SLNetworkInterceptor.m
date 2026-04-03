#import "SLNetworkInterceptor.h"
#import "SLConstants.h"
#import "SLSpinParser.h"

// ---------------------------------------------------------------------------
//  Tag key used to prevent infinite recursion — once a request has been
//  handled by SLURLProtocol it is marked with this property so
//  +canInitWithRequest: will return NO on the forwarded copy.
// ---------------------------------------------------------------------------
static NSString *const kSLHandledKey = @"com.spinlogger.handled";

// ---------------------------------------------------------------------------
//  SLURLProtocol — intercepts HTTP(S) traffic to moonactive.net
// ---------------------------------------------------------------------------
@interface SLURLProtocol : NSURLProtocol <NSURLSessionDataDelegate>

@property (nonatomic, strong) NSURLSessionDataTask *activeTask;
@property (nonatomic, strong) NSMutableData        *responseData;

@end

@implementation SLURLProtocol

#pragma mark - NSURLProtocol overrides

+ (BOOL)canInitWithRequest:(NSURLRequest *)request {
    // Already handled — bail out to avoid infinite recursion.
    if ([NSURLProtocol propertyForKey:kSLHandledKey inRequest:request]) {
        return NO;
    }
    // Only intercept requests aimed at the game API.
    NSString *host = request.URL.host;
    return host && [host containsString:kSLGameAPIHost];
}

+ (NSURLRequest *)canonicalRequestForRequest:(NSURLRequest *)request {
    return request;
}

- (void)startLoading {
    // 1. Tag the request so we don't intercept it again.
    NSMutableURLRequest *mutable = [self.request mutableCopy];
    [NSURLProtocol setProperty:@YES forKey:kSLHandledKey inRequest:mutable];

    // 2. If this is a POST to the strack endpoint, extract the body and parse.
    if ([mutable.HTTPMethod isEqualToString:@"POST"] &&
        [mutable.URL.path containsString:kSLStrackEndpoint]) {

        NSData *bodyData = nil;

        if (mutable.HTTPBody) {
            bodyData = mutable.HTTPBody;
        } else if (mutable.HTTPBodyStream) {
            NSInputStream *stream = mutable.HTTPBodyStream;
            [stream open];
            NSMutableData *accumulator = [NSMutableData data];
            uint8_t buffer[4096];
            NSInteger bytesRead;
            while ((bytesRead = [stream read:buffer maxLength:sizeof(buffer)]) > 0) {
                [accumulator appendBytes:buffer length:(NSUInteger)bytesRead];
            }
            [stream close];
            bodyData = [accumulator copy];
        }

        if (bodyData.length > 0) {
            NSString *bodyString = [[NSString alloc] initWithData:bodyData
                                                         encoding:NSUTF8StringEncoding];
            if (bodyString) {
                dispatch_async(dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
                    SLParseStrackBody(bodyString);
                });
            }
        }
    }

    // 3. Forward the request via a fresh NSURLSession.
    NSURLSessionConfiguration *config =
        [NSURLSessionConfiguration defaultSessionConfiguration];
    NSURLSession *session =
        [NSURLSession sessionWithConfiguration:config
                                      delegate:self
                                 delegateQueue:nil];

    self.responseData = [NSMutableData data];
    self.activeTask   = [session dataTaskWithRequest:mutable];
    [self.activeTask resume];
}

- (void)stopLoading {
    [self.activeTask cancel];
    self.activeTask = nil;
}

#pragma mark - NSURLSessionDataDelegate

- (void)URLSession:(NSURLSession *)session
          dataTask:(NSURLSessionDataTask *)dataTask
didReceiveResponse:(NSURLResponse *)response
 completionHandler:(void (^)(NSURLSessionResponseDisposition))completionHandler {
    [self.client URLProtocol:self
          didReceiveResponse:response
          cacheStoragePolicy:NSURLCacheStorageNotAllowed];
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
        [self.client URLProtocolDidFinishLoading:self];
    }
}

@end

// ---------------------------------------------------------------------------
//  Public installer — called from the dylib constructor
// ---------------------------------------------------------------------------
void SLNetworkInterceptorInstall(void) {
    [NSURLProtocol registerClass:[SLURLProtocol class]];
}
