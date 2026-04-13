#!/usr/bin/env python3
"""
64_pre_vt_patterns.py - Nuclear analysis of the 10 spins BEFORE each VT.

For every acc+spins VT, look at the preceding 10 spins and hunt for:
  1. Individual symbol frequencies (are certain symbols overrepresented?)
  2. Idx value frequencies per reel
  3. Back-to-back duplicates (same symbol or same idx repeating)
  4. Runs / streaks (consecutive same idx on a reel)
  5. Symbol pairs in the window (co-occurrence)
  6. Idx pair sequences (e.g., r2 goes 7->3->7 before VT)
  7. Triple presence in window (does a non-valuable triple precede VT?)
  8. Transition patterns (idx[n] -> idx[n+1] deltas)
  9. Position-specific signals (what happens at exactly -2, -3, -5 before VT?)
  10. Combined multi-spin signatures
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path
import itertools

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_F = ROOT / "data" / "Ahmed" / "spin_history_Ahmed_enriched_v2.csv"

rows = []
with open(CSV_F, newline='') as f:
    for r in csv.DictReader(f):
        r['r1'] = int(r['r1_idx'])
        r['r2'] = int(r['r2_idx'])
        r['r3'] = int(r['r3_idx'])
        r['s1'] = int(r['s1'])
        r['s2'] = int(r['s2'])
        r['s3'] = int(r['s3'])
        r['is_triple'] = r['is_triple'] == 'True'
        r['reel_1'] = r['reel_1']
        r['reel_2'] = r['reel_2']
        r['reel_3'] = r['reel_3']
        rows.append(r)

N = len(rows)
WINDOW = 10  # look back 10 spins

def is_vt(row):
    return row['is_triple'] and row['s1'] in (30, 6)

# Collect VT indices and their windows
vt_indices = [i for i in range(N) if is_vt(rows[i])]
total_vt = len(vt_indices)

# Collect non-VT windows for comparison (random baseline)
non_vt_indices = [i for i in range(WINDOW, N) if not is_vt(rows[i])]

print("=" * 90)
print(f"  64_PRE_VT_PATTERNS — 10-spin lookback before each VT (n={total_vt})")
print("=" * 90)
print(f"  Total spins: {N}, Total VT: {total_vt}")
print(f"  VT indices: {vt_indices}")

# Helper: get window of rows before index i (not including i itself)
def get_window(i, size=WINDOW):
    start = max(0, i - size)
    return rows[start:i]


# =====================================================================
# 1. INDIVIDUAL SYMBOL FREQUENCY in pre-VT window vs baseline
# =====================================================================
print("\n\n" + "=" * 90)
print("  1. SYMBOL FREQUENCY in 10-spin window before VT")
print("=" * 90)

sym_map = {1: 'coin', 2: 'goldSack', 3: 'attack', 4: 'steal', 5: 'shield', 6: 'spins', 30: 'accumulation'}

for reel, reel_name in [(1, 'reel_1', ), (2, 'reel_2'), (3, 'reel_3')]:
    s_key = f's{reel}'
    r_key = f'reel_{reel}'

    # VT windows
    vt_sym_counts = Counter()
    vt_total = 0
    for vi in vt_indices:
        win = get_window(vi)
        for w in win:
            vt_sym_counts[w[r_key]] += 1
            vt_total += 1

    # Baseline
    base_sym_counts = Counter()
    base_total = 0
    for ni in non_vt_indices[:500]:  # sample 500 non-VT for baseline
        win = get_window(ni)
        for w in win:
            base_sym_counts[w[r_key]] += 1
            base_total += 1

    print(f"\n  Reel {reel} ({r_key}):")
    print(f"  {'Symbol':>15} {'VT_win':>7} {'VT_%':>6} {'Base_%':>7} {'Lift':>7}")
    print(f"  {'-'*48}")
    for sym in sorted(set(list(vt_sym_counts.keys()) + list(base_sym_counts.keys()))):
        vt_pct = 100 * vt_sym_counts.get(sym, 0) / vt_total if vt_total else 0
        base_pct = 100 * base_sym_counts.get(sym, 0) / base_total if base_total else 0
        lift = vt_pct - base_pct
        marker = ' <<<' if abs(lift) > 3 else ''
        print(f"  {sym:>15} {vt_sym_counts.get(sym,0):>7} {vt_pct:>5.1f}% {base_pct:>6.1f}% {lift:>+6.1f}pp{marker}")


# =====================================================================
# 2. IDX FREQUENCY in pre-VT window vs baseline
# =====================================================================
print("\n\n" + "=" * 90)
print("  2. IDX FREQUENCY in 10-spin window before VT")
print("=" * 90)

for reel_name in ['r1', 'r2', 'r3']:
    vt_idx_counts = Counter()
    vt_total = 0
    for vi in vt_indices:
        win = get_window(vi)
        for w in win:
            vt_idx_counts[w[reel_name]] += 1
            vt_total += 1

    base_idx_counts = Counter()
    base_total = 0
    for ni in non_vt_indices[:500]:
        win = get_window(ni)
        for w in win:
            base_idx_counts[w[reel_name]] += 1
            base_total += 1

    print(f"\n  {reel_name}:")
    print(f"  {'Idx':>5} {'VT_win':>7} {'VT_%':>6} {'Base_%':>7} {'Lift':>7}")
    print(f"  {'-'*38}")
    for idx in range(9):
        vt_pct = 100 * vt_idx_counts.get(idx, 0) / vt_total if vt_total else 0
        base_pct = 100 * base_idx_counts.get(idx, 0) / base_total if base_total else 0
        lift = vt_pct - base_pct
        marker = ' <<<' if abs(lift) > 2 else ''
        print(f"  {idx:>5} {vt_idx_counts.get(idx,0):>7} {vt_pct:>5.1f}% {base_pct:>6.1f}% {lift:>+6.1f}pp{marker}")


# =====================================================================
# 3. BACK-TO-BACK DUPLICATES (same idx repeating on same reel)
# =====================================================================
print("\n\n" + "=" * 90)
print("  3. BACK-TO-BACK IDX DUPLICATES in pre-VT window")
print("=" * 90)

for reel_name in ['r1', 'r2', 'r3']:
    vt_dups = 0
    vt_pairs = 0
    for vi in vt_indices:
        win = get_window(vi)
        for j in range(1, len(win)):
            vt_pairs += 1
            if win[j][reel_name] == win[j-1][reel_name]:
                vt_dups += 1

    base_dups = 0
    base_pairs = 0
    for ni in non_vt_indices[:500]:
        win = get_window(ni)
        for j in range(1, len(win)):
            base_pairs += 1
            if win[j][reel_name] == win[j-1][reel_name]:
                base_dups += 1

    vt_rate = 100 * vt_dups / vt_pairs if vt_pairs else 0
    base_rate = 100 * base_dups / base_pairs if base_pairs else 0
    print(f"  {reel_name}: VT windows {vt_dups}/{vt_pairs} = {vt_rate:.1f}%  "
          f"Base {base_dups}/{base_pairs} = {base_rate:.1f}%  "
          f"Lift: {vt_rate - base_rate:+.1f}pp")

# Also check: same SYMBOL repeating across all 3 reels
print(f"\n  Cross-reel: same symbol on r1 appearing again on r1 next spin:")
for reel_name in ['r1', 'r2', 'r3']:
    # Check if specific idx values repeat more before VT
    vt_repeat_by_val = Counter()
    vt_total_by_val = Counter()
    for vi in vt_indices:
        win = get_window(vi)
        for j in range(1, len(win)):
            val = win[j-1][reel_name]
            vt_total_by_val[val] += 1
            if win[j][reel_name] == val:
                vt_repeat_by_val[val] += 1


# =====================================================================
# 4. POSITION-SPECIFIC SIGNALS (what idx at exactly -1, -2, -3... -10)
# =====================================================================
print("\n\n" + "=" * 90)
print("  4. POSITION-SPECIFIC: idx at each position before VT")
print("=" * 90)

for reel_name in ['r1', 'r2', 'r3']:
    print(f"\n  {reel_name} at each lookback position:")
    print(f"  {'Pos':>4} {'Most common':>30} {'VT avg':>8} {'Base avg':>9}")
    print(f"  {'-'*55}")

    for lookback in range(1, WINDOW + 1):
        vt_vals = []
        for vi in vt_indices:
            if vi - lookback >= 0:
                vt_vals.append(rows[vi - lookback][reel_name])

        base_vals = []
        for ni in non_vt_indices[:500]:
            if ni - lookback >= 0:
                base_vals.append(rows[ni - lookback][reel_name])

        if vt_vals:
            vt_avg = sum(vt_vals) / len(vt_vals)
            base_avg = sum(base_vals) / len(base_vals) if base_vals else 0
            top3 = Counter(vt_vals).most_common(3)
            top_str = ', '.join(f'{v}({c})' for v, c in top3)
            print(f"  {-lookback:>4} {top_str:>30} {vt_avg:>7.2f} {base_avg:>8.2f}")


# =====================================================================
# 5. TRIPLES IN WINDOW (does a triple appear before VT?)
# =====================================================================
print("\n\n" + "=" * 90)
print("  5. TRIPLES IN THE 10-SPIN WINDOW before VT")
print("=" * 90)

vt_has_triple = 0
vt_triple_types = Counter()
for vi in vt_indices:
    win = get_window(vi)
    found = False
    for w in win:
        if w['is_triple']:
            found = True
            vt_triple_types[w['reel_1']] += 1
    if found:
        vt_has_triple += 1

base_has_triple = 0
for ni in non_vt_indices[:500]:
    win = get_window(ni)
    if any(w['is_triple'] for w in win):
        base_has_triple += 1

print(f"  VT preceded by ANY triple in window: {vt_has_triple}/{total_vt} = {100*vt_has_triple/total_vt:.1f}%")
print(f"  Baseline (random 500):               {base_has_triple}/500 = {100*base_has_triple/500:.1f}%")
print(f"\n  Triple types in pre-VT windows:")
for sym, cnt in vt_triple_types.most_common():
    print(f"    {sym:>15}: {cnt}")


# =====================================================================
# 6. IDX TRANSITIONS (delta between consecutive spins)
# =====================================================================
print("\n\n" + "=" * 90)
print("  6. IDX TRANSITIONS (prev_idx -> curr_idx) in pre-VT window")
print("=" * 90)

for reel_name in ['r1', 'r2', 'r3']:
    vt_deltas = Counter()
    vt_total = 0
    for vi in vt_indices:
        win = get_window(vi)
        for j in range(1, len(win)):
            delta = win[j][reel_name] - win[j-1][reel_name]
            vt_deltas[delta] += 1
            vt_total += 1

    base_deltas = Counter()
    base_total = 0
    for ni in non_vt_indices[:500]:
        win = get_window(ni)
        for j in range(1, len(win)):
            delta = win[j][reel_name] - win[j-1][reel_name]
            base_deltas[delta] += 1
            base_total += 1

    print(f"\n  {reel_name} transitions (top deviations from baseline):")
    all_deltas = sorted(set(list(vt_deltas.keys()) + list(base_deltas.keys())))
    results = []
    for d in all_deltas:
        vt_pct = 100 * vt_deltas.get(d, 0) / vt_total if vt_total else 0
        base_pct = 100 * base_deltas.get(d, 0) / base_total if base_total else 0
        results.append((d, vt_pct, base_pct, vt_pct - base_pct))

    results.sort(key=lambda x: abs(x[3]), reverse=True)
    print(f"  {'Delta':>6} {'VT_%':>6} {'Base_%':>7} {'Lift':>7}")
    print(f"  {'-'*30}")
    for d, vp, bp, lift in results[:8]:
        marker = ' <<<' if abs(lift) > 2 else ''
        print(f"  {d:>+6} {vp:>5.1f}% {bp:>6.1f}% {lift:>+6.1f}pp{marker}")


# =====================================================================
# 7. SYMBOL SEQUENCE PATTERNS (2-gram and 3-gram on each reel)
# =====================================================================
print("\n\n" + "=" * 90)
print("  7. IDX 2-GRAMS (consecutive idx pairs) in pre-VT window")
print("=" * 90)

for reel_name in ['r1', 'r2', 'r3']:
    vt_bigrams = Counter()
    vt_total = 0
    for vi in vt_indices:
        win = get_window(vi)
        for j in range(1, len(win)):
            bg = (win[j-1][reel_name], win[j][reel_name])
            vt_bigrams[bg] += 1
            vt_total += 1

    base_bigrams = Counter()
    base_total = 0
    for ni in non_vt_indices[:500]:
        win = get_window(ni)
        for j in range(1, len(win)):
            bg = (win[j-1][reel_name], win[j][reel_name])
            base_bigrams[bg] += 1
            base_total += 1

    # Find biggest deviations
    all_bgs = set(list(vt_bigrams.keys()) + list(base_bigrams.keys()))
    results = []
    for bg in all_bgs:
        vt_pct = 100 * vt_bigrams.get(bg, 0) / vt_total if vt_total else 0
        base_pct = 100 * base_bigrams.get(bg, 0) / base_total if base_total else 0
        if vt_bigrams.get(bg, 0) >= 3:  # minimum count
            results.append((bg, vt_bigrams.get(bg, 0), vt_pct, base_pct, vt_pct - base_pct))

    results.sort(key=lambda x: x[4], reverse=True)
    print(f"\n  {reel_name} — top ENRICHED bigrams in pre-VT windows:")
    print(f"  {'Bigram':>10} {'Count':>6} {'VT_%':>6} {'Base_%':>7} {'Lift':>7}")
    print(f"  {'-'*42}")
    for bg, cnt, vp, bp, lift in results[:10]:
        marker = ' <<<' if lift > 1.5 else ''
        print(f"  {str(bg):>10} {cnt:>6} {vp:>5.1f}% {bp:>6.1f}% {lift:>+6.1f}pp{marker}")


# =====================================================================
# 8. CROSS-REEL PATTERNS (r1+r2+r3 tuples in window)
# =====================================================================
print("\n\n" + "=" * 90)
print("  8. CROSS-REEL IDX TUPLES in pre-VT window")
print("=" * 90)

vt_tuples = Counter()
vt_total = 0
for vi in vt_indices:
    win = get_window(vi)
    for w in win:
        t = (w['r1'], w['r2'], w['r3'])
        vt_tuples[t] += 1
        vt_total += 1

base_tuples = Counter()
base_total = 0
for ni in non_vt_indices[:500]:
    win = get_window(ni)
    for w in win:
        t = (w['r1'], w['r2'], w['r3'])
        base_tuples[t] += 1
        base_total += 1

print(f"\n  Most common tuples in pre-VT windows:")
print(f"  {'Tuple':>12} {'VT_cnt':>7} {'VT_%':>6} {'Base_%':>7} {'Lift':>7}")
print(f"  {'-'*45}")

results = []
for t, cnt in vt_tuples.most_common():
    if cnt >= 3:
        vt_pct = 100 * cnt / vt_total
        base_pct = 100 * base_tuples.get(t, 0) / base_total if base_total else 0
        results.append((t, cnt, vt_pct, base_pct, vt_pct - base_pct))

results.sort(key=lambda x: x[4], reverse=True)
for t, cnt, vp, bp, lift in results[:20]:
    marker = ' <<<' if lift > 1 else ''
    print(f"  {str(t):>12} {cnt:>7} {vp:>5.1f}% {bp:>6.1f}% {lift:>+6.1f}pp{marker}")


# =====================================================================
# 9. WINDOW STATISTICS (avg, variance, unique count)
# =====================================================================
print("\n\n" + "=" * 90)
print("  9. WINDOW STATISTICS (aggregates over 10-spin window)")
print("=" * 90)

for reel_name in ['r1', 'r2', 'r3']:
    vt_avgs = []
    vt_stds = []
    vt_uniques = []
    vt_max_runs = []

    for vi in vt_indices:
        win = get_window(vi)
        vals = [w[reel_name] for w in win]
        if len(vals) > 0:
            avg = sum(vals) / len(vals)
            std = (sum((v - avg)**2 for v in vals) / len(vals)) ** 0.5
            vt_avgs.append(avg)
            vt_stds.append(std)
            vt_uniques.append(len(set(vals)))

            # Max consecutive run of same value
            max_run = 1
            cur_run = 1
            for j in range(1, len(vals)):
                if vals[j] == vals[j-1]:
                    cur_run += 1
                    max_run = max(max_run, cur_run)
                else:
                    cur_run = 1
            vt_max_runs.append(max_run)

    base_avgs = []
    base_stds = []
    base_uniques = []
    base_max_runs = []
    for ni in non_vt_indices[:500]:
        win = get_window(ni)
        vals = [w[reel_name] for w in win]
        if len(vals) > 0:
            avg = sum(vals) / len(vals)
            std = (sum((v - avg)**2 for v in vals) / len(vals)) ** 0.5
            base_avgs.append(avg)
            base_stds.append(std)
            base_uniques.append(len(set(vals)))
            max_run = 1
            cur_run = 1
            for j in range(1, len(vals)):
                if vals[j] == vals[j-1]:
                    cur_run += 1
                    max_run = max(max_run, cur_run)
                else:
                    cur_run = 1
            base_max_runs.append(max_run)

    def avg(lst): return sum(lst)/len(lst) if lst else 0

    print(f"\n  {reel_name}:")
    print(f"    Avg idx:      VT={avg(vt_avgs):.2f}  Base={avg(base_avgs):.2f}  Diff={avg(vt_avgs)-avg(base_avgs):+.2f}")
    print(f"    Std idx:      VT={avg(vt_stds):.2f}  Base={avg(base_stds):.2f}  Diff={avg(vt_stds)-avg(base_stds):+.2f}")
    print(f"    Unique vals:  VT={avg(vt_uniques):.1f}  Base={avg(base_uniques):.1f}  Diff={avg(vt_uniques)-avg(base_uniques):+.1f}")
    print(f"    Max run:      VT={avg(vt_max_runs):.2f}  Base={avg(base_max_runs):.2f}  Diff={avg(vt_max_runs)-avg(base_max_runs):+.2f}")


# =====================================================================
# 10. THE BIG ONE: Show every VT with its full 10-spin prefix
# =====================================================================
print("\n\n" + "=" * 90)
print("  10. FULL 10-SPIN WINDOW before each VT")
print("=" * 90)

for vi in vt_indices:
    win = get_window(vi)
    sym = rows[vi]['reel_1']
    print(f"\n  VT at spin {vi} ({sym}):")
    print(f"  {'Pos':>5} {'r1':>3} {'r2':>3} {'r3':>3} {'sym1':>12} {'sym2':>12} {'sym3':>12} {'triple?':>8}")
    print(f"  {'-'*65}")
    for j, w in enumerate(win):
        pos = -(len(win) - j)
        triple_mark = f"*** {w['reel_1']}" if w['is_triple'] else ''
        print(f"  {pos:>5} {w['r1']:>3} {w['r2']:>3} {w['r3']:>3} "
              f"{w['reel_1']:>12} {w['reel_2']:>12} {w['reel_3']:>12} {triple_mark}")
    print(f"  {'VT->':>5} {rows[vi]['r1']:>3} {rows[vi]['r2']:>3} {rows[vi]['r3']:>3} "
          f"{rows[vi]['reel_1']:>12} {rows[vi]['reel_2']:>12} {rows[vi]['reel_3']:>12} *** VT ***")


# =====================================================================
# 11. BONUS: Count of each symbol appearing N times in window
# =====================================================================
print("\n\n" + "=" * 90)
print("  11. SYMBOL SATURATION: how many times does each symbol appear in 10-spin window?")
print("=" * 90)

for reel, r_key in [(1, 'reel_1'), (2, 'reel_2'), (3, 'reel_3')]:
    print(f"\n  {r_key}:")
    for sym_name in ['attack', 'shield', 'coin', 'steal', 'spins', 'goldSack', 'accumulation']:
        vt_counts = []
        for vi in vt_indices:
            win = get_window(vi)
            cnt = sum(1 for w in win if w[r_key] == sym_name)
            vt_counts.append(cnt)

        base_counts = []
        for ni in non_vt_indices[:500]:
            win = get_window(ni)
            cnt = sum(1 for w in win if w[r_key] == sym_name)
            base_counts.append(cnt)

        vt_avg = sum(vt_counts)/len(vt_counts) if vt_counts else 0
        base_avg = sum(base_counts)/len(base_counts) if base_counts else 0
        diff = vt_avg - base_avg
        marker = ' <<<' if abs(diff) > 0.4 else ''
        print(f"    {sym_name:>15}: VT avg={vt_avg:.2f}  Base avg={base_avg:.2f}  Diff={diff:+.2f}{marker}")


# =====================================================================
# 12. BONUS: "Drought" signals — gap since last appearance of each idx
# =====================================================================
print("\n\n" + "=" * 90)
print("  12. IDX DROUGHT: gap since last appearance of each idx before VT")
print("=" * 90)

for reel_name in ['r1', 'r2', 'r3']:
    print(f"\n  {reel_name}:")
    for idx_val in range(9):
        vt_gaps = []
        for vi in vt_indices:
            gap = None
            for lookback in range(1, min(vi, 30) + 1):
                if rows[vi - lookback][reel_name] == idx_val:
                    gap = lookback
                    break
            if gap is not None:
                vt_gaps.append(gap)

        base_gaps = []
        for ni in non_vt_indices[:300]:
            gap = None
            for lookback in range(1, min(ni, 30) + 1):
                if rows[ni - lookback][reel_name] == idx_val:
                    gap = lookback
                    break
            if gap is not None:
                base_gaps.append(gap)

        if vt_gaps and base_gaps:
            vt_avg = sum(vt_gaps)/len(vt_gaps)
            base_avg = sum(base_gaps)/len(base_gaps)
            diff = vt_avg - base_avg
            marker = ' <<<' if abs(diff) > 1.5 else ''
            print(f"    idx={idx_val}: VT avg gap={vt_avg:.1f}  Base={base_avg:.1f}  Diff={diff:+.1f}{marker}")


print("\n\nDONE")
