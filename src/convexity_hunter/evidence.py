"""Domain objects for option-structure research evidence."""

import datetime
import math
from dataclasses import dataclass
from enum import Enum
from numbers import Real
from typing import Optional, Tuple


def _validate_real(name: str, value: object) -> None:
    """Require a finite real number that is not a Boolean."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _validate_int(name: str, value: object) -> None:
    """Require an integer that is not a Boolean."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")


def _validate_date_only(name: str, value: object) -> None:
    """Require a calendar date without a time component."""

    if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
        raise TypeError(f"{name} must be a date without a time component")


def _validate_positive_real(name: str, value: object) -> None:
    """Require a finite real number greater than zero."""

    _validate_real(name, value)
    if value <= 0:  # type: ignore[operator]
        raise ValueError(f"{name} must be greater than 0")


def _validate_nonnegative_real(name: str, value: object) -> None:
    """Require a finite real number greater than or equal to zero."""

    _validate_real(name, value)
    if value < 0:  # type: ignore[operator]
        raise ValueError(f"{name} must be 0 or greater")


def _validate_percentile(name: str, value: object) -> None:
    """Require a finite decimal value in the inclusive unit interval."""

    _validate_real(name, value)
    if value < 0 or value > 1:  # type: ignore[operator]
        raise ValueError(f"{name} must be between 0.0 and 1.0 inclusive")


def _normalize_required_string(name: str, value: object) -> str:
    """Require and strip a non-empty string."""

    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _normalize_optional_string(name: str, value: object) -> Optional[str]:
    """Validate and strip an optional non-empty string."""

    if value is None:
        return None
    return _normalize_required_string(name, value)


class CandidateState(str, Enum):
    """Investigation state assigned to a candidate structure."""

    REJECT = "reject"
    WATCH = "watch"
    INVESTIGATE = "investigate"
    DATA_INSUFFICIENT = "data_insufficient"


class EvidenceKind(str, Enum):
    """Classification describing how an evidence item was produced."""

    OBSERVED_FACT = "observed_fact"
    CALCULATED_METRIC = "calculated_metric"
    ASSUMPTION = "assumption"
    AI_INTERPRETATION = "ai_interpretation"


class EvidenceImpact(str, Enum):
    """Declared effect of evidence on a research hypothesis."""

    SUPPORTS = "supports"
    WEAKENS = "weakens"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class OptionLeg:
    """One declared long-option leg."""

    underlying: str
    option_type: str
    strike: float
    expiration: datetime.date
    quantity: int = 1
    contract_multiplier: int = 100

    def __post_init__(self) -> None:
        if not isinstance(self.underlying, str) or not self.underlying.strip():
            raise ValueError("underlying must be a non-empty string")
        normalized_underlying = self.underlying.strip().upper()

        if not isinstance(self.option_type, str):
            raise TypeError("option_type must be a string")
        normalized_option_type = self.option_type.strip().lower()
        if normalized_option_type not in {"call", "put"}:
            raise ValueError("option_type must be 'call' or 'put'")

        _validate_real("strike", self.strike)
        if self.strike <= 0:
            raise ValueError("strike must be greater than 0")
        if isinstance(self.expiration, datetime.datetime) or not isinstance(
            self.expiration, datetime.date
        ):
            raise TypeError("expiration must be a date without a time component")
        _validate_int("quantity", self.quantity)
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than 0")
        _validate_int("contract_multiplier", self.contract_multiplier)
        if self.contract_multiplier <= 0:
            raise ValueError("contract_multiplier must be greater than 0")

        object.__setattr__(self, "underlying", normalized_underlying)
        object.__setattr__(self, "option_type", normalized_option_type)


