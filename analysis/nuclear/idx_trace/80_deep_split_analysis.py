#!/usr/bin/env python3
"""
80_deep_split_analysis.py - DEEP per-type idx analysis with ACC/SPN split.
Merges Ahmed v2 (1,107) + Nick 59-col (2,757) = 3,864 spins.

For each of 7 types (ACC, SPN, SHIELD, ATTACK, STEAL, COIN, GOLDSACK):
  1. Individual + pair signal discovery with 5-fold temporal CV
  2. Composite L1 scorer construction (weighted signals)
  3. Layer 2 window pattern re-validation
  4. Combined L1+L2 strategy simulation
  5. Full KPI tables: catch rate, bets/hit, precision, lift, p-values
  6. Profile threshold sweep (BAL/TGT/ULT/SNP equivalent)
"""

import csv, json, math
from collections import defaultdict
from pathlib import Path
from scipy import stats as sp_stats

ROOT = Path(__file__).resolve().parents[3]

# =====================================================================
#  Data loading (same as 79)
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

type_counts = defaultdict(int)
for r in rows:
    if r['is_triple']: type_counts[r['reel_1']] += 1

print(f"Total: {N} spins ({len(ahmed)} Ahmed + {len(nick)} Nick)")
print(f"\nTriples by type:")
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {t:>15}: {c:>4} ({100*c/N:.2f}%, 1 per {N/max(c,1):.0f})")

# =====================================================================
#  CV helper
# =====================================================================
def temporal_cv(rows, condition_fn, target_fn, n_folds=5):
    fold_size = len(rows) // n_folds
    total_sig = total_hits = total_base_n = total_base_hits = 0
    fold_lifts = []
    for fold in range(n_folds):
        start = fold * fold_size
        end = start + fold_size if fold < n_folds - 1 else len(rows)
        sig_n = sig_h = base_n = base_h = 0
        for i in range(max(start, 1), end):
            hit = target_fn(rows[i])
            if condition_fn(rows[i-1]):
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

def wilson_ci(hits, n, z=1.96):
    if n == 0: return (0, 0)
    p = hits / n
    denom = 1 + z*z/n
    center = (p + z*z/(2*n)) / denom
    margin = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
    return (max(0, center - margin), min(1, center + margin))

def fisher_p(hits, n, base_rate):
    """One-sided Fisher exact test: P(X >= hits) under binomial(n, base_rate)"""
    from scipy.stats import binom
    return 1 - binom.cdf(hits - 1, n, base_rate)

# =====================================================================
#  TRIPLE TYPES
# =====================================================================
TYPES = {
    'accumulation': [30],
    'spins':        [6],
    'shield':       [5],
    'attack':       [3],
    'steal':        [4],
    'coin':         [1],
    'goldSack':     [2],
}

# =====================================================================
#  Phase 1: Signal discovery per type
# =====================================================================
def discover_signals(type_name, target_codes, rows):
    N = len(rows)
    def is_target(row): return row['is_triple'] and row['s1'] in target_codes
    n_target = sum(1 for r in rows if is_target(r))
    if n_target == 0: return [], [], n_target
    base = n_target / N

    # Individual signals
    indiv = []
    for rn in ['r1', 'r2', 'r3']:
        for iv in range(9):
            res = temporal_cv(rows, lambda p, r=rn, v=iv: p[r] == v, is_target)
            if not res or res['n'] < 20: continue
            if res['cv'] >= 4 and res['lift_pp'] > 0:
                w = 2 if (res['cv'] >= 5 or res['lift_pp'] > base*100*0.5) else 1
                indiv.append({'reel': rn, 'idx': iv, 'dir': '+', 'weight': w, **res})
            elif res['cv'] >= 4 and res['lift_pp'] < -base*50:
                w = -2 if (res['cv'] >= 5 or res['hits'] == 0) else -1
                indiv.append({'reel': rn, 'idx': iv, 'dir': '-', 'weight': w, **res})
            elif res['hits'] == 0 and res['n'] >= 35:
                indiv.append({'reel': rn, 'idx': iv, 'dir': '-', 'weight': -2, **res})

    # Pair signals
    pairs = []
    for na, nb in [('r1','r2'), ('r1','r3'), ('r2','r3')]:
        for va in range(9):
            for vb in range(9):
                res = temporal_cv(rows,
                    lambda p, a=na, b=nb, x=va, y=vb: p[a]==x and p[b]==y, is_target)
                if not res or res['n'] < 15: continue
                if res['cv'] >= 4 and res['lift_pp'] > 0 and res['hits'] >= 2:
                    w = 2 if (res['cv'] >= 5 or res['lift_pp'] > 5.0) else 1
                    pairs.append({'pair': f"{na}={va},{nb}={vb}", 'dir': '+', 'weight': w, **res})
                elif res['hits'] == 0 and res['n'] >= 25:
                    w = -2 if res['n'] >= 50 else -1
                    pairs.append({'pair': f"{na}={va},{nb}={vb}", 'dir': '-', 'weight': w, **res})

    return indiv, pairs, n_target

