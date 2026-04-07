"""
Chunk 2: Symbol counter sweeps for ACC and SPN.

Test EVERY sa_*/ss_* counter as the rate gate numerator, not just sa_acc/ss_spn.
Also test:
  - All single counters as gates
  - All pairs (sum of two counters / sa_spins)
  - Inverse gates (low values of a counter)
  - sa_3x_* counters as raw count gates (not rates)
  - Combined counts (total non-acc symbols, total triples, etc.)
  - Cross-counter ratios (sa_atk/sa_acc, sa_spn/sa_acc, etc.)
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('ev', os.path.join(os.path.dirname(__file__), '02_eval.py'))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

SA_SYMS = ['sa_acc', 'sa_spn', 'sa_atk', 'sa_stl', 'sa_shd']
SA_3X   = ['sa_3x_atk', 'sa_3x_stl', 'sa_3x_shd']
SS_SYMS = ['ss_acc', 'ss_spn', 'ss_atk', 'ss_stl', 'ss_shd']
SS_3X   = ['ss_3x_atk', 'ss_3x_stl', 'ss_3x_shd']


def run():
    results = []
    results.append("=" * 80)
    results.append("CHUNK 2: SYMBOL COUNTER SWEEPS")
    results.append("=" * 80)

    # ========== ACC ==========
    acc_gaps = ev.all_gaps_for('accumulation')
    results.append(f"\n{'='*40} ACC ({len(acc_gaps)} gaps) {'='*40}")

    # 2A. Single sa_* counter as rate gate (all counters, threshold=130)
    results.append("\n--- ACC: Each sa_* counter as rate gate (threshold=130) ---")
    results.append(f"{'counter':>12s}  {'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for counter in SA_SYMS:
        for g100 in range(15, 46, 1):
            gate = g100 / 100.0
            def make(c, g):
                def f(s):
                    if s['sa_spins'] < 130 or s['sa_spins'] == 0: return False
                    return (s[c] / s['sa_spins']) >= g
                return f
            r = ev.simulate_fast(make(counter, gate), acc_gaps)
            if r['caught'] >= 5:
                results.append(f"{counter:>12s}  {gate:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 2B. sa_3x_* counters as raw count gates (# of other triples since last ACC)
    results.append("\n--- ACC: sa_3x_* as raw count gate (threshold=130, gate=0.30) ---")
    results.append(f"{'counter':>12s}  {'min_count':>9s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for counter in SA_3X:
        for min_c in range(0, 20):
            def make(c, mc):
                def f(s):
                    if s['sa_spins'] < 130 or s['sa_spins'] == 0: return False
                    rate_ok = (s['sa_acc'] / s['sa_spins']) >= 0.30
                    count_ok = s[c] >= mc
                    return rate_ok and count_ok
                return f
            r = ev.simulate_fast(make(counter, min_c), acc_gaps)
            if r['caught'] >= 3:
                results.append(f"{counter:>12s}  {min_c:9d}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 2C. Sum of two counters as rate gate
    results.append("\n--- ACC: Sum of 2 counters as rate gate (threshold=130) ---")
    results.append(f"{'pair':>24s}  {'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for i, c1 in enumerate(SA_SYMS):
        for c2 in SA_SYMS[i+1:]:
            for g100 in range(25, 55, 2):
                gate = g100 / 100.0
                def make(a, b, g):
                    def f(s):
                        if s['sa_spins'] < 130 or s['sa_spins'] == 0: return False
                        return ((s[a] + s[b]) / s['sa_spins']) >= g
                    return f
                r = ev.simulate_fast(make(c1, c2, gate), acc_gaps)
                if r['caught'] >= 5:
                    results.append(f"{c1+'+'+c2:>24s}  {gate:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 2D. Inverse gates (BET when counter is LOW — maybe low atk signals incoming acc?)
    results.append("\n--- ACC: Inverse gate (BET when counter is LOW, threshold=130) ---")
    results.append(f"{'counter':>12s}  {'max_rate':>8s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for counter in SA_SYMS:
        if counter == 'sa_acc':
            continue  # skip — low acc rate is opposite of pity signal
        for g100 in range(5, 30, 2):
            gate = g100 / 100.0
            def make(c, g):
                def f(s):
                    if s['sa_spins'] < 130 or s['sa_spins'] == 0: return False
                    return (s[c] / s['sa_spins']) <= g
                return f
            r = ev.simulate_fast(make(counter, gate), acc_gaps)
            if r['caught'] >= 5:
                results.append(f"{counter:>12s}  <={gate:5.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 2E. Cross-counter ratios: sa_X / sa_Y (not rate against sa_spins)
    results.append("\n--- ACC: Cross-counter ratio gate (threshold=130) ---")
    results.append(f"{'ratio':>24s}  {'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for num in SA_SYMS:
        for den in SA_SYMS:
            if num == den:
                continue
            for g100 in range(30, 200, 10):
                gate = g100 / 100.0
                def make(n, d, g):
                    def f(s):
                        if s['sa_spins'] < 130 or s['sa_spins'] == 0: return False
                        if s[d] == 0: return False
                        return (s[n] / s[d]) >= g
                    return f
                r = ev.simulate_fast(make(num, den, gate), acc_gaps)
                if r['caught'] >= 5:
                    results.append(f"{num+'/'+den:>24s}  {gate:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 2F. "Total non-acc symbols" as gate
    results.append("\n--- ACC: Total non-ACC symbols rate gate (threshold=130) ---")
    results.append(f"{'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for g100 in range(40, 90, 2):
        gate = g100 / 100.0
        def make(g):
            def f(s):
                if s['sa_spins'] < 130 or s['sa_spins'] == 0: return False
                non_acc = s['sa_atk'] + s['sa_stl'] + s['sa_shd'] + s['sa_spn']
                return (non_acc / s['sa_spins']) >= g
            return f
        r = ev.simulate_fast(make(gate), acc_gaps)
        if r['caught'] >= 5:
            results.append(f"{gate:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 2G. "Total other triples" as count gate
    results.append("\n--- ACC: Total other triples count gate (threshold=130, rate=0.30) ---")
    results.append(f"{'min_3x':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for min_3x in range(0, 20):
        def make(m):
            def f(s):
                if s['sa_spins'] < 130 or s['sa_spins'] == 0: return False
                if (s['sa_acc'] / s['sa_spins']) < 0.30: return False
                total_3x = s['sa_3x_atk'] + s['sa_3x_stl'] + s['sa_3x_shd']
                return total_3x >= m
            return f
        r = ev.simulate_fast(make(min_3x), acc_gaps)
        if r['caught'] >= 3:
            results.append(f"{min_3x:6d}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # ========== SPN with ss_* ==========
    spn_gaps = ev.all_gaps_for('spins')
    results.append(f"\n{'='*40} SPN ({len(spn_gaps)} gaps) {'='*40}")

    # 3A. Single ss_* counter as rate gate
    results.append("\n--- SPN: Each ss_* counter as rate gate (threshold=87) ---")
    results.append(f"{'counter':>12s}  {'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for counter in SS_SYMS:
        for g100 in range(15, 46, 1):
            gate = g100 / 100.0
            def make(c, g):
                def f(s):
                    if s['ss_spins'] < 87 or s['ss_spins'] == 0: return False
                    return (s[c] / s['ss_spins']) >= g
                return f
            r = ev.simulate_fast(make(counter, gate), spn_gaps)
            if r['caught'] >= 5:
                results.append(f"{counter:>12s}  {gate:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 3B. ss_3x_* raw count gates
    results.append("\n--- SPN: ss_3x_* raw count gate (threshold=87, spn_rate>=0.25) ---")
    results.append(f"{'counter':>12s}  {'min_count':>9s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for counter in SS_3X:
        for min_c in range(0, 15):
            def make(c, mc):
                def f(s):
                    if s['ss_spins'] < 87 or s['ss_spins'] == 0: return False
                    rate_ok = (s['ss_spn'] / s['ss_spins']) >= 0.25
                    count_ok = s[c] >= mc
                    return rate_ok and count_ok
                return f
            r = ev.simulate_fast(make(counter, min_c), spn_gaps)
            if r['caught'] >= 3:
                results.append(f"{counter:>12s}  {min_c:9d}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 3C. Sum of two ss_* counters
    results.append("\n--- SPN: Sum of 2 ss_* counters rate gate (threshold=87) ---")
    results.append(f"{'pair':>24s}  {'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for i, c1 in enumerate(SS_SYMS):
        for c2 in SS_SYMS[i+1:]:
            for g100 in range(25, 55, 2):
                gate = g100 / 100.0
                def make(a, b, g):
                    def f(s):
                        if s['ss_spins'] < 87 or s['ss_spins'] == 0: return False
                        return ((s[a] + s[b]) / s['ss_spins']) >= g
                    return f
                r = ev.simulate_fast(make(c1, c2, gate), spn_gaps)
                if r['caught'] >= 5:
                    results.append(f"{c1+'+'+c2:>24s}  {gate:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    out_path = os.path.join(os.path.dirname(__file__), '04_symbol_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print(f"Saved -> {out_path}")
    print(f"Total lines: {len(results)}")


if __name__ == '__main__':
    run()
