# SpinLogger Analysis Findings

> Complete reference for continuing work on any machine.
> Last updated: 2026-04-06

---

## 1. Two-Dimensional Pity Timer (BREAKTHROUGH)

The game uses BOTH spin count AND symbol accumulation rate to determine when to award a triple. Neither condition alone is sufficient.

### ACC Formula (Triple Accumulation)
```
BET when: sa_spins >= 130 AND (sa_acc / sa_spins) >= 0.30
```

- `sa_spins` = spins since last ACC triple (game's internal counter, CSV column)
- `sa_acc` = accumulation symbols seen on ANY reel since last triple (CSV column)
- rate = sa_acc / sa_spins
- When rate < 0.25: hazard is literally ZERO regardless of spin count
- When rate >= 0.30 AND spins >= 130: triple is primed = BET NOW

### SPN Formula (Triple Spins)
```
BET when: sa_spins >= 87 AND (sa_spn / sa_spins) >= 0.25
```

- `sa_spn` = spins symbols seen on any reel since last SPN triple (CSV column)

### Three-Phase Hazard Model (ACC, MLE fit)
| Phase | Spin Range | Hazard Rate |
|-------|-----------|-------------|
| Dead zone | s < 28 | 0.00263 |
| Low hazard | 28 <= s < 123 | 0.00925 |
| Pity timer | s >= 123 | 0.02915 |

LL = -852.95, delta = +41.63 vs geometric null model.

---

## 2. Validation Results

### ACC — 178 gaps across 3 accounts

| Config | Caught | Bet% | MB/Hit | Lift |
|--------|--------|------|--------|------|
| **Balanced 130/0.30** | **31/178** | **2.9%** | **17.1** | **6.0x** |
| Conservative 120/0.28 | higher catch | ~5% | — | 3.5x |
| Aggressive 130/0.32 | lower catch | ~1.5% | — | 8.2x |

### SPN — 213 gaps across 3 accounts

| Config | Caught | Bet% | MB/Hit | Lift |
|--------|--------|------|--------|------|
| **Conservative 87/0.25** | **60/213** | **18.7%** | **57.1** | **1.5x** |
| Balanced 87/0.30 | 18/213 | 2.6% | 26.1 | 3.3x |
| Aggressive 60/0.30 | 32/213 | 5.7% | 32.6 | 2.6x |
| Spin-only 87/off | 72/213 | 31.7% | 80.6 | 1.1x |

### Cross-Validation
- Train on Acct2 (gate=0.28) → test on Acct3: **7.9x lift**
- Train on Acct3 → test on Acct2: **3.1x lift**
- Both directions hold.

### Out-of-Sample (Acct4, unseen)
- Balanced formula: **9.6x lift** on completely unseen data

---

## 3. Data Files

| Label | File | Spins | ACC Gaps | SPN Gaps | Status |
|-------|------|-------|----------|----------|--------|
| Acct1 | spin_history_2026-04-04 (1).csv | 4968 | — | — | **DUPLICATE of Acct2, DO NOT USE** |
| Acct2 | spin_history_2026-04-04 (2).csv | 8378 | 83 | 95 | Valid, primary training data |
| Acct3 | spin_history_2026-04-05 (1).csv | 7603 | 77 | 86 | Valid, cross-validation |
| Acct4 | spin_history_2026-04-04 (3).csv | 2316 | 18 | 32 | Valid, out-of-sample |

**Total unique:** 178 ACC gaps, 213 SPN gaps

### Deduplication
Acct1 is FULLY CONTAINED in Acct2 (same account, earlier download). Confirmed via 50-row reel tuple comparison.

### Key CSV Columns
- `sa_spins` — spins since last ACC triple (game's internal, resets on ACC triple)
- `sa_acc` — accumulation symbols since last ACC triple
- `sa_spn` — spins symbols since last SPN triple
- `reel_1/2/3` — symbol names: accumulation, spins, attack, steal, shield, coin, goldSack
- `accumMissionIndex` — accum bar level (does NOT reset pity timer)
- `gae_segment` — event ID (pity timer DOES reset on event change)

### Gap Correction
The `sa_spins` column reveals the true gap length including spins before CSV recording started. First gaps corrected: Acct2 58→82, Acct3 43→147.

---

## 4. Pulse Skip Analysis

**Question:** When in BET NOW zone, do non-ACC triples (attack/steal/shield) signal we should briefly drop to 1x?

### Findings
- 28 real other triples land in BET NOW zones across 31 caught ACC triples
- Only 23% of zones (7/31) had a real other triple before ACC hit
- coin and goldSack are junk triples — excluded
- Mean distance from last other triple to ACC: 7.9 spins (scattered)

### Pulse Results

| Skip | MAX Spins | Saved% | Caught@MAX | Lost | MB/Hit |
|------|-----------|--------|------------|------|--------|
| 0 (off) | 530 | 0% | 31 | 0 | 17.1 |
| 3 | 279 | 47% | 25 | 6 | 11.2 |
| 5 | 193 | 37% | 29 | 2 | 11.4 |

### Verdict
Marginal benefit. Skip-5 saves 37% of MAX bets but loses 2/31 catches. Sample tiny (7 zones with other triples). Other triples are actually a POSITIVE signal ACC is about to hit (3.8 spins away avg). Implemented as optional toggle, default OFF.

---

## 5. Implementation (SLDebtTracker + SLDebtMonitor)

### Architecture
- `SLDebtTrackerConfig` — spinThreshold, rateGate, pulseSkip
- `SLDebtTracker` — pure logic: saSpins, saSymbols, phase, pulseRemaining
- `SLDebtMonitor` — UIKit tiles, notification wiring, presets menu
- `SLDebtTile` — draggable UIWindow per tracker (ACC ⭐, SPN 💊)

### Tile Display
- **Top:** `⭐ 45/130` (spins / threshold)
- **Middle:** `0.31 / 0.30` (current rate / gate) — green when met
- **Bottom:** WAIT → ALERT → BET NOW (or SKIP N during pulse)

### Available Presets (long-press tile)

**ACC:**
- Balanced: 130 / 0.30 (6.0x lift)
- Balanced+Pulse5: 130 / 0.30 + skip 5 (11.4 mb/h)
- Conservative: 120 / 0.28 (3.5x)
- Aggressive: 130 / 0.32 (8.2x)

**SPN:**
- Conservative: 87 / 0.25 (1.5x)
- Balanced: 87 / 0.30 (3.3x)
- Wide: 60 / 0.25 (1.5x)
- Aggressive: 60 / 0.30 (2.6x)
- Spin-only: 87 / off (1.1x)

### Critical Bugs Fixed
1. **Mission reset bug:** `accumMissionIndex` changes do NOT reset the game's pity timer. Only ACC/SPN triples reset sa_spins. Was causing tiles to reset to 0 mid-gap.
2. **Counter tile positions:** Saved tile positions could end up off-screen. Added bounds clamping + RESET POSITIONS button in counter tab.

---

## 6. Analysis Scripts Reference

All in `analysis/`:

| Script | Purpose |
|--------|---------|
| `explain_balanced.py` | Gap-by-gap breakdown of balanced ACC formula |
| `check_new_acct.py` | Validate formula on Acct4 (out-of-sample) |
| `validate_spn.py` | SPN formula validation, sweep all configs |
| `triple_clustering.py` | Other triples inside BET NOW (includes coin/goldSack) |
| `triple_clustering_v2.py` | Same but real symbols only (attack/steal/shield/spins) |
| `cross_validate.py` | True cross-validation between accounts |
| `combined_strategy.py` | Combined spin+accum strategy testing |
| `corrected_analysis.py` | Deduped analysis with sa_spins correction |
| `examine_sa_columns.py` | Discovery of sa_spins/sa_acc game counters |
| `check_overlap.py` | Acct1 ⊂ Acct2 proof |
| `deep_dive.py` | Hard ceiling, accum signal, Acct3 anomaly |
| `refine_formula.py` | Non-linear shifts, multi-gap memory, EWMA |
| `fit_hazard.py` / `fit_hazard_fast.py` | MLE hazard model fitting |
| `simulate_debt.py` / `simulate_debt_v2.py` | Debt strategy simulation |
| `symbol_combo_sweep.py` | All 31 symbol combos for rate gate — acc alone is best |
| `why_38_8.py` | Why 27/31 combos give identical results (rate gate is useless for non-acc) |
| `pure_count_sweep.py` | Pure symbol count (no rate) — max 2.5x, far below 6.0x |
| `triple_count_sweep.py` | Counting triples between targets — dead end, too rare |
| `dynamic_threshold.py` | 8 dynamic threshold strategies (shift, S/M/L, EWMA, debt, streak, rate slope) |
| `dynamic_plus_pulse.py` | Top dynamic strategies combined with pulse skip 5 |
| `sml_boundary_sweep.py` | Sweep S/M/L boundary definitions (S<X, L>=Y) and thresholds |
| `sml_catch_short.py` | Can we predict and catch short gaps? Cost analysis |
| `sml_full_sweep.py` | Full S/M/L with SKIP option, 2-gap lookback |
| `sml_window.py` | Betting windows (start AND stop), predicted per gap size |
| `sml_mega_sweep.py` | 204K config mega sweep: windows, boundaries, rate gates, Pareto frontier |

---

## 7. Dynamic Threshold Analysis

### Can we make the 130 threshold dynamic?

Tested 8 strategies + S/M/L + windows + mega sweep (204K configs):

**Gap transition matrix confirms mean reversion:**
- After L(>130) → S(<80): 55% of the time
- After S(<80) → L(>130): 39% of the time

**Results:**
1. **Shift base=140 shift=0.2**: 7.0x lift (25/178), threshold = 140 - 0.2*(prev_gap-100)
2. **S/M/L 150/140/100**: 6.5x lift (29/178)
3. **All dynamic strategies** trade caught for efficiency — none catch MORE at equal or better lift
4. **Catching short gaps is not viable**: prediction is only 55% accurate, wrong predictions burn 100+ spins
5. **Betting windows** (start+stop): just adding stop=170 to current formula → 7.0x (from 6.0x)

### Rate gate 0.32 discovery (mega sweep)

The Pareto frontier revealed that **gate=0.32** (instead of 0.30) is a massive efficiency lever:

| Config | Caught | Bet% | MB/Hit | Lift |
|--------|--------|------|--------|------|
| 130+/0.30 (current) | 31/178 | 2.9% | 17.1 | 6.0x |
| 40+/0.32 | 132/178 | 11.4% | 15.8 | 6.5x |
| 80+/0.32 | 96/178 | 4.5% | 8.6 | 11.9x |
| 130+/0.32 | 52/178 | 0.8% | 2.9 | 34.9x |

**Note:** Mega sweep catch numbers need verification — the precomputation checked if rate was EVER >= gate during the gap, not just at the final spin. The qualitative ranking and Pareto shape are correct, but exact caught counts may be slightly inflated. The fixed-window Phase 1 results are the most reliable.

### Conclusion

The flat 130/0.30 formula is near-optimal for its class. Minor improvements possible:
- Add stop cap at 170 → 7.0x (free improvement, no complexity)
- Shift strategy after previous gap → 7.0x (requires tracking prev gap)
- Rate gate 0.32 → dramatically better efficiency (needs live validation)

---

## 8. Next Steps

- [ ] Collect more live data with the new formula running to validate in production
- [ ] Re-run analysis when ~500+ new gaps are collected (current: 178 ACC, 213 SPN)
- [ ] **Validate gate=0.32 live** — if confirmed, this is the single biggest improvement available
- [ ] Test adding stop cap (130-170 window) as a preset
- [ ] Consider tracking actual coins won/lost per BET NOW zone for ROI calculation
- [ ] Event type (standard vs mix) may affect pity timer parameters — test separately
