"""
Dynamic Three-Phase Hazard Model with Debt Shift
=================================================
Extends the static three-phase step function by allowing thresholds
to shift based on the previous gap (debt memory).

Static model (from survival_analysis.py):
  h(s) = p1 if s < T1       (dead zone, ~0.31%)
  h(s) = p2 if T1 <= s < T2 (base rate, ~0.94%)
  h(s) = p3 if s >= T2      (pity timer, ~2.90%)

Dynamic model:
  T1_i = T1_base - alpha1 * (prev_gap - target)
  T2_i = T2_base - alpha2 * (prev_gap - target)
  h_i(s) = p1 if s < T1_i, p2 if T1_i <= s < T2_i, p3 if s >= T2_i

When prev_gap was LONG (> target): thresholds decrease, pity kicks in earlier.
When prev_gap was SHORT (< target): thresholds increase, game delays pity.
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize, differential_evolution
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 1. LOAD DATA — preserve per-account gap sequences
# ============================================================

files = [
    r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv",
    r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv",
    r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv",
]

# We need (prev_gap, current_gap) pairs — and these must NOT cross account boundaries
gap_pairs = []       # (prev_gap, gap) tuples usable for dynamic model
all_gaps = []        # all gaps (for static model baseline)
account_gaps = {}

for i, f in enumerate(files):
    df = pd.read_csv(f)
    acc_mask = (df['r1'] == 30) & (df['r2'] == 30) & (df['r3'] == 30)
    acc_idx = df.index[acc_mask].tolist()

    gaps_acct = []
    for j in range(1, len(acc_idx)):
        gap = acc_idx[j] - acc_idx[j-1]
        gaps_acct.append(gap)

    account_gaps[f'acct{i+1}'] = np.array(gaps_acct)
    all_gaps.extend(gaps_acct)

    # Build pairs within this account (prev_gap, current_gap)
    for j in range(1, len(gaps_acct)):
        gap_pairs.append((gaps_acct[j-1], gaps_acct[j]))

    print(f"Acct {i+1}: {len(gaps_acct)} gaps, {len(gaps_acct)-1} usable pairs")

all_gaps = np.array(all_gaps, dtype=float)
gap_pairs = np.array(gap_pairs, dtype=float)  # shape (N_pairs, 2)
n_total = len(all_gaps)
n_pairs = len(gap_pairs)
print(f"\nTotal gaps: {n_total}")
print(f"Usable (prev, current) pairs: {n_pairs}")
print(f"Mean gap: {np.mean(all_gaps):.2f}, Median: {np.median(all_gaps):.0f}")


# ============================================================
# 2. STATIC THREE-PHASE (baseline — refit for exact comparison)
# ============================================================
print("\n" + "="*70)
print("2. STATIC THREE-PHASE (baseline on same N_pairs)")
print("="*70)

def static_loglik(params, gaps):
    """Negative log-likelihood for static three-phase step hazard."""
    p1, p2, p3, T1, T2 = params
    if p1 <= 1e-8 or p2 <= 1e-8 or p3 <= 1e-8:
        return 1e15
    if p1 >= 1 or p2 >= 1 or p3 >= 1:
        return 1e15
    if T1 < 1 or T2 <= T1:
        return 1e15

    ll = 0.0
    for g in gaps:
        # hazard at failure spin
        if g < T1:
            h_g = p1
        elif g < T2:
            h_g = p2
        else:
            h_g = p3

        # cumulative hazard H(g) = integral of h from 1 to g
        if g <= T1:
            H_g = p1 * g
        elif g <= T2:
            H_g = p1 * T1 + p2 * (g - T1)
        else:
            H_g = p1 * T1 + p2 * (T2 - T1) + p3 * (g - T2)

        ll += np.log(h_g) - H_g

    return -ll

# Fit static model on the gap_pairs[:, 1] (same subset as dynamic will use)
current_gaps = gap_pairs[:, 1]

# Grid search T1, T2
best_static = None
best_static_nll = np.inf

for T1 in range(5, 55, 5):
    for T2 in range(T1 + 30, 180, 5):
        res = minimize(
            lambda p: static_loglik([p[0], p[1], p[2], T1, T2], current_gaps),
            x0=[0.003, 0.01, 0.03],
            method='Nelder-Mead',
            options={'maxiter': 20000, 'xatol': 1e-10, 'fatol': 1e-10}
        )
        if res.fun < best_static_nll:
            best_static_nll = res.fun
            best_static = (res.x[0], res.x[1], res.x[2], T1, T2)

p1_s, p2_s, p3_s, T1_s, T2_s = best_static
ll_static = -best_static_nll
aic_static = -2 * ll_static + 2 * 5  # 5 params
bic_static = -2 * ll_static + np.log(n_pairs) * 5

print(f"Phase 1 (s < {T1_s}):  p1 = {p1_s:.6f} ({p1_s*100:.3f}%)")
print(f"Phase 2 ({T1_s} <= s < {T2_s}): p2 = {p2_s:.6f} ({p2_s*100:.3f}%)")
print(f"Phase 3 (s >= {T2_s}): p3 = {p3_s:.6f} ({p3_s*100:.3f}%)")
print(f"LL = {ll_static:.2f}, AIC = {aic_static:.2f}, BIC = {bic_static:.2f}")

# Also fit on ALL gaps for reference
best_static_all = None
best_static_all_nll = np.inf
for T1 in range(5, 55, 5):
    for T2 in range(T1 + 30, 180, 5):
        res = minimize(
            lambda p: static_loglik([p[0], p[1], p[2], T1, T2], all_gaps),
            x0=[0.003, 0.01, 0.03],
            method='Nelder-Mead',
            options={'maxiter': 20000, 'xatol': 1e-10, 'fatol': 1e-10}
        )
        if res.fun < best_static_all_nll:
            best_static_all_nll = res.fun
            best_static_all = (res.x[0], res.x[1], res.x[2], T1, T2)

p1_sa, p2_sa, p3_sa, T1_sa, T2_sa = best_static_all
ll_static_all = -best_static_all_nll
print(f"\n(All {n_total} gaps: T1={T1_sa}, T2={T2_sa}, "
      f"p1={p1_sa*100:.3f}%, p2={p2_sa*100:.3f}%, p3={p3_sa*100:.3f}%, LL={ll_static_all:.2f})")


# ============================================================
# 3. DYNAMIC THREE-PHASE — SHARED SHIFT
# ============================================================
print("\n" + "="*70)
print("3. DYNAMIC THREE-PHASE — SHARED SHIFT (alpha)")
print("="*70)
print("T1_i = T1_base - alpha*(prev_gap - target)")
print("T2_i = T2_base - alpha*(prev_gap - target)")
print("(both thresholds shift by the same amount)\n")

def dynamic_shared_loglik(params, pairs):
    """NLL for dynamic three-phase with shared shift coefficient."""
    p1, p2, p3, T1_base, T2_base, alpha, target = params
    if p1 <= 1e-8 or p2 <= 1e-8 or p3 <= 1e-8:
        return 1e15
    if p1 >= 1 or p2 >= 1 or p3 >= 1:
        return 1e15
    if T1_base < 1 or T2_base <= T1_base + 10:
        return 1e15
    if target < 30 or target > 200:
        return 1e15

    ll = 0.0
    for prev_gap, g in pairs:
        shift = alpha * (prev_gap - target)
        T1 = max(1, T1_base - shift)
        T2 = max(T1 + 1, T2_base - shift)

        # hazard at failure spin
        if g < T1:
            h_g = p1
        elif g < T2:
            h_g = p2
        else:
            h_g = p3

        # cumulative hazard
        if g <= T1:
            H_g = p1 * g
        elif g <= T2:
            H_g = p1 * T1 + p2 * (g - T1)
        else:
            H_g = p1 * T1 + p2 * (T2 - T1) + p3 * (g - T2)

        ll += np.log(h_g) - H_g

    return -ll

# Use differential_evolution for global optimization
bounds_shared = [
    (0.001, 0.02),    # p1
    (0.004, 0.04),    # p2
    (0.01, 0.10),     # p3
    (5, 60),           # T1_base
    (70, 180),         # T2_base
    (0.0, 1.0),        # alpha
    (60, 140),         # target
]

print("Running differential evolution (global optimizer)...")
res_shared = differential_evolution(
    lambda p: dynamic_shared_loglik(p, gap_pairs),
    bounds=bounds_shared,
    seed=42,
    maxiter=2000,
    tol=1e-12,
    polish=True,
    popsize=30,
)

p1_d, p2_d, p3_d, T1b_d, T2b_d, alpha_d, target_d = res_shared.x
ll_shared = -res_shared.fun
aic_shared = -2 * ll_shared + 2 * 7
bic_shared = -2 * ll_shared + np.log(n_pairs) * 7

print(f"\nBase rates:")
print(f"  p1 = {p1_d:.6f} ({p1_d*100:.4f}%)")
print(f"  p2 = {p2_d:.6f} ({p2_d*100:.4f}%)")
print(f"  p3 = {p3_d:.6f} ({p3_d*100:.4f}%)")
print(f"Base thresholds:")
print(f"  T1_base = {T1b_d:.1f}")
print(f"  T2_base = {T2b_d:.1f}")
print(f"Shift: alpha = {alpha_d:.4f}")
print(f"Target: {target_d:.1f}")
print(f"\nLL = {ll_shared:.2f}, AIC = {aic_shared:.2f}, BIC = {bic_shared:.2f}")

print(f"\nExample threshold shifts:")
for prev in [40, 60, 80, 100, 120, 140, 160, 200]:
    shift = alpha_d * (prev - target_d)
    T1_eff = max(1, T1b_d - shift)
    T2_eff = max(T1_eff + 1, T2b_d - shift)
    print(f"  prev_gap={prev:>3}: shift={shift:>+7.1f} -> T1={T1_eff:>6.1f}, T2={T2_eff:>6.1f}")


# ============================================================
# 4. DYNAMIC THREE-PHASE — SEPARATE SHIFTS
# ============================================================
print("\n" + "="*70)
print("4. DYNAMIC THREE-PHASE — SEPARATE SHIFTS (alpha1, alpha2)")
print("="*70)
print("T1_i = T1_base - alpha1*(prev_gap - target)")
print("T2_i = T2_base - alpha2*(prev_gap - target)\n")

def dynamic_separate_loglik(params, pairs):
    """NLL for dynamic three-phase with separate shift coefficients."""
    p1, p2, p3, T1_base, T2_base, alpha1, alpha2, target = params
    if p1 <= 1e-8 or p2 <= 1e-8 or p3 <= 1e-8:
        return 1e15
    if p1 >= 1 or p2 >= 1 or p3 >= 1:
        return 1e15
    if T1_base < 1 or T2_base <= T1_base + 10:
        return 1e15
    if target < 30 or target > 200:
        return 1e15

    ll = 0.0
    for prev_gap, g in pairs:
        T1 = max(1, T1_base - alpha1 * (prev_gap - target))
        T2 = max(T1 + 1, T2_base - alpha2 * (prev_gap - target))

        if g < T1:
            h_g = p1
        elif g < T2:
            h_g = p2
        else:
            h_g = p3

        if g <= T1:
            H_g = p1 * g
        elif g <= T2:
            H_g = p1 * T1 + p2 * (g - T1)
        else:
            H_g = p1 * T1 + p2 * (T2 - T1) + p3 * (g - T2)

        ll += np.log(h_g) - H_g

    return -ll

bounds_separate = [
    (0.001, 0.02),    # p1
    (0.004, 0.04),    # p2
    (0.01, 0.10),     # p3
    (5, 60),           # T1_base
    (70, 180),         # T2_base
    (0.0, 1.0),        # alpha1
    (0.0, 1.0),        # alpha2
    (60, 140),         # target
]

print("Running differential evolution...")
res_separate = differential_evolution(
    lambda p: dynamic_separate_loglik(p, gap_pairs),
    bounds=bounds_separate,
    seed=42,
    maxiter=2000,
    tol=1e-12,
    polish=True,
    popsize=30,
)

p1_sep, p2_sep, p3_sep, T1b_sep, T2b_sep, a1_sep, a2_sep, tgt_sep = res_separate.x
ll_separate = -res_separate.fun
aic_separate = -2 * ll_separate + 2 * 8
bic_separate = -2 * ll_separate + np.log(n_pairs) * 8

print(f"\nBase rates:")
print(f"  p1 = {p1_sep:.6f} ({p1_sep*100:.4f}%)")
print(f"  p2 = {p2_sep:.6f} ({p2_sep*100:.4f}%)")
print(f"  p3 = {p3_sep:.6f} ({p3_sep*100:.4f}%)")
print(f"Base thresholds:")
print(f"  T1_base = {T1b_sep:.1f}")
print(f"  T2_base = {T2b_sep:.1f}")
print(f"Shifts: alpha1 = {a1_sep:.4f}, alpha2 = {a2_sep:.4f}")
print(f"Target: {tgt_sep:.1f}")
print(f"\nLL = {ll_separate:.2f}, AIC = {aic_separate:.2f}, BIC = {bic_separate:.2f}")


# ============================================================
# 5. DYNAMIC — RATES ALSO SHIFT
# ============================================================
print("\n" + "="*70)
print("5. DYNAMIC THREE-PHASE — RATE SHIFT (p3 scales with debt)")
print("="*70)
print("T2_i = T2_base - alpha*(prev_gap - target)")
print("p3_i = p3_base + beta*(prev_gap - target)")
print("(Phase 3 rate also intensifies with debt)\n")

def dynamic_rate_loglik(params, pairs):
    """NLL: threshold shifts + Phase 3 rate scales with debt."""
    p1, p2, p3_base, T1_base, T2_base, alpha, beta, target = params
    if p1 <= 1e-8 or p2 <= 1e-8 or p3_base <= 1e-8:
        return 1e15
    if p1 >= 0.5 or p2 >= 0.5:
        return 1e15
    if T1_base < 1 or T2_base <= T1_base + 10:
        return 1e15
    if target < 30 or target > 200:
        return 1e15

    ll = 0.0
    for prev_gap, g in pairs:
        debt = prev_gap - target
        T1 = max(1, T1_base - alpha * debt)
        T2 = max(T1 + 1, T2_base - alpha * debt)
        p3 = max(p2 + 0.001, p3_base + beta * debt)
        if p3 >= 1:
            return 1e15

        if g < T1:
            h_g = p1
        elif g < T2:
            h_g = p2
        else:
            h_g = p3

        if g <= T1:
            H_g = p1 * g
        elif g <= T2:
            H_g = p1 * T1 + p2 * (g - T1)
        else:
            H_g = p1 * T1 + p2 * (T2 - T1) + p3 * (g - T2)

        ll += np.log(h_g) - H_g

    return -ll

bounds_rate = [
    (0.001, 0.02),    # p1
    (0.004, 0.04),    # p2
    (0.01, 0.10),     # p3_base
    (5, 60),           # T1_base
    (70, 180),         # T2_base
    (0.0, 1.0),        # alpha (threshold shift)
    (-0.001, 0.002),   # beta (rate shift)
    (60, 140),         # target
]

print("Running differential evolution...")
res_rate = differential_evolution(
    lambda p: dynamic_rate_loglik(p, gap_pairs),
    bounds=bounds_rate,
    seed=42,
    maxiter=2000,
    tol=1e-12,
    polish=True,
    popsize=30,
)

p1_r, p2_r, p3b_r, T1b_r, T2b_r, alpha_r, beta_r, tgt_r = res_rate.x
ll_rate = -res_rate.fun
aic_rate = -2 * ll_rate + 2 * 8
bic_rate = -2 * ll_rate + np.log(n_pairs) * 8

print(f"\nBase rates:")
print(f"  p1 = {p1_r:.6f} ({p1_r*100:.4f}%)")
print(f"  p2 = {p2_r:.6f} ({p2_r*100:.4f}%)")
print(f"  p3_base = {p3b_r:.6f} ({p3b_r*100:.4f}%)")
print(f"Base thresholds:")
print(f"  T1_base = {T1b_r:.1f}")
print(f"  T2_base = {T2b_r:.1f}")
print(f"Shifts: alpha = {alpha_r:.4f} (threshold), beta = {beta_r:.6f} (rate)")
print(f"Target: {tgt_r:.1f}")
print(f"\nLL = {ll_rate:.2f}, AIC = {aic_rate:.2f}, BIC = {bic_rate:.2f}")

print(f"\nEffective Phase 3 by previous gap:")
for prev in [40, 60, 80, 100, 120, 140, 160, 200]:
    debt = prev - tgt_r
    T2_eff = max(1, T2b_r - alpha_r * debt)
    p3_eff = max(0.001, p3b_r + beta_r * debt)
    print(f"  prev={prev:>3}: T2={T2_eff:>6.1f}, p3={p3_eff*100:.3f}%")


# ============================================================
# 6. DYNAMIC — CUMULATIVE DEBT (multi-gap memory)
# ============================================================
print("\n" + "="*70)
print("6. DYNAMIC THREE-PHASE — CUMULATIVE DEBT (multi-gap memory)")
print("="*70)
print("debt_i = clamp(debt_{i-1} + (gap_i - target), -cap, +cap)")
print("T2 = T2_base - alpha*debt, rates fixed\n")

def dynamic_cumdebt_loglik(params, account_gaps_dict):
    """NLL: cumulative debt shifts thresholds."""
    p1, p2, p3, T1_base, T2_base, alpha, target, cap = params
    if p1 <= 1e-8 or p2 <= 1e-8 or p3 <= 1e-8:
        return 1e15
    if p1 >= 1 or p2 >= 1 or p3 >= 1:
        return 1e15
    if T1_base < 1 or T2_base <= T1_base + 10:
        return 1e15
    if target < 30 or target > 200 or cap < 10:
        return 1e15

    ll = 0.0
    for acct_gaps in account_gaps_dict.values():
        debt = 0.0
        for i, g in enumerate(acct_gaps):
            T1 = max(1, T1_base - alpha * debt)
            T2 = max(T1 + 1, T2_base - alpha * debt)

            if g < T1:
                h_g = p1
            elif g < T2:
                h_g = p2
            else:
                h_g = p3

            if g <= T1:
                H_g = p1 * g
            elif g <= T2:
                H_g = p1 * T1 + p2 * (g - T1)
            else:
                H_g = p1 * T1 + p2 * (T2 - T1) + p3 * (g - T2)

            ll += np.log(h_g) - H_g

            # Update debt
            debt = np.clip(debt + (g - target), -cap, cap)

    return -ll

bounds_cumdebt = [
    (0.001, 0.02),    # p1
    (0.004, 0.04),    # p2
    (0.01, 0.10),     # p3
    (5, 60),           # T1_base
    (70, 180),         # T2_base
    (0.0, 1.0),        # alpha
    (60, 140),         # target
    (20, 300),         # cap
]

print("Running differential evolution...")
res_cumdebt = differential_evolution(
    lambda p: dynamic_cumdebt_loglik(p, account_gaps),
    bounds=bounds_cumdebt,
    seed=42,
    maxiter=2000,
    tol=1e-12,
    polish=True,
    popsize=30,
)

p1_c, p2_c, p3_c, T1b_c, T2b_c, alpha_c, tgt_c, cap_c = res_cumdebt.x
ll_cumdebt = -res_cumdebt.fun
n_cumdebt = sum(len(g) for g in account_gaps.values())  # all gaps used
aic_cumdebt = -2 * ll_cumdebt + 2 * 8
bic_cumdebt = -2 * ll_cumdebt + np.log(n_cumdebt) * 8

print(f"\nBase rates:")
print(f"  p1 = {p1_c:.6f} ({p1_c*100:.4f}%)")
print(f"  p2 = {p2_c:.6f} ({p2_c*100:.4f}%)")
print(f"  p3 = {p3_c:.6f} ({p3_c*100:.4f}%)")
print(f"Base thresholds:")
print(f"  T1_base = {T1b_c:.1f}")
print(f"  T2_base = {T2b_c:.1f}")
print(f"Shift: alpha = {alpha_c:.4f}")
print(f"Target = {tgt_c:.1f}")
print(f"Debt cap = +/-{cap_c:.1f}")
print(f"\nLL = {ll_cumdebt:.2f}, AIC = {aic_cumdebt:.2f}, BIC = {bic_cumdebt:.2f}")


# ============================================================
# 7. MODEL COMPARISON
# ============================================================
print("\n" + "="*70)
print("7. MODEL COMPARISON (all on N_pairs = {})".format(n_pairs))
print("="*70)

# Refit static on same pairs for fair comparison
# (already done above)

# For cumulative debt, we used all gaps (including first gap per account)
# To be fair, also note the LL on pairs only

# Compute LL of cumdebt model on pairs subset
# (we can't easily do this without re-running, so note the discrepancy)
print(f"\nNote: Static & shared/separate shift use {n_pairs} gap pairs.")
print(f"      Cumulative debt uses all {n_cumdebt} gaps (includes first per account).")
print(f"      Comparison is approximate for cumulative debt.\n")

models = [
    ("Static three-phase", ll_static, aic_static, bic_static, 5, n_pairs),
    ("Dynamic shared shift", ll_shared, aic_shared, bic_shared, 7, n_pairs),
    ("Dynamic separate shifts", ll_separate, aic_separate, bic_separate, 8, n_pairs),
    ("Dynamic rate+threshold", ll_rate, aic_rate, bic_rate, 8, n_pairs),
    ("Cumulative debt shift", ll_cumdebt, aic_cumdebt, bic_cumdebt, 8, n_cumdebt),
]

best_aic = min(m[2] for m in models)
print(f"{'Model':<30} {'LL':>10} {'AIC':>10} {'BIC':>10} {'k':>4} {'n':>5} {'dAIC':>8}")
print("-"*82)
for name, ll, aic, bic, k, nn in sorted(models, key=lambda x: x[2]):
    marker = " <--" if aic == best_aic else ""
    print(f"{name:<30} {ll:>10.2f} {aic:>10.2f} {bic:>10.2f} {k:>4} {nn:>5} {aic-best_aic:>8.2f}{marker}")

# Likelihood ratio tests
print(f"\n--- Likelihood Ratio Tests (vs Static) ---")
# Shared shift: 7 params vs 5, on same data
lr_shared = 2 * (ll_shared - ll_static)
p_shared = 1 - stats.chi2.cdf(lr_shared, df=2)
print(f"Shared shift vs static: LR = {lr_shared:.2f}, df=2, p = {p_shared:.6f} {'***' if p_shared < 0.001 else '**' if p_shared < 0.01 else '*' if p_shared < 0.05 else 'ns'}")

lr_separate = 2 * (ll_separate - ll_static)
p_separate = 1 - stats.chi2.cdf(lr_separate, df=3)
print(f"Separate shifts vs static: LR = {lr_separate:.2f}, df=3, p = {p_separate:.6f} {'***' if p_separate < 0.001 else '**' if p_separate < 0.01 else '*' if p_separate < 0.05 else 'ns'}")

lr_rate = 2 * (ll_rate - ll_static)
p_rate = 1 - stats.chi2.cdf(lr_rate, df=3)
print(f"Rate+threshold vs static: LR = {lr_rate:.2f}, df=3, p = {p_rate:.6f} {'***' if p_rate < 0.001 else '**' if p_rate < 0.01 else '*' if p_rate < 0.05 else 'ns'}")


# ============================================================
# 8. RESIDUAL ANALYSIS — IS DEBT FULLY CAPTURED?
# ============================================================
print("\n" + "="*70)
print("8. RESIDUAL ANALYSIS — DOES THE DYNAMIC MODEL CAPTURE ALL DEBT?")
print("="*70)

def autocorr(x, lag=1):
    x = x - np.mean(x)
    n = len(x)
    if n <= lag:
        return 0.0
    return np.sum(x[:n-lag] * x[lag:]) / np.sum(x**2)

# Compute Cox-Snell residuals for each model
# For three-phase: H(g) = cumulative hazard at gap g

def static_cumhaz(g, p1, p2, p3, T1, T2):
    if g <= T1:
        return p1 * g
    elif g <= T2:
        return p1 * T1 + p2 * (g - T1)
    else:
        return p1 * T1 + p2 * (T2 - T1) + p3 * (g - T2)

# --- Static residuals ---
cs_static = np.array([static_cumhaz(g, p1_s, p2_s, p3_s, T1_s, T2_s) for g in current_gaps])

# --- Dynamic shared residuals ---
cs_shared = []
for prev_gap, g in gap_pairs:
    shift = alpha_d * (prev_gap - target_d)
    T1 = max(1, T1b_d - shift)
    T2 = max(T1 + 1, T2b_d - shift)
    H = static_cumhaz(g, p1_d, p2_d, p3_d, T1, T2)
    cs_shared.append(H)
cs_shared = np.array(cs_shared)

# --- Dynamic separate residuals ---
cs_separate = []
for prev_gap, g in gap_pairs:
    T1 = max(1, T1b_sep - a1_sep * (prev_gap - tgt_sep))
    T2 = max(T1 + 1, T2b_sep - a2_sep * (prev_gap - tgt_sep))
    H = static_cumhaz(g, p1_sep, p2_sep, p3_sep, T1, T2)
    cs_separate.append(H)
cs_separate = np.array(cs_separate)

# --- Dynamic rate residuals ---
cs_rate = []
for prev_gap, g in gap_pairs:
    debt = prev_gap - tgt_r
    T1 = max(1, T1b_r - alpha_r * debt)
    T2 = max(T1 + 1, T2b_r - alpha_r * debt)
    p3_eff = max(p2_r + 0.001, p3b_r + beta_r * debt)
    H = static_cumhaz(g, p1_r, p2_r, p3_eff, T1, T2)
    cs_rate.append(H)
cs_rate = np.array(cs_rate)

# --- Cumulative debt residuals ---
cs_cumdebt = []
for acct_gaps_arr in account_gaps.values():
    debt = 0.0
    for g in acct_gaps_arr:
        T1 = max(1, T1b_c - alpha_c * debt)
        T2 = max(T1 + 1, T2b_c - alpha_c * debt)
        H = static_cumhaz(g, p1_c, p2_c, p3_c, T1, T2)
        cs_cumdebt.append(H)
        debt = np.clip(debt + (g - tgt_c), -cap_c, cap_c)
cs_cumdebt = np.array(cs_cumdebt)

print(f"\n{'Model':<30} {'r(1)':>8} {'z':>8} {'sig':>6}  {'r(2)':>8} {'r(3)':>8}  {'LB(5) p':>10}")
print("-"*92)

for name, resid in [
    ("Static three-phase", cs_static),
    ("Dynamic shared", cs_shared),
    ("Dynamic separate", cs_separate),
    ("Dynamic rate+threshold", cs_rate),
    ("Cumulative debt", cs_cumdebt),
]:
    nn = len(resid)
    se = 1 / np.sqrt(nn)

    r1 = autocorr(resid, 1)
    r2 = autocorr(resid, 2)
    r3 = autocorr(resid, 3)
    z1 = r1 / se

    # Ljung-Box
    Q = 0
    for lag in range(1, 6):
        r = autocorr(resid, lag)
        Q += r**2 / (nn - lag)
    Q *= nn * (nn + 2)
    p_lb = 1 - stats.chi2.cdf(Q, df=5)

    sig = '***' if abs(z1) > 2.58 else '**' if abs(z1) > 1.96 else 'ns'
    print(f"{name:<30} {r1:>8.4f} {z1:>8.2f} {sig:>6}  {r2:>8.4f} {r3:>8.4f}  {p_lb:>10.4f} {'CLEAN' if p_lb > 0.05 else 'REJECT'}")


# ============================================================
# 9. PER-ACCOUNT RESIDUAL CHECK (best model)
# ============================================================
print("\n" + "="*70)
print("9. PER-ACCOUNT RESIDUAL CHECK")
print("="*70)

# Pick the best dynamic model and check per-account
# Use cumulative debt model since it uses full sequences
print("\n--- Cumulative Debt Model Residuals Per Account ---")
for acct_name, acct_gaps_arr in account_gaps.items():
    resid_acct = []
    debt = 0.0
    for g in acct_gaps_arr:
        T1 = max(1, T1b_c - alpha_c * debt)
        T2 = max(T1 + 1, T2b_c - alpha_c * debt)
        H = static_cumhaz(g, p1_c, p2_c, p3_c, T1, T2)
        resid_acct.append(H)
        debt = np.clip(debt + (g - tgt_c), -cap_c, cap_c)

    resid_acct = np.array(resid_acct)
    nn = len(resid_acct)
    se = 1 / np.sqrt(nn)
    r1 = autocorr(resid_acct, 1)
    z1 = r1 / se

    # Ljung-Box
    Q = 0
    for lag in range(1, 6):
        r = autocorr(resid_acct, lag)
        Q += r**2 / (nn - lag)
    Q *= nn * (nn + 2)
    p_lb = 1 - stats.chi2.cdf(Q, df=5)

    sig = '***' if abs(z1) > 2.58 else '**' if abs(z1) > 1.96 else 'ns'
    print(f"  {acct_name} ({nn} gaps): r(1)={r1:>7.4f}, z={z1:>6.2f} {sig}, LB(5) p={p_lb:.4f} {'CLEAN' if p_lb > 0.05 else 'REJECT'}")

# Also check shared shift model per account
print("\n--- Shared Shift Model Residuals Per Account ---")
offset = 0
for acct_name, acct_gaps_arr in account_gaps.items():
    n_acct = len(acct_gaps_arr)
    resid_acct = []
    for j in range(1, n_acct):
        prev_gap = acct_gaps_arr[j-1]
        g = acct_gaps_arr[j]
        shift = alpha_d * (prev_gap - target_d)
        T1 = max(1, T1b_d - shift)
        T2 = max(T1 + 1, T2b_d - shift)
        H = static_cumhaz(g, p1_d, p2_d, p3_d, T1, T2)
        resid_acct.append(H)

    resid_acct = np.array(resid_acct)
    nn = len(resid_acct)
    if nn < 5:
        continue
    se = 1 / np.sqrt(nn)
    r1 = autocorr(resid_acct, 1)
    z1 = r1 / se

    Q = 0
    for lag in range(1, min(6, nn)):
        r = autocorr(resid_acct, lag)
        Q += r**2 / (nn - lag)
    Q *= nn * (nn + 2)
    p_lb = 1 - stats.chi2.cdf(Q, df=min(5, nn-1))

    sig = '***' if abs(z1) > 2.58 else '**' if abs(z1) > 1.96 else 'ns'
    print(f"  {acct_name} ({nn} pairs): r(1)={r1:>7.4f}, z={z1:>6.2f} {sig}, LB p={p_lb:.4f} {'CLEAN' if p_lb > 0.05 else 'REJECT'}")


# ============================================================
# 10. FINAL FORMULA OUTPUT
# ============================================================
print("\n" + "="*70)
print("10. THE FORMULA")
print("="*70)

# Print whichever model is best
print(f"""
BEST MODEL BY AIC: See comparison table above.

