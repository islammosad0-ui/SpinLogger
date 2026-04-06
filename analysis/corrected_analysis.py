"""
CORRECTED analysis using:
1. Only Acct2 + Acct3 (deduplicated — Acct1 is subset of Acct2)
2. sa_spins column for accurate gap lengths (including first gap)
3. sa_acc, sa_3x_* columns as predictive signals
"""
import csv
import math

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

# ============================================================
# PART 1: Extract CORRECT gaps using sa_spins
# ============================================================
print("="*60)
print("  PART 1: Corrected gap extraction using sa_spins")
print("="*60, flush=True)

all_gaps = []
all_sa_acc = []  # accum symbols at time of triple
all_sa_3x = []   # other triples at time of ACC triple
per_acct_gaps = {}
per_acct_detail = {}  # (gap, sa_acc, sa_3x_atk, sa_3x_stl, sa_3x_shd)

for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    acct_gaps = []
    acct_detail = []

    for i, row in enumerate(rows):
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        if r1 == r2 == r3 == "accumulation":
            sa = int(row["sa_spins"])
            sa_acc = int(row["sa_acc"])
            sa_3x_atk = int(row.get("sa_3x_atk", 0))
            sa_3x_stl = int(row.get("sa_3x_stl", 0))
            sa_3x_shd = int(row.get("sa_3x_shd", 0))
            total_3x = sa_3x_atk + sa_3x_stl + sa_3x_shd

            acct_gaps.append(sa)
            all_gaps.append(sa)
            all_sa_acc.append(sa_acc)
            all_sa_3x.append(total_3x)
            acct_detail.append({
                "gap": sa, "sa_acc": sa_acc,
                "sa_3x_atk": sa_3x_atk, "sa_3x_stl": sa_3x_stl,
                "sa_3x_shd": sa_3x_shd, "total_3x": total_3x,
                "acc_rate": sa_acc / sa if sa > 0 else 0
            })

    per_acct_gaps[label] = acct_gaps
    per_acct_detail[label] = acct_detail
    print(f"\n  {label}: {len(acct_gaps)} gaps, avg={sum(acct_gaps)/len(acct_gaps):.1f}, "
          f"max={max(acct_gaps)}, min={min(acct_gaps)}")
    print(f"    First 10 gaps: {acct_gaps[:10]}")
    print(f"    sa_acc at triples: {[d['sa_acc'] for d in acct_detail[:10]]}")

n = len(all_gaps)
mean_gap = sum(all_gaps) / n
print(f"\n  TOTAL: {n} gaps, mean={mean_gap:.1f}, max={max(all_gaps)}, min={min(all_gaps)}")
print(f"  Compare to old: was 214 gaps with mean=96.8 (duplicated + wrong first gaps)")

# ============================================================
# PART 2: Corrected hazard model fitting
# ============================================================
print(f"\n{'='*60}")
print(f"  PART 2: Hazard model fitting (corrected data)")
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

# Geometric baseline
p_geo = 1.0 / mean_gap
ll_geo = ll_func(lambda s, p=p_geo: p, count, survivors, MG)
print(f"\n  Geometric baseline: p={p_geo:.5f}, LL={ll_geo:.2f}")

# Three-phase step (best from before)
best_3p = (-1e18, None)
for T1 in range(10, 80, 2):
    for T2 in range(T1+15, 180, 2):
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

ll, (p1, T1, p2, T2, p3) = best_3p
print(f"\n  Three-phase step:")
print(f"    h = {p1:.5f} (s<{T1}) | {p2:.5f} ({T1}<=s<{T2}) | {p3:.5f} (s>={T2})")
print(f"    LL = {ll:.2f} (delta = {ll - ll_geo:+.2f})")

# Two-phase step
best_2p = (-1e18, None)
for T in range(15, 180, 1):
    hb = sum(count[s] for s in range(1, T))
    sb = sum(survivors[s] for s in range(1, min(T, MG+1)) if survivors[s]>0)
    ha = sum(count[s] for s in range(T, MG+1))
    sa = sum(survivors[s] for s in range(T, min(MG+1, MG+1)) if survivors[s]>0)
    if sb==0 or sa==0: continue
    pa = max(0.001, hb/sb)
    pb = max(0.001, ha/sa)
    ll = ll_func(lambda s,T=T,p1=pa,p2=pb: p1 if s<T else p2, count, survivors, MG)
    if ll > best_2p[0]: best_2p = (ll, (pa, T, pb))

