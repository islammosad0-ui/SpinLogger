"""
Replacement Analysis — Derive dynamic symbol swaps from base strip + idx + actual symbols.

The base strip (from barSymbols[]) is:
  pos:  0    1     2       3         4      5     6      7         8
  sym:  ATK  COIN  SHIELD  GOLDSACK  STEAL  COIN  SPINS  GOLDSACK  ACCUM
  id:   3    1     5       2         4      1     6      2         30

For each spin we know:
  - idx per reel (r1_idx, r2_idx, r3_idx)
  - actual symbols (r1, r2, r3)

If strip[idx] != actual -> the game replaced that symbol.
"""

import pandas as pd
import numpy as np
from collections import Counter, defaultdict
from pathlib import Path
import sys

# ── Base strip (confirmed from barSymbols IL2CPP dump) ──────────────────
BASE_STRIP = [3, 1, 5, 2, 4, 1, 6, 2, 30]
BASE_STRIP_REV = list(reversed(BASE_STRIP))  # test reversed hypothesis

SYM_NAMES = {
    1: "coin", 2: "goldSack", 3: "attack", 4: "steal",
    5: "shield", 6: "spins", 30: "accumulation"
}

def sym(v):
    return SYM_NAMES.get(v, f"?{v}")


def load_csv(path):
    df = pd.read_csv(path)
    # Normalize column names (some files use reel_1/reel_2/reel_3)
    renames = {}
    if "reel_1" in df.columns and "r1" not in df.columns:
        renames.update({"reel_1": "r1", "reel_2": "r2", "reel_3": "r3"})
    if renames:
        df = df.rename(columns=renames)
    # Need: r1, r2, r3, r1_idx, r2_idx, r3_idx
    needed = ["r1", "r2", "r3", "r1_idx", "r2_idx", "r3_idx"]
    for c in needed:
        if c not in df.columns:
            return pd.DataFrame()  # skip files missing columns
    # Drop rows with missing idx (before scanner was active)
    df = df.dropna(subset=["r1_idx", "r2_idx", "r3_idx"])
    df = df[df["r1_idx"] >= 0].copy()
    for c in needed:
        df[c] = df[c].astype(int)
    return df


def check_strip_hypothesis(df, strip, label):
    """Check how often strip[idx] == actual for each reel."""
    print(f"\n{'='*60}")
    print(f"  STRIP HYPOTHESIS: {label}")
    print(f"  Strip: {strip}")
    print(f"  {len(df)} spins with valid idx")
    print(f"{'='*60}")

    for reel in [1, 2, 3]:
        idx_col = f"r{reel}_idx"
        sym_col = f"r{reel}"
        base = df[idx_col].map(lambda i: strip[i] if 0 <= i < len(strip) else -1)
        match = (base == df[sym_col])
        n_match = match.sum()
        n_total = len(df)
        pct = 100.0 * n_match / n_total if n_total else 0
        print(f"  Reel {reel}: {n_match}/{n_total} match ({pct:.1f}%)"
              f"  -> {n_total - n_match} replacements ({100-pct:.1f}%)")

    # Overall
    total_checks = len(df) * 3
    total_match = sum(
        (df[f"r{r}_idx"].map(lambda i: strip[i] if 0 <= i < len(strip) else -1) == df[f"r{r}"]).sum()
        for r in [1, 2, 3]
    )
    print(f"\n  Overall: {total_match}/{total_checks} match"
          f" ({100.0*total_match/total_checks:.1f}%)")
    return total_match


def analyze_replacements(df, strip):
    """Analyze what gets replaced with what."""
    print(f"\n{'='*60}")
    print(f"  REPLACEMENT PATTERNS")
    print(f"{'='*60}")

    swaps = []  # (reel, base_sym, actual_sym, idx)
    for _, row in df.iterrows():
        for reel in [1, 2, 3]:
            idx = int(row[f"r{reel}_idx"])
            actual = int(row[f"r{reel}"])
            if 0 <= idx < len(strip):
                base = strip[idx]
                if base != actual:
                    swaps.append((reel, base, actual, idx))

    print(f"\n  Total replacements: {len(swaps)} across {len(df)*3} reel-spins"
          f" ({100.0*len(swaps)/(len(df)*3):.1f}%)")

    # Swap frequency: base -> actual
    print(f"\n  Top swap pairs (base -> actual):")
    swap_counter = Counter((b, a) for _, b, a, _ in swaps)
    for (b, a), cnt in swap_counter.most_common(20):
        print(f"    {sym(b):>12} -> {sym(a):<12}  {cnt:>5}x"
              f"  ({100.0*cnt/len(swaps):.1f}%)")

    # Per reel
    for reel in [1, 2, 3]:
        reel_swaps = [(b, a) for r, b, a, _ in swaps if r == reel]
        print(f"\n  Reel {reel}: {len(reel_swaps)} replacements")
        rc = Counter(reel_swaps)
        for (b, a), cnt in rc.most_common(10):
            print(f"    {sym(b):>12} -> {sym(a):<12}  {cnt:>4}x")

    # Per position: which positions get replaced most?
    print(f"\n  Replacement rate by strip position:")
    for pos in range(len(strip)):
        pos_total = sum(1 for _, row in df.iterrows()
                       for r in [1,2,3] if int(row[f"r{r}_idx"]) == pos)
        pos_repl = sum(1 for _, b, a, i in swaps if i == pos)
        pct = 100.0 * pos_repl / pos_total if pos_total else 0
        print(f"    pos {pos} ({sym(strip[pos]):>12}): {pos_repl:>4}/{pos_total:>4}"
              f" replaced ({pct:.1f}%)")

    return swaps


