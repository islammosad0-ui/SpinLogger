"""
Sweep all 31 symbol combos using PURE COUNT (not rate).
BET when: combo_symbol_count >= threshold (no sa_spins condition)

This tests whether the pity timer fires at a fixed symbol count
rather than a rate. If "40 accumulation symbols" is the trigger,
this will find it.

Also test for both ACC triples and SPN triples as targets.
"""
import csv
from itertools import combinations

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

SYMBOLS = ["attack", "steal", "accumulation", "spins", "shield"]

# Preload
all_data = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    all_data.append((label, rows))

all_combos = []
for r in range(1, len(SYMBOLS) + 1):
    for combo in combinations(SYMBOLS, r):
        all_combos.append(set(combo))


def run_sweep(target_symbol, target_name):
    """Sweep all combos and thresholds for a given target triple."""
    print(f"\n{'='*80}")
    print(f"TARGET: Triple {target_name} ({target_symbol},{target_symbol},{target_symbol})")
    print(f"BET when: combo_count >= threshold (pure count, no spin condition)")
    print(f"{'='*80}")

    # First: find what counts look like at triple time for each combo
    print(f"\n--- Symbol counts AT {target_name} triple time ---")
    print(f"{'Combo':<40} {'Mean':>6} {'Med':>5} {'Min':>5} {'Max':>5} {'P25':>5} {'P75':>5} {'N':>4}")
    print("-" * 80)

    combo_stats = {}
    for combo_set in all_combos:
        counts_at_triple = []
        for label, rows in all_data:
            my_count = 0
            for row in rows:
                r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
                is_target = (r1 == r2 == r3 == target_symbol)
                for reel in [r1, r2, r3]:
                    if reel in combo_set:
                        my_count += 1
                if is_target:
                    counts_at_triple.append(my_count)
                    my_count = 0

        name = "+".join(sorted(combo_set))
        if counts_at_triple:
            s = sorted(counts_at_triple)
            n = len(s)
            mean = sum(s) / n
            med = s[n // 2]
            p25 = s[n // 4]
            p75 = s[3 * n // 4]
            combo_stats[name] = (mean, med, min(s), max(s), p25, p75, n, s)
            print(f"  {name:<40} {mean:>5.1f} {med:>5} {min(s):>5} {max(s):>5} {p25:>5} {p75:>5} {n:>4}")

    # Now sweep thresholds for each combo
    print(f"\n--- Best threshold per combo (maximize lift) ---")
    print(f"{'Combo':<35} {'Thresh':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
    print("-" * 75)

    best_results = []

    for combo_set in all_combos:
        name = "+".join(sorted(combo_set))
        if name not in combo_stats:
            continue

        mean, med, mn, mx, p25, p75, n, sorted_counts = combo_stats[name]

        # Test thresholds around the distribution
        best_lift = 0
        best_row = None

        # Generate thresholds: from p25 down to a reasonable range
        thresholds = set()
        for pct in [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]:
            thresholds.add(int(mean * pct))
        thresholds.update(range(max(1, mn), int(mean * 1.1) + 1, max(1, (mx - mn) // 20)))
        thresholds = sorted(thresholds)

        for thresh in thresholds:
            if thresh < 1:
                continue
            total_caught = 0
            total_bet = 0
            total_spins = 0
            total_targets = 0

            for label, rows in all_data:
                my_count = 0
                for row in rows:
                    r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
                    is_target = (r1 == r2 == r3 == target_symbol)
                    total_spins += 1
                    for reel in [r1, r2, r3]:
                        if reel in combo_set:
                            my_count += 1
                    should_bet = (my_count >= thresh)
                    if should_bet:
                        total_bet += 1
                    if is_target:
                        total_targets += 1
                        if should_bet:
                            total_caught += 1
                        my_count = 0

            if total_caught > 0 and total_bet > 0:
                mb = total_bet / total_caught
                bet_pct = total_bet / total_spins * 100
                lift = (total_caught / total_targets) / (total_bet / total_spins)
                if lift > best_lift:
                    best_lift = lift
                    best_row = (name, thresh, total_caught, total_targets, bet_pct, mb, lift)

        if best_row:
            name, thresh, caught, total, bet_pct, mb, lift = best_row
            best_results.append(best_row)
            print(f"  {name:<35} {thresh:>5} {caught:>3}/{total:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")

    # Sort by lift
    best_results.sort(key=lambda x: -x[6])
    print(f"\n--- TOP 10 by lift ---")
    print(f"{'Rank':>4} {'Combo':<35} {'Thresh':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
    print("-" * 80)
    for rank, (name, thresh, caught, total, bet_pct, mb, lift) in enumerate(best_results[:10], 1):
        print(f"  {rank:>2}. {name:<35} {thresh:>5} {caught:>3}/{total:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")

    # Detailed threshold sweep for top 3
    print(f"\n--- Detailed sweep for top 3 ---")
    top3 = best_results[:3]
    for name, best_thresh, _, _, _, _, _ in top3:
        combo_set = set(name.split("+"))
        print(f"\n  {name} (best={best_thresh}):")
        print(f"  {'Thresh':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")

        mean = combo_stats[name][0]
        for thresh in sorted(set(range(max(1, int(mean * 0.5)), int(mean * 1.15) + 1, max(1, int(mean * 0.05))))):
            total_caught = 0
            total_bet = 0
            total_spins = 0
            total_targets = 0

            for label, rows in all_data:
                my_count = 0
                for row in rows:
                    r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
                    is_target = (r1 == r2 == r3 == target_symbol)
                    total_spins += 1
                    for reel in [r1, r2, r3]:
                        if reel in combo_set:
                            my_count += 1
                    if my_count >= thresh:
                        total_bet += 1
                    if is_target:
                        total_targets += 1
                        if my_count >= thresh:
                            total_caught += 1
                        my_count = 0

            if total_caught > 0 and total_bet > 0:
                mb = total_bet / total_caught
                bet_pct = total_bet / total_spins * 100
                lift = (total_caught / total_targets) / (total_bet / total_spins)
                marker = " <-- best" if thresh == best_thresh else ""
                print(f"  {thresh:>6} {total_caught:>3}/{total_targets:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x{marker}")


# Run for ACC triples
run_sweep("accumulation", "ACC")

# Run for SPN triples
run_sweep("spins", "SPN")

print(f"\nDone!", flush=True)
