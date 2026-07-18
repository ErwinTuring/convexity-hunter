"""Tests for deterministic screening policy v0.1."""

import dataclasses
import math
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter.evidence import CandidateState
from convexity_hunter.scanner import (
    DATA_INSUFFICIENT_REASON_ORDER,
    INVESTIGATE_REASON_ORDER,
    REJECT_REASON_ORDER,
    WATCH_REASON_ORDER,
    ScreeningDecision,
    ScreeningPolicy,
    ScreeningReasonCode,
    screen_candidate,
)
from tests.screening_fixtures import build_screening_candidate, build_test_policy


R = ScreeningReasonCode


class ScreeningReasonCodeTests(unittest.TestCase):
    def test_exact_values_declaration_order_and_groups(self) -> None:
        expected_groups = (
            (
                "max_loss_hard_limit_exceeded",
                "repeated_bet_hard_limit_exceeded",
                "spread_hard_limit_exceeded",
                "open_interest_hard_minimum_failed",
                "daily_volume_hard_minimum_failed",
                "theta_burden_hard_limit_exceeded",
                "target_move_scenario_not_profitable",
            ),
            (
                "missing_costs",
                "missing_liquidity",
                "missing_volatility_environment",
                "missing_structure_expiration_tail_slice",
                "missing_target_move_scenario",
                "missing_volatility_crush_scenario",
            ),
            (
                "max_loss_above_investigate_limit",
                "repeated_bet_above_investigate_limit",
                "spread_above_investigate_limit",
                "open_interest_below_investigate_minimum",
                "daily_volume_below_investigate_minimum",
                "theta_burden_above_investigate_limit",
                "volatility_environment_not_supportive",
                "tail_pricing_not_supportive",
            ),
            (
                "affordability_gates_passed",
                "liquidity_gates_passed",
                "volatility_environment_supportive",
                "tail_pricing_supportive",
                "target_move_scenarios_profitable",
            ),
        )
        expected = tuple(value for group in expected_groups for value in group)
        self.assertEqual(len(expected), 26)
        self.assertEqual(tuple(item.value for item in ScreeningReasonCode), expected)
        actual_groups = (
            REJECT_REASON_ORDER,
            DATA_INSUFFICIENT_REASON_ORDER,
            WATCH_REASON_ORDER,
            INVESTIGATE_REASON_ORDER,
        )
        self.assertEqual(
            tuple(tuple(item.value for item in group) for group in actual_groups),
            expected_groups,
        )
        flattened = tuple(item for group in actual_groups for item in group)
        self.assertEqual(len(flattened), len(set(flattened)))


