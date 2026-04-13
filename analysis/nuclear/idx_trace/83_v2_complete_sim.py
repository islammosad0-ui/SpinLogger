#!/usr/bin/env python3
"""
83_v2_complete_sim.py — Complete V2 scorer sim with ALL validated patterns.

Exhaustive mining → CV validation → build final V2 scorer → head-to-head vs V1.
Mines: back-to-back, paired sequences (r1/r2/r3), deltas, mirrors, sums,
       monotonic, hot tuples, cross-reel, trigrams, 3x repeats, anti-clustering.
"""

import csv, json, math, sys
from collections import defaultdict, Counter
from pathlib import Path
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =====================================================================
#  Data loading (merged Ahmed + Nick = 3,864 spins)
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

def target_vt(rows, i): return is_vt(rows[i])

# =====================================================================
#  PART 1: EXHAUSTIVE PATTERN MINING + CV VALIDATION
# =====================================================================
print(f"\n{'='*100}")
print("  PART 1: EXHAUSTIVE PATTERN MINING + CV VALIDATION")
print('='*100)

all_candidates = []  # (label, cond_fn, raw_n, raw_hits, raw_lift, raw_p)

# --- 1A: Back-to-back same reel values ---
print(f"\n  --- 1A: Back-to-back same reel values ---")
for reel in ['r1', 'r2', 'r3']:
    def make_bb(r):
        def cond(rows, i):
            if i < 2: return False
            return rows[i-2][r] == rows[i-1][r]
        return cond
    n_sig = hits = 0
    for i in range(2, N):
        if rows[i-2][reel] == rows[i-1][reel]:
            n_sig += 1
            if is_vt(rows[i]): hits += 1
    if n_sig >= 20:
        rate = hits/n_sig; pval = fisher_p(hits, n_sig, base_rate)
        lift = rate/base_rate
        print(f"    same {reel} x2: N={n_sig}, hits={hits}, rate={100*rate:.2f}%, lift={lift:.1f}x, p={pval:.4f}")
        if (lift > 1.3 and pval < 0.10) or (lift < 0.5 and n_sig >= 50):
            all_candidates.append((f"bb_{reel}", make_bb(reel), n_sig, hits, lift, pval))

# --- 1B: Same reel value 3 in a row ---
print(f"\n  --- 1B: Same reel 3x in a row ---")
for reel in ['r1', 'r2', 'r3']:
    def make_3x(r):
        def cond(rows, i):
            if i < 3: return False
            return rows[i-3][r] == rows[i-2][r] == rows[i-1][r]
        return cond
    n_sig = hits = 0
    for i in range(3, N):
        if rows[i-3][reel] == rows[i-2][reel] == rows[i-1][reel]:
            n_sig += 1
            if is_vt(rows[i]): hits += 1
    if n_sig >= 10:
        rate = hits/n_sig if n_sig else 0; pval = fisher_p(hits, n_sig, base_rate)
        lift = rate/base_rate if base_rate else 0
        print(f"    same {reel} x3: N={n_sig}, hits={hits}, rate={100*rate:.2f}%, lift={lift:.1f}x, p={pval:.4f}")
        if (lift > 1.5 and pval < 0.10) or (lift < 0.3):
            all_candidates.append((f"3x_{reel}", make_3x(reel), n_sig, hits, lift, pval))

