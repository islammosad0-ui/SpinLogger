#import <UIKit/UIKit.h>
#import "SLCounterOverlay.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import "SLTrisController.h"

// ---------------------------------------------------------------------------
//  SLCounterOverlay — Individual draggable counter tiles
//
//  Each symbol has its OWN UIWindow with a UILabel (no WKWebView needed).
//  Tiles are small, individually draggable, and show distance-between-triples.
//
//  Symbol mapping (from One.dylib screenshots):
//    🔨 attack   (cyan #00e5ff)
//    🐷 steal    (pink #ff69b4)
//    💊 spins    (cyan #00bcd4)
//    🛡 shield   (purple #ce93d8)
//    🧪 potion (green #4caf50)
// ---------------------------------------------------------------------------

typedef struct {
    const char *key;
    const char *emoji;
    CGFloat r, g, b;  // color
} SLSymbolDef;

static const SLSymbolDef kSymbols[] = {
    { "attack",       "🔨", 0.00, 0.90, 1.00 },  // cyan — hammer/attack
    { "steal",        "🐷", 1.00, 0.41, 0.71 },  // pink — pig/raid
    { "spins",        "💊", 0.00, 0.74, 0.83 },  // teal — energy capsule/spins
    { "shield",       "🛡",  0.81, 0.58, 0.85 },  // purple — shield/defense
    { "accumulation", "⭐", 1.00, 0.84, 0.00 },  // gold — accumulation bar
    { "potion",       "🧪", 0.30, 0.69, 0.31 },  // green — potion rush / expedition bar
    { "spinCount",    "🔢", 1.00, 0.60, 0.00 },  // orange — generic spin counter w/ target
};
static const int kSymbolCount = 7;

@interface SLCounterTile : NSObject
@property (nonatomic, strong) UIWindow *window;
@property (nonatomic, strong) UIView *container;       // background tile view (for glow animation)
@property (nonatomic, strong) UILabel *tripleLabel;   // 3X: distance between triples
@property (nonatomic, strong) UILabel *singleLabel;   // 1X: single symbol count (resets on own triple)
@property (nonatomic, strong) UILabel *accLabel;      // ⭐: single symbol count since last ACC triple
@property (nonatomic, copy) NSString *symbolKey;
@property (nonatomic, assign) CGFloat colorR, colorG, colorB;  // symbol color
@property (nonatomic, assign) NSInteger distance;     // spins since last triple (3X)
@property (nonatomic, assign) NSInteger singleCount;  // individual appearances since last own triple (1X)
@property (nonatomic, assign) NSInteger singleCountSinceAcc;  // individual appearances since last ACC triple
@property (nonatomic, assign) BOOL visible;
@end

@implementation SLCounterTile
@end

@interface SLCounterOverlay ()
@property (nonatomic, strong) NSMutableArray<SLCounterTile *> *tiles;
@property (nonatomic, assign) NSInteger totalSpins;
@property (nonatomic, assign) NSInteger spinTileTarget;
@end

@implementation SLCounterOverlay

