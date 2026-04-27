"""v4 dynamic hazard predictor: all upgrades on v3.

Upgrades vs v3:
    1. Horizon sweep K in {3, 5, 10}.
    2. Target-specific heads: ANY_VT, ACC_only, SPN_only.
       For ACC_only we predict `y = ACC triple hits in next K spins`.
       Same for SPN_only.
    3. Richer in-cycle features:
        - spins_since specific triples (attack / shield / steal / acc / spn) within cycle
        - tuple-category flags on the current spin (triple_goldsack, triple_coin,
          tuple_has_shield, etc.)
        - cooldown_age — spins since any cooldown event in cycle
        - reel_dup_last, reel_dup_streak
        - lagged tuple categories (t-1, t-2, t-3)
    4. Isotonic calibration per session fold. Policy layer has both a
       threshold sweep and a simple EV/breakeven table (bets per target
       hit = breakeven payoff ratio).

Outputs (per (head, horizon) combo):
    combo_sweep_{head}_K{K}.csv
    spin_predictions_{head}_K{K}.csv    (only for a chosen "best" combo)
V4_REPORT.md                           (Pareto table across all combos)
feature_importance_{head}_K{K}.csv

Evaluation: per-session holdout. No cycle predicts itself.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from acc_spn_hotzone_scorer import add_features, load_data


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "analysis" / "output_tail_risk_v4_hazard_plus"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_HEADS = ("ANY_VT", "ACC", "SPN")
HORIZONS = (3, 5, 10)
THRESHOLDS = (0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30, 0.40)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-bet-spins", type=int, default=25)
    parser.add_argument("--best-head", default="ACC")
    parser.add_argument("--best-horizon", type=int, default=5)
    parser.add_argument("--best-threshold", type=float, default=0.15)
    parser.add_argument("--render-trace", action="store_true",
                        help="If set, also render the readable trace for the best combo.")
    parser.add_argument("--account", default=None,
                        help="If set, restrict training+evaluation to this account only "
                             "(per-session LOO within the account).")
    return parser.parse_args()


# --------------------------------------------------------------------------- #
# Feature engineering

def _nan_pad(values: list[float], n: int) -> list[float]:
    padded = values[-n:]
    while len(padded) < n:
        padded.insert(0, np.nan)
    return padded


def _safe_mean(values: list[float]) -> float:
    arr = np.array([v for v in values if pd.notna(v)], dtype=float)
    return float(arr.mean()) if arr.size else np.nan


def _safe_std(values: list[float]) -> float:
    arr = np.array([v for v in values if pd.notna(v)], dtype=float)
    return float(arr.std(ddof=0)) if arr.size >= 2 else np.nan


def _categorize_tuple(r1: str, r2: str, r3: str) -> str:
    # Simple category encoding of a reel tuple.
    r1, r2, r3 = r1 or "", r2 or "", r3 or ""
    if r1 == r2 == r3:
        return f"TRIPLE_{r1.upper()}"
    pair = None
    if r1 == r2:
        pair = r1
    elif r2 == r3:
        pair = r2
    elif r1 == r3:
        pair = r1
    if pair:
        return f"PAIR_{pair.upper()}"
    return "MIXED"


TUPLE_CATS = [
    "TRIPLE_ACCUMULATION", "TRIPLE_SPINS", "TRIPLE_ATTACK", "TRIPLE_SHIELD", "TRIPLE_STEAL",
    "TRIPLE_COIN", "TRIPLE_GOLDSACK",
    "PAIR_ACCUMULATION", "PAIR_SPINS", "PAIR_ATTACK", "PAIR_SHIELD", "PAIR_STEAL",
    "PAIR_COIN", "PAIR_GOLDSACK",
    "MIXED", "OTHER",
]
TUPLE_CAT_IDX = {c: i for i, c in enumerate(TUPLE_CATS)}


def _cat_idx(cat: str) -> int:
    return TUPLE_CAT_IDX.get(cat, TUPLE_CAT_IDX["OTHER"])


def build_spin_frame(max_horizon: int) -> pd.DataFrame:
    df = add_features(load_data()).copy()
    df = df.sort_values(["account", "session_id", "seq"]).reset_index(drop=True)

    rows: list[dict] = []
    cycle_id = 0

    for (account, session_id), sdf in df.groupby(["account", "session_id"], sort=False):
        sdf = sdf.sort_values("seq").reset_index(drop=True)
        seqs = sdf["seq"].to_numpy()

        r1_arr = sdf["reel_1"].fillna("").astype(str).to_numpy()
        r2_arr = sdf["reel_2"].fillna("").astype(str).to_numpy()
        r3_arr = sdf["reel_3"].fillna("").astype(str).to_numpy()

        is_acc = sdf["is_acc"].fillna(False).to_numpy(dtype=bool)
        is_spn = sdf["is_spn"].fillna(False).to_numpy(dtype=bool)
        is_vt = sdf["is_vt"].fillna(False).to_numpy(dtype=bool)
        is_triple = sdf["is_triple"].fillna(False).to_numpy(dtype=bool)
        event_label = sdf["event_label"].fillna("").astype(str).to_numpy()
        prev_vt_type_arr = sdf["prev_vt_type"].fillna("").astype(str).to_numpy()

        is_atk_evt = event_label == "T_attack"
        is_shd_evt = event_label == "T_shield"
        is_stl_evt = event_label == "T_steal"

        # Session gap streams for lag features at cycle start
        acc_events: list[tuple[int, float]] = []
        spn_events: list[tuple[int, float]] = []
        vt_events: list[tuple[int, float]] = []
        last_acc = last_spn = last_vt = None
        for i, s in enumerate(seqs):
            if is_acc[i]:
                g = (s - last_acc) if last_acc is not None else np.nan
                acc_events.append((int(s), float(g) if pd.notna(g) else np.nan))
                last_acc = s
            if is_spn[i]:
                g = (s - last_spn) if last_spn is not None else np.nan
                spn_events.append((int(s), float(g) if pd.notna(g) else np.nan))
                last_spn = s
            if is_vt[i]:
                g = (s - last_vt) if last_vt is not None else np.nan
                vt_events.append((int(s), float(g) if pd.notna(g) else np.nan))
                last_vt = s

        # Pre-compute tuple categories for the whole session
        tuple_cats = [_categorize_tuple(r1_arr[i], r2_arr[i], r3_arr[i]) for i in range(len(seqs))]
        tuple_cat_ids = [_cat_idx(c) for c in tuple_cats]

        vt_pos = np.where(is_vt)[0].tolist()

        for ci in range(1, len(vt_pos)):
            cycle_start_idx = vt_pos[ci - 1] + 1
            cycle_end_idx = vt_pos[ci]
            if cycle_end_idx <= cycle_start_idx:
                continue

            cycle_id += 1
            cycle_start_seq = int(seqs[cycle_start_idx])
            cycle_end_seq = int(seqs[cycle_end_idx])
            prev_vt_type = str(prev_vt_type_arr[cycle_start_idx])
            end_symbol = "ACC" if is_acc[cycle_end_idx] else ("SPN" if is_spn[cycle_end_idx] else "OTHER")

            acc_gaps_before = [g for s, g in acc_events if s < cycle_start_seq and pd.notna(g)]
            spn_gaps_before = [g for s, g in spn_events if s < cycle_start_seq and pd.notna(g)]
            vt_gaps_before = [g for s, g in vt_events if s < cycle_start_seq and pd.notna(g)]

            acc_lag = _nan_pad(acc_gaps_before, 4)
            spn_lag = _nan_pad(spn_gaps_before, 4)
            vt_lag = _nan_pad(vt_gaps_before, 4)

            carry = {
                "acc_gap_lag1": acc_lag[-1], "acc_gap_lag2": acc_lag[-2],
                "acc_gap_lag3": acc_lag[-3], "acc_gap_lag4": acc_lag[-4],
                "spn_gap_lag1": spn_lag[-1], "spn_gap_lag2": spn_lag[-2],
                "spn_gap_lag3": spn_lag[-3], "spn_gap_lag4": spn_lag[-4],
                "vt_gap_lag1": vt_lag[-1], "vt_gap_lag2": vt_lag[-2],
                "vt_gap_lag3": vt_lag[-3], "vt_gap_lag4": vt_lag[-4],
                "acc_gap_mean3": _safe_mean(acc_lag[-3:]),
                "acc_gap_std3": _safe_std(acc_lag[-3:]),
                "spn_gap_mean3": _safe_mean(spn_lag[-3:]),
                "spn_gap_std3": _safe_std(spn_lag[-3:]),
                "vt_gap_mean3": _safe_mean(vt_lag[-3:]),
                "vt_gap_std3": _safe_std(vt_lag[-3:]),
            }

            # cumulative state + last-seen indices for specific triple types
            cum_any = cum_acc = cum_spn = cum_atk = cum_shd = cum_stl = 0
            cum_coin_triple = cum_gs_triple = 0
            last_any_idx = last_real_idx = last_acc_idx = last_spn_idx = None
            last_atk_idx = last_shd_idx = last_stl_idx = None
            last_coin_triple_idx = last_gs_triple_idx = None
            last_cooldown_idx = None
            last_tuple_cat_ids: list[int] = []  # running history of cats within cycle
            dup_streak = 0
            prev_tuple_tuple = None

            for i in range(cycle_start_idx, cycle_end_idx):
                t = i - cycle_start_idx
                spins_to_vt = cycle_end_idx - i

                # Targets for multiple horizons
                targets = {}
                for K in (3, 5, 10):
                    targets[f"y_any_next{K}"] = int(1 <= spins_to_vt <= K)
                    # ACC/SPN hit means the cycle ends at target within K spins AND this is end-K
                    # Equivalent: cycle_end_idx - i <= K AND end_symbol == ACC/SPN
                    targets[f"y_acc_next{K}"] = int(1 <= spins_to_vt <= K and end_symbol == "ACC")
                    targets[f"y_spn_next{K}"] = int(1 <= spins_to_vt <= K and end_symbol == "SPN")

                # In-cycle "time since" features
                def _since(idx):
                    return (i - idx) if idx is not None else np.nan

                last_any_gap = _since(last_any_idx)
                last_real_gap = _since(last_real_idx)
                last_acc_gap = _since(last_acc_idx)
                last_spn_gap = _since(last_spn_idx)
                last_atk_gap = _since(last_atk_idx)
                last_shd_gap = _since(last_shd_idx)
                last_stl_gap = _since(last_stl_idx)
                last_coin_triple_gap = _since(last_coin_triple_idx)
                last_gs_triple_gap = _since(last_gs_triple_idx)
                cooldown_age = _since(last_cooldown_idx)

                # Trailing densities
                def trailing(window: int) -> tuple[int, int]:
                    lo = max(cycle_start_idx, i - window)
                    if lo >= i:
                        return 0, 0
                    w_is_triple = is_triple[lo:i]
                    w_is_cooldown = is_atk_evt[lo:i] | is_shd_evt[lo:i] | is_stl_evt[lo:i]
                    return int(w_is_triple.sum()), int(w_is_cooldown.sum())

                d5_trip, d5_cool = trailing(5)
                d10_trip, d10_cool = trailing(10)

                # Current spin tuple-category one-hot
                cur_cat = tuple_cats[i]
                cur_cat_id = tuple_cat_ids[i]

                # Lag tuple categories (t-1, t-2, t-3) within cycle
                def lag_cat_id(lag: int) -> int:
                    if len(last_tuple_cat_ids) >= lag:
                        return last_tuple_cat_ids[-lag]
                    return -1  # unknown

                cat_lag1 = lag_cat_id(1)
                cat_lag2 = lag_cat_id(2)
                cat_lag3 = lag_cat_id(3)

                # Reel-dup flags
                this_tuple = (r1_arr[i], r2_arr[i], r3_arr[i])
                reel_dup_last = int(prev_tuple_tuple is not None and this_tuple == prev_tuple_tuple)
                if reel_dup_last:
                    dup_streak += 1
                else:
                    dup_streak = 0

                row = {
                    "cycle_id": cycle_id,
                    "account": account,
                    "session_id": session_id,
                    "cycle_start_seq": cycle_start_seq,
                    "cycle_end_seq": cycle_end_seq,
                    "cycle_end_symbol": end_symbol,
                    "seq": int(seqs[i]),
                    "t": t,
                    "spins_to_vt": spins_to_vt,
                    "prev_vt_type": prev_vt_type,
                    # in-cycle cumulative counts
                    "cum_any_triples": cum_any,
                    "cum_acc_triples": cum_acc,
                    "cum_spn_triples": cum_spn,
                    "cum_atk_triples": cum_atk,
                    "cum_shd_triples": cum_shd,
                    "cum_stl_triples": cum_stl,
                    "cum_coin_triple": cum_coin_triple,
                    "cum_gs_triple": cum_gs_triple,
                    # since features
                    "last_any_triple_gap": last_any_gap,
                    "last_real_triple_gap": last_real_gap,
                    "last_acc_triple_gap": last_acc_gap,
                    "last_spn_triple_gap": last_spn_gap,
                    "last_atk_triple_gap": last_atk_gap,
                    "last_shd_triple_gap": last_shd_gap,
                    "last_stl_triple_gap": last_stl_gap,
                    "last_coin_triple_gap": last_coin_triple_gap,
                    "last_gs_triple_gap": last_gs_triple_gap,
                    "cooldown_age": cooldown_age,
                    # trailing density
                    "density_any_last5": d5_trip,
                    "density_any_last10": d10_trip,
                    "cooldown_last5": d5_cool,
                    "cooldown_last10": d10_cool,
                    # reel-dup
                    "reel_dup_last": reel_dup_last,
                    "reel_dup_streak": dup_streak,
                    # current / lag tuple category ids
                    "cur_cat_id": cur_cat_id,
                    "cat_lag1": cat_lag1,
                    "cat_lag2": cat_lag2,
                    "cat_lag3": cat_lag3,
                    # targets
                    **targets,
                    **carry,
                }
                rows.append(row)

                # Update state AFTER this row (features reflect pre-spin state)
                last_tuple_cat_ids.append(cur_cat_id)
                prev_tuple_tuple = this_tuple
                if is_atk_evt[i] or is_shd_evt[i] or is_stl_evt[i]:
                    last_cooldown_idx = i
                if is_triple[i]:
                    cum_any += 1
                    last_any_idx = i
                    last_real_idx = i
                    if is_acc[i]:
                        cum_acc += 1; last_acc_idx = i
                    elif is_spn[i]:
                        cum_spn += 1; last_spn_idx = i
                    elif is_atk_evt[i]:
                        cum_atk += 1; last_atk_idx = i
                    elif is_shd_evt[i]:
                        cum_shd += 1; last_shd_idx = i
                    elif is_stl_evt[i]:
                        cum_stl += 1; last_stl_idx = i
                # Coin / goldSack triples are cosmetic triples (is_triple==False typically
                # since is_triple means real rewards in this codebase). Use reel-match directly.
                if cur_cat == "TRIPLE_COIN":
                    cum_coin_triple += 1
                    last_coin_triple_idx = i
                elif cur_cat == "TRIPLE_GOLDSACK":
                    cum_gs_triple += 1
                    last_gs_triple_idx = i

    frame = pd.DataFrame(rows)
    if not frame.empty:
        dummies = pd.get_dummies(frame["prev_vt_type"].fillna("UNK"), prefix="pvt", dummy_na=False)
        frame = pd.concat([frame, dummies], axis=1)
    return frame


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
    "vt_gap_lag1", "vt_gap_lag2", "vt_gap_lag3", "vt_gap_lag4",
    "acc_gap_mean3", "acc_gap_std3",
    "spn_gap_mean3", "spn_gap_std3",
    "vt_gap_mean3", "vt_gap_std3",
]


def feature_cols(frame: pd.DataFrame) -> list[str]:
    pvt_cols = [c for c in frame.columns if c.startswith("pvt_")]
    return FEATURE_COLS_BASE + pvt_cols


# --------------------------------------------------------------------------- #
# Training + per-session holdout + isotonic calibration

def train_predict_calibrated(
    frame: pd.DataFrame,
    target_col: str,
) -> tuple[pd.Series, pd.DataFrame]:
    cols = feature_cols(frame)
    out = pd.Series(np.nan, index=frame.index, name=f"p_{target_col}")
    importances = defaultdict(list)

    for session in frame["session_id"].unique():
        train_idx = frame["session_id"].ne(session)
        test_idx = frame["session_id"].eq(session)
        if not train_idx.any() or not test_idx.any():
            continue

        x_tr = frame.loc[train_idx, cols].astype(float)
        y_tr = frame.loc[train_idx, target_col].astype(int)
        x_te = frame.loc[test_idx, cols].astype(float)
        y_te = frame.loc[test_idx, target_col].astype(int)

        if y_tr.nunique() < 2:
            continue

        # Split training for calibration: 80/20 on cycle id within training
        tr_cycles = frame.loc[train_idx, "cycle_id"].unique()
        rng = np.random.default_rng(7)
        shuffled = rng.permutation(tr_cycles)
        split = int(len(shuffled) * 0.8)
        fit_cycles = set(shuffled[:split].tolist())
        cal_cycles = set(shuffled[split:].tolist())
        fit_mask = frame.loc[train_idx, "cycle_id"].isin(fit_cycles).to_numpy()
        cal_mask = ~fit_mask

        x_fit = x_tr[fit_mask]; y_fit = y_tr.to_numpy()[fit_mask]
        x_cal = x_tr[cal_mask]; y_cal = y_tr.to_numpy()[cal_mask]

        model = lgb.LGBMClassifier(
            n_estimators=450,
            learning_rate=0.04,
            num_leaves=31,
            min_data_in_leaf=40,
            feature_fraction=0.85,
            bagging_fraction=0.85,
            bagging_freq=5,
            verbose=-1,
            random_state=7,
        )
        model.fit(x_fit, y_fit)

        # Calibrate on held-out slice
        p_cal = model.predict_proba(x_cal)[:, 1] if y_cal.size else np.array([])
        if p_cal.size and y_cal.sum() > 0 and y_cal.sum() < y_cal.size:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(p_cal, y_cal)
            p_te_raw = model.predict_proba(x_te)[:, 1]
            p_te = iso.predict(p_te_raw)
        else:
            p_te = model.predict_proba(x_te)[:, 1]

        out.loc[test_idx] = p_te

        for f, imp in zip(cols, model.feature_importances_):
            importances[f].append(float(imp))

    imp_df = pd.DataFrame(
        [{"feature": f, "mean_importance": float(np.mean(v))} for f, v in importances.items()]
    ).sort_values("mean_importance", ascending=False).reset_index(drop=True)
    return out, imp_df


# --------------------------------------------------------------------------- #
# Policy simulation

def simulate_threshold(
    frame: pd.DataFrame,
    proba_col: str,
    threshold: float,
    target_head: str,       # "ANY_VT" / "ACC" / "SPN"
    max_bet_spins: int,
) -> dict:
    df = frame.dropna(subset=[proba_col]).copy()
    df["would_bet"] = df[proba_col].ge(threshold)

    total_cycles = int(df["cycle_id"].nunique())
    vt_hits = target_hits = cycles_played = bets_total = 0

    for cid, cyc in df.groupby("cycle_id", sort=False):
        cyc = cyc.sort_values("t")
        bet_mask = cyc["would_bet"].to_numpy()
        if not bet_mask.any():
            continue
        cycles_played += 1

        bets_taken = 0
        caught = False
        end_symbol = str(cyc.iloc[0]["cycle_end_symbol"])
        for i in range(len(cyc)):
            if not bet_mask[i]:
                continue
            if bets_taken >= max_bet_spins:
                break
            bets_taken += 1
            if int(cyc.iloc[i]["spins_to_vt"]) == 1:
                caught = True
                break
        bets_total += bets_taken
        if caught:
            vt_hits += 1
            # target_hits depends on the head definition
            if target_head == "ANY_VT":
                target_hits += 1
            elif end_symbol == target_head:
                target_hits += 1

    return {
        "threshold": threshold,
        "cycles_total": total_cycles,
        "cycles_played": cycles_played,
        "vt_hits": vt_hits,
        "target_hits": target_hits,
        "vt_catch_total_pct": 100.0 * vt_hits / total_cycles if total_cycles else 0.0,
        "target_catch_total_pct": 100.0 * target_hits / total_cycles if total_cycles else 0.0,
        "bets_total": bets_total,
        "bets_per_vt_hit": bets_total / vt_hits if vt_hits else float("nan"),
        "bets_per_target_hit": bets_total / target_hits if target_hits else float("nan"),
    }


# --------------------------------------------------------------------------- #
# Reporting

def build_sweep_table(
    frame: pd.DataFrame,
    combos: list[tuple[str, int, str]],
    max_bet_spins: int,
) -> pd.DataFrame:
    rows = []
    for head, K, proba_col in combos:
        for thr in THRESHOLDS:
            r = simulate_threshold(frame, proba_col, thr, head, max_bet_spins)
            r.update({"head": head, "horizon": K})
            rows.append(r)
    return pd.DataFrame(rows)


def write_report(run_dir: Path, sweep: pd.DataFrame, all_importances: dict) -> None:
    sweep = sweep.copy()
    lines = [
        "# v4 Hazard-Plus: All Upgrades",
        "",
        "- Heads: `ANY_VT` (any triple), `ACC_only`, `SPN_only`.",
        "- Horizons K in {3, 5, 10}.",
        "- Isotonic calibration per session fold.",
        "- Per-session holdout (each session predicted by models trained on others).",
        "- Richer features: tuple-category flags (current + last 3), cooldown_age,",
        "  last-specific-triple gaps (attack/shield/steal/acc/spn/coin/goldsack),",
        "  reel-dup flags, trailing densities.",
        "",
        "## Combo Summary — Best Threshold per (Head, Horizon) by Bets/VT",
        "",
    ]

    best = sweep.sort_values(["head", "horizon", "bets_per_vt_hit"]).groupby(
        ["head", "horizon"]
    ).first().reset_index()

    lines.append("| Head    | K  | Best Thr | VTh  | Tgt  |  VT %  | Tgt %  | Bets/VT | Bets/Tgt |")
    lines.append("| :------ | -: | -------: | ---: | ---: | -----: | -----: | ------: | -------: |")
    for _, r in best.iterrows():
        lines.append(
            f"| {r['head']:<7} | {int(r['horizon']):>2} | "
            f"{r['threshold']:>8.2f} | {int(r['vt_hits']):>4} | {int(r['target_hits']):>4} | "
            f"{r['vt_catch_total_pct']:>5.2f}% | {r['target_catch_total_pct']:>5.2f}% | "
            f"{r['bets_per_vt_hit']:>7.2f} | {r['bets_per_target_hit']:>8.2f} |"
        )

    for head in TARGET_HEADS:
        for K in HORIZONS:
            sub = sweep[(sweep["head"] == head) & (sweep["horizon"] == K)].copy()
            if sub.empty:
                continue
            lines.append("")
            lines.append(f"## Threshold Sweep — Head={head}, K={K}")
            lines.append("")
            lines.append("| Thr  | Played | VTh  | Tgt  |  VT %  | Tgt %  | Bets  | Bets/VT | Bets/Tgt |")
            lines.append("| ---: | -----: | ---: | ---: | -----: | -----: | ----: | ------: | -------: |")
            for _, r in sub.sort_values("threshold").iterrows():
                lines.append(
                    f"| {r['threshold']:>4.2f} | {int(r['cycles_played']):>6} | "
                    f"{int(r['vt_hits']):>4} | {int(r['target_hits']):>4} | "
                    f"{r['vt_catch_total_pct']:>5.2f}% | {r['target_catch_total_pct']:>5.2f}% | "
                    f"{int(r['bets_total']):>5} | {r['bets_per_vt_hit']:>7.2f} | {r['bets_per_target_hit']:>8.2f} |"
                )

    lines.append("")
    lines.append("## EV / Breakeven Analysis")
    lines.append("")
    lines.append("- `bets_per_target_hit` = break-even payoff multiple. If a target catch pays more")
    lines.append("  than this many normal spins of value, the policy is profitable.")
    lines.append("- Lower is better. Compare to your real-game observations: an ACC triple typically")
    lines.append("  pays 40-100x normal spin value; an SPN triple pays free-spin bonus which can be 30-80x.")
    lines.append("")

    lines.append("## Feature Importance — ACC_only K=5 (top 20)")
    lines.append("")
    key = ("ACC", 5)
    imp_df = all_importances.get(key)
    if imp_df is not None:
        lines.append("| Rank | Feature                      | Importance |")
        lines.append("| ---: | :--------------------------- | ---------: |")
        for i, r in imp_df.head(20).iterrows():
            lines.append(f"| {i + 1:>4} | {r['feature']:<28} | {r['mean_importance']:>10.1f} |")

    lines.append("")
    lines.append("## Reference (honest prior results)")
    lines.append("- v1 KNN LOO:           11.24% VT catch, 40.09 bets/VT hit")
    lines.append("- v2 static GBR:        12.53% VT catch, 34.86 bets/VT hit")
    lines.append("- v3 ANY_VT K=5 @ 0.15: 29.96% VT catch, 37.54 bets/VT hit")

    (run_dir / "V4_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = f"_{args.account}" if args.account else ""
    run_dir = OUT_DIR / f"v4-{stamp}{suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("Building spin frame...")
    frame = build_spin_frame(max_horizon=max(HORIZONS))
    if args.account:
        before = len(frame)
        frame = frame[frame["account"] == args.account].reset_index(drop=True)
        print(f"  filtered to account={args.account}: {before} -> {len(frame)} rows")
        if frame.empty:
            raise SystemExit(f"No rows for account={args.account}")
    frame.to_csv(run_dir / "spin_features_v4.csv", index=False)
    print(f"  rows={len(frame)}, cycles={frame['cycle_id'].nunique()}")

    combos = []
    all_importances: dict = {}
    for K in HORIZONS:
        for head in TARGET_HEADS:
            if head == "ANY_VT":
                target_col = f"y_any_next{K}"
            elif head == "ACC":
                target_col = f"y_acc_next{K}"
            else:
                target_col = f"y_spn_next{K}"
            proba_col = f"p_{target_col}"

            print(f"[{head} K={K}] training + predicting...")
            proba, imp_df = train_predict_calibrated(frame, target_col)
            frame[proba_col] = proba
            imp_df.to_csv(run_dir / f"feature_importance_{head}_K{K}.csv", index=False)
            all_importances[(head, K)] = imp_df
            combos.append((head, K, proba_col))

    # Save spin predictions for the best combo (user's pick)
    best_head = args.best_head if args.best_head in TARGET_HEADS else "ACC"
    best_K = args.best_horizon if args.best_horizon in HORIZONS else 5
    best_target_col = (
        f"y_{'any' if best_head == 'ANY_VT' else best_head.lower()}_next{best_K}"
    )
    best_proba_col = f"p_{best_target_col}"
    frame[
        [
            "cycle_id", "account", "session_id",
            "cycle_start_seq", "cycle_end_seq", "cycle_end_symbol",
            "seq", "t", "spins_to_vt", "prev_vt_type",
            best_proba_col,
        ] + [c for c in frame.columns if c.startswith(("acc_gap_lag", "spn_gap_lag", "vt_gap_lag"))]
    ].rename(columns={best_proba_col: "p_hit"}).to_csv(
        run_dir / f"spin_predictions_{best_head}_K{best_K}.csv", index=False
    )

    # Also dump all 9 combos' probabilities to one wide CSV for horizon-stack research
    proba_cols = [f"p_y_{'any' if h == 'ANY_VT' else h.lower()}_next{K}" for h in TARGET_HEADS for K in HORIZONS]
    proba_cols = [c for c in proba_cols if c in frame.columns]
    frame[
        [
            "cycle_id", "account", "session_id",
            "cycle_start_seq", "cycle_end_seq", "cycle_end_symbol",
            "seq", "t", "spins_to_vt", "prev_vt_type",
        ] + proba_cols
    ].to_csv(run_dir / "spin_predictions_all_combos.csv", index=False)

    print("Running threshold sweep across all combos...")
    sweep = build_sweep_table(frame, combos, args.max_bet_spins)
    sweep.to_csv(run_dir / "combo_sweep_all.csv", index=False)

    write_report(run_dir, sweep, all_importances)
    print(run_dir)


if __name__ == "__main__":
    main()
