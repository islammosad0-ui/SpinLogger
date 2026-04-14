"""
Idx Weight Drift Analysis — Do per-reel position weights shift over time or by account?

If the game's weighted dice change, we can detect the shift and predict outcomes.
"""

import pandas as pd
import numpy as np
from collections import Counter
from pathlib import Path
from scipy import stats
import sys

BASE_STRIP = {
    0: "ATK", 1: "COIN", 2: "SHIELD", 3: "GOLD", 4: "STEAL",
    5: "COIN", 6: "SPINS", 7: "GOLD", 8: "ACCUM"
}


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
                # Extract account from filename
                name = p.stem.lower()
                if "ahmed" in name:
                    df["account"] = "Ahmed"
                elif "islam" in name:
                    df["account"] = "Islam"
                elif "nick" in name:
                    df["account"] = "Nick"
                else:
                    df["account"] = "Unknown"
                df["_src"] = p.stem
                print(f"  {p.name}: {len(df)} spins ({df['account'].iloc[0]})")
                all_dfs.append(df)
        except Exception:
            pass

    df = pd.concat(all_dfs, ignore_index=True)
    print(f"\nTotal: {len(df)} spins\n")
    return df


def is_triple(r1, r2, r3):
    return BASE_STRIP[r1] == BASE_STRIP[r2] == BASE_STRIP[r3]

def is_valuable(r1, r2, r3):
    if not is_triple(r1, r2, r3):
        return False
    return BASE_STRIP[r2] in ("SHIELD", "SPINS", "ACCUM")


# ═══════════════════════════════════════════════════════════════════════════
#  1. PER-ACCOUNT IDX DISTRIBUTIONS
# ═══════════════════════════════════════════════════════════════════════════
def per_account_distributions(df):
    print("=" * 70)
    print("  1. PER-ACCOUNT IDX DISTRIBUTIONS")
    print("=" * 70)

    accounts = sorted(df["account"].unique())
    for reel in [1, 2, 3]:
        col = f"r{reel}_idx"
        print(f"\n  Reel {reel}:")
        header = f"  {'pos':>3} {'sym':>6}"
        for acc in accounts:
            header += f"  {acc:>12}"
        print(header)

        # Collect distributions for chi2 test
        observed = {}
        for acc in accounts:
            sub = df[df["account"] == acc]
            observed[acc] = sub[col].value_counts().sort_index()

        for pos in range(9):
            row = f"  {pos:>3} {BASE_STRIP[pos]:>6}"
            for acc in accounts:
                n = len(df[df["account"] == acc])
                c = observed[acc].get(pos, 0)
                pct = 100.0 * c / n if n else 0
                row += f"  {pct:>5.1f}% ({c:>4})"
            print(row)

        # Chi-square test: are distributions different across accounts?
        if len(accounts) >= 2:
            contingency = np.zeros((9, len(accounts)), dtype=int)
            for j, acc in enumerate(accounts):
                for pos in range(9):
                    contingency[pos][j] = observed[acc].get(pos, 0)
            chi2, p, dof, _ = stats.chi2_contingency(contingency)
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
            print(f"  Chi2 cross-account: {chi2:.1f} (p={p:.4f}) {sig}")


