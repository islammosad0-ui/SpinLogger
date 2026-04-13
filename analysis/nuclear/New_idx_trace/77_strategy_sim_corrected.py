#!/usr/bin/env python3
"""
77_strategy_sim_corrected.py — Full strategy simulation with KPIs.

Corrected off-by-one alignment. Runs separate sims for ALL/ACC/SPN targets
with comprehensive strategies including pity timers, idx combos, non-VT triple
markers, momentum, and compound signals.
"""
import json, csv, sys
from pathlib import Path
from collections import Counter

try:
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
except Exception:
    try: sys.stdout.reconfigure(line_buffering=True)
    except: pass

def log(msg=""):
    sys.stdout.write(msg + "\n"); sys.stdout.flush()

REPO = Path(__file__).resolve().parents[3]
TRACE = REPO / "data" / "Ahmed" / "il2cpp_trace_20260412_045402.jsonl"
HIST  = REPO / "data" / "Ahmed" / "spin_history_Ahmed_2026-04-08.csv"


def load_corrected():
    settled = {}
    with TRACE.open() as f:
        for line in f:
            d = json.loads(line.strip())
            if d.get("spinning") != 0: continue
            sn = d["spin_num"]
            fields = d.get("fields", {})
            r1 = r2 = r3 = None
            for cls_key, cls_fields in fields.items():
                if cls_key.startswith("SlotBarManager_1"):
                    r1 = cls_fields.get("resultSymbolIndex", {}).get("i32")
                elif cls_key.startswith("SlotBarManager_2"):
                    r2 = cls_fields.get("resultSymbolIndex", {}).get("i32")
                elif cls_key.startswith("SlotBarManager_3"):
                    r3 = cls_fields.get("resultSymbolIndex", {}).get("i32")
            settled[sn] = (r1, r2, r3)
    hist = {}
    with HIST.open() as f:
        for row in csv.DictReader(f):
            hist[int(row["seq"])] = row
    data = []
    for sn, row in sorted(hist.items()):
        prev_sn = sn - 1
        r1 = r2 = r3 = None
        if prev_sn in settled:
            r1, r2, r3 = settled[prev_sn]
        is_triple = row["is_triple"] == "true"
        reel_1 = row.get("reel_1", "")
        is_vt = is_triple and reel_1 in ("accumulation", "spins")
        vt_type = ""
        if is_vt:
            vt_type = "ACC" if reel_1 == "accumulation" else "SPN"
        data.append({
            "spin_num": sn, "r1": r1, "r2": r2, "r3": r3,
            "reel_1": reel_1, "is_triple": is_triple,
            "is_vt": is_vt, "vt_type": vt_type,
        })
    return data


def bucket(v):
    if v <= 2: return "L"
    if v <= 5: return "M"
    return "H"


