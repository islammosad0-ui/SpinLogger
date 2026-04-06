"""
Examine the sa_ and ss_ columns - these might be the game's internal
pity timer state! sa = since accumulation, ss = since spins?
"""
import csv

files = [
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    print(f"\n{'='*60}")
    print(f"  {label}: {len(rows)} rows")
    print(f"{'='*60}")

    # Show sa_ and ss_ columns around ACC triples
    sa_cols = [c for c in rows[0].keys() if c.startswith("sa_")]
    ss_cols = [c for c in rows[0].keys() if c.startswith("ss_")]
    print(f"  sa_ columns: {sa_cols}")
    print(f"  ss_ columns: {ss_cols}")

    # Find ACC triples and show the sa_ values around them
    print(f"\n  Around ACC triples (30,30,30):")
    print(f"  {'idx':>6} {'reels':>25} {'sa_spins':>8} {'sa_acc':>8} {'sa_3x_atk':>10} {'sa_3x_stl':>10} {'sa_3x_shd':>10} {'ss_spins':>8} {'ss_acc':>8}")
    acc_count = 0
    for i, row in enumerate(rows):
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        is_acc_triple = (r1 == r2 == r3 == "accumulation")
        if is_acc_triple:
            acc_count += 1
            # Show 3 rows before and the triple itself
            for j in range(max(0, i-2), min(len(rows), i+3)):
                r = rows[j]
                marker = " <<<" if j == i else ""
                print(f"  {j:>6} {r['reel_1']:>8},{r['reel_2']:>8},{r['reel_3']:>8} "
                      f"{r.get('sa_spins','?'):>8} {r.get('sa_acc','?'):>8} "
                      f"{r.get('sa_3x_atk','?'):>10} {r.get('sa_3x_stl','?'):>10} "
                      f"{r.get('sa_3x_shd','?'):>10} "
                      f"{r.get('ss_spins','?'):>8} {r.get('ss_acc','?'):>8}{marker}")
            print()
            if acc_count >= 5:
                break

    # Now check: does sa_spins reset after ACC triples?
    print(f"\n  sa_spins values at ACC triples:")
    sa_at_triple = []
    for i, row in enumerate(rows):
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        if r1 == r2 == r3 == "accumulation":
            sa_val = row.get("sa_spins", "")
            sa_acc_val = row.get("sa_acc", "")
            sa_at_triple.append((i, sa_val, sa_acc_val))

    for idx, sa, sa_acc in sa_at_triple[:15]:
        print(f"    row {idx}: sa_spins={sa}, sa_acc={sa_acc}")

    # Also check: what do sa_ values look like when NOT at a triple?
    print(f"\n  sa_spins progression (first 30 rows):")
    for i, row in enumerate(rows[:30]):
        print(f"    [{i}] sa_spins={row.get('sa_spins','?')}, sa_acc={row.get('sa_acc','?')}, "
              f"reels={row['reel_1']},{row['reel_2']},{row['reel_3']}")

    # Check: does sa_spins match our gap counting?
    print(f"\n  Gap counting verification:")
    manual_gap = 0
    verified = 0
    for i, row in enumerate(rows[:500]):
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        manual_gap += 1
        sa_val = row.get("sa_spins", "")
        if r1 == r2 == r3 == "accumulation":
            print(f"    ACC triple at row {i}: manual_gap={manual_gap}, sa_spins={sa_val}")
            if sa_val and str(manual_gap) == sa_val:
                verified += 1
            manual_gap = 0
            if verified >= 5 or i > 400:
                break

    # Check the accum_delta column - this might be the key
    print(f"\n  accum_delta values around triples:")
    acc_count = 0
    for i, row in enumerate(rows):
        r1, r2, r3 = row["reel_1"], row["reel_2"], row["reel_3"]
        if r1 == r2 == r3 == "accumulation":
            acc_count += 1
            for j in range(max(0, i-1), min(len(rows), i+2)):
                r = rows[j]
                marker = " <<<" if j == i else ""
                print(f"    [{j}] accum_delta={r.get('accum_delta','?')}, accum_pct={r.get('accum_pct','?')}, "
                      f"accum_current={r.get('accum_current','?')}, accum_total={r.get('accum_total','?')}, "
                      f"accum_mission={r.get('accum_mission','?')}{marker}")
            print()
            if acc_count >= 5:
                break

print("\nDone!", flush=True)
