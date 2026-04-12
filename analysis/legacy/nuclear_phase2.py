"""
NUCLEAR PHASE 2 — Targeted deep analysis
Focus: strip reconstruction, optimal betting simulation, debt-based timing
"""
import csv
import statistics
from collections import Counter, defaultdict
import math

def load_csv(path):
    rows = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['r1'] = int(row['r1'])
            row['r2'] = int(row['r2'])
            row['r3'] = int(row['r3'])
            row['is_triple'] = row['is_triple'].lower() == 'true'
            row['bet_multiplier'] = int(row['bet_multiplier'])
            row['acc_count'] = int(row['acc_count'])
            row['seq'] = int(row['seq'])
            row['tuple'] = (row['r1'], row['r2'], row['r3'])
            rows.append(row)
    return rows

acc1 = load_csv(r"C:\Users\Islam\Downloads\Account 1 spin_history_2026-04-05.csv")
acc2 = load_csv(r"C:\Users\Islam\Downloads\Account 2 spin_history_2026-04-04.csv")

# ═��═════════════════════════════════════════════════════════════════════════════
# A. STRIP RECONSTRUCTION — find the true ordering of 33 outcomes
# ═══════════════════���═══════════════════════════════════════════════════════════
print("=" * 80)
print("A. STRIP RECONSTRUCTION — transition adjacency analysis")
print("=" * 80)

# Build transition matrix from BOTH accounts
all_data = acc1 + acc2  # Don't use this for sequential analysis!
unique_tuples = sorted(set(r['tuple'] for r in all_data))
n_tuples = len(unique_tuples)
idx_map = {t: i for i, t in enumerate(unique_tuples)}

# Self-transition rate per tuple
for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    self_trans = Counter()
    total_trans = Counter()
    for i in range(len(data) - 1):
        t = data[i]['tuple']
        total_trans[t] += 1
        if data[i+1]['tuple'] == t:
            self_trans[t] += 1

    print(f"\n{name}: Self-transition rates (same tuple repeats)")
    for t in unique_tuples:
        if total_trans[t] > 0:
            rate = self_trans[t] / total_trans[t] * 100
            expected = total_trans.get(t, 0) / len(data) * 100  # expected if random
            freq = total_trans[t] / len(data) * 100
            print(f"  {t}: {self_trans[t]}/{total_trans[t]} = {rate:.1f}% (freq={freq:.1f}%, expected_self={freq:.1f}%)")

# ══════���══════════════════════════���══════════════════════════���══════════════════
# B. CONDITIONAL ACC PROBABILITY BY POSITION IN GAP
# ════════��═════════════════���════════════════════════════��═══════════════════════
print("\n" + "=" * 80)
print("B. P(ACC triple) vs spins-since-last-ACC — the hazard function")
print("=" * 80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    # Find all ACC triple positions
    acc_positions = [i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30)]

    # For each spin, compute spins since last ACC triple
    spins_since = []
    last_acc = -1
    for i, r in enumerate(data):
        if r['tuple'] == (30, 30, 30):
            spins_since.append(i - last_acc if last_acc >= 0 else None)
            last_acc = i
        else:
            spins_since.append(i - last_acc if last_acc >= 0 else None)

    # Hazard function: P(ACC at spin N | survived to spin N)
    # Group by spins_since into buckets
    buckets = [(1, 20), (21, 40), (41, 60), (61, 80), (81, 100), (101, 120),
               (121, 150), (151, 200), (201, 400)]

    print(f"\n{name}: Hazard function (P(ACC) given spins since last ACC)")
    for lo, hi in buckets:
        # Count spins in this range and how many were ACC
        at_risk = 0
        hits = 0
        for i in range(len(data)):
            if spins_since[i] is not None and lo <= spins_since[i] <= hi:
                at_risk += 1
                if data[i]['tuple'] == (30, 30, 30):
                    hits += 1
        if at_risk > 0:
            rate = hits / at_risk * 100
            print(f"  Spins {lo:>3}-{hi:>3}: {hits:>3}/{at_risk:>5} = {rate:.2f}%")

