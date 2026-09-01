# Probability-Free Convexity Discrimination v0.1 Contract

## Status

This Tier-A contract is frozen for a later BUILD. It is not implemented by the
current runtime. The current Futu Exact Contract Browser, provider evidence,
selection, Direct Entry, Candidate Assembly, screening, and reporting behavior
remain unchanged.

The frozen target defines a bounded comparison layer between the existing
neutral Browser and explicit human selection. Once built, it will quantify
deterministic expiration payoff geometry under increasingly extreme states. It
will estimate no event probability, expected return, historical reach
frequency, empirical tail probability, historical win rate, or investment
merit.

Independent contract review and targeted re-review have passed. The subsequent
bounded BUILD is `READY` but has not started. This work unit stops before
production implementation.

```text
checkpoint_status = SUBSEQUENT_BUILD_READY
```

At this checkpoint, the production Futu runtime still exports exactly its
existing 22 names. The 30-name Futu API below is the frozen post-BUILD target,
not current runtime state. `convexity_discrimination.py` does not exist in the
production package; its 19-name direct-module API below is likewise a frozen
post-BUILD target.

## Durable product principle

```text
Convexity Hunter does not estimate the probability of an extreme event.
It quantifies the structure's exposure to increasingly extreme states.
```

The v0.1 layer contains no probability field, expected-return field,
historical-frequency field, weighted score, rank, recommendation, or default
selection. Historical observations never become future-probability claims.

## Frozen architecture

```text
FutuExactContractBrowser
    -> pre-selection provider-native quote batch
    -> Probability-Free Convexity Discrimination
    -> explicit human exact-structure selection
    -> existing verification / Direct Entry
```

The existing Browser remains the complete neutral market-availability surface.
It is not modified into a quote collector, scoring engine, ranking engine, or
candidate producer. The quote batch and discrimination result retain the exact
Browser by identity.

The core invariant is:

```text
ComparisonStructure != Candidate
```

A comparison structure exists only to display deterministic conditional payoff
geometry. It is not an `OptionStructure`, `CandidateResearchRecord`, Candidate
Assembly input, Screening input, or reviewed Engine artifact. Only the existing
explicit human-selection function may create an `OptionStructure`.

## Provider pre-selection quote boundary

### Direct-module API

The BUILD appends exactly these eight names to the existing 22-name
`convexity_hunter.providers.futu.__all__`, preserving the existing prefix and
this exact appended order:

```python
__all__ = (
    "initialize_futu_quote_context",
    "FutuExactOptionContractVerification",
    "verify_futu_monthly_option_contract",
    "FutuOptionChainRowStatus",
    "FutuOptionChainExpirationEvidence",
    "FutuOptionChainContractEvidence",
    "FutuOptionChainDiscoveryEvidence",
    "retrieve_futu_option_chain_discovery_evidence",
    "FutuExactContractBrowser",
    "FutuExactContractSelection",
    "create_futu_exact_contract_browser",
    "select_futu_exact_contracts",
    "FutuExactContractSelectionVerification",
    "verify_futu_exact_contract_selection",
    "FutuBboEvidence",
    "FutuDirectEntryBboEvidence",
    "retrieve_futu_direct_entry_bbo_evidence",
    "retrieve_futu_underlying_daily_bars",
    "FutuHistoricalOptionBarEvidence",
    "retrieve_futu_historical_option_bar_evidence",
    "FutuExactOptionAnalyticsActivityEvidence",
    "retrieve_futu_exact_option_analytics_activity_evidence",
    "FutuBrowserQuoteAuthority",
    "FutuBrowserQuoteSemanticState",
    "FutuBrowserQuoteAvailability",
    "FutuBrowserQuoteReasonCode",
    "FutuBrowserQuoteEvidence",
    "FutuBrowserQuoteChunkEvidence",
    "FutuBrowserQuoteBatchEvidence",
    "retrieve_futu_browser_quote_batch_evidence",
)
```

None is re-exported from the package root or `convexity_hunter.providers`.
The existing exact-selection BBO types and function remain unchanged.

### Quote authority and semantic states

```python
class FutuBrowserQuoteAuthority(str, Enum):
    INDICATIVE_ONLY = "indicative_only"


class FutuBrowserQuoteSemanticState(str, Enum):
    UNAVAILABLE = "unavailable"
    NOT_ESTABLISHED = "not_established"
    UNASSIGNED = "unassigned"
    NONE = "none"


class FutuBrowserQuoteAvailability(str, Enum):
    ASK_SIDE_AVAILABLE = "ask_side_available"
    TWO_SIDED_AVAILABLE = "two_sided_available"
    UNAVAILABLE = "unavailable"
```

Every valid batch derives, rather than accepts from a caller, exactly:

```text
authority = INDICATIVE_ONLY
event_time = UNAVAILABLE
freshness = NOT_ESTABLISHED
session_binding = NOT_ESTABLISHED
quote_scope = UNASSIGNED
executable_price_claim = NONE
cross_structure_quote_synchronicity = NOT_ESTABLISHED
```

Adapter receipt time is provenance only. It is not provider observation time,
freshness, regular-session proof, quote scope, synchrony, or executability.
Optional Futu timestamp-field numbers remain opaque provider-native values.

### Quote reason codes

The exact declaration order is:

