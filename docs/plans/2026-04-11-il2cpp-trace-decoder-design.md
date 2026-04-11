# IL2CPP Trace Decoder — Design

*2026-04-11*

## Context

The live IL2CPP signal scanner added in commit `5dd5a1f` (*feat: implement live IL2CPP signal scanner and in-game HUD panel*) is producing partially correct, partially garbage output. Sample from a live capture session, spin 64200:

```
timestamp,spinNum,betState,sym1,sym2,sym3,top1,top2,top3,bot1,bot2,bot3,idx1,idx2,idx3,len1,len2,len3,...
2026-04-11T05:13:25,64200,2,30,2,2,374974367,373755005,-1,-1,0,-1,3,3,8,9,9,9,...
```

### What works

- `spin_num` increments monotonically.
- `sym1/2/3` (center payline) read via `SlotResult → SlotSymbol3 → symbol1/2/3` return plausible `SlotSymbol` enum ints and match the game's network-logged payline.
- `bet_state`, `shields`, `has_dynamic_results` track correctly.

### What is broken

1. **`top1..3` / `bot1..3`** — values like `374974367` are pointer fragments, not symbol ints. The current `readBar → arrayElementPtr → readInt32(elem, fo_slotSymbolBacking)` path misinterprets the reel-bar data. Likely cause: `<SlotSymbol>k__BackingField` is at the wrong offset, or `m_SymbolElements` is a value-type array being dereferenced as a reference-type array (wrong stride, wrong element type).
2. **`failCounter` / `failCounterGlobal`** — always 0 despite `failThreshold=8` reading a plausible constant. Offsets may be wrong, or the counters may genuinely not have ticked — cannot tell from a single sample. Needs per-spin diff evidence.
3. **`m_NumberOfSymbols = 9`** — row-by-row cross-check shows the same reel index mapping to different symbols across spins (`idx1=7→sym=2` on spin 64202 vs `idx1=7→sym=3` on spin 64214). So `m_NumberOfSymbols` is almost certainly **not strip length**, and `m_SymbolElements` is not a stable strip layout — more likely a per-spin visible-window buffer.
4. **Stale payline on consecutive spins** — spins 64200 and 64201 return byte-identical `sym/top/bot/idx` tuples with different `spin_num`. The edge-detected spin-end snapshot is fired before `currentSlotResult` has settled.

The existing static discovery sweep in commit `e03610f` only dumped class and field **names**, which is not enough — we already have most names right. The missing piece is the **runtime layout**: field types, array strides, inline-vs-reference typing, and which field actually carries the strip.

## Goal

Replace the live scanner temporarily with a **trace-mode scanner** that records every observable piece of IL2CPP state on every 250 ms poll. Use the resulting trace offline to reverse-engineer the real memory layouts against the game's own `spin_history_*.csv` ground truth, then rewrite the live scanner with confirmed layouts.

## Architecture

Reuse phases 0–3 of [src/SLMemoryScanner.m](../../src/SLMemoryScanner.m) unchanged — API resolution, class finding, offset caching, instance watching. Only phase 4 (`ScanPhaseActive`) changes.

- New `traceScan` method replaces `activeScan`. Fires every tick regardless of `spinning` edge.
- Scanner thread performs only `memcpy` and object-pointer reads into an `NSMutableData` buffer. Target: under 1 ms per tick.
- All JSON encoding and file I/O run on a dedicated serial background `dispatch_queue_t`. Zero game impact on the hot path.
- [src/SLSignalPanel.m](../../src/SLSignalPanel.m) HUD is repurposed: it shows trace counters (`spinsSeen`, `snapshotsWritten`, `bytesWritten`, `currentPhase`) updated every 1 s.
- **No auto-stop.** Capture runs until the user closes the app. HUD counters let the user decide when enough data is collected.
- The class-finding and offset-caching phases are preserved because they already work. Evidence: `sym1/2/3` reads cleanly, `failThreshold=8` reads a plausible constant, `spin_num` increments, `shields` tracks. The broken layer is interpretation of reel-bar data, not class/offset discovery.

