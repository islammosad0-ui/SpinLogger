"""
Can we make the 130 threshold dynamic to improve the formula?

Test every idea:
1. Shift based on previous gap (long gap -> lower threshold next)
2. S/M/L pattern (small<80, medium 80-140, large>140)
3. Running average of last N gaps
4. Streak detection (2+ short in a row -> expect long)
5. Debt-based (cumulative over/under shifts threshold)
6. Adaptive percentile (lower threshold if recent gaps are short)
7. Rate of rate change (is accum rate climbing fast?)
"""
import csv
from collections import deque

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
    ("Acct4", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (3).csv"),
]

RATE_GATE = 0.30

# Preload and extract gaps per account
all_data = []
all_gaps_per_account = []
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    all_data.append((label, rows))
    gaps = []
    for row in rows:
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        if r1 == r2 == r3 == "accumulation":
            gaps.append(int(row["sa_spins"]))
    all_gaps_per_account.append((label, gaps))

# Show gap distribution first
print("=" * 80)
print("GAP DISTRIBUTION (for S/M/L boundaries)")
print("=" * 80)
all_gaps = []
for label, gaps in all_gaps_per_account:
    all_gaps.extend(gaps)
    print(f"  {label}: {len(gaps)} gaps, mean={sum(gaps)/len(gaps):.1f}, median={sorted(gaps)[len(gaps)//2]}")

all_gaps_sorted = sorted(all_gaps)
n = len(all_gaps_sorted)
print(f"\n  All: {n} gaps, mean={sum(all_gaps)/n:.1f}, median={all_gaps_sorted[n//2]}")
print(f"  P25={all_gaps_sorted[n//4]}, P50={all_gaps_sorted[n//2]}, P75={all_gaps_sorted[3*n//4]}")
print(f"  Min={all_gaps_sorted[0]}, Max={all_gaps_sorted[-1]}")

# Distribution buckets
print(f"\n  Size distribution:")
for lo, hi, label in [(0, 60, "S (<60)"), (60, 100, "M (60-100)"), (100, 140, "L (100-140)"), (140, 200, "XL (140-200)"), (200, 9999, "XXL (200+)")]:
    c = sum(1 for g in all_gaps if lo <= g < hi)
    print(f"    {label}: {c} ({c/n*100:.1f}%)")

# Sequential patterns
print(f"\n  Transition matrix (prev size -> next size):")
sizes = []
for g in all_gaps:
    if g < 80: sizes.append("S")
    elif g < 130: sizes.append("M")
    else: sizes.append("L")

from collections import Counter
transitions = Counter()
for i in range(1, len(sizes)):
    transitions[(sizes[i-1], sizes[i])] += 1
for prev in ["S", "M", "L"]:
    total = sum(transitions[(prev, nxt)] for nxt in ["S", "M", "L"])
    if total > 0:
        parts = []
        for nxt in ["S", "M", "L"]:
            c = transitions[(prev, nxt)]
            parts.append(f"{nxt}:{c}({c/total*100:.0f}%)")
        print(f"    After {prev} -> {', '.join(parts)}")


def simulate(strategy_fn, label):
    """Run a strategy across all accounts.
    strategy_fn(prev_gaps, sa_spins, sa_acc, rate) -> should_bet (bool)
    Returns (caught, total_acc, bet_spins, total_spins)
    """
    total_caught = 0
    total_bet = 0
    total_spins = 0
    total_acc = 0

    for acct_label, rows in all_data:
        prev_gaps = []
        for row in rows:
            sa = int(row["sa_spins"])
            sa_acc = int(row["sa_acc"])
            r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
            is_acc = (r1 == r2 == r3 == "accumulation")
            rate = sa_acc / sa if sa > 0 else 0.0

            total_spins += 1
            should_bet = strategy_fn(prev_gaps, sa, sa_acc, rate)
            if should_bet:
                total_bet += 1

            if is_acc:
                total_acc += 1
                if should_bet:
                    total_caught += 1
                prev_gaps.append(sa)

    if total_caught > 0 and total_bet > 0:
        mb = total_bet / total_caught
        bet_pct = total_bet / total_spins * 100
        lift = (total_caught / total_acc) / (total_bet / total_spins)
        print(f"  {label:<55} {total_caught:>3}/{total_acc:<4} {bet_pct:>5.1f}% {mb:>5.1f} {lift:>5.1f}x")
    else:
        print(f"  {label:<55} {total_caught:>3}/{total_acc if total_acc else '?':<4}   0 bet")

    return total_caught, total_acc, total_bet, total_spins