@dataclass(frozen=True)
class OptionStructure:
    """One supported long-option strategy position."""

    legs: Tuple[OptionLeg, ...]
    assumed_portfolio_value: float
    expected_holding_days: int

    def __post_init__(self) -> None:
        if not isinstance(self.legs, (tuple, list)):
            raise TypeError("legs must be a tuple or list of OptionLeg objects")
        normalized_legs = tuple(self.legs)
        object.__setattr__(self, "legs", normalized_legs)

        if len(normalized_legs) not in {1, 2}:
            raise ValueError("legs must contain one or two OptionLeg objects")
        if not all(isinstance(leg, OptionLeg) for leg in normalized_legs):
            raise ValueError("every leg must be an OptionLeg")
        _validate_real("assumed_portfolio_value", self.assumed_portfolio_value)
        if self.assumed_portfolio_value <= 0:
            raise ValueError("assumed_portfolio_value must be greater than 0")
        _validate_int("expected_holding_days", self.expected_holding_days)
        if self.expected_holding_days < 0:
            raise ValueError("expected_holding_days must be 0 or greater")

        # TODO: Validate the holding period against the earliest expiration once
        # OptionStructure receives an explicit valuation/reference date.

        if len(self.legs) == 2:
            call_legs = [leg for leg in self.legs if leg.option_type == "call"]
            put_legs = [leg for leg in self.legs if leg.option_type == "put"]
            if len(call_legs) != 1 or len(put_legs) != 1:
                raise ValueError("a two-leg structure must contain one call and one put")

            call = call_legs[0]
            put = put_legs[0]
            matching_fields = (
                call.underlying == put.underlying,
                call.strike == put.strike,
                call.expiration == put.expiration,
                call.quantity == put.quantity,
                call.contract_multiplier == put.contract_multiplier,
            )
            if not all(matching_fields):
                raise ValueError("two-leg structures must satisfy long-straddle rules")

    @property
    def structure_type(self) -> str:
        """Return the supported strategy name for this structure."""

        if len(self.legs) == 2:
            return "long_straddle"
        return "long_call" if self.legs[0].option_type == "call" else "long_put"

    @property
    def underlying(self) -> str:
        """Return the structure's shared underlying symbol."""

        return self.legs[0].underlying


@dataclass(frozen=True)
class Scenario:
    """Declared relative market shocks at a specified valuation time."""

    underlying_move: float
    iv_change: float
    valuation_time: str
    days_forward: int = 0

    def __post_init__(self) -> None:
        _validate_real("underlying_move", self.underlying_move)
        if self.underlying_move <= -1.0:
            raise ValueError("underlying_move must be greater than -1.0")
        _validate_real("iv_change", self.iv_change)
        if self.iv_change <= -1.0:
            raise ValueError("iv_change must be greater than -1.0")
        if not isinstance(self.valuation_time, str):
            raise TypeError("valuation_time must be a string")

        normalized_valuation_time = self.valuation_time.strip().lower()
        allowed_times = {
            "immediate",
            "days_forward",
            "holding_horizon",
            "expiration",
        }
        if normalized_valuation_time not in allowed_times:
            raise ValueError("valuation_time is not supported")
        _validate_int("days_forward", self.days_forward)
        if self.days_forward < 0:
            raise ValueError("days_forward must be 0 or greater")
        if normalized_valuation_time == "immediate" and self.days_forward != 0:
            raise ValueError("immediate scenarios require days_forward to equal 0")
        if normalized_valuation_time == "days_forward" and self.days_forward <= 0:
            raise ValueError("days_forward scenarios require days_forward greater than 0")
        if normalized_valuation_time in {"holding_horizon", "expiration"} and self.days_forward != 0:
            raise ValueError(
                "holding_horizon and expiration scenarios require days_forward to equal 0"
            )

        object.__setattr__(self, "valuation_time", normalized_valuation_time)


@dataclass(frozen=True)
class ClassifiedEvidence:
    """One evidence statement with explicit classification and provenance."""

    evidence_id: str
    kind: EvidenceKind
    impact: EvidenceImpact
    statement: str
    source: Optional[str] = None
    methodology: Optional[str] = None

    def __post_init__(self) -> None:
        evidence_id = _normalize_required_string("evidence_id", self.evidence_id)
        statement = _normalize_required_string("statement", self.statement)
        if not isinstance(self.kind, EvidenceKind):
            raise TypeError("kind must be an EvidenceKind")
        if not isinstance(self.impact, EvidenceImpact):
            raise TypeError("impact must be an EvidenceImpact")
        source = _normalize_optional_string("source", self.source)
        methodology = _normalize_optional_string("methodology", self.methodology)

        if self.kind is EvidenceKind.OBSERVED_FACT and source is None:
            raise ValueError("observed facts require a source")
        if self.kind is EvidenceKind.CALCULATED_METRIC:
            if source is None:
                raise ValueError("calculated metrics require a source")
            if methodology is None:
                raise ValueError("calculated metrics require a methodology")

        object.__setattr__(self, "evidence_id", evidence_id)
        object.__setattr__(self, "statement", statement)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "methodology", methodology)


@dataclass(frozen=True)
class TermVolatilityPoint:
    """Annualized ATM implied volatility at one tenor."""

    tenor_days: int
    atm_iv: float

    def __post_init__(self) -> None:
        _validate_int("tenor_days", self.tenor_days)
        if self.tenor_days <= 0:
            raise ValueError("tenor_days must be greater than 0")
        _validate_positive_real("atm_iv", self.atm_iv)


