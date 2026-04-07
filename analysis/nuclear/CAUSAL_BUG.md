# CAUSAL_BUG.md — the post-triple inflation bug

**Date discovered:** 2026-04-07
**Reporter:** user, mid-session, after live test of the 16-rule ensemble
**Severity:** invalidates the headline 63/178 catch claim and the entire rule
ensemble derived from chunks 03–10 of the nuclear sweep.

---

## TL;DR

Every "catch" claim in `NUCLEAR_FINDINGS.md` was scored using a non-causal
oracle: the simulator evaluated each rule on the **same spin** that landed the
target triple, *after* that triple's own 3 ACC symbols had already been folded
into `sa_acc`. The rate gates therefore got a free +3/sa_spins boost on every
single triple-landing row, which is exactly the kind of swing that flips a rule
from "not firing" to "firing." Many of the 63 catches were not predictions —
they were the rules reading their own answer key.

The live `SLDebtTracker` had the same shape of bug: it incremented counters
*before* evaluating rules in `onSpin:`, so a triple spin saw `sa_acc += 3`,
`acc_rate` jumped, and `firingRuleCount > 0` registered a "catch" even though
the user had no opportunity to bet.

Both have now been patched. The 16-rule ensemble itself still needs to be
re-derived under causal evaluation; the catch numbers in `NUCLEAR_FINDINGS.md`
should be treated as an upper bound, not a target.

---

## How the bug worked

### In the offline simulator

`analysis/nuclear/02_eval.py::simulate_fast`:

```python
for i, spin in enumerate(traj):
    if decision_at_end_of_gap(spin):
        bet_spins += 1
        if i == len(traj) - 1:
            gap_caught = True
```

`traj` comes from `01_loader.py::build_spin_records`, which reads counter
values **as they appear in the CSV row** — and the CSV is written **after**
the spin's own symbol counts have been added to `sa_*`. So `traj[-1]` is the
triple-landing row, and at that row `sa_acc` already includes the 3 ACC
symbols of the triple itself.

A rule like `sa_spins >= 130 and sa_acc/sa_spins >= 0.30` evaluated on this
row is asking "was the rate above 0.30 *after* counting the 3 symbols I'm
trying to predict?" — which is trivially easier than the honest question.
Concretely, on a 130-spin gap with sa_acc = 36 going into the triple:

| evaluation | sa_spins | sa_acc | rate   | passes 0.30 gate? |
|------------|---------:|-------:|-------:|:-----------------:|
| causal     |      130 |     36 | 0.2769 | NO                |
| non-causal |      130 |     39 | 0.3000 | YES               |

The +3 from the landing triple alone bumps a borderline gap from "miss" to
"catch." Most of the rules in the ensemble were tuned on borderline gaps.

### In the live tracker (pre-fix)

`SLDebtTracker.onSpin:` previously did, in order:

1. `self.saSpins++`
2. `self.saSymbols += primary` (e.g. `+= 3` on an ACC triple)
3. evaluate all 16 rules → set `firingRuleCount` / `firingRuleBitmask`
4. on target triple, also compute `targetCaught = (isAcc && firingRuleCount > 0)`

Step 3 reads exactly the same poisoned `sa_acc` value as the offline
simulator. The CSV row written for the triple spin would happily mark
`target_caught = 1` and light up `r01..r16` bits, even when the rules had
been silent on every single spin leading up to the triple.

---

## Why we missed it

- The chunks 03–10 sweeps optimised purely for `caught / bet_spins` — the
  oracle was inside the loop, never separately validated.
- `verify_tracker.py` re-implemented the same `simulate_fast` walk, so it
  agreed with the sweeps and gave us false confidence.
- The only signal that anything was wrong was the user's live experience:
  the shipped tracker felt like it was catching ~3/4 ACC triples instead of
  the 8/14 (~57%) that the new bet_decisions CSV reported on the same
  session. That mismatch is the bug — `target_caught` was non-causal, the
  user's lived experience was causal.

---

## Causal re-analysis of the test session (sanity check)

User session `bet_decisions_2026-04-07.csv` (1724 rows, 14 ACC triples):

