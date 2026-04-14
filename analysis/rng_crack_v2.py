"""
RNG Crack V2: Deep dive on the two real signals from V1:
  1. VT gaps are more regular than random (CV=0.803)
  2. Bet-change correlation (1.75x within 1 spin)

New tests:
  A. Gap-position VT probability curve (hazard rate)
  B. Pre-VT fingerprint: what do the last 5 spins before VT look like?
  C. Bet-change deconfounding: is it the strategy or the RNG?
  D. Per-account gap analysis
  E. VT prediction model: can we combine gap position + features for exact timing?
  F. Conditional gap distribution: does VT type affect next gap?
"""
import pandas as pd
import numpy as np
import os, glob, sys
from collections import Counter, defaultdict

REEL_TEXT_TO_IDX = {
    'attack': 0, 'coin': 1, 'shield': 2, 'goldSack': 3,
    'steal': 4, 'coin2': 5, 'spins': 6, 'goldSack2': 7,
    'accumulation': 8,
}
SYM_SHORT = {0: 'ATK', 1: 'CON', 2: 'SHD', 3: 'GLD', 4: 'STL', 5: 'CON2', 6: 'SPN', 7: 'GLD2', 8: 'ACC'}
VT_SYMS = {6, 8}

SKIP_DUPES = {
    'spin_history_2026-04-04 (1).csv',
    'spin_history_2026-04-06 (1).csv',
    'spin_history_2026-04-05 (2).csv',
    'spin_history_Ahmed_2026-04-08 (1).csv',
    'spin_history_Nick_2026-04-08 (1).csv',
}

def load_all_data():
    base = os.path.join(os.path.dirname(__file__), '..', 'data')
    frames = []
    for account in ['Islam', 'Ahmed', 'Nick']:
        acct_dir = os.path.join(base, account)
        if not os.path.isdir(acct_dir): continue
        for f in sorted(glob.glob(os.path.join(acct_dir, 'spin_history*.csv'))):
            basename = os.path.basename(f)
            if basename in SKIP_DUPES:
                continue
            try:
                df = pd.read_csv(f, on_bad_lines='skip')
                if 'is_triple' not in df.columns or 'r1' not in df.columns:
                    continue

                keep_cols = ['r1', 'r2', 'r3', 'is_triple']
                if 'reel_1' in df.columns:
                    df['r1_idx'] = df['reel_1'].map(REEL_TEXT_TO_IDX)
                    df['r2_idx'] = df['reel_2'].map(REEL_TEXT_TO_IDX)
                    df['r3_idx'] = df['reel_3'].map(REEL_TEXT_TO_IDX)
                    keep_cols += ['r1_idx', 'r2_idx', 'r3_idx']
                elif 'r1_idx' in df.columns:
                    keep_cols += ['r1_idx', 'r2_idx', 'r3_idx']

                for col in ['bet_multiplier', 'bet_level', 'sa_spins', 'sa_spn',
                            'sa_acc', 'accum_delta', 'accum_pct', 'seq',
                            'spin_result', 'reward_code', 'sa_atk', 'sa_stl', 'sa_shd']:
                    if col in df.columns:
                        keep_cols.append(col)

                df['is_triple'] = df['is_triple'].astype(str).str.lower().isin(['true', '1'])
                df['account'] = account
                keep_cols.append('account')

                subset = df[[c for c in keep_cols if c in df.columns]].copy()
                subset = subset.dropna(subset=['r1', 'r2', 'r3'])
                for c in ['r1', 'r2', 'r3']:
                    subset[c] = subset[c].astype(int)

                if 'r1_idx' in subset.columns:
                    subset = subset.dropna(subset=['r1_idx', 'r2_idx', 'r3_idx'])
                    for c in ['r1_idx', 'r2_idx', 'r3_idx']:
                        subset[c] = subset[c].astype(int)
                    subset['is_valuable'] = subset['is_triple'] & subset['r1_idx'].isin(VT_SYMS)
                else:
                    subset['is_valuable'] = False

                frames.append(subset)
            except Exception as e:
                print(f"  Skip {basename}: {e}", file=sys.stderr)

    big = pd.concat(frames, ignore_index=True)
    return big


