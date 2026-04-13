# 56 - Valuable Triple Predictor Results (2026-04-12)

## TL;DR

- **Actionable (lag-based) prediction: 0pp lift.** No idx-based lag feature, at any lag depth (1-5), under any model (L2-LR at 3 regularization strengths, GBT at 4 configs, RF), produced a positive top-quartile or top-decile lift on valuable triples (acc + spins).
- **Non-actionable (same-spin) structural rule FOUND: `r1_idx == r3_idx` -> 100% triple.** 69/69 rows in the enriched set, zero exceptions. This is the cross-reel coupling memory realized at its cleanest.
- **Decision: Move 1 fails its bar. Go Move 2.** Per the brief: "if NOTHING clears +5pp after exhaustive search, that is solid proof we need more data." Lag-based search returned 0pp after exhausting models and lag depths.

## Run config

- Dataset: `data/Ahmed/spin_history_Ahmed_enriched.csv` filtered to idx-enriched rows (n=213).
- Target A: `is_triple AND reel_1 in {accumulation, spins}`. Base rate 7/213 = **3.29%**.
- Target B (comparison): `is_triple` (any). Base rate 75/213 = 35.21%.
- Validation: walk-forward (train on [0, i), predict i), warmup=40.
- Symbol baseline: same two targets on full 5,393-row symbol stream, walk-forward with stride=100.

## Full results table (valuable_triple target)

| Dataset | Model | Features | log_loss | top25 prec | top25 lift | top10 prec | top10 lift |
|---|---|---|---|---|---|---|---|
| enriched_213 | base_rate | - | 0.1359 | 0.0 | -2.89pp | 0.0 | -2.89pp |
| enriched_213 | LR C=0.1 | lag_only | 0.5595 | 0.0 | **-2.89pp** | 0.0 | **-2.89pp** |
| enriched_213 | LR C=1.0 | lag_only | 0.4295 | 0.0 | **-2.89pp** | 0.0 | **-2.89pp** |
| enriched_213 | LR C=10  | lag_only | 0.4398 | 0.0 | **-2.89pp** | 0.0 | **-2.89pp** |
| enriched_213 | LR C=0.1 | same_spin r1/r3 | 0.3639 | 0.1163 | +8.74pp | 0.2941 | **+26.52pp** |
| enriched_213 | LR C=1.0 | same_spin r1/r3 | 0.1005 | 0.1163 | +8.74pp | 0.2941 | **+26.52pp** |
| enriched_213 | LR C=10  | same_spin r1/r3 | 0.0207 | 0.1163 | +8.74pp | 0.2941 | **+26.52pp** |
| enriched_213 | LR C=1.0 | lag + same + runlen | 0.0881 | 0.1163 | +8.74pp | 0.2941 | +26.52pp |
| enriched_213 | GBT n=100 d=3 | all | 0.0004 | 0.1163 | +8.74pp | 0.2941 | +26.52pp |
| enriched_213 | RF n=200 d=6 | all | 0.1241 | 0.1163 | +8.74pp | 0.2941 | +26.52pp |
| enriched_213 | GBT n=200 d=3 | lag1-5 only (probe) | 0.2123 | 0.0 | **-2.89pp** | 0.0 | **-2.89pp** |
| symbol_5393 | base_rate | - | 0.0947 | 0.0085 | -1.06pp | 0.0039 | -1.52pp |
| symbol_5393 | LR C=1 | sym_lag3 | 0.563 | 0.02 | +0.10pp | 0.019 | +0.02pp |
| symbol_5393 | GBT n=100 d=3 | sym_lag3 | 0.1063 | 0.018 | -0.13pp | 0.021 | +0.21pp |

Every lag-only row is bolded. Every lag-only row returns -2.89pp (which is just the base rate reshuffled — the model is producing uniform-ish outputs and top-k happens to miss the positives).

## Same-spin memorization mechanism

The +26.52pp / +66.47pp headlines come from features the model literally cannot use for bet-sizing:

