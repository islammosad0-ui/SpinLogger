"""
Idx Pattern Analysis — strip away cosmetic replacements, analyze raw RNG output.

The game has ONE strip of 9 positions. r1_idx, r2_idx, r3_idx are the true
RNG outputs. The displayed symbols on R1/R3 are cosmetically swapped ~69%
of the time. This analysis works ONLY with idx to find patterns the
cosmetic noise was hiding.
"""

import pandas as pd
import numpy as np
from collections import Counter, defaultdict
from pathlib import Path
from itertools import product
import sys

# ── Base strip ────────────────────────────────────────────────────────────
BASE_STRIP = {
    0: "ATK", 1: "COIN", 2: "SHIELD", 3: "GOLD", 4: "STEAL",
    5: "COIN", 6: "SPINS", 7: "GOLD", 8: "ACCUM"
}
VALUABLE_IDX = {2, 6, 8}  # shield, spins, accumulation
TRIPLE_SYM = {0: "ATK", 1: "COIN", 2: "SHIELD", 3: "GOLD", 4: "STEAL",
              5: "COIN", 6: "SPINS", 7: "GOLD", 8: "ACCUM"}

# Positions that map to the same symbol (exploit pairs)
EQUIV = {1: 5, 5: 1, 3: 7, 7: 3}  # coin(1,5) and gold(3,7)


def load_all_csvs():
    data_dir = Path(__file__).parent.parent / "data"
    dl_dir = Path.home() / "Downloads"
    csvs = sorted(data_dir.glob("**/*.csv")) + sorted(dl_dir.glob("spin_history_*2026*.csv"))

    all_dfs = []
    seen = set()
    for p in csvs:
        if p.name in seen:
            continue
        seen.add(p.name)
        try:
            df = pd.read_csv(p)
            if "reel_1" in df.columns and "r1" not in df.columns:
                df = df.rename(columns={"reel_1": "r1", "reel_2": "r2", "reel_3": "r3"})
            needed = ["r1_idx", "r2_idx", "r3_idx"]
            if not all(c in df.columns for c in needed):
                continue
            df = df.dropna(subset=needed)
            df = df[df["r1_idx"] >= 0].copy()
            for c in needed:
                df[c] = df[c].astype(int)
            if len(df) > 0:
                # Add source tag
                df["_src"] = p.stem
                print(f"  {p.name}: {len(df)} spins")
                all_dfs.append(df)
        except Exception:
            pass

    if not all_dfs:
        print("No valid data found.")
        sys.exit(1)
    df = pd.concat(all_dfs, ignore_index=True)
    print(f"\nTotal: {len(df)} spins\n")
    return df


def is_triple_idx(i1, i2, i3):
    """Triple = all three map to the same symbol (including exploit triples)."""
    s1, s2, s3 = BASE_STRIP[i1], BASE_STRIP[i2], BASE_STRIP[i3]
    return s1 == s2 == s3


def is_valuable_triple_idx(i1, i2, i3):
    s1, s2, s3 = BASE_STRIP[i1], BASE_STRIP[i2], BASE_STRIP[i3]
    if s1 != s2 or s2 != s3:
        return False
    return s1 in ("SHIELD", "SPINS", "ACCUM")


