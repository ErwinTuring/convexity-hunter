"""Offline composition tests for the three-entry ResearchCase boundary."""

import datetime
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError, fields, replace
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from convexity_hunter import research_case as app
from convexity_hunter import position_management as position_management
from convexity_hunter.evidence import CandidateState
from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.event_intelligence import (
    HypothesisReassessment,
    ReassessmentBasisKind,
)
from convexity_hunter.event_entry_preparation import (
    PreparedEventStatement,
    prepare_event_entry_hypotheses,
)
from convexity_hunter.offline_service import PositionManagementPlanRequest
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority
from convexity_hunter.providers import futu
from convexity_hunter.scanner import ScreeningPolicy

from tests.test_candidate_assembly import assemble_artifacts, complete_artifacts
from tests.test_convexity_discrimination import (
    make_bar,
    make_quote_batch,
)
from tests.test_discovery_entry import make_submission
from tests.test_event_discovery import make_batch, make_candidate
from tests.test_futu_exact_contract_browser import browser_with_rows
from tests.test_futu_option_chain_discovery import chain_row
from tests.test_futu_selection_direct_entry_bridge import ExactSelectionContext
from tests.test_direct_entry_reviewed_research_service import _contract_references
from tests.test_position_management import _qualitative, _watch_condition


EVALUATION_DATE = datetime.date(2030, 1, 3)
EXPIRATION = datetime.date(2030, 3, 1)


def _event_cases():
    """Return one accepted submission, autonomous case, and Event Entry case."""

    submission = make_submission()
    candidate = make_candidate(
        sources=submission.sources,
        observed_at=submission.observed_at,
    )
    batch = make_batch(
        candidates=(candidate,),
        observed_at=submission.observed_at,
    )
    autonomous = app.start_autonomous_discovery_case("auto-case", batch)
    autonomous = app.continue_autonomous_discovery_case(
        autonomous,
        candidate_id=candidate.candidate_id,
        submission=submission,
    )
    autonomous = app.select_discovery_hypothesis(
        autonomous,
        hypothesis_id=submission.hypotheses[0].hypothesis_id,
        evaluation_date=EVALUATION_DATE,
    )

    user_input = UserEventInput("Investigate the same event from a user request")
    preparation = prepare_event_entry_hypotheses(
        user_input,
        sources=submission.sources,
        statements=tuple(PreparedEventStatement(item) for item in submission.statements),
        hypotheses=submission.hypotheses,
        grounding_methodology="Retained source evidence supports a conditional transmission.",
        chronology_review="No realized causal effect is asserted.",
    )
    event_entry = app.start_event_entry_case("event-case", preparation)
    event_entry = app.continue_event_entry_case(
        event_entry,
        hypothesis_id=submission.hypotheses[0].hypothesis_id,
        submission_id="event-entry-submission",
        event_id=submission.event_id,
        observed_at=submission.observed_at,
        event_description=submission.event_description,
        event_date_range=submission.event_date_range,
        evaluation_date=EVALUATION_DATE,
    )
    return submission, autonomous, event_entry


def _attach_surface(case):
    rows = [
        chain_row(EXPIRATION, "CALL", "100"),
        chain_row(EXPIRATION, "PUT", "100"),
    ]
    browser, _context = browser_with_rows(
        rows,
        expiration=EXPIRATION,
        discovery_request=case.option_research_request,
    )
    case = app.attach_browser_evidence(case, browser)
    discrimination = app._discrimination.discriminate_probability_free_convexity(
        browser,
        make_quote_batch(browser),
        (make_bar(browser, EVALUATION_DATE),),
        latest_completed_session_date=EVALUATION_DATE,
    )
    case = app.attach_discrimination_evidence(case, discrimination)
    case = app.select_exact_structure(
        case,
        provider_identifiers=tuple(row.provider_identifier for row in browser.rows),
        assumed_portfolio_value=100000.0,
        expected_holding_days=20,
    )
    case = app.verify_exact_structure(
        case,
        selection_verification=futu.verify_futu_exact_contract_selection(
            ExactSelectionContext(rows),
            case.exact_structure_selection,
        ),
    )
    return case


