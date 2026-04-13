#!/usr/bin/env python3
"""
79_split_type_signals.py — Per-triple-type idx signal analysis with ACC/SPN SPLIT.
Merges Ahmed enriched_v2 (1,107 spins) + Nick 59-col rows (2,757 spins) = ~3,864 spins.
Runs 5-fold temporal CV per type including ACC and SPN as SEPARATE targets.

Output: validated signals per type -> feeds the updated SLIdxStrategy with 7 independent scorers
        (ACC, SPN, SHIELD, ATTACK, STEAL, COIN, GOLDSACK).
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# =====================================================================
#  Data loading
# =====================================================================

def load_ahmed_v2():
    """Load Ahmed enriched_v2: 1,107 rows, cols: sn,csv_seq,r1_idx,r2_idx,r3_idx,s1,s2,s3,
       reel_1,reel_2,reel_3,spin_result,reward_code,is_triple,is_valuable,se_hash,bet_state"""
    path = ROOT / "data" / "Ahmed" / "spin_history_Ahmed_enriched_v2.csv"
    rows = []
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            if r['r1_idx'] == '' or int(r['r1_idx']) < 0:
                continue
            rows.append({
                'r1': int(r['r1_idx']),
                'r2': int(r['r2_idx']),
                'r3': int(r['r3_idx']),
                's1': int(r['s1']),
                'is_triple': r['is_triple'] == 'True',
                'reel_1': r['reel_1'],
                'source': 'Ahmed',
            })
    return rows


def load_nick_59col():
    """Load Nick spin_history with 59 columns (has idx in cols 54-59).
    Header has 53 names; cols 54-59 are unnamed: r1_idx,r2_idx,r3_idx,is_valuable,strategy_tier,strategy_score"""
    path = ROOT / "data" / "Nick" / "spin_history_Nick_2026-04-08 (1).csv"
    rows = []

    # Reel symbol -> raw code mapping (from SLConstants)
    SYM_CODE = {
        'attack': 3, 'steal': 4, 'shield': 5, 'spins': 6,
        'coin': 1, 'goldSack': 2, 'accumulation': 30, 'potion': 7,
    }

    with open(path, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        n_header = len(header)

        for fields in reader:
            if len(fields) != 59:
                continue  # skip rows without idx data
            seq = int(fields[0])
            if seq < 69879:
                continue  # skip rows before idx was enabled

            r1_idx = fields[53]
            if r1_idx == '' or int(r1_idx) < 0:
                continue

            reel_1 = fields[5]   # reel_1 column
            s1 = SYM_CODE.get(reel_1, -1)
            is_triple = fields[10].lower() == 'true'

            rows.append({
                'r1': int(r1_idx),
                'r2': int(fields[54]),
                'r3': int(fields[55]),
                's1': s1,
                'is_triple': is_triple,
                'reel_1': reel_1,
                'source': 'Nick',
            })
    return rows


print("Loading data...")
ahmed = load_ahmed_v2()
nick = load_nick_59col()
rows = ahmed + nick
N = len(rows)

# Triple counts
type_counts = defaultdict(int)
for r in rows:
    if r['is_triple']:
        type_counts[r['reel_1']] += 1

print(f"Total: {N} spins ({len(ahmed)} Ahmed + {len(nick)} Nick)")
print(f"Triples by type:")
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {t:>15}: {c:>4} ({100*c/N:.2f}%, 1 per {N/max(c,1):.0f})")

# =====================================================================
#  Triple type definitions — ACC and SPN are SEPARATE
# =====================================================================

TRIPLE_TYPES = {
    'accumulation': [30],
    'spins':        [6],
    'shield':       [5],
    'attack':       [3],
    'steal':        [4],
    'coin':         [1],
    'goldSack':     [2],
}

# Keep a combined group for comparison only
COMBO_GROUPS = {
    'acc+spins': [30, 6],
}

# =====================================================================
#  Temporal 5-fold CV
# =====================================================================

def temporal_cv(rows, condition_fn, target_fn, n_folds=5):
    """
    condition_fn(prev_row) -> bool  (does previous spin match this signal?)
    target_fn(row) -> bool          (is this spin a hit?)
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

        sig_n = sig_hits = base_n = base_hits = 0
        for i in range(max(start, 1), end):
            is_hit = target_fn(rows[i])
            if condition_fn(rows[i-1]):
                sig_n += 1
                if is_hit: sig_hits += 1
            base_n += 1
            if is_hit: base_hits += 1

        total_signal += sig_n
        total_hits += sig_hits
        total_base_signal += base_n
        total_base_hits += base_hits

        if sig_n >= 5:
            sig_rate = sig_hits / sig_n
            base_rate = base_hits / base_n if base_n > 0 else 0
            fold_lifts.append(sig_rate - base_rate)
        else:
            fold_lifts.append(None)

    if total_signal == 0:
        return None

    overall_rate = total_hits / total_signal
    base_rate = total_base_hits / total_base_signal if total_base_signal > 0 else 0
    lift_pp = (overall_rate - base_rate) * 100

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
#  Per-type analysis
# =====================================================================

