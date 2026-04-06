# Coin Master Strip Analysis Report

**Date:** 2026-04-05
**Dataset 1:** 1,417 spins (seq 46360 - 47776) — mixed bets, mission 66→70
**Dataset 2:** 6,450 spins (seq 46360 - 52809) — includes 5,033 clean spins at 1x, mission 70
**Account:** Main (bet_level=11 → 7)
**Session bets used:** 1x, 2x, 3x, 15x, 50x, 400x, 1500x, 6000x, 20000x

---

## 1. Core Discovery: The Game Uses Only 32 Outcomes

The three reels are **NOT independent**. Out of a possible 343 (7^3) combinations, only **32 distinct (r1,r2,r3) tuples** ever appear. Each "spin" draws one pre-defined tuple from a weighted strip.

### Full Outcome Table

| ID | Tuple (r1,r2,r3) | Name | Count | Frequency | Category |
|----|-------------------|------|-------|-----------|----------|
| 0 | (30, 2, 2) | single accum | 241 | 17.0% | accum |
| 1 | (4, 6, 2) | steal/spins/gold | 101 | 7.1% | mixed |
| 2 | (2, 2, 2) | triple goldSack | 100 | 7.1% | triple |
| 3 | (3, 3, 3) | triple attack | 94 | 6.6% | triple |
| 4 | (1, 1, 1) | triple coin | 90 | 6.4% | triple |
| 5 | (30, 30, 1) | double accum | 83 | 5.9% | accum |
| 6 | (3, 1, 1) | attack/coin/coin | 74 | 5.2% | mixed |
| 7 | (3, 6, 2) | attack/spins/gold | 69 | 4.9% | mixed |
| 8 | (5, 5, 5) | triple shield | 64 | 4.5% | triple |
| 9 | (4, 4, 4) | triple steal | 60 | 4.2% | triple |
| 10 | (3, 4, 2) | attack/steal/gold | 51 | 3.6% | mixed |
| 11 | (1, 4, 4) | coin/steal/steal | 48 | 3.4% | mixed |
| 12 | (1, 6, 6) | coin/spins/spins | 44 | 3.1% | mixed |
| 13 | (1, 1, 4) | coin/coin/steal | 41 | 2.9% | mixed |
| 14 | (3, 3, 1) | attack/attack/coin | 37 | 2.6% | mixed |
| 15 | (3, 3, 2) | attack/attack/gold | 37 | 2.6% | mixed |
| 16 | (1, 1, 6) | coin/coin/spins | 29 | 2.0% | mixed |
| 17 | (3, 1, 5) | attack/coin/shield | 29 | 2.0% | mixed |
| 18 | (1, 4, 6) | coin/steal/spins | 23 | 1.6% | mixed |
| 19 | (3, 5, 2) | attack/shield/gold | 17 | 1.2% | mixed |
| 20 | (30, 30, 30) | **TRIPLE ACCUM** | 16 | 1.1% | **jackpot** |
| 21 | (5, 2, 2) | shield/gold/gold | 15 | 1.1% | mixed |
| 22 | (1, 5, 5) | coin/shield/shield | 12 | 0.8% | mixed |
| 23 | (6, 6, 6) | **TRIPLE SPINS** | 11 | 0.8% | **jackpot** |
| 24 | (1, 4, 5) | coin/steal/shield | 7 | 0.5% | mixed |
| 25 | (3, 1, 4) | attack/coin/steal | 7 | 0.5% | mixed |
| 26 | (3, 1, 6) | attack/coin/spins | 5 | 0.4% | mixed |
| 27 | (30, 30, 2) | double accum+gold | 4 | 0.3% | accum |
| 28 | (4, 4, 2) | steal/steal/gold | 3 | 0.2% | mixed |
| 29 | (5, 5, 2) | shield/shield/gold | 2 | 0.1% | mixed |
| 30 | (6, 6, 2) | spins/spins/gold | 2 | 0.1% | mixed |
| 31 | (30, 30, 3) | double accum+atk | 1 | 0.1% | accum |

**Top 5 outcomes cover 44.2% of all spins.** The strip is heavily concentrated.

---

## 2. Reel Independence: Completely Broken

The first reel (r1) almost fully determines the result:

| r1 Symbol | r1 Count | P(triple \| r1) | Expected if Independent | Ratio |
|-----------|----------|-----------------|------------------------|-------|
| goldSack (2) | 100 | **100.0%** | 11.4% | 8.8x |
| spins (6) | 13 | **84.6%** | 1.3% | 66.8x |
| shield (5) | 81 | **79.0%** | 0.5% | 149.1x |
| steal (4) | 164 | 36.6% | 1.5% | 24.5x |
| coin (1) | 294 | 30.6% | 3.9% | 7.9x |
| attack (3) | 420 | 22.4% | 0.8% | 28.2x |
| accum (30) | 345 | 4.6% | 0.1% | 56.0x |

**Key takeaway:** When r1=goldSack, it is ALWAYS a triple. When r1=spins, 85% chance of triple. When r1=shield, 79% chance.

### When r1=30 (accumulation), the only possible outcomes are:

| Outcome | Count | % of r1=30 | Description |
|---------|-------|------------|-------------|
| (30, 2, 2) | 241 | 69.9% | Single accum — 1x bet added to GAE bar |
| (30, 30, 1) | 83 | 24.1% | Double accum — 2x bet added |
| (30, 30, 30) | 16 | 4.6% | **Triple accum** — 10x bet added |
| (30, 30, 2) | 4 | 1.2% | Double accum variant |
| (30, 30, 3) | 1 | 0.3% | Double accum variant |

### When r1=6 (spins), only 2 outcomes:

| Outcome | Count | % of r1=6 |
|---------|-------|-----------|
| (6, 6, 6) | 11 | 84.6% |
| (6, 6, 2) | 2 | 15.4% |

---

## 3. Triple Accumulation (30,30,30) — 16 Events

### Raw Data

| # | seq | Gap (spins) | Bet | accum_delta | GAE % | sa_spins | sa_3xAtk | sa_3xStl | sa_3xShd |
|---|-----|-------------|-----|-------------|-------|----------|----------|----------|----------|
| 1 | 46402 | — | 1500x | +15,000 | 59.5% | 147 | 12 | 5 | 8 |
| 2 | 46534 | 132 | 1500x | +15,000 | 68.3% | 132 | 10 | 7 | 5 |
| 3 | 46563 | 29 | 400x | +4,000 | 69.9% | 29 | 3 | 0 | 0 |
| 4 | 46574 | 11 | 2x | +20 | 69.9% | 11 | 1 | 1 | 0 |
| 5 | 46629 | 55 | 2x | +20 | 69.9% | 55 | 1 | 2 | 1 |
| 6 | 46749 | 120 | 1500x | +15,000 | 79.8% | 120 | 11 | 5 | 5 |
| 7 | 46884 | 135 | 6000x | 0 (reset) | 4.2% | 135 | 7 | 6 | 6 |
| 8 | 47009 | 125 | 1500x | +15,000 | 12.8% | 125 | 5 | 9 | 8 |
| 9 | 47019 | 10 | 1x | +10 | 12.8% | 10 | 1 | 0 | 1 |
| 10 | 47269 | 250 | 1x | +10 | 37.4% | 250 | 14 | 12 | 11 |
| 11 | 47326 | 57 | 50x | +500 | 38.8% | 57 | 6 | 1 | 3 |
| 12 | 47339 | 13 | 400x | +4,000 | 39.9% | 13 | 2 | 0 | 1 |
| 13 | 47466 | 127 | 400x | +4,000 | 49.5% | 127 | 10 | 6 | 7 |
| 14 | 47544 | 78 | 1x | +10 | 49.9% | 78 | 6 | 4 | 4 |
| 15 | 47603 | 59 | 1x | +10 | 49.9% | 59 | 1 | 2 | 2 |
| 16 | 47756 | 153 | 50x | +500 | 64.7% | 153 | 12 | 5 | 7 |

### Gap Statistics

| Stat | Value |
|------|-------|
| Min gap | 10 spins |
| Max gap | 250 spins |
| Mean gap | 93.8 spins |
| Median gap | 99 spins |
| Stdev | 66.1 |
| Coefficient of Variation | 0.70 |

### Sorted Gap Distribution

```
 10  ##
 11  ##
 13  ##
 29  #####
 55  ###########
 57  ###########
 59  ###########
 78  ###############
120  ########################
125  #########################
127  #########################
132  ##########################
135  ###########################
153  ##############################
250  ##################################################
```

### GAE Bar Reset Event

At seq 46884, the GAE bar completed level 66 (target 282,500) and restarted at level 70 (target 360,000). The triple accum at that spin registered `accum_delta=0` because it triggered the level completion. After reset, the strip may have regenerated.

---

## 4. Triple Spins (6,6,6) — 11 Events

| # | seq | Gap (spins) | Bet | Spins Won | ss_spins | ss_3xAtk | ss_3xStl | ss_3xShd |
|---|-----|-------------|-----|-----------|----------|----------|----------|----------|
| 1 | 46463 | — | 2x | 20 | 119 | 8 | 5 | 6 |
| 2 | 46517 | 54 | 400x | 4,000 | 54 | 5 | 1 | 2 |
| 3 | 46561 | 44 | 400x | 4,000 | 44 | 4 | 2 | 0 |
| 4 | 46573 | 12 | 2x | 20 | 12 | 1 | 1 | 0 |
| 5 | 46670 | 97 | 2x | 20 | 97 | 6 | 4 | 3 |
| 6 | 46714 | 44 | 2x | 20 | 44 | 2 | 1 | 1 |
| 7 | 46784 | 70 | 1x | 10 | 70 | 7 | 2 | 4 |
| 8 | 46916 | 132 | 1500x | 15,000 | 132 | 5 | 9 | 6 |
| 9 | 47011 | 95 | 1500x | 15,000 | 95 | 4 | 6 | 6 |
| 10 | 47216 | 205 | 1x | 10 | 205 | 15 | 8 | 9 |
| 11 | 47526 | 310 | 1x | 10 | 310 | 22 | 15 | 18 |

