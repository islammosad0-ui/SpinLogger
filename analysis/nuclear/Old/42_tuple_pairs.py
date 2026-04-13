"""
H3: ordered tuple-pair precursors

For every ordered pair (A, B) of tuples appearing back-to-back in the stream,
measure:
  - how often it appears in the 10 spins before a target triple (ACC/SPN)
  - how often it appears in baseline windows (reference point not a target triple)
  - lift = pre_rate / ctl_rate

Filter by minimum support (>=10 pre occurrences) to avoid noise.
Sort by lift, show top 20.

Then cross-validate: for each account's top pairs, show how those same pairs
perform on the OTHER two accounts. Pairs that replicate across accounts are
the only ones worth building on.

Also run a forward predictive check: given pair (A,B) at spins i-1, i, what
is P(target triple within next 10 spins) vs baseline?
"""
import csv
import os
from collections import Counter, defaultdict


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


def pair_lift_analysis(stream, target, label, win=10, min_support=10):
    """Return dict {pair: (pre_n, pre_rate, ctl_rate, lift)}."""
    idxs = find_triple_indices(stream, target)
    valid = [i for i in idxs if i >= win]
    triple_set = set(idxs)

    pre_pairs = Counter()
    pre_pair_slots = 0  # number of (i, i+1) slots in pre windows
    for i in valid:
        window = stream[i - win : i]
        for j in range(len(window) - 1):
            pre_pairs[(window[j]["tuple"], window[j + 1]["tuple"])] += 1
        pre_pair_slots += len(window) - 1

    ctl_pairs = Counter()
    ctl_pair_slots = 0
    for i in range(win, len(stream) - win):
        if i in triple_set:
            continue
        window = stream[i - win : i]
        for j in range(len(window) - 1):
            ctl_pairs[(window[j]["tuple"], window[j + 1]["tuple"])] += 1
        ctl_pair_slots += len(window) - 1

    results = {}
    for pair, pre_n in pre_pairs.items():
        if pre_n < min_support:
            continue
        pre_rate = pre_n / pre_pair_slots
        ctl_n = ctl_pairs.get(pair, 0)
        ctl_rate = ctl_n / ctl_pair_slots if ctl_pair_slots else 0
        lift = pre_rate / ctl_rate if ctl_rate > 0 else float("inf")
        results[pair] = (pre_n, pre_rate, ctl_rate, lift, ctl_n)

    return results, len(valid), pre_pair_slots, ctl_pair_slots


def forward_check(stream, pair, target, win=10):
    """Given pair (A,B) back-to-back, what's P(target within next `win` spins)?"""
    A, B = pair
    signal_points = []
    for i in range(1, len(stream)):
        if stream[i - 1]["tuple"] == A and stream[i]["tuple"] == B:
            signal_points.append(i)

    hits = 0
    for pt in signal_points:
        for j in range(pt + 1, min(pt + 1 + win, len(stream))):
            if classify_triple(stream[j]) == target:
                hits += 1
                break

    # Baseline: P(target within next `win` from any random point)
    base_hits = 0
    base_total = 0
    for i in range(len(stream) - win):
        for j in range(i + 1, i + 1 + win):
            if classify_triple(stream[j]) == target:
                base_hits += 1
                break
        base_total += 1

    p_sig = hits / len(signal_points) if signal_points else 0
    p_base = base_hits / base_total if base_total else 0
    lift = p_sig / p_base if p_base > 0 else float("nan")
    return len(signal_points), hits, p_sig, p_base, lift


def short_pair(pair):
    a, b = pair

    def s(t):
        return f"({t[0][:3]},{t[1][:3]},{t[2][:3]})"

    return f"{s(a)}->{s(b)}"


