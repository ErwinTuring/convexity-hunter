"""Tests for liquidity and scenario-result report records."""

import datetime
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from convexity_hunter.evidence import OptionLeg, OptionStructure, Scenario
from convexity_hunter.report import (
    LegVolatilityInput,
    ScenarioResult,
    StructureLiquidity,
)


AS_OF_DATE = datetime.date(2030, 1, 1)
EXPIRATION = datetime.date(2030, 1, 31)


def make_structure(**overrides: object) -> OptionStructure:
    leg = OptionLeg("SPY", "call", 500.0, EXPIRATION)
    values = {
        "legs": (leg,),
        "assumed_portfolio_value": 100_000.0,
        "expected_holding_days": 10,
    }
    values.update(overrides)
    return OptionStructure(**values)  # type: ignore[arg-type]


def make_liquidity(**overrides: object) -> StructureLiquidity:
    values = {
        "structure": make_structure(),
        "as_of_date": AS_OF_DATE,
        "quoted_bid_value": 900.0,
        "quoted_ask_value": 1_100.0,
        "minimum_leg_open_interest": 500,
        "minimum_leg_daily_volume": 100,
        "quote_methodology": "provider composite; close snapshot; summed leg quotes",
    }
    values.update(overrides)
    return StructureLiquidity(**values)  # type: ignore[arg-type]


def make_volatility_input(**overrides: object) -> LegVolatilityInput:
    values = {
        "leg": OptionLeg("SPY", "call", 500.0, EXPIRATION),
        "base_iv": 0.20,
    }
    values.update(overrides)
    return LegVolatilityInput(**values)  # type: ignore[arg-type]


def make_result(**overrides: object) -> ScenarioResult:
    structure = make_structure()
    values = {
        "structure": structure,
        "as_of_date": AS_OF_DATE,
        "scenario": Scenario(0.10, 0.20, "immediate"),
        "valuation_date": AS_OF_DATE,
        "base_underlying_price": 100.0,
        "leg_volatility_inputs": tuple(
            LegVolatilityInput(leg, 0.20) for leg in structure.legs
        ),
        "estimated_position_value": 1_500.0,
        "entry_cost_basis": 1_000.0,
        "estimated_exit_cost": 20.0,
        "pricing_methodology": "provider model; flat shocked IV; stated rate and dividend",
    }
    values.update(overrides)
    return ScenarioResult(**values)  # type: ignore[arg-type]


