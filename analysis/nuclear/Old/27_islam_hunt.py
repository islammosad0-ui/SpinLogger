"""
Chunk 27: Islam-specific causal hunt.

Goal: find the best ensemble for ISLAM ALONE — not the cross-account one.
Islam's profile is known to differ from Ahmed/Nick (per-account variance is
large, see project memory + chunk 17). The shipped v5 7-rule was tuned to
generalize across all 3 accounts; this script asks "what does Islam himself
respond to?" and produces a per-Islam ensemble + greedy minimum cover.

Reuses 02_eval.simulate_causal semantics (rule fires at i predicts spin i+1).
"""
import os, sys, pickle
sys.path.insert(0, os.path.dirname(__file__))

GAPS_PATH = os.path.join(os.path.dirname(__file__), 'gaps.pkl')


def load_islam_gaps():
    with open(GAPS_PATH, 'rb') as f:
        data = pickle.load(f)
    raw = data['Islam']['gaps'].get('accumulation', [])
    out = []
    for i, g in enumerate(raw):
        g2 = dict(g)
        g2['prev_gap_length'] = raw[i-1]['length'] if i > 0 else None
        out.append(g2)
    return out


def classify(length):
    if length is None or length <= 0: return None
    if length <= 39:  return 'XS'
    if length <= 105: return 'S'
    if length <= 160: return 'M'
    return 'L'


# === Rule factories (causal — fn(spin_state, prev_gap_length) -> bool) ===

def flat(thresh, gate, cap=None):
    def f(s, prev):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if cap is not None and sp > cap: return False
        return (s['sa_acc']/sp) >= gate
    return f

def cond(prev_triple, thresh, gate, cap=None):
    def f(s, prev):
        if s.get('_prev_triple_type') != prev_triple: return False
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if cap is not None and sp > cap: return False
        return (s['sa_acc']/sp) >= gate
    return f

def double_gate(thresh, min_acc, min_spn, cap=None):
    def f(s, prev):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if cap is not None and sp > cap: return False
        if (s['sa_acc']/sp) < min_acc: return False
        if (s['sa_spn']/sp) < min_spn: return False
        return True
    return f

def quiet_zone(thresh, window=10, max_total=10):
    """sum(atk+stl+shd+spn+acc) over last `window` spins <= max_total"""
    def f(s, prev):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        traj = s.get('_traj_ref', [])
        idx = s.get('_traj_idx', 0)
        if idx + 1 < window: return False  # not enough history
        total = 0
        for k in range(idx - window + 1, idx + 1):
            r = traj[k]
            total += r['atk_count'] + r['stl_count'] + r['shd_count'] + r['spn_count'] + r['acc_count']
        return total <= max_total
    return f

def early_s_predict(low, high, prev_classes, qz_window=10, qz_max=10):
    """sa_spins in [low..high] AND prev gap class in {S/M/L} AND quiet-zone passes"""
    def f(s, prev):
        sp = s['sa_spins']
        if sp < low or sp > high: return False
        cls = classify(prev)
        if cls not in prev_classes: return False
        traj = s.get('_traj_ref', [])
        idx = s.get('_traj_idx', 0)
        if idx + 1 < qz_window: return False
        total = 0
        for k in range(idx - qz_window + 1, idx + 1):
            r = traj[k]
            total += r['atk_count'] + r['stl_count'] + r['shd_count'] + r['spn_count'] + r['acc_count']
        return total <= qz_max
    return f


