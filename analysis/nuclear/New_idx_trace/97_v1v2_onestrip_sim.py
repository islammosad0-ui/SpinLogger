"""
97_v1v2_onestrip_sim.py — V1/V2 scorers: original vs one-strip-swap-corrected
One-strip model: r1_idx controls r3 display, r3_idx controls r1 display
So all r1↔r3 idx references in scorer rules should be swapped.
"""
import csv, json, math, sys
from collections import defaultdict
from pathlib import Path
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =====================================================================
#  Data loading — ALL files with idx (targeting ~8067 spins)
# =====================================================================
SYM_CODE = {
    'attack': 3, 'steal': 4, 'shield': 5, 'spins': 6,
    'coin': 1, 'goldSack': 2, 'accumulation': 30, 'potion': 7,
}

def load_csv_auto(path, label):
    """Load CSV, auto-detect idx columns and VT definition."""
    rows = []
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames
        if not cols or 'r1_idx' not in cols:
            print(f"  {label}: no r1_idx column, skip")
            return rows
        has_valuable = 'is_valuable' in cols
        has_s1 = 's1' in cols
        for r in reader:
            try:
                r1 = int(r['r1_idx'])
                r2 = int(r['r2_idx'])
                r3 = int(r['r3_idx'])
            except (ValueError, KeyError):
                continue
            if r1 < 0 or r2 < 0 or r3 < 0:
                continue
            is_trip = str(r.get('is_triple', '')).strip().lower() in ('true', '1')
            # VT definition
            if has_valuable:
                vt = str(r.get('is_valuable', '')).strip().lower() in ('true', '1')
            elif has_s1:
                try:
                    s1 = int(r['s1'])
                except (ValueError, KeyError):
                    s1 = SYM_CODE.get(r.get('reel_1', ''), -1)
                vt = is_trip and s1 in [30, 6]
            else:
                # Fallback: use spin_result
                sr = str(r.get('spin_result', '')).strip().lower()
                vt = is_trip and sr == 'spins'
                # Also check for ACC triple (all idx==8)
                if is_trip and r1 == 8 and r2 == 8 and r3 == 8:
                    vt = True

            rows.append({
                'r1': r1, 'r2': r2, 'r3': r3,
                'is_triple': is_trip, 'is_vt': vt,
                'source': label,
            })
    return rows


files = [
    (ROOT / 'data' / 'Ahmed' / 'spin_history_Ahmed_enriched_v2.csv', 'Ahmed_v2'),
    (ROOT / 'data' / 'Ahmed' / 'spin_history_Ahmed_2026-04-13.csv', 'Ahmed_0413'),
    (ROOT / 'data' / 'Ahmed' / 'spin_history_Ahmed_2026-04-14.csv', 'Ahmed_0414'),
    (ROOT / 'data' / 'Islam' / 'spin_history_Islam_2026-04-13.csv', 'Islam'),
    (ROOT / 'data' / 'Nick' / 'spin_history_Nick_2026-04-13.csv', 'Nick'),
]

print("Loading data...")
all_rows = []
for path, label in files:
    if not path.exists():
        print(f"  {label}: file not found, skip")
        continue
    rr = load_csv_auto(str(path), label)
    print(f"  {label}: {len(rr)} spins, {sum(1 for r in rr if r['is_vt'])} VTs")
    all_rows.extend(rr)

rows = all_rows
N = len(rows)
n_vt = sum(1 for r in rows if r['is_vt'])
base_rate = n_vt / N if N else 0
print(f"\nTotal: {N} spins, {n_vt} VTs ({100*base_rate:.2f}%, 1 per {N//n_vt if n_vt else 0})")

# =====================================================================
#  Helpers
# =====================================================================
def fisher_p(hits, n, base):
    if n == 0 or hits == 0: return 1.0
    return 1 - binom.cdf(hits - 1, n, base)

def wilson_ci(hits, n, z=1.96):
    if n == 0: return (0, 0)
    p = hits / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    m = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (max(0, c-m), min(1, c+m))

def is_vt(r):
    return r['is_vt']


