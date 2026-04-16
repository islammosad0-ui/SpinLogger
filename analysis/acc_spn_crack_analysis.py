import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from scipy.cluster.vq import kmeans2


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "analysis" / "output_acc_spn"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", font_scale=0.9)
np.random.seed(42)

TARGETS = {
    "ACC": {"symbol": "accumulation", "reward_code": 10, "title": "Triple Accumulation"},
    "SPN": {"symbol": "spins", "reward_code": 5, "title": "Triple Spins"},
}


def read_spin_file(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, engine="python", on_bad_lines="skip")
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    df["account"] = path.parent.name
    df["source_file"] = str(path.relative_to(ROOT))
    df["source_name"] = path.name
    df["source_quality"] = df.notna().sum(axis=1)
    return df


def load_all_spin_history() -> pd.DataFrame:
    files = sorted(DATA_DIR.rglob("spin_history*.csv"))
    frames = []
    for path in files:
        df = read_spin_file(path)
        if not df.empty:
            frames.append(df)
    if not frames:
        raise RuntimeError("No spin_history CSV files found under data/")

    raw = pd.concat(frames, ignore_index=True, sort=False)
    raw["seq"] = pd.to_numeric(raw.get("seq"), errors="coerce")
    raw = raw[raw["seq"].notna()].copy()
    raw["seq"] = raw["seq"].astype(int)
    raw["timestamp"] = pd.to_datetime(raw.get("timestamp"), errors="coerce")
    raw["is_triple"] = raw.get("is_triple", False).astype(str).str.lower().map(
        {"true": True, "false": False}
    ).fillna(raw.get("is_triple", False)).astype(bool)

    raw["dedup_score"] = raw["source_quality"].fillna(0)
    raw = raw.sort_values(
        ["account", "seq", "dedup_score", "source_name"],
        ascending=[True, True, False, False],
    )
    deduped = raw.drop_duplicates(subset=["account", "seq"], keep="first").copy()
    deduped = deduped.sort_values(["account", "seq"]).reset_index(drop=True)

    for col in ["bet_level", "bet_multiplier", "reward_code", "r1_idx", "r2_idx", "r3_idx"]:
        if col in deduped.columns:
            deduped[col] = pd.to_numeric(deduped[col], errors="coerce")

    deduped["triple_symbol"] = np.where(deduped["is_triple"], deduped.get("reel_1"), "none")
    deduped["is_acc"] = deduped["is_triple"] & (deduped["triple_symbol"] == "accumulation")
    deduped["is_spn"] = deduped["is_triple"] & (deduped["triple_symbol"] == "spins")

    def event_label(row):
        if row["is_acc"]:
            return "T_ACC"
        if row["is_spn"]:
            return "T_SPN"
        if row["is_triple"]:
            return f"T_{row.get('triple_symbol', 'other')}"
        return str(row.get("spin_result", "unknown"))

    deduped["event_label"] = deduped.apply(event_label, axis=1)
    return raw, deduped


def bh_adjust(pvals):
    arr = np.array(pvals, dtype=float)
    n = len(arr)
    if n == 0:
        return []
    order = np.argsort(arr)
    ranked = arr[order]
    adj = np.empty(n, dtype=float)
    prev = 1.0
    for i in range(n - 1, -1, -1):
        rank = i + 1
        val = min(prev, ranked[i] * n / rank)
        adj[i] = val
        prev = val
    out = np.empty(n, dtype=float)
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


def baseline_windows(adf: pd.DataFrame, target_col: str, window: int, n_samples: int) -> list[pd.DataFrame]:
    valid_endpoints = adf.index[(~adf[target_col]) & (adf.index >= window)].tolist()
    if not valid_endpoints:
        return []
    pick = min(n_samples, len(valid_endpoints))
    sampled = np.random.choice(valid_endpoints, size=pick, replace=False)
    out = []
    for end_idx in sampled:
        w = adf.iloc[end_idx - window:end_idx].copy()
        w["pos"] = list(range(-window, 0))
        out.append(w)
    return out