# ═══════════════════════════════════════════════════════════════════════════
#  2. TEMPORAL DRIFT — SLIDING WINDOWS
# ═══════════════════════════════════════════════════════════════════════════
def temporal_drift(df):
    print("\n" + "=" * 70)
    print("  2. TEMPORAL DRIFT — IDX WEIGHTS OVER TIME (200-spin windows)")
    print("=" * 70)

    window = 200
    step = 100

    for reel in [1, 2, 3]:
        col = f"r{reel}_idx"
        print(f"\n  Reel {reel}:")

        # Per account separately (don't mix sequences)
        for acc in sorted(df["account"].unique()):
            sub = df[df["account"] == acc].reset_index(drop=True)
            if len(sub) < window:
                continue

            print(f"\n    Account: {acc} ({len(sub)} spins)")
            header = f"    {'window':>12}"
            for pos in range(9):
                header += f"  {pos}({BASE_STRIP[pos][:2]:>2})"
            header += "  triple%  val%"
            print(header)

            # Global distribution for this account
            global_dist = sub[col].value_counts(normalize=True).sort_index()

            windows_data = []
            for start in range(0, len(sub) - window + 1, step):
                chunk = sub.iloc[start:start + window]
                dist = chunk[col].value_counts(normalize=True).sort_index()
                triples = sum(1 for _, r in chunk.iterrows()
                             if is_triple(int(r["r1_idx"]), int(r["r2_idx"]), int(r["r3_idx"])))
                vals = sum(1 for _, r in chunk.iterrows()
                          if is_valuable(int(r["r1_idx"]), int(r["r2_idx"]), int(r["r3_idx"])))
                t_rate = 100.0 * triples / window
                v_rate = 100.0 * vals / window

                row = f"    {start:>5}-{start+window-1:<5}"
                for pos in range(9):
                    pct = dist.get(pos, 0) * 100
                    row += f"  {pct:5.1f}"
                row += f"  {t_rate:6.1f}  {v_rate:5.1f}"
                print(row)
                windows_data.append({
                    "start": start, "t_rate": t_rate, "v_rate": v_rate,
                    **{f"p{p}": dist.get(p, 0) for p in range(9)}
                })

            # Correlation between position weights and triple/valuable rates
            if len(windows_data) >= 5:
                wdf = pd.DataFrame(windows_data)
                print(f"\n    Correlation: position weight vs triple rate (across windows):")
                for pos in range(9):
                    r, p = stats.pearsonr(wdf[f"p{pos}"], wdf["t_rate"])
                    sig = " *" if p < 0.05 else ""
                    print(f"      pos {pos} ({BASE_STRIP[pos]:>6}): r={r:+.3f} (p={p:.3f}){sig}")

                print(f"    Correlation: position weight vs VALUABLE triple rate:")
                for pos in range(9):
                    r, p = stats.pearsonr(wdf[f"p{pos}"], wdf["v_rate"])
                    sig = " *" if p < 0.05 else ""
                    print(f"      pos {pos} ({BASE_STRIP[pos]:>6}): r={r:+.3f} (p={p:.3f}){sig}")


# ═══════════════════════════════════════════════════════════════════════════
#  3. REGIME DETECTION — KS TEST ON HALVES
# ═══════════════════════════════════════════════════════════════════════════
def regime_detection(df):
    print("\n" + "=" * 70)
    print("  3. REGIME DETECTION — FIRST HALF vs SECOND HALF (KS test)")
    print("=" * 70)

    for acc in sorted(df["account"].unique()):
        sub = df[df["account"] == acc].reset_index(drop=True)
        if len(sub) < 200:
            continue

        mid = len(sub) // 2
        first = sub.iloc[:mid]
        second = sub.iloc[mid:]

        print(f"\n  {acc}: first {mid} vs last {len(sub)-mid} spins")

        for reel in [1, 2, 3]:
            col = f"r{reel}_idx"
            ks_stat, ks_p = stats.ks_2samp(first[col], second[col])
            sig = "***" if ks_p < 0.001 else "**" if ks_p < 0.01 else "*" if ks_p < 0.05 else ""
            print(f"    R{reel}: KS={ks_stat:.4f} p={ks_p:.4f} {sig}")

            if ks_p < 0.05:
                # Show what changed
                d1 = first[col].value_counts(normalize=True).sort_index()
                d2 = second[col].value_counts(normalize=True).sort_index()
                biggest_shift = 0
                shift_pos = 0
                for pos in range(9):
                    p1 = d1.get(pos, 0)
                    p2 = d2.get(pos, 0)
                    shift = abs(p2 - p1)
                    if shift > biggest_shift:
                        biggest_shift = shift
                        shift_pos = pos
                        shift_dir = "UP" if p2 > p1 else "DOWN"
                p1_pct = d1.get(shift_pos, 0) * 100
                p2_pct = d2.get(shift_pos, 0) * 100
                print(f"      Biggest shift: pos {shift_pos} ({BASE_STRIP[shift_pos]}) "
                      f"{p1_pct:.1f}% -> {p2_pct:.1f}% ({shift_dir})")


