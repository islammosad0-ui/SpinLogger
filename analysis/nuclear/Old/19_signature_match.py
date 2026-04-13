"""
Chunk 19: Gap signature matching (user hypothesis).

User idea: If a gap of length 112 had a specific symbol pattern (acc count at
spin 50, shield count, rate trajectory, etc.), and a new gap shows the same
signature at its early spins, predict that the new gap will ALSO be ~112.

Method:
1. Compute a "signature" at fixed checkpoints (e.g., at sa_spins=50, 80, 100)
   for every completed gap. Signature = tuple of:
       (sa_acc, sa_shd, sa_atk, sa_stl, sa_spn)
   as normalized per-spin rates.
2. For each target gap, look at its live signature at each checkpoint.
3. Find historical gaps with similar signatures (cosine similarity or
   bucketed matching) and use their lengths to predict.
4. If many similar-signature historical gaps converge on a specific length,
   bet when sa_spins is near that length.

Test variants:
  A. Exact bucketed match (each rate in 5% buckets)
  B. Cosine similarity above threshold
  C. Rate-derivative match (how rates CHANGED in last 20 spins)
  D. Symbol-count match (not rates — raw counts at checkpoint)
  E. Per-account vs cross-account matching

A positive result: at spin 50 of gap N, lookup similar historical signatures,
find they all ended around spin 112, bet from spin 108 onwards.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location('e10', os.path.join(os.path.dirname(__file__), '10_ensemble.py'))
e10 = importlib.util.module_from_spec(spec); spec.loader.exec_module(e10)

import math
from collections import defaultdict

CHECKPOINTS = [30, 50, 70, 100]  # sa_spins values to snapshot signatures
BUCKET_WIDTH = 0.05  # rate buckets (0.00-0.05, 0.05-0.10, ...)


def compute_signature(spin):
    """Return tuple of rate buckets at this spin."""
    sp = spin['sa_spins']
    if sp == 0: return None
    def bucket(r): return int(r / BUCKET_WIDTH)
    return (
        bucket(spin['sa_acc'] / sp),
        bucket(spin['sa_shd'] / sp),
        bucket(spin['sa_atk'] / sp),
        bucket(spin['sa_stl'] / sp),
        bucket(spin['sa_spn'] / sp),
    )


def compute_symbol_signature(spin):
    """Symbol counts at this spin (not rates)."""
    return (
        spin['sa_acc'],
        spin['sa_shd'],
        spin['sa_atk'],
        spin['sa_stl'],
        spin['sa_spn'],
    )


def cosine_similarity(a, b):
    dot = sum(ai * bi for ai, bi in zip(a, b))
    na = math.sqrt(sum(ai * ai for ai in a))
    nb = math.sqrt(sum(bi * bi for bi in b))
    if na == 0 or nb == 0: return 0
    return dot / (na * nb)


def run():
    gaps = e10.all_gaps_with_prev()
    total_gaps = len(gaps)
    print(f"Loaded {total_gaps} ACC gaps")

    # --- Step 1: Build signature database from "historical" gaps ---
    # For each completed gap and each checkpoint, record (signature, gap_length).
    # For the prediction test, only gaps that came BEFORE the current gap are "historical".

    # Precompute per-gap snapshots
    # checkpoint_snapshots[gap_idx][cp] = (bucket_sig, symbol_sig, spin_idx_in_traj, sa_spins_at_that_spin)
    snapshots = {}
    for gi, gap in enumerate(gaps):
        traj = gap['trajectory']
        snap = {}
        for cp in CHECKPOINTS:
            # Find the trajectory index where sa_spins first reaches cp
            found_idx = None
            for i, spin in enumerate(traj):
                if spin['sa_spins'] >= cp:
                    found_idx = i
                    break
            if found_idx is None: continue
            spin = traj[found_idx]
            sig = compute_signature(spin)
            sym = compute_symbol_signature(spin)
            snap[cp] = {'idx': found_idx, 'sa_spins': spin['sa_spins'],
                        'sig': sig, 'sym': sym, 'gap_length': gap['length']}
        snapshots[gi] = snap

    # --- Step 2: Per-account causal matching test ---
    # For each gap, look up historical gaps (SAME account, gap_idx < current) with matching
    # signature at each checkpoint. Report: how many of them had lengths within ±5 of the
    # current gap's actual length?

    lines = []
    lines.append("=" * 120)
    lines.append("CHUNK 19: GAP SIGNATURE MATCHING")
    lines.append("=" * 120)
    lines.append("")
    lines.append("Hypothesis: early-gap symbol signature (rate buckets or raw counts)")
    lines.append("predicts final gap length via nearest-neighbor matching.")
    lines.append("")

    # Group gaps by account to build per-account histories
    by_acct = defaultdict(list)
    for gi, gap in enumerate(gaps):
        by_acct[gap['account']].append((gi, gap))

    # ============================================================
    # Test A: Exact bucketed signature match at each checkpoint
    # ============================================================
    lines.append("=" * 120)
    lines.append("TEST A: Exact bucketed signature (rate 5% buckets) — prediction accuracy")
    lines.append("=" * 120)

    for cp in CHECKPOINTS:
        lines.append(f"\nCheckpoint sa_spins={cp}:")
        per_acct_results = {}
        for acct, gap_list in by_acct.items():
            hits = 0
            total_predictable = 0
            correct_pred_within_5 = 0
            correct_pred_within_10 = 0

            # Accumulate historical gaps as we walk forward
            history = []  # list of (sig, gap_length) from previous gaps in this account

            for gi, gap in gap_list:
                snap = snapshots.get(gi, {}).get(cp)
                if snap is None:
                    # Gap too short to reach this checkpoint — skip
                    history.append(None)  # placeholder
                    continue

                sig = snap['sig']
                true_len = gap['length']

                # Look up historical matches (same sig) from PRIOR gaps only
                matches = []
                for h in history:
                    if h is None: continue
                    if h['sig'] == sig:
                        matches.append(h['gap_length'])

                if matches:
                    total_predictable += 1
                    predicted = sum(matches) / len(matches)  # mean of matched lengths
                    if abs(predicted - true_len) <= 5:
                        correct_pred_within_5 += 1
                    if abs(predicted - true_len) <= 10:
                        correct_pred_within_10 += 1

                # Add this gap to history
                history.append({'sig': sig, 'gap_length': true_len})

            per_acct_results[acct] = {
                'predictable': total_predictable,
                'w5': correct_pred_within_5,
                'w10': correct_pred_within_10,
            }
            lines.append(f"  {acct}: {total_predictable} predictable, "
                         f"±5: {correct_pred_within_5}/{total_predictable} "
                         f"({100*correct_pred_within_5/max(total_predictable,1):.0f}%), "
                         f"±10: {correct_pred_within_10}/{total_predictable} "
                         f"({100*correct_pred_within_10/max(total_predictable,1):.0f}%)")

    # ============================================================
    # Test B: Cosine similarity matching on symbol counts
    # ============================================================
    lines.append("")
    lines.append("=" * 120)
    lines.append("TEST B: Cosine similarity on symbol counts (threshold=0.98)")
    lines.append("=" * 120)

    for cp in CHECKPOINTS:
        lines.append(f"\nCheckpoint sa_spins={cp}, cosine >= 0.98:")
        for acct, gap_list in by_acct.items():
            total_predictable = 0
            correct_w5 = 0
            correct_w10 = 0
            history = []

            for gi, gap in gap_list:
                snap = snapshots.get(gi, {}).get(cp)
                if snap is None:
                    history.append(None); continue

                sym = snap['sym']
                true_len = gap['length']

                matches = []
                for h in history:
                    if h is None: continue
                    sim = cosine_similarity(sym, h['sym'])
                    if sim >= 0.98:
                        matches.append(h['gap_length'])

                if matches:
                    total_predictable += 1
                    predicted = sum(matches) / len(matches)
                    if abs(predicted - true_len) <= 5: correct_w5 += 1
                    if abs(predicted - true_len) <= 10: correct_w10 += 1

                history.append({'sig': snap['sig'], 'sym': sym, 'gap_length': true_len})

            lines.append(f"  {acct}: {total_predictable} predictable, "
                         f"±5: {correct_w5}/{total_predictable}, "
                         f"±10: {correct_w10}/{total_predictable}")

    # ============================================================
    # Test C: Baseline — what does random prediction look like?
    # ============================================================
    lines.append("")
    lines.append("=" * 120)
    lines.append("BASELINE: random prediction using mean gap length of history")
    lines.append("=" * 120)
    lines.append("(If signature matching beats this, we have real signal)")

    for acct, gap_list in by_acct.items():
        lengths_seen = []
        w5 = 0; w10 = 0; total = 0
        for gi, gap in gap_list:
            if len(lengths_seen) >= 2:
                predicted = sum(lengths_seen) / len(lengths_seen)
                total += 1
                if abs(predicted - gap['length']) <= 5: w5 += 1
                if abs(predicted - gap['length']) <= 10: w10 += 1
            lengths_seen.append(gap['length'])
        lines.append(f"  {acct}: {total} predictable, ±5: {w5}/{total} ({100*w5/max(total,1):.0f}%), "
                     f"±10: {w10}/{total} ({100*w10/max(total,1):.0f}%)")

    # ============================================================
    # Test D: Symbol-count exact match (no bucketing)
    # ============================================================
    lines.append("")
    lines.append("=" * 120)
    lines.append("TEST D: Exact symbol-count match (rare but strong if it works)")
    lines.append("=" * 120)

    for cp in CHECKPOINTS:
        lines.append(f"\nCheckpoint sa_spins={cp}:")
        for acct, gap_list in by_acct.items():
            total_predictable = 0
            correct_w5 = 0
            correct_w10 = 0
            history = []

            for gi, gap in gap_list:
                snap = snapshots.get(gi, {}).get(cp)
                if snap is None:
                    history.append(None); continue

                sym = snap['sym']
                true_len = gap['length']

                matches = [h['gap_length'] for h in history if h is not None and h['sym'] == sym]
                if matches:
                    total_predictable += 1
                    predicted = sum(matches) / len(matches)
                    if abs(predicted - true_len) <= 5: correct_w5 += 1
                    if abs(predicted - true_len) <= 10: correct_w10 += 1

                history.append({'sig': snap['sig'], 'sym': sym, 'gap_length': true_len})

            lines.append(f"  {acct}: {total_predictable} exact-match, ±5: {correct_w5}, ±10: {correct_w10}")

    out_path = os.path.join(os.path.dirname(__file__), '19_signature_match.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Saved -> {out_path}")


if __name__ == '__main__':
    run()
