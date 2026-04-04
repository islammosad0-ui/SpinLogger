#!/usr/bin/env python3
"""
Coin Master Spin Analyzer -- detect reel strip cycles, accumulation patterns,
triple clustering, and predictive signals from spin_history.csv data.

Usage:
    python spin_analyzer.py <csv_file>
    python spin_analyzer.py spin_history.csv
    python spin_analyzer.py --har sample.har    # parse HAR file first
"""

import sys
import os
import csv
import json
import gzip
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from itertools import groupby
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
#  Reel value mappings (from HAR analysis)
# ---------------------------------------------------------------------------
REEL_SYMBOLS = {
    1: "coin", 2: "goldSack", 3: "attack", 4: "steal",
    5: "shield", 6: "spins", 30: "accumulation"
}
REWARD_NAMES = {
    1: "gold", 2: "attack", 3: "shield", 4: "steal",
    5: "spins", 10: "accumulation"
}


# ---------------------------------------------------------------------------
#  Data loading
# ---------------------------------------------------------------------------
def load_csv(path):
    """Load spin data from CSV (exported by SpinLogger tweak)."""
    spins = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            spin = {}
            spin["seq"] = int(row.get("seq") or row.get("spin_number") or 0)
            spin["r1"] = int(row.get("r1", 0))
            spin["r2"] = int(row.get("r2", 0))
            spin["r3"] = int(row.get("r3", 0))
            spin["reel1"] = row.get("reel_1", REEL_SYMBOLS.get(spin["r1"], "?"))
            spin["reel2"] = row.get("reel_2", REEL_SYMBOLS.get(spin["r2"], "?"))
            spin["reel3"] = row.get("reel_3", REEL_SYMBOLS.get(spin["r3"], "?"))
            spin["result"] = row.get("spin_result", "")
            spin["reward_code"] = int(row.get("reward_code", 0))
            spin["pay"] = int(row.get("coins_won", 0))
            spin["coins"] = row.get("coins", "")
            spin["spins_left"] = row.get("spins_remaining", "")
            spin["shields"] = int(row.get("shields", 0))
            spin["max_shields"] = int(row.get("max_shields", 0))
            spin["bet_level"] = int(row.get("bet_level", 0))
            spin["accum_current"] = int(row.get("accum_current", 0))
            spin["accum_total"] = int(row.get("accum_total", 0))
            spin["accum_mission"] = int(row.get("accum_mission", 0))
            spin["slot2_r1"] = row.get("slot2_r1", "")
            spin["slot2_r2"] = row.get("slot2_r2", "")
            spin["slot2_r3"] = row.get("slot2_r3", "")
            spin["event_bars"] = row.get("event_bars", "")
            spin["is_triple"] = (row.get("is_triple", "").lower() == "true" or
                                 (spin["r1"] == spin["r2"] == spin["r3"] and spin["r1"] > 0))
            spin["timestamp"] = row.get("timestamp", "")
            spins.append(spin)
    return spins


