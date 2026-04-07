"""
Chunk 12: Per-rule catch timing analysis.

For every one of the 16 rules in the ensemble, show:
  - All gaps it catches
  - For each catch:
      * ALERT spin  = first spin where sa_spins reaches the rule's effective threshold
                      (the rule is now "eligible" — waiting for rate gates)
      * FIRE spin   = first spin where ALL the rule's gates pass (rule returns True)
      * TRIPLE spin = last spin of the gap (where the catch actually happens)
      * lead time   = TRIPLE - FIRE (how many spins of warning before the catch)
      * windup time = FIRE - ALERT (how many spins between eligibility and firing)

Uses the simulator logic from 10_ensemble.py with the live causal
prev_real_triple semantics. No cooldown applied — we want to see the
raw rule behavior.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('e10', os.path.join(os.path.dirname(__file__), '10_ensemble.py'))
e10 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e10)

import pickle
from pathlib import Path

GAPS_PATH = Path(__file__).parent / 'gaps.pkl'

# The 16 rules of the final ensemble — from 10_ensemble.py's CONFIGS list
WANTED_RULES = [
    ("1. COMBO w10 t110 a0.28 p0.20 s0.010",       "COMBO w10 t110 a0.28 p0.20 s0.010",       110, 0.28),
    ("2. Ideal RA w8 t110 r0.30 s0.006",           "Ideal RA w8 t110 rate0.30 s0.006",        110, 0.30),
    ("3. RA t130 r0.28 s0.010",                    "RA t130 rate0.28 s0.010",                 130, 0.28),
    ("4. FLAT 150/0.32",                           "FLAT 150/0.32",                           150, 0.32),
    ("5. SML L>=120 tL=130 g=0.32",                "SML L>=120 tL=130 g=0.32 (L-only)",       130, 0.32),
    ("6. SML L>=120 tL=130 g=0.30",                "SML L>=120 tL=130 g=0.30 (L-only)",       130, 0.30),
    ("7. SML S100 L120 tM=180 tL=130",             "SML S100 L120 tM=180 tL=130 g=0.32",      180, 0.32),
    ("8. SML S100 L120 tM=110 tL=130",             "SML S100 L120 tM=110 tL=130 g=0.32",      110, 0.32),
    ("9. SML S100 L130 tM=130 tL=100",             "SML S100 L130 tM=130 tL=100 g=0.32",      130, 0.32),
    ("10. SML S50 L130 tM=150 tL=100",             "SML S50  L130 tM=150 tL=100 g=0.32",      150, 0.32),
    ("11. SML S50 L130 tS=80 tM=150 tL=100",       "SML S50  L130 tS=80 tM=150 tL=100 g=0.32",150, 0.32),
    ("12. SHIELD-cond 110/0.32",                   "SHIELD-cond 110/0.32",                    110, 0.32),
    ("13. SHIELD-cond 120/0.32",                   "SHIELD-cond 120/0.32",                    120, 0.32),
    ("14. SHIELD-cond 130/0.32",                   "SHIELD-cond 130/0.32",                    130, 0.32),
    ("15. SHIELD-cond 140/0.32",                   "SHIELD-cond 140/0.32",                    140, 0.32),
    ("16. FLAT 150/0.37",                          "FLAT 150/0.37",                           150, 0.37),
]


def compute_effective_threshold(rule_name, prev_gap):
    """Return the effective spin threshold for this rule given prev_gap.
    Mirrors the SML S/M/L bucket logic for each rule."""
    if "SML L>=120" in rule_name:
        return 130 if (prev_gap is not None and prev_gap >= 120) else 999
    if "SML S100 L120 tM=180" in rule_name:
        if prev_gap is None: return 180
        if prev_gap < 100:   return 150
        if prev_gap < 120:   return 180
        return 130
    if "SML S100 L120 tM=110" in rule_name:
        if prev_gap is None: return 110
        if prev_gap < 100:   return 150
        if prev_gap < 120:   return 110
        return 130
    if "SML S100 L130 tM=130 tL=100" in rule_name:
        if prev_gap is None: return 130
        if prev_gap < 100:   return 150
        if prev_gap < 130:   return 130
        return 100
    if "SML S50  L130 tM=150 tL=100" in rule_name and "tS=80" not in rule_name:
        if prev_gap is None: return 150
        if prev_gap < 50:    return 100
        if prev_gap < 130:   return 150
        return 100
    if "SML S50  L130 tS=80" in rule_name:
        if prev_gap is None: return 150
        if prev_gap < 50:    return 80
        if prev_gap < 130:   return 150
        return 100
    # Plain flat rules / COMBO / Ideal RA / RA / SHIELD-cond: base threshold from WANTED_RULES
    for display, sim_name, base_thresh, _ in WANTED_RULES:
        if sim_name == rule_name:
            return base_thresh
    return 999


def all_gaps_with_prev():
    with open(GAPS_PATH, 'rb') as f:
        data = pickle.load(f)
    out = []
    for acct in ['Islam', 'Ahmed', 'Nick']:
        raw = data[acct]['gaps'].get('accumulation', [])
        for i, g in enumerate(raw):
            g2 = dict(g)
            g2['prev_gap_length'] = raw[i-1]['length'] if i > 0 else None
            g2['account'] = acct
            out.append(g2)
    return out


def run():
    gaps = all_gaps_with_prev()

    # Build name lookup to the real sim function
    name_to_fn = {}
    for n, fn, _ in e10.CONFIGS:
        name_to_fn[n] = fn

    # One combined file, each rule is a clearly separated section
    out = []
    out.append("=" * 120)
    out.append("CHUNK 12: PER-RULE CATCH TIMING — ALL RULES IN ONE FILE")
    out.append("=" * 120)
    out.append("")
    out.append("Legend:")
    out.append("  eff_t  = effective spin threshold (may change per gap based on prev_gap for SML rules)")
    out.append("  ALERT  = first sa_spins value where the rule became eligible (spins >= eff_t)")
    out.append("  FIRE   = first sa_spins value where the rule returned True (all gates met, would BET)")
    out.append("  TRIPLE = last spin of the gap — i.e. sa_spins at the ACC catch")
    out.append("  windup = FIRE - ALERT (how many spins between eligibility and first fire)")
    out.append("  lead   = TRIPLE - FIRE (how many spins of warning before the actual catch)")
    out.append("  bets   = how many spins this rule bet on within this caught gap")
    out.append("")

    # Per-rule summary table at the top
    rule_stats = []  # (display, catches, total_bets, mb)

    # First pass: compute stats + summaries for each rule so we can print the TOC
    rule_summaries = {}  # display_name -> summaries list

    for display_name, sim_name, _, _ in WANTED_RULES:
        fn = name_to_fn.get(sim_name)
        if fn is None:
            rule_stats.append((display_name, 0, 0, 0.0))
            rule_summaries[display_name] = []
            continue

        caught_count = 0
        total_bets = 0
        summaries = []

        for gi, gap in enumerate(gaps):
            prev = gap.get('prev_gap_length')
            traj = gap['trajectory']
            eff_thresh = compute_effective_threshold(sim_name, prev)

            alert_spin = None
            bet_count = 0

            # Track fire "episodes" — each continuous run of firing is one episode.
            # An episode is (start_spin, end_spin). If the rule stops firing and
            # fires again later in the same gap, that's a new episode.
            episodes = []         # list of (start, end) sa_spins values
            current_start = None  # start of the current episode, if we're in one

            for i, spin in enumerate(traj):
                spin['_traj_ref'] = traj
                spin['_traj_idx'] = i
                spin['_prev_triple_type'] = gap.get('prev_real_triple')

                sp = spin['sa_spins']
                if alert_spin is None and sp >= eff_thresh:
                    alert_spin = sp

                fired = fn(spin, prev)
                if fired:
                    bet_count += 1
                    if current_start is None:
                        current_start = sp  # episode starts
                    # We keep the end updated every spin we fire
                    current_end = sp
                else:
                    if current_start is not None:
                        episodes.append((current_start, current_end))
                        current_start = None

            # Close any dangling episode (ran until the end of the gap)
            if current_start is not None:
                episodes.append((current_start, current_end))

            # Was this gap caught by this rule? = did the rule fire on the LAST spin?
            last_idx = len(traj) - 1
            if last_idx < 0:
                continue
            last_spin = traj[last_idx]
            last_spin['_traj_ref'] = traj
            last_spin['_traj_idx'] = last_idx
            last_spin['_prev_triple_type'] = gap.get('prev_real_triple')
            was_caught = fn(last_spin, prev)

            if was_caught:
                caught_count += 1
                total_bets += bet_count
                triple_spin = gap['length']
                first_fire = episodes[0][0] if episodes else None
                windup = (first_fire - alert_spin) if (first_fire is not None and alert_spin is not None) else None
                lead = (triple_spin - first_fire) if first_fire is not None else None
                n_episodes = len(episodes)
                summaries.append({
                    'gap_idx': gi,
                    'account': gap['account'],
                    'gap_len': gap['length'],
                    'prev_gap': prev,
                    'prev_triple': gap.get('prev_real_triple'),
                    'eff_thresh': eff_thresh,
                    'alert': alert_spin,
                    'fire':  first_fire,
                    'triple': triple_spin,
                    'bets': bet_count,
                    'windup': windup,
                    'lead': lead,
                    'episodes': episodes,
                    'n_episodes': n_episodes,
                })

        mb = total_bets / max(caught_count, 1)
        rule_stats.append((display_name, caught_count, total_bets, mb))
        rule_summaries[display_name] = summaries

    # Print TOC
    out.append("TABLE OF CONTENTS")
    out.append("-" * 120)
    out.append(f"{'rule':<45s}  {'catches':>8s}  {'bets':>6s}  {'mb/hit':>7s}")
    out.append("-" * 120)
    for display, c, b, mb in rule_stats:
        out.append(f"{display:<45s}  {c:>8d}  {b:>6d}  {mb:>7.2f}")
    out.append("")
    out.append("")

    # Print each rule's dedicated section
    for display_name, _, _, _ in WANTED_RULES:
        summaries = rule_summaries.get(display_name, [])
        stat = next((s for s in rule_stats if s[0] == display_name), None)
        if stat is None:
            continue
        _, caught_count, total_bets, mb = stat

        out.append("=" * 120)
        out.append(f"{display_name}")
        out.append("=" * 120)
        out.append(f"Catches: {caught_count}  |  Total bets across catches: {total_bets}  |  mb/hit: {mb:.2f}")
        out.append("")

        if not summaries:
            out.append("  (no catches for this rule)")
            out.append("")
            continue

        out.append(f"  {'gap':>4s}  {'acct':>6s}  {'len':>4s}  {'prev':>5s}  "
                   f"{'eff_t':>5s}  {'ALERT':>6s}  {'FIRE':>6s}  {'TRIPLE':>7s}  "
                   f"{'windup':>7s}  {'lead':>5s}  {'bets':>5s}  {'eps':>4s}  fire episodes (start..end)  prev_triple")
        out.append("  " + "-" * 140)

        summaries.sort(key=lambda s: (s['account'], s['gap_idx']))
        for s in summaries:
            alert_s  = str(s['alert'])  if s['alert']  is not None else "-"
            fire_s   = str(s['fire'])   if s['fire']   is not None else "-"
            windup_s = str(s['windup']) if s['windup'] is not None else "-"
            lead_s   = str(s['lead'])   if s['lead']   is not None else "-"
            prev_s   = str(s['prev_gap']) if s['prev_gap'] is not None else "-"
            pt_s     = s['prev_triple'] or "-"
            eps_str  = ",".join(f"[{a}..{b}]" for (a, b) in s['episodes'])
            # Mark multi-episode catches with a * so they stand out
            eps_marker = "*" if s['n_episodes'] > 1 else " "
            out.append(f"  {s['gap_idx']:>4d}  {s['account']:>6s}  {s['gap_len']:>4d}  {prev_s:>5s}  "
                       f"{s['eff_thresh']:>5d}  {alert_s:>6s}  {fire_s:>6s}  {s['triple']:>7d}  "
                       f"{windup_s:>7s}  {lead_s:>5s}  {s['bets']:>5d}  {s['n_episodes']:>3d}{eps_marker}  {eps_str[:55]:<55s}  {pt_s}")

        # Per-rule summary stats
        out.append("")
        acct_counts = {acct: sum(1 for s in summaries if s['account'] == acct) for acct in ['Islam', 'Ahmed', 'Nick']}
        out.append(f"  Per-account: Islam={acct_counts['Islam']}  Ahmed={acct_counts['Ahmed']}  Nick={acct_counts['Nick']}")

        # Re-fire stats
        multi_eps = [s for s in summaries if s['n_episodes'] > 1]
        if multi_eps:
            max_eps = max(s['n_episodes'] for s in summaries)
            out.append(f"  Re-fires: {len(multi_eps)}/{len(summaries)} catches had >1 fire episode  (max episodes in one gap: {max_eps})")
        else:
            out.append(f"  Re-fires: 0 (every caught gap had exactly 1 continuous fire episode)")

        valid_leads = [s['lead'] for s in summaries if s['lead'] is not None]
        valid_windups = [s['windup'] for s in summaries if s['windup'] is not None]
        if valid_leads:
            out.append(f"  Lead time (spins from first FIRE to TRIPLE):  min={min(valid_leads)}  max={max(valid_leads)}  mean={sum(valid_leads)/len(valid_leads):.1f}")
        if valid_windups:
            out.append(f"  Windup   (spins from ALERT to first FIRE):   min={min(valid_windups)}  max={max(valid_windups)}  mean={sum(valid_windups)/len(valid_windups):.1f}")
        out.append("")

    out_path = os.path.join(os.path.dirname(__file__), '12_rule_timing.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f"Saved -> {out_path}")
    print(f"  {sum(c for _, c, _, _ in rule_stats)} total catches across 16 rules")


if __name__ == '__main__':
    run()
