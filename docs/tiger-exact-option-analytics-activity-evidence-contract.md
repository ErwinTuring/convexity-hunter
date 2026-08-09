# Tiger Exact Option Analytics and Activity Evidence v0.1

## Status and purpose

This Tier-A contract freezes a bounded read-only Tiger adapter for one already
verified exact monthly option. Formal preflight used Tiger SDK 3.7.0 source,
Tiger's official option-chain documentation, the provider-neutral core, and a
sanitized live 103-DTE SPY probe.

The live response populated volume, open interest, implied volatility, Delta,
Gamma, Theta, Vega, Rho, and last-trade time. It supplied no analytics
observation timestamp, analytics session, model identity, rate-input
description, dividend-input description, or Theta day basis. Last-trade time
does not timestamp provider analytics or activity fields. This unit therefore
retains immutable Tiger-native evidence and makes no provider-neutral
normalization claim.

## Public boundary

The direct module `convexity_hunter.providers.tiger` adds exactly:

```text
TigerExactOptionAnalyticsActivityEvidence
retrieve_tiger_exact_option_analytics_activity_evidence
```

The module therefore exports exactly thirteen names. Nothing is re-exported
from a package root, and the provider-neutral core remains unchanged.

`TigerExactOptionAnalyticsActivityEvidence` is frozen and contains exactly:

```text
contract_verification: TigerExactOptionContractVerification
volume: int
open_interest: int
implied_volatility: Decimal
delta: Decimal
gamma: Decimal
theta: Decimal
vega: Decimal
rho: Decimal
last_trade_at: datetime
retrieved_at: datetime
```

All decimal fields retain Tiger's textual numeric representation through
`Decimal(str(value))`. They remain in Tiger's provider-native conventions.
Vega is not rescaled to the core's absolute-IV convention, Theta receives no
invented day basis, Rho is not added to the provider-neutral core, and no field
is attributed to an undisclosed model or input set.

## Request boundary

The retrieval function accepts an initialized quote client and one exact
`TigerExactOptionContractVerification`. It makes exactly one call:

```python
quote_client.get_option_chain(
    contract_verification.contract_reference.contract_key.underlying_key.symbol,
    contract_verification.contract_reference.contract_key.expiration.isoformat(),
    return_greek_value=True,
    market="US",
)
```

No permission, quote-brief, expiration, bar, dividend, rate, account, order, or
execution request is authorized. SDK failures are sanitized.

## Response validation

The table must expose at least:

```text
identifier symbol expiry strike put_call multiplier
volume open_interest last_timestamp
implied_vol delta gamma theta vega rho
```

Exactly one row must match the verified provider identifier, symbol,
expiration, option type, strike, and provider-supplied multiplier. Nearby or
duplicate contracts never substitute.

Volume and open interest must be nonnegative integers. Implied volatility must
be finite and positive. Delta must be finite and inside `[-1, 1]`; Gamma and
Vega must be finite and nonnegative; Theta and Rho must be finite. Negative
zero is normalized to ordinary zero. `last_timestamp` must be a positive Unix
millisecond timestamp not later than receipt time and is retained only as
`last_trade_at`.

Receipt time is captured immediately after the response and normalized to
aware UTC. No raw table, unrelated chain row, quote fields, payload, SDK
object, request object, credential, account identifier, secret, token, or local
credential path is retained.

## Failure precedence

```text
exact verification
-> method availability
-> one request and sanitized failure
-> table shape
-> exact verified-row cardinality
-> identity and numeric validation
-> immutable evidence
```

Errors never echo provider rows, untrusted identifiers, or raw SDK exception
text.

## Required tests

Synthetic tests cover exact API arguments, exact-row binding, nearby and
duplicate rejection, zero activity counts, every numeric domain, negative-zero
normalization, last-trade/receipt chronology, malformed tables and scalars,
frozen direct construction, pandas/numpy compatibility, sanitized failures,
public boundaries, and no import/network/credential side effects. A local live
smoke may print only field presence, null facts, range facts, and exact-identity
facts; it persists no raw market payload.

## Explicit exclusions

This unit creates no `OptionQuoteObservation`, `OptionVolumeObservation`,
`OptionOpenInterestObservation`, `OptionImpliedVolatilityObservation`,
`OptionGreeksObservation`, current quote, session date, analytics timestamp,
freshness claim, model claim, rate/dividend input claim, Greek unit conversion,
historical analytics, pricing input, report change, credential change,
discovery, or trading capability. Provider-neutral analytics require a
separate contract that resolves timestamp/session, model/input descriptions,
Vega scaling, and Theta day convention without invention.
