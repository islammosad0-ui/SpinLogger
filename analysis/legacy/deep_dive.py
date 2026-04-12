"""
Deep dive into the most promising leads:
1. Hard ceiling at 394? Both max gaps identical.
2. Accum symbol accumulation as real-time trigger signal
3. Why Acct3 is so different
4. Finer EWMA grid search
5. Combined strategy: EWMA + accum rate signal
"""
import csv
import math

files = [
    ("Acct1", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (1).csv"),
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

# Load raw spin data with rich per-spin info
all_events = []  # list of (label, gap_number, spin_in_gap, reel1, reel2, reel3, is_acc_triple)
all_gaps = []
per_acct_gaps = {}
per_acct_events = {}

for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    acct_gaps = []
    acct_events = []
    sa = 0
    gap_num = 0
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        sa += 1
        is_triple = (r1 == r2 == r3)
        is_acc = is_triple and r1 == "accumulation"
        is_other_triple = is_triple and not is_acc
        ac_count = sum(1 for r in [r1, r2, r3] if r == "accumulation")

        acct_events.append({
            "spin": sa, "r1": r1, "r2": r2, "r3": r3,
            "is_acc": is_acc, "is_triple": is_triple,
            "is_other_triple": is_other_triple,
            "ac_count": ac_count, "gap_num": gap_num
        })

        if is_acc:
            acct_gaps.append(sa)
            all_gaps.append(sa)
            gap_num += 1
            sa = 0

    per_acct_gaps[label] = acct_gaps
    per_acct_events[label] = acct_events

n = len(all_gaps)
mean_gap = sum(all_gaps) / n
print(f"Total gaps: {n}, mean={mean_gap:.1f}, max={max(all_gaps)}", flush=True)

# ============================================================
# INVESTIGATION 1: Hard ceiling at 394
# ============================================================
print(f"\n{'='*60}")
print(f"  INVESTIGATION 1: Hard ceiling analysis")
print(f"{'='*60}", flush=True)

sorted_gaps = sorted(all_gaps, reverse=True)
print(f"Top 10 gaps: {sorted_gaps[:10]}")

# Which accounts have the 394 gaps?
for label, gaps in per_acct_gaps.items():
    big = [g for g in gaps if g > 300]
    if big:
        print(f"  {label}: gaps > 300 = {big}")
        # What's the gap BEFORE and AFTER each 394?
        for i, g in enumerate(gaps):
            if g > 300:
                prev_g = gaps[i-1] if i > 0 else "N/A"
                next_g = gaps[i+1] if i < len(gaps)-1 else "N/A"
                print(f"    gap index {i}: {g} (prev={prev_g}, next={next_g})")

# Distribution of gaps near the tail
print(f"\nGap distribution > 150:")
for bucket_start in range(150, 400, 10):
    count = sum(1 for g in all_gaps if bucket_start <= g < bucket_start + 10)
    if count > 0:
        bar = "#" * count
        print(f"  {bucket_start:>3}-{bucket_start+9}: {count:>2} {bar}")

# Is 394 suspicious? Check exact multiples
print(f"\n  Is 394 = some round number? 394/4 = {394/4}, 394/2 = {394/2}")
print(f"  394 in hex: {hex(394)}")
print(f"  400-394 = 6, 384+10 = 394, 256+138 = 394")
print(f"  Nearest powers of 2: 256, 512")

# ============================================================
# INVESTIGATION 2: Accum symbols as real-time trigger
# ============================================================
print(f"\n{'='*60}")
print(f"  INVESTIGATION 2: Accum symbol rate as real-time trigger")
print(f"{'='*60}", flush=True)

# For each gap, track the running accum count vs spin number
# The question: does accum_rate within the gap predict HOW MUCH LONGER?
# If we see accum_rate drop below X at spin S, does the triple come soon after?

# Build per-gap accum trajectory
for label, events in per_acct_events.items():
    # Group events by gap
    gap_trajectories = {}
    current_gap = 0
    current_accums = 0
    current_spin = 0
    for e in events:
        current_spin += 1
        current_accums += e["ac_count"]
        if e["is_acc"]:
            gap_trajectories[current_gap] = (current_spin, current_accums)
            current_gap += 1
            current_accums = 0
            current_spin = 0

    gaps = per_acct_gaps[label]
    ng = len(gaps)
    if ng < 15: continue

    # For each gap, what's the accum rate at spin 50, 80, 100, 120?
    # Actually let's look at it differently: at each checkpoint spin,
    # what's the probability the gap ends within the next 20 spins?
    print(f"\n  {label}: Accum rate at checkpoints vs remaining gap")
    print(f"    {'Check':>5} {'n':>4} {'Avg rate':>8} {'Hit<20':>6} {'Hit<40':>6}")

    for checkpoint in [40, 60, 80, 100, 120, 140]:
        rates = []
        hit_within_20 = 0
        hit_within_40 = 0
        for gap_idx in range(ng):
            gap_len = gaps[gap_idx]
            if gap_len <= checkpoint: continue
            # How many accum symbols in first `checkpoint` spins of this gap?
            # We need to reconstruct this from events
            pass  # Will do below with raw data

    break  # Just analyze the approach first

# Better approach: iterate through raw spins and track accum rate
print(f"\n  Accum rate analysis (all accounts combined):")
# For each spin within a gap, track: spin_number, running_accum_count, remaining_to_triple
all_gap_data = []  # list of (gap_length, spin_in_gap, running_accum_total, running_accum_rate)

for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    sa = 0
    accum_total = 0
    gap_spins = []  # (spin_in_gap, accum_running)
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        sa += 1
        ac = sum(1 for r in [r1, r2, r3] if r == "accumulation")
        accum_total += ac
        gap_spins.append((sa, accum_total))

        if r1 == r2 == r3 and r1 == "accumulation":
            # This gap is complete
            gap_len = sa
            all_gap_data.append((gap_len, gap_spins[:]))
            sa = 0
            accum_total = 0
            gap_spins = []

# Now analyze: at spin S in a gap, what's the accum rate, and how predictive is it?
print(f"\n  At spin S: accum_rate vs P(triple within next 30 spins)")
print(f"  {'Spin':>5} {'n_alive':>7} {'avg_rate':>9} {'hit_30':>6} {'p_hit30':>7} {'lo_rate':>8} {'hi_rate':>8} {'p_lo':>5} {'p_hi':>5}")

for check_spin in [30, 50, 70, 90, 100, 110, 120, 130, 140, 150]:
    # Filter to gaps that survived to this spin
    alive = [(gl, spins) for gl, spins in all_gap_data if gl > check_spin]
    if len(alive) < 10: continue

    rates = []
    hits_within_30 = []
    for gl, spins in alive:
        # Accum rate at this spin
        _, acc_total = spins[check_spin - 1]
        rate = acc_total / check_spin
        rates.append(rate)
        hits_within_30.append(1 if gl <= check_spin + 30 else 0)

    avg_rate = sum(rates) / len(rates)
    p_hit = sum(hits_within_30) / len(hits_within_30)

    # Split by high/low rate
    median_rate = sorted(rates)[len(rates)//2]
    lo_rates_hits = [h for r, h in zip(rates, hits_within_30) if r < median_rate]
    hi_rates_hits = [h for r, h in zip(rates, hits_within_30) if r >= median_rate]

    p_lo = sum(lo_rates_hits) / len(lo_rates_hits) if lo_rates_hits else 0
    p_hi = sum(hi_rates_hits) / len(hi_rates_hits) if hi_rates_hits else 0

    print(f"  {check_spin:>5} {len(alive):>7} {avg_rate:>9.4f} {sum(hits_within_30):>6} {p_hit:>7.3f} {median_rate-0.02:>8.4f} {median_rate+0.02:>8.4f} {p_lo:>5.3f} {p_hi:>5.3f}")

# ============================================================
# INVESTIGATION 3: Why is Acct3 so different?
# ============================================================
print(f"\n{'='*60}")
print(f"  INVESTIGATION 3: Acct3 anomaly analysis")
print(f"{'='*60}", flush=True)

for label, gaps in per_acct_gaps.items():
    ng = len(gaps)
    if ng < 15: continue
    avg = sum(gaps) / ng
    cv = (sum((g - avg)**2 for g in gaps) / ng) ** 0.5 / avg
    # Gap distribution
    q25 = sorted(gaps)[int(ng*0.25)]
    q50 = sorted(gaps)[int(ng*0.50)]
    q75 = sorted(gaps)[int(ng*0.75)]
    q90 = sorted(gaps)[int(ng*0.90)]
    short = sum(1 for g in gaps if g < 50)
    long_ = sum(1 for g in gaps if g > 150)

    # Lag-1 autocorrelation
    pairs = [(gaps[i], gaps[i+1]) for i in range(ng-1)]
    mx = sum(g for g, _ in pairs) / len(pairs)
    my = sum(g for _, g in pairs) / len(pairs)
    cov = sum((x-mx)*(y-my) for x, y in pairs) / len(pairs)
    sx = (sum((x-mx)**2 for x, _ in pairs) / len(pairs)) ** 0.5
    sy = (sum((y-my)**2 for _, y in pairs) / len(pairs)) ** 0.5
    r = cov / (sx * sy) if sx > 0 and sy > 0 else 0

    print(f"\n  {label} (n={ng}):")
    print(f"    Mean={avg:.1f}, CV={cv:.3f}, Lag1={r:+.3f}")
    print(f"    Q25={q25}, Q50={q50}, Q75={q75}, Q90={q90}")
    print(f"    Short (<50): {short} ({short/ng*100:.0f}%), Long (>150): {long_} ({long_/ng*100:.0f}%)")

    # Run the strategy and show WHERE it catches/misses
    f = lambda pg: 130 - 0.4 * (pg - 100)
    prev = 100
    catches = []
    misses = []
    for i, g in enumerate(gaps):
        t = int(f(prev))
        if g >= t:
            catches.append((i, g, prev, t))
        else:
            misses.append((i, g, prev, t))
        prev = g

    # Are catches clustered in time?
    if catches:
        catch_indices = [c[0] for c in catches]
        print(f"    Catches: {len(catches)} at indices {catch_indices[:20]}{'...' if len(catches) > 20 else ''}")
        # Consecutive catches
        consec = sum(1 for i in range(len(catch_indices)-1) if catch_indices[i+1] - catch_indices[i] <= 2)
        print(f"    Consecutive catches (within 2): {consec}")

# ============================================================
# INVESTIGATION 4: Fine EWMA grid + combined signal
# ============================================================
print(f"\n{'='*60}")
print(f"  INVESTIGATION 4: Fine EWMA grid search")
print(f"{'='*60}", flush=True)

def simulate_ewma(gaps, base, shift, alpha, center):
    caught = 0
    total_bet = 0
    total_spins = 0
    ewma = center
    for g in gaps:
        t = base - shift * (ewma - center)
        bet_start = max(1, int(t))
        bet_spins = max(0, g - bet_start + 1) if g >= bet_start else 0
        total_bet += bet_spins
        total_spins += g
        if g >= bet_start:
            caught += 1
        ewma = alpha * g + (1 - alpha) * ewma
    return caught, total_bet, total_spins

# Fine grid around the best EWMA configs
best_ewma = []
for alpha_x100 in range(70, 100):
    alpha = alpha_x100 / 100.0
    for base in range(125, 160):
        for shift_x100 in range(10, 80, 5):
            shift = shift_x100 / 100.0
            for center in [95, 97, 100]:
                caught, bet, total = simulate_ewma(all_gaps, base, shift, alpha, center)
                if caught > 0 and bet > 0:
                    mb = bet / caught
                    lift = (caught / n) / (bet / total)
                    if lift >= 3.0 and mb < 35:
                        best_ewma.append((alpha, base, shift, center, caught, bet, total, mb, lift))

best_ewma.sort(key=lambda x: -x[8])
print(f"\nTop 20 EWMA configs (lift >= 3.0, mb < 35):")
print(f"  {'alpha':>5} {'base':>4} {'shift':>5} {'ctr':>3} {'Caught':>7} {'Bet%':>6} {'mb/h':>6} {'Lift':>5}")
for alpha, base, shift, ctr, caught, bet, total, mb, lift in best_ewma[:20]:
    print(f"  {alpha:>5.2f} {base:>4} {shift:>5.2f} {ctr:>3} {caught:>5}/{n} {bet/total*100:>5.1f}% {mb:>5.1f} {lift:>4.2f}x")

# ============================================================
# INVESTIGATION 5: Accum-rate-adjusted threshold
# ============================================================
print(f"\n{'='*60}")
print(f"  INVESTIGATION 5: Accum rate as secondary signal")
print(f"{'='*60}", flush=True)

# Idea: at each spin, if running accum_rate > threshold, delay betting
# (high accum rate = game is feeding accum symbols = NOT about to triple yet)
# Low accum rate = game has been starving accum = triple is closer
# This is because accum/spin stabilizes at ~0.30 but starts higher in short gaps

# For each gap, compute the accum rate at key checkpoints
# and test: does betting when rate < X at spin S catch more?

# Build per-spin data
gap_spin_data = []  # (gap_idx, gap_len, spin, accum_rate)
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    sa = 0
    accum_total = 0
    gap_idx_global = len(gap_spin_data)
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        sa += 1
        ac = sum(1 for r in [r1, r2, r3] if r == "accumulation")
        accum_total += ac

        if r1 == r2 == r3 and r1 == "accumulation":
            gap_len = sa
            rate = accum_total / sa
            gap_spin_data.append((gap_len, rate, sa))
            sa = 0
            accum_total = 0

print(f"\n  Gap length vs final accum rate:")
# Quintile analysis of gap_length by accum_rate
data = sorted(gap_spin_data, key=lambda x: x[1])
q = len(data) // 5
for i in range(5):
    chunk = data[i*q:(i+1)*q] if i < 4 else data[i*q:]
    avg_len = sum(d[0] for d in chunk) / len(chunk)
    avg_rate = sum(d[1] for d in chunk) / len(chunk)
    print(f"    Rate Q{i+1} (avg rate={avg_rate:.3f}): avg gap = {avg_len:.1f}")

# Can we use accum rate at a checkpoint to decide whether to bet?
print(f"\n  Strategy: bet at spin S only if accum_rate at S < threshold")
# Simulate: for each gap, at the checkpoint spin, check the accum rate
# If below threshold -> bet from that spin
# If above threshold -> wait (miss this one)

for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    # Replay with accum tracking
    gap_details = []  # (gap_len, rate_at_100, rate_at_120)
    sa = 0
    accum_total = 0
    rate_at = {}
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        sa += 1
        ac = sum(1 for r in [r1, r2, r3] if r == "accumulation")
        accum_total += ac
        for cp in [80, 100, 120]:
            if sa == cp:
                rate_at[cp] = accum_total / sa

        if r1 == r2 == r3 and r1 == "accumulation":
            gap_details.append((sa, dict(rate_at)))
            sa = 0
            accum_total = 0
            rate_at = {}

    gaps = per_acct_gaps[label]
    ng = len(gaps)

    # Try: bet starting at spin 120, but only if rate_at_100 < 0.32
    for rate_threshold in [0.28, 0.30, 0.32, 0.34, 0.36]:
        for bet_start in [110, 120, 130]:
            caught = 0
            bet_spins = 0
            total_spins = 0
            for gl, rates in gap_details:
                total_spins += gl
                r100 = rates.get(100, None)
                if gl < bet_start:
                    continue
                if r100 is not None and r100 < rate_threshold:
                    bet_spins += (gl - bet_start + 1)
                    caught += 1
                elif r100 is None:
                    # Gap < 100, skip
                    pass
                else:
                    # Rate too high, but still count bet if gap > bet_start
                    # (we're NOT betting these - that's the point)
                    pass
            if caught > 0 and bet_spins > 0 and total_spins > 0:
                mb = bet_spins / caught
                lift = (caught / ng) / (bet_spins / total_spins)
                if lift > 2.0:
                    print(f"    {label} rate<{rate_threshold} bet@{bet_start}: {caught}/{ng} caught, {bet_spins/total_spins*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

# ============================================================
# INVESTIGATION 6: The 394 twins - are they in the same account?
# ============================================================
print(f"\n{'='*60}")
print(f"  INVESTIGATION 6: 394-gap deep dive")
print(f"{'='*60}", flush=True)

for label, gaps in per_acct_gaps.items():
    for i, g in enumerate(gaps):
        if g >= 380:
            # What happened around this gap?
            start_idx = max(0, i-3)
            end_idx = min(len(gaps), i+4)
            context = gaps[start_idx:end_idx]
            print(f"  {label} gap[{i}] = {g}, context: ...{context}...")
            # Sum of this gap and neighbors
            if i > 0 and i < len(gaps)-1:
                print(f"    pair sum (prev+this) = {gaps[i-1]+g}")
                print(f"    pair sum (this+next) = {g+gaps[i+1]}")

# ============================================================
# INVESTIGATION 7: Is there a "guaranteed by spin N" mechanism?
# ============================================================
print(f"\n{'='*60}")
print(f"  INVESTIGATION 7: Survival function tail analysis")
print(f"{'='*60}", flush=True)

# Empirical survival function at high spins
for s in range(150, 400, 10):
    count_above = sum(1 for g in all_gaps if g > s)
    if count_above > 0:
        print(f"  S({s:>3}) = {count_above:>3}/{n} = {count_above/n:.4f}")

# Under three-phase model, compute expected survival
print(f"\n  Three-phase model predicted survival:")
surv = 1.0
for s in range(1, 400):
    if s < 27: h = 0.003
    elif s < 122: h = 0.010
    else: h = 0.027
    surv *= (1 - h)
    if s % 20 == 0 and s >= 120:
        actual_count = sum(1 for g in all_gaps if g > s)
        print(f"  s={s:>3}: predicted S={surv:.6f} ({surv*n:.1f} expected), actual={actual_count}")

print(f"\nDone!", flush=True)
