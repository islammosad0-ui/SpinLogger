"""
Survival Analysis of Triple Accumulation Gaps
==============================================
Fits Weibull, log-logistic, gamma, shifted Weibull, and piecewise hazard models
to the 214 ACC gaps from 21K spins across 3 accounts.
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize, minimize_scalar
from scipy.special import gammaln
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 1. LOAD DATA AND EXTRACT GAPS
# ============================================================

files = [
    r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (1).csv",
    r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv",
    r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv",
]

all_gaps = []
account_gaps = {}

for i, f in enumerate(files):
    df = pd.read_csv(f)
    # Triple accum = r1=30, r2=30, r3=30
    acc_mask = (df['r1'] == 30) & (df['r2'] == 30) & (df['r3'] == 30)
    acc_idx = df.index[acc_mask].tolist()

    # Compute gaps between consecutive triple accums
    gaps = []
    for j in range(1, len(acc_idx)):
        gap = acc_idx[j] - acc_idx[j-1]
        gaps.append(gap)

    account_gaps[f'acct{i+1}'] = np.array(gaps)
    all_gaps.extend(gaps)
    print(f"Account {i+1}: {len(acc_idx)} ACC triples, {len(gaps)} gaps, "
          f"mean={np.mean(gaps):.1f}, median={np.median(gaps):.1f}")

gaps = np.array(all_gaps, dtype=float)
n = len(gaps)
print(f"\nTotal: {n} gaps")
print(f"Mean={np.mean(gaps):.2f}, Median={np.median(gaps):.1f}, "
      f"Std={np.std(gaps):.2f}, CV={np.std(gaps)/np.mean(gaps):.3f}")
print(f"Min={np.min(gaps)}, Max={np.max(gaps)}")
print(f"Quartiles: Q25={np.percentile(gaps,25):.0f}, Q50={np.percentile(gaps,50):.0f}, Q75={np.percentile(gaps,75):.0f}")

# ============================================================
# 2. FIT WEIBULL SURVIVAL MODEL
# ============================================================
print("\n" + "="*70)
print("2. WEIBULL FIT")
print("="*70)

# scipy weibull_min: CDF = 1 - exp(-(x/lambda)^k)
# weibull_min.fit returns (k, loc, scale) where scale=lambda
# Fix loc=0 for standard Weibull
k_wb, loc_wb, lam_wb = stats.weibull_min.fit(gaps, floc=0)
ll_wb = np.sum(stats.weibull_min.logpdf(gaps, k_wb, loc=0, scale=lam_wb))
aic_wb = -2*ll_wb + 2*2  # 2 params: k, lambda
bic_wb = -2*ll_wb + np.log(n)*2

print(f"Shape k = {k_wb:.4f}")
print(f"Scale lambda = {lam_wb:.4f}")
print(f"Log-likelihood = {ll_wb:.2f}")
print(f"AIC = {aic_wb:.2f}, BIC = {bic_wb:.2f}")

if k_wb > 1:
    print(f"\n>>> k = {k_wb:.4f} > 1: CONFIRMS INCREASING HAZARD (pity timer)")
    print(f"    Hazard h(s) = (k/lam)*(s/lam)^(k-1)")
    print(f"    At s=50:  h = {(k_wb/lam_wb)*(50/lam_wb)**(k_wb-1):.6f}")
    print(f"    At s=100: h = {(k_wb/lam_wb)*(100/lam_wb)**(k_wb-1):.6f}")
    print(f"    At s=150: h = {(k_wb/lam_wb)*(150/lam_wb)**(k_wb-1):.6f}")
    print(f"    At s=200: h = {(k_wb/lam_wb)*(200/lam_wb)**(k_wb-1):.6f}")
else:
    print(f"\n>>> k = {k_wb:.4f} <= 1: No increasing hazard detected")

# Per-spin probability table
print("\nWeibull per-spin hazard table:")
print(f"{'Spin':>6} {'h(s)':>10} {'P(survived to s)':>18} {'CDF':>10}")
for s in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 200, 250]:
    h = (k_wb/lam_wb)*(s/lam_wb)**(k_wb-1)
    surv = 1 - stats.weibull_min.cdf(s, k_wb, loc=0, scale=lam_wb)
    cdf = stats.weibull_min.cdf(s, k_wb, loc=0, scale=lam_wb)
    print(f"{s:>6} {h:>10.6f} {surv:>18.4f} {cdf:>10.4f}")

# ============================================================
# 3. FIT LOG-LOGISTIC MODEL
# ============================================================
print("\n" + "="*70)
print("3. LOG-LOGISTIC FIT")
print("="*70)

# Log-logistic: CDF = 1 / (1 + (x/alpha)^(-beta))
# = x^beta / (x^beta + alpha^beta)
# scipy.stats.fisk is the log-logistic distribution
# fisk.fit returns (c, loc, scale) where c=beta, scale=alpha
c_ll, loc_ll, alpha_ll = stats.fisk.fit(gaps, floc=0)
ll_ll = np.sum(stats.fisk.logpdf(gaps, c_ll, loc=0, scale=alpha_ll))
aic_ll = -2*ll_ll + 2*2
bic_ll = -2*ll_ll + np.log(n)*2

print(f"Shape beta (c) = {c_ll:.4f}")
print(f"Scale alpha = {alpha_ll:.4f}")
print(f"Log-likelihood = {ll_ll:.2f}")
print(f"AIC = {aic_ll:.2f}, BIC = {bic_ll:.2f}")

if c_ll > 1:
    print(f"\n>>> beta = {c_ll:.4f} > 1: Hazard first increases then decreases (hump-shaped)")
else:
    print(f"\n>>> beta = {c_ll:.4f} <= 1: Monotone decreasing hazard")

# Log-logistic hazard: h(s) = (beta/alpha)*(s/alpha)^(beta-1) / (1 + (s/alpha)^beta)
print("\nLog-logistic per-spin hazard table:")
print(f"{'Spin':>6} {'h(s)':>10} {'Survival':>12} {'CDF':>10}")
for s in [10, 20, 30, 50, 70, 90, 100, 120, 140, 160, 180, 200, 250]:
    h = (c_ll/alpha_ll)*(s/alpha_ll)**(c_ll-1) / (1 + (s/alpha_ll)**c_ll)
    surv = 1 - stats.fisk.cdf(s, c_ll, loc=0, scale=alpha_ll)
    cdf = stats.fisk.cdf(s, c_ll, loc=0, scale=alpha_ll)
    print(f"{s:>6} {h:>10.6f} {surv:>12.4f} {cdf:>10.4f}")

# ============================================================
# 4. FIT GAMMA MODEL
# ============================================================
print("\n" + "="*70)
print("4. GAMMA FIT")
print("="*70)

a_gm, loc_gm, scale_gm = stats.gamma.fit(gaps, floc=0)
ll_gm = np.sum(stats.gamma.logpdf(gaps, a_gm, loc=0, scale=scale_gm))
aic_gm = -2*ll_gm + 2*2
bic_gm = -2*ll_gm + np.log(n)*2

print(f"Shape a (alpha) = {a_gm:.4f}")
print(f"Scale (beta) = {scale_gm:.4f}")
print(f"Mean = a*scale = {a_gm*scale_gm:.2f}")
print(f"Log-likelihood = {ll_gm:.2f}")
print(f"AIC = {aic_gm:.2f}, BIC = {bic_gm:.2f}")

if a_gm > 1:
    print(f"\n>>> alpha = {a_gm:.4f} > 1: Hazard increases then flattens (consistent with pity timer)")
else:
    print(f"\n>>> alpha = {a_gm:.4f} <= 1: Decreasing or flat hazard")

# ============================================================
# 5. MODEL COMPARISON (AIC/BIC)
# ============================================================
print("\n" + "="*70)
print("5. MODEL COMPARISON")
print("="*70)

# Also fit geometric (exponential) as baseline
loc_exp, scale_exp = stats.expon.fit(gaps, floc=0)
ll_exp = np.sum(stats.expon.logpdf(gaps, loc=0, scale=scale_exp))
aic_exp = -2*ll_exp + 2*1
bic_exp = -2*ll_exp + np.log(n)*1

models = [
    ("Exponential (memoryless)", ll_exp, aic_exp, bic_exp, 1),
    ("Weibull", ll_wb, aic_wb, bic_wb, 2),
    ("Log-logistic", ll_ll, aic_ll, bic_ll, 2),
    ("Gamma", ll_gm, aic_gm, bic_gm, 2),
]

print(f"\n{'Model':<30} {'LL':>10} {'AIC':>10} {'BIC':>10} {'Params':>7} {'dAIC':>8} {'dBIC':>8}")
print("-"*85)
best_aic = min(m[2] for m in models)
best_bic = min(m[3] for m in models)
for name, ll, aic, bic, params in sorted(models, key=lambda x: x[2]):
    print(f"{name:<30} {ll:>10.2f} {aic:>10.2f} {bic:>10.2f} {params:>7} {aic-best_aic:>8.2f} {bic-best_bic:>8.2f}")

# ============================================================
# 6. SHIFTED WEIBULL (3-parameter: floor + Weibull above)
# ============================================================
print("\n" + "="*70)
print("6. SHIFTED WEIBULL (floor + Weibull)")
print("="*70)

# P(gap <= s) = 0 for s < floor
# P(gap <= s) = 1 - exp(-((s - floor)/lambda)^k) for s >= floor
# This is just weibull_min with loc=floor (free parameter)

# Let scipy fit with free loc
k_sw, floor_sw, lam_sw = stats.weibull_min.fit(gaps)
ll_sw = np.sum(stats.weibull_min.logpdf(gaps, k_sw, loc=floor_sw, scale=lam_sw))
aic_sw = -2*ll_sw + 2*3  # 3 params
bic_sw = -2*ll_sw + np.log(n)*3

print(f"Floor (loc) = {floor_sw:.2f}")
print(f"Shape k = {k_sw:.4f}")
print(f"Scale lambda = {lam_sw:.4f}")
print(f"Log-likelihood = {ll_sw:.2f}")
print(f"AIC = {aic_sw:.2f}, BIC = {bic_sw:.2f}")

# Also do a grid search for floor to ensure global optimum
print("\nGrid search over floor values:")
best_floor_ll = -np.inf
best_floor_params = None
for floor_test in range(0, int(np.min(gaps))):
    shifted = gaps - floor_test
    if np.any(shifted <= 0):
        continue
    try:
        k_t, _, lam_t = stats.weibull_min.fit(shifted, floc=0)
        ll_t = np.sum(stats.weibull_min.logpdf(shifted, k_t, loc=0, scale=lam_t))
        if ll_t > best_floor_ll:
            best_floor_ll = ll_t
            best_floor_params = (floor_test, k_t, lam_t)
    except:
        pass

if best_floor_params:
    fl, k_best, lam_best = best_floor_params
    aic_best_sw = -2*best_floor_ll + 2*3
    bic_best_sw = -2*best_floor_ll + np.log(n)*3
    print(f"\nBest floor (grid) = {fl}")
    print(f"Shape k = {k_best:.4f}")
    print(f"Scale lambda = {lam_best:.4f}")
    print(f"Log-likelihood = {best_floor_ll:.2f}")
    print(f"AIC = {aic_best_sw:.2f}, BIC = {bic_best_sw:.2f}")

    if k_best > 1:
        print(f"\n>>> k = {k_best:.4f} > 1 with floor={fl}: Increasing hazard ABOVE the floor")

    # Hazard table for shifted Weibull
    print(f"\nShifted Weibull hazard table (floor={fl}):")
    print(f"{'Spin':>6} {'Excess':>8} {'h(s)':>10} {'Survival':>12} {'CDF':>10}")
    for s in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 180, 200, 250]:
        excess = s - fl
        if excess <= 0:
            print(f"{s:>6} {excess:>8} {'0.000000':>10} {'1.0000':>12} {'0.0000':>10}")
        else:
            h = (k_best/lam_best)*(excess/lam_best)**(k_best-1)
            surv = np.exp(-(excess/lam_best)**k_best)
            cdf = 1 - surv
            print(f"{s:>6} {excess:>8} {h:>10.6f} {surv:>12.4f} {cdf:>10.4f}")

# ============================================================
# 7. PIECEWISE HAZARD (two regimes)
# ============================================================
print("\n" + "="*70)
print("7. PIECEWISE HAZARD MODEL")
print("="*70)
print("h(s) = base_rate if s < changepoint")
print("h(s) = base_rate + slope*(s - changepoint) if s >= changepoint")
print()

def piecewise_loglik(params, data):
    """Negative log-likelihood for piecewise linear hazard."""
    base_rate, changepoint, slope = params
    if base_rate <= 0 or slope < 0 or changepoint < 1:
        return 1e15

    ll = 0
    for g in data:
        # Compute cumulative hazard H(g) and hazard h(g)
        g = int(g)
        # h(s) at the exact failure spin
        if g < changepoint:
            h_g = base_rate
        else:
            h_g = base_rate + slope * (g - changepoint)

        if h_g <= 0:
            return 1e15

        # Cumulative hazard H(g) = integral of h from 0 to g
        # = base_rate * min(g, changepoint) + integral from changepoint to g of (base_rate + slope*(s-cp)) ds
        if g <= changepoint:
            H_g = base_rate * g
        else:
            H_g = base_rate * changepoint  # flat part
            excess = g - changepoint
            H_g += base_rate * excess + slope * excess**2 / 2  # ramp part

        ll += np.log(h_g) - H_g

    return -ll

# Grid search for changepoint, optimize base_rate and slope
print("Grid search over changepoints...")
best_pw = None
best_pw_ll = np.inf

for cp in range(20, 160, 5):
    res = minimize(
        lambda p: piecewise_loglik([p[0], cp, p[1]], gaps),
        x0=[0.008, 0.0002],
        method='Nelder-Mead',
        options={'maxiter': 10000}
    )
    if res.fun < best_pw_ll:
        best_pw_ll = res.fun
        best_pw = (res.x[0], cp, res.x[1])

base_r, cp_best, slope_best = best_pw
ll_pw = -best_pw_ll
aic_pw = -2*ll_pw + 2*3
bic_pw = -2*ll_pw + np.log(n)*3

print(f"\nbase_rate = {base_r:.6f} ({base_r*100:.3f}% per spin)")
print(f"changepoint = {cp_best} spins")
print(f"slope = {slope_best:.8f}")
print(f"Log-likelihood = {ll_pw:.2f}")
print(f"AIC = {aic_pw:.2f}, BIC = {bic_pw:.2f}")

print(f"\nPiecewise hazard at key spins:")
print(f"{'Spin':>6} {'h(s) %':>10} {'Phase':>10}")
for s in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 200]:
    if s < cp_best:
        h = base_r
        phase = "flat"
    else:
        h = base_r + slope_best * (s - cp_best)
        phase = "ramp"
    print(f"{s:>6} {h*100:>10.4f} {phase:>10}")

# ============================================================
# 7b. THREE-PHASE STEP FUNCTION (from Section 21)
# ============================================================
print("\n" + "="*70)
print("7b. THREE-PHASE STEP FUNCTION")
print("="*70)

def three_phase_loglik(params, data):
    """Negative log-likelihood for three-phase step hazard."""
    p1, p2, p3, T1, T2 = params
    if p1 <= 0 or p2 <= 0 or p3 <= 0 or T1 < 1 or T2 <= T1:
        return 1e15
    if p1 > 1 or p2 > 1 or p3 > 1:
        return 1e15

    ll = 0
    for g in data:
        g = int(g)
        # hazard at failure
        if g < T1:
            h_g = p1
        elif g < T2:
            h_g = p2
        else:
            h_g = p3

        if h_g <= 0:
            return 1e15

        # cumulative hazard
        if g <= T1:
            H_g = p1 * g
        elif g <= T2:
            H_g = p1 * T1 + p2 * (g - T1)
        else:
            H_g = p1 * T1 + p2 * (T2 - T1) + p3 * (g - T2)

        ll += np.log(h_g) - H_g

    return -ll

# Grid search over T1, T2
best_3p = None
best_3p_ll = np.inf

for T1 in range(10, 60, 5):
    for T2 in range(T1 + 20, 180, 5):
        res = minimize(
            lambda p: three_phase_loglik([p[0], p[1], p[2], T1, T2], gaps),
            x0=[0.003, 0.01, 0.03],
            method='Nelder-Mead',
            options={'maxiter': 10000}
        )
        if res.fun < best_3p_ll:
            best_3p_ll = res.fun
            best_3p = (res.x[0], res.x[1], res.x[2], T1, T2)

p1_3p, p2_3p, p3_3p, T1_3p, T2_3p = best_3p
ll_3p = -best_3p_ll
aic_3p = -2*ll_3p + 2*5
bic_3p = -2*ll_3p + np.log(n)*5

print(f"Phase 1 (s < {T1_3p}): h = {p1_3p:.6f} ({p1_3p*100:.3f}% per spin)")
print(f"Phase 2 ({T1_3p} <= s < {T2_3p}): h = {p2_3p:.6f} ({p2_3p*100:.3f}% per spin)")
print(f"Phase 3 (s >= {T2_3p}): h = {p3_3p:.6f} ({p3_3p*100:.3f}% per spin)")
print(f"Log-likelihood = {ll_3p:.2f}")
print(f"AIC = {aic_3p:.2f}, BIC = {bic_3p:.2f}")

# ============================================================
# 8. COMPREHENSIVE MODEL COMPARISON
# ============================================================
print("\n" + "="*70)
print("8. COMPREHENSIVE MODEL COMPARISON")
print("="*70)

all_models = [
    ("Exponential (baseline)", ll_exp, aic_exp, bic_exp, 1),
    ("Weibull", ll_wb, aic_wb, bic_wb, 2),
    ("Log-logistic", ll_ll, aic_ll, bic_ll, 2),
    ("Gamma", ll_gm, aic_gm, bic_gm, 2),
    ("Shifted Weibull (floor)", best_floor_ll if best_floor_params else ll_sw,
     aic_best_sw if best_floor_params else aic_sw,
     bic_best_sw if best_floor_params else bic_sw, 3),
    ("Piecewise linear hazard", ll_pw, aic_pw, bic_pw, 3),
    ("Three-phase step", ll_3p, aic_3p, bic_3p, 5),
]

best_aic_all = min(m[2] for m in all_models)
best_bic_all = min(m[3] for m in all_models)

print(f"\n{'Model':<30} {'LL':>10} {'AIC':>10} {'BIC':>10} {'k':>5} {'dAIC':>8} {'dBIC':>8}")
print("-"*81)
for name, ll, aic, bic, k in sorted(all_models, key=lambda x: x[2]):
    marker = " <-- BEST AIC" if aic == best_aic_all else ""
    print(f"{name:<30} {ll:>10.2f} {aic:>10.2f} {bic:>10.2f} {k:>5} {aic-best_aic_all:>8.2f} {bic-best_bic_all:>8.2f}{marker}")

# ============================================================
# 9. PURE COUNTER MODEL (no debt) + RESIDUAL AUTOCORRELATION
# ============================================================
print("\n" + "="*70)
print("9. PURE COUNTER MODEL — RESIDUAL ANALYSIS")
print("="*70)
print("Fitting pure models (no debt, no history), then checking residuals\n")

# Use the best-fitting model to compute residuals
# Cox-Snell residuals: r_i = H(gap_i) where H is cumulative hazard
# If model is correct, residuals should be Exp(1) and i.i.d.

# Weibull residuals
cs_wb = (gaps / lam_wb) ** k_wb  # Cox-Snell = cumulative hazard
# Deviance residuals for Weibull
# Martingale: M_i = 1 - H(t_i) = 1 - (t_i/lam)^k
mart_wb = 1 - cs_wb

print("--- Weibull Cox-Snell residuals ---")
print(f"Mean (should be ~1.0): {np.mean(cs_wb):.4f}")
print(f"Std (should be ~1.0): {np.std(cs_wb):.4f}")

# Check lag-1 autocorrelation of residuals
def autocorr(x, lag=1):
    """Compute autocorrelation at given lag."""
    x = x - np.mean(x)
    n = len(x)
    return np.sum(x[:n-lag] * x[lag:]) / np.sum(x**2)

# Per-account residual autocorrelation
print("\n--- Lag-1 Autocorrelation of Residuals (per account) ---")
print("If significant: debt/memory is REAL")
print("If i.i.d.: debt was artifact of hazard shape\n")

offset = 0
for acct_name, acct_gaps in account_gaps.items():
    n_acct = len(acct_gaps)
    cs_acct = (acct_gaps / lam_wb) ** k_wb

    r1_raw = autocorr(acct_gaps, 1)
    r1_resid = autocorr(cs_acct, 1)

    # SE for autocorrelation under null
    se = 1 / np.sqrt(n_acct)
    z_raw = r1_raw / se
    z_resid = r1_resid / se

    print(f"{acct_name} ({n_acct} gaps):")
    print(f"  Raw gaps:    lag-1 r = {r1_raw:.4f}, z = {z_raw:.2f}, {'SIGNIFICANT' if abs(z_raw) > 1.96 else 'not significant'}")
    print(f"  Residuals:   lag-1 r = {r1_resid:.4f}, z = {z_resid:.2f}, {'SIGNIFICANT' if abs(z_resid) > 1.96 else 'not significant'}")

# Overall
r1_raw_all = autocorr(gaps, 1)
r1_resid_all = autocorr(cs_wb, 1)
se_all = 1 / np.sqrt(n)
z_raw_all = r1_raw_all / se_all
z_resid_all = r1_resid_all / se_all

print(f"\nOverall ({n} gaps):")
print(f"  Raw gaps:    lag-1 r = {r1_raw_all:.4f}, z = {z_raw_all:.2f}, {'SIGNIFICANT' if abs(z_raw_all) > 1.96 else 'not significant'}")
print(f"  Residuals:   lag-1 r = {r1_resid_all:.4f}, z = {z_resid_all:.2f}, {'SIGNIFICANT' if abs(z_resid_all) > 1.96 else 'not significant'}")

# Extended lag check
print(f"\n--- Multi-lag Autocorrelation ---")
print(f"{'Lag':>5} {'Raw r':>10} {'Resid r':>10} {'Raw z':>10} {'Resid z':>10} {'Raw sig':>10} {'Resid sig':>10}")
for lag in range(1, 11):
    r_raw = autocorr(gaps, lag)
    r_res = autocorr(cs_wb, lag)
    z_r = r_raw / se_all
    z_s = r_res / se_all
    print(f"{lag:>5} {r_raw:>10.4f} {r_res:>10.4f} {z_r:>10.2f} {z_s:>10.2f} {'***' if abs(z_r) > 2.58 else '**' if abs(z_r) > 1.96 else '':>10} {'***' if abs(z_s) > 2.58 else '**' if abs(z_s) > 1.96 else '':>10}")

# Ljung-Box test
print("\n--- Ljung-Box Test (portmanteau) ---")
for max_lag in [5, 10]:
    Q = 0
    for lag in range(1, max_lag + 1):
        r = autocorr(cs_wb, lag)
        Q += r**2 / (n - lag)
    Q *= n * (n + 2)
    p_val = 1 - stats.chi2.cdf(Q, df=max_lag)
    print(f"Lags 1-{max_lag}: Q = {Q:.2f}, p = {p_val:.4f}, {'REJECT i.i.d. -> debt is REAL' if p_val < 0.05 else 'Cannot reject i.i.d.'}")

# Raw gap Ljung-Box
print("\n--- Ljung-Box on Raw Gaps ---")
for max_lag in [5, 10]:
    Q = 0
    for lag in range(1, max_lag + 1):
        r = autocorr(gaps, lag)
        Q += r**2 / (n - lag)
    Q *= n * (n + 2)
    p_val = 1 - stats.chi2.cdf(Q, df=max_lag)
    print(f"Lags 1-{max_lag}: Q = {Q:.2f}, p = {p_val:.4f}, {'REJECT i.i.d.' if p_val < 0.05 else 'Cannot reject i.i.d.'}")

# ============================================================
# 10. RUNS TEST ON RESIDUALS
# ============================================================
print("\n" + "="*70)
print("10. RUNS TEST ON RESIDUALS (above/below median)")
print("="*70)

median_resid = np.median(cs_wb)
above = cs_wb > median_resid
runs = 1 + np.sum(above[1:] != above[:-1])
n_above = np.sum(above)
n_below = n - n_above
expected_runs = 1 + 2 * n_above * n_below / n
var_runs = (2 * n_above * n_below * (2 * n_above * n_below - n)) / (n**2 * (n - 1))
z_runs = (runs - expected_runs) / np.sqrt(var_runs)
print(f"Runs: {runs}, Expected: {expected_runs:.1f}, Z = {z_runs:.2f}")
print(f"{'REJECT randomness' if abs(z_runs) > 1.96 else 'Cannot reject randomness'}")

# ============================================================
# 11. FINAL SUMMARY
# ============================================================
print("\n" + "="*70)
print("11. FINAL SUMMARY")
print("="*70)

print(f"""
DATA: {n} ACC gaps from 21K spins across 3 accounts

