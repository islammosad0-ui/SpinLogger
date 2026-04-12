#!/usr/bin/env python3
"""
72_vt_signal_sim_v2.py — Corrected VT signal sim based on real 25-VT gap analysis.

Key finding from 70_ corrected: 100% of VTs are preceded by a spin where
r1==r2==r3 ∈ {6, 8}. This script tests that signal and variations.
"""
from __future__ import annotations
import json, sys, csv
from pathlib import Path
from collections import Counter
from typing import List, Dict

try:
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
except Exception:
    try: sys.stdout.reconfigure(line_buffering=True)
    except: pass

def log(msg: str = ""):
    sys.stdout.write(msg + "\n"); sys.stdout.flush()

REPO = Path(__file__).resolve().parents[3]
TRACE = REPO / "data" / "Ahmed" / "il2cpp_trace_20260412_045402.jsonl"
HIST  = REPO / "data" / "Ahmed" / "spin_history_Ahmed_2026-04-08.csv"


def load_and_merge() -> List[dict]:
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
            settled[sn] = {"spin_num": sn, "r1_idx": r1_idx, "r2_idx": r2_idx, "r3_idx": r3_idx}

    hist = {}
    with HIST.open() as f:
        for row in csv.DictReader(f):
            hist[int(row["seq"])] = row

    data = []
    for sn, t in sorted(settled.items()):
        rec = dict(t)
        h = hist.get(sn)
        if h:
            rec["reel_1"] = h.get("reel_1", "")
            rec["is_triple"] = h.get("is_triple", "false") == "true"
        else:
            rec["reel_1"] = ""
            rec["is_triple"] = False
        # VT = CSV ground truth only
        rec["is_vt"] = rec["is_triple"] and rec["reel_1"] in ("accumulation", "spins")
        rec["vt_type"] = ""
        if rec["is_vt"]:
            rec["vt_type"] = "ACC" if rec["reel_1"] == "accumulation" else "SPN"
        data.append(rec)
    return data


