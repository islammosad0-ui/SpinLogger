"""
Deep dive on VT gap alternation.

Core finding: gaps have lag-1 autocorrelation r = -0.258.
SHORT -> LONG and LONG -> SHORT dominate.

Questions to answer:
1. Precise gap transition matrix (not just 3 bins)
2. Does knowing the previous gap SHIFT the hazard rate curve?
3. Multi-gap memory: do the last 2-3 gaps improve prediction?
4. "Debt model": does the game maintain a running VT budget?
5. Per-account consistency
6. Practical edge: optimal bet timing given previous gap knowledge
7. Does VT type (ACC vs SPN) interact with alternation?
8. Can we predict the ZONE of the next VT (narrow the window)?
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
SYM_SHORT = {0: 'ATK', 1: 'CON', 2: 'SHD', 3: 'GLD', 4: 'STL',
             5: 'CON2', 6: 'SPN', 7: 'GLD2', 8: 'ACC'}
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
                for col in ['bet_multiplier', 'sa_spins', 'sa_spn', 'sa_acc',
                            'accum_delta', 'accum_pct', 'seq']:
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


def extract_gaps(vt_array):
    """Return array of gaps between consecutive VTs."""
    vt_indices = np.where(vt_array)[0]
    if len(vt_indices) < 2:
        return np.array([]), vt_indices
    return np.diff(vt_indices), vt_indices


def extract_gap_info(df):
    """Extract gaps with metadata about the VT that starts each gap."""
    vt = df['is_valuable'].values
    vt_indices = np.where(vt)[0]
    if len(vt_indices) < 2:
        return []

    r1i = df['r1_idx'].values if 'r1_idx' in df.columns else None

    records = []
    for i in range(len(vt_indices) - 1):
        start_idx = vt_indices[i]
        end_idx = vt_indices[i + 1]
        gap_len = end_idx - start_idx

        vt_type = SYM_SHORT.get(r1i[start_idx], '?') if r1i is not None else '?'
        next_vt_type = SYM_SHORT.get(r1i[end_idx], '?') if r1i is not None else '?'

        records.append({
            'gap_num': i,
            'gap_len': gap_len,
            'start_idx': start_idx,
            'end_idx': end_idx,
            'vt_type': vt_type,       # VT that STARTED this gap
            'next_vt_type': next_vt_type,  # VT that ENDED this gap
        })
    return records


def test_1_transition_matrix(gaps):
    """Fine-grained gap transition matrix."""
    print("=" * 70)
    print("1. GAP TRANSITION MATRIX (fine-grained)")
    print("=" * 70)

    # Define quintile-based bins
    q20 = np.percentile(gaps, 20)
    q40 = np.percentile(gaps, 40)
    q60 = np.percentile(gaps, 60)
    q80 = np.percentile(gaps, 80)

    def label(g):
        if g <= q20: return f'VERY SHORT (1-{int(q20)})'
        if g <= q40: return f'SHORT ({int(q20)+1}-{int(q40)})'
        if g <= q60: return f'MED ({int(q40)+1}-{int(q60)})'
        if g <= q80: return f'LONG ({int(q60)+1}-{int(q80)})'
        return f'VERY LONG ({int(q80)+1}+)'

    labels_ordered = [
        f'VERY SHORT (1-{int(q20)})',
        f'SHORT ({int(q20)+1}-{int(q40)})',
        f'MED ({int(q40)+1}-{int(q60)})',
        f'LONG ({int(q60)+1}-{int(q80)})',
        f'VERY LONG ({int(q80)+1}+)',
    ]

    print(f"\n  Quintile boundaries: {int(q20)}, {int(q40)}, {int(q60)}, {int(q80)}")
    print(f"  Gap range: {gaps.min()}-{gaps.max()}, mean={gaps.mean():.1f}, median={np.median(gaps):.1f}")

    # Build transition counts
    trans = defaultdict(lambda: defaultdict(int))
    for i in range(len(gaps) - 1):
        prev_label = label(gaps[i])
        next_label = label(gaps[i + 1])
        trans[prev_label][next_label] += 1

    # Print matrix
    print(f"\n  {'Previous gap':<25} -> {'Next gap distribution':>40}")
    print(f"  {'-'*70}")

    for prev in labels_ordered:
        total = sum(trans[prev].values())
        if total == 0:
            continue
        parts = []
        for nxt in labels_ordered:
            cnt = trans[prev][nxt]
            pct = cnt / total * 100
            parts.append(f"{pct:5.1f}%")
        print(f"  {prev:<25}:  {'  '.join(parts)}  (n={total})")

    print(f"\n  Column headers: {', '.join([l.split(' ')[0] for l in labels_ordered])}")

    # Also show raw number transition
    print(f"\n  Exact previous gap -> mean next gap:")
    # Group prev gaps into 10-spin buckets
    for lo in range(0, 150, 10):
        hi = lo + 10
        matching = [(i, gaps[i]) for i in range(len(gaps)-1)
                    if lo <= gaps[i] < hi]
        if len(matching) >= 10:
            next_gaps = [gaps[i+1] for i, _ in matching]
            mean_next = np.mean(next_gaps)
            med_next = np.median(next_gaps)
            print(f"    prev gap [{lo:3d}-{hi:3d}): mean next = {mean_next:.1f}, "
                  f"median next = {med_next:.1f} (n={len(matching)})")


def test_2_conditional_hazard(df, gaps, vt_indices):
    """Does the hazard rate curve SHIFT based on previous gap length?"""
    print("\n" + "=" * 70)
    print("2. CONDITIONAL HAZARD RATE (how prev gap shifts the curve)")
    print("=" * 70)

    vt = df['is_valuable'].values
    base_rate = vt.mean()
    median_gap = np.median(gaps)

    # Split gaps into SHORT (below median) and LONG (above median)
    # For each, compute the hazard rate at each position within the gap
    short_thresh = np.percentile(gaps, 33)
    long_thresh = np.percentile(gaps, 67)

    print(f"\n  Thresholds: SHORT <= {int(short_thresh)}, LONG >= {int(long_thresh)}")
    print(f"  Base VT rate: {base_rate*100:.2f}%\n")

    # Compute gap position for each spin + which gap class it's in
    # We need to know: for each spin, what was the previous gap's length?
    gap_pos = np.zeros(len(df), dtype=int)
    prev_gap_len = np.full(len(df), -1, dtype=int)

    counter = 0
    last_gap_len = -1
    for i in range(len(df)):
        gap_pos[i] = counter
        prev_gap_len[i] = last_gap_len
        if vt[i]:
            last_gap_len = counter
            counter = 0
        else:
            counter += 1

    print(f"  {'Gap pos':<12} {'After SHORT':<20} {'After MED':<20} {'After LONG':<20}")
    print(f"  {'':12} {'rate  (n)  lift':<20} {'rate  (n)  lift':<20} {'rate  (n)  lift':<20}")
    print(f"  {'-'*72}")

    for g_lo, g_hi in [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
                        (50, 60), (60, 70), (70, 80), (80, 100), (100, 150)]:
        parts = []
        for prev_class, p_lo, p_hi in [('SHORT', 0, short_thresh + 1),
                                         ('MED', short_thresh + 1, long_thresh),
                                         ('LONG', long_thresh, 9999)]:
            mask = (gap_pos >= g_lo) & (gap_pos < g_hi) & \
                   (prev_gap_len >= p_lo) & (prev_gap_len < p_hi)
            n = mask.sum()
            if n >= 20:
                rate = vt[mask].mean()
                lift = rate / base_rate
                parts.append(f"{rate*100:5.2f}% ({n:4d}) {lift:.2f}x")
            else:
                parts.append(f"  --   ({n:4d})   -- ")
        print(f"  [{g_lo:3d}-{g_hi:3d})   {'  '.join(parts)}")

    # Summary: when should you bet high vs low based on prev gap?
    print(f"\n  === ACTIONABLE SUMMARY ===")
    for prev_class, p_lo, p_hi in [('SHORT (prev gap <= ' + str(int(short_thresh)) + ')',
                                      0, short_thresh + 1),
                                     ('LONG (prev gap >= ' + str(int(long_thresh)) + ')',
                                      long_thresh, 9999)]:
        print(f"\n  After {prev_class}:")
        for g_lo, g_hi in [(0, 20), (20, 40), (40, 60), (60, 80), (80, 120)]:
            mask = (gap_pos >= g_lo) & (gap_pos < g_hi) & \
                   (prev_gap_len >= p_lo) & (prev_gap_len < p_hi)
            n = mask.sum()
            if n >= 30:
                rate = vt[mask].mean()
                lift = rate / base_rate
                vt_count = vt[mask].sum()
                advice = "BET HIGH" if lift > 1.3 else ("BET LOW" if lift < 0.7 else "normal")
                print(f"    spin {g_lo:3d}-{g_hi:3d} into gap: "
                      f"{rate*100:.2f}% ({n} spins, {lift:.2f}x, {vt_count} VTs) -> {advice}")


def test_3_multigap_memory(gaps):
    """Do the last 2-3 gaps together predict the next gap better than just 1?"""
    print("\n" + "=" * 70)
    print("3. MULTI-GAP MEMORY (do last 2-3 gaps predict next?)")
    print("=" * 70)

    median_gap = np.median(gaps)

    # Lag-1 through lag-5 autocorrelation
    print(f"\n  Gap autocorrelation (extended):")
    for lag in range(1, min(11, len(gaps))):
        r = np.corrcoef(gaps[:-lag], gaps[lag:])[0, 1]
        sig = " ***" if abs(r) > 2/np.sqrt(len(gaps)) else ""
        print(f"    lag {lag}: r = {r:+.3f}{sig}")

    # Partial autocorrelation: does lag 2 add info beyond lag 1?
    print(f"\n  2-gap lookback prediction:")
    print(f"  (prev2, prev1) class -> mean next gap:")

    def classify(g):
        if g <= np.percentile(gaps, 33): return 'S'
        if g <= np.percentile(gaps, 67): return 'M'
        return 'L'

    # 2-gap sequences
    results = []
    for i in range(2, len(gaps)):
        prev2 = classify(gaps[i-2])
        prev1 = classify(gaps[i-1])
        results.append((prev2, prev1, gaps[i]))

    patterns_2 = defaultdict(list)
    for p2, p1, nxt in results:
        patterns_2[f"{p2}->{p1}"].append(nxt)

    for key in sorted(patterns_2.keys()):
        vals = np.array(patterns_2[key])
        if len(vals) >= 15:
            print(f"    {key}: mean={vals.mean():.1f}, median={np.median(vals):.1f}, "
                  f"std={vals.std():.1f}, n={len(vals)}")

    # 3-gap sequences
    print(f"\n  3-gap lookback prediction:")
    results_3 = []
    for i in range(3, len(gaps)):
        p3 = classify(gaps[i-3])
        p2 = classify(gaps[i-2])
        p1 = classify(gaps[i-1])
        results_3.append((p3, p2, p1, gaps[i]))

    patterns_3 = defaultdict(list)
    for p3, p2, p1, nxt in results_3:
        patterns_3[f"{p3}->{p2}->{p1}"].append(nxt)

    # Show patterns with enough data
    sorted_patterns = sorted(patterns_3.items(), key=lambda x: np.mean(x[1]))
    for key, vals in sorted_patterns:
        vals = np.array(vals)
        if len(vals) >= 10:
            print(f"    {key}: mean={vals.mean():.1f}, median={np.median(vals):.1f}, n={len(vals)}")

    # KEY: does knowing 2 gaps improve prediction over 1 gap?
    print(f"\n  === Prediction improvement from multi-gap memory ===")

    # 1-gap prediction error
    err_1 = []
    for i in range(1, len(gaps)):
        pred_class = classify(gaps[i-1])
        actual = gaps[i]
        # Predict median of the matching class
        class_gaps = [gaps[j] for j in range(len(gaps)) if classify(gaps[j]) == pred_class]
        pred = np.median(class_gaps)
        err_1.append(abs(actual - pred))

    # 2-gap prediction error
    err_2 = []
    for i in range(2, len(gaps)):
        key = f"{classify(gaps[i-2])}->{classify(gaps[i-1])}"
        actual = gaps[i]
        if key in patterns_2 and len(patterns_2[key]) >= 5:
            pred = np.median(patterns_2[key])
        else:
            pred = np.median(gaps)
        err_2.append(abs(actual - pred))

    print(f"    1-gap prediction MAE: {np.mean(err_1):.1f}")
    print(f"    2-gap prediction MAE: {np.mean(err_2):.1f}")
    print(f"    Baseline (always median): {np.mean([abs(g - np.median(gaps)) for g in gaps]):.1f}")


def test_4_debt_model(df, gaps, vt_indices):
    """Does the game maintain a running VT 'budget'?
    If expected 1 VT per ~49 spins, does a 100-spin gap create 'debt'
    that gets repaid with a short gap?"""
    print("\n" + "=" * 70)
    print("4. DEBT MODEL (does the game maintain a VT budget?)")
    print("=" * 70)

    expected_rate = 1 / np.mean(gaps)
    print(f"\n  Expected VT rate: 1 per {np.mean(gaps):.1f} spins")

    # Running debt: at each VT, how far behind/ahead is the game
    # from the expected VT count?
    # debt = expected_VTs_so_far - actual_VTs_so_far
    vt = df['is_valuable'].values
    n = len(vt)

    cum_expected = np.arange(1, n + 1) * expected_rate
    cum_actual = np.cumsum(vt)
    debt = cum_expected - cum_actual

    # At each VT, what's the debt and what's the next gap?
    vt_idx = np.where(vt)[0]
    print(f"\n  Debt at VT -> next gap length:")
    print(f"  (debt > 0 = game owes you VTs, debt < 0 = game gave too many)")

    debt_at_vt = debt[vt_idx[:-1]]
    next_gaps = np.diff(vt_idx)

    # Bin debt
    debt_bins = [(-999, -2), (-2, -1), (-1, 0), (0, 1), (1, 2), (2, 999)]
    for lo, hi in debt_bins:
        mask = (debt_at_vt >= lo) & (debt_at_vt < hi)
        if mask.sum() >= 10:
            g = next_gaps[mask]
            print(f"    debt [{lo:+5.0f} to {hi:+5.0f}): mean gap = {g.mean():.1f}, "
                  f"median = {np.median(g):.1f}, n = {mask.sum()}")

    # Correlation between debt and next gap
    r = np.corrcoef(debt_at_vt, next_gaps)[0, 1]
    print(f"\n  Correlation(debt, next_gap): r = {r:+.3f}")
    if abs(r) > 0.1:
        print(f"  -> The game {'repays debt (shorter gaps when behind)' if r > 0 else 'compounds debt (longer gaps when behind)'}")

    # Rolling window: VT count in last 100 spins vs next gap
    print(f"\n  Recent VT density (last 100 spins) -> next gap:")
    window = 100
    vt_rolling = np.zeros(n)
    for i in range(n):
        start = max(0, i - window)
        vt_rolling[i] = vt[start:i+1].sum()

    density_at_vt = vt_rolling[vt_idx[:-1]]
    for lo, hi in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 99)]:
        mask = (density_at_vt >= lo) & (density_at_vt < hi)
        if mask.sum() >= 10:
            g = next_gaps[mask]
            print(f"    {lo}-{hi} VTs in last {window}: mean gap = {g.mean():.1f}, "
                  f"median = {np.median(g):.1f}, n = {mask.sum()}")


def test_5_per_account(df):
    """Check gap alternation consistency across accounts."""
    print("\n" + "=" * 70)
    print("5. PER-ACCOUNT GAP ALTERNATION")
    print("=" * 70)

    for acct in sorted(df['account'].unique()):
        mask = df['account'] == acct
        vt = df.loc[mask, 'is_valuable'].values
        gaps, _ = extract_gaps(vt)

        if len(gaps) < 10:
            continue

        # Lag-1 autocorrelation
        r1 = np.corrcoef(gaps[:-1], gaps[1:])[0, 1]

        # Transition pattern
        short_t = np.percentile(gaps, 33)
        long_t = np.percentile(gaps, 67)

        ss = sl = ls = ll = 0
        for i in range(len(gaps) - 1):
            is_short = gaps[i] <= short_t
            is_long = gaps[i] >= long_t
            next_short = gaps[i+1] <= short_t
            next_long = gaps[i+1] >= long_t
            if is_short and next_short: ss += 1
            if is_short and next_long: sl += 1
            if is_long and next_short: ls += 1
            if is_long and next_long: ll += 1

        print(f"\n  {acct}: {len(gaps)} gaps, lag-1 r = {r1:+.3f}")
        print(f"    S->S: {ss}, S->L: {sl}, L->S: {ls}, L->L: {ll}")

        # Mean next gap after short vs long
        after_short = [gaps[i+1] for i in range(len(gaps)-1) if gaps[i] <= short_t]
        after_long = [gaps[i+1] for i in range(len(gaps)-1) if gaps[i] >= long_t]
        if after_short:
            print(f"    After SHORT (gap <= {int(short_t)}): mean next = {np.mean(after_short):.1f}, median = {np.median(after_short):.1f}")
        if after_long:
            print(f"    After LONG (gap >= {int(long_t)}): mean next = {np.mean(after_long):.1f}, median = {np.median(after_long):.1f}")


def test_6_optimal_betting(df, gaps, vt_indices):
    """Simulate a betting strategy based on gap alternation knowledge."""
    print("\n" + "=" * 70)
    print("6. OPTIMAL BETTING STRATEGY (gap alternation + hazard)")
    print("=" * 70)

    vt = df['is_valuable'].values
    n = len(vt)
    base_rate = vt.mean()

    # Compute gap position and prev gap length for each spin
    gap_pos = np.zeros(n, dtype=int)
    prev_gap_len = np.full(n, -1, dtype=int)

    counter = 0
    last_gap_len = -1
    for i in range(n):
        gap_pos[i] = counter
        prev_gap_len[i] = last_gap_len
        if vt[i]:
            last_gap_len = counter
            counter = 0
        else:
            counter += 1

    # Strategy 1: Bet high when gap >= 40 (simple overdue)
    # Strategy 2: Bet high based on prev gap - if prev was SHORT, bet high later;
    #             if prev was LONG, bet high earlier
    # Strategy 3: Combined (prev gap adjusts threshold)

    short_t = np.percentile(gaps, 33)
    long_t = np.percentile(gaps, 67)
    median = np.median(gaps)

    strategies = {
        'Always bet (baseline)': np.ones(n, dtype=bool),
        'Gap >= 40 (simple overdue)': gap_pos >= 40,
        'Gap >= 30 (early overdue)': gap_pos >= 30,
        'Gap >= 50 (conservative)': gap_pos >= 50,
    }

    # Adaptive: after SHORT prev gap, bet later; after LONG, bet earlier
    adaptive_mask = np.zeros(n, dtype=bool)
    for i in range(n):
        if prev_gap_len[i] < 0:  # unknown prev gap
            adaptive_mask[i] = gap_pos[i] >= 40
        elif prev_gap_len[i] <= short_t:
            # After short gap -> next will be long, bet starting at gap 55
            adaptive_mask[i] = gap_pos[i] >= 55
        elif prev_gap_len[i] >= long_t:
            # After long gap -> next will be short, bet starting at gap 20
            adaptive_mask[i] = gap_pos[i] >= 20
        else:
            adaptive_mask[i] = gap_pos[i] >= 40

    strategies['Adaptive (prev gap shifts threshold)'] = adaptive_mask

    # Aggressive adaptive
    adaptive2 = np.zeros(n, dtype=bool)
    for i in range(n):
        if prev_gap_len[i] < 0:
            adaptive2[i] = gap_pos[i] >= 40
        elif prev_gap_len[i] <= short_t:
            adaptive2[i] = gap_pos[i] >= 60
        elif prev_gap_len[i] >= long_t:
            adaptive2[i] = gap_pos[i] >= 15
        else:
            adaptive2[i] = gap_pos[i] >= 40
    strategies['Aggressive adaptive'] = adaptive2

    print(f"\n  {'Strategy':<45} {'VT rate':>8} {'Lift':>6} {'Bet %':>6} {'VTs':>5} {'Efficiency':>10}")
    print(f"  {'-'*85}")

    for name, mask in strategies.items():
        n_bet = mask.sum()
        if n_bet == 0:
            continue
        vt_rate = vt[mask].mean()
        lift = vt_rate / base_rate
        bet_pct = n_bet / n * 100
        vt_count = vt[mask].sum()
        total_vt = vt.sum()
        # Efficiency: VTs caught per spin bet
        eff = vt_rate / base_rate * 100  # % of expected VTs caught normalized
        catch_rate = vt_count / total_vt * 100  # % of total VTs caught
        print(f"  {name:<45} {vt_rate*100:>7.2f}% {lift:>5.2f}x {bet_pct:>5.1f}% {vt_count:>5.0f} {catch_rate:>8.1f}% caught")

    # Detailed view of adaptive strategy
    print(f"\n  === Adaptive strategy detail ===")
    print(f"  After SHORT prev gap (<= {int(short_t)} spins):")
    for g_lo, g_hi in [(0, 20), (20, 40), (40, 55), (55, 70), (70, 90), (90, 120), (120, 200)]:
        mask = (gap_pos >= g_lo) & (gap_pos < g_hi) & (prev_gap_len >= 0) & (prev_gap_len <= short_t)
        n_m = mask.sum()
        if n_m >= 20:
            rate = vt[mask].mean()
            lift = rate / base_rate
            action = "WAIT" if g_lo < 55 else "BET HIGH"
            print(f"    gap [{g_lo:3d}-{g_hi:3d}): {rate*100:.2f}% ({n_m} spins, {lift:.2f}x) -> {action}")

    print(f"\n  After LONG prev gap (>= {int(long_t)} spins):")
    for g_lo, g_hi in [(0, 10), (10, 20), (20, 30), (30, 40), (40, 60), (60, 80), (80, 120)]:
        mask = (gap_pos >= g_lo) & (gap_pos < g_hi) & (prev_gap_len >= long_t)
        n_m = mask.sum()
        if n_m >= 20:
            rate = vt[mask].mean()
            lift = rate / base_rate
            action = "BET HIGH" if g_lo >= 20 else "WAIT"
            print(f"    gap [{g_lo:3d}-{g_hi:3d}): {rate*100:.2f}% ({n_m} spins, {lift:.2f}x) -> {action}")


def test_7_vt_type_interaction(df, gaps, vt_indices):
    """Does the VT type (ACC vs SPN) interact with gap alternation?"""
    print("\n" + "=" * 70)
    print("7. VT TYPE x GAP ALTERNATION INTERACTION")
    print("=" * 70)

    if 'r1_idx' not in df.columns:
        print("  No r1_idx")
        return

    r1i = df['r1_idx'].values
    vt = df['is_valuable'].values

    # Get VT types at each VT
    vt_idx = np.where(vt)[0]
    if len(vt_idx) < 10:
        return

    vt_types = [SYM_SHORT.get(r1i[i], '?') for i in vt_idx]

    # Gap after SPN vs gap after ACC
    gaps_after_spn = []
    gaps_after_acc = []
    for i in range(len(vt_idx) - 1):
        gap = vt_idx[i+1] - vt_idx[i]
        if vt_types[i] == 'SPN':
            gaps_after_spn.append(gap)
        elif vt_types[i] == 'ACC':
            gaps_after_acc.append(gap)

    gaps_spn = np.array(gaps_after_spn)
    gaps_acc = np.array(gaps_after_acc)

    print(f"\n  After SPN triple: mean gap = {gaps_spn.mean():.1f}, median = {np.median(gaps_spn):.1f}, n = {len(gaps_spn)}")
    print(f"  After ACC triple: mean gap = {gaps_acc.mean():.1f}, median = {np.median(gaps_acc):.1f}, n = {len(gaps_acc)}")

    # Does SPN->SPN behave differently from SPN->ACC?
    print(f"\n  VT type transitions:")
    type_trans = defaultdict(list)
    for i in range(len(vt_idx) - 1):
        gap = vt_idx[i+1] - vt_idx[i]
        key = f"{vt_types[i]}->{vt_types[i+1]}"
        type_trans[key].append(gap)

    for key in sorted(type_trans.keys()):
        vals = np.array(type_trans[key])
        if len(vals) >= 5:
            print(f"    {key}: mean gap = {vals.mean():.1f}, median = {np.median(vals):.1f}, n = {len(vals)}")

    # Does alternation strength differ by VT type?
    print(f"\n  Lag-1 autocorrelation by ending VT type:")
    for vt_type in ['SPN', 'ACC']:
        type_gaps = []
        for i in range(len(vt_idx) - 1):
            if vt_types[i+1] == vt_type:
                type_gaps.append(vt_idx[i+1] - vt_idx[i])
        if len(type_gaps) >= 20:
            arr = np.array(type_gaps)
            r = np.corrcoef(arr[:-1], arr[1:])[0, 1]
            print(f"    Gaps ending in {vt_type}: lag-1 r = {r:+.3f} (n={len(arr)})")


def test_8_narrow_window(df, gaps, vt_indices):
    """Can we narrow down the VT prediction to a specific window?
    Goal: identify a 10-spin window that captures the VT."""
    print("\n" + "=" * 70)
    print("8. WINDOW PREDICTION (can we narrow to ~10 spins?)")
    print("=" * 70)

    vt = df['is_valuable'].values
    n = len(vt)
    base_rate = vt.mean()

    gap_pos = np.zeros(n, dtype=int)
    prev_gap_len = np.full(n, -1, dtype=int)

    counter = 0
    last_gap_len = -1
    for i in range(n):
        gap_pos[i] = counter
        prev_gap_len[i] = last_gap_len
        if vt[i]:
            last_gap_len = counter
            counter = 0
        else:
            counter += 1

    # For each VT, compute: gap_position when it hit, and prev gap length
    vt_idx = np.where(vt)[0]
    vt_gap_pos = gap_pos[vt_idx]
    vt_prev_gap = prev_gap_len[vt_idx]

    print(f"\n  Where VTs actually land (gap position distribution):")
    for lo, hi in [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
                   (50, 60), (60, 70), (70, 80), (80, 100), (100, 150), (150, 400)]:
        count = ((vt_gap_pos >= lo) & (vt_gap_pos < hi)).sum()
        pct = count / len(vt_gap_pos) * 100
        bar = '#' * int(pct * 2)
        print(f"    [{lo:3d}-{hi:3d}): {count:4d} VTs ({pct:5.1f}%) {bar}")

    # After SHORT prev gap: where do VTs land?
    short_t = np.percentile(gaps, 33)
    long_t = np.percentile(gaps, 67)

    print(f"\n  After SHORT prev gap (<= {int(short_t)}): where do VTs land?")
    mask = (vt_prev_gap >= 0) & (vt_prev_gap <= short_t)
    after_short_pos = vt_gap_pos[mask]
    for lo, hi in [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
                   (50, 60), (60, 80), (80, 100), (100, 200)]:
        count = ((after_short_pos >= lo) & (after_short_pos < hi)).sum()
        pct = count / len(after_short_pos) * 100 if len(after_short_pos) > 0 else 0
        bar = '#' * int(pct * 2)
        print(f"    [{lo:3d}-{hi:3d}): {count:4d} VTs ({pct:5.1f}%) {bar}")

    print(f"\n  After LONG prev gap (>= {int(long_t)}): where do VTs land?")
    mask = (vt_prev_gap >= long_t)
    after_long_pos = vt_gap_pos[mask]
    for lo, hi in [(0, 10), (10, 20), (20, 30), (30, 40), (40, 50),
                   (50, 60), (60, 80), (80, 100), (100, 200)]:
        count = ((after_long_pos >= lo) & (after_long_pos < hi)).sum()
        pct = count / len(after_long_pos) * 100 if len(after_long_pos) > 0 else 0
        bar = '#' * int(pct * 2)
        print(f"    [{lo:3d}-{hi:3d}): {count:4d} VTs ({pct:5.1f}%) {bar}")

    # Best 10-spin windows after short vs long prev gap
    print(f"\n  === Best 10-spin windows ===")
    for prev_label, p_lo, p_hi in [('After SHORT', 0, short_t + 1),
                                     ('After LONG', long_t, 9999)]:
        print(f"\n  {prev_label}:")
        best_window = None
        best_density = 0
        positions = vt_gap_pos[(vt_prev_gap >= p_lo) & (vt_prev_gap < p_hi)]
        for start in range(0, 150):
            count = ((positions >= start) & (positions < start + 10)).sum()
            density = count / max(1, len(positions))
            if density > best_density:
                best_density = density
                best_window = start
        print(f"    Best window: spins {best_window}-{best_window+10} "
              f"({best_density*100:.1f}% of VTs in this 10-spin window)")

        # Top 3 windows
        window_scores = []
        for start in range(0, 150):
            count = ((positions >= start) & (positions < start + 10)).sum()
            window_scores.append((start, count, count / max(1, len(positions)) * 100))
        window_scores.sort(key=lambda x: -x[1])
        for start, count, pct in window_scores[:5]:
            print(f"    spins {start:3d}-{start+10:3d}: {count} VTs ({pct:.1f}%)")

    # Cumulative: what % of VTs are caught by gap position X?
    print(f"\n  === Cumulative VT catch rate ===")
    print(f"  (if you start betting at spin X into the gap, what % of VTs do you catch?)")
    for label, positions in [('ALL', vt_gap_pos),
                              ('After SHORT', vt_gap_pos[(vt_prev_gap >= 0) & (vt_prev_gap <= short_t)]),
                              ('After LONG', vt_gap_pos[vt_prev_gap >= long_t])]:
        if len(positions) < 10:
            continue
        print(f"\n  {label} ({len(positions)} VTs):")
        for start_at in [10, 20, 30, 40, 50, 60, 70, 80]:
            caught = (positions >= start_at).sum()
            pct = caught / len(positions) * 100
            missed = 100 - pct
            print(f"    Start betting at spin {start_at:3d}: catch {pct:.1f}% of VTs, miss {missed:.1f}%")


if __name__ == '__main__':
    print("Loading data...", file=sys.stderr)
    df = load_all_data()
    vt = df['is_valuable'].values
    gaps, vt_indices = extract_gaps(vt)
    print(f"Total: {len(df)} spins, {vt.sum()} VTs, {len(gaps)} gaps", file=sys.stderr)

    test_1_transition_matrix(gaps)
    test_2_conditional_hazard(df, gaps, vt_indices)
    test_3_multigap_memory(gaps)
    test_4_debt_model(df, gaps, vt_indices)
    test_5_per_account(df)
    test_6_optimal_betting(df, gaps, vt_indices)
    test_7_vt_type_interaction(df, gaps, vt_indices)
    test_8_narrow_window(df, gaps, vt_indices)
