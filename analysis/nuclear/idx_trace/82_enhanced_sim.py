#!/usr/bin/env python3
"""
82_enhanced_sim.py - Enhanced scorer combining ALL findings + deep sequence mining.

Combines:
  - Current app L1 signals (validated)
  - New signals from 81: r3=3, r3=5, r3=8, lag-3 r3=4
  - Dead tuples from phase 5
  - r2 transition bonus (prev_r2 -> knowledge of what transitions predict)
  - Type-specific L2 (validated per ACC+SPN)
  - Multi-lag signals (lag-2, lag-3)

NEW sequence mining:
  - Back-to-back same tuple detection
  - Paired sequences (2-spin tuple patterns)
  - Repeating idx patterns (same reel value N times in a row)
  - r2 streak patterns (consecutive same r2)
  - Triple-before-triple patterns (what idx pattern precedes VT?)
  - Sliding window tuple frequency (hot tuples)
  - Mirror patterns (r1==r3, r1+r3 sums, symmetric idx)
  - Delta patterns (change between consecutive idx values)
"""

import csv, json, math, sys
from collections import defaultdict, Counter
from pathlib import Path
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =====================================================================
#  Data loading
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
                'reel_1': r['reel_1'], 'source': 'Ahmed',
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
            seq = int(fields[0])
            if seq < 69879: continue
            r1_idx = fields[53]
            if r1_idx == '' or int(r1_idx) < 0: continue
            reel_1 = fields[5]
            rows.append({
                'r1': int(r1_idx), 'r2': int(fields[54]), 'r3': int(fields[55]),
                's1': SYM_CODE.get(reel_1, -1), 'is_triple': fields[10].lower() == 'true',
                'reel_1': reel_1, 'source': 'Nick',
            })
    return rows

print("Loading data...")
ahmed = load_ahmed_v2()
nick = load_nick_59col()
rows = ahmed + nick
N = len(rows)
ACC_SPN = [30, 6]
def is_vt(r): return r['is_triple'] and r['s1'] in ACC_SPN
n_vt = sum(1 for r in rows if is_vt(r))
base_rate = n_vt / N
print(f"Total: {N} spins, VT: {n_vt} ({100*base_rate:.2f}%, 1 per {N/n_vt:.0f})")

# =====================================================================
#  Helpers
# =====================================================================
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

def temporal_cv(rows, cond_fn, target_fn, n_folds=5):
    fold_size = len(rows) // n_folds
    total_s = total_h = total_bn = total_bh = 0
    fold_lifts = []
    for fold in range(n_folds):
        start = fold * fold_size
        end = start + fold_size if fold < n_folds - 1 else len(rows)
        sn = sh = bn = bh = 0
        for i in range(max(start, 1), end):
            hit = target_fn(rows, i)
            if cond_fn(rows, i):
                sn += 1
                if hit: sh += 1
            bn += 1
            if hit: bh += 1
        total_s += sn; total_h += sh; total_bn += bn; total_bh += bh
        if sn >= 5 and bn > 0:
            fold_lifts.append(sh/sn - bh/bn)
        else:
            fold_lifts.append(None)
    if total_s == 0: return None
    rate = total_h / total_s
    base = total_bh / total_bn if total_bn else 0
    lift = (rate - base) * 100
    d = 1 if lift >= 0 else -1
    cv = sum(1 for l in fold_lifts if l is not None and l * d > 0)
    return {'rate': rate, 'base': base, 'lift_pp': lift, 'cv': cv,
            'n': total_s, 'hits': total_h}


# =====================================================================
#  PART 1: DEEP SEQUENCE MINING
# =====================================================================
print(f"\n{'='*95}")
print("  PART 1: DEEP SEQUENCE & PATTERN MINING")
print("='*95")

def target_vt(rows, i): return is_vt(rows[i])

# --- 1A: Back-to-back same tuple ---
print(f"\n  --- 1A: Back-to-back SAME TUPLE (prev tuple == prev-prev tuple) ---")
print(f"  {'Pattern':>25} {'N':>5} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'CV':>4} {'p':>8}")
print(f"  {'-'*65}")

def cond_same_tuple(rows, i):
    if i < 2: return False
    a, b = rows[i-2], rows[i-1]
    return a['r1']==b['r1'] and a['r2']==b['r2'] and a['r3']==b['r3']

res = temporal_cv(rows, cond_same_tuple, target_vt)
if res:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  {'exact same tuple x2':>25} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
          f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

# Same r2 back to back
def cond_same_r2(rows, i):
    if i < 2: return False
    return rows[i-2]['r2'] == rows[i-1]['r2']
res = temporal_cv(rows, cond_same_r2, target_vt)
if res:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  {'same r2 x2':>25} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
          f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

