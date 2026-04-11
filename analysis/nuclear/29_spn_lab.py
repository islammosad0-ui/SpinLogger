"""
Smallbump Evolution & Magic Sniper — The Final Clearing Quest

Strategy 1: Survival Grind (1500) until M18, then Nuclear Clear (20,000).
Strategy 2: Magic Sniper (Hammer Base), 20k on Shield Clusters / Pity Zone.
Target: 22/22 Mission Clear for Islam.
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

def rule_quiet_zone(s):
    if s['sa_spins'] < 130: return False
    return s['last10_sum'] <= 10
def rule_early_s(s):
    sp = s['sa_spins']
    if not (60 <= sp <= 105): return False
    return s['last10_sum'] <= 10
def rule_dg_t130(s):
    sp = s['sa_spins']
    if not (130 <= sp <= 155): return False
    return (s['sa_acc']/sp) >= 0.28
def rule_steal_t130(s):
    if s['prev_real_triple_type'] != 'steal': return False
    return s['sa_spins'] >= 130

# --- Magic Sniper Rules ---
def rule_pity_zone(s):
    return s['sa_spins'] > 150
def rule_refuel_predictor(s):
    return s.get('ss_spins', 0) > 120
def rule_shield_cluster(s):
    return s.get('last5_shd_sum', 0) >= 3

V5_RULES = [
    ('qz', rule_quiet_zone), ('early_s', rule_early_s),
    ('dg', rule_dg_t130), ('steal', rule_steal_t130)
]

MAGIC_RULES = [
    ('pity', rule_pity_zone), ('refuel', rule_refuel_predictor),
    ('shd_cluster', rule_shield_cluster)
]

def fired(state, ruleset):
    return [name for name,fn in ruleset if fn(state)]

def strat_smallbump_evolution(state, ctx, ruleset):
    """
    Survival grind (1500) -> Final Burner (20,000)
    """
    bankroll = ctx['bankroll']
    mission = ctx['mission_idx'] + 1
    base = HAMMER_LADDER[ctx['hammer_level']][0]
    
    if ctx['n_fires'] > 0:
        # THE NUCLEAR FINish (Mission 18+)
        if mission >= 18: 
            if bankroll > 100_000: return 20000
            return 6000
        # THE SURVIVAL GRIND (Mission 1-17)
        if bankroll > 30_000: return 1500
        return base
        
    return base

def strat_magic_sniper(state, ctx, ruleset):
    """
    Base: Hammer Ladder
    If any magic signal fires and bankroll > 60k: 20000
    """
    base = HAMMER_LADDER[ctx['hammer_level']][0]
    if ctx['n_fires'] > 0 and ctx['bankroll'] > 60_000:
        return 20000
    return base

# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

def simulate(spins, bankroll0, ladder, strat_fn, ruleset):
    bankroll = bankroll0
    mission_idx = 0
    mission_pts = 0
    pulls = 0
    max_bk = bankroll0
    
    triple_log = [] 
    gap_audit = [] 
    prev_real_triple_type = None
    last10 = deque(maxlen=10)
    last5_shd = deque(maxlen=5)
    
    hammer_level = 0
    hammers = 0

    for s in spins:
        sym_total = (s['atk_count']+s['stl_count']+s['shd_count']+s['spn_count']+s['acc_count'])
        last5_shd.append(s['shd_count'])
        
        state = {
            'sa_spins': s['sa_spins'], 'sa_acc': s['sa_acc'], 'sa_spn': s['sa_spn'],
            'ss_spins': s['ss_spins'], 'prev_real_triple_type': prev_real_triple_type,
            'last10_sum': sum(last10), 'last5_shd_sum': sum(last5_shd)
        }
        firing = fired(state, ruleset)
        
        ctx = {
            'bankroll': bankroll, 'mission_idx': mission_idx, 'mission_pts': mission_pts,
            'ladder': ladder, 'hammer_level': hammer_level, 'pulls': pulls,
            'n_fires': len(firing)
        }
        
        bet = strat_fn(state, ctx, ruleset)
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
                triple_log.append((pulls, triple_type[:3].upper(), bet, pts, bankroll, firing))
            
            if is_acc:
                hammer_level = 0
                hammers = 0
            prev_real_triple_type = triple_type

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
        last10.append(sym_total)

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
    print("SMALLBUMP EVOLUTION FINAL RUN")
    print("="*100)
    
    for sess in [0, 1]:
        spins = [s for s in data['Islam']['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
        res = simulate(spins, 100_000, LADDER_A, strat_smallbump_evolution, V5_RULES)
        status = "CLEAR!!" if res['cleared'] else f"FAIL ({res['missions']}/22)"
        
        print(f"\n[Smallbump Evolution] Islam Session {sess}: {status}")
        print(f"Pulls: {res['pulls']:,} | Final BK: {res['final_bk']:,} | Max BK: {res['max_bk']:,}")
        
    print("\n" + "="*100)
    print("MAGIC SNIPER FINAL RUN")
    print("="*100)
    
    for sess in [0, 1]:
        spins = [s for s in data['Islam']['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
        res = simulate(spins, 100_000, LADDER_A, strat_magic_sniper, MAGIC_RULES)
        status = "CLEAR!!" if res['cleared'] else f"FAIL ({res['missions']}/22)"
        
        print(f"\n[Magic Sniper] Islam Session {sess}: {status}")
        print(f"Pulls: {res['pulls']:,} | Final BK: {res['final_bk']:,} | Max BK: {res['max_bk']:,}")
        
        if res['cleared']:
            print(f"\n--- AUDIT TRACE (Session {sess} CLEAR!) ---")
            print(f"Total High-Bet Triples Hit: {len(res['triple_log'])}")
            for pull, ttype, bet, pts, bk, signals in res['triple_log']:
                if bet >= 20000:
                    sigs = ",".join(signals) if signals else "None"
                    print(f"  Pull {pull:>5}: {ttype} | Bet: {bet:>5} | Pts: {pts:>6} | BK: {bk:>7} | Signals: {sigs}")
            
            print(f"\n{'Mission':>7} | {'Pull':>6} | {'Bankroll':>10}")
            print("-" * 35)
            for m, p, bk in res['gap_audit']:
                print(f"M{m:>2}     | {p:>6,} | {bk:>10,}")

if __name__ == '__main__':
    run()