```python
class FutuBrowserQuoteReasonCode(str, Enum):
    BID_ABSENT = "bid_absent"
    BID_NONPOSITIVE = "bid_nonpositive"
    BID_PRICE_INVALID = "bid_price_invalid"
    BID_SIZE_INVALID = "bid_size_invalid"
    ASK_ABSENT = "ask_absent"
    ASK_NONPOSITIVE = "ask_nonpositive"
    ASK_PRICE_INVALID = "ask_price_invalid"
    ASK_SIZE_INVALID = "ask_size_invalid"
    CROSSED_MARKET = "crossed_market"
    NO_FRAME_RECEIVED = "no_frame_received"
    SUBSCRIPTION_FAILED = "subscription_failed"
    MALFORMED_FRAME = "malformed_frame"
```

Reasons are canonicalized in enum declaration order. No free-form provider
message, raw payload, account data, or credential enters an evidence record or
exception.

### Quote evidence records

```python
@dataclass(frozen=True)
class FutuBrowserQuoteEvidence:
    browser_row: FutuOptionChainContractEvidence
    chunk_index: int
    availability: FutuBrowserQuoteAvailability
    bid_price: Optional[Decimal]
    ask_price: Optional[Decimal]
    bid_size: Optional[int]
    ask_size: Optional[int]
    received_at: Optional[datetime]
    provider_bid_timestamp_value: Optional[Decimal]
    provider_ask_timestamp_value: Optional[Decimal]
    reason_codes: Tuple[FutuBrowserQuoteReasonCode, ...]


@dataclass(frozen=True)
class FutuBrowserQuoteChunkEvidence:
    chunk_index: int
    expiration: date
    requested_rows: Tuple[FutuOptionChainContractEvidence, ...]
    quotes: Tuple[FutuBrowserQuoteEvidence, ...]
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True)
class FutuBrowserQuoteBatchEvidence:
    browser: FutuExactContractBrowser
    chunks: Tuple[FutuBrowserQuoteChunkEvidence, ...]

    @property
    def schema_version(self) -> str: ...

    @property
    def quotes(self) -> Tuple[FutuBrowserQuoteEvidence, ...]: ...

    @property
    def authority(self) -> FutuBrowserQuoteAuthority: ...

    @property
    def event_time(self) -> FutuBrowserQuoteSemanticState: ...

    @property
    def freshness(self) -> FutuBrowserQuoteSemanticState: ...

    @property
    def session_binding(self) -> FutuBrowserQuoteSemanticState: ...

    @property
    def quote_scope(self) -> FutuBrowserQuoteSemanticState: ...

    @property
    def executable_price_claim(self) -> FutuBrowserQuoteSemanticState: ...

    @property
    def cross_structure_quote_synchronicity(
        self,
    ) -> FutuBrowserQuoteSemanticState: ...
```

Each quote retains the exact Browser row by identity. `quotes` is the exact
flattening of chunks and has exactly one item for every `browser.rows` item in
the same Browser order. No row is omitted because no frame arrived or one side
was unavailable.

All present provider prices require exact `Decimal` and finite values. A valid
side size requires an exact positive non-Boolean `int`. All present timestamps
require exact timezone-aware `datetime` normalized to UTC. `chunk_index` is an
exact nonnegative non-Boolean `int`.

Each item must satisfy this exact canonical field matrix. A constructor-bypassed
item that does not satisfy it is rejected before discrimination:

| Classification | Side fields retained | Receipt/timestamp fields | Exact reasons |
| --- | --- | --- | --- |
| `TWO_SIDED_AVAILABLE` | bid/ask prices and sizes all present | `received_at` present; opaque provider timestamp values retained when present | empty |
| `ASK_SIDE_AVAILABLE` | ask price/size present; bid price/size both `None` | `received_at` present; opaque provider timestamp values retained when present | exactly one bid-side reason |
| frame-derived crossed quote | valid bid/ask prices and sizes retained for audit | `received_at` present; opaque provider timestamp values retained when present | exactly `CROSSED_MARKET` |
| frame-derived ask-side or malformed unavailability | all bid/ask price/size fields `None` | `received_at` present; opaque provider timestamp values retained only when the envelope supplied structurally valid numeric values | exactly one applicable ask-side reason or `MALFORMED_FRAME` |
| no frame or subscription failure | all side fields, `received_at`, and provider timestamp values `None` | none | exactly `NO_FRAME_RECEIVED` or `SUBSCRIPTION_FAILED` |

For side classification, each field is validated independently in this fixed
precedence: absent; exact non-Boolean type and finite numeric validity;
strictly-positive price; strictly-positive exact non-Boolean integer size.
Only the first applicable reason for the decisive side is retained. Invalid
discarded bid fields never survive in an `ASK_SIDE_AVAILABLE` record.

### Side-specific availability

Availability is classified in this exact precedence:

1. A structurally malformed frame is `UNAVAILABLE / MALFORMED_FRAME`.
2. Ask-side availability requires a finite strictly positive ask and a valid
   positive ask size. Missing, nonpositive, malformed-price, or invalid-size
   ask produces `UNAVAILABLE` with the corresponding ask reason.
3. After a valid ask, a missing, nonpositive, malformed-price, or invalid-size
   bid produces `ASK_SIDE_AVAILABLE` with the corresponding bid reason.
4. Only after both complete sides have valid positive prices and valid positive
   sizes is crossing evaluated. `bid > ask` produces
   `UNAVAILABLE / CROSSED_MARKET`; `bid <= ask` produces
   `TWO_SIDED_AVAILABLE`.

Thus crossed classification requires complete valid sides. Raw crossed prices
with an invalid ask size take the ask-size reason; raw crossed prices with a
valid ask side but invalid bid size take the bid-size reason. No invalid side
field is retained merely because the raw prices appear crossed.

Consequently:

