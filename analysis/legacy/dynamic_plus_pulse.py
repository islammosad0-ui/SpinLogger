"""
Test top dynamic threshold strategies WITH pulse skip 5.
Compare mb/hit against the current best (11.4 with fixed 130 + pulse 5).
"""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

REAL_TRIPLES = {"attack", "steal", "shield", "spins"}

all_data = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    all_data.append((label, rows))


def simulate_with_pulse(threshold_fn, pulse_skip, label):
    """
    threshold_fn(prev_gaps, sa_spins, rate) -> spin threshold for this cycle
    pulse_skip: number of spins to drop to 1x after non-target triple in BET zone
    """
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    for acct_label, rows in all_data:
        prev_gaps = []
        pulse_remaining = 0

        for row in rows:
            sa = int(row["sa_spins"])
            sa_acc = int(row["sa_acc"])
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_acc = (r1 == r2 == r3 == "accumulation")
            is_other_triple = (r1 == r2 == r3) and r1 in REAL_TRIPLES
            rate = sa_acc / sa if sa > 0 else 0.0

            total_spins += 1

            # Get dynamic threshold
            thresh = threshold_fn(prev_gaps, sa, rate)

            # Base condition
            base_bet = (sa >= thresh) and (rate >= 0.30)

            # Pulse skip: if in pulse cooldown, don't bet
            if pulse_remaining > 0:
                pulse_remaining -= 1
                should_bet = False
            else:
                should_bet = base_bet

            # Trigger pulse on other triple while in bet zone
            if is_other_triple and base_bet and pulse_skip > 0:
                pulse_remaining = pulse_skip

            if should_bet:
                total_bet += 1

            if is_acc:
                total_acc += 1
                if should_bet:
                    total_caught += 1
                prev_gaps.append(sa)
                pulse_remaining = 0  # reset pulse on target hit

    if total_caught > 0 and total_bet > 0:
        mb = total_bet / total_caught
        bet_pct = total_bet / total_spins * 100
        lift = (total_caught / total_acc) / (total_bet / total_spins)
        print(f"  {label:<50} {total_caught:>3}/{total_acc:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")
    else:
        print(f"  {label:<50} {total_caught:>3}/{total_acc:<4}   0 bet")

    return total_caught, total_acc, total_bet, total_spins


print("=" * 85)
print("DYNAMIC THRESHOLD + PULSE SKIP COMBINATIONS")
print("=" * 85)

for pulse in [0, 5]:
    print(f"\n--- Pulse Skip = {pulse} ---")
    print(f"  {'Strategy':<50} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
    print(f"  {'-'*78}")

    # 1. Baseline fixed 130
    simulate_with_pulse(
        lambda pg, sa, r: 130,
        pulse, f"Fixed 130 (baseline)")

    # 2. Shift base=140 shift=0.2
    def make_shift(base, shift):
        def fn(pg, sa, r):
            prev = pg[-1] if pg else 100
            return max(50, base - shift * (prev - 100))
        return fn
    simulate_with_pulse(make_shift(140, 0.2), pulse, "Shift base=140 shift=0.2")
    simulate_with_pulse(make_shift(140, 0.3), pulse, "Shift base=140 shift=0.3")
    simulate_with_pulse(make_shift(150, 0.2), pulse, "Shift base=150 shift=0.2")
    simulate_with_pulse(make_shift(130, 0.2), pulse, "Shift base=130 shift=0.2")

    # 3. S/M/L patterns
    def make_sml(st, mt, lt):
        def fn(pg, sa, r):
            if not pg:
                return mt
            elif pg[-1] < 80:
                return st
            elif pg[-1] <= 130:
                return mt
            else:
                return lt
        return fn
    simulate_with_pulse(make_sml(150, 140, 100), pulse, "S/M/L 150/140/100")
    simulate_with_pulse(make_sml(150, 130, 100), pulse, "S/M/L 150/130/100")
    simulate_with_pulse(make_sml(140, 130, 110), pulse, "S/M/L 140/130/110")
    simulate_with_pulse(make_sml(160, 130, 90), pulse, "S/M/L 160/130/90")

    # 4. Streak detection
    def make_streak(streak_len, short_adj, long_adj):
        def fn(pg, sa, r):
            thresh = 130
            if len(pg) >= streak_len:
                recent = pg[-streak_len:]
                if all(g < 80 for g in recent):
                    thresh += short_adj
                elif all(g > 130 for g in recent):
                    thresh += long_adj
            return thresh
        return fn
    simulate_with_pulse(make_streak(2, 20, -20), pulse, "Streak>=2 short+20 long-20")
    simulate_with_pulse(make_streak(2, 30, -30), pulse, "Streak>=2 short+30 long-30")

    # 5. Debt-based
    def make_debt(base, center, factor):
        def fn(pg, sa, r):
            debt = sum(g - center for g in pg)
            return max(50, int(base - debt * factor))
        return fn
    simulate_with_pulse(make_debt(130, 100, 0.1), pulse, "Debt base=130 center=100 f=0.1")
    simulate_with_pulse(make_debt(140, 100, 0.1), pulse, "Debt base=140 center=100 f=0.1")

    # 6. EWMA
    def make_ewma(alpha, mult):
        def fn(pg, sa, r):
            if not pg:
                return 130
            ewma = pg[0]
            for g in pg[1:]:
                ewma = alpha * g + (1 - alpha) * ewma
            return max(50, int(ewma * mult))
        return fn
    simulate_with_pulse(make_ewma(0.3, 1.0), pulse, "EWMA alpha=0.3 mult=1.0")
    simulate_with_pulse(make_ewma(0.3, 1.1), pulse, "EWMA alpha=0.3 mult=1.1")

print(f"\nDone!", flush=True)
