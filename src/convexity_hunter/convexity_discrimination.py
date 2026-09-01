"""Probability-free conditional payoff geometry for neutral Browser rows."""

import datetime
import decimal
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .event_intelligence import DistributionChangeMode
from .market_data import (
    DataOrigin,
    NormalizationMetadata,
    NormalizationQualityFlag,
    SourceReference,
    UnderlyingDailyBarObservation,
)
from .market_data_transformations import (
    ExactRational,
    _PayoffMathBranch,
    _PayoffMathGrammar,
    _conditional_threshold_prices,
    _exact_rational_from_decimal,
    _gross_expiration_payoff,
    _rational_add,
    _rational_divide,
    _rational_divide_int,
    _rational_multiply,
    _rational_subtract,
    _strict_expiration_exact_rational,
)
from .option_chain_discovery import (
    HypothesisMaturityAlignment,
    OptionMaturityAuthority,
)
from .providers.futu import (
    FutuBrowserQuoteAvailability,
    FutuBrowserQuoteBatchEvidence,
    FutuBrowserQuoteEvidence,
    FutuExactContractBrowser,
    FutuOptionChainContractEvidence,
    _validate_exact_contract_browser,
)


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


_SCHEMA_VERSION = "probability-free-convexity-discrimination-v0.1"
_HURDLE_MULTIPLES = (1, 2, 5, 10)
_RESPONSE_SHOCKS = tuple(
    ExactRational(value, 100) for value in (-50, -30, -20, -10, 0, 10, 20, 30, 50)
)
_FUTU_DAILY_BAR_VERSION = "futu-underlying-daily-bar-v0.1"
_FUTU_PROVIDER = "Futu OpenAPI"
_FUTU_DATASET = "historical_kline_unadjusted_daily"


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
    LATEST_COMPLETED_NORMALIZED_CLOSE = "latest_completed_normalized_close"


class TemporalAlignmentState(str, Enum):
    NOT_ESTABLISHED = "not_established"


class PayoffBranch(str, Enum):
    DOWNSIDE = "downside"
    UPSIDE = "upside"


_METRIC_REASON_ORDER = {
    item: index for index, item in enumerate(IndicativeMetricUnavailableReason)
}


def _strict_metric_reasons(
    value: object,
) -> Tuple[IndicativeMetricUnavailableReason, ...]:
    if type(value) is not tuple:
        raise TypeError("unavailable_reasons must have exact type tuple")
    if any(type(item) is not IndicativeMetricUnavailableReason for item in value):
        raise TypeError(
            "unavailable_reasons items must have exact enum type"
        )
    if len(set(value)) != len(value) or value != tuple(
        sorted(value, key=_METRIC_REASON_ORDER.__getitem__)
    ):
        raise ValueError("unavailable_reasons must be canonical")
    return value


def _strict_rational(value: object, label: str) -> ExactRational:
    return _strict_expiration_exact_rational(value, label)


def _strict_optional_rational(
    value: object, label: str
) -> Optional[ExactRational]:
    if value is None:
        return None
    return _strict_rational(value, label)