def add_drought_features(df: pd.DataFrame, target_col: str, name: str) -> None:
    droughts = []
    gaps = []
    for account in df["account"].unique():
        adf = df[df["account"] == account].copy()
        drought = 0
        last_hit = None
        for idx, row in adf.iterrows():
            droughts.append((idx, drought))
            if row[target_col]:
                if last_hit is not None:
                    gaps.append(drought + 1)
                drought = 0
                last_hit = idx
            else:
                drought += 1
    drought_map = dict(droughts)
    df[f"drought_{name}"] = df.index.map(drought_map)
    df.attrs[f"gaps_{name}"] = gaps


def sequence_analysis(df: pd.DataFrame, target_col: str, label: str):
    windows_20 = []
    windows_10 = []
    controls_20 = []
    cluster_vectors = []
    cluster_meta = []
    seq_tests = []
    symbol_cols = ["attack", "coin", "steal", "shield", "spins", "goldSack", "accumulation"]

    for account in df["account"].unique():
        adf = df[df["account"] == account].reset_index(drop=True)
        hit_idxs = adf.index[adf[target_col]].tolist()
        for idx in hit_idxs:
            if idx >= 20:
                w20 = adf.iloc[idx - 20:idx].copy()
                w20["pos"] = list(range(-20, 0))
                windows_20.append(w20)
                counts = [(w20["spin_result"] == s).sum() for s in sorted(df["spin_result"].dropna().unique())]
                counts += [(w20["event_label"].str.startswith("T_")).sum()]
                cluster_vectors.append(counts)
                cluster_meta.append({"account": account, "target_idx": idx})
            if idx >= 10:
                w10 = adf.iloc[idx - 10:idx].copy()
                windows_10.append(w10)
        controls_20.extend(baseline_windows(adf, target_col, 20, max(1, len(hit_idxs) * 3)))

    pre20 = pd.concat(windows_20, ignore_index=True) if windows_20 else pd.DataFrame()
    pre10 = pd.concat(windows_10, ignore_index=True) if windows_10 else pd.DataFrame()
    ctrl20 = pd.concat(controls_20, ignore_index=True) if controls_20 else pd.DataFrame()

    summary = {
        "n_windows_20": len(windows_20),
        "n_windows_10": len(windows_10),
        "symbol_enrichment": [],
        "top_patterns": [],
        "clusters": [],
        "practical_signals": [],
    }

    if pre20.empty:
        return summary, []

    all_results = df["spin_result"].fillna("unknown").tolist()
    for gram in [3, 5]:
        base = Counter(tuple(all_results[i:i + gram]) for i in range(len(all_results) - gram + 1))
        total_base = sum(base.values())
        observed = Counter(
            tuple(w["spin_result"].fillna("unknown").tolist()[-gram:]) for w in windows_20
        )
        for pattern, count in observed.most_common(10):
            base_p = base.get(pattern, 0) / total_base if total_base else 0
            obs_p = count / len(windows_20)
            pval = stats.binomtest(count, len(windows_20), base_p, alternative="greater").pvalue if base_p > 0 else 1.0
            seq_tests.append(
                {
                    "window_tail": gram,
                    "pattern": " -> ".join(pattern),
                    "count": count,
                    "obs_rate": obs_p,
                    "base_rate": base_p,
                    "p": pval,
                }
            )
    if seq_tests:
        adj = bh_adjust([x["p"] for x in seq_tests])
        for row, q in zip(seq_tests, adj):
            row["q"] = q
        summary["top_patterns"] = sorted(seq_tests, key=lambda x: (x["p"], -x["count"]))[:12]

    pre_event_rate = pre20.groupby("pos")["event_label"].value_counts(normalize=True).unstack(fill_value=0)
    plt.figure(figsize=(12, 5))
    sns.heatmap(pre_event_rate.T, cmap="YlOrRd")
    plt.title(f"{label}: event distribution in the 20 spins before target")
    plt.xlabel("Position before target")
    plt.ylabel("Event label")
    plt.tight_layout()
    path_heat = OUT_DIR / f"{label.lower()}_sequence_heatmap.png"
    plt.savefig(path_heat, dpi=160)
    plt.close()

    baseline_rates = {}
    for sym in symbol_cols:
        baseline_rates[sym] = (
            ((df["reel_1"] == sym).sum() + (df["reel_2"] == sym).sum() + (df["reel_3"] == sym).sum()) / (len(df) * 3)
        )

    for sym in symbol_cols:
        pre_rate = (
            ((pre20["reel_1"] == sym).sum() + (pre20["reel_2"] == sym).sum() + (pre20["reel_3"] == sym).sum())
            / (len(pre20) * 3)
        )
        ctrl_rate = (
            ((ctrl20["reel_1"] == sym).sum() + (ctrl20["reel_2"] == sym).sum() + (ctrl20["reel_3"] == sym).sum())
            / (len(ctrl20) * 3)
        ) if not ctrl20.empty else baseline_rates[sym]
        k = int((pre20["reel_1"] == sym).sum() + (pre20["reel_2"] == sym).sum() + (pre20["reel_3"] == sym).sum())
        n = int(len(pre20) * 3)
        pval = stats.binomtest(k, n, ctrl_rate).pvalue if n > 0 and ctrl_rate > 0 else 1.0
        summary["symbol_enrichment"].append(
            {
                "symbol": sym,
                "pre_rate": pre_rate,
                "ctrl_rate": ctrl_rate,
                "baseline_rate": baseline_rates[sym],
                "ratio_vs_ctrl": pre_rate / ctrl_rate if ctrl_rate else np.nan,
                "p": pval,
            }
        )
    adj = bh_adjust([x["p"] for x in summary["symbol_enrichment"]])
    for row, q in zip(summary["symbol_enrichment"], adj):
        row["q"] = q

    if len(cluster_vectors) >= 6:
        mat = np.array(cluster_vectors, dtype=float)
        k = min(4, max(2, len(mat) // 40 or 2))
        centers, labels = kmeans2(mat, k, minit="points")
        counts = Counter(labels)
        for cluster_id in sorted(counts):
            members = mat[np.array(labels) == cluster_id]
            center = centers[cluster_id]
            summary["clusters"].append(
                {
                    "cluster": int(cluster_id),
                    "size": int(counts[cluster_id]),
                    "share": counts[cluster_id] / len(mat),
                    "dominant_results": center.tolist()[:7],
                }
            )

    target_next5 = []
    base_next5 = future_hit_within_k(df[target_col], 5)
    for event in sorted(df["event_label"].dropna().unique()):
        mask = df["event_label"] == event
        if mask.sum() < 100:
            continue
        hits = base_next5[mask]
        rate = hits.mean()
        base_rate = base_next5.fillna(False).astype(bool).mean()
        pval = stats.binomtest(int(hits.sum()), int(mask.sum()), base_rate, alternative="greater").pvalue
        target_next5.append(
            {
                "signal": event,
                "n": int(mask.sum()),
                "next5_rate": rate,
                "baseline_next5": base_rate,
                "lift": rate / base_rate if base_rate else np.nan,
                "p": pval,
            }
        )
    adj = bh_adjust([x["p"] for x in target_next5])
    for row, q in zip(target_next5, adj):
        row["q"] = q
    summary["practical_signals"] = sorted(target_next5, key=lambda x: (x["p"], -x["lift"]))[:10]

    return summary, [str(path_heat)]


def periodicity_analysis(df: pd.DataFrame, target_col: str, label: str):
    positions = np.flatnonzero(df[target_col].to_numpy())
    binary = df[target_col].astype(int).to_numpy()
    gaps = np.diff(positions)
    out = {
        "n_events": int(binary.sum()),
        "gap_summary": {},
        "autocorr_peaks": [],
        "mod_tests": [],
    }
    if len(gaps) == 0:
        return out, []

    out["gap_summary"] = {
        "mean": float(np.mean(gaps)),
        "median": float(np.median(gaps)),
        "std": float(np.std(gaps)),
        "p10": float(np.percentile(gaps, 10)),
        "p90": float(np.percentile(gaps, 90)),
        "min": int(np.min(gaps)),
        "max": int(np.max(gaps)),
    }

    max_lag = min(400, len(binary) // 3)
    ac = []
    for lag in range(1, max_lag + 1):
        x = binary[:-lag]
        y = binary[lag:]
        if x.std() == 0 or y.std() == 0:
            ac.append(0.0)
        else:
            ac.append(float(np.corrcoef(x, y)[0, 1]))
    threshold = 2 / math.sqrt(len(binary))
    for lag, val in enumerate(ac, start=1):
        if val > threshold:
            out["autocorr_peaks"].append({"lag": lag, "autocorr": val})

    mods = [25, 50, 100]
    pvals = []
    raw_mods = []
    for mod in mods:
        counts = np.bincount(positions % mod, minlength=mod)
        expected = np.full(mod, len(positions) / mod)
        stat, pval = stats.chisquare(counts, expected)
        raw_mods.append(
            {
                "mod": mod,
                "chi2": float(stat),
                "p": float(pval),
                "top_bins": counts.argsort()[-5:][::-1].tolist(),
                "top_counts": counts[counts.argsort()[-5:][::-1]].tolist(),
            }
        )
        pvals.append(pval)
    adj = bh_adjust(pvals)
    for row, q in zip(raw_mods, adj):
        row["q"] = q
    out["mod_tests"] = raw_mods

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].hist(gaps, bins=40, color="#4c72b0")
    axes[0].set_title(f"{label}: gap distribution")
    axes[0].set_xlabel("Spins between target events")
    axes[0].set_ylabel("Count")

    axes[1].plot(range(1, max_lag + 1), ac, color="#dd8452")
    axes[1].axhline(threshold, linestyle="--", color="red", alpha=0.7)
    axes[1].set_title(f"{label}: autocorrelation of event positions")
    axes[1].set_xlabel("Lag")
    axes[1].set_ylabel("Autocorrelation")
    plt.tight_layout()
    path = OUT_DIR / f"{label.lower()}_periodicity.png"
    plt.savefig(path, dpi=160)
    plt.close()
    return out, [str(path)]


def bet_analysis(df: pd.DataFrame, target_col: str, label: str):
    out = {"bet_level_rates": [], "switch_effect": None, "chi2": None}
    plots = []
    if "bet_level" not in df.columns:
        return out, plots

    work = df.copy()
    work["bet_switched"] = work.groupby("account")["bet_level"].diff().fillna(0) != 0
    lvl = work.groupby("bet_level").agg(spins=(target_col, "size"), hits=(target_col, "sum"))
    lvl = lvl[lvl["spins"] >= 200].copy()
    if not lvl.empty:
        lvl["rate"] = lvl["hits"] / lvl["spins"]
        out["bet_level_rates"] = lvl.reset_index().sort_values("rate", ascending=False).to_dict("records")
        contingency = pd.crosstab(work["bet_level"].fillna(-1), work[target_col])
        if contingency.shape[1] == 2:
            chi2, p, _, _ = stats.chi2_contingency(contingency)
            out["chi2"] = {"chi2": float(chi2), "p": float(p)}

        switch = work.groupby("bet_switched").agg(spins=(target_col, "size"), hits=(target_col, "sum"))
        switch["rate"] = switch["hits"] / switch["spins"]
        if True in switch.index and False in switch.index:
            sw_hits = int(switch.loc[True, "hits"])
            sw_n = int(switch.loc[True, "spins"])
            base_p = float(switch.loc[False, "rate"])
            pval = stats.binomtest(sw_hits, sw_n, base_p).pvalue
            out["switch_effect"] = {
                "after_switch_rate": float(switch.loc[True, "rate"]),
                "steady_rate": float(switch.loc[False, "rate"]),
                "lift": float(switch.loc[True, "rate"] / base_p) if base_p else np.nan,
                "p": float(pval),
                "n_after_switch": sw_n,
            }

        top_plot = lvl.reset_index().sort_values("bet_level")
        plt.figure(figsize=(10, 4.5))
        sns.barplot(data=top_plot, x="bet_level", y="rate", color="#55a868")
        plt.title(f"{label}: target rate by bet level")
        plt.xlabel("Bet level")
        plt.ylabel("Target rate")
        plt.tight_layout()
        path = OUT_DIR / f"{label.lower()}_bet.png"
        plt.savefig(path, dpi=160)
        plt.close()
        plots.append(str(path))
    return out, plots


def drought_analysis(df: pd.DataFrame, target_col: str, label: str, name: str):
    drought_col = f"drought_{name}"
    base_rate = df[target_col].mean()
    hazard_rows = []
    pvals = []
    grouped = df.groupby(drought_col)[target_col].agg(["size", "sum"]).reset_index()
    grouped = grouped[grouped["size"] >= 100]
    for _, row in grouped.iterrows():
        rate = row["sum"] / row["size"]
        pval = stats.binomtest(int(row["sum"]), int(row["size"]), base_rate).pvalue
        hazard_rows.append(
            {
                "drought": int(row[drought_col]),
                "n": int(row["size"]),
                "rate": float(rate),
                "baseline": float(base_rate),
                "lift": float(rate / base_rate) if base_rate else np.nan,
                "p": float(pval),
            }
        )
        pvals.append(pval)
    adj = bh_adjust(pvals)
    for row, q in zip(hazard_rows, adj):
        row["q"] = q

    gaps = df.attrs.get(f"gaps_{name}", [])
    geom_test = None
    if gaps:
        p = base_rate
        bins = [(1, 5), (6, 10), (11, 20), (21, 40), (41, 80), (81, 999999)]
        obs = []
        exp = []
        gaps_arr = np.array(gaps)
        for lo, hi in bins:
            obs.append(int(((gaps_arr >= lo) & (gaps_arr <= hi)).sum()))
            exp_prob = sum(((1 - p) ** (k - 1)) * p for k in range(lo, hi + 1 if hi < 999999 else lo + 5000))
            exp.append(exp_prob * len(gaps))
        obs = np.array(obs)
        exp = np.array(exp)
        exp[exp < 1e-9] = 1e-9
        stat, pval = stats.chisquare(obs, exp * (obs.sum() / exp.sum()))
        geom_test = {"chi2": float(stat), "p": float(pval), "mean_gap": float(np.mean(gaps)), "var_gap": float(np.var(gaps))}

    plt.figure(figsize=(10, 4.5))
    gap_hist = df.attrs.get(f"gaps_{name}", [])
    if gap_hist:
        plt.hist(gap_hist, bins=40, color="#c44e52")
    plt.title(f"{label}: drought / gap distribution")
    plt.xlabel("Gap length")
    plt.ylabel("Count")
    plt.tight_layout()
    path = OUT_DIR / f"{label.lower()}_drought.png"
    plt.savefig(path, dpi=160)
    plt.close()

    return {"hazard": hazard_rows, "geometric_fit": geom_test}, [str(path)]


def transition_analysis(df: pd.DataFrame, target_col: str, label: str):
    out = {"matrix_p": None, "notable_transitions": [], "next5_signals": []}
    plots = []
    curr = df["event_label"].iloc[:-1].reset_index(drop=True)
    nxt = df["event_label"].iloc[1:].reset_index(drop=True)
    matrix = pd.crosstab(curr, nxt, normalize="index")
    chi2, p, _, _ = stats.chi2_contingency(pd.crosstab(curr, nxt))
    out["matrix_p"] = {"chi2": float(chi2), "p": float(p)}

    keep_rows = [r for r in matrix.index if curr.value_counts().get(r, 0) >= 100]
    target_next = future_hit_within_k(df[target_col], 1)
    target_next5 = future_hit_within_k(df[target_col], 5)
    base_next = target_next.mean()
    base_next5 = target_next5.mean()
    pvals = []
    rows = []
    for event in keep_rows:
        mask = df["event_label"] == event
        k = int(target_next[mask].sum())
        n = int(mask.sum())
        pval = stats.binomtest(k, n, base_next, alternative="greater").pvalue
        rows.append(
            {
                "from_event": event,
                "n": n,
                "next1_rate": float(target_next[mask].mean()),
                "baseline_next1": float(base_next),
                "lift_next1": float(target_next[mask].mean() / base_next) if base_next else np.nan,
                "p": float(pval),
            }
        )
        pvals.append(pval)
    adj = bh_adjust(pvals)
    for row, q in zip(rows, adj):
        row["q"] = q
    out["notable_transitions"] = sorted(rows, key=lambda x: (x["p"], -x["lift_next1"]))[:12]

    pvals5 = []
    rows5 = []
    for event in keep_rows:
        mask = df["event_label"] == event
        k = int(target_next5[mask].sum())
        n = int(mask.sum())
        pval = stats.binomtest(k, n, base_next5, alternative="greater").pvalue
        rows5.append(
            {
                "from_event": event,
                "n": n,
                "next5_rate": float(target_next5[mask].mean()),
                "baseline_next5": float(base_next5),
                "lift_next5": float(target_next5[mask].mean() / base_next5) if base_next5 else np.nan,
                "p": float(pval),
            }
        )
        pvals5.append(pval)
    adj5 = bh_adjust(pvals5)
    for row, q in zip(rows5, adj5):
        row["q"] = q
    out["next5_signals"] = sorted(rows5, key=lambda x: (x["p"], -x["lift_next5"]))[:12]

    top = matrix.loc[keep_rows].copy()
    top = top[[c for c in top.columns if c in keep_rows or c in ["T_ACC", "T_SPN"]]]
    plt.figure(figsize=(12, 6))
    sns.heatmap(top, cmap="Blues")
    plt.title(f"{label}: transition matrix (current event -> next event)")
    plt.tight_layout()
    path = OUT_DIR / f"{label.lower()}_transitions.png"
    plt.savefig(path, dpi=160)
    plt.close()
    plots.append(str(path))
    return out, plots


def reel_index_analysis(df: pd.DataFrame, target_col: str, label: str, target_symbol: str):
    out = {"available_rows": 0, "target_indices": {}, "signals": [], "cycle_summary": None}
    plots = []
    idx_cols = [c for c in ["r1_idx", "r2_idx", "r3_idx"] if c in df.columns]
    if len(idx_cols) < 3:
        return out, plots
    work = df.dropna(subset=idx_cols).copy()
    out["available_rows"] = len(work)
    if work.empty:
        return out, plots

    target_rows = work[work[target_col]].copy()
    if target_rows.empty:
        return out, plots
    for col in idx_cols:
        mode = target_rows[col].mode(dropna=True)
        if not mode.empty:
            out["target_indices"][col] = int(mode.iloc[0])

    prev = work.groupby("account")[idx_cols].shift(1)
    base_rate = work[target_col].mean()
    pvals = []
    rows = []
    for col in idx_cols:
        tgt = out["target_indices"].get(col)
        if tgt is None:
            continue
        match = prev[col] == tgt
        if match.sum() < 100:
            continue
        hits = work.loc[match.fillna(False), target_col]
        pval = stats.binomtest(int(hits.sum()), int(len(hits)), base_rate, alternative="greater").pvalue
        rows.append(
            {
                "signal": f"prev {col} == target_idx {tgt}",
                "n": int(len(hits)),
                "rate": float(hits.mean()),
                "baseline": float(base_rate),
                "lift": float(hits.mean() / base_rate) if base_rate else np.nan,
                "p": float(pval),
            }
        )
        pvals.append(pval)
    adj = bh_adjust(pvals)
    for row, q in zip(rows, adj):
        row["q"] = q
    out["signals"] = sorted(rows, key=lambda x: (x["p"], -x["lift"]))

    step_counts = {}
    for col in idx_cols:
        diffs = work.groupby("account")[col].diff().dropna()
        vc = diffs.value_counts(normalize=True).head(5)
        step_counts[col] = {str(int(k)): float(v) for k, v in vc.items()}
    out["cycle_summary"] = step_counts

    plt.figure(figsize=(10, 4.5))
    for col in idx_cols:
        sns.kdeplot(data=target_rows, x=col, label=col, fill=False)
    plt.title(f"{label}: reel-index density on target spins")
    plt.tight_layout()
    path = OUT_DIR / f"{label.lower()}_reel_idx.png"
    plt.savefig(path, dpi=160)
    plt.close()
    plots.append(str(path))
    return out, plots


def df_preview(df: pd.DataFrame, n=5):
    cols = list(df.columns)
    sample = df.head(n).replace({np.nan: None}).to_dict(orient="records")
    return cols, sample


def serialize(obj):
    if isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(type(obj).__name__)


def main():
    raw, df = load_all_spin_history()

    dupes = raw.groupby(["account", "seq"]).size().reset_index(name="count")
    dupes = dupes[dupes["count"] > 1].sort_values(["account", "seq"])

    step1_cols, step1_sample = df_preview(df)
    overview = {
        "files_scanned": sorted(str(p.relative_to(ROOT)) for p in DATA_DIR.rglob("spin_history*.csv")),
        "raw_rows_loaded": int(len(raw)),
        "deduped_rows": int(len(df)),
        "duplicate_account_seq_pairs": int(len(dupes)),
        "accounts": df["account"].value_counts().to_dict(),
        "columns": step1_cols,
        "sample_rows": step1_sample,
        "triple_counts": {
            "Triple Accumulation": int(df["is_acc"].sum()),
            "Triple Spins": int(df["is_spn"].sum()),
        },
    }

    results = {"step1_overview": overview, "targets": {}, "plots": []}

    add_drought_features(df, "is_acc", "acc")
    add_drought_features(df, "is_spn", "spn")

    for key, meta in TARGETS.items():
        target_col = "is_acc" if key == "ACC" else "is_spn"
        drought_name = "acc" if key == "ACC" else "spn"
        sequence, plots_a = sequence_analysis(df, target_col, key)
        periodicity, plots_b = periodicity_analysis(df, target_col, key)
        bet, plots_c = bet_analysis(df, target_col, key)
        drought, plots_d = drought_analysis(df, target_col, key, drought_name)
        transition, plots_e = transition_analysis(df, target_col, key)
        reel, plots_f = reel_index_analysis(df, target_col, key, meta["symbol"])
        results["targets"][key] = {
            "title": meta["title"],
            "n_events": int(df[target_col].sum()),
            "baseline_rate": float(df[target_col].mean()),
            "A_sequence": sequence,
            "B_periodicity": periodicity,
            "C_bet": bet,
            "D_drought": drought,
            "E_transition": transition,
            "F_reel_index": reel,
        }
        results["plots"].extend(plots_a + plots_b + plots_c + plots_d + plots_e + plots_f)

    json_path = OUT_DIR / "acc_spn_analysis.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=serialize)

    md_lines = []
    md_lines.append("# ACC / SPN Pattern Analysis\n")
    md_lines.append("## Step 1\n")
    md_lines.append(f"- Total deduplicated spins: {overview['deduped_rows']:,}")
    md_lines.append(f"- Raw loaded rows: {overview['raw_rows_loaded']:,}")
    md_lines.append(f"- Duplicate `(account, seq)` pairs found and removed: {overview['duplicate_account_seq_pairs']:,}")
    md_lines.append(f"- Accounts: {overview['accounts']}")
    md_lines.append(f"- Triple Accumulation events: {overview['triple_counts']['Triple Accumulation']:,}")
    md_lines.append(f"- Triple Spins events: {overview['triple_counts']['Triple Spins']:,}")
    md_lines.append("")
    md_lines.append("### Columns")
    for col in overview["columns"]:
        md_lines.append(f"- `{col}`")
    md_lines.append("")
    md_lines.append("### Sample Rows")
    md_lines.append("```json")
    md_lines.append(json.dumps(overview["sample_rows"], indent=2, default=serialize))
    md_lines.append("```")

    for key in ["ACC", "SPN"]:
        tgt = results["targets"][key]
        md_lines.append(f"\n## {tgt['title']}\n")
        md_lines.append(f"- Events: {tgt['n_events']:,}")
        md_lines.append(f"- Baseline per-spin rate: {tgt['baseline_rate']:.4%}")

        md_lines.append("\n### A) Sequence")
        top_patterns = tgt["A_sequence"]["top_patterns"][:8]
        if top_patterns:
            for row in top_patterns:
                sig = " raw p<0.05" if row["p"] < 0.05 else ""
                md_lines.append(
                    f"- tail-{row['window_tail']} `{row['pattern']}`: {row['obs_rate']:.2%} vs baseline {row['base_rate']:.2%}, p={row['p']:.4g}, q={row['q']:.4g}{sig}"
                )
        practical = tgt["A_sequence"]["practical_signals"][:6]
        if practical:
            md_lines.append("Practical next-5-spin signals:")
            for row in practical:
                sig = " raw p<0.05" if row["p"] < 0.05 else ""
                md_lines.append(
                    f"- after `{row['signal']}`: next-5 target chance {row['next5_rate']:.2%} vs baseline {row['baseline_next5']:.2%}, lift {row['lift']:.2f}x, p={row['p']:.4g}, q={row['q']:.4g}{sig}"
                )

        md_lines.append("\n### B) Periodicity")
        gs = tgt["B_periodicity"]["gap_summary"]
        md_lines.append(
            f"- gap mean {gs.get('mean', float('nan')):.2f}, median {gs.get('median', float('nan')):.2f}, std {gs.get('std', float('nan')):.2f}, p10 {gs.get('p10', float('nan')):.2f}, p90 {gs.get('p90', float('nan')):.2f}"
        )
        for row in tgt["B_periodicity"]["mod_tests"]:
            sig = " raw p<0.05" if row["p"] < 0.05 else ""
            md_lines.append(f"- mod {row['mod']}: p={row['p']:.4g}, q={row['q']:.4g}{sig}, hottest bins={row['top_bins'][:3]}")

        md_lines.append("\n### C) Bet")
        if tgt["C_bet"]["chi2"]:
            md_lines.append(f"- bet level chi-square p={tgt['C_bet']['chi2']['p']:.4g}")
        if tgt["C_bet"]["switch_effect"]:
            sw = tgt["C_bet"]["switch_effect"]
            sig = " raw p<0.05" if sw["p"] < 0.05 else ""
            md_lines.append(
                f"- after bet switch: {sw['after_switch_rate']:.2%} vs steady {sw['steady_rate']:.2%}, lift {sw['lift']:.2f}x, p={sw['p']:.4g}{sig}"
            )
        for row in tgt["C_bet"]["bet_level_rates"][:6]:
            md_lines.append(f"- bet level {int(row['bet_level'])}: {row['rate']:.2%} over {int(row['spins'])} spins")

        md_lines.append("\n### D) Drought")
        gf = tgt["D_drought"]["geometric_fit"]
        if gf:
            sig = " raw p<0.05" if gf["p"] < 0.05 else ""
            md_lines.append(
                f"- geometric gap fit: p={gf['p']:.4g}{sig}, mean gap {gf['mean_gap']:.2f}, variance {gf['var_gap']:.2f}"
            )
        for row in tgt["D_drought"]["hazard"][:10]:
            if row["p"] < 0.05:
                md_lines.append(
                    f"- drought {row['drought']}: hit rate {row['rate']:.2%} vs baseline {row['baseline']:.2%}, lift {row['lift']:.2f}x, p={row['p']:.4g}, q={row['q']:.4g}"
                )

        md_lines.append("\n### E) Transition")
        md_lines.append(f"- overall transition matrix chi-square p={tgt['E_transition']['matrix_p']['p']:.4g}")
        for row in tgt["E_transition"]["notable_transitions"][:8]:
            sig = " raw p<0.05" if row["p"] < 0.05 else ""
            md_lines.append(
                f"- after `{row['from_event']}` next-spin target chance {row['next1_rate']:.2%} vs baseline {row['baseline_next1']:.2%}, lift {row['lift_next1']:.2f}x, p={row['p']:.4g}, q={row['q']:.4g}{sig}"
            )
        for row in tgt["E_transition"]["next5_signals"][:6]:
            sig = " raw p<0.05" if row["p"] < 0.05 else ""
            md_lines.append(
                f"- after `{row['from_event']}` next-5 target chance {row['next5_rate']:.2%} vs baseline {row['baseline_next5']:.2%}, lift {row['lift_next5']:.2f}x, p={row['p']:.4g}, q={row['q']:.4g}{sig}"
            )

        md_lines.append("\n### F) Reel / Position")
        md_lines.append(f"- rows with reel indices available: {tgt['F_reel_index']['available_rows']:,}")
        md_lines.append(f"- target index modes: {tgt['F_reel_index']['target_indices']}")
        for row in tgt["F_reel_index"]["signals"][:6]:
            sig = " raw p<0.05" if row["p"] < 0.05 else ""
            md_lines.append(
                f"- `{row['signal']}`: target chance {row['rate']:.2%} vs baseline {row['baseline']:.2%}, lift {row['lift']:.2f}x, p={row['p']:.4g}, q={row['q']:.4g}{sig}"
            )

    md_lines.append("\n## Plot Files\n")
    for plot in results["plots"]:
        md_lines.append(f"- `{Path(plot).name}`")

    report_path = OUT_DIR / "ACC_SPN_REPORT.md"
    report_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
