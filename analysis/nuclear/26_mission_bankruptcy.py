"""
Mission ladder bankruptcy simulator.

Walk through Islam's actual spins, picking bets via 5 strategies.
Each pull:
  - cost = strategy-chosen bet (deducted from bankroll, in spin units)
  - points = acc_count * bet, or 10 * bet on accumulation triple
Cascading mission completion: overflow points carry to next mission.
Bankrupt when bankroll < next bet.

Bet menu: 1, 2, 3, 15, 50, 400, 1500, 6000, 20000

Two scenarios:
  A) start 100K spins, screenshot-1 ladder  (22 missions, top reward 650K)
  B) start 299K spins, screenshot-2 ladder  (20 missions, top reward 2.1M)
"""
import pickle
from collections import deque

PKL = 'analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)

# ---------------------------------------------------------------------------
# Mission ladders (each row = independent mission, overflow cascades)
# ---------------------------------------------------------------------------
LADDER_A = [
    (7,        120),
    (90,       200),
    (225,      800),
    (800,      1700),
    (1200,     3100),
    (2400,     6000),
    (4800,     11000),
    (10000,    20000),
    (20000,    40000),
    (30000,    60000),
    (45000,    85000),
    (70000,    125000),
    (100000,   175000),
    (150000,   250000),
    (200000,   300000),
    (250000,   350000),
    (300000,   400000),
    (350000,   450000),
    (400000,   500000),
    (450000,   550000),
    (500000,   600000),
    (550000,   650000),
]

LADDER_B = [
    (1500,     1100),
    (3000,     2700),
    (8500,     8100),
    (18000,    19000),
    (24000,    27000),
    (36000,    46000),
    (51000,    68000),
    (75000,    107500),
    (105000,   162500),
    (150000,   230000),
    (225000,   337500),
    (300000,   472500),
    (450000,   540000),
    (600000,   675000),
    (750000,   810000),
    (1050000,  1000000),
    (1200000,  1200000),
    (1500000,  1400000),
    (1700000,  1800000),
    (2100000,  2100000),
]

HAMMER_LADDER = [(15, 25), (50, 50), (400, 75), (1500, 93), (6000, None)]
ENSEMBLE_BUMP_BET = 6000

# ---------------------------------------------------------------------------
# v5 7-rule causal ensemble (mirror of src/SLDebtTracker.m)
# ---------------------------------------------------------------------------
def gap_class(L):
    if L is None: return 'NONE'
    if L <= 39:   return 'XS'
    if L <= 105:  return 'S'
    if L <= 160:  return 'M'
    return 'L'

