"""
Chunk 16: Per-gap detail for the NEW causal 7-rule ensemble (Subset C),
          WITH 8/3 cooldown applied.

For every ACC gap, show:
  - gap index, account, length, prev_gap
  - whether the new ensemble CAUGHT it (rule fired on triple-1, NOT in REST)
  - which rules fired anywhere in the gap (high-bet spins only — REST excluded)
  - the FIRST and LAST spin where any rule fired (warning window)
  - REST periods within the gap
  - a snapshot of the counters at the firing moment

The firing-spin convention is causal:
  rule(traj[i-1])  -> bet appears on spin i

So if "fire@spin=110" the user saw the BET indicator on spin 110 (decision
made at end of spin 109). If the gap length is 111, that's a 1-spin warning
into the triple = exactly what the user wants.

Cooldown semantics (matching SLDebtTracker.m lines 408-442):
  - Cooldown decrements first; during cooldown no eval, no bet, consec=0
  - On a fire: bet, consec++, if consec >= 8 -> set cooldown = 3
  - On a non-fire: consec = 0 (single skip breaks the streak)
  - If the triple-landing spin falls inside REST, the catch is LOST
"""

COOLDOWN_AFTER = 8
COOLDOWN_LEN   = 3
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util

spec14 = importlib.util.spec_from_file_location('e14', os.path.join(os.path.dirname(__file__), '14_causal_ensemble.py'))
e14 = importlib.util.module_from_spec(spec14); spec14.loader.exec_module(e14)


# === Subset C: the 7 rules ===
RULES = [
    ("SML L>=120 t_l=130 g=0.30", e14.sml_fn(0, 120, None, None, 130, 0.30)),
    ("SML L>=120 t_l=130 g=0.28", e14.sml_fn(0, 120, None, None, 130, 0.28)),
    ("SML L>=140 t_l=130 g=0.29", e14.sml_fn(0, 140, None, None, 130, 0.29)),
    ("FLAT 130/0.31 stop=160",    e14.flat_fn(130, 0.31, 160)),
    ("COND steal t=130 g=0.29",   e14.shield_cond_fn(130, 0.29, 'steal')),
    ("COND shield t=150 g=0.30",  e14.shield_cond_fn(150, 0.30, 'shield')),
    ("SML s=50 l=130 tL=100 g=0.31", e14.sml_fn(50, 130, None, None, 100, 0.31)),
]
SHORT = {
    "SML L>=120 t_l=130 g=0.30": "L120/.30",
    "SML L>=120 t_l=130 g=0.28": "L120/.28",
    "SML L>=140 t_l=130 g=0.29": "L140/.29",
    "FLAT 130/0.31 stop=160":    "F130/.31",
    "COND steal t=130 g=0.29":   "Cstl",
    "COND shield t=150 g=0.30":  "Cshd",
    "SML s=50 l=130 tL=100 g=0.31": "Llo100",
}


def gap_causal_detail(gap):
    """
    Run all 7 rules causally over the gap WITH 8/3 cooldown applied. Return:
      events: list of (spin_idx, kind, rule_name_or_None, snapshot_dict) where
              kind is one of: 'BET', 'REST', 'WOULD-FIRE-BUT-REST'
              spin_idx is the index of the spin the user is ABOUT to press
              (i.e. counters from spin_idx - 1 made the decision).
      caught_rule: name of the rule that fired on the triple, or None.
                   If the triple landed in REST, this is None even though
                   a rule "would have" fired — the catch is lost.
    """
    prev = gap.get('prev_gap_length')
    triple_type = gap.get('prev_real_triple')
    traj = gap['trajectory']
    events = []
    caught_rule = None
    consec = 0
    cooldown = 0
    for i in range(1, len(traj)):
        prev_spin = traj[i - 1]
        prev_spin['_traj_ref'] = traj
        prev_spin['_traj_idx'] = i - 1
        prev_spin['_prev_triple_type'] = triple_type
        snap = {
            'sa_spins': prev_spin.get('sa_spins'),
            'sa_acc':   prev_spin.get('sa_acc'),
            'sa_spn':   prev_spin.get('sa_spn'),
            'rate':     (prev_spin['sa_acc'] / prev_spin['sa_spins'])
                        if prev_spin.get('sa_spins') else 0.0,
        }
        if cooldown > 0:
            # Check what WOULD have fired, just to annotate
            would = None
            for name, fn in RULES:
                if fn(prev_spin, prev):
                    would = name
                    break
            kind = 'WOULD-FIRE-BUT-REST' if would else 'REST'
            events.append((i, kind, would, snap))
            cooldown -= 1
            consec = 0
            continue
        # Normal evaluation
        fired = None
        for name, fn in RULES:
            if fn(prev_spin, prev):
                fired = name
                break
        if fired:
            events.append((i, 'BET', fired, snap))
            consec += 1
            if i == len(traj) - 1:
                caught_rule = fired
            if consec >= COOLDOWN_AFTER:
                cooldown = COOLDOWN_LEN
        else:
            consec = 0
    return events, caught_rule


