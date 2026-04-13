"""
Strategy Lab  —  chunk 29  (rewrite 2026-04-09)

Focus shift: stop chasing low mb/hit, START finding methods that actually
CLEAR the mission ladder within REAL event budgets. The chunk-28 extension
showed that every previous "clear" took 14K–43K pulls, but real events only
give each account ~4–7K in-event spins per session. We need 3× the clearing
efficiency — Islam is the priority target because he NEVER clears under
any of the 5 original strategies.

New in this rewrite:
  1. Dual-cycle offset model (from user 2026-04-09):
     "ACC and SPN triples run on ~115-spin cycles; when one drops, measure
     the offset into the other cycle to predict its next drop."
     Empirical validation: the sum (alpha + beta) around SPN drops has
     std=37 for Ahmed (tight enough to be useful) but std=91 for Islam
     (noisy). We add it as a rule regardless — every catch matters.

  2. Islam-tuned ensemble using the chunk-27 hunt results (SHIELD-heavy,
     quiet-zone variants) — different shape from the shipped v5 7-rule.

  3. Mission-aware & bankroll-aware bet sizing: bump size scales with
     proximity to next mission threshold (don't waste 60K on a 500-pt
     early mission).

  4. Confidence-tiered superbump: bet 20000 when 2+ rules fire, 6000 on
     single fire, 1 otherwise — multi-fire is the Ahmed signal we saw
     in the bump log.

  5. Island-kill hybrid: Hammer base + forced 20000 override when
     ensemble fires AND within 200K of next mission threshold.

Real in-event budgets (from data):
  Islam s0: 7,280    s1: 3,885
  Ahmed s0: 6,586    s1: 4,142
  Nick  s0:   976    s1:   693

Usage:
  python analysis/nuclear/29_strategy_lab.py                # full run
  python analysis/nuclear/29_strategy_lab.py --islam-only   # Islam sessions only
  python analysis/nuclear/29_strategy_lab.py --dualcycle    # print dual-cycle diagnostics
"""
import pickle
import sys
import statistics
from collections import deque

PKL = 'analysis/nuclear/gaps.pkl'
with open(PKL, 'rb') as f:
    data = pickle.load(f)


# ---------------------------------------------------------------------------
# Ladders (same as chunk 28)
# ---------------------------------------------------------------------------
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
HAMMER_LADDER = [(15,25),(50,50),(400,75),(1500,93),(6000,None)]


# ---------------------------------------------------------------------------
# Rule library
# ---------------------------------------------------------------------------
def gap_class(L):
    if L is None: return 'NONE'
    if L <= 39:  return 'XS'
    if L <= 105: return 'S'
    if L <= 160: return 'M'
    return 'L'

# --- v5 7-rule (shipped, cross-account tuned) ---
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

# --- Islam-specific (chunk 27 Pareto top) ---
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

# --- Islam in-event rules (2026-04-09 discovery: Islam's ACC triples are
#     preceded by ATTACK most often, NOT shield as prior work assumed.
#     Quiet-zone rules catch ~0 Islam in-event triples) ---
def rule_attack_t60_g025(s):
    """Highest-recall Islam rule — 30% recall on both sessions."""
    if s['prev_real_triple'] != 'attack': return False
    sp = s['sa_spins']
    if sp < 60: return False
    return (s['sa_acc']/sp) >= 0.25
def rule_attack_t130_g028(s):
    """Precision pair to t60 — drops fire volume but keeps recall."""
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

# --- Dual-cycle offset rules (NEW 2026-04-09) ---
# Fire when we are in the predicted ACC-drop window based on the last SPN
# triple's observed offset. Empirical ACC cycle median per session varies
# (~100-130), but the user's rule of thumb is ~115. We use that as a
# default and widen the window to account for observed std.
DUALCYCLE_PERIOD = 115   # user's reported cycle target
DUALCYCLE_WINDOW = 25    # +/- window around the predicted drop point

def rule_dualcycle(s):
    """Fire when sa_spins is in the predicted-drop window since last SPN drop.
    Requires spn_alpha (spins-since-last-spn-drop) >= 20 and current sa_spins
    near DUALCYCLE_PERIOD - spn_alpha (the predicted beta).

    Note: actually we compute predicted_drop_sa_spins = DUALCYCLE_PERIOD
    (under the assumption that ACC cycle is stable at ~115) and fire in a
    window around it. The 'offset' concept doesn't change sa_spins directly
    — it's a standalone re-affirmation that we should bet in the 115-zone.
    """
    sp = s['sa_spins']
    spn_drop_seen = s.get('_spn_drop_seen', False)
    if not spn_drop_seen: return False
    # Window around DUALCYCLE_PERIOD (user's "115 target")
    return (DUALCYCLE_PERIOD - DUALCYCLE_WINDOW) <= sp <= (DUALCYCLE_PERIOD + DUALCYCLE_WINDOW)

