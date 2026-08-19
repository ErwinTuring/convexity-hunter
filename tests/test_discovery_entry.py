"""Tests for the deterministic discovery-entry handoff."""

import datetime
import inspect
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError, fields
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import convexity_hunter
from convexity_hunter import discovery_entry
from convexity_hunter import event_intelligence
from convexity_hunter.discovery_entry import (
    DiscoveryEntryHandoff,
    create_discovery_entry_handoff,
)
from convexity_hunter.event_intelligence import (
    DistributionChangeMode,
    EventIntelligenceAcceptanceIssue,
    EventIntelligenceAcceptanceResult,
    EventIntelligenceAcceptanceStatus,
    EventIntelligenceIssueCode,
    EventIntelligenceSubmission,
    EventSourceReference,
    EventStatement,
    EventStatementKind,
    EventUnderlyingHypothesis,
    MethodologizedDateRange,
    assess_event_intelligence_submission,
)
from convexity_hunter.market_data import UnderlyingKey, UnderlyingSecurityType


OBSERVED_AT = datetime.datetime(2030, 1, 2, tzinfo=datetime.timezone.utc)
DATE_RANGE = MethodologizedDateRange(
    datetime.date(2030, 1, 3),
    datetime.date(2030, 1, 3),
    "Exact issuer filing date.",
)
WINDOW = MethodologizedDateRange(
    datetime.date(2030, 1, 3),
    datetime.date(2030, 1, 10),
    "Inclusive declared post-event window.",
)


def make_hypothesis(hypothesis_id: str = "hypothesis-1") -> EventUnderlyingHypothesis:
    return EventUnderlyingHypothesis(
        hypothesis_id,
        UnderlyingKey("ABC", "XNAS", UnderlyingSecurityType.EQUITY, "USD"),
        "The event changes the range of possible commercial outcomes.",
        DistributionChangeMode.BIDIRECTIONAL_EXPANSION,
        "The event may widen the future return distribution.",
        WINDOW,
        ("interpretation-1",),
        (),
        "Contradictory evidence was reviewed; none was identified.",
        ("The event timing may change.",),
        ("The event is formally cancelled.",),
    )


def make_submission(
    hypotheses: object = None,
    submission_id: str = "submission-1",
) -> EventIntelligenceSubmission:
    source = EventSourceReference(
        "source-1",
        "https://www.sec.gov/example",
        "Issuer filing",
        datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc),
    )
    fact = EventStatement(
        "fact-1",
        EventStatementKind.OBSERVED_FACT,
        "The filing declares a dated event.",
        (source.source_id,),
    )
    interpretation = EventStatement(
        "interpretation-1",
        EventStatementKind.INTERPRETATION,
        "The event may widen the return distribution.",
        (),
        (fact.statement_id,),
    )
    selected_hypotheses = (
        (make_hypothesis(),) if hypotheses is None else hypotheses
    )
    return EventIntelligenceSubmission(
        submission_id,
        "event-1",
        "test-producer",
        "1.0",
        OBSERVED_AT,
        "A dated issuer event is expected.",
        DATE_RANGE,
        (source,),
        (fact, interpretation),
        selected_hypotheses,
    )


def make_result(
    hypotheses: object = None,
    submission_id: str = "submission-1",
) -> EventIntelligenceAcceptanceResult:
    return assess_event_intelligence_submission(
        make_submission(hypotheses, submission_id)
    )


def forge_result(**overrides: object) -> EventIntelligenceAcceptanceResult:
    valid = make_result()
    forged = object.__new__(EventIntelligenceAcceptanceResult)
    values = {
        "submission": valid.submission,
        "status": valid.status,
        "issues": valid.issues,
        "assessment_version": valid.assessment_version,
    }
    values.update(overrides)
    for name, value in values.items():
        object.__setattr__(forged, name, value)
    return forged


