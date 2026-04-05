#import "SLTrisController.h"
#import "SLCounterOverlay.h"
#import "SLSpinStore.h"
#import "SLConstants.h"
#import "SLSpinParser.h"
#import <UIKit/UIKit.h>

// ---------------------------------------------------------------------------
//  SLTrisController — Tris Monitor (native UIKit)
//
//  6 independent scrollable columns, one per symbol.
//  Each column auto-scrolls to bottom on new entry.
//  No WKWebView — pure UIKit.
// ---------------------------------------------------------------------------

static NSString * const kColEmojis[6] = { @"🔨", @"🐷", @"💊", @"🛡", @"⭐", @"🧪" };

@interface SLTrisController ()
@property (nonatomic, strong) UIWindow *trisWindow;
// Per-column scroll views and content stacks
@property (nonatomic, strong) NSMutableArray<UIScrollView *> *colScrollViews;
@property (nonatomic, strong) NSMutableArray<UIStackView  *> *colStacks;
// Footer
@property (nonatomic, strong) UIButton *toggleButton;
@property (nonatomic, strong) UILabel  *spinCountLabel;
// Data arrays (oldest→newest)
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histAttack;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histSteal;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histSpins;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histShield;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histAccum;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *histGold;
@property (nonatomic, assign) NSInteger totalSpins;
@property (nonatomic, assign) BOOL symbolCountMode;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistAttack;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistSteal;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistSpins;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistShield;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistAccum;
@property (nonatomic, strong) NSMutableArray<NSNumber *> *symHistGold;
@end

@implementation SLTrisController

static UIColor *colColor(int c) {
    switch (c) {
        case 0: return [UIColor colorWithRed:0.00 green:0.90 blue:1.00 alpha:1]; // attack  #00e5ff
        case 1: return [UIColor colorWithRed:1.00 green:0.41 blue:0.71 alpha:1]; // steal   #ff69b4
        case 2: return [UIColor colorWithRed:0.00 green:0.74 blue:0.83 alpha:1]; // spins   #00bcd4
        case 3: return [UIColor colorWithRed:0.81 green:0.58 blue:0.85 alpha:1]; // shield  #ce93d8
        case 4: return [UIColor colorWithRed:1.00 green:0.84 blue:0.00 alpha:1]; // accum   #ffd700
        case 5: return [UIColor colorWithRed:0.30 green:0.69 blue:0.31 alpha:1]; // gold    #4caf50
        default: return UIColor.whiteColor;
    }
}

+ (instancetype)shared {
    static SLTrisController *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{ instance = [[self alloc] init]; });
    return instance;
}

- (instancetype)init {
    self = [super init];
    if (self) {
        _lockTarget  = [[NSUserDefaults standardUserDefaults] stringForKey:kSLDefaultsTrisLockTarget];
        _skipEnabled = [[NSUserDefaults standardUserDefaults] boolForKey:@"Speeder_TrisSkip"];
        _histAttack = [NSMutableArray array]; _histSteal  = [NSMutableArray array];
        _histSpins  = [NSMutableArray array]; _histShield = [NSMutableArray array];
        _histAccum  = [NSMutableArray array]; _histGold   = [NSMutableArray array];
        _symHistAttack = [NSMutableArray array]; _symHistSteal  = [NSMutableArray array];
        _symHistSpins  = [NSMutableArray array]; _symHistShield = [NSMutableArray array];
        _symHistAccum  = [NSMutableArray array]; _symHistGold   = [NSMutableArray array];
        _colScrollViews = [NSMutableArray array];
        _colStacks      = [NSMutableArray array];
        _totalSpins = 0;
        _symbolCountMode = NO;
        [self restoreState];
    }
    return self;
}

#pragma mark - Persistence

