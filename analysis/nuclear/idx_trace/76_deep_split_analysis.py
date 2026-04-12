#!/usr/bin/env python3
"""
76_deep_split_analysis.py — Deep gap analysis with ACC/SPN split.

Corrected off-by-one: trace[N] idx -> CSV spin N+1.
Analyzes ACC and SPN VTs independently with many more angles:
  - Cumulative idx running totals through gaps
  - Other triples as markers/signals within gaps
  - Reel-specific patterns per VT type
  - Triple density/spacing within gaps
  - idx momentum / derivative patterns
  - Symbol streak analysis
  - Combinatorial reel patterns
"""
import json, csv, sys, math
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations

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

IDX_SYM = {0:"attack", 1:"coin", 2:"shield", 3:"goldS",
            4:"steal", 5:"coin2", 6:"spins", 7:"goldS2", 8:"accum"}


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
        triple_type = reel_1 if is_triple else ""
        data.append({
            "spin_num": sn, "r1": r1, "r2": r2, "r3": r3,
            "reel_1": reel_1, "is_triple": is_triple, "triple_type": triple_type,
            "is_vt": is_vt, "vt_type": vt_type,
        })
    return data


def run_analysis(idx_data, label, vt_filter=None):
    """Run full analysis on idx_data, optionally filtering to a specific VT type."""
    if vt_filter:
        def is_target(d): return d["is_vt"] and d["vt_type"] == vt_filter
    else:
        def is_target(d): return d["is_vt"]

    total_targets = sum(1 for d in idx_data if is_target(d))
    N = len(idx_data)
    baseline = total_targets / (N - 1) if N > 1 else 0

    log(f"\n{'#'*70}")
    log(f"  {label}")
    log(f"  {N} spins, {total_targets} targets, baseline={baseline*100:.2f}%")
    log(f"{'#'*70}")

    if total_targets < 3:
        log(f"  Too few targets for analysis, skipping")
        return

    # Find target positions and build gaps
    target_positions = [i for i, d in enumerate(idx_data) if is_target(d)]
    gaps = []
    for g in range(len(target_positions) - 1):
        s = target_positions[g]
        e = target_positions[g + 1]
        gaps.append(idx_data[s+1:e])

    # ================================================================
    # A. GAP LENGTHS
    # ================================================================
    log(f"\n  --- A. GAP LENGTHS ---")
    gap_lens = [len(g) for g in gaps]
    if gap_lens:
        gl = sorted(gap_lens)
        log(f"  {len(gl)} gaps: min={gl[0]}, max={gl[-1]}, mean={sum(gl)/len(gl):.1f}, "
            f"median={gl[len(gl)//2]}, std={math.sqrt(sum((x-sum(gl)/len(gl))**2 for x in gl)/len(gl)):.1f}")
        log(f"  All: {gap_lens}")

    # ================================================================
    # B. OTHER TRIPLES AS MARKERS WITHIN GAPS
    # ================================================================
    log(f"\n  --- B. OTHER TRIPLES IN GAPS ---")

    # For each gap: count triples by type, position of last triple before target
    triple_counts_in_gap = []
    triple_type_counts = Counter()
    last_triple_dist = []  # distance from last non-VT triple to the target VT

    for g in gaps:
        n = len(g)
        tc = Counter()
        last_tri_pos = -1
        for i, s in enumerate(g):
            if s["is_triple"]:
                tc[s["triple_type"]] += 1
                last_tri_pos = i
        triple_counts_in_gap.append(sum(tc.values()))
        for tt, c in tc.items():
            triple_type_counts[tt] += c
        if last_tri_pos >= 0:
            last_triple_dist.append(n - last_tri_pos - 1)

    if triple_counts_in_gap:
        log(f"  Triples per gap: mean={sum(triple_counts_in_gap)/len(triple_counts_in_gap):.1f}, "
            f"min={min(triple_counts_in_gap)}, max={max(triple_counts_in_gap)}")
        log(f"  Triple types in gaps: {dict(triple_type_counts.most_common())}")
    if last_triple_dist:
        log(f"  Distance from last triple to VT: mean={sum(last_triple_dist)/len(last_triple_dist):.1f}, "
            f"min={min(last_triple_dist)}, max={max(last_triple_dist)}")
        log(f"  All: {last_triple_dist}")

    # Does triple density change through the gap?
    log(f"\n  Triple density by gap position (thirds):")
    first_tri = mid_tri = last_tri = 0
    first_tot = mid_tot = last_tot = 0
    for g in gaps:
        n = len(g)
        if n < 3: continue
        third = max(1, n // 3)
        for i, s in enumerate(g):
            if i < third:
                first_tot += 1
                if s["is_triple"]: first_tri += 1
            elif i >= n - third:
                last_tot += 1
                if s["is_triple"]: last_tri += 1
            else:
                mid_tot += 1
                if s["is_triple"]: mid_tri += 1
    log(f"    First third: {first_tri}/{first_tot} = {first_tri/first_tot*100:.1f}%" if first_tot else "    First third: N/A")
    log(f"    Middle:      {mid_tri}/{mid_tot} = {mid_tri/mid_tot*100:.1f}%" if mid_tot else "    Middle: N/A")
    log(f"    Last third:  {last_tri}/{last_tot} = {last_tri/last_tot*100:.1f}%" if last_tot else "    Last third: N/A")

    # Specific triple type on prev spin -> target VT rate
    log(f"\n  Previous spin triple type -> target VT next spin:")
    log(f"  {'triple_type':<14s}  {'then_vt':>7s}  {'total':>7s}  {'rate':>7s}  {'lift':>6s}")
    prev_triple_vt = Counter()
    prev_triple_total = Counter()
    for i in range(len(idx_data) - 1):
        if idx_data[i]["is_triple"]:
            tt = idx_data[i]["triple_type"]
            prev_triple_total[tt] += 1
            if is_target(idx_data[i + 1]):
                prev_triple_vt[tt] += 1
    for tt in sorted(prev_triple_total.keys(), key=lambda k: -prev_triple_total[k]):
        vt = prev_triple_vt.get(tt, 0)
        tot = prev_triple_total[tt]
        rate = vt / tot if tot else 0
        lift = rate / baseline if baseline > 0 else 0
        log(f"  {tt:<14s}  {vt:7d}  {tot:7d}  {rate:6.2%}  {lift:5.2f}x")

    # Non-triple prev spin symbol -> target VT rate
    log(f"\n  Previous spin symbol (non-triple) -> target VT next spin:")
    log(f"  {'reel_1':<14s}  {'then_vt':>7s}  {'total':>7s}  {'rate':>7s}  {'lift':>6s}")
    prev_sym_vt = Counter()
    prev_sym_total = Counter()
    for i in range(len(idx_data) - 1):
        if not idx_data[i]["is_triple"]:
            sym = idx_data[i]["reel_1"]
            prev_sym_total[sym] += 1
            if is_target(idx_data[i + 1]):
                prev_sym_vt[sym] += 1
    for sym in sorted(prev_sym_total.keys(), key=lambda k: -prev_sym_total[k]):
        vt = prev_sym_vt.get(sym, 0)
        tot = prev_sym_total[sym]
        rate = vt / tot if tot else 0
        lift = rate / baseline if baseline > 0 else 0
        log(f"  {sym:<14s}  {vt:7d}  {tot:7d}  {rate:6.2%}  {lift:5.2f}x")

    # ================================================================
    # C. CUMULATIVE IDX THROUGH GAPS
    # ================================================================
    log(f"\n  --- C. CUMULATIVE IDX THROUGH GAPS ---")

    # For each gap, track running sum, running mean, running max/min of each reel
    # Normalize to 10 buckets
    NBUCKETS = 10
    bucket_data = defaultdict(lambda: defaultdict(list))

    for g in gaps:
        n = len(g)
        if n < NBUCKETS: continue
        cum_r1 = cum_r2 = cum_r3 = 0
        cum_sum = 0
        cum_triples = 0
        for i, s in enumerate(g):
            cum_r1 += s["r1"]
            cum_r2 += s["r2"]
            cum_r3 += s["r3"]
            cum_sum += s["r1"] + s["r2"] + s["r3"]
            cum_triples += (1 if s["is_triple"] else 0)
            bucket = min(int(i / n * NBUCKETS), NBUCKETS - 1)
            k = i + 1
            bucket_data[bucket]["cum_sum_avg"].append(cum_sum / k)
            bucket_data[bucket]["cum_r1_avg"].append(cum_r1 / k)
            bucket_data[bucket]["cum_r2_avg"].append(cum_r2 / k)
            bucket_data[bucket]["cum_r3_avg"].append(cum_r3 / k)
            bucket_data[bucket]["cum_triple_rate"].append(cum_triples / k)
            bucket_data[bucket]["instant_sum"].append(s["r1"] + s["r2"] + s["r3"])
            bucket_data[bucket]["r3_val"].append(s["r3"])

    log(f"  Position through gap -> cumulative averages:")
    log(f"  {'pos':>6s}  {'cum_sum':>8s}  {'cum_r1':>7s}  {'cum_r2':>7s}  {'cum_r3':>7s}  "
        f"{'tri_rate':>8s}  {'inst_sum':>8s}  {'r3_avg':>7s}")
    for b in range(NBUCKETS):
        if not bucket_data[b]["cum_sum_avg"]: continue
        cs = sum(bucket_data[b]["cum_sum_avg"]) / len(bucket_data[b]["cum_sum_avg"])
        cr1 = sum(bucket_data[b]["cum_r1_avg"]) / len(bucket_data[b]["cum_r1_avg"])
        cr2 = sum(bucket_data[b]["cum_r2_avg"]) / len(bucket_data[b]["cum_r2_avg"])
        cr3 = sum(bucket_data[b]["cum_r3_avg"]) / len(bucket_data[b]["cum_r3_avg"])
        tr = sum(bucket_data[b]["cum_triple_rate"]) / len(bucket_data[b]["cum_triple_rate"])
        ins = sum(bucket_data[b]["instant_sum"]) / len(bucket_data[b]["instant_sum"])
        r3a = sum(bucket_data[b]["r3_val"]) / len(bucket_data[b]["r3_val"])
        log(f"  {b*10:3d}-{(b+1)*10:2d}%  {cs:>8.2f}  {cr1:>7.2f}  {cr2:>7.2f}  {cr3:>7.2f}  "
            f"{tr:>7.3f}  {ins:>8.2f}  {r3a:>7.2f}")

    # ================================================================
    # D. IDX MOMENTUM — change from spin to spin
    # ================================================================
    log(f"\n  --- D. IDX MOMENTUM (spin-to-spin changes) ---")

    delta_before_vt = {"dr1": [], "dr2": [], "dr3": [], "dsum": []}
    delta_overall = {"dr1": [], "dr2": [], "dr3": [], "dsum": []}

    for i in range(1, len(idx_data) - 1):
        prev = idx_data[i - 1]
        cur = idx_data[i]
        dr1 = cur["r1"] - prev["r1"]
        dr2 = cur["r2"] - prev["r2"]
        dr3 = cur["r3"] - prev["r3"]
        dsum = (cur["r1"]+cur["r2"]+cur["r3"]) - (prev["r1"]+prev["r2"]+prev["r3"])

        delta_overall["dr1"].append(dr1)
        delta_overall["dr2"].append(dr2)
        delta_overall["dr3"].append(dr3)
        delta_overall["dsum"].append(dsum)

        if is_target(idx_data[i + 1]):
            delta_before_vt["dr1"].append(dr1)
            delta_before_vt["dr2"].append(dr2)
            delta_before_vt["dr3"].append(dr3)
            delta_before_vt["dsum"].append(dsum)

    log(f"  {'delta':<6s}  {'bef_vt_mean':>11s}  {'overall_mean':>12s}  {'ratio':>6s}")
    for key in ["dr1", "dr2", "dr3", "dsum"]:
        bv = delta_before_vt[key]
        ov = delta_overall[key]
        bv_mean = sum(bv) / len(bv) if bv else 0
        ov_mean = sum(ov) / len(ov) if ov else 0
        ratio = bv_mean / ov_mean if ov_mean != 0 else float("inf")
        log(f"  {key:<6s}  {bv_mean:>11.3f}  {ov_mean:>12.3f}  {ratio:>6.2f}")

    # Absolute momentum
    log(f"\n  Absolute momentum (|delta|):")
    log(f"  {'delta':<6s}  {'bef_vt_mean':>11s}  {'overall_mean':>12s}  {'ratio':>6s}")
    for key in ["dr1", "dr2", "dr3", "dsum"]:
        bv = [abs(x) for x in delta_before_vt[key]]
        ov = [abs(x) for x in delta_overall[key]]
        bv_mean = sum(bv) / len(bv) if bv else 0
        ov_mean = sum(ov) / len(ov) if ov else 0
        ratio = bv_mean / ov_mean if ov_mean > 0 else 0
        log(f"  {key:<6s}  {bv_mean:>11.3f}  {ov_mean:>12.3f}  {ratio:>5.2f}x")

    # ================================================================
    # E. SYMBOL STREAKS — consecutive same reel_1 symbol
    # ================================================================
    log(f"\n  --- E. SYMBOL STREAKS BEFORE VT ---")

    streak_before_vt = Counter()
    streak_overall = Counter()

    for i in range(len(idx_data) - 1):
        # Count streak length ending at position i
        streak = 1
        sym = idx_data[i]["reel_1"]
        j = i - 1
        while j >= 0 and idx_data[j]["reel_1"] == sym:
            streak += 1
            j -= 1
        streak_overall[streak] += 1
        if is_target(idx_data[i + 1]):
            streak_before_vt[streak] += 1

    log(f"  {'streak':>6s}  {'bef_vt':>7s}  {'overall':>7s}  {'vt_rate':>8s}  {'lift':>6s}")
    total_ov = sum(streak_overall.values())
    for s in sorted(set(list(streak_overall.keys()) + list(streak_before_vt.keys()))):
        bv = streak_before_vt.get(s, 0)
        ov = streak_overall.get(s, 0)
        if ov == 0: continue
        rate = bv / ov
        lift = rate / baseline if baseline > 0 else 0
        if ov >= 5:
            log(f"  {s:6d}  {bv:7d}  {ov:7d}  {rate:>7.2%}  {lift:>5.2f}x")

    # ================================================================
    # F. REEL COMBINATION PATTERNS
    # ================================================================
    log(f"\n  --- F. REEL COMBINATION PATTERNS ---")

    # Which (r1_bucket, r2_bucket, r3_bucket) appears before VTs?
    # Bucket: low(0-2), mid(3-5), high(6-8)
    def bucket_val(v):
        if v <= 2: return "L"
        if v <= 5: return "M"
        return "H"

    combo_bv = Counter()
    combo_ov = Counter()
    for i in range(len(idx_data) - 1):
        d = idx_data[i]
        combo = f"{bucket_val(d['r1'])}{bucket_val(d['r2'])}{bucket_val(d['r3'])}"
        combo_ov[combo] += 1
        if is_target(idx_data[i + 1]):
            combo_bv[combo] += 1

    log(f"  {'combo':<6s}  {'bef_vt':>7s}  {'overall':>7s}  {'vt_rate':>8s}  {'lift':>6s}")
    for combo in sorted(combo_ov.keys()):
        bv = combo_bv.get(combo, 0)
        ov = combo_ov[combo]
        rate = bv / ov if ov else 0
        lift = rate / baseline if baseline > 0 else 0
        if ov >= 10:
            marker = " <--" if lift > 1.5 and bv >= 2 else ""
            log(f"  {combo:<6s}  {bv:7d}  {ov:7d}  {rate:>7.2%}  {lift:>5.2f}x{marker}")

    # ================================================================
    # G. TRIPLES IN GAP AS SIGNAL — N spins after a non-VT triple
    # ================================================================
    log(f"\n  --- G. NON-VT TRIPLE AS SIGNAL (bet N spins after it) ---")

    for window in [1, 2, 3, 5]:
        hits = 0
        bets = 0
        for i in range(len(idx_data)):
            if idx_data[i]["is_triple"] and not idx_data[i]["is_vt"]:
                # Bet on next `window` spins
                for j in range(1, window + 1):
                    if i + j < len(idx_data):
                        bets += 1
                        if is_target(idx_data[i + j]):
                            hits += 1
        prec = hits / bets * 100 if bets else 0
        catch = hits / total_targets * 100 if total_targets else 0
        bph = bets / hits if hits else float("inf")
        log(f"  Bet {window} after non-VT triple: {bets} bets, {hits} hits, "
            f"prec={prec:.2f}%, catch={catch:.1f}%, bets/hit={bph:.1f}")

    # ================================================================
    # H. SPINS SINCE LAST NON-VT TRIPLE -> VT RATE
    # ================================================================
    log(f"\n  --- H. SPINS SINCE LAST NON-VT TRIPLE -> VT RATE ---")

    dist_vt_h = Counter()
    dist_total_h = Counter()
    last_nv_triple = -1

    for i, d in enumerate(idx_data):
        if d["is_triple"] and not d["is_vt"]:
            last_nv_triple = i
        if last_nv_triple >= 0 and i > last_nv_triple:
            gap_pos = i - last_nv_triple
            if is_target(d):
                dist_vt_h[gap_pos] += 1
            else:
                dist_total_h[gap_pos] += 1

    buckets_h = [(1,2), (3,5), (6,10), (11,15), (16,20), (21,30), (31,50), (51,100)]
    log(f"  {'range':>8s}  {'vts':>5s}  {'total':>7s}  {'rate':>7s}  {'lift':>6s}")
    for lo, hi in buckets_h:
        vts = sum(dist_vt_h.get(p, 0) for p in range(lo, hi+1))
        tot = sum(dist_total_h.get(p, 0) for p in range(lo, hi+1)) + vts
        if tot == 0: continue
        rate = vts / tot
        lift = rate / baseline if baseline > 0 else 0
        log(f"  {lo:3d}-{hi:3d}  {vts:5d}  {tot:7d}  {rate:>6.2%}  {lift:>5.2f}x")

    # ================================================================
    # I. PITY TIMER (spins since last VT of THIS type)
    # ================================================================
    log(f"\n  --- I. PITY TIMER (spins since last target VT) ---")

    last_target = -1
    pity_vt = Counter()
    pity_total = Counter()

    for i, d in enumerate(idx_data):
        if is_target(d):
            if last_target >= 0:
                gap = i - last_target
                pity_vt[gap] += 1
            last_target = i
        elif last_target >= 0:
            gap = i - last_target
            pity_total[gap] += 1

    buckets_p = [(1,5), (6,10), (11,15), (16,20), (21,30), (31,40),
                 (41,50), (51,60), (61,80), (81,100), (101,150)]
    log(f"  {'range':>8s}  {'vts':>5s}  {'total':>7s}  {'rate':>7s}  {'lift':>6s}")
    for lo, hi in buckets_p:
        vts = sum(pity_vt.get(p, 0) for p in range(lo, hi+1))
        tot = sum(pity_total.get(p, 0) for p in range(lo, hi+1)) + vts
        if tot == 0: continue
        rate = vts / tot
        lift = rate / baseline if baseline > 0 else 0
        log(f"  {lo:3d}-{hi:3d}  {vts:5d}  {tot:7d}  {rate:>6.2%}  {lift:>5.2f}x")

    # ================================================================
    # J. COMPREHENSIVE STRATEGY SIM
    # ================================================================
    log(f"\n  --- J. STRATEGY SIMULATIONS ---")

    # Track state for compound strategies
    results = []
    last_target_pos = -1
    last_any_triple_pos = -1

    for i in range(len(idx_data) - 1):
        d = idx_data[i]
        nxt_target = is_target(idx_data[i + 1])

        gap_since_vt = i - last_target_pos if last_target_pos >= 0 else i
        gap_since_triple = i - last_any_triple_pos if last_any_triple_pos >= 0 else i
        s = d["r1"] + d["r2"] + d["r3"]
        spread = max(d["r1"], d["r2"], d["r3"]) - min(d["r1"], d["r2"], d["r3"])
        all_diff = d["r1"] != d["r2"] and d["r1"] != d["r3"] and d["r2"] != d["r3"]
        any_8 = 8 in (d["r1"], d["r2"], d["r3"])
        r3_high = d["r3"] >= 5

        results.append({
            "nxt_target": nxt_target,
            "gap_vt": gap_since_vt,
            "gap_tri": gap_since_triple,
            "sum": s, "spread": spread, "all_diff": all_diff,
            "any_8": any_8, "r3_high": r3_high,
            "is_triple": d["is_triple"], "r1": d["r1"], "r2": d["r2"], "r3": d["r3"],
        })

        if d["is_vt"] and is_target(d):
            last_target_pos = i
        if d["is_triple"]:
            last_any_triple_pos = i

    strategies = {
        "Always_bet": lambda r: True,
        "gap_vt>=20": lambda r: r["gap_vt"] >= 20,
        "gap_vt>=30": lambda r: r["gap_vt"] >= 30,
        "gap_vt>=40": lambda r: r["gap_vt"] >= 40,
        "gap_vt>=50": lambda r: r["gap_vt"] >= 50,
        "gap_vt>=30+sum>=15": lambda r: r["gap_vt"] >= 30 and r["sum"] >= 15,
        "gap_vt>=30+r3>=5": lambda r: r["gap_vt"] >= 30 and r["r3_high"],
        "gap_vt>=30+all_diff": lambda r: r["gap_vt"] >= 30 and r["all_diff"],
        "gap_vt>=30+any_8": lambda r: r["gap_vt"] >= 30 and r["any_8"],
        "gap_vt>=20+sum>=15": lambda r: r["gap_vt"] >= 20 and r["sum"] >= 15,
        "gap_vt>=20+r3>=5": lambda r: r["gap_vt"] >= 20 and r["r3_high"],
        "gap_tri>=5": lambda r: r["gap_tri"] >= 5,
        "gap_tri>=10": lambda r: r["gap_tri"] >= 10,
        "gap_vt>=30+gap_tri>=5": lambda r: r["gap_vt"] >= 30 and r["gap_tri"] >= 5,
        "gap_vt>=20+spread<=4": lambda r: r["gap_vt"] >= 20 and r["spread"] <= 4,
        "gap_vt>=30+spread<=4": lambda r: r["gap_vt"] >= 30 and r["spread"] <= 4,
        "gap_vt>=30+r2>=5": lambda r: r["gap_vt"] >= 30 and r["r2"] >= 5,
        "gap_vt>=30+r1>=5": lambda r: r["gap_vt"] >= 30 and r["r1"] >= 5,
    }

    log(f"\n  {'strategy':<28s}  {'bets':>6s}  {'caught':>7s}  {'missed':>7s}  "
        f"{'catch%':>7s}  {'prec%':>7s}  {'bets/hit':>8s}  {'saved%':>7s}")
    log(f"  {'-'*96}")

    for name, fn in strategies.items():
        bets = caught = missed = 0
        for r in results:
            if fn(r):
                bets += 1
                if r["nxt_target"]: caught += 1
            else:
                if r["nxt_target"]: missed += 1

        catch_pct = caught / total_targets * 100 if total_targets > 0 else 0
        prec = caught / bets * 100 if bets > 0 else 0
        bph = bets / caught if caught > 0 else float("inf")
        saved = (1 - bets / len(results)) * 100 if results else 0

        log(f"  {name:<28s}  {bets:>6d}  {caught:>7d}  {missed:>7d}  "
            f"{catch_pct:>6.1f}%  {prec:>6.1f}%  {bph:>8.1f}  {saved:>6.1f}%")

    # ================================================================
    # K. PER-REEL TRANSITION MATRICES (N-1 -> VT)
    # ================================================================
    log(f"\n  --- K. PER-REEL idx N-1 -> target VT rate ---")
    for reel, key in [("r1", "r1"), ("r2", "r2"), ("r3", "r3")]:
        log(f"\n  {reel}:")
        log(f"  {'val':>3s}  {'bef_vt':>7s}  {'total':>7s}  {'rate':>7s}  {'lift':>6s}")
        for v in range(9):
            bv = sum(1 for i in range(len(idx_data)-1) if idx_data[i][key]==v and is_target(idx_data[i+1]))
            tot = sum(1 for i in range(len(idx_data)-1) if idx_data[i][key]==v)
            if tot == 0: continue
            rate = bv / tot
            lift = rate / baseline if baseline > 0 else 0
            marker = " <--" if lift > 1.5 and bv >= 2 else ""
            log(f"  {v:3d}  {bv:7d}  {tot:7d}  {rate:>6.2%}  {lift:>5.2f}x{marker}")

    # ================================================================
    # L. 2-SPIN LOOKBACK — (N-2, N-1) -> VT
    # ================================================================
    log(f"\n  --- L. 2-SPIN LOOKBACK (r3[N-2], r3[N-1]) -> target VT ---")
    pair_bv = Counter()
    pair_ov = Counter()
    for i in range(2, len(idx_data)):
        p = (idx_data[i-2]["r3"], idx_data[i-1]["r3"])
        pair_ov[p] += 1
        if is_target(idx_data[i]):
            pair_bv[p] += 1

    # Show pairs with at least 1 hit, sorted by lift
    log(f"  {'(r3_n2,r3_n1)':<16s}  {'bef_vt':>7s}  {'total':>7s}  {'rate':>7s}  {'lift':>6s}")
    pairs_with_hits = [(p, pair_bv[p], pair_ov[p]) for p in pair_bv if pair_bv[p] > 0 and pair_ov[p] >= 5]
    pairs_with_hits.sort(key=lambda x: -x[1]/x[2])
    for p, bv, ov in pairs_with_hits[:20]:
        rate = bv / ov
        lift = rate / baseline
        log(f"  {str(p):<16s}  {bv:7d}  {ov:7d}  {rate:>6.2%}  {lift:>5.2f}x")


def main():
    data = load_corrected()
    idx_data = [d for d in data if d["r1"] is not None]

    log(f"Total data: {len(idx_data)} spins with idx")
    total_vts = sum(1 for d in idx_data if d["is_vt"])
    total_acc = sum(1 for d in idx_data if d["vt_type"] == "ACC")
    total_spn = sum(1 for d in idx_data if d["vt_type"] == "SPN")
    log(f"VTs: {total_vts} total ({total_acc} ACC, {total_spn} SPN)")

    # Run analysis for ALL VTs
    run_analysis(idx_data, "ALL VTs COMBINED")

    # Run analysis for ACC only
    run_analysis(idx_data, "ACC VTs ONLY", vt_filter="ACC")

    # Run analysis for SPN only
    run_analysis(idx_data, "SPN VTs ONLY", vt_filter="SPN")

    log(f"\n{'#'*70}")
    log(f"  ALL ANALYSES COMPLETE")
    log(f"{'#'*70}")


if __name__ == "__main__":
    main()
