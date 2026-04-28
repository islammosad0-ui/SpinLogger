#!/usr/bin/env python3
"""Leak audit — quantify how much the same-row features inflate holdout numbers.

Same-row suspects:
  - cur_cat_id     (current spin's tuple category — known only AFTER spin)
  - reel_dup_last  (does current spin's reels match previous? — same)

Live code sets these to NaN; training pipeline uses actual values. Result: the
training-time holdout numbers may be optimistic vs. live performance.

This script:
  1. Reloads feature CSVs for each account (already computed by hazard_plus).
  2. Retrains ANY_VT K=5 with LOSO, twice:
       (a) full feature set (current shipped)
       (b) WITHOUT cur_cat_id, reel_dup_last (true live-equivalent)
  3. Applies the bundled and per-account schedules to both prediction sets.
  4. Reports the delta — that's the leakage magnitude.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parent.parent
RUNS = {
    "Ahmed": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Ahmed",
    "Islam": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Islam",
    "Nick":  ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211319_Nick",
}
CFG_DIR = ROOT / "analysis/configs"
BUNDLE = json.loads((ROOT / "assets/dyn_aggr_schedules.json").read_text(encoding="utf-8"))

# Same as FEATURE_COLS_BASE in tail_risk_v4_hazard_plus.py — kept in sync.
FEATURE_COLS_BASE = [
    "t",
    "cum_any_triples", "cum_acc_triples", "cum_spn_triples",
    "cum_atk_triples", "cum_shd_triples", "cum_stl_triples",
    "cum_coin_triple", "cum_gs_triple",
    "last_any_triple_gap", "last_real_triple_gap",
    "last_acc_triple_gap", "last_spn_triple_gap",
    "last_atk_triple_gap", "last_shd_triple_gap", "last_stl_triple_gap",
    "last_coin_triple_gap", "last_gs_triple_gap",
    "cooldown_age",
    "density_any_last5", "density_any_last10",
    "cooldown_last5", "cooldown_last10",
    "reel_dup_last", "reel_dup_streak",
    "cur_cat_id", "cat_lag1", "cat_lag2", "cat_lag3",
    "acc_gap_lag1", "acc_gap_lag2", "acc_gap_lag3", "acc_gap_lag4",
    "spn_gap_lag1", "spn_gap_lag2", "spn_gap_lag3", "spn_gap_lag4",
    "vt_gap_lag1",  "vt_gap_lag2",  "vt_gap_lag3",  "vt_gap_lag4",
    "acc_gap_mean3", "acc_gap_std3",
    "spn_gap_mean3", "spn_gap_std3",
    "vt_gap_mean3",  "vt_gap_std3",
]
SAMEROW_FEATURES = ["cur_cat_id", "reel_dup_last"]
PVT_COLS = ["pvt_ACC", "pvt_SPN", "pvt_UNK"]


def feature_cols(df, exclude=None):
    base = [c for c in FEATURE_COLS_BASE if c in df.columns]
    if exclude:
        base = [c for c in base if c not in exclude]
    pvt = [c for c in PVT_COLS if c in df.columns]
    return base + pvt


def train_predict_loso(df, target_col, feat_cols):
    out = pd.Series(np.nan, index=df.index, name=f"p_{target_col}")
    for session in df["session_id"].unique():
        train_idx = df["session_id"].ne(session)
        test_idx  = df["session_id"].eq(session)
        if not train_idx.any() or not test_idx.any():
            continue

        x_tr = df.loc[train_idx, feat_cols].astype(float)
        y_tr = df.loc[train_idx, target_col].astype(int)
        x_te = df.loc[test_idx,  feat_cols].astype(float)

        if y_tr.nunique() < 2:
            continue

        tr_cycles = df.loc[train_idx, "cycle_id"].unique()
        rng = np.random.default_rng(7)
        shuffled = rng.permutation(tr_cycles)
        split = int(len(shuffled) * 0.8)
        fit_cycles = set(shuffled[:split].tolist())
        fit_mask = df.loc[train_idx, "cycle_id"].isin(fit_cycles).to_numpy()
        cal_mask = ~fit_mask

        x_fit, y_fit = x_tr[fit_mask], y_tr.to_numpy()[fit_mask]
        x_cal, y_cal = x_tr[cal_mask], y_tr.to_numpy()[cal_mask]

        model = lgb.LGBMClassifier(
            n_estimators=450, learning_rate=0.04, num_leaves=31,
            min_data_in_leaf=40, feature_fraction=0.85,
            bagging_fraction=0.85, bagging_freq=5,
            verbose=-1, random_state=7,
        )
        model.fit(x_fit, y_fit)

        p_cal = model.predict_proba(x_cal)[:, 1] if y_cal.size else np.array([])
        if p_cal.size and 0 < y_cal.sum() < y_cal.size:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(p_cal, y_cal)
            p_te = iso.predict(model.predict_proba(x_te)[:, 1])
        else:
            p_te = model.predict_proba(x_te)[:, 1]
        out.loc[test_idx] = p_te
    return out


def thr_series(t_arr, schedule):
    out = pd.Series([0.99] * len(t_arr), index=t_arr.index, dtype=float)
    for b in schedule:
        m = (t_arr >= b["t_min"]) & (t_arr <= b["t_max"])
        out[m] = b["thr"]
    return out


def score(df, p_col, schedule):
    sub = df[(df.t >= 15) & (df.t <= 100)].copy()
    sub["thr"] = thr_series(sub["t"], schedule)
    sub["fire"] = sub[p_col] >= sub["thr"]
    bets = int(sub["fire"].sum())
    cycles_total = df["cycle_id"].nunique()
    fired_cids = set(sub.loc[sub.fire, "cycle_id"].unique())
    ends = df.groupby("cycle_id")["cycle_end_symbol"].first()
    caught = sum(1 for c in fired_cids if ends.loc[c] in ("ACC", "SPN"))
    return cycles_total, len(fired_cids), caught, bets, \
           caught / cycles_total if cycles_total else 0.0, \
           bets / caught if caught else float("nan")


def main():
    print(f"\n{'='*100}")
    print("LEAK AUDIT — same-row features (cur_cat_id, reel_dup_last)")
    print(f"{'='*100}")

    for acct, run_dir in RUNS.items():
        print(f"\n--- {acct} ---")
        feat_csv = run_dir / "spin_features_v4.csv"
        df = pd.read_csv(feat_csv)
        print(f"rows={len(df)}  cycles={df.cycle_id.nunique()}  sessions={df.session_id.nunique()}")

        # Reproduce pvt one-hot if not already there
        if "pvt_ACC" not in df.columns:
            for v in ("ACC", "SPN", "UNK"):
                df[f"pvt_{v}"] = (df["prev_vt_type"].fillna("UNK") == v).astype(int)

        per_acct = json.loads((CFG_DIR / f"dyn_aggr_{acct}.json").read_text())
        bundle_acct = BUNDLE["accounts"][acct]
        holdout_sid = per_acct["holdout_session"]

        # (a) FULL features (matches shipped predictions)
        feats_full = feature_cols(df)
        print(f"training FULL ({len(feats_full)} features)...", flush=True)
        df["p_full"] = train_predict_loso(df, "y_any_next5", feats_full)

        # (b) NO same-row features
        feats_clean = feature_cols(df, exclude=SAMEROW_FEATURES)
        print(f"training NO-SAMEROW ({len(feats_clean)} features)...", flush=True)
        df["p_clean"] = train_predict_loso(df, "y_any_next5", feats_clean)

        df_hold = df[df.session_id == holdout_sid]

        for label, sched in [("BUNDLED", bundle_acct["schedule"]),
                             ("PER-ACCOUNT", per_acct["schedule"])]:
            for scope, sub in [("HOLDOUT", df_hold), ("ALL", df)]:
                tot_f, fired_f, caught_f, bets_f, vt_f, bvt_f = score(sub, "p_full", sched)
                tot_c, fired_c, caught_c, bets_c, vt_c, bvt_c = score(sub, "p_clean", sched)
                print(f"  [{label:<11}] {scope:<7} | "
                      f"FULL caught={caught_f:>3} bets={bets_f:>4} VT%={vt_f*100:5.2f}% B/VT={bvt_f:5.2f} | "
                      f"CLEAN caught={caught_c:>3} bets={bets_c:>4} VT%={vt_c*100:5.2f}% B/VT={bvt_c:5.2f} | "
                      f"Δcatch={(vt_f-vt_c)*100:+5.2f}pp")


if __name__ == "__main__":
    main()
