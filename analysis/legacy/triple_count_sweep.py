"""
Sweep all 31 symbol combinations but count TRIPLES only.
BET when: count_of_triples_from_combo >= threshold

E.g., if combo = {attack, steal}, count how many triple-attacks
and triple-steals have occurred since last ACC triple.

Test for both ACC and SPN targets.
"""
import csv
from itertools import combinations

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

SYMBOLS = ["attack", "steal", "accumulation", "spins", "shield"]
# Also include the junk triples to be thorough
ALL_TRIPLE_TYPES = ["attack", "steal", "accumulation", "spins", "shield", "coin", "goldSack"]

# Preload
all_data = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    all_data.append((label, rows))


def run_triple_sweep(target_symbol, target_name):
    print(f"\n{'='*80}")
    print(f"TARGET: Triple {target_name}")
    print(f"BET when: count_of_combo_triples >= threshold")
    print(f"{'='*80}")

    # First: how many of each triple type between target triples?
    print(f"\n--- Triple counts between {target_name} triples ---")
    triple_counts = {s: [] for s in ALL_TRIPLE_TYPES}

    for label, rows in all_data:
        counts = {s: 0 for s in ALL_TRIPLE_TYPES}
        for row in rows:
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_triple = (r1 == r2 == r3)
            is_target = is_triple and r1 == target_symbol

            if is_triple and not is_target:
                if r1 in counts:
                    counts[r1] += 1

            if is_target:
                for s in ALL_TRIPLE_TYPES:
                    if s != target_symbol:
                        triple_counts[s].append(counts[s])
                counts = {s: 0 for s in ALL_TRIPLE_TYPES}

    print(f"  {'Symbol':<15} {'Mean':>5} {'Med':>4} {'Min':>4} {'Max':>4} {'P25':>4} {'P75':>4}")
    print(f"  {'-'*50}")
    for sym in ALL_TRIPLE_TYPES:
        if sym == target_symbol:
            continue
        vals = triple_counts[sym]
        if not vals:
            continue
        s = sorted(vals)
        n = len(s)
        mean = sum(s) / n
        print(f"  {sym:<15} {mean:>5.1f} {s[n//2]:>4} {s[0]:>4} {s[-1]:>4} {s[n//4]:>4} {s[3*n//4]:>4}")

    # Now sweep all 31 combos (of the 5 real symbols, excluding target)
    countable = [s for s in SYMBOLS if s != target_symbol]
    # Also add combos that include non-real types
    all_combos = []
    for r in range(1, len(countable) + 1):
        for combo in combinations(countable, r):
            all_combos.append(set(combo))

    # Also test: all triples (any type except target)
    all_combos.append(set(ALL_TRIPLE_TYPES) - {target_symbol})
    # And: all real triples except target
    all_combos.append(set(SYMBOLS) - {target_symbol})

    print(f"\n--- Best threshold per combo (maximize lift) ---")
    print(f"  {'Combo':<40} {'Thresh':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
    print(f"  {'-'*75}")

    best_results = []

    for combo_set in all_combos:
        name = "+".join(sorted(combo_set))

        # Find triple counts at target time for this combo
        counts_at_target = []
        for label, rows in all_data:
            combo_triples = 0
            for row in rows:
                r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
                is_triple = (r1 == r2 == r3)
                is_target = is_triple and r1 == target_symbol

                if is_triple and not is_target and r1 in combo_set:
                    combo_triples += 1

                if is_target:
                    counts_at_target.append(combo_triples)
                    combo_triples = 0

        if not counts_at_target:
            continue

        s = sorted(counts_at_target)
        mean = sum(s) / len(s)

        # Sweep thresholds
        best_lift = 0
        best_row = None

        for thresh in range(1, max(s) + 1):
            total_caught = 0
            total_bet = 0
            total_spins = 0
            total_targets = 0

            for label, rows in all_data:
                combo_triples = 0
                for row in rows:
                    r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
                    is_triple = (r1 == r2 == r3)
                    is_target = is_triple and r1 == target_symbol
                    total_spins += 1

                    if is_triple and not is_target and r1 in combo_set:
                        combo_triples += 1

                    should_bet = (combo_triples >= thresh)
                    if should_bet:
                        total_bet += 1

                    if is_target:
                        total_targets += 1
                        if should_bet:
                            total_caught += 1
                        combo_triples = 0

            if total_caught > 0 and total_bet > 0:
                mb = total_bet / total_caught
                bet_pct = total_bet / total_spins * 100
                lift = (total_caught / total_targets) / (total_bet / total_spins)
                if lift > best_lift:
                    best_lift = lift
                    best_row = (name, thresh, total_caught, total_targets, bet_pct, mb, lift)

        if best_row:
            best_results.append(best_row)
            n, th, c, t, bp, mb, lf = best_row
            print(f"  {n:<40} {th:>5} {c:>3}/{t:<4} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

    # Sort by lift
    best_results.sort(key=lambda x: -x[6])
    print(f"\n  TOP 10 by lift:")
    print(f"  {'Rank':>4} {'Combo':<40} {'Thresh':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
    print(f"  {'-'*80}")
    for rank, (name, thresh, caught, total, bet_pct, mb, lift) in enumerate(best_results[:10], 1):
        print(f"  {rank:>3}. {name:<40} {thresh:>5} {caught:>3}/{total:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")

    # Detailed sweep for top 3
    print(f"\n  Detailed sweep for top 3:")
    for name, best_thresh, _, _, _, _, _ in best_results[:3]:
        combo_set = set(name.split("+"))
        print(f"\n  {name} (best={best_thresh}):")
        print(f"  {'Thresh':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")

        for thresh in range(1, best_thresh + 8):
            total_caught = 0
            total_bet = 0
            total_spins = 0
            total_targets = 0

            for label, rows in all_data:
                combo_triples = 0
                for row in rows:
                    r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
                    is_triple = (r1 == r2 == r3)
                    is_target = is_triple and r1 == target_symbol
                    total_spins += 1
                    if is_triple and not is_target and r1 in combo_set:
                        combo_triples += 1
                    if combo_triples >= thresh:
                        total_bet += 1
                    if is_target:
                        total_targets += 1
                        if combo_triples >= thresh:
                            total_caught += 1
                        combo_triples = 0

            if total_caught > 0 and total_bet > 0:
                mb = total_bet / total_caught
                bet_pct = total_bet / total_spins * 100
                lift = (total_caught / total_targets) / (total_bet / total_spins)
                marker = " <--" if thresh == best_thresh else ""
                print(f"  {thresh:>6} {total_caught:>3}/{total_targets:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x{marker}")
            else:
                print(f"  {thresh:>6}   0 caught or 0 bet")

    # === COMBINED: triple count + spin count ===
    print(f"\n  === COMBINED: best triple combo + sa_spins >= 130 ===")
    if best_results:
        top_name, top_thresh = best_results[0][0], best_results[0][1]
        top_set = set(top_name.split("+"))

        # Also try lower thresholds combined with spin gate
        print(f"  {top_name} triples >= N AND sa_spins >= 130:")
        print(f"  {'T.Thresh':>8} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
        for tthresh in range(1, top_thresh + 5):
            total_caught = 0
            total_bet = 0
            total_spins = 0
            total_targets = 0

            for label, rows in all_data:
                combo_triples = 0
                my_spins = 0
                for row in rows:
                    r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
                    is_triple = (r1 == r2 == r3)
                    is_target = is_triple and r1 == target_symbol
                    total_spins += 1
                    my_spins += 1
                    if is_triple and not is_target and r1 in top_set:
                        combo_triples += 1
                    should_bet = (combo_triples >= tthresh) and (my_spins >= 130)
                    if should_bet:
                        total_bet += 1
                    if is_target:
                        total_targets += 1
                        if should_bet:
                            total_caught += 1
                        combo_triples = 0
                        my_spins = 0

            if total_caught > 0 and total_bet > 0:
                mb = total_bet / total_caught
                bet_pct = total_bet / total_spins * 100
                lift = (total_caught / total_targets) / (total_bet / total_spins)
                print(f"  {tthresh:>8} {total_caught:>3}/{total_targets:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")
            else:
                print(f"  {tthresh:>8}   0 caught or 0 bet")


run_triple_sweep("accumulation", "ACC")
run_triple_sweep("spins", "SPN")

print(f"\nDone!", flush=True)
