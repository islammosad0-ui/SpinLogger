"""
93_sequence_analysis.py — Pre-VT sequence profiling

Analyzes the FULL sequence of spins leading up to each VT:
  - Last 10, 15, 20 spins before VT
  - The entire gap between consecutive VTs
  - Per-position profiling (what happens at gap-5, gap-4, ... gap-1, VT)
  - Stage analysis (early/mid/late gap behavior)
  - Idx distribution shift as VT approaches
  - Transition matrices (idx[N-1] → idx[N]) near VTs vs far from VTs
  - Rolling statistics within gaps
"""

import csv, os
from collections import Counter, defaultdict
from math import sqrt

STRIP = {0:'attack', 1:'coin', 2:'shield', 3:'goldSack', 4:'steal',
         5:'coin', 6:'spins', 7:'goldSack', 8:'accumulation'}
IDX_SYM = {i: s for i, s in STRIP.items()}

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data')
FILES = [
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_enriched_v2.csv')),
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_2026-04-13.csv')),
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_2026-04-14.csv')),
    ('Islam', os.path.join(DATA_DIR, 'Islam', 'spin_history_Islam_2026-04-13.csv')),
    ('Nick',  os.path.join(DATA_DIR, 'Nick',  'spin_history_Nick_2026-04-13.csv')),
]

def load():
    rows = []
    for acct, path in FILES:
        with open(path) as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    r1i, r2i, r3i = int(r['r1_idx']), int(r['r2_idx']), int(r['r3_idx'])
                except (ValueError, KeyError):
                    continue
                if any(x not in STRIP for x in (r1i, r2i, r3i)):
                    continue
                reel_1 = r.get('reel_1', '')
                is_triple = r.get('is_triple', '').lower() == 'true'
                vt = None
                if is_triple:
                    if reel_1 == 'accumulation': vt = 'ACC'
                    elif reel_1 == 'spins': vt = 'SPN'
                rows.append({
                    'acct': acct, 'r1': r1i, 'r2': r2i, 'r3': r3i,
                    'sum': r1i + r2i + r3i,
                    'sym1': IDX_SYM[r3i], 'sym2': IDX_SYM[r2i], 'sym3': IDX_SYM[r1i],
                    'is_triple': is_triple, 'vt': vt,
                })
    return rows


def extract_gaps(rows):
    """Extract gap sequences: list of (gap_spins, vt_type) for each VT."""
    gaps = []  # each is {'type': ACC/SPN, 'spins': [list of row dicts], 'length': N}
    # Per account
    acct_rows = defaultdict(list)
    for r in rows:
        acct_rows[r['acct']].append(r)

    for acct, ars in acct_rows.items():
        last_vt_idx = None
        for i, r in enumerate(ars):
            if r['vt']:
                if last_vt_idx is not None:
                    gap_spins = ars[last_vt_idx+1:i]  # spins BETWEEN VTs (not including either VT)
                    gaps.append({
                        'type': r['vt'],
                        'acct': acct,
                        'spins': gap_spins,
                        'vt_spin': r,
                        'prev_vt_spin': ars[last_vt_idx],
                        'length': len(gap_spins),
                    })
                last_vt_idx = i
    return gaps


