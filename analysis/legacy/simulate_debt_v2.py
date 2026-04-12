"""
Debt strategy simulator v2 — parameter sweep to find optimal settings.

Key fix: add debt_cap (max negative debt) and watchpoint_max to prevent
runaway watchpoints from short-gap clusters.
"""
import csv

files = [
    ("Acct1", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (1).csv"),
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

QUIET_MIN = 3; QUIET_MAX = 7; BET_WINDOW = 8

class DebtTracker:
    def __init__(self, target, floor_base, floor_min, debt_cap=None, wp_max=None):
        self.target = target
        self.floor_base = floor_base
        self.floor_min = floor_min
        self.debt_cap = debt_cap      # min debt value (e.g., -100 means debt never goes below -100)
        self.wp_max = wp_max          # max watchpoint (e.g., 150)
        self.debt = 0
        self.sa_spins = 0
        self.quiet_spins = 0
        self.quiet_triggered = False
        self.in_quiet_zone = False
        self.bet_spins_used = 0
        self.phase = "WAIT"

    @property
    def watch_point(self):
        wp = max(self.floor_min, self.floor_base - self.debt)
        if self.wp_max is not None:
            wp = min(wp, self.wp_max)
        return wp

    def on_spin(self, is_target, is_other):
        self.sa_spins += 1

        if is_target:
            gap = self.sa_spins
            self.debt += (gap - self.target)
            if self.debt_cap is not None and self.debt < self.debt_cap:
                self.debt = self.debt_cap
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


def load_rows(filepath):
    rows = []
    with open(filepath, "r") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def simulate(all_rows, target, floor_base, floor_min, debt_cap, wp_max, symbol):
    """Run strategy on concatenated rows, return (caught, bet_spins, total_hits, total_spins)"""
    tracker = DebtTracker(target, floor_base, floor_min, debt_cap, wp_max)
    total_spins = 0
    total_hits = 0
    caught = 0
    bet_spins = 0

    is_acc_mode = (symbol == "accumulation")

    for row in all_rows:
        r1 = row.get("reel_1", "")
        r2 = row.get("reel_2", "")
        r3 = row.get("reel_3", "")
        total_spins += 1

        is_triple = (r1 == r2 == r3 and r1 != "")
        is_target = is_triple and r1 == symbol

        if is_acc_mode:
            is_other = is_triple and r1 in ("attack", "steal", "shield", "spins")
        else:
            is_other = is_triple and r1 in ("attack", "steal", "shield", "accumulation")

        prev_phase = tracker.phase
        if tracker.phase == "BET NOW":
            bet_spins += 1

        gap = tracker.on_spin(is_target, is_other)
        if gap is not None:
            total_hits += 1
            if prev_phase == "BET NOW":
                caught += 1

    return caught, bet_spins, total_hits, total_spins


# Load all data
all_rows_per_acct = []
for label, fp in files:
    all_rows_per_acct.append((label, load_rows(fp)))

# ============================================================
#  SWEEP: Find best parameters
# ============================================================
print("=" * 80)
print("  PARAMETER SWEEP — ACC (accumulation)")
print("=" * 80)
print(f"  {'target':>6} {'flrBase':>7} {'flrMin':>6} {'debtCap':>8} {'wpMax':>6} | {'caught':>6} {'hits':>5} {'%':>6} {'betSp':>6} {'mb/hit':>7} {'lift':>5}")
print(f"  {'-'*6} {'-'*7} {'-'*6} {'-'*8} {'-'*6} | {'-'*6} {'-'*5} {'-'*6} {'-'*6} {'-'*7} {'-'*5}")

best_acc = None
best_acc_lift = 0

for target in [90, 95, 100]:
    for floor_base in [60, 70, 80]:
        for floor_min in [20, 30, 40]:
            for debt_cap in [None, -50, -100, -150]:
                for wp_max in [None, 120, 150, 200]:
                    total_caught = 0
                    total_bet = 0
                    total_hits = 0
                    total_spins = 0
                    for label, rows in all_rows_per_acct:
                        c, b, h, s = simulate(rows, target, floor_base, floor_min, debt_cap, wp_max, "accumulation")
                        total_caught += c
                        total_bet += b
                        total_hits += h
                        total_spins += s

                    if total_caught > 0 and total_hits > 0:
                        mb_hit = total_bet / total_caught
                        baseline = total_spins / total_hits
                        lift = baseline / mb_hit if mb_hit > 0 else 0
                        pct = 100 * total_caught / total_hits
                        if lift > best_acc_lift:
                            best_acc_lift = lift
                            best_acc = (target, floor_base, floor_min, debt_cap, wp_max, total_caught, total_hits, pct, total_bet, mb_hit, lift)
                        if lift > 1.0:
                            dc_str = str(debt_cap) if debt_cap else "none"
                            wm_str = str(wp_max) if wp_max else "none"
                            print(f"  {target:>6} {floor_base:>7} {floor_min:>6} {dc_str:>8} {wm_str:>6} | {total_caught:>6} {total_hits:>5} {pct:>5.1f}% {total_bet:>6} {mb_hit:>7.1f} {lift:>5.1f}")

if best_acc:
    print(f"\n  BEST ACC: target={best_acc[0]} floorBase={best_acc[1]} floorMin={best_acc[2]} "
          f"debtCap={best_acc[3]} wpMax={best_acc[4]}")
    print(f"    caught={best_acc[5]}/{best_acc[6]} ({best_acc[7]:.1f}%)  mb/hit={best_acc[9]:.1f}  lift={best_acc[10]:.1f}x")
else:
    print("\n  No ACC config achieved lift > 0")

print(f"\n{'='*80}")
print("  PARAMETER SWEEP — SPN (spins)")
print("=" * 80)
print(f"  {'target':>6} {'flrBase':>7} {'flrMin':>6} {'debtCap':>8} {'wpMax':>6} | {'caught':>6} {'hits':>5} {'%':>6} {'betSp':>6} {'mb/hit':>7} {'lift':>5}")
print(f"  {'-'*6} {'-'*7} {'-'*6} {'-'*8} {'-'*6} | {'-'*6} {'-'*5} {'-'*6} {'-'*6} {'-'*7} {'-'*5}")

best_spn = None
best_spn_lift = 0

for target in [80, 87, 95]:
    for floor_base in [50, 60, 65, 70]:
        for floor_min in [20, 30, 40]:
            for debt_cap in [None, -50, -100, -150]:
                for wp_max in [None, 100, 120, 150]:
                    total_caught = 0
                    total_bet = 0
                    total_hits = 0
                    total_spins = 0
                    for label, rows in all_rows_per_acct:
                        c, b, h, s = simulate(rows, target, floor_base, floor_min, debt_cap, wp_max, "spins")
                        total_caught += c
                        total_bet += b
                        total_hits += h
                        total_spins += s

                    if total_caught > 0 and total_hits > 0:
                        mb_hit = total_bet / total_caught
                        baseline = total_spins / total_hits
                        lift = baseline / mb_hit if mb_hit > 0 else 0
                        pct = 100 * total_caught / total_hits
                        if lift > best_spn_lift:
                            best_spn_lift = lift
                            best_spn = (target, floor_base, floor_min, debt_cap, wp_max, total_caught, total_hits, pct, total_bet, mb_hit, lift)
                        if lift > 1.3:
                            dc_str = str(debt_cap) if debt_cap else "none"
                            wm_str = str(wp_max) if wp_max else "none"
                            print(f"  {target:>6} {floor_base:>7} {floor_min:>6} {dc_str:>8} {wm_str:>6} | {total_caught:>6} {total_hits:>5} {pct:>5.1f}% {total_bet:>6} {mb_hit:>7.1f} {lift:>5.1f}")

if best_spn:
    print(f"\n  BEST SPN: target={best_spn[0]} floorBase={best_spn[1]} floorMin={best_spn[2]} "
          f"debtCap={best_spn[3]} wpMax={best_spn[4]}")
    print(f"    caught={best_spn[5]}/{best_spn[6]} ({best_spn[7]:.1f}%)  mb/hit={best_spn[9]:.1f}  lift={best_spn[10]:.1f}x")
else:
    print("\n  No SPN config achieved lift > 0")


# ============================================================
#  Also test: NO quiet zone (pure debt floor only)
# ============================================================
print(f"\n{'='*80}")
print("  ABLATION: Debt floor only (no quiet zone requirement)")
print("=" * 80)

class DebtTrackerNoQuiet(DebtTracker):
    def on_spin(self, is_target, is_other):
        self.sa_spins += 1
        if is_target:
            gap = self.sa_spins
            self.debt += (gap - self.target)
            if self.debt_cap is not None and self.debt < self.debt_cap:
                self.debt = self.debt_cap
            self.sa_spins = 0
            self.phase = "WAIT"
            return gap

        wp = self.watch_point
        if self.sa_spins < wp:
            self.phase = "WAIT"
        else:
            self.phase = "BET NOW"  # always bet above floor, no quiet needed
        return None

def simulate_no_quiet(all_rows, target, floor_base, floor_min, debt_cap, wp_max, symbol):
    tracker = DebtTrackerNoQuiet(target, floor_base, floor_min, debt_cap, wp_max)
    total_spins = 0; total_hits = 0; caught = 0; bet_spins = 0
    is_acc_mode = (symbol == "accumulation")
    for row in all_rows:
        r1 = row.get("reel_1", ""); r2 = row.get("reel_2", ""); r3 = row.get("reel_3", "")
        total_spins += 1
        is_triple = (r1 == r2 == r3 and r1 != "")
        is_target = is_triple and r1 == symbol
        is_other = False  # not used in NoQuiet
        prev_phase = tracker.phase
        if tracker.phase == "BET NOW":
            bet_spins += 1
        gap = tracker.on_spin(is_target, is_other)
        if gap is not None:
            total_hits += 1
            if prev_phase == "BET NOW":
                caught += 1
    return caught, bet_spins, total_hits, total_spins

print(f"\n  ACC (no quiet zone):")
for target in [90, 95, 100]:
    for floor_base in [60, 70, 80]:
        for debt_cap in [-50, -100, -150]:
            for wp_max in [120, 150, 200]:
                tc = tb = th = ts = 0
                for label, rows in all_rows_per_acct:
                    c, b, h, s = simulate_no_quiet(rows, target, floor_base, 20, debt_cap, wp_max, "accumulation")
                    tc += c; tb += b; th += h; ts += s
                if tc > 0:
                    mb = tb / tc; bl = ts / th; lift = bl / mb
                    pct = 100 * tc / th
                    if lift > 1.2:
                        print(f"    t={target} fb={floor_base} dc={debt_cap} wm={wp_max}: "
                              f"{tc}/{th} ({pct:.1f}%) mb/hit={mb:.1f} lift={lift:.1f}x")

print(f"\n  SPN (no quiet zone):")
for target in [80, 87, 95]:
    for floor_base in [50, 60, 65]:
        for debt_cap in [-50, -100, -150]:
            for wp_max in [100, 120, 150]:
                tc = tb = th = ts = 0
                for label, rows in all_rows_per_acct:
                    c, b, h, s = simulate_no_quiet(rows, target, floor_base, 20, debt_cap, wp_max, "spins")
                    tc += c; tb += b; th += h; ts += s
                if tc > 0:
                    mb = tb / tc; bl = ts / th; lift = bl / mb
                    pct = 100 * tc / th
                    if lift > 1.2:
                        print(f"    t={target} fb={floor_base} dc={debt_cap} wm={wp_max}: "
                              f"{tc}/{th} ({pct:.1f}%) mb/hit={mb:.1f} lift={lift:.1f}x")