def test_A_hazard_rate(df):
    """The hazard rate: P(VT on this spin | last VT was G spins ago).
    If players can time VTs, this curve should show a clear ramp-up."""
    print("=" * 70)
    print("TEST A: VT HAZARD RATE (P(VT | gap position))")
    print("=" * 70)

    vt = df['is_valuable'].values
    n = len(vt)

    # Compute gap position for each spin
    gap_pos = np.zeros(n, dtype=int)
    counter = 0
    for i in range(n):
        gap_pos[i] = counter
        if vt[i]:
            counter = 0
        else:
            counter += 1

    base_rate = vt.mean()
    print(f"\n  Base VT rate: {base_rate*100:.2f}%")
    print(f"\n  Hazard rate by gap position (spins since last VT):")
    print(f"  {'Gap pos':>10} {'VT rate':>10} {'N spins':>10} {'Lift':>8} {'Cumul P':>10}")

    cum_prob = 0
    for g in range(0, 201):
        mask = gap_pos == g
        n_at_g = mask.sum()
        if n_at_g < 20:
            continue
        rate = vt[mask].mean()
        lift = rate / base_rate if base_rate > 0 else 0
        # Cumulative probability of VT by gap position g
        cum_prob = 1 - (1 - cum_prob) * (1 - rate)

        flag = ""
        if lift > 1.5:
            flag = " ** HIGH"
        elif lift < 0.5:
            flag = " ** LOW"

        if g <= 80 or g % 10 == 0 or flag:
            print(f"  {g:>10} {rate*100:>9.2f}% {n_at_g:>10} {lift:>7.2f}x {cum_prob*100:>9.1f}%{flag}")

    # The KEY question: at what gap position does the hazard rate
    # consistently exceed the base rate?
    print(f"\n  Hazard rate summary by zone:")
    zones = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
             (50, 60), (60, 70), (70, 80), (80, 100), (100, 150), (150, 200)]
    for lo, hi in zones:
        mask = (gap_pos >= lo) & (gap_pos < hi)
        n_zone = mask.sum()
        if n_zone > 0:
            rate = vt[mask].mean()
            lift = rate / base_rate
            flag = " ** BET HIGH" if lift > 1.3 else (" ** BET LOW" if lift < 0.7 else "")
            print(f"    gap [{lo:3d}-{hi:3d}): {rate*100:.2f}% ({n_zone} spins, {lift:.2f}x){flag}")


