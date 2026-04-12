#!/usr/bin/env python3
"""
63_per_type_sim.py - Simulate the per-type strategy engine on 1,107 spins.

Uses the CORRECTED VT definition: accumulation(30) + spins(6) only.
Uses the per-type signal rules from 62_per_type_signals.py, matching
the Objective-C implementation in SLIdxStrategy.m.
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
        r['sn'] = int(r['sn'])
        rows.append(r)

N = len(rows)

# CORRECTED VT definition: accumulation(30) or spins(6) triples only
def is_vt(row):
    return row['is_triple'] and row['s1'] in (30, 6)

total_vt = sum(1 for r in rows if is_vt(r))
print("=" * 80)
print("  63_PER_TYPE_SIM — Strategy simulation (CORRECTED VT = acc+spins)")
print("=" * 80)
print(f"  Total spins: {N}")
print(f"  Total VT (acc+spins): {total_vt} ({100*total_vt/N:.2f}%)")
print(f"  Base VT rate: 1 per {N/total_vt:.1f} spins")

# Also count by sub-type
n_acc = sum(1 for r in rows if r['is_triple'] and r['s1'] == 30)
n_spins = sum(1 for r in rows if r['is_triple'] and r['s1'] == 6)
print(f"    Accumulation triples: {n_acc}")
print(f"    Spins triples: {n_spins}")


# =====================================================================
# ACC+SPINS SCORER — exact match to SLIdxStrategy.m scoreAccSpinsR1:r2:r3:
# =====================================================================

def score_acc_spins(r1, r2, r3):
    score = 0
    # Individual signals
    if r2 == 7: score += 2   # 5/5 CV, +2.2pp
    if r1 == 7: score += 1   # 4/5 CV, +1.4pp
    if r2 == 3: score += 1   # 4/5 CV, +1.2pp
    if r1 == 3: score += 1   # 4/5 CV, +1.2pp

    # Negative signals
    if r3 == 1: score -= 2   # 5/5 CV, 0/100 dead
    if r2 == 0: score -= 1   # 5/5 CV
    if r2 == 2: score -= 1   # 4/5 CV
    if r1 == 5: score -= 1   # 4/5 CV
    if r1 == 0: score -= 1   # 4/5 CV

    # Pair bonuses
    if r1 == 7 and r2 == 7: score += 2  # 4/5 CV, 5/73, +3.7pp
    if r1 == 7 and r3 == 8: score += 1  # 4/5 CV, 6/108, +2.4pp
    if r2 == 7 and r3 == 8: score += 1  # 4/5 CV, 7/135, +2.0pp
    if r1 == 3 and r2 == 7: score += 1  # 4/5 CV, 4/95, +1.0pp
    if r1 == 3 and r2 == 4: score += 1  # 3/5 CV, 3/24 (12.5%), +9.3pp — all acc

    # Dead pairs
    if r1 == 4 and r2 == 4: score -= 2  # 0/71, 5/5 CV
    if r1 == 7 and r3 == 0: score -= 2  # 0/60, 5/5 CV
    if r1 == 4 and r3 == 4: score -= 1  # 0/48, 5/5 CV

    return score


def tier_from_score(score):
    if score >= 4: return 'MAX'
    if score >= 2: return 'BIG'
    if score <= -3: return 'MIN'
    if score <= -1: return 'SMALL'
    return 'NORMAL'


# =====================================================================
# STRATEGY FUNCTIONS
# =====================================================================

def strategy_flat(rows, i):
    return 'NORMAL'

def strategy_oracle(rows, i):
    return 'MAX' if is_vt(rows[i]) else 'MIN'

def strategy_acc_spins_v1(rows, i):
    """Per-type acc+spins scorer — uses previous spin's idx."""
    if i == 0: return 'NORMAL'
    p = rows[i-1]
    score = score_acc_spins(p['r1'], p['r2'], p['r3'])
    return tier_from_score(score)


# =====================================================================
# SIMULATION ENGINE
# =====================================================================

