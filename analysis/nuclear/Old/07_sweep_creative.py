"""
Chunk 5: Creative angles nobody tried.

A. Rate acceleration: slope of sa_acc/sa_spins ratio over last N spins
B. Symbol deficit: observed sa_acc - expected(sa_spins * overall_acc_rate)
C. Bivariate gates: sa_acc/sa_spins >= X AND sa_atk/sa_spins <= Y (or similar combos)
D. Per-spin symbol count patterns: recent acc_count density predicts imminent ACC triple
E. N-gram on per-spin reel outcomes (are there forbidden/required predecessor patterns?)
F. accum_pct / accum_delta as predictors
G. Non-ACC triple as trigger (bet only AFTER seeing a specific non-ACC triple in the window)
H. EWMA (exponentially weighted) gap prediction
I. Consecutive short/long streaks
J. Double gate: both sa_acc AND sa_spn above threshold (enrichment by two independent signals)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('ev', os.path.join(os.path.dirname(__file__), '02_eval.py'))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

import pickle
from pathlib import Path
from collections import defaultdict, Counter

GAPS_PATH = Path(__file__).parent / 'gaps.pkl'


def load_ordered(target):
    with open(GAPS_PATH, 'rb') as f:
        data = pickle.load(f)
    out = []
    for acct, d in data.items():
        gaps = d['gaps'].get(target, [])
        for i, g in enumerate(gaps):
            g2 = {**g, 'account': acct}
            g2['prev_gap_length'] = gaps[i-1]['length'] if i > 0 else None
            g2['prev2_gap_length'] = gaps[i-2]['length'] if i > 1 else None
            out.append(g2)
    return out


def run():
    results = []
    results.append("=" * 80)
    results.append("CHUNK 5: CREATIVE ANGLES")
    results.append("=" * 80)

    acc_gaps = ev.all_gaps_for('accumulation')
    results.append(f"ACC gaps: {len(acc_gaps)}")

    # Compute overall acc symbol rate across all data
    total_acc_syms = 0
    total_spins_all = 0
    for g in acc_gaps:
        for s in g['trajectory']:
            total_acc_syms += s['acc_count']
            total_spins_all += 1
    overall_acc_rate = total_acc_syms / total_spins_all if total_spins_all else 0
    results.append(f"Overall acc symbol rate: {overall_acc_rate:.4f}")

    # ======== A. Rate acceleration ========
    results.append("\n--- A. Rate acceleration (slope of ratio over last N spins) ---")
    # At each spin, compute rate = sa_acc / sa_spins. Look at rate[now] - rate[N ago].
    # Positive slope = acc symbols appearing faster = approaching triple
    for N in [10, 20, 30, 50]:
        results.append(f"\n  Window={N}")
        for thresh in [100, 120, 130, 140]:
            for min_slope100 in [-5, 0, 2, 5, 10]:
                min_slope = min_slope100 / 1000.0
                caught = 0; bet_spins = 0; total_spins = 0
                for gap in acc_gaps:
                    traj = gap['trajectory']
                    total_spins += len(traj)
                    for i, spin in enumerate(traj):
                        sp = spin['sa_spins']
                        if sp < thresh or sp == 0:
                            continue
                        rate_now = spin['sa_acc'] / sp
                        # Rate N spins ago
                        if i >= N:
                            sp_prev = traj[i-N]['sa_spins']
                            if sp_prev > 0:
                                rate_prev = traj[i-N]['sa_acc'] / sp_prev
                                slope = rate_now - rate_prev
                            else:
                                slope = 0
                        else:
                            slope = 0  # not enough history
                        if slope >= min_slope and rate_now >= 0.28:
                            bet_spins += 1
                            if i == len(traj) - 1:
                                caught += 1
                total_gaps = len(acc_gaps)
                if caught >= 5 and bet_spins > 0:
                    bp = bet_spins / total_spins
                    br = total_gaps / total_spins
                    bhr = caught / bet_spins
                    mb = bet_spins / caught
                    lift = bhr / br if br else 0
                    results.append(f"    t={thresh} slope>={min_slope:.3f}: {caught:3d}/{total_gaps:3d}  mb={mb:.1f}  lift={lift:.2f}x")

    # ======== B. Symbol deficit ========
    results.append("\n--- B. Symbol deficit: observed sa_acc - expected ---")
    for thresh in [100, 120, 130, 140]:
        for min_def in range(-15, 16, 3):
            def make(t, md, r):
                def f(s):
                    sp = s['sa_spins']
                    if sp < t or sp == 0: return False
                    expected = sp * r
                    deficit = s['sa_acc'] - expected
                    return deficit >= md
                return f
            r = ev.simulate_fast(make(thresh, min_def, overall_acc_rate), acc_gaps)
            if r['caught'] >= 5:
                results.append(f"  t={thresh} deficit>={min_def:+d}: {ev.fmt_result(r)}")

    # ======== C. Bivariate gates ========
    results.append("\n--- C. Bivariate gates (threshold=130) ---")
    # acc rate >= X AND another counter <= Y
    SA_OTHERS = ['sa_spn', 'sa_atk', 'sa_stl', 'sa_shd']
    results.append(f"{'acc_gate':>8s} {'other':>8s} {'max_rate':>8s}  {'caught':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for acc_g100 in [28, 30, 32]:
        acc_gate = acc_g100 / 100.0
        for other in SA_OTHERS:
            for max_r100 in range(5, 35, 3):
                max_rate = max_r100 / 100.0
                def make(ag, o, mr):
                    def f(s):
                        sp = s['sa_spins']
                        if sp < 130 or sp == 0: return False
                        if (s['sa_acc'] / sp) < ag: return False
                        return (s[o] / sp) <= mr
                    return f
                r = ev.simulate_fast(make(acc_gate, other, max_rate), acc_gaps)
                if r['caught'] >= 5:
                    results.append(f"{acc_gate:8.2f} {other:>8s} <={max_rate:5.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # Also: acc rate >= X AND another counter >= Y (enrichment by correlated signal)
    results.append(f"\n{'acc_gate':>8s} {'other':>8s} {'min_rate':>8s}  {'caught':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for acc_g100 in [28, 30, 32]:
        acc_gate = acc_g100 / 100.0
        for other in SA_OTHERS:
            for min_r100 in range(10, 40, 3):
                min_rate = min_r100 / 100.0
                def make(ag, o, mr):
                    def f(s):
                        sp = s['sa_spins']
                        if sp < 130 or sp == 0: return False
                        if (s['sa_acc'] / sp) < ag: return False
                        return (s[o] / sp) >= mr
                    return f
                r = ev.simulate_fast(make(acc_gate, other, min_rate), acc_gaps)
                if r['caught'] >= 5:
                    results.append(f"{acc_gate:8.2f} {other:>8s} >={min_rate:5.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # ======== D. Recent per-spin acc_count density ========
    results.append("\n--- D. Recent acc_count density (rolling window) ---")
    # In last N spins, how many had acc_count >= 1? If high -> triple coming
    for win in [5, 10, 15, 20, 30]:
        for min_density100 in range(20, 80, 10):
            min_dens = min_density100 / 100.0
            caught = 0; bet_spins = 0; total_spins = 0
            for gap in acc_gaps:
                traj = gap['trajectory']
                total_spins += len(traj)
                for i, spin in enumerate(traj):
                    sp = spin['sa_spins']
                    if sp < 100:  # minimum threshold
                        continue
                    # Count acc symbols in last `win` spins
                    start = max(0, i - win + 1)
                    window = traj[start:i+1]
                    acc_hits = sum(1 for s in window if s['acc_count'] >= 1)
                    density = acc_hits / len(window)
                    if density >= min_dens:
                        bet_spins += 1
                        if i == len(traj) - 1:
                            caught += 1
            tg = len(acc_gaps)
            if caught >= 5 and bet_spins > 0:
                mb = bet_spins / caught
                br = tg / total_spins
                bhr = caught / bet_spins
                lift = bhr / br if br else 0
                results.append(f"  win={win:2d} density>={min_dens:.2f}: {caught:3d}/{tg:3d}  mb={mb:.1f}  lift={lift:.2f}x")

    # ======== E. Predecessor pattern (what symbol tuple preceded ACC triple?) ========
    results.append("\n--- E. Predecessor patterns (N spins before ACC triple) ---")
    # What are the most common reel tuples in the 5 spins before an ACC triple?
    predecessors = Counter()
    for gap in acc_gaps:
        traj = gap['trajectory']
        if len(traj) >= 3:
            for k in range(max(0, len(traj)-6), len(traj)-1):
                s = traj[k]
                predecessors[(s['reel_1'], s['reel_2'], s['reel_3'])] += 1
    results.append(f"  Top 20 predecessor tuples (5 spins before ACC triple):")
    for tup, cnt in predecessors.most_common(20):
        results.append(f"    {tup}: {cnt}")

    # ======== F. accum_pct as predictor ========
    results.append("\n--- F. accum_pct at ACC triple ---")
    for gap in acc_gaps:
        last_spin = gap['trajectory'][-1]
        gap['_accum_pct'] = last_spin['accum_pct']
    pcts = [g['_accum_pct'] for g in acc_gaps]
    results.append(f"  accum_pct at ACC triple: mean={sum(pcts)/len(pcts):.1f}  min={min(pcts):.1f}  max={max(pcts):.1f}")
    # Does betting only when accum_pct is high help?
    for min_pct in [30, 50, 60, 70, 80, 90]:
        def make(mp):
            def f(s):
                sp = s['sa_spins']
                if sp < 130 or sp == 0: return False
                if (s['sa_acc'] / sp) < 0.30: return False
                return s['accum_pct'] >= mp
            return f
        r = ev.simulate_fast(make(min_pct), acc_gaps)
        if r['caught'] >= 3:
            results.append(f"  accum_pct >= {min_pct}: {ev.fmt_result(r)}")

    # ======== G. Non-ACC triple as trigger (oneshot gate) ========
    results.append("\n--- G. Non-ACC triple as trigger in BET zone ---")
    # Once in BET zone (130/0.30), wait for a non-ACC triple before betting
    for trigger_types in [['attack'], ['steal'], ['shield'], ['spins'],
                          ['attack', 'steal'], ['attack', 'steal', 'shield'],
                          ['attack', 'steal', 'shield', 'spins']]:
        trigger_set = set(trigger_types)
        caught = 0; bet_spins = 0; total_spins = 0
        for gap in acc_gaps:
            traj = gap['trajectory']
            total_spins += len(traj)
            triggered = False
            for i, spin in enumerate(traj):
                sp = spin['sa_spins']
                in_zone = sp >= 130 and sp > 0 and (spin['sa_acc'] / sp) >= 0.30
                if in_zone and not triggered:
                    # Check if this spin is a non-ACC triple that triggers
                    if spin['triple'] in trigger_set:
                        triggered = True
                if in_zone and triggered:
                    bet_spins += 1
                    if i == len(traj) - 1:
                        caught += 1
        tg = len(acc_gaps)
        if caught >= 3 and bet_spins > 0:
            mb = bet_spins / caught
            br = tg / total_spins
            bhr = caught / bet_spins
            lift = bhr / br if br else 0
            trig_str = '+'.join(trigger_types)
            results.append(f"  trigger={trig_str}: {caught:3d}/{tg:3d}  mb={mb:.1f}  lift={lift:.2f}x")

    # ======== H. EWMA gap prediction ========
    results.append("\n--- H. EWMA gap prediction ---")
    all_ordered = load_ordered('accumulation')
    for alpha10 in [1, 2, 3, 5, 7]:
        alpha = alpha10 / 10.0
        caught = 0; bet_spins = 0; total_spins = 0
        ewma = 100.0  # initial estimate
        for gap in all_ordered:
            traj = gap['trajectory']
            total_spins += len(traj)
            thresh = ewma * 1.1  # bet when past 110% of EWMA prediction
            for i, spin in enumerate(traj):
                sp = spin['sa_spins']
                if sp >= thresh and sp > 0 and (spin['sa_acc'] / sp) >= 0.30:
                    bet_spins += 1
                    if i == len(traj) - 1:
                        caught += 1
            ewma = alpha * gap['length'] + (1 - alpha) * ewma
        tg = len(all_ordered)
        if caught >= 5 and bet_spins > 0:
            mb = bet_spins / caught
            br = tg / total_spins
            bhr = caught / bet_spins
            lift = bhr / br if br else 0
            results.append(f"  alpha={alpha:.1f}: {caught:3d}/{tg:3d}  mb={mb:.1f}  lift={lift:.2f}x")

    # ======== I. Consecutive short/long streaks ========
    results.append("\n--- I. Streak detection: consecutive S or L gaps ---")
    for streak_len in [2, 3]:
        for streak_type in ['S', 'L']:
            caught = 0; bet_spins = 0; total_spins = 0
            for gap in all_ordered:
                traj = gap['trajectory']
                total_spins += len(traj)
                # Check streak of last N gaps
                # Need multiple prev gaps
                prev_lens = []
                for key in ['prev_gap_length', 'prev2_gap_length']:
                    v = gap.get(key)
                    if v is not None:
                        prev_lens.append(v)
                if len(prev_lens) < streak_len:
                    continue
                if streak_type == 'S':
                    in_streak = all(p < 80 for p in prev_lens[:streak_len])
                else:
                    in_streak = all(p >= 130 for p in prev_lens[:streak_len])
                if not in_streak:
                    continue
                # After streak, use aggressive threshold
                thresh = 80 if streak_type == 'L' else 150
                for i, spin in enumerate(traj):
                    sp = spin['sa_spins']
                    if sp >= thresh and sp > 0 and (spin['sa_acc'] / sp) >= 0.28:
                        bet_spins += 1
                        if i == len(traj) - 1:
                            caught += 1
            tg = len(all_ordered)
            if caught >= 3 and bet_spins > 0:
                mb = bet_spins / caught
                br = tg / total_spins
                bhr = caught / bet_spins
                lift = bhr / br if br else 0
                results.append(f"  streak={streak_len}x{streak_type} thresh={'80 (aggr)' if streak_type=='L' else '150 (cons)'}: {caught:3d}/{tg:3d}  mb={mb:.1f}  lift={lift:.2f}x")

    # ======== J. Double gate: both acc AND spn above threshold ========
    results.append("\n--- J. Double gate: sa_acc AND sa_spn both above threshold ---")
    for acc_g100 in [26, 28, 30, 32]:
        acc_gate = acc_g100 / 100.0
        for spn_g100 in [15, 18, 20, 22, 25, 28]:
            spn_gate = spn_g100 / 100.0
            for thresh in [100, 110, 120, 130, 140]:
                def make(t, ag, sg):
                    def f(s):
                        sp = s['sa_spins']
                        if sp < t or sp == 0: return False
                        return (s['sa_acc'] / sp) >= ag and (s['sa_spn'] / sp) >= sg
                    return f
                r = ev.simulate_fast(make(thresh, acc_gate, spn_gate), acc_gaps)
                if r['caught'] >= 5:
                    results.append(f"  t={thresh} acc>={acc_gate:.2f} spn>={spn_gate:.2f}: {ev.fmt_result(r)}")

    out_path = os.path.join(os.path.dirname(__file__), '07_creative_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print(f"Saved -> {out_path}")
    print(f"Total lines: {len(results)}")


if __name__ == '__main__':
    run()
