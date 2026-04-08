#!/usr/bin/env python3
"""
HAR Analysis Report — Coin Master Spin API Response Fields
Generated from analysis of 271 spins across 5 HAR files (Jan-Apr 2026)

This script can be re-run on any new HAR files to extract spin data.
"""

import json
import sys
from collections import Counter
from urllib.parse import unquote

# =============================================================================
# SPIN API RESPONSE — COMPLETE FIELD REFERENCE
# =============================================================================
# POST https://vik-game.moonactive.net/api/v1/users/{userId}/spin
#
# REQUEST PARAMS (x-www-form-urlencoded):
#   Device[udid]       — device UUID
#   API_KEY            — always "viki"
#   API_SECRET         — always "coin"
#   Device[change]     — version string (e.g., "20260126_7")
#   fbToken            — Facebook auth token
#   locale             — "en"
#   seq                — monotonically incrementing sequence number
#   auto_spin          — "True" or "False"
#   bet                — bet multiplier (1, 2, 3, 15, 50, 150, 400, 1500, 6000, 20000)
#   Client[version]    — e.g., "3.5.2390_fbios"
#
# RESPONSE (JSON):
# ==================
#
# CORE SPIN RESULT (always present):
#   r1              int     Reel 1 symbol ID (1-6, 30)
#   r2              int     Reel 2 symbol ID (1-6, 30)
#   r3              int     Reel 3 symbol ID (1-6, 30)
#   reward          int     Reward type: 1=gold, 2=attack, 3=shield, 4=steal, 5=spins, 10=accumulation_triple
#   pay             int     Coins won (0 for non-gold rewards)
#   seq             int     Sequence number (echoed from request)
#
# SYMBOL ID MAP:
#   1 = Coin         (triple -> reward=1, pay=250000 * bet)
#   2 = Gold Sack    (triple -> reward=1, pay=1500000 * bet)
#   3 = Hammer       (triple -> reward=2, attack)
#   4 = Pig/Steal    (triple -> reward=4, raid)
#   5 = Shield       (triple -> reward=3, pay=1)
#   6 = Energy/Spins (triple -> reward=5, pay=spins_won)
#   30 = Accum       (triple -> reward=10, accumulation points)
#
# BALANCE (always present):
#   coins           int     Total coin balance after spin
#   spins           int     Remaining spins after spin
#   shields         int     Current shield count (0-5)
#   maxShields      int     Maximum shields (always 5)
#   fillTime        int     Timestamp when spins will be full (ms)
#   now             int     Server timestamp in milliseconds
#
# BET STATE (always present):
#   superBet        dict    Contains:
#     betLevel      int     Internal bet tier index (e.g., 5, 10, 11)
#     betOptions    list    Available bet multipliers (e.g., [1,2,3,15,50,400,1500,6000,20000])
#
# GAE ACCUMULATION (always present during GAE event):
#   accumulation    dict    Contains:
#     currentAmount       int     Current GAE accumulation points
#     currentAmountNonCapped int  Same as above (no cap observed)
#     totalAmount         int     Points needed for current mission
#     missionIndex        int     Current mission in the GAE map
#     reward              dict    Reward for completing current mission
#     id                  str     Event instance ID
#     event               str     Always "accumulation"
#     accumulatedProgressEnabled bool
#     bonus               dict    (optional) Active bonus details:
#       segment           str     Bonus segment ID (e.g., "bonus_bs15_gae3_no")
#       counter           int     Bonus activation count
#       remainingSeconds  int     Time left on bonus
#       bonusExtraRewards dict    Extra rewards from bonus
#       rewardsCollected  int     (sometimes) Rewards already collected
#       rewardsCollectedLimit int (sometimes) Max rewards from this bonus
#     gaeMapData          dict    Mission map:
#       lastMissionIndex  int     Final mission index (fingerprints GAE list)
#       currentMissionIndex int   Current mission
#       missions          dict    Upcoming mission details (rewards + bonuses)
#
# SECOND SLOT (present in newer versions, Apr 2026+):
#   additionalSlots dict    Contains:
#     second_slot   dict    Contains:
#       reels       list    3 strings, each "" (empty) or event symbol name
#                           e.g., ["LongExtraDayReduced", "GCEaster26", ""]
#                           These are the slot-on-slot (SOS) event reel results
#
# SERIALIZED EVENTS (intermittent, only when SOS symbol matches):
#   serializedEvents dict   Event ID -> event data
#     Each contains:
#       commonResponses list  Contains accumulationBarsById updates
#       (progress data for slot-on-slot events)
#
# EVENT BARS (intermittent, only some spins):
#   accumulationBarsById dict  Bar ID -> bar data
#     Each bar contains:
#       id, currentAmount, totalAmount, rewards, completed, missionIndex,
#       completedMissions, grandPrize, missions, totalMissionCount
#
# CONDITIONAL FIELDS (only with specific reward types):
#   attack          dict    (reward=2 only) Attack target info
#     id, name, image, coins, village, raid_target
#   random          dict    (reward=2 only, older API) Alt image for attack target
#     Same keys as attack but different image format
#   raid            dict    (reward=4 only) Raid target info
#     id, name, image, coins, village, raid_target
#
# OTHER (usually static/constant):
#   messages        list    System messages, promotion events
#   coupons         list    Active store coupons
#   genericRewards  list    Usually empty []
#
# =============================================================================
# REEL PROBABILITY DISTRIBUTIONS (from 271 spins at bet=1)
# =============================================================================
# Reel 1 (r1): 30 appears 17.0% | Coin 23.6% | Attack 32.8%
# Reel 2 (r2): 30 appears  5.2% | GoldSack 21.4% | Coin 23.6%
# Reel 3 (r3): 30 appears  0.7% | GoldSack 40.2% | Coin 19.9%
#
# KEY INSIGHT: Each reel has its OWN probability distribution.
# Symbol 30 is ~24x more common on r1 than r3.
# This is strong evidence for independent weighted reel strips.
#
# =============================================================================
# ACCUMULATION MECHANICS (from HAR data)
# =============================================================================
# - Single 30 on r1: +1 accumulation point * bet
# - Double 30,30,X:  +2 accumulation points * bet
# - Triple 30,30,30: +10 accumulation points * bet (reward=10)
# - Non-30 spins: +0 accumulation points
#
# Accumulation points ONLY come from 30-symbols appearing on reels.
#
# =============================================================================
# WHAT IS NOT IN THE API (searched and confirmed absent)
# =============================================================================
# - No RNG seed, nonce, entropy, or random state
# - No strip index, reel position, or stop position
# - No cycle counter, sequence predictor, or upcoming results
# - No probability weights, strip tables, or reel configurations
# - No phase/mode indicator that changes between spins
# - No hash or token that could be used to predict future spins
#
# The server computes everything server-side and returns ONLY the result.
# The config.segment_slot_probabilities_* and config.segment_core_slot_prob_*
# flags in fullData indicate which probability table the server uses,
# but the actual tables are never sent to the client.
# =============================================================================