ll, (p1, T, p2) = best_2p
print(f"\n  Two-phase step:")
print(f"    h = {p1:.5f} (s<{T}) | {p2:.5f} (s>={T})")
print(f"    LL = {ll:.2f} (delta = {ll - ll_geo:+.2f})")

# Linear ramp
best_lr = (-1e18, None)
for T in range(5, 130, 2):
    for px in range(5, 150, 3):
        p = px / 10000.0
        for kx in range(3, 100, 2):
            k = kx / 100000.0
            ll = ll_func(lambda s, p=p, T=T, k=k: p + k*max(0,s-T), count, survivors, MG)
            if ll > best_lr[0]: best_lr = (ll, (p, T, k))

ll, (p, T, k) = best_lr
# Refine
for Tr in range(max(1,T-3), T+4):
    for pr in range(max(1,int(p*100000)-15), int(p*100000)+16):
        pb = pr/100000.0
        for kr in range(max(1,int(k*1000000)-15), int(k*1000000)+16):
            kk = kr/1000000.0
            l = ll_func(lambda s,p=pb,T=Tr,k=kk: p+kk*max(0,s-Tr), count, survivors, MG)
            if l > best_lr[0]: best_lr = (l, (pb, Tr, kk))

ll, (p, T, k) = best_lr
print(f"\n  Linear ramp (refined):")
print(f"    h(s) = {p:.6f} + {k:.7f} * max(0, s - {T})")
print(f"    LL = {ll:.2f} (delta = {ll - ll_geo:+.2f})")

print(f"\n  Summary:")
print(f"    Geometric:    LL = {ll_geo:.2f}")
print(f"    Linear ramp:  LL = {best_lr[0]:.2f}  (delta = {best_lr[0]-ll_geo:+.2f})")
print(f"    Two-phase:    LL = {best_2p[0]:.2f}  (delta = {best_2p[0]-ll_geo:+.2f})")
print(f"    Three-phase:  LL = {best_3p[0]:.2f}  (delta = {best_3p[0]-ll_geo:+.2f})")

# ============================================================
# PART 3: sa_acc as predictor — does accum count predict gap?
# ============================================================
print(f"\n{'='*60}")
print(f"  PART 3: sa_acc (accum symbols) as predictor")
print(f"{'='*60}", flush=True)

# At the time of each triple, we know sa_spins (gap length) and sa_acc
# The key question: can we predict if we're CLOSE to a triple by looking
# at the current sa_acc relative to sa_spins?

# Group by gap length quintiles and look at accum rate
all_detail = []
for label in per_acct_detail:
    all_detail.extend(per_acct_detail[label])

sorted_by_gap = sorted(all_detail, key=lambda d: d["gap"])
q = n // 5
print(f"\n  Gap quintiles with accum stats:")
print(f"  {'Quintile':>10} {'Avg gap':>8} {'Avg sa_acc':>10} {'Acc rate':>9} {'Avg 3x':>7}")
for i in range(5):
    chunk = sorted_by_gap[i*q:(i+1)*q] if i < 4 else sorted_by_gap[i*q:]
    avg_g = sum(d["gap"] for d in chunk) / len(chunk)
    avg_a = sum(d["sa_acc"] for d in chunk) / len(chunk)
    avg_rate = sum(d["acc_rate"] for d in chunk) / len(chunk)
    avg_3x = sum(d["total_3x"] for d in chunk) / len(chunk)
    print(f"  {'Q'+str(i+1):>10} {avg_g:>8.1f} {avg_a:>10.1f} {avg_rate:>9.4f} {avg_3x:>7.1f}")

# ============================================================
# PART 4: Is there a relationship between sa_acc and gap probability?
# ============================================================
print(f"\n{'='*60}")
print(f"  PART 4: Running accum rate as real-time signal")
print(f"{'='*60}", flush=True)

# Process ALL spins (not just triples) and look at the hazard at each spin
# as a function of current sa_acc / sa_spins ratio
# Bin by (sa_spins bucket, accum_rate bucket) -> empirical hazard

