"""
Sweep all 31 symbol combinations for the rate gate.
Instead of counting only 'accumulation' symbols for the rate,
test every combo of {attack, steal, accumulation, spins, shield}.

For each combo: rate = (count of combo symbols on 3 reels) / sa_spins
BET when: sa_spins >= 130 AND rate >= 0.30

Test on ACC triples across all 3 accounts.
"""
import csv
from itertools import combinations

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

SYMBOLS = ["attack", "steal", "accumulation", "spins", "shield"]
SPIN_THRESH = 130
RATE_GATE = 0.30

# Preload all rows
all_data = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    all_data.append((label, rows))

# Generate all 31 combinations (1-symbol through 5-symbol)
all_combos = []
for r in range(1, len(SYMBOLS) + 1):
    for combo in combinations(SYMBOLS, r):
        all_combos.append(set(combo))

print(f"Testing {len(all_combos)} symbol combinations")
print(f"Formula: sa_spins >= {SPIN_THRESH} AND (combo_count / sa_spins) >= {RATE_GATE}")
print(f"Target: ACC triples (reel_1 == reel_2 == reel_3 == 'accumulation')")
print()

results = []

for combo_set in all_combos:
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    for label, rows in all_data:
        # We need to track our OWN running counters since sa_acc only tracks accumulation
        my_spins = 0  # spins since last ACC triple
        my_symbols = 0  # combo symbols since last ACC triple

        for row in rows:
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_acc_triple = (r1 == r2 == r3 == "accumulation")

            my_spins += 1
            total_spins += 1

            # Count how many of the 3 reels show a combo symbol
            for reel in [r1, r2, r3]:
                if reel in combo_set:
                    my_symbols += 1

            rate = my_symbols / my_spins if my_spins > 0 else 0.0
            should_bet = (my_spins >= SPIN_THRESH) and (rate >= RATE_GATE)

            if should_bet:
                total_bet += 1

            if is_acc_triple:
                total_acc += 1
                if should_bet:
                    total_caught += 1
                # Reset counters on ACC triple
                my_spins = 0
                my_symbols = 0

    combo_name = "+".join(sorted(combo_set))
    n_syms = len(combo_set)

    if total_caught > 0 and total_bet > 0:
        mb = total_bet / total_caught
        bet_pct = total_bet / total_spins * 100
        catch_pct = total_caught / total_acc * 100
        lift = (total_caught / total_acc) / (total_bet / total_spins)
        results.append((lift, combo_name, n_syms, total_caught, total_acc, bet_pct, mb, catch_pct))
    else:
        results.append((0, combo_name, n_syms, total_caught, total_acc, 0, 999, 0))

# Sort by lift descending
results.sort(key=lambda x: -x[0])

print(f"{'Rank':>4} {'Symbols':>3} {'Combination':<45} {'Caught':>8} {'Bet%':>6} {'Catch%':>7} {'MB/Hit':>7} {'Lift':>6}")
print("-" * 95)

for rank, (lift, name, n_syms, caught, total, bet_pct, mb, catch_pct) in enumerate(results, 1):
    if lift > 0:
        print(f"{rank:>4} {n_syms:>3}    {name:<45} {caught:>3}/{total:<4} {bet_pct:>5.1f}% {catch_pct:>6.1f}% {mb:>6.1f} {lift:>5.1f}x")
    else:
        print(f"{rank:>4} {n_syms:>3}    {name:<45} {caught:>3}/{total:<4}     0 bet")

# Highlight: top 5 and our current formula
print(f"\n{'='*95}")
print(f"TOP 5:")
for rank, (lift, name, n_syms, caught, total, bet_pct, mb, catch_pct) in enumerate(results[:5], 1):
    print(f"  {rank}. {name} -> {lift:.1f}x lift, {caught}/{total} caught, {bet_pct:.1f}% bet, {mb:.1f} mb/hit")

