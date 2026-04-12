#!/usr/bin/env python3
"""
75_full_gap_analysis_corrected.py — Comprehensive gap analysis with corrected
off-by-one alignment (trace[N] idx -> CSV spin N+1).

Examines the ENTIRE gap between VTs: positional patterns, ramp-up effects,
transition analysis, per-reel evolution, and predictive features.
"""
import json, csv, sys, math
from pathlib import Path
from collections import Counter, defaultdict

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

IDX_SYM = {0: "attack", 1: "coin", 2: "shield", 3: "goldS",
            4: "steal", 5: "coin2", 6: "spins", 7: "goldS2", 8: "accum"}


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
            "spin_num": sn, "r1": r1, "r2": r2, "r3": r3,
            "reel_1": reel_1, "is_triple": is_triple,
            "is_vt": is_vt, "vt_type": vt_type,
        })
    return data


def build_gaps(idx_data):
    """Split data into gaps between VTs. Each gap = list of non-VT spins
    between two consecutive VTs."""
    vt_positions = [i for i, d in enumerate(idx_data) if d["is_vt"]]
    gaps = []
    for g in range(len(vt_positions) - 1):
        start = vt_positions[g]
        end = vt_positions[g + 1]
        gap_spins = idx_data[start + 1:end]  # spins BETWEEN the two VTs
        gaps.append({
            "gap_num": g + 1,
            "vt_before": idx_data[start],
            "vt_after": idx_data[end],
            "spins": gap_spins,
            "length": len(gap_spins),
        })
    return gaps, vt_positions


