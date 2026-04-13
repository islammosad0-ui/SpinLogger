import pickle
import os

REAL_TRIPLES = ['attack', 'steal', 'shield', 'spins', 'accumulation']

def get_triple(s):
    r1, r2, r3 = s.get('reel_1', ''), s.get('reel_2', ''), s.get('reel_3', '')
    if r1 == r2 == r3 and r1 in REAL_TRIPLES:
        return r1
    return None

def run_raw_tracer(acct="Islam"):
    with open(r"C:\Users\Islam Nawwar\SpinLogger\analysis\nuclear\gaps.pkl", "rb") as f:
        all_data = pickle.load(f)

    if acct not in all_data:
        print(f"Account {acct} not found."); return

    fname = f"C:\\Users\\Islam Nawwar\\SpinLogger\\analysis\\nuclear\\trace_{acct}.txt"
    with open(fname, "w", encoding="utf-8") as out:
        out.write(f"=== FULL GAP-BY-GAP TRACE: {acct.upper()} ===\n\n")

        for target in ['accumulation', 'spins']:
            gaps = all_data[acct]['gaps'].get(target, [])
            if not gaps: continue
            out.write(f"{'#'*120}\n TARGET: {target.upper()}\n{'#'*120}\n\n")
            
            for g_idx, g in enumerate(gaps):
                traj = g['trajectory']
                p1, p2 = g.get('prev_gap_1', 0), g.get('prev_gap_2', 0)
                eid = g.get('event_id', 0)
                
                out.write(f"E{eid} | Gap #{g_idx:03d} | Len: {len(traj):3d} | P1: {p1:d} | P2: {p2:d}\n")
                
                for i, s in enumerate(traj):
                    r1, r2, r3 = s['reel_1'], s['reel_2'], s['reel_3']
                    is_dup = (i > 0 and r1 == traj[i-1]['reel_1'] and r2 == traj[i-1]['reel_2'] and r3 == traj[i-1]['reel_3'])
                    triple = get_triple(s)
                    
                    tag = "[   SPIN     ]"
                    if triple: tag = f"[ !!! {triple.upper()[:8]:8s} !!! ]"
                    
                    highlight = ""
                    if triple: highlight += " <--- !!! TRIPLE HIT !!!"
                    if is_dup: highlight += " (REEL DUP!)"
                    
                    # Vertical Bar Layout matching strategy_sim exactly
                    t_val = i - (len(traj) - 1)
                    out.write(f"    T{t_val:+04d} | SEQ:{str(s['seq']):6s} | POS:{str(s['sa_spins']).rjust(3)} | {tag:14s} | [{r1:8s}|{r2:8s}|{r3:8s}]{highlight}\n")
                
                out.write("-" * 120 + "\n\n")

    print(f"Gap-Structured trace generated: trace_{acct}.txt")

if __name__ == "__main__":
    run_raw_tracer("Islam")