def rule_dualcycle_tight(s):
    """Tight version: only when we're within ±10 of the predicted drop."""
    sp = s['sa_spins']
    if not s.get('_spn_drop_seen', False): return False
    return (DUALCYCLE_PERIOD - 10) <= sp <= (DUALCYCLE_PERIOD + 10)

def rule_dualcycle_pred(s):
    """Use the actual alpha (spins since last SPN drop) to predict beta.
    Fire when sa_spins_since_last_acc_triple is within ±10 of (period - alpha)."""
    sp = s['sa_spins']
    alpha = s.get('_spn_alpha', None)
    if alpha is None or alpha == 0: return False
    # Under the model: predicted beta = period - alpha
    # Meaning: when sa_spins reaches alpha + (period - alpha) = period, ACC should drop
    # But we may have started the counting from a different basis. Use alpha offset:
    pred_sa = DUALCYCLE_PERIOD - alpha + alpha  # = DUALCYCLE_PERIOD
    # Actually the meaningful version: fire when (sp + alpha) is near period
    return abs((sp + alpha) - DUALCYCLE_PERIOD) <= 15

V5_RULES = [
    ('steal_t65', rule_steal_t65), ('steal_t130', rule_steal_t130),
    ('steal_t150', rule_steal_t150), ('shield_t150', rule_shield_t150),
    ('quiet_zone', rule_quiet_zone), ('dg_t130', rule_dg_t130),
    ('early_s', rule_early_s),
]

# Islam-tuned: SHIELD-heavy + QZ variants (from chunk 27 hunt)
ISLAM_RULES = [
    ('steal_t130',   rule_steal_t130),
    ('shield_t150',  rule_shield_t150),
    ('shield_t130_g028', rule_shield_t130_g028),
    ('shield_t110_g032', rule_shield_t110_g032),
    ('quiet_zone',   rule_quiet_zone),
    ('qz_t110',      rule_qz_t110),
    ('qz_t150',      rule_qz_t150),
]

# Islam v2 rule set (2026-04-09): Islam's ACC triples are preceded by
# ATTACK most often, not SHIELD. Quiet-zone rules never fire on actual
# Islam event triples. This set reaches 65% recall on Islam s1 (20/31).
# Minimum-cover greedy result from the candidate pool analysis.
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

# v5 + dual-cycle offset (all accounts)
V5_PLUS_DC = V5_RULES + [
    ('dualcycle',       rule_dualcycle),
    ('dualcycle_tight', rule_dualcycle_tight),
]

# Islam + dual-cycle offset
ISLAM_PLUS_DC = ISLAM_RULES + [
    ('dualcycle',       rule_dualcycle),
    ('dualcycle_tight', rule_dualcycle_tight),
]


def fired(state, ruleset):
    return [name for name,fn in ruleset if fn(state)]


# ---------------------------------------------------------------------------
# Event extraction
# ---------------------------------------------------------------------------
def get_event_spins(account, session_idx):
    return [s for s in data[account]['spins']
            if s['session_idx'] == session_idx and s['gae_segment'] != '']


# ---------------------------------------------------------------------------
# Strategies
# Each strategy is: fn(state, ctx, ruleset) -> bet (in spins)
# ctx exposes: bankroll, mission_idx, mission_pts, ladder, hammer_level,
#              hammers, firing (list), n_fires (int), pulls, sa_spins
# ---------------------------------------------------------------------------
def strat_pure_1x(state, ctx, rs):
    return 1

def strat_pure_6000(state, ctx, rs):
    return 6000

def strat_hammer(state, ctx, rs):
    return HAMMER_LADDER[ctx['hammer_level']][0]

def strat_ensemble(state, ctx, rs):
    return 6000 if ctx['n_fires'] else 1

def strat_hybrid(state, ctx, rs):
    base = HAMMER_LADDER[ctx['hammer_level']][0]
    return max(base, 6000) if ctx['n_fires'] else base

def strat_superbump(state, ctx, rs):
    """Confidence-tiered: 20K on multi-fire, 6K on single, 1 else."""
    if ctx['n_fires'] >= 2: return 20000
    if ctx['n_fires'] >= 1: return 6000
    return 1

def strat_island_kill(state, ctx, rs):
    """Hammer base + forced 20K override when fires AND close to next mission."""
    base = HAMMER_LADDER[ctx['hammer_level']][0]
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    if ctx['n_fires'] and 0 < needed <= 200_000:
        return 20000
    return max(base, 6000) if ctx['n_fires'] else base

def strat_mission_aware(state, ctx, rs):
    """Scale bump size to how much we actually need."""
    if not ctx['n_fires']: return 1
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    # Don't waste 60K on a 500-pt early mission
    if needed <= 2_000:  return 1500
    if needed <= 15_000: return 6000
    if needed >= 100_000 and ctx['n_fires'] >= 2: return 20000
    return 6000

