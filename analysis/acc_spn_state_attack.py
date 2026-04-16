import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "analysis" / "output_acc_spn_state"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=0.9)


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
    for col in ["r1_idx", "r2_idx", "r3_idx", "bet_level", "bet_multiplier"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["triple_symbol"] = np.where(df["is_triple"], df.get("reel_1"), "none")
    df["is_acc"] = df["is_triple"] & df["triple_symbol"].eq("accumulation")
    df["is_spn"] = df["is_triple"] & df["triple_symbol"].eq("spins")
    df["event_label"] = np.where(df["is_acc"], "T_ACC", np.where(df["is_spn"], "T_SPN", df.get("spin_result", "other")))
    return df


TARGETS = {
    "ACC": {"col": "is_acc", "symbol": "accumulation", "idx": 8},
    "SPN": {"col": "is_spn", "symbol": "spins", "idx": 6},
}


def per_account_validation(df: pd.DataFrame, key: str, target_col: str):
    rows = []
    base = df[target_col].mean()
    next5 = future_hit_within_k(df[target_col], 5)
    for acct, adf in df.groupby("account"):
        n = len(adf)
        hits = int(adf[target_col].sum())
        rate = hits / n if n else np.nan
        seq_count = 0
        seq_opp = 0
        if key == "ACC":
            mask = adf["is_spn"]
        else:
            mask = adf["is_acc"]
        seq_opp = int(mask.sum())
        if seq_opp:
            seq_hits = next5.loc[adf.index[mask]].mean()
            pval = stats.binomtest(int(next5.loc[adf.index[mask]].sum()), seq_opp, base, alternative="greater").pvalue
        else:
            seq_hits = np.nan
            pval = np.nan
        rows.append(
            {
                "account": acct,
                "spins": n,
                "hits": hits,
                "rate": rate,
                "base_pool_rate": base,
                "opposite_triple_n": seq_opp,
                "opp_to_next5_rate": seq_hits,
                "opp_to_next5_lift": (seq_hits / next5.mean()) if seq_opp else np.nan,
                "opp_to_next5_p": pval,
            }
        )
    return rows


def sequence_cross_signal(df: pd.DataFrame, key: str, target_col: str):
    next5 = future_hit_within_k(df[target_col], 5)
    base = float(next5.mean())
    event_counts = df["event_label"].value_counts()
    rows = []
    pvals = []
    for event, n in event_counts.items():
        if n < 150:
            continue
        mask = df["event_label"] == event
        k = int(next5[mask].sum())
        pval = stats.binomtest(k, int(mask.sum()), base, alternative="greater").pvalue
        rows.append(
            {
                "from_event": event,
                "n": int(mask.sum()),
                "next5_rate": float(next5[mask].mean()),
                "baseline_next5": base,
                "lift": float(next5[mask].mean() / base) if base else np.nan,
                "p": float(pval),
            }
        )
        pvals.append(pval)
    adj = bh_adjust(pvals)
    for row, q in zip(rows, adj):
        row["q"] = q
    return sorted(rows, key=lambda x: (x["p"], -x["lift"]))


def idx_state_attack(df: pd.DataFrame, key: str, target_col: str, target_idx: int):
    idx_df = df.dropna(subset=["r1_idx", "r2_idx", "r3_idx"]).copy()
    idx_df["next_target_1"] = future_hit_within_k(idx_df[target_col], 1)
    idx_df["next_target_5"] = future_hit_within_k(idx_df[target_col], 5)
    base1 = float(idx_df["next_target_1"].mean())
    base5 = float(idx_df["next_target_5"].mean())

    for col in ["r1_idx", "r2_idx", "r3_idx"]:
        idx_df[f"{col}_prev"] = idx_df.groupby("account")[col].shift(1)
        idx_df[f"{col}_delta"] = idx_df[col] - idx_df[f"{col}_prev"]
        idx_df[f"{col}_dist"] = np.abs(idx_df[col] - target_idx)

    idx_df["all_prev_match_target"] = (
        idx_df["r1_idx_prev"].eq(target_idx) & idx_df["r2_idx_prev"].eq(target_idx) & idx_df["r3_idx_prev"].eq(target_idx)
    )
    idx_df["all_curr_match_target"] = (
        idx_df["r1_idx"].eq(target_idx) & idx_df["r2_idx"].eq(target_idx) & idx_df["r3_idx"].eq(target_idx)
    )
    idx_df["sum_dist"] = idx_df[[f"{c}_dist" for c in ["r1_idx", "r2_idx", "r3_idx"]]].sum(axis=1)
    idx_df["sum_prev_dist"] = np.abs(idx_df["r1_idx_prev"] - target_idx) + np.abs(idx_df["r2_idx_prev"] - target_idx) + np.abs(idx_df["r3_idx_prev"] - target_idx)
    idx_df["toward_target"] = idx_df["sum_dist"] < idx_df["sum_prev_dist"]

    results = {
        "rows_with_idx": int(len(idx_df)),
        "target_rows_with_idx": int(idx_df[target_col].sum()),
        "base_next1": base1,
        "base_next5": base5,
        "target_index_consistency": {},
        "step_patterns": {},
        "predictive_rules": [],
        "cycle_tests": [],
    }

    target_rows = idx_df[idx_df[target_col]]
    for col in ["r1_idx", "r2_idx", "r3_idx"]:
        vc = target_rows[col].value_counts(dropna=False)
        results["target_index_consistency"][col] = vc.head(5).to_dict()

    for col in ["r1_idx", "r2_idx", "r3_idx"]:
        vc = target_rows[f"{col}_delta"].value_counts(dropna=False).head(10)
        results["step_patterns"][col] = {str(k): int(v) for k, v in vc.items()}

    rule_defs = {
        "prev_all_target": idx_df["all_prev_match_target"],
        "curr_all_target": idx_df["all_curr_match_target"],
        "prev_r1_target": idx_df["r1_idx_prev"].eq(target_idx),
        "prev_r2_target": idx_df["r2_idx_prev"].eq(target_idx),
        "prev_r3_target": idx_df["r3_idx_prev"].eq(target_idx),
        "toward_target": idx_df["toward_target"].fillna(False),
        "sum_dist_le_2": idx_df["sum_dist"].le(2),
        "sum_prev_dist_le_2": idx_df["sum_prev_dist"].le(2),
    }
    pvals = []
    rows = []
    for name, mask in rule_defs.items():
        mask = mask.fillna(False)
        n = int(mask.sum())
        if n < 30:
            continue
        k1 = int(idx_df.loc[mask, "next_target_1"].sum())
        k5 = int(idx_df.loc[mask, "next_target_5"].sum())
        p1 = stats.binomtest(k1, n, base1, alternative="greater").pvalue if base1 > 0 else 1.0
        p5 = stats.binomtest(k5, n, base5, alternative="greater").pvalue if base5 > 0 else 1.0
        rows.append(
            {
                "rule": name,
                "n": n,
                "next1_rate": float(k1 / n),
                "base_next1": base1,
                "lift1": float((k1 / n) / base1) if base1 else np.nan,
                "p1": float(p1),
                "next5_rate": float(k5 / n),
                "base_next5": base5,
                "lift5": float((k5 / n) / base5) if base5 else np.nan,
                "p5": float(p5),
            }
        )
        pvals.extend([p1, p5])
    adj = bh_adjust(pvals)
    i = 0
    for row in rows:
        row["q1"] = adj[i]
        row["q5"] = adj[i + 1]
        i += 2
    results["predictive_rules"] = sorted(rows, key=lambda x: (x["p1"], x["p5"]))

    # Test modular cycles on indexed rows only.
    positions = np.flatnonzero(idx_df[target_col].to_numpy())
    for mod in [6, 8, 10, 12]:
        if len(positions) == 0:
            continue
        counts = np.bincount(positions % mod, minlength=mod)
        expected = np.full(mod, len(positions) / mod)
        stat, pval = stats.chisquare(counts, expected)
        results["cycle_tests"].append(
            {
                "mod": mod,
                "chi2": float(stat),
                "p": float(pval),
                "top_bins": counts.argsort()[-3:][::-1].tolist(),
                "top_counts": counts[counts.argsort()[-3:][::-1]].tolist(),
            }
        )

    # Visualize transitions into target.
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    heat = pd.crosstab(
        idx_df["sum_prev_dist"].fillna(-1).clip(-1, 12),
        idx_df["next_target_1"],
        normalize="index",
    )
    sns.heatmap(heat, cmap="mako", ax=axes[0])
    axes[0].set_title(f"{key}: next-spin hit rate by previous distance")
    axes[0].set_xlabel("Next target in 1 spin")
    axes[0].set_ylabel("Previous total distance")

    if len(target_rows) > 0:
        deltas = pd.DataFrame(
            {
                "r1": target_rows["r1_idx_delta"],
                "r2": target_rows["r2_idx_delta"],
                "r3": target_rows["r3_idx_delta"],
            }
        ).fillna(999)
        top_delta = deltas.value_counts().head(20)
        labels = [f"{a},{b},{c}" for a, b, c in top_delta.index]
        axes[1].barh(range(len(top_delta)), top_delta.values, color="#dd8452")
        axes[1].set_yticks(range(len(top_delta)))
        axes[1].set_yticklabels(labels)
        axes[1].set_title(f"{key}: top step triples entering target spins")
    plt.tight_layout()
    plot_path = OUT_DIR / f"{key.lower()}_idx_state.png"
    plt.savefig(plot_path, dpi=160)
    plt.close()

    return results, str(plot_path)


def main():
    df = load_data()
    report = {
        "overview": {
            "rows": int(len(df)),
            "accounts": df["account"].value_counts().to_dict(),
        },
        "targets": {},
        "plots": [],
    }

    for key, meta in TARGETS.items():
        target_col = meta["col"]
        account_rows = per_account_validation(df, key, target_col)
        cross_signal = sequence_cross_signal(df, key, target_col)
        idx_attack, plot = idx_state_attack(df, key, target_col, meta["idx"])
        report["targets"][key] = {
            "events": int(df[target_col].sum()),
            "per_account": account_rows,
            "cross_signal": cross_signal,
            "idx_attack": idx_attack,
        }
        report["plots"].append(plot)

    out_json = OUT_DIR / "state_attack_report.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = ["# ACC / SPN State Attack Report", ""]
    lines.append(f"- Deduped rows: {report['overview']['rows']:,}")
    lines.append(f"- Accounts: {report['overview']['accounts']}")
    for key in ["ACC", "SPN"]:
        tgt = report["targets"][key]
        lines.append("")
        lines.append(f"## {key}")
        lines.append(f"- Events: {tgt['events']}")
        lines.append("")
        lines.append("### Per-account")
        for row in tgt["per_account"]:
            lines.append(
                f"- {row['account']}: {row['hits']} hits / {row['spins']} spins = {row['rate']:.3%}; opposite-triple -> next5 {row['opp_to_next5_rate'] if pd.notna(row['opp_to_next5_rate']) else float('nan'):.3%} over {row['opposite_triple_n']} cases"
            )
        lines.append("")
        lines.append("### Cross-signal")
        for row in tgt["cross_signal"][:8]:
            lines.append(
                f"- after `{row['from_event']}`: next5 {key} = {row['next5_rate']:.3%} vs baseline {row['baseline_next5']:.3%}, lift {row['lift']:.2f}x, p={row['p']:.4g}, q={row['q']:.4g}"
            )
        lines.append("")
        lines.append("### Index attack")
        lines.append(f"- Indexed rows: {tgt['idx_attack']['rows_with_idx']}")
        lines.append(f"- Indexed target rows: {tgt['idx_attack']['target_rows_with_idx']}")
        lines.append(f"- Base next1: {tgt['idx_attack']['base_next1']:.3%}")
        lines.append(f"- Base next5: {tgt['idx_attack']['base_next5']:.3%}")
        lines.append(f"- Target index consistency: {tgt['idx_attack']['target_index_consistency']}")
        for row in tgt["idx_attack"]["predictive_rules"][:10]:
            lines.append(
                f"- rule `{row['rule']}`: next1 {row['next1_rate']:.3%} vs {row['base_next1']:.3%} (lift {row['lift1']:.2f}x, p={row['p1']:.4g}, q={row['q1']:.4g}); next5 {row['next5_rate']:.3%} vs {row['base_next5']:.3%} (lift {row['lift5']:.2f}x, p={row['p5']:.4g}, q={row['q5']:.4g})"
            )

    out_md = OUT_DIR / "STATE_ATTACK_REPORT.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")


if __name__ == "__main__":
    main()
