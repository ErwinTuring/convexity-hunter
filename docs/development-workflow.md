# Development Workflow

## Source of truth

- Git repository documentation and committed code are the durable source of truth.
- ChatGPT/Codex conversation history is not authoritative project memory.
- Old BUILD/REVIEW chats may be archived after the corresponding work is reviewed, committed, and pushed.
- A fresh session must reconstruct state from the repository rather than depend on old chat context.
- If repository contracts conflict with a prompt or remembered context, stop and report the conflict rather than silently choosing an interpretation.

## Repository grounding

Before generating or executing work that changes specifications, architecture, or code, ground from the smallest necessary repository scope. By default, read:

1. `docs/project-state.md`;
2. the relevant authoritative contract or specification section; and
3. only the necessary implementation and test files.

Do not reread the whole repository by default. Verify exact fields, enum order, formulas, reason codes, thresholds, API counts, commit state, and milestone state from the repository rather than memory.

## Execution roles

The ChatGPT main conversation performs Repository Grounding, plans the work,
authors prompts for separate Codex sessions, evaluates their returned reports,
and freezes an accepted contract after formal preflight. It does not execute
the formal preflight or return its `READY` or `BLOCKED` result.

Codex PREFLIGHT executes the formal read-only preflight in a separate session.
Codex BUILD implements the accepted contract, validates it, applies accepted
corrections, and performs the final commit and push when instructed. Codex
REVIEW independently reads the contracts and actual diff, reports findings,
and never implements fixes. See
[`context-governance.md`](context-governance.md#chatgpt-and-codex-execution-role-boundaries)
for the canonical detailed definitions.

## Risk tiers

### A — Core contract / architecture / high-risk logic

Examples include public contracts, market-data identity and provenance, freshness, correction selection, calculation lineage, screening policy, state machines, core formulas, snapshot coherence, and cross-record transformations with economic meaning.

Required workflow:

```text
ChatGPT Repository Grounding
→ ChatGPT authors Codex PREFLIGHT prompt
→ Codex PREFLIGHT performs formal read-only preflight
→ ChatGPT evaluates the report and resolves specification blockers
→ contract clarification is committed first when required
→ ChatGPT authors Codex BUILD prompt
→ Codex BUILD implements without commit
→ ChatGPT authors independent REVIEW prompt
→ Codex REVIEW performs one broad independent review
→ Codex BUILD fixes accepted concrete findings
→ Codex REVIEW performs targeted re-review only for those findings
→ Codex BUILD runs final validation
→ Codex BUILD creates one commit and pushes
```

Implementation does not start while formal preflight has unresolved blockers.
The `READY` or `BLOCKED` decision belongs to the Codex PREFLIGHT report, which
ChatGPT evaluates before any contract freeze or BUILD prompt. REVIEW must not
rely on BUILD's summary: it reads the authoritative repository contracts and
actual diff. After a targeted fix, re-review only the original finding unless
the fix creates a concrete new concern.

### B — Ordinary implementation against an already locked contract

Examples include renderer integration, CLI wiring, known-schema serialization, simple adapters, and straightforward implementation of an already reviewed contract.

Required workflow:

```text
ChatGPT Repository Grounding and Codex BUILD prompt
→ Codex BUILD implements without commit
→ Codex REVIEW performs independent review
→ Codex BUILD applies accepted fixes
→ Codex REVIEW performs targeted re-review if needed
→ Codex BUILD validates, creates one commit, and pushes
```

No separate formal preflight is required unless implementation reveals a
genuine contract ambiguity, which escalates the task to Tier A.

### C — Low-risk, behavior-preserving work

Examples include documentation, copy, comments, test names, typos, checkpoint updates, and simple behavior-preserving refactors.

Required workflow:

```text
lightweight ChatGPT Repository Grounding
→ direct Codex BUILD or documentation session
→ appropriate tests/diff validation
→ one commit and push
```

No formal preflight or independent review is required unless scope or risk
grows. If a task initially classified B or C reveals contract ambiguity,
architecture impact, or meaningful behavioral risk, escalate it to A.

## Codex session naming and separation

- Use a separate formal preflight session named
  `PREFLIGHT｜<milestone-or-task>`.
- Use a fresh BUILD session for each new sub-milestone or independent work unit, named `BUILD｜<milestone-or-task>`.
- Use a separate fresh REVIEW session for A/B independent review, named `REVIEW｜<milestone-or-task>`.
- Continue the same BUILD session for fixes arising from that work unit.
- Continue the same REVIEW session for targeted re-review of its original findings.
- Do not use REVIEW to implement fixes.
- Do not commit implementation before required review passes.
- ChatGPT main conversations are not Codex sessions.
- A ChatGPT conversation must not describe itself as already inside a Codex
  PREFLIGHT, BUILD, or REVIEW task.
- Every Codex prompt must identify the separate existing Codex session into
  which the user will paste it.

## Token and context cost control

1. Prompts reference repository contracts instead of pasting entire specifications unless a small exact excerpt is necessary.
2. Grounding reads project state, the relevant contract section, and necessary code only.
3. Re-review targets previous findings instead of repeating a full review.
4. Checkpoints store navigation facts, not duplicate entire specifications.
5. Machine-check invariants with tests whenever practical instead of repeatedly restating them in prompts.
6. Optimize for minimum total cost, including errors and rework, not simply minimum token count.

## Repository grounding and token discipline

- All code-related Codex prompts begin from the current repository state, and
  exact contracts are reread from current files.
- Grounding depth is lightweight, standard, or high-risk as defined in
  `context-governance.md`; no task is high-risk without a material reason.
- Read only task-relevant sections, source files, direct dependencies, and
  tests.
- Prompts reference repository contracts instead of copying them
  unnecessarily.
- Exact current facts never rely on conversation memory.
- `current-checkpoint.md` is navigation only, not a contract or full history.
- One broad independent review is the default for implementation work that
  requires review.
- Targeted re-review occurs only after correction of an accepted realistic
  blocker or major defect and cannot introduce unrelated requirements.

## Commit discipline

- One logical approved work unit produces one implementation commit unless a separate contract-clarification commit is intentionally required first.
- Commit A-level contract clarifications before implementation when they resolve preflight blockers.
- Review the working tree for exact scope before staging.
- Run relevant tests, compile checks when applicable, and `git diff --check`.
- Commit only after the required workflow gate passes.
- Push and verify clean, up-to-date status.

## Milestone checkpoints

At meaningful milestone boundaries, `docs/project-state.md` should retain compact navigation facts: milestone status, checkpoint commit, test count, public API count when relevant, current task, and next task. Do not duplicate full contracts in checkpoint state.

At a broad milestone boundary, a new ChatGPT main conversation reconstructs
state from the repository and authors the next Codex prompt. When the next
gate is formal preflight, its first artifact is the Codex PREFLIGHT prompt, not
a self-authored preflight report.
