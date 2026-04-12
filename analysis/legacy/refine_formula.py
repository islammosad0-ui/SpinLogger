"""
Refine the pity timer formula — push past 3.1x lift.
Tests: non-linear shifts, multi-gap memory, rate shifting, continuous models,
per-account cross-validation.
"""
import csv
import math
import sys

files = [
    ("Acct1", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (1).csv"),
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

# Load all gaps with account labels and sequential order
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
mean_gap = sum(all_gaps) / n
print(f"Total gaps: {n}, mean={mean_gap:.1f}, max={max(all_gaps)}", flush=True)

# ============================================================
# SECTION 1: Non-linear shift functions
# ============================================================
print(f"\n{'='*60}")
print(f"  SECTION 1: Non-linear shift functions")
print(f"{'='*60}", flush=True)

def simulate_strategy(gaps, threshold_func):
    """Simulate a betting strategy on gap data.
    threshold_func(prev_gap) -> spin number to start betting.
    Returns (caught, total_bet_spins, total_spins).
    """
    caught = 0
    total_bet = 0
    total_spins = 0
    prev = 100  # default for first gap
    for g in gaps:
        t = threshold_func(prev)
        bet_start = max(1, int(t))
        bet_spins = max(0, g - bet_start + 1) if g >= bet_start else 0
        no_bet_spins = g - bet_spins
        total_bet += bet_spins
        total_spins += g
        if g >= bet_start:
            caught += 1
        prev = g
    return caught, total_bet, total_spins

# Test different shift shapes
shift_configs = []

# Linear: T = base - shift * (prev - center)
for base in range(110, 160, 5):
    for shift_x10 in range(1, 8):
        shift = shift_x10 / 10.0
        for center in [90, 95, 100, 105]:
            f = lambda pg, b=base, s=shift, c=center: b - s * (pg - c)
            caught, bet, total = simulate_strategy(all_gaps, f)
            if caught > 0 and bet > 0:
                mb = bet / caught
                lift = (caught / n) / (bet / total)
                shift_configs.append(("linear", f"base={base},shift={shift},ctr={center}", caught, bet, total, mb, lift))

# Sqrt: T = base - shift * sqrt(max(0, prev - center))
for base in range(110, 160, 5):
    for shift_x10 in range(5, 40, 5):
        shift = shift_x10 / 10.0
        for center in [50, 60, 70, 80]:
            f = lambda pg, b=base, s=shift, c=center: b - s * math.sqrt(max(0, pg - c))
            caught, bet, total = simulate_strategy(all_gaps, f)
            if caught > 0 and bet > 0:
                mb = bet / caught
                lift = (caught / n) / (bet / total)
                shift_configs.append(("sqrt", f"base={base},shift={shift},ctr={center}", caught, bet, total, mb, lift))

# Log: T = base - shift * log(prev / center)
for base in range(110, 160, 5):
    for shift_x10 in range(10, 80, 10):
        shift = shift_x10 / 10.0
        for center in [80, 90, 100]:
            f = lambda pg, b=base, s=shift, c=center: b - s * math.log(max(1, pg) / c)
            caught, bet, total = simulate_strategy(all_gaps, f)
            if caught > 0 and bet > 0:
                mb = bet / caught
                lift = (caught / n) / (bet / total)
                shift_configs.append(("log", f"base={base},shift={shift},ctr={center}", caught, bet, total, mb, lift))

# Clamped linear: T = base - shift * clamp(prev - center, -cap, cap)
for base in range(115, 155, 5):
    for shift_x10 in range(2, 8):
        shift = shift_x10 / 10.0
        for center in [95, 100]:
            for cap in [30, 40, 50, 60, 80]:
                f = lambda pg, b=base, s=shift, c=center, cap=cap: b - s * max(-cap, min(cap, pg - c))
                caught, bet, total = simulate_strategy(all_gaps, f)
                if caught > 0 and bet > 0:
                    mb = bet / caught
                    lift = (caught / n) / (bet / total)
                    shift_configs.append(("clamped", f"base={base},shift={shift},ctr={center},cap={cap}", caught, bet, total, mb, lift))

# Sort by lift descending
shift_configs.sort(key=lambda x: -x[6])
print(f"\nTop 15 shift functions by lift:")
print(f"  {'Type':>8} {'Params':>40} {'Caught':>7} {'Bet%':>6} {'mb/h':>6} {'Lift':>5}")
for typ, params, caught, bet, total, mb, lift in shift_configs[:15]:
    print(f"  {typ:>8} {params:>40} {caught:>5}/{n} {bet/total*100:>5.1f}% {mb:>5.1f} {lift:>4.1f}x")

# Also show configs with best mb/hit (under 35)
efficient = [c for c in shift_configs if c[5] < 35 and c[2] >= 20]
efficient.sort(key=lambda x: -x[6])
print(f"\nTop 10 efficient (mb/hit < 35, catch >= 20):")
for typ, params, caught, bet, total, mb, lift in efficient[:10]:
    print(f"  {typ:>8} {params:>40} {caught:>5}/{n} {bet/total*100:>5.1f}% {mb:>5.1f} {lift:>4.1f}x")

# ============================================================
# SECTION 2: Multi-gap memory (last 2-3 gaps)
# ============================================================
print(f"\n{'='*60}")
print(f"  SECTION 2: Multi-gap memory (cumulative debt)")
print(f"{'='*60}", flush=True)

def simulate_multigap(gaps, base, shift, memory_len, center):
    """Use average of last N gaps as the debt signal."""
    caught = 0
    total_bet = 0
    total_spins = 0
    history = [center] * memory_len  # default
    for g in gaps:
        avg_prev = sum(history[-memory_len:]) / memory_len
        t = base - shift * (avg_prev - center)
        bet_start = max(1, int(t))
        bet_spins = max(0, g - bet_start + 1) if g >= bet_start else 0
        total_bet += bet_spins
        total_spins += g
        if g >= bet_start:
            caught += 1
        history.append(g)
    return caught, total_bet, total_spins

multi_results = []
for memory in [1, 2, 3, 4, 5]:
    for base in range(115, 155, 5):
        for shift_x10 in range(1, 8):
            shift = shift_x10 / 10.0
            for center in [95, 100, 105]:
                caught, bet, total = simulate_multigap(all_gaps, base, shift, memory, center)
                if caught > 0 and bet > 0:
                    mb = bet / caught
                    lift = (caught / n) / (bet / total)
                    multi_results.append((memory, base, shift, center, caught, bet, total, mb, lift))

multi_results.sort(key=lambda x: -x[8])
print(f"\nTop 15 by lift (all memory lengths):")
print(f"  {'Mem':>3} {'base':>4} {'shift':>5} {'ctr':>3} {'Caught':>7} {'Bet%':>6} {'mb/h':>6} {'Lift':>5}")
for mem, base, shift, ctr, caught, bet, total, mb, lift in multi_results[:15]:
    print(f"  {mem:>3} {base:>4} {shift:>5.1f} {ctr:>3} {caught:>5}/{n} {bet/total*100:>5.1f}% {mb:>5.1f} {lift:>4.1f}x")

# Best per memory length
print(f"\nBest per memory length:")
for mem_len in [1, 2, 3, 4, 5]:
    subset = [r for r in multi_results if r[0] == mem_len and r[7] < 40]
    if subset:
        best = max(subset, key=lambda x: x[8])
        mem, base, shift, ctr, caught, bet, total, mb, lift = best
        print(f"  Memory={mem}: base={base}, shift={shift:.1f}, ctr={ctr} -> {caught}/{n} caught, {bet/total*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

# ============================================================
# SECTION 3: Exponential debt decay (weighted sum of past gaps)
# ============================================================
print(f"\n{'='*60}")
print(f"  SECTION 3: Exponential debt decay")
print(f"{'='*60}", flush=True)

def simulate_ewma(gaps, base, shift, alpha, center):
    """Use EWMA of gaps as debt signal. alpha=1 means only last gap."""
    caught = 0
    total_bet = 0
    total_spins = 0
    ewma = center
    for g in gaps:
        t = base - shift * (ewma - center)
        bet_start = max(1, int(t))
        bet_spins = max(0, g - bet_start + 1) if g >= bet_start else 0
        total_bet += bet_spins
        total_spins += g
        if g >= bet_start:
            caught += 1
        ewma = alpha * g + (1 - alpha) * ewma
    return caught, total_bet, total_spins

ewma_results = []
for alpha_x10 in range(2, 11):  # 0.2 to 1.0
    alpha = alpha_x10 / 10.0
    for base in range(115, 155, 5):
        for shift_x10 in range(1, 8):
            shift = shift_x10 / 10.0
            for center in [95, 100]:
                caught, bet, total = simulate_ewma(all_gaps, base, shift, alpha, center)
                if caught > 0 and bet > 0:
                    mb = bet / caught
                    lift = (caught / n) / (bet / total)
                    ewma_results.append((alpha, base, shift, center, caught, bet, total, mb, lift))

ewma_results.sort(key=lambda x: -x[8])
print(f"\nTop 15 EWMA configs by lift:")
print(f"  {'alpha':>5} {'base':>4} {'shift':>5} {'ctr':>3} {'Caught':>7} {'Bet%':>6} {'mb/h':>6} {'Lift':>5}")
for alpha, base, shift, ctr, caught, bet, total, mb, lift in ewma_results[:15]:
    print(f"  {alpha:>5.1f} {base:>4} {shift:>5.1f} {ctr:>3} {caught:>5}/{n} {bet/total*100:>5.1f}% {mb:>5.1f} {lift:>4.1f}x")

# ============================================================
# SECTION 4: Continuous hazard models (logistic, exponential)
# ============================================================
print(f"\n{'='*60}")
print(f"  SECTION 4: Continuous hazard models (MLE fit)")
print(f"{'='*60}", flush=True)

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

# Model A: Logistic h(s) = L / (1 + exp(-k*(s - s0)))
print("\n--- Model A: Logistic h(s) = L / (1 + exp(-k*(s-s0))) ---", flush=True)
best_logistic = (-1e18, None)
for L_x1000 in range(10, 100, 5):
    L = L_x1000 / 1000.0
    for s0 in range(60, 160, 5):
        for k_x1000 in range(5, 80, 5):
            k = k_x1000 / 1000.0
            ll = ll_func(lambda s, L=L, s0=s0, k=k: L / (1 + math.exp(-k*(s - s0))), count, survivors, MG)
            if ll > best_logistic[0]:
                best_logistic = (ll, (L, s0, k))

ll, (L, s0, k) = best_logistic
print(f"  h(s) = {L:.3f} / (1 + exp(-{k:.3f} * (s - {s0})))")
print(f"  LL = {ll:.2f}")
for s in [10, 30, 50, 70, 90, 100, 110, 120, 130, 140, 150, 170, 200]:
    h = L / (1 + math.exp(-k*(s - s0)))
    print(f"    spin {s:>3}: {h:.5f} ({h*100:.2f}%)")

# Model B: Exponential h(s) = a * exp(b * s)
print("\n--- Model B: Exponential h(s) = a * exp(b * s) ---", flush=True)
best_exp = (-1e18, None)
for a_x100000 in range(1, 50, 2):
    a = a_x100000 / 100000.0
    for b_x10000 in range(5, 50, 2):
        b = b_x10000 / 10000.0
        ll = ll_func(lambda s, a=a, b=b: a * math.exp(b * s), count, survivors, MG)
        if ll > best_exp[0]:
            best_exp = (ll, (a, b))

ll, (a, b) = best_exp
print(f"  h(s) = {a:.6f} * exp({b:.5f} * s)")
print(f"  LL = {ll:.2f}")
for s in [10, 30, 50, 70, 90, 100, 110, 120, 130, 140, 150, 170, 200]:
    h = a * math.exp(b * s)
    print(f"    spin {s:>3}: {h:.5f} ({h*100:.2f}%)")

# Model C: Weibull hazard h(s) = (k/lambda) * (s/lambda)^(k-1)
print("\n--- Model C: Weibull hazard h(s) = (k/L)*(s/L)^(k-1) ---", flush=True)
best_weibull = (-1e18, None)
for k_x10 in range(10, 40, 2):
    k = k_x10 / 10.0
    for L in range(60, 200, 5):
        ll = ll_func(lambda s, k=k, L=L: (k/L) * (s/L)**(k-1), count, survivors, MG)
        if ll > best_weibull[0]:
            best_weibull = (ll, (k, L))

ll, (k, L) = best_weibull
print(f"  Weibull k={k:.1f}, lambda={L}")
print(f"  LL = {ll:.2f}")
for s in [10, 30, 50, 70, 90, 100, 110, 120, 130, 140, 150, 170, 200]:
    h = (k/L) * (s/L)**(k-1)
    print(f"    spin {s:>3}: {h:.5f} ({h*100:.2f}%)")

# Model D: Piecewise linear (two slopes)
print("\n--- Model D: Piecewise linear h(s) = p + k1*max(0,s-T1) + k2*max(0,s-T2) ---", flush=True)
best_pw = (-1e18, None)
for T1 in range(15, 60, 5):
    for T2 in range(80, 150, 5):
        for p_x10000 in range(5, 50, 5):
            p = p_x10000 / 10000.0
            for k1_x100000 in range(1, 20, 3):
                k1 = k1_x100000 / 100000.0
                for k2_x100000 in range(5, 60, 5):
                    k2 = k2_x100000 / 100000.0
                    ll = ll_func(lambda s, p=p, T1=T1, T2=T2, k1=k1, k2=k2:
                                 p + k1*max(0,s-T1) + k2*max(0,s-T2),
                                 count, survivors, MG)
                    if ll > best_pw[0]:
                        best_pw = (ll, (p, T1, k1, T2, k2))

ll, (p, T1, k1, T2, k2) = best_pw
print(f"  h(s) = {p:.5f} + {k1:.6f}*max(0,s-{T1}) + {k2:.6f}*max(0,s-{T2})")
print(f"  LL = {ll:.2f}")
for s in [10, 30, 50, 70, 90, 100, 110, 120, 130, 140, 150, 170, 200]:
    h = p + k1*max(0,s-T1) + k2*max(0,s-T2)
    print(f"    spin {s:>3}: {h:.5f} ({h*100:.2f}%)")

# ============================================================
# SECTION 5: Compare all models
# ============================================================
p_geo = 1.0 / mean_gap
ll_geo = ll_func(lambda s, p=p_geo: p, count, survivors, MG)

# Three-phase from fit_models.py (recompute)
best_3p = (-1e18, None)
for T1 in range(15, 80, 2):
    for T2 in range(T1+15, 170, 2):
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
        if ll > best_3p[0]: best_3p = (ll, (p1, T1, p2, T2, p3))

print(f"\n{'='*60}")
print(f"  ALL MODELS COMPARISON")
print(f"{'='*60}")
print(f"  Geometric (baseline):   LL = {ll_geo:.2f}")
print(f"  Three-phase step:       LL = {best_3p[0]:.2f}  (delta = {best_3p[0]-ll_geo:+.2f})")
print(f"  Logistic:               LL = {best_logistic[0]:.2f}  (delta = {best_logistic[0]-ll_geo:+.2f})")
print(f"  Exponential:            LL = {best_exp[0]:.2f}  (delta = {best_exp[0]-ll_geo:+.2f})")
print(f"  Weibull:                LL = {best_weibull[0]:.2f}  (delta = {best_weibull[0]-ll_geo:+.2f})")
print(f"  Piecewise linear (2):   LL = {best_pw[0]:.2f}  (delta = {best_pw[0]-ll_geo:+.2f})")

# ============================================================
# SECTION 6: Per-account cross-validation of best strategy
# ============================================================
print(f"\n{'='*60}")
print(f"  SECTION 6: Per-account cross-validation")
print(f"{'='*60}", flush=True)

# Test the adaptive strategy on each account separately
for label, gaps in per_acct_gaps.items():
    if len(gaps) < 15: continue
    ng = len(gaps)
    avg = sum(gaps) / ng

    # Best single-gap shift
    best_acct = None
    for base in range(110, 155, 5):
        for shift_x10 in range(1, 8):
            shift = shift_x10 / 10.0
            f = lambda pg, b=base, s=shift: b - s * (pg - 100)
            caught, bet, total = simulate_strategy(gaps, f)
            if caught > 0 and bet > 0:
                mb = bet / caught
                lift = (caught / ng) / (bet / total)
                if best_acct is None or lift > best_acct[5]:
                    best_acct = (base, shift, caught, bet, total, lift, mb)

    # Apply the GLOBAL best (base=130, shift=0.4) to each account
    f_global = lambda pg: 130 - 0.4 * (pg - 100)
    caught_g, bet_g, total_g = simulate_strategy(gaps, f_global)
    mb_g = bet_g / caught_g if caught_g > 0 else 999
    lift_g = (caught_g / ng) / (bet_g / total_g) if bet_g > 0 else 0

    print(f"\n  {label} (n={ng}, avg={avg:.1f}):")
    if best_acct:
        b, s, c, bt, t, lft, mb = best_acct
        print(f"    Best local:  base={b}, shift={s:.1f} -> {c}/{ng} caught, {bt/t*100:.1f}% bet, {mb:.1f} mb/h, {lft:.1f}x")
    print(f"    Global (130/0.4): {caught_g}/{ng} caught, {bet_g/total_g*100:.1f}% bet, {mb_g:.1f} mb/h, {lift_g:.1f}x")

# ============================================================
# SECTION 7: Combined signal — gap shift + accum symbol count
# ============================================================
print(f"\n{'='*60}")
print(f"  SECTION 7: Gap shift + accum symbol count")
print(f"{'='*60}", flush=True)

# Load raw spin data with accum counting
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    gaps = []
    accum_counts = []  # accum symbols seen in the gap
    sa = 0
    accum_in_gap = 0
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        sa += 1
        # Count accum symbols (value 30 in each reel)
        ac = sum(1 for r in [r1, r2, r3] if r == "accumulation")
        accum_in_gap += ac
        if r1 == r2 == r3 and r1 == "accumulation":
            gaps.append(sa)
            accum_counts.append(accum_in_gap)
            sa = 0
            accum_in_gap = 0

    if len(gaps) < 15: continue
    # Analyze: does accum count within a gap predict gap length?
    ng = len(gaps)
    pairs = list(zip(gaps, accum_counts))
    pairs.sort(key=lambda x: x[0])

    # Quintile analysis
    q = ng // 5
    print(f"\n  {label}: accum symbols vs gap length")
    print(f"    {'Quintile':>10} {'Avg gap':>8} {'Avg accum':>10} {'Accum/spin':>10}")
    for i in range(5):
        chunk = pairs[i*q:(i+1)*q] if i < 4 else pairs[i*q:]
        avg_g = sum(p[0] for p in chunk) / len(chunk)
        avg_a = sum(p[1] for p in chunk) / len(chunk)
        print(f"    {'Q'+str(i+1):>10} {avg_g:>8.1f} {avg_a:>10.1f} {avg_a/avg_g:>10.3f}")

# ============================================================
# SECTION 8: Look at gap sequence patterns — are there cycles?
# ============================================================
print(f"\n{'='*60}")
print(f"  SECTION 8: Gap sequence patterns and cycles")
print(f"{'='*60}", flush=True)

# Autocorrelation at different lags
for lag in range(1, 8):
    pairs = [(all_gaps[i], all_gaps[i+lag]) for i in range(n - lag)]
    mx = sum(g for g, _ in pairs) / len(pairs)
    my = sum(g for _, g in pairs) / len(pairs)
    cov = sum((x-mx)*(y-my) for x, y in pairs) / len(pairs)
    sx = (sum((x-mx)**2 for x, _ in pairs) / len(pairs)) ** 0.5
    sy = (sum((y-my)**2 for _, y in pairs) / len(pairs)) ** 0.5
    r = cov / (sx * sy) if sx > 0 and sy > 0 else 0
    print(f"  Lag {lag}: r = {r:+.3f}")

# Running sum (cumulative debt) pattern
print(f"\n  Cumulative debt over time:")
debt = 0
for i, g in enumerate(all_gaps):
    debt += g - mean_gap
    if (i+1) % 20 == 0 or i == n-1:
        print(f"    After gap {i+1:>3}: cumulative debt = {debt:+.0f} (avg so far = {sum(all_gaps[:i+1])/(i+1):.1f})")

# ============================================================
# SECTION 9: Does the game use a counter, not a probability?
# ============================================================
print(f"\n{'='*60}")
print(f"  SECTION 9: Hard ceiling test — is there a maximum gap?")
print(f"{'='*60}", flush=True)

sorted_gaps = sorted(all_gaps, reverse=True)
print(f"  Top 20 longest gaps: {sorted_gaps[:20]}")
print(f"  Maximum: {sorted_gaps[0]}")
print(f"  99th percentile: {sorted_gaps[int(n*0.01)]}")
print(f"  95th percentile: {sorted_gaps[int(n*0.05)]}")
print(f"  90th percentile: {sorted_gaps[int(n*0.10)]}")

# If there's a hard ceiling, all gaps should be below it
# Check: what's the probability of seeing max gap under geometric?
p_geo = 1.0 / mean_gap
prob_geo_exceeds_max = (1 - p_geo) ** sorted_gaps[0]
print(f"\n  P(gap > {sorted_gaps[0]}) under geometric: {prob_geo_exceeds_max:.6f}")
print(f"  Expected in {n} trials: {n * prob_geo_exceeds_max:.2f}")

# Under three-phase model, what's P(gap > max)?
# Phase 1: 0.003 for 26 spins, Phase 2: 0.010 for 95 spins, Phase 3: 0.027
surv_at_max = 1.0
for s in range(1, sorted_gaps[0] + 1):
    if s < 27:
        h = 0.003
    elif s < 122:
        h = 0.010
    else:
        h = 0.027
    surv_at_max *= (1 - h)
print(f"  P(gap > {sorted_gaps[0]}) under three-phase: {surv_at_max:.6f}")
print(f"  Expected in {n}: {n * surv_at_max:.2f}")

# Gaps near the maximum — are they suspiciously clustered?
over_180 = [g for g in all_gaps if g > 180]
over_160 = [g for g in all_gaps if g > 160]
over_140 = [g for g in all_gaps if g > 140]
print(f"\n  Gaps > 180: {len(over_180)} ({over_180})")
print(f"  Gaps > 160: {len(over_160)}")
print(f"  Gaps > 140: {len(over_140)}")

print(f"\nDone!", flush=True)