def add_derived_cols(df):
    """Add triple flags and lag columns working purely from idx."""
    df = df.copy()
    df["is_triple"] = [is_triple_idx(r1, r2, r3)
                       for r1, r2, r3 in zip(df["r1_idx"], df["r2_idx"], df["r3_idx"])]
    df["is_valuable"] = [is_valuable_triple_idx(r1, r2, r3)
                         for r1, r2, r3 in zip(df["r1_idx"], df["r2_idx"], df["r3_idx"])]
    df["triple_sym"] = [BASE_STRIP[r2] if t else "" for r2, t in zip(df["r2_idx"], df["is_triple"])]

    # Lag features
    for r in [1, 2, 3]:
        col = f"r{r}_idx"
        df[f"r{r}_lag1"] = df[col].shift(1)
        df[f"r{r}_lag2"] = df[col].shift(2)
        df[f"r{r}_delta"] = df[col] - df[col].shift(1)
    return df


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYSIS 1: Idx distribution — is the RNG uniform?
# ═══════════════════════════════════════════════════════════════════════════
def idx_distribution(df):
    print("=" * 65)
    print("  1. IDX DISTRIBUTION (is the RNG uniform across 9 positions?)")
    print("=" * 65)

    for reel in [1, 2, 3]:
        col = f"r{reel}_idx"
        counts = df[col].value_counts().sort_index()
        n = len(df)
        expected = n / 9
        print(f"\n  Reel {reel} (expected ~{expected:.0f} per position):")
        chi2 = 0
        for idx in range(9):
            c = counts.get(idx, 0)
            pct = 100.0 * c / n
            dev = (c - expected) / expected * 100
            chi2 += (c - expected) ** 2 / expected
            bar = "#" * int(pct * 2)
            print(f"    pos {idx} ({BASE_STRIP[idx]:>6}): {c:>5} ({pct:5.1f}%) {dev:+6.1f}%  {bar}")
        print(f"    chi2={chi2:.1f}  (critical ~15.5 for p=0.05, df=8)")


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYSIS 2: Cross-reel idx correlation
# ═══════════════════════════════════════════════════════════════════════════
def cross_reel_correlation(df):
    print("\n" + "=" * 65)
    print("  2. CROSS-REEL IDX CORRELATION")
    print("=" * 65)

    for pair in [(1, 2), (1, 3), (2, 3)]:
        c1, c2 = f"r{pair[0]}_idx", f"r{pair[1]}_idx"
        corr = df[c1].corr(df[c2])
        print(f"\n  R{pair[0]} x R{pair[1]}: Pearson r = {corr:.4f}")

        # Conditional: when R_a == R_b (same idx), what's the triple rate?
        same_idx = df[c1] == df[c2]
        if same_idx.sum() > 0:
            triple_when_same = df.loc[same_idx, "is_triple"].mean() * 100
            print(f"    When R{pair[0]}_idx == R{pair[1]}_idx: {same_idx.sum()} spins,"
                  f" {triple_when_same:.1f}% are triples")

    # All three same idx
    all_same = (df["r1_idx"] == df["r2_idx"]) & (df["r2_idx"] == df["r3_idx"])
    if all_same.sum() > 0:
        print(f"\n  All 3 same idx: {all_same.sum()} spins, "
              f"{df.loc[all_same, 'is_triple'].mean()*100:.1f}% triples")

    # R1 == R3 (we know from before this is strong)
    r1_eq_r3 = df["r1_idx"] == df["r3_idx"]
    print(f"  R1 == R3: {r1_eq_r3.sum()} spins, "
          f"{df.loc[r1_eq_r3, 'is_triple'].mean()*100:.1f}% triples")


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYSIS 3: Sequential idx patterns — autocorrelation per reel
# ═══════════════════════════════════════════════════════════════════════════
def sequential_patterns(df):
    print("\n" + "=" * 65)
    print("  3. SEQUENTIAL IDX PATTERNS (autocorrelation)")
    print("=" * 65)

    for reel in [1, 2, 3]:
        col = f"r{reel}_idx"
        print(f"\n  Reel {reel}:")
        for lag in [1, 2, 3, 5, 10]:
            shifted = df[col].shift(lag)
            valid = df[col].notna() & shifted.notna()
            if valid.sum() < 100:
                continue
            corr = df.loc[valid, col].corr(shifted[valid])
            # Also: does same idx repeat more than expected?
            same = (df[col] == shifted).sum()
            exp_same = len(df) / 9  # if uniform and independent
            print(f"    lag {lag:>2}: r={corr:+.4f}  same_idx={same}"
                  f" (expected ~{exp_same:.0f}, ratio={same/exp_same:.2f}x)")


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYSIS 4: Idx delta patterns before triples
# ═══════════════════════════════════════════════════════════════════════════
def delta_before_triple(df):
    print("\n" + "=" * 65)
    print("  4. IDX DELTA PATTERNS BEFORE TRIPLES")
    print("=" * 65)

    for reel in [1, 2, 3]:
        delta_col = f"r{reel}_delta"
        valid = df[delta_col].notna()
        sub = df[valid].copy()

        # Next spin is triple?
        sub["next_triple"] = sub["is_triple"].shift(-1).fillna(False).astype(bool)
        sub["next_valuable"] = sub["is_valuable"].shift(-1).fillna(False).astype(bool)

        print(f"\n  Reel {reel} delta -> next spin:")
        # Group by delta
        for delta in sorted(sub[delta_col].unique()):
            d = int(delta)
            grp = sub[sub[delta_col] == delta]
            n = len(grp)
            if n < 20:
                continue
            t_rate = grp["next_triple"].mean() * 100
            v_rate = grp["next_valuable"].mean() * 100
            print(f"    delta={d:+2d}: n={n:>5}  next_triple={t_rate:5.1f}%"
                  f"  next_valuable={v_rate:5.2f}%")

    base_t = df["is_triple"].mean() * 100
    base_v = df["is_valuable"].mean() * 100
    print(f"\n  Base rates: triple={base_t:.1f}%  valuable={base_v:.2f}%")


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYSIS 5: Idx transition matrix (R2, most reliable)
# ═══════════════════════════════════════════════════════════════════════════
def transition_matrix(df):
    print("\n" + "=" * 65)
    print("  5. R2 IDX TRANSITION MATRIX (spin N -> spin N+1)")
    print("=" * 65)

    col = "r2_idx"
    curr = df[col].values[:-1]
    nxt = df[col].values[1:]

    matrix = np.zeros((9, 9), dtype=int)
    for c, n in zip(curr, nxt):
        matrix[int(c)][int(n)] += 1

    # Row-normalize
    print(f"\n  Transition probabilities (row=from, col=to):")
    header = "       " + "".join(f"{i:>7}" for i in range(9))
    print(header)
    for i in range(9):
        row_sum = matrix[i].sum()
        if row_sum == 0:
            continue
        probs = matrix[i] / row_sum * 100
        cells = "".join(f"{p:6.1f}%" for p in probs)
        print(f"    {i} ({BASE_STRIP[i]:>5}){cells}")

    # Chi-square test for independence
    expected = np.outer(matrix.sum(axis=1), matrix.sum(axis=0)) / matrix.sum()
    valid = expected > 0
    chi2 = np.sum((matrix[valid] - expected[valid]) ** 2 / expected[valid])
    dof = (9 - 1) * (9 - 1)
    print(f"\n  Chi2 = {chi2:.1f}  (df={dof}, critical ~92.0 for p=0.05)")
    if chi2 > 92:
        print("  >>> SIGNIFICANT: transitions are NOT independent!")
    else:
        print("  >>> Not significant: transitions look independent (uniform)")


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYSIS 6: Idx combo before triple (2-spin lookback)
# ═══════════════════════════════════════════════════════════════════════════
def idx_combo_before_triple(df):
    print("\n" + "=" * 65)
    print("  6. IDX COMBOS PRECEDING TRIPLES (2-spin lookback)")
    print("=" * 65)

    # Use R2 idx (cleanest signal — no replacement noise)
    col = "r2_idx"
    df = df.copy()
    df["prev1"] = df[col].shift(1)
    df["prev2"] = df[col].shift(2)
    df = df.dropna(subset=["prev1", "prev2"])
    df["prev1"] = df["prev1"].astype(int)
    df["prev2"] = df["prev2"].astype(int)

    # Group by (prev2, prev1) pair -> triple rate on current spin
    combos = defaultdict(lambda: [0, 0, 0])  # [total, triples, valuables]
    for _, row in df.iterrows():
        key = (int(row["prev2"]), int(row["prev1"]))
        combos[key][0] += 1
        if row["is_triple"]:
            combos[key][1] += 1
        if row["is_valuable"]:
            combos[key][2] += 1

    base_t = df["is_triple"].mean()
    base_v = df["is_valuable"].mean()

    # Find combos with highest lift
    scored = []
    for (p2, p1), (n, t, v) in combos.items():
        if n < 30:  # minimum sample
            continue
        t_rate = t / n
        v_rate = v / n
        t_lift = t_rate / base_t if base_t > 0 else 0
        v_lift = v_rate / base_v if base_v > 0 else 0
        scored.append((p2, p1, n, t_rate, t_lift, v_rate, v_lift))

    scored.sort(key=lambda x: -x[4])  # sort by triple lift

    print(f"\n  Base rates: triple={base_t*100:.1f}%  valuable={base_v*100:.2f}%")
    print(f"\n  Top 15 combos by triple lift (min n=30):")
    print(f"  {'prev2':>5} {'prev1':>5}  {'n':>5}  {'triple%':>8}  {'lift':>5}  {'val%':>8}  {'v_lift':>6}")
    for p2, p1, n, tr, tl, vr, vl in scored[:15]:
        print(f"  {BASE_STRIP[p2]:>5} {BASE_STRIP[p1]:>5}  {n:>5}  {tr*100:7.1f}%  {tl:5.2f}  {vr*100:7.2f}%  {vl:5.2f}")

    print(f"\n  Bottom 15 combos by triple lift:")
    for p2, p1, n, tr, tl, vr, vl in scored[-15:]:
        print(f"  {BASE_STRIP[p2]:>5} {BASE_STRIP[p1]:>5}  {n:>5}  {tr*100:7.1f}%  {tl:5.2f}  {vr*100:7.2f}%  {vl:5.2f}")


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYSIS 7: Run-length patterns in idx
# ═══════════════════════════════════════════════════════════════════════════
def run_length_analysis(df):
    print("\n" + "=" * 65)
    print("  7. RUN-LENGTH ANALYSIS (consecutive non-triple streaks)")
    print("=" * 65)

    # How many non-triples before a triple, and does streak length predict valuable?
    streaks = []
    current_streak = 0
    for _, row in df.iterrows():
        if row["is_triple"]:
            streaks.append((current_streak, row["is_valuable"], BASE_STRIP[int(row["r2_idx"])]))
            current_streak = 0
        else:
            current_streak += 1

    print(f"\n  {len(streaks)} triple events observed")
    print(f"\n  Streak length -> valuable triple rate:")

    # Bucket streaks
    buckets = [(0, 0), (1, 1), (2, 2), (3, 3), (4, 5), (6, 10), (11, 20), (21, 50)]
    for lo, hi in buckets:
        bucket_data = [(s, v, sym) for s, v, sym in streaks if lo <= s <= hi]
        if len(bucket_data) < 10:
            continue
        n = len(bucket_data)
        val_rate = sum(1 for _, v, _ in bucket_data if v) / n * 100
        # Symbol distribution
        syms = Counter(sym for _, _, sym in bucket_data)
        top3 = syms.most_common(3)
        sym_str = ", ".join(f"{s}:{c}" for s, c in top3)
        label = f"{lo}" if lo == hi else f"{lo}-{hi}"
        print(f"    streak {label:>5}: n={n:>4}  valuable={val_rate:5.1f}%  [{sym_str}]")


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYSIS 8: R2 idx modular arithmetic patterns
# ═══════════════════════════════════════════════════════════════════════════
def modular_patterns(df):
    print("\n" + "=" * 65)
    print("  8. R2 IDX MODULAR PATTERNS (step sizes mod 9)")
    print("=" * 65)

    col = "r2_idx"
    steps = (df[col].values[1:] - df[col].values[:-1]) % 9
    triples = df["is_triple"].values[1:]
    valuables = df["is_valuable"].values[1:]

    print(f"\n  Step (mod 9) -> current spin triple rate:")
    base_t = triples.mean() * 100
    base_v = valuables.mean() * 100
    for step in range(9):
        mask = steps == step
        n = mask.sum()
        if n < 20:
            continue
        t_rate = triples[mask].mean() * 100
        v_rate = valuables[mask].mean() * 100
        lift = t_rate / base_t if base_t > 0 else 0
        print(f"    step {step}: n={n:>5}  triple={t_rate:5.1f}% (lift {lift:.2f})"
              f"  valuable={v_rate:5.2f}%")
    print(f"    base: triple={base_t:.1f}%  valuable={base_v:.2f}%")


