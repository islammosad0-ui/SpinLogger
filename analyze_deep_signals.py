"""
Deep-dive on the STRONGEST signals found in initial scan.
Focus: sa_3x counters, drought, sa_acc, event_bars tracker mechanics.
Cross-validate EVERY signal across both accounts.
"""
import pandas as pd
import numpy as np
import json
import re
from collections import defaultdict

FILES = {
    'Account 1': r'C:\Users\Islam\Downloads\Account 1 spin_history_2026-04-05.csv',
    'Account 2': r'C:\Users\Islam\Downloads\Account 2 spin_history_2026-04-04.csv',
}

dfs = {}
for name, path in FILES.items():
    df = pd.read_csv(path)
    df['is_acc_triple'] = ((df.r1 == 30) & (df.r2 == 30) & (df.r3 == 30)).astype(int)
    df['next_is_triple'] = df['is_acc_triple'].shift(-1).fillna(0).astype(int)
    dfs[name] = df

total_spins = sum(len(df) for df in dfs.values())
total_triples = sum(df.is_acc_triple.sum() for df in dfs.values())
base_rate = total_triples / total_spins

print("=" * 80)
print("DEEP SIGNAL ANALYSIS")
print("=" * 80)
print(f"Base rate: {base_rate:.6f} (1 in {1/base_rate:.1f})")

# ═══════════════════════════════════════════════════════════════════
# 1. SA_ COUNTERS: CONFIRMED — THEY RESET AFTER (30,30,30)
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 1: SA_ COUNTERS = 'SINCE-ALL' ACCUMULATORS, RESET AFTER ACC TRIPLE")
print("=" * 80)

# Verify: do ALL sa_ resets happen exactly after (30,30,30)?
for acct_name, df in dfs.items():
    sa_diff = df['sa_spins'].diff()
    resets = df[sa_diff < 0].index.tolist()
    triple_indices = df[df.is_acc_triple == 1].index.tolist()

    # Check: does every reset follow a triple?
    resets_after_triple = 0
    resets_not_after_triple = []
    for r in resets:
        if r - 1 in triple_indices:
            resets_after_triple += 1
        else:
            resets_not_after_triple.append(r)

    triples_not_followed_by_reset = 0
    for t in triple_indices:
        if t + 1 < len(df) and t + 1 not in resets:
            triples_not_followed_by_reset += 1

    print(f"\n  {acct_name}:")
    print(f"    sa_spins resets: {len(resets)}")
    print(f"    ACC triples: {len(triple_indices)}")
    print(f"    Resets after triple: {resets_after_triple}/{len(resets)}")
    print(f"    Resets NOT after triple: {len(resets_not_after_triple)}")
    if resets_not_after_triple:
        for r in resets_not_after_triple[:5]:
            ctx = df.iloc[max(0,r-2):min(len(df),r+2)][['seq','r1','r2','r3','sa_spins','sa_acc','bet_multiplier']]
            print(f"      Anomalous reset at idx {r}:")
            print(f"      {ctx.to_string()}")
    print(f"    Triples NOT followed by reset: {triples_not_followed_by_reset}")

print("\n  CONCLUSION: sa_ = 'spins since last ACC triple'. sa_spins IS the drought counter.")

# ═══════════════════════════════════════════════════════════════════
# 2. SA_3X COUNTERS — THE STRONGEST SIGNAL
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 2: SA_3X COUNTERS — TRIPLE COUNTS SINCE LAST ACC TRIPLE")
print("=" * 80)

sa_3x_cols = ['sa_3x_atk', 'sa_3x_stl', 'sa_3x_shd']

# Cross-validate: use SAME bins for both accounts
for col in sa_3x_cols:
    print(f"\n--- {col} as predictor of NEXT (30,30,30) ---")
    for acct_name, df in dfs.items():
        bins = list(range(0, 16)) + [20, 30, 50]
        df_c = df.copy()
        df_c['bin'] = pd.cut(df_c[col], bins=bins, right=False)

        results = []
        for bin_label, grp in df_c.groupby('bin', observed=True):
            if len(grp) >= 10:
                rate = grp.next_is_triple.mean()
                lift = rate / base_rate if base_rate > 0 else 0
                results.append((bin_label, rate, lift, len(grp)))

        print(f"\n  {acct_name}:")
        for b, rate, lift, n in results:
            marker = " ***" if lift > 2 else ""
            print(f"    {b}: rate={rate:.5f}, lift={lift:.2f}x, n={n}{marker}")

