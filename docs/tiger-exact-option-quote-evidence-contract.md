# Tiger Exact Option Quote Evidence v0.1

## Status and purpose

This Tier-A contract freezes the third Tiger provider work unit. It acquires
one current bid/ask snapshot for an already verified exact Tiger option contract
and proves that the runtime has active `usOptionQuote` entitlement before the
quote request.

Implementation status: complete and independently reviewed.

It deliberately returns transient Tiger-specific evidence, not an
`OptionQuoteObservation`:

```text
TigerExactOptionContractVerification
    -> active usOptionQuote permission evidence
    -> exact-expiration Tiger chain request
    -> exactly one exact provider-identifier/economic match
    -> TigerExactOptionQuoteEvidence
```

Tiger's chain supplies no quote timestamp or quote session date.
`last_timestamp` is last-trade time and may be zero. Receipt-derived calendar
date is not a market session date on weekends, holidays, or some after-hours
requests. The existing provider-neutral quote record requires `session_date`.
This work unit therefore refuses to invent that field and does not weaken the
core contract merely to complete a mapping.

## Public boundary

The direct module `convexity_hunter.providers.tiger` adds exactly:

```text
TigerExactOptionQuoteEvidence
retrieve_tiger_exact_option_quote_evidence
```

Together with the first two Tiger work units, the direct module exports exactly
six names. No Tiger name is re-exported from package roots. The provider-neutral
core does not import this module or the Tiger SDK.

The function accepts an already initialized quote client and one
`TigerExactOptionContractVerification`. It resolves no credentials, constructs
no client, grabs no permission, and accepts no incomplete contract description.

## Authorized requests and order

The function makes exactly two read-only requests:

1. `get_quote_permission()`;
2. only after active `usOptionQuote` evidence succeeds,
   `get_option_chain(symbol, expiration.isoformat(),
   return_greek_value=False, market="US")`.

It makes no expiration, quota, history, underlying, dividend, rate, license,
permission-grab, account, order, or execution request. Raw SDK errors are
replaced with stable sanitized failures.

## Permission proof

The permission response must be a list or tuple of mappings with exact `name`
and `expire_at` fields. Every entry must have a string name and a non-Boolean
integer expiration. `expire_at == -1` means provider-declared permanent
entitlement; a positive millisecond Unix timestamp is finite entitlement. Other
values are invalid.

Exactly one `name == "usOptionQuote"` entry is required. A positive expiration
must be later than both the permission-response receipt time and quote-response
receipt time. Missing, duplicate, malformed, or expired evidence fails closed.
The adapter records an aware UTC receipt timestamp immediately after each SDK
response returns.

This proves provider entitlement for the bounded acquisition. It does not prove
NBBO, consolidated aggregation, quote venue, market phase, session date, quote
observation time, or absence of all provider-side latency.

## Exact chain-row proof

The chain response must expose:

```text
identifier
symbol
expiry
strike
put_call
multiplier
bid_price
ask_price
bid_size
ask_size
```

The exact row must uniquely match the verification object's provider
identifier, underlying symbol, provider expiration timestamp, exact Decimal
strike, call/put direction, and provider-supplied multiplier. There is no
nearest strike, alternate expiration, identifier substitution, or row ranking.

`bid_price` is converted with `Decimal(str(value))`, must be finite and
nonnegative. `ask_price` must be finite, positive, and not below bid. Sizes are
provider contract counts; a missing/NaN size becomes `None`, while a present
size must be a finite nonnegative integer value and is normalized to built-in
`int`. Locked quotes are retained; crossed quotes fail.

The adapter does not read or retain last price, last-trade timestamp, volume,
open interest, IV, Greeks, or raw payload fields.

## Returned evidence

`TigerExactOptionQuoteEvidence` is frozen and contains exactly:

```text
contract_verification
bid_premium
ask_premium
bid_size
ask_size
permission_expire_at_ms
permission_received_at
quote_received_at
```

Direct construction repeats exact type, price, size, permission-expiry, UTC
timestamp ordering, and frozen verification invariants. No credential,
credential path, Tiger/account identifier, token, secret, license, SDK object,
request object, raw row, or unselected chain field is retained.

This object is runtime evidence, not repository state, a candidate research
record, calculation lineage, report input, or permission cache. It may be
consumed only by a later separately reviewed normalizer that can supply an
auditable option-session context.

## Accepted normalization decision

Provider-neutral option-quote normalization remains deferred until
authoritative Tiger evidence establishes the REST chain quote's aggregation
scope, quote timestamp/session association, and any required latency meaning.
The product will not infer `PROVIDER_COMPOSITE` from adjacent BBO subscription
documentation, assign `CONSOLIDATED`, derive a session from last-trade time, or
create an `OptionQuoteObservation` with `QuoteScope.UNKNOWN` merely to move an
otherwise ineligible/unknown record into the strict research pipeline.

Development continues through other Tiger facts whose semantics are already
established. This is a bounded deferral, not a reversal of Tiger's primary-
provider decision.

## Failure precedence

```text
verification input
-> permission method/request
-> permission container and entry shape
-> exact active usOptionQuote uniqueness
-> chain method/request
-> chain table shape
-> exact row uniqueness and identity
-> price/size normalization
-> permission still active at quote receipt
-> frozen evidence construction
```

All failures use stable sanitized `TypeError`, `ValueError`, or `RuntimeError`
messages and never echo provider payloads or raw exception text.

## Tests and live verification

Committed tests use fake clients and synthetic rows only. They cover exact
request order/arguments, no chain call without permission, permanent and finite
entitlement, missing/duplicate/expired/malformed permission, exact-row identity,
no substitution, provider numeric representations, missing sizes, locked and
crossed quotes, malicious accessors/scalars, frozen output, public boundaries,
and absence of credential/network side effects on import.

A local post-test smoke check may use the user's external provider-native
configuration and one already verified real contract. It prints only selected
normalized non-sensitive fields and persists no raw payload.

## Explicit exclusions

This work unit adds no `OptionQuoteObservation`, session date, market phase,
quote scope, venue, freshness claim, delayed-status claim, volume, open
interest, IV, Greeks, historical data, current underlying quote, discovery,
DTE/event policy, structure generation, provider routing, caching, monitoring,
scheduling, reports, orders, or execution.