def load_har(path):
    """Extract spin data from HAR file (network capture)."""
    with open(path, encoding="utf-8") as f:
        har = json.load(f)

    spins = []
    for entry in har.get("log", {}).get("entries", []):
        url = entry.get("request", {}).get("url", "")
        parsed = urlparse(url)
        if not parsed.path.endswith("/spin") or "/users/" not in parsed.path:
            continue

        resp = entry.get("response", {})
        content = resp.get("content", {})
        text = content.get("text", "")
        if not text:
            continue

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue

        if "r1" not in data:
            continue

        spin = {
            "seq": data.get("seq", 0),
            "r1": data["r1"], "r2": data["r2"], "r3": data["r3"],
            "reel1": REEL_SYMBOLS.get(data["r1"], "?"),
            "reel2": REEL_SYMBOLS.get(data["r2"], "?"),
            "reel3": REEL_SYMBOLS.get(data["r3"], "?"),
            "reward_code": data.get("reward", 0),
            "pay": data.get("pay", 0),
            "coins": str(data.get("coins", "")),
            "spins_left": str(data.get("spins", "")),
            "shields": data.get("shields", 0),
            "max_shields": data.get("maxShields", 0),
            "bet_level": 0,
            "accum_current": 0, "accum_total": 0, "accum_mission": 0,
            "slot2_r1": "", "slot2_r2": "", "slot2_r3": "",
            "event_bars": "",
        }

        # Bet state
        sb = data.get("superBet", {})
        if isinstance(sb, dict):
            spin["bet_level"] = sb.get("betLevel", 0)

        # Main GAE accumulation
        accum = data.get("accumulation", {})
        if isinstance(accum, dict):
            spin["accum_current"] = accum.get("currentAmount", 0)
            spin["accum_total"] = accum.get("totalAmount", 0)
            spin["accum_mission"] = accum.get("missionIndex", 0)

        # Second slot reels
        addslots = data.get("additionalSlots", {})
        if isinstance(addslots, dict):
            ss = addslots.get("second_slot", {})
            if isinstance(ss, dict):
                reels = ss.get("reels", [])
                if len(reels) >= 3:
                    spin["slot2_r1"] = str(reels[0])
                    spin["slot2_r2"] = str(reels[1])
                    spin["slot2_r3"] = str(reels[2])

        # Event bars snapshot
        bars = data.get("accumulationBarsById", {})
        if isinstance(bars, dict) and bars:
            bar_snap = {}
            for bid, bar in bars.items():
                if isinstance(bar, dict):
                    short = bid[:8] if len(bid) > 8 else bid
                    bar_snap[short] = f"{bar.get('currentAmount',0)}/{bar.get('totalAmount',0)}"
            spin["event_bars"] = json.dumps(bar_snap)

        spin["is_triple"] = (spin["r1"] == spin["r2"] == spin["r3"])
        spin["result"] = REWARD_NAMES.get(spin["reward_code"], "?")
        spins.append(spin)

    spins.sort(key=lambda s: s["seq"])
    return spins


# ---------------------------------------------------------------------------
#  Analysis functions
# ---------------------------------------------------------------------------

def basic_stats(spins):
    """Overall spin distribution."""
    print("\n" + "=" * 70)
    print(f"  BASIC STATS -- {len(spins)} spins analyzed")
    print("=" * 70)

    # Symbol frequency across all reels
    all_symbols = []
    for s in spins:
        all_symbols.extend([s["r1"], s["r2"], s["r3"]])

    counts = Counter(all_symbols)
    total = len(all_symbols)
    print(f"\n  Symbol frequency (all {total} reel positions):")
    for val, name in sorted(REEL_SYMBOLS.items()):
        c = counts.get(val, 0)
        pct = c / total * 100 if total else 0
        bar = "#" * int(pct)
        print(f"    {name:15s} (r={val:2d}): {c:5d}  ({pct:5.1f}%)  {bar}")

    # Triple frequency
    triples = [s for s in spins if s["is_triple"]]
    print(f"\n  Triples: {len(triples)}/{len(spins)} ({len(triples)/len(spins)*100:.1f}%)")

    triple_types = Counter(s["r1"] for s in triples)
    for val, name in sorted(REEL_SYMBOLS.items()):
        c = triple_types.get(val, 0)
        if c > 0:
            print(f"    3x {name:15s}: {c:4d}  ({c/len(spins)*100:.2f}% of all spins)")

    # Result distribution
    results = Counter(s["result"] for s in spins)
    print(f"\n  Outcome distribution:")
    for result, count in results.most_common():
        print(f"    {result:15s}: {count:5d}  ({count/len(spins)*100:.1f}%)")


