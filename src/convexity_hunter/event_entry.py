"""User-origin entry into existing evidence-governed Event Intelligence.

This boundary binds caller-prepared evidence to a user request. It performs
no search, factual verification, semantic rewriting, or market operations.
"""

import datetime
from dataclasses import dataclass
from typing import Optional, Tuple

from .discovery_entry import create_discovery_entry_handoff
from .event_intelligence import (
    EventIntelligenceAcceptanceResult, EventIntelligenceAcceptanceStatus,
    EventIntelligenceSubmission, EventUnderlyingHypothesis,
    assess_event_intelligence_submission,
)
from .option_chain_discovery import (
    OptionChainDiscoveryRequest, OptionMaturityAuthority,
    create_option_chain_discovery_request,
)

__all__ = ("UserEventInput", "EventEntryResearchContext", "prepare_event_entry_research")


def _text(value, name):
    if type(value) is not str:
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be blank")


@dataclass(frozen=True)
class UserEventInput:
    """Caller claims/hints only; never an authoritative evidence record."""

    description: str
    provisional_symbols: Tuple[str, ...] = ()
    source_locators: Tuple[str, ...] = ()
    event_date: Optional[datetime.date] = None

    def __post_init__(self):
        _text(self.description, "description")
        for name in ("provisional_symbols", "source_locators"):
            values = getattr(self, name)
            if type(values) is not tuple:
                raise TypeError(f"{name} must be a tuple")
            for value in values:
                _text(value, name)
        if self.event_date is not None and type(self.event_date) is not datetime.date:
            raise TypeError("event_date must be a date")


@dataclass(frozen=True)
class EventEntryResearchContext:
    """Keep this sidecar with downstream artifacts; it is not Engine evidence.

An accepted assessment alone is not option readiness. A non-null request is
the existing downstream boundary, not a selected option or research candidate.
"""

    user_input: UserEventInput
    grounding_methodology: Optional[str]
    assessment: Optional[EventIntelligenceAcceptanceResult]
    option_request: Optional[OptionChainDiscoveryRequest]
    blocking_reasons: Tuple[str, ...]

    @property
    def entry_origin(self) -> str:
        return "EVENT_ENTRY"


def prepare_event_entry_research(
    user_input: UserEventInput,
    *,
    evaluation_date: datetime.date,
    submission: Optional[EventIntelligenceSubmission] = None,
    grounding_methodology: Optional[str] = None,
    selected_hypothesis: Optional[EventUnderlyingHypothesis] = None,
    maturity_authority: OptionMaturityAuthority = OptionMaturityAuthority.HYPOTHESIS_ALIGNED,
) -> EventEntryResearchContext:
    """Assess supplied evidence, then create the unchanged option handoff.

Grounding methodology is the caller's explicit account of how retained source
evidence supports/refutes the input. It is not independently verified here.
No hints are copied into submission. Missing grounding returns a blocked
context; intrinsic errors and existing stale/maturity exceptions propagate.
There is no default hypothesis or exact option selection, even for one item.
"""
    if type(user_input) is not UserEventInput:
        raise TypeError("user_input must be UserEventInput")
    UserEventInput.__post_init__(user_input)
    if type(evaluation_date) is not datetime.date:
        raise TypeError("evaluation_date must be a date")
    if type(maturity_authority) is not OptionMaturityAuthority:
        raise TypeError("maturity_authority must be OptionMaturityAuthority")
    if grounding_methodology is not None:
        _text(grounding_methodology, "grounding_methodology")
    if submission is None:
        return EventEntryResearchContext(user_input, grounding_methodology, None, None,
                                         ("missing_source_submission",))
    if grounding_methodology is None:
        return EventEntryResearchContext(user_input, None, None, None,
                                         ("missing_grounding_methodology",))
    assessment = assess_event_intelligence_submission(submission)
    if assessment.status is not EventIntelligenceAcceptanceStatus.ACCEPTED:
        return EventEntryResearchContext(user_input, grounding_methodology, assessment, None,
                                         ("event_intelligence_not_accepted",))
    if selected_hypothesis is None:
        return EventEntryResearchContext(user_input, grounding_methodology, assessment, None,
                                         ("missing_selected_hypothesis",))
    handoff = create_discovery_entry_handoff(assessment, selected_hypothesis)
    request = create_option_chain_discovery_request(
        handoff, evaluation_date=evaluation_date, maturity_authority=maturity_authority,
    )
    return EventEntryResearchContext(user_input, grounding_methodology, assessment, request, ())
