#!/usr/bin/env python3
"""Run Stage 3 (field change-map) + Stage 5 (pity counter hunt) on the live trace.

The existing 50_il2cpp_trace_decode.py expects trace.spin_num == hist.seq.
On this real trace, trace.spin_num == hist.seq - 1 (the in-memory currentSpinNumber
is the 'currently playing' spin, CSV writes the completed row with next seq).
This wrapper shifts hist.seq down by 1 before invoking the stages, so the
existing tested code works unmodified.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pandas as pd


def load_stages_module() -> object:
    """Import 50_il2cpp_trace_decode.py (filename starts with digit)."""
    mod_path = Path(__file__).parent / "50_il2cpp_trace_decode.py"
    spec = importlib.util.spec_from_file_location("trace_decode", mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["trace_decode"] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, type=Path)
    ap.add_argument("--spin-history", required=True, type=Path)
    ap.add_argument("--fail-threshold", type=int, default=8)
    ap.add_argument("--min-spin", type=int, default=2,
                    help="Filter out trace spin_num < this (removes launch-time garbage)")
    args = ap.parse_args()

    trace_decode = load_stages_module()

    print(f"Loading trace: {args.trace}")
    snaps = trace_decode.load_jsonl(args.trace)
    snaps = [s for s in snaps if s.spin_num >= args.min_spin]
    print(f"  snapshots (after min_spin filter): {len(snaps)}")

    buckets = trace_decode.segment_by_spin(snaps)
    print(f"  unique spin_nums: {len(buckets)}")

    settled_buckets = {sn: sp for sn, sp in buckets.items() if sp.settled is not None}
    print(f"  with settled snapshot: {len(settled_buckets)}")

    print(f"\nLoading spin_history: {args.spin_history}")
    hist = pd.read_csv(args.spin_history)
    print(f"  rows: {len(hist)}")

    # CRITICAL: trace.spin_num = hist.seq - 1, so shift hist.seq down
    hist_shifted = hist.copy()
    hist_shifted["seq"] = hist_shifted["seq"] - 1
    print(f"  shifted seq range: {hist_shifted['seq'].min()} -> {hist_shifted['seq'].max()}")

    # How many trace spin_nums find a match?
    trace_spin_nums = set(settled_buckets.keys())
    hist_seqs = set(hist_shifted["seq"])
    overlap = trace_spin_nums & hist_seqs
    print(f"  trace<->hist overlap: {len(overlap)} / {len(settled_buckets)} trace spins")

    # ------- Stage 2 sanity gate -------
    # Note: Stage 2 looks for SlotSymbol3@ in fields; this trace doesn't have it
    # (currentSlotResult was non-null but SlotResult/SlotSymbol3 weren't pointer-followed
    # into fields). Skip stage 2.
    print("\n[Stage 2 skipped — no SlotSymbol3 fields in this trace]")

    # ------- Stage 3: field change-map -------
    print("\n=== Stage 3: Field change-map ===")
    stage3 = trace_decode.stage3_field_change_map(settled_buckets, hist_shifted)
    print(f"Profiled {len(stage3)} (class, field) pairs.")

    # Top 30 most interesting fields (not constant, best correlation)
    non_constant = [r for r in stage3 if not r["is_constant"]]
    with_corr = [r for r in non_constant if r["correlations"]]
    print(f"Non-constant fields: {len(non_constant)}")
    print(f"Fields with any correlation: {len(with_corr)}")

    print("\nTop 30 most interesting (type + best correlation):")
    print(f"{'class':<28} {'field':<42} {'type':<18} {'uniq':>5} {'best_corr':<20}")
    for row in stage3[:30]:
        if row["is_constant"]:
            continue
        best = max(row["correlations"].items(), key=lambda kv: kv[1], default=("-", 0.0))
        print(f"{row['class'][:28]:<28} {row['field'][:42]:<42} {row['type_guess']:<18} "
              f"{row['unique_count']:>5} {best[0]}={best[1]:.0%}")

    # ------- Stage 5: pity counter hunt -------
    print("\n=== Stage 5: Pity counter hunt ===")
    stage5 = trace_decode.stage5_pity_counter_hunt(
        settled_buckets, hist_shifted, fail_threshold=args.fail_threshold
    )
    print(f"Candidates found: {len(stage5)}")
    if not stage5:
        print("  (no field matched the monotonic+reset pattern with fail_threshold=8)")
        print("  Trying with fail_threshold=20 to relax the near-threshold check...")
        stage5 = trace_decode.stage5_pity_counter_hunt(
            settled_buckets, hist_shifted, fail_threshold=20
        )
        print(f"  Candidates at threshold=20: {len(stage5)}")

    for c in stage5[:10]:
        print(f"  {c['class']}.{c['field']} "
              f"monotonic={c['monotonic_between_triples']} "
              f"resets={c['resets_on_triple']} "
              f"max={c['max_value']} samples={c['n_samples']}")

    # Print the time series for m_SpinFailedCounterGlobal directly (whether or not
    # Stage 5 found it)
    print("\n=== Manual inspection: m_SpinFailedCounter* across spins ===")
    hist_by_seq = hist_shifted.set_index("seq")
    rows = []
    for sn in sorted(settled_buckets.keys())[:20]:  # first 20 spins
        settled = settled_buckets[sn].settled
        mgr = settled.fields.get("SlotMachineManager", {})
        sfc = mgr.get("m_SpinFailedCounter", {}).get("i32")
        sfcg = mgr.get("m_SpinFailedCounterGlobal", {}).get("i32")
        sfat = mgr.get("m_SpinFailedAnalyticThreshold", {}).get("i32")
        csv_row = hist_by_seq.loc[sn] if sn in hist_by_seq.index else None
        is_triple = bool(csv_row["is_triple"]) if csv_row is not None else None
        r = csv_row["reel_1"] if csv_row is not None else "?"
        rows.append((sn, sfc, sfcg, sfat, is_triple, r))

    print(f"{'spin':>7} {'Counter':>8} {'Global':>8} {'Thresh':>8} {'triple':>8} {'r1':<15}")
    for sn, sfc, sfcg, sfat, trip, r in rows:
        print(f"{sn:>7} {str(sfc):>8} {str(sfcg):>8} {str(sfat):>8} {str(trip):>8} {r}")


if __name__ == "__main__":
    main()