+ (instancetype)shared {
    static SLCounterOverlay *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (void)saveState {
    NSMutableDictionary *state = [NSMutableDictionary dictionary];
    state[@"totalSpins"] = @(self.totalSpins);
    for (SLCounterTile *t in self.tiles) {
        state[[t.symbolKey stringByAppendingString:@"_d"]] = @(t.distance);
        state[[t.symbolKey stringByAppendingString:@"_s"]] = @(t.singleCount);
        state[[t.symbolKey stringByAppendingString:@"_sa"]] = @(t.singleCountSinceAcc);
        state[[t.symbolKey stringByAppendingString:@"_v"]] = @(t.visible);
        // Save position
        state[[t.symbolKey stringByAppendingString:@"_x"]] = @(t.window.frame.origin.x);
        state[[t.symbolKey stringByAppendingString:@"_y"]] = @(t.window.frame.origin.y);
    }
    [[NSUserDefaults standardUserDefaults] setObject:state forKey:@"Speeder_CounterState"];
}

- (void)restoreState {
    NSDictionary *state = [[NSUserDefaults standardUserDefaults] dictionaryForKey:@"Speeder_CounterState"];
    if (!state) return;
    self.totalSpins = [state[@"totalSpins"] integerValue];
    for (SLCounterTile *t in self.tiles) {
        t.distance    = [state[[t.symbolKey stringByAppendingString:@"_d"]] integerValue];
        t.singleCount = [state[[t.symbolKey stringByAppendingString:@"_s"]] integerValue];
        t.singleCountSinceAcc = [state[[t.symbolKey stringByAppendingString:@"_sa"]] integerValue];
        NSNumber *vis = state[[t.symbolKey stringByAppendingString:@"_v"]];
        if (vis) {
            t.visible = vis.boolValue;
            t.window.hidden = !t.visible;
        }
        if ([t.symbolKey isEqualToString:@"spinCount"]) {
            t.tripleLabel.text = [NSString stringWithFormat:@"%ld/%ld",
                                  (long)t.distance, (long)self.spinTileTarget];
        } else {
            t.tripleLabel.text = [NSString stringWithFormat:@"%ld", (long)t.distance];
            t.singleLabel.text = [NSString stringWithFormat:@"1X:%ld", (long)t.singleCount];
            t.accLabel.text    = [NSString stringWithFormat:@"⭐:%ld", (long)t.singleCountSinceAcc];
        }
        // Restore saved position (clamp to screen bounds)
        NSNumber *sx = state[[t.symbolKey stringByAppendingString:@"_x"]];
        NSNumber *sy = state[[t.symbolKey stringByAppendingString:@"_y"]];
        if (sx && sy) {
            CGRect f = t.window.frame;
            f.origin.x = sx.doubleValue;
            f.origin.y = sy.doubleValue;
            CGRect screen = t.window.windowScene.coordinateSpace.bounds;
            if (screen.size.width > 0) {
                if (f.origin.x < -10) f.origin.x = 0;
                if (f.origin.y < -10) f.origin.y = 0;
                if (f.origin.x > screen.size.width - 10)  f.origin.x = screen.size.width - f.size.width;
                if (f.origin.y > screen.size.height - 10)  f.origin.y = screen.size.height - f.size.height;
            }
            t.window.frame = f;
        }
    }
}

- (void)install {
    self.tiles = [NSMutableArray array];
    self.totalSpins = 0;

    UIWindowScene *scene = nil;
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            if (s.activationState == UISceneActivationStateForegroundActive) break;
        }
    }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat tileW = 50, tileH = 68;
    CGFloat tileGap = 4;
    CGFloat startX = (screen.size.width - (kSymbolCount * (tileW + tileGap))) / 2;
    CGFloat startY = screen.size.height - tileH - 80;

    for (int i = 0; i < kSymbolCount; i++) {
        SLSymbolDef def = kSymbols[i];
        CGFloat x = startX + i * (tileW + tileGap);

        SLCounterTile *tile = [[SLCounterTile alloc] init];
        tile.symbolKey = [NSString stringWithUTF8String:def.key];
        tile.colorR = def.r; tile.colorG = def.g; tile.colorB = def.b;
        tile.distance = 0;
        tile.singleCount = 0;
        tile.singleCountSinceAcc = 0;
        // Default: hide potion, shield, steal, spinCount — user can toggle them on in settings
        BOOL defaultHidden = (strcmp(def.key, "potion") == 0 ||
                              strcmp(def.key, "shield") == 0 ||
                              strcmp(def.key, "steal") == 0 ||
                              strcmp(def.key, "spinCount") == 0);
        tile.visible = !defaultHidden;

        UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
        win.frame = CGRectMake(x, startY, tileW, tileH);
        win.windowLevel = UIWindowLevelAlert + 100 + i;
        win.backgroundColor = [UIColor clearColor];

        UIViewController *vc = [[UIViewController alloc] init];
        vc.view.backgroundColor = [UIColor clearColor];
        win.rootViewController = vc;

        UIView *container = [[UIView alloc] initWithFrame:CGRectMake(0, 0, tileW, tileH)];
        container.backgroundColor = [UIColor colorWithRed:0.06 green:0.08 blue:0.14 alpha:0.94];
        container.layer.cornerRadius = 12;
        container.layer.borderWidth = 1.0;
        container.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.06].CGColor;
        container.clipsToBounds = YES;
        [vc.view addSubview:container];
        tile.container = container;

        UIColor *symColor = [UIColor colorWithRed:def.r green:def.g blue:def.b alpha:1.0];

        // Emoji icon (smaller, top area)
        UILabel *emojiLabel = [[UILabel alloc] initWithFrame:CGRectMake(0, 1, tileW, 18)];
        emojiLabel.text = [NSString stringWithUTF8String:def.emoji];
        emojiLabel.font = [UIFont systemFontOfSize:13];
        emojiLabel.textAlignment = NSTextAlignmentCenter;
        [container addSubview:emojiLabel];

        // 3X distance — prominent number
        UILabel *tripleLabel = [[UILabel alloc] initWithFrame:CGRectMake(2, 18, tileW - 4, 16)];
        tripleLabel.text = @"0";
        tripleLabel.font = [UIFont boldSystemFontOfSize:13];
        tripleLabel.textColor = symColor;
        tripleLabel.textAlignment = NSTextAlignmentCenter;
        [container addSubview:tripleLabel];
        tile.tripleLabel = tripleLabel;

        // 1X count — smaller, dimmer (since last own triple)
        UILabel *singleLabel = [[UILabel alloc] initWithFrame:CGRectMake(2, 33, tileW - 4, 12)];
        singleLabel.text = @"1X:0";
        singleLabel.font = [UIFont systemFontOfSize:9];
        singleLabel.textColor = [symColor colorWithAlphaComponent:0.5];
        singleLabel.textAlignment = NSTextAlignmentCenter;
        [container addSubview:singleLabel];
        tile.singleLabel = singleLabel;

        // ⭐ count — since last ACC triple (all tiles share the same reset trigger)
        UILabel *accLabel = [[UILabel alloc] initWithFrame:CGRectMake(2, 45, tileW - 4, 12)];
        accLabel.text = @"⭐:0";
        accLabel.font = [UIFont systemFontOfSize:9];
        accLabel.textColor = [symColor colorWithAlphaComponent:0.5];
        accLabel.textAlignment = NSTextAlignmentCenter;
        [container addSubview:accLabel];
        tile.accLabel = accLabel;

        // Color accent bar at bottom
        UIView *bar = [[UIView alloc] initWithFrame:CGRectMake(6, tileH - 4, tileW - 12, 2)];
        bar.backgroundColor = [symColor colorWithAlphaComponent:0.7];
        bar.layer.cornerRadius = 1;
        [container addSubview:bar];

        // Pan gesture for individual dragging
        UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc]
            initWithTarget:self action:@selector(handleTilePan:)];
        [vc.view addGestureRecognizer:pan];
        vc.view.tag = i;

        // Spin counter tile: simpler layout (count/target only), double-tap resets.
        if (strcmp(def.key, "spinCount") == 0) {
            tile.singleLabel.hidden = YES;
            tile.accLabel.hidden    = YES;
            tile.tripleLabel.frame  = CGRectMake(2, 22, tileW - 4, 30);
            tile.tripleLabel.font   = [UIFont boldSystemFontOfSize:13];

            UITapGestureRecognizer *dbl = [[UITapGestureRecognizer alloc]
                initWithTarget:self action:@selector(handleSpinTileDoubleTap:)];
            dbl.numberOfTapsRequired = 2;
            [vc.view addGestureRecognizer:dbl];
        }

        win.hidden = !tile.visible;
        tile.window = win;
        [self.tiles addObject:tile];
    }

    NSInteger savedTarget = [[NSUserDefaults standardUserDefaults]
                             integerForKey:@"Speeder_SpinTileTarget"];
    self.spinTileTarget = (savedTarget > 0) ? savedTarget : 100;

    // Restore persisted counter values from previous session
    [self restoreState];

    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification object:nil];
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onToggleAll:)
                                                 name:@"SLToggleCounters" object:nil];
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(onToggleSymbol:)
                                                 name:@"SLToggleCounterSymbol" object:nil];
}

