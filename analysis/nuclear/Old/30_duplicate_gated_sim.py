"""
Chunk 30: DUPLICATE-GATED bet simulator.

Motivation (2026-04-09):
  `analyze_reel_patterns.py` showed that ~59% of ACC triples and ~66% of SPN
  triples are preceded by a back-to-back duplicate reel tuple in the last 15
  spins before the hit. User hypothesis: take EVERY rule we have (v5, Islam,
  Islam-v2, high-mb, feature-leaking — all of them) and instead of betting
  the moment a rule fires, DELAY betting until we physically observe a
  back-to-back duplicate. Then bet high for 7 pulls. If during those 7 pulls
  we see an intermediate win triple (steal/shield/attack), drop to 1x for
  3-5 pulls, then resume bet-high.

State machine per account:
  IDLE
    --(any rule fires)-->                             ARMED
  ARMED
    --(prev spin duplicates spin before it)-->        BET_HIGH (counter=7)
    --(target triple lands)-->                        IDLE   (lost arm)
  BET_HIGH (counter>0)
    --(target triple lands)-->                        IDLE   (CATCH)
    --(steal/shield/attack triple lands)-->           MINI_PAUSE (counter=4)
    --(counter reaches 0)-->                          IDLE
  MINI_PAUSE (counter>0)
    --(target triple lands)-->                        IDLE   (miss — we were 1x)
    --(counter reaches 0)-->                          BET_HIGH (counter=7, fresh)

Causality:
  The bet for spin i is decided using only information observable at the END
  of spin i-1 (same rule as chunks 14-29). `is_duplicate_at_prev` asks
  "do spins[i-1] and spins[i-2] have identical reels?" — both are past, so
  this is a causal check.

Rulesets tested (all rules, even the noisy high-mb ones):
  - V5         : the 7-rule shipped ensemble
  - ISLAM      : SHIELD-heavy 7-rule (chunk 27)
  - ISLAM_V2   : ATTACK-focused 8-rule (chunk 29 discovery)
  - CAUSAL_7   : the 7-rule causal SML/COND ensemble from chunk 14/16
  - UNION_ALL  : union of every rule above — deliberately over-firing

Baselines (for comparison):
  - naive_fire  : bet high on every spin where ANY rule fires (no gating)
  - rule_window : first rule fire triggers a flat 7-pull bet window (no dup gate)
  - dup_gated   : the proposed strategy

Targets:
  - accumulation
  - spins

Outputs:
  analysis/nuclear/30_duplicate_gated_results.txt
"""
from __future__ import annotations
import os
import pickle
import sys
from collections import deque
from pathlib import Path

PKL = Path(__file__).parent / 'gaps.pkl'
OUT = Path(__file__).parent / '30_duplicate_gated_results.txt'

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with open(PKL, 'rb') as f:
    DATA = pickle.load(f)

ACCOUNTS = [a for a in ['Islam', 'Ahmed', 'Nick'] if a in DATA]

# ---------------------------------------------------------------------------
# Rule library — copied/adapted from 29_strategy_lab.py so this script is
# self-contained. Rules read a state-dict. If you add a new rule anywhere
# in the codebase you can paste it here.
# ---------------------------------------------------------------------------
def gap_class(L):
    if L is None: return 'NONE'
    if L <= 39:  return 'XS'
    if L <= 105: return 'S'
    if L <= 160: return 'M'
    return 'L'

