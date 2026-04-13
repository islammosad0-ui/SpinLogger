#!/usr/bin/env python3
"""
81_proper_split_analysis.py - EXHAUSTIVE deep analysis.

Fixes from v1 (80):
  - L2 is TYPE-SPECIFIC (only validated signals per type)
  - Dead zones require n>=50
  - BASELINE: exact current app scorer for comparison

Additions per user request ("don't leave anything"):
  - Gap analysis: distribution of gaps between consecutive valuable triples
  - Multi-lag signals: lag-1, lag-2, lag-3 idx prediction
  - Sequence patterns: 2-spin and 3-spin idx sequences preceding hits
  - Transition matrix: idx->idx transition patterns before hits
  - Cluster detection: do triples bunch up?
  - Conditional signals: post-result type conditioning
  - Full 3-idx tuple scoring: specific (r1,r2,r3) combos
  - Cross-type interaction: does a recent ATTACK predict ACC/SPN?
"""

import csv, json, math, sys
from collections import defaultdict, Counter
from pathlib import Path
from scipy.stats import binom, fisher_exact

ROOT = Path(__file__).resolve().parents[3]

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =====================================================================
#  Data loading
# =====================================================================
SYM_CODE = {
    'attack': 3, 'steal': 4, 'shield': 5, 'spins': 6,
    'coin': 1, 'goldSack': 2, 'accumulation': 30, 'potion': 7,
}
SYM_NAME = {v: k for k, v in SYM_CODE.items()}

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
        header = next(reader)
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
print(f"Total: {N} spins ({len(ahmed)} Ahmed + {len(nick)} Nick)")

# Quick summary
type_counts = defaultdict(int)
for r in rows:
    if r['is_triple']: type_counts[r['reel_1']] += 1
print(f"\nTriples by type:")
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {t:>15}: {c:>4} ({100*c/N:.2f}%, 1 per {N/max(c,1):.0f})")

ACC_SPN = [30, 6]
n_vt = sum(1 for r in rows if r['is_triple'] and r['s1'] in ACC_SPN)
print(f"\n  Valuable (ACC+SPN): {n_vt} ({100*n_vt/N:.2f}%, 1 per {N/n_vt:.0f})")

# =====================================================================
#  Helpers
# =====================================================================
def fisher_p(hits, n, base_rate):
    if n == 0 or hits == 0: return 1.0
    return 1 - binom.cdf(hits - 1, n, base_rate)

def wilson_ci(hits, n, z=1.96):
    if n == 0: return (0, 0)
    p = hits / n
    denom = 1 + z*z/n
    center = (p + z*z/(2*n)) / denom
    margin = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
    return (max(0, center - margin), min(1, center + margin))

def temporal_cv(rows, condition_fn, target_fn, n_folds=5, lag=1):
    """Condition on rows[i-lag], target on rows[i]."""
    fold_size = len(rows) // n_folds
    total_sig = total_hits = total_base_n = total_base_hits = 0
    fold_lifts = []
    for fold in range(n_folds):
        start = fold * fold_size
        end = start + fold_size if fold < n_folds - 1 else len(rows)
        sig_n = sig_h = base_n = base_h = 0
        for i in range(max(start, lag), end):
            hit = target_fn(rows[i])
            if condition_fn(rows[i-lag]):
                sig_n += 1
                if hit: sig_h += 1
            base_n += 1
            if hit: base_h += 1
        total_sig += sig_n; total_hits += sig_h
        total_base_n += base_n; total_base_hits += base_h
        if sig_n >= 5:
            fold_lifts.append(sig_h/sig_n - (base_h/base_n if base_n else 0))
        else:
            fold_lifts.append(None)
    if total_sig == 0: return None
    rate = total_hits / total_sig
    base = total_base_hits / total_base_n if total_base_n else 0
    lift = (rate - base) * 100
    d = 1 if lift >= 0 else -1
    cv = sum(1 for l in fold_lifts if l is not None and l * d > 0)
    return {'rate': rate, 'base': base, 'lift_pp': lift, 'cv': cv,
            'n': total_sig, 'hits': total_hits}

# =====================================================================
#  L2 signal decomposition
# =====================================================================
ALL_L2 = ['A','B','C','D','E','F','G','H','I','J']

