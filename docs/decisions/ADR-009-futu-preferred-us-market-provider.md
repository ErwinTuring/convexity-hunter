# ADR-009: Futu preferred U.S. market-data provider

Status: Accepted
Decision date: 2026-08-18

## Context

Tiger remains useful for local historical and reference evidence, but its
current-quote path is blocked by U.S. stock Push entitlement and incomplete
quote/session semantics. A bounded Futu OpenD feasibility review with the
user's OPRA entitlement proved exact monthly/standard contract classification,
exact option and underlying history, current option analytics/activity, and
atomic provider-native option/underlying BBO frames.

## Decision

Futu OpenAPI is the preferred MVP U.S. market-data provider. Tiger remains a
frozen fallback capability; this decision creates no automatic failover,
routing, arbitration, or provider blending.

Convexity Hunter connects only to an already-authenticated local Futu OpenD
instance. OpenD owns credentials, and repository code neither reads nor stores
them.

## Rationale

Futu supplies more of the exact-contract and historical evidence needed by the
Real Direct Entry vertical slice at acceptable personal-research cost. Keeping
provider-neutral records independent preserves the core architecture while
avoiding a premature multi-provider framework.

## Rejected alternatives

- paying for Tiger U.S. stock API Push solely to unblock the vertical slice;
- treating Tiger or Futu as a universal source for every evidence category;
- automatic provider failover, precedence, or blended records; and
- lowering current-quote, deliverable, activity, or Greeks evidence standards.

## Consequences

Futu's explicit `STANDARD` classification is retained provider-natively but
does not prove exact OCC deliverable contents. Atomic BBO retains separate
opaque provider timestamp-field values when populated, but Futu explicitly
does not support their server-receive-time capability for U.S. securities.
They authorize no time, freshness, session, provider-neutral current-quote, or
quote-scope claim. Tiger code and external local configuration remain
unchanged and available as fallback evidence.

## Related documents

- `docs/futu-provider-contract.md`
- `docs/tiger-provider-contract.md`
- `docs/real-direct-entry-vertical-slice-plan.md`
- `docs/mvp-spec.md`
