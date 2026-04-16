import json
import math
from collections import Counter, defaultdict
from itertools import product
from pathlib import Path

import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import ruptures as rpt
import seaborn as sns
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "analysis" / "output_acc_spn_exhaustive"
OUT_DIR.mkdir(parents=True, exist_ok=True)
sns.set_theme(style="whitegrid", font_scale=0.9)
np.random.seed(42)

TARGETS = {
    "ACC": {"col": "is_acc", "idx": 8},
    "SPN": {"col": "is_spn", "idx": 6},
}


def bh_adjust(pvals):
    arr = np.array(pvals, dtype=float)
    if len(arr) == 0:
        return []
    order = np.argsort(arr)
    ranked = arr[order]
    adj = np.empty(len(arr), dtype=float)
    prev = 1.0
    for i in range(len(arr) - 1, -1, -1):
        rank = i + 1
        val = min(prev, ranked[i] * len(arr) / rank)
        adj[i] = val
        prev = val
    out = np.empty(len(arr), dtype=float)
    out[order] = adj
    return out.tolist()


def future_hit_within_k(series: pd.Series, k: int) -> pd.Series:
    arr = series.fillna(False).astype(bool).to_numpy()
    out = np.zeros(len(arr), dtype=bool)
    for step in range(1, k + 1):
        shifted = np.zeros(len(arr), dtype=bool)
        if step < len(arr):
            shifted[:-step] = arr[step:]
        out |= shifted
    return pd.Series(out, index=series.index)


def zscore_pval(obs_rate: float, base_rate: float, n: int):
    if n <= 0 or base_rate <= 0 or base_rate >= 1:
        return 1.0
    se = math.sqrt(base_rate * (1 - base_rate) / n)
    if se == 0:
        return 1.0
    z = (obs_rate - base_rate) / se
    if z <= 0:
        return 1.0
    return 1 - stats.norm.cdf(z)


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
        df["source_file"] = str(path.relative_to(ROOT))
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
        "bet_level", "bet_multiplier", "reward_code", "r1_idx", "r2_idx", "r3_idx",
        "sa_spins", "sa_acc", "sa_spn", "sa_atk", "sa_stl", "sa_shd",
        "sa_3x_atk", "sa_3x_stl", "sa_3x_shd", "acc_count", "spn_count", "atk_count", "stl_count", "shd_count",
        "accum_pct", "accum_current", "accum_total", "accum_mission", "accum_delta"
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["triple_symbol"] = np.where(df["is_triple"], df.get("reel_1"), "none")
    df["is_acc"] = df["is_triple"] & df["triple_symbol"].eq("accumulation")
    df["is_spn"] = df["is_triple"] & df["triple_symbol"].eq("spins")
    df["event_label"] = np.where(
        df["is_acc"], "T_ACC",
        np.where(df["is_spn"], "T_SPN",
                 np.where(df["is_triple"], "T_OTHER", df.get("spin_result", "unknown")))
    )
    return df


def add_gap_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for key, meta in TARGETS.items():
        col = meta["col"]
        gap_vals = np.zeros(len(out), dtype=int)
        for _, idxs in out.groupby("account").groups.items():
            idxs = list(idxs)
            drought = 0
            for pos in idxs:
                gap_vals[pos] = drought
                if out.at[pos, col]:
                    drought = 0
                else:
                    drought += 1
        out[f"gap_{key.lower()}"] = gap_vals
        for mod in [10, 15, 20, 25, 30, 50, 100]:
            out[f"gap_{key.lower()}_mod{mod}"] = gap_vals % mod
    return out


