"""
Chunk 9: Cross-validate top SML configs on all 3 accounts.

SML = S/M/L stratification by previous gap length.
- S bucket: prev_gap < S_bound
- M bucket: S_bound <= prev_gap < L_bound
- L bucket: prev_gap >= L_bound
- Each bucket has its own spin threshold (t_S, t_M, t_L)
- Shared rate gate across all buckets

Gaps without a known prev_gap are excluded (first gap per account).
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


def gaps_by_account_with_prev(target):
    data = load_gaps()
    out = {}
    for acct in ACCOUNTS:
        raw = data[acct]['gaps'].get(target, [])
        gaps_with_prev = []
        for i, g in enumerate(raw):
            g2 = dict(g)
            g2['prev_gap_length'] = raw[i-1]['length'] if i > 0 else None
            gaps_with_prev.append(g2)
        out[acct] = gaps_with_prev
    return out


def make_sml_fn(s_bound, l_bound, t_s, t_m, t_l, gate):
    """Returns a decision function that uses prev_gap to pick the threshold."""
    def f(spin_state, prev_gap_length):
        if prev_gap_length is None:
            return None  # unknown bucket — skip
        if prev_gap_length < s_bound:
            thresh = t_s
        elif prev_gap_length < l_bound:
            thresh = t_m
        else:
            thresh = t_l

        if thresh is None:
            return False  # SKIP bucket

        sp = spin_state['sa_spins']
        if sp < thresh or sp == 0:
            return False
        return (spin_state['sa_acc'] / sp) >= gate
    return f


def simulate_sml(fn, gaps):
    """Like simulate_fast but passes prev_gap to the decision function."""
    caught = 0
    bet_spins = 0
    total_spins = 0
    for gap in gaps:
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        total_spins += len(traj)
        for i, spin in enumerate(traj):
            decision = fn(spin, prev)
            if decision is None:
                continue  # skip unknown bucket entirely
            if decision:
                bet_spins += 1
                if i == len(traj) - 1:
                    caught += 1

    total_gaps = len(gaps)
    # For gaps where prev is unknown, we skip them — adjust total_gaps
    known_gaps = [g for g in gaps if g.get('prev_gap_length') is not None]
    total_gaps = len(known_gaps)

    if bet_spins == 0:
        return {'caught': caught, 'total_gaps': total_gaps, 'bet_spins': bet_spins,
                'total_spins': total_spins, 'mb_per_hit': float('inf'), 'lift': 0.0}

    bhr = caught / bet_spins
    # Base rate uses known gaps only
    total_spins_known = sum(len(g['trajectory']) for g in known_gaps)
    br = total_gaps / total_spins_known if total_spins_known else 0
    mb = bet_spins / caught if caught else float('inf')
    lift = bhr / br if br else 0
    return {'caught': caught, 'total_gaps': total_gaps, 'bet_spins': bet_spins,
            'total_spins': total_spins_known, 'mb_per_hit': mb, 'lift': lift}


def run():
    acct_gaps = gaps_by_account_with_prev('accumulation')

    results = []
    results.append("=" * 110)
    results.append("CHUNK 9: SML CROSS-VALIDATION (per-account breakdown)")
    results.append("=" * 110)

    # Show prev_gap distribution per account
    results.append("\n--- Prev-gap distribution by account ---")
    for acct in ACCOUNTS:
        gaps = acct_gaps[acct]
        known = [g['prev_gap_length'] for g in gaps if g['prev_gap_length'] is not None]
        if not known:
            results.append(f"  {acct}: no known prev gaps")
            continue
        import statistics
        lt80  = sum(1 for x in known if x < 80)
        lt100 = sum(1 for x in known if 80 <= x < 100)
        lt120 = sum(1 for x in known if 100 <= x < 120)
        ge120 = sum(1 for x in known if x >= 120)
        ge130 = sum(1 for x in known if x >= 130)
        results.append(f"  {acct}: n={len(known)}  <80:{lt80}  80-100:{lt100}  100-120:{lt120}"
                       f"  >=120:{ge120}  >=130:{ge130}  mean={statistics.mean(known):.1f}")

    # Collect all known-prev gaps
    all_known = []
    for acct in ACCOUNTS:
        all_known.extend(g for g in acct_gaps[acct] if g.get('prev_gap_length') is not None)

    results.append(f"\n  Total with known prev: {len(all_known)} / {sum(len(acct_gaps[a]) for a in ACCOUNTS)}")

    # =================== SML CONFIGS TO TEST ===================
    # Format: (name, s_bound, l_bound, t_s, t_m, t_l, gate)
    # None = SKIP that bucket
    SKIP = None

    sml_configs = [
        # --- Reference: flat configs ---
        ("FLAT 130/0.30 [baseline]",    None, None, 130, 130, 130, 0.30),
        ("FLAT 150/0.32",               None, None, 150, 150, 150, 0.32),
        ("FLAT 130/0.32",               None, None, 130, 130, 130, 0.32),
        # --- Top from Pareto by mb/hit ---
        # Best lift (5 catches): S<50 L>=130 t_S=100 t_M=160 t_L=100 gate=0.34
        ("SML S50 L130 tS=100 tM=160 tL=100 g=0.34", 50, 130, 100, 160, 100, 0.34),
        # Best mb/hit (10 catches): S<90 L>=120 t_S=150 t_M=180 t_L=130 gate=0.32
        ("SML S90 L120 tS=150 tM=180 tL=130 g=0.32", 90, 120, 150, 180, 130, 0.32),
        # 12 catches 3.8mb: S<100 L>=120 tM=180 tL=130 gate=0.32
        ("SML S100 L120 tS=150 tM=180 tL=130 g=0.32",100, 120, 150, 180, 130, 0.32),
        # 13 catches 4.8mb: S<100 L>=120 tM=110 tL=130 gate=0.32
        ("SML S100 L120 tS=150 tM=110 tL=130 g=0.32",100, 120, 150, 110, 130, 0.32),
        # 12 catches 4.9mb: S<100 L>=120 tM=150 tL=130 gate=0.32
        ("SML S100 L120 tS=150 tM=150 tL=130 g=0.32",100, 120, 150, 150, 130, 0.32),
        # L-only approach: skip S and M, only bet L bucket
        ("SML L-only L>=120 tL=130 g=0.32 [skip S,M]", 1, 120, SKIP, SKIP, 130, 0.32),
        ("SML L-only L>=120 tL=120 g=0.32 [skip S,M]", 1, 120, SKIP, SKIP, 120, 0.32),
        ("SML L-only L>=130 tL=130 g=0.32 [skip S,M]", 1, 130, SKIP, SKIP, 130, 0.32),
        ("SML L-only L>=120 tL=130 g=0.30 [skip S,M]", 1, 120, SKIP, SKIP, 130, 0.30),
        # 14 catches 6.0mb: S<100 L>=170 tL=100 tM=130 gate=0.32
        ("SML S100 L170 tS=150 tM=130 tL=100 g=0.32",100, 170, 150, 130, 100, 0.32),
        # 15-16 catches good mb/hit
        ("SML S100 L150 tS=150 tM=130 tL=100 g=0.32",100, 150, 150, 130, 100, 0.32),
        ("SML S100 L130 tS=150 tM=130 tL=100 g=0.32",100, 130, 150, 130, 100, 0.32),
        # 17-21 catches: higher catch rate options
        ("SML S50 L130 tS=100 tM=150 tL=100 g=0.32",  50, 130, 100, 150, 100, 0.32),
        ("SML S50 L130 tS=100 tM=130 tL=100 g=0.32",  50, 130, 100, 130, 100, 0.32),  # 21 catches, 10.0 mb
        ("SML S50 L130 tS=80  tM=150 tL=100 g=0.32",  50, 130,  80, 150, 100, 0.32),  # 19 catches
        # --- Hybrid: combine L-bucket with M as fallback ---
        ("SML S50 L120 tS=SKIP tM=150 tL=130 g=0.32", 50, 120, SKIP, 150, 130, 0.32),
        ("SML S50 L120 tS=SKIP tM=SKIP tL=130 g=0.32", 50, 120, SKIP, SKIP, 130, 0.32),
        # Nick-specific idea: Nick has mean gap 129.9 — his L bucket is large
        ("SML L-only L>=100 tL=130 g=0.32 [skip S,M]", 1, 100, SKIP, SKIP, 130, 0.32),
    ]

    # For flat configs, we use the standard simulate_fast
    def make_flat_fn(thresh, gate):
        def f(s):
            sp = s['sa_spins']
            if sp < thresh or sp == 0: return False
            return (s['sa_acc'] / sp) >= gate
        return f

    results.append(f"\n{'config':>45s}  {'ALL':>28s}  {'Islam':>22s}  {'Ahmed':>22s}  {'Nick':>22s}")
    results.append("-" * 150)

    validated = []

    for cfg in sml_configs:
        name = cfg[0]
        is_flat = cfg[1] is None

        if is_flat:
            thresh = cfg[3]  # t_S = t_M = t_L for flat configs
            gate = cfg[6]
            fn = make_flat_fn(thresh, gate)
            all_gaps_flat = [g for acct in ACCOUNTS for g in acct_gaps[acct]]
            r_all = ev.simulate_fast(fn, all_gaps_flat)
            per_acct = {a: ev.simulate_fast(fn, acct_gaps[a]) for a in ACCOUNTS}
        else:
            s_bound, l_bound, t_s, t_m, t_l, gate = cfg[1], cfg[2], cfg[3], cfg[4], cfg[5], cfg[6]
            fn = make_sml_fn(s_bound, l_bound, t_s, t_m, t_l, gate)
            r_all = simulate_sml(fn, all_known)
            per_acct = {}
            for acct in ACCOUNTS:
                known_for_acct = [g for g in acct_gaps[acct] if g.get('prev_gap_length') is not None]
                per_acct[acct] = simulate_sml(fn, known_for_acct)

        def fmt(r):
            if r['caught'] == 0:
                return f"{r['caught']:2d}/{r['total_gaps']:3d}  --  --"
            return f"{r['caught']:2d}/{r['total_gaps']:3d} mb={r['mb_per_hit']:5.1f} {r['lift']:5.1f}x"

        line = f"{name:>45s}  {fmt(r_all):>28s}"
        all_positive = True
        for acct in ACCOUNTS:
            r = per_acct[acct]
            line += f"  {fmt(r):>22s}"
            if r['caught'] == 0 or r['lift'] < 1.0:
                all_positive = False

        if all_positive:
            line += "  *** VALIDATED ***"
            validated.append((name, r_all, per_acct))

        results.append(line)

    # =================== ACCOUNT PROFILE SECTION ===================
    # For each account, find the single best flat config
    results.append(f"\n{'='*60}")
    results.append("PER-ACCOUNT BEST FLAT CONFIG (for per-profile idea)")
    results.append(f"{'='*60}")

    flat_sweeps = []
    for t in [100, 110, 120, 130, 140, 150]:
        for g in [0.28, 0.30, 0.32, 0.34]:
            flat_sweeps.append((t, g))

    for acct in ACCOUNTS:
        gaps = acct_gaps[acct]
        best = None
        for t, g in flat_sweeps:
            fn = make_flat_fn(t, g)
            r = ev.simulate_fast(fn, gaps)
            if r['caught'] < 3: continue
            score = r['mb_per_hit']  # lower is better
            if best is None or score < best[0]:
                best = (score, t, g, r)
        if best:
            score, t, g, r = best
            results.append(f"  {acct}: thresh={t} gate={g:.2f}  caught={r['caught']}/{r['total_gaps']}"
                           f"  mb={r['mb_per_hit']:.1f}  lift={r['lift']:.2f}x")

    # =================== PER-ACCOUNT BEST SML ===================
    results.append(f"\n{'='*60}")
    results.append("PER-ACCOUNT BEST SML CONFIG")
    results.append(f"{'='*60}")

    sml_sweep = []
    for s_b in [50, 70, 90, 100]:
        for l_b in [100, 110, 120, 130]:
            for t_l in [100, 110, 120, 130]:
                for g in [0.30, 0.32]:
                    sml_sweep.append((s_b, l_b, SKIP, SKIP, t_l, g))  # L-only

    for acct in ACCOUNTS:
        known_gaps = [g for g in acct_gaps[acct] if g.get('prev_gap_length') is not None]
        best = None
        for cfg in sml_sweep:
            s_b, l_b, t_s, t_m, t_l, g = cfg
            fn = make_sml_fn(s_b, l_b, t_s, t_m, t_l, g)
            r = simulate_sml(fn, known_gaps)
            if r['caught'] < 3: continue
            if best is None or r['mb_per_hit'] < best[0]:
                best = (r['mb_per_hit'], s_b, l_b, t_l, g, r)
        if best:
            mb, s_b, l_b, t_l, g, r = best
            results.append(f"  {acct}: L-only L>={l_b} tL={t_l} gate={g:.2f}  "
                           f"caught={r['caught']}/{r['total_gaps']}  mb={mb:.1f}  lift={r['lift']:.2f}x")

    # =================== VALIDATED SUMMARY ===================
    results.append(f"\n{'='*110}")
    results.append(f"VALIDATED SML CONFIGS ({len(validated)} passed all 3 accounts)")
    results.append(f"{'='*110}")
    for name, r_all, per in validated:
        per_str = "  ".join(f"{a}:{per[a]['caught']}/{per[a]['total_gaps']}" for a in ACCOUNTS)
        results.append(f"  {name:>45s}  mb={r_all['mb_per_hit']:5.1f}  lift={r_all['lift']:5.2f}x  |  {per_str}")

    out_path = os.path.join(os.path.dirname(__file__), '09_sml_crossval_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print(f"Saved -> {out_path}")

    print(f"\nVALIDATED ({len(validated)}):")
    for name, r_all, per in validated:
        per_str = "  ".join(f"{a}:{per[a]['caught']}/{per[a]['total_gaps']}" for a in ACCOUNTS)
        print(f"  {name:>45s}  mb={r_all['mb_per_hit']:5.1f}  lift={r_all['lift']:5.2f}x  |  {per_str}")


if __name__ == '__main__':
    run()
