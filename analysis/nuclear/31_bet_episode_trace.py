"""
Chunk 31: Bet-episode trace document.

For every BET_HIGH episode produced by the chunk-30 dup-gated simulator,
emit a block that shows:
  1. 10 reels BEFORE the bet started (the lead-up window)
  2. The spin where the rule first fired (and which rule)
  3. The spin where the back-to-back duplicate was detected
  4. Each pull inside the bet-high window (marked BET N/W)
  5. Any {attack/steal/shield} triple that would trigger a mini-pause
  6. The final outcome — CATCH (target triple landed inside the window)
     or MISS (window expired / non-target triple ended us)

Config (matches chunk-30 "sweet spot"):
  ruleset       = UNION_ALL   (all rules, even the noisy high-mb ones)
  strategy      = dup_gated
  bet_window    = 14           (see chunk-30 sweep)
  mini_pause    = 0            (sweep showed mp > 0 strictly loses catches)

Targets:
  - accumulation
  - spins

Two output files:
  analysis/nuclear/31_bet_trace_acc.txt
  analysis/nuclear/31_bet_trace_spn.txt
"""
from __future__ import annotations
import pickle
import sys
import importlib.util
from collections import deque
from pathlib import Path

HERE = Path(__file__).parent
PKL  = HERE / 'gaps.pkl'

# Pull rules + rulesets from chunk 30 so both scripts stay in sync.
spec = importlib.util.spec_from_file_location(
    'c30', HERE / '30_duplicate_gated_sim.py')
c30 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c30)

UNION_ALL = c30.UNION_ALL
_build_state = c30._build_state
MINI_PAUSE_TRIPLES = c30.MINI_PAUSE_TRIPLES

with open(PKL, 'rb') as f:
    DATA = pickle.load(f)

ACCOUNTS = [a for a in ['Islam', 'Ahmed', 'Nick'] if a in DATA]

BET_WINDOW   = 14
MINI_PAUSE   = 0    # disabled: chunk-30 sweep confirmed mp>0 hurts
LEADUP_SPINS = 10   # per user request: "last 10 reels" context
BET_HIGH_VALUE = 6000


def reel_str(s):
    return f"[{s.get('reel_1',''):12s} | {s.get('reel_2',''):12s} | {s.get('reel_3',''):12s}]"


