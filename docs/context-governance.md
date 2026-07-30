# Context Governance

## Purpose

The objective is not to make ChatGPT remember everything. It is to ensure that
forgetting, compression, ambiguity, or stale conversation history cannot
silently change the implementation contract.

Conversation history provides background and design understanding. The current
repository provides authoritative project facts.

## Five-layer error-prevention system

1. **Repository truth.** Repository contracts define the accepted state.
2. **Grounded planning.** ChatGPT grounds implementation planning in the
   current repository.
3. **Codex preflight and BUILD.** Preflight checks feasibility and
   contradictions before BUILD.
4. **Automated tests.** Tests verify machine-checkable invariants.
5. **Independent review.** Review looks for realistic contract and
   implementation defects.

ChatGPT is an intentionally non-authoritative and potentially incomplete
planning node.

## ChatGPT and Codex execution-role boundaries

This section is the canonical definition of the roles used by the manual
ChatGPT/Codex workflow.

### ChatGPT main conversation

The ChatGPT main conversation is the grounded planning and prompt-authoring
layer. It:

- verifies and reads the current repository through available repository
  tools;
- interprets product decisions and current contracts;
- identifies the next formal workflow gate;
- writes the complete prompt for the appropriate separate Codex session;
- evaluates Codex PREFLIGHT, BUILD, and REVIEW reports returned by the user;
- resolves or surfaces remaining product decisions;
- freezes the accepted implementation contract after the formal preflight
  report has been evaluated and accepted; and
- writes later BUILD, REVIEW, correction, re-review, commit, and documentation
  prompts as applicable.

The ChatGPT main conversation is not the formal Codex preflight executor. When
the next gate is a formal Codex preflight, it must not:

- return its own formal `READY` or `BLOCKED` result;
- present its own analysis as the completed repository preflight;
- freeze exact implementation fields, enums, APIs, file scope, fingerprints,
  or test counts before the formal Codex preflight report; or
- skip directly to BUILD.

ChatGPT may perform Repository Grounding and planning analysis sufficient to
write a precise preflight prompt. That Grounding is not the formal workflow
gate.

### Codex PREFLIGHT session

The Codex PREFLIGHT session:

- is a separate manually created Codex session;
- performs the formal read-only repository preflight;
- independently verifies repository state, contracts, source, tests,
  numerical boundaries, provenance, lineage, API impact, file scope, and
  validation scope;
- makes no repository modifications; and
- returns a structured report ending in `READY` or `BLOCKED`.

Only that returned formal report satisfies the preflight-execution step.
ChatGPT subsequently evaluates the report; it does not retroactively replace
the Codex preflight with its own analysis.

### Codex BUILD session

The Codex BUILD session:

- is a separate manually created Codex session;
- implements only the accepted and frozen contract;
- does not begin while the required formal preflight remains unresolved;
- runs the required validation;
- keeps implementation uncommitted until the required review gate passes;
- applies accepted corrections in the same BUILD session; and
- performs the final commit and push when instructed.

### Codex REVIEW session

The Codex REVIEW session:

- is separate from BUILD;
- reads repository contracts and the actual diff independently;
- performs one broad review by default;
- does not implement fixes;
- uses targeted re-review only for accepted realistic blockers or major
  defects; and
- does not introduce unrelated or newly invented requirements during targeted
  re-review.

### Formal-gate language

A checkpoint or handoff statement such as “Next gate: formal Codex preflight”
identifies the next repository workflow gate. It does not instruct the ChatGPT
main conversation to execute that gate itself. The ChatGPT main conversation's
immediate task is instead:

```text
Repository Grounding
→ author the formal Codex PREFLIGHT prompt
```

### Terminology

**Repository Grounding** means ChatGPT or Codex reads the current repository
facts needed for its role.

**Formal preflight** means the read-only gate executed in the separate Codex
PREFLIGHT session.