WEIBULL FIT:
  k = {k_wb:.4f}, lambda = {lam_wb:.2f}
  k > 1 confirms INCREASING HAZARD (pity timer)

BEST MODEL (by AIC): See table above

SHIFTED WEIBULL:
  floor = {best_floor_params[0] if best_floor_params else floor_sw:.0f}, k = {best_floor_params[1] if best_floor_params else k_sw:.4f}, lambda = {best_floor_params[2] if best_floor_params else lam_sw:.2f}

PIECEWISE HAZARD:
  Flat at {base_r*100:.3f}% per spin until spin {cp_best}
  Then ramp: +{slope_best*100:.5f}% per spin above changepoint

THREE-PHASE STEP:
  Phase 1 (s < {T1_3p}): {p1_3p*100:.3f}% per spin
  Phase 2 ({T1_3p} <= s < {T2_3p}): {p2_3p*100:.3f}% per spin
  Phase 3 (s >= {T2_3p}): {p3_3p*100:.3f}% per spin

DEBT REALITY CHECK:
  Raw gap lag-1 autocorrelation: {r1_raw_all:.4f} (z={z_raw_all:.2f})
  Weibull residual lag-1 autocorrelation: {r1_resid_all:.4f} (z={z_resid_all:.2f})
  If residual autocorrelation is SIGNIFICANT -> debt is a REAL mechanism beyond the hazard shape
  If residual autocorrelation is NOT significant -> debt was just an artifact of the increasing hazard
""")
