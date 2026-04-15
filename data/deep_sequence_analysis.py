"""
DEEP SEQUENCE & TRANSITION ANALYSIS — ACC and SPN Triples
==========================================================
Granular spin-by-spin breakdown of the 20 spins before each target triple.
Every reel, every symbol, every index, every pair, every transition.
"""

import pandas as pd
import numpy as np
from scipy import stats
from collections import Counter, defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import warnings, glob, os, sys, io

warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sns.set_theme(style='whitegrid', font_scale=0.85)
OUT = os.path.dirname(os.path.abspath(__file__))

# ── Load ──
def load_all():
    files = sorted(glob.glob('data/*/spin_history*.csv'))
    files = [f for f in files if 'enriched' not in f and 'default' not in f]
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f, on_bad_lines='skip')
            df['account'] = f.split(os.sep)[1]
            frames.append(df)
        except: pass
    c = pd.concat(frames, ignore_index=True)
    c = c.sort_values(['account','seq']).drop_duplicates(subset=['account','seq'], keep='last').reset_index(drop=True)
    return c

print("Loading...")
df = load_all()
df['triple_type'] = 'none'
mask_t = df['is_triple'] == True
for sym in ['attack','steal','shield','coin','spins','goldSack','accumulation']:
    df.loc[mask_t & (df['reel_1'] == sym), 'triple_type'] = f'3x_{sym}'
df['is_acc'] = df['triple_type'] == '3x_accumulation'
df['is_spn'] = df['triple_type'] == '3x_spins'

# Symbol names on each reel
SYMS = ['attack','coin','steal','shield','spins','goldSack','accumulation']

# Pair detection
def count_matching(row):
    r = [row['reel_1'], row['reel_2'], row['reel_3']]
    if r[0]==r[1]==r[2]: return 3
    if r[0]==r[1] or r[1]==r[2] or r[0]==r[2]: return 2
    return 1

df['n_match'] = df.apply(count_matching, axis=1)

# Which symbol forms the pair/triple
def pair_symbol(row):
    r = [row['reel_1'], row['reel_2'], row['reel_3']]
    if r[0]==r[1]: return r[0]
    if r[1]==r[2]: return r[1]
    if r[0]==r[2]: return r[0]
    return 'none'

df['pair_sym'] = df.apply(pair_symbol, axis=1)

print(f"  {len(df):,} spins | ACC: {df['is_acc'].sum()} | SPN: {df['is_spn'].sum()}")

W = 20  # analysis window

