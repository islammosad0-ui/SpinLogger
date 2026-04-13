#!/usr/bin/env python3
"""
61_strategy_sim.py - Simulate betting strategy on 1,107 spins.
Answers: how many VTs caught, at what cost (big bets per hit)?
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
        r['is_triple'] = r['is_triple'] == 'True'
        r['is_valuable'] = r['is_valuable'] == 'True'
        r['sn'] = int(r['sn'])
        r['reel_1'] = r['reel_1']
        rows.append(r)

N = len(rows)
total_vt = sum(1 for r in rows if r['is_valuable'])
total_triple = sum(1 for r in rows if r['is_triple'])

print("=" * 80)
print("  61_STRATEGY_SIM -- Betting simulation on 1,107 spins")
print("=" * 80)
print(f"  Total spins: {N}")
print(f"  Total triples: {total_triple} ({100*total_triple/N:.1f}%)")
print(f"  Total valuable triples: {total_vt} ({100*total_vt/N:.1f}%)")
print(f"  Base VT rate: 1 per {N/total_vt:.1f} spins")

# =====================================================================
# STRATEGY DEFINITIONS
# =====================================================================

def strategy_oracle(rows, i):
    """Perfect knowledge - bet big only on VT spins."""
    return 'MAX' if rows[i]['is_valuable'] else 'MIN'

def strategy_flat(rows, i):
    """Always bet same."""
    return 'NORMAL'

def strategy_star(rows, i):
    """Only the 5/5 CV signal: prev spin r2=4, r3=5 -> bet big."""
    if i == 0:
        return 'NORMAL'
    prev = rows[i-1]
    if prev['r2'] == 4 and prev['r3'] == 5:
        return 'MAX'
    return 'NORMAL'

def strategy_validated(rows, i):
    """All 4/5+ CV validated signals."""
    if i == 0:
        return 'NORMAL'
    prev = rows[i-1]

    # Anti-clustering: after valuable, bet min for 7 spins
    for lookback in range(1, 8):
        if i - lookback >= 0 and rows[i - lookback]['is_valuable']:
            return 'MIN'

    # Positive signals (any match -> BIG)
    if prev['r2'] == 4 and prev['r3'] == 5:  # 5/5 CV, +18pp
        return 'MAX'
    if prev['r1'] == 4 and prev['r3'] == 5:  # 4/5 CV, +13pp
        return 'BIG'
    if prev['r1'] == 6 and prev['r2'] == 4:  # 4/5 CV, +6pp
        return 'BIG'
    if prev['r2'] == 1 and prev['r3'] == 0:  # 4/5 CV, +6pp
        return 'BIG'

    # Single idx signals
    if prev['r3'] == 5:  # 4/5 CV, +5pp
        return 'BIG'
    if prev['r2'] == 4:  # 4/5 CV, +4pp
        return 'BIG'
    if prev['r1'] == 4:  # 4/5 CV, +4pp
        return 'BIG'

    # Negative signals -> MIN
    if prev['r3'] == 1:  # 4/5 neg
        return 'MIN'
    if prev['r2'] == 6:  # 4/5 neg
        return 'MIN'
    if prev['r2'] == 7:  # 4/5 neg
        return 'MIN'
    if prev['r1'] == 3:  # 4/5 neg
        return 'MIN'

    return 'NORMAL'

def strategy_composite(rows, i):
    """Full composite scorer from section 10."""
    if i == 0:
        return 'NORMAL'
    prev = rows[i-1]
    score = 0

    # Idx signals
    if prev['r3'] == 5: score += 2
    if prev['r2'] == 4: score += 1
    if prev['r1'] == 4: score += 1
    if prev['r3'] == 1: score -= 1
    if prev['r2'] == 6: score -= 1
    if prev['r2'] == 7: score -= 1
    if prev['r1'] == 3: score -= 1

    # Pair signals
    if prev['r1'] == 4 and prev['r3'] == 5: score += 2
    if prev['r1'] == 3 and prev['r3'] == 8: score -= 1

    # Anti-clustering
    for lookback in range(1, 8):
        if i - lookback >= 0 and rows[i - lookback]['is_valuable']:
            penalty = max(0, 4 - lookback)  # -3, -2, -1 for 1,2,3 back
            score -= penalty
            break

    # Overdue bonus
    last_val = -100
    for j in range(max(0, i-20), i):
        if rows[j]['is_valuable']:
            last_val = j
    gap = i - last_val
    if gap >= 15: score += 2
    elif gap >= 10: score += 1

    if score >= 4: return 'MAX'
    if score >= 2: return 'BIG'
    if score <= -3: return 'MIN'
    if score <= -1: return 'SMALL'
    return 'NORMAL'

def strategy_composite_v2(rows, i):
    """Fixed composite: adds (r2=4,r3=5) pair bonus (5/5 CV star signal)."""
    if i == 0:
        return 'NORMAL'
    prev = rows[i-1]
    score = 0

    # Idx signals (same as v1)
    if prev['r3'] == 5: score += 2   # 4/5 CV, +5.2pp
    if prev['r2'] == 4: score += 1   # 4/5 CV, +4.1pp
    if prev['r1'] == 4: score += 1   # 4/5 CV, +4.1pp
    if prev['r3'] == 1: score -= 1   # 4/5 neg
    if prev['r2'] == 6: score -= 1   # 4/5 neg
    if prev['r2'] == 7: score -= 1   # 4/5 neg
    if prev['r1'] == 3: score -= 1   # 4/5 neg

    # Pair signals -- FIXED: add (r2=4, r3=5) star signal bonus
    # Individuals already give +3 (r3=5:+2, r2=4:+1). Pair adds synergy.
    if prev['r2'] == 4 and prev['r3'] == 5: score += 2  # 5/5 CV, +18.1pp
    if prev['r1'] == 4 and prev['r3'] == 5: score += 2  # 4/5 CV, +12.8pp
    if prev['r1'] == 3 and prev['r3'] == 8: score -= 1  # 5/5 neg

    # Anti-clustering: after VALUABLE triple, suppress next 7 spins
    for lookback in range(1, 8):
        if i - lookback >= 0 and rows[i - lookback]['is_valuable']:
            penalty = max(0, 4 - lookback)  # -3, -2, -1 for 1,2,3 back
            score -= penalty
            break

    # Overdue bonus
    last_val = -100
    for j in range(max(0, i-20), i):
        if rows[j]['is_valuable']:
            last_val = j
    gap = i - last_val
    if gap >= 15: score += 2
    elif gap >= 10: score += 1

    if score >= 4: return 'MAX'
    if score >= 2: return 'BIG'
    if score <= -3: return 'MIN'
    if score <= -1: return 'SMALL'
    return 'NORMAL'

# =====================================================================
# SIMULATION ENGINE
# =====================================================================

def simulate(rows, strategy_fn, name, bet_multipliers=None):
    """
    Simulate a strategy. Returns stats.
    bet_multipliers: dict mapping tier -> multiplier (default: MAX=10, BIG=5, NORMAL=1, SMALL=0.5, MIN=0.1)
    """
    if bet_multipliers is None:
        bet_multipliers = {'MAX': 10, 'BIG': 5, 'NORMAL': 1, 'SMALL': 0.5, 'MIN': 0.1}

    decisions = []
    for i in range(N):
        tier = strategy_fn(rows, i)
        mult = bet_multipliers.get(tier, 1)
        is_vt = rows[i]['is_valuable']
        is_triple = rows[i]['is_triple']
        decisions.append({
            'spin': i,
            'tier': tier,
            'mult': mult,
            'is_vt': is_vt,
            'is_triple': is_triple,
        })

    # Stats
    tier_counts = Counter(d['tier'] for d in decisions)
    tier_vt = defaultdict(int)
    tier_triple = defaultdict(int)
    for d in decisions:
        if d['is_vt']:
            tier_vt[d['tier']] += 1
        if d['is_triple']:
            tier_triple[d['tier']] += 1

    # Total "bet units" spent and earned
    total_bet_units = sum(d['mult'] for d in decisions)
    flat_bet_units = N * 1.0  # flat betting comparison

    # VT caught at BIG+ (mult >= 5)
    vt_caught_big = sum(1 for d in decisions if d['is_vt'] and d['mult'] >= 5)
    vt_caught_max = sum(1 for d in decisions if d['is_vt'] and d['mult'] >= 10)
    vt_caught_any_elevated = sum(1 for d in decisions if d['is_vt'] and d['mult'] > 1)
    vt_missed = sum(1 for d in decisions if d['is_vt'] and d['mult'] <= 1)
    vt_at_min = sum(1 for d in decisions if d['is_vt'] and d['mult'] < 1)

    # Big bets wasted (big bet but no VT)
    big_bets = sum(1 for d in decisions if d['mult'] >= 5)
    big_bet_hits = sum(1 for d in decisions if d['mult'] >= 5 and d['is_vt'])
    big_bet_miss = big_bets - big_bet_hits

    # Weighted VT value (multiplier * VT)
    weighted_vt = sum(d['mult'] for d in decisions if d['is_vt'])
    flat_vt = total_vt * 1.0  # flat betting would get 87 * 1x = 87 units of VT value

    # Weighted cost of non-VT spins
    cost_non_vt = sum(d['mult'] for d in decisions if not d['is_vt'])
    flat_cost = (N - total_vt) * 1.0

    print(f"\n{'=' * 70}")
    print(f"  STRATEGY: {name}")
    print(f"{'=' * 70}")
    print(f"\n  Tier distribution:")
    for tier in ['MAX', 'BIG', 'NORMAL', 'SMALL', 'MIN']:
        n = tier_counts.get(tier, 0)
        vt = tier_vt.get(tier, 0)
        tri = tier_triple.get(tier, 0)
        if n > 0:
            print(f"    {tier:>7}: {n:>4} spins ({100*n/N:>5.1f}%) | "
                  f"{vt:>2} VT caught ({100*vt/max(n,1):>5.1f}% hit rate) | "
                  f"{tri:>3} triples ({100*tri/n:>5.1f}%)")

    print(f"\n  VT capture summary:")
    print(f"    Total VT in data:           {total_vt}")
    print(f"    VT caught at MAX (10x):     {vt_caught_max}")
    print(f"    VT caught at BIG+ (>=5x):   {vt_caught_big}")
    print(f"    VT caught at elevated (>1x):{vt_caught_any_elevated}")
    print(f"    VT at normal (1x):          {total_vt - vt_caught_any_elevated - vt_at_min}")
    print(f"    VT wasted at MIN (<1x):     {vt_at_min}")
    print(f"    VT missed (<=1x):           {vt_missed}")

    print(f"\n  Efficiency:")
    print(f"    Big bets placed (>=5x):     {big_bets}")
    print(f"    Big bets that hit VT:       {big_bet_hits}")
    if big_bets > 0:
        print(f"    Big bet hit rate:           {100*big_bet_hits/big_bets:.1f}% "
              f"({big_bets/max(big_bet_hits,1):.1f} bets per VT)")

    print(f"\n  Value (bet units):")
    print(f"    Total bet units spent:      {total_bet_units:.0f} (flat would be {flat_bet_units:.0f})")
    print(f"    Savings vs flat:            {100*(1 - total_bet_units/flat_bet_units):+.1f}%")
    print(f"    Weighted VT value:          {weighted_vt:.1f} (flat would be {flat_vt:.0f})")
    print(f"    VT value uplift vs flat:    {100*(weighted_vt/flat_vt - 1):+.1f}%")
    print(f"    Cost on non-VT spins:       {cost_non_vt:.0f} (flat would be {flat_cost:.0f})")
    print(f"    Non-VT cost savings:        {100*(1 - cost_non_vt/flat_cost):+.1f}%")

    # ROI-like metric: weighted VT value / total bet units
    roi = weighted_vt / total_bet_units if total_bet_units > 0 else 0
    flat_roi = flat_vt / flat_bet_units
    print(f"\n  ROI metric (VT_value / bet_units):")
    print(f"    Strategy ROI:  {roi:.4f}")
    print(f"    Flat ROI:      {flat_roi:.4f}")
    print(f"    Improvement:   {100*(roi/flat_roi - 1):+.1f}%")

    return decisions

# =====================================================================
# RUN ALL STRATEGIES
# =====================================================================

print("\n\n" + "#" * 80)
print("#  SIMULATION RESULTS")
print("#" * 80)

simulate(rows, strategy_flat, "FLAT (baseline)")
simulate(rows, strategy_oracle, "ORACLE (perfect knowledge)")
simulate(rows, strategy_star, "STAR SIGNAL ONLY (r2=4, r3=5)")
simulate(rows, strategy_validated, "ALL VALIDATED SIGNALS")
simulate(rows, strategy_composite, "COMPOSITE SCORER (v1)")
simulate(rows, strategy_composite_v2, "COMPOSITE SCORER v2 (fixed)")

# =====================================================================
# DETAILED: Show every VT and what bet level it got
# =====================================================================
print("\n\n" + "=" * 80)
print("  DETAILED: Every valuable triple + bet tier (composite v2 strategy)")
print("=" * 80)

decisions = []
for i in range(N):
    tier = strategy_composite_v2(rows, i)
    decisions.append(tier)

print(f"\n  {'Spin#':>6} {'r1':>3} {'r2':>3} {'r3':>3} {'Symbol':>15} {'BetTier':>8} {'Prev_r2':>7} {'Prev_r3':>7} {'Why':>20}")
print("  " + "-" * 95)

vt_by_tier = defaultdict(list)
for i in range(N):
    if rows[i]['is_valuable']:
        tier = decisions[i]
        prev_r2 = rows[i-1]['r2'] if i > 0 else '-'
        prev_r3 = rows[i-1]['r3'] if i > 0 else '-'

        # Determine why this tier
        why = ''
        if i > 0:
            p = rows[i-1]
            if p['r2'] == 4 and p['r3'] == 5: why = 'r2=4,r3=5'
            elif p['r1'] == 4 and p['r3'] == 5: why = 'r1=4,r3=5'
            elif p['r3'] == 5: why = 'r3=5'
            elif p['r2'] == 4: why = 'r2=4'
            elif p['r1'] == 4: why = 'r1=4'

            # Check anti-clustering
            for lb in range(1, 8):
                if i - lb >= 0 and rows[i - lb]['is_valuable']:
                    why = f'anti-clust({lb})'
                    break

        vt_by_tier[tier].append(i)
        print(f"  {i:>6} {rows[i]['r1']:>3} {rows[i]['r2']:>3} {rows[i]['r3']:>3} "
              f"{rows[i]['reel_1']:>15} {tier:>8} {prev_r2:>7} {prev_r3:>7} {why:>20}")

print(f"\n  VT count by tier:")
for tier in ['MAX', 'BIG', 'NORMAL', 'SMALL', 'MIN']:
    n = len(vt_by_tier.get(tier, []))
    if n > 0:
        print(f"    {tier:>7}: {n:>2} VTs")

# =====================================================================
# WHAT-IF: Different bet multiplier schemes
# =====================================================================
print("\n\n" + "=" * 80)
print("  WHAT-IF: Different bet multiplier schemes (composite v2 strategy)")
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
    non_vt_cost = 0
    for i in range(N):
        tier = strategy_composite_v2(rows, i)
        m = mults.get(tier, 1)
        total_units += m
        if rows[i]['is_valuable']:
            vt_value += m
        else:
            non_vt_cost += m

    flat_units = N * 1.0
    flat_vt_val = total_vt * 1.0
    roi = vt_value / total_units if total_units > 0 else 0
    flat_roi = flat_vt_val / flat_units

    print(f"\n  {scheme_name}:")
    print(f"    Total bet units: {total_units:.0f} (flat: {flat_units:.0f}, "
          f"savings: {100*(1-total_units/flat_units):+.1f}%)")
    print(f"    VT value:        {vt_value:.1f} (flat: {flat_vt_val:.0f}, "
          f"uplift: {100*(vt_value/flat_vt_val - 1):+.1f}%)")
    print(f"    ROI improvement: {100*(roi/flat_roi - 1):+.1f}%")

print("\nDONE")