# --- 1C: Paired 2-spin sequences (r1/r2/r3 pairs) ---
print(f"\n  --- 1C: Paired sequences (prev-prev reel, prev reel) ---")
for reel, label in [('r1','r1'), ('r2','r2'), ('r3','r3')]:
    count = 0
    for a in range(9):
        for b in range(9):
            n_sig = hits = 0
            for i in range(2, N):
                if rows[i-2][reel] == a and rows[i-1][reel] == b:
                    n_sig += 1
                    if is_vt(rows[i]): hits += 1
            if n_sig >= 20 and hits >= 1:
                rate = hits/n_sig; lift = rate/base_rate; pval = fisher_p(hits, n_sig, base_rate)
                if (lift > 1.8 and pval < 0.05) or (hits == 0 and n_sig >= 50):
                    def make_pair(r, va, vb):
                        def cond(rows, i):
                            if i < 2: return False
                            return rows[i-2][r] == va and rows[i-1][r] == vb
                        return cond
                    tag = f"{label}:({a},{b})"
                    all_candidates.append((tag, make_pair(reel, a, b), n_sig, hits, lift, pval))
                    count += 1
    print(f"    {label} pairs with lift>1.8: {count} candidates")

# --- 1D: Delta patterns ---
print(f"\n  --- 1D: Delta patterns (reel[i-1] - reel[i-2] = delta) ---")
for reel in ['r1', 'r2', 'r3']:
    for delta in range(-8, 9):
        n_sig = hits = 0
        for i in range(2, N):
            if rows[i-1][reel] - rows[i-2][reel] == delta:
                n_sig += 1
                if is_vt(rows[i]): hits += 1
        if n_sig >= 30 and hits >= 1:
            rate = hits/n_sig; lift = rate/base_rate; pval = fisher_p(hits, n_sig, base_rate)
            if (lift > 1.5 and pval < 0.05) or (hits == 0 and n_sig >= 50):
                def make_delta(r, d):
                    def cond(rows, i):
                        if i < 2: return False
                        return rows[i-1][r] - rows[i-2][r] == d
                    return cond
                tag = f"d{reel}={delta:+d}"
                all_candidates.append((tag, make_delta(reel, delta), n_sig, hits, lift, pval))
                print(f"    {tag}: N={n_sig}, hits={hits}, lift={lift:.1f}x, p={pval:.4f}")

# --- 1E: Mirror / symmetry ---
print(f"\n  --- 1E: Mirror & symmetry ---")
# r1==r3 on prev spin
def cond_mirror(rows, i):
    if i < 1: return False
    return rows[i-1]['r1'] == rows[i-1]['r3']
n_sig = sum(1 for i in range(1,N) if cond_mirror(rows,i))
hits = sum(1 for i in range(1,N) if cond_mirror(rows,i) and is_vt(rows[i]))
rate = hits/n_sig if n_sig else 0; lift = rate/base_rate; pval = fisher_p(hits, n_sig, base_rate)
print(f"    prev r1==r3: N={n_sig}, hits={hits}, lift={lift:.1f}x, p={pval:.4f}")
if lift > 1.3 and pval < 0.10:
    all_candidates.append(("mirror_r1r3", cond_mirror, n_sig, hits, lift, pval))

# r1+r3 sum
for s in range(0, 17):
    def make_sum13(target):
        def cond(rows, i):
            if i < 1: return False
            return rows[i-1]['r1'] + rows[i-1]['r3'] == target
        return cond
    n_sig = sum(1 for i in range(1,N) if make_sum13(s)(rows,i))
    hits = sum(1 for i in range(1,N) if make_sum13(s)(rows,i) and is_vt(rows[i]))
    if n_sig >= 20:
        rate = hits/n_sig; lift = rate/base_rate; pval = fisher_p(hits, n_sig, base_rate)
        if (lift > 1.8 and pval < 0.05) or (hits == 0 and n_sig >= 50):
            all_candidates.append((f"sum13={s}", make_sum13(s), n_sig, hits, lift, pval))
            print(f"    r1+r3={s}: N={n_sig}, hits={hits}, lift={lift:.1f}x, p={pval:.4f}")