def trace_episodes(spins, rules, target, bet_window=BET_WINDOW,
                   mini_pause=MINI_PAUSE):
    """Walk `spins` with the dup-gated state machine and emit per-episode
    trace data. Returns a list of episode dicts."""
    prev_real_triple = None
    prev_gap_length  = None
    last10 = deque(maxlen=10)
    spn_alpha = None
    spn_drop_seen = False

    state = 'IDLE'
    bet_counter   = 0
    pause_counter = 0

    # Per-episode capture buffers
    cur_ep = None           # dict or None
    first_fire_idx = None   # index where rule first fired (post-IDLE)
    first_fire_rule = None

    episodes = []

    def _close_episode(outcome, at_idx):
        """Finalize the current episode with an outcome label."""
        nonlocal cur_ep
        if cur_ep is None: return
        cur_ep['outcome']      = outcome
        cur_ep['end_idx']      = at_idx
        episodes.append(cur_ep)
        cur_ep = None

    n = len(spins)
    for i in range(n):
        s = spins[i]

        state_dict = _build_state(
            spins, i, prev_real_triple, prev_gap_length,
            last10, spn_alpha, spn_drop_seen
        )

        # Which rules fire on this spin?
        firing = [name for name, fn in rules if fn(state_dict)]

        # Duplicate check — did spin i-1 match spin i-2?
        is_dup = False
        if i >= 2:
            a = spins[i-1]
            b = spins[i-2]
            is_dup = (a['reel_1']==b['reel_1'] and a['reel_2']==b['reel_2']
                      and a['reel_3']==b['reel_3'])

        # --- State machine (pre-spin decision) ---
        rule_fire_this_spin = None
        dup_fire_this_spin  = False

        if state == 'IDLE' and firing:
            state = 'ARMED'
            first_fire_idx  = i
            first_fire_rule = firing[0]
            rule_fire_this_spin = firing[0]

        if state == 'ARMED' and is_dup:
            # Open a brand-new episode buffer keyed to this BET_HIGH start.
            state = 'BET_HIGH'
            bet_counter = bet_window
            dup_fire_this_spin = True
            leadup_start = max(0, i - LEADUP_SPINS)
            cur_ep = {
                'account': None,   # filled by caller
                'target':  target,
                'bet_start_idx': i,
                'bet_window':    bet_window,
                'rule_fire_idx':  first_fire_idx,
                'rule_fire_name': first_fire_rule,
                'leadup':  list(range(leadup_start, i)),
                'pulls':   [],     # list of (idx, state_label)
                'outcome': None,
                'end_idx': None,
                'rule_firings_in_leadup': [],   # [(idx, [names])]
                'dup_idx': i,      # duplicate was detected at spin i
            }
            # Annotate rule firings over the lead-up
            for j in cur_ep['leadup']:
                sj_state = _build_state(
                    spins, j, None, None, deque(maxlen=10), None, False
                )
                # Best-effort lead-up rule check — use prev_real_triple=None for
                # leadup since we're showing raw context. This is NOT used for
                # the decision, only for display, so it's fine to show any
                # matches regardless of triple context.
                # (Keeping the real state would require replaying the whole
                # history up to j; the simpler raw state is close enough for
                # a display annotation.)

        # Bet this spin
        bet_this_spin = BET_HIGH_VALUE if state == 'BET_HIGH' else 1

        # Record a pull if we're in an episode (BET_HIGH or MINI_PAUSE)
        if cur_ep is not None:
            tag = state
            cur_ep['pulls'].append({
                'idx':   i,
                'state': tag,
                'bet':   bet_this_spin,
                'rule_fire_here': rule_fire_this_spin,
                'dup_fire_here':  dup_fire_this_spin,
            })

        # Observe outcome
        triple_kind = s.get('triple')
        is_target   = (triple_kind == target)

        if is_target:
            if state == 'BET_HIGH':
                _close_episode('CATCH', i)
            elif state == 'MINI_PAUSE':
                _close_episode('MISS_PAUSED', i)
            elif state == 'ARMED' and cur_ep is not None:
                # Shouldn't happen — episode only exists after BET_HIGH
                _close_episode('MISS_ARMED', i)
            # Reset machine
            state = 'IDLE'
            bet_counter = 0
            pause_counter = 0
            first_fire_idx  = None
            first_fire_rule = None
        else:
            if state == 'BET_HIGH':
                bet_counter -= 1
                if triple_kind in MINI_PAUSE_TRIPLES and mini_pause > 0:
                    state = 'MINI_PAUSE'
                    pause_counter = mini_pause
                elif bet_counter <= 0:
                    _close_episode('WINDOW_EXPIRED', i)
                    state = 'IDLE'
                    first_fire_idx  = None
                    first_fire_rule = None
            elif state == 'MINI_PAUSE':
                pause_counter -= 1
                if pause_counter <= 0:
                    state = 'BET_HIGH'
                    bet_counter = bet_window

        # --- Cross-spin state update (same semantics as chunk 30) ---
        sym_total = (s.get('atk_count',0)+s.get('stl_count',0)+s.get('shd_count',0)
                     +s.get('spn_count',0)+s.get('acc_count',0))
        last10.append(sym_total)

        if triple_kind == 'spins':
            spn_alpha = 0
            spn_drop_seen = True
        elif spn_alpha is not None:
            spn_alpha += 1

        if triple_kind is not None:
            prev_real_triple = triple_kind
        if triple_kind == 'accumulation':
            prev_gap_length = state_dict['sa_spins']

    return episodes


