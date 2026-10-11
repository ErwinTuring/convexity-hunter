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
from convexity_hunter.core_application import CoreDirectResult, CoreOperationalBounds
from convexity_hunter.core_presentation import report
from convexity_hunter.host_profile import (
    APPROVED_STANDARD_RESEARCH_PROFILE,
    CONDITIONAL_STANDARD_PAYOFF_APPROVAL_ID,
    COST_LEDGER_GAP,
    SENSITIVITY_GAP,
    STANDARD_RESEARCH_PROFILE,
    StandardResearchProfile,
    create_core_research_policy,
)
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority


D = decimal.Decimal


def make_structure(multiplier=137):
    provenance = core_research.CoreProvenance(None, "test structure provenance")
    leg = core_research.CoreLeg(
        leg_id="call-1",
        underlying="XYZ",
        currency="USD",
        option_type=core_research.CoreOptionType.CALL,
        strike=D("100"),
        expiration=datetime.date(2031, 1, 15),
        quantity=1,
        contract_multiplier=multiplier,
        ask_per_underlying_unit=D("1.25"),
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
        self.assertEqual(profile.version, "v0.2")
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
        self.assertEqual(snapshot["portfolio_value"], "100000")
        self.assertEqual(snapshot["maximum_single_loss_fraction"], "0.005")
        self.assertEqual(snapshot["maximum_repeated_loss_fraction"], "0.015")
        self.assertEqual(snapshot["repeat_count"], 3)
        self.assertEqual(snapshot["quantity"], 1)
        self.assertEqual(snapshot["version"], "v0.2")
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
        self.assertEqual(snapshot["authorized_source"]["frozen_commit"], "1adc636")
        self.assertNotIn("credential", encoded.lower())
        self.assertNotIn("token", encoded.lower())
        self.assertEqual(
            json.loads(STANDARD_RESEARCH_PROFILE.snapshot_json()), snapshot
        )

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
        request = STANDARD_RESEARCH_PROFILE.request_factory(
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
            request = STANDARD_RESEARCH_PROFILE.request_factory(
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
        missing_request = STANDARD_RESEARCH_PROFILE.request_factory(
            case_id="case-missing-ask", structure=missing, context=None
        )
        self.assertIsNone(missing_request.cost_ledger)
        self.assertIsNone(missing_request.sensitivity)

        single = make_structure()
        single_request = STANDARD_RESEARCH_PROFILE.request_factory(
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