**Contract freeze** means ChatGPT converts the accepted formal preflight
outcome and resolved product decisions into the exact implementation boundary
used by BUILD.

Do not use “ChatGPT preflight” as a synonym for Repository Grounding.

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
tests, and direct public dependencies. Require a read-only preflight, BUILD,
automated validation, and one broad independent review.

### High-risk

Use only for public APIs, evidence or provenance boundaries, cross-module
contracts, numerical trust boundaries, and broad compatibility changes. Read
the complete affected call chain and broader regression surface. Do not treat
every task as high-risk.

## Token-minimization rules

- Read task-relevant sections, not every document in full.
- Do not paste complete repository contracts into prompts when Codex can read
  the authoritative files directly.
- Prompts should reference authoritative files and sections.
- Copy exact contract text into a prompt only when it is newly frozen,
  ambiguous in the repository, or necessary to prevent a material error.
- Do not repeat the same decision across multiple documents. Use one canonical
  definition and short cross-references elsewhere.
- Do not rerun a broad review after every small correction. Use targeted
  re-review only for accepted realistic blockers or major defects.
- Do not create ADRs for temporary, local, or easily reversible choices.

## Grounding sequence before implementation prompts

1. Resolve current Git HEAD and repository cleanliness.
2. Read `docs/current-checkpoint.md`.
3. Read the current section of `docs/project-state.md`.
4. Read only the product and technical sections relevant to the task.
5. Read the expected source files, direct dependencies, and related tests.
6. Record exact opening facts needed by the task.
7. Generate the Codex prompt from the current repository.

Opening facts may include HEAD, relevant file fingerprints, existing APIs,
test baselines, authorized and protected files, and current expected outputs.
Record only facts materially needed by the task.

## Prompt construction rules

- Prompts are concise references to repository truth, not duplicated
  repositories.
- Every implementation prompt states the current expected base commit.
- Every implementation prompt identifies authorized and protected scope.
- Every implementation prompt identifies the applicable validation and review
  boundary.
- Re-review must not introduce new unfrozen requirements.
- Conversation memory cannot override repository contracts.

## Checkpoint rules

`docs/current-checkpoint.md` is a short navigation map, not a full
specification, complete project history, or technical contract.

Update it only when a submilestone is committed and pushed, a broad milestone
completes, the accepted product direction changes, the next development gate
changes, a review correction materially changes the next task, or a new
ChatGPT milestone conversation is about to begin.

Do not update it for uncommitted work, failed intermediate tests, unaccepted
proposals, temporary exploration, or review findings not yet accepted.

Do not hard-code the commit SHA of the commit that contains
`docs/current-checkpoint.md` itself. Resolve current HEAD from Git at read
time. The checkpoint may record the product-direction baseline commit, last
completed implementation checkpoint, current status, next gate, read-first
list, validation baseline, and current prohibitions.

## ChatGPT conversation-switching rule

A new ChatGPT main conversation should normally begin at a broad milestone
boundary, a major accepted product-direction change, or when accumulated
conversation history creates material ambiguity. Do not create one for every
small subtask.

At a switch, use a short handoff containing only the repository, current HEAD
resolved from Git, current status, next gate, read-first files, and the rule
that the repository is the source of truth. Do not migrate the full previous
conversation. It becomes historical background, not an active contract.

When the next gate is a formal Codex preflight, the handoff must also state
that the ChatGPT conversation is the grounded planning and prompt-authoring
layer, must not perform the formal preflight itself, and must first deliver
the separate Codex PREFLIGHT session name and one complete preflight prompt.
It must not generate a BUILD prompt before the Codex preflight report is
returned and accepted.

The required startup workflow is:

```text
new ChatGPT main conversation
→ Repository Grounding
→ complete Codex PREFLIGHT prompt
→ user manually runs that prompt in a separate Codex PREFLIGHT session
→ user returns the Codex report
→ ChatGPT evaluates and freezes the accepted contract
→ ChatGPT writes the later BUILD prompt
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
