"""
MEGA SWEEP v2 — optimized with precomputation.

Instead of running simulate() for each config, precompute per-gap data
and do fast array operations.
"""
import csv
import sys

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

# Preload: for each spin, store (sa_spins, rate, is_acc, gap_id)
# gap_id groups spins into the gap they belong to
all_spins = []  # (sa, rate, is_acc, gap_id)
gap_lengths = []  # length of each gap (sa_spins at triple time)
gap_ids = []  # gap_id for each gap

gap_id_counter = 0
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    for row in rows:
        sa = int(row["sa_spins"])
        sa_acc = int(row["sa_acc"])
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        is_acc = (r1 == r2 == r3 == "accumulation")
        rate = sa_acc / sa if sa > 0 else 0.0
        all_spins.append((sa, rate, is_acc, gap_id_counter))
        if is_acc:
            gap_lengths.append(sa)
            gap_ids.append(gap_id_counter)
            gap_id_counter += 1

TOTAL_SPINS = len(all_spins)
N_GAPS = len(gap_lengths)
print(f"Data: {N_GAPS} gaps, {TOTAL_SPINS} spins", flush=True)
print(f"Gaps: mean={sum(gap_lengths)/N_GAPS:.0f}, med={sorted(gap_lengths)[N_GAPS//2]}, min={min(gap_lengths)}, max={max(gap_lengths)}", flush=True)

# For each gap, precompute: at which sa_spins values was rate >= each gate?
# This lets us quickly compute "caught" for any (start, stop, gate) config.

# For each gap_id, find the earliest sa_spins where rate >= gate (for each gate)
# and store the gap_length and prev_gap_length.

GATES = [0.25, 0.28, 0.30, 0.32]

# gap_info[i] = (gap_length, prev_gap_length, {gate: earliest_sa_where_rate_met})
gap_info = []
prev_length = -1

for i, (gid, glen) in enumerate(zip(gap_ids, gap_lengths)):
    # Find earliest sa where rate >= gate for this gap
    earliest = {}
    for gate in GATES:
        earliest[gate] = 9999  # never met

    for sa, rate, is_acc, spin_gid in all_spins:
        if spin_gid != gid:
            continue
        for gate in GATES:
            if rate >= gate and sa < earliest[gate]:
                earliest[gate] = sa

    gap_info.append((glen, prev_length, earliest))
    prev_length = glen

# Also precompute: for any (start, stop, gate), how many total bet spins?
# This is harder — need to count per-spin. Let's precompute bet_spins for each gap.
# For gap i with (start, stop, gate): bet_spins = number of spins where start <= sa <= stop and rate >= gate

# Precompute per-gap: list of (sa, rate_meets_gate_at_each_level)
# Then for any (start, stop, gate): count spins in [start, stop] where rate is met.

# Faster approach: for each gap, store sorted list of sa values where rate >= gate
# Then bet_spins = count of sa in [start, stop] — use binary search

from bisect import bisect_left, bisect_right

gap_bet_spins = []  # gap_bet_spins[i][gate] = sorted list of sa values where rate >= gate
for gid in gap_ids:
    gate_sas = {g: [] for g in GATES}
    for sa, rate, is_acc, spin_gid in all_spins:
        if spin_gid != gid:
            continue
        for g in GATES:
            if rate >= g:
                gate_sas[g].append(sa)
    for g in GATES:
        gate_sas[g].sort()
    gap_bet_spins.append(gate_sas)

print(f"Precomputation done.", flush=True)


def fast_simulate_fixed(start, stop, gate):
    """Fast simulation for fixed window."""
    caught = 0
    total_bet = 0
    for i in range(N_GAPS):
        glen, prev, earliest = gap_info[i]
        sas = gap_bet_spins[i][gate]
        # Count spins in [start, stop]
        lo = bisect_left(sas, start)
        hi = bisect_right(sas, stop)
        bet = hi - lo
        total_bet += bet
        # Caught if rate met at triple time and glen in [start, stop]
        if start <= glen <= stop and earliest[gate] <= glen:
            caught += 1
    if caught > 0 and total_bet > 0:
        mb = total_bet / caught
        bet_pct = total_bet / TOTAL_SPINS * 100
        lift = (caught / N_GAPS) / (total_bet / TOTAL_SPINS)
        return (caught, N_GAPS, bet_pct, mb, lift)
    return None


def fast_simulate_2tier(boundary, gate, s_start, s_stop, l_start, l_stop):
    """Fast simulation for 2-tier windows."""
    caught = 0
    total_bet = 0
    for i in range(N_GAPS):
        glen, prev, earliest = gap_info[i]
        sas = gap_bet_spins[i][gate]

        # Determine window based on previous gap
        if prev < 0:
            start, stop = 130, 9999  # first cycle
        elif prev < boundary:
            start, stop = s_start, s_stop
        else:
            start, stop = l_start, l_stop

        if start >= 9999:  # SKIP
            continue

        # Count spins in [start, stop]
        lo = bisect_left(sas, start)
        hi = bisect_right(sas, stop)
        bet = hi - lo
        total_bet += bet

        # Caught?
        if start <= glen <= stop and earliest[gate] <= glen:
            caught += 1

    if caught > 0 and total_bet > 0:
        mb = total_bet / caught
        bet_pct = total_bet / TOTAL_SPINS * 100
        lift = (caught / N_GAPS) / (total_bet / TOTAL_SPINS)
        return (caught, N_GAPS, bet_pct, mb, lift)
    return None


