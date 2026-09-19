"""Pure, provider-neutral Core convexity research kernel.

The module deliberately owns only the frozen Core records and their exact
conditional-budget evaluation.  It does not import a provider, a legacy
screening record, or an execution/safety policy.
"""

import datetime
import decimal
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Iterable, Optional, Tuple, Union

from .market_data import (
    DataOrigin,
    SourceQualityFlag,
    SourceReference,
)
from .market_data_transformations import (
    TailPricingTransformationResult,
    VolatilityEnvironmentTransformationResult,
)


# Compatibility name for the earlier implementation record.  This is an
# alias, not a second 18/22-field source-reference dataclass.  CoreProvenance
# retains the existing market_data.SourceReference object in full.
CoreSourceReference = SourceReference
D_ZERO = decimal.Decimal("0")


class CoreOptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class CoreAskAuthority(str, Enum):
    INDICATIVE_ONLY = "INDICATIVE_ONLY"


class CorePayoffAuthority(str, Enum):
    CONDITIONAL_STANDARD_PAYOFF = "CONDITIONAL_STANDARD_PAYOFF"


class CoreCostComponentStatus(str, Enum):
    EXPLICIT_UPPER_BOUND = "EXPLICIT_UPPER_BOUND"
    UNKNOWN = "UNKNOWN"


class CoreDisposition(str, Enum):
    RESEARCHABLE_CONVEXITY = "RESEARCHABLE_CONVEXITY"
    REJECT = "REJECT"
    DATA_INSUFFICIENT_CORE = "DATA_INSUFFICIENT_CORE"


class CoreGeometryStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    DATA_INSUFFICIENT_CORE = "DATA_INSUFFICIENT_CORE"