# ═══════════════════════════════════════════════════════════════════════════
#  4. TRIPLE RATE IN HIGH/LOW WEIGHT ZONES
# ═══════════════════════════════════════════════════════════════════════════
def weight_zone_triple_rate(df):
    print("\n" + "=" * 70)
    print("  4. WEIGHT ZONE ANALYSIS — WHEN RARE POSITIONS CLUSTER")
    print("=" * 70)

    # For each reel, identify "rare" positions (bottom 3 by frequency)
    for reel in [1, 2, 3]:
        col = f"r{reel}_idx"
        freq = df[col].value_counts(normalize=True).sort_values()
        rare_positions = set(freq.index[:3])
        common_positions = set(freq.index[-3:])

        print(f"\n  Reel {reel}:")
        print(f"    Rare positions: {[f'{p}({BASE_STRIP[p]})' for p in sorted(rare_positions)]}")
        print(f"    Common positions: {[f'{p}({BASE_STRIP[p]})' for p in sorted(common_positions)]}")

        # Rolling: count of rare positions in last 20 spins
        window = 20
        rare_counts = []
        for i in range(len(df)):
            if i < window:
                rare_counts.append(np.nan)
            else:
                chunk = df[col].iloc[i-window:i]
                rare_counts.append(sum(1 for v in chunk if v in rare_positions))
        df[f"r{reel}_rare_count"] = rare_counts

    # Now: when rare positions cluster across reels, what's the triple rate?
    df = df.copy()
    df["total_rare"] = df["r1_rare_count"] + df["r2_rare_count"] + df["r3_rare_count"]
    df["is_triple"] = [is_triple(int(r1), int(r2), int(r3))
                       for r1, r2, r3 in zip(df["r1_idx"], df["r2_idx"], df["r3_idx"])]
    df["is_valuable"] = [is_valuable(int(r1), int(r2), int(r3))
                         for r1, r2, r3 in zip(df["r1_idx"], df["r2_idx"], df["r3_idx"])]

    valid = df.dropna(subset=["total_rare"])
    base_t = valid["is_triple"].mean() * 100
    base_v = valid["is_valuable"].mean() * 100

    print(f"\n  Total rare-position count (last 20 spins, all reels) -> triple rate:")
    for rc in sorted(valid["total_rare"].unique()):
        grp = valid[valid["total_rare"] == rc]
        n = len(grp)
        if n < 30:
            continue
        t = grp["is_triple"].mean() * 100
        v = grp["is_valuable"].mean() * 100
        lift = t / base_t if base_t > 0 else 0
        v_lift = v / base_v if base_v > 0 else 0
        print(f"    rare_count={int(rc):>2}: n={n:>5}  triple={t:5.1f}% (lift {lift:.2f})"
              f"  valuable={v:5.2f}% (lift {v_lift:.2f})")
    print(f"    base: triple={base_t:.1f}%  valuable={base_v:.2f}%")


