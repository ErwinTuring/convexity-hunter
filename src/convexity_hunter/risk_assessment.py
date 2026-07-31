"""Standalone exact structure-affordability evidence."""

import datetime
import decimal
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .evidence import OptionLeg, OptionStructure, StructureCosts
from .market_data import (
    CalculationInputReference,
    CalculationLineage,
    CalculationQualityFlag,
    canonicalize_lineage_parameters,
)
from . import market_data_transformations as _transformations
from .market_data_transformations import (
    ExactRational,
    StructureCostsTransformationResult,
)


__all__ = (
    "PortfolioValueAssumption",
    "RiskBudgetAssumptions",
    "AffordabilityStatus",
    "AffordabilityReasonCode",
    "StructureAffordabilityEvidence",
    "StructureAffordabilityAssessmentResult",
    "assess_structure_affordability",
)


_PARAMETER_KEYS = {
    "schema_version",
    "output_architecture",
    "currency",
    "risk_scope",
    "structure_costs_dependency",
    "risk_budget_assumptions",
    "calculation_values",
    "affordability_rule",
    "outcome",
    "limitations",
}
_RISK_SCOPE_KEYS = {
    "single_position",
    "repeated_attempts",
    "annual_budget",
    "existing_committed_exposure",
    "inverse_sizing",
}
_DEPENDENCY_KEYS = {
    "calculation_id",
    "calculation_type",
    "methodology_id",
    "methodology_version",
    "calculated_at",
    "parameters_json",
    "quality_flags",
    "input_rule",
}
_ASSUMPTION_KEYS = {
    "portfolio_value",
    "maximum_single_structure_loss_fraction",
    "maximum_repeated_loss_fraction",
    "risk_budget_methodology",
    "legacy_portfolio_value_correspondence",
    "missing_assumption_policy",
}
_PORTFOLIO_KEYS = {"amount", "as_of_date", "methodology", "currency"}
_CALCULATION_VALUE_KEYS = {
    "single_position_maximum_loss",
    "repeated_bet_count",
    "repeated_aggregate_maximum_loss",
    "portfolio_value",
    "single_loss_fraction",
    "repeated_loss_fraction",
    "maximum_single_structure_loss_fraction",
    "maximum_repeated_loss_fraction",
}
_RULE_KEYS = {
    "required_assumptions",
    "single_comparison",
    "repeated_comparison",
    "complete_rule",
    "equality_boundary",
    "incomplete_precedence",
}
_OUTCOME_KEYS = {"status", "reason_codes"}
_RATIONAL_KEYS = {"numerator", "denominator"}
_PROPAGATED_FLAGS = {
    CalculationQualityFlag.INTERPOLATED,
    CalculationQualityFlag.CORRECTION_SELECTED,
    CalculationQualityFlag.COMPOSITE_INPUT_USED,
}
_PROHIBITED_RESULT_FLAGS = {
    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
    CalculationQualityFlag.ANNUALIZED,
    CalculationQualityFlag.ADJUSTED_INPUT_USED,
}
_PROHIBITED_DEPENDENCY_FLAGS = {
    CalculationQualityFlag.ANNUALIZED,
    CalculationQualityFlag.ADJUSTED_INPUT_USED,
    CalculationQualityFlag.INCOMPLETE_INPUT_USED,
}


def _required_string(label: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must have exact type str")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must not be empty")
    return normalized


def _strict_rational(value: object, label: str) -> ExactRational:
    if type(value) is not ExactRational:
        raise TypeError(f"{label} must have exact type ExactRational")
    if type(value.numerator) is not int:
        raise TypeError(f"{label} numerator must have exact type int")
    if type(value.denominator) is not int:
        raise TypeError(f"{label} denominator must have exact type int")
    rebuilt = ExactRational(value.numerator, value.denominator)
    if (
        rebuilt.numerator != value.numerator
        or rebuilt.denominator != value.denominator
    ):
        raise ValueError(f"{label} must be a canonical reduced rational")
    return rebuilt


def _rational_in_unit_interval(value: ExactRational, label: str) -> None:
    if value.numerator < 0 or value.numerator > value.denominator:
        raise ValueError(f"{label} must be within inclusive range [0, 1]")


def _rationals_equal(left: object, right: object) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return (
        type(left) is ExactRational
        and type(right) is ExactRational
        and type(left.numerator) is int
        and type(left.denominator) is int
        and left.numerator == right.numerator
        and left.denominator == right.denominator
    )


def _rational_less_equal(left: ExactRational, right: ExactRational) -> bool:
    return (
        left.numerator * right.denominator
        <= right.numerator * left.denominator
    )


def _decimal_to_rational(value: object) -> ExactRational:
    try:
        return _transformations._exact_rational_from_decimal(value)
    except (MemoryError, OverflowError, decimal.DecimalException) as error:
        raise ValueError(
            "Decimal cannot be represented as an exact rational"
        ) from error


def _rational_divide(
    numerator: ExactRational, denominator: ExactRational
) -> ExactRational:
    if denominator.numerator == 0:
        raise ValueError("exact rational divisor must be nonzero")
    sign = -1 if denominator.numerator < 0 else 1
    try:
        return ExactRational(
            numerator.numerator * denominator.denominator * sign,
            numerator.denominator * abs(denominator.numerator),
        )
    except (MemoryError, OverflowError) as error:
        raise ValueError("exact rational division exhausted resources") from error


def _multiply_decimal_int_exact(value: decimal.Decimal, multiplier: int) -> decimal.Decimal:
    sign, digits, exponent = value.as_tuple()
    coefficient = 0
    try:
        for digit in digits:
            coefficient = coefficient * 10 + digit
        coefficient *= multiplier
        product_digits = tuple(int(item) for item in str(coefficient))
        return decimal.Decimal((sign, product_digits, exponent))
    except (MemoryError, OverflowError, ValueError) as error:
        raise ValueError("exact Decimal multiplication exhausted resources") from error


