"""
True cross-validation: train on one account, test on the other.
Also: fine-tune gate thresholds and test higher gate values.
"""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

def load_spins(fp):
    return list(csv.DictReader(open(fp)))

def simulate_on_rows(rows, config):
    base = config['base']
    shift = config['shift']
    center = config['center']
    gate = config.get('gate', None)

    total_acc = 0
    caught = 0
    total_bet = 0
    total_spins = 0
    prev_gap = center

    for row in rows:
        sa = int(row["sa_spins"])
        sa_acc = int(row["sa_acc"])
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        is_acc = (r1 == r2 == r3 == "accumulation")
        acc_rate = sa_acc / sa if sa > 0 else 0.3

        total_spins += 1
        threshold = base - shift * (prev_gap - center)

        should_bet = (sa >= threshold)
        if gate is not None and acc_rate < gate:
            should_bet = False

        if should_bet:
            total_bet += 1

        if is_acc:
            total_acc += 1
            if should_bet:
                caught += 1
            prev_gap = sa

    return total_acc, caught, total_bet, total_spins

# ============================================================
# CROSS-VALIDATION: Train on Acct2, test on Acct3 (and vice versa)
# ============================================================
print("="*60)
print("  CROSS-VALIDATION: Train on one, test on other")
print("="*60, flush=True)

spins = {}
for label, fp in files:
    spins[label] = load_spins(fp)

for train_label, test_label in [("Acct2", "Acct3"), ("Acct3", "Acct2")]:
    print(f"\n  --- Train on {train_label}, Test on {test_label} ---")

    # Find best config on training set
    train_rows = spins[train_label]
    test_rows = spins[test_label]

    # Grid search on training data
    best_no_gate = None
    best_gated = {}  # gate_value -> best config

    for base in range(120, 160, 2):
        for shift_x100 in range(5, 60, 5):
            shift = shift_x100 / 100.0
            for gate_x100 in [0, 24, 26, 28, 30, 32, 34]:
                gate = gate_x100 / 100.0 if gate_x100 > 0 else None
                config = {'base': base, 'shift': shift, 'center': 100, 'gate': gate}
                ta, c, b, t = simulate_on_rows(train_rows, config)
                if c > 0 and b > 0:
                    mb = b / c
                    lift = (c / ta) / (b / t) if b > 0 else 0
                    if gate is None:
                        if best_no_gate is None or lift > best_no_gate[1]:
                            best_no_gate = (config, lift, c, ta, mb, b, t)
                    else:
                        gv = gate_x100
                        if gv not in best_gated or lift > best_gated[gv][1]:
                            best_gated[gv] = (config, lift, c, ta, mb, b, t)

    # Show training results
    if best_no_gate:
        conf, lift, c, ta, mb, b, t = best_no_gate
        print(f"\n  TRAIN best (no gate): base={conf['base']}, shift={conf['shift']:.2f}")
        print(f"    Train: {c}/{ta} caught, {b/t*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

        # Apply to test set
        ta2, c2, b2, t2 = simulate_on_rows(test_rows, conf)
        if c2 > 0 and b2 > 0:
            mb2 = b2 / c2
            lift2 = (c2 / ta2) / (b2 / t2)
            print(f"    TEST:  {c2}/{ta2} caught, {b2/t2*100:.1f}% bet, {mb2:.1f} mb/h, {lift2:.1f}x")

    for gv in sorted(best_gated.keys()):
        conf, lift, c, ta, mb, b, t = best_gated[gv]
        gate_val = gv / 100.0
        print(f"\n  TRAIN best (gate={gate_val}): base={conf['base']}, shift={conf['shift']:.2f}")
        print(f"    Train: {c}/{ta} caught, {b/t*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

        ta2, c2, b2, t2 = simulate_on_rows(test_rows, conf)
        if c2 > 0 and b2 > 0:
            mb2 = b2 / c2
            lift2 = (c2 / ta2) / (b2 / t2)
            print(f"    TEST:  {c2}/{ta2} caught, {b2/t2*100:.1f}% bet, {mb2:.1f} mb/h, {lift2:.1f}x")
        else:
            print(f"    TEST:  {c2}/{ta2} caught, {b2} bet spins (0 lift)")

# ============================================================
# FINE-TUNE GATE: test more gate values
# ============================================================
print(f"\n{'='*60}")
print("  FINE-TUNE: Gate value sweep (all data)")
print("="*60, flush=True)

all_rows = []
for label, fp in files:
    all_rows.extend(load_spins(fp))

for gate_x100 in range(20, 40):
    gate = gate_x100 / 100.0
    # Fix base/shift, sweep gate
    for base in [138, 140, 142, 144, 146]:
        for shift_x100 in [25, 30, 35, 40]:
            shift = shift_x100 / 100.0
            config = {'base': base, 'shift': shift, 'center': 100, 'gate': gate}
            ta, c, b, t = simulate_on_rows(all_rows, config)
            if c >= 10 and b > 0:
                mb = b / c
                lift = (c / ta) / (b / t)
                if lift >= 5.0:
                    print(f"  gate={gate:.2f} base={base} shift={shift:.2f}: {c}/{ta} caught, {b/t*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

# ============================================================
# SIMPLEST POSSIBLE FORMULA
# ============================================================
print(f"\n{'='*60}")
print("  SIMPLEST FORMULA: just gate + fixed threshold")
print("="*60, flush=True)

# No debt shift at all — just spin >= S AND accum_rate >= R
for S in range(100, 160, 5):
    for R_x100 in range(24, 36, 2):
        R = R_x100 / 100.0
        config = {'base': S, 'shift': 0.0, 'center': 100, 'gate': R}
        ta, c, b, t = simulate_on_rows(all_rows, config)
        if c >= 10 and b > 0:
            mb = b / c
            lift = (c / ta) / (b / t)
            if lift >= 3.0:
                print(f"  spin>={S}, rate>={R:.2f}: {c}/{ta} caught, {b/t*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")

# Per-account check for the simplest formulas
print(f"\n  Per-account for simplest formulas:")
for S in [120, 130, 140]:
    for R_x100 in [28, 30, 32]:
        R = R_x100 / 100.0
        config = {'base': S, 'shift': 0.0, 'center': 100, 'gate': R}
        print(f"\n  spin>={S}, rate>={R:.2f}:")
        for label, fp in files:
            rows = load_spins(fp)
            ta, c, b, t = simulate_on_rows(rows, config)
            if b > 0 and c > 0:
                mb = b / c
                lift = (c / ta) / (b / t)
                print(f"    {label}: {c}/{ta} caught, {b/t*100:.1f}% bet, {mb:.1f} mb/h, {lift:.1f}x")
            else:
                print(f"    {label}: {c}/{ta} caught, {b} bet")

print(f"\nDone!", flush=True)
