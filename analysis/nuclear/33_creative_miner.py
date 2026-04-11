import pickle
import pandas as pd
import numpy as np

print("Loading data...")
PKL = 'c:/Users/Islam/Desktop/Coin Master/SpinLogger/analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)

df = []
for acct in data.keys():
    for sess in [0, 1]:
        spins = [s for s in data[acct]['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
        for s in spins:
            df.append({
                'is_acc': (s.get('triple') == 'accumulation'),
                'is_spn': (s.get('triple') == 'spins'),
                'atk': s['atk_count'],
                'stl': s['stl_count'],
                'shd': s['shd_count'],
                'spn': s['spn_count'],
                'acc': s['acc_count'],
                'sa_spins': s['sa_spins']
            })

df = pd.DataFrame(df)
print(f"Total Spins: {len(df)}")

# Create TRUE strictly historical rolling windows (Memory of the past N spins, exclusively)
# Shift(1) means the window evaluates spins N-W to N-1, and perfectly applies to predicting spin N.
for w in [5, 10, 20, 30]:
    df[f'acc_{w}'] = df['acc'].rolling(w).sum().shift(1).fillna(0)
    df[f'spn_{w}'] = df['spn'].rolling(w).sum().shift(1).fillna(0)
    df[f'shd_{w}'] = df['shd'].rolling(w).sum().shift(1).fillna(0)
    df[f'atk_{w}'] = df['atk'].rolling(w).sum().shift(1).fillna(0)
    df[f'sum_{w}'] = (df['atk'] + df['stl'] + df['shd'] + df['spn'] + df['acc']).rolling(w).sum().shift(1).fillna(0)

# Target at spin N
df['target_acc'] = df['is_acc']
df['target_any'] = df['is_acc'] | df['is_spn']

baseline_acc = df['target_acc'].mean()
print(f"\nBaseline ACC hit rate: {baseline_acc*100:.2f}%")

print("\n--- Mining 20-Spin Warmup Windows ---")
for metric in ['acc_20', 'spn_20', 'shd_20', 'atk_20', 'sum_20']:
    print(f"\nEvaluating {metric}:")
    for q in [50, 75, 90, 95, 99]:
        thresh = np.percentile(df[metric], q)
        subset = df[df[metric] > thresh]
        if len(subset) < 20: continue
        rate = subset['target_acc'].mean()
        if rate > baseline_acc * 1.5:
            print(f"  If {metric} > {thresh:.1f} (Top {100-q}% of time, N={len(subset)}) -> Hit Rate: {rate*100:.2f}%")

print("\n--- Mining 10-Spin Warmup Windows ---")
for metric in ['acc_10', 'spn_10', 'shd_10', 'atk_10', 'sum_10']:
    print(f"\nEvaluating {metric}:")
    for q in [50, 75, 90, 95, 99]:
        thresh = np.percentile(df[metric], q)
        subset = df[df[metric] > thresh]
        if len(subset) < 20: continue
        rate = subset['target_acc'].mean()
        if rate > baseline_acc * 1.5:
            print(f"  If {metric} > {thresh:.1f} (Top {100-q}% of time, N={len(subset)}) -> Hit Rate: {rate*100:.2f}%")

print("\n--- Correlation with Pity Zone ---")
# Does a high concentration of Accumulation symbols IN the pity zone predict the exact drop?
pity = df[df['sa_spins'] > 120]
pity_baseline = pity['target_acc'].mean()
print(f"Pity Zone (gap>120) Baseline ACC rate: {pity_baseline*100:.2f}%")

for thresh in range(2, 10):
    subset = pity[pity['acc_10'] >= thresh]
    if len(subset) < 10: continue
    rate = subset['target_acc'].mean()
    if rate > pity_baseline * 1.5:
        print(f"  In Pity Zone, if acc_10 >= {thresh} (N={len(subset)}) -> Hit Rate: {rate*100:.2f}%")

subset2 = pity[pity['acc_10'] == 0]
if len(subset2) > 10:
    print(f"  In Pity Zone, if acc_10 == 0 (N={len(subset2)}) -> Hit Rate: {subset2['target_acc'].mean()*100:.2f}%")
