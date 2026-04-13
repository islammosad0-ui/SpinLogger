"""
Simulate the internet "Shield" and "Hammer" bet ladders against our actual data.

Shield system (Version A — original poster):
  Watch for SHIELD TRIPLES (3 shields on payline). Bet ladder advances by 1 step
  per shield triple. Round ends on the next ACC triple.

  ladder = [1, 2, 3, 15, 50, 400, 1500, 6000, 20000]
   - bet 1     until 1st shield triple
   - bet 2     until 2nd shield triple
   - bet 3     until 3rd
   - bet 15    until 4th
   - bet 50    until 5th
   - bet 400   until 6th
   - bet 1500  until 7th
   - bet 6000  until 8th
   - bet 20000 until ACC triple

Hammer system:
  Count attack symbols on the payline (atk_count per spin = 0/1/2/3).
  Cumulative count drives bet escalation. Round ends on ACC triple.

  ladder thresholds (cumulative hammer-count):
   - bet 15    until count >= 25
   - bet 50    until count >= 50   (next 25)
   - bet 400   until count >= 75   (next 25)
   - bet 1500  until count >= 93   (next 18)
   - bet 6000  until ACC triple    (no further escalation in main version)

Round restart: every ACC triple resets the ladder back to step 0.
First round per session is dropped (we joined mid-round, ladder state unknown).
"""
import pickle
import os
import csv

PKL = 'analysis/nuclear/gaps.pkl'
OUT_DIR = 'analysis/nuclear/strategy_sim'
os.makedirs(OUT_DIR, exist_ok=True)

with open(PKL, 'rb') as f:
    data = pickle.load(f)

# ---------------------------------------------------------------------------
# Ladder definitions
# ---------------------------------------------------------------------------
SHIELD_LADDER = [
    # (bet, shield_triples_required_to_advance_PAST_this_level)
    (1,     1),
    (2,     1),
    (3,     1),
    (15,    1),
    (50,    1),
    (400,   1),
    (1500,  1),
    (6000,  1),
    (20000, None),  # terminal
]
SHIELD_BETS = [s[0] for s in SHIELD_LADDER]

HAMMER_LADDER = [
    # (bet, cumulative_hammer_count_required_to_advance_PAST_this_level)
    (15,    25),
    (50,    50),
    (400,   75),
    (1500,  93),
    (6000,  None),  # terminal
]
HAMMER_BETS = [s[0] for s in HAMMER_LADDER]


def simulate_shield(spins):
    rounds = []
    r = {
        'spins': 0, 'cost': 0, 'shields': 0,
        'level_spins': [0] * len(SHIELD_LADDER),
        'level_cost':  [0] * len(SHIELD_LADDER),
        'level_idx': 0,
    }
    for s in spins:
        bet = SHIELD_LADDER[r['level_idx']][0]
        r['spins'] += 1
        r['cost'] += bet
        r['level_spins'][r['level_idx']] += 1
        r['level_cost'][r['level_idx']] += bet

        if s.get('triple') == 'shield':
            r['shields'] += 1
            # advance one step per shield triple
            if r['level_idx'] < len(SHIELD_LADDER) - 1:
                r['level_idx'] += 1

        if s.get('triple') == 'accumulation':
            r['catch_bet'] = SHIELD_LADDER[r['level_idx']][0]
            r['catch_level'] = r['level_idx']
            rounds.append(r)
            r = {
                'spins': 0, 'cost': 0, 'shields': 0,
                'level_spins': [0] * len(SHIELD_LADDER),
                'level_cost':  [0] * len(SHIELD_LADDER),
                'level_idx': 0,
            }
    return rounds


