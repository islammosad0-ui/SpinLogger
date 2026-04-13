"""
Chunk 6: Leave-one-account-out cross-validation on top ACC and SPN configs.

For each config, evaluate on each account individually. A config that
dominates on one account but fails on others is overfit noise.

Configs tested are the best from chunks 1-5.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('ev', os.path.join(os.path.dirname(__file__), '02_eval.py'))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

import pickle
from pathlib import Path

GAPS_PATH = Path(__file__).parent / 'gaps.pkl'
ACCOUNTS = ['Islam', 'Ahmed', 'Nick']


def load_gaps():
    with open(GAPS_PATH, 'rb') as f:
        return pickle.load(f)


def gaps_by_account(target):
    data = load_gaps()
    out = {}
    for acct in ACCOUNTS:
        out[acct] = data[acct]['gaps'].get(target, [])
    return out


def ordered_gaps_by_account(target):
    """Load gaps with prev_gap info per account."""
    data = load_gaps()
    out = {}
    for acct in ACCOUNTS:
        gaps = data[acct]['gaps'].get(target, [])
        for i, g in enumerate(gaps):
            g['prev_gap_length'] = gaps[i-1]['length'] if i > 0 else None
        out[acct] = gaps
    return out


def run():
    results = []
    results.append("=" * 90)
    results.append("CHUNK 6: CROSS-VALIDATION (leave-one-account-out)")
    results.append("=" * 90)

    acct_gaps = gaps_by_account('accumulation')
    acct_gaps_ordered = ordered_gaps_by_account('accumulation')

    # ======== ACC CONFIGS TO TEST ========
    # Each config is (name, strategy_fn_factory_or_fn, needs_ordered)

    def make_simple(thresh, gate):
        def f(s):
            if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
            return (s['sa_acc'] / s['sa_spins']) >= gate
        return f

    def make_window(thresh, gate, stop):
        def f(s):
            sp = s['sa_spins']
            if sp < thresh or sp > stop or sp == 0: return False
            return (s['sa_acc'] / sp) >= gate
        return f

    def make_double(thresh, acc_gate, spn_gate):
        def f(s):
            sp = s['sa_spins']
            if sp < thresh or sp == 0: return False
            return (s['sa_acc'] / sp) >= acc_gate and (s['sa_spn'] / sp) >= spn_gate
        return f

    def make_bivar_low(thresh, acc_gate, other_col, max_rate):
        def f(s):
            sp = s['sa_spins']
            if sp < thresh or sp == 0: return False
            if (s['sa_acc'] / sp) < acc_gate: return False
            return (s[other_col] / sp) <= max_rate
        return f

    acc_configs = [
        # Baseline
        ("BASELINE 130/0.30", make_simple(130, 0.30)),
        # Gate bump
        ("130/0.32", make_simple(130, 0.32)),
        ("130/0.33", make_simple(130, 0.33)),
        # Window
        ("130-250/0.30", make_window(130, 0.30, 250)),
        ("150-250/0.30", make_window(150, 0.30, 250)),
        # Higher threshold
        ("150/0.32", make_simple(150, 0.32)),
        # Double gate (THE new discovery)
        ("DG 130/acc0.30+spn0.22", make_double(130, 0.30, 0.22)),
        ("DG 130/acc0.30+spn0.25", make_double(130, 0.30, 0.25)),
        ("DG 130/acc0.32+spn0.20", make_double(130, 0.32, 0.20)),
        ("DG 130/acc0.32+spn0.22", make_double(130, 0.32, 0.22)),
        ("DG 120/acc0.32+spn0.22", make_double(120, 0.32, 0.22)),
        ("DG 110/acc0.32+spn0.22", make_double(110, 0.32, 0.22)),
        ("DG 100/acc0.32+spn0.22", make_double(100, 0.32, 0.22)),
        # Bivariate: high acc, low shd
        ("BV 130/acc0.30+shd<=0.23", make_bivar_low(130, 0.30, 'sa_shd', 0.23)),
        ("BV 130/acc0.32+shd<=0.23", make_bivar_low(130, 0.32, 'sa_shd', 0.23)),
        ("BV 130/acc0.32+spn<=0.26", make_bivar_low(130, 0.32, 'sa_spn', 0.26)),
    ]

    # === Evaluate per account and total ===
    results.append(f"\n{'config':>30s}  {'ALL':>25s}  {'Islam':>25s}  {'Ahmed':>25s}  {'Nick':>25s}")
    results.append("-" * 140)

    validated_configs = []

    for name, fn in acc_configs:
        all_gaps = []
        for acct in ACCOUNTS:
            all_gaps.extend(acct_gaps[acct])

        r_all = ev.simulate_fast(fn, all_gaps)
        per_acct = {}
        for acct in ACCOUNTS:
            per_acct[acct] = ev.simulate_fast(fn, acct_gaps[acct])

        def fmt(r):
            if r['caught'] == 0:
                return f"{r['caught']:2d}/{r['total_gaps']:3d}  --  --"
            return f"{r['caught']:2d}/{r['total_gaps']:3d} mb={r['mb_per_hit']:5.1f} {r['lift']:5.1f}x"

        line = f"{name:>30s}  {fmt(r_all):>25s}"
        all_positive = True
        for acct in ACCOUNTS:
            r = per_acct[acct]
            line += f"  {fmt(r):>25s}"
            if r['caught'] == 0 or r['lift'] < 1.0:
                all_positive = False

        # Mark validated (positive lift on ALL accounts)
        if all_positive:
            line += "  *** VALIDATED ***"
            validated_configs.append((name, r_all, per_acct))

        results.append(line)

    # Rate acceleration (special: needs per-spin slope computation)
    results.append("\n--- Rate Acceleration configs ---")
    results.append(f"{'config':>30s}  {'ALL':>25s}  {'Islam':>25s}  {'Ahmed':>25s}  {'Nick':>25s}")

    for win in [10, 20]:
        for thresh in [120, 130]:
            for min_slope1000 in [5, 10]:
                min_slope = min_slope1000 / 1000.0
                name = f"RA w={win} t={thresh} s>={min_slope:.3f}"
                per_acct = {}
                for acct in ACCOUNTS:
                    caught = 0; bet_spins = 0; total_spins = 0
                    for gap in acct_gaps[acct]:
                        traj = gap['trajectory']
                        total_spins += len(traj)
                        for i, spin in enumerate(traj):
                            sp = spin['sa_spins']
                            if sp < thresh or sp == 0: continue
                            rate_now = spin['sa_acc'] / sp
                            if i >= win:
                                sp_prev = traj[i-win]['sa_spins']
                                rate_prev = traj[i-win]['sa_acc'] / sp_prev if sp_prev else 0
                                slope = rate_now - rate_prev
                            else:
                                slope = 0
                            if slope >= min_slope and rate_now >= 0.28:
                                bet_spins += 1
                                if i == len(traj) - 1:
                                    caught += 1
                    tg = len(acct_gaps[acct])
                    bp = bet_spins / total_spins if total_spins else 0
                    br = tg / total_spins if total_spins else 0
                    bhr = caught / bet_spins if bet_spins else 0
                    mb = bet_spins / caught if caught else float('inf')
                    lift = bhr / br if br else 0
                    per_acct[acct] = {'caught': caught, 'total_gaps': tg, 'bet_spins': bet_spins,
                                      'total_spins': total_spins, 'mb_per_hit': mb, 'lift': lift}

                # All combined
                caught_all = sum(per_acct[a]['caught'] for a in ACCOUNTS)
                bet_all = sum(per_acct[a]['bet_spins'] for a in ACCOUNTS)
                ts_all = sum(per_acct[a]['total_spins'] for a in ACCOUNTS)
                tg_all = sum(per_acct[a]['total_gaps'] for a in ACCOUNTS)
                mb_all = bet_all / caught_all if caught_all else float('inf')
                br_all = tg_all / ts_all if ts_all else 0
                bhr_all = caught_all / bet_all if bet_all else 0
                lift_all = bhr_all / br_all if br_all else 0
                r_all = {'caught': caught_all, 'total_gaps': tg_all, 'mb_per_hit': mb_all, 'lift': lift_all}

                def fmt(r):
                    if r['caught'] == 0:
                        return f"{r['caught']:2d}/{r['total_gaps']:3d}  --  --"
                    return f"{r['caught']:2d}/{r['total_gaps']:3d} mb={r['mb_per_hit']:5.1f} {r['lift']:5.1f}x"

                line = f"{name:>30s}  {fmt(r_all):>25s}"
                all_positive = True
                for acct in ACCOUNTS:
                    r = per_acct[acct]
                    line += f"  {fmt(r):>25s}"
                    if r['caught'] == 0 or r['lift'] < 1.0:
                        all_positive = False
                if all_positive:
                    line += "  *** VALIDATED ***"
                    validated_configs.append((name, r_all, per_acct))
                results.append(line)

    # ======== SPN CONFIGS ========
    results.append(f"\n{'='*40} SPN {'='*40}")
    spn_acct_gaps = gaps_by_account('spins')

    def make_spn(thresh, gate):
        def f(s):
            if s['ss_spins'] < thresh or s['ss_spins'] == 0: return False
            return (s['ss_spn'] / s['ss_spins']) >= gate
        return f

    def make_spn_old(thresh, gate):
        def f(s):
            if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
            return (s['sa_spn'] / s['sa_spins']) >= gate
        return f

    spn_configs = [
        ("OLD sa 87/0.25", make_spn_old(87, 0.25)),
        ("OLD sa 87/0.30", make_spn_old(87, 0.30)),
        ("ss 60/0.25", make_spn(60, 0.25)),
        ("ss 80/0.25", make_spn(80, 0.25)),
        ("ss 87/0.25", make_spn(87, 0.25)),
        ("ss 100/0.25", make_spn(100, 0.25)),
        ("ss 120/0.25", make_spn(120, 0.25)),
        ("ss 87/0.30", make_spn(87, 0.30)),
        ("ss 100/0.30", make_spn(100, 0.30)),
        ("ss 120/0.30", make_spn(120, 0.30)),
        ("ss 80/0.28", make_spn(80, 0.28)),
        ("ss 100/0.28", make_spn(100, 0.28)),
    ]

    results.append(f"{'config':>30s}  {'ALL':>25s}  {'Islam':>25s}  {'Ahmed':>25s}  {'Nick':>25s}")
    results.append("-" * 140)

    for name, fn in spn_configs:
        all_gaps = []
        for acct in ACCOUNTS:
            all_gaps.extend(spn_acct_gaps[acct])

        r_all = ev.simulate_fast(fn, all_gaps)
        per_acct = {}
        for acct in ACCOUNTS:
            per_acct[acct] = ev.simulate_fast(fn, spn_acct_gaps[acct])

        def fmt(r):
            if r['caught'] == 0:
                return f"{r['caught']:2d}/{r['total_gaps']:3d}  --  --"
            return f"{r['caught']:2d}/{r['total_gaps']:3d} mb={r['mb_per_hit']:5.1f} {r['lift']:5.1f}x"

        line = f"{name:>30s}  {fmt(r_all):>25s}"
        all_positive = True
        for acct in ACCOUNTS:
            r = per_acct[acct]
            line += f"  {fmt(r):>25s}"
            if r['caught'] == 0 or r['lift'] < 1.0:
                all_positive = False
        if all_positive:
            line += "  *** VALIDATED ***"
            validated_configs.append((name + " [SPN]", r_all, per_acct))
        results.append(line)

    # ======== SUMMARY ========
    results.append(f"\n{'='*90}")
    results.append("VALIDATED CONFIGS (positive lift on ALL 3 accounts)")
    results.append(f"{'='*90}")
    for name, r_all, _ in validated_configs:
        results.append(f"  {name:>35s}  caught={r_all['caught']:3d}/{r_all['total_gaps']:3d}  "
                       f"mb/hit={r_all['mb_per_hit']:6.1f}  lift={r_all['lift']:6.2f}x")

    out_path = os.path.join(os.path.dirname(__file__), '08_crossval_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print(f"Saved -> {out_path}")
    print(f"\n{'='*60}")
    print(f"VALIDATED CONFIGS ({len(validated_configs)} passed)")
    print(f"{'='*60}")
    for name, r_all, per in validated_configs:
        per_str = "  ".join(f"{a}:{per[a]['caught']}/{per[a]['total_gaps']}" for a in ACCOUNTS if a in per)
        print(f"  {name:>35s}  mb/hit={r_all['mb_per_hit']:6.1f}  lift={r_all['lift']:6.2f}x  |  {per_str}")


if __name__ == '__main__':
    run()
