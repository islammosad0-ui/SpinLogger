"""
VT Gap Predictor - Real-time prediction tool.

Given your last 1-2 gap lengths, predicts:
  - The window where the next VT will most likely land
  - Spin-by-spin probability curve
  - When to start betting high
  - When to go ALL IN (peak probability zone)

Also builds the empirical conditional distributions from all data
to back every prediction with hard numbers.
"""
import pandas as pd
import numpy as np
import os, glob, sys
from collections import defaultdict

REEL_TEXT_TO_IDX = {
    'attack': 0, 'coin': 1, 'shield': 2, 'goldSack': 3,
    'steal': 4, 'coin2': 5, 'spins': 6, 'goldSack2': 7,
    'accumulation': 8,
}
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
            if basename in SKIP_DUPES: continue
            try:
                df = pd.read_csv(f, on_bad_lines='skip')
                if 'is_triple' not in df.columns or 'r1' not in df.columns: continue
                if 'reel_1' in df.columns:
                    df['r1_idx'] = df['reel_1'].map(REEL_TEXT_TO_IDX)
                    df['r2_idx'] = df['reel_2'].map(REEL_TEXT_TO_IDX)
                    df['r3_idx'] = df['reel_3'].map(REEL_TEXT_TO_IDX)
                elif 'r1_idx' not in df.columns: continue
                df['is_triple'] = df['is_triple'].astype(str).str.lower().isin(['true', '1'])
                df = df.dropna(subset=['r1_idx', 'r2_idx', 'r3_idx'])
                df['r1_idx'] = df['r1_idx'].astype(int)
                df['is_valuable'] = df['is_triple'] & df['r1_idx'].isin(VT_SYMS)
                df['account'] = account
                frames.append(df)
            except: pass
    return pd.concat(frames, ignore_index=True)


def extract_gaps(df):
    vt = df['is_valuable'].values
    vt_idx = np.where(vt)[0]
    if len(vt_idx) < 2:
        return np.array([])
    return np.diff(vt_idx)


def classify_gap(g):
    """Classify gap into bins for 2-gap lookup."""
    if g <= 20: return 'VS'    # Very Short
    if g <= 35: return 'S'     # Short
    if g <= 55: return 'M'     # Medium
    if g <= 80: return 'L'     # Long
    return 'VL'                # Very Long


