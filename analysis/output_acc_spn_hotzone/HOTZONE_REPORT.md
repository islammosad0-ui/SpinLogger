# ACC / SPN Hot Zone Backtest

- Rows: 53,993
- Sessions: 15
- Accounts: {'Ahmed': 23353, 'Islam': 21288, 'Nick': 9352}

## ACC
- Events: 496
- Base per-spin rate: 0.919%
- Base next-5 rate: 4.589%
- Top model features:
  accum_pct: 2692
  ss_stl: 1993
  sa_shd: 1793
  ss_acc: 1692
  ss_atk: 1565
  sa_stl: 1487
  sa_acc: 1479
  sa_atk: 1309
  gap_acc_mod100: 1248
  sa_spn: 1213

### Strategies
- `gap_warm`: next5 9.208% vs 4.589% (lift 2.01x), alerts 13543; windows 3024, window hit 8.532%, caught 258 / 496 (52.016%), spins/hit 56.6
- `gap_hot`: next5 10.638% vs 4.589% (lift 2.32x), alerts 5424; windows 1227, window hit 9.780%, caught 120 / 496 (24.194%), spins/hit 49.2
- `heur_warm`: next5 8.730% vs 4.589% (lift 1.90x), alerts 9588; windows 2418, window hit 7.651%, caught 185 / 496 (37.298%), spins/hit 63.2
- `heur_hot`: next5 10.471% vs 4.589% (lift 2.28x), alerts 5606; windows 1309, window hit 9.549%, caught 125 / 496 (25.202%), spins/hit 50.5
- `model_warm`: next5 9.593% vs 4.589% (lift 2.09x), alerts 10904; windows 2754, window hit 8.824%, caught 243 / 496 (48.992%), spins/hit 54.4
- `model_hot`: next5 14.418% vs 4.589% (lift 3.14x), alerts 2483; windows 662, window hit 14.048%, caught 93 / 496 (18.750%), spins/hit 33.3

## SPN
- Events: 601
- Base per-spin rate: 1.113%
- Base next-5 rate: 5.532%
- Top model features:
  accum_pct: 3450
  ss_atk: 2006
  sa_shd: 1751
  sa_atk: 1610
  ss_shd: 1587
  sa_spn: 1522
  sa_acc: 1433
  sa_stl: 1389
  ss_acc: 1323
  ss_stl: 1322

### Strategies
- `gap_warm`: next5 9.855% vs 5.532% (lift 1.78x), alerts 13607; windows 3055, window hit 9.264%, caught 283 / 601 (47.088%), spins/hit 51.9
- `gap_hot`: next5 11.125% vs 5.532% (lift 2.01x), alerts 5510; windows 1254, window hit 10.606%, caught 133 / 601 (22.130%), spins/hit 45.2
- `heur_warm`: next5 9.104% vs 5.532% (lift 1.65x), alerts 12236; windows 3447, window hit 8.326%, caught 287 / 601 (47.754%), spins/hit 58.0
- `heur_hot`: next5 10.944% vs 5.532% (lift 1.98x), alerts 5930; windows 1428, window hit 10.224%, caught 146 / 601 (24.293%), spins/hit 46.9
- `model_warm`: next5 9.831% vs 5.532% (lift 1.78x), alerts 10914; windows 2723, window hit 9.401%, caught 256 / 601 (42.596%), spins/hit 51.2
- `model_hot`: next5 13.312% vs 5.532% (lift 2.41x), alerts 2802; windows 784, window hit 12.372%, caught 97 / 601 (16.140%), spins/hit 38.4