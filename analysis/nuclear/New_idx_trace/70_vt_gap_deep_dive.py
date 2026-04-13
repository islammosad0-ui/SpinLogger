#!/usr/bin/env python3
"""
70_vt_gap_deep_dive.py — Exhaustive VT gap analysis on merged idx + spin_history data.

Merges il2cpp_trace JSONL (for reel idx 0-8) with spin_history CSV (for symbols,
counters, sa_* fields). Then analyzes the ENTIRE gap between Valuable Triples
(accumulation + spins triples) looking for any exploitable pattern.

Analyses:
  1. Gap statistics (lengths, distribution)
  2. Per-position-in-gap idx distributions (first/mid/last third)
  3. Idx value frequencies: gap-interior vs pre-VT windows (1,2,3,5,10 spins)
  4. Running mean/variance drift within gaps
  5. Bigram & trigram idx patterns preceding VTs
  6. Cumulative signal build-up (counts of specific idx, streaks, entropy)
  7. Cross-reel joint patterns (r1,r2,r3 tuples)
  8. sa_counter / symbol correlations within gaps
  9. Gap-length prediction from early-gap features
 10. Symbol (r1,r2,r3 payline) distributions within gaps
 11. Per-VT-type (ACC vs SPN) comparison
 12. Conditional: idx given previous gap length
"""
from __future__ import annotations
import json, sys, math, warnings
from pathlib import Path
from collections import Counter, defaultdict
from typing import List, Dict, Optional, Tuple
import numpy as np

warnings.filterwarnings("ignore")
try:
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
except Exception:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

def log(msg: str = ""):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

# ============================================================
#  Data loading & merge
# ============================================================

REPO = Path(__file__).resolve().parents[3]
TRACE = REPO / "data" / "Ahmed" / "il2cpp_trace_20260412_045402.jsonl"
HIST  = REPO / "data" / "Ahmed" / "spin_history_Ahmed_2026-04-08.csv"


def load_trace_idx(path: Path) -> Dict[int, dict]:
    """Load JSONL, keep only settled snapshots, extract idx per reel."""
    settled = {}
    with path.open() as f:
        for line in f:
            d = json.loads(line.strip())
            if d.get("spinning") != 0:
                continue
            sn = d["spin_num"]
            fields = d.get("fields", {})
            r1_idx = r2_idx = r3_idx = None
            sym1 = sym2 = sym3 = None
            for cls_key, cls_fields in fields.items():
                if cls_key.startswith("SlotBarManager_1"):
                    r1_idx = cls_fields.get("resultSymbolIndex", {}).get("i32")
                elif cls_key.startswith("SlotBarManager_2"):
                    r2_idx = cls_fields.get("resultSymbolIndex", {}).get("i32")
                elif cls_key.startswith("SlotBarManager_3"):
                    r3_idx = cls_fields.get("resultSymbolIndex", {}).get("i32")
                elif cls_key.startswith("SlotSymbol3"):
                    sym1 = cls_fields.get("symbol1", {}).get("i32")
                    sym2 = cls_fields.get("symbol2", {}).get("i32")
                    sym3 = cls_fields.get("symbol3", {}).get("i32")
            settled[sn] = {
                "spin_num": sn,
                "r1_idx": r1_idx, "r2_idx": r2_idx, "r3_idx": r3_idx,
                "sym1": sym1, "sym2": sym2, "sym3": sym3,
            }
    return settled


def load_hist_csv(path: Path) -> Dict[int, dict]:
    """Load spin_history CSV into {seq: row_dict}."""
    import csv
    rows = {}
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            seq = int(row["seq"])
            rows[seq] = row
    return rows


def merge_data(trace: Dict[int, dict], hist: Dict[int, dict]) -> List[dict]:
    """Merge trace idx with history on spin_num == seq. Return sorted list."""
    merged = []
    for sn, t in sorted(trace.items()):
        rec = dict(t)
        if sn in hist:
            h = hist[sn]
            rec["r1_sym"] = int(h["r1"]) if h["r1"] else None
            rec["r2_sym"] = int(h["r2"]) if h["r2"] else None
            rec["r3_sym"] = int(h["r3"]) if h["r3"] else None
            rec["reel_1"] = h.get("reel_1", "")
            rec["reel_2"] = h.get("reel_2", "")
            rec["reel_3"] = h.get("reel_3", "")
            rec["is_triple"] = h.get("is_triple", "false") == "true"
            rec["sa_spins"] = int(h["sa_spins"]) if h.get("sa_spins") else 0
            rec["sa_acc"] = int(h["sa_acc"]) if h.get("sa_acc") else 0
            rec["sa_spn"] = int(h["sa_spn"]) if h.get("sa_spn") else 0
            rec["sa_atk"] = int(h["sa_atk"]) if h.get("sa_atk") else 0
            rec["sa_stl"] = int(h["sa_stl"]) if h.get("sa_stl") else 0
            rec["sa_shd"] = int(h["sa_shd"]) if h.get("sa_shd") else 0
            rec["spins_remaining"] = int(h["spins_remaining"]) if h.get("spins_remaining") else 0
            rec["bet_level"] = int(h["bet_level"]) if h.get("bet_level") else 0
            rec["accum_pct"] = float(h["accum_pct"]) if h.get("accum_pct") else 0.0
        else:
            # Trace-only spin (no CSV match) — use symbols from trace
            rec["r1_sym"] = t.get("sym1")
            rec["r2_sym"] = t.get("sym2")
            rec["r3_sym"] = t.get("sym3")
            rec["reel_1"] = ""
            rec["is_triple"] = (t.get("sym1") is not None and
                                t["sym1"] == t.get("sym2") == t.get("sym3"))
            for k in ("sa_spins","sa_acc","sa_spn","sa_atk","sa_stl","sa_shd",
                       "spins_remaining","bet_level"):
                rec[k] = 0
            rec["accum_pct"] = 0.0
        merged.append(rec)
    return merged


