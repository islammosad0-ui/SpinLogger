#!/usr/bin/env python3
"""
84_combo_sweep.py — Sweep ALL combos of new validated patterns on top of V2.

For each combo: full KPI table + ACC vs SPN breakdown.
Then rank by best bets/hit at actionable thresholds.
"""

import csv, json, math, sys
from collections import defaultdict, Counter
from itertools import combinations
from pathlib import Path
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =====================================================================
#  Data
# =====================================================================
SYM_CODE = {
    'attack': 3, 'steal': 4, 'shield': 5, 'spins': 6,
    'coin': 1, 'goldSack': 2, 'accumulation': 30, 'potion': 7,
}

def load_ahmed_v2():
    path = ROOT / "data" / "Ahmed" / "spin_history_Ahmed_enriched_v2.csv"
    rows = []
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            if r['r1_idx'] == '' or int(r['r1_idx']) < 0: continue
            rows.append({
                'r1': int(r['r1_idx']), 'r2': int(r['r2_idx']), 'r3': int(r['r3_idx']),
                's1': int(r['s1']), 'is_triple': r['is_triple'] == 'True',
                'reel_1': r['reel_1'],
            })
    return rows

def load_nick_59col():
    path = ROOT / "data" / "Nick" / "spin_history_Nick_2026-04-08 (1).csv"
    rows = []
    with open(path, newline='') as f:
        reader = csv.reader(f)
        next(reader)
        for fields in reader:
            if len(fields) != 59: continue
            if int(fields[0]) < 69879: continue
            r1_idx = fields[53]
            if r1_idx == '' or int(r1_idx) < 0: continue
            rows.append({
                'r1': int(r1_idx), 'r2': int(fields[54]), 'r3': int(fields[55]),
                's1': SYM_CODE.get(fields[5], -1), 'is_triple': fields[10].lower() == 'true',
                'reel_1': fields[5],
            })
    return rows

print("Loading data...")
rows = load_ahmed_v2() + load_nick_59col()
N = len(rows)

def is_vt(r): return r['is_triple'] and r['s1'] in (30, 6)
def is_acc(r): return r['is_triple'] and r['s1'] == 30
def is_spn(r): return r['is_triple'] and r['s1'] == 6

n_vt = sum(1 for r in rows if is_vt(r))
n_acc = sum(1 for r in rows if is_acc(r))
n_spn = sum(1 for r in rows if is_spn(r))
base_rate = n_vt / N
print(f"Total: {N} spins, VT: {n_vt} (ACC={n_acc}, SPN={n_spn}), base={100*base_rate:.2f}%")

def fisher_p(hits, n, base):
    if n == 0 or hits == 0: return 1.0
    return 1 - binom.cdf(hits - 1, n, base)

def wilson_ci(hits, n, z=1.96):
    if n == 0: return (0, 0)
    p = hits / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    m = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (max(0, c-m), min(1, c+m))