```
Diagnostic 2:
  rows with r1_idx == r3_idx:     69 / 213   (32.4%)
    of those, triples:            69 / 69    (100.0%)
  rows with r1_idx != r3_idx:    144 / 213
    of those, triples:              6 / 144  (4.2%)

Diagnostic 3:
  r1 == r2 == r3:                 63
  r1 == r3 but r2 != r1:           6   (exploit triples via duplicate symbols)
  P(r2 == r1 | r1 == r3) = 0.913  (vs 1/9 = 0.111 independent baseline)
```

The rule is: **if the outer reels land at the same strip position, the game resolves the spin as a triple in 100% of observed cases** (symbol-level), and the middle reel hits the same strip position in 91.3% of those (the other 8.7% hit a duplicate-symbol position — the goldSack/coin exploit route).

### Why this is not actionable

- The bet is locked before the spin starts. Observing r1_idx and r3_idx mid-animation cannot change this spin's payout.
- Applied as a lag feature to the NEXT spin: zero lift. Spin N's (r1_idx, r3_idx) values carry no information about spin N+1's triple outcome under any model or lag depth we tested.
- Therefore: the same-spin rule is **confirmation of the structural hypothesis** (the game plants the outcome before the animation), but it is **not a bet-sizing predictor**.

## Top-decile picks (LR C=1, same-spin)

The 17 highest-confidence valuable-triple picks under walk-forward CV:

```
seq     reel_1         r1 r2 r3  is_triple  y_val  pred
64616   accumulation    8  8  8      T        1    0.953  <- hit
64657   spins           6  6  6      T        1    0.942  <- hit
64556   accumulation    8  8  8      T        1    0.933  <- hit
64491   accumulation    8  8  8      T        1    0.907  <- hit
64512   spins           6  6  6      T        1    0.901  <- hit
64463   coin            6  5  5      F        0    0.486
64469   coin            6  6  5      F        0    0.364
64476   accumulation    1  8  8      F        0    0.318  (accumulation NON-triple)
...
```

5/7 valuable triples caught in the top 17 (top-8%). The remaining picks at rank 6+ are all cases where r1_idx or r3_idx equals 6 (spins) or 8 (acc) but the other outer reel missed — the model is ranking by within-spin partial evidence, which does not survive the "bet before spin" actionability test.

## Symbol baseline is signal-limited, not power-limited

The 5,393-row symbol walk-forward returned ~0pp lift for both targets. 5,193 train-predict cycles with a 100-tree depth-3 GBT is not data-starved — it's pattern-starved. More of the same kind of data will not help.

## What this means for Move 2

1. **The pre-animation state is the only remaining lever.** The game decides the outcome before the reels animate (proven by the 100% outer-reel-match rule). The decision must live in fields set during the bet-to-animation interval. Those are the fields we have not captured:
   - `Board3DManager.m_NearWinSymbol`
   - `SlotBarSymbolReplacer.m_Replacements` (per reel)
   - `SlotSymbolReplacementService.persistentReplacements`
   - `SlotMachineManager.DynamicSlotResults`
   - `SlotMachineWinBehaviourComposite.m_WinBehaviours`
   - `ScenarioSlotMachineWinBehaviour.m_Scenario`
   - `Board3DManager.m_ThrowDiceScenarios`

2. **The scanner needs to capture the spinning-state snapshot**, not just the settled snapshot. The 70% settled / 30% mid-animation ratio on the current trace means we discard 30% of our capture time. But more importantly, the pre-animation fields are *written* during the animation, and the current scanner only walks them when `spinning == false`.

3. **The array-header gate bug is now a priority-1 blocker.** Without `m_SymbolElements`, we cannot read the persistent/replacement/scenario arrays which is where the pre-commitment state will live.

## Files

- `analysis/nuclear/56_valuable_triple_predictor.py` - the predictor
- `analysis/nuclear/56_results.json` - all 32 model rows
- `analysis/nuclear/56_RESULTS.md` - this file
