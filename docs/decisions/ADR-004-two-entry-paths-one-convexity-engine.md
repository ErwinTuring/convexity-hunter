# ADR-004: Two entry paths converge on one Convexity Engine

Status: Accepted
Decision date: 2026-07-30

## Context

Research may begin with Event Intelligence or with a structure supplied by the
user.

## Decision

Entry A begins with Event Intelligence and real option-chain candidate
generation. Entry B begins with a user-supplied structure. Both converge on
one verified exact `OptionStructure`.

Direct entry does not require an Event Intelligence hypothesis. It cannot
bypass real contract verification, supported structure grammar, DTE policy,
quote and reference validation, provenance, lineage, or Convexity Engine
analysis. The system must never invent a missing contract.

## Rationale

One verification and research boundary prevents a weaker direct-entry path.

## Rejected alternatives

Separate weaker validation rules for user-entered structures.

## Consequences

Both entry modes share the same evidence and Convexity Engine standards.

## Related documents

- `docs/product-direction.md`
- `docs/mvp-spec.md`
