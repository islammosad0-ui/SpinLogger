"""Validate the 2D formula for SPN (triple spins) using sa_spins and sa_spn columns."""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

# First: extract SPN gaps and rates at triple time
print("=== SPN Gap Analysis ===")
all_gaps = []
all_rates = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    gaps = []
    rates = []
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        if r1 == r2 == r3 == "spins":
            sa = int(row["sa_spins"])
            sa_spn = int(row["sa_spn"])
            rate = sa_spn / sa if sa > 0 else 0
            gaps.append(sa)
            rates.append(rate)
    n = len(gaps)
    if n > 0:
        avg = sum(gaps) / n
        avg_rate = sum(rates) / n
        print(f"{label}: {n} SPN gaps, mean_gap={avg:.1f}, mean_rate={avg_rate:.3f}, min={min(gaps)}, max={max(gaps)}")
        all_gaps.extend(gaps)
        all_rates.extend(rates)

print(f"\nTotal: {len(all_gaps)} SPN gaps, mean={sum(all_gaps)/len(all_gaps):.1f}")
print(f"Rate at triple: mean={sum(all_rates)/len(all_rates):.3f}, min={min(all_rates):.3f}, max={max(all_rates):.3f}")

# Rate distribution at triple time
print(f"\n=== Rate distribution at SPN triple ===")
brackets = [0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 1.0]
for i in range(len(brackets)-1):
    lo, hi = brackets[i], brackets[i+1]
    count = sum(1 for r in all_rates if lo <= r < hi)
    print(f"  [{lo:.2f}, {hi:.2f}): {count} ({count/len(all_rates)*100:.1f}%)")

# Test various thresholds
print(f"\n=== Strategy sweep (all 3 accounts combined) ===")
print(f"{'Config':<40} {'Caught':>7} {'Total':>6} {'Bet%':>6} {'MB/H':>6} {'Lift':>5}")
print("-" * 75)

configs = [
    ("Spin-only (>=87)",              87, 0.0),
    ("Spin-only (>=80)",              80, 0.0),
    ("Spin-only (>=70)",              70, 0.0),
    ("Spin+Rate (>=87, rate>=0.20)",  87, 0.20),
    ("Spin+Rate (>=87, rate>=0.25)",  87, 0.25),
    ("Spin+Rate (>=87, rate>=0.30)",  87, 0.30),
    ("Spin+Rate (>=80, rate>=0.20)",  80, 0.20),
    ("Spin+Rate (>=80, rate>=0.25)",  80, 0.25),
    ("Spin+Rate (>=80, rate>=0.30)",  80, 0.30),
    ("Spin+Rate (>=70, rate>=0.20)",  70, 0.20),
    ("Spin+Rate (>=70, rate>=0.25)",  70, 0.25),
    ("Spin+Rate (>=70, rate>=0.30)",  70, 0.30),
    ("Spin+Rate (>=60, rate>=0.25)",  60, 0.25),
    ("Spin+Rate (>=60, rate>=0.30)",  60, 0.30),
]

for name, spin_thresh, rate_gate in configs:
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_spn_triples = 0

    for label, fp in files:
        rows = list(csv.DictReader(open(fp)))
        for row in rows:
            sa = int(row["sa_spins"])
            sa_spn = int(row["sa_spn"])
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_spn = (r1 == r2 == r3 == "spins")
            rate = sa_spn / sa if sa > 0 else 0.0

            total_spins += 1

            should_bet = (sa >= spin_thresh)
            if rate_gate > 0.0 and rate < rate_gate:
                should_bet = False

            if should_bet:
                total_bet += 1

            if is_spn:
                total_spn_triples += 1
                if should_bet:
                    total_caught += 1

    if total_caught > 0 and total_bet > 0:
        mb = total_bet / total_caught
        lift = (total_caught / total_spn_triples) / (total_bet / total_spins)
        bet_pct = total_bet / total_spins * 100
        print(f"{name:<40} {total_caught:>3}/{total_spn_triples:<3} {total_spn_triples:>6} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")
    else:
        print(f"{name:<40} {total_caught:>3}/{total_spn_triples:<3} {total_spn_triples:>6}   0 bet")

print(f"\nDone!", flush=True)
