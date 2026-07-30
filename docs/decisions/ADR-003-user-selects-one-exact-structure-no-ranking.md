# ADR-003: User selects one exact structure without automatic ranking

Status: Accepted
Decision date: 2026-07-30

## Context

Event discovery may produce multiple eligible underlyings and structures.

## Decision

Eligibility is controlled by business and technical rules, not arbitrary
absolute caps. Layered interaction controls information volume. The user
ultimately selects one verified exact structure.

The system does not calculate a universal Convexity Score or automatically
rank candidates by investment attractiveness. Stable display ordering is
permitted but is not a recommendation.

## Rationale

This keeps investment judgment with the user while allowing deterministic
eligibility and manageable presentation.

## Rejected alternatives

Automated first-place selection, cross-candidate investment scoring, and
portfolio optimization in the active MVP.

## Consequences

The selected exact structure, not a ranking, is the final research unit.

## Related documents

- `docs/product-direction.md`
- `docs/mvp-spec.md`
- `docs/screening-policy.md`
