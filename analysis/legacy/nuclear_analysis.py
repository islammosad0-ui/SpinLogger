"""
NUCLEAR ANALYSIS — 10K spins across 2 accounts
Goal: Find predictive signals for triple accumulation (30,30,30)
"""
import csv
import sys
from collections import Counter, defaultdict
from itertools import combinations
import math
import statistics

# ─── LOAD DATA ───────────────────────────────────────────────────────────────
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
            row['accum_delta'] = int(row['accum_delta']) if row['accum_delta'] else 0
            row['seq'] = int(row['seq'])
            row['tuple'] = (row['r1'], row['r2'], row['r3'])
            row['outcome'] = row['spin_result']
            rows.append(row)
    return rows

acc1 = load_csv(r"C:\Users\Islam\Downloads\Account 1 spin_history_2026-04-05.csv")
acc2 = load_csv(r"C:\Users\Islam\Downloads\Account 2 spin_history_2026-04-04.csv")

print(f"Account 1: {len(acc1)} spins (mission {acc1[0]['accum_mission']})")
print(f"Account 2: {len(acc2)} spins (mission {acc2[0]['accum_mission']})")

# ─── 1. OUTCOME TUPLE CENSUS ─────────────────────────────────────────────────
print("\n" + "="*80)
print("1. OUTCOME TUPLE CENSUS")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    tuples = Counter(r['tuple'] for r in data)
    print(f"\n{name}: {len(tuples)} distinct tuples")
    print(f"{'Tuple':<15} {'Count':>6} {'Pct':>7} {'Triple':>7} {'Result'}")
    for t, cnt in tuples.most_common():
        pct = cnt / len(data) * 100
        is_trip = "YES" if t[0] == t[1] == t[2] else ""
        # find result name
        for r in data:
            if r['tuple'] == t:
                res = r['spin_result']
                break
        print(f"({t[0]:>2},{t[1]:>2},{t[2]:>2})   {cnt:>6} {pct:>6.2f}% {is_trip:>7} {res}")

# Combined
all_data = acc1 + acc2
all_tuples = Counter(r['tuple'] for r in all_data)
print(f"\nCOMBINED: {len(all_tuples)} distinct tuples across {len(all_data)} spins")

# ─── 2. ACC GAP ANALYSIS (gap = spins between consecutive 30,30,30) ──────────
print("\n" + "="*80)
print("2. ACC TRIPLE (30,30,30) GAP ANALYSIS")
print("="*80)

def extract_acc_gaps(data):
    """Extract gaps between 30,30,30 triples"""
    acc_positions = []
    for i, r in enumerate(data):
        if r['tuple'] == (30, 30, 30):
            acc_positions.append(i)
    gaps = []
    for i in range(1, len(acc_positions)):
        gaps.append(acc_positions[i] - acc_positions[i-1])
    return acc_positions, gaps

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, gaps = extract_acc_gaps(data)
    print(f"\n{name}: {len(positions)} ACC triples, {len(gaps)} gaps")
    if gaps:
        print(f"  Mean: {statistics.mean(gaps):.1f}")
        print(f"  Median: {statistics.median(gaps):.1f}")
        print(f"  Stdev: {statistics.stdev(gaps):.1f}" if len(gaps) > 1 else "")
        print(f"  Min: {min(gaps)}, Max: {max(gaps)}")
        print(f"  Gaps: {gaps}")

# ─── 3. ALL TRIPLE GAP ANALYSIS (any triple, not just ACC) ───────────────────
print("\n" + "="*80)
print("3. ALL TRIPLE ANALYSIS")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    triples = [(i, r['tuple']) for i, r in enumerate(data) if r['is_triple']]
    triple_types = Counter(t[1] for t in triples)
    print(f"\n{name}: {len(triples)} triples out of {len(data)} spins ({len(triples)/len(data)*100:.1f}%)")
    print(f"  Triple types: {dict(triple_types.most_common())}")

    # Gap between ANY triples
    if len(triples) > 1:
        any_gaps = [triples[i+1][0] - triples[i][0] for i in range(len(triples)-1)]
        print(f"  Gaps between any triple: mean={statistics.mean(any_gaps):.1f}, median={statistics.median(any_gaps):.1f}, min={min(any_gaps)}, max={max(any_gaps)}")