# =====================================================================
#  Phase 2: Build L1 composite scorer
# =====================================================================
def build_l1_scorer(indiv, pairs):
    """Return a function score(r1, r2, r3) -> (score, max_score)"""
    pos_indiv = [s for s in indiv if s['dir'] == '+']
    neg_indiv = [s for s in indiv if s['dir'] == '-']
    pos_pairs = [p for p in pairs if p['dir'] == '+']
    neg_pairs = [p for p in pairs if p['dir'] == '-']

    max_score = sum(s['weight'] for s in pos_indiv) + sum(p['weight'] for p in pos_pairs)

    def score(r1, r2, r3):
        s = 0
        vals = {'r1': r1, 'r2': r2, 'r3': r3}
        for sig in pos_indiv:
            if vals[sig['reel']] == sig['idx']: s += sig['weight']
        for sig in neg_indiv:
            if vals[sig['reel']] == sig['idx']: s += sig['weight']  # weight is negative
        for p in pos_pairs:
            parts = p['pair'].split(',')
            rn_a, va = parts[0].split('=')
            rn_b, vb = parts[1].split('=')
            if vals[rn_a] == int(va) and vals[rn_b] == int(vb): s += p['weight']
        for p in neg_pairs:
            parts = p['pair'].split(',')
            rn_a, va = parts[0].split('=')
            rn_b, vb = parts[1].split('=')
            if vals[rn_a] == int(va) and vals[rn_b] == int(vb): s += p['weight']
        return s, max_score

    return score, max_score

# =====================================================================
#  Phase 3: Layer 2 window patterns (re-validate on merged data)
# =====================================================================
def compute_l2(rows, i, window=10):
    """Compute L2 window score for spin i using last `window` spins."""
    if i < 3: return 0
    start = max(0, i - window)
    win = rows[start:i]
    wsize = len(win)
    if wsize < 3: return 0

    score = 0

    # A: steal on reel_1 count >= 2
    steal_r1 = sum(1 for r in win if r['s1'] == 4)
    if steal_r1 >= 2: score += 1

    # B: r3==4 count >= 2
    r3_4 = sum(1 for r in win if r['r3'] == 4)
    if r3_4 >= 2: score += 1

    # C: r3 bigram 0->8
    for j in range(1, wsize):
        if win[j-1]['r3'] == 0 and win[j]['r3'] == 8:
            score += 1; break

    # D: r3 bigram 8->4 or 4->4
    for j in range(1, wsize):
        if (win[j-1]['r3'] == 8 and win[j]['r3'] == 4) or \
           (win[j-1]['r3'] == 4 and win[j]['r3'] == 4):
            score += 1; break

    # E: r2==6 gap <= 7
    r2_6_gap = -1
    for lb in range(1, len(win)+1):
        if win[-lb]['r2'] == 6: r2_6_gap = lb; break
    if 0 < r2_6_gap <= 7: score += 1

    # F: r3==1 gap > 10 (absent = good)
    # G: r3==1 gap <= 3 (recent = bad)
    r3_1_gap = -1
    for lb in range(1, len(win)+1):
        if win[-lb]['r3'] == 1: r3_1_gap = lb; break
    if r3_1_gap < 0 or r3_1_gap > 10: score += 1
    if 0 < r3_1_gap <= 3: score -= 2

    # H: tuple (3,6,4)
    for r in win:
        if r['r1'] == 3 and r['r2'] == 6 and r['r3'] == 4:
            score += 1; break

    # I: r3 variety (low dup rate)
    if wsize > 1:
        dups = sum(1 for j in range(1, wsize) if win[j]['r3'] == win[j-1]['r3'])
        if dups / (wsize - 1) < 0.15: score += 1

    # J: r1 bigram (3,3)
    for j in range(1, wsize):
        if win[j-1]['r1'] == 3 and win[j]['r1'] == 3:
            score += 1; break

    return score