@dataclass(frozen=True)
class PortfolioValueAssumption:
    amount: decimal.Decimal
    as_of_date: datetime.date
    methodology: str

    def __post_init__(self) -> None:
        if type(self.amount) is not decimal.Decimal:
            raise TypeError("amount must have exact type Decimal")
        if not self.amount.is_finite() or self.amount <= 0:
            raise ValueError("amount must be finite and strictly positive")
        if type(self.as_of_date) is not datetime.date:
            raise TypeError("as_of_date must have exact type date")
        methodology = _required_string("methodology", self.methodology)
        object.__setattr__(self, "methodology", methodology)


@dataclass(frozen=True)
class RiskBudgetAssumptions:
    portfolio_value: Optional[PortfolioValueAssumption] = None
    maximum_single_structure_loss_fraction: Optional[ExactRational] = None
    maximum_repeated_loss_fraction: Optional[ExactRational] = None
    risk_budget_methodology: Optional[str] = None

    def __post_init__(self) -> None:
        if (
            self.portfolio_value is not None
            and type(self.portfolio_value) is not PortfolioValueAssumption
        ):
            raise TypeError(
                "portfolio_value must have exact type "
                "PortfolioValueAssumption or be None"
            )
        if self.portfolio_value is not None:
            _strict_portfolio(self.portfolio_value)
        for label, value in (
            (
                "maximum_single_structure_loss_fraction",
                self.maximum_single_structure_loss_fraction,
            ),
            (
                "maximum_repeated_loss_fraction",
                self.maximum_repeated_loss_fraction,
            ),
        ):
            if value is not None:
                rebuilt = _strict_rational(value, label)
                _rational_in_unit_interval(rebuilt, label)
        methodology = self.risk_budget_methodology
        if methodology is not None:
            methodology = _required_string(
                "risk_budget_methodology", methodology
            )
            object.__setattr__(
                self, "risk_budget_methodology", methodology
            )


class AffordabilityStatus(str, Enum):
    AFFORDABLE = "affordable"
    NOT_AFFORDABLE = "not_affordable"
    DATA_INSUFFICIENT = "data_insufficient"


class AffordabilityReasonCode(str, Enum):
    MISSING_PORTFOLIO_VALUE = "missing_portfolio_value"
    MISSING_SINGLE_LOSS_BOUNDARY = "missing_single_loss_boundary"
    MISSING_REPEATED_LOSS_BOUNDARY = "missing_repeated_loss_boundary"
    MISSING_RISK_BUDGET_METHODOLOGY = "missing_risk_budget_methodology"
    SINGLE_LOSS_EXCEEDS_BOUNDARY = "single_loss_exceeds_boundary"
    REPEATED_LOSS_EXCEEDS_BOUNDARY = "repeated_loss_exceeds_boundary"


def _strict_portfolio(value: object) -> PortfolioValueAssumption:
    if type(value) is not PortfolioValueAssumption:
        raise TypeError(
            "portfolio_value must have exact type PortfolioValueAssumption"
        )
    rebuilt = PortfolioValueAssumption(
        value.amount, value.as_of_date, value.methodology
    )
    if (
        type(value.amount) is not decimal.Decimal
        or value.amount != rebuilt.amount
        or type(value.as_of_date) is not datetime.date
        or value.as_of_date != rebuilt.as_of_date
        or type(value.methodology) is not str
        or value.methodology != rebuilt.methodology
    ):
        raise ValueError("portfolio_value is not in canonical constructor state")
    return rebuilt


def _strict_assumptions(value: object) -> RiskBudgetAssumptions:
    if type(value) is not RiskBudgetAssumptions:
        raise TypeError("assumptions must have exact type RiskBudgetAssumptions")
    portfolio = (
        None
        if value.portfolio_value is None
        else _strict_portfolio(value.portfolio_value)
    )
    single = (
        None
        if value.maximum_single_structure_loss_fraction is None
        else _strict_rational(
            value.maximum_single_structure_loss_fraction,
            "maximum_single_structure_loss_fraction",
        )
    )
    repeated = (
        None
        if value.maximum_repeated_loss_fraction is None
        else _strict_rational(
            value.maximum_repeated_loss_fraction,
            "maximum_repeated_loss_fraction",
        )
    )
    rebuilt = RiskBudgetAssumptions(
        portfolio, single, repeated, value.risk_budget_methodology
    )
    if (
        (value.portfolio_value is None) != (rebuilt.portfolio_value is None)
        or (
            value.portfolio_value is not None
            and (
                value.portfolio_value.amount != rebuilt.portfolio_value.amount
                or value.portfolio_value.as_of_date
                != rebuilt.portfolio_value.as_of_date
                or value.portfolio_value.methodology
                != rebuilt.portfolio_value.methodology
            )
        )
        or not _rationals_equal(
            value.maximum_single_structure_loss_fraction,
            rebuilt.maximum_single_structure_loss_fraction,
        )
        or not _rationals_equal(
            value.maximum_repeated_loss_fraction,
            rebuilt.maximum_repeated_loss_fraction,
        )
        or type(value.risk_budget_methodology)
        is not type(rebuilt.risk_budget_methodology)
        or value.risk_budget_methodology != rebuilt.risk_budget_methodology
    ):
        raise ValueError("assumptions are not in canonical constructor state")
    return rebuilt


