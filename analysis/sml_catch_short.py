"""
Can we CATCH short gaps by predicting them?

Current system: threshold=130, catches only long gaps (31/178).
Goal: predict when a short gap is coming, drop threshold to 40-70,
catch the short gap too. Risk: if prediction is wrong and gap goes
to 250, we waste 180+ max-bet spins.

Test: after Long gap (predict next is Short), drop threshold very low.
"""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

all_data = []
all_gaps = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    compact = []
    for row in rows:
        sa = int(row["sa_spins"])
        sa_acc = int(row["sa_acc"])
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        is_acc = (r1 == r2 == r3 == "accumulation")
        compact.append((sa, sa_acc, is_acc))
        if is_acc:
            all_gaps.append(sa)
    all_data.append(compact)

n = len(all_gaps)

# First: show what we're missing
print("=" * 70)
print("WHAT WE CURRENTLY MISS (flat 130 threshold)")
print("=" * 70)
missed = [g for g in all_gaps if g < 130]
caught = [g for g in all_gaps if g >= 130]
print(f"  Caught: {len(caught)}/178 (gaps >= 130)")
print(f"  Missed: {len(missed)}/178 (gaps < 130)")
print(f"  Missed distribution:")
for lo in range(0, 131, 20):
    hi = lo + 20
    c = sum(1 for g in missed if lo <= g < hi)
    if c > 0:
        print(f"    {lo:>3}-{hi:<3}: {c} gaps")

# After Long, what does the short gap actually look like?
print(f"\n{'='*70}")
print(f"AFTER LONG GAP: what's the next gap?")
print(f"{'='*70}")

for l_cut in [120, 130, 140, 150]:
    next_gaps = []
    for i in range(1, len(all_gaps)):
        if all_gaps[i-1] >= l_cut:
            next_gaps.append(all_gaps[i])

    if not next_gaps:
        continue

    s = sorted(next_gaps)
    nn = len(s)
    short = sum(1 for g in next_gaps if g < 80)
    med = sum(1 for g in next_gaps if 80 <= g < 130)
    long_ = sum(1 for g in next_gaps if g >= 130)

    print(f"\n  After gap >= {l_cut} (N={nn}):")
    print(f"    <80: {short} ({short/nn*100:.0f}%)  80-129: {med} ({med/nn*100:.0f}%)  >=130: {long_} ({long_/nn*100:.0f}%)")
    print(f"    Min={s[0]}, P25={s[nn//4]}, Med={s[nn//2]}, P75={s[3*nn//4]}, Max={s[-1]}")
    print(f"    Distribution:")
    for lo in range(0, 261, 20):
        hi = lo + 20
        c = sum(1 for g in next_gaps if lo <= g < hi)
        bar = "#" * c
        if c > 0:
            print(f"      {lo:>3}-{hi:<3}: {c:>2} {bar}")


def simulate(threshold_fn, label):
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    for rows in all_data:
        prev_gap = -1

        for sa, sa_acc, is_acc in rows:
            rate = sa_acc / sa if sa > 0 else 0.0
            total_spins += 1

            thresh = threshold_fn(prev_gap)
            should_bet = (sa >= thresh) and (rate >= 0.30)

            if should_bet:
                total_bet += 1

            if is_acc:
                total_acc += 1
                if should_bet:
                    total_caught += 1
                prev_gap = sa

    if total_caught > 0 and total_bet > 0:
        mb = total_bet / total_caught
        bet_pct = total_bet / total_spins * 100
        lift = (total_caught / total_acc) / (total_bet / total_spins)
        print(f"  {label:<55} {total_caught:>3}/{total_acc:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")
    else:
        print(f"  {label:<55}   0 caught")

    return total_caught, total_acc, total_bet, total_spins


print(f"\n{'='*70}")
print(f"STRATEGY: Lower threshold after Long gap to catch shorts")
print(f"{'='*70}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*78}")

# Baseline
simulate(lambda pg: 130, "Flat 130 (current)")

# After Long (>=130), drop threshold to catch the predicted short
for l_cut in [120, 130, 140]:
    for short_thresh in [40, 50, 60, 70, 80]:
        for normal_thresh in [120, 130, 140]:
            def make(lc, st, nt):
                def fn(pg):
                    if pg >= lc:
                        return st  # predict short, bet early
                    else:
                        return nt  # normal
                return fn
            label = f"After>={l_cut}->bet@{short_thresh}, else->{normal_thresh}"
            simulate(make(l_cut, short_thresh, normal_thresh), label)

# Three-tier: after Short raise, after Long lower, Medium normal
print(f"\n  --- THREE TIER ---")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*78}")

for s_cut in [70, 80, 100]:
    for l_cut in [120, 130, 140]:
        for after_s in [140, 150, 160]:     # predict long, be patient
            for after_m in [120, 130]:        # normal
                for after_l in [40, 50, 60, 70, 80]:  # predict short, bet early
                    def make3(sc, lc, a_s, a_m, a_l):
                        def fn(pg):
                            if pg < 0:
                                return a_m  # first cycle
                            elif pg < sc:
                                return a_s
                            elif pg >= lc:
                                return a_l
                            else:
                                return a_m
                        return fn
                    label = f"S<{s_cut}->{after_s} M->{after_m} L>={l_cut}->{after_l}"
                    simulate(make3(s_cut, l_cut, after_s, after_m, after_l), label)


# Show cost analysis: when we predict short but it's actually long
print(f"\n{'='*70}")
print(f"COST ANALYSIS: what happens when prediction is WRONG?")
print(f"{'='*70}")

for l_cut in [120, 130, 140]:
    print(f"\n  After gap >= {l_cut}, predict short, bet from spin 50:")
    next_gaps = []
    for i in range(1, len(all_gaps)):
        if all_gaps[i-1] >= l_cut:
            next_gaps.append(all_gaps[i])

    if not next_gaps:
        continue

    total_bet_spins = 0
    caught = 0
    for g in next_gaps:
        if g >= 50:  # we bet from spin 50 to gap end
            bet_spins = g - 50 + 1
            total_bet_spins += bet_spins
            caught += 1
        # if g < 50: we miss it AND don't waste bets

    missed_short = sum(1 for g in next_gaps if g < 50)
    correct_short = sum(1 for g in next_gaps if 50 <= g < 130)
    wrong_long = sum(1 for g in next_gaps if g >= 130)

    print(f"    Total next gaps: {len(next_gaps)}")
    print(f"    Caught (gap>=50): {caught}")
    print(f"    Too short (<50, missed anyway): {missed_short}")
    print(f"    Correct prediction (50-129): {correct_short} — avg bet: {sum(g-50+1 for g in next_gaps if 50<=g<130)/max(1,correct_short):.0f} spins")
    print(f"    WRONG (>=130, long anyway): {wrong_long} — avg bet: {sum(g-50+1 for g in next_gaps if g>=130)/max(1,wrong_long):.0f} spins")
    print(f"    Total max-bet spins: {total_bet_spins}, per catch: {total_bet_spins/max(1,caught):.1f}")

print(f"\nDone!", flush=True)
