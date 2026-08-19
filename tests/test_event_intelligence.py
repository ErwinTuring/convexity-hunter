"""Tests for the Event Intelligence acceptance boundary."""

import datetime
import inspect
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError, fields

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import convexity_hunter
from convexity_hunter import event_intelligence as event_module
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


OBSERVED_AT = datetime.datetime(2030, 1, 5, 15, 0, tzinfo=datetime.timezone.utc)
EVENT_RANGE = MethodologizedDateRange(
    datetime.date(2030, 1, 8),
    datetime.date(2030, 1, 10),
    "Issuer filing gives an inclusive expected decision interval.",
)
EXPECTED_WINDOW = MethodologizedDateRange(
    datetime.date(2030, 1, 8),
    datetime.date(2030, 1, 31),
    "Inclusive event and initial market-impact window.",
)


def make_source(**overrides: object) -> EventSourceReference:
    values = {
        "source_id": "source-1",
        "locator": "https://www.sec.gov/example",
        "title": "Issuer filing",
        "published_at": datetime.datetime(
            2030, 1, 5, 9, 0, tzinfo=datetime.timezone.utc
        ),
    }
    values.update(overrides)
    return EventSourceReference(**values)  # type: ignore[arg-type]


def make_fact(**overrides: object) -> EventStatement:
    values = {
        "statement_id": "fact-1",
        "kind": EventStatementKind.OBSERVED_FACT,
        "text": "The issuer disclosed a dated regulatory decision window.",
        "source_ids": ("source-1",),
    }
    values.update(overrides)
    return EventStatement(**values)  # type: ignore[arg-type]


def make_interpretation(**overrides: object) -> EventStatement:
    values = {
        "statement_id": "interpretation-1",
        "kind": EventStatementKind.INTERPRETATION,
        "text": "The decision may widen the issuer's return distribution.",
        "dependency_statement_ids": ("fact-1",),
    }
    values.update(overrides)
    return EventStatement(**values)  # type: ignore[arg-type]


def make_underlying() -> UnderlyingKey:
    return UnderlyingKey("ABC", "XNAS", UnderlyingSecurityType.EQUITY, "USD")


def make_hypothesis(**overrides: object) -> EventUnderlyingHypothesis:
    values = {
        "hypothesis_id": "hypothesis-1",
        "underlying_key": make_underlying(),
        "impact_path": "Decision changes the expected range of commercial outcomes.",
        "distribution_mode": DistributionChangeMode.BIDIRECTIONAL_EXPANSION,
        "distribution_hypothesis": (
            "The event may increase the frequency or magnitude of tail outcomes."
        ),
        "expected_window": EXPECTED_WINDOW,
        "supporting_statement_ids": ("interpretation-1",),
        "contradicting_statement_ids": (),
        "contradiction_review": (
            "Contradictory evidence was reviewed; none was identified."
        ),
        "uncertainties": ("The decision date may move within the stated range.",),
        "falsification_conditions": (
            "The regulator cancels the decision without a replacement date.",
        ),
    }
    values.update(overrides)
    return EventUnderlyingHypothesis(**values)  # type: ignore[arg-type]


def make_submission(**overrides: object) -> EventIntelligenceSubmission:
    values = {
        "submission_id": "submission-1",
        "event_id": "event-1",
        "producer_id": "synthetic-test-producer",
        "producer_version": "1.0",
        "observed_at": OBSERVED_AT,
        "event_description": "A dated regulatory decision is expected.",
        "event_date_range": EVENT_RANGE,
        "sources": (make_source(),),
        "statements": (make_fact(), make_interpretation()),
        "hypotheses": (make_hypothesis(),),
    }
    values.update(overrides)
    return EventIntelligenceSubmission(**values)  # type: ignore[arg-type]