| Provider frame | Availability | Ask geometry | Relative spread |
| --- | --- | --- | --- |
| `bid = 0`, valid positive ask/ask size | `ASK_SIDE_AVAILABLE` | available | unavailable |
| bid absent, valid positive ask/ask size | `ASK_SIDE_AVAILABLE` | available | unavailable |
| ask absent | `UNAVAILABLE` | unavailable | unavailable |
| ask `<= 0` | `UNAVAILABLE` | unavailable | unavailable |
| valid locked `bid == ask` | `TWO_SIDED_AVAILABLE` | available | exact zero |
| valid positive `bid > ask` | `UNAVAILABLE` | unavailable | unavailable |
| invalid bid size, valid ask side | `ASK_SIDE_AVAILABLE` | available | unavailable |
| invalid ask size | `UNAVAILABLE` | unavailable | unavailable |

Bid unavailability never erases valid ask-side optionality information. Ask
unavailability never receives a zero, midpoint, last-price, or prior-frame
fallback.

### Retrieval and chunking

```python
def retrieve_futu_browser_quote_batch_evidence(
    quote_context: object,
    browser: FutuExactContractBrowser,
    *,
    timeout_seconds: float = 15.0,
) -> FutuBrowserQuoteBatchEvidence: ...
```

The function consumes one dedicated, initially unsubscribed Futu quote context
with the pinned default order-book handler and closes it on every success or
failure path. `timeout_seconds` follows the existing exact BBO boundary: a
finite real non-Boolean value greater than zero and at most 60 seconds. It is a
per-chunk collection timeout, not a freshness threshold.

Before installing its handler, retrieval performs the same pinned private
context preflight as the existing exact BBO path: required methods are
callable, the captured order-book handler is exactly the SDK base handler, the
subscription record is structurally available, and its exact subscription
list is empty. Failure rejects before any subscribe call. Context ownership is
transferred to this operation; no concurrent caller may use it.

Chunking is deterministic and caller-independent:

1. group all Browser rows by exact expiration in Browser order;
2. create exactly one chunk for each distinct expiration;
3. assign zero-based `chunk_index` in ascending Browser expiration order;
4. call Futu subscribe exactly once per chunk with every provider identifier
   in that chunk and `ORDER_BOOK`, `is_first_push=True`, push enabled;
5. retain only the first structurally qualifying frame for each identifier
   after that chunk's successful subscription acknowledgement; never overwrite
   it with a later frame, and ignore normal later pushes for that already
   retained identifier; and
6. retain one unavailable quote item for every requested row that did not
   produce a usable frame before timeout.

Callback ordering is deterministic at the adapter boundary. Immediately before
each subscribe call, the handler activates exactly that chunk's identifier set
and a zero-based monotonic arrival sequence under one lock. Every callback is
serialized through that lock and receives the next arrival ordinal. Frames for
inactive identifiers are ignored; an identifier outside the complete Browser
universe rejects the operation. Because Futu may synchronously emit
`is_first_push` callbacks inside `subscribe`, frames arriving after chunk
activation but before the call returns are held provisionally. A successful
subscribe return opens the acknowledgement barrier and makes those provisional
frames eligible in ordinal order; a failed return discards them and marks the
whole chunk `SUBSCRIPTION_FAILED`. Later callbacks use the same sequence. The
first structurally qualifying eligible frame per requested identifier wins.
The timeout starts at successful subscribe return; it is adapter waiting time,
not provider event time. Chunk state is sealed before the next chunk activates.

Close is attempted exactly once in `finally`. A close failure overrides any
otherwise successful or partially unavailable result with the sanitized
operation-level `RuntimeError`; it does not override an already raised exact
input `TypeError` or `ValueError`, but raw close details never escape. Provider
callback/schema errors observed while a chunk is active seal that chunk and
reject the complete operation before a later chunk starts.

This matches Futu's documented option-subscription accounting: one data type
for multiple options in the same expiration chain consumes one option-chain
subscription quota. The BUILD does not hard-code an account-level quota,
change permissions, or request trading access.

A chunk-level subscription failure produces one
`UNAVAILABLE / SUBSCRIPTION_FAILED` quote for every row in that chunk and then
continues in neutral chunk order. A timeout produces
`UNAVAILABLE / NO_FRAME_RECEIVED` only for missing expected rows. An unexpected
identifier, duplicate Browser/request identity, Browser identity mismatch,
duplicate or missing constructed quote coverage, impossible chunk coverage,
malformed callback envelope, handler-installation failure, or context-close
failure rejects the complete operation. A normal later provider push for an
already retained identifier is not a duplicate-identity error and is ignored.
Raw callback payloads
and provider error text are never returned or persisted.

Frames and legs from different identifiers remain separate observations even
when they belong to one chunk. Chunk membership, adapter receipt times, or one
subscription call does not establish simultaneous market observation.

Constructor-bypass-safe reconstruction requires all of the following:

- chunk indices are exactly contiguous `0..n-1`;
- there is exactly one chunk per Browser expiration, in Browser expiration
  order, with no empty chunk;
- each `requested_rows` tuple contains the exact Browser row objects for that
  expiration in exact Browser order;
- each chunk's `quotes` tuple has the same cardinality and order as
  `requested_rows`;
- every quote's `browser_row is requested_rows[i]` and its `chunk_index` equals
  the enclosing chunk index;
- every Browser row appears in exactly one requested tuple and exactly one
  quote tuple; and
- flattened quotes cover `browser.rows` one-to-one in exact Browser order.

Any duplicate or omission rejects; equality without required object identity
does not satisfy the boundary.

The retrieval does not invoke exact-contract verification, snapshots,
analytics, activity, historical data, Candidate Assembly, Direct Entry, or any
trading method.

## Discrimination module and direct API

The BUILD adds one direct module:

