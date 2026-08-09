# U.S. Treasury Daily Par-Yield Curve v0.1

## Status and purpose

This Tier-A contract freezes the bounded external USD rate-provider work unit
anticipated by ADR-008. U.S. Treasury direct is the MVP primary provider for
the USD rate category only. Tiger OpenAPI remains the MVP primary provider for
the option and underlying market-data universe; this unit adds no provider
routing, fallback, arbitration, or quote-provider substitution.

```text
exact Treasury effective date
    -> official year-specific Daily Treasury Par Yield Curve CSV
    -> exact effective-date row
    -> six provider-native short-tenor par yields
    -> six existing RateCurvePointObservation records
```

The source is the U.S. Treasury's nominal Daily Treasury Par Yield Curve. Its
rates are constant-maturity par yields derived from indicative bid-side
Treasury quotations. They are bond-equivalent yields under a semiannual
interest convention, not zero/spot rates, discount factors, OIS rates, SOFR
term rates, swap rates, or continuously compounded model rates. This adapter
preserves that source meaning and performs no pricing-rate transformation.

## Public boundary

The new direct module `convexity_hunter.providers.us_treasury` exports exactly:

```text
retrieve_us_treasury_daily_par_yield_curve
```

Nothing is re-exported from either package root. The provider-neutral core and
Tiger module remain unchanged.

The function accepts one exact keyword-only `effective_date`, whose exact type
must be `datetime.date`, and returns an immutable tuple of exactly six existing
`RateCurvePointObservation` records in ascending normalized tenor order. The
date is the Treasury curve's effective date, not an equity exchange session
claim and not a request for the nearest available date.

## Authorized request

The adapter performs exactly one read-only HTTPS GET to the official
year-specific CSV endpoint:

```text
https://home.treasury.gov/resource-center/data-chart-center/interest-rates/
daily-treasury-rates.csv/<year>/all
    ?_format=csv
    &field_tdr_date_value=<year>
    &page=
    &type=daily_treasury_yield_curve
```

The request uses the exact effective-date year, a fixed application user agent,
and a bounded timeout. Redirected or provider-generated URLs are not accepted
from the caller. The response body is capped at one MiB and decoded as UTF-8
with an optional UTF-8 BOM. Network, HTTP, body-size, encoding, and CSV failures
are converted to stable sanitized errors that contain no response body or raw
exception text.

No API key, credential, account, Tiger client, local configuration, quote,
option, underlying, dividend, order, or execution request is authorized.

## Exact row and schema boundary

The CSV header must contain unique exact fields:

```text
Date
1 Mo
1.5 Month
2 Mo
3 Mo
4 Mo
6 Mo
```

Additional provider columns are ignored. Exactly one row must have `Date`
equal to the requested date in exact zero-padded `MM/DD/YYYY` form. The adapter
does not silently choose a previous or later business day. Missing and
duplicate exact rows fail closed. Malformed values in unrelated date rows do
not preempt exact-row selection.

Every selected rate must be a nonempty finite decimal string. `N/A`, blank,
Boolean-like, float-derived, infinite, and NaN material fails closed. Negative
rates are valid source values. The complete six-point row is required; the
adapter does not return a partial curve, fill a missing tenor, or use a nearby
date.

## Tenor and unit normalization

The exact provider-label mapping is:

| Treasury label | `tenor_days` |
| --- | ---: |
| `1 Mo` | 30 |
| `1.5 Month` | 45 |
| `2 Mo` | 60 |
| `3 Mo` | 90 |
| `4 Mo` | 120 |
| `6 Mo` | 180 |

These integers are a declared Convexity Hunter normalization convention for
the provider's named constant maturities. They do not assert an instrument
with that exact remaining calendar-day maturity. The provider label remains
in source identity and normalization methodology.

Each Treasury percentage is parsed directly as `Decimal` and divided by exact
`Decimal("100")`; for example, `3.79` becomes `Decimal("0.0379")`. No binary
float, rounding, interpolation, extrapolation, bootstrapping, curve fitting,
or par-to-zero conversion is allowed.

Every returned record has exact normalized declarations:

```text
curve_id = USD-US-TREASURY-DAILY-PAR-YIELD
currency = USD
compounding_convention = Bond-equivalent yield; simple annualized with semiannual interest convention
day_count_convention = Actual days; 365- or 366-day year
effective_date = requested exact Treasury date
```

## Provenance and time semantics

The official methodology states that curve inputs are indicative bid-side
quotations obtained at or near 3:30 PM Eastern Time each trading day, while the
CSV supplies only the effective date. The adapter therefore assigns 3:30 PM in
`America/New_York` on the effective date as a nominal observation timestamp,
converts it to aware UTC, and explicitly marks the normalization with
`TIMESTAMP_ASSIGNED`. It never claims the assigned value is an exact trade,
quote, publication, or retrieval timestamp.

Each record has one source reference with:

- provider `U.S. Department of the Treasury`;
- dataset `Daily Treasury Par Yield Curve Rates`;
- the fixed official year-specific CSV request URI;
- the effective date and exact provider tenor label in provider record
  identity;
- origin `PROVIDER_CALCULATED`;
- source flags `INDICATIVE` and `NON_FIRM`;
- provider timezone `America/New_York`;
- exact post-response aware-UTC retrieval time; and
- SHA-256 of the complete bounded CSV response.

Normalized records have origin `PROVIDER_CALCULATED`, quality flags
`UNIT_CONVERTED` and `TIMESTAMP_ASSIGNED`, and a methodology that discloses the
percent-to-decimal conversion, fixed tenor-day mapping, provider-native par
semantics, and assigned-time rule. Stable source and record IDs bind the
normalization version, response digest, effective date, and provider tenor.
No raw payload is retained or returned.

This unit does not itself assess freshness. Existing explicit
`MarketDataFreshnessPolicy`, `FreshnessContext`, and the rate-category
`maximum_rate_age_seconds` remain the only freshness authority. The assigned
timestamp flag remains available to any policy that disallows assigned times.

## Failure precedence

```text
exact caller date
-> fixed request construction and bounded retrieval
-> body size, UTF-8, and CSV header
-> exact date-row cardinality
-> six exact provider rate values
-> deterministic normalization and provenance
-> immutable ordered tuple
```

Errors never echo response rows, response bodies, provider exception text, or
environment material.

## Required tests and live verification

Committed tests use a synthetic transport response containing only public,
non-secret Treasury-shaped CSV material. They cover exact request URL, timeout,
user agent, one-call behavior, size/encoding/header failures, exact-date
selection, missing and duplicate rows, unrelated malformed rows, all six tenor
mappings, Decimal percent conversion including negative rates, incomplete and
non-finite rates, deterministic ordering, provenance, digest, assigned EST and
EDT timestamps, immutable core records, sanitized exceptions, exact exports,
and no import-time network or credential access.

Literal expected values independently verify normalization; tests must not
derive expected tenors or rates with the implementation helpers under test.
A local smoke check may retrieve one known public effective date and print only
the effective date, ordered tenors, and normalized public rates. It persists no
payload.

## Explicit exclusions

This work unit adds no nearest-date selection, business calendar, cache,
monitor, scheduler, fallback provider, FRED key, rate interpolation,
extrapolation, bootstrap, discount factor, zero/OIS/SOFR curve, option-pricing
rate, IV or Greeks reconstruction, report change, downstream orchestration,
credential handling, Tiger modification, order, or execution capability.