def compute_l2_signals(rows, i, window=10):
    if i < 3: return {}
    start = max(0, i - window)
    win = rows[start:i]
    wsize = len(win)
    if wsize < 3: return {}
    sigs = {}
    sigs['A'] = sum(1 for r in win if r['s1'] == 4) >= 2
    sigs['B'] = sum(1 for r in win if r['r3'] == 4) >= 2
    sigs['C'] = any(win[j-1]['r3']==0 and win[j]['r3']==8 for j in range(1, wsize))
    sigs['D'] = any((win[j-1]['r3']==8 and win[j]['r3']==4) or
                    (win[j-1]['r3']==4 and win[j]['r3']==4) for j in range(1, wsize))
    r2_6_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r2'] == 6: r2_6_gap = lb; break
    sigs['E'] = 0 < r2_6_gap <= 7
    r3_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r3'] == 1: r3_1_gap = lb; break
    sigs['F'] = r3_1_gap < 0 or r3_1_gap > 10
    sigs['G'] = 0 < r3_1_gap <= 3
    sigs['H'] = any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win)
    if wsize > 1:
        dups = sum(1 for j in range(1, wsize) if win[j]['r3']==win[j-1]['r3'])
        sigs['I'] = dups / (wsize - 1) < 0.15
    else:
        sigs['I'] = False
    sigs['J'] = any(win[j-1]['r1']==3 and win[j]['r1']==3 for j in range(1, wsize))
    return sigs

def validate_l2_per_type(rows, target_codes):
    N = len(rows)
    def is_t(row): return row['is_triple'] and row['s1'] in target_codes
    n_t = sum(1 for r in rows if is_t(r))
    base = n_t / N
    all_sigs = {i: compute_l2_signals(rows, i) for i in range(N)}
    results = {}
    for sig in ALL_L2:
        fold_size = N // 5
        fold_lifts = []
        total_fire = total_hit = 0
        for fold in range(5):
            fs = fold * fold_size
            fe = fs + fold_size if fold < 4 else N
            f_fire = f_hit = f_bn = f_bh = 0
            for i in range(max(fs, 3), fe):
                hit = is_t(rows[i])
                f_bn += 1
                if hit: f_bh += 1
                if all_sigs[i].get(sig, False):
                    f_fire += 1
                    if hit: f_hit += 1
            total_fire += f_fire; total_hit += f_hit
            if f_fire >= 5 and f_bn > 0:
                fold_lifts.append(f_hit/f_fire - f_bh/f_bn)
            else:
                fold_lifts.append(None)
        if total_fire == 0: continue
        rate = total_hit / total_fire
        lift = (rate - base) * 100
        d = 1 if lift >= 0 else -1
        cv = sum(1 for l in fold_lifts if l is not None and l * d > 0)
        results[sig] = {'n': total_fire, 'hits': total_hit, 'rate': rate,
                        'lift_pp': lift, 'cv': cv}
    return results

def make_type_l2(include_map):
    def l2_fn(rows, i):
        sigs = compute_l2_signals(rows, i)
        if not sigs: return 0
        s = 0
        for sig, w in include_map.items():
            if sigs.get(sig, False): s += w
        return s
    return l2_fn

# =====================================================================
#  Current app scorer (exact replica)
# =====================================================================
def app_score_acc_spns(r1, r2, r3):
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

def app_l2(rows, i, window=10):
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

# =====================================================================
#  Signal discovery (improved)
# =====================================================================
def discover_signals(target_codes, rows, lag=1):
    N = len(rows)
    def is_t(row): return row['is_triple'] and row['s1'] in target_codes
    n_t = sum(1 for r in rows if is_t(r))
    if n_t == 0: return [], [], n_t
    base = n_t / N

    indiv = []
    for rn in ['r1', 'r2', 'r3']:
        for iv in range(9):
            res = temporal_cv(rows, lambda p, r=rn, v=iv: p[r]==v, is_t, lag=lag)
            if not res or res['n'] < 20: continue
            if res['cv'] >= 4 and res['lift_pp'] > 0:
                w = 2 if (res['cv'] >= 5 or res['lift_pp'] > base*100*0.4) else 1
                indiv.append({'key': f"{rn}={iv}", 'dir': '+', 'weight': w, **res})
            elif res['cv'] >= 4 and res['lift_pp'] < -base*40:
                w = -2 if (res['cv'] >= 5 or res['hits'] == 0) else -1
                indiv.append({'key': f"{rn}={iv}", 'dir': '-', 'weight': w, **res})

    pairs = []
    for na, nb in [('r1','r2'), ('r1','r3'), ('r2','r3')]:
        for va in range(9):
            for vb in range(9):
                res = temporal_cv(rows,
                    lambda p, a=na, b=nb, x=va, y=vb: p[a]==x and p[b]==y, is_t, lag=lag)
                if not res or res['n'] < 20: continue
                if res['cv'] >= 4 and res['lift_pp'] > 0 and res['hits'] >= 3:
                    w = 2 if (res['cv'] >= 5 or res['lift_pp'] > 5.0) else 1
                    pairs.append({'key': f"({na}={va},{nb}={vb})", 'dir': '+', 'weight': w, **res})
                elif res['hits'] == 0 and res['n'] >= 50:
                    w = -2 if res['n'] >= 80 else -1
                    pairs.append({'key': f"({na}={va},{nb}={vb})", 'dir': '-', 'weight': w, **res})
    return indiv, pairs, n_t