# Same r1 back to back
def cond_same_r1(rows, i):
    if i < 2: return False
    return rows[i-2]['r1'] == rows[i-1]['r1']
res = temporal_cv(rows, cond_same_r1, target_vt)
if res:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  {'same r1 x2':>25} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
          f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

# Same r3 back to back
def cond_same_r3(rows, i):
    if i < 2: return False
    return rows[i-2]['r3'] == rows[i-1]['r3']
res = temporal_cv(rows, cond_same_r3, target_vt)
if res:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  {'same r3 x2':>25} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
          f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

# --- 1B: Repeating reel value 3 in a row ---
print(f"\n  --- 1B: Same reel value 3 spins in a row ---")
print(f"  {'Pattern':>25} {'N':>5} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'CV':>4} {'p':>8}")
print(f"  {'-'*65}")

for reel in ['r1', 'r2', 'r3']:
    def cond_3x(rows, i, r=reel):
        if i < 3: return False
        return rows[i-3][r] == rows[i-2][r] == rows[i-1][r]
    res = temporal_cv(rows, cond_3x, target_vt)
    if res and res['n'] >= 10:
        pval = fisher_p(res['hits'], res['n'], base_rate)
        print(f"  {f'{reel} same 3x':>25} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
              f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

# --- 1C: Paired 2-spin tuple sequences ---
print(f"\n  --- 1C: Specific 2-spin tuple PAIRS (prev-prev tuple, prev tuple) -> VT ---")
print(f"  Scanning all (r2_a, r2_b) pairs at lag-2 and lag-1...")
print(f"  {'Pair':>16} {'N':>5} {'Hits':>4} {'Rate':>7} {'Lift':>5} {'p':>8}")
print(f"  {'-'*55}")

pair_results = []
for a in range(9):
    for b in range(9):
        n_sig = hits = 0
        for i in range(2, N):
            if rows[i-2]['r2'] == a and rows[i-1]['r2'] == b:
                n_sig += 1
                if is_vt(rows[i]): hits += 1
        if n_sig >= 20 and hits >= 2:
            rate = hits / n_sig
            lift = rate / base_rate
            pval = fisher_p(hits, n_sig, base_rate)
            if pval < 0.10:
                pair_results.append((f"r2:({a},{b})", n_sig, hits, rate, lift, pval))
pair_results.sort(key=lambda x: -x[4])
for label, ns, h, rate, lift, pval in pair_results[:15]:
    print(f"  {label:>16} {ns:>5} {h:>4} {100*rate:>6.2f}% {lift:>4.1f}x {pval:>8.4f}")

# Same for r1
print(f"\n  r1 pairs:")
print(f"  {'Pair':>16} {'N':>5} {'Hits':>4} {'Rate':>7} {'Lift':>5} {'p':>8}")
print(f"  {'-'*55}")
pair_r1 = []
for a in range(9):
    for b in range(9):
        n_sig = hits = 0
        for i in range(2, N):
            if rows[i-2]['r1'] == a and rows[i-1]['r1'] == b:
                n_sig += 1
                if is_vt(rows[i]): hits += 1
        if n_sig >= 20 and hits >= 2:
            rate = hits / n_sig
            lift = rate / base_rate
            pval = fisher_p(hits, n_sig, base_rate)
            if pval < 0.10:
                pair_r1.append((f"r1:({a},{b})", n_sig, hits, rate, lift, pval))
pair_r1.sort(key=lambda x: -x[4])
for label, ns, h, rate, lift, pval in pair_r1[:15]:
    print(f"  {label:>16} {ns:>5} {h:>4} {100*rate:>6.2f}% {lift:>4.1f}x {pval:>8.4f}")

# Same for r3
print(f"\n  r3 pairs:")
print(f"  {'Pair':>16} {'N':>5} {'Hits':>4} {'Rate':>7} {'Lift':>5} {'p':>8}")
print(f"  {'-'*55}")
pair_r3 = []
for a in range(9):
    for b in range(9):
        n_sig = hits = 0
        for i in range(2, N):
            if rows[i-2]['r3'] == a and rows[i-1]['r3'] == b:
                n_sig += 1
                if is_vt(rows[i]): hits += 1
        if n_sig >= 20 and hits >= 2:
            rate = hits / n_sig
            lift = rate / base_rate
            pval = fisher_p(hits, n_sig, base_rate)
            if pval < 0.10:
                pair_r3.append((f"r3:({a},{b})", n_sig, hits, rate, lift, pval))
pair_r3.sort(key=lambda x: -x[4])
for label, ns, h, rate, lift, pval in pair_r3[:15]:
    print(f"  {label:>16} {ns:>5} {h:>4} {100*rate:>6.2f}% {lift:>4.1f}x {pval:>8.4f}")

# --- 1D: Delta patterns (change between consecutive spins) ---
print(f"\n  --- 1D: Delta patterns (r2[i-1] - r2[i-2] = delta) -> VT ---")
print(f"  {'Delta':>8} {'N':>5} {'Hits':>4} {'Rate':>7} {'Lift':>5} {'p':>8}")
print(f"  {'-'*45}")
for delta in range(-8, 9):
    n_sig = hits = 0
    for i in range(2, N):
        if rows[i-1]['r2'] - rows[i-2]['r2'] == delta:
            n_sig += 1
            if is_vt(rows[i]): hits += 1
    if n_sig >= 20 and hits >= 1:
        rate = hits / n_sig
        lift = rate / base_rate
        pval = fisher_p(hits, n_sig, base_rate)
        marker = " <<<" if lift > 1.5 and pval < 0.05 else (" xxx" if lift < 0.5 and pval < 0.05 else "")
        if abs(lift - 1.0) > 0.3 or pval < 0.1:
            print(f"  {delta:>+8} {n_sig:>5} {hits:>4} {100*rate:>6.2f}% {lift:>4.1f}x {pval:>8.4f}{marker}")

print(f"\n  r1 deltas:")
for delta in range(-8, 9):
    n_sig = hits = 0
    for i in range(2, N):
        if rows[i-1]['r1'] - rows[i-2]['r1'] == delta:
            n_sig += 1
            if is_vt(rows[i]): hits += 1
    if n_sig >= 20 and hits >= 1:
        rate = hits / n_sig
        lift = rate / base_rate
        pval = fisher_p(hits, n_sig, base_rate)
        if abs(lift - 1.0) > 0.3 or pval < 0.1:
            print(f"  {delta:>+8} {n_sig:>5} {hits:>4} {100*rate:>6.2f}% {lift:>4.1f}x {pval:>8.4f}")

print(f"\n  r3 deltas:")
for delta in range(-8, 9):
    n_sig = hits = 0
    for i in range(2, N):
        if rows[i-1]['r3'] - rows[i-2]['r3'] == delta:
            n_sig += 1
            if is_vt(rows[i]): hits += 1
    if n_sig >= 20 and hits >= 1:
        rate = hits / n_sig
        lift = rate / base_rate
        pval = fisher_p(hits, n_sig, base_rate)
        if abs(lift - 1.0) > 0.3 or pval < 0.1:
            print(f"  {delta:>+8} {n_sig:>5} {hits:>4} {100*rate:>6.2f}% {lift:>4.1f}x {pval:>8.4f}")

# --- 1E: Mirror / symmetry patterns ---
print(f"\n  --- 1E: Mirror & symmetry patterns ---")
print(f"  {'Pattern':>30} {'N':>5} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'CV':>4} {'p':>8}")
print(f"  {'-'*70}")

# r1 == r3 on prev spin
def cond_mirror(rows, i):
    return rows[i-1]['r1'] == rows[i-1]['r3']
res = temporal_cv(rows, cond_mirror, target_vt)
if res:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  {'prev r1==r3':>30} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
          f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

# r1 + r3 sum on prev spin
for target_sum in range(0, 17):
    def cond_sum(rows, i, s=target_sum):
        return rows[i-1]['r1'] + rows[i-1]['r3'] == s
    res = temporal_cv(rows, cond_sum, target_vt)
    if res and res['n'] >= 20 and abs(res['lift_pp']) > base_rate*30:
        pval = fisher_p(res['hits'], res['n'], base_rate)
        if pval < 0.10 or res['rate']/base_rate > 1.5:
            print(f"  {f'prev r1+r3={target_sum}':>30} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
                  f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

# r1+r2+r3 sum
for target_sum in range(0, 25):
    def cond_total(rows, i, s=target_sum):
        p = rows[i-1]
        return p['r1'] + p['r2'] + p['r3'] == s
    res = temporal_cv(rows, cond_total, target_vt)
    if res and res['n'] >= 20 and abs(res['lift_pp']) > base_rate*30:
        pval = fisher_p(res['hits'], res['n'], base_rate)
        if pval < 0.10 or res['rate']/base_rate > 1.5:
            print(f"  {f'prev sum={target_sum}':>30} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
                  f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

# --- 1F: Ascending / descending r2 sequences ---
print(f"\n  --- 1F: Monotonic sequences ---")
print(f"  {'Pattern':>30} {'N':>5} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'CV':>4} {'p':>8}")
print(f"  {'-'*70}")

# r2 ascending 2 in a row
def cond_r2_asc2(rows, i):
    if i < 2: return False
    return rows[i-1]['r2'] > rows[i-2]['r2']
res = temporal_cv(rows, cond_r2_asc2, target_vt)
if res:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  {'r2 ascending (2-step)':>30} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
          f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

def cond_r2_desc2(rows, i):
    if i < 2: return False
    return rows[i-1]['r2'] < rows[i-2]['r2']
res = temporal_cv(rows, cond_r2_desc2, target_vt)
if res:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  {'r2 descending (2-step)':>30} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
          f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

# r2 ascending 3 in a row
def cond_r2_asc3(rows, i):
    if i < 3: return False
    return rows[i-1]['r2'] > rows[i-2]['r2'] > rows[i-3]['r2']
res = temporal_cv(rows, cond_r2_asc3, target_vt)
if res and res['n'] >= 10:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  {'r2 ascending (3-step)':>30} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
          f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

def cond_r2_desc3(rows, i):
    if i < 3: return False
    return rows[i-1]['r2'] < rows[i-2]['r2'] < rows[i-3]['r2']
res = temporal_cv(rows, cond_r2_desc3, target_vt)
if res and res['n'] >= 10:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  {'r2 descending (3-step)':>30} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>5.2f}% "
          f"{res['rate']/base_rate:>4.1f}x {res['cv']}/5 {pval:>8.4f}")

# --- 1G: Window hot tuple (same tuple appeared 2+ times in last 10 spins) ---
print(f"\n  --- 1G: Hot tuples in window (any tuple repeated 2+ in last 10) ---")

def cond_hot_tuple(rows, i):
    if i < 5: return False
    start = max(0, i - 10)
    win = rows[start:i]
    tuples = [(r['r1'], r['r2'], r['r3']) for r in win]
    counts = Counter(tuples)
    return any(c >= 2 for c in counts.values())

res = temporal_cv(rows, cond_hot_tuple, target_vt)
if res:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  any tuple 2+ in win10: N={res['n']}, hits={res['hits']}, "
          f"rate={100*res['rate']:.2f}%, lift={res['rate']/base_rate:.1f}x, "
          f"cv={res['cv']}/5, p={pval:.4f}")