# r1+r2+r3 sum
for s in range(0, 25):
    def make_sum123(target):
        def cond(rows, i):
            if i < 1: return False
            p = rows[i-1]
            return p['r1'] + p['r2'] + p['r3'] == target
        return cond
    n_sig = sum(1 for i in range(1,N) if make_sum123(s)(rows,i))
    hits = sum(1 for i in range(1,N) if make_sum123(s)(rows,i) and is_vt(rows[i]))
    if n_sig >= 20:
        rate = hits/n_sig; lift = rate/base_rate; pval = fisher_p(hits, n_sig, base_rate)
        if (lift > 1.8 and pval < 0.05) or (hits == 0 and n_sig >= 50):
            all_candidates.append((f"sum123={s}", make_sum123(s), n_sig, hits, lift, pval))
            print(f"    r1+r2+r3={s}: N={n_sig}, hits={hits}, lift={lift:.1f}x, p={pval:.4f}")

# --- 1F: Monotonic sequences ---
print(f"\n  --- 1F: Monotonic sequences ---")
for reel in ['r1', 'r2', 'r3']:
    for direction, label_d in [(1, 'asc'), (-1, 'desc')]:
        # 2-step
        def make_mono2(r, d):
            def cond(rows, i):
                if i < 2: return False
                diff = rows[i-1][r] - rows[i-2][r]
                return (diff > 0) if d > 0 else (diff < 0)
            return cond
        n_sig = sum(1 for i in range(2,N) if make_mono2(reel, direction)(rows,i))
        hits = sum(1 for i in range(2,N) if make_mono2(reel, direction)(rows,i) and is_vt(rows[i]))
        if n_sig >= 30:
            rate = hits/n_sig; lift = rate/base_rate; pval = fisher_p(hits, n_sig, base_rate)
            print(f"    {reel} {label_d} 2-step: N={n_sig}, hits={hits}, lift={lift:.1f}x, p={pval:.4f}")
            if (lift > 1.3 and pval < 0.05) or (lift < 0.5):
                all_candidates.append((f"mono2_{reel}_{label_d}", make_mono2(reel, direction), n_sig, hits, lift, pval))

        # 3-step
        def make_mono3(r, d):
            def cond(rows, i):
                if i < 3: return False
                d1 = rows[i-2][r] - rows[i-3][r]
                d2 = rows[i-1][r] - rows[i-2][r]
                return (d1 > 0 and d2 > 0) if d > 0 else (d1 < 0 and d2 < 0)
            return cond
        n_sig = sum(1 for i in range(3,N) if make_mono3(reel, direction)(rows,i))
        hits = sum(1 for i in range(3,N) if make_mono3(reel, direction)(rows,i) and is_vt(rows[i]))
        if n_sig >= 15:
            rate = hits/n_sig; lift = rate/base_rate; pval = fisher_p(hits, n_sig, base_rate)
            if (lift > 1.5 and pval < 0.10) or (lift < 0.3):
                all_candidates.append((f"mono3_{reel}_{label_d}", make_mono3(reel, direction), n_sig, hits, lift, pval))
                print(f"    {reel} {label_d} 3-step: N={n_sig}, hits={hits}, lift={lift:.1f}x, p={pval:.4f}")

# --- 1G: Cross-reel paired sequences ---
print(f"\n  --- 1G: Cross-reel pairs (r1[i-2] x r2[i-1], etc.) ---")
for r_a, r_b, lab in [('r1','r2','r1xr2'), ('r1','r3','r1xr3'), ('r2','r3','r2xr3')]:
    count = 0
    for a in range(9):
        for b in range(9):
            n_sig = hits = 0
            for i in range(2, N):
                if rows[i-2][r_a] == a and rows[i-1][r_b] == b:
                    n_sig += 1
                    if is_vt(rows[i]): hits += 1
            if n_sig >= 20 and hits >= 2:
                rate = hits/n_sig; lift = rate/base_rate; pval = fisher_p(hits, n_sig, base_rate)
                if lift > 2.0 and pval < 0.03:
                    def make_xreel(ra, rb, va, vb):
                        def cond(rows, i):
                            if i < 2: return False
                            return rows[i-2][ra] == va and rows[i-1][rb] == vb
                        return cond
                    tag = f"{lab}:({a},{b})"
                    all_candidates.append((tag, make_xreel(r_a, r_b, a, b), n_sig, hits, lift, pval))
                    count += 1
    print(f"    {lab}: {count} candidates with lift>2.0")

