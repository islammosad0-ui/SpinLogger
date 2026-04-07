---
name: Next Session Brief
description: Instructions for the fresh analysis session — exhaustive investigation of 5K Account 2 data, leave no stone unturned
type: project
---

## Mission: Crack the Prediction Signal

The current quiet zone strategy gives **60.5 MB/hit (1.6x lift)** — Zoran achieves **2.3 MB/hit**. We are 26x worse. Something fundamental is missing.

### Already tested and FAILED (don't re-test)
- **4-gap window sum = constant**: Islam's handwritten method (sum of 4 consecutive gaps = ~400, predict next = 400 - sum(last 3)). Best constant = 396 (Acct 1) / 375 (Acct 2). MAE = 47.5 / 39.1 — NO BETTER than predicting mean. The stable sum is just central limit theorem, not a game constraint.
- **Quiet zone + debt floor (current tool)**: 60.5 MB/hit, 1.6x lift. Quiet zone fires too often (523 BET windows, 4% hit rate).
- **Locked median calibration**: target gets stuck on early data; running median is strictly better.

### What the next instance MUST do

**Go nuclear on the data.** Don't stop at basic stats. Explore EVERY axis:

1. **Strip position mapping**: There are only 32 distinct (r1,r2,r3) tuples. The reels are NOT independent — they're reading from a physical strip. Map the transition probabilities between outcomes. Is there a deterministic or near-deterministic sequence?

2. **Time-domain analysis**: Check timestamps between spins. Does the server use time-based seeding? Is there a pattern in spin timing that correlates with outcomes? Sub-second granularity matters.

3. **Conditional probabilities nobody checked**:
   - P(ACC triple | last N outcomes were exactly X, Y, Z)
   - P(ACC triple | specific non-ACC triple appeared K spins ago)
   - P(ACC triple | coins_won pattern, reward_code pattern)
   - P(ACC triple | bet_multiplier, bet_level)
   - P(ACC triple | shields count, attack count patterns)
   - Which of the 32 tuples tend to precede ACC triples?

4. **Sequence pattern mining**: 
   - N-gram analysis on outcome sequences (bigram, trigram, 4-gram)
   - Are there forbidden sequences? (like L-never-follows-L)
   - Markov chain modeling — what order Markov process fits the data?
   - Run length analysis on specific symbols

5. **The slot2 columns**: slot2_r1, slot2_r2, slot2_r3 exist in the CSV — what are they? Second slot machine? Do they correlate with main reel outcomes?

6. **Event bars / accumulation columns**:
   - event_bars, accum_current, accum_total, accum_delta, accum_pct
   - Does accum_pct predict when the next ACC triple comes?
   - Is there a pattern in accum_delta leading up to triples?

7. **The sa_* and ss_* columns**: 
   - sa_spins, sa_atk, sa_stl, sa_shd, sa_spn, sa_acc, sa_3x_atk, sa_3x_stl, sa_3x_shd
   - ss_spins, ss_atk, ss_stl, ss_shd, ss_spn, ss_acc, ss_3x_atk, ss_3x_stl, ss_3x_shd
   - These are server-side counters. What are they tracking? Do they reset? Do their values predict outcomes?

8. **Autocorrelation**: Are gaps correlated at lag-2, lag-3? The debt model captures lag-1 (-0.6 correlation). What about deeper structure?

9. **Clustering**: Do gaps cluster in regimes? K-means or change-point detection on gap sequences.

10. **Information theory**: Mutual information between each CSV column and "next spin is ACC triple". Which columns carry the most predictive signal?

11. **Zoran gap**: Our best is 60 MB/hit, Zoran is at 2.3. The only explanation is he sees something we don't — either a visual cue (reel position, animation), a count we're not tracking, or a simpler pattern on LOW-list accounts (village 0-999) that doesn't exist on higher missions.

12. **Cross-account comparison**: Compare Account 1 (mission 66/70) vs Account 2 (mission 37) patterns. Different missions may have fundamentally different strip configurations.

### Data locations — USE ALL OF THEM
- **Account 1 (6,450 spins, mission 66/70)**: C:\Users\Islam\Downloads\Account 1 spin_history_2026-04-05.csv
- **Account 2 OLD (1,392 spins, mission 37)**: C:\Users\Islam\Downloads\Account 2spin_history_2026-04-04.csv
- **Account 2 NEW (~5,000 spins)**: Check C:\Users\Islam\Downloads\ for newest Account 2 CSV
- **Videos of Zoran**: C:\Users\Islam\Desktop\Coin Master\videos\video1-11.mp4
- **Full prior analysis**: analysis/STRIP_ANALYSIS.md

**IMPORTANT**: Analyze BOTH Account 1 (6,450 spins) AND Account 2 (5K+ spins). Compare patterns across accounts. Things that hold on BOTH accounts are real signals; things that only appear on one might be mission-specific or noise. Cross-validation between accounts is key to separating real patterns from coincidence.

### Key constraint
Islam doesn't need to catch every triple. Even catching 1 in 3-4 is fine — but it must be PRECISE. The signal must have near-zero false positives (low MB/hit, high lift). Zoran proves this is possible.
