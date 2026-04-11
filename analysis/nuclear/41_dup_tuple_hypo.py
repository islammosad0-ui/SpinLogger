"""
Test two hypotheses about duplicate tuples predicting ACC/SPN triples.

HYPOTHESIS 1: specific single tuples as precursors
  For each tuple in the deck, compare its rate in the 10 spins before a triple
  vs its rate in all other 10-spin windows. Report tuples with highest lift.

HYPOTHESIS 2: back-to-back duplicate of a RARE tuple
  Split deck into rare (bottom 20% by global frequency) and common. Check whether
  pre-triple windows contain adj-dup of rare tuples at a different rate than
  baseline, and whether seeing a rare dup predicts a triple in the next 10 spins.

Runs on all three accounts independently, for both ACC and SPN targets.
"""
import csv
import os
from collections import Counter


def load_account(acc):
    acc_dir = f"data/{acc}"
    rows_by_seq = {}
    header = None
    for f in sorted(os.listdir(acc_dir)):
        if "spin_history" not in f:
            continue
        with open(os.path.join(acc_dir, f), "r", encoding="utf-8") as fh:
            r = csv.reader(fh)
            h = next(r)
            if header is None:
                header = h
            col = {c: i for i, c in enumerate(h)}
            for row in r:
                if not row or not row[col["seq"]]:
                    continue
                try:
                    seq = int(row[col["seq"]])
                except ValueError:
                    continue
                rows_by_seq[seq] = row
    seqs = sorted(rows_by_seq.keys())
    return header, [rows_by_seq[s] for s in seqs]


def build_stream(header, rows):
    col = {c: i for i, c in enumerate(header)}
    stream = []
    for row in rows:
        try:
            seq = int(row[col["seq"]])
        except ValueError:
            continue
        tup = (row[col["reel_1"]], row[col["reel_2"]], row[col["reel_3"]])
        is_trip = row[col["is_triple"]].strip().lower() in ("true", "1", "yes")
        stream.append({"seq": seq, "tuple": tup, "is_triple": is_trip})
    return stream


def classify_triple(row):
    if not row["is_triple"]:
        return None
    r1, r2, r3 = row["tuple"]
    if r1 != r2 or r2 != r3:
        return None
    sym = r1.lower()
    if "accum" in sym:
        return "ACC"
    if "spin" in sym:
        return "SPN"
    if "attack" in sym:
        return "ATK"
    if "steal" in sym:
        return "STL"
    if "shield" in sym:
        return "SHD"
    return None


def find_triple_indices(stream, target):
    return [i for i, r in enumerate(stream) if classify_triple(r) == target]


def hypothesis_1(stream, target, label, win=10):
    idxs = find_triple_indices(stream, target)
    valid = [i for i in idxs if i >= win]

    pre_spins = 0
    pre_counts = Counter()
    for i in valid:
        window = stream[i - win : i]
        pre_spins += len(window)
        for r in window:
            pre_counts[r["tuple"]] += 1

    triple_set = set(idxs)
    ctl_spins = 0
    ctl_counts = Counter()
    for i in range(win, len(stream) - win):
        if i in triple_set:
            continue
        window = stream[i - win : i]
        ctl_spins += len(window)
        for r in window:
            ctl_counts[r["tuple"]] += 1

    print(f"\n--- {label} ({target}) H1: specific-tuple precursor ---")
    print(f"Pre-windows: {len(valid)} | pre spins: {pre_spins} | ctl spins: {ctl_spins}")

    results = []
    for tup in set(pre_counts) | set(ctl_counts):
        pre_rate = pre_counts[tup] / pre_spins if pre_spins else 0
        ctl_rate = ctl_counts[tup] / ctl_spins if ctl_spins else 0
        if pre_counts[tup] < 5:
            continue
        lift = pre_rate / ctl_rate if ctl_rate > 0 else float("inf")
        results.append((tup, pre_counts[tup], pre_rate, ctl_rate, lift))

    results.sort(key=lambda x: -x[4])
    head = f'{"tuple":<45} {"pre_n":>6} {"pre_rt":>8} {"ctl_rt":>8} {"lift":>6}'
    print(head)
    for tup, n, pr, cr, lift in results[:10]:
        tstr = f"({tup[0][:5]},{tup[1][:5]},{tup[2][:5]})"
        print(f"  {tstr:<43} {n:>6} {pr:>7.3%} {cr:>7.3%} {lift:>5.2f}x")
    print("  --- bottom 5 (under-represented) ---")
    for tup, n, pr, cr, lift in results[-5:]:
        tstr = f"({tup[0][:5]},{tup[1][:5]},{tup[2][:5]})"
        print(f"  {tstr:<43} {n:>6} {pr:>7.3%} {cr:>7.3%} {lift:>5.2f}x")


