"""
Full S/M/L sweep — every possibility including SKIP (don't bet at all).

Options per previous gap size:
  - SKIP: don't bet that cycle at all (threshold=9999)
  - Low thresholds: 40, 50, 60, 70, 80
  - Normal thresholds: 90, 100, 110, 120, 130, 140, 150, 160, 170

Also test:
  - Different S/M/L boundary definitions
  - With and without rate gate
  - Looking at last 2 gaps, not just 1
"""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

# Preload compact
all_data = []
all_gaps = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    compact = []
    for row in rows:
        sa = int(row["sa_spins"])
        sa_acc = int(row["sa_acc"])
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        is_acc = (r1 == r2 == r3 == "accumulation")
        compact.append((sa, sa_acc, is_acc))
        if is_acc:
            all_gaps.append(sa)
    all_data.append(compact)

n_gaps = len(all_gaps)
print(f"Total gaps: {n_gaps}, Mean: {sum(all_gaps)/n_gaps:.1f}, Median: {sorted(all_gaps)[n_gaps//2]}")


def simulate(threshold_fn, rate_gate=0.30):
    """threshold_fn(prev_gap) -> threshold (9999 = skip)"""
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    for rows in all_data:
        prev_gap = -1
        for sa, sa_acc, is_acc in rows:
            rate = sa_acc / sa if sa > 0 else 0.0
            total_spins += 1
            thresh = threshold_fn(prev_gap)
            should_bet = (sa >= thresh) and (rate >= rate_gate)
            if should_bet:
                total_bet += 1
            if is_acc:
                total_acc += 1
                if should_bet:
                    total_caught += 1
                prev_gap = sa

    if total_caught > 0 and total_bet > 0:
        mb = total_bet / total_caught
        bet_pct = total_bet / total_spins * 100
        lift = (total_caught / total_acc) / (total_bet / total_spins)
        return (total_caught, total_acc, bet_pct, mb, lift)
    return None


# ================================================================
# PART 1: Two-tier (after Long vs everything else)
# ================================================================
print(f"\n{'='*80}")
print(f"PART 1: TWO-TIER (after prev >= L_cut, use thresh_L; else thresh_default)")
print(f"Including SKIP option (9999)")
print(f"{'='*80}")

SKIP = 9999
thresholds = [SKIP, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170]

results_2tier = []

for l_cut in [100, 110, 120, 130, 140, 150]:
    for t_default in thresholds:
        for t_after_long in thresholds:
            def make(lc, td, tl):
                def fn(pg):
                    if pg >= lc:
                        return tl
                    return td
                return fn
            r = simulate(make(l_cut, t_default, t_after_long))
            if r:
                caught, total, bet_pct, mb, lift = r
                if caught >= 5:  # minimum 5 catches to be meaningful
                    results_2tier.append((l_cut, t_default, t_after_long, caught, total, bet_pct, mb, lift))