# --- 1H: Anti-clustering (VT followed by drought) ---
print(f"\n  --- 1H: Post-VT anti-clustering ---")
for gap in [1, 2, 3, 5, 10, 20, 50]:
    def make_post_vt(g):
        def cond(rows, i):
            if i < g + 1: return False
            # Check if there was a VT in the last g spins
            return any(is_vt(rows[i-j]) for j in range(1, g+1))
        return cond
    n_sig = sum(1 for i in range(gap+1, N) if make_post_vt(gap)(rows,i))
    hits = sum(1 for i in range(gap+1, N) if make_post_vt(gap)(rows,i) and is_vt(rows[i]))
    if n_sig >= 20:
        rate = hits/n_sig; lift = rate/base_rate; pval = fisher_p(hits, n_sig, base_rate)
        marker = " <<<" if lift < 0.5 else ""
        print(f"    VT in last {gap:>2} spins: N={n_sig}, hits={hits}, rate={100*rate:.2f}%, lift={lift:.2f}x{marker}")
        if lift < 0.5 and n_sig >= 50:
            all_candidates.append((f"post_vt_{gap}", make_post_vt(gap), n_sig, hits, lift, pval))

# --- 1I: r2 trigrams ---
print(f"\n  --- 1I: r2 trigrams (top candidates) ---")
hot_r2 = list(range(9))
trigram_count = 0
for a in hot_r2:
    for b in hot_r2:
        for c in hot_r2:
            n_sig = hits = 0
            for i in range(3, N):
                if rows[i-3]['r2']==a and rows[i-2]['r2']==b and rows[i-1]['r2']==c:
                    n_sig += 1
                    if is_vt(rows[i]): hits += 1
            if n_sig >= 10 and hits >= 2:
                rate = hits/n_sig; lift = rate/base_rate; pval = fisher_p(hits, n_sig, base_rate)
                if lift > 3.0 and pval < 0.03:
                    def make_tri(va, vb, vc):
                        def cond(rows, i):
                            if i < 3: return False
                            return rows[i-3]['r2']==va and rows[i-2]['r2']==vb and rows[i-1]['r2']==vc
                        return cond
                    tag = f"tri_r2:({a},{b},{c})"
                    all_candidates.append((tag, make_tri(a, b, c), n_sig, hits, lift, pval))
                    trigram_count += 1
print(f"    Found {trigram_count} r2 trigrams with lift>3.0")

print(f"\n  TOTAL CANDIDATES FOR CV: {len(all_candidates)}")

# =====================================================================
#  PART 2: 5-FOLD TEMPORAL CV ON ALL CANDIDATES
# =====================================================================
print(f"\n{'='*100}")
print("  PART 2: CV VALIDATION (4/5 folds required)")
print('='*100)
print(f"\n  {'Pattern':>25} {'N':>5} {'Hits':>4} {'Rate':>7} {'Lift':>5} {'CV':>4} {'p':>8} {'Verdict':>8}")
print(f"  {'-'*75}")

validated = []
for label, cond_fn, raw_n, raw_hits, raw_lift, raw_p in all_candidates:
    res = temporal_cv(rows, cond_fn, target_vt)
    if res and res['n'] >= 15:
        pval = fisher_p(res['hits'], res['n'], base_rate)
        lift = res['rate'] / base_rate if base_rate else 0
        verdict = "PASS" if res['cv'] >= 4 and pval < 0.05 else ("WEAK" if res['cv'] >= 3 else "FAIL")
        if verdict in ("PASS", "WEAK"):
            print(f"  {label:>25} {res['n']:>5} {res['hits']:>4} {100*res['rate']:>6.2f}% "
                  f"{lift:>4.1f}x {res['cv']}/5 {pval:>8.4f} {verdict:>8}")
        if verdict == "PASS":
            validated.append((label, cond_fn, res, lift))

