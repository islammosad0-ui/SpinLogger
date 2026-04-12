#!/usr/bin/env python3
"""Joint-idx triple predictor.

Cross-validates four models on the 213 observed rows:
  M0  base rate (null)
  M1  symbol naive Bayes over (r1, r2, r3)        -- "5 months of analysis" approach
  M2  idx naive Bayes over (r1_idx, r2_idx, r3_idx) -- the new approach
  M3  idx joint-state Laplace lookup              -- raw 9^3 conditional table

Target: is_triple on spin N+1, given state on spin N.

Metrics:
  - Log loss  (lower = better)
  - Brier score (lower = better)
  - Accuracy at optimal decision threshold
  - Top-quartile precision (P(triple | prediction in top 25%))
  - Max predicted probability (best-case lift)
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


# ---------- Data ----------

def load_observed(csv: Path) -> pd.DataFrame:
    df = pd.read_csv(csv)
    obs = df[df["r1_idx"].notna()].copy()
    for c in ("r1", "r2", "r3", "r1_idx", "r2_idx", "r3_idx"):
        obs[c] = obs[c].astype(int)
    obs = obs.sort_values("seq").reset_index(drop=True)
    return obs


def build_lag1_features(obs: pd.DataFrame, feature_cols: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """For each row i>=1, features = obs[i-1], target = obs[i][is_triple]."""
    n = len(obs)
    X = obs[feature_cols].values[:-1]  # state on spin N
    y = obs["is_triple"].values[1:].astype(int)  # triple on spin N+1
    return X, y


# ---------- Models ----------

class NaiveBayesCategorical:
    """Multinomial-ish naive Bayes for discrete features with Laplace smoothing.

    P(y=1 | x) ∝ P(y=1) * prod_i P(x_i | y=1)
    """

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.classes = [0, 1]
        n_features = X.shape[1]
        self.feature_values = [sorted(set(X[:, j])) for j in range(n_features)]
        self.priors = {}
        # conditional[j][v][c] = P(feature j = v | y = c)
        self.cond = [defaultdict(lambda: {0: 0.0, 1: 0.0}) for _ in range(n_features)]
        for c in self.classes:
            mask = y == c
            self.priors[c] = (mask.sum() + self.alpha) / (len(y) + self.alpha * 2)
            for j in range(n_features):
                values = X[mask, j]
                counts = Counter(values)
                total = mask.sum()
                # Laplace over all values seen in training (for this feature)
                k = len(self.feature_values[j])
                for v in self.feature_values[j]:
                    self.cond[j][v][c] = (counts.get(v, 0) + self.alpha) / (total + self.alpha * k)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return P(y=1 | x) for each row."""
        out = np.zeros(len(X))
        n_features = X.shape[1]
        for i, row in enumerate(X):
            log0 = np.log(self.priors[0])
            log1 = np.log(self.priors[1])
            for j, v in enumerate(row):
                # Unseen feature value: back off to uniform over seen values
                k = len(self.feature_values[j])
                p0 = self.cond[j].get(v, {0: 1.0 / k, 1: 1.0 / k})[0]
                p1 = self.cond[j].get(v, {0: 1.0 / k, 1: 1.0 / k})[1]
                log0 += np.log(max(p0, 1e-12))
                log1 += np.log(max(p1, 1e-12))
            # Normalize
            m = max(log0, log1)
            p = np.exp(log1 - m) / (np.exp(log0 - m) + np.exp(log1 - m))
            out[i] = p
        return out


class JointLookup:
    """Joint-state conditional probability with Laplace smoothing.

    For each unique observed joint state s, estimate P(triple | s).
    Unseen states -> prior.
    """

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.prior = (y.sum() + self.alpha) / (len(y) + self.alpha * 2)
        table: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])  # [trip, total]
        for row, label in zip(X, y):
            key = tuple(row)
            table[key][1] += 1
            table[key][0] += int(label)
        self.table = {}
        for key, (trip, total) in table.items():
            self.table[key] = (trip + self.alpha) / (total + self.alpha * 2)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        return np.array([self.table.get(tuple(row), self.prior) for row in X])


class BaseRate:
    def fit(self, X, y):
        self.p = y.mean()
        return self

    def predict_proba(self, X):
        return np.full(len(X), self.p)


# ---------- Metrics ----------

def log_loss(y_true, y_pred):
    eps = 1e-12
    y_pred = np.clip(y_pred, eps, 1 - eps)
    return -np.mean(y_true * np.log(y_pred) + (1 - y_true) * np.log(1 - y_pred))


def brier_score(y_true, y_pred):
    return float(np.mean((y_true - y_pred) ** 2))


def best_threshold_accuracy(y_true, y_pred):
    best_acc = 0.0
    best_t = 0.5
    for t in np.linspace(0.1, 0.9, 33):
        pred = (y_pred >= t).astype(int)
        acc = (pred == y_true).mean()
        if acc > best_acc:
            best_acc = acc
            best_t = t
    return best_acc, best_t


