"""
Chunk 3: S/M/L mega sweep.

Gap-size-conditioned thresholds:
  - Classify the PREVIOUS gap as S(short), M(medium), L(long)
  - Use a different spin threshold for each bucket
  - Sweep ALL boundary definitions, ALL per-bucket thresholds, ALL rate gates

Dimensions:
  - S boundary: prev_gap < X for X in [50,60,70,80,90,100]
  - L boundary: prev_gap >= Y for Y in [100,110,120,130,140,150,160,170]
  - M = between S and L
  - Per-bucket threshold: each in [40,60,80,100,110,120,130,140,150,160,170,180]
  - Rate gate: [0.26,0.28,0.30,0.32,0.34]
  - Also: SKIP option (don't bet at all if prev gap was S — save MB)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('ev', os.path.join(os.path.dirname(__file__), '02_eval.py'))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

import pickle
from pathlib import Path

GAPS_PATH = Path(__file__).parent / 'gaps.pkl'


def load_ordered_gaps(target):
    """Load gaps in account-order with previous gap info."""
    with open(GAPS_PATH, 'rb') as f:
        data = pickle.load(f)
    out = []
    for acct, d in data.items():
        gaps = d['gaps'].get(target, [])
        for i, g in enumerate(gaps):
            prev_len = gaps[i-1]['length'] if i > 0 else None
            out.append({**g, 'prev_gap_length': prev_len, 'account': acct})
    return out


def run():
    results = []
    results.append("=" * 80)
    results.append("CHUNK 3: S/M/L MEGA SWEEP")
    results.append("=" * 80)

    acc_gaps = load_ordered_gaps('accumulation')
    # Filter: only gaps where we know prev gap
    acc_with_prev = [g for g in acc_gaps if g['prev_gap_length'] is not None]
    results.append(f"ACC gaps with known prev: {len(acc_with_prev)} / {len(acc_gaps)}")

    # Baseline for comparison
    def baseline(s):
        if s['sa_spins'] < 130 or s['sa_spins'] == 0: return False
        return (s['sa_acc'] / s['sa_spins']) >= 0.30
    r_base = ev.simulate_fast(baseline, acc_with_prev)
    results.append(f"Baseline (130/0.30) on gaps-with-prev: {ev.fmt_result(r_base)}")

    # =========== PART A: Flat strategies for comparison ===========
    results.append("\n--- Part A: Flat configs on gaps-with-prev (for fair comparison) ---")
    flat_configs = []
    for t in range(60, 200, 10):
        for g100 in range(26, 36, 2):
            gate = g100 / 100.0
            def make(thresh, g):
                def f(s):
                    if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
                    return (s['sa_acc'] / s['sa_spins']) >= g
                return f
            r = ev.simulate_fast(make(t, gate), acc_with_prev)
            if r['caught'] >= 5:
                flat_configs.append((f"flat_{t}/{gate:.2f}", t, gate, r))
    flat_configs.sort(key=lambda x: -x[3]['lift'])
    results.append(f"{'config':>20s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for name, _, _, r in flat_configs[:20]:
        results.append(f"{name:>20s}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # =========== PART B: S/M/L sweep ===========
    results.append(f"\n--- Part B: S/M/L sweep (boundaries x thresholds x gate) ---")

    S_BOUNDS = [50, 60, 70, 80, 90, 100]
    L_BOUNDS = [100, 110, 120, 130, 140, 150, 160, 170]
    THRESHOLDS = [40, 60, 80, 100, 110, 120, 130, 140, 150, 160, 180]
    GATES = [0.26, 0.28, 0.30, 0.32, 0.34]
    SKIP_SENTINEL = 99999  # "SKIP this gap" = threshold so high it never triggers

    # For speed: precompute per-spin decisions won't work easily because
    # the threshold depends on the PREVIOUS gap. So we need to walk gap by gap.
    # That's fine — we just simulate per gap with the right threshold applied.

    def simulate_sml(gaps, s_bound, l_bound, t_s, t_m, t_l, gate):
        """Simulate SML strategy. t_X = SKIP_SENTINEL means skip that bucket."""
        caught = 0
        bet_spins = 0
        total_spins = 0
        total_gaps = len(gaps)

        for gap in gaps:
            traj = gap['trajectory']
            total_spins += len(traj)
            prev = gap['prev_gap_length']
            if prev is None:
                continue  # can't classify — skip

            # Classify previous gap
            if prev < s_bound:
                thresh = t_s
            elif prev >= l_bound:
                thresh = t_l
            else:
                thresh = t_m

            if thresh == SKIP_SENTINEL:
                continue  # skip this gap entirely

            for i, spin in enumerate(traj):
                sp = spin['sa_spins']
                if sp >= thresh and sp > 0 and (spin['sa_acc'] / sp) >= gate:
                    bet_spins += 1
                    if i == len(traj) - 1:
                        caught += 1

        bet_pct = (bet_spins / total_spins) if total_spins else 0.0
        base_rate = (total_gaps / total_spins) if total_spins else 0.0
        bet_hit_rate = (caught / bet_spins) if bet_spins else 0.0
        mb_per_hit = (bet_spins / caught) if caught else float('inf')
        lift = (bet_hit_rate / base_rate) if base_rate > 0 else 0.0
        return {
            'caught': caught, 'total_gaps': total_gaps,
            'bet_spins': bet_spins, 'total_spins': total_spins,
            'bet_pct': bet_pct, 'mb_per_hit': mb_per_hit, 'lift': lift,
        }

    # Run mega sweep
    sml_results = []
    count = 0
    for s_b in S_BOUNDS:
        for l_b in L_BOUNDS:
            if l_b <= s_b:
                continue  # L must be > S
            for gate in GATES:
                # For S bucket: try thresholds + SKIP
                for t_s in THRESHOLDS + [SKIP_SENTINEL]:
                    for t_m in THRESHOLDS:
                        for t_l in THRESHOLDS:
                            count += 1
                            r = simulate_sml(acc_with_prev, s_b, l_b, t_s, t_m, t_l, gate)
                            if r['caught'] >= 5:
                                sml_results.append((s_b, l_b, t_s, t_m, t_l, gate, r))

    results.append(f"Total configs evaluated: {count:,}")
    results.append(f"Configs with >= 5 catches: {len(sml_results):,}")

    # Sort by lift
    sml_results.sort(key=lambda x: -x[6]['lift'])
    results.append(f"\n--- Top 80 by lift ---")
    results.append(f"{'S<':>4s} {'L>=':>4s} {'t_S':>6s} {'t_M':>6s} {'t_L':>6s} {'gate':>5s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for s_b, l_b, t_s, t_m, t_l, gate, r in sml_results[:80]:
        ts_str = 'SKIP' if t_s == SKIP_SENTINEL else str(t_s)
        results.append(f"{s_b:4d} {l_b:4d} {ts_str:>6s} {t_m:6d} {t_l:6d} {gate:5.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # Sort by mb_per_hit (efficiency) among those with >= 10 catches
    good = [x for x in sml_results if x[6]['caught'] >= 10]
    good.sort(key=lambda x: x[6]['mb_per_hit'])
    results.append(f"\n--- Top 50 by mb/hit (min 10 catches) ---")
    results.append(f"{'S<':>4s} {'L>=':>4s} {'t_S':>6s} {'t_M':>6s} {'t_L':>6s} {'gate':>5s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for s_b, l_b, t_s, t_m, t_l, gate, r in good[:50]:
        ts_str = 'SKIP' if t_s == SKIP_SENTINEL else str(t_s)
        results.append(f"{s_b:4d} {l_b:4d} {ts_str:>6s} {t_m:6d} {t_l:6d} {gate:5.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # Best at each catch level (Pareto frontier)
    results.append(f"\n--- Pareto frontier: best mb/hit at each catch level ---")
    results.append(f"{'S<':>4s} {'L>=':>4s} {'t_S':>6s} {'t_M':>6s} {'t_L':>6s} {'gate':>5s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    from collections import defaultdict
    by_catch = defaultdict(list)
    for item in sml_results:
        by_catch[item[6]['caught']].append(item)
    for c in sorted(by_catch.keys()):
        best = min(by_catch[c], key=lambda x: x[6]['mb_per_hit'])
        s_b, l_b, t_s, t_m, t_l, gate, r = best
        ts_str = 'SKIP' if t_s == SKIP_SENTINEL else str(t_s)
        results.append(f"{s_b:4d} {l_b:4d} {ts_str:>6s} {t_m:6d} {t_l:6d} {gate:5.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    out_path = os.path.join(os.path.dirname(__file__), '05_sml_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print(f"Saved -> {out_path}")
    print(f"Total configs: {count:,}")
    print(f"With >= 5 catches: {len(sml_results):,}")
    if sml_results:
        best = sml_results[0]
        ts_str = 'SKIP' if best[2] == SKIP_SENTINEL else str(best[2])
        print(f"Best lift: S<{best[0]} L>={best[1]} t_S={ts_str} t_M={best[3]} t_L={best[4]} gate={best[5]:.2f}")
        print(f"  -> {ev.fmt_result(best[6])}")
    if good:
        best_eff = good[0]
        ts_str = 'SKIP' if best_eff[2] == SKIP_SENTINEL else str(best_eff[2])
        print(f"Best mb/hit (min 10): S<{best_eff[0]} L>={best_eff[1]} t_S={ts_str} t_M={best_eff[3]} t_L={best_eff[4]} gate={best_eff[5]:.2f}")
        print(f"  -> {ev.fmt_result(best_eff[6])}")


if __name__ == '__main__':
    run()