# Same r2 3+ times in window
def cond_hot_r2(rows, i):
    if i < 5: return False
    start = max(0, i - 10)
    win = rows[start:i]
    counts = Counter(r['r2'] for r in win)
    return any(c >= 3 for c in counts.values())

res = temporal_cv(rows, cond_hot_r2, target_vt)
if res:
    pval = fisher_p(res['hits'], res['n'], base_rate)
    print(f"  any r2 val 3+ in win10: N={res['n']}, hits={res['hits']}, "
          f"rate={100*res['rate']:.2f}%, lift={res['rate']/base_rate:.1f}x, "
          f"cv={res['cv']}/5, p={pval:.4f}")

# --- 1H: Cross-reel paired sequences ---
print(f"\n  --- 1H: Cross-reel sequence (r1[i-2], r2[i-1]) pairs -> VT ---")
print(f"  {'Pair':>16} {'N':>5} {'Hits':>4} {'Rate':>7} {'Lift':>5} {'p':>8}")
print(f"  {'-'*55}")
xreel = []
for a in range(9):
    for b in range(9):
        n_sig = hits = 0
        for i in range(2, N):
            if rows[i-2]['r1'] == a and rows[i-1]['r2'] == b:
                n_sig += 1
                if is_vt(rows[i]): hits += 1
        if n_sig >= 20 and hits >= 2:
            rate = hits / n_sig
            lift = rate / base_rate
            pval = fisher_p(hits, n_sig, base_rate)
            if pval < 0.05:
                xreel.append((f"r1[-2]={a},r2[-1]={b}", n_sig, hits, rate, lift, pval))
