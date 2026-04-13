import pickle
import numpy as np

print("Loading data...")
PKL = 'c:/Users/Islam/Desktop/Coin Master/SpinLogger/analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)

# The German player's theory: Triples (ANY triple or specifically ACC+SPN?) follow a sequence.
# Let's extract all gaps between ANY "Major" triple (Accumulation or Spins). 
# Wait, he said: "Kommen 3 Kapseln bei 139 Drehs, haben die 3 Symbole ersetzt." -> Spins REPLACE accumulation. 
# "Immer nach einem Gewinn runter wieder. Die 3 Kapseln haben auch ihre Abstände , ähnlich wie die 3 Symbole" -> Go down after ANY WIN.
# So ANY triple resets the counter or modifies the sequence?
# Let's look at the gap between ANY Triple (Pig, Hammer, Shield, Spin, Accumulation).
# Wait, he said: "Gibt ja 4 Gewinne. (Kapseln, Hämmer, Schweine, Schild)". 
# Actually, Pigs, Hammers, Shields, Spins are the 4 base wins. Accumulation is the Event win.
# He says after 100 spins, watch for ANY win. So ALL triples count towards resetting the local counter? 

all_triple_gaps = []

for acct in data.keys():
    for sess in [0, 1]:
        spins = [s for s in data[acct]['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
        current_gap = 0
        gaps = []
        for s in spins:
            current_gap += 1
            t = s.get('triple')
            if t in ['accumulation', 'spins']:
                gaps.append((t, current_gap))
                current_gap = 0
        if gaps:
            all_triple_gaps.append(gaps)

# Let's categorize gap lengths:
# Short: < 100
# Medium: 100 - 135
# Long: > 135
def categorize(gap):
    if gap < 100: return 'S'
    elif gap <= 140: return 'M'
    else: return 'L'

print("\n--- Sequence Analysis (ACC + SPINS tripes) ---")
for i, gaps in enumerate(all_triple_gaps[:2]): # Just look at the first two sessions directly
    print(f"\nSession {i} Sequence of Gaps:")
    seq = [categorize(g) for t, g in gaps]
    print(" -> ".join(seq))

# Let's analyze transitions!
transitions = {}
for gaps in all_triple_gaps:
    cats = [categorize(g) for t, g in gaps]
    for i in range(len(cats) - 1):
        tr = f"{cats[i]} -> {cats[i+1]}"
        transitions[tr] = transitions.get(tr, 0) + 1

print("\n--- Markov Transitions ---")
for k, v in sorted(transitions.items()):
    print(f"{k}: {v}")
    
# Let's look at sequences of 3
seq3 = {}
for gaps in all_triple_gaps:
    cats = [categorize(g) for t, g in gaps]
    for i in range(len(cats) - 2):
        tr = f"{cats[i]} -> {cats[i+1]} -> {cats[i+2]}"
        seq3[tr] = seq3.get(tr, 0) + 1

print("\n--- 3-Sequence Patterns ---")
for k, v in sorted(seq3.items(), key=lambda item: item[1], reverse=True)[:10]:
    print(f"{k}: {v}")

# He said: "Kommt langer Lauf, danach tausend pro 2 mal kurz ... Dann kommt der mittlere."
# L -> S -> S -> M. Let's trace after L -> S -> S.
l_s_s_followed_by = []
for gaps in all_triple_gaps:
    cats = [categorize(g) for t, g in gaps]
    for i in range(len(cats) - 3):
        if cats[i] == 'L' and cats[i+1] == 'S' and cats[i+2] == 'S':
            l_s_s_followed_by.append(cats[i+3])

print(f"\n--- What follows L -> S -> S? (N={len(l_s_s_followed_by)}) ---")
from collections import Counter
print(Counter(l_s_s_followed_by))

# Another check: What happens after L?
after_l = [cats[i+1] for gaps in all_triple_gaps for cats in [[categorize(g) for t, g in gaps]] for i in range(len(cats)-1) if cats[i] == 'L']
print(f"\n--- What follows L? (N={len(after_l)}) ---")
print(Counter(after_l))

# Another check: Does ANY win reset the counter?
# If we count the gap between ANY triple (Hammers, Pigs, etc.)
all_any_triple_gaps = []
for acct in data.keys():
    for sess in [0, 1]:
        spins = [s for s in data[acct]['spins'] if s['session_idx'] == sess and s['gae_segment'] != '']
        current_gap = 0
        gaps = []
        for s in spins:
            current_gap += 1
            if s.get('triple'):
                gaps.append((s.get('triple'), current_gap))
                current_gap = 0
        all_any_triple_gaps.append(gaps)

print("\n--- Does ANY win follow a strict pattern? ---")
def cat_any(g):
    if g < 20: return 'S'
    if g <= 40: return 'M'
    return 'L'

after_l_any = [cat_any(gaps[i+1][1]) for gaps in all_any_triple_gaps for i in range(len(gaps)-1) if cat_any(gaps[i][1]) == 'L']
print(f"What follows an ANY-win L? {Counter(after_l_any)}")
