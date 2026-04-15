"""
STRATEGY SIMULATOR — ACC & SPN Triple Targeting
=================================================
Walk through data chronologically, evaluate rules, track KPIs.
"""

import pandas as pd
import numpy as np
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import warnings, glob, os, sys, io

warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sns.set_theme(style='whitegrid', font_scale=0.85)
OUT = os.path.dirname(os.path.abspath(__file__))

# ── Load ──
def load_all():
    files = sorted(glob.glob('data/*/spin_history*.csv'))
    files = [f for f in files if 'enriched' not in f and 'default' not in f]
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f, on_bad_lines='skip')
            df['account'] = f.split(os.sep)[1]
            frames.append(df)
        except: pass
    c = pd.concat(frames, ignore_index=True)
    c = c.sort_values(['account','seq']).drop_duplicates(subset=['account','seq'], keep='last').reset_index(drop=True)
    return c

print("Loading...")
df = load_all()

# Tags
df['triple_type'] = 'none'
mask_t = df['is_triple'] == True
for sym in ['attack','steal','shield','coin','spins','goldSack','accumulation']:
    df.loc[mask_t & (df['reel_1'] == sym), 'triple_type'] = f'3x_{sym}'
df['is_acc'] = df['triple_type'] == '3x_accumulation'
df['is_spn'] = df['triple_type'] == '3x_spins'

# Helpers
def has_sym(row, sym):
    return row['reel_1'] == sym or row['reel_2'] == sym or row['reel_3'] == sym

def pair_sym(row):
    r = [row['reel_1'], row['reel_2'], row['reel_3']]
    if r[0]==r[1]: return r[0]
    if r[1]==r[2]: return r[1]
    if r[0]==r[2]: return r[0]
    return 'none'

def n_match(row):
    r = [row['reel_1'], row['reel_2'], row['reel_3']]
    if r[0]==r[1]==r[2]: return 3
    if r[0]==r[1] or r[1]==r[2] or r[0]==r[2]: return 2
    return 1

print(f"  {len(df):,} spins | ACC: {df['is_acc'].sum()} | SPN: {df['is_spn'].sum()}")

# ══════════════════════════════════════════════════════════════
# STRATEGY DEFINITIONS
# ══════════════════════════════════════════════════════════════
# Each strategy is: (name, target_col, condition_fn)
# condition_fn(row, prev_row) -> True if we should "bet" on this spin
# "bet" means: we are actively watching/waiting for the target triple

