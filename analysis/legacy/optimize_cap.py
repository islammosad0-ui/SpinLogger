"""
Find the optimal bet window cap + threshold combo.
Goal: minimize bet spins per hit while keeping decent catch rate.
"""
import csv, statistics
from collections import defaultdict

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
            rows.append(row)
    return rows

COMBAT = {'attack', 'steal', 'shield', 'spins'}

class Strategy:
    """Threshold + optional bet cap + optional re-trigger."""
    def __init__(self, threshold_pct=1.0, bet_cap=0, retrigger=False):
        self.threshold_pct = threshold_pct
        self.bet_cap = bet_cap          # 0 = unlimited
        self.retrigger = retrigger      # if True, re-enter BET after non-ACC triple past threshold
        self.target = 100
        self.sa_spins = 0
        self.phase = 'WAIT'
        self.gap_history = []
        self.calibrated = False
        self.cal_threshold = 5
        self.catches = 0
        self.misses = 0
        self.total_bet_spins = 0
        self.bet_spins_in_window = 0
        self.bet_exhausted = False      # True = cap reached, waiting for re-trigger

    def on_spin(self, spin):
        is_triple = spin['is_triple']
        is_acc = is_triple and spin['reel1'] == 'accumulation'
        is_combat = is_triple and spin['reel1'] in COMBAT

        self.sa_spins += 1

        if is_acc:
            gap = self.sa_spins
            self.gap_history.append(gap)
            if self.calibrated:
                if self.phase == 'BET':
                    self.catches += 1
                else:
                    self.misses += 1
            if len(self.gap_history) >= self.cal_threshold:
                sorted_gaps = sorted(self.gap_history)
                mid = len(sorted_gaps) // 2
                if len(sorted_gaps) % 2 == 0:
                    self.target = (sorted_gaps[mid-1] + sorted_gaps[mid]) // 2
                else:
                    self.target = sorted_gaps[mid]
                if not self.calibrated:
                    self.calibrated = True
            self.sa_spins = 0
            self.phase = 'WAIT'
            self.bet_spins_in_window = 0
            self.bet_exhausted = False
            return

        if not self.calibrated:
            return

        threshold = int(self.target * self.threshold_pct)

        if self.sa_spins < threshold:
            self.phase = 'WAIT'
            return

        # Past threshold
        if self.bet_cap == 0:
            # Unlimited
            self.phase = 'BET'
            self.total_bet_spins += 1
            return

        # Capped mode
        if self.bet_exhausted:
            if self.retrigger and is_combat:
                # Re-trigger: non-ACC triple resets the window
                self.bet_exhausted = False
                self.bet_spins_in_window = 0
                self.phase = 'BET'
                self.total_bet_spins += 1
                self.bet_spins_in_window += 1
            else:
                self.phase = 'WATCH'
        elif self.bet_spins_in_window < self.bet_cap:
            self.phase = 'BET'
            self.total_bet_spins += 1
            self.bet_spins_in_window += 1
            if self.bet_spins_in_window >= self.bet_cap:
                self.bet_exhausted = True
        else:
            self.phase = 'WATCH'

acc1 = load_csv(r"C:\Users\Islam\Downloads\Account 1 spin_history_2026-04-05.csv")
acc2 = load_csv(r"C:\Users\Islam\Downloads\Account 2 spin_history_2026-04-04.csv")

print("=" * 95)
print("OPTIMIZING: threshold % x bet cap x re-trigger")
print("=" * 95)

for name, data in [("Account 1", acc1), ("Account 2", acc2)]:
    print(f"\n{'='*95}")
    print(f"  {name}")
    print(f"{'='*95}")

    results = []

    for tpct in [0.8, 0.9, 1.0, 1.1, 1.2]:
        # Unlimited (current new strategy)
        s = Strategy(tpct, bet_cap=0)
        for spin in data: s.on_spin(spin)
        total = s.catches + s.misses
        if s.catches > 0 and total > 0:
            results.append((tpct, 'unlim', '-', s.catches, s.misses, total,
                           s.total_bet_spins, s.total_bet_spins / s.catches))

        # Capped without re-trigger
        for cap in [5, 8, 10, 15, 20, 30, 40]:
            s = Strategy(tpct, bet_cap=cap, retrigger=False)
            for spin in data: s.on_spin(spin)
            total = s.catches + s.misses
            if s.catches > 0 and total > 0:
                results.append((tpct, cap, 'no', s.catches, s.misses, total,
                               s.total_bet_spins, s.total_bet_spins / s.catches))

        # Capped WITH re-trigger (non-ACC triple resets window)
        for cap in [3, 5, 8, 10, 15]:
            s = Strategy(tpct, bet_cap=cap, retrigger=True)
            for spin in data: s.on_spin(spin)
            total = s.catches + s.misses
            if s.catches > 0 and total > 0:
                results.append((tpct, cap, 'yes', s.catches, s.misses, total,
                               s.total_bet_spins, s.total_bet_spins / s.catches))

    # Sort by spins/hit, then by catch rate
    results.sort(key=lambda r: (r[7], -r[3]))

    print(f"\n  {'Thresh':>6} {'Cap':>5} {'ReTrig':>6} {'Caught':>8} {'Miss':>6} "
          f"{'Catch%':>7} {'BetSpins':>9} {'Spins/Hit':>10}")
    print(f"  {'-'*70}")

    shown = set()
    for tpct, cap, retrig, caught, missed, total, bet_spins, sph in results:
        pct = caught / total * 100
        # Show top results + all unlimited for reference
        key = (tpct, cap, retrig)
        if len(shown) < 35 or cap == 'unlim':
            shown.add(key)
            marker = ""
            if cap == 'unlim':
                marker = "  (current)"
            elif sph < 25 and pct > 30:
                marker = "  ***"
            elif sph < 20 and pct > 20:
                marker = "  **"
            print(f"  {tpct:>5.0%} {str(cap):>5} {retrig:>6} {caught:>5}/{total:<5} "
                  f"{pct:>6.1f}% {bet_spins:>9} {sph:>10.1f}{marker}")

    # Find sweet spot
    print(f"\n  SWEET SPOTS (spins/hit < 25 AND catch% > 30%):")
    for tpct, cap, retrig, caught, missed, total, bet_spins, sph in results:
        pct = caught / total * 100
        if sph < 25 and pct > 30:
            print(f"    thresh={tpct:.0%} cap={cap} retrig={retrig}: "
                  f"{caught}/{total} ({pct:.1f}%) | {bet_spins} bet | {sph:.1f} spins/hit")

print(f"\n{'='*95}")
print("LEGEND:")
print("  Thresh = start BET at this % of running median")
print("  Cap = max consecutive BET spins before pausing (unlim = no cap)")
print("  ReTrig = after cap exhausted, does a non-ACC triple restart BET?")
print("  *** = sweet spot candidate")
print("=" * 95)