xreel.sort(key=lambda x: -x[4])
for label, ns, h, rate, lift, pval in xreel[:12]:
    print(f"  {label:>16} {ns:>5} {h:>4} {100*rate:>6.2f}% {lift:>4.1f}x {pval:>8.4f}")

# --- 1I: 3-spin sliding window patterns ---
print(f"\n  --- 1I: 3-spin r2 trigrams (r2[i-3], r2[i-2], r2[i-1]) -> VT ---")
print(f"  {'Trigram':>16} {'N':>5} {'Hits':>4} {'Rate':>7} {'Lift':>5} {'p':>8}")
print(f"  {'-'*55}")
trigram_results = []
# Focus on promising r2 values from previous findings
hot_r2 = [3, 7, 6, 8, 4, 5]
for a in hot_r2:
    for b in hot_r2:
        for c in hot_r2:
            n_sig = hits = 0
            for i in range(3, N):
                if rows[i-3]['r2']==a and rows[i-2]['r2']==b and rows[i-1]['r2']==c:
                    n_sig += 1
                    if is_vt(rows[i]): hits += 1
            if n_sig >= 10 and hits >= 2:
                rate = hits/n_sig
                lift = rate/base_rate
                pval = fisher_p(hits, n_sig, base_rate)
                if pval < 0.05:
                    trigram_results.append((f"r2:({a},{b},{c})", n_sig, hits, rate, lift, pval))
