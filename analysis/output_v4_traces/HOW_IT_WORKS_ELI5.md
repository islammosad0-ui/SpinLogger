# How V4 Works (ELI5) — and how to read the traces

## 1. The game's hidden rule

Coin Master has a **pity timer** for the two big rewards (Vault Triggers, "VTs"):

- **ACC** (accumulation triple) — fills the energy/raid bar
- **SPN** (spins triple) — gives free spins

You won't get a VT in the first ~15 spins of a cycle. After that, the chance
slowly climbs. By spin ~70+ you're nearly guaranteed one. The "cycle" is the
spins between one VT and the next.

We have ~3,000 cycles of historical data across Ahmed/Islam/Nick. The cycle
lengths look like this (rough):

```
P5    ~15
P25   ~30
P50   ~55       ← median
P75   ~85
P95   ~130
```

So: very few VTs land before t=15, and most have landed by t=100. That's where
the model spends its attention.

---

## 2. What the model is really predicting

`v4_model.json` is a **LightGBM gradient-boosted classifier**. For each spin
**inside an open cycle**, it answers one question:

> "Will a VT (ACC or SPN triple) land in the **next 5 spins**?"

The output is a probability `p5` between 0 and 1. The model uses ~46 features —
none of them are the spin's outcome:

| Feature group | Examples |
|---|---|
| Cycle position | `t` (most important — pity timer is mostly time-based) |
| Cooldown gaps  | `last_atk_triple_gap`, `last_shd_triple_gap`, ... |
| Density        | `density_any_last5/10`, `cooldown_last5/10` |
| Carry from previous cycles | `vt_gap_lag1..4`, `acc_gap_mean3` |
| Categorical    | `prev_vt_type` (ACC/SPN/UNK), `cat_lag1..3` |

The model is trained per-account using **leave-one-session-out CV** — so the
holdout numbers reflect "how it would have done on a session it had never
seen." We also audited for label leakage and found none (see leak audit
results).

---

## 3. The decision rule (`dyn_aggr` schedule)

The raw probability isn't a decision — we still need a threshold. A flat
threshold (say "fire if p5 ≥ 0.10") wastes bets early in the cycle when the
pity timer hasn't kicked in. So we use a **per-band threshold schedule**:

```
t ∈ [15, 29]  thr = X   ← fresh-pity window, model signal strongest
t ∈ [30, 49]  thr = Y
t ∈ [50, 69]  thr = Z
t ∈ [70,100]  thr = W
```

The panel shows **FIRE** when `p5 ≥ thr(t)`, **WAIT** otherwise. Plus a hard
gate: `t < 15` and `t > 100` are always WAIT.

---

## 4. Why two modes?

We tuned each account's schedule by grid-searching for the lowest Bets/VT that
keeps catch% above a floor. Two configs survived:

### `bundled` (ships as default)
Conservative — only fires in the fresh-pity window at thr=0.08:

```
t ∈ [15, 29]  thr = 0.08
t ∈ [30,100]  thr = 0.99   ← never fires
```

→ ~60-66% catch, ~10 Bets/VT. Cheap, misses some long-tail catches.

### `tuned` (per-account, picked by holdout sweep)
Aggressive — opens the threshold across the whole window:

```
Ahmed   t∈[15,29] thr=0.03, else 0.99            (~79% catch, 12.8 B/VT)
Islam   t∈[15,29] thr=0.04, else 0.15            (~82% catch, 14.1 B/VT)
Nick    t∈[15,29] thr=0.08, decreasing 0.05/0.04/0.03 (~81% catch, 36.2 B/VT)
```

→ Higher catch, more bets. Nick especially — his model trades 4× more bets
for the extra catches because the cycle-end signal is noisier on his data.

**Tap the cfg label** in the panel (`K5·ANY·B` ↔ `K5·ANY·T`) to flip per
account. The choice persists in NSUserDefaults and survives restart. The
suffix is amber when bundled, green when tuned.

---

## 5. Why does it work?

Three things are doing the heavy lifting:

1. **`t` (cycle position)** is the single biggest feature (importance 880).
   The pity timer is mostly a time mechanic — the model is largely learning
   that.
