#!/usr/bin/env python3
"""IL2CPP trace decoder — reverse engineer memory layouts against spin_history ground truth.

Six stages:
    1. Load & segment   - group JSONL snapshots by spin_num
    2. Payline sanity   - validate sym1/2/3 chain matches spin_history r1/r2/r3
    3. Field change-map - find fields that correlate with spin_history columns
    4. Strip decoder    - lock (stride, inner_offset) for m_SymbolElements
    5. Pity counter hunt - find offsets for real session + global pity counters
    6. Report           - write layout report to 50_il2cpp_layout_report.md
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class Snapshot:
    t: str
    mono_ms: int
    spin_num: int
    spinning: bool
    bet_state: int
    phase: str
    instance_ptr: str
    fields: dict
    hex: dict


@dataclass
class Spin:
    spin_num: int
    animation: List[Snapshot] = field(default_factory=list)
    settled: Optional[Snapshot] = None


def load_jsonl(path: Path) -> List[Snapshot]:
    out = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            out.append(Snapshot(**{k: d.get(k) for k in Snapshot.__dataclass_fields__}))
    return out


def segment_by_spin(snaps: List[Snapshot]) -> Dict[int, Spin]:
    buckets: Dict[int, Spin] = {}
    for s in snaps:
        sp = buckets.setdefault(s.spin_num, Spin(spin_num=s.spin_num))
        if s.spinning:
            sp.animation.append(s)
        else:
            # A settled snapshot supersedes any earlier settled one in this spin
            sp.settled = s
    return buckets


def _extract_payline_from_settled(snap: Snapshot) -> Optional[tuple]:
    """Walk fields → SlotResult → SlotSymbol3 → symbol1/2/3 → return (s1,s2,s3) or None."""
    for key, cls_fields in snap.fields.items():
        if key.startswith("SlotSymbol3@"):
            try:
                return (
                    cls_fields["symbol1"]["i32"],
                    cls_fields["symbol2"]["i32"],
                    cls_fields["symbol3"]["i32"],
                )
            except KeyError:
                return None
    return None


def stage2_payline_sanity(buckets: Dict[int, Spin], hist: pd.DataFrame) -> dict:
    """Cross-reference memory payline (sym1/2/3) with spin_history r1/r2/r3."""
    checked = 0
    matches = 0
    mismatches = []
    hist_lookup = hist.set_index("seq")[["r1", "r2", "r3"]].to_dict("index")

    for spin_num, spin in buckets.items():
        if spin.settled is None:
            continue
        mem = _extract_payline_from_settled(spin.settled)
        if mem is None:
            continue
        if spin_num not in hist_lookup:
            continue
        checked += 1
        gt = hist_lookup[spin_num]
        if mem == (gt["r1"], gt["r2"], gt["r3"]):
            matches += 1
        else:
            mismatches.append({"spin_num": spin_num, "mem": mem, "hist": gt})

    return {
        "n_spins_checked": checked,
        "n_matches": matches,
        "match_rate": matches / checked if checked else 0.0,
        "mismatches": mismatches,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, type=Path, help="Path to JSONL trace file")
    ap.add_argument("--spin-history", required=True, type=Path, help="Ground-truth spin_history CSV")
    ap.add_argument("--report", default=Path("50_il2cpp_layout_report.md"), type=Path)
    args = ap.parse_args()

    snaps = load_jsonl(args.trace)
    buckets = segment_by_spin(snaps)
    print(f"Loaded {len(snaps)} snapshots across {len(buckets)} spins")


if __name__ == "__main__":
    main()
