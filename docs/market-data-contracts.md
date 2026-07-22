# Provider-Neutral Market-Data Contracts v0.1

> **DESIGN SPECIFICATION ONLY — NO LIVE PROVIDER OR NETWORK INTEGRATION IS AUTHORIZED**

No market-data provider has been selected. All examples in this document use synthetic values. This specification defines interfaces, semantics, lineage, and validation boundaries only. No live or delayed market data may be connected until these contracts are implemented and tested with fixed synthetic fixtures.

These contracts establish whether data is structurally usable and auditable. They do not establish whether an option is economically attractive, and they are not investment advice.

## 1. Contract purpose

This specification defines provider-neutral, auditable contracts for bringing external market observations into Convexity Hunter without coupling research records to a vendor schema. It separates source material, normalization, calculations, and decisions so every reported value can be traced and reviewed.

## 2. Architectural layers

The market-data pipeline has five strictly separate layers.

### Layer A — Raw provider material

Raw material contains provider-native payloads and fields, such as a JSON response, CSV row, vendor contract symbol, provider-specific Greek scale, vendor timestamp, or provider status code.

Rules:

- A future provider adapter owns raw material.
- Raw meaning must be preserved; fields must not be silently reinterpreted.
- Raw payloads never pass directly into screening.
- Raw payloads are never rendered directly in user-facing Markdown.
- Depending on provider licensing, raw material may be retained as exact payload text, an immutable file reference, or a cryptographic payload hash.
- API keys, secrets, cookies, tokens, and authentication headers must never be stored in records.

### Layer B — Source references

Provider-neutral source references point back to raw material. They retain provider, dataset, record or request identifiers, source symbol, observation and retrieval times, source URI when available, payload hash when available, delay disclosure, timestamp methodology, revision information, and source-quality conditions.

### Layer C — Normalized external observations

Typed, provider-neutral records express market and reference data in canonical units. Examples include an underlying quote, option contract reference, option quote, option volume, option open interest, provider-calculated IV or Greeks, underlying daily bar, rate-curve point, and dividend input.

These records remain externally sourced observations, provider-calculated values, or explicitly declared system composites. Their `NormalizationMetadata.record_origin` describes that normalized-record origin independently of each underlying `SourceReference.origin`. They are not Convexity Hunter research conclusions or screening decisions.

### Layer D — Calculated research records

Deterministic calculations transform normalized observations into existing research records, including:

- `VolatilityEnvironment`;
- `TailPricingSlice`;
- `StructureCosts`;
- `StructureLiquidity`;
- `ScenarioResult`;
- `ClassifiedEvidence` items representing observed facts or calculated metrics.

### Layer E — Decisions and presentation

This layer contains:

- `CandidateResearchRecord`;
- `ScreeningDecision`;
- Chinese and English reports.

Screening never consumes raw provider payloads. Reporting never calculates market data. An LLM never supplies numerical market data. Narrative evidence cannot replace missing normalized records.

```text
Provider payload
    ↓ adapter parsing
Source references
    ↓ normalization
Normalized external observations
    ↓ deterministic calculation
Research records
    ↓ deterministic screening
ScreeningDecision
    ↓ deterministic rendering
Bilingual report
```

This separation must allow providers to change without changing `CandidateResearchRecord`, `ScreeningPolicy`, `ScreeningDecision`, screening thresholds, or report semantics.

## 3. Planned module boundary

The future core module is:

```text
src/convexity_hunter/market_data.py
```

It will contain provider-neutral records only. It is not created by this documentation task.

Provider adapters may eventually live outside the core contract module, for example:

```text
src/convexity_hunter/providers/
```

That directory is also not created by this task. The core contract module must not import a vendor SDK, make HTTP requests, read API credentials, contain provider-specific field names, or depend on the scanner or report renderer. Future adapters may depend on the core contracts; the core contracts must never depend on adapters.

## 4. Common source-reference contract

The planned immutable `SourceReference` record has these fields:

```text
source_id: str
provider_name: str
dataset_name: str
provider_record_id: Optional[str]
provider_request_id: Optional[str]
source_symbol: Optional[str]
source_uri: Optional[str]
observed_at: datetime
retrieved_at: datetime
provider_timezone: Optional[str]
timestamp_methodology: str
origin: DataOrigin
is_delayed: bool
declared_delay_seconds: Optional[int]
payload_sha256: Optional[str]
revision_number: Optional[int]
provider_correction_id: Optional[str]
quality_flags: Tuple[SourceQualityFlag, ...]
```

### 4.1 DataOrigin

The future enum values are:

```text
exchange_observed
provider_calculated
provider_reference
system_composite
```

- `exchange_observed`: quote, trade, volume, or other exchange-originated observation supplied by a provider.
- `provider_calculated`: IV, Greeks, theoretical values, or other provider calculations.
- `provider_reference`: contract terms, symbols, multipliers, calendars, or corporate-action reference data.
- `system_composite`: a normalized observation deliberately assembled from more than one source.

`SourceReference.origin` may use only `exchange_observed`, `provider_calculated`, or `provider_reference`. A source reference identifies provider- or exchange-originated material and must never use `system_composite`. Composite origin belongs to the normalized record through `NormalizationMetadata.record_origin`.

### 4.2 SourceQualityFlag

The future source-quality values, in declaration order, are:

```text
delayed
indicative
non_firm
locked
halted
after_hours
corrected
provider_estimated
partial
unknown_condition
```

Quality flags describe source conditions. A locked quote is a source-market condition distinct from `non_firm`. `stale` is not a source flag because staleness depends on an explicit evaluation time and freshness policy.

`SourceReference` validation requires:

- `source_id`, `provider_name`, `dataset_name`, and `timestamp_methodology` are non-empty after trimming;
- every supplied optional string is non-empty after trimming;
- when `is_delayed=True`, `declared_delay_seconds` is a positive integer and the `delayed` quality flag is present;
- when `is_delayed=False`, `declared_delay_seconds` is `None` and the `delayed` quality flag is absent;
- a supplied `payload_sha256` contains exactly 64 lowercase hexadecimal characters;
- a supplied `revision_number` is a nonnegative integer;
- a supplied `provider_correction_id` is trimmed and non-empty, identifies a provider-declared correction, restatement, cancel/correct message, or equivalent revision event, and contains no credentials or secret query parameters;
- `provider_correction_id` is distinct from `provider_record_id` and `provider_request_id`;
- the `corrected` flag requires either `revision_number > 0` or a supplied `provider_correction_id`;
- a positive revision number or supplied correction ID requires the `corrected` flag;
- a correction never overwrites the earlier source reference or normalized record;
- repeated retrieval of an unchanged provider record never creates a correction ID automatically;
- quality flags contain no duplicates and are returned in the enum declaration order shown above;
- callers never rely on set ordering or alphabetical sorting.

## 5. Timestamp and session rules

### 5.1 Time-zone awareness

Every `datetime` must include timezone information, must be normalized to UTC in a core contract, and must reject naive values.

### 5.2 Observation time

`observed_at` means:

> The time at which the represented market or reference value was valid according to the source or the declared timestamp methodology.

It is not HTTP response time, local file modification time, retrieval time, or report-generation time.

### 5.3 Retrieval time

`retrieved_at` means:

> The time at which the adapter received or read the source material.

The invariant is:

```text
retrieved_at >= observed_at
```

A historical observation may be retrieved much later than it was observed.

### 5.4 Normalization and calculation time

Future normalized records include `normalized_at`; future calculation lineage includes `calculated_at`.

```text
effective_observed_at <= normalized_at
normalized_at >= latest source retrieved_at
calculated_at >= latest input normalized_at
```

### 5.5 Effective observation time

`effective_observed_at` means:

> The provider-neutral timestamp at which the normalized value is declared to represent the market or reference state.

It is not retrieval time, normalization time, report-generation time, or the evaluation time used by a freshness policy.

For a normalized record with exactly one source reference:

```text
effective_observed_at == source_reference.observed_at
```

An adapter must not silently shift or replace the source observation time.

For a normalized record with multiple source references, `normalization_methodology` states how the effective time was selected. The timestamp is timezone-aware UTC, is not earlier than the earliest source `observed_at`, and is not later than the latest source `observed_at`. The selected time must not conceal individual source timestamps or make an old component appear newer than it is. Single-record freshness inspects every source observation time. For 3C.3 cross-binding spans, every source is inspected only for the temporal-participant selected records defined in Section 13.8.

Single-record freshness assessment uses the normalized record's
`effective_observed_at` and complete source-reference observation-time range.
Milestone 3C.3 binding-set temporal coherence applies the configured
cross-record skew rule only to the exact temporal-participant types defined in
Section 13.8. Date-oriented fields are never converted to synthetic datetimes.

### 5.6 Market-session date

Records dependent on a US trading session also contain `session_date`.

- `session_date` is the exchange-local trading date.
- It must not be derived from a UTC date without an exchange-calendar rule.
- Retrieval date never substitutes for session date.
- `CandidateResearchRecord.as_of_date` must ultimately come from the declared market session, not retrieval time.

### 5.7 Sources without exact timestamps

An adapter must not silently invent an exact observation time. When a source supplies only a session date, a timestamp may be assigned only under a declared methodology. `timestamp_methodology` must explain the assignment, the observation must carry an appropriate quality flag, and the record may be ineligible for intraday screening.

### 5.8 Effective dates and observation times are distinct

- `effective_observed_at` is the timestamp of the normalized observation.
- `session_date` is the exchange-local trading date associated with a market observation.
- `effective_date` is the date on which a rate or reference value applies.
- `ex_date` is a dividend entitlement date.
- `retrieved_at` is source acquisition time.
- `normalized_at` is normalization time.
- Future `calculated_at` is deterministic calculation time.
- Future `evaluation_at` is freshness-assessment time.

None of these fields may silently substitute for another.

## 6. Normalization metadata

The planned immutable `NormalizationMetadata` record has these fields:

```text
record_id: str
source_references: Tuple[SourceReference, ...]
effective_observed_at: datetime
normalized_at: datetime
record_origin: DataOrigin
normalization_methodology: str
unit_convention: str
normalization_version: str
quality_flags: Tuple[NormalizationQualityFlag, ...]
```

Requirements:

- `record_id` is non-empty after trimming.
- At least one source reference is required.
- Source IDs are unique and source references are normalized into ascending `source_id` order.
- `effective_observed_at` is timezone-aware UTC and follows the single-source or multi-source rules in Section 5.5.
- Normalization methodology, unit convention, and normalization version are non-empty after trimming.
- An approved normalization version is immutable once used.
- `normalized_at` is timezone-aware UTC, is not earlier than `effective_observed_at`, and must not precede any source retrieval time.
- Normalization quality flags contain no duplicates and are returned in the enum declaration order shown below.

Future normalization-quality values, in declaration order, are:

```text
unit_converted
symbol_mapped
contract_adjusted
composite_source
interpolated
timestamp_assigned
incomplete
```

Interpolation must never be silent. An incomplete record may be retained for audit but may be ineligible for calculation. Deterministic source ordering means ascending normalized `source_id`, not provider order.

All four `DataOrigin` values may be used as `record_origin`. `system_composite` is valid only for a normalized record and requires at least two source references, the `composite_source` quality flag, and explicit source-priority and conflict-resolution methodology. It must expose every underlying provider source. A single-source normalized record must not be labeled `system_composite`.

## 7. Canonical identifiers

### 7.1 UnderlyingKey

The planned immutable `UnderlyingKey` fields are:

```text
symbol: str
listing_mic: Optional[str]
security_type: UnderlyingSecurityType
currency: str
```

The future `UnderlyingSecurityType` values are exactly:

```text
equity
etf
```

Symbol and currency are trimmed and uppercase, and MVP currency must be `USD`. `listing_mic`, when present, is trimmed and uppercase. Symbol alone must never silently identify another listing or share class. Provider-native symbols remain in `SourceReference.source_symbol`; mapping a provider symbol to an `UnderlyingKey` requires the `symbol_mapped` normalization flag. Listing identity is distinct from an option quote venue. Existing downstream research records may receive `UnderlyingKey.symbol` only through a later explicit transformation.

### 7.2 OptionContractKey

The planned immutable `OptionContractKey` fields are:

```text
underlying_key: UnderlyingKey
expiration: date
option_type: str
strike: Decimal
contract_multiplier: int
currency: str
deliverable_id: Optional[str]
```

Rules:

- `option_type` is `call` or `put`.
- Strike is a positive finite `Decimal`.
- Contract multiplier is a positive integer.
- Currency is uppercase ISO-style text.
- Currency equals `underlying_key.currency` in MVP v0.1.
- Adjusted and nonstandard contracts must not be merged with standard contracts.
- Nonstandard or adjusted deliverables require `deliverable_id`; standard contracts use `deliverable_id=None`.
- MVP scope remains US-listed equities and ETFs, but no contract silently assumes a multiplier of 100.

The canonical key identifies the economic option series. An execution or quote venue is not part of that identity because the same contract may have observations from multiple venues. Venue identity belongs on quote observations or source references. Provider-native contract symbols are retained in `SourceReference.source_symbol`, not in `OptionContractKey` or `OptionContractReference`.

## 8. Canonical unit conventions

| Value | Canonical unit |
| --- | --- |
| Underlying bid, ask, last, and bar prices | USD per underlying share |
| Option bid and ask premium | USD per underlying unit, before contract multiplier |
| Strike | USD per underlying share |
| Underlying quote size | Shares |
| Option quote size | Contracts |
| Underlying daily-bar volume | Shares |
| Daily option volume | Contracts |
| Open interest | Contracts |
| Implied volatility | Annualized decimal ratio; `0.20 = 20%` |
| Delta | Dimensionless change per underlying unit |
| Gamma | Option-value change per USD² of underlying movement, per underlying unit |
| Theta | USD of option-value change per underlying unit per declared day basis |
| Vega | USD of option-value change per underlying unit for a `1.00` absolute IV change |
| Interest rate | Annualized decimal ratio |
| Cash dividend | USD per underlying share |
| Time duration | Integer seconds or integer calendar days, as explicitly named |
| Percentile | Decimal unit interval; `0.40 = 40%` |

Option quote premium is not total contract value. Total contract premium is normalized premium multiplied by contract multiplier; total-position values additionally multiply by quantity. Provider-per-contract Greeks must be converted to the declared normalized unit, while provider-per-share Greeks must not be multiplied twice. Vega quoted per one volatility point must be converted to the canonical `1.00` absolute-IV convention. Theta must declare a calendar-day, trading-day, or provider-specific basis. A Greek with unknown scaling is unusable for structure-level calculations.

These conventions do not change the existing total-position `StructureCosts` units. The calculation layer performs the explicit quantity and multiplier scaling required by that record.

## Numeric representation decision

Provider-neutral market-data contracts v0.1 use:

- `decimal.Decimal` for externally sourced non-integer numeric values;
- `int` for integer counts and durations;
- `datetime.date` for dates;
- timezone-aware UTC `datetime.datetime` for timestamps.

Adapters construct `Decimal` values from the provider's textual representation whenever available and must not construct audit-critical decimals directly from binary floats. Boolean values are never accepted as numbers. NaN and infinity are rejected. Negative zero is normalized to ordinary zero. Contract records preserve the precision of the normalized source rather than applying arbitrary rounding.

`Decimal` applies to prices, premiums, strikes, implied volatility, Greeks, rates, dividend amounts, dividend yields, percentiles, and other external decimal ratios. `int` applies to volume, open interest, quote sizes, multipliers, tenor days, delay seconds, and revision numbers.

Existing Convexity Hunter research records currently use `float`. Conversion from `Decimal` to `float` occurs only in a deterministic calculation or transformation layer, never inside a provider adapter. The conversion methodology and affected input record IDs must be retained in `CalculationLineage`. Identity-bearing values such as option strike must not depend on binary-float equality.

## 9. Planned normalized observation records

All records below are planned immutable contracts and are not implemented by this specification.

The future `QuoteScope` enum values are exactly:

```text
consolidated
venue_specific
provider_composite
unknown
```

`venue_specific` requires `venue_mic`. Consolidated and provider-composite quotes must not claim one execution venue. `unknown` may be retained for audit but may be ineligible for current screening. Consolidated, venue-specific, and provider-composite observations must never be mixed silently. Quote aggregation methodology remains in `NormalizationMetadata`. Quote scope is distinct from `MarketPhase` and does not belong in `OptionContractKey`.

### 9.1 UnderlyingQuoteObservation

```text
underlying_key: UnderlyingKey
session_date
bid_price
ask_price
last_price: Optional[Decimal]
bid_size: Optional[int]
ask_size: Optional[int]
market_phase
quote_scope: QuoteScope
venue_mic: Optional[str]
metadata: NormalizationMetadata
```

Prices are finite `Decimal` values. Bid is nonnegative; ask is positive and not below bid; sizes are nonnegative share counts; last price, when present, is positive. Bid/ask equality is valid and carries the `locked` source flag. Crossed quotes are structurally invalid for current screening unless a declared correction methodology resolves them. Last price never substitutes for bid or ask.

### 9.2 OptionContractReference

```text
contract_key: OptionContractKey
listing_date: Optional[date]
last_trade_date: Optional[date]
exercise_style: Optional[str]
settlement_type: Optional[str]
metadata
```

This is reference data, not a quote. Provider-native contract symbols are retained through `SourceReference.source_symbol`. One reference record may cite multiple source references through its normalization metadata.

### 9.3 OptionQuoteObservation

```text
contract_key
session_date
bid_premium
ask_premium
bid_size: Optional[int]
ask_size: Optional[int]
market_phase
quote_scope: QuoteScope
venue_mic: Optional[str]
metadata
```

Premiums are finite `Decimal` values. Bid may be zero; ask is positive and at least bid; quote sizes are nonnegative contract counts. Bid/ask equality is valid and carries the `locked` source flag. Crossed quotes are structurally invalid for current screening. Last price is not part of this record and never substitutes for bid or ask. Premiums are USD per underlying unit. Normalized quote time is `metadata.effective_observed_at`; every underlying source observation time remains available through `metadata.source_references`.

### 9.4 OptionVolumeObservation

```text
contract_key
session_date
cumulative_volume
is_session_complete: bool
metadata
```

Volume is a nonnegative integer number of contracts. Intraday cumulative volume uses `is_session_complete=False`; completed daily volume uses `is_session_complete=True`. A false value must never be described as completed daily volume. The normalized effective observation time and complete source observation-time range remain in metadata.

### 9.5 OptionOpenInterestObservation

```text
contract_key
open_interest_session_date
open_interest
metadata
```

Open interest is a nonnegative integer and normally belongs to a completed session. It does not inherit an option quote timestamp; its applicable session date remains explicit.

### 9.6 OptionImpliedVolatilityObservation

```text
contract_key
session_date
implied_volatility
model_name
model_version: Optional[str]
rate_input_description
dividend_input_description
metadata
```

IV is a positive finite `Decimal` stored as an annualized decimal ratio. It has `provider_calculated` origin unless a future Convexity Hunter calculation module produces it. Model and input descriptions are mandatory. IV must not be labeled exchange-observed.

### 9.7 OptionGreeksObservation

```text
contract_key
session_date
delta: Optional[Decimal]
gamma: Optional[Decimal]
theta: Optional[Decimal]
vega: Optional[Decimal]
theta_day_basis: Optional[str]
model_name
model_version: Optional[str]
rate_input_description
dividend_input_description
metadata
```

At least one Greek is present and every present Greek is a finite `Decimal`. When Theta is present, `theta_day_basis` is mandatory; when Theta is absent, it must be `None`. `model_name`, `rate_input_description`, and `dividend_input_description` remain mandatory for provider-calculated Greeks; `model_version` remains optional. Scaling follows Section 8. Unknown provider scaling makes only the affected Greek unusable, and the record must not claim that Greek was normalized successfully.

### 9.8 UnderlyingDailyBarObservation

```text
underlying_key: UnderlyingKey
session_date
open_price
high_price
low_price
close_price
adjusted_close_price: Optional[Decimal]
volume
is_session_complete
adjustment_methodology: Optional[str]
metadata
```

Raw OHLC prices are positive finite `Decimal` values and must satisfy:

```text
low_price <= min(open_price, close_price)
high_price >= max(open_price, close_price)
high_price >= low_price
```

Raw consistency checks do not compare `adjusted_close_price` with daily high or low. When supplied, adjusted close is a positive finite `Decimal`, `adjustment_methodology` is mandatory, and that methodology states whether it covers splits, cash dividends, or both. When adjusted close is absent, adjustment methodology must be `None`. Adjusted close remains a separate series from raw OHLC, and raw and adjusted returns must not be mixed in one historical calculation. Volume is a nonnegative integer share count. Historical realized-volatility calculations use completed sessions only.

### 9.9 RateCurvePointObservation

```text
curve_id
currency
tenor_days
annualized_rate
compounding_convention
day_count_convention
effective_date
metadata
```

