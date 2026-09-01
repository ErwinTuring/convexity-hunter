"""Deterministic transformations from reviewed market data to research records."""

import datetime
import dataclasses
import decimal
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .evidence import OptionLeg, OptionStructure, Scenario, StructureCosts
from .market_data import (
    CalculationInputReference,
    CalculationLineage,
    CalculationQualityFlag,
    CorrectionSelection,
    CorrectionSelectionReasonCode,
    CorrectionSelectionStatus,
    DataOrigin,
    FreshnessAssessment,
    FreshnessContext,
    FreshnessReasonCode,
    FreshnessStatus,
    MarketDataBindingReference,
    MarketDataCategory,
    MarketDataFreshnessPolicy,
    MarketDataHistoricalSeriesAssessment,
    MarketDataHistoricalSeriesFrequency,
    MarketDataHistoricalSeriesReasonCode,
    MarketDataHistoricalSeriesRequest,
    MarketPhase,
    MarketDataRelationshipAssessment,
    MarketDataRelationshipGroup,
    MarketDataRelationshipGroupKind,
    MarketDataRelationshipGroupMember,
    MarketDataRelationshipRequest,
    MarketDataRelationshipRole,
    MarketDataRelationshipSelection,
    MarketDataSelectionStatus,
    MarketDataSnapshotTimingAssessment,
    NormalizationMetadata,
    NormalizationQualityFlag,
    OptionContractKey,
    OptionContractReference,
    OptionGreeksObservation,
    OptionImpliedVolatilityObservation,
    OptionOpenInterestObservation,
    OptionQuoteObservation,
    OptionVolumeObservation,
    RateCurvePointObservation,
    SelectedFreshMarketDataBinding,
    SourceReference,
    SourceQualityFlag,
    UnderlyingDailyBarObservation,
    UnderlyingKey,
    UnderlyingSecurityType,
    UnderlyingQuoteObservation,
    canonicalize_lineage_parameters,
    semantic_observation_key,
)
from .evidence import (
    TailPricingSlice,
    TermVolatilityPoint,
    VolatilityEnvironment,
)
from .report import LegVolatilityInput, ScenarioResult, StructureLiquidity


__all__ = (
    "StructureLiquidityTransformationResult",
    "transform_structure_liquidity",
    "StructureCostsTransformationResult",
    "transform_structure_costs",
    "HistoricalReturnPriceBasis",
    "HistoricalRealizedVolatility",
    "HistoricalRealizedVolatilityTransformationResult",
    "transform_historical_realized_volatility",
    "VolatilityEnvironmentTransformationResult",
    "transform_volatility_environment",
    "TailPricingTransformationResult",
    "transform_tail_pricing",
    "ScenarioPricingMethodology",
    "ScenarioPricingLegCalculation",
    "NonExpirationScenarioPricingCalculation",
    "ScenarioPricingCalculationResult",
    "ScenarioValuationTransformationResult",
    "transform_scenario_valuation",
    "ExactRational",
    "ExpirationPayoffThresholdSide",
    "ExpirationPayoffThresholdStatus",
    "ExpirationPayoffThreshold",
    "ExpirationPayoffThresholdEvidence",
    "ExpirationPayoffThresholdTransformationResult",
    "transform_expiration_payoff_thresholds",
    "TreasuryPricingRateInput",
    "TreasuryPricingRateTransformationResult",
    "transform_treasury_pricing_rate",
)


_REQUIRED_ROLES = (
    MarketDataRelationshipRole.OPTION_QUOTE,
    MarketDataRelationshipRole.OPTION_VOLUME,
    MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
)
_RECORD_TYPE_BY_ROLE = {
    MarketDataRelationshipRole.UNDERLYING_QUOTE: UnderlyingQuoteObservation,
    MarketDataRelationshipRole.OPTION_QUOTE: OptionQuoteObservation,
    MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY: (
        OptionImpliedVolatilityObservation
    ),
    MarketDataRelationshipRole.OPTION_GREEKS: OptionGreeksObservation,
    MarketDataRelationshipRole.OPTION_VOLUME: OptionVolumeObservation,
    MarketDataRelationshipRole.OPTION_OPEN_INTEREST: (
        OptionOpenInterestObservation
    ),
    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE: (
        OptionContractReference
    ),
}
_FRESHNESS_CATEGORY_BY_ROLE = {
    MarketDataRelationshipRole.UNDERLYING_QUOTE: MarketDataCategory.QUOTE,
    MarketDataRelationshipRole.OPTION_QUOTE: MarketDataCategory.QUOTE,
    MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY: (
        MarketDataCategory.ANALYTICS
    ),
    MarketDataRelationshipRole.OPTION_GREEKS: MarketDataCategory.ANALYTICS,
    MarketDataRelationshipRole.OPTION_VOLUME: MarketDataCategory.ACTIVITY,
    MarketDataRelationshipRole.OPTION_OPEN_INTEREST: (
        MarketDataCategory.ACTIVITY
    ),
    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE: (
        MarketDataCategory.CONTRACT_REFERENCE
    ),
}
_SELECTED_CORRECTION_REASONS = (
    CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
    CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,
)
_QUOTE_METHODOLOGY = (
    "exact selected option quotes scaled by quantity and contract multiplier"
)
_HISTORICAL_RETURN_FORMULA = "natural_log_price_ratio"
_HISTORICAL_VARIANCE_ESTIMATOR = "sample_variance"
_HISTORICAL_SESSION_INTEGRITY_REASONS = frozenset({
    MarketDataHistoricalSeriesReasonCode.MISSING_EXPECTED_SESSION,
    MarketDataHistoricalSeriesReasonCode.UNEXPECTED_SESSION,
    MarketDataHistoricalSeriesReasonCode.DUPLICATE_SESSION,
    MarketDataHistoricalSeriesReasonCode.INCOMPLETE_SESSION,
})
_HISTORICAL_ADJUSTMENT_ONLY_REASONS = frozenset({
    MarketDataHistoricalSeriesReasonCode.MIXED_ADJUSTED_CLOSE_AVAILABILITY,
    MarketDataHistoricalSeriesReasonCode.ADJUSTMENT_METHODOLOGY_MISMATCH,
})


class HistoricalReturnPriceBasis(str, Enum):
    RAW_CLOSE = "raw_close"
    ADJUSTED_CLOSE = "adjusted_close"


def _canonical_decimal_zero(value: decimal.Decimal) -> decimal.Decimal:
    return decimal.Decimal("0") if value.is_zero() else value


def _calculate_historical_statistics(
    prices: Tuple[decimal.Decimal, ...],
    annualization_sessions_per_year: int,
) -> Tuple[Tuple[decimal.Decimal, ...], float]:
    """Calculate precision-34 log returns and annualized sample volatility."""

    context = decimal.Context(
        prec=34,
        rounding=decimal.ROUND_HALF_EVEN,
        Emin=decimal.MIN_EMIN,
        Emax=decimal.MAX_EMAX,
        capitals=1,
        clamp=0,
    )
    context.traps[decimal.Inexact] = False
    context.traps[decimal.Rounded] = False
    context.clear_flags()
    try:
        returns = []
        for previous_price, current_price in zip(prices, prices[1:]):
            if previous_price == current_price:
                log_return = decimal.Decimal("0")
            else:
                ratio = context.divide(current_price, previous_price)
                if not ratio.is_finite() or ratio <= 0:
                    raise ValueError("price ratio must be finite and positive")
                log_return = context.ln(ratio)
            if not log_return.is_finite():
                raise ValueError("log return must be finite")
            returns.append(_canonical_decimal_zero(log_return))

        log_returns = tuple(returns)
        count = len(log_returns)
        total = decimal.Decimal("0")
        for log_return in log_returns:
            total = context.add(total, log_return)
        mean_return = context.divide(total, decimal.Decimal(count))
        if not mean_return.is_finite():
            raise ValueError("mean return must be finite")

        squared_deviation_sum = decimal.Decimal("0")
        for log_return in log_returns:
            deviation = context.subtract(log_return, mean_return)
            squared = context.multiply(deviation, deviation)
            squared_deviation_sum = context.add(
                squared_deviation_sum, squared
            )
        sample_variance = context.divide(
            squared_deviation_sum, decimal.Decimal(count - 1)
        )
        sample_variance = _canonical_decimal_zero(sample_variance)
        if not sample_variance.is_finite() or sample_variance < 0:
            raise ValueError("sample variance must be finite and nonnegative")
        daily_volatility = context.sqrt(sample_variance)
        annualization_root = context.sqrt(
            decimal.Decimal(annualization_sessions_per_year)
        )
        annualized = context.multiply(
            daily_volatility, annualization_root
        )
        annualized = _canonical_decimal_zero(annualized)
        if not annualized.is_finite() or annualized < 0:
            raise ValueError(
                "annualized realized volatility must be finite and nonnegative"
            )
        annualized_float = float(annualized)
    except (decimal.DecimalException, OverflowError, ValueError) as error:
        if isinstance(error, ValueError) and not isinstance(
            error, decimal.DecimalException
        ):
            raise
        raise ValueError(
            "historical realized-volatility calculation failed"
        ) from error
    if not math.isfinite(annualized_float):
        raise ValueError(
            "annualized realized volatility must convert to a finite float"
        )
    if annualized_float == 0.0:
        annualized_float = 0.0
    return log_returns, annualized_float


@dataclass(frozen=True)
class HistoricalRealizedVolatility:
    underlying_key: UnderlyingKey
    start_session_date: datetime.date
    end_session_date: datetime.date
    price_basis: HistoricalReturnPriceBasis
    adjustment_methodology: Optional[str]
    session_dates: Tuple[datetime.date, ...]
    prices: Tuple[decimal.Decimal, ...]
    log_returns: Tuple[decimal.Decimal, ...]
    annualized_realized_volatility: float
    annualization_sessions_per_year: int
    return_formula: str
    variance_estimator: str

    def __post_init__(self) -> None:
        if type(self.underlying_key) is not UnderlyingKey:
            raise TypeError("underlying_key must have exact type UnderlyingKey")
        for name in ("start_session_date", "end_session_date"):
            if type(getattr(self, name)) is not datetime.date:
                raise TypeError(f"{name} must have exact type date")
        if type(self.price_basis) is not HistoricalReturnPriceBasis:
            raise TypeError(
                "price_basis must have exact type HistoricalReturnPriceBasis"
            )
        for name in ("session_dates", "prices", "log_returns"):
            if type(getattr(self, name)) is not tuple:
                raise TypeError(f"{name} must have exact type tuple")
        if any(type(value) is not datetime.date for value in self.session_dates):
            raise TypeError(
                "every session_dates item must have exact type date"
            )
        if any(type(value) is not decimal.Decimal for value in self.prices):
            raise TypeError("every price must have exact type Decimal")
        if any(
            type(value) is not decimal.Decimal for value in self.log_returns
        ):
            raise TypeError("every log return must have exact type Decimal")
        if type(self.annualized_realized_volatility) is not float:
            raise TypeError(
                "annualized_realized_volatility must have exact type float"
            )
        if (
            not math.isfinite(self.annualized_realized_volatility)
            or self.annualized_realized_volatility < 0
        ):
            raise ValueError(
                "annualized_realized_volatility must be finite and nonnegative"
            )
        if type(self.annualization_sessions_per_year) is not int:
            raise TypeError(
                "annualization_sessions_per_year must have exact type int"
            )
        if self.annualization_sessions_per_year <= 0:
            raise ValueError(
                "annualization_sessions_per_year must be positive"
            )
        if type(self.return_formula) is not str:
            raise TypeError("return_formula must have exact type str")
        if type(self.variance_estimator) is not str:
            raise TypeError("variance_estimator must have exact type str")
        if self.return_formula != _HISTORICAL_RETURN_FORMULA:
            raise ValueError("return_formula is inconsistent")
        if self.variance_estimator != _HISTORICAL_VARIANCE_ESTIMATOR:
            raise ValueError("variance_estimator is inconsistent")
        if len(self.prices) < 3 or len(self.log_returns) < 2:
            raise ValueError("at least three prices and two returns are required")
        if len(self.session_dates) != len(self.prices):
            raise ValueError("session_dates and prices lengths must match")
        if len(self.log_returns) != len(self.prices) - 1:
            raise ValueError("log_returns length must be one less than prices")
        if any(
            current <= previous
            for previous, current in zip(
                self.session_dates, self.session_dates[1:]
            )
        ):
            raise ValueError("session_dates must be strictly ascending")
        if (
            self.start_session_date != self.session_dates[0]
            or self.end_session_date != self.session_dates[-1]
        ):
            raise ValueError("window endpoints must match session_dates")
        if any(not price.is_finite() or price <= 0 for price in self.prices):
            raise ValueError("every price must be finite and positive")
        if self.price_basis is HistoricalReturnPriceBasis.RAW_CLOSE:
            if self.adjustment_methodology is not None:
                if type(self.adjustment_methodology) is not str:
                    raise TypeError(
                        "adjustment_methodology must have exact type str"
                    )
                raise ValueError(
                    "raw close requires no adjustment methodology"
                )
        else:
            if self.adjustment_methodology is None:
                raise ValueError(
                    "adjusted close requires an adjustment methodology"
                )
            if type(self.adjustment_methodology) is not str:
                raise TypeError(
                    "adjustment_methodology must have exact type str"
                )
            if (
                not self.adjustment_methodology
                or self.adjustment_methodology.strip()
                != self.adjustment_methodology
            ):
                raise ValueError(
                    "adjustment_methodology must be a nonempty canonical string"
                )

        normalized_returns = tuple(
            _canonical_decimal_zero(value) for value in self.log_returns
        )
        expected_returns, expected_volatility = (
            _calculate_historical_statistics(
                self.prices, self.annualization_sessions_per_year
            )
        )
        normalized_volatility = (
            0.0
            if self.annualized_realized_volatility == 0.0
            else self.annualized_realized_volatility
        )
        if normalized_returns != expected_returns:
            raise ValueError("log_returns are inconsistent with prices")
        if normalized_volatility != expected_volatility:
            raise ValueError(
                "annualized_realized_volatility is inconsistent with returns"
            )
        object.__setattr__(self, "log_returns", normalized_returns)
        object.__setattr__(
            self, "annualized_realized_volatility", normalized_volatility
        )

    @property
    def price_observation_count(self) -> int:
        return len(self.prices)

    @property
    def return_observation_count(self) -> int:
        return len(self.log_returns)


@dataclass(frozen=True)
class HistoricalRealizedVolatilityTransformationResult:
    record: HistoricalRealizedVolatility
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.record) is not HistoricalRealizedVolatility:
            raise TypeError(
                "record must have exact type HistoricalRealizedVolatility"
            )
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")
        if len(self.lineage.inputs) != self.record.price_observation_count:
            raise ValueError(
                "realized lineage input count does not match its record"
            )


@dataclass(frozen=True)
class VolatilityEnvironmentTransformationResult:
    record: VolatilityEnvironment
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.record) is not VolatilityEnvironment:
            raise TypeError(
                "record must have exact type VolatilityEnvironment"
            )
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")
        with decimal.localcontext():
            _verify_volatility_environment_result(self.record, self.lineage)


@dataclass(frozen=True)
class TailPricingTransformationResult:
    records: Tuple[TailPricingSlice, ...]
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.records) is not tuple:
            raise TypeError("records must have exact type tuple")
        if len(self.records) < 2:
            raise ValueError("records must contain at least two items")
        if any(type(record) is not TailPricingSlice for record in self.records):
            raise TypeError("every record must have exact type TailPricingSlice")
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")
        if len({record.underlying for record in self.records}) != 1:
            raise ValueError("records must share one underlying")
        if len({record.as_of_date for record in self.records}) != 1:
            raise ValueError("records must share one as_of_date")
        if len({record.delta_methodology for record in self.records}) != 1:
            raise ValueError("records must share one delta_methodology")
        expirations = tuple(record.expiration for record in self.records)
        if len(set(expirations)) != len(expirations):
            raise ValueError("record expirations must be unique")
        if any(
            record.expiration <= record.as_of_date for record in self.records
        ):
            raise ValueError("every expiration must follow as_of_date")
        ordering = tuple(
            (
                (record.expiration - record.as_of_date).days,
                record.expiration,
            )
            for record in self.records
        )
        if any(
            current <= previous
            for previous, current in zip(ordering, ordering[1:])
        ):
            raise ValueError(
                "records must already be in strictly ascending tenor order"
            )
        with decimal.localcontext():
            _verify_tail_pricing_result(self.records, self.lineage)


@dataclass(frozen=True)
class StructureLiquidityTransformationResult:
    record: StructureLiquidity
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.record) is not StructureLiquidity:
            raise TypeError("record must have exact type StructureLiquidity")
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")
        with decimal.localcontext():
            _verify_structure_liquidity_result(self.record, self.lineage)


@dataclass(frozen=True)
class StructureCostsTransformationResult:
    record: StructureCosts
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.record) is not StructureCosts:
            raise TypeError("record must have exact type StructureCosts")
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")
        with decimal.localcontext():
            _validate_structure_costs_result(self.record, self.lineage)


def _validate_calculation_id(value: object) -> str:
    if type(value) is not str:
        raise TypeError("calculation_id must have exact type str")
    normalized = value.strip()
    if not normalized:
        raise ValueError("calculation_id must not be empty")
    return normalized


def _validate_structure(value: object) -> OptionStructure:
    if type(value) is not OptionStructure:
        raise TypeError("structure must have exact type OptionStructure")
    return value


def _validate_relationship_selection(
    value: object,
) -> MarketDataRelationshipSelection:
    if type(value) is not MarketDataRelationshipSelection:
        raise TypeError(
            "relationship_selection must have exact type "
            "MarketDataRelationshipSelection"
        )
    return value


def _normalize_calculated_at(value: object) -> datetime.datetime:
    if type(value) is not datetime.datetime:
        raise TypeError("calculated_at must have exact type datetime")
    try:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("calculated_at must be timezone-aware")
        return value.astimezone(datetime.timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError("calculated_at must be representable in UTC") from error


def _validate_selection_status(
    selection: MarketDataRelationshipSelection,
) -> None:
    if selection.status is not MarketDataSelectionStatus.SELECTED:
        raise ValueError("relationship selection must have selected status")


def _resolve_selected_candidate(
    selection: MarketDataRelationshipSelection,
) -> MarketDataRelationshipAssessment:
    selected = selection.selected_candidate
    if selected is None:
        raise ValueError("relationship selection must have one selected candidate")
    if type(selected) is not MarketDataRelationshipAssessment:
        raise TypeError(
            "selected candidate must have exact type "
            "MarketDataRelationshipAssessment"
        )
    return selected


def _validate_selected_shape(
    selected: MarketDataRelationshipAssessment,
    structure: OptionStructure,
) -> Tuple[
    Tuple[MarketDataRelationshipGroup, ...],
    Tuple[SelectedFreshMarketDataBinding, ...],
]:
    if type(selected.request) is not MarketDataRelationshipRequest:
        raise TypeError(
            "selected request must have exact type MarketDataRelationshipRequest"
        )
    if type(selected.timing_assessment) is not MarketDataSnapshotTimingAssessment:
        raise TypeError(
            "selected timing assessment must have exact type "
            "MarketDataSnapshotTimingAssessment"
        )
    groups = selected.request.groups
    if type(groups) is not tuple:
        raise TypeError("selected request groups must have exact type tuple")
    if len(groups) != len(structure.legs):
        raise ValueError("selected assessment must have one group per structure leg")

    for group in groups:
        if type(group) is not MarketDataRelationshipGroup:
            raise TypeError(
                "every selected group must have exact type "
                "MarketDataRelationshipGroup"
            )
    for group in groups:
        if type(group.group_kind) is not MarketDataRelationshipGroupKind:
            raise TypeError(
                "group_kind must have exact type MarketDataRelationshipGroupKind"
            )
        if (
            group.group_kind
            is not MarketDataRelationshipGroupKind.OPTION_ACTIVITY_V0_1
        ):
            raise ValueError("every selected group must be an option activity group")
    for group in groups:
        if type(group.members) is not tuple:
            raise TypeError("selected group members must have exact type tuple")
        for member in group.members:
            if type(member) is not MarketDataRelationshipGroupMember:
                raise TypeError(
                    "every selected member must have exact type "
                    "MarketDataRelationshipGroupMember"
                )
    for group in groups:
        for member in group.members:
            if type(member.role) is not MarketDataRelationshipRole:
                raise TypeError(
                    "member role must have exact type MarketDataRelationshipRole"
                )
            if type(member.reference) is not MarketDataBindingReference:
                raise TypeError(
                    "member reference must have exact type "
                    "MarketDataBindingReference"
                )
    for group in groups:
        roles = tuple(member.role for member in group.members)
        if (
            len(roles) != len(_REQUIRED_ROLES)
            or set(roles) != set(_REQUIRED_ROLES)
        ):
            raise ValueError(
                "option activity group must contain exactly quote, volume, "
                "and open-interest roles"
            )

    bindings = selected.timing_assessment.bindings
    if type(bindings) is not tuple:
        raise TypeError("selected timing bindings must have exact type tuple")
    for binding in bindings:
        if type(binding) is not SelectedFreshMarketDataBinding:
            raise TypeError(
                "every selected binding must have exact type "
                "SelectedFreshMarketDataBinding"
            )
    for binding in bindings:
        if type(binding.correction_selection) is not CorrectionSelection:
            raise TypeError(
                "correction_selection must have exact type CorrectionSelection"
            )
        if type(binding.freshness_assessment) is not FreshnessAssessment:
            raise TypeError(
                "freshness_assessment must have exact type FreshnessAssessment"
            )
        if type(binding.freshness_policy) is not MarketDataFreshnessPolicy:
            raise TypeError(
                "freshness_policy must have exact type MarketDataFreshnessPolicy"
            )
        if type(binding.freshness_context) is not FreshnessContext:
            raise TypeError(
                "freshness_context must have exact type FreshnessContext"
            )
    if len(bindings) != len(groups) * len(_REQUIRED_ROLES):
        raise ValueError(
            "selected assessment must have exactly one binding per required role"
        )
    return groups, bindings


def _resolve_selected_objects(
    groups: Tuple[MarketDataRelationshipGroup, ...],
    bindings: Tuple[SelectedFreshMarketDataBinding, ...],
) -> tuple:
    """Resolve all selected objects using record IDs and no proof semantics."""

    entries = []
    for group in groups:
        for member in group.members:
            selected_id = member.reference.selected_record_id
            matches = tuple(
                binding
                for binding in bindings
                if getattr(
                    getattr(binding, "correction_selection", None),
                    "selected_record_id",
                    None,
                )
                == selected_id
            )
            if len(matches) != 1:
                raise ValueError(
                    "member selected record ID must identify exactly one binding"
                )
            binding = matches[0]
            candidates = binding.candidate_records
            if type(candidates) is not tuple or not candidates:
                raise ValueError("binding has malformed candidate_records")
            selected_matches = tuple(
                candidate
                for candidate in candidates
                if getattr(
                    getattr(candidate, "metadata", None),
                    "record_id",
                    None,
                )
                == getattr(
                    binding.correction_selection,
                    "selected_record_id",
                    None,
                )
            )
            if len(selected_matches) != 1:
                raise ValueError(
                    "binding correction selected ID must resolve exactly one "
                    "candidate object"
                )
            entries.append((group, member, binding, selected_matches[0]))
    return tuple(entries)


def _validate_selected_record_types(entries: tuple) -> None:
    """Complete exact selected-record typing before any proof integrity."""

    for _group, member, _binding, record in entries:
        expected_type = _RECORD_TYPE_BY_ROLE[member.role]
        if type(record) is not expected_type:
            raise TypeError(
                f"{member.role.value} selected record must have exact type "
                f"{expected_type.__name__}"
            )


def _validate_candidate_universe(
    binding: SelectedFreshMarketDataBinding,
    selection: CorrectionSelection,
    selected_record: object,
) -> None:
    candidates = binding.candidate_records
    if type(candidates) is not tuple or not candidates:
        raise ValueError("binding candidate_records must be a nonempty exact tuple")
    candidate_ids = tuple(
        _validate_retained_id(
            "candidate metadata record_id",
            getattr(getattr(candidate, "metadata", None), "record_id", None),
        )
        for candidate in candidates
    )
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("binding candidate record IDs must be unique")
    if type(selection.candidate_record_ids) is not tuple:
        raise TypeError("candidate_record_ids must have exact type tuple")
    selection_candidate_ids = tuple(
        _validate_retained_id("candidate_record_id", record_id)
        for record_id in selection.candidate_record_ids
    )
    if (
        tuple(sorted(candidate_ids)) != selection_candidate_ids
    ):
        raise ValueError(
            "binding candidate record IDs do not match correction selection"
        )
    selected_id = _validate_retained_id(
        "correction selected_record_id", selection.selected_record_id
    )
    matches = tuple(
        candidate
        for candidate in candidates
        if candidate.metadata.record_id == selected_id
    )
    if len(matches) != 1 or matches[0] is not selected_record:
        raise ValueError(
            "correction selected ID must identify the exact selected object"
        )
    selected_object_id = _validate_retained_id(
        "selected record metadata record_id",
        selected_record.metadata.record_id,
    )
    if selected_object_id != selected_id:
        raise ValueError("selected object record ID does not match correction")


def _validate_retained_id(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must have exact type str")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be canonical and nonempty")
    return value


def _validate_correction_proof(
    binding: SelectedFreshMarketDataBinding,
    selection: CorrectionSelection,
) -> None:
    if type(selection.status) is not CorrectionSelectionStatus:
        raise ValueError(
            "correction status must have exact type CorrectionSelectionStatus"
        )
    if selection.status is not CorrectionSelectionStatus.SELECTED:
        raise ValueError("binding correction selection must be selected")
    reasons = selection.reason_codes
    if (
        type(reasons) is not tuple
        or len(reasons) != 1
        or type(reasons[0]) is not CorrectionSelectionReasonCode
        or reasons[0] not in _SELECTED_CORRECTION_REASONS
    ):
        raise ValueError(
            "binding correction selection must have one selected reason"
        )
    candidate_count = len(binding.candidate_records)
    if (
        reasons[0] is CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED
        and candidate_count != 1
    ):
        raise ValueError("only-candidate correction reason requires one candidate")
    if (
        reasons[0]
        is CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED
        and candidate_count < 2
    ):
        raise ValueError(
            "dominating-revision correction reason requires multiple candidates"
        )


def _validate_freshness_proof(
    role: MarketDataRelationshipRole,
    binding: SelectedFreshMarketDataBinding,
    selected_record: object,
) -> None:
    freshness = binding.freshness_assessment
    policy = binding.freshness_policy
    context = binding.freshness_context
    selection = binding.correction_selection
    if type(freshness.status) is not FreshnessStatus:
        raise ValueError("freshness status must have exact type FreshnessStatus")
    if type(freshness.category) is not MarketDataCategory:
        raise ValueError(
            "freshness category must have exact type MarketDataCategory"
        )
    reasons = freshness.reason_codes
    if (
        type(reasons) is not tuple
        or any(type(reason) is not FreshnessReasonCode for reason in reasons)
    ):
        raise ValueError(
            "freshness reasons must be exact FreshnessReasonCode values"
        )
    if not (
        freshness.status is FreshnessStatus.FRESH
        and reasons == (FreshnessReasonCode.FRESH_WITHIN_POLICY,)
    ):
        raise ValueError("binding freshness assessment must be exactly fresh")
    if freshness.category is not _FRESHNESS_CATEGORY_BY_ROLE[role]:
        raise ValueError("freshness assessment has the wrong market-data category")
    record_id = _validate_retained_id(
        "selected record metadata record_id",
        selected_record.metadata.record_id,
    )
    freshness_record_id = _validate_retained_id(
        "freshness record_id", freshness.record_id
    )
    correction_record_id = _validate_retained_id(
        "correction selected_record_id", selection.selected_record_id
    )
    if not (
        freshness_record_id == correction_record_id == record_id
    ):
        raise ValueError(
            "selected record IDs do not agree across retained proof sidecars"
        )
    freshness_policy_id = _validate_retained_id(
        "freshness policy_id", freshness.policy_id
    )
    retained_policy_id = _validate_retained_id(
        "retained policy_id", policy.policy_id
    )
    freshness_policy_version = _validate_retained_id(
        "freshness policy_version", freshness.policy_version
    )
    retained_policy_version = _validate_retained_id(
        "retained policy_version", policy.policy_version
    )
    if (
        freshness_policy_id != retained_policy_id
        or freshness_policy_version != retained_policy_version
        or freshness.evaluated_at != context.evaluation_at
    ):
        raise ValueError(
            "freshness assessment does not match retained policy and context"
        )
    if selection.evaluated_at > context.evaluation_at:
        raise ValueError(
            "correction selection must not follow freshness evaluation"
        )


def _validate_semantic_proof(
    member: MarketDataRelationshipGroupMember,
    binding: SelectedFreshMarketDataBinding,
    selected_record: object,
) -> None:
    selection = binding.correction_selection
    expected = semantic_observation_key(selected_record)
    if not (
        binding.semantic_observation_key
        == selection.semantic_observation_key
        == member.reference.semantic_observation_key
        == expected
    ):
        raise ValueError("retained semantic observation keys do not agree")
    if any(
        semantic_observation_key(candidate) != expected
        for candidate in binding.candidate_records
    ):
        raise ValueError(
            "every retained correction candidate must share one semantic key"
        )


def _validate_proof_integrity(
    entries: tuple,
    bindings: Tuple[SelectedFreshMarketDataBinding, ...],
) -> None:
    """Validate complete retained proof state without replaying proof layers."""

    for _group, member, binding, record in entries:
        reference_record_id = _validate_retained_id(
            "binding reference selected_record_id",
            member.reference.selected_record_id,
        )
        selection = binding.correction_selection
        _validate_candidate_universe(binding, selection, record)
        _validate_correction_proof(binding, selection)
        _validate_freshness_proof(member.role, binding, record)
        _validate_semantic_proof(member, binding, record)
        if reference_record_id != record.metadata.record_id:
            raise ValueError("binding reference selected ID does not match record")

    referenced_ids = tuple(id(entry[2]) for entry in entries)
    if len(set(referenced_ids)) != len(referenced_ids):
        raise ValueError("a selected binding must not be consumed more than once")
    if set(referenced_ids) != {id(binding) for binding in bindings}:
        raise ValueError("every selected binding must be referenced exactly once")
    selected_record_ids = tuple(
        _validate_retained_id(
            "consumed selected record_id", entry[3].metadata.record_id
        )
        for entry in entries
    )
    if len(set(selected_record_ids)) != len(selected_record_ids):
        raise ValueError("consumed selected record IDs must be unique")


def _contract_order_key(contract_key: OptionContractKey) -> tuple:
    underlying = contract_key.underlying_key
    return (
        underlying.symbol,
        underlying.listing_mic or "",
        underlying.security_type.value,
        underlying.currency,
        contract_key.expiration,
        contract_key.option_type,
        contract_key.strike,
        contract_key.contract_multiplier,
        contract_key.currency,
        contract_key.deliverable_id or "",
    )


def _matching_leg(
    contract_key: OptionContractKey,
    legs: Tuple[OptionLeg, ...],
) -> OptionLeg:
    matches = tuple(
        leg
        for leg in legs
        if (
            contract_key.underlying_key.symbol == leg.underlying
            and contract_key.option_type == leg.option_type
            and contract_key.expiration == leg.expiration
            and contract_key.strike == decimal.Decimal(str(leg.strike))
            and contract_key.contract_multiplier == leg.contract_multiplier
        )
    )
    if len(matches) != 1:
        raise ValueError("selected contract must match exactly one structure leg")
    return matches[0]


def _match_structure_legs(
    entries: tuple,
    structure: OptionStructure,
) -> tuple:
    grouped = []
    for group in tuple(dict.fromkeys(entry[0].group_id for entry in entries)):
        group_entries = tuple(
            entry for entry in entries if entry[0].group_id == group
        )
        records = {entry[1].role: entry[3] for entry in group_entries}
        bindings = {entry[1].role: entry[2] for entry in group_entries}
        quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        if type(quote.contract_key) is not OptionContractKey:
            raise TypeError("quote must retain an exact OptionContractKey")
        leg = _matching_leg(quote.contract_key, structure.legs)
        grouped.append((quote.contract_key, leg, bindings, records))
    leg_ids = tuple(id(item[1]) for item in grouped)
    if (
        len(set(leg_ids)) != len(leg_ids)
        or set(leg_ids) != {id(leg) for leg in structure.legs}
    ):
        raise ValueError("activity groups must cover structure legs one-to-one")
    return tuple(grouped)


def _validate_contract_sessions(matched: tuple) -> datetime.date:
    session_dates = set()
    for contract_key, _leg, _bindings, records in matched:
        quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        volume = records[MarketDataRelationshipRole.OPTION_VOLUME]
        open_interest = records[MarketDataRelationshipRole.OPTION_OPEN_INTEREST]
        if (
            type(volume.contract_key) is not OptionContractKey
            or type(open_interest.contract_key) is not OptionContractKey
        ):
            raise TypeError("activity records must retain exact OptionContractKey")
        if (
            volume.contract_key != contract_key
            or open_interest.contract_key != contract_key
        ):
            raise ValueError("activity group records must share one contract key")
        if quote.session_date != volume.session_date:
            raise ValueError("quote and volume must share one session date")
        session_dates.add(quote.session_date)
        if quote.session_date > contract_key.expiration:
            raise ValueError("activity session must not follow contract expiration")
    if len(session_dates) != 1:
        raise ValueError("all quote and volume records must share one session date")
    return next(iter(session_dates))


def _validate_required_values(matched: tuple) -> Tuple[int, int]:
    for _contract_key, _leg, _bindings, records in matched:
        quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        volume = records[MarketDataRelationshipRole.OPTION_VOLUME]
        open_interest = records[MarketDataRelationshipRole.OPTION_OPEN_INTEREST]
        if volume.is_session_complete is not True:
            raise ValueError("every consumed volume session must be complete")
        if (
            type(quote.bid_premium) is not decimal.Decimal
            or not quote.bid_premium.is_finite()
            or quote.bid_premium < 0
            or type(quote.ask_premium) is not decimal.Decimal
            or not quote.ask_premium.is_finite()
            or quote.ask_premium <= 0
            or type(volume.cumulative_volume) is not int
            or type(volume.cumulative_volume) is bool
            or volume.cumulative_volume < 0
            or type(open_interest.open_interest) is not int
            or type(open_interest.open_interest) is bool
            or open_interest.open_interest < 0
        ):
            raise ValueError("every consumed numerical value must be valid")
    minimum_volume = min(
        item[3][MarketDataRelationshipRole.OPTION_VOLUME].cumulative_volume
        for item in matched
    )
    minimum_open_interest = min(
        item[3][MarketDataRelationshipRole.OPTION_OPEN_INTEREST].open_interest
        for item in matched
    )
    return minimum_volume, minimum_open_interest


def _exact_decimal_precision(terms: tuple) -> int:
    """Return a dynamic bound for exact scaled products and their sum."""

    nonzero_terms = tuple(
        term for term in terms if not term[0].is_zero()
    )
    if not nonzero_terms:
        return 4
    minimum_exponent = min(
        value.as_tuple().exponent for value, _scale in nonzero_terms
    )
    aligned_product_bounds = []
    for value, scale in nonzero_terms:
        coefficient_digits = len(value.as_tuple().digits)
        # One binary bit per decimal digit is a conservative bound and avoids
        # any string conversion (including Python's large-int string limit).
        scale_digits = max(1, scale.bit_length())
        exponent_shift = value.as_tuple().exponent - minimum_exponent
        aligned_product_bounds.append(
            coefficient_digits + scale_digits + exponent_shift
        )
    carry_digits = max(1, len(nonzero_terms).bit_length())
    return max(aligned_product_bounds) + carry_digits + 2


def _integer_decimal_digits(value: int) -> int:
    """Return exact base-10 digit count without converting the integer to text."""

    if value == 0:
        return 1
    estimate = (
        ((value.bit_length() - 1) * 30103) // 100000
    ) + 1
    power = 10 ** (estimate - 1)
    while value < power:
        estimate -= 1
        power //= 10
    while value >= power * 10:
        estimate += 1
        power *= 10
    return estimate


def _exact_product_bounds(
    value: decimal.Decimal,
    scale: int,
) -> Tuple[int, int]:
    decimal_tuple = value.as_tuple()
    coefficient = 0
    for digit in decimal_tuple.digits:
        coefficient = coefficient * 10 + digit
    product_coefficient = coefficient * scale
    exponent = decimal_tuple.exponent
    if product_coefficient == 0:
        return 0, 0
    while product_coefficient % 10 == 0:
        product_coefficient //= 10
        exponent += 1
    adjusted = exponent + _integer_decimal_digits(product_coefficient) - 1
    return exponent, adjusted


def _validate_exact_decimal_range(terms: tuple, precision: int) -> None:
    if precision > decimal.MAX_PREC:
        raise ValueError(
            "exact Decimal aggregation exceeds supported Decimal precision"
        )
    minimum_representable_exponent = decimal.MIN_EMIN - precision + 1
    for value, scale in terms:
        exponent, adjusted = _exact_product_bounds(value, scale)
        if adjusted > decimal.MAX_EMAX:
            raise ValueError(
                "exact Decimal aggregation exceeds supported Decimal exponent "
                "range"
            )
        if exponent < minimum_representable_exponent:
            raise ValueError(
                "exact Decimal aggregation exceeds supported Decimal exponent "
                "range"
            )


def _exact_scaled_sum(terms: tuple) -> decimal.Decimal:
    precision = _exact_decimal_precision(terms)
    _validate_exact_decimal_range(terms, precision)
    try:
        with decimal.localcontext() as context:
            context.prec = precision
            context.rounding = decimal.ROUND_HALF_EVEN
            context.Emax = decimal.MAX_EMAX
            context.Emin = decimal.MIN_EMIN
            context.clamp = 0
            for signal in context.traps:
                context.traps[signal] = False
            context.traps[decimal.InvalidOperation] = True
            context.traps[decimal.Overflow] = True
            context.traps[decimal.Underflow] = True
            context.traps[decimal.Inexact] = True
            context.traps[decimal.Rounded] = True
            context.traps[decimal.Clamped] = True
            products = tuple(
                (
                    decimal.Decimal(0)
                    if value.is_zero()
                    else value * decimal.Decimal(scale)
                )
                for value, scale in terms
            )
            total = products[0]
            for product in products[1:]:
                total += product
            return total
    except decimal.DecimalException as error:
        raise ValueError(
            "exact Decimal aggregation could not be represented"
        ) from error


def _aggregate_decimal_values(matched: tuple) -> Tuple[decimal.Decimal, decimal.Decimal]:
    bid_terms = tuple(
        (
            item[3][MarketDataRelationshipRole.OPTION_QUOTE].bid_premium,
            item[1].quantity * item[1].contract_multiplier,
        )
        for item in matched
    )
    ask_terms = tuple(
        (
            item[3][MarketDataRelationshipRole.OPTION_QUOTE].ask_premium,
            item[1].quantity * item[1].contract_multiplier,
        )
        for item in matched
    )
    return _exact_scaled_sum(bid_terms), _exact_scaled_sum(ask_terms)


def _convert_position_values(
    bid_value: decimal.Decimal,
    ask_value: decimal.Decimal,
) -> Tuple[float, float]:
    try:
        quoted_bid_value = float(bid_value)
        quoted_ask_value = float(ask_value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError("position values must be finite floats") from error
    if not math.isfinite(quoted_bid_value) or not math.isfinite(quoted_ask_value):
        raise ValueError("position values must be finite floats")
    return quoted_bid_value, quoted_ask_value


def _construct_research_record(
    structure: OptionStructure,
    as_of_date: datetime.date,
    quoted_bid_value: float,
    quoted_ask_value: float,
    minimum_volume: int,
    minimum_open_interest: int,
) -> StructureLiquidity:
    return StructureLiquidity(
        structure=structure,
        as_of_date=as_of_date,
        quoted_bid_value=quoted_bid_value,
        quoted_ask_value=quoted_ask_value,
        minimum_leg_open_interest=minimum_open_interest,
        minimum_leg_daily_volume=minimum_volume,
        quote_methodology=_QUOTE_METHODOLOGY,
    )


def _canonical_consumed(matched: tuple) -> Tuple[tuple, tuple, tuple]:
    canonical = tuple(
        sorted(matched, key=lambda item: _contract_order_key(item[0]))
    )
    records = tuple(
        item[3][role] for item in canonical for role in _REQUIRED_ROLES
    )
    bindings = tuple(
        item[2][role] for item in canonical for role in _REQUIRED_ROLES
    )
    return canonical, records, bindings


def _input_reference(record: object) -> CalculationInputReference:
    metadata = record.metadata
    return CalculationInputReference(
        record_id=metadata.record_id,
        normalized_at=metadata.normalized_at,
        source_ids=tuple(
            source.source_id for source in metadata.source_references
        ),
    )


def _construct_input_references(records: tuple) -> tuple:
    return tuple(_input_reference(record) for record in records)


def _complete_input_reference(reference: CalculationInputReference) -> dict:
    return {
        "record_id": reference.record_id,
        "normalized_at": reference.normalized_at,
        "source_ids": reference.source_ids,
    }


def _direct_record_role(record: object) -> str:
    roles = {
        UnderlyingQuoteObservation: "underlying_quote",
        OptionQuoteObservation: "option_quote",
        OptionImpliedVolatilityObservation: "option_implied_volatility",
        OptionGreeksObservation: "option_greeks",
        OptionContractReference: "option_contract_reference",
    }
    try:
        return roles[type(record)]
    except KeyError as error:
        raise TypeError("direct normalized evidence has an unsupported type") from error


def _direct_propagated_flag_values(record: object, binding: object) -> tuple:
    selected = set()
    if binding is not None and binding.correction_selection.reason_codes == (
        CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,
    ):
        selected.add(CalculationQualityFlag.CORRECTION_SELECTED)
    if record.metadata.record_origin is DataOrigin.SYSTEM_COMPOSITE:
        selected.add(CalculationQualityFlag.COMPOSITE_INPUT_USED)
    if NormalizationQualityFlag.INTERPOLATED in record.metadata.quality_flags:
        selected.add(CalculationQualityFlag.INTERPOLATED)
    return tuple(
        flag.value for flag in CalculationQualityFlag if flag in selected
    )


def _direct_normalized_evidence(records: tuple, bindings: tuple) -> tuple:
    binding_by_id = {
        binding.selected_record.metadata.record_id: binding
        for binding in bindings
    }
    by_id = {}
    for record in records:
        reference = _input_reference(record)
        item = {
            **_complete_input_reference(reference),
            "role": _direct_record_role(record),
            "propagated_quality_flags": _direct_propagated_flag_values(
                record, binding_by_id.get(reference.record_id)
            ),
        }
        existing = by_id.get(reference.record_id)
        if existing is not None and existing != item:
            raise ValueError("duplicate direct evidence is contradictory")
        by_id[reference.record_id] = item
    return tuple(by_id[record_id] for record_id in sorted(by_id))


def _underlying_identity(underlying: UnderlyingKey) -> dict:
    return {
        "symbol": underlying.symbol,
        "listing_mic": underlying.listing_mic,
        "security_type": underlying.security_type.value,
        "currency": underlying.currency,
    }


def _contract_identity(contract: OptionContractKey) -> dict:
    return {
        "underlying": _underlying_identity(contract.underlying_key),
        "expiration": contract.expiration,
        "option_type": contract.option_type,
        "strike": contract.strike,
        "contract_multiplier": contract.contract_multiplier,
        "currency": contract.currency,
        "deliverable_id": contract.deliverable_id,
    }


def _reconstruct_lineage(value: object) -> CalculationLineage:
    if type(value) is not CalculationLineage:
        raise TypeError("lineage must have exact type CalculationLineage")
    for name in (
        "calculation_id",
        "calculation_type",
        "methodology_id",
        "methodology_version",
        "parameters_json",
    ):
        if type(getattr(value, name)) is not str:
            raise TypeError(f"lineage {name} must have exact type str")
    if type(value.calculated_at) is not datetime.datetime:
        raise TypeError("lineage calculated_at must have exact type datetime")
    if type(value.inputs) is not tuple:
        raise TypeError("lineage inputs must have exact type tuple")
    inputs = []
    for item in value.inputs:
        if type(item) is not CalculationInputReference:
            raise TypeError(
                "every lineage input must have exact type "
                "CalculationInputReference"
            )
        if type(item.record_id) is not str:
            raise TypeError("input record_id must have exact type str")
        if type(item.normalized_at) is not datetime.datetime:
            raise TypeError("input normalized_at must have exact type datetime")
        if type(item.source_ids) is not tuple:
            raise TypeError("input source_ids must have exact type tuple")
        reconstructed = CalculationInputReference(
            record_id=item.record_id,
            normalized_at=item.normalized_at,
            source_ids=item.source_ids,
        )
        if reconstructed != item:
            raise ValueError("lineage input is noncanonical")
        inputs.append(reconstructed)
    if type(value.quality_flags) is not tuple:
        raise TypeError("lineage quality_flags must have exact type tuple")
    if any(type(flag) is not CalculationQualityFlag for flag in value.quality_flags):
        raise TypeError(
            "every lineage quality flag must have exact type "
            "CalculationQualityFlag"
        )
    reconstructed = CalculationLineage(
        calculation_id=value.calculation_id,
        calculation_type=value.calculation_type,
        methodology_id=value.methodology_id,
        methodology_version=value.methodology_version,
        calculated_at=value.calculated_at,
        inputs=tuple(inputs),
        parameters_json=value.parameters_json,
        quality_flags=value.quality_flags,
    )
    if reconstructed != value:
        raise ValueError("lineage is noncanonical or constructor-bypassed")
    return reconstructed


def _stable_float(value: object, label: str) -> float:
    if type(value) is not float:
        raise TypeError(f"{label} must have exact type float")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _complete_reference_from_mapping(value: object, label: str) -> dict:
    if type(value) is not dict:
        raise TypeError(f"{label} must have exact type dict")
    if set(value) != {"record_id", "normalized_at", "source_ids"}:
        raise ValueError(f"{label} has the wrong exact schema")
    reference = CalculationInputReference(
        record_id=value["record_id"],
        normalized_at=value["normalized_at"],
        source_ids=value["source_ids"],
    )
    if _complete_input_reference(reference) != value:
        raise ValueError(f"{label} is noncanonical")
    return value


def _quality_flag_values(value: object, permitted: set, label: str) -> tuple:
    if type(value) is not tuple:
        raise TypeError(f"{label} must have exact type tuple")
    if any(type(item) is not str for item in value):
        raise TypeError(f"every {label} item must have exact type str")
    known = {flag.value: flag for flag in CalculationQualityFlag}
    if any(item not in known or known[item] not in permitted for item in value):
        raise ValueError(f"{label} contains a prohibited flag")
    expected = tuple(
        flag.value for flag in CalculationQualityFlag if flag.value in value
    )
    if value != expected:
        raise ValueError(f"{label} is duplicated or out of order")
    return value


def _validate_direct_evidence(
    value: object, allowed_roles: set, label: str
) -> tuple:
    if type(value) is not dict or set(value) != {"direct_inputs"}:
        raise ValueError(f"{label} has the wrong exact schema")
    direct = value["direct_inputs"]
    if type(direct) is not tuple:
        raise TypeError(f"{label} direct_inputs must have exact type tuple")
    permitted = {
        CalculationQualityFlag.CORRECTION_SELECTED,
        CalculationQualityFlag.COMPOSITE_INPUT_USED,
        CalculationQualityFlag.INTERPOLATED,
    }
    record_ids = []
    for index, item in enumerate(direct):
        item_label = f"{label} direct_inputs[{index}]"
        if type(item) is not dict:
            raise TypeError(f"{item_label} must have exact type dict")
        if set(item) != {
            "record_id", "role", "normalized_at", "source_ids",
            "propagated_quality_flags",
        }:
            raise ValueError(f"{item_label} has the wrong exact schema")
        _complete_reference_from_mapping(
            {key: item[key] for key in (
                "record_id", "normalized_at", "source_ids"
            )},
            item_label,
        )
        if type(item["role"]) is not str:
            raise TypeError(f"{item_label} role must have exact type str")
        if item["role"] not in allowed_roles:
            raise ValueError(f"{item_label} role is invalid")
        _quality_flag_values(
            item["propagated_quality_flags"], permitted,
            f"{item_label} propagated_quality_flags",
        )
        record_ids.append(item["record_id"])
    if tuple(sorted(record_ids)) != tuple(record_ids) or len(set(record_ids)) != len(record_ids):
        raise ValueError(f"{label} direct inputs must be unique and lexical")
    return direct


def _liquidity_propagated_flags(binding: object, record: object) -> tuple:
    permitted = {
        CalculationQualityFlag.INTERPOLATED,
        CalculationQualityFlag.CORRECTION_SELECTED,
        CalculationQualityFlag.COMPOSITE_INPUT_USED,
        CalculationQualityFlag.INCOMPLETE_INPUT_USED,
    }
    return tuple(
        flag.value
        for flag in _derive_quality_flags((binding,), (record,))
        if flag in permitted
    )


def _liquidity_evidence_item(
    leg_index: int, contract: OptionContractKey, binding: object, record: object
) -> dict:
    return {
        "leg_index": leg_index,
        **_complete_input_reference(_input_reference(record)),
        "propagated_quality_flags": _liquidity_propagated_flags(
            binding, record
        ),
        "contract": _contract_identity(contract),
    }


def _construct_parameters(
    public_matched: tuple,
    structure: OptionStructure,
    as_of_date: datetime.date,
    bid_decimal: decimal.Decimal,
    ask_decimal: decimal.Decimal,
    minimum_volume: int,
    minimum_open_interest: int,
    record: StructureLiquidity,
) -> str:
    leg_correspondence = []
    quote_evidence = []
    volume_evidence = []
    open_interest_evidence = []
    for leg_index, (contract_key, leg, bindings, records) in enumerate(
        public_matched
    ):
        underlying = contract_key.underlying_key
        leg_correspondence.append({
            "underlying": {
                "symbol": underlying.symbol,
                "listing_mic": underlying.listing_mic,
                "security_type": underlying.security_type.value,
                "currency": underlying.currency,
            },
            "option_type": contract_key.option_type,
            "expiration": contract_key.expiration,
            "strike": contract_key.strike,
            "currency": contract_key.currency,
            "deliverable_id": contract_key.deliverable_id,
            "contract_multiplier": contract_key.contract_multiplier,
            "quantity": leg.quantity,
            "quote_record_id": records[
                MarketDataRelationshipRole.OPTION_QUOTE
            ].metadata.record_id,
            "volume_record_id": records[
                MarketDataRelationshipRole.OPTION_VOLUME
            ].metadata.record_id,
            "open_interest_record_id": records[
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST
            ].metadata.record_id,
        })
        quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        volume = records[MarketDataRelationshipRole.OPTION_VOLUME]
        open_interest = records[
            MarketDataRelationshipRole.OPTION_OPEN_INTEREST
        ]
        quote_evidence.append({
            **_liquidity_evidence_item(
                leg_index,
                contract_key,
                bindings[MarketDataRelationshipRole.OPTION_QUOTE],
                quote,
            ),
            "session_date": quote.session_date,
            "bid_premium": quote.bid_premium,
            "ask_premium": quote.ask_premium,
        })
        volume_evidence.append({
            **_liquidity_evidence_item(
                leg_index,
                contract_key,
                bindings[MarketDataRelationshipRole.OPTION_VOLUME],
                volume,
            ),
            "session_date": volume.session_date,
            "cumulative_volume": volume.cumulative_volume,
            "is_session_complete": volume.is_session_complete,
        })
        open_interest_evidence.append({
            **_liquidity_evidence_item(
                leg_index,
                contract_key,
                bindings[MarketDataRelationshipRole.OPTION_OPEN_INTEREST],
                open_interest,
            ),
            "open_interest_session_date": (
                open_interest.open_interest_session_date
            ),
            "open_interest": open_interest.open_interest,
        })
    return canonicalize_lineage_parameters({
        "activity_count_unit": "contracts",
        "calculation_values": {
            "as_of_date": as_of_date,
            "quoted_bid_value_exact": bid_decimal,
            "quoted_ask_value_exact": ask_decimal,
            "minimum_leg_daily_volume": minimum_volume,
            "minimum_leg_open_interest": minimum_open_interest,
            "quote_methodology": _QUOTE_METHODOLOGY,
            "stable_public_values": {
                "quoted_bid_value_repr": repr(record.quoted_bid_value),
                "quoted_ask_value_repr": repr(record.quoted_ask_value),
            },
        },
        "leg_correspondence": leg_correspondence,
        "minimum_leg_rule": "minimum_unscaled_contract_count_across_legs",
        "normalized_evidence": {
            "option_quotes": tuple(quote_evidence),
            "option_volumes": tuple(volume_evidence),
            "option_open_interest": tuple(open_interest_evidence),
        },
        "position_value_rule": (
            "sum(premium_per_underlying_unit*quantity*contract_multiplier)"
        ),
        "position_value_unit": "usd",
        "premium_input_unit": "usd_per_underlying_unit",
        "structure_identity": {
            "structure_type": structure.structure_type,
            "underlying": structure.underlying,
            "assumed_portfolio_value_repr": repr(
                structure.assumed_portfolio_value
            ),
            "expected_holding_days": structure.expected_holding_days,
            "legs": tuple({
                "underlying": leg.underlying,
                "option_type": leg.option_type,
                "strike_float_repr": repr(leg.strike),
                "expiration": leg.expiration,
                "quantity": leg.quantity,
                "contract_multiplier": leg.contract_multiplier,
            } for leg in structure.legs),
        },
    })


def _derive_quality_flags(
    bindings: tuple,
    records: tuple,
) -> Tuple[CalculationQualityFlag, ...]:
    selected = {CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED}
    if any(
        NormalizationQualityFlag.INTERPOLATED in record.metadata.quality_flags
        for record in records
    ):
        selected.add(CalculationQualityFlag.INTERPOLATED)
    if any(
        binding.correction_selection.reason_codes
        == (
            CorrectionSelectionReasonCode
            .DOMINATING_REVISION_VECTOR_SELECTED,
        )
        for binding in bindings
    ):
        selected.add(CalculationQualityFlag.CORRECTION_SELECTED)
    if any(
        record.metadata.record_origin is DataOrigin.SYSTEM_COMPOSITE
        for record in records
    ):
        selected.add(CalculationQualityFlag.COMPOSITE_INPUT_USED)
    if any(
        NormalizationQualityFlag.INCOMPLETE in record.metadata.quality_flags
        or any(
            SourceQualityFlag.PARTIAL in source.quality_flags
            for source in record.metadata.source_references
        )
        for record in records
    ):
        selected.add(CalculationQualityFlag.INCOMPLETE_INPUT_USED)
    return tuple(flag for flag in CalculationQualityFlag if flag in selected)


def _construct_lineage(
    calculation_id: str,
    calculated_at: datetime.datetime,
    inputs: tuple,
    parameters_json: str,
    quality_flags: tuple,
) -> CalculationLineage:
    return CalculationLineage(
        calculation_id=calculation_id,
        calculation_type="structure_liquidity",
        methodology_id="exact-structure-liquidity",
        methodology_version="v0.2",
        calculated_at=calculated_at,
        inputs=inputs,
        parameters_json=parameters_json,
        quality_flags=quality_flags,
    )


def _construct_result(
    record: StructureLiquidity,
    lineage: CalculationLineage,
) -> StructureLiquidityTransformationResult:
    return StructureLiquidityTransformationResult(record=record, lineage=lineage)


def transform_structure_liquidity(
    calculation_id: object,
    structure: object,
    relationship_selection: object,
    calculated_at: object,
) -> StructureLiquidityTransformationResult:
    """Transform one exact selected option-activity proof into liquidity evidence."""

    normalized_id = _validate_calculation_id(calculation_id)
    exact_structure = _validate_structure(structure)
    selection = _validate_relationship_selection(relationship_selection)
    normalized_at = _normalize_calculated_at(calculated_at)
    _validate_selection_status(selection)
    selected = _resolve_selected_candidate(selection)
    groups, bindings = _validate_selected_shape(selected, exact_structure)
    entries = _resolve_selected_objects(groups, bindings)
    _validate_selected_record_types(entries)
    _validate_proof_integrity(entries, bindings)
    matched = _match_structure_legs(entries, exact_structure)
    as_of_date = _validate_contract_sessions(matched)
    minimum_volume, minimum_open_interest = _validate_required_values(matched)
    bid_decimal, ask_decimal = _aggregate_decimal_values(matched)
    quoted_bid, quoted_ask = _convert_position_values(
        bid_decimal, ask_decimal
    )
    record = _construct_research_record(
        exact_structure,
        as_of_date,
        quoted_bid,
        quoted_ask,
        minimum_volume,
        minimum_open_interest,
    )
    public_matched = tuple(
        next(item for item in matched if item[1] is leg)
        for leg in exact_structure.legs
    )
    _canonical_matched, records, consumed_bindings = _canonical_consumed(matched)
    inputs = _construct_input_references(records)
    parameters_json = _construct_parameters(
        public_matched,
        exact_structure,
        as_of_date,
        bid_decimal,
        ask_decimal,
        minimum_volume,
        minimum_open_interest,
        record,
    )
    quality_flags = _derive_quality_flags(consumed_bindings, records)
    lineage = _construct_lineage(
        normalized_id,
        normalized_at,
        inputs,
        parameters_json,
        quality_flags,
    )
    return _construct_result(record, lineage)


_LIQUIDITY_PARAMETER_KEYS = {
    "activity_count_unit", "calculation_values", "leg_correspondence",
    "minimum_leg_rule", "normalized_evidence", "position_value_rule",
    "position_value_unit", "premium_input_unit", "structure_identity",
}
_LIQUIDITY_LEG_KEYS = {
    "underlying", "option_type", "strike_float_repr", "expiration",
    "quantity", "contract_multiplier",
}
_LIQUIDITY_CORRESPONDENCE_KEYS = {
    "underlying", "option_type", "expiration", "strike", "currency",
    "deliverable_id", "contract_multiplier", "quantity",
    "quote_record_id", "volume_record_id", "open_interest_record_id",
}
_LIQUIDITY_EVIDENCE_COMMON_KEYS = {
    "leg_index", "record_id", "normalized_at", "source_ids",
    "propagated_quality_flags", "contract",
}


def _verify_structure_liquidity_result(
    record: object, lineage: object
) -> tuple:
    if type(record) is not StructureLiquidity:
        raise TypeError("liquidity record must have exact type StructureLiquidity")
    if type(record.structure) is not OptionStructure:
        raise TypeError("liquidity structure must have exact type OptionStructure")
    structure = record.structure
    if type(structure.legs) is not tuple:
        raise TypeError("liquidity structure legs must have exact type tuple")
    reconstructed_legs = []
    for leg in structure.legs:
        if type(leg) is not OptionLeg:
            raise TypeError("every liquidity leg must have exact type OptionLeg")
        if type(leg.underlying) is not str or type(leg.option_type) is not str:
            raise TypeError("liquidity leg strings must have exact type str")
        _stable_float(leg.strike, "liquidity leg strike")
        if type(leg.expiration) is not datetime.date:
            raise TypeError("liquidity leg expiration must have exact type date")
        if type(leg.quantity) is not int or type(leg.contract_multiplier) is not int:
            raise TypeError("liquidity leg counts must have exact type int")
        reconstructed_legs.append(OptionLeg(
            underlying=leg.underlying,
            option_type=leg.option_type,
            strike=leg.strike,
            expiration=leg.expiration,
            quantity=leg.quantity,
            contract_multiplier=leg.contract_multiplier,
        ))
    _stable_float(
        structure.assumed_portfolio_value,
        "liquidity assumed_portfolio_value",
    )
    if type(structure.expected_holding_days) is not int:
        raise TypeError("expected_holding_days must have exact type int")
    reconstructed_structure = OptionStructure(
        legs=tuple(reconstructed_legs),
        assumed_portfolio_value=structure.assumed_portfolio_value,
        expected_holding_days=structure.expected_holding_days,
    )
    if reconstructed_structure != structure:
        raise ValueError("liquidity structure is constructor-bypassed")
    if type(record.as_of_date) is not datetime.date:
        raise TypeError("liquidity as_of_date must have exact type date")
    _stable_float(record.quoted_bid_value, "liquidity quoted_bid_value")
    _stable_float(record.quoted_ask_value, "liquidity quoted_ask_value")
    for name in ("minimum_leg_open_interest", "minimum_leg_daily_volume"):
        if type(getattr(record, name)) is not int:
            raise TypeError(f"liquidity {name} must have exact type int")
    if type(record.quote_methodology) is not str:
        raise TypeError("liquidity quote_methodology must have exact type str")
    reconstructed_record = StructureLiquidity(
        structure=reconstructed_structure,
        as_of_date=record.as_of_date,
        quoted_bid_value=record.quoted_bid_value,
        quoted_ask_value=record.quoted_ask_value,
        minimum_leg_open_interest=record.minimum_leg_open_interest,
        minimum_leg_daily_volume=record.minimum_leg_daily_volume,
        quote_methodology=record.quote_methodology,
    )
    if reconstructed_record != record:
        raise ValueError("liquidity record is constructor-bypassed")
    lineage = _reconstruct_lineage(lineage)
    if (
        lineage.calculation_type != "structure_liquidity"
        or lineage.methodology_id != "exact-structure-liquidity"
        or lineage.methodology_version != "v0.2"
    ):
        raise ValueError("liquidity lineage identity is invalid")
    decoded = _decode_strict_tagged_parameters(
        lineage.parameters_json, _LIQUIDITY_PARAMETER_KEYS,
        "StructureLiquidity v0.2",
    )
    fixed = {
        "activity_count_unit": "contracts",
        "minimum_leg_rule": "minimum_unscaled_contract_count_across_legs",
        "position_value_rule": (
            "sum(premium_per_underlying_unit*quantity*contract_multiplier)"
        ),
        "position_value_unit": "usd",
        "premium_input_unit": "usd_per_underlying_unit",
    }
    if any(decoded[key] != value for key, value in fixed.items()):
        raise ValueError("liquidity fixed methodology is invalid")
    identity = decoded["structure_identity"]
    if type(identity) is not dict or set(identity) != {
        "structure_type", "underlying", "assumed_portfolio_value_repr",
        "expected_holding_days", "legs",
    }:
        raise ValueError("liquidity structure identity has the wrong schema")
    expected_identity = {
        "structure_type": structure.structure_type,
        "underlying": structure.underlying,
        "assumed_portfolio_value_repr": repr(structure.assumed_portfolio_value),
        "expected_holding_days": structure.expected_holding_days,
        "legs": tuple({
            "underlying": leg.underlying,
            "option_type": leg.option_type,
            "strike_float_repr": repr(leg.strike),
            "expiration": leg.expiration,
            "quantity": leg.quantity,
            "contract_multiplier": leg.contract_multiplier,
        } for leg in structure.legs),
    }
    if (
        type(identity["structure_type"]) is not str
        or type(identity["underlying"]) is not str
        or type(identity["assumed_portfolio_value_repr"]) is not str
        or type(identity["expected_holding_days"]) is not int
        or type(identity["legs"]) is not tuple
        or any(type(item) is not dict or set(item) != _LIQUIDITY_LEG_KEYS for item in identity["legs"])
    ):
        raise TypeError("liquidity structure identity has wrong exact types")
    for item in identity["legs"]:
        if (
            type(item["underlying"]) is not str
            or type(item["option_type"]) is not str
            or type(item["strike_float_repr"]) is not str
            or type(item["expiration"]) is not datetime.date
            or type(item["quantity"]) is not int
            or type(item["contract_multiplier"]) is not int
        ):
            raise TypeError("liquidity leg identity has wrong exact types")
    if identity != expected_identity:
        raise ValueError("liquidity structure identity differs from public record")
    correspondence = decoded["leg_correspondence"]
    if type(correspondence) is not tuple or len(correspondence) != len(structure.legs):
        raise ValueError("liquidity leg correspondence cardinality is invalid")
    evidence = decoded["normalized_evidence"]
    if type(evidence) is not dict or set(evidence) != {
        "option_quotes", "option_volumes", "option_open_interest",
    }:
        raise ValueError("liquidity normalized evidence has the wrong schema")
    roles = (
        ("option_quotes", {"session_date", "bid_premium", "ask_premium"}),
        ("option_volumes", {"session_date", "cumulative_volume", "is_session_complete"}),
        ("option_open_interest", {"open_interest_session_date", "open_interest"}),
    )
    evidence_by_role = {}
    permitted = {
        CalculationQualityFlag.INTERPOLATED,
        CalculationQualityFlag.CORRECTION_SELECTED,
        CalculationQualityFlag.COMPOSITE_INPUT_USED,
        CalculationQualityFlag.INCOMPLETE_INPUT_USED,
    }
    for role, extra_keys in roles:
        items = evidence[role]
        if type(items) is not tuple or len(items) != len(structure.legs):
            raise ValueError(f"liquidity {role} cardinality is invalid")
        verified_items = []
        for index, item in enumerate(items):
            if type(item) is not dict:
                raise TypeError(f"liquidity {role} item must have exact type dict")
            if set(item) != _LIQUIDITY_EVIDENCE_COMMON_KEYS | extra_keys:
                raise ValueError(f"liquidity {role} item has the wrong schema")
            if type(item["leg_index"]) is not int:
                raise TypeError("liquidity leg_index must have exact type int")
            if item["leg_index"] != index:
                raise ValueError("liquidity evidence leg order is invalid")
            _complete_reference_from_mapping({
                key: item[key] for key in (
                    "record_id", "normalized_at", "source_ids"
                )
            }, f"liquidity {role}[{index}]")
            _quality_flag_values(
                item["propagated_quality_flags"], permitted,
                f"liquidity {role}[{index}] flags",
            )
            if type(item["contract"]) is not dict or set(item["contract"]) != {
                "underlying", "expiration", "option_type", "strike",
                "contract_multiplier", "currency", "deliverable_id",
            }:
                raise ValueError("liquidity evidence contract schema is invalid")
            if type(item["contract"]["underlying"]) is not dict or set(item["contract"]["underlying"]) != {
                "symbol", "listing_mic", "security_type", "currency",
            }:
                raise ValueError("liquidity underlying identity schema is invalid")
            contract = item["contract"]
            underlying = contract["underlying"]
            if (
                type(underlying["symbol"]) is not str
                or underlying["listing_mic"] is not None
                and type(underlying["listing_mic"]) is not str
                or type(underlying["security_type"]) is not str
                or type(underlying["currency"]) is not str
                or type(contract["expiration"]) is not datetime.date
                or type(contract["option_type"]) is not str
                or type(contract["strike"]) is not decimal.Decimal
                or not contract["strike"].is_finite()
                or type(contract["contract_multiplier"]) is not int
                or type(contract["currency"]) is not str
                or contract["deliverable_id"] is not None
                and type(contract["deliverable_id"]) is not str
            ):
                raise TypeError("liquidity evidence contract has wrong exact types")
            verified_items.append(item)
        evidence_by_role[role] = tuple(verified_items)
    bid_terms = []
    ask_terms = []
    volumes = []
    open_interests = []
    disclosed_ids = []
    for index, (leg, item) in enumerate(zip(structure.legs, correspondence)):
        if type(item) is not dict or set(item) != _LIQUIDITY_CORRESPONDENCE_KEYS:
            raise ValueError("liquidity leg correspondence has the wrong schema")
        if (
            type(item["underlying"]) is not dict
            or set(item["underlying"]) != {
                "symbol", "listing_mic", "security_type", "currency"
            }
            or type(item["option_type"]) is not str
            or type(item["expiration"]) is not datetime.date
            or type(item["strike"]) is not decimal.Decimal
            or not item["strike"].is_finite()
            or type(item["currency"]) is not str
            or item["deliverable_id"] is not None
            and type(item["deliverable_id"]) is not str
            or type(item["contract_multiplier"]) is not int
            or type(item["quantity"]) is not int
            or any(type(item[key]) is not str for key in (
                "quote_record_id", "volume_record_id",
                "open_interest_record_id",
            ))
        ):
            raise TypeError("liquidity leg correspondence has wrong exact types")
        quote = evidence_by_role["option_quotes"][index]
        volume = evidence_by_role["option_volumes"][index]
        open_interest = evidence_by_role["option_open_interest"][index]
        if not (quote["contract"] == volume["contract"] == open_interest["contract"]):
            raise ValueError("liquidity evidence contract identities differ")
        contract = quote["contract"]
        if (
            contract["underlying"] != item["underlying"]
            or contract["option_type"] != leg.option_type
            or contract["expiration"] != leg.expiration
            or contract["strike"] != decimal.Decimal(str(leg.strike))
            or contract["contract_multiplier"] != leg.contract_multiplier
            or item["option_type"] != leg.option_type
            or item["expiration"] != leg.expiration
            or item["strike"] != contract["strike"]
            or item["contract_multiplier"] != leg.contract_multiplier
            or item["quantity"] != leg.quantity
            or item["currency"] != contract["currency"]
            or item["deliverable_id"] != contract["deliverable_id"]
            or item["quote_record_id"] != quote["record_id"]
            or item["volume_record_id"] != volume["record_id"]
            or item["open_interest_record_id"] != open_interest["record_id"]
        ):
            raise ValueError("liquidity leg correspondence is inconsistent")
        for name in ("bid_premium", "ask_premium"):
            if type(quote[name]) is not decimal.Decimal:
                raise TypeError(f"liquidity {name} must have exact type Decimal")
            if not quote[name].is_finite():
                raise ValueError(f"liquidity {name} must be finite")
        if quote["bid_premium"] < 0 or quote["ask_premium"] <= 0 or quote["ask_premium"] < quote["bid_premium"]:
            raise ValueError("liquidity quote premiums are economically invalid")
        if quote["session_date"] != record.as_of_date or volume["session_date"] != record.as_of_date:
            raise ValueError("liquidity quote and volume sessions are inconsistent")
        if volume["is_session_complete"] is not True:
            raise ValueError("liquidity volume session must be complete")
        if type(volume["cumulative_volume"]) is not int or volume["cumulative_volume"] < 0:
            raise TypeError("liquidity volume must be an exact nonnegative int")
        if type(open_interest["open_interest"]) is not int or open_interest["open_interest"] < 0:
            raise TypeError("liquidity open interest must be an exact nonnegative int")
        if type(open_interest["open_interest_session_date"]) is not datetime.date:
            raise TypeError("open-interest date must have exact type date")
        if open_interest["open_interest_session_date"] > record.as_of_date:
            raise ValueError("open-interest date follows the activity session")
        if leg.expiration <= record.as_of_date:
            raise ValueError("liquidity expiration must follow as_of_date")
        bid_terms.append((quote["bid_premium"], leg.quantity * leg.contract_multiplier))
        ask_terms.append((quote["ask_premium"], leg.quantity * leg.contract_multiplier))
        volumes.append(volume["cumulative_volume"])
        open_interests.append(open_interest["open_interest"])
        disclosed_ids.extend((quote["record_id"], volume["record_id"], open_interest["record_id"]))
    if len(set(disclosed_ids)) != len(disclosed_ids):
        raise ValueError("liquidity normalized evidence IDs must be unique")
    values = decoded["calculation_values"]
    if type(values) is not dict or set(values) != {
        "as_of_date", "quoted_bid_value_exact", "quoted_ask_value_exact",
        "minimum_leg_daily_volume", "minimum_leg_open_interest",
        "quote_methodology", "stable_public_values",
    }:
        raise ValueError("liquidity calculation values have the wrong schema")
    exact_bid = _exact_scaled_sum(tuple(bid_terms))
    exact_ask = _exact_scaled_sum(tuple(ask_terms))
    expected_volume = min(volumes)
    expected_open_interest = min(open_interests)
    stable = values["stable_public_values"]
    if type(stable) is not dict or set(stable) != {
        "quoted_bid_value_repr", "quoted_ask_value_repr",
    }:
        raise ValueError("liquidity stable values have the wrong schema")
    if (
        values["as_of_date"] != record.as_of_date
        or values["quoted_bid_value_exact"] != exact_bid
        or values["quoted_ask_value_exact"] != exact_ask
        or type(values["minimum_leg_daily_volume"]) is not int
        or values["minimum_leg_daily_volume"] != expected_volume
        or type(values["minimum_leg_open_interest"]) is not int
        or values["minimum_leg_open_interest"] != expected_open_interest
        or values["quote_methodology"] != _QUOTE_METHODOLOGY
        or record.quote_methodology != _QUOTE_METHODOLOGY
        or _finite_float(exact_bid) != record.quoted_bid_value
        or _finite_float(exact_ask) != record.quoted_ask_value
        or stable["quoted_bid_value_repr"] != repr(record.quoted_bid_value)
        or stable["quoted_ask_value_repr"] != repr(record.quoted_ask_value)
        or record.minimum_leg_daily_volume != expected_volume
        or record.minimum_leg_open_interest != expected_open_interest
    ):
        raise ValueError("liquidity calculation values are inconsistent")
    references = {item.record_id: item for item in lineage.inputs}
    if set(references) != set(disclosed_ids):
        raise ValueError("liquidity lineage inputs differ from evidence")
    propagated_values = set()
    for role, _extra in roles:
        for item in evidence_by_role[role]:
            reference = references[item["record_id"]]
            if reference.normalized_at != item["normalized_at"] or reference.source_ids != item["source_ids"]:
                raise ValueError("liquidity evidence differs from lineage input")
            propagated_values.update(item["propagated_quality_flags"])
    selected_flags = {CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED}
    for flag in permitted:
        if flag.value in propagated_values:
            selected_flags.add(flag)
    expected_flags = tuple(
        flag for flag in CalculationQualityFlag if flag in selected_flags
    )
    if lineage.quality_flags != expected_flags:
        raise ValueError("liquidity quality flags are inconsistent")
    return record, lineage, decoded


_COST_ROLES_BY_GROUP_KIND = {
    MarketDataRelationshipGroupKind.UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1: (
        MarketDataRelationshipRole.UNDERLYING_QUOTE,
        MarketDataRelationshipRole.OPTION_QUOTE,
    ),
    MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1: (
        MarketDataRelationshipRole.OPTION_QUOTE,
        MarketDataRelationshipRole.OPTION_GREEKS,
    ),
    MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1: (
        MarketDataRelationshipRole.OPTION_QUOTE,
        MarketDataRelationshipRole.OPTION_GREEKS,
        MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
    ),
}
_COST_RECORD_TYPES = (
    UnderlyingQuoteObservation,
    OptionQuoteObservation,
    OptionGreeksObservation,
    OptionContractReference,
)


def _validate_commissions_and_fees(value: object) -> decimal.Decimal:
    if type(value) is not decimal.Decimal:
        raise TypeError("commissions_and_fees must have exact type Decimal")
    if not value.is_finite() or value < 0:
        raise ValueError("commissions_and_fees must be finite and nonnegative")
    return value


def _validate_repeated_bet_count(value: object) -> int:
    if type(value) is not int:
        raise TypeError("repeated_bet_count must have exact type int")
    if value <= 0:
        raise ValueError("repeated_bet_count must be greater than zero")
    return value


def _validate_cost_selected_shape(
    selected: MarketDataRelationshipAssessment,
    structure: OptionStructure,
) -> Tuple[
    Tuple[MarketDataRelationshipGroup, ...],
    Tuple[SelectedFreshMarketDataBinding, ...],
]:
    if type(selected.request) is not MarketDataRelationshipRequest:
        raise TypeError(
            "selected request must have exact type MarketDataRelationshipRequest"
        )
    if type(selected.timing_assessment) is not MarketDataSnapshotTimingAssessment:
        raise TypeError(
            "selected timing assessment must have exact type "
            "MarketDataSnapshotTimingAssessment"
        )
    groups = selected.request.groups
    if type(groups) is not tuple:
        raise TypeError("selected request groups must have exact type tuple")
    if len(groups) != len(structure.legs) * 3:
        raise ValueError(
            "selected assessment must have exactly three groups per structure leg"
        )
    for group in groups:
        if type(group) is not MarketDataRelationshipGroup:
            raise TypeError(
                "every selected group must have exact type "
                "MarketDataRelationshipGroup"
            )
        if type(group.group_kind) is not MarketDataRelationshipGroupKind:
            raise TypeError(
                "group_kind must have exact type MarketDataRelationshipGroupKind"
            )
        if group.group_kind not in _COST_ROLES_BY_GROUP_KIND:
            raise ValueError("selected assessment contains an unsupported group kind")
        if type(group.members) is not tuple:
            raise TypeError("selected group members must have exact type tuple")
        for member in group.members:
            if type(member) is not MarketDataRelationshipGroupMember:
                raise TypeError(
                    "every selected member must have exact type "
                    "MarketDataRelationshipGroupMember"
                )
            if type(member.role) is not MarketDataRelationshipRole:
                raise TypeError(
                    "member role must have exact type MarketDataRelationshipRole"
                )
            if type(member.reference) is not MarketDataBindingReference:
                raise TypeError(
                    "member reference must have exact type "
                    "MarketDataBindingReference"
                )
        required_roles = _COST_ROLES_BY_GROUP_KIND[group.group_kind]
        roles = tuple(member.role for member in group.members)
        if len(roles) != len(required_roles) or set(roles) != set(required_roles):
            raise ValueError(
                "selected cost group does not have its exact required roles"
            )
    for group_kind in _COST_ROLES_BY_GROUP_KIND:
        if sum(group.group_kind is group_kind for group in groups) != len(
            structure.legs
        ):
            raise ValueError(
                "selected assessment must have one group of every cost kind "
                "per structure leg"
            )

    bindings = selected.timing_assessment.bindings
    if type(bindings) is not tuple:
        raise TypeError("selected timing bindings must have exact type tuple")
    for binding in bindings:
        if type(binding) is not SelectedFreshMarketDataBinding:
            raise TypeError(
                "every selected binding must have exact type "
                "SelectedFreshMarketDataBinding"
            )
        if type(binding.correction_selection) is not CorrectionSelection:
            raise TypeError(
                "correction_selection must have exact type CorrectionSelection"
            )
        if type(binding.freshness_assessment) is not FreshnessAssessment:
            raise TypeError(
                "freshness_assessment must have exact type FreshnessAssessment"
            )
        if type(binding.freshness_policy) is not MarketDataFreshnessPolicy:
            raise TypeError(
                "freshness_policy must have exact type MarketDataFreshnessPolicy"
            )
        if type(binding.freshness_context) is not FreshnessContext:
            raise TypeError(
                "freshness_context must have exact type FreshnessContext"
            )
    if len(bindings) != 1 + len(structure.legs) * 3:
        raise ValueError(
            "selected assessment must have one underlying and three bindings "
            "per structure leg"
        )
    return groups, bindings


def _validate_cost_selected_record_types(entries: tuple) -> None:
    _validate_selected_record_types(entries)
    unique_records = {}
    for _group, _member, binding, record in entries:
        unique_records[id(binding)] = record
    counts = tuple(
        sum(type(record) is record_type for record in unique_records.values())
        for record_type in _COST_RECORD_TYPES
    )
    leg_count = (len(unique_records) - 1) // 3
    if counts != (1, leg_count, leg_count, leg_count):
        raise ValueError(
            "selected binding universe must contain one underlying quote and "
            "one quote, Greeks, and contract reference per leg"
        )


def _validate_cost_proof_integrity(
    entries: tuple,
    bindings: Tuple[SelectedFreshMarketDataBinding, ...],
) -> None:
    """Validate repeated retained proof without replaying proof-layer decisions."""

    representatives = {}
    for _group, member, binding, record in entries:
        reference_record_id = _validate_retained_id(
            "binding reference selected_record_id",
            member.reference.selected_record_id,
        )
        if reference_record_id != record.metadata.record_id:
            raise ValueError("binding reference selected ID does not match record")
        _validate_semantic_proof(member, binding, record)
        representatives.setdefault(id(binding), (member, binding, record))

    if set(representatives) != {id(binding) for binding in bindings}:
        raise ValueError("every selected binding must be referenced")
    selected_record_ids = []
    for member, binding, record in representatives.values():
        selection = binding.correction_selection
        _validate_candidate_universe(binding, selection, record)
        _validate_correction_proof(binding, selection)
        _validate_freshness_proof(member.role, binding, record)
        selected_record_ids.append(_validate_retained_id(
            "consumed selected record_id", record.metadata.record_id
        ))
    if len(set(selected_record_ids)) != len(selected_record_ids):
        raise ValueError("consumed selected record IDs must be unique")


def _entries_for_group(entries: tuple, group: MarketDataRelationshipGroup) -> dict:
    return {
        member.role: (binding, record)
        for entry_group, member, binding, record in entries
        if entry_group is group
    }


def _validate_cost_repeated_references(
    entries: tuple,
    groups: Tuple[MarketDataRelationshipGroup, ...],
    structure: OptionStructure,
) -> tuple:
    uses = {}
    for group, member, binding, record in entries:
        uses.setdefault(id(binding), []).append((group, member.role, record))

    underlying_uses = tuple(
        value
        for value in uses.values()
        if type(value[0][2]) is UnderlyingQuoteObservation
    )
    if (
        len(underlying_uses) != 1
        or len(underlying_uses[0]) != len(structure.legs)
        or any(
            group.group_kind
            is not MarketDataRelationshipGroupKind
            .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
            or role is not MarketDataRelationshipRole.UNDERLYING_QUOTE
            for group, role, _record in underlying_uses[0]
        )
    ):
        raise ValueError(
            "one underlying quote binding must appear in every snapshot group"
        )

    expected_counts = {
        OptionQuoteObservation: 3,
        OptionGreeksObservation: 2,
        OptionContractReference: 1,
    }
    for value in uses.values():
        record_type = type(value[0][2])
        if record_type is UnderlyingQuoteObservation:
            continue
        expected_count = expected_counts.get(record_type)
        if expected_count is None or len(value) != expected_count:
            raise ValueError("selected binding has an invalid repeated-reference count")
        expected_role = {
            OptionQuoteObservation: MarketDataRelationshipRole.OPTION_QUOTE,
            OptionGreeksObservation: MarketDataRelationshipRole.OPTION_GREEKS,
            OptionContractReference: (
                MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
            ),
        }[record_type]
        if any(role is not expected_role for _group, role, _record in value):
            raise ValueError("selected binding is reused under the wrong role")

    snapshots = tuple(
        group for group in groups
        if group.group_kind
        is MarketDataRelationshipGroupKind.UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
    )
    analytics = tuple(
        group for group in groups
        if group.group_kind
        is MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1
    )
    references = tuple(
        group for group in groups
        if group.group_kind
        is MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1
    )
    matched = []
    for snapshot in snapshots:
        snapshot_entries = _entries_for_group(entries, snapshot)
        underlying_binding, underlying = snapshot_entries[
            MarketDataRelationshipRole.UNDERLYING_QUOTE
        ]
        quote_binding, quote = snapshot_entries[
            MarketDataRelationshipRole.OPTION_QUOTE
        ]
        analytics_matches = tuple(
            group for group in analytics
            if _entries_for_group(entries, group)[
                MarketDataRelationshipRole.OPTION_QUOTE
            ][0] is quote_binding
        )
        reference_matches = tuple(
            group for group in references
            if _entries_for_group(entries, group)[
                MarketDataRelationshipRole.OPTION_QUOTE
            ][0] is quote_binding
        )
        if len(analytics_matches) != 1 or len(reference_matches) != 1:
            raise ValueError(
                "each option quote must connect one snapshot, analytics, and "
                "contract-reference group"
            )
        analytics_entries = _entries_for_group(entries, analytics_matches[0])
        reference_entries = _entries_for_group(entries, reference_matches[0])
        greeks_binding, greeks = analytics_entries[
            MarketDataRelationshipRole.OPTION_GREEKS
        ]
        if reference_entries[
            MarketDataRelationshipRole.OPTION_GREEKS
        ][0] is not greeks_binding:
            raise ValueError(
                "analytics and contract-reference groups must reuse one Greeks "
                "binding"
            )
        reference_binding, contract_reference = reference_entries[
            MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
        ]
        matched.append((
            quote.contract_key,
            underlying_binding,
            underlying,
            quote_binding,
            quote,
            greeks_binding,
            greeks,
            reference_binding,
            contract_reference,
        ))
    if len({id(item[3]) for item in matched}) != len(structure.legs):
        raise ValueError("cost groups must cover distinct option quote bindings")
    return tuple(matched)


def _match_cost_structure_legs(
    matched: tuple,
    structure: OptionStructure,
) -> tuple:
    completed = []
    common_underlying_key = matched[0][2].underlying_key
    if common_underlying_key.symbol != structure.underlying:
        raise ValueError("underlying quote must match the supplied structure")
    for item in matched:
        (
            contract_key,
            underlying_binding,
            underlying,
            quote_binding,
            quote,
            greeks_binding,
            greeks,
            reference_binding,
            contract_reference,
        ) = item
        if (
            type(contract_key) is not OptionContractKey
            or type(greeks.contract_key) is not OptionContractKey
            or type(contract_reference.contract_key) is not OptionContractKey
        ):
            raise TypeError("cost inputs must retain exact OptionContractKey objects")
        if not (
            underlying.underlying_key
            == contract_key.underlying_key
            == greeks.contract_key.underlying_key
            == contract_reference.contract_key.underlying_key
            == common_underlying_key
        ):
            raise ValueError("all cost inputs must share one exact UnderlyingKey")
        if not (
            quote.contract_key
            == greeks.contract_key
            == contract_reference.contract_key
        ):
            raise ValueError("each leg's cost records must share one contract key")
        leg = _matching_leg(contract_key, structure.legs)
        completed.append((
            contract_key,
            leg,
            underlying_binding,
            underlying,
            quote_binding,
            quote,
            greeks_binding,
            greeks,
            reference_binding,
            contract_reference,
        ))
    leg_ids = tuple(id(item[1]) for item in completed)
    if (
        len(set(leg_ids)) != len(leg_ids)
        or set(leg_ids) != {id(leg) for leg in structure.legs}
    ):
        raise ValueError("cost groups must cover structure legs one-to-one")
    return tuple(completed)


def _validate_cost_sessions(matched: tuple) -> datetime.date:
    session_dates = {item[3].session_date for item in matched}
    session_dates.update(item[5].session_date for item in matched)
    session_dates.update(item[7].session_date for item in matched)
    if len(session_dates) != 1:
        raise ValueError("all cost observations must share one session date")
    session_date = next(iter(session_dates))
    if any(session_date >= item[0].expiration for item in matched):
        raise ValueError("cost session must precede every leg expiration")
    return session_date


def _validate_cost_values_and_methodology(matched: tuple) -> tuple:
    methodologies = []
    for item in matched:
        underlying = item[3]
        quote = item[5]
        greeks = item[7]
        decimal_values = (
            underlying.bid_price,
            underlying.ask_price,
            quote.bid_premium,
            quote.ask_premium,
        )
        if any(
            type(value) is not decimal.Decimal or not value.is_finite()
            for value in decimal_values
        ):
            raise ValueError("every consumed quote value must be a finite Decimal")
        if (
            underlying.bid_price < 0
            or underlying.ask_price <= 0
            or underlying.ask_price < underlying.bid_price
            or quote.bid_premium < 0
            or quote.ask_premium <= 0
            or quote.ask_premium < quote.bid_premium
        ):
            raise ValueError("every consumed quote must be noncrossed and valid")
        if greeks.gamma is None or greeks.theta is None:
            raise ValueError("every Greeks input must contain Gamma and Theta")
        if (
            type(greeks.gamma) is not decimal.Decimal
            or not greeks.gamma.is_finite()
            or greeks.gamma < 0
            or type(greeks.theta) is not decimal.Decimal
            or not greeks.theta.is_finite()
            or greeks.theta > 0
            or type(greeks.theta_day_basis) is not str
            or not greeks.theta_day_basis
        ):
            raise ValueError("every consumed Gamma and Theta must be usable")
        methodologies.append((
            greeks.model_name,
            greeks.model_version,
            greeks.rate_input_description,
            greeks.dividend_input_description,
            greeks.theta_day_basis,
            greeks.metadata.unit_convention,
        ))
    if any(methodology != methodologies[0] for methodology in methodologies[1:]):
        raise ValueError("all Greeks inputs must share one exact methodology")
    return methodologies[0]


def _exact_half(value: decimal.Decimal) -> decimal.Decimal:
    """Return an exact Decimal half without consulting the ambient context."""

    five_times = _exact_scaled_sum(((value, 5),))
    decimal_tuple = five_times.as_tuple()
    return decimal.Decimal((
        decimal_tuple.sign,
        decimal_tuple.digits,
        decimal_tuple.exponent - 1,
    ))


def _aggregate_cost_decimals(
    matched: tuple,
    commissions_and_fees: decimal.Decimal,
) -> tuple:
    bid = _exact_scaled_sum(tuple(
        (item[5].bid_premium, item[1].quantity * item[1].contract_multiplier)
        for item in matched
    ))
    ask = _exact_scaled_sum(tuple(
        (item[5].ask_premium, item[1].quantity * item[1].contract_multiplier)
        for item in matched
    ))
    quoted_mid = _exact_half(_exact_scaled_sum(((bid, 1), (ask, 1))))
    spread_cost = _exact_half(_exact_scaled_sum((
        (ask, 1),
        (bid.copy_negate(), 1),
    )))
    theta = _exact_scaled_sum(tuple(
        (item[7].theta, item[1].quantity * item[1].contract_multiplier)
        for item in matched
    ))
    gamma = _exact_scaled_sum(tuple(
        (item[7].gamma, item[1].quantity * item[1].contract_multiplier)
        for item in matched
    ))
    underlying = matched[0][3]
    underlying_price = _exact_half(_exact_scaled_sum((
        (underlying.bid_price, 1),
        (underlying.ask_price, 1),
    )))
    return (
        quoted_mid,
        spread_cost,
        commissions_and_fees,
        theta,
        gamma,
        underlying_price,
    )


def _convert_cost_values(values: tuple) -> tuple:
    converted = []
    for value in values:
        try:
            converted_value = float(value)
        except (OverflowError, ValueError) as error:
            raise ValueError("cost values must be finite floats") from error
        if not math.isfinite(converted_value):
            raise ValueError("cost values must be finite floats")
        converted.append(converted_value)
    return tuple(converted)


def _greeks_methodology_disclosure(methodology: tuple) -> str:
    (
        model_name,
        model_version,
        rate_description,
        dividend_description,
        theta_day_basis,
        unit_convention,
    ) = methodology
    version = "none" if model_version is None else model_version
    return (
        f"model={model_name};model_version={version};"
        f"rate_input={rate_description};"
        f"dividend_input={dividend_description};"
        f"theta_day_basis={theta_day_basis};"
        f"unit_convention={unit_convention}"
    )


_COST_PARAMETER_KEYS = {
    "commission_and_fee_scope",
    "commissions_and_fees_usd",
    "gamma_input_unit",
    "gamma_position_rule",
    "greeks_methodology",
    "leg_correspondence",
    "position_value_unit",
    "premium_input_unit",
    "premium_midpoint_rule",
    "repeated_bet_count",
    "spread_cost_rule",
    "spread_cost_scope",
    "theta_day_basis",
    "theta_input_unit",
    "theta_position_rule",
    "underlying_price_rule",
    "underlying_price_unit",
    "calculation_values",
    "normalized_evidence",
    "structure_identity",
}
_COST_METHODOLOGY_KEYS = {
    "model_name",
    "model_version",
    "rate_input_description",
    "dividend_input_description",
    "theta_day_basis",
    "unit_convention",
}
_COST_UNDERLYING_KEYS = {
    "symbol",
    "listing_mic",
    "security_type",
    "currency",
}
_COST_LEG_IDENTITY_KEYS = {
    "underlying",
    "option_type",
    "strike_float_repr",
    "expiration",
    "quantity",
    "contract_multiplier",
}
_COST_CONTRACT_FIELDS = {
    "underlying",
    "option_type",
    "expiration",
    "strike",
    "currency",
    "deliverable_id",
    "contract_multiplier",
}
_COST_COMMON_EVIDENCE_FIELDS = {
    "record_id",
    "normalized_at",
    "source_ids",
    "propagated_quality_flags",
}
_COST_STABLE_VALUE_KEYS = {
    "quoted_mid_premium_repr",
    "estimated_spread_cost_repr",
    "commissions_and_fees_repr",
    "theta_per_day_repr",
    "gamma_repr",
    "underlying_price_repr",
    "total_entry_cost_repr",
    "maximum_loss_repr",
    "cumulative_repeated_bet_cost_repr",
}
_COST_CALCULATION_VALUE_KEYS = {
    "quoted_mid_premium_exact",
    "estimated_spread_cost_exact",
    "commissions_and_fees_exact",
    "theta_per_day_exact",
    "gamma_exact",
    "underlying_price_exact",
    "total_entry_cost_exact",
    "maximum_loss_exact",
    "cumulative_repeated_bet_cost_exact",
    "stable_record_values",
}
_COST_EVIDENCE_KEYS = {
    "underlying_quote",
    "option_quotes",
    "option_greeks",
    "contract_references",
}
_COST_PROPAGATED_FLAG_ORDER = (
    "interpolated",
    "correction_selected",
    "composite_input_used",
)


def _cost_underlying_identity(underlying: UnderlyingKey) -> dict:
    return {
        "symbol": underlying.symbol,
        "listing_mic": underlying.listing_mic,
        "security_type": underlying.security_type.value,
        "currency": underlying.currency,
    }


def _cost_contract_identity(contract: OptionContractKey) -> dict:
    return {
        "underlying": _cost_underlying_identity(contract.underlying_key),
        "option_type": contract.option_type,
        "expiration": contract.expiration,
        "strike": contract.strike,
        "currency": contract.currency,
        "deliverable_id": contract.deliverable_id,
        "contract_multiplier": contract.contract_multiplier,
    }


def _cost_structure_leg_identity(leg: OptionLeg) -> dict:
    return {
        "underlying": leg.underlying,
        "option_type": leg.option_type,
        "strike_float_repr": repr(leg.strike),
        "expiration": leg.expiration,
        "quantity": leg.quantity,
        "contract_multiplier": leg.contract_multiplier,
    }


def _cost_propagated_flags(
    binding: SelectedFreshMarketDataBinding,
    record: object,
) -> tuple:
    selected = set()
    if NormalizationQualityFlag.INTERPOLATED in record.metadata.quality_flags:
        selected.add("interpolated")
    if binding.correction_selection.reason_codes == (
        CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,
    ):
        selected.add("correction_selected")
    if record.metadata.record_origin is DataOrigin.SYSTEM_COMPOSITE:
        selected.add("composite_input_used")
    return tuple(
        flag for flag in _COST_PROPAGATED_FLAG_ORDER if flag in selected
    )


def _cost_evidence_common(
    binding: SelectedFreshMarketDataBinding,
    record: object,
) -> dict:
    return {
        "record_id": record.metadata.record_id,
        "normalized_at": record.metadata.normalized_at,
        "source_ids": tuple(
            source.source_id for source in record.metadata.source_references
        ),
        "propagated_quality_flags": _cost_propagated_flags(binding, record),
    }


def _cost_contract_evidence(
    binding: SelectedFreshMarketDataBinding,
    record: object,
    leg: OptionLeg,
) -> dict:
    result = _cost_evidence_common(binding, record)
    result.update(_cost_contract_identity(record.contract_key))
    result["quantity"] = leg.quantity
    return result


def _canonical_cost_consumed(
    matched: tuple,
    structure: OptionStructure,
) -> Tuple[tuple, tuple, tuple]:
    canonical = tuple(
        next(item for item in matched if item[1] is leg)
        for leg in structure.legs
    )
    underlying_record = canonical[0][3]
    underlying_binding = canonical[0][2]
    records = (underlying_record,) + tuple(
        record
        for item in canonical
        for record in (item[5], item[7], item[9])
    )
    bindings = (underlying_binding,) + tuple(
        binding
        for item in canonical
        for binding in (item[4], item[6], item[8])
    )
    return canonical, records, bindings


def _construct_cost_parameters(
    canonical_matched: tuple,
    commissions_and_fees: decimal.Decimal,
    repeated_bet_count: int,
    methodology: tuple,
    decimal_values: tuple,
    record: StructureCosts,
) -> str:
    underlying_record_id = canonical_matched[0][3].metadata.record_id
    leg_correspondence = []
    for item in canonical_matched:
        contract_key, leg = item[0], item[1]
        underlying = contract_key.underlying_key
        leg_correspondence.append({
            "underlying": {
                "symbol": underlying.symbol,
                "listing_mic": underlying.listing_mic,
                "security_type": underlying.security_type.value,
                "currency": underlying.currency,
            },
            "option_type": contract_key.option_type,
            "expiration": contract_key.expiration,
            "strike": contract_key.strike,
            "currency": contract_key.currency,
            "deliverable_id": contract_key.deliverable_id,
            "contract_multiplier": contract_key.contract_multiplier,
            "quantity": leg.quantity,
            "underlying_quote_record_id": underlying_record_id,
            "option_quote_record_id": item[5].metadata.record_id,
            "option_greeks_record_id": item[7].metadata.record_id,
            "option_contract_reference_record_id": item[9].metadata.record_id,
        })
    methodology_parameters = {
        "model_name": methodology[0],
        "model_version": methodology[1],
        "rate_input_description": methodology[2],
        "dividend_input_description": methodology[3],
        "theta_day_basis": methodology[4],
        "unit_convention": methodology[5],
    }
    (
        quoted_mid,
        spread_cost,
        fees,
        theta,
        gamma,
        underlying_price,
    ) = decimal_values
    total_entry_cost = _exact_scaled_sum((
        (quoted_mid, 1),
        (spread_cost, 1),
        (fees, 1),
    ))
    cumulative_repeated_bet_cost = _exact_scaled_sum((
        (total_entry_cost, repeated_bet_count),
    ))
    stable_record_values = {
        "quoted_mid_premium_repr": repr(record.quoted_mid_premium),
        "estimated_spread_cost_repr": repr(record.estimated_spread_cost),
        "commissions_and_fees_repr": repr(record.commissions_and_fees),
        "theta_per_day_repr": repr(record.theta_per_day),
        "gamma_repr": repr(record.gamma),
        "underlying_price_repr": repr(record.underlying_price),
        "total_entry_cost_repr": repr(record.total_entry_cost),
        "maximum_loss_repr": repr(record.maximum_loss),
        "cumulative_repeated_bet_cost_repr": repr(
            record.cumulative_repeated_bet_cost
        ),
    }
    calculation_values = {
        "quoted_mid_premium_exact": quoted_mid,
        "estimated_spread_cost_exact": spread_cost,
        "commissions_and_fees_exact": fees,
        "theta_per_day_exact": theta,
        "gamma_exact": gamma,
        "underlying_price_exact": underlying_price,
        "total_entry_cost_exact": total_entry_cost,
        "maximum_loss_exact": total_entry_cost,
        "cumulative_repeated_bet_cost_exact": cumulative_repeated_bet_cost,
        "stable_record_values": stable_record_values,
    }
    underlying = canonical_matched[0][3]
    underlying_evidence = _cost_evidence_common(
        canonical_matched[0][2], underlying
    )
    underlying_evidence.update({
        "underlying": _cost_underlying_identity(underlying.underlying_key),
        "session_date": underlying.session_date,
        "bid_price": underlying.bid_price,
        "ask_price": underlying.ask_price,
        "midpoint_rule": "(bid_price+ask_price)/2",
        "underlying_price_exact": underlying_price,
    })
    option_quotes = []
    option_greeks = []
    contract_references = []
    for item in canonical_matched:
        leg = item[1]
        quote = item[5]
        greeks = item[7]
        reference = item[9]
        quote_evidence = _cost_contract_evidence(item[4], quote, leg)
        quote_evidence.update({
            "session_date": quote.session_date,
            "bid_premium": quote.bid_premium,
            "ask_premium": quote.ask_premium,
        })
        option_quotes.append(quote_evidence)
        greeks_evidence = _cost_contract_evidence(item[6], greeks, leg)
        greeks_evidence.update({
            "session_date": greeks.session_date,
            "gamma": greeks.gamma,
            "theta": greeks.theta,
            "theta_day_basis": greeks.theta_day_basis,
            "model_name": greeks.model_name,
            "model_version": greeks.model_version,
            "rate_input_description": greeks.rate_input_description,
            "dividend_input_description": greeks.dividend_input_description,
            "unit_convention": greeks.metadata.unit_convention,
        })
        option_greeks.append(greeks_evidence)
        reference_evidence = _cost_contract_evidence(
            item[8], reference, leg
        )
        reference_evidence.update({
            "listing_date": reference.listing_date,
            "last_trade_date": reference.last_trade_date,
            "exercise_style": reference.exercise_style,
            "settlement_type": reference.settlement_type,
        })
        contract_references.append(reference_evidence)
    normalized_evidence = {
        "underlying_quote": underlying_evidence,
        "option_quotes": tuple(option_quotes),
        "option_greeks": tuple(option_greeks),
        "contract_references": tuple(contract_references),
    }
    structure = record.structure
    structure_identity = {
        "structure_type": structure.structure_type,
        "underlying": structure.underlying,
        "assumed_portfolio_value_repr": repr(
            structure.assumed_portfolio_value
        ),
        "expected_holding_days": structure.expected_holding_days,
        "legs": tuple(
            _cost_structure_leg_identity(leg) for leg in structure.legs
        ),
    }
    return canonicalize_lineage_parameters({
        "commission_and_fee_scope": "entry_only_total_position",
        "commissions_and_fees_usd": commissions_and_fees,
        "gamma_input_unit": (
            "option_value_change_per_usd_squared_per_underlying_unit"
        ),
        "gamma_position_rule": (
            "sum(gamma_per_underlying_unit_per_usd_squared*quantity*"
            "contract_multiplier)"
        ),
        "greeks_methodology": methodology_parameters,
        "leg_correspondence": leg_correspondence,
        "position_value_unit": "usd",
        "premium_input_unit": "usd_per_underlying_unit",
        "premium_midpoint_rule": (
            "sum(((bid_premium+ask_premium)/2)*quantity*contract_multiplier)"
        ),
        "repeated_bet_count": repeated_bet_count,
        "spread_cost_rule": (
            "sum(((ask_premium-bid_premium)/2)*quantity*contract_multiplier)"
        ),
        "spread_cost_scope": "entry_only_midpoint_to_ask",
        "theta_day_basis": methodology[4],
        "theta_input_unit": (
            "usd_per_underlying_unit_per_declared_day_basis"
        ),
        "theta_position_rule": (
            "sum(theta_per_underlying_unit_per_declared_day_basis*quantity*"
            "contract_multiplier)"
        ),
        "underlying_price_rule": "(bid_price+ask_price)/2",
        "underlying_price_unit": "usd_per_underlying_share",
        "calculation_values": calculation_values,
        "normalized_evidence": normalized_evidence,
        "structure_identity": structure_identity,
    })


def _derive_cost_quality_flags(
    bindings: tuple,
    records: tuple,
) -> Tuple[CalculationQualityFlag, ...]:
    selected = set(_derive_quality_flags(bindings, records))
    selected.add(CalculationQualityFlag.ASSUMPTION_APPLIED)
    return tuple(flag for flag in CalculationQualityFlag if flag in selected)


def _validate_complete_cost_evidence(records: tuple) -> None:
    if any(
        NormalizationQualityFlag.INCOMPLETE in record.metadata.quality_flags
        or any(
            SourceQualityFlag.PARTIAL in source.quality_flags
            for source in record.metadata.source_references
        )
        for record in records
    ):
        raise ValueError("structure costs require complete normalized evidence")


def _decode_cost_parameters(parameters_json: str) -> dict:
    def reject_float(_value: str) -> object:
        raise ValueError("3C.7b v0.2 parameters must not contain JSON floats")

    def reject_constant(_value: str) -> object:
        raise ValueError(
            "3C.7b v0.2 parameters must not contain nonfinite constants"
        )

    def unique_object(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(
                    "3C.7b v0.2 parameters contain a duplicate JSON key"
                )
            result[key] = value
        return result

    try:
        raw = json.loads(
            parameters_json,
            parse_float=reject_float,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError("3C.7b v0.2 parameters_json is invalid") from error

    def decode(value: object) -> object:
        if value is None or type(value) in (bool, int, str):
            return value
        if type(value) is list:
            return tuple(decode(item) for item in value)
        if type(value) is not dict or len(value) != 1:
            raise ValueError("3C.7b v0.2 parameters use unsupported JSON")
        tag, payload = next(iter(value.items()))
        if tag == "$map":
            if type(payload) is not list:
                raise ValueError("$map payload must be a list")
            result = {}
            for pair in payload:
                if (
                    type(pair) is not list
                    or len(pair) != 2
                    or type(pair[0]) is not str
                    or pair[0] in result
                ):
                    raise ValueError(
                        "$map entries must have unique string keys"
                    )
                result[pair[0]] = decode(pair[1])
            return result
        if tag == "$list":
            if type(payload) is not list:
                raise ValueError("$list payload must be a list")
            return tuple(decode(item) for item in payload)
        if tag == "$decimal":
            if type(payload) is not str:
                raise ValueError("$decimal payload must be a string")
            try:
                result = decimal.Decimal(payload)
            except decimal.InvalidOperation as error:
                raise ValueError("$decimal payload is invalid") from error
            if not result.is_finite():
                raise ValueError("$decimal payload must be finite")
            return result
        if tag == "$date":
            if type(payload) is not str:
                raise ValueError("$date payload must be a string")
            try:
                result = datetime.date.fromisoformat(payload)
            except ValueError as error:
                raise ValueError("$date payload is invalid") from error
            if result.isoformat() != payload:
                raise ValueError("$date payload is noncanonical")
            return result
        if tag == "$datetime":
            if type(payload) is not str or not payload.endswith("Z"):
                raise ValueError("$datetime payload must be canonical UTC")
            try:
                result = datetime.datetime.fromisoformat(
                    payload[:-1] + "+00:00"
                )
            except ValueError as error:
                raise ValueError("$datetime payload is invalid") from error
            if result.isoformat().replace("+00:00", "Z") != payload:
                raise ValueError("$datetime payload is noncanonical")
            return result
        raise ValueError("3C.7b v0.2 parameters contain an unknown tag")

    decoded = decode(raw)
    if type(decoded) is not dict:
        raise ValueError("3C.7b v0.2 parameters root must be a tagged map")
    if set(decoded) != _COST_PARAMETER_KEYS:
        raise ValueError(
            "3C.7b v0.2 parameters have the wrong exact 20-key schema"
        )
    try:
        if canonicalize_lineage_parameters(decoded) != parameters_json:
            raise ValueError("3C.7b v0.2 parameters are not byte-canonical")
    except (TypeError, ValueError) as error:
        raise ValueError(
            "3C.7b v0.2 parameters are not canonical"
        ) from error
    return decoded


def _cost_exact_dict(
    value: object,
    keys: set,
    label: str,
) -> dict:
    if type(value) is not dict:
        raise TypeError(f"{label} must have exact type dict")
    if set(value) != keys:
        raise ValueError(f"{label} has the wrong exact key schema")
    return value


def _cost_exact_tuple(value: object, label: str) -> tuple:
    if type(value) is not tuple:
        raise TypeError(f"{label} must have exact type tuple")
    return value


def _cost_required_string(value: object, label: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must have exact type str")
    if not value or value.strip() != value:
        raise ValueError(f"{label} must be a canonical nonempty string")
    return value


def _cost_stable_float_repr(value: object, label: str) -> float:
    text = _cost_required_string(value, label)
    try:
        converted = float(text)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{label} must represent a finite float") from error
    if not math.isfinite(converted) or repr(converted) != text:
        raise ValueError(f"{label} must be a canonical finite float repr")
    return converted


def _validate_cost_underlying_identity(
    value: object,
    expected_symbol: str,
) -> dict:
    identity = _cost_exact_dict(
        value, _COST_UNDERLYING_KEYS, "underlying identity"
    )
    for key in ("symbol", "security_type", "currency"):
        _cost_required_string(identity[key], f"underlying identity {key}")
    if identity["listing_mic"] is not None:
        _cost_required_string(
            identity["listing_mic"], "underlying identity listing_mic"
        )
    if (
        identity["symbol"] != expected_symbol
        or identity["security_type"] not in {"equity", "etf"}
        or identity["currency"] != "USD"
    ):
        raise ValueError("underlying identity does not match the structure")
    return identity


def _validate_cost_evidence_common(value: dict) -> tuple:
    record_id = _cost_required_string(value["record_id"], "record_id")
    normalized_at = value["normalized_at"]
    if type(normalized_at) is not datetime.datetime:
        raise TypeError("normalized_at must have exact type datetime")
    if (
        normalized_at.tzinfo is None
        or normalized_at.utcoffset() != datetime.timedelta(0)
    ):
        raise ValueError("normalized_at must be an aware UTC datetime")
    source_ids = _cost_exact_tuple(value["source_ids"], "source_ids")
    if any(type(item) is not str for item in source_ids):
        raise TypeError("every source_ids item must have exact type str")
    if (
        not source_ids
        or any(not item or item.strip() != item for item in source_ids)
        or len(set(source_ids)) != len(source_ids)
        or source_ids != tuple(sorted(source_ids))
    ):
        raise ValueError(
            "source_ids must be unique canonical strings in lexical order"
        )
    flags = _cost_exact_tuple(
        value["propagated_quality_flags"], "propagated_quality_flags"
    )
    if any(type(item) is not str for item in flags):
        raise TypeError(
            "every propagated quality flag must have exact type str"
        )
    if (
        len(set(flags)) != len(flags)
        or flags != tuple(
            item for item in _COST_PROPAGATED_FLAG_ORDER if item in set(flags)
        )
    ):
        raise ValueError("propagated quality flags are invalid")
    return record_id, normalized_at, source_ids, flags


def _validate_cost_contract_evidence(
    value: dict,
    leg: OptionLeg,
    expected_underlying: dict,
) -> None:
    if value["underlying"] != expected_underlying:
        raise ValueError("contract underlying identity is inconsistent")
    if type(value["option_type"]) is not str:
        raise TypeError("contract option_type must have exact type str")
    if type(value["expiration"]) is not datetime.date:
        raise TypeError("contract expiration must have exact type date")
    if type(value["strike"]) is not decimal.Decimal:
        raise TypeError("contract strike must have exact type Decimal")
    if type(value["currency"]) is not str:
        raise TypeError("contract currency must have exact type str")
    if (
        value["deliverable_id"] is not None
        and type(value["deliverable_id"]) is not str
    ):
        raise TypeError("contract deliverable_id must be str or None")
    if (
        type(value["deliverable_id"]) is str
        and (
            not value["deliverable_id"]
            or value["deliverable_id"].strip() != value["deliverable_id"]
        )
    ):
        raise ValueError("contract deliverable_id must be canonical")
    if type(value["contract_multiplier"]) is not int:
        raise TypeError("contract_multiplier must have exact type int")
    if type(value["quantity"]) is not int:
        raise TypeError("quantity must have exact type int")
    if (
        value["option_type"] != leg.option_type
        or value["expiration"] != leg.expiration
        or value["strike"] != decimal.Decimal(str(leg.strike))
        or value["currency"] != expected_underlying["currency"]
        or value["contract_multiplier"] != leg.contract_multiplier
        or value["quantity"] != leg.quantity
    ):
        raise ValueError("contract evidence does not match the structure leg")


def _validate_cost_fixed_parameters(decoded: dict) -> dict:
    fixed = {
        "commission_and_fee_scope": "entry_only_total_position",
        "gamma_input_unit": (
            "option_value_change_per_usd_squared_per_underlying_unit"
        ),
        "gamma_position_rule": (
            "sum(gamma_per_underlying_unit_per_usd_squared*quantity*"
            "contract_multiplier)"
        ),
        "position_value_unit": "usd",
        "premium_input_unit": "usd_per_underlying_unit",
        "premium_midpoint_rule": (
            "sum(((bid_premium+ask_premium)/2)*quantity*contract_multiplier)"
        ),
        "spread_cost_rule": (
            "sum(((ask_premium-bid_premium)/2)*quantity*contract_multiplier)"
        ),
        "spread_cost_scope": "entry_only_midpoint_to_ask",
        "theta_input_unit": (
            "usd_per_underlying_unit_per_declared_day_basis"
        ),
        "theta_position_rule": (
            "sum(theta_per_underlying_unit_per_declared_day_basis*quantity*"
            "contract_multiplier)"
        ),
        "underlying_price_rule": "(bid_price+ask_price)/2",
        "underlying_price_unit": "usd_per_underlying_share",
    }
    for key, expected in fixed.items():
        if type(decoded[key]) is not str:
            raise TypeError(f"{key} must have exact type str")
        if decoded[key] != expected:
            raise ValueError(f"{key} has an unsupported value")
    if type(decoded["commissions_and_fees_usd"]) is not decimal.Decimal:
        raise TypeError("commissions_and_fees_usd must be a Decimal")
    if (
        not decoded["commissions_and_fees_usd"].is_finite()
        or decoded["commissions_and_fees_usd"] < 0
    ):
        raise ValueError("commissions_and_fees_usd must be finite and nonnegative")
    if type(decoded["repeated_bet_count"]) is not int:
        raise TypeError("repeated_bet_count must have exact type int")
    if decoded["repeated_bet_count"] <= 0:
        raise ValueError("repeated_bet_count must be positive")
    methodology = _cost_exact_dict(
        decoded["greeks_methodology"],
        _COST_METHODOLOGY_KEYS,
        "greeks_methodology",
    )
    for key in (
        "model_name",
        "rate_input_description",
        "dividend_input_description",
        "theta_day_basis",
        "unit_convention",
    ):
        _cost_required_string(methodology[key], f"greeks_methodology {key}")
    if methodology["model_version"] is not None:
        _cost_required_string(
            methodology["model_version"], "greeks_methodology model_version"
        )
    if type(decoded["theta_day_basis"]) is not str:
        raise TypeError("theta_day_basis must have exact type str")
    if decoded["theta_day_basis"] != methodology["theta_day_basis"]:
        raise ValueError("theta_day_basis must match greeks_methodology")
    return methodology


def _validate_cost_structure_identity(
    value: object,
    record: StructureCosts,
) -> tuple:
    identity = _cost_exact_dict(
        value,
        {
            "structure_type",
            "underlying",
            "assumed_portfolio_value_repr",
            "expected_holding_days",
            "legs",
        },
        "structure_identity",
    )
    if type(record.structure) is not OptionStructure:
        raise TypeError("record structure must have exact type OptionStructure")
    for key in ("structure_type", "underlying"):
        if type(identity[key]) is not str:
            raise TypeError(f"structure_identity {key} must have exact type str")
    if type(identity["expected_holding_days"]) is not int:
        raise TypeError(
            "structure_identity expected_holding_days must have exact type int"
        )
    _cost_required_string(
        identity["assumed_portfolio_value_repr"],
        "assumed_portfolio_value_repr",
    )
    if (
        identity["structure_type"] != record.structure.structure_type
        or identity["underlying"] != record.structure.underlying
        or identity["assumed_portfolio_value_repr"]
        != repr(record.structure.assumed_portfolio_value)
        or identity["expected_holding_days"]
        != record.structure.expected_holding_days
    ):
        raise ValueError("structure_identity does not match the public structure")
    legs = _cost_exact_tuple(identity["legs"], "structure_identity legs")
    if len(legs) != len(record.structure.legs):
        raise ValueError("structure_identity leg count is inconsistent")
    for value_leg, public_leg in zip(legs, record.structure.legs):
        exact_leg = _cost_exact_dict(
            value_leg, _COST_LEG_IDENTITY_KEYS, "structure_identity leg"
        )
        for key in ("underlying", "option_type", "strike_float_repr"):
            if type(exact_leg[key]) is not str:
                raise TypeError(
                    f"structure_identity leg {key} must have exact type str"
                )
        if type(exact_leg["expiration"]) is not datetime.date:
            raise TypeError(
                "structure_identity leg expiration must have exact type date"
            )
        for key in ("quantity", "contract_multiplier"):
            if type(exact_leg[key]) is not int:
                raise TypeError(
                    f"structure_identity leg {key} must have exact type int"
                )
        if (
            exact_leg["underlying"] != public_leg.underlying
            or exact_leg["option_type"] != public_leg.option_type
            or exact_leg["strike_float_repr"] != repr(public_leg.strike)
            or exact_leg["expiration"] != public_leg.expiration
            or exact_leg["quantity"] != public_leg.quantity
            or exact_leg["contract_multiplier"]
            != public_leg.contract_multiplier
        ):
            raise ValueError(
                "structure_identity leg does not match the public structure"
            )
        _cost_required_string(
            exact_leg["strike_float_repr"], "strike_float_repr"
        )
    return legs


def _validate_structure_costs_result(
    record: StructureCosts,
    lineage: CalculationLineage,
) -> None:
    if (
        lineage.calculation_type != "structure_costs"
        or lineage.methodology_id != "exact-structure-costs"
        or lineage.methodology_version != "v0.2"
    ):
        raise ValueError("lineage has the wrong 3C.7b v0.2 identity")
    decoded = _decode_cost_parameters(lineage.parameters_json)
    methodology = _validate_cost_fixed_parameters(decoded)
    _validate_cost_structure_identity(
        decoded["structure_identity"], record
    )
    if type(record.as_of_date) is not datetime.date:
        raise TypeError("record as_of_date must have exact type date")

    evidence = _cost_exact_dict(
        decoded["normalized_evidence"],
        _COST_EVIDENCE_KEYS,
        "normalized_evidence",
    )
    underlying = _cost_exact_dict(
        evidence["underlying_quote"],
        _COST_COMMON_EVIDENCE_FIELDS
        | {
            "underlying",
            "session_date",
            "bid_price",
            "ask_price",
            "midpoint_rule",
            "underlying_price_exact",
        },
        "underlying_quote evidence",
    )
    _validate_cost_evidence_common(underlying)
    underlying_identity = _validate_cost_underlying_identity(
        underlying["underlying"], record.structure.underlying
    )
    if type(underlying["session_date"]) is not datetime.date:
        raise TypeError("underlying evidence session_date must be an exact date")
    if type(underlying["midpoint_rule"]) is not str:
        raise TypeError("underlying evidence midpoint_rule must be str")
    for key in ("bid_price", "ask_price", "underlying_price_exact"):
        if type(underlying[key]) is not decimal.Decimal:
            raise TypeError(f"underlying evidence {key} must be a Decimal")
        if not underlying[key].is_finite():
            raise ValueError(f"underlying evidence {key} must be finite")
    if (
        underlying["bid_price"] <= 0
        or underlying["ask_price"] <= 0
        or underlying["ask_price"] < underlying["bid_price"]
        or underlying["midpoint_rule"] != "(bid_price+ask_price)/2"
        or underlying["session_date"] != record.as_of_date
    ):
        raise ValueError("underlying quote evidence is inconsistent")
    expected_underlying_price = _exact_half(_exact_scaled_sum((
        (underlying["bid_price"], 1),
        (underlying["ask_price"], 1),
    )))
    if underlying["underlying_price_exact"] != expected_underlying_price:
        raise ValueError("underlying midpoint evidence is inconsistent")

    quotes = _cost_exact_tuple(evidence["option_quotes"], "option_quotes")
    greeks = _cost_exact_tuple(evidence["option_greeks"], "option_greeks")
    references = _cost_exact_tuple(
        evidence["contract_references"], "contract_references"
    )
    leg_count = len(record.structure.legs)
    if not (len(quotes) == len(greeks) == len(references) == leg_count):
        raise ValueError("normalized evidence must cover every structure leg")
    quote_keys = (
        _COST_COMMON_EVIDENCE_FIELDS
        | _COST_CONTRACT_FIELDS
        | {"quantity", "session_date", "bid_premium", "ask_premium"}
    )
    greeks_keys = (
        _COST_COMMON_EVIDENCE_FIELDS
        | _COST_CONTRACT_FIELDS
        | {
            "quantity",
            "session_date",
            "gamma",
            "theta",
            "theta_day_basis",
            "model_name",
            "model_version",
            "rate_input_description",
            "dividend_input_description",
            "unit_convention",
        }
    )
    reference_keys = (
        _COST_COMMON_EVIDENCE_FIELDS
        | _COST_CONTRACT_FIELDS
        | {
            "quantity",
            "listing_date",
            "last_trade_date",
            "exercise_style",
            "settlement_type",
        }
    )
    common_records = [underlying]
    for index, public_leg in enumerate(record.structure.legs):
        quote = _cost_exact_dict(
            quotes[index], quote_keys, "option quote evidence"
        )
        greek = _cost_exact_dict(
            greeks[index], greeks_keys, "option Greeks evidence"
        )
        reference = _cost_exact_dict(
            references[index], reference_keys, "contract reference evidence"
        )
        for item in (quote, greek, reference):
            _validate_cost_evidence_common(item)
            _validate_cost_contract_evidence(
                item, public_leg, underlying_identity
            )
            common_records.append(item)
        contract_identity = {
            key: quote[key] for key in _COST_CONTRACT_FIELDS
        }
        if any(
            {key: item[key] for key in _COST_CONTRACT_FIELDS}
            != contract_identity
            for item in (greek, reference)
        ):
            raise ValueError("leg evidence contract identities are inconsistent")
        for key in ("bid_premium", "ask_premium"):
            if type(quote[key]) is not decimal.Decimal:
                raise TypeError(f"{key} must have exact type Decimal")
            if not quote[key].is_finite():
                raise ValueError(f"{key} must be finite")
        if type(quote["session_date"]) is not datetime.date:
            raise TypeError("option quote session_date must be an exact date")
        if (
            quote["session_date"] != record.as_of_date
            or quote["bid_premium"] < 0
            or quote["ask_premium"] <= 0
            or quote["ask_premium"] < quote["bid_premium"]
        ):
            raise ValueError("option quote evidence is inconsistent")
        for key in ("gamma", "theta"):
            if type(greek[key]) is not decimal.Decimal:
                raise TypeError(f"{key} must have exact type Decimal")
            if not greek[key].is_finite():
                raise ValueError(f"{key} must be finite")
        if type(greek["session_date"]) is not datetime.date:
            raise TypeError("Greeks session_date must be an exact date")
        for key in (
            "theta_day_basis",
            "model_name",
            "rate_input_description",
            "dividend_input_description",
            "unit_convention",
        ):
            _cost_required_string(greek[key], f"Greeks evidence {key}")
        if greek["model_version"] is not None:
            _cost_required_string(
                greek["model_version"], "Greeks evidence model_version"
            )
        if (
            greek["session_date"] != record.as_of_date
            or greek["gamma"] < 0
            or greek["theta"] > 0
        ):
            raise ValueError("Greeks evidence is inconsistent")
        for key in _COST_METHODOLOGY_KEYS:
            if greek[key] != methodology[key]:
                raise ValueError(
                    "Greeks evidence methodology is inconsistent"
                )
        for key in ("listing_date", "last_trade_date"):
            if reference[key] is not None and type(reference[key]) is not datetime.date:
                raise TypeError(f"{key} must be an exact date or None")
        for key in ("exercise_style", "settlement_type"):
            if reference[key] is not None:
                _cost_required_string(reference[key], key)
        if (
            reference["exercise_style"] != "American"
            or reference["settlement_type"] != "Physical"
        ):
            raise ValueError(
                "contract reference exercise and settlement are unsupported"
            )
        listing_date = reference["listing_date"]
        last_trade_date = reference["last_trade_date"]
        if (
            (listing_date is not None and listing_date > record.as_of_date)
            or (last_trade_date is not None
                and last_trade_date < record.as_of_date)
            or (listing_date is not None and last_trade_date is not None
                and listing_date > last_trade_date)
            or (last_trade_date is not None
                and last_trade_date > public_leg.expiration)
        ):
            raise ValueError("contract reference chronology is inconsistent")

    correspondence = _cost_exact_tuple(
        decoded["leg_correspondence"], "leg_correspondence"
    )
    correspondence_keys = _COST_CONTRACT_FIELDS | {
        "quantity",
        "underlying_quote_record_id",
        "option_quote_record_id",
        "option_greeks_record_id",
        "option_contract_reference_record_id",
    }
    if len(correspondence) != leg_count:
        raise ValueError("leg_correspondence must cover every leg")
    for index, public_leg in enumerate(record.structure.legs):
        item = _cost_exact_dict(
            correspondence[index],
            correspondence_keys,
            "leg_correspondence item",
        )
        _validate_cost_contract_evidence(
            item, public_leg, underlying_identity
        )
        expected_ids = {
            "underlying_quote_record_id": underlying["record_id"],
            "option_quote_record_id": quotes[index]["record_id"],
            "option_greeks_record_id": greeks[index]["record_id"],
            "option_contract_reference_record_id": references[index]["record_id"],
        }
        if any(item[key] != value for key, value in expected_ids.items()):
            raise ValueError("leg_correspondence record IDs are inconsistent")

    values = _cost_exact_dict(
        decoded["calculation_values"],
        _COST_CALCULATION_VALUE_KEYS,
        "calculation_values",
    )
    stable = _cost_exact_dict(
        values["stable_record_values"],
        _COST_STABLE_VALUE_KEYS,
        "stable_record_values",
    )
    for key in _COST_CALCULATION_VALUE_KEYS - {"stable_record_values"}:
        if type(values[key]) is not decimal.Decimal:
            raise TypeError(f"{key} must have exact type Decimal")
        if not values[key].is_finite():
            raise ValueError(f"{key} must be finite")
    bid_total = _exact_scaled_sum(tuple(
        (quote["bid_premium"], leg.quantity * leg.contract_multiplier)
        for quote, leg in zip(quotes, record.structure.legs)
    ))
    ask_total = _exact_scaled_sum(tuple(
        (quote["ask_premium"], leg.quantity * leg.contract_multiplier)
        for quote, leg in zip(quotes, record.structure.legs)
    ))
    exact_expected = {
        "quoted_mid_premium_exact": _exact_half(_exact_scaled_sum((
            (bid_total, 1), (ask_total, 1)
        ))),
        "estimated_spread_cost_exact": _exact_half(_exact_scaled_sum((
            (ask_total, 1), (bid_total.copy_negate(), 1)
        ))),
        "commissions_and_fees_exact": decoded["commissions_and_fees_usd"],
        "theta_per_day_exact": _exact_scaled_sum(tuple(
            (greek["theta"], leg.quantity * leg.contract_multiplier)
            for greek, leg in zip(greeks, record.structure.legs)
        )),
        "gamma_exact": _exact_scaled_sum(tuple(
            (greek["gamma"], leg.quantity * leg.contract_multiplier)
            for greek, leg in zip(greeks, record.structure.legs)
        )),
        "underlying_price_exact": expected_underlying_price,
    }
    for key, expected in exact_expected.items():
        if values[key] != expected:
            raise ValueError(f"{key} does not match normalized evidence")
    exact_total = _exact_scaled_sum((
        (values["quoted_mid_premium_exact"], 1),
        (values["estimated_spread_cost_exact"], 1),
        (values["commissions_and_fees_exact"], 1),
    ))
    if (
        values["total_entry_cost_exact"] != exact_total
        or values["maximum_loss_exact"] != exact_total
        or values["cumulative_repeated_bet_cost_exact"]
        != _exact_scaled_sum(((exact_total, decoded["repeated_bet_count"]),))
    ):
        raise ValueError("derived exact cost values are inconsistent")

    direct_fields = (
        "quoted_mid_premium",
        "estimated_spread_cost",
        "commissions_and_fees",
        "theta_per_day",
        "gamma",
        "underlying_price",
    )
    for field in direct_fields:
        public_value = getattr(record, field)
        exact_value = values[f"{field}_exact"]
        stable_value = _cost_stable_float_repr(
            stable[f"{field}_repr"], f"{field}_repr"
        )
        if (
            not math.isfinite(public_value)
            or float(exact_value) != public_value
            or stable_value != public_value
            or stable[f"{field}_repr"] != repr(public_value)
        ):
            raise ValueError(f"public {field} does not match exact evidence")
    stable_total = (
        record.quoted_mid_premium
        + record.estimated_spread_cost
        + record.commissions_and_fees
    )
    if record.total_entry_cost != stable_total:
        raise ValueError("public total_entry_cost is inconsistent")
    stable_total_value = _cost_stable_float_repr(
        stable["total_entry_cost_repr"], "total_entry_cost_repr"
    )
    stable_maximum = _cost_stable_float_repr(
        stable["maximum_loss_repr"], "maximum_loss_repr"
    )
    stable_cumulative = _cost_stable_float_repr(
        stable["cumulative_repeated_bet_cost_repr"],
        "cumulative_repeated_bet_cost_repr",
    )
    if (
        stable_total_value != record.total_entry_cost
        or stable["total_entry_cost_repr"] != repr(record.total_entry_cost)
        or stable_maximum != record.maximum_loss
        or stable["maximum_loss_repr"] != repr(record.maximum_loss)
    ):
        raise ValueError("stable total or maximum-loss evidence is inconsistent")
    if decoded["repeated_bet_count"] != record.repeated_bet_count:
        raise ValueError("repeated_bet_count does not match the public record")
    if (
        stable_cumulative != record.cumulative_repeated_bet_cost
        or stable["cumulative_repeated_bet_cost_repr"]
        != repr(record.cumulative_repeated_bet_cost)
    ):
        raise ValueError("stable repeated-bet evidence is inconsistent")

    generated_methodology = _greeks_methodology_disclosure((
        methodology["model_name"],
        methodology["model_version"],
        methodology["rate_input_description"],
        methodology["dividend_input_description"],
        methodology["theta_day_basis"],
        methodology["unit_convention"],
    ))
    if generated_methodology != record.greeks_methodology:
        raise ValueError("public Greeks methodology is inconsistent")

    evidence_references = tuple(
        (
            item["record_id"],
            item["normalized_at"],
            item["source_ids"],
        )
        for item in common_records
    )
    if len({item[0] for item in evidence_references}) != len(
        evidence_references
    ):
        raise ValueError("normalized evidence record IDs must be unique")
    lineage_references = tuple(
        (item.record_id, item.normalized_at, item.source_ids)
        for item in lineage.inputs
    )
    if tuple(sorted(evidence_references)) != lineage_references:
        raise ValueError(
            "normalized evidence and lineage inputs do not correspond exactly"
        )

    propagated = {
        flag for item in common_records
        for flag in item["propagated_quality_flags"]
    }
    required_flags = {
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    propagated_map = {
        "interpolated": CalculationQualityFlag.INTERPOLATED,
        "correction_selected": CalculationQualityFlag.CORRECTION_SELECTED,
        "composite_input_used": CalculationQualityFlag.COMPOSITE_INPUT_USED,
    }
    required_flags.update(propagated_map[flag] for flag in propagated)
    expected_flags = tuple(
        flag for flag in CalculationQualityFlag if flag in required_flags
    )
    if lineage.quality_flags != expected_flags:
        raise ValueError("lineage quality flags do not match disclosed evidence")

    if any(
        normalized_at > lineage.calculated_at
        for _record_id, normalized_at, _source_ids in evidence_references
    ):
        raise ValueError("lineage calculation precedes normalized evidence")
    if any(record.as_of_date >= leg.expiration for leg in record.structure.legs):
        raise ValueError("record as_of_date must precede every expiration")


def _construct_cost_lineage(
    calculation_id: str,
    calculated_at: datetime.datetime,
    inputs: tuple,
    parameters_json: str,
    quality_flags: tuple,
) -> CalculationLineage:
    return CalculationLineage(
        calculation_id=calculation_id,
        calculation_type="structure_costs",
        methodology_id="exact-structure-costs",
        methodology_version="v0.2",
        calculated_at=calculated_at,
        inputs=inputs,
        parameters_json=parameters_json,
        quality_flags=quality_flags,
    )


def transform_structure_costs(
    calculation_id: object,
    structure: object,
    relationship_selection: object,
    commissions_and_fees: object,
    repeated_bet_count: object,
    calculated_at: object,
) -> StructureCostsTransformationResult:
    """Transform one exact selected structure proof into costs and lineage."""

    normalized_id = _validate_calculation_id(calculation_id)
    exact_structure = _validate_structure(structure)
    selection = _validate_relationship_selection(relationship_selection)
    exact_fees = _validate_commissions_and_fees(commissions_and_fees)
    exact_repeated_bet_count = _validate_repeated_bet_count(repeated_bet_count)
    normalized_at = _normalize_calculated_at(calculated_at)
    _validate_selection_status(selection)
    selected = _resolve_selected_candidate(selection)
    groups, bindings = _validate_cost_selected_shape(selected, exact_structure)
    entries = _resolve_selected_objects(groups, bindings)
    _validate_cost_selected_record_types(entries)
    _validate_cost_proof_integrity(entries, bindings)
    grouped = _validate_cost_repeated_references(entries, groups, exact_structure)
    matched = _match_cost_structure_legs(grouped, exact_structure)
    as_of_date = _validate_cost_sessions(matched)
    methodology = _validate_cost_values_and_methodology(matched)
    decimal_values = _aggregate_cost_decimals(matched, exact_fees)
    (
        quoted_mid,
        spread_cost,
        fees,
        theta,
        gamma,
        underlying_price,
    ) = _convert_cost_values(decimal_values)
    record = StructureCosts(
        structure=exact_structure,
        as_of_date=as_of_date,
        quoted_mid_premium=quoted_mid,
        estimated_spread_cost=spread_cost,
        commissions_and_fees=fees,
        theta_per_day=theta,
        gamma=gamma,
        underlying_price=underlying_price,
        greeks_methodology=_greeks_methodology_disclosure(methodology),
        repeated_bet_count=exact_repeated_bet_count,
    )
    canonical_matched, records, consumed_bindings = _canonical_cost_consumed(
        matched, exact_structure
    )
    _validate_complete_cost_evidence(records)
    inputs = _construct_input_references(records)
    parameters_json = _construct_cost_parameters(
        canonical_matched,
        exact_fees,
        exact_repeated_bet_count,
        methodology,
        decimal_values,
        record,
    )
    quality_flags = _derive_cost_quality_flags(consumed_bindings, records)
    lineage = _construct_cost_lineage(
        normalized_id,
        normalized_at,
        inputs,
        parameters_json,
        quality_flags,
    )
    return StructureCostsTransformationResult(record=record, lineage=lineage)


def _validate_historical_transformation_assessment(
    value: object,
    price_basis: HistoricalReturnPriceBasis,
) -> Tuple[
    MarketDataHistoricalSeriesRequest,
    Tuple[SelectedFreshMarketDataBinding, ...],
    Tuple[UnderlyingDailyBarObservation, ...],
]:
    """Validate only retained 3C.6 facts needed for safe transformation."""

    if type(value) is not MarketDataHistoricalSeriesAssessment:
        raise TypeError(
            "historical_series_assessment must have exact type "
            "MarketDataHistoricalSeriesAssessment"
        )
    request = value.request
    if type(request) is not MarketDataHistoricalSeriesRequest:
        raise TypeError(
            "historical assessment request must have exact type "
            "MarketDataHistoricalSeriesRequest"
        )
    if type(request.underlying_key) is not UnderlyingKey:
        raise TypeError(
            "historical request underlying_key must have exact type "
            "UnderlyingKey"
        )
    if type(request.frequency) is not MarketDataHistoricalSeriesFrequency:
        raise TypeError(
            "historical request frequency must have exact type "
            "MarketDataHistoricalSeriesFrequency"
        )
    if request.frequency is not MarketDataHistoricalSeriesFrequency.DAILY:
        raise ValueError("historical request frequency must be daily")
    expected_dates = request.expected_session_dates
    if type(expected_dates) is not tuple:
        raise TypeError("expected_session_dates must have exact type tuple")
    if any(type(item) is not datetime.date for item in expected_dates):
        raise TypeError(
            "every expected_session_dates item must have exact type date"
        )
    if not expected_dates or any(
        current <= previous
        for previous, current in zip(expected_dates, expected_dates[1:])
    ):
        raise ValueError(
            "expected_session_dates must be nonempty and strictly ascending"
        )

    bindings = value.bindings
    if type(bindings) is not tuple:
        raise TypeError("historical assessment bindings must have exact type tuple")
    for binding in bindings:
        if type(binding) is not SelectedFreshMarketDataBinding:
            raise TypeError(
                "every historical binding must have exact type "
                "SelectedFreshMarketDataBinding"
            )
    bars = []
    all_candidate_record_ids = []
    regimes = []
    for binding in bindings:
        if type(binding.candidate_records) is not tuple:
            raise TypeError("candidate_records must have exact type tuple")
        if not binding.candidate_records:
            raise ValueError("candidate_records must not be empty")
        if type(binding.correction_selection) is not CorrectionSelection:
            raise TypeError(
                "correction_selection must have exact type CorrectionSelection"
            )
        if type(binding.freshness_policy) is not MarketDataFreshnessPolicy:
            raise TypeError(
                "freshness_policy must have exact type "
                "MarketDataFreshnessPolicy"
            )
        if type(binding.freshness_context) is not FreshnessContext:
            raise TypeError(
                "freshness_context must have exact type FreshnessContext"
            )
        if type(binding.freshness_assessment) is not FreshnessAssessment:
            raise TypeError(
                "freshness_assessment must have exact type FreshnessAssessment"
            )
        selection = binding.correction_selection
        candidate_ids = tuple(
            getattr(getattr(candidate, "metadata", None), "record_id", None)
            for candidate in binding.candidate_records
        )
        if (
            any(type(item) is not str for item in candidate_ids)
            or len(set(candidate_ids)) != len(candidate_ids)
            or tuple(sorted(candidate_ids)) != selection.candidate_record_ids
        ):
            raise ValueError(
                "candidate records do not match the retained correction proof"
            )
        all_candidate_record_ids.extend(candidate_ids)
        matches = tuple(
            candidate
            for candidate in binding.candidate_records
            if candidate.metadata.record_id == selection.selected_record_id
        )
        if len(matches) != 1:
            raise ValueError(
                "each binding must retain exactly one selected record"
            )
        bar = matches[0]
        if type(bar) is not UnderlyingDailyBarObservation:
            raise TypeError(
                "every selected record must have exact type "
                "UnderlyingDailyBarObservation"
            )
        if type(bar.session_date) is not datetime.date:
            raise TypeError("selected bar session_date must have exact type date")
        if type(bar.metadata) is not NormalizationMetadata:
            raise TypeError(
                "selected bar metadata must have exact type "
                "NormalizationMetadata"
            )
        if type(bar.metadata.source_references) is not tuple:
            raise TypeError("source_references must have exact type tuple")
        if any(
            type(source) is not SourceReference
            for source in bar.metadata.source_references
        ):
            raise TypeError(
                "every consumed source must have exact type SourceReference"
            )
        if selection.status is not CorrectionSelectionStatus.SELECTED:
            raise ValueError("every retained correction proof must be selected")
        if selection.reason_codes not in tuple(
            (reason,) for reason in _SELECTED_CORRECTION_REASONS
        ):
            raise ValueError("retained correction selection reason is malformed")
        freshness = binding.freshness_assessment
        if (
            semantic_observation_key(bar)
            != selection.semantic_observation_key
            or freshness.record_id != bar.metadata.record_id
            or freshness.category is not MarketDataCategory.HISTORICAL_BAR
            or freshness.status is not FreshnessStatus.FRESH
            or freshness.reason_codes
            != (FreshnessReasonCode.FRESH_WITHIN_POLICY,)
            or freshness.policy_id != binding.freshness_policy.policy_id
            or freshness.policy_version
            != binding.freshness_policy.policy_version
            or freshness.evaluated_at
            != binding.freshness_context.evaluation_at
            or selection.evaluated_at
            > binding.freshness_context.evaluation_at
        ):
            raise ValueError("retained correction/freshness proof is malformed")
        if bar.underlying_key != request.underlying_key:
            raise ValueError("every consumed bar must match the request underlying")
        bars.append(bar)
        regimes.append((
            selection.rule_id,
            selection.rule_version,
            selection.evaluated_at,
            binding.freshness_policy,
            binding.freshness_context,
        ))

    if len(set(all_candidate_record_ids)) != len(all_candidate_record_ids):
        raise ValueError("candidate record IDs must be unique across bindings")
    selected_ids = tuple(bar.metadata.record_id for bar in bars)
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("selected record IDs must be unique")
    if regimes and any(regime != regimes[0] for regime in regimes[1:]):
        raise ValueError(
            "bindings must retain one correction and freshness proof regime"
        )

    reasons = value.reason_codes
    if type(reasons) is not tuple:
        raise TypeError("historical reason_codes must have exact type tuple")
    if any(
        type(reason) is not MarketDataHistoricalSeriesReasonCode
        for reason in reasons
    ):
        raise TypeError(
            "every historical reason code must have exact enum type"
        )
    reason_set = set(reasons)
    if reason_set & _HISTORICAL_SESSION_INTEGRITY_REASONS:
        raise ValueError("session-integrity assessment prevents transformation")
    if not reason_set.issubset(_HISTORICAL_ADJUSTMENT_ONLY_REASONS):
        raise ValueError("historical assessment contains an unsupported reason")
    if (
        price_basis is HistoricalReturnPriceBasis.ADJUSTED_CLOSE
        and reasons
    ):
        raise ValueError(
            "adjusted close requires an issue-free historical assessment"
        )

    ordered_bars = tuple(bars)
    actual_dates = tuple(bar.session_date for bar in ordered_bars)
    if actual_dates != expected_dates:
        raise ValueError(
            "selected bars must exactly cover the complete expected window"
        )
    if len(ordered_bars) < 3:
        raise ValueError("at least three historical bars are required")
    for bar in ordered_bars:
        if not bar.is_session_complete:
            raise ValueError("incomplete historical bar cannot be consumed")
        if NormalizationQualityFlag.INCOMPLETE in bar.metadata.quality_flags:
            raise ValueError("incomplete normalized input cannot be consumed")
        if any(
            SourceQualityFlag.PARTIAL in source.quality_flags
            for source in bar.metadata.source_references
        ):
            raise ValueError("partial source input cannot be consumed")
    return request, bindings, ordered_bars


def _extract_historical_prices(
    bars: Tuple[UnderlyingDailyBarObservation, ...],
    price_basis: HistoricalReturnPriceBasis,
) -> Tuple[Tuple[decimal.Decimal, ...], Optional[str]]:
    if price_basis is HistoricalReturnPriceBasis.RAW_CLOSE:
        prices = tuple(bar.close_price for bar in bars)
        methodology = None
    else:
        adjusted = tuple(bar.adjusted_close_price for bar in bars)
        if any(value is None for value in adjusted):
            raise ValueError("adjusted close is unavailable for a consumed bar")
        methodologies = tuple(bar.adjustment_methodology for bar in bars)
        if (
            any(
                type(value) is not str
                or not value
                or value.strip() != value
                for value in methodologies
            )
            or any(value != methodologies[0] for value in methodologies[1:])
        ):
            raise ValueError(
                "adjusted closes require one exact common methodology"
            )
        prices = adjusted
        methodology = methodologies[0]
    if any(type(price) is not decimal.Decimal for price in prices):
        raise TypeError("every selected-basis price must have exact type Decimal")
    if any(not price.is_finite() or price <= 0 for price in prices):
        raise ValueError(
            "every selected-basis price must be finite and positive"
        )
    return prices, methodology


def _construct_historical_parameters(
    record: HistoricalRealizedVolatility,
) -> str:
    underlying = record.underlying_key
    return canonicalize_lineage_parameters({
        "adjustment_methodology": record.adjustment_methodology,
        "annualization_rule": (
            "daily_sample_standard_deviation_times_square_root_sessions_per_year"
        ),
        "annualization_sessions_per_year": (
            record.annualization_sessions_per_year
        ),
        "expected_session_dates": record.session_dates,
        "price_basis": record.price_basis.value,
        "price_observation_count": record.price_observation_count,
        "price_unit": "usd_per_underlying_share",
        "return_association_rule": "ending_session",
        "return_formula": record.return_formula,
        "return_observation_count": record.return_observation_count,
        "return_unit": "decimal_ratio",
        "underlying": {
            "symbol": underlying.symbol,
            "listing_mic": underlying.listing_mic,
            "security_type": underlying.security_type.value,
            "currency": underlying.currency,
        },
        "variance_estimator": record.variance_estimator,
        "volatility_unit": "annualized_decimal_ratio",
        "window_end_session_date": record.end_session_date,
        "window_start_session_date": record.start_session_date,
    })


def _derive_historical_quality_flags(
    bindings: Tuple[SelectedFreshMarketDataBinding, ...],
    bars: Tuple[UnderlyingDailyBarObservation, ...],
    price_basis: HistoricalReturnPriceBasis,
) -> Tuple[CalculationQualityFlag, ...]:
    selected = set(_derive_quality_flags(bindings, bars))
    selected.update({
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    })
    if price_basis is HistoricalReturnPriceBasis.ADJUSTED_CLOSE:
        selected.add(CalculationQualityFlag.ADJUSTED_INPUT_USED)
    selected.discard(CalculationQualityFlag.INCOMPLETE_INPUT_USED)
    return tuple(flag for flag in CalculationQualityFlag if flag in selected)


def transform_historical_realized_volatility(
    calculation_id: object,
    historical_series_assessment: object,
    price_basis: object,
    annualization_sessions_per_year: object,
    calculated_at: object,
) -> HistoricalRealizedVolatilityTransformationResult:
    """Transform one retained 3C.6 daily series into log-return volatility."""

    normalized_id = _validate_calculation_id(calculation_id)
    if type(price_basis) is not HistoricalReturnPriceBasis:
        raise TypeError(
            "price_basis must have exact type HistoricalReturnPriceBasis"
        )
    if type(annualization_sessions_per_year) is not int:
        raise TypeError(
            "annualization_sessions_per_year must have exact type int"
        )
    if annualization_sessions_per_year <= 0:
        raise ValueError(
            "annualization_sessions_per_year must be greater than zero"
        )
    normalized_at = _normalize_calculated_at(calculated_at)
    request, bindings, bars = _validate_historical_transformation_assessment(
        historical_series_assessment, price_basis
    )
    prices, methodology = _extract_historical_prices(bars, price_basis)
    log_returns, annualized_volatility = _calculate_historical_statistics(
        prices, annualization_sessions_per_year
    )
    record = HistoricalRealizedVolatility(
        underlying_key=request.underlying_key,
        start_session_date=request.expected_session_dates[0],
        end_session_date=request.expected_session_dates[-1],
        price_basis=price_basis,
        adjustment_methodology=methodology,
        session_dates=request.expected_session_dates,
        prices=prices,
        log_returns=log_returns,
        annualized_realized_volatility=annualized_volatility,
        annualization_sessions_per_year=annualization_sessions_per_year,
        return_formula=_HISTORICAL_RETURN_FORMULA,
        variance_estimator=_HISTORICAL_VARIANCE_ESTIMATOR,
    )
    inputs = _construct_input_references(bars)
    parameters_json = _construct_historical_parameters(record)
    quality_flags = _derive_historical_quality_flags(
        bindings, bars, price_basis
    )
    lineage = CalculationLineage(
        calculation_id=normalized_id,
        calculation_type="historical_realized_volatility",
        methodology_id=(
            "historical-log-return-sample-realized-volatility"
        ),
        methodology_version="v0.1",
        calculated_at=normalized_at,
        inputs=inputs,
        parameters_json=parameters_json,
        quality_flags=quality_flags,
    )
    return HistoricalRealizedVolatilityTransformationResult(
        record=record, lineage=lineage
    )


_VOLATILITY_GROUP_ROLES = {
    MarketDataRelationshipGroupKind
    .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1: (
        MarketDataRelationshipRole.UNDERLYING_QUOTE,
        MarketDataRelationshipRole.OPTION_QUOTE,
    ),
    MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1: (
        MarketDataRelationshipRole.OPTION_QUOTE,
        MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
    ),
    MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1: (
        MarketDataRelationshipRole.OPTION_QUOTE,
        MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
        MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
    ),
}
_VOLATILITY_RECORD_TYPE_BY_ROLE = {
    MarketDataRelationshipRole.UNDERLYING_QUOTE: UnderlyingQuoteObservation,
    MarketDataRelationshipRole.OPTION_QUOTE: OptionQuoteObservation,
    MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY: (
        OptionImpliedVolatilityObservation
    ),
    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE: (
        OptionContractReference
    ),
}


def _validate_volatility_metadata(record: object) -> None:
    metadata = record.metadata
    if type(metadata) is not NormalizationMetadata:
        raise TypeError("selected record metadata must have exact type NormalizationMetadata")
    if type(metadata.source_references) is not tuple:
        raise TypeError("source_references must have exact type tuple")
    if any(type(source) is not SourceReference for source in metadata.source_references):
        raise TypeError("every consumed source must have exact type SourceReference")
    if NormalizationQualityFlag.INCOMPLETE in metadata.quality_flags:
        raise ValueError("incomplete normalized input cannot be consumed")
    if any(
        SourceQualityFlag.PARTIAL in source.quality_flags
        for source in metadata.source_references
    ):
        raise ValueError("partial source input cannot be consumed")


def _volatility_pair_key(contract: OptionContractKey) -> tuple:
    return (
        contract.underlying_key,
        contract.expiration,
        contract.strike,
        contract.contract_multiplier,
        contract.currency,
        contract.deliverable_id,
    )


def _volatility_pair_order_key(pair: tuple) -> tuple:
    contract = pair[0].contract_key
    return (
        contract.expiration,
        contract.strike,
        contract.contract_multiplier,
        contract.currency,
        (0, "") if contract.deliverable_id is None
        else (1, contract.deliverable_id),
        pair[0].metadata.record_id,
        pair[1].metadata.record_id,
    )


def _validate_volatility_selection(
    value: object,
) -> tuple:
    selection = _validate_relationship_selection(value)
    _validate_selection_status(selection)
    selected = _resolve_selected_candidate(selection)
    if type(selected.request) is not MarketDataRelationshipRequest:
        raise TypeError("selected request must have exact type MarketDataRelationshipRequest")
    if type(selected.timing_assessment) is not MarketDataSnapshotTimingAssessment:
        raise TypeError(
            "selected timing assessment must have exact type "
            "MarketDataSnapshotTimingAssessment"
        )
    if not selected.is_coherent:
        raise ValueError("selected relationship assessment must remain coherent")
    if not selected.timing_assessment.is_temporally_coherent:
        raise ValueError("selected timing assessment must remain coherent")

    groups = selected.request.groups
    bindings = selected.timing_assessment.bindings
    if type(groups) is not tuple:
        raise TypeError("selected request groups must have exact type tuple")
    if type(bindings) is not tuple:
        raise TypeError("selected timing bindings must have exact type tuple")
    for group in groups:
        if type(group) is not MarketDataRelationshipGroup:
            raise TypeError("every selected group must have exact type MarketDataRelationshipGroup")
        if type(group.group_kind) is not MarketDataRelationshipGroupKind:
            raise TypeError("group_kind must have exact type MarketDataRelationshipGroupKind")
        if group.group_kind not in _VOLATILITY_GROUP_ROLES:
            raise ValueError("volatility selection contains an unsupported group kind")
        if type(group.members) is not tuple:
            raise TypeError("selected group members must have exact type tuple")
        for member in group.members:
            if type(member) is not MarketDataRelationshipGroupMember:
                raise TypeError(
                    "every selected member must have exact type "
                    "MarketDataRelationshipGroupMember"
                )
            if type(member.role) is not MarketDataRelationshipRole:
                raise TypeError("member role must have exact type MarketDataRelationshipRole")
            if type(member.reference) is not MarketDataBindingReference:
                raise TypeError(
                    "member reference must have exact type MarketDataBindingReference"
                )
        roles = tuple(member.role for member in group.members)
        expected_roles = _VOLATILITY_GROUP_ROLES[group.group_kind]
        if len(roles) != len(expected_roles) or set(roles) != set(expected_roles):
            raise ValueError("volatility relationship group has the wrong exact role shape")

    for binding in bindings:
        if type(binding) is not SelectedFreshMarketDataBinding:
            raise TypeError(
                "every selected binding must have exact type "
                "SelectedFreshMarketDataBinding"
            )
        if type(binding.correction_selection) is not CorrectionSelection:
            raise TypeError("correction_selection must have exact type CorrectionSelection")
        if type(binding.freshness_assessment) is not FreshnessAssessment:
            raise TypeError("freshness_assessment must have exact type FreshnessAssessment")
        if type(binding.freshness_policy) is not MarketDataFreshnessPolicy:
            raise TypeError("freshness_policy must have exact type MarketDataFreshnessPolicy")
        if type(binding.freshness_context) is not FreshnessContext:
            raise TypeError("freshness_context must have exact type FreshnessContext")

    entries = _resolve_selected_objects(groups, bindings)
    for _group, member, _binding, record in entries:
        expected_type = _VOLATILITY_RECORD_TYPE_BY_ROLE.get(member.role)
        if expected_type is None:
            raise ValueError("volatility selection contains an unsupported role")
        if type(record) is not expected_type:
            raise TypeError(
                f"{member.role.value} selected record must have exact type "
                f"{expected_type.__name__}"
            )

    entry_by_binding = {}
    for entry in entries:
        entry_by_binding.setdefault(id(entry[2]), entry)
    if set(entry_by_binding) != {id(binding) for binding in bindings}:
        raise ValueError("every selected binding must be referenced")
    for _group, member, binding, record in entry_by_binding.values():
        _validate_candidate_universe(
            binding, binding.correction_selection, record
        )
        _validate_correction_proof(binding, binding.correction_selection)
        _validate_freshness_proof(member.role, binding, record)
        _validate_semantic_proof(member, binding, record)
        _validate_volatility_metadata(record)
    selected_ids = tuple(
        entry[3].metadata.record_id for entry in entry_by_binding.values()
    )
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("selected normalized record IDs must be unique")

    group_counts = {
        kind: sum(group.group_kind is kind for group in groups)
        for kind in _VOLATILITY_GROUP_ROLES
    }
    candidate_count = group_counts[
        MarketDataRelationshipGroupKind
        .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
    ]
    if candidate_count < 1 or any(
        count != candidate_count for count in group_counts.values()
    ):
        raise ValueError("selection must contain exactly three groups per candidate")
    if len(groups) != 3 * candidate_count or len(bindings) != 1 + 3 * candidate_count:
        raise ValueError("selection has the wrong exact group or binding count")

    def group_records(group: MarketDataRelationshipGroup) -> dict:
        matched = tuple(entry for entry in entries if entry[0] is group)
        if len(matched) != len(group.members):
            raise ValueError("group members must resolve exactly once")
        return {entry[1].role: entry[3] for entry in matched}

    by_kind_and_contract = {}
    underlying_objects = []
    reference_counts = {}
    for group in groups:
        records = group_records(group)
        quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        if type(quote.contract_key) is not OptionContractKey:
            raise TypeError("option quote must retain an exact OptionContractKey")
        contract = quote.contract_key
        if group.group_kind is (
            MarketDataRelationshipGroupKind
            .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
        ):
            underlying_objects.append(
                records[MarketDataRelationshipRole.UNDERLYING_QUOTE]
            )
        if group.group_kind is not (
            MarketDataRelationshipGroupKind
            .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
        ):
            iv = records[MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY]
            if type(iv.contract_key) is not OptionContractKey:
                raise TypeError("IV record must retain an exact OptionContractKey")
            if iv.contract_key != contract:
                raise ValueError("quote and IV records must share one contract key")
        if group.group_kind is (
            MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1
        ):
            reference = records[
                MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
            ]
            if type(reference.contract_key) is not OptionContractKey:
                raise TypeError(
                    "contract reference must retain an exact OptionContractKey"
                )
            if reference.contract_key != contract:
                raise ValueError(
                    "quote, IV, and contract reference must share one contract key"
                )
        key = (group.group_kind, contract)
        if key in by_kind_and_contract:
            raise ValueError("relationship groups must cover each contract exactly once")
        by_kind_and_contract[key] = records
        for record in records.values():
            reference_counts[id(record)] = reference_counts.get(id(record), 0) + 1

    contracts = {
        contract for kind, contract in by_kind_and_contract
        if kind is MarketDataRelationshipGroupKind
        .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
    }
    if len(contracts) != candidate_count or any(
        (kind, contract) not in by_kind_and_contract
        for contract in contracts for kind in _VOLATILITY_GROUP_ROLES
    ):
        raise ValueError("each candidate contract must have the exact three-group proof")
    if len({id(record) for record in underlying_objects}) != 1:
        raise ValueError("selection must contain one shared underlying quote")
    underlying = underlying_objects[0]
    if reference_counts.get(id(underlying)) != candidate_count:
        raise ValueError("shared underlying quote has the wrong reference count")

    candidates = []
    for contract in contracts:
        snapshot = by_kind_and_contract[(
            MarketDataRelationshipGroupKind
            .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1,
            contract,
        )]
        analytics = by_kind_and_contract[(
            MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
            contract,
        )]
        reference_group = by_kind_and_contract[(
            MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1,
            contract,
        )]
        quote = snapshot[MarketDataRelationshipRole.OPTION_QUOTE]
        iv = analytics[MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY]
        reference = reference_group[
            MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
        ]
        if (
            analytics[MarketDataRelationshipRole.OPTION_QUOTE] is not quote
            or reference_group[MarketDataRelationshipRole.OPTION_QUOTE] is not quote
            or reference_group[
                MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY
            ] is not iv
        ):
            raise ValueError("required repeated references must retain exact identities")
        if (
            reference_counts.get(id(quote)) != 3
            or reference_counts.get(id(iv)) != 2
            or reference_counts.get(id(reference)) != 1
        ):
            raise ValueError("candidate records have the wrong repeated-reference counts")
        candidates.append((quote, iv, reference))

    if len({item[0].contract_key.underlying_key for item in candidates}) != 1:
        raise ValueError("selection must contain one common underlying identity")
    underlying_key = candidates[0][0].contract_key.underlying_key
    if underlying.underlying_key != underlying_key:
        raise ValueError("underlying quote and option candidates must agree")
    session_dates = {underlying.session_date}
    for quote, iv, _reference in candidates:
        if quote.contract_key != iv.contract_key:
            raise ValueError("quote and IV contract identities must agree")
        if quote.session_date != iv.session_date:
            raise ValueError("quote and IV must share one session date")
        session_dates.add(quote.session_date)
        if quote.contract_key.expiration <= quote.session_date:
            raise ValueError("option expiration must follow the session date")
    if len(session_dates) != 1:
        raise ValueError("selection must contain one common session date")
    session_date = next(iter(session_dates))

    paired = {}
    for candidate in candidates:
        paired.setdefault(_volatility_pair_key(candidate[0].contract_key), []).append(candidate)
    exact_pairs = []
    for values in paired.values():
        calls = tuple(
            item for item in values if item[0].contract_key.option_type == "call"
        )
        puts = tuple(
            item for item in values if item[0].contract_key.option_type == "put"
        )
        if len(calls) != 1 or len(puts) != 1 or len(values) != 2:
            raise ValueError("every candidate pair must contain exactly one call and one put")
        exact_pairs.append((calls[0], puts[0]))
    exact_pairs = tuple(sorted(exact_pairs, key=lambda pair: _volatility_pair_order_key((
        pair[0][0], pair[1][0]
    ))))
    return (
        selection,
        underlying,
        underlying_key,
        session_date,
        exact_pairs,
        tuple(entry[2] for entry in entry_by_binding.values()),
        tuple(entry[3] for entry in entry_by_binding.values()),
    )


def _exact_midpoint(first: decimal.Decimal, second: decimal.Decimal) -> decimal.Decimal:
    return _exact_half(_exact_scaled_sum(((first, 1), (second, 1))))


def _exact_distance(first: decimal.Decimal, second: decimal.Decimal) -> decimal.Decimal:
    difference = _exact_scaled_sum(((first, 1), (second.copy_negate(), 1)))
    return difference.copy_abs()


def _exact_two_value_mean(
    first: decimal.Decimal, second: decimal.Decimal
) -> decimal.Decimal:
    return _exact_half(_exact_scaled_sum(((first, 1), (second, 1))))


def _finite_float(value: decimal.Decimal) -> float:
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("Decimal value must convert to a finite float") from error
    if not math.isfinite(converted):
        raise ValueError("Decimal value must convert to a finite float")
    return converted


def _volatility_observations(
    underlying: UnderlyingQuoteObservation,
    session_date: datetime.date,
    pairs: tuple,
) -> tuple:
    if (
        type(underlying.bid_price) is not decimal.Decimal
        or type(underlying.ask_price) is not decimal.Decimal
        or not underlying.bid_price.is_finite()
        or not underlying.ask_price.is_finite()
        or underlying.bid_price <= 0
        or underlying.ask_price <= 0
    ):
        raise ValueError("underlying bid and ask must be finite and positive")
    midpoint = _exact_midpoint(underlying.bid_price, underlying.ask_price)
    by_expiration = {}
    methodologies = []
    for call_item, put_item in pairs:
        call_quote, call_iv, call_reference = call_item
        put_quote, put_iv, put_reference = put_item
        for iv in (call_iv, put_iv):
            if (
                type(iv.implied_volatility) is not decimal.Decimal
                or not iv.implied_volatility.is_finite()
                or iv.implied_volatility <= 0
            ):
                raise ValueError("every implied volatility must be finite and positive")
            methodologies.append((
                iv.model_name,
                iv.model_version,
                iv.rate_input_description,
                iv.dividend_input_description,
                iv.metadata.unit_convention,
            ))
        paired_iv = _exact_two_value_mean(
            call_iv.implied_volatility, put_iv.implied_volatility
        )
        distance = _exact_distance(call_quote.contract_key.strike, midpoint)
        candidate = {
            "strike": call_quote.contract_key.strike,
            "contract_multiplier": call_quote.contract_key.contract_multiplier,
            "currency": call_quote.contract_key.currency,
            "deliverable_id": call_quote.contract_key.deliverable_id,
            "call_quote_record_id": call_quote.metadata.record_id,
            "call_iv_record_id": call_iv.metadata.record_id,
            "call_contract_reference_record_id": call_reference.metadata.record_id,
            "put_quote_record_id": put_quote.metadata.record_id,
            "put_iv_record_id": put_iv.metadata.record_id,
            "put_contract_reference_record_id": put_reference.metadata.record_id,
            "call_implied_volatility": call_iv.implied_volatility,
            "put_implied_volatility": put_iv.implied_volatility,
            "paired_implied_volatility": paired_iv,
            "distance_to_underlying_midpoint": distance,
        }
        by_expiration.setdefault(call_quote.contract_key.expiration, []).append(candidate)
    if not methodologies or any(item != methodologies[0] for item in methodologies[1:]):
        raise ValueError("all IV inputs must share one exact methodology")
    if methodologies[0][4] != "annualized_decimal_ratio":
        raise ValueError("IV inputs must use annualized_decimal_ratio")

    observations = []
    for expiration in sorted(by_expiration):
        candidates = tuple(sorted(
            by_expiration[expiration],
            key=lambda item: (
                item["strike"],
                item["contract_multiplier"],
                item["currency"],
                (0, "") if item["deliverable_id"] is None
                else (1, item["deliverable_id"]),
                item["call_iv_record_id"],
                item["put_iv_record_id"],
            ),
        ))
        minimum_distance = min(
            item["distance_to_underlying_midpoint"]
            for item in candidates
        )
        distance_candidates = tuple(
            item for item in candidates
            if item["distance_to_underlying_midpoint"] == minimum_distance
        )
        selected_strike = min(
            item["strike"] for item in distance_candidates
        )
        final_candidates = tuple(
            item for item in distance_candidates
            if item["strike"] == selected_strike
        )
        if len(final_candidates) != 1:
            raise ValueError(
                "ATM candidate selection remains ambiguous at the "
                "selected strike"
            )
        selected = final_candidates[0]
        tenor_days = (expiration - session_date).days
        if tenor_days <= 0:
            raise ValueError("every expiration tenor must be positive")
        observations.append({
            "session_date": session_date,
            "expiration": expiration,
            "tenor_days": tenor_days,
            "underlying_quote_record_id": underlying.metadata.record_id,
            "underlying_midpoint": midpoint,
            "candidate_pairs": candidates,
            "selected_strike": selected["strike"],
            "selected_call_iv_record_id": selected["call_iv_record_id"],
            "selected_put_iv_record_id": selected["put_iv_record_id"],
            "selected_atm_iv": selected["paired_implied_volatility"],
        })
    return tuple(observations), methodologies[0]


def _validate_realized_dependency(
    value: object,
    calculation_id: str,
    calculated_at: datetime.datetime,
) -> tuple:
    if type(value) is not HistoricalRealizedVolatilityTransformationResult:
        raise TypeError(
            "historical_realized_volatility_result must have exact type "
            "HistoricalRealizedVolatilityTransformationResult"
        )
    record = value.record
    lineage = value.lineage
    if type(record) is not HistoricalRealizedVolatility:
        raise TypeError("realized record must have exact type HistoricalRealizedVolatility")
    if type(lineage) is not CalculationLineage:
        raise TypeError("realized lineage must have exact type CalculationLineage")
    if (
        lineage.calculation_type != "historical_realized_volatility"
        or lineage.methodology_id
        != "historical-log-return-sample-realized-volatility"
        or lineage.methodology_version != "v0.1"
    ):
        raise ValueError("realized lineage calculation identity is invalid")
    if lineage.parameters_json != _construct_historical_parameters(record):
        raise ValueError("realized lineage parameters do not match its record")
    if len(lineage.inputs) != record.price_observation_count:
        raise ValueError("realized lineage input count does not match its record")
    flags = lineage.quality_flags
    required = {
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    if not required.issubset(flags):
        raise ValueError("realized lineage is missing mandatory quality flags")
    permitted = required | {
        CalculationQualityFlag.ADJUSTED_INPUT_USED,
        CalculationQualityFlag.CORRECTION_SELECTED,
        CalculationQualityFlag.COMPOSITE_INPUT_USED,
        CalculationQualityFlag.INTERPOLATED,
    }
    if any(flag not in permitted for flag in flags):
        raise ValueError("realized lineage contains a prohibited quality flag")
    adjusted = record.price_basis is HistoricalReturnPriceBasis.ADJUSTED_CLOSE
    if (
        (CalculationQualityFlag.ADJUSTED_INPUT_USED in flags) != adjusted
        or CalculationQualityFlag.INCOMPLETE_INPUT_USED in flags
    ):
        raise ValueError("realized lineage quality flags are inconsistent")
    if calculation_id == lineage.calculation_id:
        raise ValueError("new and prior calculation IDs must differ")
    if calculated_at < lineage.calculated_at:
        raise ValueError("new calculation must not precede the prior calculation")
    return record, lineage


def _percentile(count: int, total: int) -> decimal.Decimal:
    try:
        with decimal.localcontext() as context:
            context.prec = 34
            context.rounding = decimal.ROUND_HALF_EVEN
            context.Emax = decimal.MAX_EMAX
            context.Emin = decimal.MIN_EMIN
            context.clamp = 0
            context.traps[decimal.InvalidOperation] = True
            context.traps[decimal.DivisionByZero] = True
            context.traps[decimal.Overflow] = True
            return context.divide(decimal.Decimal(count), decimal.Decimal(total))
    except decimal.DecimalException as error:
        raise ValueError("IV percentile calculation failed") from error


def _median(values: tuple) -> decimal.Decimal:
    ordered = tuple(sorted(values))
    if not ordered:
        raise ValueError("historical IV sample must not be empty")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return _exact_two_value_mean(ordered[middle - 1], ordered[middle])


def _realized_dependency_parameters(
    record: HistoricalRealizedVolatility,
    lineage: CalculationLineage,
) -> dict:
    return {
        "calculation_id": lineage.calculation_id,
        "calculation_type": lineage.calculation_type,
        "methodology_id": lineage.methodology_id,
        "methodology_version": lineage.methodology_version,
        "calculated_at": lineage.calculated_at,
        "parameters_json": lineage.parameters_json,
        "quality_flags": tuple(flag.value for flag in lineage.quality_flags),
        "inputs": tuple(
            _complete_input_reference(item) for item in lineage.inputs
        ),
        "underlying": {
            "symbol": record.underlying_key.symbol,
            "listing_mic": record.underlying_key.listing_mic,
            "security_type": record.underlying_key.security_type.value,
            "currency": record.underlying_key.currency,
        },
        "start_session_date": record.start_session_date,
        "end_session_date": record.end_session_date,
        "session_dates": record.session_dates,
        "price_basis": record.price_basis.value,
        "adjustment_methodology": record.adjustment_methodology,
        "prices": record.prices,
        "log_returns": record.log_returns,
        "annualization_sessions_per_year": record.annualization_sessions_per_year,
        "return_formula": record.return_formula,
        "variance_estimator": record.variance_estimator,
        "price_observation_count": record.price_observation_count,
        "return_observation_count": record.return_observation_count,
        "annualized_realized_volatility_float_repr": repr(
            record.annualized_realized_volatility
        ),
    }


def transform_volatility_environment(
    calculation_id: object,
    current_relationship_selection: object,
    historical_relationship_selections: object,
    historical_expected_session_dates: object,
    historical_realized_volatility_result: object,
    reference_tenor_days: object,
    atm_candidate_universes_complete: object,
    calculated_at: object,
) -> VolatilityEnvironmentTransformationResult:
    """Construct one paired-ATM volatility environment from reviewed inputs."""

    normalized_id = _validate_calculation_id(calculation_id)
    if type(historical_relationship_selections) is not tuple:
        raise TypeError("historical_relationship_selections must have exact type tuple")
    if not historical_relationship_selections:
        raise ValueError("historical_relationship_selections must not be empty")
    if any(
        type(item) is not MarketDataRelationshipSelection
        for item in historical_relationship_selections
    ):
        raise TypeError(
            "every historical selection must have exact type "
            "MarketDataRelationshipSelection"
        )
    if type(historical_expected_session_dates) is not tuple:
        raise TypeError("historical_expected_session_dates must have exact type tuple")
    if not historical_expected_session_dates:
        raise ValueError("historical_expected_session_dates must not be empty")
    if any(
        type(item) is not datetime.date
        for item in historical_expected_session_dates
    ):
        raise TypeError("every historical date must have exact type date")
    if any(
        current <= previous for previous, current in zip(
            historical_expected_session_dates,
            historical_expected_session_dates[1:],
        )
    ):
        raise ValueError("historical dates must be strictly ascending")
    if type(reference_tenor_days) is not int:
        raise TypeError("reference_tenor_days must have exact built-in type int")
    if reference_tenor_days <= 0:
        raise ValueError("reference_tenor_days must be positive")
    if type(atm_candidate_universes_complete) is not bool:
        raise TypeError("atm_candidate_universes_complete must have exact type bool")
    if not atm_candidate_universes_complete:
        raise ValueError("ATM candidate universes must be declared complete")
    normalized_at = _normalize_calculated_at(calculated_at)

    current = _validate_volatility_selection(current_relationship_selection)
    current_observations, iv_methodology = _volatility_observations(
        current[1], current[3], current[4]
    )
    if len(current_observations) < 2:
        raise ValueError("current selection must contain at least two expirations")
    current_tenors = tuple(item["tenor_days"] for item in current_observations)
    if len(set(current_tenors)) != len(current_tenors):
        raise ValueError("current term tenors must be unique")
    reference_matches = tuple(
        item for item in current_observations
        if item["tenor_days"] == reference_tenor_days
    )
    if len(reference_matches) != 1:
        raise ValueError("reference tenor must match exactly one current term point")
    current_reference_iv = reference_matches[0]["selected_atm_iv"]

    historical = tuple(
        _validate_volatility_selection(selection)
        for selection in historical_relationship_selections
    )
    derived_dates = tuple(sorted(item[3] for item in historical))
    if len(set(derived_dates)) != len(derived_dates):
        raise ValueError("historical selections must have unique session dates")
    if derived_dates != historical_expected_session_dates:
        raise ValueError("historical selections must exactly match expected dates")
    if any(date >= current[3] for date in derived_dates):
        raise ValueError("every historical date must precede the current date")
    historical_by_date = {item[3]: item for item in historical}
    historical_observations = []
    historical_values = []
    for session_date in derived_dates:
        item = historical_by_date[session_date]
        observations, methodology = _volatility_observations(
            item[1], item[3], item[4]
        )
        if len(observations) != 1:
            raise ValueError("each historical selection must have one expiration")
        observation = observations[0]
        if observation["tenor_days"] != reference_tenor_days:
            raise ValueError("historical expiration must exactly match reference tenor")
        if methodology != iv_methodology:
            raise ValueError("historical and current IV methodologies must match")
        historical_observations.append(observation)
        historical_values.append(observation["selected_atm_iv"])
    historical_values_tuple = tuple(historical_values)

    all_underlyings = (current[2],) + tuple(item[2] for item in historical)
    if any(item != current[2] for item in all_underlyings[1:]):
        raise ValueError("all IV selections must share one underlying identity")
    realized_record, realized_lineage = _validate_realized_dependency(
        historical_realized_volatility_result, normalized_id, normalized_at
    )
    if realized_record.underlying_key != current[2]:
        raise ValueError("realized and implied volatility underlyings must match")
    if realized_record.end_session_date != current[3]:
        raise ValueError("realized window must end on the current as-of date")
    realized_span = (
        realized_record.end_session_date - realized_record.start_session_date
    ).days
    if realized_span != reference_tenor_days:
        raise ValueError("realized calendar span must equal reference tenor")

    percentile_decimal = _percentile(
        sum(value <= current_reference_iv for value in historical_values_tuple),
        len(historical_values_tuple),
    )
    median_decimal = _median(historical_values_tuple)
    term_structure = tuple(
        TermVolatilityPoint(
            tenor_days=item["tenor_days"],
            atm_iv=_finite_float(item["selected_atm_iv"]),
        )
        for item in current_observations
    )
    record = VolatilityEnvironment(
        underlying=current[2].symbol,
        as_of_date=current[3],
        reference_tenor_days=reference_tenor_days,
        iv_percentile=_finite_float(percentile_decimal),
        iv_history_lookback_observations=len(historical_values_tuple),
        historical_median_atm_iv=_finite_float(median_decimal),
        matched_realized_volatility=realized_record.annualized_realized_volatility,
        matched_realized_window_days=realized_span,
        term_structure=term_structure,
    )

    iv_records = current[6] + tuple(
        selected_record for item in historical for selected_record in item[6]
    )
    all_bindings = current[5] + tuple(
        binding for item in historical for binding in item[5]
    )
    parameters_json = canonicalize_lineage_parameters({
        "atm_candidate_universe": {
            "declared_complete": True,
            "scope": "all_exact_selected_session_expiration_universes",
            "completeness_semantics": (
                "no_eligible_paired_call_put_strike_omitted"
            ),
        },
        "atm_selection_rule": (
            "nearest_paired_call_put_strike_to_underlying_bid_ask_midpoint"
        ),
        "call_put_combination_rule": (
            "arithmetic_mean_of_same_strike_call_and_put_implied_volatility"
        ),
        "current_observations": current_observations,
        "float_conversion_rule": (
            "convert_only_final_decimal_research_values_to_finite_float"
        ),
        "historical_expected_session_dates": historical_expected_session_dates,
        "historical_matched_tenor_rule": (
            "expiration_minus_session_date_calendar_days_equals_reference_tenor"
        ),
        "historical_observation_count": len(historical_values_tuple),
        "historical_observations": tuple(historical_observations),
        "historical_sample_semantics": "caller_declared_observation_sample",
        "iv_methodology": {
            "model_name": iv_methodology[0],
            "model_version": iv_methodology[1],
            "rate_input_description": iv_methodology[2],
            "dividend_input_description": iv_methodology[3],
            "unit_convention": iv_methodology[4],
        },
        "median_formula": (
            "odd_middle_even_arithmetic_mean_of_two_middle_values"
        ),
        "normalized_evidence": {
            "direct_inputs": _direct_normalized_evidence(
                iv_records, all_bindings
            ),
        },
        "percentile_formula": (
            "inclusive_count_historical_atm_iv_lte_current_reference_atm_iv_"
            "divided_by_count"
        ),
        "realized_volatility_dependency": _realized_dependency_parameters(
            realized_record, realized_lineage
        ),
        "realized_window_matching_rule": (
            "realized_end_equals_current_as_of_and_calendar_span_equals_"
            "reference_tenor"
        ),
        "reference_tenor_days": reference_tenor_days,
        "strike_tie_rule": "lower_strike",
        "term_tenor_rule": "expiration_minus_session_date_calendar_days",
        "underlying_midpoint_rule": "bid_ask_midpoint_no_last_fallback",
        "volatility_unit": "annualized_decimal_ratio",
    })

    inputs = _union_lineage_inputs(realized_lineage.inputs, iv_records)
    input_ids = tuple(item.record_id for item in inputs)
    if len(set(input_ids)) != len(input_ids):
        raise ValueError("normalized input record IDs must be globally unique")
    flags = {
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    propagated = {
        CalculationQualityFlag.ADJUSTED_INPUT_USED,
        CalculationQualityFlag.CORRECTION_SELECTED,
        CalculationQualityFlag.COMPOSITE_INPUT_USED,
        CalculationQualityFlag.INTERPOLATED,
    }
    flags.update(flag for flag in realized_lineage.quality_flags if flag in propagated)
    if any(
        binding.correction_selection.reason_codes == (
            CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,
        )
        for binding in all_bindings
    ):
        flags.add(CalculationQualityFlag.CORRECTION_SELECTED)
    if any(
        record.metadata.record_origin is DataOrigin.SYSTEM_COMPOSITE
        for record in iv_records
    ):
        flags.add(CalculationQualityFlag.COMPOSITE_INPUT_USED)
    if any(
        NormalizationQualityFlag.INTERPOLATED in record.metadata.quality_flags
        for record in iv_records
    ):
        flags.add(CalculationQualityFlag.INTERPOLATED)
    flags.discard(CalculationQualityFlag.INCOMPLETE_INPUT_USED)
    lineage = CalculationLineage(
        calculation_id=normalized_id,
        calculation_type="volatility_environment",
        methodology_id="paired-atm-volatility-environment",
        methodology_version="v0.2",
        calculated_at=normalized_at,
        inputs=inputs,
        parameters_json=parameters_json,
        quality_flags=tuple(
            flag for flag in CalculationQualityFlag if flag in flags
        ),
    )
    return VolatilityEnvironmentTransformationResult(
        record=record, lineage=lineage
    )


_TAIL_GROUP_ROLES = {
    MarketDataRelationshipGroupKind
    .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1: (
        MarketDataRelationshipRole.UNDERLYING_QUOTE,
        MarketDataRelationshipRole.OPTION_QUOTE,
    ),
    MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1: (
        MarketDataRelationshipRole.OPTION_QUOTE,
        MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
        MarketDataRelationshipRole.OPTION_GREEKS,
    ),
    MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1: (
        MarketDataRelationshipRole.OPTION_QUOTE,
        MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
        MarketDataRelationshipRole.OPTION_GREEKS,
        MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
    ),
}
_TAIL_RECORD_TYPE_BY_ROLE = {
    MarketDataRelationshipRole.UNDERLYING_QUOTE: UnderlyingQuoteObservation,
    MarketDataRelationshipRole.OPTION_QUOTE: OptionQuoteObservation,
    MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY: (
        OptionImpliedVolatilityObservation
    ),
    MarketDataRelationshipRole.OPTION_GREEKS: OptionGreeksObservation,
    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE: (
        OptionContractReference
    ),
}
_TAIL_TARGETS = {
    "call_25": decimal.Decimal("0.25"),
    "call_10": decimal.Decimal("0.10"),
    "put_25": decimal.Decimal("-0.25"),
    "put_10": decimal.Decimal("-0.10"),
}
_VOLATILITY_PARAMETER_KEYS = (
    "atm_candidate_universe",
    "atm_selection_rule",
    "call_put_combination_rule",
    "current_observations",
    "float_conversion_rule",
    "historical_expected_session_dates",
    "historical_matched_tenor_rule",
    "historical_observation_count",
    "historical_observations",
    "historical_sample_semantics",
    "iv_methodology",
    "median_formula",
    "normalized_evidence",
    "percentile_formula",
    "realized_volatility_dependency",
    "realized_window_matching_rule",
    "reference_tenor_days",
    "strike_tie_rule",
    "term_tenor_rule",
    "underlying_midpoint_rule",
    "volatility_unit",
)


def _tail_contract_order_key(contract: OptionContractKey) -> tuple:
    return (
        contract.expiration,
        contract.option_type,
        contract.strike,
        contract.contract_multiplier,
        contract.currency,
        (0, "") if contract.deliverable_id is None
        else (1, contract.deliverable_id),
    )


def _validate_tail_selection(value: object) -> dict:
    selection = _validate_relationship_selection(value)
    _validate_selection_status(selection)
    selected = _resolve_selected_candidate(selection)
    if type(selected.request) is not MarketDataRelationshipRequest:
        raise TypeError(
            "selected request must have exact type MarketDataRelationshipRequest"
        )
    if type(selected.timing_assessment) is not MarketDataSnapshotTimingAssessment:
        raise TypeError(
            "selected timing assessment must have exact type "
            "MarketDataSnapshotTimingAssessment"
        )
    if not selected.is_coherent:
        raise ValueError("selected relationship assessment must remain coherent")
    if not selected.timing_assessment.is_temporally_coherent:
        raise ValueError("selected timing assessment must remain coherent")

    groups = selected.request.groups
    bindings = selected.timing_assessment.bindings
    if type(groups) is not tuple:
        raise TypeError("selected request groups must have exact type tuple")
    if type(bindings) is not tuple:
        raise TypeError("selected timing bindings must have exact type tuple")
    for group in groups:
        if type(group) is not MarketDataRelationshipGroup:
            raise TypeError(
                "every selected group must have exact type "
                "MarketDataRelationshipGroup"
            )
        if type(group.group_kind) is not MarketDataRelationshipGroupKind:
            raise TypeError(
                "group_kind must have exact type MarketDataRelationshipGroupKind"
            )
        if group.group_kind not in _TAIL_GROUP_ROLES:
            raise ValueError("tail selection contains an unsupported group kind")
        if type(group.members) is not tuple:
            raise TypeError("selected group members must have exact type tuple")
        for member in group.members:
            if type(member) is not MarketDataRelationshipGroupMember:
                raise TypeError(
                    "every selected member must have exact type "
                    "MarketDataRelationshipGroupMember"
                )
            if type(member.role) is not MarketDataRelationshipRole:
                raise TypeError(
                    "member role must have exact type MarketDataRelationshipRole"
                )
            if type(member.reference) is not MarketDataBindingReference:
                raise TypeError(
                    "member reference must have exact type "
                    "MarketDataBindingReference"
                )
        roles = tuple(member.role for member in group.members)
        expected_roles = _TAIL_GROUP_ROLES[group.group_kind]
        if len(roles) != len(expected_roles) or set(roles) != set(expected_roles):
            raise ValueError(
                "tail relationship group has the wrong exact role shape"
            )
    for binding in bindings:
        if type(binding) is not SelectedFreshMarketDataBinding:
            raise TypeError(
                "every selected binding must have exact type "
                "SelectedFreshMarketDataBinding"
            )
        if type(binding.correction_selection) is not CorrectionSelection:
            raise TypeError(
                "correction_selection must have exact type CorrectionSelection"
            )
        if type(binding.freshness_assessment) is not FreshnessAssessment:
            raise TypeError(
                "freshness_assessment must have exact type FreshnessAssessment"
            )
        if type(binding.freshness_policy) is not MarketDataFreshnessPolicy:
            raise TypeError(
                "freshness_policy must have exact type MarketDataFreshnessPolicy"
            )
        if type(binding.freshness_context) is not FreshnessContext:
            raise TypeError(
                "freshness_context must have exact type FreshnessContext"
            )

    entries = _resolve_selected_objects(groups, bindings)
    for _group, member, _binding, record in entries:
        expected_type = _TAIL_RECORD_TYPE_BY_ROLE.get(member.role)
        if expected_type is None:
            raise ValueError("tail selection contains an unsupported role")
        if type(record) is not expected_type:
            raise TypeError(
                f"{member.role.value} selected record must have exact type "
                f"{expected_type.__name__}"
            )

    entry_by_binding = {}
    for entry in entries:
        entry_by_binding.setdefault(id(entry[2]), entry)
    if set(entry_by_binding) != {id(binding) for binding in bindings}:
        raise ValueError("every selected binding must be referenced")
    for _group, member, binding, record in entry_by_binding.values():
        _validate_candidate_universe(
            binding, binding.correction_selection, record
        )
        _validate_correction_proof(binding, binding.correction_selection)
        _validate_freshness_proof(member.role, binding, record)
        _validate_semantic_proof(member, binding, record)
        _validate_volatility_metadata(record)
    selected_ids = tuple(
        entry[3].metadata.record_id for entry in entry_by_binding.values()
    )
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("selected normalized record IDs must be unique")

    group_counts = {
        kind: sum(group.group_kind is kind for group in groups)
        for kind in _TAIL_GROUP_ROLES
    }
    candidate_count = group_counts[
        MarketDataRelationshipGroupKind
        .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
    ]
    if candidate_count < 1 or any(
        count != candidate_count for count in group_counts.values()
    ):
        raise ValueError(
            "selection must contain exactly three groups per tail candidate"
        )
    if (
        len(groups) != 3 * candidate_count
        or len(bindings) != 1 + 4 * candidate_count
    ):
        raise ValueError("selection has the wrong exact group or binding count")

    def group_records(group: MarketDataRelationshipGroup) -> dict:
        matched = tuple(entry for entry in entries if entry[0] is group)
        if len(matched) != len(group.members):
            raise ValueError("group members must resolve exactly once")
        return {entry[1].role: entry[3] for entry in matched}

    by_kind_and_contract = {}
    underlying_objects = []
    reference_counts = {}
    for group in groups:
        records = group_records(group)
        quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        if type(quote.contract_key) is not OptionContractKey:
            raise TypeError("option quote must retain an exact OptionContractKey")
        contract = quote.contract_key
        if group.group_kind is (
            MarketDataRelationshipGroupKind
            .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
        ):
            underlying_objects.append(
                records[MarketDataRelationshipRole.UNDERLYING_QUOTE]
            )
        for role in (
            MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
            MarketDataRelationshipRole.OPTION_GREEKS,
            MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
        ):
            record = records.get(role)
            if record is not None:
                if type(record.contract_key) is not OptionContractKey:
                    raise TypeError(
                        "tail record must retain an exact OptionContractKey"
                    )
                if record.contract_key != contract:
                    raise ValueError(
                        "all candidate records must share one contract key"
                    )
        key = (group.group_kind, contract)
        if key in by_kind_and_contract:
            raise ValueError(
                "relationship groups must cover each contract exactly once"
            )
        by_kind_and_contract[key] = records
        for record in records.values():
            reference_counts[id(record)] = (
                reference_counts.get(id(record), 0) + 1
            )

    contracts = {
        contract
        for kind, contract in by_kind_and_contract
        if kind is MarketDataRelationshipGroupKind
        .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
    }
    if len(contracts) != candidate_count or any(
        (kind, contract) not in by_kind_and_contract
        for contract in contracts
        for kind in _TAIL_GROUP_ROLES
    ):
        raise ValueError(
            "each tail candidate must have the exact three-group proof"
        )
    if len({id(record) for record in underlying_objects}) != 1:
        raise ValueError("selection must contain one shared underlying quote")
    underlying = underlying_objects[0]
    if reference_counts.get(id(underlying)) != candidate_count:
        raise ValueError("shared underlying quote has the wrong reference count")

    candidates = []
    for contract in sorted(contracts, key=_tail_contract_order_key):
        snapshot = by_kind_and_contract[(
            MarketDataRelationshipGroupKind
            .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1,
            contract,
        )]
        analytics = by_kind_and_contract[(
            MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
            contract,
        )]
        reference_group = by_kind_and_contract[(
            MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1,
            contract,
        )]
        quote = snapshot[MarketDataRelationshipRole.OPTION_QUOTE]
        iv = analytics[MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY]
        greeks = analytics[MarketDataRelationshipRole.OPTION_GREEKS]
        reference = reference_group[
            MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
        ]
        if (
            analytics[MarketDataRelationshipRole.OPTION_QUOTE] is not quote
            or reference_group[
                MarketDataRelationshipRole.OPTION_QUOTE
            ] is not quote
            or reference_group[
                MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY
            ] is not iv
            or reference_group[
                MarketDataRelationshipRole.OPTION_GREEKS
            ] is not greeks
        ):
            raise ValueError(
                "required repeated references must retain exact identities"
            )
        if (
            reference_counts.get(id(quote)) != 3
            or reference_counts.get(id(iv)) != 2
            or reference_counts.get(id(greeks)) != 2
            or reference_counts.get(id(reference)) != 1
        ):
            raise ValueError(
                "tail candidate records have wrong repeated-reference counts"
            )
        candidates.append((quote, iv, greeks, reference))

    if len({item[0].contract_key.underlying_key for item in candidates}) != 1:
        raise ValueError("selection must contain one common underlying identity")
    underlying_key = candidates[0][0].contract_key.underlying_key
    if underlying.underlying_key != underlying_key:
        raise ValueError("underlying quote and option candidates must agree")
    session_dates = {underlying.session_date}
    for quote, iv, greeks, _reference in candidates:
        if not (
            quote.contract_key == iv.contract_key
            == greeks.contract_key
        ):
            raise ValueError("candidate contract identities must agree")
        if not quote.session_date == iv.session_date == greeks.session_date:
            raise ValueError("candidate records must share one session date")
        session_dates.add(quote.session_date)
        if quote.contract_key.expiration <= quote.session_date:
            raise ValueError("option expiration must follow the session date")
        if (
            iv.model_name != greeks.model_name
            or iv.model_version != greeks.model_version
            or iv.rate_input_description != greeks.rate_input_description
            or iv.dividend_input_description
            != greeks.dividend_input_description
        ):
            raise ValueError("IV and Greeks methodologies must agree")
        if (
            type(iv.implied_volatility) is not decimal.Decimal
            or not iv.implied_volatility.is_finite()
            or iv.implied_volatility <= 0
        ):
            raise ValueError("every implied volatility must be finite and positive")
        delta = greeks.delta
        if type(delta) is not decimal.Decimal:
            if delta is None:
                raise ValueError("every tail candidate must supply delta")
            raise TypeError("delta must have exact type Decimal")
        if not delta.is_finite():
            raise ValueError("delta must be finite")
        if quote.contract_key.option_type == "call":
            if not decimal.Decimal("0") < delta < decimal.Decimal("1"):
                raise ValueError("call delta must be strictly between 0 and 1")
        elif quote.contract_key.option_type == "put":
            if not decimal.Decimal("-1") < delta < decimal.Decimal("0"):
                raise ValueError("put delta must be strictly between -1 and 0")
        else:
            raise ValueError("tail candidate option side is unsupported")
    if len(session_dates) != 1:
        raise ValueError("selection must contain one common session date")
    session_date = next(iter(session_dates))
    return {
        "selection": selection,
        "underlying_quote": underlying,
        "underlying_key": underlying_key,
        "session_date": session_date,
        "candidates": tuple(candidates),
        "bindings": tuple(entry[2] for entry in entry_by_binding.values()),
        "records": tuple(entry[3] for entry in entry_by_binding.values()),
    }


def _tail_methodology(candidate: tuple) -> tuple:
    _quote, iv, greeks, _reference = candidate
    return (
        iv.model_name,
        iv.model_version,
        iv.rate_input_description,
        iv.dividend_input_description,
        iv.metadata.unit_convention,
        greeks.model_name,
        greeks.model_version,
        greeks.rate_input_description,
        greeks.dividend_input_description,
        greeks.metadata.unit_convention,
    )


def _tail_selected_point(
    candidates: tuple,
    option_type: str,
    target: decimal.Decimal,
) -> dict:
    eligible = tuple(
        item for item in candidates
        if item[0].contract_key.option_type == option_type
    )
    if not eligible:
        raise ValueError("tail target has no candidate on the required side")
    distances = tuple(
        (_exact_distance(item[2].delta, target), item) for item in eligible
    )
    minimum = min(item[0] for item in distances)
    selected = tuple(item[1] for item in distances if item[0] == minimum)
    if len(selected) != 1:
        raise ValueError("nearest signed-delta target selection is ambiguous")
    quote, iv, greeks, reference = selected[0]
    contract = quote.contract_key
    return {
        "target_delta": target,
        "selected_delta": greeks.delta,
        "distance": minimum,
        "option_type": contract.option_type,
        "strike": contract.strike,
        "contract_multiplier": contract.contract_multiplier,
        "currency": contract.currency,
        "deliverable_id": contract.deliverable_id,
        "quote_record_id": quote.metadata.record_id,
        "iv_record_id": iv.metadata.record_id,
        "greeks_record_id": greeks.metadata.record_id,
        "contract_reference_record_id": reference.metadata.record_id,
        "implied_volatility": iv.implied_volatility,
        "_contract": contract,
    }


def _tail_candidate_parameters(candidate: tuple) -> dict:
    quote, iv, greeks, reference = candidate
    contract = quote.contract_key
    target_25 = (
        _TAIL_TARGETS["call_25"]
        if contract.option_type == "call"
        else _TAIL_TARGETS["put_25"]
    )
    target_10 = (
        _TAIL_TARGETS["call_10"]
        if contract.option_type == "call"
        else _TAIL_TARGETS["put_10"]
    )
    return {
        "option_type": contract.option_type,
        "strike": contract.strike,
        "contract_multiplier": contract.contract_multiplier,
        "currency": contract.currency,
        "deliverable_id": contract.deliverable_id,
        "quote_record_id": quote.metadata.record_id,
        "iv_record_id": iv.metadata.record_id,
        "greeks_record_id": greeks.metadata.record_id,
        "contract_reference_record_id": reference.metadata.record_id,
        "implied_volatility": iv.implied_volatility,
        "signed_delta": greeks.delta,
        "distance_to_25_target": _exact_distance(greeks.delta, target_25),
        "distance_to_10_target": _exact_distance(greeks.delta, target_10),
    }


def _without_private_fields(value: dict) -> dict:
    return {key: item for key, item in value.items() if not key.startswith("_")}


def _tail_wings(candidates: tuple) -> dict:
    selected = {
        name: _tail_selected_point(
            candidates,
            "call" if name.startswith("call") else "put",
            target,
        )
        for name, target in _TAIL_TARGETS.items()
    }
    for side in ("call", "put"):
        point_10 = selected[f"{side}_10"]
        point_25 = selected[f"{side}_25"]
        if point_10["_contract"] == point_25["_contract"]:
            raise ValueError(
                "one economic contract cannot satisfy both same-side targets"
            )
        if not (
            point_10["selected_delta"].copy_abs()
            < point_25["selected_delta"].copy_abs()
        ):
            raise ValueError(
                "selected 10-delta absolute value must be below 25-delta"
            )
    return selected


def _tail_skew_metrics(
    wings: dict, atm_iv: decimal.Decimal
) -> dict:
    put_25 = wings["put_25"]["implied_volatility"]
    call_25 = wings["call_25"]["implied_volatility"]
    put_10 = wings["put_10"]["implied_volatility"]
    call_10 = wings["call_10"]["implied_volatility"]
    return {
        "downside_25_delta_skew": _exact_scaled_sum(
            ((put_25, 1), (atm_iv.copy_negate(), 1))
        ),
        "upside_25_delta_skew": _exact_scaled_sum(
            ((call_25, 1), (atm_iv.copy_negate(), 1))
        ),
        "downside_wing_curvature": _exact_scaled_sum(
            ((put_10, 1), (put_25.copy_negate(), 1))
        ),
        "upside_wing_curvature": _exact_scaled_sum(
            ((call_10, 1), (call_25.copy_negate(), 1))
        ),
    }


def _decode_volatility_parameters(parameters_json: str) -> dict:
    if type(parameters_json) is not str:
        raise TypeError("volatility parameters_json must have exact type str")
    def reject_float(_value: str) -> object:
        raise ValueError("3C.7d parameters must not contain JSON floats")

    def reject_constant(_value: str) -> object:
        raise ValueError("3C.7d parameters must not contain nonfinite constants")

    def unique_object(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("3C.7d parameters contain a duplicate JSON key")
            result[key] = value
        return result

    try:
        raw = json.loads(
            parameters_json,
            parse_float=reject_float,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError("3C.7d parameters_json is invalid") from error

    def decode(value: object) -> object:
        if value is None or type(value) in (bool, int, str):
            return value
        if type(value) is list:
            return tuple(decode(item) for item in value)
        if type(value) is not dict or len(value) != 1:
            raise ValueError("3C.7d parameters use an unsupported JSON form")
        tag, payload = next(iter(value.items()))
        if tag == "$map":
            if type(payload) is not list:
                raise ValueError("$map payload must be a list")
            result = {}
            for pair in payload:
                if (
                    type(pair) is not list
                    or len(pair) != 2
                    or type(pair[0]) is not str
                    or pair[0] in result
                ):
                    raise ValueError("$map entries must have unique string keys")
                result[pair[0]] = decode(pair[1])
            return result
        if tag == "$list":
            if type(payload) is not list:
                raise ValueError("$list payload must be a list")
            return tuple(decode(item) for item in payload)
        if tag == "$decimal":
            if type(payload) is not str:
                raise ValueError("$decimal payload must be a string")
            try:
                result = decimal.Decimal(payload)
            except decimal.InvalidOperation as error:
                raise ValueError("$decimal payload is invalid") from error
            if not result.is_finite():
                raise ValueError("$decimal payload must be finite")
            return result
        if tag == "$date":
            if type(payload) is not str:
                raise ValueError("$date payload must be a string")
            try:
                result = datetime.date.fromisoformat(payload)
            except ValueError as error:
                raise ValueError("$date payload is invalid") from error
            if result.isoformat() != payload:
                raise ValueError("$date payload is noncanonical")
            return result
        if tag == "$datetime":
            if type(payload) is not str or not payload.endswith("Z"):
                raise ValueError("$datetime payload must be canonical UTC")
            try:
                result = datetime.datetime.fromisoformat(
                    payload[:-1] + "+00:00"
                )
            except ValueError as error:
                raise ValueError("$datetime payload is invalid") from error
            return result
        raise ValueError("3C.7d parameters contain an unknown tag")

    decoded = decode(raw)
    if type(decoded) is not dict:
        raise ValueError("3C.7d parameters root must be a tagged map")
    if tuple(sorted(decoded)) != tuple(sorted(_VOLATILITY_PARAMETER_KEYS)):
        raise ValueError("volatility v0.2 parameters have the wrong exact 21-key schema")
    try:
        if canonicalize_lineage_parameters(decoded) != parameters_json:
            raise ValueError("3C.7d parameters are not byte-canonical")
    except (TypeError, ValueError) as error:
        raise ValueError("3C.7d parameters are not canonical") from error
    return decoded


def _validate_volatility_fixed_methodology(decoded: dict) -> None:
    candidate_universe = decoded["atm_candidate_universe"]
    if type(candidate_universe) is not dict:
        raise TypeError(
            "volatility-environment dependency ATM candidate universe "
            "must have exact type dict"
        )
    candidate_keys = {
        "declared_complete",
        "scope",
        "completeness_semantics",
    }
    if set(candidate_universe) != candidate_keys:
        raise ValueError(
            "volatility-environment dependency has incompatible fixed "
            "methodology parameters"
        )
    if type(candidate_universe["declared_complete"]) is not bool:
        raise TypeError(
            "volatility-environment dependency declared_complete must have "
            "exact type bool"
        )
    for key in ("scope", "completeness_semantics"):
        if type(candidate_universe[key]) is not str:
            raise TypeError(
                "volatility-environment dependency candidate-universe "
                "strings must have exact type str"
            )
    if candidate_universe != {
        "declared_complete": True,
        "scope": "all_exact_selected_session_expiration_universes",
        "completeness_semantics": (
            "no_eligible_paired_call_put_strike_omitted"
        ),
    }:
        raise ValueError(
            "volatility-environment dependency does not declare a complete "
            "ATM candidate universe"
        )

    fixed_strings = {
        "atm_selection_rule": (
            "nearest_paired_call_put_strike_to_underlying_bid_ask_midpoint"
        ),
        "call_put_combination_rule": (
            "arithmetic_mean_of_same_strike_call_and_put_implied_volatility"
        ),
        "float_conversion_rule": (
            "convert_only_final_decimal_research_values_to_finite_float"
        ),
        "historical_matched_tenor_rule": (
            "expiration_minus_session_date_calendar_days_equals_reference_"
            "tenor"
        ),
        "historical_sample_semantics": (
            "caller_declared_observation_sample"
        ),
        "median_formula": (
            "odd_middle_even_arithmetic_mean_of_two_middle_values"
        ),
        "percentile_formula": (
            "inclusive_count_historical_atm_iv_lte_current_reference_atm_iv_"
            "divided_by_count"
        ),
        "realized_window_matching_rule": (
            "realized_end_equals_current_as_of_and_calendar_span_equals_"
            "reference_tenor"
        ),
        "strike_tie_rule": "lower_strike",
        "term_tenor_rule": (
            "expiration_minus_session_date_calendar_days"
        ),
        "underlying_midpoint_rule": (
            "bid_ask_midpoint_no_last_fallback"
        ),
        "volatility_unit": "annualized_decimal_ratio",
    }
    for key, expected in fixed_strings.items():
        if type(decoded[key]) is not str:
            raise TypeError(
                "volatility-environment dependency fixed methodology "
                "declarations must have exact type str"
            )
        if decoded[key] != expected:
            raise ValueError(
                "volatility-environment dependency has incompatible fixed "
                "methodology parameters"
            )

    iv_methodology = decoded["iv_methodology"]
    if type(iv_methodology) is not dict:
        raise TypeError(
            "volatility-environment dependency iv_methodology must have "
            "exact type dict"
        )
    iv_keys = {
        "model_name",
        "model_version",
        "rate_input_description",
        "dividend_input_description",
        "unit_convention",
    }
    if set(iv_methodology) != iv_keys:
        raise ValueError(
            "volatility-environment dependency has incompatible fixed "
            "methodology parameters"
        )
    for value in iv_methodology.values():
        if type(value) is not str:
            raise TypeError(
                "volatility-environment dependency IV methodology values "
                "must have exact type str"
            )
        if not value or value != value.strip():
            raise ValueError(
                "volatility-environment dependency IV methodology values "
                "must be nonempty canonical strings"
            )
    if iv_methodology["unit_convention"] != "annualized_decimal_ratio":
        raise ValueError(
            "volatility-environment dependency has incompatible fixed "
            "methodology parameters"
        )


_REALIZED_DEPENDENCY_KEYS = {
    "calculation_id",
    "calculation_type",
    "methodology_id",
    "methodology_version",
    "calculated_at",
    "parameters_json",
    "quality_flags",
    "inputs",
    "underlying",
    "start_session_date",
    "end_session_date",
    "session_dates",
    "price_basis",
    "adjustment_methodology",
    "prices",
    "log_returns",
    "annualization_sessions_per_year",
    "return_formula",
    "variance_estimator",
    "price_observation_count",
    "return_observation_count",
    "annualized_realized_volatility_float_repr",
}
_HISTORICAL_PARAMETER_KEYS = {
    "adjustment_methodology",
    "annualization_rule",
    "annualization_sessions_per_year",
    "expected_session_dates",
    "price_basis",
    "price_observation_count",
    "price_unit",
    "return_association_rule",
    "return_formula",
    "return_observation_count",
    "return_unit",
    "underlying",
    "variance_estimator",
    "volatility_unit",
    "window_end_session_date",
    "window_start_session_date",
}


def _reconstruct_realized_dependency(
    value: object,
    enclosing_underlying: str,
    enclosing_calculation_id: str,
    enclosing_calculated_at: datetime.datetime,
) -> tuple:
    if type(value) is not dict:
        raise TypeError("realized dependency must have exact type dict")
    if set(value) != _REALIZED_DEPENDENCY_KEYS:
        raise ValueError("realized dependency has the wrong exact schema")

    underlying_value = value["underlying"]
    if type(underlying_value) is not dict:
        raise TypeError("realized dependency underlying must have exact type dict")
    if set(underlying_value) != {
        "symbol", "listing_mic", "security_type", "currency",
    }:
        raise ValueError("realized dependency underlying has the wrong exact schema")
    for key in ("symbol", "security_type", "currency"):
        if type(underlying_value[key]) is not str:
            raise TypeError(
                f"realized dependency underlying {key} must have exact type str"
            )
    if (
        underlying_value["listing_mic"] is not None
        and type(underlying_value["listing_mic"]) is not str
    ):
        raise TypeError(
            "realized dependency underlying listing_mic must be None or an "
            "exact str"
        )
    try:
        security_type = UnderlyingSecurityType(
            underlying_value["security_type"]
        )
    except ValueError as error:
        raise ValueError(
            "realized dependency underlying security_type is unsupported"
        ) from error
    underlying = UnderlyingKey(
        symbol=underlying_value["symbol"],
        listing_mic=underlying_value["listing_mic"],
        security_type=security_type,
        currency=underlying_value["currency"],
    )
    if _underlying_identity(underlying) != underlying_value:
        raise ValueError("realized dependency underlying is noncanonical")
    if underlying.symbol != enclosing_underlying:
        raise ValueError("realized and volatility underlyings differ")

    if type(value["price_basis"]) is not str:
        raise TypeError("realized dependency price_basis must have exact type str")
    try:
        price_basis = HistoricalReturnPriceBasis(value["price_basis"])
    except ValueError as error:
        raise ValueError("realized dependency price_basis is unsupported") from error
    annualized = _float_from_stable_repr(
        value["annualized_realized_volatility_float_repr"],
        "realized dependency annualized volatility",
    )
    realized_record = HistoricalRealizedVolatility(
        underlying_key=underlying,
        start_session_date=value["start_session_date"],
        end_session_date=value["end_session_date"],
        price_basis=price_basis,
        adjustment_methodology=value["adjustment_methodology"],
        session_dates=value["session_dates"],
        prices=value["prices"],
        log_returns=value["log_returns"],
        annualized_realized_volatility=annualized,
        annualization_sessions_per_year=(
            value["annualization_sessions_per_year"]
        ),
        return_formula=value["return_formula"],
        variance_estimator=value["variance_estimator"],
    )
    for key, expected in (
        ("price_observation_count", realized_record.price_observation_count),
        ("return_observation_count", realized_record.return_observation_count),
    ):
        if type(value[key]) is not int:
            raise TypeError(f"realized dependency {key} must have exact type int")
        if value[key] != expected:
            raise ValueError(f"realized dependency {key} is inconsistent")

    inputs_value = value["inputs"]
    if type(inputs_value) is not tuple:
        raise TypeError("realized dependency inputs must have exact type tuple")
    inputs = tuple(
        CalculationInputReference(
            record_id=_complete_reference_from_mapping(
                item, f"realized dependency inputs[{index}]"
            )["record_id"],
            normalized_at=item["normalized_at"],
            source_ids=item["source_ids"],
        )
        for index, item in enumerate(inputs_value)
    )
    flags_value = _quality_flag_values(
        value["quality_flags"], set(CalculationQualityFlag),
        "realized dependency quality_flags",
    )
    flags = tuple(CalculationQualityFlag(item) for item in flags_value)
    realized_lineage = CalculationLineage(
        calculation_id=value["calculation_id"],
        calculation_type=value["calculation_type"],
        methodology_id=value["methodology_id"],
        methodology_version=value["methodology_version"],
        calculated_at=value["calculated_at"],
        inputs=inputs,
        parameters_json=value["parameters_json"],
        quality_flags=flags,
    )
    realized_result = HistoricalRealizedVolatilityTransformationResult(
        record=realized_record,
        lineage=realized_lineage,
    )
    _validate_realized_dependency(
        realized_result,
        enclosing_calculation_id,
        enclosing_calculated_at,
    )

    historical_parameters = _decode_strict_tagged_parameters(
        realized_lineage.parameters_json,
        _HISTORICAL_PARAMETER_KEYS,
        "realized dependency",
    )
    if realized_lineage.parameters_json != _construct_historical_parameters(
        realized_record
    ):
        raise ValueError("realized dependency parameters differ from its record")
    if (
        historical_parameters["expected_session_dates"]
        != realized_record.session_dates
        or historical_parameters["price_observation_count"]
        != realized_record.price_observation_count
        or historical_parameters["return_observation_count"]
        != realized_record.return_observation_count
    ):
        raise ValueError("realized dependency observation disclosure is inconsistent")
    return realized_record, realized_lineage, inputs_value, flags_value


def _verify_volatility_environment_result(
    record: object, lineage: object
) -> tuple:
    if type(record) is not VolatilityEnvironment:
        raise TypeError(
            "volatility dependency record must have exact type "
            "VolatilityEnvironment"
        )
    if type(record.underlying) is not str:
        raise TypeError("volatility underlying must have exact type str")
    if type(record.as_of_date) is not datetime.date:
        raise TypeError("volatility as_of_date must have exact type date")
    for name in (
        "reference_tenor_days", "iv_history_lookback_observations",
        "matched_realized_window_days",
    ):
        if type(getattr(record, name)) is not int:
            raise TypeError(f"volatility {name} must have exact type int")
    for name in (
        "iv_percentile", "historical_median_atm_iv",
        "matched_realized_volatility",
    ):
        _stable_float(getattr(record, name), f"volatility {name}")
    if type(record.term_structure) is not tuple:
        raise TypeError("volatility term_structure must have exact type tuple")
    if any(type(item) is not TermVolatilityPoint for item in record.term_structure):
        raise TypeError("every dependency term point must have exact type TermVolatilityPoint")
    reconstructed_points = []
    for point in record.term_structure:
        if type(point.tenor_days) is not int:
            raise TypeError("term-point tenor_days must have exact type int")
        _stable_float(point.atm_iv, "term-point atm_iv")
        reconstructed_points.append(TermVolatilityPoint(
            tenor_days=point.tenor_days, atm_iv=point.atm_iv
        ))
    reconstructed_record = VolatilityEnvironment(
        underlying=record.underlying,
        as_of_date=record.as_of_date,
        reference_tenor_days=record.reference_tenor_days,
        iv_percentile=record.iv_percentile,
        iv_history_lookback_observations=(
            record.iv_history_lookback_observations
        ),
        historical_median_atm_iv=record.historical_median_atm_iv,
        matched_realized_volatility=record.matched_realized_volatility,
        matched_realized_window_days=record.matched_realized_window_days,
        term_structure=tuple(reconstructed_points),
    )
    if reconstructed_record != record:
        raise ValueError("volatility record is constructor-bypassed")
    lineage = _reconstruct_lineage(lineage)
    if (
        lineage.calculation_type != "volatility_environment"
        or lineage.methodology_id != "paired-atm-volatility-environment"
        or lineage.methodology_version != "v0.2"
    ):
        raise ValueError("volatility dependency lineage identity is invalid")
    required = {
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    decoded = _decode_volatility_parameters(lineage.parameters_json)
    _validate_volatility_fixed_methodology(decoded)
    current = decoded["current_observations"]
    historical = decoded["historical_observations"]
    if type(current) is not tuple or type(historical) is not tuple:
        raise ValueError("3C.7d observations must be canonical lists")
    if decoded["historical_observation_count"] != len(historical):
        raise ValueError("3C.7d historical observation count is inconsistent")
    if record.iv_history_lookback_observations != len(historical):
        raise ValueError("dependency record history count is inconsistent")
    if decoded["reference_tenor_days"] != record.reference_tenor_days:
        raise ValueError("dependency reference tenor is inconsistent")
    if decoded["volatility_unit"] != "annualized_decimal_ratio":
        raise ValueError("dependency volatility unit is invalid")
    if len(current) != len(record.term_structure):
        raise ValueError("dependency current term count is inconsistent")
    by_tenor = {}
    for item in current:
        if type(item) is not dict:
            raise ValueError("dependency current observation must be a map")
        required_keys = {
            "candidate_pairs",
            "expiration",
            "selected_atm_iv",
            "selected_call_iv_record_id",
            "selected_put_iv_record_id",
            "selected_strike",
            "session_date",
            "tenor_days",
            "underlying_midpoint",
            "underlying_quote_record_id",
        }
        if set(item) != required_keys:
            raise ValueError(
                "dependency current observation has the wrong exact schema"
            )
        _validate_tail_atm_observation_parameter(
            item, "volatility current observation"
        )
        if (
            type(item["session_date"]) is not datetime.date
            or type(item["expiration"]) is not datetime.date
            or type(item["tenor_days"]) is not int
            or type(item["selected_atm_iv"]) is not decimal.Decimal
            or type(item["underlying_midpoint"]) is not decimal.Decimal
            or type(item["selected_call_iv_record_id"]) is not str
            or type(item["selected_put_iv_record_id"]) is not str
        ):
            raise TypeError("dependency current observation has wrong exact types")
        if item["session_date"] != record.as_of_date:
            raise ValueError("dependency current as-of date is inconsistent")
        if (
            item["expiration"] - item["session_date"]
        ).days != item["tenor_days"]:
            raise ValueError("dependency current tenor is inconsistent")
        if item["tenor_days"] in by_tenor:
            raise ValueError("dependency current tenors must be unique")
        by_tenor[item["tenor_days"]] = item
    if set(by_tenor) != {
        point.tenor_days for point in record.term_structure
    }:
        raise ValueError("dependency term points do not match parameters")
    for point in record.term_structure:
        if _finite_float(
            by_tenor[point.tenor_days]["selected_atm_iv"]
        ) != point.atm_iv:
            raise ValueError("dependency term-point ATM IV is inconsistent")
    historical_values = []
    historical_dates = []
    for item in historical:
        if type(item) is not dict or set(item) != required_keys:
            raise ValueError(
                "dependency historical observation has the wrong exact schema"
            )
        _validate_tail_atm_observation_parameter(
            item, "volatility historical observation"
        )
        if (
            type(item["session_date"]) is not datetime.date
            or type(item["expiration"]) is not datetime.date
            or type(item["tenor_days"]) is not int
            or type(item["selected_atm_iv"]) is not decimal.Decimal
        ):
            raise TypeError(
                "dependency historical observation has wrong exact types"
            )
        if item["tenor_days"] != record.reference_tenor_days:
            raise ValueError(
                "dependency historical tenor differs from reference tenor"
            )
        if (
            item["expiration"] - item["session_date"]
        ).days != item["tenor_days"]:
            raise ValueError("dependency historical tenor is inconsistent")
        historical_dates.append(item["session_date"])
        historical_values.append(item["selected_atm_iv"])
    if tuple(historical_dates) != decoded[
        "historical_expected_session_dates"
    ]:
        raise ValueError("dependency historical dates are inconsistent")
    reference_atm = by_tenor[record.reference_tenor_days]["selected_atm_iv"]
    expected_percentile = _percentile(
        sum(value <= reference_atm for value in historical_values),
        len(historical_values),
    )
    if record.iv_percentile != _finite_float(expected_percentile):
        raise ValueError("dependency IV percentile is inconsistent")
    if record.historical_median_atm_iv != _finite_float(
        _median(tuple(historical_values))
    ):
        raise ValueError("dependency historical median is inconsistent")
    realized = decoded["realized_volatility_dependency"]
    (
        realized_record,
        realized_lineage,
        realized_inputs,
        realized_flags,
    ) = _reconstruct_realized_dependency(
        realized,
        record.underlying,
        lineage.calculation_id,
        lineage.calculated_at,
    )
    realized_span = (
        realized_record.end_session_date - realized_record.start_session_date
    ).days
    if (
        realized_record.end_session_date != record.as_of_date
        or realized_span != record.reference_tenor_days
        or record.matched_realized_window_days != realized_span
        or realized_record.annualized_realized_volatility
        != record.matched_realized_volatility
        or repr(realized_record.annualized_realized_volatility)
        != realized["annualized_realized_volatility_float_repr"]
    ):
        raise ValueError("dependency realized-volatility fields are inconsistent")
    input_ids = tuple(item.record_id for item in lineage.inputs)
    realized_ids = tuple(item["record_id"] for item in realized_inputs)
    if tuple(sorted(realized_ids)) != realized_ids or len(set(realized_ids)) != len(realized_ids):
        raise ValueError("realized dependency inputs are not canonical")
    expected_input_ids = set(realized_ids)
    direct = _validate_direct_evidence(
        decoded["normalized_evidence"], {
            "underlying_quote", "option_quote",
            "option_implied_volatility", "option_contract_reference",
        }, "volatility normalized_evidence",
    )
    direct_by_id = {item["record_id"]: item for item in direct}
    expected_roles = {}
    def retain_role(record_id: str, role: str) -> None:
        existing = expected_roles.get(record_id)
        if existing is not None and existing != role:
            raise ValueError("volatility direct evidence role collision")
        expected_roles[record_id] = role
    for item in current + historical:
        expected_input_ids.add(item["underlying_quote_record_id"])
        retain_role(item["underlying_quote_record_id"], "underlying_quote")
        for pair in item["candidate_pairs"]:
            if type(pair) is not dict:
                raise ValueError("dependency ATM candidate must be a map")
            expected_input_ids.update((
                pair["call_quote_record_id"],
                pair["call_iv_record_id"],
                pair["call_contract_reference_record_id"],
                pair["put_quote_record_id"],
                pair["put_iv_record_id"],
                pair["put_contract_reference_record_id"],
            ))
            for key, role in (
                ("call_quote_record_id", "option_quote"),
                ("put_quote_record_id", "option_quote"),
                ("call_iv_record_id", "option_implied_volatility"),
                ("put_iv_record_id", "option_implied_volatility"),
                ("call_contract_reference_record_id", "option_contract_reference"),
                ("put_contract_reference_record_id", "option_contract_reference"),
            ):
                retain_role(pair[key], role)
    if set(direct_by_id) != set(expected_roles) or any(
        direct_by_id[record_id]["role"] != role
        for record_id, role in expected_roles.items()
    ):
        raise ValueError("volatility direct evidence is missing, surplus, or mis-typed")
    references = {item.record_id: item for item in lineage.inputs}
    for item in realized_inputs + direct:
        reference = references.get(item["record_id"])
        if reference is None or (
            reference.normalized_at != item["normalized_at"]
            or reference.source_ids != item["source_ids"]
        ):
            raise ValueError("volatility retained reference differs from lineage")
    if len(input_ids) != len(set(input_ids)) or set(input_ids) != expected_input_ids:
        raise ValueError("dependency lineage inputs are inconsistent with parameters")
    calculation_ids = {
        lineage.calculation_id,
        realized_lineage.calculation_id,
    }
    if (
        len(calculation_ids) != 2
        or not calculation_ids.isdisjoint(expected_input_ids)
    ):
        raise ValueError("volatility calculation ID namespace collides")
    selected_flags = set(required)
    propagated_values = set(realized_flags)
    propagated_values.update(
        flag for item in direct for flag in item["propagated_quality_flags"]
    )
    for flag in (
        CalculationQualityFlag.ADJUSTED_INPUT_USED,
        CalculationQualityFlag.CORRECTION_SELECTED,
        CalculationQualityFlag.COMPOSITE_INPUT_USED,
        CalculationQualityFlag.INTERPOLATED,
    ):
        if flag.value in propagated_values:
            selected_flags.add(flag)
    expected_flags = tuple(
        flag for flag in CalculationQualityFlag if flag in selected_flags
    )
    if lineage.quality_flags != expected_flags:
        raise ValueError("volatility dependency quality flags are invalid")
    return record, lineage, decoded, by_tenor


def _validate_volatility_dependency(
    value: object,
    calculation_id: str,
    calculated_at: datetime.datetime,
) -> tuple:
    if type(value) is not VolatilityEnvironmentTransformationResult:
        raise TypeError(
            "volatility_environment_result must have exact type "
            "VolatilityEnvironmentTransformationResult"
        )
    verified = _verify_volatility_environment_result(
        value.record, value.lineage
    )
    lineage = verified[1]
    if calculation_id == lineage.calculation_id:
        raise ValueError("new and prior calculation IDs must differ")
    if calculated_at < lineage.calculated_at:
        raise ValueError("new calculation must not precede dependency")
    return verified


def _historical_atm(
    selection: dict,
) -> dict:
    underlying = selection["underlying_quote"]
    if (
        type(underlying.bid_price) is not decimal.Decimal
        or type(underlying.ask_price) is not decimal.Decimal
        or not underlying.bid_price.is_finite()
        or not underlying.ask_price.is_finite()
        or underlying.bid_price <= 0
        or underlying.ask_price <= 0
    ):
        raise ValueError("historical underlying bid and ask must be positive")
    midpoint = _exact_midpoint(underlying.bid_price, underlying.ask_price)
    paired = {}
    for candidate in selection["candidates"]:
        contract = candidate[0].contract_key
        key = (
            contract.underlying_key,
            contract.expiration,
            contract.strike,
            contract.contract_multiplier,
            contract.currency,
            contract.deliverable_id,
        )
        paired.setdefault(key, []).append(candidate)
    candidates = []
    for values in paired.values():
        calls = tuple(
            item for item in values
            if item[0].contract_key.option_type == "call"
        )
        puts = tuple(
            item for item in values
            if item[0].contract_key.option_type == "put"
        )
        if len(calls) != 1 or len(puts) != 1 or len(values) != 2:
            continue
        call = calls[0]
        put = puts[0]
        strike = call[0].contract_key.strike
        candidates.append({
            "strike": strike,
            "contract_multiplier": call[0].contract_key.contract_multiplier,
            "currency": call[0].contract_key.currency,
            "deliverable_id": call[0].contract_key.deliverable_id,
            "call_quote_record_id": call[0].metadata.record_id,
            "call_iv_record_id": call[1].metadata.record_id,
            "call_contract_reference_record_id": call[3].metadata.record_id,
            "put_quote_record_id": put[0].metadata.record_id,
            "put_iv_record_id": put[1].metadata.record_id,
            "put_contract_reference_record_id": put[3].metadata.record_id,
            "call_implied_volatility": call[1].implied_volatility,
            "put_implied_volatility": put[1].implied_volatility,
            "paired_implied_volatility": _exact_two_value_mean(
                call[1].implied_volatility, put[1].implied_volatility
            ),
            "distance_to_underlying_midpoint": _exact_distance(
                strike, midpoint
            ),
        })
    if not candidates:
        raise ValueError("historical selection has no compatible ATM pair")
    minimum = min(
        item["distance_to_underlying_midpoint"] for item in candidates
    )
    closest = tuple(
        item for item in candidates
        if item["distance_to_underlying_midpoint"] == minimum
    )
    selected_strike = min(item["strike"] for item in closest)
    final = tuple(item for item in closest if item["strike"] == selected_strike)
    if len(final) != 1:
        raise ValueError(
            "historical ATM selection remains ambiguous at selected strike"
        )
    selected = final[0]
    return {
        "underlying_midpoint": midpoint,
        "candidate_pairs": tuple(sorted(
            candidates,
            key=lambda item: (
                item["strike"],
                item["contract_multiplier"],
                item["currency"],
                (0, "") if item["deliverable_id"] is None
                else (1, item["deliverable_id"]),
                item["call_iv_record_id"],
                item["put_iv_record_id"],
            ),
        )),
        "selected_strike": selected["strike"],
        "selected_call_iv_record_id": selected["call_iv_record_id"],
        "selected_put_iv_record_id": selected["put_iv_record_id"],
        "selected_atm_iv": selected["paired_implied_volatility"],
    }


def _tail_dependency_parameters(
    record: VolatilityEnvironment,
    lineage: CalculationLineage,
    decoded: dict,
) -> dict:
    return {
        "calculation_id": lineage.calculation_id,
        "calculation_type": lineage.calculation_type,
        "methodology_id": lineage.methodology_id,
        "methodology_version": lineage.methodology_version,
        "calculated_at": lineage.calculated_at,
        "parameters_json": lineage.parameters_json,
        "quality_flags": tuple(flag.value for flag in lineage.quality_flags),
        "inputs": tuple(
            _complete_input_reference(item) for item in lineage.inputs
        ),
        "underlying": record.underlying,
        "as_of_date": record.as_of_date,
        "reference_tenor_days": record.reference_tenor_days,
        "iv_percentile_float_repr": repr(record.iv_percentile),
        "historical_observation_count": (
            record.iv_history_lookback_observations
        ),
        "historical_median_atm_iv_float_repr": repr(
            record.historical_median_atm_iv
        ),
        "matched_realized_volatility_float_repr": repr(
            record.matched_realized_volatility
        ),
        "matched_realized_window_days": record.matched_realized_window_days,
        "term_points": tuple({
            "tenor_days": point.tenor_days,
            "atm_iv_float_repr": repr(point.atm_iv),
        } for point in record.term_structure),
        "current_atm_observations": decoded["current_observations"],
        "historical_atm_observations": decoded["historical_observations"],
    }


def _union_lineage_inputs(
    prior: tuple, direct_records: tuple
) -> tuple:
    direct = _construct_input_references(direct_records)
    by_id = {}
    for item in prior + direct:
        if type(item) is not CalculationInputReference:
            raise TypeError(
                "every lineage input must have exact type "
                "CalculationInputReference"
            )
        existing = by_id.get(item.record_id)
        if existing is not None and existing != item:
            raise ValueError(
                "overlapping lineage references must be exactly equal"
            )
        by_id[item.record_id] = item
    return tuple(by_id.values())


def _validate_delta_methodology(value: object) -> tuple:
    if type(value) is not dict:
        raise TypeError("delta_methodology must have exact built-in type dict")
    keys = {
        "signed_delta_convention",
        "delta_basis",
        "premium_adjustment",
        "model_provider_methodology",
        "target_selection_methodology",
        "interpolation_methodology",
    }
    if set(value) != keys:
        raise ValueError("delta_methodology must contain exactly six keys")
    if any(type(key) is not str for key in value):
        raise TypeError("every delta_methodology key must have exact type str")
    for item in value.values():
        if type(item) is not str:
            raise TypeError(
                "every delta_methodology value must have exact type str"
            )
        if not item or item != item.strip():
            raise ValueError(
                "delta_methodology values must be nonempty canonical strings"
            )
    if value["signed_delta_convention"] != "call_positive_put_negative":
        raise ValueError("signed_delta_convention is unsupported")
    if value["delta_basis"] not in {"spot", "forward"}:
        raise ValueError("delta_basis is unsupported")
    if value["premium_adjustment"] not in {
        "unadjusted", "premium_adjusted"
    }:
        raise ValueError("premium_adjustment is unsupported")
    if (
        value["target_selection_methodology"]
        != "nearest_observed_signed_delta"
        or value["interpolation_methodology"] != "none"
    ):
        raise ValueError("delta target or interpolation methodology is invalid")
    return dict(value), canonicalize_lineage_parameters(value)


def transform_tail_pricing(
    calculation_id: object,
    current_relationship_selection: object,
    historical_relationship_selections: object,
    historical_expected_session_dates: object,
    volatility_environment_result: object,
    tail_candidate_universes_complete: object,
    historical_end_of_day_observations_declared: object,
    historical_end_of_day_methodology: object,
    delta_methodology: object,
    calculated_at: object,
) -> TailPricingTransformationResult:
    """Construct an ordered nearest-observed-delta tail-pricing term structure."""

    normalized_id = _validate_calculation_id(calculation_id)
    if type(historical_relationship_selections) is not tuple:
        raise TypeError(
            "historical_relationship_selections must have exact type tuple"
        )
    if not historical_relationship_selections:
        raise ValueError("historical_relationship_selections must not be empty")
    if any(
        type(item) is not MarketDataRelationshipSelection
        for item in historical_relationship_selections
    ):
        raise TypeError(
            "every historical selection must have exact type "
            "MarketDataRelationshipSelection"
        )
    if type(historical_expected_session_dates) is not tuple:
        raise TypeError(
            "historical_expected_session_dates must have exact type tuple"
        )
    if not historical_expected_session_dates:
        raise ValueError("historical_expected_session_dates must not be empty")
    if any(
        type(item) is not datetime.date
        for item in historical_expected_session_dates
    ):
        raise TypeError("every historical date must have exact type date")
    if any(
        current <= previous
        for previous, current in zip(
            historical_expected_session_dates,
            historical_expected_session_dates[1:],
        )
    ):
        raise ValueError("historical dates must be strictly ascending")
    if type(tail_candidate_universes_complete) is not bool:
        raise TypeError(
            "tail_candidate_universes_complete must have exact type bool"
        )
    if not tail_candidate_universes_complete:
        raise ValueError("tail candidate universes must be declared complete")
    if type(historical_end_of_day_observations_declared) is not bool:
        raise TypeError(
            "historical_end_of_day_observations_declared must have exact "
            "type bool"
        )
    if not historical_end_of_day_observations_declared:
        raise ValueError("historical observations must be declared end-of-day")
    if type(historical_end_of_day_methodology) is not str:
        raise TypeError(
            "historical_end_of_day_methodology must have exact type str"
        )
    if (
        not historical_end_of_day_methodology
        or historical_end_of_day_methodology
        != historical_end_of_day_methodology.strip()
    ):
        raise ValueError(
            "historical_end_of_day_methodology must be canonical and nonempty"
        )
    delta_declaration, delta_string = _validate_delta_methodology(
        delta_methodology
    )
    normalized_at = _normalize_calculated_at(calculated_at)
    dependency_record, dependency_lineage, dependency_decoded, atm_by_tenor = (
        _validate_volatility_dependency(
            volatility_environment_result, normalized_id, normalized_at
        )
    )

    current = _validate_tail_selection(current_relationship_selection)
    expirations = tuple(sorted({
        item[0].contract_key.expiration for item in current["candidates"]
    }))
    if len(expirations) < 2:
        raise ValueError("current selection must contain at least two expirations")
    if current["underlying_key"].symbol != dependency_record.underlying:
        raise ValueError("current and dependency underlyings must match")
    if current["session_date"] != dependency_record.as_of_date:
        raise ValueError("current and dependency as-of dates must match")
    current_tenors = tuple(
        (expiration - current["session_date"]).days
        for expiration in expirations
    )
    if (
        any(tenor <= 0 for tenor in current_tenors)
        or len(set(current_tenors)) != len(current_tenors)
    ):
        raise ValueError("current term tenors must be unique and positive")
    if set(current_tenors) != set(atm_by_tenor):
        raise ValueError("current expirations must exactly match dependency terms")

    historical = tuple(
        _validate_tail_selection(item)
        for item in historical_relationship_selections
    )
    if len(historical) != (
        len(historical_expected_session_dates) * len(current_tenors)
    ):
        raise ValueError("historical selections must form the exact D by T matrix")
    historical_by_key = {}
    for item in historical:
        item_expirations = {
            candidate[0].contract_key.expiration
            for candidate in item["candidates"]
        }
        if len(item_expirations) != 1:
            raise ValueError(
                "every historical selection must contain one expiration universe"
            )
        expiration = next(iter(item_expirations))
        key = (
            item["session_date"],
            (expiration - item["session_date"]).days,
        )
        if key in historical_by_key:
            raise ValueError("historical intrinsic keys must be unique")
        historical_by_key[key] = item
        if any(
            candidate[0].market_phase is not MarketPhase.REGULAR
            for candidate in item["candidates"]
        ):
            raise ValueError("historical option quotes must use regular phase")
    expected_keys = {
        (session_date, tenor)
        for session_date in historical_expected_session_dates
        for tenor in current_tenors
    }
    if set(historical_by_key) != expected_keys:
        raise ValueError("historical intrinsic keys must equal date by tenor")
    if any(
        session_date >= current["session_date"]
        for session_date in historical_expected_session_dates
    ):
        raise ValueError("every historical date must precede current as_of_date")
    dependency_dates = tuple(
        dependency_decoded["historical_expected_session_dates"]
    )
    if dependency_dates != historical_expected_session_dates:
        raise ValueError(
            "historical dates must exactly equal the 3C.7d dependency sample"
        )
    if any(
        item["underlying_key"] != current["underlying_key"]
        for item in historical
    ):
        raise ValueError("all tail selections must share one underlying")

    methodologies = tuple(
        _tail_methodology(candidate)
        for item in (current,) + historical
        for candidate in item["candidates"]
    )
    if not methodologies or any(
        item != methodologies[0] for item in methodologies[1:]
    ):
        raise ValueError(
            "all IV and Greeks inputs must share one exact methodology"
        )
    analytics_methodology = methodologies[0]
    if analytics_methodology[4] != "annualized_decimal_ratio":
        raise ValueError("IV inputs must use annualized_decimal_ratio")
    dependency_iv_methodology = dependency_decoded["iv_methodology"]
    decoded_iv_methodology = (
        dependency_iv_methodology["model_name"],
        dependency_iv_methodology["model_version"],
        dependency_iv_methodology["rate_input_description"],
        dependency_iv_methodology["dividend_input_description"],
        dependency_iv_methodology["unit_convention"],
    )
    if decoded_iv_methodology != analytics_methodology[:5]:
        raise ValueError(
            "volatility-environment dependency IV methodology does not "
            "match authoritative IV inputs"
        )

    dependency_history_by_date = {
        item["session_date"]: item
        for item in dependency_decoded["historical_observations"]
    }
    historical_parameters_by_tenor = []
    historical_skews_by_tenor = {}
    reference_tenor = dependency_record.reference_tenor_days
    for tenor in sorted(current_tenors):
        observations = []
        skew_values = []
        for session_date in historical_expected_session_dates:
            item = historical_by_key[(session_date, tenor)]
            atm = _historical_atm(item)
            if tenor == reference_tenor:
                prior = dependency_history_by_date.get(session_date)
                if prior is None:
                    raise ValueError(
                        "dependency reference history is missing a date"
                    )
                if atm["selected_atm_iv"] != prior["selected_atm_iv"]:
                    raise ValueError(
                        "reference-tenor historical ATM IV is inconsistent"
                    )
                if (
                    atm["selected_call_iv_record_id"]
                    != prior["selected_call_iv_record_id"]
                    or atm["selected_put_iv_record_id"]
                    != prior["selected_put_iv_record_id"]
                ):
                    raise ValueError(
                        "reference-tenor historical ATM identities differ"
                    )
            wings = _tail_wings(item["candidates"])
            metrics = _tail_skew_metrics(wings, atm["selected_atm_iv"])
            skew_values.append(metrics["downside_25_delta_skew"])
            expiration = session_date + datetime.timedelta(days=tenor)
            observations.append({
                "session_date": session_date,
                "expiration": expiration,
                "underlying_quote_record_id": (
                    item["underlying_quote"].metadata.record_id
                ),
                "candidate_contracts": tuple(
                    _tail_candidate_parameters(candidate)
                    for candidate in item["candidates"]
                ),
                "selected_paired_atm_evidence": atm,
                "atm_iv": atm["selected_atm_iv"],
                "selected_put_25": _without_private_fields(wings["put_25"]),
                "selected_call_25": _without_private_fields(wings["call_25"]),
                "selected_put_10": _without_private_fields(wings["put_10"]),
                "selected_call_10": _without_private_fields(wings["call_10"]),
                "put_25_delta_iv": wings["put_25"]["implied_volatility"],
                "call_25_delta_iv": wings["call_25"]["implied_volatility"],
                "put_10_delta_iv": wings["put_10"]["implied_volatility"],
                "call_10_delta_iv": wings["call_10"]["implied_volatility"],
                **metrics,
            })
        historical_skews_by_tenor[tenor] = tuple(skew_values)
        current_expiration = next(
            expiration for expiration in expirations
            if (expiration - current["session_date"]).days == tenor
        )
        historical_parameters_by_tenor.append({
            "current_expiration": current_expiration,
            "tenor_days": tenor,
            "historical_observations": tuple(observations),
        })

    current_parameters = []
    output_records = []
    for expiration, tenor in zip(expirations, current_tenors):
        candidates = tuple(
            item for item in current["candidates"]
            if item[0].contract_key.expiration == expiration
        )
        wings = _tail_wings(candidates)
        dependency_atm = atm_by_tenor[tenor]
        atm_iv = dependency_atm["selected_atm_iv"]
        candidates_by_iv_id = {
            item[1].metadata.record_id: item for item in candidates
        }
        call_atm_candidate = candidates_by_iv_id.get(
            dependency_atm["selected_call_iv_record_id"]
        )
        put_atm_candidate = candidates_by_iv_id.get(
            dependency_atm["selected_put_iv_record_id"]
        )
        if call_atm_candidate is None or put_atm_candidate is None:
            raise ValueError(
                "dependency ATM selected records are absent from current universe"
            )
        if (
            call_atm_candidate[0].contract_key.option_type != "call"
            or put_atm_candidate[0].contract_key.option_type != "put"
            or _volatility_pair_key(
                call_atm_candidate[0].contract_key
            ) != _volatility_pair_key(
                put_atm_candidate[0].contract_key
            )
            or _exact_two_value_mean(
                call_atm_candidate[1].implied_volatility,
                put_atm_candidate[1].implied_volatility,
            ) != atm_iv
            or _exact_midpoint(
                current["underlying_quote"].bid_price,
                current["underlying_quote"].ask_price,
            ) != dependency_atm["underlying_midpoint"]
        ):
            raise ValueError(
                "dependency ATM evidence differs from the current universe"
            )
        metrics = _tail_skew_metrics(wings, atm_iv)
        history = historical_skews_by_tenor[tenor]
        percentile = _percentile(
            sum(
                value <= metrics["downside_25_delta_skew"]
                for value in history
            ),
            len(history),
        )
        current_parameters.append({
            "session_date": current["session_date"],
            "expiration": expiration,
            "tenor_days": tenor,
            "underlying_quote_record_id": (
                current["underlying_quote"].metadata.record_id
            ),
            "atm_iv": atm_iv,
            "atm_dependency_selected_call_iv_record_id": (
                dependency_atm["selected_call_iv_record_id"]
            ),
            "atm_dependency_selected_put_iv_record_id": (
                dependency_atm["selected_put_iv_record_id"]
            ),
            "candidate_contracts": tuple(
                _tail_candidate_parameters(candidate)
                for candidate in candidates
            ),
            "selected_put_25": _without_private_fields(wings["put_25"]),
            "selected_call_25": _without_private_fields(wings["call_25"]),
            "selected_put_10": _without_private_fields(wings["put_10"]),
            "selected_call_10": _without_private_fields(wings["call_10"]),
            **metrics,
            "skew_percentile": percentile,
            "historical_observation_count": len(history),
        })
        output_records.append(TailPricingSlice(
            underlying=current["underlying_key"].symbol,
            as_of_date=current["session_date"],
            expiration=expiration,
            atm_iv=_finite_float(atm_iv),
            put_25_delta_iv=_finite_float(
                wings["put_25"]["implied_volatility"]
            ),
            call_25_delta_iv=_finite_float(
                wings["call_25"]["implied_volatility"]
            ),
            put_10_delta_iv=_finite_float(
                wings["put_10"]["implied_volatility"]
            ),
            call_10_delta_iv=_finite_float(
                wings["call_10"]["implied_volatility"]
            ),
            skew_percentile=_finite_float(percentile),
            skew_history_lookback_observations=len(history),
            delta_methodology=delta_string,
        ))

    direct_records = current["records"] + tuple(
        selected_record
        for item in historical
        for selected_record in item["records"]
    )
    all_bindings = current["bindings"] + tuple(
        binding for item in historical for binding in item["bindings"]
    )
    parameters_json = canonicalize_lineage_parameters({
        "tail_output_architecture": "ordered_tail_pricing_slice_tuple",
        "candidate_universe": {
            "declared_complete": True,
            "scope": (
                "current_delta_and_historical_atm_and_delta_candidate_"
                "universes"
            ),
            "current_semantics": (
                "no_eligible_nearest_signed_delta_candidate_omitted"
            ),
            "historical_semantics": (
                "no_eligible_paired_atm_or_nearest_signed_delta_candidate_"
                "omitted"
            ),
        },
        "delta_convention": delta_declaration,
        "target_deltas": dict(_TAIL_TARGETS),
        "delta_point_selection_rule": "nearest_observed_signed_delta",
        "interpolation_rule": "none",
        "normalized_evidence": {
            "direct_inputs": _direct_normalized_evidence(
                direct_records, all_bindings
            ),
        },
        "delta_tie_rule": (
            "reject_equal_distance_or_remaining_economic_ambiguity"
        ),
        "same_contract_reuse_rule": (
            "reject_same_economic_contract_across_10_and_25_same_side"
        ),
        "atm_dependency": _tail_dependency_parameters(
            dependency_record, dependency_lineage, dependency_decoded
        ),
        "current_expiration_observations": tuple(current_parameters),
        "historical_expected_session_dates": (
            historical_expected_session_dates
        ),
        "historical_eod_semantics": {
            "declared": True,
            "methodology": historical_end_of_day_methodology,
            "sample_semantics": (
                "caller_declared_daily_eod_observation_sample"
            ),
            "scope": "every_historical_session_and_tenor_selection",
        },
        "historical_matched_tenor_rule": (
            "expiration_minus_session_date_calendar_days_equals_current_tenor"
        ),
        "historical_observations_by_tenor": tuple(
            historical_parameters_by_tenor
        ),
        "current_skew_formula": "put_25_delta_iv_minus_atm_iv",
        "skew_percentile_formula": (
            "inclusive_count_historical_downside_25_skew_lte_current_"
            "divided_by_count"
        ),
        "skew_term_structure_ordering": (
            "ascending_days_to_expiration_then_expiration"
        ),
        "analytics_methodology": {
            "iv_model_name": analytics_methodology[0],
            "iv_model_version": analytics_methodology[1],
            "iv_rate_input_description": analytics_methodology[2],
            "iv_dividend_input_description": analytics_methodology[3],
            "iv_unit_convention": analytics_methodology[4],
            "greeks_model_name": analytics_methodology[5],
            "greeks_model_version": analytics_methodology[6],
            "greeks_rate_input_description": analytics_methodology[7],
            "greeks_dividend_input_description": analytics_methodology[8],
            "greeks_unit_convention": analytics_methodology[9],
        },
        "float_conversion_rule": (
            "convert_only_final_tail_pricing_record_values_to_finite_float"
        ),
        "volatility_unit": "annualized_decimal_ratio",
    })
    inputs = _union_lineage_inputs(dependency_lineage.inputs, direct_records)
    flags = {
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    propagated = {
        CalculationQualityFlag.ADJUSTED_INPUT_USED,
        CalculationQualityFlag.CORRECTION_SELECTED,
        CalculationQualityFlag.COMPOSITE_INPUT_USED,
        CalculationQualityFlag.INTERPOLATED,
    }
    flags.update(
        flag for flag in dependency_lineage.quality_flags
        if flag in propagated
    )
    if any(
        binding.correction_selection.reason_codes == (
            CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,
        )
        for binding in all_bindings
    ):
        flags.add(CalculationQualityFlag.CORRECTION_SELECTED)
    if any(
        record.metadata.record_origin is DataOrigin.SYSTEM_COMPOSITE
        for record in direct_records
    ):
        flags.add(CalculationQualityFlag.COMPOSITE_INPUT_USED)
    if any(
        NormalizationQualityFlag.INTERPOLATED in record.metadata.quality_flags
        for record in direct_records
    ):
        flags.add(CalculationQualityFlag.INTERPOLATED)
    flags.discard(CalculationQualityFlag.INCOMPLETE_INPUT_USED)
    lineage = CalculationLineage(
        calculation_id=normalized_id,
        calculation_type="tail_pricing",
        methodology_id=(
            "nearest-observed-delta-wing-tail-relative-pricing"
        ),
        methodology_version="v0.2",
        calculated_at=normalized_at,
        inputs=inputs,
        parameters_json=parameters_json,
        quality_flags=tuple(
            flag for flag in CalculationQualityFlag if flag in flags
        ),
    )
    return TailPricingTransformationResult(
        records=tuple(output_records),
        lineage=lineage,
    )


_SCENARIO_PRICING_PARAMETER_KEYS = {
    "output_architecture",
    "supported_structure_scope",
    "producer_identity",
    "producer_provenance",
    "pricing_methodology",
    "structure_identity",
    "leg_correspondence",
    "scenario_definitions",
    "scenario_ordering",
    "valuation_date_rules",
    "underlying_shock_rule",
    "iv_shock_rule",
    "base_underlying_evidence",
    "leg_iv_evidence",
    "contract_reference_evidence",
    "rate_methodology",
    "dividend_methodology",
    "exercise_and_settlement_support",
    "remaining_time_rule",
    "position_scaling_rule",
    "calculation_values",
    "float_conversion_rule",
    "limitations",
}
_SCENARIO_PRICING_PROPAGATED_FLAGS = (
    "adjusted_input_used",
    "correction_selected",
    "composite_input_used",
)
_SCENARIO_PRICING_REMAINING_TIME_RULE = (
    "expiration_minus_valuation_date_calendar_days"
)
_SCENARIO_PRICING_SCALING_RULE = (
    "per_underlying_unit_value_times_quantity_times_contract_multiplier"
)


def _scenario_pricing_string(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must have exact type str")
    if not value or value != value.strip():
        raise ValueError(f"{name} must be a nonempty canonical string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{name} must not contain a Unicode surrogate") from error
    return value


def _scenario_pricing_date(name: str, value: object) -> datetime.date:
    if type(value) is not datetime.date:
        raise TypeError(f"{name} must have exact type date")
    return value


def _scenario_pricing_datetime(
    name: str, value: object
) -> datetime.datetime:
    if type(value) is not datetime.datetime:
        raise TypeError(f"{name} must have exact type datetime")
    try:
        offset = value.utcoffset()
        if offset is None:
            raise ValueError(f"{name} must be timezone-aware")
        normalized = value.astimezone(datetime.timezone.utc)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} must support valid UTC conversion") from error
    return normalized


def _scenario_pricing_decimal(
    name: str, value: object, *, positive: bool = False
) -> decimal.Decimal:
    if type(value) is not decimal.Decimal:
        raise TypeError(f"{name} must have exact type Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    if not positive and value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return value


def _scenario_pricing_context() -> decimal.Context:
    context = decimal.Context(
        prec=34,
        rounding=decimal.ROUND_HALF_EVEN,
        Emin=decimal.MIN_EMIN,
        Emax=decimal.MAX_EMAX,
        capitals=1,
        clamp=0,
    )
    context.clear_flags()
    return context


def _scenario_pricing_multiply(
    *values: decimal.Decimal,
) -> decimal.Decimal:
    context = _scenario_pricing_context()
    result = decimal.Decimal(1)
    try:
        for value in values:
            result = context.multiply(result, value)
    except decimal.DecimalException as error:
        raise ValueError("scenario-pricing Decimal multiplication failed") from error
    if not result.is_finite():
        raise ValueError("scenario-pricing Decimal result must be finite")
    return result


def _scenario_pricing_sum(
    values: Tuple[decimal.Decimal, ...],
) -> decimal.Decimal:
    context = _scenario_pricing_context()
    result = decimal.Decimal(0)
    try:
        for value in values:
            result = context.add(result, value)
    except decimal.DecimalException as error:
        raise ValueError("scenario-pricing Decimal sum failed") from error
    if not result.is_finite():
        raise ValueError("scenario-pricing Decimal result must be finite")
    return result


def _scenario_pricing_ratio(value: object) -> decimal.Decimal:
    try:
        result = decimal.Decimal(str(value))
    except decimal.DecimalException as error:
        raise ValueError("scenario ratio must convert exactly to Decimal") from error
    if not result.is_finite():
        raise ValueError("scenario ratio must be finite")
    return result


def _scenario_pricing_shock(
    base: decimal.Decimal, ratio: object
) -> decimal.Decimal:
    context = _scenario_pricing_context()
    try:
        factor = context.add(decimal.Decimal(1), _scenario_pricing_ratio(ratio))
        result = context.multiply(base, factor)
    except decimal.DecimalException as error:
        raise ValueError("scenario shock calculation failed") from error
    if not result.is_finite():
        raise ValueError("scenario shock result must be finite")
    return result


def _scenario_pricing_leg_identity(leg: OptionLeg) -> dict:
    return {
        "underlying": leg.underlying,
        "option_type": leg.option_type,
        "strike": decimal.Decimal(str(leg.strike)),
        "expiration": leg.expiration,
        "quantity": leg.quantity,
        "contract_multiplier": leg.contract_multiplier,
    }


def _scenario_pricing_underlying_identity(key: UnderlyingKey) -> dict:
    return {
        "symbol": key.symbol,
        "listing_mic": key.listing_mic,
        "security_type": key.security_type.value,
        "currency": key.currency,
    }


def _scenario_pricing_contract_identity(key: OptionContractKey) -> dict:
    return {
        "underlying_key": _scenario_pricing_underlying_identity(
            key.underlying_key
        ),
        "expiration": key.expiration,
        "option_type": key.option_type,
        "strike": key.strike,
        "contract_multiplier": key.contract_multiplier,
        "currency": key.currency,
        "deliverable_id": key.deliverable_id,
    }


def _scenario_pricing_validate_leg_contract(
    leg: OptionLeg, contract_key: OptionContractKey
) -> None:
    if (
        contract_key.underlying_key.symbol != leg.underlying
        or contract_key.option_type != leg.option_type
        or contract_key.expiration != leg.expiration
        or contract_key.strike != decimal.Decimal(str(leg.strike))
        or contract_key.contract_multiplier != leg.contract_multiplier
    ):
        raise ValueError("contract_key must exactly correspond to leg")


@dataclass(frozen=True)
class ScenarioPricingMethodology:
    pricing_source_classification: str
    producer_name: str
    producer_version: str
    pricing_request_id: str
    pricing_payload_sha256: str
    producer_calculated_at: datetime.datetime
    pricing_model_name: str
    pricing_model_version: str
    supported_exercise_settlement_pairs: Tuple[Tuple[str, str], ...]
    settlement_treatment: str
    rate_source: str
    rate_curve_identity: str
    rate_effective_date: datetime.date
    rate_currency: str
    rate_remaining_tenor_treatment: str
    rate_compounding_conversion: str
    rate_day_count_convention: str
    rate_interpolation: str
    dividend_source: str
    dividend_treatment: str
    dividend_coverage_start_date: datetime.date
    dividend_coverage_end_date: datetime.date
    explicit_zero_dividend_assumption: bool
    volatility_surface_treatment: str
    skew_treatment: str
    term_treatment: str
    volatility_interpolation: str
    remaining_time_rule: str
    position_scaling_rule: str
    numerical_calculation_boundary: str
    limitations: str

    def __post_init__(self) -> None:
        string_fields = (
            "pricing_source_classification",
            "producer_name",
            "producer_version",
            "pricing_request_id",
            "pricing_payload_sha256",
            "pricing_model_name",
            "pricing_model_version",
            "settlement_treatment",
            "rate_source",
            "rate_curve_identity",
            "rate_currency",
            "rate_remaining_tenor_treatment",
            "rate_compounding_conversion",
            "rate_day_count_convention",
            "rate_interpolation",
            "dividend_source",
            "dividend_treatment",
            "volatility_surface_treatment",
            "skew_treatment",
            "term_treatment",
            "volatility_interpolation",
            "remaining_time_rule",
            "position_scaling_rule",
            "numerical_calculation_boundary",
            "limitations",
        )
        for name in string_fields:
            _scenario_pricing_string(name, getattr(self, name))
        if self.pricing_source_classification != "provider_calculated":
            raise ValueError(
                "pricing_source_classification must be provider_calculated"
            )
        if (
            len(self.pricing_payload_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.pricing_payload_sha256
            )
        ):
            raise ValueError(
                "pricing_payload_sha256 must be 64 lowercase hexadecimal characters"
            )
        producer_calculated_at = _scenario_pricing_datetime(
            "producer_calculated_at", self.producer_calculated_at
        )
        for name in (
            "rate_effective_date",
            "dividend_coverage_start_date",
            "dividend_coverage_end_date",
        ):
            _scenario_pricing_date(name, getattr(self, name))
        if self.dividend_coverage_start_date > self.dividend_coverage_end_date:
            raise ValueError("dividend coverage dates are reversed")
        if type(self.supported_exercise_settlement_pairs) is not tuple:
            raise TypeError(
                "supported_exercise_settlement_pairs must have exact type tuple"
            )
        pairs = self.supported_exercise_settlement_pairs
        if not pairs:
            raise ValueError(
                "supported_exercise_settlement_pairs must not be empty"
            )
        for pair in pairs:
            if type(pair) is not tuple:
                raise TypeError("every supported pair must have exact type tuple")
            if len(pair) != 2:
                raise ValueError("every supported pair must contain two strings")
            _scenario_pricing_string("exercise_style", pair[0])
            _scenario_pricing_string("settlement_type", pair[1])
        if len(set(pairs)) != len(pairs):
            raise ValueError("supported pairs must be unique")
        if pairs != tuple(sorted(pairs)):
            raise ValueError("supported pairs must be in strict canonical order")
        if type(self.explicit_zero_dividend_assumption) is not bool:
            raise TypeError(
                "explicit_zero_dividend_assumption must have exact type bool"
            )
        reserved = "explicit_zero_dividend_assumption"
        if self.explicit_zero_dividend_assumption:
            if (
                self.dividend_source != reserved
                or self.dividend_treatment != reserved
            ):
                raise ValueError(
                    "explicit zero dividends require matching source and treatment"
                )
        elif (
            self.dividend_source == reserved
            or self.dividend_treatment == reserved
        ):
            raise ValueError(
                "reserved zero-dividend methodology requires a true assumption"
            )
        if self.rate_currency != "USD":
            raise ValueError("rate_currency must be USD")
        if self.remaining_time_rule != _SCENARIO_PRICING_REMAINING_TIME_RULE:
            raise ValueError("remaining_time_rule is unsupported")
        if self.position_scaling_rule != _SCENARIO_PRICING_SCALING_RULE:
            raise ValueError("position_scaling_rule is unsupported")
        object.__setattr__(
            self, "producer_calculated_at", producer_calculated_at
        )


@dataclass(frozen=True)
class ScenarioPricingLegCalculation:
    leg: OptionLeg
    contract_key: OptionContractKey
    base_iv: decimal.Decimal
    shocked_iv: decimal.Decimal
    remaining_calendar_days: int
    per_underlying_unit_option_value: decimal.Decimal
    total_leg_value: decimal.Decimal
    exercise_style: str
    settlement_type: str
    implied_volatility_record_id: str
    contract_reference_record_id: str

    def __post_init__(self) -> None:
        if type(self.leg) is not OptionLeg:
            raise TypeError("leg must have exact type OptionLeg")
        if type(self.contract_key) is not OptionContractKey:
            raise TypeError("contract_key must have exact type OptionContractKey")
        if type(self.contract_key.underlying_key) is not UnderlyingKey:
            raise TypeError(
                "contract_key.underlying_key must have exact type UnderlyingKey"
            )
        _scenario_pricing_validate_leg_contract(self.leg, self.contract_key)
        _scenario_pricing_decimal("base_iv", self.base_iv, positive=True)
        _scenario_pricing_decimal("shocked_iv", self.shocked_iv, positive=True)
        _scenario_pricing_decimal(
            "per_underlying_unit_option_value",
            self.per_underlying_unit_option_value,
        )
        _scenario_pricing_decimal("total_leg_value", self.total_leg_value)
        if type(self.remaining_calendar_days) is not int:
            raise TypeError(
                "remaining_calendar_days must have exact type int excluding bool"
            )
        if self.remaining_calendar_days <= 0:
            raise ValueError("remaining_calendar_days must be positive")
        for name in (
            "exercise_style",
            "settlement_type",
            "implied_volatility_record_id",
            "contract_reference_record_id",
        ):
            _scenario_pricing_string(name, getattr(self, name))
        if (
            self.implied_volatility_record_id
            == self.contract_reference_record_id
        ):
            raise ValueError("IV and contract-reference record IDs must differ")
        expected = _scenario_pricing_multiply(
            self.per_underlying_unit_option_value,
            decimal.Decimal(self.leg.quantity),
            decimal.Decimal(self.leg.contract_multiplier),
        )
        if self.total_leg_value != expected:
            raise ValueError("total_leg_value does not match exact leg scaling")


def _scenario_pricing_valuation_date(
    structure: OptionStructure,
    as_of_date: datetime.date,
    scenario: Scenario,
) -> datetime.date:
    if scenario.valuation_time == "expiration":
        raise ValueError("expiration scenarios are unsupported by 3C.7f1")
    try:
        if scenario.valuation_time == "immediate":
            return as_of_date
        if scenario.valuation_time == "days_forward":
            return as_of_date + datetime.timedelta(days=scenario.days_forward)
        if scenario.valuation_time == "holding_horizon":
            return as_of_date + datetime.timedelta(
                days=structure.expected_holding_days
            )
    except OverflowError as error:
        raise ValueError("scenario valuation date is outside the date range") from error
    raise ValueError("scenario valuation_time is unsupported")


@dataclass(frozen=True)
class NonExpirationScenarioPricingCalculation:
    structure: OptionStructure
    as_of_date: datetime.date
    scenario: Scenario
    valuation_date: datetime.date
    base_underlying_price: decimal.Decimal
    shocked_underlying_price: decimal.Decimal
    underlying_quote_record_id: str
    leg_calculations: Tuple[ScenarioPricingLegCalculation, ...]
    estimated_gross_position_value: decimal.Decimal
    pricing_methodology: ScenarioPricingMethodology

    def __post_init__(self) -> None:
        if type(self.structure) is not OptionStructure:
            raise TypeError("structure must have exact type OptionStructure")
        if type(self.scenario) is not Scenario:
            raise TypeError("scenario must have exact type Scenario")
        if type(self.pricing_methodology) is not ScenarioPricingMethodology:
            raise TypeError(
                "pricing_methodology must have exact type "
                "ScenarioPricingMethodology"
            )
        _scenario_pricing_date("as_of_date", self.as_of_date)
        _scenario_pricing_date("valuation_date", self.valuation_date)
        _scenario_pricing_decimal(
            "base_underlying_price", self.base_underlying_price, positive=True
        )
        _scenario_pricing_decimal(
            "shocked_underlying_price",
            self.shocked_underlying_price,
            positive=True,
        )
        _scenario_pricing_decimal(
            "estimated_gross_position_value",
            self.estimated_gross_position_value,
        )
        _scenario_pricing_string(
            "underlying_quote_record_id", self.underlying_quote_record_id
        )
        if type(self.leg_calculations) is not tuple:
            raise TypeError("leg_calculations must have exact type tuple")
        if any(
            type(item) is not ScenarioPricingLegCalculation
            for item in self.leg_calculations
        ):
            raise TypeError(
                "every leg calculation must have exact public record type"
            )
        if self.structure.structure_type not in {
            "long_call", "long_put", "long_straddle"
        }:
            raise ValueError("structure type is unsupported")
        legs = self.structure.legs
        if len(legs) not in {1, 2} or any(
            type(leg) is not OptionLeg for leg in legs
        ):
            raise ValueError("structure must contain one or two exact option legs")
        if (
            len({leg.underlying for leg in legs}) != 1
            or len({leg.expiration for leg in legs}) != 1
            or any(leg.quantity <= 0 or leg.contract_multiplier <= 0 for leg in legs)
        ):
            raise ValueError("structure legs must share identity and be positive")
        if len(legs) == 2:
            call = next((leg for leg in legs if leg.option_type == "call"), None)
            put = next((leg for leg in legs if leg.option_type == "put"), None)
            if (
                call is None
                or put is None
                or call.strike != put.strike
                or call.expiration != put.expiration
                or call.underlying != put.underlying
                or call.quantity != put.quantity
                or call.contract_multiplier != put.contract_multiplier
            ):
                raise ValueError("two-leg structure violates exact straddle rules")
        expiration = legs[0].expiration
        if self.as_of_date >= expiration:
            raise ValueError("as_of_date must precede expiration")
        required_valuation_date = _scenario_pricing_valuation_date(
            self.structure, self.as_of_date, self.scenario
        )
        if required_valuation_date >= expiration:
            raise ValueError("resolved valuation date must precede expiration")
        if self.valuation_date != required_valuation_date:
            raise ValueError("valuation_date does not match scenario rule")
        expected_underlying = _scenario_pricing_shock(
            self.base_underlying_price, self.scenario.underlying_move
        )
        if self.shocked_underlying_price != expected_underlying:
            raise ValueError(
                "shocked_underlying_price does not match the scenario shock"
            )
        if len(self.leg_calculations) != len(legs):
            raise ValueError("leg calculation count must equal structure leg count")
        if tuple(item.leg for item in self.leg_calculations) != legs:
            raise ValueError(
                "leg calculations must already follow exact structure-leg order"
            )
        if len(set(legs)) != len(legs):
            raise ValueError("each structure leg must occur exactly once")
        contract_keys = tuple(
            item.contract_key for item in self.leg_calculations
        )
        if len(set(contract_keys)) != len(contract_keys):
            raise ValueError("each contract key must occur exactly once")
        underlying_keys = tuple(
            contract.underlying_key for contract in contract_keys
        )
        if any(
            type(key) is not UnderlyingKey or key != underlying_keys[0]
            for key in underlying_keys
        ):
            raise ValueError(
                "all leg contract keys must share one complete UnderlyingKey"
            )
        record_ids = [self.underlying_quote_record_id]
        for item in self.leg_calculations:
            if item.remaining_calendar_days != (
                item.leg.expiration - self.valuation_date
            ).days:
                raise ValueError("remaining_calendar_days is inconsistent")
            expected_iv = _scenario_pricing_shock(
                item.base_iv, self.scenario.iv_change
            )
            if item.shocked_iv != expected_iv:
                raise ValueError("shocked_iv does not match the scenario shock")
            if (
                item.exercise_style,
                item.settlement_type,
            ) not in self.pricing_methodology.supported_exercise_settlement_pairs:
                raise ValueError("exercise and settlement pair is unsupported")
            record_ids.extend((
                item.implied_volatility_record_id,
                item.contract_reference_record_id,
            ))
        if len(set(record_ids)) != len(record_ids):
            raise ValueError("all normalized evidence record IDs must be unique")
        expected_total = _scenario_pricing_sum(
            tuple(item.total_leg_value for item in self.leg_calculations)
        )
        if self.estimated_gross_position_value != expected_total:
            raise ValueError(
                "estimated_gross_position_value must equal the exact leg sum"
            )
        methodology = self.pricing_methodology
        if methodology.rate_effective_date != self.as_of_date:
            raise ValueError("rate_effective_date must equal as_of_date")
        if (
            methodology.dividend_coverage_start_date > self.as_of_date
            or methodology.dividend_coverage_end_date < expiration
        ):
            raise ValueError("dividend methodology does not cover the calculation")


def _scenario_pricing_methodology_sections(
    methodology: ScenarioPricingMethodology,
) -> Tuple[dict, dict, dict, dict, dict, tuple]:
    producer_identity = {
        "producer_name": methodology.producer_name,
        "producer_version": methodology.producer_version,
    }
    producer_provenance = {
        "pricing_source_classification": (
            methodology.pricing_source_classification
        ),
        "pricing_request_id": methodology.pricing_request_id,
        "pricing_payload_sha256": methodology.pricing_payload_sha256,
        "producer_calculated_at": methodology.producer_calculated_at,
    }
    pricing_methodology = {
        "pricing_model_name": methodology.pricing_model_name,
        "pricing_model_version": methodology.pricing_model_version,
        "settlement_treatment": methodology.settlement_treatment,
        "volatility_surface_treatment": (
            methodology.volatility_surface_treatment
        ),
        "skew_treatment": methodology.skew_treatment,
        "term_treatment": methodology.term_treatment,
        "volatility_interpolation": methodology.volatility_interpolation,
        "numerical_calculation_boundary": (
            methodology.numerical_calculation_boundary
        ),
    }
    rate_methodology = {
        "rate_source": methodology.rate_source,
        "rate_curve_identity": methodology.rate_curve_identity,
        "rate_effective_date": methodology.rate_effective_date,
        "rate_currency": methodology.rate_currency,
        "rate_remaining_tenor_treatment": (
            methodology.rate_remaining_tenor_treatment
        ),
        "rate_compounding_conversion": (
            methodology.rate_compounding_conversion
        ),
        "rate_day_count_convention": methodology.rate_day_count_convention,
        "rate_interpolation": methodology.rate_interpolation,
    }
    dividend_methodology = {
        "dividend_source": methodology.dividend_source,
        "dividend_treatment": methodology.dividend_treatment,
        "dividend_coverage_start_date": (
            methodology.dividend_coverage_start_date
        ),
        "dividend_coverage_end_date": methodology.dividend_coverage_end_date,
        "explicit_zero_dividend_assumption": (
            methodology.explicit_zero_dividend_assumption
        ),
    }
    return (
        producer_identity,
        producer_provenance,
        pricing_methodology,
        rate_methodology,
        dividend_methodology,
        methodology.supported_exercise_settlement_pairs,
    )


def _scenario_pricing_structure_identity(
    record: NonExpirationScenarioPricingCalculation,
) -> dict:
    structure = record.structure
    return {
        "structure_type": structure.structure_type,
        "legs": tuple(
            _scenario_pricing_leg_identity(leg) for leg in structure.legs
        ),
        "assumed_portfolio_value": decimal.Decimal(
            str(structure.assumed_portfolio_value)
        ),
        "expected_holding_days": structure.expected_holding_days,
        "as_of_date": record.as_of_date,
        "shared_expiration": structure.legs[0].expiration,
    }


def _scenario_pricing_leg_correspondence(
    record: NonExpirationScenarioPricingCalculation,
) -> tuple:
    return tuple({
        "leg": _scenario_pricing_leg_identity(item.leg),
        "contract_key": _scenario_pricing_contract_identity(
            item.contract_key
        ),
        "base_iv": item.base_iv,
        "exercise_style": item.exercise_style,
        "settlement_type": item.settlement_type,
        "implied_volatility_record_id": (
            item.implied_volatility_record_id
        ),
        "contract_reference_record_id": (
            item.contract_reference_record_id
        ),
    } for item in record.leg_calculations)


def _scenario_pricing_scenario_definition(
    record: NonExpirationScenarioPricingCalculation,
) -> dict:
    return {
        "valuation_time": record.scenario.valuation_time,
        "days_forward": record.scenario.days_forward,
        "underlying_move": _scenario_pricing_ratio(
            record.scenario.underlying_move
        ),
        "iv_change": _scenario_pricing_ratio(record.scenario.iv_change),
    }


def _scenario_pricing_calculation_values(
    record: NonExpirationScenarioPricingCalculation,
) -> dict:
    return {
        "scenario": _scenario_pricing_scenario_definition(record),
        "valuation_date": record.valuation_date,
        "base_underlying_price": record.base_underlying_price,
        "shocked_underlying_price": record.shocked_underlying_price,
        "underlying_quote_record_id": record.underlying_quote_record_id,
        "leg_values": tuple({
            "leg": _scenario_pricing_leg_identity(item.leg),
            "contract_key": _scenario_pricing_contract_identity(
                item.contract_key
            ),
            "base_iv": item.base_iv,
            "shocked_iv": item.shocked_iv,
            "remaining_calendar_days": item.remaining_calendar_days,
            "per_underlying_unit_option_value": (
                item.per_underlying_unit_option_value
            ),
            "total_leg_value": item.total_leg_value,
        } for item in record.leg_calculations),
        "estimated_gross_position_value": (
            record.estimated_gross_position_value
        ),
    }


def _decode_scenario_pricing_parameters(parameters_json: str) -> dict:
    def reject_float(_value: str) -> object:
        raise ValueError("3C.7f1 parameters must not contain JSON floats")

    def reject_constant(_value: str) -> object:
        raise ValueError("3C.7f1 parameters must not contain constants")

    def unique_object(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("3C.7f1 parameters contain a duplicate key")
            result[key] = value
        return result

    try:
        raw = json.loads(
            parameters_json,
            parse_float=reject_float,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError("3C.7f1 parameters_json is invalid") from error

    def decode(value: object) -> object:
        if value is None or type(value) in (bool, int, str):
            return value
        if type(value) is list:
            return tuple(decode(item) for item in value)
        if type(value) is not dict or len(value) != 1:
            raise ValueError("3C.7f1 parameters use unsupported JSON")
        tag, payload = next(iter(value.items()))
        if tag == "$map":
            if type(payload) is not list:
                raise ValueError("$map payload must be a list")
            result = {}
            for pair in payload:
                if (
                    type(pair) is not list
                    or len(pair) != 2
                    or type(pair[0]) is not str
                    or pair[0] in result
                ):
                    raise ValueError("$map entries must have unique string keys")
                result[pair[0]] = decode(pair[1])
            return result
        if tag == "$list":
            if type(payload) is not list:
                raise ValueError("$list payload must be a list")
            return tuple(decode(item) for item in payload)
        if tag == "$decimal":
            if type(payload) is not str:
                raise ValueError("$decimal payload must be a string")
            try:
                result = decimal.Decimal(payload)
            except decimal.InvalidOperation as error:
                raise ValueError("$decimal payload is invalid") from error
            if not result.is_finite():
                raise ValueError("$decimal payload must be finite")
            return result
        if tag == "$date":
            if type(payload) is not str:
                raise ValueError("$date payload must be a string")
            try:
                result = datetime.date.fromisoformat(payload)
            except ValueError as error:
                raise ValueError("$date payload is invalid") from error
            if result.isoformat() != payload:
                raise ValueError("$date payload is noncanonical")
            return result
        if tag == "$datetime":
            if type(payload) is not str or not payload.endswith("Z"):
                raise ValueError("$datetime payload must be canonical UTC")
            try:
                result = datetime.datetime.fromisoformat(
                    payload[:-1] + "+00:00"
                )
            except ValueError as error:
                raise ValueError("$datetime payload is invalid") from error
            return result
        raise ValueError("3C.7f1 parameters contain an unknown tag")

    decoded = decode(raw)
    if type(decoded) is not dict:
        raise ValueError("3C.7f1 parameters root must be a tagged map")
    if set(decoded) != _SCENARIO_PRICING_PARAMETER_KEYS:
        raise ValueError("3C.7f1 parameters have the wrong exact 23-key schema")
    try:
        if canonicalize_lineage_parameters(decoded) != parameters_json:
            raise ValueError("3C.7f1 parameters are not byte-canonical")
    except (TypeError, ValueError) as error:
        raise ValueError("3C.7f1 parameters are not canonical") from error
    return decoded


def _scenario_pricing_evidence_common(
    value: object, expected_record_id: str
) -> Tuple[datetime.datetime, Tuple[str, ...], Tuple[str, ...]]:
    if type(value) is not dict:
        raise TypeError("normalized evidence must have exact type dict")
    record_id = _scenario_pricing_string("record_id", value.get("record_id"))
    if record_id != expected_record_id:
        raise ValueError("normalized evidence record_id is inconsistent")
    normalized_at = _scenario_pricing_datetime(
        "normalized_at", value.get("normalized_at")
    )
    source_ids = value.get("source_ids")
    if type(source_ids) is not tuple:
        raise TypeError("source_ids must have exact type tuple")
    if not source_ids:
        raise ValueError("source_ids must not be empty")
    for source_id in source_ids:
        _scenario_pricing_string("source_id", source_id)
    if len(set(source_ids)) != len(source_ids) or source_ids != tuple(
        sorted(source_ids)
    ):
        raise ValueError("source_ids must be unique and canonically ordered")
    flags = value.get("propagated_quality_flags")
    if type(flags) is not tuple:
        raise TypeError("propagated_quality_flags must have exact type tuple")
    if any(type(flag) is not str for flag in flags):
        raise TypeError("every propagated quality flag must have exact type str")
    expected_order = tuple(
        flag for flag in _SCENARIO_PRICING_PROPAGATED_FLAGS if flag in flags
    )
    if (
        flags != expected_order
        or len(set(flags)) != len(flags)
        or any(flag not in _SCENARIO_PRICING_PROPAGATED_FLAGS for flag in flags)
    ):
        raise ValueError("propagated quality flags are not a canonical subset")
    return normalized_at, source_ids, flags


def _scenario_pricing_require_correspondence(
    name: str, actual: object, expected: object
) -> None:
    expected_type = type(expected)
    if expected_type is dict:
        if type(actual) is not dict:
            raise TypeError(f"{name} must have exact type dict")
        if set(actual) != set(expected):
            raise ValueError(f"{name} has the wrong exact schema")
        for key in expected:
            _scenario_pricing_require_correspondence(
                f"{name}.{key}", actual[key], expected[key]
            )
        return
    if expected_type is tuple:
        if type(actual) is not tuple:
            raise TypeError(f"{name} must have exact type tuple")
        if len(actual) != len(expected):
            raise ValueError(f"{name} has the wrong tuple length")
        for index, (actual_item, expected_item) in enumerate(
            zip(actual, expected)
        ):
            _scenario_pricing_require_correspondence(
                f"{name}[{index}]", actual_item, expected_item
            )
        return
    if type(actual) is not expected_type:
        raise TypeError(
            f"{name} must have exact type {expected_type.__name__}"
        )
    if actual != expected:
        raise ValueError(f"{name} does not match the public records")


def _scenario_pricing_validate_evidence(
    decoded: dict,
    records: Tuple[NonExpirationScenarioPricingCalculation, ...],
    lineage: CalculationLineage,
) -> Tuple[str, ...]:
    common = records[0]
    underlying = decoded["base_underlying_evidence"]
    underlying_keys = {
        "record_id",
        "normalized_at",
        "source_ids",
        "propagated_quality_flags",
        "underlying_key",
        "session_date",
        "bid_price",
        "ask_price",
        "midpoint_formula",
        "base_underlying_price",
    }
    if type(underlying) is not dict or set(underlying) != underlying_keys:
        raise ValueError("base_underlying_evidence has the wrong exact schema")
    _scenario_pricing_evidence_common(
        underlying, common.underlying_quote_record_id
    )
    _scenario_pricing_require_correspondence(
        "base_underlying_evidence.underlying_key",
        underlying["underlying_key"],
        _scenario_pricing_underlying_identity(
            common.leg_calculations[0].contract_key.underlying_key
        ),
    )
    _scenario_pricing_require_correspondence(
        "base_underlying_evidence.session_date",
        underlying["session_date"],
        common.as_of_date,
    )
    _scenario_pricing_require_correspondence(
        "base_underlying_evidence.midpoint_formula",
        underlying["midpoint_formula"],
        "bid_price_plus_ask_price_divided_by_2",
    )
    base_evidence_price = _scenario_pricing_decimal(
        "base_underlying_evidence.base_underlying_price",
        underlying["base_underlying_price"],
        positive=True,
    )
    if base_evidence_price != common.base_underlying_price:
        raise ValueError("base underlying evidence price is inconsistent")
    bid = _scenario_pricing_decimal("bid_price", underlying["bid_price"])
    ask = _scenario_pricing_decimal(
        "ask_price", underlying["ask_price"], positive=True
    )
    midpoint_context = _scenario_pricing_context()
    try:
        midpoint = midpoint_context.divide(
            midpoint_context.add(bid, ask), decimal.Decimal(2)
        )
    except decimal.DecimalException as error:
        raise ValueError("underlying midpoint calculation failed") from error
    if common.base_underlying_price != midpoint:
        raise ValueError("base underlying price must equal quote midpoint")

    iv_entries = decoded["leg_iv_evidence"]
    reference_entries = decoded["contract_reference_evidence"]
    if type(iv_entries) is not tuple or type(reference_entries) is not tuple:
        raise TypeError("leg evidence containers must have exact type tuple")
    if (
        len(iv_entries) != len(common.leg_calculations)
        or len(reference_entries) != len(common.leg_calculations)
    ):
        raise ValueError("leg evidence counts must equal the structure leg count")
    iv_keys = {
        "record_id",
        "normalized_at",
        "source_ids",
        "propagated_quality_flags",
        "leg",
        "contract_key",
        "session_date",
        "implied_volatility",
        "model_name",
        "model_version",
        "rate_input_description",
        "dividend_input_description",
        "unit_convention",
    }
    reference_keys = {
        "record_id",
        "normalized_at",
        "source_ids",
        "propagated_quality_flags",
        "leg",
        "contract_key",
        "exercise_style",
        "settlement_type",
    }
    record_ids = [common.underlying_quote_record_id]
    for calculation, iv, reference in zip(
        common.leg_calculations, iv_entries, reference_entries
    ):
        if type(iv) is not dict or set(iv) != iv_keys:
            raise ValueError("leg_iv_evidence has the wrong exact schema")
        if type(reference) is not dict or set(reference) != reference_keys:
            raise ValueError(
                "contract_reference_evidence has the wrong exact schema"
            )
        _scenario_pricing_evidence_common(
            iv, calculation.implied_volatility_record_id
        )
        _scenario_pricing_evidence_common(
            reference, calculation.contract_reference_record_id
        )
        for name in (
            "model_name",
            "model_version",
            "rate_input_description",
            "dividend_input_description",
        ):
            _scenario_pricing_string(name, iv[name])
        for name, actual, expected in (
            ("leg", iv["leg"], _scenario_pricing_leg_identity(calculation.leg)),
            (
                "contract_key",
                iv["contract_key"],
                _scenario_pricing_contract_identity(calculation.contract_key),
            ),
            ("session_date", iv["session_date"], common.as_of_date),
            ("unit_convention", iv["unit_convention"], "annualized_decimal_ratio"),
        ):
            _scenario_pricing_require_correspondence(
                f"leg_iv_evidence.{name}", actual, expected
            )
        evidence_iv = _scenario_pricing_decimal(
            "leg_iv_evidence.implied_volatility",
            iv["implied_volatility"],
            positive=True,
        )
        if evidence_iv != calculation.base_iv:
            raise ValueError("leg IV evidence value is inconsistent")
        for name, actual, expected in (
            (
                "leg",
                reference["leg"],
                _scenario_pricing_leg_identity(calculation.leg),
            ),
            (
                "contract_key",
                reference["contract_key"],
                _scenario_pricing_contract_identity(calculation.contract_key),
            ),
            (
                "exercise_style",
                reference["exercise_style"],
                calculation.exercise_style,
            ),
            (
                "settlement_type",
                reference["settlement_type"],
                calculation.settlement_type,
            ),
        ):
            _scenario_pricing_require_correspondence(
                f"contract_reference_evidence.{name}", actual, expected
            )
        record_ids.extend((
            calculation.implied_volatility_record_id,
            calculation.contract_reference_record_id,
        ))

    references = {item.record_id: item for item in lineage.inputs}
    if set(references) != set(record_ids):
        raise ValueError("lineage inputs must equal exact disclosed evidence IDs")
    for evidence in (underlying,) + iv_entries + reference_entries:
        reference = references[evidence["record_id"]]
        if (
            evidence["normalized_at"] != reference.normalized_at
            or evidence["source_ids"] != reference.source_ids
        ):
            raise ValueError("normalized evidence differs from lineage input")
        if evidence["normalized_at"] > common.pricing_methodology.producer_calculated_at:
            raise ValueError("input normalization must not follow producer time")
    return tuple(
        flag
        for evidence in (underlying,) + iv_entries + reference_entries
        for flag in evidence["propagated_quality_flags"]
    )


def _scenario_pricing_expected_fixed_parameters(
    records: Tuple[NonExpirationScenarioPricingCalculation, ...],
) -> dict:
    common = records[0]
    (
        producer_identity,
        producer_provenance,
        pricing_methodology,
        rate_methodology,
        dividend_methodology,
        supported_pairs,
    ) = _scenario_pricing_methodology_sections(common.pricing_methodology)
    return {
        "output_architecture": {
            "record_type": "NonExpirationScenarioPricingCalculation",
            "records_container": "ordered_tuple",
            "lineage_scope": "shared_batch",
            "construction_boundary": (
                "authoritative_producer_direct_construction"
            ),
        },
        "supported_structure_scope": {
            "structure_types": (
                "long_call", "long_put", "long_straddle"
            ),
            "long_only": True,
            "common_expiration": True,
            "maximum_leg_count": 2,
        },
        "producer_identity": producer_identity,
        "producer_provenance": producer_provenance,
        "pricing_methodology": pricing_methodology,
        "structure_identity": _scenario_pricing_structure_identity(common),
        "leg_correspondence": _scenario_pricing_leg_correspondence(common),
        "scenario_definitions": tuple(
            _scenario_pricing_scenario_definition(record)
            for record in records
        ),
        "scenario_ordering": {
            "keys": (
                "valuation_date",
                "valuation_time_rank",
                "days_forward",
                "underlying_move_decimal",
                "iv_change_decimal",
            ),
            "valuation_time_rank": {
                "immediate": 0,
                "days_forward": 1,
                "holding_horizon": 2,
            },
        },
        "valuation_date_rules": {
            "immediate": "as_of_date",
            "days_forward": "as_of_date_plus_days_forward_calendar_days",
            "holding_horizon": (
                "as_of_date_plus_expected_holding_days_calendar_days"
            ),
            "expiration": "rejected",
        },
        "underlying_shock_rule": (
            "base_underlying_price_times_one_plus_decimal_string_"
            "underlying_move"
        ),
        "iv_shock_rule": (
            "base_iv_times_one_plus_decimal_string_iv_change"
        ),
        "rate_methodology": rate_methodology,
        "dividend_methodology": dividend_methodology,
        "exercise_and_settlement_support": supported_pairs,
        "remaining_time_rule": _SCENARIO_PRICING_REMAINING_TIME_RULE,
        "position_scaling_rule": _SCENARIO_PRICING_SCALING_RULE,
        "calculation_values": tuple(
            _scenario_pricing_calculation_values(record)
            for record in records
        ),
        "float_conversion_rule": (
            "none_all_3c7f1_economic_values_remain_decimal"
        ),
        "limitations": common.pricing_methodology.limitations,
    }


@dataclass(frozen=True)
class ScenarioPricingCalculationResult:
    records: Tuple[NonExpirationScenarioPricingCalculation, ...]
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.records) is not tuple:
            raise TypeError("records must have exact type tuple")
        if not self.records:
            raise ValueError("records must not be empty")
        if any(
            type(record) is not NonExpirationScenarioPricingCalculation
            for record in self.records
        ):
            raise TypeError(
                "every record must have exact type "
                "NonExpirationScenarioPricingCalculation"
            )
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")
        first = self.records[0]
        common_fields = (
            "structure",
            "as_of_date",
            "base_underlying_price",
            "underlying_quote_record_id",
            "pricing_methodology",
        )
        if any(
            any(getattr(record, name) != getattr(first, name)
                for name in common_fields)
            for record in self.records[1:]
        ):
            raise ValueError("scenario records must share one batch identity")
        base_leg_tuple = tuple(
            (
                item.leg,
                item.contract_key,
                item.base_iv,
                item.exercise_style,
                item.settlement_type,
                item.implied_volatility_record_id,
                item.contract_reference_record_id,
            )
            for item in first.leg_calculations
        )
        for record in self.records[1:]:
            candidate = tuple(
                (
                    item.leg,
                    item.contract_key,
                    item.base_iv,
                    item.exercise_style,
                    item.settlement_type,
                    item.implied_volatility_record_id,
                    item.contract_reference_record_id,
                )
                for item in record.leg_calculations
            )
            if candidate != base_leg_tuple:
                raise ValueError("per-leg base evidence must be common to the batch")
        identities = tuple(
            (
                record.scenario.valuation_time,
                record.scenario.days_forward,
                _scenario_pricing_ratio(record.scenario.underlying_move),
                _scenario_pricing_ratio(record.scenario.iv_change),
            )
            for record in self.records
        )
        if len(set(identities)) != len(identities):
            raise ValueError("scenario identities must be unique")
        ranks = {"immediate": 0, "days_forward": 1, "holding_horizon": 2}
        ordering = tuple(
            (
                record.valuation_date,
                ranks[record.scenario.valuation_time],
                record.scenario.days_forward,
                _scenario_pricing_ratio(record.scenario.underlying_move),
                _scenario_pricing_ratio(record.scenario.iv_change),
            )
            for record in self.records
        )
        if ordering != tuple(sorted(ordering)):
            raise ValueError("scenario records must be in strict canonical order")
        lineage = self.lineage
        if (
            lineage.calculation_type != "nonexpiration_scenario_pricing"
            or lineage.methodology_id
            != "authoritative-provider-option-scenario-pricing-evidence"
            or lineage.methodology_version != "v0.1"
        ):
            raise ValueError("lineage calculation identity is invalid")
        if lineage.calculated_at < first.pricing_methodology.producer_calculated_at:
            raise ValueError("lineage time must not precede producer time")
        decoded = _decode_scenario_pricing_parameters(lineage.parameters_json)
        expected = _scenario_pricing_expected_fixed_parameters(self.records)
        for name, value in expected.items():
            _scenario_pricing_require_correspondence(
                name, decoded[name], value
            )
        propagated_flags = _scenario_pricing_validate_evidence(
            decoded, self.records, lineage
        )
        expected_flags = {
            CalculationQualityFlag.ANNUALIZED,
            CalculationQualityFlag.ASSUMPTION_APPLIED,
        }
        propagated_map = {
            "adjusted_input_used": CalculationQualityFlag.ADJUSTED_INPUT_USED,
            "correction_selected": CalculationQualityFlag.CORRECTION_SELECTED,
            "composite_input_used": CalculationQualityFlag.COMPOSITE_INPUT_USED,
        }
        expected_flags.update(
            propagated_map[value] for value in set(propagated_flags)
        )
        methodology = first.pricing_methodology
        if (
            methodology.rate_interpolation != "none"
            or methodology.volatility_interpolation != "none"
        ):
            expected_flags.add(CalculationQualityFlag.INTERPOLATED)
        expected_tuple = tuple(
            flag for flag in CalculationQualityFlag if flag in expected_flags
        )
        if lineage.quality_flags != expected_tuple:
            raise ValueError(
                "lineage quality flags must equal the complete expected set"
            )


_TAIL_PRICING_PARAMETER_KEYS = {
    "tail_output_architecture",
    "candidate_universe",
    "delta_convention",
    "target_deltas",
    "delta_point_selection_rule",
    "interpolation_rule",
    "normalized_evidence",
    "delta_tie_rule",
    "same_contract_reuse_rule",
    "atm_dependency",
    "current_expiration_observations",
    "historical_expected_session_dates",
    "historical_eod_semantics",
    "historical_matched_tenor_rule",
    "historical_observations_by_tenor",
    "current_skew_formula",
    "skew_percentile_formula",
    "skew_term_structure_ordering",
    "analytics_methodology",
    "float_conversion_rule",
    "volatility_unit",
}
_TAIL_CANDIDATE_PARAMETER_KEYS = {
    "option_type",
    "strike",
    "contract_multiplier",
    "currency",
    "deliverable_id",
    "quote_record_id",
    "iv_record_id",
    "greeks_record_id",
    "contract_reference_record_id",
    "implied_volatility",
    "signed_delta",
    "distance_to_25_target",
    "distance_to_10_target",
}
_TAIL_SELECTED_OPTION_PARAMETER_KEYS = {
    "target_delta",
    "selected_delta",
    "distance",
    "option_type",
    "strike",
    "contract_multiplier",
    "currency",
    "deliverable_id",
    "quote_record_id",
    "iv_record_id",
    "greeks_record_id",
    "contract_reference_record_id",
    "implied_volatility",
}
_TAIL_CURRENT_OBSERVATION_PARAMETER_KEYS = {
    "session_date",
    "expiration",
    "tenor_days",
    "underlying_quote_record_id",
    "atm_iv",
    "atm_dependency_selected_call_iv_record_id",
    "atm_dependency_selected_put_iv_record_id",
    "candidate_contracts",
    "selected_put_25",
    "selected_call_25",
    "selected_put_10",
    "selected_call_10",
    "downside_25_delta_skew",
    "upside_25_delta_skew",
    "downside_wing_curvature",
    "upside_wing_curvature",
    "skew_percentile",
    "historical_observation_count",
}
_TAIL_HISTORICAL_OBSERVATION_PARAMETER_KEYS = {
    "session_date",
    "expiration",
    "underlying_quote_record_id",
    "candidate_contracts",
    "selected_paired_atm_evidence",
    "atm_iv",
    "selected_put_25",
    "selected_call_25",
    "selected_put_10",
    "selected_call_10",
    "put_25_delta_iv",
    "call_25_delta_iv",
    "put_10_delta_iv",
    "call_10_delta_iv",
    "downside_25_delta_skew",
    "upside_25_delta_skew",
    "downside_wing_curvature",
    "upside_wing_curvature",
}
_TAIL_ATM_OBSERVATION_PARAMETER_KEYS = {
    "candidate_pairs",
    "expiration",
    "selected_atm_iv",
    "selected_call_iv_record_id",
    "selected_put_iv_record_id",
    "selected_strike",
    "session_date",
    "tenor_days",
    "underlying_midpoint",
    "underlying_quote_record_id",
}
_TAIL_ATM_CANDIDATE_PAIR_PARAMETER_KEYS = {
    "strike",
    "contract_multiplier",
    "currency",
    "deliverable_id",
    "call_quote_record_id",
    "call_iv_record_id",
    "call_contract_reference_record_id",
    "put_quote_record_id",
    "put_iv_record_id",
    "put_contract_reference_record_id",
    "call_implied_volatility",
    "put_implied_volatility",
    "paired_implied_volatility",
    "distance_to_underlying_midpoint",
}
_TAIL_SELECTED_ATM_PARAMETER_KEYS = {
    "underlying_midpoint",
    "candidate_pairs",
    "selected_strike",
    "selected_call_iv_record_id",
    "selected_put_iv_record_id",
    "selected_atm_iv",
}
_TAIL_ATM_DEPENDENCY_PARAMETER_KEYS = {
    "calculation_id",
    "calculation_type",
    "methodology_id",
    "methodology_version",
    "calculated_at",
    "parameters_json",
    "quality_flags",
    "inputs",
    "underlying",
    "as_of_date",
    "reference_tenor_days",
    "iv_percentile_float_repr",
    "historical_observation_count",
    "historical_median_atm_iv_float_repr",
    "matched_realized_volatility_float_repr",
    "matched_realized_window_days",
    "term_points",
    "current_atm_observations",
    "historical_atm_observations",
}
_SCENARIO_VALUATION_PARAMETER_KEYS = {
    "output_architecture",
    "supported_structure_scope",
    "scenario_declaration",
    "scenario_grid_semantics",
    "scenario_ordering",
    "valuation_date_rules",
    "underlying_shock_rule",
    "iv_shock_rule",
    "structure_costs_dependency",
    "tail_pricing_dependency",
    "scenario_pricing_dependency",
    "cross_dependency_consistency",
    "base_underlying_rule",
    "base_iv_rule",
    "nonexpiration_valuation_rule",
    "expiration_payoff_rule",
    "entry_cost_rule",
    "exit_cost_assumptions",
    "net_liquidation_rule",
    "bounded_loss_rule",
    "record_methodology_disclosure",
    "calculation_values",
    "lineage_union_rule",
    "float_conversion_rule",
    "limitations",
}
_SCENARIO_METHODOLOGY_KEYS = {
    "schema_version",
    "valuation_source",
    "scenario_identity",
    "structure_costs_dependency",
    "tail_pricing_dependency",
    "scenario_pricing_dependency",
    "provider_disclosure",
    "nonexpiration_rule",
    "expiration_rule",
    "base_underlying_source",
    "base_iv_source",
    "entry_cost_rule",
    "exit_cost_rule",
    "float_conversion_rule",
    "limitations",
}
_SCENARIO_GRID_MOVES = tuple(
    decimal.Decimal(value)
    for value in ("-0.20", "-0.10", "-0.05", "0", "0.05", "0.10", "0.20")
)
_SCENARIO_GRID_IV_CHANGES = tuple(
    decimal.Decimal(value) for value in ("-0.20", "0", "0.20", "0.50")
)
_SCENARIO_TIME_RANK = {
    "immediate": 0,
    "days_forward": 1,
    "holding_horizon": 2,
    "expiration": 3,
}
_SCENARIO_VALUATION_PROPAGATED_FLAGS = {
    CalculationQualityFlag.INTERPOLATED,
    CalculationQualityFlag.ADJUSTED_INPUT_USED,
    CalculationQualityFlag.CORRECTION_SELECTED,
    CalculationQualityFlag.COMPOSITE_INPUT_USED,
}


def _decode_strict_tagged_parameters(
    parameters_json: object, expected_keys: set, label: str
) -> dict:
    if type(parameters_json) is not str:
        raise TypeError(f"{label} parameters_json must have exact type str")

    def reject_float(_value: str) -> object:
        raise ValueError(f"{label} parameters must not contain JSON floats")

    def reject_constant(_value: str) -> object:
        raise ValueError(f"{label} parameters contain a nonfinite constant")

    def unique_object(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} parameters contain a duplicate key")
            result[key] = value
        return result

    try:
        raw = json.loads(
            parameters_json,
            parse_float=reject_float,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError(f"{label} parameters_json is invalid") from error

    def decode(value: object) -> object:
        if value is None or type(value) in (bool, int, str):
            return value
        if type(value) is list:
            return tuple(decode(item) for item in value)
        if type(value) is not dict or len(value) != 1:
            raise ValueError(f"{label} parameters use unsupported JSON")
        tag, payload = next(iter(value.items()))
        if tag == "$map":
            if type(payload) is not list:
                raise ValueError("$map payload must be a list")
            result = {}
            for pair in payload:
                if (
                    type(pair) is not list
                    or len(pair) != 2
                    or type(pair[0]) is not str
                    or pair[0] in result
                ):
                    raise ValueError("$map entries must have unique string keys")
                result[pair[0]] = decode(pair[1])
            return result
        if tag == "$list":
            if type(payload) is not list:
                raise ValueError("$list payload must be a list")
            return tuple(decode(item) for item in payload)
        if tag == "$decimal":
            if type(payload) is not str:
                raise ValueError("$decimal payload must be a string")
            try:
                result = decimal.Decimal(payload)
            except decimal.InvalidOperation as error:
                raise ValueError("$decimal payload is invalid") from error
            if not result.is_finite():
                raise ValueError("$decimal payload must be finite")
            return result
        if tag == "$date":
            if type(payload) is not str:
                raise ValueError("$date payload must be a string")
            try:
                result = datetime.date.fromisoformat(payload)
            except ValueError as error:
                raise ValueError("$date payload is invalid") from error
            if result.isoformat() != payload:
                raise ValueError("$date payload is noncanonical")
            return result
        if tag == "$datetime":
            if type(payload) is not str or not payload.endswith("Z"):
                raise ValueError("$datetime payload must be canonical UTC")
            try:
                result = datetime.datetime.fromisoformat(
                    payload[:-1] + "+00:00"
                )
            except ValueError as error:
                raise ValueError("$datetime payload is invalid") from error
            return result
        raise ValueError(f"{label} parameters contain an unknown tag")

    decoded = decode(raw)
    if type(decoded) is not dict:
        raise ValueError(f"{label} parameters root must be a tagged map")
    if set(decoded) != expected_keys:
        raise ValueError(f"{label} parameters have the wrong exact schema")
    try:
        if canonicalize_lineage_parameters(decoded) != parameters_json:
            raise ValueError(f"{label} parameters are not byte-canonical")
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} parameters are not canonical") from error
    return decoded


def _tail_schema_map(
    value: object, keys: set, label: str
) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"{label} has the wrong exact schema")
    return value


def _tail_schema_tuple(value: object, label: str) -> tuple:
    if type(value) is not tuple:
        raise ValueError(f"{label} must have exact type tuple")
    return value


def _tail_schema_string(value: object, label: str) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
    ):
        raise ValueError(f"{label} must be a canonical nonempty string")
    return value


def _tail_schema_decimal(
    value: object, label: str, *, positive: bool = False
) -> decimal.Decimal:
    if (
        type(value) is not decimal.Decimal
        or not value.is_finite()
        or (positive and value <= 0)
    ):
        raise ValueError(f"{label} must be an exact finite Decimal")
    return value


def _tail_schema_candidate_order_key(candidate: dict) -> tuple:
    return (
        candidate["option_type"],
        candidate["strike"],
        candidate["contract_multiplier"],
        candidate["currency"],
        (
            (0, "")
            if candidate["deliverable_id"] is None
            else (1, candidate["deliverable_id"])
        ),
    )


def _validate_tail_candidate_parameter(
    value: object, label: str
) -> dict:
    candidate = _tail_schema_map(
        value, _TAIL_CANDIDATE_PARAMETER_KEYS, label
    )
    if candidate["option_type"] not in {"call", "put"}:
        raise ValueError(f"{label} option_type is invalid")
    _tail_schema_decimal(candidate["strike"], f"{label} strike", positive=True)
    if (
        type(candidate["contract_multiplier"]) is not int
        or candidate["contract_multiplier"] <= 0
    ):
        raise ValueError(f"{label} contract_multiplier is invalid")
    _tail_schema_string(candidate["currency"], f"{label} currency")
    if (
        candidate["deliverable_id"] is not None
        and type(candidate["deliverable_id"]) is not str
    ):
        raise ValueError(f"{label} deliverable_id is invalid")
    for key in (
        "quote_record_id",
        "iv_record_id",
        "greeks_record_id",
        "contract_reference_record_id",
    ):
        _tail_schema_string(candidate[key], f"{label} {key}")
    _tail_schema_decimal(
        candidate["implied_volatility"],
        f"{label} implied_volatility",
        positive=True,
    )
    signed_delta = _tail_schema_decimal(
        candidate["signed_delta"], f"{label} signed_delta"
    )
    if (
        candidate["option_type"] == "call"
        and not decimal.Decimal("0") < signed_delta < decimal.Decimal("1")
    ) or (
        candidate["option_type"] == "put"
        and not decimal.Decimal("-1") < signed_delta < decimal.Decimal("0")
    ):
        raise ValueError(f"{label} signed_delta has the wrong sign")
    for key in ("distance_to_25_target", "distance_to_10_target"):
        distance = _tail_schema_decimal(candidate[key], f"{label} {key}")
        if distance < 0:
            raise ValueError(f"{label} {key} must be nonnegative")
    return candidate


def _validate_tail_selected_option_parameter(
    value: object,
    candidates: tuple,
    name: str,
    label: str,
) -> dict:
    selected = _tail_schema_map(
        value, _TAIL_SELECTED_OPTION_PARAMETER_KEYS, label
    )
    expected_side = "call" if name.startswith("call") else "put"
    expected_target = _TAIL_TARGETS[name]
    if (
        selected["option_type"] != expected_side
        or selected["target_delta"] != expected_target
    ):
        raise ValueError(f"{label} target identity is invalid")
    _tail_schema_decimal(selected["strike"], f"{label} strike", positive=True)
    if (
        type(selected["contract_multiplier"]) is not int
        or selected["contract_multiplier"] <= 0
    ):
        raise ValueError(f"{label} contract_multiplier is invalid")
    _tail_schema_string(selected["currency"], f"{label} currency")
    if (
        selected["deliverable_id"] is not None
        and type(selected["deliverable_id"]) is not str
    ):
        raise ValueError(f"{label} deliverable_id is invalid")
    for key in (
        "quote_record_id",
        "iv_record_id",
        "greeks_record_id",
        "contract_reference_record_id",
    ):
        _tail_schema_string(selected[key], f"{label} {key}")
    selected_delta = _tail_schema_decimal(
        selected["selected_delta"], f"{label} selected_delta"
    )
    _tail_schema_decimal(
        selected["implied_volatility"],
        f"{label} implied_volatility",
        positive=True,
    )
    distance = _tail_schema_decimal(
        selected["distance"], f"{label} distance"
    )
    if distance != (selected_delta - expected_target).copy_abs():
        raise ValueError(f"{label} distance is inconsistent")
    candidate_matches = tuple(
        candidate
        for candidate in candidates
        if all(
            candidate[candidate_key] == selected[selected_key]
            for candidate_key, selected_key in (
                ("option_type", "option_type"),
                ("strike", "strike"),
                ("contract_multiplier", "contract_multiplier"),
                ("currency", "currency"),
                ("deliverable_id", "deliverable_id"),
                ("quote_record_id", "quote_record_id"),
                ("iv_record_id", "iv_record_id"),
                ("greeks_record_id", "greeks_record_id"),
                (
                    "contract_reference_record_id",
                    "contract_reference_record_id",
                ),
                ("implied_volatility", "implied_volatility"),
                ("signed_delta", "selected_delta"),
            )
        )
    )
    if len(candidate_matches) != 1:
        raise ValueError(f"{label} must match exactly one candidate")
    distance_key = (
        "distance_to_25_target"
        if name.endswith("_25")
        else "distance_to_10_target"
    )
    if candidate_matches[0][distance_key] != distance:
        raise ValueError(f"{label} candidate distance is inconsistent")
    return selected


def _validate_tail_atm_candidate_pair(
    value: object, label: str
) -> dict:
    pair = _tail_schema_map(
        value, _TAIL_ATM_CANDIDATE_PAIR_PARAMETER_KEYS, label
    )
    _tail_schema_decimal(pair["strike"], f"{label} strike", positive=True)
    if (
        type(pair["contract_multiplier"]) is not int
        or pair["contract_multiplier"] <= 0
    ):
        raise ValueError(f"{label} contract_multiplier is invalid")
    _tail_schema_string(pair["currency"], f"{label} currency")
    if (
        pair["deliverable_id"] is not None
        and type(pair["deliverable_id"]) is not str
    ):
        raise ValueError(f"{label} deliverable_id is invalid")
    for key in (
        "call_quote_record_id",
        "call_iv_record_id",
        "call_contract_reference_record_id",
        "put_quote_record_id",
        "put_iv_record_id",
        "put_contract_reference_record_id",
    ):
        _tail_schema_string(pair[key], f"{label} {key}")
    call_iv = _tail_schema_decimal(
        pair["call_implied_volatility"],
        f"{label} call_implied_volatility",
        positive=True,
    )
    put_iv = _tail_schema_decimal(
        pair["put_implied_volatility"],
        f"{label} put_implied_volatility",
        positive=True,
    )
    paired_iv = _tail_schema_decimal(
        pair["paired_implied_volatility"],
        f"{label} paired_implied_volatility",
        positive=True,
    )
    distance = _tail_schema_decimal(
        pair["distance_to_underlying_midpoint"],
        f"{label} distance_to_underlying_midpoint",
    )
    if distance < 0 or paired_iv != _exact_two_value_mean(call_iv, put_iv):
        raise ValueError(f"{label} calculated values are inconsistent")
    return pair


def _tail_atm_pair_order_key(pair: dict) -> tuple:
    return (
        pair["strike"],
        pair["contract_multiplier"],
        pair["currency"],
        (
            (0, "")
            if pair["deliverable_id"] is None
            else (1, pair["deliverable_id"])
        ),
        pair["call_iv_record_id"],
        pair["put_iv_record_id"],
    )


def _validate_tail_selected_atm_parameter(
    value: object, label: str
) -> dict:
    selected = _tail_schema_map(
        value, _TAIL_SELECTED_ATM_PARAMETER_KEYS, label
    )
    midpoint = _tail_schema_decimal(
        selected["underlying_midpoint"],
        f"{label} underlying_midpoint",
        positive=True,
    )
    pairs = _tail_schema_tuple(
        selected["candidate_pairs"], f"{label} candidate_pairs"
    )
    if not pairs:
        raise ValueError(f"{label} candidate_pairs must not be empty")
    verified_pairs = tuple(
        _validate_tail_atm_candidate_pair(
            pair, f"{label} candidate_pairs[{index}]"
        )
        for index, pair in enumerate(pairs)
    )
    ordering = tuple(
        _tail_atm_pair_order_key(pair) for pair in verified_pairs
    )
    if any(
        current <= previous
        for previous, current in zip(ordering, ordering[1:])
    ):
        raise ValueError(f"{label} candidate_pairs ordering is invalid")
    selected_strike = _tail_schema_decimal(
        selected["selected_strike"],
        f"{label} selected_strike",
        positive=True,
    )
    selected_atm_iv = _tail_schema_decimal(
        selected["selected_atm_iv"],
        f"{label} selected_atm_iv",
        positive=True,
    )
    call_id = _tail_schema_string(
        selected["selected_call_iv_record_id"],
        f"{label} selected_call_iv_record_id",
    )
    put_id = _tail_schema_string(
        selected["selected_put_iv_record_id"],
        f"{label} selected_put_iv_record_id",
    )
    matches = tuple(
        pair for pair in verified_pairs
        if (
            pair["strike"] == selected_strike
            and pair["call_iv_record_id"] == call_id
            and pair["put_iv_record_id"] == put_id
            and pair["paired_implied_volatility"] == selected_atm_iv
            and pair["distance_to_underlying_midpoint"]
            == (pair["strike"] - midpoint).copy_abs()
        )
    )
    if len(matches) != 1:
        raise ValueError(f"{label} selection does not match one candidate pair")
    return selected


def _validate_tail_atm_observation_parameter(
    value: object, label: str
) -> dict:
    observation = _tail_schema_map(
        value, _TAIL_ATM_OBSERVATION_PARAMETER_KEYS, label
    )
    session_date = observation["session_date"]
    expiration = observation["expiration"]
    if (
        type(session_date) is not datetime.date
        or type(expiration) is not datetime.date
        or type(observation["tenor_days"]) is not int
        or observation["tenor_days"] <= 0
        or (expiration - session_date).days != observation["tenor_days"]
    ):
        raise ValueError(f"{label} date and tenor fields are invalid")
    _tail_schema_string(
        observation["underlying_quote_record_id"],
        f"{label} underlying_quote_record_id",
    )
    selected = _validate_tail_selected_atm_parameter(
        {
            key: observation[key]
            for key in _TAIL_SELECTED_ATM_PARAMETER_KEYS
        },
        label,
    )
    if (
        selected["selected_strike"] != observation["selected_strike"]
        or selected["selected_atm_iv"] != observation["selected_atm_iv"]
    ):
        raise ValueError(f"{label} ATM selection is inconsistent")
    return observation


def _validate_tail_candidate_collection(
    value: object, label: str
) -> tuple:
    candidates = _tail_schema_tuple(value, label)
    if not candidates:
        raise ValueError(f"{label} must not be empty")
    verified = tuple(
        _validate_tail_candidate_parameter(
            candidate, f"{label}[{index}]"
        )
        for index, candidate in enumerate(candidates)
    )
    ordering = tuple(
        _tail_schema_candidate_order_key(candidate)
        for candidate in verified
    )
    if any(
        current <= previous
        for previous, current in zip(ordering, ordering[1:])
    ):
        raise ValueError(f"{label} ordering is invalid")
    return verified


def _validate_tail_wing_selections(
    observation: dict, candidates: tuple, label: str
) -> dict:
    selections = {
        name: _validate_tail_selected_option_parameter(
            observation[f"selected_{name}"],
            candidates,
            name,
            f"{label} selected_{name}",
        )
        for name in ("put_25", "call_25", "put_10", "call_10")
    }
    for side in ("put", "call"):
        selected_25 = selections[f"{side}_25"]
        selected_10 = selections[f"{side}_10"]
        if (
            selected_25["iv_record_id"] == selected_10["iv_record_id"]
            or not (
                selected_10["selected_delta"].copy_abs()
                < selected_25["selected_delta"].copy_abs()
            )
        ):
            raise ValueError(
                f"{label} same-side selections are inconsistent"
            )
    return selections


def _validate_tail_pricing_parameter_schema(decoded: dict) -> None:
    _validate_direct_evidence(
        decoded["normalized_evidence"], {
            "underlying_quote", "option_quote",
            "option_implied_volatility", "option_greeks",
            "option_contract_reference",
        }, "TailPricing normalized_evidence",
    )
    candidate_universe = _tail_schema_map(
        decoded["candidate_universe"],
        {
            "declared_complete",
            "scope",
            "current_semantics",
            "historical_semantics",
        },
        "TailPricing candidate_universe",
    )
    if candidate_universe != {
        "declared_complete": True,
        "scope": (
            "current_delta_and_historical_atm_and_delta_candidate_universes"
        ),
        "current_semantics": (
            "no_eligible_nearest_signed_delta_candidate_omitted"
        ),
        "historical_semantics": (
            "no_eligible_paired_atm_or_nearest_signed_delta_candidate_omitted"
        ),
    }:
        raise ValueError("TailPricing candidate_universe is invalid")

    _validate_delta_methodology(decoded["delta_convention"])
    if decoded["target_deltas"] != dict(_TAIL_TARGETS):
        raise ValueError("TailPricing target_deltas are invalid")
    fixed_values = {
        "tail_output_architecture": "ordered_tail_pricing_slice_tuple",
        "delta_point_selection_rule": "nearest_observed_signed_delta",
        "interpolation_rule": "none",
        "delta_tie_rule": (
            "reject_equal_distance_or_remaining_economic_ambiguity"
        ),
        "same_contract_reuse_rule": (
            "reject_same_economic_contract_across_10_and_25_same_side"
        ),
        "historical_matched_tenor_rule": (
            "expiration_minus_session_date_calendar_days_equals_current_tenor"
        ),
        "current_skew_formula": "put_25_delta_iv_minus_atm_iv",
        "skew_percentile_formula": (
            "inclusive_count_historical_downside_25_skew_lte_current_"
            "divided_by_count"
        ),
        "skew_term_structure_ordering": (
            "ascending_days_to_expiration_then_expiration"
        ),
        "float_conversion_rule": (
            "convert_only_final_tail_pricing_record_values_to_finite_float"
        ),
        "volatility_unit": "annualized_decimal_ratio",
    }
    if any(decoded[key] != value for key, value in fixed_values.items()):
        raise ValueError("TailPricing fixed methodology is invalid")

    eod = _tail_schema_map(
        decoded["historical_eod_semantics"],
        {"declared", "methodology", "sample_semantics", "scope"},
        "TailPricing historical_eod_semantics",
    )
    if (
        eod["declared"] is not True
        or eod["sample_semantics"]
        != "caller_declared_daily_eod_observation_sample"
        or eod["scope"]
        != "every_historical_session_and_tenor_selection"
    ):
        raise ValueError("TailPricing historical EOD semantics are invalid")
    _tail_schema_string(
        eod["methodology"], "TailPricing historical EOD methodology"
    )

    analytics = _tail_schema_map(
        decoded["analytics_methodology"],
        {
            "iv_model_name",
            "iv_model_version",
            "iv_rate_input_description",
            "iv_dividend_input_description",
            "iv_unit_convention",
            "greeks_model_name",
            "greeks_model_version",
            "greeks_rate_input_description",
            "greeks_dividend_input_description",
            "greeks_unit_convention",
        },
        "TailPricing analytics_methodology",
    )
    for key, value in analytics.items():
        _tail_schema_string(
            value, f"TailPricing analytics_methodology {key}"
        )
    if analytics["iv_unit_convention"] != "annualized_decimal_ratio":
        raise ValueError("TailPricing IV unit convention is invalid")

    expected_dates = _tail_schema_tuple(
        decoded["historical_expected_session_dates"],
        "TailPricing historical_expected_session_dates",
    )
    if (
        not expected_dates
        or any(type(item) is not datetime.date for item in expected_dates)
        or tuple(sorted(set(expected_dates))) != expected_dates
    ):
        raise ValueError(
            "TailPricing historical expected dates are not canonical"
        )

    atm_dependency = _tail_schema_map(
        decoded["atm_dependency"],
        _TAIL_ATM_DEPENDENCY_PARAMETER_KEYS,
        "TailPricing atm_dependency",
    )
    for key in (
        "calculation_id",
        "parameters_json",
        "underlying",
    ):
        _tail_schema_string(
            atm_dependency[key], f"TailPricing atm_dependency {key}"
        )
    if (
        atm_dependency["calculation_type"] != "volatility_environment"
        or atm_dependency["methodology_id"]
        != "paired-atm-volatility-environment"
        or atm_dependency["methodology_version"] != "v0.2"
        or type(atm_dependency["calculated_at"]) is not datetime.datetime
        or atm_dependency["calculated_at"].utcoffset()
        != datetime.timedelta(0)
        or type(atm_dependency["as_of_date"]) is not datetime.date
        or type(atm_dependency["reference_tenor_days"]) is not int
        or atm_dependency["reference_tenor_days"] <= 0
        or type(atm_dependency["historical_observation_count"]) is not int
        or atm_dependency["historical_observation_count"] <= 0
        or type(atm_dependency["matched_realized_window_days"]) is not int
        or atm_dependency["matched_realized_window_days"] <= 0
    ):
        raise ValueError("TailPricing atm_dependency fields are invalid")
    _validate_volatility_fixed_methodology(
        _decode_volatility_parameters(atm_dependency["parameters_json"])
    )
    dependency_inputs = _tail_schema_tuple(
        atm_dependency["inputs"],
        "TailPricing atm_dependency inputs",
    )
    flags = _tail_schema_tuple(
        atm_dependency["quality_flags"],
        "TailPricing atm_dependency quality_flags",
    )
    if (
        not dependency_inputs
        or any(type(item) is not str or not item for item in flags)
        or len(set(flags)) != len(flags)
    ):
        raise ValueError("TailPricing atm_dependency IDs or flags are invalid")
    for index, item in enumerate(dependency_inputs):
        _complete_reference_from_mapping(
            item, f"TailPricing atm_dependency inputs[{index}]"
        )
    dependency_ids = tuple(item["record_id"] for item in dependency_inputs)
    if tuple(sorted(dependency_ids)) != dependency_ids or len(set(dependency_ids)) != len(dependency_ids):
        raise ValueError("TailPricing atm_dependency inputs are noncanonical")
    for key in (
        "iv_percentile_float_repr",
        "historical_median_atm_iv_float_repr",
        "matched_realized_volatility_float_repr",
    ):
        _tail_schema_string(
            atm_dependency[key], f"TailPricing atm_dependency {key}"
        )
    term_points = _tail_schema_tuple(
        atm_dependency["term_points"],
        "TailPricing atm_dependency term_points",
    )
    term_tenors = []
    for index, point_value in enumerate(term_points):
        point = _tail_schema_map(
            point_value,
            {"tenor_days", "atm_iv_float_repr"},
            f"TailPricing atm_dependency term_points[{index}]",
        )
        if (
            type(point["tenor_days"]) is not int
            or point["tenor_days"] <= 0
        ):
            raise ValueError("TailPricing term-point tenor is invalid")
        _tail_schema_string(
            point["atm_iv_float_repr"],
            "TailPricing term-point ATM IV representation",
        )
        term_tenors.append(point["tenor_days"])
    if tuple(sorted(set(term_tenors))) != tuple(term_tenors):
        raise ValueError("TailPricing term-point ordering is invalid")

    current_atm = _tail_schema_tuple(
        atm_dependency["current_atm_observations"],
        "TailPricing atm_dependency current_atm_observations",
    )
    current_atm = tuple(
        _validate_tail_atm_observation_parameter(
            item, f"TailPricing current ATM observation[{index}]"
        )
        for index, item in enumerate(current_atm)
    )
    if tuple(item["tenor_days"] for item in current_atm) != tuple(term_tenors):
        raise ValueError("TailPricing current ATM ordering is invalid")
    historical_atm = _tail_schema_tuple(
        atm_dependency["historical_atm_observations"],
        "TailPricing atm_dependency historical_atm_observations",
    )
    historical_atm = tuple(
        _validate_tail_atm_observation_parameter(
            item, f"TailPricing historical ATM observation[{index}]"
        )
        for index, item in enumerate(historical_atm)
    )
    if (
        len(historical_atm)
        != atm_dependency["historical_observation_count"]
        or tuple(item["session_date"] for item in historical_atm)
        != expected_dates
        or any(
            item["tenor_days"]
            != atm_dependency["reference_tenor_days"]
            for item in historical_atm
        )
    ):
        raise ValueError("TailPricing historical ATM observations are invalid")

    current = _tail_schema_tuple(
        decoded["current_expiration_observations"],
        "TailPricing current_expiration_observations",
    )
    if not current:
        raise ValueError(
            "TailPricing current_expiration_observations must not be empty"
        )
    current_order = []
    current_by_tenor = {}
    for index, item_value in enumerate(current):
        label = f"TailPricing current observation[{index}]"
        observation = _tail_schema_map(
            item_value, _TAIL_CURRENT_OBSERVATION_PARAMETER_KEYS, label
        )
        if (
            type(observation["session_date"]) is not datetime.date
            or type(observation["expiration"]) is not datetime.date
            or type(observation["tenor_days"]) is not int
            or observation["tenor_days"] <= 0
            or (
                observation["expiration"] - observation["session_date"]
            ).days != observation["tenor_days"]
            or type(observation["historical_observation_count"]) is not int
            or observation["historical_observation_count"]
            != len(expected_dates)
        ):
            raise ValueError(f"{label} date or count fields are invalid")
        _tail_schema_string(
            observation["underlying_quote_record_id"],
            f"{label} underlying_quote_record_id",
        )
        candidates = _validate_tail_candidate_collection(
            observation["candidate_contracts"],
            f"{label} candidate_contracts",
        )
        selections = _validate_tail_wing_selections(
            observation, candidates, label
        )
        for key in (
            "atm_iv",
            "downside_25_delta_skew",
            "upside_25_delta_skew",
            "downside_wing_curvature",
            "upside_wing_curvature",
            "skew_percentile",
        ):
            _tail_schema_decimal(observation[key], f"{label} {key}")
        for key in (
            "atm_dependency_selected_call_iv_record_id",
            "atm_dependency_selected_put_iv_record_id",
        ):
            _tail_schema_string(observation[key], f"{label} {key}")
        expected_metrics = _tail_skew_metrics(
            {
                name: selections[name]
                for name in ("put_25", "call_25", "put_10", "call_10")
            },
            observation["atm_iv"],
        )
        if any(
            observation[key] != value
            for key, value in expected_metrics.items()
        ):
            raise ValueError(f"{label} tail metrics are inconsistent")
        current_order.append(
            (observation["tenor_days"], observation["expiration"])
        )
        if observation["tenor_days"] in current_by_tenor:
            raise ValueError("TailPricing current tenors must be unique")
        current_by_tenor[observation["tenor_days"]] = observation
    if tuple(sorted(current_order)) != tuple(current_order):
        raise ValueError("TailPricing current observation ordering is invalid")
    if tuple(current_by_tenor) != tuple(term_tenors):
        raise ValueError("TailPricing current observations differ from ATM term")
    for atm_item in current_atm:
        observation = current_by_tenor[atm_item["tenor_days"]]
        if (
            observation["session_date"] != atm_item["session_date"]
            or observation["expiration"] != atm_item["expiration"]
            or observation["atm_iv"] != atm_item["selected_atm_iv"]
            or observation["atm_dependency_selected_call_iv_record_id"]
            != atm_item["selected_call_iv_record_id"]
            or observation["atm_dependency_selected_put_iv_record_id"]
            != atm_item["selected_put_iv_record_id"]
        ):
            raise ValueError(
                "TailPricing current observations differ from ATM dependency"
            )

    historical_groups = _tail_schema_tuple(
        decoded["historical_observations_by_tenor"],
        "TailPricing historical_observations_by_tenor",
    )
    if len(historical_groups) != len(current):
        raise ValueError("TailPricing historical tenor cardinality is invalid")
    historical_atm_by_key = {
        (item["session_date"], item["tenor_days"]): item
        for item in historical_atm
    }
    group_order = []
    for group_index, group_value in enumerate(historical_groups):
        group_label = f"TailPricing historical tenor[{group_index}]"
        group = _tail_schema_map(
            group_value,
            {"current_expiration", "tenor_days", "historical_observations"},
            group_label,
        )
        if (
            type(group["current_expiration"]) is not datetime.date
            or type(group["tenor_days"]) is not int
            or group["tenor_days"] not in current_by_tenor
            or group["current_expiration"]
            != current_by_tenor[group["tenor_days"]]["expiration"]
        ):
            raise ValueError(f"{group_label} identity is invalid")
        entries = _tail_schema_tuple(
            group["historical_observations"],
            f"{group_label} historical_observations",
        )
        if len(entries) != len(expected_dates):
            raise ValueError(f"{group_label} cardinality is invalid")
        for entry_index, entry_value in enumerate(entries):
            label = f"{group_label} observation[{entry_index}]"
            observation = _tail_schema_map(
                entry_value,
                _TAIL_HISTORICAL_OBSERVATION_PARAMETER_KEYS,
                label,
            )
            if (
                type(observation["session_date"]) is not datetime.date
                or observation["session_date"] != expected_dates[entry_index]
                or type(observation["expiration"]) is not datetime.date
                or (
                    observation["expiration"] - observation["session_date"]
                ).days != group["tenor_days"]
            ):
                raise ValueError(f"{label} dates are invalid")
            _tail_schema_string(
                observation["underlying_quote_record_id"],
                f"{label} underlying_quote_record_id",
            )
            candidates = _validate_tail_candidate_collection(
                observation["candidate_contracts"],
                f"{label} candidate_contracts",
            )
            selections = _validate_tail_wing_selections(
                observation, candidates, label
            )
            selected_atm = _validate_tail_selected_atm_parameter(
                observation["selected_paired_atm_evidence"],
                f"{label} selected_paired_atm_evidence",
            )
            atm_item = historical_atm_by_key.get(
                (observation["session_date"], group["tenor_days"])
            )
            if (
                atm_item is not None
                and selected_atm
                != {
                    key: atm_item[key]
                    for key in _TAIL_SELECTED_ATM_PARAMETER_KEYS
                }
            ):
                raise ValueError(
                    f"{label} ATM evidence differs from dependency"
                )
            if observation["atm_iv"] != selected_atm["selected_atm_iv"]:
                raise ValueError(f"{label} ATM IV is inconsistent")
            for name in ("put_25", "call_25", "put_10", "call_10"):
                if (
                    observation[f"{name}_delta_iv"]
                    != selections[name]["implied_volatility"]
                ):
                    raise ValueError(f"{label} selected IV is inconsistent")
            for key in (
                "atm_iv",
                "put_25_delta_iv",
                "call_25_delta_iv",
                "put_10_delta_iv",
                "call_10_delta_iv",
                "downside_25_delta_skew",
                "upside_25_delta_skew",
                "downside_wing_curvature",
                "upside_wing_curvature",
            ):
                _tail_schema_decimal(observation[key], f"{label} {key}")
            expected_metrics = _tail_skew_metrics(
                {
                    name: selections[name]
                    for name in ("put_25", "call_25", "put_10", "call_10")
                },
                observation["atm_iv"],
            )
            if any(
                observation[key] != value
                for key, value in expected_metrics.items()
            ):
                raise ValueError(f"{label} tail metrics are inconsistent")
        group_order.append(
            (group["tenor_days"], group["current_expiration"])
        )
    if tuple(sorted(group_order)) != tuple(group_order):
        raise ValueError("TailPricing historical tenor ordering is invalid")


def _decode_tail_pricing_parameters(parameters_json: object) -> dict:
    decoded = _decode_strict_tagged_parameters(
        parameters_json, _TAIL_PRICING_PARAMETER_KEYS, "3C.7e"
    )
    _validate_tail_pricing_parameter_schema(decoded)
    return decoded


def _decode_scenario_valuation_parameters(parameters_json: object) -> dict:
    return _decode_strict_tagged_parameters(
        parameters_json, _SCENARIO_VALUATION_PARAMETER_KEYS, "3C.7f2"
    )


def _scenario_identity(scenario: Scenario) -> dict:
    return {
        "valuation_time": scenario.valuation_time,
        "days_forward": scenario.days_forward,
        "underlying_move": decimal.Decimal(str(scenario.underlying_move)),
        "iv_change": decimal.Decimal(str(scenario.iv_change)),
    }


def _scenario_identity_tuple(scenario: Scenario) -> tuple:
    identity = _scenario_identity(scenario)
    return (
        identity["valuation_time"],
        identity["days_forward"],
        identity["underlying_move"],
        identity["iv_change"],
    )


def _scenario_valuation_date(
    structure: OptionStructure,
    as_of_date: datetime.date,
    scenario: Scenario,
) -> datetime.date:
    try:
        if scenario.valuation_time == "immediate":
            return as_of_date
        if scenario.valuation_time == "days_forward":
            return as_of_date + datetime.timedelta(days=scenario.days_forward)
        if scenario.valuation_time == "holding_horizon":
            return as_of_date + datetime.timedelta(
                days=structure.expected_holding_days
            )
        if scenario.valuation_time == "expiration":
            return structure.legs[0].expiration
    except OverflowError as error:
        raise ValueError("scenario valuation date is outside the date range") from error
    raise ValueError("scenario valuation_time is unsupported")


def _scenario_order_key(
    structure: OptionStructure,
    as_of_date: datetime.date,
    scenario: Scenario,
) -> tuple:
    return (
        _scenario_valuation_date(structure, as_of_date, scenario),
        _SCENARIO_TIME_RANK[scenario.valuation_time],
        scenario.days_forward,
        decimal.Decimal(str(scenario.underlying_move)),
        decimal.Decimal(str(scenario.iv_change)),
    )


def _finite_float_from_decimal(name: str, value: decimal.Decimal) -> float:
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} cannot be converted to finite float") from error
    if not math.isfinite(converted):
        raise ValueError(f"{name} cannot be converted to finite float")
    return converted


def _calculated_dependency_disclosure(
    lineage: CalculationLineage, selected: dict
) -> dict:
    return {
        "calculation_id": lineage.calculation_id,
        "calculation_type": lineage.calculation_type,
        "methodology_id": lineage.methodology_id,
        "methodology_version": lineage.methodology_version,
        "calculated_at": lineage.calculated_at,
        "parameters_json": lineage.parameters_json,
        "quality_flags": tuple(flag.value for flag in lineage.quality_flags),
        "selected": selected,
    }


def _float_from_stable_repr(value: object, label: str) -> float:
    if type(value) is not str:
        raise TypeError(f"{label} must have exact type str")
    try:
        converted = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{label} is not a finite float representation") from error
    if not math.isfinite(converted) or repr(converted) != value:
        raise ValueError(f"{label} is not a canonical finite float representation")
    return converted


def _verify_tail_pricing_result(
    records: object, lineage: object
) -> tuple:
    if type(records) is not tuple:
        raise TypeError("tail records must have exact type tuple")
    if len(records) < 2:
        raise ValueError("tail records must contain at least two items")
    reconstructed_records = []
    for record in records:
        if type(record) is not TailPricingSlice:
            raise TypeError("every tail record must have exact type TailPricingSlice")
        for name in ("underlying", "delta_methodology"):
            if type(getattr(record, name)) is not str:
                raise TypeError(f"tail {name} must have exact type str")
        for name in ("as_of_date", "expiration"):
            if type(getattr(record, name)) is not datetime.date:
                raise TypeError(f"tail {name} must have exact type date")
        for name in (
            "atm_iv", "put_25_delta_iv", "call_25_delta_iv",
            "put_10_delta_iv", "call_10_delta_iv", "skew_percentile",
        ):
            _stable_float(getattr(record, name), f"tail {name}")
        if type(record.skew_history_lookback_observations) is not int:
            raise TypeError("tail history count must have exact type int")
        reconstructed_records.append(TailPricingSlice(
            underlying=record.underlying,
            as_of_date=record.as_of_date,
            expiration=record.expiration,
            atm_iv=record.atm_iv,
            put_25_delta_iv=record.put_25_delta_iv,
            call_25_delta_iv=record.call_25_delta_iv,
            put_10_delta_iv=record.put_10_delta_iv,
            call_10_delta_iv=record.call_10_delta_iv,
            skew_percentile=record.skew_percentile,
            skew_history_lookback_observations=(
                record.skew_history_lookback_observations
            ),
            delta_methodology=record.delta_methodology,
        ))
    if tuple(reconstructed_records) != records:
        raise ValueError("tail records are constructor-bypassed")
    lineage = _reconstruct_lineage(lineage)
    if (
        lineage.calculation_type != "tail_pricing"
        or lineage.methodology_id
        != "nearest-observed-delta-wing-tail-relative-pricing"
        or lineage.methodology_version != "v0.2"
    ):
        raise ValueError("tail-pricing dependency identity is invalid")
    if CalculationQualityFlag.INCOMPLETE_INPUT_USED in lineage.quality_flags:
        raise ValueError("tail-pricing dependency must not use incomplete inputs")
    decoded = _decode_tail_pricing_parameters(lineage.parameters_json)
    observations = decoded["current_expiration_observations"]
    if type(observations) is not tuple:
        raise TypeError(
            "current_expiration_observations must have exact type tuple"
        )
    if len(observations) != len(records):
        raise ValueError("tail records and parameters have different counts")
    if (
        decoded["volatility_unit"] != "annualized_decimal_ratio"
        or decoded["interpolation_rule"] != "none"
        or decoded["skew_term_structure_ordering"]
        != "ascending_days_to_expiration_then_expiration"
    ):
        raise ValueError("tail-pricing fixed methodology is invalid")
    delta_methodology = canonicalize_lineage_parameters(
        decoded["delta_convention"]
    )
    input_ids = set()
    direct_roles = {}
    def retain_tail_role(record_id: str, role: str) -> None:
        existing = direct_roles.get(record_id)
        if existing is not None and existing != role:
            raise ValueError("tail direct evidence role collision")
        direct_roles[record_id] = role
    for record, observation in zip(records, observations):
        if type(observation) is not dict:
            raise TypeError("every current tail observation must be a dict")
        expected = {
            "session_date": record.as_of_date,
            "expiration": record.expiration,
            "tenor_days": record.days_to_expiration,
            "atm_iv": record.atm_iv,
            "selected_put_25": record.put_25_delta_iv,
            "selected_call_25": record.call_25_delta_iv,
            "selected_put_10": record.put_10_delta_iv,
            "selected_call_10": record.call_10_delta_iv,
            "skew_percentile": record.skew_percentile,
            "historical_observation_count": (
                record.skew_history_lookback_observations
            ),
        }
        for key, expected_value in expected.items():
            actual = observation.get(key)
            if key.startswith("selected_"):
                actual = (
                    actual.get("implied_volatility")
                    if type(actual) is dict else None
                )
            if type(expected_value) is float:
                actual = (
                    float(actual)
                    if type(actual) is decimal.Decimal else actual
                )
            if key not in observation or actual != expected_value:
                raise ValueError(
                    f"tail record does not correspond to parameter {key}"
                )
        if record.delta_methodology != delta_methodology:
            raise ValueError("tail delta methodology is inconsistent")
        candidates = observation.get("candidate_contracts")
        if type(candidates) is not tuple:
            raise TypeError("candidate_contracts must have exact type tuple")
        for candidate in candidates:
            if type(candidate) is not dict:
                raise TypeError("every tail candidate must have exact type dict")
            for key in (
                "quote_record_id",
                "iv_record_id",
                "greeks_record_id",
                "contract_reference_record_id",
            ):
                if type(candidate.get(key)) is not str:
                    raise TypeError("tail candidate record IDs must be strings")
                input_ids.add(candidate[key])
            for key, role in (
                ("quote_record_id", "option_quote"),
                ("iv_record_id", "option_implied_volatility"),
                ("greeks_record_id", "option_greeks"),
                ("contract_reference_record_id", "option_contract_reference"),
            ):
                retain_tail_role(candidate[key], role)
        underlying_id = observation.get("underlying_quote_record_id")
        if type(underlying_id) is not str:
            raise TypeError("tail underlying record ID must be a string")
        input_ids.add(underlying_id)
        retain_tail_role(underlying_id, "underlying_quote")
    historical = decoded["historical_observations_by_tenor"]
    if type(historical) is not tuple:
        raise TypeError("historical_observations_by_tenor must be a tuple")
    for tenor in historical:
        if type(tenor) is not dict:
            raise TypeError("historical tenor must be a dict")
        entries = tenor.get("historical_observations")
        if type(entries) is not tuple:
            raise TypeError("historical_observations must be a tuple")
        for observation in entries:
            if type(observation) is not dict:
                raise TypeError("historical observation must be a dict")
            underlying_id = observation.get("underlying_quote_record_id")
            if type(underlying_id) is not str:
                raise TypeError("historical underlying ID must be a string")
            input_ids.add(underlying_id)
            candidates = observation.get("candidate_contracts")
            if type(candidates) is not tuple:
                raise TypeError("historical candidates must be a tuple")
            for candidate in candidates:
                if type(candidate) is not dict:
                    raise TypeError("historical candidate must be a dict")
                for key in (
                    "quote_record_id",
                    "iv_record_id",
                    "greeks_record_id",
                    "contract_reference_record_id",
                ):
                    if type(candidate.get(key)) is not str:
                        raise TypeError("historical candidate ID must be a string")
                    input_ids.add(candidate[key])
                for key, role in (
                    ("quote_record_id", "option_quote"),
                    ("iv_record_id", "option_implied_volatility"),
                    ("greeks_record_id", "option_greeks"),
                    ("contract_reference_record_id", "option_contract_reference"),
                ):
                    retain_tail_role(candidate[key], role)
            retain_tail_role(underlying_id, "underlying_quote")
    atm_dependency = decoded["atm_dependency"]
    if type(atm_dependency) is not dict:
        raise TypeError("atm_dependency must have exact type dict")
    if (
        atm_dependency.get("underlying") != records[0].underlying
        or atm_dependency.get("as_of_date") != records[0].as_of_date
    ):
        raise ValueError(
            "tail records do not correspond to dependency underlying and date"
        )
    dependency_inputs = tuple(
        CalculationInputReference(
            record_id=item["record_id"],
            normalized_at=item["normalized_at"],
            source_ids=item["source_ids"],
        )
        for item in atm_dependency["inputs"]
    )
    dependency_flags = tuple(
        CalculationQualityFlag(item) for item in atm_dependency["quality_flags"]
    )
    dependency_record = VolatilityEnvironment(
        underlying=atm_dependency["underlying"],
        as_of_date=atm_dependency["as_of_date"],
        reference_tenor_days=atm_dependency["reference_tenor_days"],
        iv_percentile=_float_from_stable_repr(
            atm_dependency["iv_percentile_float_repr"],
            "ATM dependency IV percentile",
        ),
        iv_history_lookback_observations=(
            atm_dependency["historical_observation_count"]
        ),
        historical_median_atm_iv=_float_from_stable_repr(
            atm_dependency["historical_median_atm_iv_float_repr"],
            "ATM dependency historical median",
        ),
        matched_realized_volatility=_float_from_stable_repr(
            atm_dependency["matched_realized_volatility_float_repr"],
            "ATM dependency realized volatility",
        ),
        matched_realized_window_days=(
            atm_dependency["matched_realized_window_days"]
        ),
        term_structure=tuple(TermVolatilityPoint(
            tenor_days=item["tenor_days"],
            atm_iv=_float_from_stable_repr(
                item["atm_iv_float_repr"], "ATM dependency term IV"
            ),
        ) for item in atm_dependency["term_points"]),
    )
    dependency_lineage = CalculationLineage(
        calculation_id=atm_dependency["calculation_id"],
        calculation_type=atm_dependency["calculation_type"],
        methodology_id=atm_dependency["methodology_id"],
        methodology_version=atm_dependency["methodology_version"],
        calculated_at=atm_dependency["calculated_at"],
        inputs=dependency_inputs,
        parameters_json=atm_dependency["parameters_json"],
        quality_flags=dependency_flags,
    )
    dependency = VolatilityEnvironmentTransformationResult(
        dependency_record, dependency_lineage
    )
    dependency_decoded = _decode_volatility_parameters(
        dependency.lineage.parameters_json
    )
    if (
        atm_dependency["current_atm_observations"]
        != dependency_decoded["current_observations"]
        or atm_dependency["historical_atm_observations"]
        != dependency_decoded["historical_observations"]
    ):
        raise ValueError("ATM dependency disclosure differs from verified artifact")
    if dependency.lineage.calculation_id == lineage.calculation_id:
        raise ValueError("tail and ATM calculation IDs must differ")
    if dependency.lineage.calculated_at > lineage.calculated_at:
        raise ValueError("ATM dependency follows tail calculation")
    dependency_ids = {item.record_id for item in dependency.lineage.inputs}
    direct = decoded["normalized_evidence"]["direct_inputs"]
    direct_by_id = {item["record_id"]: item for item in direct}
    dependency_calculation_ids = {
        dependency.lineage.calculation_id,
        dependency_decoded["realized_volatility_dependency"][
            "calculation_id"
        ],
    }
    calculation_ids = dependency_calculation_ids | {
        lineage.calculation_id,
    }
    complete_input_ids = dependency_ids | set(direct_by_id)
    if (
        len(dependency_calculation_ids) != 2
        or len(calculation_ids) != 3
        or not calculation_ids.isdisjoint(complete_input_ids)
    ):
        raise ValueError("tail calculation ID namespace collides")
    if set(direct_by_id) != input_ids:
        raise ValueError("tail direct evidence is missing or surplus")
    if any(
        direct_by_id[record_id]["role"] != role
        for record_id, role in direct_roles.items()
    ):
        raise ValueError("tail direct evidence role is inconsistent")
    references = {item.record_id: item for item in lineage.inputs}
    expected_union = dependency_ids | set(direct_by_id)
    if set(references) != expected_union:
        raise ValueError("tail parameter input IDs do not match lineage inputs")
    for item in direct:
        reference = references[item["record_id"]]
        if (
            reference.normalized_at != item["normalized_at"]
            or reference.source_ids != item["source_ids"]
        ):
            raise ValueError("tail direct reference differs from lineage")
    for reference in dependency.lineage.inputs:
        final = references[reference.record_id]
        if final != reference:
            raise ValueError("tail dependency overlap is contradictory")
    expected_flags = {
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    expected_flags.update(
        flag for flag in dependency.lineage.quality_flags
        if flag in _SCENARIO_VALUATION_PROPAGATED_FLAGS
    )
    direct_flag_values = {
        flag for item in direct for flag in item["propagated_quality_flags"]
    }
    expected_flags.update(
        flag for flag in _SCENARIO_VALUATION_PROPAGATED_FLAGS
        if flag.value in direct_flag_values
    )
    if lineage.quality_flags != tuple(
        flag for flag in CalculationQualityFlag if flag in expected_flags
    ):
        raise ValueError("tail-pricing quality flags are invalid")
    return decoded, observations, dependency


def _validate_tail_pricing_dependency(
    value: object,
) -> Tuple[
    TailPricingTransformationResult,
    dict,
    Tuple[dict, ...],
]:
    if type(value) is not TailPricingTransformationResult:
        raise TypeError(
            "tail_pricing_result must have exact type "
            "TailPricingTransformationResult"
        )
    decoded, observations, _dependency = _verify_tail_pricing_result(
        value.records, value.lineage
    )
    return value, decoded, observations


_SCENARIO_VALUATION_DEPENDENCY_KEYS = {
    "calculation_id",
    "calculation_type",
    "methodology_id",
    "methodology_version",
    "calculated_at",
    "parameters_json",
    "quality_flags",
    "selected",
}
_SCENARIO_VALUATION_CALCULATION_VALUE_KEYS = {
    "scenario_identity",
    "valuation_date",
    "valuation_source",
    "base_underlying_exact",
    "shocked_underlying_exact",
    "base_leg_ivs_exact",
    "shocked_leg_ivs_exact",
    "remaining_calendar_days",
    "gross_position_value_exact",
    "exit_cost_assumption_exact",
    "expiration_per_leg_payoffs_exact",
    "stable_gross_value_repr",
    "stable_exit_cost_repr",
    "stable_base_underlying_repr",
    "stable_entry_cost_repr",
    "stable_net_liquidation_repr",
    "stable_after_cost_pnl_repr",
    "stable_return_on_entry_cost_repr",
    "loss_is_within_entry_cost",
    "pricing_methodology",
}


def _scenario_valuation_exact_dict(
    value: object, keys: set, label: str
) -> dict:
    if type(value) is not dict:
        raise TypeError(f"{label} must have exact type dict")
    if set(value) != keys:
        raise ValueError(f"{label} has the wrong exact schema")
    return value


def _scenario_valuation_exact_tuple(value: object, label: str) -> tuple:
    if type(value) is not tuple:
        raise TypeError(f"{label} must have exact type tuple")
    return value


def _scenario_valuation_dependency(
    value: object,
    identity: tuple,
    selected_keys: set,
    decoder: object,
    lineage: CalculationLineage,
    label: str,
) -> Tuple[dict, dict, dict, set]:
    dependency = _scenario_valuation_exact_dict(
        value, _SCENARIO_VALUATION_DEPENDENCY_KEYS, label
    )
    for key in (
        "calculation_id",
        "calculation_type",
        "methodology_id",
        "methodology_version",
        "parameters_json",
    ):
        _scenario_pricing_string(f"{label}.{key}", dependency[key])
    if tuple(
        dependency[key]
        for key in (
            "calculation_type",
            "methodology_id",
            "methodology_version",
        )
    ) != identity:
        raise ValueError(f"{label} has the wrong exact dependency identity")
    calculated_at = _scenario_pricing_datetime(
        f"{label}.calculated_at", dependency["calculated_at"]
    )
    if calculated_at > lineage.calculated_at:
        raise ValueError(f"{label} chronology is invalid")
    flags = _scenario_valuation_exact_tuple(
        dependency["quality_flags"], f"{label}.quality_flags"
    )
    if any(type(item) is not str for item in flags):
        raise TypeError(f"{label} quality flag values must be exact strings")
    try:
        flag_values = tuple(CalculationQualityFlag(item) for item in flags)
    except ValueError as error:
        raise ValueError(f"{label} contains an unknown quality flag") from error
    if (
        len(set(flag_values)) != len(flag_values)
        or flag_values != tuple(
            flag for flag in CalculationQualityFlag if flag in set(flag_values)
        )
        or CalculationQualityFlag.INCOMPLETE_INPUT_USED in flag_values
    ):
        raise ValueError(f"{label} quality flags are invalid")
    selected = _scenario_valuation_exact_dict(
        dependency["selected"], selected_keys, f"{label}.selected"
    )
    parameters = decoder(dependency["parameters_json"])
    return dependency, selected, parameters, set(flag_values)


def _scenario_valuation_cost_structure_identity(
    structure: OptionStructure,
) -> dict:
    return {
        "structure_type": structure.structure_type,
        "underlying": structure.underlying,
        "assumed_portfolio_value_repr": repr(
            structure.assumed_portfolio_value
        ),
        "expected_holding_days": structure.expected_holding_days,
        "legs": tuple({
            "underlying": leg.underlying,
            "option_type": leg.option_type,
            "strike_float_repr": repr(leg.strike),
            "expiration": leg.expiration,
            "quantity": leg.quantity,
            "contract_multiplier": leg.contract_multiplier,
        } for leg in structure.legs),
    }


def _scenario_valuation_pricing_structure_identity(
    structure: OptionStructure, as_of_date: datetime.date
) -> dict:
    return {
        "structure_type": structure.structure_type,
        "legs": tuple(
            _scenario_pricing_leg_identity(leg) for leg in structure.legs
        ),
        "assumed_portfolio_value": decimal.Decimal(
            str(structure.assumed_portfolio_value)
        ),
        "expected_holding_days": structure.expected_holding_days,
        "as_of_date": as_of_date,
        "shared_expiration": structure.legs[0].expiration,
    }


def _scenario_valuation_methodology(
    record: ScenarioResult,
    values: dict,
    decoded: dict,
    scenario_parameters: dict,
) -> dict:
    methodology = _decode_strict_tagged_parameters(
        record.pricing_methodology,
        _SCENARIO_METHODOLOGY_KEYS,
        "ScenarioResult methodology",
    )
    valuation_source = values["valuation_source"]
    if valuation_source not in {
        "authoritative_provider_nonexpiration",
        "terminal_intrinsic_expiration",
    }:
        raise ValueError("record methodology valuation source is invalid")
    costs = decoded["structure_costs_dependency"]
    tail = decoded["tail_pricing_dependency"]
    pricing = decoded["scenario_pricing_dependency"]
    exit_section = decoded["exit_cost_assumptions"]
    producer = pricing["selected"]["producer_identity"]
    if valuation_source == "authoritative_provider_nonexpiration":
        provider_disclosure = {
            "status": "active_authoritative_provider_calculated",
            "calculation_id": pricing["calculation_id"],
            "producer_name": producer["producer_name"],
            "producer_version": producer["producer_version"],
            "request_id": producer["request_id"],
            "payload_sha256": producer["payload_sha256"],
            "producer_calculated_at": scenario_parameters[
                "producer_provenance"
            ]["producer_calculated_at"],
            "pricing_model_name": producer["pricing_model_name"],
            "pricing_model_version": producer["pricing_model_version"],
            "rate_methodology": scenario_parameters["rate_methodology"],
            "dividend_methodology": scenario_parameters[
                "dividend_methodology"
            ],
            "surface_treatment": scenario_parameters[
                "pricing_methodology"
            ]["volatility_surface_treatment"],
            "skew_treatment": scenario_parameters["pricing_methodology"][
                "skew_treatment"
            ],
            "term_treatment": scenario_parameters["pricing_methodology"][
                "term_treatment"
            ],
            "interpolation_treatment": scenario_parameters[
                "pricing_methodology"
            ]["volatility_interpolation"],
            "settlement_treatment": scenario_parameters[
                "pricing_methodology"
            ]["settlement_treatment"],
            "remaining_time_rule": scenario_parameters[
                "remaining_time_rule"
            ],
            "position_scaling_rule": scenario_parameters[
                "position_scaling_rule"
            ],
            "numerical_boundary": scenario_parameters[
                "pricing_methodology"
            ]["numerical_calculation_boundary"],
        }
    else:
        provider_disclosure = {
            "status": "inactive_for_expiration",
            "external_expiration_value": "prohibited",
        }
    expected = {
        "schema_version": "v0.1",
        "valuation_source": valuation_source,
        "scenario_identity": _scenario_identity(record.scenario),
        "structure_costs_dependency": {
            "calculation_id": costs["calculation_id"],
            "identity": (
                "structure_costs",
                "exact-structure-costs",
                "v0.2",
            ),
        },
        "tail_pricing_dependency": {
            "calculation_id": tail["calculation_id"],
            "identity": (
                "tail_pricing",
                "nearest-observed-delta-wing-tail-relative-pricing",
                "v0.2",
            ),
            "use": "context_only",
        },
        "scenario_pricing_dependency": {
            "calculation_id": pricing["calculation_id"],
            "identity": (
                "nonexpiration_scenario_pricing",
                "authoritative-provider-option-scenario-pricing-evidence",
                "v0.1",
            ),
        },
        "provider_disclosure": provider_disclosure,
        "nonexpiration_rule": {
            "active": record.scenario.valuation_time != "expiration",
            "rule": "consume_authoritative_gross_value_without_repricing",
        },
        "expiration_rule": {
            "active": record.scenario.valuation_time == "expiration",
            "call_formula": (
                "max(shocked_underlying-strike,0)*quantity*multiplier"
            ),
            "put_formula": (
                "max(strike-shocked_underlying,0)*quantity*multiplier"
            ),
            "iv_effect": "none_base_leg_ivs_retained_for_audit",
            "external_expiration_value": "prohibited",
        },
        "base_underlying_source": (
            "StructureCosts_v0.2_underlying_price_exact"
        ),
        "base_iv_source": (
            "ScenarioPricing_v0.1_actual_structure_leg_iv_evidence"
        ),
        "entry_cost_rule": (
            "StructureCosts_v0.2_stable_total_entry_cost_float"
        ),
        "exit_cost_rule": {
            "methodology": exit_section["methodology"],
            "source": "explicit_scenario_specific_decimal_assumption",
        },
        "float_conversion_rule": (
            "convert_base_iv_gross_and_exit_cost_once_to_finite_float"
        ),
        "limitations": (
            "Internal consistency is validated; self-consistent fabricated "
            "dependency artifacts are not cryptographically authenticated."
        ),
    }
    _scenario_pricing_require_correspondence(
        "ScenarioResult methodology", methodology, expected
    )
    return methodology


def _scenario_disclosed_record_ids(value: object) -> set:
    """Collect normalized record identities from one strict disclosure tree."""

    result = set()

    def visit(item: object, key: Optional[str] = None) -> None:
        if type(item) is dict:
            for child_key, child in item.items():
                if (
                    type(child_key) is str
                    and child_key.endswith("record_id")
                    and type(child) is str
                ):
                    result.add(child)
                elif (
                    type(child_key) is str
                    and child_key.endswith("record_ids")
                    and type(child) is tuple
                ):
                    for value in child:
                        if type(value) is not str:
                            raise TypeError(
                                "disclosed record IDs must be exact strings"
                            )
                        result.add(value)
                visit(child, child_key)
        elif type(item) is tuple:
            for child in item:
                visit(child, key)

    visit(value)
    return result


def _scenario_dependency_inputs(
    parameters: dict, lineage: CalculationLineage, label: str
) -> tuple:
    identifiers = _scenario_disclosed_record_ids(parameters)
    references = {item.record_id: item for item in lineage.inputs}
    missing = identifiers - set(references)
    if missing:
        raise ValueError(f"scenario is missing a {label} lineage input")
    return tuple(references[item] for item in sorted(identifiers))


def _scenario_union_dependency_inputs(groups: tuple) -> tuple:
    references = {}
    for group in groups:
        for reference in group:
            existing = references.get(reference.record_id)
            if existing is not None and existing != reference:
                raise ValueError(
                    "scenario dependency input overlap is contradictory"
                )
            references[reference.record_id] = reference
    return tuple(references[key] for key in sorted(references))


def _scenario_dependency_lineage(
    disclosure: dict,
    parameters: dict,
    lineage: CalculationLineage,
    label: str,
) -> CalculationLineage:
    try:
        flags = tuple(
            CalculationQualityFlag(value)
            for value in disclosure["quality_flags"]
        )
    except ValueError as error:
        raise ValueError(f"{label} contains an unknown quality flag") from error
    return CalculationLineage(
        calculation_id=disclosure["calculation_id"],
        calculation_type=disclosure["calculation_type"],
        methodology_id=disclosure["methodology_id"],
        methodology_version=disclosure["methodology_version"],
        calculated_at=disclosure["calculated_at"],
        inputs=_scenario_dependency_inputs(parameters, lineage, label),
        parameters_json=disclosure["parameters_json"],
        quality_flags=flags,
    )


def _scenario_reconstruct_costs_dependency(
    record: ScenarioResult,
    disclosure: dict,
    parameters: dict,
    lineage: CalculationLineage,
) -> StructureCostsTransformationResult:
    dependency_lineage = _scenario_dependency_lineage(
        disclosure, parameters, lineage, "StructureCosts"
    )
    values = parameters["calculation_values"]
    stable = values["stable_record_values"]
    methodology = parameters["greeks_methodology"]
    cost_record = StructureCosts(
        structure=record.structure,
        as_of_date=record.as_of_date,
        quoted_mid_premium=_cost_stable_float_repr(
            stable["quoted_mid_premium_repr"], "quoted_mid_premium_repr"
        ),
        estimated_spread_cost=_cost_stable_float_repr(
            stable["estimated_spread_cost_repr"],
            "estimated_spread_cost_repr",
        ),
        commissions_and_fees=_cost_stable_float_repr(
            stable["commissions_and_fees_repr"],
            "commissions_and_fees_repr",
        ),
        theta_per_day=_cost_stable_float_repr(
            stable["theta_per_day_repr"], "theta_per_day_repr"
        ),
        gamma=_cost_stable_float_repr(
            stable["gamma_repr"], "gamma_repr"
        ),
        underlying_price=_cost_stable_float_repr(
            stable["underlying_price_repr"], "underlying_price_repr"
        ),
        greeks_methodology=_greeks_methodology_disclosure((
            methodology["model_name"],
            methodology["model_version"],
            methodology["rate_input_description"],
            methodology["dividend_input_description"],
            methodology["theta_day_basis"],
            methodology["unit_convention"],
        )),
        repeated_bet_count=parameters["repeated_bet_count"],
    )
    return StructureCostsTransformationResult(cost_record, dependency_lineage)


def _scenario_reconstruct_tail_dependency(
    disclosure: dict,
    selected: dict,
    parameters: dict,
    lineage: CalculationLineage,
) -> tuple:
    dependency_lineage = _scenario_dependency_lineage(
        disclosure, parameters, lineage, "TailPricing"
    )
    delta_methodology = canonicalize_lineage_parameters(
        parameters["delta_convention"]
    )
    records = tuple(TailPricingSlice(
        underlying=selected["underlying"],
        as_of_date=observation["session_date"],
        expiration=observation["expiration"],
        atm_iv=_finite_float(observation["atm_iv"]),
        put_25_delta_iv=_finite_float(
            observation["selected_put_25"]["implied_volatility"]
        ),
        call_25_delta_iv=_finite_float(
            observation["selected_call_25"]["implied_volatility"]
        ),
        put_10_delta_iv=_finite_float(
            observation["selected_put_10"]["implied_volatility"]
        ),
        call_10_delta_iv=_finite_float(
            observation["selected_call_10"]["implied_volatility"]
        ),
        skew_percentile=_finite_float(observation["skew_percentile"]),
        skew_history_lookback_observations=(
            observation["historical_observation_count"]
        ),
        delta_methodology=delta_methodology,
    ) for observation in parameters["current_expiration_observations"])
    result = TailPricingTransformationResult(records, dependency_lineage)
    _decoded, _observations, volatility = _verify_tail_pricing_result(
        result.records, result.lineage
    )
    return result, volatility


def _scenario_reconstruct_contract_key(value: dict) -> OptionContractKey:
    underlying = value["underlying_key"]
    return OptionContractKey(
        underlying_key=UnderlyingKey(
            symbol=underlying["symbol"],
            listing_mic=underlying["listing_mic"],
            security_type=UnderlyingSecurityType(
                underlying["security_type"]
            ),
            currency=underlying["currency"],
        ),
        expiration=value["expiration"],
        option_type=value["option_type"],
        strike=value["strike"],
        contract_multiplier=value["contract_multiplier"],
        currency=value["currency"],
        deliverable_id=value["deliverable_id"],
    )


def _scenario_reconstruct_pricing_dependency(
    record: ScenarioResult,
    disclosure: dict,
    parameters: dict,
    lineage: CalculationLineage,
) -> ScenarioPricingCalculationResult:
    dependency_lineage = _scenario_dependency_lineage(
        disclosure, parameters, lineage, "ScenarioPricing"
    )
    producer_identity = parameters["producer_identity"]
    producer = parameters["producer_provenance"]
    pricing = parameters["pricing_methodology"]
    rate = parameters["rate_methodology"]
    dividend = parameters["dividend_methodology"]
    methodology = ScenarioPricingMethodology(
        pricing_source_classification=producer[
            "pricing_source_classification"
        ],
        producer_name=producer_identity["producer_name"],
        producer_version=producer_identity["producer_version"],
        pricing_request_id=producer["pricing_request_id"],
        pricing_payload_sha256=producer["pricing_payload_sha256"],
        producer_calculated_at=producer["producer_calculated_at"],
        pricing_model_name=pricing["pricing_model_name"],
        pricing_model_version=pricing["pricing_model_version"],
        supported_exercise_settlement_pairs=parameters[
            "exercise_and_settlement_support"
        ],
        settlement_treatment=pricing["settlement_treatment"],
        rate_source=rate["rate_source"],
        rate_curve_identity=rate["rate_curve_identity"],
        rate_effective_date=rate["rate_effective_date"],
        rate_currency=rate["rate_currency"],
        rate_remaining_tenor_treatment=rate[
            "rate_remaining_tenor_treatment"
        ],
        rate_compounding_conversion=rate["rate_compounding_conversion"],
        rate_day_count_convention=rate["rate_day_count_convention"],
        rate_interpolation=rate["rate_interpolation"],
        dividend_source=dividend["dividend_source"],
        dividend_treatment=dividend["dividend_treatment"],
        dividend_coverage_start_date=dividend[
            "dividend_coverage_start_date"
        ],
        dividend_coverage_end_date=dividend["dividend_coverage_end_date"],
        explicit_zero_dividend_assumption=dividend[
            "explicit_zero_dividend_assumption"
        ],
        volatility_surface_treatment=pricing[
            "volatility_surface_treatment"
        ],
        skew_treatment=pricing["skew_treatment"],
        term_treatment=pricing["term_treatment"],
        volatility_interpolation=pricing["volatility_interpolation"],
        remaining_time_rule=parameters["remaining_time_rule"],
        position_scaling_rule=parameters["position_scaling_rule"],
        numerical_calculation_boundary=pricing[
            "numerical_calculation_boundary"
        ],
        limitations=parameters["limitations"],
    )
    correspondence = parameters["leg_correspondence"]
    calculations = []
    for values in parameters["calculation_values"]:
        identity = values["scenario"]
        scenario = Scenario(
            float(identity["underlying_move"]),
            float(identity["iv_change"]),
            identity["valuation_time"],
            identity["days_forward"],
        )
        leg_values = values["leg_values"]
        leg_calculations = tuple(
            ScenarioPricingLegCalculation(
                leg=leg,
                contract_key=_scenario_reconstruct_contract_key(
                    common["contract_key"]
                ),
                base_iv=common["base_iv"],
                shocked_iv=item["shocked_iv"],
                remaining_calendar_days=item["remaining_calendar_days"],
                per_underlying_unit_option_value=item[
                    "per_underlying_unit_option_value"
                ],
                total_leg_value=item["total_leg_value"],
                exercise_style=common["exercise_style"],
                settlement_type=common["settlement_type"],
                implied_volatility_record_id=common[
                    "implied_volatility_record_id"
                ],
                contract_reference_record_id=common[
                    "contract_reference_record_id"
                ],
            )
            for leg, common, item in zip(
                record.structure.legs, correspondence, leg_values
            )
        )
        calculations.append(NonExpirationScenarioPricingCalculation(
            structure=record.structure,
            as_of_date=record.as_of_date,
            scenario=scenario,
            valuation_date=values["valuation_date"],
            base_underlying_price=values["base_underlying_price"],
            shocked_underlying_price=values["shocked_underlying_price"],
            underlying_quote_record_id=values[
                "underlying_quote_record_id"
            ],
            leg_calculations=leg_calculations,
            estimated_gross_position_value=values[
                "estimated_gross_position_value"
            ],
            pricing_methodology=methodology,
        ))
    return ScenarioPricingCalculationResult(
        tuple(calculations), dependency_lineage
    )


def _reconstruct_scenario_valuation_dependencies(
    records: object, lineage: object
) -> tuple:
    """Reconstruct Scenario's complete retained calculations without producers."""

    if type(records) is not tuple or not records:
        raise TypeError("scenario records must have exact nonempty tuple type")
    if type(lineage) is not CalculationLineage:
        raise TypeError("scenario lineage must have exact type CalculationLineage")
    decoded = _decode_scenario_valuation_parameters(lineage.parameters_json)
    cost_disclosure = decoded["structure_costs_dependency"]
    tail_disclosure = decoded["tail_pricing_dependency"]
    pricing_disclosure = decoded["scenario_pricing_dependency"]
    cost_parameters = _decode_cost_parameters(
        cost_disclosure["parameters_json"]
    )
    tail_parameters = _decode_tail_pricing_parameters(
        tail_disclosure["parameters_json"]
    )
    pricing_parameters = _decode_scenario_pricing_parameters(
        pricing_disclosure["parameters_json"]
    )
    costs = _scenario_reconstruct_costs_dependency(
        records[0], cost_disclosure, cost_parameters, lineage
    )
    tail, volatility = _scenario_reconstruct_tail_dependency(
        tail_disclosure,
        tail_disclosure["selected"],
        tail_parameters,
        lineage,
    )
    pricing = _scenario_reconstruct_pricing_dependency(
        records[0], pricing_disclosure, pricing_parameters, lineage
    )
    expected = _scenario_union_dependency_inputs((
        costs.lineage.inputs,
        tail.lineage.inputs,
        pricing.lineage.inputs,
    ))
    if lineage.inputs != expected:
        raise ValueError(
            "scenario lineage inputs must equal the exact dependency union"
        )
    return costs, tail, pricing, volatility


def _validate_scenario_valuation_records(
    records: Tuple[ScenarioResult, ...],
    lineage: CalculationLineage,
) -> None:
    if (
        lineage.calculation_type != "scenario_valuation"
        or lineage.methodology_id
        != "hybrid-authoritative-nonexpiration-terminal-intrinsic-after-costs"
        or lineage.methodology_version != "v0.1"
    ):
        raise ValueError("scenario-valuation lineage identity is invalid")
    decoded = _decode_scenario_valuation_parameters(lineage.parameters_json)
    _reconstruct_scenario_valuation_dependencies(records, lineage)
    first = records[0]
    structure = first.structure
    as_of_date = first.as_of_date
    expiration = structure.legs[0].expiration

    cost_dependency, cost_selected, cost_parameters, cost_flags = (
        _scenario_valuation_dependency(
            decoded["structure_costs_dependency"],
            ("structure_costs", "exact-structure-costs", "v0.2"),
            {
                "structure_identity",
                "as_of_date",
                "underlying_price_exact",
                "underlying_price_repr",
                "quoted_mid_premium_exact",
                "estimated_spread_cost_exact",
                "commissions_and_fees_exact",
                "total_entry_cost_exact",
                "maximum_loss_exact",
                "total_entry_cost_repr",
            },
            _decode_cost_parameters,
            lineage,
            "structure_costs_dependency",
        )
    )
    tail_dependency, tail_selected, tail_parameters, tail_flags = (
        _scenario_valuation_dependency(
            decoded["tail_pricing_dependency"],
            (
                "tail_pricing",
                "nearest-observed-delta-wing-tail-relative-pricing",
                "v0.2",
            ),
            {
                "underlying",
                "as_of_date",
                "ordered_expirations",
                "structure_expiration_match",
                "matching_candidate_details",
            },
            _decode_tail_pricing_parameters,
            lineage,
            "tail_pricing_dependency",
        )
    )
    tail_input_ids = {
        item["record_id"]
        for item in tail_parameters["atm_dependency"]["inputs"]
    }
    tail_input_ids.update(
        item["record_id"]
        for item in tail_parameters["normalized_evidence"]["direct_inputs"]
    )
    scenario_references = {
        item.record_id: item for item in lineage.inputs
    }
    if not tail_input_ids.issubset(scenario_references):
        raise ValueError("scenario is missing a TailPricing lineage input")
    tail_lineage = CalculationLineage(
        calculation_id=tail_dependency["calculation_id"],
        calculation_type=tail_dependency["calculation_type"],
        methodology_id=tail_dependency["methodology_id"],
        methodology_version=tail_dependency["methodology_version"],
        calculated_at=tail_dependency["calculated_at"],
        inputs=tuple(
            scenario_references[record_id]
            for record_id in sorted(tail_input_ids)
        ),
        parameters_json=tail_dependency["parameters_json"],
        quality_flags=tuple(
            flag for flag in CalculationQualityFlag if flag in tail_flags
        ),
    )
    delta_methodology = canonicalize_lineage_parameters(
        tail_parameters["delta_convention"]
    )
    reconstructed_tail_records = tuple(TailPricingSlice(
        underlying=tail_selected["underlying"],
        as_of_date=observation["session_date"],
        expiration=observation["expiration"],
        atm_iv=_finite_float(observation["atm_iv"]),
        put_25_delta_iv=_finite_float(
            observation["selected_put_25"]["implied_volatility"]
        ),
        call_25_delta_iv=_finite_float(
            observation["selected_call_25"]["implied_volatility"]
        ),
        put_10_delta_iv=_finite_float(
            observation["selected_put_10"]["implied_volatility"]
        ),
        call_10_delta_iv=_finite_float(
            observation["selected_call_10"]["implied_volatility"]
        ),
        skew_percentile=_finite_float(observation["skew_percentile"]),
        skew_history_lookback_observations=(
            observation["historical_observation_count"]
        ),
        delta_methodology=delta_methodology,
    ) for observation in tail_parameters["current_expiration_observations"])
    _verify_tail_pricing_result(reconstructed_tail_records, tail_lineage)
    pricing_dependency, pricing_selected, scenario_parameters, pricing_flags = (
        _scenario_valuation_dependency(
            decoded["scenario_pricing_dependency"],
            (
                "nonexpiration_scenario_pricing",
                "authoritative-provider-option-scenario-pricing-evidence",
                "v0.1",
            ),
            {
                "structure_identity",
                "as_of_date",
                "base_underlying_price",
                "actual_leg_iv_tuple",
                "declared_nonexpiration_scenarios",
                "producer_identity",
            },
            _decode_scenario_pricing_parameters,
            lineage,
            "scenario_pricing_dependency",
        )
    )

    cost_values = _scenario_valuation_exact_dict(
        cost_parameters["calculation_values"],
        _COST_CALCULATION_VALUE_KEYS,
        "StructureCosts calculation_values",
    )
    stable_cost_values = _scenario_valuation_exact_dict(
        cost_values["stable_record_values"],
        _COST_STABLE_VALUE_KEYS,
        "StructureCosts stable_record_values",
    )
    expected_cost_selected = {
        "structure_identity": cost_parameters["structure_identity"],
        "as_of_date": as_of_date,
        "underlying_price_exact": cost_values["underlying_price_exact"],
        "underlying_price_repr": stable_cost_values[
            "underlying_price_repr"
        ],
        "quoted_mid_premium_exact": cost_values[
            "quoted_mid_premium_exact"
        ],
        "estimated_spread_cost_exact": cost_values[
            "estimated_spread_cost_exact"
        ],
        "commissions_and_fees_exact": cost_values[
            "commissions_and_fees_exact"
        ],
        "total_entry_cost_exact": cost_values["total_entry_cost_exact"],
        "maximum_loss_exact": cost_values["maximum_loss_exact"],
        "total_entry_cost_repr": stable_cost_values[
            "total_entry_cost_repr"
        ],
    }
    _scenario_pricing_require_correspondence(
        "structure_costs_dependency.selected",
        cost_selected,
        expected_cost_selected,
    )
    _scenario_pricing_require_correspondence(
        "StructureCosts structure identity",
        cost_selected["structure_identity"],
        _scenario_valuation_cost_structure_identity(structure),
    )
    if (
        cost_selected["as_of_date"] != as_of_date
        or float(cost_selected["underlying_price_exact"])
        != first.base_underlying_price
        or cost_selected["underlying_price_repr"]
        != repr(first.base_underlying_price)
        or float(cost_selected["total_entry_cost_exact"])
        != first.entry_cost_basis
        or cost_selected["total_entry_cost_repr"]
        != repr(first.entry_cost_basis)
        or cost_selected["maximum_loss_exact"]
        != cost_selected["total_entry_cost_exact"]
    ):
        raise ValueError("StructureCosts disclosure differs from public records")

    current_tail = _scenario_valuation_exact_tuple(
        tail_parameters["current_expiration_observations"],
        "TailPricing current_expiration_observations",
    )
    tail_observation_keys = {
        "session_date",
        "expiration",
        "tenor_days",
        "underlying_quote_record_id",
        "atm_iv",
        "atm_dependency_selected_call_iv_record_id",
        "atm_dependency_selected_put_iv_record_id",
        "candidate_contracts",
        "selected_put_25",
        "selected_call_25",
        "selected_put_10",
        "selected_call_10",
        "downside_25_delta_skew",
        "upside_25_delta_skew",
        "downside_wing_curvature",
        "upside_wing_curvature",
        "skew_percentile",
        "historical_observation_count",
    }
    tail_candidate_keys = {
        "option_type",
        "strike",
        "contract_multiplier",
        "currency",
        "deliverable_id",
        "quote_record_id",
        "iv_record_id",
        "greeks_record_id",
        "contract_reference_record_id",
        "implied_volatility",
        "signed_delta",
        "distance_to_25_target",
        "distance_to_10_target",
    }
    for observation in current_tail:
        observation = _scenario_valuation_exact_dict(
            observation,
            tail_observation_keys,
            "TailPricing current observation",
        )
        candidates = _scenario_valuation_exact_tuple(
            observation["candidate_contracts"],
            "TailPricing candidate_contracts",
        )
        for candidate in candidates:
            _scenario_valuation_exact_dict(
                candidate,
                tail_candidate_keys,
                "TailPricing candidate",
            )
    tail_expirations = tuple(
        item["expiration"]
        for item in current_tail
    )
    atm_dependency = tail_parameters["atm_dependency"]
    expected_tail_selected = {
        "underlying": atm_dependency["underlying"],
        "as_of_date": atm_dependency["as_of_date"],
        "ordered_expirations": tail_expirations,
        "structure_expiration_match": expiration,
        "matching_candidate_details": tail_selected[
            "matching_candidate_details"
        ],
    }
    _scenario_pricing_require_correspondence(
        "tail_pricing_dependency.selected",
        tail_selected,
        expected_tail_selected,
    )
    if (
        tail_selected["underlying"] != structure.underlying
        or tail_selected["as_of_date"] != as_of_date
        or tail_expirations.count(expiration) != 1
    ):
        raise ValueError("TailPricing disclosure differs from public records")

    _scenario_pricing_require_correspondence(
        "scenario_pricing structure identity",
        pricing_selected["structure_identity"],
        scenario_parameters["structure_identity"],
    )
    _scenario_pricing_require_correspondence(
        "scenario_pricing actual leg IV tuple",
        pricing_selected["actual_leg_iv_tuple"],
        scenario_parameters["leg_correspondence"],
    )
    _scenario_pricing_require_correspondence(
        "scenario_pricing declared scenarios",
        pricing_selected["declared_nonexpiration_scenarios"],
        scenario_parameters["scenario_definitions"],
    )
    producer_identity = _scenario_valuation_exact_dict(
        pricing_selected["producer_identity"],
        {
            "producer_name",
            "producer_version",
            "request_id",
            "payload_sha256",
            "pricing_model_name",
            "pricing_model_version",
        },
        "scenario_pricing producer_identity",
    )
    expected_producer = {
        "producer_name": scenario_parameters["producer_identity"][
            "producer_name"
        ],
        "producer_version": scenario_parameters["producer_identity"][
            "producer_version"
        ],
        "request_id": scenario_parameters["producer_provenance"][
            "pricing_request_id"
        ],
        "payload_sha256": scenario_parameters["producer_provenance"][
            "pricing_payload_sha256"
        ],
        "pricing_model_name": scenario_parameters["pricing_methodology"][
            "pricing_model_name"
        ],
        "pricing_model_version": scenario_parameters["pricing_methodology"][
            "pricing_model_version"
        ],
    }
    _scenario_pricing_require_correspondence(
        "scenario_pricing producer identity",
        producer_identity,
        expected_producer,
    )
    expected_pricing_structure = (
        _scenario_valuation_pricing_structure_identity(structure, as_of_date)
    )
    if (
        pricing_selected["structure_identity"] != expected_pricing_structure
        or pricing_selected["as_of_date"] != as_of_date
        or pricing_selected["base_underlying_price"]
        != cost_selected["underlying_price_exact"]
        or scenario_parameters["base_underlying_evidence"][
            "base_underlying_price"
        ] != pricing_selected["base_underlying_price"]
    ):
        raise ValueError(
            "ScenarioPricing disclosure differs from public records"
        )

    actual_leg_tuple = _scenario_valuation_exact_tuple(
        pricing_selected["actual_leg_iv_tuple"],
        "actual_leg_iv_tuple",
    )
    if len(actual_leg_tuple) != len(structure.legs):
        raise ValueError("actual leg IV tuple has the wrong cardinality")
    base_ivs_exact = tuple(item["base_iv"] for item in actual_leg_tuple)
    for leg, item in zip(structure.legs, actual_leg_tuple):
        _scenario_pricing_require_correspondence(
            "actual leg identity",
            item["leg"],
            _scenario_pricing_leg_identity(leg),
        )

    structure_tail_observation = next(
        item for item in current_tail if item["expiration"] == expiration
    )
    candidates = _scenario_valuation_exact_tuple(
        structure_tail_observation["candidate_contracts"],
        "matching TailPricing candidates",
    )
    matching_candidates = tuple(
        candidate
        for candidate in candidates
        if any(
            candidate["option_type"] == leg_item["contract_key"]["option_type"]
            and candidate["strike"] == leg_item["contract_key"]["strike"]
            and candidate["contract_multiplier"]
            == leg_item["contract_key"]["contract_multiplier"]
            and candidate["currency"] == leg_item["contract_key"]["currency"]
            and candidate["deliverable_id"]
            == leg_item["contract_key"]["deliverable_id"]
            for leg_item in actual_leg_tuple
        )
    )
    _scenario_pricing_require_correspondence(
        "matching TailPricing candidate disclosure",
        tail_selected["matching_candidate_details"],
        matching_candidates,
    )
    for candidate in matching_candidates:
        leg_item = next(
            item for item in actual_leg_tuple
            if (
                candidate["option_type"] == item["contract_key"]["option_type"]
                and candidate["strike"] == item["contract_key"]["strike"]
                and candidate["contract_multiplier"]
                == item["contract_key"]["contract_multiplier"]
                and candidate["currency"] == item["contract_key"]["currency"]
                and candidate["deliverable_id"]
                == item["contract_key"]["deliverable_id"]
            )
        )
        if (
            candidate["implied_volatility"] != leg_item["base_iv"]
            or candidate["iv_record_id"]
            != leg_item["implied_volatility_record_id"]
            or candidate["contract_reference_record_id"]
            != leg_item["contract_reference_record_id"]
        ):
            raise ValueError(
                "matching tail candidate differs from actual leg evidence"
            )

    fixed_sections = {
        "output_architecture": {
            "result_type": "ScenarioValuationTransformationResult",
            "records": "ordered_ScenarioResult_tuple",
            "lineage": "one_shared_CalculationLineage",
        },
        "supported_structure_scope": {
            "included": (
                "one_long_call",
                "one_long_put",
                "one_long_straddle",
                "positive_long_quantities",
                "one_common_underlying",
                "one_common_expiration",
            ),
            "excluded": ("shorts", "spreads", "exotics"),
        },
        "scenario_grid_semantics": {
            "underlying_moves": _SCENARIO_GRID_MOVES,
            "relative_iv_changes": _SCENARIO_GRID_IV_CHANGES,
            "complete_rule": "exact_cartesian_product_per_time_group",
            "false_rule": "explicitly_disclosed_subset",
        },
        "scenario_ordering": {
            "keys": (
                "valuation_date",
                "valuation_time_rank",
                "days_forward",
                "underlying_move_decimal",
                "iv_change_decimal",
            ),
            "valuation_time_rank": dict(_SCENARIO_TIME_RANK),
        },
        "valuation_date_rules": {
            "immediate": "as_of_date",
            "days_forward": "as_of_date_plus_days_forward_calendar_days",
            "holding_horizon": "as_of_date_plus_expected_holding_days",
            "expiration": "common_expiration",
        },
        "underlying_shock_rule": (
            "exact_base_underlying_times_one_plus_decimal_string_move"
        ),
        "iv_shock_rule": (
            "actual_leg_base_iv_times_one_plus_decimal_string_iv_change"
        ),
        "cross_dependency_consistency": {
            "structure": "exact_equal",
            "underlying": "exact_equal",
            "as_of_date": "exact_equal",
            "expiration": "exactly_one_tail_match",
            "leg_identity_and_multiplier": "exact_equal",
        },
        "base_underlying_rule": {
            "exact_source": "StructureCosts_v0.2_calculation_values",
            "scenario_result_source": "StructureCosts_stable_float",
        },
        "base_iv_rule": (
            "ScenarioPricing_v0.1_actual_leg_evidence_in_public_leg_order"
        ),
        "nonexpiration_valuation_rule": (
            "consume_authoritative_provider_gross_value_without_repricing"
        ),
        "expiration_payoff_rule": {
            "arithmetic": "Decimal_precision_34_ROUND_HALF_EVEN",
            "call": "max(shocked_underlying-strike,0)*quantity*multiplier",
            "put": "max(strike-shocked_underlying,0)*quantity*multiplier",
            "iv_independent": True,
            "external_value": "prohibited",
        },
        "entry_cost_rule": (
            "StructureCosts_v0.2_stable_total_entry_cost_float"
        ),
        "net_liquidation_rule": "max(gross_position_value-exit_cost,0.0)",
        "bounded_loss_rule": (
            "pnl_after_costs_not_less_than_negative_entry_cost"
        ),
        "record_methodology_disclosure": {
            "schema_keys": tuple(sorted(_SCENARIO_METHODOLOGY_KEYS)),
            "serializer": "canonicalize_lineage_parameters",
        },
        "lineage_union_rule": {
            "exact_overlap": "deduplicate",
            "conflicting_overlap": "reject",
            "calculated_dependencies_are_not_inputs": True,
        },
        "float_conversion_rule": {
            "decimal_context": "precision_34_ROUND_HALF_EVEN",
            "converted": ("base_leg_iv", "gross_position_value", "exit_cost"),
            "stable_cost_floats": (
                "base_underlying_price",
                "entry_cost_basis",
            ),
            "finite_required": True,
        },
        "limitations": (
            "Validates internal consistency, not cryptographic authenticity; "
            "probabilities, expected returns, screening, recommendations, "
            "sizing, and execution are outside scope."
        ),
    }
    for name, expected in fixed_sections.items():
        _scenario_pricing_require_correspondence(
            name, decoded[name], expected
        )

    declaration = _scenario_valuation_exact_dict(
        decoded["scenario_declaration"],
        {"ordered_scenarios", "scenario_grid_complete"},
        "scenario_declaration",
    )
    if type(declaration["scenario_grid_complete"]) is not bool:
        raise TypeError("scenario_grid_complete must have exact type bool")
    expected_scenarios = tuple(
        _scenario_identity(record.scenario) for record in records
    )
    if declaration["ordered_scenarios"] != expected_scenarios:
        raise ValueError("records do not correspond to scenario declaration")
    if declaration["scenario_grid_complete"]:
        groups = {}
        for record in records:
            scenario = record.scenario
            groups.setdefault(
                (scenario.valuation_time, scenario.days_forward), set()
            ).add((
                decimal.Decimal(str(scenario.underlying_move)),
                decimal.Decimal(str(scenario.iv_change)),
            ))
        expected_grid = {
            (move, iv_change)
            for move in _SCENARIO_GRID_MOVES
            for iv_change in _SCENARIO_GRID_IV_CHANGES
        }
        if any(values != expected_grid for values in groups.values()):
            raise ValueError("scenario declaration is not a complete grid")

    exit_section = _scenario_valuation_exact_dict(
        decoded["exit_cost_assumptions"],
        {"methodology", "ordered_values"},
        "exit_cost_assumptions",
    )
    _scenario_pricing_string(
        "exit_cost_assumptions.methodology", exit_section["methodology"]
    )
    exit_values = _scenario_valuation_exact_tuple(
        exit_section["ordered_values"], "exit_cost_assumptions.ordered_values"
    )
    if len(exit_values) != len(records):
        raise ValueError("exit-cost assumption count is inconsistent")

    calculation_values = _scenario_valuation_exact_tuple(
        decoded["calculation_values"], "calculation_values"
    )
    if len(calculation_values) != len(records):
        raise ValueError("record and calculation-value counts differ")
    scenario_parameter_values = _scenario_valuation_exact_tuple(
        scenario_parameters["calculation_values"],
        "ScenarioPricing calculation_values",
    )
    scenario_calculation_keys = {
        "scenario",
        "valuation_date",
        "base_underlying_price",
        "shocked_underlying_price",
        "underlying_quote_record_id",
        "leg_values",
        "estimated_gross_position_value",
    }
    scenario_leg_value_keys = {
        "leg",
        "contract_key",
        "base_iv",
        "shocked_iv",
        "remaining_calendar_days",
        "per_underlying_unit_option_value",
        "total_leg_value",
    }
    for item in scenario_parameter_values:
        item = _scenario_valuation_exact_dict(
            item,
            scenario_calculation_keys,
            "ScenarioPricing calculation value",
        )
        leg_values = _scenario_valuation_exact_tuple(
            item["leg_values"], "ScenarioPricing leg_values"
        )
        if len(leg_values) != len(structure.legs):
            raise ValueError("ScenarioPricing leg-value count is invalid")
        for leg_value in leg_values:
            _scenario_valuation_exact_dict(
                leg_value,
                scenario_leg_value_keys,
                "ScenarioPricing leg value",
            )
    parameter_scenario_identities = tuple(
        item["scenario"] for item in scenario_parameter_values
    )
    if (
        parameter_scenario_identities
        != pricing_selected["declared_nonexpiration_scenarios"]
        or len(set(
            (
                item["valuation_time"],
                item["days_forward"],
                item["underlying_move"],
                item["iv_change"],
            )
            for item in parameter_scenario_identities
        )) != len(parameter_scenario_identities)
    ):
        raise ValueError(
            "ScenarioPricing calculation-value scenarios are inconsistent"
        )
    scenario_values = {
        (
            item["scenario"]["valuation_time"],
            item["scenario"]["days_forward"],
            item["scenario"]["underlying_move"],
            item["scenario"]["iv_change"],
        ): item
        for item in scenario_parameter_values
    }
    arithmetic_context = decimal.Context(
        prec=34, rounding=decimal.ROUND_HALF_EVEN
    )
    for index, (record, values, exit_value) in enumerate(
        zip(records, calculation_values, exit_values)
    ):
        values = _scenario_valuation_exact_dict(
            values,
            _SCENARIO_VALUATION_CALCULATION_VALUE_KEYS,
            f"calculation_values[{index}]",
        )
        exit_value = _scenario_valuation_exact_dict(
            exit_value,
            {"scenario_identity", "exit_cost"},
            f"exit_cost_assumptions.ordered_values[{index}]",
        )
        identity = _scenario_identity(record.scenario)
        if (
            values["scenario_identity"] != identity
            or exit_value["scenario_identity"] != identity
        ):
            raise ValueError("scenario identity correspondence is invalid")
        valuation_date = _scenario_valuation_date(
            structure, as_of_date, record.scenario
        )
        try:
            shocked_underlying = arithmetic_context.multiply(
                cost_selected["underlying_price_exact"],
                arithmetic_context.add(
                    decimal.Decimal(1), identity["underlying_move"]
                ),
            )
        except decimal.DecimalException as error:
            raise ValueError("scenario underlying shock failed") from error
        shocked_ivs_exact = tuple(
            _scenario_pricing_shock(value, record.scenario.iv_change)
            for value in base_ivs_exact
        )
        if record.scenario.valuation_time == "expiration":
            valuation_source = "terminal_intrinsic_expiration"
            remaining_days = 0
            try:
                payoffs = []
                for leg in structure.legs:
                    strike = decimal.Decimal(str(leg.strike))
                    intrinsic = (
                        arithmetic_context.subtract(shocked_underlying, strike)
                        if leg.option_type == "call"
                        else arithmetic_context.subtract(strike, shocked_underlying)
                    )
                    intrinsic = max(intrinsic, decimal.Decimal(0))
                    payoffs.append(arithmetic_context.multiply(
                        intrinsic,
                        arithmetic_context.multiply(
                            decimal.Decimal(leg.quantity),
                            decimal.Decimal(leg.contract_multiplier),
                        ),
                    ))
                payoffs = tuple(payoffs)
                gross = decimal.Decimal(0)
                for payoff in payoffs:
                    gross = arithmetic_context.add(gross, payoff)
            except decimal.DecimalException as error:
                raise ValueError("expiration payoff calculation failed") from error
        else:
            valuation_source = "authoritative_provider_nonexpiration"
            provider = scenario_values.get(_scenario_identity_tuple(record.scenario))
            if provider is None:
                raise ValueError("ScenarioPricing calculation value is missing")
            gross = provider["estimated_gross_position_value"]
            remaining_days = (expiration - valuation_date).days
            payoffs = ()
            if (
                provider["valuation_date"] != valuation_date
                or provider["base_underlying_price"]
                != cost_selected["underlying_price_exact"]
                or provider["shocked_underlying_price"] != shocked_underlying
                or tuple(
                    item["base_iv"] for item in provider["leg_values"]
                ) != base_ivs_exact
                or tuple(
                    item["shocked_iv"] for item in provider["leg_values"]
                ) != shocked_ivs_exact
            ):
                raise ValueError(
                    "ScenarioPricing calculation values are inconsistent"
                )
        expected_exact = {
            "scenario_identity": identity,
            "valuation_date": valuation_date,
            "valuation_source": valuation_source,
            "base_underlying_exact": cost_selected[
                "underlying_price_exact"
            ],
            "shocked_underlying_exact": shocked_underlying,
            "base_leg_ivs_exact": base_ivs_exact,
            "shocked_leg_ivs_exact": shocked_ivs_exact,
            "remaining_calendar_days": remaining_days,
            "gross_position_value_exact": gross,
            "exit_cost_assumption_exact": exit_value["exit_cost"],
            "expiration_per_leg_payoffs_exact": payoffs,
        }
        for key, expected in expected_exact.items():
            _scenario_pricing_require_correspondence(
                f"calculation_values[{index}].{key}",
                values[key],
                expected,
            )
        if len(record.leg_volatility_inputs) != len(structure.legs):
            raise ValueError("public leg volatility input count is invalid")
        for leg_index, (public_input, leg, exact_iv) in enumerate(zip(
            record.leg_volatility_inputs, structure.legs, base_ivs_exact
        )):
            if (
                public_input.leg != leg
                or public_input.base_iv
                != _finite_float_from_decimal("base IV", exact_iv)
            ):
                raise ValueError(
                    f"public base IV correspondence failed at leg {leg_index}"
                )
        expected_public_shocked_ivs = tuple(
            item.base_iv * (1 + record.scenario.iv_change)
            for item in record.leg_volatility_inputs
        )
        if record.shocked_ivs != expected_public_shocked_ivs:
            raise ValueError("public shocked IV correspondence failed")
        public_expected = {
            "valuation_date": record.valuation_date,
            "stable_gross_value_repr": repr(record.estimated_position_value),
            "stable_exit_cost_repr": repr(record.estimated_exit_cost),
            "stable_base_underlying_repr": repr(record.base_underlying_price),
            "stable_entry_cost_repr": repr(record.entry_cost_basis),
            "stable_net_liquidation_repr": repr(record.net_liquidation_value),
            "stable_after_cost_pnl_repr": repr(record.pnl_after_costs),
            "stable_return_on_entry_cost_repr": repr(
                record.return_on_entry_cost
            ),
            "loss_is_within_entry_cost": record.loss_is_within_entry_cost,
            "pricing_methodology": record.pricing_methodology,
        }
        if (
            record.structure is not structure
            or record.as_of_date != as_of_date
            or record.valuation_date != valuation_date
            or record.base_underlying_price
            != float(cost_selected["underlying_price_exact"])
            or record.entry_cost_basis
            != float(cost_selected["total_entry_cost_exact"])
            or record.estimated_position_value != float(gross)
            or record.estimated_exit_cost != float(exit_value["exit_cost"])
        ):
            raise ValueError("public ScenarioResult fields are inconsistent")
        for key, expected in public_expected.items():
            if values[key] != expected:
                raise ValueError(
                    f"ScenarioResult does not correspond to {key}"
                )
        _scenario_valuation_methodology(
            record, values, decoded, scenario_parameters
        )

    dependency_flags = cost_flags | tail_flags | pricing_flags
    expected_flags = {
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    expected_flags.update(
        dependency_flags & _SCENARIO_VALUATION_PROPAGATED_FLAGS
    )
    if lineage.quality_flags != tuple(
        flag for flag in CalculationQualityFlag if flag in expected_flags
    ):
        raise ValueError("scenario-valuation quality flags are inconsistent")
    if CalculationQualityFlag.INCOMPLETE_INPUT_USED in lineage.quality_flags:
        raise ValueError("scenario valuation must not use incomplete inputs")


@dataclass(frozen=True)
class ScenarioValuationTransformationResult:
    records: Tuple[ScenarioResult, ...]
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.records) is not tuple:
            raise TypeError("records must have exact type tuple")
        if not self.records:
            raise ValueError("records must not be empty")
        if any(type(record) is not ScenarioResult for record in self.records):
            raise TypeError("every record must have exact type ScenarioResult")
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")
        first = self.records[0]
        if type(first.structure) is not OptionStructure:
            raise TypeError("record structure must have exact type OptionStructure")
        if type(first.as_of_date) is not datetime.date:
            raise TypeError("record as_of_date must have exact type date")
        if any(
            record.structure is not first.structure
            or record.as_of_date != first.as_of_date
            for record in self.records[1:]
        ):
            raise ValueError("records must share one structure and as_of_date")
        identities = tuple(
            _scenario_identity_tuple(record.scenario) for record in self.records
        )
        if len(set(identities)) != len(identities):
            raise ValueError("scenario identities must be unique")
        ordering = tuple(
            _scenario_order_key(
                first.structure, first.as_of_date, record.scenario
            )
            for record in self.records
        )
        if ordering != tuple(sorted(ordering)):
            raise ValueError("records must already be in canonical order")
        with decimal.localcontext():
            _validate_scenario_valuation_records(self.records, self.lineage)


def _construct_scenario_valuation_lineage(
    calculation_id: str,
    calculated_at: datetime.datetime,
    inputs: tuple,
    parameters_json: str,
    quality_flags: tuple,
) -> CalculationLineage:
    return CalculationLineage(
        calculation_id=calculation_id,
        calculation_type="scenario_valuation",
        methodology_id=(
            "hybrid-authoritative-nonexpiration-terminal-intrinsic-after-costs"
        ),
        methodology_version="v0.1",
        calculated_at=calculated_at,
        inputs=inputs,
        parameters_json=parameters_json,
        quality_flags=quality_flags,
    )


def transform_scenario_valuation(
    calculation_id: object,
    structure_costs_result: object,
    tail_pricing_result: object,
    scenario_pricing_result: object,
    scenarios: object,
    scenario_grid_complete: object,
    exit_cost_assumptions: object,
    exit_cost_methodology: object,
    calculated_at: object,
) -> ScenarioValuationTransformationResult:
    """Construct hybrid provider/non-provider scenario results after costs."""

    if type(calculation_id) is not str:
        raise TypeError("calculation_id must have exact type str")
    if type(scenarios) is not tuple:
        raise TypeError("scenarios must have exact type tuple")
    if any(type(item) is not Scenario for item in scenarios):
        raise TypeError("every scenarios item must have exact type Scenario")
    if type(scenario_grid_complete) is not bool:
        raise TypeError("scenario_grid_complete must have exact type bool")
    if type(exit_cost_assumptions) is not tuple:
        raise TypeError("exit_cost_assumptions must have exact type tuple")
    if type(exit_cost_methodology) is not str:
        raise TypeError("exit_cost_methodology must have exact type str")
    if type(calculated_at) is not datetime.datetime:
        raise TypeError("calculated_at must have exact type datetime")
    normalized_id = _validate_calculation_id(calculation_id)
    normalized_at = _normalize_calculated_at(calculated_at)

    if type(structure_costs_result) is not StructureCostsTransformationResult:
        raise TypeError(
            "structure_costs_result must have exact type "
            "StructureCostsTransformationResult"
        )
    with decimal.localcontext():
        costs = StructureCostsTransformationResult(
            structure_costs_result.record, structure_costs_result.lineage
        )
        cost_decoded = _decode_cost_parameters(costs.lineage.parameters_json)
    if CalculationQualityFlag.INCOMPLETE_INPUT_USED in costs.lineage.quality_flags:
        raise ValueError("structure-costs dependency is incomplete")

    with decimal.localcontext():
        tail, tail_decoded, tail_observations = (
            _validate_tail_pricing_dependency(tail_pricing_result)
        )

    if type(scenario_pricing_result) is not ScenarioPricingCalculationResult:
        raise TypeError(
            "scenario_pricing_result must have exact type "
            "ScenarioPricingCalculationResult"
        )
    with decimal.localcontext():
        pricing = ScenarioPricingCalculationResult(
            scenario_pricing_result.records,
            scenario_pricing_result.lineage,
        )
        pricing_decoded = _decode_scenario_pricing_parameters(
            pricing.lineage.parameters_json
        )
    if (
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED
        in pricing.lineage.quality_flags
        or CalculationQualityFlag.INCOMPLETE_INPUT_USED
        in pricing.lineage.quality_flags
    ):
        raise ValueError("scenario-pricing dependency flags are invalid")

    dependency_lineages = (
        costs.lineage,
        tail.lineage,
        pricing.lineage,
    )
    calculation_ids = (normalized_id,) + tuple(
        lineage.calculation_id for lineage in dependency_lineages
    )
    if len(set(calculation_ids)) != 4:
        raise ValueError("all four calculation IDs must be mutually distinct")
    if any(lineage.calculated_at > normalized_at for lineage in dependency_lineages):
        raise ValueError("dependency calculation follows scenario valuation")

    structure = costs.record.structure
    as_of_date = costs.record.as_of_date
    pricing_common = pricing.records[0]
    if structure != pricing_common.structure:
        raise ValueError("StructureCosts and ScenarioPricing structures differ")
    if as_of_date != pricing_common.as_of_date:
        raise ValueError("dependency as_of_date values differ")
    if tail.records[0].underlying != structure.underlying:
        raise ValueError("tail underlying differs from structure underlying")
    if tail.records[0].as_of_date != as_of_date:
        raise ValueError("tail as_of_date differs from common as_of_date")
    expiration = structure.legs[0].expiration
    matching_tail = tuple(
        (record, observation)
        for record, observation in zip(tail.records, tail_observations)
        if record.expiration == expiration
    )
    if len(matching_tail) != 1:
        raise ValueError("tail pricing must contain structure expiration once")
    cost_values = cost_decoded["calculation_values"]
    base_underlying_exact = cost_values["underlying_price_exact"]
    if base_underlying_exact != pricing_common.base_underlying_price:
        raise ValueError("exact base-underlying dependencies differ")
    if float(base_underlying_exact) != costs.record.underlying_price:
        raise ValueError("stable base-underlying float is inconsistent")
    if (
        cost_values["maximum_loss_exact"]
        != cost_values["total_entry_cost_exact"]
        or costs.record.maximum_loss != costs.record.total_entry_cost
    ):
        raise ValueError("long-only maximum loss must equal total entry cost")

    base_leg_calculations = pricing_common.leg_calculations
    if tuple(item.leg for item in base_leg_calculations) != structure.legs:
        raise ValueError("actual leg-IV evidence is not in structure-leg order")
    tail_candidates = matching_tail[0][1]["candidate_contracts"]
    for calculation in base_leg_calculations:
        contract = calculation.contract_key
        candidate_matches = tuple(
            candidate
            for candidate in tail_candidates
            if (
                candidate["option_type"] == contract.option_type
                and candidate["strike"] == contract.strike
                and candidate["contract_multiplier"]
                == contract.contract_multiplier
                and candidate["currency"] == contract.currency
                and candidate["deliverable_id"] == contract.deliverable_id
            )
        )
        for candidate in candidate_matches:
            if (
                candidate["implied_volatility"] != calculation.base_iv
                or candidate["iv_record_id"]
                != calculation.implied_volatility_record_id
                or candidate["contract_reference_record_id"]
                != calculation.contract_reference_record_id
            ):
                raise ValueError(
                    "matching tail candidate differs from actual leg evidence"
                )

    if not scenarios:
        raise ValueError("scenarios must not be empty")
    if not any(item.valuation_time != "expiration" for item in scenarios):
        raise ValueError("at least one non-expiration scenario is required")
    identities = tuple(_scenario_identity_tuple(item) for item in scenarios)
    if len(set(identities)) != len(identities):
        raise ValueError("declared scenario identities must be unique")
    ordering = tuple(
        _scenario_order_key(structure, as_of_date, item) for item in scenarios
    )
    if ordering != tuple(sorted(ordering)):
        raise ValueError("declared scenarios must already be canonical")
    if any(
        _scenario_valuation_date(structure, as_of_date, item) > expiration
        for item in scenarios
    ):
        raise ValueError("declared scenario resolves after expiration")
    if scenario_grid_complete:
        groups = {}
        for scenario in scenarios:
            groups.setdefault(
                (scenario.valuation_time, scenario.days_forward), set()
            ).add((
                decimal.Decimal(str(scenario.underlying_move)),
                decimal.Decimal(str(scenario.iv_change)),
            ))
        expected_grid = {
            (move, iv_change)
            for move in _SCENARIO_GRID_MOVES
            for iv_change in _SCENARIO_GRID_IV_CHANGES
        }
        if any(values != expected_grid for values in groups.values()):
            raise ValueError(
                "complete scenario groups must equal the frozen 7 by 4 grid"
            )

    if len(exit_cost_assumptions) != len(scenarios):
        raise ValueError("one exit-cost assumption is required per scenario")
    exit_costs = []
    for declared, assumption in zip(scenarios, exit_cost_assumptions):
        if type(assumption) is not tuple:
            raise TypeError("every exit-cost assumption must be an exact tuple")
        if len(assumption) != 2:
            raise ValueError("every exit-cost assumption must contain two items")
        if type(assumption[0]) is not Scenario:
            raise TypeError("exit-cost scenario must have exact type Scenario")
        if assumption[0] is not declared:
            raise ValueError("exit-cost scenario must be the declared object")
        if type(assumption[1]) is not decimal.Decimal:
            raise TypeError("exit cost must have exact type Decimal")
        if not assumption[1].is_finite() or assumption[1] < 0:
            raise ValueError("exit cost must be finite and nonnegative")
        exit_costs.append(assumption[1])
    exit_cost_methodology = _scenario_pricing_string(
        "exit_cost_methodology", exit_cost_methodology
    )

    provider_by_identity = {
        _scenario_identity_tuple(record.scenario): record
        for record in pricing.records
    }
    nonexpiration = tuple(
        scenario for scenario in scenarios
        if scenario.valuation_time != "expiration"
    )
    if set(provider_by_identity) != {
        _scenario_identity_tuple(scenario) for scenario in nonexpiration
    }:
        raise ValueError(
            "provider records must equal declared non-expiration scenarios"
        )

    arithmetic_context = decimal.Context(
        prec=34, rounding=decimal.ROUND_HALF_EVEN
    )
    prepared_values = []
    for scenario in scenarios:
        identity = _scenario_identity(scenario)
        valuation_date = _scenario_valuation_date(
            structure, as_of_date, scenario
        )
        try:
            shocked_underlying = arithmetic_context.multiply(
                base_underlying_exact,
                arithmetic_context.add(
                    decimal.Decimal(1), identity["underlying_move"]
                ),
            )
        except decimal.DecimalException as error:
            raise ValueError("scenario underlying shock failed") from error
        shocked_ivs = tuple(
            _scenario_pricing_shock(item.base_iv, scenario.iv_change)
            for item in base_leg_calculations
        )
        if scenario.valuation_time == "expiration":
            try:
                per_leg_payoffs = []
                for leg in structure.legs:
                    strike = decimal.Decimal(str(leg.strike))
                    intrinsic = (
                        arithmetic_context.subtract(shocked_underlying, strike)
                        if leg.option_type == "call"
                        else arithmetic_context.subtract(strike, shocked_underlying)
                    )
                    intrinsic = max(intrinsic, decimal.Decimal(0))
                    per_leg_payoffs.append(arithmetic_context.multiply(
                        intrinsic,
                        arithmetic_context.multiply(
                            decimal.Decimal(leg.quantity),
                            decimal.Decimal(leg.contract_multiplier),
                        ),
                    ))
                per_leg_payoffs = tuple(per_leg_payoffs)
                gross = decimal.Decimal(0)
                for payoff in per_leg_payoffs:
                    gross = arithmetic_context.add(gross, payoff)
            except decimal.DecimalException as error:
                raise ValueError("expiration payoff calculation failed") from error
            remaining_days = 0
            valuation_source = "terminal_intrinsic_expiration"
        else:
            provider = provider_by_identity[_scenario_identity_tuple(scenario)]
            if (
                provider.scenario is not scenario
                or provider.structure != structure
                or provider.as_of_date != as_of_date
                or provider.valuation_date != valuation_date
                or provider.base_underlying_price != base_underlying_exact
                or provider.shocked_underlying_price != shocked_underlying
                or tuple(
                    item.base_iv for item in provider.leg_calculations
                ) != tuple(item.base_iv for item in base_leg_calculations)
                or tuple(
                    item.shocked_iv for item in provider.leg_calculations
                ) != shocked_ivs
            ):
                raise ValueError(
                    "provider scenario does not exactly match declaration"
                )
            gross = provider.estimated_gross_position_value
            remaining_days = (
                expiration - provider.valuation_date
            ).days
            per_leg_payoffs = ()
            valuation_source = "authoritative_provider_nonexpiration"
        prepared_values.append((
            identity,
            valuation_date,
            shocked_underlying,
            shocked_ivs,
            gross,
            remaining_days,
            per_leg_payoffs,
            valuation_source,
        ))

    leg_volatility_inputs = tuple(
        LegVolatilityInput(
            item.leg, _finite_float_from_decimal("base IV", item.base_iv)
        )
        for item in base_leg_calculations
    )
    records = []
    calculation_values = []
    cost_dependency = _calculated_dependency_disclosure(
        costs.lineage,
        {
            "structure_identity": cost_decoded["structure_identity"],
            "as_of_date": as_of_date,
            "underlying_price_exact": base_underlying_exact,
            "underlying_price_repr": cost_values["stable_record_values"][
                "underlying_price_repr"
            ],
            "quoted_mid_premium_exact": cost_values[
                "quoted_mid_premium_exact"
            ],
            "estimated_spread_cost_exact": cost_values[
                "estimated_spread_cost_exact"
            ],
            "commissions_and_fees_exact": cost_values[
                "commissions_and_fees_exact"
            ],
            "total_entry_cost_exact": cost_values["total_entry_cost_exact"],
            "maximum_loss_exact": cost_values["maximum_loss_exact"],
            "total_entry_cost_repr": cost_values["stable_record_values"][
                "total_entry_cost_repr"
            ],
        },
    )
    tail_dependency = _calculated_dependency_disclosure(
        tail.lineage,
        {
            "underlying": tail.records[0].underlying,
            "as_of_date": tail.records[0].as_of_date,
            "ordered_expirations": tuple(
                record.expiration for record in tail.records
            ),
            "structure_expiration_match": expiration,
            "matching_candidate_details": tuple(
                candidate
                for candidate in tail_candidates
                if any(
                    candidate["option_type"] == item.contract_key.option_type
                    and candidate["strike"] == item.contract_key.strike
                    and candidate["contract_multiplier"]
                    == item.contract_key.contract_multiplier
                    and candidate["currency"] == item.contract_key.currency
                    and candidate["deliverable_id"]
                    == item.contract_key.deliverable_id
                    for item in base_leg_calculations
                )
            ),
        },
    )
    methodology = pricing_common.pricing_methodology
    pricing_dependency = _calculated_dependency_disclosure(
        pricing.lineage,
        {
            "structure_identity": _scenario_pricing_structure_identity(
                pricing_common
            ),
            "as_of_date": as_of_date,
            "base_underlying_price": pricing_common.base_underlying_price,
            "actual_leg_iv_tuple": _scenario_pricing_leg_correspondence(
                pricing_common
            ),
            "declared_nonexpiration_scenarios": tuple(
                _scenario_identity(record.scenario)
                for record in pricing.records
            ),
            "producer_identity": {
                "producer_name": methodology.producer_name,
                "producer_version": methodology.producer_version,
                "request_id": methodology.pricing_request_id,
                "payload_sha256": methodology.pricing_payload_sha256,
                "pricing_model_name": methodology.pricing_model_name,
                "pricing_model_version": methodology.pricing_model_version,
            },
        },
    )

    for scenario, exit_cost, prepared in zip(
        scenarios, exit_costs, prepared_values
    ):
        (
            identity,
            valuation_date,
            shocked_underlying,
            shocked_ivs,
            gross,
            remaining_days,
            per_leg_payoffs,
            valuation_source,
        ) = prepared
        if scenario.valuation_time == "expiration":
            provider_disclosure = {
                "status": "inactive_for_expiration",
                "external_expiration_value": "prohibited",
            }
        else:
            provider_disclosure = {
                "status": "active_authoritative_provider_calculated",
                "calculation_id": pricing.lineage.calculation_id,
                "producer_name": methodology.producer_name,
                "producer_version": methodology.producer_version,
                "request_id": methodology.pricing_request_id,
                "payload_sha256": methodology.pricing_payload_sha256,
                "producer_calculated_at": methodology.producer_calculated_at,
                "pricing_model_name": methodology.pricing_model_name,
                "pricing_model_version": methodology.pricing_model_version,
                "rate_methodology": _scenario_pricing_methodology_sections(
                    methodology
                )[3],
                "dividend_methodology": _scenario_pricing_methodology_sections(
                    methodology
                )[4],
                "surface_treatment": methodology.volatility_surface_treatment,
                "skew_treatment": methodology.skew_treatment,
                "term_treatment": methodology.term_treatment,
                "interpolation_treatment": methodology.volatility_interpolation,
                "settlement_treatment": methodology.settlement_treatment,
                "remaining_time_rule": methodology.remaining_time_rule,
                "position_scaling_rule": methodology.position_scaling_rule,
                "numerical_boundary": (
                    methodology.numerical_calculation_boundary
                ),
            }
        record_methodology = canonicalize_lineage_parameters({
            "schema_version": "v0.1",
            "valuation_source": valuation_source,
            "scenario_identity": identity,
            "structure_costs_dependency": {
                "calculation_id": costs.lineage.calculation_id,
                "identity": ("structure_costs", "exact-structure-costs", "v0.2"),
            },
            "tail_pricing_dependency": {
                "calculation_id": tail.lineage.calculation_id,
                "identity": (
                    "tail_pricing",
                    "nearest-observed-delta-wing-tail-relative-pricing",
                    "v0.2",
                ),
                "use": "context_only",
            },
            "scenario_pricing_dependency": {
                "calculation_id": pricing.lineage.calculation_id,
                "identity": (
                    "nonexpiration_scenario_pricing",
                    "authoritative-provider-option-scenario-pricing-evidence",
                    "v0.1",
                ),
            },
            "provider_disclosure": provider_disclosure,
            "nonexpiration_rule": {
                "active": scenario.valuation_time != "expiration",
                "rule": "consume_authoritative_gross_value_without_repricing",
            },
            "expiration_rule": {
                "active": scenario.valuation_time == "expiration",
                "call_formula": "max(shocked_underlying-strike,0)*quantity*multiplier",
                "put_formula": "max(strike-shocked_underlying,0)*quantity*multiplier",
                "iv_effect": "none_base_leg_ivs_retained_for_audit",
                "external_expiration_value": "prohibited",
            },
            "base_underlying_source": (
                "StructureCosts_v0.2_underlying_price_exact"
            ),
            "base_iv_source": (
                "ScenarioPricing_v0.1_actual_structure_leg_iv_evidence"
            ),
            "entry_cost_rule": (
                "StructureCosts_v0.2_stable_total_entry_cost_float"
            ),
            "exit_cost_rule": {
                "methodology": exit_cost_methodology,
                "source": "explicit_scenario_specific_decimal_assumption",
            },
            "float_conversion_rule": (
                "convert_base_iv_gross_and_exit_cost_once_to_finite_float"
            ),
            "limitations": (
                "Internal consistency is validated; self-consistent fabricated "
                "dependency artifacts are not cryptographically authenticated."
            ),
        })
        record = ScenarioResult(
            structure=structure,
            as_of_date=as_of_date,
            scenario=scenario,
            valuation_date=valuation_date,
            base_underlying_price=costs.record.underlying_price,
            leg_volatility_inputs=leg_volatility_inputs,
            estimated_position_value=_finite_float_from_decimal(
                "gross position value", gross
            ),
            entry_cost_basis=costs.record.total_entry_cost,
            estimated_exit_cost=_finite_float_from_decimal(
                "exit cost", exit_cost
            ),
            pricing_methodology=record_methodology,
        )
        if (
            not record.loss_is_within_entry_cost
            or record.pnl_after_costs < -record.entry_cost_basis
        ):
            raise ValueError("ScenarioResult violates bounded-loss behavior")
        records.append(record)
        calculation_values.append({
            "scenario_identity": identity,
            "valuation_date": valuation_date,
            "valuation_source": valuation_source,
            "base_underlying_exact": base_underlying_exact,
            "shocked_underlying_exact": shocked_underlying,
            "base_leg_ivs_exact": tuple(
                item.base_iv for item in base_leg_calculations
            ),
            "shocked_leg_ivs_exact": shocked_ivs,
            "remaining_calendar_days": remaining_days,
            "gross_position_value_exact": gross,
            "exit_cost_assumption_exact": exit_cost,
            "expiration_per_leg_payoffs_exact": per_leg_payoffs,
            "stable_gross_value_repr": repr(record.estimated_position_value),
            "stable_exit_cost_repr": repr(record.estimated_exit_cost),
            "stable_base_underlying_repr": repr(record.base_underlying_price),
            "stable_entry_cost_repr": repr(record.entry_cost_basis),
            "stable_net_liquidation_repr": repr(
                record.net_liquidation_value
            ),
            "stable_after_cost_pnl_repr": repr(record.pnl_after_costs),
            "stable_return_on_entry_cost_repr": repr(
                record.return_on_entry_cost
            ),
            "loss_is_within_entry_cost": record.loss_is_within_entry_cost,
            "pricing_methodology": record.pricing_methodology,
        })

    input_by_id = {}
    for lineage in dependency_lineages:
        for item in lineage.inputs:
            existing = input_by_id.get(item.record_id)
            if existing is not None and existing != item:
                raise ValueError(
                    "overlapping lineage references must be exactly equal"
                )
            input_by_id[item.record_id] = item
    inputs = tuple(input_by_id.values())
    parameters = {
        "output_architecture": {
            "result_type": "ScenarioValuationTransformationResult",
            "records": "ordered_ScenarioResult_tuple",
            "lineage": "one_shared_CalculationLineage",
        },
        "supported_structure_scope": {
            "included": (
                "one_long_call",
                "one_long_put",
                "one_long_straddle",
                "positive_long_quantities",
                "one_common_underlying",
                "one_common_expiration",
            ),
            "excluded": ("shorts", "spreads", "exotics"),
        },
        "scenario_declaration": {
            "ordered_scenarios": tuple(
                _scenario_identity(item) for item in scenarios
            ),
            "scenario_grid_complete": scenario_grid_complete,
        },
        "scenario_grid_semantics": {
            "underlying_moves": _SCENARIO_GRID_MOVES,
            "relative_iv_changes": _SCENARIO_GRID_IV_CHANGES,
            "complete_rule": "exact_cartesian_product_per_time_group",
            "false_rule": "explicitly_disclosed_subset",
        },
        "scenario_ordering": {
            "keys": (
                "valuation_date",
                "valuation_time_rank",
                "days_forward",
                "underlying_move_decimal",
                "iv_change_decimal",
            ),
            "valuation_time_rank": dict(_SCENARIO_TIME_RANK),
        },
        "valuation_date_rules": {
            "immediate": "as_of_date",
            "days_forward": "as_of_date_plus_days_forward_calendar_days",
            "holding_horizon": "as_of_date_plus_expected_holding_days",
            "expiration": "common_expiration",
        },
        "underlying_shock_rule": (
            "exact_base_underlying_times_one_plus_decimal_string_move"
        ),
        "iv_shock_rule": (
            "actual_leg_base_iv_times_one_plus_decimal_string_iv_change"
        ),
        "structure_costs_dependency": cost_dependency,
        "tail_pricing_dependency": tail_dependency,
        "scenario_pricing_dependency": pricing_dependency,
        "cross_dependency_consistency": {
            "structure": "exact_equal",
            "underlying": "exact_equal",
            "as_of_date": "exact_equal",
            "expiration": "exactly_one_tail_match",
            "leg_identity_and_multiplier": "exact_equal",
        },
        "base_underlying_rule": {
            "exact_source": "StructureCosts_v0.2_calculation_values",
            "scenario_result_source": "StructureCosts_stable_float",
        },
        "base_iv_rule": (
            "ScenarioPricing_v0.1_actual_leg_evidence_in_public_leg_order"
        ),
        "nonexpiration_valuation_rule": (
            "consume_authoritative_provider_gross_value_without_repricing"
        ),
        "expiration_payoff_rule": {
            "arithmetic": "Decimal_precision_34_ROUND_HALF_EVEN",
            "call": "max(shocked_underlying-strike,0)*quantity*multiplier",
            "put": "max(strike-shocked_underlying,0)*quantity*multiplier",
            "iv_independent": True,
            "external_value": "prohibited",
        },
        "entry_cost_rule": (
            "StructureCosts_v0.2_stable_total_entry_cost_float"
        ),
        "exit_cost_assumptions": {
            "methodology": exit_cost_methodology,
            "ordered_values": tuple({
                "scenario_identity": _scenario_identity(scenario),
                "exit_cost": value,
            } for scenario, value in zip(scenarios, exit_costs)),
        },
        "net_liquidation_rule": "max(gross_position_value-exit_cost,0.0)",
        "bounded_loss_rule": (
            "pnl_after_costs_not_less_than_negative_entry_cost"
        ),
        "record_methodology_disclosure": {
            "schema_keys": tuple(sorted(_SCENARIO_METHODOLOGY_KEYS)),
            "serializer": "canonicalize_lineage_parameters",
        },
        "calculation_values": tuple(calculation_values),
        "lineage_union_rule": {
            "exact_overlap": "deduplicate",
            "conflicting_overlap": "reject",
            "calculated_dependencies_are_not_inputs": True,
        },
        "float_conversion_rule": {
            "decimal_context": "precision_34_ROUND_HALF_EVEN",
            "converted": ("base_leg_iv", "gross_position_value", "exit_cost"),
            "stable_cost_floats": (
                "base_underlying_price",
                "entry_cost_basis",
            ),
            "finite_required": True,
        },
        "limitations": (
            "Validates internal consistency, not cryptographic authenticity; "
            "probabilities, expected returns, screening, recommendations, "
            "sizing, and execution are outside scope."
        ),
    }
    parameters_json = canonicalize_lineage_parameters(parameters)
    flags = {
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    for lineage in dependency_lineages:
        flags.update(
            flag
            for flag in lineage.quality_flags
            if flag in _SCENARIO_VALUATION_PROPAGATED_FLAGS
        )
    lineage = _construct_scenario_valuation_lineage(
        normalized_id,
        normalized_at,
        inputs,
        parameters_json,
        tuple(
            flag for flag in CalculationQualityFlag if flag in flags
        ),
    )
    return ScenarioValuationTransformationResult(tuple(records), lineage)


_EXPIRATION_THRESHOLD_MULTIPLES = (1, 2, 5, 10)
_EXPIRATION_THRESHOLD_PARAMETER_KEYS = {
    "schema_version",
    "output_architecture",
    "supported_structure_scope",
    "target_multiples",
    "threshold_ordering",
    "numeric_representation",
    "payoff_threshold_rules",
    "move_rules",
    "solution_domain",
    "structure_costs_dependency",
    "calculation_values",
    "limitations",
}
_EXPIRATION_THRESHOLD_DEPENDENCY_KEYS = {
    "calculation_id",
    "calculation_type",
    "methodology_id",
    "methodology_version",
    "calculated_at",
    "parameters_json",
    "quality_flags",
    "input_rule",
}
_EXPIRATION_THRESHOLD_VALUE_KEYS = {
    "position_value_multiple",
    "side",
    "status",
    "strike_exact",
    "position_scale",
    "target_position_value",
    "payoff_distance",
    "unconstrained_threshold_underlying_price",
    "threshold_underlying_price",
    "absolute_move_from_base",
    "relative_move_from_base",
}
_EXPIRATION_THRESHOLD_RATIONAL_KEYS = {"numerator", "denominator"}
_EXPIRATION_THRESHOLD_PROPAGATED_FLAGS = {
    CalculationQualityFlag.INTERPOLATED,
    CalculationQualityFlag.CORRECTION_SELECTED,
    CalculationQualityFlag.COMPOSITE_INPUT_USED,
}
_EXPIRATION_THRESHOLD_PROHIBITED_FLAGS = {
    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
    CalculationQualityFlag.ANNUALIZED,
    CalculationQualityFlag.ADJUSTED_INPUT_USED,
    CalculationQualityFlag.INCOMPLETE_INPUT_USED,
}


@dataclass(frozen=True)
class ExactRational:
    """One canonical, immutable exact rational number."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int:
            raise TypeError("numerator must have exact type int")
        if type(self.denominator) is not int:
            raise TypeError("denominator must have exact type int")
        if self.denominator <= 0:
            raise ValueError("denominator must be strictly positive")
        if self.numerator == 0:
            object.__setattr__(self, "denominator", 1)
            return
        divisor = math.gcd(abs(self.numerator), self.denominator)
        object.__setattr__(self, "numerator", self.numerator // divisor)
        object.__setattr__(self, "denominator", self.denominator // divisor)


def _exact_rational_from_decimal(value: object) -> ExactRational:
    if type(value) is not decimal.Decimal:
        raise TypeError("exact rational source must have exact type Decimal")
    if not value.is_finite():
        raise ValueError("exact rational source must be finite")
    sign, digits, exponent = value.as_tuple()
    coefficient = 0
    try:
        for digit in digits:
            coefficient = coefficient * 10 + digit
        if exponent >= 0:
            numerator = coefficient * (10 ** exponent)
            denominator = 1
        else:
            numerator = coefficient
            denominator = 10 ** (-exponent)
    except (MemoryError, OverflowError) as error:
        raise ValueError(
            "Decimal cannot be represented as an exact rational"
        ) from error
    if sign:
        numerator = -numerator
    return ExactRational(numerator, denominator)


def _rational_add(left: ExactRational, right: ExactRational) -> ExactRational:
    return ExactRational(
        left.numerator * right.denominator
        + right.numerator * left.denominator,
        left.denominator * right.denominator,
    )


def _rational_subtract(
    left: ExactRational, right: ExactRational
) -> ExactRational:
    return ExactRational(
        left.numerator * right.denominator
        - right.numerator * left.denominator,
        left.denominator * right.denominator,
    )


def _rational_multiply_int(
    value: ExactRational, multiplier: int
) -> ExactRational:
    return ExactRational(value.numerator * multiplier, value.denominator)


def _rational_multiply(
    left: ExactRational, right: ExactRational
) -> ExactRational:
    return ExactRational(
        left.numerator * right.numerator,
        left.denominator * right.denominator,
    )


def _rational_divide_int(
    value: ExactRational, divisor: int
) -> ExactRational:
    if type(divisor) is not int:
        raise TypeError("rational divisor must have exact type int")
    if divisor <= 0:
        raise ValueError("rational divisor must be strictly positive")
    return ExactRational(value.numerator, value.denominator * divisor)


def _rational_divide(
    numerator: ExactRational, denominator: ExactRational
) -> ExactRational:
    if denominator.numerator == 0:
        raise ValueError("exact rational divisor must be nonzero")
    sign = -1 if denominator.numerator < 0 else 1
    return ExactRational(
        numerator.numerator * denominator.denominator * sign,
        numerator.denominator * abs(denominator.numerator),
    )


class ExpirationPayoffThresholdSide(str, Enum):
    DOWNSIDE = "downside"
    UPSIDE = "upside"


class ExpirationPayoffThresholdStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE_NEGATIVE_UNDERLYING_PRICE = (
        "unavailable_negative_underlying_price"
    )


@dataclass(frozen=True)
class ExpirationPayoffThreshold:
    position_value_multiple: int
    side: ExpirationPayoffThresholdSide
    status: ExpirationPayoffThresholdStatus
    target_position_value: ExactRational
    threshold_underlying_price: Optional[ExactRational]
    absolute_move_from_base: Optional[ExactRational]
    relative_move_from_base: Optional[ExactRational]

    def __post_init__(self) -> None:
        if type(self.position_value_multiple) is not int:
            raise TypeError("position_value_multiple must have exact type int")
        if self.position_value_multiple not in _EXPIRATION_THRESHOLD_MULTIPLES:
            raise ValueError("position_value_multiple is unsupported")
        if type(self.side) is not ExpirationPayoffThresholdSide:
            raise TypeError(
                "side must have exact type ExpirationPayoffThresholdSide"
            )
        if type(self.status) is not ExpirationPayoffThresholdStatus:
            raise TypeError(
                "status must have exact type ExpirationPayoffThresholdStatus"
            )
        if type(self.target_position_value) is not ExactRational:
            raise TypeError(
                "target_position_value must have exact type ExactRational"
            )
        target_position_value = _strict_expiration_exact_rational(
            self.target_position_value, "target_position_value"
        )
        if target_position_value.numerator <= 0:
            raise ValueError("target_position_value must be strictly positive")
        optional_values = (
            self.threshold_underlying_price,
            self.absolute_move_from_base,
            self.relative_move_from_base,
        )
        if self.status is ExpirationPayoffThresholdStatus.AVAILABLE:
            if any(type(value) is not ExactRational for value in optional_values):
                raise TypeError(
                    "available threshold values must have exact type ExactRational"
                )
            threshold_underlying_price = _strict_expiration_exact_rational(
                self.threshold_underlying_price,
                "threshold_underlying_price",
            )
            _strict_expiration_exact_rational(
                self.absolute_move_from_base,
                "absolute_move_from_base",
            )
            _strict_expiration_exact_rational(
                self.relative_move_from_base,
                "relative_move_from_base",
            )
            if threshold_underlying_price.numerator < 0:
                raise ValueError(
                    "available threshold_underlying_price must be nonnegative"
                )
        else:
            if self.side is not ExpirationPayoffThresholdSide.DOWNSIDE:
                raise ValueError(
                    "unavailable negative-price status requires downside"
                )
            if any(value is not None for value in optional_values):
                raise ValueError(
                    "unavailable threshold must publish no threshold or moves"
                )


def _strict_expiration_exact_rational(
    value: object, label: str
) -> ExactRational:
    if type(value) is not ExactRational:
        raise TypeError(f"{label} must have exact type ExactRational")
    if type(value.numerator) is not int:
        raise TypeError(f"{label} numerator must have exact type int")
    if type(value.denominator) is not int:
        raise TypeError(f"{label} denominator must have exact type int")
    rebuilt = ExactRational(value.numerator, value.denominator)
    if (
        value.numerator != rebuilt.numerator
        or value.denominator != rebuilt.denominator
    ):
        raise ValueError(f"{label} must be a canonical reduced rational")
    return rebuilt


def _strict_expiration_option_leg(value: object) -> OptionLeg:
    if type(value) is not OptionLeg:
        raise TypeError("every structure leg must have exact type OptionLeg")
    if type(value.underlying) is not str:
        raise TypeError("leg underlying must have exact type str")
    if (
        not value.underlying
        or value.underlying.strip().upper() != value.underlying
    ):
        raise ValueError("leg underlying must be nonempty normalized text")
    if type(value.option_type) is not str:
        raise TypeError("leg option_type must have exact type str")
    if (
        value.option_type not in ("call", "put")
        or value.option_type.strip().lower() != value.option_type
    ):
        raise ValueError("leg option_type must be canonical")
    if type(value.strike) not in (int, float):
        raise TypeError("leg strike must be an exact real scalar")
    if not math.isfinite(value.strike) or value.strike <= 0:
        raise ValueError("leg strike must be finite and strictly positive")
    if type(value.expiration) is not datetime.date:
        raise TypeError("leg expiration must have exact type date")
    if type(value.quantity) is not int:
        raise TypeError("leg quantity must have exact type int")
    if value.quantity <= 0:
        raise ValueError("leg quantity must be strictly positive")
    if type(value.contract_multiplier) is not int:
        raise TypeError("leg contract_multiplier must have exact type int")
    if value.contract_multiplier <= 0:
        raise ValueError("leg contract_multiplier must be strictly positive")
    rebuilt = OptionLeg(
        value.underlying,
        value.option_type,
        value.strike,
        value.expiration,
        value.quantity,
        value.contract_multiplier,
    )
    if (
        rebuilt.underlying != value.underlying
        or rebuilt.option_type != value.option_type
        or type(rebuilt.strike) is not type(value.strike)
        or rebuilt.strike != value.strike
        or rebuilt.expiration != value.expiration
        or rebuilt.quantity != value.quantity
        or rebuilt.contract_multiplier != value.contract_multiplier
    ):
        raise ValueError("leg constructor normalization changed forged input")
    return rebuilt


def _validate_expiration_threshold_structure(
    structure: object,
) -> OptionStructure:
    if type(structure) is not OptionStructure:
        raise TypeError("structure must have exact type OptionStructure")
    if type(structure.legs) is not tuple:
        raise TypeError("structure legs must have exact type tuple")
    if len(structure.legs) not in (1, 2):
        raise ValueError("structure must have one or two legs")
    rebuilt_legs = tuple(
        _strict_expiration_option_leg(leg) for leg in structure.legs
    )
    if type(structure.assumed_portfolio_value) not in (int, float):
        raise TypeError(
            "assumed_portfolio_value must be an exact real scalar"
        )
    if (
        not math.isfinite(structure.assumed_portfolio_value)
        or structure.assumed_portfolio_value <= 0
    ):
        raise ValueError(
            "assumed_portfolio_value must be finite and strictly positive"
        )
    if type(structure.expected_holding_days) is not int:
        raise TypeError("expected_holding_days must have exact type int")
    if structure.expected_holding_days < 0:
        raise ValueError("expected_holding_days must be nonnegative")
    rebuilt = OptionStructure(
        rebuilt_legs,
        structure.assumed_portfolio_value,
        structure.expected_holding_days,
    )
    if (
        type(rebuilt.assumed_portfolio_value)
        is not type(structure.assumed_portfolio_value)
        or rebuilt.assumed_portfolio_value
        != structure.assumed_portfolio_value
        or rebuilt.expected_holding_days
        != structure.expected_holding_days
        or len(rebuilt.legs) != len(structure.legs)
    ):
        raise ValueError(
            "structure constructor normalization changed forged input"
        )
    return structure


def _strict_expiration_threshold(
    value: object,
) -> ExpirationPayoffThreshold:
    if type(value) is not ExpirationPayoffThreshold:
        raise TypeError(
            "every threshold must have exact type ExpirationPayoffThreshold"
        )
    if type(value.position_value_multiple) is not int:
        raise TypeError("position_value_multiple must have exact type int")
    if type(value.side) is not ExpirationPayoffThresholdSide:
        raise TypeError(
            "side must have exact type ExpirationPayoffThresholdSide"
        )
    if type(value.status) is not ExpirationPayoffThresholdStatus:
        raise TypeError(
            "status must have exact type ExpirationPayoffThresholdStatus"
        )
    target = _strict_expiration_exact_rational(
        value.target_position_value, "target_position_value"
    )

    def optional_rational(
        item: object, label: str
    ) -> Optional[ExactRational]:
        if item is None:
            return None
        return _strict_expiration_exact_rational(item, label)

    threshold = optional_rational(
        value.threshold_underlying_price, "threshold_underlying_price"
    )
    absolute = optional_rational(
        value.absolute_move_from_base, "absolute_move_from_base"
    )
    relative = optional_rational(
        value.relative_move_from_base, "relative_move_from_base"
    )
    return ExpirationPayoffThreshold(
        value.position_value_multiple,
        value.side,
        value.status,
        target,
        threshold,
        absolute,
        relative,
    )


def _expiration_rationals_match(
    actual: Optional[ExactRational],
    expected: Optional[ExactRational],
) -> bool:
    if actual is None or expected is None:
        return actual is None and expected is None
    return (
        type(actual) is ExactRational
        and type(expected) is ExactRational
        and type(actual.numerator) is int
        and type(actual.denominator) is int
        and actual.numerator == expected.numerator
        and actual.denominator == expected.denominator
    )


def _expiration_thresholds_match(
    actual: ExpirationPayoffThreshold,
    expected: ExpirationPayoffThreshold,
) -> bool:
    return (
        type(actual.position_value_multiple) is int
        and actual.position_value_multiple
        == expected.position_value_multiple
        and actual.side is expected.side
        and actual.status is expected.status
        and _expiration_rationals_match(
            actual.target_position_value,
            expected.target_position_value,
        )
        and _expiration_rationals_match(
            actual.threshold_underlying_price,
            expected.threshold_underlying_price,
        )
        and _expiration_rationals_match(
            actual.absolute_move_from_base,
            expected.absolute_move_from_base,
        )
        and _expiration_rationals_match(
            actual.relative_move_from_base,
            expected.relative_move_from_base,
        )
    )


class _PayoffMathGrammar(str, Enum):
    LONG_CALL = "long_call"
    LONG_PUT = "long_put"
    LONG_STRADDLE = "long_straddle"


class _PayoffMathBranch(str, Enum):
    DOWNSIDE = "downside"
    UPSIDE = "upside"


def _conditional_threshold_prices(
    grammar: _PayoffMathGrammar,
    strike: ExactRational,
    payoff_distance: ExactRational,
    multiples: tuple,
) -> tuple:
    """Return private canonical threshold branches for exact payoff geometry."""

    if type(grammar) is not _PayoffMathGrammar:
        raise TypeError("grammar must have exact type _PayoffMathGrammar")
    strike = _strict_expiration_exact_rational(strike, "strike")
    distance = _strict_expiration_exact_rational(
        payoff_distance, "payoff_distance"
    )
    if strike.numerator <= 0 or distance.numerator <= 0:
        raise ValueError("strike and payoff_distance must be strictly positive")
    if type(multiples) is not tuple or any(
        type(item) is not int for item in multiples
    ):
        raise TypeError("multiples must be a tuple of exact integers")
    if not multiples or any(item <= 0 for item in multiples):
        raise ValueError("multiples must be strictly positive")
    records = []
    for multiple in multiples:
        scaled = _rational_multiply_int(distance, multiple)
        if grammar is _PayoffMathGrammar.LONG_CALL:
            branches = ((
                _PayoffMathBranch.UPSIDE,
                _rational_add(strike, scaled),
            ),)
        elif grammar is _PayoffMathGrammar.LONG_PUT:
            branches = ((
                _PayoffMathBranch.DOWNSIDE,
                _rational_subtract(strike, scaled),
            ),)
        else:
            branches = (
                (
                    _PayoffMathBranch.DOWNSIDE,
                    _rational_subtract(strike, scaled),
                ),
                (
                    _PayoffMathBranch.UPSIDE,
                    _rational_add(strike, scaled),
                ),
            )
        for branch, unconstrained in branches:
            records.append((
                multiple,
                branch,
                None if unconstrained.numerator < 0 else unconstrained,
            ))
    return tuple(records)


def _gross_expiration_payoff(
    grammar: _PayoffMathGrammar,
    strike: ExactRational,
    terminal_underlying_price: ExactRational,
) -> ExactRational:
    """Return exact scalar terminal intrinsic payoff for private grammar."""

    if type(grammar) is not _PayoffMathGrammar:
        raise TypeError("grammar must have exact type _PayoffMathGrammar")
    strike = _strict_expiration_exact_rational(strike, "strike")
    terminal = _strict_expiration_exact_rational(
        terminal_underlying_price, "terminal_underlying_price"
    )
    if strike.numerator <= 0 or terminal.numerator < 0:
        raise ValueError("strike must be positive and terminal price nonnegative")
    difference = _rational_subtract(terminal, strike)
    if grammar is _PayoffMathGrammar.LONG_CALL:
        return difference if difference.numerator > 0 else ExactRational(0, 1)
    if grammar is _PayoffMathGrammar.LONG_PUT:
        return ExactRational(-difference.numerator, difference.denominator) \
            if difference.numerator < 0 else ExactRational(0, 1)
    return ExactRational(abs(difference.numerator), difference.denominator)


def _expected_expiration_thresholds(
    structure: OptionStructure,
    base_underlying_price: decimal.Decimal,
    total_entry_cost: decimal.Decimal,
) -> Tuple[ExpirationPayoffThreshold, ...]:
    strike = _exact_rational_from_decimal(
        decimal.Decimal(str(structure.legs[0].strike))
    )
    base = _exact_rational_from_decimal(base_underlying_price)
    cost = _exact_rational_from_decimal(total_entry_cost)
    position_scale = (
        structure.legs[0].quantity
        * structure.legs[0].contract_multiplier
    )
    grammar = {
        "long_call": _PayoffMathGrammar.LONG_CALL,
        "long_put": _PayoffMathGrammar.LONG_PUT,
        "long_straddle": _PayoffMathGrammar.LONG_STRADDLE,
    }[structure.structure_type]
    one_x_distance = _rational_divide_int(cost, position_scale)
    branches = _conditional_threshold_prices(
        grammar,
        strike,
        one_x_distance,
        _EXPIRATION_THRESHOLD_MULTIPLES,
    )
    records = []
    for multiple, branch, unconstrained in branches:
        target = _rational_multiply_int(cost, multiple)
        side = (
            ExpirationPayoffThresholdSide.DOWNSIDE
            if branch is _PayoffMathBranch.DOWNSIDE
            else ExpirationPayoffThresholdSide.UPSIDE
        )
        if unconstrained is None:
            records.append(ExpirationPayoffThreshold(
                multiple,
                side,
                ExpirationPayoffThresholdStatus
                .UNAVAILABLE_NEGATIVE_UNDERLYING_PRICE,
                target,
                None,
                None,
                None,
            ))
            continue
        absolute = _rational_subtract(unconstrained, base)
        relative = _rational_divide(absolute, base)
        records.append(ExpirationPayoffThreshold(
            multiple,
            side,
            ExpirationPayoffThresholdStatus.AVAILABLE,
            target,
            unconstrained,
            absolute,
            relative,
        ))
    return tuple(records)


@dataclass(frozen=True)
class ExpirationPayoffThresholdEvidence:
    structure: OptionStructure
    as_of_date: datetime.date
    base_underlying_price: decimal.Decimal
    total_entry_cost: decimal.Decimal
    thresholds: Tuple[ExpirationPayoffThreshold, ...]

    def __post_init__(self) -> None:
        with decimal.localcontext():
            structure = _validate_expiration_threshold_structure(self.structure)
            if type(self.as_of_date) is not datetime.date:
                raise TypeError("as_of_date must have exact type date")
            if type(self.base_underlying_price) is not decimal.Decimal:
                raise TypeError(
                    "base_underlying_price must have exact type Decimal"
                )
            if type(self.total_entry_cost) is not decimal.Decimal:
                raise TypeError("total_entry_cost must have exact type Decimal")
            if (
                not self.base_underlying_price.is_finite()
                or self.base_underlying_price <= 0
                or not self.total_entry_cost.is_finite()
                or self.total_entry_cost <= 0
            ):
                raise ValueError(
                    "base_underlying_price and total_entry_cost "
                    "must be finite and strictly positive"
                )
            if any(
                self.as_of_date >= leg.expiration for leg in structure.legs
            ):
                raise ValueError("as_of_date must precede every expiration")
            if type(self.thresholds) is not tuple:
                raise TypeError("thresholds must have exact type tuple")
            validated_thresholds = tuple(
                _strict_expiration_threshold(item)
                for item in self.thresholds
            )
            expected = _expected_expiration_thresholds(
                structure,
                self.base_underlying_price,
                self.total_entry_cost,
            )
            if (
                len(validated_thresholds) != len(expected)
                or any(
                    not _expiration_thresholds_match(actual, expected_item)
                    for actual, expected_item in zip(
                        validated_thresholds, expected
                    )
                )
            ):
                raise ValueError(
                    "thresholds do not match complete canonical mathematics"
                )


def _rational_mapping(value: ExactRational) -> dict:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
    }


def _optional_rational_mapping(value: Optional[ExactRational]) -> object:
    return None if value is None else _rational_mapping(value)


def _expiration_threshold_fixed_parameters() -> dict:
    return {
        "schema_version": "expiration-payoff-thresholds-v0.1",
        "output_architecture": (
            "single_expiration_payoff_threshold_evidence_record"
        ),
        "supported_structure_scope": (
            "long_call",
            "long_put",
            "long_straddle_same_strike_expiration_quantity_multiplier",
        ),
        "target_multiples": _EXPIRATION_THRESHOLD_MULTIPLES,
        "threshold_ordering": {
            "multiple_order": _EXPIRATION_THRESHOLD_MULTIPLES,
            "straddle_side_order": ("downside", "upside"),
            "unavailable_records_retain_position": True,
        },
        "numeric_representation": {
            "public_type": "ExactRational",
            "mapping_keys": ("numerator", "denominator"),
            "reduced": True,
            "positive_denominator": True,
            "decimal_conversion": "exact_coefficient_and_exponent",
            "float_prohibited": True,
            "rounding": "none",
        },
        "payoff_threshold_rules": {
            "position_value_multiple": (
                "expiration_gross_position_value/total_entry_cost"
            ),
            "target_position_value": "multiple*total_entry_cost",
            "payoff_distance": (
                "target_position_value/(quantity*contract_multiplier)"
            ),
            "long_call": "strike+payoff_distance",
            "long_put": "strike-payoff_distance",
            "long_straddle_downside": "strike-payoff_distance",
            "long_straddle_upside": "strike+payoff_distance",
            "exit_cost": "excluded",
        },
        "move_rules": {
            "absolute": "threshold_underlying_price-base_underlying_price",
            "relative": "absolute_move_from_base/base_underlying_price",
            "signed": True,
        },
        "solution_domain": {
            "underlying_price": "nonnegative",
            "zero_lower_threshold": "available",
            "negative_lower_threshold": (
                "unavailable_negative_underlying_price"
            ),
            "negative_published_threshold": "prohibited",
        },
        "limitations": (
            "Expiration intrinsic payoff evidence only; no probabilities, "
            "expected returns, recommendations, screening, position sizing, "
            "exit-cost adjustment, provider access, or pricing model."
        ),
    }


def _expiration_threshold_calculation_values(
    record: ExpirationPayoffThresholdEvidence,
) -> tuple:
    strike = _exact_rational_from_decimal(
        decimal.Decimal(str(record.structure.legs[0].strike))
    )
    scale = (
        record.structure.legs[0].quantity
        * record.structure.legs[0].contract_multiplier
    )
    values = []
    for threshold in record.thresholds:
        payoff_distance = _rational_divide_int(
            threshold.target_position_value, scale
        )
        unconstrained = (
            _rational_subtract(strike, payoff_distance)
            if threshold.side is ExpirationPayoffThresholdSide.DOWNSIDE
            else _rational_add(strike, payoff_distance)
        )
        values.append({
            "position_value_multiple": threshold.position_value_multiple,
            "side": threshold.side.value,
            "status": threshold.status.value,
            "strike_exact": _rational_mapping(strike),
            "position_scale": {
                "quantity": record.structure.legs[0].quantity,
                "contract_multiplier": (
                    record.structure.legs[0].contract_multiplier
                ),
                "underlying_units": scale,
            },
            "target_position_value": _rational_mapping(
                threshold.target_position_value
            ),
            "payoff_distance": _rational_mapping(payoff_distance),
            "unconstrained_threshold_underlying_price": (
                _rational_mapping(unconstrained)
            ),
            "threshold_underlying_price": _optional_rational_mapping(
                threshold.threshold_underlying_price
            ),
            "absolute_move_from_base": _optional_rational_mapping(
                threshold.absolute_move_from_base
            ),
            "relative_move_from_base": _optional_rational_mapping(
                threshold.relative_move_from_base
            ),
        })
    return tuple(values)


def _expiration_threshold_dependency_disclosure(
    lineage: CalculationLineage,
) -> dict:
    return {
        "calculation_id": lineage.calculation_id,
        "calculation_type": lineage.calculation_type,
        "methodology_id": lineage.methodology_id,
        "methodology_version": lineage.methodology_version,
        "calculated_at": lineage.calculated_at,
        "parameters_json": lineage.parameters_json,
        "quality_flags": tuple(flag.value for flag in lineage.quality_flags),
        "input_rule": "exact_reuse_of_structure_costs_lineage_inputs",
    }


def _expiration_threshold_parameters(
    record: ExpirationPayoffThresholdEvidence,
    dependency_lineage: CalculationLineage,
) -> dict:
    parameters = _expiration_threshold_fixed_parameters()
    parameters["structure_costs_dependency"] = (
        _expiration_threshold_dependency_disclosure(dependency_lineage)
    )
    parameters["calculation_values"] = (
        _expiration_threshold_calculation_values(record)
    )
    return parameters


def _decode_expiration_threshold_parameters(parameters_json: object) -> dict:
    if type(parameters_json) is not str:
        raise TypeError("parameters_json must have exact type str")

    def reject_float(_value: str) -> object:
        raise ValueError("expiration threshold parameters prohibit JSON floats")

    def reject_constant(_value: str) -> object:
        raise ValueError(
            "expiration threshold parameters prohibit nonfinite constants"
        )

    def unique_object(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(
                    "expiration threshold parameters contain duplicate JSON keys"
                )
            result[key] = value
        return result

    try:
        raw = json.loads(
            parameters_json,
            parse_float=reject_float,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError(
            "expiration threshold parameters_json is invalid"
        ) from error

    def decode(value: object) -> object:
        if value is None or type(value) in (bool, int, str):
            return value
        if type(value) is list:
            return tuple(decode(item) for item in value)
        if type(value) is not dict or len(value) != 1:
            raise ValueError("expiration threshold parameters use invalid JSON")
        tag, payload = next(iter(value.items()))
        if tag == "$map":
            if type(payload) is not list:
                raise ValueError("$map payload must be a list")
            result = {}
            for pair in payload:
                if (
                    type(pair) is not list
                    or len(pair) != 2
                    or type(pair[0]) is not str
                    or pair[0] in result
                ):
                    raise ValueError("$map entries must have unique string keys")
                result[pair[0]] = decode(pair[1])
            return result
        if tag == "$list":
            if type(payload) is not list:
                raise ValueError("$list payload must be a list")
            return tuple(decode(item) for item in payload)
        if tag == "$decimal":
            if type(payload) is not str:
                raise ValueError("$decimal payload must be a string")
            try:
                result = decimal.Decimal(payload)
            except decimal.InvalidOperation as error:
                raise ValueError("$decimal payload is invalid") from error
            if not result.is_finite():
                raise ValueError("$decimal payload must be finite")
            return result
        if tag == "$date":
            if type(payload) is not str:
                raise ValueError("$date payload must be a string")
            try:
                result = datetime.date.fromisoformat(payload)
            except ValueError as error:
                raise ValueError("$date payload is invalid") from error
            if result.isoformat() != payload:
                raise ValueError("$date payload is noncanonical")
            return result
        if tag == "$datetime":
            if type(payload) is not str or not payload.endswith("Z"):
                raise ValueError("$datetime payload must be canonical UTC")
            try:
                result = datetime.datetime.fromisoformat(
                    payload[:-1] + "+00:00"
                )
            except ValueError as error:
                raise ValueError("$datetime payload is invalid") from error
            if (
                result.isoformat(timespec="microseconds")
                .replace("+00:00", "Z") != payload
            ):
                raise ValueError("$datetime payload is noncanonical")
            return result
        raise ValueError("expiration threshold parameters contain unknown tag")

    decoded = decode(raw)
    if type(decoded) is not dict:
        raise ValueError("expiration threshold parameters root must be a map")
    if set(decoded) != _EXPIRATION_THRESHOLD_PARAMETER_KEYS:
        raise ValueError(
            "expiration threshold parameters have wrong exact 12-key schema"
        )
    try:
        if canonicalize_lineage_parameters(decoded) != parameters_json:
            raise ValueError(
                "expiration threshold parameters are not byte-canonical"
            )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "expiration threshold parameters are not canonical"
        ) from error
    calculation_values = decoded["calculation_values"]
    if type(calculation_values) is not tuple:
        raise TypeError("calculation_values must have exact type tuple")
    for item in calculation_values:
        if type(item) is not dict:
            raise TypeError(
                "every calculation_values item must have exact type dict"
            )
        if set(item) != _EXPIRATION_THRESHOLD_VALUE_KEYS:
            raise ValueError(
                "calculation_values item has wrong exact key schema"
            )
        if type(item["position_value_multiple"]) is not int:
            raise TypeError(
                "position_value_multiple must have exact type int"
            )
        if type(item["side"]) is not str:
            raise TypeError("calculation-value side must have exact type str")
        if type(item["status"]) is not str:
            raise TypeError(
                "calculation-value status must have exact type str"
            )
        for key in (
            "strike_exact",
            "target_position_value",
            "payoff_distance",
            "unconstrained_threshold_underlying_price",
        ):
            _validate_expiration_threshold_rational_mapping(item[key], key)
        for key in (
            "threshold_underlying_price",
            "absolute_move_from_base",
            "relative_move_from_base",
        ):
            if item[key] is not None:
                _validate_expiration_threshold_rational_mapping(
                    item[key], key
                )
        position_scale = item["position_scale"]
        if type(position_scale) is not dict:
            raise TypeError("position_scale must have exact type dict")
        if set(position_scale) != {
            "quantity",
            "contract_multiplier",
            "underlying_units",
        }:
            raise ValueError("position_scale has wrong exact key schema")
        if any(type(value) is not int for value in position_scale.values()):
            raise TypeError("position_scale values must have exact type int")
        if (
            position_scale["quantity"] <= 0
            or position_scale["contract_multiplier"] <= 0
            or position_scale["underlying_units"]
            != position_scale["quantity"]
            * position_scale["contract_multiplier"]
        ):
            raise ValueError("position_scale is invalid")
    return decoded


def _validate_exact_expiration_parameter_tree(
    actual: object,
    expected: object,
    path: str = "parameters",
) -> None:
    if type(actual) is not type(expected):
        raise TypeError(f"{path} has the wrong exact type")
    if type(expected) is dict:
        if set(actual) != set(expected):
            raise ValueError(f"{path} has the wrong exact key schema")
        for key in expected:
            _validate_exact_expiration_parameter_tree(
                actual[key], expected[key], f"{path}.{key}"
            )
        return
    if type(expected) is tuple:
        if len(actual) != len(expected):
            raise ValueError(f"{path} has the wrong cardinality")
        for index, (actual_item, expected_item) in enumerate(
            zip(actual, expected)
        ):
            _validate_exact_expiration_parameter_tree(
                actual_item, expected_item, f"{path}[{index}]"
            )
        return
    if actual != expected:
        raise ValueError(f"{path} has the wrong frozen value")


def _validate_expiration_threshold_rational_mapping(
    value: object, label: str
) -> None:
    if type(value) is not dict:
        raise TypeError(f"{label} must have exact type dict")
    if set(value) != _EXPIRATION_THRESHOLD_RATIONAL_KEYS:
        raise ValueError(f"{label} has wrong exact rational key schema")
    if (
        type(value["numerator"]) is not int
        or type(value["denominator"]) is not int
    ):
        raise TypeError(f"{label} rational fields must have exact type int")
    canonical = ExactRational(value["numerator"], value["denominator"])
    if _rational_mapping(canonical) != value:
        raise ValueError(f"{label} must be a reduced canonical rational")


def _expiration_threshold_dependency_from_disclosure(
    record: ExpirationPayoffThresholdEvidence,
    lineage: CalculationLineage,
    disclosure: object,
) -> StructureCostsTransformationResult:
    if type(disclosure) is not dict:
        raise TypeError("structure_costs_dependency must have exact type dict")
    if set(disclosure) != _EXPIRATION_THRESHOLD_DEPENDENCY_KEYS:
        raise ValueError(
            "structure_costs_dependency has wrong exact key schema"
        )
    if (
        disclosure["calculation_type"] != "structure_costs"
        or disclosure["methodology_id"] != "exact-structure-costs"
        or disclosure["methodology_version"] != "v0.2"
        or disclosure["input_rule"]
        != "exact_reuse_of_structure_costs_lineage_inputs"
    ):
        raise ValueError("structure_costs_dependency identity is invalid")
    quality_values = disclosure["quality_flags"]
    if type(quality_values) is not tuple:
        raise TypeError("dependency quality_flags must have exact type tuple")
    if any(type(item) is not str for item in quality_values):
        raise TypeError("dependency quality flag values must be exact strings")
    try:
        flags = tuple(CalculationQualityFlag(item) for item in quality_values)
    except ValueError as error:
        raise ValueError("dependency quality flag value is invalid") from error
    if len(set(flags)) != len(flags) or flags != tuple(
        flag for flag in CalculationQualityFlag if flag in set(flags)
    ):
        raise ValueError("dependency quality flags are not canonical")
    dependency_lineage = CalculationLineage(
        calculation_id=disclosure["calculation_id"],
        calculation_type=disclosure["calculation_type"],
        methodology_id=disclosure["methodology_id"],
        methodology_version=disclosure["methodology_version"],
        calculated_at=disclosure["calculated_at"],
        inputs=lineage.inputs,
        parameters_json=disclosure["parameters_json"],
        quality_flags=flags,
    )
    decoded_cost = _decode_cost_parameters(dependency_lineage.parameters_json)
    values = decoded_cost["calculation_values"]
    stable = values["stable_record_values"]
    methodology = decoded_cost["greeks_methodology"]
    cost_record = StructureCosts(
        structure=record.structure,
        as_of_date=record.as_of_date,
        quoted_mid_premium=_cost_stable_float_repr(
            stable["quoted_mid_premium_repr"], "quoted_mid_premium_repr"
        ),
        estimated_spread_cost=_cost_stable_float_repr(
            stable["estimated_spread_cost_repr"],
            "estimated_spread_cost_repr",
        ),
        commissions_and_fees=_cost_stable_float_repr(
            stable["commissions_and_fees_repr"],
            "commissions_and_fees_repr",
        ),
        theta_per_day=_cost_stable_float_repr(
            stable["theta_per_day_repr"], "theta_per_day_repr"
        ),
        gamma=_cost_stable_float_repr(
            stable["gamma_repr"], "gamma_repr"
        ),
        underlying_price=_cost_stable_float_repr(
            stable["underlying_price_repr"], "underlying_price_repr"
        ),
        greeks_methodology=_greeks_methodology_disclosure((
            methodology["model_name"],
            methodology["model_version"],
            methodology["rate_input_description"],
            methodology["dividend_input_description"],
            methodology["theta_day_basis"],
            methodology["unit_convention"],
        )),
        repeated_bet_count=decoded_cost["repeated_bet_count"],
    )
    return StructureCostsTransformationResult(cost_record, dependency_lineage)


def _validate_expiration_threshold_result(
    record: ExpirationPayoffThresholdEvidence,
    lineage: CalculationLineage,
) -> None:
    if (
        lineage.calculation_type != "expiration_payoff_thresholds"
        or lineage.methodology_id
        != "closed-form-terminal-intrinsic-position-value-multiples"
        or lineage.methodology_version != "v0.1"
    ):
        raise ValueError("expiration threshold lineage identity is invalid")
    decoded = _decode_expiration_threshold_parameters(
        lineage.parameters_json
    )
    dependency = _expiration_threshold_dependency_from_disclosure(
        record,
        lineage,
        decoded["structure_costs_dependency"],
    )
    dependency_values = _decode_cost_parameters(
        dependency.lineage.parameters_json
    )["calculation_values"]
    if (
        dependency_values["underlying_price_exact"]
        != record.base_underlying_price
        or dependency_values["total_entry_cost_exact"]
        != record.total_entry_cost
    ):
        raise ValueError(
            "public exact values differ from StructureCosts dependency"
        )
    if lineage.inputs != dependency.lineage.inputs:
        raise ValueError("lineage inputs must exactly reuse dependency inputs")
    if lineage.calculation_id == dependency.lineage.calculation_id:
        raise ValueError("calculation ID must differ from dependency")
    if lineage.calculated_at < dependency.lineage.calculated_at:
        raise ValueError("calculation precedes StructureCosts dependency")
    expected_flags = {
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    expected_flags.update(
        set(dependency.lineage.quality_flags)
        & _EXPIRATION_THRESHOLD_PROPAGATED_FLAGS
    )
    canonical_flags = tuple(
        flag for flag in CalculationQualityFlag if flag in expected_flags
    )
    if (
        lineage.quality_flags != canonical_flags
        or set(lineage.quality_flags) & _EXPIRATION_THRESHOLD_PROHIBITED_FLAGS
    ):
        raise ValueError("expiration threshold quality flags are invalid")
    expected_parameters = _expiration_threshold_parameters(
        record, dependency.lineage
    )
    _validate_exact_expiration_parameter_tree(
        decoded, expected_parameters
    )
    expected_parameters_json = canonicalize_lineage_parameters(
        expected_parameters
    )
    if lineage.parameters_json != expected_parameters_json:
        raise ValueError(
            "expiration threshold parameters are not the independently "
            "reconstructed canonical serialization"
        )


@dataclass(frozen=True)
class ExpirationPayoffThresholdTransformationResult:
    record: ExpirationPayoffThresholdEvidence
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.record) is not ExpirationPayoffThresholdEvidence:
            raise TypeError(
                "record must have exact type ExpirationPayoffThresholdEvidence"
            )
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")
        with decimal.localcontext():
            verified_lineage = CalculationLineage(
                calculation_id=self.lineage.calculation_id,
                calculation_type=self.lineage.calculation_type,
                methodology_id=self.lineage.methodology_id,
                methodology_version=self.lineage.methodology_version,
                calculated_at=self.lineage.calculated_at,
                inputs=self.lineage.inputs,
                parameters_json=self.lineage.parameters_json,
                quality_flags=self.lineage.quality_flags,
            )
            verified_record = ExpirationPayoffThresholdEvidence(
                structure=self.record.structure,
                as_of_date=self.record.as_of_date,
                base_underlying_price=self.record.base_underlying_price,
                total_entry_cost=self.record.total_entry_cost,
                thresholds=self.record.thresholds,
            )
            _validate_expiration_threshold_result(
                verified_record, verified_lineage
            )


def _construct_expiration_threshold_lineage(
    calculation_id: str,
    calculated_at: datetime.datetime,
    inputs: tuple,
    parameters_json: str,
    quality_flags: tuple,
) -> CalculationLineage:
    return CalculationLineage(
        calculation_id=calculation_id,
        calculation_type="expiration_payoff_thresholds",
        methodology_id=(
            "closed-form-terminal-intrinsic-position-value-multiples"
        ),
        methodology_version="v0.1",
        calculated_at=calculated_at,
        inputs=inputs,
        parameters_json=parameters_json,
        quality_flags=quality_flags,
    )


def transform_expiration_payoff_thresholds(
    calculation_id,
    structure_costs_result,
    calculated_at,
):
    """Build exact expiration payoff-threshold evidence from reviewed costs."""

    if type(calculation_id) is not str:
        raise TypeError("calculation_id must have exact type str")
    if type(structure_costs_result) is not StructureCostsTransformationResult:
        raise TypeError(
            "structure_costs_result must have exact type "
            "StructureCostsTransformationResult"
        )
    if type(calculated_at) is not datetime.datetime:
        raise TypeError("calculated_at must have exact type datetime")
    normalized_id = _validate_calculation_id(calculation_id)
    normalized_at = _normalize_calculated_at(calculated_at)

    with decimal.localcontext():
        dependency = StructureCostsTransformationResult(
            structure_costs_result.record,
            structure_costs_result.lineage,
        )
        dependency_decoded = _decode_cost_parameters(
            dependency.lineage.parameters_json
        )
        if (
            CalculationQualityFlag.INCOMPLETE_INPUT_USED
            in dependency.lineage.quality_flags
        ):
            raise ValueError("StructureCosts dependency must be complete")
        if normalized_id == dependency.lineage.calculation_id:
            raise ValueError("calculation ID must differ from dependency")
        if normalized_id in {
            item.record_id for item in dependency.lineage.inputs
        }:
            raise ValueError("calculation ID must differ from every input ID")
        if normalized_at < dependency.lineage.calculated_at:
            raise ValueError("calculation precedes StructureCosts dependency")
        if any(
            normalized_at < item.normalized_at
            for item in dependency.lineage.inputs
        ):
            raise ValueError("calculation precedes a normalized input")
        prohibited_dependency_flags = {
            CalculationQualityFlag.ANNUALIZED,
            CalculationQualityFlag.ADJUSTED_INPUT_USED,
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
        }
        if (
            set(dependency.lineage.quality_flags)
            & prohibited_dependency_flags
        ):
            raise ValueError("StructureCosts dependency flags are prohibited")
        values = dependency_decoded["calculation_values"]
        structure = _validate_expiration_threshold_structure(
            dependency.record.structure
        )
        base = values["underlying_price_exact"]
        cost = values["total_entry_cost_exact"]
        thresholds = _expected_expiration_thresholds(structure, base, cost)
        record = ExpirationPayoffThresholdEvidence(
            structure=structure,
            as_of_date=dependency.record.as_of_date,
            base_underlying_price=base,
            total_entry_cost=cost,
            thresholds=thresholds,
        )
        parameters_json = canonicalize_lineage_parameters(
            _expiration_threshold_parameters(record, dependency.lineage)
        )
        selected_flags = {
            CalculationQualityFlag.ASSUMPTION_APPLIED,
        }
        selected_flags.update(
            set(dependency.lineage.quality_flags)
            & _EXPIRATION_THRESHOLD_PROPAGATED_FLAGS
        )
        quality_flags = tuple(
            flag for flag in CalculationQualityFlag
            if flag in selected_flags
        )
        lineage = _construct_expiration_threshold_lineage(
            normalized_id,
            normalized_at,
            dependency.lineage.inputs,
            parameters_json,
            quality_flags,
        )
        return ExpirationPayoffThresholdTransformationResult(record, lineage)


_TREASURY_SOURCE_TENORS = (30, 45, 60, 90, 120, 180)
_TREASURY_CURVE_ID = "USD-US-TREASURY-DAILY-PAR-YIELD"
_TREASURY_CURRENCY = "USD"
_TREASURY_COMPOUNDING_CONVENTION = (
    "Bond-equivalent yield; simple annualized with semiannual interest convention"
)
_TREASURY_DAY_COUNT_CONVENTION = "Actual days; 365- or 366-day year"
_TREASURY_NORMALIZATION_VERSION = "us-treasury-daily-par-yield-v0.1"
_TREASURY_EXACT_TENOR_METHOD = "exact_tenor_match"
_TREASURY_INTERPOLATION_METHOD = (
    "linear_in_calendar_days_on_provider_native_annualized_par_yields"
)
_TREASURY_INTERPOLATION_FORMULA = (
    "y = y_lower + (y_upper - y_lower) * "
    "(target_days - lower_days) / (upper_days - lower_days)"
)
_TREASURY_COMPOUNDING_FORMULA = "r_continuous = 2 * ln(1 + y / 2)"
_TREASURY_COMPOUNDING_METHODOLOGY = (
    "precision-34 round-half-even Decimal arithmetic applied to the "
    "nominal semiannual-interest convention"
)
_TREASURY_ECONOMIC_SEMANTICS = (
    "continuous-compounding calculation proxy derived from a nominal Treasury "
    "par yield; not a bootstrapped risk-free zero curve and not a zero/OIS curve"
)
_TREASURY_DECIMAL_ERROR = "treasury pricing-rate Decimal calculation failed"
_TREASURY_RECORD_ERROR = "treasury curve point is not canonical"
_TREASURY_METADATA_ERROR = "treasury curve point metadata is not canonical"
_TREASURY_LINEAGE_ERROR = "treasury pricing-rate lineage is not canonical"


def _treasury_rebuild_dataclass(value: object, cls: object, label: str) -> object:
    """Rebuild one immutable input dataclass and reject forged state."""

    if type(value) is not cls:
        cls_name = getattr(cls, "__name__", "dataclass")
        raise TypeError(f"{label} must have exact type {cls_name}")
    try:
        values = {
            field.name: getattr(value, field.name)
            for field in dataclasses.fields(cls)  # type: ignore[arg-type]
        }
    except Exception:
        raise ValueError(f"{label} is not canonical") from None
    try:
        rebuilt = cls(**values)  # type: ignore[operator]
    except TypeError:
        raise TypeError(f"{label} has invalid field types") from None
    except Exception:
        raise ValueError(f"{label} is not canonical") from None
    try:
        equal = rebuilt == value
    except Exception:
        equal = False
    if not equal:
        raise ValueError(f"{label} is not canonical")
    return rebuilt


def _treasury_canonical_source_reference(value: object) -> SourceReference:
    """Return one canonical source reference without exposing raw failures."""

    return _treasury_rebuild_dataclass(
        value, SourceReference, "source reference"
    )  # type: ignore[return-value]


def _treasury_canonical_metadata(value: object) -> NormalizationMetadata:
    """Return canonical metadata, including canonical nested sources."""

    if type(value) is not NormalizationMetadata:
        raise TypeError(
            "metadata must have exact type NormalizationMetadata"
        )
    try:
        source_values = value.source_references
    except Exception:
        raise ValueError(_TREASURY_METADATA_ERROR) from None
    if type(source_values) is not tuple:
        raise ValueError(_TREASURY_METADATA_ERROR)
    sources = tuple(
        _treasury_canonical_source_reference(source)
        for source in source_values
    )
    try:
        values = {
            field.name: getattr(value, field.name)
            for field in dataclasses.fields(NormalizationMetadata)
        }
        values["source_references"] = sources
        rebuilt = NormalizationMetadata(**values)
    except TypeError:
        raise TypeError("metadata has invalid field types") from None
    except Exception:
        raise ValueError(_TREASURY_METADATA_ERROR) from None
    try:
        equal = rebuilt == value
    except Exception:
        equal = False
    if not equal:
        raise ValueError(_TREASURY_METADATA_ERROR)
    return rebuilt


def _treasury_canonical_curve_point(
    value: object,
) -> RateCurvePointObservation:
    """Rebuild a curve point after rebuilding all nested provenance."""

    if type(value) is not RateCurvePointObservation:
        raise TypeError(
            "curve point must have exact type RateCurvePointObservation"
        )
    try:
        values = {
            field.name: getattr(value, field.name)
            for field in dataclasses.fields(RateCurvePointObservation)
        }
        values["metadata"] = _treasury_canonical_metadata(values["metadata"])
    except (TypeError, ValueError):
        raise
    except Exception:
        raise ValueError(_TREASURY_RECORD_ERROR) from None
    try:
        rebuilt = RateCurvePointObservation(**values)
    except TypeError:
        raise TypeError("curve point has invalid field types") from None
    except Exception:
        raise ValueError(_TREASURY_RECORD_ERROR) from None
    try:
        equal = rebuilt == value
    except Exception:
        equal = False
    if not equal:
        raise ValueError(_TREASURY_RECORD_ERROR)
    return rebuilt


def _treasury_validate_curve_points(value: object) -> Tuple[RateCurvePointObservation, ...]:
    """Validate the exact six-point Treasury input curve."""

    if type(value) is not tuple:
        raise TypeError("curve_points must have exact type tuple")
    if any(type(point) is not RateCurvePointObservation for point in value):
        raise TypeError(
            "every curve point must have exact type RateCurvePointObservation"
        )
    if len(value) != len(_TREASURY_SOURCE_TENORS):
        raise ValueError("curve_points must contain exactly six points")
    points = tuple(_treasury_canonical_curve_point(point) for point in value)
    tenors = tuple(point.tenor_days for point in points)
    if tenors != _TREASURY_SOURCE_TENORS:
        raise ValueError("curve_points must use the exact Treasury tenor order")

    effective_dates = tuple(point.effective_date for point in points)
    if any(type(effective_date) is not datetime.date for effective_date in effective_dates):
        raise TypeError("every curve point effective_date must have exact type date")
    if len(set(effective_dates)) != 1:
        raise ValueError("curve points must share one effective date")
    for point in points:
        if (
            point.curve_id != _TREASURY_CURVE_ID
            or point.currency != _TREASURY_CURRENCY
            or point.compounding_convention != _TREASURY_COMPOUNDING_CONVENTION
            or point.day_count_convention != _TREASURY_DAY_COUNT_CONVENTION
        ):
            raise ValueError("curve points must share the Treasury declarations")
        if point.metadata.record_origin is not DataOrigin.PROVIDER_CALCULATED:
            raise ValueError("curve points must be provider_calculated")
        if point.metadata.normalization_version != _TREASURY_NORMALIZATION_VERSION:
            raise ValueError("curve points must use the Treasury normalization version")
        if NormalizationQualityFlag.INCOMPLETE in point.metadata.quality_flags:
            raise ValueError("incomplete Treasury curve points are prohibited")
        if any(
            SourceQualityFlag.PARTIAL in source.quality_flags
            for source in point.metadata.source_references
        ):
            raise ValueError("partial Treasury curve sources are prohibited")
        if type(point.metadata.record_id) is not str or not point.metadata.record_id:
            raise ValueError("curve point record IDs must be nonempty")
        source_ids = tuple(
            source.source_id for source in point.metadata.source_references
        )
        if type(source_ids) is not tuple or not source_ids:
            raise ValueError("curve point source IDs must be nonempty")
        if any(type(source_id) is not str or not source_id for source_id in source_ids):
            raise ValueError("curve point source IDs must be nonempty strings")
    record_ids = tuple(point.metadata.record_id for point in points)
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("curve point record IDs must be unique")
    return points


def _treasury_normalize_calculated_at(value: object) -> datetime.datetime:
    """Normalize one exact aware calculation time to UTC."""

    if type(value) is not datetime.datetime:
        raise TypeError("calculated_at must have exact type datetime")
    try:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("calculated_at must be timezone-aware")
        return value.astimezone(datetime.timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        raise ValueError("calculated_at must be representable in UTC") from None
    except Exception:
        raise ValueError("calculated_at must be representable in UTC") from None


def _treasury_validate_target_type(value: object) -> int:
    """Validate target-tenor type before later range and bracket checks."""

    if type(value) is not int:
        raise TypeError("target_tenor_days must have exact type int")
    return value


def _treasury_validate_decimal(value: object, label: str) -> decimal.Decimal:
    """Require one finite, non-negative-zero exact Decimal value."""

    if type(value) is not decimal.Decimal:
        raise TypeError(f"{label} must have exact type Decimal")
    if not value.is_finite():
        raise ValueError(f"{label} must be finite")
    if value.is_zero() and value.is_signed():
        raise ValueError(f"{label} must not be negative zero")
    return value


def _treasury_decimal_context() -> decimal.Context:
    """Return the fixed context used by every Treasury Decimal operation."""

    context = decimal.Context(
        prec=34,
        rounding=decimal.ROUND_HALF_EVEN,
        Emin=decimal.MIN_EMIN,
        Emax=decimal.MAX_EMAX,
        capitals=1,
        clamp=0,
    )
    for signal in context.traps:
        context.traps[signal] = False
    context.clear_flags()
    return context


def _treasury_decimal_operation(
    context: decimal.Context,
    operation: object,
) -> decimal.Decimal:
    """Run one context-bound operation and hide all arithmetic failures."""

    context.clear_flags()
    try:
        value = operation()  # type: ignore[operator]
    except Exception:
        raise ValueError(_TREASURY_DECIMAL_ERROR) from None
    fatal_signals = (
        decimal.InvalidOperation,
        decimal.DivisionByZero,
        decimal.Overflow,
        decimal.Underflow,
        decimal.Subnormal,
        decimal.Clamped,
    )
    if any(context.flags[signal] for signal in fatal_signals):
        raise ValueError(_TREASURY_DECIMAL_ERROR)
    if type(value) is not decimal.Decimal or not value.is_finite():
        raise ValueError(_TREASURY_DECIMAL_ERROR)
    return value


def _treasury_same_decimal(
    left: decimal.Decimal,
    right: decimal.Decimal,
) -> bool:
    """Compare Decimal coefficient and exponent, not only numeric equality."""

    return left.as_tuple() == right.as_tuple()


def _treasury_select_yield(
    source_tenors: Tuple[int, ...],
    source_rates: Tuple[decimal.Decimal, ...],
    target_tenor_days: int,
) -> Tuple[
    decimal.Decimal,
    str,
    int,
    int,
    decimal.Decimal,
    decimal.Decimal,
]:
    """Select an exact tenor or interpolate adjacent source points."""

    try:
        exact_index = source_tenors.index(target_tenor_days)
    except ValueError:
        exact_index = -1
    if exact_index >= 0:
        selected = source_rates[exact_index]
        return (
            selected,
            _TREASURY_EXACT_TENOR_METHOD,
            target_tenor_days,
            target_tenor_days,
            selected,
            selected,
        )

    lower_index = -1
    for index, (lower, upper) in enumerate(
        zip(source_tenors, source_tenors[1:])
    ):
        if lower < target_tenor_days < upper:
            lower_index = index
            break
    if lower_index < 0:
        raise ValueError("target tenor is not bracketed by Treasury points")
    lower_days = source_tenors[lower_index]
    upper_days = source_tenors[lower_index + 1]
    lower_rate = source_rates[lower_index]
    upper_rate = source_rates[lower_index + 1]
    context = _treasury_decimal_context()
    lower_delta = _treasury_decimal_operation(
        context,
        lambda: context.subtract(upper_rate, lower_rate),
    )
    tenor_delta = decimal.Decimal(target_tenor_days - lower_days)
    span = decimal.Decimal(upper_days - lower_days)
    weighted_delta = _treasury_decimal_operation(
        context,
        lambda: context.multiply(lower_delta, tenor_delta),
    )
    fraction = _treasury_decimal_operation(
        context,
        lambda: context.divide(weighted_delta, span),
    )
    selected = _treasury_decimal_operation(
        context,
        lambda: context.add(lower_rate, fraction),
    )
    if selected.is_zero():
        selected = decimal.Decimal("0")
    return (
        selected,
        _TREASURY_INTERPOLATION_METHOD,
        lower_days,
        upper_days,
        lower_rate,
        upper_rate,
    )


def _treasury_continuous_rate(value: decimal.Decimal) -> decimal.Decimal:
    """Convert a nominal semiannual yield using the fixed Decimal context."""

    context = _treasury_decimal_context()
    half_yield = _treasury_decimal_operation(
        context,
        lambda: context.divide(value, decimal.Decimal("2")),
    )
    logarithm_argument = _treasury_decimal_operation(
        context,
        lambda: context.add(decimal.Decimal("1"), half_yield),
    )
    if not logarithm_argument.is_finite() or logarithm_argument <= 0:
        raise ValueError("Treasury logarithm argument must be finite and positive")
    logarithm = _treasury_decimal_operation(
        context,
        lambda: context.ln(logarithm_argument),
    )
    result = _treasury_decimal_operation(
        context,
        lambda: context.multiply(decimal.Decimal("2"), logarithm),
    )
    return decimal.Decimal("0") if result.is_zero() else result


def _treasury_expected_quality_flags(
    interpolation_methodology: str,
) -> Tuple[CalculationQualityFlag, ...]:
    """Return the exact declared quality flags in enum declaration order."""

    selected = {
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    if interpolation_methodology != _TREASURY_EXACT_TENOR_METHOD:
        selected.add(CalculationQualityFlag.INTERPOLATED)
    return tuple(flag for flag in CalculationQualityFlag if flag in selected)


def _treasury_canonical_input_reference(
    value: object,
) -> CalculationInputReference:
    """Independently rebuild one retained normalized-input reference."""

    if type(value) is not CalculationInputReference:
        raise TypeError(
            "source input reference must have exact type "
            "CalculationInputReference"
        )
    try:
        rebuilt = CalculationInputReference(
            record_id=value.record_id,
            normalized_at=value.normalized_at,
            source_ids=value.source_ids,
        )
    except TypeError:
        raise TypeError("source input reference has invalid field types") from None
    except Exception:
        raise ValueError("source input reference is not canonical") from None
    if rebuilt != value:
        raise ValueError("source input reference is not canonical")
    return rebuilt


@dataclass(frozen=True)
class TreasuryPricingRateInput:
    """One deterministic Treasury par-yield pricing-rate proxy input."""

    effective_date: datetime.date
    target_tenor_days: int
    source_curve_id: str
    currency: str
    source_tenors_days: Tuple[int, ...]
    source_annualized_par_yields: Tuple[decimal.Decimal, ...]
    source_input_references: Tuple[CalculationInputReference, ...]
    interpolated_annualized_par_yield: decimal.Decimal
    continuously_compounded_rate_proxy: decimal.Decimal
    interpolation_methodology: str
    compounding_conversion_methodology: str
    economic_semantics: str

    def __post_init__(self) -> None:
        if type(self.effective_date) is not datetime.date:
            raise TypeError("effective_date must have exact type date")
        if type(self.target_tenor_days) is not int:
            raise TypeError("target_tenor_days must have exact type int")
        if not 30 <= self.target_tenor_days <= 180:
            raise ValueError("target_tenor_days must be between 30 and 180")
        if type(self.source_curve_id) is not str:
            raise TypeError("source_curve_id must have exact type str")
        if self.source_curve_id != _TREASURY_CURVE_ID:
            raise ValueError("source_curve_id is not the Treasury curve")
        if type(self.currency) is not str:
            raise TypeError("currency must have exact type str")
        if self.currency != _TREASURY_CURRENCY:
            raise ValueError("currency must be USD")
        if type(self.source_tenors_days) is not tuple:
            raise TypeError("source_tenors_days must have exact type tuple")
        if any(type(tenor) is not int for tenor in self.source_tenors_days):
            raise TypeError("every source tenor must have exact type int")
        if self.source_tenors_days != _TREASURY_SOURCE_TENORS:
            raise ValueError("source_tenors_days are not the exact Treasury tenors")
        if type(self.source_annualized_par_yields) is not tuple:
            raise TypeError(
                "source_annualized_par_yields must have exact type tuple"
            )
        if len(self.source_annualized_par_yields) != len(_TREASURY_SOURCE_TENORS):
            raise ValueError("source_annualized_par_yields must contain six values")
        for rate in self.source_annualized_par_yields:
            _treasury_validate_decimal(rate, "source annualized par yield")
        if type(self.source_input_references) is not tuple:
            raise TypeError("source_input_references must have exact type tuple")
        if len(self.source_input_references) != len(_TREASURY_SOURCE_TENORS):
            raise ValueError("source_input_references must contain six values")
        references = tuple(
            _treasury_canonical_input_reference(reference)
            for reference in self.source_input_references
        )
        if len({reference.record_id for reference in references}) != len(
            references
        ):
            raise ValueError("source input reference record IDs must be unique")
        _treasury_validate_decimal(
            self.interpolated_annualized_par_yield,
            "interpolated annualized par yield",
        )
        _treasury_validate_decimal(
            self.continuously_compounded_rate_proxy,
            "continuously compounded rate proxy",
        )
        if type(self.interpolation_methodology) is not str:
            raise TypeError("interpolation_methodology must have exact type str")
        if type(self.compounding_conversion_methodology) is not str:
            raise TypeError(
                "compounding_conversion_methodology must have exact type str"
            )
        if type(self.economic_semantics) is not str:
            raise TypeError("economic_semantics must have exact type str")
        expected_yield, expected_method, _, _, _, _ = _treasury_select_yield(
            self.source_tenors_days,
            self.source_annualized_par_yields,
            self.target_tenor_days,
        )
        if self.interpolation_methodology != expected_method:
            raise ValueError("interpolation_methodology is inconsistent")
        if self.compounding_conversion_methodology != _TREASURY_COMPOUNDING_METHODOLOGY:
            raise ValueError("compounding_conversion_methodology is inconsistent")
        if self.economic_semantics != _TREASURY_ECONOMIC_SEMANTICS:
            raise ValueError("economic_semantics is inconsistent")
        if not _treasury_same_decimal(
            self.interpolated_annualized_par_yield, expected_yield
        ):
            raise ValueError("interpolated annualized par yield is inconsistent")
        expected_proxy = _treasury_continuous_rate(expected_yield)
        if not _treasury_same_decimal(
            self.continuously_compounded_rate_proxy, expected_proxy
        ):
            raise ValueError("continuously compounded rate proxy is inconsistent")


def _treasury_lineage_parameters(
    record: TreasuryPricingRateInput,
    calculation_id: str,
    calculated_at: datetime.datetime,
    inputs: Tuple[CalculationInputReference, ...],
) -> str:
    """Build the complete canonical parameter sidecar for the calculation."""

    (
        selected_yield,
        method,
        lower_days,
        upper_days,
        lower_rate,
        upper_rate,
    ) = _treasury_select_yield(
        record.source_tenors_days,
        record.source_annualized_par_yields,
        record.target_tenor_days,
    )
    if (
        method != record.interpolation_methodology
        or not _treasury_same_decimal(
            selected_yield, record.interpolated_annualized_par_yield
        )
    ):
        raise ValueError(_TREASURY_LINEAGE_ERROR)
    evidence = tuple(
        {
            "role": "rate_curve_point",
            "tenor_days": tenor,
            "annualized_par_yield": rate,
            "record_id": item.record_id,
            "normalized_at": item.normalized_at,
            "source_ids": item.source_ids,
        }
        for tenor, rate, item in zip(
            record.source_tenors_days,
            record.source_annualized_par_yields,
            inputs,
        )
    )
    return canonicalize_lineage_parameters({
        "calculation_identity": {
            "calculation_id": calculation_id,
            "calculation_type": "treasury_pricing_rate_proxy",
            "methodology_id": (
                "linear-par-yield-tenor-and-continuous-compounding-proxy"
            ),
            "methodology_version": "v0.1",
            "calculated_at": calculated_at,
        },
        "curve_identity": {
            "curve_id": record.source_curve_id,
            "currency": record.currency,
            "effective_date": record.effective_date,
            "compounding_convention": _TREASURY_COMPOUNDING_CONVENTION,
            "day_count_convention": _TREASURY_DAY_COUNT_CONVENTION,
            "normalization_version": _TREASURY_NORMALIZATION_VERSION,
        },
        "source_curve": {
            "source_tenors_days": record.source_tenors_days,
            "source_annualized_par_yields": record.source_annualized_par_yields,
        },
        "target_tenor_days": record.target_tenor_days,
        "tenor_selection": {
            "interpolation_methodology": record.interpolation_methodology,
            "interpolation_formula": _TREASURY_INTERPOLATION_FORMULA,
            "lower_tenor_days": lower_days,
            "upper_tenor_days": upper_days,
            "lower_annualized_par_yield": lower_rate,
            "upper_annualized_par_yield": upper_rate,
        },
        "compounding_conversion": {
            "formula": _TREASURY_COMPOUNDING_FORMULA,
            "methodology": record.compounding_conversion_methodology,
            "precision": 34,
            "rounding": "ROUND_HALF_EVEN",
        },
        "calculated_values": {
            "interpolated_annualized_par_yield": (
                record.interpolated_annualized_par_yield
            ),
            "continuously_compounded_rate_proxy": (
                record.continuously_compounded_rate_proxy
            ),
        },
        "output_semantics": record.economic_semantics,
        "quality_flags": tuple(
            flag.value
            for flag in _treasury_expected_quality_flags(
                record.interpolation_methodology
            )
        ),
        "normalized_evidence": evidence,
    })


def _treasury_canonical_lineage(
    value: object,
) -> CalculationLineage:
    """Rebuild a lineage sidecar to reject constructor-bypassed state."""

    if type(value) is not CalculationLineage:
        raise TypeError("lineage must have exact type CalculationLineage")
    try:
        values = {
            field.name: getattr(value, field.name)
            for field in dataclasses.fields(CalculationLineage)
        }
        if type(values["inputs"]) is not tuple:
            raise TypeError
        values["inputs"] = tuple(
            _treasury_canonical_input_reference(reference)
            for reference in values["inputs"]
        )
        rebuilt = CalculationLineage(**values)
    except TypeError:
        raise TypeError(_TREASURY_LINEAGE_ERROR) from None
    except Exception:
        raise ValueError(_TREASURY_LINEAGE_ERROR) from None
    try:
        equal = rebuilt == value
    except Exception:
        equal = False
    if not equal:
        raise ValueError(_TREASURY_LINEAGE_ERROR)
    return rebuilt


@dataclass(frozen=True)
class TreasuryPricingRateTransformationResult:
    """Immutable Treasury pricing-rate input and its auditable lineage."""

    record: TreasuryPricingRateInput
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.record) is not TreasuryPricingRateInput:
            raise TypeError(
                "record must have exact type TreasuryPricingRateInput"
            )
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")
        _treasury_rebuild_dataclass(
            self.record,
            TreasuryPricingRateInput,
            "TreasuryPricingRateInput",
        )
        _treasury_canonical_lineage(self.lineage)
        if len(self.lineage.inputs) != len(_TREASURY_SOURCE_TENORS):
            raise ValueError("Treasury lineage must contain exactly six inputs")
        expected_inputs = tuple(sorted(
            self.record.source_input_references,
            key=lambda item: item.record_id,
        ))
        if self.lineage.inputs != expected_inputs:
            raise ValueError("Treasury lineage inputs do not match the record")
        if self.lineage.calculation_type != "treasury_pricing_rate_proxy":
            raise ValueError("Treasury lineage calculation_type is inconsistent")
        if self.lineage.methodology_id != (
            "linear-par-yield-tenor-and-continuous-compounding-proxy"
        ):
            raise ValueError("Treasury lineage methodology_id is inconsistent")
        if self.lineage.methodology_version != "v0.1":
            raise ValueError("Treasury lineage methodology_version is inconsistent")
        expected_flags = _treasury_expected_quality_flags(
            self.record.interpolation_methodology
        )
        if self.lineage.quality_flags != expected_flags:
            raise ValueError("Treasury lineage quality_flags are inconsistent")
        expected_parameters = _treasury_lineage_parameters(
            self.record,
            self.lineage.calculation_id,
            self.lineage.calculated_at,
            self.record.source_input_references,
        )
        if self.lineage.parameters_json != expected_parameters:
            raise ValueError("Treasury lineage parameters are inconsistent")


def transform_treasury_pricing_rate(
    calculation_id: object,
    curve_points: object,
    target_tenor_days: object,
    calculated_at: object,
) -> TreasuryPricingRateTransformationResult:
    """Transform six normalized Treasury points into one rate proxy."""

    if type(calculation_id) is not str:
        raise TypeError("calculation_id must have exact type str")
    normalized_id = calculation_id.strip()
    if not normalized_id:
        raise ValueError("calculation_id must not be empty")
    target = _treasury_validate_target_type(target_tenor_days)
    normalized_at = _treasury_normalize_calculated_at(calculated_at)
    points = _treasury_validate_curve_points(curve_points)

    record_ids = tuple(point.metadata.record_id for point in points)
    if normalized_id in record_ids:
        raise ValueError("calculation_id must differ from every input ID")
    if any(normalized_at < point.metadata.normalized_at for point in points):
        raise ValueError("calculation precedes a normalized input")
    if target < 30 or target > 180:
        raise ValueError("target_tenor_days must be between 30 and 180")

    source_tenors = tuple(point.tenor_days for point in points)
    source_rates = tuple(point.annualized_rate for point in points)
    selected_yield, method, _, _, _, _ = _treasury_select_yield(
        source_tenors, source_rates, target
    )
    continuous_rate = _treasury_continuous_rate(selected_yield)
    input_references = tuple(
        CalculationInputReference(
            record_id=point.metadata.record_id,
            normalized_at=point.metadata.normalized_at,
            source_ids=tuple(
                source.source_id
                for source in point.metadata.source_references
            ),
        )
        for point in points
    )
    record = TreasuryPricingRateInput(
        effective_date=points[0].effective_date,
        target_tenor_days=target,
        source_curve_id=points[0].curve_id,
        currency=points[0].currency,
        source_tenors_days=source_tenors,
        source_annualized_par_yields=source_rates,
        source_input_references=input_references,
        interpolated_annualized_par_yield=selected_yield,
        continuously_compounded_rate_proxy=continuous_rate,
        interpolation_methodology=method,
        compounding_conversion_methodology=_TREASURY_COMPOUNDING_METHODOLOGY,
        economic_semantics=_TREASURY_ECONOMIC_SEMANTICS,
    )
    parameters_json = _treasury_lineage_parameters(
        record, normalized_id, normalized_at, input_references
    )
    lineage = CalculationLineage(
        calculation_id=normalized_id,
        calculation_type="treasury_pricing_rate_proxy",
        methodology_id=(
            "linear-par-yield-tenor-and-continuous-compounding-proxy"
        ),
        methodology_version="v0.1",
        calculated_at=normalized_at,
        inputs=input_references,
        parameters_json=parameters_json,
        quality_flags=_treasury_expected_quality_flags(method),
    )
    return TreasuryPricingRateTransformationResult(record, lineage)
