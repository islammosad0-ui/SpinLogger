# ACC / SPN Hot Zone Optimization

- Rows: 53,993
- Sessions: 15
- Accounts: {'Ahmed': 23353, 'Islam': 21288, 'Nick': 9352}

## ACC
- Practical picks:
- min_capture_10: `model_q975` with 3-spin window -> spins/hit 30.5, capture 10.3%, caught 51, window hit 9.5%
- min_capture_15: `model_q950` with 2-spin window -> spins/hit 34.6, capture 16.9%, caught 84, window hit 5.7%
- min_capture_20: `model_q900` with 2-spin window -> spins/hit 43.1, capture 27.0%, caught 134, window hit 4.6%
- min_capture_25: `model_q900` with 2-spin window -> spins/hit 43.1, capture 27.0%, caught 134, window hit 4.6%
- min_capture_30: `gap_warm` with 2-spin window -> spins/hit 53.7, capture 51.8%, caught 257, window hit 3.7%

- Best by spins/hit:
- `model_q950&gap_hot&acc80` @ 5 spins -> spins/hit 27.0, capture 2.4%, caught 12, windows 70, win-hit 17.1%
- `model_q950&gap_hot&acc80` @ 3 spins -> spins/hit 27.1, capture 2.2%, caught 11, windows 102, win-hit 10.8%
- `model_q950&gap_hot&acc80` @ 4 spins -> spins/hit 27.5, capture 2.2%, caught 11, windows 79, win-hit 13.9%
- `model_q900&gap_hot&acc80` @ 2 spins -> spins/hit 29.5, capture 2.6%, caught 13, windows 196, win-hit 6.6%
- `model_q975` @ 2 spins -> spins/hit 29.7, capture 9.9%, caught 49, windows 739, win-hit 6.6%
- `gap_hot&pair` @ 3 spins -> spins/hit 30.2, capture 2.4%, caught 12, windows 126, win-hit 9.5%
- `model_q975` @ 3 spins -> spins/hit 30.5, capture 10.3%, caught 51, windows 538, win-hit 9.5%
- `model_q900&gap_hot&acc80` @ 4 spins -> spins/hit 30.7, capture 2.8%, caught 14, windows 112, win-hit 12.5%
- `model_q975&gap_hot` @ 2 spins -> spins/hit 31.0, capture 7.7%, caught 38, windows 598, win-hit 6.4%
- `model_q975` @ 4 spins -> spins/hit 31.3, capture 10.5%, caught 52, windows 428, win-hit 12.1%
- `model_q975&gap_hot` @ 3 spins -> spins/hit 31.4, capture 8.1%, caught 40, windows 433, win-hit 9.2%
- `model_q975&gap_hot` @ 4 spins -> spins/hit 31.8, capture 8.3%, caught 41, windows 343, win-hit 12.0%

## SPN
- Practical picks:
- min_capture_10: `model_q950&gap_hot` with 5-spin window -> spins/hit 33.7, capture 10.8%, caught 65, window hit 14.0%
- min_capture_15: `model_q950` with 4-spin window -> spins/hit 36.9, capture 15.3%, caught 92, window hit 10.4%
- min_capture_20: `gap_hot` with 2-spin window -> spins/hit 44.0, capture 21.3%, caught 128, window hit 4.5%
- min_capture_25: `heur>=2.5` with 2-spin window -> spins/hit 49.7, capture 27.1%, caught 163, window hit 4.0%
- min_capture_30: `gap_warm` with 2-spin window -> spins/hit 49.9, capture 46.3%, caught 278, window hit 4.0%

- Best by spins/hit:
- `model_q995&gap_hot` @ 5 spins -> spins/hit 24.1, capture 2.2%, caught 13, windows 67, win-hit 19.4%
- `model_q990` @ 2 spins -> spins/hit 24.1, capture 4.2%, caught 25, windows 306, win-hit 8.2%
- `model_q995&gap_hot` @ 4 spins -> spins/hit 24.5, capture 2.0%, caught 12, windows 76, win-hit 15.8%
- `model_q990&gap_hot` @ 2 spins -> spins/hit 24.9, capture 3.5%, caught 21, windows 266, win-hit 7.9%
- `model_q995&gap_hot` @ 2 spins -> spins/hit 25.2, capture 1.7%, caught 10, windows 128, win-hit 7.8%
- `model_q995` @ 5 spins -> spins/hit 26.7, capture 2.3%, caught 14, windows 80, win-hit 17.5%
- `model_q995&gap_hot` @ 3 spins -> spins/hit 26.9, capture 1.7%, caught 10, windows 93, win-hit 10.8%
- `model_q990` @ 3 spins -> spins/hit 27.1, capture 4.0%, caught 24, windows 225, win-hit 10.7%
- `model_q995` @ 2 spins -> spins/hit 27.5, capture 1.8%, caught 11, windows 154, win-hit 7.1%
- `model_q995` @ 4 spins -> spins/hit 27.6, capture 2.2%, caught 13, windows 93, win-hit 14.0%
- `model_q990` @ 4 spins -> spins/hit 28.2, capture 4.2%, caught 25, windows 186, win-hit 13.4%
- `model_q990&gap_hot` @ 3 spins -> spins/hit 28.2, capture 3.3%, caught 20, windows 195, win-hit 10.3%