The annualized rate is a finite `Decimal` and may be negative; tenor is a positive integer. Compounding and day-count conventions are mandatory. Rate data may be published or effective on dates that are not equity-market session dates, so `effective_date` is not called `session_date`. Observation and retrieval timestamps remain in metadata. Interpolation is a later calculation step and must disclose methodology.

### 9.10 DividendObservation

The future `DividendStatus` enum values, in declaration order, are exactly:

```text
forecast
announced
historical
```

```text
underlying_key: UnderlyingKey
dividend_type
ex_date
payment_date: Optional[date]
cash_amount: Optional[Decimal]
annualized_yield: Optional[Decimal]
currency
status: DividendStatus
metadata
```

At least one of cash amount or annualized yield is present. Both are `Decimal` when supplied. Cash amount is nonnegative; annualized yield is nonnegative and finite. Currency equals `underlying_key.currency`.

- `forecast` means an estimated future dividend not yet formally announced.
- `announced` means a formally announced future dividend.
- `historical` means a completed historical dividend observation.

Forecast inputs carry `provider_calculated` origin unless Convexity Hunter later calculates them. Announced and historical observations normally carry `provider_reference` origin. Status is never inferred from whether `ex_date` is before or after the local machine date. Scenario-pricing methodology discloses which statuses are eligible, and historical and forecast dividends are never mixed silently. Provider-specific status strings do not enter the core record.

## 10. Market phase

The future `MarketPhase` values are:

```text
pre_market
regular
post_market
closed
unknown
```

Regular-session and after-hours quotes must not be mixed silently. A freshness policy may reject `unknown`. The same value may have different eligibility by phase. Phase must not be inferred from local machine time.

## 11. Deterministic freshness contracts

> **NO PRODUCTION DEFAULT THRESHOLDS ARE DEFINED.** Every assessment receives an explicit policy and context. Freshness never reads the wall clock or mutates normalized records. Stale, unknown, and ineligible records remain auditable, but only a `fresh` result is eligible to serve as current evidence. Freshness is separate from screening attractiveness. Policy identity and version are supplied and preserved, and provider selection remains deferred.

### 11.1 MarketDataCategory

The future string enum `MarketDataCategory` has this exact declaration order and values:

```text
quote
analytics
activity
contract_reference
historical_bar
rate
dividend
```

Record categories are fixed by record type:

| Category | Record types |
| --- | --- |
| `quote` | `UnderlyingQuoteObservation`, `OptionQuoteObservation` |
| `analytics` | `OptionImpliedVolatilityObservation`, `OptionGreeksObservation` |
| `activity` | `OptionVolumeObservation`, `OptionOpenInterestObservation` |
| `contract_reference` | `OptionContractReference` |
| `historical_bar` | `UnderlyingDailyBarObservation` |
| `rate` | `RateCurvePointObservation` |
| `dividend` | `DividendObservation` |

Callers cannot override a record's category. An unsupported record type raises `TypeError`; unsupported types do not produce an `unknown` assessment.

### 11.2 MarketDataFreshnessPolicy

The future immutable record has these exact fields and order:

```text
MarketDataFreshnessPolicy
    policy_id: str
    policy_version: str
    maximum_quote_age_seconds: int
    maximum_analytics_age_seconds: int
    maximum_activity_age_seconds: int
    maximum_reference_age_seconds: int
    maximum_rate_age_seconds: int
    maximum_dividend_age_seconds: int
    maximum_retrieval_lag_seconds: int
    maximum_source_observation_span_seconds: int
    maximum_cross_record_skew_seconds: int
    maximum_open_interest_session_date_gap_days: int
    maximum_historical_bar_session_date_gap_days: int
    allow_delayed_data: bool
    allow_indicative_data: bool
    allow_non_firm_data: bool
    allow_partial_data: bool
    allow_assigned_timestamps: bool
    require_regular_session_quotes: bool
    require_completed_historical_sessions: bool
```

`policy_id` and `policy_version` are trimmed, non-empty strings. Every threshold is an actual non-Boolean integer, is zero or greater, and is required. Every policy switch is an actual Boolean. v0.1 creates no process-global policy registry and defines no built-in production default policy. Policies with different semantics must use a different immutable identity or version. Tests construct explicit synthetic policies.

| Category | Applied age threshold |
| --- | --- |
| `quote` | `maximum_quote_age_seconds` |
| `analytics` | `maximum_analytics_age_seconds` |
| `activity` | `maximum_activity_age_seconds` |
| `contract_reference` | `maximum_reference_age_seconds` |
| `historical_bar` | Calendar-day session-date-gap policy rather than an age-in-seconds field |
| `rate` | `maximum_rate_age_seconds` |
| `dividend` | `maximum_dividend_age_seconds` |

`maximum_cross_record_skew_seconds` is retained for Milestone 3C.3 binding-set
temporal coherence. Single-record freshness assessment does not apply it.
Section 13.8 applies it only to selected records in the exact temporal-
participation matrix defined there. `maximum_source_observation_span_seconds`
is the within-record multi-source limit and is applied in 3B.1.

### 11.3 FreshnessContext

The future immutable record is:

```text
FreshnessContext
    evaluation_at: datetime
    latest_completed_session_date: date
```

`evaluation_at` is timezone-aware and stored as UTC; naive values are rejected. `latest_completed_session_date` is a date without time, and datetime values are rejected. The context is supplied explicitly. The system never calls `now()`, `today()`, or an exchange-calendar service. The caller supplies the correct exchange-local completed-session date, and context values are not inferred from normalized record timestamps.

### 11.4 FreshnessStatus

The exact enum order is:

```text
FreshnessStatus
    fresh
    stale
    ineligible
    unknown
```

- `fresh`: all applicable time and eligibility rules pass.
- `stale`: structurally usable but outside one or more allowed age or calendar-day session-date-gap limits.
- `ineligible`: a deterministic policy or chronology rule prohibits current use.
- `unknown`: the record contains an explicit unknown quote phase or quote scope, so current eligibility cannot be established responsibly.

`unknown` is not used for unsupported Python types; those raise `TypeError`. `stale`, `ineligible`, and `unknown` are all unsuitable for current screening evidence. Status does not delete or mutate the record.

### 11.5 FreshnessReasonCode

The future string enum has this exact canonical declaration order:

```text
record_normalized_after_evaluation
source_retrieved_after_evaluation
source_observed_after_evaluation
normalization_incomplete
assigned_timestamp_not_allowed
delayed_data_not_allowed
indicative_data_not_allowed
non_firm_data_not_allowed
partial_data_not_allowed
halted_source
source_observation_span_exceeded
non_regular_session_quote
historical_session_incomplete
session_date_after_latest_completed_session
unknown_market_phase
unknown_quote_scope
effective_age_exceeded
oldest_source_age_exceeded
retrieval_lag_exceeded
open_interest_session_date_gap_exceeded
historical_bar_session_date_gap_exceeded
fresh_within_policy
```

Ineligible reasons are the first fourteen values, through `session_date_after_latest_completed_session`. Unknown reasons are `unknown_market_phase` and `unknown_quote_scope`. Stale reasons are the five values from `effective_age_exceeded` through `historical_bar_session_date_gap_exceeded`. The fresh reason is `fresh_within_policy`.

Reasons contain no duplicates, are always returned in enum declaration order, and are never sorted alphabetically. All detected reasons remain visible even when a higher-precedence status wins. `fresh_within_policy` appears only when no other reason applies, and every assessment contains at least one reason.

### 11.6 Deterministic status precedence

The exact precedence is:

```text
ineligible > unknown > stale > fresh
```

The evaluator:

1. evaluates every applicable rule;
2. collects every reason;
3. normalizes reasons into canonical enum order;
4. selects `ineligible` if any ineligible reason exists;
5. otherwise selects `unknown` if any unknown reason exists;
6. otherwise selects `stale` if any stale reason exists;
7. otherwise selects `fresh`, with `fresh_within_policy` as the only reason.

Delayed and stale data is `ineligible` while retaining both reasons. An unknown quote scope and stale quote is `unknown` while retaining the stale reason. A record cannot be `fresh` while retaining another reason.

### 11.7 Exact freshness metrics

All second-based metrics are finite `Decimal` values, allowing exact microsecond representation without rounding.

```text
effective_age_seconds =
    evaluation_at - metadata.effective_observed_at

oldest_source_age_seconds =
    evaluation_at - min(source.observed_at)

maximum_retrieval_lag_seconds_observed =
    max(source.retrieved_at - source.observed_at)

source_observation_span_seconds =
    max(source.observed_at) - min(source.observed_at)
```

Oldest-source age represents the age of the oldest source component. For one source, source observation span is zero.

The open-interest session date gap is:

```text
latest_completed_session_date - open_interest_session_date
```

The historical-bar session date gap is:

```text
latest_completed_session_date - historical_bar.session_date
```

The result is an integer number of calendar days, not a trading-session count. Weekends and holidays are not removed, and no exchange calendar is called. A negative date gap exposes a future-session chronology problem and is never clamped to zero. An incomplete historical bar uses `session_date_gap_days=None`; an open-interest observation always exposes its calculated gap, including a negative value when its date follows the latest completed session. A configured maximum is inclusive: `observed gap <= configured maximum` passes.

> **Production policy warning:** Calendar-day gap thresholds must account for weekends and holidays until a separately reviewed trading-session-count convention exists.

Second-based calculations use exact timedeltas before conversion to Decimal seconds and do not truncate or round microseconds. The implementation derives exact Decimal seconds from the timedelta's integer `days`, `seconds`, and `microseconds` components; binary-float `total_seconds()` is not the audit-critical source. Negative ages expose future chronology problems and are never clamped to zero. No calculation uses local machine time.

### 11.8 Single-record freshness assessment

The future pure function is:

```text
assess_market_data_freshness(
    record,
    policy: MarketDataFreshnessPolicy,
    context: FreshnessContext,
) -> FreshnessAssessment
```

It accepts only the ten normalized Milestone 3A record types, grouped by their fixed categories:

```text
quote:
- UnderlyingQuoteObservation
- OptionQuoteObservation

analytics:
- OptionImpliedVolatilityObservation
- OptionGreeksObservation

activity:
- OptionVolumeObservation
- OptionOpenInterestObservation

contract_reference:
- OptionContractReference

historical_bar:
- UnderlyingDailyBarObservation

rate:
- RateCurvePointObservation

dividend:
- DividendObservation
```

The total is ten record types. Unsupported record types raise `TypeError`, and callers cannot override the category mapping. `SourceReference`, `NormalizationMetadata`, `UnderlyingKey`, and `OptionContractKey` are not freshness-assessable normalized observation records.

The function never mutates the record, policy, context, metadata, or sources; fetches data; inspects an exchange calendar; calculates economic metrics; or calls screening or reporting code.

#### Chronology rules

- `metadata.normalized_at > evaluation_at` adds `record_normalized_after_evaluation`.
- Any source `retrieved_at > evaluation_at` adds `source_retrieved_after_evaluation`.
- Any source `observed_at > evaluation_at` adds `source_observed_after_evaluation`.

#### Normalization-quality rules

- `NormalizationQualityFlag.INCOMPLETE` adds `normalization_incomplete`.
- `NormalizationQualityFlag.TIMESTAMP_ASSIGNED` adds `assigned_timestamp_not_allowed` when assigned timestamps are disallowed.

`unit_converted`, `symbol_mapped`, `contract_adjusted`, `composite_source`, and `interpolated` are not freshness failures by themselves.

#### Source-quality rules

Every source reference is inspected. `DELAYED`, `INDICATIVE`, `NON_FIRM`, and `PARTIAL` add their corresponding `*_not_allowed` reason when disallowed by policy. For `quote` and `analytics` records, any `HALTED` flag adds `halted_source`: a current quote or option analytic calculated during a halt may not represent a currently usable market. For `activity`, `contract_reference`, `historical_bar`, `rate`, and `dividend` records, the flag remains visible but does not independently add a freshness reason or make the record ineligible in v0.1. A completed historical bar, contract term, rate point, dividend record, volume record, or open-interest record is not automatically invalid merely because one source describes a halt. `LOCKED`, `CORRECTED`, `PROVIDER_ESTIMATED`, `AFTER_HOURS`, and `UNKNOWN_CONDITION` do not independently determine freshness in v0.1. Corrected data must first pass correction selection. `AFTER_HOURS` does not replace the normalized record's declared `MarketPhase`. Freshness never adds, removes, or mutates source flags.

#### Composite-source rule

For every multi-source record, not only records with `record_origin=system_composite`, the evaluator calculates the complete source observation span and adds `source_observation_span_exceeded` when it exceeds `maximum_source_observation_span_seconds`. It evaluates every source's age, retrieval lag, and quality flags. The oldest source participates in the age decision: one stale source can make the record stale, one prohibited condition can make it ineligible, an acceptable `effective_observed_at` cannot hide an old source, and source ages are never averaged. These rules are mandatory for `system_composite` records.

#### Quote rules

For `UnderlyingQuoteObservation` and `OptionQuoteObservation`, `MarketPhase.UNKNOWN` adds `unknown_market_phase`, and `QuoteScope.UNKNOWN` adds `unknown_quote_scope`. When regular-session quotes are required and market phase is not `REGULAR`, add `non_regular_session_quote`. Market phase is not inferred from source timestamps or source flags. Quote venue and scope are unchanged.

#### Historical-session rules

For `UnderlyingDailyBarObservation`:

- when completed sessions are required and `is_session_complete=False`, add `historical_session_incomplete`;
- when the bar is declared complete and its session date is later than `latest_completed_session_date`, add `session_date_after_latest_completed_session`;
- when a completed bar's session date gap exceeds `maximum_historical_bar_session_date_gap_days`, add `historical_bar_session_date_gap_exceeded`;
- an incomplete current-session bar receives no session-date-gap calculation.

For `OptionOpenInterestObservation`, a session date later than `latest_completed_session_date` adds `session_date_after_latest_completed_session`; a date gap above `maximum_open_interest_session_date_gap_days` adds `open_interest_session_date_gap_exceeded`. Quote, IV, Greeks, volume, rate, dividend, and contract-reference records have no session-date-gap rule.

#### Age rules

For categories with an age threshold, compare effective age and oldest-source age with the applicable category threshold, adding `effective_age_exceeded` or `oldest_source_age_exceeded` when exceeded. Compare maximum retrieval lag with `maximum_retrieval_lag_seconds`, adding `retrieval_lag_exceeded` when exceeded. Historical bars use the calendar-day session-date gap rather than category age in seconds but still apply retrieval-lag and source-span rules. A value equal to the configured maximum passes.

### 11.9 FreshnessAssessment

The future immutable record has these exact fields:

```text
FreshnessAssessment
    record_id: str
    category: MarketDataCategory
    status: FreshnessStatus
    reason_codes: Tuple[FreshnessReasonCode, ...]
    policy_id: str
    policy_version: str
    evaluated_at: datetime
    effective_age_seconds: Decimal
    oldest_source_age_seconds: Decimal
    maximum_retrieval_lag_seconds_observed: Decimal
    source_observation_span_seconds: Decimal
    session_date_gap_days: Optional[int]
```

`record_id` equals `record.metadata.record_id`; category is derived from record type; policy identity is copied unchanged; and `evaluated_at` equals the normalized UTC context time. Reason order and status follow the exact rules above. Metrics are supplied calculated facts, not policy conclusions. `session_date_gap_days` is present for completed daily bars and all open-interest records, including negative open-interest gaps, and is `None` otherwise. The assessment is frozen and hashable, does not embed or mutate the record, and contains no recommendation.

### Cross-record skew remains separate

`maximum_cross_record_skew_seconds` is not applied by single-record freshness
assessment. Milestone 3C.3 compares `metadata.effective_observed_at` and the
complete source-time range across only the five temporal-participant record
types locked in Section 13.8; no single effective timestamp can hide an older
participating source. It preserves every individual `FreshnessAssessment`.
Date/reference-oriented records retain their individual 3C.2 freshness proof
but do not enter 3C.3 seconds-based spans. Relationship coherence, selection,
historical completeness, and transformation remain later Milestone 3C units.

## 12. Snapshot coherence

Snapshot coherence is dependency-ordered rather than one broad operation.
Milestone 3C.3 assesses only binding-set temporal coherence under Section 13.8.
Milestone 3C.4a first supplies portable binding references. Milestones 3C.4b
through 3C.4e will then consume explicit relationship or grouping requests
before deciding which supplied records are intended counterparts and applying
the relationship requirements below. Later units separately perform
deterministic selection, historical completeness, and economic transformation.

The represented option-domain relationship requirements in Sections 12.1
through 12.3 are therefore future 3C.4b through 3C.4e work, not 3C.3 timing or
3C.4a reference rules. The rate/dividend linkage and applicability paragraph
in Section 12.2 is 3C.7 work. Section 12.4 is future 3C.6 historical-series
work. No stage may replace inspection of a participating source time with one
effective timestamp or convert a calendar date to a synthetic datetime.

### 12.1 Quote alignment

When a future explicit 3C.4b relationship request identifies underlying and
option quotes as counterparts, they must refer to the same underlying, use compatible
market phases and quote scopes, use compatible venues where relevant, pass the
freshness policy, and disclose delayed or indicative status. Their configured
effective and source observation-time skew is assessed earlier by 3C.3 when
they are supplied in the same binding set.

### 12.2 Analytics alignment

When an explicit 3C.4b relationship request identifies an option quote, IV,
and Greeks as counterparts, 3C.4c and 3C.4e own option-contract identity,
comparable-session, declared-model, and internal quote/analytics methodology
coherence. 3C.3 proves timing only and does not infer this relationship.

Every linkage from analytics to rate or dividend inputs belongs to 3C.7. This
includes rate-curve-point identity and tenor applicability; dividend-event
identity, status, and applicability; and every economic use of rates or
dividends. 3C.4b through 3C.4e do not represent or evaluate those
relationships.

### 12.3 Volume and open interest

A future `OPTION_ACTIVITY_V0_1` group always declares one option-volume
observation and one option-open-interest observation and may additionally
declare one option quote. These observations need not have identical
timestamps. Each keeps its own observation time or session date, and
differences remain visible.

Milestone 3C.4c evaluates exact option-contract identity and comparable
session/date relationships among the resolved volume, open-interest, and
optional option-quote members.

3C.4e evaluates volume/open-interest coherence and, when the optional quote
role is present, quote/activity relationship and activity applicability. 3C.5
chooses the latest eligible completed open-interest observation or any other
preferred observation. Cumulative volume is used only under its declared as-of
time, and stale open interest must not be presented as current intraday open
interest without disclosure. Open-interest session dates do not enter 3C.3
seconds-based spans.

### 12.4 Historical series

Historical percentile and realized-volatility inputs require one observation per valid completed US trading session, no duplicate session dates, consistent adjustment methodology, consistent sampling frequency, declared lookback count, and no mixing of intraday, weekly, or end-of-day observations.

These are Milestone 3C.6 historical-series assembly and completeness rules.
Daily-bar dates do not enter 3C.3 seconds-based spans.

### 12.5 Multiple providers

Multiple providers may be combined only when every provider remains identified, composite methodology is explicit, source priority and conflict resolution are deterministic, and disagreement is not silently averaged. The normalized record carries `NormalizationMetadata.record_origin=system_composite`, cites at least two provider source references, and carries the `composite_source` normalization flag. No individual `SourceReference` may use `system_composite`.

The complete source observation-time span of a system composite must be checked. An acceptable `effective_observed_at` does not make excessive source skew acceptable, and one stale component may make the composite ineligible even when another component is fresh. The exact composite-freshness rule remains part of Milestone 3B.

## 13. Deterministic correction selection

The exact order of operations is:

```text
immutable normalized candidates
    ↓ deterministic correction selection
selected record or ambiguous result
    ↓ single-record freshness assessment
fresh record may enter later calculations
```

Freshness must not choose among competing corrections; correction selection occurs first. An ambiguous group cannot be current evidence. Selection neither mutates nor deletes candidates, and historical versions remain auditable.

### 13.1 CorrectionSelectionStatus

The exact enum order is:

```text
CorrectionSelectionStatus
    selected
    ambiguous
```

`selected` means exactly one candidate can be selected under the v0.1 rule. `ambiguous` means the candidates cannot be safely ordered. Invalid Python inputs raise validation errors rather than producing another status.

### 13.2 CorrectionSelectionReasonCode

The exact canonical order is:

```text
missing_provider_record_id
source_lineage_mismatch
conflicting_correction_ids_same_revision
tied_revision_vectors
incomparable_revision_vectors
only_candidate_selected
dominating_revision_vector_selected
```

The first five values are ambiguity reasons; the last two are selected reasons. `CorrectionSelection.reason_codes` remains a tuple for consistency and future extensibility, but every valid v0.1 result contains exactly one terminal reason. Reasons preserve declaration order and are never alphabetically sorted.

### 13.3 Source-lineage key