def make_strategies():
    strategies = []

    # ─── ACC STRATEGIES ───
    # Baseline: always bet
    strategies.append(('ACC | Always (baseline)', 'is_acc',
        lambda r, p: True))

    # Pity timer thresholds
    for thresh in [20, 30, 40, 60, 80, 100, 120]:
        strategies.append((f'ACC | sa_acc >= {thresh}', 'is_acc',
            lambda r, p, t=thresh: r['sa_acc'] >= t))

    # High bet
    strategies.append(('ACC | bet >= 50', 'is_acc',
        lambda r, p: r['bet_multiplier'] >= 50))
    strategies.append(('ACC | bet >= 400', 'is_acc',
        lambda r, p: r['bet_multiplier'] >= 400))

    # Pity + high bet combos
    strategies.append(('ACC | sa_acc>=20 + bet>=50', 'is_acc',
        lambda r, p: r['sa_acc'] >= 20 and r['bet_multiplier'] >= 50))
    strategies.append(('ACC | sa_acc>=40 + bet>=50', 'is_acc',
        lambda r, p: r['sa_acc'] >= 40 and r['bet_multiplier'] >= 50))
    strategies.append(('ACC | sa_acc>=60 + bet>=50', 'is_acc',
        lambda r, p: r['sa_acc'] >= 60 and r['bet_multiplier'] >= 50))

    # Previous result = spins
    strategies.append(('ACC | prev_result=spins', 'is_acc',
        lambda r, p: p is not None and p['spin_result'] == 'spins'))

    # sa_acc + goldSack visible
    strategies.append(('ACC | sa_acc>=40 + has_goldSack', 'is_acc',
        lambda r, p: r['sa_acc'] >= 40 and has_sym(r, 'goldSack')))
    strategies.append(('ACC | sa_acc>=60 + has_goldSack', 'is_acc',
        lambda r, p: r['sa_acc'] >= 60 and has_sym(r, 'goldSack')))
    strategies.append(('ACC | sa_acc>=80 + has_goldSack', 'is_acc',
        lambda r, p: r['sa_acc'] >= 80 and has_sym(r, 'goldSack')))
    strategies.append(('ACC | sa_acc>=120 + has_goldSack', 'is_acc',
        lambda r, p: r['sa_acc'] >= 120 and has_sym(r, 'goldSack')))

    # sa_acc + steal result
    strategies.append(('ACC | sa_acc>=60 + result=steal', 'is_acc',
        lambda r, p: r['sa_acc'] >= 60 and r['spin_result'] == 'steal'))

    # sa_acc + any_pair
    strategies.append(('ACC | sa_acc>=60 + any_pair', 'is_acc',
        lambda r, p: r['sa_acc'] >= 60 and n_match(r) >= 2))
    strategies.append(('ACC | sa_acc>=120 + any_pair', 'is_acc',
        lambda r, p: r['sa_acc'] >= 120 and n_match(r) >= 2))

    # r3_idx based
    strategies.append(('ACC | r3_idx in [1,3,6]', 'is_acc',
        lambda r, p: r.get('r3_idx', -99) in [1, 3, 6]))
    strategies.append(('ACC | sa_acc>=20 + r3_idx in [1,3,6]', 'is_acc',
        lambda r, p: r['sa_acc'] >= 20 and r.get('r3_idx', -99) in [1, 3, 6]))

    # ─── SPN STRATEGIES ───
    strategies.append(('SPN | Always (baseline)', 'is_spn',
        lambda r, p: True))

    for thresh in [20, 30, 40, 60, 80]:
        strategies.append((f'SPN | sa_spn >= {thresh}', 'is_spn',
            lambda r, p, t=thresh: r['sa_spn'] >= t))

    # After steal
    strategies.append(('SPN | prev_result=steal', 'is_spn',
        lambda r, p: p is not None and p['spin_result'] == 'steal'))

    # sa_spn + goldSack
    strategies.append(('SPN | sa_spn>=60 + has_goldSack', 'is_spn',
        lambda r, p: r['sa_spn'] >= 60 and has_sym(r, 'goldSack')))
    strategies.append(('SPN | sa_spn>=80 + has_goldSack', 'is_spn',
        lambda r, p: r['sa_spn'] >= 80 and has_sym(r, 'goldSack')))
    strategies.append(('SPN | sa_spn>=100 + has_goldSack', 'is_spn',
        lambda r, p: r['sa_spn'] >= 100 and has_sym(r, 'goldSack')))

    # sa_spn + pair_spins
    strategies.append(('SPN | sa_spn>=60 + pair_spins', 'is_spn',
        lambda r, p: r['sa_spn'] >= 60 and n_match(r) >= 2 and pair_sym(r) == 'spins'))

    # r3_idx
    strategies.append(('SPN | r3_idx in [1,5]', 'is_spn',
        lambda r, p: r.get('r3_idx', -99) in [1, 5]))
    strategies.append(('SPN | sa_spn>=20 + r3_idx in [1,5]', 'is_spn',
        lambda r, p: r['sa_spn'] >= 20 and r.get('r3_idx', -99) in [1, 5]))

    # Anti-steal at high drought
    strategies.append(('SPN | sa_spn>=60 + NO steal', 'is_spn',
        lambda r, p: r['sa_spn'] >= 60 and not has_sym(r, 'steal')))

    # Combined best
    strategies.append(('SPN | sa_spn>=80 + bet>=50', 'is_spn',
        lambda r, p: r['sa_spn'] >= 80 and r['bet_multiplier'] >= 50))

    return strategies


# ══════════════════════════════════════════════════════════════
# RUN SIMULATION
# ══════════════════════════════════════════════════════════════
strategies = make_strategies()
results = []

print(f"\nRunning {len(strategies)} strategies across {df['account'].nunique()} accounts...")

