"""
100_phase3_revalidate.py — re-run Phase 3 (1107-spin) strategies on the
full 7K dataset to see if the headline results hold.

Key Phase 3 rules to revalidate (from FINDINGS.md, scripts 74-78):

ALL VTs:
  R1: gap>=30 & low_mom & r1=3or7                    -> 13.3% prec, 4.2x, 23% catch, 7.5 bph
  R2: gap>=30 & r3>=5 & all_diff & sum>=15           -> 12.2% prec, 3.9x, 17% catch, 8.2 bph
  R3: gap>=40 & r3>=5 & sum>=15                      -> 10.4% prec, 3.3x, 23% catch, 9.6 bph
  R4: gap>=30 & (r3>=5 | all_diff | sum>=15 | r2=7)  -> 7.5% prec, 2.4x, 54% catch, 13.3 bph

ACC-only:
  A1: gap_acc>=60 & prev_steal                       -> 22.2%, 14.5x, 12% catch, 4.5 bph
  A2: gap>=30 & prev_steal                           -> 14.3%, 9.3x, 18% catch, 7.0 bph

SPN-only:
  S1: gap>=40 & r3>=5 & all_diff                     -> 6.5%, 4.0x, 22% catch, 15.5 bph
  S2: gap_spn>=50 & r3>=5 & sum>=15                  -> 5.5%, 3.4x, 33% catch, 18.3 bph

Caveat: Phase 4 found r1/r3 indices are SWAPPED (one-strip model).
  Original "r1=goldSack" => actually means displayed-r3 was goldSack
  Original "r3>=5"       => actually means r1_idx >= 5 (i.e. displayed-r3 strip pos)
We test BOTH the literal indices AND the corrected (swapped) versions.
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =====================================================================
#  Load data — same files as 99
# =====================================================================
files = [
    (ROOT / 'data' / 'Ahmed' / 'spin_history_Ahmed_enriched_v2.csv', 'Ahmed_v2'),
    (ROOT / 'data' / 'Ahmed' / 'spin_history_Ahmed_2026-04-13.csv', 'Ahmed_0413'),
    (ROOT / 'data' / 'Ahmed' / 'spin_history_Ahmed_2026-04-14.csv', 'Ahmed_0414'),
    (ROOT / 'data' / 'Islam' / 'spin_history_Islam_2026-04-13.csv', 'Islam'),
    (ROOT / 'data' / 'Nick' / 'spin_history_Nick_2026-04-13.csv', 'Nick'),
]

frames = []
for path, label in files:
    if not path.exists():
        continue
    try:
        df = pd.read_csv(str(path), on_bad_lines='skip')
    except Exception as e:
        print(f"  {label}: ERROR {e}")
        continue
    if 'r1_idx' not in df.columns:
        continue
    for c in ['r1_idx', 'r2_idx', 'r3_idx']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['r1_idx', 'r2_idx', 'r3_idx']).copy()
    df['r1_idx'] = df['r1_idx'].astype(int)
    df['r2_idx'] = df['r2_idx'].astype(int)
    df['r3_idx'] = df['r3_idx'].astype(int)
    df = df[(df['r1_idx'] >= 0) & (df['r2_idx'] >= 0) & (df['r3_idx'] >= 0)].copy()
    df['is_triple'] = df['is_triple'].astype(str).str.strip().str.lower().isin(['true', '1'])

    if 'is_valuable' in df.columns:
        df['is_vt'] = df['is_valuable'].astype(str).str.strip().str.lower().isin(['true', '1'])
    else:
        df['is_vt'] = False
        if 'spin_result' in df.columns:
            df['is_vt'] = df['is_triple'] & (df['spin_result'].astype(str).str.strip().str.lower() == 'spins')
        acc_mask = df['is_triple'] & (df['r1_idx'] == 8) & (df['r2_idx'] == 8) & (df['r3_idx'] == 8)
        df['is_vt'] = df['is_vt'] | acc_mask

    # ACC = accumulation triple, SPN = spins triple
    if 'spin_result' in df.columns:
        df['is_spn'] = df['is_vt'] & (df['spin_result'].astype(str).str.strip().str.lower() == 'spins')
        df['is_acc'] = df['is_vt'] & ~df['is_spn']
    else:
        df['is_acc'] = df['is_triple'] & (df['r1_idx'] == 8) & (df['r2_idx'] == 8) & (df['r3_idx'] == 8)
        df['is_spn'] = df['is_vt'] & ~df['is_acc']

    df['source'] = label
    frames.append(df)
    print(f"  {label}: {len(df)} spins, {df['is_vt'].sum()} VTs ({df['is_acc'].sum()} ACC, {df['is_spn'].sum()} SPN)")

df_all = pd.concat(frames, ignore_index=True)

# =====================================================================
#  Compute features per source: gap, gap_acc, gap_spn, prev_*, low_mom
# =====================================================================
all_dfs = []
for src in df_all['source'].unique():
    sdf = df_all[df_all['source'] == src].copy().reset_index(drop=True)

    g = g_acc = g_spn = 999
    gaps, gaps_acc, gaps_spn = [], [], []
    for i in range(len(sdf)):
        g += 1
        g_acc += 1
        g_spn += 1
        gaps.append(g)
        gaps_acc.append(g_acc)
        gaps_spn.append(g_spn)
        if sdf.loc[i, 'is_vt']:
            g = 0
        if sdf.loc[i, 'is_acc']:
            g_acc = 0
        if sdf.loc[i, 'is_spn']:
            g_spn = 0
    sdf['gap'] = gaps
    sdf['gap_acc'] = gaps_acc
    sdf['gap_spn'] = gaps_spn

    sdf['prev_r1'] = sdf['r1_idx'].shift(1)
    sdf['prev_r2'] = sdf['r2_idx'].shift(1)
    sdf['prev_r3'] = sdf['r3_idx'].shift(1)

    # Steal symbol = idx 4 (only one position)
    sdf['prev_steal'] = (sdf['prev_r1'] == 4) | (sdf['prev_r2'] == 4) | (sdf['prev_r3'] == 4)

    # Rolling VT rate over last 50 spins (proxy for "low_mom")
    sdf['vt_roll50'] = sdf['is_vt'].rolling(50, min_periods=10).mean().shift(1).fillna(0)
    sdf['low_mom'] = sdf['vt_roll50'] < 0.04  # below baseline ~3%

    all_dfs.append(sdf)

df = pd.concat(all_dfs, ignore_index=True)
valid = df.groupby('source').cumcount() >= 5
df_v = df[valid].reset_index(drop=True)

y = df_v['is_vt'].astype(int)
y_acc = df_v['is_acc'].astype(int)
y_spn = df_v['is_spn'].astype(int)
N = len(df_v)
n_vt = int(y.sum())
n_acc = int(y_acc.sum())
n_spn = int(y_spn.sum())
base_rate = n_vt / N
base_acc = n_acc / N
base_spn = n_spn / N
print(f"\nDataset: {N} spins, {n_vt} VTs ({100*base_rate:.2f}%, 1 per {N//n_vt})")
print(f"  ACC: {n_acc} ({100*base_acc:.2f}%)")
print(f"  SPN: {n_spn} ({100*base_spn:.2f}%)")

# =====================================================================
#  Phase 3 features (literal — as r1_idx/r3_idx appear in CSV)
#  Then the swapped versions (post Phase 4 correction)
# =====================================================================
gap = df_v['gap']
gap_acc = df_v['gap_acc']
gap_spn = df_v['gap_spn']
prev_r1 = df_v['prev_r1'].fillna(-1)
prev_r2 = df_v['prev_r2'].fillna(-1)
prev_r3 = df_v['prev_r3'].fillna(-1)
prev_steal = df_v['prev_steal']
low_mom = df_v['low_mom']

# Literal features (using prev-spin indices)
sum_idx = prev_r1 + prev_r2 + prev_r3
all_diff = (prev_r1 != prev_r2) & (prev_r2 != prev_r3) & (prev_r1 != prev_r3)
r1_3or7 = (prev_r1 == 3) | (prev_r1 == 7)  # goldSack on r1
r3_3or7 = (prev_r3 == 3) | (prev_r3 == 7)  # goldSack on r3
r3_ge5 = prev_r3 >= 5
r1_ge5 = prev_r1 >= 5
r2_eq7 = prev_r2 == 7

# =====================================================================
#  Stat helpers
# =====================================================================

def fisher_p(hits, n, base):
    if n == 0 or hits == 0: return 1.0
    return 1 - binom.cdf(hits - 1, n, base)

def evaluate(name, mask, target_y, target_n, target_base, expected=None):
    tp = int((mask & (target_y == 1)).sum())
    total = int(mask.sum())
    if total == 0:
        print(f"  {name:<60}  NO HITS")
        return
    prec = tp / total * 100
    lift = (tp / total) / target_base if target_base > 0 else 0
    catch = tp / target_n * 100 if target_n > 0 else 0
    bph = total / tp if tp else 999
    pval = fisher_p(tp, total, target_base)
    marker = "***" if pval < 0.01 else ("**" if pval < 0.05 else "")
    line = f"  {name:<60}  prec={prec:5.1f}%  lift={lift:4.2f}x  catch={catch:5.1f}%  bph={bph:5.1f}  TP={tp:3d}/{total:4d}  p={pval:.4f} {marker}"
    if expected:
        line += f"   [Phase3 was: {expected}]"
    print(line)

# =====================================================================
#  PART A: ALL-VT strategies (literal interpretation)
# =====================================================================
print(f"\n{'='*100}")
print(f"PART A: ALL VTs — Phase 3 strategies as literally written (using r1_idx/r3_idx as in CSV)")
print(f"{'='*100}")

evaluate("R1: gap>=30 & low_mom & r1=3or7",
         (gap >= 30) & low_mom & r1_3or7, y, n_vt, base_rate,
         "13.3% prec, 4.2x, 23% catch, 7.5 bph")

evaluate("R2: gap>=30 & r3>=5 & all_diff & sum>=15",
         (gap >= 30) & r3_ge5 & all_diff & (sum_idx >= 15), y, n_vt, base_rate,
         "12.2% prec, 3.9x, 17% catch, 8.2 bph")

evaluate("R3: gap>=40 & r3>=5 & sum>=15",
         (gap >= 40) & r3_ge5 & (sum_idx >= 15), y, n_vt, base_rate,
         "10.4% prec, 3.3x, 23% catch, 9.6 bph")

evaluate("R4: gap>=30 & (r3>=5 | all_diff | sum>=15 | r2=7)  ** the 54% catch rule",
         (gap >= 30) & (r3_ge5 | all_diff | (sum_idx >= 15) | r2_eq7), y, n_vt, base_rate,
         "7.5% prec, 2.4x, 54% catch, 13.3 bph")

# =====================================================================
#  PART B: same rules with swapped interpretation
# =====================================================================
print(f"\n{'='*100}")
print(f"PART B: ALL VTs — corrected for one-strip swap (r1<->r3 in feature names)")
print(f"{'='*100}")

evaluate("R1-swap: gap>=30 & low_mom & r3=3or7 (was 'r1=goldSack')",
         (gap >= 30) & low_mom & r3_3or7, y, n_vt, base_rate,
         "13.3% prec, 4.2x, 23% catch, 7.5 bph")

evaluate("R2-swap: gap>=30 & r1>=5 & all_diff & sum>=15",
         (gap >= 30) & r1_ge5 & all_diff & (sum_idx >= 15), y, n_vt, base_rate,
         "12.2% prec, 3.9x, 17% catch, 8.2 bph")

evaluate("R3-swap: gap>=40 & r1>=5 & sum>=15",
         (gap >= 40) & r1_ge5 & (sum_idx >= 15), y, n_vt, base_rate,
         "10.4% prec, 3.3x, 23% catch, 9.6 bph")

evaluate("R4-swap: gap>=30 & (r1>=5 | all_diff | sum>=15 | r2=7)",
         (gap >= 30) & (r1_ge5 | all_diff | (sum_idx >= 15) | r2_eq7), y, n_vt, base_rate,
         "7.5% prec, 2.4x, 54% catch, 13.3 bph")

# =====================================================================
#  PART C: ACC-specific rules
# =====================================================================
print(f"\n{'='*100}")
print(f"PART C: ACC-only ({n_acc} targets, base {100*base_acc:.2f}%)")
print(f"{'='*100}")

evaluate("A1: gap_acc>=60 & prev_steal",
         (gap_acc >= 60) & prev_steal, y_acc, n_acc, base_acc,
         "22.2% prec, 14.5x, 12% catch, 4.5 bph")

evaluate("A2: gap>=30 & prev_steal",
         (gap >= 30) & prev_steal, y_acc, n_acc, base_acc,
         "14.3% prec, 9.3x, 18% catch, 7.0 bph")

evaluate("A3: gap>=30 & low_mom & r1=3or7  (literal)",
         (gap >= 30) & low_mom & r1_3or7, y_acc, n_acc, base_acc,
         "10.8% prec, 7.0x, 59% catch, 9.3 bph")

evaluate("A3-swap: gap>=30 & low_mom & r3=3or7",
         (gap >= 30) & low_mom & r3_3or7, y_acc, n_acc, base_acc,
         "(swap of A3)")

# =====================================================================
#  PART D: SPN-specific rules
# =====================================================================
print(f"\n{'='*100}")
print(f"PART D: SPN-only ({n_spn} targets, base {100*base_spn:.2f}%)")
print(f"{'='*100}")

evaluate("S1: gap>=40 & r3>=5 & all_diff  (literal)",
         (gap >= 40) & r3_ge5 & all_diff, y_spn, n_spn, base_spn,
         "6.5% prec, 4.0x, 22% catch, 15.5 bph")

evaluate("S1-swap: gap>=40 & r1>=5 & all_diff",
         (gap >= 40) & r1_ge5 & all_diff, y_spn, n_spn, base_spn,
         "(swap)")

evaluate("S2: gap_spn>=50 & r3>=5 & sum>=15  (literal)",
         (gap_spn >= 50) & r3_ge5 & (sum_idx >= 15), y_spn, n_spn, base_spn,
         "5.5% prec, 3.4x, 33% catch, 18.3 bph")

evaluate("S2-swap: gap_spn>=50 & r1>=5 & sum>=15",
         (gap_spn >= 50) & r1_ge5 & (sum_idx >= 15), y_spn, n_spn, base_spn,
         "(swap)")

evaluate("S3: gap>=40 & r3>=5 & sum>=15  (literal)",
         (gap >= 40) & r3_ge5 & (sum_idx >= 15), y_spn, n_spn, base_spn,
         "5.1% prec, 3.1x, 44% catch, 19.6 bph")

# =====================================================================
#  PART E: comparison vs Phase 6 sa_-counter rules on same dataset
# =====================================================================
print(f"\n{'='*100}")
print(f"PART E: Phase 6 sa_-counter benchmark rules (same dataset for direct comparison)")
print(f"{'='*100}")

sa_spn = df_v['sa_spn'].fillna(0) if 'sa_spn' in df_v.columns else pd.Series([0]*N)
sa_acc = df_v['sa_acc'].fillna(0) if 'sa_acc' in df_v.columns else pd.Series([0]*N)

evaluate("Phase6: sa_spn>=45",
         sa_spn >= 45, y, n_vt, base_rate)
evaluate("Phase6: gap>=35 & sa_spn>=45 (best single)",
         (gap >= 35) & (sa_spn >= 45), y, n_vt, base_rate)
evaluate("Phase6: gap>=50 & sa_spn>=45 (best precision)",
         (gap >= 50) & (sa_spn >= 45), y, n_vt, base_rate)
evaluate("Phase6: sa_spn>=45 OR sa_acc>=55",
         (sa_spn >= 45) | (sa_acc >= 55), y, n_vt, base_rate)

# =====================================================================
#  PART F: head-to-head — Phase 3 R4 vs Phase 6 best at matched bph
# =====================================================================
print(f"\n{'='*100}")
print(f"PART F: Head-to-head — Phase 3 ALL_OR (the 54% catch rule) vs Phase 6 best")
print(f"{'='*100}")

r4_lit = (gap >= 30) & (r3_ge5 | all_diff | (sum_idx >= 15) | r2_eq7)
r4_swap = (gap >= 30) & (r1_ge5 | all_diff | (sum_idx >= 15) | r2_eq7)

# Both versions — they're nearly identical because all_diff and sum_idx are symmetric
print(f"\n  Phase 3 R4 literal:")
evaluate("    gap>=30 & (r3>=5 | all_diff | sum>=15 | r2=7)",
         r4_lit, y, n_vt, base_rate)
print(f"\n  Phase 3 R4 swapped:")
evaluate("    gap>=30 & (r1>=5 | all_diff | sum>=15 | r2=7)",
         r4_swap, y, n_vt, base_rate)
print(f"\n  Phase 6 best at comparable bph:")
evaluate("    sa_spn>=45 OR sa_acc>=55  (10.3 bph in script 99)",
         (sa_spn >= 45) | (sa_acc >= 55), y, n_vt, base_rate)
evaluate("    gap>=35 & sa_spn>=45  (5.6 bph)",
         (gap >= 35) & (sa_spn >= 45), y, n_vt, base_rate)

# Pure baselines for sanity
print(f"\n  Pure baselines:")
evaluate("    gap>=30 alone", gap >= 30, y, n_vt, base_rate)
evaluate("    all_diff alone", all_diff, y, n_vt, base_rate)
evaluate("    sum>=15 alone", sum_idx >= 15, y, n_vt, base_rate)
evaluate("    r2=7 alone", r2_eq7, y, n_vt, base_rate)

print("\nDone.")
