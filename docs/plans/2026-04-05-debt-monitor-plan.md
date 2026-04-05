# SLDebtMonitor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build real-time debt autocorrection + quiet zone betting tiles for ACC and SPN triples in the SpinLogger iOS dylib.

**Architecture:** Model+View split — `SLDebtTracker` (pure logic: debt, floor, quiet zone, phase) + `SLDebtMonitor` (two draggable UIWindow tiles with glow + haptic). Follows existing singleton + notification pattern.

**Tech Stack:** Objective-C, UIKit, CoreAnimation, NSUserDefaults, SLSpinReceivedNotification

---

### Task 1: Create SLDebtTracker Header

**Files:**
- Create: `src/SLDebtTracker.h`

**Step 1: Write the header**

```objc
#import <Foundation/Foundation.h>

@class SLSpinResult;

typedef NS_ENUM(NSInteger, SLDebtPhase) {
    SLDebtPhaseWaiting,   // below floor — no action
    SLDebtPhaseWatch,     // above floor — paying attention
    SLDebtPhaseBetNow     // above floor + quiet zone — MAX BET
};

@interface SLDebtTrackerConfig : NSObject
@property (nonatomic, assign) NSInteger target;      // expected gap (ACC=100, SPN=87)
@property (nonatomic, assign) NSInteger floorBase;   // base floor (ACC=80, SPN=65)
@property (nonatomic, assign) NSInteger floorMin;    // absolute min floor (20)
@property (nonatomic, assign) NSInteger quietMin;    // min silence spins (3)
@property (nonatomic, assign) NSInteger quietMax;    // max silence spins (7)
@property (nonatomic, assign) NSInteger betWindow;   // max bet spins (8)
+ (instancetype)accDefaults;
+ (instancetype)spnDefaults;
@end

@interface SLDebtTracker : NSObject
@property (nonatomic, strong) SLDebtTrackerConfig *config;
@property (nonatomic, assign, readonly) NSInteger debt;
@property (nonatomic, assign, readonly) NSInteger saSpins;
@property (nonatomic, assign, readonly) NSInteger quietSpins;
@property (nonatomic, assign, readonly) BOOL inQuietZone;
@property (nonatomic, assign, readonly) BOOL quietTriggered; // non-target triple seen, counting silence
@property (nonatomic, assign, readonly) NSInteger betSpinsUsed; // spins in BetNow phase
@property (nonatomic, assign, readonly) SLDebtPhase phase;
- (instancetype)initWithConfig:(SLDebtTrackerConfig *)config;
- (void)onSpin:(SLSpinResult *)spin isTargetTriple:(BOOL)isTarget isOtherTriple:(BOOL)isOther;
- (NSInteger)watchPoint;
- (void)reset;
- (NSDictionary *)stateDictionary;
- (void)restoreFromDictionary:(NSDictionary *)dict;
@end
```

**Step 2: Commit**

```bash
git add src/SLDebtTracker.h
git commit -m "feat(debt): add SLDebtTracker header — phase enum, config, tracker interface"
```

---

### Task 2: Implement SLDebtTracker

**Files:**
- Create: `src/SLDebtTracker.m`

**Step 1: Write the implementation**

