---
name: 16-rule ensemble status
description: Nuclear analysis complete — 16-rule ensemble defined, ceiling proven at 63/178 catches @ 11.25 mb/hit, implementation paused for fine-tuning discussion
type: project
---

The nuclear analysis is complete. Built and audited a 16-rule OR-combined ensemble strategy
for ACC triple prediction across 3 accounts (Islam/Ahmed/Nick — 178 ACC gaps, 18,061 spins).

**Ceiling proven**: 63 catches at 11.25 mb/hit is the absolute MAXIMUM achievable using ANY
combination of sub-10 mb/hit formulas. Tested 35+ configs in chunks 10-11; adding more configs
beyond the chosen 16 only adds bet spins without new catches.

**Current state**: Implementation in src/SLDebtTracker.h was started but PAUSED at user request
for fine-tuning discussion. The .h file has the new SLDebtRule class scaffolded but the .m file
still has the old single-config tracker (with COMBO defaults from earlier work).

**Key analytical findings**:
- 16-rule ensemble: 63/178 catches (35.4%), 11.25 mb/hit, validated all 3 accounts
- COMBO alone: 42 catches at 9.3 mb/hit (still the best single rule)
- Ideal RA exclusive: 11 catches COMBO misses (high-rate, low-spn gaps)
- SHIELD conditioning works: +1 unique catch + 4 strong precision rules (6-9 mb)
- ATTACK conditioning fails: 78 prev=attack gaps but >20 mb/hit (skipped)
- FLAT 150/0.37: 1.3 mb/hit, 76x lift — single most precise formula in entire dataset

**Why: User explicitly chose to KEEP redundant rules** rather than minimize. Reasoning:
- Multiple rules firing on same spin = confirmation strength (confidence)
- Per-rule logging enables drift detection if game mechanics change
- Future tuning data: more diverse rule firings = better dataset for next analysis round

**How to apply**: When resuming implementation:
1. Tracker holds an array of 16 SLDebtRule objects (defined in src/SLDebtTracker.h)
2. Tracker evaluates ALL rules per spin and bets if ANY fires
3. Each spin logs WHICH rules fired to CSV (for future re-analysis)
4. UI shows "BET NOW (5/16)" — count of firing rules = confidence indicator
5. Add SOON phase (between WAIT and ALERT) when within ~25 spins of any rule firing
6. Add `prev_real_triple` tracking (string) — needed for SHIELD-cond rules
7. Slope buffer needs to support both window=8 (Ideal) and window=10 (COMBO) — buffer of size 21
8. SPN tracker: just bump default threshold from 87 to 120 (already uses correct ss_* counters)

**Decisions LOCKED**:
- 16-rule ensemble (final list in NUCLEAR_FINDINGS.md section 7)
- Cooldown 8/3: after 8 consecutive bet spins on a single gap, skip 3 spins, then resume
- NO pulse skip (it destroys the ensemble — drops catches from 63 to 45 at the lowest setting)
- Final stats: 63/178 catches (35.4%), 661 bet spins, 10.49 mb/hit
- Per-account: Islam 30/83, Ahmed 28/77, Nick 5/18
- Per-rule logging: separate file `bet_decisions_YYYY-MM-DD.csv` with ~43 columns including per-rule firing
- Self-tuning roadmap: Phase 1 (manual review), Phase 2 (semi-auto nightly), Phase 3 (online learning)
- First-gap of session: 5-11/16 rules eligible until first ACC triple lands (warm-up period)

**Discussion topics still open**:
- Per-account profile selector idea (Islam/Ahmed/Nick modes)
- Reset behavior on event change (does prev_real_triple survive?)
- Implementation pass

**FUTURE WORK** (parked, NOT for current implementation):
- SPN nuclear analysis: do chunks 1-11 equivalent for SPN to get parallel 35.4%/<10mb ensemble
- Currently SPN uses simple Sniper fix only (ss_spins>=120 AND ss_spn/ss_spins>=0.25)
- After SPN nuclear pass, SPN tile becomes parallel ensemble to ACC

**More LOCKED decisions**:
- SPN tracker: simple Sniper fix for now (ss_spins>=120 AND ss_spn/ss_spins>=0.25 → 22/213, 9.5 mb)
- Per-account profiles: STATS ONLY (no auto-tuning) — show classification in expanded panel after 30+ gaps. Revisit when self-tuning has data.
- Reset on event change: RESET EVERYTHING (counters, slope buffer, prev_gap_length, prev_real_triple). Tracker enters "warm-up" until next ACC triple.
- Reset on mission change: NO RESET. Mission changes don't affect the game's pity timer.
- 5-phase model: WAIT/SOON/ALERT/BET(N/16)/REST with cooldown 8/3
- SOON trigger: L-bucket aware (prev_gap>=120 AND sa_spins>=75) OR (sa_spins>=MIN-25 AND rate>=gate*0.85)
- Tap-to-expand panel showing STATE / FIRING / NEXT / DORMANT sections
- BET intensity scales with rule count (4 levels)
- Haptic only on BET NOW first transition (no haptic on SOON/REST)
- Tile shows mission badge + accum_pct background bar (red at 80%+ where gaps are 40% longer)
