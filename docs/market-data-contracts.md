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

For a normalized record with multiple source references, `normalization_methodology` states how the effective time was selected. The timestamp is timezone-aware UTC, is not earlier than the earliest source `observed_at`, and is not later than the latest source `observed_at`. The selected time must not conceal individual source timestamps or make an old component appear newer than it is. Downstream snapshot-coherence and freshness checks still inspect every source observation time.

A future freshness assessment will use the normalized record's `effective_observed_at`, the complete source-reference observation-time range, and configured cross-record skew rules. The final freshness algorithm remains deferred.

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

`maximum_cross_record_skew_seconds` is retained for later multi-record snapshot assembly. Single-record freshness assessment does not apply it; a separately reviewed snapshot-coherence function will apply it. `maximum_source_observation_span_seconds` is the within-record multi-source limit and is applied in 3B.1.

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

`maximum_cross_record_skew_seconds` is not applied by single-record freshness assessment. Later snapshot assembly compares `metadata.effective_observed_at` across records and also inspects every record's complete source-time range; no single effective timestamp can hide incompatible source spans. That future operation preserves every individual `FreshnessAssessment`. It is not implemented in 3B.1, and snapshot coherence and transformation into research records remain Milestone 3C.3+ work.

## 12. Snapshot coherence

Future snapshot checks use each normalized record's `effective_observed_at`, every underlying `SourceReference.observed_at`, market phase, quote scope, venue where relevant, session date, and the freshness policy. No effective timestamp replaces inspection of source timestamps.

### 12.1 Quote alignment

Underlying and option quotes used together must refer to the same underlying, use compatible market phases and quote scopes, use compatible venues where relevant, fall within configured effective and source observation-time skew, pass the freshness policy, and disclose delayed or indicative status.

### 12.2 Analytics alignment

Option IV and Greeks must match the exact `OptionContractKey`, same market session, observation time compatible with the quote snapshot, and declared model plus rate and dividend inputs.

### 12.3 Volume and open interest

Quote, volume, and open interest need not have identical timestamps. Each keeps its own observation time or session date, and differences remain visible. Calculations use the latest eligible completed open-interest session. Cumulative volume is used only under its declared as-of time. Stale open interest must not be presented as current intraday open interest without disclosure.

### 12.4 Historical series

Historical percentile and realized-volatility inputs require one observation per valid completed US trading session, no duplicate session dates, consistent adjustment methodology, consistent sampling frequency, declared lookback count, and no mixing of intraday, weekly, or end-of-day observations.

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
    -> later snapshot coherence
    -> later transformation
```

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

#### Planned public API

Milestone 3C.2 adds exactly these two planned public names to
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

The existing 37 public names and their exact order remain unchanged. The two
names above are appended to `market_data.__all__` after the existing 37 names,
in exactly the displayed order: first `SelectedFreshMarketDataBinding`, then
`bind_selected_fresh_market_data`. No public name may be inserted among or
reorder the existing names. The planned count after 3C.2 implementation is 39.
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
authoritative inputs produce equal bindings regardless of candidate input order.
Callers must not rely on using a binding as a dictionary key or set member. No
custom `__hash__` is planned; implementation must not use identity-based hashing,
catch nested unhashability, or invent a hash value.

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

#### Selection/freshness chronology and authoritative freshness

The exact per-record chronology is:

```text
correction_selection.evaluated_at <= freshness_context.evaluation_at
```

Equality is valid. A correction selection evaluated after the freshness context
raises `ValueError`. This preserves the operational sequence of selection first
and freshness second. Later snapshot logic may impose common evaluation or
as-of-time requirements across bindings. Milestone 3C.2 defines no relationship
to a future snapshot time or `CalculationLineage.calculated_at`.

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

12. Recompute correction selection from the canonical candidate metadata,
    derived key, and supplied selection rule identity, version, and evaluation
    time.
13. Propagate existing selector validation errors unchanged.
14. Require exact equality with the supplied `correction_selection`; a mismatch
    raises `ValueError`.
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

A structurally valid but forged, mismatched, stale, ambiguous, or unrelated
sidecar raises `ValueError`. The public function accepts no caller-supplied
correction or freshness sidecar; it calculates both and then constructs the
validated binding.

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
same authoritative correction result
same freshness policy and context
same authoritative freshness result
    -> structurally equal bindings
```

Candidate input order does not affect successful binding equality. Equal hashes
are not promised. The public function should conceptually compute the
authoritative sidecars and pass them to the validated constructor, but this is
not required as an internal implementation technique. Observable validation and
successful output semantics must follow this contract in either implementation.

Future 3C.2 tests must cover:

