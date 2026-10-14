"""Focused tests for the M3 host-owned Standard Research Profile."""

import datetime
import decimal
import inspect
import json
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError, replace

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter import core_research
from convexity_hunter.core_application import (
    CoreCaseContext,
    CoreCaseRecord,
    CoreDirectResult,
    CoreOperationalBounds,
)
from convexity_hunter.core_presentation import report
from convexity_hunter.host_profile import (
    APPROVED_STANDARD_RESEARCH_PROFILE,
    CONDITIONAL_STANDARD_PAYOFF_APPROVAL_ID,
    COST_LEDGER_GAP,
    SENSITIVITY_GAP,
    STANDARD_RESEARCH_PROFILE,
    StandardResearchProfile,
    _profile_for_snapshot,
    create_core_research_policy,
)
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority


D = decimal.Decimal


def make_structure(multiplier=137, *, quantity=1, ask="1.25", currency="USD"):
    provenance = core_research.CoreProvenance(None, "test structure provenance")
    leg = core_research.CoreLeg(
        leg_id="call-1",
        underlying="XYZ",
        currency=currency,
        option_type=core_research.CoreOptionType.CALL,
        strike=D("100"),
        expiration=datetime.date(2031, 1, 15),
        quantity=quantity,
        contract_multiplier=multiplier,
        ask_per_underlying_unit=D(ask),
        ask_authority=core_research.CoreAskAuthority.INDICATIVE_ONLY,
        description="verified structure leg",
        provenance=provenance,
    )
    return core_research.CoreStructure(
        legs=(leg,),
        description="verified structure",
        provenance=provenance,
    )


def make_straddle(
    *,
    strike="2",
    call_ask="1.20",
    put_ask="0.80",
    quantity=2,
    multiplier=100,
):
    provenance = core_research.CoreProvenance(None, "test straddle provenance")
    common = {
        "underlying": "XYZ",
        "currency": "USD",
        "strike": D(strike),
        "expiration": datetime.date(2031, 1, 15),
        "quantity": quantity,
        "contract_multiplier": multiplier,
        "ask_authority": core_research.CoreAskAuthority.INDICATIVE_ONLY,
        "provenance": provenance,
    }
    call = core_research.CoreLeg(
        leg_id="call-1",
        option_type=core_research.CoreOptionType.CALL,
        ask_per_underlying_unit=None if call_ask is None else D(call_ask),
        description="verified call leg",
        **common,
    )
    put = core_research.CoreLeg(
        leg_id="put-1",
        option_type=core_research.CoreOptionType.PUT,
        ask_per_underlying_unit=None if put_ask is None else D(put_ask),
        description="verified put leg",
        **common,
    )
    return core_research.CoreStructure(
        legs=(call, put), description="verified long straddle", provenance=provenance
    )


def make_bounds():
    return CoreOperationalBounds(
        max_submissions=8,
        max_hypotheses=8,
        max_browser_rows=100,
        max_cases=100,
        quote_timeout_seconds=1.0,
    )


def make_policy(authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH):
    return create_core_research_policy(
        APPROVED_STANDARD_RESEARCH_PROFILE,
        evaluation_date=datetime.date(2030, 1, 1),
        maturity_authority=authority,
        bounds=make_bounds(),
    )


