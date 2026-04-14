"""
RNG Crack Analysis: Can the raw strip positions (r1/r2/r3 = 0-30) reveal
the underlying PRNG algorithm?

If Coin Master uses a weak PRNG (LCG, xorshift, MT with known seed),
consecutive raw positions would leak state. This would let someone predict
the EXACT next spin.

Tests:
1. Delta patterns between consecutive r1 values
2. LCG detection: r1[n+1] = (a * r1[n] + c) mod m
3. Cross-reel same-spin correlation in RAW positions
4. Bet-change → VT correlation (does changing bet affect RNG?)
5. Autocorrelation in raw position sequences
6. Combined raw position state → VT prediction
"""
import pandas as pd
import numpy as np
import os, glob, sys
from collections import Counter, defaultdict
from itertools import product

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
    """Load with RAW r1/r2/r3 positions preserved (0-30 range)."""
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

                # Keep raw positions
                keep_cols = ['r1', 'r2', 'r3', 'is_triple']

                # Get symbol indices from reel text
                if 'reel_1' in df.columns:
                    df['r1_idx'] = df['reel_1'].map(REEL_TEXT_TO_IDX)
                    df['r2_idx'] = df['reel_2'].map(REEL_TEXT_TO_IDX)
                    df['r3_idx'] = df['reel_3'].map(REEL_TEXT_TO_IDX)
                    keep_cols += ['r1_idx', 'r2_idx', 'r3_idx']
                elif 'r1_idx' in df.columns:
                    keep_cols += ['r1_idx', 'r2_idx', 'r3_idx']

                # Bet columns
                if 'bet_multiplier' in df.columns:
                    keep_cols.append('bet_multiplier')
                if 'bet_level' in df.columns:
                    keep_cols.append('bet_level')

                # Session accumulators
                for col in ['sa_spins', 'sa_spn', 'sa_acc', 'accum_delta', 'accum_pct']:
                    if col in df.columns:
                        keep_cols.append(col)

                # seq for ordering
                if 'seq' in df.columns:
                    keep_cols.append('seq')

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
                    subset['is_valuable'] = False  # can't determine without idx

                print(f"  Loaded {basename}: {len(subset)} spins, r1 range [{subset['r1'].min()}-{subset['r1'].max()}]", file=sys.stderr)
                frames.append(subset)
            except Exception as e:
                print(f"  Skip {basename}: {e}", file=sys.stderr)

    big = pd.concat(frames, ignore_index=True)
    return big


def test_1_raw_position_distribution(df):
    """What does the raw position distribution look like? Uniform? Biased?"""
    print("\n" + "=" * 70)
    print("TEST 1: RAW STRIP POSITION DISTRIBUTION")
    print("=" * 70)

    for reel_name in ['r1', 'r2', 'r3']:
        vals = df[reel_name]
        print(f"\n{reel_name}: range [{vals.min()}-{vals.max()}], unique={vals.nunique()}")
        vc = vals.value_counts().sort_index()
        n = len(vals)
        print(f"  Distribution (position: count, pct):")
        for pos, cnt in vc.items():
            bar = '#' * int(cnt / n * 200)
            print(f"    pos {pos:2d}: {cnt:5d} ({cnt/n*100:5.1f}%) {bar}")


