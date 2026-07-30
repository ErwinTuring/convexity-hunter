# ADR-005: Explicit risk assumptions are required for bearability

Status: Accepted
Decision date: 2026-07-30

## Context

Supported option-long structures have bounded maximum loss, but bounded loss
does not prove that the loss is bearable for a specific user.

## Decision

Bearability requires explicit assumptions such as portfolio value and declared
risk boundaries. The product imposes no universal risk percentage. Without
required assumptions, it reports absolute cost and maximum loss but marks
affordability `Data insufficient`. It does not recommend an optimal number of
contracts in the active MVP.

## Rationale

Personal affordability cannot be inferred from payoff shape or by AI.

## Rejected alternatives

A universal “one percent per trade” rule and AI-inferred personal risk
tolerance.

## Consequences

Absolute risk remains reportable without caller assumptions; bearability does
not.

## Related documents

- `docs/product-direction.md`
- `docs/mvp-spec.md`
- `docs/screening-policy.md`
