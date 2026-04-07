#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLDebtTracker — 16-rule ensemble ACC/SPN triple predictor
//
//  Final design from nuclear analysis (Apr 2026):
//   - 16 rules OR-combined
//   - Cooldown 8/3 (after 8 consecutive bet spins, skip 3)
//   - 5 phases: WAIT / SOON / ALERT / BET / REST
//   - Tracks prev_gap_length and prev_real_triple
//   - Slope buffer supports any window 1..20
//   - 63/178 catches @ 10.49 mb/hit (validated all 3 accounts)
// ---------------------------------------------------------------------------

typedef NS_ENUM(NSInteger, SLDebtPhase) {
    SLDebtPhaseWaiting,   // far from any rule firing — gray
    SLDebtPhaseSoon,      // L-bucket pre-warm OR within 25 spins of MIN threshold — orange, no haptic
    SLDebtPhaseWatch,     // at/above threshold but no rule firing yet — yellow ALERT
    SLDebtPhaseBetNow,    // at least 1 rule firing, NOT in cooldown — green, haptic on first transition
    SLDebtPhaseRest       // in 8/3 cooldown — dim orange, no haptic
};

// Maximum slope window. The rate history buffer is sized for any window 1..20.
#define kSLSlopeWindowMax 20

// Cooldown defaults (the 8/3 rule from analysis)
#define kSLDefaultCooldownAfter 8
#define kSLDefaultCooldownLen   3

// Number of rules in the ACC ensemble (used for the (N/16) badge)
#define kSLAccEnsembleRuleCount 16

// ---------------------------------------------------------------------------
//  SLDebtRule — one bet rule. The tracker fires BET if ANY rule evaluates true.
// ---------------------------------------------------------------------------
@interface SLDebtRule : NSObject
@property (nonatomic, copy)   NSString *name;          // human-readable name (for logging/UI)
@property (nonatomic, assign) NSInteger bitIndex;      // 0..15 for the bet_decisions.csv bitmask

// Base gates (used in M bucket / when no SML override is active)
@property (nonatomic, assign) NSInteger spinThreshold; // min sa_spins (use 999 to disable)
@property (nonatomic, assign) double    rateGate;      // min sa_acc/sa_spins (0=off)
@property (nonatomic, assign) double    spnRateGate;   // min sa_spn/sa_spins (0=off, COMBO uses 0.20)
@property (nonatomic, assign) double    minSlope;      // min rate slope (0=off)
@property (nonatomic, assign) NSInteger slopeWindow;   // lookback window for slope (default 10)

// SML S-bucket override: when prev_gap < smlSBound, use these instead of base
@property (nonatomic, assign) NSInteger smlSBound;     // 0 = no S override
@property (nonatomic, assign) NSInteger smlSThreshold;
@property (nonatomic, assign) double    smlSGate;

// SML L-bucket override: when prev_gap >= smlLBound, use these instead of base
@property (nonatomic, assign) NSInteger smlLBound;     // 0 = no L override
@property (nonatomic, assign) NSInteger smlLThreshold;
@property (nonatomic, assign) double    smlLGate;

// Conditional: only fire if previous real triple was this type ("" = no condition)
@property (nonatomic, copy)   NSString *requiredPrevTriple;

+ (instancetype)ruleWithName:(NSString *)name bitIndex:(NSInteger)bitIndex;
@end

// ---------------------------------------------------------------------------
//  SLDebtTrackerConfig — holds an array of rules + cooldown settings
// ---------------------------------------------------------------------------
@interface SLDebtTrackerConfig : NSObject
@property (nonatomic, strong) NSMutableArray<SLDebtRule *> *rules;
@property (nonatomic, assign) NSInteger cooldownAfter;  // consec bets before forced rest (default 8)
@property (nonatomic, assign) NSInteger cooldownLen;    // rest length in spins (default 3)

// Preset factories
+ (instancetype)accEnsembleDefaults;  // 16 rules (the final ACC ensemble)
+ (instancetype)accBaselineDefaults;  // single rule: 130/0.30 (legacy comparison)
+ (instancetype)accComboOnlyDefaults; // single rule: COMBO only
+ (instancetype)spnDefaults;          // single rule: SPN Sniper 120/0.25
@end

// ---------------------------------------------------------------------------
//  SLDebtTracker — runs the rules per spin
// ---------------------------------------------------------------------------
@interface SLDebtTracker : NSObject
@property (nonatomic, strong) SLDebtTrackerConfig *config;

// Per-spin state
@property (nonatomic, assign, readonly) NSInteger saSpins;        // spins since last target triple
@property (nonatomic, assign, readonly) NSInteger saSymbols;      // primary symbols since last triple
@property (nonatomic, assign, readonly) NSInteger saSpnSymbols;   // secondary symbols (sa_spn for ACC)

// Gap-context state (survives event reset only via explicit reset)
@property (nonatomic, assign, readonly) NSInteger prevGapLength;     // -1 = unknown
@property (nonatomic, copy,   readonly) NSString *prevRealTriple;    // nil = unknown

// Phase state
@property (nonatomic, assign, readonly) SLDebtPhase phase;
@property (nonatomic, assign, readonly) NSInteger firingRuleCount;   // how many rules fire NOW
@property (nonatomic, assign, readonly) NSUInteger firingRuleBitmask; // bitmask for CSV logging

// Cooldown state
@property (nonatomic, assign, readonly) NSInteger consecBets;        // current consecutive-bet streak
@property (nonatomic, assign, readonly) NSInteger cooldownRemaining; // 0 = not in cooldown
@property (nonatomic, assign, readonly) NSInteger gapBetCount;       // bets made in current gap

// Init
- (instancetype)initWithConfig:(SLDebtTrackerConfig *)config;

// Process a spin
//   isTarget       — was this spin a triple of the target type? (acc for ACC, spn for SPN)
//   realTripleType — if this spin was any real triple, the type string ("attack"/"shield"/etc.). nil if no real triple.
//   primary        — count of primary symbols on this spin (for sa_acc / ss_spn)
//   secondary      — count of secondary symbols (sa_spn for ACC tracker, 0 for SPN)
- (void)onSpin:(BOOL)isTarget
  realTripleType:(NSString *)realTripleType
        primary:(NSInteger)primary
      secondary:(NSInteger)secondary;

// State accessors (used by UI / logging)
- (double)accumRate;                       // saSymbols / saSpins
- (double)spnRate;                         // saSpnSymbols / saSpins
- (double)slopeForWindow:(NSInteger)win;   // accRate_now - accRate_{win spins ago}
- (NSInteger)minEffectiveThreshold;        // smallest threshold across rules eligible for current context
- (BOOL)evaluateRule:(SLDebtRule *)r;      // does this rule fire NOW?
- (BOOL)isRuleSoon:(SLDebtRule *)r;        // within ~25 spins of firing?
- (NSArray<SLDebtRule *> *)firingRules;    // currently firing rules (for UI panel)
- (NSArray<SLDebtRule *> *)soonRules;      // rules close to firing
- (NSArray<SLDebtRule *> *)dormantRules;   // rules that cannot fire on this gap context

// Reset (event change or manual)
- (void)reset;

// Persistence
- (NSDictionary *)stateDictionary;
- (void)restoreFromDictionary:(NSDictionary *)dict;
@end