The correction-ordering key is:

```text
(
    provider_name,
    dataset_name,
    provider_record_id,
)
```

Provider and dataset names retain their normalized stored values. `provider_record_id` is mandatory when comparing more than one candidate. Source ID, provider request ID, retrieval time, payload hash, and correction ID are not part of the key or ordering.

For each normalized record, collect all keys, sort them lexicographically, and reject duplicate lineage keys inside one candidate for correction-ordering purposes. Candidates can be ordered only when they have exactly the same ordered lineage-key set.

### 13.4 Revision vector and dominance

For each ordered source-lineage key, correction selection defines one and only
one revision value:

```text
normalized revision component =
    revision_number when revision_number is positive
    otherwise 0
```

`revision_number=None` and `revision_number=0` both map to normalized revision
component `0`. Positive revision numbers retain their integer values. Every
correction-selection comparison uses this normalized revision component. In
particular, "same numeric revision" means the same normalized revision
component, not equality of the raw `revision_number` fields. Correction-identity
conflict detection and revision-vector construction use the same normalized
revision component; separate raw-revision and vector-revision semantics are
prohibited.

The candidate revision vector contains those normalized components in
source-lineage-key order. Revisions are comparable only within the same lineage
key. Revisions from unrelated providers or datasets are never compared directly.
`provider_correction_id` proves correction identity but supplies no ordering
semantics, and lexical correction-ID order is prohibited. Normalized time,
retrieval time, observation time, file order, insertion order, record ID, payload
hash, set order, and dictionary order are prohibited as latest-revision
tie-breakers.

Candidate A strictly dominates candidate B when both have the same ordered lineage keys, every revision component in A is greater than or equal to its counterpart in B, and at least one component is greater.

`evaluated_at` is timezone-aware and normalized to UTC. Before ordering corrections, every candidate must satisfy `candidate.normalized_at <= evaluated_at`. A candidate normalized later is invalid input and raises `ValueError`; it does not produce an ambiguous selection and is never silently filtered. The function never substitutes the current clock. Because `NormalizationMetadata` already requires normalization after every source retrieval, this check establishes that each candidate existed by the evaluation time.

The exact terminal-reason algorithm is:

1. Validate the non-empty tuple or list of exact `NormalizationMetadata` candidates, unique record IDs, evaluated-at chronology, and supplied rule fields.
2. Normalize candidates into ascending `record_id` order for presentation only.
3. If exactly one candidate exists, return `selected` with `only_candidate_selected`.
4. For multiple candidates, if any source lacks `provider_record_id`, return `ambiguous` with `missing_provider_record_id`.
5. Construct each candidate's source-lineage keys.
6. If one candidate contains duplicate source-lineage keys, raise `ValueError`; do not return ambiguity.
7. If candidates lack identical ordered lineage-key sets, return `ambiguous` with `source_lineage_mismatch`.
8. If candidates contain different non-equivalent correction identities for the same lineage key and normalized revision component, return `ambiguous` with `conflicting_correction_ids_same_revision`.
9. Construct revision vectors using those same normalized revision components.
10. If all revision vectors are identical, return `ambiguous` with `tied_revision_vectors`.
11. If exactly one candidate strictly dominates every other candidate, return `selected` with `dominating_revision_vector_selected`.
12. Otherwise, return `ambiguous` with `incomparable_revision_vectors`.

For correction-identity comparison, `None` and a supplied ID differ, two
different supplied IDs differ, and identical supplied IDs are equivalent.
Correction IDs establish identity only, never define ordering, and are never
compared lexicographically.

The normalized-revision and correction-identity cases include:

```text
(revision_number=None, correction_id=None)
versus (revision_number=0, correction_id=None)
    -> same normalized revision 0, equivalent correction identity
    -> no identity conflict
    -> vectors may later tie

(revision_number=None, correction_id=None)
versus (revision_number=0, correction_id="A")
    -> same normalized revision 0, conflicting correction identity
    -> conflicting_correction_ids_same_revision

(revision_number=0, correction_id="A")
versus (revision_number=0, correction_id="A")
    -> same normalized revision 0, equivalent correction identity
    -> no identity conflict

(revision_number=1, correction_id="A")
versus (revision_number=1, correction_id="B")
    -> same normalized revision 1, conflicting correction identity
    -> conflicting_correction_ids_same_revision

(revision_number=1, correction_id="A")
versus (revision_number=2, correction_id="B")
    -> different normalized revisions
    -> no same-revision identity conflict
    -> revision-vector ordering continues
```

For candidates with identical source-lineage-key sets, correction identities are
compared per matching source-lineage key plus normalized revision component. If
any such matched pair or group has non-equivalent correction identities,
selection terminates with `conflicting_correction_ids_same_revision`. Identity
differences across different normalized revision components do not create this
reason. For three or more candidates, the check covers the complete candidate
group rather than only adjacent candidates in input order. After the complete
identity-conflict check passes, revision vectors determine tied, dominating, or
incomparable behavior. The result is independent of candidate input order.

```text
(0) versus (1) → select (1)
(1, 1) versus (2, 1) → select (2, 1)
(2, 1) versus (1, 2) → ambiguous
(2, 2) versus (2, 2) → ambiguous
```

A larger record ID or later retrieval time is never treated as newer.

### 13.5 CorrectionSelection

The future immutable result is:

```text
CorrectionSelection
    semantic_observation_key: str
    candidate_record_ids: Tuple[str, ...]
    selected_record_id: Optional[str]
    status: CorrectionSelectionStatus
    reason_codes: Tuple[CorrectionSelectionReasonCode, ...]
    rule_id: str
    rule_version: str
    evaluated_at: datetime
```

Direct construction applies the following canonical validation:

- `semantic_observation_key` must be an actual string. Leading and trailing
  whitespace is trimmed, and the result must be non-empty. v0.1 defines no
  global semantic-key registry.
- `candidate_record_ids` accepts only a tuple or list. Every member must be an
  actual string, is trimmed, and must remain non-empty. At least one ID is
  required. Duplicates after normalization raise `ValueError`. Storage is an
  ascending lexicographically sorted tuple, so caller order is not preserved.
- When supplied, `selected_record_id` must be an actual string, is trimmed, must
  remain non-empty, and must belong to the normalized `candidate_record_ids`.
  `selected` requires such a candidate ID; `ambiguous` requires
  `selected_record_id=None`. The constructor cannot create a selected result
  pointing outside the candidate set.
- `reason_codes` accepts only a tuple or list whose members are actual
  `CorrectionSelectionReasonCode` values. Exactly one reason is required and
  storage is normalized to a tuple. The first five declared reasons require
  `ambiguous`; the last two require `selected`. Status/reason mismatches are
  invalid.
- `rule_id` and `rule_version` must be actual strings. Each is trimmed and must
  remain non-empty.
- `evaluated_at` must be a timezone-aware datetime and is normalized to UTC. A
  naive datetime is invalid.

Thus, `candidate_record_ids` is always non-empty, unique, and sorted after
normalization; selected-ID membership is mandatory; and every valid v0.1 result
contains exactly one terminal reason. Direct-constructor canonicalization must
match output produced by `select_correction_candidate`. The result is frozen,
hashable, independent of candidate objects, and free of wall-clock calls; it
neither embeds nor mutates candidates.

The planned pure function is:

```text
select_correction_candidate(
    semantic_observation_key,
    candidates,
    evaluated_at,
    rule_id,
    rule_version,
) -> CorrectionSelection
```

The public `candidates` input accepts only a tuple or list. Arbitrary iterables
are rejected. The collection must be non-empty, and every element must satisfy
`type(candidate) is NormalizationMetadata`; subclasses are not accepted.
Candidate `record_id` values must be unique, so repeated references to the same
candidate fail through duplicate record-ID validation. Input order has no
selection meaning. Candidates are normalized into ascending `record_id` order
only for result presentation, never for revision selection.

The exact invalid-input exception categories are:

```text
wrong candidates container type                 -> TypeError
wrong candidate element type or subclass        -> TypeError
empty candidate tuple or list                    -> ValueError
duplicate candidate record IDs                   -> ValueError
duplicate lineage key inside one candidate       -> ValueError
candidate normalized after evaluated_at          -> ValueError
```

Invalid Python inputs do not create additional result statuses. The function is
pure: it does not mutate candidates, read the wall clock, or depend on provider,
network, filesystem, or random state.

### 13.6 Milestone 3C.1 semantic observation identity

Milestone 3C.1 defines one deterministic, provider-neutral identity for each
supported normalized economic observation. Different immutable versions or
corrections of the same economic observation have the same semantic observation
key. Economically different observation slots have different keys. A semantic
observation key identifies the observation slot, not one stored record version.

The only planned public 3C.1 function is:

```text
semantic_observation_key(record) -> str
```

No public `SemanticObservationKey` dataclass, enum, alias, or other record is
planned. `CorrectionSelection.semantic_observation_key` remains `str`. When
later 3C binding logic consumes a `CorrectionSelection`, the selection's stored
semantic key must equal the deterministic key produced for the bound normalized
observation. Milestone 3C.1 does not define or implement that binding logic.

#### Supported input and purity boundary

The function supports exactly these ten normalized observation record types:

```text
UnderlyingQuoteObservation
OptionContractReference
OptionQuoteObservation
OptionVolumeObservation
OptionOpenInterestObservation
OptionImpliedVolatilityObservation
OptionGreeksObservation
UnderlyingDailyBarObservation
RateCurvePointObservation
DividendObservation
```

Every accepted value must satisfy `type(record) is SupportedRecordType` for one
of those exact types. Subclasses and all unsupported objects raise `TypeError`.
The function accepts no category override and introduces no new economic
validation layer because supported inputs are already validated immutable
records. An unexpected inability to encode an otherwise valid supported record
is an internal contract violation and must not be silently repaired. No custom
public exception is introduced.

The function is pure. It does not inspect the wall clock, filesystem,
environment, network, a provider SDK, random state, or LLM output, and it does
not mutate the record.

#### Versioned canonical encoding

The exact v0.1 format is:

```text
semantic-observation-v0.1:<canonical-tagged-json>
```

The mandatory prefix is followed by the exact canonical tagged-JSON encoding
defined in Section 14. Conceptually, the tagged JSON is produced by applying the
same deterministic canonicalization semantics as
`canonicalize_lineage_parameters(...)` to one exact built-in `dict` containing
`record_type` and the authoritative identity fields below. The `record_type`
value is the exact public normalized-record type name shown in the supported
type list. Enum identity components are passed as their exact `.value` strings.
Dates, datetimes, Decimals, strings, integers, and `None` retain their exact
supported canonical types.

This reuse is an encoding rule only. Semantic observation identity remains
conceptually separate from calculation lineage. v0.1 uses no hash; the complete
key remains human-inspectable and audit-friendly. Any change to semantic
identity meaning or field composition requires a new semantic-key version.

Nested `UnderlyingKey` identity is encoded as one exact built-in dictionary with
these exact keys and values:

| Canonical dictionary key | Exact stored value |
| --- | --- |
| `symbol` | `underlying_key.symbol` |
| `listing_mic` | `underlying_key.listing_mic` |
| `security_type` | `underlying_key.security_type.value` |
| `currency` | `underlying_key.currency` |

Nested `OptionContractKey` identity is encoded as one exact built-in dictionary
with these exact keys and values:

| Canonical dictionary key | Exact stored value |
| --- | --- |
| `underlying_key` | the exact nested `UnderlyingKey` dictionary above |
| `expiration` | `contract_key.expiration` |
| `option_type` | `contract_key.option_type` |
| `strike` | `contract_key.strike` |
| `contract_multiplier` | `contract_key.contract_multiplier` |
| `currency` | `contract_key.currency` |
| `deliverable_id` | `contract_key.deliverable_id` |

These dictionaries use the already-normalized stored values. They never use an
object representation, hash value, insertion order, or Python object identity.
Strike remains a `Decimal` in the canonical tagged representation and is never
converted through `float`.

#### Authoritative identity fields

The following lists are exact and authoritative. Implementations may not add or
remove fields dynamically.

Each row below defines the exact additional canonical dictionary keys and their
record sources. The `record_type` key is present in every dictionary. A nested
key uses the exact nested dictionary defined above.

| Normalized record type | Exact canonical dictionary entries in addition to `record_type` |
| --- | --- |
| `UnderlyingQuoteObservation` | `underlying_key=record.underlying_key`, `session_date=record.session_date`, `effective_observed_at=record.metadata.effective_observed_at`, `market_phase=record.market_phase.value`, `quote_scope=record.quote_scope.value`, `venue_mic=record.venue_mic` |
| `OptionContractReference` | `contract_key=record.contract_key` |
| `OptionQuoteObservation` | `contract_key=record.contract_key`, `session_date=record.session_date`, `effective_observed_at=record.metadata.effective_observed_at`, `market_phase=record.market_phase.value`, `quote_scope=record.quote_scope.value`, `venue_mic=record.venue_mic` |
| `OptionVolumeObservation` | `contract_key=record.contract_key`, `session_date=record.session_date`, `effective_observed_at=record.metadata.effective_observed_at` |
| `OptionOpenInterestObservation` | `contract_key=record.contract_key`, `open_interest_session_date=record.open_interest_session_date` |
| `OptionImpliedVolatilityObservation` | `contract_key=record.contract_key`, `session_date=record.session_date`, `effective_observed_at=record.metadata.effective_observed_at`, `model_name=record.model_name`, `model_version=record.model_version`, `rate_input_description=record.rate_input_description`, `dividend_input_description=record.dividend_input_description` |
| `OptionGreeksObservation` | `contract_key=record.contract_key`, `session_date=record.session_date`, `effective_observed_at=record.metadata.effective_observed_at`, `model_name=record.model_name`, `model_version=record.model_version`, `rate_input_description=record.rate_input_description`, `dividend_input_description=record.dividend_input_description` |
| `UnderlyingDailyBarObservation` | `underlying_key=record.underlying_key`, `session_date=record.session_date` |
| `RateCurvePointObservation` | `curve_id=record.curve_id`, `currency=record.currency`, `tenor_days=record.tenor_days`, `effective_date=record.effective_date`, `compounding_convention=record.compounding_convention`, `day_count_convention=record.day_count_convention` |
| `DividendObservation` | `underlying_key=record.underlying_key`, `dividend_type=record.dividend_type`, `ex_date=record.ex_date`, `status=record.status.value` |

An intraday quote is a time-specific market observation, so different effective
observation times are different quote slots. Quote market phase, scope, and
venue identity are also semantic distinctions. Cumulative volume is an as-of
observation, but its value and completion state are not identity. Open interest
and daily bars are session-date observations and do not gain an effective-time
identity component. Option analytics distinguish declared model and rate and
dividend input methodologies; their numeric outputs do not define identity.
Rate points distinguish curve, tenor, effective date, and conventions.
Dividend forecast, announced, and historical statuses are distinct semantic
states.

For `OptionContractReference`, the exact `contract_key` identifies the economic
contract. Changes or corrections to the reference record's descriptive terms,
including listing, last-trade, exercise-style, or settlement details, remain
versions of the same contract-reference observation when `contract_key` is
unchanged. For Greeks, populated or missing Greek fields and `theta_day_basis`
do not alter v0.1 identity. For daily bars, adjustment values and methodology
do not alter identity; later historical transformation rules determine
methodology compatibility.

`metadata.effective_observed_at` participates in semantic identity for exactly
five record types:

```text
UnderlyingQuoteObservation
OptionQuoteObservation
OptionVolumeObservation
OptionImpliedVolatilityObservation
OptionGreeksObservation
```

Effective time must not be added to date-based observations. Retrieval,
publication, or normalization timestamps never substitute for an identity date
or effective time.

#### Value-versus-identity and universal exclusions

A field belongs in semantic identity only when changing it changes what
economic observation is represented, rather than merely changing the observed
value, completeness, source or provenance, revision, or normalization process.
This rule explains the exact per-record lists but does not authorize dynamic
field selection.

Unless explicitly included above, every semantic key excludes:

```text
metadata.record_id
all SourceReference identity and provenance fields
provider and dataset identity
provider_record_id and provider_request_id
source_id
retrieved_at and normalized_at
payload_sha256
revision_number and provider_correction_id
normalization methodology and version
unit convention
source and normalization quality flags
actual observed numeric values
bid and ask sizes
prices, volume, and open-interest values
implied-volatility and Greek values
bar values
rate values
dividend amounts and yields
```

#### Provider neutrality and correction comparability

Records from different providers may legitimately produce the same semantic
observation key when they claim to represent the same economic observation
slot. This does not make them corrections of one another automatically:

```text
same semantic key != automatically comparable corrections
```

Correction comparability remains governed by the Section 13 source-lineage
requirements. Candidates with one semantic key but incompatible source lineage
produce the already-defined correction-selection ambiguity result. Provider
identity must not be added to the semantic key to suppress that ambiguity.
Provider provenance remains separately auditable.

#### Collision and correction invariants

When every declared identity field remains unchanged, all of these corrections
retain the same semantic key:

```text
quote bid or ask corrected
volume value or completion state corrected
open-interest value corrected
implied-volatility value corrected
Greek values corrected or additional Greeks populated
daily-bar prices or volume corrected
adjusted close or adjustment methodology corrected
rate value corrected
dividend amount or payment date corrected
```

All of these changes produce different keys:

```text
different underlying or option contract
different quote effective_observed_at
different quote market phase, scope, or venue identity
different volume effective_observed_at
different open-interest session date
different IV or Greek model or declared rate or dividend input description
different daily-bar session date
different rate curve, tenor, effective date, or conventions
different dividend ex-date, type, or status
```

Milestone 3C.1 does not infer semantic equivalence across different model names,
provider methodology descriptions, curve IDs, dividend types or statuses,
listings or share classes, quote scopes, or venues. It uses no fuzzy matching,
LLM interpretation, or alias registry. Exact normalized fields define identity.

#### Relationship to Milestone 3C.2

Only this directional dependency is locked:

```text
normalized immutable records
    -> semantic observation key
    -> correction candidate grouping
    -> explicit CorrectionSelection
    -> selected normalized record
    -> explicit FreshnessAssessment
    -> 3C.3 binding-set temporal coherence
    -> 3C.4a auditable binding references
    -> 3C.4b through 3C.4e represented option-domain relationship/group coherence
    -> 3C.5 deterministic cross-observation selection
    -> 3C.6 historical-series assembly and completeness
    -> 3C.7 transformation and CalculationLineage
```

The 3C.4b-through-3C.4e step applies only to represented option-domain
relationships. Rate-curve-point and dividend-event relationship work bypasses
that step and belongs to 3C.7.

Milestone 3C.1 specifies only semantic identity. The selected/fresh binding API
is defined separately by Milestone 3C.2 below. Milestone 3C.1 does not define
snapshot statuses or reasons, transformation APIs, transformations, or pricing
behavior.

### 13.7 Milestone 3C.2 per-record selected/fresh binding

Milestone 3C.2 defines a deterministic proof layer for one complete semantic
observation candidate group:

```text
one complete semantic observation candidate group
    -> deterministic correction selection
    -> one selected normalized record
    -> deterministic freshness assessment
    -> one auditable selected/fresh binding
```

This stage proves only that one normalized record was selected from its complete
verified correction group and was fresh under one explicit policy and context.
It does not perform cross-record skew checks, quote phase/scope/venue
compatibility, analytics alignment, selection among different semantic
observations, historical-series completeness, economic transformations,
pricing, or `CalculationLineage` construction.

#### Public API

Milestone 3C.2 added exactly these two public names to
`convexity_hunter.market_data`:

```text
SelectedFreshMarketDataBinding
bind_selected_fresh_market_data
```

The planned function is:

```text
bind_selected_fresh_market_data(
    candidates,
    correction_evaluated_at,
    correction_rule_id,
    correction_rule_version,
    freshness_policy,
    freshness_context,
) -> SelectedFreshMarketDataBinding
```

The original 37 public names and their exact order remain unchanged. The two
names above are appended to `market_data.__all__` after those 37 names,
in exactly the displayed order: first `SelectedFreshMarketDataBinding`, then
`bind_selected_fresh_market_data`. No public name may be inserted among or
reorder the original names. The implemented count at completion of 3C.2 was 39;
the current count after 3C.3 is 42.
Milestone 3C.2 introduces no additional public enum, status, reason code, alias,
registry, helper, or exception class.

#### Immutable binding artifact

The exact immutable record and field order are:

```text
SelectedFreshMarketDataBinding
    candidate_records: Tuple[SupportedNormalizedRecord, ...]
    correction_selection: CorrectionSelection
    freshness_policy: MarketDataFreshnessPolicy
    freshness_context: FreshnessContext
    freshness_assessment: FreshnessAssessment
```

`SupportedNormalizedRecord` is descriptive contract notation only and is not a
new public alias. The supported values are exactly the ten normalized record
types accepted by both `semantic_observation_key` and
`assess_market_data_freshness`.

