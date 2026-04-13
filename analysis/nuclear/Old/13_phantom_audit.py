"""
Chunk 13: Phantom catch audit — CRITICAL bug discovery.

The simulator in 10_ensemble.py counts a gap as "caught" when the rule fires
at iteration i == len(traj) - 1 — i.e., at state sa_spins = gap_length,
WHICH INCLUDES the triple itself.

In live play, the user can only act on tile state from BEFORE a spin. For a
real catch at spin L (the triple), the rule must fire at state sa_spins = L-1
(after the PREVIOUS spin), so the tile shows BET NOW when the user decides
the bet for spin L.

"Phantom" catch = rule only fires at sa_spins = L (the triple). The rate
jumped up by 3/L when the triple added its own acc symbols — so the rule
fires, but too late. User was at normal bet.

"Real" catch = rule was firing at sa_spins = L-1 (the penultimate state).
User saw BET NOW, bet high for spin L, triple hit at high bet.

This script re-walks every gap for every rule and classifies each "caught"
gap as REAL or PHANTOM. Then shows what the true catch count is.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('e10', os.path.join(os.path.dirname(__file__), '10_ensemble.py'))
e10 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e10)

import pickle
from pathlib import Path

GAPS_PATH = Path(__file__).parent / 'gaps.pkl'

WANTED_RULES = [
    ("1. COMBO w10 t110 a0.28 p0.20 s0.010",       "COMBO w10 t110 a0.28 p0.20 s0.010"),
    ("2. Ideal RA w8 t110 r0.30 s0.006",           "Ideal RA w8 t110 rate0.30 s0.006"),
    ("3. RA t130 r0.28 s0.010",                    "RA t130 rate0.28 s0.010"),
    ("4. FLAT 150/0.32",                           "FLAT 150/0.32"),
    ("5. SML L>=120 tL=130 g=0.32",                "SML L>=120 tL=130 g=0.32 (L-only)"),
    ("6. SML L>=120 tL=130 g=0.30",                "SML L>=120 tL=130 g=0.30 (L-only)"),
    ("7. SML S100 L120 tM=180 tL=130",             "SML S100 L120 tM=180 tL=130 g=0.32"),
    ("8. SML S100 L120 tM=110 tL=130",             "SML S100 L120 tM=110 tL=130 g=0.32"),
    ("9. SML S100 L130 tM=130 tL=100",             "SML S100 L130 tM=130 tL=100 g=0.32"),
    ("10. SML S50 L130 tM=150 tL=100",             "SML S50  L130 tM=150 tL=100 g=0.32"),
    ("11. SML S50 L130 tS=80 tM=150 tL=100",       "SML S50  L130 tS=80 tM=150 tL=100 g=0.32"),
    ("12. SHIELD-cond 110/0.32",                   "SHIELD-cond 110/0.32"),
    ("13. SHIELD-cond 120/0.32",                   "SHIELD-cond 120/0.32"),
    ("14. SHIELD-cond 130/0.32",                   "SHIELD-cond 130/0.32"),
    ("15. SHIELD-cond 140/0.32",                   "SHIELD-cond 140/0.32"),
    ("16. FLAT 150/0.37",                          "FLAT 150/0.37"),
]


def all_gaps_with_prev():
    with open(GAPS_PATH, 'rb') as f:
        data = pickle.load(f)
    out = []
    for acct in ['Islam', 'Ahmed', 'Nick']:
        raw = data[acct]['gaps'].get('accumulation', [])
        for i, g in enumerate(raw):
            g2 = dict(g)
            g2['prev_gap_length'] = raw[i-1]['length'] if i > 0 else None
            g2['account'] = acct
            out.append(g2)
    return out


def analyze_rule(fn, gaps):
    """
    For each gap where the rule would be considered "caught" by the old simulator:
      - PHANTOM: rule only fires at i = L-1 (state sa_spins = L, includes triple)
      - REAL:    rule fires at i = L-2 AS WELL (state sa_spins = L-1, before triple)
    """
    old_caught = 0  # old-sim catch count (fires at last iteration)
    real_caught = 0 # rule was firing at i = L-2 (penultimate iteration)
    phantom_caught = 0

    real_bets = 0   # bets in real-caught gaps (only counts bets made at sa_spins <= L-1, since the L bet doesn't help)
    phantom_bets = 0

    per_account = {'Islam': {'real': 0, 'phantom': 0},
                   'Ahmed': {'real': 0, 'phantom': 0},
                   'Nick':  {'real': 0, 'phantom': 0}}

    for gap in gaps:
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        L = len(traj)
        if L < 2: continue  # can't catch a 1-spin gap

        # Evaluate rule at each iteration to compute sa_spins at L-1 and L firings
        fires_penult = False  # rule fires at i = L-2
        fires_last   = False  # rule fires at i = L-1 (the triple)
        bet_spins_before_triple = 0

        for i, spin in enumerate(traj):
            spin['_traj_ref'] = traj
            spin['_traj_idx'] = i
            spin['_prev_triple_type'] = gap.get('prev_real_triple')
            fired = fn(spin, prev)

            if i < L - 1 and fired:
                bet_spins_before_triple += 1
            if i == L - 2 and fired:
                fires_penult = True
            if i == L - 1 and fired:
                fires_last = True

        if fires_last:
            old_caught += 1
            if fires_penult:
                # Real catch: user was betting high for the triple spin
                real_caught += 1
                real_bets += bet_spins_before_triple
                per_account[gap['account']]['real'] += 1
            else:
                phantom_caught += 1
                phantom_bets += bet_spins_before_triple
                per_account[gap['account']]['phantom'] += 1

    return {
        'old': old_caught,
        'real': real_caught,
        'phantom': phantom_caught,
        'real_bets_wasted_before_catch': real_bets,
        'phantom_bets_wasted': phantom_bets,
        'per_account': per_account,
    }


def run():
    gaps = all_gaps_with_prev()

    # Map sim names to fns
    name_to_fn = {n: fn for n, fn, _ in e10.CONFIGS}

    lines = []
    lines.append("=" * 110)
    lines.append("CHUNK 13: PHANTOM CATCH AUDIT — Which catches are REAL vs PHANTOM")
    lines.append("=" * 110)
    lines.append("")
    lines.append("PHANTOM = rule fired ONLY at the triple spin (sa_spins = gap_length).")
    lines.append("          In live play, user sees BET NOW after the triple — too late.")
    lines.append("REAL    = rule was firing at sa_spins = gap_length - 1 (the spin BEFORE the triple).")
    lines.append("          User saw BET NOW and bet high for the triple spin — real catch.")
    lines.append("")
    lines.append(f"{'rule':<42s}  {'old-sim':>8s}  {'REAL':>5s}  {'phantom':>7s}  {'phantom %':>9s}  per-account REAL (I/A/N)")
    lines.append("-" * 110)

    total_old = 0
    total_real = 0
    total_phantom = 0

    for display, sim_name in WANTED_RULES:
        fn = name_to_fn.get(sim_name)
        if fn is None:
            continue
        r = analyze_rule(fn, gaps)
        pct = 100 * r['phantom'] / r['old'] if r['old'] else 0
        pa = r['per_account']
        acct_str = f"{pa['Islam']['real']}/{pa['Ahmed']['real']}/{pa['Nick']['real']}"
        lines.append(f"{display:<42s}  {r['old']:>8d}  {r['real']:>5d}  {r['phantom']:>7d}  {pct:>8.1f}%  {acct_str}")
        total_old += r['old']
        total_real += r['real']
        total_phantom += r['phantom']

    lines.append("-" * 110)
    lines.append(f"{'TOTAL (sum across all rules — not dedup)':<42s}  {total_old:>8d}  {total_real:>5d}  {total_phantom:>7d}  {100*total_phantom/max(total_old,1):>8.1f}%")
    lines.append("")

    # Now the critical number: what is the UNION catch count with REAL catches only?
    lines.append("=" * 110)
    lines.append("ENSEMBLE UNION — REAL CATCHES ONLY")
    lines.append("=" * 110)
    lines.append("")
    lines.append("Union of REAL catches across all 16 rules (dedup):")
    lines.append("A gap is REAL-caught by the union iff AT LEAST ONE rule was firing at sa_spins = L-1.")
    lines.append("")

    real_union = set()
    phantom_union = set()  # gaps that ONLY have phantom catches (no real catch from any rule)

    all_fns = [(n, fn) for n, fn, _ in e10.CONFIGS for dn, sn in WANTED_RULES if n == sn]

    for gi, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        L = len(traj)
        if L < 2: continue

        any_real = False
        any_phantom = False

        for name, fn in all_fns:
            fires_penult = False
            fires_last = False
            for i, spin in enumerate(traj):
                spin['_traj_ref'] = traj
                spin['_traj_idx'] = i
                spin['_prev_triple_type'] = gap.get('prev_real_triple')
                if i == L - 2 and fn(spin, prev): fires_penult = True
                if i == L - 1 and fn(spin, prev): fires_last = True
                if i >= L - 1: break
            if fires_last and fires_penult:
                any_real = True
                break
            if fires_last:
                any_phantom = True

        if any_real:
            real_union.add(gi)
        elif any_phantom:
            phantom_union.add(gi)

    total_gaps = len(gaps)
    old_union = 63  # known from earlier analysis
    real_count = len(real_union)
    phantom_only = len(phantom_union)

    lines.append(f"  Old ensemble union (fires at triple spin):     {old_union}/{total_gaps}")
    lines.append(f"  REAL ensemble catches (fires at L-1 AND L):    {real_count}/{total_gaps}")
    lines.append(f"  PHANTOM-ONLY gaps (no rule fired at L-1):      {phantom_only}/{total_gaps}")
    lines.append(f"")

    # Per account for real catches
    real_per_acct = {'Islam': 0, 'Ahmed': 0, 'Nick': 0}
    for gi in real_union:
        real_per_acct[gaps[gi]['account']] += 1
    acct_counts = {a: sum(1 for g in gaps if g['account'] == a) for a in ['Islam','Ahmed','Nick']}
    lines.append(f"  REAL per-account:")
    for a in ['Islam','Ahmed','Nick']:
        lines.append(f"    {a}: {real_per_acct[a]}/{acct_counts[a]} ({100*real_per_acct[a]/acct_counts[a]:.1f}%)")
    lines.append("")

    lines.append("=" * 110)
    lines.append("IMPLICATION")
    lines.append("=" * 110)
    lines.append("")
    lines.append("If the REAL catch count is significantly lower than 63:")
    lines.append("  - The entire analysis (10_ensemble.py, 09_sml_crossval.py, 08_cross_validate.py,")
    lines.append("    03-07 sweeps) has been measuring the wrong thing.")
    lines.append("  - All 'validated' formulas need re-measurement.")
    lines.append("  - The live tracker's behavior is CORRECT (it computes state each spin,")
    lines.append("    user acts on previous state) — but the EXPECTED catch count is wrong.")
    lines.append("  - We need to re-run the entire pipeline with the L-1 fix.")

    out_path = os.path.join(os.path.dirname(__file__), '13_phantom_audit.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Saved -> {out_path}")
    print(f"Old union: 63, REAL: {real_count}, PHANTOM-ONLY: {phantom_only}")


if __name__ == '__main__':
    run()
