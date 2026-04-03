#import "SLNetworkStore.h"

// ---------------------------------------------------------------------------
//  SLCapturedRequest
// ---------------------------------------------------------------------------
@implementation SLCapturedRequest
@end

// ---------------------------------------------------------------------------
//  SLNetworkStore — in-memory ring buffer (max 200 entries)
// ---------------------------------------------------------------------------
static const NSInteger kMaxRequests = 200;

@interface SLNetworkStore ()
@property (nonatomic, strong) NSMutableArray<SLCapturedRequest *> *requests;
@end

@implementation SLNetworkStore

+ (instancetype)shared {
    static SLNetworkStore *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _requests = [NSMutableArray array];
    }
    return self;
}

- (void)addRequest:(SLCapturedRequest *)request {
    @synchronized (self.requests) {
        [self.requests addObject:request];
        if (self.requests.count > kMaxRequests) {
            [self.requests removeObjectAtIndex:0];
        }
    }
    [[NSNotificationCenter defaultCenter]
        postNotificationName:@"Name.NetShearsNewRequest"
                      object:nil
                    userInfo:@{@"request": request}];
}

- (NSArray<SLCapturedRequest *> *)allRequests {
    @synchronized (self.requests) {
        return [self.requests copy];
    }
}

- (void)clear {
    @synchronized (self.requests) {
        [self.requests removeAllObjects];
    }
}

- (NSString *)curlForRequest:(SLCapturedRequest *)req {
    if (!req) return @"";

    NSMutableString *curl = [NSMutableString stringWithFormat:@"curl -X %@ '%@'",
                             req.method ?: @"GET", req.url ?: @""];

    [req.requestHeaders enumerateKeysAndObjectsUsingBlock:^(NSString *key, NSString *val, BOOL *stop) {
        NSString *escaped = [val stringByReplacingOccurrencesOfString:@"'" withString:@"'\\''"];
        [curl appendFormat:@" \\\n  -H '%@: %@'", key, escaped];
    }];

    if (req.requestBody.length > 0) {
        NSString *bodyStr = [[NSString alloc] initWithData:req.requestBody encoding:NSUTF8StringEncoding];
        if (bodyStr) {
            NSString *escaped = [bodyStr stringByReplacingOccurrencesOfString:@"'" withString:@"'\\''"];
            [curl appendFormat:@" \\\n  --data '%@'", escaped];
        } else {
            [curl appendFormat:@" \\\n  --data-binary @- # (%lu bytes)", (unsigned long)req.requestBody.length];
        }
    }

    return [curl copy];
}

@end
