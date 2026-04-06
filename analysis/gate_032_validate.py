"""
Proper row-by-row simulation of gate=0.32 vs 0.30 on all data.
No precomputation tricks — uses game's sa_spins and sa_acc directly.
"""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

all_data = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    all_data.append((label, rows))


def simulate(start, stop, gate, label):
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    per_acct = []

    for acct_label, rows in all_data:
        a_caught = 0
        a_bet = 0
        a_spins = 0
        a_acc = 0

        for row in rows:
            sa = int(row["sa_spins"])
            sa_acc = int(row["sa_acc"])
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_acc = (r1 == r2 == r3 == "accumulation")
            rate = sa_acc / sa if sa > 0 else 0.0

            a_spins += 1
            should_bet = (sa >= start) and (sa <= stop) and (rate >= gate)

            if should_bet:
                a_bet += 1

            if is_acc:
                a_acc += 1
                if should_bet:
                    a_caught += 1

        per_acct.append((acct_label, a_caught, a_acc, a_bet, a_spins))
        total_caught += a_caught
        total_bet += a_bet
        total_spins += a_spins
        total_acc += a_acc

    if total_caught > 0 and total_bet > 0:
        mb = total_bet / total_caught
        bet_pct = total_bet / total_spins * 100
        lift = (total_caught / total_acc) / (total_bet / total_spins)
        return (label, total_caught, total_acc, bet_pct, mb, lift, per_acct)
    return (label, total_caught, total_acc, 0, 999, 0, per_acct)


INF = 999999

# ================================================================
print("=" * 90)
print("FULL VALIDATION: gate=0.30 vs 0.32 vs 0.28 vs 0.25")
print("Proper row-by-row simulation using game's sa_spins and sa_acc")
print("=" * 90)

# ================================================================
# PART 1: Sweep start thresholds at each gate
# ================================================================
print(f"\n--- PART 1: Start threshold sweep (no stop cap) ---")
print(f"  {'Gate':>5} {'Start':>6} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}   Per-account")
print(f"  {'-'*85}")

for gate in [0.25, 0.28, 0.30, 0.32, 0.34, 0.35]:
    for start in range(40, 171, 10):
        r = simulate(start, INF, gate, "")
        if r[1] > 0:
            label, caught, total, bet_pct, mb, lift, per = r
            acct_str = "  ".join(f"{a}:{c}/{t}" for a, c, t, _, _ in per)
            print(f"  {gate:>5.2f} {start:>6} {caught:>3}/{total:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x   {acct_str}")
    print()

# ================================================================
# PART 2: Window sweep at each gate
# ================================================================
print(f"\n--- PART 2: Window sweep (start + stop cap) ---")
print(f"  {'Gate':>5} {'Window':>12} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*55}")

for gate in [0.25, 0.28, 0.30, 0.32, 0.34, 0.35]:
    best_lift = 0
    best_caught = 0
    results = []
    for start in range(40, 171, 5):
        for stop in list(range(start + 20, 301, 10)) + [INF]:
            r = simulate(start, stop, gate, "")
            if r[1] >= 3:
                label, caught, total, bet_pct, mb, lift, per = r
                results.append((start, stop, caught, total, bet_pct, mb, lift))

    # Pareto frontier for this gate
    results.sort(key=lambda x: (-x[2], x[5]))  # more caught, lower mb
    pareto = []
    best_mb = float('inf')
    for row in results:
        if row[5] < best_mb:
            pareto.append(row)
            best_mb = row[5]

    print(f"\n  Gate = {gate:.2f} — Pareto frontier:")
    for start, stop, caught, total, bet_pct, mb, lift in pareto[:20]:
        stop_s = "INF" if stop >= INF else str(stop)
        win = f"{start}-{stop_s}"
        print(f"  {gate:>5.2f} {win:>12} {caught:>3}/{total:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")

# ================================================================
# PART 3: Head-to-head comparison of key configs
# ================================================================
print(f"\n{'='*90}")
print(f"PART 3: HEAD-TO-HEAD — key configs compared")
print(f"{'='*90}")
print(f"  {'Config':<40} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}   {'Acct2':>8} {'Acct3':>8} {'Acct4':>8}")
print(f"  {'-'*100}")

