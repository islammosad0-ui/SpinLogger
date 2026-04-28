#!/usr/bin/env python3
"""Strict-metric sweep across multiple candidate schedules.

The simulator's "catch" rule is: a cycle is caught iff at least one fire lands
on the spin where spins_to_vt==1 (the spin directly before the VT). Each fire
is one bet. Bets/VT = total bets / cycles caught.

Sweeps several candidate schedules per account so we can see which actually
work under the right metric:
  1. Flat thresholds (no t-banding)
  2. Pooled dyn_aggr (decreasing thr as t grows — fire more aggressively late)
  3. Current "bundled" (one band in [15,29] only)
  4. Current "tuned" (per-account from earlier LOSO tuning)
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
BUNDLE = json.loads((ROOT / "assets/dyn_aggr_schedules.json").read_text(encoding="utf-8"))


def thr_at(schedule, t):
    for b in schedule:
        if b["t_min"] <= t <= b["t_max"]:
            return b["thr"]
    return 0.99


def flat(thr):
    return [{"t_min": 15, "t_max": 100, "thr": thr}]


def banded(thrs):
    bands = [(15, 29), (30, 49), (50, 69), (70, 100)]
    return [{"t_min": lo, "t_max": hi, "thr": t} for (lo, hi), t in zip(bands, thrs)]


def score_strict(df, schedule, head_col="p_y_any_next5", max_bet_spins=25):
    """Returns dict with cycles, caught, bets, catch%, B/VT."""
    df = df.sort_values(["session_id", "cycle_id", "t"]).reset_index(drop=True)
    n_cycles = df["cycle_id"].nunique()
    caught = bets_total = 0
    for cid, g in df.groupby("cycle_id", sort=False):
        g = g.sort_values("t").reset_index(drop=True)
        ts  = g["t"].astype(int).to_numpy()
        ps  = g[head_col].astype(float).to_numpy()
        s2v = g["spins_to_vt"].astype(int).to_numpy()
        bets = 0; cycle_caught = False
        for t, p, k in zip(ts, ps, s2v):
            in_window = 15 <= t <= 100
            thr = thr_at(schedule, int(t)) if in_window else 0.99
            if p < thr:
                continue
            if bets >= max_bet_spins:
                break
            bets += 1
            if k == 1:
                cycle_caught = True
                break
        bets_total += bets
        if cycle_caught:
            caught += 1
    return {
        "cycles": n_cycles,
        "caught": caught,
        "catch_pct": 100 * caught / n_cycles,
        "bets": bets_total,
        "bets_per_vt": bets_total / caught if caught else float("nan"),
    }


CANDIDATES_PER_ACCT = lambda acct: [
    ("flat-0.05",          flat(0.05)),
    ("flat-0.08",          flat(0.08)),
    ("flat-0.10",          flat(0.10)),
    ("flat-0.15",          flat(0.15)),
    ("pooled-dyn",         banded([0.08, 0.05, 0.04, 0.03])),
    ("dyn-aggr-up",        banded([0.10, 0.07, 0.05, 0.03])),  # gradient towards aggressive late
    ("currently-bundled",  BUNDLE["accounts"][acct]["schedules"]["bundled"]),
    ("currently-tuned",    BUNDLE["accounts"][acct]["schedules"]["tuned"]),
]


def main():
    rows = []
    for acct, csv_path in RUNS.items():
        df = pd.read_csv(csv_path)
        for label, sched in CANDIDATES_PER_ACCT(acct):
            r = score_strict(df, sched)
            r["account"] = acct
            r["schedule_label"] = label
            r["schedule"] = sched
            rows.append(r)

    print(f"\n{'='*100}")
    print("STRICT-METRIC sweep (catch = fire at spins_to_vt==1; bets capped at 25/cycle)")
    print(f"{'='*100}\n")
    print(f"{'account':<8} {'schedule':<22} {'cycles':>6} {'caught':>6} {'catch%':>7} {'bets':>6} {'B/VT':>7}")
    print("-" * 70)
    for r in rows:
        print(f"{r['account']:<8} {r['schedule_label']:<22} "
              f"{r['cycles']:>6} {r['caught']:>6} {r['catch_pct']:>6.2f}% "
              f"{r['bets']:>6} {r['bets_per_vt']:>7.2f}")

    # Pareto frontier per account: maximize catch% AT each B/VT level
    print(f"\n{'='*100}")
    print("Per-account: best catch% per B/VT bucket")
    print(f"{'='*100}\n")
    for acct in RUNS:
        sub = [r for r in rows if r["account"] == acct]
        sub.sort(key=lambda r: r["catch_pct"], reverse=True)
        best = sub[0]
        print(f"  {acct:<6} highest-catch  : {best['schedule_label']:<22} "
              f"catch={best['catch_pct']:>5.2f}%  B/VT={best['bets_per_vt']:>6.2f}")
        sub.sort(key=lambda r: (r["bets_per_vt"] if r["caught"] else 1e9))
        cheap = sub[0]
        print(f"  {acct:<6} cheapest (B/VT): {cheap['schedule_label']:<22} "
              f"catch={cheap['catch_pct']:>5.2f}%  B/VT={cheap['bets_per_vt']:>6.2f}")
        print()


if __name__ == "__main__":
    main()