--- STATIC THREE-PHASE (baseline) ---
  h(s) = {p1_s*100:.3f}%  if s < {T1_s}
  h(s) = {p2_s*100:.3f}%  if {T1_s} <= s < {T2_s}
  h(s) = {p3_s*100:.3f}%  if s >= {T2_s}
  LL = {ll_static:.2f}

--- DYNAMIC SHARED SHIFT (prev_gap only) ---
  shift = {alpha_d:.4f} * (prev_gap - {target_d:.1f})
  T1 = max(1, {T1b_d:.1f} - shift)
  T2 = max(T1+1, {T2b_d:.1f} - shift)
  h(s) = {p1_d*100:.4f}%  if s < T1
  h(s) = {p2_d*100:.4f}%  if T1 <= s < T2
  h(s) = {p3_d*100:.4f}%  if s >= T2
  LL = {ll_shared:.2f}, dLL vs static = {ll_shared - ll_static:+.2f}

--- CUMULATIVE DEBT (full memory) ---
  debt starts at 0, updates: debt = clamp(debt + gap - {tgt_c:.1f}, -{cap_c:.0f}, +{cap_c:.0f})
  T1 = max(1, {T1b_c:.1f} - {alpha_c:.4f} * debt)
  T2 = max(T1+1, {T2b_c:.1f} - {alpha_c:.4f} * debt)
  h(s) = {p1_c*100:.4f}%  if s < T1
  h(s) = {p2_c*100:.4f}%  if T1 <= s < T2
  h(s) = {p3_c*100:.4f}%  if s >= T2
  LL = {ll_cumdebt:.2f}
""")

# Strategy table
print("--- PRACTICAL BET-SWITCH TABLE (best model) ---")
print("Use the model with lowest residual autocorrelation.")
print()

# Use shared shift as default since it's simpler
print("Shared shift model: start max-betting at spin T2 (when Phase 3 starts)")
print(f"{'prev_gap':>10} {'T2 (switch)':>12} {'Expected gap':>14}")
for prev in [30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 180, 200]:
    shift = alpha_d * (prev - target_d)
    T2_eff = max(1, T2b_d - shift)
    # Expected gap under this T2
    # rough: most mass is around T2, so expected ~ T2 + 1/p3
    exp_gap = T2_eff + 1/p3_d * 0.5  # rough midpoint
    print(f"{prev:>10} {T2_eff:>12.0f} {'~' + str(int(exp_gap)):>13}")