```objc
#import "SLDebtTracker.h"
#import "SLSpinParser.h"

@implementation SLDebtTrackerConfig

+ (instancetype)accDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    c.target = 100; c.floorBase = 80; c.floorMin = 20;
    c.quietMin = 3; c.quietMax = 7; c.betWindow = 8;
    return c;
}

+ (instancetype)spnDefaults {
    SLDebtTrackerConfig *c = [[self alloc] init];
    c.target = 87; c.floorBase = 65; c.floorMin = 20;
    c.quietMin = 3; c.quietMax = 7; c.betWindow = 8;
    return c;
}

@end

@interface SLDebtTracker ()
@property (nonatomic, assign, readwrite) NSInteger debt;
@property (nonatomic, assign, readwrite) NSInteger saSpins;
@property (nonatomic, assign, readwrite) NSInteger quietSpins;
@property (nonatomic, assign, readwrite) BOOL inQuietZone;
@property (nonatomic, assign, readwrite) BOOL quietTriggered;
@property (nonatomic, assign, readwrite) NSInteger betSpinsUsed;
@property (nonatomic, assign, readwrite) SLDebtPhase phase;
@end

@implementation SLDebtTracker

- (instancetype)initWithConfig:(SLDebtTrackerConfig *)config {
    self = [super init];
    if (self) {
        _config = config;
        _debt = 0; _saSpins = 0; _quietSpins = 0;
        _inQuietZone = NO; _quietTriggered = NO;
        _betSpinsUsed = 0; _phase = SLDebtPhaseWaiting;
    }
    return self;
}

- (NSInteger)watchPoint {
    return MAX(self.config.floorMin, self.config.floorBase - self.debt);
}

- (void)onSpin:(SLSpinResult *)spin isTargetTriple:(BOOL)isTarget isOtherTriple:(BOOL)isOther {
    self.saSpins++;

    // --- Handle target triple hit ---
    if (isTarget) {
        NSInteger gap = self.saSpins;
        self.debt += (gap - self.config.target);
        self.saSpins = 0;
        self.quietSpins = 0;
        self.quietTriggered = NO;
        self.inQuietZone = NO;
        self.betSpinsUsed = 0;
        self.phase = SLDebtPhaseWaiting;
        return;
    }

    // --- Handle non-target triple (combat/spins/gold) ---
    if (isOther) {
        self.quietTriggered = YES;
        self.quietSpins = 0;
        self.inQuietZone = NO;
    }

    // --- Quiet zone tracking ---
    if (self.quietTriggered) {
        if (!isOther) { // only count non-triple spins as silence
            self.quietSpins++;
        }
        self.inQuietZone = (self.quietSpins >= self.config.quietMin &&
                            self.quietSpins <= self.config.quietMax);
    }

    // --- Phase computation ---
    NSInteger wp = [self watchPoint];

    if (self.saSpins < wp) {
        self.phase = SLDebtPhaseWaiting;
        self.betSpinsUsed = 0;
    } else if (self.inQuietZone && self.betSpinsUsed < self.config.betWindow) {
        if (self.phase != SLDebtPhaseBetNow) {
            self.betSpinsUsed = 0; // just entered BetNow
        }
        self.phase = SLDebtPhaseBetNow;
        self.betSpinsUsed++;
    } else {
        self.phase = SLDebtPhaseWatch;
    }
}

- (void)reset {
    self.debt = 0; self.saSpins = 0; self.quietSpins = 0;
    self.inQuietZone = NO; self.quietTriggered = NO;
    self.betSpinsUsed = 0; self.phase = SLDebtPhaseWaiting;
}

- (NSDictionary *)stateDictionary {
    return @{
        @"debt":           @(self.debt),
        @"saSpins":        @(self.saSpins),
        @"quietSpins":     @(self.quietSpins),
        @"quietTriggered": @(self.quietTriggered),
        @"inQuietZone":    @(self.inQuietZone),
        @"betSpinsUsed":   @(self.betSpinsUsed),
        @"phase":          @(self.phase),
        @"target":         @(self.config.target),
        @"floorBase":      @(self.config.floorBase),
        @"floorMin":       @(self.config.floorMin),
        @"quietMin":       @(self.config.quietMin),
        @"quietMax":       @(self.config.quietMax),
        @"betWindow":      @(self.config.betWindow),
    };
}

- (void)restoreFromDictionary:(NSDictionary *)dict {
    if (!dict) return;
    self.debt           = [dict[@"debt"] integerValue];
    self.saSpins        = [dict[@"saSpins"] integerValue];
    self.quietSpins     = [dict[@"quietSpins"] integerValue];
    self.quietTriggered = [dict[@"quietTriggered"] boolValue];
    self.inQuietZone    = [dict[@"inQuietZone"] boolValue];
    self.betSpinsUsed   = [dict[@"betSpinsUsed"] integerValue];
    self.phase          = (SLDebtPhase)[dict[@"phase"] integerValue];
    // Restore config overrides
    if (dict[@"target"])    self.config.target    = [dict[@"target"] integerValue];
    if (dict[@"floorBase"]) self.config.floorBase = [dict[@"floorBase"] integerValue];
    if (dict[@"floorMin"])  self.config.floorMin  = [dict[@"floorMin"] integerValue];
    if (dict[@"quietMin"])  self.config.quietMin  = [dict[@"quietMin"] integerValue];
    if (dict[@"quietMax"])  self.config.quietMax  = [dict[@"quietMax"] integerValue];
    if (dict[@"betWindow"]) self.config.betWindow = [dict[@"betWindow"] integerValue];
}

@end
```