# =====================================================================
#  ORIGINAL V1 SCORER (unchanged from 83_v2_complete_sim.py)
# =====================================================================
def v1_l1_orig(prev):
    r1, r2, r3 = prev['r1'], prev['r2'], prev['r3']
    s = 0
    if r2 == 7: s += 2
    if r1 == 7: s += 1
    if r2 == 3: s += 1
    if r1 == 3: s += 1
    if r3 == 1: s -= 2
    if r2 == 0: s -= 1
    if r2 == 2: s -= 1
    if r1 == 5: s -= 1
    if r1 == 0: s -= 1
    if r1 == 7 and r2 == 7: s += 2
    if r1 == 7 and r3 == 8: s += 1
    if r2 == 7 and r3 == 8: s += 1
    if r1 == 3 and r2 == 7: s += 1
    if r1 == 3 and r2 == 4: s += 1
    if r1 == 4 and r2 == 4: s -= 2
    if r1 == 7 and r3 == 0: s -= 2
    if r1 == 4 and r3 == 4: s -= 1
    return s

def v1_l2_orig(rows, i, window=10):
    if i < 3: return 0
    start = max(0, i - window)
    win = rows[start:i]; wsize = len(win)
    if wsize < 3: return 0
    score = 0
    # A: steal count (s1-based, stays)
    # NOTE: s1 not available in all files, skip this check
    # B: r3=4 count
    if sum(1 for r in win if r['r3'] == 4) >= 2: score += 1
    # C: bigram r3: 0->8
    if any(win[j-1]['r3']==0 and win[j]['r3']==8 for j in range(1, wsize)): score += 1
    # D: bigram r3: 8->4 or 4->4
    if any((win[j-1]['r3']==8 and win[j]['r3']==4) or (win[j-1]['r3']==4 and win[j]['r3']==4) for j in range(1, wsize)): score += 1
    # E: r2=6 gap
    r2_6_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r2'] == 6: r2_6_gap = lb; break
    if 0 < r2_6_gap <= 7: score += 1
    # F/G: r3=1 gap
    r3_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r3'] == 1: r3_1_gap = lb; break
    if r3_1_gap < 0 or r3_1_gap > 10: score += 1
    if 0 < r3_1_gap <= 3: score -= 2
    # H: tuple (r1=3, r2=6, r3=4)
    if any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win): score += 1
    # I: r3 variety
    if wsize > 1:
        dups = sum(1 for j in range(1, wsize) if win[j]['r3']==win[j-1]['r3'])
        if dups/(wsize-1) < 0.15: score += 1
    # J: r1 bigram (3,3) +1
    if any(win[j-1]['r1']==3 and win[j]['r1']==3 for j in range(1, wsize)): score += 1
    return score


# =====================================================================
#  SWAP-CORRECTED V1 SCORER (all r1↔r3, r2 stays, s1 stays)
# =====================================================================
def v1_l1_swap(prev):
    r1, r2, r3 = prev['r1'], prev['r2'], prev['r3']
    s = 0
    # Positives (r1->r3, r3->r1)
    if r2 == 7: s += 2      # r2 stays
    if r3 == 7: s += 1      # was r1==7
    if r2 == 3: s += 1      # r2 stays
    if r3 == 3: s += 1      # was r1==3
    # Negatives
    if r1 == 1: s -= 2      # was r3==1
    if r2 == 0: s -= 1      # r2 stays
    if r2 == 2: s -= 1      # r2 stays
    if r3 == 5: s -= 1      # was r1==5
    if r3 == 0: s -= 1      # was r1==0
    # Pair bonuses
    if r3 == 7 and r2 == 7: s += 2    # was r1==7 & r2==7
    if r3 == 7 and r1 == 8: s += 1    # was r1==7 & r3==8
    if r2 == 7 and r1 == 8: s += 1    # was r2==7 & r3==8
    if r3 == 3 and r2 == 7: s += 1    # was r1==3 & r2==7
    if r3 == 3 and r2 == 4: s += 1    # was r1==3 & r2==4
    # Dead pairs
    if r3 == 4 and r2 == 4: s -= 2    # was r1==4 & r2==4
    if r3 == 7 and r1 == 0: s -= 2    # was r1==7 & r3==0
    if r3 == 4 and r1 == 4: s -= 1    # was r1==4 & r3==4
    return s