def main():
    # Load all three streams once
    streams = {}
    for acc in ["Islam", "Ahmed", "Nick"]:
        header, rows = load_account(acc)
        streams[acc] = build_stream(header, rows)
        print(f"{acc}: {len(streams[acc])} spins")

    for target in ["ACC", "SPN"]:
        print(f"\n\n{'=' * 90}\nTARGET: {target}\n{'=' * 90}")

        per_acc_results = {}
        for acc in ["Islam", "Ahmed", "Nick"]:
            results, n_tr, pre_slots, ctl_slots = pair_lift_analysis(
                streams[acc], target, acc, win=10, min_support=8
            )
            per_acc_results[acc] = results
            print(
                f"\n[{acc}] {n_tr} {target} triples, {pre_slots} pre-pair-slots, "
                f"{ctl_slots} ctl-pair-slots, {len(results)} pairs with >=8 support"
            )

            top = sorted(results.items(), key=lambda x: -x[1][3])[:15]
            print(f"  {'pair':<50} {'pre_n':>5} {'pre_rt':>8} {'ctl_rt':>8} {'lift':>6}")
            for pair, (pre_n, pre_r, ctl_r, lift, ctl_n) in top:
                print(
                    f"  {short_pair(pair):<50} {pre_n:>5} {pre_r:>7.3%} "
                    f"{ctl_r:>7.3%} {lift:>5.2f}x"
                )

        # Cross-account replication: take Islam's top 20 pairs, see how they do on Ahmed/Nick
        print(f"\n--- CROSS-ACCOUNT REPLICATION for {target} ---")
        islam_top = sorted(
            per_acc_results["Islam"].items(), key=lambda x: -x[1][3]
        )[:20]
        print(f"  {'pair':<50}  {'Islam':>12}  {'Ahmed':>12}  {'Nick':>12}")
        for pair, (pre_n, pre_r, ctl_r, lift, ctl_n) in islam_top:
            a_lift = per_acc_results["Ahmed"].get(pair)
            n_lift = per_acc_results["Nick"].get(pair)
            a_str = (
                f"{a_lift[3]:.2f}x(n={a_lift[0]})" if a_lift else "below_supp"
            )
            n_str = (
                f"{n_lift[3]:.2f}x(n={n_lift[0]})" if n_lift else "below_supp"
            )
            print(
                f"  {short_pair(pair):<50}  {lift:>5.2f}x(n={pre_n:<3})  "
                f"{a_str:>12}  {n_str:>12}"
            )

        # Find pairs that have lift > 1.3 on ALL three accounts (even if below support on some)
        print(f"\n--- PAIRS ABOVE BASELINE ON ALL 3 ACCOUNTS (lift > 1.3, n >= 5) ---")
        # Redo with lower support for cross-check
        relaxed = {}
        for acc in ["Islam", "Ahmed", "Nick"]:
            relaxed[acc], *_ = pair_lift_analysis(
                streams[acc], target, acc, win=10, min_support=5
            )
        common = (
            set(relaxed["Islam"].keys())
            & set(relaxed["Ahmed"].keys())
            & set(relaxed["Nick"].keys())
        )
        robust = []
        for pair in common:
            li = relaxed["Islam"][pair][3]
            la = relaxed["Ahmed"][pair][3]
            ln = relaxed["Nick"][pair][3]
            if li > 1.3 and la > 1.3 and ln > 1.3:
                avg = (li + la + ln) / 3
                robust.append((pair, li, la, ln, avg))
        robust.sort(key=lambda x: -x[4])
        if robust:
            print(f"  {'pair':<50} {'Islam':>8} {'Ahmed':>8} {'Nick':>8} {'avg':>8}")
            for pair, li, la, ln, avg in robust[:20]:
                print(
                    f"  {short_pair(pair):<50} {li:>7.2f}x {la:>7.2f}x "
                    f"{ln:>7.2f}x {avg:>7.2f}x"
                )
            print(f"\n  Found {len(robust)} pairs with lift>1.3 on all 3 accounts.")

            # Forward check on top replicated pair
            print(f"\n--- FORWARD CHECK on top replicated pair ---")
            top_pair = robust[0][0]
            for acc in ["Islam", "Ahmed", "Nick"]:
                n_sig, hits, ps, pb, lf = forward_check(
                    streams[acc], top_pair, target, win=10
                )
                print(
                    f"  [{acc}] {short_pair(top_pair)}: {n_sig} fires, "
                    f"{hits} hits within 10 -> {ps:.1%} vs base {pb:.1%} lift={lf:.2f}x"
                )
        else:
            print("  NONE. No pair has lift > 1.3 on all three accounts.")


if __name__ == "__main__":
    main()
