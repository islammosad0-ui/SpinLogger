"""
Chunk 4: Conditional / Markov / Stratification sweeps.

Tests:
  A. Previous triple type conditioning (what was the last real triple before ACC?)
  B. Previous gap length as a continuous predictor (shift threshold)
  C. Lookback: last 2-3 gaps window sum/mean
  D. Bet level stratification (different prob tables per bet)
  E. Event type (standard vs mix) stratification
  F. Mission boundary effects
  G. GAE grand prize (list tier) stratification
  H. Lag-1/2/3 gap autocorrelation analysis
  I. Transition matrix: gap size -> next gap size
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('ev', os.path.join(os.path.dirname(__file__), '02_eval.py'))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

import pickle
from pathlib import Path
from collections import defaultdict
import math

GAPS_PATH = Path(__file__).parent / 'gaps.pkl'


def load_ordered(target):
    with open(GAPS_PATH, 'rb') as f:
        data = pickle.load(f)
    out = []
    for acct, d in data.items():
        gaps = d['gaps'].get(target, [])
        for i, g in enumerate(gaps):
            prev_len = gaps[i-1]['length'] if i > 0 else None
            prev2_len = gaps[i-2]['length'] if i > 1 else None
            prev3_len = gaps[i-3]['length'] if i > 2 else None
            out.append({
                **g,
                'prev_gap_length': prev_len,
                'prev2_gap_length': prev2_len,
                'prev3_gap_length': prev3_len,
                'account': acct,
            })
    return out


def run():
    results = []
    results.append("=" * 80)
    results.append("CHUNK 4: CONDITIONAL / MARKOV / STRATIFICATION")
    results.append("=" * 80)

    acc_gaps = load_ordered('accumulation')
    results.append(f"Total ACC gaps: {len(acc_gaps)}")

    # ======== A. Previous triple type conditioning ========
    results.append("\n--- A. Previous real triple type before ACC ---")
    # Group gaps by what the last real triple was before this ACC triple
    by_prev = defaultdict(list)
    for g in acc_gaps:
        pt = g.get('prev_real_triple', None)
        by_prev[pt or 'None/first'].append(g)
    for pt, gaps in sorted(by_prev.items()):
        results.append(f"\n  prev_triple={pt}: {len(gaps)} gaps")
        if len(gaps) < 3:
            continue
        lengths = [g['length'] for g in gaps]
        results.append(f"    gap mean={sum(lengths)/len(lengths):.1f}  min={min(lengths)}  max={max(lengths)}")
        # Try formula on this subset
        for t in [100, 110, 120, 130, 140]:
            for g100 in [28, 30, 32]:
                gate = g100 / 100.0
                def make(thresh, g):
                    def f(s):
                        if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
                        return (s['sa_acc'] / s['sa_spins']) >= g
                    return f
                r = ev.simulate_fast(make(t, gate), gaps)
                if r['caught'] >= 2:
                    results.append(f"    {t}/{gate:.2f}: {ev.fmt_result(r)}")

    # ======== B. Threshold shift based on previous gap ========
    results.append("\n--- B. Shift threshold by previous gap (threshold = base - shift*(prev-mean)) ---")
    gaps_w_prev = [g for g in acc_gaps if g['prev_gap_length'] is not None]
    mean_gap = sum(g['length'] for g in gaps_w_prev) / len(gaps_w_prev)
    results.append(f"  Mean gap (all with prev): {mean_gap:.1f}")
    results.append(f"{'base':>6s} {'shift':>6s} {'gate':>5s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    shift_results = []
    for base in range(100, 180, 10):
        for shift10 in range(0, 8):  # shift = 0.0 to 0.7
            shift = shift10 / 10.0
            for g100 in [28, 30, 32]:
                gate = g100 / 100.0
                def make(b, sh, g, mn):
                    def f(s):
                        if s['sa_spins'] == 0: return False
                        return (s['sa_acc'] / s['sa_spins']) >= g and s['sa_spins'] >= b
                    return f
                # Apply shifted threshold per gap
                caught = 0; bet_spins = 0; total_spins = 0
                for gap in gaps_w_prev:
                    traj = gap['trajectory']
                    total_spins += len(traj)
                    prev = gap['prev_gap_length']
                    thresh = base - shift * (prev - mean_gap)
                    thresh = max(thresh, 30)  # floor
                    for i, spin in enumerate(traj):
                        sp = spin['sa_spins']
                        if sp >= thresh and sp > 0 and (spin['sa_acc'] / sp) >= gate:
                            bet_spins += 1
                            if i == len(traj) - 1:
                                caught += 1
                total_gaps = len(gaps_w_prev)
                bet_pct = bet_spins / total_spins if total_spins else 0
                base_rate = total_gaps / total_spins if total_spins else 0
                bet_hit_rate = caught / bet_spins if bet_spins else 0
                mb = bet_spins / caught if caught else float('inf')
                lift = bet_hit_rate / base_rate if base_rate else 0
                if caught >= 5:
                    shift_results.append((base, shift, gate, caught, total_gaps, bet_pct, mb, lift))
                    results.append(f"{base:6d} {shift:6.1f} {gate:5.2f}  {caught:3d}/{total_gaps:3d}  {bet_pct*100:6.2f}%  {mb:8.1f}  {lift:6.2f}x")
    if shift_results:
        best = max(shift_results, key=lambda x: x[7])
        results.append(f"  Best shift: base={best[0]} shift={best[1]} gate={best[2]:.2f} -> {best[3]}/{best[4]} lift={best[7]:.2f}x")

    # ======== C. Lookback: last 2-3 gaps window ========
    results.append("\n--- C. Lookback sum/mean prediction ---")
    # Window sum: if sum of last N gaps is < X, bet with lower threshold
    for N in [2, 3]:
        results.append(f"\n  Lookback={N} gap(s)")
        valid = [g for g in acc_gaps if (g['prev_gap_length'] is not None and
                 (N <= 2 or g.get('prev2_gap_length') is not None) and
                 (N <= 3 or g.get('prev3_gap_length') is not None))]
        # Compute lookback sum
        for g in valid:
            if N == 2:
                g['_lb_sum'] = g['prev_gap_length'] + (g.get('prev2_gap_length') or 0)
            else:
                g['_lb_sum'] = (g['prev_gap_length'] + (g.get('prev2_gap_length') or 0) +
                                (g.get('prev3_gap_length') or 0))
        results.append(f"  valid gaps: {len(valid)}")
        sums = [g['_lb_sum'] for g in valid]
        if sums:
            results.append(f"  lookback sum: mean={sum(sums)/len(sums):.1f} min={min(sums)} max={max(sums)}")

        # If lookback sum is high (debt building) -> use lower threshold
        results.append(f"  {'sum_thresh':>10s} {'lo_t':>5s} {'hi_t':>5s} {'gate':>5s}  {'caught':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
        for sum_t in range(150, 400, 50):
            for lo_t in [80, 100, 110, 120]:
                for hi_t in [130, 140, 150, 160]:
                    for g100 in [28, 30, 32]:
                        gate = g100 / 100.0
                        caught = 0; bet_spins = 0; total_spins = 0
                        for gap in valid:
                            traj = gap['trajectory']
                            total_spins += len(traj)
                            thresh = lo_t if gap['_lb_sum'] >= sum_t else hi_t
                            for i, spin in enumerate(traj):
                                sp = spin['sa_spins']
                                if sp >= thresh and sp > 0 and (spin['sa_acc'] / sp) >= gate:
                                    bet_spins += 1
                                    if i == len(traj) - 1:
                                        caught += 1
                        tg = len(valid)
                        if caught >= 5 and bet_spins > 0:
                            bp = bet_spins/total_spins
                            mb = bet_spins/caught
                            br = tg/total_spins
                            bhr = caught/bet_spins
                            lift = bhr/br if br else 0
                            results.append(f"  {sum_t:10d} {lo_t:5d} {hi_t:5d} {gate:5.2f}  {caught:3d}/{tg:3d}  {mb:8.1f}  {lift:6.2f}x")

    # ======== D. Bet level stratification ========
    results.append("\n--- D. Bet level stratification ---")
    by_bet = defaultdict(list)
    for g in acc_gaps:
        # Use the dominant bet level in trajectory
        bets = [s['bet_level'] for s in g['trajectory']]
        mode_bet = max(set(bets), key=bets.count) if bets else 0
        by_bet[mode_bet].append(g)
    for bl, gaps in sorted(by_bet.items()):
        lengths = [g['length'] for g in gaps]
        results.append(f"  bet_level={bl}: {len(gaps)} gaps  mean_len={sum(lengths)/len(lengths):.1f}")
        def baseline_fn(s):
            if s['sa_spins'] < 130 or s['sa_spins'] == 0: return False
            return (s['sa_acc'] / s['sa_spins']) >= 0.30
        if len(gaps) >= 3:
            r = ev.simulate_fast(baseline_fn, gaps)
            results.append(f"    130/0.30: {ev.fmt_result(r)}")

    # ======== E. Event type (standard vs mix) ========
    results.append("\n--- E. Event type: standard vs mix ---")
    for g in acc_gaps:
        mix_spins = sum(1 for s in g['trajectory'] if s['mix_signal'])
        g['_is_mix'] = mix_spins > 5  # at least 5 mix signals in gap
    std_gaps = [g for g in acc_gaps if not g['_is_mix']]
    mix_gaps = [g for g in acc_gaps if g['_is_mix']]
    for label, gaps in [('standard', std_gaps), ('mix', mix_gaps)]:
        results.append(f"\n  {label}: {len(gaps)} gaps")
        if len(gaps) < 5:
            continue
        lengths = [g['length'] for g in gaps]
        results.append(f"    mean_len={sum(lengths)/len(lengths):.1f}")
        for t in [100, 110, 120, 130, 140]:
            for g100 in [28, 30, 32]:
                gate = g100 / 100.0
                def make(thresh, g):
                    def f(s):
                        if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
                        return (s['sa_acc'] / s['sa_spins']) >= g
                    return f
                r = ev.simulate_fast(make(t, gate), gaps)
                if r['caught'] >= 3:
                    results.append(f"    {t}/{gate:.2f}: {ev.fmt_result(r)}")

    # ======== F. Mission boundary ========
    results.append("\n--- F. Mission boundary analysis ---")
    # Check if gaps that end near a mission milestone have different lengths
    missions = [g['end_mission'] for g in acc_gaps]
    results.append(f"  Mission range: {min(missions)} to {max(missions)}")
    # Group into low/mid/high mission
    for lo, hi, label in [(0, 20, 'low(0-20)'), (20, 40, 'mid(20-40)'), (40, 80, 'high(40-80)'), (80, 200, 'vhigh(80+)')]:
        subset = [g for g in acc_gaps if lo <= g['end_mission'] < hi]
        if len(subset) >= 3:
            lengths = [g['length'] for g in subset]
            results.append(f"  {label}: {len(subset)} gaps  mean_len={sum(lengths)/len(lengths):.1f}")

    # ======== G. GAE grand prize tier ========
    results.append("\n--- G. GAE grand prize (list tier) ---")
    by_gp = defaultdict(list)
    for g in acc_gaps:
        gp = g.get('end_grand_prize', 0)
        by_gp[gp].append(g)
    for gp, gaps in sorted(by_gp.items()):
        lengths = [g['length'] for g in gaps]
        results.append(f"  grand_prize={gp}: {len(gaps)} gaps  mean_len={sum(lengths)/len(lengths):.1f}")

    # ======== H. Autocorrelation ========
    results.append("\n--- H. Gap autocorrelation (lag 1-5) ---")
    with open(GAPS_PATH, 'rb') as f:
        data = pickle.load(f)
    for acct, d in data.items():
        gaps = d['gaps'].get('accumulation', [])
        lengths = [g['length'] for g in gaps]
        n = len(lengths)
        if n < 10:
            continue
        mean = sum(lengths) / n
        var = sum((x - mean)**2 for x in lengths) / n
        results.append(f"\n  {acct} ({n} gaps, mean={mean:.1f}, std={var**0.5:.1f}):")
        for lag in range(1, 6):
            if lag >= n:
                break
            cov = sum((lengths[i] - mean) * (lengths[i+lag] - mean) for i in range(n - lag)) / (n - lag)
            acf = cov / var if var > 0 else 0
            results.append(f"    lag-{lag}: r={acf:+.3f}")

    # ======== I. Transition matrix ========
    results.append("\n--- I. Gap size transition matrix ---")
    BINS = [(0, 50, 'XS'), (50, 80, 'S'), (80, 110, 'M'), (110, 150, 'L'), (150, 9999, 'XL')]
    def bin_gap(length):
        for lo, hi, label in BINS:
            if lo <= length < hi:
                return label
        return 'XL'

    trans = defaultdict(lambda: defaultdict(int))
    for acct, d in data.items():
        gaps = d['gaps'].get('accumulation', [])
        for i in range(1, len(gaps)):
            prev_bin = bin_gap(gaps[i-1]['length'])
            curr_bin = bin_gap(gaps[i]['length'])
            trans[prev_bin][curr_bin] += 1

    bin_labels = ['XS', 'S', 'M', 'L', 'XL']
    results.append(f"  {'From\\To':>8s}  " + "  ".join(f"{b:>5s}" for b in bin_labels))
    for pb in bin_labels:
        total = sum(trans[pb].values())
        if total == 0:
            continue
        row = []
        for cb in bin_labels:
            pct = trans[pb][cb] / total * 100 if total else 0
            row.append(f"{pct:5.1f}")
        results.append(f"  {pb:>8s}  " + "  ".join(row) + f"  (n={total})")

    out_path = os.path.join(os.path.dirname(__file__), '06_conditional_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print(f"Saved -> {out_path}")
    print(f"Total lines: {len(results)}")


if __name__ == '__main__':
    run()