- (void)saveState {
    NSDictionary *state = @{
        @"totalSpins": @(_totalSpins),
        @"histAttack": _histAttack, @"histSteal": _histSteal, @"histSpins": _histSpins,
        @"histShield": _histShield, @"histAccum": _histAccum, @"histGold": _histGold,
        @"symHistAttack": _symHistAttack, @"symHistSteal": _symHistSteal, @"symHistSpins": _symHistSpins,
        @"symHistShield": _symHistShield, @"symHistAccum": _symHistAccum, @"symHistGold": _symHistGold,
    };
    [[NSUserDefaults standardUserDefaults] setObject:state forKey:@"Speeder_TrisState"];
}

- (void)restoreState {
    NSDictionary *state = [[NSUserDefaults standardUserDefaults] dictionaryForKey:@"Speeder_TrisState"];
    if (!state) return;
    _totalSpins = [state[@"totalSpins"] integerValue];
    NSArray *keys   = @[@"histAttack",@"histSteal",@"histSpins",@"histShield",@"histAccum",@"histGold",
                        @"symHistAttack",@"symHistSteal",@"symHistSpins",@"symHistShield",@"symHistAccum",@"symHistGold"];
    NSArray *arrays = @[_histAttack,_histSteal,_histSpins,_histShield,_histAccum,_histGold,
                        _symHistAttack,_symHistSteal,_symHistSpins,_symHistShield,_symHistAccum,_symHistGold];
    for (NSUInteger i = 0; i < keys.count; i++) {
        NSArray *saved = state[keys[i]];
        if ([saved isKindOfClass:[NSArray class]]) [arrays[i] addObjectsFromArray:saved];
    }
}

#pragma mark - Notifications

- (void)install {
    [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(onSpinReceived:)
                                                 name:SLSpinReceivedNotification object:nil];
    [[NSNotificationCenter defaultCenter] addObserver:self selector:@selector(onShowTris:)
                                                 name:@"SLShowTrisMonitor" object:nil];
}

- (void)onSpinReceived:(NSNotification *)note {
    self.totalSpins++;
    dispatch_async(dispatch_get_main_queue(), ^{
        self.spinCountLabel.text = [NSString stringWithFormat:@"SPIN: %ld", (long)self.totalSpins];
    });
}

- (void)onShowTris:(NSNotification *)note {
    [self showTrisMonitor];
}

#pragma mark - Data helpers

- (NSMutableArray *)historyForSymbol:(NSString *)sym {
    if ([sym isEqualToString:kSLSymbolAttack])       return self.histAttack;
    if ([sym isEqualToString:kSLSymbolSteal])        return self.histSteal;
    if ([sym isEqualToString:kSLSymbolSpins])        return self.histSpins;
    if ([sym isEqualToString:kSLSymbolShield])       return self.histShield;
    if ([sym isEqualToString:kSLSymbolAccumulation]) return self.histAccum;
    if ([sym isEqualToString:kSLSymbolGoldSack] || [sym isEqualToString:@"potion"]) return self.histGold;
    return nil;
}

- (NSMutableArray *)symbolHistoryForSymbol:(NSString *)sym {
    if ([sym isEqualToString:kSLSymbolAttack])       return self.symHistAttack;
    if ([sym isEqualToString:kSLSymbolSteal])        return self.symHistSteal;
    if ([sym isEqualToString:kSLSymbolSpins])        return self.symHistSpins;
    if ([sym isEqualToString:kSLSymbolShield])       return self.symHistShield;
    if ([sym isEqualToString:kSLSymbolAccumulation]) return self.symHistAccum;
    if ([sym isEqualToString:kSLSymbolGoldSack] || [sym isEqualToString:@"potion"]) return self.symHistGold;
    return nil;
}

