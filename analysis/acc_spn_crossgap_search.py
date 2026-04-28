import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from acc_spn_hotzone_scorer import TARGETS, add_features, load_data, future_hit_within_k


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "analysis" / "output_acc_spn_crossgap"
OUT_DIR.mkdir(parents=True, exist_ok=True)
sns.set_theme(style="whitegrid", font_scale=0.9)


@dataclass
class Candidate:
    name: str
    mask: pd.Series


def episode_backtest(df: pd.DataFrame, signal: pd.Series, target_col: str, window_len: int):
    signal = signal.fillna(False).astype(bool)
    total_events = int(df[target_col].sum())
    windows = 0
    bet_spins = 0
    catches = 0

    for _, sdf in df.groupby("session_id"):
        idxs = list(sdf.index)
        active = False
        spins_left = 0
        for pos in idxs:
            if active:
                spins_left -= 1
                bet_spins += 1
                if df.at[pos, target_col]:
                    catches += 1
                    active = False
                    spins_left = 0
                elif spins_left <= 0:
                    active = False

            if (not active) and signal.at[pos]:
                active = True
                spins_left = window_len
                windows += 1

    return {
        "windows": windows,
        "bet_spins": bet_spins,
        "caught_events": catches,
        "capture_rate": (catches / total_events) if total_events else 0.0,
        "spins_per_hit": (bet_spins / catches) if catches else math.inf,
        "window_hit_rate": (catches / windows) if windows else 0.0,
    }


def build_edges(series: pd.Series, extras: list[int]):
    qs = [0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0]
    vals = set()
    for q in qs:
        try:
            vals.add(int(series.quantile(q)))
        except Exception:
            pass
    for x in extras:
        vals.add(int(x))
    vals.add(int(series.min()))
    vals.add(int(series.max()) + 1)
    edges = sorted(vals)
    clean = [edges[0]]
    for x in edges[1:]:
        if x > clean[-1]:
            clean.append(x)
    return clean


def interval_masks(series: pd.Series, edges: list[int], max_bins_width: int = 3):
    out = []
    for i in range(len(edges) - 1):
        for j in range(i + 1, min(len(edges), i + 1 + max_bins_width)):
            lo = edges[i]
            hi = edges[j]
            if j == len(edges) - 1:
                mask = (series >= lo) & (series <= hi)
                label = f"[{lo},inf)"
            else:
                mask = (series >= lo) & (series < hi)
                label = f"[{lo},{hi})"
            out.append((label, mask))
    return out


def build_candidates(df: pd.DataFrame, key: str):
    gap_t = df[f"gap_{key.lower()}"]
    other_key = "spn" if key == "ACC" else "acc"
    gap_o = df[f"gap_{other_key}"]

    extras_t = [TARGETS[key]["gap75"], TARGETS[key]["gap90"]]
    extras_o = [TARGETS["SPN"]["gap75"], TARGETS["SPN"]["gap90"]] if key == "ACC" else [TARGETS["ACC"]["gap75"], TARGETS["ACC"]["gap90"]]
    edges_t = build_edges(gap_t, extras_t)
    edges_o = build_edges(gap_o, extras_o)

    masks_t_all = interval_masks(gap_t, edges_t, max_bins_width=2)
    masks_o = interval_masks(gap_o, edges_o, max_bins_width=2)
    median_t = gap_t.quantile(0.5)
    masks_t = [(label, mask) for label, mask in masks_t_all if mask.any() and gap_t[mask].min() >= median_t]

    if "accum_pct" in df.columns:
        high_pct = df["accum_pct"].fillna(-1) >= 80
    else:
        high_pct = pd.Series(False, index=df.index)
    prev_pair = df["prev_pair_any"].fillna(False)
    filters = [
        ("any", pd.Series(True, index=df.index)),
        ("acc80", high_pct),
        ("pair", prev_pair),
    ]

    candidates = []
    for lt, mt in masks_t:
        for lo, mo in masks_o:
            base_name = f"gt{lt}&go{lo}"
            base_mask = mt & mo
            candidates.append(Candidate(base_name, base_mask))
            for fname, fmask in filters[1:]:
                candidates.append(Candidate(f"{base_name}&{fname}", base_mask & fmask))
    return candidates, edges_t, edges_o