def find_vts(data: List[dict]) -> List[int]:
    """Return row indices of Valuable Triples (acc or spins triples).
    Uses ONLY CSV ground truth — trace SlotSymbol3 memory is desync'd."""
    vt_indices = []
    for i, rec in enumerate(data):
        if not rec["is_triple"]:
            continue
        # Only trust CSV reel_1 for VT classification
        if rec.get("reel_1") in ("accumulation", "spins"):
            vt_indices.append(i)
    return vt_indices


def build_gaps(data: List[dict], vt_indices: List[int]) -> List[dict]:
    """Build gap objects: everything between consecutive VTs."""
    gaps = []
    for gi in range(len(vt_indices)):
        vt_row = vt_indices[gi]
        prev_vt = vt_indices[gi - 1] if gi > 0 else -1
        gap_start = prev_vt + 1
        gap_spins = data[gap_start:vt_row]  # spins WITHIN gap (excluding VT itself)
        vt_rec = data[vt_row]
        vt_type = "ACC" if vt_rec.get("reel_1") == "accumulation" else "SPN"
        gaps.append({
            "gap_idx": gi,
            "gap_len": len(gap_spins),
            "vt_row": vt_row,
            "vt_spin_num": vt_rec["spin_num"],
            "vt_type": vt_type,
            "vt_r1_idx": vt_rec["r1_idx"],
            "vt_r2_idx": vt_rec["r2_idx"],
            "vt_r3_idx": vt_rec["r3_idx"],
            "spins": gap_spins,
            "vt_rec": vt_rec,
        })
    return gaps


# ============================================================
#  Analysis functions
# ============================================================

def entropy(counts: Counter) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    e = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            e -= p * math.log2(p)
    return e


def analyze_1_gap_stats(gaps: List[dict]):
    """Basic gap length statistics."""
    log("=" * 70)
    log("  ANALYSIS 1: GAP LENGTH STATISTICS")
    log("=" * 70)
    lengths = [g["gap_len"] for g in gaps]
    arr = np.array(lengths, dtype=float)
    log(f"  Total VTs: {len(gaps)}")
    log(f"  Gap lengths: min={arr.min():.0f}  median={np.median(arr):.0f}  "
        f"mean={arr.mean():.1f}  max={arr.max():.0f}  std={arr.std():.1f}")

    # Histogram buckets
    buckets = [0, 5, 10, 20, 30, 50, 75, 100, 200]
    log(f"\n  Gap length distribution:")
    for i in range(len(buckets)):
        lo = buckets[i]
        hi = buckets[i + 1] if i + 1 < len(buckets) else 999
        n = sum(1 for l in lengths if lo <= l < hi)
        pct = n / len(lengths) * 100
        bar = "█" * int(pct / 2)
        log(f"    {lo:3d}-{hi:3d}: {n:3d} ({pct:5.1f}%) {bar}")

    # ACC vs SPN gap comparison
    acc_lens = [g["gap_len"] for g in gaps if g["vt_type"] == "ACC"]
    spn_lens = [g["gap_len"] for g in gaps if g["vt_type"] == "SPN"]
    if acc_lens and spn_lens:
        log(f"\n  ACC gaps (n={len(acc_lens)}): mean={np.mean(acc_lens):.1f} median={np.median(acc_lens):.0f}")
        log(f"  SPN gaps (n={len(spn_lens)}): mean={np.mean(spn_lens):.1f} median={np.median(spn_lens):.0f}")

    # Consecutive gap correlation
    if len(lengths) > 1:
        corr = np.corrcoef(lengths[:-1], lengths[1:])[0, 1]
        log(f"\n  Autocorrelation (gap[i] vs gap[i+1]): r={corr:.3f}")
    log()


def analyze_2_position_in_gap(gaps: List[dict]):
    """Idx distributions by position within gap (thirds)."""
    log("=" * 70)
    log("  ANALYSIS 2: IDX BY POSITION IN GAP (thirds)")
    log("=" * 70)
    # Only use gaps with >= 6 spins so thirds are meaningful
    valid = [g for g in gaps if g["gap_len"] >= 6]
    log(f"  Using {len(valid)} gaps with >= 6 spins\n")

    for reel in ("r1_idx", "r2_idx", "r3_idx"):
        thirds = {0: Counter(), 1: Counter(), 2: Counter()}
        for g in valid:
            n = g["gap_len"]
            t1 = n // 3
            t2 = 2 * n // 3
            for pos, spin in enumerate(g["spins"]):
                v = spin.get(reel)
                if v is None:
                    continue
                if pos < t1:
                    thirds[0][v] += 1
                elif pos < t2:
                    thirds[1][v] += 1
                else:
                    thirds[2][v] += 1

        log(f"  {reel}:")
        all_vals = sorted(set().union(*[c.keys() for c in thirds.values()]))
        header = f"    {'val':>4s}  {'1st_3rd':>8s}  {'mid_3rd':>8s}  {'last_3rd':>8s}  {'trend':>6s}"
        log(header)
        for v in all_vals:
            totals = [sum(thirds[t].values()) for t in range(3)]
            pcts = [thirds[t][v] / totals[t] * 100 if totals[t] > 0 else 0 for t in range(3)]
            trend = pcts[2] - pcts[0]
            arrow = "↑" if trend > 2 else "↓" if trend < -2 else "→"
            log(f"    {v:4d}  {pcts[0]:7.1f}%  {pcts[1]:7.1f}%  {pcts[2]:7.1f}%  {trend:+5.1f}{arrow}")
        log()