// Column index: 0=attack 1=steal 2=spins 3=shield 4=accum 5=gold
- (int)columnIndexForSymbol:(NSString *)sym {
    if ([sym isEqualToString:kSLSymbolAttack])       return 0;
    if ([sym isEqualToString:kSLSymbolSteal])        return 1;
    if ([sym isEqualToString:kSLSymbolSpins])        return 2;
    if ([sym isEqualToString:kSLSymbolShield])       return 3;
    if ([sym isEqualToString:kSLSymbolAccumulation]) return 4;
    if ([sym isEqualToString:kSLSymbolGoldSack] || [sym isEqualToString:@"potion"]) return 5;
    return -1;
}

- (NSArray *)activeArrayForColumn:(int)c {
    NSArray *spin[6] = { self.histAttack, self.histSteal, self.histSpins,
                         self.histShield, self.histAccum, self.histGold };
    NSArray *sym[6]  = { self.symHistAttack, self.symHistSteal, self.symHistSpins,
                         self.symHistShield, self.symHistAccum, self.symHistGold };
    return self.symbolCountMode ? sym[c] : spin[c];
}

#pragma mark - Record triple

- (void)recordTriple:(NSString *)symbol distance:(NSInteger)distance {
    [self recordTriple:symbol distance:distance symbolCount:0];
}

- (void)recordTriple:(NSString *)symbol distance:(NSInteger)distance symbolCount:(NSInteger)symCount {
    NSMutableArray *hist    = [self historyForSymbol:symbol];
    NSMutableArray *symHist = [self symbolHistoryForSymbol:symbol];
    if (hist)    [hist addObject:@(distance)];
    if (symHist) [symHist addObject:@(symCount)];
    [self saveState];

    if (self.trisWindow && !self.trisWindow.hidden) {
        int col = [self columnIndexForSymbol:symbol];
        if (col >= 0) {
            NSInteger val = self.symbolCountMode ? symCount : distance;
            dispatch_async(dispatch_get_main_queue(), ^{
                [self appendEntryValue:val toColumn:col];
            });
        }
    }
}

#pragma mark - Show / Hide

- (void)showTrisMonitor {
    if (self.trisWindow) {
        self.trisWindow.hidden = !self.trisWindow.hidden;
        return;
    }
    [self buildUI];
}

- (void)hideTrisMonitor {
    self.trisWindow.hidden = YES;
}

#pragma mark - Build native UIKit panel

