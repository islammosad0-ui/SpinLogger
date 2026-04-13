#!/usr/bin/env python3
"""
71_vt_signal_sim.py — Replay simulation of VT signal strategies.

Replays the merged il2cpp trace (idx) + spin_history data spin-by-spin.
For each spin, compute signals, decide BET or SKIP, then check if next spin is VT.
Report KPIs: catch rate, bets/hit, precision, saved spins, etc.

Tests:
  A) Current Layer 1 (as shipped in SLIdxStrategy.m)
  B) New signals from 70_vt_gap_deep_dive findings
  C) Combined (L1 corrected + L2 window)
  D) Sweep thresholds for each strategy
"""
from __future__ import annotations
import json, sys, math
from pathlib import Path
from collections import Counter, deque
from typing import List, Dict, Optional

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
#  Data loading (same as 70_)
# ============================================================

REPO = Path(__file__).resolve().parents[3]
TRACE = REPO / "data" / "Ahmed" / "il2cpp_trace_20260412_045402.jsonl"
HIST  = REPO / "data" / "Ahmed" / "spin_history_Ahmed_2026-04-08.csv"


def load_and_merge() -> List[dict]:
    # Load trace
    settled = {}
    with TRACE.open() as f:
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

    # Load CSV
    import csv
    hist = {}
    with HIST.open() as f:
        for row in csv.DictReader(f):
            hist[int(row["seq"])] = row

    # Merge
    data = []
    for sn, t in sorted(settled.items()):
        rec = dict(t)
        h = hist.get(sn)
        if h:
            rec["reel_1"] = h.get("reel_1", "")
            rec["is_triple"] = h.get("is_triple", "false") == "true"
        else:
            rec["reel_1"] = ""
            rec["is_triple"] = (t.get("sym1") is not None and
                                t["sym1"] == t.get("sym2") == t.get("sym3"))
        # Determine if this spin IS a VT — use ONLY CSV ground truth
        # (trace SlotSymbol3 memory is desync'd and unreliable)
        is_vt = False
        if rec["is_triple"] and rec.get("reel_1") in ("accumulation", "spins"):
            is_vt = True
        rec["is_vt"] = is_vt
        data.append(rec)
    return data


# ============================================================
#  Signal strategies
# ============================================================

class Strategy:
    """Base class. Subclasses implement score(spin, history) -> int."""
    name: str = "base"

    def reset(self):
        pass

    def score(self, spin: dict, history: list) -> int:
        """Return composite score for the CURRENT spin. Positive = bullish for VT on NEXT spin."""
        return 0


class CurrentL1(Strategy):
    """The Layer 1 signals currently shipped in SLIdxStrategy.m (acc+spins type)."""
    name = "Current_L1"

    def score(self, spin: dict, history: list) -> int:
        r1 = spin.get("r1_idx")
        r2 = spin.get("r2_idx")
        r3 = spin.get("r3_idx")
        if r1 is None or r2 is None or r3 is None:
            return 0
        s = 0
        if r2 == 7: s += 2    # r2=7 star
        if r1 == 7: s += 1    # r1=7
        if r1 == 7 and r2 == 7: s += 1  # 77 pair
        if r3 == 1: s -= 1    # r3=1 bad
        if r2 == 0: s -= 1    # r2=0 bad
        return s


class NewGapSignals(Strategy):
    """New signals derived from the 70_ gap analysis."""
    name = "New_Gap"

    def score(self, spin: dict, history: list) -> int:
        r1 = spin.get("r1_idx")
        r2 = spin.get("r2_idx")
        r3 = spin.get("r3_idx")
        if r1 is None or r2 is None or r3 is None:
            return 0
        s = 0
        # idx=0 surge (biggest finding: +20pp, +17pp, +9pp lift at N-1)
        if r1 == 0: s += 2
        if r2 == 0: s += 2
        if r3 == 0: s += 1

        # r3_idx=6 (22x lift from 0.4% to 8.8%)
        if r3 == 6: s += 2
        # r2_idx=6 (doubled from 7.3% to 14.4%)
        if r2 == 6: s += 1

        # Same-idx convergence (40.6% vs 22.9%)
        if r1 == r2 == r3: s += 2

        # Spread compression (mean 2.73 vs 3.19)
        spread = max(r1, r2, r3) - min(r1, r2, r3)
        if spread <= 2: s += 1

        # r2=7 is actually BEARISH at N-1 (-13pp)
        if r2 == 7: s -= 1
        # r1=7 also drops (-15pp)
        if r1 == 7: s -= 1

        # r3=8 collapse (-21.4pp at N-1)
        if r3 == 8: s -= 2

        # r3=1 slight negative
        if r3 == 1: s -= 1

        return s


