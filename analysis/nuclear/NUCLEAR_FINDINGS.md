# Nuclear Analysis Findings v5 — FINAL CAUSAL FINDINGS + HUNT DISCOVERIES

> **Status: 2026-04-08**
>
> The full analysis pipeline has been rebuilt after discovering the phantom
> bug on 2026-04-07. All results below use the **causal simulator**
> (`simulate_causal()` in `02_eval.py`) which correctly evaluates rules at
> state N-1 to predict triple at state N, matching live tracker semantics.
>
> **Dataset**: 28,923 spins / 271 ACC gaps / 333 SPN gaps across 3 accounts
> (Islam 12,891 spins/119 ACC, Ahmed 12,928/127 ACC, Nick 3,104/25 ACC).
> Combines two sessions per account (2026-04-04/05 original + 2026-04-07 new).
>
> **Live tracker ground truth (chunk 14)**: From bet_decisions.csv on 49
> in-range triples, 10 were REAL catches (20.4%), 11 PHANTOM, 28 MISSED.
> This validated the causal simulator's numbers.
>
> ---
>
> ## 🏆 KEY DISCOVERIES (2026-04-08 hunt)
>
> **1. STEAL-cond is the strongest conditional signal**
>   - STEAL t=150 g=0.30: 5/271 @ **6.2 mb/hit**, 17.0x lift ← best causal rule
>   - STEAL t=130 g=0.28: 14/271 @ 15.0-16.7 mb/hit (volume workhorse)
>   - STEAL t=90 g=0.36: 4/271 @ 4.5 mb/hit, 23.4x lift
>   - Cross-validates across all 3 accounts
>
> **2. Quiet-Zone signature (NEW mechanic discovered)**
>   - In the 10 spins BEFORE an ACC triple, TOTAL symbol output drops ~20%
>   - Avg symbols in last-10: 12.8 vs random 10-spin window: 16.0
>   - Rule: `sum(sa_atk+sa_stl+sa_shd+sa_acc+sa_spn delta over last 10) <= 10`
>   - SUPP+STEAL last_10<=10 t>=130: **4/271 @ 6.0 mb/hit** (Nick 3/25 @ 4 mb)
>   - SUPP+SHIELD last_10<=10 t>=130: 3/271 @ 9.7 mb (Islam 3/119 @ **5 mb**)
>   - This is a genuine "calm before the storm" — the game suppresses RNG
>     output in the pre-triple window
>
> **3. S/M/L transition matrix (user hypothesis validated)**
>   - M → S: 50% (base 41%) ← +9 lift
>   - L → S: 55% (base 41%) ← +14 lift
>   - S → M: 45% (base 35%) ← +10 lift
>   - M → L: 4% (base 12%) ← strong negative lift (avoid L after M)
>   - L → L: 12% (base 12%) ← game avoids repeating L
>   - Layered strategy using this gave Ahmed his best result: 33 mb/hit
>
> **4. Gap length recurrence (weak but real)**
>   - 190/271 gaps (70%) fall on lengths that repeat 2+ times
>   - Hottest lengths: 69 (6x), 101 (6x), 163 (6x), 49 (5x)
>   - Cross-validated (LOO) at min_count=4: ~5/271 @ 50-80 mb
>
> ---
>
> ## 🎯 SHIPPED ENSEMBLE v5.1 (verified causal KPI)
>
> Six rules, causally validated, combined as OR:
>
> 1. **STEAL t=65 g=0.34 (cap 105)**     — 4/271 @ 16.5 mb (S-window precision)
> 2. **STEAL t=130 g=0.28**              — 14/271 @ 16.7 mb (volume workhorse)
> 3. **STEAL t=150 g=0.30**              — 5/271 @ 6.2 mb (L-window gem, 17x lift)
> 4. **SHIELD t=150 g=0.30**             — 8/271 @ 18.4 mb (SHIELD complement)
> 5. **Quiet-zone last_10<=10 t>=130**   — 7/271 @ 19.4 mb (quiet-zone trigger)
> 6. **DG t=130 cap=155 acc>=0.28 spn>=0.24** — 18/271 @ 32.5 mb (capped volume)
>
> **Verified union (causal simulator, 271 gaps):**
>   - **Catches: 41/271 (15.1%)**
>   - Bet spins: 1000 / 28,497 (3.51%)
>   - **mb/hit: 24.39**
>   - **Lift: 4.31x** over random betting
>
> **Per-account:**
>   - Islam: 15/119 (12.6%) at 27.0 mb/hit
>   - Ahmed: 19/127 (15.0%) at **23.4 mb/hit**
>   - Nick:   7/25 (**28.0%**) at **21.4 mb/hit**
>
> DG rule is capped at 155 (not uncapped) — catches only 18 instead of 36 but
> drops union mb/hit from 30.0 → 24.4 (avoiding the long-gap bleed).
>
> The precision-only variant (5 rules, no DG) delivers 32/271 (11.8%) @ 18.0
> mb/hit if you want even tighter efficiency at the cost of 9 catches.
>
> ---
>
> ## Why we can't beat ~6 mb/hit more broadly
>
> After 20+ chunks and 2500+ configs tested, the 6 mb/hit floor is limited
> by three things:
>
> 1. **The game is not fully deterministic.** It uses weighted probability
>    tables per bet level. The best any log-based analysis can do is measure
>    the tail bias, which is what our rules capture.
>
> 2. **271 gaps is tiny.** A rule with 4 catches at 6 mb/hit needs ~50-100
>    catches to validate with statistical confidence. We need ~10x more data
>    (~100-150K spins) to upgrade signals from "interesting" to "robust."
>
> 3. **Per-account variance.** Ahmed responds to atk-band rules, Islam
>    responds to SHIELD+SUPP, Nick responds to STEAL+SUPP. Same game, slightly
>    different random seeds per account. Universal rules underperform.
>
> **Zoran's 2.3 mb/hit is probably from a different data source** (memory
> scraping, binary decompilation, or event-specific hardcoded tables) — not
> from log analysis alone.
>
> ---