- (void)handleSpinTileDoubleTap:(UITapGestureRecognizer *)tap {
    for (SLCounterTile *t in self.tiles) {
        if ([t.symbolKey isEqualToString:@"spinCount"]) {
            t.distance = 0;
            t.tripleLabel.text = [NSString stringWithFormat:@"%ld/%ld",
                                  (long)t.distance, (long)self.spinTileTarget];
            [self saveState];
            return;
        }
    }
}

- (NSInteger)spinTileTargetValue { return self.spinTileTarget; }

- (void)setSpinTileTargetValue:(NSInteger)target {
    if (target <= 0) return;
    self.spinTileTarget = target;
    [[NSUserDefaults standardUserDefaults] setInteger:target forKey:@"Speeder_SpinTileTarget"];
    for (SLCounterTile *t in self.tiles) {
        if ([t.symbolKey isEqualToString:@"spinCount"]) {
            t.distance = 0;
            t.tripleLabel.text = [NSString stringWithFormat:@"%ld/%ld",
                                  (long)t.distance, (long)target];
            break;
        }
    }
    [self saveState];
}

- (void)handleTilePan:(UIPanGestureRecognizer *)pan {
    NSInteger idx = pan.view.tag;
    if (pan.state == UIGestureRecognizerStateBegan ||
        pan.state == UIGestureRecognizerStateChanged) {
        if (idx < (NSInteger)self.tiles.count) {
            CGPoint t = [pan translationInView:pan.view];
            CGRect f = self.tiles[idx].window.frame;
            f.origin.x += t.x;
            f.origin.y += t.y;
            self.tiles[idx].window.frame = f;
            [pan setTranslation:CGPointZero inView:pan.view];
        }
    }
    if (pan.state == UIGestureRecognizerStateEnded) {
        [self saveState];
    }
}

