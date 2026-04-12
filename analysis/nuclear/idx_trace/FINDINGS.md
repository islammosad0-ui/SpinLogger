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
