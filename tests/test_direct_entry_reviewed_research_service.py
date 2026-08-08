"""Focused contract tests for direct-entry reviewed-research orchestration."""

import copy
import dataclasses
import datetime
import inspect
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Optional
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
from convexity_hunter import direct_entry_verification
from convexity_hunter import offline_service
from convexity_hunter import direct_entry_reviewed_research_service as service
from convexity_hunter.evidence import CandidateState
from convexity_hunter.scanner import ScreeningPolicy

from tests.test_candidate_assembly import assemble_artifacts, complete_artifacts
from tests.test_position_management import _watch_condition


class PublicContractTests(unittest.TestCase):
    def test_exact_two_name_api_and_root_boundary(self):
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

    def test_result_shape_annotations_and_frozen_construction(self):
        result_type = service.DirectEntryReviewedResearchServiceResult
        self.assertTrue(dataclasses.is_dataclass(result_type))
        self.assertTrue(result_type.__dataclass_params__.frozen)
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(result_type)),
            ("direct_entry_verification", "offline_service_result"),
        )
        self.assertEqual(
            tuple(field.type for field in dataclasses.fields(result_type)),
            (
                direct_entry_verification.DirectEntryExactStructureVerification,
                offline_service.OfflineSingleStructureServiceResult,
            ),
        )
        self.assertEqual(
            result_type.__annotations__,
            {
                "direct_entry_verification": (
                    direct_entry_verification.DirectEntryExactStructureVerification
                ),
                "offline_service_result": (
                    offline_service.OfflineSingleStructureServiceResult
                ),
            },
        )

        verification = object()
        offline_result = object()
        result = result_type(verification, offline_result)
        self.assertIs(result.direct_entry_verification, verification)
        self.assertIs(result.offline_service_result, offline_result)
        with self.assertRaises(FrozenInstanceError):
            result.offline_service_result = object()  # type: ignore[misc]

    def test_exact_23_parameter_signature(self):
        expected_names = (
            "calculation_id",
            "candidate_id",
            "state",
            "state_rationale",
            "as_of_date",
            "hypothesis",
            "structure",
            "volatility_environment_result",
            "tail_pricing_result",
            "structure_liquidity_result",
            "structure_costs_result",
            "scenario_valuation_result",
            "expiration_payoff_threshold_result",
            "structure_affordability_result",
            "evidence",
            "falsification_conditions",
            "missing_data",
            "false_positive_reasons",
            "ai_interpretation",
            "human_review_questions",
            "calculated_at",
            "screening_policy",
            "position_management_plan_request",
        )
        signature = inspect.signature(
            service.run_direct_entry_reviewed_research_service
        )
        self.assertEqual(tuple(signature.parameters), expected_names)
        self.assertEqual(
            tuple(
                signature.parameters[name].annotation
                for name in expected_names[:21]
            ),
            (object,) * 21,
        )
        self.assertIs(
            signature.parameters["screening_policy"].annotation,
            ScreeningPolicy,
        )
        self.assertEqual(
            signature.parameters[
                "position_management_plan_request"
            ].annotation,
            Optional[offline_service.PositionManagementPlanRequest],
        )
        self.assertIs(
            signature.parameters["position_management_plan_request"].default,
            None,
        )
        self.assertIs(
            signature.return_annotation,
            service.DirectEntryReviewedResearchServiceResult,
        )