**Step 2: Commit**

```bash
git add src/SLDebtTracker.m
git commit -m "feat(debt): implement SLDebtTracker — debt calc, quiet zone, phase logic"
```

---

### Task 3: Create SLDebtMonitor Header

**Files:**
- Create: `src/SLDebtMonitor.h`

**Step 1: Write the header**

```objc
#import <Foundation/Foundation.h>

@interface SLDebtMonitor : NSObject
+ (instancetype)shared;
- (void)install;
- (void)show;
- (void)hide;
@end
```

**Step 2: Commit**

```bash
git add src/SLDebtMonitor.h
git commit -m "feat(debt): add SLDebtMonitor header — singleton interface"
```

---

### Task 4: Implement SLDebtMonitor — Singleton, Tiles, Notification Wiring

**Files:**
- Create: `src/SLDebtMonitor.m`

This is the largest task. The implementation wires up two draggable UIWindow tiles (ACC + SPN), listens to `SLSpinReceivedNotification`, forwards spins to both `SLDebtTracker` instances, updates UI, and triggers glow + haptic on BetNow.

**Step 1: Write the implementation**

```objc
#import <UIKit/UIKit.h>
#import "SLDebtMonitor.h"
#import "SLDebtTracker.h"
#import "SLConstants.h"
#import "SLSpinParser.h"

// ---------------------------------------------------------------------------
//  SLDebtTile — one draggable UIWindow for a single tracker (ACC or SPN)
// ---------------------------------------------------------------------------
@interface SLDebtTile : NSObject
@property (nonatomic, strong) UIWindow *window;
@property (nonatomic, strong) UIView *container;
@property (nonatomic, strong) UILabel *debtLabel;     // emoji + debt value
@property (nonatomic, strong) UILabel *progressLabel; // saSpins / watchPoint
@property (nonatomic, strong) UILabel *phaseLabel;    // WAIT / WATCH / BET NOW
@property (nonatomic, strong) SLDebtTracker *tracker;
@property (nonatomic, copy)   NSString *emoji;
@property (nonatomic, copy)   NSString *defaultsKey;  // persistence key
@property (nonatomic, copy)   NSString *posXKey;
@property (nonatomic, copy)   NSString *posYKey;
@property (nonatomic, assign) BOOL compact;
@property (nonatomic, assign) BOOL glowing;
// Glow color (green for ACC, blue for SPN)
@property (nonatomic, strong) UIColor *glowColor;
@property (nonatomic, strong) UIColor *watchBorderColor;
@end

@implementation SLDebtTile
@end

// ---------------------------------------------------------------------------
//  SLDebtMonitor
// ---------------------------------------------------------------------------
@interface SLDebtMonitor ()
@property (nonatomic, strong) SLDebtTile *accTile;
@property (nonatomic, strong) SLDebtTile *spnTile;
@property (nonatomic, copy)   NSString *lastEventID;
@property (nonatomic, strong) UIImpactFeedbackGenerator *haptic;
@end

@implementation SLDebtMonitor

+ (instancetype)shared {
    static SLDebtMonitor *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _haptic = [[UIImpactFeedbackGenerator alloc] initWithStyle:UIImpactFeedbackStyleHeavy];
        _lastEventID = [[NSUserDefaults standardUserDefaults] stringForKey:@"Speeder_DebtEventID"];
    }
    return self;
}

#pragma mark - Install

- (void)install {
    UIWindowScene *scene = nil;
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            if (s.activationState == UISceneActivationStateForegroundActive) break;
        }
    }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;

    // --- ACC tile (gold star, green glow) ---
    self.accTile = [self buildTileInScene:scene
                                    emoji:@"⭐"
                                 glowColor:[UIColor colorWithRed:0.2 green:1.0 blue:0.3 alpha:1.0]
                            watchBorderColor:[UIColor colorWithRed:1.0 green:0.75 blue:0.0 alpha:0.8]
                                  tracker:[[SLDebtTracker alloc] initWithConfig:[SLDebtTrackerConfig accDefaults]]
                              defaultsKey:@"Speeder_DebtACC"
                                  posXKey:@"Speeder_DebtACCX"
                                  posYKey:@"Speeder_DebtACCY"
                               defaultPos:CGPointMake(screen.size.width - 100, screen.size.height * 0.3)
                              windowLevel:UIWindowLevelAlert + 260];

    // --- SPN tile (pill, blue glow) ---
    self.spnTile = [self buildTileInScene:scene
                                    emoji:@"💊"
                                 glowColor:[UIColor colorWithRed:0.2 green:0.5 blue:1.0 alpha:1.0]
                            watchBorderColor:[UIColor colorWithRed:1.0 green:0.75 blue:0.0 alpha:0.8]
                                  tracker:[[SLDebtTracker alloc] initWithConfig:[SLDebtTrackerConfig spnDefaults]]
                              defaultsKey:@"Speeder_DebtSPN"
                                  posXKey:@"Speeder_DebtSPNX"
                                  posYKey:@"Speeder_DebtSPNY"
                               defaultPos:CGPointMake(screen.size.width - 100, screen.size.height * 0.3 + 70)
                              windowLevel:UIWindowLevelAlert + 261];

    [self restoreState];
    [self updateTileUI:self.accTile];
    [self updateTileUI:self.spnTile];

    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification object:nil];
    NSLog(@"[SpinLogger] DebtMonitor installed (ACC target=%ld, SPN target=%ld)",
          (long)self.accTile.tracker.config.target,
          (long)self.spnTile.tracker.config.target);
}

#pragma mark - Build Tile

- (SLDebtTile *)buildTileInScene:(UIWindowScene *)scene
                           emoji:(NSString *)emoji
                        glowColor:(UIColor *)glowColor
                   watchBorderColor:(UIColor *)watchBorderColor
                         tracker:(SLDebtTracker *)tracker
                     defaultsKey:(NSString *)defaultsKey
                         posXKey:(NSString *)posXKey
                         posYKey:(NSString *)posYKey
                      defaultPos:(CGPoint)defaultPos
                     windowLevel:(UIWindowLevel)windowLevel {
    SLDebtTile *tile = [[SLDebtTile alloc] init];
    tile.tracker = tracker;
    tile.emoji = emoji;
    tile.glowColor = glowColor;
    tile.watchBorderColor = watchBorderColor;
    tile.defaultsKey = defaultsKey;
    tile.posXKey = posXKey;
    tile.posYKey = posYKey;
    tile.compact = NO;
    tile.glowing = NO;

    CGFloat tileW = 90, tileH = 60;

    // Restore position
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    CGFloat x = [ud doubleForKey:posXKey];
    CGFloat y = [ud doubleForKey:posYKey];
    if (x == 0 && y == 0) { x = defaultPos.x; y = defaultPos.y; }

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, y, tileW, tileH);
    win.windowLevel = windowLevel;
    win.backgroundColor = [UIColor clearColor];

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = [UIColor clearColor];
    win.rootViewController = vc;

    // Container
    UIView *container = [[UIView alloc] initWithFrame:CGRectMake(0, 0, tileW, tileH)];
    container.backgroundColor = [UIColor colorWithRed:0.06 green:0.08 blue:0.14 alpha:0.94];
    container.layer.cornerRadius = 12;
    container.layer.borderWidth = 1.0;
    container.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.06].CGColor;
    container.clipsToBounds = NO; // need overflow for glow shadow
    [vc.view addSubview:container];
    tile.container = container;

    // Debt label (top) — emoji + debt
    UILabel *debtLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 2, tileW - 8, 18)];
    debtLabel.font = [UIFont boldSystemFontOfSize:13];
    debtLabel.textColor = [UIColor whiteColor];
    debtLabel.textAlignment = NSTextAlignmentCenter;
    debtLabel.text = [NSString stringWithFormat:@"%@ 0", emoji];
    [container addSubview:debtLabel];
    tile.debtLabel = debtLabel;

    // Progress label (middle) — saSpins / watchPoint
    UILabel *progressLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 20, tileW - 8, 16)];
    progressLabel.font = [UIFont monospacedDigitSystemFontOfSize:11 weight:UIFontWeightMedium];
    progressLabel.textColor = [UIColor colorWithWhite:0.7 alpha:1.0];
    progressLabel.textAlignment = NSTextAlignmentCenter;
    progressLabel.text = @"0 / 80";
    [container addSubview:progressLabel];
    tile.progressLabel = progressLabel;

    // Phase label (bottom) — WAIT / WATCH / BET NOW
    UILabel *phaseLabel = [[UILabel alloc] initWithFrame:CGRectMake(4, 38, tileW - 8, 18)];
    phaseLabel.font = [UIFont boldSystemFontOfSize:12];
    phaseLabel.textAlignment = NSTextAlignmentCenter;
    phaseLabel.text = @"WAIT";
    phaseLabel.textColor = [UIColor colorWithWhite:0.4 alpha:1.0];
    [container addSubview:phaseLabel];
    tile.phaseLabel = phaseLabel;

    // Pan gesture
    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc]
        initWithTarget:self action:@selector(handlePan:)];
    [vc.view addGestureRecognizer:pan];

    // Tap gesture — toggle compact/expanded
    UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc]
        initWithTarget:self action:@selector(handleTap:)];
    [vc.view addGestureRecognizer:tap];

    // Long press — config menu
    UILongPressGestureRecognizer *longPress = [[UILongPressGestureRecognizer alloc]
        initWithTarget:self action:@selector(handleLongPress:)];
    [vc.view addGestureRecognizer:longPress];

    // Tag the vc.view so we know which tile
    vc.view.tag = [emoji isEqualToString:@"⭐"] ? 0 : 1;

    win.hidden = NO;
    tile.window = win;
    return tile;
}

#pragma mark - Spin Handling

- (void)onSpinReceived:(NSNotification *)note {
    SLSpinResult *result = note.userInfo[SLSpinDataKey];
    if (!result) return;

    // --- Event change detection ---
    NSString *eventID = result.gaeSegment;
    if (eventID.length > 0 && self.lastEventID.length > 0 &&
        ![eventID isEqualToString:self.lastEventID]) {
        [self.accTile.tracker reset];
        [self.spnTile.tracker reset];
        NSLog(@"[DebtMonitor] Event changed: %@ -> %@, reset both trackers", self.lastEventID, eventID);
    }
    if (eventID.length > 0) {
        self.lastEventID = eventID;
        [[NSUserDefaults standardUserDefaults] setObject:eventID forKey:@"Speeder_DebtEventID"];
    }

    // --- Detect triples ---
    BOOL isTriple = (result.reel1 && [result.reel1 isEqualToString:result.reel2] &&
                     [result.reel2 isEqualToString:result.reel3]);
    BOOL isAccTriple = isTriple && [result.reel1 isEqualToString:kSLSymbolAccumulation];
    BOOL isSpnTriple = isTriple && [result.reel1 isEqualToString:kSLSymbolSpins];
    BOOL isCombatTriple = isTriple && ([result.reel1 isEqualToString:kSLSymbolAttack] ||
                                        [result.reel1 isEqualToString:kSLSymbolSteal] ||
                                        [result.reel1 isEqualToString:kSLSymbolShield] ||
                                        [result.reel1 isEqualToString:kSLSymbolSpins]);

    // ACC tracker: target = accumulation triple, other = any combat/spins triple
    SLDebtPhase prevAccPhase = self.accTile.tracker.phase;
    [self.accTile.tracker onSpin:result isTargetTriple:isAccTriple isOtherTriple:(isCombatTriple && !isAccTriple)];

    // SPN tracker: target = spins triple, other = any combat triple (not spins itself)
    SLDebtPhase prevSpnPhase = self.spnTile.tracker.phase;
    BOOL isNonSpnCombat = isTriple && ([result.reel1 isEqualToString:kSLSymbolAttack] ||
                                        [result.reel1 isEqualToString:kSLSymbolSteal] ||
                                        [result.reel1 isEqualToString:kSLSymbolShield] ||
                                        [result.reel1 isEqualToString:kSLSymbolAccumulation]);
    [self.spnTile.tracker onSpin:result isTargetTriple:isSpnTriple isOtherTriple:isNonSpnCombat];

    // --- Update UI ---
    [self updateTileUI:self.accTile];
    [self updateTileUI:self.spnTile];

    // --- Haptic on phase transition to BetNow ---
    if ((self.accTile.tracker.phase == SLDebtPhaseBetNow && prevAccPhase != SLDebtPhaseBetNow) ||
        (self.spnTile.tracker.phase == SLDebtPhaseBetNow && prevSpnPhase != SLDebtPhaseBetNow)) {
        [self.haptic impactOccurred];
    }

    // --- Glow control ---
    [self updateGlow:self.accTile];
    [self updateGlow:self.spnTile];

    [self saveState];
}

#pragma mark - UI Update

- (void)updateTileUI:(SLDebtTile *)tile {
    SLDebtTracker *t = tile.tracker;
    NSInteger wp = [t watchPoint];

    // Debt label
    NSString *debtSign = (t.debt >= 0) ? @"+" : @"";
    tile.debtLabel.text = [NSString stringWithFormat:@"%@ %@%ld", tile.emoji, debtSign, (long)t.debt];

    // Progress label
    tile.progressLabel.text = [NSString stringWithFormat:@"%ld / %ld", (long)t.saSpins, (long)wp];
    tile.progressLabel.hidden = tile.compact;

    // Phase label
    switch (t.phase) {
        case SLDebtPhaseWaiting:
            tile.phaseLabel.text = @"WAIT";
            tile.phaseLabel.textColor = [UIColor colorWithWhite:0.4 alpha:1.0];
            tile.container.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.06].CGColor;
            tile.container.layer.borderWidth = 1.0;
            break;
        case SLDebtPhaseWatch:
            tile.phaseLabel.text = @"WATCH";
            tile.phaseLabel.textColor = [UIColor colorWithRed:1.0 green:0.75 blue:0.0 alpha:1.0];
            tile.container.layer.borderColor = tile.watchBorderColor.CGColor;
            tile.container.layer.borderWidth = 1.5;
            break;
        case SLDebtPhaseBetNow:
            tile.phaseLabel.text = @"BET NOW";
            tile.phaseLabel.textColor = tile.glowColor;
            break;
    }

    // Resize for compact mode
    CGRect f = tile.window.frame;
    f.size.height = tile.compact ? 30 : 60;
    f.size.width  = tile.compact ? 56 : 90;
    tile.window.frame = f;
    tile.container.frame = CGRectMake(0, 0, f.size.width, f.size.height);
}

#pragma mark - Glow Animation

- (void)updateGlow:(SLDebtTile *)tile {
    BOOL shouldGlow = (tile.tracker.phase == SLDebtPhaseBetNow);

    if (shouldGlow && !tile.glowing) {
        tile.glowing = YES;
        [self startGlow:tile];
    } else if (!shouldGlow && tile.glowing) {
        tile.glowing = NO;
        [self stopGlow:tile];
    }
}

- (void)startGlow:(SLDebtTile *)tile {
    CALayer *layer = tile.container.layer;
    layer.shadowColor = tile.glowColor.CGColor;
    layer.shadowOffset = CGSizeZero;
    layer.shadowOpacity = 0.0;
    layer.shadowRadius = 0;

    CABasicAnimation *anim = [CABasicAnimation animationWithKeyPath:@"shadowOpacity"];
    anim.fromValue = @(0.3);
    anim.toValue = @(1.0);
    anim.duration = 0.6;
    anim.autoreverses = YES;
    anim.repeatCount = HUGE_VALF;
    anim.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionEaseInEaseOut];
    [layer addAnimation:anim forKey:@"glowOpacity"];

    CABasicAnimation *radiusAnim = [CABasicAnimation animationWithKeyPath:@"shadowRadius"];
    radiusAnim.fromValue = @(4);
    radiusAnim.toValue = @(16);
    radiusAnim.duration = 0.6;
    radiusAnim.autoreverses = YES;
    radiusAnim.repeatCount = HUGE_VALF;
    radiusAnim.timingFunction = [CAMediaTimingFunction functionWithName:kCAMediaTimingFunctionEaseInEaseOut];
    [layer addAnimation:radiusAnim forKey:@"glowRadius"];
}

- (void)stopGlow:(SLDebtTile *)tile {
    CALayer *layer = tile.container.layer;
    [layer removeAnimationForKey:@"glowOpacity"];
    [layer removeAnimationForKey:@"glowRadius"];
    layer.shadowOpacity = 0;
    layer.shadowRadius = 0;
}

#pragma mark - Gestures

- (SLDebtTile *)tileForView:(UIView *)view {
    return (view.tag == 0) ? self.accTile : self.spnTile;
}

- (void)handlePan:(UIPanGestureRecognizer *)pan {
    SLDebtTile *tile = [self tileForView:pan.view];
    if (pan.state == UIGestureRecognizerStateBegan ||
        pan.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [pan translationInView:pan.view];
        CGRect f = tile.window.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        tile.window.frame = f;
        [pan setTranslation:CGPointZero inView:pan.view];
    }
    if (pan.state == UIGestureRecognizerStateEnded) {
        [self savePosition:tile];
    }
}

- (void)handleTap:(UITapGestureRecognizer *)tap {
    SLDebtTile *tile = [self tileForView:tap.view];
    tile.compact = !tile.compact;
    [self updateTileUI:tile];
}

- (void)handleLongPress:(UILongPressGestureRecognizer *)lp {
    if (lp.state != UIGestureRecognizerStateBegan) return;
    SLDebtTile *tile = [self tileForView:lp.view];
    [self showConfigMenuForTile:tile];
}

#pragma mark - Config Menu

- (void)showConfigMenuForTile:(SLDebtTile *)tile {
    SLDebtTrackerConfig *cfg = tile.tracker.config;
    NSString *title = (tile == self.accTile) ? @"ACC Config" : @"SPN Config";

    UIAlertController *alert = [UIAlertController alertControllerWithTitle:title
                                                                   message:nil
                                                            preferredStyle:UIAlertControllerStyleAlert];

    // Add text fields for each config parameter
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Target (gap)";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.target];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Floor Base";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.floorBase];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Floor Min";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.floorMin];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Quiet Min";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.quietMin];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Quiet Max";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.quietMax];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *tf) {
        tf.placeholder = @"Bet Window";
        tf.text = [NSString stringWithFormat:@"%ld", (long)cfg.betWindow];
        tf.keyboardType = UIKeyboardTypeNumberPad;
    }];

    [alert addAction:[UIAlertAction actionWithTitle:@"Save" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) {
        cfg.target    = [alert.textFields[0].text integerValue];
        cfg.floorBase = [alert.textFields[1].text integerValue];
        cfg.floorMin  = [alert.textFields[2].text integerValue];
        cfg.quietMin  = [alert.textFields[3].text integerValue];
        cfg.quietMax  = [alert.textFields[4].text integerValue];
        cfg.betWindow = [alert.textFields[5].text integerValue];
        [self updateTileUI:tile];
        [self saveState];
    }]];

    [alert addAction:[UIAlertAction actionWithTitle:@"Reset Tracker" style:UIAlertActionStyleDestructive handler:^(UIAlertAction *a) {
        [tile.tracker reset];
        [self stopGlow:tile];
        tile.glowing = NO;
        [self updateTileUI:tile];
        [self saveState];
    }]];

    [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];

    // Present from the tile's window root VC
    [tile.window.rootViewController presentViewController:alert animated:YES completion:nil];
}

#pragma mark - Persistence

- (void)saveState {
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    [ud setObject:[self.accTile.tracker stateDictionary] forKey:self.accTile.defaultsKey];
    [ud setObject:[self.spnTile.tracker stateDictionary] forKey:self.spnTile.defaultsKey];
}

- (void)restoreState {
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    [self.accTile.tracker restoreFromDictionary:[ud dictionaryForKey:self.accTile.defaultsKey]];
    [self.spnTile.tracker restoreFromDictionary:[ud dictionaryForKey:self.spnTile.defaultsKey]];
}

- (void)savePosition:(SLDebtTile *)tile {
    NSUserDefaults *ud = [NSUserDefaults standardUserDefaults];
    [ud setDouble:tile.window.frame.origin.x forKey:tile.posXKey];
    [ud setDouble:tile.window.frame.origin.y forKey:tile.posYKey];
}

#pragma mark - Show / Hide

- (void)show {
    self.accTile.window.hidden = NO;
    self.spnTile.window.hidden = NO;
}

- (void)hide {
    self.accTile.window.hidden = YES;
    self.spnTile.window.hidden = YES;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
```

