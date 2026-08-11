"""Focused tests for Direct Entry reviewed-research orchestration v0.2."""

import dataclasses
import decimal
import inspect
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError
from typing import Optional
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import convexity_hunter
from convexity_hunter import direct_entry_verification
from convexity_hunter import offline_service
from convexity_hunter import direct_entry_reviewed_research_service as service
from convexity_hunter.evidence import CandidateState
from convexity_hunter.scanner import ScreeningPolicy, ScreeningReasonCode

from tests import market_data_fixtures
from tests.test_candidate_assembly import assemble_artifacts, complete_artifacts


def _contract_references(structure):
    references = []
    for index, leg in enumerate(structure.legs):
        key = market_data_fixtures.build_option_contract_key(
            expiration=leg.expiration,
            option_type=leg.option_type,
            strike=decimal.Decimal(str(leg.strike)),
            contract_multiplier=leg.contract_multiplier,
        )
        reference = market_data_fixtures.build_option_contract_reference(
            contract_key=key,
            listing_date=None,
            last_trade_date=None,
        )
        references.append(
            dataclasses.replace(
                reference,
                metadata=dataclasses.replace(
                    reference.metadata,
                    record_id=f"direct-entry-contract-{index}",
                ),
            )
        )
    return tuple(references)


def _arguments(assembly, calculation_id):
    record = assembly.record
    return (
        calculation_id,
        record.candidate_id,
        record.state,
        record.state_rationale,
        record.as_of_date,
        record.hypothesis,
        record.structure,
        _contract_references(record.structure),
        assembly.volatility_environment_result,
        assembly.tail_pricing_result,
        assembly.structure_liquidity_result,
        assembly.structure_costs_result,
        assembly.scenario_valuation_result,
        assembly.expiration_payoff_threshold_result,
        assembly.structure_affordability_result,
        record.evidence,
        record.falsification_conditions,
        record.missing_data,
        record.false_positive_reasons,
        record.ai_interpretation,
        record.human_review_questions,
        assembly.lineage.calculated_at,
    )


class PublicContractTests(unittest.TestCase):
    def test_exact_api_result_shape_and_24_parameter_signature(self):
        self.assertEqual(
            service.__all__,
            (
                "DirectEntryReviewedResearchServiceResult",
                "run_direct_entry_reviewed_research_service",
            ),
        )
        self.assertEqual(
            tuple(name for name in vars(service) if not name.startswith("_")),
            service.__all__,
        )
        for name in service.__all__:
            self.assertFalse(hasattr(convexity_hunter, name))

        result_type = service.DirectEntryReviewedResearchServiceResult
        self.assertTrue(dataclasses.is_dataclass(result_type))
        self.assertTrue(result_type.__dataclass_params__.frozen)
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(result_type)),
            (
                "exact_contract_verification",
                "research_readiness_verification",
                "offline_service_result",
            ),
        )
        self.assertEqual(
            result_type.__annotations__,
            {
                "exact_contract_verification": (
                    direct_entry_verification.DirectEntryExactContractVerification
                ),
                "research_readiness_verification": Optional[
                    direct_entry_verification.DirectEntryResearchReadinessVerification
                ],
                "offline_service_result": (
                    offline_service.OfflineSingleStructureServiceResult
                ),
            },
        )
        result = result_type(object(), None, object())
        with self.assertRaises(FrozenInstanceError):
            result.offline_service_result = object()

        expected_names = (
            "calculation_id", "candidate_id", "state", "state_rationale",
            "as_of_date", "hypothesis", "structure", "contract_references",
            "volatility_environment_result", "tail_pricing_result",
            "structure_liquidity_result", "structure_costs_result",
            "scenario_valuation_result", "expiration_payoff_threshold_result",
            "structure_affordability_result", "evidence",
            "falsification_conditions", "missing_data",
            "false_positive_reasons", "ai_interpretation",
            "human_review_questions", "calculated_at", "screening_policy",
            "position_management_plan_request",
        )
        signature = inspect.signature(
            service.run_direct_entry_reviewed_research_service
        )
        self.assertEqual(tuple(signature.parameters), expected_names)
        self.assertEqual(
            tuple(signature.parameters[name].annotation for name in expected_names[:22]),
            (object,) * 22,
        )
        self.assertIs(
            signature.parameters["screening_policy"].annotation,
            ScreeningPolicy,
        )


