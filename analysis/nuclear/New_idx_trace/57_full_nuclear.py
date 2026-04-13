#!/usr/bin/env python3
"""
57_full_nuclear.py — Exhaustive analysis of 1,107-spin v2 dataset.

Attacks from every angle:
  1. Full 3x3 visible grid reconstruction + all 9 cell features
  2. Zoki's cells: top-left (r1 top), bottom-right (r3 bottom)
  3. Cell-pair interactions (9x9 = 81 pairs)
  4. Transition matrix on idx triplets
  5. Run-length / gap structure
  6. Regime detection (rolling triple rate changepoints)
  7. Rolling window aggregate features
  8. Hex byte-level features (bytes that change per spin)
  9. Mutual information scan (all features x triple/valuable)
  10. Multi-feature GBT with temporal CV
  11. Symbol co-occurrence on the 3x3 grid
  12. Specific Zoki "1-7 spin lookahead" for all features
"""

import json, csv, hashlib, sys
from collections import Counter, defaultdict
from pathlib import Path
import struct, math

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT   = Path(__file__).resolve().parent.parent.parent
CSV_F  = ROOT / "data" / "Ahmed" / "spin_history_Ahmed_enriched_v2.csv"
TRACE  = ROOT / "data" / "Ahmed" / "il2cpp_trace_20260412_045402.jsonl"
OUT    = ROOT / "analysis" / "nuclear" / "output" / "57_full_nuclear_results.txt"

# ── Reel 2 clean strip ────────────────────────────────────────────────────
REEL2_STRIP = {0:'attack', 1:'coin', 2:'shield', 3:'goldSack', 4:'steal',
               5:'coin', 6:'spins', 7:'goldSack', 8:'accumulation'}
VALUABLE_SYMS = {'accumulation', 'spins'}

# ── Load CSV ──────────────────────────────────────────────────────────────
def load_csv():
    rows = []
    with open(CSV_F, newline='') as f:
        for r in csv.DictReader(f):
            r['r1_idx'] = int(r['r1_idx'])
            r['r2_idx'] = int(r['r2_idx'])
            r['r3_idx'] = int(r['r3_idx'])
            r['is_triple'] = r['is_triple'] == 'True'
            r['is_valuable'] = r['is_valuable'] == 'True'
            r['sn'] = int(r['sn'])
            rows.append(r)
    return rows

# ── Load hex windows from trace (settled spins only) ──────────────────────
def load_trace_hex():
    """Load settled-phase snapshots keyed by spin_num."""
    settled = {}
    with open(TRACE) as f:
        for line in f:
            d = json.loads(line)
            sn = d['spin_num']
            # Take the last snapshot per spin (most settled state)
            settled[sn] = d
    return settled

# ── 3x3 Grid reconstruction ──────────────────────────────────────────────
def grid_3x3(r1_idx, r2_idx, r3_idx):
    """Returns 3x3 grid as dict: {(row, col): idx_value}
    row 0=top, 1=center, 2=bottom; col 0=reel1, 1=reel2, 2=reel3
    """
    g = {}
    for col, idx in enumerate([r1_idx, r2_idx, r3_idx]):
        g[(0, col)] = (idx - 1) % 9  # top
        g[(1, col)] = idx             # center
        g[(2, col)] = (idx + 1) % 9  # bottom
    return g

def grid_symbols(g):
    """Convert grid idx to symbols using reel 2 strip (best approx for all reels)."""
    return {k: REEL2_STRIP[v] for k, v in g.items()}

# ── Wilson 95% CI ─────────────────────────────────────────────────────────
def wilson_ci(hits, total):
    if total == 0:
        return 0, 0, 0
    p = hits / total
    z = 1.96
    denom = 1 + z*z/total
    center = (p + z*z/(2*total)) / denom
    spread = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denom
    return p, max(0, center - spread), min(1, center + spread)

# ── Temporal CV (5-fold) ──────────────────────────────────────────────────
def temporal_cv_test(rows, feature_fn, target_fn, n_folds=5):
    """Test if feature_fn predicts target_fn across temporal folds.
    Returns list of (fold_idx, hot_rate, cold_rate, spread, n_hot, n_cold)."""
    N = len(rows)
    fold_size = N // n_folds
    results = []
    for fold in range(n_folds):
        start = fold * fold_size
        end = start + fold_size if fold < n_folds - 1 else N
        fold_rows = rows[start:end]

        hot_hits, hot_n, cold_hits, cold_n = 0, 0, 0, 0
        for r in fold_rows:
            fval = feature_fn(r)
            if fval is None:
                continue
            tval = target_fn(r)
            if fval > 0:
                hot_n += 1
                hot_hits += int(tval)
            elif fval < 0:
                cold_n += 1
                cold_hits += int(tval)

        hot_rate = hot_hits / hot_n if hot_n > 0 else 0
        cold_rate = cold_hits / cold_n if cold_n > 0 else 0
        results.append((fold, hot_rate, cold_rate, hot_rate - cold_rate, hot_n, cold_n))
    return results

