"""
Scatter Swarm Strategy Lab — The Telegraph Miner

Strategy: Hammer Ladder Base -> 20,000 on "Scatter Swarm".
Target: 22/22 Mission Clear for Islam with ~10k Pull constraint.
"""
import pickle
from collections import deque

PKL = 'analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)

LADDER_A = [
    (7,120),(90,200),(225,800),(800,1700),(1200,3100),(2400,6000),(4800,11000),
    (10000,20000),(20000,40000),(30000,60000),(45000,85000),(70000,125000),
    (100000,175000),(150000,250000),(200000,300000),(250000,350000),(300000,400000),
    (350000,450000),(400000,500000),(450000,550000),(500000,600000),(550000,650000),
]

HAMMER_LADDER = [(15,25),(50,50),(400,75),(1500,93),(6000,None)]

def strat_swarm_sniper(state, ctx):
    """
    ML Telegraph: If the game drops >=10 total symbols in the last 5 spins, 
    and >=3 of them are accumulation symbols, FIRE THE NUKE (17% hit win rate).
    """
    base = HAMMER_LADDER[ctx['hammer_level']][0]
    
    # Check ML Conditions
    sum_5 = state['sum_5']
    acc_5 = state['acc_5']
    
    if sum_5 >= 10 and acc_5 >= 3:
        if ctx['bankroll'] > 60_000:
            return 20000
        return 6000
    
    return base

def strat_swarm_escalator(state, ctx):
    """
    Smoother progression.
    If dropping >=8 symbols, bet 6000.
    If >=10 and >=3 acc, bet 20000.
    """
    base = HAMMER_LADDER[ctx['hammer_level']][0]
    sum_5 = state['sum_5']
    acc_5 = state['acc_5']
    bankroll = ctx['bankroll']
    
    if sum_5 >= 10 and acc_5 >= 3 and bankroll > 60_000:
        return 20000
    elif sum_5 >= 8 and bankroll > 30_000:
        return 6000
        
    return base

def simulate(spins, bankroll0, ladder, strat_fn):
    bankroll = bankroll0
    mission_idx = 0
    mission_pts = 0
    pulls = 0
    max_bk = bankroll0
    
    triple_log = [] 
    gap_audit = [] 
    
    hammer_level = 0
    hammers = 0

    # 5-spin rolling window deques
    sum_q = deque([0]*5, maxlen=5)
    acc_q = deque([0]*5, maxlen=5)

    for s in spins:
        sum_total = (s['atk_count']+s['stl_count']+s['shd_count']+s['spn_count']+s['acc_count'])
        acc_total = s['acc_count']
        
        sum_q.append(sum_total)
        acc_q.append(acc_total)
        
        state = {
            'sum_5': sum(sum_q),
            'acc_5': sum(acc_q)
        }
        
        ctx = {
            'bankroll': bankroll, 'mission_idx': mission_idx, 'mission_pts': mission_pts,
            'ladder': ladder, 'hammer_level': hammer_level, 'pulls': pulls
        }
        
        bet = strat_fn(state, ctx)
        if bankroll < bet: break
        
        bankroll -= bet
        pulls += 1
        
        triple_type = s.get('triple')
        is_acc = (triple_type == 'accumulation')
        is_spn = (triple_type == 'spins')
        
        pts = 10 * bet if is_acc else s['acc_count'] * bet
        mission_pts += pts
        
        if triple_type:
            if is_spn: bankroll += 10 * bet # RE-FUEL
            if bet >= 6000:
                triple_log.append((pulls, triple_type[:3].upper(), bet, pts, bankroll, state['sum_5'], state['acc_5']))
            
            if is_acc:
                hammer_level = 0
                hammers = 0

        while mission_idx < len(ladder) and mission_pts >= ladder[mission_idx][0]:
            bankroll += ladder[mission_idx][1]
            mission_pts -= ladder[mission_idx][0]
            mission_idx += 1
            gap_audit.append((mission_idx, pulls, bankroll))
            
        max_bk = max(max_bk, bankroll)
        if mission_idx >= len(ladder): break
        
        hammers += s['atk_count']
        if hammer_level < len(HAMMER_LADDER)-1 and hammers >= HAMMER_LADDER[hammer_level][1]:
            hammer_level += 1

    return {
        'cleared': mission_idx >= len(ladder),
        'missions': mission_idx,
        'pulls': pulls,
        'final_bk': bankroll,
        'max_bk': max_bk,
        'triple_log': triple_log,
        'gap_audit': gap_audit
    }

def run():
    print("="*100)
    print("SCATTER SWARM ML SNIPER - FULL AUDIT RUN")
    print("="*100)
    
    accounts = ['Islam', 'Ahmed', 'Nick']
    
    with open('analysis/nuclear/30_swarm_full_results.txt', 'w') as out:
        out.write("="*80 + "\n")
        out.write("SCATTER SWARM SNIPER - FULL AUDIT REPORT\n")
        out.write("="*80 + "\n\n")
        
        for acct in accounts:
            if acct not in data: continue
            
            for sess in [0, 1]:
                spins = [s for s in data[acct]['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
                if not spins: continue
                
                res = simulate(spins, 100_000, LADDER_A, strat_swarm_sniper)
                status = "CLEAR!!" if res['cleared'] else f"FAIL ({res['missions']}/22)"
                
                # Console summary
                print(f"[{acct} s{sess}] {status} | Pulls: {res['pulls']:,} | Final BK: {res['final_bk']:,} | Max BK: {res['max_bk']:,}")
                
                # File detailed dump
                out.write(f"--- {acct} Session {sess}: {status} ---\n")
                out.write(f"Pulls: {res['pulls']:,} | Final BK: {res['final_bk']:,} | Max BK: {res['max_bk']:,}\n\n")
                
                out.write(f"  [HIGH-VALUE CATCH LOG - N={len(res['triple_log'])}]\n")
                for pull, ttype, bet, pts, bk, sum5, acc5 in res['triple_log']:
                    out.write(f"    Pull {pull:>5}: {ttype:>3} | Bet: {bet:>5} | Pts: {pts:>6} | BK: {bk:>9,} | sum_5: {sum5:>2}, acc_5: {acc5:>2}\n")
                
                out.write(f"\n  [GAP AUDIT / MISSION PROGRESS]\n")
                out.write(f"    {'Mission':>7} | {'Pull':>6} | {'Bankroll':>10}\n")
                out.write("    " + "-" * 35 + "\n")
                for m, p, bk in res['gap_audit']:
                    out.write(f"    M{m:>2}     | {p:>6,} | {bk:>10,}\n")
                
                out.write("\n" + "="*80 + "\n\n")
                
    print("\nFull detailed report saved to: analysis/nuclear/30_swarm_full_results.txt")

if __name__ == '__main__':
    run()
