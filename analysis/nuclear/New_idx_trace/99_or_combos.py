"""
99_or_combos.py — OR-based rules to maximize catch at <=10 bph
Key idea: AND rules are precise but miss VTs. OR unions catch more.

sa_spn>=45 alone = 9 TPs at 9.4 bph
gap>=35&spn>=45&acc>=45 = 8 TPs at 5.2 bph
These might catch DIFFERENT VTs — union could boost TP count.
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from scipy.stats import binom

ROOT = Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =====================================================================
#  Load data
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
    if not path.exists(): continue
    try:
        df = pd.read_csv(str(path), on_bad_lines='skip')
    except Exception as e:
        print(f"  {label}: ERROR {e}"); continue
    if 'r1_idx' not in df.columns: continue
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

    for c in ['sa_spins', 'sa_acc', 'sa_spn', 'sa_atk', 'sa_stl', 'sa_shd']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        else:
            df[c] = np.nan
    df['source'] = label
    frames.append(df)
    print(f"  {label}: {len(df)} spins, {df['is_vt'].sum()} VTs")

df_all = pd.concat(frames, ignore_index=True)

# Compute gap per source
all_dfs = []
for src in df_all['source'].unique():
    sdf = df_all[df_all['source'] == src].copy().reset_index(drop=True)
    g = 999
    gaps = []
    for i in range(len(sdf)):
        g += 1
        gaps.append(g)
        if sdf.loc[i, 'is_vt']:
            g = 0
    sdf['gap'] = gaps

    # Lag-1
    sdf['prev_r1'] = sdf['r1_idx'].shift(1)
    sdf['prev_r2'] = sdf['r2_idx'].shift(1)
    sdf['prev_r3'] = sdf['r3_idx'].shift(1)
    sdf['prev_was_triple'] = sdf['is_triple'].shift(1).fillna(False)

    # Running VT rate (last 100 spins)
    sdf['vt_roll100'] = sdf['is_vt'].rolling(100, min_periods=10).mean().shift(1).fillna(0)

    all_dfs.append(sdf)

df = pd.concat(all_dfs, ignore_index=True)
valid = df.groupby('source').cumcount() >= 5
df_v = df[valid].reset_index(drop=True)
y = df_v['is_vt'].astype(int)
N = len(df_v)
n_vt = y.sum()
base_rate = n_vt / N
print(f"\nDataset: {N} spins, {n_vt} VTs ({100*base_rate:.2f}%, 1 per {N//n_vt})")

gap = df_v['gap']
sa_spn = df_v['sa_spn'].fillna(0)
sa_acc = df_v['sa_acc'].fillna(0)
sa_spins = df_v['sa_spins'].fillna(0)


def fisher_p(hits, n, base):
    if n == 0 or hits == 0: return 1.0
    return 1 - binom.cdf(hits - 1, n, base)


def show(name, mask):
    tp = (mask & (y == 1)).sum()
    total = mask.sum()
    if total == 0: return
    prec = tp / total * 100
    catch = tp / n_vt * 100
    bph = total / tp if tp else 999
    pval = fisher_p(tp, total, base_rate)
    marker = " ***" if bph <= 10 and tp >= 5 else (" **" if bph <= 10 else "")
    print(f"  {name:>55} {prec:>7.1f} {catch:>7.1f} {bph:>7.1f} {tp:>4} {total:>5} {pval:>8.4f}{marker}")
    return tp, total, bph


# =====================================================================
#  PART 1: VT overlap analysis — which rules catch DIFFERENT VTs?
# =====================================================================
print(f"\n{'='*70}")
print("PART 1: VT OVERLAP — do rules catch different VTs?")
print(f"{'='*70}")

vt_indices = df_v[y == 1].index

rule_masks = {
    'sa_spn>=45': sa_spn >= 45,
    'sa_spn>=40': sa_spn >= 40,
    'sa_acc>=50': sa_acc >= 50,
    'sa_acc>=45': sa_acc >= 45,
    'gap>=40': gap >= 40,
    'gap>=50': gap >= 50,
    'gap>=30': gap >= 30,
    'gap>=40 & spn>=40': (gap >= 40) & (sa_spn >= 40),
    'gap>=40 & spn>=45': (gap >= 40) & (sa_spn >= 45),
    'gap>=35 & spn>=45 & acc>=45': (gap >= 35) & (sa_spn >= 45) & (sa_acc >= 45),
}

# Which VTs does each rule catch?
vt_caught_by = {}
for name, mask in rule_masks.items():
    caught = set(vt_indices[mask[vt_indices]].tolist())
    vt_caught_by[name] = caught

print(f"\n  {'Rule A':>35} {'Rule B':>35} | {'A_only':>7} {'Both':>5} {'B_only':>7} {'Union':>5}")
print(f"  {'-'*105}")
pairs = [
    ('sa_spn>=45', 'sa_acc>=50'),
    ('sa_spn>=45', 'gap>=50'),
    ('sa_spn>=45', 'gap>=40'),
    ('sa_spn>=45', 'sa_acc>=45'),
    ('sa_spn>=40', 'sa_acc>=45'),
    ('sa_spn>=40', 'gap>=40'),
    ('gap>=40 & spn>=45', 'sa_acc>=50'),
    ('gap>=40 & spn>=45', 'sa_acc>=45'),
    ('gap>=35 & spn>=45 & acc>=45', 'sa_spn>=45'),
    ('gap>=40 & spn>=40', 'sa_acc>=45'),
]
for a, b in pairs:
    ca = vt_caught_by[a]
    cb = vt_caught_by[b]
    a_only = len(ca - cb)
    both = len(ca & cb)
    b_only = len(cb - ca)
    union = len(ca | cb)
    print(f"  {a:>35} {b:>35} | {a_only:>7} {both:>5} {b_only:>7} {union:>5}")


# =====================================================================
#  PART 2: OR COMBINATIONS — union of rules
# =====================================================================
print(f"\n{'='*70}")
print("PART 2: OR COMBINATIONS — union of rules (targeting <=10 bph)")
print(f"{'='*70}")
print(f"\n  {'Rule':>55} {'Prec%':>7} {'Catch%':>7} {'BPH':>7} {'TP':>4} {'Bets':>5} {'p':>8}")

# Simple OR combos
or_rules = [
    # Two conditions OR'd
    ('sa_spn>=45 OR sa_acc>=54',
        (sa_spn >= 45) | (sa_acc >= 54)),
    ('sa_spn>=45 OR sa_acc>=50',
        (sa_spn >= 45) | (sa_acc >= 50)),
    ('sa_spn>=45 OR (gap>=50 & sa_acc>=50)',
        (sa_spn >= 45) | ((gap >= 50) & (sa_acc >= 50))),
    ('sa_spn>=45 OR (gap>=40 & sa_acc>=50)',
        (sa_spn >= 45) | ((gap >= 40) & (sa_acc >= 50))),
    ('(gap>=40&spn>=45) OR sa_acc>=54',
        ((gap >= 40) & (sa_spn >= 45)) | (sa_acc >= 54)),
    ('(gap>=40&spn>=45) OR (gap>=50&acc>=50)',
        ((gap >= 40) & (sa_spn >= 45)) | ((gap >= 50) & (sa_acc >= 50))),
    ('(gap>=40&spn>=45) OR (gap>=40&acc>=50)',
        ((gap >= 40) & (sa_spn >= 45)) | ((gap >= 40) & (sa_acc >= 50))),
    ('(gap>=40&spn>=40) OR (gap>=40&acc>=50)',
        ((gap >= 40) & (sa_spn >= 40)) | ((gap >= 40) & (sa_acc >= 50))),
    ('(gap>=30&spn>=45) OR (gap>=30&acc>=54)',
        ((gap >= 30) & (sa_spn >= 45)) | ((gap >= 30) & (sa_acc >= 54))),
    ('(gap>=30&spn>=45) OR (gap>=40&acc>=50)',
        ((gap >= 30) & (sa_spn >= 45)) | ((gap >= 40) & (sa_acc >= 50))),
    ('(gap>=30&spn>=45) OR (gap>=50&acc>=45)',
        ((gap >= 30) & (sa_spn >= 45)) | ((gap >= 50) & (sa_acc >= 45))),
    # Tiered: strong single OR moderate combo
    ('spn>=45 OR (gap>=50&acc>=45)',
        (sa_spn >= 45) | ((gap >= 50) & (sa_acc >= 45))),
    ('spn>=45 OR (gap>=40&acc>=45&spn>=35)',
        (sa_spn >= 45) | ((gap >= 40) & (sa_acc >= 45) & (sa_spn >= 35))),
    ('spn>=45 OR (gap>=50&spn>=35&acc>=45)',
        (sa_spn >= 45) | ((gap >= 50) & (sa_spn >= 35) & (sa_acc >= 45))),
    # Relax spn, add gap gating
    ('gap>=30&spn>=40 OR gap>=30&acc>=50',
        ((gap >= 30) & (sa_spn >= 40)) | ((gap >= 30) & (sa_acc >= 50))),
    ('gap>=30&spn>=40 OR gap>=40&acc>=45',
        ((gap >= 30) & (sa_spn >= 40)) | ((gap >= 40) & (sa_acc >= 45))),
    ('gap>=30&spn>=40 OR acc>=54',
        ((gap >= 30) & (sa_spn >= 40)) | (sa_acc >= 54)),
    ('gap>=35&spn>=40 OR gap>=35&acc>=50',
        ((gap >= 35) & (sa_spn >= 40)) | ((gap >= 35) & (sa_acc >= 50))),
    # Three-way OR
    ('spn>=45 OR acc>=54 OR (gap>=50&spn>=35)',
        (sa_spn >= 45) | (sa_acc >= 54) | ((gap >= 50) & (sa_spn >= 35))),
    ('spn>=45 OR acc>=54 OR (gap>=60&spn>=30)',
        (sa_spn >= 45) | (sa_acc >= 54) | ((gap >= 60) & (sa_spn >= 30))),
    ('(gap>=40&spn>=40) OR acc>=54 OR (gap>=60&acc>=45)',
        ((gap >= 40) & (sa_spn >= 40)) | (sa_acc >= 54) | ((gap >= 60) & (sa_acc >= 45))),
    ('(gap>=30&spn>=45) OR (gap>=30&acc>=54) OR (gap>=60&spn>=35)',
        ((gap >= 30) & (sa_spn >= 45)) | ((gap >= 30) & (sa_acc >= 54)) | ((gap >= 60) & (sa_spn >= 35))),
]

for name, mask in or_rules:
    show(name, mask)


# =====================================================================
#  PART 3: SYSTEMATIC OR SWEEP
# =====================================================================
print(f"\n{'='*70}")
print("PART 3: SYSTEMATIC OR SWEEP (gap+spn OR gap+acc)")
print(f"{'='*70}")

best_or = []

for g1 in range(25, 55, 5):
    for s1 in range(35, 55, 5):
        for g2 in range(25, 60, 5):
            for a2 in range(40, 60, 5):
                mask = ((gap >= g1) & (sa_spn >= s1)) | ((gap >= g2) & (sa_acc >= a2))
                tp = (mask & (y == 1)).sum()
                total = mask.sum()
                if tp >= 5 and total > 0:
                    bph = total / tp
                    if bph <= 10:
                        prec = tp / total
                        catch = tp / n_vt
                        pval = fisher_p(tp, total, base_rate)
                        best_or.append({
                            'name': f"(g>={g1}&spn>={s1}) OR (g>={g2}&acc>={a2})",
                            'tp': tp, 'total': total, 'prec': prec,
                            'catch': catch, 'bph': bph, 'pval': pval,
                        })

# Also try: single_spn OR single_acc
for s1 in range(40, 55, 5):
    for a2 in range(45, 60, 5):
        mask = (sa_spn >= s1) | (sa_acc >= a2)
        tp = (mask & (y == 1)).sum()
        total = mask.sum()
        if tp >= 5 and total > 0:
            bph = total / tp
            if bph <= 15:  # slightly relaxed for OR combos
                prec = tp / total
                catch = tp / n_vt
                pval = fisher_p(tp, total, base_rate)
                best_or.append({
                    'name': f"spn>={s1} OR acc>={a2}",
                    'tp': tp, 'total': total, 'prec': prec,
                    'catch': catch, 'bph': bph, 'pval': pval,
                })

# Gap-gated single OR
for g in range(25, 50, 5):
    for s1 in range(35, 50, 5):
        for a2 in range(40, 60, 5):
            mask = (gap >= g) & ((sa_spn >= s1) | (sa_acc >= a2))
            tp = (mask & (y == 1)).sum()
            total = mask.sum()
            if tp >= 5 and total > 0:
                bph = total / tp
                if bph <= 10:
                    prec = tp / total
                    catch = tp / n_vt
                    pval = fisher_p(tp, total, base_rate)
                    best_or.append({
                        'name': f"g>={g} & (spn>={s1} OR acc>={a2})",
                        'tp': tp, 'total': total, 'prec': prec,
                        'catch': catch, 'bph': bph, 'pval': pval,
                    })

# Sort by catch (descending), then bph (ascending)
best_or.sort(key=lambda x: (-x['catch'], x['bph']))

print(f"\nFound {len(best_or)} OR rules with <=10 bph and TP>=5")
print(f"\nTOP 30 by catch rate:")
print(f"  {'Rule':>55} {'Prec%':>7} {'Catch%':>7} {'BPH':>7} {'TP':>4} {'Bets':>5} {'p':>8}")
print(f"  {'-'*100}")
seen = set()
count = 0
for c in best_or:
    key = (c['tp'], c['total'])
    if key in seen: continue
    seen.add(key)
    marker = " ***" if c['bph'] <= 10 else ""
    print(f"  {c['name']:>55} {c['prec']*100:>7.1f} {c['catch']*100:>7.1f} "
          f"{c['bph']:>7.1f} {c['tp']:>4} {c['total']:>5} {c['pval']:>8.4f}{marker}")
    count += 1
    if count >= 30: break


# =====================================================================
#  PART 4: PARETO FRONT — best catch at each bph level
# =====================================================================
print(f"\n{'='*70}")
print("PART 4: PARETO FRONT — best catch at each bph bucket")
print(f"{'='*70}")

# Combine all tested rules (AND + OR)
all_rules = []

# AND rules
for g in range(25, 70, 5):
    for s in range(30, 55, 5):
        mask = (gap >= g) & (sa_spn >= s)
        tp = (mask & (y == 1)).sum()
        total = mask.sum()
        if tp >= 3 and total > 0:
            bph = total / tp
            all_rules.append({'name': f"g>={g}&spn>={s}", 'tp': tp, 'total': total,
                'bph': bph, 'catch': tp/n_vt, 'prec': tp/total,
                'pval': fisher_p(tp, total, base_rate)})

for g in range(25, 70, 5):
    for a in range(35, 60, 5):
        mask = (gap >= g) & (sa_acc >= a)
        tp = (mask & (y == 1)).sum()
        total = mask.sum()
        if tp >= 3 and total > 0:
            bph = total / tp
            all_rules.append({'name': f"g>={g}&acc>={a}", 'tp': tp, 'total': total,
                'bph': bph, 'catch': tp/n_vt, 'prec': tp/total,
                'pval': fisher_p(tp, total, base_rate)})

for g in range(25, 60, 5):
    for s in range(30, 50, 5):
        for a in range(30, 55, 5):
            mask = (gap >= g) & (sa_spn >= s) & (sa_acc >= a)
            tp = (mask & (y == 1)).sum()
            total = mask.sum()
            if tp >= 3 and total > 0:
                bph = total / tp
                all_rules.append({'name': f"g>={g}&spn>={s}&acc>={a}", 'tp': tp, 'total': total,
                    'bph': bph, 'catch': tp/n_vt, 'prec': tp/total,
                    'pval': fisher_p(tp, total, base_rate)})

# Single counter rules
for s in range(35, 55, 5):
    mask = sa_spn >= s
    tp = (mask & (y == 1)).sum()
    total = mask.sum()
    if tp >= 3 and total > 0:
        bph = total / tp
        all_rules.append({'name': f"spn>={s}", 'tp': tp, 'total': total,
            'bph': bph, 'catch': tp/n_vt, 'prec': tp/total,
            'pval': fisher_p(tp, total, base_rate)})

for a in range(40, 60, 5):
    mask = sa_acc >= a
    tp = (mask & (y == 1)).sum()
    total = mask.sum()
    if tp >= 3 and total > 0:
        bph = total / tp
        all_rules.append({'name': f"acc>={a}", 'tp': tp, 'total': total,
            'bph': bph, 'catch': tp/n_vt, 'prec': tp/total,
            'pval': fisher_p(tp, total, base_rate)})

# Add OR rules
all_rules.extend(best_or)

# Build pareto front
pareto = {}
for r in all_rules:
    bph_bucket = round(r['bph'])
    if bph_bucket not in pareto or r['catch'] > pareto[bph_bucket]['catch']:
        pareto[bph_bucket] = r

print(f"\n  {'BPH':>5} {'Rule':>55} {'Prec%':>7} {'Catch%':>7} {'TP':>4} {'Bets':>5} {'p':>8}")
print(f"  {'-'*95}")
for bph_b in sorted(pareto.keys()):
    if bph_b > 50: continue
    r = pareto[bph_b]
    marker = " ***" if bph_b <= 10 else ""
    print(f"  {r['bph']:>5.1f} {r['name']:>55} {r['prec']*100:>7.1f} {r['catch']*100:>7.1f} "
          f"{r['tp']:>4} {r['total']:>5} {r['pval']:>8.4f}{marker}")


# =====================================================================
#  PART 5: VT PROFILE — what do caught/missed VTs look like?
# =====================================================================
print(f"\n{'='*70}")
print("PART 5: VT PROFILE — what separates caught vs missed VTs?")
print(f"{'='*70}")

# Use best <=10 bph rule
best_rule_mask = (sa_spn >= 45) | ((gap >= 40) & (sa_acc >= 50))
caught_vts = df_v[(y == 1) & best_rule_mask]
missed_vts = df_v[(y == 1) & ~best_rule_mask]

print(f"\nUsing rule: spn>=45 OR (gap>=40 & acc>=50)")
print(f"Caught: {len(caught_vts)} VTs, Missed: {len(missed_vts)} VTs")

for col in ['gap', 'sa_spn', 'sa_acc', 'sa_spins']:
    cv = caught_vts[col].dropna()
    mv = missed_vts[col].dropna()
    if len(cv) > 0 and len(mv) > 0:
        print(f"\n  {col}:")
        print(f"    Caught VTs:  mean={cv.mean():.1f}, median={cv.median():.1f}, "
              f"min={cv.min():.0f}, max={cv.max():.0f}")
        print(f"    Missed VTs:  mean={mv.mean():.1f}, median={mv.median():.1f}, "
              f"min={mv.min():.0f}, max={mv.max():.0f}")

# What fraction of missed VTs have low gap AND low sa_?
print(f"\nMissed VTs breakdown:")
for g_thresh in [20, 30, 40]:
    low_gap = (missed_vts['gap'] < g_thresh).sum()
    print(f"  gap < {g_thresh}: {low_gap}/{len(missed_vts)} ({100*low_gap/len(missed_vts):.0f}%)")

for s_thresh in [30, 35, 40]:
    low_spn = (missed_vts['sa_spn'].fillna(0) < s_thresh).sum()
    print(f"  sa_spn < {s_thresh}: {low_spn}/{len(missed_vts)} ({100*low_spn/len(missed_vts):.0f}%)")

# sa_ availability
no_sa = missed_vts['sa_spn'].isna().sum()
print(f"  sa_spn = NaN (no data): {no_sa}/{len(missed_vts)} ({100*no_sa/len(missed_vts):.0f}%)")


# =====================================================================
#  PART 6: MAXIMUM THEORETICAL CATCH AT <=10 BPH
# =====================================================================
print(f"\n{'='*70}")
print("PART 6: THEORETICAL MAXIMUM — how good CAN we get?")
print(f"{'='*70}")

# For each VT, what's the best single indicator it has?
print(f"\nPer-VT best indicators (all {n_vt} VTs):")
vt_rows = df_v[y == 1].copy()
vt_rows['has_spn_45'] = vt_rows['sa_spn'].fillna(0) >= 45
vt_rows['has_spn_40'] = vt_rows['sa_spn'].fillna(0) >= 40
vt_rows['has_spn_35'] = vt_rows['sa_spn'].fillna(0) >= 35
vt_rows['has_acc_54'] = vt_rows['sa_acc'].fillna(0) >= 54
vt_rows['has_acc_50'] = vt_rows['sa_acc'].fillna(0) >= 50
vt_rows['has_acc_45'] = vt_rows['sa_acc'].fillna(0) >= 45
vt_rows['has_gap_50'] = vt_rows['gap'] >= 50
vt_rows['has_gap_40'] = vt_rows['gap'] >= 40
vt_rows['has_gap_30'] = vt_rows['gap'] >= 30
vt_rows['has_sa_data'] = vt_rows['sa_spn'].notna()

for col in ['has_spn_45', 'has_spn_40', 'has_spn_35', 'has_acc_54', 'has_acc_50',
            'has_acc_45', 'has_gap_50', 'has_gap_40', 'has_gap_30', 'has_sa_data']:
    ct = vt_rows[col].sum()
    print(f"  {col:>20}: {ct}/{n_vt} ({100*ct/n_vt:.1f}%)")

# How many VTs have gap>=30 AND (spn>=35 OR acc>=45)?
any_signal = (
    (vt_rows['gap'] >= 30) &
    ((vt_rows['sa_spn'].fillna(0) >= 35) | (vt_rows['sa_acc'].fillna(0) >= 45))
)
print(f"\n  gap>=30 & (spn>=35 | acc>=45): {any_signal.sum()}/{n_vt} ({100*any_signal.sum()/n_vt:.1f}%)")

# How many are unreachable (gap<20 OR no sa_ data)?
unreachable = (vt_rows['gap'] < 20) | (~vt_rows['has_sa_data'])
print(f"  Unreachable (gap<20 OR no sa_ data): {unreachable.sum()}/{n_vt} ({100*unreachable.sum()/n_vt:.1f}%)")

# Of VTs with sa_ data, what % have spn>=35 OR acc>=45?
with_sa = vt_rows[vt_rows['has_sa_data']]
has_signal = ((with_sa['sa_spn'] >= 35) | (with_sa['sa_acc'] >= 45))
print(f"  Of {len(with_sa)} VTs with sa_ data: {has_signal.sum()} have spn>=35 OR acc>=45 ({100*has_signal.sum()/len(with_sa):.1f}%)")

print("\nDone.")