# =====================================================================
#  V2 base scorer (exact match of app code)
# =====================================================================
def v2_l1(prev, prev2=None, prev3=None):
    r1, r2, r3 = prev['r1'], prev['r2'], prev['r3']
    s = 0
    if r2 == 7: s += 2
    if r1 == 7: s += 1
    if r2 == 3: s += 1
    if r1 == 3: s += 1
    if r3 == 3: s += 1
    if r3 == 5: s += 1
    if r3 == 8: s += 1
    if r3 == 1: s -= 2
    if r2 == 5: s -= 2
    if r3 == 7: s -= 1
    if r2 == 0: s -= 1
    if r2 == 2: s -= 1
    if r1 == 5: s -= 1
    if r1 == 0: s -= 1
    if r1 == 7 and r2 == 7: s += 2
    if r1 == 7 and r3 == 8: s += 1
    if r2 == 7 and r3 == 8: s += 1
    if r1 == 3 and r2 == 7: s += 1
    if r1 == 3 and r2 == 4: s += 1
    if r1 == 7 and r2 == 3: s += 2
    if r2 == 4 and r3 == 5: s += 1
    if r2 == 3 and r3 == 8: s += 1
    if r1 == 6 and r3 == 5: s += 1
    if r1 == 3 and r3 == 0: s += 1
    if r1 == 4 and r2 == 4: s -= 2
    if r1 == 7 and r3 == 0: s -= 2
    if r1 == 4 and r3 == 4: s -= 1
    if r2 == 5 and r3 == 1: s -= 2
    if r1 == 1 and r3 == 1: s -= 1
    if r1 == 5 and r2 == 5: s -= 1
    if r2 == 3 and r3 == 7: s -= 1
    if r1 == 7 and r3 == 7: s -= 1
    if r2 == 6 and r3 == 1: s -= 1
    if r1 == 6 and r2 == 5: s -= 1
    if r1 == 5 and r3 == 1: s -= 1
    if r1 == 4 and r2 == 4 and r3 == 4: s -= 2
    if r1 == 7 and r2 == 6 and r3 == 0: s -= 1
    if r1 == 6 and r2 == 4 and r3 == 1: s -= 1
    if r1 == 1 and r2 == 1 and r3 == 1: s -= 1
    # Multi-lag + sequences (already in V2)
    if prev2 is not None:
        if prev2['r3'] == r3:           s += 1   # dr3=+0
        if prev2['r3'] == 5 and r3 == 5: s += 1  # r3:(5,5)
        if prev2['r3'] == 8 and r3 == 5: s += 1  # r3:(8,5)
        if prev2['r3'] == 6: s -= 1
        if prev2['r3'] == 2: s -= 1
        if prev2['r1'] == 2: s -= 1
    if prev3 is not None:
        if prev3['r3'] == 4: s += 1
        if prev3['r1'] == 8: s -= 1
    return s

def v2_l2(rows, i, window=10):
    if i < 3: return 0
    start = max(0, i - window)
    win = rows[start:i]; wsize = len(win)
    if wsize < 3: return 0
    score = 0
    if sum(1 for r in win if r['s1'] == 4) >= 2: score += 1
    if sum(1 for r in win if r['r3'] == 4) >= 2: score += 1
    if any(win[j-1]['r3']==0 and win[j]['r3']==8 for j in range(1, wsize)): score += 1
    if any((win[j-1]['r3']==8 and win[j]['r3']==4) or (win[j-1]['r3']==4 and win[j]['r3']==4) for j in range(1, wsize)): score += 1
    r3_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r3'] == 1: r3_1_gap = lb; break
    if r3_1_gap < 0 or r3_1_gap > 10: score += 1
    if 0 < r3_1_gap <= 3: score -= 2
    if any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win): score += 1
    if any(win[j-1]['r1']==3 and win[j]['r1']==3 for j in range(1, wsize)): score -= 1
    return score

# =====================================================================
#  Define NEW pattern bonus functions (not in V2 yet)
# =====================================================================
# Each returns +1 if the pattern fires for spin i, else 0

def pat_bb_r1(rows, i):
    """Back-to-back same r1 (5/5 CV, 1.5x)"""
    if i < 2: return 0
    return 1 if rows[i-2]['r1'] == rows[i-1]['r1'] else 0

def pat_r1_seq_3_7(rows, i):
    """r1 sequence (3,7): prev-prev r1=3, prev r1=7 (4/5 CV, 2.1x)"""
    if i < 2: return 0
    return 1 if rows[i-2]['r1'] == 3 and rows[i-1]['r1'] == 7 else 0

def pat_sum13_15(rows, i):
    """prev r1+r3=15 (4/5 CV, 1.9x)"""
    if i < 1: return 0
    return 1 if rows[i-1]['r1'] + rows[i-1]['r3'] == 15 else 0