# sa_3x_sum cross-validated
print(f"\n--- sa_3x_sum (combined) as predictor ---")
for acct_name, df in dfs.items():
    df_c = df.copy()
    df_c['sa_3x_sum'] = df_c[sa_3x_cols].sum(axis=1)
    bins = [0, 3, 6, 9, 12, 15, 18, 21, 25, 30, 50, 100]
    df_c['bin'] = pd.cut(df_c['sa_3x_sum'], bins=bins, right=False)

    print(f"\n  {acct_name}:")
    for bin_label, grp in df_c.groupby('bin', observed=True):
        if len(grp) >= 10:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    {b}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

# ═══════════════════════════════════════════════════════════════════
# 3. SA_ACC — CROSS-VALIDATED IN BOTH ACCOUNTS
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 3: SA_ACC — ACCUMULATED ACC HITS SINCE LAST TRIPLE")
print("=" * 80)

for acct_name, df in dfs.items():
    df_c = df.copy()
    bins = [0, 5, 10, 15, 20, 25, 30, 35, 40, 50, 75, 100, 200]
    df_c['bin'] = pd.cut(df_c['sa_acc'], bins=bins, right=False)

    print(f"\n  {acct_name}:")
    for bin_label, grp in df_c.groupby('bin', observed=True):
        if len(grp) >= 15:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

# ═══════════════════════════════════════════════════════════════════
# 4. SA_SPINS (DROUGHT) — THE "TIME SINCE LAST ACC TRIPLE"
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 4: SA_SPINS = DROUGHT COUNTER (spins since last ACC triple)")
print("=" * 80)

for acct_name, df in dfs.items():
    df_c = df.copy()
    bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 150, 200, 300, 500]
    df_c['bin'] = pd.cut(df_c['sa_spins'], bins=bins, right=False)

    print(f"\n  {acct_name}:")
    for bin_label, grp in df_c.groupby('bin', observed=True):
        if len(grp) >= 15:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

    # What's the actual distribution of sa_spins at (30,30,30)?
    at_triple = df_c[df_c.is_acc_triple == 1]['sa_spins']
    print(f"  sa_spins AT (30,30,30): min={at_triple.min()}, max={at_triple.max()}, "
          f"mean={at_triple.mean():.1f}, median={at_triple.median():.1f}, "
          f"p25={at_triple.quantile(0.25):.0f}, p75={at_triple.quantile(0.75):.0f}")

# ═══════════════════════════════════════════════════════════════════
# 5. EVENT_BARS — WHAT ARE THE TRACKERS?
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 5: EVENT_BARS — TRACKER MECHANICS DECODED")
print("=" * 80)

def parse_event_bars(eb_str):
    if pd.isna(eb_str):
        return {}
    try:
        data = json.loads(eb_str)
    except:
        return {}
    result = {}
    for key, val in data.items():
        m = re.match(r'(\d+)\/(\d+)@m(\d+)', val)
        if m:
            result[key] = {
                'current': int(m.group(1)),
                'total': int(m.group(2)),
                'mission': int(m.group(3)),
            }
    return result

# Key discovery: trackers increment proportional to bet_multiplier
print("""
  TRACKER MECHANICS:
  - 'slot_on_' : per_spin/bet ratio ~0.77-0.79 (appears in BOTH accounts)
  - 'ec36d075' : per_spin/bet ratio ~0.14 (Account 1 only)
  - 'ae71c815' : per_spin/bet ratio ~0.14 (Account 2 only) — SAME ratio as ec36d075!
  - '6aa02145' : per_spin/bet ratio ~0.28 (Account 1 only)
  - 'ffb820e4' : per_spin/bet ratio ~0.28 (Account 2 only) — SAME ratio as 6aa02145!

  CONCLUSION: ec36d075 and ae71c815 are the SAME event bar on different accounts.
              6aa02145 and ffb820e4 are the SAME event bar on different accounts.

  These increment by bet_multiplier * constant EVERY spin (even when not reported).
  event_bars only REPORTS when the game decides to show the progress bar.
  The reporting frequency is ~47% of spins (every other spin roughly).
""")

