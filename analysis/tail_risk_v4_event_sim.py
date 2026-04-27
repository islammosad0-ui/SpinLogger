"""Event-aware mission-ladder sim with v4 champion + best ladder added.

Reuses the exact ladder / mechanics from analysis/nuclear/Old/28_event_aware_sim.py:
  - Currency is SPINS (bet X deducts X from bankroll)
  - ACC points per spin: 10 * bet if real ACC triple, else acc_count * bet
  - Mission clears when cumulative mission_pts >= threshold; reward added to bankroll
  - No cycling: if session runs out of real recorded spins, end as OUT OF DATA

New strategy `v4_ladder`:
  - Policy fires when v4 K=5 hazard `p_y_acc_next5 >= dyn_aggr_thr(t)` AND t in [15,100]
  - Ladder position counts only fires (bet>1). Bet-1 idle spins don't advance it.
  - Ladder resets when the v4 cycle_id changes (i.e. after a real VT).

Ladder:
  Fires 1-10  -> bet 1
  Fires 11-25 -> bet 100
  Fires 26-40 -> bet 2,500
  Fires 41+   -> bet 20,000

Inputs:
  - predictions CSV: spin_predictions_all_combos.csv
  - raw spin CSVs from data/<account>/ to recover triple/acc_count/etc.

Output: V4_EVENT_SIM_REPORT.md
"""

from __future__ import annotations

import argparse
import csv
from collections import deque
from datetime import datetime
from pathlib import Path

import pandas as pd


LADDER_A = [
    (7,120),(90,200),(225,800),(800,1700),(1200,3100),(2400,6000),(4800,11000),
    (10000,20000),(20000,40000),(30000,60000),(45000,85000),(70000,125000),
    (100000,175000),(150000,250000),(200000,300000),(250000,350000),(300000,400000),
    (350000,450000),(400000,500000),(450000,550000),(500000,600000),(550000,650000),
]
LADDER_B = [
    (1500,1100),(3000,2700),(8500,8100),(18000,19000),(24000,27000),(36000,46000),
    (51000,68000),(75000,107500),(105000,162500),(150000,230000),(225000,337500),
    (300000,472500),(450000,540000),(600000,675000),(750000,810000),(1050000,1000000),
    (1200000,1200000),(1500000,1400000),(1700000,1800000),(2100000,2100000),
]

REAL_TRIPLES = {'accumulation','spins','attack','steal','shield'}


def _dyn_aggr_threshold(t: int) -> float:
    if t > 100: return 0.10
    if t >= 70: return 0.03
    if t >= 50: return 0.04
    if t >= 30: return 0.05
    if t >= 15: return 0.08
    return 0.99  # effectively never fire outside window


def v4_ladder_bet(fires_in_cycle: int) -> int:
    """fires_in_cycle is 1-indexed. Bets snapped to legal game values:
    {1, 2, 3, 15, 50, 400, 1500, 6000, 20000}."""
    if fires_in_cycle <= 10: return 1
    if fires_in_cycle <= 25: return 50
    if fires_in_cycle <= 40: return 1_500
    return 20_000


# Ensemble rules (copy from 28_event_aware_sim.py) for baseline comparison.
HAMMER_LADDER = [(15,25),(50,50),(400,75),(1500,93),(6000,None)]
ENSEMBLE_BUMP_BET = 6000


def gap_class(L):
    if L is None: return 'NONE'
    if L <= 39: return 'XS'
    if L <= 105: return 'S'
    if L <= 160: return 'M'
    return 'L'


