"""
24 - Incremental Event-Total Hypothesis

User's idea (2026-04-07):
  "maybe it correct it self across the entire event from the very first spin
   and adds increments to the mean"

Test: Instead of a FIXED 3-gap rolling target (300), hypothesize that the
game enforces a running target across the ENTIRE session from spin 1.

  target(N) = N * mean_gap_length
  predicted_next = target(N+1) - cumulative_sum_so_far

If the game truly "remembers" its deviation from the start of the event,
then a short burst early forces long gaps later (and vice versa).

We test:
  1. For each account, compute cumulative gap sum vs N*mean.
  2. Does gap N+1's ACTUAL length correlate with the CORRECTION needed
     to bring cumulative back to target?
  3. Build a rule: predict next_length = N*mean - cum_so_far,
     bet in a window around it, measure catches/mb.

For comparison we also test session-level mean (per CSV file) vs the
global account mean.
"""
import pickle
import statistics
from pathlib import Path

OUT = Path(__file__).parent
DATA = pickle.load(open(OUT / 'gaps.pkl', 'rb'))

lines = []
def p(s=''):
    lines.append(s)
    print(s)


def test_incremental(account, gaps, mean_override=None, per_session=False):
    """
    Walk the gap list. For each gap, compute:
      target_cum_after_n = n * mean
      correction = target_cum_after_n - cum_before
      actual_length = gaps[n].length

    If the hypothesis holds, correction ~ actual_length.
    """
    if not gaps:
        return None

    if per_session:
        # Group gaps by session
        by_sess = {}
        for g in gaps:
            by_sess.setdefault(g.get('session_idx', 0), []).append(g)
        results = []
        for sess_idx, sess_gaps in sorted(by_sess.items()):
            r = _walk(sess_gaps, mean_override)
            r['session'] = sess_idx
            results.append(r)
        return results
    else:
        return _walk(gaps, mean_override)


def _walk(gaps, mean_override=None):
    lengths = [g['length'] for g in gaps]
    if not lengths:
        return None

    mean_len = mean_override if mean_override is not None else statistics.mean(lengths)
    cum = 0
    predictions = []  # list of (actual, predicted, cum_before, target_after)

    for n, L in enumerate(lengths, start=1):
        target_after = n * mean_len
        predicted_next = target_after - cum  # what length would make cum hit target
        predictions.append({
            'n': n,
            'actual': L,
            'predicted': predicted_next,
            'cum_before': cum,
            'target_after': target_after,
            'cum_after': cum + L,
            'deviation_before': cum - (n - 1) * mean_len,
            'deviation_after': (cum + L) - n * mean_len,
        })
        cum += L

    # Correlation between predicted and actual (ignore first which is trivially = mean)
    if len(predictions) < 3:
        return {'mean': mean_len, 'n_gaps': len(predictions), 'predictions': predictions,
                'corr': None, 'mae': None}

    preds = predictions[1:]  # skip first
    actuals = [p['actual'] for p in preds]
    predicted = [p['predicted'] for p in preds]

    n = len(actuals)
    ma = sum(actuals) / n
    mp = sum(predicted) / n
    num = sum((a - ma) * (p - mp) for a, p in zip(actuals, predicted))
    da = sum((a - ma) ** 2 for a in actuals) ** 0.5
    dp = sum((p - mp) ** 2 for p in predicted) ** 0.5
    corr = num / (da * dp) if da * dp > 0 else 0
    mae = sum(abs(a - p) for a, p in zip(actuals, predicted)) / n

    return {
        'mean': mean_len,
        'n_gaps': len(predictions),
        'predictions': predictions,
        'corr': corr,
        'mae': mae,
    }