def build_prediction_tables(gaps):
    """Build empirical prediction tables from gap data."""

    # === TABLE 1: Single previous gap -> next gap distribution ===
    # Group by previous gap range, store all next gaps
    single_table = defaultdict(list)
    for i in range(len(gaps) - 1):
        single_table[classify_gap(gaps[i])].append(gaps[i+1])

    # Also build fine-grained (10-spin buckets)
    fine_table = defaultdict(list)
    for i in range(len(gaps) - 1):
        bucket = (gaps[i] // 10) * 10  # 0, 10, 20, ...
        fine_table[bucket].append(gaps[i+1])

    # === TABLE 2: Two previous gaps -> next gap distribution ===
    double_table = defaultdict(list)
    for i in range(len(gaps) - 2):
        key = (classify_gap(gaps[i]), classify_gap(gaps[i+1]))
        double_table[key].append(gaps[i+2])

    return single_table, fine_table, double_table


def predict(single_table, fine_table, double_table, prev_gap, prev_prev_gap=None):
    """Generate prediction for next gap given previous gap(s)."""

    # Use 2-gap table if available
    if prev_prev_gap is not None:
        key = (classify_gap(prev_prev_gap), classify_gap(prev_gap))
        if key in double_table and len(double_table[key]) >= 15:
            sample = np.array(double_table[key])
            source = f"2-gap lookup ({key[0]}->{key[1]}, n={len(sample)})"
        else:
            # Fall back to single
            sample = np.array(single_table[classify_gap(prev_gap)])
            source = f"1-gap lookup ({classify_gap(prev_gap)}, n={len(sample)})"
    else:
        # Try fine-grained first
        bucket = (prev_gap // 10) * 10
        if bucket in fine_table and len(fine_table[bucket]) >= 20:
            sample = np.array(fine_table[bucket])
            source = f"fine-grained ({bucket}-{bucket+10}, n={len(sample)})"
        else:
            sample = np.array(single_table[classify_gap(prev_gap)])
            source = f"1-gap lookup ({classify_gap(prev_gap)}, n={len(sample)})"

    return sample, source


def display_prediction(sample, source, prev_gap, prev_prev_gap=None):
    """Display a full prediction with window, probabilities, strategy."""

    mean_gap = sample.mean()
    median_gap = np.median(sample)
    p25 = np.percentile(sample, 25)
    p75 = np.percentile(sample, 75)
    p10 = np.percentile(sample, 10)
    p90 = np.percentile(sample, 90)

    header = f"Previous gap: {prev_gap}"
    if prev_prev_gap is not None:
        header += f" (before that: {prev_prev_gap})"

    print()
    print("=" * 70)
    print(f"  VT GAP PREDICTION")
    print(f"  {header}")
    print(f"  Source: {source}")
    print("=" * 70)

    print(f"\n  Expected next gap:")
    print(f"    Mean:   {mean_gap:.0f} spins")
    print(f"    Median: {median_gap:.0f} spins")
    print(f"    P25-P75 (50% window): spins {p25:.0f} - {p75:.0f}")
    print(f"    P10-P90 (80% window): spins {p10:.0f} - {p90:.0f}")

    # Spin-by-spin cumulative probability
    print(f"\n  Cumulative probability (VT should have hit by spin X):")
    print(f"  {'Spin':>6}  {'Cum %':>7}  {'Bar':40}  {'Action'}")
    print(f"  {'-'*70}")

    milestones = {}
    for spin in range(0, min(int(p90) + 40, 201), 1):
        cum_pct = (sample <= spin).mean() * 100

        # Track milestones
        for m in [25, 50, 75, 90]:
            if m not in milestones and cum_pct >= m:
                milestones[m] = spin

        # Display at intervals or milestones
        show = (spin <= 30 and spin % 5 == 0) or \
               (30 < spin <= 100 and spin % 10 == 0) or \
               (spin > 100 and spin % 20 == 0) or \
               spin == 1

        if not show:
            continue

        bar_len = int(cum_pct / 100 * 40)
        bar = '#' * bar_len + '.' * (40 - bar_len)

        # Determine action
        if cum_pct < 15:
            action = "BET LOW"
        elif cum_pct < 30:
            action = "watch..."
        elif cum_pct < 50:
            action = ">> BET MEDIUM"
        elif cum_pct < 75:
            action = ">>> BET HIGH"
        elif cum_pct < 90:
            action = ">>>> ALL IN ZONE"
        else:
            action = "OVERDUE - keep pushing"

        print(f"  {spin:>6}  {cum_pct:>6.1f}%  {bar}  {action}")

    # Key windows
    print(f"\n  === KEY WINDOWS ===")
    for m in [25, 50, 75, 90]:
        if m in milestones:
            print(f"    {m}% chance VT by spin: {milestones[m]}")

    # Hot zone: where the probability density is highest
    # (the 10-spin window with most VTs)
    best_start = 0
    best_count = 0
    for start in range(0, 200):
        count = ((sample >= start) & (sample < start + 10)).sum()
        if count > best_count:
            best_count = count
            best_start = start

    hot_pct = best_count / len(sample) * 100
    print(f"\n  === HOT ZONE (highest density 10-spin window) ===")
    print(f"    Spins {best_start} - {best_start + 10}: "
          f"{hot_pct:.1f}% of VTs land here ({best_count}/{len(sample)})")

    # 20-spin hot zone
    best_start_20 = 0
    best_count_20 = 0
    for start in range(0, 200):
        count = ((sample >= start) & (sample < start + 20)).sum()
        if count > best_count_20:
            best_count_20 = count
            best_start_20 = start

    hot_pct_20 = best_count_20 / len(sample) * 100
    print(f"    Spins {best_start_20} - {best_start_20 + 20}: "
          f"{hot_pct_20:.1f}% of VTs land here ({best_count_20}/{len(sample)})")

    # Strategy summary
    print(f"\n  === STRATEGY ===")
    if median_gap <= 30:
        print(f"    FAST REBOUND expected. VT likely within {int(p75)} spins.")
        print(f"    Start betting HIGH from spin 1.")
        print(f"    Peak zone: spins {best_start}-{best_start+10}.")
        if p75 <= 50:
            print(f"    If no VT by spin {int(p75)}, you're in the unlucky 25%.")
    elif median_gap <= 50:
        print(f"    NORMAL gap expected (~{int(median_gap)} spins).")
        print(f"    Bet low for first {int(p25)} spins.")
        print(f"    Switch to HIGH at spin {int(p25)}.")
        print(f"    Peak zone: spins {best_start}-{best_start+10}.")
    else:
        print(f"    LONG GAP expected (~{int(median_gap)} spins).")
        print(f"    Bet LOW until spin {int(p25)}.")
        print(f"    Switch to MEDIUM at spin {int(p25)}, HIGH at spin {int(median_gap) - 10}.")
        print(f"    If you reach spin {int(p75)} without VT, go ALL IN.")

    return {
        'mean': mean_gap,
        'median': median_gap,
        'p25': p25,
        'p75': p75,
        'p10': p10,
        'p90': p90,
        'hot_zone': (best_start, best_start + 10),
        'hot_zone_20': (best_start_20, best_start_20 + 20),
    }


def print_master_table(single_table, fine_table, double_table):
    """Print the complete reference table."""
    print("\n" + "=" * 70)
    print("  MASTER PREDICTION REFERENCE TABLE")
    print("=" * 70)

    # 1-gap table (fine grained)
    print(f"\n  === SINGLE GAP LOOKUP (previous gap -> prediction) ===\n")
    print(f"  {'Prev Gap':>12}  {'N':>5}  {'Mean':>6}  {'Median':>6}  {'P25':>5}  {'P75':>5}  {'Hot Zone':>12}")
    print(f"  {'-'*65}")

    for bucket in sorted(fine_table.keys()):
        sample = np.array(fine_table[bucket])
        if len(sample) < 10:
            continue
        mean = sample.mean()
        med = np.median(sample)
        p25 = np.percentile(sample, 25)
        p75 = np.percentile(sample, 75)

        best_s = 0
        best_c = 0
        for s in range(0, 200):
            c = ((sample >= s) & (sample < s + 10)).sum()
            if c > best_c: best_c, best_s = c, s

        print(f"  {bucket:>3}-{bucket+10:>3} spins  {len(sample):>5}  "
              f"{mean:>5.0f}   {med:>5.0f}   {p25:>4.0f}   {p75:>4.0f}   "
              f"spins {best_s}-{best_s+10}")

    # 2-gap table
    print(f"\n  === TWO-GAP LOOKUP (prev2 -> prev1 -> prediction) ===")
    print(f"  Gap classes: VS=1-20, S=21-35, M=36-55, L=56-80, VL=81+\n")
    print(f"  {'Prev2->Prev1':>14}  {'N':>5}  {'Mean':>6}  {'Median':>6}  {'P25':>5}  {'P75':>5}  {'Hot Zone':>12}")
    print(f"  {'-'*65}")

    rows = []
    for key in sorted(double_table.keys()):
        sample = np.array(double_table[key])
        if len(sample) < 10:
            continue
        mean = sample.mean()
        med = np.median(sample)
        p25 = np.percentile(sample, 25)
        p75 = np.percentile(sample, 75)

        best_s = 0
        best_c = 0
        for s in range(0, 200):
            c = ((sample >= s) & (sample < s + 10)).sum()
            if c > best_c: best_c, best_s = c, s

        rows.append((key, len(sample), mean, med, p25, p75, best_s))

    # Sort by median (fastest VTs first)
    rows.sort(key=lambda x: x[3])
    for key, n, mean, med, p25, p75, best_s in rows:
        label = f"{key[0]}->{key[1]}"
        print(f"  {label:>14}  {n:>5}  {mean:>5.0f}   {med:>5.0f}   "
              f"{p25:>4.0f}   {p75:>4.0f}   spins {best_s}-{best_s+10}")


def print_scenario_playbook(single_table, fine_table, double_table):
    """Print specific scenario predictions for real gameplay."""
    print("\n" + "=" * 70)
    print("  SCENARIO PLAYBOOK")
    print("=" * 70)

    scenarios = [
        # (description, prev_gap, prev_prev_gap)
        ("Just survived a 100+ spin drought, VT finally hit", 105, None),
        ("Two long droughts in a row (80, then 90)", 90, 80),
        ("Quick VT! Only 10 spins after the last one", 10, None),
        ("Two quick VTs back to back (15, then 12)", 12, 15),
        ("Normal gap (45 spins), nothing special", 45, None),
        ("Long then short: 85 spin drought, then quick 15", 15, 85),
        ("Short then long: quick 12, then 75 spin drought", 75, 12),
        ("Medium then medium: 40, then 50", 50, 40),
        ("Monster drought (150+ spins), finally hit", 150, None),
        ("Quick VT after a monster drought (VL->VS pattern)", 8, 120),
    ]

    for desc, prev_gap, prev_prev_gap in scenarios:
        print(f"\n  --- SCENARIO: {desc} ---")
        sample, source = predict(single_table, fine_table, double_table,
                                  prev_gap, prev_prev_gap)
        display_prediction(sample, source, prev_gap, prev_prev_gap)


if __name__ == '__main__':
    print("Loading data...", file=sys.stderr)
    df = load_all_data()
    gaps = extract_gaps(df)
    print(f"Total: {len(df)} spins, {len(gaps)} gaps", file=sys.stderr)

    single_table, fine_table, double_table = build_prediction_tables(gaps)

    # Print the master reference table
    print_master_table(single_table, fine_table, double_table)

    # Print scenario playbook
    print_scenario_playbook(single_table, fine_table, double_table)