def analyze_3_prevt_windows(gaps: List[dict]):
    """Idx frequencies in the N spins immediately before VT vs gap interior."""
    log("=" * 70)
    log("  ANALYSIS 3: PRE-VT WINDOWS vs GAP INTERIOR")
    log("=" * 70)
    windows = [1, 2, 3, 5, 10]

    for reel in ("r1_idx", "r2_idx", "r3_idx"):
        log(f"\n  {reel}:")
        # Interior = all gap spins except last 10
        interior = Counter()
        pre = {w: Counter() for w in windows}
        for g in gaps:
            spins = g["spins"]
            n = len(spins)
            for pos, spin in enumerate(spins):
                v = spin.get(reel)
                if v is None:
                    continue
                dist_to_vt = n - pos  # how many spins before VT
                if dist_to_vt > 10:
                    interior[v] += 1
                for w in windows:
                    if dist_to_vt <= w:
                        pre[w][v] += 1

        int_total = sum(interior.values())
        if int_total == 0:
            continue

        all_vals = sorted(set(interior.keys()).union(*[c.keys() for c in pre.values()]))
        header_parts = [f"{'val':>4s}", f"{'interior':>9s}"]
        for w in windows:
            header_parts.append(f"{'pre_'+str(w):>8s}")
        header_parts.append(f"{'lift_1':>7s}")
        header_parts.append(f"{'lift_5':>7s}")
        log("    " + "  ".join(header_parts))

        for v in all_vals:
            int_pct = interior[v] / int_total * 100
            parts = [f"{v:4d}", f"{int_pct:8.1f}%"]
            lifts = {}
            for w in windows:
                w_total = sum(pre[w].values())
                w_pct = pre[w][v] / w_total * 100 if w_total > 0 else 0
                parts.append(f"{w_pct:7.1f}%")
                lifts[w] = w_pct - int_pct
            parts.append(f"{lifts[1]:+6.1f}p")
            parts.append(f"{lifts[5]:+6.1f}p")
            log("    " + "  ".join(parts))
    log()


def analyze_4_running_mean_drift(gaps: List[dict]):
    """Track running mean of each idx within gaps — does it drift toward VT?"""
    log("=" * 70)
    log("  ANALYSIS 4: RUNNING MEAN DRIFT WITHIN GAPS")
    log("=" * 70)
    # Normalize position to [0, 1] within each gap, bin into 10 segments
    bins = 10
    for reel in ("r1_idx", "r2_idx", "r3_idx"):
        bin_sums = [0.0] * bins
        bin_counts = [0] * bins
        for g in gaps:
            n = g["gap_len"]
            if n < 3:
                continue
            for pos, spin in enumerate(g["spins"]):
                v = spin.get(reel)
                if v is None:
                    continue
                frac = pos / max(n - 1, 1)
                b = min(int(frac * bins), bins - 1)
                bin_sums[b] += v
                bin_counts[b] += 1

        log(f"\n  {reel} mean by normalized position (0=gap start, 1=pre-VT):")
        for b in range(bins):
            mean = bin_sums[b] / bin_counts[b] if bin_counts[b] > 0 else float("nan")
            bar_len = int(mean * 3) if not math.isnan(mean) else 0
            bar = "▓" * bar_len
            lo = b / bins
            hi = (b + 1) / bins
            log(f"    [{lo:.1f}-{hi:.1f}]: mean={mean:5.2f}  n={bin_counts[b]:5d}  {bar}")

    # Also track variance
    log(f"\n  IDX VARIANCE by normalized position:")
    for reel in ("r1_idx", "r2_idx", "r3_idx"):
        bin_vals = [[] for _ in range(bins)]
        for g in gaps:
            n = g["gap_len"]
            if n < 3:
                continue
            for pos, spin in enumerate(g["spins"]):
                v = spin.get(reel)
                if v is None:
                    continue
                frac = pos / max(n - 1, 1)
                b = min(int(frac * bins), bins - 1)
                bin_vals[b].append(v)
        parts = [f"  {reel}:"]
        for b in range(bins):
            if len(bin_vals[b]) > 1:
                var = np.var(bin_vals[b])
                parts.append(f" {var:.2f}")
            else:
                parts.append("  n/a")
        log("".join(parts))
    log()