# ═════════════════════════════════════════════════════════════════��═════════════
# C. OPTIMAL BETTING THRESHOLD SIMULATION
# ══════════════════════════���════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("C. OPTIMAL BETTING THRESHOLD SIMULATION")
print("=" * 80)
print("Strategy: bet max after N spins since last ACC triple")

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    acc_positions = [i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30)]
    gaps = [acc_positions[i+1] - acc_positions[i] for i in range(len(acc_positions)-1)]

    if len(gaps) < 5:
        continue

    print(f"\n{name} ({len(gaps)} gaps, median={statistics.median(gaps):.0f}):")
    print(f"  {'Threshold':>10} {'Caught':>8} {'Total':>8} {'Catch%':>8} {'MaxBet Spins':>14} {'Spins/Hit':>12} {'Eff':>8}")

    for threshold in [20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140]:
        caught = 0
        max_bet_spins = 0

        for gap in gaps:
            if gap > threshold:
                # We caught this ACC triple
                caught += 1
                max_bet_spins += gap - threshold
            else:
                # Gap was shorter than threshold, we bet max the whole gap
                # but we DID catch it since we were already betting max
                caught += 1
                max_bet_spins += gap

        # Actually, let me reconsider. If threshold=80 and gap=50:
        # - We start betting at spin 80 after last ACC
        # - But ACC came at spin 50, BEFORE we started betting
        # - We MISSED this one

        caught = 0
        max_bet_spins = 0
        for gap in gaps:
            if gap >= threshold:
                caught += 1
                max_bet_spins += gap - threshold
            else:
                # Missed - gap ended before threshold
                max_bet_spins += 0  # Never bet max during this gap

        total = len(gaps)
        catch_pct = caught / total * 100
        spins_per_hit = max_bet_spins / caught if caught > 0 else float('inf')
        # Efficiency: what % of max-bet spins are hits?
        eff = caught / max_bet_spins * 100 if max_bet_spins > 0 else 0

        print(f"  {threshold:>10} {caught:>8}/{total:<8} {catch_pct:>7.1f}% {max_bet_spins:>14} {spins_per_hit:>11.1f} {eff:>7.2f}%")

# ���════════════��══════════════════════════════════════════════════════════���══════
# D. DEBT-AWARE BETTING SIMULATION
# ══════���════════════════════���═══════════════════════════════════════════════════
print("\n" + "=" * 80)
print("D. DEBT-AWARE BETTING SIMULATION")
print("=" * 80)
print("Strategy: start betting at (target + debt_adjustment)")

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    acc_positions = [i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30)]
    gaps = [acc_positions[i+1] - acc_positions[i] for i in range(len(acc_positions)-1)]

    if len(gaps) < 5:
        continue

    # Try debt-aware threshold: threshold = max(20, median - cumulative_debt * factor)
    print(f"\n{name}:")
    for debt_factor in [0.3, 0.5, 0.7, 1.0]:
        caught = 0
        max_bet_spins = 0

        for i in range(len(gaps)):
            # Running median at this point
            history = gaps[:i+1]
            target = statistics.median(history) if i > 0 else gaps[0]

            # Cumulative debt at START of this gap
            debt = 0
            for j in range(i):
                prev_target = statistics.median(gaps[:j+1]) if j > 0 else gaps[0]
                debt += gaps[j] - prev_target

            # Adaptive threshold
            threshold = max(20, target - debt * debt_factor)

            if gaps[i] >= threshold:
                caught += 1
                max_bet_spins += gaps[i] - threshold
            # else: missed

        total = len(gaps)
        catch_pct = caught / total * 100
        spins_per_hit = max_bet_spins / caught if caught > 0 else float('inf')

        print(f"  debt_factor={debt_factor:.1f}: {caught}/{total} caught ({catch_pct:.1f}%) | "
              f"{max_bet_spins} max-bet spins | {spins_per_hit:.1f} spins/hit")