print(f"\n  VALIDATED (4/5+ CV, p<0.05): {len(validated)}")
for label, _, res, lift in validated:
    print(f"    {label}: {res['hits']}/{res['n']} = {100*res['rate']:.2f}%, lift={lift:.1f}x, cv={res['cv']}/5")


# =====================================================================
#  PART 3: BUILD SCORERS — V1 (app original) vs V2 (enhanced + everything)
# =====================================================================
print(f"\n{'='*100}")
print("  PART 3: SCORER DEFINITIONS")
print('='*100)

# --- V1: Exact replica of app's current V1 scorer ---
def v1_l1(prev):
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

def v1_l2(rows, i, window=10):
    if i < 3: return 0
    start = max(0, i - window)
    win = rows[start:i]; wsize = len(win)
    if wsize < 3: return 0
    score = 0
    # A: steal r1
    if sum(1 for r in win if r['s1'] == 4) >= 2: score += 1
    # B: r3=4 count
    if sum(1 for r in win if r['r3'] == 4) >= 2: score += 1
    # C: bigram 0->8
    if any(win[j-1]['r3']==0 and win[j]['r3']==8 for j in range(1, wsize)): score += 1
    # D: bigram 8->4 or 4->4
    if any((win[j-1]['r3']==8 and win[j]['r3']==4) or (win[j-1]['r3']==4 and win[j]['r3']==4) for j in range(1, wsize)): score += 1
    # E: r2=6 gap
    r2_6_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r2'] == 6: r2_6_gap = lb; break
    if 0 < r2_6_gap <= 7: score += 1
    # F/G: r3=1 gap
    r3_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r3'] == 1: r3_1_gap = lb; break
    if r3_1_gap < 0 or r3_1_gap > 10: score += 1
    if 0 < r3_1_gap <= 3: score -= 2
    # H: tuple (3,6,4)
    if any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win): score += 1
    # I: r3 variety
    if wsize > 1:
        dups = sum(1 for j in range(1, wsize) if win[j]['r3']==win[j-1]['r3'])
        if dups/(wsize-1) < 0.15: score += 1
    # J: r1 bigram (3,3) +1
    if any(win[j-1]['r1']==3 and win[j]['r1']==3 for j in range(1, wsize)): score += 1
    return score

# --- V2: Enhanced scorer (matches app V2 code) ---
def v2_l1(prev, prev2=None, prev3=None):
    r1, r2, r3 = prev['r1'], prev['r2'], prev['r3']
    s = 0
    # Positives
    if r2 == 7: s += 2
    if r1 == 7: s += 1
    if r2 == 3: s += 1
    if r1 == 3: s += 1
    if r3 == 3: s += 1
    if r3 == 5: s += 1
    if r3 == 8: s += 1
    # Negatives
    if r3 == 1: s -= 2
    if r2 == 5: s -= 2
    if r3 == 7: s -= 1
    if r2 == 0: s -= 1
    if r2 == 2: s -= 1
    if r1 == 5: s -= 1
    if r1 == 0: s -= 1
    # Pair bonuses
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
    # Dead pairs
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
    # Dead tuples
    if r1 == 4 and r2 == 4 and r3 == 4: s -= 2
    if r1 == 7 and r2 == 6 and r3 == 0: s -= 1
    if r1 == 6 and r2 == 4 and r3 == 1: s -= 1
    if r1 == 1 and r2 == 1 and r3 == 1: s -= 1

    # Multi-lag
    if prev2 is not None:
        # Sequence patterns (prev r3 -> current r3)
        if prev2['r3'] == r3:           s += 1   # dr3=+0: back-to-back same r3
        if prev2['r3'] == 5 and r3 == 5: s += 1  # r3:(5,5) stacks with dr3
        if prev2['r3'] == 8 and r3 == 5: s += 1  # r3:(8,5)
        # Lag-2 penalties
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
    # A
    if sum(1 for r in win if r['s1'] == 4) >= 2: score += 1
    # B
    if sum(1 for r in win if r['r3'] == 4) >= 2: score += 1
    # C
    if any(win[j-1]['r3']==0 and win[j]['r3']==8 for j in range(1, wsize)): score += 1
    # D
    if any((win[j-1]['r3']==8 and win[j]['r3']==4) or (win[j-1]['r3']==4 and win[j]['r3']==4) for j in range(1, wsize)): score += 1
    # E: REMOVED
    # F/G
    r3_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r3'] == 1: r3_1_gap = lb; break
    if r3_1_gap < 0 or r3_1_gap > 10: score += 1
    if 0 < r3_1_gap <= 3: score -= 2
    # H
    if any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win): score += 1
    # I: REMOVED
    # J: FLIPPED
    if any(win[j-1]['r1']==3 and win[j]['r1']==3 for j in range(1, wsize)): score -= 1
    return score