def make_heatmap(df: pd.DataFrame, key: str, target_col: str, edges_t, edges_o):
    other_key = "spn" if key == "ACC" else "acc"
    gap_t = df[f"gap_{key.lower()}"]
    gap_o = df[f"gap_{other_key}"]
    future5 = future_hit_within_k(df[target_col], 5)

    rows = []
    for i in range(len(edges_t) - 1):
        for j in range(len(edges_o) - 1):
            lo_t, hi_t = edges_t[i], edges_t[i + 1]
            lo_o, hi_o = edges_o[j], edges_o[j + 1]
            mask_t = (gap_t >= lo_t) & ((gap_t <= hi_t) if i == len(edges_t) - 2 else (gap_t < hi_t))
            mask_o = (gap_o >= lo_o) & ((gap_o <= hi_o) if j == len(edges_o) - 2 else (gap_o < hi_o))
            mask = mask_t & mask_o
            n = int(mask.sum())
            rate = float(future5[mask].mean()) if n else np.nan
            rows.append({"tbin": f"{lo_t}-{hi_t}", "obin": f"{lo_o}-{hi_o}", "n": n, "rate": rate})
    heat = pd.DataFrame(rows).pivot(index="tbin", columns="obin", values="rate")
    annot = pd.DataFrame(rows).pivot(index="tbin", columns="obin", values="n")

    plt.figure(figsize=(10, 7))
    sns.heatmap(heat, cmap="YlOrRd", annot=annot, fmt=".0f")
    plt.title(f"{key}: next-5 hit rate by target-gap x opposite-gap bins")
    plt.xlabel(f"Opposite gap bin ({other_key})")
    plt.ylabel(f"Target gap bin ({key.lower()})")
    plt.tight_layout()
    path = OUT_DIR / f"{key.lower()}_crossgap_heatmap.png"
    plt.savefig(path, dpi=160)
    plt.close()
    return str(path), rows


def search_holdout(df: pd.DataFrame, key: str, target_col: str, candidates: list[Candidate]):
    sessions = df["session_id"].drop_duplicates().tolist()
    thresholds = [0.10, 0.15, 0.20, 0.25, 0.30]
    aggregated = {thr: {"bet_spins": 0, "caught_events": 0, "windows": 0, "picked_rules": []} for thr in thresholds}

    for holdout in sessions:
        train_mask = df["session_id"] != holdout
        test_mask = df["session_id"] == holdout
        if train_mask.sum() < 1000 or test_mask.sum() < 200:
            continue

        train_df = df.loc[train_mask].copy()
        test_df = df.loc[test_mask].copy()
        future = {w: future_hit_within_k(train_df[target_col], w) for w in [2, 3, 4, 5]}

        approx_rows = []
        for cand in candidates:
            mask_train = cand.mask.loc[train_df.index].fillna(False)
            n = int(mask_train.sum())
            if n < 40:
                continue
            for w in [2, 3, 4, 5]:
                rate = float(future[w][mask_train].mean()) if n else 0.0
                if rate <= 0:
                    continue
                approx_rows.append({
                    "name": cand.name,
                    "window_len": w,
                    "approx_sph": w / rate,
                    "train_alerts": n,
                })

        approx_df = pd.DataFrame(approx_rows)
        if approx_df.empty:
            continue

        shortlist = approx_df.sort_values("approx_sph").head(80)
        train_eval = []
        for _, row in shortlist.iterrows():
            cand = next(c for c in candidates if c.name == row["name"])
            res = episode_backtest(train_df, cand.mask.loc[train_df.index], target_col, int(row["window_len"]))
            train_eval.append({
                "name": cand.name,
                "window_len": int(row["window_len"]),
                **res,
            })

        train_eval = sorted(train_eval, key=lambda r: (r["spins_per_hit"], -r["capture_rate"]))
        for thr in thresholds:
            viable = [r for r in train_eval if r["capture_rate"] >= thr and r["caught_events"] >= 10]
            if not viable:
                continue
            best = viable[0]
            cand = next(c for c in candidates if c.name == best["name"])
            test_res = episode_backtest(test_df, cand.mask.loc[test_df.index], target_col, best["window_len"])
            agg = aggregated[thr]
            agg["bet_spins"] += test_res["bet_spins"]
            agg["caught_events"] += test_res["caught_events"]
            agg["windows"] += test_res["windows"]
            agg["picked_rules"].append({
                "session_id": holdout,
                "rule": best["name"],
                "window_len": best["window_len"],
                "train_capture": best["capture_rate"],
                "test_capture": test_res["capture_rate"],
                "test_spins_per_hit": test_res["spins_per_hit"],
            })

    out = {}
    total_events = int(df[target_col].sum())
    for thr, agg in aggregated.items():
        out[str(thr)] = {
            "bet_spins": agg["bet_spins"],
            "caught_events": agg["caught_events"],
            "windows": agg["windows"],
            "capture_rate": (agg["caught_events"] / total_events) if total_events else 0.0,
            "spins_per_hit": (agg["bet_spins"] / agg["caught_events"]) if agg["caught_events"] else math.inf,
            "picked_rules": agg["picked_rules"],
        }
    return out


