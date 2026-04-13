#!/usr/bin/env python3
"""
78_confidence_and_combos.py — Statistical confidence check + combo strategies.

1. Validate gap-based strategies on FULL CSV (7798 spins, 155 VTs, no idx needed)
2. Test combined/stacked rules on trace subset (1107 spins with idx)
3. Binomial p-values for key findings
"""
import json, csv, sys, math
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


def binomial_pvalue(k, n, p):
    """One-sided p-value: P(X >= k) under Binomial(n, p). Using normal approx."""
    if n == 0 or p == 0: return 1.0
    mu = n * p
    sigma = math.sqrt(n * p * (1 - p))
    if sigma == 0: return 1.0
    z = (k - 0.5 - mu) / sigma  # continuity correction
    # Standard normal CDF approximation
    return 0.5 * math.erfc(z / math.sqrt(2))


def wilson_ci(k, n, z=1.96):
    """Wilson score 95% confidence interval for proportion."""
    if n == 0: return (0, 0)
    p_hat = k / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2*n)) / denom
    margin = z * math.sqrt((p_hat*(1-p_hat) + z**2/(4*n)) / n) / denom
    return (max(0, center - margin), min(1, center + margin))


def load_full_csv():
    """Load full CSV without trace data — for gap-only validation."""
    hist = {}
    with HIST.open() as f:
        for row in csv.DictReader(f):
            hist[int(row["seq"])] = row
    data = []
    for sn, row in sorted(hist.items()):
        is_triple = row["is_triple"] == "true"
        reel_1 = row.get("reel_1", "")
        is_vt = is_triple and reel_1 in ("accumulation", "spins")
        vt_type = ""
        if is_vt:
            vt_type = "ACC" if reel_1 == "accumulation" else "SPN"
        data.append({
            "spin_num": sn, "reel_1": reel_1,
            "is_triple": is_triple, "is_vt": is_vt, "vt_type": vt_type,
        })
    return data


def load_corrected_trace():
    """Load trace+CSV with corrected off-by-one."""
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