# === Candidate pool — v5 rules + Islam-flavored extras ===
CANDIDATES = [
    # --- v5 7-rule baseline (so we can see how each performs on Islam) ---
    ("STEAL t65 g0.34 cap105",          cond('steal', 65, 0.34, cap=105)),
    ("STEAL t130 g0.28",                cond('steal', 130, 0.28)),
    ("STEAL t150 g0.30",                cond('steal', 150, 0.30)),
    ("SHIELD t150 g0.30",               cond('shield', 150, 0.30)),
    ("Quiet-zone t130 last10<=10",      quiet_zone(130, 10, 10)),
    ("DG t130 cap155 a0.28 p0.24",      double_gate(130, 0.28, 0.24, cap=155)),
    ("DG t130 uncapped a0.28 p0.24",    double_gate(130, 0.28, 0.24)),
    ("Early-S prev=M/L sa[60..105] qz", early_s_predict(60, 105, {'M','L'})),

    # --- SHIELD variants (Islam known to respond to SHIELD+SUPP) ---
    ("SHIELD t110 g0.30",               cond('shield', 110, 0.30)),
    ("SHIELD t110 g0.32",               cond('shield', 110, 0.32)),
    ("SHIELD t130 g0.28",               cond('shield', 130, 0.28)),
    ("SHIELD t130 g0.30",               cond('shield', 130, 0.30)),
    ("SHIELD t130 g0.32",               cond('shield', 130, 0.32)),
    ("SHIELD t140 g0.30",               cond('shield', 140, 0.30)),

    # --- Quiet-zone variants ---
    ("Quiet-zone t110 last10<=10",      quiet_zone(110, 10, 10)),
    ("Quiet-zone t150 last10<=10",      quiet_zone(150, 10, 10)),
    ("Quiet-zone t130 last10<=8",       quiet_zone(130, 10, 8)),
    ("Quiet-zone t130 last15<=15",      quiet_zone(130, 15, 15)),
    ("Quiet-zone t130 last20<=20",      quiet_zone(130, 20, 20)),

    # --- Flat tail rules (high precision) ---
    ("FLAT 150/0.32",                   flat(150, 0.32)),
    ("FLAT 150/0.34",                   flat(150, 0.34)),
    ("FLAT 150/0.37",                   flat(150, 0.37)),
    ("FLAT 130/0.34",                   flat(130, 0.34)),
    ("FLAT 130/0.36",                   flat(130, 0.36)),
    ("FLAT 170/0.30",                   flat(170, 0.30)),
    ("FLAT 180/0.28",                   flat(180, 0.28)),

    # --- DG variants ---
    ("DG t150 a0.28 p0.24",             double_gate(150, 0.28, 0.24)),
    ("DG t140 a0.30 p0.22",             double_gate(140, 0.30, 0.22)),
    ("DG t110 cap155 a0.30 p0.24",      double_gate(110, 0.30, 0.24, cap=155)),

    # --- ATTACK conditioning (cohort exists, untested per-Islam) ---
    ("ATTACK t130 g0.30",               cond('attack', 130, 0.30)),
    ("ATTACK t150 g0.30",               cond('attack', 150, 0.30)),
    ("ATTACK t130 g0.28",               cond('attack', 130, 0.28)),
    # --- SPINS conditioning ---
    ("SPINS t130 g0.30",                cond('spins', 130, 0.30)),
    ("SPINS t150 g0.30",                cond('spins', 150, 0.30)),
    # --- ACC self-conditioning (back-to-back ACC) ---
    ("ACC-cond t130 g0.30",             cond('accumulation', 130, 0.30)),
    ("ACC-cond t110 g0.32",             cond('accumulation', 110, 0.32)),
]


def simulate_with_catches(fn, gaps):
    """Causal: fn at i means BET on spin i+1. Catch iff fn fires at i = L-2."""
    caught = set()
    bets = 0
    spins = 0
    for gi, gap in enumerate(gaps):
        traj = gap['trajectory']
        L = len(traj)
        spins += L
        if L < 2: continue
        prev = gap.get('prev_gap_length')
        for i in range(L - 1):
            sp = traj[i]
            sp['_traj_ref'] = traj
            sp['_traj_idx'] = i
            sp['_prev_triple_type'] = gap.get('prev_real_triple')
            try:
                if fn(sp, prev):
                    bets += 1
                    if i + 1 == L - 1:
                        caught.add(gi)
            except Exception:
                pass
    return caught, bets, spins


def union_simulate(fns, gaps):
    caught = set()
    bets = 0
    for gi, gap in enumerate(gaps):
        traj = gap['trajectory']
        L = len(traj)
        if L < 2: continue
        prev = gap.get('prev_gap_length')
        for i in range(L - 1):
            sp = traj[i]
            sp['_traj_ref'] = traj
            sp['_traj_idx'] = i
            sp['_prev_triple_type'] = gap.get('prev_real_triple')
            for fn in fns:
                try:
                    if fn(sp, prev):
                        bets += 1
                        if i + 1 == L - 1:
                            caught.add(gi)
                        break
                except Exception:
                    pass
    return caught, bets