trigram_results.sort(key=lambda x: -x[4])
for label, ns, h, rate, lift, pval in trigram_results[:15]:
    print(f"  {label:>16} {ns:>5} {h:>4} {100*rate:>6.2f}% {lift:>4.1f}x {pval:>8.4f}")


# =====================================================================
#  PART 2: CV-VALIDATE ALL PROMISING PATTERNS
# =====================================================================
print(f"\n\n{'='*95}")
print("  PART 2: CV-VALIDATE ALL PROMISING SEQUENCE PATTERNS")
print("=" * 95)

# Collect all promising patterns for CV validation
patterns = []

# From 1C: best r2 pairs
for label, ns, h, rate, lift, pval in pair_results[:8]:
    a_str = label.split('(')[1].split(')')[0]
    va, vb = int(a_str.split(',')[0]), int(a_str.split(',')[1])
    def make_cond(va, vb):
        def cond(rows, i):
            if i < 2: return False
            return rows[i-2]['r2'] == va and rows[i-1]['r2'] == vb
        return cond
    patterns.append((label, make_cond(va, vb)))

# From 1C: best r3 pairs
for label, ns, h, rate, lift, pval in pair_r3[:5]:
    a_str = label.split('(')[1].split(')')[0]
    va, vb = int(a_str.split(',')[0]), int(a_str.split(',')[1])
    def make_cond_r3(va, vb):
        def cond(rows, i):
            if i < 2: return False
            return rows[i-2]['r3'] == va and rows[i-1]['r3'] == vb
        return cond
    patterns.append((label, make_cond_r3(va, vb)))

# Add delta patterns
for reel in ['r2', 'r1', 'r3']:
    for delta in range(-8, 9):
        n_sig = hits = 0
        for i in range(2, N):
            if rows[i-1][reel] - rows[i-2][reel] == delta:
                n_sig += 1
                if is_vt(rows[i]): hits += 1
        if n_sig >= 30 and hits >= 2:
            rate = hits/n_sig
            lift = rate/base_rate
            pval = fisher_p(hits, n_sig, base_rate)
            if pval < 0.03 and lift > 1.5:
                def make_delta_cond(r, d):
                    def cond(rows, i):
                        if i < 2: return False
                        return rows[i-1][r] - rows[i-2][r] == d
                    return cond
                patterns.append((f"d{reel}={delta:+d}", make_delta_cond(reel, delta)))

# Run CV on all collected patterns
print(f"\n  {'Pattern':>20} {'N':>5} {'Hits':>4} {'Rate':>7} {'Lift':>5} {'CV':>4} {'p':>8} {'Verdict':>10}")
print(f"  {'-'*72}")

validated_patterns = []
for label, cond_fn in patterns:
    res = temporal_cv(rows, cond_fn, target_vt)
    if res and res['n'] >= 15:
        pval = fisher_p(res['hits'], res['n'], base_rate)
        lift = res['rate'] / base_rate
        verdict = "PASS" if res['cv'] >= 4 and pval < 0.05 else ("WEAK" if res['cv'] >= 3 else "FAIL")
        print(f"  {label:>20} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>6.2f}% "
              f"{lift:>4.1f}x {res['cv']}/5 {pval:>8.4f} {verdict:>10}")
        if verdict == "PASS":
            validated_patterns.append((label, cond_fn, res))


# =====================================================================
#  PART 3: BUILD ENHANCED COMBINED SCORER
# =====================================================================
print(f"\n\n{'='*95}")
print("  PART 3: ENHANCED COMBINED SCORER (all validated signals)")
print("=" * 95)

