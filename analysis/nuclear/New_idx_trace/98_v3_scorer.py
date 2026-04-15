"""
98_v3_scorer.py — Build V3 scorer: gap + sa_ foundation + best idx patterns
Goal: <=10 bets/hit with maximum catch rate

Known signals (from scripts 95-96):
  - gap (pity timer): primary signal
  - sa_spn: strong signal (>=45 alone = ~9.4 bph)
  - sa_acc: moderate signal
  - idx patterns: near-zero incremental lift

Strategy: weighted scorer combining all, then threshold sweep.
"""
import csv, math, sys
import pandas as pd
import numpy as np
from collections import defaultdict
from pathlib import Path
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =====================================================================
#  Load ALL data with idx + sa_ columns
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
        print(f"  {label}: not found, skip")
        continue
    try:
        df = pd.read_csv(str(path), on_bad_lines='skip')
    except Exception as e:
        print(f"  {label}: ERROR {e}")
        continue
    if 'r1_idx' not in df.columns:
        print(f"  {label}: no r1_idx, skip")
        continue
    for c in ['r1_idx', 'r2_idx', 'r3_idx']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['r1_idx', 'r2_idx', 'r3_idx']).copy()
    df['r1_idx'] = df['r1_idx'].astype(int)
    df['r2_idx'] = df['r2_idx'].astype(int)
    df['r3_idx'] = df['r3_idx'].astype(int)
    # Filter out negative idx
    df = df[(df['r1_idx'] >= 0) & (df['r2_idx'] >= 0) & (df['r3_idx'] >= 0)].copy()

    df['is_triple'] = df['is_triple'].astype(str).str.strip().str.lower().isin(['true', '1'])

    # VT definition
    if 'is_valuable' in df.columns:
        df['is_vt'] = df['is_valuable'].astype(str).str.strip().str.lower().isin(['true', '1'])
    else:
        # Fallback: SPN triple or ACC triple (all idx==8)
        df['is_vt'] = False
        if 'spin_result' in df.columns:
            df['is_vt'] = df['is_triple'] & (df['spin_result'].astype(str).str.strip().str.lower() == 'spins')
        # ACC: all idx == 8
        acc_mask = df['is_triple'] & (df['r1_idx'] == 8) & (df['r2_idx'] == 8) & (df['r3_idx'] == 8)
        df['is_vt'] = df['is_vt'] | acc_mask

    # sa_ columns
    for c in ['sa_spins', 'sa_acc', 'sa_spn', 'sa_atk', 'sa_stl', 'sa_shd']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        else:
            df[c] = np.nan

    df['source'] = label
    frames.append(df)
    print(f"  {label}: {len(df)} spins, {df['is_vt'].sum()} VTs, "
          f"sa_spn avail: {df['sa_spn'].notna().sum()}")

df_all = pd.concat(frames, ignore_index=True)
print(f"\nTotal: {len(df_all)} spins, {df_all['is_vt'].sum()} VTs ({df_all['is_vt'].mean()*100:.2f}%)")
print(f"sa_spn available: {df_all['sa_spn'].notna().sum()} ({df_all['sa_spn'].notna().mean()*100:.1f}%)")
print(f"sa_acc available: {df_all['sa_acc'].notna().sum()} ({df_all['sa_acc'].notna().mean()*100:.1f}%)")

# =====================================================================
#  Feature engineering per source
# =====================================================================
all_dfs = []
for src in df_all['source'].unique():
    sdf = df_all[df_all['source'] == src].copy().reset_index(drop=True)
    n = len(sdf)

    # Gap (spins since last VT)
    g = 999
    gaps = []
    for i in range(n):
        g += 1
        gaps.append(g)
        if sdf.loc[i, 'is_vt']:
            g = 0
    sdf['gap'] = gaps

    # Lag-1 idx
    sdf['prev_r1'] = sdf['r1_idx'].shift(1)
    sdf['prev_r2'] = sdf['r2_idx'].shift(1)
    sdf['prev_r3'] = sdf['r3_idx'].shift(1)

    all_dfs.append(sdf)

df = pd.concat(all_dfs, ignore_index=True)

# Only use rows after warmup (5 spins per source)
valid = df.groupby('source').cumcount() >= 5
df_v = df[valid].reset_index(drop=True)
y = df_v['is_vt'].astype(int)

