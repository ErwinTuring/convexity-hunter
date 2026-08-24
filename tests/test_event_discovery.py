"""Tests for the provider-neutral Event Discovery and intake boundary."""

import datetime
import inspect
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError, fields
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import convexity_hunter
from convexity_hunter import event_discovery as discovery_module
from convexity_hunter.event_discovery import (
    EventCandidate,
    EventCandidateBatch,
    EventCandidateSelection,
    EventCandidateTranslation,
    select_event_candidate,
    translate_event_candidate_selection,
)
from convexity_hunter.event_intelligence import (
    EventIntelligenceAcceptanceStatus,
    EventIntelligenceSubmission,
    EventSourceReference,
    EventUnderlyingHypothesis,
    MethodologizedDateRange,
    assess_event_intelligence_submission,
)


UTC = datetime.timezone.utc
OBSERVED_AT = datetime.datetime(2030, 1, 10, 15, 0, tzinfo=UTC)


def make_source(
    source_id: str = "source-1",
    *,
    locator: object = "https://example.test/event",
    published_at: object = datetime.datetime(2030, 1, 10, 14, 0, tzinfo=UTC),
) -> EventSourceReference:
    return EventSourceReference(
        source_id,
        locator,  # type: ignore[arg-type]
        f"Source {source_id}",
        published_at,  # type: ignore[arg-type]
    )


def make_candidate(
    candidate_id: str = "candidate-1", **overrides: object
) -> EventCandidate:
    values = {
        "candidate_id": candidate_id,
        "deduplication_key": f"entity:event:{candidate_id}",
        "event_description": "A source-backed event may affect an issuer.",
        "observed_at": OBSERVED_AT,
        "event_date_range": MethodologizedDateRange(
            datetime.date(2030, 1, 15),
            datetime.date(2030, 1, 15),
            "Exact date stated by the source.",
        ),
        "expected_window": None,
        "sources": (make_source(),),
        "authoritative_source_ids": ("source-1",),
        "provisional_underlying_symbols": ("XYZ",),
        "distribution_change_rationale": (
            "The event may widen the issuer's future return distribution."
        ),
        "contradiction_review": (
            "The available sources were reviewed; no direct contradiction was found."
        ),
        "uncertainties": ("The market impact may be muted.",),
    }
    values.update(overrides)
    return EventCandidate(**values)  # type: ignore[arg-type]


def make_batch(
    candidates: object = None,
    **overrides: object,
) -> EventCandidateBatch:
    values = {
        "batch_id": "batch-1",
        "producer_id": "bounded-search-producer",
        "producer_version": "1.0",
        "observed_at": OBSERVED_AT,
        "discovery_policy": "Recent public information; at most ten; no padding.",
        "candidates": (make_candidate(),) if candidates is None else candidates,
    }
    values.update(overrides)
    return EventCandidateBatch(**values)  # type: ignore[arg-type]


def make_submission(
    sources: object,
    *,
    observed_at: object = OBSERVED_AT,
) -> EventIntelligenceSubmission:
    hypothesis = EventUnderlyingHypothesis(
        "hypothesis-1",
        None,
        None,
        None,
        None,
        None,
        (),
        (),
        None,
        (),
        (),
    )
    return EventIntelligenceSubmission(
        "submission-1",
        None,
        "translation-producer",
        "1.0",
        observed_at,  # type: ignore[arg-type]
        "Explicit but incomplete translated submission.",
        None,
        sources,  # type: ignore[arg-type]
        (),
        (hypothesis,),
    )


class PublicContractTests(unittest.TestCase):
    def test_exact_public_surface_fields_and_signatures(self) -> None:
        self.assertEqual(
            discovery_module.__all__,
            (
                "EventCandidate",
                "EventCandidateBatch",
                "EventCandidateSelection",
                "EventCandidateTranslation",
                "select_event_candidate",
                "translate_event_candidate_selection",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in fields(EventCandidate)),
            (
                "candidate_id",
                "deduplication_key",
                "event_description",
                "observed_at",
                "event_date_range",
                "expected_window",
                "sources",
                "authoritative_source_ids",
                "provisional_underlying_symbols",
                "distribution_change_rationale",
                "contradiction_review",
                "uncertainties",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in fields(EventCandidateBatch)),
            (
                "batch_id",
                "producer_id",
                "producer_version",
                "observed_at",
                "discovery_policy",
                "candidates",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in fields(EventCandidateSelection)),
            ("batch", "selected_candidate"),
        )
        self.assertEqual(
            tuple(field.name for field in fields(EventCandidateTranslation)),
            ("selection", "submission", "supplemental_sources"),
        )
        self.assertEqual(
            tuple(inspect.signature(select_event_candidate).parameters),
            ("batch", "candidate_id"),
        )
        self.assertEqual(
            tuple(
                inspect.signature(
                    translate_event_candidate_selection
                ).parameters
            ),
            ("selection", "submission", "supplemental_sources"),
        )

    def test_names_are_not_reexported_from_package_root(self) -> None:
        for name in discovery_module.__all__:
            self.assertFalse(hasattr(convexity_hunter, name))


