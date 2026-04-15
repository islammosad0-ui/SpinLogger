"""
Script 95: ML deep analysis + exhaustive statistical angles
- Gradient Boosted Tree with cross-validation
- Feature importance ranking
- Symbol frequency windows
- Accumulation game-state variables
- Cross-reel idx relationships
- Entropy of recent sequences
"""
import pandas as pd
import numpy as np
from collections import Counter
import sys, os

# Load all data with idx
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
        if 'spin_result' not in df.columns and 'sym1' in df.columns:
            df['spin_result'] = df['sym1']
            df['is_triple'] = (df['sym1'] == df['sym2']) & (df['sym2'] == df['sym3'])
        if 'r1_idx' in df.columns:
            df['source'] = label
            frames.append(df)
            print(f'{label}: {len(df)} rows')
    except Exception as e:
        print(f'{label}: ERROR {e}')

df_all = pd.concat(frames, ignore_index=True)
for c in ['r1_idx','r2_idx','r3_idx']:
    df_all[c] = pd.to_numeric(df_all[c], errors='coerce')
df_all = df_all.dropna(subset=['r1_idx','r2_idx','r3_idx']).copy()
df_all['r1_idx'] = df_all['r1_idx'].astype(int)
df_all['r2_idx'] = df_all['r2_idx'].astype(int)
df_all['r3_idx'] = df_all['r3_idx'].astype(int)
df_all['is_triple'] = df_all['is_triple'].astype(str).str.lower().isin(['true','1'])

# Fix VT identification: use is_valuable if available, else gold+spins triples
if 'is_valuable' in df_all.columns:
    df_all['is_valuable'] = df_all['is_valuable'].astype(str).str.lower().isin(['true','1'])
    vt_all = df_all['is_valuable']
else:
    vt_all = df_all['is_triple'] & df_all['spin_result'].isin(['gold','spins'])

# For ACC/SPN split: ACC = valuable gold triple, SPN = valuable spins triple
acc_all = vt_all & (df_all['spin_result'] == 'gold')
spn_all = vt_all & (df_all['spin_result'] == 'spins')
print(f'\nCombined: {len(df_all)} spins, {vt_all.sum()} VTs')
print(f'  ACC (gold VTs): {acc_all.sum()}')
print(f'  SPN: {spn_all.sum()}')

# ===================================================================
# Feature engineering per source
# ===================================================================
strip = ['attack','coin','shield','goldSack','steal','coin','spins','goldSack','accumulation']

