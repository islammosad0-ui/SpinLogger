#import "SLNetworkMonitor.h"
#import "SLNetworkStore.h"
#import "SLConstants.h"
#import <WebKit/WebKit.h>

// ---------------------------------------------------------------------------
//  SLNetworkMonitor — WKWebView-based network monitor (like One.dylib's)
//  Shows all captured HTTP requests/responses in a scrollable HTML view.
// ---------------------------------------------------------------------------

@interface SLNetworkMonitor () <WKNavigationDelegate>
@property (nonatomic, strong) UIWindow *monitorWindow;
@property (nonatomic, strong) WKWebView *webView;
@end

@implementation SLNetworkMonitor

+ (instancetype)shared {
    static SLNetworkMonitor *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (void)install {
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onNewRequest:)
                                                 name:SLNetworkRequestNotification
                                               object:nil];
}

#pragma mark - Show / Hide

- (void)show {
    if (self.monitorWindow) {
        self.monitorWindow.hidden = NO;
        [self refreshContent];
        return;
    }

    UIWindowScene *scene = nil;
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            break;
        }
    }
    if (!scene) return;

    CGRect bounds = scene.coordinateSpace.bounds;
    CGFloat h = bounds.size.height * 0.6;
    CGRect frame = CGRectMake(0, bounds.size.height - h, bounds.size.width, h);

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = frame;
    win.windowLevel = UIWindowLevelAlert + 150;
    win.backgroundColor = [UIColor clearColor];

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [[UIColor blackColor] colorWithAlphaComponent:0.95];
    win.rootViewController = vc;

    // Close button
    UIButton *closeBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    closeBtn.frame = CGRectMake(frame.size.width - 50, 4, 44, 30);
    [closeBtn setTitle:@"X" forState:UIControlStateNormal];
    [closeBtn setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    closeBtn.titleLabel.font = [UIFont boldSystemFontOfSize:16];
    [closeBtn addTarget:self action:@selector(hide) forControlEvents:UIControlEventTouchUpInside];
    [vc.view addSubview:closeBtn];

    // Title
    UILabel *titleLabel = [[UILabel alloc] initWithFrame:CGRectMake(10, 4, 200, 30)];
    titleLabel.text = @"Network Monitor";
    titleLabel.textColor = [UIColor greenColor];
    titleLabel.font = [UIFont boldSystemFontOfSize:14];
    [vc.view addSubview:titleLabel];

    // Clear button
    UIButton *clearBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    clearBtn.frame = CGRectMake(frame.size.width - 110, 4, 55, 30);
    [clearBtn setTitle:@"Clear" forState:UIControlStateNormal];
    [clearBtn setTitleColor:[UIColor orangeColor] forState:UIControlStateNormal];
    clearBtn.titleLabel.font = [UIFont systemFontOfSize:13];
    [clearBtn addTarget:self action:@selector(clearRequests) forControlEvents:UIControlEventTouchUpInside];
    [vc.view addSubview:clearBtn];

    // WKWebView
    WKWebViewConfiguration *config = [[WKWebViewConfiguration alloc] init];
    WKWebView *wv = [[WKWebView alloc] initWithFrame:CGRectMake(0, 36, frame.size.width, frame.size.height - 36)
                                        configuration:config];
    wv.backgroundColor = [UIColor clearColor];
    wv.opaque = NO;
    wv.scrollView.backgroundColor = [UIColor clearColor];
    wv.navigationDelegate = self;
    [vc.view addSubview:wv];
    self.webView = wv;

    win.hidden = NO;
    self.monitorWindow = win;

    [self refreshContent];
}

- (void)hide {
    self.monitorWindow.hidden = YES;
}

- (void)clearRequests {
    [[SLNetworkStore shared] clear];
    [self refreshContent];
}

#pragma mark - Notification

- (void)onNewRequest:(NSNotification *)note {
    if (!self.monitorWindow.hidden) {
        [self refreshContent];
    }
}

#pragma mark - HTML generation

