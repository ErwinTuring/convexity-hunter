# ADR-006: First-report management conditions without monitoring

Status: Accepted
Decision date: 2026-07-30

## Context

Users need conditions for later judgment without turning the product into a
position-monitoring or execution service.

## Decision

The first Chinese research report includes monetization, reassessment, exit,
and limitation conditions. Conditions should be quantitative where evidence
permits and guide later human judgment.

The product does not monitor positions, schedule checks, send alerts, trigger
exits, or execute trades. The report uses language equivalent to “consider
monetization,” “consider reassessment,” and “consider exit.” Quantitative
values use executable evidence where available, not unsupported theoretical
values.

## Rationale

Predeclared conditions improve disciplined human review without claiming
ongoing automation or authority to trade.

## Rejected alternatives

A monitoring service, automatic 2x take-profit, universal percentage drawdown
stop, and automatic sell instruction.

## Consequences

Position management remains a human responsibility after the first report.

## Related documents

- `docs/product-direction.md`
- `docs/mvp-spec.md`
- `docs/philosophy.md`
