"""
Chunk 14: Live tracker ground truth.

Cross-reference each account's bet_decisions.csv against its spin_history.csv
to find out what the LIVE tracker actually caught in today's session.

For each ACC triple (last spin of a gap):
  - Look up the PREVIOUS row in bet_decisions.csv (spin N-1)
  - If rules_count > 0 AND phase == BET on spin N-1, it's a REAL catch
  - If rules_count == 0 on spin N-1 but rules fired on spin N (the triple itself),
    it's a PHANTOM (matches what the broken simulator would call "caught")

This validates (or refutes) the causal simulator. If the live tracker's real
catch rate matches the causal sim's 16.2%, the fix is confirmed.
"""
import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent / 'data_2026-04-07'

ACCOUNTS = ['Ahmed', 'Islam', 'Nick']


def load_spin_history(path):
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_bet_decisions(path):
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def analyze_account(account):
    sh_path = DATA_DIR / f'{account}_spin_history.csv'
    bd_path = DATA_DIR / f'{account}_bet_decisions.csv'

    spins = load_spin_history(sh_path)
    decisions = load_bet_decisions(bd_path)

    # Build seq -> decision row
    by_seq = {int(d['seq']): d for d in decisions}

    # Tracker-covered range = seqs actually recorded in bet_decisions
    if by_seq:
        tracker_min = min(by_seq.keys())
        tracker_max = max(by_seq.keys())
    else:
        tracker_min = tracker_max = None

    # Walk spin_history and find ACC triples. Only analyze triples that fall
    # within the tracker-covered seq range (where bet_decisions has data).
    acc_triples = []
    for i, row in enumerate(spins):
        if row.get('is_triple') == 'true' and row.get('reel_1') == 'accumulation':
            seq = int(row['seq'])
            prev_seq = seq - 1
            prev_decision = by_seq.get(prev_seq)
            this_decision = by_seq.get(seq)
            in_tracker_range = (tracker_min is not None
                                and tracker_min <= prev_seq
                                and seq <= tracker_max)
            acc_triples.append({
                'seq': seq,
                'sa_spins': int(row.get('sa_spins', 0)),
                'prev_rules': int(prev_decision['rules_count']) if prev_decision else None,
                'prev_phase': prev_decision.get('phase') if prev_decision else None,
                'this_rules': int(this_decision['rules_count']) if this_decision else None,
                'this_phase': this_decision.get('phase') if this_decision else None,
                'target_caught': int(this_decision.get('target_caught', 0)) if this_decision else 0,
                'in_tracker_range': in_tracker_range,
            })

    # Two sets of stats:
    #   1) All triples (includes pre-tracker-init ones — useful for overall catch rate)
    #   2) Only triples within the tracker-covered range (ground truth subset)
    real_catches = 0
    phantom_catches = 0
    missed = 0
    outside_range = 0

    for t in acc_triples:
        if not t['in_tracker_range']:
            outside_range += 1
        elif t['prev_rules'] is not None and t['prev_rules'] > 0 and t['prev_phase'] == 'BET':
            real_catches += 1
        elif (t['this_rules'] or 0) > 0 and (t['prev_rules'] or 0) == 0:
            phantom_catches += 1
        else:
            missed += 1

    in_range_count = sum(1 for t in acc_triples if t['in_tracker_range'])

    return {
        'account': account,
        'spin_count': len(spins),
        'triple_count': len(acc_triples),
        'in_range_count': in_range_count,
        'real': real_catches,
        'phantom': phantom_catches,
        'missed': missed,
        'outside_range': outside_range,
        'tracker_range': (tracker_min, tracker_max),
        'triples': acc_triples,
    }


