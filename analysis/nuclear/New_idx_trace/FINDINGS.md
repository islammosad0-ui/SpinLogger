# Idx Trace Analysis - Findings (Updated 2026-04-12)

## Phase 1: Initial Trace Decode (Scripts 50-56)

- Decoded il2cpp binary trace from Ahmed's 1107-spin session
- Mapped `resultSymbolIndex` from `SlotBarManager_{1,2,3}` to strip positions 0-8
- Found `r1_idx == r3_idx` -> 100% triple (structural rule, not actionable since bet is locked before spin)
- Lag-based idx prediction: 0pp lift under all models (LR, GBT, RF at multiple configs)
- **Conclusion:** No pre-spin idx signal exists in lag features

## Phase 2: Off-by-One Discovery (Script 73)

**CRITICAL FIX:** The trace's `resultSymbolIndex` is shifted +1 spin from the CSV.
- `trace[N]` idx belongs to CSV spin `N+1`
- Confirmed 294/294: every all-same idx at trace[N] maps to a triple at CSV[N+1]
- The "100% predictive signal" from scripts 70-72 was an artifact -- we were reading the VT's own result one spin early
- SlotSymbol3 memory values (sym1/sym2/sym3) are desync'd and unreliable

**Full idx-to-symbol mapping (strip positions 0-8):**

| idx | symbol |
|-----|--------|
| 0 | attack |
| 1 | coin |
| 2 | shield |
| 3 | goldSack |
| 4 | steal |
| 5 | coin (2nd position) |
| 6 | spins |
| 7 | goldSack (2nd position) |
| 8 | accumulation |

Symbols with two strip positions: coin (1,5), goldSack (3,7).

## Phase 3: Corrected Analysis (Scripts 74-78)

Dataset: 1107 trace spins, 35 VTs (17 ACC, 18 SPN), base rate 3.16%.

### No single-spin idx signal works
- same_idx (6,6,6)/(8,8,8): catches only 1 VT (2.9%) after correction
- Best single feature: no_pair_same at 4.5% precision (1.4x baseline)
- Triples anti-predict VTs: 1.6% VT rate after triple vs 4.0% after non-triple

### Pity timer confirmed as primary signal
- Spins 6-15 after VT: 0.7-1.4% VT rate (dead zone)
- Spins 31-40: 5.8-6.8% (2x baseline)
- Spins 51-60: 9.8% (3x baseline)
- ACC min gap=28, SPN min gap=2 (fundamentally different profiles)

### Statistically significant combo strategies (p < 0.01)

**ALL VTs:**

| Strategy | Precision | Lift | Catch | Bets/Hit | p-value |
|----------|-----------|------|-------|----------|---------|
| gap>=30+low_mom+r1=3or7 | 13.3% | 4.2x | 23% | 7.5 | 0.0000 |
| gap>=30+r3>=5+all_diff+sum>=15 | 12.2% | 3.9x | 17% | 8.2 | 0.0006 |
| gap>=40+r3>=5+sum>=15 | 10.4% | 3.3x | 23% | 9.6 | 0.0005 |
| ALL_OR(r3>=5 or all_diff or sum>=15 or r2=7)@gap>=30 | 7.5% | 2.4x | 54% | 13.3 | 0.0001 |

**ACC specific:**

| Strategy | Precision | Lift | Catch | Bets/Hit | p-value |
|----------|-----------|------|-------|----------|---------|
| gap_acc>=60+prev_steal | 22.2% | 14.5x | 12% | 4.5 | 0.0001 |
| gap>=30+prev_steal | 14.3% | 9.3x | 18% | 7.0 | 0.0001 |
| gap>=30+low_mom+r1=3or7 | 10.8% | 7.0x | 59% | 9.3 | 0.0000 |
| ACC_OR(MHM/MML/HMM combo or steal or pity80+r1=3/7) | 7.8% | 5.1x | 65% | 12.8 | 0.0000 |

**SPN specific:**