```text
convexity_hunter.convexity_discrimination
```

Its exact `__all__` is:

```python
__all__ = (
    "ComparisonPayoffGrammar",
    "ComparisonCoverageReasonCode",
    "IndicativeMetricStatus",
    "IndicativeMetricUnavailableReason",
    "PayoffGeometryAuthority",
    "ExactDeliverableVerification",
    "ReferencePriceBasis",
    "TemporalAlignmentState",
    "PayoffBranch",
    "ComparisonStructure",
    "NonComparisonBrowserRow",
    "DiscriminationReferencePrice",
    "IndicativePremiumToReferenceRatio",
    "ConditionalPayoffMultipleHurdle",
    "ConvexityResponsePoint",
    "IndicativeRelativeSpread",
    "ComparisonStructureDiscrimination",
    "ProbabilityFreeConvexityDiscriminationResult",
    "discriminate_probability_free_convexity",
)
```

No name is re-exported from the package root. The module is Futu-bounded in
v0.1 and does not create a generic provider framework.

### Closed semantic enums

```python
class ComparisonPayoffGrammar(str, Enum):
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    LONG_STRADDLE = "long_straddle"


class ComparisonCoverageReasonCode(str, Enum):
    OPPOSITE_OPTION_TYPE = "opposite_option_type"
    UNPAIRED_STRADDLE_LEG = "unpaired_straddle_leg"


class IndicativeMetricStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class IndicativeMetricUnavailableReason(str, Enum):
    ASK_SIDE_QUOTE_UNAVAILABLE = "ask_side_quote_unavailable"
    STRADDLE_LEG_ASK_UNAVAILABLE = "straddle_leg_ask_unavailable"
    TWO_SIDED_QUOTE_UNAVAILABLE = "two_sided_quote_unavailable"
    NEGATIVE_UNDERLYING_THRESHOLD = "negative_underlying_threshold"
    NONPOSITIVE_MIDPOINT = "nonpositive_midpoint"


class PayoffGeometryAuthority(str, Enum):
    CONDITIONAL_PROVIDER_STANDARD = "conditional_provider_standard"


class ExactDeliverableVerification(str, Enum):
    NOT_ESTABLISHED = "not_established"


class ReferencePriceBasis(str, Enum):
    LATEST_COMPLETED_NORMALIZED_CLOSE = (
        "latest_completed_normalized_close"
    )


class TemporalAlignmentState(str, Enum):
    NOT_ESTABLISHED = "not_established"


class PayoffBranch(str, Enum):
    DOWNSIDE = "downside"
    UPSIDE = "upside"
```

`CONDITIONAL_PROVIDER_STANDARD` means only that every comparison row already
has exact provider `STANDARD` classification and that v0.1 applies the declared
scalar standard-option payoff grammar for comparison. It does not prove OCC
deliverable contents, corporate-action lineage, settlement, total contract
value, or formal maximum loss.

### Comparison and reference records

```python
@dataclass(frozen=True)
class ComparisonStructure:
    grammar: ComparisonPayoffGrammar
    rows: Tuple[FutuOptionChainContractEvidence, ...]


@dataclass(frozen=True)
class NonComparisonBrowserRow:
    browser_row: FutuOptionChainContractEvidence
    reason_code: ComparisonCoverageReasonCode


@dataclass(frozen=True)
class DiscriminationReferencePrice:
    observation: UnderlyingDailyBarObservation
    latest_completed_session_date: date

    @property
    def basis(self) -> ReferencePriceBasis: ...

    @property
    def close_price(self) -> Decimal: ...
```

A comparison structure contains no `OptionStructure`, quantity, portfolio
value, expected holding days, selected field, candidate field, score, rank, or
recommendation. Its rows are retained by identity from the exact Browser.

Reference construction accepts a tuple of normalized daily bars and requires
exactly one observation satisfying all of:

- exact `UnderlyingDailyBarObservation` type;
- underlying identity equal to the Browser request's exact `UnderlyingKey`;
- `session_date == latest_completed_session_date`;
- `session_date <= discovery_request.evaluation_date`;
- `is_session_complete is True`;
- finite strictly positive exact retained `close_price`;
- Futu normalization version exactly
  `futu-underlying-daily-bar-v0.1`;
- one retained source whose provider is exactly `Futu OpenAPI` and dataset is
  exactly `historical_kline_unadjusted_daily`; and
- intrinsically valid metadata and chronology.

The declared date must also equal the maximum eligible completed session date
present in the supplied tuple for that exact underlying and Futu provenance,
where eligibility means `session_date <= discovery_request.evaluation_date`
and `is_session_complete is True`. If a later eligible completed observation
is present, the caller-declared date is not latest and the operation rejects.
Incomplete or post-evaluation observations never create a later eligible date.

No matching observation, more than one matching observation, identity drift,
an incomplete session, non-Futu provenance, or a latest-completed date after
evaluation rejects before comparison construction. Older retained bars are
permitted but supply no v0.1 historical metric. The exact chosen observation
is retained by identity.

The sole reference basis is:

```text
LATEST_COMPLETED_NORMALIZED_CLOSE
```

Current underlying BBO is prohibited. Every percentage move is described as a
move relative to the declared latest completed close, never current spot or
current market price. Every result derives exactly:

```text
quote_reference_temporal_alignment = NOT_ESTABLISHED
cross_structure_quote_synchronicity = NOT_ESTABLISHED
```

### Metric records

All exact calculated numeric fields use the existing public `ExactRational`.
Provider quote evidence retains its source `Decimal` values. Conversion from a
finite `Decimal` uses its exact coefficient and exponent with no float,
rounding, ambient Decimal-context arithmetic, or display-string reparsing.

