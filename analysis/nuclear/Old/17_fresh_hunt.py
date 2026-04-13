"""
Chunk 17: FRESH HUNT — test signals we've never explored.

The phantom bug invalidated the old conclusions. We optimized COMBO/Ideal RA/SML
based on fake catches. Now we search for genuinely NEW signal we never tried:

Hypotheses to test on CAUSAL data (271 ACC gaps, 28,923 spins):
  H1. STEAL-cond (never tested)
  H2. sa_3x_* streak signals (N prior non-target triples since last ACC)
  H3. Inverse gates (LOW sa_shd, LOW sa_atk — bet when bad symbols are scarce)
  H4. Symbol ratio gates (sa_acc/sa_shd, sa_acc/sa_atk, etc.)
  H5. Recent-window rate (last N spins rate vs total gap rate)
  H6. accum_pct at gap START (mission progress when gap began)
  H7. accum_delta patterns (mix events, bar bursts)
  H8. ss_* counters as ACC predictors (cross-stream)
  H9. Multi-condition AND rules (stacking weak signals)
  H10. Second derivative (slope of slope)
  H11. Bet-sum predictor (pity timer might be bet-amount-based, not spin-count)
  H12. Inverse-other rules (low other-symbol rates AS predictor)
  H13. Recent vs historical rate divergence
  H14. Prev-gap + prev-triple combinations
  H15. Accumulation percentage delta patterns

For each hypothesis, we sweep parameters and report top configs at causal
mb/hit. Anything beating SHIELD-cond 150/0.30 (18.4 mb, 8 catches) gets special
attention.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('e10', os.path.join(os.path.dirname(__file__), '10_ensemble.py'))
e10 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e10)

from collections import defaultdict


def eval_rule(fn, gaps):
    """Causal eval. Returns (catches, bets, mb, lift)."""
    caught_set, bets, total_spins = e10.simulate_with_catch_flags(fn, gaps)
    n = len(caught_set)
    mb = bets / n if n else float('inf')
    base_rate = len(gaps) / total_spins if total_spins else 0
    lift = (n / bets) / base_rate if bets and base_rate else 0
    return n, bets, mb, lift, caught_set


def run():
    gaps = e10.all_gaps_with_prev()
    total_gaps = len(gaps)
    print(f"Loaded {total_gaps} ACC gaps")

    # We also precompute some per-spin derived fields that require trajectory context.
    # Inject them now so decision functions can read them directly.
    for gap in gaps:
        traj = gap['trajectory']
        for i, spin in enumerate(traj):
            spin['_traj_ref'] = traj
            spin['_traj_idx'] = i
            spin['_prev_triple_type'] = gap.get('prev_real_triple')

            # Last-N window rates (for H5)
            for N in [5, 10, 15, 20]:
                if i >= N:
                    start = traj[i - N]
                    d_spins = spin['sa_spins'] - start['sa_spins']
                    d_acc = spin['sa_acc'] - start['sa_acc']
                    d_spn = spin['sa_spn'] - start['sa_spn']
                    d_shd = spin['sa_shd'] - start['sa_shd']
                    d_atk = spin['sa_atk'] - start['sa_atk']
                    spin[f'_recent_{N}_acc_rate'] = d_acc / d_spins if d_spins else 0
                    spin[f'_recent_{N}_spn_rate'] = d_spn / d_spins if d_spins else 0
                    spin[f'_recent_{N}_shd_rate'] = d_shd / d_spins if d_spins else 0
                    spin[f'_recent_{N}_atk_rate'] = d_atk / d_spins if d_spins else 0
                else:
                    spin[f'_recent_{N}_acc_rate'] = 0
                    spin[f'_recent_{N}_spn_rate'] = 0
                    spin[f'_recent_{N}_shd_rate'] = 0
                    spin[f'_recent_{N}_atk_rate'] = 0

            # accum_pct at gap start (H6)
            spin['_gap_start_pct'] = traj[0].get('accum_pct', 0) if traj else 0

    # ============================================================
    # Build candidates by hypothesis
    # ============================================================
    candidates = []  # (name, fn)

    # --- H1: STEAL-cond (never tested) ---
    for t in [80, 90, 100, 110, 120, 130, 140, 150]:
        for g in [0.20, 0.22, 0.24, 0.26, 0.28, 0.30]:
            def make(t=t, g=g):
                def f(spin, prev):
                    if spin.get('_prev_triple_type') != 'steal': return False
                    sp = spin['sa_spins']
                    if sp < t: return False
                    return (spin['sa_acc']/sp) >= g if sp else False
                return f
            candidates.append((f"H1:STEAL t{t} g{g:.2f}", make()))

    # --- H2: sa_3x_* streak signals ---
    # Bet when N or more non-target triples have already happened
    for min_streak in [1, 2, 3, 4]:
        for t in [80, 100, 120, 130, 150]:
            for symbol in ['atk', 'stl', 'shd']:
                def make(min_streak=min_streak, t=t, symbol=symbol):
                    def f(spin, prev):
                        sp = spin['sa_spins']
                        if sp < t: return False
                        return spin.get(f'sa_3x_{symbol}', 0) >= min_streak
                    return f
                candidates.append((f"H2:streak {symbol}>={min_streak} t{t}", make()))

    # Total non-target triples since last ACC (combined)
    for min_total in [2, 3, 4, 5]:
        for t in [80, 100, 120, 130]:
            def make(min_total=min_total, t=t):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < t: return False
                    return (spin.get('sa_3x_atk',0) + spin.get('sa_3x_stl',0) + spin.get('sa_3x_shd',0)) >= min_total
                return f
            candidates.append((f"H2:tot_streak>={min_total} t{t}", make()))

    # --- H3: Inverse gates (LOW other-symbol rates) ---
    for t in [100, 120, 130, 150]:
        for max_rate in [0.12, 0.15, 0.18, 0.20, 0.22]:
            for symbol in ['shd', 'atk', 'stl']:
                def make(t=t, max_rate=max_rate, symbol=symbol):
                    def f(spin, prev):
                        sp = spin['sa_spins']
                        if sp < t: return False
                        return (spin.get(f'sa_{symbol}',0)/sp) <= max_rate if sp else False
                    return f
                candidates.append((f"H3:inv {symbol}<={max_rate:.2f} t{t}", make()))

    # H3+: inverse + acc gate combined
    for t in [120, 130, 140]:
        for acc_g in [0.22, 0.24, 0.26]:
            for max_shd in [0.15, 0.18, 0.20]:
                def make(t=t, acc_g=acc_g, max_shd=max_shd):
                    def f(spin, prev):
                        sp = spin['sa_spins']
                        if sp < t: return False
                        if (spin['sa_acc']/sp) < acc_g: return False
                        return (spin.get('sa_shd',0)/sp) <= max_shd
                    return f
                candidates.append((f"H3+:acc>={acc_g:.2f} shd<={max_shd:.2f} t{t}", make()))

    # --- H4: Symbol ratio gates ---
    for t in [100, 120, 130, 150]:
        for min_ratio in [1.0, 1.2, 1.5, 2.0, 2.5, 3.0]:
            def make(t=t, min_ratio=min_ratio):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < t: return False
                    shd = spin.get('sa_shd', 0)
                    if shd == 0: return spin['sa_acc'] > 0  # no shield, any acc = ratio infinity
                    return (spin['sa_acc'] / shd) >= min_ratio
                return f
            candidates.append((f"H4:acc/shd>={min_ratio:.1f} t{t}", make()))

    for t in [100, 120, 130, 150]:
        for min_ratio in [0.5, 0.8, 1.0, 1.2, 1.5, 2.0]:
            def make(t=t, min_ratio=min_ratio):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < t: return False
                    atk = spin.get('sa_atk', 0)
                    if atk == 0: return spin['sa_acc'] > 0
                    return (spin['sa_acc'] / atk) >= min_ratio
                return f
            candidates.append((f"H4:acc/atk>={min_ratio:.1f} t{t}", make()))

    # --- H5: Recent-window rate predictors ---
    for t in [100, 120, 130, 150]:
        for N in [5, 10, 15, 20]:
            for g in [0.24, 0.28, 0.32, 0.36, 0.40, 0.45, 0.50]:
                def make(t=t, N=N, g=g):
                    def f(spin, prev):
                        sp = spin['sa_spins']
                        if sp < t: return False
                        return spin.get(f'_recent_{N}_acc_rate', 0) >= g
                    return f
                candidates.append((f"H5:rec{N} acc>={g:.2f} t{t}", make()))

    # H5+: recent LOW shield + high acc
    for t in [120, 130]:
        for N in [10, 15, 20]:
            for max_shd in [0.10, 0.15, 0.20]:
                def make(t=t, N=N, max_shd=max_shd):
                    def f(spin, prev):
                        sp = spin['sa_spins']
                        if sp < t: return False
                        return spin.get(f'_recent_{N}_shd_rate', 0) <= max_shd
                    return f
                candidates.append((f"H5+:rec{N} shd<={max_shd:.2f} t{t}", make()))

    # --- H6: accum_pct at gap start ---
    for t in [100, 120, 130]:
        for min_pct in [40, 50, 60, 70, 80]:
            def make(t=t, min_pct=min_pct):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < t: return False
                    return spin.get('_gap_start_pct', 0) >= min_pct
                return f
            candidates.append((f"H6:gap_start_pct>={min_pct} t{t}", make()))

        for max_pct in [20, 30, 40]:
            def make(t=t, max_pct=max_pct):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < t: return False
                    return spin.get('_gap_start_pct', 0) <= max_pct
                return f
            candidates.append((f"H6:gap_start_pct<={max_pct} t{t}", make()))

    # --- H7: accum_delta patterns (bar-bursts detect mix events) ---
    for t in [100, 120, 130]:
        for min_delta in [5, 10, 20, 30]:
            def make(t=t, min_delta=min_delta):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < t: return False
                    return spin.get('accum_delta', 0) >= min_delta
                return f
            candidates.append((f"H7:delta>={min_delta} t{t}", make()))

    # --- H8: ss_* counters as ACC predictor ---
    for t in [100, 120, 130]:
        for g in [0.28, 0.30, 0.32, 0.34]:
            def make(t=t, g=g):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < t: return False
                    ss_sp = spin.get('ss_spins', 0)
                    if ss_sp == 0: return False
                    return (spin.get('ss_acc', 0) / ss_sp) >= g
                return f
            candidates.append((f"H8:ss_acc/ss_spins>={g:.2f} t{t}", make()))

    # H8+: ss_spn gate (low ss_spn might mean SPN is "cooling")
    for t in [100, 120, 130]:
        for max_g in [0.20, 0.25, 0.30]:
            def make(t=t, max_g=max_g):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < t: return False
                    ss_sp = spin.get('ss_spins', 0)
                    if ss_sp == 0: return False
                    return (spin.get('ss_spn', 0) / ss_sp) <= max_g
                return f
            candidates.append((f"H8+:ss_spn<={max_g:.2f} t{t}", make()))

    # --- H9: Multi-condition AND rules ---
    # SHIELD-cond + high acc + low shd (stacking)
    for t in [130, 140, 150]:
        for acc_g in [0.22, 0.26, 0.30]:
            for max_shd in [0.15, 0.20]:
                def make(t=t, acc_g=acc_g, max_shd=max_shd):
                    def f(spin, prev):
                        if spin.get('_prev_triple_type') != 'shield': return False
                        sp = spin['sa_spins']
                        if sp < t: return False
                        if (spin['sa_acc']/sp) < acc_g: return False
                        return (spin.get('sa_shd', 0)/sp) <= max_shd
                    return f
                candidates.append((f"H9:SHIELD+acc{acc_g:.2f}+shd<{max_shd:.2f} t{t}", make()))

    # prev_gap_length>=120 + shield-cond
    for t in [130, 150]:
        for g in [0.24, 0.28, 0.30]:
            def make(t=t, g=g):
                def f(spin, prev):
                    if prev is None or prev < 120: return False
                    if spin.get('_prev_triple_type') != 'shield': return False
                    sp = spin['sa_spins']
                    if sp < t: return False
                    return (spin['sa_acc']/sp) >= g
                return f
            candidates.append((f"H9:L>=120 SHIELD t{t} g{g:.2f}", make()))

    # --- H11: Bet sum predictor (pity timer might be bet-based not spin-based) ---
    # Compute cumulative bet within each gap, bet high when bet sum crosses threshold
    for gap in gaps:
        traj = gap['trajectory']
        bet_sum = 0
        for s in traj:
            bet_sum += s.get('bet_multiplier', 1) or 1
            s['_bet_sum'] = bet_sum

    for min_bet_sum in [100, 200, 500, 1000, 2000, 5000]:
        def make(min_bet_sum=min_bet_sum):
            def f(spin, prev):
                return spin.get('_bet_sum', 0) >= min_bet_sum
            return f
        candidates.append((f"H11:bet_sum>={min_bet_sum}", make()))

    # --- H12: Multi-signal light-AND — at least K signals ---
    # Define weak signals and require K+ to be active
    def weak_signals(spin):
        sp = spin['sa_spins']
        if sp < 80: return 0
        acc_r = spin['sa_acc'] / sp if sp else 0
        sigs = 0
        if sp >= 120: sigs += 1
        if acc_r >= 0.26: sigs += 1
        if spin.get('_prev_triple_type') == 'shield': sigs += 1
        if sp >= 100 and spin.get('sa_3x_shd', 0) >= 1: sigs += 1
        if sp >= 100 and (spin.get('sa_spn', 0)/sp if sp else 0) >= 0.20: sigs += 1
        if spin.get('_recent_10_acc_rate', 0) >= 0.30: sigs += 1
        return sigs

    for min_sigs in [2, 3, 4]:
        for t in [80, 100, 120]:
            def make(min_sigs=min_sigs, t=t):
                def f(spin, prev):
                    if spin['sa_spins'] < t: return False
                    return weak_signals(spin) >= min_sigs
                return f
            candidates.append((f"H12:sigs>={min_sigs} t{t}", make()))

    # --- H14: prev_gap + prev_triple combinations ---
    for prev_type in ['shield', 'attack', 'steal', 'spins']:
        for l_min in [100, 120, 140]:
            for t in [110, 130, 150]:
                for g in [0.22, 0.26]:
                    def make(prev_type=prev_type, l_min=l_min, t=t, g=g):
                        def f(spin, prev):
                            if prev is None or prev < l_min: return False
                            if spin.get('_prev_triple_type') != prev_type: return False
                            sp = spin['sa_spins']
                            if sp < t: return False
                            return (spin['sa_acc']/sp) >= g
                        return f
                    candidates.append((f"H14:{prev_type}+L>={l_min} t{t} g{g:.2f}", make()))

    # --- H16: Gap length RECURRENCE (user hypothesis) ---
    # If the same gap length has occurred 2+ times before in this account's history,
    # bet when the current sa_spins is near that recurring length.
    # Build a per-account lookup of (recurring_length -> count) using all PRIOR gaps.
    for gap in gaps:
        gap['_recurrence_triggers'] = set()

    # Group gaps by account in original order
    by_acct = defaultdict(list)
    for gi, gap in enumerate(gaps):
        by_acct[gap['account']].append((gi, gap))

    for acct, gap_list in by_acct.items():
        length_counts = defaultdict(int)
        for gi, gap in gap_list:
            # First, compute the "recurrence triggers" for THIS gap based on PRIOR history
            triggers = set()
            for L, c in length_counts.items():
                if c >= 2:
                    # bet when sa_spins is within window of this recurring length
                    triggers.add(L)
            gap['_recurrence_triggers'] = triggers
            # Now add this gap's length to the history for future gaps
            length_counts[gap['length']] += 1

    # Rule: bet when sa_spins is exactly at a recurring length (± window)
    for window in [0, 1, 2, 3, 5]:
        def make(window=window):
            def f(spin, prev):
                sp = spin['sa_spins']
                triggers = spin.get('_recurrence_triggers_for_gap', set())
                if not triggers: return False
                for L in triggers:
                    if abs(sp - L) <= window:
                        return True
                return False
            return f
        candidates.append((f"H16:recurrence window=±{window}", make()))

    # Inject recurrence triggers into each spin for lookup
    for gap in gaps:
        triggers = gap.get('_recurrence_triggers', set())
        for spin in gap['trajectory']:
            spin['_recurrence_triggers_for_gap'] = triggers

    # Stricter recurrence: require 3+ prior occurrences
    for gap in gaps:
        gap['_recurrence3_triggers'] = set()
    for acct, gap_list in by_acct.items():
        length_counts = defaultdict(int)
        for gi, gap in gap_list:
            triggers = set()
            for L, c in length_counts.items():
                if c >= 3:
                    triggers.add(L)
            gap['_recurrence3_triggers'] = triggers
            length_counts[gap['length']] += 1
    for gap in gaps:
        triggers = gap.get('_recurrence3_triggers', set())
        for spin in gap['trajectory']:
            spin['_recurrence3_for_gap'] = triggers

    for window in [0, 1, 2, 3, 5]:
        def make(window=window):
            def f(spin, prev):
                sp = spin['sa_spins']
                triggers = spin.get('_recurrence3_for_gap', set())
                if not triggers: return False
                for L in triggers:
                    if abs(sp - L) <= window:
                        return True
                return False
            return f
        candidates.append((f"H16:recur3+ window=±{window}", make()))

    # Bucketed recurrence: group nearby lengths (e.g., 100-110, 110-120)
    # then bet when prior had lots of hits in the current bucket
    for gap in gaps:
        gap['_bucket_triggers'] = set()
    BUCKET_SIZE = 10
    for acct, gap_list in by_acct.items():
        bucket_counts = defaultdict(int)
        for gi, gap in gap_list:
            triggers = set()
            for bkt, c in bucket_counts.items():
                if c >= 2:
                    triggers.add(bkt)
            gap['_bucket_triggers'] = triggers
            bucket_counts[gap['length'] // BUCKET_SIZE] += 1
    for gap in gaps:
        triggers = gap.get('_bucket_triggers', set())
        for spin in gap['trajectory']:
            spin['_bucket_triggers_for_gap'] = triggers

    for t in [100, 120]:
        def make(t=t, bs=BUCKET_SIZE):
            def f(spin, prev):
                sp = spin['sa_spins']
                if sp < t: return False
                triggers = spin.get('_bucket_triggers_for_gap', set())
                return (sp // bs) in triggers
            return f
        candidates.append((f"H16:bucket10 recur>=2 t{t}", make()))

    # --- H15: Accumulation-based rules (different from accum_pct) ---
    # When accum_current is close to accum_total (mission almost done)
    for t in [100, 130]:
        for max_remaining in [5000, 10000, 20000, 50000]:
            def make(t=t, max_remaining=max_remaining):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < t: return False
                    total = spin.get('accum_total', 0)
                    curr = spin.get('accum_current', 0)
                    return (total - curr) <= max_remaining and total > 0
                return f
            candidates.append((f"H15:mission_remaining<={max_remaining} t{t}", make()))

    print(f"\nTotal hypotheses to test: {len(candidates)}")

    # ============================================================
    # Evaluate all candidates
    # ============================================================
    results = []
    for name, fn in candidates:
        n, b, mb, lift, cs = eval_rule(fn, gaps)
        if n >= 3:  # at least 3 catches to be worth reporting
            results.append((name, n, b, mb, lift, cs))

    # ============================================================
    # Report
    # ============================================================
    lines = []
    lines.append("=" * 120)
    lines.append("CHUNK 17: FRESH HUNT — NEW signals post-phantom-bug")
    lines.append("=" * 120)
    lines.append(f"Dataset: {total_gaps} ACC gaps / 28,923 spins")
    lines.append(f"Hypotheses tested: {len(candidates)} configs")
    lines.append(f"With >= 3 catches: {len(results)}")
    lines.append("")

    # Top by mb/hit
    lines.append("TOP 50 BY MB/HIT (min 5 catches)")
    lines.append("-" * 100)
    lines.append(f"{'rule':<52s}  {'catches':>10s}  {'bets':>5s}  {'mb/hit':>7s}  {'lift':>6s}")
    qualified = [r for r in results if r[1] >= 5]
    qualified.sort(key=lambda x: x[3])
    for name, n, b, mb, lift, cs in qualified[:50]:
        lines.append(f"{name:<52s}  {n:>4d}/{total_gaps}  {b:>5d}  {mb:>7.1f}  {lift:>5.1f}x")

    lines.append("")
    lines.append("TOP 30 BY CATCH COUNT (min mb/hit <= 50)")
    lines.append("-" * 100)
    high_catch = [r for r in results if r[3] <= 50]
    high_catch.sort(key=lambda x: -x[1])
    lines.append(f"{'rule':<52s}  {'catches':>10s}  {'bets':>5s}  {'mb/hit':>7s}  {'lift':>6s}")
    for name, n, b, mb, lift, cs in high_catch[:30]:
        lines.append(f"{name:<52s}  {n:>4d}/{total_gaps}  {b:>5d}  {mb:>7.1f}  {lift:>5.1f}x")

    # Per-hypothesis best
    lines.append("")
    lines.append("=" * 120)
    lines.append("BEST RULE PER HYPOTHESIS (sorted by mb/hit within each)")
    lines.append("=" * 120)
    hyp_buckets = defaultdict(list)
    for name, n, b, mb, lift, cs in results:
        hyp = name.split(':')[0]
        hyp_buckets[hyp].append((name, n, b, mb, lift))

    for hyp in sorted(hyp_buckets.keys()):
        items = hyp_buckets[hyp]
        items.sort(key=lambda x: x[3])
        lines.append(f"\n{hyp}:")
        for name, n, b, mb, lift in items[:5]:
            lines.append(f"  {name:<55s}  {n:>3d}/{total_gaps}  bets={b:>4d}  mb={mb:>6.1f}  lift={lift:.1f}x")

    # Reference best from chunk 16
    lines.append("")
    lines.append("=" * 120)
    lines.append("REFERENCE: current best from chunk 16 (for comparison)")
    lines.append("=" * 120)
    lines.append("  SHIELD t150 g0.30:    8 catches @ 18.4 mb/hit  (5.7x lift)")
    lines.append("  SHIELD t150 g0.28:   14 catches @ 22.1 mb/hit")
    lines.append("  SHIELD t130 g0.22:   27 catches @ 31.4 mb/hit")
    lines.append("  DG t130 acc0.28 spn0.24: 36 catches @ 34.9 mb/hit")
    lines.append("  7-rule greedy cover: 93 catches @ 41.06 mb/hit")
    lines.append("")
    lines.append("A new rule is 'interesting' if it beats SHIELD t150 g0.30 (18.4 mb)")
    lines.append("OR adds unique catches not covered by the chunk 16 ensemble.")

    out_path = os.path.join(os.path.dirname(__file__), '17_fresh_hunt.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Saved -> {out_path}")
    print(f"Report: {len(lines)} lines, {len(qualified)} qualified configs")

    # Quick console summary of top 10
    print("\nTop 10 by mb/hit (>= 5 catches):")
    for name, n, b, mb, lift, cs in qualified[:10]:
        print(f"  {name:<55s}  {n:>3d}/{total_gaps}  mb={mb:>6.1f}  lift={lift:.1f}x")


if __name__ == '__main__':
    run()
