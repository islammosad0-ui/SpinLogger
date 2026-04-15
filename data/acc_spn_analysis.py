"""
Separate ACC-Triple and SPN-Triple Pattern Analysis
=====================================================
Same 6 analyses (A-F) but run independently for:
  - ACC triples (3x accumulation)
  - SPN triples (3x spins)
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.signal import find_peaks
from collections import Counter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import warnings, glob, os, sys, io

warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sns.set_theme(style='whitegrid', font_scale=0.9)
OUT = os.path.dirname(os.path.abspath(__file__))

# ──────────────────────────────────────────────
# LOAD & DEDUPLICATE
# ──────────────────────────────────────────────
def load_all():
    files = sorted(glob.glob('data/*/spin_history*.csv'))
    files = [f for f in files if 'enriched' not in f and 'default' not in f]
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f, on_bad_lines='skip')
            acct = f.split(os.sep)[1]
            df['account'] = acct
            df['source'] = os.path.basename(f)
            frames.append(df)
        except Exception as e:
            print(f"  SKIP {f}: {e}")
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(['account', 'seq', 'source']).drop_duplicates(
        subset=['account', 'seq'], keep='last'
    ).sort_values(['account', 'seq']).reset_index(drop=True)
    return combined

print("Loading data...")
df = load_all()

# Tag triple types
df['triple_type'] = 'none'
mask_triple = df['is_triple'] == True
for sym in ['attack', 'steal', 'shield', 'coin', 'spins', 'goldSack', 'accumulation']:
    df.loc[mask_triple & (df['reel_1'] == sym), 'triple_type'] = f'3x_{sym}'

df['is_acc_triple'] = df['triple_type'] == '3x_accumulation'
df['is_spn_triple'] = df['triple_type'] == '3x_spins'

print(f"  Total spins: {len(df):,}")
print(f"  ACC triples: {df['is_acc_triple'].sum()} ({df['is_acc_triple'].mean()*100:.3f}%)")
print(f"  SPN triples: {df['is_spn_triple'].sum()} ({df['is_spn_triple'].mean()*100:.3f}%)")
print()

def outcome_label(row):
    if row['is_triple']:
        return f"T_{row['spin_result']}"
    syms = [row.get('reel_1',''), row.get('reel_2',''), row.get('reel_3','')]
    if syms[0] == syms[1] or syms[1] == syms[2] or syms[0] == syms[2]:
        return f"P_{row['spin_result']}"
    return row['spin_result']

df['outcome'] = df.apply(outcome_label, axis=1)


# ══════════════════════════════════════════════════════════════
# Run full analysis for a given triple type
# ══════════════════════════════════════════════════════════════
def run_analysis(df, triple_col, label, sa_col, prefix):
    """
    triple_col: 'is_acc_triple' or 'is_spn_triple'
    label: 'ACC' or 'SPN'
    sa_col: 'sa_acc' or 'sa_spn' (the pity counter column)
    prefix: file prefix for outputs
    """
    REPORT = []
    def report(section, text):
        REPORT.append(f"\n{'='*70}\n{section}\n{'='*70}\n{text}\n")
        print(f"--- {section} ---")
        # print first 400 chars
        print(text[:400])
        print()

    n_triples = df[triple_col].sum()
    triple_rate = df[triple_col].mean()
    print(f"\n{'#'*70}")
    print(f"  ANALYZING: {label} TRIPLES  ({n_triples} events, {triple_rate*100:.3f}% rate)")
    print(f"{'#'*70}\n")

    # ╔════════════════════════════════╗
    # ║  A) SEQUENCE ANALYSIS          ║
    # ╚════════════════════════════════╝
    WINDOW = 20

    results_a = []
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].reset_index(drop=True)
        triple_idxs = adf.index[adf[triple_col] == True].tolist()
        for ti in triple_idxs:
            if ti < WINDOW:
                continue
            pre = adf.iloc[ti - WINDOW:ti]
            seq_results = tuple(pre['spin_result'].values)
            seq_triples = tuple(pre['triple_type'].values)
            # Count symbols in pre-window
            sym_counts = {}
            for sym in ['attack', 'coin', 'steal', 'shield', 'spins', 'goldSack', 'accumulation']:
                c = (pre['reel_1'] == sym).sum() + (pre['reel_2'] == sym).sum() + (pre['reel_3'] == sym).sum()
                sym_counts[f'pre_{sym}'] = c
            # Count pairs and other triples in pre-window
            sym_counts['pre_any_triple'] = pre['is_triple'].sum()
            sym_counts['pre_acc_triple'] = pre['is_acc_triple'].sum()
            sym_counts['pre_spn_triple'] = pre['is_spn_triple'].sum()
            sym_counts['pre_results'] = seq_results
            sym_counts['pre_triples'] = seq_triples
            sym_counts['account'] = acct
            sym_counts['triple_idx'] = ti
            # reel idx info from spin before
            if ti > 0:
                prev = adf.iloc[ti - 1]
                sym_counts['prev_r1_idx'] = prev.get('r1_idx', np.nan)
                sym_counts['prev_r2_idx'] = prev.get('r2_idx', np.nan)
                sym_counts['prev_r3_idx'] = prev.get('r3_idx', np.nan)
            results_a.append(sym_counts)

    seq_df = pd.DataFrame(results_a)
    text_a = f"=== {label} TRIPLE SEQUENCE ANALYSIS ===\n"
    text_a += f"  {label} triples with >={WINDOW} preceding spins: {len(seq_df)}\n\n"

    # Symbol frequency comparison
    sym_names = ['attack', 'coin', 'steal', 'shield', 'spins', 'goldSack', 'accumulation']
    sym_comp = {}
    for sym in sym_names:
        total_sym = (df['reel_1'] == sym).sum() + (df['reel_2'] == sym).sum() + (df['reel_3'] == sym).sum()
        baseline_rate = total_sym / (len(df) * 3)
        pre_rate = seq_df[f'pre_{sym}'].mean() / (WINDOW * 3) if len(seq_df) > 0 else 0
        ratio = pre_rate / baseline_rate if baseline_rate > 0 else 0
        sym_comp[sym] = {'Baseline': baseline_rate, f'Pre-{label}': pre_rate, 'Ratio': ratio}

    sdf = pd.DataFrame(sym_comp).T
    text_a += f"Symbol frequency in {WINDOW} spins before {label} triple vs baseline:\n\n"
    text_a += sdf.to_string(float_format=lambda x: f"{x:.4f}") + "\n\n"

    # Look for elevated symbols
    elevated = sdf[sdf['Ratio'] > 1.05]
    depleted = sdf[sdf['Ratio'] < 0.95]
    if len(elevated) > 0:
        text_a += f"  ELEVATED before {label} triples (>5% above baseline): {', '.join(elevated.index)} \n"
    if len(depleted) > 0:
        text_a += f"  DEPLETED before {label} triples (>5% below baseline): {', '.join(depleted.index)} \n"

    # Top 3-spin and 5-spin patterns before target triple
    if len(seq_df) > 0:
        for w in [3, 5]:
            patterns = [s[-w:] for s in seq_df['pre_results']]
            pat_counts = Counter(patterns).most_common(15)
            text_a += f"\n  Top {w}-spin patterns before {label} triple:\n"
            for pat, cnt in pat_counts:
                pct = cnt / len(patterns) * 100
                text_a += f"    {' -> '.join(pat):45s}  {cnt:4d} ({pct:.1f}%)\n"

            # Test top patterns vs baseline
            all_results = df['spin_result'].values
            all_ngrams = Counter()
            for i in range(len(all_results) - w + 1):
                all_ngrams[tuple(all_results[i:i+w])] += 1
            total_ng = sum(all_ngrams.values())

            text_a += f"\n  Statistical test (top {w}-grams vs baseline):\n"
            for pat, cnt in pat_counts[:8]:
                base_freq = all_ngrams.get(pat, 0) / total_ng if total_ng > 0 else 0
                obs_freq = cnt / len(patterns)
                if base_freq > 0:
                    pval = stats.binomtest(cnt, len(patterns), base_freq, alternative='greater').pvalue
                    sig = '*** SIGNIFICANT' if pval < 0.05 else ''
                    text_a += f"    {' -> '.join(pat):45s}  obs={obs_freq:.4f} base={base_freq:.4f} p={pval:.4f} {sig}\n"

        # Did the PREVIOUS spin's triple_type matter?
        text_a += f"\n  What was the previous spin's triple_type? (last element of pre-window triples):\n"
        prev_types = [t[-1] for t in seq_df['pre_triples']]
        prev_counts = Counter(prev_types)
        for pt, cnt in prev_counts.most_common():
            text_a += f"    {pt:25s}  {cnt:4d} ({cnt/len(prev_types)*100:.1f}%)\n"

    report(f"A) {label} SEQUENCE ANALYSIS", text_a)

    # Viz A
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    sdf[['Baseline', f'Pre-{label}']].plot(kind='bar', ax=axes[0], color=['steelblue', 'tomato'])
    axes[0].set_title(f'Symbol Frequency: Baseline vs Pre-{label}-Triple')
    axes[0].set_ylabel('Frequency (per reel)')
    axes[0].tick_params(axis='x', rotation=45)

    if len(seq_df) > 0:
        result_types = sorted(df['spin_result'].unique())
        heat_results = np.zeros((len(result_types), WINDOW))
        for _, row in seq_df.iterrows():
            for pos_i, res in enumerate(row['pre_results']):
                ri = [j for j, r in enumerate(result_types) if r == res]
                if ri:
                    heat_results[ri[0], pos_i] += 1
        col_sums = heat_results.sum(axis=0, keepdims=True)
        col_sums[col_sums == 0] = 1
        heat_norm = heat_results / col_sums
        positions = list(range(-WINDOW, 0))
        sns.heatmap(heat_norm, ax=axes[1], xticklabels=[str(p) for p in positions],
                    yticklabels=result_types, cmap='YlOrRd')
        axes[1].set_title(f'Outcome Distribution (last {WINDOW} spins before {label} triple)')
        axes[1].set_xlabel('Position relative to triple')

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, f'{prefix}_A_sequence.png'), dpi=150)
    plt.close()

    # ╔════════════════════════════════╗
    # ║  B) CYCLE / PERIODICITY        ║
    # ╚════════════════════════════════╝
    text_b = f"=== {label} TRIPLE PERIODICITY ===\n"

    all_gaps = []
    per_acct_data = {}
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].reset_index(drop=True)
        triple_positions = adf.index[adf[triple_col] == True].values
        if len(triple_positions) < 3:
            continue

        gaps = np.diff(triple_positions)
        all_gaps.extend(gaps.tolist())
        per_acct_data[acct] = {'positions': triple_positions, 'gaps': gaps, 'n_spins': len(adf)}

        text_b += f"\n--- {acct} ({len(triple_positions)} {label} triples, {len(adf)} spins) ---\n"
        text_b += f"  Gap stats: mean={gaps.mean():.1f}, median={np.median(gaps):.1f}, "
        text_b += f"std={gaps.std():.1f}, min={gaps.min()}, max={gaps.max()}\n"
        text_b += f"  Percentiles: 25th={np.percentile(gaps,25):.0f}, 75th={np.percentile(gaps,75):.0f}, "
        text_b += f"90th={np.percentile(gaps,90):.0f}, 95th={np.percentile(gaps,95):.0f}\n"

        # Autocorrelation
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
        sig_thresh = 2 / np.sqrt(len(adf))
        peaks, _ = find_peaks(autocorrs, height=sig_thresh, distance=5)
        if len(peaks) > 0:
            top_peaks = sorted(peaks, key=lambda p: autocorrs[p], reverse=True)[:8]
            text_b += f"  Autocorrelation peaks (>{sig_thresh:.4f}):\n"
            for p in top_peaks:
                text_b += f"    Lag {p+1}: r={autocorrs[p]:.4f}\n"
        else:
            text_b += f"  No significant autocorrelation peaks\n"

        # Modular tests
        text_b += f"  Modular clustering:\n"
        for mod in [25, 50, 75, 100, 150, 200]:
            bins = triple_positions % mod
            observed = np.bincount(bins, minlength=mod)
            expected = np.full(mod, len(triple_positions) / mod)
            merged_obs, merged_exp = [], []
            cum_obs, cum_exp = 0, 0
            for o, e in zip(observed, expected):
                cum_obs += o; cum_exp += e
                if cum_exp >= 5:
                    merged_obs.append(cum_obs); merged_exp.append(cum_exp)
                    cum_obs, cum_exp = 0, 0
            if cum_obs > 0:
                if merged_obs: merged_obs[-1] += cum_obs; merged_exp[-1] += cum_exp
                else: merged_obs.append(cum_obs); merged_exp.append(cum_exp)
            if len(merged_obs) > 1:
                # Normalize expected to match observed total
                merged_obs = np.array(merged_obs, dtype=float)
                merged_exp = np.array(merged_exp, dtype=float)
                merged_exp = merged_exp * (merged_obs.sum() / merged_exp.sum())
                chi2, pval = stats.chisquare(merged_obs, merged_exp)
                sig = '*** SIGNIFICANT' if pval < 0.05 else ''
                text_b += f"    mod {mod:4d}: chi2={chi2:.2f}, p={pval:.4f} {sig}\n"

    report(f"B) {label} PERIODICITY", text_b)

    # Viz B
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    gaps_arr = np.array(all_gaps) if all_gaps else np.array([1])

    # Autocorrelation for largest account
    largest = max(per_acct_data, key=lambda a: per_acct_data[a]['n_spins']) if per_acct_data else None
    if largest:
        adf = df[df['account'] == largest].reset_index(drop=True)
        tp = per_acct_data[largest]['positions']
        binary = np.zeros(len(adf)); binary[tp] = 1
        max_lag = min(400, len(adf) // 3)
        ac = [np.corrcoef(binary[:-l], binary[l:])[0, 1] if l < len(binary) else 0 for l in range(1, max_lag+1)]
        axes[0, 0].plot(range(1, max_lag+1), ac, linewidth=0.5, color='steelblue')
        st = 2 / np.sqrt(len(adf))
        axes[0, 0].axhline(y=st, color='red', linestyle='--', alpha=0.7)
        axes[0, 0].axhline(y=-st, color='red', linestyle='--', alpha=0.7)
        axes[0, 0].set_title(f'{label} Triple Autocorrelation ({largest})')
        axes[0, 0].set_xlabel('Lag'); axes[0, 0].set_ylabel('Correlation')

    axes[0, 1].hist(gaps_arr, bins=min(60, len(set(all_gaps))), color='steelblue', edgecolor='white', alpha=0.8)
    axes[0, 1].axvline(x=gaps_arr.mean(), color='red', linestyle='--', label=f'Mean={gaps_arr.mean():.1f}')
    axes[0, 1].set_title(f'{label} Inter-Triple Gap Distribution')
    axes[0, 1].set_xlabel('Spins between triples'); axes[0, 1].set_ylabel('Count')
    axes[0, 1].legend()

    for i, acct in enumerate(list(per_acct_data.keys())[:2]):
        tp = per_acct_data[acct]['positions']
        mod = 50
        bins = tp % mod
        counts = np.bincount(bins, minlength=mod)
        axes[1, i].bar(range(mod), counts, color='steelblue', alpha=0.8)
        axes[1, i].axhline(y=len(tp)/mod, color='red', linestyle='--', alpha=0.7, label='Expected')
        axes[1, i].set_title(f'{label} Position mod {mod} ({acct})')
        axes[1, i].set_xlabel(f'Position mod {mod}'); axes[1, i].set_ylabel('Count')
        axes[1, i].legend()

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, f'{prefix}_B_periodicity.png'), dpi=150)
    plt.close()

    # ╔════════════════════════════════╗
    # ║  C) BET LEVEL CORRELATION      ║
    # ╚════════════════════════════════╝
    text_c = f"=== {label} TRIPLE vs BET LEVEL ===\n\n"

    bet_stats = df.groupby('bet_multiplier').agg(
        total=('is_triple', 'count'),
        target_triples=(triple_col, 'sum'),
    ).reset_index()
    bet_stats['rate'] = bet_stats['target_triples'] / bet_stats['total']
    bet_stats['pct'] = bet_stats['rate'] * 100
    text_c += f"{label} triple rate by bet multiplier:\n\n"
    text_c += bet_stats.to_string(index=False) + "\n\n"

    # Chi-squared
    contingency = pd.crosstab(df['bet_multiplier'], df[triple_col])
    if contingency.shape[1] == 2:
        chi2, pval, dof, _ = stats.chi2_contingency(contingency)
        text_c += f"Chi-squared: chi2={chi2:.2f}, p={pval:.4f}, dof={dof}\n"
        text_c += f"{'*** SIGNIFICANT' if pval < 0.05 else 'Not significant'}\n\n"

    # Bet switch
    df['bet_changed'] = df.groupby('account')['bet_multiplier'].diff().fillna(0) != 0
    switched = df[df['bet_changed'] == True]
    not_switched = df[df['bet_changed'] == False]
    if len(switched) > 10:
        sw_rate = switched[triple_col].mean()
        nosw_rate = not_switched[triple_col].mean()
        baseline = df[triple_col].mean()

        # Next 5 spins after switch
        switch_idxs = df.index[df['bet_changed'] == True].tolist()
        post_t, post_n = 0, 0
        for si in switch_idxs:
            w = df.iloc[si:si+5]
            post_t += w[triple_col].sum()
            post_n += len(w)
        post_rate = post_t / post_n if post_n > 0 else 0

        text_c += f"Bet switch analysis:\n"
        text_c += f"  {label} rate on switch spin: {sw_rate:.5f} ({sw_rate*100:.3f}%)\n"
        text_c += f"  {label} rate on non-switch:  {nosw_rate:.5f} ({nosw_rate*100:.3f}%)\n"
        text_c += f"  {label} rate in 5 spins post-switch: {post_rate:.5f} ({post_rate*100:.3f}%)\n"
        text_c += f"  Baseline: {baseline:.5f} ({baseline*100:.3f}%)\n"

        n1, n2 = len(switched), len(not_switched)
        p_pool = (switched[triple_col].sum() + not_switched[triple_col].sum()) / (n1 + n2)
        if 0 < p_pool < 1:
            se = np.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2))
            z = (sw_rate - nosw_rate) / se if se > 0 else 0
            pval_sw = 2 * (1 - stats.norm.cdf(abs(z)))
            text_c += f"  Z-test: z={z:.3f}, p={pval_sw:.4f} {'*** SIGNIFICANT' if pval_sw < 0.05 else ''}\n"

    # By bet_level
    if df['bet_level'].nunique() > 1:
        bl = df.groupby('bet_level').agg(total=('is_triple','count'), triples=(triple_col,'sum')).reset_index()
        bl['rate'] = bl['triples'] / bl['total']
        bl['pct'] = bl['rate'] * 100
        text_c += f"\n{label} rate by bet_level:\n"
        text_c += bl[bl['total'] >= 20].to_string(index=False) + "\n"

    report(f"C) {label} BET CORRELATION", text_c)

    # Viz C
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    bp = bet_stats[bet_stats['total'] >= 20].copy()
    axes[0].bar(bp['bet_multiplier'].astype(str), bp['pct'], color='steelblue')
    axes[0].set_title(f'{label} Triple Rate by Bet Multiplier')
    axes[0].set_xlabel('Bet Multiplier'); axes[0].set_ylabel(f'{label} Triple Rate (%)')
    axes[0].axhline(y=df[triple_col].mean()*100, color='red', linestyle='--', label='Baseline')
    axes[0].legend()
    for j, row in bp.reset_index().iterrows():
        if j < len(bp):
            axes[0].text(j, row['pct'] + 0.02, f"n={int(row['total'])}", ha='center', fontsize=6)

    if df['bet_level'].nunique() > 1:
        bl_plot = df.groupby('bet_level').agg(total=('is_triple','count'), triples=(triple_col,'sum')).reset_index()
        bl_plot = bl_plot[bl_plot['total'] >= 50]
        bl_plot['pct'] = bl_plot['triples'] / bl_plot['total'] * 100
        axes[1].bar(bl_plot['bet_level'].astype(str), bl_plot['pct'], color='seagreen')
        axes[1].set_title(f'{label} Triple Rate by Bet Level')
        axes[1].set_xlabel('Bet Level'); axes[1].set_ylabel(f'{label} Triple Rate (%)')
        axes[1].axhline(y=df[triple_col].mean()*100, color='red', linestyle='--', label='Baseline')
        axes[1].legend()

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, f'{prefix}_C_bet.png'), dpi=150)
    plt.close()

    # ╔════════════════════════════════╗
    # ║  D) STREAK / DROUGHT           ║
    # ╚════════════════════════════════╝
    text_d = f"=== {label} TRIPLE DROUGHT ANALYSIS ===\n\n"

    # Use the pity counter column (sa_spins for gap since ACC, sa_spn for SPN)
    # But also compute our own gaps between target triples
    all_droughts = []
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].reset_index(drop=True)
        tp = adf.index[adf[triple_col] == True].values
        if len(tp) > 1:
            all_droughts.extend(np.diff(tp).tolist())

    droughts = np.array(all_droughts) if all_droughts else np.array([1])

    text_d += f"Drought length stats ({label} triple gaps):\n"
    text_d += f"  N gaps: {len(droughts)}\n"
    text_d += f"  Mean: {droughts.mean():.1f}\n"
    text_d += f"  Median: {np.median(droughts):.1f}\n"
    text_d += f"  Std: {droughts.std():.1f}\n"
    text_d += f"  Min: {droughts.min()}, Max: {droughts.max()}\n"
    text_d += f"  Percentiles: 25th={np.percentile(droughts,25):.0f}, 75th={np.percentile(droughts,75):.0f}, "
    text_d += f"90th={np.percentile(droughts,90):.0f}, 95th={np.percentile(droughts,95):.0f}, 99th={np.percentile(droughts,99):.0f}\n\n"

    # Geometric test
    p_est = 1 / droughts.mean()
    expected_std = np.sqrt((1 - p_est) / p_est**2)
    ratio_std = droughts.std() / expected_std
    text_d += f"Geometric (memoryless) test:\n"
    text_d += f"  Estimated p: {p_est:.5f}\n"
    text_d += f"  Expected std (geometric): {expected_std:.1f}\n"
    text_d += f"  Actual std: {droughts.std():.1f}\n"
    text_d += f"  Ratio: {ratio_std:.3f}\n"
    if ratio_std < 0.85:
        text_d += f"  *** TIGHTER than geometric -> pity timer / catch-up mechanism\n"
    elif ratio_std > 1.15:
        text_d += f"  *** WIDER than geometric -> clustering / streakiness\n"
    else:
        text_d += f"  Consistent with geometric\n"

    from scipy.stats import kstest, geom
    ks_stat, ks_pval = kstest(droughts, geom(p_est).cdf)
    text_d += f"  KS test vs geometric: D={ks_stat:.4f}, p={ks_pval:.6f}\n"
    text_d += f"  {'*** REJECTS geometric' if ks_pval < 0.05 else 'Cannot reject geometric'}\n\n"

    # Conditional probability using the sa_ counter
    text_d += f"Conditional {label} triple probability by drought length:\n\n"

    # Use the game's counter column for precise measurement
    if sa_col in df.columns:
        bins_drought = [(0, 10), (10, 20), (20, 40), (40, 60), (60, 80), (80, 100),
                        (100, 130), (130, 160), (160, 200), (200, 250), (250, 350), (350, 999)]
        cond_rows = []
        for lo, hi in bins_drought:
            mask = (df[sa_col] >= lo) & (df[sa_col] < hi)
            subset = df[mask]
            if len(subset) > 0:
                cond_rows.append({
                    'bin': f'{lo}-{hi}', 'lo': lo,
                    'n_spins': len(subset),
                    'n_target': int(subset[triple_col].sum()),
                    'rate': subset[triple_col].mean(),
                    'pct': subset[triple_col].mean() * 100
                })
        cdf = pd.DataFrame(cond_rows)
        text_d += f"  Using {sa_col} counter:\n\n"
        text_d += cdf.to_string(index=False) + "\n\n"

        # Trend test
        if len(cdf) > 3:
            from scipy.stats import spearmanr
            corr, pval_sp = spearmanr(cdf['lo'], cdf['rate'])
            text_d += f"  Spearman r={corr:.3f}, p={pval_sp:.6f}\n"
            if pval_sp < 0.05 and corr > 0:
                text_d += f"  *** SIGNIFICANT: {label} triple probability INCREASES with drought -> PITY TIMER\n"
            elif pval_sp < 0.05 and corr < 0:
                text_d += f"  *** SIGNIFICANT: {label} triple probability DECREASES with drought\n"
            else:
                text_d += f"  No significant trend\n"
    else:
        text_d += f"  Column {sa_col} not found\n"

    # Also test using our own gap computation (position within current gap)
    text_d += f"\nConditional rate by gap position (computed from sequential position):\n\n"
    # For each spin, compute how many spins since the last target triple in this account
    gap_positions = []
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].reset_index(drop=True)
        last_triple = -1
        for i, row in adf.iterrows():
            gap_pos = i - last_triple if last_triple >= 0 else i
            gap_positions.append(gap_pos)
            if row[triple_col]:
                last_triple = i

    df['_gap_pos'] = gap_positions
    bins_gp = [(1, 10), (10, 25), (25, 50), (50, 75), (75, 100), (100, 140), (140, 180), (180, 250), (250, 999)]
    gp_rows = []
    for lo, hi in bins_gp:
        mask = (df['_gap_pos'] >= lo) & (df['_gap_pos'] < hi)
        subset = df[mask]
        if len(subset) > 20:
            gp_rows.append({
                'gap_bin': f'{lo}-{hi}', 'lo': lo,
                'n_spins': len(subset),
                'n_target': int(subset[triple_col].sum()),
                'rate': subset[triple_col].mean(),
                'pct': subset[triple_col].mean() * 100
            })
    gpdf = pd.DataFrame(gp_rows)
    if len(gpdf) > 0:
        text_d += gpdf.to_string(index=False) + "\n\n"
        if len(gpdf) > 3:
            corr2, pval2 = stats.spearmanr(gpdf['lo'], gpdf['rate'])
            text_d += f"  Spearman r={corr2:.3f}, p={pval2:.6f}\n"
            if pval2 < 0.05 and corr2 > 0:
                text_d += f"  *** CONFIRMED: {label} triple rate increases with gap -> PITY TIMER\n"

    report(f"D) {label} DROUGHT ANALYSIS", text_d)

    # Viz D
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Histogram vs geometric
    axes[0, 0].hist(droughts, bins=min(60, len(set(all_droughts))), density=True,
                     color='steelblue', alpha=0.7, edgecolor='white', label='Observed')
    x = np.arange(1, int(np.percentile(droughts, 99)) + 1)
    axes[0, 0].plot(x, geom.pmf(x, p_est), 'r-', linewidth=1.5, label=f'Geometric(p={p_est:.5f})')
    axes[0, 0].set_title(f'{label} Drought Distribution vs Geometric')
    axes[0, 0].set_xlabel('Spins between triples'); axes[0, 0].set_ylabel('Density')
    axes[0, 0].legend(); axes[0, 0].set_xlim(0, np.percentile(droughts, 98))

    # ECDF
    sd = np.sort(droughts)
    ecdf = np.arange(1, len(sd)+1) / len(sd)
    axes[0, 1].plot(sd, ecdf, 'b-', linewidth=1.5, label='Observed ECDF')
    axes[0, 1].plot(sd, geom.cdf(sd, p_est), 'r--', linewidth=1.5, label='Geometric CDF')
    axes[0, 1].set_title(f'{label} ECDF vs Geometric')
    axes[0, 1].set_xlabel('Drought length'); axes[0, 1].set_ylabel('CDF')
    axes[0, 1].legend()

    # Conditional probability bars
    if sa_col in df.columns and len(cond_rows) > 0:
        axes[1, 0].bar(range(len(cdf)), cdf['pct'].values, color='steelblue', alpha=0.8)
        axes[1, 0].set_xticks(range(len(cdf)))
        axes[1, 0].set_xticklabels(cdf['bin'].values, rotation=45, fontsize=7)
        bl_pct = df[triple_col].mean() * 100
        axes[1, 0].axhline(y=bl_pct, color='red', linestyle='--', label=f'Baseline ({bl_pct:.3f}%)')
        axes[1, 0].set_title(f'{label} Triple Rate by {sa_col}')
        axes[1, 0].set_xlabel(f'{sa_col} value'); axes[1, 0].set_ylabel(f'{label} Triple Rate (%)')
        axes[1, 0].legend()

    # Hazard function
    survival = 1 - ecdf
    hazard = np.diff(ecdf) / survival[:-1]
    axes[1, 1].plot(sd[:-1], hazard, '.', markersize=1, alpha=0.3, color='steelblue')
    window = min(20, len(hazard) // 5)
    if len(hazard) > window and window > 0:
        smoothed = np.convolve(hazard, np.ones(window)/window, mode='valid')
        axes[1, 1].plot(sd[window//2:window//2+len(smoothed)], smoothed, 'r-', linewidth=2, label=f'Smoothed (w={window})')
    axes[1, 1].axhline(y=p_est, color='green', linestyle='--', alpha=0.7, label=f'Const hazard ({p_est:.5f})')
    axes[1, 1].set_title(f'{label} Hazard Function')
    axes[1, 1].set_xlabel('Drought length'); axes[1, 1].set_ylabel('Hazard rate')
    axes[1, 1].legend()

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, f'{prefix}_D_drought.png'), dpi=150)
    plt.close()

    # ╔════════════════════════════════╗
    # ║  E) TRANSITION MATRIX          ║
    # ╚════════════════════════════════╝
    text_e = f"=== {label} TRIPLE TRANSITION ANALYSIS ===\n\n"

    # Transition matrix: P(target triple on spin N+k | outcome X on spin N)
    result_types = sorted(df['spin_result'].unique())

    # Immediate next-spin
    text_e += f"P({label} triple on next spin | current spin result):\n\n"
    for res in result_types:
        idxs = df.index[(df['spin_result'] == res)].tolist()
        next_target = 0; total = 0
        for idx in idxs:
            if idx + 1 < len(df) and df.iloc[idx+1].get('account') == df.iloc[idx].get('account'):
                next_target += int(df.iloc[idx+1][triple_col])
                total += 1
        if total > 0:
            rate = next_target / total
            baseline = df[triple_col].mean()
            ratio = rate / baseline if baseline > 0 else 0
            text_e += f"  After {res:12s}: {rate:.5f} ({rate*100:.3f}%) ratio={ratio:.2f}x  n={total}\n"

    # Within next 5 spins
    text_e += f"\nP({label} triple in next 5 spins | current outcome):\n\n"
    for res in result_types:
        idxs = df.index[(df['spin_result'] == res)].tolist()
        hit = 0; total = 0
        for idx in idxs:
            window = df.iloc[idx+1:idx+6]
            if len(window) > 0 and window.iloc[0].get('account') == df.iloc[idx].get('account'):
                hit += int(window[triple_col].any())
                total += 1
        if total > 0:
            rate = hit / total
            baseline_5 = 1 - (1 - df[triple_col].mean())**5
            text_e += f"  After {res:12s}: {rate:.5f} ({rate*100:.3f}%)  expected={baseline_5:.5f}  ratio={rate/baseline_5:.2f}x\n"

    # Within next 10 spins
    text_e += f"\nP({label} triple in next 10 spins | current outcome):\n\n"
    for res in result_types:
        idxs = df.index[(df['spin_result'] == res)].tolist()
        hit = 0; total = 0
        for idx in idxs:
            window = df.iloc[idx+1:idx+11]
            if len(window) > 0 and window.iloc[0].get('account') == df.iloc[idx].get('account'):
                hit += int(window[triple_col].any())
                total += 1
        if total > 0:
            rate = hit / total
            baseline_10 = 1 - (1 - df[triple_col].mean())**10
            text_e += f"  After {res:12s}: {rate:.5f} ({rate*100:.3f}%)  expected={baseline_10:.5f}  ratio={rate/baseline_10:.2f}x\n"

    # After seeing accumulation or spins symbol (not triple)
    text_e += f"\nP({label} triple in next 5 spins | seeing specific SYMBOL on previous spin):\n\n"
    target_sym = 'accumulation' if label == 'ACC' else 'spins'
    for sym in ['attack', 'coin', 'steal', 'shield', 'spins', 'goldSack', 'accumulation']:
        # at least one reel shows this symbol
        mask = (df['reel_1'] == sym) | (df['reel_2'] == sym) | (df['reel_3'] == sym)
        idxs = df.index[mask].tolist()
        hit = 0; total = 0
        for idx in idxs:
            window = df.iloc[idx+1:idx+6]
            if len(window) > 0 and window.iloc[0].get('account') == df.iloc[idx].get('account'):
                hit += int(window[triple_col].any())
                total += 1
        if total > 0:
            rate = hit / total
            mark = ' <-- TARGET SYMBOL' if sym == target_sym else ''
            text_e += f"  Has {sym:15s}: {rate:.5f} ({rate*100:.3f}%)  n={total}{mark}\n"

    # Does having 2 of the target symbol (near-miss) predict the triple?
    text_e += f"\n{label} near-miss analysis (2-of-3 matching {target_sym}):\n"
    near_miss_mask = (
        ((df['reel_1'] == target_sym) & (df['reel_2'] == target_sym) & (df['reel_3'] != target_sym)) |
        ((df['reel_1'] == target_sym) & (df['reel_3'] == target_sym) & (df['reel_2'] != target_sym)) |
        ((df['reel_2'] == target_sym) & (df['reel_3'] == target_sym) & (df['reel_1'] != target_sym))
    )
    nm_idxs = df.index[near_miss_mask].tolist()
    nm_hit = 0; nm_total = 0
    for idx in nm_idxs:
        window = df.iloc[idx+1:idx+6]
        if len(window) > 0 and window.iloc[0].get('account') == df.iloc[idx].get('account'):
            nm_hit += int(window[triple_col].any())
            nm_total += 1
    if nm_total > 0:
        nm_rate = nm_hit / nm_total
        bl5 = 1 - (1 - df[triple_col].mean())**5
        text_e += f"  Near-miss -> {label} triple in next 5: {nm_rate:.5f} ({nm_rate*100:.3f}%)  baseline={bl5:.5f}  ratio={nm_rate/bl5:.2f}x  n={nm_total}\n"
    else:
        text_e += f"  No near-misses found\n"

    report(f"E) {label} TRANSITION ANALYSIS", text_e)

    # Viz E
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Next-1 probability
    next1_data = {}
    for res in result_types:
        idxs = df.index[(df['spin_result'] == res)].tolist()
        nt = 0; tot = 0
        for idx in idxs:
            if idx + 1 < len(df) and df.iloc[idx+1].get('account') == df.iloc[idx].get('account'):
                nt += int(df.iloc[idx+1][triple_col]); tot += 1
        if tot > 0:
            next1_data[res] = nt / tot * 100

    if next1_data:
        axes[0].bar(next1_data.keys(), next1_data.values(), color='steelblue')
        axes[0].axhline(y=df[triple_col].mean()*100, color='red', linestyle='--', label='Baseline')
        axes[0].set_title(f'P({label} triple on next spin | current result)')
        axes[0].set_ylabel(f'{label} Triple Rate (%)'); axes[0].legend()

    # Symbol-level
    sym_data = {}
    for sym in sym_names:
        mask = (df['reel_1'] == sym) | (df['reel_2'] == sym) | (df['reel_3'] == sym)
        idxs = df.index[mask].tolist()
        hit = 0; tot = 0
        for idx in idxs:
            w = df.iloc[idx+1:idx+6]
            if len(w) > 0 and w.iloc[0].get('account') == df.iloc[idx].get('account'):
                hit += int(w[triple_col].any()); tot += 1
        if tot > 0:
            sym_data[sym] = hit / tot * 100

    if sym_data:
        colors = ['tomato' if s == target_sym else 'steelblue' for s in sym_data.keys()]
        axes[1].bar(sym_data.keys(), sym_data.values(), color=colors)
        bl5 = (1 - (1 - df[triple_col].mean())**5) * 100
        axes[1].axhline(y=bl5, color='red', linestyle='--', label=f'Baseline 5-spin ({bl5:.2f}%)')
        axes[1].set_title(f'P({label} triple in 5 spins | symbol on reel)')
        axes[1].set_ylabel(f'{label} Triple Rate (%)'); axes[1].legend()
        axes[1].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, f'{prefix}_E_transitions.png'), dpi=150)
    plt.close()

    # ╔════════════════════════════════╗
    # ║  F) REEL INDEX / POSITION      ║
    # ╚════════════════════════════════╝
    text_f = f"=== {label} TRIPLE REEL/POSITION ANALYSIS ===\n\n"

    idx_cols = ['r1_idx', 'r2_idx', 'r3_idx']
    has_idx = all(c in df.columns for c in idx_cols)

    if has_idx:
        # Reel index values on target triple spins
        target_df = df[df[triple_col] == True]
        text_f += f"Reel indices ON {label} triple spins (n={len(target_df)}):\n"
        for col in idx_cols:
            vals = target_df[col].dropna().values
            if len(vals) > 0:
                vc = pd.Series(vals).value_counts().head(5)
                text_f += f"  {col}: mean={vals.mean():.2f}, std={vals.std():.2f}, "
                text_f += f"top values: {', '.join([f'{int(v)}({c})' for v, c in vc.items()])}\n"

        # Reel index of the spin BEFORE target triple
        text_f += f"\nReel indices on spin BEFORE {label} triple:\n"
        if len(seq_df) > 0 and 'prev_r1_idx' in seq_df.columns:
            for col in ['prev_r1_idx', 'prev_r2_idx', 'prev_r3_idx']:
                vals = seq_df[col].dropna().values
                if len(vals) > 0:
                    text_f += f"  {col}: mean={vals.mean():.2f}, std={vals.std():.2f}\n"

        # Does the reel index PREDICT the target triple?
        text_f += f"\n{label} triple rate by reel index value:\n"
        for col in idx_cols:
            text_f += f"\n  {col}:\n"
            for idx_val in sorted(df[col].dropna().unique()):
                mask = df[col] == idx_val
                subset = df[mask]
                if len(subset) >= 20:
                    rate = subset[triple_col].mean()
                    text_f += f"    idx={int(idx_val):2d}: {rate*100:.3f}% (n={len(subset)})\n"

        # Same-index analysis
        df['_same_idx'] = (df['r1_idx'] == df['r2_idx']) & (df['r2_idx'] == df['r3_idx'])
        same_rate = df[df['_same_idx']][triple_col].mean() if df['_same_idx'].sum() > 0 else 0
        diff_rate = df[~df['_same_idx']][triple_col].mean()
        text_f += f"\n  {label} triple rate when all 3 indices SAME: {same_rate*100:.3f}% (n={df['_same_idx'].sum()})\n"
        text_f += f"  {label} triple rate when indices DIFFER: {diff_rate*100:.3f}% (n={(~df['_same_idx']).sum()})\n"

        # Index DELTA from previous spin -> does the step size predict?
        text_f += f"\n{label} triple rate by r3_idx step from previous spin:\n"
        for acct in df['account'].unique():
            adf = df[df['account'] == acct].sort_values('seq').copy()
            adf['r3_step'] = adf['r3_idx'].diff()
            for step_val in sorted(adf['r3_step'].dropna().unique()):
                mask = adf['r3_step'] == step_val
                subset = adf[mask]
                if len(subset) >= 50:
                    rate = subset[triple_col].mean()
                    if abs(rate - df[triple_col].mean()) / df[triple_col].mean() > 0.15:
                        text_f += f"  [{acct}] step={int(step_val):3d}: {rate*100:.3f}% (n={len(subset)}) "
                        text_f += f"{'*** ELEVATED' if rate > df[triple_col].mean() * 1.15 else '*** DEPLETED'}\n"

    # Symbol-level: which symbols appear on non-matching reels during target triple?
    text_f += f"\nSymbol distribution on {label} triple reels:\n"
    target_sym = 'accumulation' if label == 'ACC' else 'spins'
    target_df = df[df[triple_col] == True]
    # All 3 reels should show the target symbol, verify
    all_match = ((target_df['reel_1'] == target_sym) &
                 (target_df['reel_2'] == target_sym) &
                 (target_df['reel_3'] == target_sym)).mean()
    text_f += f"  Pct where all 3 reels show {target_sym}: {all_match*100:.1f}%\n"

    report(f"F) {label} REEL/POSITION ANALYSIS", text_f)

    # Viz F
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    if has_idx:
        # Index distribution on target triples
        for i, col in enumerate(idx_cols):
            vals = target_df[col].dropna().values
            if len(vals) > 0:
                axes[0, 0].hist(vals, bins=range(int(vals.min()), int(vals.max())+2),
                               alpha=0.5, label=col, edgecolor='white')
        axes[0, 0].set_title(f'Reel Index Distribution on {label} Triples')
        axes[0, 0].set_xlabel('Index'); axes[0, 0].set_ylabel('Count')
        axes[0, 0].legend()

        # Target triple rate by r3_idx
        r3_rates = []
        for idx_val in sorted(df['r3_idx'].dropna().unique()):
            mask = df['r3_idx'] == idx_val
            s = df[mask]
            if len(s) >= 20:
                r3_rates.append({'idx': int(idx_val), 'rate': s[triple_col].mean() * 100, 'n': len(s)})
        if r3_rates:
            rdf = pd.DataFrame(r3_rates)
            axes[0, 1].bar(rdf['idx'].astype(str), rdf['rate'], color='steelblue')
            axes[0, 1].axhline(y=df[triple_col].mean()*100, color='red', linestyle='--', label='Baseline')
            axes[0, 1].set_title(f'{label} Triple Rate by r3_idx')
            axes[0, 1].set_xlabel('r3_idx'); axes[0, 1].set_ylabel(f'{label} Rate (%)')
            axes[0, 1].legend()

        # r1_idx vs r3_idx heatmap for target triples
        valid_t = target_df.dropna(subset=['r1_idx', 'r3_idx'])
        if len(valid_t) > 5:
            max_idx = max(int(valid_t['r1_idx'].max()), int(valid_t['r3_idx'].max())) + 1
            heat = np.zeros((max_idx, max_idx))
            for _, row in valid_t.iterrows():
                r1, r3 = int(row['r1_idx']), int(row['r3_idx'])
                if 0 <= r1 < max_idx and 0 <= r3 < max_idx:
                    heat[r1, r3] += 1
            sns.heatmap(heat, ax=axes[1, 0], cmap='YlOrRd', annot=True if max_idx <= 10 else False,
                       fmt='.0f' if max_idx <= 10 else '')
            axes[1, 0].set_title(f'{label} Triple: r1_idx vs r3_idx')
            axes[1, 0].set_xlabel('r3_idx'); axes[1, 0].set_ylabel('r1_idx')

    # Gap position conditional rate
    if len(gpdf) > 0:
        axes[1, 1].bar(range(len(gpdf)), gpdf['pct'].values, color='steelblue', alpha=0.8)
        axes[1, 1].set_xticks(range(len(gpdf)))
        axes[1, 1].set_xticklabels(gpdf['gap_bin'].values, rotation=45, fontsize=7)
        bl = df[triple_col].mean() * 100
        axes[1, 1].axhline(y=bl, color='red', linestyle='--', label=f'Baseline ({bl:.3f}%)')
        axes[1, 1].set_title(f'{label} Triple Rate by Gap Position')
        axes[1, 1].set_xlabel('Spins since last target triple')
        axes[1, 1].set_ylabel(f'{label} Triple Rate (%)')
        axes[1, 1].legend()

    plt.tight_layout()
    plt.savefig(os.path.join(OUT, f'{prefix}_F_reel.png'), dpi=150)
    plt.close()

    # ──────────────────────────────────
    # WRITE REPORT
    # ──────────────────────────────────
    header = f"""
{'#'*70}
  {label} TRIPLE PATTERN ANALYSIS
{'#'*70}

Dataset: {len(df):,} spins, {n_triples} {label} triples ({triple_rate*100:.3f}%)
Accounts: {df['account'].nunique()} ({', '.join(df['account'].unique())})

"""
    full = header + "\n".join(REPORT)
    path = os.path.join(OUT, f'{prefix}_REPORT.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(full)
    print(f"\n  Report: {path}")
    print(f"  Charts: {prefix}_A/B/C/D/E/F_*.png")

    # cleanup temp cols
    if '_gap_pos' in df.columns:
        df.drop('_gap_pos', axis=1, inplace=True)
    if '_same_idx' in df.columns:
        df.drop('_same_idx', axis=1, inplace=True)


# ══════════════════════════════════════════════
# RUN FOR ACC AND SPN
# ══════════════════════════════════════════════
run_analysis(df, 'is_acc_triple', 'ACC', 'sa_acc', 'ACC')
run_analysis(df, 'is_spn_triple', 'SPN', 'sa_spn', 'SPN')

print("\n\nALL DONE!")