def build_l1_scorer(indiv, pairs):
    def score(r1, r2, r3):
        s = 0
        vals = {'r1': r1, 'r2': r2, 'r3': r3}
        for sig in indiv:
            parts = sig['key'].split('=')
            if vals[parts[0]] == int(parts[1]): s += sig['weight']
        for p in pairs:
            inner = p['key'][1:-1]
            parts = inner.split(',')
            rn_a, va = parts[0].split('=')
            rn_b, vb = parts[1].split('=')
            if vals[rn_a] == int(va) and vals[rn_b] == int(vb): s += p['weight']
        return s
    max_s = sum(s['weight'] for s in indiv if s['dir']=='+') + \
            sum(p['weight'] for p in pairs if p['dir']=='+')
    return score, max_s

# =====================================================================
#  Simulation engine
# =====================================================================
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
]

def run_sim(rows, target_codes, l1_fn, l2_fn, thresholds):
    N = len(rows)
    def is_t(row): return row['is_triple'] and row['s1'] in target_codes
    n_t = sum(1 for r in rows if is_t(r))
    base = n_t / N
    l1s = [0]*N; l2s = [0]*N
    for i in range(1, N):
        l1s[i] = l1_fn(rows[i-1])
        l2s[i] = l2_fn(rows, i)
    results = {}
    for name, thresh in thresholds:
        bets = catches = missed = 0
        for i in range(1, N):
            c = l1s[i] + l2s[i]
            hit = is_t(rows[i])
            if c >= thresh:
                bets += 1
                if hit: catches += 1
            elif hit: missed += 1
        cr = catches/n_t if n_t else 0
        prec = catches/bets if bets else 0
        bph = bets/catches if catches else float('inf')
        lift = prec/base if base else 0
        pval = fisher_p(catches, bets, base)
        lo, hi = wilson_ci(catches, bets)
        results[name] = {'thresh': thresh, 'bets': bets, 'catches': catches,
            'missed': missed, 'cr': cr, 'prec': prec, 'bph': bph,
            'lift': lift, 'pval': pval, 'ci_lo': lo, 'ci_hi': hi, 'base': base, 'total': n_t}
    dist = defaultdict(lambda: {'n':0,'h':0})
    for i in range(1, N):
        c = l1s[i]+l2s[i]; hit = is_t(rows[i])
        dist[c]['n'] += 1
        if hit: dist[c]['h'] += 1
    return results, dist, l1s, l2s

def print_kpi(results, label, base):
    print(f"\n  {label} (base={100*base:.2f}%):")
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

def print_dist(dist, n_t, base):
    print(f"\n  Score distribution:")
    print(f"  {'Sc':>4} {'Spins':>6} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'CumH':>4} {'Cum%':>5}")
    print(f"  {'-'*40}")
    cum = 0
    for sc in sorted(dist.keys(), reverse=True):
        d = dist[sc]
        rate = d['h']/d['n'] if d['n'] else 0
        lift = rate/base if base else 0
        cum += d['h']
        cumc = cum/n_t if n_t else 0
        print(f"  {sc:>4} {d['n']:>6} {d['h']:>4} {100*rate:>5.1f}% {lift:>4.1f}x {cum:>4} {100*cumc:>4.1f}%")


# =====================================================================
#  PHASE 1: BASELINE (current app scorer)
# =====================================================================
print(f"\n{'='*95}")
print("  PHASE 1: BASELINE - Current app scorer (ACC+SPN combined + generic L2)")
print("=" * 95)
print(f"\n  ACC+SPN: {n_vt} targets ({100*n_vt/N:.2f}%, 1 per {N/n_vt:.0f})")

def app_l1_fn(prev): return app_score_acc_spns(prev['r1'], prev['r2'], prev['r3'])
base_res, base_dist, base_l1, base_l2 = run_sim(rows, ACC_SPN, app_l1_fn, app_l2, THRESHOLDS)
base_rate = n_vt / N

print_dist(base_dist, n_vt, base_rate)
print_kpi(base_res, "BASELINE (current app)", base_rate)


# =====================================================================
#  PHASE 2: GAP ANALYSIS
# =====================================================================
print(f"\n\n{'='*95}")
print("  PHASE 2: GAP ANALYSIS - Distance between valuable triples")
print("=" * 95)

def is_vt(row): return row['is_triple'] and row['s1'] in ACC_SPN
def is_acc(row): return row['is_triple'] and row['s1'] == 30
def is_spn(row): return row['is_triple'] and row['s1'] == 6

# Compute gaps
vt_positions = [i for i in range(N) if is_vt(rows[i])]
acc_positions = [i for i in range(N) if is_acc(rows[i])]
spn_positions = [i for i in range(N) if is_spn(rows[i])]

