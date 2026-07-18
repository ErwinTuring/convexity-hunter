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

## 11. Freshness policy

Production freshness ages are intentionally not defined in v0.1.

The planned immutable `MarketDataFreshnessPolicy` contains:

```text
policy_id
policy_version
maximum_quote_age_seconds
maximum_analytics_age_seconds
maximum_retrieval_lag_seconds
maximum_cross_record_skew_seconds
maximum_rate_age_seconds
maximum_dividend_age_seconds
allow_delayed_data
require_regular_session_quotes
require_completed_historical_sessions
```

The planned explicit `FreshnessContext` contains:

```text
evaluation_at
latest_completed_session_date
```

Rules:

- `evaluation_at` is supplied explicitly; freshness never calls the wall clock internally.
- The same record may receive a different assessment at another evaluation time.
- Stale records remain auditable but are ineligible for a current screen.
- Stale is not the same as structurally invalid.
- Missing observation timestamps produce an ineligible or unknown result, never an invented timestamp.
- Delayed-data eligibility depends on policy.
- Policy ID and version make assessments reproducible.

The planned `FreshnessAssessment` fields are:

```text
status
reason_codes
policy_id
policy_version
evaluated_at
```

Statuses are:

```text
fresh
stale
ineligible
unknown
```

Numerical default ages require separate review before implementation.

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

## 13. Corrections, revisions, and duplicates

- Repeated retrieval of one provider record is not automatically a new market observation.
- A provider correction carries the `corrected` flag and either a positive revision number or a provider correction ID.
- Corrections never silently overwrite historical audit records.
- Selecting the latest revision requires a deterministic rule.
- Duplicate normalized record IDs are invalid.
- Records sharing a semantic key and observation time require explicit resolution.
- Downstream calculation lineage retains the selected source revision.

`record_id` identifies one immutable normalized-record version. A corrected normalized value receives a new `NormalizationMetadata.record_id` and references the corrected `SourceReference`; the previous normalized record remains immutable. The new record's normalization methodology identifies the semantic observation being corrected. Equal semantic keys and observation times do not imply equal values, so conflicting records require deterministic resolution.

The latest correction may be selected only by a deterministic revision-resolution rule. That rule must not rely on file order, retrieval order, insertion order, set ordering, or dictionary ordering. Freshness checks and calculations retain the selected source revision in later `CalculationLineage`. Mutable overwrite is prohibited, and v0.1 defines no global record registry.

## 14. Calculation lineage

The planned immutable `CalculationLineage` sidecar contains:

```text
calculation_id
calculation_type
methodology_id
methodology_version
calculated_at
input_record_ids
input_source_ids
parameters
quality_flags
```

Requirements:

- Input IDs are non-empty, unique, and deterministically ordered.
- Methodology ID and version are immutable.
- Parameters are serializable and ordered.
- `calculated_at` is timezone-aware UTC and not earlier than any input normalization time.
- No input is hidden and a calculation cannot cite itself.
- Lineage remains separate from the calculated numeric record.

A sidecar is necessary because existing research records mostly use date-only `as_of_date`, while real inputs have intraday timestamps and individual source identities. `CandidateResearchRecord` must not be expanded or mutated merely to hold provider metadata. The sidecar preserves detail without changing existing domain contracts.

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

### Milestone 3B — Freshness and lineage

After Milestone 3A.3 review:

- finalize freshness-threshold field types;
- define freshness reason codes and canonical ordering;
- implement deterministic freshness assessment;
- finalize canonical serialization of `CalculationLineage.parameters`;
- implement `CalculationLineage`.

### Milestone 3C — Transformations

After Milestone 3B review:

- implement pure transformations into existing research records;
- preserve calculation lineage;
- validate transformations with synthetic fixtures.

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
4. Finalize and implement Milestone 3B freshness and lineage.
5. Implement Milestone 3C transformations.
6. Select a provider only after Milestones 3A–3C are stable.
7. Add recorded provider fixture payloads.
8. Implement one adapter behind the contracts.
9. Review licensing and retention constraints.
10. Separately authorize live-network testing.

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
- What exact freshness thresholds should apply by market phase?
- What freshness reason codes and canonical ordering are required?
- Should delayed data ever be eligible for screening?
- How should `CalculationLineage.parameters` be serialized canonically?
- Which source has priority when providers disagree?
- Which exchange-calendar implementation should be used?
- Which rate and dividend methodologies should scenario pricing use?
- Should Convexity Hunter calculate IV and Greeks or initially accept provider-calculated analytics?
- How should historical volatility-surface observations be stored efficiently?
- What raw payload material may legally be retained for each provider?
- When should existing research records receive direct lineage IDs instead of sidecar lineage?
- Should future composite freshness use the oldest source observation time, the effective observation time, or both?
- What deterministic revision-selection rule should choose among provider corrections?
- Should normalized records eventually carry an explicit semantic-observation key in addition to `record_id`?
- Should forecast dividends use one provider model or a system-composite methodology?