class PublicContractTests(unittest.TestCase):
    def test_exact_module_exports_and_no_package_root_exports(self) -> None:
        self.assertEqual(
            event_module.__all__,
            (
                "EventSourceReference",
                "EventStatementKind",
                "EventStatement",
                "MethodologizedDateRange",
                "DistributionChangeMode",
                "EventUnderlyingHypothesis",
                "EventIntelligenceSubmission",
                "EventIntelligenceAcceptanceStatus",
                "EventIntelligenceIssueCode",
                "EventIntelligenceAcceptanceIssue",
                "EventIntelligenceAcceptanceResult",
                "assess_event_intelligence_submission",
            ),
        )
        for name in event_module.__all__:
            self.assertFalse(hasattr(convexity_hunter, name))

    def test_exact_record_fields_and_assessor_signature(self) -> None:
        self.assertEqual(
            tuple(field.name for field in fields(EventSourceReference)),
            ("source_id", "locator", "title", "published_at"),
        )
        self.assertEqual(
            tuple(field.name for field in fields(EventStatement)),
            (
                "statement_id",
                "kind",
                "text",
                "source_ids",
                "dependency_statement_ids",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in fields(EventUnderlyingHypothesis)),
            (
                "hypothesis_id",
                "underlying_key",
                "impact_path",
                "distribution_mode",
                "distribution_hypothesis",
                "expected_window",
                "supporting_statement_ids",
                "contradicting_statement_ids",
                "contradiction_review",
                "uncertainties",
                "falsification_conditions",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in fields(EventIntelligenceSubmission)),
            (
                "submission_id",
                "event_id",
                "producer_id",
                "producer_version",
                "observed_at",
                "event_description",
                "event_date_range",
                "sources",
                "statements",
                "hypotheses",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in fields(EventIntelligenceAcceptanceResult)),
            ("submission", "status", "issues", "assessment_version"),
        )
        self.assertEqual(
            tuple(inspect.signature(assess_event_intelligence_submission).parameters),
            ("submission",),
        )

    def test_exact_enum_values(self) -> None:
        self.assertEqual(
            tuple((item.name, item.value) for item in EventStatementKind),
            (
                ("OBSERVED_FACT", "observed_fact"),
                ("INTERPRETATION", "interpretation"),
            ),
        )
        self.assertEqual(
            tuple((item.name, item.value) for item in DistributionChangeMode),
            (
                ("EXTREME_TAIL_UP", "extreme_tail_up"),
                ("EXTREME_TAIL_DOWN", "extreme_tail_down"),
                ("EVENT_DIRECTIONAL_UP", "event_directional_up"),
                ("EVENT_DIRECTIONAL_DOWN", "event_directional_down"),
                ("BIDIRECTIONAL_EXPANSION", "bidirectional_expansion"),
            ),
        )
        self.assertEqual(
            tuple(item.value for item in EventIntelligenceAcceptanceStatus),
            ("accepted", "incomplete"),
        )


