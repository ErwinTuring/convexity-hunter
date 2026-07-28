"""Deterministic transformations from reviewed market data to research records."""

import datetime
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
    SelectedFreshMarketDataBinding,
    SourceReference,
    SourceQualityFlag,
    UnderlyingDailyBarObservation,
    UnderlyingKey,
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


@dataclass(frozen=True)
class StructureLiquidityTransformationResult:
    record: StructureLiquidity
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.record) is not StructureLiquidity:
            raise TypeError("record must have exact type StructureLiquidity")
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")


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


def _construct_parameters(canonical_matched: tuple) -> str:
    leg_correspondence = []
    for contract_key, leg, _bindings, records in canonical_matched:
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
    return canonicalize_lineage_parameters({
        "activity_count_unit": "contracts",
        "leg_correspondence": leg_correspondence,
        "minimum_leg_rule": "minimum_unscaled_contract_count_across_legs",
        "position_value_rule": (
            "sum(premium_per_underlying_unit*quantity*contract_multiplier)"
        ),
        "position_value_unit": "usd",
        "premium_input_unit": "usd_per_underlying_unit",
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
        methodology_version="v0.1",
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
    canonical_matched, records, consumed_bindings = _canonical_consumed(matched)
    inputs = _construct_input_references(records)
    parameters_json = _construct_parameters(canonical_matched)
    quality_flags = _derive_quality_flags(consumed_bindings, records)
    lineage = _construct_lineage(
        normalized_id,
        normalized_at,
        inputs,
        parameters_json,
        quality_flags,
    )
    return _construct_result(record, lineage)


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
        "input_record_ids": tuple(item.record_id for item in lineage.inputs),
        "underlying": {
            "symbol": record.underlying_key.symbol,
            "listing_mic": record.underlying_key.listing_mic,
            "security_type": record.underlying_key.security_type.value,
            "currency": record.underlying_key.currency,
        },
        "start_session_date": record.start_session_date,
        "end_session_date": record.end_session_date,
        "price_basis": record.price_basis.value,
        "adjustment_methodology": record.adjustment_methodology,
        "annualization_sessions_per_year": record.annualization_sessions_per_year,
        "return_formula": record.return_formula,
        "variance_estimator": record.variance_estimator,
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

    iv_records = current[6] + tuple(
        record for item in historical for record in item[6]
    )
    inputs = realized_lineage.inputs + _construct_input_references(iv_records)
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
    all_bindings = current[5] + tuple(
        binding for item in historical for binding in item[5]
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
        methodology_version="v0.1",
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
        raise ValueError("3C.7d parameters have the wrong exact 20-key schema")
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
    record = value.record
    lineage = value.lineage
    if type(record) is not VolatilityEnvironment:
        raise TypeError(
            "volatility dependency record must have exact type "
            "VolatilityEnvironment"
        )
    if type(lineage) is not CalculationLineage:
        raise TypeError(
            "volatility dependency lineage must have exact type "
            "CalculationLineage"
        )
    if any(type(item) is not TermVolatilityPoint for item in record.term_structure):
        raise TypeError("every dependency term point must have exact type TermVolatilityPoint")
    if any(
        type(item) is not CalculationInputReference for item in lineage.inputs
    ):
        raise TypeError(
            "every prior input must have exact type CalculationInputReference"
        )
    if (
        lineage.calculation_type != "volatility_environment"
        or lineage.methodology_id != "paired-atm-volatility-environment"
        or lineage.methodology_version != "v0.1"
    ):
        raise ValueError("volatility dependency lineage identity is invalid")
    required = {
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    if (
        not required.issubset(lineage.quality_flags)
        or CalculationQualityFlag.INCOMPLETE_INPUT_USED
        in lineage.quality_flags
    ):
        raise ValueError("volatility dependency quality flags are invalid")
    if calculation_id == lineage.calculation_id:
        raise ValueError("new and prior calculation IDs must differ")
    if calculated_at < lineage.calculated_at:
        raise ValueError("new calculation must not precede dependency")
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
    if (
        type(realized) is not dict
        or realized.get("end_session_date") != record.as_of_date
        or realized.get("annualized_realized_volatility_float_repr")
        != repr(record.matched_realized_volatility)
        or record.matched_realized_window_days
        != record.reference_tenor_days
    ):
        raise ValueError("dependency realized-volatility fields are inconsistent")
    input_ids = tuple(item.record_id for item in lineage.inputs)
    expected_input_ids = set(realized.get("input_record_ids", ()))
    for item in current + historical:
        expected_input_ids.add(item["underlying_quote_record_id"])
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
    if len(input_ids) != len(set(input_ids)) or set(input_ids) != expected_input_ids:
        raise ValueError("dependency lineage inputs are inconsistent with parameters")
    return record, lineage, decoded, by_tenor


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
        "input_record_ids": tuple(item.record_id for item in lineage.inputs),
        "underlying": record.underlying,
        "as_of_date": record.as_of_date,
        "reference_tenor_days": record.reference_tenor_days,
        "historical_observation_count": (
            record.iv_history_lookback_observations
        ),
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
    direct_records = current["records"] + tuple(
        record for item in historical for record in item["records"]
    )
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
    all_bindings = current["bindings"] + tuple(
        binding for item in historical for binding in item["bindings"]
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
        methodology_version="v0.1",
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
    "input_record_ids",
    "underlying",
    "as_of_date",
    "reference_tenor_days",
    "historical_observation_count",
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
        or atm_dependency["methodology_version"] != "v0.1"
        or type(atm_dependency["calculated_at"]) is not datetime.datetime
        or atm_dependency["calculated_at"].utcoffset()
        != datetime.timedelta(0)
        or type(atm_dependency["as_of_date"]) is not datetime.date
        or type(atm_dependency["reference_tenor_days"]) is not int
        or atm_dependency["reference_tenor_days"] <= 0
        or type(atm_dependency["historical_observation_count"]) is not int
        or atm_dependency["historical_observation_count"] <= 0
    ):
        raise ValueError("TailPricing atm_dependency fields are invalid")
    _validate_volatility_fixed_methodology(
        _decode_volatility_parameters(atm_dependency["parameters_json"])
    )
    input_ids = _tail_schema_tuple(
        atm_dependency["input_record_ids"],
        "TailPricing atm_dependency input_record_ids",
    )
    flags = _tail_schema_tuple(
        atm_dependency["quality_flags"],
        "TailPricing atm_dependency quality_flags",
    )
    if (
        not input_ids
        or any(type(item) is not str or not item for item in input_ids)
        or len(set(input_ids)) != len(input_ids)
        or any(type(item) is not str or not item for item in flags)
        or len(set(flags)) != len(flags)
    ):
        raise ValueError("TailPricing atm_dependency IDs or flags are invalid")
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
    verified = TailPricingTransformationResult(value.records, value.lineage)
    lineage = verified.lineage
    if (
        lineage.calculation_type != "tail_pricing"
        or lineage.methodology_id
        != "nearest-observed-delta-wing-tail-relative-pricing"
        or lineage.methodology_version != "v0.1"
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
    if len(observations) != len(verified.records):
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
    for record, observation in zip(verified.records, observations):
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
        underlying_id = observation.get("underlying_quote_record_id")
        if type(underlying_id) is not str:
            raise TypeError("tail underlying record ID must be a string")
        input_ids.add(underlying_id)
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
    atm_dependency = decoded["atm_dependency"]
    if type(atm_dependency) is not dict:
        raise TypeError("atm_dependency must have exact type dict")
    if (
        atm_dependency.get("underlying") != verified.records[0].underlying
        or atm_dependency.get("as_of_date") != verified.records[0].as_of_date
    ):
        raise ValueError(
            "tail records do not correspond to dependency underlying and date"
        )
    atm_ids = atm_dependency.get("input_record_ids")
    if type(atm_ids) is not tuple or any(type(item) is not str for item in atm_ids):
        raise TypeError("atm_dependency input IDs must be a tuple of strings")
    input_ids.update(atm_ids)
    if set(item.record_id for item in lineage.inputs) != input_ids:
        raise ValueError("tail parameter input IDs do not match lineage inputs")
    expected_flags = {
        CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
        CalculationQualityFlag.ANNUALIZED,
        CalculationQualityFlag.ASSUMPTION_APPLIED,
    }
    expected_flags.update(
        flag
        for flag in lineage.quality_flags
        if flag in _SCENARIO_VALUATION_PROPAGATED_FLAGS
    )
    if lineage.quality_flags != tuple(
        flag for flag in CalculationQualityFlag if flag in expected_flags
    ):
        raise ValueError("tail-pricing quality flags are invalid")
    return verified, decoded, observations


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
                "v0.1",
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
                "v0.1",
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
                    "v0.1",
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
