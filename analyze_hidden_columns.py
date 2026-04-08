"""
Deep analysis of under-explored columns in Coin Master spin data.
Target: (30,30,30) triple accumulation prediction.
Threshold: >2x predictive lift.
"""
import pandas as pd
import numpy as np
import json
import re
from collections import defaultdict, Counter

# ═══════════════════════════════════════════════════════════════════
# LOAD DATA
# ═══════════════════════════════════════════════════════════════════
FILES = {
    'Account 1': r'C:\Users\Islam\Downloads\Account 1 spin_history_2026-04-05.csv',
    'Account 2': r'C:\Users\Islam\Downloads\Account 2 spin_history_2026-04-04.csv',
}

dfs = {}
for name, path in FILES.items():
    df = pd.read_csv(path)
    df['is_acc_triple'] = (df.r1 == 30) & (df.r2 == 30) & (df.r3 == 30)
    df['is_acc_triple'] = df['is_acc_triple'].astype(int)
    dfs[name] = df

combined = pd.concat(dfs.values(), keys=dfs.keys(), names=['account','row_idx']).reset_index()

print("=" * 80)
print("HIDDEN COLUMN ANALYSIS — COIN MASTER SPIN DATA")
print("=" * 80)
print(f"Account 1: {len(dfs['Account 1'])} spins, {dfs['Account 1'].is_acc_triple.sum()} ACC triples")
print(f"Account 2: {len(dfs['Account 2'])} spins, {dfs['Account 2'].is_acc_triple.sum()} ACC triples")
total_spins = len(combined)
total_triples = combined.is_acc_triple.sum()
base_rate = total_triples / total_spins
print(f"Combined: {total_spins} spins, {total_triples} ACC triples")
print(f"Base rate: {base_rate:.6f} ({base_rate*100:.3f}%, or 1 in {1/base_rate:.1f})")

# ═══════════════════════════════════════════════════════════════════
# SECTION 1: EVENT_BARS — Parse tracker IDs, step sizes, positions
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 1: EVENT_BARS ANALYSIS")
print("=" * 80)

def parse_event_bars(eb_str):
    """Parse event_bars JSON. Returns dict of tracker_id -> (current, total, mission)"""
    if pd.isna(eb_str):
        return {}
    try:
        data = json.loads(eb_str)
    except:
        return {}
    result = {}
    for key, val in data.items():
        # Format: "3848/4500@m8"
        m = re.match(r'(\d+)\/(\d+)@m(\d+)', val)
        if m:
            result[key] = {
                'current': int(m.group(1)),
                'total': int(m.group(2)),
                'mission': int(m.group(3)),
            }
    return result

# Parse all event_bars across both accounts
for acct_name, df in dfs.items():
    df['eb_parsed'] = df['event_bars'].apply(parse_event_bars)

# Collect all tracker IDs
all_tracker_ids = set()
for df in dfs.values():
    for eb in df['eb_parsed']:
        all_tracker_ids.update(eb.keys())

print(f"\nUnique tracker IDs found: {sorted(all_tracker_ids)}")

# For each tracker, extract sequences and step sizes
for tracker_id in sorted(all_tracker_ids):
    print(f"\n--- Tracker: {tracker_id} ---")

    for acct_name, df in dfs.items():
        # Get rows where this tracker appears
        mask = df['eb_parsed'].apply(lambda x: tracker_id in x)
        tracker_rows = df[mask].copy()

        if len(tracker_rows) == 0:
            print(f"  {acct_name}: Not present")
            continue

        # Extract current/total/mission values
        tracker_rows['t_current'] = tracker_rows['eb_parsed'].apply(lambda x: x[tracker_id]['current'])
        tracker_rows['t_total'] = tracker_rows['eb_parsed'].apply(lambda x: x[tracker_id]['total'])
        tracker_rows['t_mission'] = tracker_rows['eb_parsed'].apply(lambda x: x[tracker_id]['mission'])

        print(f"  {acct_name}: {len(tracker_rows)} appearances")

        # Show mission/total transitions
        missions = tracker_rows[['t_current','t_total','t_mission']].drop_duplicates(subset=['t_total','t_mission'])
        for _, row in missions.iterrows():
            print(f"    Mission m{row.t_mission}: total={row.t_total}")

        # Compute step sizes (difference in current between consecutive appearances)
        tracker_rows['step'] = tracker_rows['t_current'].diff()

        # Handle mission transitions (where current resets)
        tracker_rows['mission_changed'] = tracker_rows['t_mission'].diff() != 0
        tracker_rows.loc[tracker_rows['mission_changed'], 'step'] = np.nan

        valid_steps = tracker_rows['step'].dropna()
        if len(valid_steps) > 0:
            step_counts = valid_steps.value_counts().head(15)
            print(f"    Step sizes (top 15): {dict(step_counts)}")
            print(f"    Step mean: {valid_steps.mean():.2f}, std: {valid_steps.std():.2f}")

            # Check if step sizes correlate with outcome tuple (r1,r2,r3)
            tr = tracker_rows[tracker_rows['step'].notna()].copy()
            tr['outcome'] = tr.apply(lambda r: (r.r1, r.r2, r.r3), axis=1)
            outcome_steps = tr.groupby('outcome')['step'].agg(['mean','std','count'])
            outcome_steps = outcome_steps[outcome_steps['count'] >= 3].sort_values('count', ascending=False)
            if len(outcome_steps) > 0:
                print(f"    Step by outcome (count>=3):")
                for idx, row in outcome_steps.head(10).iterrows():
                    print(f"      {idx}: mean={row['mean']:.1f}, std={row['std']:.1f}, n={int(row['count'])}")

            # Check: does step size vary or is it FIXED per outcome?
            if len(tr) > 5:
                zero_std_outcomes = outcome_steps[outcome_steps['std'] == 0]
                variable_outcomes = outcome_steps[outcome_steps['std'] > 0]
                print(f"    Fixed step per outcome: {len(zero_std_outcomes)}/{len(outcome_steps)} outcomes have std=0")

        # Check if tracker position predicts (30,30,30)
        # For all rows (not just tracker-present), interpolate tracker position
        # Look at: among rows where tracker appears, what's the ACC triple rate?
        triple_when_tracker = tracker_rows['is_acc_triple'].sum()
        triple_rate = triple_when_tracker / len(tracker_rows) if len(tracker_rows) > 0 else 0
        lift = triple_rate / base_rate if base_rate > 0 else 0
        print(f"    ACC triple rate when tracker present: {triple_rate:.4f} (lift: {lift:.2f}x)")

        # Check if current % total correlates
        tracker_rows['pct'] = tracker_rows['t_current'] / tracker_rows['t_total']
        tracker_rows['pct_bin'] = (tracker_rows['pct'] * 10).astype(int) / 10  # 10% bins
        for pct_bin, grp in tracker_rows.groupby('pct_bin'):
            if len(grp) >= 10:
                rate = grp.is_acc_triple.mean()
                l = rate / base_rate if base_rate > 0 else 0
                if l > 1.5 or l < 0.5:
                    print(f"    pct_bin {pct_bin:.1f}: rate={rate:.4f}, lift={l:.2f}x, n={len(grp)}")

