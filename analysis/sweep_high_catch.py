#!/usr/bin/env python3
"""Push catch% as high as possible — fine threshold sweep + multi-horizon.

Strategies tried:
  A. Low flat thresholds on K=5 (sweep 0.005 .. 0.08 across all t).
  B. K=10 horizon with same sweep (longer model promise = more fire room).
  C. STICKY/LATCH: once any-K fires, force-fire for next N spins.
  D. OR-of-heads: fire if ACC-K=5 OR ANY-K=5 OR ANY-K=10 each above their thr.
  E. Per-row diagnostic: at spins_to_vt==1, what is the p5/p10 distribution?
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = {
    "Ahmed": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Ahmed/spin_predictions_all_combos.csv",
    "Islam": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Islam/spin_predictions_all_combos.csv",
    "Nick":  ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211319_Nick/spin_predictions_all_combos.csv",
}


def score_simple(df, fire_mask_col, max_bet_spins=25):
    """Walk fires per cycle, catch at spins_to_vt==1, cap bets."""
    n_cycles = df["cycle_id"].nunique()
    caught = bets_total = 0
    for cid, g in df.groupby("cycle_id", sort=False):
        g = g.sort_values("t").reset_index(drop=True)
        s2v = g["spins_to_vt"].astype(int).to_numpy()
        fires = g[fire_mask_col].astype(bool).to_numpy()
        bets = 0
        cycle_caught = False
        for i, fire in enumerate(fires):
            if not fire:
                continue
            if bets >= max_bet_spins:
                break
            bets += 1
            if s2v[i] == 1:
                cycle_caught = True
                break
        bets_total += bets
        if cycle_caught:
            caught += 1
    return {
        "cycles": n_cycles, "caught": caught,
        "catch_pct": 100 * caught / n_cycles,
        "bets": bets_total,
        "bets_per_vt": bets_total / caught if caught else float("nan"),
    }


def add_sticky(df, fire_col, latch_n):
    """If fire_col fires at row i, force-fire rows i..i+latch_n-1 of same cycle."""
    df = df.copy()
    out = df[fire_col].astype(int).to_numpy().copy()
    cycle_ids = df["cycle_id"].to_numpy()
    n = len(out)
    # Walk each cycle's window
    for cid, g in df.groupby("cycle_id", sort=False):
        idxs = g.index.to_numpy()
        f = out[idxs]
        new = f.copy()
        run = 0
        for j, v in enumerate(f):
            if v:
                run = latch_n
            elif run > 0:
                new[j] = 1
                run -= 1
        out[idxs] = new
    df["_sticky"] = out.astype(bool)
    return df


def main():
    print(f"\n{'='*100}")
    print("HIGH-CATCH SWEEP — strict metric (catch = fire at spins_to_vt==1; bets cap 25/cycle)")
    print(f"{'='*100}\n")

    # === DIAGNOSTIC: distribution of p5/p10 at spins_to_vt==1 ===
    print("[A] Distribution of p_y_any_next5 / p_y_any_next10 at spins_to_vt==1")
    print(f"  (these are the rows we MUST fire on to catch — what threshold catches X%?)\n")
    print(f"{'account':<8} {'metric':<25} {'p25':>6} {'p50':>6} {'p70':>6} {'p80':>6} {'p90':>6}")
    print("-" * 70)
    for acct, csv_path in RUNS.items():
        df = pd.read_csv(csv_path)
        last = df[df["spins_to_vt"] == 1]
        for col in ("p_y_any_next5", "p_y_any_next10", "p_y_acc_next5", "p_y_acc_next10"):
            arr = last[col].dropna().to_numpy()
            print(f"{acct:<8} {col:<25} "
                  f"{np.percentile(arr, 25):>6.3f} {np.percentile(arr, 50):>6.3f} "
                  f"{np.percentile(arr, 70):>6.3f} {np.percentile(arr, 80):>6.3f} "
                  f"{np.percentile(arr, 90):>6.3f}")
        print()

    # === FLAT SWEEPS on K=5 and K=10 ===
    for head_label, head_col in [("ANY_VT-K5",  "p_y_any_next5"),
                                  ("ANY_VT-K10", "p_y_any_next10")]:
        print(f"\n[B] Flat-threshold sweep, head={head_label}")
        print(f"{'account':<8} {'thr':>6} {'caught':>6} {'catch%':>7} {'bets':>6} {'B/VT':>7}")
        print("-" * 50)
        for acct, csv_path in RUNS.items():
            df = pd.read_csv(csv_path)
            for thr in (0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.08, 0.10):
                df["_fire"] = df[head_col].ge(thr) & df["t"].between(15, 100)
                r = score_simple(df, "_fire")
                print(f"{acct:<8} {thr:>6.3f} {r['caught']:>6} "
                      f"{r['catch_pct']:>6.2f}% {r['bets']:>6} {r['bets_per_vt']:>7.2f}")
            print()

    # === STICKY: latch fire for N spins after any K=10 trigger ===
    print(f"\n[C] STICKY (latch fire for N spins after K=10 trigger ≥thr)")
    print(f"{'account':<8} {'thr':>6} {'latch':>5} {'caught':>6} {'catch%':>7} {'bets':>6} {'B/VT':>7}")
    print("-" * 60)
    for acct, csv_path in RUNS.items():
        df = pd.read_csv(csv_path)
        for thr in (0.05, 0.08, 0.10, 0.15):
            for latch in (5, 10, 15, 25):
                df["_seed"] = df["p_y_any_next10"].ge(thr) & df["t"].between(15, 100)
                df_s = add_sticky(df, "_seed", latch)
                r = score_simple(df_s, "_sticky")
                print(f"{acct:<8} {thr:>6.3f} {latch:>5} {r['caught']:>6} "
                      f"{r['catch_pct']:>6.2f}% {r['bets']:>6} {r['bets_per_vt']:>7.2f}")
        print()


if __name__ == "__main__":
    main()
