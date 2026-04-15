"""
Comprehensive Coin Master Spin Pattern Analysis
================================================
Covers: Sequence, Periodicity, Bet-Level, Streak, Transition Matrix, Symbol/Position
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.signal import find_peaks
from collections import Counter, defaultdict
from itertools import product
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import warnings, glob, os, json

warnings.filterwarnings('ignore')
sns.set_theme(style='whitegrid', font_scale=0.9)
OUT = os.path.dirname(os.path.abspath(__file__))

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ──────────────────────────────────────────────
# 1. LOAD & DEDUPLICATE
# ──────────────────────────────────────────────
def load_all():
    files = sorted(glob.glob('data/*/spin_history*.csv'))
    # skip enriched / default variants
    files = [f for f in files if 'enriched' not in f and 'default' not in f]
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f, on_bad_lines='skip')
            # detect account from path
            acct = f.split(os.sep)[1]
            df['account'] = acct
            df['source'] = os.path.basename(f)
            frames.append(df)
        except Exception as e:
            print(f"  SKIP {f}: {e}")
    combined = pd.concat(frames, ignore_index=True)
    # Deduplicate: keep latest row per (account, seq)
    combined = combined.sort_values(['account', 'seq', 'source']).drop_duplicates(
        subset=['account', 'seq'], keep='last'
    ).sort_values(['account', 'seq']).reset_index(drop=True)
    return combined

print("Loading data...")
df = load_all()
print(f"  Total spins after dedup: {len(df):,}")
print(f"  Accounts: {df['account'].nunique()} ({', '.join(df['account'].unique())})")
print(f"  Triples: {df['is_triple'].sum():,} ({df['is_triple'].mean()*100:.2f}%)")
print(f"  Columns: {len(df.columns)}")
print(f"  Date range: {df['timestamp'].min()} -> {df['timestamp'].max()}")
print()

# Identify triple types
df['triple_type'] = 'none'
mask_triple = df['is_triple'] == True
for sym in ['attack', 'steal', 'shield', 'coin', 'spins', 'goldSack', 'accumulation']:
    mask_sym = mask_triple & (df['reel_1'] == sym)
    df.loc[mask_sym, 'triple_type'] = f'3x_{sym}'

triple_counts = df[mask_triple]['triple_type'].value_counts()
print("Triple breakdown:")
print(triple_counts.to_string())
print()

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def outcome_label(row):
    """Compact outcome label for sequence analysis."""
    if row['is_triple']:
        return f"T_{row['spin_result']}"
    # count matching reels
    syms = [row.get('reel_1',''), row.get('reel_2',''), row.get('reel_3','')]
    if syms[0] == syms[1] or syms[1] == syms[2] or syms[0] == syms[2]:
        return f"P_{row['spin_result']}"  # pair
    return row['spin_result']  # single-symbol result

df['outcome'] = df.apply(outcome_label, axis=1)

REPORT = []
def report(section, text):
    REPORT.append(f"\n{'='*70}\n{section}\n{'='*70}\n{text}\n")
    print(f"--- {section} ---")
    print(text[:500])
    print()


# ╔══════════════════════════════════════════════╗
# ║  A) SEQUENCE ANALYSIS                        ║
# ╚══════════════════════════════════════════════╝
print("="*60)
print("A) SEQUENCE ANALYSIS — pre-triple lead-up patterns")
print("="*60)

WINDOW = 15  # spins before each triple

results_a = []
for acct in df['account'].unique():
    adf = df[df['account'] == acct].reset_index(drop=True)
    triple_idxs = adf.index[adf['is_triple'] == True].tolist()
    for ti in triple_idxs:
        if ti < WINDOW:
            continue
        pre = adf.iloc[ti - WINDOW:ti]
        triple_sym = adf.iloc[ti]['triple_type']
        seq_outcomes = tuple(pre['outcome'].values)
        seq_results = tuple(pre['spin_result'].values)
        results_a.append({
            'account': acct,
            'triple_type': triple_sym,
            'triple_idx': ti,
            'pre_outcomes': seq_outcomes,
            'pre_results': seq_results,
            'pre_triples': pre['is_triple'].sum(),
            'pre_attacks': (pre['reel_1'] == 'attack').sum() + (pre['reel_2'] == 'attack').sum() + (pre['reel_3'] == 'attack').sum(),
            'pre_coins': (pre['reel_1'] == 'coin').sum() + (pre['reel_2'] == 'coin').sum() + (pre['reel_3'] == 'coin').sum(),
            'pre_steals': (pre['reel_1'] == 'steal').sum() + (pre['reel_2'] == 'steal').sum() + (pre['reel_3'] == 'steal').sum(),
            'pre_shields': (pre['reel_1'] == 'shield').sum() + (pre['reel_2'] == 'shield').sum() + (pre['reel_3'] == 'shield').sum(),
            'pre_spins_sym': (pre['reel_1'] == 'spins').sum() + (pre['reel_2'] == 'spins').sum() + (pre['reel_3'] == 'spins').sum(),
            'pre_accum': (pre['reel_1'] == 'accumulation').sum() + (pre['reel_2'] == 'accumulation').sum() + (pre['reel_3'] == 'accumulation').sum(),
        })

seq_df = pd.DataFrame(results_a)
print(f"  Triples with ≥{WINDOW} preceding spins: {len(seq_df)}")

# Compare pre-triple symbol frequencies vs baseline
sym_to_col = {
    'attack': 'pre_attacks', 'coin': 'pre_coins', 'steal': 'pre_steals',
    'shield': 'pre_shields', 'spins': 'pre_spins_sym', 'accumulation': 'pre_accum'
}
baseline_syms = {}
for sym in ['attack', 'coin', 'steal', 'shield', 'spins', 'accumulation']:
    col = sym_to_col[sym]
    total_sym = ((df['reel_1'] == sym).sum() + (df['reel_2'] == sym).sum() + (df['reel_3'] == sym).sum())
    baseline_rate = total_sym / (len(df) * 3)
    if len(seq_df) > 0:
        pre_rate = seq_df[col].mean() / (WINDOW * 3)
    else:
        pre_rate = 0
    baseline_syms[sym] = {'baseline': baseline_rate, 'pre_triple': pre_rate, 'ratio': pre_rate/baseline_rate if baseline_rate > 0 else 0}

sym_comp = pd.DataFrame(baseline_syms).T
sym_comp.columns = ['Baseline Rate', 'Pre-Triple Rate', 'Ratio']
text_a = f"Symbol frequency in {WINDOW} spins before triples vs overall baseline:\n\n"
text_a += sym_comp.to_string(float_format=lambda x: f"{x:.4f}") + "\n\n"
text_a += "(Ratio > 1.0 means symbol appears MORE often before triples)\n"

# Most common 3-spin patterns before triples (last 3 spins)
if len(seq_df) > 0:
    last3 = [s[-3:] for s in seq_df['pre_results']]
    last3_counts = Counter(last3).most_common(15)
    text_a += f"\nTop 15 three-spin patterns immediately before a triple:\n"
    total_triples = len(last3)
    for pat, cnt in last3_counts:
        pct = cnt / total_triples * 100
        text_a += f"  {' -> '.join(pat):30s}  {cnt:4d} ({pct:.1f}%)\n"

    # Test: are these more frequent than chance?
    # Build baseline 3-gram frequencies
    all_results = df['spin_result'].values
    all_3grams = Counter()
    for i in range(len(all_results) - 2):
        all_3grams[tuple(all_results[i:i+3])] += 1
    total_3g = sum(all_3grams.values())

    text_a += f"\nStatistical test (top patterns vs baseline 3-gram frequency):\n"
    for pat, cnt in last3_counts[:5]:
        baseline_freq = all_3grams.get(pat, 0) / total_3g if total_3g > 0 else 0
        observed_freq = cnt / total_triples
        # binomial test
        if baseline_freq > 0:
            pval = stats.binomtest(cnt, total_triples, baseline_freq, alternative='greater').pvalue
            text_a += f"  {' -> '.join(pat):30s}  obs={observed_freq:.3f} base={baseline_freq:.3f} p={pval:.4f} {'*** SIGNIFICANT' if pval < 0.05 else ''}\n"

report("A) SEQUENCE ANALYSIS", text_a)

# Visualization A
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
sym_comp[['Baseline Rate', 'Pre-Triple Rate']].plot(kind='bar', ax=axes[0], color=['steelblue', 'tomato'])
axes[0].set_title('Symbol Frequency: Baseline vs Pre-Triple')
axes[0].set_ylabel('Frequency (per reel)')
axes[0].tick_params(axis='x', rotation=45)

if len(seq_df) > 0:
    # Heatmap: symbol frequency by position before triple
    positions = list(range(-WINDOW, 0))
    sym_names = ['attack', 'coin', 'steal', 'shield', 'spins', 'goldSack', 'accumulation']
    heat_data = np.zeros((len(sym_names), WINDOW))
    for _, row in seq_df.iterrows():
        for pos_i in range(WINDOW):
            for reel in ['reel_1', 'reel_2', 'reel_3']:
                # We need to look up the original data
                pass  # Will do a simpler version

    # Simpler: count of each spin_result at each position before triple
    result_types = df['spin_result'].unique()
    heat_results = np.zeros((len(result_types), WINDOW))
    for _, row in seq_df.iterrows():
        for pos_i, res in enumerate(row['pre_results']):
            ri = np.where(result_types == res)[0]
            if len(ri) > 0:
                heat_results[ri[0], pos_i] += 1
    # Normalize per column
    col_sums = heat_results.sum(axis=0, keepdims=True)
    col_sums[col_sums == 0] = 1
    heat_norm = heat_results / col_sums

    sns.heatmap(heat_norm, ax=axes[1], xticklabels=[str(p) for p in positions],
                yticklabels=result_types, cmap='YlOrRd', annot=False)
    axes[1].set_title(f'Outcome Distribution by Position (last {WINDOW} spins before triple)')
    axes[1].set_xlabel('Position relative to triple')

plt.tight_layout()
plt.savefig(os.path.join(OUT, 'A_sequence_analysis.png'), dpi=150)
plt.close()


# ╔══════════════════════════════════════════════╗
# ║  B) CYCLE / PERIODICITY                      ║
# ╚══════════════════════════════════════════════╝
print("="*60)
print("B) CYCLE / PERIODICITY — autocorrelation & modular patterns")
print("="*60)

text_b = ""

for acct in df['account'].unique():
    adf = df[df['account'] == acct].reset_index(drop=True)
    triple_positions = adf.index[adf['is_triple'] == True].values
    if len(triple_positions) < 5:
        continue

    gaps = np.diff(triple_positions)
    text_b += f"\n--- {acct} ({len(triple_positions)} triples, {len(adf)} spins) ---\n"
    text_b += f"  Gap stats: mean={gaps.mean():.1f}, median={np.median(gaps):.1f}, "
    text_b += f"std={gaps.std():.1f}, min={gaps.min()}, max={gaps.max()}\n"

    # Autocorrelation of triple occurrence binary series
    binary = np.zeros(len(adf))
    binary[triple_positions] = 1

    max_lag = min(500, len(adf) // 3)
    autocorrs = []
    for lag in range(1, max_lag + 1):
        if lag < len(binary):
            c = np.corrcoef(binary[:-lag], binary[lag:])[0, 1]
            autocorrs.append(c)
        else:
            autocorrs.append(0)
    autocorrs = np.array(autocorrs)

    # Find significant peaks
    significance_threshold = 2 / np.sqrt(len(adf))
    peaks, props = find_peaks(autocorrs, height=significance_threshold, distance=5)

    if len(peaks) > 0:
        top_peaks = sorted(peaks, key=lambda p: autocorrs[p], reverse=True)[:10]
        text_b += f"  Significant autocorrelation peaks (>{significance_threshold:.4f}):\n"
        for p in top_peaks:
            text_b += f"    Lag {p+1}: r={autocorrs[p]:.4f}\n"
    else:
        text_b += f"  No significant autocorrelation peaks found (threshold={significance_threshold:.4f})\n"

    # Modular pattern test
    text_b += f"\n  Modular clustering test (chi-squared):\n"
    for mod in [25, 50, 75, 100, 150, 200]:
        if len(triple_positions) < 10:
            continue
        bins = triple_positions % mod
        observed = np.bincount(bins, minlength=mod)
        expected = np.full(mod, len(triple_positions) / mod)
        # Merge sparse bins for valid chi-squared
        min_expected = 5
        merged_obs, merged_exp = [], []
        cum_obs, cum_exp = 0, 0
        for o, e in zip(observed, expected):
            cum_obs += o
            cum_exp += e
            if cum_exp >= min_expected:
                merged_obs.append(cum_obs)
                merged_exp.append(cum_exp)
                cum_obs, cum_exp = 0, 0
        if cum_obs > 0:
            if merged_obs:
                merged_obs[-1] += cum_obs
                merged_exp[-1] += cum_exp
            else:
                merged_obs.append(cum_obs)
                merged_exp.append(cum_exp)

        if len(merged_obs) > 1:
            chi2, pval = stats.chisquare(merged_obs, merged_exp)
            sig = '*** SIGNIFICANT' if pval < 0.05 else ''
            text_b += f"    mod {mod:4d}: χ²={chi2:.2f}, p={pval:.4f} {sig}\n"

# By triple TYPE
for ttype in ['3x_attack', '3x_steal', '3x_shield', '3x_coin', '3x_spins', '3x_accumulation']:
    tdf = df[df['triple_type'] == ttype]
    if len(tdf) < 10:
        continue
    # Per-account gaps
    all_gaps = []
    for acct in tdf['account'].unique():
        adf = df[df['account'] == acct].reset_index(drop=True)
        positions = adf.index[adf['triple_type'] == ttype].values
        if len(positions) > 1:
            all_gaps.extend(np.diff(positions).tolist())
    if all_gaps:
        text_b += f"\n  {ttype} inter-triple gaps (pooled): mean={np.mean(all_gaps):.1f}, "
        text_b += f"median={np.median(all_gaps):.1f}, std={np.std(all_gaps):.1f}\n"

report("B) CYCLE / PERIODICITY", text_b)

# Visualization B
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot autocorrelation for largest account
largest_acct = df.groupby('account').size().idxmax()
adf = df[df['account'] == largest_acct].reset_index(drop=True)
triple_pos = adf.index[adf['is_triple'] == True].values
binary = np.zeros(len(adf))
binary[triple_pos] = 1
max_lag = min(300, len(adf) // 3)
ac = [np.corrcoef(binary[:-l], binary[l:])[0, 1] if l < len(binary) else 0 for l in range(1, max_lag+1)]
axes[0, 0].plot(range(1, max_lag+1), ac, linewidth=0.5, color='steelblue')
sig_thresh = 2 / np.sqrt(len(adf))
axes[0, 0].axhline(y=sig_thresh, color='red', linestyle='--', alpha=0.7, label=f'95% sig ({sig_thresh:.4f})')
axes[0, 0].axhline(y=-sig_thresh, color='red', linestyle='--', alpha=0.7)
axes[0, 0].set_title(f'Autocorrelation of Triple Occurrence ({largest_acct})')
axes[0, 0].set_xlabel('Lag (spins)')
axes[0, 0].set_ylabel('Correlation')
axes[0, 0].legend()

# Gap histogram (all accounts pooled)
all_gaps = []
for acct in df['account'].unique():
    adf = df[df['account'] == acct].reset_index(drop=True)
    tp = adf.index[adf['is_triple'] == True].values
    if len(tp) > 1:
        all_gaps.extend(np.diff(tp).tolist())

axes[0, 1].hist(all_gaps, bins=50, color='steelblue', edgecolor='white', alpha=0.8)
axes[0, 1].axvline(x=np.mean(all_gaps), color='red', linestyle='--', label=f'Mean={np.mean(all_gaps):.1f}')
axes[0, 1].set_title('Inter-Triple Gap Distribution (all accounts)')
axes[0, 1].set_xlabel('Spins between triples')
axes[0, 1].set_ylabel('Count')
axes[0, 1].legend()

# Modular clustering heatmap (mod 50)
mod = 50
for i, acct in enumerate(df['account'].unique()[:2]):
    adf = df[df['account'] == acct].reset_index(drop=True)
    tp = adf.index[adf['is_triple'] == True].values
    bins = tp % mod
    counts = np.bincount(bins, minlength=mod)
    axes[1, i].bar(range(mod), counts, color='steelblue', alpha=0.8)
    axes[1, i].axhline(y=len(tp)/mod, color='red', linestyle='--', alpha=0.7, label='Expected (uniform)')
    axes[1, i].set_title(f'Triple Position mod {mod} ({acct})')
    axes[1, i].set_xlabel(f'Position mod {mod}')
    axes[1, i].set_ylabel('Count')
    axes[1, i].legend()

plt.tight_layout()
plt.savefig(os.path.join(OUT, 'B_periodicity.png'), dpi=150)
plt.close()


# ╔══════════════════════════════════════════════╗
# ║  C) BET LEVEL CORRELATION                    ║
# ╚══════════════════════════════════════════════╝
print("="*60)
print("C) BET LEVEL CORRELATION")
print("="*60)

text_c = ""

if 'bet_multiplier' in df.columns and 'bet_level' in df.columns:
    # Triple rate by bet multiplier
    bet_stats = df.groupby('bet_multiplier').agg(
        total_spins=('is_triple', 'count'),
        triples=('is_triple', 'sum'),
    ).reset_index()
    bet_stats['triple_rate'] = bet_stats['triples'] / bet_stats['total_spins']
    bet_stats['pct'] = bet_stats['triple_rate'] * 100
    text_c += "Triple rate by bet multiplier:\n\n"
    text_c += bet_stats.to_string(index=False) + "\n\n"

    # Chi-squared test: is triple rate independent of bet level?
    if len(bet_stats) > 1:
        contingency = pd.crosstab(df['bet_multiplier'], df['is_triple'])
        chi2, pval, dof, expected = stats.chi2_contingency(contingency)
        text_c += f"Chi-squared test (triple rate vs bet multiplier): χ²={chi2:.2f}, p={pval:.4f}, dof={dof}\n"
        text_c += f"{'*** SIGNIFICANT: Triple rate DOES vary by bet level' if pval < 0.05 else 'Not significant: Triple rate appears independent of bet level'}\n\n"

    # Bet SWITCH analysis: does switching bet level affect next-N triple probability?
    df['bet_changed'] = df.groupby('account')['bet_multiplier'].diff().fillna(0) != 0
    switched = df[df['bet_changed'] == True]
    not_switched = df[df['bet_changed'] == False]

    if len(switched) > 10:
        switch_triple_rate = switched['is_triple'].mean()
        noswitch_triple_rate = not_switched['is_triple'].mean()

        # Look at next 5 spins after a switch
        switch_idxs = df.index[df['bet_changed'] == True].tolist()
        post_switch_triples = 0
        post_switch_total = 0
        for si in switch_idxs:
            window = df.iloc[si:si+5]
            post_switch_triples += window['is_triple'].sum()
            post_switch_total += len(window)

        post_rate = post_switch_triples / post_switch_total if post_switch_total > 0 else 0
        baseline_rate = df['is_triple'].mean()

        text_c += f"Bet switch analysis:\n"
        text_c += f"  Triple rate on switch spin: {switch_triple_rate:.4f}\n"
        text_c += f"  Triple rate on non-switch:  {noswitch_triple_rate:.4f}\n"
        text_c += f"  Triple rate in 5 spins post-switch: {post_rate:.4f}\n"
        text_c += f"  Baseline triple rate: {baseline_rate:.4f}\n"

        # Test significance
        n_switch = len(switched)
        n_noswitch = len(not_switched)
        p1 = switch_triple_rate
        p2 = noswitch_triple_rate
        p_pool = (switched['is_triple'].sum() + not_switched['is_triple'].sum()) / (n_switch + n_noswitch)
        if p_pool > 0 and p_pool < 1:
            se = np.sqrt(p_pool * (1 - p_pool) * (1/n_switch + 1/n_noswitch))
            z = (p1 - p2) / se if se > 0 else 0
            pval_switch = 2 * (1 - stats.norm.cdf(abs(z)))
            text_c += f"  Z-test for switch vs no-switch: z={z:.3f}, p={pval_switch:.4f} "
            text_c += f"{'*** SIGNIFICANT' if pval_switch < 0.05 else ''}\n"

    # Triple rate by bet_level
    if df['bet_level'].nunique() > 1:
        bl_stats = df.groupby('bet_level').agg(
            total_spins=('is_triple', 'count'),
            triples=('is_triple', 'sum'),
        ).reset_index()
        bl_stats['triple_rate'] = bl_stats['triples'] / bl_stats['total_spins']
        text_c += f"\nTriple rate by bet_level:\n"
        text_c += bl_stats.to_string(index=False) + "\n"
else:
    text_c = "No bet_multiplier/bet_level columns found in data.\n"

report("C) BET LEVEL CORRELATION", text_c)

# Visualization C
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
if 'bet_multiplier' in df.columns:
    bet_plot = df.groupby('bet_multiplier')['is_triple'].agg(['mean', 'count']).reset_index()
    bet_plot = bet_plot[bet_plot['count'] >= 20]  # min sample
    axes[0].bar(bet_plot['bet_multiplier'].astype(str), bet_plot['mean'] * 100, color='steelblue')
    axes[0].set_title('Triple Rate by Bet Multiplier')
    axes[0].set_xlabel('Bet Multiplier')
    axes[0].set_ylabel('Triple Rate (%)')
    for i, row in bet_plot.iterrows():
        axes[0].text(i if i < len(bet_plot) else 0, row['mean']*100 + 0.1, f"n={int(row['count'])}",
                     ha='center', fontsize=7)

    # Triple type breakdown by bet level
    if 'bet_level' in df.columns:
        bt_cross = pd.crosstab(df[df['is_triple']]['bet_level'], df[df['is_triple']]['triple_type'])
        bt_cross.plot(kind='bar', stacked=True, ax=axes[1], colormap='Set2')
        axes[1].set_title('Triple Type Distribution by Bet Level')
        axes[1].set_xlabel('Bet Level')
        axes[1].set_ylabel('Count')
        axes[1].legend(fontsize=7)
        axes[1].tick_params(axis='x', rotation=0)

plt.tight_layout()
plt.savefig(os.path.join(OUT, 'C_bet_correlation.png'), dpi=150)
plt.close()


# ╔══════════════════════════════════════════════╗
# ║  D) STREAK / DROUGHT ANALYSIS                ║
# ╚══════════════════════════════════════════════╝
print("="*60)
print("D) STREAK / DROUGHT ANALYSIS — gambler's fallacy test")
print("="*60)

text_d = ""

# Compute drought lengths (gaps between triples)
all_droughts = []
for acct in df['account'].unique():
    adf = df[df['account'] == acct].reset_index(drop=True)
    tp = adf.index[adf['is_triple'] == True].values
    if len(tp) > 1:
        gaps = np.diff(tp)
        all_droughts.extend(gaps.tolist())

droughts = np.array(all_droughts)

text_d += f"Drought length statistics (gaps between ANY triple):\n"
text_d += f"  N gaps: {len(droughts)}\n"
text_d += f"  Mean: {droughts.mean():.1f}\n"
text_d += f"  Median: {np.median(droughts):.1f}\n"
text_d += f"  Std: {droughts.std():.1f}\n"
text_d += f"  Min: {droughts.min()}, Max: {droughts.max()}\n"
text_d += f"  Percentiles: 25th={np.percentile(droughts, 25):.0f}, 75th={np.percentile(droughts, 75):.0f}, 90th={np.percentile(droughts, 90):.0f}, 99th={np.percentile(droughts, 99):.0f}\n\n"

# Test: is the distribution geometric (memoryless)?
# Geometric distribution has mean = 1/p, var = (1-p)/p^2
# If geometric: std/mean should ≈ sqrt(1-p) ≈ ~1 (for small p)
p_est = 1 / droughts.mean()
expected_std = np.sqrt((1 - p_est) / p_est**2)
text_d += f"Geometric (memoryless) test:\n"
text_d += f"  Estimated p (from mean): {p_est:.4f}\n"
text_d += f"  Expected std if geometric: {expected_std:.1f}\n"
text_d += f"  Actual std: {droughts.std():.1f}\n"
text_d += f"  Ratio (actual/expected): {droughts.std()/expected_std:.3f}\n"
text_d += f"  {'Distribution is TIGHTER than geometric -> suggests pity timer / catch-up' if droughts.std() < expected_std * 0.85 else ''}\n"
text_d += f"  {'Distribution is WIDER than geometric -> suggests clustering/streakiness' if droughts.std() > expected_std * 1.15 else ''}\n"
text_d += f"  {'Distribution is consistent with geometric (memoryless/random)' if 0.85 <= droughts.std()/expected_std <= 1.15 else ''}\n\n"

# Kolmogorov-Smirnov test against geometric
from scipy.stats import kstest, geom
ks_stat, ks_pval = kstest(droughts, geom(p_est).cdf)
text_d += f"  KS test vs geometric: D={ks_stat:.4f}, p={ks_pval:.4f}\n"
text_d += f"  {'*** REJECTS geometric (NOT memoryless)' if ks_pval < 0.05 else 'Cannot reject geometric (consistent with random)'}\n\n"

# Conditional probability: after N non-triple spins, what's triple probability?
text_d += "Conditional triple probability by drought length:\n"
text_d += "(Does P(triple) increase with drought? If yes -> pity timer)\n\n"

bins_drought = [(0, 5), (5, 10), (10, 20), (20, 30), (30, 50), (50, 75), (75, 100), (100, 150), (150, 200), (200, 999)]
cond_probs = []

for acct in df['account'].unique():
    adf = df[df['account'] == acct].reset_index(drop=True)
    # Use sa_spins as drought counter (spins since last ACC triple)
    if 'sa_spins' in adf.columns:
        for lo, hi in bins_drought:
            mask = (adf['sa_spins'] >= lo) & (adf['sa_spins'] < hi)
            subset = adf[mask]
            if len(subset) > 0:
                cond_probs.append({
                    'account': acct,
                    'drought_bin': f'{lo}-{hi}',
                    'lo': lo,
                    'n_spins': len(subset),
                    'n_triples': subset['is_triple'].sum(),
                    'triple_rate': subset['is_triple'].mean()
                })

if cond_probs:
    cpdf = pd.DataFrame(cond_probs)
    # Aggregate across accounts
    agg = cpdf.groupby(['drought_bin', 'lo']).agg(
        total_spins=('n_spins', 'sum'),
        total_triples=('n_triples', 'sum')
    ).reset_index().sort_values('lo')
    agg['triple_rate'] = agg['total_triples'] / agg['total_spins']
    agg['pct'] = agg['triple_rate'] * 100

    text_d += agg[['drought_bin', 'total_spins', 'total_triples', 'pct']].to_string(index=False) + "\n\n"

    # Trend test
    from scipy.stats import spearmanr
    if len(agg) > 3:
        corr, pval = spearmanr(agg['lo'], agg['triple_rate'])
        text_d += f"Spearman correlation (drought length vs triple rate): r={corr:.3f}, p={pval:.4f}\n"
        if pval < 0.05 and corr > 0:
            text_d += "*** SIGNIFICANT POSITIVE TREND: Triple probability INCREASES with drought -> pity timer confirmed\n"
        elif pval < 0.05 and corr < 0:
            text_d += "*** SIGNIFICANT NEGATIVE TREND: Triple probability DECREASES with drought -> clustering effect\n"
        else:
            text_d += "No significant trend: consistent with memoryless process\n"

report("D) STREAK / DROUGHT ANALYSIS", text_d)

# Visualization D
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Drought histogram vs geometric
axes[0, 0].hist(droughts, bins=50, density=True, color='steelblue', alpha=0.7, edgecolor='white', label='Observed')
x = np.arange(1, droughts.max() + 1)
axes[0, 0].plot(x, geom.pmf(x, p_est), 'r-', linewidth=1.5, label=f'Geometric(p={p_est:.4f})')
axes[0, 0].set_title('Drought Distribution vs Geometric')
axes[0, 0].set_xlabel('Spins between triples')
axes[0, 0].set_ylabel('Density')
axes[0, 0].legend()
axes[0, 0].set_xlim(0, np.percentile(droughts, 98))

# CDF comparison
sorted_d = np.sort(droughts)
ecdf = np.arange(1, len(sorted_d)+1) / len(sorted_d)
axes[0, 1].plot(sorted_d, ecdf, 'b-', linewidth=1.5, label='Observed ECDF')
axes[0, 1].plot(sorted_d, geom.cdf(sorted_d, p_est), 'r--', linewidth=1.5, label='Geometric CDF')
axes[0, 1].set_title('ECDF vs Geometric CDF')
axes[0, 1].set_xlabel('Drought length')
axes[0, 1].set_ylabel('Cumulative probability')
axes[0, 1].legend()

# Conditional probability by drought
if cond_probs:
    axes[1, 0].bar(range(len(agg)), agg['pct'].values, color='steelblue', alpha=0.8)
    axes[1, 0].set_xticks(range(len(agg)))
    axes[1, 0].set_xticklabels(agg['drought_bin'].values, rotation=45, fontsize=8)
    baseline_pct = df['is_triple'].mean() * 100
    axes[1, 0].axhline(y=baseline_pct, color='red', linestyle='--', label=f'Baseline ({baseline_pct:.1f}%)')
    axes[1, 0].set_title('Triple Rate by Drought Length (sa_spins)')
    axes[1, 0].set_xlabel('Drought bin (spins since last triple)')
    axes[1, 0].set_ylabel('Triple Rate (%)')
    axes[1, 0].legend()

# Hazard function
axes[1, 1].set_title('Hazard Function (instantaneous triple probability)')
survival = 1 - ecdf
hazard = np.diff(ecdf) / survival[:-1]
axes[1, 1].plot(sorted_d[:-1], hazard, '.', markersize=1, alpha=0.3, color='steelblue')
# Smoothed hazard
window = 20
if len(hazard) > window:
    smoothed = np.convolve(hazard, np.ones(window)/window, mode='valid')
    axes[1, 1].plot(sorted_d[window//2:window//2+len(smoothed)], smoothed, 'r-', linewidth=2, label=f'Smoothed (w={window})')
axes[1, 1].axhline(y=p_est, color='green', linestyle='--', alpha=0.7, label=f'Constant hazard ({p_est:.4f})')
axes[1, 1].set_xlabel('Drought length')
axes[1, 1].set_ylabel('Hazard rate')
axes[1, 1].legend()

plt.tight_layout()
plt.savefig(os.path.join(OUT, 'D_streak_drought.png'), dpi=150)
plt.close()


# ╔══════════════════════════════════════════════╗
# ║  E) CONDITIONAL PROBABILITY / TRANSITION     ║
# ╚══════════════════════════════════════════════╝
print("="*60)
print("E) CONDITIONAL PROBABILITY / TRANSITION MATRIX")
print("="*60)

text_e = ""

# Build transition matrix on spin_result
results_col = df.groupby('account').apply(
    lambda g: g.sort_values('seq')['spin_result'].values
).values

all_pairs = []
for arr in results_col:
    for i in range(len(arr) - 1):
        all_pairs.append((arr[i], arr[i+1]))

result_types = sorted(df['spin_result'].unique())
trans_counts = pd.DataFrame(0, index=result_types, columns=result_types)
for a, b in all_pairs:
    if a in trans_counts.index and b in trans_counts.columns:
        trans_counts.loc[a, b] += 1

trans_prob = trans_counts.div(trans_counts.sum(axis=1), axis=0)

text_e += "Transition probability matrix P(next=col | current=row):\n\n"
text_e += trans_prob.to_string(float_format=lambda x: f"{x:.3f}") + "\n\n"

# Chi-squared test for independence
chi2, pval, dof, expected = stats.chi2_contingency(trans_counts.values + 1)  # +1 to avoid 0s
text_e += f"Chi-squared test for independence: χ²={chi2:.2f}, p={pval:.6f}, dof={dof}\n"
text_e += f"{'*** SIGNIFICANT: Transitions are NOT independent (outcome depends on previous)' if pval < 0.05 else 'Not significant: transitions appear independent'}\n\n"

# Find most anomalous transitions
marginal = df['spin_result'].value_counts(normalize=True)
text_e += "Most anomalous transitions (observed vs expected under independence):\n\n"
anomalies = []
for r in result_types:
    for c in result_types:
        obs = trans_prob.loc[r, c] if r in trans_prob.index and c in trans_prob.columns else 0
        exp = marginal.get(c, 0)
        if exp > 0 and trans_counts.loc[r, c] >= 5:
            ratio = obs / exp
            n = trans_counts.loc[r, :].sum()
            # Z-test for proportion
            se = np.sqrt(exp * (1 - exp) / n) if n > 0 else 1
            z = (obs - exp) / se if se > 0 else 0
            pval_z = 2 * (1 - stats.norm.cdf(abs(z)))
            anomalies.append({
                'from': r, 'to': c, 'observed': obs, 'expected': exp,
                'ratio': ratio, 'z': z, 'p': pval_z, 'n': int(trans_counts.loc[r, c])
            })

anom_df = pd.DataFrame(anomalies).sort_values('p')
sig_anoms = anom_df[anom_df['p'] < 0.05]
text_e += f"  {len(sig_anoms)} significant transitions (p < 0.05) out of {len(anom_df)} tested:\n\n"

for _, row in sig_anoms.head(20).iterrows():
    direction = "MORE" if row['ratio'] > 1 else "LESS"
    text_e += f"  {row['from']:12s} -> {row['to']:12s}: obs={row['observed']:.3f} exp={row['expected']:.3f} "
    text_e += f"ratio={row['ratio']:.2f}x ({direction}) z={row['z']:.2f} p={row['p']:.4f} n={row['n']}\n"

# Also test: does seeing a specific outcome change triple probability in next N spins?
text_e += "\n\nTriple probability in next 5 spins given current outcome:\n\n"
baseline_5 = df['is_triple'].mean()
for res in result_types:
    idxs = df.index[df['spin_result'] == res].tolist()
    next5_triples = 0
    next5_total = 0
    for idx in idxs:
        window = df.iloc[idx+1:idx+6]
        # Only count within same account
        if len(window) > 0 and window.iloc[0].get('account') == df.iloc[idx].get('account'):
            next5_triples += window['is_triple'].sum()
            next5_total += len(window)
    if next5_total > 0:
        rate = next5_triples / next5_total
        text_e += f"  After {res:12s}: {rate:.4f} (baseline: {baseline_5:.4f}, ratio: {rate/baseline_5:.2f}x)\n"

report("E) TRANSITION MATRIX", text_e)

# Visualization E
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

sns.heatmap(trans_prob, ax=axes[0], annot=True, fmt='.3f', cmap='YlOrRd',
            linewidths=0.5, square=True)
axes[0].set_title('Transition Probability Matrix\nP(next=col | current=row)')
axes[0].set_xlabel('Next outcome')
axes[0].set_ylabel('Current outcome')

# Deviation from independence
deviation = trans_prob.copy()
for c in result_types:
    deviation[c] = deviation[c] - marginal.get(c, 0)
sns.heatmap(deviation, ax=axes[1], annot=True, fmt='.3f', cmap='RdBu_r', center=0,
            linewidths=0.5, square=True)
axes[1].set_title('Deviation from Independence\n(positive = more likely than chance)')
axes[1].set_xlabel('Next outcome')
axes[1].set_ylabel('Current outcome')

plt.tight_layout()
plt.savefig(os.path.join(OUT, 'E_transition_matrix.png'), dpi=150)
plt.close()


# ╔══════════════════════════════════════════════╗
# ║  F) SYMBOL / POSITION / REEL PATTERNS        ║
# ╚══════════════════════════════════════════════╝
print("="*60)
print("F) SYMBOL / POSITION / REEL CYCLING PATTERNS")
print("="*60)

text_f = ""

# Track reel indices across spins
idx_cols = ['r1_idx', 'r2_idx', 'r3_idx']
has_idx = all(c in df.columns for c in idx_cols)

if has_idx:
    text_f += "Reel index analysis (strip position cycling):\n\n"

    for col in idx_cols:
        vals = df[col].dropna().values
        unique_vals = np.unique(vals)
        text_f += f"  {col}: {len(unique_vals)} unique values, range [{vals.min()}-{vals.max()}]\n"

    # Check for sequential cycling (idx incrementing by fixed step)
    text_f += "\nReel index step analysis (consecutive spin differences):\n"
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].sort_values('seq')
        text_f += f"\n  {acct}:\n"
        for col in idx_cols:
            diffs = adf[col].diff().dropna().values
            diff_counts = Counter(diffs.astype(int))
            top_diffs = diff_counts.most_common(5)
            text_f += f"    {col} step distribution (top 5): "
            text_f += ", ".join([f"Δ{d}={c}({c/len(diffs)*100:.1f}%)" for d, c in top_diffs])
            text_f += f"  [entropy={stats.entropy(list(diff_counts.values())):.2f}]\n"

    # Do reel indices predict triples?
    text_f += "\n\nReel index patterns before triples:\n"

    # For each triple, look at the r1_idx, r2_idx, r3_idx on the spin BEFORE
    pre_triple_idxs = []
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].sort_values('seq').reset_index(drop=True)
        triple_pos = adf.index[adf['is_triple'] == True].values
        for tp in triple_pos:
            if tp > 0:
                prev = adf.iloc[tp - 1]
                pre_triple_idxs.append({
                    'r1_idx': prev['r1_idx'],
                    'r2_idx': prev['r2_idx'],
                    'r3_idx': prev['r3_idx'],
                    'triple_type': adf.iloc[tp]['triple_type'],
                    'r1_idx_triple': adf.iloc[tp]['r1_idx'],
                    'r2_idx_triple': adf.iloc[tp]['r2_idx'],
                    'r3_idx_triple': adf.iloc[tp]['r3_idx'],
                })

    pti_df = pd.DataFrame(pre_triple_idxs)
    if len(pti_df) > 0:
        # Are triples more likely when idx values are in certain ranges?
        for col in idx_cols:
            vals = df[col].dropna()
            if len(vals) > 0:
                # Split into quartiles
                quartiles = pd.qcut(vals, 4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')
                df[f'{col}_q'] = quartiles
                triple_by_q = df.groupby(f'{col}_q')['is_triple'].agg(['mean', 'count'])
                text_f += f"\n  Triple rate by {col} quartile:\n"
                for q, row in triple_by_q.iterrows():
                    text_f += f"    {q}: {row['mean']*100:.2f}% (n={int(row['count'])})\n"

        # Check if r1_idx == r2_idx == r3_idx (same strip position) predicts triple
        df['same_idx'] = (df['r1_idx'] == df['r2_idx']) & (df['r2_idx'] == df['r3_idx'])
        same_rate = df[df['same_idx']]['is_triple'].mean()
        diff_rate = df[~df['same_idx']]['is_triple'].mean()
        text_f += f"\n  Triple rate when all 3 reel indices are SAME: {same_rate*100:.2f}% (n={df['same_idx'].sum()})\n"
        text_f += f"  Triple rate when indices differ: {diff_rate*100:.2f}% (n={(~df['same_idx']).sum()})\n"

    # Index on the triple itself - are triple indices clustered?
    text_f += "\n\nReel index values ON triple spins:\n"
    triple_df = df[df['is_triple'] == True]
    for col in idx_cols:
        vals = triple_df[col].dropna().values
        if len(vals) > 0:
            text_f += f"  {col} on triples: mean={vals.mean():.1f}, std={vals.std():.1f}, "
            text_f += f"mode={stats.mode(vals, keepdims=True).mode[0]}\n"

else:
    text_f += "No reel index columns (r1_idx, r2_idx, r3_idx) found.\n"

# Symbol-level reel analysis
text_f += "\n\nSymbol frequency per reel position:\n"
for reel in ['reel_1', 'reel_2', 'reel_3']:
    counts = df[reel].value_counts(normalize=True)
    text_f += f"\n  {reel}:\n"
    for sym, freq in counts.items():
        text_f += f"    {sym:15s} {freq:.4f} ({freq*100:.1f}%)\n"

# Are reel symbol distributions different from each other?
text_f += "\n\nReel independence test (are reel 1, 2, 3 identically distributed?):\n"
syms_all = sorted(set(df['reel_1'].unique()) | set(df['reel_2'].unique()) | set(df['reel_3'].unique()))
contingency_reels = np.zeros((3, len(syms_all)))
for i, reel in enumerate(['reel_1', 'reel_2', 'reel_3']):
    for j, sym in enumerate(syms_all):
        contingency_reels[i, j] = (df[reel] == sym).sum()
chi2_r, pval_r, dof_r, _ = stats.chi2_contingency(contingency_reels + 1)
text_f += f"  Chi-squared: χ²={chi2_r:.2f}, p={pval_r:.6f}, dof={dof_r}\n"
text_f += f"  {'*** Reel distributions are DIFFERENT' if pval_r < 0.05 else 'Reel distributions appear identical'}\n"

report("F) SYMBOL / POSITION PATTERNS", text_f)

# Visualization F
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Symbol frequency by reel
reel_freq = pd.DataFrame({
    'Reel 1': df['reel_1'].value_counts(normalize=True),
    'Reel 2': df['reel_2'].value_counts(normalize=True),
    'Reel 3': df['reel_3'].value_counts(normalize=True),
}).fillna(0)
reel_freq.plot(kind='bar', ax=axes[0, 0], color=['steelblue', 'tomato', 'seagreen'])
axes[0, 0].set_title('Symbol Frequency by Reel Position')
axes[0, 0].set_ylabel('Frequency')
axes[0, 0].tick_params(axis='x', rotation=45)

# Reel index distribution
if has_idx:
    for i, col in enumerate(idx_cols):
        axes[0, 1].hist(df[col].dropna(), bins=50, alpha=0.5, label=col)
    axes[0, 1].set_title('Reel Index Distribution')
    axes[0, 1].set_xlabel('Strip Index')
    axes[0, 1].set_ylabel('Count')
    axes[0, 1].legend()

    # Index step autocorrelation (is position cycling deterministic?)
    largest_acct = df.groupby('account').size().idxmax()
    adf = df[df['account'] == largest_acct].sort_values('seq')
    r3_diffs = adf['r3_idx'].diff().dropna().values
    if len(r3_diffs) > 100:
        ac_idx = [np.corrcoef(r3_diffs[:-l], r3_diffs[l:])[0, 1] for l in range(1, min(50, len(r3_diffs)//3))]
        axes[1, 0].plot(range(1, len(ac_idx)+1), ac_idx, 'o-', markersize=2, color='steelblue')
        sig_t = 2 / np.sqrt(len(r3_diffs))
        axes[1, 0].axhline(y=sig_t, color='red', linestyle='--', alpha=0.5)
        axes[1, 0].axhline(y=-sig_t, color='red', linestyle='--', alpha=0.5)
        axes[1, 0].set_title(f'Autocorrelation of r3_idx Steps ({largest_acct})')
        axes[1, 0].set_xlabel('Lag')
        axes[1, 0].set_ylabel('Correlation')

# Triple index heatmap
if has_idx and len(triple_df) > 10:
    valid_triple = triple_df.dropna(subset=['r1_idx', 'r3_idx'])
    max_r1 = int(valid_triple['r1_idx'].max()) if len(valid_triple) > 0 else 10
    max_r3 = int(valid_triple['r3_idx'].max()) if len(valid_triple) > 0 else 10
    idx_heat = np.zeros((max(max_r1, 10)+1, max(max_r3, 10)+1))
    for _, row in valid_triple.iterrows():
        r1, r3 = int(row['r1_idx']), int(row['r3_idx'])
        if r1 < idx_heat.shape[0] and r3 < idx_heat.shape[1]:
            idx_heat[r1, r3] += 1
    # Subsample for visualization
    max_dim = 30
    if idx_heat.shape[0] > max_dim:
        # bin the indices
        bin_size = idx_heat.shape[0] // max_dim + 1
        new_h = np.zeros((max_dim, max_dim))
        for i in range(min(max_dim, idx_heat.shape[0])):
            for j in range(min(max_dim, idx_heat.shape[1])):
                i_start, j_start = i*bin_size, j*bin_size
                new_h[i, j] = idx_heat[i_start:i_start+bin_size, j_start:j_start+bin_size].sum()
        idx_heat = new_h
    sns.heatmap(idx_heat[:max_dim, :max_dim], ax=axes[1, 1], cmap='YlOrRd')
    axes[1, 1].set_title('Triple Occurrence by (r1_idx, r3_idx) bin')
    axes[1, 1].set_xlabel('r3_idx bin')
    axes[1, 1].set_ylabel('r1_idx bin')

plt.tight_layout()
plt.savefig(os.path.join(OUT, 'F_symbol_position.png'), dpi=150)
plt.close()


# ╔══════════════════════════════════════════════╗
# ║  SUMMARY REPORT                              ║
# ╚══════════════════════════════════════════════╝
print("\n" + "="*70)
print("WRITING FINAL REPORT")
print("="*70)

# Generate actionable summary
summary = """
╔══════════════════════════════════════════════════════════════════════╗
║  COMPREHENSIVE SPIN PATTERN ANALYSIS — EXECUTIVE SUMMARY           ║
╚══════════════════════════════════════════════════════════════════════╝

Dataset: {total_spins:,} spins across {n_accounts} accounts
Triples: {n_triples:,} ({triple_pct:.2f}%)
Date range: {date_min} -> {date_max}

""".format(
    total_spins=len(df),
    n_accounts=df['account'].nunique(),
    n_triples=int(df['is_triple'].sum()),
    triple_pct=df['is_triple'].mean() * 100,
    date_min=df['timestamp'].min(),
    date_max=df['timestamp'].max(),
)

full_report = summary + "\n".join(REPORT)

report_path = os.path.join(OUT, 'PATTERN_ANALYSIS_REPORT.txt')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(full_report)

print(f"\nReport saved to: {report_path}")
print(f"Charts saved to: {OUT}/A_*.png, B_*.png, C_*.png, D_*.png, E_*.png, F_*.png")
print("\nDone!")