def pat_sum123_15(rows, i):
    """prev r1+r2+r3=15 (4/5 CV, 2.9x)"""
    if i < 1: return 0
    p = rows[i-1]
    return 1 if p['r1'] + p['r2'] + p['r3'] == 15 else 0

def pat_xr_r1r2_33(rows, i):
    """Cross-reel: prev-prev r1=3, prev r2=3 (4/5 CV, 2.4x)"""
    if i < 2: return 0
    return 1 if rows[i-2]['r1'] == 3 and rows[i-1]['r2'] == 3 else 0

def pat_xr_r2r3_78(rows, i):
    """Cross-reel: prev-prev r2=7, prev r3=8 (4/5 CV, 3.3x)"""
    if i < 2: return 0
    return 1 if rows[i-2]['r2'] == 7 and rows[i-1]['r3'] == 8 else 0

# Dead-zone sum patterns (0 hits)
def pat_sum13_8_dead(rows, i):
    """prev r1+r3=8 → 0/159 dead (5/5 CV)"""
    if i < 1: return 0
    return -1 if rows[i-1]['r1'] + rows[i-1]['r3'] == 8 else 0

def pat_sum13_14_dead(rows, i):
    """prev r1+r3=14 → 0/57 dead (5/5 CV)"""
    if i < 1: return 0
    return -1 if rows[i-1]['r1'] + rows[i-1]['r3'] == 14 else 0

def pat_sum123_10_dead(rows, i):
    """prev r1+r2+r3=10 → 0/99 dead (5/5 CV)"""
    if i < 1: return 0
    p = rows[i-1]
    return -1 if p['r1'] + p['r2'] + p['r3'] == 10 else 0

def pat_sum123_12_dead(rows, i):
    """prev r1+r2+r3=12 → 0/193 dead (5/5 CV)"""
    if i < 1: return 0
    p = rows[i-1]
    return -1 if p['r1'] + p['r2'] + p['r3'] == 12 else 0

# All new patterns with labels
NEW_PATTERNS = [
    ("A: bb_r1",       pat_bb_r1,          "+1", "5/5 CV, 1.5x"),
    ("B: r1:(3,7)",    pat_r1_seq_3_7,     "+1", "4/5 CV, 2.1x"),
    ("C: sum13=15",    pat_sum13_15,       "+1", "4/5 CV, 1.9x"),
    ("D: sum123=15",   pat_sum123_15,      "+1", "4/5 CV, 2.9x"),
    ("E: xr1r2(3,3)",  pat_xr_r1r2_33,     "+1", "4/5 CV, 2.4x"),
    ("F: xr2r3(7,8)",  pat_xr_r2r3_78,     "+1", "4/5 CV, 3.3x"),
    ("G: sum13=8 dead", pat_sum13_8_dead,   "-1", "0/159 dead, 5/5 CV"),
    ("H: sum13=14 dead", pat_sum13_14_dead, "-1", "0/57 dead, 5/5 CV"),
    ("I: sum123=10 dead", pat_sum123_10_dead,"-1", "0/99 dead, 5/5 CV"),
    ("J: sum123=12 dead", pat_sum123_12_dead,"-1", "0/193 dead, 5/5 CV"),
]

# =====================================================================
#  Simulation engine
# =====================================================================
THRESHOLDS = [
    ('>=2 (BAL)',   2),
    ('>=4',         4),
    ('>=6 (ULT)',   6),
    ('>=8 (SNP)',   8),
    ('>=10',       10),
    ('>=12',       12),
]

