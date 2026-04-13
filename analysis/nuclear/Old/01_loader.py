import csv
import pickle
from pathlib import Path

# --- AUTOMATED DATA SCANNER ---
BASE_DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_FILES = {}
for account in ['Islam', 'Nick', 'Ahmed']:
    acc_dir = BASE_DATA_DIR / account
    if acc_dir.exists():
        paths = list(acc_dir.glob("*.csv"))
        DATA_FILES[account] = [str(p) for p in paths if "spin_history" in p.name.lower()]
    else:
        DATA_FILES[account] = []

REAL_TRIPLES = ['accumulation', 'spins', 'attack', 'steal', 'shield']
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
    if row.get('is_triple', '').lower() != 'true':
        return None
    r1, r2, r3 = row.get('reel_1', ''), row.get('reel_2', ''), row.get('reel_3', '')
    if r1 == r2 == r3 and r1 in REAL_TRIPLES:
        return r1
    return None

def build_spin_records(rows):
    out = []
    for idx, row in enumerate(rows):
        rec = {col: safe_int(row.get(col, 0)) for col in SA_COUNTERS + SS_COUNTERS}
        for col in PER_SPIN_SYM_COUNTS:
            rec[col] = safe_int(row.get(col, 0))
        rec['seq'] = safe_int(row.get('seq', 0))
        rec['reel_1'] = row.get('reel_1', '')
        rec['reel_2'] = row.get('reel_2', '')
        rec['reel_3'] = row.get('reel_3', '')
        rec['triple'] = classify_triple(row)
        rec['accum_mission'] = safe_int(row.get('accum_mission', 0))
        rec['accum_delta'] = safe_int(row.get('accum_delta', 0))
        rec['bet_multiplier'] = safe_float(row.get('bet_multiplier', 1))
        rec['bet_level'] = safe_int(row.get('bet_level', 0))
        rec['gae_segment'] = row.get('gae_segment', '')
        rec['gae_grand_prize'] = safe_int(row.get('gae_grand_prize', 0))
        out.append(rec)
    return out

def build_counter_gaps(spins, target, counter_field):
    gaps = []
    last_idx = None
    p1, p2 = 0, 0
    prev_triple = "none"
    event_id = 0
    for i, s in enumerate(spins):
        # Only increment event_id on MAJOR sequence jumps (New Session)
        if i > 0 and abs(s['seq'] - spins[i-1]['seq']) > 1000:
            event_id += 1
            p1, p2 = 0, 0 # Reset cycle history for new event
            
        if s['triple'] == target:
            length = s[counter_field]
            csv_traj = spins[(last_idx + 1):(i + 1)] if last_idx is not None else spins[:i + 1]
            gaps.append({
                'target': target,
                'length': length,
                'prev_gap_1': p1,
                'prev_gap_2': p2,
                'prev_real_triple': prev_triple,
                'event_id': event_id,
                'is_first_gap': (last_idx is None) or (i > 0 and abs(s['seq'] - spins[i-1]['seq']) > 1000),
                'trajectory': csv_traj
            })
            last_idx = i
            p2 = p1; p1 = length
            prev_triple = target
        elif s['triple'] is not None:
            prev_triple = s['triple']
    return gaps

def build_index_gaps(spins, target):
    gaps = []
    last_idx = None
    p1, p2 = 0, 0
    prev_triple = "none"
    event_id = 0
    for i, s in enumerate(spins):
        # Index gaps are harder to detect events, but we can use Seq ID jumps
        if i > 0 and abs(s['seq'] - spins[i-1]['seq']) > 500:
            event_id += 1
            p1, p2 = 0, 0

        if s['triple'] == target:
            if last_idx is not None:
                csv_traj = spins[last_idx + 1:i + 1]
                gaps.append({
                    'target': target,
                    'length': i - last_idx,
                    'prev_gap_1': p1,
                    'prev_gap_2': p2,
                    'prev_real_triple': prev_triple,
                    'event_id': event_id,
                    'is_first_gap': False,
                    'trajectory': csv_traj
                })
                p2 = p1
                p1 = i - last_idx
            last_idx = i
            prev_triple = target
        elif s['triple'] is not None:
            prev_triple = s['triple']
    return gaps

def main():
    out_dir = Path(__file__).parent
    all_data = {}
    summary = ["=== SMART NUCLEAR LOADER ==="]

    for account, paths in DATA_FILES.items():
        if not paths: continue

        # 1. Load and Fingerprint
        all_raw_rows = []
        for p in paths:
            with open(p, 'r', encoding='utf-8') as f:
                all_raw_rows.extend(list(csv.DictReader(f)))
        
        # Deduplicate by 'seq'
        unique_rows = {}
        for row in all_raw_rows:
            seq = safe_int(row.get('seq'))
            if seq not in unique_rows:
                unique_rows[seq] = row
        
        # Sort by 'seq' so the timeline is perfectly chronological
        sorted_keys = sorted(unique_rows.keys())
        sorted_rows = [unique_rows[k] for k in sorted_keys]
        
        # Convert to records
        all_spins = build_spin_records(sorted_rows)

        # 2. Split into Sessions based on mission reset
        sessions = []
        current_session = []
        prev_mission = -1
        
        for s in all_spins:
            # If mission drops, it's a new event/session
            if s['accum_mission'] < prev_mission and prev_mission != -1:
                if current_session: sessions.append(current_session)
                current_session = []
            
            current_session.append(s)
            prev_mission = s['accum_mission']
        
        if current_session: sessions.append(current_session)

        # 3. Build Gaps per Session
        total_acc = []
        total_spn = []
        total_atk = []
        total_stl = []
        total_shd = []

        for sess in sessions:
            total_acc.extend(build_counter_gaps(sess, 'accumulation', 'sa_spins'))
            total_spn.extend(build_counter_gaps(sess, 'spins', 'ss_spins'))
            total_atk.extend(build_index_gaps(sess, 'attack'))
            total_stl.extend(build_index_gaps(sess, 'steal'))
            total_shd.extend(build_index_gaps(sess, 'shield'))

        all_data[account] = {'spins': all_spins, 'gaps': {
            'accumulation': total_acc,
            'spins': total_spn,
            'attack': total_atk,
            'steal': total_stl,
            'shield': total_shd,
        }}

        line = f"\n{account}: {len(all_spins)} unique spins across {len(sessions)} detected events."
        summary.append(line); print(line)
        summary.append(f"  Total Gaps: ACC={len(total_acc)}, SPN={len(total_spn)}")

    with open(out_dir / 'gaps.pkl', 'wb') as f:
        pickle.dump(all_data, f)
    
    with open(out_dir / '01_inventory.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(summary))

if __name__ == '__main__':
    main()
