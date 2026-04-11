import pickle
from collections import deque

PKL = 'analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)

def hunt(account):
    print(f"\n--- Hunting Magic Signals for {account} ---")
    sessions = [0, 1]
    
    for sess in sessions:
        spins = [s for s in data[account]['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
        if not spins: continue
        
        print(f"\nSession {sess}: {len(spins)} spins")
        
        # 1. Look for "Cluster" probability
        # If we just hit a triple, what is the probability of another within 30 spins?
        triples = [i for i, s in enumerate(spins) if s.get('triple')]
        distances = [triples[i+1] - triples[i] for i in range(len(triples)-1)]
        
        clusters = [d for d in distances if d <= 30]
        print(f"  Total Triples: {len(triples)}")
        print(f"  Clusters (<=30 spins): {len(clusters)} ({len(clusters)/len(triples)*100:.1f}%)")
        
        # 2. Look for "Pity" probability
        # If gap > 150, what's the hit rate in the next 50 spins?
        long_gaps = [i for i, s in enumerate(spins) if s['sa_spins'] > 150]
        hits_after_pity = 0
        total_pity_spins = 0
        for i in range(len(spins)-1):
            if spins[i]['sa_spins'] > 150:
                total_pity_spins += 1
                if spins[i+1].get('triple'):
                    hits_after_pity += 1
        
        if total_pity_spins > 0:
            print(f"  Hit rate at sa_spins > 150: {hits_after_pity/total_pity_spins*100:.1f}%")
        
        # 3. Look for "Symbol" signals
        # Check if hitting 3+ of any symbol (Shield/Attack/Steal) in last 5 spins helps
        sym_hits = 0
        sym_total = 0
        for i in range(5, len(spins)-1):
            window = spins[i-5:i]
            shields = sum(s['shd_count'] for s in window)
            if shields >= 3:
                sym_total += 1
                if spins[i+1].get('triple'):
                    sym_hits += 1
        if sym_total > 0:
            print(f"  Hit rate after 3+ Shields in 5 spins: {sym_hits/sym_total*100:.2f}% (Count: {sym_total})")

        # 4. Check "Spins/ACC Rate"
        # If spins triple is "due", does it improve ACC hit rate?
        ss_hits = 0
        ss_total = 0
        for i in range(len(spins)-1):
            if spins[i]['ss_spins'] > 120:
                ss_total += 1
                if spins[i+1].get('triple'):
                    ss_hits += 1
        if ss_total > 0:
            print(f"  ACC hit rate when ss_spins > 120: {ss_hits/ss_total*100:.2f}% (Count: {ss_total})")

hunt('Islam')
hunt('Ahmed') # For comparison
