"""Tests for the first MVP domain objects."""

import datetime
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from convexity_hunter.evidence import (
    CandidateState,
    OptionLeg,
    OptionStructure,
    Scenario,
)


EXPIRATION = datetime.date(2030, 1, 18)


def make_leg(**overrides: object) -> OptionLeg:
    """Create a valid option leg with selected field overrides."""

    values = {
        "underlying": "SPY",
        "option_type": "call",
        "strike": 500.0,
        "expiration": EXPIRATION,
        "quantity": 1,
        "contract_multiplier": 100,
    }
    values.update(overrides)
    return OptionLeg(**values)  # type: ignore[arg-type]


class CandidateStateTests(unittest.TestCase):
    def test_exact_enum_values(self) -> None:
        self.assertEqual(
            {state.name: state.value for state in CandidateState},
            {
                "REJECT": "reject",
                "WATCH": "watch",
                "INVESTIGATE": "investigate",
                "DATA_INSUFFICIENT": "data_insufficient",
            },
        )


class OptionLegTests(unittest.TestCase):
    def test_valid_call(self) -> None:
        leg = make_leg(option_type="call")
        self.assertEqual(leg.option_type, "call")

    def test_valid_put(self) -> None:
        leg = make_leg(option_type="put")
        self.assertEqual(leg.option_type, "put")

    def test_symbol_and_option_type_normalization(self) -> None:
        call = make_leg(underlying="  spy  ", option_type=" Call ")
        put = make_leg(option_type=" PUT ")
        self.assertEqual(call.underlying, "SPY")
        self.assertEqual(call.option_type, "call")
        self.assertEqual(put.option_type, "put")

    def test_empty_underlying_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_leg(underlying="   ")

    def test_invalid_option_type_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_leg(option_type="future")

    def test_non_string_option_type_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            make_leg(option_type=1)

    def test_empty_normalized_option_type_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            make_leg(option_type="   ")

    def test_non_positive_strike_rejected(self) -> None:
        for strike in (0.0, -1.0):
            with self.subTest(strike=strike), self.assertRaises(ValueError):
                make_leg(strike=strike)

    def test_strike_rejects_incorrect_types(self) -> None:
        for strike in (True, "500"):
            with self.subTest(strike=strike), self.assertRaises(TypeError):
                make_leg(strike=strike)

    def test_strike_rejects_non_finite_values(self) -> None:
        for strike in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(strike=strike), self.assertRaises(ValueError):
                make_leg(strike=strike)

    def test_strike_accepts_normal_int_and_float_values(self) -> None:
        self.assertEqual(make_leg(strike=500).strike, 500)
        self.assertEqual(make_leg(strike=500.5).strike, 500.5)

    def test_invalid_expiration_type_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_leg(expiration="2030-01-18")

    def test_date_only_expiration_accepted(self) -> None:
        expiration = datetime.date(2030, 1, 18)
        self.assertEqual(make_leg(expiration=expiration).expiration, expiration)

    def test_datetime_expiration_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_leg(expiration=datetime.datetime(2030, 1, 18, 12, 0))

    def test_non_positive_quantity_rejected(self) -> None:
        for quantity in (0, -1):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                make_leg(quantity=quantity)

    def test_non_positive_multiplier_rejected(self) -> None:
        for multiplier in (0, -1):
            with self.subTest(multiplier=multiplier), self.assertRaises(ValueError):
                make_leg(contract_multiplier=multiplier)

    def test_integer_fields_reject_incorrect_types(self) -> None:
        invalid_fields = (
            {"quantity": True},
            {"quantity": "1"},
            {"contract_multiplier": True},
            {"contract_multiplier": "100"},
        )
        for fields in invalid_fields:
            with self.subTest(fields=fields), self.assertRaises(TypeError):
                make_leg(**fields)

    def test_immutability(self) -> None:
        leg = make_leg()
        with self.assertRaises(FrozenInstanceError):
            leg.strike = 510.0