**Step 2: Commit**

```bash
git add src/SLDebtMonitor.m
git commit -m "feat(debt): implement SLDebtMonitor — dual tiles, glow, haptic, config menu"
```

---

### Task 5: Wire Into SpinLoggerTweak

**Files:**
- Modify: `src/SpinLoggerTweak.m:1-36`

**Step 1: Add import and install call**

Add `#import "SLDebtMonitor.h"` to the imports, and `[[SLDebtMonitor shared] install];` inside the delayed dispatch block, after the existing install calls.

In `src/SpinLoggerTweak.m`:

1. After line 6 (`#import "SLNetworkMonitor.h"`), add:
```objc
#import "SLDebtMonitor.h"
```

2. After line 30 (`[[SLNetworkMonitor shared] install];`), add:
```objc
            [[SLDebtMonitor shared] install];
```

**Step 2: Commit**

```bash
git add src/SpinLoggerTweak.m
git commit -m "feat(debt): wire SLDebtMonitor into SpinLoggerTweak startup"
```

---

### Task 6: Verify Build

**Step 1: Check all source files compile**

The Makefile uses `$(wildcard src/*.m)` so the new files are picked up automatically. Since builds run on GitHub Actions (macOS), push and verify the CI build passes.

Locally, verify no syntax errors by checking that all imports resolve:

```bash
# Quick sanity check — all .h files referenced exist
grep -h '#import "SL' src/SLDebtTracker.m src/SLDebtMonitor.m | sort -u
# Should list: SLConstants.h, SLDebtMonitor.h, SLDebtTracker.h, SLSpinParser.h
# Verify all exist:
ls src/SLConstants.h src/SLDebtTracker.h src/SLDebtMonitor.h src/SLSpinParser.h
```

**Step 2: Final commit with all files**

```bash
git log --oneline -6
# Verify: 5 commits for tasks 1-5
```

---

## Summary of All Files

| Action | File | Lines (approx) |
|--------|------|----------------|
| Create | `src/SLDebtTracker.h` | ~35 |
| Create | `src/SLDebtTracker.m` | ~100 |
| Create | `src/SLDebtMonitor.h` | ~10 |
| Create | `src/SLDebtMonitor.m` | ~340 |
| Modify | `src/SpinLoggerTweak.m` | +2 lines |

Total new code: ~485 lines across 4 new files + 2 lines modified.
