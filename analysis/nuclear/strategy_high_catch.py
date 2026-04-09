import pickle
import os

REAL_TRIPLES = ['accumulation', 'spins', 'attack', 'steal', 'shield']

def is_other_triple(s, target):
    r1, r2, r3 = s.get('reel_1', ''), s.get('reel_2', ''), s.get('reel_3', '')
    if r1 == r2 == r3 and r1 in REAL_TRIPLES:
        if r1 != target: return r1
    return None

def check_super_ensemble_high(s, traj, idx, target, p1, p2, prev_real_triple):
    cc_acc = s['sa_spins']
    cc_spn = s.get('ss_spins', idx+1)
    cur_t = cc_acc if target == 'accumulation' else cc_spn
    if cur_t >= 100: return True, "BASE_100"
    acc_rate = s['sa_acc'] / max(1, cc_acc)
    spn_rate = s['sa_spn'] / max(1, cc_acc)
    if target == 'accumulation':
        if idx >= 10 and cur_t >= 130:
            p10 = traj[idx-10]; tot = ((s['sa_atk']-p10['sa_atk']) + (s['sa_stl']-p10['sa_stl']) + (s['sa_shd']-p10['sa_shd']) + (s['sa_acc']-p10['sa_acc']) + (s['sa_spn']-p10['sa_spn']))
            if tot <= 10: return True, "V5_QUIET"
        if prev_real_triple == "steal" and cur_t >= 130 and acc_rate >= 0.28: return True, "V5_STEAL"
        if cur_t >= 110 and acc_rate >= 0.28 and spn_rate >= 0.20: return True, "R01_COMBO"
    else:
        # SPNS
        sr_pure = s.get('ss_spn', s['sa_spn']) / max(1, cur_t)
        if cur_t >= 120 and sr_pure >= 0.25: return True, "SPN_SNIPER"
    return False, "NONE"

def sim_gap_high(traj, target, p1, p2, prev_trip, window):
    any_ens = any(check_super_ensemble_high(s, traj, i, target, p1, p2, prev_trip)[0] for i, s in enumerate(traj))
    pred_pos = 300 - (p1 + p2)
    trigger_idx = -1
    for i, s in enumerate(traj):
        pos = s['sa_spins'] if target == 'accumulation' else s.get('ss_spins', i+1)
        f, _ = check_super_ensemble_high(s, traj, i, target, p1, p2, prev_trip)
        is_dup = (i > 0 and s['reel_1'] == traj[i-1]['reel_1'] and s['reel_2'] == traj[i-1]['reel_2'] and s['reel_3'] == traj[i-1]['reel_3'])
        is_p = (not any_ens) and (abs(pos - pred_pos) <= window)
        if (f or is_p) and is_dup:
            trigger_idx = i; break
    bets, caught = 0, False
    if trigger_idx != -1:
        if (len(traj) - 1 - trigger_idx <= 12): caught = True
        bet, cd = False, 0
        for k, s in enumerate(traj):
            f, _ = check_super_ensemble_high(s, traj, k, target, p1, p2, prev_trip)
            is_dup = (k > 0 and s['reel_1'] == traj[k-1]['reel_1'] and s['reel_2'] == traj[k-1]['reel_2'] and s['reel_3'] == traj[k-1]['reel_3'])
            if (f or ((not any_ens) and abs((s['sa_spins'] if target=='accumulation' else s.get('ss_spins',k+1)) - pred_pos) <= window)) and is_dup: bet = True; cd = 0
            if is_other_triple(s, target) and bet: cd = 5; bet = False
            if cd > 0: cd -= 1
            if cd == 0 and k < (len(traj)-1) and k >= trigger_idx and trigger_idx != -1: bet = True
            if bet: bets += 1
    return caught, bets

def run_strategy_sim():
    with open(r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl", "rb") as f:
        all_data = pickle.load(f)

    summary_log = []
    
    for acct, d in all_data.items():
        st = {'bets': 0, 'hits': 0, 'caught': 0}
        for target in ['accumulation', 'spins']:
            gaps = d['gaps'].get(target, [])
            ec = {}
            for g in gaps:
                eid = g.get('event_id', 0)
                ec[eid] = ec.get(eid, 0) + 1
                if ec[eid] <= 4: continue
                traj, p1, p2, pt = g['trajectory'], g['prev_gap_1'], g['prev_gap_2'], g['prev_real_triple']
                c, b = sim_gap_high(traj, target, p1, p2, pt, 20)
                st['hits'] += 1
                if c: st['caught'] += 1; st['bets'] += b
        summary_log.append((acct, st['caught'], st['hits'], st['bets']))

    fname = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\strategy_high_summary.txt"
    with open(fname, "w") as out:
        out.write("=== HIGH CATCH SUMMARY (POS 100 VERSION) ===\n\n")
        out.write("Account  | Catch Rate | MB/Hit Efficiency\n")
        out.write("-" * 45 + "\n")
        total_c, total_h, total_b = 0, 0, 0
        for s in summary_log:
            cr = (s[1]/max(1,s[2]))*100
            mb = s[3]/max(1,s[1])
            out.write(f"{s[0]:8s} | {cr:10.1f}% | {mb:5.1f} mb/hit\n")
            total_c += s[1]; total_h += s[2]; total_b += s[3]
        out.write("-" * 45 + "\n")
        out.write(f"GLOBAL   | {(total_c/max(1,total_h))*100:10.1f}% | {total_b/max(1,total_c):5.1f} mb/hit\n")
    
    print("\nSummary created: strategy_high_summary.txt")

if __name__ == "__main__":
    run_strategy_sim()