for strat_name, target_col, cond_fn in strategies:
    total_spins = 0
    total_bets = 0      # spins where condition is True
    total_hits = 0      # bets that ARE the target triple
    total_targets = 0   # total target triples in data
    total_caught = 0    # target triples where we were betting
    total_missed = 0    # target triples where we were NOT betting

    # Track consecutive bets without a hit (max drought while betting)
    max_bet_drought = 0
    current_bet_drought = 0
    bet_droughts = []  # all completed bet droughts

    # Track lookback: how many spins before the triple did the rule first trigger?
    lookback_distances = []

    # Per-account simulation
    for acct in df['account'].unique():
        adf = df[df['account'] == acct].sort_values('seq').reset_index(drop=True)
        prev_row = None

        # Track: when did rule last trigger relative to next target
        rule_active_since = None

        for i, row in adf.iterrows():
            total_spins += 1
            is_target = bool(row[target_col])

            if is_target:
                total_targets += 1

            try:
                active = cond_fn(row, prev_row)
            except:
                active = False

            if active:
                total_bets += 1
                current_bet_drought += 1

                if is_target:
                    total_hits += 1
                    total_caught += 1
                    bet_droughts.append(current_bet_drought)
                    current_bet_drought = 0
                    if rule_active_since is not None:
                        lookback_distances.append(i - rule_active_since)
                    rule_active_since = None

                if rule_active_since is None:
                    rule_active_since = i
            else:
                if current_bet_drought > 0:
                    max_bet_drought = max(max_bet_drought, current_bet_drought)
                    current_bet_drought = 0
                rule_active_since = None

                if is_target:
                    total_missed += 1

            prev_row = row

        # End of account
        if current_bet_drought > 0:
            max_bet_drought = max(max_bet_drought, current_bet_drought)

    # Compute KPIs
    bet_pct = total_bets / total_spins * 100 if total_spins > 0 else 0
    catch_rate = total_caught / total_targets * 100 if total_targets > 0 else 0
    miss_rate = total_missed / total_targets * 100 if total_targets > 0 else 0
    precision = total_hits / total_bets * 100 if total_bets > 0 else 0
    bets_per_hit = total_bets / total_hits if total_hits > 0 else float('inf')
    baseline_bets_per_hit = total_spins / total_targets if total_targets > 0 else float('inf')
    efficiency = baseline_bets_per_hit / bets_per_hit if bets_per_hit > 0 and bets_per_hit != float('inf') else 0
    avg_bet_drought = np.mean(bet_droughts) if bet_droughts else float('inf')
    med_bet_drought = np.median(bet_droughts) if bet_droughts else float('inf')

    results.append({
        'Strategy': strat_name,
        'Target': target_col.replace('is_', '').upper(),
        'Total Spins': total_spins,
        'Bets': total_bets,
        'Bet%': bet_pct,
        'Targets': total_targets,
        'Caught': total_caught,
        'Missed': total_missed,
        'Catch%': catch_rate,
        'Hits': total_hits,
        'Precision%': precision,
        'Bets/Hit': bets_per_hit,
        'Baseline B/H': baseline_bets_per_hit,
        'Efficiency': efficiency,
        'Max Drought': max_bet_drought,
        'Avg Drought': avg_bet_drought,
        'Med Drought': med_bet_drought,
    })

rdf = pd.DataFrame(results)

# ══════════════════════════════════════════════════════════════
# REPORT
# ══════════════════════════════════════════════════════════════
report = []
report.append("=" * 120)
report.append("STRATEGY SIMULATION REPORT")
report.append("=" * 120)
report.append(f"Data: {len(df):,} spins | ACC triples: {df['is_acc'].sum()} | SPN triples: {df['is_spn'].sum()}")
report.append(f"Accounts: {df['account'].nunique()} ({', '.join(df['account'].unique())})")
report.append("")
report.append("KPI DEFINITIONS:")
report.append("  Bet%      = % of all spins where rule is active (lower = more selective)")
report.append("  Catch%    = % of target triples caught while rule active (higher = fewer missed)")
report.append("  Precision = % of active spins that ARE the target triple (higher = less waste)")
report.append("  Bets/Hit  = avg spins betting before catching one triple (lower = more efficient)")
report.append("  Efficiency= how many X better than random (Baseline_B/H / Bets/Hit)")
report.append("  Max Drought = longest streak of active bets without catching target")
report.append("  Avg/Med Drought = avg/median bets between consecutive catches")
report.append("")