hazard_by_spin_rate = {}  # (spin_bucket, rate_bucket) -> (hits, total_alive)

for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    for row in rows:
        sa = int(row["sa_spins"])
        sa_acc = int(row["sa_acc"])
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        is_acc = (r1 == r2 == r3 == "accumulation")

        # Bucket sa_spins by 20s
        spin_bucket = (sa // 20) * 20
        if spin_bucket > 200: spin_bucket = 200

        # Rate bucket
        rate = sa_acc / sa if sa > 0 else 0.3
        if rate < 0.25:
            rate_bucket = "lo(<0.25)"
        elif rate < 0.30:
            rate_bucket = "mid(0.25-0.30)"
        elif rate < 0.35:
            rate_bucket = "hi(0.30-0.35)"
        else:
            rate_bucket = "vhi(>0.35)"

        key = (spin_bucket, rate_bucket)
        if key not in hazard_by_spin_rate:
            hazard_by_spin_rate[key] = [0, 0]
        hazard_by_spin_rate[key][1] += 1
        if is_acc:
            hazard_by_spin_rate[key][0] += 1

print(f"\n  Empirical hazard by (spin_bucket, accum_rate):")
print(f"  {'Spin':>6} {'Rate bucket':>15} {'Hits':>5} {'Total':>6} {'Hazard':>8}")
for spin_bucket in range(0, 220, 20):
    for rb in ["lo(<0.25)", "mid(0.25-0.30)", "hi(0.30-0.35)", "vhi(>0.35)"]:
        key = (spin_bucket, rb)
        if key in hazard_by_spin_rate:
            hits, total = hazard_by_spin_rate[key]
            if total >= 10:
                h = hits / total
                print(f"  {spin_bucket:>6} {rb:>15} {hits:>5} {total:>6} {h:>8.4f} {'***' if h > 0.02 else ''}")

# ============================================================
# PART 5: Other triples (sa_3x_*) as predictor
# ============================================================
print(f"\n{'='*60}")
print(f"  PART 5: Other triples (sa_3x_*) as predictor")
print(f"{'='*60}", flush=True)

# Does the number of other triples since last ACC predict the gap?
# More other triples = more spins = longer gap (obviously), but
# is there an EXCESS of other triples that predicts gap end?

# Expected triples per spin: ~24% (6 triple types, each 1-7%)
# If the game uses "total triples since last ACC" as part of the counter...

for label in per_acct_detail:
    details = per_acct_detail[label]
    ng = len(details)
    print(f"\n  {label}: other_triples / gap analysis")
    print(f"  {'Gap':>5} {'3x_atk':>6} {'3x_stl':>6} {'3x_shd':>6} {'total_3x':>8} {'3x_rate':>8} {'sa_acc':>6}")
    for d in details[:15]:
        rate = d["total_3x"] / d["gap"] if d["gap"] > 0 else 0
        print(f"  {d['gap']:>5} {d['sa_3x_atk']:>6} {d['sa_3x_stl']:>6} {d['sa_3x_shd']:>6} {d['total_3x']:>8} {rate:>8.3f} {d['sa_acc']:>6}")

# Correlation: total_3x vs gap length
all_3x = [d["total_3x"] for d in all_detail]
all_g = [d["gap"] for d in all_detail]
mx = sum(all_3x) / n
my = sum(all_g) / n
cov = sum((x-mx)*(y-my) for x, y in zip(all_3x, all_g)) / n
sx = (sum((x-mx)**2 for x in all_3x) / n) ** 0.5
sy = (sum((y-my)**2 for y in all_g) / n) ** 0.5
r = cov / (sx * sy) if sx > 0 and sy > 0 else 0
print(f"\n  Correlation(total_3x, gap): r = {r:.3f}")

# What about 3x_rate (triples per spin)?
all_3x_rate = [d["total_3x"]/d["gap"] if d["gap"] > 0 else 0 for d in all_detail]
mx2 = sum(all_3x_rate) / n
cov2 = sum((x-mx2)*(y-my) for x, y in zip(all_3x_rate, all_g)) / n
sx2 = (sum((x-mx2)**2 for x in all_3x_rate) / n) ** 0.5
r2 = cov2 / (sx2 * sy) if sx2 > 0 and sy > 0 else 0
print(f"  Correlation(3x_rate, gap): r = {r2:.3f}")

# What about sa_acc rate?
all_acc_rate = [d["acc_rate"] for d in all_detail]
mx3 = sum(all_acc_rate) / n
cov3 = sum((x-mx3)*(y-my) for x, y in zip(all_acc_rate, all_g)) / n
sx3 = (sum((x-mx3)**2 for x in all_acc_rate) / n) ** 0.5
r3 = cov3 / (sx3 * sy) if sx3 > 0 and sy > 0 else 0
print(f"  Correlation(acc_rate, gap): r = {r3:.3f}")

# ============================================================
# PART 6: Corrected adaptive strategy simulation
# ============================================================
print(f"\n{'='*60}")
print(f"  PART 6: Corrected adaptive strategy (deduped data)")
print(f"{'='*60}", flush=True)

def simulate_strategy(gaps, threshold_func):
    caught = 0
    total_bet = 0
    total_spins = 0
    prev = int(mean_gap)
    for g in gaps:
        t = threshold_func(prev)
        bet_start = max(1, int(t))
        bet_spins = max(0, g - bet_start + 1) if g >= bet_start else 0
        total_bet += bet_spins
        total_spins += g
        if g >= bet_start:
            caught += 1
        prev = g
    return caught, total_bet, total_spins

# Fine grid on the best strategies
results = []
for base in range(110, 160):
    for shift_x100 in range(10, 80, 5):
        shift = shift_x100 / 100.0
        for center in [95, 97, 100]:
            f = lambda pg, b=base, s=shift, c=center: b - s * (pg - c)
            caught, bet, total = simulate_strategy(all_gaps, f)
            if caught > 0 and bet > 0:
                mb = bet / caught
                lift = (caught / n) / (bet / total)
                if lift >= 2.5 and mb < 40:
                    results.append(("linear", base, shift, center, caught, bet, total, mb, lift))

results.sort(key=lambda x: -x[8])
print(f"\nTop 20 linear shift configs (lift >= 2.5, mb < 40):")
print(f"  {'base':>4} {'shift':>5} {'ctr':>3} {'Caught':>7} {'Bet%':>6} {'mb/h':>6} {'Lift':>6}")
for _, base, shift, ctr, caught, bet, total, mb, lift in results[:20]:
    print(f"  {base:>4} {shift:>5.2f} {ctr:>3} {caught:>5}/{n} {bet/total*100:>5.1f}% {mb:>5.1f} {lift:>5.2f}x")

# EWMA
ewma_results = []
for alpha_x100 in range(70, 100):
    alpha = alpha_x100 / 100.0
    for base in range(120, 160):
        for shift_x100 in range(10, 80, 5):
            shift = shift_x100 / 100.0
            for center in [95, 97, 100]:
                caught = 0
                total_bet = 0
                total_spins = 0
                ewma = center
                for g in all_gaps:
                    t = base - shift * (ewma - center)
                    bet_start = max(1, int(t))
                    bet_spins = max(0, g - bet_start + 1) if g >= bet_start else 0
                    total_bet += bet_spins
                    total_spins += g
                    if g >= bet_start:
                        caught += 1
                    ewma = alpha * g + (1 - alpha) * ewma
                if caught > 0 and total_bet > 0:
                    mb = total_bet / caught
                    lift = (caught / n) / (total_bet / total_spins)
                    if lift >= 2.8 and mb < 35:
                        ewma_results.append((alpha, base, shift, center, caught, total_bet, total_spins, mb, lift))

ewma_results.sort(key=lambda x: -x[8])
print(f"\nTop 20 EWMA configs (lift >= 2.8, mb < 35):")
print(f"  {'alpha':>5} {'base':>4} {'shift':>5} {'ctr':>3} {'Caught':>7} {'Bet%':>6} {'mb/h':>6} {'Lift':>6}")
for alpha, base, shift, ctr, caught, bet, total, mb, lift in ewma_results[:20]:
    print(f"  {alpha:>5.2f} {base:>4} {shift:>5.2f} {ctr:>3} {caught:>5}/{n} {bet/total*100:>5.1f}% {mb:>5.1f} {lift:>5.2f}x")

# ============================================================
# PART 7: Per-account cross-validation
# ============================================================
print(f"\n{'='*60}")
print(f"  PART 7: Per-account cross-validation")
print(f"{'='*60}", flush=True)

# Test the global best on each account
for label, gaps in per_acct_gaps.items():
    ng = len(gaps)
    avg = sum(gaps) / ng
    cv = (sum((g - avg)**2 for g in gaps) / ng) ** 0.5 / avg

    # Global best linear
    if results:
        _, best_base, best_shift, best_ctr = results[0][0], results[0][1], results[0][2], results[0][3]
        f = lambda pg, b=best_base, s=best_shift, c=best_ctr: b - s * (pg - c)
        caught, bet, total = simulate_strategy(gaps, f)
        mb = bet / caught if caught > 0 else 999
        lift = (caught / ng) / (bet / total) if bet > 0 else 0
        print(f"\n  {label} (n={ng}, avg={avg:.1f}, CV={cv:.3f}):")
        print(f"    Global linear ({best_base}/{best_shift:.2f}/{best_ctr}): {caught}/{ng} caught, {bet/total*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

    # Global best EWMA
    if ewma_results:
        ba, bb, bs, bc = ewma_results[0][0], ewma_results[0][1], ewma_results[0][2], ewma_results[0][3]
        caught = 0; total_bet = 0; total_spins = 0; ewma = bc
        for g in gaps:
            t = bb - bs * (ewma - bc)
            bet_start = max(1, int(t))
            bet_spins = max(0, g - bet_start + 1) if g >= bet_start else 0
            total_bet += bet_spins; total_spins += g
            if g >= bet_start: caught += 1
            ewma = ba * g + (1 - ba) * ewma
        mb = total_bet / caught if caught > 0 else 999
        lift = (caught / ng) / (total_bet / total_spins) if total_bet > 0 else 0
        print(f"    Global EWMA ({ba:.2f}/{bb}/{bs:.2f}/{bc}): {caught}/{ng} caught, {total_bet/total_spins*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

    # Best local fit
    best_local = None
    for base in range(110, 160, 2):
        for shift_x100 in range(10, 80, 5):
            shift = shift_x100 / 100.0
            f = lambda pg, b=base, s=shift: b - s * (pg - 100)
            caught, bet, total = simulate_strategy(gaps, f)
            if caught > 0 and bet > 0:
                mb = bet / caught
                lift = (caught / ng) / (bet / total)
                if best_local is None or lift > best_local[4]:
                    best_local = (base, shift, caught, mb, lift, bet, total)
    if best_local:
        b, s, c, mb, lift, bet, total = best_local
        print(f"    Best local ({b}/{s:.2f}): {c}/{ng} caught, {bet/total*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

# ============================================================
# PART 8: Lag-1 autocorrelation and debt with corrected data
# ============================================================
print(f"\n{'='*60}")
print(f"  PART 8: Corrected statistics")
print(f"{'='*60}", flush=True)

cv = (sum((g - mean_gap)**2 for g in all_gaps) / n) ** 0.5 / mean_gap
pairs = [(all_gaps[i], all_gaps[i+1]) for i in range(n-1)]
mx = sum(g for g, _ in pairs) / len(pairs)
my = sum(g for _, g in pairs) / len(pairs)
cov = sum((x-mx)*(y-my) for x, y in pairs) / len(pairs)
sx = (sum((x-mx)**2 for x, _ in pairs) / len(pairs)) ** 0.5
sy = (sum((y-my)**2 for _, y in pairs) / len(pairs)) ** 0.5
r = cov / (sx * sy) if sx > 0 and sy > 0 else 0
print(f"\n  Mean gap: {mean_gap:.1f}")
print(f"  CV: {cv:.3f}")
print(f"  Lag-1 autocorrelation: {r:+.3f}")

# Distribution
sorted_g = sorted(all_gaps)
print(f"  Q25={sorted_g[int(n*0.25)]}, Q50={sorted_g[int(n*0.50)]}, Q75={sorted_g[int(n*0.75)]}, Q90={sorted_g[int(n*0.90)]}")
print(f"  Max={sorted_g[-1]}, Min={sorted_g[0]}")

# Top gaps
print(f"  Top 10 gaps: {sorted(all_gaps, reverse=True)[:10]}")

print(f"\nDone!", flush=True)
