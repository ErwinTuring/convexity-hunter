"""Focused contract tests for the deterministic offline single-structure service."""

import copy
import dataclasses
import datetime
import inspect
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError
from typing import Optional, Tuple, Union
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
from convexity_hunter import candidate_assembly
from convexity_hunter import offline_service as service
from convexity_hunter.evidence import CandidateState
from convexity_hunter.option_chain_discovery import OptionResearchMaturityContext
from convexity_hunter.position_management import (
    PositionManagementPlanResult,
    QualitativePositionManagementCondition,
    QuantitativePositionManagementCondition,
)
from convexity_hunter.scanner import (
    DATA_INSUFFICIENT_REASON_ORDER,
    ScreeningDecision,
    ScreeningPolicy,
)

from test_candidate_assembly import assemble_artifacts, complete_artifacts
from test_position_management import _assembly as build_watch_assembly
from test_position_management import _watch_condition


DATE = datetime.date(2030, 1, 2)
CALCULATED_AT = datetime.datetime(
    2030, 1, 2, 15, 30, tzinfo=datetime.timezone.utc
)


def build_assembly(
    state: CandidateState = CandidateState.WATCH,
    *,
    calculation_id: str = "service-assembly",
):
    if state is CandidateState.INVESTIGATE:
        artifacts = complete_artifacts()
        missing = ()
    else:
        artifacts = (None,) * 7
        missing = ("service fixture missing artifacts",)
    return assemble_artifacts(
        artifacts,
        state,
        missing,
        calculation_id=calculation_id,
    )


def decision_for(state: CandidateState) -> ScreeningDecision:
    return ScreeningDecision(
        state,
        (DATA_INSUFFICIENT_REASON_ORDER[0],),
        "service-test-policy",
        "v1",
    )


class ChildAssembly(candidate_assembly.CandidateResearchRecordAssemblyResult):
    pass


class ChildPolicy(ScreeningPolicy):
    pass


class ChildRequest(service.PositionManagementPlanRequest):
    pass


class PublicContractTests(unittest.TestCase):
    def test_exact_api_fields_annotations_signature_and_root_boundary(self):
        self.assertEqual(
            service.__all__,
            (
                "PositionManagementPlanRequest",
                "OfflineSingleStructureServiceResult",
                "run_offline_single_structure_service",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(service.PositionManagementPlanRequest)),
            ("calculation_id", "conditions", "calculated_at"),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(service.OfflineSingleStructureServiceResult)),
            (
                "assembly_result",
                "screening_decision",
                "position_management_plan_result",
                "report_markdown",
                "maturity_context",
            ),
        )
        expected_request_annotations = {
            "calculation_id": str,
            "conditions": Tuple[
                Union[
                    QuantitativePositionManagementCondition,
                    QualitativePositionManagementCondition,
                ],
                ...,
            ],
            "calculated_at": datetime.datetime,
        }
        expected_result_annotations = {
            "assembly_result": candidate_assembly.CandidateResearchRecordAssemblyResult,
            "screening_decision": ScreeningDecision,
            "position_management_plan_result": Optional[PositionManagementPlanResult],
            "report_markdown": str,
            "maturity_context": Optional[OptionResearchMaturityContext],
        }
        self.assertEqual(
            service.PositionManagementPlanRequest.__annotations__,
            expected_request_annotations,
        )
        self.assertEqual(
            service.OfflineSingleStructureServiceResult.__annotations__,
            expected_result_annotations,
        )
        signature = inspect.signature(service.run_offline_single_structure_service)
        self.assertEqual(
            tuple(signature.parameters),
            (
                "assembly_result",
                "screening_policy",
                "position_management_plan_request",
                "maturity_context",
            ),
        )
        self.assertIs(
            signature.parameters["assembly_result"].annotation,
            candidate_assembly.CandidateResearchRecordAssemblyResult,
        )
        self.assertIs(
            signature.parameters["screening_policy"].annotation,
            ScreeningPolicy,
        )
        self.assertEqual(
            signature.parameters["position_management_plan_request"].annotation,
            Optional[service.PositionManagementPlanRequest],
        )
        self.assertIs(
            signature.return_annotation,
            service.OfflineSingleStructureServiceResult,
        )
        self.assertIs(
            signature.parameters["position_management_plan_request"].default,
            None,
        )
        for name in service.__all__[:2]:
            self.assertTrue(dataclasses.is_dataclass(getattr(service, name)))
            self.assertTrue(getattr(service, name).__dataclass_params__.frozen)
        for name in service.__all__:
            self.assertNotIn(name, vars(convexity_hunter))

    def test_service_records_are_frozen(self):
        request = service.PositionManagementPlanRequest("plan", (), CALCULATED_AT)
        result = service.OfflineSingleStructureServiceResult(
            object(), object(), None, "报告", None
        )
        with self.assertRaises(FrozenInstanceError):
            request.calculation_id = "changed"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.report_markdown = "changed"  # type: ignore[misc]


class TraceAndBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.assembly = build_assembly()
        self.policy = ScreeningPolicy()
        self.decision = decision_for(CandidateState.DATA_INSUFFICIENT)
        self.plan_result = object()
        self.request = service.PositionManagementPlanRequest(
            " plan-service ",
            (_watch_condition(),),
            CALCULATED_AT + datetime.timedelta(seconds=1),
        )

    @staticmethod
    def traced_mocks(decision, plan_result, report="报告"):
        trace = mock.Mock()
        screen = mock.Mock(return_value=decision)
        plan = mock.Mock(return_value=plan_result)
        render = mock.Mock(return_value=report)
        trace.attach_mock(screen, "screen")
        trace.attach_mock(plan, "plan")
        trace.attach_mock(render, "render")
        return trace, screen, plan, render

    def test_no_plan_trace_arguments_order_and_identity(self):
        trace, screen, plan, render = self.traced_mocks(self.decision, object())
        with mock.patch.object(service, "screen_candidate", screen), \
             mock.patch.object(service, "create_position_management_plan", plan), \
             mock.patch.object(service, "render_candidate_markdown", render):
            result = service.run_offline_single_structure_service(
                self.assembly, self.policy, maturity_context=None
            )

        self.assertEqual(
            trace.mock_calls,
            [
                mock.call.screen(self.assembly.record, self.policy),
                mock.call.render(
                    self.assembly.record,
                    locale="zh-CN",
                    screening_decision=self.decision,
                    position_management_plan_result=None,
                    maturity_context=None,
                ),
            ],
        )
        screen.assert_called_once_with(self.assembly.record, self.policy)
        plan.assert_not_called()
        render.assert_called_once()
        self.assertIs(result.assembly_result, self.assembly)
        self.assertIs(result.screening_decision, self.decision)
        self.assertIsNone(result.position_management_plan_result)
        self.assertEqual(result.report_markdown, "报告")
        self.assertIsNone(result.maturity_context)

    def test_malformed_maturity_context_precedes_screening(self):
        malformed = object.__new__(OptionResearchMaturityContext)
        object.__setattr__(malformed, "structure", self.assembly.record.structure)
        with mock.patch.object(
            service,
            "screen_candidate",
            side_effect=AssertionError("screening must not run"),
        ):
            with self.assertRaisesRegex(
                ValueError, "^maturity_context is malformed$"
            ):
                service.run_offline_single_structure_service(
                    self.assembly,
                    self.policy,
                    maturity_context=malformed,
                )

    def test_plan_trace_arguments_order_locale_and_identity(self):
        trace, screen, plan, render = self.traced_mocks(
            self.decision, self.plan_result
        )
        with mock.patch.object(service, "screen_candidate", screen), \
             mock.patch.object(service, "create_position_management_plan", plan), \
             mock.patch.object(service, "render_candidate_markdown", render):
            result = service.run_offline_single_structure_service(
                self.assembly,
                self.policy,
                self.request,
                maturity_context=None,
            )

        self.assertEqual(
            trace.mock_calls,
            [
                mock.call.screen(self.assembly.record, self.policy),
                mock.call.plan(
                    self.request.calculation_id,
                    self.assembly,
                    self.request.conditions,
                    self.request.calculated_at,
                ),
                mock.call.render(
                    self.assembly.record,
                    locale="zh-CN",
                    screening_decision=self.decision,
                    position_management_plan_result=self.plan_result,
                    maturity_context=None,
                ),
            ],
        )
        self.assertIs(result.assembly_result, self.assembly)
        self.assertIs(result.screening_decision, self.decision)
        self.assertIs(result.position_management_plan_result, self.plan_result)
        self.assertEqual(result.report_markdown, "报告")

    def test_exact_direct_types_reject_before_any_downstream_call(self):
        invalid_values = (
            (object(), self.policy, None),
            (self.assembly, object(), None),
            (self.assembly, self.policy, object()),
            (object.__new__(ChildAssembly), self.policy, None),
            (self.assembly, ChildPolicy(), None),
            (self.assembly, self.policy, object.__new__(ChildRequest)),
        )
        with mock.patch.object(
            service, "screen_candidate", side_effect=AssertionError("screen called")
        ) as screen, mock.patch.object(
            service,
            "create_position_management_plan",
            side_effect=AssertionError("plan called"),
        ) as plan, mock.patch.object(
            service,
            "render_candidate_markdown",
            side_effect=AssertionError("render called"),
        ) as render:
            for assembly, policy, request in invalid_values:
                with self.subTest(assembly=type(assembly), policy=type(policy), request=type(request)):
                    with self.assertRaises(TypeError):
                        service.run_offline_single_structure_service(
                            assembly,
                            policy,
                            request,
                            maturity_context=None,
                        )
        screen.assert_not_called()
        plan.assert_not_called()
        render.assert_not_called()

    def test_plan_is_not_gated_by_screening_decision(self):
        rejected_decision = decision_for(CandidateState.DATA_INSUFFICIENT)
        trace, screen, plan, render = self.traced_mocks(
            rejected_decision, self.plan_result
        )
        with mock.patch.object(service, "screen_candidate", screen), \
             mock.patch.object(service, "create_position_management_plan", plan), \
             mock.patch.object(service, "render_candidate_markdown", render):
            result = service.run_offline_single_structure_service(
                self.assembly,
                self.policy,
                self.request,
                maturity_context=None,
            )
        self.assertIs(result.screening_decision, rejected_decision)
        plan.assert_called_once()
        self.assertEqual(trace.mock_calls[0], mock.call.screen(self.assembly.record, self.policy))
        self.assertEqual(trace.mock_calls[1], mock.call.plan(
            self.request.calculation_id,
            self.assembly,
            self.request.conditions,
            self.request.calculated_at,
        ))

    def test_service_does_not_replay_candidate_assembly(self):
        with mock.patch.object(
            service, "screen_candidate", return_value=self.decision
        ), mock.patch.object(
            service, "render_candidate_markdown", return_value="报告"
        ), mock.patch.object(
            candidate_assembly,
            "assemble_candidate_research_record",
            side_effect=AssertionError("assembly replayed"),
        ):
            result = service.run_offline_single_structure_service(
                self.assembly, self.policy, maturity_context=None
            )
        self.assertIs(result.assembly_result, self.assembly)
        self.assertEqual(result.report_markdown, "报告")

    def test_every_valid_assembly_state_is_screened(self):
        cases = (
            (CandidateState.INVESTIGATE, complete_artifacts(), ()),
            (CandidateState.WATCH, (None,) * 7, ("watch missing",)),
            (CandidateState.REJECT, (None,) * 7, ("reject missing",)),
            (CandidateState.DATA_INSUFFICIENT, (None,) * 7, ("insufficient missing",)),
        )
        policy = ScreeningPolicy()
        screen = mock.Mock(return_value=self.decision)
        render = mock.Mock(return_value="报告")
        with mock.patch.object(service, "screen_candidate", screen), \
             mock.patch.object(service, "render_candidate_markdown", render), \
             mock.patch.object(service, "create_position_management_plan") as plan:
            assemblies = [
                assemble_artifacts(
                    artifacts,
                    state,
                    missing,
                    calculation_id=f"state-{state.value}",
                )
                for state, artifacts, missing in cases
            ]
            for assembly in assemblies:
                service.run_offline_single_structure_service(
                    assembly, policy, maturity_context=None
                )

        self.assertEqual(screen.call_count, len(cases))
        self.assertEqual(
            [call.args for call in screen.call_args_list],
            [(assembly.record, policy) for assembly in assemblies],
        )
        plan.assert_not_called()
        self.assertEqual(render.call_count, len(cases))


