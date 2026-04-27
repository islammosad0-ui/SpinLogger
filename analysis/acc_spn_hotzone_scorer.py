import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "analysis" / "output_acc_spn_hotzone"
OUT_DIR.mkdir(parents=True, exist_ok=True)
sns.set_theme(style="whitegrid", font_scale=0.9)

TARGETS = {
    "ACC": {"col": "is_acc", "gap75": 100, "gap90": 142},
    "SPN": {"col": "is_spn", "gap75": 88, "gap90": 128},
}
COOLDOWN_EVENTS = {"T_shield", "T_attack", "T_steal"}


def _classify_gap_bucket(value: float, short_thr: int, long_thr: int) -> str:
    if pd.isna(value):
        return "UNK"
    if value <= short_thr:
        return "S"
    if value >= long_thr:
        return "L"
    return "M"


def load_data() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA_DIR.rglob("spin_history*.csv")):
        try:
            df = pd.read_csv(path, engine="python", on_bad_lines="skip")
        except Exception:
            continue
        if df.empty:
            continue
        df["account"] = path.parent.name
        df["source_name"] = path.name
        df["session_id"] = f"{path.parent.name}|{path.name}"
        df["source_quality"] = df.notna().sum(axis=1)
        frames.append(df)

    raw = pd.concat(frames, ignore_index=True, sort=False)
    raw["seq"] = pd.to_numeric(raw.get("seq"), errors="coerce")
    raw = raw[raw["seq"].notna()].copy()
    raw["seq"] = raw["seq"].astype(int)
    raw = raw.sort_values(
        ["account", "seq", "source_quality", "source_name"],
        ascending=[True, True, False, False],
    )
    df = raw.drop_duplicates(["account", "seq"], keep="first").copy()
    df = df.sort_values(["account", "seq"]).reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df.get("timestamp"), errors="coerce")

    df["is_triple"] = df.get("is_triple", False).astype(str).str.lower().map(
        {"true": True, "false": False}
    ).fillna(df.get("is_triple", False)).astype(bool)
    for col in [
        "bet_level", "bet_multiplier", "r1_idx", "r2_idx", "r3_idx",
        "accum_pct", "accum_delta", "acc_count", "spn_count", "atk_count", "stl_count", "shd_count",
        "sa_spins", "sa_acc", "sa_spn", "sa_atk", "sa_stl", "sa_shd",
        "ss_spins", "ss_acc", "ss_spn", "ss_atk", "ss_stl", "ss_shd",
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["triple_symbol"] = np.where(df["is_triple"], df.get("reel_1"), "none")
    df["is_acc"] = df["is_triple"] & df["triple_symbol"].eq("accumulation")
    df["is_spn"] = df["is_triple"] & df["triple_symbol"].eq("spins")
    df["event_label"] = np.where(
        df["is_acc"], "T_ACC",
        np.where(df["is_spn"], "T_SPN",
                 np.where(df["is_triple"], "T_" + df["triple_symbol"].astype(str), df.get("spin_result", "unknown")))
    )
    return df


def future_hit_within_k(series: pd.Series, k: int) -> pd.Series:
    arr = series.fillna(False).astype(bool).to_numpy()
    out = np.zeros(len(arr), dtype=bool)
    for step in range(1, k + 1):
        shifted = np.zeros(len(arr), dtype=bool)
        if step < len(arr):
            shifted[:-step] = arr[step:]
        out |= shifted
    return pd.Series(out, index=series.index)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    g = out.groupby("account", sort=False)
    out["bet_switched"] = g["bet_level"].diff().fillna(0) != 0
    out["time_delta_s"] = g["timestamp"].diff().dt.total_seconds().fillna(0)
    out["prev_event"] = g["event_label"].shift(1).fillna("START")
    out["is_vt"] = out["is_acc"] | out["is_spn"]

    for key, meta in TARGETS.items():
        gap = np.zeros(len(out), dtype=int)
        for _, idxs in out.groupby("account").groups.items():
            drought = 0
            for pos in idxs:
                gap[pos] = drought
                if out.at[pos, meta["col"]]:
                    drought = 0
                else:
                    drought += 1
        out[f"gap_{key.lower()}"] = gap
        for mod in [20, 50, 100]:
            out[f"gap_{key.lower()}_mod{mod}"] = gap % mod

    vt_mask = out["is_acc"] | out["is_spn"]
    vt_gap_samples: list[int] = []
    for _, idxs in out.groupby("account", sort=False).groups.items():
        positions = np.array(list(idxs), dtype=int)
        vt_positions = positions[vt_mask.iloc[positions].to_numpy()]
        if len(vt_positions) >= 2:
            vt_gap_samples.extend((np.diff(vt_positions) - 1).tolist())

    short_thr = int(np.percentile(vt_gap_samples, 33)) if vt_gap_samples else 28
    long_thr = int(np.percentile(vt_gap_samples, 67)) if vt_gap_samples else 60

    gap_vt = np.zeros(len(out), dtype=int)
    prev_vt_gap1 = np.full(len(out), np.nan, dtype=float)
    prev_vt_gap2 = np.full(len(out), np.nan, dtype=float)
    prev_vt_type = np.full(len(out), "START", dtype=object)
    prev_vt_transition = np.full(len(out), "START", dtype=object)
    prev_vt_gap1_class = np.full(len(out), "UNK", dtype=object)
    prev_vt_gap2_class = np.full(len(out), "UNK", dtype=object)
    prev_vt_gap_pattern = np.full(len(out), "UNK", dtype=object)
    prev_vt_same_type = np.zeros(len(out), dtype=int)

    for _, idxs in out.groupby("account", sort=False).groups.items():
        drought = 0
        last_vt_type = "START"
        last_transition = "START"
        last_same_type = False
        gap1 = np.nan
        gap2 = np.nan

        for pos in idxs:
            gap_vt[pos] = drought
            prev_vt_gap1[pos] = gap1
            prev_vt_gap2[pos] = gap2
            prev_vt_type[pos] = last_vt_type
            prev_vt_transition[pos] = last_transition
            prev_vt_same_type[pos] = int(last_same_type)

            gap1_class = _classify_gap_bucket(gap1, short_thr, long_thr)
            gap2_class = _classify_gap_bucket(gap2, short_thr, long_thr)
            prev_vt_gap1_class[pos] = gap1_class
            prev_vt_gap2_class[pos] = gap2_class
            prev_vt_gap_pattern[pos] = (
                f"{gap2_class}->{gap1_class}"
                if gap1_class != "UNK" and gap2_class != "UNK"
                else "UNK"
            )

            if vt_mask.iat[pos]:
                current_type = "ACC" if out.at[pos, "is_acc"] else "SPN"
                if last_vt_type != "START":
                    gap2 = gap1
                    gap1 = float(drought)
                    last_transition = f"{last_vt_type}->{current_type}"
                    last_same_type = last_vt_type == current_type
                last_vt_type = current_type
                drought = 0
            else:
                drought += 1

    out["gap_vt"] = gap_vt
    for mod in [20, 50, 100]:
        out[f"gap_vt_mod{mod}"] = gap_vt % mod
    out["prev_vt_type"] = prev_vt_type
    out["prev_vt_transition"] = prev_vt_transition
    out["prev_vt_gap1_class"] = prev_vt_gap1_class
    out["prev_vt_gap2_class"] = prev_vt_gap2_class
    out["prev_vt_gap_pattern"] = prev_vt_gap_pattern
    out["prev_vt_gap1"] = prev_vt_gap1
    out["prev_vt_gap2"] = prev_vt_gap2
    out["prev_vt_gap_delta"] = out["prev_vt_gap1"] - out["prev_vt_gap2"]
    out["prev_vt_same_type"] = prev_vt_same_type
    out["prev_vt_cross_type"] = (out["prev_vt_transition"].isin(["ACC->SPN", "SPN->ACC"])).astype(int)

    last_cooldown_event = np.full(len(out), "NONE", dtype=object)
    cooldown_age = np.full(len(out), np.nan, dtype=float)
    cooldown_bucket = np.full(len(out), "NONE", dtype=object)
    cooldown_event_any = np.zeros(len(out), dtype=int)
    for _, idxs in out.groupby("account", sort=False).groups.items():
        active_event = "NONE"
        age = np.nan
        for pos in idxs:
            event = out.at[pos, "event_label"]
            if event in COOLDOWN_EVENTS:
                active_event = event
                age = 0.0
            elif not pd.isna(age):
                age += 1.0
            last_cooldown_event[pos] = active_event
            cooldown_age[pos] = age
            cooldown_event_any[pos] = int(active_event != "NONE")
            if active_event == "NONE" or pd.isna(age):
                cooldown_bucket[pos] = "NONE"
            elif age == 0:
                cooldown_bucket[pos] = "event"
            elif age <= 2:
                cooldown_bucket[pos] = "1_2"
            elif age <= 5:
                cooldown_bucket[pos] = "3_5"
            elif age <= 8:
                cooldown_bucket[pos] = "6_8"
            elif age <= 12:
                cooldown_bucket[pos] = "9_12"
            else:
                cooldown_bucket[pos] = "13p"
    out["last_cooldown_event"] = last_cooldown_event
    out["cooldown_age"] = cooldown_age
    out["cooldown_event_any"] = cooldown_event_any
    out["cooldown_bucket"] = cooldown_bucket

    for lag in [1, 2]:
        for col in ["r1_idx", "r2_idx", "r3_idx", "bet_level", "bet_multiplier", "accum_pct", "accum_delta"]:
            if col in out.columns:
                out[f"{col}_lag{lag}"] = g[col].shift(lag)

    if set(["r1_idx_lag1", "r2_idx_lag1", "r3_idx_lag1"]).issubset(out.columns):
        out["prev_pair_any"] = (
            out["r1_idx_lag1"].eq(out["r2_idx_lag1"]) |
            out["r1_idx_lag1"].eq(out["r3_idx_lag1"]) |
            out["r2_idx_lag1"].eq(out["r3_idx_lag1"])
        )
        out["idx_sum_lag1"] = out[["r1_idx_lag1", "r2_idx_lag1", "r3_idx_lag1"]].sum(axis=1)
        out["idx_spread_lag1"] = out[["r1_idx_lag1", "r2_idx_lag1", "r3_idx_lag1"]].max(axis=1) - out[["r1_idx_lag1", "r2_idx_lag1", "r3_idx_lag1"]].min(axis=1)
    else:
        out["prev_pair_any"] = False
        out["idx_sum_lag1"] = np.nan
        out["idx_spread_lag1"] = np.nan

    rolling_cols = [c for c in ["acc_count", "spn_count", "atk_count", "stl_count", "shd_count", "is_triple", "is_acc", "is_spn", "is_vt"] if c in out.columns]
    for w in [5, 10, 25, 50, 100]:
        shifted = g[rolling_cols].shift(1)
        rolled = shifted.groupby(out["account"]).rolling(w, min_periods=1).sum().reset_index(level=0, drop=True)
        for c in rolling_cols:
            out[f"{c}_sum{w}"] = rolled[c]

    prev_dummies = pd.get_dummies(out["prev_event"], prefix="prev_event")
    vt_type_dummies = pd.get_dummies(prev_vt_type, prefix="prev_vt_type")
    vt_transition_dummies = pd.get_dummies(prev_vt_transition, prefix="prev_vt_transition")
    vt_gap1_class_dummies = pd.get_dummies(prev_vt_gap1_class, prefix="prev_vt_gap1_class")
    vt_gap2_class_dummies = pd.get_dummies(prev_vt_gap2_class, prefix="prev_vt_gap2_class")
    vt_gap_pattern_dummies = pd.get_dummies(prev_vt_gap_pattern, prefix="prev_vt_gap_pattern")
    cooldown_event_dummies = pd.get_dummies(last_cooldown_event, prefix="last_cooldown_event")
    cooldown_bucket_dummies = pd.get_dummies(cooldown_bucket, prefix="cooldown_bucket")
    out = pd.concat(
        [
            out,
            prev_dummies,
            vt_type_dummies,
            vt_transition_dummies,
            vt_gap1_class_dummies,
            vt_gap2_class_dummies,
            vt_gap_pattern_dummies,
            cooldown_event_dummies,
            cooldown_bucket_dummies,
        ],
        axis=1,
    )
    return out


def heuristic_score(df: pd.DataFrame, key: str) -> pd.Series:
    score = pd.Series(0.0, index=df.index)
    if key == "ACC":
        score += (df["gap_acc"] >= 100).astype(float) * 1.0
        score += (df["gap_acc"] >= 142).astype(float) * 1.5
        score += (df["accum_pct"] >= 80).fillna(False).astype(float) * 1.0
        score += df["prev_pair_any"].fillna(False).astype(float) * 0.75
        if "is_triple_sum10" in df.columns:
            score += (df["is_triple_sum10"] >= 1).astype(float) * 0.5
        if "spn_count_sum5" in df.columns:
            score += (df["spn_count_sum5"] >= 3).astype(float) * 0.5
        score += (df["accum_delta"] > 0).fillna(False).astype(float) * 0.25
    else:
        score += (df["gap_spn"] >= 88).astype(float) * 1.0
        score += (df["gap_spn"] >= 128).astype(float) * 1.5
        score += (df["accum_pct"] >= 80).fillna(False).astype(float) * 1.0
        if "acc_count_sum5" in df.columns:
            score += (df["acc_count_sum5"] >= 3).astype(float) * 0.75
        if "is_triple_sum10" in df.columns:
            score += (df["is_triple_sum10"] >= 1).astype(float) * 0.5
        score += (df["accum_delta"] > 0).fillna(False).astype(float) * 0.5
    return score


def gap_signal(df: pd.DataFrame, key: str, level: str) -> pd.Series:
    if key == "ACC":
        thr = 100 if level == "warm" else 142
        return df["gap_acc"] >= thr
    thr = 88 if level == "warm" else 128
    return df["gap_spn"] >= thr


def model_features(df: pd.DataFrame, key: str):
    base_cols = [
        f"gap_{key.lower()}",
        f"gap_{key.lower()}_mod20",
        f"gap_{key.lower()}_mod50",
        f"gap_{key.lower()}_mod100",
        "gap_vt",
        "gap_vt_mod20",
        "gap_vt_mod50",
        "gap_vt_mod100",
        "bet_level", "bet_multiplier", "bet_switched", "time_delta_s",
        "accum_pct", "accum_delta",
        "idx_sum_lag1", "idx_spread_lag1", "prev_pair_any",
        "acc_count_sum5", "spn_count_sum5", "is_triple_sum10",
        "is_acc_sum25", "is_spn_sum25", "is_vt_sum25",
        "is_acc_sum50", "is_spn_sum50", "is_vt_sum50",
        "is_acc_sum100", "is_spn_sum100", "is_vt_sum100",
        "prev_vt_gap1", "prev_vt_gap2", "prev_vt_gap_delta",
        "prev_vt_same_type", "prev_vt_cross_type",
        "cooldown_age", "cooldown_event_any",
        "sa_spins", "sa_acc", "sa_spn", "sa_atk", "sa_stl", "sa_shd",
        "ss_spins", "ss_acc", "ss_spn", "ss_atk", "ss_stl", "ss_shd",
    ]
    prev_cols = [c for c in df.columns if c.startswith("prev_event_")]
    vt_cols = [
        c for c in df.columns
        if c.startswith("prev_vt_type_")
        or c.startswith("prev_vt_transition_")
        or c.startswith("prev_vt_gap1_class_")
        or c.startswith("prev_vt_gap2_class_")
        or c.startswith("prev_vt_gap_pattern_")
        or c.startswith("last_cooldown_event_")
        or c.startswith("cooldown_bucket_")
    ]
    keep = [c for c in base_cols + prev_cols + vt_cols if c in df.columns]
    X = df[keep].copy()
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    X = X.fillna(-999)
    return X, keep


def fit_holdout_scores(df: pd.DataFrame, key: str, target_col: str):
    work = df.copy()
    work["target_next5"] = future_hit_within_k(work[target_col], 5).astype(int)
    X, feature_cols = model_features(work, key)
    sessions = work["session_id"].drop_duplicates().tolist()

    score = pd.Series(index=work.index, dtype=float)
    warm_flag = pd.Series(False, index=work.index)
    hot_flag = pd.Series(False, index=work.index)
    importances = Counter()

    for holdout in sessions:
        train_mask = work["session_id"] != holdout
        test_mask = work["session_id"] == holdout
        y_train = work.loc[train_mask, "target_next5"]
        if train_mask.sum() < 1000 or test_mask.sum() < 100 or y_train.nunique() < 2:
            continue

        model = lgb.LGBMClassifier(
            objective="binary",
            n_estimators=120,
            learning_rate=0.06,
            num_leaves=15,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            class_weight="balanced",
            verbosity=-1,
        )
        model.fit(X.loc[train_mask], y_train)
        train_scores = model.predict_proba(X.loc[train_mask])[:, 1]
        test_scores = model.predict_proba(X.loc[test_mask])[:, 1]
        score.loc[test_mask] = test_scores

        warm_thr = np.quantile(train_scores, 0.80)
        hot_thr = np.quantile(train_scores, 0.95)
        warm_flag.loc[test_mask] = test_scores >= warm_thr
        hot_flag.loc[test_mask] = test_scores >= hot_thr

        fi = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False).head(20)
        importances.update({k: int(v) for k, v in fi.items()})

    return score, warm_flag, hot_flag, importances.most_common(20)


