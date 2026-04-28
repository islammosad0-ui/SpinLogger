#!/usr/bin/env python3
"""Per-cycle FIRE/WAIT trace for the v4 K5_DYN policy.

Mirrors the format of analysis/nuclear/New_idx_trace/trace_<acct>.txt: one
header per gap (cycle), then one line per spin in the cycle showing position,
predicted probability, active threshold, and verdict. Cycle outcome (CAUGHT
vs MISSED) appended at the bottom.

Generates one trace per (account, mode) combination using the same CV
predictions and schedules that ship in the IPA.
"""

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RUNS = {
    "Ahmed": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Ahmed/spin_predictions_all_combos.csv",
    "Islam": ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211318_Islam/spin_predictions_all_combos.csv",
    "Nick":  ROOT / "analysis/output_tail_risk_v4_hazard_plus/v4-20260426_211319_Nick/spin_predictions_all_combos.csv",
}
BUNDLE = json.loads((ROOT / "assets/dyn_aggr_schedules.json").read_text(encoding="utf-8"))
OUT_DIR = ROOT / "analysis/output_v4_traces"
OUT_DIR.mkdir(exist_ok=True)


def thr_at(schedule, t):
    for b in schedule:
        if b["t_min"] <= t <= b["t_max"]:
            return b["thr"]
    return 0.99


def trace_account(acct, df, mode, schedule, head_col="p_y_any_next5",
                  K_horizon=5, max_bet_spins=25):
    """Emit a per-cycle trace for one (account, mode) using SIMULATOR semantics.

    Realistic catch rule (matches simulate_threshold in tail_risk_v4_hazard_plus.py):
        Walk the fires in time order. Each fire = one bet. After max_bet_spins
        bets, stop. A cycle is CAUGHT iff one of those bets landed on the spin
        directly before the VT (spins_to_vt == 1).

    Useful-fire rule (model-promise check):
        A fire at position t is "USEFUL" iff spins_to_vt at t is in [1..K_horizon]
        (the VT lands within the next K spins, matching the K=5 model head).
    """
    df = df.sort_values(["session_id", "cycle_id", "t"]).reset_index(drop=True)
    out_lines = []

    out_lines.append("=" * 110)
    out_lines.append(f"  V4 K5_DYN TRACE — account={acct}  mode={mode}")
    out_lines.append("=" * 110)
    out_lines.append(f"  Predictor head : ANY_VT (p_y_any_next5)  K_horizon={K_horizon}")
    out_lines.append(f"  Schedule       : {schedule}")
    out_lines.append(f"  Window gate    : t in [15, 100]")
    out_lines.append(f"  Bet workflow   : each FIRE = one bet (spin); stop after VT lands")
    out_lines.append(f"                   or after {max_bet_spins} bets in this cycle")
    out_lines.append(f"  Result legend  :")
    out_lines.append(f"    CAUGHT     - a bet landed on spins_to_vt=1 (caught the VT)")
    out_lines.append(f"    EARLY_FIRE - fired but every fire was too early to catch (model wrong)")
    out_lines.append(f"    NO_FIRE    - policy never fired in this cycle")
    out_lines.append("")

    cycles = list(df.groupby("cycle_id", sort=False))
    prev1 = prev2 = None
    n_caught = n_early = n_no_fire = 0
    total_bets = 0
    n_useful_fire_cycles = 0   # cycles where at least one fire had spins_to_vt<=K
    total_useful_fires = 0

    for cyc_id, g in cycles:
        g = g.sort_values("t").reset_index(drop=True)
        cycle_len = int(g["t"].max()) + 2   # +1 for 0-indexed, +1 for VT spin itself
        end_sym = (g["cycle_end_symbol"].iloc[0] or "").strip() or "?"
        session_id = g["session_id"].iloc[0]
        cycle_start_seq = int(g["cycle_start_seq"].iloc[0])
        cycle_end_seq   = int(g["cycle_end_seq"].iloc[0])

        ts = g["t"].astype(int).to_numpy()
        ps = g[head_col].astype(float).to_numpy()
        s2v = g["spins_to_vt"].astype(int).to_numpy()
        thrs = [thr_at(schedule, int(t)) if 15 <= t <= 100 else 0.99 for t in ts]
        fires = [bool(p >= thr) for p, thr in zip(ps, thrs)]

        # Simulator: walk fires, count bets, catch if one is at spins_to_vt==1
        bets = 0
        caught_at = None
        for i, fire in enumerate(fires):
            if not fire:
                continue
            if bets >= max_bet_spins:
                break
            bets += 1
            if s2v[i] == 1:
                caught_at = int(ts[i])
                break

        # Useful-fire counts (regardless of stop logic)
        useful_fires = [int(t) for t, f, k in zip(ts, fires, s2v) if f and 1 <= k <= K_horizon]
        n_fires_total = sum(fires)
        first_fire_t = next((int(t) for t, f in zip(ts, fires) if f), None)

        if caught_at is not None:
            result = "CAUGHT"
            n_caught += 1
        elif n_fires_total == 0:
            result = "NO_FIRE"
            n_no_fire += 1
        else:
            result = "EARLY_FIRE"
            n_early += 1
        total_bets += bets
        if useful_fires:
            n_useful_fire_cycles += 1
            total_useful_fires += len(useful_fires)

        prev1_str = f"{prev1}" if prev1 is not None else "—"
        prev2_str = f"{prev2}" if prev2 is not None else "—"

        out_lines.append(
            f"Gap #{cyc_id:>04}  Len={cycle_len:3d}  Prev1={prev1_str:>4}  Prev2={prev2_str:>4}  "
            f"EndSym={end_sym}  Fires={n_fires_total:2d}  Bets={bets:2d}  "
            f"FirstFire@t={first_fire_t}  Result={result}"
        )
        out_lines.append(
            f"  session={session_id}  start_seq={cycle_start_seq}  end_seq={cycle_end_seq}"
        )

        # Per-spin tape with FIRE/WAIT and a marker on the catch spin or VT spin
        bets_walked = 0
        for t, p, thr, fire, k in zip(ts, ps, thrs, fires, s2v):
            if fire:
                if bets_walked < bets:
                    tag = f"[ BET#{bets_walked+1} ]"
                    bets_walked += 1
                else:
                    tag = "[ FIRE ]"     # would-fire but past max_bet_spins
            else:
                tag = "[ wait  ]"
            marker = ""
            if caught_at is not None and t == caught_at:
                marker = f"  <-- *** CAUGHT *** ({end_sym} on next spin)"
            elif fire and 1 <= k <= K_horizon:
                marker = f"  <-- useful fire (VT in {k})"
            elif t == ts[-1]:
                marker = f"  <-- {end_sym} on next spin"
            out_lines.append(
                f"    POS={int(t):3d}  p5={p:6.3f}  thr={thr:5.2f}  {tag}{marker}"
            )
        out_lines.append("-" * 110)
        out_lines.append("")

        prev2 = prev1
        prev1 = cycle_len

    out_lines.append("=" * 110)
    out_lines.append(f"  SUMMARY ({acct} / mode={mode})")
    out_lines.append("=" * 110)
    n_total = len(cycles)
    catch_pct = (n_caught / n_total * 100) if n_total else 0
    bets_per_vt = (total_bets / n_caught) if n_caught else float("nan")
    out_lines.append(f"  cycles            : {n_total}")
    out_lines.append(f"  CAUGHT            : {n_caught}  ({catch_pct:.2f}% of all cycles)")
    out_lines.append(f"  EARLY_FIRE (miss) : {n_early}  (fired but every fire was too early)")
    out_lines.append(f"  NO_FIRE           : {n_no_fire}")
    out_lines.append(f"  total bets        : {total_bets}")
    out_lines.append(f"  Bets/VT           : {bets_per_vt:.2f}")
    out_lines.append(f"  cycles w/ useful  : {n_useful_fire_cycles}  (≥1 fire within K={K_horizon} of VT)")
    out_lines.append(f"  total useful fires: {total_useful_fires}")
    out_lines.append("")

    return "\n".join(out_lines), {
        "cycles": n_total, "caught": n_caught, "early": n_early, "no_fire": n_no_fire,
        "bets": total_bets, "catch_pct": catch_pct, "bets_per_vt": bets_per_vt,
        "useful_cycles": n_useful_fire_cycles,
    }


