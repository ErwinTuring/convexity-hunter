"""Domain objects for option-structure research evidence."""

import datetime
import math
from dataclasses import dataclass
from enum import Enum
from numbers import Real
from typing import Tuple


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


class CandidateState(str, Enum):
    """Investigation state assigned to a candidate structure."""

    REJECT = "reject"
    WATCH = "watch"
    INVESTIGATE = "investigate"
    DATA_INSUFFICIENT = "data_insufficient"


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