def gap_stats(positions, label):
    if len(positions) < 2:
        print(f"  {label}: too few hits for gap analysis")
        return
    gaps = [positions[i+1]-positions[i] for i in range(len(positions)-1)]
    print(f"\n  {label} ({len(positions)} hits):")
    print(f"    Mean gap: {sum(gaps)/len(gaps):.1f}")
    print(f"    Median gap: {sorted(gaps)[len(gaps)//2]}")
    print(f"    Min gap: {min(gaps)}, Max gap: {max(gaps)}")
    print(f"    Std dev: {(sum((g-sum(gaps)/len(gaps))**2 for g in gaps)/len(gaps))**0.5:.1f}")

    # Gap distribution buckets
    buckets = [(1,5), (6,15), (16,30), (31,50), (51,100), (101,200), (201,500)]
    print(f"    Gap distribution:")
    for lo, hi in buckets:
        cnt = sum(1 for g in gaps if lo <= g <= hi)
        pct = 100*cnt/len(gaps) if gaps else 0
        print(f"      {lo:>3}-{hi:>3}: {cnt:>3} ({pct:>5.1f}%)")

    # Clustering: gaps < 10 vs expected under random (Poisson)
    short = sum(1 for g in gaps if g <= 10)
    expected = len(gaps) * (1 - math.exp(-10 / (sum(gaps)/len(gaps))))
    print(f"    Clustering: {short} gaps <=10 (expected {expected:.1f} under random)")
    if short > expected * 1.3:
        print(f"    >> CLUSTERS detected: {short/expected:.2f}x more short gaps than random")
    elif short < expected * 0.7:
        print(f"    >> ANTI-clustering: {short/expected:.2f}x fewer short gaps than random")
    else:
        print(f"    >> Consistent with random ({short/expected:.2f}x)")

gap_stats(vt_positions, "ACC+SPN combined")
gap_stats(acc_positions, "ACC only")
gap_stats(spn_positions, "SPN only")

# Gap-conditioned hit rate: does current gap predict next hit?
print(f"\n  Gap-conditioned prediction:")
print(f"  (After a VT triple, does the gap since last triple predict the next?)")
print(f"  {'Gap since':>12} {'Spins':>6} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*50}")

for gap_lo, gap_hi in [(1,5), (6,15), (16,30), (31,50), (51,80), (81,150), (151,999)]:
    spins = hits = 0
    for i in range(1, N):
        # Find gap to most recent VT
        gap = None
        for back in range(1, min(i+1, 200)):
            if is_vt(rows[i-back]):
                gap = back
                break
        if gap is not None and gap_lo <= gap <= gap_hi:
            spins += 1
            if is_vt(rows[i]): hits += 1
    rate = hits/spins if spins else 0
    lift = rate/base_rate if base_rate else 0
    pval = fisher_p(hits, spins, base_rate) if spins > 0 and hits > 0 else 1.0
    print(f"  {f'{gap_lo}-{gap_hi}':>12} {spins:>6} {hits:>4} {100*rate:>5.2f}% {lift:>4.1f}x {pval:>8.4f}")


# =====================================================================
#  PHASE 3: MULTI-LAG SIGNALS
# =====================================================================
print(f"\n\n{'='*95}")
print("  PHASE 3: MULTI-LAG SIGNALS (lag-1, lag-2, lag-3)")
print("=" * 95)

for target_name, target_codes in [("ACC+SPN", ACC_SPN), ("ACC", [30]), ("SPN", [6])]:
    def is_t(row, tc=target_codes): return row['is_triple'] and row['s1'] in tc
    n_t = sum(1 for r in rows if is_t(r))
    base = n_t / N

    print(f"\n  {target_name} ({n_t} hits, {100*base:.2f}% base):")

    for lag in [1, 2, 3]:
        print(f"\n    Lag-{lag} signals (condition on spin[i-{lag}], target on spin[i]):")
        found = []
        for rn in ['r1', 'r2', 'r3']:
            for iv in range(9):
                res = temporal_cv(rows, lambda p, r=rn, v=iv: p[r]==v, is_t, lag=lag)
                if not res or res['n'] < 30: continue
                if res['cv'] >= 4 and abs(res['lift_pp']) > base*30:
                    found.append((f"{rn}={iv}", res))
        found.sort(key=lambda x: -abs(x[1]['lift_pp']))
        if not found:
            print(f"      No signals at lag-{lag}")
        for key, res in found[:8]:
            d = '+' if res['lift_pp'] > 0 else '-'
            print(f"      {key:>6}: {d}{abs(res['lift_pp']):.2f}pp, {res['cv']}/5 CV, "
                  f"{res['hits']}/{res['n']} ({100*res['rate']:.1f}%)")


# =====================================================================
#  PHASE 4: SEQUENCE PATTERNS (2-spin and 3-spin idx sequences before hits)
# =====================================================================
print(f"\n\n{'='*95}")
print("  PHASE 4: SEQUENCE PATTERNS (2-3 spin idx sequences before VT hits)")
print("=" * 95)