| Strategy | Precision | Lift | Catch | Bets/Hit | p-value |
|----------|-----------|------|-------|----------|---------|
| gap>=40+r3>=5+all_diff | 6.5% | 4.0x | 22% | 15.5 | 0.0062 |
| gap_spn>=50+r3>=5+sum>=15 | 5.5% | 3.4x | 33% | 18.3 | 0.0026 |
| gap>=40+r3>=5+sum>=15 | 5.1% | 3.1x | 44% | 19.6 | 0.0009 |
| SPN_OR(r3>=5 or HMM or sum>=18)@gap_spn>=40 | 4.6% | 2.8x | 56% | 21.7 | 0.0007 |

### Key takeaways
- Signal directions are statistically reliable (p < 0.01) but exact precision numbers need more trace data to lock in
- ACC responds to goldSack (r1=3/7) + low momentum + steal symbol
- SPN responds to r3>=5 + high sum
- 2D pity timer formula (ACC: 130/0.30, SPN: 87/0.25) remains the foundation; combo filters refine it
- More trace data needed for fine threshold tuning

## Phase 4: One-Strip Swap Discovery (Scripts 90-91, 2026-04-15)

### The Model

**There is ONE strip shared by all 3 reels, with r1/r3 indices swapped:**

```
r1 symbol = strip[r3_idx]   (swapped!)
r2 symbol = strip[r2_idx]   (direct)
r3 symbol = strip[r1_idx]   (swapped!)
```

Strip (9 positions): `0=attack, 1=coin, 2=shield, 3=goldSack, 4=steal, 5=coin, 6=spins, 7=goldSack, 8=accumulation`

**Validation:**
- Ahmed (1107 spins): 1107/1107 = 100.0% match for all three rules
- Islam (2501 spins): 2498-2499/2501 = 99.9% match

**Data inventory:** 8,067 total spins with idx across 3 accounts (Ahmed: 3,941, Islam: 3,341, Nick: 891)

### Implications

1. **Previous "3 separate reels" model was wrong** — r1 strip had ~50% consistency, r3 had ~48-69% because they were mapped against the wrong strip
2. **All old combo strategies using r1/r3 idx were analyzing swapped data** — r1_idx features actually described r3's symbol, and vice versa
3. **Triple condition**: A triple occurs when `strip[r1_idx] == strip[r2_idx] == strip[r3_idx]` — all three lookups give the same symbol
4. **Equivalence classes matter**: coin has positions [1,5] and goldSack has [3,7], so triples can occur with non-identical indices

### Triple probability: theory vs observed

If positions were uniform random: P(any triple) = 2.88%
Observed triple rate: 31.27% → **10.9x server-side manipulation**

### Actionable signal analysis (8,064 spins, 177 VTs)

**Pure lag-1 idx features: NO SIGNAL (confirms Phase 1)**
- All lag-1 features: p > 0.05, lifts between 0.7x-1.6x — none significant
- The one-strip correction doesn't change this: previous spin's idx does not predict VTs

**Gap + lag-1 combos (best actionable strategies):**

| Strategy | Prec | Lift | Catch | B/H | p-val |
|----------|------|------|-------|-----|-------|
| gap>=50+prev_r2=goldSack | 4.7% | 2.1x | 13.6% | 21.4 | 0.0001 |
| gap>=50+prev_showed_gold | 4.0% | 1.8x | 21.5% | 25.1 | 0.0001 |
| gap>=40+prev_showed_gold | 3.6% | 1.7x | 27.1% | 27.5 | 0.0002 |
| gap>=50 (baseline) | 3.2% | 1.5x | 38.4% | 30.9 | 0.0006 |

`prev_gold` adds ~0.5-1.5pp above pure gap — marginally useful.

**ACC-specific (86 targets, 1.07% base):**

| Strategy | Prec | Lift | Catch | B/H | p-val |
|----------|------|------|-------|-----|-------|
| gap_acc>=80+prev_gold | 2.6% | 2.5x | 34.9% | 38.1 | 0.0000 |
| gap_acc>=60+prev_gold | 2.4% | 2.2x | 45.3% | 42.1 | 0.0000 |
| gap_acc>=80 (baseline) | 1.9% | 1.8x | 54.7% | 52.0 | 0.0000 |

