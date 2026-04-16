# ACC / SPN Pattern Analysis

## Step 1

- Total deduplicated spins: 53,993
- Raw loaded rows: 101,900
- Duplicate `(account, seq)` pairs found and removed: 42,514
- Accounts: {'Ahmed': 23353, 'Islam': 21288, 'Nick': 9352}
- Triple Accumulation events: 496
- Triple Spins events: 601

### Columns
- `seq`
- `timestamp`
- `r1`
- `r2`
- `r3`
- `reel_1`
- `reel_2`
- `reel_3`
- `spin_result`
- `reward_code`
- `is_triple`
- `coins_won`
- `coins`
- `spins_remaining`
- `shields`
- `max_shields`
- `bet_multiplier`
- `bet_level`
- `atk_count`
- `stl_count`
- `shd_count`
- `spn_count`
- `acc_count`
- `accum_current`
- `accum_total`
- `accum_mission`
- `accum_delta`
- `accum_pct`
- `gae_segment`
- `gae_last_mission`
- `gae_grand_prize`
- `slot2_r1`
- `slot2_r2`
- `slot2_r3`
- `event_bars`
- `sa_spins`
- `sa_atk`
- `sa_stl`
- `sa_shd`
- `sa_spn`
- `sa_acc`
- `sa_3x_atk`
- `sa_3x_stl`
- `sa_3x_shd`
- `ss_spins`
- `ss_atk`
- `ss_stl`
- `ss_shd`
- `ss_spn`
- `ss_acc`
- `ss_3x_atk`
- `ss_3x_stl`
- `ss_3x_shd`
- `account`
- `source_file`
- `source_name`
- `source_quality`
- `r1_idx`
- `r2_idx`
- `r3_idx`
- `is_valuable`
- `strategy_tier`
- `strategy_score`
- `l1_score`
- `l2_score`
- `scorer_cfg`
- `cm_balance`
- `profile_name`
- `slot_prob_seg`
- `full_strip1`
- `full_strip2`
- `full_strip3`
- `repl_map1`
- `repl_map2`
- `repl_map3`
- `sn`
- `csv_seq`
- `s1`
- `s2`
- `s3`
- `se_hash`
- `bet_state`
- `dedup_score`
- `triple_symbol`
- `is_acc`
- `is_spn`
- `event_label`

