# Tiger Historical Dividend Evidence v0.1

## Status and purpose

This Tier-A contract freezes a bounded read-only Tiger adapter for historical
corporate-dividend evidence. Implementation and independent review are pending.

Tiger SDK 3.7.0 documents `amount` only as a dividend amount. It does not state
that the value is per underlying share and does not classify regular versus
special distributions. The adapter therefore must not construct the existing
provider-neutral `DividendObservation`, whose cash unit is USD per share and
whose dividend type and lifecycle status carry stronger semantics.

## Public boundary

The direct module `convexity_hunter.providers.tiger` adds exactly:

```text
TigerHistoricalDividendEvidence
retrieve_tiger_historical_dividend_evidence
```

The module therefore exports exactly nine names. Nothing is re-exported from a
package root, and the provider-neutral core remains unchanged.

`TigerHistoricalDividendEvidence` is frozen and contains exactly:

```text
underlying_key: UnderlyingKey
action_type: str
provider_amount: Decimal
currency: str
announced_date: Optional[date]
execute_date: date
record_date: Optional[date]
pay_date: Optional[date]
market: str
exchange: str
retrieved_at: datetime
```

`provider_amount` deliberately has no per-share alias or normalized cash unit.
All dates and provider classification fields are retained without inference.

## Request boundary

The retrieval function accepts an initialized quote client plus exact
keyword-only `underlying_key`, inclusive `begin_date`, inclusive `end_date`,
and `latest_completed_date`. Dates are exact date-only values; begin must not
follow end, the range must not exceed 370 calendar days, and end must not follow
the caller-declared latest completed date.

It makes exactly one call:

```python
quote_client.get_corporate_dividend(
    [underlying_key.symbol],
    "US",
    begin_date.isoformat(),
    end_date.isoformat(),
    timezone="US/Eastern",
)
```

No quote, permission, history-bar, option, rate, account, order, or execution
request is authorized. SDK failures are sanitized.

## Response validation

`None` or an empty table is valid evidence that this bounded response contains
no rows and returns an empty tuple. A nonempty table must expose exactly the
required proof columns:

```text
symbol action_type amount currency announced_date execute_date
record_date pay_date market exchange
```

Every row must use the exact requested symbol, `action_type="DIVIDEND"`,
`market="US"`, the underlying currency, and a nonempty exchange. Amount is
converted only with `Decimal(str(value))` and must be finite and nonnegative.
Provider date strings must be exact ISO `YYYY-MM-DD`; optional dates may be
missing. Execute date must fall inside the inclusive request and not follow
`latest_completed_date`. When supplied, announcement cannot follow execution,
and record/payment cannot precede execution.

Exact duplicate rows fail closed. Distinct distributions on the same execute
date remain distinct evidence rows. Results use deterministic chronological
ordering by all retained fields, independent of provider row order.

Receipt time is captured immediately after the table returns and normalized to
aware UTC. It is retrieval evidence only, not a provider observation timestamp.
No raw table, payload, SDK object, request object, account identifier,
credential, secret, or local credential path is retained.

## Failure precedence

```text
caller identity and bounded dates
-> method availability
-> one request and sanitized failure
-> table shape
-> rows in provider order
-> duplicate detection
-> deterministic immutable tuple
```

Errors never echo provider rows or raw SDK exception text.

## Required tests

Synthetic tests cover exact API arguments, no-data behavior, row mapping,
Decimal preservation, optional dates, chronology, range and identity failures,
malformed tables/scalars, duplicates, deterministic ordering, immutability,
sanitized exceptions, public boundaries, and no import/network/credential side
effects. A local live smoke may print only row counts, field-presence facts, and
bounded dates; it persists no raw payload.

## Explicit exclusions

This unit creates no `DividendObservation`, per-share unit claim,
regular/special classification, forecast or announced status, forward-dividend
schedule, yield, correction history, completeness claim, pricing input,
provider-neutral normalizer, report change, credential change, or trading
capability. Direct normalization requires separate authoritative unit and type
semantics.