# ─── 4. TRANSITION MATRIX — what tuple follows what tuple ─────────────────────
print("\n" + "="*80)
print("4. TRANSITION ANALYSIS (1st order Markov)")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    transitions = defaultdict(Counter)
    for i in range(len(data) - 1):
        transitions[data[i]['tuple']][data[i+1]['tuple']] += 1

    # Focus: what follows each triple type?
    print(f"\n{name} — After each triple, what comes next?")
    for trip_tuple in [(1,1,1), (2,2,2), (3,3,3), (4,4,4), (5,5,5), (6,6,6), (30,30,30)]:
        if trip_tuple in transitions:
            followers = transitions[trip_tuple]
            total = sum(followers.values())
            print(f"  After {trip_tuple}: {total} transitions")
            for t, cnt in followers.most_common(5):
                print(f"    -> {t}: {cnt} ({cnt/total*100:.1f}%)")

# ─── 5. PRE-ACC-TRIPLE FINGERPRINT ───────────────────────────────────────────
print("\n" + "="*80)
print("5. PRE-ACC-TRIPLE FINGERPRINT (20 spins before 30,30,30)")
print("="*80)

WINDOW = 20
for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, gaps = extract_acc_gaps(data)

    # Count tuple frequencies at each position relative to ACC triple
    pos_counts = [Counter() for _ in range(WINDOW)]
    triple_at_pos = [0] * WINDOW  # any triple at position -N
    acc_at_pos = [0] * WINDOW     # any ACC symbol at position -N

    valid = 0
    for p in positions:
        if p >= WINDOW:
            valid += 1
            for offset in range(WINDOW):
                idx = p - WINDOW + offset
                t = data[idx]['tuple']
                pos_counts[offset][t] += 1
                if data[idx]['is_triple']:
                    triple_at_pos[offset] += 1
                if data[idx]['acc_count'] > 0:
                    acc_at_pos[offset] += 1

    print(f"\n{name}: {valid} ACC triples with full {WINDOW}-spin window")
    print(f"  Position (before ACC): Triple% | ACC-symbol% | Top tuple")
    for offset in range(WINDOW):
        pos_from_end = WINDOW - offset
        trip_pct = triple_at_pos[offset] / valid * 100 if valid else 0
        acc_pct = acc_at_pos[offset] / valid * 100 if valid else 0
        top = pos_counts[offset].most_common(1)[0] if pos_counts[offset] else (None, 0)
        print(f"  -{pos_from_end:>2}: {trip_pct:>5.1f}% triple | {acc_pct:>5.1f}% has ACC | top={top[0]} ({top[1]})")

# ─── 6. ACCUMULATION BUILDUP PATTERN ─────────────────────────────────────────
print("\n" + "="*80)
print("6. ACCUMULATION BUILDUP PATTERN (accum_delta before 30,30,30)")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, gaps = extract_acc_gaps(data)

    print(f"\n{name}: ACC deltas in the 10 spins before each 30,30,30")
    for idx, p in enumerate(positions[:10]):  # show first 10
        if p >= 10:
            deltas = [data[p-10+j]['accum_delta'] for j in range(11)]
            tuples = [data[p-10+j]['tuple'] for j in range(11)]
            # Show acc_count too
            acc_counts = [data[p-10+j]['acc_count'] for j in range(11)]
            print(f"  Gap #{idx} (pos {p}): deltas={deltas}")
            print(f"    acc_counts={acc_counts}")

