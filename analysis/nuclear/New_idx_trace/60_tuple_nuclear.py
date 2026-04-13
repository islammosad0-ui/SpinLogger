#!/usr/bin/env python3
"""
60_tuple_nuclear.py - Full tuple analysis: every combination of idx values
as predictors for next-N valuable triples.

Tests:
  1. Full (r1,r2,r3) triplet -> next valuable (729 possible states)
  2. All 2-reel pairs: (r1,r2), (r1,r3), (r2,r3) -> next valuable
  3. Consecutive-spin tuples: (spin_N state, spin_N-1 state) -> next valuable
  4. 2-spin history: (prev_triple, cur_r1, cur_r2, cur_r3) -> next valuable
  5. 3-spin sliding window tuples
  6. Full grid tuple: 3x3 visible symbols as 9-tuple
  7. Diagonal patterns (Zoki: top-left + bottom-right)
  8. Symbol-level tuples (not just idx)
  9. Temporal CV on ALL promising tuples
  10. Composite tuple scorer
"""

import csv, math, json
from collections import Counter, defaultdict
from pathlib import Path
from itertools import combinations

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_F = ROOT / "data" / "Ahmed" / "spin_history_Ahmed_enriched_v2.csv"

REEL2_STRIP = {0:'attack', 1:'coin', 2:'shield', 3:'goldSack', 4:'steal',
               5:'coin', 6:'spins', 7:'goldSack', 8:'accumulation'}

rows = []
with open(CSV_F, newline='') as f:
    for r in csv.DictReader(f):
        r['r1'] = int(r['r1_idx'])
        r['r2'] = int(r['r2_idx'])
        r['r3'] = int(r['r3_idx'])
        r['is_triple'] = r['is_triple'] == 'True'
        r['is_valuable'] = r['is_valuable'] == 'True'
        r['sn'] = int(r['sn'])
        rows.append(r)

N = len(rows)
n_folds = 5
fold_size = N // n_folds
base_v = sum(1 for r in rows if r['is_valuable']) / N
base_t = sum(1 for r in rows if r['is_triple']) / N

def P(s=''):
    print(s)

def wilson_ci(hits, total, z=1.96):
    if total == 0: return 0, 0, 0
    p = hits / total
    denom = 1 + z*z/total
    center = (p + z*z/(2*total)) / denom
    spread = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denom
    return p, max(0, center-spread), min(1, center+spread)

def temporal_cv(rows, feature_fn, target_fn, n_folds=5):
    """Returns list of (fold, match_rate, other_rate, spread, n_match, n_other)."""
    results = []
    for fold in range(n_folds):
        s = fold * fold_size
        e = s + fold_size if fold < n_folds - 1 else N
        fr = rows[s:e]
        mh, mn, oh, on = 0, 0, 0, 0
        for i in range(len(fr) - 1):
            feat = feature_fn(fr, i)
            if feat is None:
                continue
            tgt = target_fn(fr, i)
            if feat:
                mn += 1; mh += int(tgt)
            else:
                on += 1; oh += int(tgt)
        mr = mh/mn if mn > 0 else 0
        ore = oh/on if on > 0 else 0
        results.append((fold, mr, ore, mr-ore, mn, on))
    return results

# =====================================================================
P("=" * 80)
P("  60_TUPLE_NUCLEAR -- Every tuple combination, pushed to the limit")
P("=" * 80)
P(f"N={N}, base triple={100*base_t:.1f}%, base valuable={100*base_v:.1f}%")

# =====================================================================
# 1. Full (r1,r2,r3) triplet -> next-1 valuable
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 1: Full (r1,r2,r3) triplet -> next-1 valuable")
P("=" * 80)

triplet_stats = defaultdict(lambda: [0, 0])  # [next_val_hits, count]
for i in range(N-1):
    key = (rows[i]['r1'], rows[i]['r2'], rows[i]['r3'])
    triplet_stats[key][1] += 1
    triplet_stats[key][0] += int(rows[i+1]['is_valuable'])