- (void)buildUI {
    UIWindowScene *scene = nil;
    for (UIScene *s in [UIApplication sharedApplication].connectedScenes) {
        if ([s isKindOfClass:[UIWindowScene class]]) {
            scene = (UIWindowScene *)s;
            if (s.activationState == UISceneActivationStateForegroundActive) break;
        }
    }
    if (!scene) return;

    CGRect screen = scene.coordinateSpace.bounds;
    CGFloat w = MIN(screen.size.width - 20, 320);
    CGFloat h = screen.size.height * 0.25;
    CGFloat x = (screen.size.width  - w) / 2;
    CGFloat y = (screen.size.height - h) / 2;

    UIWindow *win = [[UIWindow alloc] initWithWindowScene:scene];
    win.frame = CGRectMake(x, y, w, h);
    win.windowLevel = UIWindowLevelAlert + 250;
    win.backgroundColor = UIColor.clearColor;

    UIViewController *vc = [[UIViewController alloc] init];
    vc.view.backgroundColor = UIColor.clearColor;
    win.rootViewController = vc;

    // Drag
    UIPanGestureRecognizer *pan = [[UIPanGestureRecognizer alloc] initWithTarget:self action:@selector(dragTris:)];
    [vc.view addGestureRecognizer:pan];

    // Panel background
    UIView *panel = [[UIView alloc] initWithFrame:vc.view.bounds];
    panel.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    panel.backgroundColor = [UIColor colorWithRed:0.06 green:0.08 blue:0.14 alpha:0.96];
    panel.layer.cornerRadius = 14;
    panel.layer.masksToBounds = YES;
    panel.layer.borderColor = [UIColor colorWithWhite:1 alpha:0.08].CGColor;
    panel.layer.borderWidth = 1;
    [vc.view addSubview:panel];

    CGFloat panelW = panel.bounds.size.width;
    CGFloat panelH = panel.bounds.size.height;

    // Close button
    UIButton *closeBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    closeBtn.frame = CGRectMake(panelW - 27, 5, 22, 22);
    closeBtn.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin;
    [closeBtn setTitle:@"✕" forState:UIControlStateNormal];
    closeBtn.tintColor = [UIColor colorWithWhite:1 alpha:0.7];
    closeBtn.titleLabel.font = [UIFont systemFontOfSize:11 weight:UIFontWeightMedium];
    closeBtn.backgroundColor = [UIColor colorWithWhite:1 alpha:0.10];
    closeBtn.layer.cornerRadius = 11;
    [closeBtn addTarget:self action:@selector(closeTapped) forControlEvents:UIControlEventTouchUpInside];
    [panel addSubview:closeBtn];

    // Header row — 6 emoji labels
    CGFloat hdrH = 28;
    UIView *hdrView = [[UIView alloc] initWithFrame:CGRectMake(0, 0, panelW, hdrH)];
    hdrView.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    // bottom separator
    UIView *hdrLine = [[UIView alloc] initWithFrame:CGRectMake(0, hdrH - 1, panelW, 1)];
    hdrLine.backgroundColor = [UIColor colorWithWhite:1 alpha:0.12];
    hdrLine.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    [hdrView addSubview:hdrLine];
    [panel addSubview:hdrView];

    // Footer row
    CGFloat footH = 26;
    CGFloat footY = panelH - footH;
    UIView *footView = [[UIView alloc] initWithFrame:CGRectMake(0, footY, panelW, footH)];
    footView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleTopMargin;
    UIView *footLine = [[UIView alloc] initWithFrame:CGRectMake(0, 0, panelW, 1)];
    footLine.backgroundColor = [UIColor colorWithWhite:1 alpha:0.12];
    footLine.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    [footView addSubview:footLine];
    [panel addSubview:footView];

    // Columns area
    CGFloat colsY = hdrH;
    CGFloat colsH = footY - hdrH;
    CGFloat colW  = panelW / 6.0;

    [self.colScrollViews removeAllObjects];
    [self.colStacks      removeAllObjects];

    for (int c = 0; c < 6; c++) {
        CGFloat colX = c * colW;
        UIColor *color = colColor(c);

        // Header cell
        UILabel *emojiLbl = [[UILabel alloc] initWithFrame:CGRectMake(colX, 0, colW, hdrH - 2)];
        emojiLbl.text = kColEmojis[c];
        emojiLbl.textAlignment = NSTextAlignmentCenter;
        emojiLbl.font = [UIFont systemFontOfSize:13];
        [hdrView addSubview:emojiLbl];

        // Column separator (right edge, skip last)
        if (c < 5) {
            UIView *sep = [[UIView alloc] initWithFrame:CGRectMake(colX + colW - 0.5, hdrH, 0.5, colsH)];
            sep.backgroundColor = [UIColor colorWithWhite:1 alpha:0.18];
            [panel addSubview:sep];
        }

        // Scroll view for column entries
        UIScrollView *sv = [[UIScrollView alloc] initWithFrame:CGRectMake(colX, colsY, colW, colsH)];
        sv.showsVerticalScrollIndicator = NO;
        sv.showsHorizontalScrollIndicator = NO;
        sv.bounces = NO;
        [panel addSubview:sv];
        [self.colScrollViews addObject:sv];

        // Vertical stack inside scroll view
        UIStackView *stack = [[UIStackView alloc] init];
        stack.axis = UILayoutConstraintAxisVertical;
        stack.spacing = 0;
        stack.alignment = UIStackViewAlignmentFill;
        [sv addSubview:stack];
        [self.colStacks addObject:stack];

        // Store color tag for entry labels
        sv.tag = c;
        stack.tag = (NSInteger)(uintptr_t)((__bridge void *)color); // unused, color via block
    }

    // Footer buttons
    UIButton *resetBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    resetBtn.frame = CGRectMake(8, 1, 50, footH - 2);
    [resetBtn setTitle:@"RESET" forState:UIControlStateNormal];
    resetBtn.tintColor = [UIColor colorWithRed:1 green:0.4 blue:0.4 alpha:1];
    resetBtn.titleLabel.font = [UIFont systemFontOfSize:10 weight:UIFontWeightSemibold];
    [resetBtn addTarget:self action:@selector(resetTapped) forControlEvents:UIControlEventTouchUpInside];
    [footView addSubview:resetBtn];

    self.toggleButton = [UIButton buttonWithType:UIButtonTypeSystem];
    self.toggleButton.frame = CGRectMake(panelW / 2 - 25, 1, 50, footH - 2);
    self.toggleButton.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin | UIViewAutoresizingFlexibleRightMargin;
    [self.toggleButton setTitle:self.symbolCountMode ? @"[SYM]" : @"[SPIN]" forState:UIControlStateNormal];
    self.toggleButton.tintColor = [UIColor colorWithWhite:0.7 alpha:1];
    self.toggleButton.titleLabel.font = [UIFont systemFontOfSize:10 weight:UIFontWeightSemibold];
    [self.toggleButton addTarget:self action:@selector(toggleModeTapped) forControlEvents:UIControlEventTouchUpInside];
    [footView addSubview:self.toggleButton];

    self.spinCountLabel = [[UILabel alloc] initWithFrame:CGRectMake(panelW - 70, 1, 65, footH - 2)];
    self.spinCountLabel.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin;
    self.spinCountLabel.text = [NSString stringWithFormat:@"SPIN: %ld", (long)self.totalSpins];
    self.spinCountLabel.textColor = [UIColor colorWithWhite:0.6 alpha:1];
    self.spinCountLabel.font = [UIFont systemFontOfSize:10 weight:UIFontWeightSemibold];
    self.spinCountLabel.textAlignment = NSTextAlignmentRight;
    [footView addSubview:self.spinCountLabel];

    win.hidden = NO;
    self.trisWindow = win;

    // Populate all columns with existing data
    [self rebuildAllColumns];
}