def add_prespin_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    group = out.groupby("account", sort=False)
    out["bet_switched"] = group["bet_level"].diff().fillna(0) != 0
    out["time_delta_s"] = group["timestamp"].diff().dt.total_seconds().fillna(0)
    out["prev_event"] = group["event_label"].shift(1).fillna("START")
    out["prev2_event"] = group["event_label"].shift(2).fillna("START2")

    for lag in [1, 2, 3, 5]:
        for col in ["r1_idx", "r2_idx", "r3_idx", "bet_level", "bet_multiplier", "accum_pct", "accum_delta"]:
            if col in out.columns:
                out[f"{col}_lag{lag}"] = group[col].shift(lag)

    for col in ["r1_idx", "r2_idx", "r3_idx"]:
        if col in out.columns:
            out[f"{col}_delta1"] = out[col] - out[f"{col}_lag1"]
            out[f"{col}_delta2"] = out[f"{col}_lag1"] - out[f"{col}_lag2"]

    if set(["r1_idx", "r2_idx", "r3_idx"]).issubset(out.columns):
        out["idx_sum"] = out[["r1_idx", "r2_idx", "r3_idx"]].sum(axis=1)
        out["idx_spread"] = out[["r1_idx", "r2_idx", "r3_idx"]].max(axis=1) - out[["r1_idx", "r2_idx", "r3_idx"]].min(axis=1)
        out["idx_sum_lag1"] = out[[f"{c}_lag1" for c in ["r1_idx", "r2_idx", "r3_idx"]]].sum(axis=1)
        out["idx_spread_lag1"] = out[[f"{c}_lag1" for c in ["r1_idx", "r2_idx", "r3_idx"]]].max(axis=1) - out[[f"{c}_lag1" for c in ["r1_idx", "r2_idx", "r3_idx"]]].min(axis=1)
        out["prev_pair_any"] = (
            out["r1_idx_lag1"].eq(out["r2_idx_lag1"]) |
            out["r1_idx_lag1"].eq(out["r3_idx_lag1"]) |
            out["r2_idx_lag1"].eq(out["r3_idx_lag1"])
        )
    else:
        out["prev_pair_any"] = False

    event_dummies = pd.get_dummies(out["prev_event"], prefix="prev_event")
    out = pd.concat([out, event_dummies], axis=1)

    rolling_cols = [c for c in ["acc_count", "spn_count", "atk_count", "stl_count", "shd_count", "is_triple"] if c in out.columns]
    for w in [5, 10, 20]:
        shifted = group[rolling_cols].shift(1)
        rolled = shifted.groupby(out["account"]).rolling(w, min_periods=1).sum().reset_index(level=0, drop=True)
        for c in rolling_cols:
            out[f"{c}_sum{w}"] = rolled[c]

    for w in [5, 10]:
        seq_entropy = np.zeros(len(out), dtype=float)
        for _, idxs in out.groupby("account").groups.items():
            idxs = list(idxs)
            labels = out.loc[idxs, "event_label"].tolist()
            for i, pos in enumerate(idxs):
                start = max(0, i - w)
                win = labels[start:i]
                if not win:
                    seq_entropy[pos] = 0.0
                    continue
                counts = Counter(win)
                total = len(win)
                seq_entropy[pos] = -sum((v / total) * math.log2(v / total) for v in counts.values())
        out[f"event_entropy_{w}"] = seq_entropy

    return out


def session_summary(df: pd.DataFrame):
    rows = []
    for session_id, sdf in df.groupby("session_id"):
        row = {
            "session_id": session_id,
            "account": sdf["account"].iloc[0],
            "spins": len(sdf),
            "acc_rate": float(sdf["is_acc"].mean()),
            "spn_rate": float(sdf["is_spn"].mean()),
            "first_ts": str(sdf["timestamp"].min()),
            "last_ts": str(sdf["timestamp"].max()),
            "bet_levels": int(sdf["bet_level"].nunique()) if "bet_level" in sdf.columns else 0,
        }
        rows.append(row)
    return rows