2. **Cooldown gaps** (`last_stl_triple_gap`=771, `last_shd_triple_gap`=600,
   etc.) — when the game gives you a non-VT triple, that "burns" some of the
   pity budget. Recent cooldown triples push the VT moment further out.
3. **Carry features** (`vt_gap_lag1`, `acc_gap_mean3`) — the recent rhythm
   of cycle lengths predicts the current cycle. Players with shorter recent
   gaps tend to keep getting shorter gaps.

What does **not** matter:

- Reel symbols of the current spin (`cur_cat_id`, `reel_dup_last`) — minimal
  importance. The leak audit confirmed removing them slightly *improved*
  performance, meaning they were noise.

---

## 6. Live data path (what runs on the phone)

```
[Network packet]
   │
   ├─► SLSpinParser   ──► [SLV4Features feedSpin]   ← updates t, gaps, cums
   │                     dispatch_async on serial queue
   │
   └─► [SLIdxStrategy queueResult]    ← logs CSV row
                                         (separate, doesn't affect prediction)

Every spin parse:
  1. SLV4Features rebuilds the 46-element feature vector
  2. SLV4Policy.evaluate calls SLV4Model.predictHead("ANY_VT", feat, &p3, &p5, &p10)
  3. Reads schedule[mode][band], decides FIRE/WAIT
  4. Sends SLV4PanelRefreshNotification → panel refreshes
  5. Haptic fires on FIRE↔WAIT transition (Heavy → FIRE, Light → WAIT)
  6. On VT close: pvt_type / gap streams persisted to NSUserDefaults
                  so model state survives game restart
```

The model is loaded once at install from `v4_model.json` (15 MB, 4 heads × 3
horizons of decision trees walked in C).

---

## 7. How to read the trace files

`trace_<acct>_K5DYN_<mode>.txt` shows every cycle in your prediction set.

Each cycle block:

```
Gap #0042  Len= 80  Prev1= 55  Prev2=120  EndSym=ACC  Fires= 8  FirstFire@t=15  Result=CAUGHT
  session=Ahmed|spin_history_2026-04-05.csv  start_seq=46403  end_seq=46463
    POS=  0  p5= 0.007  thr= 0.99  [ wait ]
    POS=  1  p5= 0.007  thr= 0.99  [ wait ]
    ...
    POS= 15  p5= 0.085  thr= 0.08  [ FIRE ]  <-- FIRST FIRE
    POS= 16  p5= 0.073  thr= 0.08  [ wait ]
    POS= 17  p5= 0.085  thr= 0.08  [ FIRE ]
    ...
    POS= 79  p5= 0.150  thr= 0.99  [ wait ]  <-- ACC TRIPLE NEXT
```

Header fields:
- `Gap #` — cycle id (sequential within account)
- `Len` — spins from cycle start to VT spin
- `Prev1/Prev2` — lengths of the two previous cycles (rolling memory)
- `EndSym` — ACC or SPN (which VT closed the cycle)
- `Fires` — total spins where the panel said FIRE
- `FirstFire@t` — earliest position where it fired
- `Result` — `CAUGHT` (fired AND VT landed), `NO_FIRE` (never fired)

Per-spin lines:
- `POS` — t (spins into cycle)
- `p5` — model's probability of VT in next 5 spins
- `thr` — schedule threshold at this t under the active mode
- `[ FIRE ]` / `[ wait ]` — verdict

Each cycle ends with a divider, and the file closes with a SUMMARY block:
total cycles, catches, fires, B/VT.

---

## 8. Where to look first

1. **`summary.txt`** — one-line per (account, mode), see all 6 numbers at once.
2. **A single tuned cycle** — open `trace_Ahmed_K5DYN_tuned.txt`, find any
   `Gap` block with `Result=CAUGHT`. Scan the FIRE positions: that's exactly
   what the panel would have shown you live.
3. **Compare modes** — open the same `Gap #N` in both `_bundled.txt` and
   `_tuned.txt` files. Tuned will show extra FIREs across the cycle; bundled
   will only ever fire in t∈[15,29].

That's the whole system in one document.