# Base rate for next-1 valuable
base_nv = sum(1 for i in range(N-1) if rows[i+1]['is_valuable']) / (N-1)
P(f"Base next-1 valuable: {100*base_nv:.2f}%")
P(f"Unique triplets observed: {len(triplet_stats)}")
P(f"Triplets with n>=5: {sum(1 for v in triplet_stats.values() if v[1] >= 5)}")
P(f"Triplets with n>=10: {sum(1 for v in triplet_stats.values() if v[1] >= 10)}")

# Sort by rate (n>=5)
ranked = []
for key, (hits, total) in triplet_stats.items():
    if total < 5:
        continue
    p, lo, hi = wilson_ci(hits, total)
    ranked.append((key, hits, total, p, lo, hi, p - base_nv))

ranked.sort(key=lambda x: -x[6])
P(f"\n  Top 15 triplets (highest next-1 valuable rate, n>=5):")
P(f"  {'Triplet':>15} {'n':>4} {'hits':>4} {'rate':>6} {'95% CI':>15} {'lift':>7}")
for key, hits, total, p, lo, hi, lift in ranked[:15]:
    sym = tuple(REEL2_STRIP[k] for k in key)
    P(f"  {str(key):>15} {total:>4} {hits:>4} {100*p:>5.1f}% [{100*lo:>5.1f}%, {100*hi:>5.1f}%] "
      f"{100*lift:>+6.1f}pp  ({sym[0][:3]},{sym[1][:3]},{sym[2][:3]})")

P(f"\n  Bottom 15 triplets (lowest rate, n>=5):")
ranked.sort(key=lambda x: x[6])
for key, hits, total, p, lo, hi, lift in ranked[:15]:
    sym = tuple(REEL2_STRIP[k] for k in key)
    P(f"  {str(key):>15} {total:>4} {hits:>4} {100*p:>5.1f}% [{100*lo:>5.1f}%, {100*hi:>5.1f}%] "
      f"{100*lift:>+6.1f}pp  ({sym[0][:3]},{sym[1][:3]},{sym[2][:3]})")

# =====================================================================
# 2. All 2-reel pairs -> next-1 valuable (with CV)
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 2: All 2-reel pairs -> next-1 valuable (with temporal CV)")
P("=" * 80)

pair_configs = [
    ('r1,r2', lambda r: (r['r1'], r['r2'])),
    ('r1,r3', lambda r: (r['r1'], r['r3'])),
    ('r2,r3', lambda r: (r['r2'], r['r3'])),
]

all_pair_results = []

for pair_name, pair_fn in pair_configs:
    P(f"\n  --- {pair_name} ---")
    pair_stats = defaultdict(lambda: [0, 0])
    for i in range(N-1):
        key = pair_fn(rows[i])
        pair_stats[key][1] += 1
        pair_stats[key][0] += int(rows[i+1]['is_valuable'])

    candidates = []
    for key, (hits, total) in pair_stats.items():
        if total < 15:
            continue
        p, lo, hi = wilson_ci(hits, total)
        lift = p - base_nv

        # CV
        cv_lifts = []
        for fold in range(n_folds):
            s = fold * fold_size
            e = s + fold_size if fold < n_folds - 1 else N
            fh, ft, fbh, fbt = 0, 0, 0, 0
            for i in range(s, min(e, N-1)):
                k = pair_fn(rows[i])
                nv = int(rows[i+1]['is_valuable'])
                if k == key:
                    ft += 1; fh += nv
                fbt += 1; fbh += nv
            if ft >= 3:
                fr = fh/ft if ft > 0 else 0
                fbr = fbh/fbt if fbt > 0 else 0
                cv_lifts.append(fr - fbr)

        pos = sum(1 for l in cv_lifts if l > 0)
        neg = sum(1 for l in cv_lifts if l < 0)
        n_cv = len(cv_lifts)
        candidates.append((pair_name, key, hits, total, p, lo, hi, lift, pos, neg, n_cv))
        all_pair_results.append(candidates[-1])

    candidates.sort(key=lambda x: -x[7])
    P(f"  {'Pair':>10} {'n':>4} {'rate':>6} {'lift':>7} {'CV':>8} {'syms':>20}")
    for _, key, hits, total, p, lo, hi, lift, pos, neg, n_cv in candidates[:10]:
        sym = tuple(REEL2_STRIP[k] for k in key)
        flag = "***" if (pos == n_cv and lift > 0.03 and n_cv >= 4) else \
               "**" if (pos >= 4 and lift > 0.02) else \
               "*" if pos >= 3 and lift > 0 else ""
        P(f"  {str(key):>10} {total:>4} {100*p:>5.1f}% {100*lift:>+6.1f}pp "
          f"{pos}/{n_cv}+ {flag:>3}  ({sym[0][:4]},{sym[1][:4]})")