class LegVolatilityInputTests(unittest.TestCase):
    def test_valid_input(self) -> None:
        item = make_volatility_input()
        self.assertEqual(item.base_iv, 0.20)

    def test_non_option_leg_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_volatility_input(leg="SPY")

    def test_invalid_numeric_type_and_bool_rejected(self) -> None:
        for value in ("0.20", True):
            with self.subTest(value=value), self.assertRaises(TypeError):
                make_volatility_input(base_iv=value)

    def test_non_positive_iv_rejected(self) -> None:
        for value in (0.0, -0.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_volatility_input(base_iv=value)

    def test_non_finite_iv_rejected(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_volatility_input(base_iv=value)

    def test_immutability(self) -> None:
        item = make_volatility_input()
        with self.assertRaises(FrozenInstanceError):
            item.base_iv = 0.30


class StructureLiquidityTests(unittest.TestCase):
    def test_valid_long_call_liquidity(self) -> None:
        liquidity = make_liquidity()
        self.assertEqual(liquidity.structure.structure_type, "long_call")

    def test_valid_long_straddle_liquidity(self) -> None:
        call = OptionLeg("SPY", "call", 500.0, EXPIRATION)
        put = OptionLeg("SPY", "put", 500.0, EXPIRATION)
        structure = make_structure(legs=(call, put))
        self.assertEqual(
            make_liquidity(structure=structure).structure.structure_type,
            "long_straddle",
        )

    def test_quote_properties(self) -> None:
        liquidity = make_liquidity()
        self.assertAlmostEqual(liquidity.quoted_mid_value, 1_000.0)
        self.assertAlmostEqual(liquidity.bid_ask_spread, 200.0)
        self.assertAlmostEqual(liquidity.bid_ask_spread_percentage, 0.20)

    def test_methodology_normalization(self) -> None:
        liquidity = make_liquidity(quote_methodology="  composite close quote  ")
        self.assertEqual(liquidity.quote_methodology, "composite close quote")

    def test_non_option_structure_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_liquidity(structure="SPY")

    def test_date_and_datetime_validation(self) -> None:
        for value in ("2030-01-01", datetime.datetime(2030, 1, 1, 12, 0)):
            with self.subTest(value=value), self.assertRaises(TypeError):
                make_liquidity(as_of_date=value)

    def test_date_on_or_after_expiration_rejected(self) -> None:
        for value in (EXPIRATION, EXPIRATION + datetime.timedelta(days=1)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_liquidity(as_of_date=value)

    def test_negative_bid_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_liquidity(quoted_bid_value=-1.0)

    def test_non_positive_ask_rejected(self) -> None:
        for value in (0.0, -1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_liquidity(quoted_ask_value=value)

    def test_ask_below_bid_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_liquidity(quoted_bid_value=1_100.0, quoted_ask_value=1_000.0)

    def test_invalid_open_interest_and_volume_types_rejected(self) -> None:
        for fields in (
            {"minimum_leg_open_interest": "500"},
            {"minimum_leg_open_interest": 500.0},
            {"minimum_leg_daily_volume": "100"},
            {"minimum_leg_daily_volume": 100.0},
        ):
            with self.subTest(fields=fields), self.assertRaises(TypeError):
                make_liquidity(**fields)

    def test_bool_integer_values_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_liquidity(minimum_leg_open_interest=True)
        with self.assertRaises(TypeError):
            make_liquidity(minimum_leg_daily_volume=False)

    def test_negative_open_interest_and_volume_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_liquidity(minimum_leg_open_interest=-1)
        with self.assertRaises(ValueError):
            make_liquidity(minimum_leg_daily_volume=-1)

    def test_invalid_or_empty_methodology_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_liquidity(quote_methodology=1)
        with self.assertRaises(ValueError):
            make_liquidity(quote_methodology="   ")

    def test_quote_numeric_strings_and_bools_rejected(self) -> None:
        for fields in (
            {"quoted_bid_value": "900"},
            {"quoted_ask_value": "1100"},
            {"quoted_bid_value": True},
            {"quoted_ask_value": True},
        ):
            with self.subTest(fields=fields), self.assertRaises(TypeError):
                make_liquidity(**fields)

    def test_nan_and_infinity_rejected(self) -> None:
        for fields in (
            {"quoted_bid_value": float("nan")},
            {"quoted_bid_value": float("inf")},
            {"quoted_ask_value": float("-inf")},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                make_liquidity(**fields)

    def test_immutability(self) -> None:
        liquidity = make_liquidity()
        with self.assertRaises(FrozenInstanceError):
            liquidity.quoted_bid_value = 950.0


class ScenarioResultTests(unittest.TestCase):
    def test_valid_immediate_result(self) -> None:
        result = make_result()
        self.assertEqual(result.valuation_date, AS_OF_DATE)

    def test_valid_days_forward_result(self) -> None:
        scenario = Scenario(0.0, 0.0, "days_forward", days_forward=7)
        result = make_result(
            scenario=scenario,
            valuation_date=AS_OF_DATE + datetime.timedelta(days=7),
        )
        self.assertEqual(result.valuation_date, datetime.date(2030, 1, 8))

    def test_valid_holding_horizon_result(self) -> None:
        result = make_result(
            scenario=Scenario(0.0, 0.0, "holding_horizon"),
            valuation_date=AS_OF_DATE + datetime.timedelta(days=10),
        )
        self.assertEqual(result.valuation_date, datetime.date(2030, 1, 11))

    def test_valid_expiration_result(self) -> None:
        result = make_result(
            scenario=Scenario(0.0, 0.0, "expiration"),
            valuation_date=EXPIRATION,
        )
        self.assertEqual(result.valuation_date, EXPIRATION)

    def test_valid_one_leg_volatility_inputs(self) -> None:
        result = make_result()
        self.assertEqual(len(result.leg_volatility_inputs), 1)
        self.assertEqual(result.leg_volatility_inputs[0].leg, result.structure.legs[0])

    def test_valid_straddle_with_distinct_leg_ivs(self) -> None:
        call = OptionLeg("SPY", "call", 500.0, EXPIRATION)
        put = OptionLeg("SPY", "put", 500.0, EXPIRATION)
        structure = make_structure(legs=(call, put))
        result = make_result(
            structure=structure,
            leg_volatility_inputs=(
                LegVolatilityInput(call, 0.20),
                LegVolatilityInput(put, 0.30),
            ),
        )
        self.assertEqual(result.base_ivs, (0.20, 0.30))
        self.assertAlmostEqual(result.shocked_ivs[0], 0.24)
        self.assertAlmostEqual(result.shocked_ivs[1], 0.36)

    def test_input_list_normalized_and_isolated(self) -> None:
        inputs = [make_volatility_input()]
        result = make_result(leg_volatility_inputs=inputs)
        inputs.append(make_volatility_input())
        self.assertIsInstance(result.leg_volatility_inputs, tuple)
        self.assertEqual(len(result.leg_volatility_inputs), 1)

    def test_stored_order_matches_structure_leg_order(self) -> None:
        call = OptionLeg("SPY", "call", 500.0, EXPIRATION)
        put = OptionLeg("SPY", "put", 500.0, EXPIRATION)
        structure = make_structure(legs=(call, put))
        result = make_result(
            structure=structure,
            leg_volatility_inputs=[
                LegVolatilityInput(put, 0.30),
                LegVolatilityInput(call, 0.20),
            ],
        )
        self.assertEqual(
            tuple(item.leg for item in result.leg_volatility_inputs),
            structure.legs,
        )
        self.assertEqual(result.base_ivs, (0.20, 0.30))

    def test_zero_iv_shock_preserves_each_leg_iv(self) -> None:
        call = OptionLeg("SPY", "call", 500.0, EXPIRATION)
        put = OptionLeg("SPY", "put", 500.0, EXPIRATION)
        structure = make_structure(legs=(call, put))
        result = make_result(
            structure=structure,
            scenario=Scenario(0.0, 0.0, "immediate"),
            leg_volatility_inputs=(
                LegVolatilityInput(call, 0.20),
                LegVolatilityInput(put, 0.30),
            ),
        )
        self.assertEqual(result.shocked_ivs, result.base_ivs)

    def test_invalid_volatility_input_container_rejected(self) -> None:
        for value in (None, "inputs", b"inputs", {make_volatility_input()}):
            with self.subTest(value=value), self.assertRaises(TypeError):
                make_result(leg_volatility_inputs=value)

    def test_non_volatility_input_item_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_result(leg_volatility_inputs=("invalid",))

    def test_missing_leg_input_rejected(self) -> None:
        call = OptionLeg("SPY", "call", 500.0, EXPIRATION)
        put = OptionLeg("SPY", "put", 500.0, EXPIRATION)
        structure = make_structure(legs=(call, put))
        with self.assertRaises(ValueError):
            make_result(
                structure=structure,
                leg_volatility_inputs=(LegVolatilityInput(call, 0.20),),
            )

    def test_extra_leg_input_rejected(self) -> None:
        declared = OptionLeg("SPY", "call", 500.0, EXPIRATION)
        extra = OptionLeg("SPY", "put", 500.0, EXPIRATION)
        structure = make_structure(legs=(declared,))
        with self.assertRaises(ValueError):
            make_result(
                structure=structure,
                leg_volatility_inputs=(
                    LegVolatilityInput(declared, 0.20),
                    LegVolatilityInput(extra, 0.30),
                ),
            )

    def test_duplicate_leg_input_rejected(self) -> None:
        call = OptionLeg("SPY", "call", 500.0, EXPIRATION)
        put = OptionLeg("SPY", "put", 500.0, EXPIRATION)
        structure = make_structure(legs=(call, put))
        with self.assertRaises(ValueError):
            make_result(
                structure=structure,
                leg_volatility_inputs=(
                    LegVolatilityInput(call, 0.20),
                    LegVolatilityInput(call, 0.30),
                ),
            )

    def test_leg_not_in_structure_rejected(self) -> None:
        other_leg = OptionLeg("QQQ", "call", 500.0, EXPIRATION)
        with self.assertRaises(ValueError):
            make_result(
                leg_volatility_inputs=(LegVolatilityInput(other_leg, 0.20),)
            )

    def test_volatility_inputs_immutability(self) -> None:
        result = make_result()
        with self.assertRaises(FrozenInstanceError):
            result.leg_volatility_inputs = ()

    def test_shocked_price_and_iv_properties(self) -> None:
        result = make_result()
        self.assertAlmostEqual(result.shocked_underlying_price, 110.0)
        self.assertEqual(result.base_ivs, (0.20,))
        self.assertAlmostEqual(result.shocked_ivs[0], 0.24)

    def test_positive_pnl_and_return(self) -> None:
        result = make_result()
        self.assertAlmostEqual(result.pnl_after_costs, 480.0)
        self.assertAlmostEqual(result.return_on_entry_cost, 0.48)

    def test_negative_pnl(self) -> None:
        result = make_result(estimated_position_value=500.0)
        self.assertAlmostEqual(result.pnl_after_costs, -520.0)
        self.assertAlmostEqual(result.return_on_entry_cost, -0.52)

    def test_methodology_normalization(self) -> None:
        result = make_result(pricing_methodology="  provider model  ")
        self.assertEqual(result.pricing_methodology, "provider model")

    def test_leg_base_iv_is_independent_input(self) -> None:
        leg = make_structure().legs[0]
        result = make_result(
            leg_volatility_inputs=(LegVolatilityInput(leg, 0.37),)
        )
        self.assertEqual(result.base_ivs, (0.37,))
        self.assertAlmostEqual(result.shocked_ivs[0], 0.444)

    def test_non_option_structure_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_result(structure="SPY")

    def test_non_scenario_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_result(scenario="immediate")

    def test_date_and_datetime_validation(self) -> None:
        for field in ("as_of_date", "valuation_date"):
            for value in ("2030-01-01", datetime.datetime(2030, 1, 1, 12, 0)):
                with self.subTest(field=field, value=value), self.assertRaises(TypeError):
                    make_result(**{field: value})

    def test_invalid_valuation_date_for_each_time_type(self) -> None:
        cases = (
            (Scenario(0.0, 0.0, "immediate"), AS_OF_DATE + datetime.timedelta(days=1)),
            (Scenario(0.0, 0.0, "days_forward", 7), AS_OF_DATE),
            (Scenario(0.0, 0.0, "holding_horizon"), AS_OF_DATE),
            (Scenario(0.0, 0.0, "expiration"), EXPIRATION - datetime.timedelta(days=1)),
        )
        for scenario, valuation_date in cases:
            with self.subTest(scenario=scenario), self.assertRaises(ValueError):
                make_result(scenario=scenario, valuation_date=valuation_date)

    def test_valuation_date_before_as_of_date_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_result(valuation_date=AS_OF_DATE - datetime.timedelta(days=1))

    def test_valuation_date_after_expiration_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_result(valuation_date=EXPIRATION + datetime.timedelta(days=1))

    def test_holding_horizon_beyond_expiration_rejected(self) -> None:
        structure = make_structure(expected_holding_days=31)
        with self.assertRaises(ValueError):
            make_result(
                structure=structure,
                scenario=Scenario(0.0, 0.0, "holding_horizon"),
                valuation_date=EXPIRATION,
            )

    def test_days_forward_beyond_expiration_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_result(
                scenario=Scenario(0.0, 0.0, "days_forward", days_forward=31),
                valuation_date=EXPIRATION,
            )

    def test_invalid_numeric_types_and_bools_rejected(self) -> None:
        fields = (
            "base_underlying_price",
            "estimated_position_value",
            "entry_cost_basis",
            "estimated_exit_cost",
        )
        for field in fields:
            for value in ("1.0", True):
                with self.subTest(field=field, value=value), self.assertRaises(TypeError):
                    make_result(**{field: value})

    def test_non_positive_base_price_rejected(self) -> None:
        for value in (0.0, -1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_result(base_underlying_price=value)

    def test_negative_position_value_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_result(estimated_position_value=-1.0)

    def test_non_positive_entry_cost_rejected(self) -> None:
        for value in (0.0, -1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_result(entry_cost_basis=value)

    def test_negative_exit_cost_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_result(estimated_exit_cost=-1.0)

    def test_nan_and_infinity_rejected(self) -> None:
        cases = (
            {"base_underlying_price": float("nan")},
            {"estimated_position_value": float("-inf")},
            {"entry_cost_basis": float("nan")},
            {"estimated_exit_cost": float("inf")},
        )
        for fields in cases:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                make_result(**fields)

    def test_invalid_or_empty_methodology_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_result(pricing_methodology=1)
        with self.assertRaises(ValueError):
            make_result(pricing_methodology="   ")

    def test_immutability(self) -> None:
        result = make_result()
        with self.assertRaises(FrozenInstanceError):
            result.estimated_position_value = 2_000.0


if __name__ == "__main__":
    unittest.main()