def test_B_prevt_fingerprint(df):
    """What do the last 5 spins before each VT look like?
    Is there a visual/reel fingerprint that players recognize?"""
    print("\n" + "=" * 70)
    print("TEST B: PRE-VT FINGERPRINT (last 5 spins before VT)")
    print("=" * 70)

    if 'r1_idx' not in df.columns:
        print("  No r1_idx column")
        return

    vt = df['is_valuable'].values
    r1i = df['r1_idx'].values
    r2i = df['r2_idx'].values
    r3i = df['r3_idx'].values
    is_triple = df['is_triple'].values
    base_rate = vt.mean()

    vt_indices = np.where(vt)[0]
    non_vt_indices = np.where(~vt)[0]

    # For each lookback position (-1 to -5), count symbol frequencies
    # before VT vs before non-VT
    print(f"\n  Symbol frequency on reel 1 at position N before VT (vs random):")
    for lookback in range(1, 6):
        print(f"\n  === {lookback} spin(s) before VT ===")
        valid_vt = vt_indices[vt_indices >= lookback]
        prev_idx = valid_vt - lookback

        # Symbol distribution before VT
        vt_syms = Counter(r1i[prev_idx])
        total_vt = len(prev_idx)

        # Overall symbol distribution
        overall = Counter(r1i)
        total_all = len(r1i)

        for sym in sorted(set(list(vt_syms.keys()) + list(overall.keys()))):
            vt_pct = vt_syms.get(sym, 0) / total_vt * 100
            all_pct = overall.get(sym, 0) / total_all * 100
            ratio = vt_pct / all_pct if all_pct > 0 else 0
            sym_name = SYM_SHORT.get(sym, '?')
            flag = " ***" if abs(ratio - 1) > 0.3 else ""
            print(f"    {sym_name}: {vt_pct:.1f}% before VT vs {all_pct:.1f}% overall (ratio {ratio:.2f}){flag}")

    # Triple rate in the N spins before VT
    print(f"\n  ANY triple rate in N spins before VT (vs overall {is_triple.mean()*100:.1f}%):")
    for lookback in range(1, 11):
        valid_vt = vt_indices[vt_indices >= lookback]
        prev_idx = valid_vt - lookback
        trip_rate = is_triple[prev_idx].mean()
        overall_trip = is_triple.mean()
        ratio = trip_rate / overall_trip
        print(f"    {lookback} before VT: {trip_rate*100:.1f}% (ratio {ratio:.2f})")

    # VT symbol visibility before VT:
    # How often does the VT symbol (SPN=6 or ACC=8) appear on ANY reel
    # in the spins leading up to VT?
    print(f"\n  VT symbol visibility before VT (SPN or ACC on any reel):")
    for lookback in range(1, 6):
        valid_vt = vt_indices[vt_indices >= lookback]
        prev_idx = valid_vt - lookback

        # Count how many pre-VT spins have a VT symbol on any reel
        has_vt_sym = np.isin(r1i[prev_idx], list(VT_SYMS)) | \
                     np.isin(r2i[prev_idx], list(VT_SYMS)) | \
                     np.isin(r3i[prev_idx], list(VT_SYMS))
        vt_vis_rate = has_vt_sym.mean()

        # Compare to overall
        has_vt_sym_all = np.isin(r1i, list(VT_SYMS)) | \
                         np.isin(r2i, list(VT_SYMS)) | \
                         np.isin(r3i, list(VT_SYMS))
        overall_vis = has_vt_sym_all.mean()

        ratio = vt_vis_rate / overall_vis
        print(f"    {lookback} before VT: {vt_vis_rate*100:.1f}% vs {overall_vis*100:.1f}% overall (ratio {ratio:.2f})")

    # The big one: what is the EXACT pattern of the 3 spins before VT?
    print(f"\n  Most common 3-spin patterns before VT (r1_idx sequence):")
    if len(vt_indices) > 0:
        valid = vt_indices[vt_indices >= 3]
        patterns = []
        for idx in valid:
            p = tuple(r1i[idx-3:idx])
            patterns.append(p)
        pattern_counts = Counter(patterns)
        total_patterns = len(patterns)
        for pat, cnt in pattern_counts.most_common(20):
            pct = cnt / total_patterns * 100
            sym_names = [SYM_SHORT.get(s, '?') for s in pat]
            print(f"    {' -> '.join(sym_names)}: {cnt} ({pct:.1f}%)")


