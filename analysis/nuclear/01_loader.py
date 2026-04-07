"""
Nuclear analysis foundation loader.

Loads Islam / Nick / Ahmed CSVs into a clean gap-centric structure.
For each gap we store the full per-spin trajectory of every sa_* and ss_*
counter, plus contextual data. Saves a pickle for downstream sweep scripts.

Gap definition:
  - ACC gap: spins between consecutive (acc,acc,acc) triples. Length is taken
    from sa_spins at the ending row (this includes pre-CSV-recording history,
    so the first gap of each account is recoverable).
  - Other (spn/atk/stl/shd) gap: spins between consecutive triples of that
    type, measured by CSV row index. First incomplete gap is dropped.

Real triple types (game-meaningful): accumulation, spins, attack, steal, shield.
Junk triples (excluded from "real triple" detection): coin, goldSack.
"""
import csv
import pickle
from pathlib import Path

DATA_FILES = {
    'Islam': r'C:\Users\Islam\Downloads\Islam Account spin_history_2026-04-04.csv',
    'Nick':  r'C:\Users\Islam\Downloads\Nick Account spin_history_2026-04-04 (1).csv',
    'Ahmed': r'C:\Users\Islam\Downloads\Ahmed Account spin_history_2026-04-05.csv',
}

REAL_TRIPLES = ['accumulation', 'spins', 'attack', 'steal', 'shield']
TRIPLE_SHORT = {'accumulation': 'acc', 'spins': 'spn', 'attack': 'atk',
                'steal': 'stl', 'shield': 'shd'}
JUNK_TRIPLES = ['coin', 'goldSack']

SA_COUNTERS = ['sa_spins', 'sa_atk', 'sa_stl', 'sa_shd', 'sa_spn', 'sa_acc',
               'sa_3x_atk', 'sa_3x_stl', 'sa_3x_shd']
SS_COUNTERS = ['ss_spins', 'ss_atk', 'ss_stl', 'ss_shd', 'ss_spn', 'ss_acc',
               'ss_3x_atk', 'ss_3x_stl', 'ss_3x_shd']


PER_SPIN_SYM_COUNTS = ['atk_count', 'stl_count', 'shd_count', 'spn_count', 'acc_count']


def safe_int(x, default=0):
    try:
        return int(x)
    except (ValueError, TypeError):
        return default


def safe_float(x, default=0.0):
    try:
        return float(x)
    except (ValueError, TypeError):
        return default


def classify_triple(row):
    """Return triple type symbol if row is a real triple, else None."""
    if row.get('is_triple', '').lower() != 'true':
        return None
    r1, r2, r3 = row.get('reel_1', ''), row.get('reel_2', ''), row.get('reel_3', '')
    if r1 == r2 == r3 and r1 in REAL_TRIPLES:
        return r1
    return None


def classify_any_triple(row):
    """Return any triple symbol (incl. junk), else None."""
    if row.get('is_triple', '').lower() != 'true':
        return None
    r1, r2, r3 = row.get('reel_1', ''), row.get('reel_2', ''), row.get('reel_3', '')
    if r1 == r2 == r3 and r1 in (REAL_TRIPLES + JUNK_TRIPLES):
        return r1
    return None


def load_csv(path):
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def build_spin_records(rows):
    """Build a per-spin enriched record list."""
    out = []
    for idx, row in enumerate(rows):
        rec = {col: safe_int(row.get(col, 0)) for col in SA_COUNTERS + SS_COUNTERS}
        for col in PER_SPIN_SYM_COUNTS:
            rec[col] = safe_int(row.get(col, 0))
        rec['idx'] = idx
        rec['reel_1'] = row.get('reel_1', '')
        rec['reel_2'] = row.get('reel_2', '')
        rec['reel_3'] = row.get('reel_3', '')
        rec['triple'] = classify_triple(row)         # real triples only
        rec['any_triple'] = classify_any_triple(row) # incl. coin/goldSack
        rec['gae_segment'] = row.get('gae_segment', '')
        rec['gae_grand_prize'] = safe_int(row.get('gae_grand_prize', 0))
        rec['gae_last_mission'] = safe_int(row.get('gae_last_mission', 0))
        rec['accum_mission'] = safe_int(row.get('accum_mission', 0))
        rec['accum_pct'] = safe_float(row.get('accum_pct', 0))
        rec['accum_current'] = safe_int(row.get('accum_current', 0))
        rec['accum_total'] = safe_int(row.get('accum_total', 0))
        rec['accum_delta'] = safe_int(row.get('accum_delta', 0))
        rec['bet_multiplier'] = safe_float(row.get('bet_multiplier', 1))
        rec['bet_level'] = safe_int(row.get('bet_level', 0))
        rec['coins_won'] = safe_int(row.get('coins_won', 0))
        rec['shields'] = safe_int(row.get('shields', 0))
        rec['reward_code'] = safe_int(row.get('reward_code', 0))
        # Event type detection: mix event = accum bar moved without acc symbols
        rec['mix_signal'] = (rec['accum_delta'] > 0 and rec['acc_count'] == 0)
        out.append(rec)
    return out


