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

`maximum_cross_record_skew_seconds` is retained for later multi-record snapshot assembly. Single-record freshness assessment does not apply it; 3C transformations or a separately reviewed snapshot-coherence function will apply it. `maximum_source_observation_span_seconds` is the within-record multi-source limit and is applied in 3B.1.

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

It accepts only the eleven normalized 3A record types. It never mutates the record, policy, context, metadata, or sources; fetches data; inspects an exchange calendar; calculates economic metrics; or calls screening or reporting code.

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

`maximum_cross_record_skew_seconds` is not applied by single-record freshness assessment. Later snapshot assembly compares `metadata.effective_observed_at` across records and also inspects every record's complete source-time range; no single effective timestamp can hide incompatible source spans. That future operation preserves every individual `FreshnessAssessment`. It is not implemented in 3B.1, and transformation into research records remains 3C work.

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

For each ordered source-lineage key:

```text
revision component =
    revision_number when revision_number is positive
    otherwise 0
```

The candidate revision vector contains those components in source-lineage-key order. Revisions are comparable only within the same lineage key. Revisions from unrelated providers or datasets are never compared directly. `provider_correction_id` proves correction identity but supplies no ordering semantics, and lexical correction-ID order is prohibited. Normalized time, retrieval time, observation time, file order, insertion order, record ID, payload hash, set order, and dictionary order are prohibited as latest-revision tie-breakers.

Candidate A strictly dominates candidate B when both have the same ordered lineage keys, every revision component in A is greater than or equal to its counterpart in B, and at least one component is greater.

`evaluated_at` is timezone-aware and normalized to UTC. Before ordering corrections, every candidate must satisfy `candidate.normalized_at <= evaluated_at`. A candidate normalized later is invalid input and raises `ValueError`; it does not produce an ambiguous selection and is never silently filtered. The function never substitutes the current clock. Because `NormalizationMetadata` already requires normalization after every source retrieval, this check establishes that each candidate existed by the evaluation time.

The exact terminal-reason algorithm is:

1. Validate the non-empty tuple or list of `NormalizationMetadata` candidates, unique record IDs, evaluated-at chronology, and supplied rule fields.
2. Normalize candidates into ascending `record_id` order for presentation only.
3. If exactly one candidate exists, return `selected` with `only_candidate_selected`.
4. For multiple candidates, if any source lacks `provider_record_id`, return `ambiguous` with `missing_provider_record_id`.
5. Construct each candidate's source-lineage keys.
6. If one candidate contains duplicate source-lineage keys, raise `ValueError`; do not return ambiguity.
7. If candidates lack identical ordered lineage-key sets, return `ambiguous` with `source_lineage_mismatch`.
8. If candidates contain different non-equivalent correction identities for the same lineage key and numeric revision, return `ambiguous` with `conflicting_correction_ids_same_revision`.
9. Construct revision vectors.
10. If all revision vectors are identical, return `ambiguous` with `tied_revision_vectors`.
11. If exactly one candidate strictly dominates every other candidate, return `selected` with `dominating_revision_vector_selected`.
12. Otherwise, return `ambiguous` with `incomparable_revision_vectors`.

For correction-identity comparison, `None` and a supplied ID differ, two different supplied IDs differ, and identical supplied IDs are equivalent. Correction IDs never define ordering.

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

The caller supplies a trimmed, non-empty semantic observation key; v0.1 defines no global semantic-key registry. Candidate IDs are unique and sorted. Selected status requires a selected record ID; ambiguous status requires `selected_record_id=None`. Every result has exactly one reason code. Rule identity is trimmed and non-empty. Evaluation time is explicit and normalized to UTC; selection never reads the wall clock. The result is frozen and hashable and neither embeds nor mutates candidates.

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

### 14.3 Canonical parameter types

The top-level parameter input is an actual mapping with string keys. Supported recursive values are:

```text
None
bool
int
str
Decimal
date
timezone-aware datetime
list
tuple
dict
```

