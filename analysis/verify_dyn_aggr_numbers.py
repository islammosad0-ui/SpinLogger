#!/usr/bin/env python3
"""Verify the per-account K5_DYN numbers by independent cross-checks.

Sanity checks:
  1. Distinct cycle_end_symbol values per account (should all be ACC/SPN).
  2. Row count, distinct cycle count, distinct session count.
  3. For each account, hand-compute Ahmed/Islam/Nick numbers under both
     schedules using a simpler vectorized pass (pandas).
  4. Cross-check fires per t-band (fire counts at t=15..29 etc.) match the
     scorer's totals.
"""

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PRED = {
    "Ahmed": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Ahmed/spin_predictions_all_combos.csv",
    "Islam": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Islam/spin_predictions_all_combos.csv",
    "Nick":  ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211319_Nick/spin_predictions_all_combos.csv",
}
CFG_DIR = ROOT / "analysis/configs"
BUNDLE = json.loads((ROOT / "assets/dyn_aggr_schedules.json").read_text(encoding="utf-8"))


def thr_series(t_arr, schedule):
    """Vectorized threshold-by-t lookup."""
    out = pd.Series([0.99] * len(t_arr), index=t_arr.index, dtype=float)
    for b in schedule:
        mask = (t_arr >= b["t_min"]) & (t_arr <= b["t_max"])
        out[mask] = b["thr"]
    return out


def score_df(df, schedule):
    sub = df[(df.t >= 15) & (df.t <= 100)].copy()
    sub["thr"] = thr_series(sub["t"], schedule)
    sub["fire"] = sub["p_y_any_next5"] >= sub["thr"]

    bets = int(sub["fire"].sum())
    cycles_total = df["cycle_id"].nunique()
    cycles_with_fire = sub.loc[sub.fire, "cycle_id"].nunique()
    # Cycles "caught" = cycles where fire happened AND cycle ended with VT.
    cycle_ends = df.groupby("cycle_id")["cycle_end_symbol"].first()
    fired_cids = set(sub.loc[sub.fire, "cycle_id"].unique())
    caught = sum(1 for c in fired_cids if cycle_ends.loc[c] in ("ACC", "SPN"))

    return {
        "cycles_total":     cycles_total,
        "cycles_with_fire": cycles_with_fire,
        "cycles_caught":    caught,
        "bets":             bets,
        "vt_pct":           caught / cycles_total if cycles_total else 0.0,
        "bets_per_vt":      bets / caught if caught else float("nan"),
    }


def main():
    for acct, path in PRED.items():
        df = pd.read_csv(path)
        print(f"\n========== {acct} ==========")
        print(f"file: {path.name}")
        print(f"rows={len(df)}  cycles={df.cycle_id.nunique()}  sessions={df.session_id.nunique()}")
        print(f"cycle_end_symbol distribution:")
        print(df.groupby("cycle_id")["cycle_end_symbol"].first().value_counts().to_string())

        per_acct = json.loads((CFG_DIR / f"dyn_aggr_{acct}.json").read_text(encoding="utf-8"))
        bundle_acct = BUNDLE["accounts"][acct]
        holdout_sid = per_acct["holdout_session"]

        df_hold = df[df.session_id == holdout_sid]
        print(f"holdout: {holdout_sid}  rows={len(df_hold)}  cycles={df_hold.cycle_id.nunique()}")

        for label, sched in [
            ("PER-ACCOUNT", per_acct["schedule"]),
            ("BUNDLED",     bundle_acct["schedule"]),
        ]:
            for scope, sub in [("HOLDOUT", df_hold), ("ALL", df)]:
                r = score_df(sub, sched)
                print(f"  [{label:<11}] {scope:<7} | "
                      f"cycles={r['cycles_total']:>3}  fired={r['cycles_with_fire']:>3}  "
                      f"caught={r['cycles_caught']:>3}  bets={r['bets']:>4}  "
                      f"VT%={r['vt_pct']*100:5.2f}%  Bets/VT={r['bets_per_vt']:6.2f}")

        # Sanity: how many fires happen in each t-band under bundled schedule?
        print("\n  fires-by-t-band (BUNDLED, ALL sessions):")
        sched = bundle_acct["schedule"]
        sub_all = df[(df.t >= 15) & (df.t <= 100)].copy()
        sub_all["thr"] = thr_series(sub_all["t"], sched)
        sub_all["fire"] = sub_all["p_y_any_next5"] >= sub_all["thr"]
        for b in sched:
            mask = (sub_all.t >= b["t_min"]) & (sub_all.t <= b["t_max"])
            n_fire = int(sub_all.loc[mask, "fire"].sum())
            n_total = int(mask.sum())
            print(f"    t∈[{b['t_min']},{b['t_max']}] thr={b['thr']:.2f}  "
                  f"rows={n_total:>5}  fires={n_fire:>4}")


if __name__ == "__main__":
    main()
