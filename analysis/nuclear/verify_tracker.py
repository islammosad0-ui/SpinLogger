"""
Verification: Python mirror of the Objective-C SLDebtTracker logic.
Should produce 63/178 catches @ 10.49 mb/hit on gaps.pkl, matching the
locked-in ensemble result. If it doesn't match, the Objective-C tracker
has a bug.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import pickle
from pathlib import Path

GAPS_PATH = Path(__file__).parent / 'gaps.pkl'

# ============================================================================
# Mirror of SLDebtRule
# ============================================================================
class Rule:
    def __init__(self, name, bit_index):
        self.name = name
        self.bit_index = bit_index
        self.spin_threshold = 999
        self.rate_gate = 0.0
        self.spn_rate_gate = 0.0
        self.min_slope = 0.0
        self.slope_window = 10
        self.sml_s_bound = 0
        self.sml_s_threshold = 0
        self.sml_s_gate = 0.0
        self.sml_l_bound = 0
        self.sml_l_threshold = 0
        self.sml_l_gate = 0.0
        self.required_prev_triple = ""

# ============================================================================
# Build the 16-rule ensemble (mirror of accEnsembleDefaults)
# ============================================================================
def build_ensemble():
    rules = []
    # 1: COMBO
    r = Rule("COMBO", 0)
    r.spin_threshold = 110; r.rate_gate = 0.28; r.spn_rate_gate = 0.20
    r.min_slope = 0.010; r.slope_window = 10
    rules.append(r)
    # 2: Ideal RA
    r = Rule("Ideal RA", 1)
    r.spin_threshold = 110; r.rate_gate = 0.30
    r.min_slope = 0.006; r.slope_window = 8
    rules.append(r)
    # 3: RA t130
    r = Rule("RA t130", 2)
    r.spin_threshold = 130; r.rate_gate = 0.28
    r.min_slope = 0.010; r.slope_window = 10
    rules.append(r)
    # 4: FLAT 150/0.32
    r = Rule("FLAT 150/0.32", 3)
    r.spin_threshold = 150; r.rate_gate = 0.32
    rules.append(r)
    # 5: SML L>=120 g=0.32
    r = Rule("SML L>=120 g=0.32", 4)
    r.spin_threshold = 999; r.rate_gate = 0.32
    r.sml_l_bound = 120; r.sml_l_threshold = 130; r.sml_l_gate = 0.32
    rules.append(r)
    # 6: SML L>=120 g=0.30
    r = Rule("SML L>=120 g=0.30", 5)
    r.spin_threshold = 999; r.rate_gate = 0.30
    r.sml_l_bound = 120; r.sml_l_threshold = 130; r.sml_l_gate = 0.30
    rules.append(r)
    # 7: SML S100 L120 tM=180
    r = Rule("SML S100 L120 tM=180", 6)
    r.spin_threshold = 180; r.rate_gate = 0.32
    r.sml_s_bound = 100; r.sml_s_threshold = 150; r.sml_s_gate = 0.32
    r.sml_l_bound = 120; r.sml_l_threshold = 130; r.sml_l_gate = 0.32
    rules.append(r)
    # 8: SML S100 L120 tM=110
    r = Rule("SML S100 L120 tM=110", 7)
    r.spin_threshold = 110; r.rate_gate = 0.32
    r.sml_s_bound = 100; r.sml_s_threshold = 150; r.sml_s_gate = 0.32
    r.sml_l_bound = 120; r.sml_l_threshold = 130; r.sml_l_gate = 0.32
    rules.append(r)
    # 9: SML S100 L130 tM=130
    r = Rule("SML S100 L130 tM=130", 8)
    r.spin_threshold = 130; r.rate_gate = 0.32
    r.sml_s_bound = 100; r.sml_s_threshold = 150; r.sml_s_gate = 0.32
    r.sml_l_bound = 130; r.sml_l_threshold = 100; r.sml_l_gate = 0.32
    rules.append(r)
    # 10: SML S50 L130 tM=150
    r = Rule("SML S50 L130 tM=150", 9)
    r.spin_threshold = 150; r.rate_gate = 0.32
    r.sml_s_bound = 50; r.sml_s_threshold = 100; r.sml_s_gate = 0.32
    r.sml_l_bound = 130; r.sml_l_threshold = 100; r.sml_l_gate = 0.32
    rules.append(r)
    # 11: SML S50 L130 tS=80
    r = Rule("SML S50 L130 tS=80", 10)
    r.spin_threshold = 150; r.rate_gate = 0.32
    r.sml_s_bound = 50; r.sml_s_threshold = 80; r.sml_s_gate = 0.32
    r.sml_l_bound = 130; r.sml_l_threshold = 100; r.sml_l_gate = 0.32
    rules.append(r)
    # 12-15: SHIELD-cond
    for i, t in enumerate([110, 120, 130, 140]):
        r = Rule(f"SHIELD-cond {t}/0.32", 11+i)
        r.spin_threshold = t; r.rate_gate = 0.32
        r.required_prev_triple = "shield"
        rules.append(r)
    # 16: FLAT 150/0.37
    r = Rule("FLAT 150/0.37", 15)
    r.spin_threshold = 150; r.rate_gate = 0.37
    rules.append(r)
    return rules

# ============================================================================
# Mirror of SLDebtTracker
# ============================================================================
SLOPE_MAX = 20
COOLDOWN_AFTER = 8
COOLDOWN_LEN = 3

class Tracker:
    def __init__(self, rules):
        self.rules = rules
        self.reset()

    def reset(self):
        self.sa_spins = 0
        self.sa_acc = 0
        self.sa_spn = 0
        self.prev_gap_length = -1
        self.prev_real_triple = None
        self.consec_bets = 0
        self.cooldown_remaining = 0
        self.gap_bet_count = 0
        self.rate_history = [0.0] * (SLOPE_MAX + 1)

    def acc_rate(self):
        return self.sa_acc / self.sa_spins if self.sa_spins > 0 else 0.0

    def spn_rate(self):
        return self.sa_spn / self.sa_spins if self.sa_spins > 0 else 0.0

    def slope_for_window(self, win):
        if win <= 0 or win > SLOPE_MAX: return 0.0
        if self.sa_spins <= win: return 0.0
        rate_now = self.acc_rate()
        rate_prev = self.rate_history[(self.sa_spins - win) % (SLOPE_MAX + 1)]
        return rate_now - rate_prev

    def resolve_rule(self, r):
        """Returns (eligible, threshold, gate)."""
        if r.required_prev_triple:
            if self.prev_real_triple != r.required_prev_triple:
                return False, 0, 0.0
        thresh = r.spin_threshold
        gate = r.rate_gate
        if r.sml_s_bound > 0 and self.prev_gap_length >= 0 and self.prev_gap_length < r.sml_s_bound:
            thresh = r.sml_s_threshold
            gate = r.sml_s_gate
        elif r.sml_l_bound > 0 and self.prev_gap_length >= 0 and self.prev_gap_length >= r.sml_l_bound:
            thresh = r.sml_l_threshold
            gate = r.sml_l_gate
        if thresh >= 999:
            return False, 0, 0.0
        return True, thresh, gate

    def evaluate_rule(self, r):
        ok, thresh, gate = self.resolve_rule(r)
        if not ok: return False
        if self.sa_spins < thresh: return False
        if gate > 0.0 and self.acc_rate() < gate: return False
        if r.spn_rate_gate > 0.0 and self.spn_rate() < r.spn_rate_gate: return False
        if r.min_slope > 0.0 and self.slope_for_window(r.slope_window) < r.min_slope: return False
        return True

    def on_spin(self, is_target, real_triple_type, primary, secondary):
        """Returns 'BET' if bet was placed, else None.
        Rules are evaluated BEFORE the reset on target triples — so a bet placed
        on the catch spin counts as a successful catch."""
        self.sa_spins += 1
        self.sa_acc += primary
        self.sa_spn += secondary

        if self.sa_spins > 0:
            self.rate_history[self.sa_spins % (SLOPE_MAX + 1)] = self.sa_acc / self.sa_spins

        # Update prev_real_triple BEFORE evaluating rules so non-target triples on
        # this spin can be used by SHIELD-cond rules immediately. (Target triples
        # update prev_real_triple in the reset block below.)
        if real_triple_type and not is_target:
            self.prev_real_triple = real_triple_type

        bet_placed = False

        # Cooldown takes priority
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            self.consec_bets = 0
        else:
            n_firing = sum(1 for r in self.rules if self.evaluate_rule(r))
            if n_firing > 0:
                bet_placed = True
                self.consec_bets += 1
                self.gap_bet_count += 1
                if COOLDOWN_AFTER > 0 and self.consec_bets >= COOLDOWN_AFTER:
                    self.cooldown_remaining = COOLDOWN_LEN
            else:
                self.consec_bets = 0

        # Now handle target triple reset (AFTER rule evaluation so the catch is recorded)
        if is_target:
            self.prev_gap_length = self.sa_spins
            self.prev_real_triple = real_triple_type
            self.sa_spins = 0
            self.sa_acc = 0
            self.sa_spn = 0
            self.consec_bets = 0
            self.cooldown_remaining = 0
            self.gap_bet_count = 0
            self.rate_history = [0.0] * (SLOPE_MAX + 1)

        return 'BET' if bet_placed else None

# ============================================================================
# Run on gaps.pkl
# ============================================================================
def main():
    with open(GAPS_PATH, 'rb') as f:
        data = pickle.load(f)

    rules = build_ensemble()
    print(f"Built ensemble with {len(rules)} rules")

    total_caught = 0
    total_bets = 0
    total_gaps = 0
    per_account = {}

    # Skip first gap of each account — it has pre-CSV history that the live tracker
    # can't replicate (the slope buffer would be unpopulated). The simulator includes
    # them but they contribute 0 catches and 0 bets (verified earlier — too short).
    SKIP_FIRST_GAP = True

    for acct in ['Islam', 'Ahmed', 'Nick']:
        gaps = data[acct]['gaps'].get('accumulation', [])
        tracker = Tracker(rules)

        acct_caught = 0
        acct_bets = 0

        start_idx = 1 if SKIP_FIRST_GAP else 0
        # If we're skipping the first gap, we still need to set prev_gap_length
        # and prev_real_triple from it (these are passed to the next gap by the
        # simulator implicitly via the loader).
        if SKIP_FIRST_GAP and len(gaps) > 0:
            tracker.prev_gap_length = gaps[0]['length']
            # The prev_real_triple for the SECOND gap is the type of the FIRST triple — accumulation
            tracker.prev_real_triple = 'accumulation'

        for gi in range(start_idx, len(gaps)):
            gap = gaps[gi]
            traj = gap['trajectory']
            for i, spin in enumerate(traj):
                is_acc = (spin.get('triple') == 'accumulation')
                real_triple = spin.get('triple') or None
                primary = spin.get('acc_count', 0)
                secondary = spin.get('spn_count', 0)

                result = tracker.on_spin(is_acc, real_triple, primary, secondary)
                if result == 'BET':
                    acct_bets += 1
                    if i == len(traj) - 1:
                        acct_caught += 1

        per_account[acct] = (acct_caught, len(gaps) - start_idx, acct_bets)
        total_caught += acct_caught
        total_gaps += (len(gaps) - start_idx)
        total_bets += acct_bets

    print(f"\n(Skipping first gap of each account — they had 0 catches in simulator anyway)")
    expected_catches = 63
    expected_bets = 661

    print(f"\nTOTAL: {total_caught}/{total_gaps} catches, {total_bets} bets, mb/hit={total_bets/max(total_caught,1):.2f}")
    print(f"Expected (simulation): 63/178 catches, 661 bets, mb/hit=10.49")
    print()
    for acct, (c, g, b) in per_account.items():
        print(f"  {acct}: {c}/{g} catches, {b} bets")
    print()
    if total_caught == 63 and total_bets == 661:
        print("PERFECT MATCH! Tracker logic is correct.")
    else:
        delta_c = total_caught - 63
        delta_b = total_bets - 661
        print(f"DELTA from expected: catches {delta_c:+d}, bets {delta_b:+d}")

if __name__ == '__main__':
    main()