### Sample Rows
```json
[
  {
    "seq": 46360,
    "timestamp": "2026-04-05T02:41:32",
    "r1": 1.0,
    "r2": 4.0,
    "r3": 6.0,
    "reel_1": "coin",
    "reel_2": "steal",
    "reel_3": "spins",
    "spin_result": "gold",
    "reward_code": 1,
    "is_triple": false,
    "coins_won": 375000.0,
    "coins": 3226695582602.0,
    "spins_remaining": 217691.0,
    "shields": 5.0,
    "max_shields": 5.0,
    "bet_multiplier": 15.0,
    "bet_level": 11.0,
    "atk_count": 0.0,
    "stl_count": 1.0,
    "shd_count": 0.0,
    "spn_count": 1.0,
    "acc_count": 0.0,
    "accum_current": 151133.0,
    "accum_total": 282500.0,
    "accum_mission": 66.0,
    "accum_delta": 50.0,
    "accum_pct": 53.5,
    "gae_segment": "bonus_bs15_gae3_no",
    "gae_last_mission": 100.0,
    "gae_grand_prize": 1400000.0,
    "slot2_r1": null,
    "slot2_r2": null,
    "slot2_r3": null,
    "event_bars": null,
    "sa_spins": 105.0,
    "sa_atk": 55.0,
    "sa_stl": 41.0,
    "sa_shd": 23.0,
    "sa_spn": 29.0,
    "sa_acc": 22.0,
    "sa_3x_atk": 9.0,
    "sa_3x_stl": 5.0,
    "sa_3x_shd": 6.0,
    "ss_spins": 16.0,
    "ss_atk": 7.0,
    "ss_stl": 8.0,
    "ss_shd": 3.0,
    "ss_spn": 2.0,
    "ss_acc": 4.0,
    "ss_3x_atk": 1.0,
    "ss_3x_stl": 1.0,
    "ss_3x_shd": 1.0,
    "account": "Ahmed",
    "source_file": "data\\Ahmed\\spin_history_2026-04-05.csv",
    "source_name": "spin_history_2026-04-05.csv",
    "source_quality": 52,
    "r1_idx": null,
    "r2_idx": null,
    "r3_idx": null,
    "is_valuable": null,
    "strategy_tier": null,
    "strategy_score": null,
    "l1_score": null,
    "l2_score": null,
    "scorer_cfg": null,
    "cm_balance": null,
    "profile_name": null,
    "slot_prob_seg": null,
    "full_strip1": null,
    "full_strip2": null,
    "full_strip3": null,
    "repl_map1": null,
    "repl_map2": null,
    "repl_map3": null,
    "sn": null,
    "csv_seq": null,
    "s1": null,
    "s2": null,
    "s3": null,
    "se_hash": null,
    "bet_state": null,
    "dedup_score": 52,
    "triple_symbol": "none",
    "is_acc": false,
    "is_spn": false,
    "event_label": "gold"
  },
  {
    "seq": 46361,
    "timestamp": "2026-04-05T02:41:34",
    "r1": 4.0,
    "r2": 6.0,
    "r3": 2.0,
    "reel_1": "steal",
    "reel_2": "spins",
    "reel_3": "goldSack",
    "spin_result": "gold",
    "reward_code": 1,
    "is_triple": false,
    "coins_won": 1500000.0,
    "coins": 3226697082602.0,
    "spins_remaining": 217676.0,
    "shields": 5.0,
    "max_shields": 5.0,
    "bet_multiplier": 15.0,
    "bet_level": 11.0,
    "atk_count": 0.0,
    "stl_count": 1.0,
    "shd_count": 0.0,
    "spn_count": 1.0,
    "acc_count": 0.0,
    "accum_current": 151133.0,
    "accum_total": 282500.0,
    "accum_mission": 66.0,
    "accum_delta": 0.0,
    "accum_pct": 53.5,
    "gae_segment": "bonus_bs15_gae3_no",
    "gae_last_mission": 100.0,
    "gae_grand_prize": 1400000.0,
    "slot2_r1": null,
    "slot2_r2": null,
    "slot2_r3": null,
    "event_bars": null,
    "sa_spins": 106.0,
    "sa_atk": 55.0,
    "sa_stl": 42.0,
    "sa_shd": 23.0,
    "sa_spn": 30.0,
    "sa_acc": 22.0,
    "sa_3x_atk": 9.0,
    "sa_3x_stl": 5.0,
    "sa_3x_shd": 6.0,
    "ss_spins": 17.0,
    "ss_atk": 7.0,
    "ss_stl": 9.0,
    "ss_shd": 3.0,
    "ss_spn": 3.0,
    "ss_acc": 4.0,
    "ss_3x_atk": 1.0,
    "ss_3x_stl": 1.0,
    "ss_3x_shd": 1.0,
    "account": "Ahmed",
    "source_file": "data\\Ahmed\\spin_history_2026-04-05.csv",
    "source_name": "spin_history_2026-04-05.csv",
    "source_quality": 52,
    "r1_idx": null,
    "r2_idx": null,
    "r3_idx": null,
    "is_valuable": null,
    "strategy_tier": null,
    "strategy_score": null,
    "l1_score": null,
    "l2_score": null,
    "scorer_cfg": null,
    "cm_balance": null,
    "profile_name": null,
    "slot_prob_seg": null,
    "full_strip1": null,
    "full_strip2": null,
    "full_strip3": null,
    "repl_map1": null,
    "repl_map2": null,
    "repl_map3": null,
    "sn": null,
    "csv_seq": null,
    "s1": null,
    "s2": null,
    "s3": null,
    "se_hash": null,
    "bet_state": null,
    "dedup_score": 52,
    "triple_symbol": "none",
    "is_acc": false,
    "is_spn": false,
    "event_label": "gold"
  },
  {
    "seq": 46362,
    "timestamp": "2026-04-05T02:41:36",
    "r1": 2.0,
    "r2": 2.0,
    "r3": 2.0,
    "reel_1": "goldSack",
    "reel_2": "goldSack",
    "reel_3": "goldSack",
    "spin_result": "gold",
    "reward_code": 1,
    "is_triple": true,
    "coins_won": 24000000.0,
    "coins": 3226721082602.0,
    "spins_remaining": 217661.0,
    "shields": 5.0,
    "max_shields": 5.0,
    "bet_multiplier": 15.0,
    "bet_level": 11.0,
    "atk_count": 0.0,
    "stl_count": 0.0,
    "shd_count": 0.0,
    "spn_count": 0.0,
    "acc_count": 0.0,
    "accum_current": 151133.0,
    "accum_total": 282500.0,
    "accum_mission": 66.0,
    "accum_delta": 0.0,
    "accum_pct": 53.5,
    "gae_segment": "bonus_bs15_gae3_no",
    "gae_last_mission": 100.0,
    "gae_grand_prize": 1400000.0,
    "slot2_r1": "LongExtraDayReduced",
    "slot2_r2": "GCEaster26",
    "slot2_r3": null,
    "event_bars": "{\"slot_on_\":\"3848\\/4500@m8\"}",
    "sa_spins": 107.0,
    "sa_atk": 55.0,
    "sa_stl": 42.0,
    "sa_shd": 23.0,
    "sa_spn": 30.0,
    "sa_acc": 22.0,
    "sa_3x_atk": 9.0,
    "sa_3x_stl": 5.0,
    "sa_3x_shd": 6.0,
    "ss_spins": 18.0,
    "ss_atk": 7.0,
    "ss_stl": 9.0,
    "ss_shd": 3.0,
    "ss_spn": 3.0,
    "ss_acc": 4.0,
    "ss_3x_atk": 1.0,
    "ss_3x_stl": 1.0,
    "ss_3x_shd": 1.0,
    "account": "Ahmed",
    "source_file": "data\\Ahmed\\spin_history_2026-04-05.csv",
    "source_name": "spin_history_2026-04-05.csv",
    "source_quality": 55,
    "r1_idx": null,
    "r2_idx": null,
    "r3_idx": null,
    "is_valuable": null,
    "strategy_tier": null,
    "strategy_score": null,
    "l1_score": null,
    "l2_score": null,
    "scorer_cfg": null,
    "cm_balance": null,
    "profile_name": null,
    "slot_prob_seg": null,
    "full_strip1": null,
    "full_strip2": null,
    "full_strip3": null,
    "repl_map1": null,
    "repl_map2": null,
    "repl_map3": null,
    "sn": null,
    "csv_seq": null,
    "s1": null,
    "s2": null,
    "s3": null,
    "se_hash": null,
    "bet_state": null,
    "dedup_score": 55,
    "triple_symbol": "goldSack",
    "is_acc": false,
    "is_spn": false,
    "event_label": "T_goldSack"
  },
  {
    "seq": 46363,
    "timestamp": "2026-04-05T02:41:39",
    "r1": 3.0,
    "r2": 3.0,
    "r3": 2.0,
    "reel_1": "attack",
    "reel_2": "attack",
    "reel_3": "goldSack",
    "spin_result": "gold",
    "reward_code": 1,
    "is_triple": false,
    "coins_won": 1500000.0,
    "coins": 3226722582602.0,
    "spins_remaining": 217646.0,
    "shields": 5.0,
    "max_shields": 5.0,
    "bet_multiplier": 15.0,
    "bet_level": 11.0,
    "atk_count": 2.0,
    "stl_count": 0.0,
    "shd_count": 0.0,
    "spn_count": 0.0,
    "acc_count": 0.0,
    "accum_current": 151133.0,
    "accum_total": 282500.0,
    "accum_mission": 66.0,
    "accum_delta": 0.0,
    "accum_pct": 53.5,
    "gae_segment": "bonus_bs15_gae3_no",
    "gae_last_mission": 100.0,
    "gae_grand_prize": 1400000.0,
    "slot2_r1": null,
    "slot2_r2": null,
    "slot2_r3": null,
    "event_bars": null,
    "sa_spins": 108.0,
    "sa_atk": 57.0,
    "sa_stl": 42.0,
    "sa_shd": 23.0,
    "sa_spn": 30.0,
    "sa_acc": 22.0,
    "sa_3x_atk": 9.0,
    "sa_3x_stl": 5.0,
    "sa_3x_shd": 6.0,
    "ss_spins": 19.0,
    "ss_atk": 9.0,
    "ss_stl": 9.0,
    "ss_shd": 3.0,
    "ss_spn": 3.0,
    "ss_acc": 4.0,
    "ss_3x_atk": 1.0,
    "ss_3x_stl": 1.0,
    "ss_3x_shd": 1.0,
    "account": "Ahmed",
    "source_file": "data\\Ahmed\\spin_history_2026-04-05.csv",
    "source_name": "spin_history_2026-04-05.csv",
    "source_quality": 52,
    "r1_idx": null,
    "r2_idx": null,
    "r3_idx": null,
    "is_valuable": null,
    "strategy_tier": null,
    "strategy_score": null,
    "l1_score": null,
    "l2_score": null,
    "scorer_cfg": null,
    "cm_balance": null,
    "profile_name": null,
    "slot_prob_seg": null,
    "full_strip1": null,
    "full_strip2": null,
    "full_strip3": null,
    "repl_map1": null,
    "repl_map2": null,
    "repl_map3": null,
    "sn": null,
    "csv_seq": null,
    "s1": null,
    "s2": null,
    "s3": null,
    "se_hash": null,
    "bet_state": null,
    "dedup_score": 52,
    "triple_symbol": "none",
    "is_acc": false,
    "is_spn": false,
    "event_label": "gold"
  },
  {
    "seq": 46364,
    "timestamp": "2026-04-05T02:41:40",
    "r1": 5.0,
    "r2": 2.0,
    "r3": 2.0,
    "reel_1": "shield",
    "reel_2": "goldSack",
    "reel_3": "goldSack",
    "spin_result": "gold",
    "reward_code": 1,
    "is_triple": false,
    "coins_won": 2250000.0,
    "coins": 3226724832602.0,
    "spins_remaining": 217631.0,
    "shields": 5.0,
    "max_shields": 5.0,
    "bet_multiplier": 15.0,
    "bet_level": 11.0,
    "atk_count": 0.0,
    "stl_count": 0.0,
    "shd_count": 1.0,
    "spn_count": 0.0,
    "acc_count": 0.0,
    "accum_current": 151133.0,
    "accum_total": 282500.0,
    "accum_mission": 66.0,
    "accum_delta": 0.0,
    "accum_pct": 53.5,
    "gae_segment": "bonus_bs15_gae3_no",
    "gae_last_mission": 100.0,
    "gae_grand_prize": 1400000.0,
    "slot2_r1": null,
    "slot2_r2": null,
    "slot2_r3": null,
    "event_bars": null,
    "sa_spins": 109.0,
    "sa_atk": 57.0,
    "sa_stl": 42.0,
    "sa_shd": 24.0,
    "sa_spn": 30.0,
    "sa_acc": 22.0,
    "sa_3x_atk": 9.0,
    "sa_3x_stl": 5.0,
    "sa_3x_shd": 6.0,
    "ss_spins": 20.0,
    "ss_atk": 9.0,
    "ss_stl": 9.0,
    "ss_shd": 4.0,
    "ss_spn": 3.0,
    "ss_acc": 4.0,
    "ss_3x_atk": 1.0,
    "ss_3x_stl": 1.0,
    "ss_3x_shd": 1.0,
    "account": "Ahmed",
    "source_file": "data\\Ahmed\\spin_history_2026-04-05.csv",
    "source_name": "spin_history_2026-04-05.csv",
    "source_quality": 52,
    "r1_idx": null,
    "r2_idx": null,
    "r3_idx": null,
    "is_valuable": null,
    "strategy_tier": null,
    "strategy_score": null,
    "l1_score": null,
    "l2_score": null,
    "scorer_cfg": null,
    "cm_balance": null,
    "profile_name": null,
    "slot_prob_seg": null,
    "full_strip1": null,
    "full_strip2": null,
    "full_strip3": null,
    "repl_map1": null,
    "repl_map2": null,
    "repl_map3": null,
    "sn": null,
    "csv_seq": null,
    "s1": null,
    "s2": null,
    "s3": null,
    "se_hash": null,
    "bet_state": null,
    "dedup_score": 52,
    "triple_symbol": "none",
    "is_acc": false,
    "is_spn": false,
    "event_label": "gold"
  }
]
```