def analyze_5_bigrams_trigrams(gaps: List[dict]):
    """Most common idx bigrams and trigrams in the 5 spins before each VT."""
    log("=" * 70)
    log("  ANALYSIS 5: BIGRAM & TRIGRAM PATTERNS BEFORE VTs")
    log("=" * 70)
    for reel in ("r1_idx", "r2_idx", "r3_idx"):
        bigrams_pre5 = Counter()
        trigrams_pre5 = Counter()
        bigrams_all = Counter()
        trigrams_all = Counter()
        for g in gaps:
            spins = g["spins"]
            n = len(spins)
            vals = [s.get(reel) for s in spins]
            # Include the VT itself
            vt_val = g["vt_rec"].get(reel)
            vals_with_vt = vals + [vt_val]

            for i in range(1, len(vals)):
                if vals[i] is not None and vals[i-1] is not None:
                    bigrams_all[(vals[i-1], vals[i])] += 1
                    if i >= n - 5:
                        bigrams_pre5[(vals[i-1], vals[i])] += 1
            for i in range(2, len(vals)):
                if all(vals[j] is not None for j in (i-2, i-1, i)):
                    trigrams_all[(vals[i-2], vals[i-1], vals[i])] += 1
                    if i >= n - 5:
                        trigrams_pre5[(vals[i-2], vals[i-1], vals[i])] += 1

        all_total = sum(bigrams_all.values())
        pre_total = sum(bigrams_pre5.values())

        log(f"\n  {reel} — Top 15 bigrams BEFORE VT (last 5 spins):")
        log(f"    {'bigram':>12s}  {'pre5_cnt':>9s}  {'pre5_%':>7s}  {'all_%':>7s}  {'lift':>7s}")
        for bg, cnt in bigrams_pre5.most_common(15):
            pre_pct = cnt / pre_total * 100 if pre_total > 0 else 0
            all_cnt = bigrams_all[bg]
            all_pct = all_cnt / all_total * 100 if all_total > 0 else 0
            lift = pre_pct - all_pct
            log(f"    {str(bg):>12s}  {cnt:9d}  {pre_pct:6.1f}%  {all_pct:6.1f}%  {lift:+6.1f}p")

        at_total = sum(trigrams_all.values())
        pt_total = sum(trigrams_pre5.values())
        log(f"\n  {reel} — Top 10 trigrams BEFORE VT:")
        log(f"    {'trigram':>16s}  {'pre5_cnt':>9s}  {'pre5_%':>7s}  {'all_%':>7s}  {'lift':>7s}")
        for tg, cnt in trigrams_pre5.most_common(10):
            pre_pct = cnt / pt_total * 100 if pt_total > 0 else 0
            all_cnt = trigrams_all[tg]
            all_pct = all_cnt / at_total * 100 if at_total > 0 else 0
            lift = pre_pct - all_pct
            log(f"    {str(tg):>16s}  {cnt:9d}  {pre_pct:6.1f}%  {all_pct:6.1f}%  {lift:+6.1f}p")
    log()


def analyze_6_cumulative_signals(gaps: List[dict]):
    """Track cumulative counts of key idx values, streaks, and entropy within gaps."""
    log("=" * 70)
    log("  ANALYSIS 6: CUMULATIVE SIGNALS WITHIN GAPS")
    log("=" * 70)

    # For each gap, compute at the END (last spin before VT):
    # - count of r2_idx==7 (known strong signal)
    # - count of r1_idx==7
    # - count of r3_idx==1 (known bad signal)
    # - max consecutive same-value streak on each reel
    # - entropy of idx distribution
    # Compare short gaps (<=15) vs long gaps (>30) vs medium

    signal_names = [
        ("r2_idx", 7, "r2=7_count"),
        ("r1_idx", 7, "r1=7_count"),
        ("r3_idx", 4, "r3=4_count"),
        ("r3_idx", 1, "r3=1_count"),
        ("r1_idx", 3, "r1=3_count"),
        ("r2_idx", 6, "r2=6_count"),
        ("r2_idx", 0, "r2=0_count"),
    ]

    short_gaps = [g for g in gaps if g["gap_len"] <= 15]
    med_gaps = [g for g in gaps if 15 < g["gap_len"] <= 40]
    long_gaps = [g for g in gaps if g["gap_len"] > 40]

    def avg_signal(gap_list, reel, val):
        counts = []
        for g in gap_list:
            c = sum(1 for s in g["spins"] if s.get(reel) == val)
            counts.append(c / max(g["gap_len"], 1))  # normalize by gap length
        return np.mean(counts) if counts else 0

    log(f"\n  Normalized signal rates (count / gap_length):")
    log(f"  {'signal':>15s}  {'short<=15':>10s}  {'med 16-40':>10s}  {'long>40':>10s}")
    for reel, val, name in signal_names:
        s = avg_signal(short_gaps, reel, val)
        m = avg_signal(med_gaps, reel, val)
        l = avg_signal(long_gaps, reel, val)
        log(f"  {name:>15s}  {s:10.3f}  {m:10.3f}  {l:10.3f}")

    # Entropy comparison
    log(f"\n  Idx entropy by gap length bucket:")
    for reel in ("r1_idx", "r2_idx", "r3_idx"):
        for label, glist in [("short", short_gaps), ("med", med_gaps), ("long", long_gaps)]:
            ents = []
            for g in glist:
                c = Counter(s.get(reel) for s in g["spins"] if s.get(reel) is not None)
                ents.append(entropy(c))
            if ents:
                log(f"    {reel} {label:>6s}: mean_entropy={np.mean(ents):.3f}")

    # Streak analysis — max consecutive same idx before VT
    log(f"\n  Max consecutive same-idx streak in last 10 spins before VT:")
    for reel in ("r1_idx", "r2_idx", "r3_idx"):
        streaks = []
        for g in gaps:
            spins = g["spins"]
            tail = spins[-10:] if len(spins) >= 10 else spins
            vals = [s.get(reel) for s in tail if s.get(reel) is not None]
            max_streak = 1
            cur = 1
            for i in range(1, len(vals)):
                if vals[i] == vals[i-1]:
                    cur += 1
                    max_streak = max(max_streak, cur)
                else:
                    cur = 1
            streaks.append(max_streak)
        if streaks:
            log(f"    {reel}: mean_max_streak={np.mean(streaks):.2f}  max={max(streaks)}")
    log()


