"""Tests for typed MVP screening evidence records."""

import datetime
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from convexity_hunter.evidence import (
    ClassifiedEvidence,
    EvidenceImpact,
    EvidenceKind,
    OptionLeg,
    OptionStructure,
    StructureCosts,
    TailPricingSlice,
    TermVolatilityPoint,
    VolatilityEnvironment,
)


AS_OF_DATE = datetime.date(2029, 12, 1)
EXPIRATION = datetime.date(2030, 1, 18)


def make_term_point(**overrides: object) -> TermVolatilityPoint:
    values = {"tenor_days": 30, "atm_iv": 0.20}
    values.update(overrides)
    return TermVolatilityPoint(**values)  # type: ignore[arg-type]


def make_environment(**overrides: object) -> VolatilityEnvironment:
    values = {
        "underlying": "SPY",
        "as_of_date": AS_OF_DATE,
        "reference_tenor_days": 30,
        "iv_percentile": 0.40,
        "iv_history_lookback_observations": 252,
        "historical_median_atm_iv": 0.22,
        "matched_realized_volatility": 0.18,
        "matched_realized_window_days": 30,
        "term_structure": (make_term_point(), make_term_point(tenor_days=60, atm_iv=0.24)),
    }
    values.update(overrides)
    return VolatilityEnvironment(**values)  # type: ignore[arg-type]


def make_tail_slice(**overrides: object) -> TailPricingSlice:
    values = {
        "underlying": "SPY",
        "as_of_date": AS_OF_DATE,
        "expiration": EXPIRATION,
        "atm_iv": 0.20,
        "put_25_delta_iv": 0.25,
        "call_25_delta_iv": 0.21,
        "put_10_delta_iv": 0.35,
        "call_10_delta_iv": 0.24,
        "skew_percentile": 0.60,
        "skew_history_lookback_observations": 252,
        "delta_methodology": "spot delta; linear interpolation in implied volatility",
    }
    values.update(overrides)
    return TailPricingSlice(**values)  # type: ignore[arg-type]


def make_structure(**overrides: object) -> OptionStructure:
    leg = OptionLeg("SPY", "call", 500.0, EXPIRATION)
    values = {
        "legs": (leg,),
        "assumed_portfolio_value": 100_000.0,
        "expected_holding_days": 7,
    }
    values.update(overrides)
    return OptionStructure(**values)  # type: ignore[arg-type]


def make_costs(**overrides: object) -> StructureCosts:
    values = {
        "structure": make_structure(),
        "as_of_date": AS_OF_DATE,
        "quoted_mid_premium": 1_000.0,
        "estimated_spread_cost": 20.0,
        "commissions_and_fees": 5.0,
        "theta_per_day": -10.0,
        "gamma": 0.40,
        "underlying_price": 500.0,
        "greeks_methodology": (
            "provider Greeks; scaled by quantity and multiplier; "
            "theta uses provider daily convention"
        ),
        "repeated_bet_count": 3,
    }
    values.update(overrides)
    return StructureCosts(**values)  # type: ignore[arg-type]


class EvidenceEnumTests(unittest.TestCase):
    def test_exact_evidence_kind_values(self) -> None:
        self.assertEqual(
            {item.name: item.value for item in EvidenceKind},
            {
                "OBSERVED_FACT": "observed_fact",
                "CALCULATED_METRIC": "calculated_metric",
                "ASSUMPTION": "assumption",
                "AI_INTERPRETATION": "ai_interpretation",
            },
        )

    def test_exact_evidence_impact_values(self) -> None:
        self.assertEqual(
            {item.name: item.value for item in EvidenceImpact},
            {"SUPPORTS": "supports", "WEAKENS": "weakens", "NEUTRAL": "neutral"},
        )