def test_C_bet_change_deconfound(df):
    """Is the bet-change VT correlation real or just because bet changes
    correlate with high sa_spins (session depth)?"""
    print("\n" + "=" * 70)
    print("TEST C: BET CHANGE DECONFOUNDING")
    print("=" * 70)

    if 'bet_multiplier' not in df.columns:
        print("  No bet_multiplier column")
        return

    bm = df['bet_multiplier'].values.astype(float)
    vt = df['is_valuable'].values
    base_rate = vt.mean()

    # Detect bet changes
    bet_changed = np.zeros(len(df), dtype=bool)
    bet_changed[1:] = bm[1:] != bm[:-1]

    # Also compute gap position
    gap_pos = np.zeros(len(df), dtype=int)
    counter = 0
    for i in range(len(df)):
        gap_pos[i] = counter
        if vt[i]:
            counter = 0
        else:
            counter += 1

    # Stratified analysis: bet change effect WITHIN gap position bands
    print(f"\n  Bet change effect stratified by gap position:")
    for lo, hi in [(0, 30), (30, 50), (50, 80), (80, 200)]:
        in_band = (gap_pos >= lo) & (gap_pos < hi)

        changed_in_band = in_band & bet_changed
        unchanged_in_band = in_band & ~bet_changed

        n_changed = changed_in_band.sum()
        n_unchanged = unchanged_in_band.sum()

        if n_changed >= 10 and n_unchanged >= 10:
            vt_changed = vt[changed_in_band].mean()
            vt_unchanged = vt[unchanged_in_band].mean()
            band_rate = vt[in_band].mean()
            print(f"    Gap [{lo:3d}-{hi:3d}): changed {vt_changed*100:.2f}% ({n_changed}) vs unchanged {vt_unchanged*100:.2f}% ({n_unchanged}), band avg {band_rate*100:.2f}%")

    # Session depth confounding
    if 'sa_spins' in df.columns:
        sa = df['sa_spins'].values.astype(float)
        print(f"\n  Session depth at bet change vs no change:")
        print(f"    Changed:   mean sa_spins = {sa[bet_changed].mean():.0f}")
        print(f"    Unchanged: mean sa_spins = {sa[~bet_changed].mean():.0f}")

        # Stratify by sa_spins
        print(f"\n  Bet change effect stratified by session depth:")
        for lo, hi in [(0, 50), (50, 100), (100, 200), (200, 500)]:
            in_band = (sa >= lo) & (sa < hi)
            changed_in_band = in_band & bet_changed
            unchanged_in_band = in_band & ~bet_changed
            n_changed = changed_in_band.sum()
            n_unchanged = unchanged_in_band.sum()
            if n_changed >= 10 and n_unchanged >= 10:
                vt_changed = vt[changed_in_band].mean()
                vt_unchanged = vt[unchanged_in_band].mean()
                print(f"    sa [{lo:3d}-{hi:3d}): changed {vt_changed*100:.2f}% ({n_changed}) vs unchanged {vt_unchanged*100:.2f}% ({n_unchanged})")


def test_D_per_account_gaps(df):
    """Gap analysis per account to check consistency."""
    print("\n" + "=" * 70)
    print("TEST D: PER-ACCOUNT GAP ANALYSIS")
    print("=" * 70)

    vt = df['is_valuable'].values

    for acct in sorted(df['account'].unique()):
        mask = df['account'] == acct
        acct_vt = vt[mask]
        n = mask.sum()
        n_vt = acct_vt.sum()

        vt_indices = np.where(acct_vt)[0]
        if len(vt_indices) < 5:
            continue

        gaps = np.diff(vt_indices)
        base_rate = acct_vt.mean()

        print(f"\n  {acct}: {n} spins, {n_vt} VTs, rate {base_rate*100:.2f}%")
        print(f"    Gap mean: {gaps.mean():.1f}, median: {np.median(gaps):.1f}, std: {gaps.std():.1f}")
        print(f"    CV: {gaps.std()/gaps.mean():.3f} (random=1.0)")

        # Gap hazard rate by zone
        gap_pos = np.zeros(len(acct_vt), dtype=int)
        counter = 0
        for i in range(len(acct_vt)):
            gap_pos[i] = counter
            if acct_vt[i]:
                counter = 0
            else:
                counter += 1

        zones = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 120), (120, 200)]
        for lo, hi in zones:
            in_zone = (gap_pos >= lo) & (gap_pos < hi)
            n_zone = in_zone.sum()
            if n_zone > 0:
                rate = acct_vt[in_zone].mean()
                lift = rate / base_rate if base_rate > 0 else 0
                print(f"    gap [{lo:3d}-{hi:3d}): {rate*100:.2f}% ({n_zone} spins, {lift:.2f}x)")


