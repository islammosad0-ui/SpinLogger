import pickle
import collections
import json

def construct_rng_constraints():
    pkl_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl"
    with open(pkl_path, "rb") as f:
        all_data = pickle.load(f)

    report_path = r"C:\Users\Islam Nawwar\SpinLogger\analysis\cryptography\z3_constraints_report.txt"
    with open(report_path, "w", encoding="utf-8") as out:
        out.write("=== PRNG CRYPTOGRAPHIC CONSTRAINT GENERATOR ===\n\n")
        
        for acct, d in all_data.items():
            spins = d['spins']
            
            # 1. Compute empirical probability table for Reel 1
            # Reel 1 is typically chosen to be isolated from payline combo modifiers
            r1_counts = collections.Counter([s['reel_1'] for s in spins])
            total_spins = sum(r1_counts.values())
            
            # Sort by frequency
            sorted_symbols = sorted(r1_counts.items(), key=lambda x: x[1], reverse=True)
            
            out.write(f"--- ACCOUNT: {acct} ---\n")
            out.write(f"Total Spins Logged: {total_spins}\n")
            
            out.write("Reel 1 Underlying Probability Distribution:\n")
            cumulative_prob = 0.0
            prob_bounds = {}
            for sym, count in sorted_symbols:
                prob = count / total_spins
                lower_bound = cumulative_prob
                upper_bound = cumulative_prob + prob
                out.write(f"  Symbol '{sym:15s}': {prob*100:5.2f}%  [Range: {lower_bound:.4f} to {upper_bound:.4f}]\n")
                prob_bounds[sym] = (lower_bound, upper_bound)
                cumulative_prob = upper_bound
                
            out.write("\n")
            
            # 2. Extract a continuous unbroken 20-spin chain for Z3 tests
            # We must pick a chain from the exact same session so there are no time gaps
            if len(spins) < 20: 
                continue
                
            # Grab the very first 20 spins from the first session
            test_chain = []
            for s in spins[:20]:
                test_chain.append(s['reel_1'])
                
            out.write("Sample Unbroken 20-Spin Target Sequence:\n")
            out.write("  " + " -> ".join([str(x) for x in test_chain]) + "\n\n")
            
            out.write("Resulting SMT Solver (Z3) Constraints (Pseudo-code):\n")
            for i, sym in enumerate(test_chain):
                bounds = prob_bounds.get(sym)
                out.write(f"  Spin {i+1:02d} ({sym:10s}): PRNG_Output[{i}] / MAX >= {bounds[0]:.4f} AND PRNG_Output[{i}] / MAX < {bounds[1]:.4f}\n")
            
            out.write("\n" + "="*60 + "\n\n")

if __name__ == "__main__":
    construct_rng_constraints()