```python
@dataclass(frozen=True)
class IndicativePremiumToReferenceRatio:
    status: IndicativeMetricStatus
    aggregate_ask_premium_points: Optional[ExactRational]
    ratio_to_reference: Optional[ExactRational]
    unavailable_reasons: Tuple[IndicativeMetricUnavailableReason, ...]


@dataclass(frozen=True)
class ConditionalPayoffMultipleHurdle:
    gross_value_multiple: int
    side: PayoffBranch
    status: IndicativeMetricStatus
    terminal_underlying_price: Optional[ExactRational]
    absolute_move_from_reference: Optional[ExactRational]
    relative_move_from_reference: Optional[ExactRational]
    unavailable_reasons: Tuple[IndicativeMetricUnavailableReason, ...]


@dataclass(frozen=True)
class ConvexityResponsePoint:
    underlying_shock: ExactRational
    terminal_underlying_price: ExactRational
    status: IndicativeMetricStatus
    gross_expiration_response_multiple: Optional[ExactRational]
    unavailable_reasons: Tuple[IndicativeMetricUnavailableReason, ...]


@dataclass(frozen=True)
class IndicativeRelativeSpread:
    status: IndicativeMetricStatus
    aggregate_bid_premium_points: Optional[ExactRational]
    aggregate_ask_premium_points: Optional[ExactRational]
    midpoint_premium_points: Optional[ExactRational]
    relative_spread: Optional[ExactRational]
    unavailable_reasons: Tuple[IndicativeMetricUnavailableReason, ...]
```

Available records require all numeric fields and an empty reasons tuple.
Unavailable records require every metric-dependent optional numeric field to
be `None` and the exact applicable nonempty canonical reasons tuple. A response
point always retains its exact shock and terminal underlying price even when
the ask-dependent response multiple is unavailable.

Every `unavailable_reasons` tuple is deduplicated and canonicalized in exact
`IndicativeMetricUnavailableReason` declaration order. Caller order is never
retained as semantic order.

### Aggregate records and producer

```python
@dataclass(frozen=True)
class ComparisonStructureDiscrimination:
    structure: ComparisonStructure
    quote_evidence: Tuple[FutuBrowserQuoteEvidence, ...]
    premium_to_reference: IndicativePremiumToReferenceRatio
    payoff_multiple_hurdles: Tuple[ConditionalPayoffMultipleHurdle, ...]
    response_ladder: Tuple[ConvexityResponsePoint, ...]
    indicative_relative_spread: IndicativeRelativeSpread


@dataclass(frozen=True)
class ProbabilityFreeConvexityDiscriminationResult:
    browser: FutuExactContractBrowser
    quote_batch: FutuBrowserQuoteBatchEvidence
    reference_price: DiscriminationReferencePrice
    comparisons: Tuple[ComparisonStructureDiscrimination, ...]
    non_comparison_rows: Tuple[NonComparisonBrowserRow, ...]

    @property
    def schema_version(self) -> str: ...

    @property
    def maturity_authority(self) -> OptionMaturityAuthority: ...

    @property
    def hypothesis_maturity_alignment(
        self,
    ) -> HypothesisMaturityAlignment: ...

    @property
    def payoff_geometry_authority(self) -> PayoffGeometryAuthority: ...

    @property
    def exact_deliverable_verification(
        self,
    ) -> ExactDeliverableVerification: ...

    @property
    def reference_price_basis(self) -> ReferencePriceBasis: ...

    @property
    def quote_reference_temporal_alignment(
        self,
    ) -> TemporalAlignmentState: ...

    @property
    def cross_structure_quote_synchronicity(
        self,
    ) -> TemporalAlignmentState: ...


def discriminate_probability_free_convexity(
    browser: FutuExactContractBrowser,
    quote_batch: FutuBrowserQuoteBatchEvidence,
    underlying_daily_bars: Tuple[UnderlyingDailyBarObservation, ...],
    *,
    latest_completed_session_date: date,
) -> ProbabilityFreeConvexityDiscriminationResult: ...
```

The result requires `quote_batch.browser is browser`. It derives maturity
authority and alignment from
`browser.discovery_evidence.discovery_request`; neither is caller supplied or
copied into Engine evidence. Every quote object used by one comparison retains
the exact corresponding comparison row by identity and is the exact quote
object at that row's position in `quote_batch.quotes`. `quote_evidence` is in
exact `structure.rows` order. `non_comparison_rows` is in exact Browser order.

There is no rank, score, selected, recommendation, candidate-state, screening-
state, or formal-calculation-lineage field.

## Exhaustive mode-to-grammar mapping

The exact accepted `DistributionChangeMode` from the retained discovery
request controls only payoff grammar:

```text
BIDIRECTIONAL_EXPANSION
    -> every valid same-expiration, same-strike, same-lot-size Call/Put pair

EVENT_DIRECTIONAL_UP
EXTREME_TAIL_UP
    -> every Browser Call row as one Long Call comparison

EVENT_DIRECTIONAL_DOWN
EXTREME_TAIL_DOWN
    -> every Browser Put row as one Long Put comparison
```

Directional modes retain opposite-side rows in `non_comparison_rows` with
`OPPOSITE_OPTION_TYPE`. Bidirectional mode retains an unpaired Call or Put in
`non_comparison_rows` with `UNPAIRED_STRADDLE_LEG`. More than one Call or Put
inside the same provider-underlying, expiration, strike, and lot-size group is
ambiguous and rejects rather than choosing a tiebreak.