## Triple Accumulation

- Events: 496
- Baseline per-spin rate: 0.9186%

### A) Sequence
- tail-3 `gold -> gold -> spins`: 2.02% vs baseline 0.83%, p=0.009333, q=0.1867 raw p<0.05
- tail-5 `gold -> shield -> gold -> gold -> gold`: 3.23% vs baseline 2.38%, p=0.1379, q=0.5752
- tail-3 `attack -> gold -> gold`: 6.05% vs baseline 4.98%, p=0.1606, q=0.5752
- tail-5 `gold -> gold -> attack -> gold -> gold`: 4.64% vs baseline 3.70%, p=0.162, q=0.5752
- tail-5 `gold -> gold -> gold -> gold -> gold`: 44.76% vs baseline 42.61%, p=0.178, q=0.5752
- tail-5 `gold -> gold -> gold -> gold -> shield`: 2.82% vs baseline 2.19%, p=0.2054, q=0.5752
- tail-3 `gold -> gold -> shield`: 3.83% vs baseline 3.18%, p=0.2347, q=0.5752
- tail-5 `gold -> gold -> steal -> gold -> gold`: 2.02% vs baseline 1.55%, p=0.2423, q=0.5752
Practical next-5-spin signals:
- after `T_SPN`: next-5 target chance 6.66% vs baseline 4.59%, lift 1.45x, p=0.01338, q=0.1071 raw p<0.05
- after `T_coin`: next-5 target chance 5.23% vs baseline 4.59%, lift 1.14x, p=0.03473, q=0.1389 raw p<0.05
- after `T_goldSack`: next-5 target chance 4.81% vs baseline 4.59%, lift 1.05x, p=0.264, q=0.704
- after `gold`: next-5 target chance 4.61% vs baseline 4.59%, lift 1.00x, p=0.4327, q=0.8654
- after `T_steal`: next-5 target chance 4.34% vs baseline 4.59%, lift 0.95x, p=0.7005, q=0.9645
- after `T_shield`: next-5 target chance 4.35% vs baseline 4.59%, lift 0.95x, p=0.7234, q=0.9645