def rule_steal_t65(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if not (65 <= sp <= 105): return False
    return (s['sa_acc']/sp) >= 0.34 if sp else False
def rule_steal_t130(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if sp < 130: return False
    return (s['sa_acc']/sp) >= 0.28
def rule_steal_t150(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if sp < 150: return False
    return (s['sa_acc']/sp) >= 0.30
def rule_shield_t150(s):
    if s['prev_real_triple'] != 'shield': return False
    sp = s['sa_spins']
    if sp < 150: return False
    return (s['sa_acc']/sp) >= 0.30
def rule_quiet_zone(s):
    if s['sa_spins'] < 130: return False
    return s['last10_sum'] <= 10
def rule_dg_t130(s):
    sp = s['sa_spins']
    if not (130 <= sp <= 155): return False
    if (s['sa_acc']/sp) < 0.28: return False
    return (s['sa_spn']/sp) >= 0.24
def rule_early_s(s):
    if gap_class(s['prev_gap_length']) not in ('M','L'): return False
    sp = s['sa_spins']
    if not (60 <= sp <= 105): return False
    return s['last10_sum'] <= 10

RULES = [
    ('steal_t65', rule_steal_t65), ('steal_t130', rule_steal_t130),
    ('steal_t150', rule_steal_t150), ('shield_t150', rule_shield_t150),
    ('quiet_zone', rule_quiet_zone), ('dg_t130', rule_dg_t130),
    ('early_s', rule_early_s),
]


def ensemble_fires(state) -> bool:
    return any(fn(state) for _, fn in RULES)


def safe_int(x, default=0):
    try: return int(x)
    except (ValueError, TypeError): return default


def classify_triple(r1, r2, r3, is_triple_str):
    if str(is_triple_str).lower() != 'true': return None
    if r1 == r2 == r3 and r1 in REAL_TRIPLES: return r1
    return None


def load_session_spins(raw_csvs_by_session: dict[str, list[str]], session_id: str,
                       preds_for_session: pd.DataFrame, proba_col: str) -> list[dict]:
    """Iterate all in-event raw spins in seq order, attach v4 preds where available.
    VT-landing spins have no pred row (the model predicts only on non-VT spins), so
    for those we set p=0 (policy won't fire) but still include them so the
    ensemble/hammer/v4 strategies can catch on bump."""
    csv_files = raw_csvs_by_session.get(session_id, [])
    # Build a pred lookup by seq
    preds_by_seq: dict[int, dict] = {}
    for _, r in preds_for_session.iterrows():
        preds_by_seq[int(r['seq'])] = {
            'cycle_id': int(r['cycle_id']),
            't': int(r['t']),
            'p': float(r[proba_col]),
        }

    spins = []
    last_cycle = None
    synth_cycle = -1  # fallback cycle id that advances on every ACC triple post-pred
    for f in csv_files:
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            continue
        rows.sort(key=lambda r: safe_int(r.get('seq', 0)))
        for raw in rows:
            if str(raw.get('gae_segment', '')).strip() == '':
                continue
            seq = safe_int(raw.get('seq', 0))
            if not seq:
                continue
            reel1 = raw.get('reel_1',''); reel2 = raw.get('reel_2',''); reel3 = raw.get('reel_3','')
            triple = classify_triple(reel1, reel2, reel3, raw.get('is_triple',''))
            pr = preds_by_seq.get(seq)
            if pr is not None:
                cycle_id = pr['cycle_id']; t = pr['t']; p = pr['p']
                last_cycle = cycle_id
            else:
                # VT-landing spin or post-last-cycle tail: keep last-known cycle so
                # the v4 ladder can continue through the VT and catch it.
                cycle_id = last_cycle if last_cycle is not None else synth_cycle
                t = 0; p = 0.0
            spins.append({
                'seq': seq,
                'cycle_id': cycle_id,
                't': t,
                'p': p,
                'triple': triple,
                'acc_count': safe_int(raw.get('acc_count', 0)),
                'atk_count': safe_int(raw.get('atk_count', 0)),
                'stl_count': safe_int(raw.get('stl_count', 0)),
                'shd_count': safe_int(raw.get('shd_count', 0)),
                'spn_count': safe_int(raw.get('spn_count', 0)),
                'sa_spins': safe_int(raw.get('sa_spins', 0)),
                'sa_acc':   safe_int(raw.get('sa_acc',   0)),
                'sa_spn':   safe_int(raw.get('sa_spn',   0)),
            })
            # Force cycle rollover on any ACC triple so the v4 ladder resets post-catch.
            if triple == 'accumulation':
                synth_cycle -= 1
                last_cycle = synth_cycle
    return spins


def simulate(spins: list[dict], bankroll0: int, ladder, strategy: str,
             policy_threshold: float | None = None,
             policy_t_min: int = 15, policy_t_max: int = 100) -> dict:
    bankroll = bankroll0
    mission_idx = 0
    mission_pts = 0
    pulls = cost_total = points_total = rewards_total = bumps = catches_on_bump = 0

    # Ensemble state
    last10 = deque(maxlen=10)
    prev_real_triple = None
    prev_gap_length = None
    # Hammer state
    hammer_level = 0
    hammers = 0
    # v4 ladder state
    v4_fires_this_cycle = 0
    v4_last_cycle = None

    end_reason = 'cleared_all'
    walked_all = True

    for s in spins:
        # Handle cycle rollover for v4 ladder
        if s['cycle_id'] != v4_last_cycle:
            v4_fires_this_cycle = 0
            v4_last_cycle = s['cycle_id']

        # Decide bet
        if strategy == 'pure_1x':
            bet = 1
        elif strategy == 'pure_6000x':
            bet = 6000
        elif strategy == 'pure_hammer':
            bet = HAMMER_LADDER[hammer_level][0]
        elif strategy == 'pure_ensemble':
            state = {'sa_spins': s['sa_spins'], 'sa_acc': s['sa_acc'], 'sa_spn': s['sa_spn'],
                     'prev_real_triple': prev_real_triple, 'prev_gap_length': prev_gap_length,
                     'last10_sum': sum(last10)}
            bet = ENSEMBLE_BUMP_BET if ensemble_fires(state) else 1
        elif strategy == 'hybrid':
            state = {'sa_spins': s['sa_spins'], 'sa_acc': s['sa_acc'], 'sa_spn': s['sa_spn'],
                     'prev_real_triple': prev_real_triple, 'prev_gap_length': prev_gap_length,
                     'last10_sum': sum(last10)}
            base = HAMMER_LADDER[hammer_level][0]
            bet = max(base, ENSEMBLE_BUMP_BET) if ensemble_fires(state) else base
        elif strategy == 'v4_ladder':
            t = s['t']; p = s['p']
            # Commit semantics: once the policy fires in a cycle, keep firing through
            # the VT spin (p=0 on VT row) so we can actually catch it at the ladder bet.
            if policy_threshold is None:
                policy_on = (policy_t_min <= t <= policy_t_max and p >= _dyn_aggr_threshold(t))
            else:
                policy_on = (policy_t_min <= t <= policy_t_max and p >= policy_threshold)
            if policy_on or v4_fires_this_cycle > 0:
                v4_fires_this_cycle += 1
                bet = v4_ladder_bet(v4_fires_this_cycle)
            else:
                bet = 1
        else:
            raise ValueError(strategy)

        if bankroll < bet:
            end_reason = 'bankrupt'
            walked_all = False
            break

        bankroll -= bet
        cost_total += bet
        pulls += 1

        is_acc_triple = (s['triple'] == 'accumulation')
        pts = 10 * bet if is_acc_triple else s['acc_count'] * bet
        points_total += pts
        mission_pts += pts

        if bet > 1:
            bumps += 1
            if is_acc_triple:
                catches_on_bump += 1

        # Mission clears
        while mission_idx < len(ladder) and mission_pts >= ladder[mission_idx][0]:
            thresh, reward = ladder[mission_idx]
            mission_pts -= thresh
            bankroll += reward
            rewards_total += reward
            mission_idx += 1
        if mission_idx >= len(ladder):
            end_reason = 'cleared_all'
            walked_all = False
            break

        # State updates for ensemble/hammer
        hammers += s['atk_count']
        if hammer_level < len(HAMMER_LADDER) - 1 and hammers >= (HAMMER_LADDER[hammer_level][1] or 10**9):
            hammer_level += 1
        sym_total = (s['atk_count'] + s['stl_count'] + s['shd_count']
                     + s['spn_count'] + s['acc_count'])
        last10.append(sym_total)
        if s['triple'] is not None:
            prev_real_triple = s['triple']
        if is_acc_triple:
            prev_gap_length = s['sa_spins']
            hammer_level = 0
            hammers = 0

    if walked_all:
        end_reason = 'data_exhausted'

    return {
        'strategy': strategy, 'pulls': pulls, 'cost_total': cost_total,
        'points_total': points_total, 'rewards_total': rewards_total,
        'bumps': bumps, 'catches_on_bump': catches_on_bump,
        'missions_cleared': mission_idx, 'missions_total': len(ladder),
        'final_bankroll': bankroll, 'final_mission_pts': mission_pts,
        'next_threshold': ladder[mission_idx][0] if mission_idx < len(ladder) else None,
        'cleared_all': mission_idx >= len(ladder), 'end_reason': end_reason,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--predictions-csv", required=True)
    p.add_argument("--out-dir", default=None)
    p.add_argument("--head", default="ACC", choices=("ACC", "ANY_VT", "SPN"),
                   help="Predictor head to drive the V4 ladder.")
    p.add_argument("--horizon", type=int, default=5, choices=(3, 5, 10),
                   help="Predictor horizon K.")
    p.add_argument("--threshold", type=float, default=None,
                   help="If set, policy fires when p >= threshold (replaces dyn_aggr schedule).")
    p.add_argument("--t-min", type=int, default=15)
    p.add_argument("--t-max", type=int, default=100)
    args = p.parse_args()

    head_to_token = {"ANY_VT": "any", "ACC": "acc", "SPN": "spn"}
    proba_col = f"p_y_{head_to_token[args.head]}_next{args.horizon}"

    preds_path = Path(args.predictions_csv)
    preds = pd.read_csv(preds_path)
    if proba_col not in preds.columns:
        raise SystemExit(f"Predictions CSV missing column {proba_col}. "
                         f"Available: {[c for c in preds.columns if c.startswith('p_')]}")
    policy_tag = (f"{args.head}_K{args.horizon}_thr{args.threshold:.2f}"
                  if args.threshold is not None
                  else f"{args.head}_K{args.horizon}_dynaggr")
    out_dir = (Path(args.out_dir) if args.out_dir
               else preds_path.parent / f"event_sim_{policy_tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Map each session_id to its raw CSV file. session_id format is "Account|filename.csv".
    def session_to_raw(sess_id: str) -> list[str]:
        acct, fname = sess_id.split('|', 1)
        return [f"data/{acct}/{fname}"]

    scenarios = [
        ("A: 100K start, 22-mission ladder", 100_000, LADDER_A),
        ("B: 299K start, 20-mission ladder", 299_000, LADDER_B),
    ]
    strategies = ['pure_1x', 'pure_ensemble', 'pure_hammer', 'hybrid', 'v4_ladder']
    strat_label = {
        'pure_1x': 'Pure 1x', 'pure_ensemble': 'Pure Ensemble',
        'pure_hammer': 'Pure Hammer', 'hybrid': 'Hybrid', 'v4_ladder': 'V4 Ladder',
    }

    policy_desc = (f"`p ≥ {args.threshold:.2f}`" if args.threshold is not None
                   else "`p ≥ dyn_aggr_thr(t)` (legacy schedule)")
    lines: list[str] = [
        "# V4 Event-Aware Mission Sim",
        "",
        f"- Predictions: `{preds_path}`",
        f"- Policy column: `{proba_col}` (head={args.head}, K={args.horizon})",
        f"- Policy: fire when `t ∈ [{args.t_min},{args.t_max}]` AND {policy_desc}",
        "- Currency: **spins** (bet X → bankroll -= X)",
        "- ACC points per spin: `10 * bet` on real ACC triple, else `acc_count * bet`",
        "- V4 ladder (legal bets only): fires 1-10 → 1x, 11-25 → 50x, 26-40 → 1500x, 41+ → 20000x. Only policy-fires advance the ladder.",
        "",
    ]

    sessions_by_account: dict[str, list[str]] = {}
    for sid in preds['session_id'].unique():
        acct = sid.split('|', 1)[0]
        sessions_by_account.setdefault(acct, []).append(sid)

    for scen_name, bankroll0, ladder in scenarios:
        lines.append(f"\n## Scenario {scen_name}\n")
        lines.append("| Account | Session | Strategy | Verdict | Missions | %next | Pulls | Bumps | Catch-on-bump | Final bankroll |")
        lines.append("| :------ | :------ | :------- | :------ | -------: | ----: | ----: | ----: | ------------: | -------------: |")
        for acct in sorted(sessions_by_account.keys()):
            for sess_id in sessions_by_account[acct]:
                session_preds = preds[preds['session_id'] == sess_id].sort_values('seq')
                session_preds = session_preds.drop_duplicates('seq', keep='first')
                raw_files = session_to_raw(sess_id)
                spins = load_session_spins({sess_id: raw_files}, sess_id, session_preds, proba_col)
                if not spins:
                    continue
                sess_short = sess_id.split('|', 1)[1].replace('spin_history_', '').replace('.csv', '')
                for strat in strategies:
                    r = simulate(spins, bankroll0, ladder, strat,
                                 policy_threshold=args.threshold,
                                 policy_t_min=args.t_min, policy_t_max=args.t_max)
                    verdict = ('CLEAR ALL' if r['cleared_all']
                               else 'OUT OF DATA' if r['end_reason'] == 'data_exhausted'
                               else 'BANKRUPT')
                    pct = (r['final_mission_pts']/r['next_threshold']*100) if r['next_threshold'] else 0
                    lines.append(
                        f"| {acct} | {sess_short} | {strat_label[strat]} | {verdict} | "
                        f"{r['missions_cleared']}/{r['missions_total']} | "
                        f"{pct:.0f}% | {r['pulls']:,} | {r['bumps']} | "
                        f"{r['catches_on_bump']} | {r['final_bankroll']:,} |"
                    )
                lines.append("|  |  |  |  |  |  |  |  |  |  |")

    out_path = out_dir / "V4_EVENT_SIM_REPORT.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
