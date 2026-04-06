"""
Sweep S/M/L boundary definitions to find optimal cutpoints.
Faster version: precompute gaps, sweep smarter.
"""
import csv
from collections import Counter

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

REAL_TRIPLES = {"attack", "steal", "shield", "spins"}

# Preload — store only what we need: (sa_spins, sa_acc, is_acc, is_other_triple)
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
        is_other = (r1 == r2 == r3) and r1 in REAL_TRIPLES
        compact.append((sa, sa_acc, is_acc, is_other))
        if is_acc:
            all_gaps.append(sa)
    all_data.append(compact)

# Gap distribution
all_gaps_sorted = sorted(all_gaps)
n = len(all_gaps_sorted)
print("=" * 70)
print("GAP DISTRIBUTION")
print("=" * 70)
print(f"  N={n}, Mean={sum(all_gaps)/n:.1f}, Median={all_gaps_sorted[n//2]}")
print(f"  P10={all_gaps_sorted[n//10]}, P25={all_gaps_sorted[n//4]}, P50={all_gaps_sorted[n//2]}, P75={all_gaps_sorted[3*n//4]}, P90={all_gaps_sorted[9*n//10]}")
print(f"  Min={all_gaps_sorted[0]}, Max={all_gaps_sorted[-1]}")

print(f"\n  Histogram (10-spin buckets):")
for lo in range(0, 301, 10):
    hi = lo + 10
    c = sum(1 for g in all_gaps if lo <= g < hi)
    bar = "#" * c
    if c > 0:
        print(f"    {lo:>3}-{hi:<3}: {c:>3} ({c/n*100:>4.1f}%) {bar}")


def simulate_sml(s_cut, l_cut, s_thresh, m_thresh, l_thresh):
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    for rows in all_data:
        prev_gap = -1  # -1 = no previous

        for sa, sa_acc, is_acc, is_other in rows:
            rate = sa_acc / sa if sa > 0 else 0.0
            total_spins += 1

            if prev_gap < 0:
                thresh = m_thresh
            elif prev_gap < s_cut:
                thresh = s_thresh
            elif prev_gap >= l_cut:
                thresh = l_thresh
            else:
                thresh = m_thresh

            should_bet = (sa >= thresh) and (rate >= 0.30)
            if should_bet:
                total_bet += 1

            if is_acc:
                total_acc += 1
                if should_bet:
                    total_caught += 1
                prev_gap = sa

    if total_caught > 0 and total_bet > 0:
        mb = total_bet / total_caught
        lift = (total_caught / total_acc) / (total_bet / total_spins)
        bet_pct = total_bet / total_spins * 100
        return (total_caught, total_acc, bet_pct, mb, lift)
    return None


# Sweep boundaries + thresholds
print(f"\n{'='*70}")
print(f"SWEEPING S/M/L BOUNDARIES + THRESHOLDS")
print(f"{'='*70}")

results = []

for s_cut in range(50, 121, 10):
    for l_cut in range(s_cut + 20, 181, 10):
        best = None
        best_lift = 0

        for s_thresh in range(120, 171, 10):
            for m_thresh in range(110, 151, 10):
                for l_thresh in range(80, 141, 10):
                    r = simulate_sml(s_cut, l_cut, s_thresh, m_thresh, l_thresh)
                    if r and r[4] > best_lift:
                        best_lift = r[4]
                        best = (s_cut, l_cut, s_thresh, m_thresh, l_thresh, *r)

        if best:
            results.append(best)

results.sort(key=lambda x: -x[9])  # sort by lift

print(f"\n  TOP 20 by lift:")
print(f"  {'S<':>4} {'L>=':>4} {'S->':>4} {'M->':>4} {'L->':>4} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*58}")
for row in results[:20]:
    s_cut, l_cut, st, mt, lt, caught, total, bet_pct, mb, lift = row
    print(f"  {s_cut:>4} {l_cut:>4} {st:>4} {mt:>4} {lt:>4} {caught:>3}/{total:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")

# Also show: at each lift level, which catches the most?
print(f"\n  TOP 10 by CAUGHT (among those with lift >= 6.0x):")
good = [r for r in results if r[9] >= 6.0]
good.sort(key=lambda x: -x[5])  # sort by caught
print(f"  {'S<':>4} {'L>=':>4} {'S->':>4} {'M->':>4} {'L->':>4} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*58}")
for row in good[:10]:
    s_cut, l_cut, st, mt, lt, caught, total, bet_pct, mb, lift = row
    print(f"  {s_cut:>4} {l_cut:>4} {st:>4} {mt:>4} {lt:>4} {caught:>3}/{total:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")


# Transition matrices for top boundary choices
print(f"\n{'='*70}")
print(f"TRANSITION MATRICES")
print(f"{'='*70}")

# Get unique boundary pairs from top 10
seen_boundaries = set()
for row in results[:10]:
    seen_boundaries.add((row[0], row[1]))

# Also add common ones
seen_boundaries.update([(80, 130), (70, 130), (60, 140), (80, 140)])

for s_cut, l_cut in sorted(seen_boundaries):
    sizes = []
    for g in all_gaps:
        if g < s_cut:
            sizes.append("S")
        elif g >= l_cut:
            sizes.append("L")
        else:
            sizes.append("M")

    s_count = sizes.count("S")
    m_count = sizes.count("M")
    l_count = sizes.count("L")

    print(f"\n  S<{s_cut}, M={s_cut}-{l_cut-1}, L>={l_cut}  |  S={s_count}({s_count/n*100:.0f}%) M={m_count}({m_count/n*100:.0f}%) L={l_count}({l_count/n*100:.0f}%)")

    transitions = Counter()
    for i in range(1, len(sizes)):
        transitions[(sizes[i-1], sizes[i])] += 1

    for prev in ["S", "M", "L"]:
        total_t = sum(transitions[(prev, nxt)] for nxt in ["S", "M", "L"])
        if total_t > 0:
            parts = []
            for nxt in ["S", "M", "L"]:
                c = transitions[(prev, nxt)]
                parts.append(f"{nxt}:{c}({c/total_t*100:.0f}%)")
            print(f"    After {prev} -> {', '.join(parts)}")

print(f"\nDone!", flush=True)
