"""Check the new third account file and validate our formula against it."""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

# Check for overlaps first
print("=== File comparison ===")
all_rows = {}
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    all_rows[label] = rows
    reels = [(r["reel_1"], r["reel_2"], r["reel_3"]) for r in rows]
    print(f"{label}: {len(rows)} rows")
    print(f"  First 3: {reels[:3]}")
    print(f"  Last 3: {reels[-3:]}")

# Check overlap between Acct4 and others
acct4_reels = [(r["reel_1"], r["reel_2"], r["reel_3"]) for r in all_rows["Acct4"]]
for other in ["Acct2", "Acct3"]:
    other_reels = [(r["reel_1"], r["reel_2"], r["reel_3"]) for r in all_rows[other]]
    r4_first50 = acct4_reels[:50]
    found = False
    for offset in range(len(other_reels) - 50):
        if other_reels[offset:offset+50] == r4_first50:
            print(f"\n  WARNING: Acct4[0:50] matches {other}[{offset}:{offset+50}]!")
            found = True
            break
    if not found:
        print(f"\n  Acct4 vs {other}: NO overlap -- genuinely different account")

# Extract gaps using sa_spins
print(f"\n=== Gap extraction ===")
for label, fp in files:
    rows = all_rows[label]
    gaps = []
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        if r1 == r2 == r3 == "accumulation":
            gaps.append(int(row["sa_spins"]))
    n = len(gaps)
    if n > 0:
        avg = sum(gaps) / n
        cv = (sum((g - avg)**2 for g in gaps) / n) ** 0.5 / avg
        print(f"{label}: {n} ACC gaps, mean={avg:.1f}, max={max(gaps)}, min={min(gaps)}, CV={cv:.3f}")
        print(f"  First 10 gaps: {gaps[:10]}")
    else:
        print(f"{label}: 0 ACC gaps")

# Now validate our formula on Acct4
print(f"\n=== Formula validation on Acct4 ===")
rows = all_rows["Acct4"]
total_acc = 0
total_spins = 0

# Strategy configs to test
configs = [
    ("Spin-only (>=130)", 130, 0.0, None),
    ("Conservative (>=120, rate>=0.28)", 120, 0.0, 0.28),
    ("Balanced (>=130, rate>=0.30)", 130, 0.0, 0.30),
    ("Aggressive (>=130, rate>=0.32)", 130, 0.0, 0.32),
    ("Balanced (>=120, rate>=0.30)", 120, 0.0, 0.30),
]

for name, spin_thresh, shift, gate in configs:
    caught = 0
    bet_spins = 0
    total_spins = 0
    total_acc = 0
    prev_gap = 100

    for row in rows:
        sa = int(row["sa_spins"])
        sa_acc = int(row["sa_acc"])
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        is_acc = (r1 == r2 == r3 == "accumulation")
        acc_rate = sa_acc / sa if sa > 0 else 0.3

        total_spins += 1
        threshold = spin_thresh - shift * (prev_gap - 100)

        should_bet = (sa >= threshold)
        if gate is not None and acc_rate < gate:
            should_bet = False

        if should_bet:
            bet_spins += 1

        if is_acc:
            total_acc += 1
            if should_bet:
                caught += 1
            prev_gap = sa

    if caught > 0 and bet_spins > 0:
        mb = bet_spins / caught
        lift = (caught / total_acc) / (bet_spins / total_spins)
        print(f"  {name}: {caught}/{total_acc} caught, {bet_spins/total_spins*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")
    else:
        print(f"  {name}: {caught}/{total_acc} caught, {bet_spins} bet spins")

# Also test with debt shift
print(f"\n=== With debt shift on Acct4 ===")
for name, base, shift, gate in [
    ("Shift (142/0.35, rate>=0.30)", 142, 0.35, 0.30),
    ("Shift (140/0.30, rate>=0.28)", 140, 0.30, 0.28),
    ("Shift (140/0.30, rate>=0.30)", 140, 0.30, 0.30),
]:
    caught = 0
    bet_spins = 0
    total_spins = 0
    total_acc = 0
    prev_gap = 100

    for row in rows:
        sa = int(row["sa_spins"])
        sa_acc = int(row["sa_acc"])
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        is_acc = (r1 == r2 == r3 == "accumulation")
        acc_rate = sa_acc / sa if sa > 0 else 0.3

        total_spins += 1
        threshold = base - shift * (prev_gap - 100)

        should_bet = (sa >= threshold)
        if gate is not None and acc_rate < gate:
            should_bet = False

        if should_bet:
            bet_spins += 1

        if is_acc:
            total_acc += 1
            if should_bet:
                caught += 1
            prev_gap = sa

    if caught > 0 and bet_spins > 0:
        mb = bet_spins / caught
        lift = (caught / total_acc) / (bet_spins / total_spins)
        print(f"  {name}: {caught}/{total_acc} caught, {bet_spins/total_spins*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")
    else:
        print(f"  {name}: {caught}/{total_acc} caught, {bet_spins} bet spins")

# Now ALL 3 unique accounts combined
print(f"\n=== ALL 3 accounts combined ===")
all_unique_files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

for name, spin_thresh, shift, gate in [
    ("Conservative (>=120, rate>=0.28)", 120, 0.0, 0.28),
    ("Balanced (>=130, rate>=0.30)", 130, 0.0, 0.30),
    ("Aggressive (>=130, rate>=0.32)", 130, 0.0, 0.32),
    ("Shift (142/0.35, rate>=0.30)", 142, 0.35, 0.30),
]:
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    for label, fp in all_unique_files:
        rows = list(csv.DictReader(open(fp)))
        prev_gap = 100
        for row in rows:
            sa = int(row["sa_spins"])
            sa_acc = int(row["sa_acc"])
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_acc = (r1 == r2 == r3 == "accumulation")
            acc_rate = sa_acc / sa if sa > 0 else 0.3

            total_spins += 1
            threshold = spin_thresh - shift * (prev_gap - 100) if shift > 0 else spin_thresh

            should_bet = (sa >= threshold)
            if gate is not None and acc_rate < gate:
                should_bet = False

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
        print(f"  {name}: {total_caught}/{total_acc} caught, {total_bet/total_spins*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

print(f"\nDone!", flush=True)
