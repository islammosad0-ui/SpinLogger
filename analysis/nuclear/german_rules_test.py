import pickle
from pathlib import Path
import os
import numpy as np

def run_zo_ki_test():
    pkl_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl"
    with open(pkl_path, "rb") as f:
        all_data = pickle.load(f)

    # 1. Gather all ACC gaps across all accounts in sequence
    # For sequence tracking we must retain order per account/session.
    
    print("=== ZO KI STRATEGY BACKTEST ===")
    print("Testing against 28k+ logged spins\n")
    
    for acct_name, d in all_data.items():
        gaps = d['gaps']['accumulation']
        gap_lengths = [g['length'] for g in gaps]
        if not gap_lengths:
            continue
            
        print(f"--- ACCOUNT: {acct_name} ({len(gap_lengths)} ACC gaps) ---")
        
        # --- RULE 1: LONG RUN -> 2 SHORT RUNS ---
        for long_thresh in [120, 130, 140, 150, 160]:
            total_longs = 0
            matches = 0
            for i in range(len(gap_lengths) - 2):
                if gap_lengths[i] >= long_thresh:
                    total_longs += 1
                    # German rule: next two runs under 100
                    if gap_lengths[i+1] < 100 and gap_lengths[i+2] < 100:
                        matches += 1
            if total_longs > 0:
                pct = matches/total_longs*100
                print(f"  Long Lauf > {long_thresh:3d}: {total_longs} occurrences -> {matches} had two following < 100 ({pct:.1f}%)")

        # --- RULE 2: CAPSULE REPLACEMENT (Spins/Energy triples delaying the Event triple) ---
        # Look at gaps that had SPINS triples inside them
        print("\n  --- Rule 2: Capsule Replacement Analysis ---")
        caps_inside_lengths = []
        no_caps_lengths = []
        for g in gaps:
            has_capsule = False
            for s in g['trajectory']:
                # count capsule triples
                if s['spn_count'] > 0 or s['triple'] == 'spins':
                    has_capsule = True
                    break
            if has_capsule:
                caps_inside_lengths.append(g['length'])
            else:
                no_caps_lengths.append(g['length'])
        
        if caps_inside_lengths and no_caps_lengths:
            print(f"  Average ACC gap width WHEN NO Capsules hit  : {np.mean(no_caps_lengths):.1f} spins (n={len(no_caps_lengths)})")
            print(f"  Average ACC gap width WHEN Capsules replaced: {np.mean(caps_inside_lengths):.1f} spins (n={len(caps_inside_lengths)})")
            
        print("\n")

if __name__ == "__main__":
    run_zo_ki_test()