@dataclass(frozen=True)
class VolatilityEnvironment:
    """Matched-horizon volatility evidence for one underlying and date."""

    underlying: str
    as_of_date: datetime.date
    reference_tenor_days: int
    iv_percentile: float
    iv_history_lookback_observations: int
    historical_median_atm_iv: float
    matched_realized_volatility: float
    matched_realized_window_days: int
    term_structure: Tuple[TermVolatilityPoint, ...]

    def __post_init__(self) -> None:
        underlying = _normalize_required_string("underlying", self.underlying).upper()
        _validate_date_only("as_of_date", self.as_of_date)
        _validate_int("reference_tenor_days", self.reference_tenor_days)
        if self.reference_tenor_days <= 0:
            raise ValueError("reference_tenor_days must be greater than 0")
        _validate_percentile("iv_percentile", self.iv_percentile)
        _validate_int(
            "iv_history_lookback_observations",
            self.iv_history_lookback_observations,
        )
        if self.iv_history_lookback_observations <= 0:
            raise ValueError(
                "iv_history_lookback_observations must be greater than 0"
            )
        _validate_positive_real(
            "historical_median_atm_iv", self.historical_median_atm_iv
        )
        _validate_nonnegative_real(
            "matched_realized_volatility", self.matched_realized_volatility
        )
        _validate_int(
            "matched_realized_window_days", self.matched_realized_window_days
        )
        if self.matched_realized_window_days <= 0:
            raise ValueError("matched_realized_window_days must be greater than 0")
        if self.matched_realized_window_days != self.reference_tenor_days:
            raise ValueError(
                "matched_realized_window_days must equal reference_tenor_days"
            )

        if not isinstance(self.term_structure, (tuple, list)):
            raise TypeError("term_structure must be a tuple or list")
        points = tuple(self.term_structure)
        if len(points) < 2:
            raise ValueError("term_structure must contain at least two points")
        if not all(isinstance(point, TermVolatilityPoint) for point in points):
            raise TypeError("every term_structure item must be a TermVolatilityPoint")
        tenors = [point.tenor_days for point in points]
        if len(set(tenors)) != len(tenors):
            raise ValueError("term_structure tenor_days values must be unique")
        if tenors.count(self.reference_tenor_days) != 1:
            raise ValueError("term_structure must contain the reference tenor exactly once")

        object.__setattr__(self, "underlying", underlying)
        object.__setattr__(
            self, "term_structure", tuple(sorted(points, key=lambda point: point.tenor_days))
        )

    @property
    def atm_iv(self) -> float:
        """Return ATM IV at the reference tenor."""

        return next(
            point.atm_iv
            for point in self.term_structure
            if point.tenor_days == self.reference_tenor_days
        )

    @property
    def iv_vs_historical_median(self) -> float:
        """Return reference ATM IV minus its historical median."""

        return self.atm_iv - self.historical_median_atm_iv

    @property
    def implied_realized_gap(self) -> float:
        """Return reference ATM IV minus matched realized volatility."""

        return self.atm_iv - self.matched_realized_volatility


@dataclass(frozen=True)
class TailPricingSlice:
    """Relative tail pricing for one underlying and expiration."""

    underlying: str
    as_of_date: datetime.date
    expiration: datetime.date
    atm_iv: float
    put_25_delta_iv: float
    call_25_delta_iv: float
    put_10_delta_iv: float
    call_10_delta_iv: float
    skew_percentile: float
    skew_history_lookback_observations: int
    delta_methodology: str

    def __post_init__(self) -> None:
        underlying = _normalize_required_string("underlying", self.underlying).upper()
        _validate_date_only("as_of_date", self.as_of_date)
        _validate_date_only("expiration", self.expiration)
        if self.expiration <= self.as_of_date:
            raise ValueError("expiration must be later than as_of_date")
        for name in (
            "atm_iv",
            "put_25_delta_iv",
            "call_25_delta_iv",
            "put_10_delta_iv",
            "call_10_delta_iv",
        ):
            _validate_positive_real(name, getattr(self, name))
        _validate_percentile("skew_percentile", self.skew_percentile)
        _validate_int(
            "skew_history_lookback_observations",
            self.skew_history_lookback_observations,
        )
        if self.skew_history_lookback_observations <= 0:
            raise ValueError(
                "skew_history_lookback_observations must be greater than 0"
            )
        delta_methodology = _normalize_required_string(
            "delta_methodology", self.delta_methodology
        )
        object.__setattr__(self, "underlying", underlying)
        object.__setattr__(self, "delta_methodology", delta_methodology)

    @property
    def downside_25_delta_skew(self) -> float:
        """Return 25-delta put IV minus ATM IV."""

        return self.put_25_delta_iv - self.atm_iv

    @property
    def upside_25_delta_skew(self) -> float:
        """Return 25-delta call IV minus ATM IV."""

        return self.call_25_delta_iv - self.atm_iv

    @property
    def downside_wing_curvature(self) -> float:
        """Return 10-delta put IV minus 25-delta put IV."""

        return self.put_10_delta_iv - self.put_25_delta_iv

    @property
    def upside_wing_curvature(self) -> float:
        """Return 10-delta call IV minus 25-delta call IV."""

        return self.call_10_delta_iv - self.call_25_delta_iv

    @property
    def days_to_expiration(self) -> int:
        """Return calendar days from the observation to expiration."""

        return (self.expiration - self.as_of_date).days