# ========================================================================
print(f"\n{'='*80}")
print(f"BASELINE")
print(f"{'='*80}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*80}")

simulate(lambda pg, sa, saacc, r: sa >= 130 and r >= 0.30, "Fixed 130 + rate>=0.30 (CURRENT)")
simulate(lambda pg, sa, saacc, r: sa >= 130, "Fixed 130 (no rate gate)")

# ========================================================================
print(f"\n{'='*80}")
print(f"1. SHIFT BASED ON PREVIOUS GAP")
print(f"   threshold = base - shift * (prev_gap - 100)")
print(f"{'='*80}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*80}")

for base in [120, 130, 140, 150]:
    for shift in [0.1, 0.2, 0.3, 0.4, 0.5]:
        def make_shift(b, s):
            def fn(pg, sa, saacc, r):
                prev = pg[-1] if pg else 100
                thresh = max(50, b - s * (prev - 100))
                return sa >= thresh and r >= 0.30
            return fn
        label = f"base={base} shift={shift:.1f}"
        simulate(make_shift(base, shift), label)

# ========================================================================
print(f"\n{'='*80}")
print(f"2. S/M/L PATTERN — different threshold per previous gap size")
print(f"   S=<80, M=80-130, L=>130")
print(f"{'='*80}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*80}")

# After S: expect longer gap -> higher threshold?
# After L: expect shorter gap -> lower threshold?
for s_thresh, m_thresh, l_thresh in [
    (130, 130, 130),  # baseline
    (140, 130, 110),  # after S raise, after L lower
    (150, 130, 100),  # more extreme
    (120, 130, 140),  # opposite: after S lower, after L raise
    (140, 130, 120),  # mild
    (150, 130, 120),  # mild v2
    (140, 120, 100),  # all shifted
    (110, 120, 130),  # progressive
    (130, 120, 110),  # progressive v2
    (150, 140, 100),  # extreme
    (160, 130, 90),   # very extreme
]:
    def make_sml(st, mt, lt):
        def fn(pg, sa, saacc, r):
            if not pg:
                thresh = mt  # default to medium
            elif pg[-1] < 80:
                thresh = st
            elif pg[-1] <= 130:
                thresh = mt
            else:
                thresh = lt
            return sa >= thresh and r >= 0.30
        return fn
    label = f"S->{s_thresh} M->{m_thresh} L->{l_thresh}"
    simulate(make_sml(s_thresh, m_thresh, l_thresh), label)

# ========================================================================
print(f"\n{'='*80}")
print(f"3. RUNNING AVERAGE — threshold based on avg of last N gaps")
print(f"   threshold = multiplier * running_avg")
print(f"{'='*80}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*80}")

for window in [2, 3, 5, 10]:
    for mult in [0.8, 0.9, 1.0, 1.1, 1.2, 1.3]:
        def make_avg(w, m):
            def fn(pg, sa, saacc, r):
                if len(pg) < 2:
                    thresh = 130
                else:
                    recent = pg[-w:] if len(pg) >= w else pg
                    avg = sum(recent) / len(recent)
                    thresh = max(50, int(avg * m))
                return sa >= thresh and r >= 0.30
            return fn
        label = f"window={window} mult={mult:.1f}"
        simulate(make_avg(window, mult), label)

# ========================================================================
print(f"\n{'='*80}")
print(f"4. STREAK DETECTION — adjust after consecutive S or L gaps")
print(f"{'='*80}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*80}")

for streak_len in [2, 3]:
    for short_adj, long_adj in [(20, -20), (30, -30), (40, -40), (-20, 20), (-30, 30)]:
        def make_streak(sl, sa, la):
            def fn(pg, spin, saacc, r):
                thresh = 130
                if len(pg) >= sl:
                    recent = pg[-sl:]
                    if all(g < 80 for g in recent):
                        thresh += sa  # streak of shorts
                    elif all(g > 130 for g in recent):
                        thresh += la  # streak of longs
                return spin >= thresh and r >= 0.30
            return fn
        label = f"streak>={streak_len} short_adj={short_adj:+d} long_adj={long_adj:+d}"
        simulate(make_streak(streak_len, short_adj, long_adj), label)