for target_name, target_codes in [("ACC+SPN", ACC_SPN)]:
    def is_t(row, tc=target_codes): return row['is_triple'] and row['s1'] in tc
    n_t = sum(1 for r in rows if is_t(r))
    base = n_t / N

    # 2-spin bigrams: (prev_prev reel, prev reel) -> hit rate
    print(f"\n  2-spin r2 bigrams -> {target_name} hit rate:")
    print(f"  {'Bigram':>12} {'N':>5} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'p':>8}")
    print(f"  {'-'*50}")
    bigram_results = []
    for v1 in range(9):
        for v2 in range(9):
            n_sig = hits = 0
            for i in range(2, N):
                if rows[i-2]['r2'] == v1 and rows[i-1]['r2'] == v2:
                    n_sig += 1
                    if is_t(rows[i]): hits += 1
            if n_sig >= 20:
                rate = hits/n_sig
                lift = rate/base if base else 0
                pval = fisher_p(hits, n_sig, base)
                if lift > 1.5 and pval < 0.1:
                    bigram_results.append((f"r2:{v1}->{v2}", n_sig, hits, rate, lift, pval))
    bigram_results.sort(key=lambda x: -x[4])
    for key, ns, h, rate, lift, pval in bigram_results[:10]:
        print(f"  {key:>12} {ns:>5} {h:>4} {100*rate:>5.2f}% {lift:>4.1f}x {pval:>8.4f}")

    # 2-spin r1 bigrams
    print(f"\n  2-spin r1 bigrams -> {target_name} hit rate:")
    print(f"  {'Bigram':>12} {'N':>5} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'p':>8}")
    print(f"  {'-'*50}")
    bigram_results_r1 = []
    for v1 in range(9):
        for v2 in range(9):
            n_sig = hits = 0
            for i in range(2, N):
                if rows[i-2]['r1'] == v1 and rows[i-1]['r1'] == v2:
                    n_sig += 1
                    if is_t(rows[i]): hits += 1
            if n_sig >= 20:
                rate = hits/n_sig
                lift = rate/base if base else 0
                pval = fisher_p(hits, n_sig, base)
                if lift > 1.5 and pval < 0.1:
                    bigram_results_r1.append((f"r1:{v1}->{v2}", n_sig, h, rate, lift, pval))
    bigram_results_r1.sort(key=lambda x: -x[4])
    for key, ns, h, rate, lift, pval in bigram_results_r1[:10]:
        print(f"  {key:>12} {ns:>5} {h:>4} {100*rate:>5.2f}% {lift:>4.1f}x {pval:>8.4f}")


# =====================================================================
#  PHASE 5: FULL 3-IDX TUPLE SCORING
# =====================================================================
print(f"\n\n{'='*95}")
print("  PHASE 5: FULL 3-IDX TUPLE SCORING (prev spin's r1,r2,r3 -> VT hit)")
print("=" * 95)

def is_vt_fn(row): return row['is_triple'] and row['s1'] in ACC_SPN

# Count all (r1,r2,r3) tuples from prev spin and their hit rates
tuple_stats = defaultdict(lambda: {'n': 0, 'h': 0})
for i in range(1, N):
    prev = rows[i-1]
    key = (prev['r1'], prev['r2'], prev['r3'])
    tuple_stats[key]['n'] += 1
    if is_vt_fn(rows[i]): tuple_stats[key]['h'] += 1

# Filter to significant tuples
print(f"\n  Top tuples by lift (n>=15, hits>=2, p<0.10):")
print(f"  {'Tuple':>12} {'N':>5} {'Hits':>4} {'Rate':>7} {'Lift':>5} {'p':>8}")
print(f"  {'-'*50}")
top_tuples = []
for key, d in tuple_stats.items():
    if d['n'] < 15 or d['h'] < 2: continue
    rate = d['h']/d['n']
    lift = rate/base_rate if base_rate else 0
    pval = fisher_p(d['h'], d['n'], base_rate)
    if lift > 1.5 and pval < 0.10:
        top_tuples.append((key, d['n'], d['h'], rate, lift, pval))
top_tuples.sort(key=lambda x: -x[4])
for key, ns, h, rate, lift, pval in top_tuples[:20]:
    print(f"  ({key[0]},{key[1]},{key[2]}){' ':>4} {ns:>5} {h:>4} {100*rate:>6.2f}% {lift:>4.1f}x {pval:>8.4f}")

# Dead tuples (n>=20, 0 hits)
print(f"\n  Dead tuples (n>=20, 0 hits):")
dead_tuples = [(k, d['n']) for k, d in tuple_stats.items() if d['h']==0 and d['n']>=20]
dead_tuples.sort(key=lambda x: -x[1])
for key, ns in dead_tuples[:15]:
    print(f"  ({key[0]},{key[1]},{key[2]}){' ':>4} 0/{ns}")