def main():
    gaps = load_islam_gaps()
    total_gaps = len(gaps)
    total_spins = sum(len(g['trajectory']) for g in gaps)
    print(f"=== ISLAM-ONLY CAUSAL HUNT ===")
    print(f"Gaps: {total_gaps}    Spins: {total_spins}")
    print()

    # --- per-rule individual scores ---
    rule_data = {}
    print(f"{'rule':<40s}  {'catches':>9s}  {'bets':>5s}  {'mb/hit':>7s}  {'lift':>6s}")
    print("-" * 80)
    for name, fn in CANDIDATES:
        caught, bets, _ = simulate_with_catches(fn, gaps)
        n = len(caught)
        mb = bets / n if n else float('inf')
        base = total_gaps / total_spins
        lift = (n / bets) / base if bets else 0
        rule_data[name] = {'fn': fn, 'caught': caught, 'bets': bets, 'n': n, 'mb': mb, 'lift': lift}
        print(f"{name:<40s}  {n:>3d}/{total_gaps}  {bets:>5d}  {mb:>7.1f}  {lift:>5.1f}x")

    # --- shipped v5 7-rule on Islam (for reference) ---
    print()
    print("=" * 80)
    print("SHIPPED v5 7-rule on Islam (reference)")
    print("=" * 80)
    v5_names = [
        "STEAL t65 g0.34 cap105", "STEAL t130 g0.28", "STEAL t150 g0.30",
        "SHIELD t150 g0.30", "Quiet-zone t130 last10<=10",
        "DG t130 cap155 a0.28 p0.24", "Early-S prev=M/L sa[60..105] qz",
    ]
    v5_fns = [rule_data[n]['fn'] for n in v5_names]
    c, b = union_simulate(v5_fns, gaps)
    print(f"  catches: {len(c)}/{total_gaps} ({100*len(c)/total_gaps:.1f}%)  bets={b}  mb/hit={b/max(len(c),1):.1f}")

    # --- shipped v5.1 6-rule capped on Islam ---
    print()
    print("SHIPPED v5.1 6-rule capped on Islam")
    print("-" * 80)
    v51_fns = [rule_data[n]['fn'] for n in v5_names[:6]]
    c, b = union_simulate(v51_fns, gaps)
    print(f"  catches: {len(c)}/{total_gaps} ({100*len(c)/total_gaps:.1f}%)  bets={b}  mb/hit={b/max(len(c),1):.1f}")

    # --- shipped v5 6-rule uncapped on Islam ---
    print()
    print("SHIPPED v5 6-rule uncapped on Islam")
    print("-" * 80)
    v5u_names = ["STEAL t65 g0.34 cap105", "STEAL t130 g0.28", "STEAL t150 g0.30",
                 "SHIELD t150 g0.30", "Quiet-zone t130 last10<=10",
                 "DG t130 uncapped a0.28 p0.24"]
    v5u_fns = [rule_data[n]['fn'] for n in v5u_names]
    c, b = union_simulate(v5u_fns, gaps)
    print(f"  catches: {len(c)}/{total_gaps} ({100*len(c)/total_gaps:.1f}%)  bets={b}  mb/hit={b/max(len(c),1):.1f}")

    # --- TRUE union of ALL candidates ---
    print()
    print("=" * 80)
    print("TRUE union of ALL Islam candidates (ceiling)")
    print("=" * 80)
    all_fns = [rule_data[n]['fn'] for n, _ in CANDIDATES]
    c, b = union_simulate(all_fns, gaps)
    union_caught = c
    print(f"  catches: {len(c)}/{total_gaps} ({100*len(c)/total_gaps:.1f}%)  bets={b}  mb/hit={b/max(len(c),1):.1f}")

    # --- GREEDY minimum cover for Islam ---
    print()
    print("=" * 80)
    print("GREEDY MINIMUM COVER (Islam-best subset)")
    print("=" * 80)
    remaining = set(union_caught)
    chosen = []
    pool = [(n, rule_data[n]) for n, _ in CANDIDATES]
    while remaining:
        best = None
        best_score = None
        for name, d in pool:
            new = d['caught'] & remaining
            if not new: continue
            score = d['bets'] / len(new)
            if best_score is None or score < best_score:
                best_score = score
                best = (name, d, new)
        if best is None: break
        name, d, new = best
        chosen.append((name, len(new), d['bets'], d['mb']))
        remaining -= d['caught']
        pool = [(n, dd) for n, dd in pool if n != name]

    print(f"\n  Chosen subset ({len(chosen)} rules):")
    for name, new, bets, mb in chosen:
        print(f"    + {name:<40s}  +{new:>2d} new  ({bets} bets, {mb:.1f} mb/hit standalone)")

    # True union of chosen subset
    chosen_fns = [rule_data[n]['fn'] for n, _, _, _ in chosen]
    cc, cb = union_simulate(chosen_fns, gaps)
    print(f"\n  TRUE union of chosen subset:")
    print(f"    catches: {len(cc)}/{total_gaps} ({100*len(cc)/total_gaps:.1f}%)")
    print(f"    bets:    {cb}/{total_spins} ({100*cb/total_spins:.2f}%)")
    print(f"    mb/hit:  {cb/max(len(cc),1):.2f}")
    base = total_gaps / total_spins
    lift = (len(cc)/cb) / base if cb else 0
    print(f"    lift:    {lift:.2f}x")

    # --- ALSO: pareto frontier — top-N by efficiency ---
    print()
    print("=" * 80)
    print("PARETO — Top 10 individual rules for Islam by mb/hit (min 3 catches)")
    print("=" * 80)
    sorted_rules = sorted(
        [(n, d) for n, d in rule_data.items() if d['n'] >= 3],
        key=lambda x: x[1]['mb']
    )[:10]
    print(f"{'rule':<40s}  {'catches':>9s}  {'mb/hit':>7s}  {'lift':>6s}")
    print("-" * 70)
    for name, d in sorted_rules:
        print(f"{name:<40s}  {d['n']:>3d}/{total_gaps}  {d['mb']:>7.1f}  {d['lift']:>5.1f}x")


if __name__ == '__main__':
    main()
