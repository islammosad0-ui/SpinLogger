"""
Event-aware mission ladder simulator (REPLACES 26_mission_bankruptcy.py for analysis).

Fixes from 26:
  - Splits each account into separate event sessions (session_idx 0, 1)
  - Filters to in-event spins only (gae_segment != '')
  - Resets ALL state at session boundaries (sa_*, last10, prev_real_triple, hammer)
  - NO CYCLING — if you run out of spins in this event, the sim ends
  - Logs every pull where bet > 1 (the "max bet" / bumped pulls) with full detail

Usage:
  python analysis/nuclear/28_event_aware_sim.py            # full report
  python analysis/nuclear/28_event_aware_sim.py --log Ahmed pure_ensemble 0 A   # play-by-play
"""
import pickle
import sys
from collections import deque

PKL = 'analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)

# ---------------------------------------------------------------------------
# Mission ladders (same as 26)
# ---------------------------------------------------------------------------
LADDER_A = [
    (7,120),(90,200),(225,800),(800,1700),(1200,3100),(2400,6000),(4800,11000),
    (10000,20000),(20000,40000),(30000,60000),(45000,85000),(70000,125000),
    (100000,175000),(150000,250000),(200000,300000),(250000,350000),(300000,400000),
    (350000,450000),(400000,500000),(450000,550000),(500000,600000),(550000,650000),
]
LADDER_B = [
    (1500,1100),(3000,2700),(8500,8100),(18000,19000),(24000,27000),(36000,46000),
    (51000,68000),(75000,107500),(105000,162500),(150000,230000),(225000,337500),
    (300000,472500),(450000,540000),(600000,675000),(750000,810000),(1050000,1000000),
    (1200000,1200000),(1500000,1400000),(1700000,1800000),(2100000,2100000),
]

HAMMER_LADDER = [(15,25),(50,50),(400,75),(1500,93),(6000,None)]
ENSEMBLE_BUMP_BET = 6000

# ---------------------------------------------------------------------------
# v5 7-rule causal ensemble
# ---------------------------------------------------------------------------
def gap_class(L):
    if L is None: return 'NONE'
    if L <= 39:  return 'XS'
    if L <= 105: return 'S'
    if L <= 160: return 'M'
    return 'L'