def test_E_exact_timing_model(df):
    """Can we combine gap position + session depth + accum_delta to
    build a real-time VT countdown? Target: identify the 5% of spins
    that have the highest VT probability."""
    print("\n" + "=" * 70)
    print("TEST E: COMBINED VT PREDICTION MODEL")
    print("=" * 70)

    vt = df['is_valuable'].values
    base_rate = vt.mean()
    n = len(vt)

    # Compute gap position
    gap_pos = np.zeros(n, dtype=int)
    counter = 0
    for i in range(n):
        gap_pos[i] = counter
        if vt[i]:
            counter = 0
        else:
            counter += 1

    # Features
    features = {'gap_pos': gap_pos}

    if 'sa_spins' in df.columns:
        features['sa_spins'] = df['sa_spins'].values.astype(float)
    if 'accum_delta' in df.columns:
        ad = df['accum_delta'].values.astype(float)
        features['accum_delta_pos'] = (ad > 0).astype(int)
    if 'bet_multiplier' in df.columns:
        bm = df['bet_multiplier'].values.astype(float)
        bet_changed = np.zeros(n, dtype=int)
        bet_changed[1:] = (bm[1:] != bm[:-1]).astype(int)
        features['bet_changed'] = bet_changed

    # Simple rule-based model: combine the signals we know
    print(f"\n  Base VT rate: {base_rate*100:.2f}%")

    # Rule 1: Gap position > 40 (overdue)
    overdue = gap_pos >= 40
    print(f"\n  Rule: gap >= 40: {vt[overdue].mean()*100:.2f}% ({overdue.sum()} spins, {vt[overdue].mean()/base_rate:.2f}x)")

    # Rule 2: Gap position > 60
    overdue60 = gap_pos >= 60
    print(f"  Rule: gap >= 60: {vt[overdue60].mean()*100:.2f}% ({overdue60.sum()} spins, {vt[overdue60].mean()/base_rate:.2f}x)")

    # Rule 3: Gap > 80
    overdue80 = gap_pos >= 80
    print(f"  Rule: gap >= 80: {vt[overdue80].mean()*100:.2f}% ({overdue80.sum()} spins, {vt[overdue80].mean()/base_rate:.2f}x)")

    # Rule 4: Gap > 40 AND session depth > 100
    if 'sa_spins' in features:
        sa = features['sa_spins']
        combo1 = (gap_pos >= 40) & (sa >= 100)
        if combo1.sum() > 0:
            print(f"  Rule: gap >= 40 AND sa_spins >= 100: {vt[combo1].mean()*100:.2f}% ({combo1.sum()} spins, {vt[combo1].mean()/base_rate:.2f}x)")

        combo2 = (gap_pos >= 50) & (sa >= 150)
        if combo2.sum() > 0:
            print(f"  Rule: gap >= 50 AND sa_spins >= 150: {vt[combo2].mean()*100:.2f}% ({combo2.sum()} spins, {vt[combo2].mean()/base_rate:.2f}x)")

    # Rule 5: Gap > 40 AND accum_delta > 0
    if 'accum_delta_pos' in features:
        ad = features['accum_delta_pos']
        combo3 = (gap_pos >= 40) & (ad == 1)
        if combo3.sum() > 0:
            print(f"  Rule: gap >= 40 AND accum_delta > 0: {vt[combo3].mean()*100:.2f}% ({combo3.sum()} spins, {vt[combo3].mean()/base_rate:.2f}x)")

        combo4 = (gap_pos >= 30) & (ad == 1)
        if combo4.sum() > 0:
            print(f"  Rule: gap >= 30 AND accum_delta > 0: {vt[combo4].mean()*100:.2f}% ({combo4.sum()} spins, {vt[combo4].mean()/base_rate:.2f}x)")

    # Now the big question: what's the MAXIMUM VT rate achievable
    # on any identifiable subset of spins?
    print(f"\n  === GRID SEARCH: Best single-spin VT probability ===")
    print(f"  Searching gap x sa_spins x accum_delta combinations...\n")

    best_results = []
    gap_bins = [(0, 20), (20, 30), (30, 40), (40, 50), (50, 60),
                (60, 80), (80, 100), (100, 200)]

    if 'sa_spins' in features:
        sa = features['sa_spins']
        sa_bins = [(0, 50), (50, 100), (100, 150), (150, 200), (200, 500)]
    else:
        sa_bins = [(0, 99999)]
        sa = np.zeros(n)

    if 'accum_delta_pos' in features:
        ad = features['accum_delta_pos']
        ad_bins = [0, 1]
    else:
        ad_bins = [0]
        ad = np.zeros(n, dtype=int)

    for g_lo, g_hi in gap_bins:
        for s_lo, s_hi in sa_bins:
            for ad_val in ad_bins:
                mask = (gap_pos >= g_lo) & (gap_pos < g_hi) & \
                       (sa >= s_lo) & (sa < s_hi) & (ad == ad_val)
                n_mask = mask.sum()
                if n_mask >= 50:  # minimum sample
                    rate = vt[mask].mean()
                    lift = rate / base_rate
                    if lift > 2.0:
                        best_results.append({
                            'gap': f'{g_lo}-{g_hi}',
                            'sa': f'{s_lo}-{s_hi}',
                            'ad': ad_val,
                            'n': n_mask,
                            'rate': rate,
                            'lift': lift,
                            'vts': vt[mask].sum()
                        })

    best_results.sort(key=lambda x: -x['lift'])
    for r in best_results[:25]:
        print(f"    gap [{r['gap']:>7}] sa [{r['sa']:>7}] ad={r['ad']}: "
              f"{r['rate']*100:.1f}% ({r['n']:>5} spins, {r['lift']:.1f}x, {r['vts']:.0f} VTs)")