class DelegationContractTests(unittest.TestCase):
    def setUp(self):
        self.arguments = tuple(object() for _ in range(22))
        self.policy = object()
        self.exact = mock.Mock(structure=object())
        self.readiness = object()
        self.assembly = object()
        self.offline = object()

    def test_complete_path_retains_both_verifications_and_order(self):
        arguments = list(self.arguments)
        arguments[10] = object()
        arguments[11] = object()
        trace = mock.Mock()
        exact = mock.Mock(return_value=self.exact)
        readiness = mock.Mock(return_value=self.readiness)
        assemble = mock.Mock(return_value=self.assembly)
        offline = mock.Mock(return_value=self.offline)
        trace.attach_mock(exact, "exact")
        trace.attach_mock(readiness, "readiness")
        trace.attach_mock(assemble, "assemble")
        trace.attach_mock(offline, "offline")
        with mock.patch.object(service, "_verify_direct_entry_exact_contracts", exact), \
             mock.patch.object(service, "_verify_direct_entry_research_readiness", readiness), \
             mock.patch.object(service, "_assemble_candidate_research_record", assemble), \
             mock.patch.object(service, "_run_offline_single_structure_service", offline):
            result = service.run_direct_entry_reviewed_research_service(
                *arguments, self.policy
            )

        assembled = list(arguments)
        assembled[6] = self.exact.structure
        del assembled[7]
        self.assertEqual(
            trace.mock_calls,
            [
                mock.call.exact(arguments[6], arguments[7]),
                mock.call.readiness(
                    self.exact.structure, arguments[11], arguments[10]
                ),
                mock.call.assemble(*assembled),
                mock.call.offline(self.assembly, self.policy, None),
            ],
        )
        self.assertIs(result.exact_contract_verification, self.exact)
        self.assertIs(result.research_readiness_verification, self.readiness)
        self.assertIs(result.offline_service_result, self.offline)

    def test_missing_either_artifact_skips_readiness_but_not_assembly(self):
        for missing_index in (10, 11):
            with self.subTest(missing_index=missing_index):
                arguments = list(self.arguments)
                arguments[10] = object()
                arguments[11] = object()
                arguments[missing_index] = None
                with mock.patch.object(
                    service, "_verify_direct_entry_exact_contracts",
                    return_value=self.exact,
                ) as exact, mock.patch.object(
                    service, "_verify_direct_entry_research_readiness"
                ) as readiness, mock.patch.object(
                    service, "_assemble_candidate_research_record",
                    return_value=self.assembly,
                ) as assemble, mock.patch.object(
                    service, "_run_offline_single_structure_service",
                    return_value=self.offline,
                ) as offline:
                    result = service.run_direct_entry_reviewed_research_service(
                        *arguments, self.policy
                    )
                exact.assert_called_once_with(arguments[6], arguments[7])
                readiness.assert_not_called()
                assemble.assert_called_once()
                offline.assert_called_once_with(self.assembly, self.policy, None)
                self.assertIsNone(result.research_readiness_verification)

    def test_exact_verification_failure_short_circuits_all_later_stages(self):
        error = ValueError("exact failure")
        with mock.patch.object(
            service, "_verify_direct_entry_exact_contracts", side_effect=error
        ), mock.patch.object(
            service, "_verify_direct_entry_research_readiness"
        ) as readiness, mock.patch.object(
            service, "_assemble_candidate_research_record"
        ) as assemble, mock.patch.object(
            service, "_run_offline_single_structure_service"
        ) as offline:
            with self.assertRaises(ValueError) as context:
                service.run_direct_entry_reviewed_research_service(
                    *self.arguments, self.policy
                )
        self.assertIs(context.exception, error)
        readiness.assert_not_called()
        assemble.assert_not_called()
        offline.assert_not_called()


class RealVerticalSliceTests(unittest.TestCase):
    def test_complete_artifacts_retain_research_readiness(self):
        assembly = assemble_artifacts(
            complete_artifacts(),
            calculation_id="direct-entry-complete-source",
        )
        result = service.run_direct_entry_reviewed_research_service(
            *_arguments(assembly, "direct-entry-complete-result"),
            ScreeningPolicy(),
        )
        self.assertIsNotNone(result.research_readiness_verification)
        self.assertEqual(
            result.research_readiness_verification.structure,
            assembly.record.structure,
        )

    def test_zero_artifact_real_contract_path_returns_data_insufficient_report(self):
        assembly = assemble_artifacts(
            (None,) * 7,
            CandidateState.DATA_INSUFFICIENT,
            ("成本、流动性及其余研究证据尚无权威输入",),
            calculation_id="direct-entry-zero-source",
        )
        result = service.run_direct_entry_reviewed_research_service(
            *_arguments(assembly, "direct-entry-zero-result"),
            ScreeningPolicy(),
        )
        offline = result.offline_service_result
        self.assertIsNone(result.research_readiness_verification)
        self.assertIs(
            offline.screening_decision.proposed_state,
            CandidateState.DATA_INSUFFICIENT,
        )
        self.assertIn(
            ScreeningReasonCode.MISSING_COSTS,
            offline.screening_decision.reason_codes,
        )
        self.assertIn(
            ScreeningReasonCode.MISSING_LIQUIDITY,
            offline.screening_decision.reason_codes,
        )
        self.assertIsNone(offline.position_management_plan_result)
        self.assertIn("数据不足", offline.report_markdown)
        self.assertEqual(
            offline.assembly_result.lineage.inputs,
            (),
        )

    def test_one_present_artifact_is_retained_without_claiming_readiness(self):
        costs = complete_artifacts()[3]
        assembly = assemble_artifacts(
            (None, None, None, costs, None, None, None),
            CandidateState.DATA_INSUFFICIENT,
            ("流动性及其余研究证据尚无权威输入",),
            calculation_id="direct-entry-cost-only-source",
        )
        result = service.run_direct_entry_reviewed_research_service(
            *_arguments(assembly, "direct-entry-cost-only-result"),
            ScreeningPolicy(),
        )
        self.assertIsNone(result.research_readiness_verification)
        self.assertIs(
            result.offline_service_result.assembly_result.structure_costs_result,
            costs,
        )
        self.assertIsNone(
            result.offline_service_result.assembly_result.structure_liquidity_result
        )


if __name__ == "__main__":
    unittest.main()