def _strict_comparison_row(
    value: object,
) -> FutuOptionChainContractEvidence:
    if type(value) is not FutuOptionChainContractEvidence:
        raise TypeError(
            "comparison rows must have exact type FutuOptionChainContractEvidence"
        )
    try:
        rebuilt = FutuOptionChainContractEvidence(
            value.provider_identifier,
            value.provider_underlying,
            value.expiration,
            value.option_type,
            value.strike,
            value.lot_size,
            value.provider_expiration_cycle,
            value.provider_standard_type,
            value.suspension,
            value.statuses,
            value.retrieved_at,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("comparison row is malformed") from error
    if (
        rebuilt != value
        or value.provider_expiration_cycle != "MONTH"
        or value.provider_standard_type != "STANDARD"
        or value.suspension
    ):
        raise ValueError("comparison row is not provider-standard eligible")
    return value


@dataclass(frozen=True)
class ComparisonStructure:
    grammar: ComparisonPayoffGrammar
    rows: Tuple[FutuOptionChainContractEvidence, ...]

    def __post_init__(self) -> None:
        if type(self.grammar) is not ComparisonPayoffGrammar:
            raise TypeError("grammar must have exact type ComparisonPayoffGrammar")
        if type(self.rows) is not tuple:
            raise TypeError("rows must have exact type tuple")
        rows = tuple(_strict_comparison_row(row) for row in self.rows)
        expected_count = 2 if self.grammar is ComparisonPayoffGrammar.LONG_STRADDLE else 1
        if len(rows) != expected_count:
            raise ValueError("comparison row cardinality is invalid")
        if self.grammar is ComparisonPayoffGrammar.LONG_CALL:
            if rows[0].option_type != "call":
                raise ValueError("Long Call requires one Call row")
        elif self.grammar is ComparisonPayoffGrammar.LONG_PUT:
            if rows[0].option_type != "put":
                raise ValueError("Long Put requires one Put row")
        else:
            call, put = rows
            if (
                call.option_type != "call"
                or put.option_type != "put"
                or call.provider_underlying != put.provider_underlying
                or call.expiration != put.expiration
                or call.strike != put.strike
                or call.lot_size != put.lot_size
            ):
                raise ValueError("Long Straddle rows are incompatible")


@dataclass(frozen=True)
class NonComparisonBrowserRow:
    browser_row: FutuOptionChainContractEvidence
    reason_code: ComparisonCoverageReasonCode

    def __post_init__(self) -> None:
        _strict_comparison_row(self.browser_row)
        if type(self.reason_code) is not ComparisonCoverageReasonCode:
            raise TypeError(
                "reason_code must have exact type ComparisonCoverageReasonCode"
            )


def _strict_source(value: object) -> SourceReference:
    if type(value) is not SourceReference:
        raise TypeError("source reference must have exact type SourceReference")
    try:
        rebuilt = SourceReference(
            value.source_id,
            value.provider_name,
            value.dataset_name,
            value.provider_record_id,
            value.provider_request_id,
            value.source_symbol,
            value.source_uri,
            value.observed_at,
            value.retrieved_at,
            value.provider_timezone,
            value.timestamp_methodology,
            value.origin,
            value.is_delayed,
            value.declared_delay_seconds,
            value.payload_sha256,
            value.revision_number,
            value.provider_correction_id,
            value.quality_flags,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("reference source is malformed") from error
    if rebuilt != value:
        raise ValueError("reference source is not intrinsically valid")
    return value


def _strict_metadata(value: object) -> NormalizationMetadata:
    if type(value) is not NormalizationMetadata:
        raise TypeError("metadata must have exact type NormalizationMetadata")
    sources = tuple(_strict_source(item) for item in value.source_references)
    try:
        rebuilt = NormalizationMetadata(
            value.record_id,
            sources,
            value.effective_observed_at,
            value.normalized_at,
            value.record_origin,
            value.normalization_methodology,
            value.unit_convention,
            value.normalization_version,
            value.quality_flags,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("reference metadata is malformed") from error
    if rebuilt != value:
        raise ValueError("reference metadata is not intrinsically valid")
    return value


def _strict_reference_observation(value: object) -> UnderlyingDailyBarObservation:
    if type(value) is not UnderlyingDailyBarObservation:
        raise TypeError(
            "daily bars must have exact type UnderlyingDailyBarObservation"
        )
    metadata = _strict_metadata(value.metadata)
    try:
        rebuilt = UnderlyingDailyBarObservation(
            value.underlying_key,
            value.session_date,
            value.open_price,
            value.high_price,
            value.low_price,
            value.close_price,
            value.adjusted_close_price,
            value.volume,
            value.is_session_complete,
            value.adjustment_methodology,
            metadata,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("reference observation is malformed") from error
    if rebuilt != value:
        raise ValueError("reference observation is not intrinsically valid")
    return value


@dataclass(frozen=True)
class DiscriminationReferencePrice:
    observation: UnderlyingDailyBarObservation
    latest_completed_session_date: datetime.date

    def __post_init__(self) -> None:
        observation = _strict_reference_observation(self.observation)
        if type(self.latest_completed_session_date) is not datetime.date:
            raise TypeError("latest_completed_session_date must have exact type date")
        sources = observation.metadata.source_references
        if (
            observation.session_date != self.latest_completed_session_date
            or not observation.is_session_complete
            or observation.adjusted_close_price is not None
            or observation.adjustment_methodology is not None
            or type(observation.close_price) is not decimal.Decimal
            or not observation.close_price.is_finite()
            or observation.close_price <= 0
            or observation.metadata.normalization_version != _FUTU_DAILY_BAR_VERSION
            or observation.metadata.record_origin is not DataOrigin.EXCHANGE_OBSERVED
            or observation.metadata.quality_flags
            != (NormalizationQualityFlag.SYMBOL_MAPPED,)
            or len(sources) != 1
            or sources[0].provider_name != _FUTU_PROVIDER
            or sources[0].dataset_name != _FUTU_DATASET
            or sources[0].quality_flags
        ):
            raise ValueError("reference observation lacks frozen authority")

    @property
    def basis(self) -> ReferencePriceBasis:
        return ReferencePriceBasis.LATEST_COMPLETED_NORMALIZED_CLOSE

    @property
    def close_price(self) -> decimal.Decimal:
        return self.observation.close_price


@dataclass(frozen=True)
class IndicativePremiumToReferenceRatio:
    status: IndicativeMetricStatus
    aggregate_ask_premium_points: Optional[ExactRational]
    ratio_to_reference: Optional[ExactRational]
    unavailable_reasons: Tuple[IndicativeMetricUnavailableReason, ...]

    def __post_init__(self) -> None:
        _validate_metric_record(
            self.status,
            (self.aggregate_ask_premium_points, self.ratio_to_reference),
            self.unavailable_reasons,
        )


@dataclass(frozen=True)
class ConditionalPayoffMultipleHurdle:
    gross_value_multiple: int
    side: PayoffBranch
    status: IndicativeMetricStatus
    terminal_underlying_price: Optional[ExactRational]
    absolute_move_from_reference: Optional[ExactRational]
    relative_move_from_reference: Optional[ExactRational]
    unavailable_reasons: Tuple[IndicativeMetricUnavailableReason, ...]

    def __post_init__(self) -> None:
        if type(self.gross_value_multiple) is not int:
            raise TypeError("gross_value_multiple must have exact type int")
        if self.gross_value_multiple not in _HURDLE_MULTIPLES:
            raise ValueError("gross_value_multiple is unsupported")
        if type(self.side) is not PayoffBranch:
            raise TypeError("side must have exact type PayoffBranch")
        _validate_metric_record(
            self.status,
            (
                self.terminal_underlying_price,
                self.absolute_move_from_reference,
                self.relative_move_from_reference,
            ),
            self.unavailable_reasons,
            allow_negative_threshold_reason=True,
        )
        if (
            self.status is IndicativeMetricStatus.AVAILABLE
            and self.terminal_underlying_price.numerator < 0
        ):
            raise ValueError("terminal underlying price must be nonnegative")


@dataclass(frozen=True)
class ConvexityResponsePoint:
    underlying_shock: ExactRational
    terminal_underlying_price: ExactRational
    status: IndicativeMetricStatus
    gross_expiration_response_multiple: Optional[ExactRational]
    unavailable_reasons: Tuple[IndicativeMetricUnavailableReason, ...]

    def __post_init__(self) -> None:
        shock = _strict_rational(self.underlying_shock, "underlying_shock")
        terminal = _strict_rational(
            self.terminal_underlying_price, "terminal_underlying_price"
        )
        if shock not in _RESPONSE_SHOCKS or terminal.numerator < 0:
            raise ValueError("response point domain is invalid")
        _validate_metric_record(
            self.status,
            (self.gross_expiration_response_multiple,),
            self.unavailable_reasons,
        )


@dataclass(frozen=True)
class IndicativeRelativeSpread:
    status: IndicativeMetricStatus
    aggregate_bid_premium_points: Optional[ExactRational]
    aggregate_ask_premium_points: Optional[ExactRational]
    midpoint_premium_points: Optional[ExactRational]
    relative_spread: Optional[ExactRational]
    unavailable_reasons: Tuple[IndicativeMetricUnavailableReason, ...]

    def __post_init__(self) -> None:
        _validate_metric_record(
            self.status,
            (
                self.aggregate_bid_premium_points,
                self.aggregate_ask_premium_points,
                self.midpoint_premium_points,
                self.relative_spread,
            ),
            self.unavailable_reasons,
            allow_nonpositive_midpoint_reason=True,
        )


def _validate_metric_record(
    status: object,
    values: tuple,
    reasons: object,
    *,
    allow_negative_threshold_reason: bool = False,
    allow_nonpositive_midpoint_reason: bool = False,
) -> None:
    if type(status) is not IndicativeMetricStatus:
        raise TypeError("status must have exact type IndicativeMetricStatus")
    reasons = _strict_metric_reasons(reasons)
    if status is IndicativeMetricStatus.AVAILABLE:
        if reasons or any(type(item) is not ExactRational for item in values):
            raise ValueError("available metric requires complete exact values")
        for index, item in enumerate(values):
            _strict_rational(item, f"metric_value_{index}")
    else:
        if not reasons or any(item is not None for item in values):
            raise ValueError("unavailable metric requires no optional values")
        permitted = {
            IndicativeMetricUnavailableReason.ASK_SIDE_QUOTE_UNAVAILABLE,
            IndicativeMetricUnavailableReason.STRADDLE_LEG_ASK_UNAVAILABLE,
            IndicativeMetricUnavailableReason.TWO_SIDED_QUOTE_UNAVAILABLE,
        }
        if allow_negative_threshold_reason:
            permitted.add(
                IndicativeMetricUnavailableReason.NEGATIVE_UNDERLYING_THRESHOLD
            )
        if allow_nonpositive_midpoint_reason:
            permitted.add(IndicativeMetricUnavailableReason.NONPOSITIVE_MIDPOINT)
        if any(item not in permitted for item in reasons):
            raise ValueError("metric unavailable reason is invalid")


@dataclass(frozen=True)
class ComparisonStructureDiscrimination:
    structure: ComparisonStructure
    quote_evidence: Tuple[FutuBrowserQuoteEvidence, ...]
    premium_to_reference: IndicativePremiumToReferenceRatio
    payoff_multiple_hurdles: Tuple[ConditionalPayoffMultipleHurdle, ...]
    response_ladder: Tuple[ConvexityResponsePoint, ...]
    indicative_relative_spread: IndicativeRelativeSpread

    def __post_init__(self) -> None:
        if type(self.structure) is not ComparisonStructure:
            raise TypeError("structure must have exact type ComparisonStructure")
        ComparisonStructure(self.structure.grammar, self.structure.rows)
        if type(self.quote_evidence) is not tuple or any(
            type(item) is not FutuBrowserQuoteEvidence
            for item in self.quote_evidence
        ):
            raise TypeError("quote_evidence must contain exact quote records")
        if len(self.quote_evidence) != len(self.structure.rows) or any(
            quote.browser_row is not row
            for quote, row in zip(self.quote_evidence, self.structure.rows)
        ):
            raise ValueError("quote_evidence must retain exact structure rows")
        if type(self.premium_to_reference) is not IndicativePremiumToReferenceRatio:
            raise TypeError("premium_to_reference has wrong exact type")
        if type(self.payoff_multiple_hurdles) is not tuple or any(
            type(item) is not ConditionalPayoffMultipleHurdle
            for item in self.payoff_multiple_hurdles
        ):
            raise TypeError("payoff_multiple_hurdles has wrong exact type")
        expected_hurdles = 8 if self.structure.grammar is ComparisonPayoffGrammar.LONG_STRADDLE else 4
        if len(self.payoff_multiple_hurdles) != expected_hurdles:
            raise ValueError("payoff hurdle cardinality is invalid")
        if type(self.response_ladder) is not tuple or any(
            type(item) is not ConvexityResponsePoint for item in self.response_ladder
        ):
            raise TypeError("response_ladder has wrong exact type")
        if tuple(item.underlying_shock for item in self.response_ladder) != _RESPONSE_SHOCKS:
            raise ValueError("response ladder ordering is invalid")
        if type(self.indicative_relative_spread) is not IndicativeRelativeSpread:
            raise TypeError("indicative_relative_spread has wrong exact type")


@dataclass(frozen=True)
class ProbabilityFreeConvexityDiscriminationResult:
    browser: FutuExactContractBrowser
    quote_batch: FutuBrowserQuoteBatchEvidence
    reference_price: DiscriminationReferencePrice
    comparisons: Tuple[ComparisonStructureDiscrimination, ...]
    non_comparison_rows: Tuple[NonComparisonBrowserRow, ...]

    def __post_init__(self) -> None:
        try:
            raw_browser = self.browser
            raw_quote_batch = self.quote_batch
            raw_reference = self.reference_price
            raw_comparisons = self.comparisons
            raw_non_comparisons = self.non_comparison_rows
        except AttributeError as error:
            raise ValueError("discrimination result is malformed") from error
        browser = _validate_exact_contract_browser(raw_browser)
        if type(raw_quote_batch) is not FutuBrowserQuoteBatchEvidence:
            raise TypeError("quote_batch has wrong exact type")
        try:
            FutuBrowserQuoteBatchEvidence(
                raw_quote_batch.browser, raw_quote_batch.chunks
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("quote_batch is malformed") from error
        if raw_quote_batch.browser is not browser:
            raise ValueError("quote_batch must retain the exact Browser")
        if type(raw_reference) is not DiscriminationReferencePrice:
            raise TypeError("reference_price has wrong exact type")
        try:
            DiscriminationReferencePrice(
                raw_reference.observation,
                raw_reference.latest_completed_session_date,
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("reference_price is malformed") from error
        request = browser.discovery_evidence.discovery_request
        if (
            raw_reference.observation.underlying_key
            != request.underlying_key
            or raw_reference.latest_completed_session_date
            > request.evaluation_date
        ):
            raise ValueError("reference price identity or chronology mismatch")
        if type(raw_comparisons) is not tuple or any(
            type(item) is not ComparisonStructureDiscrimination
            for item in raw_comparisons
        ):
            raise TypeError("comparisons has wrong exact type")
        if type(raw_non_comparisons) is not tuple or any(
            type(item) is not NonComparisonBrowserRow
            for item in raw_non_comparisons
        ):
            raise TypeError("non_comparison_rows has wrong exact type")
        expected_comparisons, expected_non_comparisons = _build_discriminations(
            browser,
            raw_quote_batch,
            raw_reference,
        )
        if len(raw_comparisons) != len(expected_comparisons):
            raise ValueError("comparisons do not match canonical discrimination")
        try:
            for actual, expected in zip(raw_comparisons, expected_comparisons):
                ComparisonStructureDiscrimination(
                    actual.structure,
                    actual.quote_evidence,
                    actual.premium_to_reference,
                    actual.payoff_multiple_hurdles,
                    actual.response_ladder,
                    actual.indicative_relative_spread,
                )
                if len(actual.quote_evidence) != len(expected.quote_evidence) or any(
                    actual_quote is not expected_quote
                    for actual_quote, expected_quote in zip(
                        actual.quote_evidence, expected.quote_evidence
                    )
                ):
                    raise ValueError("comparison quote identity is invalid")
            if len(raw_non_comparisons) != len(expected_non_comparisons) or any(
                actual.browser_row is not expected.browser_row
                for actual, expected in zip(
                    raw_non_comparisons, expected_non_comparisons
                )
            ):
                raise ValueError("non-comparison Browser identity is invalid")
        except AttributeError as error:
            raise ValueError("discrimination result is malformed") from error
        if raw_comparisons != expected_comparisons:
            raise ValueError("comparisons do not match canonical discrimination")
        if raw_non_comparisons != expected_non_comparisons:
            raise ValueError("non_comparison_rows do not match canonical coverage")

    @property
    def schema_version(self) -> str:
        return _SCHEMA_VERSION

    @property
    def maturity_authority(self) -> OptionMaturityAuthority:
        return self.browser.discovery_evidence.discovery_request.maturity_authority

    @property
    def hypothesis_maturity_alignment(self) -> HypothesisMaturityAlignment:
        return (
            self.browser.discovery_evidence.discovery_request
            .hypothesis_maturity_alignment
        )

    @property
    def payoff_geometry_authority(self) -> PayoffGeometryAuthority:
        return PayoffGeometryAuthority.CONDITIONAL_PROVIDER_STANDARD

    @property
    def exact_deliverable_verification(self) -> ExactDeliverableVerification:
        return ExactDeliverableVerification.NOT_ESTABLISHED

    @property
    def reference_price_basis(self) -> ReferencePriceBasis:
        return self.reference_price.basis

    @property
    def quote_reference_temporal_alignment(self) -> TemporalAlignmentState:
        return TemporalAlignmentState.NOT_ESTABLISHED

    @property
    def cross_structure_quote_synchronicity(self) -> TemporalAlignmentState:
        return TemporalAlignmentState.NOT_ESTABLISHED


def _private_grammar(grammar: ComparisonPayoffGrammar) -> _PayoffMathGrammar:
    return {
        ComparisonPayoffGrammar.LONG_CALL: _PayoffMathGrammar.LONG_CALL,
        ComparisonPayoffGrammar.LONG_PUT: _PayoffMathGrammar.LONG_PUT,
        ComparisonPayoffGrammar.LONG_STRADDLE: _PayoffMathGrammar.LONG_STRADDLE,
    }[grammar]


def _payoff_branch(branch: _PayoffMathBranch) -> PayoffBranch:
    return (
        PayoffBranch.DOWNSIDE
        if branch is _PayoffMathBranch.DOWNSIDE
        else PayoffBranch.UPSIDE
    )


def _comparison_coverage(browser: FutuExactContractBrowser) -> tuple:
    rows = browser.rows
    mode = browser.discovery_evidence.discovery_request.distribution_mode
    comparisons = []
    non_comparisons = []
    if mode in (
        DistributionChangeMode.EVENT_DIRECTIONAL_UP,
        DistributionChangeMode.EXTREME_TAIL_UP,
        DistributionChangeMode.EVENT_DIRECTIONAL_DOWN,
        DistributionChangeMode.EXTREME_TAIL_DOWN,
    ):
        wanted = (
            "call"
            if mode in (
                DistributionChangeMode.EVENT_DIRECTIONAL_UP,
                DistributionChangeMode.EXTREME_TAIL_UP,
            )
            else "put"
        )
        grammar = (
            ComparisonPayoffGrammar.LONG_CALL
            if wanted == "call"
            else ComparisonPayoffGrammar.LONG_PUT
        )
        for row in rows:
            if row.option_type == wanted:
                comparisons.append(ComparisonStructure(grammar, (row,)))
            else:
                non_comparisons.append(NonComparisonBrowserRow(
                    row, ComparisonCoverageReasonCode.OPPOSITE_OPTION_TYPE
                ))
        return tuple(comparisons), tuple(non_comparisons)
    if mode is not DistributionChangeMode.BIDIRECTIONAL_EXPANSION:
        raise ValueError("distribution mode is unsupported")
    groups = {}
    for row in rows:
        key = (
            row.provider_underlying,
            row.expiration,
            row.strike,
            row.lot_size,
        )
        groups.setdefault(key, []).append(row)
    consumed = set()
    for row in rows:
        if id(row) in consumed:
            continue
        key = (
            row.provider_underlying,
            row.expiration,
            row.strike,
            row.lot_size,
        )
        group = groups[key]
        calls = [item for item in group if item.option_type == "call"]
        puts = [item for item in group if item.option_type == "put"]
        if len(calls) > 1 or len(puts) > 1:
            raise ValueError("same-strike comparison group is ambiguous")
        if len(calls) == 1 and len(puts) == 1:
            pair = (calls[0], puts[0])
            comparisons.append(ComparisonStructure(
                ComparisonPayoffGrammar.LONG_STRADDLE, pair
            ))
            consumed.update(id(item) for item in pair)
        else:
            for item in group:
                non_comparisons.append(NonComparisonBrowserRow(
                    item, ComparisonCoverageReasonCode.UNPAIRED_STRADDLE_LEG
                ))
                consumed.add(id(item))
    positions = {id(row): index for index, row in enumerate(rows)}
    comparisons.sort(key=lambda item: positions[id(item.rows[0])])
    non_comparisons.sort(key=lambda item: positions[id(item.browser_row)])
    return tuple(comparisons), tuple(non_comparisons)


def _comparison_ask_basis(
    structure: ComparisonStructure,
    quotes: tuple,
) -> tuple:
    available = (
        FutuBrowserQuoteAvailability.ASK_SIDE_AVAILABLE,
        FutuBrowserQuoteAvailability.TWO_SIDED_AVAILABLE,
    )
    if any(quote.availability not in available for quote in quotes):
        reason = (
            IndicativeMetricUnavailableReason.STRADDLE_LEG_ASK_UNAVAILABLE
            if structure.grammar is ComparisonPayoffGrammar.LONG_STRADDLE
            else IndicativeMetricUnavailableReason.ASK_SIDE_QUOTE_UNAVAILABLE
        )
        return None, (reason,)
    values = tuple(_exact_rational_from_decimal(quote.ask_price) for quote in quotes)
    aggregate = values[0]
    for value in values[1:]:
        aggregate = _rational_add(aggregate, value)
    return aggregate, ()


def _premium_ratio(ask_basis, reasons, reference):
    if ask_basis is None:
        return IndicativePremiumToReferenceRatio(
            IndicativeMetricStatus.UNAVAILABLE, None, None, reasons
        )
    return IndicativePremiumToReferenceRatio(
        IndicativeMetricStatus.AVAILABLE,
        ask_basis,
        _rational_divide(ask_basis, reference),
        (),
    )


def _hurdles(structure, ask_basis, reasons, reference):
    private_grammar = _private_grammar(structure.grammar)
    branches = (
        (_PayoffMathBranch.UPSIDE,)
        if private_grammar is _PayoffMathGrammar.LONG_CALL
        else (_PayoffMathBranch.DOWNSIDE,)
        if private_grammar is _PayoffMathGrammar.LONG_PUT
        else (_PayoffMathBranch.DOWNSIDE, _PayoffMathBranch.UPSIDE)
    )
    if ask_basis is None:
        return tuple(
            ConditionalPayoffMultipleHurdle(
                multiple,
                _payoff_branch(branch),
                IndicativeMetricStatus.UNAVAILABLE,
                None,
                None,
                None,
                reasons,
            )
            for multiple in _HURDLE_MULTIPLES
            for branch in branches
        )
    strike = _exact_rational_from_decimal(structure.rows[0].strike)
    expected = _conditional_threshold_prices(
        private_grammar, strike, ask_basis, _HURDLE_MULTIPLES
    )
    records = []
    for multiple, branch, terminal in expected:
        if terminal is None:
            records.append(ConditionalPayoffMultipleHurdle(
                multiple,
                _payoff_branch(branch),
                IndicativeMetricStatus.UNAVAILABLE,
                None,
                None,
                None,
                (IndicativeMetricUnavailableReason.NEGATIVE_UNDERLYING_THRESHOLD,),
            ))
            continue
        absolute = _rational_subtract(terminal, reference)
        records.append(ConditionalPayoffMultipleHurdle(
            multiple,
            _payoff_branch(branch),
            IndicativeMetricStatus.AVAILABLE,
            terminal,
            absolute,
            _rational_divide(absolute, reference),
            (),
        ))
    return tuple(records)


def _response_ladder(structure, ask_basis, reasons, reference):
    grammar = _private_grammar(structure.grammar)
    strike = _exact_rational_from_decimal(structure.rows[0].strike)
    one = ExactRational(1, 1)
    records = []
    for shock in _RESPONSE_SHOCKS:
        terminal = _rational_multiply(reference, _rational_add(one, shock))
        if ask_basis is None:
            records.append(ConvexityResponsePoint(
                shock,
                terminal,
                IndicativeMetricStatus.UNAVAILABLE,
                None,
                reasons,
            ))
            continue
        payoff = _gross_expiration_payoff(grammar, strike, terminal)
        records.append(ConvexityResponsePoint(
            shock,
            terminal,
            IndicativeMetricStatus.AVAILABLE,
            _rational_divide(payoff, ask_basis),
            (),
        ))
    return tuple(records)


def _relative_spread(quotes):
    if any(
        quote.availability is not FutuBrowserQuoteAvailability.TWO_SIDED_AVAILABLE
        for quote in quotes
    ):
        return IndicativeRelativeSpread(
            IndicativeMetricStatus.UNAVAILABLE,
            None,
            None,
            None,
            None,
            (IndicativeMetricUnavailableReason.TWO_SIDED_QUOTE_UNAVAILABLE,),
        )
    bids = tuple(_exact_rational_from_decimal(quote.bid_price) for quote in quotes)
    asks = tuple(_exact_rational_from_decimal(quote.ask_price) for quote in quotes)
    aggregate_bid = bids[0]
    aggregate_ask = asks[0]
    for value in bids[1:]:
        aggregate_bid = _rational_add(aggregate_bid, value)
    for value in asks[1:]:
        aggregate_ask = _rational_add(aggregate_ask, value)
    midpoint = _rational_divide_int(
        _rational_add(aggregate_bid, aggregate_ask), 2
    )
    if midpoint.numerator <= 0:
        return IndicativeRelativeSpread(
            IndicativeMetricStatus.UNAVAILABLE,
            None,
            None,
            None,
            None,
            (IndicativeMetricUnavailableReason.NONPOSITIVE_MIDPOINT,),
        )
    return IndicativeRelativeSpread(
        IndicativeMetricStatus.AVAILABLE,
        aggregate_bid,
        aggregate_ask,
        midpoint,
        _rational_divide(
            _rational_subtract(aggregate_ask, aggregate_bid), midpoint
        ),
        (),
    )


def _build_discriminations(browser, quote_batch, reference_price):
    structures, non_comparisons = _comparison_coverage(browser)
    positions = {id(row): index for index, row in enumerate(browser.rows)}
    reference = _exact_rational_from_decimal(reference_price.close_price)
    records = []
    for structure in structures:
        quotes = tuple(
            quote_batch.quotes[positions[id(row)]] for row in structure.rows
        )
        if any(quote.browser_row is not row for quote, row in zip(quotes, structure.rows)):
            raise ValueError("quote batch row identity is invalid")
        ask_basis, reasons = _comparison_ask_basis(structure, quotes)
        records.append(ComparisonStructureDiscrimination(
            structure,
            quotes,
            _premium_ratio(ask_basis, reasons, reference),
            _hurdles(structure, ask_basis, reasons, reference),
            _response_ladder(structure, ask_basis, reasons, reference),
            _relative_spread(quotes),
        ))
    return tuple(records), non_comparisons


def _reference_price(
    browser: FutuExactContractBrowser,
    underlying_daily_bars: object,
    latest_completed_session_date: object,
) -> DiscriminationReferencePrice:
    if type(underlying_daily_bars) is not tuple:
        raise TypeError("underlying_daily_bars must have exact type tuple")
    if type(latest_completed_session_date) is not datetime.date:
        raise TypeError("latest_completed_session_date must have exact type date")
    request = browser.discovery_evidence.discovery_request
    if latest_completed_session_date > request.evaluation_date:
        raise ValueError("latest completed session date exceeds evaluation date")
    bars = tuple(_strict_reference_observation(item) for item in underlying_daily_bars)
    for item in bars:
        sources = item.metadata.source_references
        if (
            item.underlying_key != request.underlying_key
            or item.adjusted_close_price is not None
            or item.adjustment_methodology is not None
            or item.metadata.normalization_version != _FUTU_DAILY_BAR_VERSION
            or item.metadata.record_origin is not DataOrigin.EXCHANGE_OBSERVED
            or item.metadata.quality_flags
            != (NormalizationQualityFlag.SYMBOL_MAPPED,)
            or len(sources) != 1
            or sources[0].provider_name != _FUTU_PROVIDER
            or sources[0].dataset_name != _FUTU_DATASET
            or sources[0].quality_flags
        ):
            raise ValueError("daily-bar identity or provenance mismatch")
    eligible = tuple(
        item
        for item in bars
        if item.is_session_complete and item.session_date <= request.evaluation_date
    )
    if not eligible:
        raise ValueError("latest completed reference observation is missing")
    maximum_date = max(item.session_date for item in eligible)
    if latest_completed_session_date != maximum_date:
        raise ValueError("declared session is not latest eligible observation")
    matching = tuple(
        item for item in eligible if item.session_date == latest_completed_session_date
    )
    if len(matching) != 1:
        raise ValueError("latest completed reference observation must be unique")
    return DiscriminationReferencePrice(matching[0], latest_completed_session_date)


def discriminate_probability_free_convexity(
    browser: FutuExactContractBrowser,
    quote_batch: FutuBrowserQuoteBatchEvidence,
    underlying_daily_bars: Tuple[UnderlyingDailyBarObservation, ...],
    *,
    latest_completed_session_date: datetime.date,
) -> ProbabilityFreeConvexityDiscriminationResult:
    """Build exhaustive conditional geometry without ranking or selection."""

    browser = _validate_exact_contract_browser(browser)
    if type(quote_batch) is not FutuBrowserQuoteBatchEvidence:
        raise TypeError("quote_batch has wrong exact type")
    try:
        FutuBrowserQuoteBatchEvidence(quote_batch.browser, quote_batch.chunks)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("quote_batch is malformed") from error
    if quote_batch.browser is not browser:
        raise ValueError("quote_batch must retain the exact Browser")
    reference = _reference_price(
        browser, underlying_daily_bars, latest_completed_session_date
    )
    comparisons, non_comparisons = _build_discriminations(
        browser, quote_batch, reference
    )
    return ProbabilityFreeConvexityDiscriminationResult(
        browser,
        quote_batch,
        reference,
        comparisons,
        non_comparisons,
    )