def bet_simulation(gaps, mean_len, window=15, min_predicted=50, max_predicted=250,
                   per_session=True):
    """
    Causal bet sim:
      For each gap n (starting from gap 2), compute predicted_next using
      cumulative sum from THIS session's start. Bet every spin inside
      [predicted - window, predicted + window] on gap n+1.

      Count a catch if actual_length falls in the bet window.
      mb_cost = number of spins we were 'betting'.
    """
    if per_session:
        by_sess = {}
        for g in gaps:
            by_sess.setdefault(g.get('session_idx', 0), []).append(g)
        total_catches = 0
        total_bets = 0
        total_gaps = 0
        total_in_range = 0
        for sess_idx, sess_gaps in sorted(by_sess.items()):
            c, b, n, r = _bet_run(sess_gaps, mean_len, window, min_predicted, max_predicted)
            total_catches += c
            total_bets += b
            total_gaps += n
            total_in_range += r
        return total_catches, total_bets, total_gaps, total_in_range
    else:
        return _bet_run(gaps, mean_len, window, min_predicted, max_predicted)


def _bet_run(gaps, mean_len, window, min_pred, max_pred):
    cum = 0
    catches = 0
    bets = 0
    n_pred_gaps = 0
    in_range = 0
    lengths = [g['length'] for g in gaps]

    for n, L in enumerate(lengths):
        # Before processing this gap, predict its length from cum_before
        # cum at this point = sum of previous gaps = (n) * mean - deviation
        cum_before = cum
        target_after = (n + 1) * mean_len
        predicted = target_after - cum_before

        # Only bet when prediction is sensible
        if min_pred <= predicted <= max_pred and n >= 1:
            n_pred_gaps += 1
            lo = predicted - window
            hi = predicted + window
            # Count spins we'd be betting: from spin (lo) to spin (hi)
            # But only within actual gap — bets = max(0, min(hi, L) - max(lo, 1) + 1)
            bet_lo = max(int(lo), 1)
            bet_hi = min(int(hi), L)
            if bet_hi >= bet_lo:
                bets += (bet_hi - bet_lo + 1)
                # Catch: triple landed at spin L, did L fall in [lo, hi]?
                if lo <= L <= hi:
                    catches += 1
                    in_range += 1
            elif lo <= L <= hi:
                # Gap shorter than lo — we never started betting, no catch
                pass

        cum += L

    return catches, bets, n_pred_gaps, in_range


# ===================================================================
# Run tests
# ===================================================================

p("=" * 78)
p("TEST 24: INCREMENTAL EVENT-TOTAL HYPOTHESIS")
p("=" * 78)
p("Hypothesis: target(N) = N * mean_gap,  predicted_next = N*mean - cum_so_far")
p()

for account in ['Islam', 'Nick', 'Ahmed']:
    acc_gaps = DATA[account]['gaps']['accumulation']
    if not acc_gaps:
        continue

    # Global account-level mean
    all_lens = [g['length'] for g in acc_gaps]
    global_mean = statistics.mean(all_lens)

    p(f"\n===== {account} =====")
    p(f"  gaps={len(acc_gaps)}  global_mean={global_mean:.1f}  "
      f"median={statistics.median(all_lens):.0f}  "
      f"range=[{min(all_lens)}, {max(all_lens)}]")

    # Per-session means (since each session resets)
    by_sess = {}
    for g in acc_gaps:
        by_sess.setdefault(g.get('session_idx', 0), []).append(g)

    for sess_idx, sess_gaps in sorted(by_sess.items()):
        sess_lens = [g['length'] for g in sess_gaps]
        sess_mean = statistics.mean(sess_lens)
        p(f"  session {sess_idx}: {len(sess_gaps)} gaps  mean={sess_mean:.1f}  "
          f"total_spins={sum(sess_lens)}")

        # Walk & print first 15 gaps
        res = _walk(sess_gaps, sess_mean)
        p(f"    corr(pred, actual)={res['corr']:+.3f}  MAE={res['mae']:.1f} spins")
        p(f"    {'n':>3} {'actual':>7} {'predict':>8} {'cum_bef':>8} "
          f"{'target':>8} {'dev_bef':>8} {'dev_aft':>8}")
        for pr in res['predictions'][:18]:
            p(f"    {pr['n']:>3} {pr['actual']:>7} {pr['predicted']:>8.1f} "
              f"{pr['cum_before']:>8} {pr['target_after']:>8.0f} "
              f"{pr['deviation_before']:>+8.1f} {pr['deviation_after']:>+8.1f}")
        if len(res['predictions']) > 18:
            p(f"    ... ({len(res['predictions']) - 18} more)")