N = len(df_v)
n_vt = y.sum()
base_rate = n_vt / N
print(f"\nAnalysis set: {N} spins, {n_vt} VTs ({100*base_rate:.2f}%, 1 per {N//n_vt if n_vt else 0})")


# =====================================================================
#  Helper
# =====================================================================
def fisher_p(hits, n, base):
    if n == 0 or hits == 0: return 1.0
    return 1 - binom.cdf(hits - 1, n, base)

def eval_rule(name, mask, y, n_vt, base_rate):
    tp = (mask & (y == 1)).sum()
    total = mask.sum()
    prec = tp / total * 100 if total else 0
    catch = tp / n_vt * 100 if n_vt else 0
    bph = total / tp if tp else 999
    pval = fisher_p(tp, total, base_rate)
    return tp, total, prec, catch, bph, pval


# =====================================================================
#  PART 1: Baseline threshold rules (reference)
# =====================================================================
print(f"\n{'='*70}")
print("PART 1: BASELINE THRESHOLD RULES (reference)")
print(f"{'='*70}")

gap = df_v['gap']
sa_spn = df_v['sa_spn'].fillna(0)
sa_acc = df_v['sa_acc'].fillna(0)
sa_spins = df_v['sa_spins'].fillna(0)

print(f"\n{'Rule':>50} {'Prec%':>7} {'Catch%':>7} {'BPH':>7} {'TP':>5} {'Bets':>6} {'p':>8}")
baselines = [
    ('gap >= 30', gap >= 30),
    ('gap >= 40', gap >= 40),
    ('gap >= 50', gap >= 50),
    ('sa_spn >= 40', sa_spn >= 40),
    ('sa_spn >= 45', sa_spn >= 45),
    ('sa_spn >= 50', sa_spn >= 50),
    ('sa_acc >= 50', sa_acc >= 50),
    ('sa_acc >= 54', sa_acc >= 54),
    ('gap>=30 & sa_spn>=35', (gap >= 30) & (sa_spn >= 35)),
    ('gap>=30 & sa_spn>=40', (gap >= 30) & (sa_spn >= 40)),
    ('gap>=40 & sa_spn>=40', (gap >= 40) & (sa_spn >= 40)),
    ('gap>=40 & sa_spn>=45', (gap >= 40) & (sa_spn >= 45)),
    ('gap>=50 & sa_spn>=45', (gap >= 50) & (sa_spn >= 45)),
    ('gap>=30 & sa_acc>=45', (gap >= 30) & (sa_acc >= 45)),
    ('gap>=30 & (sa_spn>=35 | sa_acc>=45)',
        (gap >= 30) & ((sa_spn >= 35) | (sa_acc >= 45))),
]
for name, mask in baselines:
    tp, total, prec, catch, bph, pval = eval_rule(name, mask, y, n_vt, base_rate)
    marker = " ***" if bph <= 10 and tp >= 5 else ""
    print(f"{name:>50} {prec:>7.1f} {catch:>7.1f} {bph:>7.1f} {tp:>5} {total:>6} {pval:>8.4f}{marker}")


# =====================================================================
#  PART 2: V3 SCORER — weighted combination
# =====================================================================
print(f"\n{'='*70}")
print("PART 2: V3 SCORER DESIGN — weighted gap + sa_ + idx")
print(f"{'='*70}")


def v3_score(row):
    """
    V3 scorer: combines gap, sa_ counters, and best idx patterns.
    Returns a single score; higher = more likely VT.
    """
    s = 0.0
    g = row['gap']
    spn = row['sa_spn'] if not np.isnan(row.get('sa_spn', np.nan)) else 0
    acc = row['sa_acc'] if not np.isnan(row.get('sa_acc', np.nan)) else 0

    # === GAP COMPONENT (graduated, main driver) ===
    if g >= 60: s += 5
    elif g >= 50: s += 4
    elif g >= 40: s += 3
    elif g >= 30: s += 2
    elif g >= 20: s += 1

    # === SA_SPN COMPONENT ===
    if spn >= 50: s += 4
    elif spn >= 45: s += 3
    elif spn >= 40: s += 2
    elif spn >= 35: s += 1

    # === SA_ACC COMPONENT ===
    if acc >= 55: s += 3
    elif acc >= 50: s += 2
    elif acc >= 45: s += 1

    # === IDX COMPONENT (best V2 patterns, small tweaks) ===
    pr1 = row.get('prev_r1', np.nan)
    pr2 = row.get('prev_r2', np.nan)
    pr3 = row.get('prev_r3', np.nan)
    if not np.isnan(pr1) and not np.isnan(pr2) and not np.isnan(pr3):
        pr1, pr2, pr3 = int(pr1), int(pr2), int(pr3)
        # Best positive patterns from V2
        if pr2 == 7: s += 1        # r2=goldSack position
        if pr1 == 7 and pr2 == 7: s += 1  # pair bonus
        # Best negative patterns
        if pr3 == 1: s -= 1        # r3=coin

    return s


