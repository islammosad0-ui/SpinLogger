import pickle

PKL = 'analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)

def find_reward_signature(account):
    print(f"\n--- Searching for Reward-Specific Signatures for {account} ---")
    spins = [s for s in data[account]['spins'] if s['gae_segment'] != '']
    
    # Analyze windows of 10 spins before different triple types
    types = ['accumulation', 'spins', 'attack', 'shield']
    
    for t in types:
        print(f"\nSignature for '{t}':")
        # Collect stats for windows before triple type 't'
        windows = []
        for i in range(10, len(spins)):
            if spins[i].get('triple') == t:
                windows.append(spins[i-10:i])
        
        if not windows: continue
        
        avg_acc = sum(sum(s['acc_count'] for s in w) for w in windows) / len(windows)
        avg_atk = sum(sum(s['atk_count'] for s in w) for w in windows) / len(windows)
        avg_shd = sum(sum(s['shd_count'] for s in w) for w in windows) / len(windows)
        avg_spn = sum(sum(s['spn_count'] for s in w) for w in windows) / len(windows)
        
        print(f"  Avg ACC symbols: {avg_acc:.2f}")
        print(f"  Avg ATK symbols: {avg_atk:.2f}")
        print(f"  Avg SHD symbols: {avg_shd:.2f}")
        print(f"  Avg SPN symbols: {avg_spn:.2f}")

find_reward_signature('Islam')