class CandidateTests(unittest.TestCase):
    def test_candidate_retains_provisional_semantics_and_metadata(self) -> None:
        source_a = make_source("source-a")
        source_b = make_source("source-b")
        candidate = make_candidate(
            sources=(source_b, source_a),
            authoritative_source_ids=("source-b", "source-a"),
            provisional_underlying_symbols=("ZZZ", "AAA"),
            uncertainties=("Second uncertainty.", "First uncertainty."),
        )
        self.assertEqual(
            tuple(source.source_id for source in candidate.sources),
            ("source-a", "source-b"),
        )
        self.assertEqual(
            candidate.authoritative_source_ids,
            ("source-a", "source-b"),
        )
        self.assertEqual(candidate.provisional_underlying_symbols, ("AAA", "ZZZ"))
        self.assertEqual(
            candidate.uncertainties,
            ("First uncertainty.", "Second uncertainty."),
        )
        self.assertIs(candidate.sources[0], source_a)

    def test_optional_dates_underlyings_and_authority_remain_optional(self) -> None:
        candidate = make_candidate(
            event_date_range=None,
            expected_window=None,
            authoritative_source_ids=(),
            provisional_underlying_symbols=(),
        )
        self.assertIsNone(candidate.event_date_range)
        self.assertIsNone(candidate.expected_window)
        self.assertEqual(candidate.authoritative_source_ids, ())
        self.assertEqual(candidate.provisional_underlying_symbols, ())

    def test_candidate_requires_source_locator_uncertainty_and_review(self) -> None:
        with self.assertRaisesRegex(ValueError, "sources must not be empty"):
            make_candidate(sources=())
        with self.assertRaisesRegex(ValueError, "must have a locator"):
            make_candidate(sources=(make_source(locator=None),))
        with self.assertRaisesRegex(ValueError, "uncertainties must not be empty"):
            make_candidate(uncertainties=())
        with self.assertRaisesRegex(
            ValueError, "contradiction_review must not be empty"
        ):
            make_candidate(contradiction_review="  ")

    def test_candidate_rejects_unknown_authority_and_future_source(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "authoritative_source_ids must refer"
        ):
            make_candidate(authoritative_source_ids=("unknown",))
        future = make_source(
            published_at=OBSERVED_AT + datetime.timedelta(seconds=1)
        )
        with self.assertRaisesRegex(ValueError, "must not be after observed_at"):
            make_candidate(sources=(future,), authoritative_source_ids=())

    def test_candidate_is_frozen_and_rejects_subclassed_nested_records(self) -> None:
        candidate = make_candidate()
        with self.assertRaises(FrozenInstanceError):
            candidate.event_description = "changed"  # type: ignore[misc]

        class SourceSubclass(EventSourceReference):
            pass

        source = make_source()
        subclass = SourceSubclass(
            source.source_id,
            source.locator,
            source.title,
            source.published_at,
        )
        with self.assertRaises(TypeError):
            make_candidate(sources=(subclass,))

    def test_candidate_rejects_malformed_constructor_bypassed_source(self) -> None:
        forged = object.__new__(EventSourceReference)
        object.__setattr__(forged, "source_id", None)
        object.__setattr__(forged, "locator", "https://example.test/forged")
        object.__setattr__(forged, "title", None)
        object.__setattr__(forged, "published_at", None)
        with self.assertRaises(TypeError):
            make_candidate(sources=(forged,), authoritative_source_ids=())