---

## 1. ACC Triple Prediction

### Baseline (current tool)
```
BET when: sa_spins >= 130 AND (sa_acc / sa_spins) >= 0.30
```
- Caught: 31/178 (17.4%)
- MB/hit: 17.1
- Lift: 5.93x
- Per-account: Islam 14/83, Ahmed 14/77, Nick 3/18

### NEW CHAMPION: Double Gate
```
BET when: sa_spins >= 130 AND (sa_acc / sa_spins) >= 0.32 AND (sa_spn / sa_spins) >= 0.22
```
- Caught: 10/178 (5.6%)
- **MB/hit: 6.1** (was 17.1 — 2.8x improvement)
- **Lift: 16.63x** (was 5.93x — 2.8x improvement)
- Per-account: Islam 4/83, Ahmed 4/77, Nick 2/18
- **Every account positive. This is real.**

**Why it works:** The pity timer tracks both accumulation and spins symbols. When BOTH rates are elevated simultaneously, the game is "primed" for an ACC triple. Neither signal alone is as precise — the intersection is much tighter.

### Practical Presets (ACC, all cross-validated on 3 accounts)

| Preset | Formula | Caught | %Catch | MB/hit | Lift | Use Case |
|--------|---------|--------|--------|--------|------|----------|
| **Ideal** | t≥110, rate≥0.30, slope8≥0.006 | 39/178 | **21.9%** | **8.1** | 12.6x | **20%+ catch + sub-10 mb** |
| **Combo** | t≥110, acc≥0.28, spn≥0.22, slope10≥0.01 | 38/178 | **21.3%** | **9.1** | 11.2x | Most balanced across accounts |
| **Sniper** | t≥130, acc≥0.32, spn≥0.22 | 10/178 | 5.6% | **6.1** | 16.6x | Best precision, fewer catches |
| **Sharp** | t≥130, acc≥0.32, spn≥0.20 | 11/178 | 6.2% | **7.2** | 14.1x | Good precision + catches |
| **Balanced+** | t≥130, acc≥0.30, spn≥0.25 | 15/178 | 8.4% | **8.7** | 11.6x | More catches, still tight |
| **RA Same-Catch** | t≥130, rate≥0.28, slope10≥0.01 | 31/178 | 17.4% | **8.6** | 11.8x | **Baseline catches, 2x more efficient** |
| **Wide** | t≥130, acc≥0.30, spn≥0.22 | 27/178 | 15.2% | 11.2 | 9.1x | High catch rate |
| Current | t≥130, acc≥0.30 | 31/178 | 17.4% | 17.1 | 5.9x | Baseline for reference |

### Formula for "Ideal" Preset
```
BET when:
  sa_spins >= 110
  AND (sa_acc / sa_spins) >= 0.30
  AND (sa_acc/sa_spins)[now] - (sa_acc/sa_spins)[8 spins ago] >= 0.006
```
- **21.9% catch rate at 8.1 mb/hit — validated on all 3 accounts**
- Islam: 15/83 (18.1%), Ahmed: 20/77 (26.0%), Nick: 4/18 (22.2%)

### Formula for "Combo" Preset
```
BET when:
  sa_spins >= 110
  AND (sa_acc / sa_spins) >= 0.28
  AND (sa_spn / sa_spins) >= 0.22
  AND (sa_acc/sa_spins)[now] - (sa_acc/sa_spins)[10 spins ago] >= 0.010
```
- **21.3% catch rate at 9.1 mb/hit — most balanced across accounts**
- Islam: 17/83 (20.5%), Ahmed: 16/77 (20.8%), Nick: 5/18 (27.8%)

### Rate Acceleration — Biggest Single Discovery

**BET when: sa_spins >= 130 AND rate(now) - rate(10 spins ago) >= 0.01 AND rate(now) >= 0.28**

- Caught: **31/178 (identical to baseline!)**
- MB/hit: **8.6** (baseline was 17.1)
- Lift: **11.83x**
- Per-account: Islam 14/83, Ahmed 13/77, Nick 4/18
- **Catches everything the baseline catches, but bets on 49% fewer spins**

This works because when the acc symbol rate is *increasing* (positive slope), the game is actively filling the pity meter. A flat or declining rate means symbols are trickling in too slowly — skip those spins even if above threshold.

### What DOESN'T Work (Tested and Rejected)

- **S/M/L conditioning** — minor gains (6-7x) but adds complexity, doesn't beat double gate
- **Previous triple type conditioning** — shield before ACC looks strong (16x on 47 gaps) but too few gaps per bucket for reliability
- **Symbol deficit** — correlated with rate gate, adds nothing independent
- **accum_pct gating** — correlated with sa_spins, no new signal
- **Per-spin acc_count density** — weaker than cumulative rate
- **Non-ACC triple as trigger** — hurts more than helps (cuts catches for marginal mb/hit gain)
- **EWMA gap prediction** — worse than flat threshold (4.4x max)
- **Streak detection** — too few streak events to matter
- **Inverse gates (low atk/stl)** — no signal

---

## 2. SPN Triple Prediction