def run():
    gaps = e14.all_gaps_with_prev()
    n_gaps = len(gaps)

    lines = []
    lines.append("=" * 140)
    lines.append("CHUNK 16: PER-GAP DETAIL — NEW CAUSAL 7-RULE ENSEMBLE (Subset C) + 8/3 COOLDOWN")
    lines.append("=" * 140)
    lines.append(f"Total ACC gaps: {n_gaps}")
    lines.append("")
    lines.append("Rules (7):")
    for name, _ in RULES:
        lines.append(f"  - {name}    [{SHORT[name]}]")
    lines.append("")
    lines.append("Cooldown: 8 consecutive bets -> 3 spins of forced REST (no eval, no bet).")
    lines.append("Convention: causal — rule(traj[i-1]) fires the BET on spin i.")
    lines.append("  BET@N         = high-bet spin (rule fired AND not in cooldown).")
    lines.append("  REST          = forced rest, no eval.")
    lines.append("  WOULD-FIRE-BUT-REST = rule WOULD have fired but was blocked by REST.")
    lines.append("  caught? YES   = a rule fired exactly on the triple-landing spin (1-spin warning).")
    lines.append("  caught? lost  = the triple landed in REST (catch was blocked by cooldown).")
    lines.append("")

    # ----- compute per-gap data -----
    rows = []
    for gap_idx, gap in enumerate(gaps):
        events, caught_rule = gap_causal_detail(gap)
        bets = [e for e in events if e[1] == 'BET']
        rests = [e for e in events if e[1] in ('REST', 'WOULD-FIRE-BUT-REST')]
        # "lost-to-REST" = triple-landing decision spin would have fired but was in REST
        # The triple-landing decision happens at i = len(traj) - 1 in the loop.
        catch_decision_spin = len(gap['trajectory']) - 1
        lost_to_rest = False
        for spin_i, kind, rule, _ in events:
            if spin_i == catch_decision_spin and kind == 'WOULD-FIRE-BUT-REST':
                lost_to_rest = True
        rows.append({
            'idx': gap_idx,
            'account': gap.get('account'),
            'length': gap['length'],
            'prev_gap': gap.get('prev_gap_length'),
            'prev_triple': gap.get('prev_real_triple'),
            'events': events,
            'bets': bets,
            'rests': rests,
            'caught_rule': caught_rule,
            'n_bets': len(bets),
            'n_rest': len(rests),
            'lost_to_rest': lost_to_rest,
        })

    # ============================================================
    # Section 1: ALL 178 gaps, one row each
    # ============================================================
    lines.append("=" * 140)
    lines.append("ALL 178 GAPS")
    lines.append("=" * 140)
    header = (f"{'#':>4s} {'Acct':>6s} {'len':>4s} {'prev':>5s} {'pTri':>6s} "
              f"{'caught?':>8s} {'#bets':>5s} {'#rest':>5s} {'1stBet':>7s} {'lastBet':>8s}  "
              f"{'caught by':<14s}")
    lines.append(header)
    lines.append("-" * 140)
    union_count = 0
    lost_count = 0
    for r in rows:
        prev_str = str(r['prev_gap']) if r['prev_gap'] is not None else "—"
        ptri = (r['prev_triple'] or "—")[:6]
        if r['caught_rule']:
            caught_str = "YES"
            union_count += 1
        elif r['lost_to_rest']:
            caught_str = "lost"
            lost_count += 1
        else:
            caught_str = ""
        first_bet = r['bets'][0][0] if r['bets'] else 0
        last_bet = r['bets'][-1][0] if r['bets'] else 0
        first_str = str(first_bet) if first_bet else ""
        last_str = str(last_bet) if last_bet else ""
        cby = SHORT.get(r['caught_rule'], "") if r['caught_rule'] else ""
        lines.append(f"{r['idx']:>4d} {r['account']:>6s} {r['length']:>4d} {prev_str:>5s} {ptri:>6s} "
                     f"{caught_str:>8s} {r['n_bets']:>5d} {r['n_rest']:>5d} {first_str:>7s} {last_str:>8s}  "
                     f"{cby:<14s}")
    lines.append("")
    lines.append(f"Total caught (causal, 8/3 cooldown): {union_count} / {n_gaps}")
    lines.append(f"Triples lost to REST: {lost_count}")

    # ============================================================
    # Section 2: ONLY THE CAUGHT GAPS — full firing detail
    # ============================================================
    lines.append("")
    lines.append("=" * 140)
    lines.append(f"ONLY THE {union_count} CAUGHT GAPS — full firing detail")
    lines.append("=" * 140)
    lines.append("Each caught gap shows the full event timeline: BET = high-bet spin (rule fired,")
    lines.append("not in cooldown), REST = forced rest after 8 consecutive bets (no eval, no bet),")
    lines.append("WOULD = rule would have fired but was blocked by REST. The triple landed on LAST spin.")
    lines.append("")
    for r in rows:
        if not r['caught_rule']:
            continue
        prev_str = str(r['prev_gap']) if r['prev_gap'] is not None else "—"
        ptri = r['prev_triple'] or "—"
        lines.append("-" * 140)
        lines.append(f"  Gap #{r['idx']:3d}  acct={r['account']:6s}  length={r['length']:4d}  "
                     f"prev_gap={prev_str:>5s}  prev_triple={ptri}")
        lines.append(f"    Triple landed on spin {r['length']}")
        lines.append(f"    Caught by: {r['caught_rule']}")
        lines.append(f"    Bets: {r['n_bets']}   REST spins: {r['n_rest']}   "
                     f"warning window: spin {r['bets'][0][0] if r['bets'] else '-'}..{r['length']}")
        lines.append(f"      {'spin':>5s}  {'kind':>6s}  {'sa_spins':>9s}  {'sa_acc':>7s}  {'rate':>6s}  {'rule':<40s}")
        for spin_i, kind, rule_name, snap in r['events']:
            tag = "  <-- TRIPLE" if spin_i == r['length'] else ""
            rn = rule_name or ""
            lines.append(f"      {spin_i:>5d}  {kind:>6s}  {snap['sa_spins']:>9d}  {snap['sa_acc']:>7d}  "
                         f"{snap['rate']:>6.3f}  {rn:<40s}{tag}")

    # ============================================================
    # Section 3: PHANTOMS — gaps where rules fired but did NOT land on the triple
    # ============================================================
    phantoms = [r for r in rows if r['bets'] and not r['caught_rule']]
    lines.append("")
    lines.append("=" * 140)
    lines.append(f"GAPS WHERE THE ENSEMBLE BET BUT DID NOT CATCH THE TRIPLE ({len(phantoms)} gaps)")
    lines.append("=" * 140)
    lines.append("These are bet-spins that paid in coins for nothing. Lower is better.")
    lines.append("")
    lines.append(f"{'#':>4s} {'Acct':>6s} {'len':>4s} {'prev':>5s} {'#bets':>6s} {'#rest':>6s}  bets (spin->rule)")
    lines.append("-" * 140)
    for r in phantoms:
        prev_str = str(r['prev_gap']) if r['prev_gap'] is not None else "—"
        bets_str = ",".join(f"{s}@{SHORT.get(rn,rn)}" for s, _, rn, _ in r['bets'][:8])
        more = "" if len(r['bets']) <= 8 else f" +{len(r['bets'])-8} more"
        lines.append(f"{r['idx']:>4d} {r['account']:>6s} {r['length']:>4d} {prev_str:>5s} {r['n_bets']:>6d} {r['n_rest']:>6d}  {bets_str}{more}")

    # ============================================================
    # Section 4: PER-RULE CONTRIBUTION
    # ============================================================
    lines.append("")
    lines.append("=" * 140)
    lines.append("PER-RULE CONTRIBUTION (across all gaps, with break-on-first-match priority, post-cooldown)")
    lines.append("=" * 140)
    lines.append(f"{'rule':<35s}  {'catches':>8s}  {'bet_spins':>10s}  {'mb/hit':>8s}")
    lines.append("-" * 70)
    catches_per_rule = {name: 0 for name, _ in RULES}
    bets_per_rule    = {name: 0 for name, _ in RULES}
    for r in rows:
        if r['caught_rule']:
            catches_per_rule[r['caught_rule']] += 1
        for _, kind, rname, _ in r['bets']:
            bets_per_rule[rname] += 1
    for name, _ in RULES:
        c = catches_per_rule[name]
        b = bets_per_rule[name]
        mb = (b / c) if c else float('inf')
        mb_str = f"{mb:>8.1f}" if c else f"{'inf':>8s}"
        lines.append(f"{name:<35s}  {c:>8d}  {b:>10d}  {mb_str}")

    # ============================================================
    # Section 5: PER-ACCOUNT SUMMARY
    # ============================================================
    lines.append("")
    lines.append("=" * 140)
    lines.append("PER-ACCOUNT SUMMARY (with 8/3 cooldown)")
    lines.append("=" * 140)
    for acct in e14.ACCOUNTS:
        ar = [r for r in rows if r['account'] == acct]
        if not ar: continue
        c = sum(1 for r in ar if r['caught_rule'])
        b = sum(r['n_bets'] for r in ar)
        rest = sum(r['n_rest'] for r in ar)
        lost = sum(1 for r in ar if r['lost_to_rest'])
        lines.append(f"  {acct:6s}: {c:3d}/{len(ar):3d} caught   bet_spins={b:4d}   "
                     f"REST_spins={rest:4d}   lost_to_REST={lost}   "
                     f"mb/hit={(b/c if c else float('inf')):5.1f}")

    out_path = os.path.join(os.path.dirname(__file__), '16_per_gap_causal.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Saved -> {out_path}")
    print()
    print(f"Total caught: {union_count}/{n_gaps}")
    print(f"Lost to REST: {lost_count}")
    print(f"Phantom-bet gaps: {len(phantoms)}")


if __name__ == '__main__':
    run()