# Do tracker values modulo anything predict (30,30,30)?
print("--- Tracker current value % total (normalized position) at ACC triple ---")
for acct_name, df in dfs.items():
    df['eb_parsed'] = df['event_bars'].apply(parse_event_bars)
    all_trackers = set()
    for eb in df['eb_parsed']:
        all_trackers.update(eb.keys())

    for tid in sorted(all_trackers):
        mask = df['eb_parsed'].apply(lambda x: tid in x)
        trows = df[mask].copy()
        if len(trows) < 50:
            continue

        trows['t_cur'] = trows['eb_parsed'].apply(lambda x: x[tid]['current'])
        trows['t_tot'] = trows['eb_parsed'].apply(lambda x: x[tid]['total'])
        trows['t_pct'] = trows['t_cur'] / trows['t_tot']

        # Does pct predict next ACC triple?
        trows['next_trip'] = df.loc[trows.index, 'next_is_triple']
        bins = np.arange(0, 1.05, 0.05)
        trows['pct_bin'] = pd.cut(trows['t_pct'], bins=bins, right=False)

        signals = []
        for bl, grp in trows.groupby('pct_bin', observed=True):
            if len(grp) >= 10:
                rate = grp.next_trip.mean()
                lift = rate / base_rate if base_rate > 0 else 0
                if lift > 2:
                    signals.append((bl, rate, lift, len(grp)))

        if signals:
            print(f"\n  {acct_name} tracker {tid}:")
            for b, rate, lift, n in signals:
                print(f"    pct in {b}: rate={rate:.5f}, lift={lift:.2f}x, n={n} ***")

# ═══════════════════════════════════════════════════════════════════
# 6. SS_ COUNTERS — SESSION BOUNDARIES
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 6: SS_ = 'SINCE SESSION' — WHAT TRIGGERS A SESSION?")
print("=" * 80)

for acct_name, df in dfs.items():
    ss_diff = df['ss_spins'].diff()
    boundaries = df[ss_diff < 0].index.tolist()

    print(f"\n  {acct_name}: {len(boundaries)} session boundaries")

    # What ALWAYS precedes a boundary?
    if boundaries:
        before_boundary = [b - 1 for b in boundaries if b > 0]
        before_results = df.loc[before_boundary, ['r1','r2','r3','reel_1','reel_2','reel_3']].copy()
        before_results['outcome'] = before_results.apply(
            lambda r: (r.reel_1, r.reel_2, r.reel_3), axis=1
        )

        # Is it always a triple?
        before_results['is_triple'] = (
            (before_results.r1 == before_results.r2) &
            (before_results.r2 == before_results.r3)
        )
        print(f"    Spin BEFORE boundary is a triple: {before_results.is_triple.sum()}/{len(before_results)}")

        # Is it always spins (6,6,6)?
        before_results['is_spins_triple'] = (
            (before_results.r1 == 6) & (before_results.r2 == 6) & (before_results.r3 == 6)
        )
        print(f"    Spin BEFORE boundary is (6,6,6): {before_results.is_spins_triple.sum()}/{len(before_results)}")

        # What outcomes appear before boundary?
        outcome_counts = before_results['outcome'].value_counts()
        print(f"    Outcomes before boundary: {dict(outcome_counts.head(10))}")

# ═══════════════════════════════════════════════════════════════════
# 7. SLOT2 — DECODING SECONDARY REELS
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 7: SLOT2 = SECONDARY EVENT REEL OUTCOMES")
print("=" * 80)