Boolean is distinct from integer. Floats, nonfinite Decimals, bytes, bytearray, sets, frozensets, Enum objects, and arbitrary objects are prohibited; callers pass an Enum's explicit `.value` string. Mapping keys are actual, non-empty strings without leading or trailing whitespace and are not silently trimmed. Lists and tuples normalize to the same ordered-list representation. Cycles are rejected before serialization. Date rejects datetime, and aware datetimes normalize to UTC.

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

Container depth is defined precisely: the root `$map` has depth 1; entering a nested `$map` or `$list` increases depth by 1; scalar and scalar-tag values do not increase depth beyond their containing tagged object. Depth 32 is valid and depth 33 is rejected. The canonicalizer and `CalculationLineage` validation use the same rule.

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

Output is deterministic UTF-8 JSON text with no insignificant whitespace. Identical supported values produce byte-identical text; dictionary insertion order does not affect output, while list order does. Float, unsupported, cyclic, and over-depth inputs raise validation errors. The function reads no files, clocks, environment variables, or external data.

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

`parameters_json` is a trimmed, non-empty string whose root is a canonical `$map`. The empty canonical mapping `{"$map":[]}` is valid. The string must be produced by, or be byte-equivalent to, `canonicalize_lineage_parameters`; no untagged mapping is accepted and no JSON float may survive parsing. Validation uses duplicate-key-safe parsing, validates the complete grammar and depth, and requires byte-identical canonical reserialization. Quality flags contain no duplicates and normalize to declaration order. The record is frozen and hashable. No input is hidden. Lineage remains separate from the calculated numeric record and does not calculate the research value itself.

A sidecar is necessary because existing research records mostly use date-only `as_of_date`, while real inputs have intraday timestamps and individual source identities. Existing research records do not receive lineage fields in 3B. Future 3C transformations will select corrected inputs, require fresh assessments, perform deterministic calculations, produce existing research records, and create `CalculationLineage` sidecars.

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

### Milestone 3C — Transformations

Only after all 3B subphases are reviewed:

- implement pure transformations into existing research records;
- require explicit correction selection;
- require explicit freshness assessments;
- retain `CalculationLineage`;
- apply cross-record snapshot skew;
- use fixed synthetic fixtures before provider integration.

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
7. Implement Milestone 3C transformations.
8. Select a provider only after Milestones 3A–3C are stable.
9. Add recorded provider fixture payloads.
10. Implement one adapter behind the contracts.
11. Review licensing and retention constraints.
12. Separately authorize live-network testing.

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

- Which MIC or listing registry should supply `listing_mic`?
- How should adjusted option deliverables be represented beyond `deliverable_id`?
- What production freshness thresholds apply by category?
- What production calendar-day gap thresholds should account for weekends and holidays?
- Should a future version replace calendar-day gaps with exchange-calendar trading-session counts?
- Should different policies exist for end-of-day research and intraday research?
- Should `AFTER_HOURS` source flags create an explicit policy reason in a later version?
- Should `UNKNOWN_CONDITION` source flags become policy-controlled?
- Should future policies make halted-source handling configurable by category?
- How should semantic observation keys be constructed for every record type in 3C?
- Should cross-record snapshot assessment become a separate public record?
- Which exchange calendar implementation would support trading-session counting?
- Which provider correction schemes expose genuinely comparable numeric revisions?
- Which provider licenses permit retention of correction histories?
- Which rate and dividend methodologies should scenario pricing use?
- Should Convexity Hunter calculate IV and Greeks or initially accept provider-calculated analytics?
- How should historical volatility-surface observations be stored efficiently?
- What raw payload material may legally be retained for each provider?
- When should existing research records receive direct lineage IDs instead of sidecar lineage?
- Should normalized records eventually carry an explicit semantic-observation key in addition to `record_id`?
- Should forecast dividends use one provider model or a system-composite methodology?