def triple_clustering(spins):
    """Analyze spacing between triples to detect hot/cold zones."""
    print("\n" + "=" * 70)
    print("  TRIPLE CLUSTERING ANALYSIS")
    print("=" * 70)

    triple_indices = [i for i, s in enumerate(spins) if s["is_triple"]]
    if len(triple_indices) < 2:
        print("  Not enough triples for clustering analysis.")
        return

    # Gaps between consecutive triples
    gaps = [triple_indices[i+1] - triple_indices[i] for i in range(len(triple_indices)-1)]

    print(f"\n  Triple positions: {len(triple_indices)} triples in {len(spins)} spins")
    print(f"  Gap stats (spins between consecutive triples):")
    print(f"    Min:    {min(gaps)}")
    print(f"    Max:    {max(gaps)}")
    print(f"    Mean:   {sum(gaps)/len(gaps):.1f}")
    print(f"    Median: {sorted(gaps)[len(gaps)//2]}")

    # Gap distribution
    gap_counts = Counter(gaps)
    print(f"\n  Gap distribution:")
    for g in sorted(gap_counts):
        c = gap_counts[g]
        bar = "#" * c
        print(f"    gap={g:3d}: {c:3d} times  {bar}")

    # Back-to-back triples
    b2b = sum(1 for g in gaps if g == 1)
    print(f"\n  Back-to-back triples: {b2b} ({b2b/len(gaps)*100:.1f}% of transitions)")

    # Streak analysis
    print(f"\n  Triple streaks (consecutive triples):")
    streak = 0
    streaks = []
    for i, s in enumerate(spins):
        if s["is_triple"]:
            streak += 1
        else:
            if streak > 0:
                streaks.append((i - streak, streak))
            streak = 0
    if streak > 0:
        streaks.append((len(spins) - streak, streak))

    for start, length in sorted(streaks, key=lambda x: -x[1])[:10]:
        syms = " -> ".join(
            f"3x{REEL_SYMBOLS.get(spins[start+j]['r1'], '?')}"
            for j in range(length)
        )
        print(f"    Streak of {length} starting at spin #{start}: {syms}")


def accumulation_analysis(spins):
    """Track accumulation bar progress and find patterns."""
    print("\n" + "=" * 70)
    print("  ACCUMULATION BAR ANALYSIS")
    print("=" * 70)

    # Filter spins that have accumulation data
    accum_spins = [s for s in spins if s["accum_total"] > 0]
    if not accum_spins:
        print("  No accumulation data found in spins.")
        return

    print(f"\n  Spins with accumulation data: {len(accum_spins)}")
    print(f"  Accumulation target: {accum_spins[0]['accum_total']}")
    print(f"  Mission index: {accum_spins[0]['accum_mission']}")

    # Track deltas -- how much the bar moved per spin
    deltas = []
    for i in range(1, len(accum_spins)):
        prev = accum_spins[i-1]["accum_current"]
        curr = accum_spins[i]["accum_current"]
        delta = curr - prev
        if delta < 0:
            # Bar reset (reward collected)
            delta = 0
        deltas.append({
            "spin": accum_spins[i],
            "delta": delta,
            "prev": prev,
            "curr": curr
        })

    # How many accum symbols per spin contribute
    print(f"\n  Accumulation deltas per spin:")
    delta_counts = Counter(d["delta"] for d in deltas)
    for d in sorted(delta_counts):
        c = delta_counts[d]
        print(f"    +{d:3d}: {c:4d} times")

    # Find spins where accumulation jumped by 10+ (triple accum!)
    big_jumps = [d for d in deltas if d["delta"] >= 10]
    if big_jumps:
        print(f"\n  BIG JUMPS (accumulation += 10+, likely triple accum):")
        for bj in big_jumps:
            s = bj["spin"]
            print(f"    seq={s['seq']:6d}: r[{s['r1']},{s['r2']},{s['r3']}] "
                  f"accum {bj['prev']} -> {bj['curr']} (+{bj['delta']})")

    # Count how many r=30 (accumulation symbols) appear per spin
    accum_sym_per_spin = []
    for s in spins:
        count = sum(1 for r in [s["r1"], s["r2"], s["r3"]] if r == 30)
        if count > 0:
            accum_sym_per_spin.append((s, count))

    print(f"\n  Spins containing accumulation symbols (r=30):")
    accum_sym_counts = Counter(c for _, c in accum_sym_per_spin)
    for n in sorted(accum_sym_counts):
        c = accum_sym_counts[n]
        pct = c / len(spins) * 100
        print(f"    {n}x accum symbol: {c:4d} spins ({pct:.1f}%)")

    # Spacing between accum symbol appearances
    accum_indices = [i for i, s in enumerate(spins)
                     if any(r == 30 for r in [s["r1"], s["r2"], s["r3"]])]
    if len(accum_indices) > 1:
        accum_gaps = [accum_indices[i+1] - accum_indices[i]
                      for i in range(len(accum_indices)-1)]
        print(f"\n  Gap between accum symbol appearances:")
        print(f"    Min: {min(accum_gaps)}, Max: {max(accum_gaps)}, "
              f"Mean: {sum(accum_gaps)/len(accum_gaps):.1f}")

    # Triple accum spacing
    triple_accum_indices = [i for i, s in enumerate(spins)
                            if s["r1"] == 30 and s["r2"] == 30 and s["r3"] == 30]
    if len(triple_accum_indices) > 1:
        ta_gaps = [triple_accum_indices[i+1] - triple_accum_indices[i]
                   for i in range(len(triple_accum_indices)-1)]
        print(f"\n  Gap between TRIPLE accumulation (30,30,30):")
        print(f"    Min: {min(ta_gaps)}, Max: {max(ta_gaps)}, "
              f"Mean: {sum(ta_gaps)/len(ta_gaps):.1f}")
    elif len(triple_accum_indices) == 1:
        print(f"\n  Only 1 triple accumulation found at index {triple_accum_indices[0]}")
    else:
        print(f"\n  No triple accumulations (30,30,30) found.")