# =====================================================================
#  Phase 4: Strategy simulation
# =====================================================================
def simulate_strategy(rows, target_codes, l1_scorer, thresholds, type_name):
    """
    Run simulation: for each spin, compute L1+L2, apply threshold -> BET or SKIP.
    thresholds: list of (name, min_combined) tuples
    Returns KPI dict per threshold.
    """
    N = len(rows)
    def is_target(row): return row['is_triple'] and row['s1'] in target_codes
    n_target = sum(1 for r in rows if is_target(r))
    base_rate = n_target / N

    # Pre-compute L1 and L2 for each spin
    l1_scores = []
    l2_scores = []
    for i in range(N):
        if i == 0:
            l1_scores.append(0)
            l2_scores.append(0)
        else:
            prev = rows[i-1]
            l1, _ = l1_scorer(prev['r1'], prev['r2'], prev['r3'])
            l2 = compute_l2(rows, i)
            l1_scores.append(l1)
            l2_scores.append(l2)

    results = {}
    for thresh_name, min_score in thresholds:
        bets = 0
        catches = 0
        missed = 0
        for i in range(1, N):
            combined = l1_scores[i] + l2_scores[i]
            is_hit = is_target(rows[i])
            if combined >= min_score:
                bets += 1
                if is_hit: catches += 1
            else:
                if is_hit: missed += 1

        catch_rate = catches / n_target if n_target > 0 else 0
        precision = catches / bets if bets > 0 else 0
        bets_per_hit = bets / catches if catches > 0 else float('inf')
        lift = precision / base_rate if base_rate > 0 else 0
        bet_pct = bets / N

        # P-value: probability of catching >= this many in `bets` trials at base_rate
        p_val = fisher_p(catches, bets, base_rate) if bets > 0 and catches > 0 else 1.0

        # Wilson CI on precision
        lo, hi = wilson_ci(catches, bets)

        results[thresh_name] = {
            'threshold': min_score,
            'bets': bets,
            'catches': catches,
            'missed': missed,
            'total_targets': n_target,
            'catch_rate': catch_rate,
            'precision': precision,
            'bets_per_hit': bets_per_hit,
            'lift': lift,
            'bet_pct': bet_pct,
            'p_value': p_val,
            'ci_lo': lo, 'ci_hi': hi,
            'base_rate': base_rate,
        }

    # Also compute score distribution
    score_dist = defaultdict(lambda: {'n': 0, 'hits': 0})
    for i in range(1, N):
        combined = l1_scores[i] + l2_scores[i]
        is_hit = is_target(rows[i])
        score_dist[combined]['n'] += 1
        if is_hit: score_dist[combined]['hits'] += 1

    return results, score_dist, l1_scores, l2_scores