def main():
    summary_lines = ["V4 K5_DYN — per-account, per-mode summary (CORRECT simulator metric)",
                     "Catch = at least one bet landed on spins_to_vt==1 (next spin is VT)",
                     "=" * 90]
    for acct, csv_path in RUNS.items():
        df = pd.read_csv(csv_path)
        cfg = BUNDLE["accounts"][acct]
        for mode in ("bundled", "tuned"):
            schedule = cfg["schedules"][mode]
            text, stats = trace_account(acct, df, mode, schedule)
            out_path = OUT_DIR / f"trace_{acct}_K5DYN_{mode}.txt"
            out_path.write_text(text, encoding="utf-8")
            print(f"[+] wrote {out_path}  cycles={stats['cycles']:>3}  "
                  f"caught={stats['caught']:>3}  early={stats['early']:>3}  "
                  f"no_fire={stats['no_fire']:>3}  catch%={stats['catch_pct']:5.2f}  "
                  f"B/VT={stats['bets_per_vt']:5.2f}")
            summary_lines.append(
                f"  {acct:<6} {mode:<8}  cycles={stats['cycles']:>3}  "
                f"CAUGHT={stats['caught']:>3} ({stats['catch_pct']:5.2f}%)  "
                f"early={stats['early']:>3}  no_fire={stats['no_fire']:>3}  "
                f"bets={stats['bets']:>4}  B/VT={stats['bets_per_vt']:5.2f}"
            )
    (OUT_DIR / "summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
