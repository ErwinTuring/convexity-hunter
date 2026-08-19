# Futu Option-Chain Discovery Evidence Contract v0.1

## Purpose

This Tier-A contract consumes one exact provider-neutral
`OptionChainDiscoveryRequest` and retrieves only the bounded Futu expiration
and option-chain rows needed to expose provider classifications. It does not
select, rank, quote, normalize, or generate an option structure.

The direct module `convexity_hunter.providers.futu` adds exactly:

```text
FutuOptionChainRowStatus
FutuOptionChainExpirationEvidence
FutuOptionChainContractEvidence
FutuOptionChainDiscoveryEvidence
retrieve_futu_option_chain_discovery_evidence
```

Nothing is re-exported from a package module.

## Provider calls

The function calls `get_option_expiration_date` exactly once for the request
underlying. It parses every expiration row fail closed, retains every date in
the request's inclusive interval, and rejects duplicate retained dates.

In ascending date order, it calls `get_option_chain` exactly once for each
retained expiration whose provider cycle is exactly `MONTH`. Each call uses
the same exact date for Futu's inclusive `start` and `end` parameters. It does
not call a chain for any other cycle and calls no snapshot, BBO, analytics,
history, Delta, ATM, ranking, or generation method.

Valid empty responses remain explicit empty evidence rather than errors.

## Retained evidence and classification

Every structurally valid chain row is retained. The exact request is retained
by identity. Expirations are ordered by date. Contracts are ordered by
expiration, strike, call before put, and provider identifier.

Each contract carries all applicable statuses in this fixed order:

```text
NON_MONTHLY
NON_STANDARD
SUSPENDED
```

When none applies, its status is exactly `ELIGIBLE`. A chain row inconsistent
with the expiration's `MONTH` classification is retained as `NON_MONTHLY`.
Non-standard and suspended rows are likewise evidence, not silently filtered
or promoted.

The provider identifier, underlying, expiration, call/put, strike, lot size,
cycle, standard type, suspension state, and receipt time are retained. Its
encoded expiration, call/put, and strike must agree with the row. A provider
`STANDARD` row additionally requires the encoded root to match the request
symbol. A non-standard provider root may differ because this boundary makes no
OCC identity or deliverable claim.

Receipt timestamps are aware UTC adapter times captured immediately after
each provider response. They are not provider observation timestamps.

## Failure boundary

Malformed response tables, missing fields, malformed dates or identifiers,
invalid identity, non-finite or non-positive strikes, non-positive or
non-integral lot sizes, non-Boolean suspension values, duplicate expiration
dates, and duplicate provider identifiers fail the whole request. Provider
exceptions and non-success codes become stable sanitized `RuntimeError`s;
payloads and provider error text are never returned.

Distinct provider identifiers with otherwise identical economics remain
distinct because exact deliverables are unresolved.

## Authority boundary

`MONTH + STANDARD + not suspended` establishes only Futu-classified series
eligibility for later deterministic policy work. It does not establish an
exact standard or unadjusted deliverable, OCC identity, settlement, completed
`OptionContractReference`, `StructureCosts`, liquidity, research readiness,
or a recommendation.

## Non-goals

This unit adds no automatic expiration or strike selection, option structure,
Delta/ATM logic, market quote, freshness, quote scope, activity, analytics,
pricing, costs, liquidity, candidate assembly, screening, report, monitoring,
trading, provider routing, or Tiger change.
