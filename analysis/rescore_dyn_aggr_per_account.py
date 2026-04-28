#!/usr/bin/env python3
"""Rescore K5_DYN per-account using per-account configs vs bundled schedules.

For each account:
  - Load `spin_predictions_all_combos.csv` (held-out CV predictions, per-cycle).
  - Apply the per-account schedule from analysis/configs/dyn_aggr_<acct>.json.
  - Apply the bundled schedule from assets/dyn_aggr_schedules.json.
  - Report: cycles, VT_caught, VT%, total bets, Bets/VT
            on (a) holdout session only, (b) all sessions for the account.
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRED_DIRS = {
    "Ahmed": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Ahmed",
    "Islam": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Islam",
    "Nick":  ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211319_Nick",
}
CFG_DIR = ROOT / "analysis/configs"
BUNDLE = ROOT / "assets/dyn_aggr_schedules.json"


def thr_at(schedule, t):
    for b in schedule:
        if b["t_min"] <= t <= b["t_max"]:
            return b["thr"]
    return 0.99


def score(rows, schedule, head_col="p_y_any_next5", t_window=(15, 100)):
    """For each cycle, fire on rows where t in window AND p >= thr(t).
    A cycle is 'caught' if at least one fire occurred AND it ended with a VT.
    Bets = total fires.
    """
    cycles = {}
    for r in rows:
        cid = r["cycle_id"]
        cycles.setdefault(cid, []).append(r)

    total_cycles = 0
    cycles_with_fire = 0
    cycles_caught = 0
    total_bets = 0

    for cid, cycle_rows in cycles.items():
        total_cycles += 1
        fired = False
        for r in cycle_rows:
            try:
                t = int(r["t"])
                p = float(r[head_col])
            except (ValueError, KeyError):
                continue
            if t < t_window[0] or t > t_window[1]:
                continue
            if p >= thr_at(schedule, t):
                fired = True
                total_bets += 1
        if fired:
            cycles_with_fire += 1
            # Cycle ends with a VT by definition (cycle_end_symbol non-empty
            # for completed cycles). Conditional catch = 1.0.
            end_sym = (cycle_rows[-1].get("cycle_end_symbol") or "").strip()
            if end_sym in ("ACC", "SPN"):
                cycles_caught += 1

    return {
        "cycles": total_cycles,
        "cycles_fired": cycles_with_fire,
        "cycles_caught": cycles_caught,
        "fires_total": total_bets,
        "vt_pct_of_all":   cycles_caught / total_cycles  if total_cycles else 0.0,
        "vt_pct_of_fired": cycles_caught / cycles_with_fire if cycles_with_fire else 0.0,
        "bets_per_vt":     total_bets / cycles_caught if cycles_caught else float("nan"),
    }


def load_csv(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))

    print(f"{'='*100}")
    print("Per-account K5_DYN re-score — head = ANY_VT, K = 5, p_y_any_next5")
    print(f"{'='*100}\n")

    for acct, pdir in PRED_DIRS.items():
        cfg_path = CFG_DIR / f"dyn_aggr_{acct}.json"
        per_acct = json.loads(cfg_path.read_text(encoding="utf-8"))
        bundle_acct = bundle["accounts"][acct]

        rows = load_csv(pdir / "spin_predictions_all_combos.csv")
        holdout_sid = per_acct["holdout_session"]
        holdout_rows = [r for r in rows if r.get("session_id") == holdout_sid]

        print(f"--- {acct} -----------------------------------------------------------")
        print(f"  predictions: {pdir.name}  ({len(rows)} rows)")
        print(f"  holdout session: {holdout_sid}  ({len(holdout_rows)} rows)")
        print(f"  per-account schedule:  {per_acct['schedule']}")
        print(f"  bundled    schedule:   {bundle_acct['schedule']}")
        print()

        for label, sched in [
            ("PER-ACCOUNT cfg", per_acct["schedule"]),
            ("BUNDLED    cfg", bundle_acct["schedule"]),
        ]:
            for scope_name, scope_rows in [("HOLDOUT", holdout_rows), ("ALL", rows)]:
                if not scope_rows:
                    continue
                r = score(scope_rows, sched)
                print(f"  [{label}] {scope_name:<7} | "
                      f"cycles={r['cycles']:>3}  fired={r['cycles_fired']:>3}  "
                      f"caught={r['cycles_caught']:>3}  bets={r['fires_total']:>4}  "
                      f"VT%={r['vt_pct_of_all']*100:5.2f}%  "
                      f"VT%|fired={r['vt_pct_of_fired']*100:5.2f}%  "
                      f"Bets/VT={r['bets_per_vt']:6.2f}")
            print()


if __name__ == "__main__":
    main()
