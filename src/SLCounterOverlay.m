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
//    🧪 goldSack (green #4caf50)
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
    { "goldSack",     "🧪", 0.30, 0.69, 0.31 },  // green — potion/event progress
};
static const int kSymbolCount = 6;

@interface SLCounterTile : NSObject
@property (nonatomic, strong) UIWindow *window;
@property (nonatomic, strong) UILabel *tripleLabel;   // 3X: distance between triples
@property (nonatomic, strong) UILabel *singleLabel;   // 1X: single symbol count (resets on triple too)
@property (nonatomic, copy) NSString *symbolKey;
@property (nonatomic, assign) NSInteger distance;     // spins since last triple (3X)
@property (nonatomic, assign) NSInteger singleCount;  // individual appearances since last triple (1X)
@property (nonatomic, assign) BOOL visible;
@end

@implementation SLCounterTile
@end

@interface SLCounterOverlay ()
@property (nonatomic, strong) NSMutableArray<SLCounterTile *> *tiles;
@property (nonatomic, assign) NSInteger totalSpins;
@end

@implementation SLCounterOverlay

+ (instancetype)shared {
    static SLCounterOverlay *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
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
    CGFloat tileW = 52, tileH = 68;
    CGFloat startX = (screen.size.width - (kSymbolCount * (tileW + 6))) / 2;
    CGFloat startY = screen.size.height - tileH - 80;

    for (int i = 0; i < kSymbolCount; i++) {
        SLSymbolDef def = kSymbols[i];
        CGFloat x = startX + i * (tileW + 6);

        SLCounterTile *tile = [[SLCounterTile alloc] init];
        tile.symbolKey = [NSString stringWithUTF8String:def.key];
        tile.distance = 0;
        tile.singleCount = 0;
        tile.visible = YES;

        UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
        win.frame = CGRectMake(x, startY, tileW, tileH);
        win.windowLevel = UIWindowLevelAlert + 100 + i;
        win.backgroundColor = [UIColor clearColor];

        UIViewController *vc = [[UIViewController alloc] init];
        vc.view.backgroundColor = [UIColor clearColor];
        win.rootViewController = vc;

        UIView *container = [[UIView alloc] initWithFrame:CGRectMake(0, 0, tileW, tileH)];
        container.backgroundColor = [[UIColor colorWithRed:0.08 green:0.10 blue:0.15 alpha:0.92] colorWithAlphaComponent:0.92];
        container.layer.cornerRadius = 14;
        container.clipsToBounds = YES;
        [vc.view addSubview:container];

        UIColor *symColor = [UIColor colorWithRed:def.r green:def.g blue:def.b alpha:1.0];

        // Emoji
        UILabel *emojiLabel = [[UILabel alloc] initWithFrame:CGRectMake(0, 2, tileW, 20)];
        emojiLabel.text = [NSString stringWithUTF8String:def.emoji];
        emojiLabel.font = [UIFont systemFontOfSize:16];
        emojiLabel.textAlignment = NSTextAlignmentCenter;
        [container addSubview:emojiLabel];

        // 3X line
        UILabel *tripleLabel = [[UILabel alloc] initWithFrame:CGRectMake(2, 22, tileW - 4, 14)];
        tripleLabel.text = @"3X: 0";
        tripleLabel.font = [UIFont boldSystemFontOfSize:10];
        tripleLabel.textColor = symColor;
        tripleLabel.textAlignment = NSTextAlignmentCenter;
        [container addSubview:tripleLabel];
        tile.tripleLabel = tripleLabel;

        // 1X line
        UILabel *singleLabel = [[UILabel alloc] initWithFrame:CGRectMake(2, 37, tileW - 4, 14)];
        singleLabel.text = @"1X: 0";
        singleLabel.font = [UIFont systemFontOfSize:9];
        singleLabel.textColor = [symColor colorWithAlphaComponent:0.6];
        singleLabel.textAlignment = NSTextAlignmentCenter;
        [container addSubview:singleLabel];
        tile.singleLabel = singleLabel;

        // Color bar
        UIView *bar = [[UIView alloc] initWithFrame:CGRectMake(4, tileH - 4, tileW - 8, 3)];
        bar.backgroundColor = [symColor colorWithAlphaComponent:0.8];
        bar.layer.cornerRadius = 1.5;
        [container addSubview:bar];

        // Pan gesture for individual dragging
        UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc]
            initWithTarget:self action:@selector(handleTilePan:)];
        [vc.view addGestureRecognizer:pan];
        vc.view.tag = i;

        win.hidden = NO;
        tile.window = win;
        [self.tiles addObject:tile];
    }

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

