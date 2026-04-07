"""
Chunk 11: Per-gap detail.

For every ACC gap, show:
  - gap index
  - account
  - gap length (spins it took for the ACC triple)
  - previous gap length
  - which sub-10mb configs caught it
  - whether it's in the ensemble union (caught by ANY config)
  - whether it's exclusive to one config

This is the source-of-truth view: you can see the actual 62 caught gaps and the
116 missed gaps with all their numbers.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('ev', os.path.join(os.path.dirname(__file__), '02_eval.py'))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

import pickle
from pathlib import Path

GAPS_PATH = Path(__file__).parent / 'gaps.pkl'
ACCOUNTS  = ['Islam', 'Ahmed', 'Nick']


def load_gaps():
    with open(GAPS_PATH, 'rb') as f:
        return pickle.load(f)


def all_gaps_with_prev():
    data = load_gaps()
    out = []
    for acct in ACCOUNTS:
        raw = data[acct]['gaps'].get('accumulation', [])
        for i, g in enumerate(raw):
            g2 = dict(g)
            g2['prev_gap_length'] = raw[i-1]['length'] if i > 0 else None
            g2['account'] = acct
            out.append(g2)
    return out


# === Same 11 sub-10mb configs as 10_ensemble.py ===

def flat_fn(thresh, gate):
    def f(s, prev): return s['sa_spins'] >= thresh and s['sa_spins'] > 0 and (s['sa_acc']/s['sa_spins']) >= gate
    return f

def sml_fn(s_bound, l_bound, t_s, t_m, t_l, gate):
    def f(s, prev):
        if prev is None: return None
        if prev < s_bound:   thresh = t_s
        elif prev < l_bound: thresh = t_m
        else:                thresh = t_l
        if thresh is None: return False
        sp = s['sa_spins']
        return sp >= thresh and sp > 0 and (s['sa_acc']/sp) >= gate
    return f

def ra_fn(thresh, min_rate, win, min_slope):
    def f(s, prev):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if (s['sa_acc']/sp) < min_rate: return False
        traj = s.get('_traj_ref', [])
        idx  = s.get('_traj_idx', 0)
        if idx >= win:
            sp_prev = traj[idx-win]['sa_spins']
            rate_prev = traj[idx-win]['sa_acc']/sp_prev if sp_prev else 0
        else:
            rate_prev = 0
        slope = (s['sa_acc']/sp) - rate_prev
        return slope >= min_slope
    return f

def combo_fn(thresh, min_acc, min_spn, win, min_slope):
    def f(s, prev):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if (s['sa_acc']/sp) < min_acc: return False
        if (s['sa_spn']/sp) < min_spn: return False
        traj = s.get('_traj_ref', [])
        idx  = s.get('_traj_idx', 0)
        if idx >= win:
            sp_prev = traj[idx-win]['sa_spins']
            rate_prev = traj[idx-win]['sa_acc']/sp_prev if sp_prev else 0
        else:
            rate_prev = 0
        slope = (s['sa_acc']/sp) - rate_prev
        return slope >= min_slope
    return f


CONFIGS = [
    ("COMBO",     combo_fn(110, 0.28, 0.20, 10, 0.010)),
    ("Ideal-RA",  ra_fn(110, 0.30, 8, 0.006)),
    ("RA-t130",   ra_fn(130, 0.28, 10, 0.010)),
    ("F150/.32",  flat_fn(150, 0.32)),
    ("SML-L120/.32",  sml_fn(1, 120, None, None, 130, 0.32)),
    ("SML-L120/.30",  sml_fn(1, 120, None, None, 130, 0.30)),
    ("SML-S100L120-180", sml_fn(100, 120, 150, 180, 130, 0.32)),
    ("SML-S100L120-110", sml_fn(100, 120, 150, 110, 130, 0.32)),
    ("SML-S100L130",  sml_fn(100, 130, 150, 130, 100, 0.32)),
    ("SML-S50L130-150",  sml_fn(50,  130, 100, 150, 100, 0.32)),
    ("SML-S50L130-80",  sml_fn(50,  130,  80, 150, 100, 0.32)),
]


def did_config_catch(fn, gap):
    """Did the config bet on the LAST spin of this gap (= caught the triple)?"""
    prev = gap.get('prev_gap_length')
    traj = gap['trajectory']
    if not traj: return False
    last_idx = len(traj) - 1
    spin = traj[last_idx]
    spin['_traj_ref'] = traj
    spin['_traj_idx'] = last_idx
    decision = fn(spin, prev)
    return bool(decision)


def did_config_bet_anywhere(fn, gap):
    """Did the config bet on ANY spin of this gap?"""
    prev = gap.get('prev_gap_length')
    traj = gap['trajectory']
    for i, spin in enumerate(traj):
        spin['_traj_ref'] = traj
        spin['_traj_idx'] = i
        if fn(spin, prev):
            return True
    return False


def count_bets(fn, gap):
    """How many spins did this config bet on within this gap?"""
    prev = gap.get('prev_gap_length')
    traj = gap['trajectory']
    n = 0
    for i, spin in enumerate(traj):
        spin['_traj_ref'] = traj
        spin['_traj_idx'] = i
        if fn(spin, prev):
            n += 1
    return n


def run():
    gaps = all_gaps_with_prev()

    lines = []
    lines.append("=" * 130)
    lines.append("CHUNK 11: PER-GAP DETAIL — Which configs catch which gaps")
    lines.append("=" * 130)
    lines.append(f"Total ACC gaps: {len(gaps)}")
    lines.append(f"Configs tested: {len(CONFIGS)}")
    lines.append("")
    lines.append("Legend:")
    lines.append("  CAUGHT = config bet on the FINAL spin of the gap (= caught the triple)")
    lines.append("  bets    = total spins this config wasted/spent within this gap (across all spins)")
    lines.append("  PREV    = length of the gap immediately before this one (key for SML L bucket)")
    lines.append("  L=YES   = previous gap was >=120 spins (L bucket — strongest signal)")
    lines.append("")

    # Compute per-gap catch matrix
    gap_data = []
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        catches = []
        bets_per_config = []
        for name, fn in CONFIGS:
            caught = did_config_catch(fn, gap)
            n_bets = count_bets(fn, gap)
            if caught: catches.append(name)
            bets_per_config.append(n_bets)
        gap_data.append({
            'idx': gap_idx,
            'account': gap.get('account'),
            'length': gap['length'],
            'prev_gap': prev,
            'catches': catches,
            'is_l_bucket': prev is not None and prev >= 120,
            'union_caught': len(catches) > 0,
            'total_bets': sum(bets_per_config),
        })

    # === Section 1: All 178 gaps with catch markers ===
    lines.append("=" * 130)
    lines.append("ALL 178 GAPS — ranked by account, then index")
    lines.append("=" * 130)
    header = f"{'#':>4s} {'Acct':>6s} {'len':>4s} {'prev':>5s} {'L':>2s} {'Caught?':>8s} {'#bets':>5s}  {'configs that caught it':<60s}"
    lines.append(header)
    lines.append("-" * 130)

    union_count = 0
    for g in gap_data:
        prev_str = str(g['prev_gap']) if g['prev_gap'] is not None else "—"
        l_str = "Y" if g['is_l_bucket'] else " "
        caught_str = "YES" if g['union_caught'] else ""
        configs_str = ",".join(g['catches']) if g['catches'] else ""
        if g['union_caught']:
            union_count += 1
        lines.append(f"{g['idx']:>4d} {g['account']:>6s} {g['length']:>4d} {prev_str:>5s} {l_str:>2s} "
                     f"{caught_str:>8s} {g['total_bets']:>5d}  {configs_str[:60]:<60s}")

    lines.append(f"\nTotal in ensemble union: {union_count} / {len(gaps)}")

    # === Section 2: Just the caught gaps (62) ===
    lines.append("\n" + "=" * 130)
    lines.append("ONLY THE CAUGHT GAPS (62 expected)")
    lines.append("=" * 130)
    lines.append(header)
    lines.append("-" * 130)

    caught_gaps = [g for g in gap_data if g['union_caught']]
    for g in caught_gaps:
        prev_str = str(g['prev_gap']) if g['prev_gap'] is not None else "—"
        l_str = "Y" if g['is_l_bucket'] else " "
        configs_str = ",".join(g['catches'])
        lines.append(f"{g['idx']:>4d} {g['account']:>6s} {g['length']:>4d} {prev_str:>5s} {l_str:>2s} "
                     f"{'YES':>8s} {g['total_bets']:>5d}  {configs_str[:60]:<60s}")

    # === Section 3: Just the missed gaps (116) ===
    lines.append("\n" + "=" * 130)
    lines.append("ONLY THE MISSED GAPS (gaps no config caught)")
    lines.append("=" * 130)
    lines.append(f"{'#':>4s} {'Acct':>6s} {'len':>4s} {'prev':>5s} {'L':>2s}")
    lines.append("-" * 30)
    missed = [g for g in gap_data if not g['union_caught']]
    for g in missed:
        prev_str = str(g['prev_gap']) if g['prev_gap'] is not None else "—"
        l_str = "Y" if g['is_l_bucket'] else " "
        lines.append(f"{g['idx']:>4d} {g['account']:>6s} {g['length']:>4d} {prev_str:>5s} {l_str:>2s}")
    lines.append(f"\nTotal missed: {len(missed)}")

    # === Section 4: Per-account summary ===
    lines.append("\n" + "=" * 130)
    lines.append("PER-ACCOUNT SUMMARY")
    lines.append("=" * 130)
    for acct in ACCOUNTS:
        acct_gaps = [g for g in gap_data if g['account'] == acct]
        caught   = sum(1 for g in acct_gaps if g['union_caught'])
        l_bucket = sum(1 for g in acct_gaps if g['is_l_bucket'])
        l_caught = sum(1 for g in acct_gaps if g['is_l_bucket'] and g['union_caught'])
        avg_len  = sum(g['length'] for g in acct_gaps) / len(acct_gaps) if acct_gaps else 0
        lines.append(f"  {acct}:  {len(acct_gaps)} gaps, mean_len={avg_len:.1f}, "
                     f"L-bucket={l_bucket}, caught={caught}/{len(acct_gaps)} ({100*caught/len(acct_gaps):.1f}%), "
                     f"L-bucket caught={l_caught}/{l_bucket}")

    # === Section 5: Stats per config (how often each config contributed) ===
    lines.append("\n" + "=" * 130)
    lines.append("PER-CONFIG CONTRIBUTION TO ENSEMBLE")
    lines.append("=" * 130)
    lines.append(f"{'config':>20s}  {'catches':>8s}  {'exclusive':>10s}  {'bet_spins':>10s}  {'mb/hit':>8s}")
    lines.append("-" * 70)

    # Total bet spins per config
    bet_per_config = {name: 0 for name, _ in CONFIGS}
    catches_per_config = {name: 0 for name, _ in CONFIGS}
    union_minus_one = {}  # for exclusivity
    for g in gap_data:
        for name in g['catches']:
            catches_per_config[name] += 1
    for name, fn in CONFIGS:
        for gap in gaps:
            bet_per_config[name] += count_bets(fn, gap)

    # Exclusive catches (only this config caught it)
    for name, _ in CONFIGS:
        excl = sum(1 for g in gap_data if g['catches'] == [name])
        # gaps caught by this config alone
        catches = catches_per_config[name]
        bets    = bet_per_config[name]
        mb      = bets / catches if catches else float('inf')
        lines.append(f"{name:>20s}  {catches:>8d}  {excl:>10d}  {bets:>10d}  {mb:>8.1f}")

    # === Section 6: Exclusive catches per config (which gaps are unique to this config) ===
    lines.append("\n" + "=" * 130)
    lines.append("WHICH SPECIFIC GAPS WOULD BE LOST IF WE REMOVED EACH CONFIG")
    lines.append("=" * 130)
    for name, _ in CONFIGS:
        # Gaps that ONLY this config catches
        only_this = [g for g in gap_data if g['catches'] == [name]]
        if only_this:
            ids = [f"#{g['idx']}({g['account']},len{g['length']},prev{g['prev_gap']})" for g in only_this]
            lines.append(f"  {name:>22s}: {len(only_this)} gap(s) lost: {', '.join(ids)}")
        else:
            lines.append(f"  {name:>22s}: 0 gaps lost (all its catches are also covered by another config)")

    out_path = os.path.join(os.path.dirname(__file__), '11_per_gap_detail.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Saved -> {out_path}")
    print(f"\nTotal: {union_count}/{len(gaps)} caught")
    for acct in ACCOUNTS:
        acct_gaps = [g for g in gap_data if g['account'] == acct]
        caught = sum(1 for g in acct_gaps if g['union_caught'])
        print(f"  {acct}: {caught}/{len(acct_gaps)}")


if __name__ == '__main__':
    run()