### B) Periodicity
- gap mean 108.75, median 104.00, std 61.00, p10 37.00, p90 172.20
- mod 25: p=0.2778, q=0.7679, hottest bins=[16, 23, 11]
- mod 50: p=0.7679, q=0.7679, hottest bins=[41, 26, 24]
- mod 100: p=0.6367, q=0.7679, hottest bins=[74, 14, 50]

### C) Bet
- bet level chi-square p=0.01921
- after bet switch: 2.56% vs steady 0.92%, lift 2.79x, p=0.3019
- bet level 7: 1.01% over 6646 spins
- bet level 8: 0.98% over 1831 spins
- bet level 11: 0.91% over 30314 spins
- bet level 10: 0.89% over 6744 spins
- bet level 9: 0.85% over 8310 spins

### D) Drought
- geometric gap fit: p=2.736e-19 raw p<0.05, mean gap 108.84, variance 3734.20
- drought 0: hit rate 0.00% vs baseline 0.92%, lift 0.00x, p=0.01731, q=0.2022
- drought 1: hit rate 0.00% vs baseline 0.92%, lift 0.00x, p=0.01731, q=0.2022
- drought 3: hit rate 0.00% vs baseline 0.92%, lift 0.00x, p=0.0173, q=0.2022
- drought 5: hit rate 0.00% vs baseline 0.92%, lift 0.00x, p=0.01729, q=0.2022
- drought 7: hit rate 0.00% vs baseline 0.92%, lift 0.00x, p=0.01728, q=0.2022