def v1_l2_swap(rows, i, window=10):
    if i < 3: return 0
    start = max(0, i - window)
    win = rows[start:i]; wsize = len(win)
    if wsize < 3: return 0
    score = 0
    # A: steal count — skipped (s1 not always available)
    # B: r1=4 count (was r3=4)
    if sum(1 for r in win if r['r1'] == 4) >= 2: score += 1
    # C: bigram r1: 0->8 (was r3: 0->8)
    if any(win[j-1]['r1']==0 and win[j]['r1']==8 for j in range(1, wsize)): score += 1
    # D: bigram r1: 8->4 or 4->4 (was r3)
    if any((win[j-1]['r1']==8 and win[j]['r1']==4) or (win[j-1]['r1']==4 and win[j]['r1']==4) for j in range(1, wsize)): score += 1
    # E: r2=6 gap (stays)
    r2_6_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r2'] == 6: r2_6_gap = lb; break
    if 0 < r2_6_gap <= 7: score += 1
    # F/G: r1=1 gap (was r3=1)
    r1_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r1'] == 1: r1_1_gap = lb; break
    if r1_1_gap < 0 or r1_1_gap > 10: score += 1
    if 0 < r1_1_gap <= 3: score -= 2
    # H: tuple (r3=3, r2=6, r1=4) — was (r1=3, r2=6, r3=4)
    if any(r['r3']==3 and r['r2']==6 and r['r1']==4 for r in win): score += 1
    # I: r1 variety (was r3)
    if wsize > 1:
        dups = sum(1 for j in range(1, wsize) if win[j]['r1']==win[j-1]['r1'])
        if dups/(wsize-1) < 0.15: score += 1
    # J: r3 bigram (3,3) +1 (was r1)
    if any(win[j-1]['r3']==3 and win[j]['r3']==3 for j in range(1, wsize)): score += 1
    return score


# =====================================================================
#  ORIGINAL V2 SCORER
# =====================================================================
def v2_l1_orig(prev, prev2=None, prev3=None):
    r1, r2, r3 = prev['r1'], prev['r2'], prev['r3']
    s = 0
    # Positives
    if r2 == 7: s += 2
    if r1 == 7: s += 1
    if r2 == 3: s += 1
    if r1 == 3: s += 1
    if r3 == 3: s += 1
    if r3 == 5: s += 1
    if r3 == 8: s += 1
    # Negatives
    if r3 == 1: s -= 2
    if r2 == 5: s -= 2
    if r3 == 7: s -= 1
    if r2 == 0: s -= 1
    if r2 == 2: s -= 1
    if r1 == 5: s -= 1
    if r1 == 0: s -= 1
    # Pair bonuses
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
    # Dead pairs
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
    # Dead tuples
    if r1 == 4 and r2 == 4 and r3 == 4: s -= 2
    if r1 == 7 and r2 == 6 and r3 == 0: s -= 1
    if r1 == 6 and r2 == 4 and r3 == 1: s -= 1
    if r1 == 1 and r2 == 1 and r3 == 1: s -= 1
    # Multi-lag
    if prev2 is not None:
        if prev2['r3'] == r3:           s += 1
        if prev2['r3'] == 5 and r3 == 5: s += 1
        if prev2['r3'] == 8 and r3 == 5: s += 1
        if prev2['r3'] == 6: s -= 1
        if prev2['r3'] == 2: s -= 1
        if prev2['r1'] == 2: s -= 1
    if prev3 is not None:
        if prev3['r3'] == 4: s += 1
        if prev3['r1'] == 8: s -= 1
    return s