# ─── 7. NON-ACC TRIPLE AS PRECURSOR SIGNAL ────────────────────────────────────
print("\n" + "="*80)
print("7. NON-ACC TRIPLE DISTANCE TO NEXT ACC TRIPLE")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, _ = extract_acc_gaps(data)
    pos_set = set(positions)

    # For each non-ACC triple, how far to next ACC triple?
    non_acc_triples = [(i, r['tuple']) for i, r in enumerate(data)
                        if r['is_triple'] and r['tuple'] != (30,30,30)]

    distances = defaultdict(list)
    for i, t in non_acc_triples:
        # find next ACC triple
        for p in positions:
            if p > i:
                distances[t].append(p - i)
                break

    print(f"\n{name}:")
    for t in sorted(distances.keys()):
        d = distances[t]
        print(f"  After {t}: mean dist to next ACC = {statistics.mean(d):.1f}, "
              f"median = {statistics.median(d):.1f}, n={len(d)}")

# ─── 8. TRIPLE SEQUENCE PATTERNS ─────────────────────────────────────────────
print("\n" + "="*80)
print("8. TRIPLE SEQUENCE (order of triple types)")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    triple_seq = []
    for i, r in enumerate(data):
        if r['is_triple']:
            t = r['tuple']
            label = 'ACC' if t == (30,30,30) else f"{r['reel_1'][:3]}"
            triple_seq.append((i, label, t))

    print(f"\n{name}: Triple sequence ({len(triple_seq)} triples)")
    # Show the sequence of triple types
    labels = [s[1] for s in triple_seq]
    print(f"  Sequence: {' '.join(labels)}")

    # Bigrams of triple types
    bigrams = Counter()
    for i in range(len(labels) - 1):
        bigrams[(labels[i], labels[i+1])] += 1
    print(f"\n  Triple-to-triple bigrams:")
    for bg, cnt in bigrams.most_common():
        print(f"    {bg[0]:>4} -> {bg[1]:<4}: {cnt}")

# ─── 9. GAP AUTOCORRELATION (does gap N predict gap N+1?) ────────────────────
print("\n" + "="*80)
print("9. GAP AUTOCORRELATION")
print("="*80)

def autocorr(gaps, lag=1):
    if len(gaps) <= lag + 1:
        return None
    n = len(gaps)
    mean = statistics.mean(gaps)
    var = statistics.variance(gaps)
    if var == 0:
        return 0
    cov = sum((gaps[i] - mean) * (gaps[i+lag] - mean) for i in range(n - lag)) / (n - lag)
    return cov / var

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    _, gaps = extract_acc_gaps(data)
    if len(gaps) > 5:
        print(f"\n{name} ACC gaps (n={len(gaps)}):")
        for lag in range(1, min(6, len(gaps))):
            r = autocorr(gaps, lag)
            if r is not None:
                print(f"  Lag {lag}: r = {r:.3f}")

        # Also check: gap vs previous gap (scatter data)
        print(f"\n  Gap pairs (prev -> next):")
        for i in range(len(gaps)-1):
            bucket = "S" if gaps[i] < 60 else ("M" if gaps[i] < 120 else "L")
            bucket_next = "S" if gaps[i+1] < 60 else ("M" if gaps[i+1] < 120 else "L")
            print(f"    {gaps[i]:>4} ({bucket}) -> {gaps[i+1]:>4} ({bucket_next})")

# ─── 10. DEBT MODEL (gap vs cumulative deviation from target) ─────────────────
print("\n" + "="*80)
print("10. DEBT MODEL — running median calibration")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    _, gaps = extract_acc_gaps(data)
    if len(gaps) < 3:
        print(f"\n{name}: Not enough gaps ({len(gaps)})")
        continue

    print(f"\n{name}: {len(gaps)} gaps")

    # Running median target
    debt = 0
    for i in range(len(gaps)):
        history = gaps[:i+1]
        target = statistics.median(history)
        deviation = gaps[i] - target
        debt += deviation

        if i < 30 or i >= len(gaps) - 5:
            bucket = "S" if gaps[i] < 60 else ("M" if gaps[i] < 120 else "L")
            print(f"  Gap {i:>2}: {gaps[i]:>4} ({bucket}) | target={target:>6.1f} | deviation={deviation:>+7.1f} | cum_debt={debt:>+8.1f}")

    # Final stats
    final_target = statistics.median(gaps)
    print(f"\n  Final target (median of all): {final_target:.1f}")

    # Correlation: gap[i] vs debt_before[i]
    debts_before = []
    d = 0
    for i in range(len(gaps)):
        debts_before.append(d)
        target = statistics.median(gaps[:i+1]) if i > 0 else gaps[0]
        d += gaps[i] - target

    if len(gaps) > 5:
        mean_g = statistics.mean(gaps)
        mean_d = statistics.mean(debts_before)
        cov = sum((gaps[i]-mean_g)*(debts_before[i]-mean_d) for i in range(len(gaps))) / len(gaps)
        std_g = statistics.stdev(gaps)
        std_d = statistics.stdev(debts_before) if statistics.stdev(debts_before) > 0 else 1
        corr = cov / (std_g * std_d)
        print(f"  Correlation (gap vs debt_before): {corr:.3f}")

