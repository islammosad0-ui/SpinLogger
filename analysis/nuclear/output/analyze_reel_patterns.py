import pickle
import collections

def analyze_duplicate_patterns():
    pkl_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl"
    with open(pkl_path, "rb") as f:
        all_data = pickle.load(f)

    out_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\duplicate_reel_patterns.txt"
    with open(out_path, "w", encoding="utf-8") as out:
        out.write("=== REEL PATTERN ANALYSIS: DUPLICATES IN THE PRE-TRIPLE WINDOW ===\n")
        out.write("Checking for identical back-to-back reels in the 15 spins before a hit.\n\n")

        for target_triple_name in ['accumulation', 'spins']:
            out.write(f"============================================================\n")
            out.write(f"   TARGET: TRIPLE {target_triple_name.upper()}\n")
            out.write(f"============================================================\n\n")
            
            total_hits = 0
            hits_with_duplicates = 0
            
            for acct, d in all_data.items():
                spins = d['spins']
                acct_matches = []
                
                for i in range(15, len(spins)):
                    if spins[i]['triple'] == target_triple_name:
                        total_hits += 1
                        # Check the 15 spins before the hit
                        window = spins[i-15 : i]
                        
                        duplicates = []
                        for j in range(1, len(window)):
                            prev = window[j-1]
                            curr = window[j]
                            
                            # Check if r1, r2, r3 match exactly
                            if prev['reel_1'] == curr['reel_1'] and \
                               prev['reel_2'] == curr['reel_2'] and \
                               prev['reel_3'] == curr['reel_3']:
                                
                                # Found a duplicate!
                                t_pos = 15 - j
                                duplicates.append((t_pos + 1, t_pos, curr['reel_1'], curr['reel_2'], curr['reel_3']))
                        
                        if duplicates:
                            hits_with_duplicates += 1
                            acct_matches.append((i, window, duplicates, spins[i]))

                out.write(f"--- ACCOUNT: {acct} ---\n")
                if not acct_matches:
                    out.write("  None detected in this sequence.\n\n")
                else:
                    for global_idx, window, dups, hit_spin in acct_matches:
                        out.write(f"Hit at Index {global_idx}:\n")
                        for d_info in dups:
                            out.write(f"  [!] DUPLICATE FOUND: T-{d_info[0]:02d} and T-{d_info[1]:02d} match exactly!\n")
                            out.write(f"      Reels: [{d_info[2]} | {d_info[3]} | {d_info[4]}]\n")
                        
                        # Show context
                        out.write("  Sequence (T-15 to T-00):\n")
                        for offset, s in enumerate(window):
                            prefix = " "
                            # Mark the duplicates in the list
                            for d_info in dups:
                                if (15 - offset) == d_info[0] or (15 - offset) == d_info[1]:
                                    prefix = "*"
                            
                            r_str = f"[{s['reel_1']:12s} | {s['reel_2']:12s} | {s['reel_3']:12s}]"
                            out.write(f"    {prefix} T-{15 - offset:02d}: {r_str}\n")
                        
                        out.write(f"      T-00: [{hit_spin['reel_1']:12s} | {hit_spin['reel_2']:12s} | {hit_spin['reel_3']:12s}] <--- HIT\n")
                        out.write("-" * 50 + "\n")
                    out.write("\n")

            if total_hits > 0:
                pct = (hits_with_duplicates / total_hits) * 100
                out.write(f"SUMMARY FOR {target_triple_name.upper()}:\n")
                out.write(f"  Total Triples Observed: {total_hits}\n")
                out.write(f"  Triples preceded by a Duplicate in last 15: {hits_with_duplicates} ({pct:.1f}%)\n\n")

if __name__ == "__main__":
    analyze_duplicate_patterns()