class NewGapWithWindow(Strategy):
    """New gap signals + 10-spin window patterns."""
    name = "New_Gap+Win"

    def score(self, spin: dict, history: list) -> int:
        r1 = spin.get("r1_idx")
        r2 = spin.get("r2_idx")
        r3 = spin.get("r3_idx")
        if r1 is None or r2 is None or r3 is None:
            return 0

        # Same single-spin signals as NewGapSignals
        s = 0
        if r1 == 0: s += 2
        if r2 == 0: s += 2
        if r3 == 0: s += 1
        if r3 == 6: s += 2
        if r2 == 6: s += 1
        if r1 == r2 == r3: s += 2
        spread = max(r1, r2, r3) - min(r1, r2, r3)
        if spread <= 2: s += 1
        if r2 == 7: s -= 1
        if r1 == 7: s -= 1
        if r3 == 8: s -= 2
        if r3 == 1: s -= 1

        # Window signals (last 10 spins)
        window = history[-10:] if len(history) >= 10 else history
        if len(window) >= 3:
            # Count idx=0 on any reel in window
            zero_count = sum(1 for h in window
                             if h.get("r1_idx") == 0 or h.get("r2_idx") == 0 or h.get("r3_idx") == 0)
            if zero_count >= 3: s += 1

            # Count same-idx spins in window
            same_count = sum(1 for h in window
                             if h.get("r1_idx") is not None and
                             h["r1_idx"] == h.get("r2_idx") == h.get("r3_idx"))
            if same_count >= 2: s += 1

            # r3=8 absence in last 5 (gap analysis: drops before VT)
            last5 = history[-5:] if len(history) >= 5 else history
            r3_8_count = sum(1 for h in last5 if h.get("r3_idx") == 8)
            if r3_8_count == 0 and len(last5) >= 3: s += 1

            # r2=7 absence in last 5
            r2_7_count = sum(1 for h in last5 if h.get("r2_idx") == 7)
            if r2_7_count == 0 and len(last5) >= 3: s += 1

            # r3=6 appeared recently (very rare normally but spikes before VT)
            r3_6_recent = any(h.get("r3_idx") == 6 for h in last5)
            if r3_6_recent: s += 1

        return s


class CorrectedL1(Strategy):
    """Layer 1 with flipped r2=7 and added idx=0 signals."""
    name = "Corrected_L1"

    def score(self, spin: dict, history: list) -> int:
        r1 = spin.get("r1_idx")
        r2 = spin.get("r2_idx")
        r3 = spin.get("r3_idx")
        if r1 is None or r2 is None or r3 is None:
            return 0
        s = 0
        # Corrected from gap analysis:
        if r1 == 0: s += 2
        if r2 == 0: s += 2
        if r3 == 6: s += 2
        if r2 == 6: s += 1
        if r1 == r2 == r3: s += 2
        if r3 == 8: s -= 2
        if r2 == 7: s -= 1
        if r3 == 1: s -= 1
        return s


class AlwaysBet(Strategy):
    """Baseline: bet on every spin."""
    name = "Always_Bet"

    def score(self, spin: dict, history: list) -> int:
        return 999  # always above any threshold


# ============================================================
#  Simulation engine
# ============================================================

