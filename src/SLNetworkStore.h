#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLCapturedRequest — stores one intercepted network request/response
// ---------------------------------------------------------------------------
@interface SLCapturedRequest : NSObject
@property (nonatomic, copy)   NSString *requestId;
@property (nonatomic, copy)   NSString *url;
@property (nonatomic, copy)   NSString *host;
@property (nonatomic, copy)   NSString *method;
@property (nonatomic, copy)   NSString *scheme;
@property (nonatomic, strong) NSDate *date;
@property (nonatomic, strong) NSDictionary<NSString *, NSString *> *requestHeaders;
@property (nonatomic, strong) NSData *requestBody;
@property (nonatomic, assign) NSInteger statusCode;
@property (nonatomic, strong) NSDictionary<NSString *, NSString *> *responseHeaders;
@property (nonatomic, strong) NSData *responseData;
@property (nonatomic, assign) NSTimeInterval duration;
@property (nonatomic, assign) BOOL isFinished;
@end

// ---------------------------------------------------------------------------
//  SLNetworkStore — in-memory ring buffer of captured requests
// ---------------------------------------------------------------------------
@interface SLNetworkStore : NSObject
+ (instancetype)shared;
- (void)addRequest:(SLCapturedRequest *)request;
- (NSArray<SLCapturedRequest *> *)allRequests;
- (void)clear;
- (NSString *)curlForRequest:(SLCapturedRequest *)request;
@end
