"""
Build comprehensive per-account gap tables.

For each ACC gap of each account, compute every quantity Islam has been
exploring across this analysis session:
  - The gap length itself, prev gap, mission, event
  - Cumulative spins / triples
  - Running mean / running median (using only prior gaps)
  - Expected K and deficit (with reference=100 and reference=running_median)
  - 3-window and 4-window rolling sum predictions (300-, 400-)
  - Three predictors: baseline (run_mean), lag-1, deficit*0.33
  - Errors for each predictor

Outputs CSV per account at analysis/nuclear/gap_tables/{Account}_gap_table.csv
plus a printed summary.
"""
import pickle
import csv
import os

with open('analysis/nuclear/gaps.pkl', 'rb') as f:
    data = pickle.load(f)

OUT_DIR = 'analysis/nuclear/gap_tables'
os.makedirs(OUT_DIR, exist_ok=True)


def run_median(arr):
    if not arr:
        return 100
    s = sorted(arr)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


# Pooled lag-1 fit from earlier test: gap[i+1] = -0.329*gap[i] + 135.1
LAG1_A = -0.329
LAG1_B = 135.1

print('=' * 78)
print('GAP TABLES — written to analysis/nuclear/gap_tables/')
print('=' * 78)

for acct in ['Ahmed', 'Islam', 'Nick']:
    gaps = data[acct]['gaps']['accumulation']
    gaps_sorted = sorted(gaps, key=lambda g: (g.get('session_idx', 0), g.get('end_idx', 0)))

    # Per-account reference values (full series — used for the "tuned" deficit)
    all_lens = [g['length'] for g in gaps_sorted]
    ACCT_MEAN = sum(all_lens) / len(all_lens)
    ACCT_MEDIAN = run_median(all_lens)

    # S0 mean/median for proper cross-session holdout (no leakage into S1)
    s0_lens = [g['length'] for g in gaps_sorted if g.get('session_idx', 0) == 0]
    S0_MEAN = (sum(s0_lens) / len(s0_lens)) if s0_lens else 100.0
    S0_MEDIAN = run_median(s0_lens) if s0_lens else 100.0

    print('\n[{}] acct mean={:.1f}  median={:.1f}  |  S0 mean={:.1f}  S0 median={:.1f}'.format(
        acct, ACCT_MEAN, ACCT_MEDIAN, S0_MEAN, S0_MEDIAN))

    rows = []
    cum_spins = 0
    K = 0
    prior_lens = []
    prev_gap = None

    for i, g in enumerate(gaps_sorted):
        L = g['length']
        sidx = g.get('session_idx', 0)

        # Predictors use only state from BEFORE this gap
        run_mean_prior = (sum(prior_lens) / len(prior_lens)) if prior_lens else 100.0
        run_med_prior = run_median(prior_lens) if prior_lens else 100.0

        cum_spins_start = cum_spins
        K_start = K

        # Deficit using fixed reference of 100
        expected_K_fix = cum_spins_start / 100.0
        deficit_K_fix = expected_K_fix - K_start
        deficit_spins_fix = deficit_K_fix * 100.0

        # Deficit using running median
        expected_K_med = cum_spins_start / max(1, run_med_prior)
        deficit_K_med = expected_K_med - K_start
        deficit_spins_med = deficit_K_med * run_med_prior

        # Deficit using ACCOUNT mean (fixed, per-account)
        expected_K_am = cum_spins_start / ACCT_MEAN
        deficit_K_am = expected_K_am - K_start
        deficit_spins_acctmean = deficit_K_am * ACCT_MEAN

        # Deficit using ACCOUNT median (fixed, per-account)
        expected_K_amed = cum_spins_start / ACCT_MEDIAN
        deficit_K_amed = expected_K_amed - K_start
        deficit_spins_acctmedian = deficit_K_amed * ACCT_MEDIAN

        # Deficit using S0 mean (no-leakage holdout — only valid in S1)
        expected_K_s0 = cum_spins_start / S0_MEAN
        deficit_K_s0 = expected_K_s0 - K_start
        deficit_spins_s0mean = deficit_K_s0 * S0_MEAN

        # Rolling-window sum predictions
        prev2_sum = sum(prior_lens[-2:]) if len(prior_lens) >= 2 else None
        prev3_sum = sum(prior_lens[-3:]) if len(prior_lens) >= 3 else None
        pred_3win = (300 - prev2_sum) if prev2_sum is not None else None
        pred_4win = (400 - prev3_sum) if prev3_sum is not None else None

        pred_baseline = run_mean_prior
        pred_lag1 = (LAG1_A * prev_gap + LAG1_B) if prev_gap is not None else None
        pred_deficit_partial = run_mean_prior - 0.33 * deficit_spins_fix
        # New: deficit predictors using account mean / median as fixed reference
        # Predictor: pred = ref - alpha * deficit_spins  (alpha=1 means full pull)
        pred_def_acctmean_full = ACCT_MEAN - deficit_spins_acctmean
        pred_def_acctmean_x033 = ACCT_MEAN - 0.33 * deficit_spins_acctmean
        pred_def_acctmedian_full = ACCT_MEDIAN - deficit_spins_acctmedian
        pred_def_acctmedian_x033 = ACCT_MEDIAN - 0.33 * deficit_spins_acctmedian

        err_base = L - pred_baseline
        err_lag1 = (L - pred_lag1) if pred_lag1 is not None else None
        err_def_partial = L - pred_deficit_partial
        err_3win = (L - pred_3win) if pred_3win is not None else None
        err_4win = (L - pred_4win) if pred_4win is not None else None
        err_def_am_full = L - pred_def_acctmean_full
        err_def_am_x033 = L - pred_def_acctmean_x033
        err_def_amed_full = L - pred_def_acctmedian_full
        err_def_amed_x033 = L - pred_def_acctmedian_x033

        rows.append({
            'i': i,
            'session': 'S{}'.format(sidx),
            'gap_length': L,
            'prev_gap': prev_gap if prev_gap is not None else '',
            'mission': g['end_mission'],
            'event': (g['end_event'] or '')[:25],
            'cum_spins_start': cum_spins_start,
            'K_start': K_start,
            'run_mean_prior': round(run_mean_prior, 1),
            'run_median_prior': round(run_med_prior, 1),
            'expected_K_at100': round(expected_K_fix, 2),
            'deficit_K_at100': round(deficit_K_fix, 2),
            'deficit_spins_at100': round(deficit_spins_fix, 1),
            'deficit_spins_at_median': round(deficit_spins_med, 1),
            'prev2_sum': prev2_sum if prev2_sum is not None else '',
            'prev3_sum': prev3_sum if prev3_sum is not None else '',
            'pred_3win_300minus': pred_3win if pred_3win is not None else '',
            'pred_4win_400minus': pred_4win if pred_4win is not None else '',
            'pred_baseline': round(pred_baseline, 1),
            'pred_lag1': round(pred_lag1, 1) if pred_lag1 is not None else '',
            'pred_deficit_x033': round(pred_deficit_partial, 1),
            # New: per-account deficit (the focus of this question)
            'deficit_spins_at_acctmean': round(deficit_spins_acctmean, 1),
            'deficit_spins_at_acctmedian': round(deficit_spins_acctmedian, 1),
            'pred_def_acctmean_full': round(pred_def_acctmean_full, 1),
            'pred_def_acctmean_x033': round(pred_def_acctmean_x033, 1),
            'pred_def_acctmedian_full': round(pred_def_acctmedian_full, 1),
            'pred_def_acctmedian_x033': round(pred_def_acctmedian_x033, 1),
            'err_baseline': round(err_base, 1),
            'err_lag1': round(err_lag1, 1) if err_lag1 is not None else '',
            'err_3win': err_3win if err_3win is not None else '',
            'err_4win': err_4win if err_4win is not None else '',
            'err_deficit_x033': round(err_def_partial, 1),
            'err_def_acctmean_full': round(err_def_am_full, 1),
            'err_def_acctmean_x033': round(err_def_am_x033, 1),
            'err_def_acctmedian_full': round(err_def_amed_full, 1),
            'err_def_acctmedian_x033': round(err_def_amed_x033, 1),
        })

        cum_spins += L
        K += 1
        prior_lens.append(L)
        prev_gap = L

    csv_path = os.path.join(OUT_DIR, '{}_gap_table_v2.csv'.format(acct))
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print('\nwrote {}  ({} rows)'.format(csv_path, len(rows)))

    # Inline preview: first 15 + last 15
    print('\n--- {} preview (first 15 + last 15 rows, compact) ---'.format(acct))
    hdr = ('  {:>3} {:>2} {:>4} {:>4} {:>3} {:>3} {:>5} {:>6} {:>7} '
           '{:>9} {:>5} {:>5} {:>6} {:>6} {:>7}').format(
        'i', 'S', 'gap', 'prv', 'mis', 'K', 'cum', 'runM', 'runMed',
        'def@100', '3win', '4win', 'errB', 'errL1', 'errDef')
    print(hdr)

    def fmt_row(r):
        prv = str(r['prev_gap']) if r['prev_gap'] != '' else '-'
        win3 = str(r['pred_3win_300minus']) if r['pred_3win_300minus'] != '' else '-'
        win4 = str(r['pred_4win_400minus']) if r['pred_4win_400minus'] != '' else '-'
        errL1 = '{:+.0f}'.format(r['err_lag1']) if r['err_lag1'] != '' else '-'
        return ('  {:>3} {:>2} {:>4} {:>4} {:>3} {:>3} {:>5} {:>6.1f} {:>7.1f} '
                '{:>+9.0f} {:>5} {:>5} {:>+6.0f} {:>6} {:>+7.0f}').format(
            r['i'], r['session'], r['gap_length'], prv, r['mission'], r['K_start'],
            r['cum_spins_start'], r['run_mean_prior'], r['run_median_prior'],
            r['deficit_spins_at100'], win3, win4,
            r['err_baseline'], errL1, r['err_deficit_x033'])

    for r in rows[:15]:
        print(fmt_row(r))
    if len(rows) > 30:
        print('  ...')
    for r in rows[-15:]:
        print(fmt_row(r))

    # Summary MAEs (skip warmup)
    base_errs = [abs(r['err_baseline']) for r in rows[5:]]
    lag1_errs = [abs(r['err_lag1']) for r in rows[5:] if r['err_lag1'] != '']
    def_errs = [abs(r['err_deficit_x033']) for r in rows[5:]]
    win3_errs = [abs(r['err_3win']) for r in rows[5:] if r['err_3win'] != '']
    win4_errs = [abs(r['err_4win']) for r in rows[5:] if r['err_4win'] != '']
    am_full = [abs(r['err_def_acctmean_full']) for r in rows[5:]]
    am_x033 = [abs(r['err_def_acctmean_x033']) for r in rows[5:]]
    amed_full = [abs(r['err_def_acctmedian_full']) for r in rows[5:]]
    amed_x033 = [abs(r['err_def_acctmedian_x033']) for r in rows[5:]]
    print('\n  MAE summary (n={}, skipping first 5 warmup gaps):'.format(len(base_errs)))
    print('    baseline (run_mean):                {:.1f}'.format(sum(base_errs) / len(base_errs)))
    print('    lag-1 ({:+.3f}*prev{:+.1f}):          {:.1f}'.format(LAG1_A, LAG1_B, sum(lag1_errs) / len(lag1_errs)))
    print('    3-window (300-prev2sum):            {:.1f}'.format(sum(win3_errs) / len(win3_errs)))
    print('    4-window (400-prev3sum):            {:.1f}'.format(sum(win4_errs) / len(win4_errs)))
    print('    deficit x0.33 (ref=100):            {:.1f}'.format(sum(def_errs) / len(def_errs)))
    print('    -- per-account reference (this question) --')
    print('    deficit FULL  (ref=acct_mean={:.1f}): {:.1f}'.format(ACCT_MEAN, sum(am_full) / len(am_full)))
    print('    deficit x0.33 (ref=acct_mean):       {:.1f}'.format(sum(am_x033) / len(am_x033)))
    print('    deficit FULL  (ref=acct_median={:.1f}): {:.1f}'.format(ACCT_MEDIAN, sum(amed_full) / len(amed_full)))
    print('    deficit x0.33 (ref=acct_median):     {:.1f}'.format(sum(amed_x033) / len(amed_x033)))

    # Cross-session holdout: use S0 mean to predict S1 (no leakage)
    s1_rows = [r for r in rows if r['session'] == 'S1']
    if s1_rows:
        s1_errs_baseline = []
        s1_errs_s0pred_full = []
        s1_errs_s0pred_x033 = []
        for r in s1_rows:
            L = r['gap_length']
            cum = r['cum_spins_start']
            K_st = r['K_start']
            deficit_s0 = (cum / S0_MEAN - K_st) * S0_MEAN
            pred_full = S0_MEAN - deficit_s0
            pred_x033 = S0_MEAN - 0.33 * deficit_s0
            s1_errs_baseline.append(abs(L - S0_MEAN))
            s1_errs_s0pred_full.append(abs(L - pred_full))
            s1_errs_s0pred_x033.append(abs(L - pred_x033))
        print('\n  HOLDOUT (S0 mean as fixed reference, predicting S1, n={}):'.format(len(s1_rows)))
        print('    baseline (predict S0_mean={:.1f}):  {:.1f}'.format(S0_MEAN, sum(s1_errs_baseline)/len(s1_errs_baseline)))
        print('    deficit FULL:                       {:.1f}'.format(sum(s1_errs_s0pred_full)/len(s1_errs_s0pred_full)))
        print('    deficit x0.33:                      {:.1f}'.format(sum(s1_errs_s0pred_x033)/len(s1_errs_s0pred_x033)))

print()
print('=' * 78)
print('All 3 CSVs written to analysis/nuclear/gap_tables/')
print('Open them in Excel - every column you might want to plot is there.')