def replacement_before_triple(df, strip):
    """Check: when a valuable triple happens, what replacements led to it?"""
    print(f"\n{'='*60}")
    print(f"  REPLACEMENTS ON TRIPLE SPINS")
    print(f"{'='*60}")

    triple_mask = (df["r1"] == df["r2"]) & (df["r2"] == df["r3"])
    triples = df[triple_mask]
    print(f"\n  {len(triples)} triples found")

    for _, row in triples.iterrows():
        sym_val = int(row["r1"])
        idxs = [int(row[f"r{r}_idx"]) for r in [1,2,3]]
        bases = [strip[i] if 0 <= i < len(strip) else -1 for i in idxs]
        repls = ["REPL" if b != sym_val else "base" for b in bases]
        n_repl = sum(1 for r in repls if r == "REPL")
        print(f"    seq={int(row.get('seq',0)):>6}  {sym(sym_val):>12} triple"
              f"  idx=({idxs[0]},{idxs[1]},{idxs[2]})"
              f"  base=({sym(bases[0])},{sym(bases[1])},{sym(bases[2])})"
              f"  -> {n_repl} replaced")


def replacement_predictive_signal(df, strip):
    """Check if replacement count/pattern on spin N predicts valuable triple on spin N+1."""
    print(f"\n{'='*60}")
    print(f"  PREDICTIVE SIGNAL: replacements vs next-spin outcome")
    print(f"{'='*60}")

    # Compute per-spin replacement count
    repl_counts = []
    for _, row in df.iterrows():
        n = 0
        for reel in [1, 2, 3]:
            idx = int(row[f"r{reel}_idx"])
            actual = int(row[f"r{reel}"])
            if 0 <= idx < len(strip) and strip[idx] != actual:
                n += 1
        repl_counts.append(n)

    df = df.copy()
    df["repl_count"] = repl_counts
    df["next_is_triple"] = ((df["r1"].shift(-1) == df["r2"].shift(-1)) &
                            (df["r2"].shift(-1) == df["r3"].shift(-1))).astype(int)
    df["next_is_valuable"] = (df["next_is_triple"] &
                              df["r1"].shift(-1).isin([5, 6, 30])).astype(int)

    # Drop last row (no next spin)
    df = df.iloc[:-1]

    print(f"\n  Replacement count distribution:")
    for rc in sorted(df["repl_count"].unique()):
        subset = df[df["repl_count"] == rc]
        n = len(subset)
        any_triple = subset["next_is_triple"].sum()
        val_triple = subset["next_is_valuable"].sum()
        t_rate = 100.0 * any_triple / n if n else 0
        v_rate = 100.0 * val_triple / n if n else 0
        print(f"    {rc} replacements: n={n:>5}  next_triple={any_triple:>3} ({t_rate:.1f}%)"
              f"  next_valuable={val_triple:>2} ({v_rate:.1f}%)")

    # Base rates
    base_triple = 100.0 * df["next_is_triple"].mean()
    base_valuable = 100.0 * df["next_is_valuable"].mean()
    print(f"\n  Base rates: any_triple={base_triple:.1f}%  valuable={base_valuable:.2f}%")


def main():
    # Find CSV files
    data_dir = Path(__file__).parent.parent / "data"
    csvs = sorted(data_dir.glob("**/*.csv"))

    # Also check Downloads for recent files
    dl_dir = Path.home() / "Downloads"
    csvs += sorted(dl_dir.glob("spin_history_*2026*.csv"))

    if len(sys.argv) > 1:
        csvs = [Path(sys.argv[1])]

    if not csvs:
        print("No CSV files found. Pass a path as argument.")
        sys.exit(1)

    all_dfs = []
    seen_names = set()
    for p in csvs:
        if p.name in seen_names:
            continue
        seen_names.add(p.name)
        try:
            df = load_csv(p)
            if len(df) > 0:
                print(f"Loaded {p.name}: {len(df)} spins with idx")
                all_dfs.append(df)
        except Exception as e:
            print(f"Skip {p.name}: {e}")

    if not all_dfs:
        print("No valid data found.")
        sys.exit(1)

    df = pd.concat(all_dfs, ignore_index=True)
    print(f"\nTotal: {len(df)} spins with idx data")

    # Test both strip hypotheses
    fwd_match = check_strip_hypothesis(df, BASE_STRIP, "FORWARD (as discovered)")
    rev_match = check_strip_hypothesis(df, BASE_STRIP_REV, "REVERSED")

    # Use whichever matches better
    if rev_match > fwd_match:
        print(f"\n*** REVERSED strip matches better! Using reversed. ***")
        strip = BASE_STRIP_REV
    else:
        print(f"\n*** Forward strip matches better (or equal). Using forward. ***")
        strip = BASE_STRIP

    analyze_replacements(df, strip)
    replacement_before_triple(df, strip)
    replacement_predictive_signal(df, strip)


if __name__ == "__main__":
    main()
