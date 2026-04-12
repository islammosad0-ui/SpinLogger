"""
HYPOTHESIS: the game triggers 30,30,30 after a fixed number of ACC SYMBOLS,
not after a fixed number of spins.

If true: counting ACC symbols within a gap = precision predictor.
"""
import csv, statistics, math
from collections import Counter

def load_csv(path):
    rows = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['r1'] = int(row['r1'])
            row['r2'] = int(row['r2'])
            row['r3'] = int(row['r3'])
            row['is_triple'] = row['is_triple'].lower() == 'true'
            row['tuple'] = (row['r1'], row['r2'], row['r3'])
            row['acc_count'] = int(row['acc_count'])
            row['accum_delta'] = int(row['accum_delta']) if row['accum_delta'] else 0
            rows.append(row)
    return rows

acc1 = load_csv(r"C:\Users\Islam\Downloads\Account 1 spin_history_2026-04-05.csv")
acc2 = load_csv(r"C:\Users\Islam\Downloads\Account 2 spin_history_2026-04-04.csv")

# ── COUNT ACC SYMBOLS PER GAP ─────────────────────────────────────────────────
print("=" * 90)
print("TEST 1: ACC SYMBOL COUNT PER GAP")
print("=" * 90)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    acc_positions = [i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30)]

    gap_profiles = []
    for g in range(len(acc_positions) - 1):
        start = acc_positions[g] + 1
        end = acc_positions[g + 1]
        gap_len = end - start

        # Count different ACC-bearing outcomes
        r1_30 = 0        # r1 == 30 (any)
        r1r2_30 = 0      # r1==30 AND r2==30 (double/triple)
        acc_symbols = 0   # total ACC symbols: r1=30 counts 1, r2=30 counts 1, r3=30 counts 1
        acc_events = 0    # spins with acc_count > 0
        acc_delta_sum = 0 # total accumulation delta

        for j in range(start, end):
            r = data[j]
            s = 0
            if r['r1'] == 30: s += 1
            if r['r2'] == 30: s += 1
            if r['r3'] == 30: s += 1
            acc_symbols += s
            if r['r1'] == 30: r1_30 += 1
            if r['r1'] == 30 and r['r2'] == 30: r1r2_30 += 1
            if r['acc_count'] > 0: acc_events += 1
            acc_delta_sum += r['accum_delta']

        gap_profiles.append({
            'gap': gap_len, 'r1_30': r1_30, 'r1r2_30': r1r2_30,
            'acc_symbols': acc_symbols, 'acc_events': acc_events,
            'acc_delta': acc_delta_sum
        })

    # KEY TEST: is acc_symbols roughly constant across gaps?
    sym_counts = [p['acc_symbols'] for p in gap_profiles]
    r1_counts = [p['r1_30'] for p in gap_profiles]
    event_counts = [p['acc_events'] for p in gap_profiles]
    gap_lens = [p['gap'] for p in gap_profiles]

    print(f"\n{name} ({len(gap_profiles)} gaps):")

    for label, counts in [("ACC symbols (r1+r2+r3=30)", sym_counts),
                           ("r1=30 outcomes", r1_counts),
                           ("acc_events (acc_count>0)", event_counts),
                           ("gap length (spins)", gap_lens)]:
        cv = statistics.stdev(counts) / statistics.mean(counts) if statistics.mean(counts) > 0 else 0
        print(f"\n  {label}:")
        print(f"    Mean={statistics.mean(counts):.1f}, Median={statistics.median(counts):.0f}, "
              f"Stdev={statistics.stdev(counts):.1f}, CV={cv:.3f}")
        print(f"    Min={min(counts)}, Max={max(counts)}")
        print(f"    Values: {counts[:20]}...")

    # CORRELATION: acc_symbols vs gap_length
    # If constant: correlation should be ~0 (symbols don't depend on gap)
    # If proportional: correlation should be ~1.0 (more spins = more symbols)
    def corr(x, y):
        n = len(x)
        mx, my = statistics.mean(x), statistics.mean(y)
        sx, sy = statistics.stdev(x), statistics.stdev(y)
        if sx == 0 or sy == 0: return 0
        return sum((x[i]-mx)*(y[i]-my) for i in range(n)) / (n * sx * sy)

    print(f"\n  CORRELATIONS with gap length:")
    print(f"    acc_symbols vs gap: r = {corr(sym_counts, gap_lens):.3f}")
    print(f"    r1_30 vs gap:      r = {corr(r1_counts, gap_lens):.3f}")
    print(f"    acc_events vs gap:  r = {corr(event_counts, gap_lens):.3f}")

    # CRITICAL: acc_symbols / gap_len ratio
    ratios = [p['acc_symbols'] / p['gap'] for p in gap_profiles if p['gap'] > 0]
    print(f"\n  acc_symbols per spin: mean={statistics.mean(ratios):.3f}, stdev={statistics.stdev(ratios):.3f}")

