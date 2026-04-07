"""
Chunk 1: Univariate sweeps for ACC and SPN.
Fine-grain sweep of every single parameter independently.

Dimensions:
  - spinThreshold (start): 10 to 250 step 5
  - rateGate: 0.15 to 0.45 step 0.01
  - stopCap (end of window): threshold+10 to 400 step 10
  - counter used as numerator: sa_acc, sa_spn, sa_atk, sa_stl, sa_shd, sa_3x_atk, sa_3x_stl, sa_3x_shd (for ACC)
  - same for SPN with ss_* counters

For each sweep, hold other params at baseline and vary one dimension.
Then do a 2D sweep: threshold x gate (the two strongest params).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('ev', os.path.join(os.path.dirname(__file__), '02_eval.py'))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)

def run():
    results = []
    results.append("=" * 80)
    results.append("CHUNK 1: UNIVARIATE SWEEPS")
    results.append("=" * 80)

    # ========== ACC ==========
    acc_gaps = ev.all_gaps_for('accumulation')
    results.append(f"\n{'='*40} ACC ({len(acc_gaps)} gaps) {'='*40}")

    # 1A. Spin threshold sweep (gate=0.30 fixed)
    results.append("\n--- ACC: Spin Threshold sweep (gate=0.30, no stop) ---")
    results.append(f"{'thresh':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for t in range(10, 260, 5):
        def make(thresh):
            def f(s):
                if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
                return (s['sa_acc'] / s['sa_spins']) >= 0.30
            return f
        r = ev.simulate_fast(make(t), acc_gaps)
        if r['caught'] > 0:
            results.append(f"{t:6d}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 1B. Rate gate sweep (threshold=130 fixed)
    results.append("\n--- ACC: Rate Gate sweep (threshold=130, no stop) ---")
    results.append(f"{'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for g100 in range(15, 46):
        gate = g100 / 100.0
        def make(g):
            def f(s):
                if s['sa_spins'] < 130 or s['sa_spins'] == 0: return False
                return (s['sa_acc'] / s['sa_spins']) >= g
            return f
        r = ev.simulate_fast(make(gate), acc_gaps)
        if r['caught'] > 0:
            results.append(f"{gate:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 1C. Stop cap sweep (threshold=130, gate=0.30, add stop)
    results.append("\n--- ACC: Stop Cap sweep (threshold=130, gate=0.30) ---")
    results.append(f"{'stop':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for stop in range(140, 410, 10):
        def make(st):
            def f(s):
                sp = s['sa_spins']
                if sp < 130 or sp > st or sp == 0: return False
                return (s['sa_acc'] / sp) >= 0.30
            return f
        r = ev.simulate_fast(make(stop), acc_gaps)
        if r['caught'] > 0:
            results.append(f"{stop:6d}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 1D. Spin-only (no rate gate) sweep
    results.append("\n--- ACC: Spin-only sweep (NO rate gate) ---")
    results.append(f"{'thresh':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for t in range(20, 260, 5):
        def make(thresh):
            def f(s):
                return s['sa_spins'] >= thresh
            return f
        r = ev.simulate_fast(make(t), acc_gaps)
        if r['caught'] > 0:
            results.append(f"{t:6d}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 1E. Rate-only (no spin threshold) sweep
    results.append("\n--- ACC: Rate-only sweep (NO spin threshold) ---")
    results.append(f"{'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for g100 in range(15, 46):
        gate = g100 / 100.0
        def make(g):
            def f(s):
                if s['sa_spins'] == 0: return False
                return (s['sa_acc'] / s['sa_spins']) >= g
            return f
        r = ev.simulate_fast(make(gate), acc_gaps)
        if r['caught'] > 0:
            results.append(f"{gate:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 1F. 2D sweep: threshold x gate (THE key parameter space)
    results.append("\n--- ACC: 2D sweep threshold x gate (top configs, sorted by lift) ---")
    results.append(f"{'thresh':>6s}  {'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    configs_2d = []
    for t in range(40, 220, 10):
        for g100 in range(20, 40):
            gate = g100 / 100.0
            def make(thresh, g):
                def f(s):
                    if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
                    return (s['sa_acc'] / s['sa_spins']) >= g
                return f
            r = ev.simulate_fast(make(t, gate), acc_gaps)
            if r['caught'] >= 5:  # min 5 catches to be reportable
                configs_2d.append((t, gate, r))
    configs_2d.sort(key=lambda x: -x[2]['lift'])
    for t, g, r in configs_2d[:60]:
        results.append(f"{t:6d}  {g:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 1G. 3D sweep: threshold x gate x stop (THE key parameter space)
    results.append("\n--- ACC: 3D sweep threshold x gate x stop (top configs) ---")
    results.append(f"{'thresh':>6s}  {'gate':>6s}  {'stop':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    configs_3d = []
    for t in range(60, 200, 10):
        for g100 in range(26, 38):
            gate = g100 / 100.0
            for stop in range(t + 20, min(t + 200, 400), 20):
                def make(thresh, g, st):
                    def f(s):
                        sp = s['sa_spins']
                        if sp < thresh or sp > st or sp == 0: return False
                        return (s['sa_acc'] / sp) >= g
                    return f
                r = ev.simulate_fast(make(t, gate, stop), acc_gaps)
                if r['caught'] >= 5:
                    configs_3d.append((t, gate, stop, r))
    configs_3d.sort(key=lambda x: -x[3]['lift'])
    for t, g, st, r in configs_3d[:60]:
        results.append(f"{t:6d}  {g:6.2f}  {st:6d}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # ========== SPN ==========
    spn_gaps = ev.all_gaps_for('spins')
    results.append(f"\n{'='*40} SPN ({len(spn_gaps)} gaps) {'='*40}")

    # 2A. Spin threshold sweep (ss_spins, gate=0.25 fixed)
    results.append("\n--- SPN: Spin Threshold sweep (ss_spn gate=0.25) ---")
    results.append(f"{'thresh':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for t in range(10, 220, 5):
        def make(thresh):
            def f(s):
                if s['ss_spins'] < thresh or s['ss_spins'] == 0: return False
                return (s['ss_spn'] / s['ss_spins']) >= 0.25
            return f
        r = ev.simulate_fast(make(t), spn_gaps)
        if r['caught'] > 0:
            results.append(f"{t:6d}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 2B. Rate gate sweep (ss_spins=87 fixed)
    results.append("\n--- SPN: Rate Gate sweep (ss_spins threshold=87) ---")
    results.append(f"{'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for g100 in range(15, 46):
        gate = g100 / 100.0
        def make(g):
            def f(s):
                if s['ss_spins'] < 87 or s['ss_spins'] == 0: return False
                return (s['ss_spn'] / s['ss_spins']) >= g
            return f
        r = ev.simulate_fast(make(gate), spn_gaps)
        if r['caught'] > 0:
            results.append(f"{gate:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 2C. SPN 2D sweep: ss_threshold x ss_gate
    results.append("\n--- SPN: 2D sweep ss_threshold x ss_gate (top configs) ---")
    results.append(f"{'thresh':>6s}  {'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    spn_2d = []
    for t in range(20, 200, 5):
        for g100 in range(18, 40):
            gate = g100 / 100.0
            def make(thresh, g):
                def f(s):
                    if s['ss_spins'] < thresh or s['ss_spins'] == 0: return False
                    return (s['ss_spn'] / s['ss_spins']) >= g
                return f
            r = ev.simulate_fast(make(t, gate), spn_gaps)
            if r['caught'] >= 5:
                spn_2d.append((t, gate, r))
    spn_2d.sort(key=lambda x: -x[2]['lift'])
    for t, g, r in spn_2d[:60]:
        results.append(f"{t:6d}  {g:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 2D. SPN 3D sweep: threshold x gate x stop
    results.append("\n--- SPN: 3D sweep threshold x gate x stop (top configs) ---")
    results.append(f"{'thresh':>6s}  {'gate':>6s}  {'stop':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    spn_3d = []
    for t in range(40, 180, 10):
        for g100 in range(20, 38):
            gate = g100 / 100.0
            for stop in range(t + 20, min(t + 200, 350), 20):
                def make(thresh, g, st):
                    def f(s):
                        sp = s['ss_spins']
                        if sp < thresh or sp > st or sp == 0: return False
                        return (s['ss_spn'] / sp) >= g
                    return f
                r = ev.simulate_fast(make(t, gate, stop), spn_gaps)
                if r['caught'] >= 5:
                    spn_3d.append((t, gate, stop, r))
    spn_3d.sort(key=lambda x: -x[3]['lift'])
    for t, g, st, r in spn_3d[:60]:
        results.append(f"{t:6d}  {g:6.2f}  {st:6d}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    # 2E. SPN using sa_* counters (old FINDINGS formula for comparison)
    results.append("\n--- SPN: Using sa_* counters (old FINDINGS formula) ---")
    results.append(f"{'thresh':>6s}  {'gate':>6s}  {'caught':>7s}  {'bet%':>7s}  {'mb/hit':>8s}  {'lift':>6s}")
    for t in range(40, 200, 10):
        for g100 in range(20, 36):
            gate = g100 / 100.0
            def make(thresh, g):
                def f(s):
                    if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
                    return (s['sa_spn'] / s['sa_spins']) >= g
                return f
            r = ev.simulate_fast(make(t, gate), spn_gaps)
            if r['caught'] >= 10:
                spn_2d.append((t, gate, r))
    # just show old formula baselines
    for (t, g) in [(87, 0.25), (87, 0.30), (60, 0.30)]:
        def make(thresh, gate):
            def f(s):
                if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
                return (s['sa_spn'] / s['sa_spins']) >= gate
            return f
        r = ev.simulate_fast(make(t, g), spn_gaps)
        results.append(f"{t:6d}  {g:6.2f}  {r['caught']:3d}/{r['total_gaps']:3d}  {r['bet_pct']*100:6.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:6.2f}x")

    out_path = os.path.join(os.path.dirname(__file__), '03_univariate_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print(f"Saved -> {out_path}")
    print(f"\nTotal lines: {len(results)}")

    # Print key findings summary
    print("\n--- KEY ACC FINDINGS ---")
    if configs_2d:
        best_lift = configs_2d[0]
        print(f"Best lift (2D): {best_lift[0]}/{best_lift[1]:.2f} -> {ev.fmt_result(best_lift[2])}")
    if configs_3d:
        best_3d = configs_3d[0]
        print(f"Best lift (3D): {best_3d[0]}/{best_3d[1]:.2f}/stop={best_3d[2]} -> {ev.fmt_result(best_3d[3])}")

    print("\n--- KEY SPN FINDINGS ---")
    if spn_2d:
        best_spn2 = sorted([x for x in spn_2d if len(x) == 3], key=lambda x: -x[2]['lift'])
        if best_spn2:
            b = best_spn2[0]
            print(f"Best lift (2D): {b[0]}/{b[1]:.2f} -> {ev.fmt_result(b[2])}")
    if spn_3d:
        best_spn3 = spn_3d[0]
        print(f"Best lift (3D): {best_spn3[0]}/{best_spn3[1]:.2f}/stop={best_spn3[2]} -> {ev.fmt_result(best_spn3[3])}")


if __name__ == '__main__':
    run()