class ScreeningPolicyTests(unittest.TestCase):
    EXPECTED_FIELD_NAMES = (
        "policy_id",
        "policy_version",
        "maximum_loss_hard_limit",
        "repeated_bet_hard_limit",
        "spread_hard_limit",
        "open_interest_hard_minimum",
        "daily_volume_hard_minimum",
        "theta_burden_hard_limit",
        "maximum_loss_investigate_limit",
        "repeated_bet_investigate_limit",
        "theta_burden_investigate_limit",
        "spread_investigate_limit",
        "open_interest_investigate_minimum",
        "daily_volume_investigate_minimum",
        "iv_percentile_support_maximum",
        "iv_vs_historical_median_support_maximum",
        "implied_realized_gap_support_maximum",
        "minimum_volatility_support_signals",
        "long_call_upside_skew_maximum",
        "long_call_upside_curvature_maximum",
        "long_put_downside_skew_maximum",
        "long_put_downside_curvature_maximum",
        "required_valuation_time",
        "long_call_target_underlying_move",
        "long_put_target_underlying_move",
        "long_straddle_downside_target_underlying_move",
        "long_straddle_upside_target_underlying_move",
        "target_iv_change",
        "volatility_crush_underlying_move",
        "volatility_crush_iv_change",
        "scenario_relative_tolerance",
        "scenario_absolute_tolerance",
    )

    def test_exact_policy_dataclass_field_surface(self) -> None:
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(ScreeningPolicy)),
            self.EXPECTED_FIELD_NAMES,
        )

    def test_default_identity_and_values(self) -> None:
        policy = ScreeningPolicy()
        expected = {
            "policy_id": "synthetic-screening-v0.1",
            "policy_version": "0.1",
            "maximum_loss_hard_limit": 0.05,
            "repeated_bet_hard_limit": 0.15,
            "spread_hard_limit": 0.12,
            "open_interest_hard_minimum": 50,
            "daily_volume_hard_minimum": 10,
            "theta_burden_hard_limit": 0.50,
            "maximum_loss_investigate_limit": 0.025,
            "repeated_bet_investigate_limit": 0.08,
            "theta_burden_investigate_limit": 0.25,
            "spread_investigate_limit": 0.06,
            "open_interest_investigate_minimum": 200,
            "daily_volume_investigate_minimum": 50,
            "iv_percentile_support_maximum": 0.40,
            "iv_vs_historical_median_support_maximum": 0.0,
            "implied_realized_gap_support_maximum": 0.0,
            "minimum_volatility_support_signals": 2,
            "long_call_upside_skew_maximum": 0.015,
            "long_call_upside_curvature_maximum": 0.025,
            "long_put_downside_skew_maximum": 0.025,
            "long_put_downside_curvature_maximum": 0.035,
            "required_valuation_time": "holding_horizon",
            "long_call_target_underlying_move": 0.10,
            "long_put_target_underlying_move": -0.10,
            "long_straddle_downside_target_underlying_move": -0.10,
            "long_straddle_upside_target_underlying_move": 0.10,
            "target_iv_change": 0.0,
            "volatility_crush_underlying_move": 0.0,
            "volatility_crush_iv_change": -0.20,
            "scenario_relative_tolerance": 1e-9,
            "scenario_absolute_tolerance": 1e-12,
        }
        self.assertEqual(dataclasses.asdict(policy), expected)

    def test_frozen_and_string_normalization(self) -> None:
        policy = ScreeningPolicy(
            policy_id="  family  ",
            policy_version="  version  ",
            required_valuation_time="  HOLDING_HORIZON  ",
        )
        self.assertEqual(policy.policy_id, "family")
        self.assertEqual(policy.policy_version, "version")
        self.assertEqual(policy.required_valuation_time, "holding_horizon")
        with self.assertRaises(FrozenInstanceError):
            policy.policy_version = "changed"  # type: ignore[misc]

    def test_explicit_approved_defaults_with_default_identity_succeed(self) -> None:
        default_values = dataclasses.asdict(ScreeningPolicy())
        self.assertEqual(ScreeningPolicy(**default_values), ScreeningPolicy())

    def test_modified_rule_categories_cannot_use_approved_identity(self) -> None:
        modified_rules = (
            {"maximum_loss_hard_limit": 0.06},
            {"maximum_loss_investigate_limit": 0.03},
            {"iv_percentile_support_maximum": 0.41},
            {"long_call_upside_skew_maximum": 0.016},
            {"target_iv_change": 0.10},
            {"scenario_relative_tolerance": 2e-9},
        )
        for overrides in modified_rules:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                ScreeningPolicy(**overrides)

        normalized = ScreeningPolicy(required_valuation_time=" HOLDING_HORIZON ")
        self.assertEqual(normalized, ScreeningPolicy())

    def test_custom_rule_set_requires_and_retains_custom_identity(self) -> None:
        policy = build_test_policy(
            "maximum-loss-custom",
            maximum_loss_hard_limit=0.06,
        )
        self.assertEqual(policy.policy_id, "synthetic-screening-test-maximum-loss-custom")
        self.assertEqual(policy.policy_version, "test-1")
        self.assertEqual(policy.maximum_loss_hard_limit, 0.06)
        with self.assertRaises(FrozenInstanceError):
            policy.maximum_loss_hard_limit = 0.07  # type: ignore[misc]

    def test_decisions_retain_each_actual_custom_policy_identity(self) -> None:
        candidate = build_screening_candidate()
        first_policy = build_test_policy(
            "identity-first",
            minimum_volatility_support_signals=1,
        )
        second_policy = build_test_policy(
            "identity-second",
            minimum_volatility_support_signals=3,
        )
        first = screen_candidate(candidate, first_policy)
        second = screen_candidate(candidate, second_policy)
        self.assertEqual(
            (first.policy_id, first.policy_version),
            (first_policy.policy_id, first_policy.policy_version),
        )
        self.assertEqual(
            (second.policy_id, second.policy_version),
            (second_policy.policy_id, second_policy.policy_version),
        )
        self.assertNotEqual(first.policy_id, second.policy_id)
        self.assertNotEqual(first.policy_id, "synthetic-screening-v0.1")
        self.assertNotEqual(second.policy_id, "synthetic-screening-v0.1")

    def test_invalid_strings_and_types(self) -> None:
        for kwargs, exception in (
            ({"policy_id": 1}, TypeError),
            ({"policy_id": "  "}, ValueError),
            ({"policy_version": None}, TypeError),
            ({"required_valuation_time": 1}, TypeError),
            ({"maximum_loss_hard_limit": "0.05"}, TypeError),
            ({"open_interest_hard_minimum": 50.0}, TypeError),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(exception):
                ScreeningPolicy(**kwargs)  # type: ignore[arg-type]

    def test_boolean_numbers_and_nonfinite_values_rejected(self) -> None:
        for kwargs, exception in (
            ({"maximum_loss_hard_limit": True}, TypeError),
            ({"open_interest_hard_minimum": False}, TypeError),
            ({"minimum_volatility_support_signals": True}, TypeError),
            ({"spread_hard_limit": math.nan}, ValueError),
            ({"target_iv_change": math.inf}, ValueError),
            ({"scenario_absolute_tolerance": -math.inf}, ValueError),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(exception):
                ScreeningPolicy(**kwargs)

    def test_invalid_threshold_relationships_and_minimums(self) -> None:
        invalid = (
            {"maximum_loss_investigate_limit": 0.06},
            {"repeated_bet_investigate_limit": 0.16},
            {"spread_investigate_limit": 0.13},
            {"theta_burden_investigate_limit": 0.51},
            {"open_interest_investigate_minimum": 49},
            {"daily_volume_investigate_minimum": 9},
            {"open_interest_hard_minimum": -1},
            {"daily_volume_investigate_minimum": -1},
            {"maximum_loss_hard_limit": -0.01},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ScreeningPolicy(**kwargs)

    def test_invalid_volatility_count_scenario_signs_shocks_and_tolerances(self) -> None:
        invalid = (
            {"minimum_volatility_support_signals": 0},
            {"minimum_volatility_support_signals": 4},
            {"long_call_target_underlying_move": 0.0},
            {"long_put_target_underlying_move": 0.0},
            {"long_straddle_upside_target_underlying_move": -0.1},
            {"long_straddle_downside_target_underlying_move": 0.1},
            {"target_iv_change": -1.0},
            {"volatility_crush_underlying_move": -1.0},
            {"volatility_crush_iv_change": -1.0},
            {"scenario_relative_tolerance": -1e-9},
            {"scenario_absolute_tolerance": -1e-12},
            {"required_valuation_time": "immediate"},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ScreeningPolicy(**kwargs)


class ScreeningDecisionTests(unittest.TestCase):
    def test_normalization_and_frozen_object(self) -> None:
        decision = ScreeningDecision(
            CandidateState.REJECT,
            [R.MAX_LOSS_HARD_LIMIT_EXCEEDED],
            "  family  ",
            "  1  ",
        )
        self.assertEqual(decision.reason_codes, (R.MAX_LOSS_HARD_LIMIT_EXCEEDED,))
        self.assertEqual(decision.policy_id, "family")
        self.assertEqual(decision.policy_version, "1")
        with self.assertRaises(FrozenInstanceError):
            decision.policy_id = "changed"  # type: ignore[misc]

    def test_invalid_primary_values(self) -> None:
        cases = (
            (("watch", [R.MAX_LOSS_ABOVE_INVESTIGATE_LIMIT], "p", "v"), TypeError),
            ((CandidateState.WATCH, "reason", "p", "v"), TypeError),
            ((CandidateState.WATCH, [], "p", "v"), ValueError),
            ((CandidateState.WATCH, ["reason"], "p", "v"), TypeError),
            ((CandidateState.WATCH, [R.MAX_LOSS_ABOVE_INVESTIGATE_LIMIT], "", "v"), ValueError),
        )
        for args, exception in cases:
            with self.subTest(args=args), self.assertRaises(exception):
                ScreeningDecision(*args)  # type: ignore[arg-type]

    def test_duplicate_mixed_and_noncanonical_reasons_rejected(self) -> None:
        invalid = (
            (
                CandidateState.WATCH,
                [
                    R.MAX_LOSS_ABOVE_INVESTIGATE_LIMIT,
                    R.MAX_LOSS_ABOVE_INVESTIGATE_LIMIT,
                ],
            ),
            (
                CandidateState.WATCH,
                [R.MAX_LOSS_ABOVE_INVESTIGATE_LIMIT, R.MISSING_COSTS],
            ),
            (
                CandidateState.WATCH,
                [
                    R.SPREAD_ABOVE_INVESTIGATE_LIMIT,
                    R.MAX_LOSS_ABOVE_INVESTIGATE_LIMIT,
                ],
            ),
        )
        for state, reasons in invalid:
            with self.subTest(reasons=reasons), self.assertRaises(ValueError):
                ScreeningDecision(state, reasons, "p", "v")

    def test_investigate_requires_exact_complete_tuple(self) -> None:
        ScreeningDecision(
            CandidateState.INVESTIGATE,
            INVESTIGATE_REASON_ORDER,
            "p",
            "v",
        )
        for reasons in (
            INVESTIGATE_REASON_ORDER[:-1],
            INVESTIGATE_REASON_ORDER + (R.MAX_LOSS_HARD_LIMIT_EXCEEDED,),
        ):
            with self.subTest(reasons=reasons), self.assertRaises(ValueError):
                ScreeningDecision(CandidateState.INVESTIGATE, reasons, "p", "v")


class ScreeningCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ScreeningPolicy()

    def test_input_validation_determinism_and_immutability(self) -> None:
        candidate = build_screening_candidate()
        with self.assertRaises(TypeError):
            screen_candidate("candidate", self.policy)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            screen_candidate(candidate, "policy")  # type: ignore[arg-type]
        before = repr(candidate)
        first = screen_candidate(candidate, self.policy)
        second = screen_candidate(candidate, self.policy)
        self.assertEqual(first, second)
        self.assertEqual(repr(candidate), before)

    def test_candidate_state_rationale_evidence_and_disclosures_are_ignored(self) -> None:
        watch = build_screening_candidate(
            supplied_state=CandidateState.WATCH,
            state_rationale="First rationale.",
            missing_data=("Disclosure only.",),
        )
        reject = build_screening_candidate(
            supplied_state=CandidateState.REJECT,
            state_rationale="Different rationale.",
            missing_data=("Different disclosure.",),
        )
        self.assertEqual(
            screen_candidate(watch, self.policy),
            screen_candidate(reject, self.policy),
        )
        self.assertIs(
            screen_candidate(watch, self.policy).proposed_state,
            CandidateState.INVESTIGATE,
        )

    def test_all_structure_types_investigate_with_exact_reasons(self) -> None:
        for structure_type in ("long_call", "long_put", "long_straddle"):
            with self.subTest(structure_type=structure_type):
                decision = screen_candidate(
                    build_screening_candidate(structure_type), self.policy
                )
                self.assertIs(decision.proposed_state, CandidateState.INVESTIGATE)
                self.assertEqual(decision.reason_codes, INVESTIGATE_REASON_ORDER)

    def test_decision_has_only_approved_fields_and_no_hidden_score(self) -> None:
        decision = screen_candidate(build_screening_candidate(), self.policy)
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(decision)),
            ("proposed_state", "reason_codes", "policy_id", "policy_version"),
        )
        for forbidden in (
            "score",
            "probability",
            "expected_return",
            "ranking",
            "position_size",
            "sizing",
            "recommendation",
            "diagnostics",
        ):
            self.assertFalse(hasattr(decision, forbidden))

    def test_final_state_reason_isolation_and_policy_identity(self) -> None:
        policy = build_test_policy("final-state-isolation")
        cases = (
            (
                build_screening_candidate(
                    assumed_portfolio_value=40_000.0,
                    cost_overrides={"repeated_bet_count": 1},
                ),
                CandidateState.REJECT,
                REJECT_REASON_ORDER,
            ),
            (
                build_screening_candidate(omit=("costs",)),
                CandidateState.DATA_INSUFFICIENT,
                DATA_INSUFFICIENT_REASON_ORDER,
            ),
            (
                build_screening_candidate(spread_percentage=0.07),
                CandidateState.WATCH,
                WATCH_REASON_ORDER,
            ),
            (
                build_screening_candidate(),
                CandidateState.INVESTIGATE,
                INVESTIGATE_REASON_ORDER,
            ),
        )
        for candidate, state, group in cases:
            with self.subTest(state=state):
                decision = screen_candidate(candidate, policy)
                self.assertIs(decision.proposed_state, state)
                self.assertTrue(all(reason in group for reason in decision.reason_codes))
                if state is CandidateState.INVESTIGATE:
                    self.assertEqual(decision.reason_codes, INVESTIGATE_REASON_ORDER)
                self.assertEqual(decision.policy_id, policy.policy_id)
                self.assertEqual(decision.policy_version, policy.policy_version)


class RejectDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ScreeningPolicy()

    def assert_reject(self, candidate, reasons) -> None:
        decision = screen_candidate(candidate, self.policy)
        self.assertIs(decision.proposed_state, CandidateState.REJECT)
        self.assertEqual(decision.reason_codes, reasons)

    def test_each_hard_threshold_reason_is_isolated(self) -> None:
        cases = (
            (
                build_screening_candidate(
                    assumed_portfolio_value=40_000.0,
                    cost_overrides={"repeated_bet_count": 1},
                ),
                R.MAX_LOSS_HARD_LIMIT_EXCEEDED,
            ),
            (
                build_screening_candidate(
                    cost_overrides={"repeated_bet_count": 8}
                ),
                R.REPEATED_BET_HARD_LIMIT_EXCEEDED,
            ),
            (
                build_screening_candidate(spread_percentage=0.13),
                R.SPREAD_HARD_LIMIT_EXCEEDED,
            ),
            (
                build_screening_candidate(
                    liquidity_overrides={"minimum_leg_open_interest": 49}
                ),
                R.OPEN_INTEREST_HARD_MINIMUM_FAILED,
            ),
            (
                build_screening_candidate(
                    liquidity_overrides={"minimum_leg_daily_volume": 9}
                ),
                R.DAILY_VOLUME_HARD_MINIMUM_FAILED,
            ),
            (
                build_screening_candidate(cost_overrides={"theta_per_day": -101.0}),
                R.THETA_BURDEN_HARD_LIMIT_EXCEEDED,
            ),
        )
        for candidate, reason in cases:
            with self.subTest(reason=reason):
                self.assert_reject(candidate, (reason,))

    def test_zero_and_negative_target_pnl_reject(self) -> None:
        for pnl in (0.0, -1.0):
            with self.subTest(pnl=pnl):
                self.assert_reject(
                    build_screening_candidate(
                        scenario_pnl_overrides={"target": pnl}
                    ),
                    (R.TARGET_MOVE_SCENARIO_NOT_PROFITABLE,),
                )

    def test_multiple_reasons_are_canonical_and_isolated(self) -> None:
        candidate = build_screening_candidate(
            assumed_portfolio_value=40_000.0,
            cost_overrides={"repeated_bet_count": 8, "theta_per_day": -101.0},
            spread_percentage=0.13,
            liquidity_overrides={
                "minimum_leg_open_interest": 49,
                "minimum_leg_daily_volume": 9,
            },
            scenario_pnl_overrides={"target": 0.0},
            omit=("volatility", "tail", "crush"),
        )
        self.assert_reject(candidate, REJECT_REASON_ORDER)

    def test_known_reject_overrides_missing_inputs(self) -> None:
        candidate = build_screening_candidate(
            assumed_portfolio_value=40_000.0,
            cost_overrides={"repeated_bet_count": 1},
            omit=("volatility", "tail", "target", "crush"),
        )
        self.assert_reject(candidate, (R.MAX_LOSS_HARD_LIMIT_EXCEEDED,))

    def test_straddle_target_failure_and_missing_side(self) -> None:
        candidate = build_screening_candidate(
            "long_straddle",
            omit=("upside_target",),
            scenario_pnl_overrides={"downside_target": 0.0},
        )
        self.assert_reject(candidate, (R.TARGET_MOVE_SCENARIO_NOT_PROFITABLE,))

    def test_two_failed_straddle_targets_emit_one_reason(self) -> None:
        candidate = build_screening_candidate(
            "long_straddle",
            scenario_pnl_overrides={
                "downside_target": 0.0,
                "upside_target": -1.0,
            },
        )
        self.assert_reject(candidate, (R.TARGET_MOVE_SCENARIO_NOT_PROFITABLE,))


class DataInsufficientDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ScreeningPolicy()

    def test_each_missing_reason_is_isolated(self) -> None:
        cases = (
            (("costs",), R.MISSING_COSTS),
            (("liquidity",), R.MISSING_LIQUIDITY),
            (("volatility",), R.MISSING_VOLATILITY_ENVIRONMENT),
            (("tail",), R.MISSING_STRUCTURE_EXPIRATION_TAIL_SLICE),
            (("target",), R.MISSING_TARGET_MOVE_SCENARIO),
            (("crush",), R.MISSING_VOLATILITY_CRUSH_SCENARIO),
        )
        for omitted, reason in cases:
            with self.subTest(reason=reason):
                decision = screen_candidate(
                    build_screening_candidate(omit=omitted), self.policy
                )
                self.assertIs(
                    decision.proposed_state, CandidateState.DATA_INSUFFICIENT
                )
                self.assertEqual(decision.reason_codes, (reason,))

    def test_multiple_missing_reasons_are_canonical_and_isolated(self) -> None:
        candidate = build_screening_candidate(
            omit=("costs", "liquidity", "volatility", "tail", "target", "crush")
        )
        decision = screen_candidate(candidate, self.policy)
        self.assertIs(decision.proposed_state, CandidateState.DATA_INSUFFICIENT)
        self.assertEqual(decision.reason_codes, DATA_INSUFFICIENT_REASON_ORDER)

    def test_straddle_missing_target_sides_use_one_stable_code(self) -> None:
        for omitted in (
            ("downside_target",),
            ("upside_target",),
            ("downside_target", "upside_target"),
        ):
            with self.subTest(omitted=omitted):
                decision = screen_candidate(
                    build_screening_candidate("long_straddle", omit=omitted),
                    self.policy,
                )
                self.assertEqual(
                    decision.reason_codes, (R.MISSING_TARGET_MOVE_SCENARIO,)
                )

    def test_missing_data_disclosure_does_not_change_complete_result(self) -> None:
        candidate = build_screening_candidate(
            missing_data=("Report disclosure is intentionally non-empty.",)
        )
        self.assertIs(
            screen_candidate(candidate, self.policy).proposed_state,
            CandidateState.INVESTIGATE,
        )


class WatchDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ScreeningPolicy()

    def assert_watch(self, candidate, reasons) -> None:
        decision = screen_candidate(candidate, self.policy)
        self.assertIs(decision.proposed_state, CandidateState.WATCH)
        self.assertEqual(decision.reason_codes, reasons)

    def test_each_soft_gate_reason_is_isolated(self) -> None:
        cases = (
            (
                build_screening_candidate(
                    assumed_portfolio_value=80_000.0,
                    cost_overrides={"repeated_bet_count": 1},
                ),
                R.MAX_LOSS_ABOVE_INVESTIGATE_LIMIT,
            ),
            (
                build_screening_candidate(
                    cost_overrides={"repeated_bet_count": 4}
                ),
                R.REPEATED_BET_ABOVE_INVESTIGATE_LIMIT,
            ),
            (
                build_screening_candidate(spread_percentage=0.07),
                R.SPREAD_ABOVE_INVESTIGATE_LIMIT,
            ),
            (
                build_screening_candidate(
                    liquidity_overrides={"minimum_leg_open_interest": 199}
                ),
                R.OPEN_INTEREST_BELOW_INVESTIGATE_MINIMUM,
            ),
            (
                build_screening_candidate(
                    liquidity_overrides={"minimum_leg_daily_volume": 49}
                ),
                R.DAILY_VOLUME_BELOW_INVESTIGATE_MINIMUM,
            ),
            (
                build_screening_candidate(cost_overrides={"theta_per_day": -51.0}),
                R.THETA_BURDEN_ABOVE_INVESTIGATE_LIMIT,
            ),
            (
                build_screening_candidate(
                    environment_overrides={
                        "iv_percentile": 0.50,
                        "historical_median_atm_iv": 0.19,
                        "matched_realized_volatility": 0.19,
                    }
                ),
                R.VOLATILITY_ENVIRONMENT_NOT_SUPPORTIVE,
            ),
            (
                build_screening_candidate(
                    tail_overrides={"call_25_delta_iv": 0.22}
                ),
                R.TAIL_PRICING_NOT_SUPPORTIVE,
            ),
        )
        for candidate, reason in cases:
            with self.subTest(reason=reason):
                self.assert_watch(candidate, (reason,))

    def test_multiple_watch_reasons_are_canonical_and_isolated(self) -> None:
        candidate = build_screening_candidate(
            assumed_portfolio_value=80_000.0,
            cost_overrides={"repeated_bet_count": 4, "theta_per_day": -51.0},
            spread_percentage=0.07,
            liquidity_overrides={
                "minimum_leg_open_interest": 199,
                "minimum_leg_daily_volume": 49,
            },
            environment_overrides={
                "iv_percentile": 0.50,
                "historical_median_atm_iv": 0.19,
                "matched_realized_volatility": 0.19,
            },
            tail_overrides={"call_25_delta_iv": 0.22},
        )
        self.assert_watch(candidate, WATCH_REASON_ORDER)


class VolatilityAndTailLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ScreeningPolicy()

    def test_volatility_signal_counts_and_positive_gap(self) -> None:
        cases = (
            ({}, CandidateState.INVESTIGATE),
            (
                {"matched_realized_volatility": 0.19},
                CandidateState.INVESTIGATE,
            ),
            (
                {
                    "iv_percentile": 0.50,
                    "historical_median_atm_iv": 0.22,
                    "matched_realized_volatility": 0.19,
                },
                CandidateState.WATCH,
            ),
            (
                {
                    "iv_percentile": 0.50,
                    "historical_median_atm_iv": 0.19,
                    "matched_realized_volatility": 0.19,
                },
                CandidateState.WATCH,
            ),
        )
        for overrides, state in cases:
            with self.subTest(overrides=overrides):
                decision = screen_candidate(
                    build_screening_candidate(environment_overrides=overrides),
                    self.policy,
                )
                self.assertIs(decision.proposed_state, state)

    def test_zero_gap_equality_passes_and_minimum_count_controls_result(self) -> None:
        candidate = build_screening_candidate(
            environment_overrides={
                "iv_percentile": 0.50,
                "historical_median_atm_iv": 0.19,
                "matched_realized_volatility": 0.20,
            }
        )
        self.assertIs(
            screen_candidate(
                candidate,
                build_test_policy(
                    "volatility-minimum-one",
                    minimum_volatility_support_signals=1,
                ),
            ).proposed_state,
            CandidateState.INVESTIGATE,
        )
        self.assertIs(
            screen_candidate(candidate, self.policy).proposed_state,
            CandidateState.WATCH,
        )

    def test_structure_specific_tail_logic_and_irrelevant_side(self) -> None:
        call_with_bad_put = build_screening_candidate(
            "long_call",
            tail_overrides={"put_25_delta_iv": 0.30, "put_10_delta_iv": 0.40},
        )
        put_with_bad_call = build_screening_candidate(
            "long_put",
            tail_overrides={"call_25_delta_iv": 0.30, "call_10_delta_iv": 0.40},
        )
        for candidate in (call_with_bad_put, put_with_bad_call):
            self.assertIs(
                screen_candidate(candidate, self.policy).proposed_state,
                CandidateState.INVESTIGATE,
            )
        straddle = build_screening_candidate(
            "long_straddle", tail_overrides={"call_25_delta_iv": 0.22}
        )
        self.assertIs(
            screen_candidate(straddle, self.policy).proposed_state,
            CandidateState.WATCH,
        )

    def test_tail_threshold_equalities_pass_and_above_values_fail(self) -> None:
        equal_tail = {
            "call_25_delta_iv": 0.215,
            "call_10_delta_iv": 0.240,
            "put_25_delta_iv": 0.225,
            "put_10_delta_iv": 0.260,
        }
        self.assertIs(
            screen_candidate(
                build_screening_candidate("long_straddle", tail_overrides=equal_tail),
                self.policy,
            ).proposed_state,
            CandidateState.INVESTIGATE,
        )
        for structure_type, overrides in (
            ("long_call", {"call_25_delta_iv": 0.216}),
            ("long_call", {"call_10_delta_iv": 0.236}),
            ("long_put", {"put_25_delta_iv": 0.226}),
            ("long_put", {"put_10_delta_iv": 0.256}),
        ):
            with self.subTest(structure_type=structure_type, overrides=overrides):
                self.assertIs(
                    screen_candidate(
                        build_screening_candidate(
                            structure_type, tail_overrides=overrides
                        ),
                        self.policy,
                    ).proposed_state,
                    CandidateState.WATCH,
                )

    def test_skew_percentile_does_not_affect_state(self) -> None:
        low = build_screening_candidate(tail_overrides={"skew_percentile": 0.0})
        high = build_screening_candidate(tail_overrides={"skew_percentile": 1.0})
        self.assertEqual(
            screen_candidate(low, self.policy), screen_candidate(high, self.policy)
        )


class BoundaryAndScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ScreeningPolicy()

    def test_hard_limit_equalities_do_not_reject(self) -> None:
        entry_cost = 2_102.0
        cases = (
            build_screening_candidate(
                assumed_portfolio_value=entry_cost / 0.05,
                cost_overrides={"repeated_bet_count": 1},
            ),
            build_screening_candidate(
                assumed_portfolio_value=entry_cost * 3 / 0.15
            ),
            build_screening_candidate(spread_percentage=0.12),
            build_screening_candidate(
                liquidity_overrides={"minimum_leg_open_interest": 50}
            ),
            build_screening_candidate(
                liquidity_overrides={"minimum_leg_daily_volume": 10}
            ),
            build_screening_candidate(cost_overrides={"theta_per_day": -100.0}),
        )
        for candidate in cases:
            with self.subTest(candidate=candidate):
                self.assertIsNot(
                    screen_candidate(candidate, self.policy).proposed_state,
                    CandidateState.REJECT,
                )

    def test_investigate_gate_equalities_pass_their_specific_gates(self) -> None:
        entry_cost = 2_102.0
        candidates_and_absent_reasons = (
            (
                build_screening_candidate(
                    assumed_portfolio_value=entry_cost / 0.025
                ),
                R.MAX_LOSS_ABOVE_INVESTIGATE_LIMIT,
            ),
            (
                build_screening_candidate(
                    assumed_portfolio_value=entry_cost * 3 / 0.08
                ),
                R.REPEATED_BET_ABOVE_INVESTIGATE_LIMIT,
            ),
            (
                build_screening_candidate(spread_percentage=0.06),
                R.SPREAD_ABOVE_INVESTIGATE_LIMIT,
            ),
            (
                build_screening_candidate(
                    liquidity_overrides={"minimum_leg_open_interest": 200}
                ),
                R.OPEN_INTEREST_BELOW_INVESTIGATE_MINIMUM,
            ),
            (
                build_screening_candidate(
                    liquidity_overrides={"minimum_leg_daily_volume": 50}
                ),
                R.DAILY_VOLUME_BELOW_INVESTIGATE_MINIMUM,
            ),
            (
                build_screening_candidate(cost_overrides={"theta_per_day": -50.0}),
                R.THETA_BURDEN_ABOVE_INVESTIGATE_LIMIT,
            ),
            (
                build_screening_candidate(
                    environment_overrides={
                        "iv_percentile": 0.40,
                        "historical_median_atm_iv": 0.20,
                        "matched_realized_volatility": 0.20,
                    }
                ),
                R.VOLATILITY_ENVIRONMENT_NOT_SUPPORTIVE,
            ),
        )
        for candidate, absent_reason in candidates_and_absent_reasons:
            with self.subTest(absent_reason=absent_reason):
                decision = screen_candidate(candidate, self.policy)
                self.assertNotIn(absent_reason, decision.reason_codes)

    def test_valuation_time_and_tolerance_matching(self) -> None:
        immediate = build_screening_candidate(
            scenario_value_overrides={"target": (0.10, 0.0, 500.0, "immediate")}
        )
        expiration = build_screening_candidate(
            scenario_value_overrides={"target": (0.10, 0.0, 500.0, "expiration")}
        )
        within = build_screening_candidate(
            scenario_value_overrides={
                "target": (0.10 + 5e-13, 0.0, 500.0, "holding_horizon")
            }
        )
        outside = build_screening_candidate(
            scenario_value_overrides={
                "target": (0.10 + 1e-6, 0.0, 500.0, "holding_horizon")
            }
        )
        for candidate in (immediate, expiration, outside):
            self.assertEqual(
                screen_candidate(candidate, self.policy).reason_codes,
                (R.MISSING_TARGET_MOVE_SCENARIO,),
            )
        self.assertIs(
            screen_candidate(within, self.policy).proposed_state,
            CandidateState.INVESTIGATE,
        )

    def test_ambiguous_tolerance_matches_raise(self) -> None:
        candidate = build_screening_candidate(
            extra_scenarios=((0.10 + 5e-13, 0.0, 600.0, "holding_horizon"),)
        )
        with self.assertRaises(ValueError):
            screen_candidate(candidate, self.policy)

    def test_duplicate_crush_match_raises(self) -> None:
        candidate = build_screening_candidate(
            extra_scenarios=((5e-13, -0.20, -400.0, "holding_horizon"),)
        )
        with self.assertRaises(ValueError):
            screen_candidate(candidate, self.policy)

    def test_ambiguity_precedes_hard_cost_and_liquidity_rejections(self) -> None:
        duplicate_target_with_cost_failure = build_screening_candidate(
            assumed_portfolio_value=40_000.0,
            cost_overrides={"repeated_bet_count": 1},
            extra_scenarios=((0.10 + 5e-13, 0.0, 600.0, "holding_horizon"),),
        )
        duplicate_crush_with_spread_failure = build_screening_candidate(
            spread_percentage=0.13,
            extra_scenarios=((5e-13, -0.20, -400.0, "holding_horizon"),),
        )
        for candidate in (
            duplicate_target_with_cost_failure,
            duplicate_crush_with_spread_failure,
        ):
            with self.assertRaises(ValueError):
                screen_candidate(candidate, self.policy)

    def test_ambiguity_precedes_missing_and_nonprofitable_scenarios(self) -> None:
        duplicate_with_missing_crush = build_screening_candidate(
            omit=("crush",),
            extra_scenarios=((0.10 + 5e-13, 0.0, 600.0, "holding_horizon"),),
        )
        duplicate_nonprofitable_target = build_screening_candidate(
            scenario_pnl_overrides={"target": 0.0},
            extra_scenarios=((0.10 + 5e-13, 0.0, 600.0, "holding_horizon"),),
        )
        for candidate in (duplicate_with_missing_crush, duplicate_nonprofitable_target):
            with self.assertRaises(ValueError):
                screen_candidate(candidate, self.policy)

    def test_straddle_ambiguity_on_either_target_side_raises(self) -> None:
        for duplicate in (
            (-0.10 + 5e-13, 0.0, 600.0, "holding_horizon"),
            (0.10 + 5e-13, 0.0, 600.0, "holding_horizon"),
        ):
            with self.subTest(duplicate=duplicate):
                candidate = build_screening_candidate(
                    "long_straddle", extra_scenarios=(duplicate,)
                )
                with self.assertRaises(ValueError):
                    screen_candidate(candidate, self.policy)

    def test_outside_tolerance_and_nonrequired_times_are_not_ambiguous(self) -> None:
        candidate = build_screening_candidate(
            extra_scenarios=(
                (0.10 + 1e-6, 0.0, 600.0, "holding_horizon"),
                (0.10, 0.0, 600.0, "immediate"),
                (0.10, 0.0, 600.0, "expiration"),
            )
        )
        self.assertIs(
            screen_candidate(candidate, self.policy).proposed_state,
            CandidateState.INVESTIGATE,
        )

    def test_negative_crush_is_allowed_and_target_is_strictly_positive(self) -> None:
        self.assertIs(
            screen_candidate(build_screening_candidate(), self.policy).proposed_state,
            CandidateState.INVESTIGATE,
        )
        zero_target = build_screening_candidate(
            scenario_pnl_overrides={"target": 0.0}
        )
        self.assertIs(
            screen_candidate(zero_target, self.policy).proposed_state,
            CandidateState.REJECT,
        )


if __name__ == "__main__":
    unittest.main()
