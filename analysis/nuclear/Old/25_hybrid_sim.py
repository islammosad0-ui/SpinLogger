"""
Hybrid simulator: Hammer ladder + v5 7-rule causal ensemble (max-bet override).

VALUE MODEL (per Islam, 2026-04-08):
  - Each ACC symbol on the payline pays 1 * bet  (acc_count of 1 or 2)
  - ACC triple pays 10 * bet                     (acc_count == 3, bonus multiplier)
  Value accumulates ON EVERY SPIN, not just at the round-ending triple.
  This means strategies that bet higher on AVERAGE earn more partial-acc value
  too — you can't ignore the in-round drip.

Three strategies are simulated side-by-side on the same spin stream:
  1. PURE HAMMER     — Hammer ladder on every spin, ensemble ignored
  2. PURE ENSEMBLE   — bet MAX when any ensemble rule fires, base bet 1 otherwise
  3. HYBRID          — Hammer ladder always, BUT bumped to MAX whenever ensemble fires

The 7-rule v5 causal ensemble (mirror of src/SLDebtTracker.m accCausalDefaults):
  R1  STEAL t65  cap105 g0.34
  R2  STEAL t130        g0.28
  R3  STEAL t150        g0.30
  R4  SHIELD t150       g0.30
  R5  Quiet-zone last10<=10  t130
  R6  DG t130 cap155  acc0.28 spn0.24
  R7  prev=M/L early S window (sa_spins in [60,105], quietzone10<=10)

Gap class boundaries (from src/SLDebtTracker.h):
  XS: <=39    S: 40-105    M: 106-160    L: 161+
"""
import pickle
import os
from collections import deque

PKL = 'analysis/nuclear/gaps.pkl'
OUT_DIR = 'analysis/nuclear/strategy_sim'
os.makedirs(OUT_DIR, exist_ok=True)

with open(PKL, 'rb') as f:
    data = pickle.load(f)

# ---------------------------------------------------------------------------
# Strategy parameters
# ---------------------------------------------------------------------------
HAMMER_LADDER = [
    (15,    25),
    (50,    50),
    (400,   75),
    (1500,  93),
    (6000,  None),
]
HAMMER_BETS = [s[0] for s in HAMMER_LADDER]
ENSEMBLE_MAX_BET = 6000  # bet level used when ensemble fires

# Gap class boundaries
def gap_class(L):
    if L is None:    return 'NONE'
    if L <= 39:      return 'XS'
    if L <= 105:     return 'S'
    if L <= 160:     return 'M'
    return 'L'

# ---------------------------------------------------------------------------
# 7-rule causal ensemble — pure Python mirror of accCausalDefaults
# ---------------------------------------------------------------------------
# State the rules need (passed in via the `state` dict):
#   sa_spins, sa_acc, sa_spn — running counters from spin record
#   prev_real_triple — string ('steal', 'shield', etc.) or None
#   prev_gap_length — int or None
#   last10_sum — total symbol count in last 10 spins (atk+stl+shd+spn+acc)