class PublicContractTests(unittest.TestCase):
    def test_exact_public_surface_shape_and_signature(self) -> None:
        self.assertEqual(
            discovery_entry.__all__,
            ("DiscoveryEntryHandoff", "create_discovery_entry_handoff"),
        )
        for name in discovery_entry.__all__:
            self.assertFalse(hasattr(convexity_hunter, name))
        self.assertEqual(
            tuple(field.name for field in fields(DiscoveryEntryHandoff)),
            ("acceptance_result", "selected_hypothesis"),
        )
        self.assertEqual(
            DiscoveryEntryHandoff.__annotations__,
            {
                "acceptance_result": EventIntelligenceAcceptanceResult,
                "selected_hypothesis": EventUnderlyingHypothesis,
            },
        )
        signature = inspect.signature(create_discovery_entry_handoff)
        self.assertEqual(
            tuple(signature.parameters),
            ("acceptance_result", "selected_hypothesis"),
        )
        self.assertIs(
            signature.return_annotation,
            DiscoveryEntryHandoff,
        )


class SuccessfulHandoffTests(unittest.TestCase):
    def test_valid_handoff_retains_both_inputs_by_identity(self) -> None:
        result = make_result()
        hypothesis = result.submission.hypotheses[0]
        handoff = create_discovery_entry_handoff(result, hypothesis)
        self.assertIs(handoff.acceptance_result, result)
        self.assertIs(handoff.selected_hypothesis, hypothesis)

    def test_caller_can_select_each_of_multiple_hypotheses(self) -> None:
        submitted = (
            make_hypothesis("hypothesis-c"),
            make_hypothesis("hypothesis-a"),
            make_hypothesis("hypothesis-b"),
        )
        result = make_result(submitted)
        self.assertEqual(
            tuple(item.hypothesis_id for item in result.submission.hypotheses),
            ("hypothesis-a", "hypothesis-b", "hypothesis-c"),
        )
        for hypothesis in result.submission.hypotheses:
            handoff = create_discovery_entry_handoff(result, hypothesis)
            self.assertIs(handoff.selected_hypothesis, hypothesis)

    def test_direct_constructor_and_function_have_the_same_boundary(self) -> None:
        result = make_result()
        hypothesis = result.submission.hypotheses[0]
        direct = DiscoveryEntryHandoff(result, hypothesis)
        produced = create_discovery_entry_handoff(result, hypothesis)
        self.assertEqual(direct, produced)
        self.assertIs(direct.acceptance_result, result)

    def test_repeated_calls_are_deterministic_pure_and_frozen(self) -> None:
        result = make_result()
        hypothesis = result.submission.hypotheses[0]
        before = repr(result)
        first = create_discovery_entry_handoff(result, hypothesis)
        second = create_discovery_entry_handoff(result, hypothesis)
        self.assertEqual(first, second)
        self.assertEqual(repr(result), before)
        with self.assertRaises(FrozenInstanceError):
            first.selected_hypothesis = hypothesis  # type: ignore[misc]

    def test_acceptance_semantics_are_not_replayed(self) -> None:
        result = make_result()
        hypothesis = result.submission.hypotheses[0]
        with mock.patch.object(
            event_intelligence,
            "assess_event_intelligence_submission",
            side_effect=AssertionError("assessor replayed"),
        ), mock.patch.object(
            event_intelligence,
            "_derive_event_intelligence_issues",
            side_effect=AssertionError("issue derivation replayed"),
        ):
            handoff = create_discovery_entry_handoff(result, hypothesis)
        self.assertIs(handoff.selected_hypothesis, hypothesis)


