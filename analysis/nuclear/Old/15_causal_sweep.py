"""
Chunk 15: Fresh causal sweep — rediscover best ACC formulas after phantom fix.

Sweeps every flat, COMBO, Ideal RA, SML, double-gate, and SHIELD-cond variant
using the CAUSAL simulator on all 271 gaps. Reports Pareto frontier (best
mb/hit at each catch count level) and validates top configs on all 3 accounts.

This REPLACES the old chunks 3-9 which all used simulate_fast (phantom bug).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('e10', os.path.join(os.path.dirname(__file__), '10_ensemble.py'))
e10 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e10)

from collections import defaultdict

def run():
    gaps = e10.all_gaps_with_prev()
    total_gaps = len(gaps)
    print(f"Loaded {total_gaps} ACC gaps")

    def eval_rule(fn, gaps_in):
        """Returns (caught_set, bets, mb, catch_rate)."""
        caught_set, bets, total = e10.simulate_with_catch_flags(fn, gaps_in)
        n = len(caught_set)
        mb = bets / n if n else float('inf')
        return caught_set, bets, mb, n / total_gaps, total

    def per_account(fn):
        """Returns {Islam: (catches, bets, mb), Ahmed: ..., Nick: ...}."""
        out = {}
        for acct in ['Islam', 'Ahmed', 'Nick']:
            acct_gaps = [g for g in gaps if g['account'] == acct]
            cs, bets, _, _, _ = eval_rule(fn, acct_gaps)
            mb = bets / len(cs) if cs else float('inf')
            out[acct] = (len(cs), bets, mb, len(acct_gaps))
        return out

    results = []
    configs_tested = []

    # ============================================================
    # A. Flat (threshold + acc rate gate)
    # ============================================================
    print("\nA. Flat sweep...")
    for t in [80, 90, 100, 110, 120, 130, 140, 150, 160, 180, 200]:
        for g in [0.18, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34]:
            fn = e10.flat_fn(t, g)
            cs, bets, mb, rate, _ = eval_rule(fn, gaps)
            if len(cs) >= 5:
                configs_tested.append((f"FLAT {t}/{g:.2f}", fn, len(cs), bets, mb, rate))

    # ============================================================
    # B. Double gate (flat + spn rate)
    # ============================================================
    print("B. Double gate sweep...")
    for t in [90, 100, 110, 120, 130, 140, 150]:
        for acc_g in [0.22, 0.24, 0.26, 0.28, 0.30, 0.32]:
            for spn_g in [0.14, 0.16, 0.18, 0.20, 0.22, 0.24, 0.26]:
                fn = e10.double_gate_fn(t, acc_g, spn_g)
                cs, bets, mb, rate, _ = eval_rule(fn, gaps)
                if len(cs) >= 5:
                    configs_tested.append((f"DG t{t} acc{acc_g:.2f} spn{spn_g:.2f}",
                                           fn, len(cs), bets, mb, rate))

    # ============================================================
    # C. Rate acceleration
    # ============================================================
    print("C. Rate acceleration sweep...")
    for t in [90, 100, 110, 120, 130, 140]:
        for r in [0.22, 0.24, 0.26, 0.28, 0.30]:
            for w in [5, 8, 10, 15]:
                for s in [0.004, 0.006, 0.008, 0.010, 0.015]:
                    fn = e10.ra_fn(t, r, w, s)
                    cs, bets, mb, rate, _ = eval_rule(fn, gaps)
                    if len(cs) >= 5:
                        configs_tested.append((f"RA t{t} r{r:.2f} w{w} s{s}",
                                               fn, len(cs), bets, mb, rate))

    # ============================================================
    # D. COMBO (flat + acc + spn + slope)
    # ============================================================
    print("D. COMBO sweep...")
    for t in [100, 110, 120, 130, 140]:
        for acc_g in [0.22, 0.24, 0.26, 0.28, 0.30]:
            for spn_g in [0.14, 0.16, 0.18, 0.20, 0.22]:
                for s in [0.004, 0.006, 0.008, 0.010]:
                    fn = e10.combo_fn(t, acc_g, spn_g, 10, s)
                    cs, bets, mb, rate, _ = eval_rule(fn, gaps)
                    if len(cs) >= 5:
                        configs_tested.append((f"COMBO t{t} a{acc_g:.2f} p{spn_g:.2f} s{s}",
                                               fn, len(cs), bets, mb, rate))

    # ============================================================
    # E. SML L-only (prev_gap >= L_bound, bet at t_L / g_L)
    # ============================================================
    print("E. SML L-only sweep...")
    for l_b in [100, 110, 120, 130, 140, 150, 160]:
        for t_l in [90, 100, 110, 120, 130, 140, 150]:
            for g_l in [0.22, 0.24, 0.26, 0.28, 0.30, 0.32]:
                fn = e10.sml_fn(1, l_b, None, None, t_l, g_l)
                cs, bets, mb, rate, _ = eval_rule(fn, gaps)
                if len(cs) >= 5:
                    configs_tested.append((f"SML L>={l_b} tL={t_l} g={g_l:.2f}",
                                           fn, len(cs), bets, mb, rate))

    # ============================================================
    # F. SHIELD-cond (prev real triple == shield)
    # ============================================================
    print("F. SHIELD-cond sweep...")
    for t in [80, 90, 100, 110, 120, 130, 140, 150]:
        for g in [0.22, 0.24, 0.26, 0.28, 0.30, 0.32]:
            fn = e10.shield_cond_fn(t, g, 'shield')
            cs, bets, mb, rate, _ = eval_rule(fn, gaps)
            if len(cs) >= 5:
                configs_tested.append((f"SHIELD t{t} g{g:.2f}",
                                       fn, len(cs), bets, mb, rate))

    print(f"\nTotal configs with >= 5 catches: {len(configs_tested)}")

    # ============================================================
    # Pareto frontier: best mb/hit at each catch count
    # ============================================================
    by_catches = defaultdict(list)
    for name, fn, c, b, mb, rate in configs_tested:
        by_catches[c].append((mb, name, fn, b, rate))
    for c in by_catches:
        by_catches[c].sort()  # by mb

    pareto = []
    seen_mb = float('inf')
    for c in sorted(by_catches.keys(), reverse=True):
        # Best mb at this catch count
        best = by_catches[c][0]
        if best[0] < seen_mb:
            pareto.append((c, best))
            seen_mb = best[0]
    # Also walk up in catches (low -> high) for the efficiency frontier
    up_pareto = []
    seen_mb = float('inf')
    for c in sorted(by_catches.keys()):
        best = by_catches[c][0]
        if best[0] < seen_mb:
            up_pareto.append((c, best))
            seen_mb = best[0]

    # ============================================================
    # Report
    # ============================================================
    lines = []
    lines.append("=" * 120)
    lines.append("CHUNK 15: FRESH CAUSAL SWEEP — Post-phantom-bug rediscovery")
    lines.append("=" * 120)
    lines.append("")
    lines.append(f"Dataset: {total_gaps} ACC gaps / 28,923 spins (old + new combined)")
    lines.append(f"Configs tested with >= 5 catches: {len(configs_tested)}")
    lines.append("")
    lines.append("Target reality check:")
    lines.append("  - Live tracker ground truth: 20.4% REAL catches on 49 in-range triples")
    lines.append("  - The old 10.49 mb/hit was PHANTOM")
    lines.append("  - Real target: find rules <30 mb/hit with solid catch counts")
    lines.append("")

    # Top 30 by mb/hit (with min 10 catches)
    qualified = [c for c in configs_tested if c[2] >= 10]
    qualified.sort(key=lambda x: x[4])
    lines.append("=" * 120)
    lines.append("TOP 40 by mb/hit (min 10 catches)")
    lines.append("=" * 120)
    lines.append(f"{'rule':<50s}  {'catches':>8s}  {'bets':>5s}  {'mb/hit':>7s}  {'catch%':>7s}")
    lines.append("-" * 100)
    for name, fn, c, b, mb, rate in qualified[:40]:
        lines.append(f"{name:<50s}  {c:>4d}/{total_gaps}  {b:>5d}  {mb:>7.1f}  {100*rate:>6.1f}%")

    # Also top 30 overall (any catch count)
    lines.append("")
    lines.append("=" * 120)
    lines.append("TOP 30 by mb/hit (min 5 catches — includes ultra-precise)")
    lines.append("=" * 120)
    all_sorted = sorted(configs_tested, key=lambda x: x[4])
    lines.append(f"{'rule':<50s}  {'catches':>8s}  {'bets':>5s}  {'mb/hit':>7s}  {'catch%':>7s}")
    lines.append("-" * 100)
    for name, fn, c, b, mb, rate in all_sorted[:30]:
        lines.append(f"{name:<50s}  {c:>4d}/{total_gaps}  {b:>5d}  {mb:>7.1f}  {100*rate:>6.1f}%")

    # Pareto frontier
    lines.append("")
    lines.append("=" * 120)
    lines.append("PARETO FRONTIER — best mb/hit at each catch level (upward)")
    lines.append("=" * 120)
    lines.append(f"{'catches':>8s}  {'mb/hit':>7s}  {'bets':>5s}  rule")
    lines.append("-" * 100)
    for c, (mb, name, fn, b, rate) in up_pareto:
        lines.append(f"{c:>4d}/{total_gaps}  {mb:>7.1f}  {b:>5d}  {name}")

    # Top by catch count at reasonable mb
    lines.append("")
    lines.append("=" * 120)
    lines.append("HIGH-CATCH RULES (highest catch count with mb/hit <= 50)")
    lines.append("=" * 120)
    high_catch = [c for c in configs_tested if c[4] <= 50]
    high_catch.sort(key=lambda x: -x[2])
    lines.append(f"{'rule':<50s}  {'catches':>8s}  {'bets':>5s}  {'mb/hit':>7s}  {'catch%':>7s}")
    lines.append("-" * 100)
    for name, fn, c, b, mb, rate in high_catch[:25]:
        lines.append(f"{name:<50s}  {c:>4d}/{total_gaps}  {b:>5d}  {mb:>7.1f}  {100*rate:>6.1f}%")

    # Cross-validate top 10 on per-account
    lines.append("")
    lines.append("=" * 120)
    lines.append("CROSS-VALIDATION (top 15 by catch count) — per-account breakdown")
    lines.append("=" * 120)
    top_catch = sorted(configs_tested, key=lambda x: -x[2])[:15]
    lines.append(f"{'rule':<50s}  {'Islam':>18s}  {'Ahmed':>18s}  {'Nick':>18s}")
    lines.append("-" * 115)
    for name, fn, c, b, mb, rate in top_catch:
        pa = per_account(fn)
        def fmt(pa_tuple):
            cs, bts, mb_acct, total = pa_tuple
            if cs == 0:
                return f"0/{total}"
            return f"{cs}/{total} mb={mb_acct:.0f}"
        line = f"{name:<50s}  {fmt(pa['Islam']):>18s}  {fmt(pa['Ahmed']):>18s}  {fmt(pa['Nick']):>18s}"
        lines.append(line)

    out_path = os.path.join(os.path.dirname(__file__), '15_causal_sweep.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Saved -> {out_path}")
    print(f"Report: {len(lines)} lines")


if __name__ == '__main__':
    run()
