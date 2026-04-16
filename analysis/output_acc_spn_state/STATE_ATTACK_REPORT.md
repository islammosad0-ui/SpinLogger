ok# ACC / SPN State Attack Report

- Deduped rows: 53,993
- Accounts: {'Ahmed': 23353, 'Islam': 21288, 'Nick': 9352}

## ACC
- Events: 496

### Per-account
- Ahmed: 225 hits / 23353 spins = 0.963%; opposite-triple -> next5 6.178% over 259 cases
- Islam: 190 hits / 21288 spins = 0.893%; opposite-triple -> next5 7.950% over 239 cases
- Nick: 81 hits / 9352 spins = 0.866%; opposite-triple -> next5 4.854% over 103 cases

### Cross-signal
- after `T_SPN`: next5 ACC = 6.656% vs baseline 4.589%, lift 1.45x, p=0.01338, q=0.08029
- after `gold`: next5 ACC = 4.679% vs baseline 4.589%, lift 1.02x, p=0.1852, q=0.5556
- after `steal`: next5 ACC = 4.340% vs baseline 4.589%, lift 0.95x, p=0.7005, q=1
- after `shield`: next5 ACC = 4.351% vs baseline 4.589%, lift 0.95x, p=0.7234, q=1
- after `attack`: next5 ACC = 3.988% vs baseline 4.589%, lift 0.87x, p=0.9655, q=1
- after `T_ACC`: next5 ACC = 0.403% vs baseline 4.589%, lift 0.09x, p=1, q=1

### Index attack
- Indexed rows: 6234
- Indexed target rows: 67
- Base next1: 1.075%
- Base next5: 5.358%
- Target index consistency: {'r1_idx': {8.0: 66, -1.0: 1}, 'r2_idx': {8.0: 66, -1.0: 1}, 'r3_idx': {8.0: 66, -1.0: 1}}
- rule `prev_r3_target`: next1 1.195% vs 1.075% (lift 1.11x, p=0.3577, q=1); next5 5.113% vs 5.358% (lift 0.95x, p=0.6794, q=1)
- rule `prev_r2_target`: next1 1.205% vs 1.075% (lift 1.12x, p=0.4459, q=1); next5 4.819% vs 5.358% (lift 0.90x, p=0.7308, q=1)
- rule `sum_prev_dist_le_2`: next1 1.075% vs 1.075% (lift 1.00x, p=0.5777, q=1); next5 5.018% vs 5.358% (lift 0.94x, p=0.637, q=1)
- rule `sum_dist_le_2`: next1 0.717% vs 1.075% (lift 0.67x, p=0.8022, q=1); next5 5.018% vs 5.358% (lift 0.94x, p=0.637, q=1)
- rule `toward_target`: next1 0.727% vs 1.075% (lift 0.68x, p=0.9772, q=1); next5 5.087% vs 5.358% (lift 0.95x, p=0.7525, q=1)
- rule `prev_all_target`: next1 0.000% vs 1.075% (lift 0.00x, p=1, q=1); next5 0.000% vs 5.358% (lift 0.00x, p=1, q=1)
- rule `curr_all_target`: next1 0.000% vs 1.075% (lift 0.00x, p=1, q=1); next5 0.000% vs 5.358% (lift 0.00x, p=1, q=1)
- rule `prev_r1_target`: next1 0.000% vs 1.075% (lift 0.00x, p=1, q=1); next5 0.000% vs 5.358% (lift 0.00x, p=1, q=1)

## SPN
- Events: 601

### Per-account
- Ahmed: 259 hits / 23353 spins = 1.109%; opposite-triple -> next5 5.333% over 225 cases
- Islam: 239 hits / 21288 spins = 1.123%; opposite-triple -> next5 4.737% over 190 cases
- Nick: 103 hits / 9352 spins = 1.101%; opposite-triple -> next5 3.704% over 81 cases

### Cross-signal
- after `steal`: next5 SPN = 6.262% vs baseline 5.532%, lift 1.13x, p=0.1113, q=0.6677
- after `attack`: next5 SPN = 5.794% vs baseline 5.532%, lift 1.05x, p=0.2525, q=0.7575
- after `gold`: next5 SPN = 5.537% vs baseline 5.532%, lift 1.00x, p=0.4851, q=0.7661
- after `shield`: next5 SPN = 5.534% vs baseline 5.532%, lift 1.00x, p=0.5107, q=0.7661
- after `T_ACC`: next5 SPN = 4.839% vs baseline 5.532%, lift 0.87x, p=0.7771, q=0.9325
- after `T_SPN`: next5 SPN = 2.163% vs baseline 5.532%, lift 0.39x, p=1, q=1

### Index attack
- Indexed rows: 6234
- Indexed target rows: 67
- Base next1: 1.075%
- Base next5: 5.326%
- Target index consistency: {'r1_idx': {6.0: 67}, 'r2_idx': {6.0: 67}, 'r3_idx': {6.0: 67}}
- rule `prev_r1_target`: next1 1.573% vs 1.075% (lift 1.46x, p=0.1673, q=1); next5 4.895% vs 5.326% (lift 0.92x, p=0.7027, q=1)
- rule `toward_target`: next1 1.091% vs 1.075% (lift 1.02x, p=0.4906, q=1); next5 5.491% vs 5.326% (lift 1.03x, p=0.3588, q=1)
- rule `sum_prev_dist_le_2`: next1 0.595% vs 1.075% (lift 0.55x, p=0.8372, q=1); next5 3.571% vs 5.326% (lift 0.67x, p=0.8877, q=1)
- rule `sum_dist_le_2`: next1 0.595% vs 1.075% (lift 0.55x, p=0.8372, q=1); next5 2.976% vs 5.326% (lift 0.56x, p=0.9478, q=1)
- rule `prev_r2_target`: next1 0.338% vs 1.075% (lift 0.31x, p=0.9961, q=1); next5 4.279% vs 5.326% (lift 0.80x, p=0.9322, q=1)
- rule `prev_all_target`: next1 0.000% vs 1.075% (lift 0.00x, p=1, q=1); next5 1.493% vs 5.326% (lift 0.28x, p=0.9744, q=1)
- rule `curr_all_target`: next1 0.000% vs 1.075% (lift 0.00x, p=1, q=1); next5 1.493% vs 5.326% (lift 0.28x, p=0.9744, q=1)
- rule `prev_r3_target`: next1 0.000% vs 1.075% (lift 0.00x, p=1, q=1); next5 1.149% vs 5.326% (lift 0.22x, p=0.9914, q=1)