def run():
    lines = []
    lines.append("=" * 110)
    lines.append("CHUNK 14: LIVE TRACKER GROUND TRUTH — from bet_decisions.csv")
    lines.append("=" * 110)
    lines.append("")
    lines.append("Reads each account's spin_history.csv + bet_decisions.csv and checks, for every")
    lines.append("ACC triple, whether the live tracker was actually in BET phase on the PREVIOUS spin.")
    lines.append("")
    lines.append("  REAL    = prev spin had rules_count > 0 AND phase == BET (user bet high, triple hit)")
    lines.append("  PHANTOM = prev spin had 0 rules firing, but rules fired ON the triple spin itself")
    lines.append("  MISSED  = no rules fired on prev or this spin (tracker missed it entirely)")
    lines.append("")

    total_in_range = 0
    total_real = 0
    total_phantom = 0
    total_missed = 0

    for acct in ACCOUNTS:
        try:
            r = analyze_account(acct)
        except Exception as e:
            lines.append(f"{acct}: ERROR — {e}")
            continue

        tmin, tmax = r['tracker_range']
        lines.append(f"--- {acct} ---")
        lines.append(f"  Spin history:        {r['spin_count']} rows")
        lines.append(f"  bet_decisions range: seq {tmin}..{tmax}  ({tmax - tmin + 1 if tmin else 0} spins)")
        lines.append(f"  ACC triples total:   {r['triple_count']}")
        lines.append(f"  ACC triples in range: {r['in_range_count']}  (only these have ground truth)")
        denom = max(r['in_range_count'], 1)
        lines.append(f"  REAL catches: {r['real']}  ({100*r['real']/denom:.1f}% of in-range triples)")
        lines.append(f"  PHANTOM:      {r['phantom']}  ({100*r['phantom']/denom:.1f}%)")
        lines.append(f"  MISSED:       {r['missed']}  ({100*r['missed']/denom:.1f}%)")
        lines.append(f"  Outside range:{r['outside_range']}  (logger not active for those)")
        lines.append("")

        total_in_range += r['in_range_count']
        total_real += r['real']
        total_phantom += r['phantom']
        total_missed += r['missed']

        # Show details of IN-RANGE triples
        in_range_triples = [t for t in r['triples'] if t['in_tracker_range']]
        if in_range_triples:
            lines.append(f"  All {len(in_range_triples)} in-range triples:")
            lines.append(f"    {'seq':>7s}  {'sa_spins':>8s}  {'prev_rules':>10s}  {'prev_phase':>10s}  {'this_rules':>10s}  {'verdict':<12s}")
            for t in in_range_triples:
                verdict = "?"
                if t['prev_rules'] is not None and t['prev_rules'] > 0 and t['prev_phase'] == 'BET':
                    verdict = "REAL"
                elif (t['this_rules'] or 0) > 0 and (t['prev_rules'] or 0) == 0:
                    verdict = "PHANTOM"
                else:
                    verdict = "MISSED"
                lines.append(f"    {t['seq']:>7d}  {t['sa_spins']:>8d}  {str(t['prev_rules']):>10s}  "
                             f"{str(t['prev_phase']):>10s}  {str(t['this_rules']):>10s}  {verdict:<12s}")
        lines.append("")

    lines.append("=" * 110)
    lines.append(f"TOTAL (in-range only — ground truth subset)")
    lines.append("=" * 110)
    lines.append(f"  In-range ACC triples:  {total_in_range}")
    lines.append(f"  REAL catches: {total_real}  ({100*total_real/max(total_in_range,1):.1f}%)")
    lines.append(f"  PHANTOM:      {total_phantom}  ({100*total_phantom/max(total_in_range,1):.1f}%)")
    lines.append(f"  MISSED:       {total_missed}  ({100*total_missed/max(total_in_range,1):.1f}%)")
    lines.append("")
    lines.append("Compare to causal simulator projection on all 271 gaps: 44 catches (16.2%).")
    lines.append("If live REAL % is close to 16%, the causal simulator is validated.")

    out_path = Path(__file__).parent / '14_live_ground_truth.txt'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Saved -> {out_path}")
    print(f"\nKey result: {total_real}/{total_in_range} REAL catches ({100*total_real/max(total_in_range,1):.1f}%)")
    print(f"            {total_phantom}/{total_in_range} PHANTOM  ({100*total_phantom/max(total_in_range,1):.1f}%)")


if __name__ == '__main__':
    run()
