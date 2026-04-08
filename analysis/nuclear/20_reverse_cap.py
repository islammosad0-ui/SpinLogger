"""
Chunk 20: REVERSE CAP hypothesis (user idea).

Instead of threshold = minimum spin count before betting (wait for pity),
threshold = MAXIMUM spin cap. Bet within a window, give up past the cap.

Rationale: 47% of ACC gaps end <= spin 100. Instead of waiting until 130+
and missing two-thirds of gaps, target the short-gap window directly.

Variants tested:
  A. Simple spin-window: bet if N_min <= sa_spins <= N_max
  B. Rate-gated window: same + acc_rate >= gate
  C. Conditional window: bet if prev_triple matches AND in window
  D. Early-fire: bet from spin 0 if rate is already high
  E. Multi-window: bet in multiple disjoint windows
  F. STEAL + early window (combines the best new rules)
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
    total_spins = sum(len(g['trajectory']) for g in gaps)

    for g in gaps:
        for s in g['trajectory']:
            s['_prev_triple_type'] = g.get('prev_real_triple')

    def eval_fn(fn):
        cs, bets, _ = e10.simulate_with_catch_flags(fn, gaps)
        n = len(cs)
        mb = bets / n if n else float('inf')
        base_rate = total_gaps / total_spins
        bhr = n / bets if bets else 0
        lift = bhr / base_rate if base_rate else 0
        return n, bets, mb, lift, cs

    def per_account(fn):
        out = {}
        for acct in ['Islam','Ahmed','Nick']:
            ag = [x for x in gaps if x['account'] == acct]
            cs, b, _ = e10.simulate_with_catch_flags(fn, ag)
            mb = b/len(cs) if cs else float('inf')
            out[acct] = (len(cs), len(ag), mb)
        return out

    def fmt_acct(t):
        cs, tot, mb = t
        if cs == 0: return f"0/{tot}"
        return f"{cs}/{tot} mb={mb:.0f}"

    results = []
    results.append("=" * 120)
    results.append("CHUNK 20: REVERSE CAP APPROACH — target the short-gap window")
    results.append("=" * 120)
    results.append(f"Dataset: {total_gaps} ACC gaps / {total_spins} spins")
    results.append("")
    results.append("Key insight: 47% of gaps end <= spin 100. Betting only in a")
    results.append("short window can beat waiting for the pity threshold.")
    results.append("")

    # ============================================================
    # A. Simple spin windows (no rate gate)
    # ============================================================
    results.append("=" * 120)
    results.append("A. SIMPLE SPIN WINDOWS (no rate gate)")
    results.append("=" * 120)
    results.append(f"{'window':>15s}  {'catches':>10s}  {'bets':>5s}  {'mb/hit':>7s}  {'lift':>5s}")
    results.append("-" * 60)
    windows = [
        (1, 50), (1, 80), (1, 100), (1, 120), (1, 150),
        (20, 80), (30, 80), (40, 80), (50, 100), (60, 100),
        (60, 120), (70, 110), (80, 120), (80, 150), (50, 130),
    ]
    for lo, hi in windows:
        def make(lo=lo, hi=hi):
            def f(spin, prev):
                sp = spin['sa_spins']
                return lo <= sp <= hi
            return f
        n, b, mb, lift, _ = eval_fn(make())
        results.append(f"[{lo:>3d}..{hi:>3d}]     {n:>4d}/{total_gaps}  {b:>5d}  {mb:>7.1f}  {lift:>4.1f}x")

    # ============================================================
    # B. Rate-gated windows
    # ============================================================
    results.append("")
    results.append("=" * 120)
    results.append("B. RATE-GATED WINDOWS (bet in window IF rate is high enough)")
    results.append("=" * 120)
    results.append(f"{'window':>15s}  {'gate':>5s}  {'catches':>10s}  {'bets':>5s}  {'mb/hit':>7s}  {'lift':>5s}")
    results.append("-" * 75)

    good_B = []
    for lo, hi in [(30, 80), (30, 100), (50, 100), (50, 120), (60, 100), (60, 120),
                    (70, 120), (80, 120), (80, 150), (40, 90), (40, 110)]:
        for g in [0.26, 0.28, 0.30, 0.32, 0.34, 0.36]:
            def make(lo=lo, hi=hi, g=g):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < lo or sp > hi: return False
                    return (spin['sa_acc']/sp) >= g if sp else False
                return f
            fn = make()
            n, b, mb, lift, _ = eval_fn(fn)
            if n >= 4 and mb < 40:
                results.append(f"[{lo:>3d}..{hi:>3d}]     {g:>5.2f}  {n:>4d}/{total_gaps}  {b:>5d}  {mb:>7.1f}  {lift:>4.1f}x")
                good_B.append((f"[{lo}..{hi}] g{g}", fn, n, b, mb, lift))

    # ============================================================
    # C. STEAL-cond + spin window (combine best discovery with cap)
    # ============================================================
    results.append("")
    results.append("=" * 120)
    results.append("C. STEAL-cond + SPIN WINDOW")
    results.append("=" * 120)
    results.append(f"{'window':>15s}  {'gate':>5s}  {'catches':>10s}  {'bets':>5s}  {'mb/hit':>7s}  {'lift':>5s}")
    results.append("-" * 75)

    for lo, hi in [(1, 80), (1, 100), (30, 100), (50, 120), (60, 120), (80, 150)]:
        for g in [0.30, 0.32, 0.34, 0.36]:
            def make(lo=lo, hi=hi, g=g):
                def f(spin, prev):
                    if spin.get('_prev_triple_type') != 'steal': return False
                    sp = spin['sa_spins']
                    if sp < lo or sp > hi: return False
                    return (spin['sa_acc']/sp) >= g if sp else False
                return f
            fn = make()
            n, b, mb, lift, _ = eval_fn(fn)
            if n >= 3:
                results.append(f"STEAL [{lo:>3d}..{hi:>3d}] {g:>5.2f}  {n:>4d}/{total_gaps}  {b:>5d}  {mb:>7.1f}  {lift:>4.1f}x")

    # ============================================================
    # D. Early-fire (bet from spin 0 IF rate is high)
    # ============================================================
    results.append("")
    results.append("=" * 120)
    results.append("D. EARLY-FIRE (no spin threshold, only rate gate)")
    results.append("=" * 120)
    results.append(f"{'min_spins':>10s}  {'gate':>5s}  {'catches':>10s}  {'bets':>5s}  {'mb/hit':>7s}  {'lift':>5s}")
    results.append("-" * 70)
    for min_sp in [10, 15, 20, 25, 30, 40, 50]:
        for g in [0.30, 0.33, 0.36, 0.40, 0.45, 0.50]:
            def make(min_sp=min_sp, g=g):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp < min_sp: return False
                    return (spin['sa_acc']/sp) >= g if sp else False
                return f
            n, b, mb, lift, _ = eval_fn(make())
            if n >= 5 and mb < 50:
                results.append(f"  t>={min_sp:>3d}  {g:>5.2f}  {n:>4d}/{total_gaps}  {b:>5d}  {mb:>7.1f}  {lift:>4.1f}x")

    # ============================================================
    # E. Inverse approach: bet cap at 100, no lower bound
    # ============================================================
    results.append("")
    results.append("=" * 120)
    results.append("E. HARD CAP STRATEGY: bet if sa_spins <= cap (no min, with rate)")
    results.append("=" * 120)
    results.append(f"{'cap':>5s}  {'gate':>5s}  {'catches':>10s}  {'bets':>5s}  {'mb/hit':>7s}  {'lift':>5s}")
    results.append("-" * 65)
    for cap in [50, 70, 80, 100, 120, 150]:
        for g in [0.0, 0.25, 0.30, 0.35]:
            def make(cap=cap, g=g):
                def f(spin, prev):
                    sp = spin['sa_spins']
                    if sp == 0 or sp > cap: return False
                    return (spin['sa_acc']/sp) >= g if g > 0 else True
                return f
            n, b, mb, lift, _ = eval_fn(make())
            if n >= 10:
                results.append(f"  {cap:>3d}  {g:>5.2f}  {n:>4d}/{total_gaps}  {b:>5d}  {mb:>7.1f}  {lift:>4.1f}x")

    # ============================================================
    # Compare reverse-cap champions to existing best rules
    # ============================================================
    results.append("")
    results.append("=" * 120)
    results.append("REFERENCE — best rules from other approaches")
    results.append("=" * 120)
    reference = [
        ("COMBO t=110 a=0.28 p=0.20 s=0.010 (old champion)", e10.combo_fn(110, 0.28, 0.20, 10, 0.010)),
        ("STEAL-cond t=130 g=0.28 (new best volume)", lambda: None),
        ("STEAL-cond t=90 g=0.36 (best precision)", lambda: None),
    ]
    for name, fn in reference:
        if fn is None or not callable(fn): continue
        try:
            n, b, mb, lift, _ = eval_fn(fn)
            results.append(f"  {name}: {n}/{total_gaps} @ {mb:.1f} mb, {lift:.1f}x")
        except:
            pass

    # ============================================================
    # Find the TOP reverse-cap rules and validate per-account
    # ============================================================
    results.append("")
    results.append("=" * 120)
    results.append("TOP REVERSE-CAP RULES — per-account validation")
    results.append("=" * 120)

    # Re-scan comprehensively
    comprehensive = []
    for lo in [1, 20, 30, 40, 50, 60, 70, 80]:
        for hi in [60, 80, 100, 120, 150]:
            if hi <= lo: continue
            for g in [0.0, 0.25, 0.28, 0.30, 0.32, 0.34, 0.36]:
                def make(lo=lo, hi=hi, g=g):
                    def f(spin, prev):
                        sp = spin['sa_spins']
                        if sp < lo or sp > hi: return False
                        if g > 0:
                            return (spin['sa_acc']/sp) >= g
                        return True
                    return f
                fn = make()
                n, b, mb, lift, _ = eval_fn(fn)
                if n >= 10 and mb <= 50:
                    comprehensive.append((f"[{lo}..{hi}] g{g}", fn, n, b, mb, lift))

    comprehensive.sort(key=lambda x: x[4])
    results.append(f"{'rule':<25s}  {'TOTAL':>15s}  {'Islam':>18s}  {'Ahmed':>18s}  {'Nick':>18s}")
    results.append("-" * 100)
    for name, fn, n, b, mb, lift in comprehensive[:20]:
        pa = per_account(fn)
        t_str = f"{n}/{total_gaps} mb={mb:.0f}"
        results.append(f"{name:<25s}  {t_str:>15s}  {fmt_acct(pa['Islam']):>18s}  {fmt_acct(pa['Ahmed']):>18s}  {fmt_acct(pa['Nick']):>18s}")

    out_path = os.path.join(os.path.dirname(__file__), '20_reverse_cap.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print(f"Saved -> {out_path}")


if __name__ == '__main__':
    run()