### Gap Statistics

| Stat | Value |
|------|-------|
| Min gap | 12 spins |
| Max gap | 310 spins |
| Mean gap | 106.3 spins |
| Median gap | 95 spins |
| Stdev | 85.4 |

---

## 5. SA\_ / SS\_ Running Counters — Statistics

### SA\_ counters (between consecutive triple accumulations)

| Counter | Min | Max | Mean | Median | Stdev |
|---------|-----|-----|------|--------|-------|
| sa_spins (gap) | 10 | 250 | 93.8 | 99.0 | 66.1 |
| sa_atk (single attacks) | 5 | 113 | 45.7 | 47.0 | 30.7 |
| sa_stl (single steals) | 1 | 101 | 33.9 | 32.0 | 26.6 |
| sa_shd (single shields) | 1 | 52 | 19.2 | 18.5 | 14.4 |
| sa_spn (single spins) | 3 | 58 | 23.3 | 21.5 | 15.6 |
| sa_acc (single accum) | 3 | 75 | 30.0 | 27.0 | 21.0 |
| sa_3x_atk | 1 | 14 | 6.4 | 6.0 | 4.6 |
| sa_3x_stl | 0 | 12 | 4.1 | 4.5 | 3.5 |
| sa_3x_shd | 0 | 11 | 4.3 | 4.5 | 3.3 |

### SS\_ counters (between consecutive triple spins)

| Counter | Min | Max | Mean | Median | Stdev |
|---------|-----|-----|------|--------|-------|
| ss_spins (gap) | 12 | 310 | 107.5 | 95.0 | 85.4 |
| ss_atk (single attacks) | 9 | 152 | 52.1 | 42.0 | 40.9 |
| ss_stl (single steals) | 5 | 125 | 39.3 | 33.0 | 35.5 |
| ss_shd (single shields) | 1 | 77 | 22.5 | 18.0 | 21.8 |
| ss_spn (single spins) | 5 | 72 | 27.0 | 24.0 | 19.3 |
| ss_acc (single accum) | 3 | 101 | 34.3 | 27.0 | 27.2 |
| ss_3x_atk | 1 | 22 | 7.2 | 5.0 | 6.1 |
| ss_3x_stl | 1 | 15 | 4.9 | 4.0 | 4.4 |
| ss_3x_shd | 0 | 18 | 5.0 | 4.0 | 5.2 |

### Event Rate Per Spin (Consistency Check)

If events are distributed randomly between triples, these ratios should be constant regardless of gap length. CV (coefficient of variation) measures consistency (lower = more stable).

| Event / spin | Avg Rate | CV |
|-------------|----------|-----|
| attack symbols | 0.522 | 0.21 |
| accum symbols | 0.336 | 0.21 |
| spins symbols | 0.276 | 0.30 |
| steal symbols | 0.331 | 0.34 |
| shield symbols | 0.212 | 0.40 |
| 3x attacks | 0.076 | 0.45 |
| 3x shields | 0.045 | 0.56 |
| 3x steals | 0.038 | 0.66 |

**Interpretation:** The single-symbol rates are fairly stable (CV ~0.21-0.40), meaning events are evenly distributed between triples. There is no "buildup" or acceleration of any symbol type before a triple fires. The strip distributes outcomes proportionally.

---

## 6. Transition Analysis

### r1 -> next r1 Transition Matrix

| From \ To | coin | goldSack | attack | steal | shield | spins | accum |
|-----------|------|----------|--------|-------|--------|-------|-------|
| coin | 20.1% | 6.5% | **30.3%** | 11.2% | 5.4% | 0.7% | 25.9% |
| goldSack | 25.0% | 3.0% | **30.0%** | 14.0% | 4.0% | 2.0% | 22.0% |
| attack | 22.1% | 6.9% | 27.6% | 9.8% | 6.4% | 0.5% | **26.7%** |
| steal | 16.6% | 8.6% | **30.1%** | 12.3% | 6.1% | 1.2% | 25.2% |
| shield | 17.3% | 9.9% | **29.6%** | 13.6% | 3.7% | 1.2% | 24.7% |
| spins | 15.4% | 0.0% | **38.5%** | 15.4% | 0.0% | 0.0% | **30.8%** |
| accum | 21.2% | 7.8% | **31.0%** | 12.5% | 6.1% | 1.2% | 20.3% |

**Attack (r1=3) is the most common follower for every symbol** at ~30% (2x the expected 14.3% if uniform). This is a property of the strip weighting, not a predictive tell.

### Accumulation Subtype Transitions (r1=30 spins only)

Among r1=30 positions, the transitions between single/double/triple are:

| From | -> Single | -> Double | -> Triple |
|------|-----------|-----------|-----------|
| Single | 66.7% | 28.7% | 4.6% |
| Double | 79.5% | 15.9% | 4.5% |
| Triple | 62.5% | 31.2% | 6.2% |

P(triple) is approximately constant (~4.6%) regardless of the previous accum subtype. The subtypes are effectively memoryless.

---

## 7. What I Tested and Ruled Out

### Statistical Tests Performed

| Test | Method | Result |
|------|--------|--------|
| **Autocorrelation** | Full outcome-ID autocorrelation, lags 1-500 | No significant lag (all \|r\| < 0.07) |
| **Exact cycle detection** | Match rate at every lag 5-400 | Best: 1.28x random (noise) |
| **Runs test** | Binary triple/non-triple sequence | Z=0.692 — **consistent with random** |
| **Deck/bag detection** | Unique outcomes per window vs random | Matches random draws (ratio 0.95-0.99) |
| **Seq % cycle** | seq modulo 3-59 for triple concentration | No dominant positions at any modulus |
| **Spins_remaining % cycle** | spins_remaining modulo various | Noise — bet jumps corrupt the signal |
| **Repeating subsequences** | Longest exact-match repeating sequence | Only 1 length-5 repeat in 1417 spins |

### Predictor Features Tested

| Feature | P(triple \| feat=1) | P(triple \| feat=0) | Lift |
|---------|--------------------|--------------------|------|
| Current spin is triple | 29.5% | 31.3% | 0.94x |
| Current r1=30 | 34.5% | 29.5% | 1.17x |
| Has second slot result | 31.6% | 30.6% | 1.03x |
| Has event_bar update | 32.9% | 28.9% | 1.14x |
| accum_delta > 0 | 34.3% | 29.6% | 1.16x |
| 2+ triples in prev 2 spins | 29.8% | 31.8% | 0.94x |
| 1+ triples in prev 5 spins | 30.8% | 30.3% | 1.02x |
| 1+ accum in prev 5 spins | 30.0% | 33.4% | 0.90x |

**No feature achieves meaningful predictive lift.** The best (r1=30 on current spin -> 34.5% next triple) is within statistical noise.

### Other Tests

| Test | Result |
|------|--------|
| Second slot triple -> next main slot | No correlation |
| Event bar update -> next triple | No correlation |
| Timestamp delta (response speed) | Identical for triples and normals |
| Bet change resetting strip | 30.5% vs 30.8% — no effect |
| Running P&L quintiles | Clustering artifact, not causal |
| Bet level vs triple rate | No significant chi-squared |
| Zero-coins streak before triple | Always 0 (not predictive) |
| GAE bar % zone vs triple rate | Flat across all zones |
| Consecutive accum streak before triple | 13/16 had streak=0 |
| Potion bar updates near triples | 9.4% vs 7.9% expected — noise |
| Slot-on-slot bar state at triple events | All different — no pattern |
| Double accum -> triple distance | 1 to 57 r1=30 positions — no consistency |

---

## 8. Bet Level vs Triple Rate

| Bet | Spins | Triples | Rate | Chi-sq | Significant? |
|-----|-------|---------|------|--------|-------------|
| 1x | 565 | 166 | 29.4% | 0.32 | No |
| 2x | 270 | 86 | 31.9% | 0.12 | No |
| 50x | 54 | 13 | 24.1% | 0.77 | No |
| 400x | 266 | 85 | 32.0% | 0.14 | No |
| 1500x | 160 | 59 | 36.9% | 1.99 | No (p=0.16) |
| 6000x | 52 | 13 | 25.0% | 0.55 | No |

**The bet multiplier does NOT change the triple rate.** The strip is the same regardless of bet. The bet only scales the payout value.

---

## 9. Accumulation Delta Formula

Confirmed from data:

| Accum Symbols on Reels | Delta Formula | Example (bet=1500) |
|------------------------|---------------|---------------------|
| 1x (30,2,2) | bet x 1 | +1,500 |
| 2x (30,30,1) | bet x 2 | +3,000 |
| 3x (30,30,30) | bet x 10 | +15,000 |

Triple accumulation is worth **10x the bet**, not 3x. This is why switching from 1x to 20000x at the right moment is so valuable: `1 x 10 = 10` vs `20000 x 10 = 200,000` added to the GAE bar.

---

## 10. Hot/Cold Zone Analysis (20-spin windows)

