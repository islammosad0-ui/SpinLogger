#!/usr/bin/env python3
"""59_idx_cv_validate.py - Temporal CV on each idx value -> next-N valuable/triple."""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_F = ROOT / "data" / "Ahmed" / "spin_history_Ahmed_enriched_v2.csv"

rows = []
with open(CSV_F, newline='') as f:
    for r in csv.DictReader(f):
        r['r1_idx'] = int(r['r1_idx'])
        r['r2_idx'] = int(r['r2_idx'])
        r['r3_idx'] = int(r['r3_idx'])
        r['is_triple'] = r['is_triple'] == 'True'
        r['is_valuable'] = r['is_valuable'] == 'True'
        r['sn'] = int(r['sn'])
        rows.append(r)

N = len(rows)
n_folds = 5
fold_size = N // n_folds

# Pre-compute lookahead targets
for la in [1, 3, 5, 7]:
    for i, r in enumerate(rows):
        window = rows[i+1:i+1+la]
        r[f'nxt{la}_t'] = any(w['is_triple'] for w in window) if window else None
        r[f'nxt{la}_v'] = any(w['is_valuable'] for w in window) if window else None

# Compute base rates per fold for reference
print("=" * 80)
print("  59_IDX_CV_VALIDATE -- Each idx value -> next-N triple/valuable")
print("  5-fold temporal CV, minimum 10 observations per fold")
print("=" * 80)

# =====================================================================
# For each reel (r1, r2, r3), each idx (0-8), each lookahead (1,3,5,7):
#   temporal CV of: "when reel X shows idx Y, what's next-N valuable rate?"
# =====================================================================