# ═══════════════════════════════════════════════════════════════════
# Check: step size fixed per SPIN RESULT (not just outcome tuple)?
# ═══════════════════════════════════════════════════════════════════
print("\n--- Step Size vs Spin Result ---")
for tracker_id in sorted(all_tracker_ids):
    for acct_name, df in dfs.items():
        mask = df['eb_parsed'].apply(lambda x: tracker_id in x)
        tracker_rows = df[mask].copy()
        if len(tracker_rows) == 0:
            continue
        tracker_rows['t_current'] = tracker_rows['eb_parsed'].apply(lambda x: x[tracker_id]['current'])
        tracker_rows['t_total'] = tracker_rows['eb_parsed'].apply(lambda x: x[tracker_id]['total'])
        tracker_rows['t_mission'] = tracker_rows['eb_parsed'].apply(lambda x: x[tracker_id]['mission'])
        tracker_rows['step'] = tracker_rows['t_current'].diff()
        tracker_rows['mission_changed'] = tracker_rows['t_mission'].diff() != 0
        tracker_rows.loc[tracker_rows['mission_changed'], 'step'] = np.nan

        tr = tracker_rows[tracker_rows['step'].notna()].copy()
        if len(tr) == 0:
            continue

        # Now check: how many SPINS elapsed between tracker appearances?
        tr['spin_gap'] = tr.index.to_series().diff()

        # Check if step = spin_gap * some_constant
        tr['step_per_spin'] = tr['step'] / tr['spin_gap']
        valid = tr[(tr['spin_gap'] > 0) & tr['step_per_spin'].notna()]
        if len(valid) > 5:
            sps = valid['step_per_spin']
            print(f"  {tracker_id} ({acct_name}): step_per_spin mean={sps.mean():.4f}, std={sps.std():.4f}, "
                  f"min={sps.min():.4f}, max={sps.max():.4f}")
            # Check if step_per_spin is constant (i.e. tracker increments by bet_multiplier or similar)
            if sps.std() / sps.mean() < 0.01:
                print(f"    *** NEAR-CONSTANT step_per_spin = {sps.mean():.4f} ***")

# Check what outcome tuples trigger event_bars to appear (vs not appear)
print("\n--- What triggers event_bars to appear? ---")
for acct_name, df in dfs.items():
    has_eb = df['event_bars'].notna()
    no_eb = ~has_eb

    # Check if is_triple correlates
    triple_rate_with_eb = df[has_eb].is_triple.apply(lambda x: x if isinstance(x, bool) else str(x).lower() == 'true').mean()
    triple_rate_without_eb = df[no_eb].is_triple.apply(lambda x: x if isinstance(x, bool) else str(x).lower() == 'true').mean()
    print(f"  {acct_name}: is_triple rate WITH event_bars: {triple_rate_with_eb:.4f}, WITHOUT: {triple_rate_without_eb:.4f}")

    # Check which spin_results have event_bars
    result_eb_rate = df.groupby('spin_result')['event_bars'].apply(lambda x: x.notna().mean())
    print(f"    event_bars rate by spin_result: {dict(result_eb_rate)}")


# ═══════════════════════════════════════════════════════════════════
# SECTION 2: SA_ (SINCE ALL) COUNTERS
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 2: SA_ (SINCE-ALL) COUNTERS")
print("=" * 80)

sa_cols = ['sa_spins','sa_atk','sa_stl','sa_shd','sa_spn','sa_acc']
sa_3x_cols = ['sa_3x_atk','sa_3x_stl','sa_3x_shd']

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")

    # Detect resets: when value at row i < value at row i-1
    for col in sa_cols + sa_3x_cols:
        diffs = df[col].diff()
        resets = df[diffs < 0]
        if len(resets) > 0:
            print(f"  {col}: {len(resets)} resets detected")
            # Check if reset happens AT or NEAR (30,30,30)
            for idx in resets.index[:5]:
                # Look at context around reset
                context_start = max(0, idx - 2)
                context_end = min(len(df), idx + 3)
                ctx = df.iloc[context_start:context_end][['r1','r2','r3', col, 'is_acc_triple']]
                print(f"    Reset at index {idx}:")
                print(f"    {ctx.to_string()}")
                print()

    # sa_acc specifically: what value does it reach before (30,30,30)?
    acc_triples = df[df.is_acc_triple == 1]
    if len(acc_triples) > 0:
        sa_acc_at_triple = acc_triples['sa_acc']
        print(f"  sa_acc value AT (30,30,30): mean={sa_acc_at_triple.mean():.1f}, "
              f"median={sa_acc_at_triple.median():.1f}, std={sa_acc_at_triple.std():.1f}")
        print(f"    min={sa_acc_at_triple.min()}, max={sa_acc_at_triple.max()}")
        print(f"    Distribution: {dict(sa_acc_at_triple.describe())}")

        # One row BEFORE the triple
        before_idx = acc_triples.index - 1
        before_idx = before_idx[before_idx >= 0]
        sa_acc_before = df.loc[before_idx, 'sa_acc']
        print(f"  sa_acc BEFORE (30,30,30): mean={sa_acc_before.mean():.1f}, "
              f"median={sa_acc_before.median():.1f}")