# ══════════════════════════════════════════════════════════════════════════
#                          MAIN ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
def main():
    out_lines = []
    def P(s=''):
        out_lines.append(s)
        print(s)

    P("=" * 80)
    P("  57_FULL_NUCLEAR — Exhaustive 1,107-spin analysis")
    P("=" * 80)

    rows = load_csv()
    N = len(rows)
    P(f"\nLoaded {N} spins from enriched CSV")

    n_triple = sum(1 for r in rows if r['is_triple'])
    n_valuable = sum(1 for r in rows if r['is_valuable'])
    P(f"Base rates: triple={n_triple}/{N} ({100*n_triple/N:.1f}%), "
      f"valuable={n_valuable}/{N} ({100*n_valuable/N:.1f}%)")

    # ── 1. Full 3x3 grid: all 9 cells ────────────────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 1: All 9 grid cells -> next-1/3/5/7 triple & valuable")
    P("=" * 80)

    cell_names = {
        (0,0): 'R1_top', (1,0): 'R1_ctr', (2,0): 'R1_bot',
        (0,1): 'R2_top', (1,1): 'R2_ctr', (2,1): 'R2_bot',
        (0,2): 'R3_top', (1,2): 'R3_ctr', (2,2): 'R3_bot',
    }

    # Pre-compute grids
    for r in rows:
        r['grid'] = grid_3x3(r['r1_idx'], r['r2_idx'], r['r3_idx'])

    # Pre-compute lookahead targets
    for lookahead in [1, 3, 5, 7]:
        for i, r in enumerate(rows):
            window = rows[i+1:i+1+lookahead]
            r[f'next{lookahead}_triple'] = any(w['is_triple'] for w in window) if window else None
            r[f'next{lookahead}_valuable'] = any(w['is_valuable'] for w in window) if window else None

    # Test each cell x each idx value x each lookahead
    P(f"\n{'Cell':<10} {'Idx':<5} {'N':>5} | {'next1_T%':>8} {'next3_T%':>8} {'next5_T%':>8} {'next7_T%':>8} | {'next3_V%':>8} {'next7_V%':>8}")
    P("-" * 95)

    significant_cells = []  # (cell, idx, lookahead, rate, base_rate, n, lift)

    for cell_pos in sorted(cell_names.keys()):
        cell_name = cell_names[cell_pos]
        idx_counts = Counter(r['grid'][cell_pos] for r in rows)

        for idx_val in sorted(idx_counts.keys()):
            n_cell = idx_counts[idx_val]
            if n_cell < 30:  # minimum sample
                continue

            matching = [r for r in rows if r['grid'][cell_pos] == idx_val]

            rates = {}
            for la in [1, 3, 5, 7]:
                valid = [r for r in matching if r[f'next{la}_triple'] is not None]
                hits = sum(1 for r in valid if r[f'next{la}_triple'])
                rates[f'next{la}_T'] = hits / len(valid) if valid else 0

                valid_v = [r for r in matching if r[f'next{la}_valuable'] is not None]
                hits_v = sum(1 for r in valid_v if r[f'next{la}_valuable'])
                rates[f'next{la}_V'] = hits_v / len(valid_v) if valid_v else 0

            # Compute base rates for comparison
            for la in [1, 3, 5, 7]:
                valid_all = [r for r in rows if r[f'next{la}_triple'] is not None]
                base_t = sum(1 for r in valid_all if r[f'next{la}_triple']) / len(valid_all)
                lift_t = rates[f'next{la}_T'] - base_t
                if abs(lift_t) > 0.05 and n_cell >= 50:
                    significant_cells.append((cell_name, idx_val, f'next{la}_T', rates[f'next{la}_T'], base_t, n_cell, lift_t))

                valid_all_v = [r for r in rows if r[f'next{la}_valuable'] is not None]
                base_v = sum(1 for r in valid_all_v if r[f'next{la}_valuable']) / len(valid_all_v)
                lift_v = rates[f'next{la}_V'] - base_v
                if abs(lift_v) > 0.03 and n_cell >= 50:
                    significant_cells.append((cell_name, idx_val, f'next{la}_V', rates[f'next{la}_V'], base_v, n_cell, lift_v))

            P(f"{cell_name:<10} {idx_val:<5} {n_cell:>5} | "
              f"{100*rates['next1_T']:>7.1f}% {100*rates['next3_T']:>7.1f}% "
              f"{100*rates['next5_T']:>7.1f}% {100*rates['next7_T']:>7.1f}% | "
              f"{100*rates['next3_V']:>7.1f}% {100*rates['next7_V']:>7.1f}%")

    P(f"\n--- Significant cells (|lift| > 5pp triple or 3pp valuable, n>=50) ---")
    significant_cells.sort(key=lambda x: -abs(x[6]))
    for cell, idx, target, rate, base, n, lift in significant_cells[:30]:
        P(f"  {cell} idx={idx} -> {target}: {100*rate:.1f}% (base {100*base:.1f}%, lift {100*lift:+.1f}pp, n={n})")

    # ── 2. Zoki's cells: top-left, bottom-right ──────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 2: Zoki's specific cells — top-left (R1_top) & bottom-right (R3_bot)")
    P("=" * 80)

    for cell_pos, cell_name in [((0,0), 'R1_top (Zoki top-left)'), ((2,2), 'R3_bot (Zoki bottom-right)')]:
        P(f"\n  {cell_name}:")
        idx_counter = Counter(r['grid'][cell_pos] for r in rows)
        for idx_val in sorted(idx_counter.keys()):
            n_c = idx_counter[idx_val]
            sym = REEL2_STRIP[idx_val]
            matching = [r for r in rows if r['grid'][cell_pos] == idx_val]

            for la in [1, 3, 5, 7]:
                valid = [r for r in matching if r[f'next{la}_triple'] is not None]
                hits_t = sum(1 for r in valid if r[f'next{la}_triple'])
                valid_v = [r for r in matching if r[f'next{la}_valuable'] is not None]
                hits_v = sum(1 for r in valid_v if r[f'next{la}_valuable'])
                all_valid = [r for r in rows if r[f'next{la}_triple'] is not None]
                base_t = sum(1 for r in all_valid if r[f'next{la}_triple']) / len(all_valid)
                all_valid_v = [r for r in rows if r[f'next{la}_valuable'] is not None]
                base_v = sum(1 for r in all_valid_v if r[f'next{la}_valuable']) / len(all_valid_v)

                t_rate = hits_t / len(valid) if valid else 0
                v_rate = hits_v / len(valid_v) if valid_v else 0
                t_lift = t_rate - base_t
                v_lift = v_rate - base_v

                if la == 3:  # Focus on next-3 for readability
                    P(f"    idx={idx_val} ({sym:>12s}) n={n_c:>4} | "
                      f"triple {100*t_rate:.1f}% ({100*t_lift:+.1f}pp) "
                      f"valuable {100*v_rate:.1f}% ({100*v_lift:+.1f}pp)")

    # ── 3. Cell-pair interactions ─────────────────────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 3: Cell-pair interactions (best pairs for next-3 triple/valuable)")
    P("=" * 80)

    pair_results = []
    cell_list = sorted(cell_names.keys())
    for i, c1 in enumerate(cell_list):
        for c2 in cell_list[i+1:]:
            pair_key = f"{cell_names[c1]}x{cell_names[c2]}"
            pair_counter = Counter((r['grid'][c1], r['grid'][c2]) for r in rows)

            for (v1, v2), cnt in pair_counter.most_common():
                if cnt < 25:
                    continue
                matching = [r for r in rows if r['grid'][c1] == v1 and r['grid'][c2] == v2
                           and r['next3_triple'] is not None]
                if len(matching) < 20:
                    continue

                hits_t = sum(1 for r in matching if r['next3_triple'])
                hits_v = sum(1 for r in matching if r['next3_valuable'])
                t_rate = hits_t / len(matching)
                v_rate = hits_v / len(matching)
                base_t = sum(1 for r in rows if r['next3_triple'] is not None and r['next3_triple']) / sum(1 for r in rows if r['next3_triple'] is not None)
                base_v = sum(1 for r in rows if r['next3_valuable'] is not None and r['next3_valuable']) / sum(1 for r in rows if r['next3_valuable'] is not None)

                t_lift = t_rate - base_t
                v_lift = v_rate - base_v
                pair_results.append((pair_key, v1, v2, cnt, t_rate, t_lift, v_rate, v_lift))

    # Sort by valuable lift
    pair_results.sort(key=lambda x: -abs(x[7]))
    P(f"\n--- Top 20 pairs by |valuable lift| (next-3, n>=25) ---")
    P(f"{'Pair':<25} {'v1':>3} {'v2':>3} {'n':>4} | {'T%':>6} {'T_lift':>8} | {'V%':>6} {'V_lift':>8}")
    for pk, v1, v2, cnt, tr, tl, vr, vl in pair_results[:20]:
        P(f"{pk:<25} {v1:>3} {v2:>3} {cnt:>4} | {100*tr:>5.1f}% {100*tl:>+7.1f}pp | {100*vr:>5.1f}% {100*vl:>+7.1f}pp")

    # Sort by triple lift
    pair_results.sort(key=lambda x: -abs(x[5]))
    P(f"\n--- Top 20 pairs by |triple lift| (next-3, n>=25) ---")
    P(f"{'Pair':<25} {'v1':>3} {'v2':>3} {'n':>4} | {'T%':>6} {'T_lift':>8} | {'V%':>6} {'V_lift':>8}")
    for pk, v1, v2, cnt, tr, tl, vr, vl in pair_results[:20]:
        P(f"{pk:<25} {v1:>3} {v2:>3} {cnt:>4} | {100*tr:>5.1f}% {100*tl:>+7.1f}pp | {100*vr:>5.1f}% {100*vl:>+7.1f}pp")

    # ── 4. Transition matrix ──────────────────────────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 4: Transition matrix — (prev_idx_triple -> next triple)")
    P("=" * 80)

    # Hash full idx triplet as state
    for i, r in enumerate(rows):
        r['state'] = (r['r1_idx'], r['r2_idx'], r['r3_idx'])

    transitions = defaultdict(lambda: {'n':0, 'triple':0, 'valuable':0})
    for i in range(len(rows)-1):
        prev_state = rows[i]['state']
        next_triple = rows[i+1]['is_triple']
        next_valuable = rows[i+1]['is_valuable']
        transitions[prev_state]['n'] += 1
        transitions[prev_state]['triple'] += int(next_triple)
        transitions[prev_state]['valuable'] += int(next_valuable)

    # States with enough data and extreme triple rates
    base_next1_t = sum(1 for r in rows[1:] if r['is_triple']) / (N-1)
    base_next1_v = sum(1 for r in rows[1:] if r['is_valuable']) / (N-1)

    P(f"\nBase: next-1 triple={100*base_next1_t:.1f}%, valuable={100*base_next1_v:.1f}%")
    P(f"Total unique states: {len(transitions)}")

    state_results = []
    for state, stats in transitions.items():
        if stats['n'] < 5:
            continue
        t_rate = stats['triple'] / stats['n']
        v_rate = stats['valuable'] / stats['n']
        state_results.append((state, stats['n'], t_rate, t_rate - base_next1_t, v_rate, v_rate - base_next1_v))

    state_results.sort(key=lambda x: -x[3])
    P(f"\n--- Top 10 states -> highest next-1 triple rate (n>=5) ---")
    for state, n, tr, tl, vr, vl in state_results[:10]:
        P(f"  state={state} n={n} triple={100*tr:.0f}% ({100*tl:+.0f}pp) valuable={100*vr:.0f}% ({100*vl:+.0f}pp)")

    state_results.sort(key=lambda x: x[3])
    P(f"\n--- Bottom 10 states -> lowest next-1 triple rate (n>=5) ---")
    for state, n, tr, tl, vr, vl in state_results[:10]:
        P(f"  state={state} n={n} triple={100*tr:.0f}% ({100*tl:+.0f}pp) valuable={100*vr:.0f}% ({100*vl:+.0f}pp)")

    # States sorted by valuable lift
    state_results.sort(key=lambda x: -x[5])
    P(f"\n--- Top 10 states -> highest next-1 VALUABLE rate (n>=5) ---")
    for state, n, tr, tl, vr, vl in state_results[:10]:
        P(f"  state={state} n={n} triple={100*tr:.0f}% ({100*tl:+.0f}pp) valuable={100*vr:.0f}% ({100*vl:+.0f}pp)")

    # ── 5. Run-length / gap analysis ──────────────────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 5: Gap structure — inter-triple and inter-valuable gaps")
    P("=" * 80)

    # Triple gaps
    triple_gaps = []
    last_triple_idx = -1
    for i, r in enumerate(rows):
        if r['is_triple']:
            if last_triple_idx >= 0:
                triple_gaps.append(i - last_triple_idx)
            last_triple_idx = i

    valuable_gaps = []
    last_val_idx = -1
    for i, r in enumerate(rows):
        if r['is_valuable']:
            if last_val_idx >= 0:
                valuable_gaps.append(i - last_val_idx)
            last_val_idx = i

    P(f"\nTriple gaps: n={len(triple_gaps)}, mean={sum(triple_gaps)/len(triple_gaps):.1f}, "
      f"median={sorted(triple_gaps)[len(triple_gaps)//2]}, "
      f"min={min(triple_gaps)}, max={max(triple_gaps)}")

    # Gap distribution
    gap_hist = Counter(triple_gaps)
    P(f"\nTriple gap distribution (gap -> count):")
    for g in sorted(gap_hist.keys())[:20]:
        bar = '#' * gap_hist[g]
        P(f"  gap={g:>3}: {gap_hist[g]:>4} {bar}")

    P(f"\nValuable gaps: n={len(valuable_gaps)}, mean={sum(valuable_gaps)/len(valuable_gaps):.1f}, "
      f"median={sorted(valuable_gaps)[len(valuable_gaps)//2]}, "
      f"min={min(valuable_gaps)}, max={max(valuable_gaps)}")

    # Test geometric (memoryless) fit
    # If gaps are geometric, P(gap=k) = (1-p)^(k-1) * p
    # Expected mean = 1/p
    p_est_t = 1 / (sum(triple_gaps) / len(triple_gaps))
    P(f"\nGeometric fit test (triple):")
    P(f"  Estimated p = {p_est_t:.4f}")
    # Compare observed vs expected for first 10 gaps
    P(f"  {'Gap':>5} {'Observed':>10} {'Expected':>10} {'Ratio':>8}")
    for g in range(1, 11):
        obs = gap_hist.get(g, 0)
        exp = len(triple_gaps) * ((1-p_est_t)**(g-1)) * p_est_t
        ratio = obs / exp if exp > 0 else 0
        P(f"  {g:>5} {obs:>10} {exp:>10.1f} {ratio:>8.2f}")

    # Test: does gap length predict next triple type?
    P(f"\n--- Gap length -> next triple type ---")
    gap_to_sym = defaultdict(lambda: Counter())
    last_triple_idx = -1
    for i, r in enumerate(rows):
        if r['is_triple']:
            if last_triple_idx >= 0:
                gap = i - last_triple_idx
                gap_bucket = min(gap, 10)  # bucket 10+
                gap_to_sym[gap_bucket][r['reel_1']] += 1
            last_triple_idx = i

    P(f"  {'Gap':>5} | {'acc':>5} {'spins':>5} {'attack':>6} {'steal':>5} {'shield':>6} {'gSack':>5} {'coin':>5} | {'valuable%':>10}")
    for g in sorted(gap_to_sym.keys()):
        c = gap_to_sym[g]
        total = sum(c.values())
        val = c.get('accumulation', 0) + c.get('spins', 0)
        P(f"  {g:>5} | {c.get('accumulation',0):>5} {c.get('spins',0):>5} "
          f"{c.get('attack',0):>6} {c.get('steal',0):>5} {c.get('shield',0):>6} "
          f"{c.get('goldSack',0):>5} {c.get('coin',0):>5} | {100*val/total:>9.1f}%")

    # ── 6. Regime detection ───────────────────────────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 6: Regime detection — rolling triple/valuable rates")
    P("=" * 80)

    window_sizes = [20, 50, 100]
    for ws in window_sizes:
        triple_rates = []
        valuable_rates = []
        for i in range(ws, N):
            window = rows[i-ws:i]
            triple_rates.append(sum(1 for r in window if r['is_triple']) / ws)
            valuable_rates.append(sum(1 for r in window if r['is_valuable']) / ws)

        P(f"\n  Window={ws}: triple rate range [{100*min(triple_rates):.1f}%, {100*max(triple_rates):.1f}%] "
          f"valuable range [{100*min(valuable_rates):.1f}%, {100*max(valuable_rates):.1f}%]")

        # Find extreme regimes
        hottest_start = triple_rates.index(max(triple_rates)) + ws
        coldest_start = triple_rates.index(min(triple_rates)) + ws
        P(f"  Hottest {ws}-spin block starts at spin #{hottest_start}: {100*max(triple_rates):.1f}% triple")
        P(f"  Coldest {ws}-spin block starts at spin #{coldest_start}: {100*min(triple_rates):.1f}% triple")

        # Valuable extremes
        val_hot = max(valuable_rates)
        val_cold = min(valuable_rates)
        val_hot_start = valuable_rates.index(val_hot) + ws
        val_cold_start = valuable_rates.index(val_cold) + ws
        P(f"  Hottest valuable block starts at #{val_hot_start}: {100*val_hot:.1f}%")
        P(f"  Coldest valuable block starts at #{val_cold_start}: {100*val_cold:.1f}%")

    # ── 7. Rolling window features ────────────────────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 7: Rolling window features -> next triple/valuable prediction")
    P("=" * 80)

    # Pre-compute rolling features
    for r in rows:
        r['rolling_features'] = {}

    for ws in [5, 10, 20]:
        for i, r in enumerate(rows):
            if i < ws:
                r['rolling_features'][f'tri_rate_{ws}'] = None
                r['rolling_features'][f'val_rate_{ws}'] = None
                r['rolling_features'][f'mean_r2idx_{ws}'] = None
                continue
            window = rows[i-ws:i]
            r['rolling_features'][f'tri_rate_{ws}'] = sum(1 for w in window if w['is_triple']) / ws
            r['rolling_features'][f'val_rate_{ws}'] = sum(1 for w in window if w['is_valuable']) / ws
            r['rolling_features'][f'mean_r2idx_{ws}'] = sum(w['r2_idx'] for w in window) / ws

    # Test rolling features
    P(f"\n--- Rolling triple rate -> next-1 triple ---")
    for ws in [5, 10, 20]:
        fname = f'tri_rate_{ws}'
        valid = [r for r in rows if r['rolling_features'].get(fname) is not None]
        # Split by above/below median
        vals = [r['rolling_features'][fname] for r in valid]
        median_val = sorted(vals)[len(vals)//2]

        high = [r for r in valid if r['rolling_features'][fname] > median_val]
        low = [r for r in valid if r['rolling_features'][fname] <= median_val]

        high_triple = sum(1 for r in high if r['is_triple']) / len(high) if high else 0
        low_triple = sum(1 for r in low if r['is_triple']) / len(low) if low else 0
        high_val = sum(1 for r in high if r['is_valuable']) / len(high) if high else 0
        low_val = sum(1 for r in low if r['is_valuable']) / len(low) if low else 0

        P(f"  window={ws}: HIGH tri_rate -> {100*high_triple:.1f}% triple, {100*high_val:.1f}% valuable (n={len(high)})")
        P(f"  {'':>{10}} LOW tri_rate -> {100*low_triple:.1f}% triple, {100*low_val:.1f}% valuable (n={len(low)})")
        P(f"  {'':>{10}} spread: triple={100*(high_triple-low_triple):+.1f}pp, valuable={100*(high_val-low_val):+.1f}pp")

    # ── 8. Hex byte-level analysis ────────────────────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 8: Hex byte-level features from trace")
    P("=" * 80)

    P("\nLoading trace hex windows...")
    trace_data = load_trace_hex()
    P(f"Loaded {len(trace_data)} trace snapshots")

    # Match trace to CSV rows by spin_num
    matched = 0
    for r in rows:
        sn = r['sn']
        if sn in trace_data:
            r['trace'] = trace_data[sn]
            matched += 1
        else:
            r['trace'] = None
    P(f"Matched {matched}/{N} spins to trace data")

    # For each hex window that varies, extract per-byte entropy
    hex_windows_to_analyze = [
        'slotBar1@', 'slotBar2@', 'slotBar3@',
        'DynamicSlotResults@',
        'WinBehaviours.innerList@',
    ]

    for hex_prefix in hex_windows_to_analyze:
        # Find full key
        sample_trace = next((r['trace'] for r in rows if r['trace']), None)
        if not sample_trace:
            continue
        full_key = None
        for k in sample_trace.get('hex', {}):
            if k.startswith(hex_prefix):
                full_key = k
                break
        if not full_key:
            continue

        # Extract hex bytes across spins
        hex_vals = []
        triple_flags = []
        valuable_flags = []
        for r in rows:
            if r['trace'] is None:
                continue
            hx = r['trace']['hex'].get(full_key, '')
            if isinstance(hx, str) and len(hx) >= 4:
                hex_vals.append(hx)
                triple_flags.append(r['is_triple'])
                valuable_flags.append(r['is_valuable'])

        if len(hex_vals) < 100:
            P(f"\n  {hex_prefix}: only {len(hex_vals)} samples, skipping")
            continue

        # Find bytes with highest variance
        n_bytes = min(len(hex_vals[0]) // 2, 128)  # up to 128 bytes
        byte_entropy = []
        for b in range(n_bytes):
            byte_vals = []
            for h in hex_vals:
                if b*2+2 <= len(h):
                    byte_vals.append(h[b*2:b*2+2])
            unique = len(set(byte_vals))
            if unique > 1:
                byte_entropy.append((b, unique))

        byte_entropy.sort(key=lambda x: -x[1])
        P(f"\n  {hex_prefix} ({len(hex_vals)} spins, {n_bytes} bytes)")
        P(f"  Variable bytes: {len(byte_entropy)} / {n_bytes}")
        if byte_entropy:
            P(f"  Top 5 most variable: {byte_entropy[:5]}")

        # For top variable bytes, test correlation with triple/valuable
        for byte_off, n_unique in byte_entropy[:10]:
            byte_vals_list = []
            for h in hex_vals:
                if byte_off*2+2 <= len(h):
                    byte_vals_list.append(int(h[byte_off*2:byte_off*2+2], 16))
                else:
                    byte_vals_list.append(0)

            # Split by median byte value
            median_b = sorted(byte_vals_list)[len(byte_vals_list)//2]
            high_idx = [i for i, v in enumerate(byte_vals_list) if v > median_b]
            low_idx = [i for i, v in enumerate(byte_vals_list) if v <= median_b]

            if len(high_idx) < 20 or len(low_idx) < 20:
                continue

            high_t = sum(triple_flags[i] for i in high_idx) / len(high_idx)
            low_t = sum(triple_flags[i] for i in low_idx) / len(low_idx)
            high_v = sum(valuable_flags[i] for i in high_idx) / len(high_idx)
            low_v = sum(valuable_flags[i] for i in low_idx) / len(low_idx)

            if abs(high_t - low_t) > 0.05 or abs(high_v - low_v) > 0.03:
                P(f"    ** byte[{byte_off}] ({n_unique} vals): HIGH->triple {100*high_t:.1f}% LOW->{100*low_t:.1f}% "
                  f"(D={100*(high_t-low_t):+.1f}pp) | valuable HIGH {100*high_v:.1f}% LOW {100*low_v:.1f}% "
                  f"(D={100*(high_v-low_v):+.1f}pp)")

    # ── 9. Mutual information scan ────────────────────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 9: Mutual information — all features x triple/valuable")
    P("=" * 80)

    def mutual_info(x_vals, y_vals):
        """Discrete MI between two lists of categorical values."""
        n = len(x_vals)
        if n == 0:
            return 0
        xy_counts = Counter(zip(x_vals, y_vals))
        x_counts = Counter(x_vals)
        y_counts = Counter(y_vals)
        mi = 0
        for (x, y), c in xy_counts.items():
            pxy = c / n
            px = x_counts[x] / n
            py = y_counts[y] / n
            if pxy > 0 and px > 0 and py > 0:
                mi += pxy * math.log2(pxy / (px * py))
        return mi

    # Build feature vectors
    features = {}
    for r in rows:
        for cell_pos in cell_names:
            cn = cell_names[cell_pos]
            features.setdefault(cn, []).append(r['grid'][cell_pos])
        # idx features
        features.setdefault('r1_idx', []).append(r['r1_idx'])
        features.setdefault('r2_idx', []).append(r['r2_idx'])
        features.setdefault('r3_idx', []).append(r['r3_idx'])
        # State hash
        features.setdefault('state_hash', []).append(hash(r['state']) % 100)
        # Reel symbols
        features.setdefault('s1', []).append(r['reel_1'])
        features.setdefault('s2', []).append(r['reel_2'])
        features.setdefault('s3', []).append(r['reel_3'])
        # Previous spin features
        if rows.index(r) > 0:
            prev = rows[rows.index(r) - 1]
            features.setdefault('prev_triple', []).append(int(prev['is_triple']))
            features.setdefault('prev_valuable', []).append(int(prev['is_valuable']))
            features.setdefault('prev_r1_idx', []).append(prev['r1_idx'])
            features.setdefault('prev_r2_idx', []).append(prev['r2_idx'])
            features.setdefault('prev_r3_idx', []).append(prev['r3_idx'])
        else:
            for fn in ['prev_triple', 'prev_valuable', 'prev_r1_idx', 'prev_r2_idx', 'prev_r3_idx']:
                features.setdefault(fn, []).append(-1)

    # Compute MI with current-spin triple and valuable
    triple_vec = [int(r['is_triple']) for r in rows]
    valuable_vec = [int(r['is_valuable']) for r in rows]

    # Also next-spin triple/valuable
    next_triple_vec = [int(rows[i+1]['is_triple']) if i+1 < N else -1 for i in range(N)]
    next_valuable_vec = [int(rows[i+1]['is_valuable']) if i+1 < N else -1 for i in range(N)]

    P(f"\n{'Feature':<20} {'MI(cur_triple)':>15} {'MI(cur_val)':>12} {'MI(nxt_triple)':>15} {'MI(nxt_val)':>12}")
    P("-" * 78)

    mi_results = []
    for fname, fvals in sorted(features.items()):
        mi_ct = mutual_info(fvals, triple_vec)
        mi_cv = mutual_info(fvals, valuable_vec)
        mi_nt = mutual_info(fvals[:-1], next_triple_vec[:-1])  # skip last
        mi_nv = mutual_info(fvals[:-1], next_valuable_vec[:-1])
        mi_results.append((fname, mi_ct, mi_cv, mi_nt, mi_nv))

    mi_results.sort(key=lambda x: -x[3])  # sort by next-triple MI
    for fname, mi_ct, mi_cv, mi_nt, mi_nv in mi_results:
        flag_t = " *" if mi_nt > 0.01 else ""
        flag_v = " ***" if mi_nv > 0.005 else ""
        P(f"{fname:<20} {mi_ct:>15.4f} {mi_cv:>12.4f} {mi_nt:>15.4f}{flag_t} {mi_nv:>12.4f}{flag_v}")

    # ── 10. Composite scoring with temporal CV ────────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 10: Composite scoring — all significant features stacked")
    P("=" * 80)

    # Use ALL significant single-cell features from section 1
    # Build composite score per spin
    for r in rows:
        score_triple = 0
        score_valuable = 0
        g = r['grid']

        # From prior session: r1_idx=1 -> +12.7pp, r3_idx=2 -> -10.2pp
        # Now add ALL 9 cells
        for cell_pos in cell_names:
            idx_val = g[cell_pos]
            # Pre-compute: for this cell+idx, what's the observed next-3 triple/valuable rate?
            # Use entire dataset as training (we'll CV later)
            matching = [x for x in rows if x['grid'][cell_pos] == idx_val and x['next3_triple'] is not None]
            if len(matching) < 20:
                continue
            base_t_count = sum(1 for x in rows if x['next3_triple'] is not None and x['next3_triple'])
            base_t_total = sum(1 for x in rows if x['next3_triple'] is not None)
            base_t = base_t_count / base_t_total

            cell_t = sum(1 for x in matching if x['next3_triple']) / len(matching)
            lift_t = cell_t - base_t

            if abs(lift_t) > 0.05:
                score_triple += 1 if lift_t > 0 else -1

            matching_v = [x for x in matching if x['next3_valuable'] is not None]
            base_v_count = sum(1 for x in rows if x['next3_valuable'] is not None and x['next3_valuable'])
            base_v_total = sum(1 for x in rows if x['next3_valuable'] is not None)
            base_v = base_v_count / base_v_total

            if len(matching_v) >= 20:
                cell_v = sum(1 for x in matching_v if x['next3_valuable']) / len(matching_v)
                lift_v = cell_v - base_v
                if abs(lift_v) > 0.03:
                    score_valuable += 1 if lift_v > 0 else -1

        r['score_triple'] = score_triple
        r['score_valuable'] = score_valuable

    # Report composite score distributions
    score_t_dist = Counter(r['score_triple'] for r in rows)
    score_v_dist = Counter(r['score_valuable'] for r in rows)
    P(f"\nTriple score distribution: {dict(sorted(score_t_dist.items()))}")
    P(f"Valuable score distribution: {dict(sorted(score_v_dist.items()))}")

    # Temporal CV on composite score
    P(f"\n--- Temporal CV: composite triple score -> next-3 triple ---")
    fold_size = N // 5
    for fold in range(5):
        start = fold * fold_size
        end = start + fold_size if fold < 4 else N
        fold_rows = [r for r in rows[start:end] if r['next3_triple'] is not None]

        hot = [r for r in fold_rows if r['score_triple'] >= 2]
        cold = [r for r in fold_rows if r['score_triple'] <= -1]
        neutral = [r for r in fold_rows if -1 < r['score_triple'] < 2]

        ht = sum(1 for r in hot if r['next3_triple']) / len(hot) if hot else 0
        ct = sum(1 for r in cold if r['next3_triple']) / len(cold) if cold else 0
        nt_rate = sum(1 for r in neutral if r['next3_triple']) / len(neutral) if neutral else 0

        hv = sum(1 for r in hot if r['next3_valuable']) / len(hot) if hot else 0
        cv = sum(1 for r in cold if r['next3_valuable']) / len(cold) if cold else 0

        P(f"  Fold {fold}: HOT={100*ht:.1f}% ({len(hot)}) NEUTRAL={100*nt_rate:.1f}% ({len(neutral)}) "
          f"COLD={100*ct:.1f}% ({len(cold)}) | spread={100*(ht-ct):+.1f}pp | "
          f"valuable: HOT={100*hv:.1f}% COLD={100*cv:.1f}% spread={100*(hv-cv):+.1f}pp")

    # ── 11. Symbol co-occurrence on 3x3 grid ──────────────────────────────
    P("\n" + "=" * 80)
    P("  SECTION 11: Symbol co-occurrence — which visible symbols predict next triple?")
    P("=" * 80)

    # Hash full 3x3 symbol grid
    for r in rows:
        gsym = grid_symbols(r['grid'])
        r['grid_sym_hash'] = hashlib.md5(str(sorted(gsym.items())).encode()).hexdigest()[:8]
        # Count unique symbols visible
        r['n_unique_syms'] = len(set(gsym.values()))
        # Count valuable symbols visible
        r['n_valuable_visible'] = sum(1 for v in gsym.values() if v in VALUABLE_SYMS)
        # Specific: accumulation anywhere in grid
        r['acc_visible'] = any(v == 'accumulation' for v in gsym.values())
        r['spins_visible'] = any(v == 'spins' for v in gsym.values())

    # Test: number of valuable symbols visible -> next triple/valuable
    P(f"\n--- Valuable symbols visible -> next-1 triple/valuable ---")
    for nv in range(7):
        matching = [r for r in rows[:-1] if r['n_valuable_visible'] == nv]
        if len(matching) < 10:
            continue
        next_t = sum(1 for i, r in enumerate(rows[:-1]) if r['n_valuable_visible'] == nv
                    and rows[rows.index(r)+1]['is_triple']) / len(matching)
        next_v = sum(1 for i, r in enumerate(rows[:-1]) if r['n_valuable_visible'] == nv
                    and rows[rows.index(r)+1]['is_valuable']) / len(matching)
        P(f"  {nv} valuable syms visible: n={len(matching)}, next triple={100*next_t:.1f}%, next valuable={100*next_v:.1f}%")

    # Test: accumulation visible -> next valuable
    P(f"\n--- Accumulation visible -> next valuable ---")
    acc_vis = [r for r in rows[:-1] if r['acc_visible']]
    no_acc = [r for r in rows[:-1] if not r['acc_visible']]
    if acc_vis and no_acc:
        av_next_v = sum(1 for r in acc_vis if rows[rows.index(r)+1]['is_valuable']) / len(acc_vis)
        na_next_v = sum(1 for r in no_acc if rows[rows.index(r)+1]['is_valuable']) / len(no_acc)
        P(f"  ACC visible: {100*av_next_v:.1f}% next valuable (n={len(acc_vis)})")
        P(f"  No ACC:      {100*na_next_v:.1f}% next valuable (n={len(no_acc)})")

    # Test: spins visible -> next valuable
    P(f"\n--- Spins visible -> next valuable ---")
    spn_vis = [r for r in rows[:-1] if r['spins_visible']]
    no_spn = [r for r in rows[:-1] if not r['spins_visible']]
    if spn_vis and no_spn:
        sv_next_v = sum(1 for r in spn_vis if rows[rows.index(r)+1]['is_valuable']) / len(spn_vis)
        ns_next_v = sum(1 for r in no_spn if rows[rows.index(r)+1]['is_valuable']) / len(no_spn)
        P(f"  SPINS visible: {100*sv_next_v:.1f}% next valuable (n={len(spn_vis)})")
        P(f"  No SPINS:      {100*ns_next_v:.1f}% next valuable (n={len(no_spn)})")

    # ── 12. Zoki 1-7 lookahead for ALL promising features ────────────────
    P("\n" + "=" * 80)
    P("  SECTION 12: Zoki-style 1-7 lookahead — promising features deep dive")
    P("=" * 80)

    # Test the most promising features from above in a 1-7 lookahead window
    # Feature: "is current spin a triple?" -> does THAT predict next valuable within 1-7?
    P(f"\n--- Current triple -> next valuable within N ---")
    for la in [1, 2, 3, 5, 7]:
        # For non-standard lookaheads (2), compute inline first
        if la == 2:
            cur_triple = []
            cur_nontriple = []
            for i, r in enumerate(rows):
                if i + 2 >= N:
                    continue
                has_val = any(rows[j]['is_valuable'] for j in range(i+1, min(i+3, N)))
                if r['is_triple']:
                    cur_triple.append(has_val)
                else:
                    cur_nontriple.append(has_val)
            t_rate = sum(cur_triple) / len(cur_triple) if cur_triple else 0
            nt_rate = sum(cur_nontriple) / len(cur_nontriple) if cur_nontriple else 0
            P(f"  next-{la}: after TRIPLE={100*t_rate:.1f}% (n={len(cur_triple)}) "
              f"after NON-TRIPLE={100*nt_rate:.1f}% (n={len(cur_nontriple)}) "
              f"spread={100*(t_rate-nt_rate):+.1f}pp")
            continue

        cur_triple = [r for r in rows if r['is_triple'] and r[f'next{la}_valuable'] is not None]
        cur_nontriple = [r for r in rows if not r['is_triple'] and r[f'next{la}_valuable'] is not None]
        if not cur_triple:
            continue
        t_rate = sum(1 for r in cur_triple if r[f'next{la}_valuable']) / len(cur_triple)
        nt_rate = sum(1 for r in cur_nontriple if r[f'next{la}_valuable']) / len(cur_nontriple)
        P(f"  next-{la}: after TRIPLE={100*t_rate:.1f}% (n={len(cur_triple)}) "
          f"after NON-TRIPLE={100*nt_rate:.1f}% (n={len(cur_nontriple)}) "
          f"spread={100*(t_rate-nt_rate):+.1f}pp")

    # Feature: "spin N was valuable" -> next valuable within 1-7?
    P(f"\n--- Current valuable -> next valuable within N ---")
    for la in [1, 3, 5, 7]:
        cur_val = [r for r in rows if r['is_valuable'] and r[f'next{la}_valuable'] is not None]
        cur_nonval = [r for r in rows if not r['is_valuable'] and r[f'next{la}_valuable'] is not None]
        if not cur_val:
            continue
        v_rate = sum(1 for r in cur_val if r[f'next{la}_valuable']) / len(cur_val)
        nv_rate = sum(1 for r in cur_nonval if r[f'next{la}_valuable']) / len(cur_nonval)
        P(f"  next-{la}: after VALUABLE={100*v_rate:.1f}% (n={len(cur_val)}) "
          f"after NON-VAL={100*nv_rate:.1f}% (n={len(cur_nonval)}) "
          f"spread={100*(v_rate-nv_rate):+.1f}pp")

    # ── FINAL SUMMARY ─────────────────────────────────────────────────────
    P("\n" + "=" * 80)
    P("  FINAL SUMMARY")
    P("=" * 80)

    P("\nSECTION VERDICTS:")
    P("  1. 9-cell grid: [results above]")
    P("  2. Zoki cells: [results above]")
    P("  3. Cell pairs: [results above]")
    P("  4. Transitions: [results above]")
    P("  5. Gaps: [results above]")
    P("  6. Regimes: [results above]")
    P("  7. Rolling windows: [results above]")
    P("  8. Hex bytes: [results above]")
    P("  9. Mutual information: [results above]")
    P("  10. Composite: [results above]")
    P("  11. Symbol co-occurrence: [results above]")
    P("  12. Zoki lookahead: [results above]")

    # Write output
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, 'w') as f:
        f.write('\n'.join(out_lines))
    P(f"\nResults saved to {OUT}")

if __name__ == '__main__':
    main()
