"""Tests for provider-neutral option-chain discovery requests."""

import datetime
import inspect
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError, fields
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import convexity_hunter
from convexity_hunter import event_intelligence
from convexity_hunter import option_chain_discovery
from convexity_hunter.discovery_entry import (
    DiscoveryEntryHandoff,
    create_discovery_entry_handoff,
)
from convexity_hunter.event_intelligence import (
    DistributionChangeMode,
    EventIntelligenceSubmission,
    EventSourceReference,
    EventStatement,
    EventStatementKind,
    EventUnderlyingHypothesis,
    MethodologizedDateRange,
    assess_event_intelligence_submission,
)
from convexity_hunter.market_data import UnderlyingKey, UnderlyingSecurityType
from convexity_hunter.option_chain_discovery import (
    OptionChainDiscoveryRequest,
    create_option_chain_discovery_request,
)


EVALUATION_DATE = datetime.date(2030, 1, 1)


def make_handoff(
    mode: DistributionChangeMode = DistributionChangeMode.BIDIRECTIONAL_EXPANSION,
    event_window_end: datetime.date = datetime.date(2030, 1, 10),
) -> DiscoveryEntryHandoff:
    source = EventSourceReference(
        "source-1",
        "https://www.sec.gov/example",
        "Issuer filing",
        datetime.datetime(2029, 12, 31, tzinfo=datetime.timezone.utc),
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
        "The event may change the return distribution.",
        (),
        (fact.statement_id,),
    )
    event_range = MethodologizedDateRange(
        event_window_end,
        event_window_end,
        "Exact event date.",
    )
    hypothesis = EventUnderlyingHypothesis(
        "hypothesis-1",
        UnderlyingKey("ABC", "XNAS", UnderlyingSecurityType.EQUITY, "USD"),
        "The event changes possible commercial outcomes.",
        mode,
        "The event may change the future return distribution.",
        event_range,
        (interpretation.statement_id,),
        (),
        "Contradictory evidence was reviewed; none was identified.",
        ("The event timing may change.",),
        ("The event is cancelled.",),
    )
    submission = EventIntelligenceSubmission(
        "submission-1",
        "event-1",
        "test-producer",
        "1.0",
        datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc),
        "A dated issuer event is expected.",
        event_range,
        (source,),
        (fact, interpretation),
        (hypothesis,),
    )
    result = assess_event_intelligence_submission(submission)
    return create_discovery_entry_handoff(result, hypothesis)


