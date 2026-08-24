"""Provider-neutral Event Discovery and explicit intake boundary."""

import datetime
from dataclasses import dataclass
from typing import Optional, Tuple

from .event_intelligence import (
    EventIntelligenceSubmission,
    EventSourceReference,
    MethodologizedDateRange,
)


__all__ = (
    "EventCandidate",
    "EventCandidateBatch",
    "EventCandidateSelection",
    "EventCandidateTranslation",
    "select_event_candidate",
    "translate_event_candidate_selection",
)


_MAX_BATCH_SIZE = 10


def _required_string(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must have exact type str")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _optional_string(name: str, value: object) -> Optional[str]:
    if value is None:
        return None
    return _required_string(name, value)


def _aware_utc_datetime(name: str, value: object) -> datetime.datetime:
    if type(value) is not datetime.datetime:
        raise TypeError(f"{name} must have exact type datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(datetime.timezone.utc)


def _string_tuple(
    name: str,
    values: object,
    *,
    require_nonempty: bool = False,
) -> Tuple[str, ...]:
    if type(values) not in {tuple, list}:
        raise TypeError(f"{name} must have exact type tuple or list")
    normalized = tuple(_required_string(f"{name} item", item) for item in values)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must not contain duplicates")
    if require_nonempty and not normalized:
        raise ValueError(f"{name} must not be empty")
    return tuple(sorted(normalized))


def _require_date_range(name: str, value: object) -> None:
    if type(value) is not MethodologizedDateRange:
        raise TypeError(f"{name} must have exact type MethodologizedDateRange")
    try:
        rebuilt = MethodologizedDateRange(
            value.start_date,
            value.end_date,
            value.methodology,
        )
    except AttributeError as error:
        raise ValueError(f"{name} is malformed") from error
    if rebuilt != value:
        raise ValueError(f"{name} is not intrinsically valid")


def _require_source(name: str, value: object) -> None:
    if type(value) is not EventSourceReference:
        raise TypeError(f"{name} must have exact type EventSourceReference")
    try:
        rebuilt = EventSourceReference(
            value.source_id,
            value.locator,
            value.title,
            value.published_at,
        )
    except AttributeError as error:
        raise ValueError(f"{name} is malformed") from error
    if rebuilt != value:
        raise ValueError(f"{name} is not intrinsically valid")


def _source_tuple(
    name: str,
    values: object,
    *,
    require_nonempty: bool,
) -> Tuple[EventSourceReference, ...]:
    if type(values) not in {tuple, list}:
        raise TypeError(f"{name} must have exact type tuple or list")
    normalized = tuple(values)
    if not all(type(item) is EventSourceReference for item in normalized):
        raise TypeError(
            f"every {name} item must have exact type EventSourceReference"
        )
    if require_nonempty and not normalized:
        raise ValueError(f"{name} must not be empty")
    for source in normalized:
        _require_source(f"{name} item", source)
        if source.locator is None:
            raise ValueError(f"every {name} item must have a locator")
    identifiers = tuple(source.source_id for source in normalized)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{name} must not contain duplicate source IDs")
    return tuple(sorted(normalized, key=lambda item: item.source_id))


def _require_submission(value: object) -> None:
    if type(value) is not EventIntelligenceSubmission:
        raise TypeError(
            "submission must have exact type EventIntelligenceSubmission"
        )
    try:
        rebuilt = EventIntelligenceSubmission(
            value.submission_id,
            value.event_id,
            value.producer_id,
            value.producer_version,
            value.observed_at,
            value.event_description,
            value.event_date_range,
            value.sources,
            value.statements,
            value.hypotheses,
        )
    except AttributeError as error:
        raise ValueError("submission is malformed") from error
    if rebuilt != value:
        raise ValueError("submission is not intrinsically valid")


@dataclass(frozen=True)
class EventCandidate:
    """One provisional source-backed event surfaced for human navigation."""

    candidate_id: str
    deduplication_key: str
    event_description: str
    observed_at: datetime.datetime
    event_date_range: Optional[MethodologizedDateRange]
    expected_window: Optional[MethodologizedDateRange]
    sources: Tuple[EventSourceReference, ...]
    authoritative_source_ids: Tuple[str, ...]
    provisional_underlying_symbols: Tuple[str, ...]
    distribution_change_rationale: str
    contradiction_review: str
    uncertainties: Tuple[str, ...]

    def __post_init__(self) -> None:
        candidate_id = _required_string("candidate_id", self.candidate_id)
        deduplication_key = _required_string(
            "deduplication_key", self.deduplication_key
        )
        event_description = _required_string(
            "event_description", self.event_description
        )
        observed_at = _aware_utc_datetime("observed_at", self.observed_at)
        if self.event_date_range is not None:
            _require_date_range("event_date_range", self.event_date_range)
        if self.expected_window is not None:
            _require_date_range("expected_window", self.expected_window)
        sources = _source_tuple("sources", self.sources, require_nonempty=True)
        if any(
            source.published_at is not None
            and source.published_at > observed_at
            for source in sources
        ):
            raise ValueError("source published_at must not be after observed_at")
        authoritative_source_ids = _string_tuple(
            "authoritative_source_ids", self.authoritative_source_ids
        )
        source_ids = {source.source_id for source in sources}
        if set(authoritative_source_ids) - source_ids:
            raise ValueError(
                "authoritative_source_ids must refer to candidate sources"
            )
        provisional_symbols = _string_tuple(
            "provisional_underlying_symbols",
            self.provisional_underlying_symbols,
        )
        rationale = _required_string(
            "distribution_change_rationale",
            self.distribution_change_rationale,
        )
        contradiction_review = _required_string(
            "contradiction_review", self.contradiction_review
        )
        uncertainties = _string_tuple(
            "uncertainties", self.uncertainties, require_nonempty=True
        )

        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "deduplication_key", deduplication_key)
        object.__setattr__(self, "event_description", event_description)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "sources", sources)
        object.__setattr__(
            self, "authoritative_source_ids", authoritative_source_ids
        )
        object.__setattr__(
            self, "provisional_underlying_symbols", provisional_symbols
        )
        object.__setattr__(self, "distribution_change_rationale", rationale)
        object.__setattr__(self, "contradiction_review", contradiction_review)
        object.__setattr__(self, "uncertainties", uncertainties)


