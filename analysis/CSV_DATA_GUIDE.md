# SpinLogger CSV Data Guide

## Overview

This CSV is produced by the SpinLogger tweak injected into Coin Master (iOS). It captures **every spin response** from the game server at `POST /api/v1/users/{userId}/spin` on `vik-game.moonactive.net`. Each row = one spin. The data is raw server truth, not client-side animation.

Spins are **100% server-determined**. The client sends only `seq`, `bet`, and `auto_spin`. The server returns the reel results, reward, and all game state updates. There is no local RNG.

### CSV File Naming

CSV files are date-based: `spin_history_YYYY-MM-DD.csv`. The date is the session start date (set when the user taps RESET in the tris monitor). Old CSVs stay on disk. A typical workflow:
- Spin all week during an event
- Monday comes, event resets
- Tap RESET in the tris monitor → new CSV starts with today's date
- Each file = one event cycle, clean data for analysis

---

## Column Reference (53 columns)

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

### Economy State (columns 12-18)

| # | Column | Type | Description |
|---|--------|------|-------------|
| 12 | `coins_won` | int | Coins paid out this spin. 0 for attacks/steals/accumulation. |
| 13 | `coins` | string | Player's total coin balance after this spin. Can be very large (trillions). |
| 14 | `spins_remaining` | string | Remaining spin balance after this spin. |
| 15 | `shields` | int | Current shield count (0 to max_shields). Shields block incoming attacks. |
| 16 | `max_shields` | int | Maximum shields allowed at current village level (typically 3-5). |
| 17 | `bet_multiplier` | int | Actual bet multiplier used for this spin (1, 2, 3, 15, 50, 150, 200, 600, etc.). Extracted from the spin request body `bet=` parameter. This is the actual value the player chose, not an index. |
| 18 | `bet_level` | int | Internal bet level index from `superBet.betLevel` in the response. The server uses this to select which probability table to use. |

**Bet extraction:** The `bet` parameter in the request is the actual multiplier value (e.g. `bet=15` means 15x), NOT an index into `betOptions`. The value is captured in `startLoading` before the HTTP body stream is consumed during forwarding.

---

### Per-Spin Symbol Counts (columns 19-23)

How many of each combat/special symbol appeared on this spin's reels (0-3 each).

| # | Column | Type | Description |
|---|--------|------|-------------|
| 19 | `atk_count` | int | Attack symbols (r=3) on this spin (0-3). |
| 20 | `stl_count` | int | Steal symbols (r=4) on this spin (0-3). |
| 21 | `shd_count` | int | Shield symbols (r=5) on this spin (0-3). |
| 22 | `spn_count` | int | Spins symbols (r=6) on this spin (0-3). |
| 23 | `acc_count` | int | Accumulation symbols (r=30) on this spin (0-3). |

**Why these matter:** In Mix events, attack or steal symbols also contribute to GAE progression. These counts let you:
- **Detect standard vs mix events:** if `accum_delta > 0` and `acc_count == 0`, it's a mix event
- **Calculate mix GAE points:** 1 atk/stl symbol = +1pt, 2 = +2pt, 3 = +5pt (× bet multiplier)
- **Identify which symbol is the mix contributor:** compare `atk_count` vs `stl_count` correlation with `accum_delta`

---

### GAE Accumulation Bar (columns 24-28)

The GAE (Global Accumulation Event) is the main weekly progress bar. It resets every Monday.

| # | Column | Type | Description |
|---|--------|------|-------------|
| 24 | `accum_current` | int | Current points in the GAE bar for this mission. |
| 25 | `accum_total` | int | Points needed to complete the current mission/milestone. |
| 26 | `accum_mission` | int | Current mission index (0-100+). Each mission has a different target and reward. When you collect a mission reward, this increments. |
| 27 | `accum_delta` | int | How much the bar moved THIS spin. Set to 0 on mission boundary changes. |
| 28 | `accum_pct` | float | Percentage of current mission completed (0.0 to 100.0). |

**GAE Event Types (weekly, resets Monday):**

**Standard (10 Symbol Event):**
- ONLY accumulation symbols (r=30) contribute to the GAE bar
- 1 accum symbol = +1 base point, 2 = +2, triple = +10
- Points multiplied by bet multiplier