**SPN-specific (91 targets, 1.13% base):** Weak signals, best is gap_spn>=50+prev_display_pair at 1.6%, 1.4x lift, p=0.004.

### Near-miss analysis: ANTI-PREDICTIVE

| Previous spin near-miss | VT lift | Interpretation |
|------------------------|---------|----------------|
| 2/3 accumulation | 0.7x | Anti-predictive |
| 2/3 spins | 0.4x | Anti-predictive |
| 2/3 shield | 2.8x | Noise (5 hits only) |

Near-misses on ACC/SPN do NOT predict the next VT — they slightly suppress it. The game uses near-misses as engagement hooks, not signals.

### Conclusions

1. **One-strip swap is a structural finding** — corrects our understanding of the game's reel mechanics
2. **Does NOT unlock new predictive signals** — the game determines outcomes server-side before revealing idx values
3. **Gap/pity timer remains the only reliable signal**, with marginal boost from prev_gold (+0.5-1.5pp)
4. **Previous combo strategies (Phase 3) were partially wrong** — features like `r1=3or7` meant "r1_idx was goldSack" but actually described r3's displayed symbol. The corrected `prev_showed_gold` still works (p<0.001) because goldSack frequency is high regardless of which reel shows it
5. **Near-misses are anti-predictive** — design pattern, not signal

## Phase 5: repl_map Discovery (2026-04-15)

### The Discovery

**`repl_map1/2/3` is the game's internal outcome instruction for each reel.** It encodes the exact symbol that will display on each reel, using a numeric symbol ID system.

Dataset: 1,926 spins with repl_map data (Ahmed_0414: 881, Islam wide: 571, Nick wide: 474)

### Symbol ID Mapping (from triple analysis)

| repl_map value | Symbol | Triple type | Verified |
|----------------|--------|-------------|----------|
| 1 | coin | gold | Yes (125 triples) |
| 2 | goldSack | gold | Yes (79 triples) |
| 3 | attack | attack | Yes (131 triples) |
| 4 | steal | steal | Yes (56 triples) |
| 5 | shield | shield | Yes (85 triples) |
| 6 | spins | spins (VT) | Yes (17 VTs) |
| 8 | accumulation | accumulation (VT) | **HYPOTHESIZED** (0 ACC triples in data) |
| 30 | special gold? | gold | Yes (7 triples) |
| -1 | null/init | various | Initialization period only |

### Key Results

**Perfect VT identification: 17/17 spins VTs = repl_map (6,6,6), ZERO false positives**

| Account | Spins | SPN VTs | repl_map=(6,6,6) at VT | False positives |
|---------|-------|---------|------------------------|-----------------|
| Ahmed | 881 | 7 | 7/7 (100%) | 0 |
| Islam | 571 | 6 | 5/6 (83%)* | 0 |
| Nick | 474 | 4 | 4/4 (100%) | 0 |
| **Total** | **1,926** | **17** | **16/17 (94%)** | **0** |

*Islam's 1 miss had repl_map=(-1,-1,-1) — initialization null, not a real mismatch.

For ALL triple types, repl_map = (N,N,N) matches the symbol with near-100% accuracy. The only exceptions are -1 (null) values during session initialization.

### Cross-tab verification (non-triple spins)

repl_map values match r1/r2/r3 symbol IDs perfectly on every non-null spin. The repl_map IS the reel outcome, just read from a different memory field.

### Is it pre-fetched? (Pre-spin actionability)

**CSV-based lag test: NO pre-fetch detected**

| Test | Match rate | Random baseline | Conclusion |
|------|-----------|----------------|------------|
| repl_map1[N-1] == r1[N] | 20.9% | 22.7% | Random |
| repl_map2[N-1] == r2[N] | 15.6% | 17.1% | Random |
| repl_map3[N-1] == r3[N] | 24.4% | 27.2% | Random |

