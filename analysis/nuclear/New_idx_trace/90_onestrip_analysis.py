"""
90_onestrip_analysis.py — One-Strip Swap Corrected Analysis

Discovery: There is ONE strip shared by all 3 reels. The idx values swap:
  r1 symbol = strip[r3_idx]
  r2 symbol = strip[r2_idx]
  r3 symbol = strip[r1_idx]

Strip: 0=attack, 1=coin, 2=shield, 3=goldSack, 4=steal, 5=coin, 6=spins, 7=goldSack, 8=accumulation

This script loads all 8173 spins with idx data, applies the corrected model,
and searches for new predictive rules for ACC/SPN triples.
"""

import csv
import os
from collections import Counter, defaultdict
from math import comb, sqrt
import json

# ─── Strip definition ───
STRIP = {0:'attack', 1:'coin', 2:'shield', 3:'goldSack', 4:'steal',
         5:'coin', 6:'spins', 7:'goldSack', 8:'accumulation'}
STRIP_ID = {0:3, 1:1, 2:5, 3:2, 4:4, 5:1, 6:6, 7:2, 8:30}

# Symbol equivalence classes (indices that map to same symbol)
SYM_CLASS = {
    'attack': [0], 'coin': [1,5], 'shield': [2], 'goldSack': [3,7],
    'steal': [4], 'spins': [6], 'accumulation': [8]
}
# Reverse: idx -> equivalence class name
IDX_TO_SYM = {i: s for s, indices in SYM_CLASS.items() for i in indices}

# ─── Loader ───
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'data')

FILES = [
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_enriched_v2.csv')),
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_2026-04-13.csv')),
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_2026-04-14.csv')),
    ('Islam', os.path.join(DATA_DIR, 'Islam', 'spin_history_Islam_2026-04-13.csv')),
    ('Nick',  os.path.join(DATA_DIR, 'Nick',  'spin_history_Nick_2026-04-13.csv')),
]

def load_all():
    """Load all spins with idx into unified list of dicts."""
    rows = []
    for acct, path in FILES:
        with open(path) as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    r1i = int(r['r1_idx'])
                    r2i = int(r['r2_idx'])
                    r3i = int(r['r3_idx'])
                except (ValueError, KeyError):
                    continue
                if r1i not in STRIP or r2i not in STRIP or r3i not in STRIP:
                    continue

                seq = int(r.get('seq') or r.get('csv_seq') or 0)
                reel_1 = r.get('reel_1', '')
                reel_2 = r.get('reel_2', '')
                reel_3 = r.get('reel_3', '')
                is_triple = r.get('is_triple', '').lower() == 'true'

                # Determine VT type from reel symbols
                vt_type = None
                if is_triple:
                    if reel_1 == 'accumulation':
                        vt_type = 'ACC'
                    elif reel_1 == 'spins':
                        vt_type = 'SPN'

                # sa_ counters if available
                sa_spn = int(r['sa_spn']) if r.get('sa_spn', '') else None
                sa_acc = int(r['sa_acc']) if r.get('sa_acc', '') else None
                sa_spins = int(r['sa_spins']) if r.get('sa_spins', '') else None

                rows.append({
                    'acct': acct, 'seq': seq,
                    'r1_idx': r1i, 'r2_idx': r2i, 'r3_idx': r3i,
                    # Corrected: what symbol each reel actually shows
                    'true_r1_sym': IDX_TO_SYM[r3i],  # r1 shows strip[r3_idx]
                    'true_r2_sym': IDX_TO_SYM[r2i],  # r2 shows strip[r2_idx]
                    'true_r3_sym': IDX_TO_SYM[r1i],  # r3 shows strip[r1_idx]
                    'reel_1': reel_1, 'reel_2': reel_2, 'reel_3': reel_3,
                    'is_triple': is_triple, 'vt_type': vt_type,
                    'sa_spn': sa_spn, 'sa_acc': sa_acc, 'sa_spins': sa_spins,
                })
    return rows