# =====================================================================
# 3. Consecutive-spin tuples: (prev_state -> cur_state) -> next valuable
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 3: 2-spin history (prev_triplet, cur_triplet) -> next valuable")
P("=" * 80)

# Use simplified state: (is_triple, r2_idx) since r2 is cleanest reel
twospin_stats = defaultdict(lambda: [0, 0])
for i in range(1, N-1):
    prev_state = (rows[i-1]['is_triple'], rows[i-1]['r2'])
    cur_state = (rows[i]['is_triple'], rows[i]['r2'])
    key = (prev_state, cur_state)
    twospin_stats[key][1] += 1
    twospin_stats[key][0] += int(rows[i+1]['is_valuable'])

ranked2 = []
for key, (hits, total) in twospin_stats.items():
    if total < 8:
        continue
    p = hits / total
    ranked2.append((key, hits, total, p, p - base_nv))

ranked2.sort(key=lambda x: -x[4])
P(f"\n  Top 15 (prev_state, cur_state) -> next valuable (n>=8):")
P(f"  {'(prev_tri,prev_r2)':>20} {'(cur_tri,cur_r2)':>20} {'n':>4} {'rate':>6} {'lift':>7}")
for key, hits, total, p, lift in ranked2[:15]:
    P(f"  {str(key[0]):>20} {str(key[1]):>20} {total:>4} {100*p:>5.1f}% {100*lift:>+6.1f}pp")

P(f"\n  Bottom 10:")
ranked2.sort(key=lambda x: x[4])
for key, hits, total, p, lift in ranked2[:10]:
    P(f"  {str(key[0]):>20} {str(key[1]):>20} {total:>4} {100*p:>5.1f}% {100*lift:>+6.1f}pp")

# =====================================================================
# 4. Extended history: last 2 spins' full (r1,r2,r3) -> next valuable
#    Too sparse for full triplets, so use (r2_prev, r2_cur) pair
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 4: r2 sequence tuple (r2[N-2], r2[N-1], r2[N]) -> next valuable")
P("=" * 80)

r2_seq_stats = defaultdict(lambda: [0, 0])
for i in range(2, N-1):
    key = (rows[i-2]['r2'], rows[i-1]['r2'], rows[i]['r2'])
    r2_seq_stats[key][1] += 1
    r2_seq_stats[key][0] += int(rows[i+1]['is_valuable'])

ranked3 = []
for key, (hits, total) in r2_seq_stats.items():
    if total < 5:
        continue
    p = hits / total
    ranked3.append((key, hits, total, p, p - base_nv))

ranked3.sort(key=lambda x: -x[4])
P(f"\n  Top 15 r2 sequences -> next valuable (n>=5):")
P(f"  {'(r2[-2],r2[-1],r2[0])':>25} {'n':>4} {'rate':>6} {'lift':>7} {'symbols':>25}")
for key, hits, total, p, lift in ranked3[:15]:
    sym = tuple(REEL2_STRIP[k] for k in key)
    P(f"  {str(key):>25} {total:>4} {100*p:>5.1f}% {100*lift:>+6.1f}pp  {str(sym):>25}")

