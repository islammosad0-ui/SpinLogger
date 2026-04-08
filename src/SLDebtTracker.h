#import <Foundation/Foundation.h>

// ---------------------------------------------------------------------------
//  SLDebtTracker — real-causal ensemble ACC/SPN triple predictor
//
//  v5 design (2026-04-08) — after phantom bug fix + STEAL/quiet-zone hunt:
//   - OR-combined rule list (7 rules in final causal ensemble)
//   - Rules: STEAL/SHIELD-conditioned + quiet-zone suppression + capped DG
//     + early-S-window prev=M/L prediction
//   - 5 phases: WAIT / SOON / ALERT / BET / REST
//   - Tracks prev_gap_length, prev_real_triple, prev_gap_class (S/M/L)
//   - Slope buffer (window 1..20) + quiet-zone buffer (last-N symbol sum)
//   - Verified: 45/271 catches @ ~28 mb/hit on 271-gap validation
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

// Quiet-zone window max (last-N symbol sum for the suppression rule)
#define kSLQuietZoneMax 20

// Cooldown defaults (disabled by default in v5 — cooldown didn't help the real ensemble)
#define kSLDefaultCooldownAfter 0
#define kSLDefaultCooldownLen   0

// S/M/L classification boundaries for gap length
#define kSLGapXsMax  39    // <40 = XS (mix-event triples)
#define kSLGapSMin   40    // 40-105 = S
#define kSLGapSMax  105
#define kSLGapMMin  106    // 106-160 = M
#define kSLGapMMax  160    // 161+ = L

// Number of rules in the ACC ensemble (used for the (N/X) badge)
#define kSLAccEnsembleRuleCount 7

// Gap length class
typedef NS_ENUM(NSInteger, SLGapClass) {
    SLGapClassUnknown = 0,
    SLGapClassXS,
    SLGapClassS,
    SLGapClassM,
    SLGapClassL,
};

// ---------------------------------------------------------------------------
//  SLDebtRule — one bet rule. The tracker fires BET if ANY rule evaluates true.
// ---------------------------------------------------------------------------
@interface SLDebtRule : NSObject
@property (nonatomic, copy)   NSString *name;          // human-readable name (for logging/UI)
@property (nonatomic, assign) NSInteger bitIndex;      // 0..15 for the bet_decisions.csv bitmask

// Base gates
@property (nonatomic, assign) NSInteger spinThreshold; // min sa_spins (use 999 to disable)
@property (nonatomic, assign) NSInteger spinCap;       // max sa_spins (0 = no cap, e.g. 105 for S-window)
@property (nonatomic, assign) double    rateGate;      // min sa_acc/sa_spins (0=off)
@property (nonatomic, assign) double    spnRateGate;   // min sa_spn/sa_spins (0=off, COMBO uses 0.20)
@property (nonatomic, assign) double    minSlope;      // min rate slope (0=off)
@property (nonatomic, assign) NSInteger slopeWindow;   // lookback window for slope (default 10)

// Quiet-zone suppression gate (last-N symbol sum <= max)
@property (nonatomic, assign) NSInteger quietZoneWindow; // 0 = off (e.g. 10 = check last 10 spins)
@property (nonatomic, assign) NSInteger quietZoneMax;    // max total symbols allowed in window

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

// Prev-gap class condition: only fire if previous gap's class matches
// (bitmask: 0=none, 1=XS, 2=S, 4=M, 8=L — OR the desired classes)
@property (nonatomic, assign) NSInteger requiredPrevClassMask;

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
+ (instancetype)accCausalDefaults;      // v5 DEFAULT: 7-rule (STEAL+SHIELD+quiet-zone+DGcap+early-S). 45/271 @ ~28 mb
+ (instancetype)accCausal6Capped;       // v5.1 6-rule: drops early-S, keeps DG cap155. 41/271 @ 24.4 mb (4.3x lift)
+ (instancetype)accCausal6Uncapped;     // v5  6-rule: drops early-S, uncapped DG.     53/271 @ 30.0 mb (3.5x lift)
+ (instancetype)accEnsembleDefaults;    // v4 legacy (phantom 16 rules) - kept for comparison
+ (instancetype)accBaselineDefaults;    // single rule: 130/0.30 (legacy comparison)
+ (instancetype)accComboOnlyDefaults;   // single rule: COMBO only
+ (instancetype)spnDefaults;            // single rule: SPN Sniper 120/0.25
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
@property (nonatomic, assign, readonly) SLGapClass prevGapClass;     // derived from prevGapLength

// Phase state
@property (nonatomic, assign, readonly) SLDebtPhase phase;
@property (nonatomic, assign, readonly) NSInteger firingRuleCount;   // how many rules fire NOW (post-spin, forward-looking display)
@property (nonatomic, assign, readonly) NSUInteger firingRuleBitmask; // bitmask for display

// CAUSAL firing state — snapshot of firingRuleCount/Bitmask AS OF the START of the current
// onSpin: call (i.e. end of the previous spin). This is the honest answer to "was the tracker
// in BET state going INTO this spin?", used for target_caught and per-rule CSV logging.
// The non-causal (post-spin) firingRuleCount is kept for UI display purposes only.
@property (nonatomic, assign, readonly) NSInteger priorFiringRuleCount;
@property (nonatomic, assign, readonly) NSUInteger priorFiringRuleBitmask;

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
//   totalSymbols   — total symbols this spin (atk+stl+shd+spn+acc, 0..3) — for quiet-zone rule
- (void)onSpin:(BOOL)isTarget
  realTripleType:(NSString *)realTripleType
        primary:(NSInteger)primary
      secondary:(NSInteger)secondary
  totalSymbols:(NSInteger)totalSymbols;

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

// S/M/L prediction for NEXT gap based on prev gap's class
//   Returns a human-readable string like "S(50%)", "M(45%)", "L/M", or "?" if unknown
- (NSString *)predictedNextWindow;
// Quiet-zone state — total symbols in last N spins (for display)
- (NSInteger)symbolsInLastWindow:(NSInteger)N;
// Class a gap length
+ (SLGapClass)classifyGapLength:(NSInteger)length;
+ (NSString *)classAbbreviation:(SLGapClass)cls;

// Reset (event change or manual)
- (void)reset;

// Persistence
- (NSDictionary *)stateDictionary;
- (void)restoreFromDictionary:(NSDictionary *)dict;
@end