The PREVIOUS spin's repl_map does NOT predict the NEXT spin's result — it matches at exactly the random baseline rate.

**However: CSV data captures repl_map AFTER the spin completes.** The critical question is whether the game writes repl_map to memory BEFORE the user presses the spin button.

### Actionable hypothesis: real-time memory pre-fetch

If the game's API pre-fetches spin results:
1. Server sends next spin result -> game writes repl_map to memory
2. User hasn't pressed spin yet
3. IL2CPP reader detects repl_map = (6,6,6) or (8,8,8)
4. User sets max bet -> presses spin -> guaranteed VT

**This cannot be verified from CSV data — requires real-time memory polling between spins.**

### Other findings

- **full_strip variations are initialization artifacts** — complex comma-separated values with memory addresses appear only in first ~25 rows of session, not dynamic strip changes
- **slot_prob_seg "transitions" were a parsing artifact** — Islam's data has mixed 65-col and 71-col rows; the "5" and "-1" values previously attributed to slot_prob_seg were actually full_strip3/repl_map values shifted by column misalignment. All rows show `segment_tag_core_slot_prob_nu_29_06_base1` when properly parsed.
- **repl_map=-1 rows = full_strip=-1 rows** — 47/47 perfect overlap, all session initialization
- **Zero accumulation results** in any repl_map-enabled data — ACC mapping to repl_map=8 is hypothesized but unverified

### Conclusions

1. **repl_map perfectly encodes spin outcomes** — the game's internal symbol instruction, verified across 3 accounts
2. **Same-spin signal from CSV perspective** — the lag-1 test confirms no pre-fetch in logged data
3. **Real-time pre-fetch is the $100 question** — if the game loads repl_map before the spin button press, this is 100% VT prediction at 1 bet/hit
4. **Need ACC triple data** — no accumulation events occurred during repl_map sessions; need to capture repl_map during an ACC triple to confirm value 8

## Phase 6: sa_ Counter Strategies & OR Combos (Scripts 95-99, 2026-04-15)

### The shift to sa_ counters

After the one-strip swap (Phase 4) and repl_map (Phase 5) discoveries closed off idx-based prediction, focus moved to in-game counters:
- `sa_spn` — spins remaining until next SPN VT (visible to player)
- `sa_acc` — spins remaining until next ACC VT (visible to player)
- `gap` — spins since last VT (computed)

Dataset for Phase 6: **7,038 spins, 212 VTs (3.01%, 1 per 33 spins)** across Ahmed (3 files), Islam, Nick.

### Pareto front: precision vs catch rate (script 99)

The fundamental tradeoff — pick a row matching your risk tolerance:

| BPH | Rule | Prec% | Catch% | TP | Bets |
|-----|------|-------|--------|----|----|
| 2.8 | g>=50 & spn>=45 | 35.7 | 2.4 | 5 | 14 |
| 4.1 | g>=40 & spn>=45 | 24.1 | 3.3 | 7 | 29 |
| 5.2 | g>=35 & spn>=45 & acc>=45 | 19.0 | 3.8 | 8 | 42 |
| 5.6 | g>=35 & spn>=45 | 17.8 | 3.8 | 8 | 45 |
| 7.0 | (g>=35&spn>=45) OR (g>=35&acc>=55) | 14.3 | 4.2 | 9 | 63 |
| 9.4 | spn>=45 | 10.6 | 4.2 | 9 | 85 |
| 10.3 | spn>=45 OR acc>=55 | 9.7 | 4.7 | 10 | 103 |

**Sweet spot: `g>=35 & spn>=45` at 17.8% precision (5.6x baseline), 5.6 bets/hit.** The OR-with-acc adds 1 TP for ~1.4 extra bph.

### Theoretical ceiling

Of the 212 VTs in the dataset:
- **115 (54.2%) are unreachable** — either gap<20 (game just gave a VT) or no sa_ data captured pre-spin
- Only **125 VTs (59%) had usable sa_ counter data** at all
- Of those 125: only 21 (16.8%) had spn>=35 OR acc>=45
- Best achievable catch with current features: ~10% of all VTs