- (void)handleTilePan:(UIPanGestureRecognizer *)pan {
    if (pan.state == UIGestureRecognizerStateBegan ||
        pan.state == UIGestureRecognizerStateChanged) {
        NSInteger idx = pan.view.tag;
        if (idx < (NSInteger)self.tiles.count) {
            CGPoint t = [pan translationInView:pan.view];
            CGRect f = self.tiles[idx].window.frame;
            f.origin.x += t.x;
            f.origin.y += t.y;
            self.tiles[idx].window.frame = f;
            [pan setTranslation:CGPointZero inView:pan.view];
        }
    }
}

#pragma mark - Spin handling (distance between triples)

- (void)onSpinReceived:(NSNotification *)note {
    SLSpinResult *result = note.userInfo[SLSpinDataKey];
    if (!result) return;

    self.totalSpins++;

    // Increment ALL 3X distance counters every spin
    for (SLCounterTile *tile in self.tiles) {
        tile.distance++;
    }

    // Increment 1X count for reel symbols (goldSack excluded — driven by Potion Rush bar below)
    for (NSString *sym in @[result.reel1 ?: @"", result.reel2 ?: @"", result.reel3 ?: @""]) {
        if (sym.length == 0 || [sym isEqualToString:@"goldSack"]) continue;
        for (SLCounterTile *tile in self.tiles) {
            if ([tile.symbolKey isEqualToString:sym]) { tile.singleCount++; break; }
        }
    }

    // Check for triple (reel symbols, goldSack excluded — driven by Potion Rush bar below)
    if (result.reel1 && [result.reel1 isEqualToString:result.reel2] &&
        [result.reel2 isEqualToString:result.reel3] &&
        ![result.reel1 isEqualToString:@"goldSack"]) {
        for (SLCounterTile *tile in self.tiles) {
            if ([tile.symbolKey isEqualToString:result.reel1]) {
                [[SLTrisController shared] recordTriple:tile.symbolKey distance:tile.distance symbolCount:tile.singleCount];
                tile.distance = 0;
                tile.singleCount = 0;
                break;
            }
        }
    }

    // Check for Potion Rush bar completion (🧪 goldSack tile)
    // Identified by progressive_reward_pr_ec reward key (UUID changes per event)
    static NSInteger sPotionMissionIndex = -1;
    if (result.potionRushMissionIndex >= 0) {
        NSInteger mIdx = result.potionRushMissionIndex;
        if (sPotionMissionIndex >= 0 && mIdx > sPotionMissionIndex) {
            // missionIndex increased — bar completed
            for (SLCounterTile *tile in self.tiles) {
                if ([tile.symbolKey isEqualToString:@"goldSack"]) {
                    [[SLTrisController shared] recordTriple:@"goldSack" distance:tile.distance symbolCount:tile.singleCount];
                    tile.singleCount++;  // 1X = completions this session
                    tile.distance = 0;
                    break;
                }
            }
        }
        sPotionMissionIndex = mIdx;
    }

    // Update all labels
    for (SLCounterTile *tile in self.tiles) {
        tile.tripleLabel.text = [NSString stringWithFormat:@"3X: %ld", (long)tile.distance];
        tile.singleLabel.text = [NSString stringWithFormat:@"1X: %ld", (long)tile.singleCount];
    }
}

#pragma mark - Visibility

- (void)onToggleAll:(NSNotification *)note {
    BOOL anyVisible = NO;
    for (SLCounterTile *t in self.tiles) { if (t.visible) { anyVisible = YES; break; } }
    for (SLCounterTile *t in self.tiles) {
        t.visible = !anyVisible;
        t.window.hidden = !t.visible;
    }
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
    for (SLCounterTile *t in self.tiles) { t.window.hidden = NO; t.visible = YES; }
}

- (void)hide {
    for (SLCounterTile *t in self.tiles) { t.window.hidden = YES; t.visible = NO; }
}

- (void)resetAllCounters {
    self.totalSpins = 0;
    for (SLCounterTile *t in self.tiles) {
        t.distance = 0;
        t.tripleLabel.text = @"3X: 0"; t.singleLabel.text = @"1X: 0";
    }
}

- (void)resetCounterForSymbol:(NSString *)symbol {
    for (SLCounterTile *t in self.tiles) {
        if ([t.symbolKey isEqualToString:symbol]) {
            t.distance = 0;
            t.tripleLabel.text = @"3X: 0"; t.singleLabel.text = @"1X: 0";
            break;
        }
    }
}

- (NSDictionary<NSString *, NSNumber *> *)currentCounts {
    NSMutableDictionary *d = [NSMutableDictionary dictionary];
    for (SLCounterTile *t in self.tiles) d[t.symbolKey] = @(t.distance);
    return d;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
