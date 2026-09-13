"""Deterministic retained-research boundary; not search or causal inference."""

import datetime
from dataclasses import dataclass
from typing import Optional, Tuple

from .event_entry import UserEventInput, prepare_event_entry_research
from .event_intelligence import (
    EventSourceReference, EventStatement, EventStatementKind,
    EventUnderlyingHypothesis, EventIntelligenceSubmission,
    MethodologizedDateRange,
)

__all__ = (
    "PreparedEventStatement", "EventCausalLink", "EventEntryPreparation",
    "EventEntryHypothesisSelection", "EventEntryTranslation",
    "prepare_event_entry_hypotheses", "select_event_entry_hypothesis",
    "translate_event_entry_selection",
)


def _text(value):
    if type(value) is not str or not value.strip():
        raise ValueError("explicit nonblank text required")


def _record(value, kind):
    if type(value) is not kind:
        raise TypeError("unexpected record type")
    # Reject constructor-bypassed malformed records without replacing identity.
    if kind(**{name: getattr(value, name) for name in kind.__dataclass_fields__}) != value:
        raise ValueError("record is not intrinsically valid")


def _records(values, kind, key):
    if type(values) is not tuple:
        raise TypeError("records must be an immutable tuple")
    for value in values:
        _record(value, kind)
    if len({key(value) for value in values}) != len(values):
        raise ValueError("duplicate record identity")


@dataclass(frozen=True)
class PreparedEventStatement:
    """Existing statement plus optional attribution and sourced occurrence date.

For claims, text must report the attribution verbatim, never assert its truth.
Dates are occurrence dates, not publication dates; no date is inferred.
Caller research remains responsible for source fidelity and complete labeling.
"""

    statement: EventStatement
    claimant: Optional[str] = None
    claim: Optional[str] = None
    occurrence_date: Optional[datetime.date] = None
    date_methodology: Optional[str] = None

    def __post_init__(self):
        _record(self.statement, EventStatement)
        _text(self.statement.text)
        fact = self.statement.kind is EventStatementKind.OBSERVED_FACT
        if fact and not self.statement.source_ids:
            raise ValueError("source fact requires retained sources")
        if self.claimant is not None or self.claim is not None:
            _text(self.claimant)
            _text(self.claim)
            if not fact or self.statement.text != f"{self.claimant} alleged: {self.claim}":
                raise ValueError("claim must remain an attributed allegation")
        if self.occurrence_date is not None:
            if type(self.occurrence_date) is not datetime.date or not fact:
                raise ValueError("occurrence date requires a source fact and exact date")
            _text(self.date_methodology)
        elif self.date_methodology is not None:
            raise ValueError("date methodology requires an occurrence date")


@dataclass(frozen=True)
class EventCausalLink:
    """Caller-declared realized cause/effect assertion, not a causal proof.

Future conditional transmission need not declare a realized effect or date.
"""

    interpretation_id: str
    cause_statement_id: str
    effect_statement_id: str

    def __post_init__(self):
        for value in (self.interpretation_id, self.cause_statement_id, self.effect_statement_id):
            _text(value)
        if self.cause_statement_id == self.effect_statement_id:
            raise ValueError("cause and effect must differ")


@dataclass(frozen=True)
class EventEntryPreparation:
    user_input: UserEventInput
    sources: Tuple[EventSourceReference, ...]
    statements: Tuple[PreparedEventStatement, ...]
    hypotheses: Tuple[EventUnderlyingHypothesis, ...]
    grounding_methodology: str
    chronology_review: str
    causal_links: Tuple[EventCausalLink, ...] = ()

    @property
    def entry_origin(self):
        return "EVENT_ENTRY"

    def __post_init__(self):
        _record(self.user_input, UserEventInput)
        _text(self.grounding_methodology)
        _text(self.chronology_review)
        _records(self.sources, EventSourceReference, lambda x: x.source_id)
        _records(self.statements, PreparedEventStatement, lambda x: x.statement.statement_id)
        _records(self.hypotheses, EventUnderlyingHypothesis, lambda x: x.hypothesis_id)
        _records(self.causal_links, EventCausalLink, lambda x: x)
        source_ids = {s.source_id for s in self.sources}
        if any(not s.locator for s in self.sources):
            raise ValueError("retained source requires locator")
        by_id = {s.statement.statement_id: s for s in self.statements}
        for wrapped in self.statements:
            s = wrapped.statement
            if not set(s.source_ids) <= source_ids or not set(s.dependency_statement_ids) <= by_id.keys():
                raise ValueError("dangling statement evidence")

        def ancestors(key, visiting=()):
            if key in visiting:
                raise ValueError("cyclic statement dependencies")
            result = {key}
            for dependency in by_id[key].statement.dependency_statement_ids:
                result |= ancestors(dependency, visiting + (key,))
            return result

        closures = {key: ancestors(key) for key in by_id}
        for link in self.causal_links:
            if any(key not in by_id for key in
                   (link.interpretation_id, link.cause_statement_id, link.effect_statement_id)):
                raise ValueError("dangling causal link")
            interpretation = by_id[link.interpretation_id].statement
            cause, effect = by_id[link.cause_statement_id], by_id[link.effect_statement_id]
            if interpretation.kind is not EventStatementKind.INTERPRETATION:
                raise ValueError("causal assertion must be interpretation")
            if not {link.cause_statement_id, link.effect_statement_id} <= closures[link.interpretation_id]:
                raise ValueError("causal evidence must be interpretation dependencies")
            if cause.occurrence_date is None or effect.occurrence_date is None:
                raise ValueError("realized causal link requires sourced occurrence dates")
            if effect.occurrence_date < cause.occurrence_date:
                raise ValueError("effect predates cause")

        for h in self.hypotheses:
            if h.underlying_key is None or h.distribution_mode is None:
                raise ValueError("draft requires provisional underlying and distribution interpretation")
            for value in (h.impact_path, h.distribution_hypothesis, h.contradiction_review):
                _text(value)
            if not h.uncertainties or not h.falsification_conditions:
                raise ValueError("draft requires uncertainty and observable falsification")
            if not set(h.supporting_statement_ids + h.contradicting_statement_ids) <= by_id.keys():
                raise ValueError("dangling hypothesis evidence")
            supported = [key for key in h.supporting_statement_ids
                         if by_id[key].statement.kind is EventStatementKind.INTERPRETATION]
            if not supported or not any(
                by_id[key].statement.kind is EventStatementKind.OBSERVED_FACT
                for support in supported for key in closures[support]
            ):
                raise ValueError("association alone is insufficient: sourced transmission interpretation required")