def _strict_structure(value: object) -> OptionStructure:
    if type(value) is not OptionStructure:
        raise TypeError("structure must have exact type OptionStructure")
    if type(value.legs) is not tuple:
        raise TypeError("structure legs must have exact type tuple")
    if len(value.legs) not in (1, 2):
        raise ValueError("structure must have one or two legs")
    rebuilt_legs = tuple(_strict_option_leg(leg) for leg in value.legs)
    if type(value.assumed_portfolio_value) not in (int, float):
        raise TypeError(
            "assumed_portfolio_value must have exact type int or float"
        )
    if (
        not math.isfinite(value.assumed_portfolio_value)
        or value.assumed_portfolio_value <= 0
    ):
        raise ValueError(
            "assumed_portfolio_value must be finite and strictly positive"
        )
    if type(value.expected_holding_days) is not int:
        raise TypeError("expected_holding_days must have exact type int")
    if value.expected_holding_days < 0:
        raise ValueError("expected_holding_days must be nonnegative")
    rebuilt = OptionStructure(
        rebuilt_legs,
        value.assumed_portfolio_value,
        value.expected_holding_days,
    )
    if (
        type(rebuilt.legs) is not tuple
        or len(rebuilt.legs) != len(value.legs)
        or any(
            not _option_legs_match(actual, expected)
            for actual, expected in zip(value.legs, rebuilt.legs)
        )
        or type(rebuilt.assumed_portfolio_value)
        is not type(value.assumed_portfolio_value)
        or rebuilt.assumed_portfolio_value
        != value.assumed_portfolio_value
        or type(rebuilt.expected_holding_days) is not int
        or rebuilt.expected_holding_days != value.expected_holding_days
    ):
        raise ValueError("structure is not in canonical constructor state")
    return rebuilt


def _strict_option_leg(value: object) -> OptionLeg:
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
        raise TypeError("leg strike must have exact type int or float")
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
    if not _option_legs_match(value, rebuilt):
        raise ValueError("leg is not in canonical constructor state")
    return rebuilt


def _option_legs_match(left: object, right: object) -> bool:
    return (
        type(left) is OptionLeg
        and type(right) is OptionLeg
        and type(left.underlying) is str
        and left.underlying == right.underlying
        and type(left.option_type) is str
        and left.option_type == right.option_type
        and type(left.strike) is type(right.strike)
        and left.strike == right.strike
        and type(left.expiration) is datetime.date
        and left.expiration == right.expiration
        and type(left.quantity) is int
        and left.quantity == right.quantity
        and type(left.contract_multiplier) is int
        and left.contract_multiplier == right.contract_multiplier
    )


def _strict_input_reference(
    value: object,
) -> CalculationInputReference:
    if type(value) is not CalculationInputReference:
        raise TypeError(
            "every input must have exact type CalculationInputReference"
        )
    if type(value.record_id) is not str:
        raise TypeError("input record_id must have exact type str")
    if not value.record_id or value.record_id.strip() != value.record_id:
        raise ValueError("input record_id must be nonempty normalized text")
    if type(value.normalized_at) is not datetime.datetime:
        raise TypeError("input normalized_at must have exact type datetime")
    try:
        if (
            value.normalized_at.tzinfo is None
            or value.normalized_at.utcoffset() is None
        ):
            raise ValueError("input normalized_at must be timezone-aware")
        normalized_at = value.normalized_at.astimezone(
            datetime.timezone.utc
        )
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError(
            "input normalized_at must be representable in UTC"
        ) from error
    if (
        value.normalized_at.tzinfo is not datetime.timezone.utc
        or value.normalized_at != normalized_at
    ):
        raise ValueError("input normalized_at must be normalized to UTC")
    if type(value.source_ids) is not tuple:
        raise TypeError("input source_ids must have exact type tuple")
    if not value.source_ids:
        raise ValueError("input source_ids must not be empty")
    if any(type(item) is not str for item in value.source_ids):
        raise TypeError("every input source_id must have exact type str")
    if any(not item or item.strip() != item for item in value.source_ids):
        raise ValueError("input source_ids must be nonempty normalized text")
    if (
        len(set(value.source_ids)) != len(value.source_ids)
        or value.source_ids != tuple(sorted(value.source_ids))
    ):
        raise ValueError("input source_ids must be unique and ordered")
    rebuilt = CalculationInputReference(
        value.record_id, normalized_at, value.source_ids
    )
    if not _input_references_match(value, rebuilt):
        raise ValueError(
            "input reference is not in canonical constructor state"
        )
    return rebuilt


def _input_references_match(left: object, right: object) -> bool:
    return (
        type(left) is CalculationInputReference
        and type(right) is CalculationInputReference
        and type(left.record_id) is str
        and type(right.record_id) is str
        and left.record_id == right.record_id
        and type(left.normalized_at) is datetime.datetime
        and type(right.normalized_at) is datetime.datetime
        and left.normalized_at.tzinfo is datetime.timezone.utc
        and right.normalized_at.tzinfo is datetime.timezone.utc
        and left.normalized_at == right.normalized_at
        and type(left.source_ids) is tuple
        and type(right.source_ids) is tuple
        and len(left.source_ids) == len(right.source_ids)
        and all(
            type(left_item) is str
            and type(right_item) is str
            and left_item == right_item
            for left_item, right_item in zip(
                left.source_ids, right.source_ids
            )
        )
    )


def _strict_inputs(
    values: object,
    calculated_at: Optional[datetime.datetime] = None,
) -> Tuple[CalculationInputReference, ...]:
    if type(values) is not tuple:
        raise TypeError("inputs must have exact type tuple")
    if not values:
        raise ValueError("inputs must contain at least one item")
    rebuilt = tuple(_strict_input_reference(item) for item in values)
    record_ids = tuple(item.record_id for item in rebuilt)
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("input record IDs must not contain duplicates")
    if record_ids != tuple(sorted(record_ids)):
        raise ValueError("inputs must be ordered by record_id")
    if calculated_at is not None and any(
        calculated_at < item.normalized_at for item in rebuilt
    ):
        raise ValueError("calculation must not precede any input")
    return rebuilt