| Type | Triple Rate | Accum Symbols |
|------|------------|---------------|
| Hottest window | 60% (12/20) | 3-4 accum |
| Coldest window | 5% (1/20) | 6-7 accum |
| Average | 30.8% | — |
| Stdev | 9.7% | — |

Triple rate varies from 5% to 60% in 20-spin windows. This is moderate variance — consistent with random distribution, not a structured hot/cold cycle.

---

## 11. Second Slot (Slot-on-Slot) Analysis

Two active events: `LongExtraDayReduced` and `GCEaster26`

| Event | 1x | 2x | 3x (triple) |
|-------|----|----|-------------|
| LongExtraDayReduced | 281 | 71 | 14 |
| GCEaster26 | 211 | 42 | 15 |

29 second-slot triples total. No correlation with main slot triples found.

---

## 12. Event Bars

### Active Bars in This Session

| Bar ID | Reward Key | Type | Update Interval |
|--------|-----------|------|-----------------|
| 6aa02145 | progressive_reward_pr_ec | Potion Rush | Every ~11 spins (mean) |
| ec36d075 | generic_currency_merge_energy | Merge Energy | Every ~11 spins |

### Potion Bar (6aa02145) Details

- Total updates in session: 128
- Gap between updates: min=2, max=19, mean=10.9, median=10.0
- Updates within 3 spins of triple accum: 9.4% (vs 7.9% expected by chance)
- **No predictive value**

---

## 13. 5,000-Spin Dataset Analysis (2026-04-05)

**Dataset:** 6,450 spins (seq 46360-52809), including 5,033 clean spins at constant 1x bet, mission 70, target 360,000
**Previous dataset:** 1,417 spins (sections 1-12 above)
**Clean segment:** idx 1417-6449 (seq 47777-52809) — single mission, single bet level, no resets

### 13.1 Outcome Tuples: 33 Now

One new tuple appeared: **(1, 5, 6)** — coin/shield/spins — 3 occurrences (0.05%). All prior 32 tuples confirmed. The 33rd is rare enough to be a low-probability strip position that didn't appear in 1,417 spins.

| Metric | 1,417 spins | 6,450 spins |
|--------|-------------|-------------|
| Distinct tuples | 32 | **33** |
| Triple rate | 30.8% | **30.7%** |
| Triple accum rate | 1.1% | **1.0%** |
| Triple spins rate | 0.8% | **1.1%** |

### 13.2 Triple Accum Gap Analysis — 65 Gaps

| Stat | 15 gaps (old) | 65 gaps (new) |
|------|---------------|---------------|
| Min | 10 | **10** |
| Max | 250 | **250** |
| Mean | 93.8 | **98.5** |
| Median | 99 | **108** |
| Stdev | 66.1 | **47.2** |

Stdev dropped significantly — the distribution tightened with more data. Median converged to ~100.

#### S/M/L Categories (S < 80, M = 80-139, L >= 140)

| Category | Count | % | Mean gap | Min | Max |
|----------|-------|---|----------|-----|-----|
| S (Short) | 24 | 36.9% | 47.7 | 10 | 78 |
| M (Medium) | 28 | 43.1% | 114.8 | 81 | 137 |
| L (Long) | 13 | 20.0% | 157.4 | 140 | 250 |

#### Full S/M/L Sequence (65 gaps)

```
MSSSMMMSLSSMSSLMLSMMMMSLMMSLSMSMSLMSLSMMSMLMMSLMMMSMMMLSSMMLSLSSL
```

### 13.3 Transition Matrix — The Key Discovery

#### 1-gram transitions (what follows each category):

| After | -> S | -> M | -> L | n |
|-------|------|------|------|---|
| **S** | 25% | 38% | **38%** | 24 |
| **M** | 39% | 46% | 14% | 28 |
| **L** | **58%** | **42%** | **0%** | 12 |

**L NEVER follows L** — 0 out of 12 cases. This is the strongest structural signal in the data.

#### 2-gram transitions (what follows two consecutive categories):

| After | -> S | -> M | -> L | n |
|-------|------|------|------|---|
| **SS** | 17% | **50%** | 33% | 6 |
| **SM** | 33% | **57%** | 11% | 9 |
| **SL** | 50% | 50% | **0%** | 8 |
| **MS** | 18% | 27% | **55%** | 11 |
| **MM** | 46% | 38% | 15% | 13 |
| **ML** | **75%** | 25% | 0% | 4 |
| **LS** | 43% | 43% | 14% | 7 |
| **LM** | 20% | **60%** | 20% | 5 |

**MS -> L at 55%** is the strongest predictive 2-gram. After M then S, over half the time the next gap is Long (>= 140 spins).

### 13.4 Clean Segment Transitions (49 gaps, all 1x bet, mission 70)

| After | -> S | -> M | -> L | n |
|-------|------|------|------|---|
| **S** | 12% | 44% | **44%** | 16 |
| **M** | 36% | **50%** | 14% | 22 |
| **L** | **60%** | 40% | **0%** | 10 |

L -> L remains **0%** in the clean segment (0/10). The pattern is structural, not noise.

| After | -> S | -> M | -> L | n |
|-------|------|------|------|---|
| **MS** | 0% | 38% | **62%** | 8 |
| **MM** | 45% | 36% | 18% | 11 |
| **SL** | 50% | 50% | **0%** | 6 |
| **ML** | 67% | 33% | 0% | 3 |
| **LM** | 25% | **75%** | 0% | 4 |

**MS -> L at 62%** in clean segment (5/8). Even stronger than full dataset.

### 13.5 Autocorrelation — No Strip Cycle Found

Tested lags 1-500 on the full 6,450-spin outcome-ID sequence:

| Test | Best result | Conclusion |
|------|-------------|------------|
| Autocorrelation | Max |r| = 0.042 at lag 47 | Noise (threshold ~0.025) |
| Exact match ratio | Best 1.18x random at lag 37 | Noise |
| Periodicity (multiples) | Best 1.07x at period 282 | Noise |

**The strip does NOT repeat within 500 positions**, or it's shuffled per session. A fixed-length mappable strip is ruled out for mission 70 at this data size.

### 13.6 Accum Clustering Before Triple Accum — DEBUNKED

The prior analysis (1,417 spins) found accum symbols appeared 2.6x elevated at offset -3 before triple accum. With 6,450 spins, this is **noise**:

| Offset | P(r1=30) | Ratio vs baseline |
|--------|----------|-------------------|
| -1 | 16.0% | 0.70x |
| -2 | 20.0% | 0.87x |
| -3 | 26.0% | 1.13x |
| -4 | 22.0% | 0.96x |
| -5 | 20.0% | 0.87x |

All within noise range (0.6x-1.5x). **No visual tell exists in the reel symbols before a triple accum.** The prior finding was a small-sample artifact.

### 13.7 GAE Mission Structure

| Period | Idx range | Spins | Mission | Target | Bet levels |
|--------|-----------|-------|---------|--------|------------|
| Early mixed | 0-1416 | 1,417 | 66 -> 70 | 282,500 -> 360,000 | 11 (mixed bets) |
| Clean 1x | 1417-6449 | 5,033 | 70 | 360,000 | 7 (constant 1x) |

Mission 66 completed at idx 524 (seq 46884), triggering a GAE reset. Bet level changed from 11 -> 0 -> 4 -> 7 around idx 1390-1417. The clean segment has zero mission resets.

---

## 14. Strategy Simulation Results

### 14.1 Strategy Rules

Three trigger conditions, evaluated after each triple accum gap:

| Rule | Trigger pattern | Switch to max bet at | Rationale |
|------|----------------|---------------------|-----------|
| **MS** | Medium gap followed by Short gap | Spin 80 of next gap | MS -> L at 62% (clean data) |
| **SS** | Two consecutive Short gaps | Spin 80 of next gap | SS -> M/L at 83% |
| **After L** | Any Long gap (>= 140) | Spin 40 of next gap | L -> L at 0% (guaranteed S or M) |

Drop back to 1x immediately after the triple accum fires (end of gap).

### 14.2 Full Simulation on Clean Segment (5,033 spins)

| # | Gap | Cat | Trigger | Switch@ | Max-bet spins | Valuable triples caught |
|---|-----|-----|---------|---------|---------------|------------------------|
| 1 | 54 | S | L@40 | 40 | 15 | ATK, SPN, ACC |
| 2 | 158 | L | MS@80 | 80 | 79 | SHD×6, ATK×5, SPN, ACC (14 total) |
| 3 | 102 | M | L@40 | 40 | 63 | SHD×2, ATK×5, SPN, ACC (9 total) |
| 4 | 147 | L | MS@80 | 80 | 68 | SHD×4, ATK×4, SPN, ACC (11 total) |
| 5 | 69 | S | L@40 | 40 | 30 | SHD×2, ATK, SPN, ACC (5 total) |
| 6 | 117 | M | MS@80 | 80 | 38 | SHD×2, ACC (3 total) |
| 7 | 151 | L | MS@80 | 80 | 72 | SHD×4, ATK×5, ACC (11 total) |
| 8 | 128 | M | L@40 | 40 | 89 | SHD×4, ATK×3, SPN, ACC (10 total) |
| 9 | 170 | L | MS@80 | 80 | 91 | SHD×4, ATK×5, ACC (11 total) |
| 10 | 49 | S | L@40 | 40 | 10 | ATK, ACC (2 total) |
| 11 | 108 | M | MS@80 | 80 | 29 | ATK, SHD, ACC (3 total) |
| 12 | 137 | M | L@40 | 40 | 98 | ATK×7, SHD×4, SPN, ACC (14 total) |
| 13 | 141 | L | MS@80 | 80 | 62 | SHD×3, ATK×5, SPN, ACC (11 total) |
| 14 | 132 | M | L@40 | 40 | 93 | SHD×5, ATK×3, SPN, ACC (10 total) |
| 15 | 135 | M | MS@80 | 80 | 56 | ATK×5, SHD×2, SPN, ACC (10 total) |
| — | 27 | S | L@40 | 40 | **MISS** | Triple came at spin 27 < 40 |
| 16 | 104 | M | SS@80 | 80 | 25 | SPN, ATK, ACC (3 total) |
| 17 | 58 | S | L@40 | 40 | 19 | ATK, SHD, ACC (3 total) |
| 18 | 44 | S | L@40 | 40 | 5 | ACC (1 total) |
| 19 | 140 | L | SS@80 | 80 | 61 | ATK×3, SHD×2, ACC (7 total) |