def hypothesis_2(stream, target, label, win=10, rare_pctile=20):
    all_counts = Counter(r["tuple"] for r in stream)
    total = sum(all_counts.values())

    sorted_tups = sorted(all_counts.items(), key=lambda x: x[1])
    rare_cutoff = max(1, int(len(sorted_tups) * rare_pctile / 100))
    rare_set = {t for t, _ in sorted_tups[:rare_cutoff]}

    rare_total = sum(c for t, c in all_counts.items() if t in rare_set)
    print(f"\n--- {label} ({target}) H2: rare-tuple adj-dup precursor ---")
    print(
        f"Deck size: {len(sorted_tups)} | rare(bot{rare_pctile}%): "
        f"{len(rare_set)} tuples, {rare_total}/{total}={rare_total/total:.1%} of spins"
    )

    idxs = find_triple_indices(stream, target)
    valid = [i for i in idxs if i >= win]
    triple_set = set(idxs)

    def window_flags(window):
        adj_rare = False
        adj_common = False
        for i in range(len(window) - 1):
            if window[i]["tuple"] == window[i + 1]["tuple"]:
                if window[i]["tuple"] in rare_set:
                    adj_rare = True
                else:
                    adj_common = True
        return adj_rare, adj_common

    pre_rare = pre_common = 0
    for i in valid:
        ar, ac = window_flags(stream[i - win : i])
        pre_rare += ar
        pre_common += ac

    ctl_rare = ctl_common = ctl_total = 0
    for i in range(win, len(stream) - win):
        if i in triple_set:
            continue
        ar, ac = window_flags(stream[i - win : i])
        ctl_rare += ar
        ctl_common += ac
        ctl_total += 1

    def fmt(pre_n, n_pre, ctl_n, n_ctl, lab):
        p = pre_n / n_pre if n_pre else 0
        c = ctl_n / n_ctl if n_ctl else 0
        lift = p / c if c > 0 else float("nan")
        print(
            f"  {lab:<20} pre={p:6.1%} ({pre_n}/{n_pre})   "
            f"ctl={c:6.1%} ({ctl_n}/{n_ctl})   lift={lift:.2f}x"
        )

    fmt(pre_rare, len(valid), ctl_rare, ctl_total, "adj-dup RARE:")
    fmt(pre_common, len(valid), ctl_common, ctl_total, "adj-dup COMMON:")

    # Forward predictive check
    rare_dup_points = []
    for i in range(1, len(stream)):
        if (
            stream[i]["tuple"] == stream[i - 1]["tuple"]
            and stream[i]["tuple"] in rare_set
        ):
            rare_dup_points.append(i)

    def hit_within(start, w):
        for j in range(start + 1, min(start + 1 + w, len(stream))):
            if classify_triple(stream[j]) == target:
                return True
        return False

    hits = sum(1 for i in rare_dup_points if hit_within(i, win))
    base_hits = 0
    base_total = 0
    for i in range(len(stream) - win):
        if hit_within(i, win):
            base_hits += 1
        base_total += 1

    p_signal = hits / len(rare_dup_points) if rare_dup_points else 0
    p_base = base_hits / base_total if base_total else 0
    lift = p_signal / p_base if p_base > 0 else float("nan")
    print(
        f"  FORWARD rare-dup -> {target} within {win}: "
        f"{hits}/{len(rare_dup_points)}={p_signal:.1%}  "
        f"vs baseline {p_base:.1%}  lift={lift:.2f}x"
    )


if __name__ == "__main__":
    for acc in ["Islam", "Ahmed", "Nick"]:
        print(f'\n{"=" * 70}\n{acc}\n{"=" * 70}')
        header, rows = load_account(acc)
        stream = build_stream(header, rows)
        print(f"Total deduped spins: {len(stream)}")

        for target in ["ACC", "SPN"]:
            hypothesis_1(stream, target, acc, win=10)
            hypothesis_2(stream, target, acc, win=10, rare_pctile=20)