class AcceptanceTests(unittest.TestCase):
    def test_complete_submission_is_accepted_and_retained_by_identity(self) -> None:
        submission = make_submission()
        result = assess_event_intelligence_submission(submission)
        self.assertIs(result.submission, submission)
        self.assertIs(result.status, EventIntelligenceAcceptanceStatus.ACCEPTED)
        self.assertEqual(result.issues, ())
        self.assertEqual(result.issue_codes, ())
        self.assertEqual(
            result.assessment_version, "event-intelligence-acceptance-v0.1"
        )

    def test_missing_semantics_return_canonical_incomplete_issues(self) -> None:
        hypothesis = make_hypothesis(
            underlying_key=None,
            impact_path=None,
            distribution_mode=None,
            distribution_hypothesis=None,
            expected_window=None,
            supporting_statement_ids=(),
            contradiction_review=None,
            uncertainties=(),
            falsification_conditions=(),
        )
        submission = make_submission(
            event_id=None,
            producer_id=None,
            producer_version=None,
            observed_at=None,
            event_description=None,
            event_date_range=None,
            sources=(),
            statements=(),
            hypotheses=(hypothesis,),
        )
        result = assess_event_intelligence_submission(submission)
        self.assertIs(result.status, EventIntelligenceAcceptanceStatus.INCOMPLETE)
        self.assertEqual(
            result.issue_codes,
            (
                EventIntelligenceIssueCode.MISSING_EVENT_ID,
                EventIntelligenceIssueCode.MISSING_PRODUCER_ID,
                EventIntelligenceIssueCode.MISSING_PRODUCER_VERSION,
                EventIntelligenceIssueCode.MISSING_OBSERVED_AT,
                EventIntelligenceIssueCode.MISSING_EVENT_DESCRIPTION,
                EventIntelligenceIssueCode.INCOMPLETE_EVENT_DATE_RANGE,
                EventIntelligenceIssueCode.NO_STRUCTURED_SOURCES,
                EventIntelligenceIssueCode.NO_STATEMENTS,
                EventIntelligenceIssueCode.MISSING_UNDERLYING_KEY,
                EventIntelligenceIssueCode.MISSING_IMPACT_PATH,
                EventIntelligenceIssueCode.MISSING_DISTRIBUTION_MODE,
                EventIntelligenceIssueCode.MISSING_DISTRIBUTION_HYPOTHESIS,
                EventIntelligenceIssueCode.INCOMPLETE_EXPECTED_WINDOW,
                EventIntelligenceIssueCode.MISSING_SUPPORTING_EVIDENCE,
                EventIntelligenceIssueCode.MISSING_CONTRADICTION_REVIEW,
                EventIntelligenceIssueCode.MISSING_UNCERTAINTIES,
                EventIntelligenceIssueCode.MISSING_FALSIFICATION_CONDITIONS,
            ),
        )

    def test_issues_bind_to_subjects_and_are_caller_order_invariant(self) -> None:
        incomplete = make_hypothesis(
            hypothesis_id="hypothesis-2", impact_path=None
        )
        complete = make_hypothesis(hypothesis_id="hypothesis-1")
        forward = make_submission(hypotheses=(incomplete, complete))
        reverse = make_submission(hypotheses=(complete, incomplete))
        first = assess_event_intelligence_submission(forward)
        second = assess_event_intelligence_submission(reverse)
        self.assertEqual(first, second)
        self.assertEqual(
            first.issues,
            (
                EventIntelligenceAcceptanceIssue(
                    EventIntelligenceIssueCode.MISSING_IMPACT_PATH,
                    "hypothesis-2",
                ),
            ),
        )

    def test_partial_ranges_are_incomplete(self) -> None:
        submission = make_submission(
            event_date_range=MethodologizedDateRange(
                datetime.date(2030, 1, 8), None, None
            ),
            hypotheses=(
                make_hypothesis(
                    expected_window=MethodologizedDateRange(
                        None, datetime.date(2030, 1, 31), "Known end only."
                    )
                ),
            ),
        )
        result = assess_event_intelligence_submission(submission)
        self.assertEqual(
            result.issue_codes,
            (
                EventIntelligenceIssueCode.INCOMPLETE_EVENT_DATE_RANGE,
                EventIntelligenceIssueCode.INCOMPLETE_EXPECTED_WINDOW,
            ),
        )

    def test_source_statement_and_closure_gaps_are_subject_bound(self) -> None:
        source = make_source(locator=None)
        fact = make_fact(text=None, source_ids=())
        interpretation = make_interpretation(
            text=None, dependency_statement_ids=()
        )
        hypothesis = make_hypothesis(supporting_statement_ids=("interpretation-1",))
        result = assess_event_intelligence_submission(
            make_submission(
                sources=(source,),
                statements=(interpretation, fact),
                hypotheses=(hypothesis,),
            )
        )
        self.assertEqual(
            tuple((issue.code, issue.subject_id) for issue in result.issues),
            (
                (EventIntelligenceIssueCode.SOURCE_LOCATOR_MISSING, "source-1"),
                (EventIntelligenceIssueCode.STATEMENT_TEXT_MISSING, "fact-1"),
                (
                    EventIntelligenceIssueCode.STATEMENT_TEXT_MISSING,
                    "interpretation-1",
                ),
                (
                    EventIntelligenceIssueCode.OBSERVED_FACT_SOURCE_MISSING,
                    "fact-1",
                ),
                (
                    EventIntelligenceIssueCode.INTERPRETATION_SOURCE_CLOSURE_MISSING,
                    "interpretation-1",
                ),
                (
                    EventIntelligenceIssueCode.MISSING_SUPPORTING_OBSERVED_FACT,
                    "hypothesis-1",
                ),
            ),
        )

    def test_support_requires_fact_and_interpretation(self) -> None:
        fact_only = assess_event_intelligence_submission(
            make_submission(
                statements=(make_fact(),),
                hypotheses=(
                    make_hypothesis(supporting_statement_ids=("fact-1",)),
                ),
            )
        )
        self.assertIn(
            EventIntelligenceIssueCode.MISSING_SUPPORTING_INTERPRETATION,
            fact_only.issue_codes,
        )

        interpretation = make_interpretation(
            source_ids=("source-1",), dependency_statement_ids=()
        )
        interpretation_only = assess_event_intelligence_submission(
            make_submission(
                statements=(interpretation,),
                hypotheses=(
                    make_hypothesis(
                        supporting_statement_ids=("interpretation-1",)
                    ),
                ),
            )
        )
        self.assertIn(
            EventIntelligenceIssueCode.MISSING_SUPPORTING_OBSERVED_FACT,
            interpretation_only.issue_codes,
        )

    def test_empty_contradiction_set_with_explicit_review_is_accepted(self) -> None:
        result = assess_event_intelligence_submission(make_submission())
        self.assertNotIn(
            EventIntelligenceIssueCode.MISSING_CONTRADICTION_REVIEW,
            result.issue_codes,
        )

    def test_repeated_assessment_is_pure_and_deterministic(self) -> None:
        submission = make_submission()
        before = repr(submission)
        self.assertEqual(
            assess_event_intelligence_submission(submission),
            assess_event_intelligence_submission(submission),
        )
        self.assertEqual(repr(submission), before)