def v2_l2_orig(rows, i, window=10):
    if i < 3: return 0
    start = max(0, i - window)
    win = rows[start:i]; wsize = len(win)
    if wsize < 3: return 0
    score = 0
    # A: steal s1 — skipped
    # B: r3=4
    if sum(1 for r in win if r['r3'] == 4) >= 2: score += 1
    # C: bigram r3: 0->8
    if any(win[j-1]['r3']==0 and win[j]['r3']==8 for j in range(1, wsize)): score += 1
    # D: bigram r3: 8->4 or 4->4
    if any((win[j-1]['r3']==8 and win[j]['r3']==4) or (win[j-1]['r3']==4 and win[j]['r3']==4) for j in range(1, wsize)): score += 1
    # E: REMOVED in V2
    # F/G: r3=1 gap
    r3_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r3'] == 1: r3_1_gap = lb; break
    if r3_1_gap < 0 or r3_1_gap > 10: score += 1
    if 0 < r3_1_gap <= 3: score -= 2
    # H: tuple (r1=3, r2=6, r3=4)
    if any(r['r1']==3 and r['r2']==6 and r['r3']==4 for r in win): score += 1
    # I: REMOVED in V2
    # J: FLIPPED in V2
    if any(win[j-1]['r1']==3 and win[j]['r1']==3 for j in range(1, wsize)): score -= 1
    return score


# =====================================================================
#  SWAP-CORRECTED V2 SCORER (all r1↔r3)
# =====================================================================
def v2_l1_swap(prev, prev2=None, prev3=None):
    r1, r2, r3 = prev['r1'], prev['r2'], prev['r3']
    s = 0
    # Positives (swap r1↔r3)
    if r2 == 7: s += 2      # stays
    if r3 == 7: s += 1      # was r1
    if r2 == 3: s += 1      # stays
    if r3 == 3: s += 1      # was r1
    if r1 == 3: s += 1      # was r3
    if r1 == 5: s += 1      # was r3
    if r1 == 8: s += 1      # was r3
    # Negatives
    if r1 == 1: s -= 2      # was r3
    if r2 == 5: s -= 2      # stays
    if r1 == 7: s -= 1      # was r3
    if r2 == 0: s -= 1      # stays
    if r2 == 2: s -= 1      # stays
    if r3 == 5: s -= 1      # was r1
    if r3 == 0: s -= 1      # was r1
    # Pair bonuses (swap r1↔r3)
    if r3 == 7 and r2 == 7: s += 2    # was r1,r2
    if r3 == 7 and r1 == 8: s += 1    # was r1,r3
    if r2 == 7 and r1 == 8: s += 1    # was r2,r3
    if r3 == 3 and r2 == 7: s += 1    # was r1,r2
    if r3 == 3 and r2 == 4: s += 1    # was r1,r2
    if r3 == 7 and r2 == 3: s += 2    # was r1,r2
    if r2 == 4 and r1 == 5: s += 1    # was r2,r3
    if r2 == 3 and r1 == 8: s += 1    # was r2,r3
    if r3 == 6 and r1 == 5: s += 1    # was r1,r3
    if r3 == 3 and r1 == 0: s += 1    # was r1,r3
    # Dead pairs (swap r1↔r3)
    if r3 == 4 and r2 == 4: s -= 2    # was r1,r2
    if r3 == 7 and r1 == 0: s -= 2    # was r1,r3
    if r3 == 4 and r1 == 4: s -= 1    # was r1,r3
    if r2 == 5 and r1 == 1: s -= 2    # was r2,r3
    if r3 == 1 and r1 == 1: s -= 1    # was r1,r3
    if r3 == 5 and r2 == 5: s -= 1    # was r1,r2
    if r2 == 3 and r1 == 7: s -= 1    # was r2,r3
    if r3 == 7 and r1 == 7: s -= 1    # was r1,r3
    if r2 == 6 and r1 == 1: s -= 1    # was r2,r3
    if r3 == 6 and r2 == 5: s -= 1    # was r1,r2
    if r3 == 5 and r1 == 1: s -= 1    # was r1,r3
    # Dead tuples (swap r1↔r3)
    if r3 == 4 and r2 == 4 and r1 == 4: s -= 2    # symmetric
    if r3 == 7 and r2 == 6 and r1 == 0: s -= 1    # was r1,r2,r3
    if r3 == 6 and r2 == 4 and r1 == 1: s -= 1    # was r1,r2,r3
    if r3 == 1 and r2 == 1 and r1 == 1: s -= 1    # symmetric
    # Multi-lag (swap r1↔r3 in prev2/prev3 too)
    if prev2 is not None:
        if prev2['r1'] == r1:           s += 1   # was prev2.r3==r3
        if prev2['r1'] == 5 and r1 == 5: s += 1  # was prev2.r3==5 & r3==5
        if prev2['r1'] == 8 and r1 == 5: s += 1  # was prev2.r3==8 & r3==5
        if prev2['r1'] == 6: s -= 1              # was prev2.r3==6
        if prev2['r1'] == 2: s -= 1              # was prev2.r3==2
        if prev2['r3'] == 2: s -= 1              # was prev2.r1==2
    if prev3 is not None:
        if prev3['r1'] == 4: s += 1              # was prev3.r3==4
        if prev3['r3'] == 8: s -= 1              # was prev3.r1==8
    return s