def change_point_analysis(df: pd.DataFrame, key: str, target_col: str):
    rows = []
    plot_paths = []
    for session_id, sdf in df.groupby("session_id"):
        if len(sdf) < 800:
            continue
        bucket = 25
        bins = np.arange(len(sdf)) // bucket
        agg = pd.DataFrame({
            "target": sdf[target_col].astype(int),
            "bet": sdf["bet_level"].fillna(0),
            "acc": sdf["acc_count"].fillna(0) if "acc_count" in sdf.columns else 0,
            "spn": sdf["spn_count"].fillna(0) if "spn_count" in sdf.columns else 0,
        }).groupby(bins).mean()
        signal = agg.to_numpy()
        algo = rpt.Binseg(model="l2").fit(signal)
        try:
            max_breaks = min(6, max(1, len(signal) // 20))
            bkps = algo.predict(n_bkps=max_breaks)
        except Exception:
            bkps = [len(signal)]
        if len(bkps) <= 1:
            continue
        scaled_bkps = [min(len(sdf), int(x * bucket)) for x in bkps]
        seg_starts = [0] + scaled_bkps[:-1]
        seg_ends = scaled_bkps
        seg_rows = []
        for a, b in zip(seg_starts, seg_ends):
            seg = sdf.iloc[a:b]
            if len(seg) == 0:
                continue
            seg_rows.append({
                "start": int(a),
                "end": int(b),
                "len": int(len(seg)),
                "rate": float(seg[target_col].mean()),
                "bet_mean": float(seg["bet_level"].fillna(0).mean()) if "bet_level" in seg.columns else 0.0,
            })
        rows.append({"session_id": session_id, "n_breaks": len(bkps) - 1, "segments": seg_rows})

        fig, ax = plt.subplots(figsize=(12, 4.2))
        series = agg["target"]
        ax.plot((series.index * bucket).values, series.values, color="#4c72b0")
        for bp in scaled_bkps[:-1]:
            ax.axvline(bp, color="red", linestyle="--", alpha=0.6)
        ax.set_title(f"{key}: change points for {session_id}")
        ax.set_xlabel("Spin within session")
        ax.set_ylabel("Bucketed hit rate")
        plt.tight_layout()
        path = OUT_DIR / f"{key.lower()}_cp_{session_id.replace('|', '_').replace('.', '_')}.png"
        plt.savefig(path, dpi=160)
        plt.close()
        plot_paths.append(str(path))
    return rows, plot_paths


def rule_mining(df: pd.DataFrame, key: str, target_col: str):
    work = df.copy()
    work["target_next5"] = future_hit_within_k(work[target_col], 5)
    base = float(work["target_next5"].mean())

    candidate_defs = [
        ("bet_switched", work["bet_switched"].fillna(False)),
        ("prev_T_ACC", work["prev_event"].eq("T_ACC")),
        ("prev_T_SPN", work["prev_event"].eq("T_SPN")),
        ("prev_pair_any", work["prev_pair_any"].fillna(False)),
        ("gap_high_p90", work[f"gap_{key.lower()}"] >= work[f"gap_{key.lower()}"].quantile(0.9)),
        ("gap_high_p75", work[f"gap_{key.lower()}"] >= work[f"gap_{key.lower()}"].quantile(0.75)),
        ("time_delta_gt5", work["time_delta_s"] > 5),
        ("time_delta_gt20", work["time_delta_s"] > 20),
        ("bet_level_high", work["bet_level"] >= work["bet_level"].quantile(0.75) if "bet_level" in work.columns else False),
        ("acc_pct_high", work["accum_pct"] >= 80 if "accum_pct" in work.columns else False),
        ("acc_delta_pos", work["accum_delta"] > 0 if "accum_delta" in work.columns else False),
        ("last5_spn_ge3", work["spn_count_sum5"] >= 3 if "spn_count_sum5" in work.columns else False),
        ("last5_acc_ge3", work["acc_count_sum5"] >= 3 if "acc_count_sum5" in work.columns else False),
        ("last10_triples_ge1", work["is_triple_sum10"] >= 1 if "is_triple_sum10" in work.columns else False),
        ("entropy_high", work["event_entropy_10"] >= work["event_entropy_10"].quantile(0.75)),
    ]

    idx_cols = ["r1_idx_lag1", "r2_idx_lag1", "r3_idx_lag1"]
    if set(idx_cols).issubset(work.columns):
        target_idx = TARGETS[key]["idx"]
        candidate_defs.extend([
            ("prev_r1_target_idx", work["r1_idx_lag1"].eq(target_idx)),
            ("prev_r2_target_idx", work["r2_idx_lag1"].eq(target_idx)),
            ("prev_r3_target_idx", work["r3_idx_lag1"].eq(target_idx)),
            ("idx_sum_lag1_high", work["idx_sum_lag1"] >= work["idx_sum_lag1"].quantile(0.75)),
            ("idx_spread_lag1_low", work["idx_spread_lag1"] <= work["idx_spread_lag1"].quantile(0.25)),
        ])

    rules = []
    pvals = []

    for name, mask in candidate_defs:
        if isinstance(mask, bool):
            continue
        mask = pd.Series(mask, index=work.index).fillna(False)
        n = int(mask.sum())
        if n < 50:
            continue
        rate = float(work.loc[mask, "target_next5"].mean())
        pval = zscore_pval(rate, base, n)
        rules.append({
            "rule": name,
            "arity": 1,
            "n": n,
            "rate": rate,
            "base": base,
            "lift": float(rate / base) if base else np.nan,
            "p": pval,
        })
        pvals.append(pval)

    named = [(n, pd.Series(m, index=work.index).fillna(False)) for n, m in candidate_defs if not isinstance(m, bool)]
    for i in range(len(named)):
        for j in range(i + 1, len(named)):
            name = f"{named[i][0]} & {named[j][0]}"
            mask = named[i][1] & named[j][1]
            n = int(mask.sum())
            if n < 30:
                continue
            rate = float(work.loc[mask, "target_next5"].mean())
            pval = zscore_pval(rate, base, n)
            rules.append({
                "rule": name,
                "arity": 2,
                "n": n,
                "rate": rate,
                "base": base,
                "lift": float(rate / base) if base else np.nan,
                "p": pval,
            })
            pvals.append(pval)

    adj = bh_adjust(pvals)
    for row, q in zip(rules, adj):
        row["q"] = q
    return sorted(rules, key=lambda x: (x["p"], -x["lift"], -x["n"]))


def build_model_matrix(df: pd.DataFrame, target_col: str):
    numeric_cols = []
    for col in df.columns:
        if col in [target_col, "is_acc", "is_spn", "is_triple"]:
            continue
        if col.startswith("prev_event_"):
            numeric_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        elif col in ["bet_switched"]:
            numeric_cols.append(col)
    feature_cols = sorted(set(numeric_cols))
    X = df[feature_cols].copy()
    for col in X.columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    X = X.fillna(-999)
    y = df[target_col].astype(int).copy()
    return X, y, feature_cols


def model_backtest(df: pd.DataFrame, key: str, target_col: str):
    work = df.copy()
    work["target_next5"] = future_hit_within_k(work[target_col], 5).astype(int)
    X, y, feature_cols = build_model_matrix(work, "target_next5")

    sessions = work["session_id"].drop_duplicates().tolist()
    fold_rows = []
    feature_importance = Counter()

    for holdout in sessions:
        train_mask = work["session_id"] != holdout
        test_mask = work["session_id"] == holdout
        if train_mask.sum() < 1000 or test_mask.sum() < 200:
            continue
        y_train = work.loc[train_mask, "target_next5"]
        if y_train.nunique() < 2:
            continue
        model = lgb.LGBMClassifier(
            objective="binary",
            n_estimators=140,
            learning_rate=0.06,
            num_leaves=15,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            class_weight="balanced",
            verbosity=-1,
        )
        model.fit(X.loc[train_mask], y_train)
        proba = model.predict_proba(X.loc[test_mask])[:, 1]
        top10 = np.quantile(proba, 0.9)
        top5 = np.quantile(proba, 0.95)
        base = float(work.loc[test_mask, "target_next5"].mean())
        for label, thr in [("top10pct", top10), ("top5pct", top5)]:
            pick = proba >= thr
            n = int(pick.sum())
            rate = float(work.loc[test_mask, "target_next5"].iloc[np.where(pick)[0]].mean()) if n else 0.0
            fold_rows.append({
                "session_id": holdout,
                "bucket": label,
                "n": n,
                "rate": rate,
                "base": base,
                "lift": float(rate / base) if base else np.nan,
            })
        fi = pd.Series(model.feature_importances_, index=feature_cols).sort_values(ascending=False).head(20)
        feature_importance.update({k: int(v) for k, v in fi.items()})

    fold_df = pd.DataFrame(fold_rows)
    top_features = feature_importance.most_common(20)

    if not fold_df.empty:
        plt.figure(figsize=(10, 4.5))
        sns.barplot(data=fold_df, x="session_id", y="lift", hue="bucket")
        plt.xticks(rotation=45, ha="right")
        plt.title(f"{key}: leave-one-session-out model lift")
        plt.tight_layout()
        plot_path = OUT_DIR / f"{key.lower()}_model_lift.png"
        plt.savefig(plot_path, dpi=160)
        plt.close()
    else:
        plot_path = None

    return {
        "folds": fold_df.to_dict("records") if not fold_df.empty else [],
        "top_features": top_features,
        "top_shap": [],
    }, str(plot_path) if plot_path else None


def affine_index_search(df: pd.DataFrame, key: str):
    idx_df = df.dropna(subset=["r1_idx", "r2_idx", "r3_idx"]).copy()
    if idx_df.empty:
        return {"tested": 0, "best_rules": []}

    results = []
    for reel in ["r1_idx", "r2_idx", "r3_idx"]:
        prev = idx_df.groupby("account")[reel].shift(1)
        curr = idx_df[reel]
        valid = prev.notna() & curr.notna()
        if valid.sum() < 100:
            continue
        p = prev[valid].astype(int).to_numpy()
        c = curr[valid].astype(int).to_numpy()
        for a, b in product(range(9), range(9)):
            pred = (a * p + b) % 9
            acc = float((pred == c).mean())
            target_mask = pred == TARGETS[key]["idx"]
            if target_mask.sum() == 0:
                tgt_acc = 0.0
            else:
                tgt_acc = float((c[target_mask] == TARGETS[key]["idx"]).mean())
            results.append({
                "reel": reel,
                "a": a,
                "b": b,
                "overall_match": acc,
                "target_pred_precision": tgt_acc,
                "n": int(len(c)),
            })
    best = sorted(results, key=lambda x: (-x["overall_match"], -x["target_pred_precision"]))[:20]
    return {"tested": len(results), "best_rules": best}


def main():
    df = load_data()
    df = add_gap_features(df)
    df = add_prespin_features(df)

    report = {
        "overview": {
            "rows": int(len(df)),
            "sessions": int(df["session_id"].nunique()),
            "accounts": df["account"].value_counts().to_dict(),
            "session_summary": session_summary(df),
        },
        "targets": {},
        "plots": [],
    }

    for key, meta in TARGETS.items():
        target_col = meta["col"]
        cp_rows, cp_plots = change_point_analysis(df, key, target_col)
        rules = rule_mining(df, key, target_col)
        model_res, model_plot = model_backtest(df, key, target_col)
        affine = affine_index_search(df, key)
        report["targets"][key] = {
            "events": int(df[target_col].sum()),
            "base_rate": float(df[target_col].mean()),
            "base_next5": float(future_hit_within_k(df[target_col], 5).mean()),
            "change_points": cp_rows,
            "rules": rules[:100],
            "model": model_res,
            "affine_search": affine,
        }
        report["plots"].extend(cp_plots)
        if model_plot:
            report["plots"].append(model_plot)

    json_path = OUT_DIR / "exhaustive_hunt_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = ["# ACC / SPN Exhaustive Hunt", ""]
    lines.append(f"- Rows: {report['overview']['rows']:,}")
    lines.append(f"- Sessions: {report['overview']['sessions']}")
    lines.append(f"- Accounts: {report['overview']['accounts']}")

    lines.append("")
    lines.append("## Sessions")
    for row in report["overview"]["session_summary"]:
        lines.append(
            f"- `{row['session_id']}`: {row['spins']} spins, ACC {row['acc_rate']:.3%}, SPN {row['spn_rate']:.3%}, bet levels {row['bet_levels']}"
        )

    for key in ["ACC", "SPN"]:
        tgt = report["targets"][key]
        lines.append("")
        lines.append(f"## {key}")
        lines.append(f"- Events: {tgt['events']}")
        lines.append(f"- Base per-spin rate: {tgt['base_rate']:.3%}")
        lines.append(f"- Base next-5 rate: {tgt['base_next5']:.3%}")
        lines.append("")
        lines.append("### Best Rules")
        for row in tgt["rules"][:15]:
            lines.append(
                f"- `{row['rule']}`: next5 {row['rate']:.3%} vs {row['base']:.3%}, lift {row['lift']:.2f}x, n={row['n']}, p={row['p']:.4g}, q={row['q']:.4g}"
            )
        lines.append("")
        lines.append("### Model")
        for row in tgt["model"]["folds"][:20]:
            lines.append(
                f"- {row['session_id']} {row['bucket']}: {row['rate']:.3%} vs {row['base']:.3%}, lift {row['lift']:.2f}x, n={row['n']}"
            )
        if tgt["model"]["top_features"]:
            lines.append("- Top features:")
            for feat, val in tgt["model"]["top_features"][:10]:
                lines.append(f"  {feat}: {val}")
        if tgt["model"]["top_shap"]:
            lines.append("- Top SHAP:")
            for feat, val in tgt["model"]["top_shap"][:10]:
                lines.append(f"  {feat}: {val:.3f}")
        lines.append("")
        lines.append("### Change Points")
        for row in tgt["change_points"][:10]:
            lines.append(f"- {row['session_id']}: {row['n_breaks']} breaks")
        lines.append("")
        lines.append("### Affine Index Search")
        lines.append(f"- Rules tested: {tgt['affine_search']['tested']}")
        for row in tgt["affine_search"]["best_rules"][:10]:
            lines.append(
                f"- {row['reel']}: next=(a*prev+b) mod 9 with a={row['a']}, b={row['b']} -> match {row['overall_match']:.3%}, target precision {row['target_pred_precision']:.3%}"
            )

    md_path = OUT_DIR / "EXHAUSTIVE_HUNT_REPORT.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