# Find our current formula (accumulation only)
for lift, name, n_syms, caught, total, bet_pct, mb, catch_pct in results:
    if name == "accumulation":
        print(f"\n  Current (accumulation only) -> {lift:.1f}x lift, {caught}/{total} caught, {bet_pct:.1f}% bet, {mb:.1f} mb/hit")
        break

# === Now also sweep different rate gates for top combos ===
print(f"\n{'='*95}")
print(f"RATE GATE SWEEP for top 5 combos")
print(f"{'='*95}")

top5_combos = [set(name.split("+")) for _, name, *_ in results[:5]]

for combo_set in top5_combos:
    combo_name = "+".join(sorted(combo_set))
    print(f"\n--- {combo_name} ---")
    print(f"  {'Gate':>5} {'Caught':>8} {'Bet%':>6} {'MB/Hit':>7} {'Lift':>6}")

    for gate in [0.15, 0.20, 0.25, 0.28, 0.30, 0.32, 0.35, 0.40]:
        total_caught = 0
        total_bet = 0
        total_spins = 0
        total_acc = 0

        for label, rows in all_data:
            my_spins = 0
            my_symbols = 0

            for row in rows:
                r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
                is_acc_triple = (r1 == r2 == r3 == "accumulation")

                my_spins += 1
                total_spins += 1

                for reel in [r1, r2, r3]:
                    if reel in combo_set:
                        my_symbols += 1

                rate = my_symbols / my_spins if my_spins > 0 else 0.0
                should_bet = (my_spins >= SPIN_THRESH) and (rate >= gate)

                if should_bet:
                    total_bet += 1

                if is_acc_triple:
                    total_acc += 1
                    if should_bet:
                        total_caught += 1
                    my_spins = 0
                    my_symbols = 0

        if total_caught > 0 and total_bet > 0:
            mb = total_bet / total_caught
            bet_pct = total_bet / total_spins * 100
            lift = (total_caught / total_acc) / (total_bet / total_spins)
            print(f"  {gate:>5.2f} {total_caught:>3}/{total_acc:<4} {bet_pct:>5.1f}% {mb:>6.1f} {lift:>5.1f}x")
        else:
            print(f"  {gate:>5.2f}   0/{total_acc:<4}     0 bet")

# === Also test with the game's own sa_acc column as baseline ===
print(f"\n{'='*95}")
print(f"COMPARISON: game's sa_acc column vs our manual count")
print(f"{'='*95}")

for method_name, use_sa in [("game sa_acc", True), ("manual acc count", False)]:
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    for label, rows in all_data:
        my_spins = 0
        my_symbols = 0

        for row in rows:
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_acc_triple = (r1 == r2 == r3 == "accumulation")

            if use_sa:
                # Use game's counters
                sa = int(row["sa_spins"])
                sa_acc = int(row["sa_acc"])
                rate = sa_acc / sa if sa > 0 else 0.0
                should_bet = (sa >= SPIN_THRESH) and (rate >= RATE_GATE)
            else:
                my_spins += 1
                for reel in [r1, r2, r3]:
                    if reel == "accumulation":
                        my_symbols += 1
                rate = my_symbols / my_spins if my_spins > 0 else 0.0
                should_bet = (my_spins >= SPIN_THRESH) and (rate >= RATE_GATE)

            total_spins += 1

            if should_bet:
                total_bet += 1

            if is_acc_triple:
                total_acc += 1
                if should_bet:
                    total_caught += 1
                if not use_sa:
                    my_spins = 0
                    my_symbols = 0

    if total_caught > 0 and total_bet > 0:
        mb = total_bet / total_caught
        bet_pct = total_bet / total_spins * 100
        lift = (total_caught / total_acc) / (total_bet / total_spins)
        print(f"  {method_name:<20} {total_caught:>3}/{total_acc:<4} {bet_pct:>5.1f}% {mb:>6.1f} {lift:>5.1f}x")

print(f"\nDone!", flush=True)