def analyze_7_cross_reel(gaps: List[dict]):
    """Joint (r1_idx, r2_idx, r3_idx) tuples — pre-VT vs interior."""
    log("=" * 70)
    log("  ANALYSIS 7: CROSS-REEL JOINT PATTERNS")
    log("=" * 70)

    pre3_tuples = Counter()
    interior_tuples = Counter()
    for g in gaps:
        n = g["gap_len"]
        for pos, s in enumerate(g["spins"]):
            r1, r2, r3 = s.get("r1_idx"), s.get("r2_idx"), s.get("r3_idx")
            if r1 is None or r2 is None or r3 is None:
                continue
            t = (r1, r2, r3)
            if pos >= n - 3:
                pre3_tuples[t] += 1
            else:
                interior_tuples[t] += 1

    int_total = sum(interior_tuples.values())
    pre_total = sum(pre3_tuples.values())

    log(f"\n  Top 20 (r1,r2,r3) tuples in last 3 spins before VT:")
    log(f"  {'tuple':>14s}  {'pre3_cnt':>9s}  {'pre3_%':>7s}  {'int_%':>7s}  {'lift':>7s}")
    for t, cnt in pre3_tuples.most_common(20):
        pre_pct = cnt / pre_total * 100 if pre_total > 0 else 0
        int_pct = interior_tuples[t] / int_total * 100 if int_total > 0 else 0
        lift = pre_pct - int_pct
        log(f"  {str(t):>14s}  {cnt:9d}  {pre_pct:6.1f}%  {int_pct:6.1f}%  {lift:+6.1f}p")

    # Also check: does r1==r2==r3 (same idx) appear more before VTs?
    pre_same = sum(c for (r1,r2,r3), c in pre3_tuples.items() if r1 == r2 == r3)
    int_same = sum(c for (r1,r2,r3), c in interior_tuples.items() if r1 == r2 == r3)
    log(f"\n  Same-idx (r1==r2==r3): pre3={pre_same}/{pre_total} ({pre_same/pre_total*100:.1f}%) "
        f"vs interior={int_same}/{int_total} ({int_same/int_total*100:.1f}%)")

    # Check: r2 == specific values in cross-reel context
    log(f"\n  r2_idx distribution in pre-3 vs interior:")
    for v in range(9):
        pre_c = sum(c for (r1,r2,r3), c in pre3_tuples.items() if r2 == v)
        int_c = sum(c for (r1,r2,r3), c in interior_tuples.items() if r2 == v)
        pre_pct = pre_c / pre_total * 100 if pre_total > 0 else 0
        int_pct = int_c / int_total * 100 if int_total > 0 else 0
        log(f"    r2={v}: pre3={pre_pct:5.1f}%  int={int_pct:5.1f}%  lift={pre_pct-int_pct:+5.1f}p")
    log()


def analyze_8_sa_counters(gaps: List[dict]):
    """Correlate sa_* counters with gap length and VT proximity."""
    log("=" * 70)
    log("  ANALYSIS 8: sa_COUNTER PATTERNS WITHIN GAPS")
    log("=" * 70)

    # At the spin just before the VT, what are the sa_* values?
    counters = ["sa_spins", "sa_acc", "sa_spn", "sa_atk", "sa_stl", "sa_shd"]
    log(f"\n  sa_* values at the spin just BEFORE the VT:")
    log(f"  {'counter':>12s}  {'mean':>8s}  {'median':>8s}  {'min':>6s}  {'max':>6s}  {'std':>8s}")
    for cname in counters:
        vals = []
        for g in gaps:
            if g["spins"]:
                last = g["spins"][-1]
                v = last.get(cname, 0)
                vals.append(v)
        if vals:
            arr = np.array(vals, dtype=float)
            log(f"  {cname:>12s}  {arr.mean():8.1f}  {np.median(arr):8.0f}  "
                f"{arr.min():6.0f}  {arr.max():6.0f}  {arr.std():8.1f}")

    # Correlation: sa_spins at last spin vs gap_length
    sa_vals = []
    gap_lens = []
    for g in gaps:
        if g["spins"]:
            sa_vals.append(g["spins"][-1].get("sa_spins", 0))
            gap_lens.append(g["gap_len"])
    if len(sa_vals) > 2:
        corr = np.corrcoef(sa_vals, gap_lens)[0, 1]
        log(f"\n  Correlation sa_spins(last) vs gap_length: r={corr:.3f}")

    # sa_acc at various positions within gap
    log(f"\n  sa_acc by normalized position within gap:")
    bins = 5
    bin_vals = [[] for _ in range(bins)]
    for g in gaps:
        n = g["gap_len"]
        if n < 3:
            continue
        for pos, spin in enumerate(g["spins"]):
            frac = pos / max(n - 1, 1)
            b = min(int(frac * bins), bins - 1)
            bin_vals[b].append(spin.get("sa_acc", 0))
    for b in range(bins):
        if bin_vals[b]:
            log(f"    [{b/bins:.1f}-{(b+1)/bins:.1f}]: mean_sa_acc={np.mean(bin_vals[b]):.1f}")
    log()


