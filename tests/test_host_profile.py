"""Focused tests for the M3 host-owned Standard Research Profile."""

import datetime
import decimal
import inspect
import json
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter import core_research
from convexity_hunter.core_application import CoreOperationalBounds
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
        self.assertEqual(profile.version, "v0.1")
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

    def test_factory_retains_structure_identity_and_verified_multiplier(self):
        structure = make_structure(multiplier=271)
        request = make_policy().request_factory(
            case_id="case-identity", structure=structure, context=object()
        )
        self.assertIs(request.structure, structure)
        self.assertEqual(request.structure.legs[0].contract_multiplier, 271)
        self.assertEqual(request.structure.legs[0].quantity, 1)

    def test_core_reports_only_explicit_incomplete_gaps(self):
        request = make_policy().request_factory(
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

    def test_no_legacy_structure_costs_or_invented_grid_is_in_profile_module(self):
        source = inspect.getsource(sys.modules["convexity_hunter.host_profile"])
        self.assertNotIn("StructureCosts", source)
        self.assertNotIn("risk_assessment", source)
        self.assertNotIn("sensitivity_grid", source)
        self.assertNotIn("fee", STANDARD_RESEARCH_PROFILE.snapshot())
        self.assertNotIn("cost", STANDARD_RESEARCH_PROFILE.snapshot())


if __name__ == "__main__":
    unittest.main()