class ExceptionAndPurityTests(unittest.TestCase):
    def setUp(self):
        self.assembly = build_assembly()
        self.policy = ScreeningPolicy()
        self.request = service.PositionManagementPlanRequest(
            "plan-purity",
            (_watch_condition(),),
            CALCULATED_AT + datetime.timedelta(seconds=1),
        )

    def test_each_stage_exception_short_circuits_and_preserves_identity(self):
        screening_error = ValueError("screening failure")
        with mock.patch.object(service, "screen_candidate", side_effect=screening_error) as screen, \
             mock.patch.object(service, "create_position_management_plan") as plan, \
             mock.patch.object(service, "render_candidate_markdown") as render:
            with self.assertRaises(ValueError) as context:
                service.run_offline_single_structure_service(
                    self.assembly,
                    self.policy,
                    self.request,
                    maturity_context=None,
                )
        self.assertIs(context.exception, screening_error)
        screen.assert_called_once()
        plan.assert_not_called()
        render.assert_not_called()

        plan_error = RuntimeError("plan failure")
        decision = decision_for(CandidateState.DATA_INSUFFICIENT)
        with mock.patch.object(service, "screen_candidate", return_value=decision) as screen, \
             mock.patch.object(service, "create_position_management_plan", side_effect=plan_error) as plan, \
             mock.patch.object(service, "render_candidate_markdown") as render:
            with self.assertRaises(RuntimeError) as context:
                service.run_offline_single_structure_service(
                    self.assembly,
                    self.policy,
                    self.request,
                    maturity_context=None,
                )
        self.assertIs(context.exception, plan_error)
        screen.assert_called_once()
        plan.assert_called_once()
        render.assert_not_called()

        render_error = KeyError("renderer failure")
        with mock.patch.object(service, "screen_candidate", return_value=decision) as screen, \
             mock.patch.object(service, "create_position_management_plan", return_value=object()) as plan, \
             mock.patch.object(service, "render_candidate_markdown", side_effect=render_error) as render:
            with self.assertRaises(KeyError) as context:
                service.run_offline_single_structure_service(
                    self.assembly,
                    self.policy,
                    self.request,
                    maturity_context=None,
                )
        self.assertIs(context.exception, render_error)
        screen.assert_called_once()
        plan.assert_called_once()
        render.assert_called_once()

    def test_repeated_calls_are_deterministic_and_do_not_mutate_inputs(self):
        decision = decision_for(CandidateState.DATA_INSUFFICIENT)
        plan_result = object()
        assembly_before = copy.deepcopy(self.assembly)
        policy_before = copy.deepcopy(self.policy)
        request_before = copy.deepcopy(self.request)
        with mock.patch.object(service, "screen_candidate", return_value=decision), \
             mock.patch.object(service, "create_position_management_plan", return_value=plan_result), \
             mock.patch.object(service, "render_candidate_markdown", return_value="固定中文报告"):
            first = service.run_offline_single_structure_service(
                self.assembly,
                self.policy,
                self.request,
                maturity_context=None,
            )
            second = service.run_offline_single_structure_service(
                self.assembly,
                self.policy,
                self.request,
                maturity_context=None,
            )
        self.assertEqual(first, second)
        self.assertEqual(first.report_markdown, "固定中文报告")
        self.assertIs(first.assembly_result, self.assembly)
        self.assertIs(first.screening_decision, decision)
        self.assertIs(first.position_management_plan_result, plan_result)
        self.assertEqual(self.assembly, assembly_before)
        self.assertEqual(self.policy, policy_before)
        self.assertEqual(self.request, request_before)