class OptionStructureTests(unittest.TestCase):
    def make_structure(self, *legs: OptionLeg, **overrides: object) -> OptionStructure:
        values = {
            "legs": legs,
            "assumed_portfolio_value": 100_000.0,
            "expected_holding_days": 7,
        }
        values.update(overrides)
        return OptionStructure(**values)  # type: ignore[arg-type]

    def test_valid_long_call(self) -> None:
        structure = self.make_structure(make_leg(option_type="call"))
        self.assertEqual(structure.structure_type, "long_call")

    def test_valid_long_put(self) -> None:
        structure = self.make_structure(make_leg(option_type="put"))
        self.assertEqual(structure.structure_type, "long_put")

    def test_valid_long_straddle(self) -> None:
        structure = self.make_structure(
            make_leg(option_type="call"), make_leg(option_type="put")
        )
        self.assertEqual(structure.structure_type, "long_straddle")

    def test_shared_underlying_property(self) -> None:
        structure = self.make_structure(
            make_leg(option_type="put"), make_leg(option_type="call")
        )
        self.assertEqual(structure.underlying, "SPY")

    def test_list_of_legs_is_normalized_to_tuple(self) -> None:
        legs = [make_leg()]
        structure = self.make_structure(legs=legs)
        self.assertIsInstance(structure.legs, tuple)
        self.assertEqual(structure.legs, tuple(legs))

    def test_mutating_input_list_does_not_change_structure(self) -> None:
        legs = [make_leg()]
        structure = self.make_structure(legs=legs)
        legs.append(make_leg(option_type="put"))
        self.assertEqual(len(structure.legs), 1)
        self.assertEqual(structure.structure_type, "long_call")

    def test_unsupported_legs_container_types_rejected(self) -> None:
        for legs in ("SPY", b"SPY", None, {make_leg()}):
            with self.subTest(legs=legs), self.assertRaises(TypeError):
                self.make_structure(legs=legs)

    def test_zero_legs_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.make_structure()

    def test_more_than_two_legs_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.make_structure(make_leg(), make_leg(option_type="put"), make_leg())

    def test_non_option_leg_item_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.make_structure(make_leg(), "not a leg")  # type: ignore[arg-type]

    def assert_mismatched_straddle_rejected(
        self, call: OptionLeg, put: OptionLeg
    ) -> None:
        with self.assertRaises(ValueError):
            self.make_structure(call, put)

    def test_mismatched_straddle_underlying_rejected(self) -> None:
        self.assert_mismatched_straddle_rejected(
            make_leg(option_type="call"),
            make_leg(underlying="QQQ", option_type="put"),
        )

    def test_mismatched_strike_rejected(self) -> None:
        self.assert_mismatched_straddle_rejected(
            make_leg(option_type="call"), make_leg(option_type="put", strike=505.0)
        )

    def test_mismatched_expiration_rejected(self) -> None:
        self.assert_mismatched_straddle_rejected(
            make_leg(option_type="call"),
            make_leg(option_type="put", expiration=datetime.date(2030, 2, 15)),
        )

    def test_mismatched_quantity_rejected(self) -> None:
        self.assert_mismatched_straddle_rejected(
            make_leg(option_type="call"), make_leg(option_type="put", quantity=2)
        )

    def test_mismatched_multiplier_rejected(self) -> None:
        self.assert_mismatched_straddle_rejected(
            make_leg(option_type="call"),
            make_leg(option_type="put", contract_multiplier=10),
        )

    def test_two_calls_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.make_structure(make_leg(), make_leg())

    def test_two_puts_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.make_structure(make_leg(option_type="put"), make_leg(option_type="put"))

    def test_non_positive_portfolio_value_rejected(self) -> None:
        for value in (0.0, -1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.make_structure(make_leg(), assumed_portfolio_value=value)

    def test_portfolio_value_rejects_incorrect_types(self) -> None:
        for value in (True, "100000"):
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.make_structure(make_leg(), assumed_portfolio_value=value)

    def test_portfolio_value_rejects_non_finite_values(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.make_structure(make_leg(), assumed_portfolio_value=value)

    def test_portfolio_value_accepts_normal_int_and_float_values(self) -> None:
        for value in (100_000, 100_000.5):
            with self.subTest(value=value):
                structure = self.make_structure(
                    make_leg(), assumed_portfolio_value=value
                )
                self.assertEqual(structure.assumed_portfolio_value, value)

    def test_negative_holding_days_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.make_structure(make_leg(), expected_holding_days=-1)

    def test_holding_days_rejects_incorrect_types(self) -> None:
        for value in (True, "7", 7.0):
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.make_structure(make_leg(), expected_holding_days=value)

    def test_immutability(self) -> None:
        structure = self.make_structure(make_leg())
        with self.assertRaises(FrozenInstanceError):
            structure.expected_holding_days = 10


class ScenarioTests(unittest.TestCase):
    def test_valid_immediate_scenario(self) -> None:
        scenario = Scenario(-0.10, 0.20, "immediate")
        self.assertEqual(scenario.days_forward, 0)

    def test_valid_days_forward_scenario(self) -> None:
        scenario = Scenario(0.05, 0.0, "days_forward", days_forward=7)
        self.assertEqual(scenario.days_forward, 7)

    def test_valid_holding_horizon_scenario(self) -> None:
        scenario = Scenario(0.10, 0.50, "holding_horizon")
        self.assertEqual(scenario.valuation_time, "holding_horizon")

    def test_valid_expiration_scenario(self) -> None:
        scenario = Scenario(0.20, -0.20, "expiration")
        self.assertEqual(scenario.valuation_time, "expiration")

    def test_valuation_time_normalization(self) -> None:
        immediate = Scenario(0.0, 0.0, " Immediate ")
        days_forward = Scenario(0.0, 0.0, " DAYS_FORWARD ", days_forward=7)
        self.assertEqual(immediate.valuation_time, "immediate")
        self.assertEqual(days_forward.valuation_time, "days_forward")

    def test_underlying_move_of_negative_one_or_less_rejected(self) -> None:
        for move in (-1.0, -1.1):
            with self.subTest(move=move), self.assertRaises(ValueError):
                Scenario(move, 0.0, "immediate")

    def test_iv_change_of_negative_one_or_less_rejected(self) -> None:
        for change in (-1.0, -1.1):
            with self.subTest(change=change), self.assertRaises(ValueError):
                Scenario(0.0, change, "immediate")

    def test_moves_reject_incorrect_types(self) -> None:
        invalid_values = (
            {"underlying_move": True},
            {"underlying_move": "0.1"},
            {"iv_change": True},
            {"iv_change": "0.2"},
        )
        for values in invalid_values:
            inputs = {"underlying_move": 0.0, "iv_change": 0.0}
            inputs.update(values)
            with self.subTest(values=values), self.assertRaises(TypeError):
                Scenario(valuation_time="immediate", **inputs)  # type: ignore[arg-type]

    def test_moves_reject_non_finite_values(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(field="underlying_move", value=value), self.assertRaises(
                ValueError
            ):
                Scenario(value, 0.0, "immediate")
            with self.subTest(field="iv_change", value=value), self.assertRaises(
                ValueError
            ):
                Scenario(0.0, value, "immediate")

    def test_moves_accept_normal_int_and_float_values(self) -> None:
        scenario = Scenario(0, 0.5, "immediate")
        self.assertEqual(scenario.underlying_move, 0)
        self.assertEqual(scenario.iv_change, 0.5)

    def test_invalid_valuation_time_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Scenario(0.0, 0.0, "tomorrow")

    def test_non_string_valuation_time_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            Scenario(0.0, 0.0, 1)  # type: ignore[arg-type]

    def test_empty_normalized_valuation_time_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            Scenario(0.0, 0.0, "   ")

    def test_negative_days_forward_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Scenario(0.0, 0.0, "days_forward", days_forward=-1)

    def test_days_forward_rejects_incorrect_types(self) -> None:
        for value in (True, "7", 7.0):
            with self.subTest(value=value), self.assertRaises(TypeError):
                Scenario(0.0, 0.0, "days_forward", days_forward=value)

    def test_inconsistent_immediate_days_forward_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Scenario(0.0, 0.0, "immediate", days_forward=1)

    def test_inconsistent_days_forward_value_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Scenario(0.0, 0.0, "days_forward", days_forward=0)

    def test_inconsistent_holding_horizon_days_forward_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Scenario(0.0, 0.0, "holding_horizon", days_forward=7)

    def test_inconsistent_expiration_days_forward_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Scenario(0.0, 0.0, "expiration", days_forward=7)

    def test_immutability(self) -> None:
        scenario = Scenario(0.0, 0.0, "immediate")
        with self.assertRaises(FrozenInstanceError):
            scenario.iv_change = 0.20


if __name__ == "__main__":
    unittest.main()
