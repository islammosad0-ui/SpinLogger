# ACC / SPN Exhaustive Hunt

- Rows: 53,993
- Sessions: 15
- Accounts: {'Ahmed': 23353, 'Islam': 21288, 'Nick': 9352}

## Sessions
- `Ahmed|spin_history_2026-04-05.csv`: 7622 spins, ACC 1.010%, SPN 1.141%, bet levels 8
- `Ahmed|spin_history_2026-04-06.csv`: 5325 spins, ACC 0.939%, SPN 1.127%, bet levels 2
- `Ahmed|spin_history_Ahmed_2026-04-08.csv`: 2179 spins, ACC 1.010%, SPN 1.147%, bet levels 1
- `Ahmed|spin_history_Ahmed_2026-04-13.csv`: 1953 spins, ACC 1.075%, SPN 1.229%, bet levels 5
- `Ahmed|spin_history_Ahmed_2026-04-14.csv`: 881 spins, ACC 0.908%, SPN 0.795%, bet levels 1
- `Ahmed|spin_history_Ahmed_enriched.csv`: 5393 spins, ACC 0.872%, SPN 1.038%, bet levels 4
- `Islam|spin_history_2026-04-04.csv`: 8379 spins, ACC 0.991%, SPN 1.134%, bet levels 1
- `Islam|spin_history_2026-04-06.csv`: 4681 spins, ACC 0.812%, SPN 1.154%, bet levels 1
- `Islam|spin_history_Islam_2026-04-10.csv`: 2560 spins, ACC 0.859%, SPN 1.172%, bet levels 2
- `Islam|spin_history_Islam_2026-04-13.csv`: 2770 spins, ACC 1.011%, SPN 1.119%, bet levels 2
- `Islam|spin_history_default_2026-04-06.csv`: 2898 spins, ACC 0.656%, SPN 1.001%, bet levels 1
- `Nick|spin_history_2026-04-04.csv`: 2318 spins, ACC 0.820%, SPN 1.381%, bet levels 7
- `Nick|spin_history_2026-04-06.csv`: 788 spins, ACC 0.888%, SPN 1.015%, bet levels 2
- `Nick|spin_history_Nick_2026-04-08.csv`: 5829 spins, ACC 0.841%, SPN 1.046%, bet levels 3
- `Nick|spin_history_Nick_2026-04-13.csv`: 417 spins, ACC 1.439%, SPN 0.480%, bet levels 1

## ACC
- Events: 496
- Base per-spin rate: 0.919%
- Base next-5 rate: 4.589%

### Best Rules
- `prev_pair_any & gap_high_p90`: next5 16.226% vs 4.589%, lift 3.54x, n=265, p=0, q=0
- `gap_high_p90 & acc_pct_high`: next5 13.296% vs 4.589%, lift 2.90x, n=895, p=0, q=0
- `gap_high_p90 & last10_triples_ge1`: next5 10.667% vs 4.589%, lift 2.32x, n=5325, p=0, q=0
- `gap_high_p90`: next5 10.638% vs 4.589%, lift 2.32x, n=5424, p=0, q=0
- `gap_high_p90 & gap_high_p75`: next5 10.638% vs 4.589%, lift 2.32x, n=5424, p=0, q=0
- `gap_high_p90 & idx_sum_lag1_high`: next5 10.638% vs 4.589%, lift 2.32x, n=5424, p=0, q=0
- `gap_high_p75 & acc_pct_high`: next5 10.077% vs 4.589%, lift 2.20x, n=2084, p=0, q=0
- `gap_high_p90 & acc_delta_pos`: next5 9.608% vs 4.589%, lift 2.09x, n=1301, p=0, q=0
- `gap_high_p90 & entropy_high`: next5 9.588% vs 4.589%, lift 2.09x, n=2065, p=0, q=0
- `gap_high_p75 & last10_triples_ge1`: next5 9.239% vs 4.589%, lift 2.01x, n=13281, p=0, q=0
- `gap_high_p75 & idx_sum_lag1_high`: next5 9.208% vs 4.589%, lift 2.01x, n=13542, p=0, q=0
- `gap_high_p75`: next5 9.208% vs 4.589%, lift 2.01x, n=13543, p=0, q=0
- `gap_high_p75 & last5_spn_ge3`: next5 8.955% vs 4.589%, lift 1.95x, n=2077, p=0, q=0
- `gap_high_p90 & bet_level_high`: next5 8.657% vs 4.589%, lift 1.89x, n=3754, p=0, q=0
- `gap_high_p75 & entropy_high`: next5 8.592% vs 4.589%, lift 1.87x, n=5249, p=0, q=0

