"""Deterministic transformations from reviewed market data to research records."""

import datetime
import decimal
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .evidence import OptionLeg, OptionStructure, StructureCosts
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
from .evidence import TermVolatilityPoint, VolatilityEnvironment
from .report import StructureLiquidity


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
    except (OverflowError, ValueError) as error:
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


def _canonical_cost_consumed(matched: tuple) -> Tuple[tuple, tuple, tuple]:
    canonical = tuple(
        sorted(matched, key=lambda item: _contract_order_key(item[0]))
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
    })


def _derive_cost_quality_flags(
    bindings: tuple,
    records: tuple,
) -> Tuple[CalculationQualityFlag, ...]:
    selected = set(_derive_quality_flags(bindings, records))
    selected.add(CalculationQualityFlag.ASSUMPTION_APPLIED)
    return tuple(flag for flag in CalculationQualityFlag if flag in selected)


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
        methodology_version="v0.1",
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
        matched
    )
    inputs = _construct_input_references(records)
    parameters_json = _construct_cost_parameters(
        canonical_matched,
        exact_fees,
        exact_repeated_bet_count,
        methodology,
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