# Compute V3 scores
print("\nComputing V3 scores...")
scores = df_v.apply(v3_score, axis=1)
df_v = df_v.copy()
df_v['v3_score'] = scores

print(f"\nV3 score distribution:")
print(f"  {'Score':>6} {'Spins':>6} {'VTs':>4} {'Rate%':>7} {'Lift':>5}")
print(f"  {'-'*35}")
for sc in sorted(df_v['v3_score'].unique(), reverse=True):
    mask = df_v['v3_score'] == sc
    n_sc = mask.sum()
    h_sc = (mask & (y == 1)).sum()
    if n_sc >= 3 or h_sc > 0:
        rate = h_sc / n_sc * 100 if n_sc else 0
        lift = (h_sc / n_sc) / base_rate if n_sc and base_rate else 0
        print(f"  {sc:>6.0f} {n_sc:>6} {h_sc:>4} {rate:>7.2f} {lift:>5.1f}x")

print(f"\nV3 threshold sweep:")
print(f"  {'Thr':>6} {'Bets':>6} {'TP':>4} {'Miss':>4} {'Prec%':>7} {'Catch%':>7} {'BPH':>7} {'p':>8}")
print(f"  {'-'*60}")
for thresh in range(0, 16):
    mask = df_v['v3_score'] >= thresh
    tp, total, prec, catch, bph, pval = eval_rule(f">={thresh}", mask, y, n_vt, base_rate)
    missed = n_vt - tp
    marker = " ***" if bph <= 10 and tp >= 5 else ""
    if total > 0:
        print(f"  {thresh:>6} {total:>6} {tp:>4} {missed:>4} {prec:>7.2f} {catch:>7.1f} {bph:>7.1f} {pval:>8.4f}{marker}")


# =====================================================================
#  PART 3: SYSTEMATIC WEIGHT OPTIMIZATION
# =====================================================================
print(f"\n{'='*70}")
print("PART 3: WEIGHT OPTIMIZATION — find best weights for <=10 bph")
print(f"{'='*70}")


def scored_eval(gap_w, spn_w, acc_w, gap_breaks, spn_breaks, acc_breaks, thresh):
    """Evaluate a weighted scorer config."""
    scores = np.zeros(N)

    g = df_v['gap'].values
    spn = df_v['sa_spn'].fillna(0).values
    acc = df_v['sa_acc'].fillna(0).values

    for level, cutoff in enumerate(gap_breaks, 1):
        scores += (g >= cutoff) * gap_w

    for level, cutoff in enumerate(spn_breaks, 1):
        scores += (spn >= cutoff) * spn_w

    for level, cutoff in enumerate(acc_breaks, 1):
        scores += (acc >= cutoff) * acc_w

    mask = scores >= thresh
    tp = (mask & (y.values == 1)).sum()
    total = mask.sum()
    if tp < 3 or total == 0:
        return None
    prec = tp / total
    catch = tp / n_vt
    bph = total / tp
    return {'tp': tp, 'total': total, 'prec': prec, 'catch': catch, 'bph': bph}


# Sweep different weight configs
best_configs = []

gap_break_options = [
    [20, 30, 40, 50, 60],
    [25, 35, 45, 55],
    [30, 40, 50],
    [30, 45, 60],
]
spn_break_options = [
    [30, 35, 40, 45, 50],
    [35, 40, 45, 50],
    [35, 40, 45],
    [40, 45, 50],
]
acc_break_options = [
    [40, 45, 50, 55],
    [45, 50, 55],
    [45, 50],
    [50, 55],
]