def analyze_har(paths):
    """Analyze one or more HAR files for spin data."""
    all_spins = []

    for path in paths:
        with open(path, 'r', encoding='utf-8') as f:
            har = json.load(f)

        for entry in har['log']['entries']:
            url = entry['request']['url']
            if '/spin' not in url:
                continue

            # Parse request
            req_text = entry['request'].get('postData', {}).get('text', '')
            params = {}
            for pair in req_text.split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    params[unquote(k)] = unquote(v)

            # Parse response
            content = entry['response'].get('content', {})
            text = content.get('text', '')
            try:
                resp = json.loads(text)
                resp['_bet'] = int(params.get('bet', 1))
                resp['_auto'] = params.get('auto_spin', '?')
                resp['_file'] = path
                all_spins.append(resp)
            except:
                pass

    if not all_spins:
        print("No spin responses found.")
        return

    print(f"Total spins: {len(all_spins)}")

    # Symbol distributions per reel
    print("\n=== REEL DISTRIBUTIONS ===")
    for pos in ['r1', 'r2', 'r3']:
        counts = Counter(r.get(pos) for r in all_spins)
        total = sum(counts.values())
        print(f"\n  {pos}:")
        for sym in sorted(counts.keys()):
            pct = counts[sym] / total * 100
            print(f"    {sym:>3}: {counts[sym]:>5}x ({pct:5.1f}%)")

    # Triples
    print("\n=== TRIPLES ===")
    for sym in sorted(set(r.get('r1') for r in all_spins)):
        triples = sum(1 for r in all_spins if r.get('r1') == sym and r.get('r2') == sym and r.get('r3') == sym)
        if triples > 0:
            print(f"  Triple {sym:>3}: {triples}x")

    # 30-symbol accumulation
    print("\n=== ACCUMULATION (30-symbol) ANALYSIS ===")
    single_30 = sum(1 for r in all_spins if sum(1 for x in [r.get('r1'), r.get('r2'), r.get('r3')] if x == 30) == 1)
    double_30 = sum(1 for r in all_spins if sum(1 for x in [r.get('r1'), r.get('r2'), r.get('r3')] if x == 30) == 2)
    triple_30 = sum(1 for r in all_spins if sum(1 for x in [r.get('r1'), r.get('r2'), r.get('r3')] if x == 30) == 3)
    print(f"  Single 30: {single_30}x")
    print(f"  Double 30: {double_30}x")
    print(f"  Triple 30: {triple_30}x")

    # All unique top-level keys
    print("\n=== ALL RESPONSE KEYS ===")
    all_keys = set()
    for r in all_spins:
        all_keys.update(r.keys())
    all_keys -= {'_bet', '_auto', '_file'}
    for k in sorted(all_keys):
        present = sum(1 for r in all_spins if k in r)
        print(f"  {k:30s} present in {present}/{len(all_spins)} spins")

    # Spin table
    print("\n=== SPIN TABLE ===")
    print(f"{'#':>4} | {'seq':>6} | {'bet':>4} | {'r1':>3} {'r2':>3} {'r3':>3} | {'rwd':>3} | {'pay':>12} | {'accum':>12}")
    for i, r in enumerate(all_spins):
        r1, r2, r3 = r.get('r1','?'), r.get('r2','?'), r.get('r3','?')
        is_triple = r1 == r2 == r3
        marker = " <<<" if is_triple else ""
        accum = r.get('accumulation', {})
        acc_str = f"{accum.get('currentAmount','?')}/{accum.get('totalAmount','?')}"
        print(f"{i+1:>4} | {r.get('seq','?'):>6} | {r.get('_bet',1):>4} | {r1:>3} {r2:>3} {r3:>3} | {r.get('reward','?'):>3} | {r.get('pay','?'):>12} | {acc_str:>12}{marker}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        analyze_har(sys.argv[1:])
    else:
        # Default: analyze all known HAR files
        default_paths = [
            "C:/Users/Islam/Desktop/Coin Master/New folder/1.har",
            "C:/Users/Islam/Desktop/Coin Master/sample .har",
            "C:/Users/Islam/Desktop/Coin Master/2nd account .har",
            "C:/Users/Islam/Desktop/Coin Master/ccc.har",
            "C:/Users/Islam/Desktop/Coin Master/test.har",
        ]
        analyze_har(default_paths)
