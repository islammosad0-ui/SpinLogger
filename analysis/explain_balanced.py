"""
Show exactly how the balanced formula works, gap by gap.
BET when: sa_spins >= 130 AND (sa_acc / sa_spins) >= 0.30
"""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

SPIN_THRESH = 130
RATE_GATE = 0.30

print("HOW THE FORMULA WORKS")
print("=" * 70)
print(f"BET when: sa_spins >= {SPIN_THRESH} AND (sa_acc / sa_spins) >= {RATE_GATE}")
print()
print("sa_spins = spins since your last triple accumulation (30,30,30)")
print("sa_acc   = accumulation symbols seen on ANY reel since last triple")
print("rate     = sa_acc / sa_spins (what fraction of reels showed accum)")
print()
print("The game has a pity timer that kicks in around spin 123.")
print("BUT it also needs to have shown enough accum symbols first.")
print("When rate < 0.30 = game is starving accum symbols = triple NOT ready.")
print("When rate >= 0.30 AND spins >= 130 = triple is primed = BET NOW.")
print()

grand_total_acc = 0
grand_caught = 0
grand_bet = 0
grand_spins = 0

for label, fp in files:
    rows = list(csv.DictReader(open(fp)))

    print(f"\n{'='*70}")
    print(f"  {label} ({len(rows)} spins)")
    print(f"{'='*70}")
    print(f"  {'#':>3} {'Gap':>5} {'sa_acc':>6} {'Rate':>6} {'Spins>=130':>10} {'Rate>=0.30':>10} {'BET?':>5} {'Bet spins':>9} {'Result':>8}")
    print(f"  {'-'*3} {'-'*5} {'-'*6} {'-'*6} {'-'*10} {'-'*10} {'-'*5} {'-'*9} {'-'*8}")

    gap_num = 0
    total_acc = 0
    caught = 0
    bet_spins = 0
    total_spins = 0

    # Track per-gap betting
    current_gap_bet = 0
    current_gap_started_betting = None

    for row in rows:
        sa = int(row["sa_spins"])
        sa_acc_val = int(row["sa_acc"])
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        is_acc = (r1 == r2 == r3 == "accumulation")
        rate = sa_acc_val / sa if sa > 0 else 0.0

        total_spins += 1

        cond_spin = sa >= SPIN_THRESH
        cond_rate = rate >= RATE_GATE
        should_bet = cond_spin and cond_rate

        if should_bet:
            bet_spins += 1
            current_gap_bet += 1
            if current_gap_started_betting is None:
                current_gap_started_betting = sa

        if is_acc:
            total_acc += 1
            gap_num += 1
            was_caught = should_bet

            if was_caught:
                caught += 1
                result = "CAUGHT"
            elif sa < SPIN_THRESH:
                result = "too early"
            elif rate < RATE_GATE:
                result = "low rate"
            else:
                result = "missed"

            spin_ok = "YES" if sa >= SPIN_THRESH else "no"
            rate_ok = "YES" if rate >= RATE_GATE else "no"
            bet_str = "BET" if was_caught else "-"

            print(f"  {gap_num:>3} {sa:>5} {sa_acc_val:>6} {rate:>6.3f} {spin_ok:>10} {rate_ok:>10} {bet_str:>5} {current_gap_bet:>9} {result:>8}")

            current_gap_bet = 0
            current_gap_started_betting = None

    mb = bet_spins / caught if caught > 0 else 999
    lift = (caught / total_acc) / (bet_spins / total_spins) if bet_spins > 0 else 0
    print(f"\n  Summary: {caught}/{total_acc} caught, {bet_spins}/{total_spins} bet ({bet_spins/total_spins*100:.1f}%), {mb:.1f} mb/hit, {lift:.1f}x lift")

    grand_total_acc += total_acc
    grand_caught += caught
    grand_bet += bet_spins
    grand_spins += total_spins

print(f"\n{'='*70}")
print(f"  GRAND TOTAL")
print(f"{'='*70}")
mb = grand_bet / grand_caught if grand_caught > 0 else 999
lift = (grand_caught / grand_total_acc) / (grand_bet / grand_spins) if grand_bet > 0 else 0
print(f"  {grand_caught}/{grand_total_acc} caught, {grand_bet}/{grand_spins} bet ({grand_bet/grand_spins*100:.1f}%), {mb:.1f} mb/hit, {lift:.1f}x lift")
print(f"\n  You bet on {grand_bet/grand_spins*100:.1f}% of spins")
print(f"  You catch {grand_caught/grand_total_acc*100:.1f}% of all triples")
print(f"  Every {mb:.0f} bet-spins you get a triple (random would be ~{grand_spins/grand_total_acc:.0f})")
print(f"  That's {lift:.1f}x more efficient than random betting")

print(f"\nDone!", flush=True)