for reel_name in ['r1_idx', 'r2_idx', 'r3_idx']:
    print(f"\n{'=' * 80}")
    print(f"  REEL: {reel_name}")
    print(f"{'=' * 80}")

    for la in [1, 3, 5, 7]:
        print(f"\n  --- Lookahead = next-{la} ---")
        print(f"  {'idx':>4} {'total_n':>7} | ", end="")
        for fold in range(n_folds):
            print(f"{'F'+str(fold)+'_v%':>8} {'(n)':>5} ", end="")
        print(f"| {'avg_v':>6} {'consist':>7} | ", end="")
        for fold in range(n_folds):
            print(f"{'F'+str(fold)+'_t%':>8} {'(n)':>5} ", end="")
        print(f"| {'avg_t':>6} {'consist':>7}")
        print("  " + "-" * 170)

        # Base rates per fold
        base_v = []
        base_t = []
        for fold in range(n_folds):
            start = fold * fold_size
            end_ = start + fold_size if fold < n_folds - 1 else N
            fr = [r for r in rows[start:end_] if r[f'nxt{la}_v'] is not None]
            bv = sum(1 for r in fr if r[f'nxt{la}_v']) / len(fr) if fr else 0
            bt = sum(1 for r in fr if r[f'nxt{la}_t']) / len(fr) if fr else 0
            base_v.append(bv)
            base_t.append(bt)

        print(f"  {'BASE':>4} {'':>7} | ", end="")
        for fold in range(n_folds):
            print(f"{100*base_v[fold]:>7.1f}% {'':>5} ", end="")
        print(f"| {100*sum(base_v)/n_folds:>5.1f}% {'':>7} | ", end="")
        for fold in range(n_folds):
            print(f"{100*base_t[fold]:>7.1f}% {'':>5} ", end="")
        print(f"| {100*sum(base_t)/n_folds:>5.1f}%")

        for idx_val in range(9):
            total_n = sum(1 for r in rows if r[reel_name] == idx_val)
            if total_n < 20:
                continue

            fold_v_lifts = []
            fold_t_lifts = []
            fold_v_rates = []
            fold_t_rates = []
            fold_ns = []

            for fold in range(n_folds):
                start = fold * fold_size
                end_ = start + fold_size if fold < n_folds - 1 else N
                fr = rows[start:end_]

                match = [r for r in fr if r[reel_name] == idx_val and r[f'nxt{la}_v'] is not None]
                n_match = len(match)

                if n_match < 5:
                    fold_v_rates.append(None)
                    fold_t_rates.append(None)
                    fold_v_lifts.append(None)
                    fold_t_lifts.append(None)
                    fold_ns.append(n_match)
                    continue

                v_rate = sum(1 for r in match if r[f'nxt{la}_v']) / n_match
                t_rate = sum(1 for r in match if r[f'nxt{la}_t']) / n_match
                fold_v_rates.append(v_rate)
                fold_t_rates.append(t_rate)
                fold_v_lifts.append(v_rate - base_v[fold])
                fold_t_lifts.append(t_rate - base_t[fold])
                fold_ns.append(n_match)

            # Print row
            print(f"  {idx_val:>4} {total_n:>7} | ", end="")
            for fold in range(n_folds):
                if fold_v_rates[fold] is not None:
                    lift = fold_v_lifts[fold]
                    marker = "+" if lift > 0.03 else ("-" if lift < -0.03 else " ")
                    print(f"{100*fold_v_rates[fold]:>6.1f}%{marker} ({fold_ns[fold]:>3}) ", end="")
                else:
                    print(f"{'n/a':>7}  ({fold_ns[fold]:>3}) ", end="")

            # Avg and consistency for valuable
            valid_v = [l for l in fold_v_lifts if l is not None]
            if valid_v:
                avg_v_lift = sum(valid_v) / len(valid_v)
                pos_v = sum(1 for l in valid_v if l > 0)
                neg_v = sum(1 for l in valid_v if l < 0)
                v_tag = f"{pos_v}/{len(valid_v)}+" if avg_v_lift > 0 else f"{neg_v}/{len(valid_v)}-"
                flag_v = " ***" if (pos_v == len(valid_v) and avg_v_lift > 0.03) or \
                                   (neg_v == len(valid_v) and avg_v_lift < -0.03) else \
                         " **" if (pos_v >= 4 and avg_v_lift > 0.02) or \
                                  (neg_v >= 4 and avg_v_lift < -0.02) else \
                         " *" if (pos_v >= 3 and avg_v_lift > 0.01) or \
                                 (neg_v >= 3 and avg_v_lift < -0.01) else ""
            else:
                avg_v_lift = 0
                v_tag = "n/a"
                flag_v = ""

            print(f"| {100*avg_v_lift:>+5.1f}% {v_tag:>7}{flag_v} | ", end="")

            # Print triple rates
            for fold in range(n_folds):
                if fold_t_rates[fold] is not None:
                    lift = fold_t_lifts[fold]
                    marker = "+" if lift > 0.05 else ("-" if lift < -0.05 else " ")
                    print(f"{100*fold_t_rates[fold]:>6.1f}%{marker} ({fold_ns[fold]:>3}) ", end="")
                else:
                    print(f"{'n/a':>7}  ({fold_ns[fold]:>3}) ", end="")

            valid_t = [l for l in fold_t_lifts if l is not None]
            if valid_t:
                avg_t_lift = sum(valid_t) / len(valid_t)
                pos_t = sum(1 for l in valid_t if l > 0)
                neg_t = sum(1 for l in valid_t if l < 0)
                t_tag = f"{pos_t}/{len(valid_t)}+" if avg_t_lift > 0 else f"{neg_t}/{len(valid_t)}-"
                flag_t = " ***" if (pos_t == len(valid_t) and avg_t_lift > 0.05) or \
                                   (neg_t == len(valid_t) and avg_t_lift < -0.05) else \
                         " **" if (pos_t >= 4 and avg_t_lift > 0.03) or \
                                  (neg_t >= 4 and avg_t_lift < -0.03) else ""
            else:
                avg_t_lift = 0
                t_tag = "n/a"
                flag_t = ""

            print(f"| {100*avg_t_lift:>+5.1f}% {t_tag:>7}{flag_t}")

# =====================================================================
# NEXT-SPIN specific (most actionable): idx -> next-1 valuable
# Deep dive with Wilson CIs
# =====================================================================
import math

def wilson_ci(hits, total, z=1.96):
    if total == 0:
        return 0, 0, 0
    p = hits / total
    denom = 1 + z*z/total
    center = (p + z*z/(2*total)) / denom
    spread = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denom
    return p, max(0, center - spread), min(1, center + spread)

print(f"\n\n{'=' * 80}")
print(f"  DEEP DIVE: idx -> next-1 valuable (Wilson 95% CI)")
print(f"{'=' * 80}")

base_v1 = sum(1 for r in rows[:-1] if rows[rows.index(r)+1]['is_valuable']) / (N-1)
# Actually compute properly
base_v1_hits = sum(1 for i in range(N-1) if rows[i+1]['is_valuable'])
base_v1 = base_v1_hits / (N-1)
print(f"\nBase rate: {100*base_v1:.2f}% ({base_v1_hits}/{N-1})")