# ══════════════════════════════════════════════════════════
def deep_analysis(df, triple_col, label, target_sym, sa_col):
    """Full deep-dive for one triple type."""

    R = []
    def rpt(title, text):
        R.append(f"\n{'='*75}\n{title}\n{'='*75}\n{text}\n")
        print(f"  [{label}] {title}")

    # ── Gather pre-triple windows ──
    windows = []  # list of DataFrames, each is W rows before a target triple
    triple_rows = []
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].reset_index(drop=True)
        idxs = adf.index[adf[triple_col] == True].tolist()
        for ti in idxs:
            if ti < W: continue
            pre = adf.iloc[ti-W:ti].copy()
            pre['pos'] = list(range(-W, 0))  # -20 to -1
            pre['_triple_idx'] = ti
            pre['_acct'] = acct
            windows.append(pre)
            triple_rows.append(adf.iloc[ti])

    n_win = len(windows)
    if n_win == 0:
        rpt("NO DATA", "Not enough triples with preceding window")
        return

    all_pre = pd.concat(windows, ignore_index=True)
    triple_df = pd.DataFrame(triple_rows)

    # ── Also build NON-triple control windows (same size, random positions) ──
    np.random.seed(42)
    ctrl_windows = []
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].reset_index(drop=True)
        non_triple_idxs = adf.index[adf[triple_col] == False].tolist()
        sample_idxs = np.random.choice([i for i in non_triple_idxs if i >= W],
                                        size=min(n_win * 3, len(non_triple_idxs)), replace=False)
        for ci in sample_idxs:
            pre = adf.iloc[ci-W:ci].copy()
            pre['pos'] = list(range(-W, 0))
            ctrl_windows.append(pre)

    all_ctrl = pd.concat(ctrl_windows, ignore_index=True) if ctrl_windows else pd.DataFrame()
    n_ctrl = len(ctrl_windows)

    rpt("OVERVIEW", f"{n_win} {label} triples with {W}-spin windows | {n_ctrl} control windows")

    # ══════════════════════════════════════════
    # 1. POSITION-BY-POSITION SYMBOL FREQUENCY
    # ══════════════════════════════════════════
    text = f"For each position (-{W} to -1), symbol frequency on each reel.\n"
    text += f"Compare pre-{label} vs control. Highlight deviations > 20%.\n\n"

    # Build: for each position, for each reel, for each symbol -> count
    anomalies_pos = []
    for reel in ['reel_1', 'reel_2', 'reel_3']:
        text += f"\n--- {reel} ---\n"
        text += f"{'Pos':>4s} | "
        for sym in SYMS:
            text += f"{sym[:5]:>6s} "
        text += f"| {'best_signal':>12s} ratio    p-val\n"
        text += "-" * 100 + "\n"

        for pos in range(-W, 0):
            pre_slice = all_pre[all_pre['pos'] == pos][reel]
            ctrl_slice = all_ctrl[all_ctrl['pos'] == pos][reel] if len(all_ctrl) > 0 else pd.Series()

            text += f"{pos:4d} | "
            best_sym, best_ratio, best_p = '', 0, 1
            for sym in SYMS:
                pre_rate = (pre_slice == sym).mean() if len(pre_slice) > 0 else 0
                ctrl_rate = (ctrl_slice == sym).mean() if len(ctrl_slice) > 0 else 0
                text += f"{pre_rate:6.3f} "

                if ctrl_rate > 0.01 and len(pre_slice) > 20:
                    ratio = pre_rate / ctrl_rate
                    # binomial test
                    k = int((pre_slice == sym).sum())
                    n = len(pre_slice)
                    alt = 'greater' if ratio > 1 else 'less'
                    try:
                        pv = stats.binomtest(k, n, ctrl_rate, alternative=alt).pvalue
                    except:
                        pv = 1.0
                    if pv < best_p:
                        best_sym, best_ratio, best_p = sym, ratio, pv
                    if pv < 0.05:
                        anomalies_pos.append({
                            'pos': pos, 'reel': reel, 'symbol': sym,
                            'pre_rate': pre_rate, 'ctrl_rate': ctrl_rate,
                            'ratio': ratio, 'p': pv
                        })

            sig = '***' if best_p < 0.05 else '   '
            text += f"| {best_sym:>12s} {best_ratio:5.2f}x  {best_p:.4f} {sig}\n"

    if anomalies_pos:
        text += f"\n\nALL SIGNIFICANT POSITION-SYMBOL ANOMALIES (p < 0.05):\n"
        adf_pos = pd.DataFrame(anomalies_pos).sort_values('p')
        for _, r in adf_pos.iterrows():
            direction = "MORE" if r['ratio'] > 1 else "LESS"
            text += f"  pos={r['pos']:3d} {r['reel']:7s} {r['symbol']:13s}: "
            text += f"pre={r['pre_rate']:.4f} ctrl={r['ctrl_rate']:.4f} "
            text += f"{r['ratio']:.2f}x ({direction}) p={r['p']:.4f}\n"
    else:
        text += "\n  No significant position-symbol anomalies found.\n"

    rpt("1. POSITION-BY-POSITION SYMBOL FREQUENCY (per reel)", text)

    # ══════════════════════════════════════════
    # 2. PAIR/NEAR-MISS TRACKING BEFORE TRIPLE
    # ══════════════════════════════════════════
    text2 = f"Track pairs (2-of-3 matching) and near-misses of {target_sym} by position.\n\n"

    # For each position: what % show a pair? what % show a pair of target_sym?
    text2 += f"{'Pos':>4s} | {'any_pair%':>9s} {'target_pair%':>13s} {'ctrl_pair%':>11s} {'ctrl_tgt%':>10s} | ratio_pair  ratio_tgt\n"
    text2 += "-" * 95 + "\n"

    pair_anomalies = []
    for pos in range(-W, 0):
        pre_slice = all_pre[all_pre['pos'] == pos]
        ctrl_slice = all_ctrl[all_ctrl['pos'] == pos] if len(all_ctrl) > 0 else pd.DataFrame()

        pre_pair = (pre_slice['n_match'] >= 2).mean() if len(pre_slice) > 0 else 0
        pre_tgt_pair = ((pre_slice['n_match'] >= 2) & (pre_slice['pair_sym'] == target_sym)).mean() if len(pre_slice) > 0 else 0
        ctrl_pair = (ctrl_slice['n_match'] >= 2).mean() if len(ctrl_slice) > 0 else 0
        ctrl_tgt_pair = ((ctrl_slice['n_match'] >= 2) & (ctrl_slice['pair_sym'] == target_sym)).mean() if len(ctrl_slice) > 0 else 0

        r_pair = pre_pair / ctrl_pair if ctrl_pair > 0 else 0
        r_tgt = pre_tgt_pair / ctrl_tgt_pair if ctrl_tgt_pair > 0 else 0

        sig = ''
        if ctrl_tgt_pair > 0 and len(pre_slice) > 20:
            k = int(((pre_slice['n_match'] >= 2) & (pre_slice['pair_sym'] == target_sym)).sum())
            pv = stats.binomtest(k, len(pre_slice), ctrl_tgt_pair).pvalue
            if pv < 0.05:
                sig = f' *** p={pv:.4f}'
                pair_anomalies.append({'pos': pos, 'pre': pre_tgt_pair, 'ctrl': ctrl_tgt_pair, 'ratio': r_tgt, 'p': pv})

        text2 += f"{pos:4d} | {pre_pair:9.4f} {pre_tgt_pair:13.4f} {ctrl_pair:11.4f} {ctrl_tgt_pair:10.4f} | {r_pair:9.2f}x  {r_tgt:9.2f}x{sig}\n"

    rpt(f"2. PAIR & NEAR-MISS ({target_sym}) BY POSITION", text2)

    # ══════════════════════════════════════════
    # 3. REEL INDEX TRAJECTORY BEFORE TRIPLE
    # ══════════════════════════════════════════
    text3 = f"Track r1_idx, r2_idx, r3_idx values at each position before {label} triple.\n"
    text3 += f"Compare mean/std vs control. Look for convergence toward target idx.\n\n"

    # What idx does the target triple land on?
    target_idx_vals = triple_df[['r1_idx','r2_idx','r3_idx']].dropna()
    if len(target_idx_vals) > 0:
        target_idx = int(target_idx_vals['r1_idx'].mode().iloc[0])
        text3 += f"Target {label} triple lands on idx = {target_idx} (100% of cases)\n\n"
    else:
        target_idx = None

    for col in ['r1_idx', 'r2_idx', 'r3_idx']:
        text3 += f"\n--- {col} (target idx = {target_idx}) ---\n"
        text3 += f"{'Pos':>4s} | {'pre_mean':>9s} {'pre_std':>8s} {'ctrl_mean':>10s} | {'%_at_target':>12s} {'ctrl_%_tgt':>11s} | delta\n"
        text3 += "-" * 85 + "\n"

        for pos in range(-W, 0):
            pre_v = all_pre[all_pre['pos'] == pos][col].dropna()
            ctrl_v = all_ctrl[all_ctrl['pos'] == pos][col].dropna() if len(all_ctrl) > 0 else pd.Series(dtype=float)

            pre_mean = pre_v.mean() if len(pre_v) > 0 else 0
            pre_std = pre_v.std() if len(pre_v) > 0 else 0
            ctrl_mean = ctrl_v.mean() if len(ctrl_v) > 0 else 0

            pre_at_tgt = (pre_v == target_idx).mean() if target_idx is not None and len(pre_v) > 0 else 0
            ctrl_at_tgt = (ctrl_v == target_idx).mean() if target_idx is not None and len(ctrl_v) > 0 else 0

            delta = pre_mean - ctrl_mean
            sig = '***' if abs(delta) > 0.3 else ''

            text3 += f"{pos:4d} | {pre_mean:9.2f} {pre_std:8.2f} {ctrl_mean:10.2f} | {pre_at_tgt:12.4f} {ctrl_at_tgt:11.4f} | {delta:+.2f} {sig}\n"

    # Index STEP (delta from pos to pos) — does it trend toward target?
    text3 += f"\n\nINDEX STEP ANALYSIS (r3_idx delta between consecutive positions):\n"
    text3 += f"{'Pos':>4s} | {'pre_step_mean':>14s} {'ctrl_step_mean':>15s} | {'pre_toward_tgt%':>16s} {'ctrl_toward%':>13s}\n"
    text3 += "-" * 80 + "\n"

    for pos in range(-W+1, 0):
        pre_curr = all_pre[all_pre['pos'] == pos]['r3_idx'].values
        pre_prev = all_pre[all_pre['pos'] == pos-1]['r3_idx'].values
        ctrl_curr = all_ctrl[all_ctrl['pos'] == pos]['r3_idx'].values if len(all_ctrl) > 0 else np.array([])
        ctrl_prev = all_ctrl[all_ctrl['pos'] == pos-1]['r3_idx'].values if len(all_ctrl) > 0 else np.array([])

        min_len = min(len(pre_curr), len(pre_prev))
        if min_len > 0:
            pre_steps = pre_curr[:min_len] - pre_prev[:min_len]
            pre_step_mean = np.nanmean(pre_steps)
            # "toward target" = step reduces distance to target_idx
            if target_idx is not None:
                pre_dist_before = np.abs(pre_prev[:min_len] - target_idx)
                pre_dist_after = np.abs(pre_curr[:min_len] - target_idx)
                pre_toward = np.nanmean(pre_dist_after < pre_dist_before)
            else:
                pre_toward = 0
        else:
            pre_step_mean = 0; pre_toward = 0

        min_len_c = min(len(ctrl_curr), len(ctrl_prev))
        if min_len_c > 0:
            ctrl_steps = ctrl_curr[:min_len_c] - ctrl_prev[:min_len_c]
            ctrl_step_mean = np.nanmean(ctrl_steps)
            if target_idx is not None:
                ctrl_dist_b = np.abs(ctrl_prev[:min_len_c] - target_idx)
                ctrl_dist_a = np.abs(ctrl_curr[:min_len_c] - target_idx)
                ctrl_toward = np.nanmean(ctrl_dist_a < ctrl_dist_b)
            else:
                ctrl_toward = 0
        else:
            ctrl_step_mean = 0; ctrl_toward = 0

        text3 += f"{pos:4d} | {pre_step_mean:14.3f} {ctrl_step_mean:15.3f} | {pre_toward:16.4f} {ctrl_toward:13.4f}\n"

    rpt(f"3. REEL INDEX TRAJECTORY BEFORE {label}", text3)

    # ══════════════════════════════════════════
    # 4. PREVIOUS SPIN (N-1) DEEP BREAKDOWN
    # ══════════════════════════════════════════
    text4 = f"The single spin immediately before {label} triple — complete breakdown.\n\n"

    prev_spins = all_pre[all_pre['pos'] == -1].copy()
    ctrl_prev = all_ctrl[all_ctrl['pos'] == -1].copy() if len(all_ctrl) > 0 else pd.DataFrame()

    # 4a: spin_result distribution
    text4 += f"spin_result on spin N-1:\n"
    for res in sorted(df['spin_result'].unique()):
        pre_r = (prev_spins['spin_result'] == res).mean() if len(prev_spins) > 0 else 0
        ctrl_r = (ctrl_prev['spin_result'] == res).mean() if len(ctrl_prev) > 0 else 0
        ratio = pre_r / ctrl_r if ctrl_r > 0 else 0
        sig = '***' if abs(ratio - 1) > 0.15 and len(prev_spins) > 30 else ''
        text4 += f"  {res:12s}: pre={pre_r:.4f} ctrl={ctrl_r:.4f} ratio={ratio:.2f}x {sig}\n"

    # 4b: full reel configuration
    text4 += f"\nTop 20 full reel configs (reel_1, reel_2, reel_3) on spin N-1:\n"
    if len(prev_spins) > 0:
        configs = prev_spins.apply(lambda r: f"{r['reel_1']:>13s} | {r['reel_2']:>10s} | {r['reel_3']:>13s}", axis=1)
        cfg_counts = configs.value_counts().head(20)
        for cfg, cnt in cfg_counts.items():
            pct = cnt / len(prev_spins) * 100
            # control rate
            if len(ctrl_prev) > 0:
                ctrl_configs = ctrl_prev.apply(lambda r: f"{r['reel_1']:>13s} | {r['reel_2']:>10s} | {r['reel_3']:>13s}", axis=1)
                ctrl_cnt = (ctrl_configs == cfg).sum()
                ctrl_pct = ctrl_cnt / len(ctrl_prev) * 100
                ratio = pct / ctrl_pct if ctrl_pct > 0 else 0
                sig = '***' if ratio > 1.3 or ratio < 0.7 else ''
            else:
                ctrl_pct = 0; ratio = 0; sig = ''
            text4 += f"  {cfg}  {cnt:4d} ({pct:5.1f}%)  ctrl={ctrl_pct:5.1f}%  ratio={ratio:.2f}x {sig}\n"

    # 4c: n_match on N-1
    text4 += f"\nn_match (reels matching) on spin N-1:\n"
    for m in [1, 2, 3]:
        pre_r = (prev_spins['n_match'] == m).mean() if len(prev_spins) > 0 else 0
        ctrl_r = (ctrl_prev['n_match'] == m).mean() if len(ctrl_prev) > 0 else 0
        ratio = pre_r / ctrl_r if ctrl_r > 0 else 0
        text4 += f"  {m} matching: pre={pre_r:.4f} ctrl={ctrl_r:.4f} ratio={ratio:.2f}x\n"

    # 4d: pair_sym on N-1
    text4 += f"\npair_sym on spin N-1 (which symbol forms the pair):\n"
    for sym in SYMS + ['none']:
        pre_r = (prev_spins['pair_sym'] == sym).mean() if len(prev_spins) > 0 else 0
        ctrl_r = (ctrl_prev['pair_sym'] == sym).mean() if len(ctrl_prev) > 0 else 0
        ratio = pre_r / ctrl_r if ctrl_r > 0 else 0
        sig = '***' if abs(ratio - 1) > 0.2 and pre_r > 0.005 else ''
        text4 += f"  {sym:15s}: pre={pre_r:.4f} ctrl={ctrl_r:.4f} ratio={ratio:.2f}x {sig}\n"

    # 4e: reel indices on N-1
    text4 += f"\nReel indices on spin N-1:\n"
    for col in ['r1_idx', 'r2_idx', 'r3_idx']:
        vals = prev_spins[col].dropna()
        ctrl_vals = ctrl_prev[col].dropna() if len(ctrl_prev) > 0 else pd.Series(dtype=float)
        text4 += f"\n  {col}:\n"
        for idx_v in sorted(df[col].dropna().unique()):
            pre_r = (vals == idx_v).mean() if len(vals) > 0 else 0
            ctrl_r = (ctrl_vals == idx_v).mean() if len(ctrl_vals) > 0 else 0
            ratio = pre_r / ctrl_r if ctrl_r > 0 else 0
            sig = '***' if abs(ratio - 1) > 0.3 and pre_r > 0.01 else ''
            text4 += f"    idx={int(idx_v):2d}: pre={pre_r:.4f} ctrl={ctrl_r:.4f} ratio={ratio:.2f}x {sig}\n"

    # 4f: sa_ counter value on N-1
    if sa_col in prev_spins.columns:
        text4 += f"\n{sa_col} value on spin N-1:\n"
        bins = [(0,10),(10,20),(20,40),(40,60),(60,80),(80,100),(100,150),(150,999)]
        for lo, hi in bins:
            pre_r = ((prev_spins[sa_col] >= lo) & (prev_spins[sa_col] < hi)).mean()
            ctrl_r = ((ctrl_prev[sa_col] >= lo) & (ctrl_prev[sa_col] < hi)).mean() if len(ctrl_prev) > 0 else 0
            ratio = pre_r / ctrl_r if ctrl_r > 0 else 0
            sig = '***' if ratio > 1.3 or ratio < 0.7 else ''
            text4 += f"  {sa_col} {lo:3d}-{hi:3d}: pre={pre_r:.4f} ctrl={ctrl_r:.4f} ratio={ratio:.2f}x {sig}\n"

    # 4g: bet_multiplier on N-1
    text4 += f"\nbet_multiplier on spin N-1:\n"
    for bm in sorted(prev_spins['bet_multiplier'].unique()):
        pre_r = (prev_spins['bet_multiplier'] == bm).mean()
        ctrl_r = (ctrl_prev['bet_multiplier'] == bm).mean() if len(ctrl_prev) > 0 else 0
        ratio = pre_r / ctrl_r if ctrl_r > 0 else 0
        if pre_r > 0.005 or ctrl_r > 0.005:
            sig = '***' if abs(ratio - 1) > 0.2 else ''
            text4 += f"  bet={bm:6d}: pre={pre_r:.4f} ctrl={ctrl_r:.4f} ratio={ratio:.2f}x {sig}\n"

    rpt(f"4. PREVIOUS SPIN (N-1) DEEP BREAKDOWN", text4)

    # ══════════════════════════════════════════
    # 5. N-2 AND N-3 BREAKDOWN
    # ══════════════════════════════════════════
    for lookback, pos_val in [("N-2", -2), ("N-3", -3)]:
        text5 = f"Spin {lookback} before {label} triple.\n\n"
        lb_pre = all_pre[all_pre['pos'] == pos_val]
        lb_ctrl = all_ctrl[all_ctrl['pos'] == pos_val] if len(all_ctrl) > 0 else pd.DataFrame()

        # spin_result
        text5 += f"spin_result:\n"
        for res in sorted(df['spin_result'].unique()):
            pre_r = (lb_pre['spin_result'] == res).mean() if len(lb_pre) > 0 else 0
            ctrl_r = (lb_ctrl['spin_result'] == res).mean() if len(lb_ctrl) > 0 else 0
            ratio = pre_r / ctrl_r if ctrl_r > 0 else 0
            sig = '***' if abs(ratio - 1) > 0.15 else ''
            text5 += f"  {res:12s}: pre={pre_r:.4f} ctrl={ctrl_r:.4f} ratio={ratio:.2f}x {sig}\n"

        # Each reel symbol
        for reel in ['reel_1', 'reel_2', 'reel_3']:
            text5 += f"\n{reel}:\n"
            for sym in SYMS:
                pre_r = (lb_pre[reel] == sym).mean() if len(lb_pre) > 0 else 0
                ctrl_r = (lb_ctrl[reel] == sym).mean() if len(lb_ctrl) > 0 else 0
                ratio = pre_r / ctrl_r if ctrl_r > 0 else 0
                sig = '***' if abs(ratio - 1) > 0.15 and pre_r > 0.01 else ''
                text5 += f"  {sym:15s}: pre={pre_r:.4f} ctrl={ctrl_r:.4f} ratio={ratio:.2f}x {sig}\n"

        # pair info
        text5 += f"\npair_sym:\n"
        for sym in SYMS + ['none']:
            pre_r = (lb_pre['pair_sym'] == sym).mean() if len(lb_pre) > 0 else 0
            ctrl_r = (lb_ctrl['pair_sym'] == sym).mean() if len(lb_ctrl) > 0 else 0
            ratio = pre_r / ctrl_r if ctrl_r > 0 else 0
            sig = '***' if abs(ratio - 1) > 0.2 and pre_r > 0.005 else ''
            text5 += f"  {sym:15s}: pre={pre_r:.4f} ctrl={ctrl_r:.4f} ratio={ratio:.2f}x {sig}\n"

        # reel indices
        text5 += f"\nReel indices:\n"
        for col in ['r1_idx', 'r2_idx', 'r3_idx']:
            pre_v = lb_pre[col].dropna()
            ctrl_v = lb_ctrl[col].dropna() if len(lb_ctrl) > 0 else pd.Series(dtype=float)
            pre_m = pre_v.mean() if len(pre_v) > 0 else 0
            ctrl_m = ctrl_v.mean() if len(ctrl_v) > 0 else 0
            text5 += f"  {col}: pre_mean={pre_m:.2f} ctrl_mean={ctrl_m:.2f} delta={pre_m-ctrl_m:+.2f}\n"

        rpt(f"5. SPIN {lookback} BREAKDOWN", text5)

    # ══════════════════════════════════════════
    # 6. 2-SPIN AND 3-SPIN TRANSITION PATTERNS
    # ══════════════════════════════════════════
    text6 = f"Full (reel_1,reel_2,reel_3) config transitions leading into {label} triple.\n\n"

    # 2-spin: what config on N-1 given config on N-2?
    text6 += f"--- Last 2 spins before {label} triple (N-2 -> N-1) ---\n"
    text6 += f"Top 20 (N-2 result, N-1 result) pairs:\n"
    pairs_2 = []
    for w in windows:
        r_m2 = w[w['pos'] == -2].iloc[0]['spin_result'] if len(w[w['pos'] == -2]) > 0 else ''
        r_m1 = w[w['pos'] == -1].iloc[0]['spin_result'] if len(w[w['pos'] == -1]) > 0 else ''
        pairs_2.append((r_m2, r_m1))

    p2_counts = Counter(pairs_2).most_common(20)
    # baseline 2-gram
    all_2g = Counter()
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].sort_values('seq')
        res = adf['spin_result'].values
        for i in range(len(res)-1):
            all_2g[(res[i], res[i+1])] += 1
    total_2g = sum(all_2g.values())

    for pair, cnt in p2_counts:
        pct = cnt / len(pairs_2) * 100
        base = all_2g.get(pair, 0) / total_2g * 100 if total_2g > 0 else 0
        ratio = pct / base if base > 0 else 0
        sig = '***' if ratio > 1.3 or ratio < 0.7 else ''
        text6 += f"  {pair[0]:>8s} -> {pair[1]:>8s}:  {cnt:4d} ({pct:5.1f}%)  base={base:5.1f}%  ratio={ratio:.2f}x {sig}\n"

    # 3-spin: N-3 -> N-2 -> N-1
    text6 += f"\n--- Last 3 spins (N-3 -> N-2 -> N-1) ---\n"
    triples_3 = []
    for w in windows:
        r3 = w[w['pos'] == -3].iloc[0]['spin_result'] if len(w[w['pos'] == -3]) > 0 else ''
        r2 = w[w['pos'] == -2].iloc[0]['spin_result'] if len(w[w['pos'] == -2]) > 0 else ''
        r1 = w[w['pos'] == -1].iloc[0]['spin_result'] if len(w[w['pos'] == -1]) > 0 else ''
        triples_3.append((r3, r2, r1))

    t3_counts = Counter(triples_3).most_common(20)
    all_3g = Counter()
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].sort_values('seq')
        res = adf['spin_result'].values
        for i in range(len(res)-2):
            all_3g[(res[i], res[i+1], res[i+2])] += 1
    total_3g = sum(all_3g.values())

    for trip, cnt in t3_counts:
        pct = cnt / len(triples_3) * 100
        base = all_3g.get(trip, 0) / total_3g * 100 if total_3g > 0 else 0
        ratio = pct / base if base > 0 else 0
        sig = '***' if ratio > 1.3 or ratio < 0.7 else ''
        text6 += f"  {trip[0]:>8s} -> {trip[1]:>8s} -> {trip[2]:>8s}:  {cnt:4d} ({pct:5.1f}%)  base={base:5.1f}%  ratio={ratio:.2f}x {sig}\n"

    # SYMBOL-LEVEL 2-spin: (reel_1 on N-1, reel_2 on N-1, reel_3 on N-1) full config
    text6 += f"\n--- Full reel config on N-1 (symbol-level) ---\n"
    text6 += f"Top 25 configs and whether they predict {label}:\n"
    if len(prev_spins) > 0:
        prev_configs = prev_spins.apply(
            lambda r: (r['reel_1'], r['reel_2'], r['reel_3']), axis=1
        )
        cfg_counts = prev_configs.value_counts().head(25)
        # baseline config frequencies
        all_cfgs = df.apply(lambda r: (r['reel_1'], r['reel_2'], r['reel_3']), axis=1)
        all_cfg_counts = all_cfgs.value_counts()
        total_cfgs = len(df)

        for cfg, cnt in cfg_counts.items():
            pct = cnt / len(prev_spins) * 100
            base_cnt = all_cfg_counts.get(cfg, 0)
            base_pct = base_cnt / total_cfgs * 100
            ratio = pct / base_pct if base_pct > 0 else 0
            sig = '***' if ratio > 1.3 or ratio < 0.7 else ''
            text6 += f"  ({cfg[0]:>5s}, {cfg[1]:>8s}, {cfg[2]:>8s}): {cnt:3d} ({pct:5.1f}%) base={base_pct:5.1f}% ratio={ratio:.2f}x {sig}\n"

    rpt(f"6. TRANSITION PATTERNS (2-spin, 3-spin, symbol-level)", text6)

    # ══════════════════════════════════════════
    # 7. CONDITIONAL: GIVEN I SEE X, WHAT'S THE
    #    PROBABILITY OF TARGET TRIPLE IN NEXT N?
    # ══════════════════════════════════════════
    text7 = f"If I see condition X on the current spin, what's P({label} triple) in next 1/3/5/10 spins?\n\n"

    conditions = {}

    # Condition: each spin_result
    for res in sorted(df['spin_result'].unique()):
        conditions[f'result={res}'] = df['spin_result'] == res

    # Condition: each reel symbol on any reel
    for sym in SYMS:
        conditions[f'has_{sym}'] = (df['reel_1'] == sym) | (df['reel_2'] == sym) | (df['reel_3'] == sym)

    # Condition: pair of target sym
    conditions[f'pair_{target_sym}'] = (df['n_match'] >= 2) & (df['pair_sym'] == target_sym)

    # Condition: any pair
    conditions['any_pair'] = df['n_match'] >= 2

    # Condition: any triple (of any type)
    conditions['any_triple'] = df['is_triple'] == True

    # Condition: specific other triples
    for tt in ['3x_attack', '3x_coin', '3x_goldSack', '3x_steal', '3x_shield']:
        conditions[f'after_{tt}'] = df['triple_type'] == tt

    # Condition: r3_idx values
    for idx_v in sorted(df['r3_idx'].dropna().unique()):
        conditions[f'r3_idx={int(idx_v)}'] = df['r3_idx'] == idx_v

    # Condition: sa_counter ranges
    if sa_col in df.columns:
        for lo, hi in [(0,20),(20,50),(50,80),(80,120),(120,160),(160,999)]:
            conditions[f'{sa_col}_{lo}-{hi}'] = (df[sa_col] >= lo) & (df[sa_col] < hi)

    # Condition: bet multiplier ranges
    conditions['bet<=3'] = df['bet_multiplier'] <= 3
    conditions['bet>=50'] = df['bet_multiplier'] >= 50
    conditions['bet>=400'] = df['bet_multiplier'] >= 400

    baseline = df[triple_col].mean()
    text7 += f"Baseline {label} rate: {baseline:.5f} ({baseline*100:.3f}%)\n\n"
    text7 += f"{'Condition':>30s} | {'n':>7s} | {'next1':>8s} {'next3':>8s} {'next5':>8s} {'next10':>8s} | {'r1':>5s} {'r3':>5s} {'r5':>5s} {'r10':>5s}\n"
    text7 += "-" * 110 + "\n"

    cond_results = []
    for cond_name, mask in conditions.items():
        idxs = df.index[mask].tolist()
        if len(idxs) < 20: continue

        hits = {1: 0, 3: 0, 5: 0, 10: 0}
        totals = {1: 0, 3: 0, 5: 0, 10: 0}
        for idx in idxs:
            acct = df.iloc[idx].get('account', '')
            for horizon in [1, 3, 5, 10]:
                window = df.iloc[idx+1:idx+1+horizon]
                if len(window) > 0 and window.iloc[0].get('account', '') == acct:
                    hits[horizon] += int(window[triple_col].any())
                    totals[horizon] += 1

        rates = {}
        ratios = {}
        for h in [1, 3, 5, 10]:
            r = hits[h] / totals[h] if totals[h] > 0 else 0
            bl = 1 - (1 - baseline)**h
            rates[h] = r
            ratios[h] = r / bl if bl > 0 else 0

        # Flag interesting ones
        any_sig = any(ratios[h] > 1.3 or ratios[h] < 0.7 for h in [1, 3, 5, 10])
        flag = ' ***' if any_sig else ''

        text7 += f"{cond_name:>30s} | {len(idxs):7d} | "
        text7 += f"{rates[1]*100:7.3f}% {rates[3]*100:7.3f}% {rates[5]*100:7.3f}% {rates[10]*100:7.3f}% | "
        text7 += f"{ratios[1]:5.2f} {ratios[3]:5.2f} {ratios[5]:5.2f} {ratios[10]:5.2f}{flag}\n"

        cond_results.append({'cond': cond_name, 'n': len(idxs), **{f'r{h}': ratios[h] for h in [1,3,5,10]}})

    # Summary of best predictors
    crdf = pd.DataFrame(cond_results)
    if len(crdf) > 0:
        text7 += f"\n\nTOP 10 POSITIVE PREDICTORS (by next-5 ratio):\n"
        top = crdf.nlargest(10, 'r5')
        for _, r in top.iterrows():
            text7 += f"  {r['cond']:>30s}  n={r['n']:6d}  r1={r['r1']:.2f}x  r5={r['r5']:.2f}x  r10={r['r10']:.2f}x\n"

        text7 += f"\nTOP 10 NEGATIVE PREDICTORS (lowest next-5 ratio):\n"
        bot = crdf.nsmallest(10, 'r5')
        for _, r in bot.iterrows():
            text7 += f"  {r['cond']:>30s}  n={r['n']:6d}  r1={r['r1']:.2f}x  r5={r['r5']:.2f}x  r10={r['r10']:.2f}x\n"

    rpt(f"7. CONDITIONAL PROBABILITY TABLE — P({label}) AFTER SEEING X", text7)

    # ══════════════════════════════════════════
    # 8. COMBINED CONDITIONS (multi-factor)
    # ══════════════════════════════════════════
    text8 = f"Test combined conditions for stronger signals.\n\n"

    combos = []
    # High drought + specific conditions
    if sa_col in df.columns:
        for thresh in [60, 80, 100, 120]:
            drought_mask = df[sa_col] >= thresh
            for cond_name, extra_mask in [
                ('has_steal', (df['reel_1']=='steal')|(df['reel_2']=='steal')|(df['reel_3']=='steal')),
                ('has_goldSack', (df['reel_1']=='goldSack')|(df['reel_2']=='goldSack')|(df['reel_3']=='goldSack')),
                ('has_attack', (df['reel_1']=='attack')|(df['reel_2']=='attack')|(df['reel_3']=='attack')),
                ('any_pair', df['n_match'] >= 2),
                (f'pair_{target_sym}', (df['n_match']>=2)&(df['pair_sym']==target_sym)),
                ('bet>=50', df['bet_multiplier'] >= 50),
                ('bet>=400', df['bet_multiplier'] >= 400),
                ('result=attack', df['spin_result'] == 'attack'),
                ('result=steal', df['spin_result'] == 'steal'),
            ]:
                combined = drought_mask & extra_mask
                n_comb = combined.sum()
                if n_comb < 15: continue

                idxs = df.index[combined].tolist()
                hits5 = 0; tot5 = 0
                for idx in idxs:
                    acct = df.iloc[idx]['account']
                    w = df.iloc[idx+1:idx+6]
                    if len(w) > 0 and w.iloc[0].get('account','') == acct:
                        hits5 += int(w[triple_col].any())
                        tot5 += 1

                if tot5 > 0:
                    rate5 = hits5 / tot5
                    bl5 = 1 - (1 - baseline)**5
                    ratio5 = rate5 / bl5 if bl5 > 0 else 0
                    combos.append({
                        'combo': f'{sa_col}>={thresh} + {cond_name}',
                        'n': n_comb, 'hits': hits5, 'total': tot5,
                        'rate': rate5, 'ratio': ratio5
                    })

    if combos:
        combo_df = pd.DataFrame(combos).sort_values('ratio', ascending=False)
        text8 += f"{'Combo':>45s} | {'n':>5s} {'hits':>5s} {'rate%':>7s} {'ratio':>6s}\n"
        text8 += "-" * 80 + "\n"
        for _, r in combo_df.head(25).iterrows():
            sig = '***' if r['ratio'] > 1.3 else ''
            text8 += f"{r['combo']:>45s} | {r['n']:5d} {r['hits']:5d} {r['rate']*100:7.3f} {r['ratio']:6.2f}x {sig}\n"

    rpt(f"8. COMBINED CONDITIONS (multi-factor)", text8)

    # ══════════════════════════════════════════
    # VISUALIZATIONS
    # ══════════════════════════════════════════
    fig, axes = plt.subplots(3, 2, figsize=(16, 18))

    # Viz 1: symbol frequency deviation by position (heatmap)
    sym_dev = np.zeros((len(SYMS), W))
    for si, sym in enumerate(SYMS):
        for pi, pos in enumerate(range(-W, 0)):
            pre_r = (all_pre[(all_pre['pos']==pos)]['reel_1']==sym).mean() + \
                    (all_pre[(all_pre['pos']==pos)]['reel_2']==sym).mean() + \
                    (all_pre[(all_pre['pos']==pos)]['reel_3']==sym).mean()
            ctrl_r = 0
            if len(all_ctrl) > 0:
                ctrl_r = (all_ctrl[(all_ctrl['pos']==pos)]['reel_1']==sym).mean() + \
                         (all_ctrl[(all_ctrl['pos']==pos)]['reel_2']==sym).mean() + \
                         (all_ctrl[(all_ctrl['pos']==pos)]['reel_3']==sym).mean()
            sym_dev[si, pi] = (pre_r - ctrl_r) if ctrl_r > 0 else 0

    sns.heatmap(sym_dev, ax=axes[0,0], cmap='RdBu_r', center=0,
                xticklabels=[str(p) for p in range(-W,0)],
                yticklabels=SYMS, annot=False)
    axes[0,0].set_title(f'Symbol Freq Deviation (pre-{label} vs control)\nby position')
    axes[0,0].set_xlabel('Position'); axes[0,0].set_ylabel('Symbol')

    # Viz 2: reel index trajectory
    for col, color in [('r1_idx','blue'), ('r2_idx','green'), ('r3_idx','red')]:
        pre_means = [all_pre[all_pre['pos']==p][col].mean() for p in range(-W,0)]
        ctrl_means = [all_ctrl[all_ctrl['pos']==p][col].mean() for p in range(-W,0)] if len(all_ctrl) > 0 else [0]*W
        axes[0,1].plot(range(-W,0), pre_means, 'o-', color=color, markersize=3, label=f'pre-{label} {col}')
        axes[0,1].plot(range(-W,0), ctrl_means, 's--', color=color, markersize=2, alpha=0.4, label=f'control {col}')
    if target_idx is not None:
        axes[0,1].axhline(y=target_idx, color='black', linestyle=':', label=f'Target idx={target_idx}')
    axes[0,1].set_title(f'Reel Index Trajectory Before {label} Triple')
    axes[0,1].set_xlabel('Position'); axes[0,1].set_ylabel('Mean Index')
    axes[0,1].legend(fontsize=6, ncol=2)

    # Viz 3: pair/near-miss rate by position
    pre_pair_rates = [(all_pre[all_pre['pos']==p]['n_match']>=2).mean() for p in range(-W,0)]
    ctrl_pair_rates = [(all_ctrl[all_ctrl['pos']==p]['n_match']>=2).mean() for p in range(-W,0)] if len(all_ctrl) > 0 else [0]*W
    pre_tgt_rates = [((all_pre[all_pre['pos']==p]['n_match']>=2) & (all_pre[all_pre['pos']==p]['pair_sym']==target_sym)).mean() for p in range(-W,0)]
    ctrl_tgt_rates = [((all_ctrl[all_ctrl['pos']==p]['n_match']>=2) & (all_ctrl[all_ctrl['pos']==p]['pair_sym']==target_sym)).mean() for p in range(-W,0)] if len(all_ctrl) > 0 else [0]*W

    axes[1,0].plot(range(-W,0), pre_pair_rates, 'o-', color='steelblue', label=f'Pre-{label} any pair')
    axes[1,0].plot(range(-W,0), ctrl_pair_rates, 's--', color='steelblue', alpha=0.4, label='Control any pair')
    axes[1,0].plot(range(-W,0), pre_tgt_rates, 'o-', color='tomato', label=f'Pre-{label} {target_sym} pair')
    axes[1,0].plot(range(-W,0), ctrl_tgt_rates, 's--', color='tomato', alpha=0.4, label=f'Control {target_sym} pair')
    axes[1,0].set_title(f'Pair Rate by Position Before {label}')
    axes[1,0].set_xlabel('Position'); axes[1,0].set_ylabel('Rate')
    axes[1,0].legend(fontsize=7)

    # Viz 4: top conditional predictors
    if len(crdf) > 0:
        top15 = crdf.nlargest(15, 'r5')
        axes[1,1].barh(range(len(top15)), top15['r5'].values, color='steelblue')
        axes[1,1].set_yticks(range(len(top15)))
        axes[1,1].set_yticklabels(top15['cond'].values, fontsize=7)
        axes[1,1].axvline(x=1.0, color='red', linestyle='--')
        axes[1,1].set_title(f'Top Predictors: P({label} in next 5) ratio')
        axes[1,1].set_xlabel('Ratio vs baseline')

    # Viz 5: N-1 reel config distribution
    if len(prev_spins) > 0:
        prev_results = prev_spins['spin_result'].value_counts(normalize=True)
        ctrl_results = ctrl_prev['spin_result'].value_counts(normalize=True) if len(ctrl_prev) > 0 else pd.Series()
        x_labels = sorted(df['spin_result'].unique())
        pre_vals = [prev_results.get(r, 0) for r in x_labels]
        ctrl_vals = [ctrl_results.get(r, 0) for r in x_labels]
        x = np.arange(len(x_labels))
        axes[2,0].bar(x - 0.15, pre_vals, 0.3, label=f'Pre-{label}', color='tomato')
        axes[2,0].bar(x + 0.15, ctrl_vals, 0.3, label='Control', color='steelblue')
        axes[2,0].set_xticks(x)
        axes[2,0].set_xticklabels(x_labels, rotation=45)
        axes[2,0].set_title(f'Spin Result on N-1 (Pre-{label} vs Control)')
        axes[2,0].set_ylabel('Frequency'); axes[2,0].legend()

    # Viz 6: combined conditions
    if combos:
        combo_df_top = combo_df.head(15)
        axes[2,1].barh(range(len(combo_df_top)), combo_df_top['ratio'].values, color='seagreen')
        axes[2,1].set_yticks(range(len(combo_df_top)))
        axes[2,1].set_yticklabels(combo_df_top['combo'].values, fontsize=6)
        axes[2,1].axvline(x=1.0, color='red', linestyle='--')
        axes[2,1].set_title(f'Combined Conditions: {label} in next 5 ratio')
        axes[2,1].set_xlabel('Ratio vs baseline')

    plt.suptitle(f'DEEP SEQUENCE & TRANSITION: {label} TRIPLES', fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(os.path.join(OUT, f'{label}_DEEP.png'), dpi=150)
    plt.close()

    # Write report
    header = f"\n{'#'*75}\n  DEEP SEQUENCE & TRANSITION: {label} TRIPLES\n"
    header += f"  {n_win} triples | {n_ctrl} controls | Window = {W} spins\n{'#'*75}\n"
    full = header + "\n".join(R)
    path = os.path.join(OUT, f'{label}_DEEP_REPORT.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(full)
    print(f"  -> {path}")
    print(f"  -> {label}_DEEP.png")


# ══════════════════════════════════
# RUN BOTH
# ══════════════════════════════════
deep_analysis(df, 'is_acc', 'ACC', 'accumulation', 'sa_acc')
deep_analysis(df, 'is_spn', 'SPN', 'spins', 'sa_spn')

print("\nALL DONE!")