# =====================================================================
#  Phase 5: L2 signal-by-signal re-validation
# =====================================================================
def validate_l2_signals(rows, target_codes):
    """Re-validate each L2 signal on the merged dataset."""
    N = len(rows)
    def is_target(row): return row['is_triple'] and row['s1'] in target_codes
    n_target = sum(1 for r in rows if is_target(r))
    base = n_target / N

    signal_names = ['A:steal_r1>=2', 'B:r3=4>=2', 'C:r3_0->8', 'D:r3_8->4|4->4',
                    'E:r2=6_gap<=7', 'F:r3=1_absent', 'G:r3=1_recent(-)',
                    'H:tuple_364', 'I:r3_variety', 'J:r1_bigram_33']

    print(f"\n  L2 signal re-validation ({n_target} targets, {N} spins, base={100*base:.2f}%):")
    print(f"  {'Signal':>22} {'N':>5} {'Hits':>5} {'Rate':>7} {'Lift':>8} {'CV':>4}")
    print(f"  {'-'*58}")

    for sig_idx, sig_name in enumerate(signal_names):
        def cond_factory(idx):
            def cond(prev_row):
                # We need window context, so this is approximate
                # Just check if the signal would fire based on the scoring
                return True  # placeholder
            return cond

        # Direct computation: for each spin, check if THIS signal fires, then track hit rate
        sig_n = sig_hits = 0
        nosig_n = nosig_hits = 0
        fold_size = N // 5
        fold_lifts = []

        for fold in range(5):
            fs = fold * fold_size
            fe = fs + fold_size if fold < 4 else N
            f_sig_n = f_sig_h = f_base_n = f_base_h = 0

            for i in range(max(fs, 3), fe):
                start = max(0, i - 10)
                win = rows[start:i]
                wsize = len(win)
                hit = is_target(rows[i])
                f_base_n += 1
                if hit: f_base_h += 1

                fires = False
                if sig_idx == 0:  # A
                    fires = sum(1 for r in win if r['s1'] == 4) >= 2
                elif sig_idx == 1:  # B
                    fires = sum(1 for r in win if r['r3'] == 4) >= 2
                elif sig_idx == 2:  # C
                    fires = any(win[j-1]['r3']==0 and win[j]['r3']==8 for j in range(1, wsize))
                elif sig_idx == 3:  # D
                    fires = any((win[j-1]['r3']==8 and win[j]['r3']==4) or
                               (win[j-1]['r3']==4 and win[j]['r3']==4) for j in range(1, wsize))
                elif sig_idx == 4:  # E
                    gap = -1
                    for lb in range(1, wsize+1):
                        if win[-lb]['r2'] == 6: gap = lb; break
                    fires = (0 < gap <= 7)
                elif sig_idx == 5:  # F
                    gap = -1
                    for lb in range(1, wsize+1):
                        if win[-lb]['r3'] == 1: gap = lb; break
                    fires = (gap < 0 or gap > 10)
                elif sig_idx == 6:  # G (negative)
                    gap = -1
                    for lb in range(1, wsize+1):
                        if win[-lb]['r3'] == 1: gap = lb; break
                    fires = (0 < gap <= 3)
                elif sig_idx == 7:  # H
                    fires = any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win)
                elif sig_idx == 8:  # I
                    if wsize > 1:
                        dups = sum(1 for j in range(1, wsize) if win[j]['r3']==win[j-1]['r3'])
                        fires = dups / (wsize - 1) < 0.15
                elif sig_idx == 9:  # J
                    fires = any(win[j-1]['r1']==3 and win[j]['r1']==3 for j in range(1, wsize))

                if fires:
                    f_sig_n += 1
                    if hit: f_sig_h += 1

            sig_n += f_sig_n; sig_hits += f_sig_h
            if f_sig_n >= 5 and f_base_n > 0:
                fold_lifts.append(f_sig_h/f_sig_n - f_base_h/f_base_n)
            else:
                fold_lifts.append(None)

        if sig_n == 0: continue
        rate = sig_hits / sig_n
        lift = (rate - base) * 100
        d = 1 if lift >= 0 else -1
        cv = sum(1 for l in fold_lifts if l is not None and l * d > 0)
        marker = ' <<<' if cv >= 4 and lift > 0 else (' xxx' if cv >= 4 and lift < 0 else '')
        print(f"  {sig_name:>22} {sig_n:>5} {sig_hits:>5} {100*rate:>6.1f}% {lift:>+7.2f}pp {cv}/5{marker}")