for acct_name, df in dfs.items():
    print(f"\n  {acct_name}:")
    slot2_cols = ['slot2_r1', 'slot2_r2', 'slot2_r3']

    # How many slot2 reels are filled?
    df['slot2_count'] = df[slot2_cols].notna().sum(axis=1)

    # When slot2 has data, what are the COMBINATIONS?
    has_any = df[df.slot2_count > 0].copy()
    has_any['slot2_combo'] = has_any.apply(
        lambda r: tuple(
            str(r[c]) if pd.notna(r[c]) else 'empty'
            for c in slot2_cols
        ), axis=1
    )
    combo_counts = has_any['slot2_combo'].value_counts().head(15)
    print(f"    Top slot2 combos:")
    for combo, count in combo_counts.items():
        print(f"      {combo}: {count}")

    # Are the two values (LongExtraDayReduced, GCEaster26) like a secondary reel?
    # Count combinations
    for s in ['LongExtraDayReduced', 'GCEaster26']:
        count_1 = (df['slot2_r1'] == s).sum()
        count_2 = (df['slot2_r2'] == s).sum()
        count_3 = (df['slot2_r3'] == s).sum()
        print(f"    '{s}': r1={count_1}, r2={count_2}, r3={count_3}")

    # Triple slot2 (all same value)
    has_3 = df[df.slot2_count == 3].copy()
    if len(has_3) > 0:
        has_3['s2_triple'] = (has_3.slot2_r1 == has_3.slot2_r2) & (has_3.slot2_r2 == has_3.slot2_r3)
        print(f"    slot2 triples (all 3 same): {has_3.s2_triple.sum()}/{len(has_3)}")

        # When slot2 is a triple of LongExtraDayReduced or GCEaster26
        for val in ['LongExtraDayReduced', 'GCEaster26']:
            s2t = has_3[
                (has_3.slot2_r1 == val) & (has_3.slot2_r2 == val) & (has_3.slot2_r3 == val)
            ]
            if len(s2t) > 0:
                rate = s2t.next_is_triple.mean()
                lift = rate / base_rate if base_rate > 0 else 0
                print(f"    slot2 triple '{val}': n={len(s2t)}, next_trip_rate={rate:.4f}, lift={lift:.2f}x")

# ═══════════════════════════════════════════════════════════════════
# 8. THE BIG QUESTION: COMBINATORIAL PREDICTION
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 8: COMBINED PREDICTORS — sa_acc + sa_3x_sum + sa_spins")
print("=" * 80)