# ═══════════════════════════��═════════════════════════════���═════════════════════
# E. LOOK-BACK TRIGGER: "N spins with no ACC symbol" signal
# ═══════════════════════════════��═══════════════════════════════════════════════
print("\n" + "=" * 80)
print("E. DRY-STREAK TRIGGER (N spins with zero ACC symbols)")
print("=" * 80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    # For each spin, compute how many of the last N had acc_count=0
    # Then check: does a long dry streak of no-ACC predict imminent ACC triple?

    acc_positions = set(i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30))
    acc_pos_list = sorted(acc_positions)

    for dry_threshold in [5, 8, 10, 12, 15, 20]:
        trigger_positions = []
        dry_run = 0
        in_trigger = False

        for i, r in enumerate(data):
            if r['acc_count'] == 0 and r['tuple'] != (30, 30, 30):
                dry_run += 1
            else:
                dry_run = 0

            if dry_run >= dry_threshold and not in_trigger:
                trigger_positions.append(i)
                in_trigger = True
            elif dry_run < dry_threshold:
                in_trigger = False

        # For each trigger, find distance to next ACC triple
        catches = 0
        total_bet_spins = 0
        BET_WINDOW = 10  # bet for 10 spins after trigger

        for tp in trigger_positions:
            # Check if ACC triple appears within BET_WINDOW
            for j in range(tp, min(tp + BET_WINDOW, len(data))):
                if j in acc_positions:
                    catches += 1
                    total_bet_spins += j - tp + 1
                    break
            else:
                total_bet_spins += BET_WINDOW

        total_max_bet = len(trigger_positions) * BET_WINDOW
        spins_per_hit = total_max_bet / catches if catches > 0 else float('inf')

        if trigger_positions:
            print(f"  {name} dry>={dry_threshold:>2}: {len(trigger_positions):>4} triggers | "
                  f"{catches:>3} catches | "
                  f"{catches/len(trigger_positions)*100:.1f}% hit rate | "
                  f"{spins_per_hit:.1f} bet-spins/hit")

# ═══════════════════════════���══════════════════════════════���════════════════════
# F. COMBINED SIGNAL: debt-aware threshold + non-ACC-triple trigger
# ═��══════════════════════════════════════════════════════════════���══════════════
print("\n" + "=" * 80)
print("F. COMBINED SIGNAL: threshold + non-ACC-triple trigger")
print("=" * 80)
print("Strategy: after passing threshold, WAIT for non-ACC triple, then bet for K spins")

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    acc_positions_set = set(i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30))
    acc_pos_list = sorted(acc_positions_set)
    gaps = [acc_pos_list[i+1] - acc_pos_list[i] for i in range(len(acc_pos_list)-1)]

    if len(gaps) < 5:
        continue

    # Simulate spin by spin
    for threshold_pct in [0.3, 0.5, 0.6, 0.7]:
        for bet_window in [3, 5, 8, 10, 15]:
            target = statistics.median(gaps)
            threshold = int(target * threshold_pct)

            catches = 0
            total_bet_spins = 0
            bet_countdown = 0
            spins_since_acc = 0
            past_threshold = False

            for i in range(len(data)):
                if data[i]['tuple'] == (30, 30, 30):
                    if bet_countdown > 0:
                        catches += 1
                    spins_since_acc = 0
                    past_threshold = False
                    bet_countdown = 0
                    continue

                spins_since_acc += 1

                if bet_countdown > 0:
                    total_bet_spins += 1
                    bet_countdown -= 1
                    continue

                if spins_since_acc >= threshold and not past_threshold:
                    past_threshold = True

                # Trigger: past threshold + see a non-ACC triple
                if past_threshold and data[i]['is_triple'] and data[i]['tuple'] != (30, 30, 30):
                    bet_countdown = bet_window
                    total_bet_spins += 1
                    past_threshold = True  # Can re-trigger

            total_acc = len(acc_pos_list)
            spins_per_hit = total_bet_spins / catches if catches > 0 else float('inf')

            if catches > 0 and total_bet_spins > 0:
                # Only print promising combos
                if spins_per_hit < 80:
                    print(f"  {name} thresh={threshold_pct:.0%}*med({target:.0f})={threshold} win={bet_window}: "
                          f"{catches}/{total_acc} caught ({catches/total_acc*100:.1f}%) | "
                          f"{total_bet_spins} bet-spins | {spins_per_hit:.1f} spins/hit")