#pragma mark - Triple glow animation

- (void)flashTriple:(SLCounterTile *)tile {
    UIColor *glowColor = [UIColor colorWithRed:tile.colorR green:tile.colorG blue:tile.colorB alpha:0.6];
    UIColor *normalBg = [UIColor colorWithRed:0.06 green:0.08 blue:0.14 alpha:0.94];
    // Keep UIColor objects alive so CGColorRef stays valid through animation blocks
    UIColor *glowBorderColor = [UIColor colorWithRed:tile.colorR green:tile.colorG blue:tile.colorB alpha:0.9];
    UIColor *normalBorderColor = [UIColor colorWithWhite:1 alpha:0.06];

    // Flash: bright glow bg + colored border
    tile.container.backgroundColor = glowColor;
    tile.container.layer.borderColor = glowBorderColor.CGColor;
    tile.container.layer.borderWidth = 2.0;

    // Scale pop
    tile.container.transform = CGAffineTransformMakeScale(1.15, 1.15);

    // Animate back to normal
    [UIView animateWithDuration:0.25 delay:0 options:UIViewAnimationOptionCurveEaseOut animations:^{
        tile.container.transform = CGAffineTransformIdentity;
    } completion:^(BOOL finished) {
        [UIView animateWithDuration:0.6 delay:0.1 options:UIViewAnimationOptionCurveEaseInOut animations:^{
            tile.container.backgroundColor = normalBg;
            tile.container.layer.borderColor = normalBorderColor.CGColor;
            tile.container.layer.borderWidth = 1.0;
        } completion:nil];
    }];
}

#pragma mark - Spin handling (distance between triples)