**Mix (10er Mix Symbol Event):**
- Accumulation symbols contribute as normal (+1/+2/+10)
- PLUS either attack OR steal symbols also contribute (one type per event, not both):
  - 1 symbol = +1pt, 2 symbols = +2pt, 3 symbols (triple) = +5pt
  - Also multiplied by bet multiplier
- **Detection:** if `accum_delta > 0` on a spin where `acc_count == 0`, it's a mix event

**The bet multiplier applies to ALL GAE points.** The actual delta is `base_points * bet_multiplier`.

---

### GAE List Identification (columns 29-30)

| # | Column | Type | Description |
|---|--------|------|-------------|
| 29 | `gae_segment` | string | Server-assigned list segment (e.g. `bonus_bs15_gae0_no`). Encodes the player's reward list tier. |
| 30 | `gae_last_mission` | int | Total missions/milestones in this list (e.g. 59). Each list tier has a different count, so this fingerprints the exact list. |

**Event List Assignment:** At the START of each new event, the player's current spin count determines which reward list they get:

| Starting Spins | List Difficulty | Example Total Points |
|---|---|---|
| 0 - 999 | Easiest | 300k-500k |
| 1k - 4.9k | Low | 360k-660k |
| 5k - 9.9k | Mid-low | 400k-650k |
| 10k - 19.9k | Mid | 560k-980k |
| 20k - 39.9k | Mid-high | 500k |
| 40k - 74.9k | High | 800k |
| 75k - 149k | Higher | 850k-1.8M |
| 150k - 299k | Highest | 1.3M-1.7M |
| 300k+ | Max | 3.4M+ |

Higher lists require more points for the same spin rewards but offer higher total potential.

**Surprise Events:** When a player is inactive for ~1 week, the server assigns an easier "surprise" list to encourage return. These are randomly assigned regardless of spin count. The `gae_segment` will differ from standard lists.

**How to identify your list:** Use `gae_segment` + `gae_last_mission` + `spins_remaining` from row 1 of the CSV. The segment string uniquely identifies the server's list assignment. Reference tables at coinmasterspins.de.

---

### Second Slot / Slot-on-Slot (columns 31-33)

| # | Column | Type | Description |
|---|--------|------|-------------|
| 31 | `slot2_r1` | string | Second slot reel 1. Empty string or event symbol name. |
| 32 | `slot2_r2` | string | Second slot reel 2. |
| 33 | `slot2_r3` | string | Second slot reel 3. |

**Known symbol names (rotate seasonally):**
- `GCEaster26` (Easter Dove) — fills egg currency bar
- `LongExtraDayReduced` (Easter Cookie) — fills spins/chest bar
- `SlotOnSlotStPatrick2026_Drum`, `SlotOnSlotStPatrick2026_Guitar`
- Empty string = no symbol on that reel position

**Slot-on-slot scoring:** 1 symbol = +1pt, 2 matching = +2pt, 3 matching = +5pt (× bet level)

---

### Event Bars Snapshot (column 34)

| # | Column | Type | Description |
|---|--------|------|-------------|
| 34 | `event_bars` | JSON string | Snapshot of ALL active event progress bars. Quoted JSON object. |

Format: `{"348a373a":"27/40@m7","bf1b4f4b":"396/400@m27"}` where `27/40@m7` = currentAmount=27, totalAmount=40, missionIndex=7.

**Bar identification:** Bar UUIDs change every event rotation. Identify bars by their reward type:

| Reward Key | Event |
|---|---|
| `progressive_reward_pr_ec` | Potion Rush (Expedition Cave) |
| `expedition_cave_blaster` | Cave Blaster |
| `generic_currency_merge_energy` | Merge Energy |
| `generic_currency_egg_currency` | Easter Eggs |
| `generic_currency_picks_currency` | Picks event |
| `token_currency_wheel_token_cw_one` | Wheel Token |

**Note:** The Potion Rush bar is also tracked separately via `potionRushMissionIndex` in the parser, detected by the `progressive_reward_pr_ec` reward key (not by hardcoded UUID).

---