def v2_l2_swap(rows, i, window=10):
    if i < 3: return 0
    start = max(0, i - window)
    win = rows[start:i]; wsize = len(win)
    if wsize < 3: return 0
    score = 0
    # A: steal s1 — skipped
    # B: r1=4 (was r3=4)
    if sum(1 for r in win if r['r1'] == 4) >= 2: score += 1
    # C: bigram r1: 0->8 (was r3)
    if any(win[j-1]['r1']==0 and win[j]['r1']==8 for j in range(1, wsize)): score += 1
    # D: bigram r1: 8->4 or 4->4 (was r3)
    if any((win[j-1]['r1']==8 and win[j]['r1']==4) or (win[j-1]['r1']==4 and win[j]['r1']==4) for j in range(1, wsize)): score += 1
    # E: REMOVED
    # F/G: r1=1 gap (was r3=1)
    r1_1_gap = -1
    for lb in range(1, wsize+1):
        if win[-lb]['r1'] == 1: r1_1_gap = lb; break
    if r1_1_gap < 0 or r1_1_gap > 10: score += 1
    if 0 < r1_1_gap <= 3: score -= 2
    # H: tuple (r3=3, r2=6, r1=4) — was (r1=3, r2=6, r3=4)
    if any(r['r3']==3 and r['r2']==6 and r['r1']==4 for r in win): score += 1
    # I: REMOVED
    # J: FLIPPED — r3 bigram (3,3) -1 (was r1)
    if any(win[j-1]['r3']==3 and win[j]['r3']==3 for j in range(1, wsize)): score -= 1
    return score


# =====================================================================
#  SIMULATION ENGINE
# =====================================================================
THRESHOLDS = [
    ('ALL (>=0)',  0),
    ('>=1',        1),
    ('>=2',        2),
    ('>=3',        3),
    ('>=4',        4),
    ('>=5',        5),
    ('>=6',        6),
    ('>=8',        8),
    ('>=10',      10),
    ('>=12',      12),
]

def run_sim(rows, l1_fn, l2_fn, label, has_multilag=False):
    N = len(rows)
    scores = [0]*N
    for i in range(1, N):
        prev = rows[i-1]
        if has_multilag:
            prev2 = rows[i-2] if i >= 2 else None
            prev3 = rows[i-3] if i >= 3 else None
            l1 = l1_fn(prev, prev2, prev3)
        else:
            l1 = l1_fn(prev)
        l2 = l2_fn(rows, i)
        scores[i] = l1 + l2

    results = {}
    for name, thresh in THRESHOLDS:
        bets = catches = missed = 0
        for i in range(1, N):
            hit = is_vt(rows[i])
            if scores[i] >= thresh:
                bets += 1
                if hit: catches += 1
            elif hit:
                missed += 1
        cr = catches / n_vt if n_vt else 0
        prec = catches / bets if bets else 0
        bph = bets / catches if catches else float('inf')
        lift = prec / base_rate if base_rate else 0
        pval = fisher_p(catches, bets, base_rate)
        lo, hi = wilson_ci(catches, bets)
        results[name] = {
            'thresh': thresh, 'bets': bets, 'catches': catches,
            'missed': missed, 'cr': cr, 'prec': prec, 'bph': bph,
            'lift': lift, 'pval': pval, 'ci_lo': lo, 'ci_hi': hi,
        }

    # Score distribution
    dist = defaultdict(lambda: {'n': 0, 'h': 0})
    for i in range(1, N):
        dist[scores[i]]['n'] += 1
        if is_vt(rows[i]):
            dist[scores[i]]['h'] += 1

    return results, dist, scores