def render_episode(ep, ep_num, spins):
    """Turn one episode dict into a human-readable block."""
    L = []
    L.append('=' * 100)
    L.append(f'EPISODE #{ep_num:04d}   account={ep["account"]}   target={ep["target"]}   outcome={ep["outcome"]}')
    L.append('=' * 100)
    L.append(f'  rule fired   : idx={ep["rule_fire_idx"]}  ({ep["rule_fire_name"]})')
    L.append(f'  dup detected : idx={ep["dup_idx"]}  (bet window opens here, w={ep["bet_window"]})')
    L.append(f'  episode end  : idx={ep["end_idx"]}  [{ep["outcome"]}]')
    dist_rule_to_dup   = ep["dup_idx"] - ep["rule_fire_idx"]
    dist_dup_to_end    = ep["end_idx"]  - ep["dup_idx"]
    L.append(f'  rule->dup    : {dist_rule_to_dup} pulls')
    L.append(f'  dup->outcome : {dist_dup_to_end} pulls')
    bet_spins_used = sum(1 for p in ep['pulls'] if p['bet'] > 1)
    L.append(f'  bet-high spins used: {bet_spins_used}')
    L.append('')

    # Lead-up: show 10 spins before the bet started
    L.append('  --- LEAD-UP (10 spins before BET_HIGH opened) ---')
    for idx in ep['leadup']:
        s = spins[idx]
        tags = []
        if idx == ep['rule_fire_idx']:
            tags.append(f'*RULE:{ep["rule_fire_name"]}')
        # Mark dup-eligibility (was this spin half of a duplicate pair?)
        if idx >= 1:
            a, b = spins[idx], spins[idx-1]
            if (a['reel_1']==b['reel_1'] and a['reel_2']==b['reel_2']
                and a['reel_3']==b['reel_3']):
                tags.append('(dup pair with prev)')
        triple_kind = s.get('triple')
        if triple_kind is not None:
            tags.append(f'triple={triple_kind}')
        tag_str = '  ' + '  '.join(tags) if tags else ''
        L.append(f'    idx={idx:>6d}  {reel_str(s)}{tag_str}')

    # Pulls: each BET_HIGH / MINI_PAUSE pull
    L.append('')
    L.append(f'  --- BET-HIGH WINDOW (w={ep["bet_window"]}) ---')
    pull_num = 0
    for p in ep['pulls']:
        idx = p['idx']
        s = spins[idx]
        is_high = p['bet'] > 1
        if is_high:
            pull_num += 1
        bet_lbl = f'BET {pull_num:>2d}/{ep["bet_window"]}' if is_high else 'bet 1x   '
        tags = []
        if p['dup_fire_here']:
            tags.append('*DUP_DETECTED (window opens)')
        triple_kind = s.get('triple')
        if triple_kind is not None:
            if triple_kind == ep['target']:
                tags.append(f'<<< TARGET {triple_kind.upper()} LANDED >>>')
            elif triple_kind in MINI_PAUSE_TRIPLES:
                tags.append(f'<mini-win: {triple_kind}>')
            else:
                tags.append(f'triple={triple_kind}')
        tag_str = '  ' + '  '.join(tags) if tags else ''
        L.append(f'    idx={idx:>6d}  [{p["state"]:<9s}]  {bet_lbl}  {reel_str(s)}{tag_str}')

    L.append('')
    return '\n'.join(L)


def run_all():
    targets = [
        ('accumulation', HERE / '31_bet_trace_acc.txt'),
        ('spins',        HERE / '31_bet_trace_spn.txt'),
    ]

    for target, out_path in targets:
        all_episodes = []
        for acct in ACCOUNTS:
            spins = DATA[acct]['spins']
            eps = trace_episodes(spins, UNION_ALL, target)
            for ep in eps:
                ep['account'] = acct
                ep['_spins_ref'] = spins  # only used for rendering
            all_episodes.extend(eps)

        # Sort: by account, then by bet_start_idx
        all_episodes.sort(key=lambda e: (e['account'], e['bet_start_idx']))

        # Render
        lines = []
        lines.append('#' * 100)
        lines.append(f'#  CHUNK 31: BET-EPISODE TRACE   target = {target.upper()}')
        lines.append('#' * 100)
        lines.append(f'#  ruleset    = UNION_ALL ({len(UNION_ALL)} rules)')
        lines.append(f'#  strategy   = dup_gated')
        lines.append(f'#  bet_window = {BET_WINDOW}  pulls')
        lines.append(f'#  mini_pause = {MINI_PAUSE}  (disabled — chunk 30 sweep)')
        lines.append(f'#  lead-up    = {LEADUP_SPINS} reels shown before each BET_HIGH start')
        lines.append('#')
        lines.append('#  Outcomes:')
        lines.append('#    CATCH          = target triple landed inside the bet-high window')
        lines.append('#    WINDOW_EXPIRED = bet window ran out without catching the target')
        lines.append('#    MISS_PAUSED    = target landed while mini-pause held us at 1x (only if MP>0)')
        lines.append('#')
        # Outcome counts
        by_out = {}
        by_acct = {}
        for ep in all_episodes:
            by_out[ep['outcome']] = by_out.get(ep['outcome'], 0) + 1
            by_acct[ep['account']] = by_acct.get(ep['account'], 0) + 1
        total = len(all_episodes)
        lines.append(f'#  Total episodes: {total}')
        for out_name, count in sorted(by_out.items()):
            lines.append(f'#    {out_name:<16s} {count:>5d} ({100*count/max(1,total):.1f}%)')
        lines.append('#  By account:')
        for a in ACCOUNTS:
            if a in by_acct:
                lines.append(f'#    {a:<10s} {by_acct[a]:>5d}')
        lines.append('#' * 100)
        lines.append('')

        for n, ep in enumerate(all_episodes, 1):
            lines.append(render_episode(ep, n, ep['_spins_ref']))

        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        catches = by_out.get('CATCH', 0)
        print(f'[{target}] {total} episodes ({catches} CATCH), wrote {out_path}')


if __name__ == '__main__':
    run_all()
