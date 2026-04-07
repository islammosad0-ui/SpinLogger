# Ladder Strategy Backtest — Design

**Date:** 2026-04-08
**Topic:** Config-driven backtest of `sa_spins`-based bet-ladder strategies against the 28k+ spin dataset, with per-account head-to-head comparison vs actual historical play.

## Purpose

Test bet-ladder strategies (found online) that tier the bet multiplier based on spins since the last accumulation triple. For each strategy, measure how efficiently the ladder captures acc triples at its top bet tier, and compare that to how efficiently the player actually captured acc triples at the same bet threshold in their real play.

## Goals / Non-goals

**Goals**
- Configurable ladder definitions (tiers = list of `(min_spins, max_spins, bet_multiplier)`)
- Simulate each ladder over all spins in `gaps.pkl`, per account separately
- Measure capture rate, efficiency, and waste ratio at the ladder's top tier
- Compare to the same metrics computed on actual historical `bet_multiplier` data, using the same top-tier threshold for apples-to-apples
- Human-readable report written to `analysis/nuclear/22_ladder_backtest.txt`

**Non-goals**
- Betting strategies that use counters other than `sa_spins` (out of scope for v1)
- ROI / coin-flow simulation (user explicitly prefers capture efficiency as the metric)
- Cross-account pooling (user wants per-account comparisons)
- CLI arg parsing — strategies are defined inline in the script
- Per-tier breakdown (only top tier matters for v1)

## Inputs

- `analysis/nuclear/gaps.pkl` (produced by `01_loader.py`)
  - Contains `all_data[account]['spins']` — list of enriched spin records
  - Each spin has: `triple`, `bet_multiplier`, `session_idx`, `session_file`, and all `sa_*` / `ss_*` counters
- `STRATEGIES` dict defined inline at top of the script

## Architecture

Single standalone Python script: `analysis/nuclear/22_ladder_backtest.py`

Follows the existing nuclear-analysis convention (see `15_causal_sweep.py`, `16_causal_ensemble.py`, `20_reverse_cap.py`, `21_layered_ensemble.py`):
- Loads `gaps.pkl`
- Does all computation in memory
- Writes a `.txt` report alongside the script
- Also prints to stdout while running

No external dependencies beyond what the loader already uses (`pickle`, standard library).

## Components

### 1. Strategy config

Defined as a module-level dict at the top of the script. Each strategy has:

```python
STRATEGIES = {
    'reddit_basic_3_50_100': {
        'source': 'https://reddit.com/...',        # optional, for documentation
        'notes': 'classic 3-tier ladder',          # optional
        'tiers': [
            (1,   50,  3),     # spins 1–50:   bet 3x
            (51,  90,  50),    # spins 51–90:  bet 50x
            (91,  999, 100),   # spins 91+:    bet 100x  (top tier)
        ],
    },
    # more strategies pasted here as needed
}
```

Tier semantics:
- Each tier is `(min_spins_inclusive, max_spins_inclusive, bet_multiplier)`
- `local_sa_spins` in `[min, max]` → bet at `bet_multiplier`
- Tiers must be contiguous and non-overlapping; this is **validated at startup** and the script hard-errors with a clear message if violated
- The **top tier** is the tier with the highest `bet_multiplier`. This multiplier is the "high bet" threshold used in metrics.

### 2. Session-local `sa_spins` counter

The loader's `sa_spins` field carries pre-CSV history at session start, which violates the user's requirement that each new CSV be treated as a fresh acc event. The backtest computes its own counter:

```
For each account:
  For each session_idx in account:
    counter = 1
    For each spin in session (in order):
      local_sa_spins[spin] = counter
      bet[spin]            = ladder_lookup(counter, strategy)
      if spin.triple == 'accumulation':
          counter = 1     # reset so NEXT spin starts at 1
      else:
          counter += 1
```

Session boundary = hard reset regardless of whether the last spin of the previous session was a triple. First spin of every session has `local_sa_spins = 1`.

Sessions are identified by the `session_idx` field already tagged by the loader.

### 3. Metrics engine

For a given account × strategy:

**Core definitions**
- `top_tier_bet` = max `bet_multiplier` across the strategy's tiers
- A spin is "at high bet" iff its assigned bet ≥ `top_tier_bet`
- "Captured triple" = acc triple on a high-bet spin
- "Wasted high bet" = high-bet spin without an acc triple

**Computed fields**

| Metric | Formula |
|---|---|
| `total_acc_triples` | `sum(1 for s in spins if s.triple == 'accumulation')` |
| `top_tier_spins` | `sum(1 for s in spins if bet[s] >= top_tier_bet)` |
| `captured` | `sum(1 for s in spins if bet[s] >= top_tier_bet and s.triple == 'accumulation')` |
| `wasted` | `top_tier_spins - captured` |
| `capture_rate` | `captured / total_acc_triples` (0 if denom 0) |
| `efficiency` | `captured / top_tier_spins` (0 if denom 0) |
| `waste_ratio` | `wasted / captured` (`inf` if `captured == 0`, reported as `"—"`) |