def rule_steal_t65(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if not (65 <= sp <= 105): return False
    return (s['sa_acc']/sp) >= 0.34
def rule_steal_t130(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if sp < 130: return False
    return (s['sa_acc']/sp) >= 0.28
def rule_steal_t150(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if sp < 150: return False
    return (s['sa_acc']/sp) >= 0.30
def rule_shield_t150(s):
    if s['prev_real_triple'] != 'shield': return False
    sp = s['sa_spins']
    if sp < 150: return False
    return (s['sa_acc']/sp) >= 0.30
def rule_quiet_zone(s):
    if s['sa_spins'] < 130: return False
    return s['last10_sum'] <= 10
def rule_dg_t130(s):
    sp = s['sa_spins']
    if not (130 <= sp <= 155): return False
    if (s['sa_acc']/sp) < 0.28: return False
    return (s['sa_spn']/sp) >= 0.24
def rule_early_s(s):
    if gap_class(s['prev_gap_length']) not in ('M','L'): return False
    sp = s['sa_spins']
    if not (60 <= sp <= 105): return False
    return s['last10_sum'] <= 10

RULES = [
    ('steal_t65',    rule_steal_t65),
    ('steal_t130',   rule_steal_t130),
    ('steal_t150',   rule_steal_t150),
    ('shield_t150',  rule_shield_t150),
    ('quiet_zone',   rule_quiet_zone),
    ('dg_t130',      rule_dg_t130),
    ('early_s',      rule_early_s),
]

def fired_rules(state):
    return [name for name,fn in RULES if fn(state)]


def get_event_spins(account, session_idx):
    return [s for s in data[account]['spins']
            if s['session_idx'] == session_idx and s['gae_segment'] != '']


# ---------------------------------------------------------------------------
# Core simulator (event-scoped, NO CYCLING, fresh state per call)
# ---------------------------------------------------------------------------
def simulate(spins, bankroll0, ladder, strategy, log_bumps=False, side_events=None,
             cycle_data=False, max_pulls=2_000_000):
    """side_events: list of (mission_idx_1based, spin_grant). Grant fires when
    the triggering mission *completes* (so e.g. (8, 50000) adds 50K spins right
    after Mission 8 clears).

    cycle_data: if True, loop the in-event spins[] indefinitely (capped by
    max_pulls) so OOD sessions can be extended to see where they would actually
    end. State is NOT reset on cycle wrap — it just keeps running.
    """
    side_events = side_events or []
    pending_side = {m: amt for m, amt in side_events}
    bankroll      = bankroll0
    mission_idx   = 0
    mission_pts   = 0
    pulls         = 0
    cost_total    = 0
    points_total  = 0
    rewards_total = 0
    bumps         = 0
    catches_on_bump = 0

    hammer_level = 0
    hammers      = 0
    prev_real_triple = None
    prev_gap_length  = None
    last10 = deque(maxlen=10)

    bump_log = []
    end_reason = 'cleared_all'

    n = len(spins)
    walked_all = True
    data_idx = 0
    cycle_count = 0
    while True:
        if data_idx >= n:
            if not cycle_data:
                break
            data_idx = 0
            cycle_count += 1
        if pulls >= max_pulls:
            end_reason = 'max_pulls'
            walked_all = False
            break
        s = spins[data_idx]
        spin_idx = data_idx
        data_idx += 1
        sym_total = (s['atk_count']+s['stl_count']+s['shd_count']
                     +s['spn_count']+s['acc_count'])
        state = {
            'sa_spins': s['sa_spins'],
            'sa_acc': s['sa_acc'],
            'sa_spn': s['sa_spn'],
            'prev_real_triple': prev_real_triple,
            'prev_gap_length':  prev_gap_length,
            'last10_sum':       sum(last10),
        }
        firing = fired_rules(state)
        fires = bool(firing)

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

        if bankroll < bet:
            end_reason = 'bankrupt'
            walked_all = False
            break

        bankroll  -= bet
        cost_total += bet
        pulls     += 1

        is_triple = (s.get('triple') == 'accumulation')
        if is_triple:
            pts = 10 * bet
        else:
            pts = s['acc_count'] * bet
        points_total += pts
        mission_pts  += pts

        if bet > 1:
            bumps += 1
            if is_triple:
                catches_on_bump += 1
            if log_bumps:
                bump_log.append({
                    'pull_idx':       pulls,
                    'spin_idx':       spin_idx,
                    'bet':            bet,
                    'fired_rules':    firing,
                    'sa_spins':       s['sa_spins'],
                    'sa_acc':         s['sa_acc'],
                    'sa_spn':         s['sa_spn'],
                    'last10_sum':     sum(last10),
                    'prev_real_triple': prev_real_triple,
                    'prev_gap_class': gap_class(prev_gap_length),
                    'acc_count':      s['acc_count'],
                    'is_triple':      is_triple,
                    'pts_earned':     pts,
                    'mission_idx':    mission_idx,
                    'mission_pts':    mission_pts,
                    'bankroll_after': bankroll,
                })

        cleared_now = []
        side_grants_now = 0
        while mission_idx < len(ladder) and mission_pts >= ladder[mission_idx][0]:
            thresh, reward = ladder[mission_idx]
            mission_pts -= thresh
            bankroll    += reward
            rewards_total += reward
            cleared_now.append((mission_idx+1, thresh, reward))
            mission_idx += 1
            # Check for side-event grant tied to this mission completion
            if mission_idx in pending_side:
                grant = pending_side.pop(mission_idx)
                bankroll += grant
                side_grants_now += grant

        if log_bumps and cleared_now and bump_log and bet > 1:
            bump_log[-1]['cleared_missions'] = cleared_now
            bump_log[-1]['bankroll_after'] = bankroll

        if mission_idx >= len(ladder):
            end_reason = 'cleared_all'
            walked_all = False
            break

        hammers += s['atk_count']
        if hammer_level < len(HAMMER_LADDER) - 1:
            if hammers >= HAMMER_LADDER[hammer_level][1]:
                hammer_level += 1

        last10.append(sym_total)
        if s['triple'] is not None:
            prev_real_triple = s['triple']
        if is_triple:
            prev_gap_length = s['sa_spins']
            hammer_level = 0
            hammers = 0

    if walked_all:
        end_reason = 'data_exhausted'

    return {
        'strategy':         strategy,
        'bankroll0':        bankroll0,
        'pulls':            pulls,
        'cost_total':       cost_total,
        'points_total':     points_total,
        'rewards_total':    rewards_total,
        'bumps':            bumps,
        'catches_on_bump':  catches_on_bump,
        'missions_cleared': mission_idx,
        'missions_total':   len(ladder),
        'final_bankroll':   bankroll,
        'final_mission_pts': mission_pts,
        'next_threshold':   ladder[mission_idx][0] if mission_idx < len(ladder) else None,
        'cleared_all':      mission_idx >= len(ladder),
        'end_reason':       end_reason,
        'bump_log':         bump_log,
        'data_spins':       len(spins),
        'cycle_count':      cycle_count,
    }


def main_report():
    print('=' * 110)
    print('EVENT-AWARE MISSION SIM  —  per-event, no cycling, state resets between events')
    print('=' * 110)

    for scenario, bankroll0, ladder in [
        ('A: 100K start, 22-mission ladder', 100_000, LADDER_A),
        ('B: 299K start, 20-mission ladder', 299_000, LADDER_B),
    ]:
        print()
        print('=' * 110)
        print('  SCENARIO ' + scenario)
        print('=' * 110)

        for acct in ['Islam', 'Ahmed', 'Nick']:
            for sess_id in [0, 1]:
                spins = get_event_spins(acct, sess_id)
                if not spins:
                    continue
                gae_last = spins[0]['gae_last_mission']
                print(f'\n--- {acct} session {sess_id}  '
                      f'({len(spins):,} in-event spins, gae_last_mission={gae_last}) ---')
                for strat in ['pure_1x','pure_6000x','pure_hammer','pure_ensemble','hybrid']:
                    r = simulate(spins, bankroll0, ladder, strat)
                    label = {
                        'pure_1x':'Pure 1x','pure_6000x':'Pure 6000x',
                        'pure_hammer':'Pure Hammer','pure_ensemble':'Pure Ensemble',
                        'hybrid':'HYBRID',
                    }[strat]
                    if r['cleared_all']:
                        verdict = 'CLEAR ALL'
                    elif r['end_reason'] == 'data_exhausted':
                        verdict = 'OUT OF DATA'
                    else:
                        verdict = 'BANKRUPT'
                    pct = (r['final_mission_pts']/r['next_threshold']*100) if r['next_threshold'] else 0
                    print(f'  {label:<14s} {verdict:<13s} '
                          f'missions={r["missions_cleared"]:>2}/{r["missions_total"]} ({pct:>4.0f}% next)  '
                          f'pulls={r["pulls"]:>5,}  '
                          f'bumps={r["bumps"]:>4}  catch_on_bump={r["catches_on_bump"]:>3}  '
                          f'final_bk={r["final_bankroll"]:>9,}')


def play_by_play(account, strategy, sess_id, scenario):
    bankroll0, ladder = (100_000, LADDER_A) if scenario == 'A' else (299_000, LADDER_B)
    spins = get_event_spins(account, sess_id)
    r = simulate(spins, bankroll0, ladder, strategy, log_bumps=True)

    print('=' * 110)
    print(f'PLAY-BY-PLAY: {account} session {sess_id}, {strategy}, scenario {scenario}')
    print(f'  Started with {bankroll0:,} spins | {len(spins):,} in-event spins available')
    print(f'  gae_last_mission={spins[0]["gae_last_mission"]}')
    print('=' * 110)

    final = 'CLEAR' if r['cleared_all'] else r['end_reason'].upper()
    print(f'\nFINAL: {final}')
    print(f'  missions cleared:   {r["missions_cleared"]}/{r["missions_total"]}')
    print(f'  total pulls:        {r["pulls"]:,}')
    print(f'  bumped pulls (>1x): {r["bumps"]}')
    print(f'  catches on bumps:   {r["catches_on_bump"]}')
    print(f'  total cost:         {r["cost_total"]:,}')
    print(f'  total acc points:   {r["points_total"]:,}')
    print(f'  rewards earned:     {r["rewards_total"]:,}')
    print(f'  final bankroll:     {r["final_bankroll"]:,}')
    if not r['cleared_all'] and r['next_threshold']:
        print(f'  stuck on mission {r["missions_cleared"]+1}: '
              f'{int(r["final_mission_pts"]):,} / {r["next_threshold"]:,} '
              f'({r["final_mission_pts"]/r["next_threshold"]*100:.1f}%)')

    print(f'\n--- ALL {len(r["bump_log"])} BUMPED PULLS (bet > 1) ---')
    print(f'{"#":>4} {"spin":>5} {"bet":>6} {"acc":>3} {"trip":>4} {"pts":>9} '
          f'{"prev_t":>7} {"sa_sp":>5} {"sa_acc":>6} {"l10":>4} '
          f'{"rules":<32} {"clears":<22} {"bkr_after":>11}')
    print('-' * 110)
    for b in r['bump_log']:
        rules_str = ','.join(rn for rn in b['fired_rules']) if b['fired_rules'] else '(hammer)'
        if len(rules_str) > 31:
            rules_str = rules_str[:28]+'...'
        clears = b.get('cleared_missions', [])
        clears_str = ''
        if clears:
            ms = [f'M{m[0]}' for m in clears]
            clears_str = '+'.join(ms)
            if len(clears_str) > 21:
                clears_str = f'{len(clears)}xM (chain)'
        prev = (b['prev_real_triple'] or '-')[:7]
        trip = 'YES' if b['is_triple'] else ''
        print(f'{b["pull_idx"]:>4} {b["spin_idx"]:>5} {b["bet"]:>6,} {b["acc_count"]:>3} {trip:>4} '
              f'{b["pts_earned"]:>9,} {prev:>7} {b["sa_spins"]:>5} {b["sa_acc"]:>6} '
              f'{b["last10_sum"]:>4} {rules_str:<32} {clears_str:<22} {b["bankroll_after"]:>11,}')


def extend_ood_report():
    """For every (account, session, strategy, scenario) combo that ran out of
    data without bankrupting, re-run with cycle_data=True so the in-event spins
    loop indefinitely. Tells us 'where would they actually have ended?'"""
    print('=' * 118)
    print('OOD-EXTENSION SIM  —  re-running every \'OUT OF DATA\' result with cycle_data=True')
    print('  (loops the same in-event spins[] until bankrupt OR all missions cleared OR 2M-pull cap)')
    print('=' * 118)

    scenarios = [
        ('A', 100_000, LADDER_A),
        ('B', 299_000, LADDER_B),
    ]
    accts = ['Islam', 'Ahmed', 'Nick']
    strats = ['pure_1x','pure_6000x','pure_hammer','pure_ensemble','hybrid']
    label = {
        'pure_1x':'Pure 1x','pure_6000x':'Pure 6000x',
        'pure_hammer':'Pure Hammer','pure_ensemble':'Pure Ensemble',
        'hybrid':'HYBRID',
    }

    # First pass: discover OOD cases via the normal (non-cycling) sim
    ood_cases = []
    for scen_name, br0, ladder in scenarios:
        for acct in accts:
            for sess in [0, 1]:
                spins = get_event_spins(acct, sess)
                if not spins:
                    continue
                for strat in strats:
                    r0 = simulate(spins, br0, ladder, strat)
                    if r0['end_reason'] == 'data_exhausted':
                        ood_cases.append({
                            'scen': scen_name, 'br0': br0, 'ladder': ladder,
                            'acct': acct, 'sess': sess, 'strat': strat,
                            'spins': spins, 'r0': r0,
                        })

    print(f'\nFound {len(ood_cases)} OOD cases.\n')

    # Second pass: extend each
    print(f'{"scen":<5}{"acct":<7}{"sess":<6}{"strategy":<14}'
          f'{"orig msn":>9}{"orig bk":>11}  ->  '
          f'{"ext msn":>9}{"ext bk":>11}{"verdict":>15}{"cycles":>8}{"pulls":>10}')
    print('-' * 118)
    summary_lines = []
    for c in ood_cases:
        r1 = simulate(c['spins'], c['br0'], c['ladder'], c['strat'],
                      cycle_data=True, max_pulls=2_000_000)
        if r1['cleared_all']:
            verdict = 'CLEAR ALL'
        elif r1['end_reason'] == 'bankrupt':
            verdict = 'BANKRUPT'
        elif r1['end_reason'] == 'max_pulls':
            verdict = '2M-PULL CAP'
        else:
            verdict = r1['end_reason']
        line = (f'{c["scen"]:<5}{c["acct"]:<7}s{c["sess"]:<5}{label[c["strat"]]:<14}'
                f'{c["r0"]["missions_cleared"]:>4}/{c["r0"]["missions_total"]:<4}'
                f'{c["r0"]["final_bankroll"]:>11,}  ->  '
                f'{r1["missions_cleared"]:>4}/{r1["missions_total"]:<4}'
                f'{r1["final_bankroll"]:>11,}{verdict:>15}'
                f'{r1["cycle_count"]:>8}{r1["pulls"]:>10,}')
        print(line)
        summary_lines.append((c, r1, verdict))

    # Aggregate counts
    print()
    print('=' * 118)
    print('  TALLY  (extended verdicts of OOD cases)')
    print('=' * 118)
    cleared = [s for s in summary_lines if s[1]['cleared_all']]
    bankrupted = [s for s in summary_lines if s[1]['end_reason'] == 'bankrupt']
    capped = [s for s in summary_lines if s[1]['end_reason'] == 'max_pulls']
    print(f'  CLEAR ALL : {len(cleared):>3} / {len(summary_lines)}')
    print(f'  BANKRUPT  : {len(bankrupted):>3} / {len(summary_lines)}')
    print(f'  2M CAP    : {len(capped):>3} / {len(summary_lines)}  '
          f'(strategy keeps growing the bankroll faster than it spends — would clear with more pulls or higher cap)')

    if cleared:
        print()
        print('  --- CASES THAT WOULD ACTUALLY CLEAR THE FULL LADDER ---')
        for c, r1, _ in cleared:
            extra_event_spins_played = (r1['cycle_count']) * len(c['spins'])
            print(f'    {c["scen"]} {c["acct"]} s{c["sess"]} {label[c["strat"]]:<14}  '
                  f'cleared in {r1["pulls"]:,} pulls '
                  f'(needed {r1["cycle_count"]:.0f}× more event data, '
                  f'~{extra_event_spins_played:,} extra in-event spins) '
                  f'final bk={r1["final_bankroll"]:,}')

    if bankrupted:
        print()
        print('  --- CASES THAT EVENTUALLY BANKRUPT EVEN WITH UNLIMITED DATA ---')
        for c, r1, _ in bankrupted:
            short = r1['final_mission_pts']
            need = r1['next_threshold']
            pct = (short/need*100) if need else 0
            print(f'    {c["scen"]} {c["acct"]} s{c["sess"]} {label[c["strat"]]:<14}  '
                  f'died on M{r1["missions_cleared"]+1} after '
                  f'{r1["cycle_count"]} cycles ({r1["pulls"]:,} pulls), '
                  f'{int(short):,}/{need:,} ({pct:.0f}%)')

    if capped:
        print()
        print('  --- CASES THAT HIT THE 2M-PULL SAFETY CAP (still solvent) ---')
        for c, r1, _ in capped:
            print(f'    {c["scen"]} {c["acct"]} s{c["sess"]} {label[c["strat"]]:<14}  '
                  f'M{r1["missions_cleared"]}/{r1["missions_total"]}, '
                  f'bk={r1["final_bankroll"]:,} after '
                  f'{r1["cycle_count"]} cycles — likely clears with higher cap')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--log':
        account = sys.argv[2]
        strategy = sys.argv[3]
        sess_id = int(sys.argv[4])
        scenario = sys.argv[5] if len(sys.argv) > 5 else 'A'
        play_by_play(account, strategy, sess_id, scenario)
    elif len(sys.argv) > 1 and sys.argv[1] == '--extend-ood':
        extend_ood_report()
    else:
        main_report()
