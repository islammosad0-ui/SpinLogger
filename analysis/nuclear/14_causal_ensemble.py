"""
Chunk 14: Build the new causal ACC ensemble.

Strategy:
  1. Run a causal SML sweep (gap-context conditioning) to find any rules that
     beat the flat 130/0.31 baseline.
  2. Take the top causal flat candidates from chunk 13 + the best causal SML
     candidates and build the union.
  3. Run greedy minimum cover under causal eval to pick the smallest subset
     that captures the union catches.
  4. Print a clean rule list ready to drop into SLDebtTracker.

All evaluation is causal (strategy fired on traj[i-1], no triple-spin self-bump).
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


def all_gaps_with_prev():
    with open(GAPS_PATH, 'rb') as f:
        data = pickle.load(f)
    out = []
    for acct in ACCOUNTS:
        raw = data[acct]['gaps'].get('accumulation', [])
        for i, g in enumerate(raw):
            g2 = dict(g)
            g2['prev_gap_length'] = raw[i-1]['length'] if i > 0 else None
            g2['account'] = acct
            out.append(g2)
    return out


# ============================================================
#  Rule factories
# ============================================================
def flat_fn(thresh, gate, stop=None):
    def f(s, prev):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if stop is not None and sp > stop: return False
        return (s['sa_acc'] / sp) >= gate
    return f


def sml_fn(s_bound, l_bound, t_s, t_m, t_l, gate):
    """SML override: bucket by prev_gap_length."""
    def f(s, prev):
        if prev is None: return None
        if prev < s_bound:   thresh = t_s
        elif prev < l_bound: thresh = t_m
        else:                thresh = t_l
        if thresh is None: return False
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        return (s['sa_acc'] / sp) >= gate
    return f


def shield_cond_fn(thresh, gate, required='shield'):
    def f(s, prev):
        if s.get('_prev_triple_type') != required: return False
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        return (s['sa_acc'] / sp) >= gate
    return f


def double_gate_fn(thresh, min_acc, min_spn):
    def f(s, prev):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if (s['sa_acc'] / sp) < min_acc: return False
        if (s['sa_spn'] / sp) < min_spn: return False
        return True
    return f


# ============================================================
#  Simulator (causal)
# ============================================================
def simulate_causal(fn, gaps):
    caught_set = set()
    bet_spins = 0
    total_spins = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        total_spins += len(traj)
        for i in range(1, len(traj)):
            prev_spin = traj[i - 1]
            prev_spin['_traj_ref'] = traj
            prev_spin['_traj_idx'] = i - 1
            prev_spin['_prev_triple_type'] = gap.get('prev_real_triple')
            decision = fn(prev_spin, prev)
            if decision is None:
                continue
            if decision:
                bet_spins += 1
                if i == len(traj) - 1:
                    caught_set.add(gap_idx)
    return caught_set, bet_spins, total_spins


def metrics(caught_set, bet_spins, total_spins, n_gaps):
    n = len(caught_set)
    if not bet_spins:
        return f"{n}/{n_gaps}  bet=0  mb=inf  lift=0"
    bet_pct = 100 * bet_spins / total_spins
    mb = bet_spins / n if n else float('inf')
    bhr = n / bet_spins
    br = n_gaps / total_spins
    lift = bhr / br if br else 0
    return f"{n:3d}/{n_gaps}  bet={bet_pct:4.2f}%  mb/hit={mb:5.1f}  lift={lift:4.2f}x"


def run():
    gaps = all_gaps_with_prev()
    n_gaps = len(gaps)

    out = []
    out.append("=" * 100)
    out.append("CHUNK 14: NEW CAUSAL ACC ENSEMBLE")
    out.append("=" * 100)
    out.append(f"Total gaps: {n_gaps}")
    out.append("")

    # ============================================================
    # Step 1: Causal SML sweep — find good gap-context rules
    # ============================================================
    out.append("=" * 60)
    out.append("STEP 1: Causal SML sweep")
    out.append("=" * 60)
    out.append("Sweeping (s_bound, l_bound, t_l, gate) — L-bucket only (most signal),")
    out.append("with t_s/t_m = SKIP (None). Then a small full-SML grid.")
    out.append("")

    out.append("--- L-only SML: prev >= L_bound, threshold = t_l, gate = g ---")
    out.append(f"{'L_bound':>8s}  {'t_l':>4s}  {'gate':>5s}  catches")
    sml_l_results = []
    for L in range(80, 220, 10):
        for t_l in range(80, 200, 10):
            for g100 in range(25, 38):
                gate = g100 / 100.0
                fn = sml_fn(0, L, None, None, t_l, gate)
                cs, bs, ts = simulate_causal(fn, gaps)
                if len(cs) >= 4:
                    sml_l_results.append((L, t_l, gate, cs, bs, ts))
    # rank by lift then catches
    def lift_of(r):
        cs, bs, ts = r[3], r[4], r[5]
        if not bs: return 0
        return (len(cs)/bs) / (n_gaps/ts) if ts else 0
    sml_l_results.sort(key=lambda r: (-lift_of(r), -len(r[3])))
    for L, t_l, g, cs, bs, ts in sml_l_results[:25]:
        out.append(f"  L>={L:3d}  t_l={t_l:3d}  g={g:.2f}  {metrics(cs, bs, ts, n_gaps)}")

    out.append("")
    out.append("--- Full SML grid (S/M/L thresholds, gate=0.30..0.32) ---")
    sml_full_results = []
    for s_b in [50, 80, 100]:
        for l_b in [110, 120, 130, 150]:
            if l_b <= s_b: continue
            for t_s in [None, 60, 80, 100]:
                for t_m in [None, 110, 130, 150]:
                    for t_l in [80, 100, 130, 150]:
                        for g100 in [29, 30, 31, 32]:
                            gate = g100 / 100.0
                            fn = sml_fn(s_b, l_b, t_s, t_m, t_l, gate)
                            cs, bs, ts = simulate_causal(fn, gaps)
                            if len(cs) >= 5:
                                sml_full_results.append((s_b, l_b, t_s, t_m, t_l, gate, cs, bs, ts))
    def lift_full(r):
        cs, bs, ts = r[6], r[7], r[8]
        if not bs: return 0
        return (len(cs)/bs) / (n_gaps/ts) if ts else 0
    sml_full_results.sort(key=lambda r: (-lift_full(r), -len(r[6])))
    out.append(f"{'s':>3s} {'l':>3s} {'tS':>4s} {'tM':>4s} {'tL':>4s} {'gate':>5s}  metrics")
    for s_b, l_b, t_s, t_m, t_l, g, cs, bs, ts in sml_full_results[:20]:
        ts_str = str(t_s) if t_s else 'SK'
        tm_str = str(t_m) if t_m else 'SK'
        out.append(f"{s_b:>3d} {l_b:>3d} {ts_str:>4s} {tm_str:>4s} {t_l:>4d} {g:.2f}   {metrics(cs, bs, ts, n_gaps)}")

    # ============================================================
    # Step 2: Causal SHIELD-cond sweep
    # ============================================================
    out.append("")
    out.append("=" * 60)
    out.append("STEP 2: Causal SHIELD/triple-cond sweep")
    out.append("=" * 60)
    cond_results = []
    for triple in ['shield', 'attack', 'steal', 'spins']:
        for t in range(80, 200, 10):
            for g100 in range(28, 36):
                gate = g100 / 100.0
                fn = shield_cond_fn(t, gate, triple)
                cs, bs, ts = simulate_causal(fn, gaps)
                if len(cs) >= 3:
                    cond_results.append((triple, t, gate, cs, bs, ts))
    def lift_cond(r):
        cs, bs, ts = r[3], r[4], r[5]
        if not bs: return 0
        return (len(cs)/bs) / (n_gaps/ts) if ts else 0
    cond_results.sort(key=lambda r: (-lift_cond(r), -len(r[3])))
    out.append(f"{'triple':>8s}  {'thresh':>6s}  {'gate':>5s}  metrics")
    for tr, t, g, cs, bs, ts in cond_results[:25]:
        out.append(f"{tr:>8s}  {t:>6d}  {g:.2f}   {metrics(cs, bs, ts, n_gaps)}")

    # ============================================================
    # Step 3: Build candidate set from top results
    # ============================================================
    out.append("")
    out.append("=" * 60)
    out.append("STEP 3: Build candidate ensemble")
    out.append("=" * 60)

    # Top causal flat rules from chunk 13 + diversity picks
    candidates = [
        ("FLAT 130/0.31 stop=160", flat_fn(130, 0.31, 160)),
        ("FLAT 130/0.31",          flat_fn(130, 0.31)),
        ("FLAT 130/0.30",          flat_fn(130, 0.30)),
        ("FLAT 130/0.28",          flat_fn(130, 0.28)),
        ("FLAT 115/0.34",          flat_fn(115, 0.34)),
        ("FLAT 110/0.34",          flat_fn(110, 0.34)),
        ("FLAT 150/0.28",          flat_fn(150, 0.28)),
        ("FLAT 100/0.35",          flat_fn(100, 0.35)),
    ]

    # Add top SML rules
    for L, t_l, g, cs, bs, ts in sml_l_results[:8]:
        name = f"SML L>={L} t_l={t_l} g={g:.2f}"
        candidates.append((name, sml_fn(0, L, None, None, t_l, g)))
    for s_b, l_b, t_s, t_m, t_l, g, cs, bs, ts in sml_full_results[:8]:
        ts_str = str(t_s) if t_s else 'SK'
        tm_str = str(t_m) if t_m else 'SK'
        name = f"SML s={s_b} l={l_b} tS={ts_str} tM={tm_str} tL={t_l} g={g:.2f}"
        candidates.append((name, sml_fn(s_b, l_b, t_s, t_m, t_l, g)))

    # Add top conditional rules
    for tr, t, g, cs, bs, ts in cond_results[:5]:
        name = f"COND {tr} t={t} g={g:.2f}"
        candidates.append((name, shield_cond_fn(t, g, tr)))

    out.append(f"Total candidate rules: {len(candidates)}")

    # Score each candidate causally
    cand_data = {}
    out.append("")
    out.append(f"{'rule':>50s}  metrics")
    out.append("-" * 90)
    for name, fn in candidates:
        cs, bs, ts = simulate_causal(fn, gaps)
        cand_data[name] = (cs, bs, ts)
        out.append(f"{name[:50]:>50s}  {metrics(cs, bs, ts, n_gaps)}")

    # ============================================================
    # Step 4: True union of all candidates
    # ============================================================
    out.append("")
    out.append("=" * 60)
    out.append("STEP 4: True union of all candidates (causal)")
    out.append("=" * 60)

    union_caught = set()
    union_bets = 0
    union_total = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        union_total += len(traj)
        for i in range(1, len(traj)):
            prev_spin = traj[i - 1]
            prev_spin['_traj_ref'] = traj
            prev_spin['_traj_idx'] = i - 1
            prev_spin['_prev_triple_type'] = gap.get('prev_real_triple')
            any_bet = False
            for name, fn in candidates:
                d = fn(prev_spin, prev)
                if d:
                    any_bet = True
                    break
            if any_bet:
                union_bets += 1
                if i == len(traj) - 1:
                    union_caught.add(gap_idx)
    out.append(f"True union catches: {metrics(union_caught, union_bets, union_total, n_gaps)}")

    # ============================================================
    # Step 5: Greedy minimum cover
    # ============================================================
    out.append("")
    out.append("=" * 60)
    out.append("STEP 5: Greedy minimum cover (causal)")
    out.append("=" * 60)
    target = set(union_caught)
    remaining = set(target)
    chosen = []
    available = list(candidates)
    while remaining:
        best_score = None
        best_idx = -1
        for idx, (name, fn) in enumerate(available):
            cs, bs, _ = cand_data[name]
            new = cs & remaining
            if not new:
                continue
            score = bs / len(new)  # bet spins per new catch
            if best_score is None or score < best_score:
                best_score = score
                best_idx = idx
        if best_idx < 0:
            break
        name, fn = available.pop(best_idx)
        cs, bs, _ = cand_data[name]
        new = cs & remaining
        chosen.append((name, len(new), bs))
        remaining -= cs

    out.append(f"Greedy chosen ({len(chosen)} rules):")
    for name, n_new, bs in chosen:
        out.append(f"  + {name}  (+{n_new} new, {bs} bet spins alone)")

    # True simulation of the chosen subset
    chosen_fns = [fn for name, fn in candidates if name in [c[0] for c in chosen]]
    sub_caught = set()
    sub_bets = 0
    sub_total = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        sub_total += len(traj)
        for i in range(1, len(traj)):
            prev_spin = traj[i - 1]
            prev_spin['_traj_ref'] = traj
            prev_spin['_traj_idx'] = i - 1
            prev_spin['_prev_triple_type'] = gap.get('prev_real_triple')
            for fn in chosen_fns:
                d = fn(prev_spin, prev)
                if d:
                    sub_bets += 1
                    if i == len(traj) - 1:
                        sub_caught.add(gap_idx)
                    break
    out.append("")
    out.append(f"True greedy subset simulation: {metrics(sub_caught, sub_bets, sub_total, n_gaps)}")

    out_path = Path(__file__).parent / '14_causal_ensemble_results.txt'
    out_path.write_text('\n'.join(out), encoding='utf-8')
    print(f"Saved -> {out_path}")
    print()
    print(f"True union (all candidates): {metrics(union_caught, union_bets, union_total, n_gaps)}")
    print(f"Greedy subset ({len(chosen)} rules): {metrics(sub_caught, sub_bets, sub_total, n_gaps)}")
    print()
    print("Greedy subset:")
    for name, n_new, bs in chosen:
        print(f"  + {name}  (+{n_new})")


if __name__ == '__main__':
    run()