def strat_bankroll_scaled(state, ctx, rs):
    """Bet size = clamp(bk * 0.05, 1500, 20000) on fire. Grows with rewards."""
    if not ctx['n_fires']: return 1
    target = int(ctx['bankroll'] * 0.05)
    for b in [20000, 6000, 1500]:
        if b <= target: return b
    return 1500  # floor

def strat_dualcycle_bump(state, ctx, rs):
    """
    Bet 20K when dual-cycle rule fires alone (high-confidence shot),
    6K on any v5 fire, 1 else.
    """
    if any(n in ctx['firing'] for n in ('dualcycle','dualcycle_tight')):
        return 20000
    return 6000 if ctx['n_fires'] else 1

def strat_islam_killer(state, ctx, rs):
    """
    Custom Islam strategy — combines everything that scored highest for Islam:
      - Superbump (20K on 2+ fires)
      - Island kill (20K when fires AND within 200K of next mission)
      - Hammer base progression
      - Mission-waste avoidance (don't overbump tiny early missions)
    """
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']

    # Tiny early missions — don't waste
    if needed <= 2_000:
        return 1500 if ctx['n_fires'] else 1

    # Within 200K of threshold AND ensemble fires: force 20K to chain-clear
    if ctx['n_fires'] and 0 < needed <= 200_000:
        return 20000

    # Multi-fire: maximum confidence, go 20K
    if ctx['n_fires'] >= 2:
        return 20000

    # Single fire: 6K
    if ctx['n_fires'] == 1:
        return 6000

    # No fire: Hammer base (to still progress through hammer ladder)
    return HAMMER_LADDER[ctx['hammer_level']][0]

def strat_islam_killer_small(state, ctx, rs):
    """Gentler variant: uses 6K instead of 20K most places, 1x base."""
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    if needed <= 2_000:
        return 1500 if ctx['n_fires'] else 1
    if ctx['n_fires'] >= 2 and needed <= 100_000:
        return 20000
    return 6000 if ctx['n_fires'] else 1

def strat_islam_conserve(state, ctx, rs):
    """
    Conservation variant of islam_killer: bet 1 when no fires (never Hammer base).
    Motivation: islam_killer got 17/22 at 100% of next mission with bk=0 —
    literally 1 pull short. It wastes bankroll on 6000-per-pull Hammer base
    fallback during grind. By betting 1 in no-fire spins we maximize pulls
    and let the constant 0.401 pts/cost ratio accumulate more missions pts
    per spin-unit while preserving bankroll for high-confidence bumps.
    """
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    if needed <= 2_000:
        return 1500 if ctx['n_fires'] else 1
    if ctx['n_fires'] and 0 < needed <= 200_000:
        return 20000
    if ctx['n_fires'] >= 2:
        return 20000
    if ctx['n_fires'] == 1:
        return 6000
    return 1  # CONSERVE — not hammer base

def strat_islam_conserve_6k(state, ctx, rs):
    """
    Even gentler: 6K on any fire, never 20K, bet 1 on no fire.
    Deliberately slow — we want to maximize pulls inside the budget while
    still capturing bumped triples at a meaningful bet.
    """
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    if needed <= 2_000:
        return 1500 if ctx['n_fires'] else 1
    if ctx['n_fires']:
        return 6000
    return 1