def test_2_delta_patterns(df):
    """Look at r1[n+1] - r1[n] mod strip_size. LCG would show structure."""
    print("\n" + "=" * 70)
    print("TEST 2: CONSECUTIVE DELTA PATTERNS (r1[n+1] - r1[n])")
    print("=" * 70)

    for reel_name in ['r1', 'r2', 'r3']:
        vals = df[reel_name].values
        strip_size = vals.max() + 1  # e.g., 31 positions (0-30)

        deltas = (vals[1:] - vals[:-1]) % strip_size

        print(f"\n{reel_name} deltas (mod {strip_size}):")
        vc = pd.Series(deltas).value_counts().sort_index()
        n = len(deltas)
        expected = n / strip_size

        # Show distribution + chi-square
        chi2 = 0
        for d in range(strip_size):
            cnt = vc.get(d, 0)
            chi2 += (cnt - expected) ** 2 / expected
            if cnt > expected * 1.3 or cnt < expected * 0.7:
                flag = " *** BIASED"
            else:
                flag = ""
            print(f"    delta {d:2d}: {cnt:5d} (expected {expected:.0f}){flag}")

        from scipy import stats
        p_val = 1 - stats.chi2.cdf(chi2, strip_size - 1)
        print(f"  Chi-square: {chi2:.1f}, p-value: {p_val:.6f}")
        print(f"  {'UNIFORM (no pattern)' if p_val > 0.01 else 'NON-UNIFORM - PATTERN DETECTED!'}")


def test_3_lcg_detection(df):
    """Try to find LCG parameters: x[n+1] = (a*x[n] + c) mod m.
    If found, the RNG is completely cracked."""
    print("\n" + "=" * 70)
    print("TEST 3: LCG DETECTION")
    print("=" * 70)
    print("Testing if r1[n+1] = (a * r1[n] + c) mod m for some a, c, m")

    for reel_name in ['r1', 'r2', 'r3']:
        vals = df[reel_name].values
        n = len(vals)

        # Try different moduli
        for m in [31, 32, 64, 128, 256]:
            best_a, best_c, best_score = 0, 0, 0

            # Brute force a, c for small m
            if m <= 64:
                for a in range(m):
                    for c in range(m):
                        predicted = (a * vals[:-1] + c) % m
                        matches = np.sum(predicted == vals[1:] % m)
                        if matches > best_score:
                            best_a, best_c, best_score = a, c, matches

                pct = best_score / (n - 1) * 100
                random_expect = (n - 1) / m
                if pct > 100 / m * 2:  # More than 2x random chance
                    print(f"\n  {reel_name} mod {m}: BEST a={best_a}, c={best_c} -> {best_score}/{n-1} matches ({pct:.1f}%)")
                    print(f"    Random expectation: {random_expect:.0f} ({100/m:.1f}%)")
                    if pct > 50:
                        print(f"    *** STRONG LCG CANDIDATE! ***")
            else:
                # For large m, sample approach
                # Check if consecutive pairs have a linear relationship
                x = vals[:-1].astype(np.int64)
                y = vals[1:].astype(np.int64)

                # If LCG: y = a*x + c mod m
                # Try to solve using 3 consecutive values:
                # y0 = a*x0 + c, y1 = a*x1 + c -> a = (y1-y0)/(x1-x0) mod m
                samples = min(1000, len(x) - 1)
                found = False
                for i in range(samples):
                    if x[i] != x[i+1]:  # avoid division by zero
                        for m_try in [m]:
                            a_try = ((y[i+1] - y[i]) * pow(int(x[i+1] - x[i]), -1, m_try) if np.gcd(int(x[i+1] - x[i]) % m_try, m_try) == 1 else None)
                            if a_try is not None:
                                a_try = a_try % m_try
                                c_try = (y[i] - a_try * x[i]) % m_try
                                # Verify on all data
                                predicted = (a_try * x + c_try) % m_try
                                matches = np.sum(predicted == y % m_try)
                                if matches > len(x) * 0.5:
                                    print(f"\n  {reel_name} mod {m}: a={a_try}, c={c_try} -> {matches}/{len(x)} matches ({matches/len(x)*100:.1f}%)")
                                    print(f"    *** LCG CRACKED! ***")
                                    found = True
                                    break
                    if found:
                        break

        # Also test: is the raw sequence periodic?
        print(f"\n  {reel_name}: Checking for short periods...")
        for period in range(2, 100):
            if period > len(vals) // 2:
                break
            matches = np.sum(vals[period:] == vals[:-period])
            expected = len(vals[period:]) / vals.max()
            if matches > expected * 3:
                print(f"    Period {period}: {matches} matches vs {expected:.0f} expected -> {matches/expected:.1f}x")