def simulate(rows, strategy_fn, name, bet_mults=None):
    if bet_mults is None:
        bet_mults = {'MAX': 10, 'BIG': 5, 'NORMAL': 1, 'SMALL': 0.5, 'MIN': 0.1}

    decisions = []
    for i in range(N):
        tier = strategy_fn(rows, i)
        mult = bet_mults.get(tier, 1)
        decisions.append({
            'spin': i,
            'tier': tier,
            'mult': mult,
            'is_vt': is_vt(rows[i]),
            'is_triple': rows[i]['is_triple'],
            'reel_1': rows[i]['reel_1'],
        })

    tier_counts = Counter(d['tier'] for d in decisions)
    tier_vt = defaultdict(int)
    for d in decisions:
        if d['is_vt']:
            tier_vt[d['tier']] += 1

    total_bet_units = sum(d['mult'] for d in decisions)
    flat_bet_units = N * 1.0

    vt_caught_max = sum(1 for d in decisions if d['is_vt'] and d['mult'] >= 10)
    vt_caught_big = sum(1 for d in decisions if d['is_vt'] and d['mult'] >= 5)
    vt_caught_elevated = sum(1 for d in decisions if d['is_vt'] and d['mult'] > 1)
    vt_at_min = sum(1 for d in decisions if d['is_vt'] and d['mult'] < 1)
    vt_missed = sum(1 for d in decisions if d['is_vt'] and d['mult'] <= 1)

    big_bets = sum(1 for d in decisions if d['mult'] >= 5)
    big_bet_hits = sum(1 for d in decisions if d['mult'] >= 5 and d['is_vt'])

    weighted_vt = sum(d['mult'] for d in decisions if d['is_vt'])
    flat_vt = total_vt * 1.0

    cost_non_vt = sum(d['mult'] for d in decisions if not d['is_vt'])
    flat_cost = (N - total_vt) * 1.0

    print(f"\n{'='*70}")
    print(f"  STRATEGY: {name}")
    print(f"{'='*70}")
    print(f"\n  Tier distribution:")
    for tier in ['MAX', 'BIG', 'NORMAL', 'SMALL', 'MIN']:
        n = tier_counts.get(tier, 0)
        vt = tier_vt.get(tier, 0)
        if n > 0:
            print(f"    {tier:>7}: {n:>4} spins ({100*n/N:>5.1f}%) | "
                  f"{vt:>2} VT ({100*vt/max(n,1):>5.1f}% hit rate)")

    print(f"\n  VT capture:")
    print(f"    Total VT:               {total_vt}")
    print(f"    VT at MAX (10x):        {vt_caught_max}")
    print(f"    VT at BIG+ (>=5x):      {vt_caught_big}")
    print(f"    VT at elevated (>1x):   {vt_caught_elevated}")
    print(f"    VT missed (<=1x):       {vt_missed}")
    print(f"    VT wasted at MIN:       {vt_at_min}")

    print(f"\n  Efficiency:")
    print(f"    Big bets placed:        {big_bets}")
    print(f"    Big bets that hit VT:   {big_bet_hits}")
    if big_bets > 0:
        print(f"    Hit rate:               {100*big_bet_hits/big_bets:.1f}% "
              f"({big_bets/max(big_bet_hits,1):.1f} bets per VT)")

    print(f"\n  Value:")
    print(f"    Total bet units:        {total_bet_units:.0f} (flat: {flat_bet_units:.0f}, "
          f"savings: {100*(1-total_bet_units/flat_bet_units):+.1f}%)")
    print(f"    Weighted VT value:      {weighted_vt:.1f} (flat: {flat_vt:.0f}, "
          f"uplift: {100*(weighted_vt/flat_vt-1):+.1f}%)")
    print(f"    Non-VT cost:            {cost_non_vt:.0f} (flat: {flat_cost:.0f}, "
          f"savings: {100*(1-cost_non_vt/flat_cost):+.1f}%)")

    roi = weighted_vt / total_bet_units if total_bet_units > 0 else 0
    flat_roi = flat_vt / flat_bet_units
    print(f"\n  ROI: {roi:.4f} (flat: {flat_roi:.4f}, improvement: {100*(roi/flat_roi-1):+.1f}%)")

    return decisions


# =====================================================================
# RUN SIMULATIONS
# =====================================================================

print("\n" + "#" * 80)
print("#  SIMULATION RESULTS (VT = accumulation + spins ONLY)")
print("#" * 80)

simulate(rows, strategy_flat, "FLAT baseline")
simulate(rows, strategy_oracle, "ORACLE (perfect knowledge)")
d_v1 = simulate(rows, strategy_acc_spins_v1, "ACC+SPINS per-type scorer")


