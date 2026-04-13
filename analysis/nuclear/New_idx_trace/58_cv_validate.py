#!/usr/bin/env python3
"""58_cv_validate.py - Temporal CV validation of nuclear findings."""

import json, csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_F = ROOT / "data" / "Ahmed" / "spin_history_Ahmed_enriched_v2.csv"
TRACE = ROOT / "data" / "Ahmed" / "il2cpp_trace_20260412_045402.jsonl"

rows = []
with open(CSV_F, newline='') as f:
    for r in csv.DictReader(f):
        r['r1_idx'] = int(r['r1_idx'])
        r['r2_idx'] = int(r['r2_idx'])
        r['r3_idx'] = int(r['r3_idx'])
        r['is_triple'] = r['is_triple'] == 'True'
        r['is_valuable'] = r['is_valuable'] == 'True'
        r['sn'] = int(r['sn'])
        rows.append(r)

trace = {}
with open(TRACE) as f:
    for line in f:
        d = json.loads(line)
        trace[d['spin_num']] = d

for r in rows:
    r['trace'] = trace.get(r['sn'])

N = len(rows)
n_folds = 5
fold_size = N // n_folds

# =====================================================================
# TEST 1: Valuable anti-clustering
# =====================================================================
print("=" * 70)
print("TEST 1: Valuable anti-clustering -- 5-fold temporal CV")
print("=" * 70)

for lookahead in [1, 3, 5, 7]:
    print(f"\n  Next-{lookahead} valuable:")
    all_spreads = []
    for fold in range(n_folds):
        start = fold * fold_size
        end = start + fold_size if fold < n_folds - 1 else N
        fold_rows = rows[start:end]

        av_hits, av_n, anv_hits, anv_n = 0, 0, 0, 0
        for i in range(len(fold_rows) - lookahead):
            has_next = any(fold_rows[j]['is_valuable']
                         for j in range(i+1, min(i+1+lookahead, len(fold_rows))))
            if fold_rows[i]['is_valuable']:
                av_n += 1; av_hits += int(has_next)
            else:
                anv_n += 1; anv_hits += int(has_next)

        av = av_hits / av_n if av_n > 0 else 0
        anv = anv_hits / anv_n if anv_n > 0 else 0
        spread = av - anv
        all_spreads.append(spread)
        print(f"    Fold {fold}: after_VAL={100*av:.1f}% (n={av_n}) "
              f"after_NON={100*anv:.1f}% (n={anv_n}) spread={100*spread:+.1f}pp")

    neg = sum(1 for s in all_spreads if s < 0)
    avg = sum(all_spreads) / len(all_spreads)
    print(f"    VERDICT: avg={100*avg:+.1f}pp, {neg}/5 negative folds")

# =====================================================================
# TEST 2: WinBehaviours byte[96] -> NEXT-spin valuable
# =====================================================================
print("\n" + "=" * 70)
print("TEST 2: WinBehaviours byte[96] -> NEXT-spin valuable -- temporal CV")
print("=" * 70)

wb_key = None
for k in rows[0]['trace']['hex']:
    if k.startswith('WinBehaviours.innerList@'):
        wb_key = k
        break

for r in rows:
    if r['trace']:
        hx = r['trace']['hex'].get(wb_key, '')
        if isinstance(hx, str) and len(hx) > 194:
            r['wb96'] = int(hx[192:194], 16)
        else:
            r['wb96'] = None
    else:
        r['wb96'] = None