The binding is frozen, immutable in ordinary use, and structurally comparable
for equality. It is not guaranteed to be hashable in v0.1. Some already-valid
normalized records may contain nested values accepted by existing contracts
whose runtime hashability is not guaranteed. Milestone 3C.2 does not strengthen
those earlier nested validation boundaries or add a runtime `hash(...)`
eligibility check merely to make the wrapper hashable.

The constructor stores candidate records in a tuple and stores only the supplied
frozen or immutable contract objects. It performs no mutation. Structural
equality is deterministic after candidate canonicalization, and equal
authoritative inputs, including the same correction-evaluation context, produce
equal bindings regardless of candidate input order. Callers must not rely on
using a binding as a dictionary key or set member. No custom `__hash__` is
planned; implementation must not use identity-based hashing, catch nested
unhashability, or invent a hash value.

The artifact embeds the complete immutable candidate group so the correction
proof remains auditable without a process-global record registry. It embeds the
complete immutable freshness policy and context because policy ID/version alone
do not preserve thresholds, switches, or `latest_completed_session_date`.

The binding exposes exactly these public properties:

```text
semantic_observation_key -> str
selected_record -> one exact supported normalized record
```

After constructor validation succeeds, `semantic_observation_key` returns
`correction_selection.semantic_observation_key`. `selected_record` returns the
unique candidate for which:

```text
candidate.metadata.record_id == correction_selection.selected_record_id
```

The semantic key and selected record are derived properties, not duplicate
stored fields.

#### Candidate boundary and semantic-group integrity

Both the public function and direct binding construction accept candidate
records only through a tuple or list. Any other container raises `TypeError`.
Every element must satisfy `type(candidate) is SupportedRecordType` for one of
the exact ten supported normalized record types. Subclasses and unsupported
objects raise `TypeError`.

The collection must be non-empty and candidate `metadata.record_id` values must
be unique. An empty collection or duplicate record ID raises `ValueError`.
Storage is a tuple containing the supplied candidate record objects in ascending
`candidate.metadata.record_id` order. Caller order has no semantic meaning and
must not affect the result.

For every candidate, the binding derives:

```text
semantic_observation_key(candidate)
```

Every derived key must be exactly equal. A mixed-semantic candidate group raises
`ValueError`. The common group key is derived from the complete normalized
records and is never accepted as an independent caller-supplied function
argument. Candidate metadata alone is insufficient to prove semantic grouping.

#### Global and public-function validation precedence

The general binding-layer validation order is:

```text
top-level Python type validation
    -> candidate element type validation
    -> collection and value canonicalization
    -> deterministic recomputation
    -> chronology
    -> eligibility
```

No economic or value computation occurs before all required top-level Python
object types have been validated. Wrong Python types raise `TypeError` before
value-level `ValueError` conditions are evaluated according to the path-specific
orders in this section. Errors delegated to the existing correction and
freshness functions occur only after the binding layer's preceding validation
steps have completed.

For `bind_selected_fresh_market_data`, the exact observable order is:

**Phase A — top-level types**

1. Validate that `candidates` is a tuple or list.
2. Require `type(freshness_policy) is MarketDataFreshnessPolicy`.
3. Require `type(freshness_context) is FreshnessContext`.

The binding layer does not duplicate validation of
`correction_evaluated_at`, `correction_rule_id`, or
`correction_rule_version`. Their type and value validation remains authoritative
in `select_correction_candidate` when it is invoked in Phase D.

**Phase B — candidate element types**

4. Validate every candidate in caller order using the exact supported-record
   rule. The first wrong element type or subclass raises `TypeError`.

**Phase C — candidate collection values**

5. Reject an empty candidate collection with `ValueError`.
6. Reject duplicate candidate record IDs with `ValueError`.
7. Sort candidates by normalized record ID and store the canonical tuple.
8. Derive every semantic observation key.
9. Reject mixed semantic keys with `ValueError`.

**Phase D — correction selection**

10. Call `select_correction_candidate` with the derived key, canonical candidate
    metadata, and explicit correction arguments.
11. Propagate its existing `TypeError` or `ValueError` taxonomy unchanged.
12. Reject an ambiguous result with binding-level `ValueError`. After a selected
    result, resolve the selected record uniquely from the canonical tuple.

**Phase E — chronology and freshness**

13. Enforce `correction_selection.evaluated_at <=
    freshness_context.evaluation_at`; a violation raises `ValueError`.
14. Compute freshness from the selected record, exact policy, and exact context.
15. Reject any non-fresh result with `ValueError`.
16. Construct the validated binding from the canonical candidates and
    authoritative sidecars, policy, and context.

Consequently:

```text
empty candidates + wrong freshness_policy type
    -> TypeError from freshness_policy validation
unsupported candidate element + an empty-value condition
    -> TypeError from candidate element validation
valid candidate group + invalid correction_rule_id type
    -> existing selector TypeError
```

#### Authoritative correction selection and selected-record proof

The public function recomputes correction selection by calling the existing
`select_correction_candidate` with:

```text
derived group semantic key
tuple(candidate.metadata for candidate in canonical candidate order)
correction_evaluated_at
correction_rule_id
correction_rule_version
```

Every group, including a one-record group, must pass explicit correction
selection. A one-record group must produce `selected` with exactly
`only_candidate_selected`; a record never bypasses selection merely because no
competing correction is currently known.

If the recomputed result is `ambiguous`, the binding function raises
`ValueError`. It does not return `None` or create a rejection assessment.
Callers that need to inspect an ambiguous result may call
`select_correction_candidate` separately.

A successful binding requires all of these relationships:

```text
correction_selection.status == selected
correction_selection.selected_record_id is not None
correction_selection.selected_record_id appears exactly once in candidate_records
correction_selection.semantic_observation_key
    == semantic_observation_key(candidate) for every candidate
```

The selected record is resolved only from the canonical candidate tuple. Record
ID order, caller or file order, retrieval time, normalization time, and lexical
correction-ID order never replace the existing correction-selection algorithm.

#### Correction-evaluation context trust boundary

For the public function, the explicit `correction_rule_id`,
`correction_rule_version`, and `correction_evaluated_at` arguments are the
authoritative correction-evaluation context. For direct construction, the
supplied `correction_selection.rule_id`, `correction_selection.rule_version`,
and `correction_selection.evaluated_at` fields are the authoritative
correction-evaluation context used for recomputation.

These values remain subject to the existing selector's type, normalization, and
value validation. Every candidate must satisfy
`candidate.metadata.normalized_at <= correction_selection.evaluated_at`, and the
binding chronology rule still requires
`correction_selection.evaluated_at <= freshness_context.evaluation_at`. The
binding contract does not prove that a rule identity was approved or registered
by an external authority, or that the evaluation time was chosen by one. v0.1
introduces no process-global rule registry, rule fingerprint, configuration
object, or external trust source.

Direct construction still recomputes the complete correction selection from the
derived common semantic key, canonical candidate metadata, and that supplied
authoritative correction-evaluation context. Exact equality between the
supplied and recomputed `CorrectionSelection` proves that:

- the semantic observation key agrees with the complete candidate group;
- the candidate record IDs agree with the complete candidate group;
- the selected record ID agrees with deterministic correction ordering;
- status and the terminal reason agree with the selector outcome; and
- the rule fields and evaluation time are valid, normalized, and preserved
  consistently.

Exact equality does not prove that the supplied rule ID/version is the only
legitimate rule identity, that the evaluation time came from a trusted external
authority, or that another valid rule label or valid evaluation time must be
rejected. A different valid rule ID, rule version, or evaluation time may
therefore produce a different but valid binding when all candidate-existence,
selection, and chronology constraints still pass.

#### Selection/freshness chronology and authoritative freshness

The exact per-record chronology is:

```text
correction_selection.evaluated_at <= freshness_context.evaluation_at
```

Equality is valid. A correction selection evaluated after the freshness context
raises `ValueError`. This preserves the operational sequence of selection first
and freshness second. Milestone 3C.3 requires structurally equal complete
freshness contexts across a temporally coherent binding set but introduces no
separate snapshot time. Later relationship or transformation contracts may
define explicit as-of-time requirements. Milestone 3C.2 defines no relationship
to `CalculationLineage.calculated_at`.

The public binding function computes freshness through:

```text
assess_market_data_freshness(
    selected_record,
    freshness_policy,
    freshness_context,
)
```

A successful binding requires exactly:

```text
freshness_assessment.status == fresh
freshness_assessment.reason_codes == (fresh_within_policy,)
```

`stale`, `ineligible`, and `unknown` results all raise `ValueError`. They are not
converted into missing data, zero values, a binding, or a new status. The
complete recomputed `FreshnessAssessment` is stored in the binding.

#### Direct-construction trust boundary

Direct construction must not trust supplied sidecars merely because their own
constructors accepted them. The binding constructor independently performs this
exact observable validation sequence:

**Phase A — top-level types**

1. Validate that `candidate_records` is a tuple or list.
2. Require `type(correction_selection) is CorrectionSelection`.
3. Require `type(freshness_policy) is MarketDataFreshnessPolicy`.
4. Require `type(freshness_context) is FreshnessContext`.
5. Require `type(freshness_assessment) is FreshnessAssessment`.

**Phase B — candidate element types**

6. Validate every candidate in caller order using the exact supported-record
   rule. The first wrong element type or subclass raises `TypeError`.

**Phase C — candidate collection values**

7. Reject an empty candidate collection with `ValueError`.
8. Reject duplicate candidate record IDs with `ValueError`.
9. Sort candidates by record ID into the canonical tuple.
10. Derive every semantic observation key.
11. Reject mixed semantic keys with `ValueError`.

**Phase D — correction proof**

12. Use the supplied selection's rule ID, rule version, and evaluation time as
    the authoritative correction-evaluation context for recomputation.
13. Recompute the full correction selection from the canonical candidate
    metadata, derived key, and that context, propagating existing selector
    validation errors unchanged.
14. Require exact equality with the supplied `correction_selection`; a mismatch
    raises `ValueError`. Equality establishes candidate-group and
    selector-result consistency, not external authorization of the rule or
    evaluation time.
15. Require selected status and resolve the selected record uniquely from the
    canonical tuple; invalid proof raises `ValueError`.

**Phase E — chronology**

16. Enforce `correction_selection.evaluated_at <=
    freshness_context.evaluation_at`; a violation raises `ValueError`.

**Phase F — freshness proof**

17. Recompute freshness from the selected record, supplied policy, and supplied
    context.
18. Require exact equality with the supplied `freshness_assessment`; a mismatch
    raises `ValueError`.
19. Require `fresh` status and only `fresh_within_policy`; otherwise raise
    `ValueError`.
20. Store the canonical candidate tuple and supplied authoritative selection,
    policy, context, and assessment objects.

Consequently:

```text
empty candidate_records + wrong correction_selection type
    -> TypeError from correction_selection validation
forged freshness sidecar + late correction chronology
    -> chronology ValueError before freshness-sidecar equality validation
freshness-sidecar mismatch + non-fresh supplied status
    -> freshness equality-mismatch ValueError before the fresh-only check
```

A correction sidecar raises `ValueError` when its independently derivable
selection claims are inconsistent with the complete candidate group or the
deterministic selector result. This includes mismatches in semantic observation
key, candidate record IDs, selected record ID, status, or reason codes. Invalid
rule fields or evaluation times still fail through existing selector validation,
candidate-existence validation, or binding chronology. A sidecar is not rejected
solely because a valid alternative rule ID, rule version, or evaluation time was
used consistently. The public function accepts no caller-supplied correction or
freshness sidecar; it calculates both and then constructs the validated binding.

The freshness trust boundary is unchanged. Direct construction independently
recomputes freshness from the selected record, complete supplied
`MarketDataFreshnessPolicy`, and complete supplied `FreshnessContext`.
Consequently every `FreshnessAssessment` field remains independently verifiable,
and any structurally valid but inconsistent freshness sidecar raises
`ValueError`.

For direct construction, all sidecars and freshness inputs require exact types:

```text
type(correction_selection) is CorrectionSelection
type(freshness_policy) is MarketDataFreshnessPolicy
type(freshness_context) is FreshnessContext
type(freshness_assessment) is FreshnessAssessment
```

The public function likewise requires exact `MarketDataFreshnessPolicy` and
`FreshnessContext` objects. Subclasses and other objects raise `TypeError`.
Existing functions remain authoritative for validation of correction evaluation
time, correction rule identity/version, policy fields, and context fields; the
binding contract neither weakens nor duplicates that validation.

#### Failure behavior

`TypeError` is used for:

```text
wrong candidate container type
wrong candidate element type or subclass
wrong policy, context, or sidecar Python type or subclass
wrong correction argument types propagated from select_correction_candidate
wrong types propagated from an invoked existing authoritative function
```

`ValueError` is used for:

```text
empty candidate collection
duplicate candidate record IDs
mixed semantic observation keys
ambiguous correction selection
selection/result mismatch
selection evaluated after freshness evaluation
non-fresh freshness result
freshness/result mismatch
record, category, policy, context, or metric mismatch exposed by recomputation
invalid correction argument values propagated from select_correction_candidate
invalid values propagated from an invoked existing authoritative function
```

No custom public exception, binding status, or binding reason enum is introduced.

The path-specific orders above define deterministic precedence when multiple
defects coexist. Within those orders:

- candidate elements are checked in caller order;
- duplicate record IDs are checked before semantic-key derivation;
- mixed semantic keys are checked before correction recomputation;
- correction recomputation, and direct-constructor equality, are checked before
  chronology;
- chronology is checked before freshness recomputation or equality; and
- direct-constructor freshness equality is checked before the final fresh-only
  condition.

No public rejection status or reason code is returned. The binding contract does
not define finer precedence among multiple defects discovered inside one
delegated existing function; that function's existing deterministic validation
order and exception taxonomy remain authoritative.

#### Successful-path equivalence and future test expectations

The public function and direct constructor have identical successful semantics:

```text
same canonical candidate records
same authoritative correction-selection context and result
same freshness policy and context
same authoritative freshness result
    -> structurally equal bindings
```

Candidate input order does not affect successful binding equality. Bindings
with identical candidate records, policy, context, and selected record may
nevertheless be structurally unequal when their valid correction selections
differ by rule ID, rule version, or evaluation time. This is intentional: the
binding preserves the exact correction-evaluation event. Public-function and
direct-constructor equivalence applies only when both paths use the same
authoritative correction-evaluation context. Equal hashes are not promised. The
public function should conceptually compute the authoritative sidecars and pass
them to the validated constructor, but this is not required as an internal
implementation technique. Observable validation and successful output semantics
must follow this contract in either implementation.

Future 3C.2 tests must cover:

- frozen behavior and no mutation;
- deterministic structural equality and candidate-order independence;
- the absence of a hashability promise, with an optional regression showing
  that callers cannot depend on hashing when an existing valid nested value is
  unhashable;
- exact append order of the two public exports after the existing 37 names;
- exact top-level and path-specific validation precedence;
- equivalent successful output from the public function and direct constructor
  when both use the same correction-evaluation context;
- valid but structurally unequal bindings produced by a different valid rule ID,
  a different valid rule version, and a different valid evaluation time when all
  candidates existed, selection is unchanged, and chronology passes;
- rejection of invalid or empty correction rule IDs/versions, wrong rule-field
  Python types, evaluation before candidate normalization, and evaluation after
  freshness evaluation;
- rejection of correction-sidecar mismatches in semantic key, candidate IDs,
  selected ID, status, and terminal reason, plus ambiguous recomputed selection;
  and
- independent rejection of every freshness-sidecar field mismatch through
  recomputation from the selected record, full policy, and full context.

Tests must not require bindings to be hashable.

#### Determinism, snapshot boundary, and lineage

The record and function are pure. They do not mutate inputs; inspect the wall
clock; call `date.today` or `datetime.now`; read files or environment variables;
use randomness; access a network, provider SDK, or LLM; or use a process-global
registry. All time, rule, policy, and context values are explicit inputs. Input
order does not affect the resulting binding or its structural equality.

Milestone 3C.2 proves only per-record selected/fresh eligibility. Milestone 3C.3
may consume multiple bindings and inspect their preserved selected records,
candidate records and sources, freshness policies and contexts, correction and
freshness evaluation times, effective times, and source observation times.
Milestones 3C.4b through 3C.4e separately consume explicit relationship/group
requests for represented option-domain observations after 3C.4a references and
before using market phase, quote scope, venue, session, contract, or other
represented option-domain relationship fields.

Milestone 3C.2 does not evaluate `maximum_cross_record_skew_seconds`, global
timestamp ranges, common cross-record policy or context, phase/scope/venue
compatibility, analytics/quote alignment, activity/reference selection,
rate/dividend relationship or economic use, or historical completeness.
Activity/reference selection remains later 3C.5 work. Every rate/dividend
relationship, identity, linkage, applicability, selection for economic use,
and economic use belongs to 3C.7. The 3C.2 output remains stable before those
future algorithms are specified because it retains all required immutable
inputs and proof objects.

Milestone 3C.2 does not create or modify `CalculationLineage`. The dependency is:

```text
SelectedFreshMarketDataBinding
    -> 3C.3 binding-set temporal coherence
    -> 3C.4a auditable binding references
    -> 3C.4b through 3C.4e represented option-domain relationship/group coherence
    -> 3C.5 deterministic cross-observation selection
    -> 3C.6 historical-series assembly and completeness
    -> 3C.7 transformation
    -> CalculationLineage
```

Later transformation lineage may use
`CalculationQualityFlag.correction_selected`, but that flag does not replace the
detailed binding proof.

Only represented option-domain relationships enter 3C.4b through 3C.4e.
`RateCurvePointObservation` and `DividendObservation` relationships bypass
that structural/evaluation layer and remain 3C.7 work.

### 13.8 Milestone 3C.3 binding-set temporal coherence

Milestone 3C.3 is the pure temporal-coherence layer for one explicit caller-
supplied set of already validated `SelectedFreshMarketDataBinding` objects:

```text
per-record eligibility
    -> 3C.3 binding-set temporal coherence
    -> 3C.4a auditable binding references
    -> 3C.4b through 3C.4e explicit relationship/group coherence
    -> 3C.5 deterministic cross-observation selection
    -> 3C.6 historical-series assembly and completeness
    -> 3C.7 market-data-to-research transformations and CalculationLineage
```

The 3C.4b-through-3C.4e step applies only to represented option-domain
relationships. Rate-curve-point and dividend-event relationship work bypasses
that step and belongs to 3C.7.

It assesses only whether the supplied bindings use compatible complete
freshness policies and contexts and whether the applicable selected records
fall within common cross-record effective-time and complete-source-observation-
time limits. It does not claim that the set is a complete calculation snapshot
or that any two records are intended economic counterparts. A temporally
coherent set may contain unrelated records.

#### Public API

Milestone 3C.3 added exactly these three public names, in this order:

```text
MarketDataSnapshotTimingReasonCode
MarketDataSnapshotTimingAssessment
assess_market_data_snapshot_timing
```

The preceding 39 `convexity_hunter.market_data` public names and their exact
order remained unchanged. The three names above append after those 39 names in
the displayed order. The current implemented public count is 42.

Milestone 3C.3 introduces no public status enum, snapshot policy,
relationship/group alias, registry, exception class, validated-success
snapshot class, or helper.

The reason-code enum has this exact declaration order and values:

```text
MarketDataSnapshotTimingReasonCode
    mixed_freshness_policy
    mixed_freshness_context
    effective_time_span_exceeded
    source_observation_span_exceeded
```

All applicable reasons are collected without duplicates and stored in enum
declaration order. There is no coherent reason code. An empty reason tuple is
the exact successful terminal result.

The planned function is:

```text
assess_market_data_snapshot_timing(
    bindings,
) -> MarketDataSnapshotTimingAssessment
```

It accepts no separate policy, context, threshold, snapshot time, reason,
metric, raw normalized record, correction sidecar, or freshness sidecar.

#### Immutable assessment artifact

The frozen assessment has exactly one stored dataclass field:

```text
MarketDataSnapshotTimingAssessment
    bindings: Tuple[SelectedFreshMarketDataBinding, ...]
```

It exposes exactly these derived public properties:

```text
is_temporally_coherent -> bool

reason_codes
    -> Tuple[MarketDataSnapshotTimingReasonCode, ...]

common_freshness_policy
    -> Optional[MarketDataFreshnessPolicy]

common_freshness_context
    -> Optional[FreshnessContext]

effective_time_span_seconds
    -> Optional[Decimal]

source_observation_span_seconds
    -> Optional[Decimal]
```

Status, reasons, common artifacts, and metrics are derived from the canonical
stored bindings, never independently supplied. No private dataclass field may
be added to store a derived sidecar or appear in public dataclass field
introspection. Direct construction therefore cannot forge calculated timing
facts.

