"""
Analyze: when we're in BET NOW zone for ACC, do other triples cluster?
If so, can we pulse (drop to 1x for 3-5 spins after a non-ACC triple)?

Questions:
1. How many non-ACC triples land inside the BET NOW window?
2. How many spins between a non-ACC triple and the ACC triple that follows?
3. If we skip 3-5 spins after each non-ACC triple, do we still catch ACC?
"""
import csv
from collections import defaultdict

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

SPIN_THRESH = 130
RATE_GATE = 0.30

# Track everything that happens inside BET NOW windows
print("=" * 70)
print("TRIPLE CLUSTERING INSIDE BET NOW ZONE")
print(f"Zone: sa_spins >= {SPIN_THRESH} AND rate >= {RATE_GATE}")
print("=" * 70)

all_other_triples_in_zone = []  # (account, gap#, symbol, spins_into_zone, spins_before_acc)
all_acc_triples = []  # (account, gap#, sa_spins, had_other_triple_in_zone, spins_since_last_other)
all_zone_lengths = []  # how many spins we're in BET NOW before ACC hits

for label, fp in files:
    rows = list(csv.DictReader(open(fp)))

    gap_num = 0
    in_zone = False
    zone_start_spin = 0
    zone_spins = 0
    other_triples_this_zone = []  # (symbol, spin_number_in_zone)

    for row in rows:
        sa = int(row["sa_spins"])
        sa_acc = int(row["sa_acc"])
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        rate = sa_acc / sa if sa > 0 else 0.0

        is_triple = (r1 == r2 == r3)
        is_acc_triple = is_triple and r1 == "accumulation"
        triple_type = r1 if is_triple else None

        should_bet = (sa >= SPIN_THRESH) and (rate >= RATE_GATE)

        if should_bet and not in_zone:
            in_zone = True
            zone_start_spin = sa
            zone_spins = 0
            other_triples_this_zone = []

        if in_zone:
            zone_spins += 1

            if is_triple and not is_acc_triple:
                other_triples_this_zone.append((triple_type, zone_spins))

            if is_acc_triple:
                gap_num += 1

                # Record what happened in this zone
                spins_since_last_other = zone_spins
                had_other = len(other_triples_this_zone) > 0
                if had_other:
                    last_other_spin = other_triples_this_zone[-1][1]
                    spins_since_last_other = zone_spins - last_other_spin

                all_acc_triples.append((label, gap_num, sa, had_other, spins_since_last_other, zone_spins))
                all_zone_lengths.append(zone_spins)

                for sym, spin_in_zone in other_triples_this_zone:
                    spins_before_acc = zone_spins - spin_in_zone
                    all_other_triples_in_zone.append((label, gap_num, sym, spin_in_zone, spins_before_acc))

                in_zone = False
                other_triples_this_zone = []

        if not should_bet:
            in_zone = False

# === Report ===
print(f"\nTotal ACC triples caught in BET NOW: {len(all_acc_triples)}")
print(f"Total other triples in BET NOW zones: {len(all_other_triples_in_zone)}")

# How many zones had other triples?
zones_with_others = sum(1 for _, _, _, had, _, _ in all_acc_triples if had)
print(f"\nBET NOW zones with >= 1 other triple: {zones_with_others}/{len(all_acc_triples)} ({zones_with_others/len(all_acc_triples)*100:.0f}%)")

# What symbols appear as triples in the zone?
print(f"\n--- Other triple types in BET NOW zone ---")
sym_counts = defaultdict(int)
for _, _, sym, _, _ in all_other_triples_in_zone:
    sym_counts[sym] += 1
for sym, count in sorted(sym_counts.items(), key=lambda x: -x[1]):
    print(f"  {sym}: {count}")

