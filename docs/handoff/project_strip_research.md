---
name: Strip Research Status
description: 11K spin nuclear analysis complete — 110% hazard threshold implemented, future research directions identified
type: project
---

## Current State (2026-04-06) — ANALYSIS CONCLUDED, TOOL UPDATED

### Architecture (proven with 11,418 spins + HAR API analysis)
- **33 fixed outcome tuples** — identical between accounts, weighted random table
- **NOT a strip** — normalized MI = 0.03-0.04 (a strip would need >0.1)
- **Server-side RNG** — HAR analysis confirms no hidden fields (no seed, no strip index, no counter)
- **Village-based probability tables** — `segment_slot_probabilities_villages_200_269` in API config
- **A/B testing** — `segment_core_slot_prob_nu_29_06_var_a` flag seen in config
- Running median targets: Acc1=108 (mission 66/70), Acc2=74 (mission 37)

### What Was Tested (25+ approaches, 3 parallel research agents)
- PRNG state recovery (LCG, xorshift) — dead
- Modular arithmetic on all counters — debunked (small counter artifact)
- Timestamp correlation — dead (no time-based seed)
- N-gram prediction (2-5 grams) — all overfit, zero cross-validation
- Bit pattern / XOR analysis — tautological artifacts only
- ACC symbol counter — r=0.965 with gap length, just a proxy
- Strip reconstruction (greedy adjacency) — no structure found
- Multiple strip table detection — outcome frequency shifts don't cross-validate
- Event bars (slot_on_, ec36d075, etc.) — just event progress, no RNG state
- Session counters (ss_*) — reset on (6,6,6), no ACC prediction
- sa_3x_sum as secondary signal — correlated with sa_spins, partially redundant
- Quiet zone trigger — worse than pure threshold (60+ spins/hit)
- Capped retrigger — 33.6 spins/hit but lower catch rate
- Patent research — US 8,500,542, 9,536,377 confirm debt correction in social casino games

### Confirmed Signal: Hazard Function
- P(ACC) rises sharply past median: 3.8% at 121-150 spins, 6.7% at 151+ (Acc1)
- Cross-validates on both accounts
- `sa_spins > 130` + recent triple = 5-7x lift (cross-validated)
- Lag-1 autocorrelation: -0.337 (Acc1), -0.378 (Acc2)

### Implemented Strategy: 110% Threshold + Oneshot Gate
- WAIT: saSpins < 70% of median (green)
- ALERT: saSpins 70-110% of median (yellow)
- WATCH: saSpins >= 110%, waiting for non-ACC triple trigger
- BET NOW: triggered, stays until ACC triple hits
- Simulated: Acc1 = 29/61 caught (48%), 38.9 spins/hit | Acc2 = 24/49 caught (49%), 63.5 spins/hit
- vs OLD quiet zone: Acc1 = 18/61 caught (30%), 95.3 spins/hit — **2.4x improvement**

### Future Research Directions (to reduce MB/hit further)
1. **Reel animation analysis** — client knows outcome before animating, visual tells might exist. Record screen and analyze animation patterns before ACC triple vs before other outcomes
2. **Fresh GAE event data** — collect 5K spins from the VERY START of a new GAE event on both accounts. Test if early-event gaps are tighter or more predictable
3. **Low mission account** — the game uses easier probability tables at lower village levels. A fresh low-mission account might have more predictable gaps
4. **Cross-event comparison** — collect data across different GAE events. The `segment_*` flags suggest tables change per event
5. **Bet level effect** — preliminary data shows shorter gaps at high bet (mean 78 vs 102 for Acc1). Collect more data at high bet to confirm
6. **More data volume** — 11K spins gives 118 ACC gaps. 50K+ spins would let us find weaker signals that currently drown in noise
7. **Client-side intercept** — the Unity client receives outcome before animating. Hooking the animation system could reveal if there are visual pre-signals

### Key Files
- Nuclear analysis: analysis/nuclear_analysis.py, nuclear_phase2.py, nuclear_phase3.py
- Strategy simulations: analysis/simulate_strategies.py, optimize_cap.py, final_strategy_sim.py
- ACC symbol test: analysis/acc_symbol_counter.py
- HAR analysis: har_analysis_report.py
- Tool: SLDebtTracker.m (110% threshold + oneshot gate), SLDebtMonitor.m, SLMenuOverlay.m
- Account 1: C:\Users\Islam\Downloads\Account 1 spin_history_2026-04-05.csv (6,450 spins)
- Account 2: C:\Users\Islam\Downloads\Account 2 spin_history_2026-04-04.csv (4,968 spins)
