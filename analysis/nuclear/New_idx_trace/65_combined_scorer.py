#!/usr/bin/env python3
"""
65_combined_scorer.py - Combine single-spin idx signals with multi-spin
lookback patterns. Measure the combined KPIs.

Layer 1 (existing): Previous spin's idx → score
Layer 2 (new):      10-spin window patterns → bonus/penalty

Goal: push 18.7 bets/VT closer to 10.
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

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
        rows.append(r)

N = len(rows)

def is_vt(row):
    return row['is_triple'] and row['s1'] in (30, 6)

total_vt = sum(1 for r in rows if is_vt(r))

# =====================================================================
# LAYER 1: Single-spin idx scorer (existing engine)
# =====================================================================
def score_layer1(r1, r2, r3):
    score = 0
    if r2 == 7: score += 2
    if r1 == 7: score += 1
    if r2 == 3: score += 1
    if r1 == 3: score += 1
    if r3 == 1: score -= 2
    if r2 == 0: score -= 1
    if r2 == 2: score -= 1
    if r1 == 5: score -= 1
    if r1 == 0: score -= 1
    if r1 == 7 and r2 == 7: score += 2
    if r1 == 7 and r3 == 8: score += 1
    if r2 == 7 and r3 == 8: score += 1
    if r1 == 3 and r2 == 7: score += 1
    if r1 == 3 and r2 == 4: score += 1
    if r1 == 4 and r2 == 4: score -= 2
    if r1 == 7 and r3 == 0: score -= 2
    if r1 == 4 and r3 == 4: score -= 1
    return score


# =====================================================================
# LAYER 2: Multi-spin window patterns (from 64_pre_vt_patterns.py)
# =====================================================================
def score_layer2(rows, i, window=10):
    """Score based on the 10-spin window ending at spin i-1."""
    score = 0
    start = max(0, i - window)
    win = rows[start:i]
    if len(win) < 3:
        return 0

    # --- Signal A: Steal count on reel_1 (VT avg=1.20 vs base 0.64) ---
    # r1 steal = symbol code 4, mapped to various idx values
    # Actually r1=4 maps to steal. Count r1 symbol = steal in window
    steal_r1_count = sum(1 for w in win if w['reel_1'] == 'steal')
    if steal_r1_count >= 2:
        score += 1  # elevated steal on r1

    # --- Signal B: r3=4 count (VT 12.0% vs base 6.4%) ---
    r3_4_count = sum(1 for w in win if w['r3'] == 4)
    if r3_4_count >= 2:
        score += 1  # r3=4 appearing multiple times

    # --- Signal C: r3 bigram (0->8) in window ---
    r3_0_to_8 = 0
    for j in range(1, len(win)):
        if win[j-1]['r3'] == 0 and win[j]['r3'] == 8:
            r3_0_to_8 += 1
    if r3_0_to_8 >= 1:
        score += 1

    # --- Signal D: r3 bigram (8->4) or (4->4) in window ---
    r3_8_to_4 = 0
    r3_4_to_4 = 0
    for j in range(1, len(win)):
        if win[j-1]['r3'] == 8 and win[j]['r3'] == 4:
            r3_8_to_4 += 1
        if win[j-1]['r3'] == 4 and win[j]['r3'] == 4:
            r3_4_to_4 += 1
    if r3_8_to_4 >= 1 or r3_4_to_4 >= 1:
        score += 1

    # --- Signal E: r2=6 (spins) drought < 8 (appeared recently) ---
    r2_6_gap = None
    for lookback in range(1, min(i, 20) + 1):
        if rows[i - lookback]['r2'] == 6:
            r2_6_gap = lookback
            break
    if r2_6_gap is not None and r2_6_gap <= 7:
        score += 1

    # --- Signal F: r3=1 drought > 10 (hasn't appeared = good) ---
    r3_1_gap = None
    for lookback in range(1, min(i, 20) + 1):
        if rows[i - lookback]['r3'] == 1:
            r3_1_gap = lookback
            break
    if r3_1_gap is None or r3_1_gap > 10:
        score += 1  # r3=1 absent = good for VT

    # --- Signal G: r3=1 appeared recently = BAD ---
    if r3_1_gap is not None and r3_1_gap <= 3:
        score -= 2  # r3=1 very recent = dead zone

    # --- Signal H: Tuple (3,6,4) in window ---
    tuple_364 = sum(1 for w in win if w['r1'] == 3 and w['r2'] == 6 and w['r3'] == 4)
    if tuple_364 >= 1:
        score += 1

    # --- Signal I: r3 variety (fewer back-to-back = good) ---
    r3_dups = 0
    for j in range(1, len(win)):
        if win[j]['r3'] == win[j-1]['r3']:
            r3_dups += 1
    if len(win) > 1:
        dup_rate = r3_dups / (len(win) - 1)
        if dup_rate < 0.15:  # less than baseline 24%
            score += 1

    # --- Signal J: r1 bigram (3,3) in window ---
    r1_33 = 0
    for j in range(1, len(win)):
        if win[j-1]['r1'] == 3 and win[j]['r1'] == 3:
            r1_33 += 1
    if r1_33 >= 1:
        score += 1

    return score


# =====================================================================
# COMBINED SCORER
# =====================================================================
def score_combined(rows, i):
    if i == 0:
        return 0, 0, 0
    p = rows[i-1]
    l1 = score_layer1(p['r1'], p['r2'], p['r3'])
    l2 = score_layer2(rows, i)
    return l1, l2, l1 + l2


def tier(score):
    if score >= 4: return 'MAX'
    if score >= 2: return 'BIG'
    if score <= -3: return 'MIN'
    if score <= -1: return 'SMALL'
    return 'NORMAL'


# =====================================================================
# FIRST: Validate Layer 2 signals independently
# =====================================================================
print("=" * 80)
print("  65_COMBINED_SCORER — Layer 1 + Layer 2 combined")
print("=" * 80)
print(f"  {N} spins, {total_vt} VT (acc+spins)")

print("\n\n" + "=" * 80)
print("  LAYER 2 VALIDATION: Window signals alone")
print("=" * 80)

l2_dist = defaultdict(lambda: {'total': 0, 'vt': 0})
for i in range(10, N):
    l2 = score_layer2(rows, i)
    l2_dist[l2]['total'] += 1
    if is_vt(rows[i]):
        l2_dist[l2]['vt'] += 1

print(f"\n  {'L2 Score':>9} {'Spins':>6} {'%':>6} {'VT':>4} {'VT rate':>8}")
print(f"  {'-'*40}")
for s in sorted(l2_dist.keys()):
    d = l2_dist[s]
    pct = 100 * d['total'] / N
    vt_rate = 100 * d['vt'] / d['total'] if d['total'] > 0 else 0
    marker = ' <<<' if vt_rate > 5 else ''
    print(f"  {s:>+9} {d['total']:>6} {pct:>5.1f}% {d['vt']:>4} {vt_rate:>7.1f}%{marker}")


# =====================================================================
# COMBINED: Layer 1 + Layer 2
# =====================================================================
print("\n\n" + "=" * 80)
print("  COMBINED SCORE DISTRIBUTION (L1 + L2)")
print("=" * 80)

combined_dist = defaultdict(lambda: {'total': 0, 'vt': 0})
for i in range(10, N):
    l1, l2, combined = score_combined(rows, i)
    combined_dist[combined]['total'] += 1
    if is_vt(rows[i]):
        combined_dist[combined]['vt'] += 1

print(f"\n  {'Score':>6} {'Spins':>6} {'%':>6} {'VT':>4} {'VT rate':>8} {'Tier':>7}")
print(f"  {'-'*48}")
for s in sorted(combined_dist.keys()):
    d = combined_dist[s]
    pct = 100 * d['total'] / N
    vt_rate = 100 * d['vt'] / d['total'] if d['total'] > 0 else 0
    t = tier(s)
    marker = ' <<<' if vt_rate > 5 else ''
    print(f"  {s:>+6} {d['total']:>6} {pct:>5.1f}% {d['vt']:>4} {vt_rate:>7.1f}% {t:>7}{marker}")


# =====================================================================
# SIMULATION: Different tier thresholds
# =====================================================================
print("\n\n" + "=" * 80)
print("  TIER THRESHOLD SWEEP (combined score)")
print("=" * 80)

print(f"\n  {'Threshold':>10} {'MAX spins':>10} {'VT@MAX':>7} {'Hit rate':>9} {'Bets/VT':>8} {'%VT caught':>11}")
print(f"  {'-'*60}")

for thresh in range(2, 14):
    max_n = 0
    max_vt = 0
    for i in range(10, N):
        _, _, combined = score_combined(rows, i)
        if combined >= thresh:
            max_n += 1
            if is_vt(rows[i]):
                max_vt += 1
    if max_n > 0 and max_vt > 0:
        hit_rate = 100 * max_vt / max_n
        bets_per = max_n / max_vt
        pct_caught = 100 * max_vt / total_vt
        marker = ' <<<' if bets_per <= 12 else ''
        print(f"  {'>=' + str(thresh):>10} {max_n:>10} {max_vt:>7} {hit_rate:>8.1f}% {bets_per:>7.1f} {pct_caught:>10.0f}%{marker}")
    elif max_n > 0:
        print(f"  {'>=' + str(thresh):>10} {max_n:>10} {0:>7} {'0.0%':>9} {'inf':>8} {'0%':>11}")


# =====================================================================
# STRATEGY SIMULATION with combined scorer
# =====================================================================
print("\n\n" + "=" * 80)
print("  STRATEGY COMPARISON: Layer 1 only vs Combined")
print("=" * 80)

# Strategy A: Layer 1 only (current engine)
# Strategy B: Combined (L1+L2), same tier thresholds
# Strategy C: Combined with tighter MAX (>=6)

strategies = {
    'L1 only (current)': lambda rows, i: tier(score_layer1(rows[i-1]['r1'], rows[i-1]['r2'], rows[i-1]['r3'])) if i > 0 else 'NORMAL',
    'Combined (>=4 MAX)': lambda rows, i: tier(score_combined(rows, i)[2]) if i >= 10 else 'NORMAL',
    'Combined tight (>=6 MAX)': None,  # custom
    'Combined ultra (>=8 MAX)': None,  # custom
}

def combined_tight(rows, i):
    if i < 10: return 'NORMAL'
    _, _, c = score_combined(rows, i)
    if c >= 6: return 'MAX'
    if c >= 3: return 'BIG'
    if c <= -3: return 'MIN'
    if c <= -1: return 'SMALL'
    return 'NORMAL'

def combined_ultra(rows, i):
    if i < 10: return 'NORMAL'
    _, _, c = score_combined(rows, i)
    if c >= 8: return 'MAX'
    if c >= 4: return 'BIG'
    if c <= -3: return 'MIN'
    if c <= -1: return 'SMALL'
    return 'NORMAL'

strat_fns = {
    'L1 only (current)': strategies['L1 only (current)'],
    'Combined (>=4 MAX)': strategies['Combined (>=4 MAX)'],
    'Combined tight (>=6 MAX)': combined_tight,
    'Combined ultra (>=8 MAX)': combined_ultra,
}

for name, fn in strat_fns.items():
    tier_counts = Counter()
    tier_vt = defaultdict(int)

    for i in range(10, N):
        t = fn(rows, i)
        tier_counts[t] += 1
        if is_vt(rows[i]):
            tier_vt[t] += 1

    total = sum(tier_counts.values())
    max_n = tier_counts.get('MAX', 0)
    max_vt_n = tier_vt.get('MAX', 0)
    big_n = tier_counts.get('BIG', 0) + max_n
    big_vt_n = tier_vt.get('BIG', 0) + max_vt_n
    min_n = tier_counts.get('MIN', 0)
    min_vt_n = tier_vt.get('MIN', 0)

    print(f"\n  --- {name} ---")
    for t in ['MAX', 'BIG', 'NORMAL', 'SMALL', 'MIN']:
        n = tier_counts.get(t, 0)
        vt = tier_vt.get(t, 0)
        if n > 0:
            print(f"    {t:>7}: {n:>4} spins ({100*n/total:>5.1f}%) | "
                  f"{vt:>2} VT ({100*vt/n:>5.1f}% hit)")

    if max_vt_n > 0:
        print(f"    >>> MAX: {max_vt_n} VT in {max_n} bets = {max_n/max_vt_n:.1f} bets/VT "
              f"({100*max_vt_n/total_vt:.0f}% of VTs caught)")
    if big_vt_n > 0:
        print(f"    >>> BIG+: {big_vt_n} VT in {big_n} bets = {big_n/big_vt_n:.1f} bets/VT "
              f"({100*big_vt_n/total_vt:.0f}% of VTs caught)")
    print(f"    >>> MIN: {min_vt_n} VT wasted at MIN")


# =====================================================================
# DETAILED: Show every VT with combined score
# =====================================================================
print("\n\n" + "=" * 80)
print("  EVERY VT — L1 + L2 + Combined score")
print("=" * 80)
print(f"\n  {'Spin':>6} {'Symbol':>12} {'L1':>4} {'L2':>4} {'Comb':>5} {'Tier(4)':>8} {'Tier(6)':>8} {'Tier(8)':>8}")
print(f"  {'-'*60}")

for i in range(N):
    if is_vt(rows[i]) and i >= 10:
        l1, l2, c = score_combined(rows, i)
        t4 = tier(c)
        t6 = combined_tight(rows, i)
        t8 = combined_ultra(rows, i)
        print(f"  {i:>6} {rows[i]['reel_1']:>12} {l1:>+4} {l2:>+4} {c:>+5} {t4:>8} {t6:>8} {t8:>8}")


print("\n\nDONE")
