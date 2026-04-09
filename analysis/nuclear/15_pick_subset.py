"""
Chunk 15: Pick the right ensemble size.

Greedy ordering from chunk 14 has steeply diminishing returns. Build the
union for each "first N greedy rules" and report catches / mb-per-hit /
lift, so we can pick the size that maximises catches per honest bet.

Also tries a couple of hand-curated small subsets focused on the
high-lift SML L-bucket rules.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('ev', os.path.join(os.path.dirname(__file__), '02_eval.py'))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)
spec14 = importlib.util.spec_from_file_location('e14', os.path.join(os.path.dirname(__file__), '14_causal_ensemble.py'))
e14 = importlib.util.module_from_spec(spec14); spec14.loader.exec_module(e14)


def union_simulate(rules, gaps):
    """Simulate the OR-union of rules causally, return catches/bets/total."""
    caught = set()
    bets = 0
    total = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        total += len(traj)
        for i in range(1, len(traj)):
            prev_spin = traj[i - 1]
            prev_spin['_traj_ref'] = traj
            prev_spin['_traj_idx'] = i - 1
            prev_spin['_prev_triple_type'] = gap.get('prev_real_triple')
            for fn in rules:
                d = fn(prev_spin, prev)
                if d:
                    bets += 1
                    if i == len(traj) - 1:
                        caught.add(gap_idx)
                    break
    return caught, bets, total


def fmt(caught, bets, total, n_gaps):
    n = len(caught)
    if not bets:
        return f"{n}/{n_gaps}  bet=0  mb=inf"
    bet_pct = 100 * bets / total
    mb = bets / n if n else float('inf')
    bhr = n / bets
    br = n_gaps / total
    lift = bhr / br if br else 0
    return f"{n:3d}/{n_gaps}  bet={bet_pct:4.2f}%  mb/hit={mb:5.1f}  lift={lift:4.2f}x"


def run():
    gaps = e14.all_gaps_with_prev()
    n_gaps = len(gaps)

    out = []
    out.append("=" * 90)
    out.append("CHUNK 15: PICK ENSEMBLE SIZE — sweet spot scan")
    out.append("=" * 90)

    # Greedy order from chunk 14, named so we can recreate them
    greedy_named = [
        ("SML L>=120 t_l=130 g=0.31",                e14.sml_fn(0, 120, None, None, 130, 0.31)),
        ("SML L>=140 t_l=130 g=0.29",                e14.sml_fn(0, 140, None, None, 130, 0.29)),
        ("COND shield t=150 g=0.30",                 e14.shield_cond_fn(150, 0.30, 'shield')),
        ("SML s=50 l=130 tL=100 g=0.31",             e14.sml_fn(50, 130, None, None, 100, 0.31)),
        ("COND steal t=130 g=0.29",                  e14.shield_cond_fn(130, 0.29, 'steal')),
        ("SML L>=130 t_l=130 g=0.28",                e14.sml_fn(0, 130, None, None, 130, 0.28)),
        ("SML L>=120 t_l=130 g=0.30",                e14.sml_fn(0, 120, None, None, 130, 0.30)),
        ("FLAT 115/0.34",                            e14.flat_fn(115, 0.34)),
        ("FLAT 150/0.28",                            e14.flat_fn(150, 0.28)),
        ("FLAT 130/0.31 stop=160",                   e14.flat_fn(130, 0.31, 160)),
        ("FLAT 130/0.28",                            e14.flat_fn(130, 0.28)),
    ]

    # Build subsets first-N for N = 1..11
    out.append("")
    out.append("--- First-N greedy subsets ---")
    out.append(f"{'N':>3s}  {'last rule added':>40s}  {'metrics':>40s}")
    for n in range(1, len(greedy_named) + 1):
        rules = [fn for _, fn in greedy_named[:n]]
        cs, bs, ts = union_simulate(rules, gaps)
        last = greedy_named[n-1][0]
        out.append(f"{n:>3d}  {last[:40]:>40s}  {fmt(cs, bs, ts, n_gaps):>40s}")

    # ----- Hand-curated lean subsets -----
    out.append("")
    out.append("--- Hand-curated lean subsets ---")

    # Subset A: pure SML L-bucket family (highest lift, lowest cost)
    subsetA = [
        ("SML L>=120 t_l=130 g=0.30", e14.sml_fn(0, 120, None, None, 130, 0.30)),
        ("SML L>=120 t_l=130 g=0.28", e14.sml_fn(0, 120, None, None, 130, 0.28)),
        ("SML L>=140 t_l=130 g=0.29", e14.sml_fn(0, 140, None, None, 130, 0.29)),
    ]
    rules = [fn for _, fn in subsetA]
    cs, bs, ts = union_simulate(rules, gaps)
    out.append(f"  A: SML L-only family ({len(subsetA)} rules)  -> {fmt(cs, bs, ts, n_gaps)}")
    for name, _ in subsetA: out.append(f"     - {name}")

    # Subset B: SML L-bucket + best flat + best conditional
    subsetB = subsetA + [
        ("FLAT 130/0.31 stop=160", e14.flat_fn(130, 0.31, 160)),
        ("COND steal t=130 g=0.29", e14.shield_cond_fn(130, 0.29, 'steal')),
    ]
    rules = [fn for _, fn in subsetB]
    cs, bs, ts = union_simulate(rules, gaps)
    out.append(f"  B: A + FLAT130/.31stop + COND steal ({len(subsetB)} rules)  -> {fmt(cs, bs, ts, n_gaps)}")
    for name, _ in subsetB[3:]: out.append(f"     - {name}")

    # Subset C: B + 2 more high-lift rules
    subsetC = subsetB + [
        ("COND shield t=150 g=0.30", e14.shield_cond_fn(150, 0.30, 'shield')),
        ("SML s=50 l=130 tL=100 g=0.31", e14.sml_fn(50, 130, None, None, 100, 0.31)),
    ]
    rules = [fn for _, fn in subsetC]
    cs, bs, ts = union_simulate(rules, gaps)
    out.append(f"  C: B + COND shield + SML s/l ({len(subsetC)} rules)  -> {fmt(cs, bs, ts, n_gaps)}")
    for name, _ in subsetC[5:]: out.append(f"     - {name}")

    # Subset D: C + FLAT 115/0.34
    subsetD = subsetC + [
        ("FLAT 115/0.34", e14.flat_fn(115, 0.34)),
    ]
    rules = [fn for _, fn in subsetD]
    cs, bs, ts = union_simulate(rules, gaps)
    out.append(f"  D: C + FLAT 115/.34 ({len(subsetD)} rules)  -> {fmt(cs, bs, ts, n_gaps)}")

    # Subset E: D + FLAT 130/0.30 (the old baseline)
    subsetE = subsetD + [
        ("FLAT 130/0.30", e14.flat_fn(130, 0.30)),
    ]
    rules = [fn for _, fn in subsetE]
    cs, bs, ts = union_simulate(rules, gaps)
    out.append(f"  E: D + FLAT 130/.30 ({len(subsetE)} rules)  -> {fmt(cs, bs, ts, n_gaps)}")

    # Per-account breakdown for the recommended subset
    out.append("")
    out.append("--- Per-account breakdown for subset C (8 rules) ---")
    rules = [fn for _, fn in subsetC]
    for acct in e14.ACCOUNTS:
        acct_indices = [i for i, g in enumerate(gaps) if g.get('account') == acct]
        acct_gaps = [g for g in gaps if g.get('account') == acct]
        cs, bs, ts = union_simulate(rules, acct_gaps)
        out.append(f"  {acct:6s}: {fmt(cs, bs, ts, len(acct_gaps))}")

    out_path = os.path.join(os.path.dirname(__file__), '15_pick_subset_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f"Saved -> {out_path}")
    print()
    for line in out[-20:]:
        print(line)


if __name__ == '__main__':
    run()
