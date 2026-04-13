"""
Chunk 12: Causal validation of the existing 16-rule ensemble.

Re-runs the same 16 configs from 10_ensemble.py under CAUSAL evaluation —
the strategy is evaluated on counters at end of the PREVIOUS spin (the
state visible to the user before they pressed the spin we're scoring),
not the post-spin state that includes the triple's own symbols.

Output: a per-rule before/after table + causal union/greedy-cover + a
list of which gaps are still catchable causally.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('ev', os.path.join(os.path.dirname(__file__), '02_eval.py'))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)
spec10 = importlib.util.spec_from_file_location('ens', os.path.join(os.path.dirname(__file__), '10_ensemble.py'))
ens = importlib.util.module_from_spec(spec10); spec10.loader.exec_module(ens)

import pickle
from pathlib import Path

GAPS_PATH = Path(__file__).parent / 'gaps.pkl'
ACCOUNTS  = ['Islam', 'Ahmed', 'Nick']


def all_gaps_with_prev():
    with open(GAPS_PATH, 'rb') as f:
        data = pickle.load(f)
    out = []
    for acct in ACCOUNTS:
        raw = data[acct]['gaps'].get('accumulation', [])
        for i, g in enumerate(raw):
            g2 = dict(g)
            g2['prev_gap_length'] = raw[i-1]['length'] if i > 0 else None
            g2['account'] = acct
            out.append(g2)
    return out


def simulate_causal(fn, gaps):
    """
    Causal version of 10_ensemble.simulate_with_catch_flags.

    Strategy fn(spin_record, prev_gap_length) is evaluated on traj[i-1] —
    the counter snapshot at end of the previous spin. Spin 0 of every gap
    is unbettable (counters were just reset). A catch requires the strategy
    to fire on the spin immediately before the triple landed.

    Slope-aware rules read _traj_ref / _traj_idx from the injected dict.
    We set _traj_idx = i-1 so the slope window looks `win` spins back from
    the prior-spin context, matching what the live tracker sees.
    """
    caught_set = set()
    bet_spins = 0
    total_spins = 0

    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        total_spins += len(traj)

        for i in range(1, len(traj)):
            prev_spin = traj[i - 1]
            prev_spin['_traj_ref'] = traj
            prev_spin['_traj_idx'] = i - 1
            prev_spin['_prev_triple_type'] = gap.get('prev_real_triple')
            decision = fn(prev_spin, prev)
            if decision is None:
                continue
            if decision:
                bet_spins += 1
                if i == len(traj) - 1:
                    caught_set.add(gap_idx)

    return caught_set, bet_spins, total_spins


def fmt_metrics(n_caught, bet_spins, total_spins, n_gaps):
    if not bet_spins:
        return f"{n_caught:3d}/{n_gaps:3d}   0.00%      inf    0.0x"
    bet_pct = 100 * bet_spins / total_spins
    mb = bet_spins / n_caught if n_caught else float('inf')
    bhr = n_caught / bet_spins if bet_spins else 0
    br  = n_gaps / total_spins if total_spins else 0
    lift = bhr / br if br else 0
    mb_str = f"{mb:7.1f}" if mb != float('inf') else "    inf"
    return f"{n_caught:3d}/{n_gaps:3d}  {bet_pct:5.2f}%  {mb_str}  {lift:5.1f}x"


def run():
    gaps = all_gaps_with_prev()
    n_gaps = len(gaps)

    out = []
    out.append("=" * 100)
    out.append("CHUNK 12: CAUSAL VALIDATION of the existing 16-rule ensemble")
    out.append("=" * 100)
    out.append(f"Total gaps: {n_gaps} (178 ACC gaps across Islam/Ahmed/Nick)")
    out.append("")
    out.append("Each row compares the rule's NON-CAUSAL score (from chunk 10) against")
    out.append("its CAUSAL score (strategy evaluated on counters at end of prior spin).")
    out.append("")

    # ---- Per-rule before/after ----
    header = f"{'rule':>45s}  {'NC catches':>11s}  {'NC mb/hit':>10s}  {'C catches':>10s}  {'C mb/hit':>10s}  {'C lift':>7s}"
    out.append(header)
    out.append("-" * len(header))

    nc_data = {}
    c_data  = {}
    for name, fn, ref_mb in ens.CONFIGS:
        nc_caught, nc_bets, nc_total = ens.simulate_with_catch_flags(fn, gaps)
        c_caught,  c_bets,  c_total  = simulate_causal(fn, gaps)
        nc_data[name] = {'caught_set': nc_caught, 'bet_spins': nc_bets, 'total_spins': nc_total}
        c_data[name]  = {'caught_set': c_caught,  'bet_spins': c_bets,  'total_spins': c_total}

        nc_n = len(nc_caught)
        c_n  = len(c_caught)
        nc_mb = nc_bets / nc_n if nc_n else float('inf')
        c_mb  = c_bets  / c_n  if c_n  else float('inf')
        c_bhr = c_n / c_bets if c_bets else 0
        c_br  = n_gaps / c_total if c_total else 0
        c_lift = c_bhr / c_br if c_br else 0

        nc_mb_str = f"{nc_mb:8.1f}" if nc_mb != float('inf') else "     inf"
        c_mb_str  = f"{c_mb:8.1f}"  if c_mb  != float('inf') else "     inf"
        out.append(f"{name[:45]:>45s}  {nc_n:5d}/{n_gaps:3d}  {nc_mb_str}  {c_n:4d}/{n_gaps:3d}  {c_mb_str}  {c_lift:6.1f}x")

    # ---- TRUE union under causal ----
    out.append("")
    out.append("--- TRUE causal union (bet if ANY of the 16 rules fires causally) ---")
    union_caught_c = set()
    union_bets_c   = 0
    union_total    = 0
    all_fns = [fn for _, fn, _ in ens.CONFIGS]

    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        union_total += len(traj)

        for i in range(1, len(traj)):
            prev_spin = traj[i - 1]
            prev_spin['_traj_ref'] = traj
            prev_spin['_traj_idx'] = i - 1
            prev_spin['_prev_triple_type'] = gap.get('prev_real_triple')
            any_bet = False
            for fn in all_fns:
                decision = fn(prev_spin, prev)
                if decision:
                    any_bet = True
                    break
            if any_bet:
                union_bets_c += 1
                if i == len(traj) - 1:
                    union_caught_c.add(gap_idx)

    n_u = len(union_caught_c)
    bhr_u = n_u / union_bets_c if union_bets_c else 0
    br_u  = n_gaps / union_total if union_total else 0
    mb_u  = union_bets_c / n_u if n_u else float('inf')
    lift_u = bhr_u / br_u if br_u else 0
    bet_pct_u = 100 * union_bets_c / union_total if union_total else 0
    out.append(f"  Catches  : {n_u}/{n_gaps} ({100*n_u/n_gaps:.1f}%)")
    out.append(f"  Bet spins: {union_bets_c} / {union_total} ({bet_pct_u:.2f}%)")
    out.append(f"  mb/hit   : {mb_u:.1f}")
    out.append(f"  lift     : {lift_u:.1f}x")

    # Per-account
    out.append("")
    out.append("  Per-account causal union:")
    for acct in ACCOUNTS:
        acct_indices = [i for i, g in enumerate(gaps) if g.get('account') == acct]
        acct_caught  = union_caught_c & set(acct_indices)
        out.append(f"    {acct:6s}: {len(acct_caught):3d}/{len(acct_indices):3d} ({100*len(acct_caught)/max(len(acct_indices),1):.0f}%)")

    # ---- Drop summary ----
    out.append("")
    out.append("--- Headline drop (non-causal -> causal) ---")
    nc_union = set()
    for d in nc_data.values():
        nc_union |= d['caught_set']
    out.append(f"  Non-causal union of 16 rules : {len(nc_union)}/{n_gaps} catches  (the old '63/178' figure)")
    out.append(f"  Causal     union of 16 rules : {n_u}/{n_gaps} catches")
    out.append(f"  Phantom catches removed      : {len(nc_union) - n_u}")
    out.append(f"  Survival rate                : {100*n_u/max(len(nc_union),1):.0f}%")

    # ---- Which gaps are STILL catchable causally vs phantom-only ----
    phantom_only = nc_union - union_caught_c
    out.append("")
    out.append(f"--- Gaps that were phantom-only catches (in non-causal union but NOT in causal) ---")
    out.append(f"Count: {len(phantom_only)}")
    for gap_idx in sorted(phantom_only):
        g = gaps[gap_idx]
        out.append(f"  gap {gap_idx:3d}  acct={g['account']:6s}  len={g['length']:3d}  prev={g.get('prev_gap_length')}")

    # ---- Greedy minimum cover under causal eval ----
    out.append("")
    out.append("--- GREEDY MINIMUM COVER (causal) ---")
    target_set = set(union_caught_c)
    remaining = set(target_set)
    chosen = []
    available = list(ens.CONFIGS)
    while remaining:
        best_score = None
        best_idx = -1
        for idx, (name, fn, ref_mb) in enumerate(available):
            d = c_data[name]
            new_catches = d['caught_set'] & remaining
            if not new_catches:
                continue
            score = d['bet_spins'] / len(new_catches)
            if best_score is None or score < best_score:
                best_score = score
                best_idx = idx
        if best_idx < 0:
            break
        name, fn, ref_mb = available.pop(best_idx)
        d = c_data[name]
        new = d['caught_set'] & remaining
        chosen.append((name, len(new)))
        remaining -= d['caught_set']

    out.append(f"  Greedy chosen subset ({len(chosen)} configs):")
    for name, n_new in chosen:
        out.append(f"    + {name}  (+{n_new} new catches)")

    out_path = Path(__file__).parent / '12_causal_validate_results.txt'
    out_path.write_text('\n'.join(out), encoding='utf-8')
    print(f"Saved -> {out_path}")
    print()
    print(f"Headline: non-causal union = {len(nc_union)}/{n_gaps}, causal union = {n_u}/{n_gaps}")
    print(f"Causal mb/hit (full union of 16 rules): {mb_u:.1f}")


if __name__ == '__main__':
    run()