configs = [
    # (start, stop, gate, label)
    (130, INF, 0.30, "CURRENT: 130+/0.30"),
    (130, 170, 0.30, "130-170/0.30 (capped)"),
    (130, 180, 0.30, "130-180/0.30"),
    (130, INF, 0.32, "130+/0.32"),
    (130, 170, 0.32, "130-170/0.32"),
    (130, 180, 0.32, "130-180/0.32"),
    (120, INF, 0.30, "120+/0.30"),
    (120, INF, 0.32, "120+/0.32"),
    (120, 170, 0.32, "120-170/0.32"),
    (110, INF, 0.32, "110+/0.32"),
    (110, 170, 0.32, "110-170/0.32"),
    (100, INF, 0.32, "100+/0.32"),
    (100, 160, 0.32, "100-160/0.32"),
    (90, INF, 0.32, "90+/0.32"),
    (80, INF, 0.32, "80+/0.32"),
    (70, INF, 0.32, "70+/0.32"),
    (60, INF, 0.32, "60+/0.32"),
    (50, INF, 0.32, "50+/0.32"),
    (40, INF, 0.32, "40+/0.32"),
    (130, INF, 0.28, "130+/0.28"),
    (130, INF, 0.25, "130+/0.25"),
    (130, INF, 0.34, "130+/0.34"),
    (130, INF, 0.35, "130+/0.35"),
    (100, INF, 0.34, "100+/0.34"),
    (80, INF, 0.34, "80+/0.34"),
    (60, INF, 0.34, "60+/0.34"),
    (50, INF, 0.34, "50+/0.34"),
    (40, INF, 0.34, "40+/0.34"),
    (100, INF, 0.35, "100+/0.35"),
    (80, INF, 0.35, "80+/0.35"),
    (60, INF, 0.35, "60+/0.35"),
    (50, INF, 0.35, "50+/0.35"),
    (40, INF, 0.35, "40+/0.35"),
]

for start, stop, gate, label in configs:
    r = simulate(start, stop, gate, label)
    _, caught, total, bet_pct, mb, lift, per = r
    acct_parts = "  ".join(f"{c}/{t}" for _, c, t, _, _ in per)
    if caught > 0:
        print(f"  {label:<40} {caught:>3}/{total:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x   {acct_parts}")
    else:
        print(f"  {label:<40}   0/{total:<4}     no catches")


# ================================================================
# PART 4: Fine-grained gate sweep around 0.30-0.35
# ================================================================
print(f"\n{'='*90}")
print(f"PART 4: Fine-grained gate sweep (0.28-0.36, step 0.01)")
print(f"{'='*90}")
print(f"  {'Start':>6} {'Gate':>5} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*45}")

for start in [40, 60, 80, 100, 120, 130]:
    for gate_100 in range(28, 37):
        gate = gate_100 / 100.0
        r = simulate(start, INF, gate, "")
        if r[1] > 0:
            _, caught, total, bet_pct, mb, lift, _ = r
            print(f"  {start:>6} {gate:>5.2f} {caught:>3}/{total:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")
    print()


# ================================================================
# PART 5: Best configs at each catch level
# ================================================================
print(f"\n{'='*90}")
print(f"PART 5: BEST CONFIG AT EACH CATCH LEVEL")
print(f"What's the lowest mb/hit possible for each # of catches?")
print(f"{'='*90}")

all_results = []
for gate_100 in range(25, 37):
    gate = gate_100 / 100.0
    for start in range(40, 171, 5):
        for stop in list(range(start + 20, 251, 10)) + [INF]:
            r = simulate(start, stop, gate, "")
            if r[1] >= 3:
                _, caught, total, bet_pct, mb, lift, _ = r
                all_results.append((start, stop, gate, caught, total, bet_pct, mb, lift))

# Group by caught count, find lowest mb for each
from collections import defaultdict
by_caught = defaultdict(list)
for r in all_results:
    by_caught[r[3]].append(r)

print(f"  {'Caught':>7} {'Config':>25} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*55}")

for caught in sorted(by_caught.keys(), reverse=True):
    if caught < 5:
        continue
    configs = by_caught[caught]
    configs.sort(key=lambda x: x[6])  # lowest mb
    best = configs[0]
    start, stop, gate, c, t, bp, mb, lf = best
    stop_s = "INF" if stop >= INF else str(stop)
    config = f"{start}-{stop_s}/g={gate:.2f}"
    print(f"  {caught:>3}/{t:<4} {config:>25} {bp:>5.1f}% {mb:>5.1f} {lf:>5.1f}x")

print(f"\nDone!", flush=True)