| metric                                          | value |
|-------------------------------------------------|------:|
| triples logged as `target_caught = 1` (non-causal) | 8/14 |
| triples where ANY rule fired on the *prior* spin (causal, 1-spin warning) | 3/14 |
| triples where ANY rule fired anywhere in last 5 spins              | 7/14 |

The "3/14 with a one-spin warning" exactly matches what the user said they
felt at the table ("3/4 of about 15 runs"). The non-causal oracle was
cheating by ~5 catches per 14 — a 30 percentage-point inflation.

Extrapolating to the full nuclear corpus (178 ACC gaps): a similar
30-point inflation suggests the honest catch count for the current 16-rule
ensemble is closer to **18/178 strict** or **~64/178 if rules are allowed
to "hold through" cooldown** — at substantially worse mb/hit than the
10.49 figure quoted in `NUCLEAR_FINDINGS.md`.

(Full causal re-sweep is the next session's job.)

---

## The fix

### Live tracker (`SLDebtTracker.h` / `.m`)

Two new readonly properties expose the firing state captured at the **start**
of `onSpin:` — i.e., the state going INTO the spin, before any of this spin's
symbol counts are folded in:

```objc
@property (nonatomic, assign, readonly) NSInteger priorFiringRuleCount;
@property (nonatomic, assign, readonly) NSUInteger priorFiringRuleBitmask;
```

`onSpin:` snapshots them before incrementing any counter:

```objc
// ---- CAUSAL snapshot ----
self.priorFiringRuleCount   = self.firingRuleCount;
self.priorFiringRuleBitmask = self.firingRuleBitmask;

self.saSpins++;
// ... rest of counter updates and rule evaluation ...
```

The post-spin `firingRuleCount` is still computed and exposed for the UI
(forward-looking display: "is the tracker telling me to bet on the NEXT
spin?"), but the CSV logger and target_caught logic now use the prior values.

On a target triple, `firingRuleCount` is cleared at reset so the next gap's
prior-snapshot starts from a clean slate. The logger has already captured
`priorFiringRule*` for the triple row by then, which is what matters for
`target_caught`.

### CSV logger (`SLBetDecisionLogger.m`)

Three columns now read from the prior snapshot:

- `r01..r16` per-rule binary columns (decoded from `priorFiringRuleBitmask`)
- `rules_count` / `rules_bitmask` (the prior values)
- `target_caught` = `isAcc && priorFiringRuleCount > 0`

The `phase` column is still post-spin for now — recoverable from
`rules_count > 0` and `cooldown_remaining`, so analysts can re-derive a causal
phase if needed.

### Offline simulator (still TODO)

`02_eval.py::simulate_fast` needs an analogous shift: the catch criterion
must evaluate the strategy on `traj[end_i - 1]` (or the equivalent prior-spin
counter snapshot) when `i == len(traj) - 1`, not on `traj[end_i]`. Every
sweep result downstream needs to be regenerated.

---

## Impact on existing artefacts

| artefact                              | status under causal evaluation |
|---------------------------------------|--------------------------------|
| `NUCLEAR_FINDINGS.md` 63/178 claim    | invalidated                    |
| 16-rule ensemble in `SLDebtTracker`   | unsafe — needs re-derivation   |
| `accBaselineDefaults` 130/0.30        | needs re-validation            |
| `accComboOnlyDefaults`                | needs re-validation            |
| `spnDefaults` 120/0.25                | needs re-validation            |
| 8/3 cooldown                          | needs re-validation            |

The shipped tracker is still safe to *run* (it now evaluates causally and
will simply fire less often), but its rule thresholds were tuned against the
poisoned oracle and are likely too aggressive on rate gates. Expect the next
causal sweep to surface lower-rate / longer-spin variants of most rules.

---

## Lessons

- **Counters in CSV rows are post-spin.** When asking "could I have decided
  to bet on this spin?", read the row *before* the one you're scoring.
- **The oracle must live outside the rule.** A simulator that re-uses the
  rule's own counter snapshot to score the catch is a tautology generator.
- **Live experience is ground truth.** The bug was invisible to every script
  in the repo and only showed up when the user said "I felt like I caught
  3/4, not 8/14." Trust the meatspace report.