def analyze_type(type_name, target_codes, rows):
    N = len(rows)

    def is_target(row):
        return row['is_triple'] and row['s1'] in target_codes

    n_target = sum(1 for r in rows if is_target(r))
    if n_target == 0:
        print(f"\n  {type_name.upper()}: 0 hits — skipping")
        return [], []

    base_rate = n_target / N

    print(f"\n{'='*80}")
    print(f"  {type_name.upper()} — {n_target} hits in {N} spins ({100*base_rate:.2f}%, 1 per {N/n_target:.0f})")
    print(f"{'='*80}")

    # --- Individual idx signals ---
    print(f"\n  Individual idx signals (prev spin -> next spin triple):")
    print(f"  {'Signal':>12} {'N':>5} {'Hits':>5} {'Rate':>7} {'Base':>7} {'Lift':>8} {'CV':>4}")
    print(f"  {'-'*55}")

    results = []
    for reel_name in ['r1', 'r2', 'r3']:
        for idx_val in range(9):
            def cond(prev, rn=reel_name, iv=idx_val):
                return prev[rn] == iv
            res = temporal_cv(rows, cond, is_target)
            if res and res['n'] >= 20:
                results.append((reel_name, idx_val, res))

    results.sort(key=lambda x: abs(x[2]['lift_pp']), reverse=True)

    good_signals = []
    for reel_name, idx_val, res in results:
        marker = ''
        if res['cv'] >= 4 and res['lift_pp'] > 0:
            marker = ' <<<'
            good_signals.append((reel_name, idx_val, res, '+'))
        elif res['cv'] >= 4 and res['lift_pp'] < -base_rate * 50:
            marker = ' xxx'
            good_signals.append((reel_name, idx_val, res, '-'))
        elif res['hits'] == 0 and res['n'] >= 40:
            marker = ' DEAD'
            good_signals.append((reel_name, idx_val, res, '-'))

        print(f"  {reel_name}={idx_val:>2}     {res['n']:>5} {res['hits']:>5} "
              f"{100*res['rate']:>6.1f}% {100*res['base']:>6.2f}% "
              f"{res['lift_pp']:>+7.2f}pp {res['cv']}/5{marker}")

    # --- Pair signals ---
    print(f"\n  Pair signals (prev spin -> next spin triple):")
    print(f"  {'Signal':>18} {'N':>5} {'Hits':>5} {'Rate':>7} {'Base':>7} {'Lift':>8} {'CV':>4}")
    print(f"  {'-'*60}")

    pair_results = []
    for name_a, name_b in [('r1','r2'), ('r1','r3'), ('r2','r3')]:
        for va in range(9):
            for vb in range(9):
                def cond(prev, na=name_a, nb=name_b, a=va, b=vb):
                    return prev[na] == a and prev[nb] == b
                res = temporal_cv(rows, cond, is_target)
                if res and res['n'] >= 15:
                    pair_results.append((f"{name_a}={va},{name_b}={vb}", res))

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

    # Dead-zone pairs
    print(f"\n  Top NEGATIVE / dead-zone pairs:")
    shown = 0
    for label, res in reversed(pair_results):
        if res['hits'] == 0 and res['n'] >= 25:
            print(f"  {label:>18} {res['n']:>5} {res['hits']:>5} "
                  f"{100*res['rate']:>6.1f}% {100*res['base']:>6.2f}% "
                  f"{res['lift_pp']:>+7.2f}pp {res['cv']}/5  DEAD")
            good_pairs.append((label, res, '-'))
            shown += 1
            if shown >= 10:
                break

    # --- Anti-clustering ---
    print(f"\n  Anti-clustering (does a {type_name} triple predict fewer {type_name} soon?):")
    for gap in [1, 2, 3, 5, 10, 15, 20]:
        hits_after = total_after = 0
        for i in range(N - gap):
            if is_target(rows[i]):
                total_after += 1
                if is_target(rows[i + gap]):
                    hits_after += 1
        if total_after > 0:
            rate = hits_after / total_after
            tag = 'CLUSTER' if rate > base_rate * 1.3 else 'anti-cluster' if rate < base_rate * 0.7 else 'neutral'
            print(f"    Gap {gap:>2}: {hits_after}/{total_after} = {100*rate:.1f}% "
                  f"(base {100*base_rate:.2f}%, {tag})")

    return good_signals, good_pairs


# =====================================================================
#  RUN
# =====================================================================

print("\n" + "=" * 90)
print("  79_SPLIT_TYPE_SIGNALS — 3,864 spins, ACC & SPN SEPARATE")
print("=" * 90)

all_results = {}

# Individual types (ACC and SPN separate!)
for type_name, codes in TRIPLE_TYPES.items():
    signals, pairs = analyze_type(type_name, codes, rows)
    all_results[type_name] = {'signals': signals, 'pairs': pairs}