# =====================================================================
#  MAIN: Run everything
# =====================================================================

print("\n" + "=" * 90)
print("  80_DEEP_SPLIT_ANALYSIS -- 3,864 spins, 7 independent types")
print("=" * 90)

# Threshold sweep
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

all_kpis = {}

for type_name, codes in TYPES.items():
    print(f"\n\n{'#'*90}")
    print(f"#  {type_name.upper()}")
    print(f"{'#'*90}")

    # Phase 1: Discover
    indiv, pairs, n_target = discover_signals(type_name, codes, rows)
    if n_target == 0:
        print("  No hits, skipping.")
        continue

    base_rate = n_target / N
    pos_i = [s for s in indiv if s['dir'] == '+']
    neg_i = [s for s in indiv if s['dir'] == '-']
    pos_p = [p for p in pairs if p['dir'] == '+']
    neg_p = [p for p in pairs if p['dir'] == '-']

    print(f"\n  L1 Signal Summary:")
    print(f"    Positive individuals: {len(pos_i)}")
    for s in sorted(pos_i, key=lambda x: -x['lift_pp']):
        print(f"      {s['reel']}={s['idx']}: +{s['lift_pp']:.2f}pp, {s['cv']}/5 CV, "
              f"{s['hits']}/{s['n']} ({100*s['rate']:.1f}%), w={s['weight']}")
    print(f"    Negative individuals: {len(neg_i)}")
    for s in sorted(neg_i, key=lambda x: x['lift_pp']):
        print(f"      {s['reel']}={s['idx']}: {s['lift_pp']:+.2f}pp, {s['cv']}/5 CV, "
              f"{s['hits']}/{s['n']} ({100*s['rate']:.1f}%), w={s['weight']}")
    print(f"    Positive pairs: {len(pos_p)}")
    for p in sorted(pos_p, key=lambda x: -x['lift_pp'])[:8]:
        print(f"      ({p['pair']}): +{p['lift_pp']:.2f}pp, {p['cv']}/5 CV, "
              f"{p['hits']}/{p['n']}, w={p['weight']}")
    print(f"    Dead-zone pairs: {len(neg_p)}")
    for p in sorted(neg_p, key=lambda x: x['n'])[:5]:
        print(f"      ({p['pair']}): 0/{p['n']} DEAD, w={p['weight']}")

    # Phase 2: Build scorer
    l1_scorer, max_l1 = build_l1_scorer(indiv, pairs)
    print(f"\n  L1 max possible score: {max_l1}")

    # Phase 3: L2 re-validation for this type
    validate_l2_signals(rows, codes)

    # Phase 4: Strategy simulation
    sim_results, score_dist, l1_arr, l2_arr = simulate_strategy(
        rows, codes, l1_scorer, THRESHOLDS, type_name)

    # Score distribution table
    print(f"\n  Combined (L1+L2) Score Distribution:")
    print(f"  {'Score':>6} {'Spins':>6} {'Hits':>5} {'Rate':>7} {'Lift':>6} {'CumHits':>7} {'CumCatch':>8}")
    print(f"  {'-'*55}")
    cum_hits = 0
    for sc in sorted(score_dist.keys(), reverse=True):
        d = score_dist[sc]
        rate = d['hits']/d['n'] if d['n'] > 0 else 0
        lift = rate / base_rate if base_rate > 0 else 0
        cum_hits += d['hits']
        cum_catch = cum_hits / n_target
        print(f"  {sc:>6} {d['n']:>6} {d['hits']:>5} {100*rate:>6.1f}% {lift:>5.1f}x {cum_hits:>7} {100*cum_catch:>7.1f}%")

    # KPI table
    print(f"\n  Strategy Simulation KPIs (base rate = {100*base_rate:.2f}%):")
    print(f"  {'Profile':>12} {'Thresh':>6} {'Bets':>5} {'Catch':>5} {'Miss':>5} "
          f"{'CatchR':>7} {'Prec':>7} {'B/Hit':>6} {'Lift':>5} {'BetPct':>7} {'p-val':>8} {'CI95':>14}")
    print(f"  {'-'*100}")

    for name, _ in THRESHOLDS:
        r = sim_results[name]
        ci_str = f"[{100*r['ci_lo']:.1f}-{100*r['ci_hi']:.1f}]"
        bph = f"{r['bets_per_hit']:.1f}" if r['bets_per_hit'] < 1000 else "inf"
        print(f"  {name:>12} {r['threshold']:>6} {r['bets']:>5} {r['catches']:>5} {r['missed']:>5} "
              f"{100*r['catch_rate']:>6.1f}% {100*r['precision']:>6.2f}% {bph:>6} "
              f"{r['lift']:>4.1f}x {100*r['bet_pct']:>6.1f}% {r['p_value']:>8.4f} {ci_str:>14}")

    all_kpis[type_name] = sim_results

    # L1-only vs L2-only vs combined comparison
    print(f"\n  L1-only vs L2-only vs Combined (at threshold >=2):")
    for mode_name, use_l1, use_l2 in [('L1 only', True, False), ('L2 only', False, True), ('Combined', True, True)]:
        bets = catches = 0
        for i in range(1, N):
            s = 0
            if use_l1: s += l1_arr[i]
            if use_l2: s += l2_arr[i]
            if s >= 2:
                bets += 1
                if rows[i]['is_triple'] and rows[i]['s1'] in codes: catches += 1
        prec = catches / bets if bets > 0 else 0
        catch_r = catches / n_target if n_target > 0 else 0
        bph = bets / catches if catches > 0 else float('inf')
        bph_s = f"{bph:.1f}" if bph < 1000 else "inf"
        print(f"    {mode_name:>10}: bets={bets:>5}, catches={catches:>3}, "
              f"catch={100*catch_r:.1f}%, prec={100*prec:.2f}%, b/h={bph_s}")


