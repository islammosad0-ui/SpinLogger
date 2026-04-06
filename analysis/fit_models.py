"""
Fit hazard function models — split into fast sequential runs.
Uses precomputed survivor tables for speed.
"""
import csv
import math
import sys

files = [
    ("Acct1", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (1).csv"),
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

all_gaps = []
per_acct_gaps = {}
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    acct_gaps = []
    sa = 0
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        sa += 1
        if r1 == r2 == r3 and r1 == "accumulation":
            all_gaps.append(sa)
            acct_gaps.append(sa)
            sa = 0
    per_acct_gaps[label] = acct_gaps

n = len(all_gaps)
max_g = max(all_gaps) + 1
print(f"Total gaps: {n}, mean={sum(all_gaps)/n:.1f}, max={max(all_gaps)}", flush=True)

def build_tables(gaps):
    mg = max(gaps) + 1
    cnt = [0] * (mg + 1)
    for g in gaps: cnt[g] += 1
    surv = [0] * (mg + 1)
    surv[1] = len(gaps)
    for s in range(2, mg + 1):
        surv[s] = surv[s-1] - cnt[s-1]
    return cnt, surv, mg

count, survivors, MG = build_tables(all_gaps)

def ll_func(h_func, cnt, surv, mg):
    ll = 0.0
    for s in range(1, mg + 1):
        if surv[s] == 0: break
        h = h_func(s)
        h = max(0.00001, min(h, 0.999))
        if cnt[s] > 0: ll += cnt[s] * math.log(h)
        if surv[s] - cnt[s] > 0: ll += (surv[s] - cnt[s]) * math.log(1.0 - h)
    return ll

# ============================================================
print("\n=== MODEL 1: h(s) = p + k * max(0, s - T) [linear ramp] ===", flush=True)
best1 = (-1e18, None)
for T in range(5, 130, 2):
    for px in range(5, 150, 3):
        p = px / 10000.0
        for kx in range(3, 100, 2):
            k = kx / 100000.0
            ll = ll_func(lambda s, p=p, T=T, k=k: p + k*max(0,s-T), count, survivors, MG)
            if ll > best1[0]: best1 = (ll, (p, T, k))

ll, (p, T, k) = best1
# Refine
for Tr in range(max(1,T-3), T+4):
    for pr in range(max(1,int(p*100000)-15), int(p*100000)+16):
        pb = pr/100000.0
        for kr in range(max(1,int(k*1000000)-15), int(k*1000000)+16):
            kk = kr/1000000.0
            l = ll_func(lambda s,p=pb,T=Tr,k=kk: p+kk*max(0,s-Tr), count, survivors, MG)
            if l > best1[0]: best1 = (l, (pb, Tr, kk))

ll, (p, T, k) = best1
print(f"  h(s) = {p:.6f} + {k:.7f} * max(0, s - {T})", flush=True)
print(f"  LL = {ll:.2f}", flush=True)
for s in [10,30,50,70,90,100,110,120,130,140,150,170,200]:
    h = p + k*max(0,s-T)
    print(f"    spin {s:>3}: {h:.5f} ({h*100:.2f}%)")

# ============================================================
print("\n=== MODEL 2: h(s) = p + k*(s-T)^2 [quadratic ramp] ===", flush=True)
best2 = (-1e18, None)
for T in range(5, 130, 3):
    for px in range(5, 150, 5):
        p = px / 10000.0
        for kx in range(1, 50, 2):
            k = kx / 10000000.0
            ll = ll_func(lambda s,p=p,T=T,k=k: p+k*max(0,s-T)**2, count, survivors, MG)
            if ll > best2[0]: best2 = (ll, (p, T, k))

ll, (p, T, k) = best2
print(f"  h(s) = {p:.6f} + {k:.8f} * max(0, s - {T})^2", flush=True)
print(f"  LL = {ll:.2f}", flush=True)
for s in [10,30,50,70,90,100,110,120,130,140,150,170,200]:
    ex = max(0,s-T)
    h = p + k*ex*ex
    print(f"    spin {s:>3}: {h:.5f} ({h*100:.2f}%)")

# ============================================================
print("\n=== MODEL 3: h = p1 if s<T, else p2 [step] ===", flush=True)
best3 = (-1e18, None)
for T in range(20, 160, 1):
    # For each T, optimal p1 and p2 can be computed directly
    # p1 = hits_before_T / survivors_before_T (average hazard)
    # p2 = hits_at_or_after_T / survivors_at_or_after_T
    hits_before = sum(count[s] for s in range(1, T))
    surv_before = sum(survivors[s] for s in range(1, min(T, MG+1)) if survivors[s] > 0)
    hits_after = sum(count[s] for s in range(T, MG+1))
    surv_after = sum(survivors[s] for s in range(T, min(MG+1, MG+1)) if survivors[s] > 0)

    if surv_before == 0 or surv_after == 0: continue
    p1 = hits_before / surv_before
    p2 = hits_after / surv_after
    if p1 <= 0: p1 = 0.001
    if p2 <= 0: p2 = 0.001

    ll = ll_func(lambda s,T=T,p1=p1,p2=p2: p1 if s<T else p2, count, survivors, MG)
    if ll > best3[0]: best3 = (ll, (p1, T, p2))

ll, (p1, T, p2) = best3
print(f"  h = {p1:.5f} if s < {T}, else {p2:.5f}", flush=True)
print(f"  LL = {ll:.2f}", flush=True)
print(f"  Phase 1 ({p1*100:.2f}%): spins 1-{T-1}", flush=True)
print(f"  Phase 2 ({p2*100:.2f}%): spins {T}+", flush=True)

# ============================================================
print("\n=== MODEL 4: Three-phase [optimized] ===", flush=True)
best4 = (-1e18, None)
for T1 in range(15, 80, 2):
    for T2 in range(T1+15, 170, 2):
        # Compute optimal p1, p2, p3 analytically
        h1 = sum(count[s] for s in range(1, T1))
        s1 = sum(survivors[s] for s in range(1, min(T1, MG+1)) if survivors[s]>0)
        h2 = sum(count[s] for s in range(T1, T2))
        s2 = sum(survivors[s] for s in range(T1, min(T2, MG+1)) if survivors[s]>0)
        h3 = sum(count[s] for s in range(T2, MG+1))
        s3 = sum(survivors[s] for s in range(T2, min(MG+1, MG+1)) if survivors[s]>0)

        if s1==0 or s2==0 or s3==0: continue
        p1 = max(0.001, h1/s1)
        p2 = max(0.001, h2/s2)
        p3 = max(0.001, h3/s3)

        ll = ll_func(lambda s,T1=T1,T2=T2,p1=p1,p2=p2,p3=p3: p1 if s<T1 else (p2 if s<T2 else p3),
                     count, survivors, MG)
        if ll > best4[0]: best4 = (ll, (p1, T1, p2, T2, p3))

ll, (p1, T1, p2, T2, p3) = best4
print(f"  h = {p1:.5f} (s<{T1}) | {p2:.5f} ({T1}<=s<{T2}) | {p3:.5f} (s>={T2})", flush=True)
print(f"  LL = {ll:.2f}", flush=True)

# ============================================================
# Geometric baseline
p_geo = 1.0 / (sum(all_gaps)/n)
ll_geo = ll_func(lambda s, p=p_geo: p, count, survivors, MG)

print(f"\n{'='*60}")
print(f"  MODEL COMPARISON")
print(f"{'='*60}")
print(f"  Geometric (no pity):  LL = {ll_geo:.2f}")
print(f"  Linear ramp:          LL = {best1[0]:.2f}  (delta = {best1[0]-ll_geo:+.2f})")
print(f"  Quadratic ramp:       LL = {best2[0]:.2f}  (delta = {best2[0]-ll_geo:+.2f})")
print(f"  Two-phase step:       LL = {best3[0]:.2f}  (delta = {best3[0]-ll_geo:+.2f})")
print(f"  Three-phase step:     LL = {best4[0]:.2f}  (delta = {best4[0]-ll_geo:+.2f})")

# ============================================================
# Survival curve comparison
print(f"\n{'='*60}")
print(f"  SURVIVAL CURVE: Actual vs Best Model")
print(f"{'='*60}")
_, best_model_params = best1
pm_p, pm_T, pm_k = best_model_params
pred = 1.0
print(f"  {'s':>4} {'actual':>8} {'linear':>8} {'step2':>8} {'step3':>8}")
_, (s_p1, s_T, s_p2) = best3
_, (t_p1, t_T1, t_p2, t_T2, t_p3) = best4

pred_lin = pred_s2 = pred_s3 = 1.0
for s in range(1, 210):
    actual = sum(1 for g in all_gaps if g > s) / n

    h_lin = pm_p + pm_k * max(0, s - pm_T)
    h_lin = max(0.00001, min(h_lin, 0.999))
    pred_lin *= (1 - h_lin)

    h_s2 = s_p1 if s < s_T else s_p2
    pred_s2 *= (1 - h_s2)

    h_s3 = t_p1 if s < t_T1 else (t_p2 if s < t_T2 else t_p3)
    pred_s3 *= (1 - h_s3)

    if s % 10 == 0 or s in [1, 5]:
        print(f"  {s:>4} {actual:>8.3f} {pred_lin:>8.3f} {pred_s2:>8.3f} {pred_s3:>8.3f}")

# ============================================================
# Per-account check
print(f"\n{'='*60}")
print(f"  PER-ACCOUNT FIT (linear ramp)")
print(f"{'='*60}")
for label, gaps in per_acct_gaps.items():
    if len(gaps) < 15: continue
    ac, asurv, amg = build_tables(gaps)
    best_a = (-1e18, None)
    for T in range(5, 130, 3):
        for px in range(5, 150, 5):
            p = px/10000.0
            for kx in range(3, 80, 3):
                k = kx/100000.0
                ll = ll_func(lambda s,p=p,T=T,k=k: p+k*max(0,s-T), ac, asurv, amg)
                if ll > best_a[0]: best_a = (ll, (p, T, k))
    ll,(ap,aT,ak) = best_a
    avg = sum(gaps)/len(gaps)
    print(f"  {label} (n={len(gaps)}, avg={avg:.1f}): h = {ap:.5f} + {ak:.6f} * max(0, s-{aT})")

# ============================================================
# Does threshold shift with prev gap?
print(f"\n{'='*60}")
print(f"  DEBT EFFECT: Does hazard shift based on previous gap?")
print(f"{'='*60}")
pairs = [(all_gaps[i], all_gaps[i+1]) for i in range(n-1)]
for label, filt in [
    ("After SHORT (<60)", lambda pg: pg < 60),
    ("After MID (60-120)", lambda pg: 60 <= pg <= 120),
    ("After LONG (>120)", lambda pg: pg > 120),
]:
    subset = [ng for pg, ng in pairs if filt(pg)]
    if len(subset) < 10:
        print(f"  {label}: too few ({len(subset)})")
        continue
    sc, ss, sm = build_tables(subset)
    best_s = (-1e18, None)
    for T in range(5, 120, 3):
        for px in range(5, 150, 5):
            p = px/10000.0
            for kx in range(3, 80, 3):
                k = kx/100000.0
                ll = ll_func(lambda s,p=p,T=T,k=k: p+k*max(0,s-T), sc, ss, sm)
                if ll > best_s[0]: best_s = (ll, (p, T, k))
    ll,(sp,sT,sk) = best_s
    avg = sum(subset)/len(subset)
    print(f"  {label} (n={len(subset)}, avg={avg:.1f}): h = {sp:.5f} + {sk:.6f} * max(0, s-{sT})")

print(f"\nDone!", flush=True)