def test_F_gap_conditioning(df):
    """Does the previous VT's type (ACC vs SPN) or the previous gap length
    predict the current gap length? If so, gaps are not i.i.d."""
    print("\n" + "=" * 70)
    print("TEST F: GAP CONDITIONING (does VT type predict next gap?)")
    print("=" * 70)

    if 'r1_idx' not in df.columns:
        print("  No r1_idx column")
        return

    vt = df['is_valuable'].values
    r1i = df['r1_idx'].values

    vt_indices = np.where(vt)[0]
    gaps = np.diff(vt_indices)

    if len(gaps) < 10:
        print("  Too few gaps")
        return

    # VT type at the START of each gap (the VT that ended the previous gap)
    vt_types = []
    for i in range(len(vt_indices) - 1):
        sym = r1i[vt_indices[i]]
        vt_types.append(SYM_SHORT.get(sym, '?'))

    # Gap length by previous VT type
    print(f"\n  Gap length by previous VT type:")
    for sym_name in ['SPN', 'ACC']:
        matching_gaps = [g for g, t in zip(gaps, vt_types) if t == sym_name]
        if matching_gaps:
            arr = np.array(matching_gaps)
            print(f"    After {sym_name}: mean={arr.mean():.1f}, median={np.median(arr):.1f}, std={arr.std():.1f}, n={len(arr)}")

    # Gap autocorrelation: does gap N predict gap N+1?
    if len(gaps) >= 10:
        print(f"\n  Gap autocorrelation:")
        for lag in range(1, 6):
            if lag < len(gaps):
                corr = np.corrcoef(gaps[:-lag], gaps[lag:])[0, 1]
                print(f"    lag {lag}: r={corr:+.3f}")

    # Short gap after short gap? Long after long?
    print(f"\n  Gap transition patterns:")
    short_thresh = np.percentile(gaps, 33)
    long_thresh = np.percentile(gaps, 67)

    for prev_label, prev_lo, prev_hi in [('SHORT', 0, short_thresh),
                                           ('MED', short_thresh, long_thresh),
                                           ('LONG', long_thresh, 999)]:
        for next_label, next_lo, next_hi in [('SHORT', 0, short_thresh),
                                              ('MED', short_thresh, long_thresh),
                                              ('LONG', long_thresh, 999)]:
            count = 0
            for i in range(len(gaps) - 1):
                if prev_lo <= gaps[i] < prev_hi and next_lo <= gaps[i+1] < next_hi:
                    count += 1
            prev_total = sum(1 for i in range(len(gaps)-1) if prev_lo <= gaps[i] < prev_hi)
            if prev_total > 0:
                pct = count / prev_total * 100
                print(f"    {prev_label} -> {next_label}: {pct:.1f}% ({count}/{prev_total})")