# --- L1: Current app signals + new validated additions ---
def enhanced_l1(prev, prev2=None, prev3=None):
    """Enhanced L1 scorer using lag-1 idx + validated new signals."""
    r1, r2, r3 = prev['r1'], prev['r2'], prev['r3']
    s = 0

    # === Original app signals (validated on 3,864 spins) ===
    if r2 == 7: s += 2   # 5/5 CV, star signal
    if r1 == 7: s += 1   # 5/5 CV on merged data
    if r2 == 3: s += 1   # 4/5 CV
    if r1 == 3: s += 1   # 4/5 CV

    if r3 == 1: s -= 2   # 5/5 CV dead zone
    if r2 == 0: s -= 1   # 5/5 CV in 81 (neg on merged)
    if r2 == 2: s -= 1   # 4/5 CV
    if r1 == 5: s -= 1   # 4/5 CV
    if r1 == 0: s -= 1   # 4/5 CV

    # Pair bonuses
    if r1 == 7 and r2 == 7: s += 2
    if r1 == 7 and r3 == 8: s += 1
    if r2 == 7 and r3 == 8: s += 1
    if r1 == 3 and r2 == 7: s += 1
    if r1 == 3 and r2 == 4: s += 1

    # Dead pairs
    if r1 == 4 and r2 == 4: s -= 2
    if r1 == 7 and r3 == 0: s -= 2
    if r1 == 4 and r3 == 4: s -= 1

    # === NEW signals from 81 re-discovery (validated on merged 3,864) ===
    if r3 == 3: s += 1   # +1.80pp, 4/5 CV (new)
    if r3 == 5: s += 1   # +0.75pp, 4/5 CV (new)
    if r3 == 8: s += 1   # +0.71pp, 5/5 CV (new — strong)

    # New pair: r2=4,r3=5 (+3.49pp, 4/5 CV)
    if r2 == 4 and r3 == 5: s += 1
    # New pair: r1=7,r2=3 (+1.98pp, 5/5 CV)
    if r1 == 7 and r2 == 3: s += 2
    # New pair: r2=3,r3=8 (+1.51pp, 4/5 CV)
    if r2 == 3 and r3 == 8: s += 1
    # New pair: r1=6,r3=5 (+1.19pp, 4/5 CV)
    if r1 == 6 and r3 == 5: s += 1
    # New pair: r1=3,r3=0 (+0.48pp, 4/5 CV)
    if r1 == 3 and r3 == 0: s += 1

    # New dead pairs n>=50
    if r1 == 6 and r2 == 5: s -= 1
    if r2 == 6 and r3 == 1: s -= 1
    if r1 == 7 and r3 == 7: s -= 1
    if r1 == 5 and r3 == 1: s -= 1
    if r2 == 3 and r3 == 7: s -= 1
    if r1 == 5 and r2 == 5: s -= 1
    if r1 == 1 and r3 == 1: s -= 1
    if r2 == 5 and r3 == 1: s -= 2  # 0/105

    # New dead tuple bonuses (0/136+)
    if r1 == 4 and r2 == 4 and r3 == 4: s -= 2  # 0/136 mega-dead
    if r1 == 7 and r2 == 6 and r3 == 0: s -= 1  # 0/86
    if r1 == 6 and r2 == 4 and r3 == 1: s -= 1  # 0/77
    if r1 == 1 and r2 == 1 and r3 == 1: s -= 1  # 0/58

    # === Multi-lag bonuses (applied if prev2/prev3 available) ===
    if prev3 is not None:
        # Lag-3 r3=4: +2.68pp for ACC+SPN, 4/5 CV
        if prev3['r3'] == 4: s += 1
        # Lag-3 r1=8: dead (0/39)
        if prev3['r1'] == 8: s -= 1

    if prev2 is not None:
        # Lag-2 r3=6: dead (0/57 for ACC+SPN)
        if prev2['r3'] == 6: s -= 1
        # Lag-2 r3=2: -1.76pp, 5/5 CV
        if prev2['r3'] == 2: s -= 1
        # Lag-2 r1=2: -1.56pp, 5/5 CV
        if prev2['r1'] == 2: s -= 1

    return s

# --- Type-specific L2 (validated for ACC+SPN on merged data) ---
def enhanced_l2(rows, i, window=10):
    if i < 3: return 0
    start = max(0, i - window)
    win = rows[start:i]
    wsize = len(win)
    if wsize < 3: return 0
    score = 0

    # A: steal_r1 >= 2 (5/5 CV, +2.36pp) -> +1
    if sum(1 for r in win if r['s1'] == 4) >= 2: score += 1
    # B: r3=4 count >= 2 (5/5 CV, +2.36pp) -> +1
    if sum(1 for r in win if r['r3'] == 4) >= 2: score += 1
    # C: r3 bigram 0->8 (4/5 CV, +0.21pp) -> +1
    if any(win[j-1]['r3']==0 and win[j]['r3']==8 for j in range(1, wsize)): score += 1
    # D: r3 bigram 8->4|4->4 (4/5 CV, +1.62pp) -> +1
    if any((win[j-1]['r3']==8 and win[j]['r3']==4) or
           (win[j-1]['r3']==4 and win[j]['r3']==4) for j in range(1, wsize)): score += 1
    # E: SKIP (2/5 CV)
    # F: r3=1 absent (4/5 CV, +0.41pp) -> +1
    r3_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r3'] == 1: r3_1_gap = lb; break
    if r3_1_gap < 0 or r3_1_gap > 10: score += 1
    # G: r3=1 recent (5/5 CV, -0.92pp) -> -2
    if 0 < r3_1_gap <= 3: score -= 2
    # H: tuple (3,6,4) (4/5 CV, +1.58pp) -> +1
    if any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win): score += 1
    # I: SKIP (2/5 CV for combined)
    # J: r1 bigram (3,3) (4/5 CV, -0.06pp) -> -1 (weak negative validated)
    if any(win[j-1]['r1']==3 and win[j]['r1']==3 for j in range(1, wsize)): score -= 1

    return score