Comparison order is the neutral order induced by the first row of each
comparison. Rows inside a Straddle are exact Call then Put Browser order.
`comparisons` plus `non_comparison_rows`, when expanded and sorted by exact
Browser position, cover every Browser row exactly once. The layer does not
choose an expiration, strike, ATM reference, Delta, preferred structure, or
default structure and does not hide a Browser row.

## Indicative ask basis

Comparison quantity is fixed to one contract per leg only as a unit comparison
basis. It is not a position-sizing recommendation and is not stored as an
`OptionStructure` quantity.

For valid ask-side quote evidence:

```text
Long Call:     A = Call ask premium points
Long Put:      A = Put ask premium points
Long Straddle: A = Call ask + Put ask premium points
```

The exact aggregation occurs after exact rational conversion. Multiplier is
not used to manufacture a portfolio cost, total entry cost, maximum loss,
affordability fraction, or formal contract value. Lot-size equality is used
only to enforce the existing compatible Straddle identity grammar.

If one Straddle leg lacks ask-side availability, every Straddle ask-dependent
metric is unavailable with `STRADDLE_LEG_ASK_UNAVAILABLE`; both Browser rows
and both quote evidence objects remain retained. If both asks are available
but one or both bids are not two-sided available, ask-based metrics remain
available and only relative spread is unavailable.

## Indicative Premium-to-Reference Ratio

The exact metric name is:

```text
Indicative Premium-to-Reference Ratio
```

For exact ask basis `A` and latest completed close reference `R`:

```text
ratio_to_reference = A / R
```

`R` is strictly positive. The result is an exact rational. It means only the
aggregate provider-native ask points divided by the declared latest completed
close. It is not portfolio affordability, total entry cost, maximum-loss
fraction, `StructureCosts`, or `StructureAffordabilityEvidence`, and it cannot
close `missing_costs`.

## Conditional payoff-multiple hurdles

The exact ordered target multiples are:

```text
1, 2, 5, 10
```

Let `K` be exact strike, `A` the indicative ask basis, `M` one target multiple,
and `R` the latest completed reference close.

```text
Long Call:
    terminal threshold = K + M*A

Long Put:
    unconstrained terminal threshold = K - M*A

Long Straddle:
    lower unconstrained threshold = K - M*A
    upper threshold = K + M*A
```

For every available threshold `S`:

```text
absolute_move_from_reference = S - R
relative_move_from_reference = (S - R) / R
```

These are exact arithmetic thresholds conditional on
`CONDITIONAL_PROVIDER_STANDARD` geometry and the indicative ask basis. They
are not formal break-even prices, total-cost thresholds, expected returns, or
probabilities. User-facing text must say "move relative to the declared latest
completed close reference", never "move from current spot".

An unconstrained downside threshold below zero is retained in canonical
position as `UNAVAILABLE / NEGATIVE_UNDERLYING_THRESHOLD`, with all threshold
and move fields `None`. A zero lower threshold is available. Missing ask basis
retains the complete canonical 4- or 8-record cardinality with unavailable
ask-side reasons and no numeric threshold values.

Canonical ordering is multiple order `1, 2, 5, 10`; within each Straddle
multiple, `DOWNSIDE` then `UPSIDE`. Calls have four upside records, Puts four
downside records, and Straddles eight records.

No `ExpirationPayoffThresholdEvidence` or
`ExpirationPayoffThresholdTransformationResult` is created.

## Convexity Response Ladder

The exact ordered expiration shocks are exact rational values:

```text
-50%, -30%, -20%, -10%, 0%, +10%, +20%, +30%, +50%
```

For reference close `R`:

```text
S = R * (1 + shock)
```

Under the same conditional standard-payoff geometry and ask basis `A`:

```text
Long Call:     max(S - K, 0) / A
Long Put:      max(K - S, 0) / A
Long Straddle: abs(S - K) / A
```

The grid guarantees nonnegative `S`; no clamping is used. The output is gross
expiration response value relative to the indicative ask basis. It includes no
fees, spread cost, exit cost, carrying path, IV repricing, interim valuation,
probability, expected return, scenario likelihood, volatility forecast, or
recommendation.

All nine records remain in exact shock order. Missing ask basis leaves exact
shock and terminal price visible but makes the response multiple unavailable.

## Indicative execution friction

Relative spread exists only when every comparison leg has
`TWO_SIDED_AVAILABLE` evidence:

```text
aggregate_bid = sum exact leg bids
aggregate_ask = sum exact leg asks
midpoint = (aggregate_bid + aggregate_ask) / 2
relative_spread = (aggregate_ask - aggregate_bid) / midpoint
```

Valid two-sided inputs guarantee a positive midpoint. A constructor-bypassed
or otherwise impossible nonpositive midpoint produces
`UNAVAILABLE / NONPOSITIVE_MIDPOINT`; it never divides by zero. A locked quote
produces exact zero spread. A crossed quote was already classified unavailable
at the provider boundary.

The metric is disclosure-only. It has no freshness, synchronization, session,
scope, liquidity-sufficiency, or executable-price claim. It is not
`StructureLiquidity` and cannot close `missing_liquidity`.

## Shared deterministic payoff mathematics

The BUILD must not duplicate Milestone-4 payoff mathematics. It refactors the
existing private exact-rational arithmetic in
`market_data_transformations.py` into exactly these private concepts in that
same module, with names finalized during BUILD but signatures and authority
boundaries frozen here:

```text
private payoff grammar: LONG_CALL | LONG_PUT | LONG_STRADDLE

threshold helper(
    exact private grammar,
    exact strike,
    exact positive per-underlying-unit payoff distance,
    exact ordered positive integer multiples,
) -> canonical conditional threshold branches

terminal-payoff helper(
    exact private grammar,
    exact strike,
    exact nonnegative terminal underlying price,
) -> exact nonnegative gross per-underlying-unit expiration payoff
```