def rule_steal_t65(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if not (65 <= sp <= 105): return False
    return (s['sa_acc']/sp) >= 0.34

def rule_steal_t130(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if sp < 130 or sp == 0: return False
    return (s['sa_acc']/sp) >= 0.28

def rule_steal_t150(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if sp < 150 or sp == 0: return False
    return (s['sa_acc']/sp) >= 0.30

def rule_shield_t150(s):
    if s['prev_real_triple'] != 'shield': return False
    sp = s['sa_spins']
    if sp < 150 or sp == 0: return False
    return (s['sa_acc']/sp) >= 0.30

def rule_quiet_zone(s):
    sp = s['sa_spins']
    if sp < 130: return False
    return s['last10_sum'] <= 10

def rule_dg_t130(s):
    sp = s['sa_spins']
    if not (130 <= sp <= 155): return False
    if (s['sa_acc']/sp) < 0.28: return False
    return (s['sa_spn']/sp) >= 0.24

def rule_early_s(s):
    cls = gap_class(s['prev_gap_length'])
    if cls not in ('M', 'L'): return False
    sp = s['sa_spins']
    if not (60 <= sp <= 105): return False
    return s['last10_sum'] <= 10

ENSEMBLE_RULES = [rule_steal_t65, rule_steal_t130, rule_steal_t150,
                  rule_shield_t150, rule_quiet_zone, rule_dg_t130, rule_early_s]

def ensemble_fires(state):
    return any(r(state) for r in ENSEMBLE_RULES)


# ---------------------------------------------------------------------------
# Core simulator
# ---------------------------------------------------------------------------
def simulate(bankroll0, ladder, strategy, account='Islam', max_pulls=20_000_000):
    spins = data[account]['spins']
    n = len(spins)

    bankroll      = bankroll0
    mission_idx   = 0
    mission_pts   = 0       # current mission's running point total
    pulls         = 0
    cost_total    = 0
    points_total  = 0
    rewards_total = 0
    bumps         = 0       # ensemble fires (or hybrid bumps)

    # Hammer round state
    hammer_level  = 0
    hammers       = 0

    # Cross-spin state for ensemble
    prev_real_triple = None
    prev_gap_length  = None
    last10 = deque(maxlen=10)

    data_idx     = 0
    bankrupt_at  = None     # which mission was active when we ran out

    while True:
        s = spins[data_idx % n]
        data_idx += 1

        # Build state for ensemble rules
        sym_total = (s['atk_count'] + s['stl_count'] + s['shd_count']
                     + s['spn_count'] + s['acc_count'])
        state = {
            'sa_spins':         s['sa_spins'],
            'sa_acc':           s['sa_acc'],
            'sa_spn':           s['sa_spn'],
            'prev_real_triple': prev_real_triple,
            'prev_gap_length':  prev_gap_length,
            'last10_sum':       sum(last10),
        }
        fires = ensemble_fires(state)

        # Strategy picks bet
        if strategy == 'pure_1x':
            bet = 1
        elif strategy == 'pure_6000x':
            bet = 6000
        elif strategy == 'pure_hammer':
            bet = HAMMER_LADDER[hammer_level][0]
        elif strategy == 'pure_ensemble':
            bet = ENSEMBLE_BUMP_BET if fires else 1
        elif strategy == 'hybrid':
            base = HAMMER_LADDER[hammer_level][0]
            bet = max(base, ENSEMBLE_BUMP_BET) if fires else base
        else:
            raise ValueError(strategy)

        # Bankrupt check BEFORE the pull
        if bankroll < bet:
            bankrupt_at = mission_idx
            break

        # Pull the lever
        bankroll  -= bet
        cost_total += bet
        pulls     += 1
        if fires:
            bumps += 1

        # Earn points
        if s.get('triple') == 'accumulation':
            pts = 10 * bet
        else:
            pts = s['acc_count'] * bet
        points_total += pts
        mission_pts  += pts

        # Cascading mission completion
        while mission_idx < len(ladder) and mission_pts >= ladder[mission_idx][0]:
            thresh, reward = ladder[mission_idx]
            mission_pts  -= thresh
            bankroll     += reward
            rewards_total += reward
            mission_idx  += 1

        if mission_idx >= len(ladder):
            bankrupt_at = None
            break

        # Update Hammer round state
        hammers += s['atk_count']
        if hammer_level < len(HAMMER_LADDER) - 1:
            if hammers >= HAMMER_LADDER[hammer_level][1]:
                hammer_level += 1

        # Cross-spin state for ensemble
        last10.append(sym_total)
        if s['triple'] is not None:
            prev_real_triple = s['triple']
        if s['triple'] == 'accumulation':
            prev_gap_length = s['sa_spins']
            hammer_level = 0
            hammers = 0

        if pulls >= max_pulls:
            bankrupt_at = mission_idx
            break

    return {
        'strategy':         strategy,
        'bankroll0':        bankroll0,
        'pulls':            pulls,
        'cost_total':       cost_total,
        'points_total':     points_total,
        'rewards_total':    rewards_total,
        'bumps':            bumps,
        'missions_cleared': mission_idx,
        'missions_total':   len(ladder),
        'final_bankroll':   bankroll,
        'final_mission_pts': mission_pts,
        'next_threshold':   ladder[mission_idx][0] if mission_idx < len(ladder) else None,
        'cleared_all':      mission_idx >= len(ladder),
        'data_cycles':      data_idx / n,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def report(r, ladder):
    label = {
        'pure_1x':       'Pure 1x',
        'pure_6000x':    'Pure 6000x',
        'pure_hammer':   'Pure Hammer',
        'pure_ensemble': 'Pure Ensemble',
        'hybrid':        'HYBRID',
    }[r['strategy']]
    status = 'CLEARED ALL' if r['cleared_all'] else 'BANKRUPT'
    pct = (r['final_mission_pts'] / r['next_threshold'] * 100) if r['next_threshold'] else 0
    line1 = '  {:<14s}  {}  missions={:>2}/{}  pulls={:>10,}  cost={:>14,}'.format(
        label, status, r['missions_cleared'], r['missions_total'],
        r['pulls'], r['cost_total'])
    line2 = '  {:<14s}  rewards_won={:>14,}  final_bankroll={:>10,}  data_cycles={:.1f}'.format(
        '', r['rewards_total'], r['final_bankroll'], r['data_cycles'])
    line3 = ''
    if not r['cleared_all']:
        line3 = '  {:<14s}  stuck on mission {}: {:,} / {:,} pts ({:.1f}%) when bankroll ran out'.format(
            '', r['missions_cleared']+1, int(r['final_mission_pts']),
            r['next_threshold'], pct)
    elif r['cleared_all']:
        line3 = '  {:<14s}  >>> ALL {} MISSIONS CLEARED, walked away with {:,} spins <<<'.format(
            '', r['missions_total'], r['final_bankroll'])
    print(line1)
    print(line2)
    if line3:
        print(line3)
    print()


ACCOUNTS = ['Islam', 'Ahmed', 'Nick']
STRATEGIES = ['pure_1x', 'pure_6000x', 'pure_hammer', 'pure_ensemble', 'hybrid']

def run_scenario(name, bankroll0, ladder):
    print('=' * 96)
    print('  SCENARIO {}: start {:,} spins  |  ladder = {} missions  |  top reward = {:,}'.format(
        name, bankroll0, len(ladder), ladder[-1][1]))
    print('=' * 96)

    summary = {}  # acct -> { strategy -> r }

    for acct in ACCOUNTS:
        n_spins = len(data[acct]['spins'])
        print('--- {} (data: {:,} spins) ---'.format(acct, n_spins))
        summary[acct] = {}
        for strategy in STRATEGIES:
            r = simulate(bankroll0, ladder, strategy, account=acct)
            summary[acct][strategy] = r
            report(r, ladder)
        print()

    # Compact comparison table
    print('  COMPACT COMPARISON  (missions cleared / next-mission % progress)')
    header = '  {:<14s}'.format('strategy')
    for acct in ACCOUNTS:
        header += '  {:>18s}'.format(acct)
    print(header)
    print('  ' + '-' * (14 + 20 * len(ACCOUNTS)))
    for strategy in STRATEGIES:
        label = {
            'pure_1x':       'Pure 1x',
            'pure_6000x':    'Pure 6000x',
            'pure_hammer':   'Pure Hammer',
            'pure_ensemble': 'Pure Ensemble',
            'hybrid':        'HYBRID',
        }[strategy]
        row = '  {:<14s}'.format(label)
        for acct in ACCOUNTS:
            r = summary[acct][strategy]
            if r['cleared_all']:
                cell = '{}/{} CLEAR'.format(r['missions_cleared'], r['missions_total'])
            else:
                pct = (r['final_mission_pts'] / r['next_threshold'] * 100) if r['next_threshold'] else 0
                cell = '{}/{}  ({:.0f}%)'.format(r['missions_cleared'], r['missions_total'], pct)
            row += '  {:>18s}'.format(cell)
        print(row)
    print()
    return summary


print('=' * 96)
print('MISSION LADDER BANKRUPTCY SIM  —  Coin Master 10er Symbol event')
print('  cost-per-pull = bet  |  points = acc_count * bet  (10 * bet on triple)')
print('  cascading mission completion (overflow carries forward)')
print('  data: per-account spin history, cycling, v5 7-rule causal ensemble')
print('=' * 96)
print()

run_scenario('A', 100_000, LADDER_A)
print()
run_scenario('B', 299_000, LADDER_B)
