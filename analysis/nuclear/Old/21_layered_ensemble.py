"""
Chunk 21: LAYERED ensemble — Stage 1 predicts window from prev gap class,
Stage 2 fires specialized rules inside that window.

User hypothesis: instead of one big rule set, split into two stages.
Stage 1: Use prev_gap classification to predict the likely target window (S/M/L).
Stage 2: Only evaluate rules appropriate for the predicted window.

Benefits:
  - S-window (40-105): use quiet-zone suppression + STEAL/SHIELD tail rules
  - M-window (106-160): use rate-gate and slope rules
  - L-window (161+): use high-threshold precision rules
  - Avoids wasting bets on spin 130+ when we expect a short gap
  - Avoids wasting early bets when we expect a long gap

The bet for spin N+1 fires only if:
  - Stage 1 says 'next gap is in window W'
  - Stage 2 says 'a W-window rule is firing at current state'
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('e10', os.path.join(os.path.dirname(__file__), '10_ensemble.py'))
e10 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e10)

from collections import defaultdict


def classify(L):
    if L < 40: return 'XS'
    if L <= 105: return 'S'
    if L <= 160: return 'M'
    return 'L'


def run():
    gaps = e10.all_gaps_with_prev()
    total = len(gaps)

    # Inject prev_class and suppression features onto each gap/spin
    by_acct = defaultdict(list)
    for gi, g in enumerate(gaps):
        by_acct[g['account']].append((gi, g))

    for acct, gap_list in by_acct.items():
        prev_class = None
        for gi, gap in gap_list:
            gap['_prev_class'] = prev_class
            traj = gap['trajectory']
            for i, spin in enumerate(traj):
                spin['_traj_ref'] = traj
                spin['_traj_idx'] = i
                spin['_prev_class'] = prev_class
                spin['_prev_triple_type'] = gap.get('prev_real_triple')
                # Suppression features
                for N in [5, 8, 10, 12, 15]:
                    if i >= N:
                        start = traj[i - N]
                        spin[f'_symbols_last_{N}'] = (
                            (spin['sa_acc']-start['sa_acc']) +
                            (spin['sa_spn']-start['sa_spn']) +
                            (spin['sa_shd']-start['sa_shd']) +
                            (spin['sa_atk']-start['sa_atk']) +
                            (spin['sa_stl']-start['sa_stl'])
                        )
                        spin[f'_atk_last_{N}'] = spin['sa_atk'] - start['sa_atk']
                    else:
                        spin[f'_symbols_last_{N}'] = -1
                        spin[f'_atk_last_{N}'] = -1
            prev_class = classify(gap['length'])

    # ============================================================
    # STAGE 1 RULES — predict window from prev_class
    # ============================================================
    # Based on the transition matrix:
    #   M  → S: 50%    L  → S: 55%    (predict S)
    #   S  → M: 45%                    (predict M)
    #   XS → M/L: 51%                  (predict M or L — weaker)

    # ============================================================
    # STAGE 2 RULES per window
    # ============================================================

    # --- S window (40-105) — quiet-zone + conditionals ---
    S_RULES = [
        # Quiet-zone suppression
        ('SUPP_10<=10 t65', lambda spin, p: (
            spin['sa_spins'] >= 65 and spin['sa_spins'] <= 105 and
            0 <= spin.get('_symbols_last_10', -1) <= 10
        )),
        ('SUPP_10<=12 t65', lambda spin, p: (
            spin['sa_spins'] >= 65 and spin['sa_spins'] <= 105 and
            0 <= spin.get('_symbols_last_10', -1) <= 12
        )),
        # STEAL in S window
        ('STEAL t65 g0.34', lambda spin, p: (
            spin.get('_prev_triple_type') == 'steal' and
            65 <= spin['sa_spins'] <= 105 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.34
        )),
        ('STEAL t65 g0.32', lambda spin, p: (
            spin.get('_prev_triple_type') == 'steal' and
            65 <= spin['sa_spins'] <= 105 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.32
        )),
        # SHIELD in S window (looser)
        ('SHIELD t80 g0.34', lambda spin, p: (
            spin.get('_prev_triple_type') == 'shield' and
            80 <= spin['sa_spins'] <= 105 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.34
        )),
        # Acc-only high gate
        ('HIGH_ACC t80 g0.38', lambda spin, p: (
            80 <= spin['sa_spins'] <= 105 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.38
        )),
    ]

    # --- M window (106-160) — rate-gate rules ---
    M_RULES = [
        ('STEAL t110 g0.30', lambda spin, p: (
            spin.get('_prev_triple_type') == 'steal' and
            110 <= spin['sa_spins'] <= 160 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.30
        )),
        ('STEAL t130 g0.28', lambda spin, p: (
            spin.get('_prev_triple_type') == 'steal' and
            130 <= spin['sa_spins'] <= 160 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.28
        )),
        ('SHIELD t130 g0.22', lambda spin, p: (
            spin.get('_prev_triple_type') == 'shield' and
            130 <= spin['sa_spins'] <= 160 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.22
        )),
        ('DG t130 acc0.28 spn0.24', lambda spin, p: (
            130 <= spin['sa_spins'] <= 160 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.28 and
            (spin['sa_spn']/spin['sa_spins']) >= 0.24
        )),
        ('SUPP_10<=10 t130', lambda spin, p: (
            130 <= spin['sa_spins'] <= 160 and
            0 <= spin.get('_symbols_last_10', -1) <= 10
        )),
    ]

    # --- L window (161+) — high-threshold precision ---
    L_RULES = [
        ('SHIELD t150 g0.30', lambda spin, p: (
            spin.get('_prev_triple_type') == 'shield' and
            spin['sa_spins'] >= 150 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.30
        )),
        ('STEAL t150 g0.30', lambda spin, p: (
            spin.get('_prev_triple_type') == 'steal' and
            spin['sa_spins'] >= 150 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.30
        )),
        ('FLAT 180 g0.24', lambda spin, p: (
            spin['sa_spins'] >= 180 and
            spin['sa_spins'] > 0 and
            (spin['sa_acc']/spin['sa_spins']) >= 0.24
        )),
    ]

    # ============================================================
    # Stage 1: predict window from prev_class
    # ============================================================
    # Based on the transition probabilities, define the predicted window(s):
    WINDOW_FROM_PREV = {
        'M':  ['S'],         # 50% S, 30% M, 16% XS, 4% L → bet S window
        'L':  ['S'],         # 55% S, 15% M, 18% XS, 12% L → bet S window
        'S':  ['M'],         # 45% M, 31% S, 19% L, 6% XS → bet M window
        'XS': ['M', 'L'],    # 33% M, 30% S, 18% XS, 18% L → bet M and L (lower certainty)
        None: ['S', 'M', 'L'],  # unknown, bet all
    }

    # ============================================================
    # Run layered simulation
    # ============================================================
    def eval_layered(rules_per_window, window_pred):
        caught = set()
        bets = 0
        per_acct = defaultdict(lambda: [0, 0, 0])  # [caught, bets, total]
        for gi, gap in enumerate(gaps):
            per_acct[gap['account']][2] += 1
            prev_c = gap.get('_prev_class')
            allowed_windows = window_pred.get(prev_c, ['S','M','L'])
            traj = gap['trajectory']
            L = len(traj)
            if L < 2: continue
            gap_caught = False
            for i in range(L - 1):
                spin = traj[i]
                # Gather active rules from all allowed windows
                fired = False
                for w in allowed_windows:
                    for name, rule in rules_per_window[w]:
                        if rule(spin, None):
                            fired = True; break
                    if fired: break
                if fired:
                    bets += 1
                    per_acct[gap['account']][1] += 1
                    if i + 1 == L - 1:
                        gap_caught = True
            if gap_caught:
                caught.add(gi)
                per_acct[gap['account']][0] += 1
        mb = bets / len(caught) if caught else float('inf')
        return len(caught), bets, mb, per_acct

    rules_per_window = {'S': S_RULES, 'M': M_RULES, 'L': L_RULES}

    lines = []
    lines.append("=" * 100)
    lines.append("CHUNK 21: LAYERED ENSEMBLE")
    lines.append("=" * 100)
    lines.append("")
    lines.append("Stage 1: predict window (S/M/L) from prev gap class")
    lines.append("Stage 2: fire specialized rules inside predicted window only")
    lines.append("")
    lines.append("Window rules:")
    lines.append(f"  S window ({len(S_RULES)} rules): quiet-zone suppression + STEAL/SHIELD tail")
    lines.append(f"  M window ({len(M_RULES)} rules): rate-gate + DG + SHIELD/STEAL")
    lines.append(f"  L window ({len(L_RULES)} rules): high-threshold precision")
    lines.append("")
    lines.append("Stage 1 mapping (prev -> predicted window):")
    for k, v in WINDOW_FROM_PREV.items():
        lines.append(f"  {str(k):>4s} -> {v}")
    lines.append("")

    # Full layered run
    c, b, mb, pa = eval_layered(rules_per_window, WINDOW_FROM_PREV)
    lines.append(f"LAYERED FULL RESULT:")
    lines.append(f"  catches: {c}/{total} ({100*c/total:.1f}%)")
    lines.append(f"  bets:    {b}")
    lines.append(f"  mb/hit:  {mb:.1f}")
    lines.append(f"  Per-account:")
    for acct in ['Islam','Ahmed','Nick']:
        ct, bt, tot = pa[acct]
        acct_mb = bt/ct if ct else float('inf')
        lines.append(f"    {acct}: {ct}/{tot} ({100*ct/tot:.1f}%) @ {acct_mb:.1f} mb")

    lines.append("")
    lines.append("=" * 100)
    lines.append("ALTERNATIVE 1: Bet all windows (no stage 1 filter)")
    lines.append("=" * 100)
    wp_all = {k: ['S','M','L'] for k in [None,'XS','S','M','L']}
    c, b, mb, pa = eval_layered(rules_per_window, wp_all)
    lines.append(f"  catches: {c}/{total} @ {mb:.1f} mb/hit")
    for acct in ['Islam','Ahmed','Nick']:
        ct, bt, tot = pa[acct]
        acct_mb = bt/ct if ct else float('inf')
        lines.append(f"    {acct}: {ct}/{tot} @ {acct_mb:.1f} mb")

    lines.append("")
    lines.append("=" * 100)
    lines.append("ALTERNATIVE 2: Strict layered (only ONE predicted window, not multi)")
    lines.append("=" * 100)
    wp_strict = {
        'M':  ['S'],
        'L':  ['S'],
        'S':  ['M'],
        'XS': ['M'],
        None: ['S'],
    }
    c, b, mb, pa = eval_layered(rules_per_window, wp_strict)
    lines.append(f"  catches: {c}/{total} @ {mb:.1f} mb/hit")
    for acct in ['Islam','Ahmed','Nick']:
        ct, bt, tot = pa[acct]
        acct_mb = bt/ct if ct else float('inf')
        lines.append(f"    {acct}: {ct}/{tot} @ {acct_mb:.1f} mb")

    lines.append("")
    lines.append("=" * 100)
    lines.append("ALTERNATIVE 3: 'hedge' — predict S window AND M window (broader)")
    lines.append("=" * 100)
    wp_hedge = {
        'M':  ['S','M'],
        'L':  ['S','M'],
        'S':  ['M','L'],
        'XS': ['S','M','L'],
        None: ['S','M','L'],
    }
    c, b, mb, pa = eval_layered(rules_per_window, wp_hedge)
    lines.append(f"  catches: {c}/{total} @ {mb:.1f} mb/hit")
    for acct in ['Islam','Ahmed','Nick']:
        ct, bt, tot = pa[acct]
        acct_mb = bt/ct if ct else float('inf')
        lines.append(f"    {acct}: {ct}/{tot} @ {acct_mb:.1f} mb")

    # Per-rule contribution in the S window
    lines.append("")
    lines.append("=" * 100)
    lines.append("S-WINDOW RULES: solo performance")
    lines.append("=" * 100)
    for name, rule in S_RULES:
        caught = 0
        bets = 0
        for gap in gaps:
            traj = gap['trajectory']
            L = len(traj)
            if L < 2: continue
            for i in range(L - 1):
                if rule(traj[i], None):
                    bets += 1
                    if i + 1 == L - 1:
                        caught += 1
        mb = bets/caught if caught else float('inf')
        lines.append(f"  {name:<35s}: {caught}/{total} @ {mb:.1f} mb")

    lines.append("")
    lines.append("=" * 100)
    lines.append("M-WINDOW RULES: solo performance")
    lines.append("=" * 100)
    for name, rule in M_RULES:
        caught = 0
        bets = 0
        for gap in gaps:
            traj = gap['trajectory']
            L = len(traj)
            if L < 2: continue
            for i in range(L - 1):
                if rule(traj[i], None):
                    bets += 1
                    if i + 1 == L - 1:
                        caught += 1
        mb = bets/caught if caught else float('inf')
        lines.append(f"  {name:<35s}: {caught}/{total} @ {mb:.1f} mb")

    lines.append("")
    lines.append("=" * 100)
    lines.append("L-WINDOW RULES: solo performance")
    lines.append("=" * 100)
    for name, rule in L_RULES:
        caught = 0
        bets = 0
        for gap in gaps:
            traj = gap['trajectory']
            L = len(traj)
            if L < 2: continue
            for i in range(L - 1):
                if rule(traj[i], None):
                    bets += 1
                    if i + 1 == L - 1:
                        caught += 1
        mb = bets/caught if caught else float('inf')
        lines.append(f"  {name:<35s}: {caught}/{total} @ {mb:.1f} mb")

    out_path = os.path.join(os.path.dirname(__file__), '21_layered_ensemble.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Saved -> {out_path}")
    print(f"\nLayered result: {eval_layered(rules_per_window, WINDOW_FROM_PREV)[0]}/{total} @ {eval_layered(rules_per_window, WINDOW_FROM_PREV)[2]:.1f} mb")


if __name__ == '__main__':
    run()