def test_4_cross_reel_raw(df):
    """Do raw positions on different reels in the SAME spin correlate?"""
    print("\n" + "=" * 70)
    print("TEST 4: CROSS-REEL RAW POSITION CORRELATION (SAME SPIN)")
    print("=" * 70)

    from scipy.stats import pearsonr, spearmanr

    pairs = [('r1', 'r2'), ('r1', 'r3'), ('r2', 'r3')]
    for a, b in pairs:
        r_pearson, p_pearson = pearsonr(df[a], df[b])
        r_spearman, p_spearman = spearmanr(df[a], df[b])
        print(f"\n  {a} vs {b}:")
        print(f"    Pearson:  r={r_pearson:.4f}, p={p_pearson:.2e}")
        print(f"    Spearman: r={r_spearman:.4f}, p={p_spearman:.2e}")

    # Also: does r1+r2+r3 (sum of raw positions) predict VT?
    if 'is_valuable' in df.columns:
        df_temp = df.copy()
        df_temp['raw_sum'] = df_temp['r1'] + df_temp['r2'] + df_temp['r3']
        base_rate = df_temp['is_valuable'].mean()

        print(f"\n  Raw position sum -> VT rate (base: {base_rate*100:.2f}%):")
        bins = pd.qcut(df_temp['raw_sum'], 10, duplicates='drop')
        for name, group in df_temp.groupby(bins, observed=True):
            vt_rate = group['is_valuable'].mean()
            lift = vt_rate / base_rate if base_rate > 0 else 0
            n = len(group)
            print(f"    sum {name}: {vt_rate*100:.2f}% ({n} spins, {lift:.2f}x lift)")


def test_5_bet_change_vt(df):
    """Does CHANGING your bet correlate with VT on the next spin?
    This tests whether the RNG reseeds on bet change."""
    print("\n" + "=" * 70)
    print("TEST 5: BET CHANGE -> VT CORRELATION")
    print("=" * 70)

    if 'bet_multiplier' not in df.columns:
        print("  No bet_multiplier column found")
        return

    bm = df['bet_multiplier'].values
    vt = df['is_valuable'].values

    # Detect bet changes
    bet_changed = np.zeros(len(df), dtype=bool)
    bet_changed[1:] = bm[1:] != bm[:-1]

    base_rate = vt.mean()
    n_changed = bet_changed.sum()
    n_unchanged = (~bet_changed).sum()

    # VT rate on spin where bet was just changed
    vt_on_change = vt[bet_changed].mean() if n_changed > 0 else 0
    vt_on_same = vt[~bet_changed].mean() if n_unchanged > 0 else 0

    print(f"\n  Base VT rate: {base_rate*100:.2f}%")
    print(f"  Bet changed this spin: {n_changed} spins, VT rate: {vt_on_change*100:.2f}% ({vt_on_change/base_rate:.2f}x)")
    print(f"  Bet unchanged:         {n_unchanged} spins, VT rate: {vt_on_same*100:.2f}% ({vt_on_same/base_rate:.2f}x)")

    # What about bet INCREASE specifically?
    bet_increased = np.zeros(len(df), dtype=bool)
    bet_increased[1:] = bm[1:] > bm[:-1]
    bet_decreased = np.zeros(len(df), dtype=bool)
    bet_decreased[1:] = bm[1:] < bm[:-1]

    n_inc = bet_increased.sum()
    n_dec = bet_decreased.sum()

    if n_inc > 0:
        vt_inc = vt[bet_increased].mean()
        print(f"\n  Bet INCREASED: {n_inc} spins, VT rate: {vt_inc*100:.2f}% ({vt_inc/base_rate:.2f}x)")
    if n_dec > 0:
        vt_dec = vt[bet_decreased].mean()
        print(f"  Bet DECREASED: {n_dec} spins, VT rate: {vt_dec*100:.2f}% ({vt_dec/base_rate:.2f}x)")

    # How about VT within N spins AFTER a bet change?
    print(f"\n  VT rate within N spins after ANY bet change:")
    for window in [1, 2, 3, 5, 10]:
        change_indices = np.where(bet_changed)[0]
        target_spins = set()
        for idx in change_indices:
            for offset in range(1, window + 1):
                if idx + offset < len(df):
                    target_spins.add(idx + offset)
        target_spins = list(target_spins)
        if len(target_spins) > 0:
            vt_rate = vt[target_spins].mean()
            print(f"    Within {window:2d} spins: {vt_rate*100:.2f}% ({len(target_spins)} spins, {vt_rate/base_rate:.2f}x)")

    # Does the DIRECTION of bet change matter?
    print(f"\n  Bet change by direction and magnitude:")
    if n_changed > 10:
        changes = bm[1:].astype(float) / np.maximum(bm[:-1].astype(float), 1)
        changes = np.concatenate([[1.0], changes])  # pad first

        big_increase = changes >= 5  # 5x+ increase
        if big_increase.sum() > 0:
            print(f"    Big increase (5x+): {big_increase.sum()} spins, VT rate: {vt[big_increase].mean()*100:.2f}%")

        big_decrease = changes <= 0.2  # 5x+ decrease
        if big_decrease.sum() > 0:
            print(f"    Big decrease (5x+): {big_decrease.sum()} spins, VT rate: {vt[big_decrease].mean()*100:.2f}%")