valid = [r['wb96'] for r in rows if r['wb96'] is not None]
median_wb = sorted(valid)[len(valid)//2]
print(f"Median byte[96] = {median_wb}")

for fold in range(n_folds):
    start = fold * fold_size
    end = start + fold_size if fold < n_folds - 1 else N
    fr = rows[start:end]

    hh, hn, lh, ln = 0, 0, 0, 0
    for i in range(len(fr) - 1):
        if fr[i]['wb96'] is None:
            continue
        nv = fr[i+1]['is_valuable']
        if fr[i]['wb96'] > median_wb:
            hn += 1; hh += int(nv)
        else:
            ln += 1; lh += int(nv)

    hr = hh / hn if hn > 0 else 0
    lr = lh / ln if ln > 0 else 0
    print(f"  Fold {fold}: HIGH={100*hr:.1f}% (n={hn}) LOW={100*lr:.1f}% (n={ln}) "
          f"spread={100*(hr-lr):+.1f}pp")

# Also test byte[96] with non-zero vs zero
print("\n  Byte[96] non-zero (rare states) vs common states:")
for fold in range(n_folds):
    start = fold * fold_size
    end = start + fold_size if fold < n_folds - 1 else N
    fr = rows[start:end]

    rare_h, rare_n, common_h, common_n = 0, 0, 0, 0
    for i in range(len(fr) - 1):
        if fr[i]['wb96'] is None:
            continue
        nv = fr[i+1]['is_valuable']
        if fr[i]['wb96'] not in (0, 32, 48):  # rare values
            rare_n += 1; rare_h += int(nv)
        else:
            common_n += 1; common_h += int(nv)

    rr = rare_h / rare_n if rare_n > 0 else 0
    cr = common_h / common_n if common_n > 0 else 0
    print(f"  Fold {fold}: RARE={100*rr:.1f}% (n={rare_n}) COMMON={100*cr:.1f}% (n={common_n}) "
          f"spread={100*(rr-cr):+.1f}pp")

# =====================================================================
# TEST 3: Gap parity -> valuable triple type
# =====================================================================
print("\n" + "=" * 70)
print("TEST 3: Gap parity (odd vs even) -> valuable triple -- temporal CV")
print("=" * 70)

for fold in range(n_folds):
    start = fold * fold_size
    end = start + fold_size if fold < n_folds - 1 else N
    fr = rows[start:end]

    last_t = -1
    odd_v, odd_n, even_v, even_n = 0, 0, 0, 0
    for i, r in enumerate(fr):
        if r['is_triple']:
            if last_t >= 0:
                gap = i - last_t
                if gap % 2 == 1:
                    odd_n += 1; odd_v += int(r['is_valuable'])
                else:
                    even_n += 1; even_v += int(r['is_valuable'])
            last_t = i

    orate = odd_v / odd_n if odd_n > 0 else 0
    erate = even_v / even_n if even_n > 0 else 0
    print(f"  Fold {fold}: ODD_gap={100*orate:.1f}% (n={odd_n}) "
          f"EVEN_gap={100*erate:.1f}% (n={even_n}) spread={100*(orate-erate):+.1f}pp")

# =====================================================================
# TEST 4: "Overdue" predictor
# =====================================================================
print("\n" + "=" * 70)
print("TEST 4: Overdue valuable (>=10 spins + no recent 5) -- temporal CV")
print("=" * 70)

for fold in range(n_folds):
    start = fold * fold_size
    end = start + fold_size if fold < n_folds - 1 else N
    fr = rows[start:end]

    mh, mn, oh, on = 0, 0, 0, 0
    last_val = -100
    for i, r in enumerate(fr):
        if i < 5:
            if r['is_valuable']:
                last_val = i
            continue
        gap = i - last_val
        recent_clean = not any(fr[j]['is_valuable'] for j in range(i-5, i))
        if gap >= 10 and recent_clean:
            mn += 1; mh += int(r['is_valuable'])
        else:
            on += 1; oh += int(r['is_valuable'])
        if r['is_valuable']:
            last_val = i

    mr = mh / mn if mn > 0 else 0
    ore = oh / on if on > 0 else 0
    print(f"  Fold {fold}: OVERDUE={100*mr:.1f}% (n={mn}) "
          f"NOT_OVERDUE={100*ore:.1f}% (n={on}) spread={100*(mr-ore):+.1f}pp")

# =====================================================================
# TEST 5: Top transition states -> NEXT valuable
# =====================================================================
print("\n" + "=" * 70)
print("TEST 5: Best transition states -> NEXT valuable -- temporal CV")
print("=" * 70)

test_states = [(1,5,0), (6,4,5), (4,5,5), (3,4,0), (4,1,5), (7,3,8)]
for state in test_states:
    spreads = []
    for fold in range(n_folds):
        start = fold * fold_size
        end = start + fold_size if fold < n_folds - 1 else N
        fr = rows[start:end]

        sh, sn, ooh, oon = 0, 0, 0, 0
        for i in range(len(fr) - 1):
            s = (fr[i]['r1_idx'], fr[i]['r2_idx'], fr[i]['r3_idx'])
            nv = fr[i+1]['is_valuable']
            if s == state:
                sn += 1; sh += int(nv)
            else:
                oon += 1; ooh += int(nv)

        sr = sh / sn if sn > 0 else 0
        ot = ooh / oon if oon > 0 else 0
        spreads.append(sr - ot)

    total_n = sum(1 for r in rows if (r['r1_idx'], r['r2_idx'], r['r3_idx']) == state)
    pos = sum(1 for s in spreads if s > 0)
    avg = sum(spreads) / len(spreads)
    print(f"  state={state} total_n={total_n:>3} | avg_spread={100*avg:+.1f}pp ({pos}/5 positive)")

# =====================================================================
# TEST 6: Inverted momentum -- rolling HIGH triple -> LOWER valuable
# =====================================================================
print("\n" + "=" * 70)
print("TEST 6: Inverted momentum -- hot triple streak -> cold valuable")
print("=" * 70)

for ws in [5, 10, 20]:
    print(f"\n  Window = {ws}:")
    for fold in range(n_folds):
        start = fold * fold_size
        end = start + fold_size if fold < n_folds - 1 else N
        fr = rows[start:end]

        vals = []
        for i in range(ws, len(fr)):
            rate = sum(1 for j in range(i-ws, i) if fr[j]['is_triple']) / ws
            vals.append(rate)

        if not vals:
            continue
        med = sorted(vals)[len(vals)//2]

        hh, hn, lh, ln = 0, 0, 0, 0
        for i, v in enumerate(vals):
            idx = i + ws
            if idx >= len(fr):
                continue
            if v > med:
                hn += 1; hh += int(fr[idx]['is_valuable'])
            else:
                ln += 1; lh += int(fr[idx]['is_valuable'])

        hr = hh / hn if hn > 0 else 0
        lr = lh / ln if ln > 0 else 0
        print(f"    Fold {fold}: HOT_STREAK={100*hr:.1f}% (n={hn}) "
              f"COLD_STREAK={100*lr:.1f}% (n={ln}) spread={100*(hr-lr):+.1f}pp")

print("\n" + "=" * 70)
print("DONE")
print("=" * 70)
