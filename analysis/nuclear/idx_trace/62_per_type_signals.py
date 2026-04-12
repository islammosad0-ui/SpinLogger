#!/usr/bin/env python3
"""
62_per_type_signals.py - Per-triple-type idx signal analysis.
For each triple type, find the best individual idx signals and pair signals.
Uses temporal 5-fold CV to validate.
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path
import math

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_F = ROOT / "data" / "Ahmed" / "spin_history_Ahmed_enriched_v2.csv"

rows = []
with open(CSV_F, newline='') as f:
    for r in csv.DictReader(f):
        r['r1'] = int(r['r1_idx'])
        r['r2'] = int(r['r2_idx'])
        r['r3'] = int(r['r3_idx'])
        r['s1'] = int(r['s1'])
        r['is_triple'] = r['is_triple'] == 'True'
        r['reel_1'] = r['reel_1']
        r['sn'] = int(r['sn'])
        rows.append(r)

N = len(rows)

# Triple types we care about (with raw codes)
TRIPLE_TYPES = {
    'accumulation': 30,
    'spins': 6,
    'shield': 5,
    'steal': 4,
    'attack': 3,
    'coin': 1,
    'goldSack': 2,
}

# Also define combo groups
COMBO_GROUPS = {
    'acc+spins': [30, 6],       # user's primary target
    'shield+spins': [5, 6],     # old target for reference
    'any_valuable': [30, 6, 5], # broader
}

print("=" * 90)
print("  62_PER_TYPE_SIGNALS — Per-triple-type idx signal analysis (1,107 spins)")
print("=" * 90)

# =====================================================================
# Temporal 5-fold CV helper
# =====================================================================
def temporal_cv(rows, condition_fn, target_fn, n_folds=5):
    """
    condition_fn(prev_row) -> bool  (does previous spin match this signal?)
    target_fn(row) -> bool          (is this spin a hit?)
    Returns: (overall_rate, base_rate, lift_pp, cv_pass_count, n_signal, n_hits)
    """
    fold_size = len(rows) // n_folds
    fold_lifts = []

    total_signal = 0
    total_hits = 0
    total_base_signal = 0
    total_base_hits = 0

    for fold in range(n_folds):
        start = fold * fold_size
        end = start + fold_size if fold < n_folds - 1 else len(rows)

        sig_n = 0
        sig_hits = 0
        base_n = 0
        base_hits = 0

        for i in range(max(start, 1), end):
            is_hit = target_fn(rows[i])
            if condition_fn(rows[i-1]):
                sig_n += 1
                if is_hit:
                    sig_hits += 1
            base_n += 1
            if is_hit:
                base_hits += 1

        total_signal += sig_n
        total_hits += sig_hits
        total_base_signal += base_n
        total_base_hits += base_hits

        if sig_n >= 5:  # minimum sample
            sig_rate = sig_hits / sig_n
            base_rate = base_hits / base_n if base_n > 0 else 0
            fold_lifts.append(sig_rate - base_rate)
        else:
            fold_lifts.append(None)

    # Overall stats
    if total_signal == 0:
        return None

    overall_rate = total_hits / total_signal
    base_rate = total_base_hits / total_base_signal if total_base_signal > 0 else 0
    lift_pp = (overall_rate - base_rate) * 100

    # CV pass: fold has positive lift (for positive signals) or negative (for negative)
    direction = 1 if lift_pp >= 0 else -1
    cv_pass = sum(1 for l in fold_lifts if l is not None and l * direction > 0)

    return {
        'rate': overall_rate,
        'base': base_rate,
        'lift_pp': lift_pp,
        'cv': cv_pass,
        'n': total_signal,
        'hits': total_hits,
    }


# =====================================================================
# ANALYSIS: Individual idx signals for each triple type
# =====================================================================

def analyze_type(type_name, target_codes, rows):
    """Analyze all individual and pair signals for a given triple target."""

    def is_target(row):
        return row['is_triple'] and row['s1'] in target_codes

    # Count targets
    n_target = sum(1 for r in rows if is_target(r))
    base_rate = n_target / N

    print(f"\n{'='*80}")
    print(f"  {type_name.upper()} — {n_target} hits in {N} spins ({100*base_rate:.2f}%, 1 per {N/max(n_target,1):.1f})")
    print(f"{'='*80}")

    # --- Individual idx signals ---
    print(f"\n  Individual idx signals (prev spin):")
    print(f"  {'Signal':>12} {'N':>5} {'Hits':>5} {'Rate':>7} {'Base':>7} {'Lift':>8} {'CV':>4}")
    print(f"  {'-'*55}")

    results = []
    for reel, reel_name in [(1, 'r1'), (2, 'r2'), (3, 'r3')]:
        for idx_val in range(9):
            def cond(prev, rv=reel_name, iv=idx_val):
                return prev[rv] == iv

            res = temporal_cv(rows, cond, is_target)
            if res and res['n'] >= 20:
                results.append((reel_name, idx_val, res))

    # Sort by absolute lift
    results.sort(key=lambda x: abs(x[2]['lift_pp']), reverse=True)

    good_signals = []
    for reel_name, idx_val, res in results:
        marker = ''
        if res['cv'] >= 4 and res['lift_pp'] > 0:
            marker = ' <<<'
            good_signals.append((reel_name, idx_val, res, '+'))
        elif res['cv'] >= 4 and res['lift_pp'] < -base_rate*50:  # significant negative
            marker = ' xxx'
            good_signals.append((reel_name, idx_val, res, '-'))
        elif res['hits'] == 0 and res['n'] >= 50:
            marker = ' DEAD'
            good_signals.append((reel_name, idx_val, res, '-'))

        print(f"  {reel_name}={idx_val:>2}     {res['n']:>5} {res['hits']:>5} "
              f"{100*res['rate']:>6.1f}% {100*res['base']:>6.2f}% "
              f"{res['lift_pp']:>+7.2f}pp {res['cv']}/5{marker}")

    # --- Pair signals ---
    print(f"\n  Pair signals (prev spin):")
    print(f"  {'Signal':>18} {'N':>5} {'Hits':>5} {'Rate':>7} {'Base':>7} {'Lift':>8} {'CV':>4}")
    print(f"  {'-'*60}")

    pair_results = []
    for r_a, name_a in [(1, 'r1'), (2, 'r2'), (3, 'r3')]:
        for r_b, name_b in [(1, 'r1'), (2, 'r2'), (3, 'r3')]:
            if r_a >= r_b:
                continue
            for va in range(9):
                for vb in range(9):
                    def cond(prev, na=name_a, nb=name_b, a=va, b=vb):
                        return prev[na] == a and prev[nb] == b

                    res = temporal_cv(rows, cond, is_target)
                    if res and res['n'] >= 20:
                        pair_results.append((f"{name_a}={va},{name_b}={vb}", res))

    # Sort by absolute lift, show top positive and negative
    pair_results.sort(key=lambda x: x[1]['lift_pp'], reverse=True)

    good_pairs = []

    # Top positive pairs
    print(f"\n  Top POSITIVE pairs:")
    shown = 0
    for label, res in pair_results:
        if res['cv'] >= 3 and res['lift_pp'] > 0 and res['hits'] >= 2:
            marker = ' <<<' if res['cv'] >= 4 else ''
            print(f"  {label:>18} {res['n']:>5} {res['hits']:>5} "
                  f"{100*res['rate']:>6.1f}% {100*res['base']:>6.2f}% "
                  f"{res['lift_pp']:>+7.2f}pp {res['cv']}/5{marker}")
            if res['cv'] >= 4:
                good_pairs.append((label, res, '+'))
            shown += 1
            if shown >= 15:
                break

    # Top negative (0-hit) pairs
    print(f"\n  Top NEGATIVE / dead-zone pairs:")
    shown = 0
    for label, res in reversed(pair_results):
        if res['hits'] == 0 and res['n'] >= 30:
            print(f"  {label:>18} {res['n']:>5} {res['hits']:>5} "
                  f"{100*res['rate']:>6.1f}% {100*res['base']:>6.2f}% "
                  f"{res['lift_pp']:>+7.2f}pp {res['cv']}/5  DEAD")
            good_pairs.append((label, res, '-'))
            shown += 1
            if shown >= 10:
                break

    # --- Anti-clustering check ---
    print(f"\n  Anti-clustering check (does a {type_name} predict fewer {type_name} soon?):")
    for gap in [1, 2, 3, 5, 7]:
        hits_after = 0
        total_after = 0
        for i in range(N - gap):
            if is_target(rows[i]):
                total_after += 1
                if is_target(rows[i + gap]):
                    hits_after += 1
        if total_after > 0:
            rate = hits_after / total_after
            print(f"    Gap {gap}: {hits_after}/{total_after} = {100*rate:.1f}% "
                  f"(base {100*base_rate:.2f}%, {'CLUSTER' if rate > base_rate*1.3 else 'anti-cluster' if rate < base_rate*0.7 else 'neutral'})")

    return good_signals, good_pairs


# =====================================================================
# RUN ANALYSIS FOR EACH TYPE
# =====================================================================

all_results = {}

# Individual types
for type_name, code in TRIPLE_TYPES.items():
    signals, pairs = analyze_type(type_name, [code], rows)
    all_results[type_name] = {'signals': signals, 'pairs': pairs}

# Combo groups
for group_name, codes in COMBO_GROUPS.items():
    signals, pairs = analyze_type(group_name, codes, rows)
    all_results[group_name] = {'signals': signals, 'pairs': pairs}


# =====================================================================
# SUMMARY: Best signals per type for HUD
# =====================================================================
print("\n\n" + "#" * 90)
print("#  SUMMARY: Best validated signals per triple type (for HUD implementation)")
print("#" * 90)

for name, data in all_results.items():
    n_pos = sum(1 for s in data['signals'] if s[3] == '+')
    n_neg = sum(1 for s in data['signals'] if s[3] == '-')
    n_pos_pair = sum(1 for p in data['pairs'] if p[2] == '+')
    n_neg_pair = sum(1 for p in data['pairs'] if p[2] == '-')

    print(f"\n  {name.upper()}:")
    print(f"    Positive individual signals: {n_pos}")
    for reel_name, idx_val, res, direction in data['signals']:
        if direction == '+':
            print(f"      {reel_name}={idx_val}: +{res['lift_pp']:.1f}pp, {res['cv']}/5 CV, "
                  f"{res['hits']}/{res['n']} hits ({100*res['rate']:.1f}%)")

    print(f"    Negative individual signals: {n_neg}")
    for reel_name, idx_val, res, direction in data['signals']:
        if direction == '-':
            print(f"      {reel_name}={idx_val}: {res['lift_pp']:+.1f}pp, {res['cv']}/5 CV, "
                  f"{res['hits']}/{res['n']} ({100*res['rate']:.1f}%)")

    if n_pos_pair:
        print(f"    Positive pairs: {n_pos_pair}")
        for label, res, direction in data['pairs']:
            if direction == '+':
                print(f"      ({label}): +{res['lift_pp']:.1f}pp, {res['cv']}/5 CV, "
                      f"{res['hits']}/{res['n']}")

    if n_neg_pair:
        print(f"    Dead-zone pairs: {n_neg_pair}")
        for label, res, direction in data['pairs']:
            if direction == '-':
                print(f"      ({label}): 0/{res['n']} DEAD")

print("\n\nDONE")