# ── TEST 2: RUNNING ACC SYMBOL COUNT AS PREDICTOR ─────────────────────────────
print("\n" + "=" * 90)
print("TEST 2: CAN ACC SYMBOL COUNT PREDICT REMAINING SPINS?")
print("=" * 90)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    acc_positions = [i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30)]

    # For each gap, track running acc_symbol count and check where triple lands
    print(f"\n{name}:")

    # Collect: at what acc_symbol count does the triple land?
    final_counts = []
    for g in range(len(acc_positions) - 1):
        start = acc_positions[g] + 1
        end = acc_positions[g + 1]
        count = 0
        for j in range(start, end):
            r = data[j]
            if r['r1'] == 30: count += 1
            if r['r2'] == 30: count += 1
            # Don't count r3=30 since that only happens in the triple itself
        final_counts.append(count)

    cv = statistics.stdev(final_counts) / statistics.mean(final_counts) if statistics.mean(final_counts) > 0 else 0
    gaps = [acc_positions[i+1] - acc_positions[i] for i in range(len(acc_positions)-1)]
    gap_cv = statistics.stdev(gaps) / statistics.mean(gaps)

    print(f"  ACC symbol count at triple: mean={statistics.mean(final_counts):.1f}, "
          f"stdev={statistics.stdev(final_counts):.1f}, CV={cv:.3f}")
    print(f"  Gap length:                 mean={statistics.mean(gaps):.1f}, "
          f"stdev={statistics.stdev(gaps):.1f}, CV={gap_cv:.3f}")
    print(f"  CV IMPROVEMENT: {gap_cv/cv:.2f}x tighter" if cv > 0 else "")
    print(f"  Counts: {final_counts[:25]}...")

# ── TEST 3: DIFFERENT COUNTING METHODS ────────────────────────────────────────
print("\n" + "=" * 90)
print("TEST 3: TRYING DIFFERENT COUNTING METHODS")
print("=" * 90)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    acc_positions = [i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30)]
    gaps = [acc_positions[i+1] - acc_positions[i] for i in range(len(acc_positions)-1)]
    gap_cv = statistics.stdev(gaps) / statistics.mean(gaps)

    methods = {
        'spins (baseline)': lambda r: 1,
        'r1=30 only': lambda r: 1 if r['r1'] == 30 else 0,
        'any reel=30': lambda r: (1 if r['r1']==30 else 0) + (1 if r['r2']==30 else 0),
        'acc_count': lambda r: r['acc_count'],
        'acc_delta': lambda r: r['accum_delta'],
        'non-ACC triples': lambda r: 1 if (r['is_triple'] and r['tuple'] != (30,30,30)) else 0,
        'ANY triple': lambda r: 1 if r['is_triple'] else 0,
        'non-triple spins': lambda r: 0 if r['is_triple'] else 1,
        'r1=3 (attack reel)': lambda r: 1 if r['r1'] == 3 else 0,
        'r3=2 spins': lambda r: 1 if r['r3'] == 2 else 0,
        'gold outcomes': lambda r: 1 if (not r['is_triple']) else 0,
    }

    print(f"\n{name}:")
    print(f"  {'Method':<25} {'Mean':>8} {'Stdev':>8} {'CV':>8} {'Improvement':>12}")
    print(f"  {'-'*65}")

    for mname, counter in methods.items():
        final_counts = []
        for g in range(len(acc_positions) - 1):
            start = acc_positions[g] + 1
            end = acc_positions[g + 1]
            total = sum(counter(data[j]) for j in range(start, end))
            final_counts.append(total)

        if not final_counts or statistics.mean(final_counts) == 0:
            continue
        cv = statistics.stdev(final_counts) / statistics.mean(final_counts)
        improvement = gap_cv / cv if cv > 0 else 0
        marker = " <---" if improvement > 1.1 else ""
        print(f"  {mname:<25} {statistics.mean(final_counts):>8.1f} {statistics.stdev(final_counts):>8.1f} "
              f"{cv:>8.3f} {improvement:>11.2f}x{marker}")

