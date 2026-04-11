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

def categorize_gap(gap):
    if gap < 100: return 'S'
    elif gap <= 140: return 'M'
    else: return 'L'

def strat_german_sniper(state, ctx):
    bankroll = ctx['bankroll']
    base = 15 # "x1" in Coin Master is physically the lowest unlocked bet. 15.
    
    # State flags
    seq = state['sequence']
    current_gap = state['sa_major']
    dodge_counter = state.get('dodge_counter', 0)
    m_idx = ctx['mission_idx']
    
    if bankroll < base: return base
    if m_idx >= len(ctx['ladder']): return base
    
    # DODGE MECHANIC
    if dodge_counter > 0:
        return base
        
    # Check if we are in "Sniper Mode"
    if len(seq) >= 3 and seq[-3:] == ['L', 'S', 'S']:
        # Wait until we hit 100 spins at x1 before firing
        if current_gap <= 100:
            return base
            
        # Target Point sizing: "Raises it again to x20000 until he get the triple acc"
        ideal_bet = 20000 
                
        # Downgrade ONLY if we literally don't have enough to physically pull the lever once
        while ideal_bet > base and bankroll < ideal_bet:
            opts = [15, 50, 400, 1500, 6000, 20000]
            idx = opts.index(ideal_bet)
            if idx > 0: ideal_bet = opts[idx-1]
            else: ideal_bet = base
            
        return ideal_bet
        
    return base

def simulate_german(spins, bankroll0, ladder):
    bankroll = bankroll0
    mission_idx = 0
    mission_pts = 0
    pulls = 0
    max_bk = bankroll0
    
    triple_log = []
    gap_audit = []
    
    hammer_level = 0
    hammers = 0

    sa_major = 0 # Spins since accumulation OR spins triple
    sequence = []
    dodge_counter = 0

    for s in spins:
        sa_major += 1
        if dodge_counter > 0: dodge_counter -= 1
        
        state = {
            'sa_major': sa_major,
            'sequence': sequence,
            'dodge_counter': dodge_counter
        }
        
        ctx = {
            'bankroll': bankroll, 'mission_idx': mission_idx, 'mission_pts': mission_pts,
            'ladder': ladder, 'hammer_level': hammer_level, 'pulls': pulls
        }
        
        bet = strat_german_sniper(state, ctx)
        if bankroll < bet: break
        
        bankroll -= bet
        pulls += 1
        
        triple_type = s.get('triple')
        is_major = (triple_type in ['accumulation', 'spins'])
        
        # Point Logic
        is_acc = (triple_type == 'accumulation')
        pts = 10 * bet if is_acc else s['acc_count'] * bet
        mission_pts += pts
        
        if triple_type:
            if triple_type == 'spins': bankroll += 10 * bet # RE-FUEL
            
            # THE DODGE Mechanic
            # If we are betting High, and hit an irrelevant triple (shield/thief/attack)
            if bet > max(15, 50) and not is_major:
                dodge_counter = 5 # Enter Dodge
                
            if bet > max(15, 50):
                triple_log.append((pulls, triple_type[:3].upper(), bet, pts, bankroll, sa_major))
            
            # Sequence tracker logic for major triples
            if is_major:
                category = categorize_gap(sa_major)
                sequence.append(category)
                sa_major = 0
                dodge_counter = 0 # Reset dodge if a major drops
                
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
    print("GERMAN SEQUENCE SNIPER")
    print("="*100)
    
    accounts = ['Islam', 'Ahmed', 'Nick']
    
    with open('analysis/nuclear/35_german_results.txt', 'w') as out:
        out.write("="*80 + "\n")
        out.write("GERMAN SEQUENCE STRATEGY - FULL AUDIT REPORT\n")
        out.write("="*80 + "\n\n")
        
        for acct in accounts:
            if acct not in data: continue
            
            for sess in [0, 1]:
                spins = [s for s in data[acct]['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
                if not spins: continue
                
                res = simulate_german(spins, 100_000, LADDER_A)
                status = "CLEAR!!" if res['cleared'] else f"FAIL ({res['missions']}/22)"
                
                print(f"[{acct} s{sess}] {status} | Pulls: {res['pulls']:,} | Final BK: {res['final_bk']:,}")
                
                out.write(f"--- {acct} Session {sess}: {status} ---\n")
                out.write(f"Pulls: {res['pulls']:,} | Final BK: {res['final_bk']:,} | Max BK: {res['max_bk']:,}\n\n")
                
                out.write(f"  [CATCH LOG (High Bet >= 400) - N={len(res['triple_log'])}]\n")
                for pull, ttype, bet, pts, bk, gap in res['triple_log']:
                    out.write(f"    Pull {pull:>5}: {ttype:>3} | Bet: {bet:>5} | Pts: {pts:>6} | BK: {bk:>9,} | sa_major: {gap:>3}\n")
                
                out.write(f"\n  [GAP AUDIT / MISSION PROGRESS]\n")
                out.write(f"    {'Mission':>7} | {'Pull':>6} | {'Bankroll':>10}\n")
                out.write("    " + "-" * 35 + "\n")
                for m, p, bk in res['gap_audit']:
                    out.write(f"    M{m:>2}     | {p:>6,} | {bk:>10,}\n")
                
                out.write("\n" + "="*80 + "\n\n")
                
    print("\nFull detailed report saved to: analysis/nuclear/35_german_results.txt")

if __name__ == '__main__':
    run()
