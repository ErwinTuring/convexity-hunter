# ADR-001: Repository truth and grounded implementation planning

Status: Accepted
Decision date: 2026-07-30

## Context

Long-running conversations may compress, weaken, or confuse early details.
Similar milestone names, revised contracts, stale test counts, old field
names, and historical decisions may coexist in memory.

## Decision

The current repository is authoritative for exact project facts. ChatGPT must
ground implementation planning in the current HEAD before producing a
code-related Codex prompt. Conversation memory provides context only.

## Rationale

This prevents old conversation content from silently overriding current
contracts and permits new milestone conversations without migrating the full
history.

## Rejected alternatives

- relying on the complete conversation as the primary specification;
- copying the full repository into every new prompt; and
- reading every repository file for every task.

## Consequences

Grounding is task-scoped and risk-proportional. Exact values are reread;
stable design understanding may remain contextual.

## Related documents

- `docs/context-governance.md`
- `docs/current-checkpoint.md`
- `docs/development-workflow.md`
- `docs/project-state.md`
