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

def strat_phase_sniper(state, ctx):
    bankroll = ctx['bankroll']
    base = 15
    m_idx = ctx['mission_idx']
    
    sa_acc = state['sa_acc']
    ss_spn = state['ss_spn']
    dodge_counter = state.get('dodge_counter', 0)
    projected_spn_target = state.get('projected_spn_target', -1)
    projected_acc_target = state.get('projected_acc_target', -1)
    
    if bankroll < base: return base
    if m_idx >= len(ctx['ladder']): return base
    if dodge_counter > 0: return base # The Dodge!
    
    FIRE = False
    
    # Mathematical Combined Median Cycle = 115
    # If we have a projected target > 0, we track it
    if projected_acc_target > 0:
        dist = projected_acc_target - sa_acc
        if -10 <= dist <= 15: # Enter Sniper Window (+/- spins from exact mathematical projection)
            FIRE = True
            
    if projected_spn_target > 0 and not FIRE:
        dist = projected_spn_target - ss_spn
        if -10 <= dist <= 15:
            FIRE = True
            
    # Also if the raw pity gap is massively huge, we just organically fire
    if sa_acc > 150 or ss_spn > 150:
        FIRE = True

    if FIRE:
        target_pts = ctx['ladder'][m_idx][0] - ctx['mission_pts']
        ideal_bet = 20000 
        
        while ideal_bet > base and bankroll < ideal_bet:
            opts = [15, 50, 400, 1500, 6000, 20000]
            idx = opts.index(ideal_bet)
            if idx > 0: ideal_bet = opts[idx-1]
            else: ideal_bet = base
            
        return ideal_bet
        
    return base

def simulate_phase(spins, bankroll0, ladder):
    bankroll = bankroll0
    mission_idx = 0
    mission_pts = 0
    pulls = 0
    max_bk = bankroll0
    
    triple_log = []
    gap_audit = []
    
    sa_acc = 0 
    ss_spn = 0
    dodge_counter = 0
    
    projected_spn_target = -1
    projected_acc_target = -1

    for s in spins:
        sa_acc += 1
        ss_spn += 1
        if dodge_counter > 0: dodge_counter -= 1
        
        state = {
            'sa_acc': sa_acc,
            'ss_spn': ss_spn,
            'dodge_counter': dodge_counter,
            'projected_spn_target': projected_spn_target,
            'projected_acc_target': projected_acc_target
        }
        
        ctx = {
            'bankroll': bankroll, 'mission_idx': mission_idx, 'mission_pts': mission_pts,
            'ladder': ladder, 'pulls': pulls
        }
        
        bet = strat_phase_sniper(state, ctx)
        if bankroll < bet: break
        
        bankroll -= bet
        pulls += 1
        
        tt = s.get('triple')
        is_acc = (tt == 'accumulation')
        is_spn = (tt == 'spins')
        is_major = is_acc or is_spn
        
        pts = 10 * bet if is_acc else s['acc_count'] * bet
        mission_pts += pts
        
        if tt:
            if is_spn: bankroll += 10 * bet # RE-FUEL
            
            # The Dodge
            if bet > max(15, 50) and not is_major:
                dodge_counter = 5
                
            if bet > max(15, 50):
                triple_log.append((pulls, tt[:3].upper(), bet, pts, bankroll, sa_acc, ss_spn, projected_acc_target))
            
            if is_acc:
                # Accumulation hit! Project the next SPIN triple
                # Median combined cycle is 115.
                # Project the remaining gap for the Spin triple based on its current offset
                projected_spn_target = ss_spn + (115 - ss_spn) 
                
                # And clear the acc target since it hit
                projected_acc_target = -1
                dodge_counter = 0
                sa_acc = 0
                
            if is_spn:
                # Spin hit! Project the next ACCUMULATION triple
                projected_acc_target = sa_acc + (115 - sa_acc)
                
                projected_spn_target = -1
                dodge_counter = 0
                ss_spn = 0

        while mission_idx < len(ladder) and mission_pts >= ladder[mission_idx][0]:
            bankroll += ladder[mission_idx][1]
            mission_pts -= ladder[mission_idx][0]
            mission_idx += 1
            gap_audit.append((mission_idx, pulls, bankroll))
            
        max_bk = max(max_bk, bankroll)
        if mission_idx >= len(ladder): break

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
    print("PHASE OFFSET SNIPER")
    print("="*100)
    
    accounts = ['Islam', 'Ahmed', 'Nick']
    
    with open('analysis/nuclear/37_phase_results.txt', 'w') as out:
        out.write("="*80 + "\n")
        out.write("PHASE OFFSET STRATEGY - FULL AUDIT REPORT\n")
        out.write("="*80 + "\n\n")
        
        for acct in accounts:
            if acct not in data: continue
            
            for sess in [0, 1]:
                spins = [s for s in data[acct]['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
                if not spins: continue
                
                res = simulate_phase(spins, 100_000, LADDER_A)
                status = "CLEAR!!" if res['cleared'] else f"FAIL ({res['missions']}/22)"
                
                print(f"[{acct} s{sess}] {status} | Pulls: {res['pulls']:>5,} | Final BK: {res['final_bk']:>9,}")
                
                out.write(f"--- {acct} Session {sess}: {status} ---\n")
                out.write(f"Pulls: {res['pulls']:,} | Final BK: {res['final_bk']:,} | Max BK: {res['max_bk']:,}\n\n")
                
                out.write(f"  [CATCH LOG (High Bet >= 400) - N={len(res['triple_log'])}]\n")
                for pull, ttype, bet, pts, bk, sa, ss, proj in res['triple_log']:
                    out.write(f"    Pull {pull:>5}: {ttype:>3} | Bet: {bet:>5} | Pts: {pts:>6} | BK: {bk:>9,} | sa_acc: {sa:>3} | ss_spn: {ss:>3} | Proj_Acc: {proj:>3}\n")
                
                out.write(f"\n  [GAP AUDIT / MISSION PROGRESS]\n")
                out.write(f"    {'Mission':>7} | {'Pull':>6} | {'Bankroll':>10}\n")
                out.write("    " + "-" * 35 + "\n")
                for m, p, bk in res['gap_audit']:
                    out.write(f"    M{m:>2}     | {p:>6,} | {bk:>10,}\n")
                
                out.write("\n" + "="*80 + "\n\n")
                
    print("\nFull detailed report saved to: analysis/nuclear/37_phase_results.txt")

if __name__ == '__main__':
    run()