class DelegationContractTests(unittest.TestCase):
    @staticmethod
    def _arguments():
        return tuple(object() for _ in range(21))

    @staticmethod
    def _verification(arguments):
        return SimpleNamespace(
            structure=object(),
            costs_result=object(),
            liquidity_result=object(),
        )

    def test_exact_four_stage_trace_and_retained_identity_without_plan(self):
        arguments = self._arguments()
        verification = self._verification(arguments)
        assembly_result = object()
        offline_result = object()
        policy = object()
        trace = mock.Mock()
        verify = mock.Mock(return_value=verification)
        assemble = mock.Mock(return_value=assembly_result)
        offline = mock.Mock(return_value=offline_result)
        trace.attach_mock(verify, "verify")
        trace.attach_mock(assemble, "assemble")
        trace.attach_mock(offline, "offline")

        with mock.patch.object(
            service, "_verify_direct_entry_exact_structure", verify
        ), mock.patch.object(
            service, "_assemble_candidate_research_record", assemble
        ), mock.patch.object(
            service, "_run_offline_single_structure_service", offline
        ):
            result = service.run_direct_entry_reviewed_research_service(
                *arguments, policy
            )

        expected_assembly_arguments = list(arguments)
        expected_assembly_arguments[6] = verification.structure
        expected_assembly_arguments[9] = verification.liquidity_result
        expected_assembly_arguments[10] = verification.costs_result
        self.assertEqual(
            trace.mock_calls,
            [
                mock.call.verify(
                    arguments[6], arguments[10], arguments[9]
                ),
                mock.call.assemble(*expected_assembly_arguments),
                mock.call.offline(assembly_result, policy, None),
            ],
        )
        self.assertIs(result.direct_entry_verification, verification)
        self.assertIs(result.offline_service_result, offline_result)

    def test_plan_request_is_passed_unchanged_as_third_offline_argument(self):
        arguments = self._arguments()
        verification = self._verification(arguments)
        assembly_result = object()
        offline_result = object()
        policy = object()
        request = object()
        with mock.patch.object(
            service,
            "_verify_direct_entry_exact_structure",
            return_value=verification,
        ) as verify, mock.patch.object(
            service,
            "_assemble_candidate_research_record",
            return_value=assembly_result,
        ) as assemble, mock.patch.object(
            service,
            "_run_offline_single_structure_service",
            return_value=offline_result,
        ) as offline:
            result = service.run_direct_entry_reviewed_research_service(
                *arguments, policy, request
            )

        verify.assert_called_once_with(arguments[6], arguments[10], arguments[9])
        assembled = list(arguments)
        assembled[6] = verification.structure
        assembled[9] = verification.liquidity_result
        assembled[10] = verification.costs_result
        assemble.assert_called_once_with(*assembled)
        offline.assert_called_once_with(assembly_result, policy, request)
        self.assertIs(result.direct_entry_verification, verification)
        self.assertIs(result.offline_service_result, offline_result)

    def test_no_service_level_prevalidation_or_local_authority(self):
        arguments = tuple({"caller_value": index} for index in range(21))
        verification = self._verification(arguments)
        assembly_result = {"assembly": []}
        offline_result = {"offline": []}
        policy = {"policy": []}
        request = {"request": []}
        with mock.patch.object(
            service,
            "_verify_direct_entry_exact_structure",
            return_value=verification,
        ), mock.patch.object(
            service,
            "_assemble_candidate_research_record",
            return_value=assembly_result,
        ), mock.patch.object(
            service,
            "_run_offline_single_structure_service",
            return_value=offline_result,
        ):
            result = service.run_direct_entry_reviewed_research_service(
                *arguments, policy, request
            )
        self.assertIs(result.direct_entry_verification, verification)
        self.assertIs(result.offline_service_result, offline_result)

    def test_delegated_failures_propagate_unchanged_and_short_circuit(self):
        arguments = self._arguments()
        verification = self._verification(arguments)
        policy = object()

        verification_error = ValueError("verification failure")
        with mock.patch.object(
            service,
            "_verify_direct_entry_exact_structure",
            side_effect=verification_error,
        ) as verify, mock.patch.object(
            service,
            "_assemble_candidate_research_record",
        ) as assemble, mock.patch.object(
            service,
            "_run_offline_single_structure_service",
        ) as offline:
            with self.assertRaises(ValueError) as context:
                service.run_direct_entry_reviewed_research_service(
                    *arguments, policy
                )
        self.assertIs(context.exception, verification_error)
        verify.assert_called_once_with(arguments[6], arguments[10], arguments[9])
        assemble.assert_not_called()
        offline.assert_not_called()

        assembly_error = RuntimeError("assembly failure")
        with mock.patch.object(
            service,
            "_verify_direct_entry_exact_structure",
            return_value=verification,
        ) as verify, mock.patch.object(
            service,
            "_assemble_candidate_research_record",
            side_effect=assembly_error,
        ) as assemble, mock.patch.object(
            service,
            "_run_offline_single_structure_service",
        ) as offline:
            with self.assertRaises(RuntimeError) as context:
                service.run_direct_entry_reviewed_research_service(
                    *arguments, policy
                )
        self.assertIs(context.exception, assembly_error)
        verify.assert_called_once_with(arguments[6], arguments[10], arguments[9])
        assemble.assert_called_once()
        offline.assert_not_called()

        offline_error = KeyError("offline failure")
        assembly_result = object()
        with mock.patch.object(
            service,
            "_verify_direct_entry_exact_structure",
            return_value=verification,
        ) as verify, mock.patch.object(
            service,
            "_assemble_candidate_research_record",
            return_value=assembly_result,
        ) as assemble, mock.patch.object(
            service,
            "_run_offline_single_structure_service",
            side_effect=offline_error,
        ) as offline:
            with self.assertRaises(KeyError) as context:
                service.run_direct_entry_reviewed_research_service(
                    *arguments, policy
                )
        self.assertIs(context.exception, offline_error)
        verify.assert_called_once()
        assemble.assert_called_once()
        offline.assert_called_once_with(assembly_result, policy, None)

    def test_repeated_calls_are_deterministic_and_do_not_mutate_inputs(self):
        arguments = tuple(
            {"index": index, "nested": [index]} for index in range(21)
        )
        policy = {"policy": ["fixed"]}
        request = {"request": ["fixed"]}
        arguments_before = copy.deepcopy(arguments)
        policy_before = copy.deepcopy(policy)
        request_before = copy.deepcopy(request)
        verification = self._verification(arguments)
        assembly_result = object()
        offline_result = object()
        with mock.patch.object(
            service,
            "_verify_direct_entry_exact_structure",
            return_value=verification,
        ), mock.patch.object(
            service,
            "_assemble_candidate_research_record",
            return_value=assembly_result,
        ), mock.patch.object(
            service,
            "_run_offline_single_structure_service",
            return_value=offline_result,
        ):
            first = service.run_direct_entry_reviewed_research_service(
                *arguments, policy, request
            )
            second = service.run_direct_entry_reviewed_research_service(
                *arguments, policy, request
            )
        self.assertEqual(first, second)
        self.assertIs(first.direct_entry_verification, verification)
        self.assertIs(first.offline_service_result, offline_result)
        self.assertEqual(arguments, arguments_before)
        self.assertEqual(policy, policy_before)
        self.assertEqual(request, request_before)


class RealDelegationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        artifacts = complete_artifacts()
        cls.complete = assemble_artifacts(
            artifacts,
            calculation_id="direct-entry-service-complete",
        )
        cls.partial = assemble_artifacts(
            (None, None, artifacts[2], artifacts[3], None, None, None),
            CandidateState.WATCH,
            ("volatility, tail, scenario, and sidecar artifacts omitted",),
            calculation_id="direct-entry-service-partial",
        )

    @staticmethod
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

    def test_complete_and_costs_liquidity_only_partial_assemblies(self):
        for label, assembly in (
            ("complete", self.complete),
            ("partial", self.partial),
        ):
            with self.subTest(label=label):
                self.assertIsNotNone(assembly.structure_costs_result)
                self.assertIsNotNone(assembly.structure_liquidity_result)
                arguments = self._arguments(
                    assembly, "direct-entry-service-" + label
                )
                result = service.run_direct_entry_reviewed_research_service(
                    *arguments, ScreeningPolicy()
                )
                verification = result.direct_entry_verification
                self.assertIs(verification.structure, arguments[6])
                self.assertIs(
                    verification.liquidity_result,
                    arguments[9],
                )
                self.assertIs(
                    verification.costs_result,
                    arguments[10],
                )
                self.assertIsInstance(
                    result.offline_service_result,
                    offline_service.OfflineSingleStructureServiceResult,
                )

    def test_partial_path_accepts_plan_request_and_offline_retains_assembly(self):
        arguments = self._arguments(self.partial, "direct-entry-service-plan")
        request = offline_service.PositionManagementPlanRequest(
            "direct-entry-service-plan-result",
            (_watch_condition(),),
            self.partial.lineage.calculated_at + datetime.timedelta(seconds=1),
        )
        result = service.run_direct_entry_reviewed_research_service(
            *arguments,
            ScreeningPolicy(),
            request,
        )
        offline_result = result.offline_service_result
        self.assertIsNotNone(offline_result.position_management_plan_result)
        self.assertIs(
            offline_result.position_management_plan_result.assembly_result,
            offline_result.assembly_result,
        )

    def test_costs_and_liquidity_are_mandatory_for_direct_entry(self):
        for label, index in (("liquidity", 9), ("costs", 10)):
            with self.subTest(label=label):
                arguments = list(
                    self._arguments(
                        self.partial, "direct-entry-service-missing-" + label
                    )
                )
                arguments[index] = None
                with mock.patch.object(
                    service,
                    "_assemble_candidate_research_record",
                    side_effect=AssertionError("assembly must not run"),
                ) as assemble:
                    with self.assertRaises(TypeError):
                        service.run_direct_entry_reviewed_research_service(
                            *arguments, ScreeningPolicy()
                        )
                assemble.assert_not_called()
