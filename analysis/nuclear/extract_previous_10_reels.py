import pickle
import numpy as np
import collections

def analyze_all_10_reels():
    pkl_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl"
    with open(pkl_path, "rb") as f:
        all_data = pickle.load(f)

    out_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\all_pre_triple_reels.txt"
    with open(out_path, "w", encoding="utf-8") as out:
        out.write("=== FULL DATASET: PREVIOUS 10 REELS BEFORE EVERY TRIPLE ===\n\n")

        for target_triple_name in ['accumulation', 'spins']:
            out.write(f"============================================================\n")
            out.write(f"   TARGET: TRIPLE {target_triple_name.upper()}\n")
            out.write(f"============================================================\n\n")
            
            for acct, d in all_data.items():
                spins = d['spins']
                
                # Collect all sequences
                hits = []
                for i in range(10, len(spins)):
                    if spins[i]['triple'] == target_triple_name:
                        # Store index and the 10 prior spins
                        hits.append((i, spins[i-10 : i+1])) 
                
                out.write(f"--- ACCOUNT: {acct} ({len(hits)} hits) ---\n\n")
                
                for idx, (original_idx, sequence) in enumerate(hits):
                    out.write(f"Hit #{idx+1} (Global Index: {original_idx})\n")
                    # First 10 are the pre-triple spins
                    for t_offset in range(10):
                        s = sequence[t_offset]
                        r1 = s['reel_1'][:10]
                        r2 = s['reel_2'][:10]
                        r3 = s['reel_3'][:10]
                        out.write(f"  T-{10 - t_offset:02d}: [{r1:10s} | {r2:10s} | {r3:10s}]\n")
                    
                    # The actual hit
                    hit = sequence[10]
                    out.write(f"  T-00: [{hit['reel_1']:10s} | {hit['reel_2']:10s} | {hit['reel_3']:10s}] <--- HIT\n")
                    out.write("-" * 40 + "\n")
                
                out.write("\n\n")

if __name__ == "__main__":
    analyze_all_10_reels()
