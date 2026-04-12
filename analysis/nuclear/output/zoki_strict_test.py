import pickle
from pathlib import Path
import numpy as np

def run_pure_zoki_test():
    pkl_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl"
    with open(pkl_path, "rb") as f:
        all_data = pickle.load(f)

    with open(r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\zoki_strict_report.txt", "w", encoding="utf-8") as out_f:
        out_f.write("=== PURE ZO-KI STRATEGY BACKTEST ===\n\n")

        all_acc_gaps = []
        all_spn_gaps = []
        
        for acct, d in all_data.items():
            acc_gaps = [g['length'] for g in d['gaps']['accumulation']]
            spn_gaps = [g['length'] for g in d['gaps']['spins']]
            
            all_acc_gaps.extend(acc_gaps)
            all_spn_gaps.extend(spn_gaps)
            
        out_f.write(f"Total ACC (Event) Gaps  : {len(all_acc_gaps)}\n")
        out_f.write(f"Total SPN (Capsule) Gaps: {len(all_spn_gaps)}\n\n")

        # ---------------------------------------------------------
        # TEST 1: The "L -> S -> S -> M" Cycle
        # ---------------------------------------------------------
        out_f.write("TEST 1: The 'Long -> Short -> Short -> Medium' Cycle\n")
        out_f.write("  Rule: If gap > 150, expect next two < 100, then expect 110-130.\n")
        
        long_count = 0
        long_then_short = 0
        long_then_two_shorts = 0
        perfect_cycle_matches = 0
        
        for i in range(len(all_acc_gaps) - 3):
            # Is it a Long Lauf? (150+)
            if all_acc_gaps[i] >= 150:
                long_count += 1
                # Is next one short? (<100)
                if all_acc_gaps[i+1] < 100:
                    long_then_short += 1
                    # Is second one short? (<100)
                    if all_acc_gaps[i+2] < 100:
                        long_then_two_shorts += 1
                        # Is the third one Medium? (110-130)
                        if 110 <= all_acc_gaps[i+3] <= 130:
                            perfect_cycle_matches += 1
                            
        out_f.write(f"  Times a Long run (>150) occurred: {long_count}\n")
        if long_count > 0:
            out_f.write(f"  -> Followed by ONE Short (<100) : {long_then_short} ({long_then_short/long_count*100:.1f}%)\n")
            out_f.write(f"  -> Followed by TWO Shorts       : {long_then_two_shorts} ({long_then_two_shorts/long_count*100:.1f}%)\n")
            out_f.write(f"  -> TWO Shorts then a Medium (110-130): {perfect_cycle_matches} ({perfect_cycle_matches/long_count*100:.1f}%)\n\n")

        out_f.write("  Let's expand the Medium definition to 100-140 just in case:\n")
        perfect_expanded = sum(1 for i in range(len(all_acc_gaps)-3) 
                               if all_acc_gaps[i] >= 150 
                               and all_acc_gaps[i+1] < 100 
                               and all_acc_gaps[i+2] < 100 
                               and 100 <= all_acc_gaps[i+3] <= 140)
        out_f.write(f"  -> TWO Shorts then Expanded Medium (100-140): {perfect_expanded} ({perfect_expanded/max(1,long_count)*100:.1f}%)\n\n")

        # ---------------------------------------------------------
        # TEST 2: The Capsule Triple "2-3 Shorts then Very Long" Pattern
        # ---------------------------------------------------------
        out_f.write("TEST 2: The Capsule (SPN) Triple Pattern\n")
        out_f.write("  Rule: '2-3 times short, very long'\n")
        
        # Define short as < 100, very long as > 150
        spn_two_shorts = 0
        spn_long_after_two = 0
        
        for i in range(len(all_spn_gaps) - 2):
            if all_spn_gaps[i] < 100 and all_spn_gaps[i+1] < 100:
                spn_two_shorts += 1
                if all_spn_gaps[i+2] >= 150:
                    spn_long_after_two += 1
                    
        out_f.write(f"  Times we had 2 consecutive Short Capsule gaps (<100): {spn_two_shorts}\n")
        if spn_two_shorts > 0:
            out_f.write(f"  -> Followed by a Very Long (>150): {spn_long_after_two} ({spn_long_after_two/spn_two_shorts*100:.1f}%)\n")
            
        spn_three_shorts = 0
        spn_long_after_three = 0
        for i in range(len(all_spn_gaps) - 3):
            if all_spn_gaps[i] < 100 and all_spn_gaps[i+1] < 100 and all_spn_gaps[i+2] < 100:
                spn_three_shorts += 1
                if all_spn_gaps[i+3] >= 150:
                    spn_long_after_three += 1
        
        out_f.write(f"  Times we had 3 consecutive Short Capsule gaps (<100): {spn_three_shorts}\n")
        if spn_three_shorts > 0:
            out_f.write(f"  -> Followed by a Very Long (>150): {spn_long_after_three} ({spn_long_after_three/spn_three_shorts*100:.1f}%)\n\n")

        out_f.write(f"  Average Capsule Gap length overall: {np.mean(all_spn_gaps):.1f} spins\n\n")

        # ---------------------------------------------------------
        # TEST 3: Capsule Distance INDEPENDENT of ACC boundaries
        # ---------------------------------------------------------
        out_f.write("TEST 3: Continuous Capsule Counting ('Drought' tracking)\n")
        out_f.write("  Rule: If Capsules didn't hit for X spins at the end of an ACC run, they will hit around 100-X in the next run.\n")
        out_f.write("  We already track `ss_spins` which does exactly this. \n")
        out_f.write("  Let's see the variation: how many spins does a Capsule gap take normally?\n")
        
        # Generate buckets for SPINS lengths
        bins = [0, 50, 100, 150, 200, 500]
        hist, _ = np.histogram(all_spn_gaps, bins=bins)
        
        out_f.write("  Capsule Gap Size Distribution:\n")
        out_f.write(f"  0-50 spins  : {hist[0]} gaps ({hist[0]/len(all_spn_gaps)*100:.1f}%)\n")
        out_f.write(f"  50-100 spins: {hist[1]} gaps ({hist[1]/len(all_spn_gaps)*100:.1f}%)\n")
        out_f.write(f"  100-150 rng : {hist[2]} gaps ({hist[2]/len(all_spn_gaps)*100:.1f}%)\n")
        out_f.write(f"  150-200 rng : {hist[3]} gaps ({hist[3]/len(all_spn_gaps)*100:.1f}%)\n")
        out_f.write(f"  200+ spins  : {hist[4]} gaps ({hist[4]/len(all_spn_gaps)*100:.1f}%)\n")

if __name__ == "__main__":
    run_pure_zoki_test()