def run(rows):
    gaps = extract_gaps(rows)
    print(f"Total gaps extracted: {len(gaps)}")
    print(f"  ACC: {sum(1 for g in gaps if g['type']=='ACC')}")
    print(f"  SPN: {sum(1 for g in gaps if g['type']=='SPN')}")
    lengths = [g['length'] for g in gaps]
    print(f"  Gap lengths: min={min(lengths)}, max={max(lengths)}, "
          f"mean={sum(lengths)/len(lengths):.1f}, median={sorted(lengths)[len(lengths)//2]}")

    # ═══════════════════════════════════════════════
    # SECTION 1: Position-by-position profiling (last N spins before VT)
    # ═══════════════════════════════════════════════
    for window_label, window_size in [("Last 10", 10), ("Last 15", 15), ("Last 20", 20)]:
        print(f"\n{'='*100}")
        print(f"  SECTION: {window_label} spins before VT — per-position idx distribution")
        print(f"{'='*100}")

        # Collect idx values at each position relative to VT
        # Position -1 = spin right before VT, -2 = two before, etc.
        for vt_filter, vt_label in [(None, "ALL VTs"), ('ACC', "ACC"), ('SPN', "SPN")]:
            filtered = [g for g in gaps if (vt_filter is None or g['type'] == vt_filter) and g['length'] >= window_size]
            if len(filtered) < 5:
                continue

            print(f"\n  --- {vt_label} ({len(filtered)} gaps with length >= {window_size}) ---")

            # For each reel
            for reel, reel_name in [('r1', 'r1_idx->r3sym'), ('r2', 'r2_idx->r2sym'), ('r3', 'r3_idx->r1sym')]:
                print(f"\n  {reel_name}:")
                print(f"  {'Pos':>5s}", end='')
                for idx in range(9):
                    print(f"  {idx}:{STRIP[idx][:3]:>4s}", end='')
                print(f"  {'mean':>6s} {'std':>5s}")
                print("  " + "-" * 85)

                for pos in range(-window_size, 0):
                    vals = []
                    for g in filtered:
                        spin_idx = g['length'] + pos  # position in gap
                        if 0 <= spin_idx < g['length']:
                            vals.append(g['spins'][spin_idx][reel])

                    if not vals:
                        continue

                    counts = Counter(vals)
                    total = len(vals)
                    mean = sum(vals) / total
                    std = (sum((v - mean)**2 for v in vals) / total) ** 0.5

                    print(f"  {pos:>5d}", end='')
                    for idx in range(9):
                        pct = counts.get(idx, 0) / total * 100
                        print(f"  {pct:>6.1f}%", end='')
                    print(f"  {mean:>6.2f} {std:>5.2f}")

                # Also show overall (all non-VT spins) for comparison
                all_vals = [r[reel] for r in rows if r['vt'] is None]
                counts = Counter(all_vals)
                total = len(all_vals)
                mean = sum(all_vals) / total
                print(f"  {'base':>5s}", end='')
                for idx in range(9):
                    pct = counts.get(idx, 0) / total * 100
                    print(f"  {pct:>6.1f}%", end='')
                print(f"  {mean:>6.2f}")

    # ═══════════════════════════════════════════════
    # SECTION 2: Running statistics within gaps
    # ═══════════════════════════════════════════════
    print(f"\n{'='*100}")
    print(f"  SECTION 2: Running idx_sum statistics within gaps (binned by % through gap)")
    print(f"{'='*100}")

    for vt_filter, vt_label in [(None, "ALL VTs"), ('ACC', "ACC"), ('SPN', "SPN")]:
        filtered = [g for g in gaps if (vt_filter is None or g['type'] == vt_filter) and g['length'] >= 10]
        if len(filtered) < 5:
            continue

        print(f"\n  --- {vt_label} ({len(filtered)} gaps) ---")
        # Bin by percentage through gap (0-10%, 10-20%, ..., 90-100%)
        bins = defaultdict(list)
        for g in filtered:
            n = g['length']
            for i, s in enumerate(g['spins']):
                pct = i / n
                bin_idx = min(int(pct * 10), 9)  # 0-9
                bins[bin_idx].append(s)

        print(f"  {'Pct':>6s} {'N':>6s} {'mean_sum':>9s} {'mean_r1':>8s} {'mean_r2':>8s} {'mean_r3':>8s} "
              f"{'trip%':>6s} {'near_miss%':>10s} {'spread':>7s}")
        print("  " + "-" * 80)
        for b in range(10):
            spins = bins[b]
            if not spins:
                continue
            n = len(spins)
            ms = sum(s['sum'] for s in spins) / n
            mr1 = sum(s['r1'] for s in spins) / n
            mr2 = sum(s['r2'] for s in spins) / n
            mr3 = sum(s['r3'] for s in spins) / n
            trips = sum(1 for s in spins if s['is_triple']) / n * 100
            nm = 0
            for s in spins:
                syms = [s['sym1'], s['sym2'], s['sym3']]
                if max(Counter(syms).values()) == 2:
                    nm += 1
            nm_pct = nm / n * 100
            spr = sum(s['r1'] - min(s['r1'], s['r2'], s['r3']) + max(s['r1'], s['r2'], s['r3']) - s['r1']
                      for s in spins)  # rough
            spr2 = sum(max(s['r1'],s['r2'],s['r3']) - min(s['r1'],s['r2'],s['r3']) for s in spins) / n

            pct_label = f"{b*10}-{(b+1)*10}%"
            print(f"  {pct_label:>6s} {n:>6d} {ms:>9.2f} {mr1:>8.2f} {mr2:>8.2f} {mr3:>8.2f} "
                  f"{trips:>5.1f}% {nm_pct:>9.1f}% {spr2:>7.2f}")

    # ═══════════════════════════════════════════════
    # SECTION 3: Transition matrices near VT vs far from VT
    # ═══════════════════════════════════════════════
    print(f"\n{'='*100}")
    print(f"  SECTION 3: r2_idx transitions (spin N-1 → spin N) — last 5 before VT vs rest")
    print(f"{'='*100}")

    near_transitions = Counter()  # last 5 spins before VT
    far_transitions = Counter()   # rest of gap

    for g in gaps:
        if g['length'] < 6:
            continue
        for i in range(1, g['length']):
            prev_r2 = g['spins'][i-1]['r2']
            curr_r2 = g['spins'][i]['r2']
            pair = (prev_r2, curr_r2)
            if i >= g['length'] - 5:
                near_transitions[pair] += 1
            else:
                far_transitions[pair] += 1

    near_total = sum(near_transitions.values())
    far_total = sum(far_transitions.values())

    if near_total > 0 and far_total > 0:
        print(f"\n  Transition ratios (near/far) where near = last 5 spins of gap:")
        print(f"  Near transitions: {near_total}, Far transitions: {far_total}")
        print(f"\n  {'From→To':>10s}", end='')
        for to_idx in range(9):
            print(f"  →{to_idx}:{STRIP[to_idx][:3]:>4s}", end='')
        print()
        print("  " + "-" * 80)
        for from_idx in range(9):
            print(f"  {from_idx}:{STRIP[from_idx][:4]:>6s}", end='')
            for to_idx in range(9):
                near_pct = near_transitions.get((from_idx, to_idx), 0) / near_total * 100
                far_pct = far_transitions.get((from_idx, to_idx), 0) / far_total * 100
                ratio = near_pct / far_pct if far_pct > 0 else 0
                if ratio >= 1.5:
                    marker = '▲'
                elif ratio <= 0.5:
                    marker = '▼'
                else:
                    marker = ' '
                print(f"  {ratio:>5.1f}x{marker}", end='')
            print()

    # ═══════════════════════════════════════════════
    # SECTION 4: "Ramp-up" detection — does the game increase VT-symbol idx before firing?
    # ═══════════════════════════════════════════════
    print(f"\n{'='*100}")
    print(f"  SECTION 4: VT-symbol idx presence in last N spins (ramp-up detection)")
    print(f"{'='*100}")

    for vt_filter, vt_label, target_idx_name, target_indices in [
        ('ACC', 'ACC', 'acc(8)', [8]),
        ('SPN', 'SPN', 'spn(6)', [6]),
    ]:
        filtered = [g for g in gaps if g['type'] == vt_filter and g['length'] >= 20]
        if len(filtered) < 5:
            continue

        print(f"\n  --- {vt_label} gaps ({len(filtered)} with len>=20) ---")
        print(f"  Presence of {target_idx_name} on any reel at each position before VT:")
        print(f"  {'Pos':>5s} {'count':>6s} {'pct':>6s} {'baseline':>8s} {'ratio':>6s}")
        print("  " + "-" * 40)

        # Baseline: how often target idx appears on any reel in all non-VT spins
        all_non_vt = [r for r in rows if r['vt'] is None]
        base_count = sum(1 for r in all_non_vt if any(x in target_indices for x in (r['r1'], r['r2'], r['r3'])))
        baseline = base_count / len(all_non_vt) if all_non_vt else 0

        for pos in range(-20, 0):
            count = 0
            total = 0
            for g in filtered:
                spin_idx = g['length'] + pos
                if 0 <= spin_idx < g['length']:
                    s = g['spins'][spin_idx]
                    total += 1
                    if any(x in target_indices for x in (s['r1'], s['r2'], s['r3'])):
                        count += 1
            if total == 0:
                continue
            pct = count / total
            ratio = pct / baseline if baseline > 0 else 0
            bar = '█' * int(ratio * 10)
            print(f"  {pos:>5d} {count:>6d} {pct:>5.1%} {baseline:>7.1%} {ratio:>5.2f}x {bar}")

    # ═══════════════════════════════════════════════
    # SECTION 5: Full gap profile — idx sum trajectory
    # ═══════════════════════════════════════════════
    print(f"\n{'='*100}")
    print(f"  SECTION 5: Average idx_sum at each position from end of gap")
    print(f"{'='*100}")

    for vt_filter, vt_label in [(None, "ALL VTs"), ('ACC', "ACC"), ('SPN', "SPN")]:
        filtered = [g for g in gaps if (vt_filter is None or g['type'] == vt_filter) and g['length'] >= 20]
        if len(filtered) < 5:
            continue

        print(f"\n  --- {vt_label} ({len(filtered)} gaps) — positions -30 to -1 ---")
        print(f"  {'Pos':>5s} {'N':>5s} {'mean_sum':>9s} {'mean_r1':>8s} {'mean_r2':>8s} {'mean_r3':>8s} "
              f"{'trip%':>6s} {'bar':>20s}")
        print("  " + "-" * 85)

        overall_mean_sum = sum(r['sum'] for r in rows) / len(rows)

        for pos in range(-30, 0):
            sums = []
            r1s, r2s, r3s = [], [], []
            trip_count = 0
            for g in filtered:
                spin_idx = g['length'] + pos
                if 0 <= spin_idx < g['length']:
                    s = g['spins'][spin_idx]
                    sums.append(s['sum'])
                    r1s.append(s['r1'])
                    r2s.append(s['r2'])
                    r3s.append(s['r3'])
                    if s['is_triple']:
                        trip_count += 1
            if not sums:
                continue
            n = len(sums)
            ms = sum(sums) / n
            mr1 = sum(r1s) / n
            mr2 = sum(r2s) / n
            mr3 = sum(r3s) / n
            tp = trip_count / n * 100
            # Visual bar
            bar_len = int((ms - overall_mean_sum + 5) * 2)
            bar = '█' * max(0, bar_len) if ms >= overall_mean_sum else '░' * max(0, -bar_len + 10)
            print(f"  {pos:>5d} {n:>5d} {ms:>9.2f} {mr1:>8.2f} {mr2:>8.2f} {mr3:>8.2f} {tp:>5.1f}% {bar:>20s}")

    # ═══════════════════════════════════════════════
    # SECTION 6: Specific idx patterns in last 5 spins (trigrams/patterns)
    # ═══════════════════════════════════════════════
    print(f"\n{'='*100}")
    print(f"  SECTION 6: Specific idx patterns in last 3-5 spins before VT")
    print(f"{'='*100}")

    # Look at r2_idx patterns (most reliable reel)
    # Collect 3-gram patterns before VT vs random
    vt_3grams = Counter()
    random_3grams = Counter()

    for g in gaps:
        if g['length'] < 5:
            continue
        # Last 3 spins before VT
        last3 = tuple(g['spins'][i]['r2'] for i in range(g['length']-3, g['length']))
        vt_3grams[last3] += 1

        # Random 3-grams from middle of gap
        for start in range(0, g['length']-5, 3):
            trip = tuple(g['spins'][i]['r2'] for i in range(start, start+3))
            random_3grams[trip] += 1

    vt_total = sum(vt_3grams.values())
    rand_total = sum(random_3grams.values())

    if vt_total > 0 and rand_total > 0:
        print(f"\n  r2_idx 3-grams: {vt_total} pre-VT, {rand_total} random")
        print(f"\n  Top enriched 3-grams before VT (ratio > 2x):")
        print(f"  {'Pattern':>15s} {'VT_count':>9s} {'VT%':>6s} {'Rand%':>6s} {'Ratio':>6s}")
        print("  " + "-" * 50)
        enriched = []
        for pattern, count in vt_3grams.most_common():
            if count < 3:
                continue
            vt_pct = count / vt_total * 100
            rand_pct = random_3grams.get(pattern, 0) / rand_total * 100
            ratio = vt_pct / rand_pct if rand_pct > 0 else 99
            enriched.append((pattern, count, vt_pct, rand_pct, ratio))
        enriched.sort(key=lambda x: -x[4])
        for pat, cnt, vpct, rpct, ratio in enriched[:20]:
            syms = '→'.join(f"{p}({STRIP[p][:3]})" for p in pat)
            print(f"  {syms:>40s} {cnt:>5d} {vpct:>5.1f}% {rpct:>5.1f}% {ratio:>5.1f}x")

    # ═══════════════════════════════════════════════
    # SECTION 7: Per-reel "convergence" — do r1/r2/r3 indices converge before VT?
    # ═══════════════════════════════════════════════
    print(f"\n{'='*100}")
    print(f"  SECTION 7: Index convergence/spread in last N spins before VT")
    print(f"{'='*100}")

    for vt_filter, vt_label in [(None, "ALL"), ('ACC', "ACC"), ('SPN', "SPN")]:
        filtered = [g for g in gaps if (vt_filter is None or g['type'] == vt_filter) and g['length'] >= 20]
        if len(filtered) < 5:
            continue

        print(f"\n  --- {vt_label} ({len(filtered)} gaps) ---")
        print(f"  {'Pos':>5s} {'mean_spread':>12s} {'0_spread%':>10s} {'pair%':>6s} {'all_diff%':>10s}")
        print("  " + "-" * 55)

        for pos in range(-20, 0):
            spreads = []
            zero_sp = 0
            pair = 0
            all_diff = 0
            for g in filtered:
                si = g['length'] + pos
                if 0 <= si < g['length']:
                    s = g['spins'][si]
                    sp = max(s['r1'], s['r2'], s['r3']) - min(s['r1'], s['r2'], s['r3'])
                    spreads.append(sp)
                    if sp == 0: zero_sp += 1
                    syms = [IDX_SYM[s['r1']], IDX_SYM[s['r2']], IDX_SYM[s['r3']]]
                    uc = len(set(syms))
                    if uc == 1: zero_sp += 0  # already counted
                    elif uc == 2: pair += 1
                    else: all_diff += 1
            if not spreads:
                continue
            n = len(spreads)
            print(f"  {pos:>5d} {sum(spreads)/n:>12.2f} {zero_sp/n*100:>9.1f}% {pair/n*100:>5.1f}% {all_diff/n*100:>9.1f}%")

        # Baseline
        all_non = [r for r in rows if r['vt'] is None]
        spreads = [max(r['r1'],r['r2'],r['r3'])-min(r['r1'],r['r2'],r['r3']) for r in all_non]
        zero_sp = sum(1 for s in spreads if s == 0) / len(spreads) * 100
        print(f"  {'base':>5s} {sum(spreads)/len(spreads):>12.2f} {zero_sp:>9.1f}%")

    # ═══════════════════════════════════════════════
    # SECTION 8: Gap-length conditioned analysis
    # ═══════════════════════════════════════════════
    print(f"\n{'='*100}")
    print(f"  SECTION 8: Do short gaps look different from long gaps?")
    print(f"{'='*100}")

    for vt_filter, vt_label in [(None, "ALL"), ('ACC', "ACC"), ('SPN', "SPN")]:
        filtered = [g for g in gaps if (vt_filter is None or g['type'] == vt_filter)]
        if len(filtered) < 5:
            continue

        print(f"\n  --- {vt_label} ({len(filtered)} gaps) ---")

        # Bin by gap length
        bins = [
            ("1-15", lambda l: 1 <= l <= 15),
            ("16-30", lambda l: 16 <= l <= 30),
            ("31-50", lambda l: 31 <= l <= 50),
            ("51-80", lambda l: 51 <= l <= 80),
            ("81+", lambda l: l >= 81),
        ]

        print(f"  {'Bin':>8s} {'N':>4s} {'mean_sum':>9s} {'mean_r1':>8s} {'mean_r2':>8s} {'mean_r3':>8s} "
              f"{'trip%':>6s} {'last3_sum':>10s}")
        print("  " + "-" * 75)

        for label, pred in bins:
            grp = [g for g in filtered if pred(g['length'])]
            if not grp:
                continue
            all_spins = [s for g in grp for s in g['spins']]
            if not all_spins:
                continue
            n = len(grp)
            ms = sum(s['sum'] for s in all_spins) / len(all_spins)
            mr1 = sum(s['r1'] for s in all_spins) / len(all_spins)
            mr2 = sum(s['r2'] for s in all_spins) / len(all_spins)
            mr3 = sum(s['r3'] for s in all_spins) / len(all_spins)
            trips = sum(1 for s in all_spins if s['is_triple']) / len(all_spins) * 100

            # Last 3 spins average sum
            last3_sums = []
            for g in grp:
                if g['length'] >= 3:
                    last3_sums.extend([g['spins'][i]['sum'] for i in range(g['length']-3, g['length'])])
            l3s = sum(last3_sums) / len(last3_sums) if last3_sums else 0

            print(f"  {label:>8s} {n:>4d} {ms:>9.2f} {mr1:>8.2f} {mr2:>8.2f} {mr3:>8.2f} {trips:>5.1f}% {l3s:>10.2f}")

    # ═══════════════════════════════════════════════
    # SECTION 9: What happens at EACH position in the gap (absolute, not relative)
    # ═══════════════════════════════════════════════
    print(f"\n{'='*100}")
    print(f"  SECTION 9: Absolute position in gap — VT rate if you bet at spin K after last VT")
    print(f"{'='*100}")

    # For each absolute position (spin 1, 2, 3, ... after last VT), what's the VT rate?
    position_hits = Counter()
    position_total = Counter()

    for g in gaps:
        for i in range(g['length']):
            pos = i + 1  # 1-indexed
            position_total[pos] += 1
        # The VT itself is at position = gap_length + 1
        position_hits[g['length'] + 1] = position_hits.get(g['length'] + 1, 0) + 1
        # Actually, each gap contributes a "1" at its end
        # But we need to count: how many gaps REACH each position?

    # Recalculate: at position K, how many gaps are still alive?
    # A gap "reaches" position K if its length >= K
    # A VT happens at position K if gap_length = K-1 (0-indexed gap has K-1 spins)
    print(f"\n  {'Pos':>5s} {'Gaps_alive':>11s} {'VT_here':>8s} {'VT_rate':>8s} {'Cum_VT%':>8s}")
    print("  " + "-" * 50)

    max_pos = max(g['length'] for g in gaps) + 1
    cum_vts = 0
    total_gaps = len(gaps)
    for pos in range(1, min(max_pos + 1, 151)):
        alive = sum(1 for g in gaps if g['length'] >= pos - 1)
        vts_here = sum(1 for g in gaps if g['length'] == pos - 1)
        rate = vts_here / alive * 100 if alive > 0 else 0
        cum_vts += vts_here
        cum_pct = cum_vts / total_gaps * 100
        bar = '█' * int(rate * 5)
        if pos <= 60 or pos % 10 == 0 or vts_here > 0:
            print(f"  {pos:>5d} {alive:>11d} {vts_here:>8d} {rate:>7.2f}% {cum_pct:>7.1f}% {bar}")


if __name__ == '__main__':
    rows = load()
    run(rows)