#pragma mark - Column population

// Append a single entry label to a column and scroll to bottom
- (void)appendEntryValue:(NSInteger)val toColumn:(int)col {
    if (col < 0 || col >= (int)self.colStacks.count) return;
    UIStackView *stack = self.colStacks[col];
    UIScrollView *sv   = self.colScrollViews[col];
    UIColor *color     = colColor(col);

    UILabel *lbl = [[UILabel alloc] init];
    lbl.text = [NSString stringWithFormat:@"%ld", (long)val];
    lbl.textColor = color;
    lbl.font = [UIFont systemFontOfSize:11 weight:UIFontWeightBold];
    lbl.textAlignment = NSTextAlignmentCenter;
    lbl.backgroundColor = UIColor.clearColor;

    // Bottom separator line
    UIView *row = [[UIView alloc] init];
    row.backgroundColor = UIColor.clearColor;
    UIView *line = [[UIView alloc] init];
    line.backgroundColor = [UIColor colorWithWhite:1 alpha:0.05];
    [row addSubview:lbl];
    [row addSubview:line];

    // Layout inside row: label fills, 1pt separator at bottom
    lbl.translatesAutoresizingMaskIntoConstraints = NO;
    line.translatesAutoresizingMaskIntoConstraints = NO;
    row.translatesAutoresizingMaskIntoConstraints = NO;
    [NSLayoutConstraint activateConstraints:@[
        [lbl.topAnchor constraintEqualToAnchor:row.topAnchor],
        [lbl.leadingAnchor constraintEqualToAnchor:row.leadingAnchor],
        [lbl.trailingAnchor constraintEqualToAnchor:row.trailingAnchor],
        [lbl.heightAnchor constraintEqualToConstant:22],
        [line.topAnchor constraintEqualToAnchor:lbl.bottomAnchor],
        [line.leadingAnchor constraintEqualToAnchor:row.leadingAnchor],
        [line.trailingAnchor constraintEqualToAnchor:row.trailingAnchor],
        [line.heightAnchor constraintEqualToConstant:1],
        [row.bottomAnchor constraintEqualToAnchor:line.bottomAnchor],
    ]];

    [stack addArrangedSubview:row];

    // Size the stack to fit and scroll to bottom
    [stack sizeToFit];
    CGFloat stackW = sv.bounds.size.width;
    CGFloat stackH = MAX(stack.systemLayoutSizeFittingSize(UILayoutFittingCompressedSize).height, 0);
    stack.frame = CGRectMake(0, 0, stackW, stackH);
    sv.contentSize = CGSizeMake(stackW, stackH);

    CGFloat maxY = MAX(0, sv.contentSize.height - sv.bounds.size.height);
    [sv setContentOffset:CGPointMake(0, maxY) animated:NO];
}

