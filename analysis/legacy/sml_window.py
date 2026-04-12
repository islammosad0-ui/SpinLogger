"""
S/M/L with BETTING WINDOWS — start AND stop thresholds.

For each predicted gap size:
  - start: when to start betting max
  - stop: when to STOP if triple hasn't fired (prediction was wrong)

This prevents burning spins on wrong predictions.
"""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

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


def simulate_window(window_fn):
    """
    window_fn(prev_gap) -> (start, stop)
    Bet when: start <= sa_spins <= stop AND rate >= 0.30
    """
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    for rows in all_data:
        prev_gap = -1
        for sa, sa_acc, is_acc in rows:
            rate = sa_acc / sa if sa > 0 else 0.0
            total_spins += 1

            start, stop = window_fn(prev_gap)
            should_bet = (sa >= start) and (sa <= stop) and (rate >= 0.30)

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
# PART 1: What do gap distributions look like after each size?
# (to pick good window ranges)
# ================================================================
print("=" * 80)
print("GAP DISTRIBUTION AFTER EACH SIZE (for picking windows)")
print("=" * 80)

for boundary in [100, 120]:
    print(f"\n  Boundary: S < {boundary}, L >= {boundary}")
    for prev_label, condition in [("Short", lambda g: g < boundary), ("Long", lambda g: g >= boundary)]:
        next_gaps = [all_gaps[i] for i in range(1, len(all_gaps)) if condition(all_gaps[i-1])]
        if not next_gaps:
            continue
        s = sorted(next_gaps)
        nn = len(s)
        print(f"\n    After {prev_label} (N={nn}):")
        print(f"      P10={s[nn//10]} P25={s[nn//4]} P50={s[nn//2]} P75={s[3*nn//4]} P90={s[9*nn//10]}")
        for lo in range(0, 261, 20):
            hi = lo + 20
            c = sum(1 for g in next_gaps if lo <= g < hi)
            bar = "#" * c
            if c > 0:
                print(f"        {lo:>3}-{hi:<3}: {c:>2} ({c/nn*100:>4.1f}%) {bar}")


# ================================================================
# PART 2: Fixed window (no prediction) — just test window sizes
# ================================================================
print(f"\n{'='*80}")
print(f"PART 2: FIXED WINDOWS (no S/M/L, same window every cycle)")
print(f"{'='*80}")
print(f"  {'Start':>6} {'Stop':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*46}")

for start in [80, 90, 100, 110, 120, 130]:
    for stop in [start + 20, start + 30, start + 40, start + 50, start + 80, start + 100, 9999]:
        r = simulate_window(lambda pg, s=start, e=stop: (s, e))
        if r and r[0] >= 3:
            stop_s = "INF" if stop > 9000 else str(stop)
            print(f"  {start:>6} {stop_s:>6} {r[0]:>3}/{r[1]:<4} {r[2]:>5.1f}% {r[3]:>5.1f} {r[4]:>5.1f}x")


# ================================================================
# PART 3: Predicted windows — different window per predicted size
# ================================================================
print(f"\n{'='*80}")
print(f"PART 3: PREDICTED WINDOWS — different window per previous gap size")
print(f"{'='*80}")

SKIP = (9999, 0)  # impossible window = skip

results = []

# After Short: predict long -> high start, open end
# After Long: predict short -> low start, capped end
# After Medium: normal

for boundary in [100, 120]:
    # Windows to try for "after short" (predict long)
    after_short_windows = [
        SKIP,
        (130, 9999),  # normal, open
        (140, 9999),
        (150, 9999),
        (130, 200),   # normal, capped
        (140, 200),
        (150, 200),
    ]

    # Windows to try for "after long" (predict short)
    after_long_windows = [
        SKIP,
        (40, 80), (40, 100), (40, 120), (40, 9999),
        (50, 80), (50, 100), (50, 120), (50, 9999),
        (60, 90), (60, 100), (60, 120), (60, 9999),
        (70, 100), (70, 120), (70, 9999),
        (80, 110), (80, 120), (80, 130), (80, 9999),
        (90, 120), (90, 130), (90, 9999),
        (100, 130), (100, 140), (100, 9999),
        (110, 140), (110, 9999),
        (120, 150), (120, 9999),
        (130, 170), (130, 9999),
    ]

    for sw in after_short_windows:
        for lw in after_long_windows:
            def make(b, s_win, l_win):
                def fn(pg):
                    if pg < 0:
                        return (130, 9999)  # first cycle
                    elif pg < b:
                        return s_win
                    else:
                        return l_win
                return fn

            r = simulate_window(make(boundary, sw, lw))
            if r and r[0] >= 5:
                caught, total, bet_pct, mb, lift = r
                sw_s = "SKIP" if sw == SKIP else f"{sw[0]}-{sw[1] if sw[1]<9000 else 'INF'}"
                lw_s = "SKIP" if lw == SKIP else f"{lw[0]}-{lw[1] if lw[1]<9000 else 'INF'}"
                results.append((boundary, sw_s, lw_s, caught, total, bet_pct, mb, lift))