def prepare_event_entry_hypotheses(user_input, *, sources, statements, hypotheses,
                                   grounding_methodology, chronology_review, causal_links=()):
    """Validate caller-prepared drafts in retained navigation order; never generate."""
    return EventEntryPreparation(user_input, sources, statements, hypotheses,
                                 grounding_methodology, chronology_review, causal_links)


@dataclass(frozen=True)
class EventEntryHypothesisSelection:
    preparation: EventEntryPreparation
    hypothesis: Optional[EventUnderlyingHypothesis]

    def __post_init__(self):
        _record(self.preparation, EventEntryPreparation)
        if self.hypothesis is not None and not any(
            self.hypothesis is h for h in self.preparation.hypotheses
        ):
            raise ValueError("selected hypothesis must retain identity")


def select_event_entry_hypothesis(preparation, *, hypothesis_id):
    """Required explicit argument: one retained ID or None. No default."""
    _record(preparation, EventEntryPreparation)
    if hypothesis_id is None:
        return EventEntryHypothesisSelection(preparation, None)
    _text(hypothesis_id)
    for h in preparation.hypotheses:
        if h.hypothesis_id == hypothesis_id:
            return EventEntryHypothesisSelection(preparation, h)
    raise ValueError("unknown hypothesis ID")


@dataclass(frozen=True)
class EventEntryTranslation:
    """Sidecar retains preparation/selection; submission is unchanged EI type."""

    selection: EventEntryHypothesisSelection
    submission: EventIntelligenceSubmission

    def __post_init__(self):
        _record(self.selection, EventEntryHypothesisSelection)
        _record(self.submission, EventIntelligenceSubmission)
        p = self.selection.preparation
        h = self.selection.hypothesis
        if h is None or len(self.submission.hypotheses) != 1 or self.submission.hypotheses[0] is not h:
            raise ValueError("translation requires exact selected hypothesis")
        for retained, supplied in ((p.sources, self.submission.sources),
                                   (tuple(s.statement for s in p.statements), self.submission.statements)):
            if len(retained) != len(supplied) or any(a is not b for a, b in zip(retained, supplied)):
                raise ValueError("translation must retain evidence by identity and order")

    def prepare_research(self, *, evaluation_date, maturity_authority):
        """Return existing context; keep this translation alongside it for lineage."""
        _record(self, EventEntryTranslation)
        p = self.selection.preparation
        return prepare_event_entry_research(
            p.user_input, evaluation_date=evaluation_date, submission=self.submission,
            grounding_methodology=p.grounding_methodology,
            selected_hypothesis=self.selection.hypothesis, maturity_authority=maturity_authority,
        )


def translate_event_entry_selection(selection, *, submission_id, event_id,
                                    observed_at, event_description, event_date_range):
    """No assessment here. All temporal inputs explicit, including None.

To add evidence or change a draft, prepare a new batch and obtain human selection
again. This bridge cannot silently supplement or replace the chosen hypothesis.
"""
    _record(selection, EventEntryHypothesisSelection)
    if selection.hypothesis is None:
        raise ValueError("NONE stops before EI")
    p = selection.preparation
    submission = EventIntelligenceSubmission(
        submission_id, event_id, "event-entry-preparation", "1.0", observed_at,
        event_description, event_date_range, p.sources,
        tuple(s.statement for s in p.statements), (selection.hypothesis,),
    )
    return EventEntryTranslation(selection, submission)