for reel_name in ['r1_idx', 'r2_idx', 'r3_idx']:
    print(f"\n  {reel_name}:")
    print(f"  {'idx':>4} {'n':>5} {'rate':>6} {'95% CI':>15} {'lift':>7} {'CV folds':>12}")
    for idx_val in range(9):
        hits = 0
        total = 0
        for i in range(N-1):
            if rows[i][reel_name] == idx_val:
                total += 1
                hits += int(rows[i+1]['is_valuable'])

        if total < 10:
            continue

        p, lo, hi = wilson_ci(hits, total)
        lift = p - base_v1

        # Quick CV consistency check
        cv_lifts = []
        for fold in range(n_folds):
            s = fold * fold_size
            e = s + fold_size if fold < n_folds - 1 else N
            fh, ft = 0, 0
            fb_h, fb_t = 0, 0
            for i in range(s, min(e, N-1)):
                if rows[i][reel_name] == idx_val:
                    ft += 1
                    fh += int(rows[i+1]['is_valuable'])
                fb_t += 1
                fb_h += int(rows[i+1]['is_valuable'])
            fr = fh/ft if ft > 0 else 0
            fbr = fb_h/fb_t if fb_t > 0 else 0
            if ft >= 5:
                cv_lifts.append(fr - fbr)

        pos = sum(1 for l in cv_lifts if l > 0)
        neg = sum(1 for l in cv_lifts if l < 0)
        cv_str = f"{pos}/5+ {neg}/5-"
        flag = " ***" if (pos == 5 and lift > 0.03) or (neg == 5 and lift < -0.03) else \
               " **" if (pos >= 4 and lift > 0.02) or (neg >= 4 and lift < -0.02) else \
               " *" if (pos >= 3 and lift > 0.01) or (neg >= 3 and lift < -0.01) else ""

        print(f"  {idx_val:>4} {total:>5} {100*p:>5.1f}% [{100*lo:>5.1f}%, {100*hi:>5.1f}%] "
              f"{100*lift:>+6.1f}pp {cv_str}{flag}")

# =====================================================================
# Combo: prev idx pair -> next valuable
# =====================================================================
print(f"\n\n{'=' * 80}")
print(f"  IDX PAIRS: (r1_idx, r3_idx) -> next-1 valuable (top candidates)")
print(f"{'=' * 80}")

from collections import defaultdict
pair_stats = defaultdict(lambda: [0, 0])  # [hits, total]
for i in range(N-1):
    pair = (rows[i]['r1_idx'], rows[i]['r3_idx'])
    pair_stats[pair][1] += 1
    pair_stats[pair][0] += int(rows[i+1]['is_valuable'])

# Sort by lift
pair_results = []
for pair, (hits, total) in pair_stats.items():
    if total < 10:
        continue
    p, lo, hi = wilson_ci(hits, total)
    lift = p - base_v1

    # CV check
    cv_lifts = []
    for fold in range(n_folds):
        s = fold * fold_size
        e = s + fold_size if fold < n_folds - 1 else N
        fh, ft, fbh, fbt = 0, 0, 0, 0
        for i in range(s, min(e, N-1)):
            pr = (rows[i]['r1_idx'], rows[i]['r3_idx'])
            nv = int(rows[i+1]['is_valuable'])
            if pr == pair:
                ft += 1; fh += nv
            fbt += 1; fbh += nv
        fr = fh/ft if ft > 0 else 0
        fbr = fbh/fbt if fbt > 0 else 0
        if ft >= 3:
            cv_lifts.append(fr - fbr)

    pos = sum(1 for l in cv_lifts if l > 0)
    pair_results.append((pair, hits, total, p, lo, hi, lift, pos, len(cv_lifts)))

pair_results.sort(key=lambda x: -x[6])
print(f"\n  {'Pair':>10} {'n':>5} {'rate':>6} {'95% CI':>15} {'lift':>7} {'CV pos':>8}")
for pair, hits, total, p, lo, hi, lift, pos, n_cv in pair_results[:15]:
    flag = " ***" if pos == n_cv and lift > 0.03 and n_cv >= 4 else \
           " **" if pos >= 4 and lift > 0.02 else ""
    print(f"  {str(pair):>10} {total:>5} {100*p:>5.1f}% [{100*lo:>5.1f}%, {100*hi:>5.1f}%] "
          f"{100*lift:>+6.1f}pp {pos}/{n_cv}+{flag}")

print("\n  Bottom (most negative):")
pair_results.sort(key=lambda x: x[6])
for pair, hits, total, p, lo, hi, lift, pos, n_cv in pair_results[:15]:
    neg = n_cv - pos
    flag = " ***" if neg == n_cv and lift < -0.03 and n_cv >= 4 else \
           " **" if neg >= 4 and lift < -0.02 else ""
    print(f"  {str(pair):>10} {total:>5} {100*p:>5.1f}% [{100*lo:>5.1f}%, {100*hi:>5.1f}%] "
          f"{100*lift:>+6.1f}pp {neg}/{n_cv}-{flag}")

print("\nDONE")