def compute_features(rows):
    """Add derived features to each row."""
    # Per-account gap tracking
    last_vt = {}       # acct -> row index of last VT
    last_acc = {}      # acct -> row index of last ACC
    last_spn = {}      # acct -> row index of last SPN
    last_triple = {}   # acct -> row index of last any triple

    for i, r in enumerate(rows):
        acct = r['acct']
        r1i, r2i, r3i = r['r1_idx'], r['r2_idx'], r['r3_idx']

        # ── Index-based features ──
        r['idx_sum'] = r1i + r2i + r3i
        r['idx_spread'] = max(r1i, r2i, r3i) - min(r1i, r2i, r3i)
        r['idx_max'] = max(r1i, r2i, r3i)
        r['idx_min'] = min(r1i, r2i, r3i)

        # Parity
        r['idx_parity_sum'] = (r1i % 2) + (r2i % 2) + (r3i % 2)  # 0=all even, 3=all odd
        r['all_same_parity'] = r['idx_parity_sum'] in (0, 3)

        # Same symbol class checks (accounting for coin=[1,5], goldSack=[3,7])
        sym1, sym2, sym3 = IDX_TO_SYM[r1i], IDX_TO_SYM[r2i], IDX_TO_SYM[r3i]
        r['all_same_class'] = (sym1 == sym2 == sym3)
        r['pair_12'] = (sym1 == sym2)
        r['pair_13'] = (sym1 == sym3)
        r['pair_23'] = (sym2 == sym3)
        r['any_pair'] = r['pair_12'] or r['pair_13'] or r['pair_23']
        r['no_pair'] = not r['any_pair']

        # Corrected symbol checks (what each reel actually displays)
        ts1, ts2, ts3 = r['true_r1_sym'], r['true_r2_sym'], r['true_r3_sym']
        r['true_all_same'] = (ts1 == ts2 == ts3)
        r['true_pair_12'] = (ts1 == ts2)
        r['true_pair_13'] = (ts1 == ts3)
        r['true_pair_23'] = (ts2 == ts3)
        r['true_any_pair'] = r['true_pair_12'] or r['true_pair_13'] or r['true_pair_23']

        # High-value idx indicators (goldSack=3,7; acc=8; spins=6)
        r['has_acc_idx'] = 8 in (r1i, r2i, r3i)
        r['has_spn_idx'] = 6 in (r1i, r2i, r3i)
        r['has_gold_idx'] = any(x in (3, 7) for x in (r1i, r2i, r3i))
        r['has_steal_idx'] = 4 in (r1i, r2i, r3i)
        r['acc_idx_count'] = [r1i, r2i, r3i].count(8)
        r['spn_idx_count'] = [r1i, r2i, r3i].count(6)

        # Index distances (circular on 9-position strip)
        def circ_dist(a, b):
            d = abs(a - b)
            return min(d, 9 - d)
        r['dist_12'] = circ_dist(r1i, r2i)
        r['dist_23'] = circ_dist(r2i, r3i)
        r['dist_13'] = circ_dist(r1i, r3i)
        r['max_dist'] = max(r['dist_12'], r['dist_23'], r['dist_13'])
        r['min_dist'] = min(r['dist_12'], r['dist_23'], r['dist_13'])

        # ── Gap features ──
        r['gap_vt'] = i - last_vt.get(acct, -999)
        r['gap_acc'] = i - last_acc.get(acct, -999)
        r['gap_spn'] = i - last_spn.get(acct, -999)
        r['gap_triple'] = i - last_triple.get(acct, -999)

        # Update trackers
        if r['vt_type']:
            last_vt[acct] = i
            if r['vt_type'] == 'ACC':
                last_acc[acct] = i
            elif r['vt_type'] == 'SPN':
                last_spn[acct] = i
        if r['is_triple']:
            last_triple[acct] = i

    # ── Lag features (previous spin's idx) ──
    for i in range(1, len(rows)):
        if rows[i]['acct'] != rows[i-1]['acct']:
            continue  # Don't cross account boundaries
        prev = rows[i-1]
        r = rows[i]
        r['prev_r1_idx'] = prev['r1_idx']
        r['prev_r2_idx'] = prev['r2_idx']
        r['prev_r3_idx'] = prev['r3_idx']
        r['prev_idx_sum'] = prev['idx_sum']
        r['prev_is_triple'] = prev['is_triple']
        r['prev_true_r1_sym'] = prev['true_r1_sym']
        r['prev_true_r2_sym'] = prev['true_r2_sym']
        r['prev_true_r3_sym'] = prev['true_r3_sym']

        # Idx deltas
        r['delta_r1'] = r['r1_idx'] - prev['r1_idx']
        r['delta_r2'] = r['r2_idx'] - prev['r2_idx']
        r['delta_r3'] = r['r3_idx'] - prev['r3_idx']
        r['delta_sum'] = r['idx_sum'] - prev['idx_sum']

    return rows


