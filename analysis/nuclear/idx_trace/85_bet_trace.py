#!/usr/bin/env python3
"""
85_bet_trace.py — Visual bet-by-bet trace for each combo at key thresholds.

Shows every spin where score >= threshold, what was caught, gaps, and running stats.
"""

import csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SYM_CODE = {
    'attack': 3, 'steal': 4, 'shield': 5, 'spins': 6,
    'coin': 1, 'goldSack': 2, 'accumulation': 30, 'potion': 7,
}

def load_ahmed_v2():
    path = ROOT / "data" / "Ahmed" / "spin_history_Ahmed_enriched_v2.csv"
    rows = []
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            if r['r1_idx'] == '' or int(r['r1_idx']) < 0: continue
            rows.append({
                'r1': int(r['r1_idx']), 'r2': int(r['r2_idx']), 'r3': int(r['r3_idx']),
                's1': int(r['s1']), 'is_triple': r['is_triple'] == 'True',
                'reel_1': r['reel_1'], 'src': 'A',
            })
    return rows

def load_nick_59col():
    path = ROOT / "data" / "Nick" / "spin_history_Nick_2026-04-08 (1).csv"
    rows = []
    with open(path, newline='') as f:
        reader = csv.reader(f)
        next(reader)
        for fields in reader:
            if len(fields) != 59: continue
            if int(fields[0]) < 69879: continue
            r1_idx = fields[53]
            if r1_idx == '' or int(r1_idx) < 0: continue
            rows.append({
                'r1': int(r1_idx), 'r2': int(fields[54]), 'r3': int(fields[55]),
                's1': SYM_CODE.get(fields[5], -1), 'is_triple': fields[10].lower() == 'true',
                'reel_1': fields[5], 'src': 'N',
            })
    return rows

rows = load_ahmed_v2() + load_nick_59col()
N = len(rows)

def is_vt(r): return r['is_triple'] and r['s1'] in (30, 6)
def is_acc(r): return r['is_triple'] and r['s1'] == 30
def is_spn(r): return r['is_triple'] and r['s1'] == 6

n_vt = sum(1 for r in rows if is_vt(r))
n_acc = sum(1 for r in rows if is_acc(r))
n_spn = sum(1 for r in rows if is_spn(r))
print(f"Data: {N} spins, VT={n_vt} (ACC={n_acc}, SPN={n_spn})\n")

# =====================================================================
#  Scorers
# =====================================================================
def v2_l1(rows, i):
    if i < 1: return 0
    prev = rows[i-1]
    r1, r2, r3 = prev['r1'], prev['r2'], prev['r3']
    s = 0
    if r2 == 7: s += 2
    if r1 == 7: s += 1
    if r2 == 3: s += 1
    if r1 == 3: s += 1
    if r3 == 3: s += 1
    if r3 == 5: s += 1
    if r3 == 8: s += 1
    if r3 == 1: s -= 2
    if r2 == 5: s -= 2
    if r3 == 7: s -= 1
    if r2 == 0: s -= 1
    if r2 == 2: s -= 1
    if r1 == 5: s -= 1
    if r1 == 0: s -= 1
    if r1 == 7 and r2 == 7: s += 2
    if r1 == 7 and r3 == 8: s += 1
    if r2 == 7 and r3 == 8: s += 1
    if r1 == 3 and r2 == 7: s += 1
    if r1 == 3 and r2 == 4: s += 1
    if r1 == 7 and r2 == 3: s += 2
    if r2 == 4 and r3 == 5: s += 1
    if r2 == 3 and r3 == 8: s += 1
    if r1 == 6 and r3 == 5: s += 1
    if r1 == 3 and r3 == 0: s += 1
    if r1 == 4 and r2 == 4: s -= 2
    if r1 == 7 and r3 == 0: s -= 2
    if r1 == 4 and r3 == 4: s -= 1
    if r2 == 5 and r3 == 1: s -= 2
    if r1 == 1 and r3 == 1: s -= 1
    if r1 == 5 and r2 == 5: s -= 1
    if r2 == 3 and r3 == 7: s -= 1
    if r1 == 7 and r3 == 7: s -= 1
    if r2 == 6 and r3 == 1: s -= 1
    if r1 == 6 and r2 == 5: s -= 1
    if r1 == 5 and r3 == 1: s -= 1
    if r1 == 4 and r2 == 4 and r3 == 4: s -= 2
    if r1 == 7 and r2 == 6 and r3 == 0: s -= 1
    if r1 == 6 and r2 == 4 and r3 == 1: s -= 1
    if r1 == 1 and r2 == 1 and r3 == 1: s -= 1
    # Multi-lag + sequences
    if i >= 2:
        prev2 = rows[i-2]
        if prev2['r3'] == r3:           s += 1
        if prev2['r3'] == 5 and r3 == 5: s += 1
        if prev2['r3'] == 8 and r3 == 5: s += 1
        if prev2['r3'] == 6: s -= 1
        if prev2['r3'] == 2: s -= 1
        if prev2['r1'] == 2: s -= 1
    if i >= 3:
        prev3 = rows[i-3]
        if prev3['r3'] == 4: s += 1
        if prev3['r1'] == 8: s -= 1
    return s