all_features = []
for src in df_all['source'].unique():
    sdf = df_all[df_all['source'] == src].copy().reset_index(drop=True)
    n = len(sdf)

    # --- Gap tracking ---
    g, ga, gs = 999, 999, 999
    gaps, gaps_a, gaps_s = [], [], []
    for i in range(n):
        g += 1; ga += 1; gs += 1
        gaps.append(g); gaps_a.append(ga); gaps_s.append(gs)
        is_vt = sdf.loc[i, 'is_triple'] and sdf.loc[i, 'spin_result'] in ['accumulation','spins']
        if is_vt: g = 0
        if sdf.loc[i, 'is_triple'] and sdf.loc[i, 'spin_result'] == 'accumulation': ga = 0
        if sdf.loc[i, 'is_triple'] and sdf.loc[i, 'spin_result'] == 'spins': gs = 0
    sdf['gap'] = gaps
    sdf['gap_acc'] = gaps_a
    sdf['gap_spn'] = gaps_s

    # --- Lag features (1-5) ---
    for lag in range(1, 6):
        sdf[f'prev{lag}_r1'] = sdf['r1_idx'].shift(lag)
        sdf[f'prev{lag}_r2'] = sdf['r2_idx'].shift(lag)
        sdf[f'prev{lag}_r3'] = sdf['r3_idx'].shift(lag)
        sdf[f'prev{lag}_sum'] = sdf[f'prev{lag}_r1'] + sdf[f'prev{lag}_r2'] + sdf[f'prev{lag}_r3']
        cols3 = [f'prev{lag}_r1', f'prev{lag}_r2', f'prev{lag}_r3']
        sdf[f'prev{lag}_spread'] = sdf[cols3].max(axis=1) - sdf[cols3].min(axis=1)
        sdf[f'prev{lag}_all_same'] = ((sdf[f'prev{lag}_r1'] == sdf[f'prev{lag}_r2']) &
                                       (sdf[f'prev{lag}_r2'] == sdf[f'prev{lag}_r3'])).astype(int)

    # --- Rolling window stats (lag-1 shifted, windows 3/5/10) ---
    for w in [3, 5, 10]:
        for c in ['r1_idx', 'r2_idx', 'r3_idx']:
            shifted = sdf[c].shift(1)
            sdf[f'{c}_roll{w}_mean'] = shifted.rolling(w, min_periods=1).mean()
            sdf[f'{c}_roll{w}_std'] = shifted.rolling(w, min_periods=1).std().fillna(0)
        total = sdf['r1_idx'].shift(1) + sdf['r2_idx'].shift(1) + sdf['r3_idx'].shift(1)
        sdf[f'sum_roll{w}_mean'] = total.rolling(w, min_periods=1).mean()

    # --- Cross-reel relationships (lag-1) ---
    sdf['prev_r1r2_diff'] = sdf['r1_idx'].shift(1) - sdf['r2_idx'].shift(1)
    sdf['prev_r2r3_diff'] = sdf['r2_idx'].shift(1) - sdf['r3_idx'].shift(1)
    sdf['prev_r1r3_diff'] = sdf['r1_idx'].shift(1) - sdf['r3_idx'].shift(1)
    sdf['prev_r1r2_xor'] = sdf['r1_idx'].shift(1).fillna(0).astype(int) ^ sdf['r2_idx'].shift(1).fillna(0).astype(int)
    sdf['prev_sum_mod9'] = (sdf['r1_idx'].shift(1) + sdf['r2_idx'].shift(1) + sdf['r3_idx'].shift(1)) % 9
    sdf['prev_sum_mod5'] = (sdf['r1_idx'].shift(1) + sdf['r2_idx'].shift(1) + sdf['r3_idx'].shift(1)) % 5

    # --- Symbol frequency in last N spins (corrected strip mapping) ---
    for window in [5, 10]:
        for sym_name, sym_idxs in [('acc', [8]), ('spn', [6]), ('gold', [3,7]), ('steal', [4])]:
            counts = np.zeros(n)
            for i in range(1, n):
                start = max(0, i - window)
                for j in range(start, i):
                    r1_strip = sdf.loc[j, 'r3_idx']  # swap
                    r2_strip = sdf.loc[j, 'r2_idx']
                    r3_strip = sdf.loc[j, 'r1_idx']  # swap
                    if r1_strip in sym_idxs or r2_strip in sym_idxs or r3_strip in sym_idxs:
                        counts[i] += 1
            sdf[f'last{window}_{sym_name}_freq'] = counts

    # --- Entropy of last 5 idx triples ---
    def entropy(values):
        if len(values) == 0: return 0
        counts = Counter(values)
        total = sum(counts.values())
        return -sum((c/total) * np.log2(c/total) for c in counts.values() if c > 0)

    ent = np.zeros(n)
    for i in range(5, n):
        vals = []
        for j in range(i-5, i):
            vals.extend([sdf.loc[j,'r1_idx'], sdf.loc[j,'r2_idx'], sdf.loc[j,'r3_idx']])
        ent[i] = entropy(vals)
    sdf['idx_entropy_5'] = ent

    # --- Triple count in last 10 ---
    tc = np.zeros(n)
    for i in range(1, n):
        start = max(0, i-10)
        for j in range(start, i):
            if sdf.loc[j, 'is_triple']:
                tc[i] += 1
    sdf['triples_last10'] = tc

    # --- sa_ counters ---
    for c in ['sa_spins','sa_acc','sa_spn','sa_atk','sa_stl','sa_shd',
              'sa_3x_atk','sa_3x_stl','sa_3x_shd']:
        if c in sdf.columns:
            sdf[c] = pd.to_numeric(sdf[c], errors='coerce')

    # --- Accumulation state ---
    for c in ['accum_current','accum_total','accum_pct']:
        if c in sdf.columns:
            sdf[c] = pd.to_numeric(sdf[c], errors='coerce')

    # --- gap modular features ---
    for mod in [10, 15, 20, 25, 30]:
        sdf[f'gap_mod{mod}'] = sdf['gap'] % mod

    all_features.append(sdf)
    print(f'  {src}: {n} spins, features built')

df = pd.concat(all_features, ignore_index=True)
if 'is_valuable' in df.columns:
    df['is_valuable'] = df['is_valuable'].astype(str).str.lower().isin(['true','1'])
    vt_mask = df['is_valuable']
