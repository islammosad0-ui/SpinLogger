import pickle
from pathlib import Path
import os
import numpy as np

def run_zo_ki_test():
    pkl_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl"
    with open(pkl_path, "rb") as f:
        all_data = pickle.load(f)

    with open(r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\clean_output.txt", "w", encoding="utf-8") as out_f:
        out_f.write("=== ZO KI STRATEGY BACKTEST ===\n")
        out_f.write("Testing against 28k+ logged spins\n\n")
        
        for acct_name, d in all_data.items():
            gaps = d['gaps']['accumulation']
            gap_lengths = [g['length'] for g in gaps]
            if not gap_lengths:
                continue
                
            out_f.write(f"--- ACCOUNT: {acct_name} ({len(gap_lengths)} ACC gaps) ---\n")
            
            # --- RULE 1: LONG RUN -> 2 SHORT RUNS ---
            for long_thresh in [120, 130, 140, 150, 160]:
                total_longs = 0
                matches = 0
                for i in range(len(gap_lengths) - 2):
                    if gap_lengths[i] >= long_thresh:
                        total_longs += 1
                        if gap_lengths[i+1] < 100 and gap_lengths[i+2] < 100:
                            matches += 1
                if total_longs > 0:
                    pct = matches/total_longs*100
                    out_f.write(f"  Long Lauf > {long_thresh:3d}: {total_longs} occurrences -> {matches} had two following < 100 ({pct:.1f}%)\n")

            # BASELINE Probability of 2 short runs:
            total_pairs = len(gap_lengths) - 1
            if total_pairs > 0:
                short_pairs = sum(1 for i in range(total_pairs) if gap_lengths[i] < 100 and gap_lengths[i+1] < 100)
                baseline_pct = short_pairs / total_pairs * 100
                out_f.write(f"  [BASELINE] Normal chance of getting two gaps < 100 in a row: {baseline_pct:.1f}%\n")

            # --- RULE 2: CAPSULE REPLACEMENT (Spins/Energy triples delaying the Event triple) ---
            out_f.write("\n  --- Rule 2: Capsule Replacement Analysis ---\n")
            caps_inside_lengths = []
            no_caps_lengths = []
            for g in gaps:
                has_capsule = False
                for s in g['trajectory']:
                    if s['spn_count'] > 0 or s['triple'] == 'spins':
                        has_capsule = True
                        break
                if has_capsule:
                    caps_inside_lengths.append(g['length'])
                else:
                    no_caps_lengths.append(g['length'])
            
            if caps_inside_lengths and no_caps_lengths:
                out_f.write(f"  Average ACC gap width WHEN NO Capsules hit  : {np.mean(no_caps_lengths):.1f} spins (n={len(no_caps_lengths)})\n")
                out_f.write(f"  Average ACC gap width WHEN Capsules replaced: {np.mean(caps_inside_lengths):.1f} spins (n={len(caps_inside_lengths)})\n")
                
            out_f.write("\n")

if __name__ == "__main__":
    run_zo_ki_test()
