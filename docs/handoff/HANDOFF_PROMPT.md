# Handoff Prompt — paste this into a new Claude instance

Use this when starting a new Claude Code session (any machine, any Claude
interface) to pick up the SpinLogger project where the previous instance
left off.

---

## Copy-paste this:

```
We just shipped the 16-rule ACC ensemble tracker for SpinLogger. Read these
to catch up:

1. docs/handoff/MEMORY.md — session memory snapshot (auto-loads on this machine,
   manual read on others)
2. docs/handoff/project_ensemble_status.md — locked decisions and deferred work
3. analysis/nuclear/NUCLEAR_FINDINGS.md — the source-of-truth findings doc (most important)

Latest 3 commits on main:
  2549a5e fix: update SLMenuOverlay to use new 16-rule tracker API
  6945e3b feat: 16-rule ensemble tracker with cooldown 8/3 + bet_decisions logging
  e9e4c8a analysis: nuclear pass — 16-rule ACC ensemble + per-account validation

Key implementation files:
- src/SLDebtTracker.h/m       — 16-rule ensemble (live behavior: 62/178 catches @ ~10.95 mb/hit)
- src/SLDebtMonitor.m         — 5-phase UI, mission badge, accum_pct bar
- src/SLBetDecisionLogger.h/m — writes bet_decisions_YYYY-MM-DD.csv per spin

Status:
- Build compiles (after the 2549a5e SLMenuOverlay fix)
- Pushed to origin/main, GitHub Actions builds the .dylib
- Installed/testing on device

What's parked for future work:
- SPN nuclear analysis (full chunks 1-11 mirror to get a parallel SPN
  ensemble at <10 mb/hit). The complete playbook with all lessons
  learned is in NUCLEAR_FINDINGS.md "FUTURE WORK — SPN Nuclear Analysis"
- Tap-to-expand panel UI (deferred — long-press config menu is sufficient)
- Self-tuning script (chunk 12_self_tune.py) — needs collected
  bet_decisions.csv data first

Things I might come back with:
- Build errors (other files referencing the old single-config API)
- UI feedback after first session (phases/colors/badge issues)
- bet_decisions.csv format questions or analysis requests
- Once I have a few sessions of data: "let's run self-tune analysis"

Do NOT change the locked-in numbers without re-running the verification.
The 62/10.95 figure is the realistic live behavior — the simulator's
older 63/10.49 was non-causal (used future prev_real_triple).
```

---

## Why this exists

The previous Claude instance built memory files in
`~/.claude/projects/.../memory/` on the original machine. That directory
isn't tracked in git and doesn't follow you across machines.

This `docs/handoff/` directory mirrors those memory files INTO the repo
so any future Claude instance — on any machine — has the same context.

After loading this prompt, the new instance should:
1. Read `docs/handoff/MEMORY.md` and `project_ensemble_status.md`
2. Read `analysis/nuclear/NUCLEAR_FINDINGS.md` for the full findings
3. Be ready to continue work
