import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from acc_spn_hotzone_scorer import (
    TARGETS,
    add_features,
    fit_holdout_scores,
    gap_signal,
    heuristic_score,
    load_data,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "analysis" / "output_acc_spn_hotzone_opt"
OUT_DIR.mkdir(parents=True, exist_ok=True)
sns.set_theme(style="whitegrid", font_scale=0.9)


def episode_backtest(df: pd.DataFrame, signal: pd.Series, target_col: str, window_len: int):
    signal = signal.fillna(False).astype(bool)
    total_events = int(df[target_col].sum())
    windows = 0
    bet_spins = 0
    catches = 0
    by_session = []

    for session_id, sdf in df.groupby("session_id"):
        idxs = list(sdf.index)
        active = False
        spins_left = 0
        local_windows = 0
        local_bets = 0
        local_hits = 0

        for pos in idxs:
            if active:
                spins_left -= 1
                local_bets += 1
                if df.at[pos, target_col]:
                    local_hits += 1
                    active = False
                    spins_left = 0
                elif spins_left <= 0:
                    active = False

            if (not active) and signal.at[pos]:
                active = True
                spins_left = window_len
                local_windows += 1

        windows += local_windows
        bet_spins += local_bets
        catches += local_hits
        by_session.append({
            "session_id": session_id,
            "windows": local_windows,
            "bet_spins": local_bets,
            "hits": local_hits,
        })

    return {
        "windows": windows,
        "bet_spins": bet_spins,
        "caught_events": catches,
        "capture_rate": (catches / total_events) if total_events else 0.0,
        "spins_per_hit": (bet_spins / catches) if catches else math.inf,
        "window_hit_rate": (catches / windows) if windows else 0.0,
        "session_rows": by_session,
    }


def build_hybrid_signals(df: pd.DataFrame, key: str, score_model: pd.Series):
    heur = heuristic_score(df, key)
    high_pct = df["accum_pct"].fillna(-1) >= 80 if "accum_pct" in df.columns else pd.Series(False, index=df.index)
    prev_pair = df["prev_pair_any"].fillna(False)
    bet_high = df["bet_level"].fillna(-1) >= df["bet_level"].quantile(0.75) if "bet_level" in df.columns else pd.Series(False, index=df.index)
    gap_warm = gap_signal(df, key, "warm")
    gap_hot = gap_signal(df, key, "hot")

    # Heuristic thresholds
    heur_levels = {
        "heur>=2.0": heur >= 2.0,
        "heur>=2.5": heur >= 2.5,
        "heur>=3.0": heur >= 3.0,
        "heur>=3.5": heur >= 3.5,
        "heur>=4.0": heur >= 4.0,
    }

    out = {
        "gap_warm": gap_warm,
        "gap_hot": gap_hot,
        "gap_hot&acc80": gap_hot & high_pct,
        "gap_hot&pair": gap_hot & prev_pair,
        "gap_hot&betHigh": gap_hot & bet_high,
    }
    out.update(heur_levels)

    model_score = score_model.fillna(-1)
    quantiles = [0.90, 0.95, 0.975, 0.99, 0.995]
    valid_scores = model_score[model_score >= 0]
    for q in quantiles:
        if valid_scores.empty:
            continue
        thr = float(valid_scores.quantile(q))
        base = model_score >= thr
        name = f"model_q{int(q*1000):03d}"
        out[name] = base
        out[f"{name}&gap_hot"] = base & gap_hot
        out[f"{name}&acc80"] = base & high_pct
        out[f"{name}&pair"] = base & prev_pair
        out[f"{name}&gap_hot&acc80"] = base & gap_hot & high_pct

    return out


def pareto_frontier(rows):
    rows = sorted(rows, key=lambda r: (r["spins_per_hit"], -r["capture_rate"]))
    frontier = []
    best_capture = -1.0
    for row in rows:
        if row["capture_rate"] > best_capture:
            frontier.append(row)
            best_capture = row["capture_rate"]
    return frontier


def optimize_target(df: pd.DataFrame, key: str, target_col: str):
    score_model, _, _, top_features = fit_holdout_scores(df, key, target_col)
    signals = build_hybrid_signals(df, key, score_model)

    candidates = []
    for signal_name, signal in signals.items():
        for window_len in [2, 3, 4, 5]:
            res = episode_backtest(df, signal, target_col, window_len)
            if res["caught_events"] < 10:
                continue
            candidates.append({
                "signal": signal_name,
                "window_len": window_len,
                "windows": res["windows"],
                "bet_spins": res["bet_spins"],
                "caught_events": res["caught_events"],
                "capture_rate": res["capture_rate"],
                "spins_per_hit": res["spins_per_hit"],
                "window_hit_rate": res["window_hit_rate"],
            })

    candidates = sorted(candidates, key=lambda r: (r["spins_per_hit"], -r["capture_rate"]))
    frontier = pareto_frontier(candidates)

    # Pick a few practical operating points.
    picks = {}
    for min_capture in [0.10, 0.15, 0.20, 0.25, 0.30]:
        viable = [r for r in candidates if r["capture_rate"] >= min_capture]
        if viable:
            picks[f"min_capture_{int(min_capture*100)}"] = viable[0]

    # Plot frontier.
    if frontier:
        plt.figure(figsize=(8, 5))
        xs = [r["capture_rate"] * 100 for r in candidates]
        ys = [r["spins_per_hit"] for r in candidates]
        plt.scatter(xs, ys, alpha=0.25, s=20, color="#4c72b0")
        fxs = [r["capture_rate"] * 100 for r in frontier]
        fys = [r["spins_per_hit"] for r in frontier]
        plt.plot(fxs, fys, color="#dd8452", marker="o")
        for r in frontier[:8]:
            plt.annotate(
                f"{r['signal']}@{r['window_len']}",
                (r["capture_rate"] * 100, r["spins_per_hit"]),
                fontsize=8,
                alpha=0.8,
            )
        plt.xlabel("Capture Rate (%)")
        plt.ylabel("Spins Per Hit")
        plt.title(f"{key}: strategy frontier")
        plt.tight_layout()
        plot_path = OUT_DIR / f"{key.lower()}_frontier.png"
        plt.savefig(plot_path, dpi=160)
        plt.close()
    else:
        plot_path = None

    return {
        "top_features": top_features,
        "best_by_spins_per_hit": candidates[:20],
        "frontier": frontier,
        "practical_picks": picks,
    }, str(plot_path) if plot_path else None


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
        result, plot_path = optimize_target(df, key, meta["col"])
        report["targets"][key] = result
        if plot_path:
            report["plots"].append(plot_path)

    json_path = OUT_DIR / "hotzone_opt_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = ["# ACC / SPN Hot Zone Optimization", ""]
    lines.append(f"- Rows: {report['overview']['rows']:,}")
    lines.append(f"- Sessions: {report['overview']['sessions']}")
    lines.append(f"- Accounts: {report['overview']['accounts']}")

    for key in ["ACC", "SPN"]:
        tgt = report["targets"][key]
        lines.append("")
        lines.append(f"## {key}")
        lines.append("- Practical picks:")
        for label, row in tgt["practical_picks"].items():
            lines.append(
                f"- {label}: `{row['signal']}` with {row['window_len']}-spin window -> spins/hit {row['spins_per_hit']:.1f}, capture {row['capture_rate']:.1%}, caught {row['caught_events']}, window hit {row['window_hit_rate']:.1%}"
            )
        lines.append("")
        lines.append("- Best by spins/hit:")
        for row in tgt["best_by_spins_per_hit"][:12]:
            lines.append(
                f"- `{row['signal']}` @ {row['window_len']} spins -> spins/hit {row['spins_per_hit']:.1f}, capture {row['capture_rate']:.1%}, caught {row['caught_events']}, windows {row['windows']}, win-hit {row['window_hit_rate']:.1%}"
            )

    md_path = OUT_DIR / "HOTZONE_OPT_REPORT.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
