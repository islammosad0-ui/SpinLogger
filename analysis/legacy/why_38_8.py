"""
Why do 27/31 combos give EXACTLY 58/178, 12.3%, 38.8 mb/hit?

Hypothesis: the rate gate does NOTHING for those symbols because their
rate is ALWAYS >= 0.30 when sa_spins >= 130. So they're all equivalent
to spin-count-only betting.

Let's prove it by checking the actual rate of each symbol at sa_spins >= 130.
"""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

SYMBOLS = ["attack", "steal", "accumulation", "spins", "shield"]

# For each symbol, track what its rate looks like when sa_spins >= 130
print("=" * 70)
print("SYMBOL RATES WHEN sa_spins >= 130")
print("If rate is ALWAYS >= 0.30, the gate does nothing -> spin-only")
print("=" * 70)

for sym in SYMBOLS:
    rates_at_130 = []
    min_rate = 999
    max_rate = 0
    below_030_count = 0
    total_at_130 = 0

    for label, fp in files:
        rows = list(csv.DictReader(open(fp)))
        my_spins = 0
        my_symbols = 0

        for row in rows:
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_acc_triple = (r1 == r2 == r3 == "accumulation")

            my_spins += 1
            for reel in [r1, r2, r3]:
                if reel == sym:
                    my_symbols += 1

            if my_spins >= 130:
                rate = my_symbols / my_spins
                total_at_130 += 1
                rates_at_130.append(rate)
                if rate < min_rate: min_rate = rate
                if rate > max_rate: max_rate = rate
                if rate < 0.30: below_030_count += 1

            if is_acc_triple:
                my_spins = 0
                my_symbols = 0

    avg_rate = sum(rates_at_130) / len(rates_at_130) if rates_at_130 else 0
    print(f"\n  {sym}:")
    print(f"    Spins at 130+: {total_at_130}")
    print(f"    Rate: min={min_rate:.3f}  avg={avg_rate:.3f}  max={max_rate:.3f}")
    print(f"    Below 0.30: {below_030_count}/{total_at_130} ({below_030_count/total_at_130*100:.1f}%)")
    if below_030_count == 0:
        print(f"    --> GATE IS USELESS: rate NEVER drops below 0.30")
    else:
        print(f"    --> Gate filters {below_030_count} spins ({below_030_count/total_at_130*100:.1f}%)")

# Now verify: is 58/178 exactly what spin-count-only (>=130) gives?
print(f"\n{'='*70}")
print(f"PROOF: spin-count-only (>=130, no rate gate)")
print(f"{'='*70}")

total_caught = 0
total_bet = 0
total_spins = 0
total_acc = 0

for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    my_spins = 0

    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        is_acc_triple = (r1 == r2 == r3 == "accumulation")

        my_spins += 1
        total_spins += 1

        should_bet = (my_spins >= 130)
        if should_bet:
            total_bet += 1

        if is_acc_triple:
            total_acc += 1
            if should_bet:
                total_caught += 1
            my_spins = 0

mb = total_bet / total_caught if total_caught > 0 else 999
bet_pct = total_bet / total_spins * 100
lift = (total_caught / total_acc) / (total_bet / total_spins)
print(f"  Caught: {total_caught}/{total_acc}, Bet: {bet_pct:.1f}%, MB/Hit: {mb:.1f}, Lift: {lift:.1f}x")
print(f"  --> {'MATCHES 58/178!' if total_caught == 58 else 'Different!'}")

# What makes accumulation special?
print(f"\n{'='*70}")
print(f"WHY ACCUMULATION IS SPECIAL")
print(f"{'='*70}")
print(f"\nRate distribution of each symbol at spins 130-200:")

for sym in SYMBOLS:
    rates = []
    for label, fp in files:
        rows = list(csv.DictReader(open(fp)))
        my_spins = 0
        my_symbols = 0
        for row in rows:
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_acc_triple = (r1 == r2 == r3 == "accumulation")
            my_spins += 1
            for reel in [r1, r2, r3]:
                if reel == sym:
                    my_symbols += 1
            if 130 <= my_spins <= 200:
                rates.append(my_symbols / my_spins)
            if is_acc_triple:
                my_spins = 0
                my_symbols = 0

    if not rates:
        continue

    # Bucket the rates
    buckets = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]
    print(f"\n  {sym}:")
    for i in range(len(buckets) - 1):
        lo, hi = buckets[i], buckets[i+1]
        c = sum(1 for r in rates if lo <= r < hi)
        bar = "#" * (c // 2)
        print(f"    [{lo:.2f}-{hi:.2f}): {c:>4} ({c/len(rates)*100:>5.1f}%) {bar}")

print(f"\nDone!", flush=True)