class FailureBoundaryTests(unittest.TestCase):
    def test_equal_copy_and_cross_result_hypotheses_fail_identity(self) -> None:
        result = make_result()
        retained = result.submission.hypotheses[0]
        equal_copy = make_hypothesis(retained.hypothesis_id)
        self.assertEqual(equal_copy, retained)
        self.assertIsNot(equal_copy, retained)
        with self.assertRaisesRegex(ValueError, "retained by identity"):
            create_discovery_entry_handoff(result, equal_copy)

        other = make_result(submission_id="submission-2")
        other_hypothesis = other.submission.hypotheses[0]
        self.assertEqual(other_hypothesis, retained)
        with self.assertRaisesRegex(ValueError, "retained by identity"):
            create_discovery_entry_handoff(result, other_hypothesis)

    def test_wrong_top_level_types_and_subclasses_fail_before_nested_access(self) -> None:
        result = make_result()
        hypothesis = result.submission.hypotheses[0]

        class ResultSubclass(EventIntelligenceAcceptanceResult):
            pass

        class HypothesisSubclass(EventUnderlyingHypothesis):
            pass

        result_subclass = ResultSubclass(
            result.submission,
            result.status,
            result.issues,
            result.assessment_version,
        )
        for invalid in (None, object(), [], result_subclass):
            with self.assertRaises(TypeError):
                create_discovery_entry_handoff(invalid, hypothesis)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            create_discovery_entry_handoff(result, object())  # type: ignore[arg-type]
        subclass_hypothesis = HypothesisSubclass(
            *tuple(getattr(hypothesis, field.name) for field in fields(hypothesis))
        )
        with self.assertRaises(TypeError):
            create_discovery_entry_handoff(result, subclass_hypothesis)

    def test_incomplete_status_and_nonempty_issues_fail(self) -> None:
        incomplete_submission = make_submission()
        object.__setattr__(incomplete_submission, "event_id", None)
        incomplete = assess_event_intelligence_submission(incomplete_submission)
        with self.assertRaisesRegex(ValueError, "must be accepted"):
            create_discovery_entry_handoff(
                incomplete,
                incomplete.submission.hypotheses[0],
            )

        issue = EventIntelligenceAcceptanceIssue(
            EventIntelligenceIssueCode.MISSING_EVENT_ID
        )
        forged = forge_result(issues=(issue,))
        with self.assertRaisesRegex(ValueError, "no acceptance issues"):
            create_discovery_entry_handoff(
                forged,
                forged.submission.hypotheses[0],
            )

    def test_wrong_terminal_field_types_and_version_fail(self) -> None:
        valid_hypothesis = make_result().submission.hypotheses[0]
        for forged, error in (
            (forge_result(status="accepted"), TypeError),
            (forge_result(issues=[]), TypeError),
            (forge_result(assessment_version=1), TypeError),
            (forge_result(assessment_version="other"), ValueError),
            (forge_result(submission=object()), TypeError),
        ):
            with self.assertRaises(error):
                create_discovery_entry_handoff(forged, valid_hypothesis)

    def test_missing_result_or_submission_attributes_fail_controlled(self) -> None:
        result = object.__new__(EventIntelligenceAcceptanceResult)
        hypothesis = make_hypothesis()
        with self.assertRaises(ValueError):
            create_discovery_entry_handoff(result, hypothesis)

        malformed_submission = object.__new__(EventIntelligenceSubmission)
        forged = forge_result(submission=malformed_submission)
        with self.assertRaises(ValueError):
            create_discovery_entry_handoff(forged, hypothesis)

    def test_noncanonical_or_nested_malformed_submission_fails(self) -> None:
        result = make_result(
            (make_hypothesis("hypothesis-b"), make_hypothesis("hypothesis-a"))
        )
        canonical = result.submission
        forged_submission = object.__new__(EventIntelligenceSubmission)
        for field in fields(EventIntelligenceSubmission):
            object.__setattr__(
                forged_submission,
                field.name,
                getattr(canonical, field.name),
            )
        object.__setattr__(
            forged_submission,
            "hypotheses",
            tuple(reversed(canonical.hypotheses)),
        )
        forged = forge_result(submission=forged_submission)
        with self.assertRaisesRegex(ValueError, "not intrinsically valid"):
            create_discovery_entry_handoff(forged, canonical.hypotheses[0])

        malformed_source = object.__new__(EventSourceReference)
        nested_submission = object.__new__(EventIntelligenceSubmission)
        for field in fields(EventIntelligenceSubmission):
            object.__setattr__(
                nested_submission,
                field.name,
                getattr(canonical, field.name),
            )
        object.__setattr__(nested_submission, "sources", (malformed_source,))
        nested_forged = forge_result(submission=nested_submission)
        with self.assertRaises((TypeError, ValueError)):
            create_discovery_entry_handoff(
                nested_forged,
                canonical.hypotheses[0],
            )


if __name__ == "__main__":
    unittest.main()