def main():
    data = load_and_merge()
    total_vts = sum(1 for d in data if d["is_vt"])
    log(f"Data: {len(data)} spins, {total_vts} VTs (base rate {total_vts/len(data)*100:.1f}%)")
    log(f"Baseline: {len(data)-1} bets → {total_vts} VTs = {(len(data)-1)/total_vts:.1f} bets/hit\n")

    # ================================================================
    # Step 1: Verify the raw finding — what idx does the spin before
    #         each VT actually have?
    # ================================================================
    log("=" * 70)
    log("  STEP 1: RAW IDX OF SPIN IMMEDIATELY BEFORE EACH VT")
    log("=" * 70)
    pre_vt_tuples = []
    for i in range(1, len(data)):
        if data[i]["is_vt"]:
            prev = data[i - 1]
            r1, r2, r3 = prev["r1_idx"], prev["r2_idx"], prev["r3_idx"]
            vt = data[i]
            vt_r1, vt_r2, vt_r3 = vt["r1_idx"], vt["r2_idx"], vt["r3_idx"]
            pre_vt_tuples.append((r1, r2, r3))
            log(f"  VT #{len(pre_vt_tuples):2d} spin={vt['spin_num']:5d} {vt['vt_type']:3s}  "
                f"prev_idx=({r1},{r2},{r3})  vt_idx=({vt_r1},{vt_r2},{vt_r3})")

    log(f"\n  Pre-VT tuple counts:")
    tc = Counter(pre_vt_tuples)
    for t, c in tc.most_common():
        log(f"    {t}: {c} ({c/len(pre_vt_tuples)*100:.0f}%)")

    # ================================================================
    # Step 2: How common are these tuples in the FULL dataset?
    # ================================================================
    log(f"\n{'='*70}")
    log(f"  STEP 2: FREQUENCY OF KEY TUPLES IN FULL DATASET")
    log(f"{'='*70}")
    all_tuples = Counter()
    for d in data:
        r1, r2, r3 = d["r1_idx"], d["r2_idx"], d["r3_idx"]
        if r1 is not None:
            all_tuples[(r1, r2, r3)] += 1

    total = sum(all_tuples.values())
    key_tuples = [(6,6,6), (8,8,8), (0,0,0), (3,3,8), (7,7,8), (3,7,8)]
    for t in key_tuples:
        c = all_tuples[t]
        log(f"  {t}: {c}/{total} ({c/total*100:.2f}%)")

    # ================================================================
    # Step 3: Simulate exact strategies
    # ================================================================
    log(f"\n{'='*70}")
    log(f"  STEP 3: STRATEGY SIMULATIONS")
    log(f"{'='*70}")

    strategies = {
        "Always_bet": lambda r1, r2, r3, hist: True,
        "(6,6,6)_only": lambda r1, r2, r3, hist: r1 == 6 and r2 == 6 and r3 == 6,
        "(8,8,8)_only": lambda r1, r2, r3, hist: r1 == 8 and r2 == 8 and r3 == 8,
        "(6,6,6)_or_(8,8,8)": lambda r1, r2, r3, hist: (r1 == r2 == r3 == 6) or (r1 == r2 == r3 == 8),
        "same_idx_any": lambda r1, r2, r3, hist: r1 == r2 == r3,
        "r1=6_or_8": lambda r1, r2, r3, hist: r1 in (6, 8),
        "r2=6_or_8": lambda r1, r2, r3, hist: r2 in (6, 8),
        "r3=6_or_8": lambda r1, r2, r3, hist: r3 in (6, 8),
        "all_reels_6or8": lambda r1, r2, r3, hist: r1 in (6, 8) and r2 in (6, 8) and r3 in (6, 8),
        "any2_reels_6or8": lambda r1, r2, r3, hist: sum(1 for v in (r1,r2,r3) if v in (6,8)) >= 2,
        "r1r2_same_6or8": lambda r1, r2, r3, hist: r1 == r2 and r1 in (6, 8),
        "r1==r2==r3_in_6or8": lambda r1, r2, r3, hist: r1 == r2 == r3 and r1 in (6, 8),
        "same_idx+spread0": lambda r1, r2, r3, hist: r1 == r2 == r3,
        # Relaxed: at least 2 reels at same value in {6,8}
        "2of3_at_6or8": lambda r1, r2, r3, hist: (
            (r1 in (6,8) and r2 in (6,8) and r1 == r2) or
            (r1 in (6,8) and r3 in (6,8) and r1 == r3) or
            (r2 in (6,8) and r3 in (6,8) and r2 == r3)
        ),
    }

    log(f"\n  {'strategy':<25s}  {'bets':>6s}  {'caught':>7s}  {'missed':>7s}  "
        f"{'catch%':>7s}  {'prec%':>7s}  {'bets/hit':>8s}  {'saved%':>7s}")
    log(f"  {'-'*90}")

    for name, fn in strategies.items():
        bets = 0
        caught = 0
        missed = 0
        for i in range(len(data) - 1):
            spin = data[i]
            r1, r2, r3 = spin["r1_idx"], spin["r2_idx"], spin["r3_idx"]
            if r1 is None: continue
            next_vt = data[i + 1]["is_vt"]

            if fn(r1, r2, r3, data[:i]):
                bets += 1
                if next_vt: caught += 1
            else:
                if next_vt: missed += 1

        catch_pct = caught / total_vts * 100 if total_vts > 0 else 0
        prec = caught / bets * 100 if bets > 0 else 0
        bph = bets / caught if caught > 0 else float("inf")
        saved = (1 - bets / (len(data) - 1)) * 100

        log(f"  {name:<25s}  {bets:>6d}  {caught:>7d}  {missed:>7d}  "
            f"{catch_pct:>6.1f}%  {prec:>6.1f}%  {bph:>8.1f}  {saved:>6.1f}%")

    # ================================================================
    # Step 4: Per-VT detail for the best strategy
    # ================================================================
    log(f"\n{'='*70}")
    log(f"  STEP 4: PER-VT DETAIL — (6,6,6) or (8,8,8) strategy")
    log(f"{'='*70}")
    caught_list = []
    missed_list = []
    for i in range(1, len(data)):
        if not data[i]["is_vt"]:
            continue
        prev = data[i - 1]
        r1, r2, r3 = prev["r1_idx"], prev["r2_idx"], prev["r3_idx"]
        hit = (r1 == r2 == r3 == 6) or (r1 == r2 == r3 == 8)
        vt = data[i]
        if hit:
            caught_list.append((i, vt, prev))
        else:
            missed_list.append((i, vt, prev))

    log(f"\n  CAUGHT ({len(caught_list)}):")
    for idx, vt, prev in caught_list:
        log(f"    spin={vt['spin_num']:5d} {vt['vt_type']:3s}  prev=({prev['r1_idx']},{prev['r2_idx']},{prev['r3_idx']})  "
            f"vt=({vt['r1_idx']},{vt['r2_idx']},{vt['r3_idx']})")

    log(f"\n  MISSED ({len(missed_list)}):")
    for idx, vt, prev in missed_list:
        log(f"    spin={vt['spin_num']:5d} {vt['vt_type']:3s}  prev=({prev['r1_idx']},{prev['r2_idx']},{prev['r3_idx']})  "
            f"vt=({vt['r1_idx']},{vt['r2_idx']},{vt['r3_idx']})")

    # ================================================================
    # Step 5: False positive detail — when (6,6,6) or (8,8,8) fires
    #         but next spin is NOT a VT
    # ================================================================
    log(f"\n{'='*70}")
    log(f"  STEP 5: FALSE POSITIVES — (6,6,6)/(8,8,8) fires but no VT")
    log(f"{'='*70}")
    fp_count = 0
    for i in range(len(data) - 1):
        spin = data[i]
        r1, r2, r3 = spin["r1_idx"], spin["r2_idx"], spin["r3_idx"]
        if r1 is None: continue
        if (r1 == r2 == r3 == 6) or (r1 == r2 == r3 == 8):
            if not data[i + 1]["is_vt"]:
                fp_count += 1
                nxt = data[i + 1]
                log(f"    spin={spin['spin_num']:5d} idx=({r1},{r2},{r3})  "
                    f"next={nxt['spin_num']:5d} reel_1={nxt['reel_1']}  "
                    f"is_triple={nxt['is_triple']}  next_idx=({nxt['r1_idx']},{nxt['r2_idx']},{nxt['r3_idx']})")
    log(f"\n  Total false positives: {fp_count}")

    # ================================================================
    # Step 6: What about using the broader "all_reels_6or8" to catch more?
    # ================================================================
    log(f"\n{'='*70}")
    log(f"  STEP 6: MISSED VTs — what would catch them?")
    log(f"{'='*70}")
    for idx, vt, prev in missed_list:
        r1, r2, r3 = prev["r1_idx"], prev["r2_idx"], prev["r3_idx"]
        all_6or8 = all(v in (6, 8) for v in (r1, r2, r3))
        any2_6or8 = sum(1 for v in (r1, r2, r3) if v in (6, 8)) >= 2
        any1_6or8 = sum(1 for v in (r1, r2, r3) if v in (6, 8)) >= 1
        log(f"    spin={vt['spin_num']:5d} {vt['vt_type']:3s}  prev=({r1},{r2},{r3})  "
            f"all_6or8={all_6or8}  any2_6or8={any2_6or8}  any1_6or8={any1_6or8}")

    log(f"\n{'='*70}")
    log(f"  DONE")
    log(f"{'='*70}")


if __name__ == "__main__":
    main()
