# Nuclear Session Findings — 2026-04-12

Session reverse-engineering the Coin Master slot machine RNG using the IL2CPP trace
scanner + spin_history ground truth on Ahmed's account (306 spins captured,
213 with full settled snapshots).

## Data artifacts

| File | Contents |
| --- | --- |
| `data/Ahmed/il2cpp_trace_20260411_234110.jsonl` | 3,497 raw snapshots, 306 unique `spin_num`, 213 settled |
| `data/Ahmed/spin_history_Ahmed_2026-04-08.csv` | Full 5,393-row spin history (seq 59308 -> 64700), continuously appended |
| `data/Ahmed/spin_history_Ahmed_enriched.csv` | Same CSV with `r1_idx`, `r2_idx`, `r3_idx` left-joined from trace (213 rows labelled) |
| `analysis/nuclear/51_strip_layout.md` | Observation-based strip reconstruction per reel |

## Pipeline scripts

| Script | Role |
| --- | --- |
| `50_il2cpp_trace_decode.py` | Core decoder: 6-stage pipeline (load/segment/sanity/change-map/strip-decode/pity-hunt) |
| `51_strip_reconstruct.py` | Observation-based strip reconstruction (no memory decode needed) |
| `52_field_correlations.py` | Stage-3/5 wrapper that applies seq-1 shift and prints counter time-series |
| `53_index_periodicity.py` | Uniformity / autocorrelation / Markov / cross-reel / triple-gap on idx stream |
| `54_symbol_vs_idx.py` | Head-to-head: symbol-level vs idx-level structure |
| `55_joint_idx_predictor.py` | 5-fold CV, 4 models predicting `is_triple[N+1]` from state[N] |

## Findings (in order of importance)

### 1. spin_num = seq - 1 offset

The in-memory `SlotMachineManager.currentSpinNumber` is the "currently playing" spin,
while `spin_history.csv` writes the completed row with the *next* seq number. So:

```
trace.spin_num == hist.seq - 1
```

Verified: trace spin 64394 bar indices (4,4,4) match CSV seq 64395 with
r=(4,4,4) steal triple. The analysis code applies `hist_shifted["seq"] -= 1`
before joining.

### 2. Strip reconstruction from observation (no memory decode)

The scanner's `m_SymbolElements` hex gate (`len <= 0 || len > 256`) rejected every
reel's array — almost certainly because `kArrayLengthOffset = 24` is wrong for
this IL2CPP build. Pivoted to observation-based reconstruction: pair
`(bar_idx, r_value)` from 213 settled spins, group by reel/idx, take modal symbol.

**Reel 2 is 100% clean** (every idx maps to exactly one symbol across all 213
observations):

```
idx 0: attack       idx 3: goldSack *   idx 6: spins
idx 1: coin *       idx 4: steal        idx 7: goldSack *
idx 2: shield       idx 5: coin *       idx 8: accumulation
```

Duplicate symbol positions confirmed: `coin` at idx 1 and 5, `goldSack` at idx 3 and 7.
**This confirms the "goldSack duplicate theory"** — the in-game visual tell where
goldSack appears with different neighbours is real because goldSack physically
lives at two different strip positions.