print("\nSweeping weight/threshold combinations...")
n_tested = 0
for gap_breaks in gap_break_options:
    for spn_breaks in spn_break_options:
        for acc_breaks in acc_break_options:
            for gw in [1, 2]:
                for sw in [1, 2, 3]:
                    for aw in [1, 2]:
                        for thresh in range(3, 15):
                            n_tested += 1
                            res = scored_eval(gw, sw, aw, gap_breaks, spn_breaks, acc_breaks, thresh)
                            if res and res['bph'] <= 10 and res['tp'] >= 5:
                                best_configs.append({
                                    'gw': gw, 'sw': sw, 'aw': aw,
                                    'g_breaks': gap_breaks, 's_breaks': spn_breaks, 'a_breaks': acc_breaks,
                                    'thresh': thresh, **res,
                                })

print(f"Tested {n_tested} configs, {len(best_configs)} hit <=10 bph with TP>=5")

if best_configs:
    # Sort by: primary = catch rate (higher better), secondary = bph (lower better)
    # Show pareto front: best catch at each bph bucket
    best_configs.sort(key=lambda x: (-x['catch'], x['bph']))

    print(f"\nTOP 20 by catch rate (<=10 bph):")
    print(f"  {'BPH':>6} {'Prec%':>7} {'Catch%':>7} {'TP':>4} {'Bets':>5} | "
          f"{'gw':>3} {'sw':>3} {'aw':>3} {'thr':>4} | gap_breaks | spn_breaks | acc_breaks")
    print(f"  {'-'*110}")
    seen = set()
    count = 0
    for c in best_configs:
        key = (c['tp'], c['total'])
        if key in seen: continue
        seen.add(key)
        print(f"  {c['bph']:>6.1f} {c['prec']*100:>7.2f} {c['catch']*100:>7.1f} {c['tp']:>4} {c['total']:>5} | "
              f"{c['gw']:>3} {c['sw']:>3} {c['aw']:>3} {c['thresh']:>4} | "
              f"{c['g_breaks']} | {c['s_breaks']} | {c['a_breaks']}")
        count += 1
        if count >= 20: break

    # Best at each bph level
    print(f"\nPARETO FRONT (best catch at each bph level):")
    print(f"  {'BPH':>6} {'Prec%':>7} {'Catch%':>7} {'TP':>4} {'Bets':>5} | Config")
    print(f"  {'-'*80}")
    pareto = {}
    for c in best_configs:
        bph_bucket = round(c['bph'])
        if bph_bucket not in pareto or c['catch'] > pareto[bph_bucket]['catch']:
            pareto[bph_bucket] = c
    for bph_b in sorted(pareto.keys()):
        c = pareto[bph_b]
        print(f"  {c['bph']:>6.1f} {c['prec']*100:>7.2f} {c['catch']*100:>7.1f} {c['tp']:>4} {c['total']:>5} | "
              f"gw={c['gw']},sw={c['sw']},aw={c['aw']},thr={c['thresh']} "
              f"g={c['g_breaks']} s={c['s_breaks']} a={c['a_breaks']}")


# =====================================================================
#  PART 4: BUILD BEST V3 SCORER + compare to simple rules
# =====================================================================
print(f"\n{'='*70}")
print("PART 4: BEST V3 vs SIMPLE THRESHOLD RULES")
print(f"{'='*70}")

if best_configs:
    # Pick the config with highest catch at <=10 bph
    best = max(best_configs, key=lambda x: (x['catch'], -x['bph']))
    print(f"\nBest V3 config: gw={best['gw']}, sw={best['sw']}, aw={best['aw']}, "
          f"thresh={best['thresh']}")
    print(f"  gap breaks: {best['g_breaks']}")
    print(f"  spn breaks: {best['s_breaks']}")
    print(f"  acc breaks: {best['a_breaks']}")
    print(f"  -> BPH={best['bph']:.1f}, Prec={best['prec']*100:.2f}%, "
          f"Catch={best['catch']*100:.1f}%, TP={best['tp']}, Bets={best['total']}")

