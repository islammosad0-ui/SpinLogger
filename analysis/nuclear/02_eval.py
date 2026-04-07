"""
Nuclear analysis evaluation framework.

Provides simulate() — given a strategy and a list of gaps, returns:
  caught       : number of gaps where the ending triple landed inside a BET window
  total_gaps   : total gaps evaluated
  bet_spins    : total spins where strategy said BET
  total_spins  : total spins across all gaps
  bet_pct      : bet_spins / total_spins
  mb_per_hit   : mean bets per hit (efficiency — lower is better)
  lift         : (caught/bet_spins) / (total_gaps/total_spins) — multiplicative
                 advantage over random betting
  catch_rate   : caught / total_gaps

A "strategy" is a callable that takes a list of per-spin records (the gap
trajectory up to and including the current spin) and returns True if we BET on
the current spin. The strategy receives the trajectory as a list because some
strategies need to look at the most recent N spins, slope, etc. For efficiency
we slice the trajectory once per gap and pass it incrementally.

We also support "factory" strategies — callables that take config and return a
strategy. This enables sweeping.
"""
import pickle
from pathlib import Path

NUCLEAR_DIR = Path(__file__).parent
GAPS_PATH = NUCLEAR_DIR / 'gaps.pkl'


def load_gaps():
    with open(GAPS_PATH, 'rb') as f:
        return pickle.load(f)


def all_gaps_for(target, accounts=None):
    """Concat gaps across accounts. accounts=None means all 3."""
    data = load_gaps()
    out = []
    for acct, d in data.items():
        if accounts is None or acct in accounts:
            out.extend(d['gaps'].get(target, []))
    return out


def simulate(strategy_fn, gaps, ending_must_be_bet=True):
    """
    strategy_fn: callable(spin_record_list_so_far) -> bool
                 spin_record_list_so_far is the gap trajectory from start up
                 to and including the current spin.

    Returns dict of metrics.
    """
    caught = 0
    bet_spins = 0
    total_spins = 0
    total_gaps = len(gaps)

    for gap in gaps:
        traj = gap['trajectory']
        total_spins += len(traj)
        gap_caught = False
        # Walk every spin in trajectory, applying strategy
        for end_i in range(1, len(traj) + 1):
            so_far = traj[:end_i]
            bet = strategy_fn(so_far)
            if bet:
                bet_spins += 1
                if end_i == len(traj):
                    # The ending triple lands on this spin
                    gap_caught = True
        if gap_caught:
            caught += 1

    bet_pct = (bet_spins / total_spins) if total_spins else 0.0
    catch_rate = (caught / total_gaps) if total_gaps else 0.0
    base_rate = (total_gaps / total_spins) if total_spins else 0.0
    bet_hit_rate = (caught / bet_spins) if bet_spins else 0.0
    mb_per_hit = (bet_spins / caught) if caught else float('inf')
    lift = (bet_hit_rate / base_rate) if base_rate > 0 else 0.0

    return {
        'caught': caught,
        'total_gaps': total_gaps,
        'bet_spins': bet_spins,
        'total_spins': total_spins,
        'bet_pct': bet_pct,
        'catch_rate': catch_rate,
        'mb_per_hit': mb_per_hit,
        'lift': lift,
    }


def simulate_fast(decision_at_end_of_gap, gaps):
    """
    OPTIMIZED simulate for memoryless strategies that only depend on the
    counter values at each spin (not the full trajectory).

    decision_at_end_of_gap: callable(spin_record) -> bool

    This evaluates the predicate directly on each spin record, no slicing.
    Returns same metrics dict.
    """
    caught = 0
    bet_spins = 0
    total_spins = 0
    total_gaps = len(gaps)

    for gap in gaps:
        traj = gap['trajectory']
        total_spins += len(traj)
        gap_caught = False
        for i, spin in enumerate(traj):
            if decision_at_end_of_gap(spin):
                bet_spins += 1
                if i == len(traj) - 1:
                    gap_caught = True
        if gap_caught:
            caught += 1

    bet_pct = (bet_spins / total_spins) if total_spins else 0.0
    catch_rate = (caught / total_gaps) if total_gaps else 0.0
    base_rate = (total_gaps / total_spins) if total_spins else 0.0
    bet_hit_rate = (caught / bet_spins) if bet_spins else 0.0
    mb_per_hit = (bet_spins / caught) if caught else float('inf')
    lift = (bet_hit_rate / base_rate) if base_rate > 0 else 0.0

    return {
        'caught': caught,
        'total_gaps': total_gaps,
        'bet_spins': bet_spins,
        'total_spins': total_spins,
        'bet_pct': bet_pct,
        'catch_rate': catch_rate,
        'mb_per_hit': mb_per_hit,
        'lift': lift,
    }


def fmt_result(r):
    return (f"caught={r['caught']:3d}/{r['total_gaps']:3d}  "
            f"bet={r['bet_pct']*100:5.2f}%  "
            f"mb/hit={r['mb_per_hit']:6.1f}  "
            f"lift={r['lift']:5.2f}x")


# Sanity check
if __name__ == '__main__':
    gaps = all_gaps_for('accumulation')
    print(f"Total ACC gaps: {len(gaps)}")
    print(f"Total spins: {sum(len(g['trajectory']) for g in gaps)}")

    # Replicate FINDINGS baseline: 130/0.30
    def balanced_acc(spin):
        if spin['sa_spins'] < 130:
            return False
        if spin['sa_spins'] == 0:
            return False
        rate = spin['sa_acc'] / spin['sa_spins']
        return rate >= 0.30

    r = simulate_fast(balanced_acc, gaps)
    print(f"Baseline (130/0.30): {fmt_result(r)}")

    # SPN baseline
    spn_gaps = all_gaps_for('spins')
    print(f"\nTotal SPN gaps: {len(spn_gaps)}")

    def conservative_spn(spin):
        if spin['ss_spins'] < 87:
            return False
        if spin['ss_spins'] == 0:
            return False
        rate = spin['ss_spn'] / spin['ss_spins']
        return rate >= 0.25

    r = simulate_fast(conservative_spn, spn_gaps)
    print(f"SPN Conservative (87/0.25): {fmt_result(r)}")