# ═══════════════════════════════════════════════════════════════════════════
#  ANALYSIS 9: Sum of idx across reels
# ═══════════════════════════════════════════════════════════════════════════
def idx_sum_analysis(df):
    print("\n" + "=" * 65)
    print("  9. IDX SUM / SPREAD ANALYSIS")
    print("=" * 65)

    df = df.copy()
    df["idx_sum"] = df["r1_idx"] + df["r2_idx"] + df["r3_idx"]
    df["idx_spread"] = df[["r1_idx", "r2_idx", "r3_idx"]].apply(
        lambda r: r.max() - r.min(), axis=1)

    # Next-spin prediction
    df["next_triple"] = df["is_triple"].shift(-1).fillna(False).astype(bool)
    df["next_valuable"] = df["is_valuable"].shift(-1).fillna(False).astype(bool)

    base_t = df["next_triple"].mean() * 100
    base_v = df["next_valuable"].mean() * 100

    print(f"\n  Idx sum -> next-spin triple rate:")
    for s in sorted(df["idx_sum"].unique()):
        grp = df[df["idx_sum"] == s]
        n = len(grp)
        if n < 20:
            continue
        t = grp["next_triple"].mean() * 100
        v = grp["next_valuable"].mean() * 100
        lift = t / base_t if base_t > 0 else 0
        print(f"    sum={s:>2}: n={n:>5}  next_triple={t:5.1f}% (lift {lift:.2f})"
              f"  next_val={v:5.2f}%")

    print(f"\n  Idx spread -> next-spin triple rate:")
    for sp in sorted(df["idx_spread"].unique()):
        grp = df[df["idx_spread"] == sp]
        n = len(grp)
        if n < 20:
            continue
        t = grp["next_triple"].mean() * 100
        v = grp["next_valuable"].mean() * 100
        lift = t / base_t if base_t > 0 else 0
        print(f"    spread={sp}: n={n:>5}  next_triple={t:5.1f}% (lift {lift:.2f})"
              f"  next_val={v:5.2f}%")

    print(f"\n  Base rates: triple={base_t:.1f}%  valuable={base_v:.2f}%")


def main():
    print("Loading CSVs...")
    df = load_all_csvs()
    df = add_derived_cols(df)

    idx_distribution(df)
    cross_reel_correlation(df)
    sequential_patterns(df)
    delta_before_triple(df)
    transition_matrix(df)
    idx_combo_before_triple(df)
    run_length_analysis(df)
    modular_patterns(df)
    idx_sum_analysis(df)


if __name__ == "__main__":
    main()