# Build final V3 scorer based on best config and evaluate at multiple thresholds
print(f"\nFull threshold sweep with best weights:")
if best_configs:
    bc = best
    g_vals = df_v['gap'].values
    spn_vals = df_v['sa_spn'].fillna(0).values
    acc_vals = df_v['sa_acc'].fillna(0).values

    final_scores = np.zeros(N)
    for cutoff in bc['g_breaks']:
        final_scores += (g_vals >= cutoff) * bc['gw']
    for cutoff in bc['s_breaks']:
        final_scores += (spn_vals >= cutoff) * bc['sw']
    for cutoff in bc['a_breaks']:
        final_scores += (acc_vals >= cutoff) * bc['aw']

    print(f"\n  {'Thr':>6} {'Bets':>6} {'TP':>4} {'Prec%':>7} {'Catch%':>7} {'BPH':>7} {'p':>8}")
    print(f"  {'-'*55}")
    for thresh in range(1, 20):
        mask = final_scores >= thresh
        tp = (mask & (y.values == 1)).sum()
        total = mask.sum()
        if total == 0: continue
        prec = tp / total * 100
        catch = tp / n_vt * 100
        bph = total / tp if tp else 999
        pval = fisher_p(tp, total, base_rate)
        marker = " ***" if bph <= 10 and tp >= 5 else ""
        print(f"  {thresh:>6} {total:>6} {tp:>4} {prec:>7.2f} {catch:>7.1f} {bph:>7.1f} {pval:>8.4f}{marker}")


# =====================================================================
#  PART 5: HEAD-TO-HEAD — V3 vs pure threshold rules
# =====================================================================
print(f"\n{'='*70}")
print("PART 5: DIRECT COMPARISON — which approach wins?")
print(f"{'='*70}")

# For each bph bucket (2-10), find best pure rule and best V3 config
print(f"\n  {'BPH target':>12} | {'Best pure rule':>40} {'Prec%':>7} {'Catch%':>7} {'TP':>4} | "
      f"{'Best V3':>7} {'Catch%':>7} {'TP':>4}")
print(f"  {'-'*105}")

for bph_target in [3, 4, 5, 6, 7, 8, 9, 10]:
    # Best pure rule at this bph level
    best_pure = None
    pure_rules_sweep = []
    for g_t in range(20, 70, 5):
        for spn_t in range(30, 55, 5):
            mask = (gap >= g_t) & (sa_spn >= spn_t)
            tp = (mask & (y == 1)).sum()
            total = mask.sum()
            if tp >= 3 and total > 0:
                bph = total / tp
                if bph <= bph_target:
                    catch = tp / n_vt
                    prec = tp / total
                    pure_rules_sweep.append({
                        'name': f"gap>={g_t} & spn>={spn_t}",
                        'tp': tp, 'total': total, 'prec': prec,
                        'catch': catch, 'bph': bph
                    })
    # Also try sa_acc combos
    for g_t in range(20, 70, 5):
        for acc_t in range(40, 60, 5):
            mask = (gap >= g_t) & (sa_acc >= acc_t)
            tp = (mask & (y == 1)).sum()
            total = mask.sum()
            if tp >= 3 and total > 0:
                bph = total / tp
                if bph <= bph_target:
                    catch = tp / n_vt
                    prec = tp / total
                    pure_rules_sweep.append({
                        'name': f"gap>={g_t} & acc>={acc_t}",
                        'tp': tp, 'total': total, 'prec': prec,
                        'catch': catch, 'bph': bph
                    })
    # Triple combos
    for g_t in range(20, 60, 5):
        for spn_t in range(25, 50, 5):
            for acc_t in range(25, 55, 5):
                mask = (gap >= g_t) & (sa_spn >= spn_t) & (sa_acc >= acc_t)
                tp = (mask & (y == 1)).sum()
                total = mask.sum()
                if tp >= 3 and total > 0:
                    bph = total / tp
                    if bph <= bph_target:
                        catch = tp / n_vt
                        prec = tp / total
                        pure_rules_sweep.append({
                            'name': f"g>={g_t}&spn>={spn_t}&acc>={acc_t}",
                            'tp': tp, 'total': total, 'prec': prec,
                            'catch': catch, 'bph': bph
                        })

    if pure_rules_sweep:
        best_pure = max(pure_rules_sweep, key=lambda x: (x['catch'], -x['bph']))

    # Best V3 at this bph level
    best_v3 = None
    v3_at_bph = [c for c in best_configs if c['bph'] <= bph_target] if best_configs else []
    if v3_at_bph:
        best_v3 = max(v3_at_bph, key=lambda x: (x['catch'], -x['bph']))

    pure_str = f"{best_pure['name']:>40} {best_pure['prec']*100:>7.2f} {best_pure['catch']*100:>7.1f} {best_pure['tp']:>4}" if best_pure else f"{'(none)':>40} {'':>7} {'':>7} {'':>4}"
    v3_str = f"{best_v3['bph']:>7.1f} {best_v3['catch']*100:>7.1f} {best_v3['tp']:>4}" if best_v3 else f"{'(none)':>7} {'':>7} {'':>4}"

    print(f"  {'<= '+str(bph_target):>12} | {pure_str} | {v3_str}")


