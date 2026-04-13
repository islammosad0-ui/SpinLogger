#!/usr/bin/env python3
"""74_corrected_gap_analysis.py — Rerun gap analysis with corrected off-by-one alignment.

The trace's resultSymbolIndex at spin N actually belongs to CSV spin N+1.
This script shifts the alignment and reruns all strategy simulations.
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

IDX_SYMBOL = {0: "attack", 1: "coin", 2: "shield", 3: "goldSack",
              4: "steal", 5: "coin", 6: "spins", 7: "goldSack", 8: "accumulation"}


def load_corrected():
    """Load trace + CSV with corrected alignment: trace[N] idx -> CSV spin N+1."""
    settled = {}
    with TRACE.open() as f:
        for line in f:
            d = json.loads(line.strip())
            if d.get("spinning") != 0:
                continue
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

    # CORRECTED: trace[N] idx belongs to CSV spin N+1
    # So CSV spin S gets idx from trace[S-1]
    data = []
    for sn, row in sorted(hist.items()):
        prev_sn = sn - 1
        if prev_sn in settled:
            r1, r2, r3 = settled[prev_sn]
        else:
            r1 = r2 = r3 = None

        is_triple = row["is_triple"] == "true"
        reel_1 = row.get("reel_1", "")
        is_vt = is_triple and reel_1 in ("accumulation", "spins")
        vt_type = ""
        if is_vt:
            vt_type = "ACC" if reel_1 == "accumulation" else "SPN"

        data.append({
            "spin_num": sn,
            "r1_idx": r1, "r2_idx": r2, "r3_idx": r3,
            "reel_1": reel_1,
            "is_triple": is_triple,
            "is_vt": is_vt,
            "vt_type": vt_type,
        })
    return data


def main():
    data = load_corrected()
    # Only analyze spins WITH idx data
    idx_data = [d for d in data if d["r1_idx"] is not None]
    total_vts = sum(1 for d in idx_data if d["is_vt"])
    log(f"Corrected data: {len(idx_data)} spins with idx, {total_vts} VTs")
    log(f"Baseline VT rate: {total_vts/len(idx_data)*100:.2f}%")
    log(f"Baseline: {len(idx_data)-1} bets -> {total_vts} VTs = {(len(idx_data)-1)/total_vts:.1f} bets/hit")
    log()

    # ================================================================
    # ANALYSIS 1: What idx patterns appear N-1 before a VT?
    # ================================================================
    log("=" * 70)
    log("  ANALYSIS 1: IDX OF REAL PREVIOUS SPIN BEFORE EACH VT")
    log("=" * 70)

    pre_vt = []
    for i in range(1, len(idx_data)):
        if idx_data[i]["is_vt"]:
            prev = idx_data[i - 1]
            t = (prev["r1_idx"], prev["r2_idx"], prev["r3_idx"])
            pre_vt.append((t, prev, idx_data[i]))
            log(f"  VT spin={idx_data[i]['spin_num']:6d} {idx_data[i]['vt_type']:3s}  "
                f"prev_idx={t}  prev_triple={prev['is_triple']}  prev_reel1={prev['reel_1']}")

    log(f"\nPre-VT idx tuple counts:")
    tc = Counter(t for t, _, _ in pre_vt)
    for t, c in tc.most_common(20):
        log(f"  {t}: {c} ({c/len(pre_vt)*100:.1f}%)")

    # ================================================================
    # ANALYSIS 2: Per-reel idx before VT vs overall
    # ================================================================
    log(f"\n{'='*70}")
    log(f"  ANALYSIS 2: PER-REEL IDX BEFORE VT vs OVERALL")
    log(f"{'='*70}")

    for reel_name, reel_key in [("r1", "r1_idx"), ("r2", "r2_idx"), ("r3", "r3_idx")]:
        pre_vt_vals = Counter()
        overall_vals = Counter()
        for i in range(1, len(idx_data)):
            overall_vals[idx_data[i - 1][reel_key]] += 1
            if idx_data[i]["is_vt"]:
                pre_vt_vals[idx_data[i - 1][reel_key]] += 1

        log(f"\n  {reel_name}:")
        log(f"  {'val':>3s}  {'pre_vt':>7s} {'pre%':>6s}  {'overall':>7s} {'ovr%':>6s}  {'lift':>6s}")
        total_pre = sum(pre_vt_vals.values())
        total_ovr = sum(overall_vals.values())
        for v in range(9):
            pv = pre_vt_vals.get(v, 0)
            ov = overall_vals.get(v, 0)
            pv_pct = pv / total_pre * 100 if total_pre else 0
            ov_pct = ov / total_ovr * 100 if total_ovr else 0
            lift = pv_pct / ov_pct if ov_pct > 0 else 0
            log(f"  {v:3d}  {pv:7d} {pv_pct:5.1f}%  {ov:7d} {ov_pct:5.1f}%  {lift:5.2f}x")

    # ================================================================
    # ANALYSIS 3: Windows of N spins before VT
    # ================================================================
    log(f"\n{'='*70}")
    log(f"  ANALYSIS 3: WINDOW PATTERNS BEFORE VT (N=3,5,10)")
    log(f"{'='*70}")

    for window_size in [3, 5, 10]:
        log(f"\n  --- Window size: {window_size} ---")
        vt_windows = []
        non_vt_windows = []

        for i in range(window_size, len(idx_data)):
            window = idx_data[i - window_size:i]
            features = {
                "triple_count": sum(1 for w in window if w["is_triple"]),
                "vt_count": sum(1 for w in window if w["is_vt"]),
                "mean_r1": sum(w["r1_idx"] for w in window) / window_size,
                "mean_r2": sum(w["r2_idx"] for w in window) / window_size,
                "mean_r3": sum(w["r3_idx"] for w in window) / window_size,
                "same_idx_count": sum(1 for w in window if w["r1_idx"] == w["r2_idx"] == w["r3_idx"]),
                "has_6or8": sum(1 for w in window if any(w[k] in (6,8) for k in ("r1_idx","r2_idx","r3_idx"))),
                "sum_idx": sum(w["r1_idx"] + w["r2_idx"] + w["r3_idx"] for w in window),
                "max_spread": max(max(w["r1_idx"],w["r2_idx"],w["r3_idx"]) - min(w["r1_idx"],w["r2_idx"],w["r3_idx"]) for w in window),
            }
            if idx_data[i]["is_vt"]:
                vt_windows.append(features)
            else:
                non_vt_windows.append(features)

        if not vt_windows:
            log(f"  No VTs with full window")
            continue

        log(f"  VT windows: {len(vt_windows)}, non-VT: {len(non_vt_windows)}")
        log(f"  {'feature':<20s}  {'vt_mean':>8s}  {'non_vt_mean':>11s}  {'ratio':>6s}")
        for feat in sorted(vt_windows[0].keys()):
            vt_mean = sum(f[feat] for f in vt_windows) / len(vt_windows)
            nv_mean = sum(f[feat] for f in non_vt_windows) / len(non_vt_windows)
            ratio = vt_mean / nv_mean if nv_mean > 0 else float("inf")
            log(f"  {feat:<20s}  {vt_mean:>8.2f}  {nv_mean:>11.2f}  {ratio:>5.2f}x")

    # ================================================================
    # ANALYSIS 4: Strategy simulations (CORRECTED)
    # ================================================================
    log(f"\n{'='*70}")
    log(f"  ANALYSIS 4: STRATEGY SIMULATIONS (CORRECTED)")
    log(f"{'='*70}")

    strategies = {
        "Always_bet": lambda d, h: True,
        "same_idx(any)": lambda d, h: d["r1_idx"] == d["r2_idx"] == d["r3_idx"],
        "same_idx_6or8": lambda d, h: d["r1_idx"] == d["r2_idx"] == d["r3_idx"] and d["r1_idx"] in (6, 8),
        "same_idx_not_6or8": lambda d, h: d["r1_idx"] == d["r2_idx"] == d["r3_idx"] and d["r1_idx"] not in (6, 8),
        "r1==r2": lambda d, h: d["r1_idx"] == d["r2_idx"],
        "r1==r3": lambda d, h: d["r1_idx"] == d["r3_idx"],
        "r2==r3": lambda d, h: d["r2_idx"] == d["r3_idx"],
        "any_pair_same": lambda d, h: d["r1_idx"]==d["r2_idx"] or d["r1_idx"]==d["r3_idx"] or d["r2_idx"]==d["r3_idx"],
        "no_pair_same": lambda d, h: d["r1_idx"]!=d["r2_idx"] and d["r1_idx"]!=d["r3_idx"] and d["r2_idx"]!=d["r3_idx"],
        "r1_in_6or8": lambda d, h: d["r1_idx"] in (6, 8),
        "r2_in_6or8": lambda d, h: d["r2_idx"] in (6, 8),
        "r3_in_6or8": lambda d, h: d["r3_idx"] in (6, 8),
        "any_reel_6or8": lambda d, h: any(d[k] in (6,8) for k in ("r1_idx","r2_idx","r3_idx")),
        "no_reel_6or8": lambda d, h: not any(d[k] in (6,8) for k in ("r1_idx","r2_idx","r3_idx")),
        "all_reels_6or8": lambda d, h: all(d[k] in (6,8) for k in ("r1_idx","r2_idx","r3_idx")),
        "sum>=18": lambda d, h: d["r1_idx"] + d["r2_idx"] + d["r3_idx"] >= 18,
        "sum>=15": lambda d, h: d["r1_idx"] + d["r2_idx"] + d["r3_idx"] >= 15,
        "sum<=6": lambda d, h: d["r1_idx"] + d["r2_idx"] + d["r3_idx"] <= 6,
        "sum<=3": lambda d, h: d["r1_idx"] + d["r2_idx"] + d["r3_idx"] <= 3,
        "spread<=2": lambda d, h: max(d["r1_idx"],d["r2_idx"],d["r3_idx"])-min(d["r1_idx"],d["r2_idx"],d["r3_idx"])<=2,
        "spread>=6": lambda d, h: max(d["r1_idx"],d["r2_idx"],d["r3_idx"])-min(d["r1_idx"],d["r2_idx"],d["r3_idx"])>=6,
        "is_triple_csv": lambda d, h: d["is_triple"],
        "is_triple_not_vt": lambda d, h: d["is_triple"] and not d["is_vt"],
        "r1>=5": lambda d, h: d["r1_idx"] >= 5,
        "r2>=5": lambda d, h: d["r2_idx"] >= 5,
        "r3>=5": lambda d, h: d["r3_idx"] >= 5,
        "r1<=2": lambda d, h: d["r1_idx"] <= 2,
        "r2<=2": lambda d, h: d["r2_idx"] <= 2,
        "r3<=2": lambda d, h: d["r3_idx"] <= 2,
    }

    log(f"\n  {'strategy':<22s}  {'bets':>6s}  {'caught':>7s}  {'missed':>7s}  "
        f"{'catch%':>7s}  {'prec%':>7s}  {'bets/hit':>8s}  {'saved%':>7s}")
    log(f"  {'-'*90}")

    for name, fn in strategies.items():
        bets = caught = missed = 0
        for i in range(len(idx_data) - 1):
            cur = idx_data[i]
            next_vt = idx_data[i + 1]["is_vt"]
            if fn(cur, idx_data[:i]):
                bets += 1
                if next_vt:
                    caught += 1
            else:
                if next_vt:
                    missed += 1

        catch_pct = caught / total_vts * 100 if total_vts > 0 else 0
        prec = caught / bets * 100 if bets > 0 else 0
        bph = bets / caught if caught > 0 else float("inf")
        saved = (1 - bets / (len(idx_data) - 1)) * 100

        log(f"  {name:<22s}  {bets:>6d}  {caught:>7d}  {missed:>7d}  "
            f"{catch_pct:>6.1f}%  {prec:>6.1f}%  {bph:>8.1f}  {saved:>6.1f}%")

    # ================================================================
    # ANALYSIS 5: Does the PREVIOUS spin being a triple predict the next VT?
    # ================================================================
    log(f"\n{'='*70}")
    log(f"  ANALYSIS 5: CSV TRIPLE -> NEXT SPIN IS VT?")
    log(f"{'='*70}")

    triple_then_vt = 0
    triple_then_not_vt = 0
    non_triple_then_vt = 0
    non_triple_then_not_vt = 0

    for i in range(len(idx_data) - 1):
        cur_triple = idx_data[i]["is_triple"]
        next_vt = idx_data[i + 1]["is_vt"]
        if cur_triple:
            if next_vt: triple_then_vt += 1
            else: triple_then_not_vt += 1
        else:
            if next_vt: non_triple_then_vt += 1
            else: non_triple_then_not_vt += 1

    total_after_triple = triple_then_vt + triple_then_not_vt
    total_after_non = non_triple_then_vt + non_triple_then_not_vt

    log(f"  After triple:     {triple_then_vt}/{total_after_triple} VTs = {triple_then_vt/total_after_triple*100:.2f}%" if total_after_triple else "  No triples")
    log(f"  After non-triple: {non_triple_then_vt}/{total_after_non} VTs = {non_triple_then_vt/total_after_non*100:.2f}%" if total_after_non else "  No non-triples")
    log(f"  Baseline:         {total_vts}/{len(idx_data)-1} = {total_vts/(len(idx_data)-1)*100:.2f}%")

    # ================================================================
    # ANALYSIS 6: Gap length analysis (spins since last VT)
    # ================================================================
    log(f"\n{'='*70}")
    log(f"  ANALYSIS 6: GAP LENGTH DISTRIBUTION (corrected)")
    log(f"{'='*70}")

    last_vt = -1
    gaps = []
    for i, d in enumerate(idx_data):
        if d["is_vt"]:
            if last_vt >= 0:
                gap = i - last_vt - 1
                gaps.append(gap)
            last_vt = i

    if gaps:
        gaps.sort()
        log(f"  {len(gaps)} gaps, min={min(gaps)}, max={max(gaps)}, "
            f"mean={sum(gaps)/len(gaps):.1f}, median={gaps[len(gaps)//2]}")
        log(f"\n  Gap distribution:")
        buckets = Counter()
        for g in gaps:
            if g < 10: buckets["0-9"] += 1
            elif g < 20: buckets["10-19"] += 1
            elif g < 30: buckets["20-29"] += 1
            elif g < 40: buckets["30-39"] += 1
            elif g < 50: buckets["40-49"] += 1
            elif g < 75: buckets["50-74"] += 1
            else: buckets["75+"] += 1
        for b in ["0-9", "10-19", "20-29", "30-39", "40-49", "50-74", "75+"]:
            c = buckets.get(b, 0)
            log(f"    {b:>6s}: {c:3d} {'#' * c}")

    log(f"\n{'='*70}")
    log(f"  DONE")
    log(f"{'='*70}")


if __name__ == "__main__":
    main()