Both helpers are pure exact-rational mathematics, remain outside `__all__`, and
accept no costs object, quote object, reference observation, authority state,
portfolio value, multiplier, or quantity. Public grammar enums are mapped
exhaustively to the private grammar; no stringly typed fallback exists.

The existing formal wrapper continues to:

1. require exact `StructureCostsTransformationResult`;
2. revalidate complete reviewed costs and lineage;
3. derive `total_entry_cost / (quantity * multiplier)`; and
4. pass only that internally derived exact distance to the private threshold
   helper; and
5. construct the unchanged formal `ExpirationPayoffThresholdEvidence` and
   existing methodology/version.

The formal wrapper signature never accepts a caller-supplied payoff distance.
The new indicative path may pass only its internally derived exact ask-basis
distance to the same private threshold helper and use the terminal-payoff
helper for its ladder. It constructs only the new conditional records and
carries the weaker authority state. Sharing private mathematics never allows
the indicative path to call the formal wrapper or weaken its dependency
checks. `market_data_transformations.__all__`, public records, formal producer
signature, lineage identity, methodology version, and golden outputs remain
unchanged.

## Formal artifact isolation

The new result and every nested record are prohibited from:

- `StructureCosts` or `StructureCostsTransformationResult`;
- `StructureLiquidity` or `StructureLiquidityTransformationResult`;
- formal `ExpirationPayoffThresholdEvidence` or its wrapper;
- `StructureAffordabilityEvidence` or its assessment wrapper;
- `CandidateResearchRecord`;
- Candidate Assembly artifact inputs;
- Screening inputs or reason resolution; and
- calculation lineage for formal reviewed artifacts.

The new types are not added to Candidate Assembly's exact seven-artifact union.
No conversion or adapter from the new records to a formal artifact is added.
Exact-type validation makes accidental substitution fail. The six existing
reasons remain unchanged and unresolved:

```text
missing_costs
missing_liquidity
missing_volatility_environment
missing_structure_expiration_tail_slice
missing_target_move_scenario
missing_volatility_crush_scenario
```

Indicative Premium-to-Reference Ratio does not use portfolio value, fees,
commissions, multiplier-scaled total cost, repeated attempts, or caller risk
boundaries. It therefore cannot be called affordability or maximum loss.

## Maturity preservation

The exact maturity request remains reachable by identity through the retained
Browser. The result derives, never accepts, maturity authority and alignment.

For `NEUTRAL_STRUCTURAL_RESEARCH`:

```text
hypothesis_maturity_alignment = NOT_ESTABLISHED
```

No payoff shape, low ask ratio, large response multiple, narrow indicative
spread, human interest, or later exact verification may upgrade that state.
The state remains a separate research-context disclosure and never enters the
conditional payoff calculation.

## Data-authority matrix

| Input or output | Formal existing Engine authority | v0.1 discrimination authority | Prohibited claim |
| --- | --- | --- | --- |
| Browser exact identity, expiry, strike | exact listed-identity context only; reference remains incomplete | comparison identity and grammar | deliverable completion or merit |
| Futu provider `STANDARD` | provider classification only | conditional standard-payoff geometry | exact OCC deliverable proof |
| Provider-native ask and size | no canonical quote | ask-side `INDICATIVE_ONLY` basis | freshness, executable price, total cost |
| Provider-native bid/ask and sizes | no canonical quote or liquidity | optional indicative relative spread | `StructureLiquidity`, NBBO, scope |
| Latest completed normalized close | formal normalized daily-bar observation | sole exact dated reference close | current spot or time alignment |
| Provider multiplier/lot size | retained provider identity field only while deliverable is incomplete | Straddle compatibility disclosure; no cost scaling | total position cost or maximum loss |
| Completed unadjusted daily bars | formal raw observations under existing contracts | only one exact latest close | adjusted return history |
| Adjusted history | unavailable | unavailable | extreme-return integrity |
| IV and Greeks | provider-native semantics incomplete | unavailable | probability, scenario, or response input |
| Volume and open interest | provider-native date/session semantics incomplete | unavailable | liquidity qualification |
| Hurdles and ladder | formal only through existing reviewed wrappers where applicable | exact arithmetic, conditional and indicative only | expected return or formal evidence |

## Historical and other deferred metrics

v0.1 explicitly defers:

- Historical Extreme Envelope;
- Historical Shock Replay;
- every historical frequency, reach count, empirical probability, or win rate;
- IV, Greeks, volume, and open interest;
- carry burden or premium-per-day;
- Pareto dominance;
- weighted or unweighted aggregate scores;
- automatic Candidate Generation; and
- ranking, recommendation, or default selection.

Current Futu bars are completed but unadjusted. Splits and other corporate
actions can create false raw-return extremes. v0.1 performs no anomaly filter,
corporate-action inference, adjusted-price reconstruction, or historical-tail
calculation.

## NDAQ offline golden fixture

The BUILD must create a synthetic sanitized fixture reproducing only the
recorded cardinality and identities needed for the contract:

```text
underlying: NDAQ
DistributionChangeMode: BIDIRECTIONAL_EXPANSION
maturity authority: NEUTRAL_STRUCTURAL_RESEARCH
hypothesis maturity alignment: NOT_ESTABLISHED
Browser rows: 162
same-strike Call/Put groups: 81
comparison Long Straddles: 81
non-comparison rows: 0
```

The fixture preserves the recorded three-expiration neutral ordering and exact
Call-before-Put pair order without using or persisting live provider payload.
It proves no contract is selected, ranked, hidden, promoted, or recommended.
Futu is not called.