# ========================================================================
print(f"\n{'='*80}")
print(f"5. DEBT-BASED — cumulative over/under shifts threshold")
print(f"   debt += (gap - 100); threshold = base - debt * factor")
print(f"{'='*80}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*80}")

for base in [130, 140]:
    for center in [90, 100, 110]:
        for factor in [0.1, 0.2, 0.3, 0.5]:
            def make_debt(b, c, f):
                def fn(pg, sa, saacc, r):
                    debt = sum(g - c for g in pg)
                    thresh = max(50, int(b - debt * f))
                    return sa >= thresh and r >= 0.30
                return fn
            label = f"base={base} center={center} factor={factor:.1f}"
            simulate(make_debt(base, center, factor), label)

# ========================================================================
print(f"\n{'='*80}")
print(f"6. EWMA — exponentially weighted moving average")
print(f"   threshold = multiplier * ewma(gaps)")
print(f"{'='*80}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*80}")

for alpha in [0.1, 0.2, 0.3, 0.5]:
    for mult in [0.9, 1.0, 1.1, 1.2, 1.3]:
        def make_ewma(a, m):
            def fn(pg, sa, saacc, r):
                if not pg:
                    thresh = 130
                else:
                    ewma = pg[0]
                    for g in pg[1:]:
                        ewma = a * g + (1 - a) * ewma
                    thresh = max(50, int(ewma * m))
                return sa >= thresh and r >= 0.30
            return fn
        label = f"alpha={alpha:.1f} mult={mult:.1f}"
        simulate(make_ewma(alpha, mult), label)

# ========================================================================
print(f"\n{'='*80}")
print(f"7. RATE SLOPE — threshold based on how fast accum rate is climbing")
print(f"   If rate is climbing steeply, lower threshold (triple imminent)")
print(f"{'='*80}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*80}")

# Can't easily do rate slope from sa_acc/sa_spins alone since it's cumulative
# But we can use: if rate > high_gate at fewer spins, bet earlier
for early_spins, early_gate in [(100, 0.35), (110, 0.33), (90, 0.38), (80, 0.40), (100, 0.32)]:
    def make_rate_slope(es, eg):
        def fn(pg, sa, saacc, r):
            # Normal: sa >= 130 and rate >= 0.30
            # Early: sa >= early_spins and rate >= early_gate
            return (sa >= 130 and r >= 0.30) or (sa >= es and r >= eg)
        return fn
    label = f"normal OR (spins>={early_spins} + rate>={early_gate:.2f})"
    simulate(make_rate_slope(early_spins, early_gate), label)

# ========================================================================
print(f"\n{'='*80}")
print(f"8. VARIABLE RATE GATE — adjust rate gate based on spin count")
print(f"   Higher spins = lower rate needed (pity timer more desperate)")
print(f"{'='*80}")
print(f"  {'Strategy':<55} {'Caught':>8} {'Bet%':>6} {'MB/H':>6} {'Lift':>6}")
print(f"  {'-'*80}")

for base_spins, base_gate, gate_decay in [
    (130, 0.30, 0.001),   # rate gate drops 0.001 per spin past 130
    (130, 0.30, 0.002),
    (130, 0.30, 0.005),
    (120, 0.32, 0.001),
    (120, 0.32, 0.002),
    (110, 0.35, 0.001),
    (110, 0.35, 0.002),
    (100, 0.38, 0.001),
    (100, 0.38, 0.002),
]:
    def make_variable_gate(bs, bg, gd):
        def fn(pg, sa, saacc, r):
            if sa < bs:
                return False
            adjusted_gate = max(0.20, bg - gd * (sa - bs))
            return r >= adjusted_gate
        return fn
    label = f"spins>={base_spins} gate={base_gate:.2f}-{gate_decay:.3f}*(sa-{base_spins})"
    simulate(make_variable_gate(base_spins, base_gate, gate_decay), label)

print(f"\nDone!", flush=True)
