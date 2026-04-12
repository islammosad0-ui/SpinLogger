#!/usr/bin/env python3
"""Dump every spin with idx, reels, signal/VT markers, and gap boundaries."""
import json, csv, sys
from pathlib import Path

try:
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
except Exception:
    try: sys.stdout.reconfigure(line_buffering=True)
    except: pass

REPO = Path(__file__).resolve().parents[3]
TRACE = REPO / "data" / "Ahmed" / "il2cpp_trace_20260412_045402.jsonl"
HIST  = REPO / "data" / "Ahmed" / "spin_history_Ahmed_2026-04-08.csv"

# Load trace idx
settled = {}
with TRACE.open() as f:
    for line in f:
        d = json.loads(line.strip())
        if d.get("spinning") != 0: continue
        sn = d["spin_num"]
        fields = d.get("fields", {})
        r1_idx = r2_idx = r3_idx = None
        for cls_key, cls_fields in fields.items():
            if cls_key.startswith("SlotBarManager_1"):
                r1_idx = cls_fields.get("resultSymbolIndex", {}).get("i32")
            elif cls_key.startswith("SlotBarManager_2"):
                r2_idx = cls_fields.get("resultSymbolIndex", {}).get("i32")
            elif cls_key.startswith("SlotBarManager_3"):
                r3_idx = cls_fields.get("resultSymbolIndex", {}).get("i32")
        settled[sn] = {"r1": r1_idx, "r2": r2_idx, "r3": r3_idx}

# Load CSV
hist = {}
with HIST.open() as f:
    for row in csv.DictReader(f):
        hist[int(row["seq"])] = row

# Build full spin list
spins = []
for sn in sorted(settled.keys()):
    t = settled[sn]
    h = hist.get(sn)
    reel_1 = h["reel_1"] if h else ""
    reel_2 = h["reel_2"] if h else ""
    reel_3 = h["reel_3"] if h else ""
    is_triple = h["is_triple"] == "true" if h else False
    is_vt = is_triple and reel_1 in ("accumulation", "spins")
    vt_type = ""
    if is_vt:
        vt_type = "ACC" if reel_1 == "accumulation" else "SPN"

    is_signal = (t["r1"] == t["r2"] == t["r3"] == 6) or (t["r1"] == t["r2"] == t["r3"] == 8)

    spins.append({
        "sn": sn, "r1": t["r1"], "r2": t["r2"], "r3": t["r3"],
        "reel_1": reel_1, "reel_2": reel_2, "reel_3": reel_3,
        "is_triple": is_triple, "is_vt": is_vt, "vt_type": vt_type,
        "is_signal": is_signal,
    })

# Print header
hdr = f"{'row':>5s}  {'spin#':>6s}  {'idx(r1,r2,r3)':>13s}  {'reel1':>5s} {'reel2':>5s} {'reel3':>5s}  {'tri':>3s}  flags"
print(hdr)
print("=" * 110)

last_vt_row = -1
gap_num = 0

for i, s in enumerate(spins):
    idx_str = f"({s['r1']},{s['r2']},{s['r3']})"

    r1_short = s["reel_1"][:5] if s["reel_1"] else "-"
    r2_short = s["reel_2"][:5] if s["reel_2"] else "-"
    r3_short = s["reel_3"][:5] if s["reel_3"] else "-"

    tri = "3x" if s["is_triple"] else ""

    flags = []

    # Signal marker
    if s["is_signal"]:
        sig_type = "(6,6,6)" if s["r1"] == 6 else "(8,8,8)"
        flags.append(f">>> MAX BET {sig_type} <<<")

    # Next-after-signal marker
    if i > 0 and spins[i - 1]["is_signal"]:
        flags.append("<-- NEXT SPIN AFTER SIGNAL")

    # VT marker
    if s["is_vt"]:
        gap = i - last_vt_row - 1 if last_vt_row >= 0 else i
        gap_num += 1
        flags.append(f"**VT#{gap_num} {s['vt_type']}** (gap={gap})")
        last_vt_row = i
    elif s["is_triple"]:
        flags.append(f"(triple: {s['reel_1']})")

    flag_str = "  ".join(flags)

    # Print separator before VT gap
    if s["is_vt"] and gap_num > 1:
        print(f"{'':>5s}  {'':>6s}  {'':>13s}  {'':>5s} {'':>5s} {'':>5s}  {'':>3s}  --- gap {gap_num}: {gap} spins ---")

    print(f"{i:5d}  {s['sn']:6d}  {idx_str:>13s}  {r1_short:>5s} {r2_short:>5s} {r3_short:>5s}  {tri:>3s}  {flag_str}")
