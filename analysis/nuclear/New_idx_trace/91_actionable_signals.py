"""
91_actionable_signals.py — Actionable Pre-Spin Signal Analysis

KEY INSIGHT: Same-spin idx features are TAUTOLOGICAL for VTs.
A VT at spin N means all 3 indices map to the same symbol, so of course
idx_sum is high, spread=0, same_parity=True. You can't use spin N's idx
to decide whether to bet on spin N — the bet is already locked.

ACTIONABLE signals must come from BEFORE the spin:
  1. Gap (pity timer) — known pre-spin
  2. Lag-1 idx features (previous spin's indices) — known pre-spin
  3. sa_ counters — known pre-spin
  4. Near-miss on lag-1 (2 of 3 matched) — known pre-spin
  5. Symbol class transitions — known pre-spin
"""

import csv, os
from collections import Counter, defaultdict
from math import sqrt

# ─── Strip ───
STRIP = {0:'attack', 1:'coin', 2:'shield', 3:'goldSack', 4:'steal',
         5:'coin', 6:'spins', 7:'goldSack', 8:'accumulation'}
IDX_TO_SYM = {}
for i, s in STRIP.items():
    IDX_TO_SYM[i] = s

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'data')
FILES = [
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_enriched_v2.csv')),
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_2026-04-13.csv')),
    ('Ahmed', os.path.join(DATA_DIR, 'Ahmed', 'spin_history_Ahmed_2026-04-14.csv')),
    ('Islam', os.path.join(DATA_DIR, 'Islam', 'spin_history_Islam_2026-04-13.csv')),
    ('Nick',  os.path.join(DATA_DIR, 'Nick',  'spin_history_Nick_2026-04-13.csv')),
]

def load_all():
    rows = []
    for acct, path in FILES:
        with open(path) as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    r1i = int(r['r1_idx'])
                    r2i = int(r['r2_idx'])
                    r3i = int(r['r3_idx'])
                except (ValueError, KeyError):
                    continue
                if any(x not in STRIP for x in (r1i, r2i, r3i)):
                    continue

                reel_1 = r.get('reel_1', '')
                is_triple = r.get('is_triple', '').lower() == 'true'
                vt_type = None
                if is_triple:
                    if reel_1 == 'accumulation': vt_type = 'ACC'
                    elif reel_1 == 'spins': vt_type = 'SPN'

                sa_spn = int(r['sa_spn']) if r.get('sa_spn', '') else None
                sa_acc = int(r['sa_acc']) if r.get('sa_acc', '') else None
                sa_spins = int(r['sa_spins']) if r.get('sa_spins', '') else None
                sa_stl = int(r['sa_stl']) if r.get('sa_stl', '') else None

                rows.append({
                    'acct': acct,
                    'r1_idx': r1i, 'r2_idx': r2i, 'r3_idx': r3i,
                    # True displayed symbols (with swap correction)
                    'sym_r1': IDX_TO_SYM[r3i], 'sym_r2': IDX_TO_SYM[r2i], 'sym_r3': IDX_TO_SYM[r1i],
                    'is_triple': is_triple, 'vt_type': vt_type,
                    'reel_1': reel_1,
                    'sa_spn': sa_spn, 'sa_acc': sa_acc, 'sa_spins': sa_spins, 'sa_stl': sa_stl,
                })
    return rows