# ═══════════════════════════════════════════════════════════════════
# SA_ACC value as predictor — bucket analysis
# ═══════════════════════════════════════════════════════════════════
print("\n--- sa_acc value as predictor of (30,30,30) on NEXT spin ---")
for acct_name, df in dfs.items():
    print(f"\n  {acct_name}:")
    df_copy = df.copy()
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)

    # Bucket sa_acc into ranges
    bins = [0, 5, 10, 15, 20, 30, 50, 75, 100, 150, 200, 500, 1000, 10000]
    df_copy['sa_acc_bin'] = pd.cut(df_copy['sa_acc'], bins=bins, right=False)

    for bin_label, grp in df_copy.groupby('sa_acc_bin', observed=True):
        if len(grp) >= 20:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    sa_acc in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

# ═══════════════════════════════════════════════════════════════════
# SA_ ratios as predictors
# ═══════════════════════════════════════════════════════════════════
print("\n--- SA_ ratios as predictors ---")
for acct_name, df in dfs.items():
    print(f"\n  {acct_name}:")
    df_copy = df.copy()
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)

    # Compute ratios
    for sa_col in ['sa_atk','sa_stl','sa_shd','sa_spn','sa_acc']:
        ratio_col = f'{sa_col}_ratio'
        df_copy[ratio_col] = df_copy[sa_col] / df_copy['sa_spins'].clip(lower=1)

    # Also sa_acc / sa_spins ratio binned
    df_copy['acc_ratio'] = df_copy['sa_acc'] / df_copy['sa_spins'].clip(lower=1)
    bins = [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 1.0]
    df_copy['acc_ratio_bin'] = pd.cut(df_copy['acc_ratio'], bins=bins, right=False)

    for bin_label, grp in df_copy.groupby('acc_ratio_bin', observed=True):
        if len(grp) >= 20:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    sa_acc/sa_spins in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")


# ═══════════════════════════════════════════════════════════════════
# SECTION 3: SA_3X_ (TRIPLE COUNTERS)
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 3: SA_3X_ (TRIPLE COUNTERS)")
print("=" * 80)

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")
    df_copy = df.copy()
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)

    for col in sa_3x_cols:
        print(f"\n  {col}:")
        print(f"    Range: {df_copy[col].min()} to {df_copy[col].max()}")
        print(f"    Mean: {df_copy[col].mean():.1f}")

        # Value at (30,30,30)
        at_triple = df_copy[df_copy.is_acc_triple == 1][col]
        print(f"    Value AT (30,30,30): mean={at_triple.mean():.1f}, median={at_triple.median():.1f}")

        # Bucket analysis for predicting NEXT spin
        val_range = df_copy[col].max() - df_copy[col].min()
        if val_range > 0:
            n_bins = min(15, int(val_range) + 1)
            bins = np.linspace(df_copy[col].min(), df_copy[col].max() + 1, n_bins + 1)
            df_copy[f'{col}_bin'] = pd.cut(df_copy[col], bins=bins, right=False)
            for bin_label, grp in df_copy.groupby(f'{col}_bin', observed=True):
                if len(grp) >= 15:
                    rate = grp.next_is_triple.mean()
                    lift = rate / base_rate if base_rate > 0 else 0
                    marker = " ***" if lift > 2 else ""
                    print(f"      {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

    # Cross-analysis: combination of sa_3x values
    print(f"\n  Combined sa_3x analysis:")
    df_copy['sa_3x_sum'] = df_copy[sa_3x_cols].sum(axis=1)
    bins = [0, 5, 10, 15, 20, 30, 50, 100, 200]
    df_copy['sa_3x_sum_bin'] = pd.cut(df_copy['sa_3x_sum'], bins=bins, right=False)
    for bin_label, grp in df_copy.groupby('sa_3x_sum_bin', observed=True):
        if len(grp) >= 15:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    sa_3x_sum in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

# ═══════════════════════════════════════════════════════════════════
# SECTION 4: SS_ (SINCE SESSION) COUNTERS
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 4: SS_ (SINCE-SESSION) COUNTERS")
print("=" * 80)

ss_cols = ['ss_spins','ss_atk','ss_stl','ss_shd','ss_spn','ss_acc']
ss_3x_cols = ['ss_3x_atk','ss_3x_stl','ss_3x_shd']

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")
    df_copy = df.copy()

    # Detect session boundaries: where ss_spins drops
    ss_diff = df_copy['ss_spins'].diff()
    session_starts = df_copy[ss_diff < 0].index.tolist()
    session_starts = [0] + session_starts  # first row is also a session start

    print(f"  Session boundaries detected: {len(session_starts)}")
    print(f"  ss_spins range: {df_copy.ss_spins.min()} to {df_copy.ss_spins.max()}")

    # Session lengths
    session_lengths = []
    for i in range(len(session_starts)):
        start = session_starts[i]
        end = session_starts[i+1] if i+1 < len(session_starts) else len(df_copy)
        session_lengths.append(end - start)

    sl = pd.Series(session_lengths)
    print(f"  Session lengths: mean={sl.mean():.1f}, median={sl.median():.1f}, "
          f"min={sl.min()}, max={sl.max()}")
    print(f"  Session length distribution: {dict(sl.describe())}")

    # Do sessions tend to END near (30,30,30)?
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)

    # For each session, check if it contains a (30,30,30)
    sessions_with_triple = 0
    for i in range(len(session_starts)):
        start = session_starts[i]
        end = session_starts[i+1] if i+1 < len(session_starts) else len(df_copy)
        session = df_copy.iloc[start:end]
        if session.is_acc_triple.sum() > 0:
            sessions_with_triple += 1

    print(f"  Sessions containing ACC triple: {sessions_with_triple}/{len(session_starts)} "
          f"({sessions_with_triple/len(session_starts)*100:.1f}%)")

    # ss_spins as predictor
    print(f"\n  ss_spins as predictor of NEXT (30,30,30):")
    bins = [0, 10, 25, 50, 100, 200, 500, 1000, 5000, 100000]
    df_copy['ss_spins_bin'] = pd.cut(df_copy['ss_spins'], bins=bins, right=False)
    for bin_label, grp in df_copy.groupby('ss_spins_bin', observed=True):
        if len(grp) >= 15:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    ss_spins in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

    # ss_acc as predictor
    print(f"\n  ss_acc as predictor of NEXT (30,30,30):")
    bins = [0, 5, 10, 20, 50, 100, 200, 500, 1000, 100000]
    df_copy['ss_acc_bin'] = pd.cut(df_copy['ss_acc'], bins=bins, right=False)
    for bin_label, grp in df_copy.groupby('ss_acc_bin', observed=True):
        if len(grp) >= 15:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    ss_acc in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

    # ss_acc / ss_spins ratio
    print(f"\n  ss_acc/ss_spins ratio as predictor:")
    df_copy['ss_acc_ratio'] = df_copy['ss_acc'] / df_copy['ss_spins'].clip(lower=1)
    bins = [0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0, 10.0]
    df_copy['ss_acc_ratio_bin'] = pd.cut(df_copy['ss_acc_ratio'], bins=bins, right=False)
    for bin_label, grp in df_copy.groupby('ss_acc_ratio_bin', observed=True):
        if len(grp) >= 15:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    ss_acc/ss_spins in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

    # Does position within session predict?
    print(f"\n  Position within session as predictor:")
    df_copy['session_id'] = 0
    for i, start in enumerate(session_starts):
        end = session_starts[i+1] if i+1 < len(session_starts) else len(df_copy)
        df_copy.iloc[start:end, df_copy.columns.get_loc('session_id')] = i

    df_copy['session_pos'] = df_copy.groupby('session_id').cumcount()
    df_copy['session_len'] = df_copy.groupby('session_id')['session_id'].transform('count')
    df_copy['session_pct'] = df_copy['session_pos'] / df_copy['session_len'].clip(lower=1)

    bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    df_copy['session_pct_bin'] = pd.cut(df_copy['session_pct'], bins=bins, right=True)
    for bin_label, grp in df_copy.groupby('session_pct_bin', observed=True):
        if len(grp) >= 15:
            rate = grp.is_acc_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    session_pct in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")