def fisher_pvalue(hits, trials, base_rate, n_total):
    """One-sided binomial p-value approximation using normal approx."""
    if trials == 0:
        return 1.0
    observed = hits / trials
    expected = base_rate
    se = sqrt(expected * (1 - expected) / trials) if trials > 0 else 1
    if se == 0:
        return 1.0
    z = (observed - expected) / se
    # Quick normal CDF approx for upper tail
    if z <= 0:
        return 1.0
    # Abramowitz & Stegun approximation
    t = 1.0 / (1.0 + 0.2316419 * z)
    d = 0.3989422804 * (2.718281828 ** (-z * z / 2))
    p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    return p


def evaluate_strategy(rows, condition_fn, label, target_fn=None):
    """Evaluate a betting strategy."""
    if target_fn is None:
        target_fn = lambda r: r['vt_type'] is not None

    n_total = len(rows)
    n_targets = sum(1 for r in rows if target_fn(r))
    base_rate = n_targets / n_total if n_total > 0 else 0

    bets = 0
    hits = 0
    for r in rows:
        if condition_fn(r):
            bets += 1
            if target_fn(r):
                hits += 1

    if bets == 0:
        return None

    precision = hits / bets if bets > 0 else 0
    lift = precision / base_rate if base_rate > 0 else 0
    catch = hits / n_targets if n_targets > 0 else 0
    pval = fisher_pvalue(hits, bets, base_rate, n_total)

    return {
        'label': label,
        'bets': bets, 'hits': hits,
        'precision': precision, 'lift': lift,
        'catch': catch, 'bets_per_hit': bets / hits if hits > 0 else float('inf'),
        'pvalue': pval,
        'base_rate': base_rate, 'n_total': n_total, 'n_targets': n_targets,
    }


def print_results(results, title, min_hits=2):
    """Print strategy results table sorted by p-value."""
    results = [r for r in results if r and r['hits'] >= min_hits]
    results.sort(key=lambda x: x['pvalue'])

    print(f"\n{'='*100}")
    print(f"  {title}")
    print(f"  Total: {results[0]['n_total']} spins, {results[0]['n_targets']} targets, "
          f"base rate: {results[0]['base_rate']:.2%}" if results else "  No results")
    print(f"{'='*100}")
    print(f"{'Strategy':<55s} {'Prec':>6s} {'Lift':>5s} {'Catch':>6s} {'B/H':>5s} {'Bets':>5s} {'Hits':>4s} {'p-val':>8s}")
    print("-" * 100)
    for r in results[:30]:
        sig = '***' if r['pvalue'] < 0.001 else '**' if r['pvalue'] < 0.01 else '*' if r['pvalue'] < 0.05 else ''
        print(f"{r['label']:<55s} {r['precision']:>5.1%} {r['lift']:>5.1f}x {r['catch']:>5.1%} "
              f"{r['bets_per_hit']:>5.1f} {r['bets']:>5d} {r['hits']:>4d} {r['pvalue']:>7.4f} {sig}")