class StandardResearchProfileTests(unittest.TestCase):
    def test_profile_is_immutable_and_has_exact_approved_values(self):
        profile = STANDARD_RESEARCH_PROFILE
        self.assertIs(profile, APPROVED_STANDARD_RESEARCH_PROFILE)
        self.assertIsInstance(profile, StandardResearchProfile)
        self.assertEqual(profile.profile_id, "standard-research-profile")
        self.assertEqual(profile.version, "v0.4")
        self.assertEqual(profile.currency, "USD")
        self.assertEqual(profile.portfolio_value, D("100000"))
        self.assertEqual(profile.maximum_single_loss_fraction, D("0.005"))
        self.assertEqual(profile.maximum_repeated_loss_fraction, D("0.015"))
        self.assertEqual(profile.repeat_count, 3)
        self.assertEqual(profile.quantity, 1)
        with self.assertRaises(FrozenInstanceError):
            profile.quantity = 2  # type: ignore[misc]

    def test_snapshot_is_exact_sanitized_json(self):
        snapshot = STANDARD_RESEARCH_PROFILE.snapshot()
        encoded = json.dumps(snapshot, sort_keys=True)
        decoded = json.loads(encoded)
        self.assertEqual(decoded, snapshot)
        self.assertEqual(
            set(snapshot),
            {
                "profile_id",
                "version",
                "currency",
                "portfolio_value",
                "maximum_single_loss_fraction",
                "maximum_repeated_loss_fraction",
                "repeat_count",
                "quantity",
                "authorized_source",
                "payoff_approval",
                "cash_sensitivity_policy",
                "strategy_governance",
                "conditional_entry_fee_policy",
            },
        )
        self.assertEqual(snapshot["portfolio_value"], "100000")
        self.assertEqual(snapshot["maximum_single_loss_fraction"], "0.005")
        self.assertEqual(snapshot["maximum_repeated_loss_fraction"], "0.015")
        self.assertEqual(snapshot["repeat_count"], 3)
        self.assertEqual(snapshot["quantity"], 1)
        self.assertEqual(snapshot["version"], "v0.4")
        self.assertEqual(
            snapshot["cash_sensitivity_policy"],
            {
                "policy_id": "core-cash-sensitivity-policy",
                "version": "v0.1",
                "observed_position_ask_basis": "sum(ask_per_underlying_unit*quantity*contract_multiplier)",
                "conditional_premium_factor": "1.10",
                "required_unknown_component_ids": [
                    "entry_fees",
                    "strategy_dependent_funding",
                    "strategy_dependent_exit",
                    "strategy_dependent_settlement",
                ],
                "sensitivity": {
                    "grammar": "long_straddle_equal_quantity_multiplier_same_underlying_strike_expiration",
                    "terminal_formula": "strike+x*baseline_sum_per_underlying_unit_asks",
                    "x_offsets": [-2, -1, 0, 1, 2],
                    "per_leg_ask_factors": ["1", "1.10", "1.25"],
                    "negative_terminal_price": "NOT_APPLICABLE",
                },
            },
        )
        self.assertEqual(
            snapshot["authorized_source"]["source_id"],
            "standalone-mvp-architecture-v0.1",
        )
        self.assertEqual(
            snapshot["strategy_governance"],
            {
                "version": "v0.1",
                "funding_rule": "OWN_CASH_PREMIUM; MARGIN_FINANCING_PROHIBITED",
                "lifecycle_intent": "CLOSE_OR_ABANDON_BEFORE_EXPIRY",
                "exercise_rule": "EXERCISE_TO_STOCK_PROHIBITED",
                "execution_enforcement": "NOT_ESTABLISHED",
                "automatic_exercise_protection": "NOT_ESTABLISHED",
            },
        )
        self.assertEqual(
            snapshot["conditional_entry_fee_policy"],
            {
                "policy_id": "conditional-entry-fee-scenarios",
                "version": "v0.1",
                "source_url": "https://www.futuhk.com/hans/support/topic2_283",
                "verified_on": "2026-10-14",
                "currency": "USD",
                "scope": "US_LISTED_EQUITY_OPTIONS_ONLY",
                "applicability": "CONDITIONAL_NOT_VERIFIED",
                "account_tariff": "UNKNOWN",
                "security_type": "NOT_VERIFIED",
                "order_assumption": "one_buy_order_per_leg_wholly_filled_within_one_trading_day",
                "scenarios": [
                    {"scenario_id": "FIXED", "platform_fee_per_contract": "0.30"},
                    {
                        "scenario_id": "TIER_FIRST_50",
                        "platform_fee_per_contract": "0.60",
                        "prior_monthly_contracts": 0,
                        "maximum_total_order_quantity": 50,
                    },
                ],
                "commission": {
                    "minimum_per_leg": "1.99",
                    "ask_threshold": "0.10",
                    "rate_above_threshold_per_contract": "0.65",
                    "rate_at_or_below_threshold_per_contract": "0.15",
                },
                "other_buy_fees_per_contract": "0.2175",
                "partial_subtotal": "existing_1.10_conditional_premium_budget_plus_scenario_entry_fees",
                "rounding_rule": "NOT_VERIFIED",
                "not_included": [
                    "sell_side_charges",
                    "promotions",
                    "extra_services",
                    "index_option_surcharges",
                    "currency_conversion",
                    "future_tariff_changes",
                ],
            },
        )
        self.assertEqual(snapshot["authorized_source"]["frozen_commit"], "1adc636")
        self.assertNotIn("credential", encoded.lower())
        self.assertNotIn("token", encoded.lower())
        self.assertEqual(
            json.loads(STANDARD_RESEARCH_PROFILE.snapshot_json()), snapshot
        )

    def test_v03_snapshot_and_report_remain_historical(self):
        historical = StandardResearchProfile(version="v0.3")
        expected = StandardResearchProfile(version="v0.2").snapshot()
        expected["version"] = "v0.3"
        expected["strategy_governance"] = {
            "version": "v0.1",
            "funding_rule": "OWN_CASH_PREMIUM; MARGIN_FINANCING_PROHIBITED",
            "lifecycle_intent": "CLOSE_OR_ABANDON_BEFORE_EXPIRY",
            "exercise_rule": "EXERCISE_TO_STOCK_PROHIBITED",
            "execution_enforcement": "NOT_ESTABLISHED",
            "automatic_exercise_protection": "NOT_ESTABLISHED",
        }
        self.assertEqual(historical.snapshot(), expected)
        self.assertNotIn("conditional_entry_fee_policy", historical.snapshot())

        structure = make_straddle(quantity=1)
        request = historical.request_factory(
            case_id="case-v03-historical-report", structure=structure, context=None
        )
        result = core_research.evaluate_core_research(request)
        rendered = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=request,
                kernel_result=result,
                reasons=(),
                full_report="",
            )
        )
        self.assertIn("profile=standard-research-profile:v0.3", rendered)
        self.assertIn("策略治理意图（非执行控制）", rendered)
        self.assertIn(
            "actual_tariff=unknown; funding_strategy=not_assumed; no zero-cost inference",
            rendered,
        )
        self.assertNotIn("条件化买入开仓费用情景", rendered)

    def test_v04_conditional_entry_fee_golden_is_private_report_only(self):
        structure = make_straddle(quantity=1)
        request = STANDARD_RESEARCH_PROFILE.request_factory(
            case_id="case-v04-fee-golden", structure=structure, context=None
        )
        result = core_research.evaluate_core_research(request)
        direct_text = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=request,
                kernel_result=result,
                reasons=(),
                full_report="",
            )
        )
        context = CoreCaseContext(
            raw_input=None,
            maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
            core_structure=structure,
            kernel_request=request,
            kernel_result=result,
        )
        case_text = report(CoreCaseRecord(request.case_id, context, request, result, ()))
        fee_section = tuple(
            line
            for line in direct_text.splitlines()
            if line.startswith(("条件化买入开仓费用情景", "FIXED:", "TIER_FIRST_50:"))
        )
        self.assertEqual(
            fee_section,
            (
                "条件化买入开仓费用情景（仅v0.4详情展示，不写入CoreCostLedger）",
                "FIXED: entry_fee_USD=5.015; partial_subtotal_USD=225.015",
                "TIER_FIRST_50: entry_fee_USD=5.615; partial_subtotal_USD=225.615",
            ),
        )
        self.assertEqual(
            fee_section,
            tuple(
                line
                for line in case_text.splitlines()
                if line.startswith(
                    ("条件化买入开仓费用情景", "FIXED:", "TIER_FIRST_50:")
                )
            ),
        )
        self.assertIn("CONDITIONAL/NOT_VERIFIED", direct_text)
        self.assertIn(
            "own_cash_funding_research_intent=ADOPTED; funding_cost=UNKNOWN; no_zero_cost_or_execution_control_inference",
            direct_text,
        )
        self.assertIn("指数附加费未纳入，实际品种适用性未验证", direct_text)
        self.assertIn(
            "a=CoreLeg.ask_per_underlying_unit，单位USD/标的单位；不是头寸权利金或每张合约现金额。",
            direct_text,
        )
        self.assertIn("Q=sum(q_i)=2（不乘合约乘数）", direct_text)
        self.assertIn("entry_fees及资金/退出/结算仍为UNKNOWN", direct_text)
        self.assertIn("生存/可负担性未建立", direct_text)
        self.assertIn("处置: DATA_INSUFFICIENT_CORE", direct_text)
        self.assertIsNone(result.cash_ledger.conditional_total_upper_bound)
        self.assertEqual(
            tuple(item.component_id for item in request.cost_ledger.impact_components),
            (
                "entry_fees",
                "strategy_dependent_funding",
                "strategy_dependent_exit",
                "strategy_dependent_settlement",
            ),
        )
        self.assertTrue(
            all(
                item.status is core_research.CoreCostComponentStatus.UNKNOWN
                and item.upper_bound is None
                for item in request.cost_ledger.impact_components
            )
        )

    def test_v04_fee_threshold_quantity_and_low_precision_boundaries(self):
        threshold_structure = make_straddle(
            call_ask="0.10", put_ask="0.1001", quantity=4
        )
        threshold_request = STANDARD_RESEARCH_PROFILE.request_factory(
            case_id="case-v04-fee-threshold",
            structure=threshold_structure,
            context=None,
        )
        threshold_text = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=threshold_structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=threshold_request,
                kernel_result=core_research.evaluate_core_research(threshold_request),
                reasons=(),
                full_report="",
            )
        )
        self.assertIn("FIXED: entry_fee_USD=8.73;", threshold_text)
        self.assertIn("Q=sum(q_i)=8（不乘合约乘数）", threshold_text)

        over_tier_structure = make_structure(quantity=51, ask="0.10", multiplier=100)
        over_tier_request = STANDARD_RESEARCH_PROFILE.request_factory(
            case_id="case-v04-fee-over-tier",
            structure=over_tier_structure,
            context=None,
        )
        over_tier_text = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=over_tier_structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=over_tier_request,
                kernel_result=core_research.evaluate_core_research(over_tier_request),
                reasons=(),
                full_report="",
            )
        )
        self.assertIn("Q=sum(q_i)=51（不乘合约乘数）", over_tier_text)
        self.assertIn(
            "TIER_FIRST_50: unavailable[total_order_quantity_exceeds_50]",
            over_tier_text,
        )

        precise_structure = make_structure(
            multiplier=100,
            ask="0.12345678901234567890123456789",
        )
        with decimal.localcontext() as context:
            context.prec = 2
            precise_request = STANDARD_RESEARCH_PROFILE.request_factory(
                case_id="case-v04-low-precision",
                structure=precise_structure,
                context=None,
            )
            precise_text = report(
                CoreDirectResult(
                    raw_input=None,
                    core_structure=precise_structure,
                    exact_verifications=(),
                    native_quotes=(),
                    provider_references=(),
                    kernel_request=precise_request,
                    kernel_result=core_research.evaluate_core_research(precise_request),
                    reasons=(),
                    full_report="",
                )
            )
        self.assertIn(
            "FIXED: entry_fee_USD=2.5075; partial_subtotal_USD=16.0877467913580246791358024679",
            precise_text,
        )

    def test_v04_fee_unavailable_invalid_boolean_asks_and_forged_marker(self):
        missing_structure = make_straddle(put_ask=None, quantity=1)
        missing_request = STANDARD_RESEARCH_PROFILE.request_factory(
            case_id="case-v04-missing-ask", structure=missing_structure, context=None
        )
        missing_text = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=missing_structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=missing_request,
                kernel_result=core_research.evaluate_core_research(missing_request),
                reasons=(),
                full_report="",
            )
        )
        self.assertIn("FIXED: unavailable[invalid_or_missing_ask]", missing_text)
        self.assertNotIn("entry_fee_USD=", missing_text)

        valid_structure = make_structure()
        valid_request = STANDARD_RESEARCH_PROFILE.request_factory(
            case_id="case-v04-boolean-ask", structure=valid_structure, context=None
        )
        object.__setattr__(valid_structure.legs[0], "ask_per_underlying_unit", True)
        from convexity_hunter.core_presentation import _conditional_entry_fee_scenario_view

        invalid_view = _conditional_entry_fee_scenario_view(
            valid_request, STANDARD_RESEARCH_PROFILE
        )
        self.assertEqual(invalid_view.fixed.unavailable_reason, "invalid_or_missing_ask")
        self.assertIsNone(invalid_view.fixed.entry_fee)

        forged_snapshot = STANDARD_RESEARCH_PROFILE.snapshot()
        forged_snapshot["conditional_entry_fee_policy"]["scenarios"][1][
            "maximum_total_order_quantity"
        ] = True
        with self.assertRaises(ValueError):
            _profile_for_snapshot(forged_snapshot)
        altered = STANDARD_RESEARCH_PROFILE.snapshot()
        altered["conditional_entry_fee_policy"]["commission"][
            "ask_threshold"
        ] = "0.100"
        with self.assertRaises(ValueError):
            _profile_for_snapshot(altered)

        good_request = STANDARD_RESEARCH_PROFILE.request_factory(
            case_id="case-v04-forged-marker", structure=make_structure(), context=None
        )
        forged_request = replace(
            good_request,
            provenance=replace(
                good_request.provenance,
                description="core-request; profile_snapshot={}",
            ),
        )
        forged_result = core_research.evaluate_core_research(forged_request)
        forged_text = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=forged_request.structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=forged_request,
                kernel_result=forged_result,
                reasons=(),
                full_report="",
            )
        )
        self.assertNotIn("条件化买入开仓费用情景", forged_text)

    def test_v02_snapshot_factory_and_cash_report_remain_historical(self):
        historical = StandardResearchProfile(version="v0.2")
        historical_snapshot = {
            "authorized_source": {
                "basis": "user-approved-standard-research-profile",
                "frozen_commit": "1adc636",
                "source_id": "standalone-mvp-architecture-v0.1",
                "version": "v0.1",
            },
            "cash_sensitivity_policy": {
                "conditional_premium_factor": "1.10",
                "observed_position_ask_basis": "sum(ask_per_underlying_unit*quantity*contract_multiplier)",
                "policy_id": "core-cash-sensitivity-policy",
                "required_unknown_component_ids": [
                    "entry_fees",
                    "strategy_dependent_funding",
                    "strategy_dependent_exit",
                    "strategy_dependent_settlement",
                ],
                "sensitivity": {
                    "grammar": "long_straddle_equal_quantity_multiplier_same_underlying_strike_expiration",
                    "negative_terminal_price": "NOT_APPLICABLE",
                    "per_leg_ask_factors": ["1", "1.10", "1.25"],
                    "terminal_formula": "strike+x*baseline_sum_per_underlying_unit_asks",
                    "x_offsets": [-2, -1, 0, 1, 2],
                },
                "version": "v0.1",
            },
            "currency": "USD",
            "maximum_repeated_loss_fraction": "0.015",
            "maximum_single_loss_fraction": "0.005",
            "payoff_approval": {
                "limitations": [
                    "conditional standard-payoff geometry only",
                    "exact deliverable verification remains unestablished",
                    "indicative asks are non-executable and do not establish underpricing",
                ],
                "model_id": "conditional-standard-payoff",
                "model_version": "0.1",
            },
            "portfolio_value": "100000",
            "profile_id": "standard-research-profile",
            "quantity": 1,
            "repeat_count": 3,
            "version": "v0.2",
        }
        historical_snapshot_json = (
            '{"authorized_source":{"basis":"user-approved-standard-research-profile",'
            '"frozen_commit":"1adc636","source_id":"standalone-mvp-architecture-v0.1",'
            '"version":"v0.1"},"cash_sensitivity_policy":{"conditional_premium_factor":"1.10",'
            '"observed_position_ask_basis":"sum(ask_per_underlying_unit*quantity*contract_multiplier)",'
            '"policy_id":"core-cash-sensitivity-policy","required_unknown_component_ids":'
            '["entry_fees","strategy_dependent_funding","strategy_dependent_exit",'
            '"strategy_dependent_settlement"],"sensitivity":{"grammar":'
            '"long_straddle_equal_quantity_multiplier_same_underlying_strike_expiration",'
            '"negative_terminal_price":"NOT_APPLICABLE","per_leg_ask_factors":'
            '["1","1.10","1.25"],"terminal_formula":'
            '"strike+x*baseline_sum_per_underlying_unit_asks","x_offsets":[-2,-1,0,1,2]},'
            '"version":"v0.1"},"currency":"USD","maximum_repeated_loss_fraction":"0.015",'
            '"maximum_single_loss_fraction":"0.005","payoff_approval":{"limitations":'
            '["conditional standard-payoff geometry only","exact deliverable verification remains '
            'unestablished","indicative asks are non-executable and do not establish underpricing"],'
            '"model_id":"conditional-standard-payoff","model_version":"0.1"},'
            '"portfolio_value":"100000","profile_id":"standard-research-profile",'
            '"quantity":1,"repeat_count":3,"version":"v0.2"}'
        )
        self.assertEqual(historical.snapshot(), historical_snapshot)
        self.assertEqual(historical.snapshot_json(), historical_snapshot_json)
        self.assertNotIn("strategy_governance", historical.snapshot())

        structure = make_straddle()
        request = historical.request_factory(
            case_id="case-v02-historical", structure=structure, context=None
        )
        result = core_research.evaluate_core_research(request)
        self.assertEqual(request.risk_policy.methodology, "approved-standard-research-profile-v0.2")
        self.assertEqual(request.cost_ledger.premium_bound, D("440.000"))
        self.assertEqual(len(request.sensitivity.points), 12)
        rendered = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=request,
                kernel_result=result,
                reasons=(),
                full_report="",
            )
        )
        self.assertIn("profile=standard-research-profile:v0.2", rendered)
        self.assertIn("conditional_premium_factor=1.10", rendered)
        self.assertNotIn("策略治理意图", rendered)

    def test_v01_snapshot_and_factory_remain_exact_historical_behavior(self):
        legacy = StandardResearchProfile(version="v0.1")
        self.assertEqual(
            legacy.snapshot(),
            {
                "profile_id": "standard-research-profile",
                "version": "v0.1",
                "currency": "USD",
                "portfolio_value": "100000",
                "maximum_single_loss_fraction": "0.005",
                "maximum_repeated_loss_fraction": "0.015",
                "repeat_count": 3,
                "quantity": 1,
                "authorized_source": {
                    "source_id": "standalone-mvp-architecture-v0.1",
                    "version": "v0.1",
                    "basis": "user-approved-standard-research-profile",
                    "frozen_commit": "1adc636",
                },
                "payoff_approval": {
                    "model_id": "conditional-standard-payoff",
                    "model_version": "0.1",
                    "limitations": [
                        "conditional standard-payoff geometry only",
                        "exact deliverable verification remains unestablished",
                        "indicative asks are non-executable and do not establish underpricing",
                    ],
                },
            },
        )
        request = legacy.request_factory(
            case_id="legacy-v0.1", structure=make_structure(), context=object()
        )
        self.assertIsNone(request.cost_ledger)
        self.assertIsNone(request.sensitivity)
        self.assertEqual(
            request.risk_policy.methodology,
            "approved-standard-research-profile-v0.1",
        )
        rendered = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=request.structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=request,
                kernel_result=core_research.evaluate_core_research(request),
                reasons=(),
                full_report="",
            )
        )
        self.assertNotIn("现金与敏感性政策", rendered)
        self.assertNotIn("固定基线敏感性网格", rendered)

        forged_request = replace(
            request,
            provenance=replace(
                request.provenance,
                description="core-request; profile_snapshot="
                + STANDARD_RESEARCH_PROFILE.snapshot_json(),
            ),
        )
        forged_result = core_research.evaluate_core_research(forged_request)
        forged_rendered = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=forged_request.structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=forged_request,
                kernel_result=forged_result,
                reasons=(),
                full_report="",
            )
        )
        self.assertNotIn("现金与敏感性政策", forged_rendered)
        self.assertNotIn("策略治理意图", forged_rendered)

    def test_v03_governance_report_separates_intent_from_enforcement(self):
        structure = make_structure()
        request = STANDARD_RESEARCH_PROFILE.request_factory(
            case_id="case-v03-governance", structure=structure, context=None
        )
        result = core_research.evaluate_core_research(request)
        rendered = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=request,
                kernel_result=result,
                reasons=(),
                full_report="",
            )
        )
        self.assertIn("策略治理意图（非执行控制）", rendered)
        self.assertIn("funding_rule=OWN_CASH_PREMIUM; MARGIN_FINANCING_PROHIBITED", rendered)
        self.assertIn("lifecycle_intent=CLOSE_OR_ABANDON_BEFORE_EXPIRY", rendered)
        self.assertIn("exercise_rule=EXERCISE_TO_STOCK_PROHIBITED", rendered)
        self.assertIn("execution_enforcement=NOT_ESTABLISHED", rendered)
        self.assertIn("automatic_exercise_protection=NOT_ESTABLISHED", rendered)
        self.assertIn("unknown_required_costs=entry_fees", rendered)
        self.assertIn("不构成自动行权保护", rendered)
        self.assertIn("被动不操作不等于已放弃", rendered)

        mutated = STANDARD_RESEARCH_PROFILE.snapshot()
        mutated["strategy_governance"]["automatic_exercise_protection"] = "PROTECTED"
        forged_request = replace(
            request,
            provenance=replace(
                request.provenance,
                description="core-request; profile_snapshot="
                + json.dumps(mutated, sort_keys=True, separators=(",", ":")),
            ),
        )
        forged_result = core_research.evaluate_core_research(forged_request)
        forged_rendered = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=forged_request.structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=forged_request,
                kernel_result=forged_result,
                reasons=(),
                full_report="",
            )
        )
        self.assertNotIn("策略治理意图", forged_rendered)
        self.assertNotIn("automatic_exercise_protection=PROTECTED", forged_rendered)

    def test_three_origins_use_the_same_profile_request_factory(self):
        structures = (make_structure(101), make_structure(102), make_structure(103))
        policies = (
            make_policy(OptionMaturityAuthority.HYPOTHESIS_ALIGNED),
            make_policy(OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH),
            make_policy(OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH),
        )
        requests = tuple(
            policy.request_factory(
                case_id="case-{}".format(index),
                structure=structure,
                context=object(),
            )
            for index, (policy, structure) in enumerate(zip(policies, structures))
        )
        self.assertTrue(all(policy.request_factory.__self__ is STANDARD_RESEARCH_PROFILE for policy in policies))
        self.assertEqual(
            [request.risk_policy for request in requests],
            [requests[0].risk_policy] * 3,
        )
        self.assertTrue(all(request.payoff_model is not None for request in requests))
        self.assertTrue(all(request.cost_ledger is not None for request in requests))

    def test_factory_retains_structure_identity_and_verified_multiplier(self):
        structure = make_structure(multiplier=271)
        request = make_policy().request_factory(
            case_id="case-identity", structure=structure, context=object()
        )
        self.assertIs(request.structure, structure)
        self.assertEqual(request.structure.legs[0].contract_multiplier, 271)
        self.assertEqual(request.structure.legs[0].quantity, 1)
        self.assertEqual(request.cost_ledger.premium_bound, D("372.625"))

    def test_core_reports_only_explicit_incomplete_gaps(self):
        legacy = StandardResearchProfile(version="v0.1")
        request = legacy.request_factory(
            case_id="case-incomplete", structure=make_structure(), context=object()
        )
        result = core_research.evaluate_core_research(request)
        self.assertEqual(
            result.disposition, core_research.CoreDisposition.DATA_INSUFFICIENT_CORE
        )
        self.assertIn(COST_LEDGER_GAP, result.reasons)
        self.assertIn(SENSITIVITY_GAP, result.reasons)
        self.assertNotIn(core_research.CoreReasonCode.RISK_POLICY_MISSING, result.reasons)
        self.assertIsNone(request.cost_ledger)
        self.assertIsNone(request.sensitivity)
        self.assertIsNone(result.cash_ledger.conditional_total_upper_bound)
        self.assertEqual(request.payoff_model.model_id, CONDITIONAL_STANDARD_PAYOFF_APPROVAL_ID)
        self.assertIn("exact deliverable verification remains unestablished", request.payoff_model.description)

    def test_v02_exact_cash_budget_unknown_costs_and_fixed_baseline_grid(self):
        structure = make_straddle()
        historical = StandardResearchProfile(version="v0.2")
        request = historical.request_factory(
            case_id="case-v02-grid", structure=structure, context=object()
        )
        ledger = request.cost_ledger
        sensitivity = request.sensitivity
        self.assertEqual(ledger.premium_bound, D("440.000"))
        self.assertEqual(
            tuple(component.component_id for component in ledger.impact_components),
            (
                "entry_fees",
                "strategy_dependent_funding",
                "strategy_dependent_exit",
                "strategy_dependent_settlement",
            ),
        )
        self.assertTrue(
            all(
                component.status is core_research.CoreCostComponentStatus.UNKNOWN
                and component.upper_bound is None
                for component in ledger.impact_components
            )
        )
        self.assertEqual(len(sensitivity.points), 12)
        self.assertEqual(
            tuple(point.point_id for point in sensitivity.points[:6]),
            (
                "x-1-ask-1",
                "x-1-ask-1.10",
                "x-1-ask-1.25",
                "x+0-ask-1",
                "x+0-ask-1.10",
                "x+0-ask-1.25",
            ),
        )
        self.assertEqual(
            tuple(
                point.terminal_underlying_price
                for point in sensitivity.points
                if point.point_id.startswith("x+0-")
            ),
            (D("2"), D("2"), D("2")),
        )
        self.assertIn("x-2-ask-1(x=-2,terminal=-2", sensitivity.description)
        self.assertIn("NOT_APPLICABLE", sensitivity.description)
        stressed = next(
            point for point in sensitivity.points if point.point_id == "x+0-ask-1.25"
        )
        self.assertEqual(stressed.ask_per_leg, (D("1.5000"), D("1.0000")))
        result = core_research.evaluate_core_research(request)
        self.assertEqual(result.cash_ledger.observed_ask_cost, D("400"))
        self.assertIsNone(result.cash_ledger.conditional_total_upper_bound)
        self.assertEqual(len(result.sensitivity_results.points), 12)
        rendered = report(
            CoreDirectResult(
                raw_input=None,
                core_structure=structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=request,
                kernel_result=result,
                reasons=(),
                full_report="",
            )
        )
        self.assertIn("unknown_required_costs=entry_fees", rendered)
        self.assertIn("conditional_premium_factor=1.10", rendered)
        self.assertIn("x-2-ask-1(x=-2,terminal=-2", rendered)
        self.assertIn("x+0-ask-1.25", rendered)

    def test_v02_decimal_math_is_exact_under_low_ambient_precision(self):
        structure = make_straddle(
            strike="100.00000000000000000000000000000",
            call_ask="0.12345678901234567890123456789",
            put_ask="0.98765432109876543210987654321",
            quantity=3,
            multiplier=100,
        )
        with decimal.localcontext() as context:
            context.prec = 3
            historical = StandardResearchProfile(version="v0.2")
            request = historical.request_factory(
                case_id="case-exact-decimal", structure=structure, context=object()
            )
            self.assertEqual(
                request.cost_ledger.premium_bound,
                D("366.66666633666666663366666666300"),
            )
            self.assertEqual(
                next(point for point in request.sensitivity.points if point.point_id == "x+0-ask-1").terminal_underlying_price,
                D("100.00000000000000000000000000000"),
            )

    def test_v02_missing_asks_and_single_leg_scope(self):
        missing = make_straddle(put_ask=None)
        historical = StandardResearchProfile(version="v0.2")
        missing_request = historical.request_factory(
            case_id="case-missing-ask", structure=missing, context=None
        )
        self.assertIsNone(missing_request.cost_ledger)
        self.assertIsNone(missing_request.sensitivity)

        single = make_structure()
        single_request = historical.request_factory(
            case_id="case-single-leg", structure=single, context=None
        )
        self.assertIsNotNone(single_request.cost_ledger)
        self.assertEqual(single_request.cost_ledger.premium_bound, D("188.375"))
        self.assertIsNone(single_request.sensitivity)
        single_result = core_research.evaluate_core_research(single_request)
        self.assertIn(core_research.CoreReasonCode.SENSITIVITY_MISSING, single_result.reasons)

    def test_no_legacy_structure_costs_or_invented_grid_is_in_profile_module(self):
        source = inspect.getsource(sys.modules["convexity_hunter.host_profile"])
        self.assertNotIn("StructureCosts", source)
        self.assertNotIn("risk_assessment", source)
        self.assertNotIn("sensitivity_grid", source)
        legacy = StandardResearchProfile(version="v0.1")
        self.assertNotIn("cash_sensitivity_policy", legacy.snapshot())
        self.assertNotIn("fee", json.dumps(legacy.snapshot()).lower())
        self.assertNotIn("cost", json.dumps(legacy.snapshot()).lower())


if __name__ == "__main__":
    unittest.main()
