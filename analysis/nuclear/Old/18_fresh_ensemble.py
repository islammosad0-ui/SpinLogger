"""
Chunk 18: Fresh ensemble using the new discoveries from chunk 17.

Takes the top causal rules from the fresh hunt and builds the REAL ensemble.
Includes the STEAL-cond discovery (the biggest find), gap_start_pct, symbol
ratios, and multi-condition rules.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('e10', os.path.join(os.path.dirname(__file__), '10_ensemble.py'))
e10 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e10)
from collections import defaultdict


# ============================================================
# Candidate rules — the BEST from causal sweeps (chunks 15, 16, 17)
# ============================================================
def make_steal(t, g):
    def f(spin, prev):
        if spin.get('_prev_triple_type') != 'steal': return False
        sp = spin['sa_spins']
        if sp < t: return False
        return (spin['sa_acc']/sp) >= g if sp else False
    return f

def make_shield(t, g):
    def f(spin, prev):
        if spin.get('_prev_triple_type') != 'shield': return False
        sp = spin['sa_spins']
        if sp < t: return False
        return (spin['sa_acc']/sp) >= g if sp else False
    return f

def make_spins_cond(t, g):
    def f(spin, prev):
        if spin.get('_prev_triple_type') != 'spins': return False
        sp = spin['sa_spins']
        if sp < t: return False
        return (spin['sa_acc']/sp) >= g if sp else False
    return f

def make_spins_cond_L(L_min, t, g):
    def f(spin, prev):
        if prev is None or prev < L_min: return False
        if spin.get('_prev_triple_type') != 'spins': return False
        sp = spin['sa_spins']
        if sp < t: return False
        return (spin['sa_acc']/sp) >= g if sp else False
    return f

def make_acc_atk_ratio(t, min_ratio):
    def f(spin, prev):
        sp = spin['sa_spins']
        if sp < t: return False
        atk = spin.get('sa_atk', 0)
        if atk == 0: return spin['sa_acc'] > 0
        return (spin['sa_acc'] / atk) >= min_ratio
    return f

def make_acc_shd_ratio(t, min_ratio):
    def f(spin, prev):
        sp = spin['sa_spins']
        if sp < t: return False
        shd = spin.get('sa_shd', 0)
        if shd == 0: return spin['sa_acc'] > 0
        return (spin['sa_acc'] / shd) >= min_ratio
    return f

def make_shield_multi(t, acc_g, max_shd):
    def f(spin, prev):
        if spin.get('_prev_triple_type') != 'shield': return False
        sp = spin['sa_spins']
        if sp < t: return False
        if (spin['sa_acc']/sp) < acc_g: return False
        return (spin.get('sa_shd', 0)/sp) <= max_shd
    return f

def make_gap_start_pct(t, min_pct):
    def f(spin, prev):
        sp = spin['sa_spins']
        if sp < t: return False
        return spin.get('_gap_start_pct', 0) >= min_pct
    return f

def make_mission_remaining(t, max_rem):
    def f(spin, prev):
        sp = spin['sa_spins']
        if sp < t: return False
        total = spin.get('accum_total', 0)
        curr = spin.get('accum_current', 0)
        return (total - curr) <= max_rem and total > 0
    return f

def make_ss_spn_low(t, max_g):
    def f(spin, prev):
        sp = spin['sa_spins']
        if sp < t: return False
        ss_sp = spin.get('ss_spins', 0)
        if ss_sp == 0: return False
        return (spin.get('ss_spn', 0) / ss_sp) <= max_g
    return f

def make_shield_L(L_min, t, g):
    def f(spin, prev):
        if prev is None or prev < L_min: return False
        if spin.get('_prev_triple_type') != 'shield': return False
        sp = spin['sa_spins']
        if sp < t: return False
        return (spin['sa_acc']/sp) >= g if sp else False
    return f

def make_steal_L(L_min, t, g):
    def f(spin, prev):
        if prev is None or prev < L_min: return False
        if spin.get('_prev_triple_type') != 'steal': return False
        sp = spin['sa_spins']
        if sp < t: return False
        return (spin['sa_acc']/sp) >= g if sp else False
    return f


# The curated pool
CANDIDATES = [
    # --- Ultra-precision (< 20 mb/hit) ---
    ("STEAL t150 g0.30",          make_steal(150, 0.30)),        # 5/271 @ 6.2 mb, 17x lift — THE BEST
    ("STEAL t150 g0.28",          make_steal(150, 0.28)),        # 5/271 @ 11.4 mb
    ("SHIELD+acc0.30+shd<0.20 t150", make_shield_multi(150, 0.30, 0.20)), # 4/271 @ 13.2 mb
    ("acc/atk>=0.8 t100",         make_acc_atk_ratio(100, 0.8)), # 5/271 @ 13.8 mb
    ("STEAL t140 g0.30",          make_steal(140, 0.30)),        # 6/271 @ 14.2 mb
    ("steal+L>=100 t130 g0.26",   make_steal_L(100, 130, 0.26)), # 5/271 @ 15.2 mb
    ("STEAL t130 g0.28",          make_steal(130, 0.28)),        # 14/271 @ 16.7 mb — best STEAL with volume
    ("STEAL t130 g0.30",          make_steal(130, 0.30)),        # 9/271 @ 17.0 mb
    ("SHIELD t150 g0.30",         make_shield(150, 0.30)),       # 8/271 @ 18.4 mb — the best SHIELD
    ("SHIELD t150 g0.28",         make_shield(150, 0.28)),       # 14/271 @ 22.1 mb
    ("spins+L>=100 t130 g0.22",   make_spins_cond_L(100, 130, 0.22)), # 3/271 @ 8.7 mb — rare but precise

    # --- Mid-catch / good efficiency (20-30 mb/hit) ---
    ("STEAL t120 g0.28",          make_steal(120, 0.28)),        # 15/271 @ 25.5 mb
    ("STEAL t130 g0.26",          make_steal(130, 0.26)),        # 18/271 @ 27.8 mb
    ("STEAL t130 g0.22",          make_steal(130, 0.22)),        # 20/271 @ 28.1 mb
    ("gap_start_pct>=60 t130",    make_gap_start_pct(130, 60)),  # 43/271 @ 27.4 mb — BIG catch count
    ("gap_start_pct>=50 t130",    make_gap_start_pct(130, 50)),  # 49/271 @ 31.9 mb
    ("gap_start_pct>=40 t130",    make_gap_start_pct(130, 40)),  # 56/271 @ 32.9 mb
    ("mission_remaining<=10000 t130", make_mission_remaining(130, 10000)), # 20/271 @ 30.6 mb
    ("SHIELD t130 g0.22",         make_shield(130, 0.22)),       # 27/271 @ 31.4 mb
    ("SHIELD t140 g0.22",         make_shield(140, 0.22)),       # 21/271 @ 28.4 mb
    ("DG t130 acc0.28 spn0.26",   e10.double_gate_fn(130, 0.28, 0.26)), # 22/271 @ 33.0 mb

    # --- High-catch (30-45 mb/hit) ---
    ("DG t130 acc0.28 spn0.24",   e10.double_gate_fn(130, 0.28, 0.24)), # 36/271 @ 34.9 mb
    ("acc/shd>=1.2 t130",         make_acc_shd_ratio(130, 1.2)), # 73/271 @ 36.9 mb — ratio signal
    ("ss_spn<=0.25 t130",         make_ss_spn_low(130, 0.25)),   # 75/271 @ 37.4 mb — cross-stream
]


def run():
    gaps = e10.all_gaps_with_prev()
    total_gaps = len(gaps)
    total_spins = sum(len(g['trajectory']) for g in gaps)

    # Precompute all the derived fields that the new rules need
    for gap in gaps:
        traj = gap['trajectory']
        start_pct = traj[0].get('accum_pct', 0) if traj else 0
        for spin in traj:
            spin['_gap_start_pct'] = start_pct
            spin['_prev_triple_type'] = gap.get('prev_real_triple')

    lines = []
    lines.append("=" * 120)
    lines.append("CHUNK 18: FRESH ENSEMBLE — post-phantom-bug real rules")
    lines.append("=" * 120)
    lines.append(f"Dataset: {total_gaps} ACC gaps / {total_spins} spins")
    lines.append("")

    # Evaluate each candidate
    rule_data = {}
    lines.append(f"{'rule':<40s}  {'catches':>10s}  {'bets':>5s}  {'mb/hit':>7s}  {'lift':>6s}")
    lines.append("-" * 85)
    for name, fn in CANDIDATES:
        caught_set, bets, _ = e10.simulate_with_catch_flags(fn, gaps)
        n = len(caught_set)
        mb = bets / n if n else float('inf')
        bhr = n / bets if bets else 0
        base_rate = total_gaps / total_spins
        lift = bhr / base_rate if base_rate else 0
        rule_data[name] = {'fn': fn, 'caught_set': caught_set, 'bets': bets, 'n': n, 'mb': mb, 'lift': lift}
        lines.append(f"{name:<40s}  {n:>4d}/{total_gaps}   {bets:>5d}  {mb:>7.1f}  {lift:>5.1f}x")

    # --- TRUE UNION ---
    lines.append("")
    lines.append("=" * 120)
    lines.append("TRUE CAUSAL UNION")
    lines.append("=" * 120)
    all_fns = [rule_data[n]['fn'] for n, _ in CANDIDATES]
    union_caught = set()
    union_bets = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        L = len(traj)
        if L < 2: continue
        for i in range(L - 1):
            spin = traj[i]
            spin['_traj_ref'] = traj; spin['_traj_idx'] = i
            any_bet = False
            for fn in all_fns:
                if fn(spin, prev): any_bet = True; break
            if any_bet:
                union_bets += 1
                if i + 1 == L - 1:
                    union_caught.add(gap_idx)
    n_u = len(union_caught)
    mb_u = union_bets / n_u if n_u else float('inf')
    lines.append(f"  Catches:    {n_u}/{total_gaps} ({100*n_u/total_gaps:.1f}%)")
    lines.append(f"  Bet spins:  {union_bets}/{total_spins} ({100*union_bets/total_spins:.2f}%)")
    lines.append(f"  mb/hit:     {mb_u:.1f}")
    lines.append("")
    lines.append("  Per-account:")
    for acct in ['Islam', 'Ahmed', 'Nick']:
        ai = [i for i, g in enumerate(gaps) if g['account'] == acct]
        at = len(ai)
        ac = len(union_caught & set(ai))
        lines.append(f"    {acct}: {ac}/{at} ({100*ac/at:.1f}%)")

    # --- GREEDY MINIMUM COVER ---
    lines.append("")
    lines.append("=" * 120)
    lines.append("GREEDY MINIMUM COVER")
    lines.append("=" * 120)

    remaining = set(union_caught)
    chosen = []
    available = list(CANDIDATES)

    while remaining:
        best_score = None
        best_idx = -1
        for i, (name, _) in enumerate(available):
            d = rule_data[name]
            new_catches = d['caught_set'] & remaining
            if not new_catches: continue
            score = d['bets'] / len(new_catches)
            if best_score is None or score < best_score:
                best_score = score; best_idx = i
        if best_idx < 0: break
        name, _ = available.pop(best_idx)
        d = rule_data[name]
        new = d['caught_set'] & remaining
        chosen.append((name, len(new)))
        remaining -= d['caught_set']

    lines.append(f"\n  Chosen subset ({len(chosen)} rules):")
    for name, n_new in chosen:
        d = rule_data[name]
        lines.append(f"    + {name:<40s} (+{n_new:>2d} new)  solo: {d['n']}/{total_gaps} @ {d['mb']:.1f} mb")

    # True mb/hit of chosen subset
    chosen_fns = [rule_data[n]['fn'] for n, _ in chosen]
    subset_caught = set()
    subset_bets = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        L = len(traj)
        if L < 2: continue
        for i in range(L - 1):
            spin = traj[i]
            spin['_traj_ref'] = traj; spin['_traj_idx'] = i
            any_bet = False
            for fn in chosen_fns:
                if fn(spin, prev): any_bet = True; break
            if any_bet:
                subset_bets += 1
                if i + 1 == L - 1:
                    subset_caught.add(gap_idx)

    sub_mb = subset_bets / len(subset_caught) if subset_caught else float('inf')
    lines.append(f"\n  TRUE simulation of greedy subset:")
    lines.append(f"    catches:    {len(subset_caught)}/{total_gaps} ({100*len(subset_caught)/total_gaps:.1f}%)")
    lines.append(f"    bet spins:  {subset_bets}/{total_spins} ({100*subset_bets/total_spins:.2f}%)")
    lines.append(f"    mb/hit:     {sub_mb:.2f}")

    # --- SMALL "PRECISION-ONLY" ENSEMBLE (only <20 mb/hit rules) ---
    lines.append("")
    lines.append("=" * 120)
    lines.append("PRECISION-ONLY ENSEMBLE (only rules <= 20 mb/hit solo)")
    lines.append("=" * 120)
    precision_rules = [(n, rule_data[n]['fn']) for n, _ in CANDIDATES if rule_data[n]['mb'] <= 20]
    lines.append(f"  {len(precision_rules)} rules chosen:")
    for n, _ in precision_rules:
        d = rule_data[n]
        lines.append(f"    + {n:<40s}  {d['n']}/{total_gaps} @ {d['mb']:.1f} mb")

    prec_fns = [fn for _, fn in precision_rules]
    prec_caught = set()
    prec_bets = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        L = len(traj)
        if L < 2: continue
        for i in range(L - 1):
            spin = traj[i]
            spin['_traj_ref'] = traj; spin['_traj_idx'] = i
            any_bet = False
            for fn in prec_fns:
                if fn(spin, prev): any_bet = True; break
            if any_bet:
                prec_bets += 1
                if i + 1 == L - 1:
                    prec_caught.add(gap_idx)
    pm = prec_bets / len(prec_caught) if prec_caught else float('inf')
    lines.append(f"\n  Precision-only result:")
    lines.append(f"    catches:    {len(prec_caught)}/{total_gaps} ({100*len(prec_caught)/total_gaps:.1f}%)")
    lines.append(f"    bet spins:  {prec_bets}/{total_spins}")
    lines.append(f"    mb/hit:     {pm:.2f}")

    out_path = os.path.join(os.path.dirname(__file__), '18_fresh_ensemble.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Saved -> {out_path}")
    print(f"\nFull union: {n_u}/{total_gaps} @ {mb_u:.1f} mb")
    print(f"Greedy min cover: {len(chosen)} rules -> {len(subset_caught)}/{total_gaps} @ {sub_mb:.2f} mb")
    print(f"Precision-only: {len(prec_caught)}/{total_gaps} @ {pm:.2f} mb")


if __name__ == '__main__':
    run()