def run_sim(rows, active_patterns):
    """Run V2 + active_patterns combo. Return full results."""
    scores = [0]*N
    for i in range(1, N):
        prev = rows[i-1]
        prev2 = rows[i-2] if i >= 2 else None
        prev3 = rows[i-3] if i >= 3 else None
        s = v2_l1(prev, prev2, prev3) + v2_l2(rows, i)
        # Add new pattern bonuses
        for _, fn, _, _ in active_patterns:
            s += fn(rows, i)
        scores[i] = s

    results = {}
    for name, thresh in THRESHOLDS:
        bets = catches = 0
        acc_c = spn_c = 0
        for i in range(1, N):
            if scores[i] >= thresh:
                bets += 1
                if is_vt(rows[i]):
                    catches += 1
                    if is_acc(rows[i]): acc_c += 1
                    if is_spn(rows[i]): spn_c += 1
        cr = catches/n_vt if n_vt else 0
        prec = catches/bets if bets else 0
        bph = bets/catches if catches else float('inf')
        lift = prec/base_rate if base_rate else 0
        pval = fisher_p(catches, bets, base_rate)
        results[name] = {
            'bets': bets, 'catches': catches, 'acc': acc_c, 'spn': spn_c,
            'cr': cr, 'prec': prec, 'bph': bph, 'lift': lift, 'pval': pval,
        }
    return results

# =====================================================================
#  V1 baseline for reference
# =====================================================================
def v1_score(rows, i):
    if i < 1: return 0
    prev = rows[i-1]
    r1, r2, r3 = prev['r1'], prev['r2'], prev['r3']
    s = 0
    if r2 == 7: s += 2
    if r1 == 7: s += 1
    if r2 == 3: s += 1
    if r1 == 3: s += 1
    if r3 == 1: s -= 2
    if r2 == 0: s -= 1
    if r2 == 2: s -= 1
    if r1 == 5: s -= 1
    if r1 == 0: s -= 1
    if r1 == 7 and r2 == 7: s += 2
    if r1 == 7 and r3 == 8: s += 1
    if r2 == 7 and r3 == 8: s += 1
    if r1 == 3 and r2 == 7: s += 1
    if r1 == 3 and r2 == 4: s += 1
    if r1 == 4 and r2 == 4: s -= 2
    if r1 == 7 and r3 == 0: s -= 2
    if r1 == 4 and r3 == 4: s -= 1
    # V1 L2
    if i < 3: return s
    start = max(0, i-10); win = rows[start:i]; wsize = len(win)
    if wsize < 3: return s
    l2 = 0
    if sum(1 for r in win if r['s1']==4) >= 2: l2 += 1
    if sum(1 for r in win if r['r3']==4) >= 2: l2 += 1
    if any(win[j-1]['r3']==0 and win[j]['r3']==8 for j in range(1,wsize)): l2 += 1
    if any((win[j-1]['r3']==8 and win[j]['r3']==4) or (win[j-1]['r3']==4 and win[j]['r3']==4) for j in range(1,wsize)): l2 += 1
    r2_6g = -1
    for lb in range(1,wsize+1):
        if win[-lb]['r2']==6: r2_6g = lb; break
    if 0 < r2_6g <= 7: l2 += 1
    r3_1g = -1
    for lb in range(1,wsize+1):
        if win[-lb]['r3']==1: r3_1g = lb; break
    if r3_1g < 0 or r3_1g > 10: l2 += 1
    if 0 < r3_1g <= 3: l2 -= 2
    if any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win): l2 += 1
    if wsize > 1:
        dups = sum(1 for j in range(1,wsize) if win[j]['r3']==win[j-1]['r3'])
        if dups/(wsize-1) < 0.15: l2 += 1
    if any(win[j-1]['r1']==3 and win[j]['r1']==3 for j in range(1,wsize)): l2 += 1
    return s + l2

# =====================================================================
#  Run V1, V2 base, and all combos
# =====================================================================
print(f"\n{'='*110}")
print("  V1 BASELINE")
print('='*110)