def top_quartile_precision(y_true, y_pred):
    """Of the top 25% most-confident triple predictions, what fraction actually triple?"""
    if len(y_pred) < 4:
        return float("nan"), 0
    sorted_idx = np.argsort(-y_pred)
    q = max(1, len(y_pred) // 4)
    top_idx = sorted_idx[:q]
    return float(y_true[top_idx].mean()), int(q)


# ---------- Cross-validation ----------

def k_fold_indices(n: int, k: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    idx = np.arange(n)
    rng.shuffle(idx)
    folds = np.array_split(idx, k)
    for i in range(k):
        test = folds[i]
        train = np.concatenate([folds[j] for j in range(k) if j != i])
        yield train, test


def cross_validate(model_factory, X, y, k=5, seed=0):
    all_y_true = []
    all_y_pred = []
    for train_idx, test_idx in k_fold_indices(len(X), k, seed):
        m = model_factory()
        m.fit(X[train_idx], y[train_idx])
        y_pred = m.predict_proba(X[test_idx])
        all_y_true.append(y[test_idx])
        all_y_pred.append(y_pred)
    yt = np.concatenate(all_y_true)
    yp = np.concatenate(all_y_pred)
    return yt, yp


def report_model(name, yt, yp, base_rate):
    ll = log_loss(yt, yp)
    br = brier_score(yt, yp)
    acc, thr = best_threshold_accuracy(yt, yp)
    topq_prec, topq_n = top_quartile_precision(yt, yp)
    max_p = yp.max()
    min_p = yp.min()
    print(f"\n--- {name} ---")
    print(f"  log loss       : {ll:.4f}")
    print(f"  brier score    : {br:.4f}")
    print(f"  best-thr acc   : {acc:.3f}  (threshold {thr:.2f})")
    print(f"  top-25% precision: {topq_prec:.1%}  (n={topq_n}, base rate={base_rate:.1%}, "
          f"lift={topq_prec - base_rate:+.1%})")
    print(f"  prediction range: [{min_p:.3f}, {max_p:.3f}]")


# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enriched-csv", required=True, type=Path)
    ap.add_argument("--k", type=int, default=5, help="Number of CV folds")
    ap.add_argument("--seeds", type=int, default=10, help="Number of random seeds to average over")
    args = ap.parse_args()

    obs = load_observed(args.enriched_csv)
    print(f"Observed rows         : {len(obs)}")
    print(f"Base triple rate      : {obs['is_triple'].mean():.1%}")

    X_sym, y = build_lag1_features(obs, ["r1", "r2", "r3"])
    X_idx, _ = build_lag1_features(obs, ["r1_idx", "r2_idx", "r3_idx"])
    n = len(y)
    base_rate = y.mean()
    print(f"Lag-1 pairs           : {n}")
    print(f"Lag-1 base triple rate: {base_rate:.1%}")
    print()

    # Average over multiple seeds to reduce fold-luck variance
    results = {"M0 base rate": [], "M1 symbol NB": [], "M2 idx NB": [], "M3 idx joint-lookup": []}

    for seed in range(args.seeds):
        yt, yp = cross_validate(lambda: BaseRate(), X_idx, y, k=args.k, seed=seed)
        results["M0 base rate"].append((yt, yp))

        yt, yp = cross_validate(lambda: NaiveBayesCategorical(alpha=1.0), X_sym, y, k=args.k, seed=seed)
        results["M1 symbol NB"].append((yt, yp))

        yt, yp = cross_validate(lambda: NaiveBayesCategorical(alpha=1.0), X_idx, y, k=args.k, seed=seed)
        results["M2 idx NB"].append((yt, yp))

        yt, yp = cross_validate(lambda: JointLookup(alpha=1.0), X_idx, y, k=args.k, seed=seed)
        results["M3 idx joint-lookup"].append((yt, yp))

    print(f"=== {args.k}-fold CV, averaged over {args.seeds} seeds ===")
    for name, runs in results.items():
        # Average metrics across seeds
        lls = []
        brs = []
        accs = []
        topqs = []
        max_ps = []
        for yt, yp in runs:
            lls.append(log_loss(yt, yp))
            brs.append(brier_score(yt, yp))
            a, _ = best_threshold_accuracy(yt, yp)
            accs.append(a)
            p, _ = top_quartile_precision(yt, yp)
            topqs.append(p)
            max_ps.append(yp.max())
        print(f"\n--- {name} ---")
        print(f"  log loss         : {np.mean(lls):.4f} +/- {np.std(lls):.4f}")
        print(f"  brier score      : {np.mean(brs):.4f} +/- {np.std(brs):.4f}")
        print(f"  best-thr accuracy: {np.mean(accs):.3f} +/- {np.std(accs):.3f}")
        print(f"  top-25% precision: {np.mean(topqs):.1%} +/- {np.std(topqs):.1%}  "
              f"(base={base_rate:.1%}, lift={np.mean(topqs) - base_rate:+.1%})")
        print(f"  max prediction   : {np.mean(max_ps):.3f}")

    # --- Best-state cherry-pick (training on ALL data, no CV) ---
    print("\n=== In-sample: which idx states have the highest / lowest P(triple) ? ===")
    model = JointLookup(alpha=1.0).fit(X_idx, y)
    states = sorted(
        ((k, v, sum(1 for row in X_idx if tuple(row) == k))
         for k, v in model.table.items()),
        key=lambda t: -t[1]
    )
    # Only show states with >= 3 occurrences to suppress noise
    print("\nTop 15 (states with n>=3):")
    print(f"{'state (r1i,r2i,r3i)':<22} {'P(triple)':<12} {'n':<5}")
    shown = 0
    for (k, p, n_obs) in states:
        if n_obs < 3:
            continue
        print(f"  {str(k):<20} {p:.1%}         {n_obs}")
        shown += 1
        if shown >= 15:
            break

    print("\nBottom 15 (states with n>=3):")
    shown = 0
    for (k, p, n_obs) in reversed(states):
        if n_obs < 3:
            continue
        print(f"  {str(k):<20} {p:.1%}         {n_obs}")
        shown += 1
        if shown >= 15:
            break


if __name__ == "__main__":
    main()