def _require_candidate(value: object) -> None:
    if type(value) is not EventCandidate:
        raise TypeError("candidate must have exact type EventCandidate")
    try:
        rebuilt = EventCandidate(
            value.candidate_id,
            value.deduplication_key,
            value.event_description,
            value.observed_at,
            value.event_date_range,
            value.expected_window,
            value.sources,
            value.authoritative_source_ids,
            value.provisional_underlying_symbols,
            value.distribution_change_rationale,
            value.contradiction_review,
            value.uncertainties,
        )
    except AttributeError as error:
        raise ValueError("candidate is malformed") from error
    if rebuilt != value:
        raise ValueError("candidate is not intrinsically valid")


@dataclass(frozen=True)
class EventCandidateBatch:
    """One bounded producer-ordered candidate batch for human navigation."""

    batch_id: str
    producer_id: str
    producer_version: str
    observed_at: datetime.datetime
    discovery_policy: str
    candidates: Tuple[EventCandidate, ...]

    def __post_init__(self) -> None:
        batch_id = _required_string("batch_id", self.batch_id)
        producer_id = _required_string("producer_id", self.producer_id)
        producer_version = _required_string(
            "producer_version", self.producer_version
        )
        observed_at = _aware_utc_datetime("observed_at", self.observed_at)
        discovery_policy = _required_string(
            "discovery_policy", self.discovery_policy
        )
        if type(self.candidates) not in {tuple, list}:
            raise TypeError("candidates must have exact type tuple or list")
        candidates = tuple(self.candidates)
        if not all(type(item) is EventCandidate for item in candidates):
            raise TypeError(
                "every candidates item must have exact type EventCandidate"
            )
        if len(candidates) > _MAX_BATCH_SIZE:
            raise ValueError("candidates must contain at most 10 items")
        for candidate in candidates:
            _require_candidate(candidate)
            if candidate.observed_at > observed_at:
                raise ValueError(
                    "candidate observed_at must not be after batch observed_at"
                )
        identifiers = tuple(item.candidate_id for item in candidates)
        deduplication_keys = tuple(item.deduplication_key for item in candidates)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("candidates must not contain duplicate candidate IDs")
        if len(set(deduplication_keys)) != len(deduplication_keys):
            raise ValueError(
                "candidates must not contain duplicate deduplication keys"
            )

        object.__setattr__(self, "batch_id", batch_id)
        object.__setattr__(self, "producer_id", producer_id)
        object.__setattr__(self, "producer_version", producer_version)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "discovery_policy", discovery_policy)
        object.__setattr__(self, "candidates", candidates)