results_2tier.sort(key=lambda x: -x[7])  # by lift
print(f"\n  TOP 20 by LIFT (min 5 catches):")
print(f"  {'L>=':>4} {'Default':>8} {'AfterL':>8} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*55}")
for row in results_2tier[:20]:
    lc, td, tl, c, t, bp, mb, lf = row
    td_s = "SKIP" if td == SKIP else str(td)
    tl_s = "SKIP" if tl == SKIP else str(tl)
    print(f"  {lc:>4} {td_s:>8} {tl_s:>8} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Also by caught (with lift >= 5.0)
good = [r for r in results_2tier if r[7] >= 5.0]
good.sort(key=lambda x: -x[3])
print(f"\n  TOP 20 by CAUGHT (lift >= 5.0x):")
print(f"  {'L>=':>4} {'Default':>8} {'AfterL':>8} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*55}")
for row in good[:20]:
    lc, td, tl, c, t, bp, mb, lf = row
    td_s = "SKIP" if td == SKIP else str(td)
    tl_s = "SKIP" if tl == SKIP else str(tl)
    print(f"  {lc:>4} {td_s:>8} {tl_s:>8} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")


# ================================================================
# PART 2: Three-tier with SKIP
# ================================================================
print(f"\n{'='*80}")
print(f"PART 2: THREE-TIER (S/M/L with SKIP option)")
print(f"{'='*80}")

# Use fewer thresholds for 3-tier to keep it fast
thresholds_3 = [SKIP, 50, 70, 90, 110, 130, 150, 170]

results_3tier = []

for s_cut in [70, 80, 100]:
    for l_cut in [120, 130, 140]:
        for t_s in thresholds_3:
            for t_m in thresholds_3:
                for t_l in thresholds_3:
                    # Skip if all same (already tested) or all SKIP
                    if t_s == t_m == t_l:
                        continue
                    if t_s == SKIP and t_m == SKIP and t_l == SKIP:
                        continue

                    def make3(sc, lc, ts, tm, tl):
                        def fn(pg):
                            if pg < 0:
                                return tm
                            elif pg < sc:
                                return ts
                            elif pg >= lc:
                                return tl
                            else:
                                return tm
                        return fn

                    r = simulate(make3(s_cut, l_cut, t_s, t_m, t_l))
                    if r:
                        caught, total, bet_pct, mb, lift = r
                        if caught >= 5:
                            results_3tier.append((s_cut, l_cut, t_s, t_m, t_l, caught, total, bet_pct, mb, lift))

results_3tier.sort(key=lambda x: -x[9])  # by lift
print(f"\n  TOP 30 by LIFT (min 5 catches):")
print(f"  {'S<':>4} {'L>=':>4} {'AftS':>6} {'AftM':>6} {'AftL':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*62}")
for row in results_3tier[:30]:
    sc, lc, ts, tm, tl, c, t, bp, mb, lf = row
    ts_s = "SKIP" if ts == SKIP else str(ts)
    tm_s = "SKIP" if tm == SKIP else str(tm)
    tl_s = "SKIP" if tl == SKIP else str(tl)
    print(f"  {sc:>4} {lc:>4} {ts_s:>6} {tm_s:>6} {tl_s:>6} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Best by caught with lift >= 5.0
good3 = [r for r in results_3tier if r[9] >= 5.0]
good3.sort(key=lambda x: -x[5])
print(f"\n  TOP 20 by CAUGHT (lift >= 5.0x):")
print(f"  {'S<':>4} {'L>=':>4} {'AftS':>6} {'AftM':>6} {'AftL':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*62}")
for row in good3[:20]:
    sc, lc, ts, tm, tl, c, t, bp, mb, lf = row
    ts_s = "SKIP" if ts == SKIP else str(ts)
    tm_s = "SKIP" if tm == SKIP else str(tm)
    tl_s = "SKIP" if tl == SKIP else str(tl)
    print(f"  {sc:>4} {lc:>4} {ts_s:>6} {tm_s:>6} {tl_s:>6} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Best balanced (lift * caught)
results_3tier.sort(key=lambda x: -(x[5] * x[9]))
print(f"\n  TOP 20 by LIFT × CAUGHT (balanced):")
print(f"  {'S<':>4} {'L>=':>4} {'AftS':>6} {'AftM':>6} {'AftL':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6} {'Score':>7}")
print(f"  {'-'*70}")
for row in results_3tier[:20]:
    sc, lc, ts, tm, tl, c, t, bp, mb, lf = row
    ts_s = "SKIP" if ts == SKIP else str(ts)
    tm_s = "SKIP" if tm == SKIP else str(tm)
    tl_s = "SKIP" if tl == SKIP else str(tl)
    print(f"  {sc:>4} {lc:>4} {ts_s:>6} {tm_s:>6} {tl_s:>6} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x {c*lf:>6.0f}")


# ================================================================
# PART 3: Two-gap lookback
# ================================================================
print(f"\n{'='*80}")
print(f"PART 3: TWO-GAP LOOKBACK")
print(f"Use last 2 gaps to decide: SS, SM, SL, MS, MM, ML, LS, LM, LL")
print(f"{'='*80}")

def simulate_2gap(boundary, thresh_map):
    """thresh_map: dict of (prev1_size, prev2_size) -> threshold"""
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    for rows in all_data:
        prev_gaps = []
        for sa, sa_acc, is_acc in rows:
            rate = sa_acc / sa if sa > 0 else 0.0
            total_spins += 1

            if len(prev_gaps) < 2:
                thresh = 130  # default until we have 2 gaps
            else:
                g1 = prev_gaps[-2]  # two gaps ago
                g2 = prev_gaps[-1]  # last gap
                s1 = "S" if g1 < boundary else "L"
                s2 = "S" if g2 < boundary else "L"
                thresh = thresh_map.get((s1, s2), 130)

            should_bet = (sa >= thresh) and (rate >= 0.30)
            if should_bet:
                total_bet += 1
            if is_acc:
                total_acc += 1
                if should_bet:
                    total_caught += 1
                prev_gaps.append(sa)

    if total_caught > 0 and total_bet > 0:
        mb = total_bet / total_caught
        bet_pct = total_bet / total_spins * 100
        lift = (total_caught / total_acc) / (total_bet / total_spins)
        return (total_caught, total_acc, bet_pct, mb, lift)
    return None

# First: show 2-gap transition frequencies
from collections import Counter
for boundary in [100, 120]:
    print(f"\n  2-gap patterns (boundary={boundary}):")
    patterns = []
    for i in range(2, len(all_gaps)):
        g1 = all_gaps[i-2]
        g2 = all_gaps[i-1]
        g3 = all_gaps[i]
        s1 = "S" if g1 < boundary else "L"
        s2 = "S" if g2 < boundary else "L"
        patterns.append((s1, s2, g3))

    for p1 in ["S", "L"]:
        for p2 in ["S", "L"]:
            gaps_after = [g for s1, s2, g in patterns if s1 == p1 and s2 == p2]
            if gaps_after:
                s = sorted(gaps_after)
                nn = len(s)
                print(f"    After {p1}{p2} (N={nn}): med={s[nn//2]}, mean={sum(s)/nn:.0f}, <{boundary}:{sum(1 for g in s if g<boundary)}({sum(1 for g in s if g<boundary)/nn*100:.0f}%) >={boundary}:{sum(1 for g in s if g>=boundary)}({sum(1 for g in s if g>=boundary)/nn*100:.0f}%)")

# Sweep 2-gap configs
results_2gap = []
thresholds_2g = [SKIP, 90, 110, 130, 150, 170]

for boundary in [100, 120]:
    for t_ss in thresholds_2g:
        for t_sl in thresholds_2g:
            for t_ls in thresholds_2g:
                for t_ll in thresholds_2g:
                    if t_ss == t_sl == t_ls == t_ll:
                        continue
                    tmap = {("S","S"): t_ss, ("S","L"): t_sl, ("L","S"): t_ls, ("L","L"): t_ll}
                    r = simulate_2gap(boundary, tmap)
                    if r:
                        caught, total, bet_pct, mb, lift = r
                        if caught >= 5:
                            results_2gap.append((boundary, t_ss, t_sl, t_ls, t_ll, caught, total, bet_pct, mb, lift))

results_2gap.sort(key=lambda x: -x[9])
print(f"\n  TOP 20 by LIFT:")
print(f"  {'B':>3} {'SS':>6} {'SL':>6} {'LS':>6} {'LL':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*60}")
for row in results_2gap[:20]:
    b, tss, tsl, tls, tll, c, t, bp, mb, lf = row
    def f(v): return "SKIP" if v == SKIP else str(v)
    print(f"  {b:>3} {f(tss):>6} {f(tsl):>6} {f(tls):>6} {f(tll):>6} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Best balanced
results_2gap.sort(key=lambda x: -(x[5] * x[9]))
print(f"\n  TOP 10 BALANCED (lift × caught):")
print(f"  {'B':>3} {'SS':>6} {'SL':>6} {'LS':>6} {'LL':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*60}")
for row in results_2gap[:10]:
    b, tss, tsl, tls, tll, c, t, bp, mb, lf = row
    def f(v): return "SKIP" if v == SKIP else str(v)
    print(f"  {b:>3} {f(tss):>6} {f(tsl):>6} {f(tls):>6} {f(tll):>6} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")


# ================================================================
# PART 4: SUMMARY — best configs vs baseline
# ================================================================
print(f"\n{'='*80}")
print(f"FINAL COMPARISON vs BASELINE")
print(f"{'='*80}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*78}")

# Baseline
r = simulate(lambda pg: 130)
if r:
    print(f"  {'Flat 130 (CURRENT)':<55} {r[0]:>3}/{r[1]:<4} {r[2]:>5.1f}% {r[3]:>5.1f} {r[4]:>5.1f}x")

# Best 2-tier by lift
if results_2tier:
    row = results_2tier[0]
    lc, td, tl = row[0], row[1], row[2]
    td_s = "SKIP" if td == SKIP else str(td)
    tl_s = "SKIP" if tl == SKIP else str(tl)
    label = f"2-tier: L>={lc} default={td_s} afterL={tl_s}"
    print(f"  {label:<55} {row[3]:>3}/{row[4]:<4} {row[5]:>5.1f}% {row[6]:>5.1f} {row[7]:>5.1f}x")

# Best 3-tier by lift
if results_3tier:
    results_3tier.sort(key=lambda x: -x[9])
    row = results_3tier[0]
    sc, lc, ts, tm, tl = row[:5]
    ts_s = "SKIP" if ts == SKIP else str(ts)
    tm_s = "SKIP" if tm == SKIP else str(tm)
    tl_s = "SKIP" if tl == SKIP else str(tl)
    label = f"3-tier: S<{sc} L>={lc} [{ts_s}/{tm_s}/{tl_s}]"
    print(f"  {label:<55} {row[5]:>3}/{row[6]:<4} {row[7]:>5.1f}% {row[8]:>5.1f} {row[9]:>5.1f}x")

# Best 3-tier balanced
results_3tier.sort(key=lambda x: -(x[5] * x[9]))
if results_3tier:
    row = results_3tier[0]
    sc, lc, ts, tm, tl = row[:5]
    ts_s = "SKIP" if ts == SKIP else str(ts)
    tm_s = "SKIP" if tm == SKIP else str(tm)
    tl_s = "SKIP" if tl == SKIP else str(tl)
    label = f"3-tier balanced: S<{sc} L>={lc} [{ts_s}/{tm_s}/{tl_s}]"
    print(f"  {label:<55} {row[5]:>3}/{row[6]:<4} {row[7]:>5.1f}% {row[8]:>5.1f} {row[9]:>5.1f}x")

# Best 2-gap by lift
if results_2gap:
    results_2gap.sort(key=lambda x: -x[9])
    row = results_2gap[0]
    def f(v): return "SKIP" if v == SKIP else str(v)
    label = f"2-gap: b={row[0]} SS={f(row[1])} SL={f(row[2])} LS={f(row[3])} LL={f(row[4])}"
    print(f"  {label:<55} {row[5]:>3}/{row[6]:<4} {row[7]:>5.1f}% {row[8]:>5.1f} {row[9]:>5.1f}x")

print(f"\nDone!", flush=True)