for target_label in ['ACC', 'SPN']:
    sub = rdf[rdf['Target'] == target_label].copy()
    report.append("")
    report.append("#" * 120)
    report.append(f"  {target_label} TRIPLE STRATEGIES")
    report.append("#" * 120)
    report.append("")

    # Sort by efficiency
    sub_sorted = sub.sort_values('Efficiency', ascending=False)

    report.append(f"{'Strategy':<45s} | {'Bet%':>5s} | {'Catch%':>6s} | {'Prec%':>6s} | {'B/Hit':>6s} | {'Effic':>5s} | {'MaxDr':>5s} | {'AvgDr':>6s} | {'MedDr':>6s} | {'Caught':>6s}/{' Targets':>4s}")
    report.append("-" * 140)

    for _, r in sub_sorted.iterrows():
        bh = f"{r['Bets/Hit']:.1f}" if r['Bets/Hit'] != float('inf') else "inf"
        eff = f"{r['Efficiency']:.2f}" if r['Efficiency'] > 0 else "0.00"
        md = f"{r['Max Drought']:.0f}"
        ad = f"{r['Avg Drought']:.1f}" if r['Avg Drought'] != float('inf') else "inf"
        mdd = f"{r['Med Drought']:.1f}" if r['Med Drought'] != float('inf') else "inf"

        report.append(
            f"{r['Strategy']:<45s} | {r['Bet%']:5.1f} | {r['Catch%']:6.1f} | {r['Precision%']:6.3f} | "
            f"{bh:>6s} | {eff:>5s} | {md:>5s} | {ad:>6s} | {mdd:>6s} | "
            f"{r['Caught']:6.0f} / {r['Targets']:4.0f}"
        )

    # Best trade-offs
    report.append("")
    report.append(f"  BEST EFFICIENCY (least waste per hit):")
    best_eff = sub_sorted[sub_sorted['Caught'] >= 5].head(5)
    for _, r in best_eff.iterrows():
        report.append(f"    {r['Strategy']:<45s}  Eff={r['Efficiency']:.2f}x  Catch={r['Catch%']:.1f}%  B/Hit={r['Bets/Hit']:.1f}")

    report.append(f"\n  BEST CATCH RATE (fewest missed, Catch% > 50%):")
    best_catch = sub_sorted[sub_sorted['Catch%'] >= 50].sort_values('Efficiency', ascending=False).head(5)
    for _, r in best_catch.iterrows():
        report.append(f"    {r['Strategy']:<45s}  Catch={r['Catch%']:.1f}%  Eff={r['Efficiency']:.2f}x  B/Hit={r['Bets/Hit']:.1f}")

    report.append(f"\n  BEST BALANCED (Catch% >= 30% AND Efficiency >= 1.5x):")
    balanced = sub_sorted[(sub_sorted['Catch%'] >= 30) & (sub_sorted['Efficiency'] >= 1.5)]
    if len(balanced) == 0:
        balanced = sub_sorted[(sub_sorted['Catch%'] >= 20) & (sub_sorted['Efficiency'] >= 1.2)]
    for _, r in balanced.head(5).iterrows():
        report.append(f"    {r['Strategy']:<45s}  Catch={r['Catch%']:.1f}%  Eff={r['Efficiency']:.2f}x  B/Hit={r['Bets/Hit']:.1f}")

    report.append("")

# ── Pareto frontier analysis ──
report.append("\n" + "=" * 120)
report.append("PARETO FRONTIER — Catch% vs Efficiency trade-off")
report.append("=" * 120)
report.append("(Strategies on the frontier cannot be improved on one axis without losing on the other)\n")

for target_label in ['ACC', 'SPN']:
    sub = rdf[rdf['Target'] == target_label].copy()
    sub = sub[sub['Caught'] >= 3]  # min catches
    sub = sub.sort_values('Catch%', ascending=False)

    pareto = []
    max_eff = 0
    for _, r in sub.iterrows():
        if r['Efficiency'] >= max_eff:
            pareto.append(r)
            max_eff = r['Efficiency']

    report.append(f"\n  {target_label} PARETO FRONTIER:")
    for r in pareto:
        report.append(f"    {r['Strategy']:<45s}  Catch={r['Catch%']:5.1f}%  Eff={r['Efficiency']:.2f}x  B/Hit={r['Bets/Hit']:.1f}  Caught={int(r['Caught'])}/{int(r['Targets'])}")

