"""Immutable records used to assemble investigation reports."""

import datetime
import math
from dataclasses import dataclass
from numbers import Real
from typing import Tuple

from .evidence import OptionLeg, OptionStructure, Scenario


def _validate_real(name: str, value: object) -> None:
    """Require a finite real number that is not a Boolean."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


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


def _validate_nonnegative_int(name: str, value: object) -> None:
    """Require a nonnegative integer that is not a Boolean."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be 0 or greater")


def _validate_date_only(name: str, value: object) -> None:
    """Require a calendar date without a time component."""

    if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
        raise TypeError(f"{name} must be a date without a time component")


def _normalize_required_string(name: str, value: object) -> str:
    """Require and strip a non-empty string."""

    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _earliest_expiration(structure: OptionStructure) -> datetime.date:
    """Return the earliest expiration in a validated option structure."""

    return min(leg.expiration for leg in structure.legs)


@dataclass(frozen=True)
class LegVolatilityInput:
    """Starting implied volatility supplied for one exact option leg."""

    leg: OptionLeg
    base_iv: float

    def __post_init__(self) -> None:
        if not isinstance(self.leg, OptionLeg):
            raise TypeError("leg must be an OptionLeg")
        _validate_positive_real("base_iv", self.base_iv)


@dataclass(frozen=True)
class StructureLiquidity:
    """Total-position quote and weakest-leg liquidity evidence."""

    structure: OptionStructure
    as_of_date: datetime.date
    quoted_bid_value: float
    quoted_ask_value: float
    minimum_leg_open_interest: int
    minimum_leg_daily_volume: int
    quote_methodology: str

    def __post_init__(self) -> None:
        if not isinstance(self.structure, OptionStructure):
            raise TypeError("structure must be an OptionStructure")
        _validate_date_only("as_of_date", self.as_of_date)
        if self.as_of_date >= _earliest_expiration(self.structure):
            raise ValueError("as_of_date must be earlier than every leg expiration")
        _validate_nonnegative_real("quoted_bid_value", self.quoted_bid_value)
        _validate_positive_real("quoted_ask_value", self.quoted_ask_value)
        if self.quoted_ask_value < self.quoted_bid_value:
            raise ValueError("quoted_ask_value must be at least quoted_bid_value")
        _validate_nonnegative_int(
            "minimum_leg_open_interest", self.minimum_leg_open_interest
        )
        _validate_nonnegative_int(
            "minimum_leg_daily_volume", self.minimum_leg_daily_volume
        )
        quote_methodology = _normalize_required_string(
            "quote_methodology", self.quote_methodology
        )
        object.__setattr__(self, "quote_methodology", quote_methodology)

    @property
    def quoted_mid_value(self) -> float:
        """Return the total-position quote midpoint."""

        return (self.quoted_bid_value + self.quoted_ask_value) / 2

    @property
    def bid_ask_spread(self) -> float:
        """Return the absolute total-position bid-ask spread."""

        return self.quoted_ask_value - self.quoted_bid_value

    @property
    def bid_ask_spread_percentage(self) -> float:
        """Return the spread as a fraction of quoted midpoint value."""

        return self.bid_ask_spread / self.quoted_mid_value