class NormalizationAndValidationTests(unittest.TestCase):
    def test_records_normalize_strings_collections_time_and_order(self) -> None:
        offset = datetime.timezone(datetime.timedelta(hours=8))
        source_b = make_source(
            source_id=" source-b ",
            published_at=datetime.datetime(2030, 1, 5, 16, 0, tzinfo=offset),
        )
        source_a = make_source(source_id="source-a")
        fact = make_fact(
            source_ids=[" source-b ", "source-a"],
        )
        hypothesis = make_hypothesis(
            supporting_statement_ids=["interpretation-1"],
            uncertainties=[" uncertainty-b ", "uncertainty-a"],
        )
        submission = make_submission(
            observed_at=datetime.datetime(2030, 1, 6, 0, 0, tzinfo=offset),
            sources=[source_b, source_a],
            statements=[make_interpretation(), fact],
            hypotheses=[hypothesis],
        )
        self.assertEqual(
            tuple(source.source_id for source in submission.sources),
            ("source-a", "source-b"),
        )
        self.assertEqual(fact.source_ids, ("source-a", "source-b"))
        self.assertEqual(
            hypothesis.uncertainties, ("uncertainty-a", "uncertainty-b")
        )
        self.assertEqual(source_b.published_at.tzinfo, datetime.timezone.utc)
        self.assertEqual(submission.observed_at.tzinfo, datetime.timezone.utc)

    def test_records_are_frozen(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            make_submission().event_id = "other"  # type: ignore[misc]

    def test_duplicate_normalized_ids_and_text_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_fact(source_ids=("source-1", " source-1 "))
        with self.assertRaises(ValueError):
            make_hypothesis(uncertainties=("same", " same "))
        with self.assertRaises(ValueError):
            make_submission(sources=(make_source(), make_source()))
        with self.assertRaises(ValueError):
            make_submission(statements=(make_fact(), make_fact()))
        with self.assertRaises(ValueError):
            make_submission(hypotheses=(make_hypothesis(), make_hypothesis()))

    def test_empty_hypotheses_are_malformed(self) -> None:
        with self.assertRaises(ValueError):
            make_submission(hypotheses=())

    def test_dangling_references_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "dangling source"):
            make_submission(statements=(make_fact(source_ids=("missing",)),))
        with self.assertRaisesRegex(ValueError, "dangling dependencies"):
            make_submission(
                statements=(
                    make_fact(),
                    make_interpretation(dependency_statement_ids=("missing",)),
                )
            )
        with self.assertRaisesRegex(ValueError, "dangling support"):
            make_submission(
                hypotheses=(
                    make_hypothesis(supporting_statement_ids=("missing",)),
                )
            )
        with self.assertRaisesRegex(ValueError, "dangling contradiction"):
            make_submission(
                hypotheses=(
                    make_hypothesis(contradicting_statement_ids=("missing",)),
                )
            )

    def test_statement_cycles_self_dependencies_and_fact_dependencies_reject(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not depend on itself"):
            make_interpretation(
                dependency_statement_ids=("interpretation-1",)
            )
        with self.assertRaisesRegex(ValueError, "observed facts"):
            make_fact(dependency_statement_ids=("interpretation-1",))
        first = make_interpretation(
            statement_id="interpretation-1",
            dependency_statement_ids=("interpretation-2",),
        )
        second = make_interpretation(
            statement_id="interpretation-2",
            dependency_statement_ids=("interpretation-1",),
        )
        with self.assertRaisesRegex(ValueError, "cycle"):
            make_submission(statements=(make_fact(), first, second))

    def test_support_and_contradiction_overlap_rejects(self) -> None:
        with self.assertRaises(ValueError):
            make_hypothesis(
                supporting_statement_ids=("fact-1",),
                contradicting_statement_ids=("fact-1",),
            )

    def test_datetime_and_date_boundaries_reject_malformed_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            make_source(published_at=datetime.datetime(2030, 1, 5, 9, 0))
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            make_submission(observed_at=datetime.datetime(2030, 1, 5, 15, 0))
        with self.assertRaisesRegex(TypeError, "without a time component"):
            MethodologizedDateRange(
                datetime.datetime(2030, 1, 1), datetime.date(2030, 1, 2), "x"
            )
        with self.assertRaisesRegex(ValueError, "must not be after"):
            MethodologizedDateRange(
                datetime.date(2030, 1, 2), datetime.date(2030, 1, 1), "x"
            )

    def test_source_publication_after_observation_rejects(self) -> None:
        source = make_source(
            published_at=OBSERVED_AT + datetime.timedelta(seconds=1)
        )
        with self.assertRaisesRegex(ValueError, "must not be after observed_at"):
            make_submission(sources=(source,))

    def test_wrong_types_and_blank_supplied_values_reject(self) -> None:
        with self.assertRaises(TypeError):
            EventStatement("statement", "observed_fact", "text")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            make_source(locator=" ")
        with self.assertRaises(TypeError):
            make_hypothesis(underlying_key="ABC")
        with self.assertRaises(TypeError):
            assess_event_intelligence_submission(object())  # type: ignore[arg-type]

    def test_subclasses_and_constructor_bypasses_fail_with_controlled_errors(self) -> None:
        class UnderlyingSubclass(UnderlyingKey):
            pass

        subclass = UnderlyingSubclass(
            "ABC", "XNAS", UnderlyingSecurityType.EQUITY, "USD"
        )
        with self.assertRaises(TypeError):
            make_hypothesis(underlying_key=subclass)

        malformed_underlying = object.__new__(UnderlyingKey)
        with self.assertRaises(ValueError):
            make_hypothesis(underlying_key=malformed_underlying)

        malformed_source = object.__new__(EventSourceReference)
        with self.assertRaises(ValueError):
            make_submission(sources=(malformed_source,))

        malformed_range = object.__new__(MethodologizedDateRange)
        with self.assertRaises(ValueError):
            make_hypothesis(expected_window=malformed_range)

        malformed_submission = object.__new__(EventIntelligenceSubmission)
        with self.assertRaises(ValueError):
            assess_event_intelligence_submission(malformed_submission)

    def test_deep_acyclic_dependency_graph_does_not_use_recursion_limit(self) -> None:
        statements = [make_fact()]
        previous_id = "fact-1"
        for index in range(1, 1101):
            statement_id = f"interpretation-{index:04d}"
            statements.append(
                make_interpretation(
                    statement_id=statement_id,
                    dependency_statement_ids=(previous_id,),
                )
            )
            previous_id = statement_id
        hypothesis = make_hypothesis(supporting_statement_ids=(previous_id,))
        result = assess_event_intelligence_submission(
            make_submission(
                statements=tuple(reversed(statements)),
                hypotheses=(hypothesis,),
            )
        )
        self.assertIs(result.status, EventIntelligenceAcceptanceStatus.ACCEPTED)

    def test_result_invariants_and_canonical_issue_order(self) -> None:
        submission = make_submission(
            event_id=None,
            hypotheses=(make_hypothesis(hypothesis_id="hypothesis-2", impact_path=None),),
        )
        late = EventIntelligenceAcceptanceIssue(
            EventIntelligenceIssueCode.MISSING_IMPACT_PATH, "hypothesis-2"
        )
        early = EventIntelligenceAcceptanceIssue(
            EventIntelligenceIssueCode.MISSING_EVENT_ID
        )
        result = EventIntelligenceAcceptanceResult(
            submission,
            EventIntelligenceAcceptanceStatus.INCOMPLETE,
            (late, early),
        )
        self.assertEqual(result.issues, (early, late))
        with self.assertRaises(ValueError):
            EventIntelligenceAcceptanceResult(
                make_submission(),
                EventIntelligenceAcceptanceStatus.ACCEPTED,
                (late,),
            )
        with self.assertRaises(ValueError):
            EventIntelligenceAcceptanceResult(
                submission,
                EventIntelligenceAcceptanceStatus.INCOMPLETE,
                (early, early),
            )
        with self.assertRaises(ValueError):
            EventIntelligenceAcceptanceResult(
                submission,
                EventIntelligenceAcceptanceStatus.ACCEPTED,
                (),
                assessment_version="other",
            )

    def test_no_numeric_confidence_ranking_or_market_data_fields(self) -> None:
        names = {
            field.name
            for record_type in (
                EventUnderlyingHypothesis,
                EventIntelligenceSubmission,
                EventIntelligenceAcceptanceResult,
            )
            for field in fields(record_type)
        }
        self.assertTrue(
            names.isdisjoint(
                {
                    "confidence",
                    "probability",
                    "rank",
                    "score",
                    "bid",
                    "ask",
                    "implied_volatility",
                    "delta",
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