def episode_backtest(df: pd.DataFrame, signal: pd.Series, target_col: str):
    signal = signal.fillna(False).astype(bool)
    total_events = int(df[target_col].sum())
    windows = 0
    windows_hit = 0
    bet_spins = 0
    catches = 0
    session_rows = []

    for session_id, sdf in df.groupby("session_id"):
        idxs = list(sdf.index)
        active = 0
        spins_left = 0
        local_windows = 0
        local_hits = 0
        local_bets = 0
        local_catches = 0

        for pos in idxs:
            if active:
                spins_left -= 1
                local_bets += 1
                if df.at[pos, target_col]:
                    local_hits += 1
                    local_catches += 1
                    active = 0
                    spins_left = 0
                elif spins_left <= 0:
                    active = 0

            if not active and signal.at[pos]:
                # Start a new betting episode for the NEXT 5 spins.
                active = 1
                spins_left = 5
                local_windows += 1

        windows += local_windows
        windows_hit += local_hits
        bet_spins += local_bets
        catches += local_catches
        session_rows.append({
            "session_id": session_id,
            "windows": local_windows,
            "hits": local_hits,
            "bet_spins": local_bets,
        })

    return {
        "windows": windows,
        "windows_hit": windows_hit,
        "window_hit_rate": (windows_hit / windows) if windows else 0.0,
        "bet_spins": bet_spins,
        "spins_per_hit": (bet_spins / catches) if catches else math.inf,
        "caught_events": catches,
        "capture_rate": (catches / total_events) if total_events else 0.0,
        "session_rows": session_rows,
    }


