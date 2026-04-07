# SpinLogger Handoff Directory

This directory exists so you can pick up work on **any machine** without
losing the Claude session memory.

## Files

| File | What it is |
|------|------------|
| `HANDOFF_PROMPT.md` | **The prompt to paste into a new Claude instance.** Start here. |
| `MEMORY.md` | Index of memory entries (mirrors the local Claude memory) |
| `project_ensemble_status.md` | Current status of the 16-rule ensemble + locked decisions + parked future work |
| `user_profile.md` | Working style notes (high-confidence strategies preferred) |
| `feedback_analysis.md` | Past feedback on how to push analysis harder |
| `project_strip_research.md` | Older strip-research thread (running median calibration) |
| `project_next_session_brief.md` | Older brief from before the nuclear pass |

## How to use on a new machine

1. Pull the repo: `git pull` or `git clone <url>`
2. Open a new Claude Code session in the repo directory
3. Open `HANDOFF_PROMPT.md` and copy its body
4. Paste it as your first message in the new Claude session
5. The new instance will read all the relevant docs and have full context

## Why this exists

Claude Code stores per-project memory in `~/.claude/projects/<project>/memory/`
which is local to each machine. To make memory portable across machines,
this `docs/handoff/` directory mirrors those memory files into the git repo.

**Update process**: when you make significant new decisions in a session,
ask Claude to also copy the updated memory files into `docs/handoff/` and
commit them. That keeps the cross-machine handoff in sync.

## Source of truth

The most important reference is `analysis/nuclear/NUCLEAR_FINDINGS.md`. The
memory files are summaries and pointers — that doc has the actual data.