report.append("")

# Write report
full_report = "\n".join(report)
report_path = os.path.join(OUT, 'STRATEGY_SIM_REPORT.txt')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(full_report)

print(full_report)

# ══════════════════════════════════════════════════════════════
# VISUALIZATIONS
# ══════════════════════════════════════════════════════════════
for target_label in ['ACC', 'SPN']:
    sub = rdf[rdf['Target'] == target_label].copy()
    sub = sub[sub['Strategy'] != f'{target_label} | Always (baseline)']
    sub = sub[sub['Caught'] >= 3]

    fig, axes = plt.subplots(2, 2, figsize=(18, 14))

    # 1. Catch% vs Efficiency scatter
    ax = axes[0, 0]
    colors = sub['Efficiency'].values
    sc = ax.scatter(sub['Catch%'], sub['Efficiency'], c=colors, cmap='RdYlGn', s=80, edgecolors='black', linewidth=0.5)
    for _, r in sub.iterrows():
        name = r['Strategy'].replace(f'{target_label} | ', '')
        if r['Efficiency'] > 1.3 or r['Catch%'] > 60:
            ax.annotate(name, (r['Catch%'], r['Efficiency']), fontsize=5.5,
                       xytext=(3, 3), textcoords='offset points')
    ax.axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label='Random baseline')
    ax.set_xlabel('Catch Rate (%)')
    ax.set_ylabel('Efficiency (x baseline)')
    ax.set_title(f'{target_label} — Catch% vs Efficiency\n(top-right = best)')
    ax.legend()

    # 2. Bets/Hit bar chart (top strategies)
    ax = axes[0, 1]
    top = sub.nlargest(15, 'Efficiency')
    names = [s.replace(f'{target_label} | ', '') for s in top['Strategy']]
    baseline_bh = sub['Baseline B/H'].iloc[0] if len(sub) > 0 else 100
    ax.barh(range(len(top)), top['Bets/Hit'].values, color='steelblue', alpha=0.8)
    ax.axvline(x=baseline_bh, color='red', linestyle='--', label=f'Random ({baseline_bh:.0f})')
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(names, fontsize=7)
    ax.set_xlabel('Bets per Hit (lower = better)')
    ax.set_title(f'{target_label} — Bets/Hit (top 15 by efficiency)')
    ax.legend()
    ax.invert_yaxis()

    # 3. Catch% bar chart
    ax = axes[1, 0]
    top_catch = sub.nlargest(15, 'Catch%')
    names_c = [s.replace(f'{target_label} | ', '') for s in top_catch['Strategy']]
    colors_c = ['tomato' if e >= 1.5 else 'steelblue' for e in top_catch['Efficiency']]
    ax.barh(range(len(top_catch)), top_catch['Catch%'].values, color=colors_c, alpha=0.8)
    ax.set_yticks(range(len(top_catch)))
    ax.set_yticklabels(names_c, fontsize=7)
    ax.set_xlabel('Catch Rate (%)')
    ax.set_title(f'{target_label} — Catch Rate (red = eff >= 1.5x)')
    ax.invert_yaxis()

    # 4. Drought distribution for top strategies
    ax = axes[1, 1]
    top3 = sub.nlargest(3, 'Efficiency')
    for _, r in top3.iterrows():
        name = r['Strategy'].replace(f'{target_label} | ', '')
        ax.bar(name, r['Avg Drought'], color='steelblue', alpha=0.7, label='Avg')
        ax.bar(name, r['Max Drought'], color='tomato', alpha=0.3, label='Max')
    ax.set_ylabel('Bets')
    ax.set_title(f'{target_label} — Drought (avg vs max) for top 3')
    ax.tick_params(axis='x', rotation=30, labelsize=7)
    # Custom legend
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color='steelblue', alpha=0.7, label='Avg Drought'),
                       Patch(color='tomato', alpha=0.3, label='Max Drought')])

    plt.suptitle(f'{target_label} TRIPLE STRATEGY SIMULATION', fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(os.path.join(OUT, f'{target_label}_STRATEGY_SIM.png'), dpi=150)
    plt.close()

print(f"\nReport: {report_path}")
print(f"Charts: ACC_STRATEGY_SIM.png, SPN_STRATEGY_SIM.png")
print("\nDONE!")