# =====================================================================
#  PART 4: SIMULATION — V1 vs V2 vs V2+NEW
# =====================================================================
print(f"\n{'='*100}")
print("  PART 4: SIMULATION")
print('='*100)

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
    ('>=14',       14),
]

def run_sim(rows, l1_fn, l2_fn, label, has_multilag=False):
    N = len(rows)
    scores = [0]*N
    l1s = [0]*N; l2s = [0]*N
    for i in range(1, N):
        prev = rows[i-1]
        if has_multilag:
            prev2 = rows[i-2] if i >= 2 else None
            prev3 = rows[i-3] if i >= 3 else None
            l1s[i] = l1_fn(prev, prev2, prev3)
        else:
            l1s[i] = l1_fn(prev)
        l2s[i] = l2_fn(rows, i)
        scores[i] = l1s[i] + l2s[i]

    results = {}
    for name, thresh in THRESHOLDS:
        bets = catches = missed = 0
        for i in range(1, N):
            hit = is_vt(rows[i])
            if scores[i] >= thresh:
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

    # Score distribution
    dist = defaultdict(lambda: {'n':0,'h':0})
    for i in range(1, N):
        dist[scores[i]]['n'] += 1
        if is_vt(rows[i]): dist[scores[i]]['h'] += 1

    return results, dist, scores

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
    print(f"  {'-'*42}")
    cum = 0
    for sc in sorted(dist.keys(), reverse=True):
        d = dist[sc]
        rate = d['h']/d['n'] if d['n'] else 0
        lift = rate/base_rate if base_rate else 0
        cum += d['h']
        cumc = cum/n_vt if n_vt else 0
        if d['n'] >= 3 or d['h'] > 0:
            print(f"  {sc:>4} {d['n']:>6} {d['h']:>4} {100*rate:>5.1f}% {lift:>4.1f}x {cum:>4} {100*cumc:>4.1f}%")


# Run V1
print("\n  A) V1 SCORER (current app):")
v1_res, v1_dist, v1_scores = run_sim(rows, v1_l1, v1_l2, "V1")
print_dist(v1_dist, "V1 score distribution")
print_kpi(v1_res, "V1 KPIs")

# Run V2
print("\n\n  B) V2 SCORER (enhanced + multi-lag + sequences):")
v2_res, v2_dist, v2_scores = run_sim(rows, v2_l1, v2_l2, "V2", has_multilag=True)
print_dist(v2_dist, "V2 score distribution")
print_kpi(v2_res, "V2 KPIs")