for acct_name, df in dfs.items():
    print(f"\n  {acct_name}:")
    df_c = df.copy()
    df_c['sa_3x_sum'] = df_c[sa_3x_cols].sum(axis=1)

    # Bin sa_acc and sa_3x_sum and check lift
    acc_bins = [0, 20, 30, 40, 200]
    x3_bins = [0, 10, 15, 20, 200]
    spins_bins = [0, 50, 100, 150, 500]

    df_c['acc_bin'] = pd.cut(df_c['sa_acc'], bins=acc_bins, right=False)
    df_c['x3_bin'] = pd.cut(df_c['sa_3x_sum'], bins=x3_bins, right=False)
    df_c['spins_bin'] = pd.cut(df_c['sa_spins'], bins=spins_bins, right=False)

    # Two-way: sa_acc x sa_3x_sum
    print(f"\n  sa_acc x sa_3x_sum:")
    for (ab, xb), grp in df_c.groupby(['acc_bin', 'x3_bin'], observed=True):
        if len(grp) >= 20:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    sa_acc={ab}, sa_3x_sum={xb}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

    # Three-way: sa_spins x sa_acc x sa_3x_sum
    print(f"\n  sa_spins x sa_acc x sa_3x_sum:")
    for (sb, ab, xb), grp in df_c.groupby(['spins_bin', 'acc_bin', 'x3_bin'], observed=True):
        if len(grp) >= 15:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            if lift > 1.5:
                print(f"    spins={sb}, acc={ab}, 3x={xb}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

# ═══════════════════════════════════════════════════════════════════
# 9. DOES SA_ACC TELL YOU THE EXACT TRIP POINT?
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 9: SA_ACC AT TRIPLE — WHAT IS THE DISTRIBUTION?")
print("=" * 80)

for acct_name, df in dfs.items():
    at_triple = df[df.is_acc_triple == 1].copy()
    print(f"\n  {acct_name}: {len(at_triple)} ACC triples")
    print(f"    sa_acc at triple: {sorted(at_triple.sa_acc.tolist())}")
    print(f"    sa_spins at triple: {sorted(at_triple.sa_spins.tolist())}")
    print(f"    sa_3x_sum at triple: {sorted((at_triple[sa_3x_cols].sum(axis=1)).tolist())}")

    # What's the sa_acc value immediately BEFORE the triple?
    before_idx = at_triple.index - 1
    before_idx = before_idx[before_idx >= 0]
    before = df.loc[before_idx]
    print(f"    sa_acc BEFORE triple: {sorted(before.sa_acc.tolist())}")

    # Compute the delta: sa_acc AT triple minus sa_acc BEFORE
    # This is how many ACC symbols appear in the (30,30,30) spin itself
    for i in at_triple.index:
        if i > 0:
            delta = df.loc[i, 'sa_acc'] - df.loc[i-1, 'sa_acc']
            # Should always be 3 (since 30,30,30 = 3 acc symbols)
            if delta != 3:
                print(f"    ANOMALY: idx {i}, delta={delta}")
    # Actually sample the deltas
    deltas = []
    for i in at_triple.index:
        if i > 0:
            deltas.append(df.loc[i, 'sa_acc'] - df.loc[i-1, 'sa_acc'])
    print(f"    sa_acc delta at triple: {set(deltas)}")

# ═══════════════════════════════════════════════════════════════════
# 10. CAN WE PREDICT WITH accum_pct?
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 10: ACCUM_PCT AS PREDICTOR")
print("=" * 80)

for acct_name, df in dfs.items():
    print(f"\n  {acct_name}:")
    df_c = df.copy()
    bins = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    df_c['bin'] = pd.cut(df_c['accum_pct'], bins=bins, right=True)

    for bin_label, grp in df_c.groupby('bin', observed=True):
        if len(grp) >= 15:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    accum_pct in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

    # accum_pct at triple
    at_triple = df_c[df_c.is_acc_triple == 1].accum_pct
    print(f"    accum_pct AT triple: mean={at_triple.mean():.1f}, median={at_triple.median():.1f}")

# ═══════════════════════════════════════════════════════════════════
# 11. ANOMALOUS SA_ RESETS NOT AFTER TRIPLE
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 11: ANOMALOUS SA_ RESETS (not after ACC triple)")
print("=" * 80)

for acct_name, df in dfs.items():
    sa_diff = df['sa_spins'].diff()
    resets = df[sa_diff < 0].index.tolist()
    triple_indices = set(df[df.is_acc_triple == 1].index.tolist())

    anomalous = [r for r in resets if r - 1 not in triple_indices]
    print(f"\n  {acct_name}: {len(anomalous)} anomalous resets (not after triple)")

    for idx in anomalous:
        ctx = df.iloc[max(0,idx-3):min(len(df),idx+3)]
        cols = ['seq','r1','r2','r3','sa_spins','sa_acc','bet_multiplier','accum_pct']
        print(f"\n    Reset at idx {idx}:")
        print(f"    {ctx[cols].to_string()}")

# ═══════════════════════════════════════════════════════════════════
# 12. HOW RELIABLY DOES THE GAME HIT (30,30,30) WITHIN sa_spins RANGES?
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 12: CUMULATIVE PROBABILITY — WHAT % OF ACC TRIPLES HAPPEN BY SPIN N?")
print("=" * 80)

for acct_name, df in dfs.items():
    at_triple = df[df.is_acc_triple == 1]['sa_spins'].values
    total = len(at_triple)

    print(f"\n  {acct_name} ({total} triples):")
    for threshold in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120, 150, 200, 250, 300, 400]:
        pct = (at_triple <= threshold).sum() / total * 100
        if pct > 0:
            print(f"    By sa_spins <= {threshold}: {pct:.1f}% of ACC triples")