# =====================================================================
#  PHASE 6: CROSS-TYPE INTERACTION (does recent attack/steal predict VT?)
# =====================================================================
print(f"\n\n{'='*95}")
print("  PHASE 6: CROSS-TYPE INTERACTION")
print("=" * 95)

# For each other triple type: hit rate of VT within N spins after
print(f"\n  VT hit rate within window after each triple type:")
print(f"  {'After':>12} {'Window':>6} {'N':>5} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*55}")

for other_type, other_code in [('attack', 3), ('steal', 4), ('shield', 5), ('coin', 1), ('goldSack', 2)]:
    other_pos = [i for i in range(N) if rows[i]['is_triple'] and rows[i]['s1'] == other_code]
    for win_size in [3, 5, 10]:
        n_check = hits = 0
        for pos in other_pos:
            for j in range(1, min(win_size+1, N-pos)):
                n_check += 1
                if is_vt(rows[pos+j]): hits += 1
        if n_check == 0: continue
        rate = hits/n_check
        lift = rate/base_rate if base_rate else 0
        pval = fisher_p(hits, n_check, base_rate)
        print(f"  {other_type:>12} {win_size:>6} {n_check:>5} {hits:>4} {100*rate:>5.2f}% {lift:>4.1f}x {pval:>8.4f}")


# =====================================================================
#  PHASE 7: TRANSITION MATRIX (idx position transitions before VT)
# =====================================================================
print(f"\n\n{'='*95}")
print("  PHASE 7: r2 TRANSITION PATTERNS (prev->current r2 value for VT spins)")
print("=" * 95)

print(f"\n  r2 transition: prev_spin_r2 -> current_spin_r2 when current IS VT:")
trans_vt = defaultdict(int)
trans_all = defaultdict(int)
for i in range(1, N):
    key = (rows[i-1]['r2'], rows[i]['r2'])
    trans_all[key] += 1
    if is_vt(rows[i]):
        trans_vt[key] += 1

print(f"  {'From->To':>10} {'N':>5} {'VT':>4} {'Rate':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*45}")
trans_results = []
for key in trans_all:
    n_a = trans_all[key]
    n_v = trans_vt.get(key, 0)
    if n_a < 15 or n_v < 2: continue
    rate = n_v/n_a
    lift = rate/base_rate if base_rate else 0
    pval = fisher_p(n_v, n_a, base_rate)
    if lift > 1.5 and pval < 0.15:
        trans_results.append((f"r2:{key[0]}->{key[1]}", n_a, n_v, rate, lift, pval))
trans_results.sort(key=lambda x: -x[4])
for label, na, nv, rate, lift, pval in trans_results[:15]:
    print(f"  {label:>10} {na:>5} {nv:>4} {100*rate:>5.2f}% {lift:>4.1f}x {pval:>8.4f}")


# =====================================================================
#  PHASE 8: CONDITIONAL SIGNALS (post-specific-result prediction)
# =====================================================================
print(f"\n\n{'='*95}")
print("  PHASE 8: POST-RESULT CONDITIONING")
print("=" * 95)

# After a non-triple spin, check if the result symbol predicts next VT
print(f"\n  After non-triple spin with s1=X, VT hit rate on next spin:")
print(f"  {'Prev s1':>12} {'N':>5} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*50}")
for sym_code, sym_name in sorted(SYM_NAME.items()):
    n_sig = hits = 0
    for i in range(1, N):
        if not rows[i-1]['is_triple'] and rows[i-1]['s1'] == sym_code:
            n_sig += 1
            if is_vt(rows[i]): hits += 1
    if n_sig < 20: continue
    rate = hits/n_sig if n_sig else 0
    lift = rate/base_rate if base_rate else 0
    pval = fisher_p(hits, n_sig, base_rate)
    marker = " <<<" if lift > 1.3 and pval < 0.05 else ""
    print(f"  {sym_name:>12} {n_sig:>5} {hits:>4} {100*rate:>5.2f}% {lift:>4.1f}x {pval:>8.4f}{marker}")

# After triple vs non-triple
print(f"\n  After TRIPLE vs non-triple:")
for label, cond in [("after triple", lambda r: r['is_triple']),
                     ("after non-triple", lambda r: not r['is_triple'])]:
    n_sig = hits = 0
    for i in range(1, N):
        if cond(rows[i-1]):
            n_sig += 1
            if is_vt(rows[i]): hits += 1
    rate = hits/n_sig if n_sig else 0
    lift = rate/base_rate if base_rate else 0
    pval = fisher_p(hits, n_sig, base_rate)
    print(f"  {label:>18}: {n_sig:>5} spins, {hits} VT, {100*rate:.2f}% ({lift:.2f}x, p={pval:.4f})")