def _require_batch(value: object) -> None:
    if type(value) is not EventCandidateBatch:
        raise TypeError("batch must have exact type EventCandidateBatch")
    try:
        rebuilt = EventCandidateBatch(
            value.batch_id,
            value.producer_id,
            value.producer_version,
            value.observed_at,
            value.discovery_policy,
            value.candidates,
        )
    except AttributeError as error:
        raise ValueError("batch is malformed") from error
    if rebuilt != value:
        raise ValueError("batch is not intrinsically valid")


@dataclass(frozen=True)
class EventCandidateSelection:
    """An explicit human choice of zero or one candidate from one batch."""

    batch: EventCandidateBatch
    selected_candidate: Optional[EventCandidate]

    def __post_init__(self) -> None:
        _require_batch(self.batch)
        if self.selected_candidate is None:
            return
        _require_candidate(self.selected_candidate)
        if not any(
            self.selected_candidate is candidate
            for candidate in self.batch.candidates
        ):
            raise ValueError(
                "selected_candidate must be retained by identity in the batch"
            )


def _require_selection(value: object) -> None:
    if type(value) is not EventCandidateSelection:
        raise TypeError("selection must have exact type EventCandidateSelection")
    try:
        rebuilt = EventCandidateSelection(value.batch, value.selected_candidate)
    except AttributeError as error:
        raise ValueError("selection is malformed") from error
    if rebuilt != value:
        raise ValueError("selection is not intrinsically valid")


@dataclass(frozen=True)
class EventCandidateTranslation:
    """Explicit provenance binding from one human selection to one submission."""

    selection: EventCandidateSelection
    submission: EventIntelligenceSubmission
    supplemental_sources: Tuple[EventSourceReference, ...]

    def __post_init__(self) -> None:
        _require_selection(self.selection)
        selected_candidate = self.selection.selected_candidate
        if selected_candidate is None:
            raise ValueError("translation requires one selected candidate")
        _require_submission(self.submission)
        supplemental_sources = _source_tuple(
            "supplemental_sources",
            self.supplemental_sources,
            require_nonempty=False,
        )
        candidate_sources = selected_candidate.sources
        candidate_ids = {source.source_id for source in candidate_sources}
        supplemental_ids = {
            source.source_id for source in supplemental_sources
        }
        if candidate_ids & supplemental_ids:
            raise ValueError(
                "candidate and supplemental source IDs must be disjoint"
            )
        expected_sources = {
            source.source_id: source
            for source in candidate_sources + supplemental_sources
        }
        submission_sources = {
            source.source_id: source for source in self.submission.sources
        }
        if set(submission_sources) != set(expected_sources):
            raise ValueError(
                "submission sources must exactly equal candidate and "
                "supplemental sources"
            )
        if any(
            submission_sources[source_id] is not source
            for source_id, source in expected_sources.items()
        ):
            raise ValueError(
                "submission must retain every candidate and supplemental "
                "source by identity"
            )
        if (
            self.submission.observed_at is not None
            and self.submission.observed_at < selected_candidate.observed_at
        ):
            raise ValueError(
                "submission observed_at must not precede candidate observed_at"
            )
        object.__setattr__(self, "supplemental_sources", supplemental_sources)


def select_event_candidate(
    batch: EventCandidateBatch,
    *,
    candidate_id: Optional[str],
) -> EventCandidateSelection:
    """Record an explicit human choice without ranking or default selection."""

    _require_batch(batch)
    normalized_id = _optional_string("candidate_id", candidate_id)
    if normalized_id is None:
        return EventCandidateSelection(batch, None)
    for candidate in batch.candidates:
        if candidate.candidate_id == normalized_id:
            return EventCandidateSelection(batch, candidate)
    raise ValueError("candidate_id must identify a candidate in the batch")


def translate_event_candidate_selection(
    selection: EventCandidateSelection,
    *,
    submission: EventIntelligenceSubmission,
    supplemental_sources: Tuple[EventSourceReference, ...] = (),
) -> EventCandidateTranslation:
    """Bind explicit inputs without completing or assessing Event Intelligence."""

    _require_selection(selection)
    _require_submission(submission)
    return EventCandidateTranslation(
        selection,
        submission,
        supplemental_sources,
    )