def test_6_autocorrelation(df):
    """Autocorrelation of raw r1 positions. True random = near zero at all lags."""
    print("\n" + "=" * 70)
    print("TEST 6: AUTOCORRELATION OF RAW POSITIONS")
    print("=" * 70)

    for reel_name in ['r1', 'r2', 'r3']:
        vals = df[reel_name].values.astype(float)
        vals = (vals - vals.mean()) / vals.std()

        print(f"\n  {reel_name} autocorrelation:")
        n = len(vals)
        significant = []
        for lag in range(1, 51):
            acf = np.corrcoef(vals[:-lag], vals[lag:])[0, 1]
            threshold = 2 / np.sqrt(n)  # 95% confidence
            flag = " ***" if abs(acf) > threshold else ""
            if abs(acf) > threshold:
                significant.append(lag)
            if lag <= 20 or flag:
                print(f"    lag {lag:3d}: {acf:+.4f}{flag}")

        if significant:
            print(f"  SIGNIFICANT lags: {significant}")
        else:
            print(f"  No significant autocorrelation (looks random)")


def test_7_raw_state_vt_prediction(df):
    """Can the raw position state (r1, r2, r3) of spin N predict if spin N+1 is VT?"""
    print("\n" + "=" * 70)
    print("TEST 7: RAW POSITION STATE -> NEXT SPIN VT")
    print("=" * 70)

    vt = df['is_valuable'].values
    r1 = df['r1'].values
    r2 = df['r2'].values
    r3 = df['r3'].values
    base_rate = vt.mean()

    # Single raw position -> next VT
    print(f"\n  Base VT rate: {base_rate*100:.2f}%")
    print(f"\n  Previous r1 raw position -> next VT rate:")

    best_singles = []
    for pos in range(int(r1.max()) + 1):
        mask = np.zeros(len(df), dtype=bool)
        mask[:-1] = r1[:-1] == pos
        n = mask.sum()
        if n >= 30:
            rate = vt[mask].mean()
            lift = rate / base_rate
            if abs(lift - 1) > 0.3:
                best_singles.append((pos, n, rate, lift))
                print(f"    r1={pos:2d}: {rate*100:.2f}% ({n} spins, {lift:.2f}x)")

    if not best_singles:
        print("    No individual raw position shows >30% lift")

    # Raw sum of previous spin -> next VT
    print(f"\n  Previous spin raw sum (r1+r2+r3) -> next VT rate:")
    raw_sum = r1 + r2 + r3
    prev_sum = np.zeros(len(df))
    prev_sum[1:] = raw_sum[:-1]

    df_temp = pd.DataFrame({'prev_sum': prev_sum, 'vt': vt})
    df_temp = df_temp.iloc[1:]  # skip first
    bins = pd.qcut(df_temp['prev_sum'], 10, duplicates='drop')
    for name, group in df_temp.groupby(bins, observed=True):
        rate = group['vt'].mean()
        lift = rate / base_rate
        n = len(group)
        flag = " ***" if abs(lift - 1) > 0.3 else ""
        print(f"    sum {name}: {rate*100:.2f}% ({n} spins, {lift:.2f}x){flag}")

    # Raw position PAIR of previous spin -> next VT (just r1, r2)
    print(f"\n  Previous (r1, r2) raw pair -> next VT (top 20 by lift, n>=20):")
    results = []
    for p1 in range(int(r1.max()) + 1):
        for p2 in range(int(r2.max()) + 1):
            mask = np.zeros(len(df), dtype=bool)
            mask[:-1] = (r1[:-1] == p1) & (r2[:-1] == p2)
            n = mask.sum()
            if n >= 20:
                rate = vt[mask].mean()
                lift = rate / base_rate
                results.append((p1, p2, n, rate, lift))

    results.sort(key=lambda x: -x[4])
    for p1, p2, n, rate, lift in results[:20]:
        print(f"    r1={p1:2d}, r2={p2:2d}: {rate*100:.2f}% ({n} spins, {lift:.2f}x)")


