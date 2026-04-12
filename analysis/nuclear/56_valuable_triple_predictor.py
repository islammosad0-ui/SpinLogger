"""
56_valuable_triple_predictor.py

Move 1: richer models on the 213-row IL2CPP-enriched dataset, targeting
ONLY the valuable triples (accumulation + spins). Goldsack / coin / attack /
steal / shield triples are discarded — they are either farmable elsewhere
(goldSack, coin) or secondary (attack/steal/shield).

Valuable triple definition: is_triple == True AND reel_1 in {accumulation, spins}.

On the 213-row enriched set, the 7 observed valuable triples are all either
(r1,r2,r3)_idx = (6,6,6) [spins] or (8,8,8) [accumulation]. Base rate = 7/213
= 3.29%. Narrower target than "any triple" (35%), with a lower base rate that
leaves more room for a separating model to clear a lift threshold.

Features (strictly idx-based, no symbol stream):
  - Same-spin: r1_idx, r3_idx (as one-hot). r2_idx is WITHHELD because it
    trivially discloses the target for the valuable set (if r2_idx in {6,8}
    the target is always 1 when the other reels match). Same-spin predictor
    is the "tell on the non-payline reels" the user asked for.
  - Lag features: r{1,2,3}_idx at N-1, N-2, N-3 (gap-aware, masked when the
    seq gap > 1)
  - Run-length: spins_since_any_triple, spins_since_val_triple
  - Interaction pairs: (r1_idx, r3_idx) joint one-hot

Models:
  - Base rate (null)
  - L2-regularized logistic regression (sklearn)
  - Gradient boosted trees (sklearn)
  - Random forest (sklearn)
  - Symbol-stream baseline (to prove idx > symbol — or disprove it)

Cross-validation: walk-forward temporal. For each i from warmup..N-1,
train on [0, i), predict i. This is LOOCV-style forward-only prediction;
no future leakage. Aggregate predictions then score once at the end.

Decision rule:
  - +10pp lift on top-quartile precision -> SAVE as bet-sizing candidate
  - +5pp lift -> note but don't ship; try scanner v2 first
  - <+5pp after exhaustive search -> proof we need more data (Move 2)

Also runs a power-boosted baseline on the full 5,393-row symbol-only dataset
so we can tell if the bottleneck is feature quality or sample size.

Usage:
  python analysis/nuclear/56_valuable_triple_predictor.py
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# Line-buffered stdout so progress is visible in real time (the default Windows
# Python buffering eats all output until process exit).
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass


def log(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    SKLEARN_OK = True
except Exception as e:
    log(f"sklearn unavailable: {e}")
    SKLEARN_OK = False

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data" / "Ahmed" / "spin_history_Ahmed_enriched.csv"


# -------------------------------------------------------------- data loading


def load_enriched() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    enriched = df.dropna(subset=["r1_idx", "r2_idx", "r3_idx"]).copy()
    enriched = enriched.sort_values("seq").reset_index(drop=True)
    for c in ["r1_idx", "r2_idx", "r3_idx"]:
        enriched[c] = enriched[c].astype(int)
    return enriched


def load_full_symbol() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    df = df.sort_values("seq").reset_index(drop=True)
    return df


def make_target_valuable(df: pd.DataFrame) -> np.ndarray:
    return (
        (df["is_triple"] == True)
        & (df["reel_1"].isin(["accumulation", "spins"]))
    ).astype(int).to_numpy()


def make_target_any_triple(df: pd.DataFrame) -> np.ndarray:
    return (df["is_triple"] == True).astype(int).to_numpy()


# -------------------------------------------------------------- features


IDX_VOCAB = list(range(9))  # strip positions 0..8


def one_hot_idx(values: np.ndarray) -> np.ndarray:
    """Return (n, 9) one-hot. NaN / -1 encodes the mask row (all zeros)."""
    n = len(values)
    out = np.zeros((n, 9), dtype=np.float32)
    for i, v in enumerate(values):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        iv = int(v)
        if 0 <= iv <= 8:
            out[i, iv] = 1.0
    return out


def build_lag_features(
    enriched: pd.DataFrame,
    max_lag: int = 3,
) -> tuple[np.ndarray, list[str]]:
    """Gap-aware lag features on r1/r2/r3 idx. When gap>1 from previous row,
    that lag slot is masked to zeros (as if 'missing')."""
    seq = enriched["seq"].to_numpy()
    r1 = enriched["r1_idx"].to_numpy()
    r2 = enriched["r2_idx"].to_numpy()
    r3 = enriched["r3_idx"].to_numpy()
    n = len(enriched)

    feats: list[np.ndarray] = []
    names: list[str] = []
    for lag in range(1, max_lag + 1):
        for reel, vals in (("r1", r1), ("r2", r2), ("r3", r3)):
            shifted = np.full(n, np.nan)
            for i in range(lag, n):
                # only apply lag when the stream is unbroken across `lag` steps
                if seq[i] - seq[i - lag] == lag:
                    shifted[i] = vals[i - lag]
            oh = one_hot_idx(shifted)
            feats.append(oh)
            names.extend([f"{reel}_idx_lag{lag}_eq{k}" for k in IDX_VOCAB])
    return np.concatenate(feats, axis=1), names


def build_same_spin_nonpayline(
    enriched: pd.DataFrame,
) -> tuple[np.ndarray, list[str]]:
    """Same-spin features using only r1_idx and r3_idx (non-payline reels).
    This is the 'tell on the other two' formulation."""
    r1 = enriched["r1_idx"].to_numpy()
    r3 = enriched["r3_idx"].to_numpy()
    oh1 = one_hot_idx(r1)
    oh3 = one_hot_idx(r3)
    # interaction pair (r1_idx, r3_idx) -> 81 cells
    n = len(enriched)
    pair = np.zeros((n, 81), dtype=np.float32)
    for i in range(n):
        a, b = int(r1[i]), int(r3[i])
        pair[i, a * 9 + b] = 1.0
    names = (
        [f"r1_idx_eq{k}" for k in IDX_VOCAB]
        + [f"r3_idx_eq{k}" for k in IDX_VOCAB]
        + [f"r1xr3_{a}_{b}" for a in IDX_VOCAB for b in IDX_VOCAB]
    )
    return np.concatenate([oh1, oh3, pair], axis=1), names


def build_runlength(
    enriched: pd.DataFrame,
    target: np.ndarray,
) -> tuple[np.ndarray, list[str]]:
    """Spins-since counters. NOTE: only use target values strictly before
    the current row (walk-forward), so this is leakage-safe when used with
    temporal CV. We compute them using the same method for train and test
    because we just look backward at each row."""
    any_tr = (enriched["is_triple"] == True).to_numpy().astype(int)
    val_tr = target.astype(int)
    n = len(enriched)

    since_any = np.full(n, np.nan)
    since_val = np.full(n, np.nan)
    last_any = None
    last_val = None
    for i in range(n):
        since_any[i] = (i - last_any) if last_any is not None else 50
        since_val[i] = (i - last_val) if last_val is not None else 200
        if any_tr[i]:
            last_any = i
        if val_tr[i]:
            last_val = i
    feats = np.stack([since_any, since_val], axis=1).astype(np.float32)
    return feats, ["spins_since_any_triple", "spins_since_val_triple"]


def build_feature_set(
    enriched: pd.DataFrame,
    target: np.ndarray,
    include_lag: bool = True,
    include_same_spin: bool = True,
    include_runlen: bool = True,
) -> tuple[np.ndarray, list[str]]:
    parts: list[np.ndarray] = []
    names: list[str] = []
    if include_lag:
        X, n = build_lag_features(enriched, max_lag=3)
        parts.append(X)
        names += n
    if include_same_spin:
        X, n = build_same_spin_nonpayline(enriched)
        parts.append(X)
        names += n
    if include_runlen:
        X, n = build_runlength(enriched, target)
        parts.append(X)
        names += n
    if not parts:
        return np.zeros((len(enriched), 0), dtype=np.float32), []
    return np.concatenate(parts, axis=1).astype(np.float32), names


def build_symbol_features(df: pd.DataFrame, max_lag: int = 3) -> np.ndarray:
    """Baseline: lag features over (r1, r2, r3) symbols (1..6) from the
    full 5,393-row dataset. Gap-aware (all seq are dense at 1)."""
    n = len(df)
    r1 = df["r1"].to_numpy()
    r2 = df["r2"].to_numpy()
    r3 = df["r3"].to_numpy()
    parts = []
    for lag in range(1, max_lag + 1):
        for vals in (r1, r2, r3):
            oh = np.zeros((n, 8), dtype=np.float32)
            for i in range(lag, n):
                v = int(vals[i - lag])
                if 0 <= v <= 7:
                    oh[i, v] = 1.0
            parts.append(oh)
    return np.concatenate(parts, axis=1).astype(np.float32)


# -------------------------------------------------------------- walk-forward CV


def walk_forward_predict(
    model_factory: Callable,
    X: np.ndarray,
    y: np.ndarray,
    warmup: int = 40,
    stride: int = 1,
) -> np.ndarray:
    """Train on [0, i), predict the next `stride` rows [i, i+stride), then
    advance by `stride`. stride=1 -> retrain every row (LOOCV-style).
    stride=50 -> retrain every 50 rows (cheap on large N, still no leakage
    because the training set only uses rows < i).
    """
    n = len(y)
    preds = np.full(n, np.nan)
    i = warmup
    while i < n:
        X_train = X[:i]
        y_train = y[:i]
        end = min(i + stride, n)
        if len(np.unique(y_train)) < 2:
            preds[i:end] = y_train.mean()
        else:
            try:
                model = model_factory()
                model.fit(X_train, y_train)
                preds[i:end] = model.predict_proba(X[i:end])[:, 1]
            except Exception:
                preds[i:end] = y_train.mean()
        i = end
    return preds


def score_predictions(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    quantile: float = 0.25,
) -> dict:
    """Evaluate walk-forward predictions. Skip NaN rows (warmup)."""
    mask = ~np.isnan(y_pred)
    yt = y_true[mask].astype(float)
    yp = np.clip(y_pred[mask].astype(float), 1e-6, 1 - 1e-6)
    if len(yt) == 0:
        return {"n_scored": 0}
    base = yt.mean()
    brier = float(np.mean((yp - yt) ** 2))
    log_loss = float(-np.mean(yt * np.log(yp) + (1 - yt) * np.log(1 - yp)))
    # top-quantile precision
    k = max(1, int(round(len(yt) * quantile)))
    order = np.argsort(-yp)
    top_idx = order[:k]
    precision_top = float(yt[top_idx].mean())
    lift_top = precision_top - base
    # top-10% precision
    k10 = max(1, int(round(len(yt) * 0.10)))
    top10 = order[:k10]
    precision_top10 = float(yt[top10].mean())
    lift_top10 = precision_top10 - base
    # predicted-max row
    best_pred_row = int(order[0])
    best_pred_val = float(yp[best_pred_row])
    return {
        "n_scored": int(len(yt)),
        "base_rate": round(base, 4),
        "log_loss": round(log_loss, 4),
        "brier": round(brier, 4),
        "k_top25": k,
        "prec_top25": round(precision_top, 4),
        "lift_top25_pp": round(lift_top * 100, 2),
        "k_top10": k10,
        "prec_top10": round(precision_top10, 4),
        "lift_top10_pp": round(lift_top10 * 100, 2),
        "max_pred_prob": round(best_pred_val, 4),
    }


# -------------------------------------------------------------- model factories


def mk_base_rate(y: np.ndarray) -> float:
    return float(y.mean())


def base_rate_predict(y: np.ndarray, warmup: int = 40) -> np.ndarray:
    n = len(y)
    preds = np.full(n, np.nan)
    for i in range(warmup, n):
        preds[i] = y[:i].mean()
    return preds


def mk_lr(C: float = 1.0):
    return lambda: LogisticRegression(
        penalty="l2", C=C, solver="liblinear", max_iter=1000, class_weight="balanced"
    )


def mk_gbt(n_estimators: int = 100, max_depth: int = 3, lr: float = 0.05):
    return lambda: GradientBoostingClassifier(
        n_estimators=n_estimators, max_depth=max_depth, learning_rate=lr,
    )


def mk_rf(n_estimators: int = 200, max_depth: int = 6):
    return lambda: RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        class_weight="balanced",
        n_jobs=1,
        random_state=0,
    )


# -------------------------------------------------------------- drivers


def run_enriched_experiment() -> list[dict]:
    enriched = load_enriched()
    log(f"\n=== ENRICHED (IL2CPP idx) n={len(enriched)} ===")
    y_val = make_target_valuable(enriched)
    y_any = make_target_any_triple(enriched)
    log(
        f"valuable triples: {int(y_val.sum())}/{len(y_val)} "
        f"(base rate {y_val.mean()*100:.2f}%)"
    )
    log(
        f"any triples:      {int(y_any.sum())}/{len(y_any)} "
        f"(base rate {y_any.mean()*100:.2f}%)"
    )

    results: list[dict] = []

    def score(name: str, target_name: str, y: np.ndarray, y_pred: np.ndarray):
        s = score_predictions(y, y_pred)
        row = {"dataset": "enriched_213", "target": target_name, "model": name, **s}
        results.append(row)
        log(
            f"  {name:40s} logloss={s.get('log_loss','-')} "
            f"top25_prec={s.get('prec_top25','-')} lift_top25={s.get('lift_top25_pp','-')}pp "
            f"top10_prec={s.get('prec_top10','-')} lift_top10={s.get('lift_top10_pp','-')}pp"
        )

    for target_name, y in (("valuable_triple", y_val), ("any_triple", y_any)):
        log(f"\n--- TARGET: {target_name} ---")

        # Base rate
        base_preds = base_rate_predict(y, warmup=40)
        score("base_rate", target_name, y, base_preds)

        if not SKLEARN_OK:
            continue

        # Feature sets
        X_lag_only, _ = build_feature_set(
            enriched, y, include_lag=True, include_same_spin=False, include_runlen=False
        )
        X_ss_only, _ = build_feature_set(
            enriched, y, include_lag=False, include_same_spin=True, include_runlen=False
        )
        X_all, _ = build_feature_set(
            enriched, y, include_lag=True, include_same_spin=True, include_runlen=True
        )

        # Logistic regression variants
        log("  fitting LR variants...")
        for C in (0.1, 1.0, 10.0):
            for fname, X in (
                ("lag_only", X_lag_only),
                ("same_spin_r1r3", X_ss_only),
                ("lag+same+runlen", X_all),
            ):
                preds = walk_forward_predict(mk_lr(C=C), X, y, warmup=40)
                score(f"LR_C={C}_{fname}", target_name, y, preds)

        # GBT (on combined)
        log("  fitting GBT variants...")
        for ne in (50, 100):
            for md in (2, 3):
                preds = walk_forward_predict(
                    mk_gbt(n_estimators=ne, max_depth=md), X_all, y, warmup=40
                )
                score(f"GBT_n{ne}_d{md}_all", target_name, y, preds)

        # RF
        log("  fitting RF...")
        preds = walk_forward_predict(mk_rf(), X_all, y, warmup=40)
        score("RF_n200_d6_all", target_name, y, preds)

    return results


def run_symbol_baseline_experiment() -> list[dict]:
    if not SKLEARN_OK:
        return []
    df = load_full_symbol()
    log(f"\n=== SYMBOL BASELINE (full) n={len(df)} ===")
    y_val = make_target_valuable(df)
    y_any = make_target_any_triple(df)
    log(
        f"valuable triples: {int(y_val.sum())}/{len(y_val)} "
        f"(base rate {y_val.mean()*100:.2f}%)"
    )
    log(
        f"any triples:      {int(y_any.sum())}/{len(y_any)} "
        f"(base rate {y_any.mean()*100:.2f}%)"
    )

    X = build_symbol_features(df, max_lag=3)
    results: list[dict] = []

    def score(name: str, target_name: str, y: np.ndarray, y_pred: np.ndarray):
        s = score_predictions(y, y_pred)
        row = {"dataset": "symbol_5393", "target": target_name, "model": name, **s}
        results.append(row)
        log(
            f"  {name:40s} logloss={s.get('log_loss','-')} "
            f"top25_prec={s.get('prec_top25','-')} lift_top25={s.get('lift_top25_pp','-')}pp "
            f"top10_prec={s.get('prec_top10','-')} lift_top10={s.get('lift_top10_pp','-')}pp"
        )

    for target_name, y in (("valuable_triple", y_val), ("any_triple", y_any)):
        log(f"\n--- TARGET: {target_name} ---")
        # Stride=100 on 5K rows: retrain every 100 rows (~52 fits instead of ~5200).
        # Still a legitimate walk-forward (each window's training set is strictly
        # rows < start_of_window) but 50x cheaper.
        warmup = 200
        stride = 100

        base_preds = base_rate_predict(y, warmup=warmup)
        score("base_rate", target_name, y, base_preds)

        log("  fitting LR walk-forward (stride=100)...")
        preds = walk_forward_predict(mk_lr(C=1.0), X, y, warmup=warmup, stride=stride)
        score("LR_C=1_symlag3", target_name, y, preds)

        log("  fitting GBT walk-forward (stride=100)...")
        preds = walk_forward_predict(
            mk_gbt(n_estimators=100, max_depth=3), X, y, warmup=warmup, stride=stride
        )
        score("GBT_n100_d3_symlag3", target_name, y, preds)

    return results


# -------------------------------------------------------------- summary


def decide(rows: list[dict]) -> str:
    """Apply the Move 1 decision rule across all results."""
    lines = []
    lines.append("\n=== DECISION ===")
    # Filter to valuable_triple target rows
    val = [r for r in rows if r["target"] == "valuable_triple" and "lift_top25_pp" in r]
    any_tr = [r for r in rows if r["target"] == "any_triple" and "lift_top25_pp" in r]

    def best(rset: list[dict], key: str) -> dict | None:
        if not rset:
            return None
        return max(rset, key=lambda r: r.get(key, -1e9))

    b_val_25 = best(val, "lift_top25_pp")
    b_val_10 = best(val, "lift_top10_pp")
    b_any_25 = best(any_tr, "lift_top25_pp")
    b_any_10 = best(any_tr, "lift_top10_pp")

    if b_val_25:
        lines.append(
            f"  best valuable top-25 lift: {b_val_25['lift_top25_pp']}pp "
            f"via {b_val_25['dataset']}/{b_val_25['model']}"
        )
    if b_val_10:
        lines.append(
            f"  best valuable top-10 lift: {b_val_10['lift_top10_pp']}pp "
            f"via {b_val_10['dataset']}/{b_val_10['model']}"
        )
    if b_any_25:
        lines.append(
            f"  best any-triple top-25 lift: {b_any_25['lift_top25_pp']}pp "
            f"via {b_any_25['dataset']}/{b_any_25['model']}"
        )
    if b_any_10:
        lines.append(
            f"  best any-triple top-10 lift: {b_any_10['lift_top10_pp']}pp "
            f"via {b_any_10['dataset']}/{b_any_10['model']}"
        )

    best_val_lift = max(
        r["lift_top25_pp"] for r in val if "lift_top25_pp" in r
    ) if val else None
    best_val_lift10 = max(
        r["lift_top10_pp"] for r in val if "lift_top10_pp" in r
    ) if val else None

    if best_val_lift is None:
        lines.append("  [NO DATA]")
    else:
        peak = max(best_val_lift, best_val_lift10 or -1e9)
        if peak >= 10:
            lines.append(
                f"  CLEAR +10pp ON VALUABLE-TRIPLE: {peak}pp  -> SAVE AS BET-SIZING CANDIDATE"
            )
        elif peak >= 5:
            lines.append(
                f"  PARTIAL +5pp ON VALUABLE-TRIPLE: {peak}pp  -> note, do not ship; "
                f"try scanner v2 before committing"
            )
        else:
            lines.append(
                f"  UNDER +5pp ON VALUABLE-TRIPLE (peak {peak}pp)  -> proof we need more data. Go Move 2."
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(REPO / "analysis" / "nuclear" / "56_results.json"),
    )
    args = parser.parse_args()

    all_rows: list[dict] = []
    all_rows += run_enriched_experiment()
    all_rows += run_symbol_baseline_experiment()

    out_path = Path(args.out)
    out_path.write_text(json.dumps(all_rows, indent=2))
    log(f"\nwrote: {out_path}")
    log(decide(all_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