# ═══════════════════════════════════════════════════════════════════
# SECTION 5: SLOT2 (SECONDARY SLOT VALUES)
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 5: SLOT2 (SECONDARY SLOT VALUES)")
print("=" * 80)

slot2_cols = ['slot2_r1', 'slot2_r2', 'slot2_r3']

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")
    df_copy = df.copy()
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)

    # What values appear?
    for col in slot2_cols:
        vals = df_copy[col].dropna().unique()
        print(f"  {col}: {len(vals)} unique values: {list(vals)}")
        print(f"    Non-null: {df_copy[col].notna().sum()}/{len(df_copy)}")

    # How many slot2 reels are populated per spin?
    df_copy['slot2_count'] = df_copy[slot2_cols].notna().sum(axis=1)
    for count_val in [0, 1, 2, 3]:
        grp = df_copy[df_copy.slot2_count == count_val]
        if len(grp) > 0:
            rate = grp.is_acc_triple.mean()
            next_rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            next_lift = next_rate / base_rate if base_rate > 0 else 0
            print(f"  slot2_count={count_val}: n={len(grp)}, "
                  f"ACC rate={rate:.5f} (lift={lift:.2f}x), "
                  f"NEXT ACC rate={next_rate:.5f} (lift={next_lift:.2f}x)")

    # Do specific slot2 values predict (30,30,30)?
    for col in slot2_cols:
        for val in df_copy[col].dropna().unique():
            grp = df_copy[df_copy[col] == val]
            if len(grp) >= 10:
                rate = grp.is_acc_triple.mean()
                next_rate = grp.next_is_triple.mean()
                lift = rate / base_rate if base_rate > 0 else 0
                next_lift = next_rate / base_rate if base_rate > 0 else 0
                marker = " ***" if next_lift > 2 else ""
                print(f"  {col}='{val}': n={len(grp)}, "
                      f"ACC rate={rate:.5f} (lift={lift:.2f}x), "
                      f"NEXT ACC rate={next_rate:.5f} (lift={next_lift:.2f}x){marker}")

    # Check: does slot2 appear on the spin BEFORE (30,30,30)?
    triple_indices = df_copy[df_copy.is_acc_triple == 1].index
    before_triple = triple_indices - 1
    before_triple = before_triple[before_triple >= 0]

    before_slot2_rate = df_copy.loc[before_triple, 'slot2_count'].mean()
    overall_slot2_rate = df_copy['slot2_count'].mean()
    print(f"  Avg slot2_count BEFORE triple: {before_slot2_rate:.3f} vs overall: {overall_slot2_rate:.3f}")

    # Specific slot2 values before triple
    for col in slot2_cols:
        before_vals = df_copy.loc[before_triple, col].dropna()
        if len(before_vals) > 0:
            print(f"  {col} before triple: {dict(before_vals.value_counts())}")

    # Check correlation between slot2 and primary reels
    has_slot2 = df_copy[df_copy.slot2_count > 0]
    if len(has_slot2) > 10:
        # Does slot2 presence correlate with specific primary outcomes?
        primary_outcomes_with_slot2 = has_slot2.groupby(['r1','r2','r3']).size().sort_values(ascending=False).head(10)
        print(f"  Top primary outcomes when slot2 present:")
        for (r1,r2,r3), count in primary_outcomes_with_slot2.items():
            total_this_outcome = len(df_copy[(df_copy.r1==r1)&(df_copy.r2==r2)&(df_copy.r3==r3)])
            pct = count / total_this_outcome * 100 if total_this_outcome > 0 else 0
            print(f"    ({r1},{r2},{r3}): {count}/{total_this_outcome} ({pct:.1f}%)")