def test_8_modular_tricks(df):
    """Test modular arithmetic relationships that might reveal RNG structure.
    If the game uses a single RNG and derives r1/r2/r3 from it, there might
    be mathematical relationships between them."""
    print("\n" + "=" * 70)
    print("TEST 8: MODULAR ARITHMETIC / RNG STRUCTURE")
    print("=" * 70)

    r1 = df['r1'].values.astype(int)
    r2 = df['r2'].values.astype(int)
    r3 = df['r3'].values.astype(int)
    vt = df['is_valuable'].values
    base_rate = vt.mean()

    # Test: (r1 + r2 + r3) mod K for various K
    print("\n  (r1 + r2 + r3) mod K -> VT rate:")
    for k in [3, 5, 7, 9, 10, 11, 13, 31]:
        mod_val = (r1 + r2 + r3) % k
        print(f"\n    mod {k}:")
        for v in range(k):
            mask = mod_val == v
            n = mask.sum()
            if n > 0:
                rate = vt[mask].mean()
                lift = rate / base_rate
                flag = " ***" if abs(lift - 1) > 0.4 else ""
                print(f"      {v}: {rate*100:.2f}% ({n} spins, {lift:.2f}x){flag}")

    # Test: (r1 * r2 + r3) mod K
    print("\n  (r1 * r2 + r3) mod K -> VT rate:")
    for k in [7, 11, 13, 31]:
        mod_val = (r1 * r2 + r3) % k
        best_lift = 0
        best_v = 0
        for v in range(k):
            mask = mod_val == v
            n = mask.sum()
            if n > 30:
                rate = vt[mask].mean()
                lift = rate / base_rate
                if lift > best_lift:
                    best_lift = lift
                    best_v = v
        if best_lift > 1.3:
            print(f"    mod {k}: best residue {best_v} -> {best_lift:.2f}x lift")
        else:
            print(f"    mod {k}: max lift {best_lift:.2f}x (noise)")

    # Test: XOR-based combinations
    print("\n  r1 XOR r2 XOR r3 -> VT rate:")
    xor_val = r1 ^ r2 ^ r3
    for v in sorted(set(xor_val)):
        mask = xor_val == v
        n = mask.sum()
        if n >= 50:
            rate = vt[mask].mean()
            lift = rate / base_rate
            if abs(lift - 1) > 0.4:
                print(f"    XOR={v:2d}: {rate*100:.2f}% ({n} spins, {lift:.2f}x) ***")

    # Test: difference patterns d1 = r2-r1, d2 = r3-r2
    print("\n  (r2-r1, r3-r2) difference pattern -> VT rate (top lifts, n>=30):")
    d1 = r2 - r1
    d2 = r3 - r2
    results = []
    for v1 in sorted(set(d1)):
        for v2 in sorted(set(d2)):
            mask = (d1 == v1) & (d2 == v2)
            n = mask.sum()
            if n >= 30:
                rate = vt[mask].mean()
                lift = rate / base_rate
                results.append((v1, v2, n, rate, lift))
    results.sort(key=lambda x: -x[4])
    for v1, v2, n, rate, lift in results[:10]:
        print(f"    d1={v1:+3d}, d2={v2:+3d}: {rate*100:.2f}% ({n} spins, {lift:.2f}x)")