# ─── 11. SECOND-ORDER MARKOV ON TUPLES ───────────────────────────────────────
print("\n" + "="*80)
print("11. SECOND-ORDER MARKOV (tuple pair -> next tuple)")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    # Only focus on: given last 2 tuples, what's P(next = ACC triple)?
    second_order = defaultdict(lambda: {'acc': 0, 'total': 0})
    for i in range(2, len(data)):
        key = (data[i-2]['tuple'], data[i-1]['tuple'])
        second_order[key]['total'] += 1
        if data[i]['tuple'] == (30, 30, 30):
            second_order[key]['acc'] += 1

    # Find pairs with highest ACC probability (min 3 occurrences)
    acc_predictors = []
    for key, v in second_order.items():
        if v['total'] >= 3 and v['acc'] > 0:
            acc_predictors.append((key, v['acc'], v['total'], v['acc']/v['total']))

    acc_predictors.sort(key=lambda x: -x[3])

    print(f"\n{name}: Top tuple-pairs predicting next ACC triple (min 3 samples):")
    base_rate = sum(1 for r in data if r['tuple'] == (30,30,30)) / len(data)
    print(f"  Base rate: {base_rate*100:.2f}%")
    for key, hits, total, prob in acc_predictors[:20]:
        lift = prob / base_rate if base_rate > 0 else 0
        print(f"  {key[0]} -> {key[1]}: {hits}/{total} = {prob*100:.1f}% ({lift:.1f}x lift)")

# ─── 12. POSITION-IN-GAP ANALYSIS ────────────────────────────────────────────
print("\n" + "="*80)
print("12. POSITION-IN-GAP ANALYSIS (outcome distribution changes through gap)")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, gaps = extract_acc_gaps(data)
    if len(positions) < 2:
        continue

    # For each spin, compute its position within the current ACC gap (0.0 = just after ACC, 1.0 = just before next ACC)
    # Divide each gap into quartiles
    quartile_outcomes = [Counter() for _ in range(4)]  # Q1=early, Q4=late
    quartile_triples = [0, 0, 0, 0]
    quartile_totals = [0, 0, 0, 0]
    quartile_acc_symbols = [0, 0, 0, 0]  # spins with any acc symbol

    for g_idx in range(len(positions) - 1):
        start = positions[g_idx] + 1
        end = positions[g_idx + 1]
        gap_len = end - start
        if gap_len < 4:
            continue

        for spin_idx in range(start, end):
            frac = (spin_idx - start) / gap_len  # 0.0 to ~1.0
            q = min(3, int(frac * 4))
            quartile_outcomes[q][data[spin_idx]['tuple']] += 1
            quartile_totals[q] += 1
            if data[spin_idx]['is_triple']:
                quartile_triples[q] += 1
            if data[spin_idx]['acc_count'] > 0:
                quartile_acc_symbols[q] += 1

    print(f"\n{name}: Outcome distribution by quartile within ACC gap")
    for q in range(4):
        if quartile_totals[q] > 0:
            trip_pct = quartile_triples[q] / quartile_totals[q] * 100
            acc_pct = quartile_acc_symbols[q] / quartile_totals[q] * 100
            print(f"  Q{q+1} ({'early' if q<2 else 'late ':>5}): {quartile_totals[q]:>5} spins | "
                  f"{trip_pct:>5.1f}% triple | {acc_pct:>5.1f}% has ACC symbol | "
                  f"{len(quartile_outcomes[q])} distinct tuples")