### Model
- Ahmed|spin_history_2026-04-05.csv top10pct: 17.824% vs 5.051%, lift 3.53x, n=763
- Ahmed|spin_history_2026-04-05.csv top5pct: 19.634% vs 5.051%, lift 3.89x, n=382
- Ahmed|spin_history_2026-04-06.csv top10pct: 11.445% vs 4.695%, lift 2.44x, n=533
- Ahmed|spin_history_2026-04-06.csv top5pct: 15.730% vs 4.695%, lift 3.35x, n=267
- Ahmed|spin_history_Ahmed_enriched.csv top10pct: 9.815% vs 4.358%, lift 2.25x, n=540
- Ahmed|spin_history_Ahmed_enriched.csv top5pct: 10.000% vs 4.358%, lift 2.29x, n=270
- Ahmed|spin_history_Ahmed_2026-04-08.csv top10pct: 15.138% vs 5.048%, lift 3.00x, n=218
- Ahmed|spin_history_Ahmed_2026-04-08.csv top5pct: 25.688% vs 5.048%, lift 5.09x, n=109
- Ahmed|spin_history_Ahmed_2026-04-13.csv top10pct: 13.776% vs 5.376%, lift 2.56x, n=196
- Ahmed|spin_history_Ahmed_2026-04-13.csv top5pct: 14.286% vs 5.376%, lift 2.66x, n=98
- Ahmed|spin_history_Ahmed_2026-04-14.csv top10pct: 17.978% vs 4.540%, lift 3.96x, n=89
- Ahmed|spin_history_Ahmed_2026-04-14.csv top5pct: 15.556% vs 4.540%, lift 3.43x, n=45
- Islam|spin_history_2026-04-04.csv top10pct: 11.667% vs 4.929%, lift 2.37x, n=840
- Islam|spin_history_2026-04-04.csv top5pct: 13.126% vs 4.929%, lift 2.66x, n=419
- Islam|spin_history_2026-04-06.csv top10pct: 8.955% vs 4.059%, lift 2.21x, n=469
- Islam|spin_history_2026-04-06.csv top5pct: 11.064% vs 4.059%, lift 2.73x, n=235
- Islam|spin_history_default_2026-04-06.csv top10pct: 7.586% vs 3.278%, lift 2.31x, n=290
- Islam|spin_history_default_2026-04-06.csv top5pct: 9.655% vs 3.278%, lift 2.95x, n=145
- Islam|spin_history_Islam_2026-04-10.csv top10pct: 9.302% vs 4.297%, lift 2.16x, n=258
- Islam|spin_history_Islam_2026-04-10.csv top5pct: 9.375% vs 4.297%, lift 2.18x, n=128
- Top features:
  coins: 1634
  spins_remaining: 1352
  accum_current: 1079
  sa_shd: 929
  seq: 907
  sa_stl: 878
  gap_acc_mod100: 873
  sa_acc: 851
  ss_acc: 811
  accum_pct_lag5: 806

### Change Points
- Ahmed|spin_history_2026-04-05.csv: 6 breaks
- Ahmed|spin_history_2026-04-06.csv: 6 breaks
- Ahmed|spin_history_Ahmed_2026-04-08.csv: 4 breaks
- Ahmed|spin_history_Ahmed_2026-04-13.csv: 3 breaks
- Ahmed|spin_history_Ahmed_2026-04-14.csv: 1 breaks
- Ahmed|spin_history_Ahmed_enriched.csv: 6 breaks
- Islam|spin_history_2026-04-04.csv: 6 breaks
- Islam|spin_history_2026-04-06.csv: 6 breaks
- Islam|spin_history_Islam_2026-04-10.csv: 5 breaks
- Islam|spin_history_Islam_2026-04-13.csv: 5 breaks

