#import <UIKit/UIKit.h>
#import "SLCounterOverlay.h"
#import "SLConstants.h"
#import "SLSpinParser.h"

// ---------------------------------------------------------------------------
//  SLDraggableLabel — a UILabel that can be dragged and persists its position
// ---------------------------------------------------------------------------
@interface SLDraggableLabel : UILabel
@end

@implementation SLDraggableLabel

- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    UITouch *touch = [touches anyObject];
    CGPoint prev = [touch previousLocationInView:self.superview];
    CGPoint curr = [touch locationInView:self.superview];
    CGPoint center = self.center;
    center.x += curr.x - prev.x;
    center.y += curr.y - prev.y;
    self.center = center;
}

- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    NSString *key = [NSString stringWithFormat:@"SpinLogger_Pos_%ld", (long)self.tag];
    NSDictionary *pos = @{
        @"x" : @(self.frame.origin.x),
        @"y" : @(self.frame.origin.y)
    };
    [[NSUserDefaults standardUserDefaults] setObject:pos forKey:key];
}

@end

// ---------------------------------------------------------------------------
//  Pass-through window — lets touches fall through to the app beneath
// ---------------------------------------------------------------------------
@interface SLPassthroughWindow : UIWindow
@end

@implementation SLPassthroughWindow

- (BOOL)pointInside:(CGPoint)point withEvent:(UIEvent *)event {
    for (UIView *subview in self.rootViewController.view.subviews) {
        if (!subview.hidden && subview.alpha > 0.01 &&
            [subview pointInside:[self convertPoint:point toView:subview] withEvent:event]) {
            return YES;
        }
    }
    return NO;
}

@end

// ---------------------------------------------------------------------------
//  SLCounterOverlay private interface
// ---------------------------------------------------------------------------
@interface SLCounterOverlay ()
@property (nonatomic, strong) UIWindow *overlayWindow;
@property (nonatomic, strong) NSMutableDictionary<NSString *, SLDraggableLabel *> *labels;
@property (nonatomic, strong) NSMutableDictionary<NSString *, NSNumber *> *counts;
@property (nonatomic, assign) NSInteger sessionSpinCount;
@property (nonatomic, strong) SLDraggableLabel *sessionLabel;
@end

// ---------------------------------------------------------------------------
//  Emoji lookup
// ---------------------------------------------------------------------------
static NSDictionary<NSString *, NSString *> *SLEmojiMap(void) {
    static NSDictionary *map;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        map = @{
            kSLSymbolAttack       : @"🔨",
            kSLSymbolSteal        : @"🐷",
            kSLSymbolAccumulation : @"⭐",
            kSLSymbolShield       : @"🛡",
            kSLSymbolSpins        : @"🎰",
            kSLSymbolGoldSack     : @"💰"
        };
    });
    return map;
}

// ---------------------------------------------------------------------------
//  SLCounterOverlay implementation
// ---------------------------------------------------------------------------
@implementation SLCounterOverlay