# =====================================================================
#  GRAND SUMMARY
# =====================================================================
print(f"\n\n{'#'*90}")
print(f"#  GRAND SUMMARY: Best profile per type")
print(f"{'#'*90}")
print(f"\n  {'Type':>15} {'Hits':>5} {'Base':>6} | {'Profile':>8} {'Bets':>5} {'Catch':>5} "
      f"{'CatchR':>7} {'Prec':>7} {'B/Hit':>6} {'Lift':>5} {'p-val':>8}")
print(f"  {'-'*95}")

for type_name, codes in TYPES.items():
    if type_name not in all_kpis: continue
    n_t = sum(1 for r in rows if r['is_triple'] and r['s1'] in codes)
    base = n_t / N

    # Find best profile: highest lift with p < 0.05 and catch >= 20%
    best = None
    for name, _ in THRESHOLDS:
        r = all_kpis[type_name][name]
        if r['p_value'] < 0.05 and r['catch_rate'] >= 0.15 and r['catches'] >= 3:
            if best is None or r['lift'] > all_kpis[type_name][best]['lift']:
                best = name
    if best is None:
        best = '>=2 (BAL)'

    r = all_kpis[type_name][best]
    bph = f"{r['bets_per_hit']:.1f}" if r['bets_per_hit'] < 1000 else "inf"
    print(f"  {type_name:>15} {n_t:>5} {100*base:>5.2f}% | {best:>8} {r['bets']:>5} {r['catches']:>5} "
          f"{100*r['catch_rate']:>6.1f}% {100*r['precision']:>6.2f}% {bph:>6} "
          f"{r['lift']:>4.1f}x {r['p_value']:>8.4f}")

# Save full results
out = {}
for t in all_kpis:
    out[t] = {}
    for p in all_kpis[t]:
        r = all_kpis[t][p]
        out[t][p] = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()}

out_path = Path(__file__).parent / "80_deep_results.json"
with open(out_path, 'w') as f:
    json.dump(out, f, indent=2)
print(f"\n\nFull results saved to {out_path}")
print("\nDONE")