def spins_symbol_analysis(spins):
    """Specifically analyze the spins symbol (r=6) -- triple spins detection."""
    print("\n" + "=" * 70)
    print("  SPINS SYMBOL (r=6) ANALYSIS -- Triple Spins Focus")
    print("=" * 70)

    # Spins containing r=6
    spin6_spins = [(i, s) for i, s in enumerate(spins)
                   if any(r == 6 for r in [s["r1"], s["r2"], s["r3"]])]

    print(f"\n  Spins containing spins symbol (r=6): {len(spin6_spins)}/{len(spins)} "
          f"({len(spin6_spins)/len(spins)*100:.1f}%)")

    sym6_per_spin = Counter(
        sum(1 for r in [s["r1"], s["r2"], s["r3"]] if r == 6)
        for _, s in spin6_spins
    )
    for n in sorted(sym6_per_spin):
        c = sym6_per_spin[n]
        print(f"    {n}x spins symbol: {c:4d}")

    # Triple spins
    triple_spins = [(i, s) for i, s in enumerate(spins)
                    if s["r1"] == 6 and s["r2"] == 6 and s["r3"] == 6]
    print(f"\n  Triple spins (6,6,6): {len(triple_spins)}")
    for idx, s in triple_spins:
        print(f"    at index {idx}, seq={s['seq']}")

    if len(triple_spins) > 1:
        ts_gaps = [triple_spins[i+1][0] - triple_spins[i][0]
                   for i in range(len(triple_spins)-1)]
        print(f"    Gap between triple spins: min={min(ts_gaps)}, max={max(ts_gaps)}, "
              f"mean={sum(ts_gaps)/len(ts_gaps):.1f}")