def simulate_hammer(spins):
    rounds = []
    r = {
        'spins': 0, 'cost': 0, 'hammers': 0,
        'level_spins': [0] * len(HAMMER_LADDER),
        'level_cost':  [0] * len(HAMMER_LADDER),
        'level_idx': 0,
    }
    for s in spins:
        bet = HAMMER_LADDER[r['level_idx']][0]
        r['spins'] += 1
        r['cost'] += bet
        r['level_spins'][r['level_idx']] += 1
        r['level_cost'][r['level_idx']] += bet

        # add this spin's hammers (atk_count on payline = 0/1/2/3)
        r['hammers'] += s.get('atk_count', 0)

        # check threshold to advance
        if r['level_idx'] < len(HAMMER_LADDER) - 1:
            thr = HAMMER_LADDER[r['level_idx']][1]
            if r['hammers'] >= thr:
                r['level_idx'] += 1

        if s.get('triple') == 'accumulation':
            r['catch_bet'] = HAMMER_LADDER[r['level_idx']][0]
            r['catch_level'] = r['level_idx']
            rounds.append(r)
            r = {
                'spins': 0, 'cost': 0, 'hammers': 0,
                'level_spins': [0] * len(HAMMER_LADDER),
                'level_cost':  [0] * len(HAMMER_LADDER),
                'level_idx': 0,
            }
    return rounds


def run_account(acct, simfunc):
    spins = data[acct]['spins']
    by_session = {}
    for s in spins:
        by_session.setdefault(s.get('session_idx', 0), []).append(s)
    all_rounds = []
    for sidx in sorted(by_session.keys()):
        rounds = simfunc(by_session[sidx])
        if rounds:
            # Drop the first round per session — joined mid-round, ladder unknown.
            rounds = rounds[1:]
        for r in rounds:
            r['session'] = sidx
        all_rounds.extend(rounds)
    return all_rounds


def fmt_lvl_breakdown(r, bets):
    parts = []
    for i, b in enumerate(bets):
        if r['level_spins'][i] > 0:
            parts.append('{}@{}'.format(r['level_spins'][i], b))
    return ' '.join(parts)


def summarize(rounds, bets, system_name, acct):
    n = len(rounds)
    if n == 0:
        return
    total_spins = sum(r['spins'] for r in rounds)
    total_cost = sum(r['cost'] for r in rounds)
    print('  {} ({}): {} rounds, {} spins, {} bet units'.format(
        system_name, acct, n, total_spins, total_cost))
    print('    bet/round avg: {:>10.0f}   bet/catch: {:>10.0f}   bet/spin: {:.1f}'.format(
        total_cost / n, total_cost / n, total_cost / total_spins))

    # catches by bet level
    by_bet = {}
    for r in rounds:
        by_bet[r['catch_bet']] = by_bet.get(r['catch_bet'], 0) + 1
    print('    catches by bet level (where the round ended):')
    for b in bets:
        c = by_bet.get(b, 0)
        pct = c / n * 100
        bar = '#' * int(pct / 2)
        print('      bet {:>5}: {:>3} ({:>5.1f}%) {}'.format(b, c, pct, bar))


def write_csv(rounds, bets, path):
    cols = ['acct', 'session', 'round_idx', 'spins', 'cost',
            'shields_or_hammers', 'catch_bet', 'catch_level', 'breakdown']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i, r in enumerate(rounds):
            sk = r.get('shields', r.get('hammers', 0))
            w.writerow([r.get('acct', ''), r['session'], i, r['spins'], r['cost'],
                        sk, r['catch_bet'], r['catch_level'],
                        fmt_lvl_breakdown(r, bets)])


def show_rounds_inline(rounds, bets, label, n_show=8):
    print('  ' + label)
    print('    {:>3} {:>2} {:>5} {:>6} {:>4} {:>5} {:>3}  breakdown'.format(
        'i', 'S', 'spins', 'cost', 'shd', 'catch', 'lvl'))
    head = rounds[:n_show]
    tail = rounds[-n_show:] if len(rounds) > n_show * 2 else []
    for i, r in enumerate(head):
        sk = r.get('shields', r.get('hammers', 0))
        print('    {:>3} {:>2} {:>5} {:>6} {:>4} {:>5} {:>3}  {}'.format(
            i, r['session'], r['spins'], r['cost'], sk,
            r['catch_bet'], r['catch_level'],
            fmt_lvl_breakdown(r, bets)))
    if tail:
        print('    ...')
        for j, r in enumerate(tail):
            i = len(rounds) - len(tail) + j
            sk = r.get('shields', r.get('hammers', 0))
            print('    {:>3} {:>2} {:>5} {:>6} {:>4} {:>5} {:>3}  {}'.format(
                i, r['session'], r['spins'], r['cost'], sk,
                r['catch_bet'], r['catch_level'],
                fmt_lvl_breakdown(r, bets)))


