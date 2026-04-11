"""
Escalator Shield Strategy Lab

Strategy: 
  0-50:   Base Hammer (Sleep)
  51-100: 1500        (Jog)
 101-150: 6000        (Run)
 151-200: 20000       (Nuke)
 201+   : 6000        (Survivor - protect against anomalies)
"""
import pickle

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

def strat_escalator_shield(state, ctx):
    bankroll = ctx['bankroll']
    base = HAMMER_LADDER[ctx['hammer_level']][0]
    gap = state['sa_spins']
    m_idx = ctx['mission_idx']
    
    if bankroll < base: return base
    if m_idx >= len(ctx['ladder']): return base
    
    target_pts = ctx['ladder'][m_idx][0] - ctx['mission_pts']
    
    # Check if a 1500 bet is enough to clear (15,000 pts).
    # If a 1500 bet clears it, our ideal is 1500.
    ideal_bet = base
    for b in [15, 50, 400, 1500, 6000, 20000]:
        if b * 10 >= target_pts:
            ideal_bet = b
            break
    if target_pts > 200000:
        ideal_bet = 20000
        
    # Cap ideal bet by bankroll safety (only need to survive 20 spins in the Tight Zone)
    while ideal_bet > base and bankroll < (ideal_bet * 20):
        opts = [15, 50, 400, 1500, 6000, 20000]
        idx = opts.index(ideal_bet)
        if idx > 0: ideal_bet = opts[idx-1]
        else: ideal_bet = base

    # TIGHT PITY SNIPER
    # Wait until exactly Gap 150 where the probability spikes to 33%.
    if gap < 145:
        return base
    elif 145 <= gap <= 175:
        return max(base, ideal_bet)
    else:
        # Anomaly Desert (gap > 175)
        # Drop back so we don't go bankrupt waiting for the 300+ gap glitch
        if bankroll > 15_000:
            return max(base, 1500)
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

    current_sa_spins = 0

    for s in spins:
        current_sa_spins += 1
        
        state = {
            'sa_spins': current_sa_spins
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
            if bet >= 1500:
                triple_log.append((pulls, triple_type[:3].upper(), bet, pts, bankroll, state['sa_spins']))
            
            if is_acc:
                hammer_level = 0
                hammers = 0
                current_sa_spins = 0

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
    print("ESCALATOR SHIELD RUN")
    print("="*100)
    
    accounts = ['Islam', 'Ahmed', 'Nick']
    
    with open('analysis/nuclear/32_escalator_results.txt', 'w') as out:
        out.write("="*80 + "\n")
        out.write("ESCALATOR SHIELD STRATEGY - FULL AUDIT REPORT\n")
        out.write("="*80 + "\n\n")
        
        for acct in accounts:
            if acct not in data: continue
            
            for sess in [0, 1]:
                spins = [s for s in data[acct]['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
                if not spins: continue
                
                # Requested starting bankroll
                res = simulate(spins, 100_000, LADDER_A, strat_escalator_shield)
                status = "CLEAR!!" if res['cleared'] else f"FAIL ({res['missions']}/22)"
                
                print(f"[{acct} s{sess}] {status} | Pulls: {res['pulls']:,} | Final BK: {res['final_bk']:,}")
                
                out.write(f"--- {acct} Session {sess}: {status} ---\n")
                out.write(f"Pulls: {res['pulls']:,} | Final BK: {res['final_bk']:,} | Max BK: {res['max_bk']:,}\n\n")
                
                out.write(f"  [CATCH LOG (>=1500 bet) - N={len(res['triple_log'])}]\n")
                for pull, ttype, bet, pts, bk, gap in res['triple_log']:
                    out.write(f"    Pull {pull:>5}: {ttype:>3} | Bet: {bet:>5} | Pts: {pts:>6} | BK: {bk:>9,} | sa_spins: {gap:>3}\n")
                
                out.write(f"\n  [GAP AUDIT / MISSION PROGRESS]\n")
                out.write(f"    {'Mission':>7} | {'Pull':>6} | {'Bankroll':>10}\n")
                out.write("    " + "-" * 35 + "\n")
                for m, p, bk in res['gap_audit']:
                    out.write(f"    M{m:>2}     | {p:>6,} | {bk:>10,}\n")
                
                out.write("\n" + "="*80 + "\n\n")
                
    print("\nFull detailed report saved to: analysis/nuclear/32_escalator_results.txt")

if __name__ == '__main__':
    run()