**Reel 1 and Reel 3 have dynamic/weighted strips** — multiple symbols map to the
same idx across observations (e.g. reel 1 idx 3 maps to accumulation 25/50,
attack 13, goldSack 9, steal 3). This is not sampling noise — `resultSymbolIndex`
is stable within settled snapshots. Most likely cause: `SlotBarSymbolReplacer.m_Replacements`
(from yesterday's class dump) rewrites the strip per-spin.

### 3. 16% of triples are "exploit triples"

Triple classification from 75 observed triples:

- 63 (84%) have matching bar indices (idx1 == idx2 == idx3)
- **12 (16%) are exploit triples** — same symbol across all three reels but with
  different indices on each reel. Example: `spin 64433: idx=(3,3,7) -> goldSack`.
  The game is leveraging the multi-position symbols (especially goldSack on reel 3,
  which has it at idx 0, 3, 7, 8) to get "free" triples without landing on a
  single aligned stop.

For **goldSack triples specifically, 7 out of 12 (58%) are exploits**, which
means the visible goldSack triple rate overstates the underlying RNG pressure.

### 4. m_SpinFailedCounter is analytics, NOT a pity timer

Yesterday's class dump found:

```
SlotMachineManager
  - m_SpinFailedCounter               (session)
  - m_SpinFailedCounterGlobal         (global, "persists")
  - m_SpinFailedAnalyticThreshold     (default 8, server-tunable)
```

The hypothesis was "client-side pity counter — when it crosses threshold 8,
game forces a payout."

**Reality from trace: both counters are FROZEN AT ZERO for all 213 settled
snapshots**, across multi-spin losing streaks. Threshold stayed pinned at 8.

The "Analytic" in `m_SpinFailedAnalyticThreshold` is the clue — this is an
**analytics/telemetry trigger**, not a gameplay mechanism. It either resets
every spin/session, or only ticks on a rare subtype of "fail event" we haven't
characterised.

**Implication:** `docs/coin_master_rng_analysis_deep.md` was right all along —
"there is no client-side pity timer you can simply read." No amount of scanner
work will find a pity counter that isn't there.

### 5. CROSS-REEL COUPLING (the big structural finding)

At the IDX level, the three reels are structurally coupled within the same spin:

```
CROSS-REEL CORRELATION:
  r1_idx x r2_idx   r = +0.396 *
  r1_idx x r3_idx   r = +0.303 *
  r2_idx x r3_idx   r = +0.594 *    <-- very strong
  (white-noise band: +/- 0.134 at n=213)
```

All three pairs are far outside the white-noise band. The game is not rolling
three independent reels — it is **picking the outcome first and then fitting
stop positions to realise it**, with all three positions co-varying.

This explains why Ahmed sees a 35% triple rate instead of the ~1% you'd expect
from three independent 9-position uniform reels.

### 6. Symbol -> idx projection DESTROYS the signal

The same 213 rows analyzed at the *symbol* level (r1, r2, r3) vs the *idx* level
(r1_idx, r2_idx, r3_idx):

| Test | Symbol result | Idx result |
| --- | --- | --- |
| r1 x r3 correlation | +0.018 (noise) | **+0.303** (coupled) |
| r2 x r3 correlation | +0.273 | **+0.594** |
| Autocorrelation sig lags (reels 1/2/3) | 0 / 0 / 0 | 0 / 1 / 2 |

**At the symbol level, reels 1 and 3 look completely independent.** At the idx
level they are clearly coupled. The many-to-one collapse from idx -> symbol
(duplicate positions, dynamic replacement) erases 100% of the r1<->r3 coupling
signal and 100% of the temporal structure.

**This is why 5 months of surface analysis failed to predict anything.** Every
Markov model, PRNG scanner, pattern engine, and causal ensemble was fitted to
`(r1, r2, r3)` — a lossy projection of the true generative state
`(r1_idx, r2_idx, r3_idx)`. We were modelling the shadow, not the object.

### 7. Reel 3 is severely non-uniform

```
Reel 3 idx distribution (chi^2 = 210.85 vs critical 15.51):
  idx 0:  62 hits  <- goldSack (wrap)
  idx 8:  71 hits  <- goldSack (wrap)
  idx 3:   7 hits
  idx 6:   3 hits
  idx 7:   5 hits
```

133/213 (62%) of all reel 3 landings are on idx 0 or idx 8, both of which map
to goldSack in the reconstructed strip. This is consistent with the reel being
a weighted wheel rather than a uniform strip, OR with dynamic replacement making
idx 0/8 the "idle/safe" positions the game falls back to.

### 8. Reel 2 Markov transitions show conditional structure

The cleanest reel's one-step transition matrix has several entries at 2-3x the
11% uniform baseline:

```
idx 0 -> idx 3 @ 32%    (goldSack at the duplicate position)
idx 4 -> idx 7 @ 26%    (steal -> goldSack-dup)
idx 7 -> idx 4 @ 32%    (goldSack-dup -> steal)
idx 8 -> idx 3 @ 32%    (accumulation -> goldSack)
idx 5 -> idx 0 @ 30%    (coin-dup -> attack)
```

The transition steps cluster around +/-3 and +/-4 positions. Weak but real
conditional structure — not enough for a standalone predictor at n=213, but
enough to suggest a hidden state variable that modulates the reel on a short cycle.

### 9. Reel 3 has temporal structure

Reel 3 autocorrelation (95% CI band +/- 0.134):

```
lag  1: -0.158 *   (adjacent spins anti-correlated)
lag  6: -0.140 *
lag 12: +0.181 *   (weak 12-spin period)
```

3 significant lags out of 15. The most-skewed strip (reel 3) is also the most
temporally structured. Consistent with a hidden state that cycles on ~12 spins.
Reel 1 has zero significant lags, reel 2 has one.

### 10. Joint-idx predictor @ n=213 is underpowered

5-fold CV averaged over 10 seeds on 212 lag-1 pairs:

```
                       top-25% precision    vs base 34.9%
M0  base rate          27.2% +/- 2.8%       (noise floor)
M1  symbol naive Bayes 39.8% +/- 2.0%       +4.9pp lift
M2  idx naive Bayes    37.5% +/- 5.0%       +2.6pp lift
M3  idx joint-lookup   27.5% +/- 2.6%       -7.4pp (overfit)
```

Both NB models have WORSE log loss than the base rate (0.74 vs 0.65), meaning
they are overconfident and poorly calibrated. The joint-state lookup is
catastrophically overfit — 729 possible states with 212 training pairs means
0.3 observations per cell on average.

**Power analysis:**
- n=213 can reliably detect effects of **+15pp or bigger**
- To reliably find a +10pp edge: need ~400 spins
- To reliably find a +5pp edge: need ~1,500 spins
- The observed +4.9pp lift has a 95% CI of roughly +/- 13pp — noise cannot be
  ruled out, but neither can a real effect

**Honest reading:** at n=213, we can confidently rule out huge smoking-gun
patterns but NOT rule out a useful +5-10pp edge. The data is borderline.

## Scanner v2 backlog (for next capture session)

Prioritized from the 529-class il2cpp discovery dump:

### MUST ADD (high RNG impact)

1. `Board3DManager.m_NearWinSymbol` — the symbol the game chose for a near-miss display
2. `Board3DManager.m_ThrowDiceScenarios` — pre-built scenario branching
3. `ScenarioSlotMachineWinBehaviour.m_Scenario` — the win-behaviour tree's scenario pick
4. `SlotSymbolReplacementService.persistentReplacements` — explains reel 1/3 ambiguity
5. `SlotMachineWinBehaviourComposite.m_WinBehaviours` — the composite win-behaviour chain
6. `SlotMachineManager.DynamicSlotResults` — server-pushed result overrides
7. `SlotMachineManager.m_FreezeResolveContext` — buffered/locked outcomes
8. `SlotBarSymbolReplacer.m_Replacements` (per reel) — active replacement map

### SHOULD ADD

9. `SlotDataProvider.SpinFailedCounter` — alternative counter reference (not on Manager)
10. `SlotMachineManager.WEIGHTS_IDENTICAL_SYMBOLS` / `WEIGHTS_NON_IDENTICAL_SYMBOLS` — weight tables
11. `SlotMachineManager.m_SpecialEventsContainers` — active special event overlays
12. `PvpBaseCompetitorSlotsController.m_Random` — direct RNG instance reference
13. `BaseSlotSymbolController.m_SlotMachineManager` — backref to walk from symbol controllers

### NICE TO HAVE

14. `SlotBarManager.m_SymbolElements` — fix the `kArrayLengthOffset` gate so the hex dump works
15. `SlotBarManager.slotObjects` — alternative full-strip access via GameObject array
16. `SlotMachineManager.m_SlotMachineAnimationSpeed` — subtle mode indicator

### Scanner fix pre-requisite

The `len <= 0 || len > 256` gate in `src/SLMemoryScanner.m:501-518` is rejecting
every array. Needs investigation of the actual IL2CPP array header layout for
this Coin Master build (`kArrayHeaderSize = 32`, `kArrayLengthOffset = 24`
constants are suspect).

## Next moves

### Move 1 (no new data needed)

Richer models on the 213-row dataset, targeting the VALUABLE triples specifically:

- Target: `is_triple AND reel_1 in {accumulation, spins}` — the two triples the user actually hunts. Base rate much lower than 35% but this is a narrower, easier prediction problem.
- Features: idx-based (r1_idx, r2_idx, r3_idx) plus multi-lag variants
  (N-1, N-2, N-3), run-length features (spins since last valuable triple),
  interaction terms.
- Models: regularized logistic regression, gradient boosted trees if xgboost
  is available, scikit-learn if installed.
- Cross-validation: temporal (rolling window) not random k-fold — random folds
  leak future into past when there's autocorrelation.
- Also evaluate on the full 5,393-row symbol-only dataset as a fallback.

### Move 2 (requires device redeployment)

Extend `src/SLMemoryScanner.m` to pointer-walk to the MUST-ADD and SHOULD-ADD
classes above, redeploy to jailbroken device, capture 1,000+ spins on Ahmed's
account next session. Target sample size to reliably detect +5-10pp edges.