class BatchAndSelectionTests(unittest.TestCase):
    def test_batch_allows_zero_and_ten_without_padding_or_reordering(self) -> None:
        empty = make_batch(candidates=())
        self.assertEqual(empty.candidates, ())

        candidates = tuple(make_candidate(f"candidate-{index}") for index in range(10))
        batch = make_batch(candidates=tuple(reversed(candidates)))
        self.assertEqual(batch.candidates, tuple(reversed(candidates)))
        self.assertTrue(
            all(
                actual is expected
                for actual, expected in zip(batch.candidates, reversed(candidates))
            )
        )

    def test_batch_rejects_eleven_duplicates_and_future_candidates(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most 10"):
            make_batch(
                candidates=tuple(
                    make_candidate(f"candidate-{index}") for index in range(11)
                )
            )
        first = make_candidate("candidate-a")
        duplicate_id = make_candidate(
            "candidate-a", deduplication_key="other:event:key"
        )
        with self.assertRaisesRegex(ValueError, "duplicate candidate IDs"):
            make_batch(candidates=(first, duplicate_id))
        duplicate_key = make_candidate(
            "candidate-b", deduplication_key=first.deduplication_key
        )
        with self.assertRaisesRegex(ValueError, "duplicate deduplication keys"):
            make_batch(candidates=(first, duplicate_key))
        future = make_candidate(
            observed_at=OBSERVED_AT + datetime.timedelta(seconds=1)
        )
        with self.assertRaisesRegex(ValueError, "candidate observed_at"):
            make_batch(candidates=(future,))

    def test_selection_explicitly_records_zero_or_one_by_identity(self) -> None:
        candidate = make_candidate()
        batch = make_batch(candidates=(candidate,))
        none_selected = select_event_candidate(batch, candidate_id=None)
        self.assertIs(none_selected.batch, batch)
        self.assertIsNone(none_selected.selected_candidate)

        selected = select_event_candidate(
            batch,
            candidate_id=candidate.candidate_id,
        )
        self.assertIs(selected.batch, batch)
        self.assertIs(selected.selected_candidate, candidate)
        with self.assertRaisesRegex(ValueError, "identify a candidate"):
            select_event_candidate(batch, candidate_id="unknown")

    def test_equal_candidate_copy_cannot_authorize_direct_selection(self) -> None:
        candidate = make_candidate()
        equal_copy = make_candidate()
        self.assertEqual(candidate, equal_copy)
        self.assertIsNot(candidate, equal_copy)
        batch = make_batch(candidates=(candidate,))
        with self.assertRaisesRegex(ValueError, "retained by identity"):
            EventCandidateSelection(batch, equal_copy)

    def test_batch_and_selection_reject_subclasses(self) -> None:
        candidate = make_candidate()

        class CandidateSubclass(EventCandidate):
            pass

        subclass = CandidateSubclass(
            candidate.candidate_id,
            candidate.deduplication_key,
            candidate.event_description,
            candidate.observed_at,
            candidate.event_date_range,
            candidate.expected_window,
            candidate.sources,
            candidate.authoritative_source_ids,
            candidate.provisional_underlying_symbols,
            candidate.distribution_change_rationale,
            candidate.contradiction_review,
            candidate.uncertainties,
        )
        with self.assertRaises(TypeError):
            make_batch(candidates=(subclass,))

        batch = make_batch(candidates=(candidate,))

        class BatchSubclass(EventCandidateBatch):
            pass

        batch_subclass = BatchSubclass(
            batch.batch_id,
            batch.producer_id,
            batch.producer_version,
            batch.observed_at,
            batch.discovery_policy,
            batch.candidates,
        )
        with self.assertRaises(TypeError):
            select_event_candidate(batch_subclass, candidate_id=None)


class TranslationTests(unittest.TestCase):
    def test_translation_retains_exact_inputs_and_source_union(self) -> None:
        candidate_source = make_source("candidate-source")
        supplemental = make_source("supplemental-source")
        candidate = make_candidate(
            sources=(candidate_source,),
            authoritative_source_ids=(candidate_source.source_id,),
        )
        selection = select_event_candidate(
            make_batch(candidates=(candidate,)),
            candidate_id=candidate.candidate_id,
        )
        submission = make_submission((supplemental, candidate_source))
        translation = translate_event_candidate_selection(
            selection,
            submission=submission,
            supplemental_sources=(supplemental,),
        )
        self.assertIs(translation.selection, selection)
        self.assertIs(translation.submission, submission)
        self.assertIs(translation.supplemental_sources[0], supplemental)
        self.assertIs(
            next(
                source
                for source in submission.sources
                if source.source_id == candidate_source.source_id
            ),
            candidate_source,
        )

    def test_translation_does_not_assess_or_fill_incomplete_submission(self) -> None:
        candidate = make_candidate(event_date_range=None, expected_window=None)
        selection = select_event_candidate(
            make_batch(candidates=(candidate,)),
            candidate_id=candidate.candidate_id,
        )
        submission = make_submission(candidate.sources)
        with mock.patch(
            "convexity_hunter.event_intelligence.assess_event_intelligence_submission"
        ) as assessor:
            translation = translate_event_candidate_selection(
                selection,
                submission=submission,
            )
        assessor.assert_not_called()
        self.assertIsNone(candidate.event_date_range)
        self.assertIsNone(candidate.expected_window)
        self.assertIsNone(translation.submission.event_date_range)
        result = assess_event_intelligence_submission(translation.submission)
        self.assertIs(result.status, EventIntelligenceAcceptanceStatus.INCOMPLETE)

    def test_translation_rejects_no_selection_and_source_id_overlap(self) -> None:
        candidate = make_candidate()
        no_selection = select_event_candidate(
            make_batch(candidates=(candidate,)),
            candidate_id=None,
        )
        with self.assertRaisesRegex(ValueError, "requires one selected candidate"):
            translate_event_candidate_selection(
                no_selection,
                submission=make_submission(candidate.sources),
            )

        selected = select_event_candidate(
            no_selection.batch,
            candidate_id=candidate.candidate_id,
        )
        overlapping = make_source(candidate.sources[0].source_id)
        with self.assertRaisesRegex(ValueError, "must be disjoint"):
            translate_event_candidate_selection(
                selected,
                submission=make_submission(candidate.sources),
                supplemental_sources=(overlapping,),
            )

    def test_translation_rejects_missing_extra_and_equal_copy_sources(self) -> None:
        source = make_source("candidate-source")
        candidate = make_candidate(
            sources=(source,), authoritative_source_ids=(source.source_id,)
        )
        selection = select_event_candidate(
            make_batch(candidates=(candidate,)),
            candidate_id=candidate.candidate_id,
        )
        with self.assertRaisesRegex(ValueError, "must exactly equal"):
            translate_event_candidate_selection(
                selection,
                submission=make_submission(()),
            )
        extra = make_source("extra-source")
        with self.assertRaisesRegex(ValueError, "must exactly equal"):
            translate_event_candidate_selection(
                selection,
                submission=make_submission((source, extra)),
            )
        equal_copy = make_source("candidate-source")
        self.assertEqual(source, equal_copy)
        self.assertIsNot(source, equal_copy)
        with self.assertRaisesRegex(ValueError, "by identity"):
            translate_event_candidate_selection(
                selection,
                submission=make_submission((equal_copy,)),
            )

    def test_translation_rejects_submission_chronology_before_candidate(self) -> None:
        candidate = make_candidate()
        selection = select_event_candidate(
            make_batch(candidates=(candidate,)),
            candidate_id=candidate.candidate_id,
        )
        earlier = OBSERVED_AT - datetime.timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError, "must not precede"):
            translate_event_candidate_selection(
                selection,
                submission=make_submission(candidate.sources, observed_at=earlier),
            )

    def test_translation_rejects_unlocated_and_subclassed_inputs(self) -> None:
        candidate = make_candidate()
        selection = select_event_candidate(
            make_batch(candidates=(candidate,)),
            candidate_id=candidate.candidate_id,
        )
        unlocated = make_source("supplemental", locator=None)
        with self.assertRaisesRegex(ValueError, "must have a locator"):
            translate_event_candidate_selection(
                selection,
                submission=make_submission(candidate.sources),
                supplemental_sources=(unlocated,),
            )

        class SelectionSubclass(EventCandidateSelection):
            pass

        subclass = SelectionSubclass(selection.batch, selection.selected_candidate)
        with self.assertRaises(TypeError):
            translate_event_candidate_selection(
                subclass,
                submission=make_submission(candidate.sources),
            )

    def test_translation_is_frozen(self) -> None:
        candidate = make_candidate()
        selection = select_event_candidate(
            make_batch(candidates=(candidate,)),
            candidate_id=candidate.candidate_id,
        )
        translation = translate_event_candidate_selection(
            selection,
            submission=make_submission(candidate.sources),
        )
        with self.assertRaises(FrozenInstanceError):
            translation.submission = make_submission(  # type: ignore[misc]
                candidate.sources
            )


if __name__ == "__main__":
    unittest.main()