## Trace record schema

One JSON object per tick, one per line (JSONL), written to `~/Documents/il2cpp_trace_<YYYYMMDD_HHMMSS>.jsonl`.

### Top-level quick-filter fields

`t` (ISO timestamp), `mono_ms` (monotonic ms since scanner start), `spin_num`, `spinning`, `bet_state`, `phase`, `instance_ptr`. Duplicated above the nested objects so offline filters can skip past uninteresting snapshots without parsing the full record.

### `fields` section — β (named field enumeration)

For each known class (`SlotMachineManager`, `SlotResult`, `SlotSymbol3`, `SlotBarManager`, `SlotBarSymbolInfo`, `BoardManager`), iterate via `il2cpp_class_get_fields` and record per field:

```json
"field_name": {"off": 408, "u64": 1, "i32": 1, "ptr": "0x1"}
```

Three interpretations of the same 8 bytes. Offline analysis picks whichever is correct per field. This eliminates the "is this a pointer or an int?" rebuild cycle entirely.

**Pointer follow — one level only.** When a field's `ptr` is a valid heap address, dereference it and dump the target class's fields too, keyed as `ClassName@0xADDRESS`. No recursive chase, no cycle detection needed.

### `hex` section — γ (targeted raw windows)

Raw bytes at the specific suspect structures:

- Each reel bar instance (`slotBar1..3`) — 256 bytes.
- Each bar's `m_SymbolElements` array payload (header + full element count × stride), with `array_len` and `element_size` precomputed so Python can unpack even if the element type is still unknown.
- `currentSlotResult` — 128 bytes.

### Volume

Approximate per-snapshot size: ~100 KB. At 4 Hz × ~5 s per spin cycle, that is ~2 MB per spin → ~400 MB per hour of continuous play. Well within iOS file system throughput and Python offline analysis budgets.

### Deliberately not in the schema

- No parsed "top row / bot row / strip" columns. The point is that those interpretations are not trusted yet; offline analysis discovers them.
- No flat CSV columns. JSONL per-snapshot + nested objects survives schema evolution — adding another class to follow next week does not break old records.

## Offline analyzer

New script [analysis/nuclear/50_il2cpp_trace_decode.py](../../analysis/nuclear/). Standalone; depends only on `pandas`, `numpy`, and stdlib. Six stages, each independently printable.

### Inputs

1. Trace JSONL path, e.g. `il2cpp_trace_20260411_051325.jsonl` copied off device.
2. Matching spin_history CSV, picked by temporal overlap or passed on the command line, e.g. [data/Islam/spin_history_2026-04-11.csv](../../data/Islam/).

### Stage 1 — Load & segment

Parse JSONL into snapshot dicts; group by `spin_num`. Each spin yields:

- A **settled snapshot** — last snapshot where `spinning` just flipped false.
- An **animation sequence** — all preceding snapshots during the spin.

### Stage 2 — Payline sanity gate

For every settled snapshot, walk `fields → SlotResult → SlotSymbol3 → symbol1/2/3`, join with spin_history on `spin_num == seq`, and report match rate against `r1/r2/r3`.

**Gate: ≥95% match.** Failure means the scanner is reading the wrong instance or reading stale memory. Revise trace mode before proceeding downstream.

### Stage 3 — Field change-map

For every `(class, field_name)` pair in settled snapshots, compute:

- `is_constant` — never changes across all spins → prune.
- `unique_count` — distinct values.
- `type_guess` — `symbol_like` (1..50), `bool_like` (0..1), `counter_like` (monotonic), `resetting_counter` (small int with periodic resets).
- Equality-match-rate against every numeric column in spin_history: `r1`, `r2`, `r3`, `is_triple`, `sa_spins`, `sa_acc`, `sa_spn`, `coins_won`, `bet_level`, etc.

Output: ranked "most interesting" table. This is where the real pity counter either proves itself or reveals that it lives on a different field than the one we named.

### Stage 4 — Strip decoder (the payoff stage)

For each reel bar, using the animation sequence across many spins:

1. For every plausible element `(stride, inner_offset)` combination from `{4, 8, 12, 16, 24, 32} × {0, 4, 8, 12, 16}`, unpack `m_SymbolElements` hex as an array of integers.
2. For each candidate, check whether `element[resultSymbolIndex] == r_n` across settled snapshots. Pick the combination with the highest match rate.
3. Once `(stride, inner_offset)` is locked for bar1, verify the same layout works for bar2 (vs `r2`) and bar3 (vs `r3`).
4. With layout confirmed, compute `top = element[(idx − 1) mod N]` and `bot = element[(idx + 1) mod N]` for every spin. Cross-check against the animation sequence: the elements the reel passed through during spin-up should form a contiguous arc on the decoded strip.

Output: confirmed `(stride, inner_offset)` for `m_SymbolElements`, the decoded strip for each of the three bars, and top/bot predictions for every spin.

### Stage 5 — Pity counter hunt

Filter Stage 3 results to `counter_like` and `resetting_counter` candidates. Validate:

- **Monotonic increment on non-triple spins** (using spin_history's `is_triple` column).
- **Reset on triple spins** — field returns to 0 (or a small value) within one poll of a triple.
- **Max value near `failThreshold`** (currently 8).

Output: confirmed offsets for real session and global pity counters, with evidence counts.

### Stage 6 — Report

Write [analysis/nuclear/50_il2cpp_layout_report.md](../../analysis/nuclear/) containing:

- Confirmed field layout table: `(class, field, offset, type, interpretation)`.
- Decoded reel strips for all three bars.
- Pity counter offsets plus monotonic + reset evidence.
- Anomalies: Stage 2 mismatches, unidentified changing fields, animations that failed to decode.
- A "next scanner should do X" recommendation list that feeds the follow-up rewrite plan.

### Gates before rewrite

Stages 2 and 4 are **must-pass gates**. Stage 2 proves we are reading the right instance; Stage 4 proves we understand the reel layout. If either fails, we iterate on trace mode before rewriting the live scanner. We do not rewrite on partial evidence.

Stages 3 and 5 are nice-to-have improvements that strengthen the rewritten scanner but are not blocking.

## Success criteria

1. Stage 2 passes: memory-read payline matches spin_history `r1/r2/r3` on ≥95% of spins.
2. Stage 4 passes: a single `(stride, inner_offset)` combination decodes `m_SymbolElements` correctly for all three bars, validated against `r1/r2/r3`.
3. Stage 5 passes: pity counter offsets identified with monotonic + reset evidence on ≥90% of non-triple / triple spins.
4. Stage 6 report committed to `analysis/nuclear/50_il2cpp_layout_report.md` and readable standalone.

## Open questions to be answered by the trace

- Whether `SlotSymbol` is a value-type enum (4-byte int) or a reference-type class (pointer to a boxed int). The field enumeration's `u64` / `i32` / `ptr` triple will resolve this immediately.
- Whether the top/bottom symbols come from a separate "visible window" structure or from adjacent elements of a unified strip.
- Whether the scanner is reading stale memory on spin-end (Stage 2 catches it; fix is to shift the settled-snapshot forward by 1–2 polls).
- Whether the game ever reallocates the `SlotMachineManager` singleton mid-session (top-level `instance_ptr` will show it).

## Out of scope

- Hooking Unity/IL2CPP methods (`SlotBar.SetResult`, `SlotBarAnimator.ShowStop`, etc.) as an alternative data source. Considered; parked as a fallback if Stage 4 decoding fails after iteration.
- Ground truth for top/bot rows. Not present in any existing log. Validation relies on the decoded strip being internally self-consistent (arc-traversal during animation) rather than external ground truth.
- Rewriting the live scanner. That is the follow-up plan — to be written once the trace has produced a layout report.

## Next step

Invoke the `writing-plans` skill to produce the detailed step-by-step implementation plan for the trace mode + offline analyzer, as [docs/plans/2026-04-11-il2cpp-trace-decoder-plan.md](2026-04-11-il2cpp-trace-decoder-plan.md).