# ═══════════════════════════════════════════════════════════════════
# SECTION 6: GAE (GRAND ALLIANCE EVENT) DATA
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 6: GAE (GRAND ALLIANCE EVENT) DATA")
print("=" * 80)

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")
    df_copy = df.copy()
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)

    # gae_segment
    print(f"  gae_segment unique: {df_copy.gae_segment.dropna().unique()}")
    print(f"  gae_segment non-null: {df_copy.gae_segment.notna().sum()}/{len(df_copy)}")

    for seg in df_copy.gae_segment.dropna().unique():
        grp = df_copy[df_copy.gae_segment == seg]
        rate = grp.is_acc_triple.mean()
        next_rate = grp.next_is_triple.mean()
        lift = rate / base_rate if base_rate > 0 else 0
        marker = " ***" if lift > 2 else ""
        print(f"    '{seg}': n={len(grp)}, ACC rate={rate:.5f} (lift={lift:.2f}x), "
              f"NEXT ACC rate={next_rate:.5f}{marker}")

    # gae_last_mission
    gae_lm = df_copy.gae_last_mission.dropna().unique()
    print(f"  gae_last_mission: {df_copy.gae_last_mission.notna().sum()} non-null, values: {gae_lm}")

    # gae_grand_prize
    print(f"  gae_grand_prize unique: {df_copy.gae_grand_prize.dropna().unique()}")
    print(f"  gae_grand_prize range: {df_copy.gae_grand_prize.min()} to {df_copy.gae_grand_prize.max()}")

    # Does gae_grand_prize value predict ACC triple?
    bins = np.percentile(df_copy.gae_grand_prize.dropna(), [0, 20, 40, 60, 80, 100])
    bins = sorted(set(bins))
    if len(bins) > 1:
        df_copy['gae_gp_bin'] = pd.cut(df_copy.gae_grand_prize, bins=bins, right=True, include_lowest=True)
        for bin_label, grp in df_copy.groupby('gae_gp_bin', observed=True):
            if len(grp) >= 15:
                rate = grp.is_acc_triple.mean()
                next_rate = grp.next_is_triple.mean()
                lift = rate / base_rate if base_rate > 0 else 0
                next_lift = next_rate / base_rate if base_rate > 0 else 0
                marker = " ***" if next_lift > 2 else ""
                print(f"    gae_grand_prize in {bin_label}: n={len(grp)}, "
                      f"ACC rate={rate:.5f} (lift={lift:.2f}x), "
                      f"NEXT rate={next_rate:.5f} (lift={next_lift:.2f}x){marker}")

    # gae_segment presence vs absence
    has_gae = df_copy.gae_segment.notna()
    no_gae = ~has_gae
    if has_gae.sum() > 0 and no_gae.sum() > 0:
        rate_with = df_copy[has_gae].is_acc_triple.mean()
        rate_without = df_copy[no_gae].is_acc_triple.mean()
        print(f"  ACC triple rate WITH gae_segment: {rate_with:.5f} vs WITHOUT: {rate_without:.5f}")


# ═══════════════════════════════════════════════════════════════════
# SECTION 7: DEEP EVENT_BARS — DELTA ANALYSIS
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 7: EVENT_BARS — INTER-SPIN DELTA ANALYSIS")
print("=" * 80)
print("Checking: does each spin increment trackers, even when event_bars is empty?")
print("If so, event_bars only REPORTS periodically, and we can infer hidden state.")

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")

    for tracker_id in sorted(all_tracker_ids):
        mask = df['eb_parsed'].apply(lambda x: tracker_id in x)
        tracker_rows = df[mask].copy()

        if len(tracker_rows) < 10:
            continue

        tracker_rows['t_current'] = tracker_rows['eb_parsed'].apply(lambda x: x[tracker_id]['current'])
        tracker_rows['t_total'] = tracker_rows['eb_parsed'].apply(lambda x: x[tracker_id]['total'])
        tracker_rows['t_mission'] = tracker_rows['eb_parsed'].apply(lambda x: x[tracker_id]['mission'])

        # Compute delta / spin_gap to get per-spin increment
        tracker_rows['delta'] = tracker_rows['t_current'].diff()
        tracker_rows['spin_gap'] = tracker_rows.index.to_series().diff()
        tracker_rows['mission_changed'] = tracker_rows['t_mission'].diff() != 0

        valid = tracker_rows[
            (tracker_rows['delta'].notna()) &
            (~tracker_rows['mission_changed']) &
            (tracker_rows['spin_gap'] > 0)
        ].copy()

        if len(valid) < 5:
            continue

        valid['per_spin'] = valid['delta'] / valid['spin_gap']

        # Correlate with bet_multiplier
        valid['bet'] = df.loc[valid.index, 'bet_multiplier']

        # Group by bet_multiplier
        by_bet = valid.groupby('bet')['per_spin'].agg(['mean','std','count'])
        by_bet = by_bet[by_bet['count'] >= 3]

        if len(by_bet) > 0:
            print(f"\n  Tracker {tracker_id}: per-spin increment by bet_multiplier:")
            for bet, row in by_bet.iterrows():
                print(f"    bet={bet}: per_spin={row['mean']:.4f} (std={row['std']:.4f}, n={int(row['count'])})")

            # Check if per_spin = bet_multiplier
            if len(by_bet) > 1:
                corr = valid[['per_spin','bet']].corr().iloc[0,1]
                print(f"    Correlation(per_spin, bet_multiplier) = {corr:.4f}")

                # Check ratio
                valid['ratio'] = valid['per_spin'] / valid['bet']
                print(f"    per_spin/bet ratio: mean={valid['ratio'].mean():.4f}, std={valid['ratio'].std():.4f}")

        # Key question: does tracker position JUST BEFORE (30,30,30) show a pattern?
        # Interpolate tracker position for all rows
        df_copy = df.copy()
        df_copy['tracker_pos'] = np.nan
        df_copy.loc[mask, 'tracker_pos'] = tracker_rows['t_current']
        df_copy['tracker_pos'] = df_copy['tracker_pos'].interpolate(method='linear')

        # At ACC triple
        triple_mask = df_copy.is_acc_triple == 1
        if triple_mask.sum() > 0:
            pos_at_triple = df_copy.loc[triple_mask, 'tracker_pos'].dropna()
            total_at_triple = df.loc[mask, 'eb_parsed'].apply(lambda x: x[tracker_id]['total'])

            if len(pos_at_triple) > 0:
                # Normalize by total (use most common total)
                most_common_total = tracker_rows['t_total'].mode().iloc[0] if len(tracker_rows) > 0 else 1
                pct_at_triple = pos_at_triple / most_common_total
                print(f"    Tracker pct at ACC triple: mean={pct_at_triple.mean():.4f}, "
                      f"std={pct_at_triple.std():.4f}")