### E) Transition
- overall transition matrix chi-square p=0.000638
- after `T_SPN` next-spin target chance 1.83% vs baseline 0.92%, lift 1.99x, p=0.02526, q=0.2021 raw p<0.05
- after `gold` next-spin target chance 0.94% vs baseline 0.92%, lift 1.03x, p=0.3167, q=0.7754
- after `T_shield` next-spin target chance 1.01% vs baseline 0.92%, lift 1.10x, p=0.3415, q=0.7754
- after `T_coin` next-spin target chance 0.97% vs baseline 0.92%, lift 1.06x, p=0.3877, q=0.7754
- after `T_attack` next-spin target chance 0.81% vs baseline 0.92%, lift 0.88x, p=0.7822, q=1
- after `T_steal` next-spin target chance 0.68% vs baseline 0.92%, lift 0.74x, p=0.8735, q=1
- after `T_goldSack` next-spin target chance 0.76% vs baseline 0.92%, lift 0.83x, p=0.8755, q=1
- after `T_ACC` next-spin target chance 0.00% vs baseline 0.92%, lift 0.00x, p=1, q=1
- after `T_SPN` next-5 target chance 6.66% vs baseline 4.59%, lift 1.45x, p=0.01338, q=0.1071 raw p<0.05
- after `T_coin` next-5 target chance 5.23% vs baseline 4.59%, lift 1.14x, p=0.03473, q=0.1389 raw p<0.05
- after `T_goldSack` next-5 target chance 4.81% vs baseline 4.59%, lift 1.05x, p=0.264, q=0.704
- after `gold` next-5 target chance 4.61% vs baseline 4.59%, lift 1.00x, p=0.4327, q=0.8654
- after `T_steal` next-5 target chance 4.34% vs baseline 4.59%, lift 0.95x, p=0.7005, q=0.9645
- after `T_shield` next-5 target chance 4.35% vs baseline 4.59%, lift 0.95x, p=0.7234, q=0.9645