def main():
    data = load_corrected()
    idx_data = [d for d in data if d["r1"] is not None]
    total_vts = sum(1 for d in idx_data if d["is_vt"])

    log(f"Data: {len(idx_data)} spins with idx, {total_vts} VTs")
    log(f"Baseline: {total_vts/(len(idx_data))*100:.2f}% VT rate, {len(idx_data)/total_vts:.1f} bets/hit")

    gaps, vt_pos = build_gaps(idx_data)
    log(f"Gaps between consecutive VTs: {len(gaps)}")
    log()

    # ==================================================================
    # 1. GAP LENGTH STATS
    # ==================================================================
    log("=" * 70)
    log("  1. GAP LENGTH DISTRIBUTION")
    log("=" * 70)
    lengths = [g["length"] for g in gaps]
    lengths_sorted = sorted(lengths)
    log(f"  Count: {len(lengths)}")
    log(f"  Min: {min(lengths)}, Max: {max(lengths)}")
    log(f"  Mean: {sum(lengths)/len(lengths):.1f}, Median: {lengths_sorted[len(lengths)//2]}")
    log(f"  Std: {(sum((x-sum(lengths)/len(lengths))**2 for x in lengths)/len(lengths))**0.5:.1f}")

    log(f"\n  All gaps: {lengths}")

    # ==================================================================
    # 2. POSITIONAL IDX ANALYSIS — how do idx values evolve through a gap?
    #    Normalize each gap to 0%-100% and check if idx changes near the end
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  2. POSITIONAL ANALYSIS — idx at start/mid/end of gap")
    log(f"{'='*70}")

    # Split each gap into thirds: first third, middle third, last third
    for reel, key in [("r1", "r1"), ("r2", "r2"), ("r3", "r3")]:
        first_vals = Counter()
        mid_vals = Counter()
        last_vals = Counter()
        for g in gaps:
            n = g["length"]
            if n < 3: continue
            third = max(1, n // 3)
            for i, s in enumerate(g["spins"]):
                if i < third:
                    first_vals[s[key]] += 1
                elif i >= n - third:
                    last_vals[s[key]] += 1
                else:
                    mid_vals[s[key]] += 1

        total_f = sum(first_vals.values())
        total_m = sum(mid_vals.values())
        total_l = sum(last_vals.values())

        log(f"\n  {reel} distribution by gap position:")
        log(f"  {'idx':>3s}  {'first':>6s} {'f%':>5s}  {'mid':>6s} {'m%':>5s}  {'last':>6s} {'l%':>5s}  shift(l-f)")
        for v in range(9):
            f = first_vals.get(v, 0)
            m = mid_vals.get(v, 0)
            l = last_vals.get(v, 0)
            fp = f/total_f*100 if total_f else 0
            mp = m/total_m*100 if total_m else 0
            lp = l/total_l*100 if total_l else 0
            shift = lp - fp
            marker = " <--" if abs(shift) > 3 else ""
            log(f"  {v:3d}  {f:6d} {fp:4.1f}%  {m:6d} {mp:4.1f}%  {l:6d} {lp:4.1f}%  {shift:+5.1f}%{marker}")

    # ==================================================================
    # 3. LAST-N SPINS BEFORE VT vs RANDOM SPINS
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  3. LAST N SPINS BEFORE VT vs RANDOM (feature comparison)")
    log(f"{'='*70}")

    for N in [1, 2, 3, 5, 10]:
        pre_vt_features = []
        random_features = []

        for g in gaps:
            if g["length"] < N: continue
            last_n = g["spins"][-N:]

            def feats(spins):
                r1s = [s["r1"] for s in spins]
                r2s = [s["r2"] for s in spins]
                r3s = [s["r3"] for s in spins]
                sums = [s["r1"]+s["r2"]+s["r3"] for s in spins]
                spreads = [max(s["r1"],s["r2"],s["r3"])-min(s["r1"],s["r2"],s["r3"]) for s in spins]
                pairs = sum(1 for s in spins if s["r1"]==s["r2"] or s["r1"]==s["r3"] or s["r2"]==s["r3"])
                triples_csv = sum(1 for s in spins if s["is_triple"])
                has_8 = sum(1 for s in spins if 8 in (s["r1"],s["r2"],s["r3"]))
                has_6 = sum(1 for s in spins if 6 in (s["r1"],s["r2"],s["r3"]))
                return {
                    "mean_r1": sum(r1s)/len(r1s),
                    "mean_r2": sum(r2s)/len(r2s),
                    "mean_r3": sum(r3s)/len(r3s),
                    "mean_sum": sum(sums)/len(sums),
                    "mean_spread": sum(spreads)/len(spreads),
                    "pair_rate": pairs/len(spins),
                    "triple_rate": triples_csv/len(spins),
                    "has_8_rate": has_8/len(spins),
                    "has_6_rate": has_6/len(spins),
                    "r3_8_rate": sum(1 for s in spins if s["r3"]==8)/len(spins),
                    "r3_0_rate": sum(1 for s in spins if s["r3"]==0)/len(spins),
                }

            pre_vt_features.append(feats(last_n))

            # Random window from the gap (not last N)
            if g["length"] >= 2 * N:
                rand_n = g["spins"][:N]
                random_features.append(feats(rand_n))

        if not pre_vt_features or not random_features:
            continue

        log(f"\n  --- Last {N} spins before VT vs first {N} of gap ---")
        log(f"  {'feature':<16s}  {'pre_vt':>8s}  {'random':>8s}  {'ratio':>6s}")
        for feat in sorted(pre_vt_features[0].keys()):
            vt_mean = sum(f[feat] for f in pre_vt_features) / len(pre_vt_features)
            rn_mean = sum(f[feat] for f in random_features) / len(random_features)
            ratio = vt_mean / rn_mean if rn_mean > 0 else float("inf")
            marker = " ***" if abs(ratio - 1) > 0.2 else ""
            log(f"  {feat:<16s}  {vt_mean:>8.3f}  {rn_mean:>8.3f}  {ratio:>5.2f}x{marker}")

    # ==================================================================
    # 4. RUNNING SUM / CUMULATIVE IDX THROUGH GAP
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  4. CUMULATIVE IDX SUM — does it ramp up before VT?")
    log(f"{'='*70}")

    # Normalize each gap to 10 buckets and compute mean cumsum at each bucket
    NBUCKETS = 10
    bucket_sums = defaultdict(list)
    bucket_r3_8_rate = defaultdict(list)

    for g in gaps:
        n = g["length"]
        if n < NBUCKETS: continue
        cumsum = 0
        r3_8_count = 0
        for i, s in enumerate(g["spins"]):
            cumsum += s["r1"] + s["r2"] + s["r3"]
            r3_8_count += (1 if s["r3"] == 8 else 0)
            bucket = min(int(i / n * NBUCKETS), NBUCKETS - 1)
            avg_sum = cumsum / (i + 1)
            avg_r3_8 = r3_8_count / (i + 1)
            bucket_sums[bucket].append(avg_sum)
            bucket_r3_8_rate[bucket].append(avg_r3_8)

    log(f"  Position through gap (0%=start, 90%=just before VT):")
    log(f"  {'bucket':>6s}  {'mean_avg_sum':>12s}  {'mean_r3_8_rate':>14s}")
    for b in range(NBUCKETS):
        if bucket_sums[b]:
            ms = sum(bucket_sums[b]) / len(bucket_sums[b])
            mr = sum(bucket_r3_8_rate[b]) / len(bucket_r3_8_rate[b])
            log(f"  {b*10:4d}-{(b+1)*10:2d}%  {ms:>12.2f}  {mr:>14.3f}")

    # ==================================================================
    # 5. TRANSITION ANALYSIS — what idx tuple follows what?
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  5. TRANSITION PATTERNS (idx[i] -> idx[i+1])")
    log(f"{'='*70}")

    # Check: does a specific r3 value on spin i predict VT on spin i+1?
    r3_before_vt = Counter()
    r3_before_non_vt = Counter()
    for i in range(len(idx_data) - 1):
        r3 = idx_data[i]["r3"]
        if idx_data[i + 1]["is_vt"]:
            r3_before_vt[r3] += 1
        else:
            r3_before_non_vt[r3] += 1

    log(f"\n  r3 value -> probability next spin is VT:")
    log(f"  {'r3':>3s}  {'before_vt':>9s}  {'before_nv':>9s}  {'vt_rate':>8s}  {'lift':>6s}")
    baseline = total_vts / (len(idx_data) - 1)
    for v in range(9):
        bv = r3_before_vt.get(v, 0)
        bn = r3_before_non_vt.get(v, 0)
        total_v = bv + bn
        if total_v == 0: continue
        rate = bv / total_v
        lift = rate / baseline
        log(f"  {v:3d}  {bv:9d}  {bn:9d}  {rate:>7.2%}  {lift:>5.2f}x")

    # Same for r1
    log(f"\n  r1 value -> probability next spin is VT:")
    r1_bv = Counter()
    r1_bn = Counter()
    for i in range(len(idx_data) - 1):
        r1 = idx_data[i]["r1"]
        if idx_data[i + 1]["is_vt"]:
            r1_bv[r1] += 1
        else:
            r1_bn[r1] += 1

    log(f"  {'r1':>3s}  {'before_vt':>9s}  {'before_nv':>9s}  {'vt_rate':>8s}  {'lift':>6s}")
    for v in range(9):
        bv = r1_bv.get(v, 0)
        bn = r1_bn.get(v, 0)
        total_v = bv + bn
        if total_v == 0: continue
        rate = bv / total_v
        lift = rate / baseline
        log(f"  {v:3d}  {bv:9d}  {bn:9d}  {rate:>7.2%}  {lift:>5.2f}x")

    # Same for r2
    log(f"\n  r2 value -> probability next spin is VT:")
    r2_bv = Counter()
    r2_bn = Counter()
    for i in range(len(idx_data) - 1):
        r2 = idx_data[i]["r2"]
        if idx_data[i + 1]["is_vt"]:
            r2_bv[r2] += 1
        else:
            r2_bn[r2] += 1

    log(f"  {'r2':>3s}  {'before_vt':>9s}  {'before_nv':>9s}  {'vt_rate':>8s}  {'lift':>6s}")
    for v in range(9):
        bv = r2_bv.get(v, 0)
        bn = r2_bn.get(v, 0)
        total_v = bv + bn
        if total_v == 0: continue
        rate = bv / total_v
        lift = rate / baseline
        log(f"  {v:3d}  {bv:9d}  {bn:9d}  {rate:>7.2%}  {lift:>5.2f}x")

    # ==================================================================
    # 6. SUM OF IDX — distribution before VT vs overall
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  6. IDX SUM DISTRIBUTION (r1+r2+r3) BEFORE VT vs OVERALL")
    log(f"{'='*70}")

    sum_before_vt = Counter()
    sum_overall = Counter()
    for i in range(len(idx_data) - 1):
        s = idx_data[i]["r1"] + idx_data[i]["r2"] + idx_data[i]["r3"]
        sum_overall[s] += 1
        if idx_data[i + 1]["is_vt"]:
            sum_before_vt[s] += 1

    total_bv = sum(sum_before_vt.values())
    total_ov = sum(sum_overall.values())

    log(f"  {'sum':>4s}  {'bef_vt':>7s} {'bv%':>5s}  {'overall':>7s} {'ov%':>5s}  {'lift':>6s}")
    for s in range(25):
        bv = sum_before_vt.get(s, 0)
        ov = sum_overall.get(s, 0)
        if ov == 0: continue
        bvp = bv / total_bv * 100 if total_bv else 0
        ovp = ov / total_ov * 100 if total_ov else 0
        lift = bvp / ovp if ovp > 0 else 0
        marker = " <--" if lift > 1.5 or (lift < 0.5 and bv > 0) else ""
        log(f"  {s:4d}  {bv:7d} {bvp:4.1f}%  {ov:7d} {ovp:4.1f}%  {lift:5.2f}x{marker}")

    # ==================================================================
    # 7. SPREAD DISTRIBUTION BEFORE VT
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  7. IDX SPREAD (max-min) BEFORE VT vs OVERALL")
    log(f"{'='*70}")

    spread_bv = Counter()
    spread_ov = Counter()
    for i in range(len(idx_data) - 1):
        sp = max(idx_data[i]["r1"],idx_data[i]["r2"],idx_data[i]["r3"]) - \
             min(idx_data[i]["r1"],idx_data[i]["r2"],idx_data[i]["r3"])
        spread_ov[sp] += 1
        if idx_data[i + 1]["is_vt"]:
            spread_bv[sp] += 1

    total_sbv = sum(spread_bv.values())
    total_sov = sum(spread_ov.values())
    log(f"  {'spread':>6s}  {'bef_vt':>7s} {'bv%':>5s}  {'overall':>7s} {'ov%':>5s}  {'lift':>6s}")
    for sp in range(9):
        bv = spread_bv.get(sp, 0)
        ov = spread_ov.get(sp, 0)
        if ov == 0: continue
        bvp = bv / total_sbv * 100 if total_sbv else 0
        ovp = ov / total_sov * 100 if total_sov else 0
        lift = bvp / ovp if ovp > 0 else 0
        log(f"  {sp:6d}  {bv:7d} {bvp:4.1f}%  {ov:7d} {ovp:4.1f}%  {lift:5.2f}x")

    # ==================================================================
    # 8. PAIR PATTERN ON PREVIOUS SPIN
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  8. PAIR PATTERNS ON SPIN BEFORE VT")
    log(f"{'='*70}")

    pair_types = {
        "r1==r2": lambda d: d["r1"]==d["r2"],
        "r1==r3": lambda d: d["r1"]==d["r3"],
        "r2==r3": lambda d: d["r2"]==d["r3"],
        "all_same": lambda d: d["r1"]==d["r2"]==d["r3"],
        "all_diff": lambda d: d["r1"]!=d["r2"] and d["r1"]!=d["r3"] and d["r2"]!=d["r3"],
    }

    log(f"  {'pattern':<12s}  {'bef_vt':>7s} {'bv%':>5s}  {'overall':>7s} {'ov%':>5s}  {'lift':>6s}")
    for name, fn in pair_types.items():
        bv = 0
        ov = 0
        for i in range(len(idx_data) - 1):
            if fn(idx_data[i]):
                ov += 1
                if idx_data[i + 1]["is_vt"]:
                    bv += 1
        bvp = bv / total_bv * 100 if total_bv else 0
        ovp = ov / total_ov * 100 if total_ov else 0
        lift = bvp / ovp if ovp > 0 else 0
        log(f"  {name:<12s}  {bv:7d} {bvp:4.1f}%  {ov:7d} {ovp:4.1f}%  {lift:5.2f}x")

    # ==================================================================
    # 9. REEL_1 SYMBOL ON PREVIOUS SPIN (CSV)
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  9. REEL_1 SYMBOL ON PREVIOUS SPIN -> VT RATE")
    log(f"{'='*70}")

    reel1_bv = Counter()
    reel1_ov = Counter()
    for i in range(len(idx_data) - 1):
        r1sym = idx_data[i]["reel_1"]
        reel1_ov[r1sym] += 1
        if idx_data[i + 1]["is_vt"]:
            reel1_bv[r1sym] += 1

    log(f"  {'symbol':<14s}  {'bef_vt':>7s}  {'total':>7s}  {'vt_rate':>8s}  {'lift':>6s}")
    for sym in sorted(reel1_ov.keys(), key=lambda s: -reel1_ov[s]):
        bv = reel1_bv.get(sym, 0)
        ov = reel1_ov[sym]
        rate = bv / ov if ov else 0
        lift = rate / baseline if baseline > 0 else 0
        log(f"  {sym:<14s}  {bv:7d}  {ov:7d}  {rate:>7.2%}  {lift:>5.2f}x")

    # ==================================================================
    # 10. MULTI-SPIN COMBO PATTERNS (2-spin sequences before VT)
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  10. 2-SPIN SEQUENCES BEFORE VT (idx categories)")
    log(f"{'='*70}")

    def categorize(d):
        """Categorize a spin's idx into a simple label."""
        r1, r2, r3 = d["r1"], d["r2"], d["r3"]
        s = r1 + r2 + r3
        if r1 == r2 == r3: return f"triple_{r1}"
        if s >= 18: return "high"
        if s <= 6: return "low"
        if max(r1,r2,r3) - min(r1,r2,r3) <= 2: return "tight"
        if max(r1,r2,r3) - min(r1,r2,r3) >= 6: return "wide"
        return "mid"

    seq2_bv = Counter()
    seq2_ov = Counter()
    for i in range(1, len(idx_data) - 1):
        cat_prev = categorize(idx_data[i-1])
        cat_cur = categorize(idx_data[i])
        seq = f"{cat_prev}->{cat_cur}"
        seq2_ov[seq] += 1
        if idx_data[i + 1]["is_vt"]:
            seq2_bv[seq] += 1

    total_s2_ov = sum(seq2_ov.values())
    log(f"\n  Top sequences before VT:")
    log(f"  {'sequence':<30s}  {'bef_vt':>7s}  {'total':>7s}  {'vt_rate':>8s}  {'lift':>6s}")
    # Show all sequences that appeared before at least 1 VT, sorted by lift
    vt_seqs = [(seq, seq2_bv[seq], seq2_ov[seq]) for seq in seq2_bv if seq2_bv[seq] > 0]
    vt_seqs.sort(key=lambda x: -x[1]/x[2] if x[2] > 0 else 0)
    for seq, bv, ov in vt_seqs[:25]:
        rate = bv / ov if ov else 0
        lift = rate / baseline
        log(f"  {seq:<30s}  {bv:7d}  {ov:7d}  {rate:>7.2%}  {lift:>5.2f}x")

    # ==================================================================
    # 11. GAP POSITION AWARE — VT rate by position within gap
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  11. VT RATE BY SPINS-SINCE-LAST-VT (pity timer check)")
    log(f"{'='*70}")

    # For each spin, compute how many spins since the last VT
    dist_vt = Counter()
    dist_total = Counter()
    last_vt_pos = -1

    for i, d in enumerate(idx_data):
        if d["is_vt"]:
            if last_vt_pos >= 0:
                gap_pos = i - last_vt_pos
                dist_vt[gap_pos] += 1
            last_vt_pos = i
        else:
            if last_vt_pos >= 0:
                gap_pos = i - last_vt_pos
                dist_total[gap_pos] += 1

    # Bucket by ranges
    buckets = [(1,5), (6,10), (11,15), (16,20), (21,25), (26,30),
               (31,35), (36,40), (41,50), (51,60), (61,80), (81,100)]

    log(f"  {'range':>8s}  {'vts':>5s}  {'total_spins':>11s}  {'vt_rate':>8s}  {'lift':>6s}")
    for lo, hi in buckets:
        vts = sum(dist_vt.get(p, 0) for p in range(lo, hi+1))
        tot = sum(dist_total.get(p, 0) for p in range(lo, hi+1)) + vts
        if tot == 0: continue
        rate = vts / tot
        lift = rate / baseline if baseline > 0 else 0
        log(f"  {lo:3d}-{hi:3d}  {vts:5d}  {tot:11d}  {rate:>7.2%}  {lift:>5.2f}x")

    # ==================================================================
    # 12. COMPOUND STRATEGIES — combining multiple features
    # ==================================================================
    log(f"\n{'='*70}")
    log(f"  12. COMPOUND STRATEGIES")
    log(f"{'='*70}")

    # Strategies that combine idx features with gap position
    # We need to track gap position
    last_vt_idx = -1
    compound_data = []
    for i, d in enumerate(idx_data):
        gap_pos = i - last_vt_idx if last_vt_idx >= 0 else i
        compound_data.append({"gap_pos": gap_pos, **d})
        if d["is_vt"]:
            last_vt_idx = i

    def strat_gap_ge20(d, h): return d["gap_pos"] >= 20
    def strat_gap_ge30(d, h): return d["gap_pos"] >= 30
    def strat_gap_ge40(d, h): return d["gap_pos"] >= 40
    def strat_gap_ge20_r3_8(d, h): return d["gap_pos"] >= 20 and d["r3"] == 8
    def strat_gap_ge20_sum_ge15(d, h): return d["gap_pos"] >= 20 and d["r1"]+d["r2"]+d["r3"] >= 15
    def strat_gap_ge20_no_pair(d, h): return d["gap_pos"] >= 20 and d["r1"]!=d["r2"] and d["r1"]!=d["r3"] and d["r2"]!=d["r3"]
    def strat_gap_ge30_r3_8(d, h): return d["gap_pos"] >= 30 and d["r3"] == 8
    def strat_gap_ge30_sum_ge15(d, h): return d["gap_pos"] >= 30 and d["r1"]+d["r2"]+d["r3"] >= 15
    def strat_gap_ge15_triple_csv(d, h): return d["gap_pos"] >= 15 and d["is_triple"]
    def strat_after_triple_non_vt(d, h):
        # Bet on the spin AFTER a non-VT triple when gap >= 20
        if len(h) == 0: return False
        prev = h[-1] if h else None
        return prev and prev.get("is_triple") and not prev.get("is_vt") and d["gap_pos"] >= 20

    cstrategies = {
        "Always_bet": lambda d, h: True,
        "gap>=20": strat_gap_ge20,
        "gap>=30": strat_gap_ge30,
        "gap>=40": strat_gap_ge40,
        "gap>=20+r3=8": strat_gap_ge20_r3_8,
        "gap>=20+sum>=15": strat_gap_ge20_sum_ge15,
        "gap>=20+no_pair": strat_gap_ge20_no_pair,
        "gap>=30+r3=8": strat_gap_ge30_r3_8,
        "gap>=30+sum>=15": strat_gap_ge30_sum_ge15,
        "gap>=15+triple": strat_gap_ge15_triple_csv,
    }

    log(f"\n  {'strategy':<24s}  {'bets':>6s}  {'caught':>7s}  {'missed':>7s}  "
        f"{'catch%':>7s}  {'prec%':>7s}  {'bets/hit':>8s}  {'saved%':>7s}")
    log(f"  {'-'*92}")

    for name, fn in cstrategies.items():
        bets = caught = missed = 0
        for i in range(len(compound_data) - 1):
            cur = compound_data[i]
            next_vt = compound_data[i + 1]["is_vt"]
            if fn(cur, compound_data[:i]):
                bets += 1
                if next_vt: caught += 1
            else:
                if next_vt: missed += 1

        catch_pct = caught / total_vts * 100 if total_vts > 0 else 0
        prec = caught / bets * 100 if bets > 0 else 0
        bph = bets / caught if caught > 0 else float("inf")
        saved = (1 - bets / (len(compound_data) - 1)) * 100

        log(f"  {name:<24s}  {bets:>6d}  {caught:>7d}  {missed:>7d}  "
            f"{catch_pct:>6.1f}%  {prec:>6.1f}%  {bph:>8.1f}  {saved:>6.1f}%")

    log(f"\n{'='*70}")
    log(f"  DONE — all analyses complete")
    log(f"{'='*70}")


if __name__ == "__main__":
    main()