# Distance from other triple to ACC triple
print(f"\n--- Spins between last other triple and ACC triple ---")
distances = [spins_since for _, _, _, had, spins_since, _ in all_acc_triples if had]
if distances:
    print(f"  Count: {len(distances)}")
    print(f"  Mean: {sum(distances)/len(distances):.1f}")
    print(f"  Min: {min(distances)}, Max: {max(distances)}")
    print(f"  Distribution:")
    for d in range(1, 16):
        c = sum(1 for x in distances if x == d)
        if c > 0:
            print(f"    {d} spins: {c} ({c/len(distances)*100:.0f}%)")
    c = sum(1 for x in distances if x > 15)
    if c > 0:
        print(f"    >15 spins: {c} ({c/len(distances)*100:.0f}%)")

# Zone lengths (how long we bet before ACC hits)
print(f"\n--- BET NOW zone length (spins until ACC) ---")
if all_zone_lengths:
    print(f"  Mean: {sum(all_zone_lengths)/len(all_zone_lengths):.1f}")
    print(f"  Median: {sorted(all_zone_lengths)[len(all_zone_lengths)//2]}")
    print(f"  Min: {min(all_zone_lengths)}, Max: {max(all_zone_lengths)}")

# === PULSE SIMULATION ===
# After a non-ACC triple in BET NOW, drop to 1x for N spins, then resume MAX
print(f"\n{'='*70}")
print(f"PULSE SIMULATION: drop to 1x for N spins after non-ACC triple")
print(f"{'='*70}")

for skip in [1, 2, 3, 4, 5]:
    # Re-simulate
    total_max_bet = 0
    total_1x_bet = 0
    total_caught_at_max = 0
    total_caught_at_1x = 0
    total_caught = 0
    total_spins = 0
    total_acc = 0

    for label, fp in files:
        rows = list(csv.DictReader(open(fp)))
        skip_remaining = 0  # spins left at 1x after non-ACC triple

        for row in rows:
            sa = int(row["sa_spins"])
            sa_acc = int(row["sa_acc"])
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            rate = sa_acc / sa if sa > 0 else 0.0
            is_triple = (r1 == r2 == r3)
            is_acc_triple = is_triple and r1 == "accumulation"

            total_spins += 1
            should_bet = (sa >= SPIN_THRESH) and (rate >= RATE_GATE)

            if should_bet:
                if skip_remaining > 0:
                    total_1x_bet += 1
                    skip_remaining -= 1
                    bet_level = "1x"
                else:
                    total_max_bet += 1
                    bet_level = "MAX"

                if is_acc_triple:
                    total_acc += 1
                    total_caught += 1
                    if bet_level == "MAX":
                        total_caught_at_max += 1
                    else:
                        total_caught_at_1x += 1
                    skip_remaining = 0  # reset on ACC triple
                elif is_triple:
                    # Non-ACC triple in zone: start skip
                    skip_remaining = skip
            else:
                skip_remaining = 0
                if is_acc_triple:
                    total_acc += 1

    total_bet = total_max_bet + total_1x_bet
    saved = total_1x_bet  # spins saved from MAX
    pct_saved = saved / total_bet * 100 if total_bet > 0 else 0
    print(f"\n  Skip {skip} after non-ACC triple:")
    print(f"    MAX bet spins: {total_max_bet}, 1x spins: {total_1x_bet} (saved {pct_saved:.1f}% of bet spins)")
    print(f"    Caught at MAX: {total_caught_at_max}, at 1x: {total_caught_at_1x}, missed: {total_acc - total_caught}")
    if total_caught_at_1x > 0:
        print(f"    WARNING: {total_caught_at_1x} ACC triples would land during 1x skip!")
    mb_max = total_max_bet / total_caught_at_max if total_caught_at_max > 0 else 999
    print(f"    Effective MB/hit (MAX only): {mb_max:.1f}")

print(f"\n--- Comparison: no pulse ---")
print(f"  All {len(all_acc_triples)} caught at MAX, zone avg {sum(all_zone_lengths)/len(all_zone_lengths):.1f} spins")

print(f"\nDone!", flush=True)