# ═══════════════════════════════════════════════════════════════════
# 13. DOES ACCUM_PCT MATTER FOR PREDICTION?
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("FINDING 13: CONDITIONAL ON HIGH SA_ACC, DOES ACCUM_PCT ADD VALUE?")
print("=" * 80)

for acct_name, df in dfs.items():
    print(f"\n  {acct_name}:")
    df_c = df.copy()
    df_c['high_sa_acc'] = df_c['sa_acc'] >= 30

    # Within high sa_acc, bin by accum_pct
    high = df_c[df_c.high_sa_acc].copy()
    bins = [0, 20, 40, 60, 80, 100]
    high['pct_bin'] = pd.cut(high['accum_pct'], bins=bins, right=True)

    for bin_label, grp in high.groupby('pct_bin', observed=True):
        if len(grp) >= 10:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate if base_rate > 0 else 0
            marker = " ***" if lift > 2 else ""
            print(f"    sa_acc>=30 & accum_pct in {bin_label}: rate={rate:.5f}, lift={lift:.2f}x, n={len(grp)}{marker}")

# ═══════════════════════════════════════════════════════════════════
# FINAL: ACTIONABLE SIGNAL SUMMARY
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("ACTIONABLE SIGNAL SUMMARY")
print("=" * 80)

# Compute the strongest combined signal across both accounts
all_signals = []
for acct_name, df in dfs.items():
    df_c = df.copy()
    df_c['sa_3x_sum'] = df_c[sa_3x_cols].sum(axis=1)

    # Test every sa_acc threshold
    for thresh in range(5, 80, 5):
        grp = df_c[df_c.sa_acc >= thresh]
        if len(grp) >= 20:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate
            all_signals.append(('sa_acc', f'>={thresh}', acct_name, rate, lift, len(grp)))

    # Test every sa_3x_sum threshold
    for thresh in range(3, 40, 3):
        grp = df_c[df_c.sa_3x_sum >= thresh]
        if len(grp) >= 20:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate
            all_signals.append(('sa_3x_sum', f'>={thresh}', acct_name, rate, lift, len(grp)))

    # Test every sa_spins threshold
    for thresh in range(20, 300, 10):
        grp = df_c[df_c.sa_spins >= thresh]
        if len(grp) >= 20:
            rate = grp.next_is_triple.mean()
            lift = rate / base_rate
            all_signals.append(('sa_spins', f'>={thresh}', acct_name, rate, lift, len(grp)))

# Show signals that appear in BOTH accounts with >2x
print("\n  Consistent signals (>2x in BOTH accounts):")
sig_df = pd.DataFrame(all_signals, columns=['feature', 'threshold', 'account', 'rate', 'lift', 'n'])
for (feat, thresh), grp in sig_df.groupby(['feature', 'threshold']):
    if len(grp) == 2:  # both accounts
        min_lift = grp.lift.min()
        if min_lift > 2.0:
            a1 = grp[grp.account == 'Account 1'].iloc[0]
            a2 = grp[grp.account == 'Account 2'].iloc[0]
            print(f"    {feat} {thresh}: A1 lift={a1.lift:.2f}x (n={int(a1.n)}), "
                  f"A2 lift={a2.lift:.2f}x (n={int(a2.n)})")

print("\n  Highest lift in BOTH accounts (>1.5x min):")
for (feat, thresh), grp in sig_df.groupby(['feature', 'threshold']):
    if len(grp) == 2:
        min_lift = grp.lift.min()
        max_lift = grp.lift.max()
        if min_lift > 1.5 and max_lift > 2.0:
            a1 = grp[grp.account == 'Account 1'].iloc[0]
            a2 = grp[grp.account == 'Account 2'].iloc[0]
            print(f"    {feat} {thresh}: A1 lift={a1.lift:.2f}x (n={int(a1.n)}), "
                  f"A2 lift={a2.lift:.2f}x (n={int(a2.n)})")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