def cycle_detection(spins):
    """Attempt to detect repeating cycles in the reel strip."""
    print("\n" + "=" * 70)
    print("  CYCLE / STRIP DETECTION")
    print("=" * 70)

    if len(spins) < 50:
        print("  Need at least 50 spins for cycle detection.")
        return

    # Build the reel sequence as a string for pattern matching
    r1_seq = [s["r1"] for s in spins]
    r2_seq = [s["r2"] for s in spins]
    r3_seq = [s["r3"] for s in spins]

    # Autocorrelation -- does the sequence repeat at some lag?
    print(f"\n  Autocorrelation analysis (r1 reel):")
    print(f"  Looking for periodic patterns in reel 1...")

    best_lags = []
    n = len(r1_seq)
    for lag in range(1, min(n // 2, 500)):
        matches = sum(1 for i in range(n - lag) if r1_seq[i] == r1_seq[i + lag])
        corr = matches / (n - lag)
        if corr > 0.3:  # Higher than random chance (~14% for 7 symbols)
            best_lags.append((lag, corr))

    if best_lags:
        best_lags.sort(key=lambda x: -x[1])
        print(f"  Top correlating lags (random baseline ~14%):")
        for lag, corr in best_lags[:15]:
            bar = "#" * int(corr * 50)
            print(f"    lag={lag:4d}: {corr:.3f} {bar}")
    else:
        print("  No significant autocorrelation found (sequence appears random at each lag).")

    # Transition matrix -- what follows what?
    print(f"\n  Transition matrix (r1 -> next r1):")
    transitions = defaultdict(Counter)
    for i in range(len(r1_seq) - 1):
        transitions[r1_seq[i]][r1_seq[i+1]] += 1

    header = "  From\\To  " + " ".join(f"{REEL_SYMBOLS.get(v, '?'):>7s}" for v in sorted(REEL_SYMBOLS))
    print(header)
    for from_val in sorted(REEL_SYMBOLS):
        row_total = sum(transitions[from_val].values())
        if row_total == 0:
            continue
        cells = []
        for to_val in sorted(REEL_SYMBOLS):
            count = transitions[from_val][to_val]
            pct = count / row_total * 100 if row_total else 0
            cells.append(f"{pct:6.1f}%")
        print(f"  {REEL_SYMBOLS[from_val]:>9s}  " + " ".join(cells))

    # Check if any transitions are significantly non-uniform
    print(f"\n  Looking for non-random transitions...")
    n_symbols = len(REEL_SYMBOLS)
    significant = []
    for from_val, to_counts in transitions.items():
        total = sum(to_counts.values())
        if total < 10:
            continue
        for to_val, count in to_counts.items():
            expected = total / n_symbols
            if count > expected * 2:
                significant.append((from_val, to_val, count/total, count, total))

    if significant:
        significant.sort(key=lambda x: -x[2])
        for fv, tv, pct, cnt, tot in significant[:10]:
            print(f"    {REEL_SYMBOLS.get(fv,'?')} -> {REEL_SYMBOLS.get(tv,'?')}: "
                  f"{pct:.1%} ({cnt}/{tot}) -- {pct/((1/n_symbols)):.1f}x expected")
    else:
        print("  No significantly biased transitions detected.")


def hot_cold_windows(spins, window=20):
    """Sliding window analysis to find hot/cold zones."""
    print("\n" + "=" * 70)
    print(f"  HOT/COLD ZONE ANALYSIS (window={window} spins)")
    print("=" * 70)

    if len(spins) < window * 2:
        print("  Not enough spins for window analysis.")
        return

    # Count triples per window
    windows = []
    for i in range(len(spins) - window + 1):
        w = spins[i:i+window]
        triples = sum(1 for s in w if s["is_triple"])
        accums = sum(1 for s in w if any(r == 30 for r in [s["r1"], s["r2"], s["r3"]]))
        windows.append({
            "start_idx": i,
            "start_seq": w[0]["seq"],
            "end_seq": w[-1]["seq"],
            "triples": triples,
            "triple_rate": triples / window,
            "accum_symbols": accums,
        })

    # Hottest windows
    by_triples = sorted(windows, key=lambda w: -w["triple_rate"])
    print(f"\n  HOTTEST windows (most triples per {window} spins):")
    for w in by_triples[:5]:
        print(f"    seq {w['start_seq']:6d}-{w['end_seq']:6d}: "
              f"{w['triples']:2d} triples ({w['triple_rate']:.0%}), "
              f"{w['accum_symbols']} accum symbols")

    # Coldest windows
    print(f"\n  COLDEST windows (fewest triples per {window} spins):")
    for w in by_triples[-5:]:
        print(f"    seq {w['start_seq']:6d}-{w['end_seq']:6d}: "
              f"{w['triples']:2d} triples ({w['triple_rate']:.0%}), "
              f"{w['accum_symbols']} accum symbols")

    # Overall triple rate variation
    rates = [w["triple_rate"] for w in windows]
    mean_rate = sum(rates) / len(rates)
    variance = sum((r - mean_rate)**2 for r in rates) / len(rates)
    print(f"\n  Triple rate stats across windows:")
    print(f"    Mean: {mean_rate:.1%}")
    print(f"    StdDev: {variance**0.5:.1%}")
    print(f"    Min: {min(rates):.0%}, Max: {max(rates):.0%}")

    if variance**0.5 > mean_rate * 0.5:
        print(f"  -> HIGH VARIANCE -- suggests hot/cold zones exist, not uniform randomness")
    else:
        print(f"  -> Moderate variance -- consistent with near-random distribution")


def attack_steal_analysis(spins):
    """Track attacks (r=3) and steals (r=4) -- frequency, gaps, shield correlation."""
    print("\n" + "=" * 70)
    print("  ATTACK & STEAL ANALYSIS")
    print("=" * 70)

    for sym_val, sym_name in [(3, "ATTACK"), (4, "STEAL")]:
        triple_idx = [i for i, s in enumerate(spins)
                      if s["r1"] == sym_val and s["r2"] == sym_val and s["r3"] == sym_val]
        single_idx = [i for i, s in enumerate(spins)
                      if any(r == sym_val for r in [s["r1"], s["r2"], s["r3"]])]

        print(f"\n  --- {sym_name} (r={sym_val}) ---")
        print(f"  Spins with 1+ {sym_name.lower()} symbol: {len(single_idx)}/{len(spins)} "
              f"({len(single_idx)/len(spins)*100:.1f}%)")
        print(f"  Triple {sym_name.lower()}: {len(triple_idx)} "
              f"({len(triple_idx)/len(spins)*100:.2f}%)")

        if len(triple_idx) > 1:
            gaps = [triple_idx[i+1] - triple_idx[i] for i in range(len(triple_idx)-1)]
            print(f"  Gap between 3x {sym_name.lower()}: "
                  f"min={min(gaps)}, max={max(gaps)}, mean={sum(gaps)/len(gaps):.1f}")

        # Shield state when attack/steal triple lands
        if triple_idx:
            shield_vals = [spins[i]["shields"] for i in triple_idx]
            print(f"  Shield count when 3x {sym_name.lower()} hit: {shield_vals}")


def shield_tracking(spins):
    """Track shield count changes -- gains/losses per spin."""
    print("\n" + "=" * 70)
    print("  SHIELD COUNT CHANGES")
    print("=" * 70)

    if len(spins) < 2:
        print("  Not enough spins.")
        return

    changes = []
    for i in range(1, len(spins)):
        prev = spins[i-1]["shields"]
        curr = spins[i]["shields"]
        delta = curr - prev
        if delta != 0:
            changes.append({
                "idx": i, "spin": spins[i],
                "prev": prev, "curr": curr, "delta": delta
            })

    print(f"\n  Shield changes: {len(changes)} out of {len(spins)-1} transitions")

    gains = [c for c in changes if c["delta"] > 0]
    losses = [c for c in changes if c["delta"] < 0]
    print(f"  Shield gains: {len(gains)}")
    print(f"  Shield losses: {len(losses)}")

    if gains:
        gain_deltas = Counter(c["delta"] for c in gains)
        print(f"\n  Shield gain amounts:")
        for d in sorted(gain_deltas):
            print(f"    +{d}: {gain_deltas[d]} times")
        # What reel result caused the gain?
        gain_results = Counter(
            f"r[{c['spin']['r1']},{c['spin']['r2']},{c['spin']['r3']}]"
            for c in gains
        )
        print(f"  Reels when shield gained (top 5):")
        for combo, cnt in gain_results.most_common(5):
            print(f"    {combo}: {cnt}x")

    if losses:
        loss_deltas = Counter(c["delta"] for c in losses)
        print(f"\n  Shield loss amounts:")
        for d in sorted(loss_deltas):
            print(f"    {d}: {loss_deltas[d]} times")
        loss_results = Counter(
            f"r[{c['spin']['r1']},{c['spin']['r2']},{c['spin']['r3']}] reward={c['spin']['reward_code']}"
            for c in losses
        )
        print(f"  Reels when shield lost (top 5):")
        for combo, cnt in loss_results.most_common(5):
            print(f"    {combo}: {cnt}x")

    # Shield state distribution
    shield_dist = Counter(s["shields"] for s in spins)
    print(f"\n  Shield count distribution:")
    for sh in sorted(shield_dist):
        c = shield_dist[sh]
        bar = "#" * (c * 40 // len(spins))
        print(f"    shields={sh}: {c:5d} spins ({c/len(spins)*100:.1f}%) {bar}")


def second_slot_analysis(spins):
    """Analyze slot-on-slot second reel patterns."""
    print("\n" + "=" * 70)
    print("  SECOND SLOT (SLOT-ON-SLOT) ANALYSIS")
    print("=" * 70)

    has_slot2 = [s for s in spins if any(s.get(f"slot2_r{i}", "") for i in [1,2,3])]
    if not has_slot2:
        print("  No second slot data found.")
        return

    # Count symbol appearances
    all_syms = []
    for s in spins:
        for i in [1,2,3]:
            v = s.get(f"slot2_r{i}", "")
            if v:
                all_syms.append(v)

    sym_counts = Counter(all_syms)
    total_positions = len(spins) * 3
    empty = total_positions - len(all_syms)

    print(f"\n  {len(spins)} spins, {total_positions} reel positions:")
    print(f"    empty: {empty} ({empty/total_positions*100:.1f}%)")
    for sym, cnt in sym_counts.most_common():
        print(f"    {sym}: {cnt} ({cnt/total_positions*100:.1f}%)")

    # Match counts per spin
    for sym_name in sym_counts:
        matches = []
        for s in spins:
            c = sum(1 for i in [1,2,3] if s.get(f"slot2_r{i}") == sym_name)
            if c > 0:
                matches.append(c)
        match_dist = Counter(matches)
        print(f"\n  {sym_name} per-spin matches:")
        for n in sorted(match_dist):
            print(f"    {n}x: {match_dist[n]} spins")

    # Triple matches on second slot
    triples_s2 = [(i, s) for i, s in enumerate(spins)
                  if s.get("slot2_r1") and s["slot2_r1"] == s.get("slot2_r2") == s.get("slot2_r3")]
    print(f"\n  Second slot triples (all 3 match): {len(triples_s2)}")
    for idx, s in triples_s2:
        print(f"    idx={idx} seq={s['seq']}: 3x {s['slot2_r1']}")


def bet_level_correlation(spins):
    """Check if bet level affects triple frequency."""
    print("\n" + "=" * 70)
    print("  BET LEVEL vs TRIPLE RATE CORRELATION")
    print("=" * 70)

    bet_spins = [s for s in spins if s.get("bet_level", 0) > 0]
    if not bet_spins:
        print("  No bet level data found.")
        return

    by_bet = defaultdict(list)
    for s in bet_spins:
        by_bet[s["bet_level"]].append(s)

    print(f"\n  Bet level | Spins | Triples | Rate")
    print(f"  ---------|-------|---------|-----")
    for bet in sorted(by_bet):
        group = by_bet[bet]
        trips = sum(1 for s in group if s["is_triple"])
        rate = trips / len(group) * 100 if group else 0
        print(f"  bet={bet:4d}   | {len(group):5d} | {trips:7d} | {rate:.1f}%")


def export_for_visualization(spins, output_path):
    """Export processed data as JSON for external visualization tools."""
    print(f"\n  Exporting {len(spins)} spins to {output_path}")
    with open(output_path, "w") as f:
        json.dump(spins, f, indent=2, default=str)
    print(f"  Done. Open in any JSON viewer or load into a spreadsheet.")


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Coin Master Spin Analyzer")
    parser.add_argument("input", help="CSV file from SpinLogger or HAR capture file")
    parser.add_argument("--har", action="store_true", help="Input is a HAR file")
    parser.add_argument("--window", type=int, default=20, help="Window size for hot/cold analysis")
    parser.add_argument("--export", help="Export processed spins as JSON to this path")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}")
        sys.exit(1)

    # Load data
    if args.har or args.input.endswith(".har"):
        print(f"Loading HAR file: {args.input}")
        spins = load_har(args.input)
    else:
        print(f"Loading CSV: {args.input}")
        spins = load_csv(args.input)

    if not spins:
        print("No spin data found!")
        sys.exit(1)

    print(f"Loaded {len(spins)} spins (seq {spins[0]['seq']} -> {spins[-1]['seq']})")

    # Run all analyses
    basic_stats(spins)
    triple_clustering(spins)
    accumulation_analysis(spins)
    spins_symbol_analysis(spins)
    attack_steal_analysis(spins)
    shield_tracking(spins)
    second_slot_analysis(spins)
    bet_level_correlation(spins)
    cycle_detection(spins)
    hot_cold_windows(spins, window=args.window)

    if args.export:
        export_for_visualization(spins, args.export)

    print("\n" + "=" * 70)
    print("  ANALYSIS COMPLETE")
    print("=" * 70)
    print("\n  To get better results, collect more spins!")
    print("  The more data, the clearer the patterns become.")
    print("  Aim for 500+ spins for cycle detection, 2000+ for strip mapping.\n")


if __name__ == "__main__":
    main()