def _research_input(
    case,
    calculation_id,
    *,
    artifacts=None,
    state=CandidateState.DATA_INSUFFICIENT,
    missing=("offline research artifacts remain unavailable",),
    position_management_plan_request=None,
):
    structure = case.exact_contract_verification.structure
    assembly = assemble_artifacts(
        (None,) * 7 if artifacts is None else artifacts,
        state,
        missing,
        calculation_id=calculation_id,
        structure_override=structure,
    )
    record = assembly.record
    return app.ResearchCaseResearchInput(
        calculation_id,
        record.candidate_id,
        record.state,
        record.state_rationale,
        record.as_of_date,
        record.hypothesis,
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
        ScreeningPolicy(),
        position_management_plan_request,
    )


def _placeholder_research_input():
    return app.ResearchCaseResearchInput(*([object()] * 21 + [None]))


class ResearchCaseTests(unittest.TestCase):
    def test_public_model_is_frozen_and_has_no_package_root_exports(self):
        self.assertTrue(app.ResearchCase.__dataclass_params__.frozen)
        self.assertTrue(app.ResearchCaseResearchInput.__dataclass_params__.frozen)
        self.assertEqual(
            tuple(field.name for field in fields(app.ResearchCase)),
            (
                "case_id",
                "entry_origin",
                "original_input",
                "stage",
                "discovery_selection",
                "discovery_translation",
                "event_entry_preparation",
                "event_entry_selection",
                "event_entry_translation",
                "event_entry_context",
                "event_intelligence_assessment",
                "selected_hypothesis",
                "option_research_request",
                "browser",
                "discrimination",
                "exact_structure_selection",
                "futu_selection_verification",
                "direct_contract_references",
                "direct_entry_exact_contract_verification",
                "downstream_result",
                "blocking_reasons",
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            app.start_autonomous_discovery_case("x", make_batch()).stage = (  # type: ignore[misc]
                app.ResearchCaseStage.COMPLETED
            )

    def test_positive_discovery_and_raw_event_entry_are_separate_checkpoints(self):
        submission = make_submission()
        candidate = make_candidate(
            sources=submission.sources,
            observed_at=submission.observed_at,
        )
        batch = make_batch(
            candidates=(candidate,),
            observed_at=submission.observed_at,
        )
        discovery = app.start_autonomous_discovery_case("selection-only", batch)
        with mock.patch.object(
            app._event_intelligence,
            "assess_event_intelligence_submission",
            side_effect=AssertionError("candidate selection must not run EI"),
        ):
            selected = app.continue_autonomous_discovery_case(
                discovery,
                candidate_id=candidate.candidate_id,
            )
        self.assertEqual(selected.stage, app.ResearchCaseStage.EVENT_INTELLIGENCE)
        self.assertIs(selected.discovery_selection.selected_candidate, candidate)
        self.assertIsNone(selected.discovery_translation)
        self.assertEqual(
            selected.blocking_reasons,
            ("awaiting_event_intelligence_submission",),
        )
        with self.assertRaisesRegex(ValueError, "not awaiting discovery selection"):
            app.continue_autonomous_discovery_case(
                selected,
                candidate_id=candidate.candidate_id,
            )
        assessed = app.attach_discovery_submission(
            selected,
            submission=submission,
        )
        self.assertIs(assessed.discovery_translation.submission, submission)
        self.assertIsNotNone(assessed.event_intelligence_assessment)

        raw_input = UserEventInput("Start Event Entry before grounding is prepared")
        raw_case = app.start_event_entry_case("raw-event", raw_input)
        self.assertIs(raw_case.original_input, raw_input)
        self.assertIsNone(raw_case.event_entry_preparation)
        self.assertEqual(
            raw_case.blocking_reasons,
            ("awaiting_event_grounding_preparation",),
        )
        with self.assertRaisesRegex(ValueError, "preparation is missing"):
            app.continue_event_entry_case(
                raw_case,
                hypothesis_id=submission.hypotheses[0].hypothesis_id,
            )
        preparation = prepare_event_entry_hypotheses(
            raw_input,
            sources=submission.sources,
            statements=tuple(PreparedEventStatement(item) for item in submission.statements),
            hypotheses=submission.hypotheses,
            grounding_methodology="Retained source evidence supports a conditional transmission.",
            chronology_review="No realized causal effect is asserted.",
        )
        prepared = app.attach_event_entry_preparation(raw_case, preparation)
        self.assertIs(prepared.event_entry_preparation, preparation)
        self.assertIs(prepared.event_entry_preparation.user_input, raw_input)

    def test_empty_browser_and_unpaired_comparison_stop_without_structure_checkpoint(self):
        _submission, case, _event = _event_cases()
        empty_browser, _context = browser_with_rows(
            [],
            expiration=EXPIRATION,
            discovery_request=case.option_research_request,
        )
        empty_surface = app.attach_browser_evidence(case, empty_browser)
        self.assertEqual(
            empty_surface.stage,
            app.ResearchCaseStage.NO_OPTION_RESEARCH_SURFACE,
        )
        self.assertEqual(
            empty_surface.blocking_reasons,
            ("no_option_research_surface",),
        )
        with self.assertRaisesRegex(ValueError, "not awaiting exact structure selection"):
            app.select_exact_structure(
                empty_surface,
                provider_identifiers=None,
            )

        unpaired_browser, _context = browser_with_rows(
            [chain_row(EXPIRATION, "CALL", "100")],
            expiration=EXPIRATION,
            discovery_request=case.option_research_request,
        )
        unpaired = app.attach_browser_evidence(case, unpaired_browser)
        discrimination = app._discrimination.discriminate_probability_free_convexity(
            unpaired_browser,
            make_quote_batch(unpaired_browser),
            (make_bar(unpaired_browser, EVALUATION_DATE),),
            latest_completed_session_date=EVALUATION_DATE,
        )
        self.assertEqual(discrimination.comparisons, ())
        no_comparison = app.attach_discrimination_evidence(unpaired, discrimination)
        self.assertEqual(
            no_comparison.stage,
            app.ResearchCaseStage.NO_OPTION_RESEARCH_SURFACE,
        )
        with self.assertRaisesRegex(ValueError, "not awaiting exact structure selection"):
            app.select_exact_structure(
                no_comparison,
                provider_identifiers=None,
            )

    def test_autonomous_and_event_entry_keep_distinct_existing_handoffs(self):
        submission, autonomous, event_entry = _event_cases()

        self.assertEqual(
            autonomous.entry_origin,
            app.ResearchCaseEntryOrigin.AUTONOMOUS_DISCOVERY,
        )
        self.assertEqual(autonomous.stage, app.ResearchCaseStage.OPTION_DISCOVERY)
        self.assertIs(
            autonomous.discovery_translation.submission,
            submission,
        )
        self.assertIs(
            autonomous.option_research_request.discovery_entry_handoff.selected_hypothesis,
            submission.hypotheses[0],
        )

        self.assertEqual(event_entry.entry_origin, app.ResearchCaseEntryOrigin.EVENT_ENTRY)
        self.assertEqual(event_entry.stage, app.ResearchCaseStage.OPTION_DISCOVERY)
        self.assertIs(
            event_entry.event_entry_preparation.user_input,
            event_entry.original_input,
        )
        self.assertIs(
            event_entry.event_entry_context.assessment.submission,
            event_entry.event_entry_translation.submission,
        )
        self.assertIs(
            event_entry.option_research_request.discovery_entry_handoff.selected_hypothesis,
            event_entry.selected_hypothesis,
        )
        self.assertIsNot(
            autonomous.option_research_request,
            event_entry.option_research_request,
        )

    def test_neutral_research_retains_not_established_maturity_alignment(self):
        submission = make_submission()
        reassessment_date = datetime.date(2030, 1, 10)
        submission = replace(
            submission,
            hypotheses=(
                replace(
                    submission.hypotheses[0],
                    expected_window=None,
                    reassessment=HypothesisReassessment(
                        reassessment_date,
                        "caller-research-policy-assumption:"
                        f"{reassessment_date.isoformat()}:Review the evidence before continued research.",
                        ReassessmentBasisKind.CALLER_RESEARCH_POLICY_ASSUMPTION,
                        ("interpretation-1",),
                    ),
                ),
            ),
        )
        user_input = UserEventInput("Neutral structural research input")
        preparation = prepare_event_entry_hypotheses(
            user_input,
            sources=submission.sources,
            statements=tuple(PreparedEventStatement(item) for item in submission.statements),
            hypotheses=submission.hypotheses,
            grounding_methodology="Retained source evidence supports structural review.",
            chronology_review="No realized causal effect is asserted.",
        )
        event_entry = app.start_event_entry_case("neutral-event", preparation)
        autonomous = app.continue_event_entry_case(
            event_entry,
            hypothesis_id=submission.hypotheses[0].hypothesis_id,
            submission_id="neutral-event-entry-submission",
            event_id=submission.event_id,
            observed_at=submission.observed_at,
            event_description=submission.event_description,
            event_date_range=submission.event_date_range,
            evaluation_date=EVALUATION_DATE,
            maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
        )
        request = autonomous.option_research_request
        self.assertEqual(
            request.maturity_authority,
            OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
        )
        self.assertEqual(
            request.hypothesis_maturity_alignment.name,
            "NOT_ESTABLISHED",
        )
        self.assertIs(
            request.discovery_entry_handoff.selected_hypothesis,
            autonomous.selected_hypothesis,
        )

    def test_every_human_checkpoint_is_explicit_and_none_stops(self):
        submission = make_submission()
        candidate = make_candidate(
            sources=submission.sources,
            observed_at=submission.observed_at,
        )
        batch = make_batch(candidates=(candidate,), observed_at=submission.observed_at)
        autonomous = app.start_autonomous_discovery_case("auto-none", batch)
        autonomous_none = app.continue_autonomous_discovery_case(
            autonomous,
            candidate_id=None,
        )
        self.assertEqual(autonomous_none.stage, app.ResearchCaseStage.STOPPED_NONE)
        self.assertIsNone(autonomous_none.discovery_selection.selected_candidate)
        autonomous_rendered = app.render_research_case_markdown(autonomous_none)
        self.assertIn("人工事件选择：NONE", autonomous_rendered)
        self.assertNotIn("人工结构选择：NONE", autonomous_rendered)
        with self.assertRaisesRegex(ValueError, "not awaiting discovery selection"):
            app.continue_autonomous_discovery_case(
                autonomous_none,
                candidate_id=candidate.candidate_id,
            )

        assessed = app.continue_autonomous_discovery_case(
            autonomous, candidate_id=candidate.candidate_id, submission=submission,
        )
        hypothesis_none = app.select_discovery_hypothesis(
            assessed, hypothesis_id=None, evaluation_date=EVALUATION_DATE,
        )
        rendered = app.render_research_case_markdown(hypothesis_none)
        self.assertIn("人工事件假设选择：NONE", rendered)
        self.assertNotIn("人工结构选择：NONE", rendered)
        self.assertNotIn("人工事件选择：NONE", rendered)
        with self.assertRaisesRegex(ValueError, "not awaiting discovery hypothesis"):
            app.select_discovery_hypothesis(
                hypothesis_none, hypothesis_id=submission.hypotheses[0].hypothesis_id,
                evaluation_date=EVALUATION_DATE,
            )

        user_input = UserEventInput("No hypothesis should be selected automatically")
        preparation = prepare_event_entry_hypotheses(
            user_input,
            sources=submission.sources,
            statements=tuple(PreparedEventStatement(item) for item in submission.statements),
            hypotheses=submission.hypotheses,
            grounding_methodology="Explicit retained grounding.",
            chronology_review="Chronology was reviewed.",
        )
        event_entry = app.start_event_entry_case("event-none", preparation)
        with mock.patch(
            "convexity_hunter.event_intelligence.assess_event_intelligence_submission",
            side_effect=AssertionError("NONE must stop before EI"),
        ):
            event_none = app.continue_event_entry_case(
                event_entry,
                hypothesis_id=None,
            )
        self.assertEqual(event_none.stage, app.ResearchCaseStage.STOPPED_NONE)
        self.assertIsNone(event_none.event_entry_selection.hypothesis)
        event_rendered = app.render_research_case_markdown(event_none)
        self.assertIn("人工事件选择：NONE", event_rendered)
        self.assertNotIn("人工结构选择：NONE", event_rendered)
        with self.assertRaisesRegex(ValueError, "not awaiting Event Entry hypothesis"):
            app.continue_event_entry_case(
                event_none,
                hypothesis_id=submission.hypotheses[0].hypothesis_id,
            )

        _submission, case, _event = _event_cases()
        rows = [
            chain_row(EXPIRATION, "CALL", "100"),
            chain_row(EXPIRATION, "PUT", "100"),
        ]
        browser, _context = browser_with_rows(
            rows,
            expiration=EXPIRATION,
            discovery_request=case.option_research_request,
        )
        surface_case = app.attach_browser_evidence(case, browser)
        surface_case = app.attach_discrimination_evidence(
            surface_case,
            app._discrimination.discriminate_probability_free_convexity(
                browser,
                make_quote_batch(browser),
                (make_bar(browser, EVALUATION_DATE),),
                latest_completed_session_date=EVALUATION_DATE,
            ),
        )
        structure_none = app.select_exact_structure(
            surface_case,
            provider_identifiers=None,
        )
        self.assertEqual(structure_none.stage, app.ResearchCaseStage.STOPPED_NONE)
        self.assertIsNone(structure_none.exact_structure_selection)
        structure_rendered = app.render_research_case_markdown(structure_none)
        self.assertIn("人工结构选择：NONE", structure_rendered)
        self.assertNotIn("人工事件选择：NONE", structure_rendered)
        with self.assertRaisesRegex(ValueError, "not awaiting exact structure selection"):
            app.select_exact_structure(
                structure_none,
                provider_identifiers=None,
            )

    def test_browser_discrimination_and_exact_verification_retain_identity(self):
        _submission, case, _event = _event_cases()
        rows = [
            chain_row(EXPIRATION, "CALL", "100"),
            chain_row(EXPIRATION, "PUT", "100"),
        ]
        browser, _context = browser_with_rows(
            rows,
            expiration=EXPIRATION,
            discovery_request=case.option_research_request,
        )
        attached = app.attach_browser_evidence(case, browser)
        self.assertIs(attached.browser, browser)
        self.assertEqual(
            attached.stage,
            app.ResearchCaseStage.AWAITING_RTH_EVIDENCE,
        )
        result = app._discrimination.discriminate_probability_free_convexity(
            browser,
            make_quote_batch(browser),
            (make_bar(browser, EVALUATION_DATE),),
            latest_completed_session_date=EVALUATION_DATE,
        )
        compared = app.attach_discrimination_evidence(attached, result)
        self.assertIs(compared.discrimination, result)
        self.assertIs(compared.discrimination.browser, browser)
        selected = app.select_exact_structure(
            compared,
            provider_identifiers=tuple(row.provider_identifier for row in browser.rows),
            assumed_portfolio_value=100000.0,
            expected_holding_days=20,
        )
        self.assertIs(selected.exact_structure_selection.browser, browser)
        typed_verification = futu.verify_futu_exact_contract_selection(
            ExactSelectionContext(rows),
            selected.exact_structure_selection,
        )
        alternate_selection = futu.select_futu_exact_contracts(
            browser,
            provider_identifiers=(browser.rows[0].provider_identifier,),
            assumed_portfolio_value=100000.0,
            expected_holding_days=20,
        )
        alternate_verification = futu.verify_futu_exact_contract_selection(
            ExactSelectionContext(rows),
            alternate_selection,
        )
        with self.assertRaisesRegex(ValueError, "retain exact selection"):
            app.verify_exact_structure(
                selected,
                selection_verification=alternate_verification,
            )
        with mock.patch.object(
            app._futu,
            "verify_futu_exact_contract_selection",
            side_effect=AssertionError("typed verification must not call the provider bridge"),
        ):
            verified_from_typed_result = app.verify_exact_structure(
                selected,
                selection_verification=typed_verification,
            )
        self.assertIs(
            verified_from_typed_result.futu_selection_verification,
            typed_verification,
        )
        verified = verified_from_typed_result
        self.assertEqual(verified.stage, app.ResearchCaseStage.ENGINE_RESEARCH)
        self.assertIs(
            verified.futu_selection_verification.selection,
            verified.exact_structure_selection,
        )
        self.assertIs(
            verified.maturity_context.discovery_request,
            verified.option_research_request,
        )

    def test_direct_entry_has_no_event_thesis_and_uses_existing_verification(self):
        _submission, _autonomous, event_entry = _event_cases()
        # Use a structure and source-backed references from the existing
        # candidate-assembly fixtures; the app does not create either one.
        assembly = assemble_artifacts(
            (None,) * 7,
            CandidateState.DATA_INSUFFICIENT,
            ("missing direct research evidence",),
            calculation_id="direct-start-assembly",
        )
        structure = assembly.record.structure
        references = _contract_references(structure)
        direct = app.start_direct_entry_case("direct-case", structure, references)
        self.assertEqual(direct.entry_origin, app.ResearchCaseEntryOrigin.DIRECT_ENTRY)
        self.assertIs(direct.original_input, structure)
        self.assertIsNone(direct.selected_hypothesis)
        self.assertIsNone(direct.option_research_request)
        self.assertIsNone(direct.browser)
        verified = app.verify_exact_structure(direct)
        self.assertIs(verified.exact_contract_verification.structure, structure)
        self.assertIs(
            verified.exact_contract_verification.contract_references,
            references,
        )
        self.assertIsNone(event_entry.exact_contract_verification)

    def test_one_existing_reviewed_service_runs_partial_research_for_all_origins(self):
        _submission, autonomous, event_entry = _event_cases()
        cases = [
            _attach_surface(autonomous),
            _attach_surface(event_entry),
        ]
        assembly = assemble_artifacts(
            (None,) * 7,
            CandidateState.DATA_INSUFFICIENT,
            ("missing direct research evidence",),
            calculation_id="direct-converged-assembly",
        )
        direct = app.start_direct_entry_case(
            "direct-converged",
            assembly.record.structure,
            _contract_references(assembly.record.structure),
        )
        cases.append(app.verify_exact_structure(direct))

        with mock.patch.object(
            app._reviewed_service,
            "run_direct_entry_reviewed_research_service",
            wraps=app._reviewed_service.run_direct_entry_reviewed_research_service,
        ) as downstream:
            results = [
                app.run_research_case(case, _research_input(case, f"case-{index}"))
                for index, case in enumerate(cases)
            ]

        self.assertEqual(downstream.call_count, 3)
        self.assertEqual(
            [result.stage for result in results],
            [
                app.ResearchCaseStage.COMPLETED,
                app.ResearchCaseStage.COMPLETED,
                app.ResearchCaseStage.COMPLETED,
            ],
        )
        for result in results:
            self.assertIsNotNone(result.candidate_record)
            self.assertIsNotNone(result.screening_decision)
            rendered = app.render_research_case_markdown(result)
            self.assertIn("# 研究案例", rendered)
            if result.discrimination is not None:
                self.assertIn("# 条件式凸性比较", rendered)
            self.assertIn("Convexity Hunter", result.report_markdown)
            self.assertEqual(result.blocking_reasons, ())
            self.assertIn("missing_costs", rendered)
        self.assertIsNone(results[2].maturity_context)
        self.assertIsNotNone(results[0].maturity_context)
        self.assertIsNotNone(results[1].maturity_context)
        with self.assertRaisesRegex(ValueError, "not awaiting Event Entry hypothesis"):
            app.continue_event_entry_case(
                results[1],
                hypothesis_id=_submission.hypotheses[0].hypothesis_id,
            )

    def test_full_reviewed_artifacts_and_optional_plan_reach_completed(self):
        artifacts = complete_artifacts()
        assembly = assemble_artifacts(
            artifacts,
            CandidateState.INVESTIGATE,
            (),
            calculation_id="direct-full-assembly",
        )
        direct = app.start_direct_entry_case(
            "direct-full",
            assembly.record.structure,
            _contract_references(assembly.record.structure),
        )
        verified = app.verify_exact_structure(direct)
        plan_request = PositionManagementPlanRequest(
            "direct-full-plan",
            (
                _qualitative(
                    "monetize",
                    position_management.PositionManagementCategory.MONETIZATION,
                    position_management.PositionManagementQualitativeTrigger.EVENT_BECOMES_PUBLIC,
                ),
                _watch_condition(),
                _qualitative(
                    "exit_event",
                    position_management.PositionManagementCategory.EXIT,
                    position_management.PositionManagementQualitativeTrigger.EVENT_CANCELLED,
                ),
            ),
            assembly.lineage.calculated_at + datetime.timedelta(seconds=1),
        )
        result = app.run_research_case(
            verified,
            _research_input(
                verified,
                "direct-full-input",
                artifacts=artifacts,
                state=CandidateState.INVESTIGATE,
                missing=(),
                position_management_plan_request=plan_request,
            ),
        )
        self.assertEqual(result.stage, app.ResearchCaseStage.COMPLETED)
        self.assertIsNotNone(result.downstream_result.research_readiness_verification)
        self.assertIsNotNone(result.position_management_plan)
        self.assertIsNot(
            result.screening_decision.proposed_state,
            CandidateState.DATA_INSUFFICIENT,
        )
        self.assertEqual(result.blocking_reasons, ())
        with self.assertRaisesRegex(ValueError, "not ready for Engine research"):
            app.run_research_case(result, _placeholder_research_input())

    def test_downstream_cannot_be_run_without_verified_structure(self):
        _submission, case, _event = _event_cases()
        with self.assertRaisesRegex(ValueError, "not ready for Engine research"):
            app.run_research_case(case, _placeholder_research_input())
        with self.assertRaisesRegex(TypeError, "ResearchCaseResearchInput"):
            app.run_research_case(case, object())  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