- (void)onSpinReceived:(NSNotification *)note {
    SLSpinResult *result = note.userInfo[SLSpinDataKey];
    if (!result) return;

    self.totalSpins++;

    // Increment ALL 3X distance counters every spin (spin counter tile uses
    // the same `distance` field as a generic spin counter that resets on target)
    for (SLCounterTile *tile in self.tiles) {
        tile.distance++;
        if ([tile.symbolKey isEqualToString:@"spinCount"]) {
            if (self.spinTileTarget > 0 && tile.distance >= self.spinTileTarget) {
                tile.distance = 0;
            }
        }
    }

    // Increment 1X count for reel symbols (potion excluded — driven by Potion Rush bar below)
    // Both singleCount (resets on own triple) and singleCountSinceAcc (resets on ACC triple)
    // tick together — they differ only in their reset trigger.
    for (NSString *sym in @[result.reel1 ?: @"", result.reel2 ?: @"", result.reel3 ?: @""]) {
        if (sym.length == 0 || [sym isEqualToString:@"potion"]) continue;
        for (SLCounterTile *tile in self.tiles) {
            if ([tile.symbolKey isEqualToString:sym]) {
                tile.singleCount++;
                tile.singleCountSinceAcc++;
                break;
            }
        }
    }

    // Check for triple (reel symbols, potion excluded — driven by Potion Rush bar below)
    BOOL isReelTriple = (result.reel1 && [result.reel1 isEqualToString:result.reel2] &&
                         [result.reel2 isEqualToString:result.reel3] &&
                         ![result.reel1 isEqualToString:@"potion"]);
    if (isReelTriple) {
        for (SLCounterTile *tile in self.tiles) {
            if ([tile.symbolKey isEqualToString:result.reel1]) {
                [[SLTrisController shared] recordTriple:tile.symbolKey distance:tile.distance symbolCount:tile.singleCount];
                tile.distance = 0;
                tile.singleCount = 0;
                [self flashTriple:tile];
                break;
            }
        }
        // ⭐ reset: when an ACC triple lands, reset the since-last-ACC counter on ALL tiles.
        if ([result.reel1 isEqualToString:kSLSymbolAccumulation]) {
            for (SLCounterTile *tile in self.tiles) {
                tile.singleCountSinceAcc = 0;
            }
        }
    }

    // 🧪 Potion Rush / Expedition bar tracking
    // Tracks distance (spins) between each time the bar's currentAmount increases.
    // The bar only appears in the response when it changes — so when we see it,
    // compare against the last known value to detect an increase.
    static NSMutableDictionary *sPrevBarAmounts = nil;
    if (!sPrevBarAmounts) sPrevBarAmounts = [NSMutableDictionary dictionary];

    if (result.eventBarAmounts.count > 0) {
        BOOL barIncreased = NO;
        for (NSString *barId in result.eventBarAmounts) {
            NSInteger curAmount = [result.eventBarAmounts[barId] integerValue];
            NSNumber *prevVal = sPrevBarAmounts[barId];
            if (prevVal && curAmount > prevVal.integerValue) {
                barIncreased = YES;
            }
            sPrevBarAmounts[barId] = @(curAmount);
        }
        if (barIncreased) {
            for (SLCounterTile *tile in self.tiles) {
                if ([tile.symbolKey isEqualToString:@"potion"]) {
                    [[SLTrisController shared] recordTriple:@"potion" distance:tile.distance symbolCount:0];
                    tile.distance = 0;
                    [self flashTriple:tile];
                    break;
                }
            }
        }
    }

    // Update all labels
    for (SLCounterTile *tile in self.tiles) {
        if ([tile.symbolKey isEqualToString:@"potion"]) {
            // 🧪 Potion tile: just distance since last bar increase
            tile.tripleLabel.text = [NSString stringWithFormat:@"%ld", (long)tile.distance];
            tile.singleLabel.text = @"";
            tile.accLabel.text = @"";
        } else if ([tile.symbolKey isEqualToString:@"spinCount"]) {
            // 🔢 Spin counter tile: count / target
            tile.tripleLabel.text = [NSString stringWithFormat:@"%ld/%ld",
                                     (long)tile.distance, (long)self.spinTileTarget];
        } else {
            // Reel tiles: distance since last triple, 1X since own triple, ⭐ since ACC triple
            tile.tripleLabel.text = [NSString stringWithFormat:@"%ld", (long)tile.distance];
            tile.singleLabel.text = [NSString stringWithFormat:@"1X:%ld", (long)tile.singleCount];
            tile.accLabel.text = [NSString stringWithFormat:@"⭐:%ld", (long)tile.singleCountSinceAcc];
        }
    }

    [self saveState];
}

#pragma mark - Visibility

// shield + potion are opt-in only — the master "show/hide all" toggle ignores
// them. User must flip them via the per-symbol toggle in settings.
static inline BOOL SLCounter_IsMasterExempt(NSString *key) {
    return [key isEqualToString:@"shield"] ||
           [key isEqualToString:@"potion"];
}