- frozen behavior and no mutation;
- deterministic structural equality and candidate-order independence;
- the absence of a hashability promise, with an optional regression showing
  that callers cannot depend on hashing when an existing valid nested value is
  unhashable;
- exact append order of the two public exports after the existing 37 names;
- exact top-level and path-specific validation precedence; and
- equivalent successful output from the public function and direct constructor.

Tests must not require bindings to be hashable.

#### Determinism, snapshot boundary, and lineage

The record and function are pure. They do not mutate inputs; inspect the wall
clock; call `date.today` or `datetime.now`; read files or environment variables;
use randomness; access a network, provider SDK, or LLM; or use a process-global
registry. All time, rule, policy, and context values are explicit inputs. Input
order does not affect the resulting binding or its structural equality.

Milestone 3C.2 proves only per-record selected/fresh eligibility. A later
snapshot stage may consume multiple bindings and inspect their preserved
selected records, candidate records and sources, freshness policies and
contexts, correction and freshness evaluation times, market phase, quote scope,
venue, session and effective dates, and source observation times.

Milestone 3C.2 does not evaluate `maximum_cross_record_skew_seconds`, global
timestamp ranges, common cross-record policy or context, phase/scope/venue
compatibility, analytics/quote alignment, activity/reference/rate/dividend
selection, or historical completeness. Its output remains stable before those
future algorithms are specified because it retains all required immutable
inputs and proof objects.

Milestone 3C.2 does not create or modify `CalculationLineage`. The dependency is:

```text
SelectedFreshMarketDataBinding
    -> later snapshot and cross-observation selection
    -> later transformation
    -> CalculationLineage
```

Later transformation lineage may use
`CalculationQualityFlag.correction_selected`, but that flag does not replace the
detailed binding proof.

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

A sidecar is necessary because existing research records mostly use date-only `as_of_date`, while real inputs have intraday timestamps and individual source identities. Existing research records do not receive lineage fields in 3B. Future Milestone 3C.3+ transformations will consume selected/fresh bindings, perform deterministic calculations, produce existing research records, and create `CalculationLineage` sidecars.

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
| Calculation layer | Interpolation; annualization; percentiles; realized volatility; structure aggregation; pricing scenarios; `CalculationLineage` | No hidden inputs or state classification |
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

After Milestone 3C.1, implement and review only the Section 13.7 per-record
selected/fresh binding contract. Its exact two planned public additions are:

```text
SelectedFreshMarketDataBinding
bind_selected_fresh_market_data
```

The current public `market_data` API count is 37; the planned count after 3C.2
implementation is 39. The binding verifies a complete semantic candidate group,
recomputes correction selection, resolves one selected record, recomputes
freshness, and retains the complete immutable proof. Milestone 3C.2 must be
reviewed and stable before snapshot assembly consumes bindings.

Completing the 3C.2 contract does not authorize snapshot or transformation
implementation.

### Milestone 3C.3+ — Remaining Milestone 3C work

Snapshot coherence, deterministic cross-observation selection, historical
completeness, and research-record transformations stay grouped at dependency
level only. Milestone 3C.3+ remains specification-blocked and unimplemented.
Final numbering and public APIs beyond 3C.2 are intentionally not assigned until
their contracts are clarified.

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
8. Review and stabilize the Milestone 3C.2 per-record selected/fresh binding
   contract, then implement it only after approval.
9. Clarify and review Milestone 3C.3+ snapshot coherence, deterministic
   cross-observation selection, historical completeness, and transformation
   specifications before implementing them.
10. Select a provider only after Milestones 3A–3C are stable.
11. Add recorded provider fixture payloads.
12. Implement one adapter behind the contracts.
13. Review licensing and retention constraints.
14. Separately authorize live-network testing.

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

- A standalone per-record selected/fresh binding stage precedes snapshot
  coherence.
- The binding retains and verifies the complete candidate records; metadata
  alone does not prove a semantic candidate group.
- Correction selection and freshness assessment are recomputed from their
  authoritative inputs rather than trusted as supplied sidecars.
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
- Should cross-record snapshot assessment become a separate public record?
- Which exchange calendar implementation would support trading-session counting?
- Which provider correction schemes expose genuinely comparable numeric revisions?
- Which provider licenses permit retention of correction histories?
- Which rate and dividend methodologies should scenario pricing use?
- Should Convexity Hunter calculate IV and Greeks or initially accept provider-calculated analytics?
- How should historical volatility-surface observations be stored efficiently?
- What raw payload material may legally be retained for each provider?
- When should existing research records receive direct lineage IDs instead of sidecar lineage?
- Should forecast dividends use one provider model or a system-composite methodology?
