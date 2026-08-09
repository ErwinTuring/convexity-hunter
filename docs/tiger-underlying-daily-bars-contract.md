# Tiger Underlying Daily Bars v0.1

## Status and purpose

This Tier-A contract freezes a bounded Tiger adapter from one caller-specified
US underlying/date range to the existing provider-neutral
`UnderlyingDailyBarObservation`.

Implementation status: complete and independently reviewed.

```text
UnderlyingKey + inclusive begin date + exclusive end date
    -> Tiger unadjusted daily bars (NR)
    -> Tiger forward-adjusted daily bars (BR)
    -> exact timestamp/session pairing
    -> chronological UnderlyingDailyBarObservation tuple
```

The work unit supplies historical underlying observations for the existing
realized-volatility path. It does not retrieve option history or calculate
volatility.

## Public boundary

The direct module `convexity_hunter.providers.tiger` adds exactly:

```text
retrieve_tiger_underlying_daily_bars
```

The module therefore exports exactly seven names. No Tiger name is re-exported
from package roots, and the provider-neutral core does not import Tiger code.

The function accepts an initialized quote client plus exact keyword-only:

```text
underlying_key
begin_date
end_date
latest_completed_session_date
```

Dates are date-only values. Begin is inclusive and end exclusive. Begin must
precede end, the range must not exceed 370 calendar days, and end must not
exceed the day after `latest_completed_session_date`. The caller therefore
cannot request or label an incomplete current session as complete.

## Authorized requests

The adapter makes exactly two read-only SDK calls in order:

1. `get_bars_by_page` with `period="day"`, `right="nr"`;
2. `get_bars_by_page` with identical bounds and `right="br"`.

Both calls use the exact symbol, integer Unix-millisecond begin/end boundaries,
`total=1000`,
`page_size=1000`, `time_interval=0`, no extended-hours session, no fundamentals,
and no security-type override. This range cannot contain 1,000 US daily
sessions, so silent truncation is not accepted.

Each boundary is constructed as midnight for the caller's date in
`America/New_York`, converted as an aware datetime to UTC, then encoded as an
exact integer Unix timestamp in milliseconds. This preserves the declared
inclusive-begin/exclusive-end US-session range independently of Tiger's default
string timezone and across EST/EDT transitions. The work unit does not alter
the global Tiger client timezone.

No permission, permission-grab, quote, option, calendar, dividend, rate,
account, order, or execution request is authorized. SDK failures are sanitized.

## Provider fields and exact pairing

Each DataFrame must expose only the required proof fields:

```text
symbol
time
open
high
low
close
volume
```

`time` must be a positive non-Boolean millisecond Unix timestamp. It is
retained as the provider's daily-bar session marker and converted to a
`session_date` in `America/New_York`; it is not relabeled as an exchange close
timestamp. Every row must use the exact requested symbol, fall inside the date
range, and not follow `latest_completed_session_date`.

Each NR and BR response must contain exactly one row for exactly the same set
of provider timestamps/session dates. Duplicates, missing counterparts,
different timestamps for one session, empty responses, and rows outside the
request fail closed. Results are sorted by session date and timestamp.

## Field mapping

For each paired session:

- NR `open/high/low/close` become canonical unadjusted OHLC;
- NR `volume` becomes exact nonnegative built-in integer volume;
- BR `close` becomes `adjusted_close_price`;
- BR OHLC other than close is validated as finite positive provider material
  but is not retained;
- `is_session_complete` is `True` only because every accepted date is no later
  than the caller's explicit latest completed session; and
- `adjustment_methodology` explicitly states that Tiger `QuoteRight.BR`
  supplied the forward-adjusted close while Tiger `QuoteRight.NR` supplied
  unadjusted OHLC and volume.

Prices use `Decimal(str(value))`, with no binary-float arithmetic or rounding.
OHLC ordering must satisfy the existing core record invariants. NR and BR
volume are not required to match; only NR volume is authoritative for output.

## Provenance and timing

The adapter records aware UTC receipt time immediately after each series
returns and normalization time after pairing. Every output has two source
references:

- `underlying_daily_bars_nr`, origin `EXCHANGE_OBSERVED`;
- `underlying_daily_bars_br`, origin `PROVIDER_CALCULATED`.

Both source observation times retain the exact provider bar timestamp. Their
timestamp methodologies state that it is Tiger's daily session marker, not an
asserted close time. Retrieval times use the separately captured response
receipt times.

Normalization origin is `SYSTEM_COMPOSITE`; flags contain `COMPOSITE_SOURCE`.
Decimal representation conversion is not mislabeled as a unit conversion.
Stable source/record IDs derive from symbol, provider
timestamp, both receipt times, and normalization version. Payload hashes and
raw rows are not retained.

## Returned boundary

The function returns an immutable chronological tuple of exact
`UnderlyingDailyBarObservation` objects. It returns no DataFrame, SDK object,
pagination token, amount/fundamental field, raw payload, credential, account
identifier, or Tiger-specific wrapper.

## Failure precedence

```text
caller inputs and bounded range
-> NR method/request/table/rows
-> BR method/request/table/rows
-> nonempty exact timestamp/session pairing
-> price/volume and OHLC validation
-> provenance construction
-> chronological immutable tuple
```

All errors are stable and sanitized and never echo provider rows or raw SDK
exception text.

## Tests and live verification

Committed tests use synthetic DataFrame-equivalent rows. They cover exact
request arguments/order, range boundaries, timestamp/date conversion across
DST, exact NR/BR pairing, duplicates and gaps, out-of-range/future sessions,
OHLC and volume validation, Decimal preservation, deterministic provenance,
source origins/methodology, chronological output, pandas/numpy compatibility,
malicious accessors/scalars, public boundaries, and no import/network side
effects.

A local smoke check may retrieve a small completed SPY range through the user's
external configuration. It prints only selected normalized dates/counts and
persists no payload.

## Explicit exclusions

This work unit adds no current underlying quote, option quote normalization,
option bars, dividend, rate, realized-volatility calculation, historical IV,
Greeks, completeness policy beyond exact returned-series pairing, provider
routing, caching, monitoring, scheduling, reporting, orders, or execution.