v1_results = {}
for name, thresh in THRESHOLDS:
    bets = catches = acc_c = spn_c = 0
    for i in range(1, N):
        if v1_score(rows, i) >= thresh:
            bets += 1
            if is_vt(rows[i]):
                catches += 1
                if is_acc(rows[i]): acc_c += 1
                if is_spn(rows[i]): spn_c += 1
    cr = catches/n_vt if n_vt else 0
    prec = catches/bets if bets else 0
    bph = bets/catches if catches else float('inf')
    lift = prec/base_rate if base_rate else 0
    pval = fisher_p(catches, bets, base_rate)
    v1_results[name] = {'bets': bets, 'catches': catches, 'acc': acc_c, 'spn': spn_c,
                         'cr': cr, 'prec': prec, 'bph': bph, 'lift': lift, 'pval': pval}

print(f"\n  {'Thresh':>12} {'Bets':>5} {'Cat':>4} {'ACC':>4} {'SPN':>4} {'CatR':>6} {'Prec':>7} {'B/H':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*75}")
for name, _ in THRESHOLDS:
    r = v1_results[name]
    bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
    print(f"  {name:>12} {r['bets']:>5} {r['catches']:>4} {r['acc']:>4} {r['spn']:>4} "
          f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} {r['lift']:>4.1f}x {r['pval']:>8.4f}")

# V2 base (no new patterns)
print(f"\n{'='*110}")
print("  V2 BASE (current app code)")
print('='*110)

v2_base = run_sim(rows, [])
print(f"\n  {'Thresh':>12} {'Bets':>5} {'Cat':>4} {'ACC':>4} {'SPN':>4} {'CatR':>6} {'Prec':>7} {'B/H':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*75}")
for name, _ in THRESHOLDS:
    r = v2_base[name]
    bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
    print(f"  {name:>12} {r['bets']:>5} {r['catches']:>4} {r['acc']:>4} {r['spn']:>4} "
          f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} {r['lift']:>4.1f}x {r['pval']:>8.4f}")

# =====================================================================
#  Sweep ALL combos of new patterns (2^10 = 1024)
# =====================================================================
print(f"\n{'='*110}")
print(f"  COMBO SWEEP: {len(NEW_PATTERNS)} new patterns = {2**len(NEW_PATTERNS)} combos")
print('='*110)

print(f"\n  Available patterns:")
for i, (label, _, weight, stats) in enumerate(NEW_PATTERNS):
    print(f"    {label:>22} {weight:>3}  ({stats})")

# Run all combos
combo_results = []
n_pats = len(NEW_PATTERNS)
for mask in range(0, 2**n_pats):
    active = [NEW_PATTERNS[j] for j in range(n_pats) if mask & (1 << j)]
    if not active:
        continue  # skip empty (that's V2 base)
    res = run_sim(rows, active)
    tag = '+'.join(chr(65+j) for j in range(n_pats) if mask & (1 << j))
    combo_results.append((tag, active, res))

# Sort by bets/hit at >=10
combo_results.sort(key=lambda x: x[2].get('>=10', {}).get('bph', 9999))

# Print top 30 combos at >=10
print(f"\n  TOP 30 COMBOS by B/H at >=10:")
print(f"  {'#':>3} {'Combo':>30} {'Bets':>5} {'Cat':>4} {'ACC':>4} {'SPN':>4} {'CatR':>6} {'Prec':>7} {'B/H':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*95}")

# V2 base first
r = v2_base['>=10']
bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
print(f"  {'':>3} {'V2 BASE':>30} {r['bets']:>5} {r['catches']:>4} {r['acc']:>4} {r['spn']:>4} "
      f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} {r['lift']:>4.1f}x {r['pval']:>8.4f}")

for rank, (tag, active, res) in enumerate(combo_results[:30], 1):
    r = res['>=10']
    bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
    print(f"  {rank:>3} {tag:>30} {r['bets']:>5} {r['catches']:>4} {r['acc']:>4} {r['spn']:>4} "
          f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} {r['lift']:>4.1f}x {r['pval']:>8.4f}")

