"""
Chunk 16: Causal ensemble — pick the best real-data rules and compute
the union + greedy minimum cover.

Starts from top ~30 candidate rules from chunk 15 (causal sweep) and
builds the real ensemble using causal semantics end-to-end.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('e10', os.path.join(os.path.dirname(__file__), '10_ensemble.py'))
e10 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e10)

from collections import defaultdict

# Candidate pool from chunk 15 — top configs by various metrics
# name, factory-call-args, factory-fn
CANDIDATES = [
    # SHIELD-cond variants (top 10 by mb/hit on real data)
    ("SHIELD t150 g0.30", ('shield', 150, 0.30)),
    ("SHIELD t150 g0.28", ('shield', 150, 0.28)),
    ("SHIELD t150 g0.22", ('shield', 150, 0.22)),
    ("SHIELD t150 g0.24", ('shield', 150, 0.24)),
    ("SHIELD t140 g0.28", ('shield', 140, 0.28)),
    ("SHIELD t140 g0.22", ('shield', 140, 0.22)),
    ("SHIELD t130 g0.28", ('shield', 130, 0.28)),
    ("SHIELD t130 g0.22", ('shield', 130, 0.22)),
    ("SHIELD t140 g0.24", ('shield', 140, 0.24)),
    ("SHIELD t130 g0.24", ('shield', 130, 0.24)),
    # ATTACK-cond (test — attack is 78 gaps cohort)
    ("ATTACK t130 g0.24", ('attack', 130, 0.24)),
    ("ATTACK t130 g0.22", ('attack', 130, 0.22)),
    # SPINS-cond (test — spins-triple-before-acc)
    ("SPINS t130 g0.24", ('spins', 130, 0.24)),
    # Rate acceleration — best causal variants
    ("RA t130 r0.26 w8 s0.015", ('ra', 130, 0.26, 8, 0.015)),
    ("RA t130 r0.24 w8 s0.015", ('ra', 130, 0.24, 8, 0.015)),
    ("RA t130 r0.22 w8 s0.015", ('ra', 130, 0.22, 8, 0.015)),
    ("RA t130 r0.26 w5 s0.008", ('ra', 130, 0.26, 5, 0.008)),
    # COMBO — few survive phantom purge
    ("COMBO t130 a0.26 p0.20 s0.010", ('combo', 130, 0.26, 0.20, 10, 0.010)),
    ("COMBO t130 a0.24 p0.20 s0.010", ('combo', 130, 0.24, 0.20, 10, 0.010)),
    # Double gate (best non-shield)
    ("DG t130 acc0.28 spn0.24", ('dg', 130, 0.28, 0.24)),
    ("DG t130 acc0.28 spn0.26", ('dg', 130, 0.28, 0.26)),
    ("DG t120 acc0.28 spn0.26", ('dg', 120, 0.28, 0.26)),
    ("DG t140 acc0.28 spn0.26", ('dg', 140, 0.28, 0.26)),
    # Flat — lowered gates
    ("FLAT t130 g0.24", ('flat', 130, 0.24)),
    ("FLAT t130 g0.22", ('flat', 130, 0.22)),
    ("FLAT t150 g0.22", ('flat', 150, 0.22)),
]

def build_fn(spec):
    kind = spec[0]
    if kind == 'shield': return e10.shield_cond_fn(spec[1], spec[2], 'shield')
    if kind == 'attack': return e10.shield_cond_fn(spec[1], spec[2], 'attack')
    if kind == 'spins': return e10.shield_cond_fn(spec[1], spec[2], 'spins')
    if kind == 'ra': return e10.ra_fn(spec[1], spec[2], spec[3], spec[4])
    if kind == 'combo': return e10.combo_fn(spec[1], spec[2], spec[3], spec[4], spec[5])
    if kind == 'dg': return e10.double_gate_fn(spec[1], spec[2], spec[3])
    if kind == 'flat': return e10.flat_fn(spec[1], spec[2])
    raise ValueError(f"unknown kind: {kind}")


def run():
    gaps = e10.all_gaps_with_prev()
    total_gaps = len(gaps)
    total_spins = sum(len(g['trajectory']) for g in gaps)

    results = []
    results.append("=" * 120)
    results.append("CHUNK 16: CAUSAL ENSEMBLE — real-data rediscovery")
    results.append("=" * 120)
    results.append(f"Dataset: {total_gaps} ACC gaps / {total_spins} spins")
    results.append("")

    # Evaluate all candidates individually
    rule_data = {}
    results.append(f"{'rule':<50s}  {'catches':>10s}  {'bets':>5s}  {'mb/hit':>7s}  {'catch%':>7s}  {'lift':>6s}")
    results.append("-" * 100)
    for name, spec in CANDIDATES:
        fn = build_fn(spec)
        caught_set, bets, _ = e10.simulate_with_catch_flags(fn, gaps)
        n = len(caught_set)
        mb = bets / n if n else float('inf')
        bhr = n / bets if bets else 0
        br = total_gaps / total_spins
        lift = bhr / br if br else 0
        rule_data[name] = {'spec': spec, 'fn': fn, 'caught_set': caught_set,
                           'bets': bets, 'mb': mb, 'lift': lift, 'n': n}
        results.append(f"{name:<50s}  {n:>4d}/{total_gaps}   {bets:>5d}  {mb:>7.1f}  {100*n/total_gaps:>6.1f}%  {lift:>5.1f}x")

    # --- TRUE CAUSAL UNION (all candidates OR'd) ---
    results.append("")
    results.append("=" * 120)
    results.append("TRUE CAUSAL UNION (all candidates OR'd)")
    results.append("=" * 120)
    all_fns = [rule_data[name]['fn'] for name, _ in CANDIDATES]

    union_caught = set()
    union_bets = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        L = len(traj)
        if L < 2: continue
        for i in range(L - 1):
            spin = traj[i]
            spin['_traj_ref'] = traj
            spin['_traj_idx'] = i
            spin['_prev_triple_type'] = gap.get('prev_real_triple')
            any_bet = False
            for fn in all_fns:
                if fn(spin, prev):
                    any_bet = True
                    break
            if any_bet:
                union_bets += 1
                if i + 1 == L - 1:
                    union_caught.add(gap_idx)

    n_u = len(union_caught)
    mb_u = union_bets / n_u if n_u else float('inf')
    results.append(f"  Unique catches:  {n_u}/{total_gaps} ({100*n_u/total_gaps:.1f}%)")
    results.append(f"  Bet spins:       {union_bets}/{total_spins} ({100*union_bets/total_spins:.2f}%)")
    results.append(f"  mb/hit:          {mb_u:.1f}")

    # Per-account
    results.append("")
    results.append("  Per-account union:")
    for acct in ['Islam', 'Ahmed', 'Nick']:
        acct_gaps_idx = [i for i, g in enumerate(gaps) if g['account'] == acct]
        acct_total = len(acct_gaps_idx)
        acct_caught = len(union_caught & set(acct_gaps_idx))
        results.append(f"    {acct}: {acct_caught}/{acct_total} ({100*acct_caught/acct_total:.1f}%)")

    # --- GREEDY MINIMUM COVER ---
    # Pick configs one at a time that add the most NEW catches per added bet spin
    results.append("")
    results.append("=" * 120)
    results.append("GREEDY MINIMUM COVER — smallest subset to reach union with lowest mb/hit")
    results.append("=" * 120)

    remaining = set(union_caught)
    chosen = []
    available = list(CANDIDATES)

    while remaining:
        best_score = None
        best_idx = -1
        for i, (name, spec) in enumerate(available):
            d = rule_data[name]
            new_catches = d['caught_set'] & remaining
            if not new_catches:
                continue
            score = d['bets'] / len(new_catches)
            if best_score is None or score < best_score:
                best_score = score
                best_idx = i
        if best_idx < 0:
            break
        name, spec = available.pop(best_idx)
        d = rule_data[name]
        new_catches = d['caught_set'] & remaining
        chosen.append((name, len(new_catches)))
        remaining -= d['caught_set']

    results.append(f"\n  Chosen subset ({len(chosen)} rules):")
    for name, n_new in chosen:
        results.append(f"    + {name}  (+{n_new} new catches)")

    # True mb/hit of chosen subset (deduplicated bets)
    chosen_fns = [rule_data[name]['fn'] for name, _ in chosen]
    subset_caught = set()
    subset_bets = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        L = len(traj)
        if L < 2: continue
        for i in range(L - 1):
            spin = traj[i]
            spin['_traj_ref'] = traj
            spin['_traj_idx'] = i
            spin['_prev_triple_type'] = gap.get('prev_real_triple')
            any_bet = False
            for fn in chosen_fns:
                if fn(spin, prev):
                    any_bet = True
                    break
            if any_bet:
                subset_bets += 1
                if i + 1 == L - 1:
                    subset_caught.add(gap_idx)

    sub_mb = subset_bets / len(subset_caught) if subset_caught else float('inf')
    results.append(f"\n  TRUE simulation of greedy subset:")
    results.append(f"    catches:    {len(subset_caught)}/{total_gaps}")
    results.append(f"    bet spins:  {subset_bets}/{total_spins} ({100*subset_bets/total_spins:.2f}%)")
    results.append(f"    mb/hit:     {sub_mb:.2f}")

    # --- COOLDOWN TEST on the greedy subset ---
    results.append("")
    results.append("=" * 120)
    results.append("COOLDOWN TEST on greedy subset")
    results.append("=" * 120)
    results.append(f"{'strategy':>30s}  {'catches':>10s}  {'bets':>5s}  {'mb/hit':>7s}")
    results.append("-" * 65)

    def simulate_subset(cooldown_after=0, cooldown_len=0):
        caught = set()
        bet = 0
        for gap_idx, gap in enumerate(gaps):
            prev = gap.get('prev_gap_length')
            traj = gap['trajectory']
            L = len(traj)
            if L < 2: continue
            consec = 0
            cool = 0
            for i in range(L - 1):
                spin = traj[i]
                spin['_traj_ref'] = traj
                spin['_traj_idx'] = i
                spin['_prev_triple_type'] = gap.get('prev_real_triple')
                if cool > 0:
                    cool -= 1; consec = 0; continue
                wants = False
                for fn in chosen_fns:
                    if fn(spin, prev): wants = True; break
                if wants:
                    bet += 1; consec += 1
                    if i + 1 == L - 1: caught.add(gap_idx)
                    if cooldown_after > 0 and consec >= cooldown_after:
                        cool = cooldown_len; consec = 0
                else:
                    consec = 0
        return len(caught), bet

    c, b = simulate_subset()
    results.append(f"{'no cooldown':>30s}  {c:>4d}/{total_gaps}  {b:>5d}  {b/max(c,1):>7.2f}")
    for ca, cl in [(3,2),(4,2),(5,2),(5,3),(6,3),(8,3),(10,3),(10,5),(12,3),(15,5)]:
        c, b = simulate_subset(ca, cl)
        results.append(f"{f'cooldown {ca}/{cl}':>30s}  {c:>4d}/{total_gaps}  {b:>5d}  {b/max(c,1):>7.2f}")

    out_path = os.path.join(os.path.dirname(__file__), '16_causal_ensemble.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print(f"Saved -> {out_path}")
    print(f"\nUnion: {n_u}/{total_gaps} ({100*n_u/total_gaps:.1f}%)  mb/hit: {mb_u:.1f}")
    print(f"Greedy minimum cover: {len(chosen)} rules -> {len(subset_caught)} catches @ {sub_mb:.2f} mb/hit")


if __name__ == '__main__':
    run()