# --- v5 7-rule (shipped) ---
def rule_steal_t65(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if not (65 <= sp <= 105): return False
    return (s['sa_acc']/sp) >= 0.34
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

# --- Islam chunk-27 ---
def rule_shield_t130_g028(s):
    if s['prev_real_triple'] != 'shield': return False
    sp = s['sa_spins']
    if sp < 130: return False
    return (s['sa_acc']/sp) >= 0.28
def rule_shield_t110_g032(s):
    if s['prev_real_triple'] != 'shield': return False
    sp = s['sa_spins']
    if sp < 110: return False
    return (s['sa_acc']/sp) >= 0.32
def rule_qz_t110(s):
    if s['sa_spins'] < 110: return False
    return s['last10_sum'] <= 10
def rule_qz_t150(s):
    if s['sa_spins'] < 150: return False
    return s['last10_sum'] <= 10

# --- Islam v2 (chunk-29 ATTACK discovery) ---
def rule_attack_t60_g025(s):
    if s['prev_real_triple'] != 'attack': return False
    sp = s['sa_spins']
    if sp < 60: return False
    return (s['sa_acc']/sp) >= 0.25
def rule_attack_t130_g028(s):
    if s['prev_real_triple'] != 'attack': return False
    sp = s['sa_spins']
    if sp < 130: return False
    return (s['sa_acc']/sp) >= 0.28
def rule_shield_t80_g028(s):
    if s['prev_real_triple'] != 'shield': return False
    sp = s['sa_spins']
    if sp < 80: return False
    return (s['sa_acc']/sp) >= 0.28
def rule_steal_t60_g028(s):
    if s['prev_real_triple'] != 'steal': return False
    sp = s['sa_spins']
    if sp < 60: return False
    return (s['sa_acc']/sp) >= 0.28
def rule_spins_t100_g028(s):
    if s['prev_real_triple'] != 'spins': return False
    sp = s['sa_spins']
    if sp < 100: return False
    return (s['sa_acc']/sp) >= 0.28

# --- Causal-7 (chunks 14/16) — adapted to state-dict API ---
def _sml(s_bound, l_bound, t_s, t_m, t_l, gate):
    def f(s):
        prev = s.get('prev_gap_length')
        if prev is None: return False
        if prev < s_bound:   thresh = t_s
        elif prev < l_bound: thresh = t_m
        else:                thresh = t_l
        if thresh is None: return False
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        return (s['sa_acc']/sp) >= gate
    return f

def _flat(thresh, gate, stop=None):
    def f(s):
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        if stop is not None and sp > stop: return False
        return (s['sa_acc']/sp) >= gate
    return f

def _cond(required, thresh, gate):
    def f(s):
        if s.get('prev_real_triple') != required: return False
        sp = s['sa_spins']
        if sp < thresh or sp == 0: return False
        return (s['sa_acc']/sp) >= gate
    return f

CAUSAL_7_RULES = [
    ('SML L120 tL130 g030', _sml(0, 120, None, None, 130, 0.30)),
    ('SML L120 tL130 g028', _sml(0, 120, None, None, 130, 0.28)),
    ('SML L140 tL130 g029', _sml(0, 140, None, None, 130, 0.29)),
    ('FLAT 130 g031 s160',  _flat(130, 0.31, 160)),
    ('COND steal 130 g029', _cond('steal', 130, 0.29)),
    ('COND shield 150 g030',_cond('shield',150, 0.30)),
    ('SML L130 tL100 g031', _sml(50, 130, None, None, 100, 0.31)),
]

# ---------------------------------------------------------------------------
# Rulesets
# ---------------------------------------------------------------------------
V5_RULES = [
    ('steal_t65',    rule_steal_t65),
    ('steal_t130',   rule_steal_t130),
    ('steal_t150',   rule_steal_t150),
    ('shield_t150',  rule_shield_t150),
    ('quiet_zone',   rule_quiet_zone),
    ('dg_t130',      rule_dg_t130),
    ('early_s',      rule_early_s),
]

ISLAM_RULES = [
    ('steal_t130',       rule_steal_t130),
    ('shield_t150',      rule_shield_t150),
    ('shield_t130_g028', rule_shield_t130_g028),
    ('shield_t110_g032', rule_shield_t110_g032),
    ('quiet_zone',       rule_quiet_zone),
    ('qz_t110',          rule_qz_t110),
    ('qz_t150',          rule_qz_t150),
]

ISLAM_V2_RULES = [
    ('attack_t60_g025',  rule_attack_t60_g025),
    ('attack_t130_g028', rule_attack_t130_g028),
    ('shield_t150',      rule_shield_t150),
    ('shield_t80_g028',  rule_shield_t80_g028),
    ('shield_t130_g028', rule_shield_t130_g028),
    ('steal_t130',       rule_steal_t130),
    ('steal_t60_g028',   rule_steal_t60_g028),
    ('spins_t100_g028',  rule_spins_t100_g028),
]

def _union(*rulesets):
    seen = set()
    out = []
    for rs in rulesets:
        for name, fn in rs:
            if name in seen: continue
            seen.add(name)
            out.append((name, fn))
    return out

UNION_ALL = _union(V5_RULES, ISLAM_RULES, ISLAM_V2_RULES, CAUSAL_7_RULES)

RULESETS = [
    ('V5',       V5_RULES),
    ('ISLAM',    ISLAM_RULES),
    ('ISLAM_V2', ISLAM_V2_RULES),
    ('CAUSAL_7', CAUSAL_7_RULES),
    ('UNION_ALL',UNION_ALL),
]

# ---------------------------------------------------------------------------
# Simulation core
# ---------------------------------------------------------------------------
# Strategy identifiers
STRAT_NAIVE   = 'naive_fire'    # bet high on every spin any rule fires
STRAT_WINDOW  = 'rule_window'   # first fire triggers a 7-pull bet window
STRAT_GATED   = 'dup_gated'     # fire → wait for dup → 7-pull bet window

MINI_PAUSE_TRIPLES = {'attack', 'steal', 'shield'}
BET_WINDOW = 7
MINI_PAUSE_LEN = 4

def _build_state(spins, i, prev_real_triple, prev_gap_length,
                 last10, spn_alpha, spn_drop_seen):
    """Construct the state dict that rules are evaluated against,
    using ONLY information observable at the end of spin i-1."""
    if i == 0:
        cur_sa_spins = 0
        cur_sa_acc   = 0
        cur_sa_spn   = 0
    else:
        prev = spins[i-1]
        cur_sa_spins = prev['sa_spins']
        cur_sa_acc   = prev['sa_acc']
        cur_sa_spn   = prev['sa_spn']
    return {
        'sa_spins': cur_sa_spins,
        'sa_acc':   cur_sa_acc,
        'sa_spn':   cur_sa_spn,
        'prev_real_triple': prev_real_triple,
        'prev_gap_length':  prev_gap_length,
        'last10_sum':       sum(last10),
        '_spn_alpha':       spn_alpha,
        '_spn_drop_seen':   spn_drop_seen,
    }


def duplicate_distance_histogram(spins, target, max_dist=40):
    """For each target triple, find the SMALLEST distance (in spins) from any
    back-to-back duplicate reel pair to the target. Returns a histogram
    binned by distance, plus a "no dup within window" count.

    A duplicate at (i-1, i-2) is conceptually "detected at i" (both spins in
    the past). So distance = target_idx - i = target_idx - duplicate_detect_idx.
    """
    hist = [0] * (max_dist + 1)
    no_dup = 0
    total = 0
    for t_idx, s in enumerate(spins):
        if s.get('triple') != target:
            continue
        total += 1
        # Walk backwards looking for duplicates
        best = None
        for j in range(max(2, t_idx - max_dist), t_idx):
            a = spins[j-1]
            b = spins[j-2]
            if (a['reel_1']==b['reel_1'] and a['reel_2']==b['reel_2']
                and a['reel_3']==b['reel_3']):
                # detected at spin j (smallest distance = latest duplicate)
                dist = t_idx - j
                if best is None or dist < best:
                    best = dist
        if best is None or best > max_dist:
            no_dup += 1
        else:
            hist[best] += 1
    return hist, no_dup, total


def simulate(spins, rules, target, strategy, bet_high=6000,
             bet_window=BET_WINDOW, mini_pause=MINI_PAUSE_LEN):
    """Run one pass of the simulator over `spins`.

    Returns a dict of metrics.
    """
    # Cross-spin causal state for rules
    prev_real_triple = None
    prev_gap_length  = None
    last10 = deque(maxlen=10)
    spn_alpha = None
    spn_drop_seen = False

    # Strategy state machine
    state = 'IDLE'
    bet_counter = 0
    pause_counter = 0

    # Metrics
    pulls = 0
    bet_high_spins = 0
    bet_high_cost  = 0
    targets_seen = 0
    catches = 0                   # target triple while BET_HIGH
    catches_during_pause = 0      # target landed during MINI_PAUSE (we bet 1)
    arms = 0                      # rule_fire → ARMED transitions
    duplicates_fired = 0          # ARMED → BET_HIGH transitions
    lost_arms = 0                 # target landed while ARMED (before dup)
    windows_expired = 0           # bet-window exhausted without catching
    mini_pauses = 0

    n = len(spins)
    for i in range(n):
        s = spins[i]

        # --- Evaluate rules causally ---
        state_dict = _build_state(
            spins, i, prev_real_triple, prev_gap_length,
            last10, spn_alpha, spn_drop_seen
        )
        rule_firing = any(fn(state_dict) for _, fn in rules)

        # --- Duplicate check (causal: was spin i-1 a duplicate of i-2?) ---
        is_duplicate_at_prev = False
        if i >= 2:
            a = spins[i-1]
            b = spins[i-2]
            is_duplicate_at_prev = (
                a['reel_1'] == b['reel_1'] and
                a['reel_2'] == b['reel_2'] and
                a['reel_3'] == b['reel_3']
            )

        # --- Strategy-specific state transitions BEFORE placing bet ---
        if strategy == STRAT_NAIVE:
            # No state machine. Bet high iff rule fires.
            bet = bet_high if rule_firing else 1
        elif strategy == STRAT_WINDOW:
            # First fire arms a fresh 7-pull bet window (no duplicate gate).
            if state == 'IDLE' and rule_firing:
                state = 'BET_HIGH'
                bet_counter = bet_window
                arms += 1
                duplicates_fired += 1  # treat fire as the gate for bookkeeping
            bet = bet_high if state == 'BET_HIGH' else 1
        elif strategy == STRAT_GATED:
            if state == 'IDLE' and rule_firing:
                state = 'ARMED'
                arms += 1
            if state == 'ARMED' and is_duplicate_at_prev:
                state = 'BET_HIGH'
                bet_counter = bet_window
                duplicates_fired += 1
            bet = bet_high if state == 'BET_HIGH' else 1
        else:
            raise ValueError(strategy)

        pulls += 1
        if bet > 1:
            bet_high_spins += 1
            bet_high_cost  += bet

        # --- Observe spin i outcome ---
        is_target = (s.get('triple') == target)
        triple_kind = s.get('triple')
        is_mini_trigger = triple_kind in MINI_PAUSE_TRIPLES

        if is_target:
            targets_seen += 1
            if strategy == STRAT_NAIVE:
                if bet > 1:
                    catches += 1
            else:
                if state == 'BET_HIGH':
                    catches += 1
                elif state == 'MINI_PAUSE':
                    catches_during_pause += 1
                elif state == 'ARMED':
                    lost_arms += 1
                # Reset state machine on target triple
                state = 'IDLE'
                bet_counter = 0
                pause_counter = 0

        # Post-spin state machine evolution (only for stateful strategies).
        # mini_pause > 0: on a mid-win triple, drop to 1x for `mini_pause`
        #                 pulls, then resume BET_HIGH with a fresh window.
        # mini_pause == 0: mid-wins are IGNORED — bet window runs flat to 0.
        if strategy in (STRAT_WINDOW, STRAT_GATED) and not is_target:
            if state == 'BET_HIGH':
                bet_counter -= 1
                if is_mini_trigger and mini_pause > 0:
                    state = 'MINI_PAUSE'
                    pause_counter = mini_pause
                    mini_pauses += 1
                elif bet_counter <= 0:
                    state = 'IDLE'
                    windows_expired += 1
            elif state == 'MINI_PAUSE':
                pause_counter -= 1
                if pause_counter <= 0:
                    state = 'BET_HIGH'
                    bet_counter = bet_window

        # --- Cross-spin state update for rule inputs ---
        sym_total = (s.get('atk_count',0)+s.get('stl_count',0)+s.get('shd_count',0)
                     +s.get('spn_count',0)+s.get('acc_count',0))
        last10.append(sym_total)

        if s.get('triple') == 'spins':
            spn_alpha = 0
            spn_drop_seen = True
        elif spn_alpha is not None:
            spn_alpha += 1

        if s.get('triple') is not None:
            prev_real_triple = s.get('triple')
        if s.get('triple') == 'accumulation':
            prev_gap_length = state_dict['sa_spins']

    recall_pct = 100 * catches / max(1, targets_seen)
    # mb/hit = max bets per hit = bet-high spins / catches (chunk 25-29 convention).
    mb_hit = (bet_high_spins / catches) if catches else float('inf')

    return {
        'pulls': pulls,
        'targets': targets_seen,
        'catches': catches,
        'catches_during_pause': catches_during_pause,
        'lost_arms': lost_arms,
        'arms': arms,
        'dups_fired': duplicates_fired,
        'mini_pauses': mini_pauses,
        'windows_expired': windows_expired,
        'bet_high_spins': bet_high_spins,
        'bet_high_cost':  bet_high_cost,
        'recall_pct': recall_pct,
        'mb_hit': mb_hit,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def fmt_inf(x, width=7):
    return f'{"inf":>{width}}' if x == float('inf') else f'{x:>{width}.0f}'

def fmt_row(r, strat_name):
    return (
        f'    {strat_name:<11s} '
        f'catches={r["catches"]:>3d}/{r["targets"]:<3d} '
        f'({r["recall_pct"]:>5.1f}%)  '
        f'bet_spins={r["bet_high_spins"]:>5d}  '
        f'mb/hit={fmt_inf(r["mb_hit"], 5)}  '
        f'arms={r["arms"]:>4d} '
        f'dups={r["dups_fired"]:>4d} '
        f'lost_arm={r["lost_arms"]:>3d} '
        f'mp={r["mini_pauses"]:>3d} '
        f'exp={r["windows_expired"]:>3d}'
    )


def run_all():
    lines = []
    def P(msg=''):
        lines.append(msg)
        print(msg)

    P('=' * 140)
    P('CHUNK 30: DUPLICATE-GATED BET SIMULATION  (chunk-29 rules + duplicate-reel gate)')
    P('=' * 140)
    P('Hypothesis: rule fires -> wait for back-to-back duplicate reel tuple -> 7-pull bet window.')
    P(f'  bet window = {BET_WINDOW} pulls,  mini-pause = {MINI_PAUSE_LEN} pulls on {{attack,steal,shield}} triple')
    P(f'  bet-high size = 6000 spins,  bet-low size = 1 spin')
    P(f'  evaluation = causal (spin i uses prev-spin state), reruns ENTIRE per-account spin log')
    P('  mb/hit = "max bets per hit" = count of bet-high pulls divided by catches.')
    P('           Same convention as chunks 25-29. LOWER is better.')
    P('')
    P('Base-rate reference (analyze_reel_patterns.py):')
    P('  accumulation triples preceded by duplicate in last 15: 160/271 (59.0%)')
    P('  spins        triples preceded by duplicate in last 15: 221/333 (66.4%)')
    P('')

    for target in ['accumulation', 'spins']:
        P('#' * 140)
        P(f'#  TARGET = {target.upper()}')
        P('#' * 140)
        P('')

        # Aggregate across accounts per (ruleset, strategy)
        agg = {}

        for acct in ACCOUNTS:
            spins = DATA[acct]['spins']
            P(f'--- ACCOUNT: {acct}  ({len(spins):,} spins) ---')
            for rs_name, rules in RULESETS:
                P(f'  Ruleset: {rs_name}  ({len(rules)} rules)')
                for strategy in (STRAT_NAIVE, STRAT_WINDOW, STRAT_GATED):
                    r = simulate(spins, rules, target, strategy)
                    P(fmt_row(r, strategy))
                    key = (rs_name, strategy)
                    a = agg.setdefault(key, {
                        'catches':0,'targets':0,'bet_high_spins':0,'bet_high_cost':0,
                        'arms':0,'dups_fired':0,'lost_arms':0,'mini_pauses':0,
                        'windows_expired':0,'catches_during_pause':0,'pulls':0
                    })
                    for k in a: a[k] += r[k]
                P('')
            P('')

        # Overall summary table
        P('=' * 140)
        P(f'OVERALL  target={target}  (summed across {", ".join(ACCOUNTS)})  bet_window={BET_WINDOW}')
        P('=' * 140)
        P(f'  {"ruleset":<10s} {"strategy":<12s} {"catches":>10s} {"recall":>8s} '
          f'{"bet_spins":>10s} {"mb/hit":>8s} '
          f'{"arms":>6s} {"dups":>6s} {"lost":>5s} {"mp":>4s} {"exp":>4s}')
        for (rs_name, strategy), a in sorted(agg.items()):
            catches = a['catches']; targets = a['targets']
            bs = a['bet_high_spins']
            recall = 100*catches/max(1,targets)
            mb = (bs/catches) if catches else float('inf')
            P(f'  {rs_name:<10s} {strategy:<12s} '
              f'{catches:>5d}/{targets:<4d} {recall:>6.1f}% '
              f'{bs:>10d} {fmt_inf(mb,8)} '
              f'{a["arms"]:>6d} {a["dups_fired"]:>6d} '
              f'{a["lost_arms"]:>5d} {a["mini_pauses"]:>4d} {a["windows_expired"]:>4d}')
        P('')

        # --- Distance-to-duplicate histogram (feasibility analysis) ---
        P('-' * 140)
        P(f'DISTANCE FROM NEAREST BACK-TO-BACK DUPLICATE TO {target.upper()} TRIPLE')
        P('  dist = # pulls between the duplicate-detection spin and the triple-landing spin.')
        P('  A bet window of size W starting at the duplicate will catch a triple if distance <= W - 1.')
        P('-' * 140)
        tot_hist = [0] * 41
        tot_no_dup = 0
        tot_targets = 0
        for acct in ACCOUNTS:
            hist, no_dup, total = duplicate_distance_histogram(DATA[acct]['spins'], target, max_dist=40)
            tot_targets += total
            tot_no_dup += no_dup
            for i, v in enumerate(hist):
                tot_hist[i] += v
        P(f'  Total {target} triples: {tot_targets}')
        P(f'  No duplicate within 40 spins: {tot_no_dup} ({100*tot_no_dup/max(1,tot_targets):.1f}%)')
        cum = 0
        P(f'  {"dist":>5s} {"count":>6s} {"cum":>6s} {"cum%":>6s}')
        for d in range(0, 41):
            cum += tot_hist[d]
            if tot_hist[d] > 0 or d in (7, 14, 21, 28, 35):
                P(f'  {d:>5d} {tot_hist[d]:>6d} {cum:>6d} {100*cum/max(1,tot_targets):>5.1f}%')
        P('')

        # --- bet_window sweep on UNION_ALL ---
        P('-' * 140)
        P(f'BET-WINDOW SWEEP — ruleset=UNION_ALL, strategy=dup_gated, target={target}')
        P('  Tests different bet_window sizes. Mini-pause fixed at 4. Shows how window size')
        P('  trades off catches vs bet-spins burned.')
        P('-' * 140)
        P(f'  {"win":>4s} {"mp":>3s} {"catches":>10s} {"recall":>7s} '
          f'{"bet_spins":>10s} {"mb/hit":>8s} '
          f'{"arms":>5s} {"dups":>5s} {"lost":>5s}')
        for win in (5, 7, 10, 14, 20, 30):
            for mp in (0, 4):
                agg_c = agg_t = agg_bs = agg_a = agg_d = agg_l = 0
                for acct in ACCOUNTS:
                    r = simulate(DATA[acct]['spins'], UNION_ALL, target,
                                 STRAT_GATED, bet_window=win, mini_pause=mp)
                    agg_c += r['catches']; agg_t += r['targets']
                    agg_bs += r['bet_high_spins']
                    agg_a += r['arms']; agg_d += r['dups_fired']; agg_l += r['lost_arms']
                recall = 100*agg_c/max(1,agg_t)
                mb = (agg_bs/agg_c) if agg_c else float('inf')
                P(f'  {win:>4d} {mp:>3d} {agg_c:>4d}/{agg_t:<4d} '
                  f'{recall:>6.1f}% {agg_bs:>10d} '
                  f'{fmt_inf(mb,8)} '
                  f'{agg_a:>5d} {agg_d:>5d} {agg_l:>5d}')
        P('')

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'\n[wrote {OUT}]')


if __name__ == '__main__':
    run_all()