def run_analysis(rows):
    """Run full analysis."""
    # Filter to rows with lag features
    valid = [r for r in rows if 'prev_r1_idx' in r]
    print(f"\nLoaded {len(rows)} total spins, {len(valid)} with lag features")

    n_vt = sum(1 for r in valid if r['vt_type'])
    n_acc = sum(1 for r in valid if r['vt_type'] == 'ACC')
    n_spn = sum(1 for r in valid if r['vt_type'] == 'SPN')
    n_triple = sum(1 for r in valid if r['is_triple'])
    print(f"VTs: {n_vt} (ACC: {n_acc}, SPN: {n_spn}), All triples: {n_triple}")

    # ─────────────────────────────────────────────
    # SECTION 1: Strip position distributions
    # ─────────────────────────────────────────────
    print("\n" + "="*80)
    print("  SECTION 1: Index distributions (all spins vs pre-VT)")
    print("="*80)

    # Overall idx distribution per reel
    for reel_name, idx_key in [('r1_idx','r1_idx'), ('r2_idx','r2_idx'), ('r3_idx','r3_idx')]:
        all_counts = Counter(r[idx_key] for r in valid)
        vt_counts = Counter(r[idx_key] for r in valid if r['vt_type'])
        print(f"\n{reel_name} distribution (all / pre-VT):")
        for idx in range(9):
            a_pct = all_counts[idx] / len(valid) * 100
            v_pct = vt_counts[idx] / n_vt * 100 if n_vt > 0 else 0
            ratio = v_pct / a_pct if a_pct > 0 else 0
            bar = '#' * int(ratio * 10)
            print(f"  idx={idx} ({STRIP[idx]:>13s}): all={a_pct:5.1f}%  vt={v_pct:5.1f}%  ratio={ratio:.2f}x  {bar}")

    # ─────────────────────────────────────────────
    # SECTION 2: Previous-spin idx before VT
    # ─────────────────────────────────────────────
    print("\n" + "="*80)
    print("  SECTION 2: PREVIOUS spin idx distribution before VT (lag-1)")
    print("="*80)

    for reel_name, idx_key in [('prev_r1_idx','prev_r1_idx'), ('prev_r2_idx','prev_r2_idx'), ('prev_r3_idx','prev_r3_idx')]:
        all_counts = Counter(r.get(idx_key) for r in valid if r.get(idx_key) is not None)
        vt_counts = Counter(r.get(idx_key) for r in valid if r['vt_type'] and r.get(idx_key) is not None)
        print(f"\n{reel_name} (spin N-1) before VT at spin N:")
        for idx in range(9):
            a_pct = all_counts[idx] / sum(all_counts.values()) * 100 if sum(all_counts.values()) > 0 else 0
            v_pct = vt_counts[idx] / sum(vt_counts.values()) * 100 if sum(vt_counts.values()) > 0 else 0
            ratio = v_pct / a_pct if a_pct > 0 else 0
            print(f"  idx={idx} ({STRIP[idx]:>13s}): all={a_pct:5.1f}%  pre_vt={v_pct:5.1f}%  ratio={ratio:.2f}x")

    # ─────────────────────────────────────────────
    # SECTION 3: Corrected symbol class analysis
    # ─────────────────────────────────────────────
    print("\n" + "="*80)
    print("  SECTION 3: True displayed symbol analysis (corrected for swap)")
    print("="*80)

    # What symbol did r1 ACTUALLY show on the spin before VT?
    for label, key in [("r1 displays (=strip[r3_idx])", 'true_r1_sym'),
                       ("r2 displays (=strip[r2_idx])", 'true_r2_sym'),
                       ("r3 displays (=strip[r1_idx])", 'true_r3_sym')]:
        all_c = Counter(r[key] for r in valid)
        vt_c = Counter(r[key] for r in valid if r['vt_type'])
        print(f"\n{label}:")
        for sym in sorted(SYM_CLASS.keys()):
            a_pct = all_c[sym] / len(valid) * 100
            v_pct = vt_c[sym] / n_vt * 100 if n_vt > 0 else 0
            ratio = v_pct / a_pct if a_pct > 0 else 0
            print(f"  {sym:>14s}: all={a_pct:5.1f}%  vt={v_pct:5.1f}%  ratio={ratio:.2f}x")

    # ─────────────────────────────────────────────
    # SECTION 4: Feature distributions pre-VT
    # ─────────────────────────────────────────────
    print("\n" + "="*80)
    print("  SECTION 4: Composite features (same-spin)")
    print("="*80)

    features = [
        ('idx_sum', lambda r: r['idx_sum']),
        ('idx_spread', lambda r: r['idx_spread']),
        ('idx_parity_sum', lambda r: r['idx_parity_sum']),
        ('all_same_parity', lambda r: r['all_same_parity']),
        ('all_same_class', lambda r: r['all_same_class']),
        ('any_pair', lambda r: r['any_pair']),
        ('no_pair', lambda r: r['no_pair']),
        ('has_acc_idx', lambda r: r['has_acc_idx']),
        ('has_spn_idx', lambda r: r['has_spn_idx']),
        ('has_gold_idx', lambda r: r['has_gold_idx']),
        ('has_steal_idx', lambda r: r['has_steal_idx']),
        ('max_dist', lambda r: r['max_dist']),
        ('min_dist', lambda r: r['min_dist']),
        ('true_any_pair', lambda r: r['true_any_pair']),
    ]

    for fname, fn in features:
        all_vals = [fn(r) for r in valid]
        vt_vals = [fn(r) for r in valid if r['vt_type']]
        if isinstance(all_vals[0], bool):
            all_rate = sum(all_vals) / len(all_vals)
            vt_rate = sum(vt_vals) / len(vt_vals) if vt_vals else 0
            print(f"  {fname:<25s}: all={all_rate:.3f}  vt={vt_rate:.3f}  ratio={vt_rate/all_rate:.2f}x" if all_rate > 0 else f"  {fname}: all=0")
        else:
            all_mean = sum(all_vals) / len(all_vals)
            vt_mean = sum(vt_vals) / len(vt_vals) if vt_vals else 0
            print(f"  {fname:<25s}: all_mean={all_mean:.2f}  vt_mean={vt_mean:.2f}  ratio={vt_mean/all_mean:.2f}x" if all_mean > 0 else f"  {fname}: all=0")

    # ─────────────────────────────────────────────
    # SECTION 5: Strategy sweep — ALL VTs
    # ─────────────────────────────────────────────
    strategies_all = []

    # Gap-based conditions
    gap_thresholds = [20, 30, 40, 50, 60]

    for g in gap_thresholds:
        # Pure gap
        strategies_all.append(evaluate_strategy(valid,
            lambda r, g=g: r['gap_vt'] >= g,
            f"gap_vt>={g}"))

        # Gap + idx features
        for idx_cond, idx_label in [
            (lambda r: r['idx_sum'] >= 15, "sum>=15"),
            (lambda r: r['idx_sum'] >= 18, "sum>=18"),
            (lambda r: r['idx_spread'] <= 2, "spread<=2"),
            (lambda r: r['idx_spread'] >= 5, "spread>=5"),
            (lambda r: r['no_pair'], "no_pair"),
            (lambda r: r['any_pair'], "any_pair"),
            (lambda r: r['has_acc_idx'], "has_acc_idx"),
            (lambda r: r['has_spn_idx'], "has_spn_idx"),
            (lambda r: r['has_gold_idx'], "has_gold_idx"),
            (lambda r: r['has_steal_idx'], "has_steal_idx"),
            (lambda r: r['all_same_parity'], "same_parity"),
            (lambda r: r['max_dist'] <= 2, "max_dist<=2"),
            (lambda r: r['min_dist'] == 0, "min_dist=0"),
            (lambda r: r['idx_max'] >= 7, "max_idx>=7"),
            (lambda r: r['idx_min'] <= 1, "min_idx<=1"),
            (lambda r: r['true_any_pair'], "true_any_pair"),
            (lambda r: not r['true_any_pair'], "true_no_pair"),
            # Prev-spin features
            (lambda r: r.get('prev_is_triple', False), "prev_triple"),
            (lambda r: not r.get('prev_is_triple', True), "prev_no_triple"),
            (lambda r: r.get('prev_true_r1_sym') == 'steal', "prev_r1_steal"),
            (lambda r: r.get('prev_true_r2_sym') == 'steal', "prev_r2_steal"),
            (lambda r: r.get('prev_true_r3_sym') == 'steal', "prev_r3_steal"),
            (lambda r: 'steal' in (r.get('prev_true_r1_sym',''), r.get('prev_true_r2_sym',''), r.get('prev_true_r3_sym','')), "prev_any_steal"),
            (lambda r: r.get('prev_idx_sum', 0) >= 15, "prev_sum>=15"),
            (lambda r: r.get('prev_idx_sum', 99) <= 8, "prev_sum<=8"),
        ]:
            strategies_all.append(evaluate_strategy(valid,
                lambda r, g=g, ic=idx_cond: r['gap_vt'] >= g and ic(r),
                f"gap>={g}+{idx_label}"))

        # Gap + two-feature combos
        combos = [
            (lambda r: r['has_acc_idx'] and r['idx_sum'] >= 15, "acc_idx+sum>=15"),
            (lambda r: r['has_spn_idx'] and r['idx_spread'] >= 5, "spn_idx+spread>=5"),
            (lambda r: r['has_gold_idx'] and r['no_pair'], "gold+no_pair"),
            (lambda r: r['has_steal_idx'] and r['idx_sum'] >= 15, "steal+sum>=15"),
            (lambda r: r['max_dist'] <= 2 and r['idx_sum'] >= 12, "close+sum>=12"),
            (lambda r: r['all_same_parity'] and r['idx_sum'] >= 15, "parity+sum>=15"),
            (lambda r: r['true_any_pair'] and r['idx_sum'] >= 15, "true_pair+sum>=15"),
            (lambda r: r['no_pair'] and r['idx_sum'] >= 18, "no_pair+sum>=18"),
            (lambda r: r.get('prev_is_triple', False) is False and r['has_acc_idx'], "no_prev_triple+acc_idx"),
            (lambda r: r['has_gold_idx'] and r.get('prev_true_r2_sym') == 'steal', "gold+prev_steal"),
            (lambda r: r['min_dist'] == 0 and r['has_acc_idx'], "adj+acc_idx"),
            (lambda r: r['idx_spread'] <= 3 and r['has_acc_idx'], "tight+acc_idx"),
            (lambda r: r['has_acc_idx'] and r['has_gold_idx'], "acc_idx+gold_idx"),
            (lambda r: r['idx_max'] >= 7 and r['idx_min'] <= 1, "extreme_spread"),
        ]
        for combo_fn, combo_label in combos:
            strategies_all.append(evaluate_strategy(valid,
                lambda r, g=g, cf=combo_fn: r['gap_vt'] >= g and cf(r),
                f"gap>={g}+{combo_label}"))

    # No-gap idx-only strategies
    idx_only = [
        (lambda r: r['all_same_class'], "all_same_class"),
        (lambda r: r['acc_idx_count'] >= 2, "acc_idx_x2"),
        (lambda r: r['spn_idx_count'] >= 2, "spn_idx_x2"),
        (lambda r: r['idx_sum'] >= 20, "sum>=20"),
        (lambda r: r['idx_spread'] == 0, "spread=0"),
        (lambda r: r['max_dist'] == 0, "all_same_idx"),
        (lambda r: r['has_acc_idx'] and r['has_spn_idx'], "acc+spn_idx"),
        (lambda r: r['idx_sum'] <= 4, "sum<=4"),
    ]
    for fn, label in idx_only:
        strategies_all.append(evaluate_strategy(valid, fn, f"[no_gap]{label}"))

    print_results(strategies_all, "ALL VTs (ACC + SPN)")

    # ─────────────────────────────────────────────
    # SECTION 6: Strategy sweep — ACC only
    # ─────────────────────────────────────────────
    strategies_acc = []
    target_acc = lambda r: r['vt_type'] == 'ACC'

    for g in gap_thresholds:
        strategies_acc.append(evaluate_strategy(valid,
            lambda r, g=g: r['gap_acc'] >= g, f"gap_acc>={g}", target_acc))

        for idx_cond, idx_label in [
            (lambda r: r['has_acc_idx'], "has_acc_idx"),
            (lambda r: r['acc_idx_count'] >= 2, "acc_x2"),
            (lambda r: r['has_gold_idx'], "has_gold"),
            (lambda r: r['has_steal_idx'], "has_steal"),
            (lambda r: r['idx_sum'] >= 15, "sum>=15"),
            (lambda r: r['idx_sum'] >= 18, "sum>=18"),
            (lambda r: r['no_pair'], "no_pair"),
            (lambda r: r['all_same_parity'], "same_parity"),
            (lambda r: r['idx_spread'] <= 2, "spread<=2"),
            (lambda r: r.get('prev_true_r2_sym') == 'steal', "prev_r2_steal"),
            (lambda r: r.get('prev_true_r1_sym') in ('goldSack','accumulation'), "prev_r1_high"),
            (lambda r: r.get('prev_idx_sum', 0) >= 15, "prev_sum>=15"),
            (lambda r: r['true_any_pair'], "true_pair"),
            (lambda r: r['max_dist'] <= 2, "close"),
            (lambda r: r['has_acc_idx'] and r['has_gold_idx'], "acc+gold"),
            (lambda r: r['has_acc_idx'] and r['idx_sum'] >= 15, "acc+sum>=15"),
            (lambda r: r['has_gold_idx'] and r.get('prev_true_r2_sym') == 'steal', "gold+prev_steal"),
        ]:
            strategies_acc.append(evaluate_strategy(valid,
                lambda r, g=g, ic=idx_cond: r['gap_acc'] >= g and ic(r),
                f"gap_acc>={g}+{idx_label}", target_acc))

    print_results(strategies_acc, "ACC ONLY")

    # ─────────────────────────────────────────────
    # SECTION 7: Strategy sweep — SPN only
    # ─────────────────────────────────────────────
    strategies_spn = []
    target_spn = lambda r: r['vt_type'] == 'SPN'

    for g in gap_thresholds:
        strategies_spn.append(evaluate_strategy(valid,
            lambda r, g=g: r['gap_spn'] >= g, f"gap_spn>={g}", target_spn))

        for idx_cond, idx_label in [
            (lambda r: r['has_spn_idx'], "has_spn_idx"),
            (lambda r: r['spn_idx_count'] >= 2, "spn_x2"),
            (lambda r: r['has_gold_idx'], "has_gold"),
            (lambda r: r['has_steal_idx'], "has_steal"),
            (lambda r: r['idx_sum'] >= 15, "sum>=15"),
            (lambda r: r['idx_sum'] >= 18, "sum>=18"),
            (lambda r: r['no_pair'], "no_pair"),
            (lambda r: r['all_same_parity'], "same_parity"),
            (lambda r: r['idx_spread'] >= 5, "spread>=5"),
            (lambda r: r.get('prev_true_r2_sym') == 'steal', "prev_r2_steal"),
            (lambda r: r.get('prev_idx_sum', 0) >= 15, "prev_sum>=15"),
            (lambda r: r['true_any_pair'], "true_pair"),
            (lambda r: r['max_dist'] <= 2, "close"),
            (lambda r: r['has_spn_idx'] and r['idx_sum'] >= 15, "spn+sum>=15"),
            (lambda r: r['has_spn_idx'] and r['has_gold_idx'], "spn+gold"),
        ]:
            strategies_spn.append(evaluate_strategy(valid,
                lambda r, g=g, ic=idx_cond: r['gap_spn'] >= g and ic(r),
                f"gap_spn>={g}+{idx_label}", target_spn))

    print_results(strategies_spn, "SPN ONLY")

    # ─────────────────────────────────────────────
    # SECTION 8: Transition analysis (idx N-1 → VT at N)
    # ─────────────────────────────────────────────
    print("\n" + "="*80)
    print("  SECTION 8: Index transitions — does idx delta predict VT?")
    print("="*80)

    for fname in ['delta_r1', 'delta_r2', 'delta_r3', 'delta_sum']:
        all_vals = [r.get(fname) for r in valid if r.get(fname) is not None]
        vt_vals = [r.get(fname) for r in valid if r['vt_type'] and r.get(fname) is not None]
        if all_vals:
            all_mean = sum(all_vals) / len(all_vals)
            vt_mean = sum(vt_vals) / len(vt_vals) if vt_vals else 0
            all_abs = sum(abs(v) for v in all_vals) / len(all_vals)
            vt_abs = sum(abs(v) for v in vt_vals) / len(vt_vals) if vt_vals else 0
            print(f"  {fname:<12s}: all_mean={all_mean:+.2f}  vt_mean={vt_mean:+.2f}  |all|={all_abs:.2f}  |vt|={vt_abs:.2f}")

    # ─────────────────────────────────────────────
    # SECTION 9: Per-account consistency check
    # ─────────────────────────────────────────────
    print("\n" + "="*80)
    print("  SECTION 9: Per-account VT rates and strip consistency")
    print("="*80)

    for acct in ['Ahmed', 'Islam', 'Nick']:
        acct_rows = [r for r in valid if r['acct'] == acct]
        if not acct_rows:
            continue
        n = len(acct_rows)
        vt = sum(1 for r in acct_rows if r['vt_type'])
        acc = sum(1 for r in acct_rows if r['vt_type'] == 'ACC')
        spn = sum(1 for r in acct_rows if r['vt_type'] == 'SPN')
        trips = sum(1 for r in acct_rows if r['is_triple'])
        print(f"  {acct}: {n} spins, {trips} triples ({100*trips/n:.1f}%), {vt} VTs ({100*vt/n:.2f}%): {acc} ACC, {spn} SPN")

    return valid


if __name__ == '__main__':
    rows = load_all()
    rows = compute_features(rows)
    run_analysis(rows)