# =====================================================================
# 5. Diagonal tuples: (top-left, bottom-right) = Zoki's tells
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 5: Diagonal tuples (Zoki's top-left + bottom-right)")
P("=" * 80)

# Full diagonals: TL-BR and TR-BL
diag_stats = defaultdict(lambda: [0, 0])
anti_diag_stats = defaultdict(lambda: [0, 0])

for i in range(N-1):
    r1, r2, r3 = rows[i]['r1'], rows[i]['r2'], rows[i]['r3']
    tl = (r1 - 1) % 9  # top of reel 1
    br = (r3 + 1) % 9  # bottom of reel 3
    tr = (r3 - 1) % 9  # top of reel 3
    bl = (r1 + 1) % 9  # bottom of reel 1
    center = r2         # center of reel 2

    diag_key = (tl, center, br)  # main diagonal TL -> center -> BR
    anti_key = (tr, center, bl)  # anti-diagonal TR -> center -> BL

    diag_stats[diag_key][1] += 1
    diag_stats[diag_key][0] += int(rows[i+1]['is_valuable'])
    anti_diag_stats[anti_key][1] += 1
    anti_diag_stats[anti_key][0] += int(rows[i+1]['is_valuable'])

P(f"\n  Main diagonal (TL, center, BR) -> next valuable:")
diag_ranked = []
for key, (hits, total) in diag_stats.items():
    if total < 5:
        continue
    p = hits/total
    diag_ranked.append((key, hits, total, p, p - base_nv))

diag_ranked.sort(key=lambda x: -x[4])
P(f"  {'Diagonal':>15} {'n':>4} {'rate':>6} {'lift':>7}")
for key, hits, total, p, lift in diag_ranked[:15]:
    sym = tuple(REEL2_STRIP[k] for k in key)
    P(f"  {str(key):>15} {total:>4} {100*p:>5.1f}% {100*lift:>+6.1f}pp  ({sym[0][:3]},{sym[1][:3]},{sym[2][:3]})")

P(f"\n  Anti-diagonal (TR, center, BL) -> next valuable:")
adiag_ranked = []
for key, (hits, total) in anti_diag_stats.items():
    if total < 5:
        continue
    p = hits/total
    adiag_ranked.append((key, hits, total, p, p - base_nv))

adiag_ranked.sort(key=lambda x: -x[4])
P(f"  {'Anti-diag':>15} {'n':>4} {'rate':>6} {'lift':>7}")
for key, hits, total, p, lift in adiag_ranked[:15]:
    sym = tuple(REEL2_STRIP[k] for k in key)
    P(f"  {str(key):>15} {total:>4} {100*p:>5.1f}% {100*lift:>+6.1f}pp  ({sym[0][:3]},{sym[1][:3]},{sym[2][:3]})")

# =====================================================================
# 6. Symbol-level tuples (using reel 2 strip mapping for all reels)
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 6: Symbol tuples (s1, s2, s3) -> next valuable")
P("=" * 80)

sym_stats = defaultdict(lambda: [0, 0])
for i in range(N-1):
    key = (REEL2_STRIP[rows[i]['r1']], REEL2_STRIP[rows[i]['r2']], REEL2_STRIP[rows[i]['r3']])
    sym_stats[key][1] += 1
    sym_stats[key][0] += int(rows[i+1]['is_valuable'])

sym_ranked = []
for key, (hits, total) in sym_stats.items():
    if total < 8:
        continue
    p = hits/total
    sym_ranked.append((key, hits, total, p, p - base_nv))

sym_ranked.sort(key=lambda x: -x[4])
P(f"\n  Top 15 symbol tuples (n>=8):")
P(f"  {'(s1, s2, s3)':>30} {'n':>4} {'rate':>6} {'lift':>7}")
for key, hits, total, p, lift in sym_ranked[:15]:
    P(f"  {str(key):>30} {total:>4} {100*p:>5.1f}% {100*lift:>+6.1f}pp")

P(f"\n  Bottom 10:")
sym_ranked.sort(key=lambda x: x[4])
for key, hits, total, p, lift in sym_ranked[:10]:
    P(f"  {str(key):>30} {total:>4} {100*p:>5.1f}% {100*lift:>+6.1f}pp")

# =====================================================================
# 7. FULL TEMPORAL CV on ALL promising tuples (>= +5pp lift, n>=10)
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 7: Temporal CV validation on ALL promising tuples")
P("=" * 80)

# Collect all candidates from sections above
P("\n  Gathering candidates with lift >= +5pp and n >= 10...")

candidates_for_cv = []

# From section 1: full triplets
for key, (hits, total) in triplet_stats.items():
    if total < 10:
        continue
    p = hits/total
    lift = p - base_nv
    if lift >= 0.04:
        candidates_for_cv.append(('triplet', key, hits, total, p, lift,
            lambda r, k=key: (r['r1'], r['r2'], r['r3']) == k))

# From section 2: pairs
for pname, pfn in pair_configs:
    pair_s = defaultdict(lambda: [0, 0])
    for i in range(N-1):
        k = pfn(rows[i])
        pair_s[k][1] += 1
        pair_s[k][0] += int(rows[i+1]['is_valuable'])
    for key, (hits, total) in pair_s.items():
        if total < 10:
            continue
        p = hits/total
        lift = p - base_nv
        if lift >= 0.04:
            candidates_for_cv.append((f'pair_{pname}', key, hits, total, p, lift,
                lambda r, fn=pfn, k=key: fn(r) == k))

# From diagonals
for key, (hits, total) in diag_stats.items():
    if total < 10:
        continue
    p = hits/total
    lift = p - base_nv
    if lift >= 0.04:
        r1k, r2k, r3k = key
        candidates_for_cv.append(('diag', key, hits, total, p, lift,
            lambda r, a=r1k, b=r2k, c=r3k: ((r['r1']-1)%9 == a and r['r2'] == b and (r['r3']+1)%9 == c)))

P(f"  Found {len(candidates_for_cv)} candidates")

# Run CV on each
cv_results = []
for cat, key, hits, total, p, lift, match_fn in candidates_for_cv:
    fold_lifts = []
    fold_ns = []
    for fold in range(n_folds):
        s = fold * fold_size
        e = s + fold_size if fold < n_folds - 1 else N
        mh, mn, oh, on = 0, 0, 0, 0
        for i in range(s, min(e, N-1)):
            nv = int(rows[i+1]['is_valuable'])
            if match_fn(rows[i]):
                mn += 1; mh += nv
            else:
                on += 1; oh += nv
        mr = mh/mn if mn > 0 else 0
        ore = oh/on if on > 0 else 0
        if mn >= 2:
            fold_lifts.append(mr - ore)
            fold_ns.append(mn)

    if len(fold_lifts) < 3:
        continue

    pos = sum(1 for l in fold_lifts if l > 0)
    avg_lift = sum(fold_lifts) / len(fold_lifts)
    min_n = min(fold_ns) if fold_ns else 0
    cv_results.append((cat, key, total, p, lift, avg_lift, pos, len(fold_lifts), min_n, fold_lifts))

cv_results.sort(key=lambda x: (-x[6]/max(x[7],1), -x[5]))  # Sort by consistency then avg lift

P(f"\n  {'Type':>12} {'Key':>15} {'n':>4} {'rate':>6} {'raw_lift':>8} {'cv_avg':>7} {'consist':>8} {'folds':>30}")
P("  " + "-" * 110)
for cat, key, total, p, lift, avg_lift, pos, n_cv, min_n, folds in cv_results[:30]:
    fold_str = " ".join(f"{100*fl:+5.1f}" for fl in folds)
    flag = " ***" if pos == n_cv and avg_lift > 0.03 and n_cv >= 4 else \
           " **" if pos >= 4 and avg_lift > 0.02 else \
           " *" if pos >= 3 and avg_lift > 0.01 else ""
    P(f"  {cat:>12} {str(key):>15} {total:>4} {100*p:>5.1f}% {100*lift:>+7.1f}pp "
      f"{100*avg_lift:>+6.1f}pp {pos}/{n_cv}+{flag:>4} [{fold_str}]")

# =====================================================================
# 8. Multi-spin tuple: (triple_N-1, r1_N, r2_N, r3_N) -> next valuable
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 8: (was_prev_triple, cur_r1, cur_r2, cur_r3) -> next valuable")
P("=" * 80)

ext_stats = defaultdict(lambda: [0, 0])
for i in range(1, N-1):
    prev_tri = rows[i-1]['is_triple']
    key = (prev_tri, rows[i]['r1'], rows[i]['r2'], rows[i]['r3'])
    ext_stats[key][1] += 1
    ext_stats[key][0] += int(rows[i+1]['is_valuable'])

ext_ranked = []
for key, (hits, total) in ext_stats.items():
    if total < 5:
        continue
    p = hits/total
    ext_ranked.append((key, hits, total, p, p - base_nv))

ext_ranked.sort(key=lambda x: -x[4])
P(f"\n  Top 20 (n>=5):")
P(f"  {'(prev_tri, r1, r2, r3)':>28} {'n':>4} {'rate':>6} {'lift':>7}")
for key, hits, total, p, lift in ext_ranked[:20]:
    P(f"  {str(key):>28} {total:>4} {100*p:>5.1f}% {100*lift:>+6.1f}pp")

# =====================================================================
# 9. "Hot zone" detector: which idx regions cluster before valuable?
# Look at N-3..N-1 window patterns before a valuable triple
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 9: 3-spin window before valuable triples")
P("=" * 80)

# For each valuable triple, capture the 3-spin window before it
pre_valuable_patterns = []
pre_nonvaluable_patterns = []
for i in range(3, N):
    window = (rows[i-3]['r2'], rows[i-2]['r2'], rows[i-1]['r2'])
    if rows[i]['is_valuable']:
        pre_valuable_patterns.append(window)
    elif rows[i]['is_triple']:
        pre_nonvaluable_patterns.append(window)

P(f"\n  Pre-valuable windows: {len(pre_valuable_patterns)}")
P(f"  Pre-nonvaluable-triple windows: {len(pre_nonvaluable_patterns)}")

# Most common pre-valuable patterns
val_counter = Counter(pre_valuable_patterns)
nonval_counter = Counter(pre_nonvaluable_patterns)

P(f"\n  Top 15 pre-VALUABLE r2 windows (3-spin):")
P(f"  {'Pattern':>15} {'val_count':>9} {'nonval_count':>12} {'val_rate':>8}")
for pattern, count in val_counter.most_common(15):
    nv_count = nonval_counter.get(pattern, 0)
    rate = count / (count + nv_count) if (count + nv_count) > 0 else 0
    base_rate = len(pre_valuable_patterns) / (len(pre_valuable_patterns) + len(pre_nonvaluable_patterns))
    lift = rate - base_rate
    sym = tuple(REEL2_STRIP[k] for k in pattern)
    P(f"  {str(pattern):>15} {count:>9} {nv_count:>12} {100*rate:>7.1f}% ({100*lift:>+.1f}pp)  {sym}")

# =====================================================================
# 10. Composite tuple scorer with temporal CV
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 10: Composite tuple scorer")
P("=" * 80)

# Score each spin based on ALL validated signals
# Positive: r3_idx=5, r2_idx=4, r1_idx=4, pair(4,5), overdue
# Negative: r3_idx=1, r2_idx=6, r2_idx=7, r1_idx=3, pair(3,8)
# Anti-clustering: bet less after valuable

for i, r in enumerate(rows):
    score = 0

    # Idx signals
    if r['r3'] == 5: score += 2
    if r['r2'] == 4: score += 1
    if r['r1'] == 4: score += 1
    if r['r3'] == 1: score -= 1
    if r['r2'] == 6: score -= 1
    if r['r2'] == 7: score -= 1
    if r['r1'] == 3: score -= 1

    # Pair signals
    if r['r1'] == 4 and r['r3'] == 5: score += 2
    if r['r1'] == 3 and r['r3'] == 8: score -= 1

    # Anti-clustering: recent valuable penalty
    if i >= 1 and rows[i-1]['is_valuable']: score -= 3
    if i >= 2 and rows[i-2]['is_valuable']: score -= 2
    if i >= 3 and rows[i-3]['is_valuable']: score -= 1

    # Overdue bonus
    last_val = -100
    for j in range(max(0, i-20), i):
        if rows[j]['is_valuable']:
            last_val = j
    gap = i - last_val
    if gap >= 15: score += 2
    elif gap >= 10: score += 1

    r['tuple_score'] = score

# Report distribution
score_dist = Counter(r['tuple_score'] for r in rows)
P(f"\nScore distribution: {dict(sorted(score_dist.items()))}")

# Bin into tiers
for r in rows:
    if r['tuple_score'] >= 4:
        r['tier'] = 'HOT'
    elif r['tuple_score'] >= 2:
        r['tier'] = 'WARM'
    elif r['tuple_score'] <= -3:
        r['tier'] = 'COLD'
    elif r['tuple_score'] <= -1:
        r['tier'] = 'COOL'
    else:
        r['tier'] = 'NEUTRAL'

# Temporal CV on tiers
P(f"\n--- Temporal CV: tuple score tiers -> next-1 valuable ---")
for fold in range(n_folds):
    s = fold * fold_size
    e = s + fold_size if fold < n_folds - 1 else N
    fr = rows[s:e]

    tier_stats = defaultdict(lambda: [0, 0])
    for i in range(len(fr) - 1):
        tier = fr[i]['tier']
        tier_stats[tier][0] += int(fr[i+1]['is_valuable'])
        tier_stats[tier][1] += 1

    parts = []
    for tier in ['HOT', 'WARM', 'NEUTRAL', 'COOL', 'COLD']:
        h, n = tier_stats[tier]
        rate = h/n if n > 0 else 0
        parts.append(f"{tier}={100*rate:.1f}%({n})")

    P(f"  Fold {fold}: {' | '.join(parts)}")

# Overall
P(f"\n--- Overall tier rates ---")
for tier in ['HOT', 'WARM', 'NEUTRAL', 'COOL', 'COLD']:
    match = [r for r in rows[:-1] if r['tier'] == tier]
    hits = sum(1 for i, r in enumerate(rows[:-1]) if r['tier'] == tier and rows[rows.index(r)+1]['is_valuable'])
    if match:
        rate = hits / len(match)
        p, lo, hi = wilson_ci(hits, len(match))
        P(f"  {tier:>8}: {100*rate:.1f}% [{100*lo:.1f}%, {100*hi:.1f}%] n={len(match)} "
          f"(lift={100*(rate-base_nv):+.1f}pp)")

# =====================================================================
# 11. The kitchen sink: try ALL possible feature combos
# =====================================================================
P("\n" + "=" * 80)
P("  SECTION 11: Exhaustive feature combo search (brute force)")
P("=" * 80)

# Define all atomic features
features = {
    'r1=0': lambda r: r['r1'] == 0,
    'r1=1': lambda r: r['r1'] == 1,
    'r1=2': lambda r: r['r1'] == 2,
    'r1=3': lambda r: r['r1'] == 3,
    'r1=4': lambda r: r['r1'] == 4,
    'r1=5': lambda r: r['r1'] == 5,
    'r1=6': lambda r: r['r1'] == 6,
    'r1=7': lambda r: r['r1'] == 7,
    'r2=0': lambda r: r['r2'] == 0,
    'r2=1': lambda r: r['r2'] == 1,
    'r2=2': lambda r: r['r2'] == 2,
    'r2=3': lambda r: r['r2'] == 3,
    'r2=4': lambda r: r['r2'] == 4,
    'r2=5': lambda r: r['r2'] == 5,
    'r2=6': lambda r: r['r2'] == 6,
    'r2=7': lambda r: r['r2'] == 7,
    'r2=8': lambda r: r['r2'] == 8,
    'r3=0': lambda r: r['r3'] == 0,
    'r3=1': lambda r: r['r3'] == 1,
    'r3=3': lambda r: r['r3'] == 3,
    'r3=4': lambda r: r['r3'] == 4,
    'r3=5': lambda r: r['r3'] == 5,
    'r3=8': lambda r: r['r3'] == 8,
    'is_triple': lambda r: r['is_triple'],
    'is_valuable': lambda r: r['is_valuable'],
}

# Test every single and pair of features as AND combination
P(f"\n  Testing {len(features)} single features + {len(features)*(len(features)-1)//2} pairs...")

best_combos = []

# Singles
for fname, ffn in features.items():
    hits, total = 0, 0
    for i in range(N-1):
        if ffn(rows[i]):
            total += 1
            hits += int(rows[i+1]['is_valuable'])
    if total < 15:
        continue
    p = hits/total
    lift = p - base_nv
    if abs(lift) > 0.02:
        # CV
        cv_pos = 0
        cv_n = 0
        for fold in range(n_folds):
            s = fold * fold_size
            e = s + fold_size if fold < n_folds - 1 else N
            fh, ft, fbh, fbt = 0, 0, 0, 0
            for i in range(s, min(e, N-1)):
                nv = int(rows[i+1]['is_valuable'])
                if ffn(rows[i]):
                    ft += 1; fh += nv
                fbt += 1; fbh += nv
            if ft >= 3:
                cv_n += 1
                fr = fh/ft; fbr = fbh/fbt
                if fr - fbr > 0: cv_pos += 1

        best_combos.append((fname, total, p, lift, cv_pos, cv_n))

# Pairs (AND)
feat_items = list(features.items())
for i in range(len(feat_items)):
    for j in range(i+1, len(feat_items)):
        fn1, ff1 = feat_items[i]
        fn2, ff2 = feat_items[j]
        combo_name = f"{fn1} AND {fn2}"

        hits, total = 0, 0
        for k in range(N-1):
            if ff1(rows[k]) and ff2(rows[k]):
                total += 1
                hits += int(rows[k+1]['is_valuable'])
        if total < 8:
            continue
        p = hits/total
        lift = p - base_nv
        if lift > 0.05:  # Only strong positive
            cv_pos = 0
            cv_n = 0
            for fold in range(n_folds):
                s = fold * fold_size
                e = s + fold_size if fold < n_folds - 1 else N
                fh, ft, fbh, fbt = 0, 0, 0, 0
                for k in range(s, min(e, N-1)):
                    nv = int(rows[k+1]['is_valuable'])
                    if ff1(rows[k]) and ff2(rows[k]):
                        ft += 1; fh += nv
                    fbt += 1; fbh += nv
                if ft >= 2:
                    cv_n += 1
                    fr = fh/ft; fbr = fbh/fbt
                    if fr - fbr > 0: cv_pos += 1

            best_combos.append((combo_name, total, p, lift, cv_pos, cv_n))

best_combos.sort(key=lambda x: (-x[4]/max(x[5],1), -x[3]))
P(f"\n  Top 30 feature combos by CV consistency then lift:")
P(f"  {'Feature':>35} {'n':>4} {'rate':>6} {'lift':>7} {'CV':>6}")
for name, total, p, lift, cv_pos, cv_n in best_combos[:30]:
    flag = "***" if cv_pos == cv_n and lift > 0.03 and cv_n >= 4 else \
           "**" if cv_pos >= 4 and lift > 0.02 else \
           "*" if cv_pos >= 3 else ""
    P(f"  {name:>35} {total:>4} {100*p:>5.1f}% {100*lift:>+6.1f}pp {cv_pos}/{cv_n}+ {flag}")

P("\nDONE")