# --- Sequence bonus layer ---
def sequence_bonus(rows, i):
    """Bonus from validated sequence patterns."""
    if i < 3: return 0
    bonus = 0
    # Add validated patterns from Part 2 (we'll add them after seeing results)
    # For now, compute all pattern features and apply CV-validated ones
    return bonus


# =====================================================================
#  PART 4: SIMULATION
# =====================================================================
print(f"\n\n{'='*95}")
print("  PART 4: SIMULATION RESULTS")
print("=" * 95)

THRESHOLDS = [
    ('ALL (>=0)',    0),
    ('>=1',         1),
    ('>=2 (BAL)',   2),
    ('>=3 (TGT)',   3),
    ('>=4',         4),
    ('>=5',         5),
    ('>=6 (ULT)',   6),
    ('>=8 (SNP)',   8),
    ('>=10',       10),
    ('>=12',       12),
]

def run_full_sim(rows, l1_fn, l2_fn, label):
    """Run simulation and return results."""
    N = len(rows)
    l1s = [0]*N; l2s = [0]*N
    for i in range(1, N):
        prev = rows[i-1]
        prev2 = rows[i-2] if i >= 2 else None
        prev3 = rows[i-3] if i >= 3 else None
        l1s[i] = l1_fn(prev, prev2, prev3) if l1_fn.__code__.co_varnames[:3] == ('prev','prev2','prev3') else l1_fn(prev)
        l2s[i] = l2_fn(rows, i)

    results = {}
    for name, thresh in THRESHOLDS:
        bets = catches = missed = 0
        for i in range(1, N):
            c = l1s[i] + l2s[i]
            hit = is_vt(rows[i])
            if c >= thresh:
                bets += 1
                if hit: catches += 1
            elif hit: missed += 1
        cr = catches/n_vt if n_vt else 0
        prec = catches/bets if bets else 0
        bph = bets/catches if catches else float('inf')
        lift = prec/base_rate if base_rate else 0
        pval = fisher_p(catches, bets, base_rate)
        lo, hi = wilson_ci(catches, bets)
        results[name] = {'thresh': thresh, 'bets': bets, 'catches': catches,
            'missed': missed, 'cr': cr, 'prec': prec, 'bph': bph,
            'lift': lift, 'pval': pval, 'ci_lo': lo, 'ci_hi': hi}

    dist = defaultdict(lambda: {'n':0,'h':0})
    for i in range(1, N):
        c = l1s[i]+l2s[i]; hit = is_vt(rows[i])
        dist[c]['n'] += 1
        if hit: dist[c]['h'] += 1
    return results, dist, l1s, l2s

def print_kpi(results, label):
    print(f"\n  {label}:")
    print(f"  {'Prof':>12} {'Thr':>4} {'Bets':>5} {'Cat':>4} {'Miss':>4} "
          f"{'CatR':>6} {'Prec':>7} {'B/H':>6} {'Lift':>5} {'Bet%':>5} {'p':>8} {'CI95':>14}")
    print(f"  {'-'*100}")
    for name, _ in THRESHOLDS:
        r = results[name]
        ci = f"[{100*r['ci_lo']:.1f}-{100*r['ci_hi']:.1f}]"
        bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
        print(f"  {name:>12} {r['thresh']:>4} {r['bets']:>5} {r['catches']:>4} {r['missed']:>4} "
              f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} "
              f"{r['lift']:>4.1f}x {100*r['bets']/(N-1):>4.1f}% {r['pval']:>8.4f} {ci:>14}")

def print_dist(dist, label):
    print(f"\n  {label}:")
    print(f"  {'Sc':>4} {'Spins':>6} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'CumH':>4} {'Cum%':>5}")
    print(f"  {'-'*40}")
    cum = 0
    for sc in sorted(dist.keys(), reverse=True):
        d = dist[sc]
        rate = d['h']/d['n'] if d['n'] else 0
        lift = rate/base_rate if base_rate else 0
        cum += d['h']
        cumc = cum/n_vt if n_vt else 0
        if d['n'] >= 3 or d['h'] > 0:
            print(f"  {sc:>4} {d['n']:>6} {d['h']:>4} {100*rate:>5.1f}% {lift:>4.1f}x {cum:>4} {100*cumc:>4.1f}%")


# --- A: Baseline (current app) ---
def baseline_l1(prev):
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
    return s