# ═══════════════════════════════════════════════════════════════════
# SECTION 8: SA_ACC RESET PATTERN — THE KEY QUESTION
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 8: SA_ACC RESET ANALYSIS — WHEN AND WHY?")
print("=" * 80)

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")
    df_copy = df.copy()

    sa_diff = df_copy['sa_acc'].diff()
    resets = df_copy[sa_diff < 0]

    if len(resets) == 0:
        print("  No sa_acc resets detected")
        # Check if sa_acc is monotonically increasing
        print(f"  sa_acc range: {df_copy.sa_acc.min()} to {df_copy.sa_acc.max()}")
        print(f"  sa_acc always increasing: {(sa_diff.dropna() >= 0).all()}")
        continue

    print(f"  sa_acc resets: {len(resets)}")
    for idx in resets.index:
        ctx_start = max(0, idx - 3)
        ctx_end = min(len(df_copy), idx + 3)
        ctx = df_copy.iloc[ctx_start:ctx_end][['seq','r1','r2','r3','sa_spins','sa_acc','is_acc_triple']]
        print(f"\n  Reset at index {idx}:")
        print(f"  {ctx.to_string()}")

    # CRITICAL: Does sa_acc reset immediately after (30,30,30)?
    print("\n  Does sa_acc reset AT (30,30,30)?")
    triples = df_copy[df_copy.is_acc_triple == 1].index.tolist()
    for t_idx in triples[:10]:
        if t_idx + 1 < len(df_copy):
            sa_at = df_copy.loc[t_idx, 'sa_acc']
            sa_after = df_copy.loc[t_idx + 1, 'sa_acc']
            reset = "RESET" if sa_after < sa_at else "no reset"
            print(f"    Triple at idx {t_idx}: sa_acc={sa_at} -> {sa_after} ({reset})")


# ═══════════════════════════════════════════════════════════════════
# SECTION 9: COMBINED MULTI-SIGNAL PREDICTOR
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 9: COMBINED MULTI-SIGNAL ANALYSIS")
print("=" * 80)

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")
    df_copy = df.copy()
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)

    # Features that might interact
    df_copy['has_event_bars'] = df_copy['event_bars'].notna().astype(int)
    df_copy['slot2_count'] = df_copy[slot2_cols].notna().sum(axis=1)
    df_copy['has_gae'] = df_copy['gae_segment'].notna().astype(int)
    df_copy['acc_ratio'] = df_copy['sa_acc'] / df_copy['sa_spins'].clip(lower=1)
    df_copy['ss_acc_ratio'] = df_copy['ss_acc'] / df_copy['ss_spins'].clip(lower=1)

    # Look for interactions
    # event_bars + high sa_acc
    sa_acc_median = df_copy.sa_acc.median()

    conditions = {
        'has_eb AND sa_acc > median': (df_copy.has_event_bars == 1) & (df_copy.sa_acc > sa_acc_median),
        'has_eb AND sa_acc <= median': (df_copy.has_event_bars == 1) & (df_copy.sa_acc <= sa_acc_median),
        'no_eb AND sa_acc > median': (df_copy.has_event_bars == 0) & (df_copy.sa_acc > sa_acc_median),
        'no_eb AND sa_acc <= median': (df_copy.has_event_bars == 0) & (df_copy.sa_acc <= sa_acc_median),
        'has_slot2 AND has_eb': (df_copy.slot2_count > 0) & (df_copy.has_event_bars == 1),
        'has_slot2 AND no_eb': (df_copy.slot2_count > 0) & (df_copy.has_event_bars == 0),
        'triple slot2 (all 3 filled)': df_copy.slot2_count == 3,
        'has_gae AND has_eb': (df_copy.has_gae == 1) & (df_copy.has_event_bars == 1),
    }

    for label, mask in conditions.items():
        grp = df_copy[mask]
        if len(grp) >= 10:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"  {label}: n={len(grp)}, next_triple_rate={rate:.5f}, lift={lift:.2f}x{marker}")

    # The REAL deep cut: what's happening in the rows immediately BEFORE (30,30,30)?
    print(f"\n  Features N spins BEFORE (30,30,30):")
    triples = df_copy[df_copy.is_acc_triple == 1].index.tolist()

    for lookback in [1, 2, 3, 5, 10]:
        before_indices = [t - lookback for t in triples if t - lookback >= 0]
        if len(before_indices) == 0:
            continue
        before = df_copy.loc[before_indices]

        eb_rate = before.has_event_bars.mean()
        slot2_rate = before.slot2_count.mean()
        sa_acc_val = before.sa_acc.mean()
        ss_acc_val = before.ss_acc.mean()

        overall_eb = df_copy.has_event_bars.mean()
        overall_slot2 = df_copy.slot2_count.mean()

        print(f"    {lookback} spin(s) before: event_bars={eb_rate:.3f} (vs {overall_eb:.3f}), "
              f"slot2_count={slot2_rate:.3f} (vs {overall_slot2:.3f}), "
              f"sa_acc={sa_acc_val:.1f}, ss_acc={ss_acc_val:.1f}")


