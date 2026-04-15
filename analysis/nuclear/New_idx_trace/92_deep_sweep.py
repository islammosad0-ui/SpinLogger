"""
92_deep_sweep.py — Exhaustive signal search for VT prediction

Target: >=10% precision (<=10 bets/hit) with HIGH catch rate
Base rate: ~2.2% → need ~4.6x+ lift

Angles explored:
  1. Multi-lag idx features (lag 1-10)
  2. Rolling windows (3, 5, 7, 10 spin averages/sums)
  3. Idx momentum/velocity/acceleration
  4. Modular arithmetic (mod 2, 3, 4)
  5. High/Med/Low zone classification
  6. Gap-conditioned idx distributions (does idx behave differently at high gap?)
  7. Streak/run detection
  8. Entropy/diversity of recent idx
  9. Autocorrelation features
  10. Cumulative idx sum patterns
  11. Three-spin trigrams
  12. Near-miss aftermath (2-5 spins after near-miss)
  13. Parity sequences
  14. Score-based multi-signal fusion
  15. Exhaustive 2-3 feature combo sweep
  16. Phase detection from idx patterns
  17. sa_ counter × idx interactions
  18. Position-specific conditional distributions
  19. Post-triple idx behavior
  20. Bayesian posterior scoring
"""

import csv, os, sys
from collections import Counter, defaultdict
from math import sqrt, log, exp
from itertools import combinations

# ─── Strip ───
STRIP = {0:'attack', 1:'coin', 2:'shield', 3:'goldSack', 4:'steal',
         5:'coin', 6:'spins', 7:'goldSack', 8:'accumulation'}
IDX_SYM = {i: s for i, s in STRIP.items()}

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data')
FILES = [
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_enriched_v2.csv')),
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_2026-04-13.csv')),
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_2026-04-14.csv')),
    ('Islam', os.path.join(DATA_DIR, 'Islam', 'spin_history_Islam_2026-04-13.csv')),
    ('Nick',  os.path.join(DATA_DIR, 'Nick',  'spin_history_Nick_2026-04-13.csv')),
]


def load():
    rows = []
    for acct, path in FILES:
        with open(path) as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    r1i, r2i, r3i = int(r['r1_idx']), int(r['r2_idx']), int(r['r3_idx'])
                except (ValueError, KeyError):
                    continue
                if any(x not in STRIP for x in (r1i, r2i, r3i)):
                    continue
                reel_1 = r.get('reel_1', '')
                is_triple = r.get('is_triple', '').lower() == 'true'
                vt = None
                if is_triple:
                    if reel_1 == 'accumulation': vt = 'ACC'
                    elif reel_1 == 'spins': vt = 'SPN'

                rows.append({
                    'acct': acct,
                    'r1': r1i, 'r2': r2i, 'r3': r3i,
                    'sym1': IDX_SYM[r3i], 'sym2': IDX_SYM[r2i], 'sym3': IDX_SYM[r1i],
                    'is_triple': is_triple, 'vt': vt,
                    'sum': r1i + r2i + r3i,
                    'spread': max(r1i, r2i, r3i) - min(r1i, r2i, r3i),
                    'sa_spn': int(r['sa_spn']) if r.get('sa_spn', '') else None,
                    'sa_acc': int(r['sa_acc']) if r.get('sa_acc', '') else None,
                    'sa_stl': int(r['sa_stl']) if r.get('sa_stl', '') else None,
                    'sa_spins': int(r['sa_spins']) if r.get('sa_spins', '') else None,
                    'sa_atk': int(r['sa_atk']) if r.get('sa_atk', '') else None,
                    'sa_shd': int(r['sa_shd']) if r.get('sa_shd', '') else None,
                })
    return rows


