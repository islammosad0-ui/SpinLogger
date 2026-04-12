import pickle
import os

REAL_TRIPLES = ['accumulation', 'spins', 'attack', 'steal', 'shield']

def is_other_triple(s, target):
    r1, r2, r3 = s.get('reel_1', ''), s.get('reel_2', ''), s.get('reel_3', '')
    if r1 == r2 == r3 and r1 in REAL_TRIPLES:
        if r1 != target: return r1
    return None

def check_super_ensemble(s, traj, idx, target, p1, p2, prev_real_triple):
    cur_t = s['sa_spins'] if target == 'accumulation' else s.get('ss_spins', idx+1)
    acc_rate = s['sa_acc'] / max(1, cur_t)
    spn_rate = s['sa_spn'] / max(1, cur_t)
    if target == 'accumulation':
        if idx >= 10 and cur_t >= 130:
            p10 = traj[idx-10]; tot = ((s['sa_atk']-p10['sa_atk']) + (s['sa_stl']-p10['sa_stl']) + (s['sa_shd']-p10['sa_shd']) + (s['sa_acc']-p10['sa_acc']) + (s['sa_spn']-p10['sa_spn']))
            if tot <= 10: return True, "V5_QUIET"
        if prev_real_triple == "steal" and cur_t >= 130 and acc_rate >= 0.28: return True, "V5_STEAL_M"
        if cur_t >= 110 and acc_rate >= 0.28 and spn_rate >= 0.20: return True, "R01_COMBO"
        if cur_t >= 150 and acc_rate >= 0.37: return True, "R16_SNIPER"
        if cur_t >= 160: return True, "DEEP_PITY"
    else:
        sr_p = s.get('ss_spn', s['sa_spn']) / max(1, cur_t)
        if cur_t >= 120 and sr_p >= 0.25: return True, "SPN_SNIPER"
        if cur_t >= 150: return True, "SPN_PITY"
    return False, "NONE"

def run_strategy_sim():
    with open(r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl", "rb") as f:
        all_data = pickle.load(f)

    for acct, d in all_data.items():
        fname = f"C:\\Users\\Islam Nawwar\\SpinLogger\\analysis\\nuclear\\strategy_{acct}.txt"
        with open(fname, "w", encoding="utf-8") as out:
            out.write(f"=== STRICT RESEARCH TRACE: {acct.upper()} ===\n\n")

            for target in ['accumulation', 'spins']:
                gaps = d['gaps'].get(target, [])
                if not gaps: continue
                out.write(f"{'='*120}\n TARGET: {target.upper()}\n{'='*120}\n\n")
                
                ev_c = {}
                for g_idx, g in enumerate(gaps):
                    eid = g.get('event_id', 0); ev_c[eid] = ev_c.get(eid, 0) + 1
                    if ev_c[eid] <= 4: continue
                    traj, p1, p2, pt = g['trajectory'], g['prev_gap_1'], g['prev_gap_2'], g['prev_real_triple']
                    pred_pos = 300 - (p1+p2)
                    any_ens = any(check_super_ensemble(s, traj, i, target, p1, p2, pt)[0] for i, s in enumerate(traj))
                    
                    t_idx, t_type = -1, "NONE"
                    for i, s in enumerate(traj):
                        pos = s['sa_spins'] if target == 'accumulation' else s.get('ss_spins', i+1)
                        f, _ = check_super_ensemble(s, traj, i, target, p1, p2, pt)
                        is_dup = (i > 0 and s['reel_1'] == traj[i-1]['reel_1'] and s['reel_2'] == traj[i-1]['reel_2'] and s['reel_3'] == traj[i-1]['reel_3'])
                        is_p = (not any_ens) and (abs(pos - pred_pos) <= 20)
                        if (f or is_p) and is_dup and t_idx == -1:
                            t_idx = i; t_type = "SNIPER" if f else "300-SUM"
                    
                    res = "CATCH" if (t_idx != -1 and len(traj)-1-t_idx <= 12) else ("FAIL" if t_idx != -1 else "MISSED")
                    out.write(f"E{eid} | Gap #{g_idx:03d} | Len: {len(traj):3d} | Pred: {pred_pos:3d} | Result: {res} | {t_type}\n")
                    
                    bet, cd = False, 0
                    start_view = max(0, t_idx - 5) if t_idx != -1 else max(0, len(traj)-15)
                    for k in range(start_view, len(traj)):
                        s = traj[k]; pos = s['sa_spins'] if target == 'accumulation' else s.get('ss_spins', k+1)
                        f, rule = check_super_ensemble(s, traj, k, target, p1, p2, pt)
                        is_dup = (k > 0 and s['reel_1'] == traj[k-1]['reel_1'] and s['reel_2'] == traj[k-1]['reel_2'] and s['reel_3'] == traj[k-1]['reel_3'])
                        is_p = (not any_ens) and (abs(pos - pred_pos) <= 20)
                        
                        if (f or is_p) and is_dup: bet = True; cd = 0
                        min_t = is_other_triple(s, target)
                        mod = ""
                        if min_t and bet: mod = f" <--- MINOR [{min_t.upper()}] (CD)"; cd = 5; bet = False
                        elif min_t: mod = f" <--- MINOR [{min_t.upper()}]"
                        if cd > 0: cd -= 1
                        if cd == 0 and k < (len(traj)-1) and k >= t_idx and t_idx != -1: bet = True
                        if bet: mod += " <--- [ HIGH BET $$$ ]"
                        if is_dup: mod += " (REEL DUP!)"
                        
                        tag = f"[{rule:12s}]" if f else ("[PRED]" if is_p else "[WAITING]")
                        if k == t_idx: mod += " <--- !!! ENTRY !!!"
                        if k == len(traj)-1: mod += " <--- 🎯 JACKPOT"
                        out.write(f"    T{k-max(0,t_idx):+03d} | SEQ:{str(s.get('seq','n/a')).rjust(6)} | POS:{str(pos).rjust(3)} | {tag} | [{s['reel_1'][:8]:8s}|{s['reel_2'][:8]:8s}|{s['reel_3'][:8]:8s}]{mod}\n")
                    out.write("-" * 110 + "\n\n")
    print("Strategy Strict Updated with Duplicate Highlights.")

if __name__ == "__main__":
    run_strategy_sim()