# ═══════════════════════════════════════════════════════════════════
# SECTION 10: TRACKER APPEARANCE FREQUENCY AS PREDICTOR
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 10: EVENT_BARS DENSITY AS PREDICTOR")
print("=" * 80)
print("If event_bars appears every N spins, does N predict (30,30,30)?")

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")
    df_copy = df.copy()
    df_copy['has_eb'] = df_copy['event_bars'].notna().astype(int)
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)

    # Rolling density of event_bars in last N spins
    for window in [5, 10, 20, 50]:
        df_copy[f'eb_density_{window}'] = df_copy['has_eb'].rolling(window, min_periods=1).mean()

        bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
        col = f'eb_density_{window}'
        df_copy['density_bin'] = pd.cut(df_copy[col], bins=bins, right=True)

        has_signal = False
        for bin_label, grp in df_copy.groupby('density_bin', observed=True):
            if len(grp) >= 15:
                rate = grp.next_is_triple.mean()
                lift = rate / base_rate if base_rate > 0 else 0
                if lift > 2:
                    has_signal = True
                    print(f"  eb_density_{window} in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)} ***")

        if not has_signal:
            avg_lift = df_copy.groupby('density_bin', observed=True).apply(
                lambda g: g.next_is_triple.mean() / base_rate if len(g) >= 15 else np.nan
            ).dropna()
            if len(avg_lift) > 0:
                print(f"  eb_density_{window}: lifts range {avg_lift.min():.2f}x to {avg_lift.max():.2f}x (no >2x)")


# ═══════════════════════════════════════════════════════════════════
# SECTION 11: SA_ COUNTER DIFFERENTIALS (change rate)
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 11: SA_ COUNTER CHANGE RATES")
print("=" * 80)
print("Do counter ACCELERATION patterns predict (30,30,30)?")

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")
    df_copy = df.copy()
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)

    # sa_acc increments
    df_copy['sa_acc_delta'] = df_copy['sa_acc'].diff()

    # How many ACC outcomes in last N spins
    df_copy['acc_any'] = ((df_copy.r1 == 30) | (df_copy.r2 == 30) | (df_copy.r3 == 30)).astype(int)

    for window in [5, 10, 20]:
        df_copy[f'acc_density_{window}'] = df_copy['acc_any'].rolling(window, min_periods=1).mean()

        bins = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0]
        col = f'acc_density_{window}'
        df_copy['ad_bin'] = pd.cut(df_copy[col], bins=bins, right=True)

        print(f"\n  acc_density_{window} (any reel=30 in last {window} spins):")
        for bin_label, grp in df_copy.groupby('ad_bin', observed=True):
            if len(grp) >= 15:
                rate = grp.next_is_triple.mean()
                lift = rate / base_rate if base_rate > 0 else 0
                marker = " ***" if lift > 2 else ""
                print(f"    {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")


# ═══════════════════════════════════════════════════════════════════
# SECTION 12: SPINS SINCE LAST ACC TRIPLE (from sa_ and ss_)
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 12: SPINS SINCE LAST ACC TRIPLE — does drought predict?")
print("=" * 80)

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")
    df_copy = df.copy()
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)

    # Compute spins since last ACC triple manually
    last_triple = -1
    spins_since = []
    for i, row in df_copy.iterrows():
        if last_triple >= 0:
            spins_since.append(i - last_triple)
        else:
            spins_since.append(i + 1)  # unknown, use index
        if row.is_acc_triple == 1:
            last_triple = i

    df_copy['spins_since_last_acc'] = spins_since

    bins = [0, 10, 20, 30, 50, 75, 100, 150, 200, 500, 10000]
    df_copy['drought_bin'] = pd.cut(df_copy['spins_since_last_acc'], bins=bins, right=False)

    for bin_label, grp in df_copy.groupby('drought_bin', observed=True):
        if len(grp) >= 15:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"  drought in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")


# ═══════════════════════════════════════════════════════════════════
# SECTION 13: SS_ RESET DEEP DIVE
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("SECTION 13: SS_ RESET DEEP DIVE — What triggers session boundaries?")
print("=" * 80)