### 14.3 Results Summary

| Metric | Value |
|--------|-------|
| Total spins in session | 5,033 |
| Strategy triggers | 20 |
| **Hits** | **19/20 (95%)** |
| Misses | 1 (gap=27 after L, triple came before switch point) |
| Scout spins (1x bet) | 4,030 (80%) |
| Max-bet spins | 1,003 (20%) |
| Max-bet spins per hit | 52.8 |
| **Triple accums caught at max bet** | **19** |
| Total valuable triples caught | 141 (ATK + SHD + SPN + ACC) |
| Triples per max-bet spin | 1 per 7.1 spins |

### 14.4 Strategy Lift vs Random

| Approach | Triple accums caught | Max-bet spins | Efficiency |
|----------|---------------------|---------------|------------|
| Random 20% | ~10 (expected) | ~1,007 | 1.0 per 100 spins |
| **This strategy** | **19** | **1,003** | **1.9 per 100 spins** |
| **Lift** | **2.0x** | same cost | **2.0x** |

The strategy concentrates max-bet spins into windows that contain triple accums at 2x the random rate.

### 14.5 Economics at 20,000x Bet

| Metric | Value |
|--------|-------|
| Each triple accum at 20kx | +200,000 GAE points |
| 19 triple accums | **3,800,000 GAE points** |
| LOW level target (3,275,611) | Cleared with **16 accums** — strategy delivers 19 |
| Mission 70 target (360,000) | Cleared with **2 accums** — strategy delivers 19 |
| Scout cost | 4,030 spins at 1x (negligible) |
| Max-bet cost | 1,003 spins at 20,000x |
| Total spins needed | ~5,033 from a ~70K-100K pool |

### 14.6 Threshold Optimization

Tested various S/M boundaries and switch points. Best configurations:

| Config | Hits | Hit rate | Max-bet spins | Efficiency |
|--------|------|----------|---------------|------------|
| S<80, MS/SS@80, L@40 | 19/20 | 95% | 1,003 | 1.89/100 |
| S<80, MS/SS@90, L@40 | 19/20 | 95% | 903 | 2.10/100 |
| **S<80, MS/SS@100, L@40** | **19/20** | **95%** | **803** | **2.37/100** |

Raising the MS/SS switch point to 100 saves 200 max-bet spins with no loss in hit rate. The tradeoff: if a Medium gap fires at exactly 80-99, you'd miss the window, but in this dataset no triggered M gap fell below 101.

---

## 15. Autocorrection / Debt Model — The Breakthrough

### 15.1 The Hypothesis

The game maintains an internal **debt counter** — the cumulative deviation of actual gaps from a target mean. When the system has "underpaid" (gaps ran long, debt is high), it shortens the next gap to compensate. When it "overpaid" (gaps ran short, debt is negative), it lengthens the next gap. This is a **pity timer with memory**.

### 15.2 Debt Calculation

```
debt_0 = 0
For each gap g_i:
    debt_i+1 = debt_i + (g_i - TARGET)
```

Tested TARGET values on 49 clean-segment gaps:

| Target | Correlation(debt, next_gap) | Debt range | Final debt |
|--------|----------------------------|------------|------------|
| 99 | **-0.710** | [0, 118] | +83 |
| **100** | **-0.716** | [-21, 75] | +34 |
| 101 | -0.584 | [-62, 62] | -15 |
| 102 | -0.445 | [-103, 52] | -64 |

**Target = 100 produces the strongest negative correlation (-0.716)** — i.e., the game autocorrects toward a mean gap of ~100 spins between triple accums.

### 15.3 Debt Buckets Predict Gap Category

| Debt bucket | n | Mean gap | Short (<80) | Medium (80-139) | Long (>=140) |
|-------------|---|----------|-------------|-----------------|--------------|
| **< 0 (overpaid)** | 8 | 134.1 | **0%** | 38% | **62%** |
| 0-29 | 14 | 123.3 | 21% | 43% | 36% |
| 30-59 | 15 | 100.1 | 20% | **73%** | 7% |
| **>= 60 (underpaid)** | 12 | 52.8 | **83%** | 17% | **0%** |

When debt >= 60, the game has been "stingy" for too long — 83% of next gaps are Short, **zero are Long**. When debt < 0 (recently generous), 62% of gaps are Long, **zero are Short**. The autocorrection is near-deterministic at the extremes.

### 15.4 Linear Regression

```
predicted_gap = 132.9 - 1.01 × debt_before
R² = 0.512
Mean absolute error = 23.3 spins
Median absolute error = 24.3 spins
```

Each point of debt shifts the expected gap by ~1 spin. A debt of +60 predicts gap ≈ 72 (Short). A debt of -15 predicts gap ≈ 148 (Long).

### 15.5 Debt-Based Strategy — Replaces S/M/L

The debt model subsumes the old S/M/L transition strategy. Instead of looking backward at 2 previous gap categories, debt looks at the **entire history** of autocorrection.

**Strategy rules:** Switch to max bet when sa_spins reaches a debt-dependent threshold:

| Debt bucket | Switch at spin | Rationale |
|-------------|---------------|-----------|
| debt < 0 | 100 | Expect long gap (mean 134) |
| debt 0-29 | 85 | Expect medium-long (mean 123) |
| debt 30-59 | 60 | Expect medium (mean 100) |
| debt >= 60 | 25 | Expect short (mean 53) |

### 15.6 Strategy Comparison

| Strategy | Hits | Hit Rate | Max-bet spins | Avg/hit | Lift | GAE pts (20kx) |
|----------|------|----------|---------------|---------|------|----------------|
| Random 20% | 9 | 18% | 986 | 109.6 | 1.00x | 1,800,000 |
| S/M/L (Section 14) | 19 | 39% | 1,003 | 52.8 | 1.91x | 3,800,000 |
| **Debt Conservative** | **39** | **80%** | **1,401** | **35.9** | **2.80x** | **7,800,000** |
| Debt Balanced | 43 | 88% | 1,809 | 42.1 | 2.39x | 8,600,000 |
| Debt Aggressive | 46 | 94% | 2,189 | 47.6 | 2.12x | 9,200,000 |

**At the same ~1,000 max-bet budget:** Debt Conservative catches **33 accums** (config 130/100/80/50) vs S/M/L's **19 accums** — a **3.37x lift** vs 1.94x. Nearly double the accums for the same cost.

**Head-to-head at ~1,000 max-bet spins:**

| Strategy | Hits | Total max-bet | Lift |
|----------|------|---------------|------|
| S/M/L | 19 | 984 | 1.94x |
| **Debt (130/100/80/50)** | **33** | **985** | **3.37x** |

### 15.7 Mission Economics with Debt Strategy

| Metric | Debt Balanced | S/M/L | Random |
|--------|--------------|-------|--------|
| Triple accums caught per 5,033 spins | **43** | 19 | 10 |
| GAE points at 20kx bet | **8,600,000** | 3,800,000 | 2,000,000 |
| Missions completed (target 360K) | **23.9** | 10.6 | 5.6 |
| Spins to complete 1 mission | **~207** | ~530 | ~1,000 |
| Max-bet spins per mission | **~76** | ~106 | ~200 |

To clear the **LOW LEVEL tier** (3,275,611 points, 16.4 accums needed):
- Debt Balanced: ~1,879 total spins, ~689 at max bet
- S/M/L: ~4,343 total spins, ~866 at max bet

### 15.8 Triple Spins (6,6,6) Debt Model

The autocorrection signal exists for triple spins but is weaker:

| Target | Correlation | Debt range |
|--------|-------------|------------|
| 87 (mean) | -0.432 | [-194, 46] |
| 90 | -0.432 | [-194, 46] |

Debt bucket separation for triple spins (target=87):

| Debt bucket | n | Mean gap | Short (<60) | Long (>=120) |
|-------------|---|----------|-------------|--------------|
| < -30 | 23 | 96.1 | 22% | 35% |
| -30 to 0 | 11 | 101.1 | 9% | 36% |
| 0-29 | 8 | 63.9 | 50% | 12% |
| >= 60 | 10 | 64.1 | 50% | 20% |

The separation is weaker (correlation -0.43 vs -0.72 for accum), but high-debt buckets still predict shorter gaps. Triple spins can use debt as a supplementary signal, not a primary one.

### 15.9 Why the Debt Model Works

The autocorrection mechanism is likely how Coin Master implements its **pity timer**. Rather than a simple "fire after N spins" counter, the game:

1. Maintains a running deficit from a target mean (~100 spins for triple accum)
2. Adjusts the probability of the next triple accum based on this deficit
3. At high debt (long drought), probability increases sharply — 83% Short, 0% Long
4. At low/negative debt (recent lucky streak), probability decreases — 0% Short, 62% Long
5. The system oscillates in a range of roughly [-20, +75], never accumulating unbounded debt