else:
    vt_mask = df['is_triple'] & df['spin_result'].isin(['gold','spins'])
print(f'\nFinal: {len(df)} spins, {vt_mask.sum()} VTs')

# ===================================================================
# Build feature matrix
# ===================================================================
feature_cols = []
for c in df.columns:
    if c in ['gap','gap_acc','gap_spn']:
        feature_cols.append(c)
    elif c.startswith('prev') and c not in ['prev_result']:
        feature_cols.append(c)
    elif c.endswith(('_mean','_std')):
        feature_cols.append(c)
    elif c.startswith('last'):
        feature_cols.append(c)
    elif c.startswith('idx_entropy'):
        feature_cols.append(c)
    elif c == 'triples_last10':
        feature_cols.append(c)
    elif c.startswith('sa_'):
        feature_cols.append(c)
    elif c.startswith('accum_') and c in df.columns:
        feature_cols.append(c)
    elif c.startswith('gap_mod'):
        feature_cols.append(c)

feature_cols = sorted(set(feature_cols))
print(f'\nFeature columns: {len(feature_cols)}')

X = df[feature_cols].copy()
for c in X.columns:
    X[c] = pd.to_numeric(X[c], errors='coerce')
X = X.fillna(0)
y = vt_mask.astype(int)

# Skip first 10 rows per source
valid = df.groupby('source').cumcount() >= 10
X = X[valid].reset_index(drop=True)
y = y[valid].reset_index(drop=True)
df_valid = df[valid].reset_index(drop=True)

print(f'ML dataset: {len(X)} samples, {y.sum()} positives ({y.mean()*100:.2f}%)')

