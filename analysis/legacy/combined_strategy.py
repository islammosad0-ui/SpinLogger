"""
Combined strategy using BOTH:
1. Spin counter (sa_spins) with debt shift
2. Running accum rate (sa_acc / sa_spins) as gate/modifier
3. Other triple count as secondary signal

This models the game's two-dimensional pity timer.
"""
import csv
import math

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

# Load all spins with full state
all_spins = []  # list of dicts per file
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    all_spins.append((label, rows))

# ============================================================
# STRATEGY SIMULATOR
# Replays all spins, tracking state, applies strategy in real-time
# ============================================================

def simulate_combined(spins_data, config):
    """
    config = {
        'spin_threshold_base': int,     # base spin count to start betting
        'spin_shift': float,            # how much to shift based on prev gap
        'spin_center': int,             # center for shift
        'acc_rate_gate': float or None, # if set, only bet when acc_rate >= this
        'acc_rate_boost': float,        # if acc_rate > this, lower threshold by boost_amount
        'boost_amount': int,            # spins to subtract from threshold when boosted
        'use_ewma': bool,              # use EWMA of prev gaps instead of just last
        'ewma_alpha': float,
    }
    """
    base = config['spin_threshold_base']
    shift = config['spin_shift']
    center = config['spin_center']
    gate = config.get('acc_rate_gate', None)
    boost_rate = config.get('acc_rate_boost', None)
    boost_amount = config.get('boost_amount', 0)
    use_ewma = config.get('use_ewma', False)
    alpha = config.get('ewma_alpha', 1.0)

    total_acc = 0
    caught = 0
    total_bet = 0
    total_spins = 0

    for label, rows in spins_data:
        prev_gap = center
        ewma_gap = center

        for row in rows:
            sa = int(row["sa_spins"])
            sa_acc = int(row["sa_acc"])
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_acc = (r1 == r2 == r3 == "accumulation")
            acc_rate = sa_acc / sa if sa > 0 else 0.3

            total_spins += 1

            # Compute dynamic threshold
            ref = ewma_gap if use_ewma else prev_gap
            threshold = base - shift * (ref - center)

            # Boost: if acc_rate is high, lower threshold
            if boost_rate is not None and acc_rate > boost_rate:
                threshold -= boost_amount

            # Gate: only bet if acc_rate above minimum
            should_bet = (sa >= threshold)
            if gate is not None and acc_rate < gate:
                should_bet = False

            if should_bet:
                total_bet += 1

            if is_acc:
                total_acc += 1
                if should_bet:
                    caught += 1
                # Update tracking
                if use_ewma:
                    ewma_gap = alpha * sa + (1 - alpha) * ewma_gap
                prev_gap = sa

    return total_acc, caught, total_bet, total_spins

# ============================================================
# TEST 1: Spin-only baseline (no accum rate)
# ============================================================
print("="*60)
print("  TEST 1: Spin-only baseline")
print("="*60, flush=True)