def simulate(data: List[dict], strategy: Strategy, threshold: int) -> dict:
    """
    Replay spin-by-spin. On each spin i:
      1. Compute score from spin[i]'s idx
      2. If score >= threshold => BET on spin[i+1]
      3. Check if spin[i+1] is VT

    Returns KPIs.
    """
    strategy.reset()
    history = []

    total_vts = sum(1 for d in data if d["is_vt"])
    bets = 0
    vts_caught = 0
    vts_missed = 0
    bet_on_non_vt = 0
    scores_when_vt = []      # score at N-1 for each VT
    scores_when_not_vt = []  # score at N-1 for non-VT spins

    for i in range(len(data) - 1):
        spin = data[i]
        next_spin = data[i + 1]

        score = strategy.score(spin, history)
        history.append(spin)

        is_next_vt = next_spin["is_vt"]

        if is_next_vt:
            scores_when_vt.append(score)
        else:
            scores_when_not_vt.append(score)

        if score >= threshold:
            bets += 1
            if is_next_vt:
                vts_caught += 1
            else:
                bet_on_non_vt += 1
        else:
            if is_next_vt:
                vts_missed += 1

    # Also count VTs that are at position 0 (can't predict) as missed
    if data[0]["is_vt"]:
        vts_missed += 1

    catch_rate = vts_caught / total_vts * 100 if total_vts > 0 else 0
    precision = vts_caught / bets * 100 if bets > 0 else 0
    bets_per_hit = bets / vts_caught if vts_caught > 0 else float("inf")
    spins_saved_pct = (1 - bets / max(len(data) - 1, 1)) * 100

    return {
        "strategy": strategy.name,
        "threshold": threshold,
        "total_spins": len(data),
        "total_vts": total_vts,
        "bets": bets,
        "vts_caught": vts_caught,
        "vts_missed": vts_missed,
        "catch_rate": catch_rate,
        "precision": precision,
        "bets_per_hit": bets_per_hit,
        "spins_saved_pct": spins_saved_pct,
        "bet_on_non_vt": bet_on_non_vt,
        "scores_when_vt": scores_when_vt,
        "scores_when_not_vt": scores_when_not_vt,
    }


# ============================================================
#  Score distribution analysis
# ============================================================

def print_score_distribution(result: dict):
    """Show how scores distribute for VT vs non-VT next spins."""
    vt_scores = result["scores_when_vt"]
    nonvt_scores = result["scores_when_not_vt"]
    if not vt_scores:
        return

    all_scores = sorted(set(vt_scores + nonvt_scores))
    min_s = min(all_scores)
    max_s = max(all_scores)

    vt_c = Counter(vt_scores)
    nonvt_c = Counter(nonvt_scores)
    vt_total = len(vt_scores)
    nonvt_total = len(nonvt_scores)

    log(f"\n  Score distribution (N-1 score when next spin is VT vs not):")
    log(f"  {'score':>6s}  {'VT_cnt':>7s}  {'VT_%':>7s}  {'nonVT_%':>8s}  {'VT_rate':>8s}  {'cum_VT':>7s}  {'cum_bets':>9s}  {'cum_b/h':>8s}")

    cum_vt = 0
    cum_bets = 0
    # Walk from highest score downward (as if lowering threshold)
    for s in range(max_s, min_s - 1, -1):
        vc = vt_c.get(s, 0)
        nc = nonvt_c.get(s, 0)
        vt_pct = vc / vt_total * 100 if vt_total > 0 else 0
        nonvt_pct = nc / nonvt_total * 100 if nonvt_total > 0 else 0
        total_at_score = vc + nc
        vt_rate = vc / total_at_score * 100 if total_at_score > 0 else 0
        cum_vt += vc
        cum_bets += total_at_score
        cum_bph = cum_bets / cum_vt if cum_vt > 0 else float("inf")
        cum_catch = cum_vt / vt_total * 100

        if total_at_score > 0 or s == 0:
            log(f"  {s:6d}  {vc:7d}  {vt_pct:6.1f}%  {nonvt_pct:7.1f}%  {vt_rate:7.1f}%  "
                f"{cum_catch:5.1f}%  {cum_bets:9d}  {cum_bph:8.1f}")


# ============================================================
#  Main
# ============================================================

