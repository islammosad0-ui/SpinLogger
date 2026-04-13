"""
Chunk 13: Causal univariate + 2D sweeps for ACC and SPN.

Re-runs the chunk 03 univariate sweep under causal evaluation to find new
optimal threshold/gate combinations. The non-causal sweep was tuned against
post-triple counter spikes, so its sweet spots no longer apply.

Sweeps performed (all causal):
  - ACC threshold x gate (2D)
  - ACC threshold x gate x stop (3D)
  - SPN threshold x gate (2D, ss_* counters)
  - SPN threshold x gate (2D, sa_* counters — old FINDINGS formula)

We report top 30 by lift for each sweep, filtered to caught >= 5 so we
don't end up with 1-catch flukes.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('ev', os.path.join(os.path.dirname(__file__), '02_eval.py'))
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)


def fmt(r):
    return f"caught={r['caught']:3d}/{r['total_gaps']:3d}  bet={r['bet_pct']*100:5.2f}%  mb/hit={r['mb_per_hit']:6.1f}  lift={r['lift']:5.2f}x"


def run():
    out = []
    out.append("=" * 90)
    out.append("CHUNK 13: CAUSAL SWEEPS")
    out.append("=" * 90)
    out.append("All metrics computed with simulate_fast_causal — strategy is evaluated on")
    out.append("the spin record from the PREVIOUS spin (the user's actual decision context).")
    out.append("")

    # ============================================================
    #  ACC
    # ============================================================
    acc_gaps = ev.all_gaps_for('accumulation')
    out.append(f"{'='*30} ACC ({len(acc_gaps)} gaps) {'='*30}")

    # ACC: 2D sweep threshold x gate
    out.append("")
    out.append("--- ACC 2D sweep: threshold x gate (sa_acc/sa_spins) ---")
    out.append(f"{'thresh':>6s}  {'gate':>6s}  {'caught':>9s}  {'bet%':>6s}  {'mb/hit':>8s}  {'lift':>6s}")
    acc_2d = []
    for t in range(40, 220, 5):
        for g100 in range(15, 40):
            gate = g100 / 100.0
            def make(thresh, g):
                def f(s):
                    if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
                    return (s['sa_acc'] / s['sa_spins']) >= g
                return f
            r = ev.simulate_fast_causal(make(t, gate), acc_gaps)
            if r['caught'] >= 5:
                acc_2d.append((t, gate, r))
    acc_2d.sort(key=lambda x: -x[2]['lift'])
    for t, g, r in acc_2d[:40]:
        out.append(f"{t:6d}  {g:6.2f}  {r['caught']:4d}/{r['total_gaps']:3d}  {r['bet_pct']*100:5.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:5.2f}x")

    # ACC: spin-only sweep (NO rate gate)
    out.append("")
    out.append("--- ACC spin-only sweep (no rate gate) ---")
    out.append(f"{'thresh':>6s}  {'caught':>9s}  {'bet%':>6s}  {'mb/hit':>8s}  {'lift':>6s}")
    for t in range(40, 260, 10):
        def make(thresh):
            def f(s):
                return s['sa_spins'] >= thresh
            return f
        r = ev.simulate_fast_causal(make(t), acc_gaps)
        if r['caught'] >= 5:
            out.append(f"{t:6d}  {r['caught']:4d}/{r['total_gaps']:3d}  {r['bet_pct']*100:5.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:5.2f}x")

    # ACC: 3D sweep threshold x gate x stop
    out.append("")
    out.append("--- ACC 3D sweep: threshold x gate x stop ---")
    out.append(f"{'thresh':>6s}  {'gate':>6s}  {'stop':>6s}  {'caught':>9s}  {'bet%':>6s}  {'mb/hit':>8s}  {'lift':>6s}")
    acc_3d = []
    for t in range(60, 200, 10):
        for g100 in range(20, 36):
            gate = g100 / 100.0
            for stop in range(t + 30, min(t + 250, 400), 20):
                def make(thresh, g, st):
                    def f(s):
                        sp = s['sa_spins']
                        if sp < thresh or sp > st or sp == 0: return False
                        return (s['sa_acc'] / sp) >= g
                    return f
                r = ev.simulate_fast_causal(make(t, gate, stop), acc_gaps)
                if r['caught'] >= 5:
                    acc_3d.append((t, gate, stop, r))
    acc_3d.sort(key=lambda x: -x[3]['lift'])
    for t, g, st, r in acc_3d[:40]:
        out.append(f"{t:6d}  {g:6.2f}  {st:6d}  {r['caught']:4d}/{r['total_gaps']:3d}  {r['bet_pct']*100:5.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:5.2f}x")

    # ============================================================
    #  SPN
    # ============================================================
    spn_gaps = ev.all_gaps_for('spins')
    out.append("")
    out.append(f"{'='*30} SPN ({len(spn_gaps)} gaps) {'='*30}")

    # SPN 2D sweep with ss_* counters
    out.append("")
    out.append("--- SPN 2D sweep: ss_threshold x ss_gate (ss_spn/ss_spins) ---")
    out.append(f"{'thresh':>6s}  {'gate':>6s}  {'caught':>9s}  {'bet%':>6s}  {'mb/hit':>8s}  {'lift':>6s}")
    spn_ss = []
    for t in range(20, 200, 5):
        for g100 in range(15, 40):
            gate = g100 / 100.0
            def make(thresh, g):
                def f(s):
                    if s['ss_spins'] < thresh or s['ss_spins'] == 0: return False
                    return (s['ss_spn'] / s['ss_spins']) >= g
                return f
            r = ev.simulate_fast_causal(make(t, gate), spn_gaps)
            if r['caught'] >= 5:
                spn_ss.append((t, gate, r))
    spn_ss.sort(key=lambda x: -x[2]['lift'])
    for t, g, r in spn_ss[:40]:
        out.append(f"{t:6d}  {g:6.2f}  {r['caught']:4d}/{r['total_gaps']:3d}  {r['bet_pct']*100:5.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:5.2f}x")

    # SPN 2D sweep with sa_* counters (old FINDINGS formula)
    out.append("")
    out.append("--- SPN 2D sweep: sa_threshold x sa_gate (old formula sa_spn/sa_spins) ---")
    out.append(f"{'thresh':>6s}  {'gate':>6s}  {'caught':>9s}  {'bet%':>6s}  {'mb/hit':>8s}  {'lift':>6s}")
    spn_sa = []
    for t in range(20, 200, 5):
        for g100 in range(15, 40):
            gate = g100 / 100.0
            def make(thresh, g):
                def f(s):
                    if s['sa_spins'] < thresh or s['sa_spins'] == 0: return False
                    return (s['sa_spn'] / s['sa_spins']) >= g
                return f
            r = ev.simulate_fast_causal(make(t, gate), spn_gaps)
            if r['caught'] >= 5:
                spn_sa.append((t, gate, r))
    spn_sa.sort(key=lambda x: -x[2]['lift'])
    for t, g, r in spn_sa[:40]:
        out.append(f"{t:6d}  {g:6.2f}  {r['caught']:4d}/{r['total_gaps']:3d}  {r['bet_pct']*100:5.2f}%  {r['mb_per_hit']:8.1f}  {r['lift']:5.2f}x")

    out_path = os.path.join(os.path.dirname(__file__), '13_causal_sweep_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f"Saved -> {out_path}")
    print()
    if acc_2d:
        print(f"ACC 2D top: {acc_2d[0][0]}/{acc_2d[0][1]:.2f} -> {fmt(acc_2d[0][2])}")
    if acc_3d:
        print(f"ACC 3D top: {acc_3d[0][0]}/{acc_3d[0][1]:.2f}/stop={acc_3d[0][2]} -> {fmt(acc_3d[0][3])}")
    if spn_ss:
        print(f"SPN ss top: {spn_ss[0][0]}/{spn_ss[0][1]:.2f} -> {fmt(spn_ss[0][2])}")
    if spn_sa:
        print(f"SPN sa top: {spn_sa[0][0]}/{spn_sa[0][1]:.2f} -> {fmt(spn_sa[0][2])}")


if __name__ == '__main__':
    run()