# ════════════════��═════════════════════════════════════════════════════════��════
# G. THE CRITICAL TEST: Is there a STRIP or just a weighted table?
# ═══════════════════════���═══════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("G. STRIP vs TABLE TEST — mutual information between consecutive spins")
print("=" * 80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    # Mutual information I(X_t; X_{t+1})
    # If strip: high MI (knowing current position tells you a lot about next)
    # If table: low MI (approximately independent draws)

    joint = Counter()
    marginal_x = Counter()
    marginal_y = Counter()
    total = len(data) - 1

    for i in range(total):
        x = data[i]['tuple']
        y = data[i+1]['tuple']
        joint[(x, y)] += 1
        marginal_x[x] += 1
        marginal_y[y] += 1

    mi = 0
    for (x, y), count in joint.items():
        p_xy = count / total
        p_x = marginal_x[x] / total
        p_y = marginal_y[y] / total
        if p_xy > 0 and p_x > 0 and p_y > 0:
            mi += p_xy * math.log2(p_xy / (p_x * p_y))

    # Entropy of X
    h_x = -sum((c/total) * math.log2(c/total) for c in marginal_x.values() if c > 0)

    print(f"\n{name}:")
    print(f"  H(X) = {h_x:.4f} bits")
    print(f"  I(X_t; X_{{t+1}}) = {mi:.4f} bits")
    print(f"  Normalized MI: {mi/h_x:.4f}")
    print(f"  If pure table (no strip): MI should be ~0")
    print(f"  If circular strip with small steps: MI should be high (>0.1)")

    # Also compute I(X_t; X_{t+2}) and I(X_t; X_{t+3})
    for lag in [2, 3, 5, 10]:
        joint_lag = Counter()
        for i in range(len(data) - lag):
            joint_lag[(data[i]['tuple'], data[i+lag]['tuple'])] += 1
        total_lag = len(data) - lag
        mi_lag = 0
        for (x, y), count in joint_lag.items():
            p_xy = count / total_lag
            p_x = marginal_x[x] / total  # approximate
            p_y = marginal_y[y] / total
            if p_xy > 0 and p_x > 0 and p_y > 0:
                mi_lag += p_xy * math.log2(p_xy / (p_x * p_y))
        print(f"  I(X_t; X_{{t+{lag}}}) = {mi_lag:.4f} bits")

# ═════════════════════════════════════════════════════��═════════════════════════
# H. THE KILLER: Reconstruct strip from transition probabilities
# ═════════════════���═════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("H. STRIP RECONSTRUCTION — greedy nearest-neighbor ordering")
print("=" * 80)

# Use combined data for better statistics
transitions = defaultdict(Counter)
for data in [acc1, acc2]:
    for i in range(len(data) - 1):
        transitions[data[i]['tuple']][data[i+1]['tuple']] += 1

# Build "affinity" matrix: how often does A follow B or B follow A?
affinity = defaultdict(int)
for a in unique_tuples:
    for b in unique_tuples:
        if a != b:
            affinity[(a,b)] = transitions[a].get(b, 0) + transitions[b].get(a, 0)

# Greedy chain: start from most common tuple, pick highest-affinity neighbor
visited = set()
chain = [unique_tuples[0]]  # Start from (1,1,1)
visited.add(unique_tuples[0])

for _ in range(n_tuples - 1):
    current = chain[-1]
    best = None
    best_score = -1
    for t in unique_tuples:
        if t not in visited:
            score = affinity[(current, t)]
            if score > best_score:
                best_score = score
                best = t
    if best:
        chain.append(best)
        visited.add(best)

print("\nReconstructed strip order (greedy adjacency):")
for i, t in enumerate(chain):
    # Show transition counts to next
    if i < len(chain) - 1:
        fwd = transitions[t].get(chain[i+1], 0)
        bwd = transitions[chain[i+1]].get(t, 0)
        print(f"  [{i:>2}] {t} -> fwd:{fwd} bwd:{bwd}")
    else:
        fwd = transitions[t].get(chain[0], 0)
        bwd = transitions[chain[0]].get(t, 0)
        print(f"  [{i:>2}] {t} -> (wrap to [0]) fwd:{fwd} bwd:{bwd}")

# Test this ordering: if it's a strip, step sizes should cluster
strip_map = {t: i for i, t in enumerate(chain)}
for name, data_set in [("Account 1", acc1), ("Account 2", acc2)]:
    steps = []
    for i in range(len(data_set) - 1):
        s = (strip_map[data_set[i+1]['tuple']] - strip_map[data_set[i]['tuple']]) % n_tuples
        steps.append(s)

    step_dist = Counter(steps)
    top_steps = step_dist.most_common(10)
    total_steps = len(steps)

    print(f"\n{name}: Step distribution on reconstructed strip")
    concentration = sum(c for _, c in top_steps[:3]) / total_steps * 100
    print(f"  Top 3 steps cover: {concentration:.1f}% of transitions")
    for s, cnt in top_steps:
        print(f"    Step {s:>2}: {cnt:>5} ({cnt/total_steps*100:.1f}%)")

# ════���═══════════════════════════��═════════════════════════════════════════���════
# I. FRESH ANGLE: Per-reel analysis (is any reel more predictable?)
# ══════════════════════════════════════════════════════════���════════════════════
print("\n" + "=" * 80)
print("I. PER-REEL PREDICTABILITY")
print("=" * 80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    for reel in ['r1', 'r2', 'r3']:
        # MI between consecutive values of this reel
        joint = Counter()
        marginal = Counter()
        for i in range(len(data) - 1):
            x = data[i][reel]
            y = data[i+1][reel]
            joint[(x,y)] += 1
            marginal[x] += 1

        total = len(data) - 1
        mi = 0
        for (x,y), count in joint.items():
            p_xy = count / total
            p_x = marginal[x] / total
            # Use marginal for y too (approximate)
            marginal_y_cnt = sum(1 for i in range(1, len(data)) if data[i][reel] == y)
            p_y = marginal_y_cnt / total
            if p_xy > 0 and p_x > 0 and p_y > 0:
                mi += p_xy * math.log2(p_xy / (p_x * p_y))

        h = -sum((c/total) * math.log2(c/total) for c in marginal.values() if c > 0)
        print(f"  {name} {reel}: H={h:.3f} bits, MI={mi:.4f} bits, MI/H={mi/h:.4f}")

# ���═══════════════════════════════════════════════���══════════════════════════════
# J. THE ULTIMATE SIMULATION: best-possible strategy
# ════���══════════════════════��════════════════════════════���══════════════════════
print("\n" + "=" * 80)
print("J. BEST STRATEGY SIMULATION — combining debt + threshold + window")
print("=" * 80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    acc_positions = [i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30)]
    gaps = [acc_positions[i+1] - acc_positions[i] for i in range(len(acc_positions)-1)]

    if len(gaps) < 10:
        continue

    # Simulate: use running median and gap-1 autocorrelation to predict
    print(f"\n{name} ({len(gaps)} gaps):")

    best_result = None
    best_params = None

    # Try combinations
    for min_offset in [0, 10, 20, 30]:  # Start betting at threshold - min_offset
        for threshold_pct in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
            caught = 0
            total_bet = 0

            for i in range(1, len(gaps)):
                history = gaps[:i]
                target = statistics.median(history)

                # Debt-adjusted threshold
                debt = sum(gaps[j] - statistics.median(gaps[:j+1]) for j in range(i))
                adjusted = target - debt * 0.3
                threshold = max(20, adjusted * threshold_pct) - min_offset

                if gaps[i] >= threshold:
                    caught += 1
                    total_bet += gaps[i] - threshold
                # Note: if gap < threshold, we missed it entirely

            if caught > 0:
                spins_per_hit = total_bet / caught
                catch_rate = caught / (len(gaps) - 1) * 100

                if best_result is None or spins_per_hit < best_result:
                    best_result = spins_per_hit
                    best_params = (threshold_pct, min_offset, caught, len(gaps)-1, catch_rate, total_bet)

    if best_params:
        tp, mo, c, t, cr, tb = best_params
        print(f"  Best pure-threshold: pct={tp}, offset={mo}")
        print(f"    {c}/{t} caught ({cr:.1f}%), {tb} bet-spins, {best_result:.1f} spins/hit")

    # Now try: threshold + bet window (stop betting after K spins if no hit)
    print(f"\n  With bet-window cap:")
    for threshold_pct in [0.3, 0.5, 0.7]:
        for window in [15, 20, 30, 50]:
            caught = 0
            total_bet = 0
            missed_early = 0
            missed_late = 0

            for i in range(1, len(gaps)):
                history = gaps[:i]
                target = statistics.median(history)
                threshold = max(20, target * threshold_pct)

                if gaps[i] < threshold:
                    missed_early += 1
                elif gaps[i] < threshold + window:
                    caught += 1
                    total_bet += gaps[i] - threshold
                else:
                    missed_late += 1
                    total_bet += window

            total = len(gaps) - 1
            if caught > 0:
                sph = total_bet / caught
                print(f"    pct={threshold_pct} win={window}: {caught}/{total} caught "
                      f"({caught/total*100:.1f}%, miss_early={missed_early}, miss_late={missed_late}) | "
                      f"{total_bet} bet | {sph:.1f} spins/hit")

# ══════════════════════════════════════════��════════════════════════════════════
# K. THE GAP-SIZE PREDICTOR: use last gap to predict next gap range
# ═══════════════════════���═══════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("K. GAP-SIZE PREDICTION (use prior gap to set strategy)")
print("=" * 80)

for name, data_set in [("Account 1", acc1), ("Account 2", acc2)]:
    acc_positions = [i for i, r in enumerate(data_set) if r['tuple'] == (30, 30, 30)]
    gaps = [acc_positions[i+1] - acc_positions[i] for i in range(len(acc_positions)-1)]

    if len(gaps) < 10:
        continue

    # After S gap (< median*0.5), what's next?
    # After M gap (0.5-1.5 * median), what's next?
    # After L gap (> median*1.5), what's next?
    target = statistics.median(gaps)

    categories = {'S': [], 'M': [], 'L': []}
    for i in range(len(gaps) - 1):
        if gaps[i] < target * 0.5:
            cat = 'S'
        elif gaps[i] < target * 1.5:
            cat = 'M'
        else:
            cat = 'L'
        categories[cat].append(gaps[i + 1])

    print(f"\n{name} (target={target:.0f}):")
    for cat in ['S', 'M', 'L']:
        vals = categories[cat]
        if vals:
            print(f"  After {cat} gap: n={len(vals)}, "
                  f"mean={statistics.mean(vals):.1f}, "
                  f"median={statistics.median(vals):.0f}, "
                  f"min={min(vals)}, max={max(vals)}")
            # Optimal threshold for this category
            sorted_vals = sorted(vals)
            for pctile in [25, 50, 75]:
                idx = int(len(sorted_vals) * pctile / 100)
                print(f"    P{pctile} = {sorted_vals[min(idx, len(sorted_vals)-1)]}")

    # Simulate adaptive strategy: different threshold based on prev gap category
    print(f"\n  Adaptive simulation (threshold=P25 of predicted distribution):")
    caught = 0
    total_bet = 0
    for i in range(1, len(gaps)):
        prev = gaps[i-1]
        if prev < target * 0.5:
            # After S, expect L -> high threshold
            threshold = max(20, statistics.median(categories.get('S', [target])) * 0.6)
        elif prev < target * 1.5:
            # After M, uncertain
            threshold = max(20, statistics.median(categories.get('M', [target])) * 0.5)
        else:
            # After L, expect S -> low threshold
            threshold = max(20, min(categories.get('L', [target])) if categories.get('L') else 20)

        if gaps[i] >= threshold:
            caught += 1
            total_bet += gaps[i] - threshold

    if caught > 0:
        print(f"    Caught: {caught}/{len(gaps)-1} ({caught/(len(gaps)-1)*100:.1f}%) | "
              f"{total_bet} bet-spins | {total_bet/caught:.1f} spins/hit")

print("\n" + "=" * 80)
print("PHASE 2 ANALYSIS COMPLETE")
print("=" * 80)