Ordinary frozen-dataclass structural equality applies. Hashability is not
guaranteed because a nested binding may contain an already-valid unhashable
value. No custom hash or successful-hashing promise is introduced. The public
function and direct construction have identical successful semantics.

#### Input, duplicate, and canonicalization boundary

Both paths accept only an exact built-in `tuple` or `list`. Tuple/list
subclasses and every other container raise `TypeError`. Every element is
validated in caller order and must satisfy:

```text
type(binding) is SelectedFreshMarketDataBinding
```

Binding subclasses, raw normalized records, and unsupported objects raise
`TypeError`. The collection must be non-empty; empty input raises `ValueError`.

Duplicate selected record IDs and duplicate semantic observation keys each
raise `ValueError`:

```text
binding.selected_record.metadata.record_id
binding.semantic_observation_key
```

A repeated binding object is rejected by the duplicate selected-record-ID
rule; object identity is not a separate duplicate criterion. One 3C.3 binding
set contains at most one selected/fresh proof for one semantic observation
slot. Corrections for that slot must already have been resolved inside the
complete 3C.2 candidate group. Repeated normalized record types with different
semantic keys remain valid.

The stored tuple is sorted by this exact key:

```text
(
    binding.semantic_observation_key,
    binding.selected_record.metadata.record_id,
)
```

Caller order has no semantic meaning. Equivalent permutations produce
structurally equal assessments.

The sort uses ordinary deterministic Python string lexicographic ordering of
the already validated stored semantic keys and record IDs. It does not use
`locale.strxfrm`, locale-aware or platform-specific collation, case folding,
3C.3 Unicode normalization, or the process environment locale. 3C.3 does not
renormalize either string. A process-locale change cannot alter canonical
binding order.

After validation and sorting, `assessment.bindings` is an outer tuple
containing the exact original `SelectedFreshMarketDataBinding` objects supplied
by the caller. For each binding at its canonical index:

```python
assessment.bindings[canonical_index] is supplied_binding
```

List input is normalized only by creating this outer canonical tuple. The
implementation may reorder the supplied bindings but must not copy,
reconstruct, recompute, serialize and deserialize, or replace a binding with an
equal binding; unwrap and rebind its selected record; or replace any object
already retained by that binding. Nested binding-object identity is preserved.
The public function and direct construction have identical object-retention
semantics.

#### Binding trust boundary

Each exact `SelectedFreshMarketDataBinding` is treated as the previously
validated immutable 3C.2 proof. 3C.3 does not repeat semantic candidate-group
reconstruction, correction selection, freshness assessment, or 3C.2 sidecar-
equality validation. It may inspect every retained selected record, source
reference, freshness policy, freshness context, freshness assessment,
correction selection, and semantic observation key.

All cross-binding compatibility, canonicalization, spans, reasons, and outcome
properties are recomputed from the canonical bindings. No binding or nested
object is mutated.

#### Complete policy and context compatibility

Policy compatibility uses exact structural equality of the complete
`MarketDataFreshnessPolicy` objects. Policy ID/version equality alone is
insufficient. If every binding's policy is structurally equal,
`common_freshness_policy` returns the exact policy object belonging to the first
canonical binding. Otherwise it returns `None` and
`mixed_freshness_policy` applies. Structurally different policies with equal
IDs/versions are mixed.

When common, the returned policy is exactly:

```python
assessment.common_freshness_policy is assessment.bindings[0].freshness_policy
```

It is never a copy or reconstructed equal policy.

The assessment never chooses the strictest, loosest, first, average, or
pairwise threshold. It introduces no separate snapshot policy.

Context compatibility likewise uses exact structural equality of the complete
`FreshnessContext`, including `evaluation_at` and
`latest_completed_session_date`. If every context is structurally equal,
`common_freshness_context` returns the exact context object belonging to the
first canonical binding. Otherwise it returns `None` and
`mixed_freshness_context` applies.

When common, the returned context is exactly:

```python
assessment.common_freshness_context is assessment.bindings[0].freshness_context
```

It is never a copy or reconstructed equal context.

Different policies and contexts are valid 3C.2 inputs. They produce a valid
but temporally incoherent 3C.3 assessment rather than an exception.

#### Exact temporal-participation matrix

Seconds-based 3C.3 spans include exactly the five normalized record types whose
`metadata.effective_observed_at` participates in semantic observation identity:

```text
UnderlyingQuoteObservation
OptionQuoteObservation
OptionVolumeObservation
OptionImpliedVolatilityObservation
OptionGreeksObservation
```

These are the temporal participants. Exact selected-record type determines
participation; subclasses cannot occur through a valid 3C.2 binding.

The five date/reference-oriented types are excluded from both seconds-based
spans:

```text
OptionContractReference
OptionOpenInterestObservation
UnderlyingDailyBarObservation
RateCurvePointObservation
DividendObservation
```

Their individual freshness remains proven by 3C.2. Option-contract-reference
and open-interest relationship checks belong to 3C.4c through 3C.4e;
historical-bar relationships belong to 3C.6; and all rate-curve-point and
dividend-event relationship, identity, linkage, applicability, and economic-
use checks belong to 3C.7. No calendar date is converted to midnight or any
other synthetic datetime.

#### Exact timing metrics

For every temporal participant, the effective-time span uses:

```text
binding.selected_record.metadata.effective_observed_at
```

The metric is:

```text
max(effective_observed_at) - min(effective_observed_at)
```

Zero temporal participants produce `None`; one produces `Decimal("0")`; two or
more produce the exact nonnegative span.

The complete-source-observation span includes every
`SourceReference.observed_at` from every temporal participant's selected
record:

```text
max(all participating source observed_at values)
    - min(all participating source observed_at values)
```

Zero temporal participants produce `None`. Every participating record already
has at least one source. One total source produces `Decimal("0")`. All sources
from multi-source and system-composite records participate; there is no
system-composite exception. A single old participating source may exceed the
global limit, and an effective timestamp never hides it.

Both timedeltas are converted to exact `Decimal` seconds from integer
components:

```text
days * 86400
    + seconds
    + microseconds / 1_000_000
```

Binary-float `total_seconds()` is not the audit-critical calculation. Neither
metric truncates or rounds microseconds.

#### Threshold evaluation and outcome

The only governing threshold is:

```text
common_freshness_policy.maximum_cross_record_skew_seconds
```

Threshold reasons are evaluated only when both
`common_freshness_policy` and `common_freshness_context` are non-`None`. When
either policies or contexts are mixed, raw spans remain available and every
applicable mixed reason is returned, but neither exceeded reason is added
because there is no fully common policy/context basis for one timing decision.

With common artifacts:

```text
effective_time_span_seconds > maximum_cross_record_skew_seconds
    -> effective_time_span_exceeded

source_observation_span_seconds > maximum_cross_record_skew_seconds
    -> source_observation_span_exceeded
```

Equality with the configured maximum passes. A `None` span cannot produce an
exceeded reason.

Every applicable reason is returned in enum declaration order. The exact
outcome is:

```text
reason_codes == ()
    -> is_temporally_coherent is True

one or more reason codes
    -> is_temporally_coherent is False
```

An incoherent set returns an assessment rather than `None` or an exception.
Exceptions are limited to malformed collection input and prohibited
duplicates. The assessment expresses no attractiveness, recommendation, or
candidate-state meaning.

#### Exact validation precedence

The public function and direct constructor use this observable order:

**Phase A — top-level collection**

1. Require an exact built-in tuple or list.

**Phase B — element types**

2. Validate every element in caller order as an exact
   `SelectedFreshMarketDataBinding`.

**Phase C — collection values**

3. Reject empty input.
4. Reject duplicate selected record IDs.
5. Reject duplicate semantic observation keys.
6. Sort into the canonical tuple.

**Phase D — compatibility and metrics**

7. Derive the common structural policy or `None`.
8. Derive the common structural context or `None`.
9. Identify temporal participants by exact selected-record type.
10. Calculate the effective-time span.
11. Calculate the complete-source-observation span.

**Phase E — reasons and outcome**

12. Add the mixed-policy reason when applicable.
13. Add the mixed-context reason when applicable.
14. Only when both common artifacts exist, evaluate both thresholds.
15. Normalize reasons into enum declaration order.
16. Derive the Boolean outcome.

Malformed-input exception precedence completes before compatibility or metric
work. Multiple valid incoherence conditions are collected rather than short-
circuited.

#### Explicit exclusions and purity

Milestone 3C.3 does not evaluate underlying or option-contract relationships,
session-date relationships, market-phase, quote-scope, or venue compatibility,
quote/IV/Greek relationships, analytics methodology compatibility, analytics-
to-rate or analytics-to-dividend linkage, activity/reference applicability,
rate-tenor or dividend-event applicability, latest or preferred observations,
missing records, calculation completeness, historical-series completeness,
economic formulas, pricing, research evidence, `CandidateResearchRecord`,
`CalculationLineage`, or candidate states. Analytics-to-rate and analytics-to-
dividend linkage, rate identity and tenor applicability, and dividend-event
identity, status, and applicability belong to 3C.7.

Those boundaries are dependency-ordered as follows:

- 3C.4a defines only portable references. 3C.4b through 3C.4e receive explicit
  relationship or grouping requests before deciding
  which records are intended counterparts. They define underlying/option,
  session, phase, scope, venue, quote/analytics methodology, activity,
  reference, and contract compatibility for the represented option-domain
  observations. Their APIs are not defined by 3C.3.
- 3C.5 performs deterministic selection among different semantic
  observations.
- 3C.6 assembles and proves historical-series completeness.
- 3C.7 performs economic transformation, pricing where authorized, research-
  evidence construction, and `CalculationLineage` construction. It also owns
  every analytics-to-rate and analytics-to-dividend linkage, rate-curve-point
  identity and tenor applicability, dividend-event identity, status, and
  applicability, and every economic use of rates or dividends.

The assessment preserves all nested source and normalization flags but adds no
stricter delayed, indicative, halted, or other quality rule. Those conditions
were already assessed under each binding's complete freshness policy. No 3C.3
timing reason represents source quality.

The record and function are pure. They do not mutate inputs; inspect a wall
clock or exchange calendar; read files or environment variables; depend on
locale; use randomness; access a network, provider SDK, LLM, or process-global
registry; or perform hidden selection. Canonical string ordering, exact
`Decimal` timing conversion, reason ordering, and structural equality are
locale-independent. Decimal separators are never locale-derived, enum reasons
are never locale-sorted, and no string is formatted or parsed through a
locale-sensitive function.

#### Future test expectations

Future fixed synthetic tests cover:

- exact tuple/list containers and container-subclass rejection;
- exact binding elements and binding-subclass rejection;
- empty input, duplicate selected IDs, and duplicate semantic keys, including a
  simultaneous-defect regression that deterministically proves duplicate
  selected-record-ID `ValueError` occurs before semantic-key duplicate
  validation without creating a public exception subclass or broad public
  error-message contract;
- canonical order, input-order-independent equality, and ordinary frozen
  behavior without a hashability promise;
- exact supplied-binding identity retention after canonical reordering for
  tuple input and for list input whose outer container becomes a tuple;
- structurally equal public-function and direct-construction results that retain
  the same supplied binding objects across different caller orders;
- exact common-artifact identity with the first canonical binding's policy and
  context, with no copied or reconstructed equal object;
- full structural policy equality, including equal ID/version with different
  policy fields;
- full structural context equality, including different evaluation times and
  latest-completed-session dates;
- zero, one, and multiple temporal participants;
- parameterized or subtest coverage independently proving that each of
  `UnderlyingQuoteObservation`, `OptionQuoteObservation`,
  `OptionVolumeObservation`, `OptionImpliedVolatilityObservation`, and
  `OptionGreeksObservation` contributes its effective time and every selected-
  record source time, has a one-binding effective span of `Decimal("0")`, and
  is not treated as excluded;
- exclusion coverage independently proving that each of
  `OptionContractReference`, `OptionOpenInterestObservation`,
  `UnderlyingDailyBarObservation`, `RateCurvePointObservation`, and
  `DividendObservation` contributes to neither seconds-based metric;
- effective and source spans below, equal to, and above the threshold;
- microsecond-exact `Decimal` calculation, one old source, and complete multi-
  source/system-composite participation;
- a one-binding, multi-source participant whose within-record source range
  produces a nonzero global source span;
- mixed policy/context results with raw metrics but skipped threshold reasons;
- multiple simultaneous reasons in declaration order;
- valid incoherent assessments versus invalid-input exceptions;
- locale-independence coverage for canonical binding order, reason order,
  `Decimal` timing values, and structural equality, using restored available
  locale settings or a portable controlled probe that does not require any
  non-default locale installation and never manipulates locale in production;
- no mutation or wall-clock, network, filesystem, environment, locale,
  randomness, provider, or LLM dependency; and
- no relationship, selection, completeness, calculation, pricing, research,
  or lineage leakage.

### 13.9 Milestone 3C.4a auditable binding-reference foundation

The broad standalone Milestone 3C.4 relationship/group-coherence contract was
preflighted and found not yet viable. Relationship group kinds, roles,
cardinalities, temporal-block behavior, assessment architecture, structured
issue evidence, and phase/scope/venue compatibility remain unresolved.
Milestone 3C.4a therefore extracts only the independently determined portable
binding-reference foundation:

```text
portable binding reference
    -> exact resolution inside one existing 3C.3 timing assessment
    -> exact retained 3C.2 binding object
```

3C.4a does exactly four things:

1. represents one portable reference to one selected/fresh binding;
2. constructs that reference from one exact 3C.2 binding;
3. resolves that reference inside one exact 3C.3 timing assessment; and
4. returns the exact binding object retained by that assessment.

A 3C.4a reference is a locator, not proof that any relationship is valid. This
sub-unit does not declare relationships, groups, or roles; evaluate relationship
or timing coherence; select observations or groups; require missing roles;
prove completeness; assemble historical series; apply rate or dividend
applicability; perform calculations or pricing; construct research evidence or
`CalculationLineage`; or produce candidate states.

#### Public API

Milestone 3C.4a plans exactly these three public additions, in this order:

```text
MarketDataBindingReference
market_data_binding_reference
resolve_market_data_binding_reference
```

The existing 42 `convexity_hunter.market_data` public names and their exact
order remain unchanged. The three names above append after those 42 names in
the displayed order. The current implemented public count is 42. The planned
post-3C.4a implementation count is 45.

3C.4a introduces no public group-kind enum, role enum, relationship request,
relationship group, reason-code enum, status enum, issue record, relationship
assessment, success-only artifact, registry, exception class, or compatibility
policy.

#### Immutable reference artifact

The planned frozen record has exactly these two stored dataclass fields, in
this order:

```python
@dataclass(frozen=True)
class MarketDataBindingReference:
    semantic_observation_key: str
    selected_record_id: str
```

No additional field stores a binding object, timing assessment, canonical
index, record type, provider, policy, context, correction selection, freshness
assessment, relationship role, or group ID. The record is a portable value
artifact rather than a Python object-identity reference. Ordinary frozen-
dataclass structural equality applies. No custom hash is planned.

For both strings, the constructor requires exact built-in `str` and applies
exactly this normalization:

```python
normalized = value.strip()
```

This is Python's no-argument built-in `str.strip()` behavior. No explicit
character set is supplied: every leading and trailing character recognized by
Python as whitespace is removed, while internal characters remain unchanged.
An empty normalized result raises `ValueError`; otherwise the normalized value
is stored. Case and Unicode code points remaining after stripping are
preserved. No case folding, Unicode normalization, parsing, or locale-aware
transformation occurs.

The exact observable validation order is:

```text
1. semantic_observation_key exact built-in str type
2. selected_record_id exact built-in str type
3. semantic_observation_key nonempty after `value.strip()`
4. selected_record_id nonempty after `value.strip()`
5. store both stripped strings
```

String subclasses and every non-string value raise `TypeError`. Direct
construction validates only the two string values and does not prove that
either value belongs to a real binding. A reference becomes authoritative only
when it resolves inside a supplied 3C.3 timing assessment.

#### Factory function

The planned factory is:

```python
market_data_binding_reference(
    binding,
) -> MarketDataBindingReference
```

It requires:

```python
type(binding) is SelectedFreshMarketDataBinding
```

A binding subclass, raw normalized record, timing assessment, binding
reference, or any unsupported object raises `TypeError`. After that exact-type
check, the function derives only:

```python
binding.semantic_observation_key
binding.selected_record.metadata.record_id
```

It does not recompute semantic identity, reconstruct correction or freshness
evidence, mutate the binding, or copy the binding. It returns a new value
reference. The exact equivalence is:

```python
market_data_binding_reference(binding)
    == MarketDataBindingReference(
        semantic_observation_key=binding.semantic_observation_key,
        selected_record_id=binding.selected_record.metadata.record_id,
    )
```

The factory requires no timing assessment and introduces no hidden
authorization beyond the direct reference constructor.

Its exact validation phases are:

```text
1. exact SelectedFreshMarketDataBinding type
2. derive the two retained strings
3. construct and return the reference
```

#### Resolver function

The planned resolver is:

```python
resolve_market_data_binding_reference(
    reference,
    timing_assessment,
) -> SelectedFreshMarketDataBinding
```

Its exact successful behavior is:

1. require `type(reference) is MarketDataBindingReference`;
2. require `type(timing_assessment) is MarketDataSnapshotTimingAssessment`;
3. search only `timing_assessment.bindings` in its already-canonical order;
4. match both reference fields by exact stored-string equality;
5. require exactly one complete-pair match; and
6. return the exact retained binding object at the matching assessment index.

The complete-pair predicate is:

```python
binding.semantic_observation_key
    == reference.semantic_observation_key
and binding.selected_record.metadata.record_id
    == reference.selected_record_id
```

Successful resolution guarantees:

```python
resolved_binding is timing_assessment.bindings[index]
```

The resolver never resolves by semantic key alone or record ID alone, falls
back from one field to the other, uses a canonical index as a reference,
chooses a close or latest match, parses the semantic key, recomputes semantic
identity, reconstructs a binding, copies a binding, or resorts the assessment.
A cross-paired reference containing one binding's semantic key and another
binding's record ID raises `ValueError` unless that exact complete pair
independently exists in the supplied target assessment. Because a valid 3C.3
assessment has unique semantic keys and unique selected record IDs, such a
cross-pair normally has no match.

The exact resolver validation order is:

```text
1. exact MarketDataBindingReference type
2. exact MarketDataSnapshotTimingAssessment type
3. exact complete-pair resolution
4. return the exact retained binding
```

The resolver does not access `timing_assessment.bindings` before both public
argument types pass.

#### Resolution failures

Malformed public argument types raise `TypeError`. A well-formed reference that
does not resolve to exactly one complete pair in the supplied assessment raises
`ValueError`. Resolution failure includes an unknown semantic key, unknown
selected record ID, stale reference, forged reference, cross-paired values
without an independently matching complete pair, or a reference of any origin
whose complete pair is absent from the supplied target assessment.

3C.4a introduces no public exception class or reason enum. Full private error-
message text is not a public contract; tests may distinguish the exception
category without locking implementation-specific wording.

#### Trust and assessment-membership boundary

`MarketDataBindingReference` is only a two-string portable locator. Direct
construction does not prove that a binding exists. The exact supplied
`MarketDataSnapshotTimingAssessment` is the authoritative binding universe.
Successful resolution proves only that the exact pair occurs in that supplied
assessment and returns the exact already-validated 3C.2 binding retained by
the 3C.3 assessment.

3C.4a trusts the already-valid exact timing assessment. It does not repeat
3C.2 semantic candidate-group reconstruction, correction selection, selected-
record resolution, or freshness validation. It does not repeat 3C.3 duplicate,
canonicalization, policy, context, metric, reason, or timing validation.

A reference carries no assessment origin or assessment identity. Resolution
depends only on whether its complete `(semantic_observation_key,
selected_record_id)` pair exists in the timing assessment explicitly supplied
as the resolver's target. A reference created from a binding in Assessment A
resolves successfully in Assessment B when Assessment B contains the same
complete pair, and the resolver returns the exact matching binding retained by
Assessment B. It raises `ValueError` in Assessment B when Assessment B does not
contain that complete pair.

The same reference may therefore resolve successfully in multiple assessments.
A reference is not foreign in any observable sense merely because it was
constructed using a binding retained elsewhere. No assessment ID, fingerprint,
object identity, version, registry entry, or hidden origin metadata exists, and
the resolver must not attempt to determine where a reference was created.
Target-assessment complete-pair membership is the sole resolution criterion.
No process-global registry, provider lookup, repository lookup, filesystem
lookup, cache, or network lookup exists.

A valid 3C.3 timing assessment already guarantees unique selected record IDs
and unique semantic observation keys within its canonical binding set. The
composite pair remains mandatory because it carries semantic context, provides
stronger audit evidence, detects cross-paired or stale references, and remains
suitable for later serialized group requests. Neither field is claimed to be
globally unique outside the supplied assessment.

#### Temporal-coherence independence