class CoreHurdleSide(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


class CoreHurdleStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class CoreBudgetStatus(str, Enum):
    CONDITIONAL_PASS = "CONDITIONAL_PASS"
    CONDITIONAL_BREACH = "CONDITIONAL_BREACH"
    DATA_INSUFFICIENT_CORE = "DATA_INSUFFICIENT_CORE"


class CoreReasonCode(str, Enum):
    """Canonical classification-reason order for the Core service."""

    STRUCTURE_UNSUPPORTED = "structure_unsupported"
    PAYOFF_MODEL_MISSING = "payoff_model_missing"
    PAYOFF_AUTHORITY_UNSUPPORTED = "payoff_authority_unsupported"
    ASK_MISSING = "ask_missing"
    COST_LEDGER_MISSING = "cost_ledger_missing"
    MISSING_REQUIRED_COMPONENT = "missing_required_component"
    UNKNOWN_REQUIRED_COMPONENT = "unknown_required_component"
    UNKNOWN_COST_COMPONENT = "unknown_cost_component"
    PREMIUM_BOUND_BELOW_OBSERVED_ASK_COST = (
        "premium_bound_below_observed_ask_cost"
    )
    RISK_POLICY_MISSING = "risk_policy_missing"
    SENSITIVITY_MISSING = "sensitivity_missing"
    SINGLE_LOSS_BUDGET_EXCEEDED = "single_loss_budget_exceeded"
    REPEATED_LOSS_BUDGET_EXCEEDED = "repeated_loss_budget_exceeded"


@dataclass(frozen=True)
class CoreProvenance:
    """Full retained source reference plus a human-readable basis."""

    source_reference: Optional[SourceReference]
    description: str

    def __post_init__(self) -> None:
        _validate_provenance(self)


@dataclass(frozen=True)
class CoreLeg:
    leg_id: str
    underlying: str
    currency: str
    option_type: CoreOptionType
    strike: decimal.Decimal
    expiration: datetime.date
    quantity: int
    contract_multiplier: int
    ask_per_underlying_unit: Optional[decimal.Decimal]
    ask_authority: CoreAskAuthority
    description: str
    provenance: CoreProvenance

    def __post_init__(self) -> None:
        _validate_core_leg(self)


@dataclass(frozen=True)
class CoreStructure:
    legs: Tuple[CoreLeg, ...]
    description: str
    provenance: CoreProvenance

    def __post_init__(self) -> None:
        _validate_core_structure(self)


@dataclass(frozen=True)
class CorePayoffModel:
    authority: CorePayoffAuthority
    model_id: str
    model_version: str
    description: str
    provenance: CoreProvenance

    def __post_init__(self) -> None:
        _validate_core_payoff_model(self)


@dataclass(frozen=True)
class CoreCostComponent:
    component_id: str
    status: CoreCostComponentStatus
    upper_bound: Optional[decimal.Decimal]
    currency: str
    methodology: str
    description: str
    provenance: CoreProvenance

    def __post_init__(self) -> None:
        _validate_core_cost_component(self)


@dataclass(frozen=True)
class CoreCostLedger:
    premium_bound: decimal.Decimal
    impact_components: Tuple[CoreCostComponent, ...]
    required_component_ids: Tuple[str, ...]
    currency: str
    methodology: str
    description: str
    provenance: CoreProvenance

    def __post_init__(self) -> None:
        _validate_core_cost_ledger(self)

    @property
    def premium_upper_bound(self) -> decimal.Decimal:
        """Compatibility spelling for the explicit position-level bound."""

        return self.premium_bound


@dataclass(frozen=True)
class CoreRiskRepeatPolicy:
    portfolio_value: decimal.Decimal
    maximum_single_loss_fraction: decimal.Decimal
    maximum_repeated_loss_fraction: decimal.Decimal
    repeat_count: int
    methodology: str
    currency: str
    description: str
    provenance: CoreProvenance

    def __post_init__(self) -> None:
        _validate_core_risk_policy(self)


@dataclass(frozen=True)
class CoreSensitivityPoint:
    point_id: str
    terminal_underlying_price: decimal.Decimal
    ask_per_leg: Tuple[decimal.Decimal, ...]
    description: str
    provenance: CoreProvenance

    def __post_init__(self) -> None:
        _validate_core_sensitivity_point(self)


@dataclass(frozen=True)
class CoreSensitivity:
    points: Tuple[CoreSensitivityPoint, ...]
    description: str
    provenance: CoreProvenance

    def __post_init__(self) -> None:
        _validate_core_sensitivity(self)


@dataclass(frozen=True)
class CoreReviewedEnhancements:
    enhancement_id: str
    reviewed_artifact: Optional[
        Union[VolatilityEnvironmentTransformationResult, TailPricingTransformationResult]
    ]
    description: str
    provenance: CoreProvenance

    def __post_init__(self) -> None:
        _validate_core_reviewed_enhancement(self)


@dataclass(frozen=True)
class CoreResearchRequest:
    case_id: str
    structure: CoreStructure
    payoff_model: Optional[CorePayoffModel]
    cost_ledger: Optional[CoreCostLedger]
    risk_policy: Optional[CoreRiskRepeatPolicy]
    sensitivity: Optional[CoreSensitivity]
    reviewed_enhancements: Tuple[CoreReviewedEnhancements, ...]
    description: str
    provenance: CoreProvenance

    def __post_init__(self) -> None:
        _validate_core_request(self)


@dataclass(frozen=True)
class CoreHurdle:
    gross_value_multiple: int
    side: CoreHurdleSide
    status: CoreHurdleStatus
    terminal_underlying_price: Optional[decimal.Decimal]
    reason: Optional[str]


@dataclass(frozen=True)
class CoreGeometry:
    status: CoreGeometryStatus
    payoff_authority: Optional[CorePayoffAuthority]
    ask_basis_per_underlying_unit: Optional[decimal.Decimal]
    hurdles: Tuple[CoreHurdle, ...]


@dataclass(frozen=True)
class CoreCashLedgerView:
    observed_ask_cost: Optional[decimal.Decimal]
    known_components: Tuple[CoreCostComponent, ...]
    known_total: Optional[decimal.Decimal]
    conditional_total_upper_bound: Optional[decimal.Decimal]
    unknown_component_ids: Tuple[str, ...]
    missing_required_component_ids: Tuple[str, ...]


@dataclass(frozen=True)
class CoreBudgetStress:
    status: CoreBudgetStatus
    single_cost_upper_bound: Optional[decimal.Decimal]
    repeated_cost_upper_bound: Optional[decimal.Decimal]
    single_loss_fraction: Optional[decimal.Decimal]
    repeated_loss_fraction: Optional[decimal.Decimal]
    missing_assumptions: Tuple[CoreReasonCode, ...]


@dataclass(frozen=True)
class CoreSensitivityResultPoint:
    """One retained sensitivity point and its conditional gross outputs."""

    point: CoreSensitivityPoint
    conditional_gross_payoff_per_underlying_unit: Optional[decimal.Decimal]
    conditional_position_payoff: Optional[decimal.Decimal]
    declared_ask_basis_per_underlying_unit: Optional[decimal.Decimal]
    gross_response_multiple: Optional[decimal.Decimal]
    gross_hurdles: Tuple[CoreHurdle, ...]
    unavailable_reason: Optional[str]


@dataclass(frozen=True)
class CoreSensitivityResult:
    points: Tuple[CoreSensitivityResultPoint, ...]


@dataclass(frozen=True)
class CoreResearchResult:
    request: CoreResearchRequest
    disposition: CoreDisposition
    reasons: Tuple[CoreReasonCode, ...]
    geometry: CoreGeometry
    cash_ledger: CoreCashLedgerView
    budget_stress: CoreBudgetStress
    sensitivity_results: Optional[CoreSensitivityResult]
    reviewed_enhancements: Tuple[CoreReviewedEnhancements, ...]


def _field(value: object, name: str) -> object:
    try:
        return getattr(value, name)
    except AttributeError as error:
        raise TypeError(f"malformed {type(value).__name__}: missing {name}") from error


def _require_exact_type(name: str, value: object, expected: type) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must have exact type {expected.__name__}")


def _require_text(name: str, value: object) -> None:
    _require_exact_type(name, value, str)
    if not value.strip():  # type: ignore[union-attr]
        raise ValueError(f"{name} must not be empty")


def _require_enum(name: str, value: object, expected: type) -> None:
    if type(value) is not expected:
        raise TypeError(f"{name} must have exact type {expected.__name__}")


def _require_tuple(name: str, value: object) -> Tuple[object, ...]:
    _require_exact_type(name, value, tuple)
    return value  # type: ignore[return-value]


def _require_int(name: str, value: object, minimum: Optional[int] = None) -> None:
    _require_exact_type(name, value, int)
    if minimum is not None and value < minimum:  # type: ignore[operator]
        raise ValueError(f"{name} must be at least {minimum}")


def _require_date(name: str, value: object) -> None:
    _require_exact_type(name, value, datetime.date)


def _require_decimal(
    name: str,
    value: object,
    *,
    minimum: Optional[decimal.Decimal] = None,
    maximum: Optional[decimal.Decimal] = None,
) -> None:
    _require_exact_type(name, value, decimal.Decimal)
    decimal_value = value  # type: ignore[assignment]
    if not decimal_value.is_finite():
        raise ValueError(f"{name} must be finite")
    if minimum is not None and decimal_value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    if maximum is not None and decimal_value > maximum:
        raise ValueError(f"{name} must be at most {maximum}")


def _validate_source_reference(value: object) -> None:
    """Revalidate an existing SourceReference without trusting dataclass eq."""

    if type(value) is not SourceReference:
        raise TypeError("source_reference must have exact type SourceReference")
    names = (
        "source_id",
        "provider_name",
        "dataset_name",
        "provider_record_id",
        "provider_request_id",
        "source_symbol",
        "source_uri",
        "observed_at",
        "retrieved_at",
        "provider_timezone",
        "timestamp_methodology",
        "origin",
        "is_delayed",
        "declared_delay_seconds",
        "payload_sha256",
        "revision_number",
        "provider_correction_id",
        "quality_flags",
    )
    values = {name: _field(value, name) for name in names}
    try:
        rebuilt = SourceReference(**values)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise type(error)(f"invalid source_reference: {error}") from error
    for name in names:
        if _field(value, name) != _field(rebuilt, name):
            raise ValueError(f"source_reference.{name} is not canonical")


def _validate_provenance(value: object) -> None:
    if type(value) is not CoreProvenance:
        raise TypeError("provenance must have exact type CoreProvenance")
    source = _field(value, "source_reference")
    if source is not None:
        _validate_source_reference(source)
    _require_text("provenance.description", _field(value, "description"))


def _validate_core_leg(value: object) -> None:
    if type(value) is not CoreLeg:
        raise TypeError("leg must have exact type CoreLeg")
    _require_text("leg_id", _field(value, "leg_id"))
    _require_text("underlying", _field(value, "underlying"))
    _require_text("currency", _field(value, "currency"))
    _require_enum("option_type", _field(value, "option_type"), CoreOptionType)
    _require_decimal("strike", _field(value, "strike"), minimum=decimal.Decimal("0"))
    _require_date("expiration", _field(value, "expiration"))
    _require_int("quantity", _field(value, "quantity"), 1)
    _require_int("contract_multiplier", _field(value, "contract_multiplier"), 1)
    ask = _field(value, "ask_per_underlying_unit")
    if ask is not None:
        _require_decimal(
            "ask_per_underlying_unit", ask, minimum=decimal.Decimal("0")
        )
        if ask == decimal.Decimal("0"):
            raise ValueError("ask_per_underlying_unit must be greater than 0")
    _require_enum(
        "ask_authority", _field(value, "ask_authority"), CoreAskAuthority
    )
    _require_text("description", _field(value, "description"))
    _validate_provenance(_field(value, "provenance"))


def _validate_core_structure(value: object) -> None:
    if type(value) is not CoreStructure:
        raise TypeError("structure must have exact type CoreStructure")
    legs = _require_tuple("legs", _field(value, "legs"))
    if not legs:
        raise ValueError("legs must not be empty")
    seen = set()
    for leg in legs:
        _validate_core_leg(leg)
        leg_id = _field(leg, "leg_id")
        if leg_id in seen:
            raise ValueError("leg_id values must be unique")
        seen.add(leg_id)
    _require_text("description", _field(value, "description"))
    _validate_provenance(_field(value, "provenance"))
    if len(legs) == 2:
        first, second = legs
        first_type = _field(first, "option_type")
        second_type = _field(second, "option_type")
        if {first_type, second_type} != {CoreOptionType.CALL, CoreOptionType.PUT}:
            return
        fields = ("underlying", "currency", "strike", "expiration", "quantity", "contract_multiplier")
        if any(_field(first, name) != _field(second, name) for name in fields):
            raise ValueError("straddle legs must match underlying, currency, strike, expiration, quantity, and multiplier")


def _validate_core_payoff_model(value: object) -> None:
    if type(value) is not CorePayoffModel:
        raise TypeError("payoff_model must have exact type CorePayoffModel")
    _require_enum("authority", _field(value, "authority"), CorePayoffAuthority)
    _require_text("model_id", _field(value, "model_id"))
    _require_text("model_version", _field(value, "model_version"))
    _require_text("description", _field(value, "description"))
    _validate_provenance(_field(value, "provenance"))


def _validate_core_cost_component(value: object) -> None:
    if type(value) is not CoreCostComponent:
        raise TypeError("impact component must have exact type CoreCostComponent")
    _require_text("component_id", _field(value, "component_id"))
    _require_enum(
        "status", _field(value, "status"), CoreCostComponentStatus
    )
    upper_bound = _field(value, "upper_bound")
    status = _field(value, "status")
    if status is CoreCostComponentStatus.EXPLICIT_UPPER_BOUND:
        _require_decimal(
            "upper_bound", upper_bound, minimum=decimal.Decimal("0")
        )
    elif upper_bound is not None:
        raise ValueError("unknown cost components must not carry an upper_bound")
    _require_text("currency", _field(value, "currency"))
    _require_text("methodology", _field(value, "methodology"))
    _require_text("description", _field(value, "description"))
    _validate_provenance(_field(value, "provenance"))


def _validate_core_cost_ledger(value: object) -> None:
    if type(value) is not CoreCostLedger:
        raise TypeError("cost_ledger must have exact type CoreCostLedger")
    _require_decimal("premium_bound", _field(value, "premium_bound"), minimum=decimal.Decimal("0"))
    components = _require_tuple("impact_components", _field(value, "impact_components"))
    ids = _require_tuple("required_component_ids", _field(value, "required_component_ids"))
    if not components and not ids:
        raise ValueError("impact_components must declare the cost strategy")
    if not ids:
        raise ValueError("required_component_ids must declare the cost strategy")
    seen = set()
    component_ids = set()
    for component in components:
        _validate_core_cost_component(component)
        if _field(component, "currency") != _field(value, "currency"):
            raise ValueError("impact component currency must match cost ledger currency")
        component_id = _field(component, "component_id")
        if component_id in component_ids:
            raise ValueError("impact component IDs must be unique")
        component_ids.add(component_id)
    for component_id in ids:
        _require_text("required_component_id", component_id)
        if component_id in seen:
            raise ValueError("required component IDs must be unique")
        seen.add(component_id)
    _require_text("currency", _field(value, "currency"))
    _require_text("methodology", _field(value, "methodology"))
    _require_text("description", _field(value, "description"))
    _validate_provenance(_field(value, "provenance"))


def _validate_core_risk_policy(value: object) -> None:
    if type(value) is not CoreRiskRepeatPolicy:
        raise TypeError("risk_policy must have exact type CoreRiskRepeatPolicy")
    _require_decimal("portfolio_value", _field(value, "portfolio_value"), minimum=decimal.Decimal("0"))
    if _field(value, "portfolio_value") == decimal.Decimal("0"):
        raise ValueError("portfolio_value must be greater than 0")
    for name in ("maximum_single_loss_fraction", "maximum_repeated_loss_fraction"):
        _require_decimal(name, _field(value, name), minimum=decimal.Decimal("0"), maximum=decimal.Decimal("1"))
    _require_int("repeat_count", _field(value, "repeat_count"), 1)
    _require_text("methodology", _field(value, "methodology"))
    _require_text("currency", _field(value, "currency"))
    _require_text("description", _field(value, "description"))
    _validate_provenance(_field(value, "provenance"))


def _validate_core_sensitivity_point(value: object) -> None:
    if type(value) is not CoreSensitivityPoint:
        raise TypeError("sensitivity point must have exact type CoreSensitivityPoint")
    _require_text("point_id", _field(value, "point_id"))
    _require_decimal(
        "terminal_underlying_price",
        _field(value, "terminal_underlying_price"),
        minimum=decimal.Decimal("0"),
    )
    asks = _require_tuple("ask_per_leg", _field(value, "ask_per_leg"))
    if not asks:
        raise ValueError("ask_per_leg must not be empty")
    for ask in asks:
        _require_decimal("ask_per_leg item", ask, minimum=decimal.Decimal("0"))
        if ask == decimal.Decimal("0"):
            raise ValueError("ask_per_leg items must be greater than 0")
    _require_text("description", _field(value, "description"))
    _validate_provenance(_field(value, "provenance"))


def _validate_core_sensitivity(value: object) -> None:
    if type(value) is not CoreSensitivity:
        raise TypeError("sensitivity must have exact type CoreSensitivity")
    points = _require_tuple("points", _field(value, "points"))
    if not points:
        raise ValueError("sensitivity points must not be empty")
    seen = set()
    for point in points:
        _validate_core_sensitivity_point(point)
        point_id = _field(point, "point_id")
        if point_id in seen:
            raise ValueError("sensitivity point IDs must be unique")
        seen.add(point_id)
    _require_text("description", _field(value, "description"))
    _validate_provenance(_field(value, "provenance"))


def _validate_core_reviewed_enhancement(value: object) -> None:
    if type(value) is not CoreReviewedEnhancements:
        raise TypeError("reviewed enhancement must have exact type CoreReviewedEnhancements")
    _require_text("enhancement_id", _field(value, "enhancement_id"))
    artifact = _field(value, "reviewed_artifact")
    if artifact is not None and type(artifact) not in {
        VolatilityEnvironmentTransformationResult,
        TailPricingTransformationResult,
    }:
        raise TypeError(
            "reviewed_artifact must be None, VolatilityEnvironmentTransformationResult, "
            "or TailPricingTransformationResult"
        )
    _require_text("description", _field(value, "description"))
    _validate_provenance(_field(value, "provenance"))


def _validate_core_request(value: object) -> None:
    if type(value) is not CoreResearchRequest:
        raise TypeError("request must have exact type CoreResearchRequest")
    _require_text("case_id", _field(value, "case_id"))
    _validate_core_structure(_field(value, "structure"))
    payoff = _field(value, "payoff_model")
    if payoff is not None:
        _validate_core_payoff_model(payoff)
    ledger = _field(value, "cost_ledger")
    if ledger is not None:
        _validate_core_cost_ledger(ledger)
    risk = _field(value, "risk_policy")
    if risk is not None:
        _validate_core_risk_policy(risk)
    sensitivity = _field(value, "sensitivity")
    if sensitivity is not None:
        _validate_core_sensitivity(sensitivity)
    enhancements = _require_tuple("reviewed_enhancements", _field(value, "reviewed_enhancements"))
    seen = set()
    for enhancement in enhancements:
        _validate_core_reviewed_enhancement(enhancement)
        enhancement_id = _field(enhancement, "enhancement_id")
        if enhancement_id in seen:
            raise ValueError("reviewed enhancement IDs must be unique")
        seen.add(enhancement_id)
    _require_text("description", _field(value, "description"))
    _validate_provenance(_field(value, "provenance"))


def _validate_cross_record_matches(request: CoreResearchRequest) -> None:
    structure = _field(request, "structure")
    legs = _field(structure, "legs")
    currency = _field(legs[0], "currency")
    ledger = _field(request, "cost_ledger")
    risk = _field(request, "risk_policy")
    if ledger is not None and _field(ledger, "currency") != currency:
        raise ValueError("cost ledger currency must match structure currency")
    if ledger is not None:
        for component in _field(ledger, "impact_components"):
            if _field(component, "currency") != _field(ledger, "currency"):
                raise ValueError("impact component currency must match cost ledger currency")
    if risk is not None and _field(risk, "currency") != currency:
        raise ValueError("risk policy currency must match structure currency")
    sensitivity = _field(request, "sensitivity")
    if sensitivity is not None:
        leg_count = len(legs)
        for point in _field(sensitivity, "points"):
            if len(_field(point, "ask_per_leg")) != leg_count:
                raise ValueError("sensitivity ask_per_leg must match structure leg count")


__all__ = (
    "CoreAskAuthority",
    "CoreBudgetStatus",
    "CoreBudgetStress",
    "CoreCashLedgerView",
    "CoreCostComponent",
    "CoreCostComponentStatus",
    "CoreCostLedger",
    "CoreDisposition",
    "CoreGeometry",
    "CoreGeometryStatus",
    "CoreHurdle",
    "CoreHurdleSide",
    "CoreHurdleStatus",
    "CoreLeg",
    "CoreOptionType",
    "CorePayoffAuthority",
    "CorePayoffModel",
    "CoreProvenance",
    "CoreReasonCode",
    "CoreResearchRequest",
    "CoreResearchResult",
    "CoreReviewedEnhancements",
    "CoreRiskRepeatPolicy",
    "CoreSensitivity",
    "CoreSensitivityPoint",
    "CoreSensitivityResult",
    "CoreSensitivityResultPoint",
    "CoreSourceReference",
    "CoreStructure",
    "evaluate_core_research",
)


def evaluate_core_research(request: CoreResearchRequest) -> CoreResearchResult:
    """Evaluate one exact Core request using only declared evidence/policy."""

    _validate_core_request(request)
    _validate_cross_record_matches(request)

    structure = _field(request, "structure")
    legs = _field(structure, "legs")
    payoff_model = _field(request, "payoff_model")
    cost_ledger = _field(request, "cost_ledger")
    risk_policy = _field(request, "risk_policy")
    sensitivity = _field(request, "sensitivity")

    observed_ask_cost = _observed_ask_cost(legs)
    cash_ledger, cash_reasons = _cash_ledger_view(
        legs, cost_ledger, observed_ask_cost
    )
    geometry, geometry_reasons = _geometry_view(legs, payoff_model)
    budget_stress, budget_reasons = _budget_view(
        cost_ledger, risk_policy, cash_ledger
    )
    sensitivity_result, sensitivity_reasons = _sensitivity_view(
        sensitivity, legs, payoff_model
    )

    reasons = set(cash_reasons)
    reasons.update(geometry_reasons)
    reasons.update(budget_reasons)
    reasons.update(sensitivity_reasons)

    if len(legs) not in {1, 2}:
        reasons.add(CoreReasonCode.STRUCTURE_UNSUPPORTED)

    ordered_reasons = _ordered_reasons(reasons)
    hard_reject = CoreReasonCode.STRUCTURE_UNSUPPORTED in reasons
    data_reasons = reasons.intersection(_DATA_INSUFFICIENCY_REASONS)
    budget_breach = reasons.intersection(_BUDGET_BREACH_REASONS)
    if hard_reject:
        disposition = CoreDisposition.REJECT
    elif data_reasons:
        disposition = CoreDisposition.DATA_INSUFFICIENT_CORE
    elif budget_breach:
        disposition = CoreDisposition.REJECT
    else:
        disposition = CoreDisposition.RESEARCHABLE_CONVEXITY

    return CoreResearchResult(
        request=request,
        disposition=disposition,
        reasons=ordered_reasons,
        geometry=geometry,
        cash_ledger=cash_ledger,
        budget_stress=budget_stress,
        sensitivity_results=sensitivity_result,
        reviewed_enhancements=_field(request, "reviewed_enhancements"),
    )


_HURDLE_MULTIPLES = (1, 2, 5, 10)
_DATA_INSUFFICIENCY_REASONS = frozenset(
    {
        CoreReasonCode.PAYOFF_MODEL_MISSING,
        CoreReasonCode.PAYOFF_AUTHORITY_UNSUPPORTED,
        CoreReasonCode.ASK_MISSING,
        CoreReasonCode.COST_LEDGER_MISSING,
        CoreReasonCode.MISSING_REQUIRED_COMPONENT,
        CoreReasonCode.UNKNOWN_REQUIRED_COMPONENT,
        CoreReasonCode.UNKNOWN_COST_COMPONENT,
        CoreReasonCode.RISK_POLICY_MISSING,
        CoreReasonCode.SENSITIVITY_MISSING,
    }
)
_BUDGET_BREACH_REASONS = frozenset(
    {
        CoreReasonCode.SINGLE_LOSS_BUDGET_EXCEEDED,
        CoreReasonCode.REPEATED_LOSS_BUDGET_EXCEEDED,
    }
)


def _ordered_reasons(reasons: Iterable[CoreReasonCode]) -> Tuple[CoreReasonCode, ...]:
    present = set(reasons)
    return tuple(code for code in CoreReasonCode if code in present)


def _fraction_from_decimal(value: decimal.Decimal) -> Fraction:
    _require_decimal("calculation value", value)
    return Fraction(value)


def _decimal_from_fraction(value: Fraction) -> decimal.Decimal:
    """Convert an exact rational with a deterministic, isolated context."""

    numerator_digits = len(str(abs(value.numerator)))
    denominator_digits = len(str(abs(value.denominator)))
    context = decimal.Context(
        prec=max(80, numerator_digits + denominator_digits + 20),
        rounding=decimal.ROUND_HALF_EVEN,
        Emin=decimal.MIN_EMIN,
        Emax=decimal.MAX_EMAX,
        capitals=1,
        clamp=0,
    )
    # Context() starts with implementation defaults for traps.  Set every
    # signal explicitly so caller rounding/trap flags cannot leak in.
    for signal in context.traps:
        context.traps[signal] = False
    with decimal.localcontext(context):
        return decimal.Decimal(value.numerator) / decimal.Decimal(value.denominator)


def _decimal_sum(values: Iterable[decimal.Decimal]) -> decimal.Decimal:
    total = Fraction(0, 1)
    for value in values:
        total += _fraction_from_decimal(value)
    return _decimal_from_fraction(total)


def _decimal_product(*values: object) -> decimal.Decimal:
    total = Fraction(1, 1)
    for value in values:
        if type(value) is int:
            total *= value
        else:
            total *= _fraction_from_decimal(value)  # type: ignore[arg-type]
    return _decimal_from_fraction(total)


def _decimal_ratio(numerator: decimal.Decimal, denominator: decimal.Decimal) -> decimal.Decimal:
    return _decimal_from_fraction(
        _fraction_from_decimal(numerator) / _fraction_from_decimal(denominator)
    )


def _observed_ask_cost(legs: Tuple[CoreLeg, ...]) -> Optional[decimal.Decimal]:
    asks = tuple(_field(leg, "ask_per_underlying_unit") for leg in legs)
    if any(ask is None for ask in asks):
        return None
    return _decimal_sum(
        _decimal_product(
            _field(leg, "quantity"),
            _field(leg, "contract_multiplier"),
            _field(leg, "ask_per_underlying_unit"),
        )
        for leg in legs
    )


def _cash_ledger_view(
    legs: Tuple[CoreLeg, ...],
    ledger: Optional[CoreCostLedger],
    observed_ask_cost: Optional[decimal.Decimal],
) -> Tuple[CoreCashLedgerView, Tuple[CoreReasonCode, ...]]:
    if ledger is None:
        return (
            CoreCashLedgerView(
                observed_ask_cost=observed_ask_cost,
                known_components=(),
                known_total=observed_ask_cost,
                conditional_total_upper_bound=None,
                unknown_component_ids=(),
                missing_required_component_ids=(),
            ),
            (CoreReasonCode.COST_LEDGER_MISSING,),
        )

    components = _field(ledger, "impact_components")
    known_components = tuple(
        component
        for component in components
        if _field(component, "status") is CoreCostComponentStatus.EXPLICIT_UPPER_BOUND
    )
    unknown_ids = tuple(
        _field(component, "component_id")
        for component in components
        if _field(component, "status") is CoreCostComponentStatus.UNKNOWN
    )
    component_ids = {_field(component, "component_id") for component in components}
    missing_required = tuple(
        component_id
        for component_id in _field(ledger, "required_component_ids")
        if component_id not in component_ids
    )
    known_total = _decimal_sum(
        [_field(ledger, "premium_bound")]
        + [_field(component, "upper_bound") for component in known_components]
    )
    conditional_total = None
    if not unknown_ids and not missing_required:
        conditional_total = _decimal_sum(
            [_field(ledger, "premium_bound")]
            + [_field(component, "upper_bound") for component in components]
        )

    if observed_ask_cost is not None and _fraction_from_decimal(
        _field(ledger, "premium_bound")
    ) < _fraction_from_decimal(observed_ask_cost):
        raise ValueError(
            "premium_bound must be at least the exact observed position ask cost"
        )

    reasons = []
    if missing_required:
        reasons.append(CoreReasonCode.MISSING_REQUIRED_COMPONENT)
    if any(
        component_id in unknown_ids
        for component_id in _field(ledger, "required_component_ids")
    ):
        reasons.append(CoreReasonCode.UNKNOWN_REQUIRED_COMPONENT)
    if unknown_ids:
        reasons.append(CoreReasonCode.UNKNOWN_COST_COMPONENT)
    return (
        CoreCashLedgerView(
            observed_ask_cost=observed_ask_cost,
            known_components=known_components,
            known_total=known_total,
            conditional_total_upper_bound=conditional_total,
            unknown_component_ids=unknown_ids,
            missing_required_component_ids=missing_required,
        ),
        tuple(reasons),
    )


def _supported_grammar(legs: Tuple[CoreLeg, ...]) -> Optional[str]:
    if len(legs) != 1 and len(legs) != 2:
        return None
    if len(legs) == 1:
        option_type = _field(legs[0], "option_type")
        if option_type is CoreOptionType.CALL:
            return "call"
        if option_type is CoreOptionType.PUT:
            return "put"
        return None
    option_types = {_field(leg, "option_type") for leg in legs}
    if option_types == {CoreOptionType.CALL, CoreOptionType.PUT}:
        return "straddle"
    return None


def _geometry_view(
    legs: Tuple[CoreLeg, ...], payoff_model: Optional[CorePayoffModel]
) -> Tuple[CoreGeometry, Tuple[CoreReasonCode, ...]]:
    grammar = _supported_grammar(legs)
    if grammar is None:
        return (
            CoreGeometry(
                status=CoreGeometryStatus.DATA_INSUFFICIENT_CORE,
                payoff_authority=(
                    _field(payoff_model, "authority") if payoff_model is not None else None
                ),
                ask_basis_per_underlying_unit=None,
                hurdles=(),
            ),
            (CoreReasonCode.STRUCTURE_UNSUPPORTED,),
        )

    missing: list = []
    if payoff_model is None:
        missing.append(CoreReasonCode.PAYOFF_MODEL_MISSING)
    asks = tuple(_field(leg, "ask_per_underlying_unit") for leg in legs)
    if any(ask is None for ask in asks):
        missing.append(CoreReasonCode.ASK_MISSING)

    authority = _field(payoff_model, "authority") if payoff_model is not None else None
    if missing:
        hurdles = _unavailable_hurdles(grammar, missing)
        return (
            CoreGeometry(
                status=CoreGeometryStatus.DATA_INSUFFICIENT_CORE,
                payoff_authority=authority,
                ask_basis_per_underlying_unit=None,
                hurdles=hurdles,
            ),
            tuple(missing),
        )

    ask_basis = _decimal_sum(ask for ask in asks if ask is not None)
    strike = _field(legs[0], "strike")
    hurdles = _available_hurdles(grammar, strike, ask_basis)
    return (
        CoreGeometry(
            status=CoreGeometryStatus.AVAILABLE,
            payoff_authority=authority,
            ask_basis_per_underlying_unit=ask_basis,
            hurdles=hurdles,
        ),
        (),
    )


def _hurdle_branches(grammar: str) -> Tuple[CoreHurdleSide, ...]:
    if grammar == "call":
        return (CoreHurdleSide.UP,)
    if grammar == "put":
        return (CoreHurdleSide.DOWN,)
    return (CoreHurdleSide.DOWN, CoreHurdleSide.UP)


def _unavailable_hurdles(
    grammar: str, reasons: Iterable[CoreReasonCode]
) -> Tuple[CoreHurdle, ...]:
    reason_text = ",".join(reason.value for reason in reasons)
    return tuple(
        CoreHurdle(
            gross_value_multiple=multiple,
            side=branch,
            status=CoreHurdleStatus.UNAVAILABLE,
            terminal_underlying_price=None,
            reason=reason_text,
        )
        for multiple in _HURDLE_MULTIPLES
        for branch in _hurdle_branches(grammar)
    )


def _available_hurdles(
    grammar: str, strike: decimal.Decimal, ask_basis: decimal.Decimal
) -> Tuple[CoreHurdle, ...]:
    records = []
    for multiple in _HURDLE_MULTIPLES:
        for branch in _hurdle_branches(grammar):
            if branch is CoreHurdleSide.UP:
                terminal = _decimal_from_fraction(
                    _fraction_from_decimal(strike)
                    + multiple * _fraction_from_decimal(ask_basis)
                )
            else:
                terminal = _decimal_from_fraction(
                    _fraction_from_decimal(strike)
                    - multiple * _fraction_from_decimal(ask_basis)
                )
            if terminal < decimal.Decimal("0"):
                records.append(
                    CoreHurdle(
                        gross_value_multiple=multiple,
                        side=branch,
                        status=CoreHurdleStatus.UNAVAILABLE,
                        terminal_underlying_price=None,
                        reason="negative_terminal_underlying_price",
                    )
                )
            else:
                records.append(
                    CoreHurdle(
                        gross_value_multiple=multiple,
                        side=branch,
                        status=CoreHurdleStatus.AVAILABLE,
                        terminal_underlying_price=terminal,
                        reason=None,
                    )
                )
    return tuple(records)


def _budget_view(
    ledger: Optional[CoreCostLedger],
    risk_policy: Optional[CoreRiskRepeatPolicy],
    cash_ledger: CoreCashLedgerView,
) -> Tuple[CoreBudgetStress, Tuple[CoreReasonCode, ...]]:
    missing = set()
    if ledger is None:
        missing.add(CoreReasonCode.COST_LEDGER_MISSING)
    if risk_policy is None:
        missing.add(CoreReasonCode.RISK_POLICY_MISSING)
    if cash_ledger.missing_required_component_ids:
        missing.add(CoreReasonCode.MISSING_REQUIRED_COMPONENT)
    if cash_ledger.unknown_component_ids:
        missing.add(CoreReasonCode.UNKNOWN_COST_COMPONENT)
        required_ids = set(_field(ledger, "required_component_ids")) if ledger is not None else set()
        if required_ids.intersection(cash_ledger.unknown_component_ids):
            missing.add(CoreReasonCode.UNKNOWN_REQUIRED_COMPONENT)
    if cash_ledger.conditional_total_upper_bound is None:
        if ledger is not None:
            missing.add(CoreReasonCode.UNKNOWN_REQUIRED_COMPONENT)
        else:
            missing.add(CoreReasonCode.COST_LEDGER_MISSING)

    if missing or risk_policy is None or cash_ledger.conditional_total_upper_bound is None:
        return (
            CoreBudgetStress(
                status=CoreBudgetStatus.DATA_INSUFFICIENT_CORE,
                single_cost_upper_bound=None,
                repeated_cost_upper_bound=None,
                single_loss_fraction=None,
                repeated_loss_fraction=None,
                missing_assumptions=_ordered_reasons(missing),
            ),
            tuple(missing),
        )

    single_cost = cash_ledger.conditional_total_upper_bound
    repeated_cost = _decimal_product(single_cost, _field(risk_policy, "repeat_count"))
    single_fraction = _decimal_ratio(single_cost, _field(risk_policy, "portfolio_value"))
    repeated_fraction = _decimal_ratio(repeated_cost, _field(risk_policy, "portfolio_value"))
    single_fraction_exact = _fraction_from_decimal(single_cost) / _fraction_from_decimal(
        _field(risk_policy, "portfolio_value")
    )
    repeated_fraction_exact = _fraction_from_decimal(repeated_cost) / _fraction_from_decimal(
        _field(risk_policy, "portfolio_value")
    )
    reasons = set()
    if single_fraction_exact > _fraction_from_decimal(
        _field(risk_policy, "maximum_single_loss_fraction")
    ):
        reasons.add(CoreReasonCode.SINGLE_LOSS_BUDGET_EXCEEDED)
    if repeated_fraction_exact > _fraction_from_decimal(
        _field(risk_policy, "maximum_repeated_loss_fraction")
    ):
        reasons.add(CoreReasonCode.REPEATED_LOSS_BUDGET_EXCEEDED)
    status = (
        CoreBudgetStatus.CONDITIONAL_BREACH
        if reasons
        else CoreBudgetStatus.CONDITIONAL_PASS
    )
    return (
        CoreBudgetStress(
            status=status,
            single_cost_upper_bound=single_cost,
            repeated_cost_upper_bound=repeated_cost,
            single_loss_fraction=single_fraction,
            repeated_loss_fraction=repeated_fraction,
            missing_assumptions=(),
        ),
        tuple(reasons),
    )


def _sensitivity_view(
    sensitivity: Optional[CoreSensitivity],
    legs: Tuple[CoreLeg, ...],
    payoff_model: Optional[CorePayoffModel],
) -> Tuple[Optional[CoreSensitivityResult], Tuple[CoreReasonCode, ...]]:
    if sensitivity is None:
        return None, (CoreReasonCode.SENSITIVITY_MISSING,)
    points = _field(sensitivity, "points")
    # The shape was checked at entry; retain exact point identity and values.
    if any(len(_field(point, "ask_per_leg")) != len(legs) for point in points):
        raise ValueError("sensitivity ask_per_leg must match structure leg count")
    grammar = _supported_grammar(legs)
    if grammar is None:
        return (
            CoreSensitivityResult(
                points=tuple(
                    _sensitivity_result_point(
                        point,
                        None,
                        None,
                        _declared_ask_basis(point),
                        None,
                        (),
                        "structure_unsupported",
                    )
                    for point in points
                )
            ),
            (),
        )

    results = []
    for point in points:
        ask_basis = _declared_ask_basis(point)
        if payoff_model is None:
            results.append(
                _sensitivity_result_point(
                    point,
                    None,
                    None,
                    ask_basis,
                    None,
                    _unavailable_hurdles(
                        grammar, (CoreReasonCode.PAYOFF_MODEL_MISSING,)
                    ),
                    "payoff_model_missing",
                )
            )
            continue
        terminal = _field(point, "terminal_underlying_price")
        per_unit = _gross_payoff_per_underlying_unit(legs, terminal)
        position_payoff = _decimal_sum(
            _decimal_product(
                _leg_gross_payoff(leg, terminal),
                _field(leg, "quantity"),
                _field(leg, "contract_multiplier"),
            )
            for leg in legs
        )
        response = _decimal_ratio(per_unit, ask_basis)
        strike = _field(legs[0], "strike")
        hurdles = _available_hurdles(grammar, strike, ask_basis)
        results.append(
            _sensitivity_result_point(
                point,
                per_unit,
                position_payoff,
                ask_basis,
                response,
                hurdles,
                None,
            )
        )
    return CoreSensitivityResult(points=tuple(results)), ()


def _sensitivity_result_point(
    point: CoreSensitivityPoint,
    per_unit: Optional[decimal.Decimal],
    position_payoff: Optional[decimal.Decimal],
    ask_basis: Optional[decimal.Decimal],
    response: Optional[decimal.Decimal],
    hurdles: Tuple[CoreHurdle, ...],
    unavailable_reason: Optional[str],
) -> CoreSensitivityResultPoint:
    return CoreSensitivityResultPoint(
        point=point,
        conditional_gross_payoff_per_underlying_unit=per_unit,
        conditional_position_payoff=position_payoff,
        declared_ask_basis_per_underlying_unit=ask_basis,
        gross_response_multiple=response,
        gross_hurdles=hurdles,
        unavailable_reason=unavailable_reason,
    )


def _declared_ask_basis(point: CoreSensitivityPoint) -> decimal.Decimal:
    return _decimal_sum(_field(point, "ask_per_leg"))


def _leg_gross_payoff(leg: CoreLeg, terminal: decimal.Decimal) -> decimal.Decimal:
    strike = _field(leg, "strike")
    option_type = _field(leg, "option_type")
    if option_type is CoreOptionType.CALL:
        difference = _decimal_from_fraction(
            _fraction_from_decimal(terminal) - _fraction_from_decimal(strike)
        )
    else:
        difference = _decimal_from_fraction(
            _fraction_from_decimal(strike) - _fraction_from_decimal(terminal)
        )
    return difference if difference > decimal.Decimal("0") else D_ZERO


def _gross_payoff_per_underlying_unit(
    legs: Tuple[CoreLeg, ...], terminal: decimal.Decimal
) -> decimal.Decimal:
    return _decimal_sum(_leg_gross_payoff(leg, terminal) for leg in legs)