class RealProducerIntegrationTests(unittest.TestCase):
    def test_real_producers_no_plan_path_is_chinese_and_deterministic(self):
        assembly = build_watch_assembly()
        policy = ScreeningPolicy()
        first = service.run_offline_single_structure_service(
            assembly, policy, maturity_context=None
        )
        second = service.run_offline_single_structure_service(
            assembly, policy, maturity_context=None
        )
        self.assertIs(first.assembly_result, assembly)
        self.assertIsNone(first.position_management_plan_result)
        self.assertEqual(first, second)
        self.assertEqual(first.report_markdown, second.report_markdown)
        self.assertTrue(first.report_markdown.startswith("# Convexity Hunter 候选研究报告\n"))
        self.assertIn("## 通俗概要：先看懂这份报告", first.report_markdown)

    def test_real_producers_plan_path_uses_existing_plan_and_renderer(self):
        assembly = build_watch_assembly()
        request = service.PositionManagementPlanRequest(
            "plan-integration",
            (_watch_condition(),),
            assembly.lineage.calculated_at + datetime.timedelta(seconds=1),
        )
        result = service.run_offline_single_structure_service(
            assembly,
            ScreeningPolicy(),
            request,
            maturity_context=None,
        )
        self.assertIs(result.assembly_result, assembly)
        self.assertIsInstance(result.screening_decision, type(decision_for(CandidateState.DATA_INSUFFICIENT)))
        self.assertEqual(result.screening_decision.proposed_state, CandidateState.DATA_INSUFFICIENT)
        self.assertIsInstance(result.position_management_plan_result, PositionManagementPlanResult)
        self.assertIs(result.position_management_plan_result.assembly_result, assembly)
        self.assertEqual(result.position_management_plan_result.lineage.calculation_id, "plan-integration")
        self.assertTrue(result.report_markdown.startswith("# Convexity Hunter 候选研究报告\n"))
        self.assertIn("plan-integration", result.report_markdown)


if __name__ == "__main__":
    unittest.main()