// Rebuild all 6 columns from scratch (used on first show and mode toggle)
- (void)rebuildAllColumns {
    for (int c = 0; c < 6; c++) {
        UIStackView *stack = self.colStacks[c];
        // Remove existing entries
        for (UIView *v in stack.arrangedSubviews) [stack removeArrangedSubview:v];
        [stack.subviews makeObjectsPerformSelector:@selector(removeFromSuperview)];

        NSArray *arr = [self activeArrayForColumn:c];
        for (NSNumber *val in arr) {
            [self appendEntryValue:val.integerValue toColumn:c];
        }
    }
}

#pragma mark - Actions

- (void)closeTapped {
    self.trisWindow.hidden = YES;
}

- (void)resetTapped {
    [self.histAttack removeAllObjects]; [self.histSteal  removeAllObjects];
    [self.histSpins  removeAllObjects]; [self.histShield removeAllObjects];
    [self.histAccum  removeAllObjects]; [self.histGold   removeAllObjects];
    [self.symHistAttack removeAllObjects]; [self.symHistSteal  removeAllObjects];
    [self.symHistSpins  removeAllObjects]; [self.symHistShield removeAllObjects];
    [self.symHistAccum  removeAllObjects]; [self.symHistGold   removeAllObjects];
    self.totalSpins = 0;
    self.spinCountLabel.text = @"SPIN: 0";
    [self saveState];
    [[SLCounterOverlay shared] resetAllCounters];
    SLSpinStoreRotateCSV();
    [self rebuildAllColumns];
}

- (void)toggleModeTapped {
    self.symbolCountMode = !self.symbolCountMode;
    [self.toggleButton setTitle:self.symbolCountMode ? @"[SYM]" : @"[SPIN]" forState:UIControlStateNormal];
    [self rebuildAllColumns];
}

#pragma mark - Drag

- (void)dragTris:(UIPanGestureRecognizer *)pan {
    if (pan.state == UIGestureRecognizerStateBegan ||
        pan.state == UIGestureRecognizerStateChanged) {
        CGPoint t = [pan translationInView:pan.view];
        CGRect f = self.trisWindow.frame;
        f.origin.x += t.x;
        f.origin.y += t.y;
        self.trisWindow.frame = f;
        [pan setTranslation:CGPointZero inView:pan.view];
    }
}

#pragma mark - Setters

- (void)setLockTarget:(NSString *)lockTarget {
    _lockTarget = [lockTarget copy];
    [[NSUserDefaults standardUserDefaults] setObject:_lockTarget forKey:kSLDefaultsTrisLockTarget];
}

- (void)setSkipEnabled:(BOOL)skipEnabled {
    _skipEnabled = skipEnabled;
    [[NSUserDefaults standardUserDefaults] setBool:_skipEnabled forKey:@"Speeder_TrisSkip"];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
