"""
Fit the exact pity timer hazard function for ACC triples.
h(s) = p_base + k * max(0, s - T)
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
print(f"Total ACC gaps: {n}, mean={sum(all_gaps)/n:.1f}")

# Precompute: for each gap, we need sum of h(s) for s=1..g-1 and h(g)
# For speed, compute log-likelihood analytically
# h(s) = p + k*max(0, s-T)
# log P(gap=g) = log(h(g)) + sum_{s=1}^{g-1} log(1-h(s))

def log_likelihood(gaps, p, T, k):
    ll = 0.0
    for g in gaps:
        # Product of survival up to g-1
        for s in range(1, g):
            h = p + k * max(0, s - T)
            if h >= 1.0: h = 0.999
            if h <= 0.0: h = 0.0001
            ll += math.log(1.0 - h)
        # Hit at g
        h_g = p + k * max(0, g - T)
        if h_g >= 1.0: h_g = 0.999
        if h_g <= 0.0: h_g = 0.0001
        ll += math.log(h_g)
    return ll

# Coarser grid first, then refine
print("\nPhase 1: Coarse grid search...")
best_ll = -1e18
best_params = None

for T in range(20, 120, 10):
    for p_x1000 in range(2, 15, 2):
        p = p_x1000 / 1000.0
        for k_x10000 in range(2, 40, 2):
            k = k_x10000 / 10000.0
            ll = log_likelihood(all_gaps, p, T, k)
            if ll > best_ll:
                best_ll = ll
                best_params = (p, T, k)

p0, T0, k0 = best_params
print(f"  Coarse best: p={p0:.4f} T={T0} k={k0:.5f} LL={best_ll:.2f}")

# Phase 2: Refine around best
print("Phase 2: Refining...")
best_ll2 = best_ll
best_p2 = (p0, T0, k0)

for T in range(max(5, T0-15), T0+16, 1):
    for p_x10000 in range(max(1, int(p0*10000)-20), int(p0*10000)+21, 1):
        p = p_x10000 / 10000.0
        for k_x100000 in range(max(1, int(k0*100000)-20), int(k0*100000)+21, 1):
            k = k_x100000 / 100000.0
            ll = log_likelihood(all_gaps, p, T, k)
            if ll > best_ll2:
                best_ll2 = ll
                best_p2 = (p, T, k)

p, T, k = best_p2
print(f"\nBEST FIT: h(s) = {p:.5f} + {k:.6f} * max(0, s - {T})")
print(f"  Log-likelihood: {best_ll2:.2f}")
print(f"")
print(f"  Base rate: {p:.5f} ({p*100:.3f}% per spin)")
print(f"  Threshold: {T} spins (pity timer kicks in)")
print(f"  Ramp rate: {k:.6f} per spin above threshold")
print(f"")

# Print hazard at key points
for s in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 175, 200]:
    h = p + k * max(0, s - T)
    print(f"  Spin {s:>3}: h={h:.5f} ({h*100:.2f}%)")

# Geometric comparison
p_geo = 1.0 / (sum(all_gaps) / n)
ll_geo = sum(math.log(p_geo) + (g - 1) * math.log(1 - p_geo) for g in all_gaps)
print(f"\nGeometric (memoryless): p={p_geo:.5f}, LL={ll_geo:.2f}")
print(f"Pity timer improvement: {best_ll2 - ll_geo:.1f} LL units")

# Predicted survival curve vs actual
print(f"\nPredicted vs Actual survival S(s) = P(gap > s):")
print(f"  {'s':>4} {'actual':>8} {'predicted':>10}")
sorted_gaps = sorted(all_gaps)
for s in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 175, 200]:
    actual = sum(1 for g in all_gaps if g > s) / n
    # Predicted: S(s) = prod(1 - h(t) for t=1..s)
    pred = 1.0
    for t in range(1, s + 1):
        h = p + k * max(0, t - T)
        h = min(h, 0.999)
        pred *= (1 - h)
    print(f"  {s:>4} {actual:>8.3f} {pred:>10.3f}")

# Now check if T shifts based on debt
print(f"\n--- Does threshold shift with previous gap? ---")
prev_gap_data = [(all_gaps[i], all_gaps[i + 1]) for i in range(n - 1)]

for label, filt in [
    ("After SHORT gap (<60)", lambda pg: pg < 60),
    ("After MID gap (60-120)", lambda pg: 60 <= pg <= 120),
    ("After LONG gap (>120)", lambda pg: 120 < pg),
]:
    subset = [ng for pg, ng in prev_gap_data if filt(pg)]
    if len(subset) < 15:
        print(f"  {label}: too few ({len(subset)})")
        continue
    avg = sum(subset) / len(subset)

    best_sub_ll = -1e18
    best_sub = None
    for T2 in range(10, 110, 5):
        for p2x in range(10, 100, 5):
            pb = p2x / 10000.0
            for k2x in range(5, 80, 5):
                kk = k2x / 100000.0
                ll = log_likelihood(subset, pb, T2, kk)
                if ll > best_sub_ll:
                    best_sub_ll = ll
                    best_sub = (pb, T2, kk)
    print(f"  {label}: n={len(subset)} avg={avg:.1f}")
    print(f"    h(s) = {best_sub[0]:.5f} + {best_sub[2]:.6f} * max(0, s - {best_sub[1]})")
