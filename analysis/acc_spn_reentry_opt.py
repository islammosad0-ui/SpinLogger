import json
import math
from pathlib import Path

import pandas as pd

from acc_spn_hotzone_scorer import add_features, fit_holdout_scores, gap_signal, load_data


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "analysis" / "output_acc_spn_reentry"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def episode_backtest(df: pd.DataFrame, signal: pd.Series, target_col: str, window_len: int, cooldown: int = 0, entry_only: bool = False):
    signal = signal.fillna(False).astype(bool)
    total_events = int(df[target_col].sum())
    windows = 0
    bet_spins = 0
    catches = 0

    for _, sdf in df.groupby("session_id"):
        idxs = list(sdf.index)
        active = False
        left = 0
        cool = 0
        prev_sig = False
        for pos in idxs:
            sig = bool(signal.at[pos])
            if active:
                left -= 1
                bet_spins += 1
                if df.at[pos, target_col]:
                    catches += 1
                    active = False
                    left = 0
                    cool = cooldown
                elif left <= 0:
                    active = False
                    cool = cooldown
            else:
                if cool > 0:
                    cool -= 1
                trigger = sig and cool == 0
                if entry_only:
                    trigger = trigger and (not prev_sig)
                if trigger:
                    active = True
                    left = window_len
                    windows += 1
            prev_sig = sig

    return {
        "windows": windows,
        "bet_spins": bet_spins,
        "caught_events": catches,
        "capture_rate": (catches / total_events) if total_events else 0.0,
        "spins_per_hit": (bet_spins / catches) if catches else math.inf,
        "window_hit_rate": (catches / windows) if windows else 0.0,
    }


def build_signals(df: pd.DataFrame):
    score_acc, _, _, _ = fit_holdout_scores(df, "ACC", "is_acc")
    score_spn, _, _, _ = fit_holdout_scores(df, "SPN", "is_spn")

    acc_q950 = score_acc >= score_acc.dropna().quantile(0.95)
    acc_q975 = score_acc >= score_acc.dropna().quantile(0.975)
    spn_q950 = score_spn >= score_spn.dropna().quantile(0.95)
    spn_q990 = score_spn >= score_spn.dropna().quantile(0.99)

    signals = {
        "ACC": {
            "acc_q950": {"signal": acc_q950, "window_len": 2},
            "acc_q975": {"signal": acc_q975, "window_len": 3},
            "acc_hot_band1": {
                "signal": (df["gap_acc"] >= 125) & (df["gap_acc"] < 175) & (df["gap_spn"] >= 50) & (df["gap_spn"] < 110),
                "window_len": 2,
            },
        },
        "SPN": {
            "spn_q950": {"signal": spn_q950, "window_len": 4},
            "spn_q990": {"signal": spn_q990, "window_len": 2},
            "spn_q950_gaphot": {"signal": spn_q950 & gap_signal(df, "SPN", "hot"), "window_len": 5},
            "spn_hot_band1": {
                "signal": (df["gap_spn"] >= 110) & (df["gap_spn"] < 220) & (df["gap_acc"] >= 50) & (df["gap_acc"] < 100),
                "window_len": 2,
            },
        },
    }
    return signals


def main():
    df = add_features(load_data())
    signals = build_signals(df)

    report = {
        "overview": {
            "rows": int(len(df)),
            "sessions": int(df["session_id"].nunique()),
            "accounts": df["account"].value_counts().to_dict(),
        },
        "targets": {},
    }

    for key, bundle in signals.items():
        target_col = "is_acc" if key == "ACC" else "is_spn"
        rows = []
        best = {}
        for name, cfg in bundle.items():
            local = []
            for entry_only in [False, True]:
                for cooldown in [0, 2, 5, 10]:
                    res = episode_backtest(df, cfg["signal"], target_col, cfg["window_len"], cooldown=cooldown, entry_only=entry_only)
                    row = {
                        "signal": name,
                        "window_len": cfg["window_len"],
                        "entry_only": entry_only,
                        "cooldown": cooldown,
                        **res,
                    }
                    rows.append(row)
                    if row["caught_events"] >= 10:
                        local.append(row)
            if local:
                best[name] = min(local, key=lambda r: (r["spins_per_hit"], -r["capture_rate"]))
        report["targets"][key] = {
            "all_results": rows,
            "best_per_signal": best,
        }

    json_path = OUT_DIR / "reentry_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = ["# ACC / SPN Re-entry Optimization", ""]
    lines.append(f"- Rows: {report['overview']['rows']:,}")
    lines.append(f"- Sessions: {report['overview']['sessions']}")
    lines.append(f"- Accounts: {report['overview']['accounts']}")

    for key in ["ACC", "SPN"]:
        lines.append("")
        lines.append(f"## {key}")
        for name, row in report["targets"][key]["best_per_signal"].items():
            lines.append(
                f"- `{name}` best = window {row['window_len']}, entry_only={row['entry_only']}, cooldown={row['cooldown']} -> spins/hit {row['spins_per_hit']:.1f}, capture {row['capture_rate']:.1%}, caught {row['caught_events']}, win-hit {row['window_hit_rate']:.1%}"
            )

    md_path = OUT_DIR / "REENTRY_REPORT.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