### Affine Index Search
- Rules tested: 243
- r3_idx: next=(a*prev+b) mod 9 with a=0, b=0 -> match 30.348%, target precision 0.000%
- r1_idx: next=(a*prev+b) mod 9 with a=0, b=3 -> match 24.667%, target precision 0.000%
- r3_idx: next=(a*prev+b) mod 9 with a=0, b=8 -> match 24.186%, target precision 24.186%
- r1_idx: next=(a*prev+b) mod 9 with a=0, b=7 -> match 20.045%, target precision 0.000%
- r3_idx: next=(a*prev+b) mod 9 with a=1, b=0 -> match 19.066%, target precision 22.406%
- r3_idx: next=(a*prev+b) mod 9 with a=8, b=8 -> match 17.686%, target precision 24.590%
- r3_idx: next=(a*prev+b) mod 9 with a=8, b=0 -> match 17.589%, target precision 24.641%
- r1_idx: next=(a*prev+b) mod 9 with a=6, b=6 -> match 15.503%, target precision 0.000%
- r1_idx: next=(a*prev+b) mod 9 with a=1, b=0 -> match 15.423%, target precision 0.000%
- r3_idx: next=(a*prev+b) mod 9 with a=7, b=0 -> match 15.343%, target precision 26.742%

## SPN
- Events: 601
- Base per-spin rate: 1.113%
- Base next-5 rate: 5.532%

### Best Rules
- `gap_high_p90 & acc_pct_high`: next5 13.341% vs 5.532%, lift 2.41x, n=922, p=0, q=0
- `gap_high_p90 & entropy_high`: next5 11.748% vs 5.532%, lift 2.12x, n=2077, p=0, q=0
- `gap_high_p90 & last10_triples_ge1`: next5 11.254% vs 5.532%, lift 2.03x, n=5358, p=0, q=0
- `gap_high_p90`: next5 11.125% vs 5.532%, lift 2.01x, n=5510, p=0, q=0
- `gap_high_p90 & gap_high_p75`: next5 11.125% vs 5.532%, lift 2.01x, n=5510, p=0, q=0
- `gap_high_p90 & idx_sum_lag1_high`: next5 11.117% vs 5.532%, lift 2.01x, n=5505, p=0, q=0
- `gap_high_p90 & acc_delta_pos`: next5 10.851% vs 5.532%, lift 1.96x, n=1281, p=0, q=0
- `gap_high_p75 & last5_acc_ge3`: next5 10.721% vs 5.532%, lift 1.94x, n=3274, p=0, q=0
- `gap_high_p90 & last5_acc_ge3`: next5 10.660% vs 5.532%, lift 1.93x, n=1379, p=0, q=0
- `gap_high_p90 & bet_level_high`: next5 10.580% vs 5.532%, lift 1.91x, n=3346, p=0, q=0
- `gap_high_p75 & entropy_high`: next5 10.449% vs 5.532%, lift 1.89x, n=5101, p=0, q=0
- `gap_high_p75 & acc_pct_high`: next5 10.161% vs 5.532%, lift 1.84x, n=2234, p=0, q=0
- `gap_high_p75 & acc_delta_pos`: next5 10.051% vs 5.532%, lift 1.82x, n=3134, p=0, q=0
- `gap_high_p75`: next5 9.855% vs 5.532%, lift 1.78x, n=13607, p=0, q=0
- `gap_high_p75 & last10_triples_ge1`: next5 9.850% vs 5.532%, lift 1.78x, n=13279, p=0, q=0

