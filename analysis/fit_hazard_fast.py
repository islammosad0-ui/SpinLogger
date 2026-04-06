"""
Fast hazard function fitting for ACC triples.
Uses precomputed survival tables instead of per-gap loops.
"""
import csv
import math

files = [
    ("Acct1", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (1).csv"),
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

all_gaps = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    sa = 0
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        sa += 1
        if r1 == r2 == r3 and r1 == "accumulation":
            all_gaps.append(sa)
            sa = 0

n = len(all_gaps)
max_g = max(all_gaps) + 1
print(f"Total ACC gaps: {n}, mean={sum(all_gaps)/n:.1f}, max={max(all_gaps)}")

# Precompute: count[s] = number of gaps exactly equal to s
# survivors[s] = number of gaps >= s
count = [0] * (max_g + 1)
for g in all_gaps:
    count[g] += 1

# Fast LL: instead of iterating per gap, use counts
# LL = sum over s: count[s] * log(h(s)) + (survivors[s] - count[s]) * log(1-h(s))
# where survivors[s] = n - cumulative_count[1..s-1]
survivors = [0] * (max_g + 1)
survivors[1] = n
for s in range(2, max_g + 1):
    survivors[s] = survivors[s-1] - count[s-1]

def fast_ll(p, T, k):
    ll = 0.0
    for s in range(1, max_g + 1):
        if survivors[s] == 0:
            break
        h = p + k * max(0, s - T)
        if h >= 1.0: h = 0.999
        if h <= 0.0: h = 0.00001
        hits = count[s]
        alive = survivors[s]
        if hits > 0:
            ll += hits * math.log(h)
        if alive - hits > 0:
            ll += (alive - hits) * math.log(1.0 - h)
    return ll

# ============================================================
# MODEL 1: h(s) = p + k * max(0, s - T)  [linear ramp]
# ============================================================
print("\n=== MODEL 1: h(s) = p + k * max(0, s - T) ===")
print("Coarse grid...")
best_ll = -1e18
best_params = None

for T in range(5, 130, 3):
    for p_x10000 in range(10, 150, 5):
        p = p_x10000 / 10000.0
        for k_x100000 in range(5, 100, 3):
            k = k_x100000 / 100000.0
            ll = fast_ll(p, T, k)
            if ll > best_ll:
                best_ll = ll
                best_params = (p, T, k)

p0, T0, k0 = best_params
print(f"  Coarse: p={p0:.5f} T={T0} k={k0:.6f} LL={best_ll:.2f}")

# Refine
print("Refining...")
for T in range(max(1, T0-5), T0+6):
    for p_x100000 in range(max(1, int(p0*100000)-30), int(p0*100000)+31):
        p = p_x100000 / 100000.0
        for k_x1000000 in range(max(1, int(k0*1000000)-30), int(k0*1000000)+31):
            k = k_x1000000 / 1000000.0
            ll = fast_ll(p, T, k)
            if ll > best_ll:
                best_ll = ll
                best_params = (p, T, k)

p, T, k = best_params
print(f"\n  BEST: h(s) = {p:.6f} + {k:.7f} * max(0, s - {T})")
print(f"  LL = {best_ll:.2f}")

for s in [10, 20, 30, 50, 70, 90, 100, 110, 120, 130, 140, 150, 175, 200]:
    h = p + k * max(0, s - T)
    print(f"    spin {s:>3}: h = {h:.5f} ({h*100:.2f}%)")

# ============================================================
# MODEL 2: h(s) = p + k * max(0, s - T)^2  [quadratic ramp]
# ============================================================
def fast_ll_quad(p, T, k):
    ll = 0.0
    for s in range(1, max_g + 1):
        if survivors[s] == 0: break
        excess = max(0, s - T)
        h = p + k * excess * excess
        if h >= 1.0: h = 0.999
        if h <= 0.0: h = 0.00001
        hits = count[s]
        alive = survivors[s]
        if hits > 0: ll += hits * math.log(h)
        if alive - hits > 0: ll += (alive - hits) * math.log(1.0 - h)
    return ll

print("\n=== MODEL 2: h(s) = p + k * max(0, s - T)^2 ===")
best_ll2 = -1e18
best_p2 = None
for T in range(5, 130, 3):
    for p_x10000 in range(10, 150, 5):
        pb = p_x10000 / 10000.0
        for k_x10000000 in range(1, 100, 3):
            kk = k_x10000000 / 10000000.0
            ll = fast_ll_quad(pb, T, kk)
            if ll > best_ll2:
                best_ll2 = ll
                best_p2 = (pb, T, kk)

print(f"  BEST: h(s) = {best_p2[0]:.6f} + {best_p2[2]:.8f} * max(0, s - {best_p2[1]})^2")
print(f"  LL = {best_ll2:.2f}")

for s in [10, 20, 30, 50, 70, 90, 100, 110, 120, 130, 140, 150, 175, 200]:
    ex = max(0, s - best_p2[1])
    h = best_p2[0] + best_p2[2] * ex * ex
    print(f"    spin {s:>3}: h = {h:.5f} ({h*100:.2f}%)")

# ============================================================
# MODEL 3: Two-phase step function
# h(s) = p1 if s < T, else p2
# ============================================================
print("\n=== MODEL 3: h(s) = p1 if s < T, else p2 (step) ===")
best_ll3 = -1e18
best_p3 = None
for T in range(20, 160, 2):
    for p1x in range(10, 200, 5):
        p1 = p1x / 10000.0
        for p2x in range(p1x, 500, 5):
            p2 = p2x / 10000.0
            ll = 0.0
            for s in range(1, max_g + 1):
                if survivors[s] == 0: break
                h = p1 if s < T else p2
                if h >= 1.0: h = 0.999
                hits = count[s]; alive = survivors[s]
                if hits > 0: ll += hits * math.log(h)
                if alive - hits > 0: ll += (alive - hits) * math.log(1.0 - h)
            if ll > best_ll3:
                best_ll3 = ll
                best_p3 = (p1, T, p2)

print(f"  BEST: h = {best_p3[0]:.5f} if s < {best_p3[1]}, else {best_p3[2]:.5f}")
print(f"  LL = {best_ll3:.2f}")

# ============================================================
# MODEL 4: Three-phase (low / medium / high)
# ============================================================
print("\n=== MODEL 4: Three-phase h(s) ===")
best_ll4 = -1e18
best_p4 = None
for T1 in range(20, 80, 5):
    for T2 in range(T1+10, 160, 5):
        for p1x in range(10, 100, 10):
            p1 = p1x / 10000.0
            for p2x in range(p1x, 200, 10):
                p2 = p2x / 10000.0
                for p3x in range(p2x, 500, 10):
                    p3 = p3x / 10000.0
                    ll = 0.0
                    for s in range(1, max_g + 1):
                        if survivors[s] == 0: break
                        h = p1 if s < T1 else (p2 if s < T2 else p3)
                        if h >= 1.0: h = 0.999
                        hits = count[s]; alive = survivors[s]
                        if hits > 0: ll += hits * math.log(h)
                        if alive - hits > 0: ll += (alive - hits) * math.log(1.0 - h)
                    if ll > best_ll4:
                        best_ll4 = ll
                        best_p4 = (p1, T1, p2, T2, p3)

print(f"  BEST: h = {best_p4[0]:.5f} (s<{best_p4[1]}) | {best_p4[2]:.5f} ({best_p4[1]}<=s<{best_p4[3]}) | {best_p4[4]:.5f} (s>={best_p4[3]})")
print(f"  LL = {best_ll4:.2f}")

# ============================================================
# Geometric baseline
# ============================================================
p_geo = 1.0 / (sum(all_gaps) / n)
ll_geo = 0.0
for s in range(1, max_g + 1):
    if survivors[s] == 0: break
    if count[s] > 0: ll_geo += count[s] * math.log(p_geo)
    if survivors[s] - count[s] > 0: ll_geo += (survivors[s] - count[s]) * math.log(1 - p_geo)

print(f"\n=== COMPARISON ===")
print(f"  Geometric (no pity):  LL = {ll_geo:.2f}")
print(f"  Linear ramp:          LL = {best_ll:.2f}  (delta = {best_ll - ll_geo:+.2f})")
print(f"  Quadratic ramp:       LL = {best_ll2:.2f}  (delta = {best_ll2 - ll_geo:+.2f})")
print(f"  Two-phase step:       LL = {best_ll3:.2f}  (delta = {best_ll3 - ll_geo:+.2f})")
print(f"  Three-phase step:     LL = {best_ll4:.2f}  (delta = {best_ll4 - ll_geo:+.2f})")

# ============================================================
# Predicted vs Actual survival curves for best model
# ============================================================
print(f"\n=== Survival curve: best model (linear ramp) vs actual ===")
p_best, T_best, k_best = best_params
print(f"  {'s':>4} {'actual':>8} {'predicted':>10} {'error':>8}")
pred_surv = 1.0
for s in range(1, 210):
    actual = sum(1 for g in all_gaps if g > s) / n
    h = p_best + k_best * max(0, s - T_best)
    h = min(h, 0.999)
    pred_surv *= (1 - h)
    if s % 10 == 0 or s <= 5:
        err = pred_surv - actual
        print(f"  {s:>4} {actual:>8.3f} {pred_surv:>10.3f} {err:>+8.3f}")

# ============================================================
# CHECK: does the formula change across accounts?
# ============================================================
print(f"\n=== Per-account fit (linear ramp) ===")
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    acct_gaps = []
    sa = 0
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        sa += 1
        if r1 == r2 == r3 and r1 == "accumulation":
            acct_gaps.append(sa)
            sa = 0

    if len(acct_gaps) < 10:
        print(f"  {label}: too few gaps ({len(acct_gaps)})")
        continue

    # Build count/survivor tables
    mg = max(acct_gaps) + 1
    ac = [0] * (mg + 1)
    for g in acct_gaps: ac[g] += 1
    asurv = [0] * (mg + 1)
    asurv[1] = len(acct_gaps)
    for s in range(2, mg + 1):
        asurv[s] = asurv[s-1] - ac[s-1]

    best_all = -1e18
    best_ap = None
    for T in range(5, 130, 3):
        for px in range(10, 150, 5):
            pb = px / 10000.0
            for kx in range(5, 100, 3):
                kk = kx / 100000.0
                ll = 0.0
                for s in range(1, mg + 1):
                    if asurv[s] == 0: break
                    h = pb + kk * max(0, s - T)
                    if h >= 1.0: h = 0.999
                    if h <= 0.0: h = 0.00001
                    if ac[s] > 0: ll += ac[s] * math.log(h)
                    if asurv[s] - ac[s] > 0: ll += (asurv[s] - ac[s]) * math.log(1.0 - h)
                if ll > best_all:
                    best_all = ll
                    best_ap = (pb, T, kk)

    print(f"  {label} ({len(acct_gaps)} gaps, avg={sum(acct_gaps)/len(acct_gaps):.1f}): "
          f"h = {best_ap[0]:.5f} + {best_ap[2]:.6f} * max(0, s - {best_ap[1]})")
