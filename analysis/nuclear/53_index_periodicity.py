#!/usr/bin/env python3
"""Retro analysis on the 213-spin enriched dataset — is there structure in the bar indices?

Five tests:
  1. Uniformity per reel   - is every strip index hit equally often?
  2. Autocorrelation       - does idx[N] predict idx[N+k] for small k?
  3. Markov transitions    - is the next-index distribution conditioned on current index?
  4. Cross-reel coupling   - are r1_idx / r2_idx / r3_idx correlated on the same spin?
  5. Triple predictors     - do the indices on spins N-1..N-3 differ when spin N is a triple?

This works purely from observed data; no new memory captures needed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


def load_observed(enriched_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(enriched_csv)
    obs = df[df["r1_idx"].notna()].copy()
    for c in ("r1_idx", "r2_idx", "r3_idx"):
        obs[c] = obs[c].astype(int)
    obs = obs.sort_values("seq").reset_index(drop=True)
    return obs


def chi_square_uniform(values, n_bins: int = 9):
    counts = Counter(int(v) for v in values)
    observed = [counts.get(i, 0) for i in range(n_bins)]
    expected = sum(observed) / n_bins
    chi2 = sum((o - expected) ** 2 / expected for o in observed)
    # df=8, p=0.05 critical = 15.507; p=0.01 critical = 20.090
    return observed, expected, chi2


def autocorrelation(series, max_lag: int = 15):
    x = np.array(series, dtype=float)
    x = x - x.mean()
    denom = np.dot(x, x)
    if denom == 0:
        return [0.0] * max_lag
    out = []
    for lag in range(1, max_lag + 1):
        if lag >= len(x):
            break
        out.append(float(np.dot(x[:-lag], x[lag:]) / denom))
    return out


def markov_counts(series, n_states: int = 9):
    tm = np.zeros((n_states, n_states), dtype=int)
    arr = [int(v) for v in series]
    for a, b in zip(arr[:-1], arr[1:]):
        tm[a][b] += 1
    return tm


def print_matrix(tm: np.ndarray, title: str) -> None:
    print(title)
    print("        " + "".join(f"{i:>5}" for i in range(tm.shape[1])))
    row_totals = tm.sum(axis=1)
    for i, row in enumerate(tm):
        total = row_totals[i]
        line = f"  {i:>2} | " + "".join(f"{v:>5}" for v in row)
        if total:
            line += f"   n={total}"
        print(line)


def print_markov_probabilities(tm: np.ndarray, title: str, min_row_total: int = 5) -> None:
    print(title)
    print("        " + "".join(f"{i:>6}" for i in range(tm.shape[1])) + "     n")
    row_totals = tm.sum(axis=1)
    for i, row in enumerate(tm):
        total = row_totals[i]
        if total < min_row_total:
            continue
        probs = row / total
        line = f"  {i:>2} | " + "".join(f"{p:>5.0%} " for p in probs)
        line += f"   {total}"
        print(line)


def test_uniformity(obs: pd.DataFrame) -> None:
    print("=" * 70)
    print("TEST 1 — Uniformity per reel (chi² vs 15.507 @ p=0.05, 8 dof)")
    print("=" * 70)
    for reel in (1, 2, 3):
        col = f"r{reel}_idx"
        observed, expected, chi2 = chi_square_uniform(obs[col])
        verdict = "SKEWED" if chi2 > 15.507 else "uniform"
        print(f"\nReel {reel}: expected={expected:.1f} per bin   chi²={chi2:.2f}   [{verdict}]")
        for i, c in enumerate(observed):
            bar = "#" * int(c / 2)
            diff = c - expected
            sign = "+" if diff >= 0 else ""
            print(f"  idx {i}: {c:>3}  ({sign}{diff:+.1f})  {bar}")


def test_autocorrelation(obs: pd.DataFrame) -> None:
    print("\n" + "=" * 70)
    print("TEST 2 — Autocorrelation per reel (lags 1-15)")
    print("=" * 70)
    ci = 1.96 / np.sqrt(len(obs))
    print(f"White-noise 95% confidence band: ±{ci:.3f}")
    print()
    for reel in (1, 2, 3):
        col = f"r{reel}_idx"
        ac = autocorrelation(obs[col].values, max_lag=15)
        flags = ["*" if abs(c) > ci else " " for c in ac]
        print(f"Reel {reel}:")
        print("  lag:  " + "".join(f"{i+1:>6}" for i in range(len(ac))))
        print("  acf:  " + "".join(f"{c:>+5.2f}{f}" for c, f in zip(ac, flags)))
        significant = [(i + 1, c) for i, c in enumerate(ac) if abs(c) > ci]
        if significant:
            print(f"  --> significant lags: {significant}")
        else:
            print("  --> no significant autocorrelation")
        print()


def test_markov(obs: pd.DataFrame) -> None:
    print("=" * 70)
    print("TEST 3 — Markov transitions for reel 2 (clean strip)")
    print("=" * 70)
    tm = markov_counts(obs["r2_idx"].values)
    print_matrix(tm, "\nTransition COUNTS (row=idx[N], col=idx[N+1]):")
    print_markov_probabilities(tm, "\nTransition PROBS (row=idx[N]):")

    # A random strip would have each transition ≈ 1/9 ≈ 11%
    # Look for rows where the top transition is significantly > 11%
    print("\nDominant next-index per starting position (if any >25%):")
    for i, row in enumerate(tm):
        total = row.sum()
        if total < 5:
            continue
        top_idx = int(np.argmax(row))
        top_p = row[top_idx] / total
        if top_p >= 0.25:
            print(f"  idx {i} → idx {top_idx} @ {top_p:.0%} ({row[top_idx]}/{total} transitions)")


def test_cross_reel(obs: pd.DataFrame) -> None:
    print("\n" + "=" * 70)
    print("TEST 4 — Cross-reel index coupling (same spin)")
    print("=" * 70)
    pairs = [("r1_idx", "r2_idx"), ("r1_idx", "r3_idx"), ("r2_idx", "r3_idx")]
    for a, b in pairs:
        r = np.corrcoef(obs[a], obs[b])[0, 1]
        ci = 1.96 / np.sqrt(len(obs))
        flag = "*" if abs(r) > ci else " "
        print(f"  {a:<7} x {b:<7}  r = {r:+.3f}  {flag}")
    print(f"(white-noise band: ±{1.96 / np.sqrt(len(obs)):.3f})")


def test_triple_predictors(obs: pd.DataFrame) -> None:
    print("\n" + "=" * 70)
    print("TEST 5 — Do prior-spin indices predict the next spin being a triple?")
    print("=" * 70)
    base_rate = obs["is_triple"].mean()
    print(f"Base triple rate (this session): {base_rate:.1%}")
    print()

    for reel in (1, 2, 3):
        col = f"r{reel}_idx"
        print(f"P(triple | prior spin r{reel}_idx = X)")
        triple_next_by_prior = Counter()
        total_by_prior = Counter()
        for i in range(1, len(obs)):
            prior_val = int(obs.iloc[i - 1][col])
            total_by_prior[prior_val] += 1
            if obs.iloc[i]["is_triple"]:
                triple_next_by_prior[prior_val] += 1
        lines = []
        for idx in range(9):
            total = total_by_prior.get(idx, 0)
            trip = triple_next_by_prior.get(idx, 0)
            if total == 0:
                continue
            rate = trip / total
            delta = rate - base_rate
            sig = "*" if total >= 15 and abs(delta) > 0.15 else " "
            lines.append(f"  idx {idx}: {rate:.1%}  ({trip:>2}/{total:>2})  Δ={delta:+.1%} {sig}")
        for line in lines:
            print(line)
        print()


def analyze_triple_gaps(obs: pd.DataFrame) -> None:
    print("=" * 70)
    print("TEST 6 — Gap analysis between triples (periodicity in fail streaks)")
    print("=" * 70)
    triple_positions = obs[obs["is_triple"]].index.tolist()
    if len(triple_positions) < 2:
        print("Not enough triples to compute gaps.")
        return
    gaps = [triple_positions[i + 1] - triple_positions[i] for i in range(len(triple_positions) - 1)]
    gap_counts = Counter(gaps)
    print(f"Triples observed: {len(triple_positions)}")
    print(f"Gap count: {len(gaps)}  mean={np.mean(gaps):.2f}  median={np.median(gaps):.1f}  max={max(gaps)}")
    print("\nGap distribution (gaps >= 1 only since we index on observed spins):")
    for g in sorted(gap_counts):
        bar = "#" * gap_counts[g]
        print(f"  gap={g:>2}: {gap_counts[g]:>3}  {bar}")

    # Geometric (memoryless) expectation: with p=base_rate, P(gap=k) = (1-p)^(k-1) * p
    p = len(triple_positions) / len(obs)
    print(f"\nExpected under memoryless geometric (p={p:.3f}):")
    for k in range(1, max(gap_counts) + 1):
        expected = len(gaps) * ((1 - p) ** (k - 1)) * p
        actual = gap_counts.get(k, 0)
        diff = actual - expected
        if abs(diff) > 2:
            flag = " <--"
        else:
            flag = ""
        print(f"  gap={k:>2}: observed={actual:>3}  expected={expected:>5.1f}  Δ={diff:+5.1f}{flag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enriched-csv", required=True, type=Path)
    args = ap.parse_args()

    obs = load_observed(args.enriched_csv)
    print(f"Observed rows with indices: {len(obs)}")
    print(f"Triples in observed set   : {obs['is_triple'].sum()} "
          f"({obs['is_triple'].mean():.1%})")
    print(f"Seq range                 : {obs['seq'].min()} -> {obs['seq'].max()} "
          f"(span={obs['seq'].max() - obs['seq'].min()})")
    print()

    test_uniformity(obs)
    test_autocorrelation(obs)
    test_markov(obs)
    test_cross_reel(obs)
    test_triple_predictors(obs)
    print()
    analyze_triple_gaps(obs)


if __name__ == "__main__":
    main()
