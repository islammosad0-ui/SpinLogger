import pickle
import numpy as np

print("Loading data...")
PKL = 'c:/Users/Islam/Desktop/Coin Master/SpinLogger/analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)


print("\n--- Phase Tracking Theory ---")
# Theory: If Accumulation drops, how long until Spins drop, based on the existing ss_spins gap?
# He says: "Wait 120 spins. Accumulation drops. Spins dropped at 50. So it's been 70 spins without Spins. So Spins will drop in 50-60 spins."
# Let's test this mathematically.

phase_gaps = []

for acct in data.keys():
    for sess in [0, 1]:
        spins = [s for s in data[acct]['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
        if not spins: continue
        
        # We want to find: When ACC drops, what was the current `ss_spins`?
        # And when does the NEXT SPN drop?
        
        current_ss_spins = 0
        current_sa_acc = 0
        
        # To find the next SPN, we need forward looking
        for i in range(len(spins)):
            t = spins[i].get('triple')
            
            if t == 'spins':
                current_ss_spins = 0
            else:
                current_ss_spins += 1
                
            if t == 'accumulation':
                current_sa_acc = 0
                
                # Acc dropped! What is the current ss_spins offset?
                offset = current_ss_spins
                
                # How long until the NEXT Spin triple?
                spins_until_next_spn = -1
                for j in range(i+1, len(spins)):
                    if spins[j].get('triple') == 'spins':
                        spins_until_next_spn = j - i
                        break
                        
                if spins_until_next_spn > 0:
                    phase_gaps.append((offset, spins_until_next_spn))
                    
            else:
                current_sa_acc += 1

print(f"Recorded Phase Shifts: {len(phase_gaps)}")

# Let's analyze. If offset + spins_until_next_spn == ~120-130 constantly, he is right.
total_cycle_lengths = [offset + nxt for offset, nxt in phase_gaps]

print(f"\nAverage Combined Cycle (Offset + Next Gap): {np.mean(total_cycle_lengths):.1f}")
print(f"Median Combined Cycle: {np.median(total_cycle_lengths)}")

print("\n--- Specific Example Math ---")
# "70 Drehs ohne 3 Kapseln . Heißt die kommen spätestens bei 50-60 Drehs wieder"
# He predicts the combined cycle is 120-130!
seventies = [nxt for offset, nxt in phase_gaps if 65 <= offset <= 75]
print(f"If offset is ~70, Average Next Gap to Spins: {np.mean(seventies) if seventies else 0:.1f} (He says 50-60)")

eighties = [nxt for offset, nxt in phase_gaps if 76 <= offset <= 86]
print(f"If offset is ~80, Average Next Gap to Spins: {np.mean(eighties) if eighties else 0:.1f} (Should be 40-50)")

forties_to_sixties = [offset + nxt for offset, nxt in phase_gaps if 40 <= offset <= 60]
print(f"If offset is 40-60, Combined cycle is: {np.mean(forties_to_sixties):.1f}")

hist, edges = np.histogram(total_cycle_lengths, bins=[0, 50, 80, 100, 120, 140, 160, 200, 300])
print("\nHistogram of Total Cycle Lengths (Offset + Next Gap):")
for i in range(len(hist)):
    print(f"  {edges[i]:>3} to {edges[i+1]:>3}: {hist[i]} times")