def v2_l2(rows, i, window=10):
    if i < 3: return 0
    start = max(0, i - window)
    win = rows[start:i]; wsize = len(win)
    if wsize < 3: return 0
    score = 0
    if sum(1 for r in win if r['s1'] == 4) >= 2: score += 1
    if sum(1 for r in win if r['r3'] == 4) >= 2: score += 1
    if any(win[j-1]['r3']==0 and win[j]['r3']==8 for j in range(1, wsize)): score += 1
    if any((win[j-1]['r3']==8 and win[j]['r3']==4) or (win[j-1]['r3']==4 and win[j]['r3']==4) for j in range(1, wsize)): score += 1
    r3_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r3'] == 1: r3_1_gap = lb; break
    if r3_1_gap < 0 or r3_1_gap > 10: score += 1
    if 0 < r3_1_gap <= 3: score -= 2
    if any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win): score += 1
    if any(win[j-1]['r1']==3 and win[j]['r1']==3 for j in range(1, wsize)): score -= 1
    return score

# New pattern bonuses
def pat_A(rows, i):  # bb_r1
    if i < 2: return 0
    return 1 if rows[i-2]['r1'] == rows[i-1]['r1'] else 0

def pat_B(rows, i):  # r1:(3,7)
    if i < 2: return 0
    return 1 if rows[i-2]['r1'] == 3 and rows[i-1]['r1'] == 7 else 0

def pat_D(rows, i):  # sum123=15
    if i < 1: return 0
    p = rows[i-1]
    return 1 if p['r1'] + p['r2'] + p['r3'] == 15 else 0

def pat_F(rows, i):  # xr2r3(7,8)
    if i < 2: return 0
    return 1 if rows[i-2]['r2'] == 7 and rows[i-1]['r3'] == 8 else 0

# Build reasons for what fired
def explain(rows, i, active_pats):
    parts = []
    prev = rows[i-1]
    r1, r2, r3 = prev['r1'], prev['r2'], prev['r3']
    # Key L1 signals
    if r2 == 7: parts.append('r2=7*')
    if r1 == 7: parts.append('r1=7')
    if r2 == 3: parts.append('r2=3')
    if r1 == 3: parts.append('r1=3')
    if r3 == 3: parts.append('r3=3')
    if r3 == 5: parts.append('r3=5')
    if r3 == 8: parts.append('r3=8')
    if r1 == 7 and r2 == 7: parts.append('77P')
    if r1 == 7 and r2 == 3: parts.append('73P')
    if r3 == 1: parts.append('r3=1X')
    if r2 == 5: parts.append('r2=5X')
    # Sequences
    if i >= 2:
        prev2 = rows[i-2]
        if prev2['r3'] == r3: parts.append('dr3=0')
        if prev2['r3'] == 5 and r3 == 5: parts.append('55seq')
        if prev2['r3'] == 8 and r3 == 5: parts.append('85seq')
    # New patterns
    for tag, fn in active_pats:
        if fn(rows, i): parts.append(tag)
    return ' '.join(parts) if parts else '-'

