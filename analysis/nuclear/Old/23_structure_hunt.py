"""
Hunt for hidden structure in the gap sequences using stronger statistical tests.

Tests:
1. Hurst exponent (R/S analysis) — H=0.5 random walk, H<0.5 mean-reverting, H>0.5 trending
2. Distribution shape — fit exponential and check goodness; deviation = structure
3. Symbol composition — long vs short gaps, what symbols dominate?
4. Cross-target correlation — does ACC gap length co-vary with SPN/ATK/STL/SHD gap lengths?
5. Prev-triple conditional — full matrix of P(next ACC gap | prev real triple)
6. Distribution percentile bins — does the conditional distribution look different
   in different deciles?
"""
import pickle
import math
from collections import defaultdict, Counter

with open('analysis/nuclear/gaps.pkl', 'rb') as f:
    data = pickle.load(f)


def mean(arr):
    return sum(arr) / len(arr) if arr else 0.0


def stdev(arr):
    if len(arr) < 2:
        return 0.0
    m = mean(arr)
    return math.sqrt(sum((x - m) ** 2 for x in arr) / len(arr))


def corr(pairs):
    n = len(pairs)
    if n < 4:
        return None
    sx = sum(p[0] for p in pairs); sy = sum(p[1] for p in pairs)
    sxx = sum(p[0] ** 2 for p in pairs); sxy = sum(p[0] * p[1] for p in pairs)
    syy = sum(p[1] ** 2 for p in pairs)
    mx, my = sx / n, sy / n
    num = sxy - n * mx * my
    den = ((sxx - n * mx * mx) * (syy - n * my * my)) ** 0.5
    return num / den if den > 0 else 0


def hurst_rs(arr):
    """Rescaled-range Hurst exponent. H=0.5 random, <0.5 mean-revert, >0.5 trend."""
    arr = list(arr)
    N = len(arr)
    if N < 16:
        return None
    # Use chunk sizes that divide N reasonably
    sizes = []
    s = 8
    while s <= N // 2:
        sizes.append(s)
        s = int(s * 1.5)
    if not sizes:
        return None

    points = []  # (log size, log R/S avg)
    for n in sizes:
        chunks = N // n
        if chunks < 1:
            continue
        rs_vals = []
        for c in range(chunks):
            chunk = arr[c * n:(c + 1) * n]
            m = mean(chunk)
            dev = [x - m for x in chunk]
            cum = []
            running = 0.0
            for d in dev:
                running += d
                cum.append(running)
            R = max(cum) - min(cum)
            S = stdev(chunk)
            if S > 0:
                rs_vals.append(R / S)
        if rs_vals:
            points.append((math.log(n), math.log(mean(rs_vals))))

    if len(points) < 3:
        return None
    n = len(points)
    sx = sum(p[0] for p in points); sy = sum(p[1] for p in points)
    sxx = sum(p[0] ** 2 for p in points); sxy = sum(p[0] * p[1] for p in points)
    mx, my = sx / n, sy / n
    den = sxx - n * mx * mx
    if den == 0:
        return None
    return (sxy - n * mx * my) / den


def variance_ratio(arr, k):
    """Variance ratio test: var(sum of k) / (k * var(1)).
    iid -> 1.0; mean-reverting -> < 1.0; trending -> > 1.0."""
    n = len(arr)
    if n < k * 4:
        return None
    var1 = stdev(arr) ** 2
    if var1 == 0:
        return None
    sums = [sum(arr[i:i + k]) for i in range(n - k + 1)]
    var_k = stdev(sums) ** 2
    return var_k / (k * var1)


print('=' * 78)
print('TEST 1: HURST EXPONENT (R/S analysis)')
print('  H=0.5: random walk (iid)')
print('  H<0.5: mean-reverting')
print('  H>0.5: trending / persistent')
print('=' * 78)
for acct in ['Ahmed', 'Islam', 'Nick']:
    seq = [g['length'] for g in data[acct]['gaps']['accumulation']]
    H = hurst_rs(seq)
    print('  {}: n={:3d}  H = {}'.format(
        acct, len(seq), '{:.3f}'.format(H) if H is not None else 'n/a'))

