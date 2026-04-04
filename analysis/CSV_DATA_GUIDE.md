# SpinLogger CSV Data Guide

## Overview

This CSV is produced by the SpinLogger tweak injected into Coin Master (iOS). It captures **every spin response** from the game server at `POST /api/v1/users/{userId}/spin` on `vik-game.moonactive.net`. Each row = one spin. The data is raw server truth, not client-side animation.

Spins are **100% server-determined**. The client sends only `seq`, `bet`, and `auto_spin`. The server returns the reel results, reward, and all game state updates. There is no local RNG.

---

## Column Reference (46 columns)

### Core Spin Data (columns 1-11)

| # | Column | Type | Description |
|---|--------|------|-------------|
| 1 | `seq` | int | Server sequence number. Increments by 1 per spin. This is the spin's unique ID. |
| 2 | `timestamp` | datetime | Local device time when the spin response was received. Format: `yyyy-MM-dd HH:mm:ss`. |
| 3 | `r1` | int | Reel 1 raw value (server integer). See symbol mapping below. |
| 4 | `r2` | int | Reel 2 raw value. |
| 5 | `r3` | int | Reel 3 raw value. |
| 6 | `reel_1` | string | Reel 1 symbol name (human-readable). |
| 7 | `reel_2` | string | Reel 2 symbol name. |
| 8 | `reel_3` | string | Reel 3 symbol name. |
| 9 | `spin_result` | string | Outcome type name (gold, attack, steal, shield, spins, accumulation). |
| 10 | `reward_code` | int | Server reward type code. See reward mapping below. |
| 11 | `is_triple` | bool | `true` if all 3 reels match (r1 == r2 == r3). This is a three-of-a-kind. |

### Symbol Mapping (r1/r2/r3 values)

| Raw Value | Symbol Name | Description |
|-----------|-------------|-------------|
| 1 | coin | Basic coin. Triple = small gold payout. |
| 2 | goldSack | Bag of gold. Triple = large gold payout. |
| 3 | attack | Hammer. Triple = attack another player's village. |
| 4 | steal | Pig/raid. Triple = raid another player's coin stash. |
| 5 | shield | Shield. Triple = gain shield(s). Shields block attacks. |
| 6 | spins | Energy capsule. Triple = bonus free spins. |
| 30 | accumulation | Star. Fills the GAE accumulation bar. Triple = +10 points. |

### Reward Code Mapping

| Code | Meaning | Triggered by |
|------|---------|-------------|
| 1 | Gold (coins) | Any non-triple, triple coin, triple goldSack |
| 2 | Attack | Triple attack (3,3,3) |
| 3 | Shield | Triple shield (5,5,5) |
| 4 | Steal/Raid | Triple steal (4,4,4) |
| 5 | Spins | Triple spins (6,6,6) |
| 10 | Accumulation | Triple accumulation (30,30,30) |

Non-triple spins almost always have reward_code=1 (gold) regardless of which symbols appeared.

---

### Economy State (columns 12-17)

| # | Column | Type | Description |
|---|--------|------|-------------|
| 12 | `coins_won` | int | Coins paid out this spin. 0 for attacks/steals/accumulation. |
| 13 | `coins` | string | Player's total coin balance after this spin. Can be very large (trillions). |
| 14 | `spins_remaining` | string | Remaining spin balance after this spin. |
| 15 | `shields` | int | Current shield count (0 to max_shields). Shields block incoming attacks. |
| 16 | `max_shields` | int | Maximum shields allowed at current village level (typically 3-5). |
| 17 | `bet_multiplier` | int | Actual bet multiplier used for this spin (1, 2, 3, 15, 50, 400, 1500, 6000, 20000). Extracted from the spin request body `bet=` parameter. This is what the player chose. |
| 18 | `bet_level` | int | Internal bet level index from `superBet.betLevel` in the response. The server uses this to select which probability table to use. |

---

### GAE Accumulation Bar (columns 19-23)

The GAE (Global Accumulation Event) is the main progress bar. It fills when accumulation symbols (r=30) appear on the reels.

| # | Column | Type | Description |
|---|--------|------|-------------|
| 19 | `accum_current` | int | Current points in the GAE bar. |
| 20 | `accum_total` | int | Points needed to complete the current mission/milestone. |
| 21 | `accum_mission` | int | Current mission index (0-100+). Each mission has a different target and reward. When you collect a mission reward, this increments. |
| 22 | `accum_delta` | int | How much the bar moved THIS spin. This is `bet_multiplier * base_points`. Set to 0 on mission boundary changes. |
| 23 | `accum_pct` | float | Percentage of current mission completed (0.0 to 100.0). Calculated as `accum_current / accum_total * 100`. |

**GAE Scoring (base points, before bet multiplier):**
- 1 accumulation symbol on reels: +1 base point
- 2 accumulation symbols on reels: +2 base points
- 3 accumulation symbols (triple): +10 base points