# ================================================================
# PHASE 1: Fixed window sweep
# ================================================================
print(f"\n{'='*80}", flush=True)
print(f"PHASE 1: FIXED WINDOW SWEEP", flush=True)
print(f"{'='*80}", flush=True)

fixed_results = []
for start in range(40, 171, 5):
    for stop in list(range(start + 10, 301, 10)) + [9999]:
        for gate in GATES:
            r = fast_simulate_fixed(start, stop, gate)
            if r and r[0] >= 3:
                stop_s = "INF" if stop >= 9999 else stop
                fixed_results.append((start, stop_s, gate, *r))

# Pareto
fixed_results.sort(key=lambda x: (-x[3], x[6]))
pareto = []
best_mb = float('inf')
for r in fixed_results:
    if r[6] < best_mb:
        pareto.append(r)
        best_mb = r[6]

print(f"\n  PARETO FRONTIER:", flush=True)
print(f"  {'Start':>6} {'Stop':>6} {'Gate':>5} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}", flush=True)
print(f"  {'-'*50}", flush=True)
for r in pareto:
    print(f"  {r[0]:>6} {r[1]:>6} {r[2]:>5.2f} {r[3]:>3}/{r[4]:<4} {r[5]:>5.1f}% {r[6]:>5.1f} {r[7]:>5.1f}x", flush=True)

# Top by lift
fixed_results.sort(key=lambda x: -x[7])
print(f"\n  TOP 15 by LIFT:", flush=True)
print(f"  {'Start':>6} {'Stop':>6} {'Gate':>5} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*50}")
for r in fixed_results[:15]:
    print(f"  {r[0]:>6} {r[1]:>6} {r[2]:>5.2f} {r[3]:>3}/{r[4]:<4} {r[5]:>5.1f}% {r[6]:>5.1f} {r[7]:>5.1f}x")

# Top caught at lift >= 5
good = [r for r in fixed_results if r[7] >= 5.0]
good.sort(key=lambda x: -x[3])
print(f"\n  TOP 15 by CAUGHT (lift >= 5.0x):")
print(f"  {'Start':>6} {'Stop':>6} {'Gate':>5} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*50}")
for r in good[:15]:
    print(f"  {r[0]:>6} {r[1]:>6} {r[2]:>5.2f} {r[3]:>3}/{r[4]:<4} {r[5]:>5.1f}% {r[6]:>5.1f} {r[7]:>5.1f}x")

# Lowest mb >= 20 caught
good_mb = [r for r in fixed_results if r[3] >= 20]
good_mb.sort(key=lambda x: x[6])
print(f"\n  LOWEST MB/HIT (>= 20 caught):")
print(f"  {'Start':>6} {'Stop':>6} {'Gate':>5} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*50}")
for r in good_mb[:15]:
    print(f"  {r[0]:>6} {r[1]:>6} {r[2]:>5.2f} {r[3]:>3}/{r[4]:<4} {r[5]:>5.1f}% {r[6]:>5.1f} {r[7]:>5.1f}x")

sys.stdout.flush()

# ================================================================
# PHASE 2: Two-tier window sweep
# ================================================================
print(f"\n{'='*80}", flush=True)
print(f"PHASE 2: TWO-TIER WINDOWS", flush=True)
print(f"{'='*80}", flush=True)

SKIP = 9999
starts = [SKIP, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160]
stops = [80, 100, 120, 140, 160, 180, 200, 250, 9999]

two_results = []
count = 0

for boundary in [80, 90, 100, 110, 120]:
    for gate in GATES:
        for s_start in starts:
            for s_stop in stops:
                if s_start != SKIP and s_stop <= s_start:
                    continue
                for l_start in starts:
                    for l_stop in stops:
                        if l_start != SKIP and l_stop <= l_start:
                            continue

                        r = fast_simulate_2tier(boundary, gate, s_start, s_stop, l_start, l_stop)
                        count += 1
                        if r and r[0] >= 5:
                            caught, total, bet_pct, mb, lift = r
                            two_results.append((boundary, gate, s_start, s_stop, l_start, l_stop,
                                                caught, total, bet_pct, mb, lift))

    print(f"  boundary={boundary} done ({count} configs tested, {len(two_results)} viable)", flush=True)

def fmt(start, stop):
    if start == SKIP: return "SKIP"
    return f"{start}-{'INF' if stop >= 9999 else stop}"

# Pareto
two_results.sort(key=lambda x: (-x[6], x[9]))
pareto2 = []
best_mb = float('inf')
for r in two_results:
    if r[9] < best_mb:
        pareto2.append(r)
        best_mb = r[9]

