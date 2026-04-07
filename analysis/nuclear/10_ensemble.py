"""
Chunk 10: Ensemble analysis.

Question: Do all the validated sub-10mb configs catch the SAME gaps, or different ones?
If different, combining them (BET if ANY config says BET) might give more total catches
while still being efficient.

Strategy: for each gap, record which configs "catch" it (gap ends during a bet window).
Then build the union — total unique catches and combined bet spins / mb/hit.
Also show overlap matrix and exclusive-to-each-config catches.
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


# ======================================================
# Decision functions — all sub-10mb validated configs
# ======================================================

def flat_fn(thresh, gate):
    def f(s, prev): return s['sa_spins'] >= thresh and s['sa_spins'] > 0 and (s['sa_acc']/s['sa_spins']) >= gate
    return f

def sml_fn(s_bound, l_bound, t_s, t_m, t_l, gate):
    SKIP = None
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
    """Rate acceleration: slope of acc_rate over last `win` spins."""
    def f(s, prev):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if (s['sa_acc']/sp) < min_rate: return False
        traj = s.get('_traj_ref', [])   # injected during simulation
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
    """COMBO: acc rate + spn rate + slope."""
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

def double_gate_fn(thresh, min_acc, min_spn):
    """Double gate: acc + spn rates, no slope (catches plateau-rate gaps COMBO rejects)."""
    def f(s, prev):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if (s['sa_acc']/sp) < min_acc: return False
        if (s['sa_spn']/sp) < min_spn: return False
        return True
    return f

def bivariate_low_fn(thresh, min_acc, other_col, max_other_rate):
    """Bivariate: high acc rate AND low another-symbol rate (e.g., low shield)."""
    def f(s, prev):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if (s['sa_acc']/sp) < min_acc: return False
        return (s.get(other_col, 0)/sp) <= max_other_rate
    return f

# === Shield/triple-type conditioned formulas ===
# These rules only fire when the PREVIOUS triple was a specific type.
# We pass the prev_real_triple via the gap object — need to inject it into spin state.

def shield_cond_fn(thresh, gate, required_prev='shield'):
    """Bet only if previous triple was a SHIELD (or other type) AND flat threshold/gate met."""
    def f(s, prev):
        if s.get('_prev_triple_type') != required_prev: return False
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        return (s['sa_acc']/sp) >= gate
    return f


CONFIGS = [
    # === ORIGINAL 11 ===
    ("COMBO w10 t110 a0.28 p0.20 s0.010",
     combo_fn(110, 0.28, 0.20, 10, 0.010), 9.3),
    ("Ideal RA w8 t110 rate0.30 s0.006",
     ra_fn(110, 0.30, 8, 0.006), 8.1),
    ("RA t130 rate0.28 s0.010",
     ra_fn(130, 0.28, 10, 0.010), 8.6),
    ("FLAT 150/0.32",
     flat_fn(150, 0.32), 6.7),
    ("SML L>=120 tL=130 g=0.32 (L-only)",
     sml_fn(1, 120, None, None, 130, 0.32), 2.4),
    ("SML L>=120 tL=130 g=0.30 (L-only)",
     sml_fn(1, 120, None, None, 130, 0.30), 4.2),
    ("SML S100 L120 tM=180 tL=130 g=0.32",
     sml_fn(100, 120, 150, 180, 130, 0.32), 3.8),
    ("SML S100 L120 tM=110 tL=130 g=0.32",
     sml_fn(100, 120, 150, 110, 130, 0.32), 4.8),
    ("SML S100 L130 tM=130 tL=100 g=0.32",
     sml_fn(100, 130, 150, 130, 100, 0.32), 5.9),
    ("SML S50  L130 tM=150 tL=100 g=0.32",
     sml_fn(50,  130, 100, 150, 100, 0.32), 7.8),
    ("SML S50  L130 tS=80 tM=150 tL=100 g=0.32",
     sml_fn(50,  130,  80, 150, 100, 0.32), 9.6),
    # === ADDED FROM AUDIT ===
    # Double-gate sniper variants — catch plateau-rate gaps COMBO rejects (no slope req)
    ("DG t130 acc0.32 spn0.22 (Sniper)",
     double_gate_fn(130, 0.32, 0.22), 6.1),
    ("DG t130 acc0.32 spn0.20",
     double_gate_fn(130, 0.32, 0.20), 7.2),
    ("DG t120 acc0.32 spn0.22",
     double_gate_fn(120, 0.32, 0.22), 8.7),
    ("DG t130 acc0.30 spn0.25",
     double_gate_fn(130, 0.30, 0.25), 8.7),
    # Higher rate gate (no spn requirement)
    ("FLAT 130/0.33",
     flat_fn(130, 0.33), 9.8),
    # Lower-threshold rate acceleration
    ("RA t120 rate0.28 s0.010",
     ra_fn(120, 0.28, 10, 0.010), 9.8),
    # SML with different L boundaries
    ("SML S100 L150 tM=130 tL=100 g=0.32",
     sml_fn(100, 150, 150, 130, 100, 0.32), 5.7),
    ("SML S100 L170 tM=130 tL=100 g=0.32",
     sml_fn(100, 170, 150, 130, 100, 0.32), 6.0),
    ("SML L>=100 tL=130 g=0.32 (L-only loose)",
     sml_fn(1, 100, None, None, 130, 0.32), 5.7),
    # SML SKIP variants
    ("SML S50 L120 tS=SKIP tM=150 tL=130 g=0.32",
     sml_fn(50, 120, None, 150, 130, 0.32), 5.6),
    ("SML S50 L120 tS=SKIP tM=SKIP tL=130 g=0.32",
     sml_fn(50, 120, None, None, 130, 0.32), 2.4),
    ("SML S100 L120 tM=150 tL=130 g=0.32",
     sml_fn(100, 120, 150, 150, 130, 0.32), 4.9),
    # Highest gate variant
    ("SML S50 L130 tS=100 tM=160 tL=100 g=0.34",
     sml_fn(50, 130, 100, 160, 100, 0.34), 1.6),
    # === USER-REQUESTED ADDITIONS: extreme gates + shield conditioning ===
    # Extreme rate gates (3 catches each — small but might add unique gaps)
    ("FLAT 130/0.37",
     flat_fn(130, 0.37), 7.0),
    ("FLAT 110/0.37",
     flat_fn(110, 0.37), 7.0),
    ("FLAT 150/0.37",
     flat_fn(150, 0.37), 7.0),
    ("FLAT 130/0.36",
     flat_fn(130, 0.36), 9.5),
    ("FLAT 130/0.34",
     flat_fn(130, 0.34), 7.0),
    # Shield-conditioned rules — only fire after previous triple was SHIELD
    ("SHIELD-cond 110/0.32",
     shield_cond_fn(110, 0.32, 'shield'), 9.4),
    ("SHIELD-cond 120/0.32",
     shield_cond_fn(120, 0.32, 'shield'), 8.5),
    ("SHIELD-cond 130/0.32",
     shield_cond_fn(130, 0.32, 'shield'), 6.3),
    ("SHIELD-cond 140/0.32",
     shield_cond_fn(140, 0.32, 'shield'), 6.0),
    # Also try attack-conditioned (78 gaps follow attack — biggest cohort, untested)
    ("ATTACK-cond 130/0.32",
     shield_cond_fn(130, 0.32, 'attack'), 9.0),
    ("ATTACK-cond 110/0.32",
     shield_cond_fn(110, 0.32, 'attack'), 9.0),
]


def simulate_with_catch_flags(fn, gaps):
    """
    CAUSAL: rule fires at state i (after spin i) determines the bet for spin i+1.
    A gap is caught iff the rule fired at i = L-2 (the spin BEFORE the triple),
    because the user acts on the tile state after that spin to bet on the triple
    at L-1. This matches live tracker semantics.

    Returns:
      - caught_set: set of gap indices where the rule fired at L-2
      - bet_spins: count of (i, i+1) pairs where rule fired at i (0 <= i <= L-2)
      - total_spins: total spins seen
    """
    caught_set = set()
    bet_spins  = 0
    total_spins = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        L = len(traj)
        total_spins += L
        if L < 2:
            continue
        # Walk 0..L-2: rule firing at i means user bets high for spin i+1
        for i in range(L - 1):
            spin = traj[i]
            spin['_traj_ref'] = traj
            spin['_traj_idx'] = i
            spin['_prev_triple_type'] = gap.get('prev_real_triple')
            decision = fn(spin, prev)
            if decision is None:
                continue
            if decision:
                bet_spins += 1  # user bet high for spin i+1
                if i + 1 == L - 1:
                    caught_set.add(gap_idx)  # that's the triple
    return caught_set, bet_spins, total_spins


def run():
    gaps = all_gaps_with_prev()
    # Use only gaps with known prev for SML fairness
    # (flat/RA configs don't need prev so they run on all 178)
    all_gap_indices = list(range(len(gaps)))

    results = []
    results.append("=" * 100)
    results.append("CHUNK 10: ENSEMBLE ANALYSIS — Sub-10mb Configs")
    results.append("=" * 100)
    results.append(f"Total gaps: {len(gaps)} (178 total, 175 with known prev)")

    # ---- Per-config results ----
    config_data = {}  # name -> {caught_set, bet_spins, total_spins}
    results.append(f"\n{'config':>45s}  {'caught':>8s}  {'bet%':>6s}  {'mb/hit':>7s}  {'lift':>7s}")
    results.append("-" * 85)

    for name, fn, ref_mb in CONFIGS:
        caught_set, bet_spins, total_spins = simulate_with_catch_flags(fn, gaps)
        n_caught = len(caught_set)
        n_gaps   = len(gaps)
        bhr = n_caught / bet_spins if bet_spins else 0
        br  = n_gaps / total_spins if total_spins else 0
        mb  = bet_spins / n_caught if n_caught else float('inf')
        lift = bhr / br if br else 0
        bet_pct = 100 * bet_spins / total_spins if total_spins else 0
        config_data[name] = {'caught_set': caught_set, 'bet_spins': bet_spins,
                             'total_spins': total_spins, 'n_gaps': n_gaps}
        results.append(f"{name:>45s}  {n_caught:3d}/{n_gaps:3d}   {bet_pct:5.2f}%  {mb:7.1f}  {lift:7.1f}x")

    # ---- Overlap matrix ----
    results.append(f"\n--- Overlap matrix (how many gaps caught by BOTH row and col) ---")
    names = [c[0] for c in CONFIGS]
    short = [n.replace("SML ","S:").replace("FLAT ","F:").replace("Ideal ","I:").replace("COMBO ","C:").replace("RA ","R:")[:20] for n in names]

    header = f"{'':>25s}"
    for s in short:
        header += f"  {s[:8]:>8s}"
    results.append(header)

    for i, ni in enumerate(names):
        row = f"{short[i][:25]:>25s}"
        si = config_data[ni]['caught_set']
        for j, nj in enumerate(names):
            sj = config_data[nj]['caught_set']
            overlap = len(si & sj)
            row += f"  {overlap:>8d}"
        results.append(row)

    # ---- Union analysis — add configs one by one in order of mb/hit ----
    results.append(f"\n--- Union build-up: adding configs sorted by mb/hit ---")
    results.append(f"{'configs included':>50s}  {'unique catches':>15s}  {'bet_spins':>10s}  {'mb/hit':>8s}")
    results.append("-" * 90)

    # Sort configs by mb/hit (reference value)
    sorted_configs = sorted(CONFIGS, key=lambda x: x[2])

    union_caught   = set()
    union_bet_spins = 0
    total_spins_ref = config_data[CONFIGS[0][0]]['total_spins']
    n_gaps_ref      = config_data[CONFIGS[0][0]]['n_gaps']

    for name, fn, ref_mb in sorted_configs:
        d = config_data[name]
        new_catches = d['caught_set'] - union_caught
        union_caught   |= d['caught_set']
        union_bet_spins += d['bet_spins']
        # Deduplicate bet spins properly requires per-spin tracking — approximate here
        n = len(union_caught)
        mb = union_bet_spins / n if n else float('inf')
        results.append(f"+{name[:48]:>48s}  {n:3d}/{n_gaps_ref:3d} (+{len(new_catches):2d})  "
                       f"{union_bet_spins:>10d}  {mb:8.1f}")

    # ---- True union simulation ----
    results.append(f"\n--- TRUE union simulation (bet if ANY config says bet) — CAUSAL ---")
    results.append("(rule firing at i determines bet for spin i+1; catch iff i+1 == triple)")

    all_fns = [fn for _, fn, _ in CONFIGS]
    union_caught_true = set()
    union_bet_true    = 0
    union_total       = 0

    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        L = len(traj)
        union_total += L
        if L < 2: continue
        for i in range(L - 1):
            spin = traj[i]
            spin['_traj_ref'] = traj
            spin['_traj_idx'] = i
            spin['_prev_triple_type'] = gap.get('prev_real_triple')
            any_bet = False
            for fn in all_fns:
                decision = fn(spin, prev)
                if decision:
                    any_bet = True
                    break
            if any_bet:
                union_bet_true += 1
                if i + 1 == L - 1:
                    union_caught_true.add(gap_idx)

    n_u = len(union_caught_true)
    bhr_u = n_u / union_bet_true if union_bet_true else 0
    br_u  = len(gaps) / union_total if union_total else 0
    mb_u  = union_bet_true / n_u if n_u else float('inf')
    lift_u = bhr_u / br_u if br_u else 0
    bet_pct_u = 100 * union_bet_true / union_total if union_total else 0
    results.append(f"  Unique catches:  {n_u}/{len(gaps)} ({100*n_u/len(gaps):.1f}%)")
    results.append(f"  Bet spins:       {union_bet_true:,} / {union_total:,} ({bet_pct_u:.2f}%)")
    results.append(f"  mb/hit:          {mb_u:.1f}")
    results.append(f"  lift:            {lift_u:.1f}x")

    # Per-account breakdown of union
    results.append(f"\n  Per-account union:")
    for acct in ACCOUNTS:
        acct_gaps = [g for g in gaps if g.get('account') == acct]
        acct_indices = [i for i, g in enumerate(gaps) if g.get('account') == acct]
        acct_union_caught = union_caught_true & set(acct_indices)
        results.append(f"    {acct}: {len(acct_union_caught)}/{len(acct_gaps)}")

    # ---- Which gaps are exclusive to SML (not caught by COMBO) ----
    results.append(f"\n--- Exclusive catches (not caught by COMBO flat) ---")
    combo_name = "COMBO w10 t110 a0.28 p0.20 s0.010"
    combo_set = config_data[combo_name]['caught_set']
    for name, fn, ref_mb in CONFIGS:
        if name == combo_name: continue
        excl = config_data[name]['caught_set'] - combo_set
        if excl:
            results.append(f"  {name[:45]:>45s}: {len(excl)} exclusive catches (gaps {sorted(excl)})")
        else:
            results.append(f"  {name[:45]:>45s}: 0 exclusive (all subsumed by COMBO)")

    # ---- COMBO + SML L-only union ----
    results.append(f"\n--- Targeted union: COMBO + SML L-only L>=120 tL=130 g=0.32 ---")
    sml_name = "SML L>=120 tL=130 g=0.32 (L-only)"
    combo_sml_union = combo_set | config_data[sml_name]['caught_set']
    combo_sml_bets  = 0
    combo_fn_  = CONFIGS[0][1]
    sml_fn_    = CONFIGS[4][1]
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        for i, spin in enumerate(traj):
            spin['_traj_ref'] = traj
            spin['_traj_idx'] = i
            spin['_prev_triple_type'] = gap.get('prev_real_triple')
            d1 = combo_fn_(spin, prev)
            d2 = sml_fn_(spin, prev)
            if d1 or d2:
                combo_sml_bets += 1

    n_cs = len(combo_sml_union)
    mb_cs = combo_sml_bets / n_cs if n_cs else float('inf')
    lift_cs = (n_cs / combo_sml_bets) / (len(gaps) / union_total) if combo_sml_bets else 0
    results.append(f"  COMBO alone:           {len(combo_set)}/{len(gaps)}  mb={config_data[combo_name]['bet_spins']/len(combo_set):.1f}")
    results.append(f"  SML L-only alone:      {len(config_data[sml_name]['caught_set'])}/{len(gaps)}  mb={config_data[sml_name]['bet_spins']/max(len(config_data[sml_name]['caught_set']),1):.1f}")
    results.append(f"  COMBO | SML L-only:    {n_cs}/{len(gaps)}  mb={mb_cs:.1f}  lift={lift_cs:.1f}x")
    results.append(f"  Extra catches vs COMBO: +{n_cs - len(combo_set)}")

    # ---- MINIMUM COVER: greedy + bet-spin-optimal subset search ----
    results.append(f"\n--- MINIMUM COVER ANALYSIS ---")
    results.append("Goal: smallest config subset that catches all 62 union gaps with FEWEST bet spins")

    target_set = union_caught_true  # the 62 catches we want to preserve

    # Greedy: at each step, pick the config that adds the most NEW catches per bet spin
    remaining = set(target_set)
    chosen = []
    available = [(name, fn, ref_mb) for name, fn, ref_mb in CONFIGS]

    # We need to know each config's bet spins (already in config_data)
    while remaining:
        best_score = None
        best_idx   = -1
        for i, (name, fn, ref_mb) in enumerate(available):
            d = config_data[name]
            new_catches = d['caught_set'] & remaining
            if not new_catches:
                continue
            # Score: bet_spins per new catch (lower is better)
            score = d['bet_spins'] / len(new_catches)
            if best_score is None or score < best_score:
                best_score = score
                best_idx   = i
        if best_idx < 0:
            break  # nothing more to add
        name, fn, ref_mb = available.pop(best_idx)
        d = config_data[name]
        new = d['caught_set'] & remaining
        chosen.append((name, len(new)))
        remaining -= d['caught_set']

    results.append(f"\n  Greedy chosen subset ({len(chosen)} configs):")
    for name, n_new in chosen:
        results.append(f"    + {name}  (+{n_new} new catches)")

    # Compute true mb/hit of chosen subset
    chosen_fns = [fn for name, fn, _ in CONFIGS if name in [c[0] for c in chosen]]
    subset_caught = set()
    subset_bet    = 0
    for gap_idx, gap in enumerate(gaps):
        prev = gap.get('prev_gap_length')
        traj = gap['trajectory']
        for i, spin in enumerate(traj):
            spin['_traj_ref'] = traj
            spin['_traj_idx'] = i
            spin['_prev_triple_type'] = gap.get('prev_real_triple')
            any_bet = False
            for fn in chosen_fns:
                if fn(spin, prev):
                    any_bet = True
                    break
            if any_bet:
                subset_bet += 1
                if i == len(traj) - 1:
                    subset_caught.add(gap_idx)

    sub_mb = subset_bet / len(subset_caught) if subset_caught else float('inf')
    results.append(f"\n  TRUE simulation of greedy subset:")
    results.append(f"    catches:    {len(subset_caught)}/{len(gaps)}")
    results.append(f"    bet spins:  {subset_bet} / {union_total}  ({100*subset_bet/union_total:.2f}%)")
    results.append(f"    mb/hit:     {sub_mb:.2f}")
    results.append(f"    vs full union: {n_u} catches at {mb_u:.1f} mb/hit")
    results.append(f"    vs COMBO alone: {len(combo_set)} catches at {config_data[combo_name]['bet_spins']/len(combo_set):.1f} mb/hit")

    out_path = os.path.join(os.path.dirname(__file__), '10_ensemble_results.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))
    print(f"Saved -> {out_path}")
    print(f"\nKey results:")
    print(f"  TRUE UNION ({len(CONFIGS)} configs): {n_u}/{len(gaps)} catches  mb={mb_u:.1f}  lift={lift_u:.1f}x")
    print(f"  COMBO alone: {len(combo_set)}/{len(gaps)} catches  mb={config_data[combo_name]['bet_spins']/len(combo_set):.1f}")
    print(f"  COMBO | SML L-only: {n_cs}/{len(gaps)} catches  mb={mb_cs:.1f}")
    print(f"\n  GREEDY MINIMUM COVER: {len(chosen)} configs -> {len(subset_caught)} catches  mb={sub_mb:.2f}")
    print(f"    Configs: {[c[0] for c in chosen]}")


if __name__ == '__main__':
    run()
