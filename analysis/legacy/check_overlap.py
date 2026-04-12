"""Check if Acct1 and Acct2 share data (identical gap context at index 25)."""
import csv

files = [
    ("Acct1", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (1).csv"),
    ("Acct2", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-04 (2).csv"),
    ("Acct3", r"C:\Users\Islam Nawwar\Downloads\spin_history_2026-04-05 (1).csv"),
]

# Load first N rows of each and compare
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    print(f"{label}: {len(rows)} rows")
    # Print first 5 rows
    for i, row in enumerate(rows[:5]):
        print(f"  [{i}] {row.get('reel_1','?')}, {row.get('reel_2','?')}, {row.get('reel_3','?')} | seq={row.get('spin_seq','?')} bet={row.get('bet_level','?')}")
    # Print last 3 rows
    print(f"  ...")
    for i, row in enumerate(rows[-3:]):
        print(f"  [{len(rows)-3+i}] {row.get('reel_1','?')}, {row.get('reel_2','?')}, {row.get('reel_3','?')} | seq={row.get('spin_seq','?')}")
    print()

# Check overlap: compare spin sequences
print("=== Overlap check ===")
for i, (l1, fp1) in enumerate(files):
    rows1 = list(csv.DictReader(open(fp1)))
    seqs1 = [r.get("spin_seq", r.get("seq", "")) for r in rows1]
    reels1 = [(r["reel_1"], r["reel_2"], r["reel_3"]) for r in rows1]

    for j, (l2, fp2) in enumerate(files):
        if j <= i: continue
        rows2 = list(csv.DictReader(open(fp2)))
        seqs2 = [r.get("spin_seq", r.get("seq", "")) for r in rows2]
        reels2 = [(r["reel_1"], r["reel_2"], r["reel_3"]) for r in rows2]

        # Check if reels overlap
        # Compare first 100 reels of file1 vs start of file2
        match_start = 0
        for offset in range(len(reels2)):
            if reels2[offset:offset+min(20, len(reels1))] == reels1[:min(20, len(reels1))]:
                match_start = offset
                print(f"  {l1} starts at offset {offset} in {l2}")
                break

        # Also try if file1 is contained in file2
        # Check reel tuples of first 50 from file1 against all of file2
        r1_first50 = reels1[:50]
        for offset in range(len(reels2) - 50):
            if reels2[offset:offset+50] == r1_first50:
                print(f"  MATCH: {l1}[0:50] == {l2}[{offset}:{offset+50}]")
                # Check how far the overlap extends
                overlap_len = 0
                for k in range(min(len(reels1), len(reels2) - offset)):
                    if reels1[k] == reels2[offset + k]:
                        overlap_len += 1
                    else:
                        break
                print(f"    Overlap length: {overlap_len} / {len(reels1)} rows of {l1}")
                print(f"    {l1} has {len(reels1)} rows, {l2} has {len(reels2)} rows")
                if overlap_len == len(reels1):
                    print(f"    ==> {l1} is FULLY CONTAINED in {l2}!")
                break
        else:
            # No match found in first 50
            # Try comparing spin_seq values
            seq_set1 = set(seqs1[:100])
            seq_overlap = sum(1 for s in seqs2[:100] if s in seq_set1)
            if seq_overlap > 10:
                print(f"  {l1} vs {l2}: {seq_overlap}/100 seq overlaps in first 100")
            else:
                print(f"  {l1} vs {l2}: NO overlap detected")

# Also check: do the CSV headers have any identifying info?
print("\n=== CSV headers ===")
for label, fp in files:
    rows = list(csv.DictReader(open(fp)))
    if rows:
        print(f"{label}: columns = {list(rows[0].keys())}")
