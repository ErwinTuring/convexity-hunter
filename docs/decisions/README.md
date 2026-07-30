# Architecture Decision Records

ADRs preserve the rationale for durable, cross-cutting decisions that are
likely to be questioned again, costly to reverse, and not fully explained by
the final specification alone.

An ADR is required for such decisions. It is not required for temporary
implementation details, contract-fixed field names, routine threshold
changes, local refactors, easily reversible choices, or unaccepted proposals.

Allowed statuses are `Proposed`, `Accepted`, `Superseded`, and `Rejected`.
Files use `ADR-NNN-short-kebab-case-title.md`.

ADRs explain why. Contracts define what. `docs/project-state.md` records where
the project currently is. An ADR must not duplicate a full contract.

## Template

```text
# ADR-NNN: Title

Status:
Decision date:

## Context

## Decision

## Rationale

## Rejected alternatives

## Consequences

## Related documents
```