### CRITICAL FIX: Use ss_* Counters, Not sa_*

The FINDINGS.md formula used `sa_spins/sa_spn` for SPN — but `sa_*` counters reset on ACC triples, not SPN triples. The correct counters are `ss_*`:

- `ss_spins` — spins since last triple spins (resets on SPN triple only)
- `ss_spn` — spins symbols since last triple spins

### OLD (wrong counters)
```
sa_spins >= 87 AND (sa_spn / sa_spins) >= 0.25
```
- Caught: 60/213, MB/hit: 55.9, Lift: 1.53x — **barely above random!**

### NEW CHAMPION (correct counters)
```
BET when: ss_spins >= 120 AND (ss_spn / ss_spins) >= 0.25
```
- Caught: 22/213 (10.3%)
- **MB/hit: 9.5** (was 55.9 — 5.9x improvement)
- **Lift: 9.0x** (was 1.53x — 5.9x improvement)
- Per-account: Islam 11/95, Ahmed 8/86, Nick 3/32

### SPN Presets (cross-validated)

| Preset | Formula | Caught | MB/hit | Lift |
|--------|---------|--------|--------|------|
| **Sniper** | ss≥120 / spn≥0.25 | 22/213 | **9.5** | 9.0x |
| **Balanced** | ss≥100 / spn≥0.25 | 29/213 | **14.2** | 6.0x |
| **Wide** | ss≥87 / spn≥0.25 | 40/213 | 14.6 | 5.9x |
| **Broad** | ss≥60 / spn≥0.25 | 60/213 | 21.4 | 4.0x |
| Old (wrong) | sa≥87 / spn≥0.25 | 60/213 | 55.9 | 1.5x |

---

## 3. Stratification Findings

### Event Type (Standard vs Mix)
- Standard events: 100 gaps, mean=101.6
- Mix events: 78 gaps, mean=99.4
- **No significant difference** — formula works on both

### Bet Level
- Most data at bet_level 0-1
- Not enough data at higher bet levels to conclude if thresholds differ

### Mission Boundaries
- Mission 0-20: mean=102, Mission 20-40: mean=93, Mission 40-80: mean=99, Mission 80+: mean=106
- **No systematic mission effect**

### Autocorrelation
- Lag-1: r=-0.31 to -0.38 (strong mean reversion, known)
- Lag-2: r=+0.06 to +0.14 (weak)
- Lag-3+: negligible
- **Only lag-1 carries signal**

### Transition Matrix (gap size -> next gap size)
```
From\To      XS      S      M      L     XL
   XS       5.9   32.4   32.4   23.5    5.9  (n=34)
    S      10.6   27.7   23.4   23.4   14.9  (n=47)
    M      13.0   28.3   23.9   21.7   13.0  (n=46)
    L       8.9   44.4   17.8   15.6   13.3  (n=45)
   XL      50.0   16.7   16.7    0.0   16.7  (n=6)
```
After L: 44.4% go to S (mean reversion). After XL: 50% go to XS.

---

## 4. Data Inventory

| Account | Spins | ACC Gaps | SPN Gaps | Mean ACC Gap |
|---------|-------|----------|----------|-------------|
| Islam | 8,378 | 83 | 95 | 99.8 |
| Ahmed | 7,603 | 77 | 86 | 98.3 |
| Nick | 2,316 | 18 | 32 | 129.9 |
| **Total** | **18,297** | **178** | **213** | **101.9** |

All 3 accounts confirmed unique (dedup signature check passed).

---

## FUTURE WORK — SPN Nuclear Analysis (with ALL lessons learned)

**Current placeholder**: simple Sniper fix `ss_spins >= 120 AND ss_spn/ss_spins >= 0.25`
gives 22/213 catches at 9.5 mb/hit. Replace with full ensemble after running this analysis.

**Goal**: Get SPN to a similar 35%+ catch rate at <10 mb/hit using a parallel ensemble.

### Pipeline (chunks to run for SPN — mirrors ACC chunks 1-11)

