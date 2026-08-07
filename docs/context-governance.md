# Context Governance

## Purpose

The objective is not to make the Main Architect thread remember everything.
It is to ensure that forgetting, compression, ambiguity, or stale conversation
history cannot silently change the implementation contract.

Conversation history provides background and design understanding. The current
repository provides authoritative project facts and durable memory. The Main
Architect thread is disposable.

## Five-layer error-prevention system

1. **Repository truth.** Repository contracts define the accepted state.
2. **Grounded planning.** The Main Architect grounds work in the current
   repository and freezes accepted contracts at the appropriate gate.
3. **Formal preflight and BUILD.** A read-only PREFLIGHT checks feasibility and
   contradictions before Tier A BUILD.
4. **Automated tests.** Tests verify machine-checkable invariants.
5. **Independent review.** Review looks for realistic contract and
   implementation defects.

The Main Architect must not override authoritative repository contracts or
user-owned product decisions by relying on incomplete conversation context.

## Codex Main Architect and child-agent boundaries

This section is the canonical definition of the autonomous development
workflow. The Codex Main Architect is the only user-facing development thread;
child agents are execution contexts, not additional user-facing threads.

### Codex Main Architect

The Main Architect:

- performs Repository Grounding and classifies the work as Tier A, B, or C;
- dispatches child agents when they provide clear value and keeps execution
  serial by default;
- evaluates formal PREFLIGHT evidence, resolves ordinary technical choices,
  and freezes the accepted contract before Tier A BUILD;
- coordinates BUILD, independent REVIEW, accepted fixes, targeted re-review,
  validation, and checkpoint maintenance; and
- commits and pushes ordinary completed work units automatically after the
  required tests and review pass.

The Main Architect proceeds autonomously within the accepted direction. The
user owns product goals, major architecture, governance principles, MVP scope,
external credentials or authority, and genuinely blocking product decisions.
Escalate only when one of those decisions is required. Do not ask the user to
confirm ordinary gates, fixes, commits, or pushes.

When the next gate is Tier A formal preflight, the Main Architect must obtain
the read-only child-agent result before synthesis/contract freeze and BUILD.
Repository Grounding is not itself the formal preflight result.

### PREFLIGHT child agent

The PREFLIGHT child agent:

- is a separate read-only execution context when Tier A requires it;
- performs the formal read-only repository preflight;
- independently verifies repository state, contracts, source, tests,
  numerical boundaries, provenance, lineage, API impact, file scope, and
  validation scope;
- makes no repository modifications; and
- returns structured evidence ending in `READY` or `BLOCKED` to the Main
  Architect.

The Main Architect evaluates the result; the user does not manually create a
session or copy a report between threads.

### BUILD child agent

The BUILD child agent:

- is dispatched only after the accepted contract is frozen;
- implements only the accepted and frozen contract;
- does not begin while the required formal preflight remains unresolved;
- runs the required validation;
- keeps implementation uncommitted until the required review gate passes; and
- applies accepted corrections in the same BUILD context when useful.

### REVIEW child agent

The REVIEW child agent:

- is independent from BUILD and does not review its own work;
- reads repository contracts and the actual diff independently;
- performs one broad review by default;
- does not implement fixes;
- uses targeted re-review only for accepted realistic blockers or major
  defects; and
- does not introduce unrelated or newly invented requirements during targeted
  re-review.

### Fix and recovery

PREFLIGHT, BUILD, REVIEW, fixes, and targeted re-review default to
`gpt-5.6-luna` with `max` reasoning effort. A requested model name or a
child's self-report is not evidence of actual execution; only runtime metadata
that binds the child context to the actual model and effort may support that
claim. Do not add a custom telemetry or audit framework for this purpose.

If the same substantive blocker survives two Luna/max fix-and-re-review
rounds, use temporary `gpt-5.6-sol` with `medium` effort for at most two
rounds. If it remains unresolved, the Main Architect replans from root cause
and escalates only if the issue is now a product, architecture, contract, or
scope decision.

### Formal-gate language

A checkpoint or handoff statement such as “Next gate: formal Codex preflight”
identifies the next repository workflow gate. It instructs the Main Architect
to dispatch the read-only PREFLIGHT when Tier A requires it; it does not ask
the user to create another session or transport a report. The sequence is:

```text
Repository Grounding
→ formal read-only PREFLIGHT
→ Main Architect synthesis and contract freeze
```

### Terminology

**Repository Grounding** means the Main Architect or a child agent reads the
current repository facts needed for its role.

**Formal preflight** means the read-only Tier A gate executed by a PREFLIGHT
child agent and evaluated by the Main Architect.

**Contract freeze** means the Main Architect converts the accepted formal
preflight outcome and resolved product decisions into the exact implementation
boundary used by BUILD.

Do not use Main Architect Repository Grounding as a synonym for formal
preflight.

## Source-of-truth responsibility matrix

| Question | Authoritative source |
| --- | --- |
| Final product direction | `docs/product-direction.md` |
| Active MVP requirements | `docs/mvp-spec.md` |
| Current project state | `docs/project-state.md` and `docs/current-checkpoint.md` |
| Exact technical contracts | Relevant contract document |
| Current implemented behavior | Current production code and tests |
| Development process | `docs/development-workflow.md` |
| Why a durable decision was made | Relevant ADR |
| Historical discussion | Conversation history, background only |

Repository files do not all have equal authority for every question.

## Target state versus implementation state

A product requirement and currently retained code may differ without
contradiction:

```text
Target state:
    active product output is Chinese only

Implementation state:
    English rendering remains implemented but inactive
```

Documentation defines intended active behavior. Code and tests define current
implemented capability. Neither may be silently substituted for the other.

