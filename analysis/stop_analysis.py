"""Stop-point analysis: when to bail on max bet to avoid outlier waste."""
import pandas as pd, numpy as np, glob, os

files = glob.glob(os.path.join('data', '*', 'spin_history_*.csv'))
all_dfs = []
for f in files:
    try:
        df = pd.read_csv(f, on_bad_lines='skip')
        if 'seq' in df.columns and 'r1' in df.columns:
            acct = os.path.basename(os.path.dirname(f))
            df['account'] = acct
            all_dfs.append(df)
    except:
        pass

df = pd.concat(all_dfs, ignore_index=True)
df = df.sort_values(['account', 'seq']).drop_duplicates(subset=['account', 'seq'], keep='last')
if 'is_triple' in df.columns:
    df['triple'] = df['is_triple'].fillna(False).astype(bool)
else:
    df['triple'] = False
df['triple_raw'] = (df['r1'] == df['r2']) & (df['r2'] == df['r3'])
df['triple'] = df['triple'] | df['triple_raw']
df['is_vt'] = df['triple'] & df['r1'].isin([6, 30])

all_gaps = []
for acct in sorted(df['account'].unique()):
    adf = df[df['account'] == acct].sort_values('seq')
    gap_counter = 0
    for _, row in adf.iterrows():
        if row['is_vt']:
            all_gaps.append(gap_counter)
            gap_counter = 0
        else:
            gap_counter += 1

gaps = np.array(all_gaps[1:])

def classify(g):
    if g <= 20: return 0
    if g <= 35: return 1
    if g <= 55: return 2
    if g <= 80: return 3
    return 4

single_table = [
    (8,34,70,91,128,77), (14,34,57,83,110,37), (8,28,46,73,110,21),
    (5,20,40,68,98,5), (9,23,43,76,91,3), (10,26,41,62,83,34),
    (4,13,33,59,79,4), (4,14,28,48,77,5), (5,19,33,57,72,24),
    (3,11,38,52,74,2), (5,8,27,58,83,0), (4,8,14,20,27,11),
    (3,10,16,34,46,4), (3,8,20,40,60,2), (2,6,18,35,55,1),
]
double_table = [
    (4,3,12,18,30,5,30),(0,4,8,26,53,2,96),(1,4,15,27,51,7,31),
    (4,4,17,28,35,24,12),(3,3,19,29,37,28,28),(3,1,23,30,50,21,44),
    (2,4,13,34,44,4,48),(2,2,19,35,75,15,53),(0,3,13,35,60,0,54),
    (2,3,13,36,58,5,47),(3,4,25,38,58,16,15),(4,1,21,41,55,30,36),
    (0,2,28,42,86,33,60),(3,2,22,42,70,34,43),(4,2,32,42,58,30,44),
    (2,1,17,43,74,6,43),(1,3,26,44,60,22,36),(1,1,22,46,68,44,41),
    (4,0,31,48,81,28,80),(1,2,18,56,77,0,42),(0,0,42,63,84,37,43),
    (1,0,22,68,83,2,40),(0,1,33,69,86,65,26),(3,0,44,70,89,83,64),
    (2,0,50,79,106,85,51),
]
double_dict = {(e[0], e[1]): e for e in double_table if e[6] >= 12}

predicted = []
for i in range(2, len(gaps)):
    prev = gaps[i-1]
    prevprev = gaps[i-2]
    actual = gaps[i]
    cls2 = classify(prevprev)
    cls1 = classify(prev)
    if (cls2, cls1) in double_dict:
        e = double_dict[(cls2, cls1)]
        p25, med, p75 = e[2], e[3], e[4]
        spread = p75 - p25
        p10 = max(1, p25 - spread // 2)
        p90 = p75 + spread // 2
    else:
        bucket = min(prev // 10, 14)
        e = single_table[bucket]
        p10, p25, med, p75, p90 = e[0], e[1], e[2], e[3], e[4]
    predicted.append({
        'actual': actual, 'p10': p10, 'p25': p25, 'med': med, 'p75': p75, 'p90': p90
    })

pdf = pd.DataFrame(predicted)
n = len(pdf)
base_rate = n / pdf['actual'].sum()

print(f'=== STOP POINT ANALYSIS ({n} gaps, {len(df)} spins) ===')
print(f'Strategy: start max bet at P25, stop (drop to min) at various limits')
print()
print(f'{"Stop at":>15s} {"MaxSpins":>9s} {"Caught":>7s} {"Missed":>7s} {"Catch%":>7s} {"Lift":>6s}')
print('-' * 55)

stops = [
    ('P90',      lambda r: r['p90']),
    ('P90+10',   lambda r: r['p90'] + 10),
    ('P90+20',   lambda r: r['p90'] + 20),
    ('P90+30',   lambda r: r['p90'] + 30),
    ('P90+50',   lambda r: r['p90'] + 50),
    ('P75+20',   lambda r: r['p75'] + 20),
    ('P75+30',   lambda r: r['p75'] + 30),
    ('P75+40',   lambda r: r['p75'] + 40),
    ('P75+50',   lambda r: r['p75'] + 50),
    ('2x P75',   lambda r: r['p75'] * 2),
    ('No stop',  lambda r: 99999),
]

for label, stop_fn in stops:
    total_max = 0
    caught = 0
    missed = 0
    for _, r in pdf.iterrows():
        start = r['p25']
        stop = stop_fn(r)
        if r['actual'] < start:
            pass
        elif r['actual'] <= stop:
            total_max += r['actual'] - start
            caught += 1
        else:
            total_max += stop - start
            missed += 1
    eff = caught / max(total_max, 1)
    lift = eff / base_rate
    print(f'{label:>15s} {total_max:>9d} {caught:>7d} {missed:>7d} {caught/n*100:>6.1f}% {lift:>5.2f}x')

print()
print('=== OUTLIERS: gaps that went past P90+30 ===')
outliers = pdf[pdf['actual'] > pdf['p90'] + 30]
print(f'Count: {len(outliers)} / {n} ({len(outliers)/n*100:.1f}%)')
if len(outliers) > 0:
    waste = (outliers['actual'] - outliers['p25']).sum()
    print(f'Total max-bet spins wasted on these: {waste:.0f}')
    print(f'Avg gap length: {outliers["actual"].mean():.0f}')
    print()
    print('Individual outliers:')
    for _, r in outliers.sort_values('actual').iterrows():
        print(f'  gap={int(r["actual"]):4d}  window={int(r["p25"])}-{int(r["p75"])}  P90={int(r["p90"])}  overshoot=+{int(r["actual"]-r["p90"])}')

print()
print('=== EFFICIENCY SWEEP: find best stop ===')
best_lift = 0
best_label = ''
for extra in range(0, 80, 5):
    label = f'P90+{extra}'
    total_max = 0
    caught = 0
    for _, r in pdf.iterrows():
        start = r['p25']
        stop = r['p90'] + extra
        if r['actual'] < start:
            pass
        elif r['actual'] <= stop:
            total_max += r['actual'] - start
            caught += 1
        else:
            total_max += stop - start
    eff = caught / max(total_max, 1)
    lift = eff / base_rate
    tag = ' <-- BEST' if lift > best_lift else ''
    if lift > best_lift:
        best_lift = lift
        best_label = label
    print(f'  {label:>8s}: catch {caught/n*100:.1f}%, lift {lift:.3f}x, {total_max} max spins{tag}')

print()
print(f'OPTIMAL: Start at P25, stop at {best_label} => {best_lift:.3f}x lift')
