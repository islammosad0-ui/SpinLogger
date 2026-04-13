import pickle

PKL = 'analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)

def hunt_refuel_windows(account):
    print(f"\n--- HUNTING REFUEL WINDOWS (>10% SPN hit rate) for {account} ---")
    spins = [s for s in data[account]['spins'] if s['gae_segment'] != '']
    
    def is_spn(s):
        return s.get('triple') == 'spins'

    # Check various "Overdue" thresholds for SPINS specifically
    for threshold in [80, 100, 120, 140, 160]:
        matching = [s for s in spins if s['ss_spins'] >= threshold]
        if not matching: continue
        hits = [s for s in matching if is_spn(s)]
        print(f"SPN Overdue > {threshold}: {len(hits)}/{len(matching)} ({len(hits)/len(matching)*100:.1f}%)")

    # Check Shield density during SPN overdue
    for threshold in [100, 120, 140]:
        matching = [s for s in spins if s['ss_spins'] >= threshold and s['shd_count'] >= 1]
        if not matching: continue
        hits = [s for s in matching if is_spn(s)]
        if hits:
            print(f"SPN Overdue > {threshold} + Shield Spike: {len(hits)}/{len(matching)} ({len(hits)/len(matching)*100:.1f}%)")

hunt_refuel_windows('Islam')