# Combo for comparison
for group_name, codes in COMBO_GROUPS.items():
    signals, pairs = analyze_type(group_name, codes, rows)
    all_results[group_name] = {'signals': signals, 'pairs': pairs}


# =====================================================================
#  SUMMARY -> JSON for SLIdxStrategy update
# =====================================================================

print("\n\n" + "#" * 90)
print("#  SUMMARY: Validated signals per type (for SLIdxStrategy.m)")
print("#" * 90)

json_output = {}

for name, data in all_results.items():
    positives = []
    negatives = []
    pos_pairs = []
    neg_pairs = []

    for reel_name, idx_val, res, direction in data['signals']:
        entry = {
            'reel': reel_name, 'idx': idx_val,
            'lift_pp': round(res['lift_pp'], 2),
            'cv': res['cv'],
            'hits': res['hits'], 'n': res['n'],
            'rate_pct': round(100 * res['rate'], 2),
        }
        if direction == '+':
            positives.append(entry)
        else:
            negatives.append(entry)

    for label, res, direction in data['pairs']:
        entry = {
            'pair': label,
            'lift_pp': round(res['lift_pp'], 2),
            'cv': res['cv'],
            'hits': res['hits'], 'n': res['n'],
        }
        if direction == '+':
            pos_pairs.append(entry)
        else:
            neg_pairs.append(entry)

    n_pos = len(positives)
    n_neg = len(negatives)

    print(f"\n  {name.upper()}:")
    print(f"    Positive individual: {n_pos}")
    for s in positives:
        w = 2 if s['cv'] >= 5 or s['lift_pp'] > 3.0 else 1
        print(f"      {s['reel']}={s['idx']}: +{s['lift_pp']:.1f}pp, {s['cv']}/5 CV, "
              f"{s['hits']}/{s['n']} ({s['rate_pct']:.1f}%)  -> weight {w}")
        s['weight'] = w

    print(f"    Negative individual: {n_neg}")
    for s in negatives:
        w = -2 if (s['cv'] >= 5 or s['hits'] == 0) else -1
        print(f"      {s['reel']}={s['idx']}: {s['lift_pp']:+.1f}pp, {s['cv']}/5 CV, "
              f"{s['hits']}/{s['n']} ({s['rate_pct']:.1f}%)  -> weight {w}")
        s['weight'] = w

    if pos_pairs:
        print(f"    Positive pairs: {len(pos_pairs)}")
        for p in pos_pairs:
            w = 2 if p['cv'] >= 5 or p['lift_pp'] > 5.0 else 1
            print(f"      ({p['pair']}): +{p['lift_pp']:.1f}pp, {p['cv']}/5 CV, {p['hits']}/{p['n']}  -> weight {w}")
            p['weight'] = w

    if neg_pairs:
        print(f"    Dead-zone pairs: {len(neg_pairs)}")
        for p in neg_pairs:
            w = -2 if p['n'] >= 50 else -1
            print(f"      ({p['pair']}): 0/{p['n']} DEAD  -> weight {w}")
            p['weight'] = w

    json_output[name] = {
        'positives': positives,
        'negatives': negatives,
        'pos_pairs': pos_pairs,
        'neg_pairs': neg_pairs,
    }


# Save JSON
out_path = Path(__file__).parent / "79_split_signals.json"
with open(out_path, 'w') as f:
    json.dump(json_output, f, indent=2)
print(f"\n\nJSON saved to {out_path}")

# =====================================================================
#  Codegen hint: ObjC scoring functions
# =====================================================================
print("\n\n" + "#" * 90)
print("#  CODEGEN: Suggested ObjC scoring functions")
print("#" * 90)

for name in ['accumulation', 'spins', 'shield', 'attack', 'steal', 'coin', 'goldSack']:
    data = json_output.get(name, {})
    pos = data.get('positives', [])
    neg = data.get('negatives', [])
    pp = data.get('pos_pairs', [])
    np_ = data.get('neg_pairs', [])

    max_score = sum(abs(s['weight']) for s in pos) + sum(abs(p['weight']) for p in pp)

    print(f"\n  // {name.upper()} — maxScore = {max_score}")
    for s in pos:
        print(f"  if ({s['reel']} == {s['idx']}) score += {s['weight']};   "
              f"// {s['cv']}/5 CV, +{s['lift_pp']:.1f}pp")
    for s in neg:
        print(f"  if ({s['reel']} == {s['idx']}) score -= {abs(s['weight'])};   "
              f"// {s['cv']}/5 CV, {s['lift_pp']:+.1f}pp")
    for p in pp:
        parts = p['pair'].split(',')
        print(f"  if ({parts[0]} && {parts[1]}) score += {p['weight']};   "
              f"// {p['cv']}/5 CV, +{p['lift_pp']:.1f}pp")
    for p in np_:
        parts = p['pair'].split(',')
        print(f"  if ({parts[0]} && {parts[1]}) score -= {abs(p['weight'])};   "
              f"// 0/{p['n']} DEAD")

print("\n\nDONE")