def per_spin_eval(df: pd.DataFrame, signal: pd.Series, target_col: str):
    future5 = future_hit_within_k(df[target_col], 5)
    signal = signal.fillna(False).astype(bool)
    n = int(signal.sum())
    rate = float(future5[signal].mean()) if n else 0.0
    base = float(future5.mean())
    return {
        "alerts": n,
        "alert_rate": n / len(df),
        "next5_rate": rate,
        "baseline_next5": base,
        "lift": (rate / base) if base else 0.0,
    }


def heuristic_flags(df: pd.DataFrame, key: str):
    score = heuristic_score(df, key)
    warm = score >= 2.0
    hot = score >= 3.0
    return score, warm, hot


def build_reports(df: pd.DataFrame):
    report = {
        "overview": {
            "rows": int(len(df)),
            "sessions": int(df["session_id"].nunique()),
            "accounts": df["account"].value_counts().to_dict(),
        },
        "targets": {},
    }

    plot_paths = []

    for key, meta in TARGETS.items():
        target_col = meta["col"]
        score_model, warm_model, hot_model, top_features = fit_holdout_scores(df, key, target_col)
        score_heur, warm_heur, hot_heur = heuristic_flags(df, key)

        strategies = {
            "gap_warm": gap_signal(df, key, "warm"),
            "gap_hot": gap_signal(df, key, "hot"),
            "heur_warm": warm_heur,
            "heur_hot": hot_heur,
            "model_warm": warm_model,
            "model_hot": hot_model,
        }

        strat_rows = {}
        for name, signal in strategies.items():
            strat_rows[name] = {
                "per_spin": per_spin_eval(df, signal, target_col),
                "episodes": episode_backtest(df, signal, target_col),
            }

        report["targets"][key] = {
            "events": int(df[target_col].sum()),
            "base_rate": float(df[target_col].mean()),
            "base_next5": float(future_hit_within_k(df[target_col], 5).mean()),
            "top_features": top_features,
            "strategies": strat_rows,
        }

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        sns.histplot(score_heur, bins=20, ax=axes[0], color="#4c72b0")
        axes[0].set_title(f"{key} heuristic score")
        axes[0].set_xlabel("Score")

        sns.histplot(score_model.dropna(), bins=20, ax=axes[1], color="#dd8452")
        axes[1].set_title(f"{key} model score (holdout)")
        axes[1].set_xlabel("Probability")
        plt.tight_layout()
        path = OUT_DIR / f"{key.lower()}_score_dists.png"
        plt.savefig(path, dpi=160)
        plt.close()
        plot_paths.append(str(path))

    report["plots"] = plot_paths
    return report