def main():
    log("Loading data...")
    data = load_and_merge()
    total_vts = sum(1 for d in data if d["is_vt"])
    log(f"  {len(data)} spins, {total_vts} VTs (base rate {total_vts/len(data)*100:.1f}%)\n")

    strategies = [
        AlwaysBet(),
        CurrentL1(),
        CorrectedL1(),
        NewGapSignals(),
        NewGapWithWindow(),
    ]

    # Header
    log("=" * 110)
    log(f"  {'strategy':<20s} {'thresh':>6s}  {'bets':>6s}  {'caught':>7s}  {'missed':>7s}  "
        f"{'catch%':>7s}  {'prec%':>7s}  {'bets/hit':>8s}  {'saved%':>7s}")
    log("=" * 110)

    all_results = []

    for strat in strategies:
        # Find score range first
        test = simulate(data, strat, -999)
        all_scores = test["scores_when_vt"] + test["scores_when_not_vt"]
        if not all_scores:
            continue
        min_s = min(all_scores)
        max_s = max(all_scores)

        # Sweep thresholds
        thresholds = sorted(set(range(min_s, max_s + 1)))
        for t in thresholds:
            r = simulate(data, strat, t)
            all_results.append(r)
            # Only print interesting thresholds (some bets, not all bets)
            if r["bets"] > 0 and r["bets"] < len(data):
                log(f"  {strat.name:<20s} {t:>6d}  {r['bets']:>6d}  {r['vts_caught']:>7d}  "
                    f"{r['vts_missed']:>7d}  {r['catch_rate']:>6.1f}%  {r['precision']:>6.1f}%  "
                    f"{r['bets_per_hit']:>8.1f}  {r['spins_saved_pct']:>6.1f}%")

        # Also print the always-bet baseline
        if isinstance(strat, AlwaysBet):
            r = simulate(data, strat, 0)
            log(f"  {'BASELINE':<20s} {'all':>6s}  {r['bets']:>6d}  {r['vts_caught']:>7d}  "
                f"{r['vts_missed']:>7d}  {r['catch_rate']:>6.1f}%  {r['precision']:>6.1f}%  "
                f"{r['bets_per_hit']:>8.1f}  {r['spins_saved_pct']:>6.1f}%")

        log("-" * 110)

    # Detailed score distributions for the key strategies
    for strat in [CurrentL1(), NewGapSignals(), NewGapWithWindow()]:
        log(f"\n{'='*70}")
        log(f"  SCORE DISTRIBUTION: {strat.name}")
        log(f"{'='*70}")
        r = simulate(data, strat, -999)
        print_score_distribution(r)

    # Best configs comparison
    log(f"\n{'='*70}")
    log(f"  BEST CONFIGS COMPARISON (Pareto-optimal catch% vs bets/hit)")
    log(f"{'='*70}")
    log(f"\n  Interpretation guide:")
    log(f"    catch% = what % of VTs you'd have bet MAX on")
    log(f"    bets/hit = how many MAX bets per actual VT hit")
    log(f"    precision = what % of your MAX bets actually hit a VT")
    log(f"    saved% = what % of spins you DON'T bet MAX on\n")

    # Find Pareto-optimal points
    interesting = [r for r in all_results if r["bets"] > 0 and r["vts_caught"] > 0
                   and not isinstance(r.get("_strat"), AlwaysBet)]

    # Group by strategy, find best bets/hit at various catch levels
    for strat_name in ["Current_L1", "Corrected_L1", "New_Gap", "New_Gap+Win"]:
        strat_results = [r for r in all_results if r["strategy"] == strat_name
                         and r["bets"] > 0 and r["vts_caught"] > 0]
        if not strat_results:
            continue
        log(f"\n  {strat_name}:")
        log(f"    {'thresh':>6s}  {'catch%':>7s}  {'bets/hit':>8s}  {'prec%':>7s}  {'bets':>6s}  {'caught':>7s}  {'saved%':>7s}")
        seen_catch = set()
        for r in sorted(strat_results, key=lambda x: -x["catch_rate"]):
            bucket = int(r["catch_rate"] / 10) * 10
            if bucket in seen_catch:
                continue
            seen_catch.add(bucket)
            log(f"    {r['threshold']:>6d}  {r['catch_rate']:>6.1f}%  {r['bets_per_hit']:>8.1f}  "
                f"{r['precision']:>6.1f}%  {r['bets']:>6d}  {r['vts_caught']:>7d}  {r['spins_saved_pct']:>6.1f}%")

    log(f"\n{'='*70}")
    log(f"  DONE")
    log(f"{'='*70}")


if __name__ == "__main__":
    main()