def run_gap_validation(data, label, is_target_fn):
    """Run gap-based strategies on full CSV data (no idx needed)."""
    N = len(data)
    total_targets = sum(1 for d in data if is_target_fn(d))
    baseline = total_targets / (N - 1) if N > 1 else 0

    log(f"\n{'='*90}")
    log(f"  {label}")
    log(f"  {N} spins, {total_targets} targets, baseline={baseline*100:.2f}%, bets/hit={((N-1)/total_targets):.1f}")
    log(f"{'='*90}")

    if total_targets < 5:
        log("  Too few targets")
        return

    # Build state
    last_target_pos = -1
    last_acc_pos = -1
    last_spn_pos = -1
    last_nv_triple_pos = -1

    states = []
    for i, d in enumerate(data):
        gap_vt = i - last_target_pos if last_target_pos >= 0 else 999
        gap_acc = i - last_acc_pos if last_acc_pos >= 0 else 999
        gap_spn = i - last_spn_pos if last_spn_pos >= 0 else 999
        gap_nv_tri = i - last_nv_triple_pos if last_nv_triple_pos >= 0 else 999

        states.append({
            "gap_vt": gap_vt, "gap_acc": gap_acc, "gap_spn": gap_spn,
            "gap_nv_tri": gap_nv_tri,
            "is_triple": d["is_triple"], "is_vt": d["is_vt"],
            "reel_1": d["reel_1"], "vt_type": d["vt_type"],
            "nxt_target": is_target_fn(data[i+1]) if i+1 < N else False,
        })

        if is_target_fn(d):
            last_target_pos = i
        if d["vt_type"] == "ACC":
            last_acc_pos = i
        if d["vt_type"] == "SPN":
            last_spn_pos = i
        if d["is_triple"] and not d["is_vt"]:
            last_nv_triple_pos = i

    strategies = {}
    strategies["Always_bet"] = lambda s: True
    for t in [20, 25, 30, 35, 40, 50, 60, 80]:
        strategies[f"gap>={t}"] = lambda s, t=t: s["gap_vt"] >= t

    strategies["gap_acc>=30"] = lambda s: s["gap_acc"] >= 30
    strategies["gap_acc>=40"] = lambda s: s["gap_acc"] >= 40
    strategies["gap_acc>=50"] = lambda s: s["gap_acc"] >= 50
    strategies["gap_acc>=60"] = lambda s: s["gap_acc"] >= 60
    strategies["gap_acc>=80"] = lambda s: s["gap_acc"] >= 80
    strategies["gap_acc>=100"] = lambda s: s["gap_acc"] >= 100

    strategies["gap_spn>=20"] = lambda s: s["gap_spn"] >= 20
    strategies["gap_spn>=30"] = lambda s: s["gap_spn"] >= 30
    strategies["gap_spn>=40"] = lambda s: s["gap_spn"] >= 40
    strategies["gap_spn>=50"] = lambda s: s["gap_spn"] >= 50
    strategies["gap_spn>=60"] = lambda s: s["gap_spn"] >= 60

    # CSV-based non-idx combos
    strategies["gap>=30+prev_steal"] = lambda s: s["gap_vt"] >= 30 and not s["is_triple"] and s["reel_1"] == "steal"
    strategies["gap>=30+prev_accum"] = lambda s: s["gap_vt"] >= 30 and not s["is_triple"] and s["reel_1"] == "accumulation"
    strategies["gap>=30+prev_triple"] = lambda s: s["gap_vt"] >= 30 and s["is_triple"]
    strategies["gap>=30+nv_tri<=5"] = lambda s: s["gap_vt"] >= 30 and 1 <= s["gap_nv_tri"] <= 5
    strategies["gap>=30+nv_tri<=3"] = lambda s: s["gap_vt"] >= 30 and 1 <= s["gap_nv_tri"] <= 3

    log(f"\n  {'strategy':<26s}  {'bets':>6s}  {'hit':>5s}  {'miss':>5s}  "
        f"{'catch%':>7s}  {'prec%':>7s}  {'lift':>5s}  {'bets/hit':>8s}  {'saved%':>7s}  "
        f"{'p-val':>8s}  {'95% CI':>14s}")
    log(f"  {'-'*115}")

    results = []
    for name, fn in strategies.items():
        bets = caught = missed = 0
        for s in states[:-1]:
            if fn(s):
                bets += 1
                if s["nxt_target"]: caught += 1
            else:
                if s["nxt_target"]: missed += 1
        if bets == 0: continue

        catch_pct = caught / total_targets * 100
        prec = caught / bets * 100
        bph = bets / caught if caught > 0 else float("inf")
        saved = (1 - bets / (N-1)) * 100
        lift = prec / (baseline * 100) if baseline > 0 else 0
        pval = binomial_pvalue(caught, bets, baseline)
        ci_lo, ci_hi = wilson_ci(caught, bets)

        results.append({
            "name": name, "bets": bets, "caught": caught, "missed": missed,
            "catch_pct": catch_pct, "prec": prec, "bph": bph,
            "saved": saved, "lift": lift, "pval": pval,
            "ci_lo": ci_lo, "ci_hi": ci_hi,
        })

    results.sort(key=lambda r: (-r["prec"], -r["caught"]))
    for r in results:
        if r["caught"] == 0: continue
        sig = ""
        if r["pval"] < 0.01: sig = " ***"
        elif r["pval"] < 0.05: sig = " **"
        elif r["pval"] < 0.10: sig = " *"
        ci_str = f"[{r['ci_lo']*100:.1f}-{r['ci_hi']*100:.1f}%]"
        log(f"  {r['name']:<26s}  {r['bets']:>6d}  {r['caught']:>5d}  {r['missed']:>5d}  "
            f"{r['catch_pct']:>6.1f}%  {r['prec']:>6.2f}%  {r['lift']:>4.1f}x  "
            f"{r['bph']:>8.1f}  {r['saved']:>6.1f}%  "
            f"{r['pval']:>8.4f}  {ci_str:>14s}{sig}")