def test_9_sequential_raw_lcg(df):
    """More sophisticated LCG test: treat (r1,r2,r3) as a single
    combined state and look for linear recurrence across spins."""
    print("\n" + "=" * 70)
    print("TEST 9: COMBINED STATE SEQUENTIAL LCG")
    print("=" * 70)

    r1 = df['r1'].values.astype(np.int64)
    r2 = df['r2'].values.astype(np.int64)
    r3 = df['r3'].values.astype(np.int64)

    # Encode full state as single number: r1*31*31 + r2*31 + r3
    # (assuming max strip position is 30, so 31 values)
    max_pos = max(r1.max(), r2.max(), r3.max()) + 1
    state = r1 * max_pos * max_pos + r2 * max_pos + r3

    print(f"\n  State space size: {max_pos}^3 = {max_pos**3}")
    print(f"  Unique states observed: {len(set(state))}")
    print(f"  Total spins: {len(state)}")

    # If states repeat, check what comes AFTER
    from collections import defaultdict
    next_state = defaultdict(list)
    for i in range(len(state) - 1):
        next_state[state[i]].append(state[i + 1])

    # How deterministic is the transition?
    deterministic_count = 0
    total_repeated = 0
    for s, nexts in next_state.items():
        if len(nexts) >= 2:
            total_repeated += 1
            if len(set(nexts)) == 1:
                deterministic_count += 1

    print(f"\n  States that appeared 2+ times: {total_repeated}")
    print(f"  Of those, states with DETERMINISTIC next state: {deterministic_count}")
    if total_repeated > 0:
        print(f"  Determinism rate: {deterministic_count/total_repeated*100:.1f}%")
        if deterministic_count / total_repeated > 0.5:
            print(f"  *** HIGH DETERMINISM - RNG STATE IS PARTIALLY OBSERVABLE! ***")

    # Check: when same state repeats, is the VT outcome the same?
    vt = df['is_valuable'].values
    vt_by_state = defaultdict(list)
    for i in range(len(state)):
        vt_by_state[state[i]].append(vt[i])

    consistent_vt = 0
    total_vt_repeat = 0
    for s, vts in vt_by_state.items():
        if len(vts) >= 2:
            total_vt_repeat += 1
            if len(set(vts)) == 1:
                consistent_vt += 1

    print(f"\n  States with 2+ occurrences: {total_vt_repeat}")
    print(f"  VT outcome always same for state: {consistent_vt} ({consistent_vt/total_vt_repeat*100:.1f}%)")