# ─── 13. SINGLE-ACC SYMBOL DENSITY BEFORE ACC TRIPLE ─────────────────────────
print("\n" + "="*80)
print("13. SINGLE-ACC DENSITY (acc_count > 0 but not 30,30,30) BEFORE ACC TRIPLE")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, _ = extract_acc_gaps(data)

    # For each ACC triple, count single-ACC spins in last N windows
    windows = [5, 10, 15, 20]
    for w in windows:
        counts = []
        for p in positions:
            if p >= w:
                c = sum(1 for j in range(p-w, p) if data[j]['acc_count'] > 0 and data[j]['tuple'] != (30,30,30))
                counts.append(c)
        if counts:
            print(f"\n{name} last-{w} spins before ACC triple: "
                  f"mean={statistics.mean(counts):.2f}, "
                  f"median={statistics.median(counts):.1f}, "
                  f"min={min(counts)}, max={max(counts)}")
            # Compare with random baseline
            total_single_acc = sum(1 for r in data if r['acc_count'] > 0 and r['tuple'] != (30,30,30))
            baseline = total_single_acc / len(data) * w
            print(f"    Baseline (random): {baseline:.2f} | Lift: {statistics.mean(counts)/baseline:.2f}x" if baseline > 0 else "")

# ─── 14. BET MULTIPLIER CORRELATION ──────────────────────────────────────────
print("\n" + "="*80)
print("14. BET MULTIPLIER ANALYSIS")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    bet_dist = Counter(r['bet_multiplier'] for r in data)
    print(f"\n{name}: Bet multiplier distribution")
    for bet, cnt in sorted(bet_dist.items()):
        acc_at_bet = sum(1 for r in data if r['bet_multiplier'] == bet and r['tuple'] == (30,30,30))
        pct = acc_at_bet / cnt * 100 if cnt > 0 else 0
        print(f"  Bet {bet:>5}: {cnt:>5} spins | {acc_at_bet} ACC triples ({pct:.2f}%)")

# ─── 15. STREAK ANALYSIS (consecutive same outcome) ──────────────────────────
print("\n" + "="*80)
print("15. STREAK ANALYSIS")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    # Track streaks of same tuple
    streaks = []
    current_tuple = None
    current_len = 0
    for r in data:
        if r['tuple'] == current_tuple:
            current_len += 1
        else:
            if current_tuple is not None:
                streaks.append((current_tuple, current_len))
            current_tuple = r['tuple']
            current_len = 1
    if current_tuple:
        streaks.append((current_tuple, current_len))

    long_streaks = [(t, l) for t, l in streaks if l >= 2]
    print(f"\n{name}: {len(long_streaks)} streaks of length >= 2")
    streak_len_dist = Counter(l for _, l in streaks)
    print(f"  Streak length distribution: {dict(sorted(streak_len_dist.items()))}")

