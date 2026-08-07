# Development Workflow

## Source of truth

- Git repository documentation and committed code are the durable source of truth.
- The Codex Main Architect is the only user-facing development thread. Its
  conversation history and child-agent context are not authoritative project
  memory.
- The main thread is disposable; repository state is durable memory.
- A fresh Main Architect thread reconstructs state from the repository rather
  than depending on old chat context or copied reports.
- If repository contracts conflict with a prompt or remembered context, stop and report the conflict rather than silently choosing an interpretation.

## Main Architect and execution model

The Codex Main Architect is the only user-facing development thread. It owns
Repository Grounding, risk classification, sequencing, contract synthesis and
freeze, child-agent dispatch, review decisions, fixes, validation, checkpoint
maintenance, and ordinary commit/push actions.

Execution is autonomous within the accepted product direction. The user owns
product goals, major architecture, governance principles, MVP scope, external
credentials or authority, and genuinely blocking product decisions. Do not
ask the user to approve ordinary gates, fixes, commits, or pushes. Escalate by
exception when one of those user-owned decisions is required.

The default execution flow is serial. Use child agents only when they provide
clear value; do not add parallelism or governance machinery for its own sake.

## Repository grounding

Before generating or executing work that changes specifications, architecture, or code, ground from the smallest necessary repository scope. By default, read:

1. `docs/project-state.md`;
2. the relevant authoritative contract or specification section; and
3. only the necessary implementation and test files.

Do not reread the whole repository by default. Verify exact fields, enum order, formulas, reason codes, thresholds, API counts, commit state, and milestone state from the repository rather than memory.

## Execution roles

The Main Architect may dispatch separate child-agent contexts for formal
PREFLIGHT, BUILD, REVIEW, fixes, or targeted re-review. Child agents return
evidence to the Main Architect; the user does not manually create sessions or
copy reports between them. The canonical role boundaries are in
[`context-governance.md`](context-governance.md#codex-main-architect-and-child-agent-boundaries).

PREFLIGHT is read-only. BUILD implements only the accepted contract. REVIEW
independently reads the authoritative contracts and actual diff and never
implements fixes. The Main Architect accepts findings, directs fixes, and
decides whether targeted re-review is sufficient.

## Risk tiers

### A — Core contract / architecture / high-risk logic

Examples include public contracts, market-data identity and provenance, freshness, correction selection, calculation lineage, screening policy, state machines, core formulas, snapshot coherence, and cross-record transformations with economic meaning.

Required workflow:

```text
Repository Grounding
→ formal read-only PREFLIGHT
→ Main Architect synthesis and contract freeze
→ BUILD
→ independent REVIEW
→ accepted fixes and targeted re-review
→ validation
```

Implementation does not start while the formal read-only PREFLIGHT has
unresolved blockers. The Main Architect evaluates the PREFLIGHT evidence and
freezes the accepted boundary before BUILD. REVIEW must not rely on BUILD's
summary: it reads the authoritative repository contracts and actual diff.
After a targeted fix, re-review only the original finding unless the fix
creates a concrete new concern.

### B — Ordinary implementation against an already locked contract

Examples include renderer integration, CLI wiring, known-schema serialization, simple adapters, and straightforward implementation of an already reviewed contract.

Required workflow:

```text
Repository Grounding
→ BUILD
→ independent REVIEW
→ accepted fixes and targeted re-review
→ validation
```

No separate formal preflight is required unless implementation reveals a
genuine contract ambiguity, which escalates the task to Tier A.

### C — Low-risk, behavior-preserving work

Examples include documentation, copy, comments, test names, typos, checkpoint updates, and simple behavior-preserving refactors.

Required workflow:

```text
lightweight Repository Grounding
→ direct documentation or maintenance work
→ proportional validation and review
```

No formal PREFLIGHT or independent review is required unless scope or risk
justifies it. If a task initially classified B or C reveals contract
ambiguity, architecture impact, or meaningful behavioral risk, escalate it to
A.

## Child-agent separation and runtime evidence

- Use a fresh child-agent context for an independent REVIEW; the Builder must
  not review its own work.
- Continue the BUILD context for accepted fixes and the REVIEW context for
  targeted re-review of the original findings when that is useful.
- REVIEW never implements fixes, and fixes never introduce unrelated
  requirements.
- Do not commit implementation before the required review and validation
  gates pass.
- Child-agent work is serial by default. Dispatch separate child agents only
  when the role separation or a genuinely independent task provides clear
  value.

## Child-agent model and recovery

PREFLIGHT, BUILD, REVIEW, targeted fixes, targeted re-review, and other
execution child agents default to `gpt-5.6-luna` with `max` reasoning effort.
The requested model or a child's self-report is not evidence of actual
execution. Claim the model and effort only when runtime metadata binds the
child context to the actual values. Do not add a custom telemetry or audit
framework to establish this.

If the same substantive blocker survives two Luna/max fix-and-re-review
rounds, enter temporary recovery mode with `gpt-5.6-sol` and `medium` effort
for at most two rounds. If it still survives, the Main Architect performs a
root-cause replan. Escalate to the user only if the replan becomes a product,
architecture, contract, or scope decision; do not mechanically repeat the
same loop.

## Token and context cost control

1. Child contexts reference repository contracts instead of duplicating entire specifications unless a small exact excerpt is necessary.
2. Grounding reads project state, the relevant contract section, and necessary code only.
3. Re-review targets previous findings instead of repeating a full review.
4. Checkpoints store navigation facts, not duplicate entire specifications.
5. Machine-check invariants with tests whenever practical instead of repeatedly restating them in dispatch context.
6. Governance cost must match risk and MVP value; optimize total cost, including errors and rework, rather than maximizing process.

## Repository grounding and token discipline

- Main Architect and child-agent work begins from the current repository
  state, and exact contracts are reread from current files.
- Grounding depth is lightweight, standard, or high-risk as defined in
  `context-governance.md`; no task is high-risk without a material reason.
- Read only task-relevant sections, source files, direct dependencies, and
  tests.
- Dispatch context references repository contracts instead of copying them
  unnecessarily.
- Exact current facts never rely on conversation memory.
- `current-checkpoint.md` is navigation only, not a contract or full history.
- One broad independent review is the default for implementation work that
  requires review.
- Targeted re-review occurs only after correction of an accepted realistic
  blocker or major defect and cannot introduce unrelated requirements.

## Commit discipline

- One logical work unit accepted by the Main Architect produces one implementation commit unless a separate contract-clarification commit is intentionally required first.
- Commit A-level contract clarifications before implementation when they resolve preflight blockers.
- Review the working tree for exact scope before staging.
- Run relevant tests, compile checks when applicable, and `git diff --check`.
- After the required tests and review for the applicable tier pass, the Main
  Architect may commit and push an ordinary completed work unit automatically.
- Force pushes, history rewrites, releases, destructive external operations,
  credentials, and destructive migrations require user approval.
- After commit/push, verify clean and up-to-date status.

## Milestone checkpoints

At meaningful milestone boundaries, `docs/project-state.md` should retain compact navigation facts: milestone status, checkpoint commit, test count, public API count when relevant, current task, and next task. Do not duplicate full contracts in checkpoint state.

At a broad milestone boundary, a new Main Architect thread reconstructs state
from the repository. When the next gate is formal preflight, the Main
Architect dispatches the formal read-only PREFLIGHT before synthesis or BUILD;
Repository Grounding is not itself the preflight result.
