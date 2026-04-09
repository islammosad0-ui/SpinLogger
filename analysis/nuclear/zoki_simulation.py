import pickle
import numpy as np

def run_simulation():
    pkl_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl"
    with open(pkl_path, "rb") as f:
        all_data = pickle.load(f)

    def run_zoki_sim(spins_stream):
        total_spins = 0
        high_bets = 0
        
        acc_catches = 0
        spn_catches = 0
        
        last_three_gaps = []
        current_acc_gap_spins = 0
        current_spn_gap_spins = 0
        spins_since_any_win = 999
        
        for s in spins_stream:
            bet_high = False
            
            # ZoKi Rule 1: "After 100 spins, go for the wins"
            if current_acc_gap_spins >= 100:
                bet_high = True
                
            # ZoKi Rule 2: "Continuous Capsule count" - target 85
            if current_spn_gap_spins >= 75:
                bet_high = True

            # ZoKi Rule 3: The L -> S -> S Tracker
            if len(last_three_gaps) >= 3:
                L, S1, S2 = last_three_gaps[-3], last_three_gaps[-2], last_three_gaps[-1]
                # If sequence confirms "Long -> Short -> Short" - heavily target "Medium" (110-130)
                if L >= 140 and S1 <= 100 and S2 <= 100:
                    if 110 <= current_acc_gap_spins <= 130:
                        bet_high = True
                    else:
                        bet_high = False # Outside the sweet spot
            
            # ZoKi Rule 4: "Immer nach einem Gewinn runter wieder" 
            # (Always down to x1 after any win). We enforce a 10-spin rest.
            if spins_since_any_win < 10:
                bet_high = False
                
            # Execution
            total_spins += 1
            if bet_high:
                high_bets += 1
                if s['triple'] == 'accumulation':
                    acc_catches += 1
                if s['triple'] == 'spins':
                    spn_catches += 1
                    
            # State Updates
            current_acc_gap_spins += 1
            current_spn_gap_spins += 1
            spins_since_any_win += 1
            
            if s['triple'] in ['attack', 'steal', 'shield', 'spins', 'accumulation']:
                spins_since_any_win = 0
                
            if s['triple'] == 'accumulation':
                last_three_gaps.append(current_acc_gap_spins)
                current_acc_gap_spins = 0
                
            if s['triple'] == 'spins':
                current_spn_gap_spins = 0
                
        return total_spins, high_bets, acc_catches, spn_catches, len(last_three_gaps)

    with open(r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\zoki_sim_results.txt", "w", encoding="utf-8") as out:
        out.write("=== ZO KI STRATEGY SIMULATION (28K SPINS) ===\n\n")
        out.write("Betting Rules Engaged:\n")
        out.write("- Base bet HIGH if Spins > 100\n")
        out.write("- Base bet HIGH if Capsule Drought > 75\n")
        out.write("- Sequence Lock: If L -> S -> S, ONLY bet HIGH strictly between 110-130\n")
        out.write("- Power Rest: STRICT 'x1' enforced for 10 spins after ANY secondary win\n\n")
        
        total_a_catch = 0
        total_gaps = 0
        total_hbets = 0

        for acct, d in all_data.items():
            stream = d['spins']
            total, h_bets, a_catch, s_catch, tot_gaps = run_zoki_sim(stream)
            
            total_a_catch += a_catch
            total_gaps += tot_gaps
            total_hbets += h_bets
            
            mb_hit_acc = (h_bets / max(1, a_catch)) if a_catch > 0 else 0
            
            out.write(f"--- {acct} ---\n")
            out.write(f"Total Spins Played : {total}\n")
            out.write(f"High Bet Spins Mode: {h_bets} ({(h_bets/total)*100:.1f}%)\n")
            out.write(f"Event Triples Hit  : {a_catch} / {tot_gaps} ({a_catch/max(1,tot_gaps)*100:.1f}%)\n")
            out.write(f"Capsule Triples Hit: {s_catch}\n")
            out.write(f"Efficiency Metrics : {mb_hit_acc:.1f} high-bets per Event Triple Catch\n\n")

        overall_mb = total_hbets / max(1, total_a_catch)
        out.write("--- OVERALL ---\n")
        out.write(f"Total Event Catches: {total_a_catch} / {total_gaps} ({total_a_catch/total_gaps*100:.1f}%)\n")
        out.write(f"Mean Bets per Catch: {overall_mb:.1f} mb/hit\n")

if __name__ == "__main__":
    run_simulation()