# ─── 16. TRIPLE CLUSTERING — inter-triple gaps ───────────────────────────────
print("\n" + "="*80)
print("16. TRIPLE CLUSTERING (ALL triples, not just ACC)")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    triple_positions = [i for i, r in enumerate(data) if r['is_triple']]
    inter_gaps = [triple_positions[i+1] - triple_positions[i] for i in range(len(triple_positions)-1)]

    if inter_gaps:
        # Classify: burst (gap <= 3), normal, dry (gap >= 20)
        bursts = sum(1 for g in inter_gaps if g <= 3)
        normal = sum(1 for g in inter_gaps if 4 <= g <= 15)
        dry = sum(1 for g in inter_gaps if g > 15)
        print(f"\n{name}: {len(inter_gaps)} inter-triple gaps")
        print(f"  Burst (<=3): {bursts} ({bursts/len(inter_gaps)*100:.1f}%)")
        print(f"  Normal (4-15): {normal} ({normal/len(inter_gaps)*100:.1f}%)")
        print(f"  Dry (>15): {dry} ({dry/len(inter_gaps)*100:.1f}%)")

        # After a burst, what's next? After dry, what's next?
        for i in range(len(inter_gaps) - 1):
            pass  # We'll do this in the Markov section

        # Does a burst of non-ACC triples predict ACC is coming?
        # For each non-ACC triple that's part of a burst, distance to next ACC
        positions, _ = extract_acc_gaps(data)
        pos_set = set(positions)

        burst_to_acc = []
        for i in range(len(triple_positions) - 1):
            if triple_positions[i+1] - triple_positions[i] <= 3:
                # This is a burst pair
                burst_end = triple_positions[i+1]
                if burst_end not in pos_set:
                    # Non-ACC triple in burst, find distance to next ACC
                    for p in positions:
                        if p > burst_end:
                            burst_to_acc.append(p - burst_end)
                            break

        if burst_to_acc:
            print(f"\n  After non-ACC triple burst: distance to next ACC triple")
            print(f"    Mean: {statistics.mean(burst_to_acc):.1f}, Median: {statistics.median(burst_to_acc):.1f}, n={len(burst_to_acc)}")

# ─── 17. THE STRIP HYPOTHESIS — position tracking ────────────────────────────
print("\n" + "="*80)
print("17. STRIP POSITION TRACKING")
print("="*80)

# If the game uses a circular strip of N outcomes, consecutive spins advance by
# a fixed or variable step. Let's look for patterns in tuple sequences.
for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    tuples_list = [r['tuple'] for r in data]
    unique_tuples = list(set(tuples_list))
    tuple_to_idx = {t: i for i, t in enumerate(unique_tuples)}
    idx_seq = [tuple_to_idx[t] for t in tuples_list]

    # Check if there's a fixed step size (modular arithmetic)
    # Compute differences between consecutive tuple indices
    diffs = [(idx_seq[i+1] - idx_seq[i]) % len(unique_tuples) for i in range(len(idx_seq)-1)]
    diff_dist = Counter(diffs)

    print(f"\n{name}: {len(unique_tuples)} unique tuples")
    print(f"  Top 10 step sizes (mod {len(unique_tuples)}):")
    for d, cnt in diff_dist.most_common(10):
        print(f"    Step {d:>2}: {cnt:>5} ({cnt/len(diffs)*100:.1f}%)")

    # Also check: can we find repeating subsequences?
    # Look for the longest repeated sequence of tuples
    for seq_len in [3, 4, 5]:
        subseqs = Counter()
        for i in range(len(tuples_list) - seq_len):
            subseqs[tuple(tuples_list[i:i+seq_len])] += 1
        repeats = {k: v for k, v in subseqs.items() if v >= 3}
        if repeats:
            print(f"\n  Repeated {seq_len}-tuple sequences (>= 3 times):")
            for seq, cnt in sorted(repeats.items(), key=lambda x: -x[1])[:5]:
                print(f"    {seq}: {cnt} times")

# ─── 18. ACC ACCUMULATION RATE BEFORE TRIPLE ──────────────────────────────────
print("\n" + "="*80)
print("18. ACCUMULATION RATE ANALYSIS (how accum_pct changes through gap)")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, gaps = extract_acc_gaps(data)

    if len(positions) < 2:
        continue

    print(f"\n{name}: accum_pct trajectory through each gap")
    for g_idx in range(min(5, len(positions) - 1)):
        start = positions[g_idx]
        end = positions[g_idx + 1]
        pcts = []
        for j in range(start, end + 1):
            try:
                pct = float(data[j]['accum_pct'])
                pcts.append(pct)
            except:
                pass
        if pcts:
            print(f"  Gap {g_idx}: {pcts[0]:.1f}% -> {pcts[-1]:.1f}% over {end-start} spins (delta={pcts[-1]-pcts[0]:.1f}%)")

# ─── 19. ENTROPY ANALYSIS ────────────────────────────────────────────────────
print("\n" + "="*80)
print("19. ENTROPY ANALYSIS (does prediction get easier near ACC triple?)")
print("="*80)

