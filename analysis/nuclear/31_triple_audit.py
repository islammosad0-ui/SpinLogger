import pickle

PKL = 'analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)

def audit_triple_types(account):
    print(f"\n--- Triple Type Audit for {account} ---")
    for sess in [0, 1]:
        spins = [s for s in data[account]['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
        if not spins: continue
        
        counts = {'accumulation': 0, 'spins': 0, 'shield': 0, 'attack': 0, 'steal': 0, 'total': 0}
        
        for s in spins:
            t = s.get('triple')
            if t:
                counts['total'] += 1
                counts[t] = counts.get(t, 0) + 1
        
        print(f"\nSession {sess}: {counts['total']} total triples")
        reward_triples = counts['accumulation'] + counts['spins']
        print(f"  REWARD TRIPLES (ACC+SPN): {reward_triples} ({reward_triples/counts['total']*100:.1f}%)")
        for t, c in counts.items():
            if t != 'total':
                print(f"    - {t:<13}: {c} ({c/counts['total']*100:.1f}%)")

audit_triple_types('Islam')
audit_triple_types('Ahmed')
