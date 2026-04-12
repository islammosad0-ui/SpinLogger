import pickle
import os

REAL_TRIPLES = ['accumulation', 'spins', 'attack', 'steal', 'shield']

def is_other_triple(s, target):
    r1, r2, r3 = s.get('reel_1', ''), s.get('reel_2', ''), s.get('reel_3', '')
    if r1 == r2 == r3 and r1 in REAL_TRIPLES:
        if r1 != target: return r1
    return None

def check_super_ensemble(s, traj, idx, target, p1, p2, prev_real_triple):
    # ACC Counters
    cur_t_acc = s['sa_spins']
    acc_rate = s['sa_acc'] / max(1, cur_t_acc)
    spn_rate = s['sa_spn'] / max(1, cur_t_acc)
    
    # SPN Counters (if available in record)
    cur_t_spn = s.get('ss_spins', cur_t_acc)
    spn_rate_pure = s.get('ss_spn', s['sa_spn']) / max(1, cur_t_spn)

    # ACC RULES
    if target == 'accumulation':
        # V5 Behavioral
        if idx >= 10 and cur_t_acc >= 130:
            prev_s = traj[idx-10]
            total = ((s['sa_atk'] - prev_s['sa_atk']) + (s['sa_stl'] - prev_s['sa_stl']) + 
                     (s['sa_shd'] - prev_s['sa_shd']) + (s['sa_acc'] - prev_s['sa_acc']) + 
                     (s['sa_spn'] - prev_s['sa_spn']))
            if total <= 10: return True, "V5_QUIET"
        if prev_real_triple == "steal":
            if 65 <= cur_t_acc <= 105 and acc_rate >= 0.34: return True, "V5_STEAL_S"
            if cur_t_acc >= 130 and acc_rate >= 0.28: return True, "V5_STEAL_M"
        if prev_real_triple == "shield" and cur_t_acc >= 150 and acc_rate >= 0.30: return True, "V5_SHIELD_L"
        if cur_t_acc >= 110 and acc_rate >= 0.28 and spn_rate >= 0.20: return True, "R01_COMBO"
        if p1 >= 120 and cur_t_acc >= 130 and acc_rate >= 0.30: return True, "R06_SML_L"
        if cur_t_acc >= 150 and acc_rate >= 0.37: return True, "R16_SNIPER"
        if cur_t_acc >= 160: return True, "DEEP_PITY"

    # SPN RULES
    if target == 'spins':
        if cur_t_spn >= 120 and spn_rate_pure >= 0.25: return True, "SPN_SNIPER"
        if cur_t_spn >= 150: return True, "SPN_PITY"

    return False, "NONE"

def run_precision_trace():
    pkl_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl"
    with open(pkl_path, "rb") as f:
        all_data = pickle.load(f)

    for acct, d in all_data.items():
        fname = f"C:\\Users\\Islam Nawwar\\SpinLogger\\analysis\\nuclear\\trace_{acct}.txt"
        with open(fname, "w", encoding="utf-8") as out:
            out.write(f"=== MASTER TRACE: {acct.upper()} ===\n")
            out.write("Targets: ACCUMULATION and SPINS\n\n")

            for target in ['accumulation', 'spins']:
                gaps = d['gaps'].get(target, [])
                if not gaps: continue
                
                out.write(f"{'#'*100}\n TARGET: {target.upper()}\n{'#'*100}\n\n")
                
                for g_idx, g in enumerate(gaps):
                    traj = g['trajectory']
                    p1, p2, prev_triple = g.get('prev_gap_1', 0), g.get('prev_gap_2', 0), g['prev_real_triple']
                    
                    trigger_idx, nat_dup_idx = -1, -1
                    for i, s in enumerate(traj):
                        firing, _ = check_super_ensemble(s, traj, i, target, p1, p2, prev_triple)
                        if trigger_idx == -1 and firing and i > 0:
                            if (s['reel_1'] == traj[i-1]['reel_1'] and s['reel_2'] == traj[i-1]['reel_2'] and s['reel_3'] == traj[i-1]['reel_3']):
                                trigger_idx = i
                    
                    lookback = max(1, len(traj)-10)
                    for i in range(lookback, len(traj)):
                        if (traj[i]['reel_1'] == traj[i-1]['reel_1'] and traj[i]['reel_2'] == traj[i-1]['reel_2'] and traj[i]['reel_3'] == traj[i-1]['reel_3']):
                            nat_dup_idx = i
                            break

                    if trigger_idx == -1 and nat_dup_idx == -1: continue
                    
                    is_caught = (trigger_idx != -1 and (len(traj)-1-trigger_idx) <= 10)
                    res = "CLEAN CATCH" if is_caught else ("MISSED (NAT DUP)" if nat_dup_idx != -1 else "LATE HIT")
                    
                    out.write(f"Gap #{g_idx:03d} | CurLen: {len(traj):3d} | Prev1: {p1:3d} | Prev2: {p2:3d} | Result: {res}\n")
                    
                    # Logic for start_p
                    start_p = 0
                    if trigger_idx != -1:
                        ensemble_start = next((k for k,v in enumerate(traj) if check_super_ensemble(v,traj,k,target,p1,p2,prev_triple)[0]), 0)
                        start_p = max(0, ensemble_start - 3)
                    else: start_p = max(0, nat_dup_idx - 5)
                    
                    for j in range(start_p, len(traj)):
                        s = traj[j]
                        f, rule = check_super_ensemble(s, traj, j, target, p1, p2, prev_triple)
                        tag = f"[{rule:12s}]" if f else "[   WAITING  ]"
                        m = ""
                        if j == trigger_idx: m += " <--- !!! SNIPER-TRIGGER !!!"
                        elif nat_dup_idx != -1 and j == nat_dup_idx and trigger_idx == -1: m += " <--- *NATURAL SIGNAL*"
                        if j > trigger_idx and trigger_idx != -1:
                            oth = is_other_triple(s, target)
                            if oth: m += f" <--- MINOR [{oth.upper()}]"
                            if j > 0 and s['reel_1'] == traj[j-1]['reel_1'] and s['reel_2'] == traj[j-1]['reel_2'] and s['reel_3'] == traj[j-1]['reel_3']: m += " <--- *SUB-DUP*"
                        if j == len(traj) - 1: m += " <--- 🎯 JACKPOT 🎯"
                        
                        pos_in_gap = s['sa_spins'] if target == 'accumulation' else s.get('ss_spins', j+1)
                        out.write(f"    T{j-(trigger_idx if trigger_idx != -1 else (nat_dup_idx if nat_dup_idx != -1 else len(traj)-1)):+03d} | SEQ:{str(s.get('seq','n/a')).rjust(6)} | POS:{str(pos_in_gap).rjust(3)} | {tag} | [{s['reel_1'][:8]:8s}|{s['reel_2'][:8]:8s}|{s['reel_3'][:8]:8s}]{m}\n")
                    out.write("-" * 140 + "\n\n")
        print(f"Created trace file: trace_{acct}.txt")

if __name__ == "__main__":
    run_precision_trace()
