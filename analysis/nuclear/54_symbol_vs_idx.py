#!/usr/bin/env python3
"""Prove the core insight: symbol-level analysis loses the signal that idx-level has.

For the same 213 observed spins, run identical tests on:
  - the SYMBOL stream (r1, r2, r3) — what we've been working with for 5 months
  - the IDX stream (r1_idx, r2_idx, r3_idx) — the underlying physical stop positions

If the idx stream shows stronger structure (Markov skew, cross-reel correlation,
autocorrelation), that's the evidence that every previous analysis was working on
a lossy projection.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


def load_observed(csv: Path) -> pd.DataFrame:
    df = pd.read_csv(csv)
    obs = df[df["r1_idx"].notna()].copy()
    for c in ("r1_idx", "r2_idx", "r3_idx", "r1", "r2", "r3"):
        obs[c] = obs[c].astype(int)
    return obs.sort_values("seq").reset_index(drop=True)


def chi2_uniform(series):
    vals = list(series)
    counts = Counter(vals)
    expected = len(vals) / len(counts)
    chi2 = sum((c - expected) ** 2 / expected for c in counts.values())
    dof = len(counts) - 1
    return chi2, dof, len(counts)


def autocorr(series, max_lag=10):
    x = np.array(series, dtype=float)
    x = x - x.mean()
    denom = np.dot(x, x)
    if denom == 0:
        return [0.0] * max_lag
    return [float(np.dot(x[:-lag], x[lag:]) / denom) for lag in range(1, max_lag + 1)]


def markov_max_transition(series):
    """Return (n_states, max_transition_prob, max_over_base_ratio) for a stream."""
    vals = [int(v) for v in series]
    states = sorted(set(vals))
    n = len(states)
    s2i = {s: i for i, s in enumerate(states)}
    tm = np.zeros((n, n), dtype=int)
    for a, b in zip(vals[:-1], vals[1:]):
        tm[s2i[a]][s2i[b]] += 1

    row_totals = tm.sum(axis=1)
    baseline = 1 / n  # uniform next-state prob
    max_ratio = 0.0
    max_prob = 0.0
    for i in range(n):
        if row_totals[i] < 5:
            continue
        probs = tm[i] / row_totals[i]
        m = probs.max()
        if m > max_prob:
            max_prob = m
        r = m / baseline
        if r > max_ratio:
            max_ratio = r
    return n, max_prob, max_ratio


def cross_corr(obs, col_a, col_b):
    return float(np.corrcoef(obs[col_a], obs[col_b])[0, 1])


def compare(obs: pd.DataFrame) -> None:
    N = len(obs)
    ci = 1.96 / np.sqrt(N)
    print(f"Observed spins: {N}")
    print(f"White-noise 95% CI band: +/- {ci:.3f}")
    print()

    # --- Uniformity ---
    print("=" * 78)
    print("UNIFORMITY (chi-square; higher = more skewed)")
    print("=" * 78)
    print(f"{'Reel':<6} {'Symbol chi2':<16} {'Idx chi2':<16} {'Winner'}")
    for reel in (1, 2, 3):
        sym_chi2, sym_dof, sym_k = chi2_uniform(obs[f"r{reel}"])
        idx_chi2, idx_dof, idx_k = chi2_uniform(obs[f"r{reel}_idx"])
        winner = "IDX" if idx_chi2 > sym_chi2 else "SYM"
        print(f"  {reel:<4} {sym_chi2:>7.1f} (k={sym_k})   "
              f"{idx_chi2:>7.1f} (k={idx_k})   {winner}")
    print()

    # --- Cross-reel correlation ---
    print("=" * 78)
    print("CROSS-REEL CORRELATION (bigger = more coupled)")
    print("=" * 78)
    print(f"{'Pair':<18} {'Symbol r':<12} {'Idx r':<12} {'Ratio (idx/sym)'}")
    for a, b in (("1", "2"), ("1", "3"), ("2", "3")):
        sym_r = cross_corr(obs, f"r{a}", f"r{b}")
        idx_r = cross_corr(obs, f"r{a}_idx", f"r{b}_idx")
        ratio = abs(idx_r / sym_r) if sym_r != 0 else float("inf")
        flag_sym = "*" if abs(sym_r) > ci else " "
        flag_idx = "*" if abs(idx_r) > ci else " "
        print(f"  r{a} x r{b}         "
              f"{sym_r:+.3f}{flag_sym}    "
              f"{idx_r:+.3f}{flag_idx}    x{ratio:.1f}")
    print()

    # --- Markov structure ---
    print("=" * 78)
    print("MARKOV STRUCTURE (max transition prob / uniform baseline)")
    print("=" * 78)
    print(f"{'Reel':<6} {'Symbol max ratio':<20} {'Idx max ratio':<20} {'Winner'}")
    for reel in (1, 2, 3):
        _, sym_p, sym_r = markov_max_transition(obs[f"r{reel}"])
        _, idx_p, idx_r = markov_max_transition(obs[f"r{reel}_idx"])
        winner = "IDX" if idx_r > sym_r else "SYM"
        print(f"  {reel:<4} {sym_p:>5.0%} ({sym_r:>4.1f}x base)   "
              f"{idx_p:>5.0%} ({idx_r:>4.1f}x base)   {winner}")
    print()

    # --- Autocorrelation ---
    print("=" * 78)
    print("AUTOCORRELATION (count of lags with |acf| > CI, lags 1-10)")
    print("=" * 78)
    print(f"{'Reel':<6} {'Symbol sig lags':<20} {'Idx sig lags':<20} {'Winner'}")
    for reel in (1, 2, 3):
        sym_acf = autocorr(obs[f"r{reel}"].values)
        idx_acf = autocorr(obs[f"r{reel}_idx"].values)
        sym_sig = sum(1 for c in sym_acf if abs(c) > ci)
        idx_sig = sum(1 for c in idx_acf if abs(c) > ci)
        winner = "IDX" if idx_sig > sym_sig else ("SYM" if sym_sig > idx_sig else "tie")
        print(f"  {reel:<4} {sym_sig:>3} of 10           "
              f"{idx_sig:>3} of 10           {winner}")
    print()

    # --- How many idx values produce each symbol? ---
    print("=" * 78)
    print("INFORMATION LOSS: how many idx values collapse onto each symbol?")
    print("=" * 78)
    for reel in (1, 2, 3):
        sym_col = f"r{reel}"
        idx_col = f"r{reel}_idx"
        reel_col = f"reel_{reel}"
        sym_to_idxs = {}
        for _, row in obs.iterrows():
            sym_to_idxs.setdefault(row[reel_col], set()).add(int(row[idx_col]))
        total_idxs = sum(len(s) for s in sym_to_idxs.values())
        print(f"  Reel {reel}: {len(sym_to_idxs)} unique symbols "
              f"cover {total_idxs} observed idx values")
        for sym, idxs in sorted(sym_to_idxs.items(), key=lambda kv: -len(kv[1])):
            if len(idxs) > 1:
                print(f"     {sym:<15} -> idxs {sorted(idxs)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enriched-csv", required=True, type=Path)
    args = ap.parse_args()
    obs = load_observed(args.enriched_csv)
    compare(obs)


if __name__ == "__main__":
    main()