base_config = {
    'spin_threshold_base': 140,
    'spin_shift': 0.30,
    'spin_center': 100,
    'acc_rate_gate': None,
    'acc_rate_boost': None,
    'boost_amount': 0,
    'use_ewma': False,
    'ewma_alpha': 1.0,
}
total_acc, caught, bet, total = simulate_combined(all_spins, base_config)
mb = bet / caught if caught > 0 else 999
lift = (caught / total_acc) / (bet / total) if bet > 0 else 0
print(f"  Base (140/0.30/100): {caught}/{total_acc} caught, {bet/total*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

# ============================================================
# TEST 2: Add accum rate GATE
# ============================================================
print(f"\n{'='*60}")
print("  TEST 2: Spin + accum rate gate")
print("="*60, flush=True)

results = []
for base in range(120, 160, 2):
    for shift_x100 in range(10, 60, 5):
        shift = shift_x100 / 100.0
        for gate_x100 in [0, 20, 22, 24, 26, 28, 30]:
            gate = gate_x100 / 100.0 if gate_x100 > 0 else None
            config = {
                'spin_threshold_base': base,
                'spin_shift': shift,
                'spin_center': 100,
                'acc_rate_gate': gate,
                'acc_rate_boost': None,
                'boost_amount': 0,
                'use_ewma': False,
                'ewma_alpha': 1.0,
            }
            total_acc, caught, bet, total = simulate_combined(all_spins, config)
            if caught > 0 and bet > 0:
                mb = bet / caught
                lift = (caught / total_acc) / (bet / total)
                results.append((base, shift, gate, caught, bet, total_acc, total, mb, lift))

results.sort(key=lambda x: -x[8])
print(f"\nTop 20 (with gate):")
print(f"  {'base':>4} {'shift':>5} {'gate':>5} {'Caught':>8} {'Bet%':>6} {'mb/h':>6} {'Lift':>6}")
for base, shift, gate, caught, bet, ta, total, mb, lift in results[:20]:
    gstr = f"{gate:.2f}" if gate else " none"
    print(f"  {base:>4} {shift:>5.2f} {gstr:>5} {caught:>5}/{ta} {bet/total*100:>5.1f}% {mb:>5.1f} {lift:>5.2f}x")

# Show best WITHOUT gate vs best WITH gate
no_gate = [r for r in results if r[2] is None]
with_gate = [r for r in results if r[2] is not None]
if no_gate:
    best_ng = max(no_gate, key=lambda x: x[8])
    print(f"\n  Best WITHOUT gate: base={best_ng[0]}, shift={best_ng[1]:.2f} -> {best_ng[3]}/{best_ng[5]} caught, {best_ng[7]:.1f} mb/h, {best_ng[8]:.2f}x")
if with_gate:
    best_wg = max(with_gate, key=lambda x: x[8])
    print(f"  Best WITH gate:    base={best_wg[0]}, shift={best_wg[1]:.2f}, gate={best_wg[2]:.2f} -> {best_wg[3]}/{best_wg[5]} caught, {best_wg[7]:.1f} mb/h, {best_wg[8]:.2f}x")

# ============================================================
# TEST 3: Add accum rate BOOST
# ============================================================
print(f"\n{'='*60}")
print("  TEST 3: Spin + accum rate boost")
print("="*60, flush=True)

boost_results = []
for base in range(130, 160, 2):
    for shift_x100 in range(10, 50, 5):
        shift = shift_x100 / 100.0
        for boost_rate_x100 in [30, 32, 34, 36, 38]:
            boost_rate = boost_rate_x100 / 100.0
            for boost_amt in [10, 15, 20, 25, 30]:
                config = {
                    'spin_threshold_base': base,
                    'spin_shift': shift,
                    'spin_center': 100,
                    'acc_rate_gate': None,
                    'acc_rate_boost': boost_rate,
                    'boost_amount': boost_amt,
                    'use_ewma': False,
                    'ewma_alpha': 1.0,
                }
                total_acc, caught, bet, total = simulate_combined(all_spins, config)
                if caught > 0 and bet > 0:
                    mb = bet / caught
                    lift = (caught / total_acc) / (bet / total)
                    if lift >= 2.5 and mb < 40:
                        boost_results.append((base, shift, boost_rate, boost_amt, caught, bet, total_acc, total, mb, lift))

boost_results.sort(key=lambda x: -x[9])
print(f"\nTop 15 boost configs:")
print(f"  {'base':>4} {'shift':>5} {'brate':>5} {'bamt':>4} {'Caught':>8} {'Bet%':>6} {'mb/h':>6} {'Lift':>6}")
for base, shift, br, ba, caught, bet, ta, total, mb, lift in boost_results[:15]:
    print(f"  {base:>4} {shift:>5.2f} {br:>5.2f} {ba:>4} {caught:>5}/{ta} {bet/total*100:>5.1f}% {mb:>5.1f} {lift:>5.2f}x")

# ============================================================
# TEST 4: Gate + Boost combined
# ============================================================
print(f"\n{'='*60}")
print("  TEST 4: Gate + Boost combined")
print("="*60, flush=True)

combo_results = []
for base in range(130, 155, 3):
    for shift_x100 in range(15, 45, 5):
        shift = shift_x100 / 100.0
        for gate_x100 in [22, 24, 26, 28]:
            gate = gate_x100 / 100.0
            for boost_rate_x100 in [32, 34, 36]:
                boost_rate = boost_rate_x100 / 100.0
                for boost_amt in [10, 15, 20]:
                    config = {
                        'spin_threshold_base': base,
                        'spin_shift': shift,
                        'spin_center': 100,
                        'acc_rate_gate': gate,
                        'acc_rate_boost': boost_rate,
                        'boost_amount': boost_amt,
                        'use_ewma': False,
                        'ewma_alpha': 1.0,
                    }
                    total_acc, caught, bet, total = simulate_combined(all_spins, config)
                    if caught > 0 and bet > 0:
                        mb = bet / caught
                        lift = (caught / total_acc) / (bet / total)
                        if lift >= 2.5 and mb < 40:
                            combo_results.append((base, shift, gate, boost_rate, boost_amt, caught, bet, total_acc, total, mb, lift))

combo_results.sort(key=lambda x: -x[10])
print(f"\nTop 15 gate+boost combos:")
print(f"  {'base':>4} {'shift':>5} {'gate':>4} {'brate':>5} {'bamt':>4} {'Caught':>8} {'Bet%':>6} {'mb/h':>6} {'Lift':>6}")
for base, shift, gate, br, ba, caught, bet, ta, total, mb, lift in combo_results[:15]:
    print(f"  {base:>4} {shift:>5.2f} {gate:>4.2f} {br:>5.2f} {ba:>4} {caught:>5}/{ta} {bet/total*100:>5.1f}% {mb:>5.1f} {lift:>5.2f}x")

# ============================================================
# TEST 5: Per-account validation of best combined strategy
# ============================================================
print(f"\n{'='*60}")
print("  TEST 5: Per-account validation")
print("="*60, flush=True)

# Get the global best configs
if combo_results:
    best = combo_results[0]
    best_config = {
        'spin_threshold_base': best[0],
        'spin_shift': best[1],
        'spin_center': 100,
        'acc_rate_gate': best[2],
        'acc_rate_boost': best[3],
        'boost_amount': best[4],
        'use_ewma': False,
        'ewma_alpha': 1.0,
    }
    print(f"\n  Global best: base={best[0]}, shift={best[1]:.2f}, gate={best[2]:.2f}, boost_rate={best[3]:.2f}, boost={best[4]}")

    for label, rows in all_spins:
        ta, caught, bet, total = simulate_combined([(label, rows)], best_config)
        mb = bet / caught if caught > 0 else 999
        lift = (caught / ta) / (bet / total) if bet > 0 else 0
        print(f"    {label}: {caught}/{ta} caught, {bet/total*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

# Also test spin-only best
if results:
    best_ng_conf = {
        'spin_threshold_base': 140,
        'spin_shift': 0.30,
        'spin_center': 100,
        'acc_rate_gate': None,
        'acc_rate_boost': None,
        'boost_amount': 0,
        'use_ewma': False,
        'ewma_alpha': 1.0,
    }
    print(f"\n  Spin-only (140/0.30/100):")
    for label, rows in all_spins:
        ta, caught, bet, total = simulate_combined([(label, rows)], best_ng_conf)
        mb = bet / caught if caught > 0 else 999
        lift = (caught / ta) / (bet / total) if bet > 0 else 0
        print(f"    {label}: {caught}/{ta} caught, {bet/total*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

# ============================================================
# TEST 6: What's the theoretical maximum with perfect knowledge?
# ============================================================
print(f"\n{'='*60}")
print("  TEST 6: Oracle analysis (perfect knowledge)")
print("="*60, flush=True)

# If we bet only on the LAST N spins of each gap, what's the achievable lift?
all_gaps_corrected = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        if r1 == r2 == r3 == "accumulation":
            all_gaps_corrected.append(int(row["sa_spins"]))

n = len(all_gaps_corrected)
total_spins = sum(all_gaps_corrected)

print(f"  If we bet the last N spins of each gap:")
for N in [1, 3, 5, 10, 15, 20, 30]:
    bet_spins = sum(min(N, g) for g in all_gaps_corrected)
    mb = bet_spins / n
    lift = 1.0 / (bet_spins / total_spins)
    print(f"    Last {N:>2}: {n} caught, {bet_spins/total_spins*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

# What's the lift if we only bet gaps > threshold?
print(f"\n  If we bet everything above spin S:")
for S in [80, 100, 110, 120, 130, 140, 150]:
    caught = sum(1 for g in all_gaps_corrected if g >= S)
    bet_spins = sum(max(0, g - S + 1) for g in all_gaps_corrected)
    if caught > 0 and bet_spins > 0:
        mb = bet_spins / caught
        lift = (caught / n) / (bet_spins / total_spins)
        print(f"    S>={S:>3}: {caught}/{n} caught, {bet_spins/total_spins*100:.1f}% bet, {mb:.1f} mb/h, {lift:.2f}x")

print(f"\nDone!", flush=True)