def run_sim(idx_data, label, is_target_fn):
    N = len(idx_data)
    total_targets = sum(1 for d in idx_data if is_target_fn(d))
    baseline = total_targets / (N - 1) if N > 1 else 0

    log(f"\n{'='*90}")
    log(f"  {label}")
    log(f"  {N} spins, {total_targets} targets, baseline={baseline*100:.2f}%, "
        f"baseline bets/hit={((N-1)/total_targets):.1f}")
    log(f"{'='*90}")

    if total_targets < 3:
        log(f"  Too few targets, skipping")
        return

    # Build state for each spin
    states = []
    last_target_pos = -1
    last_acc_pos = -1
    last_spn_pos = -1
    last_any_triple_pos = -1
    last_nv_triple_pos = -1  # non-VT triple
    prev_r1 = prev_r2 = prev_r3 = 4  # neutral init
    prev_sum = 12

    for i, d in enumerate(idx_data):
        gap_vt = i - last_target_pos if last_target_pos >= 0 else 999
        gap_acc = i - last_acc_pos if last_acc_pos >= 0 else 999
        gap_spn = i - last_spn_pos if last_spn_pos >= 0 else 999
        gap_tri = i - last_any_triple_pos if last_any_triple_pos >= 0 else 999
        gap_nv_tri = i - last_nv_triple_pos if last_nv_triple_pos >= 0 else 999

        s = d["r1"] + d["r2"] + d["r3"]
        spread = max(d["r1"], d["r2"], d["r3"]) - min(d["r1"], d["r2"], d["r3"])
        all_diff = d["r1"] != d["r2"] and d["r1"] != d["r3"] and d["r2"] != d["r3"]
        combo = bucket(d["r1"]) + bucket(d["r2"]) + bucket(d["r3"])

        # Momentum
        delta_sum = s - prev_sum
        abs_delta_r1 = abs(d["r1"] - prev_r1)

        states.append({
            "gap_vt": gap_vt, "gap_acc": gap_acc, "gap_spn": gap_spn,
            "gap_tri": gap_tri, "gap_nv_tri": gap_nv_tri,
            "r1": d["r1"], "r2": d["r2"], "r3": d["r3"],
            "sum": s, "spread": spread, "all_diff": all_diff, "combo": combo,
            "is_triple": d["is_triple"], "is_vt": d["is_vt"],
            "reel_1": d["reel_1"], "vt_type": d["vt_type"],
            "delta_sum": delta_sum, "abs_delta_r1": abs_delta_r1,
            "nxt_target": is_target_fn(idx_data[i + 1]) if i + 1 < N else False,
        })

        if is_target_fn(d):
            last_target_pos = i
        if d["vt_type"] == "ACC":
            last_acc_pos = i
        if d["vt_type"] == "SPN":
            last_spn_pos = i
        if d["is_triple"]:
            last_any_triple_pos = i
            if not d["is_vt"]:
                last_nv_triple_pos = i

        prev_r1, prev_r2, prev_r3 = d["r1"], d["r2"], d["r3"]
        prev_sum = s

    # Define strategies
    strategies = {}

    # Baseline
    strategies["Always_bet"] = lambda s: True

    # Pure pity timer
    for thresh in [20, 25, 30, 35, 40, 50, 60, 80]:
        t = thresh
        strategies[f"gap>={t}"] = lambda s, t=t: s["gap_vt"] >= t

    # Pity + idx sum
    for gt in [20, 30, 40]:
        for sm in [12, 15, 18]:
            strategies[f"gap>={gt}+sum>={sm}"] = lambda s, g=gt, m=sm: s["gap_vt"] >= g and s["sum"] >= m

    # Pity + r3 value
    for gt in [20, 30, 40]:
        strategies[f"gap>={gt}+r3>=5"] = lambda s, g=gt: s["gap_vt"] >= g and s["r3"] >= 5
        strategies[f"gap>={gt}+r3==8"] = lambda s, g=gt: s["gap_vt"] >= g and s["r3"] == 8
        strategies[f"gap>={gt}+r3<=4"] = lambda s, g=gt: s["gap_vt"] >= g and s["r3"] <= 4

    # Pity + spread / pair patterns
    for gt in [20, 30]:
        strategies[f"gap>={gt}+all_diff"] = lambda s, g=gt: s["gap_vt"] >= g and s["all_diff"]
        strategies[f"gap>={gt}+spread<=3"] = lambda s, g=gt: s["gap_vt"] >= g and s["spread"] <= 3
        strategies[f"gap>={gt}+spread>=5"] = lambda s, g=gt: s["gap_vt"] >= g and s["spread"] >= 5

    # Pity + reel combos
    for gt in [20, 30]:
        strategies[f"gap>={gt}+HMM"] = lambda s, g=gt: s["gap_vt"] >= g and s["combo"] == "HMM"
        strategies[f"gap>={gt}+MHM"] = lambda s, g=gt: s["gap_vt"] >= g and s["combo"] == "MHM"
        strategies[f"gap>={gt}+MML"] = lambda s, g=gt: s["gap_vt"] >= g and s["combo"] == "MML"
        strategies[f"gap>={gt}+HHH"] = lambda s, g=gt: s["gap_vt"] >= g and s["combo"] == "HHH"

    # Pity + specific reels
    for gt in [20, 30]:
        strategies[f"gap>={gt}+r1=3or7"] = lambda s, g=gt: s["gap_vt"] >= g and s["r1"] in (3, 7)
        strategies[f"gap>={gt}+r2=7"] = lambda s, g=gt: s["gap_vt"] >= g and s["r2"] == 7
        strategies[f"gap>={gt}+r2>=5"] = lambda s, g=gt: s["gap_vt"] >= g and s["r2"] >= 5

    # Non-VT triple as marker
    for d in [3, 5, 8, 10]:
        strategies[f"nv_tri<={d}"] = lambda s, d=d: s["gap_nv_tri"] <= d and s["gap_nv_tri"] >= 1
    for gt in [20, 30]:
        for d in [3, 5, 8]:
            strategies[f"gap>={gt}+nv_tri<={d}"] = lambda s, g=gt, d=d: s["gap_vt"] >= g and 1 <= s["gap_nv_tri"] <= d

    # Pity + non-triple reel_1 symbol
    for gt in [20, 30]:
        strategies[f"gap>={gt}+prev_steal"] = lambda s, g=gt: s["gap_vt"] >= g and not s["is_triple"] and s["reel_1"] == "steal"
        strategies[f"gap>={gt}+prev_accum"] = lambda s, g=gt: s["gap_vt"] >= g and not s["is_triple"] and s["reel_1"] == "accumulation"

    # Momentum-based
    for gt in [20, 30]:
        strategies[f"gap>={gt}+low_momentum"] = lambda s, g=gt: s["gap_vt"] >= g and s["abs_delta_r1"] <= 1
        strategies[f"gap>={gt}+delta_sum>0"] = lambda s, g=gt: s["gap_vt"] >= g and s["delta_sum"] > 0
        strategies[f"gap>={gt}+delta_sum>=5"] = lambda s, g=gt: s["gap_vt"] >= g and s["delta_sum"] >= 5

    # ACC-specific pity using separate counter
    strategies["gap_acc>=60"] = lambda s: s["gap_acc"] >= 60
    strategies["gap_acc>=80"] = lambda s: s["gap_acc"] >= 80
    strategies["gap_acc>=100"] = lambda s: s["gap_acc"] >= 100
    strategies["gap_acc>=60+r1=3or7"] = lambda s: s["gap_acc"] >= 60 and s["r1"] in (3, 7)
    strategies["gap_acc>=80+r1=3or7"] = lambda s: s["gap_acc"] >= 80 and s["r1"] in (3, 7)

    # SPN-specific pity
    strategies["gap_spn>=40"] = lambda s: s["gap_spn"] >= 40
    strategies["gap_spn>=50"] = lambda s: s["gap_spn"] >= 50
    strategies["gap_spn>=60"] = lambda s: s["gap_spn"] >= 60
    strategies["gap_spn>=40+r3>=5"] = lambda s: s["gap_spn"] >= 40 and s["r3"] >= 5
    strategies["gap_spn>=50+r3>=5"] = lambda s: s["gap_spn"] >= 50 and s["r3"] >= 5

    # Run all strategies
    results = []
    for name, fn in strategies.items():
        bets = caught = missed = 0
        for s in states[:-1]:  # exclude last spin (no next)
            if fn(s):
                bets += 1
                if s["nxt_target"]: caught += 1
            else:
                if s["nxt_target"]: missed += 1

        if bets == 0:
            continue

        catch_pct = caught / total_targets * 100
        prec = caught / bets * 100
        bph = bets / caught if caught > 0 else float("inf")
        saved = (1 - bets / (N - 1)) * 100
        lift = prec / (baseline * 100) if baseline > 0 else 0

        results.append({
            "name": name, "bets": bets, "caught": caught, "missed": missed,
            "catch_pct": catch_pct, "prec": prec, "bph": bph,
            "saved": saved, "lift": lift,
        })

    # Sort by precision (descending), then by caught (descending)
    results.sort(key=lambda r: (-r["prec"], -r["caught"]))

    # Print header
    log(f"\n  {'strategy':<30s}  {'bets':>5s}  {'hit':>4s}  {'miss':>4s}  "
        f"{'catch%':>7s}  {'prec%':>7s}  {'lift':>5s}  {'bets/hit':>8s}  {'saved%':>7s}")
    log(f"  {'-'*100}")

    shown = set()
    for r in results:
        # Skip duplicates and useless (0 caught)
        key = (r["bets"], r["caught"])
        if r["caught"] == 0: continue

        marker = ""
        if r["prec"] >= baseline * 100 * 2 and r["caught"] >= 3:
            marker = " ***"
        elif r["prec"] >= baseline * 100 * 1.5 and r["caught"] >= 2:
            marker = " **"

        log(f"  {r['name']:<30s}  {r['bets']:>5d}  {r['caught']:>4d}  {r['missed']:>4d}  "
            f"{r['catch_pct']:>6.1f}%  {r['prec']:>6.2f}%  {r['lift']:>4.1f}x  "
            f"{r['bph']:>8.1f}  {r['saved']:>6.1f}%{marker}")

    # Top picks summary
    log(f"\n  --- TOP PICKS (prec >= 2x baseline, caught >= 3) ---")
    top = [r for r in results if r["lift"] >= 2.0 and r["caught"] >= 3]
    top.sort(key=lambda r: (-r["caught"], -r["prec"]))
    for r in top[:15]:
        log(f"  {r['name']:<30s}  prec={r['prec']:.2f}% ({r['lift']:.1f}x)  "
            f"catch={r['catch_pct']:.0f}%  bets/hit={r['bph']:.1f}  saved={r['saved']:.0f}%")


def main():
    data = load_corrected()
    idx_data = [d for d in data if d["r1"] is not None]

    total_vts = sum(1 for d in idx_data if d["is_vt"])
    total_acc = sum(1 for d in idx_data if d["vt_type"] == "ACC")
    total_spn = sum(1 for d in idx_data if d["vt_type"] == "SPN")
    log(f"Data: {len(idx_data)} spins, {total_vts} VTs ({total_acc} ACC, {total_spn} SPN)")

    # ALL VTs
    run_sim(idx_data, "ALL VTs", lambda d: d["is_vt"])

    # ACC only
    run_sim(idx_data, "ACC VTs ONLY", lambda d: d["vt_type"] == "ACC")

    # SPN only
    run_sim(idx_data, "SPN VTs ONLY", lambda d: d["vt_type"] == "SPN")

    log(f"\n{'='*90}")
    log(f"  DONE")
    log(f"{'='*90}")


if __name__ == "__main__":
    main()