# ===================================================================
# ML Model
# ===================================================================
try:
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.model_selection import cross_val_predict, StratifiedKFold
    from sklearn.metrics import precision_score, recall_score

    print('\n' + '='*60)
    print('GRADIENT BOOSTED TREE - 5-FOLD CROSS-VALIDATED')
    print('='*60)

    gbt = GradientBoostingClassifier(
        n_estimators=300, max_depth=4, min_samples_leaf=15,
        subsample=0.8, learning_rate=0.05, random_state=42
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    y_pred_proba = cross_val_predict(gbt, X, y, cv=cv, method='predict_proba')[:, 1]

    print('\nThreshold sweep (bph = bets per hit):')
    print(f'{"Threshold":>10} {"Prec%":>8} {"Catch%":>8} {"BPH":>8} {"TP":>5} {"FP":>5} {"Bets":>6}')
    for threshold in [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.15, 0.20, 0.30, 0.50]:
        y_pred = (y_pred_proba >= threshold).astype(int)
        tp = ((y_pred == 1) & (y == 1)).sum()
        fp = ((y_pred == 1) & (y == 0)).sum()
        total_pred = y_pred.sum()
        prec = tp / total_pred * 100 if total_pred > 0 else 0
        recall = tp / y.sum() * 100 if y.sum() > 0 else 0
        bph = total_pred / tp if tp > 0 else float('inf')
        print(f'{threshold:>10.2f} {prec:>8.1f} {recall:>8.1f} {bph:>8.1f} {tp:>5} {fp:>5} {total_pred:>6}')

    # Feature importance
    gbt.fit(X, y)
    importances = pd.Series(gbt.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print('\nTop 30 features by importance:')
    for i, (feat, imp) in enumerate(importances.head(30).items()):
        print(f'  {i+1:2d}. {feat:35s} {imp:.4f}')

    # === Now: train WITHOUT gap features to see if anything else matters ===
    print('\n' + '='*60)
    print('GBT WITHOUT GAP FEATURES (testing pure idx/state signal)')
    print('='*60)

    nogap_cols = [c for c in feature_cols if 'gap' not in c]
    X_nogap = X[nogap_cols]

    gbt2 = GradientBoostingClassifier(
        n_estimators=300, max_depth=4, min_samples_leaf=15,
        subsample=0.8, learning_rate=0.05, random_state=42
    )
    y_pred_proba2 = cross_val_predict(gbt2, X_nogap, y, cv=cv, method='predict_proba')[:, 1]

    print(f'\n{"Threshold":>10} {"Prec%":>8} {"Catch%":>8} {"BPH":>8} {"TP":>5} {"FP":>5}')
    for threshold in [0.02, 0.03, 0.05, 0.10, 0.20]:
        y_pred = (y_pred_proba2 >= threshold).astype(int)
        tp = ((y_pred == 1) & (y == 1)).sum()
        fp = ((y_pred == 1) & (y == 0)).sum()
        total_pred = y_pred.sum()
        prec = tp / total_pred * 100 if total_pred > 0 else 0
        recall = tp / y.sum() * 100 if y.sum() > 0 else 0
        bph = total_pred / tp if tp > 0 else float('inf')
        print(f'{threshold:>10.2f} {prec:>8.1f} {recall:>8.1f} {bph:>8.1f} {tp:>5} {fp:>5}')

    gbt2.fit(X_nogap, y)
    importances2 = pd.Series(gbt2.feature_importances_, index=nogap_cols).sort_values(ascending=False)
    print('\nTop 15 non-gap features:')
    for i, (feat, imp) in enumerate(importances2.head(15).items()):
        print(f'  {i+1:2d}. {feat:35s} {imp:.4f}')

except ImportError:
    print('\nsklearn not available!')
    print('Install with: pip install scikit-learn')

# ===================================================================
# ANGLE: Conditional analysis - what adds info BEYOND gap?
# ===================================================================
print('\n' + '='*60)
print('CONDITIONAL ANALYSIS: WHAT ADDS INFO BEYOND GAP?')
print('='*60)

# For spins with gap >= 40, test every lag-1 feature
high_gap = df_valid['gap'] >= 40
n_high = high_gap.sum()
vt_high = (high_gap & vt_mask[valid].reset_index(drop=True)).sum()
base_rate = vt_high / n_high * 100 if n_high > 0 else 0
print(f'\nBaseline: gap>=40: {vt_high}/{n_high} = {base_rate:.2f}%')

# Test each feature as a split within gap>=40
results = []
test_features = [c for c in feature_cols if 'gap' not in c and c in X.columns]
for feat in test_features:
    vals = X.loc[high_gap, feat].dropna()
    if len(vals) < 50:
        continue
    median = vals.median()

    # Split above/below median
    above = high_gap & (X[feat] > median)
    below = high_gap & (X[feat] <= median)

    vt_above = (above & y.astype(bool)).sum()
    vt_below = (below & y.astype(bool)).sum()
    n_above = above.sum()
    n_below = below.sum()

    if n_above > 0 and n_below > 0:
        rate_above = vt_above / n_above * 100
        rate_below = vt_below / n_below * 100
        diff = abs(rate_above - rate_below)
        better = 'above' if rate_above > rate_below else 'below'
        better_rate = max(rate_above, rate_below)
        better_n = n_above if rate_above > rate_below else n_below
        better_vts = vt_above if rate_above > rate_below else vt_below
        bph = better_n / better_vts if better_vts > 0 else 999
        results.append((feat, diff, better, better_rate, better_vts, better_n, bph, median))

results.sort(key=lambda x: -x[1])
print(f'\nTop 20 features that split VT rate within gap>=40:')
print(f'{"Feature":>35} {"Split":>6} {"Dir":>6} {"Rate%":>7} {"VTs":>5} {"N":>6} {"BPH":>6} {"Median":>8}')
for feat, diff, better, rate, vts, n, bph, med in results[:20]:
    print(f'{feat:>35} {diff:>6.2f} {better:>6} {rate:>7.2f} {vts:>5} {n:>6} {bph:>6.1f} {med:>8.1f}')

# ===================================================================
# ANGLE: Specific sa_acc / sa_spn threshold sweep
# ===================================================================
print('\n' + '='*60)
print('sa_acc AND sa_spn THRESHOLD SWEEP')
print('='*60)

for counter in ['sa_acc', 'sa_spn', 'sa_spins']:
    if counter not in df_valid.columns:
        continue
    vals = pd.to_numeric(df_valid[counter], errors='coerce')
    if vals.isna().all():
        continue

    print(f'\n{counter}:')
    vt_series = vt_mask[valid].reset_index(drop=True)
    for thresh in sorted(vals.dropna().unique()):
        if thresh < 5:
            continue
        m = vals >= thresh
        n_m = m.sum()
        if n_m < 20:
            continue
        vts = (m & vt_series).sum()
        rate = vts / n_m * 100 if n_m > 0 else 0
        bph = n_m / vts if vts > 0 else 999
        if rate > base_rate * 0.8:  # only show if close to baseline or better
            print(f'  >={thresh:.0f}: {vts}/{n_m} = {rate:.2f}%, bph={bph:.1f}')

print('\nDone.')