def run_combo_strategies(data, label, is_target_fn):
    """Run combined/stacked strategies on trace data with idx."""
    idx_data = [d for d in data if d["r1"] is not None]
    N = len(idx_data)
    total_targets = sum(1 for d in idx_data if is_target_fn(d))
    baseline = total_targets / (N - 1) if N > 1 else 0

    log(f"\n{'='*90}")
    log(f"  COMBO STRATEGIES — {label}")
    log(f"  {N} spins with idx, {total_targets} targets, baseline={baseline*100:.2f}%")
    log(f"{'='*90}")

    if total_targets < 3:
        log("  Too few targets")
        return

    # Build state
    last_target_pos = -1
    last_acc_pos = -1
    last_spn_pos = -1
    last_nv_triple_pos = -1
    prev_r1 = prev_r2 = prev_r3 = 4
    prev_sum = 12

    states = []
    for i, d in enumerate(idx_data):
        gap_vt = i - last_target_pos if last_target_pos >= 0 else 999
        gap_acc = i - last_acc_pos if last_acc_pos >= 0 else 999
        gap_spn = i - last_spn_pos if last_spn_pos >= 0 else 999
        gap_nv_tri = i - last_nv_triple_pos if last_nv_triple_pos >= 0 else 999
        s = d["r1"] + d["r2"] + d["r3"]
        spread = max(d["r1"], d["r2"], d["r3"]) - min(d["r1"], d["r2"], d["r3"])
        all_diff = d["r1"] != d["r2"] and d["r1"] != d["r3"] and d["r2"] != d["r3"]
        combo = bucket(d["r1"]) + bucket(d["r2"]) + bucket(d["r3"])
        delta_sum = s - prev_sum
        abs_dr1 = abs(d["r1"] - prev_r1)

        states.append({
            "gap_vt": gap_vt, "gap_acc": gap_acc, "gap_spn": gap_spn,
            "gap_nv_tri": gap_nv_tri,
            "r1": d["r1"], "r2": d["r2"], "r3": d["r3"],
            "sum": s, "spread": spread, "all_diff": all_diff, "combo": combo,
            "is_triple": d["is_triple"], "is_vt": d["is_vt"],
            "reel_1": d["reel_1"], "vt_type": d["vt_type"],
            "delta_sum": delta_sum, "abs_dr1": abs_dr1,
            "nxt_target": is_target_fn(idx_data[i+1]) if i+1 < N else False,
        })

        if is_target_fn(d): last_target_pos = i
        if d["vt_type"] == "ACC": last_acc_pos = i
        if d["vt_type"] == "SPN": last_spn_pos = i
        if d["is_triple"] and not d["is_vt"]: last_nv_triple_pos = i
        prev_r1, prev_r2, prev_r3 = d["r1"], d["r2"], d["r3"]
        prev_sum = s

    # Combined strategies — stacking multiple filters
    strategies = {}

    # ALL VTs combos
    strategies["gap>=30+r3>=5+all_diff"] = lambda s: s["gap_vt"]>=30 and s["r3"]>=5 and s["all_diff"]
    strategies["gap>=30+r3>=5+sum>=15"] = lambda s: s["gap_vt"]>=30 and s["r3"]>=5 and s["sum"]>=15
    strategies["gap>=30+r3>=5+r1=3or7"] = lambda s: s["gap_vt"]>=30 and s["r3"]>=5 and s["r1"] in (3,7)
    strategies["gap>=30+r3>=5+r2>=5"] = lambda s: s["gap_vt"]>=30 and s["r3"]>=5 and s["r2"]>=5
    strategies["gap>=30+sum>=12+all_diff"] = lambda s: s["gap_vt"]>=30 and s["sum"]>=12 and s["all_diff"]
    strategies["gap>=30+sum>=15+r1=3or7"] = lambda s: s["gap_vt"]>=30 and s["sum"]>=15 and s["r1"] in (3,7)
    strategies["gap>=30+sum>=15+all_diff"] = lambda s: s["gap_vt"]>=30 and s["sum"]>=15 and s["all_diff"]
    strategies["gap>=30+r1=3or7+all_diff"] = lambda s: s["gap_vt"]>=30 and s["r1"] in (3,7) and s["all_diff"]
    strategies["gap>=30+r1=3or7+r2>=5"] = lambda s: s["gap_vt"]>=30 and s["r1"] in (3,7) and s["r2"]>=5
    strategies["gap>=30+r2=7+all_diff"] = lambda s: s["gap_vt"]>=30 and s["r2"]==7 and s["all_diff"]
    strategies["gap>=30+r2=7+r3>=5"] = lambda s: s["gap_vt"]>=30 and s["r2"]==7 and s["r3"]>=5
    strategies["gap>=40+r3>=5+sum>=15"] = lambda s: s["gap_vt"]>=40 and s["r3"]>=5 and s["sum"]>=15
    strategies["gap>=40+r3>=5+all_diff"] = lambda s: s["gap_vt"]>=40 and s["r3"]>=5 and s["all_diff"]
    strategies["gap>=40+r3>=5+r1=3or7"] = lambda s: s["gap_vt"]>=40 and s["r3"]>=5 and s["r1"] in (3,7)
    strategies["gap>=40+r3>=5+r2>=5"] = lambda s: s["gap_vt"]>=40 and s["r3"]>=5 and s["r2"]>=5
    strategies["gap>=40+sum>=15+all_diff"] = lambda s: s["gap_vt"]>=40 and s["sum"]>=15 and s["all_diff"]

    # 4-filter combos
    strategies["gap>=30+r3>=5+all_diff+sum>=15"] = lambda s: s["gap_vt"]>=30 and s["r3"]>=5 and s["all_diff"] and s["sum"]>=15
    strategies["gap>=30+r1=3or7+r3>=5+all_diff"] = lambda s: s["gap_vt"]>=30 and s["r1"] in (3,7) and s["r3"]>=5 and s["all_diff"]
    strategies["gap>=40+r3>=5+sum>=15+r1=3or7"] = lambda s: s["gap_vt"]>=40 and s["r3"]>=5 and s["sum"]>=15 and s["r1"] in (3,7)

    # ACC-specific combos
    strategies["gap_acc>=60+r1=3or7+r2>=4"] = lambda s: s["gap_acc"]>=60 and s["r1"] in (3,7) and s["r2"]>=4
    strategies["gap_acc>=60+r1=3or7+all_diff"] = lambda s: s["gap_acc"]>=60 and s["r1"] in (3,7) and s["all_diff"]
    strategies["gap_acc>=80+r1=3or7+r2=7"] = lambda s: s["gap_acc"]>=80 and s["r1"] in (3,7) and s["r2"]==7
    strategies["gap>=30+prev_steal+gap_vt>=30"] = lambda s: s["gap_vt"]>=30 and not s["is_triple"] and s["reel_1"]=="steal"
    strategies["gap_acc>=60+prev_steal"] = lambda s: s["gap_acc"]>=60 and not s["is_triple"] and s["reel_1"]=="steal"
    strategies["gap_acc>=60+MML_or_MHM"] = lambda s: s["gap_acc"]>=60 and s["combo"] in ("MML","MHM")
    strategies["gap>=30+low_mom+r1=3or7"] = lambda s: s["gap_vt"]>=30 and s["abs_dr1"]<=1 and s["r1"] in (3,7)
    strategies["gap>=30+low_mom+all_diff"] = lambda s: s["gap_vt"]>=30 and s["abs_dr1"]<=1 and s["all_diff"]

    # SPN-specific combos
    strategies["gap_spn>=40+r3>=5+sum>=15"] = lambda s: s["gap_spn"]>=40 and s["r3"]>=5 and s["sum"]>=15
    strategies["gap_spn>=40+r3>=5+all_diff"] = lambda s: s["gap_spn"]>=40 and s["r3"]>=5 and s["all_diff"]
    strategies["gap_spn>=50+r3>=5+sum>=15"] = lambda s: s["gap_spn"]>=50 and s["r3"]>=5 and s["sum"]>=15
    strategies["gap_spn>=50+r3>=5+r2>=5"] = lambda s: s["gap_spn"]>=50 and s["r3"]>=5 and s["r2"]>=5
    strategies["gap>=40+r3>=5+HMM"] = lambda s: s["gap_vt"]>=40 and s["r3"]>=5 and s["combo"]=="HMM"
    strategies["gap>=40+r3==8+sum>=15"] = lambda s: s["gap_vt"]>=40 and s["r3"]==8 and s["sum"]>=15

    # OR-based (bet if ANY of the top signals fire)
    def acc_or(s):
        if s["gap_acc"] < 30: return False
        return (s["combo"] in ("MHM","MML","HMM") or
                (not s["is_triple"] and s["reel_1"] == "steal") or
                (s["gap_acc"] >= 80 and s["r1"] in (3,7)))
    strategies["ACC_OR(combo+steal+pity80)"] = acc_or

    def spn_or(s):
        if s["gap_spn"] < 40: return False
        return (s["r3"] >= 5 or s["combo"] == "HMM" or s["sum"] >= 18)
    strategies["SPN_OR(r3>=5+HMM+sum18)"] = spn_or

    def all_or(s):
        if s["gap_vt"] < 30: return False
        return (s["r3"] >= 5 or s["all_diff"] or s["sum"] >= 15 or s["r2"] == 7)
    strategies["ALL_OR(r3+diff+sum+r2)@30"] = all_or

    # References
    strategies["BASELINE: Always_bet"] = lambda s: True
    strategies["REF: gap>=30"] = lambda s: s["gap_vt"] >= 30
    strategies["REF: gap>=40"] = lambda s: s["gap_vt"] >= 40

    log(f"\n  {'strategy':<36s}  {'bets':>5s}  {'hit':>4s}  {'miss':>4s}  "
        f"{'catch%':>7s}  {'prec%':>7s}  {'lift':>5s}  {'bets/hit':>8s}  {'saved%':>7s}  "
        f"{'p-val':>8s}")
    log(f"  {'-'*110}")

    results = []
    for name, fn in strategies.items():
        bets = caught = missed = 0
        for s in states[:-1]:
            if fn(s):
                bets += 1
                if s["nxt_target"]: caught += 1
            else:
                if s["nxt_target"]: missed += 1
        if bets == 0: continue

        catch_pct = caught / total_targets * 100
        prec = caught / bets * 100
        bph = bets / caught if caught > 0 else float("inf")
        saved = (1 - bets / (N-1)) * 100
        lift = prec / (baseline * 100) if baseline > 0 else 0
        pval = binomial_pvalue(caught, bets, baseline)

        results.append({
            "name": name, "bets": bets, "caught": caught, "missed": missed,
            "catch_pct": catch_pct, "prec": prec, "bph": bph,
            "saved": saved, "lift": lift, "pval": pval,
        })

    results.sort(key=lambda r: (-r["prec"] if r["caught"] > 0 else 0, -r["caught"]))
    for r in results:
        if r["caught"] == 0: continue
        sig = ""
        if r["pval"] < 0.01: sig = " ***"
        elif r["pval"] < 0.05: sig = " **"
        elif r["pval"] < 0.10: sig = " *"
        log(f"  {r['name']:<36s}  {r['bets']:>5d}  {r['caught']:>4d}  {r['missed']:>4d}  "
            f"{r['catch_pct']:>6.1f}%  {r['prec']:>6.2f}%  {r['lift']:>4.1f}x  "
            f"{r['bph']:>8.1f}  {r['saved']:>6.1f}%  "
            f"{r['pval']:>8.4f}{sig}")


def main():
    log("#" * 90)
    log("  STRATEGY SIMULATION WITH CONFIDENCE (1107 spins with idx)")
    log("  Combined strategies + p-values to check statistical reliability")
    log("#" * 90)

    trace_data = load_corrected_trace()
    run_combo_strategies(trace_data, "ALL VTs", lambda d: d["is_vt"])
    run_combo_strategies(trace_data, "ACC VTs ONLY", lambda d: d["vt_type"] == "ACC")
    run_combo_strategies(trace_data, "SPN VTs ONLY", lambda d: d["vt_type"] == "SPN")

    log(f"\n{'='*90}")
    log("  DONE")
    log(f"{'='*90}")


if __name__ == "__main__":
    main()
