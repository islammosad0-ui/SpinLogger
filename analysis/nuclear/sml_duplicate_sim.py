import pickle
import collections
import numpy as np

def run_sml_duplicate_simulation():
    pkl_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl"
    with open(pkl_path, "rb") as f:
        all_data = pickle.load(f)

    out_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\sml_duplicate_simulation.txt"
    with open(out_path, "w", encoding="utf-8") as out:
        out.write("=== S/M/L + DUPLICATE REEL PINPOINT SIMULATION ===\n")
        out.write("Strategy: Use previous gap to PREDICT current gap type.\n")
        out.write("          Then look for duplicate reels in the predicted window.\n")
        out.write("          If duplicate found -> BET HIGH, triple is imminent.\n\n")

        for target_triple in ['accumulation', 'spins']:
            out.write(f"{'='*70}\n")
            out.write(f"   TARGET: TRIPLE {target_triple.upper()}\n")
            out.write(f"{'='*70}\n\n")

            # SML classification
            # S = Short (<80), M = Medium (80-130), L = Long (>130)
            # Prediction rules (from Zo Ki):
            #   After L -> expect S (scan 50-100)
            #   After S -> expect M (scan 80-130)  
            #   After M -> expect S or L (scan 50-100 first, then 130+)

            total_gaps = 0
            total_predicted_correctly = 0
            total_dup_found_in_window = 0
            total_dup_hit_within_5 = 0
            total_dup_hit_within_10 = 0
            total_high_bets = 0
            total_catches = 0

            for acct, d in all_data.items():
                spins = d['spins']
                
                # First, find all gap boundaries for this target
                triple_indices = []
                for i, s in enumerate(spins):
                    if s['triple'] == target_triple:
                        triple_indices.append(i)

                if len(triple_indices) < 3:
                    continue

                out.write(f"--- ACCOUNT: {acct} ({len(triple_indices)} hits) ---\n\n")

                acct_catches = 0
                acct_high_bets = 0
                acct_dup_signals = 0

                for gap_num in range(1, len(triple_indices)):
                    prev_gap_start = triple_indices[gap_num - 2] if gap_num >= 2 else 0
                    prev_gap_end = triple_indices[gap_num - 1]
                    curr_gap_end = triple_indices[gap_num]

                    prev_gap_length = prev_gap_end - prev_gap_start if gap_num >= 2 else None
                    curr_gap_length = curr_gap_end - prev_gap_end

                    if prev_gap_length is None:
                        continue  # Skip first gap, no previous to predict from

                    total_gaps += 1

                    # Classify previous gap
                    if prev_gap_length < 80:
                        prev_class = 'S'
                    elif prev_gap_length <= 130:
                        prev_class = 'M'
                    else:
                        prev_class = 'L'

                    # Classify current gap (ground truth)
                    if curr_gap_length < 80:
                        curr_class = 'S'
                    elif curr_gap_length <= 130:
                        curr_class = 'M'
                    else:
                        curr_class = 'L'

                    # PREDICTION: Based on Zo Ki rules
                    if prev_class == 'L':
                        predicted_class = 'S'
                        scan_start = 50
                        scan_end = 100
                    elif prev_class == 'S':
                        predicted_class = 'M'
                        scan_start = 80
                        scan_end = 130
                    else:  # M
                        predicted_class = 'S'
                        scan_start = 50
                        scan_end = 100

                    if curr_class == predicted_class:
                        total_predicted_correctly += 1

                    # Now scan the predicted window for duplicate reels
                    gap_start_idx = prev_gap_end + 1  # First spin of current gap

                    found_dup = False
                    dup_spin_offset = None
                    dup_reels = None

                    for spin_offset in range(scan_start, min(scan_end, curr_gap_length)):
                        abs_idx = gap_start_idx + spin_offset
                        if abs_idx <= 0 or abs_idx >= len(spins):
                            continue

                        prev_s = spins[abs_idx - 1]
                        curr_s = spins[abs_idx]

                        if (prev_s['reel_1'] == curr_s['reel_1'] and
                            prev_s['reel_2'] == curr_s['reel_2'] and
                            prev_s['reel_3'] == curr_s['reel_3']):
                            found_dup = True
                            dup_spin_offset = spin_offset
                            dup_reels = (curr_s['reel_1'], curr_s['reel_2'], curr_s['reel_3'])
                            break  # Take the first duplicate

                    if found_dup:
                        total_dup_found_in_window += 1
                        acct_dup_signals += 1

                        # How far is the actual triple from this duplicate?
                        distance_to_triple = curr_gap_length - dup_spin_offset

                        # Simulate: BET HIGH from duplicate signal for 15 spins
                        bet_window = 15
                        bets_used = min(bet_window, distance_to_triple + 1)
                        acct_high_bets += bets_used
                        total_high_bets += bets_used

                        caught = distance_to_triple <= bet_window
                        if caught:
                            acct_catches += 1
                            total_catches += 1

                        if distance_to_triple <= 5:
                            total_dup_hit_within_5 += 1
                        if distance_to_triple <= 10:
                            total_dup_hit_within_10 += 1

                        out.write(f"  Gap #{gap_num:3d} | Prev: {prev_class} ({prev_gap_length:3d}) | "
                                  f"Curr: {curr_class} ({curr_gap_length:3d}) | "
                                  f"Predicted: {predicted_class} | "
                                  f"Dup at spin {dup_spin_offset:3d} [{dup_reels[0][:8]:8s}|{dup_reels[1][:8]:8s}|{dup_reels[2][:8]:8s}] | "
                                  f"Triple {distance_to_triple:3d} spins later")
                        if caught:
                            out.write(f" *** CAUGHT ***\n")
                        else:
                            out.write(f"\n")

                mb_hit = acct_high_bets / max(1, acct_catches)
                out.write(f"\n  Account Summary: {acct_dup_signals} duplicate signals, "
                          f"{acct_catches} catches, {acct_high_bets} high bets, "
                          f"{mb_hit:.1f} mb/hit\n\n")

            # Overall Summary
            out.write(f"\n{'='*70}\n")
            out.write(f"OVERALL SUMMARY FOR {target_triple.upper()}:\n")
            out.write(f"  Total Gaps Analyzed: {total_gaps}\n")
            out.write(f"  S/M/L Prediction Accuracy: {total_predicted_correctly}/{total_gaps} "
                      f"({total_predicted_correctly/max(1,total_gaps)*100:.1f}%)\n")
            out.write(f"  Duplicate Signals Found in Window: {total_dup_found_in_window}\n")
            if total_dup_found_in_window > 0:
                out.write(f"  Triple landed within 5 spins of dup: {total_dup_hit_within_5} "
                          f"({total_dup_hit_within_5/total_dup_found_in_window*100:.1f}%)\n")
                out.write(f"  Triple landed within 10 spins of dup: {total_dup_hit_within_10} "
                          f"({total_dup_hit_within_10/total_dup_found_in_window*100:.1f}%)\n")
                out.write(f"  Triple CAUGHT (within 15 spins of dup): {total_catches} "
                          f"({total_catches/total_dup_found_in_window*100:.1f}%)\n")
            out.write(f"  Total High Bets Used: {total_high_bets}\n")
            out.write(f"  Total Catches: {total_catches}\n")
            if total_catches > 0:
                out.write(f"  Efficiency: {total_high_bets/total_catches:.1f} mb/hit\n")
            out.write(f"{'='*70}\n\n")

if __name__ == "__main__":
    run_sml_duplicate_simulation()