### F) Reel / Position
- rows with reel indices available: 6,234
- target index modes: {'r1_idx': 8, 'r2_idx': 8, 'r3_idx': 8}
- `prev r3_idx == target_idx 8`: target chance 0.80% vs baseline 1.07%, lift 0.74x, p=0.8833, q=0.9033
- `prev r2_idx == target_idx 8`: target chance 0.60% vs baseline 1.07%, lift 0.56x, p=0.9033, q=0.9033

## Triple Spins

- Events: 601
- Baseline per-spin rate: 1.1131%

### A) Sequence
- tail-3 `steal -> gold -> gold`: 3.33% vs baseline 2.20%, p=0.04716, q=0.5044 raw p<0.05
- tail-5 `gold -> gold -> steal -> gold -> gold`: 2.50% vs baseline 1.55%, p=0.05044, q=0.5044
- tail-5 `gold -> steal -> gold -> gold -> gold`: 2.33% vs baseline 1.57%, p=0.09783, q=0.6522
- tail-3 `gold -> gold -> gold`: 62.56% vs baseline 60.28%, p=0.1356, q=0.6779
- tail-5 `gold -> gold -> gold -> gold -> attack`: 4.33% vs baseline 3.71%, p=0.2407, q=0.7708
- tail-5 `shield -> gold -> gold -> gold -> gold`: 2.83% vs baseline 2.34%, p=0.2453, q=0.7708
- tail-5 `gold -> gold -> gold -> gold -> gold`: 43.93% vs baseline 42.61%, p=0.2698, q=0.7708
- tail-5 `gold -> gold -> shield -> gold -> gold`: 2.66% vs baseline 2.34%, p=0.3332, q=0.7763
Practical next-5-spin signals:
- after `T_steal`: next-5 target chance 6.26% vs baseline 5.53%, lift 1.13x, p=0.1113, q=0.6345
- after `T_attack`: next-5 target chance 5.79% vs baseline 5.53%, lift 1.05x, p=0.2525, q=0.6345
- after `T_coin`: next-5 target chance 5.73% vs baseline 5.53%, lift 1.04x, p=0.3098, q=0.6345
- after `gold`: next-5 target chance 5.59% vs baseline 5.53%, lift 1.01x, p=0.3172, q=0.6345
- after `T_shield`: next-5 target chance 5.53% vs baseline 5.53%, lift 1.00x, p=0.5107, q=0.8172
- after `T_ACC`: next-5 target chance 4.84% vs baseline 5.53%, lift 0.87x, p=0.7771, q=1

