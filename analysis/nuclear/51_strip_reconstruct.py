#!/usr/bin/env python3
"""Strip reconstruction from observation.

The live trace captures `resultSymbolIndex` per reel per spin, but the
`m_SymbolElements` hex blobs failed the scanner's sanity check and weren't
dumped. So instead of decoding strip layouts from memory, we reconstruct them
by cross-referencing trace bar indices against spin_history ground truth.

Key insight: trace spin_num corresponds to CSV seq-1 (the in-memory counter
is the "currently-playing" spin; CSV writes the completed row with the next seq).

For every settled trace snapshot, we pair (bar<N>_idx, r<N>, reel_<N>) with
the matching CSV row. After ~200 spins we learn:
  - strip layout per reel (idx -> symbol)
  - duplicate symbol positions (goldSack theory test)
  - triple index patterns vs triple symbol patterns

Output:
  - Console report (strip layouts, duplicates, ambiguities)
  - analysis/nuclear/51_strip_layout.md (markdown report)
  - data/Ahmed/spin_history_Ahmed_enriched.csv (CSV + new columns)
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


def load_settled_bar_indices(trace_path: Path) -> Dict[int, Dict[int, int]]:
    """For each spin_num, return the LAST-seen settled {reel: resultSymbolIndex}.

    A "settled" snapshot has spinning=0. We take the last settled snapshot of
    each spin_num because it's the most recent read before the next spin starts.
    """
    out: Dict[int, Dict[int, int]] = {}
    with trace_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("spinning") != 0:
                continue
            sn = d.get("spin_num")
            if sn is None or sn < 2:  # skip the "1" garbage
                continue
            bars: Dict[int, int] = {}
            for class_key, cls_fields in d.get("fields", {}).items():
                if not class_key.startswith("SlotBarManager_"):
                    continue
                try:
                    reel = int(class_key.split("@", 1)[0].split("_")[1])
                except (IndexError, ValueError):
                    continue
                rsi = cls_fields.get("resultSymbolIndex", {}).get("i32")
                if rsi is not None:
                    bars[reel] = rsi
            if len(bars) == 3:
                out[sn] = bars   # last write wins => latest settled snapshot
    return out


def build_observation_pairs(
    bar_idx_by_spin: Dict[int, Dict[int, int]],
    hist: pd.DataFrame,
) -> pd.DataFrame:
    """Build DataFrame of observations pairing trace bar_idx with CSV r values.

    Joins trace.spin_num -> CSV.seq = spin_num + 1.
    Returns columns: spin_num, seq, r1_idx, r2_idx, r3_idx, r1, r2, r3,
    reel_1, reel_2, reel_3, is_triple.
    """
    hist_by_seq = hist.set_index("seq")
    rows = []
    for spin_num, bars in bar_idx_by_spin.items():
        seq = spin_num + 1
        if seq not in hist_by_seq.index:
            continue
        row = hist_by_seq.loc[seq]
        rows.append({
            "spin_num": spin_num,
            "seq": seq,
            "r1_idx": bars[1],
            "r2_idx": bars[2],
            "r3_idx": bars[3],
            "r1": int(row["r1"]),
            "r2": int(row["r2"]),
            "r3": int(row["r3"]),
            "reel_1": row.get("reel_1"),
            "reel_2": row.get("reel_2"),
            "reel_3": row.get("reel_3"),
            "is_triple": bool(row.get("is_triple", False)),
        })
    return pd.DataFrame(rows)


def reconstruct_strip(
    obs: pd.DataFrame, reel: int
) -> Tuple[Dict[int, Counter], Dict[int, str]]:
    """For one reel, build {idx -> Counter(symbol_id)} and a name mapping.

    Returns:
      counts: idx -> Counter of (r_id, reel_name) tuples (to verify consistency)
      canonical: idx -> most common (r_id, reel_name) string
    """
    idx_col = f"r{reel}_idx"
    r_col = f"r{reel}"
    name_col = f"reel_{reel}"

    counts: Dict[int, Counter] = defaultdict(Counter)
    for _, row in obs.iterrows():
        key = (int(row[r_col]), row[name_col])
        counts[int(row[idx_col])][key] += 1

    canonical: Dict[int, str] = {}
    for idx in sorted(counts):
        top, n = counts[idx].most_common(1)[0]
        r_id, name = top
        total = sum(counts[idx].values())
        pct = n / total * 100
        canonical[idx] = f"{name}({r_id})  [{n}/{total} = {pct:.0f}%]"
    return counts, canonical


def find_symbol_duplicates(
    counts_per_reel: Dict[int, Dict[int, Counter]],
) -> Dict[int, Dict[str, List[int]]]:
    """For each reel, return {symbol_name -> [idx, idx, ...]} for duplicates."""
    out: Dict[int, Dict[str, List[int]]] = {}
    for reel, counts in counts_per_reel.items():
        symbol_to_indices: Dict[str, List[int]] = defaultdict(list)
        for idx, counter in counts.items():
            if not counter:
                continue
            (_, name), _ = counter.most_common(1)[0]
            symbol_to_indices[name].append(idx)
        # Keep only duplicates
        out[reel] = {s: sorted(ids) for s, ids in symbol_to_indices.items() if len(ids) > 1}
    return out


def classify_triples(obs: pd.DataFrame) -> dict:
    """For triples: what fraction have matching bar indices?

    Also for non-triples: what bar index patterns produce the highest
    triple rate?
    """
    triples = obs[obs["is_triple"]]
    non_triples = obs[~obs["is_triple"]]

    n_triples = len(triples)
    matching_idx_triples = triples[
        (triples["r1_idx"] == triples["r2_idx"])
        & (triples["r2_idx"] == triples["r3_idx"])
    ]
    return {
        "n_triples": n_triples,
        "matching_idx_triples": len(matching_idx_triples),
        "index_matching_triple_rate": (
            len(matching_idx_triples) / n_triples if n_triples else 0.0
        ),
        "n_non_triples": len(non_triples),
        "example_matching_idx_triples": matching_idx_triples[
            ["spin_num", "r1_idx", "r2_idx", "r3_idx", "r1", "reel_1"]
        ]
        .head(5)
        .to_dict("records"),
        "example_non_matching_idx_triples": triples[
            ~(
                (triples["r1_idx"] == triples["r2_idx"])
                & (triples["r2_idx"] == triples["r3_idx"])
            )
        ][["spin_num", "r1_idx", "r2_idx", "r3_idx", "r1", "reel_1"]]
        .head(5)
        .to_dict("records"),
    }


def write_report(
    out_path: Path,
    canonical_by_reel: Dict[int, Dict[int, str]],
    counts_by_reel: Dict[int, Dict[int, Counter]],
    duplicates_by_reel: Dict[int, Dict[str, List[int]]],
    triple_stats: dict,
    obs_count: int,
) -> None:
    lines = []
    lines.append("# Strip Reconstruction Report")
    lines.append("")
    lines.append(
        f"Reconstructed from {obs_count} settled spin observations, "
        "joined trace.spin_num -> CSV.seq = spin_num + 1."
    )
    lines.append("")

    for reel in (1, 2, 3):
        lines.append(f"## Reel {reel}")
        lines.append("")
        lines.append("| idx | symbol(id) | consistency |")
        lines.append("| --- | --- | --- |")
        canonical = canonical_by_reel.get(reel, {})
        for idx in sorted(canonical):
            lines.append(f"| {idx} | {canonical[idx]} | |")
        lines.append("")

        dups = duplicates_by_reel.get(reel, {})
        if dups:
            lines.append(f"**Duplicate symbols on reel {reel}:**")
            lines.append("")
            for sym, ids in dups.items():
                lines.append(f"- `{sym}` appears at indices: {ids}")
            lines.append("")
        else:
            lines.append(f"_No duplicate symbols detected on reel {reel}._")
            lines.append("")

    lines.append("## Triple index patterns")
    lines.append("")
    lines.append(f"- Total triples observed: **{triple_stats['n_triples']}**")
    lines.append(
        f"- Triples with matching bar indices "
        f"(idx1==idx2==idx3): **{triple_stats['matching_idx_triples']}** "
        f"({triple_stats['index_matching_triple_rate']:.1%})"
    )
    lines.append("")
    if triple_stats["example_matching_idx_triples"]:
        lines.append("**Example matching-index triples:**")
        lines.append("")
        for ex in triple_stats["example_matching_idx_triples"]:
            lines.append(
                f"- spin {ex['spin_num']}: idx=({ex['r1_idx']},{ex['r2_idx']},"
                f"{ex['r3_idx']}) -> {ex['reel_1']} (r_id={ex['r1']})"
            )
        lines.append("")
    if triple_stats["example_non_matching_idx_triples"]:
        lines.append("**Example non-matching-index triples (triple symbol but different indices):**")
        lines.append("")
        for ex in triple_stats["example_non_matching_idx_triples"]:
            lines.append(
                f"- spin {ex['spin_num']}: idx=({ex['r1_idx']},{ex['r2_idx']},"
                f"{ex['r3_idx']}) -> {ex['reel_1']} (r_id={ex['r1']})"
            )
        lines.append("")

    out_path.write_text("\n".join(lines))


def write_enriched_csv(hist: pd.DataFrame, obs: pd.DataFrame, out_path: Path) -> None:
    """Left-join the enriched index columns onto spin_history, write to disk."""
    join = obs[["seq", "r1_idx", "r2_idx", "r3_idx"]]
    merged = hist.merge(join, on="seq", how="left")
    merged.to_csv(out_path, index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, type=Path)
    ap.add_argument("--spin-history", required=True, type=Path)
    ap.add_argument(
        "--report",
        type=Path,
        default=Path("analysis/nuclear/51_strip_layout.md"),
    )
    ap.add_argument("--enriched-csv", type=Path, default=None)
    args = ap.parse_args()

    print(f"Loading trace: {args.trace}")
    bar_idx_by_spin = load_settled_bar_indices(args.trace)
    print(f"  Settled spins with all 3 bar indices: {len(bar_idx_by_spin)}")

    print(f"Loading spin_history: {args.spin_history}")
    hist = pd.read_csv(args.spin_history)
    print(f"  rows: {len(hist)}, seq range: {hist['seq'].min()} -> {hist['seq'].max()}")

    print("Building observation pairs (trace.spin_num -> seq = spin_num + 1)...")
    obs = build_observation_pairs(bar_idx_by_spin, hist)
    print(f"  paired observations: {len(obs)}")

    if len(obs) == 0:
        print("FATAL: no observations after join. Check the seq/spin_num mapping.")
        return

    print("Reconstructing strips from observations...")
    counts_by_reel: Dict[int, Dict[int, Counter]] = {}
    canonical_by_reel: Dict[int, Dict[int, str]] = {}
    for reel in (1, 2, 3):
        counts, canonical = reconstruct_strip(obs, reel)
        counts_by_reel[reel] = counts
        canonical_by_reel[reel] = canonical
        print(f"  reel {reel}: {len(canonical)} unique indices")

    duplicates_by_reel = find_symbol_duplicates(counts_by_reel)
    for reel, dups in duplicates_by_reel.items():
        if dups:
            print(f"  reel {reel} duplicates: {dups}")

    triple_stats = classify_triples(obs)
    print(
        f"Triples: {triple_stats['n_triples']} total, "
        f"{triple_stats['matching_idx_triples']} with matching indices "
        f"({triple_stats['index_matching_triple_rate']:.1%})"
    )

    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_report(
        args.report,
        canonical_by_reel,
        counts_by_reel,
        duplicates_by_reel,
        triple_stats,
        len(obs),
    )
    print(f"Report: {args.report}")

    if args.enriched_csv:
        args.enriched_csv.parent.mkdir(parents=True, exist_ok=True)
        write_enriched_csv(hist, obs, args.enriched_csv)
        print(f"Enriched CSV: {args.enriched_csv}")


if __name__ == "__main__":
    main()