results.sort(key=lambda x: -x[7])  # by lift
print(f"\n  TOP 30 by LIFT (min 5 catches):")
print(f"  {'B':>3} {'After Short':>14} {'After Long':>14} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*66}")
for row in results[:30]:
    b, sw, lw, c, t, bp, mb, lf = row
    print(f"  {b:>3} {sw:>14} {lw:>14} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# By caught with lift >= 5
good = [r for r in results if r[7] >= 5.0]
good.sort(key=lambda x: -x[3])
print(f"\n  TOP 20 by CAUGHT (lift >= 5.0x):")
print(f"  {'B':>3} {'After Short':>14} {'After Long':>14} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*66}")
for row in good[:20]:
    b, sw, lw, c, t, bp, mb, lf = row
    print(f"  {b:>3} {sw:>14} {lw:>14} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Best balanced
results.sort(key=lambda x: -(x[3] * x[7]))
print(f"\n  TOP 20 BALANCED (lift × caught):")
print(f"  {'B':>3} {'After Short':>14} {'After Long':>14} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6} {'Score':>7}")
print(f"  {'-'*74}")
for row in results[:20]:
    b, sw, lw, c, t, bp, mb, lf = row
    print(f"  {b:>3} {sw:>14} {lw:>14} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x {c*lf:>6.0f}")


# ================================================================
# PART 4: THREE-TIER windows (S/M/L each has own window)
# ================================================================
print(f"\n{'='*80}")
print(f"PART 4: THREE-TIER WINDOWS (S/M/L each has own start-stop)")
print(f"{'='*80}")

results_3 = []

for s_cut in [80, 100]:
    for l_cut in [120, 140]:
        # After S windows
        for s_win in [SKIP, (140, 9999), (150, 9999), (130, 200), (150, 200)]:
            # After M windows
            for m_win in [(120, 9999), (130, 9999), (130, 180), (120, 170)]:
                # After L windows
                for l_win in [
                    SKIP, (50, 90), (50, 100), (60, 100), (60, 110),
                    (70, 110), (70, 120), (80, 120), (80, 130),
                    (90, 130), (100, 140), (110, 9999), (120, 9999), (130, 9999),
                ]:
                    def make3(sc, lc, sw, mw, lw):
                        def fn(pg):
                            if pg < 0:
                                return mw
                            elif pg < sc:
                                return sw
                            elif pg >= lc:
                                return lw
                            else:
                                return mw
                        return fn

                    r = simulate_window(make3(s_cut, l_cut, s_win, m_win, l_win))
                    if r and r[0] >= 5:
                        caught, total, bet_pct, mb, lift = r
                        def fmt(w):
                            if w == SKIP: return "SKIP"
                            return f"{w[0]}-{w[1] if w[1]<9000 else 'INF'}"
                        results_3.append((s_cut, l_cut, fmt(s_win), fmt(m_win), fmt(l_win),
                                         caught, total, bet_pct, mb, lift))

results_3.sort(key=lambda x: -x[9])  # lift
print(f"\n  TOP 20 by LIFT:")
print(f"  {'S<':>3} {'L>=':>4} {'AftS':>10} {'AftM':>10} {'AftL':>10} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*72}")
for row in results_3[:20]:
    sc, lc, sw, mw, lw, c, t, bp, mb, lf = row
    print(f"  {sc:>3} {lc:>4} {sw:>10} {mw:>10} {lw:>10} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Best balanced
results_3.sort(key=lambda x: -(x[5] * x[9]))
print(f"\n  TOP 20 BALANCED:")
print(f"  {'S<':>3} {'L>=':>4} {'AftS':>10} {'AftM':>10} {'AftL':>10} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*72}")
for row in results_3[:20]:
    sc, lc, sw, mw, lw, c, t, bp, mb, lf = row
    print(f"  {sc:>3} {lc:>4} {sw:>10} {mw:>10} {lw:>10} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# By caught at lift >= 5
good3 = [r for r in results_3 if r[9] >= 5.0]
good3.sort(key=lambda x: -x[5])
print(f"\n  TOP 20 by CAUGHT (lift >= 5.0x):")
print(f"  {'S<':>3} {'L>=':>4} {'AftS':>10} {'AftM':>10} {'AftL':>10} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*72}")
for row in good3[:20]:
    sc, lc, sw, mw, lw, c, t, bp, mb, lf = row
    print(f"  {sc:>3} {lc:>4} {sw:>10} {mw:>10} {lw:>10} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")


# ================================================================
# FINAL SUMMARY
# ================================================================
print(f"\n{'='*80}")
print(f"FINAL SUMMARY vs BASELINE")
print(f"{'='*80}")

# Baseline
r = simulate_window(lambda pg: (130, 9999))
print(f"  Flat 130+ (CURRENT):                  {r[0]:>3}/{r[1]:<4} {r[2]:>5.1f}% mb={r[3]:>5.1f} lift={r[4]:>5.1f}x")

# Find best at each tier
print(f"\n  Best by lift (min 5 caught):")
results.sort(key=lambda x: -x[7])
if results:
    row = results[0]
    print(f"    2-tier: b={row[0]} short={row[1]} long={row[2]}  =>  {row[3]}/{row[4]} mb={row[6]:.1f} lift={row[7]:.1f}x")

results_3.sort(key=lambda x: -x[9])
if results_3:
    row = results_3[0]
    print(f"    3-tier: S<{row[0]} L>={row[1]} [{row[2]}/{row[3]}/{row[4]}]  =>  {row[5]}/{row[6]} mb={row[8]:.1f} lift={row[9]:.1f}x")

print(f"\n  Best balanced (lift × caught):")
results.sort(key=lambda x: -(x[3] * x[7]))
if results:
    row = results[0]
    print(f"    2-tier: b={row[0]} short={row[1]} long={row[2]}  =>  {row[3]}/{row[4]} mb={row[6]:.1f} lift={row[7]:.1f}x")

results_3.sort(key=lambda x: -(x[5] * x[9]))
if results_3:
    row = results_3[0]
    print(f"    3-tier: S<{row[0]} L>={row[1]} [{row[2]}/{row[3]}/{row[4]}]  =>  {row[5]}/{row[6]} mb={row[8]:.1f} lift={row[9]:.1f}x")

print(f"\nDone!", flush=True)