def add_features(rows):
    """Add ONLY pre-spin-knowable features."""
    last_vt = {}
    last_acc = {}
    last_spn = {}
    last_triple = {}

    for i, r in enumerate(rows):
        acct = r['acct']
        r1i, r2i, r3i = r['r1_idx'], r['r2_idx'], r['r3_idx']

        # Idx composite (same-spin, for reference only)
        r['idx_sum'] = r1i + r2i + r3i

        # Gap tracking (PRE-SPIN: known before this spin)
        r['gap_vt'] = i - last_vt.get(acct, -999)
        r['gap_acc'] = i - last_acc.get(acct, -999)
        r['gap_spn'] = i - last_spn.get(acct, -999)
        r['gap_triple'] = i - last_triple.get(acct, -999)

        if r['vt_type']:
            last_vt[acct] = i
            if r['vt_type'] == 'ACC': last_acc[acct] = i
            elif r['vt_type'] == 'SPN': last_spn[acct] = i
        if r['is_triple']:
            last_triple[acct] = i

    # Lag-1 features (all PRE-SPIN: from the PREVIOUS spin's settled state)
    for i in range(1, len(rows)):
        if rows[i]['acct'] != rows[i-1]['acct']:
            continue
        p = rows[i-1]
        r = rows[i]

        r['p_r1'] = p['r1_idx']
        r['p_r2'] = p['r2_idx']
        r['p_r3'] = p['r3_idx']
        r['p_sum'] = p['r1_idx'] + p['r2_idx'] + p['r3_idx']
        r['p_spread'] = max(p['r1_idx'], p['r2_idx'], p['r3_idx']) - min(p['r1_idx'], p['r2_idx'], p['r3_idx'])
        r['p_max'] = max(p['r1_idx'], p['r2_idx'], p['r3_idx'])
        r['p_min'] = min(p['r1_idx'], p['r2_idx'], p['r3_idx'])

        # Previous spin's TRUE displayed symbols
        r['p_sym_r1'] = p['sym_r1']
        r['p_sym_r2'] = p['sym_r2']
        r['p_sym_r3'] = p['sym_r3']

        # Previous spin near-miss: how many indices map to same symbol?
        syms = [IDX_TO_SYM[p['r1_idx']], IDX_TO_SYM[p['r2_idx']], IDX_TO_SYM[p['r3_idx']]]
        r['p_idx_pair'] = (syms[0]==syms[1]) or (syms[0]==syms[2]) or (syms[1]==syms[2])
        r['p_idx_match_count'] = max(Counter(syms).values())  # 1=all diff, 2=pair, 3=triple

        # Previous spin's TRUE displayed symbol pairs
        true_syms = [p['sym_r1'], p['sym_r2'], p['sym_r3']]
        r['p_true_pair'] = len(set(true_syms)) < 3
        r['p_true_match'] = max(Counter(true_syms).values())

        r['p_triple'] = p['is_triple']
        r['p_vt'] = p['vt_type'] is not None

        # Previous spin had steal showing
        r['p_has_steal'] = 'steal' in true_syms
        r['p_has_acc'] = 'accumulation' in true_syms
        r['p_has_spn'] = 'spins' in true_syms
        r['p_has_gold'] = 'goldSack' in true_syms

        # Parity
        r['p_parity_sum'] = (p['r1_idx'] % 2) + (p['r2_idx'] % 2) + (p['r3_idx'] % 2)
        r['p_all_even'] = r['p_parity_sum'] == 0
        r['p_all_odd'] = r['p_parity_sum'] == 3

        # sa_ from previous spin (if available)
        r['p_sa_spn'] = p['sa_spn']
        r['p_sa_acc'] = p['sa_acc']
        r['p_sa_stl'] = p['sa_stl']

    # Lag-2 features
    for i in range(2, len(rows)):
        if rows[i]['acct'] != rows[i-2]['acct']:
            continue
        pp = rows[i-2]
        r = rows[i]
        r['pp_r1'] = pp['r1_idx']
        r['pp_r2'] = pp['r2_idx']
        r['pp_r3'] = pp['r3_idx']
        r['pp_sum'] = pp['r1_idx'] + pp['r2_idx'] + pp['r3_idx']

        # 2-spin trend
        if 'p_sum' in r:
            r['trend_sum'] = r['p_sum'] - r['pp_sum']

    return rows


def pvalue(hits, bets, base):
    if bets == 0 or base == 0: return 1.0
    obs = hits / bets
    se = sqrt(base * (1 - base) / bets)
    if se == 0: return 1.0
    z = (obs - base) / se
    if z <= 0: return 1.0
    t = 1.0 / (1.0 + 0.2316419 * z)
    d = 0.3989422804 * (2.718281828 ** (-z * z / 2))
    return d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))