def main():
    df = add_features(load_data())
    report = build_reports(df)

    json_path = OUT_DIR / "hotzone_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = ["# ACC / SPN Hot Zone Backtest", ""]
    lines.append(f"- Rows: {report['overview']['rows']:,}")
    lines.append(f"- Sessions: {report['overview']['sessions']}")
    lines.append(f"- Accounts: {report['overview']['accounts']}")

    for key in ["ACC", "SPN"]:
        tgt = report["targets"][key]
        lines.append("")
        lines.append(f"## {key}")
        lines.append(f"- Events: {tgt['events']}")
        lines.append(f"- Base per-spin rate: {tgt['base_rate']:.3%}")
        lines.append(f"- Base next-5 rate: {tgt['base_next5']:.3%}")
        lines.append("- Top model features:")
        for feat, val in tgt["top_features"][:10]:
            lines.append(f"  {feat}: {val}")
        lines.append("")
        lines.append("### Strategies")
        for name, row in tgt["strategies"].items():
            ps = row["per_spin"]
            ep = row["episodes"]
            lines.append(
                f"- `{name}`: next5 {ps['next5_rate']:.3%} vs {ps['baseline_next5']:.3%} (lift {ps['lift']:.2f}x), alerts {ps['alerts']}; windows {ep['windows']}, window hit {ep['window_hit_rate']:.3%}, caught {ep['caught_events']} / {tgt['events']} ({ep['capture_rate']:.3%}), spins/hit {ep['spins_per_hit']:.1f}"
            )

    md_path = OUT_DIR / "HOTZONE_REPORT.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