The resolver accepts an exact valid timing assessment whether it is temporally
coherent or temporally incoherent. Reference resolution is structural and must
not inspect:

```text
is_temporally_coherent
reason_codes
common_freshness_policy
common_freshness_context
effective_time_span_seconds
source_observation_span_seconds
timing thresholds
```

Later relationship work will decide whether temporal incoherence blocks
relationship evaluation. 3C.4a neither makes nor pre-empts that decision.

#### Canonical behavior, locale independence, and purity

Construction and resolution use exact stored-string equality. They prohibit
`locale.strxfrm`, locale-aware comparison, case folding, lowercasing,
uppercasing, Unicode renormalization, platform collation, fuzzy matching,
prefix matching, and substring matching. Resolution follows the canonical
order already retained by `timing_assessment.bindings` and does not resort or
mutate it. Results do not depend on caller locale, environment locale,
platform, or process-global state.

Both public functions are provider neutral, clock free, calendar free,
filesystem free, environment free, network free, locale independent,
randomness free, LLM free, registry free, and non-mutating. They do not inspect
or alter source URIs, provider IDs, provider symbols, listing MIC as a fallback,
relationship fields, or economic fields.

#### Explicit exclusions

3C.4a defines no semantics for same-underlying, same-option-contract, same-
session, market-phase, quote-scope, quote-venue, analytics-methodology,
volume/open-interest, contract-reference, rate, dividend, or historical-series
relationships. It defines no group kinds, roles, role cardinalities, required
roles, relationship findings, relationship reason order, relationship outcome,
upstream temporal blocking, or validated coherent groups. These are
intentionally deferred.

#### Revised dependency decomposition

The completed broad 3C.4 preflight establishes this revised order:

```text
3C.2 selected/fresh binding
    -> 3C.3 binding-set temporal coherence
    -> 3C.4a auditable binding references
    -> 3C.4b explicit relationship/group request representation
    -> 3C.4c exact identity and comparable-session coherence
    -> 3C.4d quote phase/scope/venue compatibility
    -> 3C.4e analytics/activity/contract-reference coherence
    -> 3C.5 deterministic cross-observation/group selection
    -> 3C.6 historical-series assembly and completeness
    -> 3C.7 transformations, pricing where authorized,
       research evidence, and CalculationLineage
```

The 3C.4a contract is defined here. Section 13.10 defines the approved,
implemented, and committed 3C.4b structural request contract. Section 13.11
defines the locally implemented 3C.4c contract pending independent review.
APIs for 3C.4d and 3C.4e remain undefined.
Every rate/dividend relationship, identity, linkage, applicability, and
economic use remains 3C.7 work. Historical-series membership and completeness
remain 3C.6 work.

#### Future test expectations

Future fixed synthetic 3C.4a tests cover:

- the unchanged existing 42 public names, exact three-name append order,
  planned total of 45, public signatures, exact two-field dataclass
  introspection, and absence of unauthorized relationship APIs;
- exact-string constructor boundaries, string-subclass and non-string
  rejection, validation precedence, no-argument `str.strip()` behavior, ASCII
  surrounding whitespace, non-ASCII Python-recognized surrounding whitespace,
  internal whitespace preservation, whitespace-only rejection, case and
  Unicode preservation, absence of case folding or Unicode normalization,
  field order, frozen behavior, and structural equality;
- exact binding factory success; rejection of binding subclasses, raw records,
  timing assessments, references, and unsupported objects; factory/direct
  structural equality; and no binding mutation;
- exact reference and timing-assessment resolver success; rejection of
  reference and assessment subclasses; argument precedence; unknown semantic
  key, unknown record ID, both unknown, stale and forged pairs, and cross-paired
  values without an independent exact-pair match; a foreign-origin reference
  whose complete pair is present returning the exact retained binding from the
  supplied target assessment; a foreign-origin reference whose complete pair
  is absent raising `ValueError`; exact retained binding identity; and unchanged
  nested object identity;
- successful structural resolution for both coherent and temporally incoherent
  timing assessments, with a controlled regression proving that no derived
  timing property is accessed;
- canonical assessment order independence of the reference value, no resolver
  resorting or mutation, and absence of locale-sensitive comparison; and
- no clock, calendar, network, filesystem, environment, randomness, provider,
  LLM, registry, selection, relationship, completeness, calculation, pricing,
  research, or lineage dependency.

### 13.10 Milestone 3C.4b explicit relationship/group request representation

The A-level specification preflight and targeted specification reviews found
that the standalone Milestone 3C.4b structural contract is viable. This section
defines the approved and committed Milestone 3C.4b contract. Its implementation
is complete and committed.

3C.4b represents explicit caller-declared relationship intent. It answers:

```text
Which observations does the caller intend to compare, and in which roles?
```

It does not answer whether those observations are compatible. It does exactly
the following:

1. identifies one explicit, versioned relationship-group kind;
2. assigns portable 3C.4a references to explicit roles;
3. enforces the fixed structural grammar and cardinalities of that kind;
4. canonicalizes members and groups deterministically; and
5. rejects malformed or structurally contradictory requests.

Role allowance and cardinality are structural request grammar. Facts learned
only after reference resolution belong to 3C.4c through 3C.4e. Structural
request validity makes no claim that later reference resolution or relationship
evaluation will succeed.

3C.4b does not resolve references; check resolved record types, underlying or
option-contract identity, comparable sessions or dates, market phase, quote
scope, venue, analytics methodology, activity coherence, contract-reference
coherence, or timing coherence; produce findings, issues, reasons, statuses, or
outcomes; select or rank observations or groups; prove historical
completeness; or perform pricing or other transformations. It does not
represent or evaluate `RateCurvePointObservation` or `DividendObservation`
relationships, identity, linkage, applicability, or economic use, and it does
not construct evidence or `CalculationLineage`.

#### Public API

3C.4b added exactly these five public additions, in this order:

```text
MarketDataRelationshipGroupKind
MarketDataRelationshipRole
MarketDataRelationshipGroupMember
MarketDataRelationshipGroup
MarketDataRelationshipRequest
```

The unchanged existing 45 `convexity_hunter.market_data` public names remain
the implemented prefix. The five names append after that prefix for the
implemented post-3C.4b count of 50.

No public function was added. 3C.4b introduces no public policy, status,
reason-code enum, issue record, assessment, resolver, exception class,
registry, alias, serializer, or 3C.4c-or-later artifact.

#### Versioned relationship-group kinds

The closed enum has this exact declaration order and exact values:

```python
class MarketDataRelationshipGroupKind(str, Enum):
    UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1 = (
        "underlying_option_quote_snapshot_v0.1"
    )
    OPTION_QUOTE_ANALYTICS_V0_1 = "option_quote_analytics_v0.1"
    OPTION_ACTIVITY_V0_1 = "option_activity_v0.1"
    OPTION_CONTRACT_REFERENCE_V0_1 = "option_contract_reference_v0.1"
```

The kind is explicit, provider neutral, domain-named rather than milestone-
named, and closed for v0.1. It is never inferred from members or resolved
records. Public construction requires its exact type; subclasses, foreign
Enums, strings, and every other value are rejected.

The suffix embedded in each value is the group-definition version. Adding or
removing roles, changing cardinality, or changing a group's meaning requires a
new versioned group-kind value. 3C.4b adds no separate group version field,
group-kind record, global request version, or evaluation-policy version. Later
3C.4c through 3C.4e evaluation-policy versions are separate from group-
definition versioning.

#### Relationship roles

The closed global role enum has this exact declaration order and exact
values:

```python
class MarketDataRelationshipRole(str, Enum):
    UNDERLYING_QUOTE = "underlying_quote"
    OPTION_QUOTE = "option_quote"
    OPTION_IMPLIED_VOLATILITY = "option_implied_volatility"
    OPTION_GREEKS = "option_greeks"
    OPTION_VOLUME = "option_volume"
    OPTION_OPEN_INTEREST = "option_open_interest"
    OPTION_CONTRACT_REFERENCE = "option_contract_reference"
```

Roles are global, explicit, provider neutral, exact-type validated, and never
inferred from a reference or resolved record. A role declares caller intent;
it does not prove that the reference later resolves to an expected record type.

No role is added for `UnderlyingDailyBarObservation`,
`RateCurvePointObservation`, or `DividendObservation`.
`UnderlyingDailyBarObservation` relationships remain 3C.6 work.
`RateCurvePointObservation` and `DividendObservation` relationships, identity,
linkage, applicability, and economic use remain 3C.7 work.

#### Immutable group member

The member is exactly:

```python
@dataclass(frozen=True)
class MarketDataRelationshipGroupMember:
    role: MarketDataRelationshipRole
    reference: MarketDataBindingReference
```

The stored dataclass field order is exactly `role`, then `reference`. Public
construction requires:

```python
type(role) is MarketDataRelationshipRole
type(reference) is MarketDataBindingReference
```

The exact validation order is:

```text
1. role exact type
2. reference exact type
3. store
```

The member is frozen and uses ordinary dataclass structural equality. It has
no custom equality or custom hash. It has no member ID. One member contains
exactly one role and one portable reference.

A member cannot contain a raw normalized record,
`SelectedFreshMarketDataBinding`, `MarketDataSnapshotTimingAssessment`, a
resolved binding object, multiple references, metadata, a description, or
provider fields.

#### Immutable relationship group

The group is exactly:

```python
@dataclass(frozen=True)
class MarketDataRelationshipGroup:
    group_id: str
    group_kind: MarketDataRelationshipGroupKind
    members: Tuple[MarketDataRelationshipGroupMember, ...]
```

The stored dataclass field order is exactly `group_id`, `group_kind`, then
`members`. No additional field is stored.

`group_id` requires exact built-in `str`. It is normalized only by Python's
no-argument `str.strip()`:

```python
normalized_group_id = group_id.strip()
```

An empty normalized result raises `ValueError`. Case, internal characters,
remaining Unicode code points, and canonically distinct Unicode sequences are
preserved. Construction performs no case folding, Unicode normalization,
locale transformation, parsing, automatic generation, or derived
fingerprinting. A group ID claims no global uniqueness. It is a caller-
declared group-instance identity and participates in ordinary dataclass
equality.

`members` accepts only an exact built-in tuple or list. Tuple and list
subclasses and all other iterables raise `TypeError`. Every element must have
exact type `MarketDataRelationshipGroupMember`; member subclasses and every
other element raise `TypeError`. After complete validation, the collection is
stored as an immutable canonical tuple. At least one member is required.

#### Exact group grammar and cardinality

Callers do not declare cardinality policies. The versioned group-kind contract
defines the complete v0.1 grammar. No separate cardinality-policy artifact is
introduced, and no role is repeatable in v0.1.

`OPTION_ACTIVITY_V0_1` declares one option-volume observation and one option-
open-interest observation as intended activity counterparts, with an optional
option quote that supplies declared quote/activity context. Allowing the
optional role expresses caller intent only. 3C.4b does not resolve the
reference or verify that it identifies an option quote.

| Group kind | Role | Minimum | Maximum |
|---|---|---:|---:|
| `UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1` | `UNDERLYING_QUOTE` | 1 | 1 |
| `UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1` | `OPTION_QUOTE` | 1 | 1 |
| `OPTION_QUOTE_ANALYTICS_V0_1` | `OPTION_QUOTE` | 1 | 1 |
| `OPTION_QUOTE_ANALYTICS_V0_1` | `OPTION_IMPLIED_VOLATILITY` | 0 | 1 |
| `OPTION_QUOTE_ANALYTICS_V0_1` | `OPTION_GREEKS` | 0 | 1 |
| `OPTION_ACTIVITY_V0_1` | `OPTION_QUOTE` | 0 | 1 |
| `OPTION_ACTIVITY_V0_1` | `OPTION_VOLUME` | 1 | 1 |
| `OPTION_ACTIVITY_V0_1` | `OPTION_OPEN_INTEREST` | 1 | 1 |
| `OPTION_CONTRACT_REFERENCE_V0_1` | `OPTION_CONTRACT_REFERENCE` | 1 | 1 |
| `OPTION_CONTRACT_REFERENCE_V0_1` | `OPTION_QUOTE` | 0 | 1 |
| `OPTION_CONTRACT_REFERENCE_V0_1` | `OPTION_IMPLIED_VOLATILITY` | 0 | 1 |
| `OPTION_CONTRACT_REFERENCE_V0_1` | `OPTION_GREEKS` | 0 | 1 |
| `OPTION_CONTRACT_REFERENCE_V0_1` | `OPTION_VOLUME` | 0 | 1 |
| `OPTION_CONTRACT_REFERENCE_V0_1` | `OPTION_OPEN_INTEREST` | 0 | 1 |

Every role not listed for a group kind is prohibited. In particular,
`UNDERLYING_QUOTE` is prohibited in `OPTION_CONTRACT_REFERENCE_V0_1`.

Two aggregate rules complete the grammar:

- `OPTION_QUOTE_ANALYTICS_V0_1` requires at least one of
  `OPTION_IMPLIED_VOLATILITY` or `OPTION_GREEKS`.
- `OPTION_CONTRACT_REFERENCE_V0_1` requires at least one non-reference role.

#### Complete-reference duplication and reuse

Within one group, the same complete `MarketDataBindingReference` may appear at
most once regardless of role. Duplicate identity is exactly:

```python
(
    reference.semantic_observation_key,
    reference.selected_record_id,
)
```

Therefore:

```text
same role + same complete reference -> duplicate ValueError
different roles + same complete reference -> duplicate ValueError
same role + distinct references -> maximum-one cardinality ValueError
```

The cross-role prohibition is structural: one observation cannot be declared
as two different roles inside one relationship group. Duplicate detection
never uses Python object identity, semantic observation key alone, or selected
record ID alone. Independently constructed but structurally equal references
are duplicates.

The following remain structurally distinct complete references and are subject
to the separate role-cardinality rules:

```text
same semantic key + different selected record IDs
different semantic keys + same selected record ID
```

The same complete reference may appear in different groups. Identical group
contents under distinct group IDs are also allowed.

#### Canonical member order

Caller member order is discarded. The exact member sort key is:

```python
(
    role_declaration_index,
    reference.semantic_observation_key,
    reference.selected_record_id,
)
```

`role_declaration_index` uses `MarketDataRelationshipRole` declaration order.
Strings use ordinary Python code-point ordering. Canonicalization performs no
locale collation, Unicode normalization, case folding, semantic-key parsing,
set iteration, or object-identity comparison. The stored canonical tuple
determines ordinary group structural equality.

#### Exact group validation precedence

The observable group validation order is exactly:

```text
1. group_id exact built-in str type
2. group_kind exact MarketDataRelationshipGroupKind type
3. members exact built-in tuple/list container type
4. every member exact type, checked in caller order
5. normalize group_id using no-argument str.strip()
6. reject empty normalized group_id
7. reject empty members
8. reject repeated complete references, checked in caller order
9. reject roles prohibited for the declared group kind
10. validate per-role minimum and maximum counts in role declaration order
11. validate group-kind aggregate constraints
12. canonicalize members
13. store normalized group_id and canonical member tuple
```

No normalized value is partially stored and no input is mutated before all
validation passes. Representative simultaneous defects resolve as follows:

```text
empty group ID + invalid member element
    -> member TypeError wins

duplicate complete reference + role prohibited for kind
    -> duplicate ValueError wins

missing required role + excessive optional role
    -> first failing role in MarketDataRelationshipRole declaration order wins
```

#### Immutable top-level request

The request is exactly:

```python
@dataclass(frozen=True)
class MarketDataRelationshipRequest:
    groups: Tuple[MarketDataRelationshipGroup, ...]
```

Its only stored field is `groups`. There is no request ID, and no `request_id`
field is introduced. It also stores no
priority, evaluation order, fallback, success criteria, temporal policy,
selection preference, description, metadata, caller identity, or timestamp.

`groups` accepts only an exact built-in tuple or list. Tuple/list subclasses
and all other containers raise `TypeError`. Every element must have exact type
`MarketDataRelationshipGroup`; group subclasses and all other elements raise
`TypeError`. At least one group is required. Normalized group IDs must be
unique within the request. The same complete reference may appear in several
different groups.

Caller group order is discarded. Because normalized group IDs are unique, the
exact request canonical sort key is only:

```python
group.group_id
```

No unreachable group-kind or member-content tie breaker is added. Sorting uses
ordinary Python code-point ordering. The validated collection is stored as an
immutable canonical tuple, so request equality is caller-order independent.
Two structurally identical groups with different IDs remain distinct and are
allowed.

The observable request validation order is exactly:

```text
1. groups exact built-in tuple/list container type
2. every group exact type, checked in caller order
3. reject empty groups
4. reject duplicate normalized group IDs, checked in caller order
5. canonicalize groups by group_id
6. store canonical group tuple
```

A duplicate group ID therefore raises `ValueError` before noncanonical caller
order is sorted.

#### Structural versus semantic validation boundary

3C.4b validates only:

- known exact group-kind and role types;
- role allowance for the declared group kind;
- required and optional role counts and aggregate structural requirements;
- exact member and reference artifact types;
- nonempty member and group collections;
- complete-reference duplication;
- normalized group-ID validity and request-local group-ID uniqueness; and
- canonical tuple order.

It does not validate whether a reference resolves; whether two references
resolve to the same binding; resolved record type; underlying or option-
contract equality; comparable sessions or dates; phase, scope, or venue;
analytics methodology; activity coherence; contract-reference terms; or
timing coherence.

#### Resolution and temporal boundaries

3C.4b introduces no resolver, resolve-all helper, materialized group, success-
only artifact, or function accepting `MarketDataSnapshotTimingAssessment`.
Later evaluators receive a validated group and an exact timing assessment,
call `resolve_market_data_binding_reference` for each canonical member, and
perform their own separately contracted semantic evaluation. 3C.4b does not
duplicate 3C.4a.

A group or request is constructed without any timing assessment. It may later
be used with a temporally coherent or incoherent assessment. 3C.4b does not
store or inspect `is_temporally_coherent`, timing reason codes, freshness
policy or context, timing metrics, or timing thresholds. Temporal blocking
remains an unresolved later evaluation decision.

#### Non-normative map to later relationship evaluation

This dependency map does not define compatibility matrices, findings, reasons,
statuses, outcomes, or temporal-blocking behavior:

| Group kind | 3C.4c | 3C.4d | 3C.4e |
|---|---|---|---|
| Underlying/option quote snapshot | underlying identity and comparable session | phase, scope, and venue compatibility | none |
| Option quote analytics | option-contract identity and comparable session | none defined by 3C.4b | quote/IV/Greeks alignment and methodology coherence |
| Option activity | exact option-contract identity and comparable session/date relationships among volume, open interest, and the optional option quote when present | none | volume/open-interest coherence and, when the optional quote is present, quote/activity relationship and activity applicability |
| Option contract reference | exact option-contract identity | none | reference-term coherence against each option observation |

Section 13.11 defines the locally implemented 3C.4c result API. Milestones
3C.4d and 3C.4e remain undefined and unimplemented. The table expresses
dependency ownership; the 3C.4b artifacts themselves introduce no result API.

#### Later milestone exclusions

- 3C.5 owns cross-group ranking, selection, fallback, and priorities.
- 3C.6 owns historical-series membership, ordering, lookback, and
  completeness.
- 3C.7 owns analytics-to-rate and analytics-to-dividend linkage; rate-curve-
  point identity and tenor applicability; dividend-event identity, status, and
  applicability; every economic use of rates or dividends; transformations;
  pricing; evidence; and `CalculationLineage`.

No 3C.4b field exists solely for a later milestone.

#### Portability, equality, and purity

Portability means frozen value artifacts, closed enums, normalized strings,
immutable canonical tuples, portable `MarketDataBindingReference` values, and
ordinary dataclass equality. No binding or timing-assessment object is
retained. No JSON serializer is introduced. No free-text rationale or metadata
participates in equality.

Construction is provider neutral, network free, filesystem free, environment
free, clock free, calendar free, locale independent, randomness free, LLM
free, registry free, process-global-state free, pure, and non-mutating.

#### Failure taxonomy

3C.4b uses only `TypeError` and `ValueError`.

`TypeError` covers a wrong exact scalar type, enum subclass or foreign Enum,
reference/member/group subclass, wrong collection type, collection subclass,
or invalid collection element type.

`ValueError` covers an empty normalized group ID, empty group or request,
duplicate complete reference, duplicate group ID, role prohibited for a group
kind, minimum or maximum cardinality violation, or aggregate structural-
constraint violation.

Reference-resolution and semantic-incompatibility errors do not occur during
3C.4b construction. No public exception, reason enum, issue record, status, or
assessment is introduced. Full private error-message text is not public.
Future tests may require narrow field or constraint fragments only when needed
to prove validation precedence.

#### Fixed synthetic examples

The semantic keys below are intentionally synthetic opaque strings. 3C.4b
does not parse or authenticate them.

