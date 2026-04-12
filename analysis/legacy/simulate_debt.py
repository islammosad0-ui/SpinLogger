import csv, sys

files = [
    ("Acct1", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (1).csv"),
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

# Strategy parameters (matching SLDebtTracker defaults)
ACC_TARGET = 100; ACC_FLOOR_BASE = 80; ACC_FLOOR_MIN = 20
SPN_TARGET = 87;  SPN_FLOOR_BASE = 65; SPN_FLOOR_MIN = 20
QUIET_MIN = 3; QUIET_MAX = 7; BET_WINDOW = 8

class DebtTracker:
    def __init__(self, target, floor_base, floor_min):
        self.target = target
        self.floor_base = floor_base
        self.floor_min = floor_min
        self.debt = 0
        self.sa_spins = 0
        self.quiet_spins = 0
        self.quiet_triggered = False
        self.in_quiet_zone = False
        self.bet_spins_used = 0
        self.phase = "WAIT"

    @property
    def watch_point(self):
        return max(self.floor_min, self.floor_base - self.debt)

    def on_spin(self, is_target, is_other):
        self.sa_spins += 1

        if is_target:
            gap = self.sa_spins
            self.debt += (gap - self.target)
            self.sa_spins = 0
            self.quiet_spins = 0
            self.quiet_triggered = False
            self.in_quiet_zone = False
            self.bet_spins_used = 0
            self.phase = "WAIT"
            return gap

        if is_other:
            self.quiet_triggered = True
            self.quiet_spins = 0
            self.in_quiet_zone = False

        if self.quiet_triggered and not is_other:
            self.quiet_spins += 1
            self.in_quiet_zone = (QUIET_MIN <= self.quiet_spins <= QUIET_MAX)

        wp = self.watch_point
        if self.sa_spins < wp:
            self.phase = "WAIT"
            self.bet_spins_used = 0
        elif self.in_quiet_zone and self.bet_spins_used < BET_WINDOW:
            if self.phase != "BET NOW":
                self.bet_spins_used = 0
            self.phase = "BET NOW"
            self.bet_spins_used += 1
        else:
            self.phase = "WATCH"

        return None


def simulate_file(label, filepath):
    rows = []
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    acc_tracker = DebtTracker(ACC_TARGET, ACC_FLOOR_BASE, ACC_FLOOR_MIN)
    spn_tracker = DebtTracker(SPN_TARGET, SPN_FLOOR_BASE, SPN_FLOOR_MIN)

    total_spins = 0
    acc_hits = []
    spn_hits = []
    acc_bet_now_spins = 0
    spn_bet_now_spins = 0
    acc_watch_spins = 0
    spn_watch_spins = 0

    for i, row in enumerate(rows):
        r1 = row.get("reel_1", "")
        r2 = row.get("reel_2", "")
        r3 = row.get("reel_3", "")
        total_spins += 1

        is_triple = (r1 == r2 == r3 and r1 != "")

        # ACC
        is_acc = is_triple and r1 == "accumulation"
        is_combat_not_acc = is_triple and r1 in ("attack", "steal", "shield", "spins")

        prev_acc_phase = acc_tracker.phase
        if acc_tracker.phase == "BET NOW":
            acc_bet_now_spins += 1
        elif acc_tracker.phase == "WATCH":
            acc_watch_spins += 1

        gap = acc_tracker.on_spin(is_acc, is_combat_not_acc)
        if gap is not None:
            acc_hits.append((gap, prev_acc_phase == "BET NOW", prev_acc_phase == "WATCH", i))

        # SPN
        is_spn = is_triple and r1 == "spins"
        is_combat_not_spn = is_triple and r1 in ("attack", "steal", "shield", "accumulation")

        prev_spn_phase = spn_tracker.phase
        if spn_tracker.phase == "BET NOW":
            spn_bet_now_spins += 1
        elif spn_tracker.phase == "WATCH":
            spn_watch_spins += 1

        gap = spn_tracker.on_spin(is_spn, is_combat_not_spn)
        if gap is not None:
            spn_hits.append((gap, prev_spn_phase == "BET NOW", prev_spn_phase == "WATCH", i))

    # --- Report ---
    print(f"\n{'='*70}")
    print(f"  {label}: {filepath.split(chr(92))[-1]}  ({total_spins} spins)")
    print(f"{'='*70}")

    for sym, hits, bet_spins, watch_spins, tracker in [
        ("ACC (accumulation)", acc_hits, acc_bet_now_spins, acc_watch_spins, acc_tracker),
        ("SPN (spins)",        spn_hits, spn_bet_now_spins, spn_watch_spins, spn_tracker),
    ]:
        total_hits = len(hits)
        caught_bet = sum(1 for _, b, _, _ in hits if b)
        caught_watch = sum(1 for _, _, w, _ in hits if w)
        missed = total_hits - caught_bet - caught_watch

        if total_hits == 0:
            print(f"\n  {sym}: 0 triples found")
            continue

        gaps = [g for g, _, _, _ in hits]
        avg_gap = sum(gaps) / len(gaps)

        baseline_mb = total_spins / total_hits if total_hits > 0 else 0

        strategy_mb = bet_spins / caught_bet if caught_bet > 0 else float("inf")
        lift = baseline_mb / strategy_mb if strategy_mb > 0 and strategy_mb != float("inf") else 0

        print(f"\n  {sym}")
        print(f"  {'-'*50}")
        print(f"  Total triples:      {total_hits}")
        print(f"  Avg gap:            {avg_gap:.1f} spins")
        print(f"  Min/Max gap:        {min(gaps)} / {max(gaps)}")
        print(f"  Final debt:         {tracker.debt:+d}")
        print(f"  ")
        print(f"  BET NOW caught:     {caught_bet}/{total_hits} ({100*caught_bet/total_hits:.1f}%)")
        print(f"  WATCH caught:       {caught_watch}/{total_hits} ({100*caught_watch/total_hits:.1f}%)")
        print(f"  Missed (WAIT):      {missed}/{total_hits} ({100*missed/total_hits:.1f}%)")
        print(f"  ")
        print(f"  BET NOW spins:      {bet_spins} ({100*bet_spins/total_spins:.1f}% of all spins)")
        print(f"  Baseline (random):  {baseline_mb:.1f} max-bet spins per hit")
        if caught_bet > 0:
            print(f"  Strategy:           {strategy_mb:.1f} max-bet spins per hit")
            print(f"  Lift vs random:     {lift:.1f}x")
        else:
            print(f"  Strategy:           no BET NOW catches")

        print(f"\n  Hit-by-hit:")
        print(f"  {'#':>3}  {'Gap':>5}  {'Phase':>8}  {'Debt after':>10}  {'WatchPt':>8}")
        running_debt = 0
        for j, (g, b, w, idx) in enumerate(hits):
            prev_debt = running_debt
            running_debt += (g - tracker.target)
            phase = "BET NOW" if b else ("WATCH" if w else "WAIT")
            wp = max(tracker.floor_min, tracker.floor_base - prev_debt)
            print(f"  {j+1:>3}  {g:>5}  {phase:>8}  {running_debt:>+10d}  {wp:>8}")

    return total_spins, acc_hits, spn_hits, acc_bet_now_spins, spn_bet_now_spins


# Run all 3
all_acc_hits = []
all_spn_hits = []
total_all = 0
total_acc_bet = 0
total_spn_bet = 0

for label, fp in files:
    ts, ah, sh, ab, sb = simulate_file(label, fp)
    total_all += ts
    all_acc_hits.extend(ah)
    all_spn_hits.extend(sh)
    total_acc_bet += ab
    total_spn_bet += sb

# Combined summary
print(f"\n{'='*70}")
print(f"  COMBINED SUMMARY ({total_all} spins, 3 accounts)")
print(f"{'='*70}")

for sym, hits, bet_spins in [("ACC", all_acc_hits, total_acc_bet), ("SPN", all_spn_hits, total_spn_bet)]:
    total_hits = len(hits)
    caught = sum(1 for _, b, _, _ in hits if b)
    if total_hits == 0:
        print(f"\n  {sym}: 0 triples")
        continue
    gaps = [g for g, _, _, _ in hits]
    baseline = total_all / total_hits
    strat = bet_spins / caught if caught > 0 else float("inf")
    lift = baseline / strat if strat > 0 and strat != float("inf") else 0
    catch_pct = 100 * caught / total_hits
    print(f"\n  {sym}: {total_hits} triples, {caught} caught by BET NOW ({catch_pct:.1f}%)")
    print(f"    Avg gap: {sum(gaps)/len(gaps):.1f}  |  BET NOW spins: {bet_spins}  |  mb/hit: {strat:.1f}  |  Lift: {lift:.1f}x")