class ClassifiedEvidenceTests(unittest.TestCase):
    def test_valid_observed_fact(self) -> None:
        item = ClassifiedEvidence(
            "obs-1",
            EvidenceKind.OBSERVED_FACT,
            EvidenceImpact.SUPPORTS,
            "ATM IV is 20%.",
            source="provider snapshot",
        )
        self.assertEqual(item.source, "provider snapshot")

    def test_valid_calculated_metric(self) -> None:
        item = ClassifiedEvidence(
            "calc-1",
            EvidenceKind.CALCULATED_METRIC,
            EvidenceImpact.NEUTRAL,
            "IV minus realized volatility is 2%.",
            source="provider history",
            methodology="matched 30-day annualized windows",
        )
        self.assertIs(item.kind, EvidenceKind.CALCULATED_METRIC)

    def test_valid_assumption(self) -> None:
        item = ClassifiedEvidence(
            "assume-1",
            EvidenceKind.ASSUMPTION,
            EvidenceImpact.NEUTRAL,
            "Portfolio value is assumed to be $100,000.",
        )
        self.assertIsNone(item.source)

    def test_valid_ai_interpretation(self) -> None:
        item = ClassifiedEvidence(
            "ai-1",
            EvidenceKind.AI_INTERPRETATION,
            EvidenceImpact.WEAKENS,
            "The evidence may be incomplete.",
            methodology="critical review",
        )
        self.assertEqual(item.methodology, "critical review")

    def test_normalization(self) -> None:
        item = ClassifiedEvidence(
            "  obs-1  ",
            EvidenceKind.OBSERVED_FACT,
            EvidenceImpact.SUPPORTS,
            "  Statement.  ",
            source="  source  ",
            methodology="  method  ",
        )
        self.assertEqual(item.evidence_id, "obs-1")
        self.assertEqual(item.statement, "Statement.")
        self.assertEqual(item.source, "source")
        self.assertEqual(item.methodology, "method")

    def test_empty_evidence_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ClassifiedEvidence(
                " ", EvidenceKind.ASSUMPTION, EvidenceImpact.NEUTRAL, "Statement"
            )

    def test_empty_statement_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ClassifiedEvidence(
                "id", EvidenceKind.ASSUMPTION, EvidenceImpact.NEUTRAL, " "
            )

    def test_invalid_enum_types_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ClassifiedEvidence(
                "id", "observed_fact", EvidenceImpact.NEUTRAL, "Statement"  # type: ignore[arg-type]
            )
        with self.assertRaises(TypeError):
            ClassifiedEvidence(
                "id", EvidenceKind.ASSUMPTION, "neutral", "Statement"  # type: ignore[arg-type]
            )

    def test_observed_fact_without_source_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ClassifiedEvidence(
                "id", EvidenceKind.OBSERVED_FACT, EvidenceImpact.NEUTRAL, "Statement"
            )

    def test_calculated_metric_without_source_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ClassifiedEvidence(
                "id",
                EvidenceKind.CALCULATED_METRIC,
                EvidenceImpact.NEUTRAL,
                "Statement",
                methodology="method",
            )

    def test_calculated_metric_without_methodology_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ClassifiedEvidence(
                "id",
                EvidenceKind.CALCULATED_METRIC,
                EvidenceImpact.NEUTRAL,
                "Statement",
                source="source",
            )

    def test_invalid_optional_strings_rejected(self) -> None:
        for field, value, exception in (
            ("source", 1, TypeError),
            ("methodology", 1, TypeError),
            ("source", " ", ValueError),
            ("methodology", " ", ValueError),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(exception):
                ClassifiedEvidence(
                    "id",
                    EvidenceKind.ASSUMPTION,
                    EvidenceImpact.NEUTRAL,
                    "Statement",
                    **{field: value},  # type: ignore[arg-type]
                )

    def test_immutability(self) -> None:
        item = ClassifiedEvidence(
            "id", EvidenceKind.ASSUMPTION, EvidenceImpact.NEUTRAL, "Statement"
        )
        with self.assertRaises(FrozenInstanceError):
            item.statement = "Changed"


class TermVolatilityPointTests(unittest.TestCase):
    def test_valid_point(self) -> None:
        point = make_term_point()
        self.assertEqual(point.tenor_days, 30)
        self.assertEqual(point.atm_iv, 0.20)

    def test_invalid_tenor_type(self) -> None:
        for value in (True, "30", 30.0):
            with self.subTest(value=value), self.assertRaises(TypeError):
                make_term_point(tenor_days=value)

    def test_non_positive_tenor(self) -> None:
        for value in (0, -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_term_point(tenor_days=value)

    def test_invalid_iv_type(self) -> None:
        for value in (True, "0.20"):
            with self.subTest(value=value), self.assertRaises(TypeError):
                make_term_point(atm_iv=value)

    def test_non_positive_iv(self) -> None:
        for value in (0.0, -0.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_term_point(atm_iv=value)

    def test_non_finite_iv_rejected(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_term_point(atm_iv=value)

    def test_immutability(self) -> None:
        point = make_term_point()
        with self.assertRaises(FrozenInstanceError):
            point.atm_iv = 0.30


class VolatilityEnvironmentTests(unittest.TestCase):
    def test_valid_environment(self) -> None:
        environment = make_environment()
        self.assertEqual(environment.reference_tenor_days, 30)
        self.assertEqual(environment.iv_history_lookback_observations, 252)

    def test_underlying_normalization(self) -> None:
        self.assertEqual(make_environment(underlying="  spy ").underlying, "SPY")

    def test_list_term_structure_normalized_to_sorted_tuple(self) -> None:
        points = [make_term_point(tenor_days=60), make_term_point(tenor_days=30)]
        environment = make_environment(term_structure=points)
        self.assertIsInstance(environment.term_structure, tuple)
        self.assertEqual(
            [point.tenor_days for point in environment.term_structure], [30, 60]
        )

    def test_properties(self) -> None:
        environment = make_environment()
        self.assertEqual(environment.atm_iv, 0.20)
        self.assertAlmostEqual(environment.iv_vs_historical_median, -0.02)
        self.assertAlmostEqual(environment.implied_realized_gap, 0.02)

    def test_invalid_date_and_datetime_rejected(self) -> None:
        for value in ("2029-12-01", datetime.datetime(2029, 12, 1, 12, 0)):
            with self.subTest(value=value), self.assertRaises(TypeError):
                make_environment(as_of_date=value)

    def test_invalid_percentile_bounds_rejected(self) -> None:
        for value in (-0.01, 1.01):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_environment(iv_percentile=value)

    def test_non_matching_realized_window_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_environment(matched_realized_window_days=20)

    def test_invalid_iv_history_lookback_observations_rejected(self) -> None:
        for value, exception in (
            (True, TypeError),
            ("252", TypeError),
            (252.0, TypeError),
            (0, ValueError),
            (-1, ValueError),
        ):
            with self.subTest(value=value), self.assertRaises(exception):
                make_environment(iv_history_lookback_observations=value)

    def test_fewer_than_two_term_points_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_environment(term_structure=(make_term_point(),))

    def test_duplicate_tenors_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_environment(term_structure=(make_term_point(), make_term_point()))

    def test_missing_reference_tenor_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_environment(
                term_structure=(
                    make_term_point(tenor_days=60),
                    make_term_point(tenor_days=90),
                )
            )

    def test_invalid_term_item_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_environment(term_structure=(make_term_point(), "invalid"))

    def test_original_term_list_is_isolated(self) -> None:
        points = [make_term_point(), make_term_point(tenor_days=60)]
        environment = make_environment(term_structure=points)
        points.append(make_term_point(tenor_days=90))
        self.assertEqual(len(environment.term_structure), 2)

    def test_strict_numeric_validation(self) -> None:
        cases = (
            ({"reference_tenor_days": True}, TypeError),
            ({"iv_percentile": True}, TypeError),
            ({"historical_median_atm_iv": "0.22"}, TypeError),
            ({"matched_realized_volatility": float("nan")}, ValueError),
            ({"iv_percentile": float("inf")}, ValueError),
        )
        for fields, exception in cases:
            with self.subTest(fields=fields), self.assertRaises(exception):
                make_environment(**fields)

    def test_immutability(self) -> None:
        environment = make_environment()
        with self.assertRaises(FrozenInstanceError):
            environment.iv_percentile = 0.50


class TailPricingSliceTests(unittest.TestCase):
    def test_valid_slice_and_normalization(self) -> None:
        tail = make_tail_slice(
            underlying="  spy ",
            delta_methodology="  spot delta; linear interpolation  ",
        )
        self.assertEqual(tail.underlying, "SPY")
        self.assertEqual(tail.skew_history_lookback_observations, 252)
        self.assertEqual(tail.delta_methodology, "spot delta; linear interpolation")

    def test_skew_curvature_and_expiration_properties(self) -> None:
        tail = make_tail_slice()
        self.assertAlmostEqual(tail.downside_25_delta_skew, 0.05)
        self.assertAlmostEqual(tail.upside_25_delta_skew, 0.01)
        self.assertAlmostEqual(tail.downside_wing_curvature, 0.10)
        self.assertAlmostEqual(tail.upside_wing_curvature, 0.03)
        self.assertEqual(tail.days_to_expiration, 48)

    def test_expiration_on_or_before_as_of_date_rejected(self) -> None:
        for expiration in (AS_OF_DATE, AS_OF_DATE - datetime.timedelta(days=1)):
            with self.subTest(expiration=expiration), self.assertRaises(ValueError):
                make_tail_slice(expiration=expiration)

    def test_datetime_values_rejected(self) -> None:
        value = datetime.datetime(2029, 12, 1, 12, 0)
        with self.assertRaises(TypeError):
            make_tail_slice(as_of_date=value)
        with self.assertRaises(TypeError):
            make_tail_slice(expiration=value)

    def test_invalid_iv_types_and_non_positive_values_rejected(self) -> None:
        cases = (
            ({"atm_iv": True}, TypeError),
            ({"put_25_delta_iv": "0.25"}, TypeError),
            ({"call_25_delta_iv": 0.0}, ValueError),
            ({"put_10_delta_iv": -0.1}, ValueError),
        )
        for fields, exception in cases:
            with self.subTest(fields=fields), self.assertRaises(exception):
                make_tail_slice(**fields)

    def test_invalid_percentile_bounds_rejected(self) -> None:
        for value in (-0.01, 1.01):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_tail_slice(skew_percentile=value)

    def test_invalid_skew_history_lookback_observations_rejected(self) -> None:
        for value, exception in (
            (True, TypeError),
            ("252", TypeError),
            (252.0, TypeError),
            (0, ValueError),
            (-1, ValueError),
        ):
            with self.subTest(value=value), self.assertRaises(exception):
                make_tail_slice(skew_history_lookback_observations=value)

    def test_invalid_delta_methodology_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_tail_slice(delta_methodology=1)
        with self.assertRaises(ValueError):
            make_tail_slice(delta_methodology="   ")

    def test_non_finite_values_rejected(self) -> None:
        for fields in (
            {"atm_iv": float("nan")},
            {"call_10_delta_iv": float("inf")},
            {"skew_percentile": float("-inf")},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                make_tail_slice(**fields)

    def test_immutability(self) -> None:
        tail = make_tail_slice()
        with self.assertRaises(FrozenInstanceError):
            tail.atm_iv = 0.30


class StructureCostsTests(unittest.TestCase):
    def test_valid_long_call_costs(self) -> None:
        costs = make_costs()
        self.assertEqual(costs.structure.structure_type, "long_call")

    def test_valid_long_straddle_costs(self) -> None:
        call = OptionLeg("SPY", "call", 500.0, EXPIRATION)
        put = OptionLeg("SPY", "put", 500.0, EXPIRATION)
        structure = make_structure(legs=(call, put))
        costs = make_costs(structure=structure)
        self.assertEqual(costs.structure.structure_type, "long_straddle")

    def test_cost_properties(self) -> None:
        costs = make_costs()
        self.assertAlmostEqual(costs.total_entry_cost, 1_025.0)
        self.assertAlmostEqual(costs.maximum_loss, 1_025.0)
        self.assertAlmostEqual(costs.maximum_loss_percentage, 0.01025)
        self.assertAlmostEqual(costs.gamma_pnl_for_one_percent_move, 5.0)
        self.assertAlmostEqual(costs.gamma_cost_ratio_for_one_percent_move, 0.005)
        self.assertAlmostEqual(costs.cumulative_repeated_bet_cost, 3_075.0)
        self.assertAlmostEqual(costs.cumulative_repeated_bet_percentage, 0.03075)

    def test_zero_gamma_local_measures(self) -> None:
        costs = make_costs(gamma=0.0)
        self.assertAlmostEqual(costs.gamma_pnl_for_one_percent_move, 0.0)
        self.assertAlmostEqual(costs.gamma_cost_ratio_for_one_percent_move, 0.0)

    def test_valid_and_normalized_greeks_methodology(self) -> None:
        costs = make_costs(
            greeks_methodology="  provider Greeks; scaled by quantity and multiplier  "
        )
        self.assertEqual(
            costs.greeks_methodology,
            "provider Greeks; scaled by quantity and multiplier",
        )

    def test_invalid_greeks_methodology_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_costs(greeks_methodology=1)
        with self.assertRaises(ValueError):
            make_costs(greeks_methodology="   ")

    def test_greeks_methodology_immutability(self) -> None:
        costs = make_costs()
        with self.assertRaises(FrozenInstanceError):
            costs.greeks_methodology = "changed"

    def test_non_option_structure_rejected(self) -> None:
        with self.assertRaises(TypeError):
            make_costs(structure="SPY")

    def test_invalid_date_and_datetime_rejected(self) -> None:
        for value in ("2029-12-01", datetime.datetime(2029, 12, 1, 12, 0)):
            with self.subTest(value=value), self.assertRaises(TypeError):
                make_costs(as_of_date=value)

    def test_as_of_date_on_or_after_expiration_rejected(self) -> None:
        for value in (EXPIRATION, EXPIRATION + datetime.timedelta(days=1)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_costs(as_of_date=value)

    def test_holding_period_beyond_earliest_expiration_rejected(self) -> None:
        structure = make_structure(expected_holding_days=49)
        with self.assertRaises(ValueError):
            make_costs(structure=structure)

    def test_non_positive_quoted_mid_premium_rejected(self) -> None:
        for value in (0.0, -1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_costs(quoted_mid_premium=value)

    def test_negative_spread_or_fees_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_costs(estimated_spread_cost=-1.0)
        with self.assertRaises(ValueError):
            make_costs(commissions_and_fees=-1.0)

    def test_positive_theta_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_costs(theta_per_day=0.01)

    def test_negative_gamma_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_costs(gamma=-0.01)

    def test_invalid_underlying_price_rejected(self) -> None:
        for value, exception in (
            ("500", TypeError),
            (True, TypeError),
            (0.0, ValueError),
            (-1.0, ValueError),
            (float("nan"), ValueError),
            (float("inf"), ValueError),
            (float("-inf"), ValueError),
        ):
            with self.subTest(value=value), self.assertRaises(exception):
                make_costs(underlying_price=value)

    def test_invalid_repeated_bet_count_rejected(self) -> None:
        for value, exception in (
            (0, ValueError),
            (-1, ValueError),
            (True, TypeError),
            ("3", TypeError),
            (3.0, TypeError),
        ):
            with self.subTest(value=value), self.assertRaises(exception):
                make_costs(repeated_bet_count=value)

    def test_strict_numeric_validation(self) -> None:
        cases = (
            ({"quoted_mid_premium": True}, TypeError),
            ({"estimated_spread_cost": "20"}, TypeError),
            ({"theta_per_day": True}, TypeError),
            ({"quoted_mid_premium": float("nan")}, ValueError),
            ({"gamma": float("inf")}, ValueError),
            ({"commissions_and_fees": float("-inf")}, ValueError),
        )
        for fields, exception in cases:
            with self.subTest(fields=fields), self.assertRaises(exception):
                make_costs(**fields)

    def test_immutability(self) -> None:
        costs = make_costs()
        with self.assertRaises(FrozenInstanceError):
            costs.quoted_mid_premium = 2_000.0


if __name__ == "__main__":
    unittest.main()