@dataclass(frozen=True)
class StructureCosts:
    """Total-position costs and exposures for a declared option structure."""

    structure: OptionStructure
    as_of_date: datetime.date
    quoted_mid_premium: float
    estimated_spread_cost: float
    commissions_and_fees: float
    theta_per_day: float
    gamma: float
    underlying_price: float
    greeks_methodology: str
    repeated_bet_count: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.structure, OptionStructure):
            raise TypeError("structure must be an OptionStructure")
        _validate_date_only("as_of_date", self.as_of_date)
        _validate_positive_real("quoted_mid_premium", self.quoted_mid_premium)
        _validate_nonnegative_real(
            "estimated_spread_cost", self.estimated_spread_cost
        )
        _validate_nonnegative_real("commissions_and_fees", self.commissions_and_fees)
        _validate_real("theta_per_day", self.theta_per_day)
        if self.theta_per_day > 0:
            raise ValueError("theta_per_day must be 0 or less")
        _validate_nonnegative_real("gamma", self.gamma)
        _validate_positive_real("underlying_price", self.underlying_price)
        greeks_methodology = _normalize_required_string(
            "greeks_methodology", self.greeks_methodology
        )
        _validate_int("repeated_bet_count", self.repeated_bet_count)
        if self.repeated_bet_count <= 0:
            raise ValueError("repeated_bet_count must be greater than 0")

        earliest_expiration = min(leg.expiration for leg in self.structure.legs)
        if self.as_of_date >= earliest_expiration:
            raise ValueError("as_of_date must be earlier than every leg expiration")
        days_to_earliest_expiration = (earliest_expiration - self.as_of_date).days
        if self.structure.expected_holding_days > days_to_earliest_expiration:
            raise ValueError("expected holding period exceeds the earliest expiration")
        object.__setattr__(self, "greeks_methodology", greeks_methodology)

    @property
    def total_entry_cost(self) -> float:
        """Return midpoint premium plus estimated spread, commissions, and fees."""

        return (
            self.quoted_mid_premium
            + self.estimated_spread_cost
            + self.commissions_and_fees
        )

    @property
    def maximum_loss(self) -> float:
        """Return maximum loss for the supported long-only structures."""

        return self.total_entry_cost

    @property
    def maximum_loss_percentage(self) -> float:
        """Return maximum loss as a fraction of assumed portfolio value."""

        return self.maximum_loss / self.structure.assumed_portfolio_value

    @property
    def gamma_pnl_for_one_percent_move(self) -> float:
        """Return the local Gamma P&L approximation for a 1% price move.

        This formula is valid because gamma is total-position d²V/dS² in USD
        of position-value change per USD² of underlying-price movement. The
        approximation excludes Delta, Vega, Theta, volatility-surface changes,
        jumps, and model error. It is not scenario P&L and must not be presented
        as expected profit.
        """

        return 0.5 * self.gamma * (self.underlying_price * 0.01) ** 2

    @property
    def gamma_cost_ratio_for_one_percent_move(self) -> float:
        """Return local 1% Gamma P&L divided by quoted midpoint premium.

        This is a local, dimensionless convexity-to-premium measure, not
        complete scenario P&L or expected profit.
        """

        return self.gamma_pnl_for_one_percent_move / self.quoted_mid_premium

    @property
    def cumulative_repeated_bet_cost(self) -> float:
        """Return entry cost across equal repeated attempts."""

        return self.total_entry_cost * self.repeated_bet_count

    @property
    def cumulative_repeated_bet_percentage(self) -> float:
        """Return repeated-attempt cost as a fraction of portfolio value."""

        return (
            self.cumulative_repeated_bet_cost
            / self.structure.assumed_portfolio_value
        )