### B) Periodicity
- gap mean 89.66, median 83.00, std 56.85, p10 21.90, p90 159.20
- mod 25: p=0.3491, q=0.3491, hottest bins=[22, 4, 8]
- mod 50: p=0.07592, q=0.1139, hottest bins=[22, 28, 8]
- mod 100: p=0.01058, q=0.03175 raw p<0.05, hottest bins=[72, 18, 4]

### C) Bet
- bet level chi-square p=0.1938
- after bet switch: 7.69% vs steady 1.11%, lift 6.94x, p=0.009241 raw p<0.05
- bet level 8: 1.26% over 1831 spins
- bet level 10: 1.22% over 6744 spins
- bet level 7: 1.20% over 6646 spins
- bet level 11: 1.09% over 30314 spins
- bet level 9: 1.00% over 8310 spins

### D) Drought
- geometric gap fit: p=2.489e-13 raw p<0.05, mean gap 89.77, variance 3238.34
- drought 1: hit rate 0.17% vs baseline 1.11%, lift 0.15x, p=0.01792, q=0.249
- drought 8: hit rate 0.00% vs baseline 1.11%, lift 0.00x, p=0.00252, q=0.1168

### E) Transition
- overall transition matrix chi-square p=0.000638
- after `T_coin` next-spin target chance 1.37% vs baseline 1.11%, lift 1.23x, p=0.08259, q=0.6607
- after `T_attack` next-spin target chance 1.27% vs baseline 1.11%, lift 1.14x, p=0.2057, q=0.8227
- after `gold` next-spin target chance 1.12% vs baseline 1.11%, lift 1.01x, p=0.4364, q=0.9907
- after `T_steal` next-spin target chance 1.12% vs baseline 1.11%, lift 1.00x, p=0.5276, q=0.9907
- after `T_ACC` next-spin target chance 0.81% vs baseline 1.11%, lift 0.72x, p=0.8023, q=0.9907
- after `T_goldSack` next-spin target chance 0.98% vs baseline 1.11%, lift 0.88x, p=0.8091, q=0.9907
- after `T_shield` next-spin target chance 0.80% vs baseline 1.11%, lift 0.72x, p=0.9441, q=0.9907
- after `T_SPN` next-spin target chance 0.33% vs baseline 1.11%, lift 0.30x, p=0.9907, q=0.9907
- after `T_steal` next-5 target chance 6.26% vs baseline 5.53%, lift 1.13x, p=0.1113, q=0.6345
- after `T_attack` next-5 target chance 5.79% vs baseline 5.53%, lift 1.05x, p=0.2525, q=0.6345
- after `T_coin` next-5 target chance 5.73% vs baseline 5.53%, lift 1.04x, p=0.3098, q=0.6345
- after `gold` next-5 target chance 5.59% vs baseline 5.53%, lift 1.01x, p=0.3172, q=0.6345
- after `T_shield` next-5 target chance 5.53% vs baseline 5.53%, lift 1.00x, p=0.5107, q=0.8172
- after `T_ACC` next-5 target chance 4.84% vs baseline 5.53%, lift 0.87x, p=0.7771, q=1

### F) Reel / Position
- rows with reel indices available: 6,234
- target index modes: {'r1_idx': 6, 'r2_idx': 6, 'r3_idx': 6}
- `prev r1_idx == target_idx 6`: target chance 1.22% vs baseline 1.07%, lift 1.14x, p=0.4175, q=0.835
- `prev r2_idx == target_idx 6`: target chance 0.79% vs baseline 1.07%, lift 0.73x, p=0.8398, q=0.8398

## Plot Files

- `acc_sequence_heatmap.png`
- `acc_periodicity.png`
- `acc_bet.png`
- `acc_drought.png`
- `acc_transitions.png`
- `acc_reel_idx.png`
- `spn_sequence_heatmap.png`
- `spn_periodicity.png`
- `spn_bet.png`
- `spn_drought.png`
- `spn_transitions.png`
- `spn_reel_idx.png`