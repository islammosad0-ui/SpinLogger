"""
Script 96: Isolated ML tests — what adds signal beyond gap?
TEST 1: gap + sa_ only (no idx, no accum)
TEST 2: gap + sa_ + idx (no accum)
TEST 3: pure idx only
TEST 4: simple threshold rules
"""
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_predict, StratifiedKFold

files = [
    ('c:/Users/Islam Nawwar/SpinLogger/data/Ahmed/spin_history_Ahmed_enriched_v2.csv', 'Ahmed_v2'),
    ('c:/Users/Islam Nawwar/SpinLogger/data/Ahmed/spin_history_Ahmed_2026-04-13.csv', 'Ahmed_0413'),
    ('c:/Users/Islam Nawwar/SpinLogger/data/Ahmed/spin_history_Ahmed_2026-04-14.csv', 'Ahmed_0414'),
    ('c:/Users/Islam Nawwar/SpinLogger/data/Islam/spin_history_Islam_2026-04-13.csv', 'Islam'),
    ('c:/Users/Islam Nawwar/SpinLogger/data/Nick/spin_history_Nick_2026-04-13.csv', 'Nick'),
]

frames = []
for path, label in files:
    try:
        df = pd.read_csv(path, on_bad_lines='skip')
        if 'r1_idx' in df.columns:
            df['source'] = label
            frames.append(df)
            print(f'{label}: {len(df)} rows')
    except Exception as e:
        print(f'{label}: ERROR {e}')

df_all = pd.concat(frames, ignore_index=True)
for c in ['r1_idx', 'r2_idx', 'r3_idx']:
    df_all[c] = pd.to_numeric(df_all[c], errors='coerce')
df_all = df_all.dropna(subset=['r1_idx', 'r2_idx', 'r3_idx']).copy()
df_all['r1_idx'] = df_all['r1_idx'].astype(int)
df_all['r2_idx'] = df_all['r2_idx'].astype(int)
df_all['r3_idx'] = df_all['r3_idx'].astype(int)
df_all['is_triple'] = df_all['is_triple'].astype(str).str.lower().isin(['true', '1'])
df_all['is_valuable'] = df_all['is_valuable'].astype(str).str.lower().isin(['true', '1'])

print(f"\nTotal: {len(df_all)} spins, {df_all['is_valuable'].sum()} VTs ({df_all['is_valuable'].mean()*100:.2f}%)")

# Feature engineering per source
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
        if sdf.loc[i, 'is_valuable']:
            g = 0
    sdf['gap'] = gaps

    # Lag-1 through lag-3
    for lag in range(1, 4):
        sdf[f'prev{lag}_r1'] = sdf['r1_idx'].shift(lag)
        sdf[f'prev{lag}_r2'] = sdf['r2_idx'].shift(lag)
        sdf[f'prev{lag}_r3'] = sdf['r3_idx'].shift(lag)
        sdf[f'prev{lag}_sum'] = sdf[f'prev{lag}_r1'] + sdf[f'prev{lag}_r2'] + sdf[f'prev{lag}_r3']
        cols3 = [f'prev{lag}_r1', f'prev{lag}_r2', f'prev{lag}_r3']
        sdf[f'prev{lag}_spread'] = sdf[cols3].max(axis=1) - sdf[cols3].min(axis=1)
        sdf[f'prev{lag}_all_same'] = (
            (sdf[f'prev{lag}_r1'] == sdf[f'prev{lag}_r2']) &
            (sdf[f'prev{lag}_r2'] == sdf[f'prev{lag}_r3'])
        ).astype(int)

    # Cross-reel
    sdf['prev_r1r2_diff'] = sdf['r1_idx'].shift(1) - sdf['r2_idx'].shift(1)
    sdf['prev_r1r3_diff'] = sdf['r1_idx'].shift(1) - sdf['r3_idx'].shift(1)
    sdf['prev_sum_mod9'] = (sdf['r1_idx'].shift(1) + sdf['r2_idx'].shift(1) + sdf['r3_idx'].shift(1)) % 9

    # Rolling stats
    for w in [5, 10]:
        for c in ['r1_idx', 'r2_idx', 'r3_idx']:
            shifted = sdf[c].shift(1)
            sdf[f'{c}_roll{w}_mean'] = shifted.rolling(w, min_periods=1).mean()
            sdf[f'{c}_roll{w}_std'] = shifted.rolling(w, min_periods=1).std().fillna(0)

    # sa_ counters
    for c in ['sa_spins', 'sa_acc', 'sa_spn', 'sa_atk', 'sa_stl', 'sa_shd']:
        if c in sdf.columns:
            sdf[c] = pd.to_numeric(sdf[c], errors='coerce')

    # accum state
    for c in ['accum_current', 'accum_delta', 'accum_pct', 'accum_total']:
        if c in sdf.columns:
            sdf[c] = pd.to_numeric(sdf[c], errors='coerce')

    all_dfs.append(sdf)