def strat_islam_scaled_conserve(state, ctx, rs):
    """
    Bet size scales with 'needed'. Early missions = tiny bets. Late = big.
    Always 1 on no-fire (conservation).
    """
    if not ctx['n_fires']:
        return 1
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    # Scale the bet so one catch can clear the mission
    # 10 * bet >= needed  =>  bet >= needed / 10
    target = max(1, needed // 10)
    for b in [20000, 6000, 1500, 400, 50, 15]:
        if b >= target and b <= 20000:
            return b
    return 20000 if ctx['n_fires'] >= 2 else 6000

def strat_islam_pace_400(state, ctx, rs):
    """
    Paced base bet = 400. Over the ~3,885 pull budget this spends
    ~1.55M spins baseline, which fits inside start+rewards (~1.9M)
    and leaves ~400K for high-confidence bumps.
    The goal is to burn the WHOLE bankroll across the WHOLE budget
    rather than bankrupting early or running out of budget with
    unspent bankroll.
    """
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    if needed <= 2_000:
        return 1500 if ctx['n_fires'] else 50
    if ctx['n_fires'] >= 2 and needed <= 100_000:
        return 20000
    if ctx['n_fires'] and 0 < needed <= 200_000:
        return 20000
    if ctx['n_fires'] >= 2:
        return 6000
    if ctx['n_fires'] == 1:
        return 6000
    return 400

def strat_islam_pace_1500(state, ctx, rs):
    """
    Paced base bet = 1500. Spends more aggressively but caps bumps at 6000
    instead of 20000. Total baseline spend = 3885 * 1500 = 5.8M (too much
    without rewards, but spins come in from M0-M16 clears so it's workable).
    """
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    if needed <= 2_000:
        return 1500 if ctx['n_fires'] else 50
    if ctx['n_fires']:
        return 6000
    return 1500

def strat_islam_adaptive_base(state, ctx, rs):
    """
    Adaptive base: size the no-fire bet by bankroll / remaining_budget.
    Aim to spend all bankroll exactly by end of budget. Overrides to
    20K on any fire within 200K of next mission.
    """
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    if needed <= 2_000:
        return 1500 if ctx['n_fires'] else 50

    # Bumps are highest priority
    if ctx['n_fires'] and 0 < needed <= 200_000:
        return 20000
    if ctx['n_fires'] >= 2:
        return 20000
    if ctx['n_fires'] == 1:
        return 6000

    # No fire: adaptive base
    # We have budget_left pulls; we want to spend bankroll over them.
    # Reserve a chunk (~20%) for bumps.
    budget_total = 3885  # assume Islam s1 worst case
    remaining = max(1, budget_total - ctx['pulls'])
    target = int((ctx['bankroll'] * 0.8) / remaining)
    # Snap to bet menu
    for b in [6000, 1500, 400, 50, 15, 3, 2, 1]:
        if b <= target: return b
    return 1

def strat_islam_reserve_guard(state, ctx, rs):
    """
    Like islam_killer but with a hard reserve: never let bankroll drop below
    a safety floor of 2000 spins unless we can finish on this pull. The
    reserve ensures we have tail-end bet-1 pulls to grind to the last threshold.
    """
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    bk = ctx['bankroll']
    RESERVE = 2000

    # If we're already below reserve, go full conserve (bet 1 unless cheap bump wins it)
    if bk <= RESERVE:
        if ctx['n_fires'] and needed <= 150:  # 15*10 = 150 pts would clear it
            return 15
        return 1

    # Tiny missions
    if needed <= 2_000:
        return 1500 if ctx['n_fires'] else 1

    # Calculate affordable "bump" that doesn't dip below reserve
    max_affordable = max(1, bk - RESERVE)

    if ctx['n_fires'] >= 2:
        for b in [20000, 6000, 1500]:
            if b <= max_affordable: return b
        return 1
    if ctx['n_fires'] == 1:
        for b in [6000, 1500]:
            if b <= max_affordable: return b
        return 1
    return 1


# --- Phase-switching strategies (NEW: early-game frugal, late-game aggressive) ---
def strat_phase_1x_then_ensemble(state, ctx, rs):
    """Pure 1x through M7, then ensemble-6000 bumping after."""
    if ctx['mission_idx'] < 7:
        return 1
    return 6000 if ctx['n_fires'] else 1

def strat_phase_1x_then_superbump(state, ctx, rs):
    """Pure 1x through M7, then superbump (multi-fire = 20K)."""
    if ctx['mission_idx'] < 7:
        return 1
    if ctx['n_fires'] >= 2: return 20000
    if ctx['n_fires'] >= 1: return 6000
    return 1

def strat_phase_hammer_then_killer(state, ctx, rs):
    """Hammer until M8 cleared, then islam_killer logic."""
    if ctx['mission_idx'] < 8:
        return HAMMER_LADDER[ctx['hammer_level']][0]
    return strat_islam_killer(state, ctx, rs)

def strat_phase_hammer_then_superbump(state, ctx, rs):
    """Hammer until M8, then superbump. No 1x waste."""
    if ctx['mission_idx'] < 8:
        return HAMMER_LADDER[ctx['hammer_level']][0]
    if ctx['n_fires'] >= 2: return 20000
    if ctx['n_fires'] >= 1: return 6000
    return HAMMER_LADDER[ctx['hammer_level']][0]

def strat_triple_phase(state, ctx, rs):
    """3 phases: M0-7 = 1x, M8-13 = ensemble 6000, M14+ = superbump 20K on multi."""
    m = ctx['mission_idx']
    if m < 7:
        return 1
    if m < 14:
        return 6000 if ctx['n_fires'] else 1
    if ctx['n_fires'] >= 2: return 20000
    if ctx['n_fires'] >= 1: return 6000
    return 1

def strat_clean_hammer(state, ctx, rs):
    """
    Hammer base ALWAYS. Override to 20K only when:
      - 2+ rules fire AND within 200K of next mission threshold
    Never drop below the hammer base.
    """
    base = HAMMER_LADDER[ctx['hammer_level']][0]
    needed = ctx['ladder'][ctx['mission_idx']][0] - ctx['mission_pts']
    if ctx['n_fires'] >= 2 and 0 < needed <= 200_000:
        return 20000
    return base

def strat_shield_hunter(state, ctx, rs):
    """
    Islam responds heavily to SHIELD rules. Bet 20K only on shield_* fires
    (these are the highest-catch-density rules for Islam per chunk 27).
    Otherwise hammer base.
    """
    shield_fires = [n for n in ctx['firing'] if n.startswith('shield')]
    if shield_fires:
        return 20000
    base = HAMMER_LADDER[ctx['hammer_level']][0]
    return max(base, 6000) if ctx['n_fires'] else base


STRATEGIES = [
    # Baselines
    ('pure_1x',              strat_pure_1x,       V5_RULES),
    ('pure_6000',            strat_pure_6000,     V5_RULES),
    ('pure_hammer',          strat_hammer,        V5_RULES),
    # v5 ensemble
    ('ensemble_v5',          strat_ensemble,      V5_RULES),
    ('hybrid_v5',            strat_hybrid,        V5_RULES),
    ('superbump_v5',         strat_superbump,     V5_RULES),
    ('island_kill_v5',       strat_island_kill,   V5_RULES),
    ('mission_aware_v5',     strat_mission_aware, V5_RULES),
    ('bankroll_scaled_v5',   strat_bankroll_scaled,V5_RULES),
    # Islam-tuned ensemble
    ('ensemble_islam',       strat_ensemble,      ISLAM_RULES),
    ('hybrid_islam',         strat_hybrid,        ISLAM_RULES),
    ('superbump_islam',      strat_superbump,     ISLAM_RULES),
    ('island_kill_islam',    strat_island_kill,   ISLAM_RULES),
    ('mission_aware_islam',  strat_mission_aware, ISLAM_RULES),
    ('bankroll_scaled_islam',strat_bankroll_scaled,ISLAM_RULES),
    # Dual-cycle extended
    ('ensemble_v5_dc',       strat_ensemble,      V5_PLUS_DC),
    ('superbump_v5_dc',      strat_superbump,     V5_PLUS_DC),
    ('dualcycle_bump_v5',    strat_dualcycle_bump,V5_PLUS_DC),
    ('ensemble_islam_dc',    strat_ensemble,      ISLAM_PLUS_DC),
    ('superbump_islam_dc',   strat_superbump,     ISLAM_PLUS_DC),
    ('dualcycle_bump_islam', strat_dualcycle_bump,ISLAM_PLUS_DC),
    # Custom Islam killers
    ('islam_killer',         strat_islam_killer,      ISLAM_RULES),
    ('islam_killer_dc',      strat_islam_killer,      ISLAM_PLUS_DC),
    ('islam_killer_small',   strat_islam_killer_small,ISLAM_RULES),
    ('islam_killer_sml_dc',  strat_islam_killer_small,ISLAM_PLUS_DC),
    ('islam_conserve',       strat_islam_conserve,    ISLAM_RULES),
    ('islam_conserve_v5',    strat_islam_conserve,    V5_RULES),
    ('islam_conserve_dc',    strat_islam_conserve,    ISLAM_PLUS_DC),
    ('islam_conserve_6k',    strat_islam_conserve_6k, ISLAM_RULES),
    ('islam_conserve_6k_v5', strat_islam_conserve_6k, V5_RULES),
    ('islam_scaled_conserve',strat_islam_scaled_conserve,ISLAM_RULES),
    ('islam_reserve_guard',  strat_islam_reserve_guard,ISLAM_RULES),
    ('islam_reserve_v5',     strat_islam_reserve_guard,V5_RULES),
    ('islam_pace_400',       strat_islam_pace_400,    ISLAM_RULES),
    ('islam_pace_400_v5',    strat_islam_pace_400,    V5_RULES),
    ('islam_pace_1500',      strat_islam_pace_1500,   ISLAM_RULES),
    ('islam_pace_1500_v5',   strat_islam_pace_1500,   V5_RULES),
    ('islam_adaptive_base',  strat_islam_adaptive_base,ISLAM_RULES),
    ('islam_adaptive_v5',    strat_islam_adaptive_base,V5_RULES),
    # Islam v2 ensemble (ATTACK-focused, 65% s1 recall)
    ('islam_v2_ensemble',    strat_ensemble,          ISLAM_V2_RULES),
    ('islam_v2_superbump',   strat_superbump,         ISLAM_V2_RULES),
    ('islam_v2_killer',      strat_islam_killer,      ISLAM_V2_RULES),
    ('islam_v2_conserve',    strat_islam_conserve,    ISLAM_V2_RULES),
    ('islam_v2_conserve_6k', strat_islam_conserve_6k, ISLAM_V2_RULES),
    ('islam_v2_pace_400',    strat_islam_pace_400,    ISLAM_V2_RULES),
    ('islam_v2_island_kill', strat_island_kill,       ISLAM_V2_RULES),
    ('islam_v2_clean_hammer',strat_clean_hammer,      ISLAM_V2_RULES),
    # Phase-switching
    ('phase_1x_ensemble',    strat_phase_1x_then_ensemble,   V5_RULES),
    ('phase_1x_ensemble_i',  strat_phase_1x_then_ensemble,   ISLAM_RULES),
    ('phase_1x_superbump',   strat_phase_1x_then_superbump,  V5_RULES),
    ('phase_1x_superbump_i', strat_phase_1x_then_superbump,  ISLAM_RULES),
    ('phase_hammer_killer',  strat_phase_hammer_then_killer, ISLAM_RULES),
    ('phase_hammer_sb',      strat_phase_hammer_then_superbump, V5_RULES),
    ('phase_hammer_sb_i',    strat_phase_hammer_then_superbump, ISLAM_RULES),
    ('triple_phase_v5',      strat_triple_phase,      V5_RULES),
    ('triple_phase_islam',   strat_triple_phase,      ISLAM_RULES),
    ('clean_hammer_v5',      strat_clean_hammer,      V5_RULES),
    ('clean_hammer_islam',   strat_clean_hammer,      ISLAM_RULES),
    ('shield_hunter',        strat_shield_hunter,     ISLAM_RULES),
    ('shield_hunter_dc',     strat_shield_hunter,     ISLAM_PLUS_DC),
]


# ---------------------------------------------------------------------------
# Simulator  (CAUSAL + corrected SPN triple payout)
# ---------------------------------------------------------------------------
# Causal rule: bet for spin i+1 is decided using state recorded AT spin i
# (i.e., before spin i+1 resolves).  Spin 0 gets a default bet because no
# prior state exists.
#
# Payout model (corrected 2026-04-09):
#   - ACC triple:  mission_points += 10 * bet    (as before)
#   - SPN triple:  bankroll       += 10 * bet    (NEW — 10x bet refunded in spins)
#   - Normal spin: mission_points += acc_count * bet
#
# Cost: bankroll -= bet on every pull.
# ---------------------------------------------------------------------------
def simulate(spins, bankroll0, ladder, strat_fn, ruleset):
    bankroll = bankroll0
    mission_idx = 0
    mission_pts = 0
    pulls = 0
    bumps = 0
    catches_on_bump_acc = 0
    spn_triples_on_bump = 0
    hammer_level = 0
    hammers = 0

    # State tracked ACROSS spins. Everything in here reflects what we know
    # AFTER spin i has been observed — which is the basis for spin i+1's bet.
    prev_real_triple = None
    prev_gap_length = None
    last10 = deque(maxlen=10)
    spn_alpha = None          # spins since last SPN triple drop (None until first SPN drop)
    spn_drop_seen = False

    n = len(spins)
    i = 0
    while i < n:
        s = spins[i]

        # --- Build the state WE WOULD KNOW just before spin i resolves ---
        # For spin 0 there is no prior information. For spin i>=1, use prior
        # spins' values (prev_real_triple etc. are all updated at end of loop
        # from spin i-1, so reading them here reflects spin i-1's snapshot).
        #
        # For the current spin's "snapshot" fields (sa_spins, sa_acc, sa_spn,
        # last10) we use the PREVIOUS spin's values — not spins[i]'s — because
        # spins[i]'s sa_* fields are post-inclusive (they include this spin's
        # contribution), so using them would leak the current outcome.
        if i == 0:
            # No history, fall back to zeros
            cur_sa_spins = 0
            cur_sa_acc   = 0
            cur_sa_spn   = 0
        else:
            prev = spins[i-1]
            cur_sa_spins = prev['sa_spins']
            cur_sa_acc   = prev['sa_acc']
            cur_sa_spn   = prev['sa_spn']

        state = {
            'sa_spins': cur_sa_spins,
            'sa_acc':   cur_sa_acc,
            'sa_spn':   cur_sa_spn,
            'prev_real_triple': prev_real_triple,
            'prev_gap_length':  prev_gap_length,
            'last10_sum':       sum(last10),
            '_spn_alpha':       spn_alpha,
            '_spn_drop_seen':   spn_drop_seen,
        }
        firing = fired(state, ruleset)
        ctx = {
            'bankroll':     bankroll,
            'mission_idx':  mission_idx,
            'mission_pts':  mission_pts,
            'ladder':       ladder,
            'hammer_level': hammer_level,
            'hammers':      hammers,
            'firing':       firing,
            'n_fires':      len(firing),
            'pulls':        pulls,
            'sa_spins':     cur_sa_spins,
        }
        bet = strat_fn(state, ctx, ruleset)

        # Failsafe: if we can't afford the requested bet, drop to bet=1
        # (only option if bankroll < smallest meaningful bet). This matches
        # real play: you'd never forfeit a bet because 50 > 38, you'd just
        # spin at 1x.
        if bankroll < bet:
            if bankroll >= 1:
                bet = 1
            else:
                break

        bankroll -= bet
        pulls += 1

        is_acc_triple = (s.get('triple') == 'accumulation')
        is_spn_triple = (s.get('triple') == 'spins')

        if is_acc_triple:
            # 10x bet goes into mission points
            mission_pts += 10 * bet
        else:
            mission_pts += s['acc_count'] * bet

        if is_spn_triple:
            # 10x bet comes back to bankroll as free spins
            bankroll += 10 * bet

        if bet > 1:
            bumps += 1
            if is_acc_triple: catches_on_bump_acc += 1
            if is_spn_triple: spn_triples_on_bump += 1

        # Mission cascade
        while mission_idx < len(ladder) and mission_pts >= ladder[mission_idx][0]:
            thresh, reward = ladder[mission_idx]
            mission_pts -= thresh
            bankroll += reward
            mission_idx += 1

        if mission_idx >= len(ladder):
            return {
                'cleared': True, 'pulls_to_clear': pulls,
                'missions_cleared': mission_idx, 'final_bankroll': bankroll,
                'end_mission_pts': mission_pts, 'pulls': pulls,
                'bumps': bumps,
                'catches_on_bump_acc': catches_on_bump_acc,
                'spn_triples_on_bump': spn_triples_on_bump,
                'next_thresh': None,
            }

        # --- Update cross-spin state for NEXT iteration ---
        sym_total = (s['atk_count']+s['stl_count']+s['shd_count']
                     +s['spn_count']+s['acc_count'])
        hammers += s['atk_count']
        if hammer_level < len(HAMMER_LADDER) - 1:
            if hammers >= HAMMER_LADDER[hammer_level][1]:
                hammer_level += 1
        last10.append(sym_total)

        # Track SPN triple drops for dual-cycle rules
        if is_spn_triple:
            spn_alpha = 0
            spn_drop_seen = True
        elif spn_alpha is not None:
            spn_alpha += 1

        if s['triple'] is not None:
            prev_real_triple = s['triple']
        if is_acc_triple:
            prev_gap_length = cur_sa_spins  # use the pre-spin sa_spins as the gap length
            hammer_level = 0
            hammers = 0

        i += 1

    return {
        'cleared': mission_idx >= len(ladder),
        'pulls_to_clear': None,
        'missions_cleared': mission_idx,
        'final_bankroll': bankroll,
        'end_mission_pts': mission_pts,
        'pulls': pulls,
        'bumps': bumps,
        'catches_on_bump_acc': catches_on_bump_acc,
        'spn_triples_on_bump': spn_triples_on_bump,
        'next_thresh': ladder[mission_idx][0] if mission_idx < len(ladder) else None,
    }


# ---------------------------------------------------------------------------
# Diagnostics — dual-cycle empirical stats
# ---------------------------------------------------------------------------
def print_dualcycle_stats():
    print('=' * 120)
    print('DUAL-CYCLE EMPIRICAL STATS  (test of the 115-spin hypothesis)')
    print('=' * 120)
    for a in ['Islam','Ahmed','Nick']:
        for si in [0,1]:
            sp = get_event_spins(a, si)
            if not sp: continue
            acc_idx = [i for i,s in enumerate(sp) if s.get('triple')=='accumulation']
            spn_idx = [i for i,s in enumerate(sp) if s.get('triple')=='spins']
            # ACC cycle period
            acc_gaps = [acc_idx[i+1]-acc_idx[i] for i in range(len(acc_idx)-1)]
            # Offset test: alpha = spins since last ACC at moment of SPN drop
            #              beta  = spins until next ACC
            sums, alphas, betas = [], [], []
            for sd in spn_idx:
                prev_acc = [a2 for a2 in acc_idx if a2 <= sd]
                next_acc = [a2 for a2 in acc_idx if a2 > sd]
                if prev_acc and next_acc:
                    alpha = sd - prev_acc[-1]
                    beta = next_acc[0] - sd
                    alphas.append(alpha); betas.append(beta); sums.append(alpha+beta)
            line = f'{a} s{si}:'
            if acc_gaps:
                line += (f'  ACC cycle n={len(acc_gaps)} mean={statistics.mean(acc_gaps):.0f} '
                         f'median={sorted(acc_gaps)[len(acc_gaps)//2]} '
                         f'std={statistics.stdev(acc_gaps) if len(acc_gaps)>1 else 0:.0f}')
            if sums:
                med_sum = sorted(sums)[len(sums)//2]
                errors = [abs((med_sum - a) - b) for a,b in zip(alphas,betas)]
                within10 = sum(1 for e in errors if e<=10)
                within20 = sum(1 for e in errors if e<=20)
                line += (f'  | DC sum median={med_sum} std={statistics.stdev(sums) if len(sums)>1 else 0:.0f} '
                         f'pred ±10: {within10}/{len(errors)} ({100*within10/len(errors):.0f}%) '
                         f'±20: {within20}/{len(errors)} ({100*within20/len(errors):.0f}%)')
            print(line)
    print()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def fmt_result(r, total_missions):
    if r['cleared']:
        return f'CLEAR in {r["pulls_to_clear"]:>5,}  final_bk={r["final_bankroll"]:>11,}'
    pct = (r['end_mission_pts']/r['next_thresh']*100) if r['next_thresh'] else 0
    return (f'{r["missions_cleared"]:>2}/{total_missions} ({pct:>3.0f}%)  '
            f'pulls={r["pulls"]:>5,}  bk={r["final_bankroll"]:>9,}')


def run_all(islam_only=False):
    print('=' * 120)
    print('STRATEGY LAB  (chunk 29 rewrite)  —  clearing-focused, Islam-priority')
    print('=' * 120)
    print('Real in-event budgets:')
    print('  Islam s0 = 7,280    Islam s1 = 3,885')
    print('  Ahmed s0 = 6,586    Ahmed s1 = 4,142')
    print('  Nick  s0 =   976    Nick  s1 =   693')
    print()
    print_dualcycle_stats()

    accounts = ['Islam'] if islam_only else ['Islam','Ahmed','Nick']
    scenarios = [('A', 100_000, LADDER_A), ('B', 299_000, LADDER_B)]

    all_results = {}  # (scen, acct, sess) -> {strat_name: result}

    for scen_name, br0, ladder in scenarios:
        print()
        print('=' * 120)
        print(f'  SCENARIO {scen_name}  (start {br0:,} spins, {len(ladder)}-mission ladder)')
        print('=' * 120)
        for acct in accounts:
            for sess in [0, 1]:
                spins = get_event_spins(acct, sess)
                if not spins: continue
                print(f'\n--- {acct} s{sess}  ({len(spins):,} in-event spins) ---')
                all_results[(scen_name, acct, sess)] = {}
                for name, fn, rules in STRATEGIES:
                    r = simulate(spins, br0, ladder, fn, rules)
                    all_results[(scen_name, acct, sess)][name] = r
                    verdict = fmt_result(r, len(ladder))
                    mark = ' <-- CLEAR' if r['cleared'] else ''
                    print(f'  {name:<24s} {verdict}{mark}')

    # ---------- Islam quest ----------
    print()
    print('=' * 120)
    print('  ISLAM CLEARING QUEST  —  did ANY strategy clear for Islam?')
    print('=' * 120)
    islam_clears = []
    for scen, _, ladder in scenarios:
        for sess in [0, 1]:
            key = (scen, 'Islam', sess)
            if key not in all_results: continue
            for name, r in all_results[key].items():
                if r['cleared']:
                    islam_clears.append((scen, sess, name, r['pulls_to_clear'], r['final_bankroll']))
    if islam_clears:
        print(f'  YES — {len(islam_clears)} Islam CLEARING runs:')
        for scen, sess, name, pulls, bk in sorted(islam_clears, key=lambda x: x[3]):
            print(f'    Scen {scen} s{sess} {name:<24s}  {pulls:>5,} pulls  bk={bk:>10,}')
    else:
        print('  NO clear yet. Top 10 Islam attempts by missions cleared:')
        all_islam = []
        for scen, _, ladder in scenarios:
            for sess in [0, 1]:
                key = (scen, 'Islam', sess)
                if key not in all_results: continue
                for name, r in all_results[key].items():
                    all_islam.append((r['missions_cleared'], scen, sess, name, r))
        all_islam.sort(key=lambda x: -x[0])
        seen = set()
        shown = 0
        for mc, scen, sess, name, r in all_islam:
            # Deduplicate by strategy (show best scenario per strat)
            if name in seen: continue
            seen.add(name)
            pct = (r['end_mission_pts']/r['next_thresh']*100) if r['next_thresh'] else 0
            ladder_total = 22 if scen == 'A' else 20
            print(f'    {name:<24s}  best: Scen {scen} s{sess} {mc:>2}/{ladder_total} '
                  f'({pct:>3.0f}% next) pulls={r["pulls"]:>5,} bk={r["final_bankroll"]:>9,}')
            shown += 1
            if shown >= 10: break

    # ---------- All-account summary ----------
    if not islam_only:
        print()
        print('=' * 120)
        print('  PER-ACCOUNT BEST STRATEGIES')
        print('=' * 120)
        for scen, _, ladder in scenarios:
            print(f'\n--- Scenario {scen} ({len(ladder)}M ladder) ---')
            for acct in accounts:
                best_per_sess = {}
                for sess in [0,1]:
                    key = (scen, acct, sess)
                    if key not in all_results: continue
                    for name, r in all_results[key].items():
                        k = (sess, acct)
                        if k not in best_per_sess or r['missions_cleared'] > best_per_sess[k][1]['missions_cleared']:
                            best_per_sess[k] = (name, r)
                for (sess, _), (name, r) in sorted(best_per_sess.items()):
                    pct = (r['end_mission_pts']/r['next_thresh']*100) if r['next_thresh'] else 0
                    mark = ' [CLEAR]' if r['cleared'] else ''
                    print(f'  {acct} s{sess}: best = {name:<24s}  {r["missions_cleared"]:>2}/{len(ladder)} '
                          f'({pct:>3.0f}% next) pulls={r["pulls"]:>5,} bk={r["final_bankroll"]:>9,}{mark}')


if __name__ == '__main__':
    if '--dualcycle' in sys.argv:
        print_dualcycle_stats()
    elif '--islam-only' in sys.argv:
        run_all(islam_only=True)
    else:
        run_all(islam_only=False)