def test(rows, cond, label, target_fn=None, min_hits=2):
    if target_fn is None:
        target_fn = lambda r: r['vt_type'] is not None
    n = len(rows)
    n_tgt = sum(1 for r in rows if target_fn(r))
    base = n_tgt / n if n > 0 else 0
    bets = hits = 0
    for r in rows:
        if cond(r):
            bets += 1
            if target_fn(r): hits += 1
    if bets == 0 or hits < min_hits: return None
    prec = hits / bets
    return {
        'label': label, 'bets': bets, 'hits': hits,
        'prec': prec, 'lift': prec / base if base else 0,
        'catch': hits / n_tgt if n_tgt else 0,
        'bph': bets / hits if hits else 999,
        'pval': pvalue(hits, bets, base),
        'base': base, 'n': n, 'n_tgt': n_tgt,
    }


def show(results, title):
    results = [r for r in results if r]
    results.sort(key=lambda x: x['pval'])
    print(f"\n{'='*110}")
    print(f"  {title}")
    if results:
        print(f"  {results[0]['n']} spins, {results[0]['n_tgt']} targets, base={results[0]['base']:.2%}")
    print(f"{'='*110}")
    print(f"{'Strategy':<60s} {'Prec':>6s} {'Lift':>5s} {'Catch':>6s} {'B/H':>5s} {'Bets':>5s} {'Hits':>4s} {'p-val':>8s}")
    print("-" * 110)
    for r in results[:40]:
        s = '***' if r['pval'] < 0.001 else '**' if r['pval'] < 0.01 else '*' if r['pval'] < 0.05 else ''
        print(f"{r['label']:<60s} {r['prec']:>5.1%} {r['lift']:>5.1f}x {r['catch']:>5.1%} "
              f"{r['bph']:>5.1f} {r['bets']:>5d} {r['hits']:>4d} {r['pval']:>7.4f} {s}")


