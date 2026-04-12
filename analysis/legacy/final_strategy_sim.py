"""
FINAL STRATEGY SIMULATION — 110% threshold + recent triple gate
Replay every spin exactly as the tool would process it.
Show every gap in detail.
"""
import csv, statistics
from collections import Counter

def load_csv(path):
    rows = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row['r1'] = int(row['r1'])
            row['r2'] = int(row['r2'])
            row['r3'] = int(row['r3'])
            row['is_triple'] = row['is_triple'].lower() == 'true'
            row['tuple'] = (row['r1'], row['r2'], row['r3'])
            row['reel1'] = row['reel_1']
            row['bet_multiplier'] = int(row['bet_multiplier'])
            rows.append(row)
    return rows

COMBAT = {'attack', 'steal', 'shield', 'spins'}

class FinalStrategy:
    """
    110% threshold + recent-triple gate.

    Logic:
    - Track running median of gaps (auto-calibrates)
    - WAIT: sa_spins < median * 0.7
    - ALERT: sa_spins >= median * 0.7 AND < median * 1.1
    - BET: sa_spins >= median * 1.1 AND saw a non-ACC triple in last 3 spins
    - WATCH: sa_spins >= median * 1.1 but no recent triple (pause betting)
    """
    def __init__(self):
        self.target = 100
        self.sa_spins = 0
        self.phase = 'WAIT'
        self.gap_history = []
        self.calibrated = False
        self.cal_threshold = 5
        self.catches = 0
        self.misses = 0
        self.total_bet_spins = 0
        self.debt = 0
        self.last_3_triples = []  # track if any of last 3 spins was non-ACC triple

    def on_spin(self, spin):
        is_triple = spin['is_triple']
        is_acc = is_triple and spin['reel1'] == 'accumulation'
        is_other_triple = is_triple and not is_acc

        self.sa_spins += 1

        # Track recent non-ACC triples
        self.last_3_triples.append(is_other_triple)
        if len(self.last_3_triples) > 3:
            self.last_3_triples.pop(0)

        if is_acc:
            gap = self.sa_spins
            self.gap_history.append(gap)

            if self.calibrated:
                if self.phase == 'BET':
                    self.catches += 1
                else:
                    self.misses += 1
                self.debt += (gap - self.target)

            if len(self.gap_history) >= self.cal_threshold:
                sorted_gaps = sorted(self.gap_history)
                mid = len(sorted_gaps) // 2
                if len(sorted_gaps) % 2 == 0:
                    self.target = (sorted_gaps[mid-1] + sorted_gaps[mid]) // 2
                else:
                    self.target = sorted_gaps[mid]
                if not self.calibrated:
                    self.calibrated = True
                    self.debt = 0

            self.sa_spins = 0
            self.last_3_triples = []
            self.phase = 'WAIT'
            return

        if not self.calibrated:
            return

        threshold = int(self.target * 1.1)
        alert_point = int(self.target * 0.7)
        has_recent_triple = any(self.last_3_triples)

        if self.sa_spins >= threshold and has_recent_triple:
            self.phase = 'BET'
            self.total_bet_spins += 1
        elif self.sa_spins >= threshold:
            self.phase = 'WATCH'  # past threshold but waiting for triple trigger
        elif self.sa_spins >= alert_point:
            self.phase = 'ALERT'
        else:
            self.phase = 'WAIT'


acc1 = load_csv(r"C:\Users\Islam\Downloads\Account 1 spin_history_2026-04-05.csv")
acc2 = load_csv(r"C:\Users\Islam\Downloads\Account 2 spin_history_2026-04-04.csv")

for name, data in [("Account 1 (6450 spins, mission 66/70)", acc1),
                    ("Account 2 (4968 spins, mission 37)", acc2)]:
    print("=" * 95)
    print(f"  {name}")
    print("=" * 95)

    total_acc = sum(1 for r in data if r['tuple'] == (30, 30, 30))

    strat = FinalStrategy()
    # Detailed trace
    gap_num = 0
    bet_start = None
    gap_bet_spins = 0
    gap_details = []

    for i, spin in enumerate(data):
        was_phase = strat.phase
        strat.on_spin(spin)

        if strat.phase == 'BET' and was_phase != 'BET':
            bet_start = i

        if spin['tuple'] == (30, 30, 30):
            if strat.calibrated or len(strat.gap_history) == strat.cal_threshold:
                gap_num += 1
                gap_len = strat.gap_history[-1]
                result = "CAUGHT" if was_phase == 'BET' else "MISSED"
                # Count bet spins in this gap
                gap_details.append({
                    'num': gap_num,
                    'gap': gap_len,
                    'result': result,
                    'target_during': strat.target,  # target AFTER update
                    'bet_multi': spin['bet_multiplier']
                })
            bet_start = None

    # Print all gaps
    print(f"\n  Total ACC triples: {total_acc}")
    print(f"  Calibration used first {strat.cal_threshold} gaps, then tracking started\n")
    print(f"  {'Gap#':>5} {'Length':>7} {'Result':>8} {'Target':>7} {'Bet':>5}")
    print(f"  {'-'*40}")

    caught_gaps = []
    missed_gaps = []
    for g in gap_details:
        marker = " ***" if g['result'] == 'CAUGHT' else ""
        bet_str = f"{g['bet_multi']}x" if g['bet_multi'] > 1 else "1x"
        print(f"  {g['num']:>5} {g['gap']:>7} {g['result']:>8} {g['target_during']:>7} {bet_str:>5}{marker}")
        if g['result'] == 'CAUGHT':
            caught_gaps.append(g['gap'])
        else:
            missed_gaps.append(g['gap'])

    # Summary
    total = strat.catches + strat.misses
    print(f"\n  {'='*50}")
    print(f"  RESULTS:")
    print(f"    Caught:     {strat.catches}/{total} ({strat.catches/total*100:.1f}%)")
    print(f"    Missed:     {strat.misses}/{total}")
    print(f"    Bet spins:  {strat.total_bet_spins}")
    print(f"    Spins/hit:  {strat.total_bet_spins/strat.catches:.1f}" if strat.catches > 0 else "")
    print(f"    Final target: {strat.target}")
    print(f"    Final debt: {strat.debt:+d}")

    if caught_gaps:
        print(f"\n  CAUGHT gaps: mean={statistics.mean(caught_gaps):.0f}, "
              f"median={statistics.median(caught_gaps):.0f}, "
              f"range={min(caught_gaps)}-{max(caught_gaps)}")
    if missed_gaps:
        print(f"  MISSED gaps: mean={statistics.mean(missed_gaps):.0f}, "
              f"median={statistics.median(missed_gaps):.0f}, "
              f"range={min(missed_gaps)}-{max(missed_gaps)}")

    # Per-gap bet spin breakdown for caught ones
    print(f"\n  BET SPIN DETAIL (caught gaps only):")
    print(f"    Gap length - threshold = bet spins burned")
    for g in gap_details:
        if g['result'] == 'CAUGHT':
            # threshold during this gap was ~target*1.1 but target was set AFTER
            # We approximate: bet spins = gap - threshold (roughly)
            approx_bet = max(0, g['gap'] - int(g['target_during'] * 1.0))  # rough
            print(f"    Gap {g['num']:>3}: {g['gap']:>4} spins, ~{approx_bet:>3} at max bet")

    print()