df = pd.concat(all_dfs, ignore_index=True)
vt_mask = df['is_valuable']
valid = df.groupby('source').cumcount() >= 5
y = vt_mask[valid].astype(int).reset_index(drop=True)
df_v = df[valid].reset_index(drop=True)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
print(f"\nML dataset: {len(df_v)} samples, {y.sum()} VTs ({y.mean()*100:.2f}%)")


def run_test(name, feature_cols):
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")
    X = df_v[feature_cols].fillna(0).reset_index(drop=True)
    gbt = GradientBoostingClassifier(
        n_estimators=200, max_depth=3, min_samples_leaf=15, random_state=42
    )
    yp = cross_val_predict(gbt, X, y, cv=cv, method='predict_proba')[:, 1]

    print(f"Features ({len(feature_cols)}): {feature_cols}")
    print(f"{'Thr':>10} {'Prec%':>8} {'Catch%':>8} {'BPH':>8} {'TP':>5} {'Bets':>6}")
    for t in [0.02, 0.03, 0.04, 0.05, 0.08, 0.10, 0.15, 0.20]:
        pred = (yp >= t).astype(int)
        tp = ((pred == 1) & (y == 1)).sum()
        total = pred.sum()
        prec = tp / total * 100 if total else 0
        catch = tp / y.sum() * 100 if y.sum() else 0
        bph = total / tp if tp else 999
        print(f"{t:>10.2f} {prec:>8.1f} {catch:>8.1f} {bph:>8.1f} {tp:>5} {total:>6}")

    gbt.fit(X, y)
    imp = pd.Series(gbt.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print(f"\nFeature importance:")
    for f, v in imp.head(10).items():
        print(f"  {f:30s} {v:.4f}")


# TEST 1: gap + sa_ only
sa_cols = [c for c in ['sa_spins', 'sa_acc', 'sa_spn'] if c in df_v.columns]
run_test("TEST 1: gap + sa_ counters ONLY", ['gap'] + sa_cols)

# TEST 2: gap + sa_ + lag-1 idx
idx_cols = ['prev1_r1', 'prev1_r2', 'prev1_r3', 'prev1_sum', 'prev1_spread', 'prev1_all_same']
run_test("TEST 2: gap + sa_ + lag-1 idx", ['gap'] + sa_cols + idx_cols)

# TEST 3: gap + sa_ + ALL idx (lag 1-3, rolling, cross-reel)
all_idx = [c for c in df_v.columns if c.startswith('prev') and 'accum' not in c]
all_idx += [c for c in df_v.columns if 'roll' in c]
all_idx += ['prev_r1r2_diff', 'prev_r1r3_diff', 'prev_sum_mod9']
all_idx = [c for c in all_idx if c in df_v.columns]
run_test("TEST 3: gap + sa_ + ALL idx features", ['gap'] + sa_cols + all_idx)

# TEST 4: pure idx only (no gap, no sa_)
run_test("TEST 4: PURE idx ONLY (no gap, no sa_)", all_idx)

# TEST 5: gap + sa_ + accum (the full model without idx)
accum_cols = [c for c in ['accum_current', 'accum_delta', 'accum_pct', 'accum_total'] if c in df_v.columns]
run_test("TEST 5: gap + sa_ + accum (no idx)", ['gap'] + sa_cols + accum_cols)

# ===== SIMPLE THRESHOLD RULES =====
print(f"\n{'='*60}")
print("SIMPLE THRESHOLD RULES")
print(f"{'='*60}")

sa_spn = pd.to_numeric(df_v.get('sa_spn', pd.Series(dtype=float)), errors='coerce').fillna(0)
sa_acc = pd.to_numeric(df_v.get('sa_acc', pd.Series(dtype=float)), errors='coerce').fillna(0)
gap = df_v['gap']

rules = [
    ('gap >= 30', gap >= 30),
    ('gap >= 40', gap >= 40),
    ('gap >= 50', gap >= 50),
    ('sa_spn >= 40', sa_spn >= 40),
    ('sa_spn >= 45', sa_spn >= 45),
    ('sa_acc >= 50', sa_acc >= 50),
    ('sa_acc >= 54', sa_acc >= 54),
    ('gap>=40 AND sa_spn>=30', (gap >= 40) & (sa_spn >= 30)),
    ('gap>=40 AND sa_acc>=40', (gap >= 40) & (sa_acc >= 40)),
    ('gap>=30 AND sa_spn>=35', (gap >= 30) & (sa_spn >= 35)),
    ('gap>=30 AND sa_acc>=45', (gap >= 30) & (sa_acc >= 45)),
    ('sa_spn>=40 AND sa_acc>=40', (sa_spn >= 40) & (sa_acc >= 40)),
    ('sa_spn>=45 OR sa_acc>=54', (sa_spn >= 45) | (sa_acc >= 54)),
    ('gap>=30 AND (sa_spn>=35 OR sa_acc>=45)', (gap >= 30) & ((sa_spn >= 35) | (sa_acc >= 45))),
    ('gap>=25 AND sa_spn>=30 AND sa_acc>=30', (gap >= 25) & (sa_spn >= 30) & (sa_acc >= 30)),
]

print(f"{'Rule':>45} {'Prec%':>8} {'Catch%':>8} {'BPH':>8} {'TP':>5} {'Bets':>6}")
for name, mask in rules:
    tp = (mask & (y == 1)).sum()
    total = mask.sum()
    prec = tp / total * 100 if total else 0
    catch = tp / y.sum() * 100 if y.sum() else 0
    bph = total / tp if tp else 999
    print(f"{name:>45} {prec:>8.1f} {catch:>8.1f} {bph:>8.1f} {tp:>5} {total:>6}")

# Fine-grained combo sweep for <=10 bph targets
print(f"\n{'='*60}")
print("COMBO SWEEP: gap + sa_spn + sa_acc (targeting <=10 bph)")
print(f"{'='*60}")

best = []
for g_thresh in range(20, 80, 5):
    for spn_thresh in range(20, 60, 5):
        for acc_thresh in range(20, 70, 5):
            mask = (gap >= g_thresh) & (sa_spn >= spn_thresh) & (sa_acc >= acc_thresh)
            tp = (mask & (y == 1)).sum()
            total = mask.sum()
            if tp >= 3 and total > 0:
                prec = tp / total * 100
                catch = tp / y.sum() * 100
                bph = total / tp
                if bph <= 15:
                    best.append((bph, prec, catch, tp, total,
                                 f"gap>={g_thresh} & sa_spn>={spn_thresh} & sa_acc>={acc_thresh}"))

best.sort()
print(f"{'Rule':>55} {'Prec%':>8} {'Catch%':>8} {'BPH':>8} {'TP':>5} {'Bets':>6}")
for bph, prec, catch, tp, total, name in best[:20]:
    print(f"{name:>55} {prec:>8.1f} {catch:>8.1f} {bph:>8.1f} {tp:>5} {total:>6}")

if not best:
    print("  No combos found with bph <= 15 and tp >= 3")

print("\nDone.")