### Running Counters: Since Last Triple Accumulation (columns 35-43)

These counters track what happened between consecutive triple accumulation events (30,30,30). They increment every spin and **reset to 0 when a triple accumulation lands** (after writing the row). All counters persist across app restarts via NSUserDefaults.

| # | Column | Type | Description |
|---|--------|------|-------------|
| 35 | `sa_spins` | int | Total spins since last triple accumulation. |
| 36 | `sa_atk` | int | Total attack symbols (r=3) since last triple accum. |
| 37 | `sa_stl` | int | Total steal symbols (r=4) since last triple accum. |
| 38 | `sa_shd` | int | Total shield symbols (r=5) since last triple accum. |
| 39 | `sa_spn` | int | Total spins symbols (r=6) since last triple accum. |
| 40 | `sa_acc` | int | Total accumulation symbols (r=30) since last triple accum. |
| 41 | `sa_3x_atk` | int | Triple attacks since last triple accum. |
| 42 | `sa_3x_stl` | int | Triple steals since last triple accum. |
| 43 | `sa_3x_shd` | int | Triple shields since last triple accum. |

---

### Running Counters: Since Last Triple Spins (columns 44-52)

Identical to `sa_` counters but reset on triple spins (6,6,6).

| # | Column | Type | Description |
|---|--------|------|-------------|
| 44 | `ss_spins` | int | Total spins since last triple spins. |
| 45 | `ss_atk` | int | Total attack symbols since last triple spins. |
| 46 | `ss_stl` | int | Total steal symbols since last triple spins. |
| 47 | `ss_shd` | int | Total shield symbols since last triple spins. |
| 48 | `ss_spn` | int | Total spins symbols since last triple spins. |
| 49 | `ss_acc` | int | Total accumulation symbols since last triple spins. |
| 50 | `ss_3x_atk` | int | Triple attacks since last triple spins. |
| 51 | `ss_3x_stl` | int | Triple steals since last triple spins. |
| 52 | `ss_3x_shd` | int | Triple shields since last triple spins. |

---

## Persistence & Session Management

### What persists across app restarts:
- **CSV file** — written to Documents, survives restarts
- **Counter overlay values** (3X distance, 1X count per symbol) — saved to `Speeder_CounterState` in NSUserDefaults
- **Tris history** (all 12 history arrays + totalSpins) — saved to `Speeder_TrisState`
- **CSV running counters** (sa_*, ss_*, GAE delta state) — saved to `Speeder_CSVCounters`
- **Session date** — saved to `Speeder_SessionDate`, determines CSV filename

### Reset behavior (tris RESET button):
1. Clears all tris history arrays (spin + symbol mode)
2. Resets all counter overlay tiles to 0
3. Rotates to a new CSV file with today's date
4. Resets all running CSV counters (sa_*, ss_*)
5. All persisted state is updated immediately

---

## Server Probability Segments

The server does NOT use a single probability table. It selects a table based on multiple player attributes:

1. **Village level** — segments like `slot_probabilities_villages_200_269`
2. **Purchase power percentile** — segments like `pps_by_segment_over_p90_under_p95`
3. **A/B test variant** — segments like `core_slot_prob_nu_29_06_var_a`
4. **Bet level** — different bet multipliers may use different probability weights
5. **GAE mission index** — probability may shift at mission boundaries

The `gae_segment` column captures the server's assignment (e.g. `bonus_bs15_gae0_no`).

---

## Data Source

All data comes from intercepting the server response to `POST /api/v1/users/{userId}/spin`. The request body is form-encoded:
```
Device[udid]=...
API_KEY=viki
API_SECRET=coin
seq=45439          (sequence number)
auto_spin=False
bet=15             (actual multiplier value, NOT index)
Client[version]=3.5.2490_fbios
```

The `bet` parameter is the actual multiplier value (1, 2, 3, 15, 50, 150, 200, 600). It is captured in `startLoading` before the HTTP body stream is consumed during request forwarding. The response is JSON containing all source data. The tweak captures this via NSURLProtocol injection, parses it in `SLParseSpinAPIResponseWithBet()`, and appends to `Documents/spin_history_YYYY-MM-DD.csv`.