# =====================================================================
#  PHASE 9: RE-DISCOVERED COMBINED SCORER (ACC+SPN on merged data)
# =====================================================================
print(f"\n\n{'='*95}")
print("  PHASE 9: RE-DISCOVERED COMBINED SCORER (ACC+SPN on 3,864 spins)")
print("=" * 95)

indiv_c, pairs_c, n_c = discover_signals(ACC_SPN, rows, lag=1)
pos_ic = [s for s in indiv_c if s['dir']=='+']
neg_ic = [s for s in indiv_c if s['dir']=='-']
pos_pc = [p for p in pairs_c if p['dir']=='+']
neg_pc = [p for p in pairs_c if p['dir']=='-']

print(f"\n  L1 Signals (lag-1):")
print(f"    Positive idx ({len(pos_ic)}):")
for s in sorted(pos_ic, key=lambda x: -x['lift_pp']):
    print(f"      {s['key']:>6}: +{s['lift_pp']:.2f}pp, {s['cv']}/5 CV, "
          f"{s['hits']}/{s['n']} ({100*s['rate']:.1f}%), w={s['weight']}")
print(f"    Negative idx ({len(neg_ic)}):")
for s in sorted(neg_ic, key=lambda x: x['lift_pp']):
    print(f"      {s['key']:>6}: {s['lift_pp']:+.2f}pp, {s['cv']}/5 CV, "
          f"{s['hits']}/{s['n']} ({100*s['rate']:.1f}%), w={s['weight']}")
print(f"    Positive pairs ({len(pos_pc)}):")
for p in sorted(pos_pc, key=lambda x: -x['lift_pp'])[:12]:
    print(f"      {p['key']:>16}: +{p['lift_pp']:.2f}pp, {p['cv']}/5 CV, "
          f"{p['hits']}/{p['n']}, w={p['weight']}")
print(f"    Dead pairs n>=50 ({len(neg_pc)}):")
for p in sorted(neg_pc, key=lambda x: x['n'])[:8]:
    print(f"      {p['key']:>16}: 0/{p['n']} DEAD, w={p['weight']}")

# L2 validation for combined type
l2_val_c = validate_l2_per_type(rows, ACC_SPN)
print(f"\n  L2 validation (ACC+SPN):")
print(f"  {'Sig':>4} {'N':>5} {'Hits':>4} {'Rate':>6} {'Lift':>8} {'CV':>4} {'Use':>6}")
print(f"  {'-'*42}")
comb_l2_inc = {}
for sig in ALL_L2:
    if sig not in l2_val_c: continue
    v = l2_val_c[sig]
    w = 0
    if v['cv'] >= 4:
        w = 1 if v['lift_pp'] > 0 else -1
    marker = f"w={w:+d}" if w != 0 else "SKIP"
    print(f"  {sig:>4} {v['n']:>5} {v['hits']:>4} {100*v['rate']:>5.1f}% {v['lift_pp']:>+7.2f}pp {v['cv']}/5 {marker:>6}")
    if w != 0: comb_l2_inc[sig] = w
print(f"  -> Using: {dict(comb_l2_inc)}")

l1_scorer_c, max_l1_c = build_l1_scorer(indiv_c, pairs_c)
comb_l2_fn = make_type_l2(comb_l2_inc)
def l1_fn_new(prev): return l1_scorer_c(prev['r1'], prev['r2'], prev['r3'])
new_res, new_dist, new_l1, new_l2 = run_sim(rows, ACC_SPN, l1_fn_new, comb_l2_fn, THRESHOLDS)

print_dist(new_dist, n_vt, base_rate)
print_kpi(new_res, "NEW combined (re-discovered L1 + type-specific L2)", base_rate)


# =====================================================================
#  PHASE 10: SPLIT ACC/SPN INDIVIDUAL
# =====================================================================
print(f"\n\n{'='*95}")
print("  PHASE 10: SPLIT ACC and SPN (individual type-specific scorers)")
print("=" * 95)

