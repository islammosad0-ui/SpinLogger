# Strip Reconstruction Report

Reconstructed from 213 settled spin observations, joined trace.spin_num -> CSV.seq = spin_num + 1.

## Reel 1

| idx | symbol(id) | consistency |
| --- | --- | --- |
| 0 | attack(3)  [25/25 = 100%] | |
| 1 | accumulation(30)  [10/16 = 62%] | |
| 2 | shield(5)  [13/18 = 72%] | |
| 3 | accumulation(30)  [25/50 = 50%] | |
| 4 | coin(1)  [12/23 = 52%] | |
| 5 | accumulation(30)  [8/14 = 57%] | |
| 6 | coin(1)  [11/14 = 79%] | |
| 7 | accumulation(30)  [24/49 = 49%] | |
| 8 | accumulation(30)  [4/4 = 100%] | |

**Duplicate symbols on reel 1:**

- `coin` appears at indices: [4, 6]
- `accumulation` appears at indices: [1, 3, 5, 7, 8]

## Reel 2

| idx | symbol(id) | consistency |
| --- | --- | --- |
| 0 | attack(3)  [34/34 = 100%] | |
| 1 | coin(1)  [14/14 = 100%] | |
| 2 | shield(5)  [18/18 = 100%] | |
| 3 | goldSack(2)  [38/38 = 100%] | |
| 4 | steal(4)  [31/31 = 100%] | |
| 5 | coin(1)  [10/10 = 100%] | |
| 6 | spins(6)  [21/21 = 100%] | |
| 7 | goldSack(2)  [25/25 = 100%] | |
| 8 | accumulation(30)  [22/22 = 100%] | |

**Duplicate symbols on reel 2:**

- `goldSack` appears at indices: [3, 7]
- `coin` appears at indices: [1, 5]

## Reel 3

| idx | symbol(id) | consistency |
| --- | --- | --- |
| 0 | goldSack(2)  [30/62 = 48%] | |
| 1 | steal(4)  [7/18 = 39%] | |
| 2 | shield(5)  [13/15 = 87%] | |
| 3 | goldSack(2)  [7/7 = 100%] | |
| 4 | steal(4)  [11/17 = 65%] | |
| 5 | spins(6)  [6/15 = 40%] | |
| 6 | spins(6)  [3/3 = 100%] | |
| 7 | goldSack(2)  [5/5 = 100%] | |
| 8 | goldSack(2)  [49/71 = 69%] | |

**Duplicate symbols on reel 3:**

- `steal` appears at indices: [1, 4]
- `goldSack` appears at indices: [0, 3, 7, 8]
- `spins` appears at indices: [5, 6]

## Triple index patterns

- Total triples observed: **75**
- Triples with matching bar indices (idx1==idx2==idx3): **63** (84.0%)

**Example matching-index triples:**

- spin 64394: idx=(4,4,4) -> steal (r_id=4)
- spin 64397: idx=(6,6,6) -> spins (r_id=6)
- spin 64401: idx=(8,8,8) -> accumulation (r_id=30)
- spin 64406: idx=(0,0,0) -> attack (r_id=3)
- spin 64407: idx=(1,1,1) -> coin (r_id=1)

**Example non-matching-index triples (triple symbol but different indices):**

- spin 64403: idx=(5,5,1) -> coin (r_id=1)
- spin 64433: idx=(3,3,7) -> goldSack (r_id=2)
- spin 64450: idx=(5,5,1) -> coin (r_id=1)
- spin 64471: idx=(1,5,1) -> coin (r_id=1)
- spin 64480: idx=(3,3,7) -> goldSack (r_id=2)