def shannon_entropy(counter):
    total = sum(counter.values())
    if total == 0:
        return 0
    return -sum((c/total) * math.log2(c/total) for c in counter.values() if c > 0)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, gaps = extract_acc_gaps(data)
    if len(positions) < 3:
        continue

    # Compute entropy in 5-spin windows at different positions relative to ACC triple
    window = 5
    offsets = [-20, -15, -10, -5, -3, -1]

    print(f"\n{name}: Entropy of next-tuple distribution at offsets from ACC triple")
    for offset in offsets:
        counts = Counter()
        valid = 0
        for p in positions:
            idx = p + offset
            if 0 <= idx < len(data) - 1:
                counts[data[idx + 1]['tuple']] += 1
                valid += 1
        if valid > 5:
            ent = shannon_entropy(counts)
            print(f"  Offset {offset:>3}: entropy = {ent:.3f} bits (from {valid} samples, {len(counts)} distinct outcomes)")

    # Baseline entropy
    baseline = Counter(r['tuple'] for r in data)
    print(f"  Baseline: entropy = {shannon_entropy(baseline):.3f} bits ({len(baseline)} distinct outcomes)")

# ─── 20. THE KILLER QUESTION: WHAT UNIQUELY PRECEDES 30,30,30? ───────────────
print("\n" + "="*80)
print("20. UNIQUE PRECURSOR ANALYSIS — what ONLY appears before ACC triples?")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, _ = extract_acc_gaps(data)

    # For each window size, find tuples/patterns that appear disproportionately before ACC
    for lookback in [3, 5, 8]:
        before_acc = Counter()
        before_other = Counter()  # before any non-ACC-triple spin

        for i in range(lookback, len(data)):
            window_tuples = tuple(data[j]['tuple'] for j in range(i - lookback, i))
            if data[i]['tuple'] == (30, 30, 30):
                before_acc[window_tuples] += 1
            else:
                before_other[window_tuples] += 1

        # This generates too many patterns. Instead, use features:
        # Feature: count of each reel value in the lookback window
        before_acc_feat = Counter()
        before_other_feat = Counter()

        for i in range(lookback, len(data)):
            # Feature: number of spins with acc_count > 0 in window
            acc_in_window = sum(1 for j in range(i - lookback, i) if data[j]['acc_count'] > 0)
            # Feature: number of triples in window
            trip_in_window = sum(1 for j in range(i - lookback, i) if data[j]['is_triple'])

            feat = (acc_in_window, trip_in_window)
            if data[i]['tuple'] == (30, 30, 30):
                before_acc_feat[feat] += 1
            else:
                before_other_feat[feat] += 1

        print(f"\n{name} lookback={lookback}: (acc_spins, triple_spins) -> ACC probability")
        for feat in sorted(set(list(before_acc_feat.keys()) + list(before_other_feat.keys()))):
            hits = before_acc_feat.get(feat, 0)
            total = hits + before_other_feat.get(feat, 0)
            if total >= 5:
                pct = hits / total * 100
                base = sum(before_acc_feat.values()) / (sum(before_acc_feat.values()) + sum(before_other_feat.values())) * 100
                lift = pct / base if base > 0 else 0
                print(f"    {feat}: {hits}/{total} = {pct:.2f}% ({lift:.1f}x lift)")

# ─── 21. THE r1 COLUMN ANALYSIS (reel 1 = 30 means ACC symbol) ───────────────
print("\n" + "="*80)
print("21. REEL VALUE DISTRIBUTIONS")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    for reel in ['r1', 'r2', 'r3']:
        dist = Counter(r[reel] for r in data)
        print(f"\n{name} {reel}: {dict(sorted(dist.items()))}")