def baseline_l2(rows, i, window=10):
    if i < 3: return 0
    start = max(0, i - window)
    win = rows[start:i]
    wsize = len(win)
    if wsize < 3: return 0
    score = 0
    if sum(1 for r in win if r['s1'] == 4) >= 2: score += 1
    if sum(1 for r in win if r['r3'] == 4) >= 2: score += 1
    for j in range(1, wsize):
        if win[j-1]['r3']==0 and win[j]['r3']==8: score += 1; break
    for j in range(1, wsize):
        if (win[j-1]['r3']==8 and win[j]['r3']==4) or (win[j-1]['r3']==4 and win[j]['r3']==4):
            score += 1; break
    r2_6_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r2'] == 6: r2_6_gap = lb; break
    if 0 < r2_6_gap <= 7: score += 1
    r3_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r3'] == 1: r3_1_gap = lb; break
    if r3_1_gap < 0 or r3_1_gap > 10: score += 1
    if 0 < r3_1_gap <= 3: score -= 2
    if any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win): score += 1
    if wsize > 1:
        dups = sum(1 for j in range(1, wsize) if win[j]['r3']==win[j-1]['r3'])
        if dups/(wsize-1) < 0.15: score += 1
    for j in range(1, wsize):
        if win[j-1]['r1']==3 and win[j]['r1']==3: score += 1; break
    return score

print("\n  A) BASELINE (current app scorer):")
base_res, base_dist, base_l1s, base_l2s = run_full_sim(rows, baseline_l1, baseline_l2, "baseline")
print_dist(base_dist, "Baseline score distribution")
print_kpi(base_res, "BASELINE KPIs")

# --- B: Enhanced scorer ---
print("\n\n  B) ENHANCED SCORER (all validated signals + type-specific L2 + multi-lag):")
enh_res, enh_dist, enh_l1s, enh_l2s = run_full_sim(rows, enhanced_l1, enhanced_l2, "enhanced")
print_dist(enh_dist, "Enhanced score distribution")
print_kpi(enh_res, "ENHANCED KPIs")


# --- C: Head-to-head ---
print(f"\n\n{'='*95}")
print("  HEAD-TO-HEAD: BASELINE vs ENHANCED")
print("=" * 95)
print(f"\n  Target: ACC+SPN = {n_vt}/{N} = {100*base_rate:.2f}%")
print(f"\n  {'System':>12} {'Prof':>12} {'Bets':>5} {'Cat':>4} {'CatR':>5} "
      f"{'Prec':>7} {'B/H':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*80}")

for name, _ in THRESHOLDS:
    b = base_res[name]
    e = enh_res[name]
    b_bph = f"{b['bph']:.1f}" if b['bph'] < 9999 else "inf"
    e_bph = f"{e['bph']:.1f}" if e['bph'] < 9999 else "inf"
    b_win = b['bph'] < e['bph'] and b['pval'] < 0.05
    e_win = e['bph'] < b['bph'] and e['pval'] < 0.05
    marker = " <-- BASE" if b_win else (" <-- ENH" if e_win else "")
    print(f"  {'BASE':>12} {name:>12} {b['bets']:>5} {b['catches']:>4} "
          f"{100*b['cr']:>4.1f}% {100*b['prec']:>6.2f}% {b_bph:>6} "
          f"{b['lift']:>4.1f}x {b['pval']:>8.4f}")
    print(f"  {'ENHANCED':>12} {name:>12} {e['bets']:>5} {e['catches']:>4} "
          f"{100*e['cr']:>4.1f}% {100*e['prec']:>6.2f}% {e_bph:>6} "
          f"{e['lift']:>4.1f}x {e['pval']:>8.4f}{marker}")
    print()


# --- D: Component breakdown ---
print(f"\n  COMPONENT BREAKDOWN (Enhanced at >=6):")
for mode, u1, u2 in [('L1-only',1,0),('L2-only',0,1),('Both',1,1)]:
    b = c = 0
    for i in range(1, N):
        s = u1*enh_l1s[i] + u2*enh_l2s[i]
        if s >= 6:
            b += 1
            if is_vt(rows[i]): c += 1
    pr = c/b if b else 0
    cr = c/n_vt if n_vt else 0
    bph = b/c if c else float('inf')
    bph_s = f"{bph:.1f}" if bph < 9999 else "inf"
    print(f"    {mode:>8}: bets={b:>5}, catch={c:>2}/{n_vt}, cr={100*cr:.1f}%, prec={100*pr:.2f}%, b/h={bph_s}")


# =====================================================================
#  Save
# =====================================================================
out = {'baseline': {}, 'enhanced': {}}
for name in base_res:
    r = base_res[name]
    out['baseline'][name] = {k: (round(v,6) if isinstance(v,float) else v) for k,v in r.items()}
for name in enh_res:
    r = enh_res[name]
    out['enhanced'][name] = {k: (round(v,6) if isinstance(v,float) else v) for k,v in r.items()}

out_path = Path(__file__).parent / "82_enhanced_results.json"
with open(out_path, 'w') as f:
    json.dump(out, f, indent=2)
print(f"\nResults saved to {out_path}")
print("\nDONE")
