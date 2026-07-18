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

## Risk tiers

### A — Core contract / architecture / high-risk logic

Examples include public contracts, market-data identity and provenance, freshness, correction selection, calculation lineage, screening policy, state machines, core formulas, snapshot coherence, and cross-record transformations with economic meaning.

Required workflow:

```text
Repository grounding
→ fresh BUILD specification preflight
→ resolve specification blockers
→ commit contract clarification first when needed
→ BUILD implementation without commit
→ fresh independent REVIEW
→ BUILD fixes for concrete findings
→ targeted REVIEW only for those findings
→ final validation
→ one commit and push
```

Implementation does not start while preflight has unresolved blockers. REVIEW must not rely on BUILD's summary: it reads the authoritative repository contracts and actual diff. After a targeted fix, re-review only the original finding unless the fix creates a concrete new concern.

### B — Ordinary implementation against an already locked contract

Examples include renderer integration, CLI wiring, known-schema serialization, simple adapters, and straightforward implementation of an already reviewed contract.

Required workflow:

```text
Repository grounding
→ BUILD implementation without commit
→ independent REVIEW
→ targeted fixes/re-review if needed
→ one commit and push
```

No separate specification preflight is required unless implementation reveals a genuine ambiguity.

### C — Low-risk, behavior-preserving work

Examples include documentation, copy, comments, test names, typos, checkpoint updates, and simple behavior-preserving refactors.

Required workflow:

```text
BUILD
→ appropriate tests/diff validation
→ one commit and push
```

Independent REVIEW is optional unless scope or risk grows. If a task initially classified B or C reveals contract ambiguity, architecture impact, or meaningful behavioral risk, escalate it to A.

## BUILD and REVIEW session rules

- Use a fresh BUILD session for each new sub-milestone or independent work unit, named `BUILD｜<milestone-or-task>`.
- Use a separate fresh REVIEW session for A/B independent review, named `REVIEW｜<milestone-or-task>`.
- Continue the same BUILD session for fixes arising from that work unit.
- Continue the same REVIEW session for targeted re-review of its original findings.
- Do not use REVIEW to implement fixes.
- Do not commit implementation before required review passes.

## Token and context cost control

1. Prompts reference repository contracts instead of pasting entire specifications unless a small exact excerpt is necessary.
2. Grounding reads project state, the relevant contract section, and necessary code only.
3. Re-review targets previous findings instead of repeating a full review.
4. Checkpoints store navigation facts, not duplicate entire specifications.
5. Machine-check invariants with tests whenever practical instead of repeatedly restating them in prompts.
6. Optimize for minimum total cost, including errors and rework, not simply minimum token count.

## Commit discipline

- One logical approved work unit produces one implementation commit unless a separate contract-clarification commit is intentionally required first.
- Commit A-level contract clarifications before implementation when they resolve preflight blockers.
- Review the working tree for exact scope before staging.
- Run relevant tests, compile checks when applicable, and `git diff --check`.
- Commit only after the required workflow gate passes.
- Push and verify clean, up-to-date status.

## Milestone checkpoints

At meaningful milestone boundaries, `docs/project-state.md` should retain compact navigation facts: milestone status, checkpoint commit, test count, public API count when relevant, current task, and next task. Do not duplicate full contracts in checkpoint state.