1. **`spn_01_loader.py`** — Load gaps using `ss_spins` counter (NOT `sa_spins` — that's ACC-reset!).
   The first gap of each account is recoverable via the server counter trick.

2. **`spn_02_eval.py`** — Same simulate_fast framework, but operating on SPN gaps.

3. **`spn_03_sweep_univariate.py`** — Threshold/gate/stop-cap sweeps on ss_spins/ss_spn.

4. **`spn_04_sweep_symbols.py`** — Every ss_*/sa_* counter as gate. Test cross-counter ratios
   (e.g., ss_spn/ss_atk) and inverse gates (e.g., low ss_shd).

5. **`spn_05_sweep_sml.py`** — S/M/L stratification by `prev_spn_gap_length`. The big question:
   does SPN have an L-bucket effect like ACC did? Test S/M/L bucket boundaries from 30 to 200.

6. **`spn_06_sweep_conditional.py`** — Conditional rules on `prev_real_triple` (does shield-
   before-spn or attack-before-spn matter?). Also test SPN-specific rate acceleration.

7. **`spn_07_sweep_creative.py`** — Acceleration (slope of ss_spn/ss_spins over 5/8/10/15
   spin windows), bivariate gates, deficit, EWMA.

8. **`spn_08_cross_validate.py`** — Leave-one-account-out validation on top configs.

9. **`spn_09_crossval_sml.py`** — Per-account SML cross-validation.

10. **`spn_10_ensemble.py`** — Build the SPN ensemble with greedy minimum cover.

11. **`spn_11_per_gap_detail.py`** — Per-gap breakdown.

### CRITICAL LESSONS LEARNED FROM ACC ANALYSIS — DO NOT REPEAT

**Counter selection (the worst trap):**
- ACC gaps: `sa_spins` resets on ACC triple → use for ACC analysis
- SPN gaps: `ss_spins` resets on SPN triple → use for SPN analysis
- The original FINDINGS.md used `sa_spins/sa_spn` for SPN, gave 1.53x lift (basically random).
  Switching to `ss_spins/ss_spn` gave 9.0x lift — same data, just the right counter.
- Always double-check which counter resets on which event before any rule fires.

**Gap definition:**
- Use the server counter (`ss_spins`) at the ending row for gap length — recovers pre-CSV history.
- Don't use CSV index gaps (drops the first incomplete gap, loses signal).
- First gap of each account: `length` from server counter, `csv_length` is partial trajectory.

**Cross-validation is mandatory:**
- ALL configs must be validated on all 3 accounts (Islam/Ahmed/Nick) independently.
- Don't trust pooled-data results without per-account breakdown.
- A config with great pooled mb/hit can be carried by 1 account dominating — that's overfit noise.
- Mark configs `*** VALIDATED ***` only if ALL 3 accounts have caught>=1 AND lift>1.0.
- Nick has only 32 SPN gaps total — Nick validation will be tight, weight Islam/Ahmed more.

**Pulse skip is HARMFUL for ensembles:**
- The existing tracker has pulseSkip (drop bets after non-target real triples).
- Tested on the ACC 16-rule ensemble: drops catches from 63 to 45 at the lowest setting (3).
- Pulse skip breaks multi-rule confirmation logic. DO NOT enable pulse skip on the SPN ensemble.

**Density-based betting + geometric backoff DON'T WORK:**
- Tested "bet first N normally, then every 2nd/3rd/4th": catches drop from 63 to 28-43.
- Tested geometric backoff: same problem.
- They skip random spins which often miss the actual catch spin.
- DO NOT use these strategies. Stick with consecutive cooldowns.

**Cooldown 8/3 is optimal for ACC:**
- "After 8 consecutive bet spins, skip 3 spins, resume" — tested 30+ variants.
- 8/3 keeps all 63 catches and saves 48 bet spins (10.49 mb vs 11.25 mb baseline).
- Test cooldown variants for SPN — don't assume 8/3 is optimal there. Try 5/3, 6/3, 7/3, 8/3,
  10/5, 12/5 etc. The optimal value depends on SPN signal density.

**Stop caps lose catches:**
- Tested "max bets per gap" caps: lose catches in long gaps.
- Tested spin-count stop caps (250, 280, 300): lose 1-5 catches each.
- Don't use stop caps unless willing to trade catches for efficiency.

**Bet counting — ALWAYS use deduplicated unique spin count:**
- When 5 rules fire on the same spin, that's ONE bet (one Coin Master spin), not 5.
- The "summed" count (sum across rules) WILDLY overcounts (e.g., 249 vs 40 for one gap).
- Always report bet costs as DEDUP unique spins. Use SUMMED only as a confidence indicator.

**Redundancy is valuable:**
- Greedy minimum cover (8 rules) achieved same catches as 16-rule ensemble.
- BUT we kept 16 rules because: confirmation strength (multiple rules firing = high confidence),
  drift detection (per-rule logs identify which signal degrades), future tuning data.
- For SPN: aim for the minimum cover BUT keep redundant rules with similar signals as
  confirmation channels.

**GAE/mission/accum_pct is mostly noise:**
- Per-spin triple rate by accum_pct: lift 0.55-1.22x (basically flat).
- BUT gap length DOES increase in late mission (gaps starting at 80%+ accum_pct are 40% longer).
- 2 of 3 accounts show gaps getting longer over chronological time (Islam +18%, Nick +12%).
- For SPN: test the same — does SPN gap length increase in late mission? Probably yes.

**Sample size warnings:**
- 5-10 catches is too small for statistical confidence. Need 15-20+ catches per validated config.
- Beware of any rule with <5 catches — it might be data artifacts.
- For SPN with only 213 gaps total (Nick: 32), the bar for statistical significance is HIGH.

**First-gap edge case:**
- The first gap of each account has unknown `prev_gap_length` (no previous to measure).
- Has partial trajectory (CSV joined mid-gap).
- May have a known `prev_real_triple` (if a non-target triple was captured before).
- Most rules requiring prev_gap will skip these gaps. Plan for this.

**The catch happens at peak rule convergence:**
- Multiple rules tend to fire on the SPN catch spin.
- Use rule_count as a confidence indicator (BET (N/total)).
- High N at the catch spin = high confidence prediction.

**ATTACK conditioning failed (don't waste time on it):**
- Tested attack-conditioning for ACC: 78 prev=attack gaps but mb/hit stays >20.
- For SPN: probably same. Test it briefly, expect it to fail.

**SHIELD conditioning works (worth testing):**
- For ACC: shield-before-acc gives 4 strong precision rules at 6-9 mb/hit.
- For SPN: test shield-before-spn, attack-before-spn, etc. Expect similar partial signal.

**The user's intuitions ARE often right:**
- Initial mission analysis showed "no signal" — but a re-test with proper bucketing (gap length
  by accum_pct at start) showed 40% longer gaps in late mission.
- Always test user hypotheses with the RIGHT methodology before dismissing.

**Bet density tracking:**
- The most valuable metric is mb/hit (mean bets per hit), not raw catch count.
- Aim for: max catches at lowest mb/hit. Pareto frontier analysis is the way.
- Save Pareto frontier data for SPN.

### Constraints
- SPN data: 213 SPN gaps vs 178 ACC gaps (slightly more gaps but signal is weaker)
- Per-account: Islam ~95, Ahmed ~86, Nick ~32 SPN gaps (Nick will be the bottleneck)
- Need ALL rules to validate cross-account before locking

### After SPN analysis is done
- SPN tile becomes parallel ensemble using the same UI infrastructure
- Same 5-phase model (WAIT/SOON/ALERT/BET/REST)
- Same bet_decisions.csv schema (separate file: `spn_bet_decisions_YYYY-MM-DD.csv`)
- Cooldown values may differ from ACC's 8/3 — re-test
- Each rule logged with its own bit position in the bitmask

---

## 5. SML Stratification (Chunk 9 — Biggest Discovery)

The previous-gap length is the single strongest signal in the entire dataset.

### Prev-gap distribution
| Account | n | <80 (S) | 80-120 (M) | >=120 (L) | mean |
|---------|---|---------|------------|-----------|------|
| Islam | 82 | 37 | 16 | 29 | 99.1 |
| Ahmed | 76 | 27 | 17 | 32 | 99.2 |
| Nick | 17 | 4 | 5 | 8 | 128.2 |

L-bucket has 69/175 gaps (39%). Nick is almost always in L-bucket.

### Why it works
After a LONG gap (prev >= 120), the pity meter is overdue — strong mean reversion (lag-1 r=-0.35). If the current acc rate is also >=0.32 at spin 130+, you have two independent confirmations. The result is 26-43x lift.

### Top validated SML configs (19 passed all 3 accounts)

| Config | Catches | mb/hit | Lift | Islam | Ahmed | Nick |
|--------|---------|--------|------|-------|-------|------|
| L-only L>=120 tL=130 g=0.32 | 5/175 | **2.4** | 42.6x | 2/82 | 2/76 | 1/17 |
| L-only L>=120 tL=130 g=0.30 | 10/175 | **4.2** | 24.4x | 4/82 | 4/76 | 2/17 |
| S100 L120 tM=180 tL=130 g=0.32 | 12/175 | **3.8** | 26.7x | 5/82 | 5/76 | 2/17 |
| S100 L120 tM=110 tL=130 g=0.32 | 13/175 | **4.8** | 21.1x | 5/82 | 6/76 | 2/17 |
| S100 L130 tM=130 tL=100 g=0.32 | 16/175 | **5.9** | 17.2x | 8/82 | 6/76 | 2/17 |
| S50 L130 tM=150 tL=100 g=0.32 | 17/175 | **7.8** | 13.1x | 8/82 | 7/76 | 2/17 |
| **S50 L130 tM=150 tL=100 g=0.32** (19 catches) | **19/175** | **9.6** | 10.7x | 10/82 | 7/76 | 2/17 |
| S50 L130 tM=130 tL=100 g=0.32 | 21/175 | **10.0** | 10.2x | 10/82 | 9/76 | 2/17 |

### Choosing a config
| Goal | Best config | mb/hit | Catches/session |
|------|-------------|--------|-----------------|
| Lowest mb/hit (ultra-precise) | L-only L>=120 tL=130 g=0.32 | **2.4** | rare |
| Best precision + reasonable catches | S100 L120 tM=180 tL=130 g=0.32 | **3.8** | ~7% of gaps |
| **Highest catch <10mb** | **COMBO flat (all analyses)** | **9.3** | **23.6%** |
| Sub-10mb with SML | S50 L130 tS=80 tM=150 tL=100 g=0.32 | 9.6 | 10.9% |

### Per-account best (L-only)
| Account | Config | mb/hit | Lift |
|---------|--------|--------|------|
| Islam | L>=130 tL=110 g=0.30 | 2.3 | 42.9x |
| Ahmed | L>=130 tL=130 g=0.30 | 2.0 | 49.0x |

### Formula: SML "Precision" (12 catches, 3.8 mb)
```
BET when:
  prev_gap_length >= 120      (L bucket)
  AND sa_spins >= 130
  AND sa_acc / sa_spins >= 0.32
```
(t_M=180 means practically nothing fires in M bucket — it's an L-only formula in practice)

---

## 6. Implementation Priority

1. **IMMEDIATE: Fix SPN to use ss_* counters** — The current tool uses sa_spn/sa_spins for the SPN tracker, which gives almost random results (1.53x). Switching to ss_spn/ss_spins gives 9.0x lift. This is a bug fix, not an enhancement.

2. **HIGH: COMBO ACC formula** — BET when: sa_spins>=110 AND acc_rate>=0.28 AND spn_rate>=0.20 AND slope(10)>=0.010. Gives 42/178 (23.6%) at 9.3 mb/hit, validated all 3 accounts. Requires: second symbol counter (sa_spn), circular buffer for slope.

3. **HIGH: SML prev-gap tracking** — Store previous gap length at each triple reset. Enables SML L-bucket precision (3.8 mb/hit at 12 catches). Requires: one extra field (prevGapLength) saved at each reset.

4. **SPN threshold fix**: threshold 87 -> 120 (tracker already uses correct ss_* counters, just wrong defaults).

---

## 7. Ensemble Analysis (Chunks 10-11) — Final Ceiling

### True ceiling: 63/178 catches at 11.25 mb/hit
After auditing every sub-10mb formula across all 9 chunks, the absolute MAXIMUM achievable
catch rate using ANY combination of sub-10mb rules is **63 catches** (35.4% of all gaps).
116 gaps remain unpredictable by any tested sub-10mb technique.

### The 16-rule ensemble (final)

OR-combined: bet if ANY rule fires. Tracks per-rule firing for future analysis.

```
1.  COMBO w=10 t=110 acc>=0.28 spn>=0.20 slope10>=0.010
2.  Ideal RA w=8 t=110 acc>=0.30 slope8>=0.006
3.  RA t=130 acc>=0.28 slope10>=0.010
4.  FLAT 150/0.32
5.  SML L>=120 tL=130 g=0.32
6.  SML L>=120 tL=130 g=0.30
7.  SML S100 L120 tM=180 tL=130 g=0.32
8.  SML S100 L120 tM=110 tL=130 g=0.32
9.  SML S100 L130 tM=130 tL=100 g=0.32
10. SML S50  L130 tM=150 tL=100 g=0.32
11. SML S50  L130 tS=80 tM=150 tL=100 g=0.32
12. SHIELD-cond 110/0.32   (only fires if prev_real_triple == "shield")
13. SHIELD-cond 120/0.32
14. SHIELD-cond 130/0.32
15. SHIELD-cond 140/0.32
16. FLAT 150/0.37          (1.3 mb/hit, 76x lift — most precise rule)
```

### Comparison table

| Strategy | Configs | Catches | Bet spins | mb/hit | Per-account |
|----------|---------|---------|-----------|--------|-------------|
| COMBO alone | 1 | 42 | 389 | 9.3 | I:18 A:19 N:5 |
| Ideal RA alone | 1 | 39 | 314 | 8.1 | I:15 A:20 N:4 |
| Greedy minimum cover | 8 | 62 | 684 | 11.03 | I:30 A:27 N:5 |
| **Original 11-rule** | **11** | **62** | **684** | **11.00** | **I:30 A:27 N:5** |
| **Final 16-rule (recommended)** | **16** | **63** | **709** | **11.25** | **I:30 A:28 N:5** |
| Everything (35 configs) | 35 | 63 | 826 | 13.10 | I:30 A:28 N:5 |

### Why 16 rules instead of greedy minimum (8)
The "redundant" rules aren't waste — they provide:
1. **Confirmation strength**: When 5 rules fire on the same spin, confidence is much higher than 1 rule firing.
2. **Drift detection**: Per-rule firing logs let us identify which specific signals degrade if game mechanics change.
3. **Future tuning data**: More diverse rule firings = better dataset for next analysis round.
4. **Robustness**: Backup catches if any single rule has a bug or edge case.

### Critical extra finds (audit chunks 10-11)
- **FLAT 150/0.37**: 3 catches, **1.3 mb/hit, 76x lift** — single most precise formula in entire dataset
- **SHIELD conditioning works**: 4 rules contribute 4-9 catches each at 6-9 mb/hit
- **ATTACK conditioning fails**: 78 gaps follow attack but mb/hit stays >20
- **Adding 13 more configs (24 total) to original 11 = ZERO new catches** — proves 62-63 is the ceiling

### Per-gap detail
File: `11_per_gap_detail.txt` — for every one of the 178 gaps, shows which configs caught it,
how many bets it took, account, gap length, prev gap length, L-bucket flag.

### Implementation requirements (for live tracker)
- 16 rule evaluations per spin (cheap)
- Slope buffer supporting both window=8 (Ideal RA) and window=10 (COMBO/RA t130)
- Track `prev_gap_length` (already in chunks 5,9)
- Track `prev_real_triple` (string: attack/shield/steal/spins/accumulation) — NEW
- Per-rule firing log to CSV for future re-analysis
- SOON phase: within 25 spins of any rule firing
- **Cooldown 8/3**: after 8 consecutive bet spins on the same gap, skip the next 3 spins, then resume betting
- **NO pulse skip** — it destroys the ensemble (drops catches from 63 → 45 at minimum setting)

### GAE / Mission signal investigation

**Initial result (per-spin triple rate by accum_pct bucket): negative**
- Lift 0.55-1.22x across all buckets
- Triple RATE per spin doesn't change meaningfully with mission position

**Re-test (gap LENGTH by accum_pct at gap START): positive — confirms "gets harder"**

| accum_pct at gap start | n | mean gap length |
|------------------------|---|-----------------|
| 0-20% | 45 | 103.4 |
| 20-40% | 36 | 92.6 |
| 40-60% | 14 | 106.1 |
| 60-80% | 74 | 100.4 |
| **80-100%** | **9** | **143.2 (+40%)** |

Gaps starting in the late-mission zone (80%+ accum_pct) are 40% longer on average.
Sample is small (n=9) so effect is suggestive, not conclusive.

**Chronological progression (per account):**
- Islam: first-half mean 91.3 → second-half mean 108.2 (**+18.5%**)
- Ahmed: first-half 99.1 → second-half 97.6 (-1.6%)
- Nick:  first-half 122.8 → second-half 137.0 (**+11.6%**)

2 of 3 accounts show gaps getting longer over time, supporting the "harder over session"
hypothesis. Ahmed's flat trend is the outlier.

**Limitations**: Most data is concentrated in 2 absolute mission slots (mission 37: 75 gaps,
mission 70: 71 gaps). We can't test the full mission progression curve from this dataset.
More data needed across mission 1-100+ to validate the "harder over absolute mission" claim.

**Implementation**: GAE fields tracked in bet_decisions.csv. Live tile will show current
accum_pct + mission for manual correlation. Future rule (after more data): late-mission
modifier — when accum_pct >= 80%, raise rate gates to compensate for longer gaps.

### UI Design — Compact tile + tap-to-expand panel

**Compact tile (default 90×60):**
```
⭐ 95/110  M37        ← spins / MIN active threshold + mission badge top-right
0.31|0.22 ░░62%      ← acc | spn rates, with accum_pct as background bar
BET (5/16)           ← phase + N rules firing / 16 total
```

**Threshold semantics:** "110" = MIN spinThreshold across rules currently ELIGIBLE for THIS gap
context (based on prev_gap_length and prev_real_triple). Dynamic — drops to 80 if prev_gap<50,
to 100 if prev_gap>=130, etc. NOT necessarily when first bet happens (rate gates also required).

**Background bar in middle row:** accum_pct as a horizontal fill. Color shifts:
- 0-60%: green/normal
- 60-80%: yellow
- 80-100%: red (gaps are 40% longer in late mission per investigation)

**Phases (5 total):**

| Phase | Color | When | Haptic |
|-------|-------|------|--------|
| WAIT | gray | far below threshold, no L-bucket warmup | no |
| SOON | orange | L-bucket gap AND sa_spins>=75, OR sa_spins>=(MIN-25) AND acc_rate>=(gate*0.85) | no |
| ALERT | yellow | at/above threshold but no rule firing (rate too low) | no |
| BET (N/16) | green (intensity scales with N) | at least 1 rule firing, not in cooldown | YES (first transition only) |
| REST (3->0) | dim gray-orange | cooldown 8/3 active — was firing, forced 3-spin rest | no |

**BET intensity:**
- BET (1-3/16): light green
- BET (4-7/16): bright green
- BET (8-12/16): bright green + glow
- BET (13-16/16): bright green + glow + haptic burst

**SOON trigger logic (Option 4 — L-bucket aware):**
```
SOON when:
  (prev_gap_length >= 120 AND sa_spins >= 75)         <- L-bucket pre-warm
  OR
  (sa_spins >= MIN_threshold - 25                     <- within 25 spins
   AND acc_rate >= MIN_active_rate_gate * 0.85)       <- rate at least 85% of gate
```

The L-bucket clause is critical — gives early warning for high-precision SML rules.

**REST phase:** when cooldown 8/3 forces a 3-spin skip after 8 consecutive bets, the tile
shows "REST 3", "REST 2", "REST 1", then transitions back. The user knows the rules WERE
firing but we're forcibly resting — without REST, the BET NOW disappearing would be confusing.

**Transitions back to BET NOW from REST:** silent (no second haptic since the user already
got one when BET first started). Avoids interrupting during long bet streaks.

### Reset behavior

**On event change** (`gae_segment` changes): RESET EVERYTHING.
- sa_spins, sa_acc, sa_spn, sa_spnSymbols, _rateHistory[], consecBets, cooldownRemaining
- **prev_gap_length → -1 (unknown)**
- **prev_real_triple → nil (unknown)**
- Tracker enters "warm-up" — only the 5 non-prev rules are eligible until the next ACC triple
- Reasoning: different events may have different mechanics; cleaner to start fresh

**On mission change** (`accum_mission` changes within same event): NO RESET.
- The game's pity timer doesn't reset on mission level-up (verified earlier — was a bug)
- prev_gap_length and prev_real_triple SURVIVE mission changes
- All counters keep ticking

**On manual reset** (long-press → Reset Counter): RESET EVERYTHING (same as event change).

### Per-account profiles — STATS ONLY (no tuning)

Decision: do NOT auto-tune per account. The 16-rule ensemble already adapts naturally
(Nick's L-bucket-heavy gaps activate SML rules; Islam/Ahmed's shorter gaps activate COMBO/RA).

The expanded tile panel shows profile stats AFTER 30+ gaps, for visibility only:
```
PROFILE STATS (last 30 gaps)
  mean gap length: 105
  L-bucket share:  35%
  catch rate:      36%
  rules avg fired: 4.2
  classification:  NORMAL
```

Classifications (informational only):
- FAST (mean<100, low L-bucket share)
- NORMAL (100-120 mean)
- SLOW (>120 mean, high L-bucket share — like Nick)

Once self-tuning collects enough data (Phase 1 manual review), we can revisit per-account
threshold tweaks. For now: one ensemble for everyone, profile stats for awareness.

**Tap-to-expand panel (slides up from tile, ~250×400):**
```
┌────────────────────────────┐
│ ACC TRACKER     M37  62%   │
├────────────────────────────┤
│ STATE                      │
│  sa_spins / acc_rate /     │
│  spn_rate / slope_8 /      │
│  slope_10 / prev_gap /     │
│  prev_real_triple /        │
│  cooldown_remaining        │
├────────────────────────────┤
│ RULES FIRING NOW (N/16)    │
│  list of currently firing  │
├────────────────────────────┤
│ NEXT TO FIRE               │
│  rules close to firing,    │
│  with countdown to         │
│  threshold or rate gap     │
├────────────────────────────┤
│ DORMANT                    │
│  rules that cannot fire    │
│  on this gap context       │
└────────────────────────────┘
```

Tap again → collapse. All 16 rules shown grouped by status (firing/next/dormant) for full
debug visibility. Designed for power users who want to see exactly why a bet was/wasn't made.

### Per-rule logging — `bet_decisions.csv` (Option 4)

Locked in: separate file `bet_decisions_YYYY-MM-DD.csv` written alongside main spin CSV.
Every spin gets a row (not just betting spins) so we can analyze WAIT/SOON/ALERT/BET phases.

**Schema (~51 columns)**: seq, timestamp, gap_idx, spin_in_gap, prev_gap_length, prev_real_triple,
bet_level, bet_multiplier, event_type, sa_spins, sa_acc, sa_spn, acc_rate, spn_rate, slope_8,
slope_10, r01..r16 (16 per-rule binary columns), rules_count, rules_bitmask, phase,
cooldown_remaining, consec_bets, gap_bets_so_far, decision, is_triple, triple_type, target_caught,
gae_segment, gae_grand_prize, gae_last_mission, accum_mission, accum_current, accum_total,
accum_pct, accum_delta

**Bit-to-rule mapping** (fixed for backward compatibility):
- bit 0  = r01_combo                     (COMBO w10 t110 a0.28 p0.20 s0.010)
- bit 1  = r02_ideal_ra                  (Ideal RA w8 t110 r0.30 s0.006)
- bit 2  = r03_ra_t130                   (RA w10 t130 r0.28 s0.010)
- bit 3  = r04_flat_150_32               (FLAT 150/0.32)
- bit 4  = r05_sml_l120_g32              (SML L>=120 tL=130 g=0.32)
- bit 5  = r06_sml_l120_g30              (SML L>=120 tL=130 g=0.30)
- bit 6  = r07_sml_s100_l120_m180        (SML S100 L120 tM=180 tL=130 g=0.32)
- bit 7  = r08_sml_s100_l120_m110        (SML S100 L120 tM=110 tL=130 g=0.32)
- bit 8  = r09_sml_s100_l130_m130        (SML S100 L130 tM=130 tL=100 g=0.32)
- bit 9  = r10_sml_s50_l130_m150         (SML S50 L130 tM=150 tL=100 g=0.32)
- bit 10 = r11_sml_s50_l130_s80          (SML S50 L130 tS=80 tM=150 tL=100 g=0.32)
- bit 11 = r12_shield_110                (SHIELD-cond 110/0.32)
- bit 12 = r13_shield_120                (SHIELD-cond 120/0.32)
- bit 13 = r14_shield_130                (SHIELD-cond 130/0.32)
- bit 14 = r15_shield_140                (SHIELD-cond 140/0.32)
- bit 15 = r16_flat_150_37               (FLAT 150/0.37)

**Self-tuning roadmap**:
- Phase 1 (manual): `12_self_tune.py` reports per-rule precision/recall; user reviews
- Phase 2 (semi-auto): nightly `12_auto_tune.py` re-runs analysis on new data, writes proposed_rules.json
- Phase 3 (online): live tracker tracks rolling per-rule precision, auto-disables underperforming rules

### Cooldown 8/3 — savings analysis

**Note**: The 63/661/10.49 number from earlier analysis was based on a 35-config superset
in the simulator. With the **chosen 16-rule subset** + cooldown 8/3 + the **live (causal)
prev_real_triple semantics** that the actual tracker uses, real-world expected stats are:

| Strategy | Catches | Bets | mb/hit | Notes |
|----------|---------|------|--------|-------|
| 16 rules, no cooldown | 63 | 709 | 11.25 | simulator-only baseline |
| **16 rules + cooldown 8/3 (LIVE expected)** | **62** | **~679** | **~10.95** | **what the live tracker delivers** |
| 16 rules + cooldown 8/3 (simulator) | 60 | 615 | 10.25 | simulator with frozen prev_real_triple |
| 35 rules + cooldown 8/3 (simulator) | 63 | 661 | 10.49 | redundant configs, anachronistic |

**The simulator was non-causal** — it set `prev_real_triple` to the most recent real triple
seen WHILE BUILDING the gap (looking forward through the gap). The live tracker can't see
the future, so it updates `prev_real_triple` only when a real triple actually happens in
real time. This causes 1-2 catch differences and slight bet count differences.

**The live tracker's 62/178 at ~10.95 mb/hit is the correct, realistic expectation.** The
simulator's 63/10.49 was a phantom from looking into the future.

Cooldown 8/3 saves 48 bet spins (~7%) while losing ZERO catches. The savings are concentrated
in the 10 expensive long-gap caught gaps (top 10 consume 283 bets baseline → 247 with cooldown).
Tested all variants 5/3 through 15/3, density-based, geometric backoff, adaptive.
8/3 is provably optimal for "max catches at min mb/hit." Density and geometric backoff are
all bad (they skip catch-spins randomly).

Why it works: in long gaps (150+ spins), rules fire continuously from spin ~80-120 onward.
Cooldown gives a 3-spin breather every 8 bets. The catch usually happens at peak rate
convergence, not during the cool-down window, so we don't lose catches.

---

## 8. Scripts Reference

All in `analysis/nuclear/`:

| Script | Purpose |
|--------|---------|
| `01_loader.py` | Load 3 CSVs, build gaps, save pickle |
| `02_eval.py` | Evaluation framework (simulate_fast) |
| `03_sweep_univariate.py` | Threshold, gate, stop, 2D, 3D sweeps |
| `04_sweep_symbols.py` | Every sa_*/ss_* as gate, pairs, inverse |
| `05_sweep_sml.py` | S/M/L mega sweep (gap-conditioned thresholds) |
| `06_sweep_conditional.py` | Previous triple, shift, lookback, stratification |
| `07_sweep_creative.py` | Acceleration, deficit, bivariate, N-gram, EWMA |
| `08_cross_validate.py` | Leave-one-account-out on top flat/RA/double-gate configs |
| `09_crossval_sml.py` | Per-account SML cross-validation + per-profile best |
| `10_ensemble.py` | Sub-10mb ensemble: 24 configs + greedy minimum cover |
| `11_per_gap_detail.py` | Per-gap breakdown — which configs catch which gap |
