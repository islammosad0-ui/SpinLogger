"""
Re-run triple clustering analysis.
- Exclude coin and goldSack (non-actionable triples)
- Only count: attack, steal, shield, spins as "other triples"
- Show the 31/178 breakdown clearly
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
REAL_SYMBOLS = {"attack", "steal", "shield", "spins"}  # exclude coin, goldSack

print("=" * 70)
print("TRIPLE CLUSTERING (real symbols only: attack/steal/shield/spins)")
print(f"Zone: sa_spins >= {SPIN_THRESH} AND rate >= {RATE_GATE}")
print("=" * 70)

all_other_triples_in_zone = []
all_acc_triples = []
all_zone_lengths = []

for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    gap_num = 0
    in_zone = False
    zone_spins = 0
    other_triples_this_zone = []

    for row in rows:
        sa = int(row["sa_spins"])
        sa_acc = int(row["sa_acc"])
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        rate = sa_acc / sa if sa > 0 else 0.0

        is_triple = (r1 == r2 == r3)
        is_acc_triple = is_triple and r1 == "accumulation"
        is_real_other = is_triple and (not is_acc_triple) and (r1 in REAL_SYMBOLS)

        should_bet = (sa >= SPIN_THRESH) and (rate >= RATE_GATE)

        if should_bet and not in_zone:
            in_zone = True
            zone_spins = 0
            other_triples_this_zone = []

        if in_zone:
            zone_spins += 1

            if is_real_other:
                other_triples_this_zone.append((r1, zone_spins))

            if is_acc_triple:
                gap_num += 1
                had_other = len(other_triples_this_zone) > 0
                spins_since_last_other = zone_spins
                if had_other:
                    last_other_spin = other_triples_this_zone[-1][1]
                    spins_since_last_other = zone_spins - last_other_spin

                all_acc_triples.append((label, gap_num, sa, had_other, spins_since_last_other, zone_spins))
                all_zone_lengths.append(zone_spins)

                for sym, spin_in_zone in other_triples_this_zone:
                    spins_before_acc = zone_spins - spin_in_zone
                    all_other_triples_in_zone.append((label, gap_num, sym, spin_in_zone, spins_before_acc))

                in_zone = False

        if not should_bet:
            in_zone = False

print(f"\nACC triples caught in BET NOW: {len(all_acc_triples)}")
print(f"Real other triples in BET NOW zones: {len(all_other_triples_in_zone)}")

zones_with_others = sum(1 for _, _, _, had, _, _ in all_acc_triples if had)
print(f"Zones with >= 1 real other triple: {zones_with_others}/{len(all_acc_triples)} ({zones_with_others/len(all_acc_triples)*100:.0f}%)")

print(f"\n--- Other triple types in BET NOW zone ---")
sym_counts = defaultdict(int)
for _, _, sym, _, _ in all_other_triples_in_zone:
    sym_counts[sym] += 1
for sym, count in sorted(sym_counts.items(), key=lambda x: -x[1]):
    print(f"  {sym}: {count}")

print(f"\n--- Spins between last other triple and ACC triple ---")
distances = [spins_since for _, _, _, had, spins_since, _ in all_acc_triples if had]
if distances:
    print(f"  Count: {len(distances)}")
    print(f"  Mean: {sum(distances)/len(distances):.1f}")
    print(f"  Min: {min(distances)}, Max: {max(distances)}")
    for d in range(1, 11):
        c = sum(1 for x in distances if x == d)
        if c > 0:
            bar = "#" * c
            print(f"    {d:>2} spins: {c} ({c/len(distances)*100:.0f}%) {bar}")
    c = sum(1 for x in distances if x > 10)
    if c > 0:
        print(f"    >10 spins: {c} ({c/len(distances)*100:.0f}%)")

# === PULSE SIMULATION with real symbols only ===
print(f"\n{'='*70}")
print(f"PULSE: drop to 1x for N spins after real non-ACC triple")
print(f"{'='*70}")
print(f"{'Skip':>4} {'MAX spins':>10} {'1x spins':>9} {'Saved%':>7} {'Caught@MAX':>11} {'Lost@1x':>8} {'MB/hit':>7}")
print("-" * 65)

for skip in [0, 1, 2, 3, 4, 5]:
    total_max_bet = 0
    total_1x_bet = 0
    total_caught_max = 0
    total_caught_1x = 0
    total_acc = 0
    total_spins = 0

    for label, fp in files:
        rows = list(csv.DictReader(open(fp)))
        skip_remaining = 0

        for row in rows:
            sa = int(row["sa_spins"])
            sa_acc = int(row["sa_acc"])
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            rate = sa_acc / sa if sa > 0 else 0.0
            is_triple = (r1 == r2 == r3)
            is_acc_triple = is_triple and r1 == "accumulation"
            is_real_other = is_triple and (not is_acc_triple) and (r1 in REAL_SYMBOLS)

            total_spins += 1
            should_bet = (sa >= SPIN_THRESH) and (rate >= RATE_GATE)

            if should_bet:
                if skip_remaining > 0:
                    total_1x_bet += 1
                    skip_remaining -= 1
                    at_max = False
                else:
                    total_max_bet += 1
                    at_max = True

                if is_acc_triple:
                    total_acc += 1
                    if at_max:
                        total_caught_max += 1
                    else:
                        total_caught_1x += 1
                    skip_remaining = 0
                elif is_real_other and skip > 0:
                    skip_remaining = skip
            else:
                skip_remaining = 0
                if is_acc_triple:
                    total_acc += 1

    total_bet = total_max_bet + total_1x_bet
    saved_pct = total_1x_bet / total_bet * 100 if total_bet > 0 else 0
    mb = total_max_bet / total_caught_max if total_caught_max > 0 else 999
    label = "(no pulse)" if skip == 0 else ""
    print(f"  {skip:>2}   {total_max_bet:>10} {total_1x_bet:>9} {saved_pct:>6.1f}% {total_caught_max:>11} {total_caught_1x:>8} {mb:>6.1f}  {label}")

print(f"\nDone!", flush=True)
