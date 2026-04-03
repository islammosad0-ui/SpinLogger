#import <UIKit/UIKit.h>
#import "SLCounterOverlay.h"
#import "SLConstants.h"
#import "SLSpinParser.h"

// ---------------------------------------------------------------------------
//  SLDraggableLabel — draggable UILabel that persists position
// ---------------------------------------------------------------------------
@interface SLDraggableLabel : UILabel
@property (nonatomic, copy) NSString *symbolKey;
@end

@implementation SLDraggableLabel

- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    UITouch *touch = [touches anyObject];
    CGPoint prev = [touch previousLocationInView:self.superview];
    CGPoint curr = [touch locationInView:self.superview];
    self.center = CGPointMake(self.center.x + curr.x - prev.x,
                              self.center.y + curr.y - prev.y);
}

- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if (!self.symbolKey) return;
    // Save position into the Speeder_CounterPositions dict (One.dylib compat)
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    NSMutableDictionary *positions =
        [[defaults dictionaryForKey:kSLDefaultsCounterPositions] mutableCopy]
        ?: [NSMutableDictionary dictionary];
    positions[self.symbolKey] = @{
        @"x": @(self.frame.origin.x),
        @"y": @(self.frame.origin.y)
    };
    [defaults setObject:positions forKey:kSLDefaultsCounterPositions];
}

@end

// ---------------------------------------------------------------------------
//  Pass-through window
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
//  SLCounterOverlay
// ---------------------------------------------------------------------------
@interface SLCounterOverlay ()
@property (nonatomic, strong) UIWindow *overlayWindow;
@property (nonatomic, strong) NSMutableDictionary<NSString *, SLDraggableLabel *> *labels;
@property (nonatomic, strong) NSMutableDictionary<NSString *, NSNumber *> *counts;
@property (nonatomic, assign) NSInteger sessionSpinCount;
@property (nonatomic, strong) SLDraggableLabel *sessionLabel;
@end

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

// One.dylib symbol key mapping (hammer, pig, pills, potion, symbol)
static NSString *SLSpeederKey(NSString *sym) {
    static NSDictionary *keyMap;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        keyMap = @{
            kSLSymbolAttack       : @"hammer",
            kSLSymbolSteal        : @"pig",
            kSLSymbolAccumulation : @"pills",
            kSLSymbolShield       : @"potion",
            kSLSymbolSpins        : @"symbol",
            kSLSymbolGoldSack     : @"goldsack"
        };
    });
    return keyMap[sym] ?: sym;
}

@implementation SLCounterOverlay

+ (instancetype)shared {
    static SLCounterOverlay *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (void)install {
    NSArray<NSString *> *symbols = SLTrackedSymbols();
    NSDictionary<NSString *, NSString *> *emojiMap = SLEmojiMap();

    self.counts = [NSMutableDictionary dictionary];
    self.labels = [NSMutableDictionary dictionary];
    self.sessionSpinCount = 0;

    for (NSString *sym in symbols) {
        self.counts[sym] = @0;
    }

    UIWindowScene *scene = nil;
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            if (s.activationState == UISceneActivationStateForegroundActive) break;
        }
    }
    if (!scene) return;

    SLPassthroughWindow *window = [[SLPassthroughWindow alloc] initWithWindowScene:scene];
    window.windowLevel = UIWindowLevelAlert + 100;
    window.backgroundColor = [UIColor clearColor];
    window.userInteractionEnabled = YES;
    window.rootViewController = [[UIViewController alloc] init];
    window.rootViewController.view.backgroundColor = [UIColor clearColor];
    window.rootViewController.view.userInteractionEnabled = YES;
    self.overlayWindow = window;

    UIView *container = window.rootViewController.view;
    NSDictionary *savedPositions =
        [[NSUserDefaults standardUserDefaults] dictionaryForKey:kSLDefaultsCounterPositions];

    NSInteger tag = 0;
    CGFloat startY = 600.0;

    for (NSString *sym in symbols) {
        SLDraggableLabel *label = [self makeLabelWithTag:tag];
        label.backgroundColor = [[UIColor blackColor] colorWithAlphaComponent:0.6];
        label.symbolKey = SLSpeederKey(sym);

        NSString *emoji = emojiMap[sym] ?: @"❓";
        label.text = [NSString stringWithFormat:@"%@ 0", emoji];

        CGFloat x = 10.0;
        CGFloat y = startY + tag * 40.0;

        // Restore from Speeder_CounterPositions (One.dylib format)
        NSDictionary *savedPos = savedPositions[label.symbolKey];
        if (savedPos) {
            x = [savedPos[@"x"] doubleValue];
            y = [savedPos[@"y"] doubleValue];
        }

        label.frame = CGRectMake(x, y, 80, 32);
        [container addSubview:label];
        self.labels[sym] = label;
        tag++;
    }

    // Session spin counter
    SLDraggableLabel *sessionLabel = [self makeLabelWithTag:tag];
    sessionLabel.backgroundColor = [[UIColor blueColor] colorWithAlphaComponent:0.6];
    sessionLabel.text = @"Spins: 0";
    sessionLabel.symbolKey = @"session";

    CGFloat sx = 10.0, sy = startY + tag * 40.0;
    NSDictionary *sessionPos = savedPositions[@"session"];
    if (sessionPos) {
        sx = [sessionPos[@"x"] doubleValue];
        sy = [sessionPos[@"y"] doubleValue];
    }
    sessionLabel.frame = CGRectMake(sx, sy, 80, 32);
    [container addSubview:sessionLabel];
    self.sessionLabel = sessionLabel;

    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification
                                               object:nil];
    window.hidden = NO;
}

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

- (void)show  { self.overlayWindow.hidden = NO; }
- (void)hide  { self.overlayWindow.hidden = YES; }

- (void)resetAllCounters {
    for (NSString *sym in self.counts.allKeys) self.counts[sym] = @0;
    self.sessionSpinCount = 0;
    [self updateLabels];
}

- (void)resetCounterForSymbol:(NSString *)symbol {
    if (self.counts[symbol]) self.counts[symbol] = @0;
    [self updateLabels];
}

- (NSDictionary<NSString *, NSNumber *> *)currentCounts {
    return [self.counts copy];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