# =====================================================================
#  PART 6: Does adding idx improve V3?
# =====================================================================
print(f"\n{'='*70}")
print("PART 6: V3 + IDX PATTERNS — does idx help?")
print(f"{'='*70}")

if best_configs:
    bc = best
    g_vals = df_v['gap'].values
    spn_vals = df_v['sa_spn'].fillna(0).values
    acc_vals = df_v['sa_acc'].fillna(0).values
    pr1 = df_v['prev_r1'].fillna(-1).astype(int).values
    pr2 = df_v['prev_r2'].fillna(-1).astype(int).values
    pr3 = df_v['prev_r3'].fillna(-1).astype(int).values

    base_scores = np.zeros(N)
    for cutoff in bc['g_breaks']:
        base_scores += (g_vals >= cutoff) * bc['gw']
    for cutoff in bc['s_breaks']:
        base_scores += (spn_vals >= cutoff) * bc['sw']
    for cutoff in bc['a_breaks']:
        base_scores += (acc_vals >= cutoff) * bc['aw']

    # Test individual idx adjustments
    idx_tests = [
        ("prev_r2==7 (+1)", lambda: (pr2 == 7).astype(float)),
        ("prev_r2==3 (+1)", lambda: (pr2 == 3).astype(float)),
        ("prev_r1==7 & prev_r2==7 (+1)", lambda: ((pr1 == 7) & (pr2 == 7)).astype(float)),
        ("prev_r3==1 (-1)", lambda: -(pr3 == 1).astype(float)),
        ("prev_r1==1 (-1)", lambda: -(pr1 == 1).astype(float)),
        ("prev_sum>=15 (+1)", lambda: ((pr1+pr2+pr3) >= 15).astype(float) * (pr1 >= 0)),
        ("prev_all_same (-1)", lambda: -((pr1==pr2) & (pr2==pr3) & (pr1>=0)).astype(float)),
        ("prev_showed_gold (+1)", lambda: (
            ((pr2==3)|(pr2==7)).astype(float) * (pr2 >= 0)
        )),
    ]

    print(f"\nAdding idx adjustment to V3 base (thresh={bc['thresh']}):")
    print(f"  {'Pattern':>35} {'BPH':>7} {'Prec%':>7} {'Catch%':>7} {'TP':>4} {'Bets':>5} {'Delta':>7}")
    print(f"  {'-'*80}")

    # Base performance
    base_mask = base_scores >= bc['thresh']
    base_tp = (base_mask & (y.values == 1)).sum()
    base_total = base_mask.sum()
    base_bph = base_total / base_tp if base_tp else 999
    base_catch = base_tp / n_vt
    print(f"  {'V3 BASE':>35} {base_bph:>7.1f} {base_tp/base_total*100 if base_total else 0:>7.2f} "
          f"{base_catch*100:>7.1f} {base_tp:>4} {base_total:>5} {'':>7}")

    for name, adj_fn in idx_tests:
        adj = adj_fn()
        new_scores = base_scores + adj
        mask = new_scores >= bc['thresh']
        tp = (mask & (y.values == 1)).sum()
        total = mask.sum()
        if total == 0: continue
        bph = total / tp if tp else 999
        catch = tp / n_vt
        delta_bph = bph - base_bph
        print(f"  {name:>35} {bph:>7.1f} {tp/total*100:>7.2f} {catch*100:>7.1f} "
              f"{tp:>4} {total:>5} {delta_bph:>+7.1f}")

print("\nDone.")
