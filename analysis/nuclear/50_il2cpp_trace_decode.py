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


def stage3_field_change_map(buckets: Dict[int, Spin], hist: pd.DataFrame) -> list:
    """For every (class, field) pair observed in settled snapshots, classify behavior."""
    series: Dict[tuple, List[tuple]] = {}
    for spin_num in sorted(buckets):
        settled = buckets[spin_num].settled
        if settled is None:
            continue
        for class_key, cls_fields in settled.fields.items():
            class_name = class_key.split("@", 1)[0]
            for fname, fdata in cls_fields.items():
                if not isinstance(fdata, dict) or "i32" not in fdata:
                    continue
                series.setdefault((class_name, fname), []).append(
                    (spin_num, fdata["i32"], fdata.get("u64", 0), fdata.get("ptr", "0x0"))
                )

    hist_lookup = hist.set_index("seq")

    out = []
    for (cls, fname), points in series.items():
        vals = [p[1] for p in points]
        uniq = set(vals)
        is_constant = len(uniq) == 1
        unique_count = len(uniq)

        if is_constant:
            type_guess = "constant"
        elif all(0 <= v <= 1 for v in vals):
            type_guess = "bool_like"
        elif all(1 <= v <= 50 for v in vals):
            type_guess = "symbol_like"
        elif all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1)):
            type_guess = "counter_like"
        elif any(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
            type_guess = "resetting_counter"
        else:
            type_guess = "unknown"

        correlations = {}
        for col in ("r1", "r2", "r3", "is_triple", "sa_spins", "coins_won", "bet_level"):
            if col not in hist_lookup.columns:
                continue
            matches = 0
            checked = 0
            for spin_num, i32, u64, ptr in points:
                if spin_num not in hist_lookup.index:
                    continue
                checked += 1
                gt = hist_lookup.loc[spin_num, col]
                if gt == i32 or gt == u64:
                    matches += 1
            if checked:
                correlations[col] = matches / checked

        out.append({
            "class": cls,
            "field": fname,
            "is_constant": is_constant,
            "unique_count": unique_count,
            "type_guess": type_guess,
            "correlations": correlations,
        })

    out.sort(key=lambda r: (
        r["is_constant"],
        -max(r["correlations"].values()) if r["correlations"] else 0,
    ))
    return out


def _unpack_array_bytes(hex_blob: dict, stride: int, inner_offset: int, array_len: int) -> List[int]:
    """Return list of ints decoded from the array payload using (stride, inner_offset)."""
    raw = bytes.fromhex(hex_blob["bytes"])
    header = hex_blob["header_size"]
    out = []
    for i in range(array_len):
        start = header + i * stride + inner_offset
        if start + 4 > len(raw):
            out.append(None)
            continue
        out.append(int.from_bytes(raw[start:start + 4], "little", signed=True))
    return out


def stage4_strip_decoder(buckets: Dict[int, Spin], hist: pd.DataFrame, reel: int) -> dict:
    """Find (stride, inner_offset) for m_SymbolElements on bar<reel>."""
    hist_lookup = hist.set_index("seq")
    r_col = f"r{reel}"
    candidates = [(s, o) for s in (4, 8, 12, 16, 24, 32) for o in (0, 4, 8, 12, 16)]

    def score(stride: int, inner_offset: int):
        hits = 0
        checked = 0
        for spin_num, spin in buckets.items():
            if spin.settled is None or spin_num not in hist_lookup.index:
                continue
            gt = hist_lookup.loc[spin_num, r_col]
            hex_key = next(
                (k for k in spin.settled.hex if k.startswith(f"slotBar{reel}.m_SymbolElements@")),
                None,
            )
            if hex_key is None:
                continue
            blob = spin.settled.hex[hex_key]
            if not isinstance(blob, dict):
                continue
            bar_key = next(
                (k for k in spin.settled.fields if k.startswith(f"SlotBarManager_{reel}@")),
                None,
            )
            if bar_key is None:
                continue
            idx = spin.settled.fields[bar_key].get("resultSymbolIndex", {}).get("i32")
            if idx is None:
                continue
            elements = _unpack_array_bytes(blob, stride, inner_offset, blob["array_len"])
            if 0 <= idx < len(elements) and elements[idx] == gt:
                hits += 1
            checked += 1
        return hits, checked

    best = {"stride": None, "inner_offset": None, "match_rate": 0.0, "hits": 0, "checked": 0}
    for stride, inner_offset in candidates:
        hits, checked = score(stride, inner_offset)
        if checked == 0:
            continue
        rate = hits / checked
        if rate > best["match_rate"]:
            best = {
                "stride": stride,
                "inner_offset": inner_offset,
                "match_rate": rate,
                "hits": hits,
                "checked": checked,
            }
    return best


def stage5_pity_counter_hunt(buckets: Dict[int, Spin], hist: pd.DataFrame, fail_threshold: int) -> list:
    """Identify pity counter candidates by monotonic + reset behavior."""
    hist_lookup = hist.set_index("seq")
    ordered = sorted(buckets.keys())
    triple_map = {s: bool(hist_lookup.loc[s, "is_triple"])
                  for s in ordered if s in hist_lookup.index and "is_triple" in hist_lookup.columns}

    series: Dict[tuple, List[tuple]] = {}
    for spin_num in ordered:
        settled = buckets[spin_num].settled
        if settled is None or spin_num not in triple_map:
            continue
        for class_key, cls_fields in settled.fields.items():
            class_name = class_key.split("@", 1)[0]
            for fname, fdata in cls_fields.items():
                if not isinstance(fdata, dict) or "i32" not in fdata:
                    continue
                series.setdefault((class_name, fname), []).append(
                    (spin_num, fdata["i32"], triple_map[spin_num])
                )

    candidates = []
    for (cls, fname), points in series.items():
        vals = [p[1] for p in points]
        if len(vals) < 3:
            continue
        if len(set(vals)) == 1:
            continue

        non_triple_vals = [v for (_, v, is_tr) in points if not is_tr]
        monotonic = all(non_triple_vals[i] <= non_triple_vals[i + 1]
                        for i in range(len(non_triple_vals) - 1))
        resets = any(v == 0 for (_, v, is_tr) in points if is_tr)
        max_val = max(vals)
        near_threshold = max_val <= fail_threshold + 2

        if monotonic and resets and near_threshold:
            candidates.append({
                "class": cls,
                "field": fname,
                "monotonic_between_triples": True,
                "resets_on_triple": True,
                "max_value": max_val,
                "n_samples": len(points),
            })

    candidates.sort(key=lambda c: (-c["n_samples"], abs(c["max_value"] - fail_threshold)))
    return candidates


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