# ═══════════════════════════════════════════════════════════════════════════
#  5. POSITION-SPECIFIC STREAKS -> WHAT FOLLOWS
# ═══════════════════════════════════════════════════════════════════════════
def position_streak_signal(df):
    print("\n" + "=" * 70)
    print("  5. POSITION-SPECIFIC STREAKS (R2) -> NEXT OUTCOME")
    print("=" * 70)

    col = "r2_idx"
    df = df.copy()
    df["is_triple"] = [is_triple(int(r1), int(r2), int(r3))
                       for r1, r2, r3 in zip(df["r1_idx"], df["r2_idx"], df["r3_idx"])]
    df["is_valuable"] = [is_valuable(int(r1), int(r2), int(r3))
                         for r1, r2, r3 in zip(df["r1_idx"], df["r2_idx"], df["r3_idx"])]

    # For each position, track how many times it's appeared in last N spins
    # and check if concentration predicts triples
    lookback = 10
    base_t = df["is_triple"].mean() * 100
    base_v = df["is_valuable"].mean() * 100

    print(f"\n  R2 position concentration (last {lookback} spins) -> current triple rate:")

    for pos in range(9):
        # Rolling count
        counts = []
        for i in range(len(df)):
            if i < lookback:
                counts.append(np.nan)
            else:
                counts.append(sum(1 for v in df[col].iloc[i-lookback:i] if v == pos))
        df[f"p{pos}_count"] = counts

        valid = df.dropna(subset=[f"p{pos}_count"])
        print(f"\n    pos {pos} ({BASE_STRIP[pos]:>6}) count in last {lookback}:")
        for c in sorted(valid[f"p{pos}_count"].unique()):
            grp = valid[valid[f"p{pos}_count"] == c]
            n = len(grp)
            if n < 30:
                continue
            t = grp["is_triple"].mean() * 100
            v = grp["is_valuable"].mean() * 100
            lift = t / base_t if base_t else 0
            print(f"      count={int(c)}: n={n:>5}  triple={t:5.1f}% (lift {lift:.2f})"
                  f"  valuable={v:5.2f}%")

    print(f"\n  Base: triple={base_t:.1f}%  valuable={base_v:.2f}%")


# ═══════════════════════════════════════════════════════════════════════════
#  6. ACCOUNT-SPECIFIC IDX WEIGHT FINGERPRINT
# ═══════════════════════════════════════════════════════════════════════════
def account_fingerprint(df):
    print("\n" + "=" * 70)
    print("  6. ACCOUNT FINGERPRINT — PER-REEL WEIGHT PROFILE")
    print("=" * 70)

    for reel in [1, 2, 3]:
        col = f"r{reel}_idx"
        print(f"\n  Reel {reel} weight profile per account:")
        print(f"  {'Account':>10}  {'n':>5}", end="")
        for pos in range(9):
            print(f"  {pos}({BASE_STRIP[pos][:2]:>2})", end="")
        print("  entropy  triple%  val%")

        for acc in sorted(df["account"].unique()):
            sub = df[df["account"] == acc]
            n = len(sub)
            dist = sub[col].value_counts(normalize=True).sort_index()

            # Entropy
            probs = [dist.get(p, 0) for p in range(9)]
            probs = [p for p in probs if p > 0]
            entropy = -sum(p * np.log2(p) for p in probs)

            # Triple/valuable rates
            triples = sum(1 for _, r in sub.iterrows()
                         if is_triple(int(r["r1_idx"]), int(r["r2_idx"]), int(r["r3_idx"])))
            vals = sum(1 for _, r in sub.iterrows()
                      if is_valuable(int(r["r1_idx"]), int(r["r2_idx"]), int(r["r3_idx"])))
            t_rate = 100.0 * triples / n
            v_rate = 100.0 * vals / n

            row = f"  {acc:>10}  {n:>5}"
            for pos in range(9):
                pct = dist.get(pos, 0) * 100
                row += f"  {pct:5.1f}"
            row += f"  {entropy:.3f}   {t_rate:5.1f}   {v_rate:4.1f}"
            print(row)

        # Uniform entropy reference
        print(f"  {'uniform':>10}  {'':>5}", end="")
        for _ in range(9):
            print(f"  {11.1:5.1f}", end="")
        print(f"  {np.log2(9):.3f}")


def main():
    print("Loading CSVs...")
    df = load_all_csvs()

    per_account_distributions(df)
    temporal_drift(df)
    regime_detection(df)
    weight_zone_triple_rate(df)
    position_streak_signal(df)
    account_fingerprint(df)


if __name__ == "__main__":
    main()