# =====================================================================
#  Trace function
# =====================================================================
def print_trace(label, rows, score_fn, thresholds, active_pats=[]):
    print(f"\n{'='*120}")
    print(f"  {label}")
    print(f"{'='*120}")

    # Compute all scores
    scores = [0]*N
    for i in range(1, N):
        scores[i] = score_fn(rows, i)

    for thresh_name, thresh in thresholds:
        bets = 0; catches = 0; acc_c = 0; spn_c = 0
        missed_vt = []
        last_bet = -1

        print(f"\n  --- {thresh_name} (score >= {thresh}) ---")
        print(f"  {'#':>4} {'Spin':>5} {'Src':>3} {'Idx(prev)':>12} {'Score':>5} {'Gap':>5} "
              f"{'Result':>8} {'Type':>4} {'RunB/H':>7} {'Signals':>30}")
        print(f"  {'-'*105}")

        for i in range(1, N):
            hit = is_vt(rows[i])
            if scores[i] >= thresh:
                bets += 1
                gap = i - last_bet if last_bet >= 0 else i
                last_bet = i

                result = ''
                typ = ''
                if hit:
                    catches += 1
                    if is_acc(rows[i]):
                        acc_c += 1
                        result = '>>> ACC'
                        typ = 'ACC'
                    else:
                        spn_c += 1
                        result = '>>> SPN'
                        typ = 'SPN'
                else:
                    result = '   miss'
                    typ = ''

                run_bph = f"{bets/catches:.1f}" if catches > 0 else "inf"
                prev = rows[i-1]
                reason = explain(rows, i, active_pats)

                # Only print catches and every 10th miss to keep it readable
                if hit or bets <= 5 or bets % 10 == 0:
                    print(f"  {bets:>4} {i:>5} {rows[i]['src']:>3} ({prev['r1']},{prev['r2']},{prev['r3']}) "
                          f"{scores[i]:>+5} {gap:>5} {result:>8} {typ:>4} {run_bph:>7} {reason:>30}")
            elif hit:
                missed_vt.append(i)

        print(f"  {'-'*105}")
        bph = f"{bets/catches:.1f}" if catches else "inf"
        print(f"  TOTAL: {bets} bets, {catches} catches (ACC={acc_c}, SPN={spn_c}), "
              f"missed={len(missed_vt)}, B/H={bph}, catch_rate={100*catches/n_vt:.1f}%")

        # Show missed VTs
        if missed_vt and len(missed_vt) <= 20:
            print(f"  MISSED VTs:")
            for mi in missed_vt:
                prev = rows[mi-1]
                mtype = "ACC" if is_acc(rows[mi]) else "SPN"
                print(f"    spin {mi} ({rows[mi]['src']}) idx=({prev['r1']},{prev['r2']},{prev['r3']}) "
                      f"score={scores[mi]:+d} -> {mtype}")

# =====================================================================
#  Define scorer combos
# =====================================================================

# V2 base
def score_v2(rows, i):
    return v2_l1(rows, i) + v2_l2(rows, i)

# V2 + D+F (best at >=10)
def score_v2_DF(rows, i):
    return v2_l1(rows, i) + v2_l2(rows, i) + pat_D(rows, i) + pat_F(rows, i)

# V2 + A+B (best at >=8)
def score_v2_AB(rows, i):
    return v2_l1(rows, i) + v2_l2(rows, i) + pat_A(rows, i) + pat_B(rows, i)

# V2 + A+D+F (best at >=12)
def score_v2_ADF(rows, i):
    return v2_l1(rows, i) + v2_l2(rows, i) + pat_A(rows, i) + pat_D(rows, i) + pat_F(rows, i)

# =====================================================================
#  Run traces
# =====================================================================

KEY_THRESHOLDS = [
    ('>=8 (SNP)', 8),
    ('>=10',     10),
    ('>=12',     12),
]

print_trace("V2 BASE", rows, score_v2, KEY_THRESHOLDS)
print_trace("V2 + D+F (sum123=15, xr2r3(7,8))", rows, score_v2_DF, KEY_THRESHOLDS,
            [('D', pat_D), ('F', pat_F)])
print_trace("V2 + A+B (bb_r1, r1:(3,7))", rows, score_v2_AB, KEY_THRESHOLDS,
            [('A', pat_A), ('B', pat_B)])
print_trace("V2 + A+D+F (bb_r1, sum123=15, xr2r3(7,8))", rows, score_v2_ADF, KEY_THRESHOLDS,
            [('A', pat_A), ('D', pat_D), ('F', pat_F)])

print("\n\nDONE")