- (void)refreshContent {
    NSArray<SLCapturedRequest *> *requests = [[SLNetworkStore shared] allRequests];

    NSMutableString *html = [NSMutableString string];
    [html appendString:@"<!doctype html><html><head><meta charset='utf-8'>"
     "<meta name='viewport' content='width=device-width,initial-scale=1'>"
     "<style>"
     "body{background:#111;color:#ddd;font:12px/1.4 monospace;margin:0;padding:8px}"
     ".req{border:1px solid #333;border-radius:4px;margin:4px 0;padding:6px;cursor:pointer}"
     ".req:hover{border-color:#555}"
     ".url{color:#4fc3f7;word-break:break-all;font-size:11px}"
     ".method{color:#81c784;font-weight:bold}"
     ".status{font-weight:bold}"
     ".s2{color:#81c784}.s3{color:#4fc3f7}.s4{color:#e57373}.s5{color:#ef5350}"
     ".dur{color:#aaa;font-size:10px}"
     ".count{color:#888;font-size:11px;padding:4px 0}"
     ".body{color:#aaa;font-size:10px;max-height:100px;overflow:auto;"
     "white-space:pre-wrap;word-break:break-all;margin-top:4px;display:none;"
     "background:#1a1a1a;padding:4px;border-radius:2px}"
     "</style></head><body>"];

    [html appendFormat:@"<div class='count'>%lu requests captured</div>",
     (unsigned long)requests.count];

    // Reverse order — newest first
    for (NSInteger i = requests.count - 1; i >= 0; i--) {
        SLCapturedRequest *r = requests[i];
        NSString *statusClass = @"";
        if (r.statusCode >= 200 && r.statusCode < 300) statusClass = @"s2";
        else if (r.statusCode >= 300 && r.statusCode < 400) statusClass = @"s3";
        else if (r.statusCode >= 400 && r.statusCode < 500) statusClass = @"s4";
        else if (r.statusCode >= 500) statusClass = @"s5";

        NSString *statusStr = r.isFinished ?
            [NSString stringWithFormat:@"%ld", (long)r.statusCode] : @"...";

        NSString *durStr = r.duration > 0 ?
            [NSString stringWithFormat:@"%.0fms", r.duration * 1000] : @"";

        // Truncate URL for display
        NSString *displayUrl = r.url.length > 80 ?
            [[r.url substringToIndex:80] stringByAppendingString:@"..."] : r.url;

        // Escape HTML
        displayUrl = [displayUrl stringByReplacingOccurrencesOfString:@"<" withString:@"&lt;"];
        displayUrl = [displayUrl stringByReplacingOccurrencesOfString:@">" withString:@"&gt;"];

        NSString *bodyPreview = @"";
        if (r.responseData.length > 0) {
            NSString *bodyStr = [[NSString alloc] initWithData:r.responseData encoding:NSUTF8StringEncoding];
            if (bodyStr.length > 500) bodyStr = [[bodyStr substringToIndex:500] stringByAppendingString:@"..."];
            if (bodyStr) {
                bodyStr = [bodyStr stringByReplacingOccurrencesOfString:@"<" withString:@"&lt;"];
                bodyStr = [bodyStr stringByReplacingOccurrencesOfString:@">" withString:@"&gt;"];
                bodyPreview = [NSString stringWithFormat:
                    @"<div class='body' id='b%ld'>%@</div>", (long)i, bodyStr];
            }
        }

        [html appendFormat:
         @"<div class='req' onclick=\"var b=document.getElementById('b%ld');"
         "if(b)b.style.display=b.style.display=='none'?'block':'none'\">"
         "<span class='method'>%@</span> "
         "<span class='status %@'>%@</span> "
         "<span class='dur'>%@</span><br>"
         "<span class='url'>%@</span>"
         "%@</div>",
         (long)i, r.method, statusClass, statusStr, durStr, displayUrl, bodyPreview];
    }

    [html appendString:@"</body></html>"];

    [self.webView loadHTMLString:html baseURL:nil];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