# --- V2+NEW: If validated patterns exist, build V2+NEW with them ---
if validated:
    print(f"\n\n  C) V2+NEW (V2 + {len(validated)} new validated patterns):")

    # Build bonus function from validated patterns
    def v2new_l1(prev, prev2=None, prev3=None):
        s = v2_l1(prev, prev2, prev3)
        return s

    # We'll add the validated patterns as additional L2-style bonuses
    def v2new_l2(rows, i):
        base = v2_l2(rows, i)
        bonus = 0
        for label, cond_fn, res, lift in validated:
            # Skip patterns already in V2 (back-to-back r3, multi-lag, etc.)
            if label.startswith('bb_r3'):  continue  # already dr3=+0 in V2
            if label.startswith('r3:(5,5'): continue  # already in V2
            if label.startswith('r3:(8,5'): continue  # already in V2
            if label.startswith('dr3=+0'): continue  # already in V2
            try:
                if cond_fn(rows, i):
                    if lift > 1.0:
                        bonus += 1
                    else:
                        bonus -= 1
            except:
                pass
        return base + bonus

    v2n_res, v2n_dist, v2n_scores = run_sim(rows, v2new_l1, v2new_l2, "V2+NEW", has_multilag=True)
    print_dist(v2n_dist, "V2+NEW score distribution")
    print_kpi(v2n_res, "V2+NEW KPIs")


# =====================================================================
#  HEAD-TO-HEAD
# =====================================================================
print(f"\n\n{'='*100}")
print("  HEAD-TO-HEAD: V1 vs V2")
print('='*100)
print(f"\n  Target: ACC+SPN = {n_vt}/{N} = {100*base_rate:.2f}%")
print(f"\n  {'':>12} {'Prof':>12} {'Bets':>5} {'Cat':>4} {'CatR':>5} "
      f"{'Prec':>7} {'B/H':>6} {'Lift':>5} {'p':>8} {'Winner':>8}")
print(f"  {'-'*85}")

for name, _ in THRESHOLDS:
    v1 = v1_res[name]; v2 = v2_res[name]
    v1_bph = f"{v1['bph']:.1f}" if v1['bph'] < 9999 else "inf"
    v2_bph = f"{v2['bph']:.1f}" if v2['bph'] < 9999 else "inf"

    winner = ""
    if v2['catches'] > 0 and v1['catches'] > 0:
        if v2['bph'] < v1['bph'] and v2['pval'] < 0.05: winner = "V2"
        elif v1['bph'] < v2['bph'] and v1['pval'] < 0.05: winner = "V1"

    print(f"  {'V1':>12} {name:>12} {v1['bets']:>5} {v1['catches']:>4} "
          f"{100*v1['cr']:>4.1f}% {100*v1['prec']:>6.2f}% {v1_bph:>6} "
          f"{v1['lift']:>4.1f}x {v1['pval']:>8.4f}")
    print(f"  {'V2':>12} {name:>12} {v2['bets']:>5} {v2['catches']:>4} "
          f"{100*v2['cr']:>4.1f}% {100*v2['prec']:>6.2f}% {v2_bph:>6} "
          f"{v2['lift']:>4.1f}x {v2['pval']:>8.4f} {winner:>8}")
    print()

# Key comparison
for key_name in ['>=6 (ULT)', '>=8 (SNP)', '>=10', '>=12']:
    if key_name in v1_res and key_name in v2_res:
        v1 = v1_res[key_name]; v2 = v2_res[key_name]
        if v1['catches'] > 0 and v2['catches'] > 0:
            bph_diff = v1['bph'] - v2['bph']
            print(f"  {key_name}: V2 saves {bph_diff:+.1f} bets/hit ({v1['bph']:.1f} -> {v2['bph']:.1f})")

# Save
out = {'v1': {}, 'v2': {}}
for name in v1_res:
    out['v1'][name] = {k: (round(v,6) if isinstance(v,float) else v) for k,v in v1_res[name].items()}
for name in v2_res:
    out['v2'][name] = {k: (round(v,6) if isinstance(v,float) else v) for k,v in v2_res[name].items()}

out_path = Path(__file__).parent / "83_v2_results.json"
with open(out_path, 'w') as f:
    json.dump(out, f, indent=2)
print(f"\nResults saved to {out_path}")
print("\nDONE")