def add_deep_features(rows):
    """Add every conceivable pre-spin feature."""

    # ─── Gap tracking ───
    last_vt, last_acc, last_spn, last_trip = {}, {}, {}, {}
    for i, r in enumerate(rows):
        a = r['acct']
        r['gap_vt'] = i - last_vt.get(a, -999)
        r['gap_acc'] = i - last_acc.get(a, -999)
        r['gap_spn'] = i - last_spn.get(a, -999)
        r['gap_trip'] = i - last_trip.get(a, -999)
        if r['vt']:
            last_vt[a] = i
            if r['vt'] == 'ACC': last_acc[a] = i
            if r['vt'] == 'SPN': last_spn[a] = i
        if r['is_triple']:
            last_trip[a] = i

    # ─── Multi-lag features (lag 1-10) ───
    for lag in range(1, 11):
        for i in range(lag, len(rows)):
            if rows[i]['acct'] != rows[i-lag]['acct']:
                continue
            p = rows[i-lag]
            pref = f'L{lag}'
            rows[i][f'{pref}_r1'] = p['r1']
            rows[i][f'{pref}_r2'] = p['r2']
            rows[i][f'{pref}_r3'] = p['r3']
            rows[i][f'{pref}_sum'] = p['sum']
            rows[i][f'{pref}_spread'] = p['spread']
            rows[i][f'{pref}_triple'] = p['is_triple']
            rows[i][f'{pref}_vt'] = p['vt'] is not None
            rows[i][f'{pref}_sym1'] = p['sym1']
            rows[i][f'{pref}_sym2'] = p['sym2']
            rows[i][f'{pref}_sym3'] = p['sym3']

    # ─── Rolling windows ───
    for win in [3, 5, 7, 10]:
        for i in range(win, len(rows)):
            if any(rows[i-j]['acct'] != rows[i]['acct'] for j in range(1, win)):
                continue
            window = [rows[i-j] for j in range(1, win+1)]  # prev spins only
            sums = [w['sum'] for w in window]
            r1s = [w['r1'] for w in window]
            r2s = [w['r2'] for w in window]
            r3s = [w['r3'] for w in window]
            spreads = [w['spread'] for w in window]
            triples = sum(1 for w in window if w['is_triple'])
            vts = sum(1 for w in window if w['vt'])

            rows[i][f'W{win}_mean_sum'] = sum(sums) / win
            rows[i][f'W{win}_max_sum'] = max(sums)
            rows[i][f'W{win}_min_sum'] = min(sums)
            rows[i][f'W{win}_std_sum'] = (sum((s - sum(sums)/win)**2 for s in sums) / win) ** 0.5
            rows[i][f'W{win}_mean_r1'] = sum(r1s) / win
            rows[i][f'W{win}_mean_r2'] = sum(r2s) / win
            rows[i][f'W{win}_mean_r3'] = sum(r3s) / win
            rows[i][f'W{win}_mean_spread'] = sum(spreads) / win
            rows[i][f'W{win}_triples'] = triples
            rows[i][f'W{win}_vts'] = vts
            rows[i][f'W{win}_triple_rate'] = triples / win

            # Unique symbols in window
            all_syms = []
            for w in window:
                all_syms.extend([w['sym1'], w['sym2'], w['sym3']])
            rows[i][f'W{win}_unique_syms'] = len(set(all_syms))

            # Unique idx values in window
            all_idx = []
            for w in window:
                all_idx.extend([w['r1'], w['r2'], w['r3']])
            rows[i][f'W{win}_unique_idx'] = len(set(all_idx))
            rows[i][f'W{win}_idx_entropy'] = _entropy(all_idx)

            # Streak: consecutive same idx on any reel
            rows[i][f'W{win}_r2_streak'] = _streak(r2s)

            # Near-miss count in window
            nm = 0
            for w in window:
                syms = [w['sym1'], w['sym2'], w['sym3']]
                if max(Counter(syms).values()) == 2:
                    nm += 1
            rows[i][f'W{win}_near_miss'] = nm

            # Parity pattern
            parity = [(w['r1'] + w['r2'] + w['r3']) % 2 for w in window]
            rows[i][f'W{win}_parity_run'] = _max_run(parity)

    # ─── Momentum/velocity/acceleration ───
    for i in range(3, len(rows)):
        if rows[i]['acct'] != rows[i-1]['acct'] or rows[i-1]['acct'] != rows[i-2]['acct']:
            continue
        if rows[i-2]['acct'] != rows[i-3]['acct']:
            continue
        d1 = rows[i-1]['sum'] - rows[i-2]['sum']
        d2 = rows[i-2]['sum'] - rows[i-3]['sum']
        rows[i]['velocity'] = d1
        rows[i]['accel'] = d1 - d2
        rows[i]['momentum_3'] = rows[i-1]['sum'] + rows[i-2]['sum'] + rows[i-3]['sum']

    # ─── Modular features ───
    for i in range(1, len(rows)):
        if rows[i]['acct'] != rows[i-1]['acct']:
            continue
        p = rows[i-1]
        rows[i]['p_sum_mod2'] = p['sum'] % 2
        rows[i]['p_sum_mod3'] = p['sum'] % 3
        rows[i]['p_sum_mod4'] = p['sum'] % 4
        rows[i]['p_sum_mod9'] = p['sum'] % 9
        rows[i]['p_r1_mod3'] = p['r1'] % 3
        rows[i]['p_r2_mod3'] = p['r2'] % 3
        rows[i]['p_r3_mod3'] = p['r3'] % 3

        # High/Med/Low zone (0-2=L, 3-5=M, 6-8=H)
        rows[i]['p_r1_zone'] = 'L' if p['r1'] <= 2 else ('M' if p['r1'] <= 5 else 'H')
        rows[i]['p_r2_zone'] = 'L' if p['r2'] <= 2 else ('M' if p['r2'] <= 5 else 'H')
        rows[i]['p_r3_zone'] = 'L' if p['r3'] <= 2 else ('M' if p['r3'] <= 5 else 'H')
        rows[i]['p_zone_combo'] = rows[i]['p_r1_zone'] + rows[i]['p_r2_zone'] + rows[i]['p_r3_zone']

        # Specific idx value presence
        for idx_val in range(9):
            rows[i][f'p_has_{idx_val}'] = idx_val in (p['r1'], p['r2'], p['r3'])

        # Pair/near-miss type on previous
        syms = [p['sym1'], p['sym2'], p['sym3']]
        c = Counter(syms)
        most = c.most_common(1)[0]
        rows[i]['p_dominant_sym'] = most[0]
        rows[i]['p_dominant_count'] = most[1]

        # sa_ deltas if available
        if p['sa_acc'] is not None and rows[i].get('sa_acc') is not None:
            pass  # sa_ counters are cumulative within session, not per-spin

    # ─── Cumulative idx tracking ───
    cum_sum = {}
    cum_count = {}
    for i, r in enumerate(rows):
        a = r['acct']
        if a not in cum_sum:
            cum_sum[a] = 0
            cum_count[a] = 0
        cum_sum[a] += r['sum']
        cum_count[a] += 1
        r['cum_avg_sum'] = cum_sum[a] / cum_count[a]
        r['cum_sum_mod'] = cum_sum[a] % 27  # 3*9
        r['spin_in_session'] = cum_count[a]

    # ─── Post-triple/post-VT idx patterns ───
    for i in range(1, len(rows)):
        if rows[i]['acct'] != rows[i-1]['acct']:
            continue
        rows[i]['after_triple'] = rows[i-1]['is_triple']
        rows[i]['after_vt'] = rows[i-1]['vt'] is not None
        if rows[i-1]['is_triple']:
            rows[i]['post_triple_type'] = rows[i-1].get('sym1', '')  # what was the triple symbol

    # ─── Gap-conditioned features ───
    # Does idx distribution differ at high gap?
    for i, r in enumerate(rows):
        if 'L1_sum' not in r:
            continue
        # Interaction: gap_zone × prev_sum
        g = r['gap_vt']
        r['gap_zone'] = 'early' if g < 20 else ('mid' if g < 40 else ('late' if g < 60 else 'deep'))
        r['gap_x_psum'] = f"{r['gap_zone']}_{r['L1_sum']}"

    return rows


