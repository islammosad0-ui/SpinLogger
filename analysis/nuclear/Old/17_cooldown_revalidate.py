"""
Chunk 17: Re-validate the causal ensemble with the 8/3 cooldown rule.

The earlier causal sweeps (chunks 13-15) all assumed every fire-spin = 1
bet, and ignored SLDebtTracker's cooldown:

  kSLDefaultCooldownAfter = 8   # consec bets before forced rest
  kSLDefaultCooldownLen   = 3   # rest length in spins

Effects of applying cooldown:
  - Bet totals shrink (forced REST spins are not bets).
  - Catches can be LOST if the triple-landing spin falls inside REST,
    because rule evaluation is skipped during cooldown.
  - Subsets that catch only via long fire runs are penalised harder than
    subsets that catch with short fire bursts.

This chunk re-runs subsets A-E from chunk 15 and the first-N greedy
subsets, with cooldown applied, so we can pick the real sweet spot.

Cooldown semantics (matching SLDebtTracker.m lines 408-442):
  - Cooldown decrements first; during cooldown no eval, no bet, consec=0
  - On a fire: bet, consec++, if consec >= 8 -> set cooldown = 3
  - On a non-fire: consec = 0 (single skip breaks the streak)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec14 = importlib.util.spec_from_file_location('e14', os.path.join(os.path.dirname(__file__), '14_causal_ensemble.py'))
e14 = importlib.util.module_from_spec(spec14); spec14.loader.exec_module(e14)


COOLDOWN_AFTER = 8
COOLDOWN_LEN   = 3


def simulate_cooldown(rules, gaps, cd_after=COOLDOWN_AFTER, cd_len=COOLDOWN_LEN):
    """
    Causal OR-union simulator with 8/3 cooldown.

    Returns (caught_set, bet_spins, total_spins, lost_to_rest)
    where lost_to_rest is the number of gaps whose triple would have been
    caught (rule fires causally on triple-1) but the cooldown REST blocked
    the evaluation.
    """
    caught = set()
    would_have_caught = set()
    bet_spins = 0
    total_spins = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        triple_type = gap.get('prev_real_triple')
        traj = gap['trajectory']
        total_spins += len(traj)
        consec = 0
        cooldown = 0
        for i in range(1, len(traj)):
            in_rest = cooldown > 0
            # Always check what WOULD have fired (for lost-to-rest stat)
            prev_spin = traj[i - 1]
            prev_spin['_traj_ref'] = traj
            prev_spin['_traj_idx'] = i - 1
            prev_spin['_prev_triple_type'] = triple_type
            would_fire = False
            if i == len(traj) - 1:  # only need this on triple-landing spin
                for fn in rules:
                    if fn(prev_spin, prev):
                        would_fire = True
                        break
                if would_fire:
                    would_have_caught.add(gap_idx)

            if in_rest:
                cooldown -= 1
                consec = 0
                continue  # REST: no eval, no bet

            # Normal evaluation
            fired = would_fire if i == len(traj) - 1 else False
            if i != len(traj) - 1:
                for fn in rules:
                    if fn(prev_spin, prev):
                        fired = True
                        break
            if fired:
                bet_spins += 1
                consec += 1
                if i == len(traj) - 1:
                    caught.add(gap_idx)
                if consec >= cd_after:
                    cooldown = cd_len
            else:
                consec = 0
    lost = would_have_caught - caught
    return caught, bet_spins, total_spins, lost


def fmt(caught, bets, total, n_gaps, lost=None):
    n = len(caught)
    if not bets:
        s = f"{n}/{n_gaps}  bet=0  mb=inf"
    else:
        bet_pct = 100 * bets / total
        mb = bets / n if n else float('inf')
        bhr = n / bets
        br = n_gaps / total
        lift = bhr / br if br else 0
        s = f"{n:3d}/{n_gaps}  bet={bet_pct:4.2f}%  mb/hit={mb:5.1f}  lift={lift:4.2f}x"
    if lost is not None and len(lost) > 0:
        s += f"  lost-to-REST={len(lost)}"
    return s


# === The same rules from chunk 15 ===
GREEDY = [
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

SUBSET_A = [
    ("SML L>=120 t_l=130 g=0.30", e14.sml_fn(0, 120, None, None, 130, 0.30)),
    ("SML L>=120 t_l=130 g=0.28", e14.sml_fn(0, 120, None, None, 130, 0.28)),
    ("SML L>=140 t_l=130 g=0.29", e14.sml_fn(0, 140, None, None, 130, 0.29)),
]
SUBSET_B = SUBSET_A + [
    ("FLAT 130/0.31 stop=160", e14.flat_fn(130, 0.31, 160)),
    ("COND steal t=130 g=0.29", e14.shield_cond_fn(130, 0.29, 'steal')),
]
SUBSET_C = SUBSET_B + [
    ("COND shield t=150 g=0.30", e14.shield_cond_fn(150, 0.30, 'shield')),
    ("SML s=50 l=130 tL=100 g=0.31", e14.sml_fn(50, 130, None, None, 100, 0.31)),
]
SUBSET_D = SUBSET_C + [
    ("FLAT 115/0.34", e14.flat_fn(115, 0.34)),
]
SUBSET_E = SUBSET_D + [
    ("FLAT 130/0.30", e14.flat_fn(130, 0.30)),
]


def run():
    gaps = e14.all_gaps_with_prev()
    n_gaps = len(gaps)

    out = []
    out.append("=" * 100)
    out.append("CHUNK 17: COOLDOWN-AWARE RE-VALIDATION (8/3 rule applied)")
    out.append("=" * 100)
    out.append(f"Total gaps: {n_gaps}")
    out.append(f"Cooldown: {COOLDOWN_AFTER} consec bets -> {COOLDOWN_LEN} REST spins")
    out.append("")

    out.append("--- First-N greedy subsets WITH cooldown ---")
    out.append(f"{'N':>3s}  {'last rule added':>40s}  {'metrics':>50s}")
    for n in range(1, len(GREEDY) + 1):
        rules = [fn for _, fn in GREEDY[:n]]
        cs, bs, ts, lost = simulate_cooldown(rules, gaps)
        last = GREEDY[n-1][0]
        out.append(f"{n:>3d}  {last[:40]:>40s}  {fmt(cs, bs, ts, n_gaps, lost):>50s}")

    out.append("")
    out.append("--- Hand-curated lean subsets WITH cooldown ---")
    for label, subset in [('A', SUBSET_A), ('B', SUBSET_B), ('C', SUBSET_C),
                          ('D', SUBSET_D), ('E', SUBSET_E)]:
        rules = [fn for _, fn in subset]
        cs, bs, ts, lost = simulate_cooldown(rules, gaps)
        out.append(f"  {label}: {len(subset)} rules  ->  {fmt(cs, bs, ts, n_gaps, lost)}")

    out.append("")
    out.append("--- Direct comparison: NO cooldown vs WITH cooldown for Subset C ---")
    rules = [fn for _, fn in SUBSET_C]
    # Re-import the no-cooldown simulator from chunk 15-style
    cs0, bs0, ts0 = _simulate_no_cooldown(rules, gaps)
    cs1, bs1, ts1, lost1 = simulate_cooldown(rules, gaps)
    out.append(f"  NO  cooldown: {fmt(cs0, bs0, ts0, n_gaps)}")
    out.append(f"  8/3 cooldown: {fmt(cs1, bs1, ts1, n_gaps, lost1)}")
    out.append(f"  Delta: catches {len(cs0)}->{len(cs1)} ({len(cs0)-len(cs1)} lost), "
               f"bets {bs0}->{bs1} ({bs0-bs1} saved, -{100*(bs0-bs1)/bs0:.1f}%)")

    out.append("")
    out.append("--- Per-account breakdown for Subset C WITH cooldown ---")
    for acct in e14.ACCOUNTS:
        acct_gaps = [g for g in gaps if g.get('account') == acct]
        cs, bs, ts, lost = simulate_cooldown(rules, acct_gaps)
        out.append(f"  {acct:6s}: {fmt(cs, bs, ts, len(acct_gaps), lost)}")

    out_path = os.path.join(os.path.dirname(__file__), '17_cooldown_revalidate_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f"Saved -> {out_path}")
    print()
    for line in out:
        print(line)


def _simulate_no_cooldown(rules, gaps):
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
                if fn(prev_spin, prev):
                    bets += 1
                    if i == len(traj) - 1:
                        caught.add(gap_idx)
                    break
    return caught, bets, total


if __name__ == '__main__':
    run()