@dataclass(frozen=True)
class ScenarioResult:
    """A supplied total-position valuation under one declared scenario.

    This record stores a result from a pricing engine or provider; it does not
    price options. P&L includes declared entry and estimated exit costs and is
    neither an expected return nor a probability-weighted forecast. Each
    ``LegVolatilityInput`` records the actual starting IV supplied for one
    declared structure leg. At expiration, these inputs remain for auditability
    even when terminal payoff no longer depends on volatility. Pricing
    methodology must describe the model or provider, rates, dividends,
    volatility-surface construction, interpolation, and limitations.
    """

    structure: OptionStructure
    as_of_date: datetime.date
    scenario: Scenario
    valuation_date: datetime.date
    base_underlying_price: float
    leg_volatility_inputs: Tuple[LegVolatilityInput, ...]
    estimated_position_value: float
    entry_cost_basis: float
    estimated_exit_cost: float
    pricing_methodology: str

    def __post_init__(self) -> None:
        if not isinstance(self.structure, OptionStructure):
            raise TypeError("structure must be an OptionStructure")
        if not isinstance(self.scenario, Scenario):
            raise TypeError("scenario must be a Scenario")
        _validate_date_only("as_of_date", self.as_of_date)
        _validate_date_only("valuation_date", self.valuation_date)

        earliest_expiration = _earliest_expiration(self.structure)
        if self.as_of_date >= earliest_expiration:
            raise ValueError("as_of_date must be earlier than every leg expiration")
        if self.valuation_date < self.as_of_date:
            raise ValueError("valuation_date must not be earlier than as_of_date")
        if self.valuation_date > earliest_expiration:
            raise ValueError("valuation_date must not be later than expiration")

        if self.scenario.valuation_time == "immediate":
            required_valuation_date = self.as_of_date
        elif self.scenario.valuation_time == "days_forward":
            required_valuation_date = self.as_of_date + datetime.timedelta(
                days=self.scenario.days_forward
            )
        elif self.scenario.valuation_time == "holding_horizon":
            required_valuation_date = self.as_of_date + datetime.timedelta(
                days=self.structure.expected_holding_days
            )
        else:
            required_valuation_date = earliest_expiration

        if required_valuation_date > earliest_expiration:
            raise ValueError("scenario valuation time resolves after expiration")
        if self.valuation_date != required_valuation_date:
            raise ValueError("valuation_date does not match the declared scenario")

        if not isinstance(self.leg_volatility_inputs, (tuple, list)):
            raise TypeError("leg_volatility_inputs must be a tuple or list")
        volatility_inputs = tuple(self.leg_volatility_inputs)
        if not all(
            isinstance(item, LegVolatilityInput) for item in volatility_inputs
        ):
            raise TypeError(
                "every leg_volatility_inputs item must be a LegVolatilityInput"
            )
        if len(volatility_inputs) != len(self.structure.legs):
            raise ValueError("one volatility input is required for every structure leg")
        input_legs = [item.leg for item in volatility_inputs]
        if len(set(input_legs)) != len(input_legs):
            raise ValueError("duplicate leg volatility inputs are not allowed")
        if any(leg not in self.structure.legs for leg in input_legs):
            raise ValueError("volatility input leg is not contained in the structure")
        ordered_inputs = tuple(
            next(item for item in volatility_inputs if item.leg == structure_leg)
            for structure_leg in self.structure.legs
        )
        object.__setattr__(self, "leg_volatility_inputs", ordered_inputs)

        _validate_positive_real("base_underlying_price", self.base_underlying_price)
        _validate_nonnegative_real(
            "estimated_position_value", self.estimated_position_value
        )
        _validate_positive_real("entry_cost_basis", self.entry_cost_basis)
        _validate_nonnegative_real("estimated_exit_cost", self.estimated_exit_cost)
        pricing_methodology = _normalize_required_string(
            "pricing_methodology", self.pricing_methodology
        )
        object.__setattr__(self, "pricing_methodology", pricing_methodology)

        # Cross-record consistency with StructureCosts and StructureLiquidity
        # belongs to the later CandidateResearchRecord, not this value record.

    @property
    def shocked_underlying_price(self) -> float:
        """Return the underlying price after the scenario's relative move."""

        return self.base_underlying_price * (1 + self.scenario.underlying_move)

    @property
    def base_ivs(self) -> Tuple[float, ...]:
        """Return starting IVs ordered consistently with structure legs."""

        return tuple(item.base_iv for item in self.leg_volatility_inputs)

    @property
    def shocked_ivs(self) -> Tuple[float, ...]:
        """Return each leg's IV after a parallel proportional shock.

        MVP v0.1 applies the same relative IV shock to every leg while
        preserving each starting IV. This does not model changes in skew,
        smile curvature, or term-structure shape and is not a complete
        volatility-surface scenario.
        """

        return tuple(
            base_iv * (1 + self.scenario.iv_change) for base_iv in self.base_ivs
        )

    @property
    def pnl_after_costs(self) -> float:
        """Return supplied scenario value less entry and estimated exit costs."""

        return (
            self.estimated_position_value
            - self.entry_cost_basis
            - self.estimated_exit_cost
        )

    @property
    def return_on_entry_cost(self) -> float:
        """Return after-cost P&L as a fraction of declared entry cost."""

        return self.pnl_after_costs / self.entry_cost_basis