```python
underlying_quote_reference = MarketDataBindingReference(
    "semantic-observation-v0.1:synthetic-spy-underlying-quote",
    "synthetic-underlying-quote-001",
)
option_quote_reference = MarketDataBindingReference(
    "semantic-observation-v0.1:synthetic-spy-option-quote",
    "synthetic-option-quote-001",
)

snapshot_group = MarketDataRelationshipGroup(
    group_id="spy-quote-snapshot",
    group_kind=(
        MarketDataRelationshipGroupKind
        .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
    ),
    members=(
        MarketDataRelationshipGroupMember(
            MarketDataRelationshipRole.OPTION_QUOTE,
            option_quote_reference,
        ),
        MarketDataRelationshipGroupMember(
            MarketDataRelationshipRole.UNDERLYING_QUOTE,
            underlying_quote_reference,
        ),
    ),
)

# Stored member order is UNDERLYING_QUOTE, then OPTION_QUOTE.
```

```python
iv_reference = MarketDataBindingReference(
    "semantic-observation-v0.1:synthetic-spy-option-iv",
    "synthetic-option-iv-001",
)
greeks_reference = MarketDataBindingReference(
    "semantic-observation-v0.1:synthetic-spy-option-greeks",
    "synthetic-option-greeks-001",
)

analytics_group = MarketDataRelationshipGroup(
    group_id="spy-option-analytics",
    group_kind=MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
    members=(
        MarketDataRelationshipGroupMember(
            MarketDataRelationshipRole.OPTION_GREEKS,
            greeks_reference,
        ),
        MarketDataRelationshipGroupMember(
            MarketDataRelationshipRole.OPTION_QUOTE,
            option_quote_reference,
        ),
        MarketDataRelationshipGroupMember(
            MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
            iv_reference,
        ),
    ),
)

# Stored member order is OPTION_QUOTE, OPTION_IMPLIED_VOLATILITY,
# then OPTION_GREEKS.
```

```python
request = MarketDataRelationshipRequest((snapshot_group, analytics_group))

# The caller supplied noncanonical group order. Stored group order is
# analytics_group, then snapshot_group, sorted only by normalized group_id.
```

#### Test expectations

Implemented fixed synthetic tests cover:

- the unchanged original 45-name public prefix, exact five-name append order,
  implemented total of 50, and absence of unauthorized public functions or later
  result APIs;
- exact enum declaration order and values; exact dataclass field order;
  frozen behavior and ordinary structural equality;
- exact enum, reference, member, and group types; subclass and foreign-Enum
  rejection; exact tuple/list acceptance; tuple/list-subclass rejection; and
  invalid element types;
- group-ID no-argument `str.strip()` behavior, ASCII and non-ASCII surrounding
  whitespace, whitespace-only rejection, case and Unicode preservation, and
  absence of Unicode normalization;
- empty group and request; every allowed and prohibited role for each kind;
  every minimum and maximum cardinality; and both aggregate constraints;
- valid activity groups without `OPTION_QUOTE` and with exactly one
  `OPTION_QUOTE`; two option-quote members producing cardinality `ValueError`;
  missing `OPTION_VOLUME` and missing `OPTION_OPEN_INTEREST` independently
  producing `ValueError`; and IV, Greeks, contract-reference, and underlying-
  quote roles each being prohibited in an activity group;
- canonical activity-member order when the optional quote is present; the same
  complete reference reused between quote and either activity role producing
  duplicate `ValueError`; absence of rate/dividend roles and group kinds; and
  absence of 3C.4b-through-3C.4e rate/dividend evaluation behavior;
- the same reference repeated under the same role and under different roles;
  two distinct references under one singular role; structurally equal
  independently created references; the same reference across groups; the
  same semantic key with different record IDs; and different semantic keys
  with the same record ID;
- duplicate normalized group IDs and identical group contents under distinct
  IDs;
- member-order and group-order independence, exact canonical sort keys,
  validation precedence, locale independence, and input non-mutation; and
- absence of reference resolution, timing-property access, record-type or
  relationship evaluation, downstream result APIs, and selection APIs.

Tests for resolved record types and compatibility belong to 3C.4c through
3C.4e and are not part of the 3C.4b structural tests.

### 13.11 Milestone 3C.4c exact identity and comparable-session coherence

Milestone 3C.4c evaluates one exact `MarketDataRelationshipRequest` against
one exact `MarketDataSnapshotTimingAssessment`. It resolves every declared
member in the supplied assessment, verifies the resolved role type, and
evaluates only exact underlying/option-contract identity and the explicitly
owned comparable-session rules. It does not reinterpret the 3C.3 timing
outcome or perform 3C.4d-or-later compatibility work.

#### Public API

3C.4c appends exactly these four public names after the implemented 50-name
prefix, for a total public count of 54:

```text
MarketDataRelationshipIssueCode
MarketDataRelationshipGroupAssessment
MarketDataRelationshipAssessment
assess_market_data_relationships
```

The issue enum has this exact declaration order and values:

```python
class MarketDataRelationshipIssueCode(str, Enum):
    RESOLVED_RECORD_TYPE_MISMATCH = "resolved_record_type_mismatch"
    UNDERLYING_IDENTITY_MISMATCH = "underlying_identity_mismatch"
    OPTION_CONTRACT_IDENTITY_MISMATCH = "option_contract_identity_mismatch"
    SESSION_DATE_MISMATCH = "session_date_mismatch"
```

No public policy, configuration, status, evidence object, exception, registry,
or additional function is introduced.

#### Immutable assessment artifacts and resolution

The frozen group assessment stores exactly:

```python
MarketDataRelationshipGroupAssessment
    group: MarketDataRelationshipGroup
    resolved_bindings: Tuple[SelectedFreshMarketDataBinding, ...]
```

It derives `issue_codes` and `is_coherent`. Direct construction requires an
exact group and an exact tuple/list of exact bindings, one per canonical group
member. Each binding's complete semantic-key/selected-record-ID pair must
match the corresponding member reference. Count or alignment failure raises
`ValueError`; successful construction stores an immutable tuple containing the
exact supplied binding objects.

The frozen top-level assessment stores exactly:

```python
MarketDataRelationshipAssessment
    request: MarketDataRelationshipRequest
    timing_assessment: MarketDataSnapshotTimingAssessment
```

It derives canonical `group_assessments` and `is_coherent`. Construction and
the public function require exact request and timing-assessment types. They
first resolve every reference in canonical request-group and group-member
order. Only after the complete request resolves may group assessments be
constructed. A missing, stale, forged, or cross-paired complete reference
raises `ValueError`; no partial assessment is retained or returned. Wrong
Python types raise `TypeError`.

The exact supplied request, timing assessment, groups, and resolved binding
objects are retained. Temporally coherent and incoherent 3C.3 assessments are
both valid inputs; 3C.4c does not access or gate on any derived 3C.3 timing
property.

#### Exact resolved types and identity matrix

Role type checking uses exact selected-record type:

| Role | Required exact record type |
|---|---|
| `UNDERLYING_QUOTE` | `UnderlyingQuoteObservation` |
| `OPTION_QUOTE` | `OptionQuoteObservation` |
| `OPTION_IMPLIED_VOLATILITY` | `OptionImpliedVolatilityObservation` |
| `OPTION_GREEKS` | `OptionGreeksObservation` |
| `OPTION_VOLUME` | `OptionVolumeObservation` |
| `OPTION_OPEN_INTEREST` | `OptionOpenInterestObservation` |
| `OPTION_CONTRACT_REFERENCE` | `OptionContractReference` |

Any wrong resolved type produces only
`RESOLVED_RECORD_TYPE_MISMATCH`; identity and session fields are not accessed
for that group. It is a relationship issue, not an exception.

With exact types established, ordinary structural equality of complete
normalized keys applies:

| Group kind | Exact identity rule |
|---|---|
| `UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1` | underlying quote `underlying_key` equals option quote `contract_key.underlying_key` |
| `OPTION_QUOTE_ANALYTICS_V0_1` | every present IV/Greeks `contract_key` equals the required quote `contract_key` |
| `OPTION_ACTIVITY_V0_1` | open-interest and optional quote `contract_key` each equal the required volume `contract_key` |
| `OPTION_CONTRACT_REFERENCE_V0_1` | every non-reference `contract_key` equals the required contract-reference `contract_key` |

The snapshot failure is `UNDERLYING_IDENTITY_MISMATCH`; the other three use
`OPTION_CONTRACT_IDENTITY_MISMATCH`.

#### Comparable-session matrix

| Group kind | Exact 3C.4c session rule |
|---|---|
| `UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1` | underlying and option quote `session_date` values are equal |
| `OPTION_QUOTE_ANALYTICS_V0_1` | quote and every present IV/Greeks `session_date` are equal |
| `OPTION_ACTIVITY_V0_1` | optional quote `session_date`, when present, equals volume `session_date` |
| `OPTION_CONTRACT_REFERENCE_V0_1` | no session comparison |

A failed comparison adds `SESSION_DATE_MISMATCH`. Identity and session issues
may coexist and are returned in issue-enum declaration order.
`OptionOpenInterestObservation.open_interest_session_date` and
`OptionContractReference` do not participate. Open-interest lag, completed-
session policy, and applicability remain later work.

#### Ordering, precedence, and exclusions

Group assessments follow canonical `request.groups` order; bindings follow
canonical member order. A group is coherent exactly when its issue tuple is
empty, and the top-level assessment is coherent exactly when every group is
coherent. Validation and evaluation order is:

```text
1. exact request type
2. exact timing-assessment type
3. resolve every complete reference in canonical order
4. exact resolved role-to-record type checks
5. exact identity checks for type-safe groups
6. comparable-session checks for type-safe groups
7. canonical issue and assessment construction
```

3C.4c does not inspect market phase, quote scope, venue, analytics
methodology, activity completeness or freshness, open-interest lag or
applicability, contract-reference applicability beyond exact identity,
selection or ranking, historical completeness, rates, dividends, pricing,
transformations, evidence, or `CalculationLineage`. Phase/scope/venue belongs
to 3C.4d. Analytics, activity, and reference coherence beyond the narrow rules
above belongs to 3C.4e.

## 14. Canonical calculation lineage

A separate input-reference record is required because IDs alone cannot validate calculation chronology.

### 14.1 CalculationQualityFlag

The exact enum order is:

```text
decimal_to_float_converted
interpolated
annualized
adjusted_input_used
correction_selected
composite_input_used
assumption_applied
incomplete_input_used
```

Flags contain no duplicates, use declaration order rather than alphabetical order, and describe calculation conditions rather than attractiveness. A flag never substitutes for methodology disclosure.

### 14.2 CalculationInputReference

The future immutable record is:

```text
CalculationInputReference
    record_id: str
    normalized_at: datetime
    source_ids: Tuple[str, ...]
```

Record ID is trimmed and non-empty. Normalized time is timezone-aware and stored as UTC. At least one source ID is required; source IDs are trimmed, non-empty, unique, and sorted. The frozen, hashable record references one immutable normalized-record version without embedding it.

`source_ids` accepts only a tuple or list. Any other container type raises `TypeError`. Every member must have exact type `str`; string subclasses raise `TypeError`. Each member is trimmed, an ID that is empty after trimming raises `ValueError`, and duplicates after trimming raise `ValueError`. An empty collection raises `ValueError`. The stored value is a tuple in ascending lexicographic order.

`normalized_at` must have exact type `datetime`; datetime subclasses raise `TypeError`. It must be timezone-aware and is normalized to UTC. A naive value raises `ValueError`. If UTC normalization would cross below year 1 or above year 9999 and therefore cannot be represented by Python's `datetime`, it raises `ValueError`; the value is never clamped, wrapped, or otherwise altered.

### 14.3 Canonical parameter types

The top-level parameter input must have exact built-in type `dict`:

```python
type(parameters) is dict
```

Dictionary subclasses, `collections.abc.Mapping` implementations, `UserDict`, custom mappings, and every non-`dict` root raise `TypeError`. Nested mappings must also have exact built-in type `dict`; mappings are never silently coerced to dictionaries. Mapping keys must have exact type `str`, not a string subclass. Strict exact-type boundaries are intentional for deterministic canonicalization.

Supported recursive Python values have the following exact types:

```text
None
type(value) is bool
type(value) is int
type(value) is str
type(value) is Decimal
type(value) is date
type(value) is datetime
type(value) is list
type(value) is tuple
type(value) is dict
```

Subclasses of every supported type are rejected with `TypeError`. Enum objects are rejected with `TypeError` even when they otherwise resemble strings or integers; callers pass an Enum's explicit `.value` using an exact supported type. Type checks distinguish Boolean from integer and check `datetime` separately from `date`; datetime is never accepted as a date. Floats, bytes, bytearray, sets, frozensets, arbitrary objects, and every other unsupported recursive Python type raise `TypeError`. Nonfinite Decimals raise `ValueError`.

Mapping keys are exact, non-empty strings without leading or trailing whitespace and are not silently trimmed; blank or whitespace-invalid keys raise `ValueError`. Lists and tuples normalize to the same ordered-list representation. Arbitrary iterables are not coerced to lists. Cycles are rejected with `ValueError` before serialization. Date rejects datetime, and aware datetimes normalize to UTC. A naive datetime raises `ValueError`. If an otherwise aware datetime near year 1 or year 9999 would cross Python's supported year range during UTC normalization, it raises `ValueError`; normalization never clamps, wraps, or silently alters the date.

Python string values and mapping keys must contain no Unicode surrogate code points in the range U+D800 through U+DFFF. A surrogate code point raises `ValueError`. Valid Unicode scalar values, including non-BMP characters such as emoji represented as ordinary Python Unicode characters, remain valid. Canonical output must be strictly UTF-8 encodable without replacement characters, `surrogatepass`, or any other surrogate-error handler.

### 14.4 Canonical tagged representation

The root is always a tagged mapping. An empty top-level mapping is valid:

```json
{"$map":[]}
```

Every tagged object is an actual JSON object containing exactly one key, with no additional keys. The only valid tag keys are `$map`, `$list`, `$decimal`, `$date`, and `$datetime`. No untagged JSON object is valid anywhere in the tree.

Every mapping is encoded through `$map`, preventing confusion between user mappings and type tags:

```json
{"$map":[["key",value],["next_key",value]]}
```

The `$map` value is a JSON array. Each entry is a JSON array of exactly two elements: a JSON string key and a value following this complete parameter-tree grammar. Keys are non-empty, contain no leading or trailing whitespace, are unique, and appear in strictly increasing Unicode string order. Dictionary insertion order does not affect output. Duplicate or unsorted keys, malformed entry lengths, non-string keys, blank keys, and keys with surrounding whitespace are invalid.

Lists and tuples preserve input order:

```json
{"$list":[value,value]}
```

The `$list` value is a JSON array, and every item follows this grammar. Input lists and tuples both normalize to `$list`; item order is preserved and affects canonical output.

Decimal preserves precision and exponent:

```json
{"$decimal":"0.20"}
```

The `$decimal` value is a JSON string that parses as a finite `Decimal`; NaN and infinities are rejected. Negative zero normalizes to unsigned zero, and the canonical string is `str(normalized_decimal)`. Validation reparses, normalizes negative zero, and requires `str()` to reproduce the supplied string exactly. This preserves precision and exponent while rejecting noncanonical alternatives that do not round-trip identically. Examples such as `0.20`, `0E+2`, and `1.25E-7` may be canonical when produced by this normalization.

Date uses:

```json
{"$date":"2026-07-18"}
```

The `$date` value is a JSON string that parses as `datetime.date` without time information, and `parsed_date.isoformat()` must reproduce the string exactly.

Datetime is always UTC with six microsecond digits:

```json
{"$datetime":"2026-07-18T19:00:00.000000Z"}
```

The `$datetime` value must exactly match `YYYY-MM-DDTHH:MM:SS.ffffffZ`. It always uses UTC, ends in `Z`, and contains six microsecond digits. Parsing and reserializing must reproduce the string exactly. The canonicalizer accepts aware non-UTC Python datetimes but converts them to UTC before serialization; non-`Z` offsets are not canonical JSON input.

The only untagged scalar values are `null`, `true`, `false`, JSON integers, and JSON strings. JSON floating-point values and arbitrary untagged JSON objects are prohibited. Boolean remains distinct from integer.

All parsed JSON strings follow the same Unicode scalar-value rule as Python input. This includes untagged string values, `$map` keys, and the string payloads of `$decimal`, `$date`, and `$datetime`. Any surrogate code point raises `ValueError`. Escaped JSON text that decodes to valid Unicode but differs from canonical output is still rejected by byte-identical reserialization.

Container depth is defined precisely: the root `$map` has depth 1; entering a nested `$map` or `$list` increases depth by 1; scalar and scalar-tag values do not increase depth beyond their containing tagged object. Depth 32 is valid and depth 33 is rejected. The canonicalizer and `CalculationLineage` validation use the same rule.

Cycle detection for Python inputs is based on the active recursion path, not a global set of object identities. Direct and indirect cycles, including tuple/list indirect cycles, raise `ValueError`. Reusing a shared list, tuple, or dictionary in multiple non-cyclic branches is valid and must not be mistaken for a cycle.

### 14.5 Canonical JSON serialization

The planned pure function is:

```text
canonicalize_lineage_parameters(parameters) -> str
```

It serializes the tagged tree using the logical equivalent of:

```python
json.dumps(
    value,
    ensure_ascii=False,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
)
```

Output is deterministic UTF-8 JSON text with no insignificant whitespace. Identical supported values produce byte-identical text; dictionary insertion order does not affect output, while list order does. Float and other unsupported Python types raise `TypeError`; cyclic and over-depth inputs raise `ValueError`. The function reads no files, clocks, environment variables, or external data.

The canonicalizer requires an exact `dict` root. A wrong root type, unsupported recursive Python type, prohibited supported-type subclass, or wrong mapping-key type raises `TypeError`. A structurally supported value with invalid content, including a nonfinite Decimal, invalid key, naive or UTC-unrepresentable datetime, prohibited surrogate code point, cycle, or depth above 32, raises `ValueError`. The function never silently coerces a Mapping to `dict`, an arbitrary iterable to `list`, an Enum to `.value`, a float to Decimal or integer, or a supported-type subclass to its base type. Callers perform any such conversion explicitly before invoking the canonicalizer.

When validating existing canonical JSON, parsing must detect duplicate JSON object keys instead of silently overwriting them. Validation must:

1. parse JSON while rejecting duplicate object keys;
2. validate the complete tagged grammar;
3. require the root to be `$map`;
4. reject JSON floats;
5. reject malformed or unknown tags;
6. reject noncanonical map-key order;
7. reject noncanonical Decimal, date, or datetime strings;
8. enforce the maximum nesting depth;
9. reserialize through the canonical serializer;
10. require byte-identical text.

No additional public validation function is planned; `CalculationLineage` may use a private parser and validator.

Across the new 3B.3 public APIs, `TypeError` denotes a wrong Python type: a wrong canonicalizer root or recursive value type, a prohibited subclass, a wrong mapping-key type, a wrong constructor collection type, or a wrong constructor element type. `ValueError` denotes an invalid value of an otherwise structurally accepted type: invalid or duplicate keys, nonfinite Decimal, naive or UTC-unrepresentable datetime, chronology failure, an empty required collection, duplicate IDs or flags, calculation/input ID collision, cycle, excessive depth, prohibited surrogate code point, or malformed or noncanonical parameter JSON. No custom public exception class is introduced.

JSON syntax and parsing failures exposed by `CalculationLineage` validation raise `ValueError` and do not leak `json.JSONDecodeError` as the public exception type. Duplicate JSON object keys, duplicate `$map` user keys, JSON floats, malformed or unknown tags, noncanonical Decimal/date/datetime strings, prohibited surrogate code points, and byte-nonidentical canonical JSON likewise raise `ValueError`.

### 14.6 CalculationLineage

The future immutable record has these exact fields:

```text
CalculationLineage
    calculation_id: str
    calculation_type: str
    methodology_id: str
    methodology_version: str
    calculated_at: datetime
    inputs: Tuple[CalculationInputReference, ...]
    parameters_json: str
    quality_flags: Tuple[CalculationQualityFlag, ...]
```

Required strings are trimmed and non-empty. Calculation time is timezone-aware UTC. At least one `CalculationInputReference` is required; input record IDs are unique, and inputs normalize into ascending record-ID order. `calculation_id` cannot equal an input record ID, and `calculated_at` cannot precede any input normalized time.

`calculated_at` must have exact type `datetime`; datetime subclasses raise `TypeError`. A naive value raises `ValueError`. An aware value is normalized to UTC, and UTC-normalization overflow below year 1 or above year 9999 raises `ValueError` without clamping, wrapping, or silent alteration.

`inputs` accepts only a tuple or list; another container raises `TypeError`. Every element must satisfy `type(item) is CalculationInputReference`; subclasses and all other elements raise `TypeError`. An empty collection, duplicate normalized `record_id`, calculation-ID/input-ID collision, or chronology violation raises `ValueError`. The stored value is a tuple in ascending `record_id` order.