for tname, tcodes in [('ACC', [30]), ('SPN', [6])]:
    n_t = sum(1 for r in rows if r['is_triple'] and r['s1'] in tcodes)
    brate = n_t / N
    print(f"\n  {'#'*70}")
    print(f"  # {tname}: {n_t} hits, {100*brate:.2f}%, 1 per {N/max(n_t,1):.0f}")
    print(f"  {'#'*70}")

    indiv, pairs, _ = discover_signals(tcodes, rows, lag=1)
    pos_i = [s for s in indiv if s['dir']=='+']
    neg_i = [s for s in indiv if s['dir']=='-']
    pos_p = [p for p in pairs if p['dir']=='+']
    neg_p = [p for p in pairs if p['dir']=='-']

    print(f"\n  L1: +idx={len(pos_i)}, -idx={len(neg_i)}, +pair={len(pos_p)}, dead={len(neg_p)}")
    for s in sorted(pos_i, key=lambda x: -x['lift_pp']):
        print(f"    + {s['key']:>6}: +{s['lift_pp']:.2f}pp, {s['cv']}/5, {s['hits']}/{s['n']}, w={s['weight']}")
    for s in sorted(neg_i, key=lambda x: x['lift_pp'])[:5]:
        print(f"    - {s['key']:>6}: {s['lift_pp']:+.2f}pp, {s['cv']}/5, {s['hits']}/{s['n']}, w={s['weight']}")
    for p in sorted(pos_p, key=lambda x: -x['lift_pp'])[:6]:
        print(f"    + {p['key']:>16}: +{p['lift_pp']:.2f}pp, {p['cv']}/5, {p['hits']}/{p['n']}, w={p['weight']}")
    for p in sorted(neg_p, key=lambda x: x['n'])[:4]:
        print(f"    - {p['key']:>16}: 0/{p['n']} DEAD, w={p['weight']}")

    l2v = validate_l2_per_type(rows, tcodes)
    print(f"\n  L2 per-type:")
    t_l2 = {}
    for sig in ALL_L2:
        if sig not in l2v: continue
        v = l2v[sig]
        w = 0
        if v['cv'] >= 4: w = 1 if v['lift_pp'] > 0 else -1
        m = f"w={w:+d}" if w != 0 else "SKIP"
        print(f"    {sig}: {v['n']:>5}n, {v['hits']:>3}h, {v['lift_pp']:>+6.2f}pp, {v['cv']}/5 -> {m}")
        if w != 0: t_l2[sig] = w
    print(f"    Using: {dict(t_l2)}")

    l1s, mx = build_l1_scorer(indiv, pairs)
    t_l2_fn = make_type_l2(t_l2)
    def mk_l1(scorer):
        def fn(prev): return scorer(prev['r1'], prev['r2'], prev['r3'])
        return fn
    res, dist, l1a, l2a = run_sim(rows, tcodes, mk_l1(l1s), t_l2_fn, THRESHOLDS)
    print_dist(dist, n_t, brate)
    print_kpi(res, f"{tname} (type-specific L1+L2)", brate)

    # Breakdown
    print(f"\n  Component breakdown (>=2):")
    for mode, u1, u2 in [('L1-only',1,0),('L2-only',0,1),('Both',1,1)]:
        b = c = 0
        for i in range(1, N):
            s = u1*l1a[i] + u2*l2a[i]
            if s >= 2:
                b += 1
                if rows[i]['is_triple'] and rows[i]['s1'] in tcodes: c += 1
        pr = c/b if b else 0
        cr = c/n_t if n_t else 0
        bph = b/c if c else float('inf')
        bph_s = f"{bph:.1f}" if bph < 9999 else "inf"
        print(f"    {mode:>8}: bets={b:>5}, catch={c:>2}/{n_t}, cr={100*cr:.1f}%, prec={100*pr:.2f}%, b/h={bph_s}")


# =====================================================================
#  PHASE 11: HEAD-TO-HEAD
# =====================================================================
print(f"\n\n{'='*95}")
print("  PHASE 11: HEAD-TO-HEAD COMPARISON")
print("=" * 95)

print(f"\n  Target: ACC+SPN = {n_vt} hits / {N} spins ({100*base_rate:.2f}%)")
print(f"\n  {'System':>32} | {'Prof':>12} {'Bets':>5} {'Cat':>4} {'CatR':>5} "
      f"{'Prec':>7} {'B/H':>6} {'Lift':>5} {'p':>8}")
print(f"  {'-'*95}")

for name, res in [("CURRENT APP (baseline)", base_res), ("NEW re-discovered", new_res)]:
    for prof in ['>=2 (BAL)', '>=3 (TGT)', '>=5', '>=6 (ULT)', '>=8 (SNP)', '>=10']:
        r = res[prof]
        bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
        print(f"  {name:>32} | {prof:>12} {r['bets']:>5} {r['catches']:>4} "
              f"{100*r['cr']:>4.1f}% {100*r['prec']:>6.2f}% {bph:>6} "
              f"{r['lift']:>4.1f}x {r['pval']:>8.4f}")
    print()


# =====================================================================
#  Save
# =====================================================================
out = {'baseline': {}, 'new_combined': {}}
for name in base_res:
    r = base_res[name]
    out['baseline'][name] = {k: (round(v,6) if isinstance(v,float) else v) for k,v in r.items()}
for name in new_res:
    r = new_res[name]
    out['new_combined'][name] = {k: (round(v,6) if isinstance(v,float) else v) for k,v in r.items()}

out_path = Path(__file__).parent / "81_proper_results.json"
with open(out_path, 'w') as f:
    json.dump(out, f, indent=2)
print(f"\nResults saved to {out_path}")
print("\nDONE")
