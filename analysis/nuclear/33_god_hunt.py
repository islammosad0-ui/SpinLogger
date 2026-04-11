import pickle

PKL = 'analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)

def hunt_god_windows(account):
    print(f"\n--- HUNTING GOD WINDOWS (>20% hit rate) for {account} ---")
    spins = [s for s in data[account]['spins'] if s['gae_segment'] != '']
    
    # We are looking for REWARD TRIPLES specifically (ACC + SPN)
    def is_reward(s):
        return s.get('triple') in ['accumulation', 'spins']

    # Candidate 1: Extreme Pity
    for threshold in [160, 170, 180, 190]:
        matching = [s for s in spins if s['sa_spins'] >= threshold]
        if not matching: continue
        hits = [s for s in matching if is_reward(s)]
        print(f"Pity > {threshold}: {len(hits)}/{len(matching)} ({len(hits)/len(matching)*100:.1f}%)")

    # Candidate 2: Shield Density + Mature Gap
    for sp_thresh in [120, 140, 160]:
        for sh_thresh in [0.4, 0.5]:
            matching = [s for s in spins if s['sa_spins'] >= sp_thresh and (s['shd_count']/10) >= sh_thresh] # rough density check
            if not matching: continue
            hits = [s for s in matching if is_reward(s)]
            if len(hits) > 5:
                print(f"Gap > {sp_thresh} & Shields > {sh_thresh}: {len(hits)}/{len(matching)} ({len(hits)/len(matching)*100:.1f}%)")

    # Candidate 3: Post-Triple Cluster Sniper (0-10 spins after any triple)
    matching = []
    last_hit = -100
    for i, s in enumerate(spins):
        if s.get('triple'):
            last_hit = i
        elif i - last_hit <= 10:
            matching.append(s)
            
    if matching:
        hits = [s for s in matching if is_reward(s)]
        print(f"Post-Triple Frenzy (0-10): {len(hits)}/{len(matching)} ({len(hits)/len(matching)*100:.1f}%)")

hunt_god_windows('Islam')