def global_top_rules(df: pd.DataFrame, key: str, target_col: str, candidates: list[Candidate]):
    future = {w: future_hit_within_k(df[target_col], w) for w in [2, 3, 4, 5]}
    approx_rows = []
    for cand in candidates:
        mask = cand.mask.fillna(False)
        n = int(mask.sum())
        if n < 40:
            continue
        for w in [2, 3, 4, 5]:
            rate = float(future[w][mask].mean()) if n else 0.0
            if rate <= 0:
                continue
            approx_rows.append({
                "rule": cand.name,
                "window_len": w,
                "approx_sph": w / rate,
                "alerts": n,
            })
    approx_df = pd.DataFrame(approx_rows)
    if approx_df.empty:
        return []
    shortlist = approx_df.sort_values("approx_sph").head(120)
    rows = []
    for _, row in shortlist.iterrows():
        cand = next(c for c in candidates if c.name == row["rule"])
        res = episode_backtest(df, cand.mask, target_col, int(row["window_len"]))
        if res["caught_events"] < 10:
            continue
        rows.append({
            "rule": cand.name,
            "window_len": int(row["window_len"]),
            **res,
        })
    return sorted(rows, key=lambda r: (r["spins_per_hit"], -r["capture_rate"]))


def main():
    df = add_features(load_data())
    report = {
        "overview": {
            "rows": int(len(df)),
            "sessions": int(df["session_id"].nunique()),
            "accounts": df["account"].value_counts().to_dict(),
        },
        "targets": {},
        "plots": [],
    }

    for key, meta in TARGETS.items():
        target_col = meta["col"]
        candidates, edges_t, edges_o = build_candidates(df, key)
        heatmap_path, heat_rows = make_heatmap(df, key, target_col, edges_t, edges_o)
        holdout = search_holdout(df, key, target_col, candidates)
        global_best = global_top_rules(df, key, target_col, candidates)
        report["targets"][key] = {
            "heatmap_rows": heat_rows,
            "holdout_search": holdout,
            "global_best": global_best[:40],
        }
        report["plots"].append(heatmap_path)

    json_path = OUT_DIR / "crossgap_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = ["# ACC / SPN Cross-Gap Search", ""]
    lines.append(f"- Rows: {report['overview']['rows']:,}")
    lines.append(f"- Sessions: {report['overview']['sessions']}")
    lines.append(f"- Accounts: {report['overview']['accounts']}")
    for key in ["ACC", "SPN"]:
        tgt = report["targets"][key]
        lines.append("")
        lines.append(f"## {key}")
        lines.append("### Holdout Search")
        for thr, row in tgt["holdout_search"].items():
            lines.append(
                f"- train capture >= {thr}: holdout aggregate spins/hit {row['spins_per_hit']:.1f}, capture {row['capture_rate']:.1%}, caught {row['caught_events']}, windows {row['windows']}"
            )
        lines.append("")
        lines.append("### Global Best")
        for row in tgt["global_best"][:15]:
            lines.append(
                f"- `{row['rule']}` @ {row['window_len']} spins -> spins/hit {row['spins_per_hit']:.1f}, capture {row['capture_rate']:.1%}, caught {row['caught_events']}, win-hit {row['window_hit_rate']:.1%}"
            )

    md_path = OUT_DIR / "CROSSGAP_REPORT.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