**The bet multiplier applies to GAE points.** The actual delta is `base_points * bet_multiplier`. For example:
- Bet x1, triple accum: +10 points
- Bet x50, triple accum: +500 points
- Bet x1500, triple accum: +15,000 points
- Bet x1500, single accum symbol: +1,500 points

This means `accum_delta` already reflects the multiplied value (it's computed from the server's `currentAmount` difference, which is post-multiplication).

**Why this matters for pattern detection:** The server assigns probability segments partly based on the GAE mission index. As you progress through missions, the probability tables may shift. Track `accum_mission` changes and see if triple frequency changes at mission boundaries.

---

### Second Slot / Slot-on-Slot (columns 23-25)

The second slot is a mini-reel that runs alongside the main slot machine. It powers event progress bars (Easter Dove, Easter Cookie, St. Patrick's, etc.). The symbols rotate with seasonal events.

| # | Column | Type | Description |
|---|--------|------|-------------|
| 23 | `slot2_r1` | string | Second slot reel 1. Either empty string (no symbol) or event symbol name. |
| 24 | `slot2_r2` | string | Second slot reel 2. |
| 25 | `slot2_r3` | string | Second slot reel 3. |

**Known symbol names (rotate seasonally):**
- `GCEaster26` (Easter Dove icon) -- fills egg currency bar
- `LongExtraDayReduced` (Easter Cookie icon) -- fills spins/chest bar
- `SlotOnSlotStPatrick2026_Drum`, `SlotOnSlotStPatrick2026_Guitar`
- Empty string = no symbol on that reel position

**Slot-on-slot scoring:**
- 1 symbol: +1 point (multiplied by bet level)
- 2 matching symbols: +2 points (multiplied by bet level)
- 3 matching symbols: +5 points (multiplied by bet level)

---

### Event Bars Snapshot (column 26)

| # | Column | Type | Description |
|---|--------|------|-------------|
| 26 | `event_bars` | JSON string | Snapshot of ALL active event progress bars this spin. Quoted JSON object. |

This column captures every `accumulationBarsById` entry from the spin response, plus any bars nested inside `serializedEvents` (slot-on-slot progress). Each bar is keyed by the first 8 characters of its UUID.

**Format:** `{"6aa02145":"684/3200@m7","ec36d075":"8675/21000@m43"}`

Where `684/3200@m7` means: currentAmount=684, totalAmount=3200, missionIndex=7.

**Known bar IDs (first 8 chars) from analysis:**

| Short ID | Event | Reward Type |
|----------|-------|-------------|
| `6aa02145` | Potion Rush (Expedition Cave Progressive) | `progressive_reward_pr_ec` |
| `ec36d075` | Merge Energy | `generic_currency_merge_energy` |
| `ed125bfa` | Expedition Cave Blaster | `expedition_cave_blaster` |
| `tourname` | Tournament Milestones | coins, cards |
| `c819ecc4` | Bring Back Friends | mystery chests |
| (slot_on_slot key) | Easter Dove | `generic_currency_egg_currency` |
| (slot_on_slot key) | Easter Cookie | spins, wheel tokens, chests |

**Note:** Bar IDs are UUIDs that change when events rotate. The short IDs above are from a specific session. New events will have new IDs. Use the reward types in the full JSON to identify which bar is which.

**Note:** This column is only populated when the server includes `accumulationBarsById` or `serializedEvents` in the spin response. Not every spin includes bar updates.

---

### Running Counters: Since Last Triple Accumulation (columns 27-36)

These counters track what happened between consecutive triple accumulation events (30,30,30). They increment every spin and **reset to 0 when a triple accumulation lands** (after writing the row, so the triple row shows the final count).

| # | Column | Type | Description |
|---|--------|------|-------------|
| 27 | `sa_spins` | int | Total spins since last triple accumulation. |
| 28 | `sa_atk1` | int | Spins with exactly 1 attack symbol (r=3) since last triple accum. |
| 29 | `sa_atk2` | int | Spins with exactly 2 attack symbols since last triple accum. |
| 30 | `sa_atk3` | int | Spins with 3 attack symbols (= triple attack) since last triple accum. |
| 31 | `sa_stl1` | int | Spins with exactly 1 steal symbol (r=4) since last triple accum. |
| 32 | `sa_stl2` | int | Spins with exactly 2 steal symbols since last triple accum. |
| 33 | `sa_stl3` | int | Spins with 3 steal symbols (= triple steal) since last triple accum. |
| 34 | `sa_shd1` | int | Spins with exactly 1 shield symbol (r=5) since last triple accum. |
| 35 | `sa_shd2` | int | Spins with exactly 2 shield symbols since last triple accum. |
| 36 | `sa_shd3` | int | Spins with 3 shield symbols (= triple shield) since last triple accum. |

**How to use:** When `is_triple=true` and `r1=30`, that row's `sa_spins` value tells you exactly how many spins it took to get from the previous triple accum to this one. The `sa_atk3` value tells you how many triple attacks happened in that window. After this row, all `sa_` counters reset to 0 and start counting again.

---

### Running Counters: Since Last Triple Spins (columns 37-46)

Identical to the `sa_` counters but reset on triple spins (6,6,6) instead of triple accumulation.

| # | Column | Type | Description |
|---|--------|------|-------------|
| 37 | `ss_spins` | int | Total spins since last triple spins. |
| 38 | `ss_atk1` | int | Spins with exactly 1 attack symbol since last triple spins. |
| 39 | `ss_atk2` | int | Spins with exactly 2 attack symbols since last triple spins. |
| 40 | `ss_atk3` | int | Spins with 3 attack symbols (= triple attack) since last triple spins. |
| 41 | `ss_stl1` | int | Spins with exactly 1 steal symbol since last triple spins. |
| 42 | `ss_stl2` | int | Spins with exactly 2 steal symbols since last triple spins. |
| 43 | `ss_stl3` | int | Spins with 3 steal symbols (= triple steal) since last triple spins. |
| 44 | `ss_shd1` | int | Spins with exactly 1 shield symbol since last triple spins. |
| 45 | `ss_shd2` | int | Spins with exactly 2 shield symbols since last triple spins. |
| 46 | `ss_shd3` | int | Spins with 3 shield symbols (= triple shield) since last triple spins. |

---

## Server Probability Segments

The server does NOT use a single probability table. It selects a table based on multiple player attributes. From network analysis, the known segmentation factors are:

1. **Village level** -- segments like `slot_probabilities_villages_200_269`
2. **Purchase power percentile** -- segments like `pps_by_segment_over_p90_under_p95` (how much real money the player has spent)
3. **A/B test variant** -- segments like `core_slot_prob_nu_29_06_var_a`
4. **Bet level** -- different bet multipliers may use different probability weights
5. **GAE mission index** -- probability may shift at mission boundaries

This means two players at different villages or spending tiers will see different triple frequencies. When analyzing patterns, always control for `bet_level` and `accum_mission`.

---

## Known Patterns from Initial Analysis (128 spins)

These are preliminary findings. More data needed to confirm.

### Triple Clustering
- 29.7% of spins were triples (much higher than random chance for 7 symbols)
- 27% of triple-to-triple transitions were back-to-back (gap=1)
- Average gap between triples: 3.2 spins
- Longest triple streak: 4 consecutive triples
- This suggests a pre-generated strip/sequence, not independent random draws

### Autocorrelation
- Reel 1 shows correlation at lags 11, 22, and 48 (all >30%, vs ~14% random baseline)
- Suggests a possible cycle length around 11 or a multiple

### Transition Bias
- Attack follows attack 42.2% of the time (3x expected)
- Accumulation follows accumulation 30% of the time (2.1x expected)

### Triple Accumulation (30,30,30)
- 0.78% of spins (1 in 128)
- Each single accum symbol adds +1 to GAE bar
- Triple adds +10 (bonus, not just 3)

### Triple Spins (6,6,6)
- 1.56% of spins (2 in 128)
- Gap between both occurrences was exactly 35 spins
- Awards 10 extra spins

---

## Analysis Tools

### Python Analyzer
Run `python analysis/spin_analyzer.py spin_history.csv` to get:
- Symbol frequency distribution
- Triple clustering and streak analysis
- Accumulation bar delta tracking
- Attack/steal frequency and shield correlation
- Second slot symbol analysis
- Bet level vs triple rate correlation
- Autocorrelation and cycle detection
- Transition matrix (what follows what)
- Hot/cold zone sliding window analysis

### HAR File Analysis
Run `python analysis/spin_analyzer.py --har sample.har` to analyze network captures directly.

---

## Data Collection Tips

- **500+ spins** needed for meaningful cycle detection
- **2000+ spins** needed to map strip positions
- **Keep bet level constant** during a session for clean data (bet changes shift probability segments)
- **Note when events change** -- event rotations may coincide with probability table changes
- **Delete spin_history.csv** between sessions if you change village level or bet level significantly, to avoid mixing probability segments
- The CSV appends to the same file. If you want separate sessions, rename/move the file between runs.

---

## Data Source

All data comes from intercepting the server response to `POST /api/v1/users/{userId}/spin`. The request contains:
```
Device[udid]=...
API_KEY=viki
API_SECRET=coin
seq=45439          (sequence number)
auto_spin=False
bet=1              (bet multiplier)
Client[version]=3.5.2470_fbios
```

The response is a JSON object containing all 46 columns' source data. The tweak captures this via NSURLProtocol injection, parses it in `SLParseSpinAPIResponse()`, and appends to `Documents/spin_history.csv`.