def analyze_9_gap_prediction(gaps: List[dict]):
    """Can we predict gap length from early-gap idx features?"""
    log("=" * 70)
    log("  ANALYSIS 9: GAP-LENGTH PREDICTION FROM EARLY IDX")
    log("=" * 70)

    # Use first 5 spins of each gap to predict if gap will be short (<20) or long (>=20)
    valid = [g for g in gaps if g["gap_len"] >= 5]
    log(f"  Using {len(valid)} gaps with >= 5 spins")

    # Feature: mean idx of first 5 spins for each reel
    features = []
    labels = []
    for g in valid:
        first5 = g["spins"][:5]
        r1_mean = np.mean([s["r1_idx"] for s in first5 if s.get("r1_idx") is not None])
        r2_mean = np.mean([s["r2_idx"] for s in first5 if s.get("r2_idx") is not None])
        r3_mean = np.mean([s["r3_idx"] for s in first5 if s.get("r3_idx") is not None])
        # Count of r2=7 in first 5
        r2_7_cnt = sum(1 for s in first5 if s.get("r2_idx") == 7)
        features.append([r1_mean, r2_mean, r3_mean, r2_7_cnt])
        labels.append(1 if g["gap_len"] < 20 else 0)

    features = np.array(features)
    labels = np.array(labels)

    log(f"  Short gaps (<20): {labels.sum()}/{len(labels)} ({labels.mean()*100:.1f}%)")
    log(f"\n  Early-gap feature means by gap outcome:")
    log(f"  {'feature':>20s}  {'short(<20)':>10s}  {'long(>=20)':>10s}  {'diff':>8s}")
    fnames = ["r1_mean_5", "r2_mean_5", "r3_mean_5", "r2=7_cnt_5"]
    for fi, fn in enumerate(fnames):
        short_mean = features[labels == 1, fi].mean() if labels.sum() > 0 else 0
        long_mean = features[labels == 0, fi].mean() if (1-labels).sum() > 0 else 0
        log(f"  {fn:>20s}  {short_mean:10.2f}  {long_mean:10.2f}  {short_mean-long_mean:+8.2f}")

    # Also: does the PREVIOUS gap length predict the next?
    if len(gaps) > 1:
        prev_lens = [gaps[i-1]["gap_len"] for i in range(1, len(gaps))]
        next_lens = [gaps[i]["gap_len"] for i in range(1, len(gaps))]
        corr = np.corrcoef(prev_lens, next_lens)[0, 1]
        log(f"\n  Previous gap length -> next gap length correlation: r={corr:.3f}")

    # Previous VT type -> next gap length
    log(f"\n  Previous VT type -> next gap length:")
    for prev_type in ("ACC", "SPN"):
        next_gaps = [gaps[i]["gap_len"] for i in range(1, len(gaps)) if gaps[i-1]["vt_type"] == prev_type]
        if next_gaps:
            log(f"    After {prev_type}: n={len(next_gaps)}  mean={np.mean(next_gaps):.1f}  "
                f"median={np.median(next_gaps):.0f}")
    log()


def analyze_10_symbol_distributions(gaps: List[dict]):
    """Payline symbol distributions within gaps."""
    log("=" * 70)
    log("  ANALYSIS 10: SYMBOL DISTRIBUTIONS WITHIN GAPS")
    log("=" * 70)

    # Reel_1 symbol frequencies in last 10 vs interior
    reel_names = {1: "coin", 2: "goldSack", 3: "attack", 4: "steal",
                  5: "shield", 6: "spins", 30: "accumulation"}

    for reel_col, sym_col in [("r1_sym", "reel_1"), ("r2_sym", "reel_2"), ("r3_sym", "reel_3")]:
        pre10 = Counter()
        interior = Counter()
        for g in gaps:
            n = g["gap_len"]
            for pos, s in enumerate(g["spins"]):
                name = s.get(sym_col, "") or str(s.get(reel_col, ""))
                if not name:
                    continue
                if pos >= n - 10:
                    pre10[name] += 1
                else:
                    interior[name] += 1

        int_total = sum(interior.values())
        pre_total = sum(pre10.values())
        if int_total == 0 or pre_total == 0:
            continue

        log(f"\n  {reel_col} symbol: pre-10 vs interior")
        all_names = sorted(set(interior.keys()) | set(pre10.keys()))
        log(f"    {'symbol':>15s}  {'interior':>9s}  {'pre10':>9s}  {'lift':>7s}")
        for name in all_names:
            int_pct = interior[name] / int_total * 100
            pre_pct = pre10[name] / pre_total * 100
            log(f"    {name:>15s}  {int_pct:8.1f}%  {pre_pct:8.1f}%  {pre_pct-int_pct:+6.1f}p")
    log()


def analyze_11_vt_type_comparison(gaps: List[dict]):
    """Compare idx patterns for ACC vs SPN VTs."""
    log("=" * 70)
    log("  ANALYSIS 11: ACC vs SPN VT COMPARISON")
    log("=" * 70)

    for vt_type in ("ACC", "SPN"):
        type_gaps = [g for g in gaps if g["vt_type"] == vt_type]
        log(f"\n  {vt_type} VTs (n={len(type_gaps)}):")

        for reel in ("r1_idx", "r2_idx", "r3_idx"):
            # Last 5 spins before VT
            pre5 = Counter()
            for g in type_gaps:
                for s in g["spins"][-5:]:
                    v = s.get(reel)
                    if v is not None:
                        pre5[v] += 1
            total = sum(pre5.values())
            if total == 0:
                continue
            top5 = pre5.most_common(5)
            dist_str = ", ".join(f"{v}:{c/total*100:.0f}%" for v, c in top5)
            log(f"    {reel} pre-5 dist: {dist_str}")

        # VT idx values themselves
        r1s = [g["vt_r1_idx"] for g in type_gaps if g["vt_r1_idx"] is not None]
        r2s = [g["vt_r2_idx"] for g in type_gaps if g["vt_r2_idx"] is not None]
        r3s = [g["vt_r3_idx"] for g in type_gaps if g["vt_r3_idx"] is not None]
        if r1s:
            log(f"    VT idx: r1={Counter(r1s).most_common(3)}  "
                f"r2={Counter(r2s).most_common(3)}  r3={Counter(r3s).most_common(3)}")
    log()