def test_G_reel_behavior_before_vt(df):
    """Do reels show specific BEHAVIOR changes before VT?
    Like: does reel stickiness, near-miss rate, or symbol repetition
    increase in the 10 spins before a VT?"""
    print("\n" + "=" * 70)
    print("TEST G: REEL BEHAVIOR CHANGES BEFORE VT")
    print("=" * 70)

    if 'r1_idx' not in df.columns:
        print("  No r1_idx column")
        return

    vt = df['is_valuable'].values
    r1i = df['r1_idx'].values
    r2i = df['r2_idx'].values
    r3i = df['r3_idx'].values

    vt_indices = np.where(vt)[0]

    # For each pre-VT window, compute various features
    metrics = {
        'match_2of3': [],    # 2 of 3 reels match (near miss)
        'any_vt_sym': [],    # VT symbol visible on any reel
        'r1_repeat': [],     # r1 same as previous spin
        'unique_syms': [],   # number of unique symbols across 3 reels
    }
    # Same metrics for random positions
    metrics_random = {k: [] for k in metrics}

    for idx in vt_indices:
        if idx < 10:
            continue
        for lookback in range(1, 11):
            i = idx - lookback
            m2 = int(r1i[i] == r2i[i] or r1i[i] == r3i[i] or r2i[i] == r3i[i])
            av = int(r1i[i] in VT_SYMS or r2i[i] in VT_SYMS or r3i[i] in VT_SYMS)
            rr = int(r1i[i] == r1i[i-1]) if i > 0 else 0
            us = len({r1i[i], r2i[i], r3i[i]})

            metrics['match_2of3'].append((lookback, m2))
            metrics['any_vt_sym'].append((lookback, av))
            metrics['r1_repeat'].append((lookback, rr))
            metrics['unique_syms'].append((lookback, us))

    # Random control: pick random non-VT positions
    np.random.seed(42)
    random_indices = np.random.choice(np.where(~vt)[0], size=min(len(vt_indices), (~vt).sum()), replace=False)
    for idx in random_indices:
        if idx < 10:
            continue
        for lookback in range(1, 11):
            i = idx - lookback
            if i < 1:
                continue
            m2 = int(r1i[i] == r2i[i] or r1i[i] == r3i[i] or r2i[i] == r3i[i])
            av = int(r1i[i] in VT_SYMS or r2i[i] in VT_SYMS or r3i[i] in VT_SYMS)
            rr = int(r1i[i] == r1i[i-1])
            us = len({r1i[i], r2i[i], r3i[i]})

            metrics_random['match_2of3'].append((lookback, m2))
            metrics_random['any_vt_sym'].append((lookback, av))
            metrics_random['r1_repeat'].append((lookback, rr))
            metrics_random['unique_syms'].append((lookback, us))

    # Compare pre-VT vs random for each metric and lookback
    for metric_name in ['match_2of3', 'any_vt_sym', 'r1_repeat', 'unique_syms']:
        print(f"\n  {metric_name} before VT vs random:")
        for lb in range(1, 11):
            vt_vals = [v for l, v in metrics[metric_name] if l == lb]
            rand_vals = [v for l, v in metrics_random[metric_name] if l == lb]
            if vt_vals and rand_vals:
                vt_mean = np.mean(vt_vals)
                rand_mean = np.mean(rand_vals)
                ratio = vt_mean / rand_mean if rand_mean > 0 else 0
                flag = " ***" if abs(ratio - 1) > 0.15 else ""
                print(f"    -{lb}: VT={vt_mean:.3f} vs rand={rand_mean:.3f} (ratio {ratio:.2f}){flag}")


if __name__ == '__main__':
    print("Loading data...", file=sys.stderr)
    df = load_all_data()
    print(f"Total: {len(df)} spins, {df['is_valuable'].sum()} VTs", file=sys.stderr)

    test_A_hazard_rate(df)
    test_B_prevt_fingerprint(df)
    test_C_bet_change_deconfound(df)
    test_D_per_account_gaps(df)
    test_E_exact_timing_model(df)
    test_F_gap_conditioning(df)
    test_G_reel_behavior_before_vt(df)