def _input_tuples_match(left: object, right: object) -> bool:
    return (
        type(left) is tuple
        and type(right) is tuple
        and len(left) == len(right)
        and all(
            _input_references_match(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    )


def _expected_outcome(
    assumptions: RiskBudgetAssumptions,
    single_fraction: Optional[ExactRational],
    repeated_fraction: Optional[ExactRational],
) -> tuple:
    missing = []
    if assumptions.portfolio_value is None:
        missing.append(AffordabilityReasonCode.MISSING_PORTFOLIO_VALUE)
    if assumptions.maximum_single_structure_loss_fraction is None:
        missing.append(
            AffordabilityReasonCode.MISSING_SINGLE_LOSS_BOUNDARY
        )
    if assumptions.maximum_repeated_loss_fraction is None:
        missing.append(
            AffordabilityReasonCode.MISSING_REPEATED_LOSS_BOUNDARY
        )
    if assumptions.risk_budget_methodology is None:
        missing.append(
            AffordabilityReasonCode.MISSING_RISK_BUDGET_METHODOLOGY
        )
    if missing:
        return AffordabilityStatus.DATA_INSUFFICIENT, tuple(missing)
    if single_fraction is None or repeated_fraction is None:
        raise ValueError("complete assumptions require both loss fractions")
    breaches = []
    if not _rational_less_equal(
        single_fraction,
        assumptions.maximum_single_structure_loss_fraction,
    ):
        breaches.append(
            AffordabilityReasonCode.SINGLE_LOSS_EXCEEDS_BOUNDARY
        )
    if not _rational_less_equal(
        repeated_fraction,
        assumptions.maximum_repeated_loss_fraction,
    ):
        breaches.append(
            AffordabilityReasonCode.REPEATED_LOSS_EXCEEDS_BOUNDARY
        )
    if breaches:
        return AffordabilityStatus.NOT_AFFORDABLE, tuple(breaches)
    return AffordabilityStatus.AFFORDABLE, ()


@dataclass(frozen=True)
class StructureAffordabilityEvidence:
    structure: OptionStructure
    as_of_date: datetime.date
    assumptions: RiskBudgetAssumptions
    single_position_maximum_loss: decimal.Decimal
    repeated_bet_count: int
    repeated_aggregate_maximum_loss: decimal.Decimal
    single_loss_fraction: Optional[ExactRational]
    repeated_loss_fraction: Optional[ExactRational]
    status: AffordabilityStatus
    reason_codes: Tuple[AffordabilityReasonCode, ...]

    def __post_init__(self) -> None:
        with decimal.localcontext():
            structure = _strict_structure(self.structure)
            if type(self.as_of_date) is not datetime.date:
                raise TypeError("as_of_date must have exact type date")
            if any(
                self.as_of_date >= leg.expiration for leg in structure.legs
            ):
                raise ValueError("as_of_date must precede every expiration")
            assumptions = _strict_assumptions(self.assumptions)
            if assumptions.portfolio_value is not None:
                if assumptions.portfolio_value.as_of_date != self.as_of_date:
                    raise ValueError(
                        "portfolio-value date must equal evidence as_of_date"
                    )
                try:
                    legacy_portfolio_value = decimal.Decimal(
                        str(structure.assumed_portfolio_value)
                    )
                except decimal.InvalidOperation as error:
                    raise ValueError(
                        "legacy portfolio value cannot be represented exactly"
                    ) from error
                if (
                    assumptions.portfolio_value.amount
                    != legacy_portfolio_value
                ):
                    raise ValueError(
                        "portfolio value contradicts legacy structure metadata"
                    )
            for label, value in (
                (
                    "single_position_maximum_loss",
                    self.single_position_maximum_loss,
                ),
                (
                    "repeated_aggregate_maximum_loss",
                    self.repeated_aggregate_maximum_loss,
                ),
            ):
                if type(value) is not decimal.Decimal:
                    raise TypeError(f"{label} must have exact type Decimal")
                if not value.is_finite() or value <= 0:
                    raise ValueError(
                        f"{label} must be finite and strictly positive"
                    )
            if type(self.repeated_bet_count) is not int:
                raise TypeError("repeated_bet_count must have exact type int")
            if self.repeated_bet_count <= 0:
                raise ValueError("repeated_bet_count must be strictly positive")
            expected_aggregate = _multiply_decimal_int_exact(
                self.single_position_maximum_loss,
                self.repeated_bet_count,
            )
            if self.repeated_aggregate_maximum_loss != expected_aggregate:
                raise ValueError("repeated aggregate maximum loss is incorrect")
            for label, value in (
                ("single_loss_fraction", self.single_loss_fraction),
                ("repeated_loss_fraction", self.repeated_loss_fraction),
            ):
                if value is not None:
                    _strict_rational(value, label)
            if assumptions.portfolio_value is None:
                expected_single = None
                expected_repeated = None
            else:
                portfolio = _decimal_to_rational(
                    assumptions.portfolio_value.amount
                )
                expected_single = _rational_divide(
                    _decimal_to_rational(
                        self.single_position_maximum_loss
                    ),
                    portfolio,
                )
                expected_repeated = _rational_divide(
                    _decimal_to_rational(
                        self.repeated_aggregate_maximum_loss
                    ),
                    portfolio,
                )
            if not _rationals_equal(
                self.single_loss_fraction, expected_single
            ) or not _rationals_equal(
                self.repeated_loss_fraction, expected_repeated
            ):
                raise ValueError("actual loss fractions are inconsistent")
            if type(self.status) is not AffordabilityStatus:
                raise TypeError(
                    "status must have exact type AffordabilityStatus"
                )
            if type(self.reason_codes) is not tuple:
                raise TypeError("reason_codes must have exact type tuple")
            if any(
                type(item) is not AffordabilityReasonCode
                for item in self.reason_codes
            ):
                raise TypeError(
                    "reason_codes items must have exact type "
                    "AffordabilityReasonCode"
                )
            if len(set(self.reason_codes)) != len(self.reason_codes):
                raise ValueError("reason_codes must be unique")
            canonical = tuple(
                reason
                for reason in AffordabilityReasonCode
                if reason in set(self.reason_codes)
            )
            if self.reason_codes != canonical:
                raise ValueError("reason_codes must be in declaration order")
            expected_status, expected_reasons = _expected_outcome(
                assumptions, expected_single, expected_repeated
            )
            if (
                self.status is not expected_status
                or self.reason_codes != expected_reasons
            ):
                raise ValueError("status and reason_codes are inconsistent")


def _rational_mapping(value: Optional[ExactRational]) -> object:
    if value is None:
        return None
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
    }


def _dependency_disclosure(lineage: CalculationLineage) -> dict:
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


def _parameters(
    record: StructureAffordabilityEvidence,
    dependency_lineage: CalculationLineage,
) -> dict:
    assumptions = record.assumptions
    portfolio = assumptions.portfolio_value
    return {
        "schema_version": "v0.1",
        "output_architecture": (
            "standalone_structure_affordability_evidence"
        ),
        "currency": "USD",
        "risk_scope": {
            "single_position": "one_already_specified_structure",
            "repeated_attempts": (
                "equal_repeated_attempts_not_concurrency_or_annual_frequency"
            ),
            "annual_budget": "excluded",
            "existing_committed_exposure": "excluded",
            "inverse_sizing": "excluded",
        },
        "structure_costs_dependency": _dependency_disclosure(
            dependency_lineage
        ),
        "risk_budget_assumptions": {
            "portfolio_value": (
                None
                if portfolio is None
                else {
                    "amount": portfolio.amount,
                    "as_of_date": portfolio.as_of_date,
                    "methodology": portfolio.methodology,
                    "currency": "USD",
                }
            ),
            "maximum_single_structure_loss_fraction": _rational_mapping(
                assumptions.maximum_single_structure_loss_fraction
            ),
            "maximum_repeated_loss_fraction": _rational_mapping(
                assumptions.maximum_repeated_loss_fraction
            ),
            "risk_budget_methodology": assumptions.risk_budget_methodology,
            "legacy_portfolio_value_correspondence": (
                "exact_equality_to_Decimal(str(assumed_portfolio_value))"
            ),
            "missing_assumption_policy": (
                "data_insufficient_without_boundary_breach_evaluation"
            ),
        },
        "calculation_values": {
            "single_position_maximum_loss": (
                record.single_position_maximum_loss
            ),
            "repeated_bet_count": record.repeated_bet_count,
            "repeated_aggregate_maximum_loss": (
                record.repeated_aggregate_maximum_loss
            ),
            "portfolio_value": (
                None if portfolio is None else portfolio.amount
            ),
            "single_loss_fraction": _rational_mapping(
                record.single_loss_fraction
            ),
            "repeated_loss_fraction": _rational_mapping(
                record.repeated_loss_fraction
            ),
            "maximum_single_structure_loss_fraction": _rational_mapping(
                assumptions.maximum_single_structure_loss_fraction
            ),
            "maximum_repeated_loss_fraction": _rational_mapping(
                assumptions.maximum_repeated_loss_fraction
            ),
        },
        "affordability_rule": {
            "required_assumptions": (
                "portfolio_value",
                "maximum_single_structure_loss_fraction",
                "maximum_repeated_loss_fraction",
                "risk_budget_methodology",
            ),
            "single_comparison": (
                "single_loss_fraction"
                "<=maximum_single_structure_loss_fraction"
            ),
            "repeated_comparison": (
                "repeated_loss_fraction<=maximum_repeated_loss_fraction"
            ),
            "complete_rule": "both_comparisons_must_pass",
            "equality_boundary": "affordable",
            "incomplete_precedence": (
                "missing_assumptions_precede_boundary_breach_evaluation"
            ),
        },
        "outcome": {
            "status": record.status.value,
            "reason_codes": tuple(
                reason.value for reason in record.reason_codes
            ),
        },
        "limitations": (
            "Affordability evidence for one declared structure and equal "
            "repeated attempts only; no annual budget, committed exposure, "
            "inverse sizing, quantity recommendation, portfolio optimization, "
            "probability, expected return, screening, reporting, provider "
            "access, monitoring, or execution."
        ),
    }


def _decode_parameters(parameters_json: object) -> dict:
    if type(parameters_json) is not str:
        raise TypeError("parameters_json must have exact type str")

    def reject_float(_value: str) -> object:
        raise ValueError("affordability parameters prohibit JSON floats")

    def unique_object(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(
                    "affordability parameters contain duplicate JSON keys"
                )
            result[key] = value
        return result

    try:
        raw = json.loads(
            parameters_json,
            parse_float=reject_float,
            parse_constant=reject_float,
            object_pairs_hook=unique_object,
        )
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise ValueError("affordability parameters_json is invalid") from error

    def decode(value: object) -> object:
        if value is None or type(value) in (bool, int, str):
            return value
        if type(value) is list:
            return tuple(decode(item) for item in value)
        if type(value) is not dict or len(value) != 1:
            raise ValueError("affordability parameters use invalid JSON")
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
            if (
                result.isoformat(timespec="microseconds")
                .replace("+00:00", "Z") != payload
            ):
                raise ValueError("$datetime payload is noncanonical")
            return result
        raise ValueError("affordability parameters contain an unknown tag")

    decoded = decode(raw)
    if type(decoded) is not dict or set(decoded) != _PARAMETER_KEYS:
        raise ValueError(
            "affordability parameters have wrong exact ten-key schema"
        )
    try:
        if canonicalize_lineage_parameters(decoded) != parameters_json:
            raise ValueError("affordability parameters are not byte-canonical")
    except (TypeError, ValueError) as error:
        raise ValueError("affordability parameters are not canonical") from error
    _validate_parameter_shapes(decoded)
    return decoded


def _exact_dict(value: object, keys: set, label: str) -> dict:
    if type(value) is not dict:
        raise TypeError(f"{label} must have exact type dict")
    if set(value) != keys:
        raise ValueError(f"{label} has the wrong exact key schema")
    return value


def _validate_rational_mapping(value: object, label: str) -> None:
    mapping = _exact_dict(value, _RATIONAL_KEYS, label)
    if (
        type(mapping["numerator"]) is not int
        or type(mapping["denominator"]) is not int
    ):
        raise TypeError(f"{label} fields must have exact type int")
    rebuilt = ExactRational(mapping["numerator"], mapping["denominator"])
    if _rational_mapping(rebuilt) != mapping:
        raise ValueError(f"{label} must be a canonical reduced rational")


def _validate_optional_rational(value: object, label: str) -> None:
    if value is not None:
        _validate_rational_mapping(value, label)


def _validate_parameter_shapes(decoded: dict) -> None:
    _exact_dict(decoded["risk_scope"], _RISK_SCOPE_KEYS, "risk_scope")
    dependency = _exact_dict(
        decoded["structure_costs_dependency"],
        _DEPENDENCY_KEYS,
        "structure_costs_dependency",
    )
    if type(dependency["quality_flags"]) is not tuple:
        raise TypeError("dependency quality_flags must have exact type tuple")
    assumptions = _exact_dict(
        decoded["risk_budget_assumptions"],
        _ASSUMPTION_KEYS,
        "risk_budget_assumptions",
    )
    if assumptions["portfolio_value"] is not None:
        _exact_dict(
            assumptions["portfolio_value"],
            _PORTFOLIO_KEYS,
            "portfolio_value",
        )
    _validate_optional_rational(
        assumptions["maximum_single_structure_loss_fraction"],
        "maximum_single_structure_loss_fraction",
    )
    _validate_optional_rational(
        assumptions["maximum_repeated_loss_fraction"],
        "maximum_repeated_loss_fraction",
    )
    values = _exact_dict(
        decoded["calculation_values"],
        _CALCULATION_VALUE_KEYS,
        "calculation_values",
    )
    if type(values["repeated_bet_count"]) is not int:
        raise TypeError("repeated_bet_count must have exact type int")
    for key in (
        "single_position_maximum_loss",
        "repeated_aggregate_maximum_loss",
    ):
        if type(values[key]) is not decimal.Decimal:
            raise TypeError(f"{key} must have exact type Decimal")
    for key in (
        "single_loss_fraction",
        "repeated_loss_fraction",
        "maximum_single_structure_loss_fraction",
        "maximum_repeated_loss_fraction",
    ):
        _validate_optional_rational(values[key], key)
    _exact_dict(
        decoded["affordability_rule"], _RULE_KEYS, "affordability_rule"
    )
    outcome = _exact_dict(decoded["outcome"], _OUTCOME_KEYS, "outcome")
    if type(outcome["reason_codes"]) is not tuple:
        raise TypeError("outcome reason_codes must have exact type tuple")


def _exact_tree_matches(actual: object, expected: object, path: str) -> None:
    if type(actual) is not type(expected):
        raise TypeError(f"{path} has the wrong exact type")
    if type(expected) is dict:
        if set(actual) != set(expected):
            raise ValueError(f"{path} has the wrong exact key schema")
        for key in expected:
            _exact_tree_matches(actual[key], expected[key], f"{path}.{key}")
        return
    if type(expected) is tuple:
        if len(actual) != len(expected):
            raise ValueError(f"{path} has the wrong cardinality")
        for index, (left, right) in enumerate(zip(actual, expected)):
            _exact_tree_matches(left, right, f"{path}[{index}]")
        return
    if actual != expected:
        raise ValueError(f"{path} has the wrong frozen value")


def _dependency_from_disclosure(
    record: StructureAffordabilityEvidence,
    lineage: CalculationLineage,
    disclosure: object,
) -> StructureCostsTransformationResult:
    item = _exact_dict(
        disclosure, _DEPENDENCY_KEYS, "structure_costs_dependency"
    )
    if (
        item["calculation_type"] != "structure_costs"
        or item["methodology_id"] != "exact-structure-costs"
        or item["methodology_version"] != "v0.2"
        or item["input_rule"]
        != "exact_reuse_of_structure_costs_lineage_inputs"
    ):
        raise ValueError("structure_costs_dependency identity is invalid")
    if type(item["quality_flags"]) is not tuple or any(
        type(value) is not str for value in item["quality_flags"]
    ):
        raise TypeError("dependency quality flags must be exact strings")
    try:
        flags = tuple(
            CalculationQualityFlag(value)
            for value in item["quality_flags"]
        )
    except ValueError as error:
        raise ValueError("dependency quality flag value is invalid") from error
    if len(set(flags)) != len(flags) or flags != tuple(
        flag for flag in CalculationQualityFlag if flag in set(flags)
    ):
        raise ValueError("dependency quality flags are not canonical")
    dependency_inputs = _strict_inputs(lineage.inputs)
    dependency_lineage = CalculationLineage(
        calculation_id=item["calculation_id"],
        calculation_type=item["calculation_type"],
        methodology_id=item["methodology_id"],
        methodology_version=item["methodology_version"],
        calculated_at=item["calculated_at"],
        inputs=dependency_inputs,
        parameters_json=item["parameters_json"],
        quality_flags=flags,
    )
    dependency_inputs = _strict_inputs(
        dependency_lineage.inputs, dependency_lineage.calculated_at
    )
    if not _input_tuples_match(
        dependency_inputs, dependency_lineage.inputs
    ):
        raise ValueError(
            "dependency inputs changed during intrinsic reconstruction"
        )
    decoded = _transformations._decode_cost_parameters(
        dependency_lineage.parameters_json
    )
    stable = decoded["calculation_values"]["stable_record_values"]
    methodology = decoded["greeks_methodology"]
    cost_record = StructureCosts(
        structure=record.structure,
        as_of_date=record.as_of_date,
        quoted_mid_premium=_transformations._cost_stable_float_repr(
            stable["quoted_mid_premium_repr"], "quoted_mid_premium_repr"
        ),
        estimated_spread_cost=_transformations._cost_stable_float_repr(
            stable["estimated_spread_cost_repr"],
            "estimated_spread_cost_repr",
        ),
        commissions_and_fees=_transformations._cost_stable_float_repr(
            stable["commissions_and_fees_repr"],
            "commissions_and_fees_repr",
        ),
        theta_per_day=_transformations._cost_stable_float_repr(
            stable["theta_per_day_repr"], "theta_per_day_repr"
        ),
        gamma=_transformations._cost_stable_float_repr(
            stable["gamma_repr"], "gamma_repr"
        ),
        underlying_price=_transformations._cost_stable_float_repr(
            stable["underlying_price_repr"], "underlying_price_repr"
        ),
        greeks_methodology=_transformations._greeks_methodology_disclosure((
            methodology["model_name"],
            methodology["model_version"],
            methodology["rate_input_description"],
            methodology["dividend_input_description"],
            methodology["theta_day_basis"],
            methodology["unit_convention"],
        )),
        repeated_bet_count=decoded["repeated_bet_count"],
    )
    return StructureCostsTransformationResult(cost_record, dependency_lineage)


def _validate_result(
    record: StructureAffordabilityEvidence,
    lineage: CalculationLineage,
) -> None:
    if (
        lineage.calculation_type != "structure_affordability"
        or lineage.methodology_id
        != "exact-bounded-loss-against-declared-risk-fractions"
        or lineage.methodology_version != "v0.1"
    ):
        raise ValueError("affordability lineage identity is invalid")
    decoded = _decode_parameters(lineage.parameters_json)
    dependency = _dependency_from_disclosure(
        record, lineage, decoded["structure_costs_dependency"]
    )
    cost_values = _transformations._decode_cost_parameters(
        dependency.lineage.parameters_json
    )["calculation_values"]
    if (
        record.single_position_maximum_loss
        != cost_values["maximum_loss_exact"]
        or record.repeated_bet_count
        != dependency.record.repeated_bet_count
        or record.repeated_aggregate_maximum_loss
        != cost_values["cumulative_repeated_bet_cost_exact"]
    ):
        raise ValueError(
            "public exact values differ from StructureCosts dependency"
        )
    if not _input_tuples_match(
        lineage.inputs, dependency.lineage.inputs
    ):
        raise ValueError("lineage inputs must exactly reuse dependency inputs")
    if lineage.calculation_id == dependency.lineage.calculation_id:
        raise ValueError("calculation ID must differ from dependency")
    if lineage.calculated_at < dependency.lineage.calculated_at:
        raise ValueError("calculation precedes StructureCosts dependency")
    if set(dependency.lineage.quality_flags) & _PROHIBITED_DEPENDENCY_FLAGS:
        raise ValueError("StructureCosts dependency flags are prohibited")
    selected = {CalculationQualityFlag.ASSUMPTION_APPLIED}
    if record.status is AffordabilityStatus.DATA_INSUFFICIENT:
        selected.add(CalculationQualityFlag.INCOMPLETE_INPUT_USED)
    selected.update(
        set(dependency.lineage.quality_flags) & _PROPAGATED_FLAGS
    )
    expected_flags = tuple(
        flag for flag in CalculationQualityFlag if flag in selected
    )
    if (
        lineage.quality_flags != expected_flags
        or set(lineage.quality_flags) & _PROHIBITED_RESULT_FLAGS
    ):
        raise ValueError("affordability quality flags are invalid")
    expected = _parameters(record, dependency.lineage)
    _exact_tree_matches(decoded, expected, "parameters")
    if lineage.parameters_json != canonicalize_lineage_parameters(expected):
        raise ValueError(
            "affordability parameters are not independently reconstructed "
            "canonical bytes"
        )


@dataclass(frozen=True)
class StructureAffordabilityAssessmentResult:
    record: StructureAffordabilityEvidence
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        if type(self.record) is not StructureAffordabilityEvidence:
            raise TypeError(
                "record must have exact type StructureAffordabilityEvidence"
            )
        if type(self.lineage) is not CalculationLineage:
            raise TypeError("lineage must have exact type CalculationLineage")
        with decimal.localcontext():
            verified_inputs = _strict_inputs(self.lineage.inputs)
            verified_lineage = CalculationLineage(
                calculation_id=self.lineage.calculation_id,
                calculation_type=self.lineage.calculation_type,
                methodology_id=self.lineage.methodology_id,
                methodology_version=self.lineage.methodology_version,
                calculated_at=self.lineage.calculated_at,
                inputs=verified_inputs,
                parameters_json=self.lineage.parameters_json,
                quality_flags=self.lineage.quality_flags,
            )
            if (
                type(self.lineage.calculation_id) is not str
                or self.lineage.calculation_id
                != verified_lineage.calculation_id
                or type(self.lineage.calculation_type) is not str
                or self.lineage.calculation_type
                != verified_lineage.calculation_type
                or type(self.lineage.methodology_id) is not str
                or self.lineage.methodology_id
                != verified_lineage.methodology_id
                or type(self.lineage.methodology_version) is not str
                or self.lineage.methodology_version
                != verified_lineage.methodology_version
                or type(self.lineage.calculated_at) is not datetime.datetime
                or self.lineage.calculated_at
                != verified_lineage.calculated_at
                or not _input_tuples_match(
                    self.lineage.inputs, verified_lineage.inputs
                )
                or type(self.lineage.parameters_json) is not str
                or self.lineage.parameters_json
                != verified_lineage.parameters_json
                or type(self.lineage.quality_flags) is not tuple
                or self.lineage.quality_flags
                != verified_lineage.quality_flags
            ):
                raise ValueError(
                    "lineage is not in canonical constructor state"
                )
            verified_record = StructureAffordabilityEvidence(
                structure=self.record.structure,
                as_of_date=self.record.as_of_date,
                assumptions=self.record.assumptions,
                single_position_maximum_loss=(
                    self.record.single_position_maximum_loss
                ),
                repeated_bet_count=self.record.repeated_bet_count,
                repeated_aggregate_maximum_loss=(
                    self.record.repeated_aggregate_maximum_loss
                ),
                single_loss_fraction=self.record.single_loss_fraction,
                repeated_loss_fraction=self.record.repeated_loss_fraction,
                status=self.record.status,
                reason_codes=self.record.reason_codes,
            )
            _validate_result(verified_record, verified_lineage)


def _normalize_calculated_at(value: object) -> datetime.datetime:
    if type(value) is not datetime.datetime:
        raise TypeError("calculated_at must have exact type datetime")
    try:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("calculated_at must be timezone-aware")
        return value.astimezone(datetime.timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError("calculated_at must be representable in UTC") from error


def assess_structure_affordability(
    calculation_id,
    structure_costs_result,
    risk_budget_assumptions,
    calculated_at,
):
    """Assess exact bounded losses against caller-declared risk fractions."""

    if type(calculation_id) is not str:
        raise TypeError("calculation_id must have exact type str")
    if type(structure_costs_result) is not StructureCostsTransformationResult:
        raise TypeError(
            "structure_costs_result must have exact type "
            "StructureCostsTransformationResult"
        )
    if type(risk_budget_assumptions) is not RiskBudgetAssumptions:
        raise TypeError(
            "risk_budget_assumptions must have exact type "
            "RiskBudgetAssumptions"
        )
    if type(calculated_at) is not datetime.datetime:
        raise TypeError("calculated_at must have exact type datetime")
    normalized_id = _required_string("calculation_id", calculation_id)
    normalized_at = _normalize_calculated_at(calculated_at)

    with decimal.localcontext():
        supplied_dependency_lineage = structure_costs_result.lineage
        if type(supplied_dependency_lineage) is not CalculationLineage:
            raise TypeError(
                "StructureCosts lineage must have exact type "
                "CalculationLineage"
            )
        dependency_inputs = _strict_inputs(
            supplied_dependency_lineage.inputs
        )
        reconstructed_dependency_lineage = CalculationLineage(
            calculation_id=supplied_dependency_lineage.calculation_id,
            calculation_type=supplied_dependency_lineage.calculation_type,
            methodology_id=supplied_dependency_lineage.methodology_id,
            methodology_version=supplied_dependency_lineage.methodology_version,
            calculated_at=supplied_dependency_lineage.calculated_at,
            inputs=dependency_inputs,
            parameters_json=supplied_dependency_lineage.parameters_json,
            quality_flags=supplied_dependency_lineage.quality_flags,
        )
        if not _input_tuples_match(
            supplied_dependency_lineage.inputs,
            reconstructed_dependency_lineage.inputs,
        ):
            raise ValueError(
                "StructureCosts inputs changed during reconstruction"
            )
        dependency = StructureCostsTransformationResult(
            structure_costs_result.record,
            reconstructed_dependency_lineage,
        )
        dependency_inputs = _strict_inputs(
            dependency.lineage.inputs, dependency.lineage.calculated_at
        )
        dependency_lineage = CalculationLineage(
            calculation_id=dependency.lineage.calculation_id,
            calculation_type=dependency.lineage.calculation_type,
            methodology_id=dependency.lineage.methodology_id,
            methodology_version=dependency.lineage.methodology_version,
            calculated_at=dependency.lineage.calculated_at,
            inputs=dependency_inputs,
            parameters_json=dependency.lineage.parameters_json,
            quality_flags=dependency.lineage.quality_flags,
        )
        dependency = StructureCostsTransformationResult(
            dependency.record, dependency_lineage
        )
        decoded_cost = _transformations._decode_cost_parameters(
            dependency.lineage.parameters_json
        )
        if set(dependency.lineage.quality_flags) & _PROHIBITED_DEPENDENCY_FLAGS:
            raise ValueError("StructureCosts dependency flags are prohibited")
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

        assumptions = _strict_assumptions(risk_budget_assumptions)
        structure = _strict_structure(dependency.record.structure)
        portfolio = assumptions.portfolio_value
        if portfolio is not None:
            if portfolio.as_of_date != dependency.record.as_of_date:
                raise ValueError(
                    "portfolio-value date must equal StructureCosts as_of_date"
                )
            try:
                legacy = decimal.Decimal(
                    str(structure.assumed_portfolio_value)
                )
            except decimal.InvalidOperation as error:
                raise ValueError(
                    "legacy portfolio value cannot be represented exactly"
                ) from error
            if portfolio.amount != legacy:
                raise ValueError(
                    "portfolio value contradicts legacy structure metadata"
                )

        values = decoded_cost["calculation_values"]
        single_loss = values["maximum_loss_exact"]
        repeated_count = dependency.record.repeated_bet_count
        repeated_loss = _multiply_decimal_int_exact(
            single_loss, repeated_count
        )
        if repeated_loss != values["cumulative_repeated_bet_cost_exact"]:
            raise ValueError(
                "StructureCosts repeated aggregate disclosure is inconsistent"
            )
        if portfolio is None:
            single_fraction = None
            repeated_fraction = None
        else:
            denominator = _decimal_to_rational(portfolio.amount)
            single_fraction = _rational_divide(
                _decimal_to_rational(single_loss), denominator
            )
            repeated_fraction = _rational_divide(
                _decimal_to_rational(repeated_loss), denominator
            )
        status, reasons = _expected_outcome(
            assumptions, single_fraction, repeated_fraction
        )
        record = StructureAffordabilityEvidence(
            structure=structure,
            as_of_date=dependency.record.as_of_date,
            assumptions=assumptions,
            single_position_maximum_loss=single_loss,
            repeated_bet_count=repeated_count,
            repeated_aggregate_maximum_loss=repeated_loss,
            single_loss_fraction=single_fraction,
            repeated_loss_fraction=repeated_fraction,
            status=status,
            reason_codes=reasons,
        )
        selected = {CalculationQualityFlag.ASSUMPTION_APPLIED}
        if status is AffordabilityStatus.DATA_INSUFFICIENT:
            selected.add(CalculationQualityFlag.INCOMPLETE_INPUT_USED)
        selected.update(
            set(dependency.lineage.quality_flags) & _PROPAGATED_FLAGS
        )
        flags = tuple(
            flag for flag in CalculationQualityFlag if flag in selected
        )
        parameters_json = canonicalize_lineage_parameters(
            _parameters(record, dependency.lineage)
        )
        lineage = CalculationLineage(
            calculation_id=normalized_id,
            calculation_type="structure_affordability",
            methodology_id=(
                "exact-bounded-loss-against-declared-risk-fractions"
            ),
            methodology_version="v0.1",
            calculated_at=normalized_at,
            inputs=dependency.lineage.inputs,
            parameters_json=parameters_json,
            quality_flags=flags,
        )
        return StructureAffordabilityAssessmentResult(record, lineage)
