"""
Gap Predictor vs Reality Comparison Simulation.

Walk through every gap in the dataset chronologically.
At each VT, predict the next gap window using prev gap (and prev-prev gap).
Compare prediction to actual outcome.

Metrics:
  - Did the VT land inside the predicted P25-P75 window? (50% target)
  - Did it land inside P10-P90? (80% target)
  - Did it land inside the hot zone? (10-spin window)
  - Mean absolute error of median prediction vs actual
  - Betting sim: if you bet high only inside the predicted window, ROI?
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


def classify_gap(g):
    if g <= 20: return 'VS'
    if g <= 35: return 'S'
    if g <= 55: return 'M'
    if g <= 80: return 'L'
    return 'VL'


def build_tables(gaps):
    """Build lookup tables from training gaps."""
    fine = defaultdict(list)
    double = defaultdict(list)
    for i in range(len(gaps) - 1):
        bucket = (gaps[i] // 10) * 10
        fine[bucket].append(gaps[i + 1])
    for i in range(len(gaps) - 2):
        key = (classify_gap(gaps[i]), classify_gap(gaps[i + 1]))
        double[key].append(gaps[i + 2])
    return fine, double


def get_prediction(fine, double, prev_gap, prev_prev_gap=None):
    """Return prediction sample array and source label."""
    # Try 2-gap first
    if prev_prev_gap is not None:
        key = (classify_gap(prev_prev_gap), classify_gap(prev_gap))
        if key in double and len(double[key]) >= 12:
            return np.array(double[key]), f"2gap {key[0]}->{key[1]}"

    # Fine-grained 1-gap
    bucket = (prev_gap // 10) * 10
    if bucket in fine and len(fine[bucket]) >= 15:
        return np.array(fine[bucket]), f"fine {bucket}-{bucket+10}"

    # Coarse 1-gap fallback (pool neighbouring buckets)
    pooled = []
    for b in [bucket - 10, bucket, bucket + 10]:
        if b in fine:
            pooled.extend(fine[b])
    if len(pooled) >= 10:
        return np.array(pooled), f"pooled ~{bucket}"

    # Last resort: all gaps
    all_gaps = []
    for v in fine.values():
        all_gaps.extend(v)
    return np.array(all_gaps), "baseline"


def run_comparison(gaps, mode='full'):
    """
    Walk through gaps and compare predictions to actuals.
    mode='full'  : train on ALL data (in-sample, best case)
    mode='split'  : train on first 60%, test on last 40%
    mode='rolling': train on all gaps BEFORE current (walk-forward)
    """
    if mode == 'full':
        fine, double = build_tables(gaps)
        test_start = 2  # need at least 2 prior gaps
        test_gaps = gaps
    elif mode == 'split':
        split = int(len(gaps) * 0.6)
        train_gaps = gaps[:split]
        fine, double = build_tables(train_gaps)
        test_start = split
        test_gaps = gaps
    elif mode == 'rolling':
        fine, double = None, None  # rebuilt each step
        test_start = 30  # need minimum history
        test_gaps = gaps

    results = []

    for i in range(test_start, len(test_gaps)):
        actual = test_gaps[i]
        prev_gap = test_gaps[i - 1]
        prev_prev_gap = test_gaps[i - 2] if i >= 2 else None

        if mode == 'rolling':
            # Rebuild tables from all gaps before i
            fine, double = build_tables(test_gaps[:i])

        sample, source = get_prediction(fine, double, prev_gap, prev_prev_gap)

        median_pred = np.median(sample)
        mean_pred = sample.mean()
        p10 = np.percentile(sample, 10)
        p25 = np.percentile(sample, 25)
        p75 = np.percentile(sample, 75)
        p90 = np.percentile(sample, 90)

        # Hot zone (10-spin window with most VTs in sample)
        best_s, best_c = 0, 0
        for s in range(0, 200):
            c = ((sample >= s) & (sample < s + 10)).sum()
            if c > best_c:
                best_c, best_s = c, s
        hot_lo, hot_hi = best_s, best_s + 10

        # 20-spin hot zone
        best_s20, best_c20 = 0, 0
        for s in range(0, 200):
            c = ((sample >= s) & (sample < s + 20)).sum()
            if c > best_c20:
                best_c20, best_s20 = c, s
        hot20_lo, hot20_hi = best_s20, best_s20 + 20

        results.append({
            'idx': i,
            'actual': actual,
            'prev_gap': prev_gap,
            'prev_prev': prev_prev_gap,
            'median_pred': median_pred,
            'mean_pred': mean_pred,
            'p10': p10, 'p25': p25, 'p75': p75, 'p90': p90,
            'hot_lo': hot_lo, 'hot_hi': hot_hi,
            'hot20_lo': hot20_lo, 'hot20_hi': hot20_hi,
            'source': source,
            'in_p25_p75': p25 <= actual <= p75,
            'in_p10_p90': p10 <= actual <= p90,
            'in_hot10': hot_lo <= actual < hot_hi,
            'in_hot20': hot20_lo <= actual < hot20_hi,
            'abs_err_median': abs(actual - median_pred),
            'abs_err_mean': abs(actual - mean_pred),
        })

    return results


def print_results(results, label):
    n = len(results)
    if n == 0:
        print(f"  No results for {label}")
        return

    print(f"\n{'='*70}")
    print(f"  {label} ({n} predictions)")
    print(f"{'='*70}")

    # Accuracy metrics
    in_50 = sum(r['in_p25_p75'] for r in results) / n * 100
    in_80 = sum(r['in_p10_p90'] for r in results) / n * 100
    in_hot10 = sum(r['in_hot10'] for r in results) / n * 100
    in_hot20 = sum(r['in_hot20'] for r in results) / n * 100
    mae_median = np.mean([r['abs_err_median'] for r in results])
    mae_mean = np.mean([r['abs_err_mean'] for r in results])

    # Baseline: always predict overall median
    overall_median = np.median([r['actual'] for r in results])
    mae_baseline = np.mean([abs(r['actual'] - overall_median) for r in results])

    print(f"\n  Window accuracy:")
    print(f"    VT landed in P25-P75 (50% window): {in_50:.1f}%  (target: 50%)")
    print(f"    VT landed in P10-P90 (80% window): {in_80:.1f}%  (target: 80%)")
    print(f"    VT landed in hot zone (10-spin):   {in_hot10:.1f}%")
    print(f"    VT landed in hot zone (20-spin):   {in_hot20:.1f}%")

    print(f"\n  Error metrics:")
    print(f"    MAE (median prediction):  {mae_median:.1f} spins")
    print(f"    MAE (mean prediction):    {mae_mean:.1f} spins")
    print(f"    MAE (baseline = always {overall_median:.0f}): {mae_baseline:.1f} spins")
    print(f"    Improvement over baseline: {(1 - mae_median/mae_baseline)*100:.1f}%")

    # Breakdown by previous gap class
    print(f"\n  Accuracy by previous gap class:")
    print(f"  {'Prev class':<12} {'N':>5} {'P25-P75':>8} {'P10-P90':>8} {'Hot10':>7} {'Hot20':>7} {'MAE':>6}")
    print(f"  {'-'*60}")
    for cls in ['VS', 'S', 'M', 'L', 'VL']:
        subset = [r for r in results if classify_gap(r['prev_gap']) == cls]
        if len(subset) < 5: continue
        ns = len(subset)
        s_50 = sum(r['in_p25_p75'] for r in subset) / ns * 100
        s_80 = sum(r['in_p10_p90'] for r in subset) / ns * 100
        s_h10 = sum(r['in_hot10'] for r in subset) / ns * 100
        s_h20 = sum(r['in_hot20'] for r in subset) / ns * 100
        s_mae = np.mean([r['abs_err_median'] for r in subset])
        print(f"  {cls:<12} {ns:>5} {s_50:>7.1f}% {s_80:>7.1f}% {s_h10:>6.1f}% {s_h20:>6.1f}% {s_mae:>5.1f}")

    # Show 20 example predictions
    print(f"\n  Sample predictions (first 30):")
    print(f"  {'#':>4} {'Prev':>5} {'Actual':>7} {'Median':>7} {'P25-P75':>11} {'Hot10':>10} {'Err':>5} {'Hit?':>5}")
    print(f"  {'-'*60}")
    for r in results[:30]:
        hit_50 = 'Y' if r['in_p25_p75'] else ''
        hit_hot = 'Y' if r['in_hot10'] else ''
        print(f"  {r['idx']:>4} {r['prev_gap']:>5} {r['actual']:>7} {r['median_pred']:>7.0f} "
              f"{r['p25']:>4.0f}-{r['p75']:<4.0f}  "
              f"{r['hot_lo']:>3}-{r['hot_hi']:<3}  "
              f"{r['abs_err_median']:>5.0f} {hit_50:>3} {hit_hot:>2}")


def betting_simulation(results, gaps, base_vt_rate):
    """Simulate actual betting using predictions.
    Compare: always bet vs bet only in predicted window."""
    print(f"\n{'='*70}")
    print(f"  BETTING SIMULATION")
    print(f"{'='*70}")

    total_spins = sum(r['actual'] for r in results)
    total_vts = len(results)

    # Strategy 1: Always bet high (baseline)
    # Strategy 2: Bet high only when gap_pos is inside P25-P75
    # Strategy 3: Bet high only when gap_pos is inside P10-P90
    # Strategy 4: Bet high only when gap_pos >= P25 (start of expected window)
    # Strategy 5: Bet high in hot zone (20-spin)
    # Strategy 6: Adaptive from conditional hazard

    strategies = {
        'Always high (baseline)': lambda r, pos: True,
        'Inside P25-P75 only': lambda r, pos: r['p25'] <= pos <= r['p75'],
        'Inside P10-P90 only': lambda r, pos: r['p10'] <= pos <= r['p90'],
        'After P25 (start of window)': lambda r, pos: pos >= r['p25'],
        'Hot zone 20-spin': lambda r, pos: r['hot20_lo'] <= pos < r['hot20_hi'],
        'Hot zone 10-spin': lambda r, pos: r['hot_lo'] <= pos < r['hot_hi'],
        'After P10 (wide start)': lambda r, pos: pos >= r['p10'],
    }

    print(f"\n  Total gaps simulated: {len(results)}")
    print(f"  Total spins across all gaps: {total_spins}")
    print(f"  Base VT rate: {base_vt_rate*100:.2f}%")

    print(f"\n  {'Strategy':<30} {'Spins bet':>10} {'Bet%':>6} {'VTs caught':>11} {'Catch%':>7} {'VT rate':>8} {'Lift':>6}")
    print(f"  {'-'*85}")

    for name, rule in strategies.items():
        spins_bet = 0
        vts_caught = 0

        for r in results:
            actual_gap = r['actual']
            for pos in range(actual_gap + 1):  # 0 to actual_gap inclusive
                is_vt_spin = (pos == actual_gap)  # VT lands at this position
                should_bet = rule(r, pos)

                if should_bet:
                    spins_bet += 1
                    if is_vt_spin:
                        vts_caught += 1

        bet_pct = spins_bet / total_spins * 100 if total_spins > 0 else 0
        catch_pct = vts_caught / total_vts * 100 if total_vts > 0 else 0
        vt_rate = vts_caught / spins_bet * 100 if spins_bet > 0 else 0
        lift = (vts_caught / spins_bet) / base_vt_rate if spins_bet > 0 and base_vt_rate > 0 else 0

        print(f"  {name:<30} {spins_bet:>10} {bet_pct:>5.1f}% {vts_caught:>7}/{total_vts:<3} "
              f"{catch_pct:>6.1f}% {vt_rate:>7.2f}% {lift:>5.2f}x")

    # Detailed: what does the P25-start strategy look like gap by gap?
    print(f"\n  === 'After P25' strategy detail by gap class ===")
    for cls in ['VS', 'S', 'M', 'L', 'VL']:
        subset = [r for r in results if classify_gap(r['prev_gap']) == cls]
        if len(subset) < 5: continue

        total_sub = sum(r['actual'] for r in subset)
        spins_bet = 0
        vts_caught = 0
        for r in subset:
            for pos in range(r['actual'] + 1):
                if pos >= r['p25']:
                    spins_bet += 1
                    if pos == r['actual']:
                        vts_caught += 1

        bet_pct = spins_bet / total_sub * 100 if total_sub > 0 else 0
        catch_pct = vts_caught / len(subset) * 100
        vt_rate = vts_caught / spins_bet * 100 if spins_bet > 0 else 0
        lift = (vts_caught / spins_bet) / base_vt_rate if spins_bet > 0 and base_vt_rate > 0 else 0

        print(f"    After {cls}: bet {bet_pct:.0f}% of spins, catch {catch_pct:.0f}% of VTs, "
              f"VT rate {vt_rate:.2f}% ({lift:.2f}x lift)")


def per_account_sim(df):
    """Run the simulation per account to check consistency."""
    print(f"\n{'='*70}")
    print(f"  PER-ACCOUNT COMPARISON")
    print(f"{'='*70}")

    for acct in sorted(df['account'].unique()):
        mask = df['account'] == acct
        vt = df.loc[mask, 'is_valuable'].values
        vt_idx = np.where(vt)[0]
        if len(vt_idx) < 20: continue
        acct_gaps = np.diff(vt_idx)
        base_rate = vt.mean()

        # Walk-forward on this account
        results = run_comparison(acct_gaps, mode='rolling')
        if len(results) < 10: continue

        n = len(results)
        in_50 = sum(r['in_p25_p75'] for r in results) / n * 100
        in_80 = sum(r['in_p10_p90'] for r in results) / n * 100
        in_h20 = sum(r['in_hot20'] for r in results) / n * 100
        mae = np.mean([r['abs_err_median'] for r in results])
        overall_med = np.median(acct_gaps)
        mae_base = np.mean([abs(r['actual'] - overall_med) for r in results])

        print(f"\n  {acct}: {len(acct_gaps)} gaps, base rate {base_rate*100:.2f}%")
        print(f"    P25-P75 hit: {in_50:.1f}%  |  P10-P90 hit: {in_80:.1f}%  |  Hot20 hit: {in_h20:.1f}%")
        print(f"    MAE: {mae:.1f} (baseline {mae_base:.1f}, improvement {(1-mae/mae_base)*100:.1f}%)")


if __name__ == '__main__':
    print("Loading data...", file=sys.stderr)
    df = load_all_data()
    vt = df['is_valuable'].values
    vt_idx = np.where(vt)[0]
    gaps = np.diff(vt_idx)
    base_vt_rate = vt.mean()
    print(f"Total: {len(df)} spins, {vt.sum()} VTs, {len(gaps)} gaps, base rate {base_vt_rate*100:.2f}%", file=sys.stderr)

    # === MODE 1: In-sample (best case, uses all data to predict all data) ===
    results_full = run_comparison(gaps, mode='full')
    print_results(results_full, "IN-SAMPLE (train=all, test=all)")

    # === MODE 2: 60/40 split (realistic, train on first 60%) ===
    results_split = run_comparison(gaps, mode='split')
    print_results(results_split, "60/40 SPLIT (train=first 60%, test=last 40%)")

    # === MODE 3: Walk-forward (most realistic, only uses past data) ===
    results_rolling = run_comparison(gaps, mode='rolling')
    print_results(results_rolling, "WALK-FORWARD (train=all prior, test=current)")

    # === BETTING SIM on walk-forward results ===
    betting_simulation(results_rolling, gaps, base_vt_rate)

    # === PER ACCOUNT ===
    per_account_sim(df)