p()
p("=" * 78)
p("BETTING SIM - what happens if we actually bet on the predicted length?")
p("=" * 78)

# Try several window widths and mean strategies
STRATEGIES = [
    ('global_mean', None),  # use account global mean
    ('session_mean', 'per_sess'),  # use each session's own mean
    ('fixed_100', 100),
    ('fixed_105', 105),
    ('fixed_110', 110),
    ('fixed_120', 120),
]

WINDOWS = [10, 15, 20, 25, 30]

for account in ['Islam', 'Nick', 'Ahmed']:
    acc_gaps = DATA[account]['gaps']['accumulation']
    if not acc_gaps:
        continue
    global_mean = statistics.mean([g['length'] for g in acc_gaps])
    p(f"\n----- {account} (global_mean={global_mean:.1f}) -----")
    p(f"  {'strategy':<14} {'win':>4} {'catches':>8} {'bets':>6} {'mb/hit':>8} {'rate':>6}")

    for strat_name, strat_val in STRATEGIES:
        for w in WINDOWS:
            if strat_val == 'per_sess':
                # Walk per session, each session uses its own mean
                by_sess = {}
                for g in acc_gaps:
                    by_sess.setdefault(g.get('session_idx', 0), []).append(g)
                tc, tb, tn, tr = 0, 0, 0, 0
                for sidx, sg in sorted(by_sess.items()):
                    sm = statistics.mean([g['length'] for g in sg])
                    c, b, n, r = _bet_run(sg, sm, w, 40, 250)
                    tc += c; tb += b; tn += n; tr += r
                catches, bets, npred, inrange = tc, tb, tn, tr
            else:
                use_mean = global_mean if strat_val is None else strat_val
                catches, bets, npred, inrange = bet_simulation(
                    acc_gaps, use_mean, window=w, per_session=True)
            if bets > 0:
                mb_hit = bets / max(catches, 1)
                rate = catches / max(npred, 1) * 100
                p(f"  {strat_name:<14} {w:>4} {catches:>8} {bets:>6} "
                  f"{mb_hit:>8.1f} {rate:>5.1f}%")

p()
p("=" * 78)
p("COMPARISON: fixed target vs incremental target")
p("=" * 78)
p("Fixed 3-gap rolling target (300) was found earlier to catch 23-30/gaps at 41-54 mb/hit.")
p("If incremental hypothesis is better, we should see LOWER mb/hit OR HIGHER catch count.")
p()

# Global combined metric: pool all accounts
p("\n===== POOLED (all 3 accounts) =====")
p(f"  {'strategy':<14} {'win':>4} {'catches':>8} {'bets':>6} {'mb/hit':>8} {'rate':>6}")
for strat_name, strat_val in STRATEGIES:
    for w in WINDOWS:
        tot_c = tot_b = tot_n = 0
        for account in ['Islam', 'Nick', 'Ahmed']:
            acc_gaps = DATA[account]['gaps']['accumulation']
            if not acc_gaps:
                continue
            gm = statistics.mean([g['length'] for g in acc_gaps])
            if strat_val == 'per_sess':
                by_sess = {}
                for g in acc_gaps:
                    by_sess.setdefault(g.get('session_idx', 0), []).append(g)
                for sidx, sg in sorted(by_sess.items()):
                    sm = statistics.mean([g['length'] for g in sg])
                    c, b, n, r = _bet_run(sg, sm, w, 40, 250)
                    tot_c += c; tot_b += b; tot_n += n
            else:
                use_mean = gm if strat_val is None else strat_val
                c, b, n, r = bet_simulation(acc_gaps, use_mean, window=w, per_session=True)
                tot_c += c; tot_b += b; tot_n += n
        if tot_b > 0:
            mb = tot_b / max(tot_c, 1)
            rate = tot_c / max(tot_n, 1) * 100
            p(f"  {strat_name:<14} {w:>4} {tot_c:>8} {tot_b:>6} "
              f"{mb:>8.1f} {rate:>5.1f}%")


with open(OUT / '24_incremental_mean.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f"\nSaved -> {OUT / '24_incremental_mean.txt'}")