def analyze_12_conditional_patterns(gaps: List[dict], data: List[dict]):
    """Conditional: idx patterns given previous gap length, and gap-over-gap trends."""
    log("=" * 70)
    log("  ANALYSIS 12: CONDITIONAL & GAP-OVER-GAP PATTERNS")
    log("=" * 70)

    # After a short gap, are certain idx more common in the next gap's first 5?
    for i in range(1, len(gaps)):
        prev_len = gaps[i-1]["gap_len"]
    log(f"\n  First 5 spins of gap, conditioned on PREVIOUS gap length:")
    for reel in ("r1_idx", "r2_idx", "r3_idx"):
        after_short = Counter()  # prev gap <= 10
        after_long = Counter()   # prev gap > 30
        for i in range(1, len(gaps)):
            prev_len = gaps[i-1]["gap_len"]
            first5 = gaps[i]["spins"][:5]
            target = after_short if prev_len <= 10 else (after_long if prev_len > 30 else None)
            if target is None:
                continue
            for s in first5:
                v = s.get(reel)
                if v is not None:
                    target[v] += 1
        as_total = sum(after_short.values())
        al_total = sum(after_long.values())
        if as_total == 0 or al_total == 0:
            continue
        log(f"\n    {reel} (first 5 of gap):")
        log(f"    {'val':>4s}  {'after_short':>12s}  {'after_long':>12s}  {'diff':>7s}")
        for v in range(9):
            as_pct = after_short[v] / as_total * 100
            al_pct = after_long[v] / al_total * 100
            log(f"    {v:4d}  {as_pct:11.1f}%  {al_pct:11.1f}%  {as_pct-al_pct:+6.1f}p")

    # Gap length trend: running average of last 3 gaps
    if len(gaps) >= 4:
        log(f"\n  Gap length rolling avg (window=3) and actual:")
        for i in range(3, len(gaps)):
            avg3 = np.mean([gaps[j]["gap_len"] for j in range(i-3, i)])
            actual = gaps[i]["gap_len"]
            diff = actual - avg3
            log(f"    gap#{i:2d}: avg_prev3={avg3:5.1f}  actual={actual:3d}  diff={diff:+6.1f}")
    log()


def analyze_13_parity_modular(gaps: List[dict]):
    """Check if idx values modulo small numbers show patterns near VTs."""
    log("=" * 70)
    log("  ANALYSIS 13: MODULAR / PARITY PATTERNS")
    log("=" * 70)

    for mod in (2, 3):
        for reel in ("r1_idx", "r2_idx", "r3_idx"):
            pre5 = Counter()
            interior = Counter()
            for g in gaps:
                n = g["gap_len"]
                for pos, s in enumerate(g["spins"]):
                    v = s.get(reel)
                    if v is None:
                        continue
                    r = v % mod
                    if pos >= n - 5:
                        pre5[r] += 1
                    else:
                        interior[r] += 1

            int_total = sum(interior.values())
            pre_total = sum(pre5.values())
            if int_total == 0 or pre_total == 0:
                continue

            parts = []
            for r in range(mod):
                int_pct = interior.get(r, 0) / int_total * 100
                pre_pct = pre5.get(r, 0) / pre_total * 100
                parts.append(f"mod{r}={pre_pct:.1f}%({pre_pct-int_pct:+.1f})")
            log(f"  {reel} mod{mod} pre-5: {', '.join(parts)}")
    log()


def analyze_14_sum_and_spread(gaps: List[dict]):
    """Sum (r1+r2+r3) and spread (max-min) of idx per spin — pre-VT vs interior."""
    log("=" * 70)
    log("  ANALYSIS 14: SUM & SPREAD OF IDX PER SPIN")
    log("=" * 70)

    pre5_sums = []
    int_sums = []
    pre5_spreads = []
    int_spreads = []
    for g in gaps:
        n = g["gap_len"]
        for pos, s in enumerate(g["spins"]):
            r1, r2, r3 = s.get("r1_idx"), s.get("r2_idx"), s.get("r3_idx")
            if r1 is None or r2 is None or r3 is None:
                continue
            total = r1 + r2 + r3
            spread = max(r1, r2, r3) - min(r1, r2, r3)
            if pos >= n - 5:
                pre5_sums.append(total)
                pre5_spreads.append(spread)
            else:
                int_sums.append(total)
                int_spreads.append(spread)

    if pre5_sums and int_sums:
        log(f"  idx sum (r1+r2+r3):")
        log(f"    interior: mean={np.mean(int_sums):.2f}  std={np.std(int_sums):.2f}")
        log(f"    pre-5:    mean={np.mean(pre5_sums):.2f}  std={np.std(pre5_sums):.2f}")
        log(f"    diff:     {np.mean(pre5_sums)-np.mean(int_sums):+.2f}")

    if pre5_spreads and int_spreads:
        log(f"\n  idx spread (max-min):")
        log(f"    interior: mean={np.mean(int_spreads):.2f}")
        log(f"    pre-5:    mean={np.mean(pre5_spreads):.2f}")
        log(f"    diff:     {np.mean(pre5_spreads)-np.mean(int_spreads):+.2f}")

    # Distribution of sums
    log(f"\n  Sum distribution (pre-5 vs interior):")
    int_total = len(int_sums)
    pre_total = len(pre5_sums)
    for s_val in range(0, 25):
        int_c = sum(1 for x in int_sums if x == s_val)
        pre_c = sum(1 for x in pre5_sums if x == s_val)
        int_pct = int_c / int_total * 100 if int_total > 0 else 0
        pre_pct = pre_c / pre_total * 100 if pre_total > 0 else 0
        if int_c + pre_c > 0:
            log(f"    sum={s_val:2d}: int={int_pct:5.1f}%  pre5={pre_pct:5.1f}%  lift={pre_pct-int_pct:+5.1f}p")
    log()


