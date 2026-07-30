# ADR-002: Events create hypotheses; market data tests pricing

Status: Accepted
Decision date: 2026-07-30

## Context

Event narratives and numerical market evidence serve different trust roles.

## Decision

Event Intelligence identifies events, affected underlyings, impact paths, and
distribution-change hypotheses. These outputs remain research hypotheses and
interpreted evidence. Numerical market data determines whether relevant
convexity appears insufficiently priced.

AI may explain and organize evidence but cannot invent prices, IV, Greeks,
historical observations, scenario values, or probabilities.

## Rationale

Separating hypothesis formation from numerical testing preserves an auditable
pricing boundary.

## Rejected alternatives

An architecture in which narrative confidence directly becomes a numerical
opportunity score or trade decision.

## Consequences

Event Intelligence and the Convexity Engine remain separate but connected.

## Related documents

- `docs/product-direction.md`
- `docs/philosophy.md`
- `docs/mvp-spec.md`