def test_10_timing_pattern(df):
    """Do VTs cluster at specific positions modulo some cycle length?"""
    print("\n" + "=" * 70)
    print("TEST 10: VT TIMING / CYCLE DETECTION")
    print("=" * 70)

    vt_indices = np.where(df['is_valuable'].values)[0]
    base_rate = df['is_valuable'].mean()
    n_total = len(df)

    print(f"\n  Total VTs: {len(vt_indices)}, base rate: {base_rate*100:.2f}%")

    # Test: VT rate at position mod K
    print("\n  VT rate by spin_number mod K:")
    for k in [10, 25, 31, 50, 100, 127, 200]:
        positions = np.arange(n_total) % k
        best_lift = 0
        worst_lift = 999
        best_pos = 0
        for p in range(k):
            mask = positions == p
            n = mask.sum()
            if n > 0:
                rate = df['is_valuable'].values[mask].mean()
                lift = rate / base_rate
                if lift > best_lift:
                    best_lift = lift
                    best_pos = p
                if lift < worst_lift:
                    worst_lift = lift

        spread = best_lift - worst_lift
        flag = " ***" if spread > 0.5 else ""
        print(f"    mod {k:3d}: best pos {best_pos} at {best_lift:.2f}x, worst {worst_lift:.2f}x, spread {spread:.2f}{flag}")

    # VT gap analysis: are gaps between VTs from a known distribution?
    gaps = np.diff(vt_indices)
    print(f"\n  VT gap statistics:")
    print(f"    Mean gap: {gaps.mean():.1f}")
    print(f"    Median gap: {np.median(gaps):.1f}")
    print(f"    Std gap: {gaps.std():.1f}")
    print(f"    Min gap: {gaps.min()}")
    print(f"    Max gap: {gaps.max()}")

    # If gaps were geometric (memoryless), std ~= mean
    # If there's a cycle/pattern, std would be lower
    cv = gaps.std() / gaps.mean()
    print(f"    CV (std/mean): {cv:.3f}")
    print(f"    Geometric (random) would have CV ~= 1.0")
    if cv < 0.7:
        print(f"    *** CV < 0.7 - gaps are MORE REGULAR than random! ***")
    elif cv > 1.3:
        print(f"    *** CV > 1.3 - gaps are MORE CLUSTERED than random! ***")

    # Gap distribution: does it match geometric?
    print(f"\n  Gap distribution vs geometric expectation:")
    for threshold in [10, 20, 30, 50, 80, 100, 150, 200]:
        observed_pct = (gaps <= threshold).mean() * 100
        expected_pct = (1 - (1 - base_rate) ** threshold) * 100
        ratio = observed_pct / expected_pct if expected_pct > 0 else 0
        flag = " ***" if abs(ratio - 1) > 0.1 else ""
        print(f"    gap <= {threshold:3d}: observed {observed_pct:.1f}%, expected {expected_pct:.1f}% (ratio {ratio:.2f}){flag}")


if __name__ == '__main__':
    print("Loading all spin data with RAW positions...", file=sys.stderr)
    df = load_all_data()
    print(f"\nTotal: {len(df)} spins, {df['is_valuable'].sum()} VTs", file=sys.stderr)

    # Run by account too to check consistency
    for acct in df['account'].unique():
        sub = df[df['account'] == acct]
        print(f"  {acct}: {len(sub)} spins, {sub['is_valuable'].sum()} VTs, r1 range [{sub['r1'].min()}-{sub['r1'].max()}]", file=sys.stderr)

    test_1_raw_position_distribution(df)
    test_2_delta_patterns(df)
    test_3_lcg_detection(df)
    test_4_cross_reel_raw(df)
    test_5_bet_change_vt(df)
    test_6_autocorrelation(df)
    test_7_raw_state_vt_prediction(df)
    test_8_modular_tricks(df)
    test_9_sequential_raw_lcg(df)
    test_10_timing_pattern(df)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("If ANY test above shows strong non-random structure,")
    print("the RNG is potentially crackable and exact-spin prediction")
    print("becomes possible by observing consecutive raw positions.")