### Model
- Ahmed|spin_history_2026-04-05.csv top10pct: 12.713% vs 5.681%, lift 2.24x, n=763
- Ahmed|spin_history_2026-04-05.csv top5pct: 18.848% vs 5.681%, lift 3.32x, n=382
- Ahmed|spin_history_2026-04-06.csv top10pct: 10.882% vs 5.653%, lift 1.93x, n=533
- Ahmed|spin_history_2026-04-06.csv top5pct: 13.858% vs 5.653%, lift 2.45x, n=267
- Ahmed|spin_history_Ahmed_enriched.csv top10pct: 10.926% vs 5.173%, lift 2.11x, n=540
- Ahmed|spin_history_Ahmed_enriched.csv top5pct: 12.963% vs 5.173%, lift 2.51x, n=270
- Ahmed|spin_history_Ahmed_2026-04-08.csv top10pct: 14.220% vs 5.691%, lift 2.50x, n=218
- Ahmed|spin_history_Ahmed_2026-04-08.csv top5pct: 21.101% vs 5.691%, lift 3.71x, n=109
- Ahmed|spin_history_Ahmed_2026-04-13.csv top10pct: 12.245% vs 6.144%, lift 1.99x, n=196
- Ahmed|spin_history_Ahmed_2026-04-13.csv top5pct: 11.224% vs 6.144%, lift 1.83x, n=98
- Ahmed|spin_history_Ahmed_2026-04-14.csv top10pct: 13.483% vs 3.973%, lift 3.39x, n=89
- Ahmed|spin_history_Ahmed_2026-04-14.csv top5pct: 15.556% vs 3.973%, lift 3.92x, n=45
- Islam|spin_history_2026-04-04.csv top10pct: 12.649% vs 5.562%, lift 2.27x, n=838
- Islam|spin_history_2026-04-04.csv top5pct: 13.604% vs 5.562%, lift 2.45x, n=419
- Islam|spin_history_2026-04-06.csv top10pct: 11.940% vs 5.768%, lift 2.07x, n=469
- Islam|spin_history_2026-04-06.csv top5pct: 15.319% vs 5.768%, lift 2.66x, n=235
- Islam|spin_history_default_2026-04-06.csv top10pct: 10.345% vs 5.176%, lift 2.00x, n=290
- Islam|spin_history_default_2026-04-06.csv top5pct: 15.862% vs 5.176%, lift 3.06x, n=145
- Islam|spin_history_Islam_2026-04-10.csv top10pct: 6.226% vs 5.625%, lift 1.11x, n=257
- Islam|spin_history_Islam_2026-04-10.csv top5pct: 7.812% vs 5.625%, lift 1.39x, n=128
- Top features:
  seq: 1257
  ss_atk: 1206
  accum_current: 1185
  spins_remaining: 1157
  coins: 1138
  ss_shd: 846
  sa_stl: 829
  ss_acc: 689
  sa_atk: 686
  ss_spn: 686

### Change Points
- Ahmed|spin_history_2026-04-05.csv: 6 breaks
- Ahmed|spin_history_2026-04-06.csv: 6 breaks
- Ahmed|spin_history_Ahmed_2026-04-08.csv: 4 breaks
- Ahmed|spin_history_Ahmed_2026-04-13.csv: 3 breaks
- Ahmed|spin_history_Ahmed_2026-04-14.csv: 1 breaks
- Ahmed|spin_history_Ahmed_enriched.csv: 6 breaks
- Islam|spin_history_2026-04-04.csv: 6 breaks
- Islam|spin_history_2026-04-06.csv: 6 breaks
- Islam|spin_history_Islam_2026-04-10.csv: 5 breaks
- Islam|spin_history_Islam_2026-04-13.csv: 5 breaks

### Affine Index Search
- Rules tested: 243
- r3_idx: next=(a*prev+b) mod 9 with a=0, b=0 -> match 30.348%, target precision 0.000%
- r1_idx: next=(a*prev+b) mod 9 with a=0, b=3 -> match 24.667%, target precision 0.000%
- r3_idx: next=(a*prev+b) mod 9 with a=0, b=8 -> match 24.186%, target precision 0.000%
- r1_idx: next=(a*prev+b) mod 9 with a=0, b=7 -> match 20.045%, target precision 0.000%
- r3_idx: next=(a*prev+b) mod 9 with a=1, b=0 -> match 19.066%, target precision 0.000%
- r3_idx: next=(a*prev+b) mod 9 with a=8, b=8 -> match 17.686%, target precision 1.201%
- r3_idx: next=(a*prev+b) mod 9 with a=8, b=0 -> match 17.589%, target precision 0.760%
- r1_idx: next=(a*prev+b) mod 9 with a=6, b=6 -> match 15.503%, target precision 9.724%
- r1_idx: next=(a*prev+b) mod 9 with a=1, b=0 -> match 15.423%, target precision 12.937%
- r3_idx: next=(a*prev+b) mod 9 with a=7, b=0 -> match 15.343%, target precision 0.000%