def analyze_15_delta_patterns(gaps: List[dict]):
    """Spin-to-spin idx deltas (changes) — are certain deltas more common before VTs?"""
    log("=" * 70)
    log("  ANALYSIS 15: SPIN-TO-SPIN IDX DELTAS")
    log("=" * 70)

    for reel in ("r1_idx", "r2_idx", "r3_idx"):
        pre5_deltas = Counter()
        int_deltas = Counter()
        for g in gaps:
            n = g["gap_len"]
            spins = g["spins"]
            for pos in range(1, n):
                prev_v = spins[pos-1].get(reel)
                cur_v = spins[pos].get(reel)
                if prev_v is None or cur_v is None:
                    continue
                delta = cur_v - prev_v
                if pos >= n - 5:
                    pre5_deltas[delta] += 1
                else:
                    int_deltas[delta] += 1

        int_total = sum(int_deltas.values())
        pre_total = sum(pre5_deltas.values())
        if int_total == 0 or pre_total == 0:
            continue

        log(f"\n  {reel} deltas (top 10 by lift):")
        log(f"    {'delta':>6s}  {'interior':>9s}  {'pre5':>9s}  {'lift':>7s}")
        all_deltas = sorted(set(int_deltas.keys()) | set(pre5_deltas.keys()))
        rows = []
        for d in all_deltas:
            int_pct = int_deltas.get(d, 0) / int_total * 100
            pre_pct = pre5_deltas.get(d, 0) / pre_total * 100
            rows.append((d, int_pct, pre_pct, pre_pct - int_pct))
        rows.sort(key=lambda x: -abs(x[3]))
        for d, ip, pp, lift in rows[:10]:
            log(f"    {d:+6d}  {ip:8.1f}%  {pp:8.1f}%  {lift:+6.1f}p")
    log()


def analyze_16_accum_pct_at_vt(gaps: List[dict]):
    """Accumulation percentage at the moment of VT."""
    log("=" * 70)
    log("  ANALYSIS 16: ACCUM_PCT NEAR VTs")
    log("=" * 70)

    for vt_type in ("ACC", "SPN", "ALL"):
        subset = gaps if vt_type == "ALL" else [g for g in gaps if g["vt_type"] == vt_type]
        pcts = []
        for g in subset:
            if g["spins"]:
                pct = g["spins"][-1].get("accum_pct", 0)
                if pct > 0:
                    pcts.append(pct)
        if pcts:
            arr = np.array(pcts)
            log(f"  {vt_type} VTs (n={len(pcts)}): accum_pct mean={arr.mean():.1f}%  "
                f"median={np.median(arr):.1f}%  min={arr.min():.1f}%  max={arr.max():.1f}%")
    log()


# ============================================================
#  Main
# ============================================================

def main():
    log("Loading trace...")
    trace = load_trace_idx(TRACE)
    log(f"  {len(trace)} settled snapshots from trace")

    log("Loading spin history...")
    hist = load_hist_csv(HIST)
    log(f"  {len(hist)} rows from CSV")

    log("Merging...")
    data = merge_data(trace, hist)
    log(f"  {len(data)} merged spins")

    # Count how many have both idx and CSV data
    both = sum(1 for d in data if d.get("r1_idx") is not None and d.get("reel_1"))
    log(f"  {both} spins have both idx + CSV data")

    vt_indices = find_vts(data)
    log(f"  {len(vt_indices)} Valuable Triples found")

    gaps = build_gaps(data, vt_indices)
    log(f"  {len(gaps)} gaps built\n")

    # Run all analyses
    analyze_1_gap_stats(gaps)
    analyze_2_position_in_gap(gaps)
    analyze_3_prevt_windows(gaps)
    analyze_4_running_mean_drift(gaps)
    analyze_5_bigrams_trigrams(gaps)
    analyze_6_cumulative_signals(gaps)
    analyze_7_cross_reel(gaps)
    analyze_8_sa_counters(gaps)
    analyze_9_gap_prediction(gaps)
    analyze_10_symbol_distributions(gaps)
    analyze_11_vt_type_comparison(gaps)
    analyze_12_conditional_patterns(gaps, data)
    analyze_13_parity_modular(gaps)
    analyze_14_sum_and_spread(gaps)
    analyze_15_delta_patterns(gaps)
    analyze_16_accum_pct_at_vt(gaps)

    log("=" * 70)
    log("  DONE — 16 analyses complete")
    log("=" * 70)


if __name__ == "__main__":
    main()