def print_kpi(results, label):
    print(f"\n  {label}:")
    print(f"  {'Tier':>10} {'Thr':>4} {'Bets':>6} {'Cat':>4} {'Miss':>4} "
          f"{'CatR':>6} {'Prec':>7} {'B/H':>6} {'Lift':>5} {'Bet%':>5} {'p':>8} {'CI95':>14}")
    print(f"  {'-'*100}")
    for name, _ in THRESHOLDS:
        r = results[name]
        ci = f"[{100*r['ci_lo']:.1f}-{100*r['ci_hi']:.1f}]"
        bph = f"{r['bph']:.1f}" if r['bph'] < 9999 else "inf"
        print(f"  {name:>10} {r['thresh']:>4} {r['bets']:>6} {r['catches']:>4} {r['missed']:>4} "
              f"{100*r['cr']:>5.1f}% {100*r['prec']:>6.2f}% {bph:>6} "
              f"{r['lift']:>4.1f}x {100*r['bets']/(N-1):>4.1f}% {r['pval']:>8.4f} {ci:>14}")


def print_dist(dist, label):
    print(f"\n  {label}:")
    print(f"  {'Sc':>4} {'Spins':>6} {'Hits':>4} {'Rate':>6} {'Lift':>5} {'CumH':>4} {'Cum%':>5}")
    print(f"  {'-'*42}")
    cum = 0
    for sc in sorted(dist.keys(), reverse=True):
        d = dist[sc]
        rate = d['h'] / d['n'] if d['n'] else 0
        lift = rate / base_rate if base_rate else 0
        cum += d['h']
        cumc = cum / n_vt if n_vt else 0
        if d['n'] >= 3 or d['h'] > 0:
            print(f"  {sc:>4} {d['n']:>6} {d['h']:>4} {100*rate:>5.1f}% {lift:>4.1f}x {cum:>4} {100*cumc:>4.1f}%")


# =====================================================================
#  RUN ALL 4 VARIANTS
# =====================================================================
print(f"\n{'='*100}")
print("  A) V1 ORIGINAL")
print('='*100)
v1o_res, v1o_dist, v1o_scores = run_sim(rows, v1_l1_orig, v1_l2_orig, "V1-orig")
print_dist(v1o_dist, "V1-orig score distribution")
print_kpi(v1o_res, "V1-orig KPIs")

print(f"\n\n{'='*100}")
print("  B) V1 SWAP-CORRECTED")
print('='*100)
v1s_res, v1s_dist, v1s_scores = run_sim(rows, v1_l1_swap, v1_l2_swap, "V1-swap")
print_dist(v1s_dist, "V1-swap score distribution")
print_kpi(v1s_res, "V1-swap KPIs")

print(f"\n\n{'='*100}")
print("  C) V2 ORIGINAL")
print('='*100)
v2o_res, v2o_dist, v2o_scores = run_sim(rows, v2_l1_orig, v2_l2_orig, "V2-orig", has_multilag=True)
print_dist(v2o_dist, "V2-orig score distribution")
print_kpi(v2o_res, "V2-orig KPIs")

print(f"\n\n{'='*100}")
print("  D) V2 SWAP-CORRECTED")
print('='*100)
v2s_res, v2s_dist, v2s_scores = run_sim(rows, v2_l1_swap, v2_l2_swap, "V2-swap", has_multilag=True)
print_dist(v2s_dist, "V2-swap score distribution")
print_kpi(v2s_res, "V2-swap KPIs")