def _entropy(vals):
    """Shannon entropy of a list of values."""
    c = Counter(vals)
    n = len(vals)
    if n == 0: return 0
    return -sum((v/n) * log(v/n + 1e-10) for v in c.values())


def _streak(vals):
    """Max consecutive same value."""
    if not vals: return 0
    mx = 1; cur = 1
    for i in range(1, len(vals)):
        if vals[i] == vals[i-1]:
            cur += 1
            mx = max(mx, cur)
        else:
            cur = 1
    return mx


def _max_run(vals):
    """Max run of same value."""
    return _streak(vals)


def pval(hits, bets, base):
    if bets == 0 or base == 0: return 1.0
    obs = hits / bets
    se = sqrt(base * (1 - base) / bets)
    if se == 0: return 1.0
    z = (obs - base) / se
    if z <= 0: return 1.0
    t = 1.0 / (1.0 + 0.2316419 * z)
    d = 0.3989422804 * (2.718281828 ** (-z * z / 2))
    return d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))


def test_strat(rows, cond, label, target_fn=None, min_hits=3):
    if target_fn is None:
        target_fn = lambda r: r['vt'] is not None
    n = len(rows)
    nt = sum(1 for r in rows if target_fn(r))
    base = nt / n if n > 0 else 0
    bets = hits = 0
    for r in rows:
        if cond(r):
            bets += 1
            if target_fn(r): hits += 1
    if bets == 0 or hits < min_hits: return None
    prec = hits / bets
    return {
        'l': label, 'b': bets, 'h': hits,
        'p': prec, 'x': prec / base if base else 0,
        'c': hits / nt if nt else 0,
        'bph': bets / hits if hits else 999,
        'pv': pval(hits, bets, base),
        'base': base, 'n': n, 'nt': nt,
    }


def show(results, title, max_bph=10, min_catch=0.0):
    results = [r for r in results if r]
    # Filter by target: bph <= max_bph
    good = [r for r in results if r['bph'] <= max_bph and r['c'] >= min_catch]
    rest = [r for r in results if r not in good]
    rest.sort(key=lambda x: x['pv'])

    print(f"\n{'='*120}")
    print(f"  {title}")
    if results:
        print(f"  {results[0]['n']} spins, {results[0]['nt']} targets, base={results[0]['base']:.2%}")
        print(f"  TARGET: bets/hit <= {max_bph}, catch >= {min_catch:.0%}")
    print(f"{'='*120}")

    if good:
        good.sort(key=lambda x: (-x['c'], x['bph']))  # best catch first, then efficient
        print(f"\n  >>> HITS TARGET (bph<={max_bph}) <<<")
        print(f"  {'Strategy':<65s} {'Prec':>6s} {'Lift':>5s} {'Catch':>6s} {'B/H':>5s} {'Bets':>5s} {'Hits':>4s} {'p-val':>8s}")
        print("  " + "-" * 115)
        for r in good[:50]:
            s = '***' if r['pv'] < 0.001 else '**' if r['pv'] < 0.01 else '*' if r['pv'] < 0.05 else ''
            print(f"  {r['l']:<65s} {r['p']:>5.1%} {r['x']:>5.1f}x {r['c']:>5.1%} "
                  f"{r['bph']:>5.1f} {r['b']:>5d} {r['h']:>4d} {r['pv']:>7.4f} {s}")
    else:
        print(f"\n  >>> NO STRATEGIES MET TARGET (bph<={max_bph}) <<<")

    # Show top 20 near-misses (close to target)
    close = [r for r in rest if r['bph'] <= max_bph * 1.5]
    if close:
        close.sort(key=lambda x: x['bph'])
        print(f"\n  --- Near-misses (bph {max_bph}-{max_bph*1.5:.0f}) ---")
        print(f"  {'Strategy':<65s} {'Prec':>6s} {'Lift':>5s} {'Catch':>6s} {'B/H':>5s} {'Bets':>5s} {'Hits':>4s} {'p-val':>8s}")
        print("  " + "-" * 115)
        for r in close[:20]:
            s = '***' if r['pv'] < 0.001 else '**' if r['pv'] < 0.01 else '*' if r['pv'] < 0.05 else ''
            print(f"  {r['l']:<65s} {r['p']:>5.1%} {r['x']:>5.1f}x {r['c']:>5.1%} "
                  f"{r['bph']:>5.1f} {r['b']:>5d} {r['h']:>4d} {r['pv']:>7.4f} {s}")