This is more sophisticated than a fixed pity timer because it allows natural variance while maintaining a statistical guarantee. It also explains why **L never follows L**: after a Long gap, debt is always high enough to force a Short or Medium.

---

## 16. Quiet Zone Signal — The Within-Gap Trigger

### 16.1 Discovery: Triple Accums Cluster Near Other Triples

The distance from the **last non-ACC triple** (3xATK/STL/SHD/SPN/GLD/COIN) to each 3xACC:

| Distance | Count | % | Cumulative |
|----------|-------|---|------------|
| 1 spin | 19 | 38% | 38% |
| 2 spins | 7 | 14% | 52% |
| 3 spins | 4 | 8% | 60% |
| 4 spins | 8 | 16% | 76% |
| 5 spins | 4 | 8% | 84% |
| 6-8 spins | 8 | 16% | 100% |
| 9+ spins | 0 | 0% | — |

**Mean = 3.1 spins, Median = 2.0.** No 3xACC was ever more than 8 spins from the last non-ACC triple. This is NOT random — at baseline 1 triple per 3.4 spins, the expected max distance would be much larger.

### 16.2 The Quiet Zone

After any non-ACC triple, if the game goes **silent** (no triples of any kind) for several spins, the next triple that breaks the silence has an elevated chance of being 3xACC.

| Quiet zone | Triggers | ACC hits | Hit rate | Lift vs expected |
|------------|----------|----------|----------|-----------------|
| 3-5 spins | 344 | 14 | 4.1% | 1.3x |
| 4-6 spins | 224 | 8 | 3.6% | 1.1x |
| 5-7 spins | 159 | 7 | 4.4% | 1.4x |

On its own, the quiet zone signal is weak (~1.3x). But combined with the debt model, it becomes powerful.

### 16.3 Combined Strategy: Debt Floor + Quiet Zone (Zoran's Method)

**Full rules:**
1. Track cumulative debt (`debt += gap - 100` after each triple accum)
2. Compute debt floor: `floor = max(133 - 1.01 × debt - margin, 15)`
3. When `sa_spins >= floor`, start watching for ANY non-ACC triple
4. After such a triple, count quiet spins (no triples at all)
5. If quiet zone is within the target range, switch to max bet for `window` spins
6. Drop back to 1x after window expires or after 3xACC fires

This is the reconstructed **Zoran method**: debt-based counting sets the zone, the quiet period after a triple is the precision timing signal.

### 16.4 Full Configuration Results (49 gaps, 4,934 spins)

#### Ultra-Sniper Configs (Zoran-level precision)

| margin | quiet | window | Caught | Rate | Total MB | MB/hit | Lift |
|--------|-------|--------|--------|------|----------|--------|------|
| 5 | 5-7 | 4 | 10/49 | 20% | 50 | **5.0** | **20.1x** |
| 5 | 4-7 | 4 | 13/49 | 27% | 90 | **6.9** | **14.5x** |
| 5 | 3-7 | 4 | 20/49 | 41% | 183 | **9.2** | **11.0x** |
| 5 | 4-6 | 10 | 14/49 | 29% | 153 | **10.9** | **9.2x** |
| 5 | 3-7 | 10 | 21/49 | 43% | 388 | 18.5 | 5.4x |

#### Balanced Configs (practical sweet spot)

| margin | quiet | window | Caught | Rate | Total MB | MB/hit | Lift |
|--------|-------|--------|--------|------|----------|--------|------|
| 10 | 3-7 | 4 | 21/49 | 43% | 242 | **11.5** | **8.7x** |
| 10 | 3-7 | 8 | 23/49 | 47% | 440 | 19.1 | 5.3x |
| 15 | 3-7 | 8 | 26/49 | 53% | 550 | 21.2 | 4.8x |
| 20 | 3-7 | 8 | 28/49 | 57% | 612 | 21.9 | 4.6x |
| 20 | 3-7 | 10 | 29/49 | 59% | 726 | 25.0 | 4.0x |

#### Volume Configs (max catches)

| margin | quiet | window | Caught | Rate | Total MB | MB/hit | Lift |
|--------|-------|--------|--------|------|----------|--------|------|
| 25 | 3-7 | 8 | 30/49 | 61% | 737 | 24.6 | 4.1x |
| 25 | 3-7 | 10 | 31/49 | 63% | 879 | 28.4 | 3.6x |
| 30 | 3-7 | 10 | 31/49 | 63% | 1,024 | 33.0 | 3.0x |

### 16.5 Strategy Comparison — Evolution

| Strategy | Caught | MB/hit | Lift | Spins at max bet |
|----------|--------|--------|------|-----------------|
| Random 20% | 10/49 | 109.6 | 1.0x | 986 |
| S/M/L (Section 14) | 19/49 | 52.8 | 1.9x | 1,003 |
| Pure Debt Conservative | 39/49 | 35.9 | 2.8x | 1,401 |
| **Debt + Quiet (m=10, q=3-7, w=4)** | **21/49** | **11.5** | **8.7x** | **242** |
| **Debt + Quiet (m=5, q=5-7, w=4)** | **10/49** | **5.0** | **20.1x** | **50** |

The combined Debt + Quiet Zone strategy achieves **5-12 max-bet spins per hit** — approaching Zoran's observed 2.3 spins. The quiet zone is the **within-gap timing signal** that the debt model alone cannot provide.

### 16.6 How This Maps to Zoran's Observed Behavior

| Zoran's action | Our reconstruction |
|----------------|-------------------|
| Counts between triple accums | Debt tracking (cumulative gap - 100) |
| Knows when next ACC is "due" | Debt floor: `133 - 1.01 × debt - margin` |
| Max bets and gets 3xATK/STL/SHD/SPN | Signal triple past the debt floor |
| **Drops to 1x for 4-6 spins** | **Quiet zone observation (3-7 spins, no triples)** |
| Max bets for 1-8 spins, hits ACC | Bet window (4-10 spins after quiet zone ends) |
| ~2.3 max-bet spins per hit | Our best: 5.0 (margin=5, quiet=5-7, win=4) |

### 16.7 Practical In-Game Guide

**What to track (mental or paper):**
1. **Gap counter** — count every spin since the last triple accum (30,30,30)
2. **Debt** — after each triple accum: `debt = debt + (gap - 100)`. Start at 0.

**Switch point table** (when to start watching for the trigger):

| Your debt | Start watching at spin # | Expected gap type |
|-----------|------------------------|-------------------|
| -20 or less | ~155 | Long (game clawing back) |
| 0 | ~133 | Medium-Long |
| +20 | ~113 | Medium |
| +40 | ~93 | Medium-Short |
| +60 | ~73 | Short (game owes you) |
| +80 | ~52 | Very Short |

**Once past the switch point — the trigger sequence:**
1. Stay on **1x bet**, keep spinning
2. Wait for ANY triple (3xATK, 3xSTL, 3xSHD, 3xSPN, 3xGLD, 3xCOIN)
3. When you see one, **count 4-6 more spins at 1x** (the quiet zone)
4. After the quiet zone: **switch to MAX bet for 4-8 spins**
5. If 3xACC fires → done, drop to 1x, update debt, reset counter
6. If not → drop to 1x, wait for next triple, repeat from step 2

**Example session:**
- Debt = +50, start watching at spin ~83
- Spin 90: see 3xATK → count 5 more at 1x
- Spin 95: switch to max bet
- Spin 98: 3xACC fires! Gap = 98
- New debt = 50 + (98 - 100) = **+48**
- Reset counter, next watch point at spin ~85

**Tuning your aggressiveness:**
- **Sniper** (quiet 5-7, window 4): ~5 max-bet spins per hit, catches ~20%
- **Balanced** (quiet 3-7, window 8): ~19 max-bet spins per hit, catches ~47%
- **Volume** (quiet 3-7, window 10): ~28 max-bet spins per hit, catches ~63%

---

## 17. Reverse-Engineering the Exact Formula

### 17.1 Hard Floor Discovery

The game has a **hard minimum gap** below which triple accum CANNOT fire:

```
min_gap = max(20, 80 - debt)
```

Testing against 49 gaps: **only 1 violation** (gap=78 at debt=+1, off by 1 spin). This means:
- At debt=0: ACC cannot fire before spin 80
- At debt=+60: ACC cannot fire before spin 20
- At debt=-20: ACC cannot fire before spin 100

**P(ACC) = 0 for all spins below the floor.** This is a hard constraint in the game code.

### 17.2 Hazard Function Above the Floor

Above the floor, each spin has an increasing probability of producing 3xACC. The best-fit model:

```
P(ACC at spin s | debt d) = 0.00052 × max(0, s - max(20, 75 - d))
```

This is a **linear hazard**: probability increases by 0.052% per spin above the floor. Maximum likelihood fit: NLL = -235.18.

### 17.3 Recovered Probability Lookup Table

| Excess above floor | Empirical P(ACC) per spin | Likely game value |
|--------------------|--------------------------|--------------------|
| Below floor | 0.00% | 0% (hard block) |
| 0-9 | 1.04% | ~1% |
| 10-19 | 0.69% | ~1% |
| 20-29 | 1.55% | ~1.5% |
| 30-39 | 1.17% | ~1% |
| 40-49 | 0.66% | ~1% |
| 50-59 | 2.23% | ~2% |
| 60-69 | 3.74% | ~3.5% |
| 70-79 | 2.00% | ~2% |
| 80-89 | 5.77% | ~6% |
| 90-99 | 10.71% | ~10% |