for acct_name, df in dfs.items():
    print(f"\n--- {acct_name} ---")
    df_copy = df.copy()

    # Detect ALL ss_ resets
    for col in ss_cols + ss_3x_cols:
        diffs = df_copy[col].diff()
        resets = df_copy[diffs < 0]
        if len(resets) > 0:
            print(f"  {col}: {len(resets)} resets")

    # Session boundaries = where ss_spins drops
    ss_diff = df_copy['ss_spins'].diff()
    session_boundaries = df_copy[ss_diff < 0].index.tolist()

    print(f"\n  Session boundaries (ss_spins drops): {len(session_boundaries)}")

    if len(session_boundaries) > 0:
        # What happens at session boundaries?
        print(f"  First 5 session boundaries:")
        for idx in session_boundaries[:5]:
            ctx_start = max(0, idx - 1)
            ctx_end = min(len(df_copy), idx + 2)
            ctx = df_copy.iloc[ctx_start:ctx_end][['seq','timestamp','r1','r2','r3','ss_spins','ss_acc','bet_multiplier']]
            print(f"\n    Boundary at index {idx}:")
            print(f"    {ctx.to_string()}")

        # Time gaps at session boundaries
        df_copy['ts'] = pd.to_datetime(df_copy['timestamp'])
        df_copy['time_gap'] = df_copy['ts'].diff().dt.total_seconds()

        boundary_gaps = df_copy.loc[session_boundaries, 'time_gap']
        non_boundary_gaps = df_copy.loc[~df_copy.index.isin(session_boundaries), 'time_gap'].dropna()

        print(f"\n  Time gap at session boundaries: mean={boundary_gaps.mean():.1f}s, "
              f"median={boundary_gaps.median():.1f}s")
        print(f"  Time gap at non-boundaries: mean={non_boundary_gaps.mean():.1f}s, "
              f"median={non_boundary_gaps.median():.1f}s")

        # Does bet_multiplier change at boundaries?
        df_copy['bet_changed'] = df_copy['bet_multiplier'].diff() != 0
        boundary_bet_change = df_copy.loc[session_boundaries, 'bet_changed'].mean()
        overall_bet_change = df_copy['bet_changed'].mean()
        print(f"\n  Bet change rate at boundaries: {boundary_bet_change:.3f} vs overall: {overall_bet_change:.3f}")

        # Does (30,30,30) appear disproportionately right after session boundary?
        first_n_after_boundary = []
        for boundary in session_boundaries:
            for offset in range(1, 11):  # first 10 spins
                if boundary + offset < len(df_copy):
                    first_n_after_boundary.append((offset, df_copy.iloc[boundary + offset].is_acc_triple))

        if first_n_after_boundary:
            after_df = pd.DataFrame(first_n_after_boundary, columns=['offset','is_triple'])
            for offset in range(1, 11):
                subset = after_df[after_df.offset == offset]
                if len(subset) > 0:
                    rate = subset.is_triple.mean()
                    lift = rate / base_rate if base_rate > 0 else 0
                    marker = " ***" if lift > 2 else ""
                    print(f"  Spin {offset} after session boundary: rate={rate:.5f}, lift={lift:.2f}x, n={len(subset)}{marker}")


# ═══════════════════════════════════════════════════════════════════
# FINAL SUMMARY: ALL SIGNALS WITH >2x LIFT
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINAL SUMMARY: COMPREHENSIVE SIGNAL SCAN")
print("=" * 80)
print(f"Base rate: {base_rate:.6f} (1 in {1/base_rate:.1f})")
print(f"Threshold: >2.0x lift with n>=15")
print()

# Re-scan all features systematically for lift > 2
all_signals = []

for acct_name, df in dfs.items():
    df_copy = df.copy()
    df_copy['next_is_triple'] = df_copy['is_acc_triple'].shift(-1).fillna(0).astype(int)
    df_copy['has_eb'] = df_copy['event_bars'].notna().astype(int)
    df_copy['slot2_count'] = df_copy[slot2_cols].notna().sum(axis=1)
    df_copy['acc_ratio'] = df_copy['sa_acc'] / df_copy['sa_spins'].clip(lower=1)
    df_copy['ss_acc_ratio'] = df_copy['ss_acc'] / df_copy['ss_spins'].clip(lower=1)
    df_copy['acc_any'] = ((df_copy.r1 == 30) | (df_copy.r2 == 30) | (df_copy.r3 == 30)).astype(int)

    for window in [5, 10, 20]:
        df_copy[f'acc_density_{window}'] = df_copy['acc_any'].rolling(window, min_periods=1).mean()
        df_copy[f'eb_density_{window}'] = df_copy['has_eb'].rolling(window, min_periods=1).mean()

    # All feature/bin combos
    feature_bins = {
        'sa_acc': [0, 5, 10, 15, 20, 30, 50, 75, 100, 150, 200, 500, 1000, 10000],
        'ss_acc': [0, 5, 10, 20, 50, 100, 200, 500, 1000, 100000],
        'sa_spins': [0, 10, 25, 50, 100, 200, 500, 1000, 5000, 100000],
        'ss_spins': [0, 10, 25, 50, 100, 200, 500, 1000, 5000, 100000],
        'acc_ratio': [0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 1.0],
        'ss_acc_ratio': [0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0, 10.0],
        'slot2_count': [-0.5, 0.5, 1.5, 2.5, 3.5],
        'has_eb': [-0.5, 0.5, 1.5],
        'acc_density_5': [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0],
        'acc_density_10': [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0],
        'acc_density_20': [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0],
    }

    for feat, bins in feature_bins.items():
        if feat not in df_copy.columns:
            continue
        df_copy['_bin'] = pd.cut(df_copy[feat], bins=bins, right=False)
        for bin_label, grp in df_copy.groupby('_bin', observed=True):
            if len(grp) >= 15:
                rate = grp.next_is_triple.mean()
                lift = rate / base_rate if base_rate > 0 else 0
                if lift > 2.0:
                    all_signals.append({
                        'account': acct_name,
                        'feature': feat,
                        'bin': str(bin_label),
                        'n': len(grp),
                        'rate': rate,
                        'lift': lift,
                    })

if all_signals:
    sig_df = pd.DataFrame(all_signals).sort_values('lift', ascending=False)
    print(f"\nFound {len(sig_df)} signals with >2x lift:\n")
    for _, row in sig_df.iterrows():
        print(f"  [{row.account}] {row.feature} in {row['bin']}: "
              f"lift={row.lift:.2f}x, rate={row.rate:.5f}, n={int(row.n)}")

    # Check cross-account consistency
    print("\n--- Cross-account consistency ---")
    features_with_signal = sig_df['feature'].unique()
    for feat in features_with_signal:
        feat_signals = sig_df[sig_df.feature == feat]
        accounts = feat_signals.account.unique()
        if len(accounts) > 1:
            print(f"  {feat}: Signal in BOTH accounts!")
            for _, row in feat_signals.iterrows():
                print(f"    [{row.account}] {row['bin']}: lift={row.lift:.2f}x, n={int(row.n)}")
        else:
            print(f"  {feat}: Signal only in {accounts[0]}")
else:
    print("\nNo signals found with >2x lift and n>=15")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