def run(rows):
    valid = [r for r in rows if 'L1_r1' in r]
    deep = [r for r in rows if 'W10_mean_sum' in r]
    print(f"Total spins: {len(rows)}, with lag-1: {len(valid)}, with W10: {len(deep)}")
    n_vt = sum(1 for r in deep if r['vt'])
    n_acc = sum(1 for r in deep if r['vt'] == 'ACC')
    n_spn = sum(1 for r in deep if r['vt'] == 'SPN')
    print(f"VTs in deep set: {n_vt} (ACC: {n_acc}, SPN: {n_spn})")
    print(f"Base rate: {n_vt/len(deep):.2%}")

    results = []
    data = deep  # use deep set for maximum features

    # ═══════════════════════════════════════════════
    # ANGLE 1: Multi-lag individual idx values
    # ═══════════════════════════════════════════════
    print("\n>>> ANGLE 1: Multi-lag idx (lag 1-10)")
    for lag in range(1, 11):
        for reel in ['r1', 'r2', 'r3']:
            key = f'L{lag}_{reel}'
            for val in range(9):
                results.append(test_strat(data,
                    lambda r, k=key, v=val: r.get(k) == v,
                    f"L{lag}_{reel}={val}({STRIP[val]})"))

    # ═══════════════════════════════════════════════
    # ANGLE 2: Multi-lag sums and spreads
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 2: Multi-lag sums/spreads")
    for lag in range(1, 11):
        for thresh in [4, 6, 8, 12, 15, 18, 20]:
            results.append(test_strat(data,
                lambda r, l=lag, t=thresh: r.get(f'L{l}_sum', 99) >= t,
                f"L{lag}_sum>={thresh}"))
            results.append(test_strat(data,
                lambda r, l=lag, t=thresh: r.get(f'L{l}_sum', -1) <= t,
                f"L{lag}_sum<={thresh}"))
        for thresh in [0, 1, 2, 4, 6]:
            results.append(test_strat(data,
                lambda r, l=lag, t=thresh: r.get(f'L{l}_spread', -1) == t,
                f"L{lag}_spread={thresh}"))

    # ═══════════════════════════════════════════════
    # ANGLE 3: Rolling window features
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 3: Rolling windows")
    for win in [3, 5, 7, 10]:
        for thresh in [8, 10, 12, 14, 16]:
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_mean_sum', 0) >= t,
                f"W{win}_avgsum>={thresh}"))
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_mean_sum', 99) <= t,
                f"W{win}_avgsum<={thresh}"))
        for thresh in [0, 1, 2, 3]:
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_triples', -1) >= t,
                f"W{win}_triples>={thresh}"))
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_triples', 99) == t,
                f"W{win}_triples={thresh}"))
        for thresh in [0, 1]:
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_vts', -1) >= t,
                f"W{win}_vts>={thresh}"))
        for thresh in [3, 5, 7, 9]:
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_unique_idx', 0) >= t,
                f"W{win}_uniq_idx>={thresh}"))
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_unique_idx', 99) <= t,
                f"W{win}_uniq_idx<={thresh}"))
        for thresh in [0, 1, 2, 3]:
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_near_miss', -1) >= t,
                f"W{win}_nearmiss>={thresh}"))
        for thresh in [1.0, 1.5, 2.0, 2.5]:
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_idx_entropy', 0) >= t,
                f"W{win}_entropy>={thresh}"))
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_idx_entropy', 99) <= t,
                f"W{win}_entropy<={thresh}"))
        for thresh in [2, 3, 4]:
            results.append(test_strat(data,
                lambda r, w=win, t=thresh: r.get(f'W{w}_r2_streak', 0) >= t,
                f"W{win}_r2streak>={thresh}"))

    # ═══════════════════════════════════════════════
    # ANGLE 4: Momentum/velocity/acceleration
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 4: Momentum/velocity")
    for thresh in [-8, -5, -3, 0, 3, 5, 8]:
        results.append(test_strat(data,
            lambda r, t=thresh: r.get('velocity', 0) >= t,
            f"velocity>={thresh}"))
        results.append(test_strat(data,
            lambda r, t=thresh: r.get('velocity', 0) <= t,
            f"velocity<={thresh}"))
        results.append(test_strat(data,
            lambda r, t=thresh: r.get('accel', 0) >= t,
            f"accel>={thresh}"))
    for thresh in [20, 25, 30, 35]:
        results.append(test_strat(data,
            lambda r, t=thresh: r.get('momentum_3', 0) >= t,
            f"momentum3>={thresh}"))
        results.append(test_strat(data,
            lambda r, t=thresh: r.get('momentum_3', 99) <= t,
            f"momentum3<={thresh}"))

    # ═══════════════════════════════════════════════
    # ANGLE 5: Modular arithmetic
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 5: Modular patterns")
    for mod in [2, 3, 4, 9]:
        for val in range(mod):
            results.append(test_strat(data,
                lambda r, m=mod, v=val: r.get('p_sum_mod'+str(m)) == v,
                f"psum_mod{mod}={val}"))

    # ═══════════════════════════════════════════════
    # ANGLE 6: Zone combos (H/M/L)
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 6: Zone combos")
    zone_combos = set()
    for r in data:
        z = r.get('p_zone_combo', '')
        if z:
            zone_combos.add(z)
    for z in sorted(zone_combos):
        results.append(test_strat(data,
            lambda r, zc=z: r.get('p_zone_combo') == zc,
            f"prev_zone={z}"))

    # ═══════════════════════════════════════════════
    # ANGLE 7: Specific idx presence on prev spin
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 7: Prev-spin specific idx presence")
    for idx in range(9):
        results.append(test_strat(data,
            lambda r, i=idx: r.get(f'p_has_{i}', False),
            f"prev_has_idx{idx}({STRIP[idx]})"))
        results.append(test_strat(data,
            lambda r, i=idx: not r.get(f'p_has_{i}', True),
            f"prev_no_idx{idx}({STRIP[idx]})"))

    # ═══════════════════════════════════════════════
    # ANGLE 8: Post-triple behavior
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 8: Post-triple patterns")
    results.append(test_strat(data, lambda r: r.get('after_triple', False), "after_triple"))
    results.append(test_strat(data, lambda r: r.get('after_vt', False), "after_vt"))
    results.append(test_strat(data, lambda r: not r.get('after_triple', True), "not_after_triple"))
    for sym in ['attack', 'coin', 'shield', 'goldSack', 'steal', 'spins', 'accumulation']:
        results.append(test_strat(data,
            lambda r, s=sym: r.get('post_triple_type') == s,
            f"after_triple_{sym}"))

    # ═══════════════════════════════════════════════
    # ANGLE 9: Dominant symbol on prev spin
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 9: Dominant symbol")
    for sym in ['attack', 'coin', 'shield', 'goldSack', 'steal', 'spins', 'accumulation']:
        results.append(test_strat(data,
            lambda r, s=sym: r.get('p_dominant_sym') == s and r.get('p_dominant_count', 0) >= 2,
            f"prev_pair_{sym}"))

    # ═══════════════════════════════════════════════
    # ANGLE 10: Cumulative patterns
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 10: Cumulative/session")
    for thresh in [10, 20, 50, 100, 200, 500]:
        results.append(test_strat(data,
            lambda r, t=thresh: r.get('spin_in_session', 0) >= t,
            f"session_spin>={thresh}"))
    for mod_val in range(0, 27, 3):
        results.append(test_strat(data,
            lambda r, m=mod_val: r.get('cum_sum_mod', -1) == m,
            f"cumsum_mod27={mod_val}"))

    # ═══════════════════════════════════════════════
    # ANGLE 11: Gap-conditioned features
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 11: Gap-conditioned idx interactions")
    for gap_min in [20, 30, 40, 50]:
        for lag in [1, 2, 3]:
            for reel in ['r1', 'r2', 'r3']:
                key = f'L{lag}_{reel}'
                for val in range(9):
                    results.append(test_strat(data,
                        lambda r, g=gap_min, k=key, v=val: r['gap_vt'] >= g and r.get(k) == v,
                        f"gap>={gap_min}+L{lag}_{reel}={val}"))

    # gap + rolling window combos
    for gap_min in [30, 40, 50]:
        for win in [3, 5]:
            results.append(test_strat(data,
                lambda r, g=gap_min, w=win: r['gap_vt'] >= g and r.get(f'W{w}_mean_sum', 0) >= 14,
                f"gap>={gap_min}+W{win}_avgsum>=14"))
            results.append(test_strat(data,
                lambda r, g=gap_min, w=win: r['gap_vt'] >= g and r.get(f'W{w}_mean_sum', 99) <= 8,
                f"gap>={gap_min}+W{win}_avgsum<=8"))
            results.append(test_strat(data,
                lambda r, g=gap_min, w=win: r['gap_vt'] >= g and r.get(f'W{w}_triples', 99) == 0,
                f"gap>={gap_min}+W{win}_notriples"))
            results.append(test_strat(data,
                lambda r, g=gap_min, w=win: r['gap_vt'] >= g and r.get(f'W{w}_near_miss', 0) >= 2,
                f"gap>={gap_min}+W{win}_nm>=2"))
            results.append(test_strat(data,
                lambda r, g=gap_min, w=win: r['gap_vt'] >= g and r.get(f'W{w}_unique_idx', 0) >= 7,
                f"gap>={gap_min}+W{win}_uniq>=7"))
            results.append(test_strat(data,
                lambda r, g=gap_min, w=win: r['gap_vt'] >= g and r.get(f'W{w}_triple_rate', 1) <= 0.1,
                f"gap>={gap_min}+W{win}_trirate<=0.1"))

    # gap + momentum combos
    for gap_min in [30, 40, 50]:
        for vt in [-5, -3, 3, 5, 8]:
            results.append(test_strat(data,
                lambda r, g=gap_min, v=vt: r['gap_vt'] >= g and r.get('velocity', 0) >= v,
                f"gap>={gap_min}+vel>={vt}"))
            results.append(test_strat(data,
                lambda r, g=gap_min, v=vt: r['gap_vt'] >= g and r.get('velocity', 0) <= v,
                f"gap>={gap_min}+vel<={vt}"))

    # gap + prev dominant symbol combos
    for gap_min in [30, 40, 50]:
        for sym in ['goldSack', 'steal', 'accumulation', 'spins', 'coin']:
            results.append(test_strat(data,
                lambda r, g=gap_min, s=sym: r['gap_vt'] >= g and r.get('p_dominant_sym') == s and r.get('p_dominant_count', 0) >= 2,
                f"gap>={gap_min}+prev_pair_{sym}"))

    # gap + zone combos
    for gap_min in [30, 40, 50]:
        for z in sorted(zone_combos):
            results.append(test_strat(data,
                lambda r, g=gap_min, zc=z: r['gap_vt'] >= g and r.get('p_zone_combo') == zc,
                f"gap>={gap_min}+zone={z}"))

    # gap + parity window
    for gap_min in [30, 40, 50]:
        for win in [3, 5]:
            for thresh in [2, 3]:
                results.append(test_strat(data,
                    lambda r, g=gap_min, w=win, t=thresh: r['gap_vt'] >= g and r.get(f'W{w}_parity_run', 0) >= t,
                    f"gap>={gap_min}+W{win}_parrun>={thresh}"))

    # ═══════════════════════════════════════════════
    # ANGLE 12: Multi-lag combos (lag1+lag2, lag1+lag3, etc.)
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 12: Multi-lag combos")
    for g in [30, 40, 50]:
        # lag1 + lag2 sum combos
        for t1 in [12, 15, 18]:
            for t2 in [12, 15, 18]:
                results.append(test_strat(data,
                    lambda r, g_=g, a=t1, b=t2: r['gap_vt'] >= g_ and r.get('L1_sum', 0) >= a and r.get('L2_sum', 0) >= b,
                    f"gap>={g}+L1sum>={t1}+L2sum>={t2}"))
        # lag1 + lag2 triple status
        results.append(test_strat(data,
            lambda r, g_=g: r['gap_vt'] >= g_ and r.get('L1_triple') and r.get('L2_triple'),
            f"gap>={g}+L1triple+L2triple"))
        results.append(test_strat(data,
            lambda r, g_=g: r['gap_vt'] >= g_ and not r.get('L1_triple', True) and not r.get('L2_triple', True),
            f"gap>={g}+L1notrip+L2notrip"))

    # ═══════════════════════════════════════════════
    # ANGLE 13: Score-based fusion
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 13: Score-based signal fusion")

    def compute_score(r, weights):
        """Compute weighted score from multiple pre-spin features."""
        score = 0
        # Gap component
        g = r['gap_vt']
        if g >= 50: score += weights.get('gap50', 0)
        elif g >= 40: score += weights.get('gap40', 0)
        elif g >= 30: score += weights.get('gap30', 0)

        # Prev gold
        if r.get('p_dominant_sym') == 'goldSack' and r.get('p_dominant_count', 0) >= 2:
            score += weights.get('prev_gold_pair', 0)
        if r.get(f'p_has_3', False) or r.get(f'p_has_7', False):
            score += weights.get('prev_has_gold', 0)

        # Prev steal
        if r.get(f'p_has_4', False):
            score += weights.get('prev_has_steal', 0)

        # Prev sum
        psum = r.get('L1_sum', 11)
        if psum >= 18: score += weights.get('psum_high', 0)
        elif psum <= 6: score += weights.get('psum_low', 0)

        # Window features
        w5_avg = r.get('W5_mean_sum', 11)
        if w5_avg >= 14: score += weights.get('w5_high', 0)
        elif w5_avg <= 8: score += weights.get('w5_low', 0)

        # Post-triple
        if r.get('after_triple'): score += weights.get('post_triple', 0)
        if r.get('gap_trip', 999) <= 3: score += weights.get('recent_triple', 0)

        # Velocity
        v = r.get('velocity', 0)
        if v >= 5: score += weights.get('vel_up', 0)
        elif v <= -5: score += weights.get('vel_down', 0)

        return score

    # Try different weight configs
    configs = [
        {'gap50': 3, 'gap40': 2, 'gap30': 1, 'prev_has_gold': 1, 'prev_has_steal': 1, 'psum_high': 1},
        {'gap50': 4, 'gap40': 3, 'gap30': 2, 'prev_gold_pair': 2, 'prev_has_steal': 1, 'psum_high': 1, 'vel_up': 1},
        {'gap50': 3, 'gap40': 2, 'gap30': 1, 'prev_has_gold': 2, 'w5_high': 1, 'psum_low': -1},
        {'gap50': 5, 'gap40': 3, 'gap30': 1, 'prev_gold_pair': 3, 'prev_has_steal': 2, 'post_triple': -1, 'psum_high': 1},
        {'gap50': 4, 'gap40': 2, 'gap30': 1, 'prev_has_gold': 1, 'prev_has_steal': 2, 'vel_up': 1, 'w5_high': 1, 'post_triple': -2},
    ]

    for ci, cfg in enumerate(configs):
        for thresh in range(2, 10):
            results.append(test_strat(data,
                lambda r, c=cfg, t=thresh: compute_score(r, c) >= t,
                f"score_v{ci}_>={thresh}"))

    # ═══════════════════════════════════════════════
    # ANGLE 14: sa_ counter interactions
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 14: sa_ counter interactions")
    sa_data = [r for r in data if r.get('sa_acc') is not None]
    if sa_data:
        sa_results = []
        for g in [30, 40, 50]:
            for sa_key, sa_name in [('sa_acc', 'sacc'), ('sa_spn', 'saspn'), ('sa_stl', 'sastl'),
                                     ('sa_atk', 'saatk'), ('sa_shd', 'sashd')]:
                for thresh in [1, 2, 3, 5, 7, 10]:
                    sa_results.append(test_strat(sa_data,
                        lambda r, g_=g, k=sa_key, t=thresh: r['gap_vt'] >= g_ and (r.get(k) or 0) >= t,
                        f"gap>={g}+{sa_name}>={thresh}"))
                    sa_results.append(test_strat(sa_data,
                        lambda r, g_=g, k=sa_key, t=thresh: r['gap_vt'] >= g_ and (r.get(k) or 0) == t,
                        f"gap>={g}+{sa_name}={thresh}"))
            # sa combo conditions
            sa_results.append(test_strat(sa_data,
                lambda r, g_=g: r['gap_vt'] >= g_ and (r.get('sa_acc') or 0) >= 3 and (r.get('sa_stl') or 0) >= 2,
                f"gap>={g}+sacc>=3+sastl>=2"))
            sa_results.append(test_strat(sa_data,
                lambda r, g_=g: r['gap_vt'] >= g_ and (r.get('sa_spn') or 0) >= 3 and (r.get('sa_stl') or 0) >= 2,
                f"gap>={g}+saspn>=3+sastl>=2"))
            # sa + prev gold
            sa_results.append(test_strat(sa_data,
                lambda r, g_=g: r['gap_vt'] >= g_ and (r.get('sa_acc') or 0) >= 3 and (r.get('p_has_3', False) or r.get('p_has_7', False)),
                f"gap>={g}+sacc>=3+prev_gold"))

        show(sa_results, "sa_ COUNTER INTERACTIONS", max_bph=10)

    # ═══════════════════════════════════════════════
    # ANGLE 15: Exhaustive 2-feature combo sweep with gap
    # ═══════════════════════════════════════════════
    print(">>> ANGLE 15: Exhaustive 2-feature combo sweep")
    # Define atomic conditions
    atoms = [
        (lambda r: r.get('L1_sum', 0) >= 15, "psum>=15"),
        (lambda r: r.get('L1_sum', 0) >= 18, "psum>=18"),
        (lambda r: r.get('L1_sum', 99) <= 6, "psum<=6"),
        (lambda r: r.get('L1_sum', 99) <= 4, "psum<=4"),
        (lambda r: r.get('L1_spread', -1) == 0, "pspread=0"),
        (lambda r: r.get('L1_spread', -1) >= 5, "pspread>=5"),
        (lambda r: r.get('L1_triple', False), "ptriple"),
        (lambda r: not r.get('L1_triple', True), "pnotrip"),
        (lambda r: r.get('p_has_3', False) or r.get('p_has_7', False), "pgold"),
        (lambda r: r.get('p_has_4', False), "psteal"),
        (lambda r: r.get('p_has_6', False), "pspn"),
        (lambda r: r.get('p_has_8', False), "pacc"),
        (lambda r: r.get('p_has_0', False), "patk"),
        (lambda r: not r.get('p_has_0', True), "pnoatk"),
        (lambda r: r.get('p_dominant_count', 0) >= 2, "ppair"),
        (lambda r: r.get('p_dominant_sym') == 'goldSack' and r.get('p_dominant_count', 0) >= 2, "pgoldpair"),
        (lambda r: r.get('p_dominant_sym') == 'steal' and r.get('p_dominant_count', 0) >= 2, "pstealpair"),
        (lambda r: r.get('velocity', 0) >= 5, "vel>=5"),
        (lambda r: r.get('velocity', 0) <= -5, "vel<=-5"),
        (lambda r: r.get('W3_mean_sum', 0) >= 14, "w3avg>=14"),
        (lambda r: r.get('W3_mean_sum', 99) <= 8, "w3avg<=8"),
        (lambda r: r.get('W5_mean_sum', 0) >= 14, "w5avg>=14"),
        (lambda r: r.get('W5_mean_sum', 99) <= 8, "w5avg<=8"),
        (lambda r: r.get('W3_triples', 99) == 0, "w3notrip"),
        (lambda r: r.get('W5_triples', 99) == 0, "w5notrip"),
        (lambda r: r.get('W3_near_miss', 0) >= 2, "w3nm>=2"),
        (lambda r: r.get('W5_near_miss', 0) >= 3, "w5nm>=3"),
        (lambda r: r.get('L2_sum', 0) >= 15, "L2sum>=15"),
        (lambda r: r.get('L2_triple', False), "L2triple"),
        (lambda r: r.get('after_triple', False), "aftertrip"),
        (lambda r: r.get('gap_trip', 999) >= 5, "gaptrip>=5"),
        (lambda r: r.get('gap_trip', 999) >= 10, "gaptrip>=10"),
        (lambda r: r.get('p_sum_mod3') == 0, "pmod3=0"),
        (lambda r: r.get('p_sum_mod3') == 1, "pmod3=1"),
        (lambda r: r.get('p_sum_mod3') == 2, "pmod3=2"),
        (lambda r: r.get('momentum_3', 0) >= 35, "mom3>=35"),
        (lambda r: r.get('momentum_3', 99) <= 20, "mom3<=20"),
    ]

    combo_results = []
    for g in [30, 40, 50]:
        # Singles with gap
        for fn, lbl in atoms:
            combo_results.append(test_strat(data,
                lambda r, g_=g, f_=fn: r['gap_vt'] >= g_ and f_(r),
                f"gap>={g}+{lbl}"))

        # All pairs with gap
        for (fn1, l1), (fn2, l2) in combinations(atoms, 2):
            combo_results.append(test_strat(data,
                lambda r, g_=g, f1=fn1, f2=fn2: r['gap_vt'] >= g_ and f1(r) and f2(r),
                f"gap>={g}+{l1}+{l2}"))

    show(combo_results, "EXHAUSTIVE 2-FEATURE COMBOS + GAP (ALL VTs)", max_bph=10)

    # ═══════════════════════════════════════════════
    # Show ALL results
    # ═══════════════════════════════════════════════
    show(results, "ALL SINGLE-FEATURE & GAP+FEATURE STRATEGIES (ALL VTs)", max_bph=10)

    # ═══════════════════════════════════════════════
    # ACC-specific sweep
    # ═══════════════════════════════════════════════
    print("\n\n>>> ACC-SPECIFIC SWEEP")
    acc_results = []
    target_acc = lambda r: r['vt'] == 'ACC'

    for g in [40, 50, 60, 80, 100]:
        acc_results.append(test_strat(data,
            lambda r, g_=g: r['gap_acc'] >= g_, f"gapacc>={g}", target_acc))

        for fn, lbl in atoms:
            acc_results.append(test_strat(data,
                lambda r, g_=g, f_=fn: r['gap_acc'] >= g_ and f_(r),
                f"gapacc>={g}+{lbl}", target_acc))

        # Top pairs for ACC
        acc_atoms = atoms[:20]  # trim for speed
        for (fn1, l1), (fn2, l2) in combinations(acc_atoms, 2):
            acc_results.append(test_strat(data,
                lambda r, g_=g, f1=fn1, f2=fn2: r['gap_acc'] >= g_ and f1(r) and f2(r),
                f"gapacc>={g}+{l1}+{l2}", target_acc))

    show(acc_results, "ACC-SPECIFIC STRATEGIES", max_bph=10)

    # ═══════════════════════════════════════════════
    # SPN-specific sweep
    # ═══════════════════════════════════════════════
    print("\n\n>>> SPN-SPECIFIC SWEEP")
    spn_results = []
    target_spn = lambda r: r['vt'] == 'SPN'

    for g in [30, 40, 50, 60, 80]:
        spn_results.append(test_strat(data,
            lambda r, g_=g: r['gap_spn'] >= g_, f"gapspn>={g}", target_spn))

        for fn, lbl in atoms:
            spn_results.append(test_strat(data,
                lambda r, g_=g, f_=fn: r['gap_spn'] >= g_ and f_(r),
                f"gapspn>={g}+{lbl}", target_spn))

        spn_atoms = atoms[:20]
        for (fn1, l1), (fn2, l2) in combinations(spn_atoms, 2):
            spn_results.append(test_strat(data,
                lambda r, g_=g, f1=fn1, f2=fn2: r['gap_spn'] >= g_ and f1(r) and f2(r),
                f"gapspn>={g}+{l1}+{l2}", target_spn))

    show(spn_results, "SPN-SPECIFIC STRATEGIES", max_bph=10)


if __name__ == '__main__':
    print("Loading data...")
    rows = load()
    print(f"Loaded {len(rows)} spins")
    print("Computing deep features...")
    rows = add_deep_features(rows)
    print("Running exhaustive sweep...")
    run(rows)
    print("\nDone.")
