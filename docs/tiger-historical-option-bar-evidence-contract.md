# Tiger Historical Option-Bar Evidence v0.1

## Status and purpose

This Tier-A contract freezes a bounded read-only Tiger adapter for completed
historical US-option daily bars. Formal preflight used Tiger SDK 3.7.0 source,
Tiger's official option-bar documentation, the existing provider-neutral core,
and a sanitized live SPY probe. The live probe returned 60 daily rows with all
documented fields populated for one explicitly monthly 103-DTE contract,
spanning 2026-05-13 through 2026-08-07.

Implementation and independent review are complete.

Tiger supplies daily OHLC, volume, and open interest with a bar-start
timestamp. It supplies no historical bid/ask, implied volatility, or Greeks in
this response. The provider-neutral core has no historical option-OHLC record,
and Tiger does not define whether each daily open-interest value applies at the
start or end of the bar. This unit therefore retains immutable Tiger-native
evidence and makes no stronger normalization claim.

## Public boundary

The direct module `convexity_hunter.providers.tiger` adds exactly:

```text
TigerHistoricalOptionBarEvidence
retrieve_tiger_historical_option_bar_evidence
```

The module therefore exports exactly eleven names. Nothing is re-exported from
a package root, and the provider-neutral core remains unchanged.

`TigerHistoricalOptionBarEvidence` is frozen and contains exactly:

```text
contract_verification: TigerExactOptionContractVerification
bar_started_at: datetime
session_date: date
open_premium: Decimal
high_premium: Decimal
low_premium: Decimal
close_premium: Decimal
volume: int
open_interest: int
retrieved_at: datetime
```

The exact verified Tiger identifier and normalized contract key remain
available through `contract_verification`. Prices are provider-supplied option
premiums. Volume and open interest retain Tiger's documented contract-count
fields without changing the unresolved open-interest applicability semantics.

## Request boundary

The retrieval function accepts an initialized quote client, one exact
`TigerExactOptionContractVerification`, and keyword-only inclusive
`begin_date`, exclusive `end_date`, and `latest_completed_session_date`.
Dates are exact date-only values; begin must precede end, the range must not
exceed 370 calendar days, and end must not include an incomplete US session.

Each date boundary is converted from `America/New_York` midnight to aware UTC
and then to an integer Unix timestamp in milliseconds. The function makes
exactly one call:

```python
quote_client.get_option_bars(
    [contract_verification.provider_identifier],
    begin_time=<begin Unix milliseconds>,
    end_time=<end Unix milliseconds>,
    period="day",
    limit=None,
    sort_dir=None,
    market="US",
    timezone="US/Eastern",
)
```

The explicit timezone is local to this request and does not modify the Tiger
client's global timezone. No permission, chain, quote, underlying-bar,
dividend, rate, account, order, or execution request is authorized. SDK
failures are sanitized.

## Response validation

`None` or an empty table is valid evidence that the bounded response contains
no traded daily bars and returns an empty tuple. A nonempty table must expose
exactly:

```text
identifier symbol expiry put_call strike time
open high low close volume open_interest
```

Every row must match the verified provider identifier, underlying symbol,
expiration timestamp, option type, and strike exactly. `time` is Tiger's
documented bar-start millisecond timestamp. It is retained as aware UTC and
converted through `America/New_York` only to derive the explicit session date.
The session must be inside `[begin_date, end_date)` and not later than the
caller-declared latest completed session.

OHLC values use only `Decimal(str(value))`, must be finite and positive, and
must satisfy normal bar ordering. Volume and open interest must be nonnegative
integers. Duplicate timestamps or duplicate session dates fail closed. Results
are returned in deterministic chronological order independent of provider row
order.

Receipt time is captured immediately after the table returns and normalized to
aware UTC. No raw table, payload, SDK object, request object, credential,
account identifier, secret, token, or local credential path is retained.

## Failure precedence

```text
exact verification and bounded dates
-> method availability
-> one request and sanitized failure
-> table shape
-> rows in provider order
-> duplicate detection
-> deterministic immutable tuple
```

Errors never echo provider rows, identifiers supplied by an untrusted response,
or raw SDK exception text.

## Required tests

Synthetic tests cover exact EST and EDT millisecond request boundaries,
DST-safe session conversion, exact API arguments, no-data behavior, exact
contract identity, OHLC/volume/open-interest validation, malformed tables and
scalars, duplicate rejection, completed-range enforcement, deterministic
ordering, immutability, sanitized exceptions, public boundaries, and no
import/network/credential side effects. A local live smoke may print only row
counts, schema facts, bounded session dates, null counts, and exact-identity
facts; it persists no raw market payload.

## Explicit exclusions

This unit creates no `OptionQuoteObservation`, `OptionVolumeObservation`,
`OptionOpenInterestObservation`, historical option-OHLC provider-neutral
record, IV, Greeks, bid/ask, freshness claim, completeness claim, interpolation,
deterministic IV reconstruction, pricing input, report change, credential
change, contract discovery, or trading capability. Historical IV and Greeks
remain `requires deterministic reconstruction` from separately accepted
inputs.