+ (instancetype)shared {
    static SLCounterOverlay *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

// ---- install -------------------------------------------------------------
- (void)install {
    NSArray<NSString *> *symbols = SLTrackedSymbols();
    NSDictionary<NSString *, NSString *> *emojiMap = SLEmojiMap();

    self.counts = [NSMutableDictionary dictionary];
    self.labels = [NSMutableDictionary dictionary];
    self.sessionSpinCount = 0;

    for (NSString *sym in symbols) {
        self.counts[sym] = @0;
    }

    // -- obtain a UIWindowScene ------------------------------------------------
    UIWindowScene *scene = nil;
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if (s.activationState == UISceneActivationStateForegroundActive &&
            [s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            break;
        }
    }
    if (!scene) {
        // Fallback: grab the first UIWindowScene regardless of state
        for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
            if ([s isKindOfClass:[UIWindowScene class]]) {
                scene = (UIWindowScene *)s;
                break;
            }
        }
    }

    // -- create pass-through window -------------------------------------------
    SLPassthroughWindow *window = [[SLPassthroughWindow alloc] initWithWindowScene:scene];
    window.windowLevel = UIWindowLevelAlert + 100;
    window.backgroundColor = [UIColor clearColor];
    window.userInteractionEnabled = YES;
    window.rootViewController = [[UIViewController alloc] init];
    window.rootViewController.view.backgroundColor = [UIColor clearColor];
    window.rootViewController.view.userInteractionEnabled = YES;
    self.overlayWindow = window;

    UIView *container = window.rootViewController.view;
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];

    // -- create one label per tracked symbol ----------------------------------
    NSInteger tag = 0;
    CGFloat startY = 600.0;

    for (NSString *sym in symbols) {
        SLDraggableLabel *label = [self makeLabelWithTag:tag];
        label.backgroundColor = [[UIColor blackColor] colorWithAlphaComponent:0.6];

        NSString *emoji = emojiMap[sym] ?: @"❓";
        label.text = [NSString stringWithFormat:@"%@ 0", emoji];

        // Default position
        CGFloat x = 10.0;
        CGFloat y = startY + tag * 40.0;

        // Restore saved position if available
        NSString *posKey = [NSString stringWithFormat:@"SpinLogger_Pos_%ld", (long)tag];
        NSDictionary *savedPos = [defaults objectForKey:posKey];
        if (savedPos) {
            x = [savedPos[@"x"] doubleValue];
            y = [savedPos[@"y"] doubleValue];
        }

        label.frame = CGRectMake(x, y, 80, 32);
        [container addSubview:label];
        self.labels[sym] = label;

        tag++;
    }

    // -- session spin counter label -------------------------------------------
    SLDraggableLabel *sessionLabel = [self makeLabelWithTag:tag];
    sessionLabel.backgroundColor = [[UIColor blueColor] colorWithAlphaComponent:0.6];
    sessionLabel.text = @"Spins: 0";

    CGFloat sx = 10.0;
    CGFloat sy = startY + tag * 40.0;
    NSString *sessionPosKey = [NSString stringWithFormat:@"SpinLogger_Pos_%ld", (long)tag];
    NSDictionary *savedSessionPos = [defaults objectForKey:sessionPosKey];
    if (savedSessionPos) {
        sx = [savedSessionPos[@"x"] doubleValue];
        sy = [savedSessionPos[@"y"] doubleValue];
    }
    sessionLabel.frame = CGRectMake(sx, sy, 80, 32);
    [container addSubview:sessionLabel];
    self.sessionLabel = sessionLabel;

    // -- register for spin notifications -------------------------------------
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification
                                               object:nil];

    // -- show -----------------------------------------------------------------
    window.hidden = NO;
}

// ---- helper: create a styled label ----------------------------------------
- (SLDraggableLabel *)makeLabelWithTag:(NSInteger)tag {
    SLDraggableLabel *label = [[SLDraggableLabel alloc] init];
    label.tag = tag;
    label.frame = CGRectMake(0, 0, 80, 32);
    label.font = [UIFont boldSystemFontOfSize:14];
    label.textColor = [UIColor whiteColor];
    label.textAlignment = NSTextAlignmentCenter;
    label.layer.cornerRadius = 8;
    label.clipsToBounds = YES;
    label.userInteractionEnabled = YES;
    return label;
}

// ---- notification handler -------------------------------------------------
- (void)onSpinReceived:(NSNotification *)note {
    self.sessionSpinCount++;

    SLSpinResult *result = note.userInfo[SLSpinDataKey];
    if (!result) return;

    NSArray<NSString *> *reels = @[];
    if (result.reel1) reels = [reels arrayByAddingObject:result.reel1];
    if (result.reel2) reels = [reels arrayByAddingObject:result.reel2];
    if (result.reel3) reels = [reels arrayByAddingObject:result.reel3];

    for (NSString *sym in reels) {
        NSNumber *current = self.counts[sym];
        if (current) {
            self.counts[sym] = @(current.integerValue + 1);
        } else {
            self.counts[sym] = @1;
        }
    }

    [self updateLabels];
}

// ---- update all label texts -----------------------------------------------
- (void)updateLabels {
    NSDictionary<NSString *, NSString *> *emojiMap = SLEmojiMap();

    for (NSString *sym in self.labels) {
        SLDraggableLabel *label = self.labels[sym];
        NSString *emoji = emojiMap[sym] ?: @"❓";
        NSInteger count = [self.counts[sym] integerValue];
        label.text = [NSString stringWithFormat:@"%@ %ld", emoji, (long)count];
    }

    self.sessionLabel.text = [NSString stringWithFormat:@"Spins: %ld",
                              (long)self.sessionSpinCount];
}

// ---- show / hide ----------------------------------------------------------
- (void)show {
    self.overlayWindow.hidden = NO;
}

- (void)hide {
    self.overlayWindow.hidden = YES;
}

// ---- reset ----------------------------------------------------------------
- (void)resetAllCounters {
    for (NSString *sym in self.counts.allKeys) {
        self.counts[sym] = @0;
    }
    self.sessionSpinCount = 0;
    [self updateLabels];
}

- (void)resetCounterForSymbol:(NSString *)symbol {
    if (self.counts[symbol]) {
        self.counts[symbol] = @0;
    }
    [self updateLabels];
}

// ---- current counts -------------------------------------------------------
- (NSDictionary<NSString *, NSNumber *> *)currentCounts {
    return [self.counts copy];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
