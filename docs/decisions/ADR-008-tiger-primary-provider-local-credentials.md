# ADR-008: Tiger primary provider with local provider-native credentials

Status: Accepted
Decision date: 2026-08-09

## Context

The completed feasibility spike established that Tiger OpenAPI can supply the
bounded option and underlying market-data universe required for the MVP, with
known gaps in historical derived analytics, term-curve inputs, and some quote
and Greek semantics. Convexity Hunter is a public shared repository, while
Tiger credentials belong to each local user.

## Decision

Tiger OpenAPI is the MVP primary market-data provider. Provider-neutral core
contracts remain vendor-independent.

Tiger's official `tiger_openapi_config.properties` remains outside the
repository and is resolved at runtime from one path-only environment override
or the conventional user configuration path. Credentials are never copied
into a Convexity Hunter schema or passed through model context.

## Rationale

One proven primary provider reaches the real-data vertical slice with less
cost and ambiguity than premature multi-provider routing. Reusing the official
local configuration avoids a second secret schema and makes credential
discovery deterministic without model involvement.

## Rejected alternatives

- generic provider routing, precedence, arbitration, and failover for MVP;
- repository-local credentials or shared application defaults;
- chat- or LLM-mediated credential entry;
- a new secret database, cloud vault, OAuth-like flow, or generic secret
  framework; and
- treating Tiger as the sole future source of every reference input.

## Consequences

Provider access lives outside `market_data.py` and downstream research
services. Tiger-specific uncertainty must remain explicit. Historical IV and
Greeks require deterministic reconstruction, and a bounded external USD term
curve may be added later without becoming quote-provider arbitration.

## Related documents

- `docs/tiger-provider-contract.md`
- `docs/market-data-contracts.md`
- `docs/product-direction.md`
- `docs/mvp-spec.md`