## Information that may use contextual understanding

Context may support stable understanding of why the project exists, the
positive-convexity philosophy, events creating hypotheses while market data
tests pricing, AI explaining rather than deciding, no automatic trading, user
selection of the final exact structure, auditable evidence, and BUILD, test,
and review discipline. Even these concepts remain subject to correction by a
current repository document.

## Information that must never rely on memory

Current repository grounding is mandatory for:

- HEAD and commit parent;
- current milestone and task;
- implemented versus unimplemented state;
- field names and field counts;
- enum values and order;
- reason codes;
- methodology IDs and versions;
- formulas and thresholds;
- public API names and counts;
- test counts;
- file fingerprints;
- authorized and protected files; and
- current validation baselines.

Statements such as “I remember that the field is,” “it was probably,” or “the
previous conversation said” must never be the factual basis for implementation
work.

## Grounding levels

### Lightweight

Use for small documentation wording changes, navigation updates, and low-risk
non-contract edits. At minimum, read the current checkpoint, the target
document, and its directly referenced authoritative document.

### Standard

This is the default for a single-module deterministic capability. At minimum,
read the current checkpoint, the current section of project state, the
relevant product or technical contract section, expected source files, related
tests, and direct public dependencies. Apply the risk-tier workflow: formal
read-only PREFLIGHT is required for Tier A, while Tier B proceeds directly to
BUILD and independent REVIEW.

### High-risk

Use only for public APIs, evidence or provenance boundaries, cross-module
contracts, numerical trust boundaries, and broad compatibility changes. Read
the complete affected call chain and broader regression surface. Do not treat
every task as high-risk.

## Token-minimization rules

- Read task-relevant sections, not every document in full.
- Do not paste complete repository contracts into prompts when Codex can read
  the authoritative files directly.
- Child-agent dispatch context should reference authoritative files and
  sections.
- Copy exact contract text into dispatch context only when it is newly frozen,
  ambiguous in the repository, or necessary to prevent a material error.
- Do not repeat the same decision across multiple documents. Use one canonical
  definition and short cross-references elsewhere.
- Do not rerun a broad review after every small correction. Use targeted
  re-review only for accepted realistic blockers or major defects.
- Do not create ADRs for temporary, local, or easily reversible choices.
- Governance cost must match risk and MVP value.

## Grounding sequence before child dispatch

1. Resolve current Git HEAD and repository cleanliness.
2. Read `docs/current-checkpoint.md`.
3. Read the current section of `docs/project-state.md`.
4. Read only the product and technical sections relevant to the task.
5. Read the expected source files, direct dependencies, and related tests.
6. Record exact opening facts needed by the task.
7. Prepare concise child-agent dispatch context from the current repository
   when a child is useful.

Opening facts may include HEAD, relevant file fingerprints, existing APIs,
test baselines, authorized and protected files, and current expected outputs.
Record only facts materially needed by the task.

## Child-agent dispatch rules

- Dispatch context is a concise reference to repository truth, not a duplicated
  repository.
- Every implementation dispatch states the current expected base commit.
- Every implementation dispatch identifies authorized and protected scope.
- Every implementation dispatch identifies the applicable validation and review
  boundary.
- Re-review must not introduce new unfrozen requirements.
- Conversation memory cannot override repository contracts.

## Checkpoint rules

`docs/current-checkpoint.md` is a short navigation map, not a full
specification, complete project history, or technical contract.

Update it only when a submilestone is committed and pushed, a broad milestone
completes, the accepted product direction changes, the next development gate
changes, a review correction materially changes the next task, or a new
Main Architect milestone thread is about to begin.

Do not update it for uncommitted work, failed intermediate tests, unaccepted
proposals, temporary exploration, or review findings not yet accepted.

Do not hard-code the commit SHA of the commit that contains
`docs/current-checkpoint.md` itself. Resolve current HEAD from Git at read
time. The checkpoint may record the product-direction baseline commit, last
completed implementation checkpoint, current status, next gate, read-first
list, validation baseline, and current prohibitions.

## Main Architect thread continuity

A new Main Architect thread should normally begin at a broad milestone
boundary, a major accepted product-direction change, or when accumulated
conversation history creates material ambiguity. The repository remains the
durable handoff; do not create a new thread for every small subtask.

At a switch, the Main Architect reads a short handoff containing only the
repository, current HEAD resolved from Git, current status, next gate,
read-first files, and the rule that the repository is the source of truth. Do
not migrate the full previous conversation. It becomes historical background,
not an active contract.

When the next gate is a Tier A formal preflight, the Main Architect first
dispatches the read-only PREFLIGHT child and does not begin synthesis/contract
freeze or BUILD while it has unresolved blockers. The Main Architect does not
present Repository Grounding as the formal preflight result.

The required startup workflow is:

```text
new Main Architect thread
→ Repository Grounding
→ formal read-only PREFLIGHT when Tier A requires it
→ Main Architect synthesis and contract freeze
→ BUILD / REVIEW / validation according to the risk tier
```

Keep the handoff short and repository-grounded. Do not add complete product or
technical contracts to it.

## ADR rules

Create an ADR only when a decision is cross-cutting, durable, likely to be
questioned again, costly to reverse, and not fully explained by the final
specification alone.

Do not create an ADR for temporary implementation details, individual field
names already fixed by a contract, routine threshold changes, local
refactors, or unaccepted proposals.

ADRs explain why. Contracts explain what. Project state explains where the
project currently is.

## Governance maintenance principle

Stable governance rules are written once and reused. Dynamic status remains
minimal and changes only when materially necessary.

Accuracy takes priority over token minimization, but unnecessary repeated
context is not a form of accuracy.