# ── TEST 4: SIMULATE ACC-SYMBOL-COUNT STRATEGY ───────────────────────────────
print("\n" + "=" * 90)
print("TEST 4: SIMULATE ACC-SYMBOL-COUNT BETTING STRATEGY")
print("=" * 90)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    acc_positions = [i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30)]

    # First pass: get median acc_symbol count at triple
    final_counts = []
    for g in range(len(acc_positions) - 1):
        start = acc_positions[g] + 1
        end = acc_positions[g + 1]
        count = 0
        for j in range(start, end):
            if data[j]['r1'] == 30: count += 1
            if data[j]['r2'] == 30: count += 1
        final_counts.append(count)

    target_syms = statistics.median(final_counts)
    print(f"\n{name}: median ACC symbols per gap = {target_syms}")

    # Simulate: bet when running acc_symbol count >= threshold
    for tpct in [0.7, 0.8, 0.9, 1.0, 1.1]:
        threshold = int(target_syms * tpct)
        catches = 0
        misses = 0
        total_bet = 0
        sym_count = 0
        calibrated = False
        cal_gaps = 0
        sym_history = []

        for i, r in enumerate(data):
            if r['tuple'] == (30, 30, 30):
                cal_gaps += 1
                sym_history.append(sym_count)
                if cal_gaps >= 5:
                    calibrated = True
                    target_syms = statistics.median(sym_history)
                    threshold = int(target_syms * tpct)

                if calibrated:
                    if sym_count >= threshold:
                        catches += 1
                    else:
                        misses += 1
                sym_count = 0
                continue

            # Count ACC symbols
            if r['r1'] == 30: sym_count += 1
            if r['r2'] == 30: sym_count += 1

            if calibrated and sym_count >= threshold:
                total_bet += 1

        total = catches + misses
        if catches > 0 and total > 0:
            sph = total_bet / catches
            print(f"  Sym threshold {tpct:.0%} ({threshold}): "
                  f"{catches}/{total} caught ({catches/total*100:.1f}%) | "
                  f"{total_bet} bet spins | {sph:.1f} spins/hit")

    # COMPARE with spin-count strategy
    print(f"\n  For comparison — spin-count at 100%:")
    gaps = [acc_positions[i+1]-acc_positions[i] for i in range(len(acc_positions)-1)]
    caught_spin = sum(1 for g in gaps[5:] if g >= statistics.median(gaps[:5]))
    # rough
    print(f"  (see earlier simulation: ~43-67 spins/hit)")

# ── TEST 5: THE COMBINED COUNTER ─────────────────────────────────────────────
print("\n" + "=" * 90)
print("TEST 5: COMBINED SIGNAL (spin count + acc symbol count)")
print("=" * 90)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    acc_positions = [i for i, r in enumerate(data) if r['tuple'] == (30, 30, 30)]
    gaps = [acc_positions[i+1]-acc_positions[i] for i in range(len(acc_positions)-1)]

    # For each gap, compute: (spin_count, acc_sym_count) at the point of triple
    pairs = []
    for g in range(len(acc_positions) - 1):
        start = acc_positions[g] + 1
        end = acc_positions[g + 1]
        gap_len = end - start
        sym_count = 0
        for j in range(start, end):
            if data[j]['r1'] == 30: sym_count += 1
            if data[j]['r2'] == 30: sym_count += 1
        pairs.append((gap_len, sym_count))

    # Can we combine them? Try: weighted_score = a*spins + b*symbols
    # Find weights that minimize variance of the score at triple time
    print(f"\n{name}:")
    spins_list = [p[0] for p in pairs]
    syms_list = [p[1] for p in pairs]

    best_cv = 999
    best_a = 0
    best_b = 0
    for a_pct in range(0, 101, 5):
        a = a_pct / 100.0
        b = 1.0 - a
        scores = [a * p[0] + b * p[1] for p in pairs]
        if statistics.mean(scores) > 0:
            cv = statistics.stdev(scores) / statistics.mean(scores)
            if cv < best_cv:
                best_cv = cv
                best_a = a
                best_b = b

    spin_cv = statistics.stdev(spins_list) / statistics.mean(spins_list)
    sym_cv = statistics.stdev(syms_list) / statistics.mean(syms_list)

    print(f"  Spin-only CV:   {spin_cv:.3f}")
    print(f"  Symbol-only CV: {sym_cv:.3f}")
    print(f"  Best combo:     {best_cv:.3f}  (weights: {best_a:.2f}*spins + {best_b:.2f}*symbols)")

    best_scores = [best_a * p[0] + best_b * p[1] for p in pairs]
    print(f"  Best combo scores: mean={statistics.mean(best_scores):.1f}, "
          f"stdev={statistics.stdev(best_scores):.1f}")

print("\n" + "=" * 90)
print("VERDICT")
print("=" * 90)