`parameters_json` is a trimmed, non-empty string whose root is a canonical `$map`. The empty canonical mapping `{"$map":[]}` is valid. The string must be produced by, or be byte-equivalent to, `canonicalize_lineage_parameters`; no untagged mapping is accepted and no JSON float may survive parsing. Validation uses duplicate-key-safe parsing, validates the complete grammar and depth, and requires byte-identical canonical reserialization. Quality flags contain no duplicates and normalize to declaration order. The record is frozen and hashable. No input is hidden. Lineage remains separate from the calculated numeric record and does not calculate the research value itself.

`parameters_json` must have exact type `str`; string subclasses raise `TypeError`. Required-string normalization first trims leading and trailing whitespace, and the normalized string is the value validated and stored. Surrounding whitespace may therefore be removed, but after trimming the stored text must be byte-identical to canonical reserialization. Internal insignificant whitespace, noncanonical escapes, ordering, or number spellings remain invalid and raise `ValueError`.

`quality_flags` accepts only a tuple or list; another container raises `TypeError`. Every element must have exact type `CalculationQualityFlag`; foreign Enum values, subclasses, and all other elements raise `TypeError`. Duplicate flags raise `ValueError`. Empty flags are valid, and the stored tuple follows enum declaration order. Flags are never inferred from calculation behavior.

A sidecar is necessary because existing research records mostly use date-only `as_of_date`, while real inputs have intraday timestamps and individual source identities. Existing research records do not receive lineage fields in 3B. Future Milestone 3C.7 transformations will consume temporally coherent, relationship-validated, deterministically selected, and where applicable historically complete inputs; perform deterministic calculations; produce existing research records; and create `CalculationLineage` sidecars.

## 15. Mapping to existing research records

| Existing record | Normalized inputs | Required calculation disclosure |
| --- | --- | --- |
| `VolatilityEnvironment` | Current ATM `OptionImpliedVolatilityObservation` or deterministically interpolated surface points; historical ATM IV observations; completed `UnderlyingDailyBarObservation` series | ATM-selection method, interpolation, tenor matching, realized-volatility formula, annualization, historical observation count, and source lineage |
| `TailPricingSlice` | `OptionImpliedVolatilityObservation` records; `OptionGreeksObservation` Delta values or declared Delta calculation; exact expiration | Delta convention, 10-delta/25-delta/ATM selection or interpolation, surface exclusions, historical skew count, and source lineage |
| `StructureLiquidity` | Exact-leg `OptionQuoteObservation`, `OptionVolumeObservation`, and `OptionOpenInterestObservation` | Leg-to-position quote aggregation, quote-time alignment, minimum-leg selection, activity session dates, and delayed or indicative status |
| `StructureCosts` | Exact-leg `OptionQuoteObservation`, `OptionGreeksObservation`, `OptionContractReference`, and declared commission/fee assumptions | Premium, multiplier, and quantity scaling; spread-cost method; Gamma scaling; Theta day convention; fee assumptions; source lineage |
| `ScenarioResult` | Underlying quote, exact-leg IV, contract terms, rate points, dividends, pricing-engine output, and declared scenario | Model/version, rate interpolation, dividends, surface construction, shock methodology, exit-cost methodology, and source lineage |

Normalized observations never directly produce `CandidateState`. Calculated records feed `CandidateResearchRecord`, which is then evaluated into a separate `ScreeningDecision`. Provider choice does not change screening thresholds.

## 16. Validation boundaries

| Layer | Responsibilities | Explicit exclusions |
| --- | --- | --- |
| Provider adapter | Authentication and transport; provider schema parsing; raw-meaning preservation; provider timestamp extraction; `SourceReference` construction | No economic screening |
| Core normalization records | Types; finite values; canonical units; timezone awareness; identifier consistency; basic quote/bar invariants; provenance presence | No historical calculations or provider fetching |
| Selected/fresh binding layer | Complete semantic candidate-group verification; authoritative correction selection; selected-record resolution; authoritative single-record freshness; immutable proof retention | No cross-record coherence, cross-observation selection, historical completeness, economic transformation, or calculation lineage |
| Binding-set temporal-coherence layer | Exact binding-set canonicalization; complete policy/context compatibility; effective and complete-source spans for exact temporal participants | No relationship inference, selection, completeness, economic transformation, or calculation lineage |
| Auditable binding-reference layer | Portable semantic-key/selected-record-ID references; exact resolution within one supplied timing assessment; exact retained-binding identity | No timing decision, relationship/group semantics, selection, completeness, economic transformation, or calculation lineage |
| Explicit relationship/group-coherence layer | Caller-declared counterpart grouping; contract, session, phase, scope, venue, analytics, activity, and reference compatibility for represented option-domain observations | No rate/dividend relationship, identity, linkage, applicability, or economic use; observation selection; completeness; economic transformation; or calculation lineage |
| Calculation layer | Rate/dividend identity, linkage, applicability, and economic use; interpolation; annualization; percentiles; realized volatility; structure aggregation; pricing scenarios; `CalculationLineage` | No hidden inputs or state classification |
| `CandidateResearchRecord` | Aggregate consistency; evidence classification; research disclosures | No provider parsing |
| `ScreeningPolicy` and `screen_candidate` | Deterministic state classification | No provider normalization or fetching |
| Report renderer | Deterministic presentation | No fetching, market calculations, or raw untrusted provider payloads |

## 17. Failure behavior

- Invalid data raises validation errors.
- Missing data remains missing; it is not replaced with zero.
- Stale data is retained for audit but cannot be treated as current evidence.
- Unknown units or Greek scaling make the affected value unusable.
- Provider errors are not market observations.
- Network failures never produce synthetic fallback prices.
- Last price never silently replaces a missing bid/ask midpoint.
- Another strike or expiration never substitutes for the requested contract.
- No LLM may repair or invent numerical fields.

## 18. Security and licensing boundaries

- Credentials remain outside records and source control.
- Raw-payload retention follows provider licensing.
- Payload hashes or provider IDs may be retained when raw storage is prohibited.
- Source URIs must not contain secrets.
- Provider response text is untrusted input.
- Raw provider text must not be rendered until Markdown escaping and sanitization exist.
- Licensing restrictions do not change numerical validation rules.

## 19. Planned implementation sequence

### Milestone 3A.1 — Provenance and identity foundations

Implement only:

```text
DataOrigin
SourceQualityFlag
NormalizationQualityFlag
MarketPhase
QuoteScope
UnderlyingSecurityType
DividendStatus
SourceReference
NormalizationMetadata
UnderlyingKey
OptionContractKey
```

Tests use fixed synthetic values only. This phase does not implement quote observations, option analytics, historical bars, rates, dividends, freshness policies, freshness assessments, freshness reason codes, `CalculationLineage`, transformations, provider adapters, provider SDKs, credentials, or network access.

### Milestone 3A.2 — Quotes, contract reference, and activity records

After Milestone 3A.1 review, implement:

```text
UnderlyingQuoteObservation
OptionContractReference
OptionQuoteObservation
OptionVolumeObservation
OptionOpenInterestObservation
```

### Milestone 3A.3 — Analytics, historical, rate, and dividend records

After Milestone 3A.2 review, implement:

```text
OptionImpliedVolatilityObservation
OptionGreeksObservation
UnderlyingDailyBarObservation
RateCurvePointObservation
DividendObservation
```

No network access is authorized in any Milestone 3A subphase.

### Milestone 3B.1 — Freshness contracts and assessment

Implement only:

```text
MarketDataCategory
MarketDataFreshnessPolicy
FreshnessContext
FreshnessStatus
FreshnessReasonCode
FreshnessAssessment
assess_market_data_freshness
```

Use fixed synthetic records and explicit synthetic policies. Implement the calendar-date-gap fields and reasons defined in Section 11; do not implement trading-session counting. Do not implement correction selection or `CalculationLineage` in 3B.1.

### Milestone 3B.2 — Correction selection

After 3B.1 review, implement only:

```text
CorrectionSelectionStatus
CorrectionSelectionReasonCode
CorrectionSelection
select_correction_candidate
```

Use immutable synthetic `NormalizationMetadata` candidates. Implement the exact one-terminal-reason algorithm and candidate normalized-at chronology check.

### Milestone 3B.3 — Calculation lineage

After 3B.2 review, implement only:

```text
CalculationQualityFlag
CalculationInputReference
CalculationLineage
canonicalize_lineage_parameters
```

Use fixed synthetic inputs. Implement the complete canonical tagged-tree grammar and duplicate-key-safe JSON validation. No provider or network access is authorized in any 3B subphase.

### Milestone 3C.1 — Semantic observation identity (complete)

The deterministic provider-neutral semantic observation identity contract in
Section 13.6 is implemented, reviewed, and stable. Its only public API is:

```text
semantic_observation_key(record) -> str
```

### Milestone 3C.2 — Per-record selected/fresh binding

The Section 13.7 per-record selected/fresh binding contract is implemented,
reviewed, and stable. Its exact two public additions are:

```text
SelectedFreshMarketDataBinding
bind_selected_fresh_market_data
```

The implemented public `market_data` API count at completion of 3C.2 was 39;
the current count after 3C.3 is 42. The binding verifies a
complete semantic candidate group, recomputes correction selection, resolves
one selected record, recomputes freshness, and retains the complete immutable
proof.

Completing the 3C.2 contract does not authorize snapshot or transformation
implementation.

### Milestone 3C.3 — Binding-set temporal coherence

The Section 13.8 binding-set temporal-coherence contract is implemented and
reviewed. Its exact three public additions are:

```text
MarketDataSnapshotTimingReasonCode
MarketDataSnapshotTimingAssessment
assess_market_data_snapshot_timing
```

The current implemented public count is 42. 3C.3 assesses complete
policy/context compatibility and the effective/source spans of the exact
temporal-participant types. It does not infer relationships, choose
observations, prove completeness, or transform market data.

### Milestone 3C.4a — Auditable binding references

The Section 13.9 portable two-string binding reference, exact factory from one
selected/fresh binding, and exact resolution inside one binding-set timing
assessment are implemented and reviewed. The current implemented public count
is 45.

### Milestone 3C.4b — Explicit relationship/group request representation

The standalone structural contract in Section 13.10 was found viable by A-level
preflight and drafted locally. Its first targeted specification preflight found
two cross-document ownership/taxonomy contradictions. The draft was remediated
by assigning all rate/dividend relationship work to 3C.7 and permitting an
optional option quote in `OPTION_ACTIVITY_V0_1`. The first targeted re-preflight
found the remaining Section 12.3 ownership gap, which was corrected. The final
second targeted re-preflight passed, and the Milestone 3C.4b documentation
contract is approved, implemented, reviewed, and committed. Its exact five
public names append after the unchanged 45-name prefix for an implemented
post-3C.4b count of 50.

### Milestone 3C.4c — Exact identity and comparable sessions

The Section 13.11 contract is implemented locally pending independent review.
Its four public names append after the implemented 50-name prefix for a local
count of 54. It evaluates exact resolved role types, underlying/option-contract
identity, and only the declared comparable-session matrix.

### Milestones 3C.4d and 3C.4e — Later relationship evaluation

Separately define quote phase/scope/venue compatibility and analytics,
activity, and contract-reference coherence. Their APIs remain undefined. They
do not represent or evaluate rate/dividend relationships. Every rate/dividend
identity, linkage, applicability, and economic use remains 3C.7 work.

### Milestone 3C.5 — Deterministic cross-observation selection

Choose among different eligible semantic observations only after temporal and
explicit relationship coherence. Do not silently choose a latest or preferred
observation before this contract is defined.

### Milestone 3C.6 — Historical-series assembly and completeness

Define expected-session, lookback, frequency, adjustment-methodology, and
duplicate/missing-session rules separately from current snapshot timing and
selection.

### Milestone 3C.7 — Market-data-to-research transformations

Perform economic calculations, pricing where authorized, research-evidence and
research-record construction, and `CalculationLineage` construction only after
the required temporal, relationship, selection, and historical-completeness
proofs. Selection, completeness, calculation, pricing, research evidence, and
lineage remain separate responsibilities.

### Milestone 3D — Provider adapter

Only after the contracts and transformations are stable:

- evaluate providers;
- select one provider;
- add recorded raw fixtures;
- implement an adapter;
- separately authorize live-network use.

Live and delayed provider data remain unauthorized until that separate review.

The full implementation sequence is:

1. Implement and review Milestone 3A.1.
2. Implement and review Milestone 3A.2.
3. Implement and review Milestone 3A.3.
4. Implement and review Milestone 3B.1 freshness contracts and assessment.
5. Implement and review Milestone 3B.2 correction selection.
6. Implement and review Milestone 3B.3 calculation lineage.
7. Complete and review Milestone 3C.1 semantic observation identity.
8. Complete and review Milestone 3C.2 per-record selected/fresh binding.
9. Define, review, then implement Milestone 3C.3 binding-set temporal
   coherence.
10. Define, review, then implement Milestone 3C.4a auditable binding
    references.
11. Define, review, then implement Milestones 3C.4b through 3C.4e explicit
    relationship/group coherence.
12. Define, review, then implement Milestone 3C.5 deterministic cross-
    observation selection.
13. Define, review, then implement Milestone 3C.6 historical-series assembly
    and completeness.
14. Define, review, then implement Milestone 3C.7 market-data-to-research
    transformations and `CalculationLineage` construction.
15. Select a provider only after Milestones 3A–3C are stable.
16. Add recorded provider fixture payloads.
17. Implement one adapter behind the contracts.
18. Review licensing and retention constraints.
19. Separately authorize live-network testing.

## 20. Non-goals

Market-data contracts v0.1 do not:

- select or rank providers;
- negotiate licensing;
- make HTTP requests;
- store credentials;
- scan an option chain;
- calculate volatility percentiles or realized volatility;
- price options;
- calculate `ScreeningDecision`;
- recommend or execute trades;
- integrate news or event narratives;
- implement Markdown escaping;
- define production freshness thresholds;
- support non-US currencies in the MVP pipeline;
- solve policy registration or fingerprinting.

## 21. Open design questions

Resolved for v0.1 by the Milestone 3C.1 contract:

- Semantic observation keys for all ten normalized record types use the exact
  deterministic identity maps and versioned canonical encoding in Section 13.6.
- No for v0.1: existing immutable normalized records do not directly carry a
  semantic observation key. The key is derived by the planned pure
  `semantic_observation_key(record) -> str` function; no new stored field is
  added.

Resolved for v0.1 by the Milestone 3C.2 contract:

- A standalone per-record selected/fresh binding stage precedes binding-set
  temporal coherence.
- The binding retains and verifies the complete candidate records; metadata
  alone does not prove a semantic candidate group.
- Correction selection is recomputed from the complete candidate group and the
  supplied authoritative correction-evaluation context. Exact equality verifies
  candidate-group and selector-result consistency but does not externally
  authorize the supplied rule ID/version or evaluation time.
- Freshness assessment is independently recomputed from the selected record,
  full freshness policy, and full freshness context rather than trusted as a
  supplied sidecar.
- Every record, including a one-candidate group, requires explicit correction
  selection.
- Correction evaluation time must be less than or equal to freshness context
  evaluation time.
- The complete freshness policy and context are retained in the binding.
- Successful output is the frozen public `SelectedFreshMarketDataBinding`
  artifact.
- The binding has deterministic structural equality after candidate
  canonicalization but no v0.1 hashability guarantee and no new nested
  hashability eligibility rule.
- The two 3C.2 public names append, in contract order, after the unchanged
  existing 37-name public API sequence.
- Public-function and direct-constructor validation use the exact path-specific
  precedence defined in Section 13.7.
- A valid-but-ambiguous correction group or non-fresh assessment raises
  `ValueError`; no new rejection status or assessment is introduced.

Resolved for v0.1 by the Milestone 3C.3 contract:

- The broad standalone snapshot-coherence contract was not viable without an
  explicit relationship request. 3C.3 is narrowed to binding-set temporal
  coherence; decomposed 3C.4 work separately defines portable references and
  later relationship/group coherence.
- The assessment accepts only a non-empty exact tuple/list of exact
  `SelectedFreshMarketDataBinding` objects, rejects duplicate selected record
  IDs and semantic keys, and stores bindings in the canonical semantic-key/
  record-ID order.
- Complete policies and contexts require exact structural equality. Mixed
  artifacts produce canonical incoherence reasons rather than exceptions, and
  threshold conclusions are skipped while raw spans remain available.
- Seconds-based spans include exactly underlying quotes, option quotes, option
  volume, option IV, and option Greeks. The five date/reference-oriented record
  types do not participate, and calendar dates are never converted to
  datetimes.
- The effective span and complete participating-source span use exact
  `Decimal` seconds. Equality with the common cross-record threshold passes.
- The frozen assessment stores only canonical bindings and derives all common
  artifacts, metrics, reasons, and its Boolean outcome. It has no status enum,
  success-only snapshot class, separate snapshot policy, or hashability
  promise.
- The current implemented public API has 42 names. The exact three 3C.3 names
  append in Section 13.8 order after the preceding 39 names.
- No normalized-record schema change is required for the narrow 3C.3 contract.

Resolved for v0.1 by the implemented Milestone 3C.4a contract. The contract
completed targeted specification preflight, implementation, and independent
review. The implemented contract decisions are:

- One portable binding reference contains exactly the semantic observation key
  and selected record ID as exact strings normalized by Python's no-argument
  `str.strip()`, with remaining case and Unicode code points preserved.
- The factory derives those strings from one exact
  `SelectedFreshMarketDataBinding` without recomputing its proofs.
- The resolver requires one exact complete-pair match inside one exact
  `MarketDataSnapshotTimingAssessment` and returns the exact retained binding.
- Direct reference construction supplies no existence proof; the explicitly
  supplied timing assessment is the only authoritative binding universe.
- Resolution is independent of the timing assessment's coherent or incoherent
  outcome and defines no relationship, group, role, compatibility, issue, or
  selection behavior.
- The three 3C.4a names append after the existing 42 names for the current
  implemented count of 45.

Resolved by the implemented Milestone 3C.4b contract. The first
targeted specification preflight did not pass because of two cross-document
ownership/taxonomy contradictions. The local draft was remediated. The first
targeted re-preflight found the remaining Section 12.3 ownership gap, which was
corrected; the final second targeted specification re-preflight passed before
the contract was implemented, reviewed, and committed:

- The structural request model uses exact versioned group kinds, exact global
  roles, one role/reference member, one caller-identified group, and one
  request containing canonical groups.
- A complete reference may appear only once within one group regardless of
  role, but may be reused across different groups.
- Group members canonicalize by role declaration index, semantic observation
  key, and selected record ID. Request groups canonicalize only by unique
  normalized `group_id`.
- `OPTION_ACTIVITY_V0_1` requires volume and open interest and permits zero or
  one option quote as declared quote/activity context.
- Every rate/dividend relationship, identity, linkage, applicability, and
  economic use belongs to 3C.7; no rate/dividend role or group kind exists in
  3C.4b.
- 3C.4b performs no reference resolution, timing gating, record-type checking,
  or relationship evaluation.
- The five 3C.4b names append after the existing 45 names for the implemented
  post-3C.4b count of 50.

Resolved for local implementation by the Milestone 3C.4c A-level preflight:

- Exact resolved role types are assessed before field access; a mismatch is a
  canonical issue rather than an exception.
- Snapshot, analytics, activity, and contract-reference groups use the exact
  identity and kind-specific session matrices in Section 13.11.
- Open-interest session lag and contract-reference applicability remain later
  work, and temporal incoherence does not block 3C.4c evaluation.
- Four 3C.4c names append after the implemented 50-name prefix for a local
  public count of 54 pending independent review.

The following questions remain open:

- Which MIC or listing registry should supply `listing_mic`?
- How should adjusted option deliverables be represented beyond `deliverable_id`?
- What production freshness thresholds apply by category?
- What production calendar-day gap thresholds should account for weekends and holidays?
- Should a future version replace calendar-day gaps with exchange-calendar trading-session counts?
- Should different policies exist for end-of-day research and intraday research?
- Should `AFTER_HOURS` source flags create an explicit policy reason in a later version?
- Should `UNKNOWN_CONDITION` source flags become policy-controlled?
- Should future policies make halted-source handling configurable by category?
- Which exchange calendar implementation would support trading-session counting?
- Which provider correction schemes expose genuinely comparable numeric revisions?
- Which provider licenses permit retention of correction histories?
- Which rate and dividend methodologies should scenario pricing use?
- Should Convexity Hunter calculate IV and Greeks or initially accept provider-calculated analytics?
- How should historical volatility-surface observations be stored efficiently?
- What raw payload material may legally be retained for each provider?
- When should existing research records receive direct lineage IDs instead of sidecar lineage?
- Should forecast dividends use one provider model or a system-composite methodology?