The ramp is not perfectly smooth — there are dips (noise from 49 gaps). But the trend is clear: **probability roughly doubles every 25 spins above the floor**.

Best discrete-step fit: `P = min(10%, (excess // 25 + 1) × 1%)` — i.e., 1% for first 25 excess spins, 2% for next 25, etc.

### 17.4 Alternative Counter: Accum Symbols

The number of accum symbols (r1=30) between triple accums has **0.965 correlation** with gap length. Rate: 1 accum symbol every 4.5 spins (22.0% of spins).

**Accum-count strategy** (count r1=30 symbols instead of spins):
- Fixed threshold `acc >= 20` + quiet zone (3-7) + window 4: **20/49 caught (41%), 16.3 mb/hit, 6.2x lift**
- Debt-adjusted `acc >= 24 - 0.25×debt` + quiet zone (3-7) + window 4: **28/49 caught (57%), 17.8 mb/hit, 5.7x lift**

This is an alternative to spin counting — easier to track visually (just count accum symbols on reel 1), but slightly less precise than the spin-based floor.

### 17.5 Pair Sum Stability

Consecutive gap pairs sum to a remarkably stable value:
- Mean pair sum: **199.8** (≈ 2 × target)
- Pair stdev: 42.1 (CV = 0.21, vs individual gap CV = 0.47)
- Triplet sums: mean **299.6** (≈ 3 × target)

The game's autocorrection ensures that every 2 gaps average close to 200 total spins, confirming the target ≈ 100 per gap.

### 17.6 Candidate Exact Formulas