print(f"\n  PARETO FRONTIER:", flush=True)
print(f"  {'B':>3} {'Gate':>5} {'After Short':>12} {'After Long':>12} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*68}")
for r in pareto2[:25]:
    b, g, ss, sst, ls, lst, c, t, bp, mb, lf = r
    print(f"  {b:>3} {g:>5.2f} {fmt(ss,sst):>12} {fmt(ls,lst):>12} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Top lift
two_results.sort(key=lambda x: -x[10])
print(f"\n  TOP 20 by LIFT:", flush=True)
print(f"  {'B':>3} {'Gate':>5} {'After Short':>12} {'After Long':>12} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*68}")
for r in two_results[:20]:
    b, g, ss, sst, ls, lst, c, t, bp, mb, lf = r
    print(f"  {b:>3} {g:>5.02f} {fmt(ss,sst):>12} {fmt(ls,lst):>12} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Top caught at lift >= 5
good2 = [r for r in two_results if r[10] >= 5.0]
good2.sort(key=lambda x: -x[6])
print(f"\n  TOP 20 by CAUGHT (lift >= 5.0x):", flush=True)
print(f"  {'B':>3} {'Gate':>5} {'After Short':>12} {'After Long':>12} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*68}")
for r in good2[:20]:
    b, g, ss, sst, ls, lst, c, t, bp, mb, lf = r
    print(f"  {b:>3} {g:>5.02f} {fmt(ss,sst):>12} {fmt(ls,lst):>12} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Lowest mb at >= 15 caught
good2mb = [r for r in two_results if r[6] >= 15]
good2mb.sort(key=lambda x: x[9])
print(f"\n  LOWEST MB/HIT (>= 15 caught):", flush=True)
print(f"  {'B':>3} {'Gate':>5} {'After Short':>12} {'After Long':>12} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*68}")
for r in good2mb[:20]:
    b, g, ss, sst, ls, lst, c, t, bp, mb, lf = r
    print(f"  {b:>3} {g:>5.02f} {fmt(ss,sst):>12} {fmt(ls,lst):>12} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Balanced
two_results.sort(key=lambda x: -(x[6] * x[10]))
print(f"\n  TOP 20 BALANCED (caught × lift):", flush=True)
print(f"  {'B':>3} {'Gate':>5} {'After Short':>12} {'After Long':>12} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*68}")
for r in two_results[:20]:
    b, g, ss, sst, ls, lst, c, t, bp, mb, lf = r
    print(f"  {b:>3} {g:>5.02f} {fmt(ss,sst):>12} {fmt(ls,lst):>12} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

# Best caught/mb ratio (most efficient)
two_results.sort(key=lambda x: x[6] / max(x[9], 0.1), reverse=True)
print(f"\n  TOP 20 EFFICIENCY (caught / mb):", flush=True)
print(f"  {'B':>3} {'Gate':>5} {'After Short':>12} {'After Long':>12} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*68}")
for r in two_results[:20]:
    b, g, ss, sst, ls, lst, c, t, bp, mb, lf = r
    print(f"  {b:>3} {g:>5.02f} {fmt(ss,sst):>12} {fmt(ls,lst):>12} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")


# ================================================================
# PHASE 3: Overall summary
# ================================================================
print(f"\n{'='*80}", flush=True)
print(f"FINAL COMPARISON", flush=True)
print(f"{'='*80}", flush=True)
print(f"  {'Strategy':<58} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*86}")

r = fast_simulate_fixed(130, 9999, 0.30)
if r:
    print(f"  {'CURRENT: 130+/0.30':<58} {r[0]:>3}/{r[1]:<4} {r[2]:>5.1f}% {r[3]:>5.1f} {r[4]:>5.1f}x")

# Best fixed pareto points
for label_suffix, sort_key in [("best lift", lambda x: -x[7]), ("most caught@5x+", lambda x: -x[3] if x[7] >= 5 else 0), ("lowest mb@20+", lambda x: x[6] if x[3] >= 20 else 999)]:
    fixed_results.sort(key=sort_key)
    r = fixed_results[0]
    label = f"Fixed {r[0]}-{r[1]}/g={r[2]} ({label_suffix})"
    print(f"  {label:<58} {r[3]:>3}/{r[4]:<4} {r[5]:>5.1f}% {r[6]:>5.1f} {r[7]:>5.1f}x")

# Best two-tier pareto points
for label_suffix, sort_key in [("best lift", lambda x: -x[10]), ("most caught@5x+", lambda x: -x[6] if x[10] >= 5 else 0), ("lowest mb@15+", lambda x: x[9] if x[6] >= 15 else 999), ("balanced", lambda x: -(x[6]*x[10]))]:
    two_results.sort(key=sort_key)
    r = two_results[0]
    label = f"2tier b={r[0]} S={fmt(r[2],r[3])} L={fmt(r[4],r[5])} g={r[1]} ({label_suffix})"
    print(f"  {label:<58} {r[6]:>3}/{r[7]:<4} {r[8]:>5.1f}% {r[9]:>5.1f} {r[10]:>5.1f}x")

print(f"\nDone! Tested {count} configs total.", flush=True)