print()
print('TEST 1b: VARIANCE RATIO (at multiple horizons)')
print('  iid -> 1.0   |   mean-reverting -> < 1.0   |   trending -> > 1.0')
for acct in ['Ahmed', 'Islam', 'Nick']:
    seq = [g['length'] for g in data[acct]['gaps']['accumulation']]
    print('  {}:'.format(acct))
    for k in [2, 3, 5, 8, 12, 20]:
        vr = variance_ratio(seq, k)
        if vr is not None:
            print('    k={:2d}: VR = {:.3f}'.format(k, vr))

print()
print('=' * 78)
print('TEST 2: DISTRIBUTION SHAPE — is gap length exponentially distributed?')
print('  An iid memoryless RNG produces exponential gaps. Deviation = structure.')
print('=' * 78)
for acct in ['Ahmed', 'Islam', 'Nick']:
    seq = sorted(g['length'] for g in data[acct]['gaps']['accumulation'])
    n = len(seq)
    m = mean(seq)
    sd = stdev(seq)
    # For an exponential distribution: mean = stdev. CV = stdev/mean = 1.0
    cv = sd / m if m > 0 else 0
    # Skewness (sample)
    skew = sum((x - m) ** 3 for x in seq) / (n * sd ** 3) if sd > 0 else 0
    # Empirical percentiles vs exponential percentiles
    print('  {}: n={}  mean={:.1f}  stdev={:.1f}  CV={:.3f} (exp=1.0)  skew={:.2f} (exp=2.0)'.format(
        acct, n, m, sd, cv, skew))
    # Show deciles vs exponential expectation
    print('    decile cutoffs (actual vs exponential expected with same mean):')
    for p in [0.1, 0.25, 0.5, 0.75, 0.9, 0.95]:
        actual = seq[min(n - 1, int(p * n))]
        # Exponential CDF: F(x) = 1 - exp(-x/m); inverse: x = -m*ln(1-p)
        expected = -m * math.log(1 - p)
        print('      p={:.2f}: actual={:6.1f}  exp_expected={:6.1f}  diff={:+6.1f}'.format(
            p, actual, expected, actual - expected))

print()
print('=' * 78)
print('TEST 3: SYMBOL COMPOSITION — long vs short gaps differ?')
print('=' * 78)
for acct in ['Ahmed', 'Islam', 'Nick']:
    gaps = data[acct]['gaps']['accumulation']
    seq = [g['length'] for g in gaps]
    m = mean(seq)
    sd = stdev(seq)
    short_cut = m - 0.5 * sd
    long_cut = m + 0.5 * sd
    short = [g for g in gaps if g['length'] <= short_cut]
    longg = [g for g in gaps if g['length'] >= long_cut]
    if not short or not longg:
        continue
    # Average per-spin counts of each symbol type in short vs long gaps
    def comp(bucket):
        out = {'atk': 0, 'stl': 0, 'shd': 0, 'spn': 0, 'acc_partial': 0}
        spins = 0
        for g in bucket:
            for s in g['trajectory'][:-1]:  # exclude the closing acc-triple spin
                spins += 1
                out['atk'] += s['atk_count']
                out['stl'] += s['stl_count']
                out['shd'] += s['shd_count']
                out['spn'] += s['spn_count']
                out['acc_partial'] += s['acc_count']
        return spins, {k: v / spins for k, v in out.items()} if spins > 0 else None

    spins_s, comp_s = comp(short)
    spins_l, comp_l = comp(longg)
    print('  {}: short_cut={:.0f} (n={}, spins={})   long_cut={:.0f} (n={}, spins={})'.format(
        acct, short_cut, len(short), spins_s, long_cut, len(longg), spins_l))
    if comp_s and comp_l:
        print('    {:>12} {:>10} {:>10} {:>10}'.format('symbol', 'short/spin', 'long/spin', 'ratio L/S'))
        for k in ['atk', 'stl', 'shd', 'spn', 'acc_partial']:
            ratio = comp_l[k] / comp_s[k] if comp_s[k] > 0 else 0
            mark = ' <-- diff' if abs(ratio - 1) > 0.10 else ''
            print('    {:>12} {:>10.3f} {:>10.3f} {:>10.3f}{}'.format(k, comp_s[k], comp_l[k], ratio, mark))