## Validation precedence

The BUILD freezes this order:

1. exact direct-module input types and constructor-bypass-safe intrinsic
   reconstruction;
2. exact Browser and discovery-request validity;
3. exact quote-batch Browser identity and complete row/chunk coverage;
4. exact reference-bar container, item, identity, provenance, completeness,
   uniqueness, and chronology;
5. exhaustive mode-to-grammar and row-coverage construction;
6. exact quote-item identity and availability reconstruction;
7. exact rational conversion and metric arithmetic;
8. complete metric cardinality, ordering, status, reasons, and authority
   validation; and
9. immutable result construction.

Wrong exact Python, enum, container, or item types raise `TypeError`. Invalid
identity, chronology, provider response, semantic state, arithmetic,
cardinality, ordering, or intrinsic reconstruction raises controlled
`ValueError` or the existing sanitized provider `RuntimeError` boundary. Raw
`AttributeError`, `KeyError`, `IndexError`, provider payload, or provider error
text never escapes.

## Decisive contract tests

The BUILD must include deterministic tests for at least:

1. all five `DistributionChangeMode` grammar mappings;
2. exhaustive Browser row preservation and neutral order;
3. 162 NDAQ rows producing exactly 81 Straddles;
4. valid ask plus zero bid: ask metrics available, spread unavailable;
5. valid ask plus absent bid: ask metrics available;
6. missing or nonpositive ask: ask metrics unavailable;
7. one missing Straddle ask: all pair ask metrics unavailable;
8. two asks plus one missing bid: payoff metrics available, spread unavailable;
9. valid locked quote: exact zero spread;
10. crossed quote: complete quote unavailable;
11. malformed quote price and size fields with side-specific precedence;
12. unexpected, duplicate, missing, and chunk-mismatched identifiers, plus
    contiguous chunk/request/quote identity and complete-coverage reconstruction;
13. reference close missing, duplicate, incomplete, wrong-provider, or identity
    mismatch, and a declared date older than a later eligible supplied complete
    Futu observation;
14. latest completed date after evaluation rejection;
15. quote/reference and cross-structure alignment staying `NOT_ESTABLISHED`;
16. literal exact 1x/2x/5x/10x rational goldens;
17. negative Put/Straddle downside branch unavailable and zero branch available;
18. literal nine-point response-ladder ordering and no float/context drift;
19. exact-deliverable status remaining conditional/unverified;
20. no formal costs, liquidity, threshold, or affordability construction;
21. Candidate Assembly rejecting every indicative discrimination type;
22. all six `missing_*` reasons remaining unchanged;
23. `NOT_ESTABLISHED` maturity alignment never upgrading;
24. absence of rank, score, selected, recommendation, and default fields;
25. constructor-bypass, forged-identity, and malformed-sidecar failures;
26. shared private payoff-kernel golden equivalence with the unchanged formal
    Milestone-4 outputs; and
27. synchronous first-push callbacks during `subscribe`, later-push ignoring,
    failed-ack provisional-frame discard, and serialized arrival ordering; and
28. quote contexts closing on success and every failure path, including exact
    close/error precedence.

Golden tests use literal expected exact rationals and independently computed
fixture values; they must not compare a producer against the same helper used
to generate the expected result.

## Versioning and compatibility

The frozen versions are:

```text
Futu Browser quote batch schema:
    futu-browser-provider-native-quote-batch-v0.1

Probability-Free Convexity Discrimination schema:
    probability-free-convexity-discrimination-v0.1
```

This is an additive future API. Existing Browser v0.2, option-chain request,
selection, selection verification, Direct Entry, candidate, screening,
reporting, `market_data`, transformation, and risk-assessment schemas remain
unchanged. There is no persisted-artifact migration, legacy decoder, automatic
upgrade, compatibility adapter, or package-root export.

The first BUILD may add only:

- the bounded provider quote records/retrieval in `providers/futu.py`;
- the new `convexity_discrimination.py` module;
- the private shared payoff-kernel refactor with unchanged formal behavior;
- focused synthetic tests; and
- proportional contract/state documentation updates.

It may not add provider routing, historical adjustment, a generic metric
framework, UI ranking, report integration, Candidate integration, or live
fixtures.

## Independent review challenge set

Independent contract review must specifically challenge:

- accidental affordability or maximum-loss semantics;
- accidental exact-deliverable or settlement claims;
- zero/absent-bid handling for far-tail options;
- asynchronous cross-leg, cross-row, and quote/reference misuse;
- incomplete Browser-row or chunk coverage;
- formal artifact or Candidate Assembly leakage;
- hidden ranking, recommendation, or default-selection semantics;
- duplicated Milestone-4 mathematics or weakened formal costs dependency;
- maturity-alignment upgrade; and
- constructor-bypass error leakage.

Accepted findings are corrected in the contract and receive targeted
re-review. No production implementation begins before that review passes.

### Review result

The independent read-only review initially returned `FAIL` with six accepted
findings: latest-close authority, synchronous callback/acknowledgement ordering,
constructor-bypass chunk identity and coverage, the shared private payoff-math
authority boundary, crossed-price versus invalid-size precedence, and canonical
tuple ordering. This contract incorporates all six corrections. Targeted
re-review returned `PASS` with no unresolved or new blocking finding.

## Explicit non-goals

This contract adds no production code, live provider call, exact human
selection, Candidate generation, screening change, report output, historical
stress, probability, expected return, score, rank, recommendation, portfolio
affordability, position sizing, monitoring, trading, provider routing, or
resolution of any current `missing_*` gap.
