#!/usr/bin/env python3
"""Strict-metric sweep with NO bet cap (user spins through entire fire streak).

Also tries the K=10 horizon and OR-of-heads to maximize catch.
"""

from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = {
    "Ahmed": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Ahmed/spin_predictions_all_combos.csv",
    "Islam": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Islam/spin_predictions_all_combos.csv",
    "Nick":  ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211319_Nick/spin_predictions_all_combos.csv",
}


def score_uncapped(df, fire_mask_col):
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


def main():
    print(f"\n{'='*100}")
    print("UNCAPPED strict-metric sweep — user keeps spinning through entire fire streak")
    print(f"{'='*100}\n")

    print(f"{'account':<8} {'config':<35} {'caught':>6} {'catch%':>7} {'bets':>7} {'B/VT':>7}")
    print("-" * 80)

    for acct, csv_path in RUNS.items():
        df = pd.read_csv(csv_path)

        # Flat-threshold sweep ANY_VT-K5
        for thr in (0.005, 0.02, 0.05, 0.08, 0.10, 0.15):
            df["_f"] = df["p_y_any_next5"].ge(thr) & df["t"].between(15, 100)
            r = score_uncapped(df, "_f")
            print(f"{acct:<8} {f'flat-K5-thr{thr:.3f}':<35} "
                  f"{r['caught']:>6} {r['catch_pct']:>6.2f}% "
                  f"{r['bets']:>7} {r['bets_per_vt']:>7.2f}")

        # Flat ANY_VT-K10
        for thr in (0.05, 0.08, 0.10, 0.15, 0.20):
            df["_f"] = df["p_y_any_next10"].ge(thr) & df["t"].between(15, 100)
            r = score_uncapped(df, "_f")
            print(f"{acct:<8} {f'flat-K10-thr{thr:.3f}':<35} "
                  f"{r['caught']:>6} {r['catch_pct']:>6.2f}% "
                  f"{r['bets']:>7} {r['bets_per_vt']:>7.2f}")

        # OR of K5 and K10
        for thr5, thr10 in [(0.05, 0.10), (0.05, 0.15), (0.08, 0.15)]:
            df["_f"] = ((df["p_y_any_next5"].ge(thr5)) | (df["p_y_any_next10"].ge(thr10))) \
                       & df["t"].between(15, 100)
            r = score_uncapped(df, "_f")
            print(f"{acct:<8} {f'OR-K5≥{thr5}|K10≥{thr10}':<35} "
                  f"{r['caught']:>6} {r['catch_pct']:>6.2f}% "
                  f"{r['bets']:>7} {r['bets_per_vt']:>7.2f}")

        # ALL-FIRE in window [15,100] (theoretical max)
        df["_f"] = df["t"].between(15, 100)
        r = score_uncapped(df, "_f")
        print(f"{acct:<8} {'ALL-FIRE in [15,100]':<35} "
              f"{r['caught']:>6} {r['catch_pct']:>6.2f}% "
              f"{r['bets']:>7} {r['bets_per_vt']:>7.2f}")
        print()


if __name__ == "__main__":
    main()