def build_counter_gaps(spins, target, counter_field):
    """
    Gap builder using a specific counter field (sa_spins for ACC, ss_spins for SPN).
    The counter resets on the target triple, so the value at the ending row IS
    the true gap length (including pre-CSV-recording history). The first gap of
    each account is therefore recoverable.
    """
    gaps = []
    last_idx = None
    prev_real_triple = None
    for i, s in enumerate(spins):
        if s['triple'] == target:
            length = s[counter_field]
            csv_traj = spins[(last_idx + 1):(i + 1)] if last_idx is not None else spins[:i + 1]
            gaps.append({
                'target': target,
                'end_idx': i,
                'start_idx': (last_idx + 1) if last_idx is not None else 0,
                'length': length,
                'csv_length': len(csv_traj),
                'is_first_gap': last_idx is None,
                'trajectory': csv_traj,
                'end_event': s['gae_segment'],
                'end_grand_prize': s['gae_grand_prize'],
                'end_mission': s['accum_mission'],
                'end_bet_level': s['bet_level'],
                'end_bet_multiplier': s['bet_multiplier'],
                'prev_real_triple': prev_real_triple,
            })
            last_idx = i
            prev_real_triple = target
        elif s['triple'] is not None:
            prev_real_triple = s['triple']
    return gaps


def build_index_gaps(spins, target):
    """Generic gap builder using CSV row distances. Drops first incomplete gap."""
    gaps = []
    last_idx = None
    prev_real_triple = None
    for i, s in enumerate(spins):
        if s['triple'] == target:
            if last_idx is not None:
                csv_traj = spins[last_idx + 1:i + 1]
                gaps.append({
                    'target': target,
                    'end_idx': i,
                    'start_idx': last_idx + 1,
                    'length': i - last_idx,
                    'csv_length': len(csv_traj),
                    'is_first_gap': False,
                    'trajectory': csv_traj,
                    'end_event': s['gae_segment'],
                    'end_grand_prize': s['gae_grand_prize'],
                    'end_mission': s['accum_mission'],
                    'end_bet_level': s['bet_level'],
                    'end_bet_multiplier': s['bet_multiplier'],
                    'prev_real_triple': prev_real_triple,
                })
            last_idx = i
            prev_real_triple = target
        elif s['triple'] is not None:
            prev_real_triple = s['triple']
    return gaps


def main():
    out_dir = Path(__file__).parent
    out_dir.mkdir(exist_ok=True)

    all_data = {}
    summary = ["=" * 70, "NUCLEAR LOADER - gap inventory", "=" * 70]

    for account, path in DATA_FILES.items():
        rows = load_csv(path)
        spins = build_spin_records(rows)
        acct = {'spins': spins, 'gaps': {}}
        line = f"\n{account}: {len(spins)} spins"
        summary.append(line)
        print(line)

        # ACC uses sa_spins (resets on ACC triple)
        acc_gaps = build_counter_gaps(spins, 'accumulation', 'sa_spins')
        acct['gaps']['accumulation'] = acc_gaps
        if acc_gaps:
            lengths = [g['length'] for g in acc_gaps]
            line = (f"  accumulation : {len(acc_gaps):4d} gaps (sa_spins)  "
                    f"mean={sum(lengths)/len(lengths):6.1f}  "
                    f"min={min(lengths):4d}  max={max(lengths):4d}")
        else:
            line = "  accumulation : 0 gaps"
        summary.append(line)
        print(line)

        # SPN uses ss_spins (resets on SPN triple)
        spn_gaps = build_counter_gaps(spins, 'spins', 'ss_spins')
        acct['gaps']['spins'] = spn_gaps
        if spn_gaps:
            lengths = [g['length'] for g in spn_gaps]
            line = (f"  spins        : {len(spn_gaps):4d} gaps (ss_spins)  "
                    f"mean={sum(lengths)/len(lengths):6.1f}  "
                    f"min={min(lengths):4d}  max={max(lengths):4d}")
        else:
            line = "  spins        : 0 gaps"
        summary.append(line)
        print(line)

        # Other triples use index gaps (no dedicated counter)
        for target in ['attack', 'steal', 'shield']:
            gaps = build_index_gaps(spins, target)
            acct['gaps'][target] = gaps
            if gaps:
                lengths = [g['length'] for g in gaps]
                line = (f"  {target:13s}: {len(gaps):4d} gaps (idx)       "
                        f"mean={sum(lengths)/len(lengths):6.1f}  "
                        f"min={min(lengths):4d}  max={max(lengths):4d}")
            else:
                line = f"  {target:13s}: 0 gaps"
            summary.append(line)
            print(line)

        all_data[account] = acct

    # Dedup signature check
    summary.append("\n--- DEDUP SIGNATURE CHECK (first 50 reels) ---")
    sigs = {}
    for acct, d in all_data.items():
        sig = tuple((s['reel_1'], s['reel_2'], s['reel_3']) for s in d['spins'][:50])
        sigs[acct] = sig
    accts = list(sigs)
    for i in range(len(accts)):
        for j in range(i+1, len(accts)):
            same = sigs[accts[i]] == sigs[accts[j]]
            summary.append(f"  {accts[i]} vs {accts[j]}: {'SAME *** DUP ***' if same else 'different'}")

    # Aggregate gap counts across accounts
    summary.append("\n--- TOTAL GAPS ACROSS ALL 3 ACCOUNTS ---")
    for target in REAL_TRIPLES:
        total = sum(len(d['gaps'][target]) for d in all_data.values())
        summary.append(f"  {target:13s}: {total} gaps")

    pickle_path = out_dir / 'gaps.pkl'
    with open(pickle_path, 'wb') as f:
        pickle.dump(all_data, f)

    summary_path = out_dir / '01_inventory.txt'
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary))

    print(f"\nSaved gap data -> {pickle_path}")
    print(f"Saved summary  -> {summary_path}")


if __name__ == '__main__':
    main()