# Same for >=8
combo_results_8 = sorted(combo_results, key=lambda x: x[2].get('>=8 (SNP)', {}).get('bph', 9999))
print(f"\n  TOP 15 COMBOS by B/H at >=8 (SNP):")
print(f"  {'#':>3} {'Combo':>30} {'Bets':>5} {'Cat':>4} {'ACC':>4} {'SPN':>4} {'CatR':>6} {'Prec':>7} {'B/H':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*95}")
r = v2_base['>=8 (SNP)']
bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
print(f"  {'':>3} {'V2 BASE':>30} {r['bets']:>5} {r['catches']:>4} {r['acc']:>4} {r['spn']:>4} "
      f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} {r['lift']:>4.1f}x {r['pval']:>8.4f}")
for rank, (tag, active, res) in enumerate(combo_results_8[:15], 1):
    r = res['>=8 (SNP)']
    bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
    print(f"  {rank:>3} {tag:>30} {r['bets']:>5} {r['catches']:>4} {r['acc']:>4} {r['spn']:>4} "
          f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} {r['lift']:>4.1f}x {r['pval']:>8.4f}")

# Same for >=12
combo_results_12 = sorted(combo_results, key=lambda x: x[2].get('>=12', {}).get('bph', 9999))
print(f"\n  TOP 15 COMBOS by B/H at >=12:")
print(f"  {'#':>3} {'Combo':>30} {'Bets':>5} {'Cat':>4} {'ACC':>4} {'SPN':>4} {'CatR':>6} {'Prec':>7} {'B/H':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*95}")
r = v2_base['>=12']
bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
print(f"  {'':>3} {'V2 BASE':>30} {r['bets']:>5} {r['catches']:>4} {r['acc']:>4} {r['spn']:>4} "
      f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} {r['lift']:>4.1f}x {r['pval']:>8.4f}")
for rank, (tag, active, res) in enumerate(combo_results_12[:15], 1):
    r = res['>=12']
    bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
    print(f"  {rank:>3} {tag:>30} {r['bets']:>5} {r['catches']:>4} {r['acc']:>4} {r['spn']:>4} "
          f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} {r['lift']:>4.1f}x {r['pval']:>8.4f}")

# =====================================================================
#  Full KPI for the BEST combo at >=10
# =====================================================================
best_tag, best_active, best_res = combo_results[0]
print(f"\n{'='*110}")
print(f"  BEST COMBO AT >=10: V2 + {best_tag}")
print(f"  Patterns: {', '.join(p[0] for p in best_active)}")
print('='*110)

print(f"\n  {'Thresh':>12} {'Bets':>5} {'Cat':>4} {'ACC':>4} {'SPN':>4} {'CatR':>6} {'Prec':>7} {'B/H':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*75}")
for name, _ in THRESHOLDS:
    r = best_res[name]
    bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
    print(f"  {name:>12} {r['bets']:>5} {r['catches']:>4} {r['acc']:>4} {r['spn']:>4} "
          f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} {r['lift']:>4.1f}x {r['pval']:>8.4f}")

# Compare V1 vs V2 base vs best combo
print(f"\n  COMPARISON at >=10:")
v1r = v1_results['>=10']
v2r = v2_base['>=10']
br = best_res['>=10']
print(f"    V1:         B/H={v1r['bph']:.1f}, catches={v1r['catches']} (ACC={v1r['acc']}, SPN={v1r['spn']}), prec={100*v1r['prec']:.1f}%")
print(f"    V2 base:    B/H={v2r['bph']:.1f}, catches={v2r['catches']} (ACC={v2r['acc']}, SPN={v2r['spn']}), prec={100*v2r['prec']:.1f}%")
print(f"    V2+{best_tag}: B/H={br['bph']:.1f}, catches={br['catches']} (ACC={br['acc']}, SPN={br['spn']}), prec={100*br['prec']:.1f}%")

print("\nDONE")