def rule_steal_t65(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if not (65 <= sp <= 105): return False
    return (s['sa_acc'] / sp) >= 0.34

def rule_steal_t130(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if sp < 130 or sp == 0: return False
    return (s['sa_acc'] / sp) >= 0.28

def rule_steal_t150(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if sp < 150 or sp == 0: return False
    return (s['sa_acc'] / sp) >= 0.30

def rule_shield_t150(s):
    if s['prev_real_triple'] != 'shield': return False
    sp = s['sa_spins']
    if sp < 150 or sp == 0: return False
    return (s['sa_acc'] / sp) >= 0.30

def rule_quiet_zone(s):
    sp = s['sa_spins']
    if sp < 130: return False
    return s['last10_sum'] <= 10

def rule_dg_t130(s):
    sp = s['sa_spins']
    if not (130 <= sp <= 155): return False
    if (s['sa_acc'] / sp) < 0.28: return False
    return (s['sa_spn'] / sp) >= 0.24

def rule_early_s(s):
    cls = gap_class(s['prev_gap_length'])
    if cls not in ('M', 'L'): return False
    sp = s['sa_spins']
    if not (60 <= sp <= 105): return False
    return s['last10_sum'] <= 10

ENSEMBLE_RULES = [
    ('STEAL t65',     rule_steal_t65),
    ('STEAL t130',    rule_steal_t130),
    ('STEAL t150',    rule_steal_t150),
    ('SHIELD t150',   rule_shield_t150),
    ('Quiet-zone',    rule_quiet_zone),
    ('DG t130 cap',   rule_dg_t130),
    ('Early S',       rule_early_s),
]


# ---------------------------------------------------------------------------
# Per-account simulation
# ---------------------------------------------------------------------------
def acc_points(acc_count, bet):
    """Coin Master accumulator payout for this spin.
       1 acc on payline = 1*bet, 2 acc = 2*bet, triple acc = 10*bet."""
    if acc_count == 3:
        return 10 * bet
    return acc_count * bet


def simulate_account(acct):
    """Walk all spins for this account, simulating all 3 strategies in lockstep.
    Returns three lists of round dicts plus per-spin firing log."""
    spins = data[acct]['spins']
    by_session = {}
    for s in spins:
        by_session.setdefault(s.get('session_idx', 0), []).append(s)

    rounds_hm = []
    rounds_en = []
    rounds_hy = []
    rule_fires = {name: 0 for name, _ in ENSEMBLE_RULES}
    rule_catches = {name: 0 for name, _ in ENSEMBLE_RULES}

    for sidx in sorted(by_session.keys()):
        sess_spins = by_session[sidx]

        # Round-state for each strategy (carried across spins, reset on ACC triple)
        def new_round_hm():
            return {'spins':0,'cost':0,'value':0,'hammers':0,
                    'level_spins':[0]*len(HAMMER_LADDER),
                    'level_idx':0}
        def new_round_en():
            return {'spins':0,'cost':0,'value':0,'bet_spins':0,'fired_count':0,'session':sidx}
        def new_round_hy():
            return {'spins':0,'cost':0,'value':0,'hammers':0,'bumps':0,
                    'level_spins':[0]*len(HAMMER_LADDER),
                    'level_idx':0,'session':sidx}

        rh = new_round_hm(); rh['session'] = sidx
        re = new_round_en()
        ry = new_round_hy()

        # Cross-spin state for ensemble rules
        prev_real_triple = None
        prev_gap_length = None
        last10 = deque(maxlen=10)  # holds per-spin total symbol counts
        # First gap of each session is a partial — we drop those rounds at the end.

        for s in sess_spins:
            # Build the rule state from this spin
            sym_total = (s['atk_count'] + s['stl_count'] + s['shd_count']
                         + s['spn_count'] + s['acc_count'])
            state = {
                'sa_spins': s['sa_spins'],
                'sa_acc':   s['sa_acc'],
                'sa_spn':   s['sa_spn'],
                'prev_real_triple': prev_real_triple,
                'prev_gap_length':  prev_gap_length,
                'last10_sum': sum(last10),
            }

            # Evaluate ensemble rules
            fired = []
            for name, fn in ENSEMBLE_RULES:
                if fn(state):
                    fired.append(name)
            ensemble_fires = len(fired) > 0
            if ensemble_fires:
                for n in fired:
                    rule_fires[n] += 1

            acc_c = s['acc_count']

            # ----- Strategy 1: Pure Hammer -----
            hm_bet = HAMMER_LADDER[rh['level_idx']][0]
            rh['spins'] += 1
            rh['cost'] += hm_bet
            rh['value'] += acc_points(acc_c, hm_bet)
            rh['level_spins'][rh['level_idx']] += 1
            rh['hammers'] += s['atk_count']
            if rh['level_idx'] < len(HAMMER_LADDER) - 1:
                if rh['hammers'] >= HAMMER_LADDER[rh['level_idx']][1]:
                    rh['level_idx'] += 1

            # ----- Strategy 2: Pure Ensemble (bet=ENSEMBLE_MAX_BET on fire, bet=1 else) -----
            en_bet = ENSEMBLE_MAX_BET if ensemble_fires else 1
            re['spins'] += 1
            re['cost'] += en_bet
            re['value'] += acc_points(acc_c, en_bet)
            if ensemble_fires:
                re['bet_spins'] += 1
                re['fired_count'] += 1

            # ----- Strategy 3: Hybrid (Hammer base, ensemble override to MAX) -----
            hy_base_bet = HAMMER_LADDER[ry['level_idx']][0]
            hy_bet = max(hy_base_bet, ENSEMBLE_MAX_BET) if ensemble_fires else hy_base_bet
            ry['spins'] += 1
            ry['cost'] += hy_bet
            ry['value'] += acc_points(acc_c, hy_bet)
            ry['level_spins'][ry['level_idx']] += 1
            ry['hammers'] += s['atk_count']
            if ensemble_fires:
                ry['bumps'] += 1
            if ry['level_idx'] < len(HAMMER_LADDER) - 1:
                if ry['hammers'] >= HAMMER_LADDER[ry['level_idx']][1]:
                    ry['level_idx'] += 1

            # ----- Update cross-spin state AFTER bet decision -----
            last10.append(sym_total)

            # Triple events
            if s['triple'] is not None:
                prev_real_triple = s['triple']

            # ACC triple → round ends, record for all 3 strategies
            if s['triple'] == 'accumulation':
                rh['catch_bet'] = hm_bet
                rounds_hm.append(rh)

                re['catch_bet'] = en_bet
                re['catch_was_ensemble'] = ensemble_fires
                rounds_en.append(re)

                ry['catch_bet'] = hy_bet
                ry['catch_was_bump'] = ensemble_fires
                rounds_hy.append(ry)

                if ensemble_fires:
                    for n in fired:
                        rule_catches[n] += 1

                # Update prev_gap_length, reset rounds
                prev_gap_length = ry['spins']  # actual length of completed round
                rh = new_round_hm(); rh['session'] = sidx
                re = new_round_en()
                ry = new_round_hy()

        # End of session — drop the first round (we joined mid-round, ladder unknown)
        if rounds_hm: rounds_hm = rounds_hm[1:] if rounds_hm[0].get('session') == sidx else rounds_hm
        if rounds_en: rounds_en = rounds_en[1:] if rounds_en[0].get('session') == sidx else rounds_en
        if rounds_hy: rounds_hy = rounds_hy[1:] if rounds_hy[0].get('session') == sidx else rounds_hy

    return rounds_hm, rounds_en, rounds_hy, rule_fires, rule_catches


def summarize(label, rounds, ensemble=False):
    n = len(rounds)
    if n == 0:
        print('  {}: 0 rounds'.format(label))
        return
    spins = sum(r['spins'] for r in rounds)
    cost = sum(r['cost'] for r in rounds)
    value = sum(r['value'] for r in rounds)
    print('  {}'.format(label))
    print('    rounds={}  spins={}  cost={:>14,}  acc_value={:>14,}'.format(
        n, spins, cost, value))
    print('    cost/round={:>12,.0f}  cost/spin={:>9.1f}  value/cost={:>6.2f}%  net={:>+14,}'.format(
        cost/n, cost/spins, value/cost*100, value-cost))
    if ensemble:
        bet_spins = sum(r.get('bet_spins',0) for r in rounds)
        catches_on_bet = sum(1 for r in rounds if r.get('catch_was_ensemble'))
        if bet_spins:
            print('    bet_spins={}  catches_on_bet={}  mb/hit={:.1f}'.format(
                bet_spins, catches_on_bet, bet_spins/max(catches_on_bet,1)))
    if 'bumps' in rounds[0]:
        bumps = sum(r['bumps'] for r in rounds)
        catches_on_bump = sum(1 for r in rounds if r.get('catch_was_bump'))
        print('    bumps={}  catches_on_bump={}  ({}% of catches)'.format(
            bumps, catches_on_bump, round(100*catches_on_bump/n)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
print('=' * 78)
print('HYBRID SIMULATION  —  Hammer + v5 7-rule causal ensemble')
print('=' * 78)
print('Ensemble fires -> bet override = {}'.format(ENSEMBLE_MAX_BET))
print()

ACCTS = ['Islam', 'Ahmed', 'Nick']
all_hm, all_en, all_hy = [], [], []
all_fires = {n:0 for n,_ in ENSEMBLE_RULES}
all_catches = {n:0 for n,_ in ENSEMBLE_RULES}

for acct in ACCTS:
    print('--- {} ---'.format(acct))
    rh, re, ry, fires, catches = simulate_account(acct)
    summarize('PURE HAMMER',     rh)
    summarize('PURE ENSEMBLE',   re, ensemble=True)
    summarize('HYBRID',          ry)
    print()
    all_hm.extend(rh)
    all_en.extend(re)
    all_hy.extend(ry)
    for k,v in fires.items():   all_fires[k]   += v
    for k,v in catches.items(): all_catches[k] += v

print('=' * 78)
print('POOLED — all 3 accounts')
print('=' * 78)
summarize('PURE HAMMER',     all_hm)
print()
summarize('PURE ENSEMBLE',   all_en, ensemble=True)
print()
summarize('HYBRID',          all_hy)
print()
print('Per-rule firings (POOLED):')
print('  {:<20s}  {:>10s}  {:>10s}'.format('rule','total fires','catches'))
for name,_ in ENSEMBLE_RULES:
    print('  {:<20s}  {:>10d}  {:>10d}'.format(name, all_fires[name], all_catches[name]))

print()
print('=' * 78)
print('STRATEGY COMPARISON (POOLED)')
print('=' * 78)
def lift(rounds):
    spins = sum(r['spins'] for r in rounds)
    cost = sum(r['cost'] for r in rounds)
    value = sum(r['value'] for r in rounds)
    # Baseline: always bet 1. Cost = spins. Value per spin = sum acc_count + 9 per triple,
    # which equals sum(acc_count) + 9*catches. Approximate value-per-spin baseline as:
    #   acc_partial_total + 10*catches = sum-of-acc-symbols-on-payline + 9*catches
    # But we don't have raw acc symbol counts here; instead we recompute roi vs cost only.
    roi = value / cost if cost else 0
    net = value - cost
    return cost, value, roi, net

c_hm, v_hm, roi_hm, net_hm = lift(all_hm)
c_en, v_en, roi_en, net_en = lift(all_en)
c_hy, v_hy, roi_hy, net_hy = lift(all_hy)

print('  {:<18s} {:>14s} {:>14s} {:>10s} {:>16s}'.format(
    'strategy','total cost','total value','ROI%','net (value-cost)'))
print('  ' + '-'*78)
print('  {:<18s} {:>14,} {:>14,} {:>9.2f}% {:>+16,}'.format('Pure Hammer',  c_hm, v_hm, roi_hm*100, net_hm))
print('  {:<18s} {:>14,} {:>14,} {:>9.2f}% {:>+16,}'.format('Pure Ensemble',c_en, v_en, roi_en*100, net_en))
print('  {:<18s} {:>14,} {:>14,} {:>9.2f}% {:>+16,}'.format('HYBRID',       c_hy, v_hy, roi_hy*100, net_hy))

# Per-round averages
print()
print('  Per-round averages:')
print('  {:<18s} {:>10s} {:>14s} {:>14s} {:>14s}'.format(
    'strategy','rounds','cost/round','value/round','net/round'))
print('  ' + '-'*78)
for label, rs, c, v, nt in [('Pure Hammer',   all_hm, c_hm, v_hm, net_hm),
                            ('Pure Ensemble', all_en, c_en, v_en, net_en),
                            ('HYBRID',        all_hy, c_hy, v_hy, net_hy)]:
    n = len(rs)
    print('  {:<18s} {:>10d} {:>14,.0f} {:>14,.0f} {:>+14,.0f}'.format(
        label, n, c/n, v/n, nt/n))