- (void)onToggleAll:(NSNotification *)note {
    BOOL anyVisible = NO;
    for (SLCounterTile *t in self.tiles) {
        if (SLCounter_IsMasterExempt(t.symbolKey)) continue;
        if (t.visible) { anyVisible = YES; break; }
    }
    for (SLCounterTile *t in self.tiles) {
        if (SLCounter_IsMasterExempt(t.symbolKey)) continue;
        t.visible = !anyVisible;
        t.window.hidden = !t.visible;
    }
    [self saveState];
}

- (void)onToggleSymbol:(NSNotification *)note {
    NSString *sym = note.userInfo[@"symbol"];
    for (SLCounterTile *t in self.tiles) {
        if ([t.symbolKey isEqualToString:sym]) {
            t.visible = !t.visible;
            t.window.hidden = !t.visible;
            break;
        }
    }
}

- (void)show {
    for (SLCounterTile *t in self.tiles) {
        if (SLCounter_IsMasterExempt(t.symbolKey)) continue;
        t.window.hidden = NO; t.visible = YES;
    }
}

- (void)resetPositions {
    UIWindowScene *scene = self.tiles.firstObject.window.windowScene;
    if (!scene) return;
    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat tileW = 50, tileH = 68, tileGap = 4;
    CGFloat startX = (screen.size.width - (self.tiles.count * (tileW + tileGap))) / 2;
    CGFloat startY = screen.size.height - tileH - 80;
    for (NSUInteger i = 0; i < self.tiles.count; i++) {
        SLCounterTile *t = self.tiles[i];
        t.window.frame = CGRectMake(startX + i * (tileW + tileGap), startY, tileW, tileH);
        // shield + potion keep their saved visibility; only their position resets.
        if (!SLCounter_IsMasterExempt(t.symbolKey)) {
            t.window.hidden = NO;
            t.visible = YES;
        }
    }
    [self saveState];
}

- (void)hide {
    for (SLCounterTile *t in self.tiles) {
        if (SLCounter_IsMasterExempt(t.symbolKey)) continue;
        t.window.hidden = YES; t.visible = NO;
    }
}

- (void)resetAllCounters {
    self.totalSpins = 0;
    for (SLCounterTile *t in self.tiles) {
        t.distance = 0;
        t.singleCount = 0;
        t.singleCountSinceAcc = 0;
        if ([t.symbolKey isEqualToString:@"spinCount"]) {
            t.tripleLabel.text = [NSString stringWithFormat:@"0/%ld", (long)self.spinTileTarget];
        } else {
            t.tripleLabel.text = @"0";
            t.singleLabel.text = @"1X:0";
            t.accLabel.text = @"⭐:0";
        }
    }
    [self saveState];
}

- (void)resetCounterForSymbol:(NSString *)symbol {
    for (SLCounterTile *t in self.tiles) {
        if ([t.symbolKey isEqualToString:symbol]) {
            t.distance = 0;
            t.tripleLabel.text = @"0";
            t.singleLabel.text = @"1X:0";
            break;
        }
    }
}

- (NSDictionary<NSString *, NSNumber *> *)currentCounts {
    NSMutableDictionary *d = [NSMutableDictionary dictionary];
    for (SLCounterTile *t in self.tiles) d[t.symbolKey] = @(t.distance);
    return d;
}

- (BOOL)isSymbolVisible:(NSString *)symbol {
    for (SLCounterTile *t in self.tiles) {
        if ([t.symbolKey isEqualToString:symbol]) return t.visible;
    }
    return YES;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)showTeaserAlert {
    dispatch_async(dispatch_get_main_queue(), ^{
        UIView *flashView = [[UIView alloc] initWithFrame:[UIScreen mainScreen].bounds];
        flashView.backgroundColor = [[UIColor redColor] colorWithAlphaComponent:0.5];
        flashView.userInteractionEnabled = NO;
        UIWindow *window = [UIApplication sharedApplication].keyWindow;
        [window addSubview:flashView];
        
        [UIView animateWithDuration:0.5 animations:^{
            flashView.alpha = 0;
        } completion:^(BOOL finished) {
            [flashView removeFromSuperview];
        }];
        
        NSLog(@"[SpinLogger] TEASER TRIGGER FLASHED!");
    });
}
@end