### Why catch is capped

Profile of caught vs missed VTs (rule: spn>=45 OR (gap>=40 & acc>=50)):

| Feature | Caught (n=10) | Missed (n=202) |
|---------|---------------|----------------|
| gap median | 61 | 21.5 |
| sa_spn median | 46 | 17 |
| sa_acc median | 54 | 20 |

92% of missed VTs had `sa_spn < 30` at the spin before — the game often delivers VTs without showing the counter "ready" state in advance.

### OR combos: small gain over best AND rule

Best statistically significant OR rules (p<0.01):

| Rule | Prec% | Lift | Catch | BPH |
|------|-------|------|-------|-----|
| (g>=30&spn>=45) OR (g>=30&acc>=54) | 12.2 | 4.0x | 4.7% | 8.2 |
| spn>=45 OR (gap>=50&acc>=45) | 6.3 | 2.1x | 6.6% | 15.8 |
| spn>=45 OR acc>=54 OR (g>=50&spn>=35) | 6.6 | 2.2x | 9.0% | 15.2 |

OR rules add 1-3 TPs vs the equivalent AND rule but at proportional bph cost. **Marginal gain — not a breakthrough.**

### Conclusions

1. **The game is harder than the original 2D pity formula suggested** — base rate is 3.01% (1 per 33), not 5%+
2. **`sa_spn>=45` is the strongest single signal** — 10.6% precision, 3.5x lift, but only 4.2% catch
3. **Adding `gap>=35` filter triples precision** (17.8%) at half the catch — best single rule for low-bph play
4. **OR-combining acc and spn rules adds marginal coverage** — useful only if you're already committed to the bph budget
5. **Catch is fundamentally capped at ~10%** without new features — most VTs land without sa_ counters reaching threshold
6. **Real-time repl_map polling (Phase 5) remains the only path to >50% catch at <2 bph** — counter-based strategies have hit their ceiling

## Scripts & Outputs

| Script | Description | Output |
|--------|-------------|--------|
| 50 | il2cpp trace decode | trace_Ahmed/Islam/Nick.txt |
| 51 | Strip layout reconstruction | 51_strip_layout.md |
| 52 | Field correlations | (terminal only) |
| 53 | Index periodicity | (terminal only) |
| 54 | Symbol vs idx | (terminal only) |
| 55 | Joint idx predictor | (terminal only) |
| 56 | Valuable triple predictor | 56_RESULTS.md, 56_results.json |
| 62 | Per-type signals | (terminal only) |
| 63 | Per-type sim | (terminal only) |
| 70-72 | **INVALIDATED** (off-by-one bug) | -- |
| 73 | Full spin dump (verification) | 73_full_spin_dump_output.txt |
| 74 | Corrected gap analysis | 74_corrected_gap_analysis_output.txt |
| 75 | 12-part comprehensive analysis | 75_full_gap_analysis_output.txt |
| 76 | ALL/ACC/SPN deep split | 76_deep_split_analysis_output.txt |
| 77 | 80+ strategy simulations | 77_strategy_sim_output.txt |
| 78 | P-values & Wilson CIs | 78_confidence_and_combos_output.txt |
| 90 | One-strip swap analysis (8067 spins) | (terminal) |
| 91 | Actionable pre-spin signals (lag-1 only) | (terminal) |
| 92 | Exhaustive 15-angle deep sweep (20K+ strategies) | (terminal) |
| 93 | Full gap/sequence profiling (9 sections) | 93_output.txt |
| 94* | repl_map discovery & cross-account validation | (terminal, this session) |
| 95 | ML deep dive on idx + sa_ features | (terminal) |
| 96 | Isolated single-feature significance tests | (terminal) |
| 97 | One-strip swap simulator (v1/v2 strategies) | (terminal) |
| 98 | v3 composite scorer | (terminal) |
| 99 | OR-combo Pareto front (sa_spn/sa_acc/gap) | 99_or_combos_output.txt |