class PublicContractTests(unittest.TestCase):
    def test_exact_api_fields_signature_and_root_boundary(self) -> None:
        self.assertEqual(
            option_chain_discovery.__all__,
            (
                "OptionChainDiscoveryRequest",
                "create_option_chain_discovery_request",
            ),
        )
        for name in option_chain_discovery.__all__:
            self.assertFalse(hasattr(convexity_hunter, name))
        self.assertEqual(
            tuple(field.name for field in fields(OptionChainDiscoveryRequest)),
            ("discovery_entry_handoff", "evaluation_date"),
        )
        self.assertEqual(
            OptionChainDiscoveryRequest.__annotations__,
            {
                "discovery_entry_handoff": DiscoveryEntryHandoff,
                "evaluation_date": datetime.date,
            },
        )
        signature = inspect.signature(create_option_chain_discovery_request)
        self.assertEqual(
            tuple(signature.parameters),
            ("discovery_entry_handoff", "evaluation_date"),
        )
        self.assertEqual(
            signature.parameters["evaluation_date"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )
        self.assertIs(signature.return_annotation, OptionChainDiscoveryRequest)


class SuccessfulRequestTests(unittest.TestCase):
    def test_active_hypothesis_retains_handoff_and_exact_boundaries(self) -> None:
        handoff = make_handoff(event_window_end=datetime.date(2030, 1, 10))
        request = create_option_chain_discovery_request(
            handoff,
            evaluation_date=EVALUATION_DATE,
        )
        self.assertIs(request.discovery_entry_handoff, handoff)
        self.assertIs(
            request.underlying_key,
            handoff.selected_hypothesis.underlying_key,
        )
        self.assertIs(
            request.distribution_mode,
            handoff.selected_hypothesis.distribution_mode,
        )
        self.assertEqual(request.event_window_end_date, datetime.date(2030, 1, 10))
        self.assertEqual(request.minimum_expiration_date, datetime.date(2030, 2, 9))
        self.assertEqual(request.maximum_expiration_date, datetime.date(2030, 5, 31))

    def test_boundary_day_is_active_and_controls_dte_boundaries(self) -> None:
        handoff = make_handoff(event_window_end=EVALUATION_DATE)
        request = create_option_chain_discovery_request(
            handoff,
            evaluation_date=EVALUATION_DATE,
        )
        self.assertEqual(request.minimum_expiration_date, datetime.date(2030, 1, 31))
        self.assertEqual(request.maximum_expiration_date, datetime.date(2030, 5, 31))
        self.assertEqual((request.minimum_expiration_date - EVALUATION_DATE).days, 30)
        self.assertEqual((request.maximum_expiration_date - EVALUATION_DATE).days, 150)

    def test_all_distribution_modes_are_retained_without_selection(self) -> None:
        for mode in DistributionChangeMode:
            with self.subTest(mode=mode):
                handoff = make_handoff(mode=mode)
                request = create_option_chain_discovery_request(
                    handoff,
                    evaluation_date=EVALUATION_DATE,
                )
                self.assertIs(request.distribution_mode, mode)

    def test_direct_constructor_matches_public_function(self) -> None:
        handoff = make_handoff()
        direct = OptionChainDiscoveryRequest(handoff, EVALUATION_DATE)
        produced = create_option_chain_discovery_request(
            handoff,
            evaluation_date=EVALUATION_DATE,
        )
        self.assertEqual(direct, produced)
        self.assertIs(direct.discovery_entry_handoff, handoff)

    def test_repeated_calls_are_deterministic_pure_and_frozen(self) -> None:
        handoff = make_handoff()
        before = repr(handoff)
        first = create_option_chain_discovery_request(
            handoff,
            evaluation_date=EVALUATION_DATE,
        )
        second = create_option_chain_discovery_request(
            handoff,
            evaluation_date=EVALUATION_DATE,
        )
        self.assertEqual(first, second)
        self.assertEqual(repr(handoff), before)
        with self.assertRaises(FrozenInstanceError):
            first.evaluation_date = datetime.date(2030, 1, 2)  # type: ignore[misc]

    def test_no_acceptance_replay_or_clock_read(self) -> None:
        handoff = make_handoff()

        class DateTimeWithoutClock:
            date = datetime.date
            timedelta = datetime.timedelta

            class datetime:
                @classmethod
                def now(cls, *args: object, **kwargs: object) -> object:
                    raise AssertionError("clock read")

        with mock.patch.object(
            event_intelligence,
            "assess_event_intelligence_submission",
            side_effect=AssertionError("acceptance replayed"),
        ), mock.patch.object(
            event_intelligence,
            "_derive_event_intelligence_issues",
            side_effect=AssertionError("issues replayed"),
        ), mock.patch.object(
            option_chain_discovery,
            "datetime",
            DateTimeWithoutClock,
        ):
            request = create_option_chain_discovery_request(
                handoff,
                evaluation_date=EVALUATION_DATE,
            )
        self.assertEqual(request.evaluation_date, EVALUATION_DATE)


class FailureBoundaryTests(unittest.TestCase):
    def test_expired_hypothesis_fails_closed_without_extending_window(self) -> None:
        handoff = make_handoff(
            event_window_end=EVALUATION_DATE - datetime.timedelta(days=1)
        )
        with self.assertRaisesRegex(
            ValueError,
            "selected hypothesis is expired for evaluation_date",
        ):
            create_option_chain_discovery_request(
                handoff,
                evaluation_date=EVALUATION_DATE,
            )
        with self.assertRaisesRegex(
            ValueError,
            "selected hypothesis is expired for evaluation_date",
        ):
            OptionChainDiscoveryRequest(handoff, EVALUATION_DATE)
        self.assertEqual(
            handoff.selected_hypothesis.expected_window.end_date,
            EVALUATION_DATE - datetime.timedelta(days=1),
        )

    def test_expired_hypothesis_precedes_date_arithmetic_overflow(self) -> None:
        handoff = make_handoff(
            event_window_end=datetime.date.max - datetime.timedelta(days=1)
        )
        with self.assertRaisesRegex(
            ValueError,
            "selected hypothesis is expired for evaluation_date",
        ):
            create_option_chain_discovery_request(
                handoff,
                evaluation_date=datetime.date.max,
            )

    def test_wrong_top_level_types_and_subclasses_fail(self) -> None:
        handoff = make_handoff()

        class HandoffSubclass(DiscoveryEntryHandoff):
            pass

        subclass = HandoffSubclass(
            handoff.acceptance_result,
            handoff.selected_hypothesis,
        )
        for invalid in (None, object(), [], subclass):
            with self.assertRaises(TypeError):
                create_option_chain_discovery_request(  # type: ignore[arg-type]
                    invalid,
                    evaluation_date=EVALUATION_DATE,
                )
        for invalid_date in (
            None,
            "2030-01-01",
            datetime.datetime(2030, 1, 1),
        ):
            with self.assertRaises(TypeError):
                create_option_chain_discovery_request(
                    handoff,
                    evaluation_date=invalid_date,  # type: ignore[arg-type]
                )

    def test_malformed_handoff_fails_controlled(self) -> None:
        malformed = object.__new__(DiscoveryEntryHandoff)
        with self.assertRaises(ValueError):
            create_option_chain_discovery_request(
                malformed,
                evaluation_date=EVALUATION_DATE,
            )

    def test_missing_selected_semantics_fail_closed(self) -> None:
        for field_name in (
            "underlying_key",
            "distribution_mode",
            "expected_window",
        ):
            with self.subTest(field=field_name):
                handoff = make_handoff()
                hypothesis = handoff.selected_hypothesis
                object.__setattr__(hypothesis, field_name, None)
                with self.assertRaises((TypeError, ValueError)):
                    create_option_chain_discovery_request(
                        handoff,
                        evaluation_date=EVALUATION_DATE,
                    )

    def test_event_window_end_is_required(self) -> None:
        handoff = make_handoff()
        window = handoff.selected_hypothesis.expected_window
        object.__setattr__(window, "end_date", None)
        with self.assertRaises((TypeError, ValueError)):
            create_option_chain_discovery_request(
                handoff,
                evaluation_date=EVALUATION_DATE,
            )

    def test_empty_interval_and_date_overflow_fail(self) -> None:
        empty = make_handoff(event_window_end=datetime.date(2030, 5, 2))
        with self.assertRaisesRegex(ValueError, "interval is empty"):
            create_option_chain_discovery_request(
                empty,
                evaluation_date=EVALUATION_DATE,
            )
        overflow = make_handoff(event_window_end=datetime.date.max)
        with self.assertRaisesRegex(ValueError, "date arithmetic failed"):
            create_option_chain_discovery_request(
                overflow,
                evaluation_date=datetime.date.max,
            )


if __name__ == "__main__":
    unittest.main()