print()
print('=' * 78)
print('TEST 4: CROSS-TARGET CORRELATION — do ACC gaps share state with other triples?')
print('  For each ACC gap, count how many SPN/ATK/STL/SHD triples landed inside it.')
print('=' * 78)
for acct in ['Ahmed', 'Islam', 'Nick']:
    gaps = data[acct]['gaps']['accumulation']
    rows = []
    for g in gaps:
        traj = g['trajectory']
        cnt_spn = sum(1 for s in traj if s['triple'] == 'spins')
        cnt_atk = sum(1 for s in traj if s['triple'] == 'attack')
        cnt_stl = sum(1 for s in traj if s['triple'] == 'steal')
        cnt_shd = sum(1 for s in traj if s['triple'] == 'shield')
        # Per-spin rates of each type during this ACC gap
        spins = max(1, g['length'])
        rows.append({
            'L': g['length'],
            'spn_per_100': cnt_spn / spins * 100,
            'atk_per_100': cnt_atk / spins * 100,
            'stl_per_100': cnt_stl / spins * 100,
            'shd_per_100': cnt_shd / spins * 100,
        })
    print('  {}: n={}'.format(acct, len(rows)))
    for k in ['spn_per_100', 'atk_per_100', 'stl_per_100', 'shd_per_100']:
        pairs = [(r[k], r['L']) for r in rows]
        r = corr(pairs)
        print('    r({}, ACC_gap_length) = {:+.3f}'.format(k, r))

print()
print('=' * 78)
print('TEST 5: PREV-TRIPLE CONDITIONAL — full matrix')
print('=' * 78)
for acct in ['Ahmed', 'Islam', 'Nick']:
    gaps = data[acct]['gaps']['accumulation']
    by_prev = defaultdict(list)
    for g in gaps:
        prev = g.get('prev_real_triple') or 'NONE'
        by_prev[prev].append(g['length'])
    overall = mean([g['length'] for g in gaps])
    print('  {}: overall mean ACC gap = {:.1f}'.format(acct, overall))
    for prev in sorted(by_prev.keys()):
        lens = by_prev[prev]
        if len(lens) < 3:
            continue
        m = mean(lens); sd = stdev(lens)
        delta = m - overall
        print('    prev={:>13s}  n={:3d}  mean={:6.1f}  delta={:+6.1f}  stdev={:.1f}'.format(
            prev, len(lens), m, delta, sd))

# Pool across accounts for prev-triple test
print()
print('  POOLED across all 3 accounts:')
by_prev = defaultdict(list)
overall_all = []
for acct in ['Ahmed', 'Islam', 'Nick']:
    for g in data[acct]['gaps']['accumulation']:
        prev = g.get('prev_real_triple') or 'NONE'
        by_prev[prev].append(g['length'])
        overall_all.append(g['length'])
overall_mean = mean(overall_all)
print('    overall mean = {:.1f}'.format(overall_mean))
for prev in sorted(by_prev.keys()):
    lens = by_prev[prev]
    m = mean(lens); sd = stdev(lens)
    print('    prev={:>13s}  n={:3d}  mean={:6.1f}  delta={:+6.1f}  stdev={:.1f}'.format(
        prev, len(lens), m, m - overall_mean, sd))