def run(rows):
    valid = [r for r in rows if 'p_r1' in r]
    print(f"Total: {len(rows)} spins, {len(valid)} with lag features")
    n_vt = sum(1 for r in valid if r['vt_type'])
    n_acc = sum(1 for r in valid if r['vt_type'] == 'ACC')
    n_spn = sum(1 for r in valid if r['vt_type'] == 'SPN')
    print(f"VTs: {n_vt} (ACC: {n_acc}, SPN: {n_spn})")

    # ═══════════════════════════════════════════════
    # SECTION A: Pure lag-1 idx features (NO gap filter)
    # ═══════════════════════════════════════════════
    print("\n" + "="*80)
    print("  SECTION A: Lag-1 idx features ONLY (no gap) — are any predictive?")
    print("="*80)

    lag_only = []
    for idx in range(9):
        lag_only.append(test(valid, lambda r, i=idx: r['p_r1'] == i, f"prev_r1_idx={idx} ({STRIP[idx]})"))
        lag_only.append(test(valid, lambda r, i=idx: r['p_r2'] == i, f"prev_r2_idx={idx} ({STRIP[idx]})"))
        lag_only.append(test(valid, lambda r, i=idx: r['p_r3'] == i, f"prev_r3_idx={idx} ({STRIP[idx]})"))

    lag_only += [
        test(valid, lambda r: r['p_sum'] >= 18, "prev_sum>=18"),
        test(valid, lambda r: r['p_sum'] >= 20, "prev_sum>=20"),
        test(valid, lambda r: r['p_sum'] <= 6, "prev_sum<=6"),
        test(valid, lambda r: r['p_sum'] <= 4, "prev_sum<=4"),
        test(valid, lambda r: r['p_spread'] == 0, "prev_spread=0"),
        test(valid, lambda r: r['p_spread'] >= 6, "prev_spread>=6"),
        test(valid, lambda r: r['p_idx_match_count'] == 3, "prev_idx_triple"),
        test(valid, lambda r: r['p_idx_match_count'] >= 2, "prev_idx_pair+"),
        test(valid, lambda r: r['p_idx_match_count'] == 1, "prev_all_diff_idx"),
        test(valid, lambda r: r['p_true_match'] >= 2, "prev_true_pair+"),
        test(valid, lambda r: r['p_true_match'] == 1, "prev_true_all_diff"),
        test(valid, lambda r: r['p_triple'], "prev_was_triple"),
        test(valid, lambda r: not r['p_triple'], "prev_not_triple"),
        test(valid, lambda r: r['p_has_steal'], "prev_showed_steal"),
        test(valid, lambda r: r['p_has_acc'], "prev_showed_acc"),
        test(valid, lambda r: r['p_has_spn'], "prev_showed_spn"),
        test(valid, lambda r: r['p_has_gold'], "prev_showed_gold"),
        test(valid, lambda r: r['p_all_even'], "prev_all_even"),
        test(valid, lambda r: r['p_all_odd'], "prev_all_odd"),
        test(valid, lambda r: r['p_max'] == 8, "prev_max=8(acc)"),
        test(valid, lambda r: r['p_min'] == 0, "prev_min=0(atk)"),
        test(valid, lambda r: r['p_r1'] in (3,7), "prev_r1=gold(3or7)"),
        test(valid, lambda r: r['p_r2'] in (3,7), "prev_r2=gold(3or7)"),
        test(valid, lambda r: r['p_r3'] in (3,7), "prev_r3=gold(3or7)"),
        test(valid, lambda r: r['p_r1'] == 8, "prev_r1=8(acc)"),
        test(valid, lambda r: r['p_r2'] == 8, "prev_r2=8(acc)"),
        test(valid, lambda r: r['p_r3'] == 8, "prev_r3=8(acc)"),
    ]
    show(lag_only, "LAG-1 IDX FEATURES ONLY (ALL VTs)")

    # ═══════════════════════════════════════════════
    # SECTION B: Gap + lag-1 combos (ALL VTs)
    # ═══════════════════════════════════════════════
    combos_all = []
    for g in [20, 30, 40, 50]:
        # Pure gap baseline
        combos_all.append(test(valid, lambda r, g=g: r['gap_vt'] >= g, f"gap>={g} (baseline)"))

        for cond, lbl in [
            (lambda r: r['p_has_steal'], "prev_steal"),
            (lambda r: r['p_has_acc'], "prev_acc"),
            (lambda r: r['p_has_spn'], "prev_spn"),
            (lambda r: r['p_has_gold'], "prev_gold"),
            (lambda r: r['p_sum'] >= 15, "psum>=15"),
            (lambda r: r['p_sum'] >= 18, "psum>=18"),
            (lambda r: r['p_sum'] <= 6, "psum<=6"),
            (lambda r: r['p_spread'] <= 2, "pspread<=2"),
            (lambda r: r['p_spread'] >= 5, "pspread>=5"),
            (lambda r: r['p_idx_match_count'] >= 2, "prev_pair+"),
            (lambda r: r['p_idx_match_count'] == 1, "prev_alldiff"),
            (lambda r: r['p_triple'], "prev_triple"),
            (lambda r: not r['p_triple'], "prev_no_triple"),
            (lambda r: r['p_all_even'], "prev_alleven"),
            (lambda r: r['p_all_odd'], "prev_allodd"),
            (lambda r: r['p_r1'] in (3,7), "prev_r1=gold"),
            (lambda r: r['p_r3'] in (3,7), "prev_r3=gold"),
            (lambda r: r['p_r1'] == 8, "prev_r1=8"),
            (lambda r: r['p_r3'] == 8, "prev_r3=8"),
            (lambda r: r['p_max'] == 8, "prev_max=8"),
            (lambda r: r['p_r2'] in (3,7), "prev_r2=gold"),
            # Near-miss: previous had 2 matching symbols on display
            (lambda r: r['p_true_match'] >= 2, "prev_display_pair"),
            (lambda r: r.get('trend_sum', 0) > 5, "trend_sum>5"),
            (lambda r: r.get('trend_sum', 0) < -5, "trend_sum<-5"),
        ]:
            combos_all.append(test(valid,
                lambda r, g=g, c=cond: r['gap_vt'] >= g and c(r),
                f"gap>={g}+{lbl}"))

        # Two-feature combos with gap
        two_combos = [
            (lambda r: r['p_has_steal'] and r['p_sum'] >= 15, "prev_steal+psum>=15"),
            (lambda r: r['p_has_gold'] and r['p_has_steal'], "prev_gold+steal"),
            (lambda r: r['p_has_acc'] and r['p_has_gold'], "prev_acc+gold"),
            (lambda r: r['p_has_steal'] and r['p_spread'] <= 2, "prev_steal+tight"),
            (lambda r: r['p_has_gold'] and r['p_sum'] >= 15, "prev_gold+psum>=15"),
            (lambda r: r['p_r1'] in (3,7) and r['p_has_steal'], "prev_r1gold+steal"),
            (lambda r: r['p_all_even'] and r['p_sum'] >= 15, "prev_alleven+psum>=15"),
            (lambda r: r['p_true_match'] >= 2 and r['p_has_steal'], "prev_pair+steal"),
            (lambda r: r['p_true_match'] >= 2 and r['p_sum'] >= 15, "prev_pair+psum>=15"),
            (lambda r: not r['p_triple'] and r['p_has_steal'], "prev_notriple+steal"),
            (lambda r: r['p_max'] == 8 and r['p_has_gold'], "prev_hasacc+gold"),
        ]
        for cfn, clbl in two_combos:
            combos_all.append(test(valid,
                lambda r, g=g, c=cfn: r['gap_vt'] >= g and c(r),
                f"gap>={g}+{clbl}"))

    show(combos_all, "GAP + LAG-1 COMBOS (ALL VTs) — ACTIONABLE")

    # ═══════════════════════════════════════════════
    # SECTION C: ACC-specific actionable
    # ═══════════════════════════════════════════════
    target_acc = lambda r: r['vt_type'] == 'ACC'
    combos_acc = []
    for g in [30, 50, 60, 80]:
        combos_acc.append(test(valid, lambda r, g=g: r['gap_acc'] >= g, f"gap_acc>={g}", target_acc))
        for cond, lbl in [
            (lambda r: r['p_has_steal'], "prev_steal"),
            (lambda r: r['p_has_acc'], "prev_acc"),
            (lambda r: r['p_has_gold'], "prev_gold"),
            (lambda r: r['p_sum'] >= 15, "psum>=15"),
            (lambda r: r['p_sum'] >= 18, "psum>=18"),
            (lambda r: r['p_r1'] in (3,7), "prev_r1=gold"),
            (lambda r: r['p_r3'] in (3,7), "prev_r3=gold"),
            (lambda r: r['p_max'] == 8, "prev_max=8(acc)"),
            (lambda r: r['p_triple'], "prev_triple"),
            (lambda r: not r['p_triple'], "prev_no_triple"),
            (lambda r: r['p_true_match'] >= 2, "prev_display_pair"),
            (lambda r: r['p_idx_match_count'] >= 2, "prev_idx_pair"),
            (lambda r: r['p_has_steal'] and r['p_has_gold'], "prev_steal+gold"),
            (lambda r: r['p_has_steal'] and r['p_sum'] >= 15, "prev_steal+sum15"),
            (lambda r: r['p_has_acc'] and r['p_has_steal'], "prev_acc+steal"),
            (lambda r: r['p_r1'] in (3,7) and r['p_has_steal'], "prev_r1gold+steal"),
        ]:
            combos_acc.append(test(valid,
                lambda r, g=g, c=cond: r['gap_acc'] >= g and c(r),
                f"gap_acc>={g}+{lbl}", target_acc))

    show(combos_acc, "ACC — GAP + LAG-1 COMBOS (ACTIONABLE)")

    # ═══════════════════════════════════════════════
    # SECTION D: SPN-specific actionable
    # ═══════════════════════════════════════════════
    target_spn = lambda r: r['vt_type'] == 'SPN'
    combos_spn = []
    for g in [20, 30, 40, 50]:
        combos_spn.append(test(valid, lambda r, g=g: r['gap_spn'] >= g, f"gap_spn>={g}", target_spn))
        for cond, lbl in [
            (lambda r: r['p_has_steal'], "prev_steal"),
            (lambda r: r['p_has_spn'], "prev_spn"),
            (lambda r: r['p_has_gold'], "prev_gold"),
            (lambda r: r['p_sum'] >= 15, "psum>=15"),
            (lambda r: r['p_sum'] >= 18, "psum>=18"),
            (lambda r: r['p_spread'] >= 5, "pspread>=5"),
            (lambda r: r['p_r3'] >= 5, "prev_r3>=5"),
            (lambda r: r['p_max'] == 8, "prev_max=8"),
            (lambda r: r['p_triple'], "prev_triple"),
            (lambda r: not r['p_triple'], "prev_no_triple"),
            (lambda r: r['p_true_match'] >= 2, "prev_display_pair"),
            (lambda r: r['p_has_spn'] and r['p_sum'] >= 15, "prev_spn+sum15"),
            (lambda r: r['p_has_steal'] and r['p_has_gold'], "prev_steal+gold"),
            (lambda r: r['p_r3'] >= 5 and r['p_sum'] >= 15, "prev_r3hi+sum15"),
        ]:
            combos_spn.append(test(valid,
                lambda r, g=g, c=cond: r['gap_spn'] >= g and c(r),
                f"gap_spn>={g}+{lbl}", target_spn))

    show(combos_spn, "SPN — GAP + LAG-1 COMBOS (ACTIONABLE)")

    # ═══════════════════════════════════════════════
    # SECTION E: sa_ counter signals (if available)
    # ═══════════════════════════════════════════════
    valid_sa = [r for r in valid if r.get('p_sa_acc') is not None]
    if valid_sa:
        print(f"\n{'='*80}")
        print(f"  SECTION E: sa_ counter features ({len(valid_sa)} spins with sa_ data)")
        print(f"{'='*80}")

        sa_strats = []
        for g in [30, 50]:
            for cond, lbl in [
                (lambda r: r['p_sa_acc'] and r['p_sa_acc'] >= 3, "sa_acc>=3"),
                (lambda r: r['p_sa_acc'] and r['p_sa_acc'] >= 5, "sa_acc>=5"),
                (lambda r: r['p_sa_stl'] and r['p_sa_stl'] >= 2, "sa_stl>=2"),
                (lambda r: r['p_sa_stl'] and r['p_sa_stl'] >= 3, "sa_stl>=3"),
                (lambda r: r['p_sa_spn'] and r['p_sa_spn'] >= 3, "sa_spn>=3"),
            ]:
                sa_strats.append(test(valid_sa,
                    lambda r, g=g, c=cond: r['gap_vt'] >= g and c(r),
                    f"gap>={g}+{lbl}"))
        show(sa_strats, "sa_ COUNTER FEATURES")

    # ═══════════════════════════════════════════════
    # SECTION F: Near-miss depth analysis
    # ═══════════════════════════════════════════════
    print(f"\n{'='*80}")
    print(f"  SECTION F: Near-miss analysis (prev spin had 2 matching display symbols)")
    print(f"{'='*80}")

    # For each symbol, check: does a pair of that symbol on prev spin predict VT?
    for sym in ['accumulation', 'spins', 'coin', 'goldSack', 'attack', 'shield', 'steal']:
        def near_miss_fn(r, s=sym):
            syms = [r.get('p_sym_r1',''), r.get('p_sym_r2',''), r.get('p_sym_r3','')]
            return syms.count(s) >= 2 and syms.count(s) < 3
        r = test(valid, near_miss_fn, f"prev_near_miss_{sym}")
        if r:
            s = '***' if r['pval'] < 0.001 else '**' if r['pval'] < 0.01 else '*' if r['pval'] < 0.05 else ''
            print(f"  {r['label']:<45s} prec={r['prec']:.2%} lift={r['lift']:.1f}x catch={r['catch']:.1%} "
                  f"bets={r['bets']} hits={r['hits']} p={r['pval']:.4f} {s}")

    # Near-miss for ACC specifically
    print("\n  ACC near-miss:")
    for sym in ['accumulation']:
        def nm_acc(r, s=sym):
            syms = [r.get('p_sym_r1',''), r.get('p_sym_r2',''), r.get('p_sym_r3','')]
            return syms.count(s) >= 2 and syms.count(s) < 3
        for g in [0, 30, 50]:
            if g > 0:
                r = test(valid, lambda r, g=g, fn=nm_acc: r['gap_acc'] >= g and fn(r),
                         f"gap_acc>={g}+near_miss_acc", target_acc)
            else:
                r = test(valid, nm_acc, f"near_miss_acc (no gap)", target_acc)
            if r:
                s = '***' if r['pval'] < 0.001 else '**' if r['pval'] < 0.01 else '*' if r['pval'] < 0.05 else ''
                print(f"    {r['label']:<45s} prec={r['prec']:.2%} lift={r['lift']:.1f}x catch={r['catch']:.1%} "
                      f"bets={r['bets']} hits={r['hits']} p={r['pval']:.4f} {s}")

    # Near-miss for SPN specifically
    print("\n  SPN near-miss:")
    for sym in ['spins']:
        def nm_spn(r, s=sym):
            syms = [r.get('p_sym_r1',''), r.get('p_sym_r2',''), r.get('p_sym_r3','')]
            return syms.count(s) >= 2 and syms.count(s) < 3
        for g in [0, 20, 40]:
            if g > 0:
                r = test(valid, lambda r, g=g, fn=nm_spn: r['gap_spn'] >= g and fn(r),
                         f"gap_spn>={g}+near_miss_spn", target_spn)
            else:
                r = test(valid, nm_spn, f"near_miss_spn (no gap)", target_spn)
            if r:
                s = '***' if r['pval'] < 0.001 else '**' if r['pval'] < 0.01 else '*' if r['pval'] < 0.05 else ''
                print(f"    {r['label']:<45s} prec={r['prec']:.2%} lift={r['lift']:.1f}x catch={r['catch']:.1%} "
                      f"bets={r['bets']} hits={r['hits']} p={r['pval']:.4f} {s}")

    # ═══════════════════════════════════════════════
    # SECTION G: Theoretical triple probability from strip
    # ═══════════════════════════════════════════════
    print(f"\n{'='*80}")
    print(f"  SECTION G: Strip-based theoretical vs observed triple rates")
    print(f"{'='*80}")

    # If indices were uniform random on 9 positions:
    # P(triple for symbol with k positions) = (k/9)^3
    # Total: sum over symbols
    theory_total = 0
    for sym, indices in sorted([('attack',[0]),('coin',[1,5]),('shield',[2]),('goldSack',[3,7]),
                                 ('steal',[4]),('spins',[6]),('accumulation',[8])]):
        k = len(indices)
        p = (k/9)**3
        theory_total += p
        print(f"  {sym:>14s}: {k} positions, P(triple) = ({k}/9)^3 = {p:.4%}")
    print(f"  {'TOTAL':>14s}: P(any triple) = {theory_total:.4%}")

    obs_triple = sum(1 for r in valid if r['is_triple']) / len(valid)
    obs_vt = sum(1 for r in valid if r['vt_type']) / len(valid)
    print(f"\n  Observed: triple rate = {obs_triple:.2%}, VT rate = {obs_vt:.2%}")
    print(f"  Ratio observed/theory: {obs_triple/theory_total:.1f}x (game manipulates probabilities)")


if __name__ == '__main__':
    rows = load_all()
    rows = add_features(rows)
    run(rows)