def show_worst(rounds, bets, label):
    if not rounds:
        return
    worst_cost = max(rounds, key=lambda r: r['cost'])
    worst_long = max(rounds, key=lambda r: r['spins'])
    sk_c = worst_cost.get('shields', worst_cost.get('hammers', 0))
    sk_l = worst_long.get('shields', worst_long.get('hammers', 0))
    print('  {} worst-cost round:  {} spins, cost={}, shd/hmr={}, ended at bet {}'.format(
        label, worst_cost['spins'], worst_cost['cost'], sk_c, worst_cost['catch_bet']))
    print('     breakdown: ' + fmt_lvl_breakdown(worst_cost, bets))
    print('  {} longest round:     {} spins, cost={}, shd/hmr={}, ended at bet {}'.format(
        label, worst_long['spins'], worst_long['cost'], sk_l, worst_long['catch_bet']))
    print('     breakdown: ' + fmt_lvl_breakdown(worst_long, bets))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
print('=' * 78)
print('STRATEGY SIMULATION  —  Shield 🛡  &  Hammer ⚒  on actual gap data'.replace('🛡','S').replace('⚒','H'))
print('=' * 78)

ACCTS = ['Islam', 'Ahmed', 'Nick']

for acct in ACCTS:
    print('\n--- {} ---'.format(acct))
    sh_rounds = run_account(acct, simulate_shield)
    hm_rounds = run_account(acct, simulate_hammer)
    for r in sh_rounds:
        r['acct'] = acct
    for r in hm_rounds:
        r['acct'] = acct
    summarize(sh_rounds, SHIELD_BETS, 'SHIELD', acct)
    print()
    summarize(hm_rounds, HAMMER_BETS, 'HAMMER', acct)
    print()
    show_rounds_inline(sh_rounds, SHIELD_BETS, 'SHIELD per-round (first 8 + last 8):')
    print()
    show_rounds_inline(hm_rounds, HAMMER_BETS, 'HAMMER per-round (first 8 + last 8):')
    print()
    show_worst(sh_rounds, SHIELD_BETS, 'SHIELD')
    show_worst(hm_rounds, HAMMER_BETS, 'HAMMER')

    write_csv(sh_rounds, SHIELD_BETS, os.path.join(OUT_DIR, '{}_shield.csv'.format(acct)))
    write_csv(hm_rounds, HAMMER_BETS, os.path.join(OUT_DIR, '{}_hammer.csv'.format(acct)))

print()
print('=' * 78)
print('POOLED — across all 3 accounts')
print('=' * 78)
all_sh = []
all_hm = []
for acct in ACCTS:
    sh = run_account(acct, simulate_shield)
    hm = run_account(acct, simulate_hammer)
    for r in sh:
        r['acct'] = acct
    for r in hm:
        r['acct'] = acct
    all_sh.extend(sh)
    all_hm.extend(hm)

summarize(all_sh, SHIELD_BETS, 'SHIELD', 'POOLED')
print()
summarize(all_hm, HAMMER_BETS, 'HAMMER', 'POOLED')

write_csv(all_sh, SHIELD_BETS, os.path.join(OUT_DIR, 'POOLED_shield.csv'))
write_csv(all_hm, HAMMER_BETS, os.path.join(OUT_DIR, 'POOLED_hammer.csv'))

print()
print('CSVs written to {}/'.format(OUT_DIR))