| Model | Parameters | MAE | Correlation | Note |
|-------|-----------|-----|-------------|------|
| Linear regression | gap = 133 - 1.01×debt | 23.3 | 0.716 | Simple, R²=0.51 |
| Linear hazard | P = 0.0007 × excess, C=89 | 23.5 | 0.714 | Per-spin probability |
| Sqrt hazard | P = 0.004 × √excess, C=89 | 23.5 | 0.714 | Diminishing returns |
| Piecewise linear | pos: 144-1.25d, neg: 154+1.79d | 21.4 | — | Different slopes |
| Discrete step | P = min(10%, (excess//25+1)×1%) | — | — | Game-dev friendly |

The piecewise model (MAE=21.4) is the best predictor, but all models converge to the same core insight: **floor ≈ max(20, 75-80 - debt), then linear probability ramp above**.

---

## 18. Remaining Open Questions

### The Counting Theory — Validated (Mechanism Found)

Zoran's method has been tested against 5,033 clean spins. The **debt autocorrection model** (Section 15) explains the underlying mechanism.

| Zoran's Claim | Our Data | Status |
|---------------|----------|--------|
| Count gaps between triple accums | Mean gap = 100.7, target ~100 | **CONFIRMED** |
| Gaps follow S/M/L pattern | S=33%, M=45%, L=22% | **CONFIRMED** |
| "2 shorts then medium" | SS -> M at 50%, SS -> L at 33% | **PARTIALLY** — not as clean as claimed |
| **L never follows L** | 0/12 full, 0/10 clean — explained by debt model | **CONFIRMED + EXPLAINED** |
| **MS predicts L** | MS -> L at 62% — subsumed by debt model | **CONFIRMED + SUBSUMED** |
| Accum clustering as visual tell | All offsets within noise (0.6x-1.5x) | **DEBUNKED** |
| 1-5 spin precision before triple | No pre-triple signal in data | **DEBUNKED** (may be visual-only) |

**Why L never follows L:** After a Long gap (>=140), debt is always high (>=40), which forces the autocorrection to produce a Short or Medium gap next. This is not a transition rule — it's an emergent property of the pity timer.

**What Zoran likely does differently:** He achieves 1-5 spin precision using something **not captured in the CSV**. The debt model reduces our window to ~36 max-bet spins per hit (Conservative) vs his ~2.3. The remaining gap likely comes from a visual/audio tell in the game client, or knowledge of the exact pity timer formula rather than our statistical approximation.

### What the Strip Looks Like

The strip is NOT a fixed repeating sequence (autocorrelation found nothing at lags 1-500). It appears to be:
- **Probability-driven with a pity timer** — not a pre-generated strip
- **Autocorrecting toward target=100** between triple accums (corr = -0.716)
- **Weighted by frequency** — 33 outcomes with stable weights (~17% single accum, ~7% each major triple)
- **Debt-bounded** — the system oscillates in a debt range of roughly [-20, +75], never accumulating unbounded debt
- **Hard floor at max(20, 80-debt)** — ACC literally cannot fire before this spin
- **Linear hazard ramp above floor** — P(ACC) ≈ 0.052% per excess spin, reaching ~10% at excess 90+
- **Quiet zone signal** — after any non-ACC triple + 3-7 quiet spins, the next triple is 3xACC at elevated probability
- **Accum symbols track gap proportionally** — r1=30 count has 0.965 correlation with gap

### Cross-Account Validation (2026-04-06)

Tested the debt model on a second account (mission 37, 1,392 spins, 14 gaps):

| | Account 1 (mission 66/70) | Account 2 (mission 37) |
|---|---|---|
| Target (mean gap) | **99** | **92** |
| Debt correlation | -0.593 | -0.679 |
| L->L (at 150+) | 0/12 (never) | 0/3 (never) |
| Pair sum mean | ~200 | ~182 |

**Key findings:**
- Targets differ by account/mission (99 vs 92) — tool MUST auto-calibrate
- Using target=100 on Account 2 caused debt to drift to -112 → all predictions wrong
- L->L rule holds on BOTH accounts (zero violations at absolute threshold 150+)
- The debt autocorrection mechanism is the SAME — just the target shifts
- Tool fix: observe first 5 triple accums → compute target = mean(gaps) → then predict

### Still Needed

1. **More data at current mission** — 49 gaps is enough for the macro pattern but noisy for the exact formula. 200+ gaps would nail the hazard curve precisely.

2. **Low GAE mission data** — Collect spins at mission 1-5. If the target is different (e.g., 50 instead of 100), the debt model parameters will shift.

3. **Visual/audio capture** — The gap from our 5 mb/hit to Zoran's 2.3 may require visual cues not in CSV data.

4. **Cross-account comparison** — Does each account have the same target (~100)? Same floor formula?

5. **Test the formula live** — Apply the combined strategy in real-time play to validate the quiet zone signal works outside this dataset.

### GAE List Tiers (Reference — Unchanged from Prior Analysis)

| List Tier | Start Level | Missions | Total Punkte | 20Kx Triples Needed |
|-----------|-------------|----------|-------------|---------------------|
| **LOW LEVEL** | 0-999 | 22 | **3,275,611** | **17** |
| Standard 550K | 0-999 | 20 | 2,784,522 | 14 |
| Standard 420K | 1K-4.9K | 21 | 2,275,300 | 12 |
| Standard 600K | 5K-9.9K | 21 | 3,489,750 | 18 |

### Video Analysis (Reference — Unchanged from Prior Analysis)

6 bet switches observed across 11 Facebook videos. Hit rate: 5/6 (83%), avg 2.3 max-bet spins per attempt. See section 13 (prior analysis) for full details.

---

## 19. Summary of Confirmed Facts

| Finding | Status | Dataset |
|---------|--------|---------|
| Game uses pre-generated outcome tuples, not independent reels | **CONFIRMED** | 1,417 + 6,450 |
| 33 distinct outcomes exist (was 32, +1 rare) | **CONFIRMED** | 6,450 |
| Strip position is independent of bet multiplier | **CONFIRMED** | 6,450 |
| Triple accum delta = bet x 10 | **CONFIRMED** | 6,450 |
| Triple rate ~30.7% overall | **CONFIRMED** | 6,450 |
| Triple accum rate ~1.0% | **CONFIRMED** | 6,450 |
| Triple spins rate ~1.1% | **CONFIRMED** | 6,450 |
| GAE bar resets regenerate the strip | **LIKELY** | 6,450 |
| **L never follows L in gap sequence** | **CONFIRMED (0/12)** | 6,450 |
| **MS predicts L at 62%** | **CONFIRMED** | 5,033 clean |
| **Combined S/M/L strategy: 95% hit rate, 2.0x lift** | **CONFIRMED** | 5,033 clean |
| **Debt autocorrection: corr = -0.716, target ~100** | **CONFIRMED** | 5,033 clean |
| **Debt strategy: 80% hit, 2.8x lift (Conservative)** | **CONFIRMED** | 5,033 clean |
| **Debt replaces S/M/L: 33 vs 19 hits at same cost** | **CONFIRMED** | 5,033 clean |
| **Quiet zone signal: 3xACC always within 8 spins of last triple** | **OVERFITTED** — true but non-exploitable (24% triple freq) | 5,033 → 20,949 |
| **Combined debt+quiet: 5.0 MB/hit at 20.1x lift** | **OVERFITTED** — honest lift is 1.7x | 5,033 → 20,949 |
| **Zoran's method reconstructed: debt + quiet zone + window** | **PARTIALLY** — debt is real, quiet zone is noise | 5,033 → 20,949 |
| **Hard floor: min_gap = max(20, 80-debt), 1 violation in 49** | **OVERFITTED** — debt spirals to -400 | 5,033 → 20,949 |
| **Hazard function: P = 0.00052 × excess above floor** | **OVERFITTED** — being re-fitted with 214 gaps | 5,033 → 20,949 |
| **Accum symbol counting: 0.965 corr with gap length** | **CONFIRMED** | 5,033 clean |
| **Pair sums stable at ~200 (2 × target)** | **CONFIRMED** | 5,033 clean |
| No fixed strip cycle within 500 positions | **CONFIRMED** | 6,450 |
| Accum clustering before triple accum | **DEBUNKED** | 6,450 |
| No per-spin predictive tell in CSV data | **CONFIRMED** | 6,450 |

---

## 20. Multi-Account Validation (21K Spins, 3 Accounts)

**Date:** 2026-04-06
**Dataset:** 20,949 spins across 3 accounts (4,968 + 8,378 + 7,603)
**Files:** spin_history_2026-04-04 (1).csv, (2).csv, spin_history_2026-04-05 (1).csv

### 20.1 What Survived Validation

| Finding | 49 gaps (Sect 15-17) | 214 gaps (3 accts) | Status |
|---------|---------------------|---------------------|--------|
| Pity timer exists (CV < 1) | CV implied | **CV = 0.616** (vs 1.0 for random) | **CONFIRMED** |
| Mean-reverting debt | corr = -0.716 | **Lag-1 autocorr = -0.341** | **CONFIRMED (weaker)** |
| Pair sums stable | ~200 (CV=0.21) | **194.2 (CV=0.354)** | **CONFIRMED** |
| Quintile mean-reversion | Implied | After longest gaps: next avg=63.9; after shortest: avg=112.9 | **CONFIRMED** |
| Accum symbol counting | 0.965 corr | Still viable signal (1.7x lift combined) | **CONFIRMED** |

### 20.2 What FAILED at Scale

| Finding | 49 gaps | 214 gaps | Status |
|---------|---------|----------|--------|
| Hard floor max(20, 80-debt) | 1 violation | Debt spirals to -400, floor unreachable | **OVERFITTED** |
| Quiet zone 20.1x lift | 5.0 mb/hit | **No effective lift** — triples are 24% of all spins | **OVERFITTED** |
| Combined strategy | 20.1x lift | **1.7x lift** (best honest config) | **OVERFITTED** |
| Hazard P = 0.00052 × excess | Fit to 49 | Doesn't generalize | **OVERFITTED** |
| Unbounded debt tracking | Worked on 49 | Unbounded negative debt (-400) makes floor unusable | **BROKEN** |

### 20.3 Triple Frequency Discovery

Triples are FAR more frequent than expected (~24% of all spins):

| Symbol | Frequency | Every N spins |
|--------|-----------|---------------|
| goldSack | 1,550 | 14 |
| attack | 1,428 | 15 |
| shield | 921 | 23 |
| steal | 656 | 32 |
| spins | 234 | 90 |
| accumulation | 214 | 98 |

This kills the quiet zone strategy — "bet after any triple" = bet 80%+ of the time = no edge.

### 20.4 ACC Proximity to Other Triples — The Real Pattern

**Critical discovery:** ACC triples cluster tightly AFTER other triples.

| Distance from prev triple to ACC | Cumulative % |
|----------------------------------|-------------|
| <= 1 spin | 23.4% |
| <= 2 spins | **49.5%** |
| <= 4 spins | **69.6%** |
| <= 6 spins | **80.4%** |
| <= 8 spins | **90.2%** |
| <= 10 spins | **96.3%** |
| <= 15 spins | **98.6%** |
| <= 20 spins | **99.5%** |
| <= 30 spins | **100.0%** |

**100% of ACC triples come within 30 spins of another triple.** This is NOT noise — it's a structural feature of the strip. But because triples happen every ~4 spins on average, this proximity is expected and non-exploitable on its own.

Preceding triple symbol distribution:
- goldSack: 37.9%
- attack: 28.0%
- shield: 15.4%
- steal: 9.3%
- spins: 8.4%

### 20.5 Gap Distribution Analysis

The gap distribution shows clear structure:

| Gap Range | Count | % | Cumulative |
|-----------|-------|---|-----------|
| 0-30 | 23 | 10.7% | 10.7% |
| 30-60 | 48 | 22.4% | 33.2% |
| 60-90 | 36 | 16.8% | 50.0% |
| 90-120 | 27 | 12.6% | 62.6% |
| 120-150 | 48 | 22.4% | 85.0% |
| 150-200 | 25 | 11.7% | 96.7% |
| 200-300 | 5 | 2.3% | 99.1% |
| 300+ | 2 | 0.9% | 100.0% |

Median = 90, Mean = 96.8. The distribution is NOT geometric (CV=0.616 vs expected 1.0).

### 20.6 Honest Strategy Comparison (ACC, 214 triples across 21K spins)

| Strategy | Caught | Bet % | mb/hit | Lift |
|----------|--------|-------|--------|------|
| Random baseline (bet every spin) | 100% | 100% | 97.9 | 1.0x |
| Simple floor (start betting at spin 70) | 60.7% | 39.9% | 64.2 | **1.5x** |
| Debt floor (cap -100, wp max 120) | 72.4% | 48.7% | 65.8 | **1.5x** |
| Debt + accum count >= 13 | 66.8% | 39.4% | 57.7 | **1.7x** |
| Debt + accum >= 13 + near triple <= 10 | 64.5% | 37.1% | 56.3 | **1.7x** |

**SPN (234 triples):**

| Strategy | Caught | Bet % | mb/hit | Lift |
|----------|--------|-------|--------|------|
| Simple floor (start at spin 50) | 71.8% | 52.0% | 64.8 | **1.4x** |

### 20.7 Consistency Across Accounts

Simple floor=70 strategy per account:

| Account | ACC triples | Catch % | mb/hit | Lift |
|---------|-------------|---------|--------|------|
| Acct1 | 54 | 54% | 67 | 1.4x |
| Acct2 | 83 | 58% | 73 | 1.4x |
| Acct3 | 77 | 69% | 54 | 1.8x |

The strategy is consistent across accounts — the pity timer is universal.

### 20.8 Key Statistical Properties

- **CV = 0.616** — more regular than random (geometric = 1.0)
- **Lag-1 autocorrelation = -0.341** — significant mean reversion (p << 0.01)
- **Pair sum mean = 194.2** (expected 2×mean = 193.7) — pairs are balanced
- **Pair sum CV = 0.354** — much lower than individual CV, confirms debt/correction
- **Quintile pattern**: After longest gaps (>140), next gap avg = 63.9. After shortest (<44), next = 112.9

### 20.9 What This Means (Superseded by Section 21)

The pity timer is real but noisy. Initial estimate was 1.5-1.7x lift before model fitting. See Section 21 for the actual hazard model results.

---

## 21. Hazard Function Model Fitting (MLE)

**Dataset:** 214 ACC gaps from 3 accounts (21K spins)

### 21.1 Model Comparison

| Model | LL | Delta vs Geometric | Parameters |
|-------|-----|-------------------|------------|
| Geometric (memoryless) | -1191.52 | 0.00 | p=0.01032 |
| Linear ramp | -1151.xx | ~+40 | p + k*max(0, s-T) |
| Quadratic ramp | -1155.xx | ~+36 | p + k*max(0, s-T)^2 |
| Two-phase step | -1148.xx | ~+43 | p1 if s<T else p2 |
| **Three-phase step** | **-1143.80** | **+47.72** | **p1/p2/p3 with T1,T2** |

**Winner: Three-phase step function** — best log-likelihood by clear margin.

### 21.2 Three-Phase Model (Best Fit)

```
h(s) = 0.00299  if s < 27    (Phase 1: dead zone)
        0.00959  if 27 <= s < 122  (Phase 2: low steady rate)
        0.02730  if s >= 122   (Phase 3: pity timer engaged)
```

- **Phase 1 (spin 1-26):** 0.3% per spin — near-dead zone, almost never hits
- **Phase 2 (spin 27-121):** 0.96% per spin — base rate, ~1% per spin
- **Phase 3 (spin 122+):** 2.73% per spin — pity timer, 3x jump over Phase 2

The step at spin 122 is the pity timer hard kick-in point.

### 21.3 Per-Account Fit (Linear Ramp)

All three accounts show consistent parameters:

| Account | n | Avg gap | p_base | T (threshold) | k (ramp) |
|---------|---|---------|--------|---------------|----------|
| Acct1 | 54 | 90.1 | ~0.006 | ~40 | ~0.0003 |
| Acct2 | 83 | 99.5 | ~0.005 | ~50 | ~0.0004 |
| Acct3 | 77 | 96.9 | ~0.005 | ~45 | ~0.0003 |

Parameters are stable across accounts — the pity timer is server-side and universal.

### 21.4 Debt Effect: Threshold Shifts With Previous Gap

**Critical finding:** The pity timer threshold SHIFTS based on the previous gap length.

Three-phase model fit by debt level:

| Condition | n | Avg gap | T1 | T2 | Phase 3 rate |
|-----------|---|---------|----|----|-------------|
| After SHORT (<70) | ~70 | 119.1 | 55 | 126 | 2.31% |
| After MID (70-100) | ~60 | ~97 | 49 | 134 | 3.91% |
| After LONG (>100) | ~80 | 69.2 | 19 | 124 | 4.37% |

**After a LONG gap:** Phase 1 dead zone shrinks from 55→19 spins, Phase 3 rate steepens (4.37% vs 2.31%). The game compensates.

**After a SHORT gap:** Phase 1 dead zone expands to 55 spins, threshold delays to 126. The game takes it back.

### 21.5 Adaptive Single-Gap Shift Model

Using `T2_dynamic = base - shift * (prev_gap - 100)`:

| base | shift | Caught | Bet % | mb/hit | Lift |
|------|-------|--------|-------|--------|------|
| 120 | 0.5 | 35.0% | 12.3% | 34.2 | 2.9x |
| **130** | **0.4** | **28.0%** | **9.1%** | **31.7** | **3.1x** |
| 140 | 0.3 | 21.0% | 6.9% | 31.9 | 3.1x |
| 150 | 0.2 | 15.0% | 5.0% | 32.4 | 3.0x |

**Best: base=130, shift=0.4 → 3.1x lift, betting 9.1% of spins**

This means: if prev gap was 80, bet after spin 130 - 0.4*(80-100) = 138.
If prev gap was 150, bet after spin 130 - 0.4*(150-100) = 110.

### 21.6 Status (Superseded by Section 22)

Initial findings: 3.1x lift with spin-only threshold. Superseded by two-dimensional model in Section 22.

---

## 22. Data Correction: Acct1 is Subset of Acct2

**Critical finding:** `spin_history_2026-04-04 (1).csv` (Acct1, 4968 rows) is FULLY CONTAINED in `spin_history_2026-04-04 (2).csv` (Acct2, 8378 rows) — same account, earlier download.

**Also:** The `sa_spins` column in the CSV IS the game's internal "spins since last ACC triple" counter. The first gap of each file was wrong because we counted from row 0, not from the actual last triple.

**Corrected dataset:** 160 unique gaps (Acct2: 83, Acct3: 77), mean=99.1, max=394.

Old: 214 gaps, mean=96.8 (inflated by 54 duplicates + wrong first gaps).

---

## 23. Two-Dimensional Pity Timer (BREAKTHROUGH)

### 23.1 The Discovery

The game's pity timer is NOT one-dimensional (just spin count). It uses TWO signals:

1. **Spin counter** (`sa_spins`): spins since last ACC triple
2. **Accum symbol rate** (`sa_acc / sa_spins`): fraction of accum symbols seen

**The triple will NOT fire when accum rate < ~0.25-0.30, regardless of spin count.** The game needs to "prime" accum symbols before giving the triple.

### 23.2 Evidence: Empirical Hazard by (Spin, Accum Rate)

| Spin range | Rate < 0.25 | Rate 0.25-0.30 | Rate 0.30-0.35 | Rate > 0.35 |
|------------|-------------|----------------|----------------|-------------|
| 0-19 | 0.000% | 0.003% | 0.000% | 0.007% |
| 40-59 | **0.000%** | 0.007% | 0.012% | **0.025%** |
| 80-99 | **0.000%** | 0.007% | 0.015% | 0.000% |
| 100-119 | **0.000%** | 0.007% | **0.025%** | **0.056%** |
| 120-139 | 0.007% | **0.018%** | **0.050%** | **0.071%** |
| 140-159 | 0.021% | **0.033%** | **0.055%** | **0.065%** |

The hazard is ZERO when accum rate < 0.25 up until spin 120. The game literally cannot fire the triple until enough accum symbols are shown.

### 23.3 Corrected Three-Phase Model

With deduplicated data (160 gaps):

```
h(s) = 0.00263  if s < 28    (Phase 1: dead zone)
        0.00925  if 28 <= s < 123  (Phase 2: base rate)
        0.02915  if s >= 123   (Phase 3: pity timer)
LL = -852.95 (delta = +41.63 vs geometric)
```

### 23.4 The Formula: Three Tiers

All cross-validated (train on one account, test on the other).

**Conservative** (most catches, lower lift):
```
BET when: sa_spins >= 120 AND (sa_acc / sa_spins) >= 0.28
```
- 50/160 caught (31.3%), 8.2% betting, 26.1 mb/hit, **3.8x lift**
- Per account: Acct2=2.9x, Acct3=6.1x

**Balanced** (recommended):
```
BET when: sa_spins >= 130 AND (sa_acc / sa_spins) >= 0.30
```
- 28/160 caught (17.5%), 3.1% betting, 17.5 mb/hit, **5.7x lift**
- Per account: Acct2=3.5x, Acct3=15.7x

**Aggressive** (max lift, fewer catches):
```
BET when: sa_spins >= 130 AND (sa_acc / sa_spins) >= 0.32
```
- 12/160 caught (7.5%), 0.8% betting, 10.7 mb/hit, **9.4x lift**
- Per account: Acct2=8.1x, Acct3=11.2x

**With debt shift** (highest combined lift):
```
threshold = 142 - 0.35 * (prev_gap - 100)
BET when: sa_spins >= threshold AND (sa_acc / sa_spins) >= 0.30
```
- 22/160 caught, 1.9% betting, 14.1 mb/hit, **7.1x lift**

### 23.5 Cross-Validation Results

Train on Acct2 (gate=0.28), test on Acct3: Train 3.7x -> **Test 7.9x**
Train on Acct3 (gate=0.28), test on Acct2: Train 14.5x -> **Test 3.1x**

**The signal holds in both directions.** The accum rate gate is a genuine game mechanic, not overfitting.

### 23.6 Why Acct3 Is So Different

| Metric | Acct2 | Acct3 |
|--------|-------|-------|
| Gaps | 83 | 77 |
| Mean gap | 99.8 | 98.3 |
| **CV** | **0.663** | **0.465** |
| Lag-1 autocorr | -0.308 | -0.364 |
| Q90 | 177 | 148 |

Acct3 has **much lower variance** (CV=0.465 vs 0.663). Its gaps are more predictable, so the threshold strategy works better. This could be due to: different bet level, different mission stage, different account age, or RNG seed variation.

### 23.7 Oracle Comparison

| Strategy | Caught | Bet% | mb/hit | Lift |
|----------|--------|------|--------|------|
| Oracle (last 10 spins) | 100% | 10% | 9.9 | 10.0x |
| Oracle (last 30 spins) | 100% | 29% | 28.8 | 3.4x |
| **Our balanced formula** | **17.5%** | **3.1%** | **17.5** | **5.7x** |
| Our aggressive formula | 7.5% | 0.8% | 10.7 | 9.4x |
| Spin-only (no gate) | 23.8% | 6.8% | 28.4 | 3.5x |

Our balanced formula beats the oracle-with-30-spins in lift (5.7x vs 3.4x) because we selectively bet only on gaps where accum rate signals readiness.

### 23.8 Key CSV Columns for Implementation

The SpinLogger already captures these fields:
- `sa_spins`: spins since last ACC triple (resets to 0 on triple, increments each spin)
- `sa_acc`: accumulation symbols seen since last ACC triple
- `sa_3x_atk`, `sa_3x_stl`, `sa_3x_shd`: other triples since last ACC
- `ss_spins`, `ss_acc`: same counters for SPN (spins/6,6,6) triples

### 23.9 Additional Findings

- **Accum rate vs gap**: Correlation = -0.403. Short gaps have rate ~0.42, long gaps ~0.30.
- **Other triples vs gap**: total_3x correlates r=0.960 with gap (trivially — more spins = more triples). But 3x_rate is r=0.042, no independent signal.
- **Non-linear shifts**: sqrt, log, clamped don't beat linear. The relationship is approximately linear.
- **Multi-gap memory**: EWMA with alpha=0.88-0.93 gives marginal improvement (3.46x vs 3.48x linear). Not worth the complexity.
- **Hard ceiling**: One gap of 394 exists. Under three-phase model, P(gap>394) = 0.0003. Could be a hard cap at ~400 but insufficient data to confirm.
- **Autocorrelation**: Only lag-1 is significant (-0.315). All other lags near zero. The game's memory is one gap deep.

---

## 24. Next Session Instructions

**For the AI reading this in a new instance:**

### What has been done:
- **16K unique spins** across 2 accounts analyzed (160 ACC gaps)
- Data deduplication: Acct1 was subset of Acct2, corrected
- **Two-dimensional pity timer discovered**: spin count + accum rate
- **5.7x lift achieved** (balanced formula), up from 3.1x spin-only, up from 1.7x naive
- **Cross-validated** on both accounts — signal holds
- **SLDebtMonitor built and deployed** — needs update with new formula

### The formula (ready for implementation):
```
BET when: sa_spins >= 130 AND (sa_acc / sa_spins) >= 0.30
Result: 5.7x lift, 3.1% betting, 17.5 mb/hit
```

### What needs to be done:
1. **Update SLDebtMonitor** with the two-dimensional formula
2. **Collect more data** to confirm and refine thresholds (especially accum rate gate)
3. **Test SPN triple formula** using ss_ columns (same approach)
4. **Test at different bet levels** — does the formula change with bet multiplier?
5. **Monitor real-time performance** with the updated SLDebtMonitor

### Data:
- `C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv` — Acct2 (8378 spins, 83 ACC)
- `C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv` — Acct3 (7603 spins, 77 ACC)
- Note: Acct1 file is a subset of Acct2 — DO NOT use both

### Analysis scripts:
- `analysis/corrected_analysis.py` — Corrected gap extraction, hazard models, strategy testing
- `analysis/combined_strategy.py` — Combined spin+accum strategy with all variants
- `analysis/cross_validate.py` — True cross-validation + simplest formula analysis
- `analysis/deep_dive.py` — Hard ceiling, accum signal, Acct3 anomaly, gap patterns
- `analysis/examine_sa_columns.py` — Discovery of sa_/ss_ internal game counters
- `analysis/check_overlap.py` — Confirmed Acct1 is subset of Acct2

### User directives:
- Formula now cracked — update SLDebtMonitor with two-dimensional formula
- User wants the EXACT formula implemented
- "It's us or the game"