# =====================================================================
# DETAILED: Every VT + what tier it got
# =====================================================================
print("\n\n" + "=" * 80)
print("  DETAILED: Every VT + bet tier (acc+spins scorer)")
print("=" * 80)

print(f"\n  {'Spin#':>6} {'Symbol':>15} {'Prev_idx':>14} {'Score':>6} {'Tier':>7}")
print("  " + "-" * 55)

vt_by_tier = defaultdict(list)
for i in range(N):
    if is_vt(rows[i]):
        tier = d_v1[i]['tier']
        if i > 0:
            p = rows[i-1]
            score = score_acc_spins(p['r1'], p['r2'], p['r3'])
            prev_idx = f"({p['r1']},{p['r2']},{p['r3']})"
        else:
            score = 0
            prev_idx = "(-,-,-)"

        vt_by_tier[tier].append(i)
        print(f"  {i:>6} {rows[i]['reel_1']:>15} {prev_idx:>14} {score:>+6} {tier:>7}")

print(f"\n  VT by tier:")
for tier in ['MAX', 'BIG', 'NORMAL', 'SMALL', 'MIN']:
    n = len(vt_by_tier.get(tier, []))
    if n > 0:
        print(f"    {tier:>7}: {n:>2} VTs")


# =====================================================================
# SCORE DISTRIBUTION
# =====================================================================
print("\n\n" + "=" * 80)
print("  SCORE DISTRIBUTION (all spins)")
print("=" * 80)

score_dist = defaultdict(lambda: {'total': 0, 'vt': 0})
for i in range(1, N):
    p = rows[i-1]
    score = score_acc_spins(p['r1'], p['r2'], p['r3'])
    score_dist[score]['total'] += 1
    if is_vt(rows[i]):
        score_dist[score]['vt'] += 1

print(f"\n  {'Score':>6} {'Spins':>6} {'%':>6} {'VT':>4} {'VT_rate':>8} {'Tier':>7}")
print("  " + "-" * 45)
for score in sorted(score_dist.keys()):
    d = score_dist[score]
    pct = 100 * d['total'] / N
    vt_rate = 100 * d['vt'] / d['total'] if d['total'] > 0 else 0
    tier = tier_from_score(score)
    marker = ' <<<' if d['vt'] > 0 and vt_rate > 5 else ''
    print(f"  {score:>+6} {d['total']:>6} {pct:>5.1f}% {d['vt']:>4} {vt_rate:>7.1f}% {tier:>7}{marker}")


# =====================================================================
# WHAT-IF: bet multiplier schemes
# =====================================================================
print("\n\n" + "=" * 80)
print("  WHAT-IF: Bet multiplier schemes")
print("=" * 80)

schemes = [
    ("Conservative (3x/2x/1x/0.5x/0.2x)", {'MAX': 3, 'BIG': 2, 'NORMAL': 1, 'SMALL': 0.5, 'MIN': 0.2}),
    ("Moderate (5x/3x/1x/0.5x/0.1x)", {'MAX': 5, 'BIG': 3, 'NORMAL': 1, 'SMALL': 0.5, 'MIN': 0.1}),
    ("Aggressive (10x/5x/1x/0.5x/0.1x)", {'MAX': 10, 'BIG': 5, 'NORMAL': 1, 'SMALL': 0.5, 'MIN': 0.1}),
    ("Ultra (20x/10x/1x/0.2x/0.1x)", {'MAX': 20, 'BIG': 10, 'NORMAL': 1, 'SMALL': 0.2, 'MIN': 0.1}),
]

for scheme_name, mults in schemes:
    total_units = 0
    vt_value = 0
    for i in range(N):
        tier = strategy_acc_spins_v1(rows, i)
        m = mults.get(tier, 1)
        total_units += m
        if is_vt(rows[i]):
            vt_value += m

    flat_units = N * 1.0
    flat_vt_val = total_vt * 1.0
    roi = vt_value / total_units if total_units > 0 else 0
    flat_roi = flat_vt_val / flat_units

    print(f"\n  {scheme_name}:")
    print(f"    Bet units: {total_units:.0f} (savings: {100*(1-total_units/flat_units):+.1f}%)")
    print(f"    VT value:  {vt_value:.1f} (uplift: {100*(vt_value/flat_vt_val-1):+.1f}%)")
    print(f"    ROI:       {100*(roi/flat_roi-1):+.1f}%")


print("\nDONE")