Each metric is computed **twice**:
1. **STRATEGY run** — uses `bet[spin]` from the ladder
2. **ACTUAL run** — uses the spin's real `bet_multiplier` from the CSV, with the **same** `top_tier_bet` threshold

### 4. Report writer

Output path: `analysis/nuclear/22_ladder_backtest.txt` (overwritten on each run). Also printed to stdout.

**Format:**

```
================================================================
LADDER BACKTEST: <strategy_name>
  source: <source>
  notes:  <notes>
  tiers:  (1-50: 3x) (51-90: 50x) (91+: 100x)   top_tier=100x
================================================================

ISLAM  (<N> spins, <T> acc triples)
  STRATEGY:  captured  <c>/<T> (<pct>%)   eff <c>/<ts> (<pct>%)   waste <w>/<c>
  ACTUAL:    captured  <c>/<T> (<pct>%)   eff <c>/<ts> (<pct>%)   waste <w>/<c>
  Δ:         <sign><pp> capture    <sign><pp> eff    <sign> waste
  VERDICT:   <one-line summary: strategy wins / loses / neutral>

NICK   (...)
  ...

AHMED  (...)
  ...

(repeats for each strategy in STRATEGIES dict)

================================================================
SUMMARY TABLE
================================================================
Strategy                          Islam Δcap   Nick Δcap   Ahmed Δcap
reddit_basic_3_50_100             +14.5pp      +10.1pp     +8.2pp
aggressive_early                  ...
```

**Verdict rule** (simple, deterministic). `Δcapture_rate` is in percentage points; `Δwaste_ratio` is relative change vs actual (`(strategy_waste − actual_waste) / actual_waste`, or `0` if `actual_waste == 0`):
- `Δcapture_rate >= +5pp` AND `Δwaste_ratio <= 0` → "strategy wins"
- `Δcapture_rate <= -5pp` OR `Δwaste_ratio >= +0.5` (50% worse) → "strategy loses"
- otherwise → "roughly neutral"

## Data flow

```
gaps.pkl
   │
   ▼
load_data() ──► all_data[account]['spins']
   │
   ▼
for strategy in STRATEGIES:
    validate_tiers(strategy)
    for account in ['Islam', 'Nick', 'Ahmed']:
        spins = all_data[account]['spins']
        bet_strat  = assign_strategy_bets(spins, strategy)   # uses local sa_spins
        metrics_s  = compute_metrics(spins, bet_strat, top_tier)
        metrics_a  = compute_metrics(spins,
                                     actual_bets=[s['bet_multiplier'] for s in spins],
                                     top_tier=top_tier)
        report.add(strategy, account, metrics_s, metrics_a)
report.write('22_ladder_backtest.txt')
```

## Error handling

- **Invalid tier definition** (overlap, gap, non-contiguous, empty list) → hard-error at startup with the offending strategy name and tier details
- **Missing `gaps.pkl`** → hard-error with instruction to run `01_loader.py` first
- **Zero acc triples in an account** → skip with a warning line in the report; don't crash
- **Zero top-tier spins in strategy or actual run** → `capture_rate = 0`, `efficiency = 0`, `waste_ratio = "—"`; not an error

## Testing / verification

This is a one-off analysis script in the `analysis/nuclear/` tree, matching the pattern of the other scripts in that directory (none of which have formal tests). Verification strategy:

1. **Sanity check 1** — a trivial strategy with tiers `(1, 999, 1)` (flat 1x bet) should produce `top_tier_spins == all spins`, `captured == total_acc_triples`, `capture_rate == 100%`
2. **Sanity check 2** — a strategy with top tier never reached in the data (e.g. `(1, 999, 1)` + `(1000, 9999, 100)`) should produce `top_tier_spins == 0`, `captured == 0`, `capture_rate == 0`
3. **Cross-check with loader** — total spin counts and total acc triples per account should match the numbers in `01_inventory.txt`
4. **Spot-check one trajectory** — pick a specific acc gap in Islam's data, walk through it by hand, confirm `local_sa_spins` and `bet` at each spin match expectation

These checks are run manually after implementation, not automated.

## Open questions

None — all resolved during brainstorming. Documented decisions:

- **Strategy config location**: inline dict in script (Approach A), not external YAML
- **Counter basis**: `sa_spins`, session-local (fresh start per CSV)
- **High bet definition**: strategy's top tier `bet_multiplier`, same threshold applied to actual data
- **Account handling**: 3 accounts run separately, per-account comparison
- **Metric**: capture efficiency (capture rate + waste), not ROI
- **Per-tier breakdown**: out of scope for v1
