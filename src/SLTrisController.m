#import "SLTrisController.h"
#import "SLConstants.h"

@implementation SLTrisController

+ (instancetype)shared {
    static SLTrisController *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
        _lockTarget  = [defaults stringForKey:kSLDefaultsTrisLockTarget];
        _skipEnabled = [defaults boolForKey:kSLDefaultsTrisSkipEnabled];
    }
    return self;
}

#pragma mark - Install

- (void)install {
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onTrisEvent:)
                                                 name:@"SLTrisEventNotification"
                                               object:nil];
    NSLog(@"[SpinLogger] SLTrisController installed (lockTarget=%@, skipEnabled=%d)",
          _lockTarget ?: @"(none)", _skipEnabled);
}

#pragma mark - Notification handler

- (void)onTrisEvent:(NSNotification *)notification {
    NSString *cardId = notification.userInfo[@"card_id"];
    if (!cardId) return;

    if (_lockTarget && [cardId isEqualToString:_lockTarget]) {
        NSLog(@"[SpinLogger] LOCK HIT — card %@ matches target", cardId);
        return;
    }

    if (_skipEnabled) {
        NSLog(@"[SpinLogger] Tris skip — card %@ does not match lock target %@",
              cardId, _lockTarget ?: @"(none)");
    }
}

#pragma mark - Custom setters (persist to NSUserDefaults)

- (void)setLockTarget:(NSString *)lockTarget {
    _lockTarget = [lockTarget copy];
    [[NSUserDefaults standardUserDefaults] setObject:_lockTarget
                                              forKey:kSLDefaultsTrisLockTarget];
}

- (void)setSkipEnabled:(BOOL)skipEnabled {
    _skipEnabled = skipEnabled;
    [[NSUserDefaults standardUserDefaults] setBool:_skipEnabled
                                            forKey:kSLDefaultsTrisSkipEnabled];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