# ─── 22. CONSECUTIVE ACC SYMBOL RUNS ─────────────────────────────────────────
print("\n" + "="*80)
print("22. CONSECUTIVE SPINS WITH ACC SYMBOLS (building toward 30,30,30)")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, _ = extract_acc_gaps(data)

    # Before each ACC triple, how many consecutive spins had at least one ACC symbol?
    print(f"\n{name}: ACC symbol run-up before each 30,30,30")
    for p in positions[:15]:
        run = 0
        for j in range(p - 1, -1, -1):
            if data[j]['acc_count'] > 0:
                run += 1
            else:
                break
        print(f"  Position {p}: {run} consecutive ACC-symbol spins before the triple")

# ─── 23. CROSS-ACCOUNT TUPLE COMPARISON ──────────────────────────────────────
print("\n" + "="*80)
print("23. CROSS-ACCOUNT TUPLE COMPARISON")
print("="*80)

tuples1 = set(r['tuple'] for r in acc1)
tuples2 = set(r['tuple'] for r in acc2)
shared = tuples1 & tuples2
only1 = tuples1 - tuples2
only2 = tuples2 - tuples1

print(f"Account 1: {len(tuples1)} tuples")
print(f"Account 2: {len(tuples2)} tuples")
print(f"Shared: {len(shared)}")
print(f"Only Account 1: {only1}")
print(f"Only Account 2: {only2}")

# Compare frequencies of shared tuples
print(f"\nFrequency comparison (shared tuples):")
freq1 = Counter(r['tuple'] for r in acc1)
freq2 = Counter(r['tuple'] for r in acc2)
print(f"{'Tuple':<15} {'Acc1 %':>8} {'Acc2 %':>8} {'Ratio':>8}")
for t in sorted(shared):
    p1 = freq1[t] / len(acc1) * 100
    p2 = freq2[t] / len(acc2) * 100
    ratio = p1 / p2 if p2 > 0 else float('inf')
    print(f"({t[0]:>2},{t[1]:>2},{t[2]:>2})   {p1:>7.2f}% {p2:>7.2f}% {ratio:>7.2f}")

# ─── 24. SPECTRAL ANALYSIS ON GAP SEQUENCE ───────────────────────────────────
print("\n" + "="*80)
print("24. GAP SEQUENCE PERIODICITY (manual DFT-like analysis)")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    _, gaps = extract_acc_gaps(data)
    if len(gaps) < 10:
        print(f"\n{name}: only {len(gaps)} gaps, need more for periodicity")
        continue

    # Check for periods 2 through 8
    print(f"\n{name} ({len(gaps)} gaps):")
    mean_gap = statistics.mean(gaps)

    for period in range(2, min(9, len(gaps)//2)):
        # Split gaps into groups by position mod period
        groups = [[] for _ in range(period)]
        for i, g in enumerate(gaps):
            groups[i % period].append(g)

        # If there's a real period, groups should have different means
        group_means = [statistics.mean(grp) if grp else 0 for grp in groups]
        if all(len(g) >= 2 for g in groups):
            # Compute between-group variance vs within-group variance (crude ANOVA)
            between = sum(len(g) * (statistics.mean(g) - mean_gap)**2 for g in groups) / (period - 1)
            within = sum(sum((x - statistics.mean(g))**2 for x in g) for g in groups) / (len(gaps) - period)
            f_stat = between / within if within > 0 else 0
            print(f"  Period {period}: group means = {[f'{m:.0f}' for m in group_means]} | F = {f_stat:.2f}")

# ─── 25. THE MEGA PATTERN: LOOK AT ACCUM_PCT THRESHOLDS ──────────────────────
print("\n" + "="*80)
print("25. ACCUM_PCT AT TIME OF ACC TRIPLE")
print("="*80)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    positions, _ = extract_acc_gaps(data)

    pcts = []
    for p in positions:
        try:
            # The spin BEFORE the ACC triple
            if p > 0:
                pct_before = float(data[p-1]['accum_pct'])
                pct_at = float(data[p]['accum_pct'])
                delta = float(data[p]['accum_delta'])
                pcts.append((pct_before, pct_at, delta))
        except:
            pass

    print(f"\n{name}: accum_pct just before each 30,30,30")
    for pb, pa, d in pcts:
        print(f"  Before: {pb:.1f}% -> After: {pa:.1f}% (delta={d})")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
