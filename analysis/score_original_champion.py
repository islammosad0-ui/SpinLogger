#!/usr/bin/env python3
"""Score the ORIGINAL K=5 dyn_aggr champion config under the strict metric.

Original champion (from initial SLV4Policy.m, before per-account tuning):
  Schedule: t∈[15,29] thr=0.08, [30,49] 0.05, [50,69] 0.04, [70,100] 0.03
  Head:     ACC (the original implementation used p_y_acc_next5)

Compare side-by-side with ANY_VT head on the same schedule (current ship)
and the per-account tuned configs.
"""

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = {
    "Ahmed": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Ahmed/spin_predictions_all_combos.csv",
    "Islam": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Islam/spin_predictions_all_combos.csv",
    "Nick":  ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211319_Nick/spin_predictions_all_combos.csv",
}

CHAMPION_SCHEDULE = [
    {"t_min": 15, "t_max": 29, "thr": 0.08},
    {"t_min": 30, "t_max": 49, "thr": 0.05},
    {"t_min": 50, "t_max": 69, "thr": 0.04},
    {"t_min": 70, "t_max": 100, "thr": 0.03},
]


def thr_at(schedule, t):
    for b in schedule:
        if b["t_min"] <= t <= b["t_max"]:
            return b["thr"]
    return 0.99


def score(df, schedule, head_col, max_bet_spins=25):
    df = df.sort_values(["session_id", "cycle_id", "t"]).reset_index(drop=True)
    n_cycles = df["cycle_id"].nunique()
    caught = bets_total = useful_cycles = 0
    cycles_played = 0
    for cid, g in df.groupby("cycle_id", sort=False):
        g = g.sort_values("t").reset_index(drop=True)
        ts  = g["t"].astype(int).to_numpy()
        ps  = g[head_col].astype(float).to_numpy()
        s2v = g["spins_to_vt"].astype(int).to_numpy()
        bets = 0
        cycle_caught = False
        had_useful = False
        had_fire = False
        for t, p, k in zip(ts, ps, s2v):
            in_window = 15 <= t <= 100
            thr = thr_at(schedule, int(t)) if in_window else 0.99
            if p < thr:
                continue
            had_fire = True
            if 1 <= k <= 5:
                had_useful = True
            if bets >= max_bet_spins:
                continue  # don't bet more, but keep counting fires? we cap bets
            bets += 1
            if k == 1:
                cycle_caught = True
                break
        bets_total += bets
        if cycle_caught:
            caught += 1
        if had_useful:
            useful_cycles += 1
        if had_fire:
            cycles_played += 1
    return {
        "cycles": n_cycles,
        "cycles_played": cycles_played,    # cycles where policy fired at least once
        "caught": caught,                  # strict metric (fire at spins_to_vt==1)
        "useful_cycles": useful_cycles,    # cycles where ≥1 fire was within K=5 of VT
        "catch_pct": 100 * caught / n_cycles,
        "useful_pct": 100 * useful_cycles / n_cycles,
        "bets": bets_total,
        "bets_per_vt": bets_total / caught if caught else float("nan"),
    }


def main():
    rows = []
    for acct, csv_path in RUNS.items():
        df = pd.read_csv(csv_path)
        for head_label, head_col in [("ACC",    "p_y_acc_next5"),
                                     ("ANY_VT", "p_y_any_next5")]:
            r = score(df, CHAMPION_SCHEDULE, head_col)
            r["account"] = acct
            r["head"] = head_label
            rows.append(r)

    print(f"\n{'='*100}")
    print("ORIGINAL K=5 dyn_aggr CHAMPION — schedule: 0.08 / 0.05 / 0.04 / 0.03 across t-bands")
    print("Strict metric: catch = fire at spins_to_vt==1; useful = fire within K=5 of VT")
    print(f"{'='*100}\n")

    print(f"{'account':<8} {'head':<8} {'cycles':>6} {'played':>6} {'CAUGHT':>7} {'catch%':>7} {'useful%':>8} {'bets':>6} {'B/VT':>7}")
    print("-" * 80)
    for r in rows:
        print(f"{r['account']:<8} {r['head']:<8} "
              f"{r['cycles']:>6} {r['cycles_played']:>6} "
              f"{r['caught']:>7} {r['catch_pct']:>6.2f}% "
              f"{r['useful_pct']:>7.2f}% "
              f"{r['bets']:>6} {r['bets_per_vt']:>7.2f}")

    print(f"\n{'='*100}")
    print("Notes")
    print(f"{'='*100}")
    print("  catch%   = strict simulator metric (panel fires AT spins_to_vt==1, next spin = VT)")
    print("  useful%  = at least one fire within K=5 of VT (matches the K=5 horizon promise)")
    print("  cycles_played = cycles where policy fired at least once (any fire)")
    print("  Bets are capped at 25 per cycle; bets/VT divides total bets by CAUGHT cycles.")


if __name__ == "__main__":
    main()