# =====================================================================
#  HEAD-TO-HEAD COMPARISON
# =====================================================================
print(f"\n\n{'='*100}")
print("  HEAD-TO-HEAD: ORIGINAL vs SWAP-CORRECTED")
print('='*100)
print(f"\n  Dataset: {N} spins, {n_vt} VTs ({100*base_rate:.2f}%)")

for v_label, orig_res, swap_res in [("V1", v1o_res, v1s_res), ("V2", v2o_res, v2s_res)]:
    print(f"\n  --- {v_label} ---")
    print(f"  {'Tier':>10} | {'ORIG B/H':>8} {'ORIG Prec':>10} {'ORIG Cat':>9} | "
          f"{'SWAP B/H':>8} {'SWAP Prec':>10} {'SWAP Cat':>9} | {'Winner':>7} {'Delta B/H':>10}")
    print(f"  {'-'*105}")
    for name, _ in THRESHOLDS:
        o = orig_res[name]
        s = swap_res[name]
        o_bph = f"{o['bph']:.1f}" if o['bph'] < 9999 else "inf"
        s_bph = f"{s['bph']:.1f}" if s['bph'] < 9999 else "inf"
        o_prec = f"{100*o['prec']:.2f}%"
        s_prec = f"{100*s['prec']:.2f}%"
        o_cat = f"{100*o['cr']:.1f}%"
        s_cat = f"{100*s['cr']:.1f}%"

        winner = ""
        delta = ""
        if o['catches'] > 0 and s['catches'] > 0:
            d = o['bph'] - s['bph']
            if abs(d) > 0.1:
                winner = "SWAP" if d > 0 else "ORIG"
                delta = f"{d:+.1f}"
            else:
                winner = "TIE"
                delta = "0.0"
        elif o['catches'] == 0 and s['catches'] == 0:
            winner = "TIE"
            delta = "-"
        elif s['catches'] > 0:
            winner = "SWAP"
            delta = "N/A"
        else:
            winner = "ORIG"
            delta = "N/A"

        print(f"  {name:>10} | {o_bph:>8} {o_prec:>10} {o_cat:>9} | "
              f"{s_bph:>8} {s_prec:>10} {s_cat:>9} | {winner:>7} {delta:>10}")


# =====================================================================
#  SPIN-BY-SPIN AGREEMENT
# =====================================================================
print(f"\n\n{'='*100}")
print("  SPIN-BY-SPIN SCORE AGREEMENT")
print('='*100)

for v_label, orig_scores, swap_scores in [("V1", v1o_scores, v1s_scores), ("V2", v2o_scores, v2s_scores)]:
    same = sum(1 for i in range(1, N) if orig_scores[i] == swap_scores[i])
    diff = N - 1 - same
    avg_orig = sum(orig_scores[1:]) / (N-1)
    avg_swap = sum(swap_scores[1:]) / (N-1)
    corr_num = sum((orig_scores[i]-avg_orig)*(swap_scores[i]-avg_swap) for i in range(1,N))
    corr_den1 = sum((orig_scores[i]-avg_orig)**2 for i in range(1,N))**0.5
    corr_den2 = sum((swap_scores[i]-avg_swap)**2 for i in range(1,N))**0.5
    corr = corr_num / (corr_den1 * corr_den2) if corr_den1 * corr_den2 > 0 else 0

    print(f"\n  {v_label}: {same}/{N-1} identical ({100*same/(N-1):.1f}%), {diff} differ")
    print(f"  {v_label}: avg score orig={avg_orig:.2f}, swap={avg_swap:.2f}, correlation={corr:.3f}")

    # Where swap differs on VT spins
    vt_orig_better = vt_swap_better = vt_same = 0
    for i in range(1, N):
        if is_vt(rows[i]):
            if orig_scores[i] > swap_scores[i]: vt_orig_better += 1
            elif swap_scores[i] > orig_scores[i]: vt_swap_better += 1
            else: vt_same += 1
    print(f"  {v_label} on VT spins: orig-higher={vt_orig_better}, swap-higher={vt_swap_better}, same={vt_same}")

print("\nDone.")
