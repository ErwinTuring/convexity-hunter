"""Deterministic handoff from accepted Event Intelligence to discovery."""

from dataclasses import dataclass

from .event_intelligence import (
    EventIntelligenceAcceptanceResult,
    EventIntelligenceAcceptanceStatus,
    EventIntelligenceSubmission,
    EventUnderlyingHypothesis,
)


__all__ = (
    "DiscoveryEntryHandoff",
    "create_discovery_entry_handoff",
)


_ACCEPTANCE_VERSION = "event-intelligence-acceptance-v0.2"


def _validate_handoff_inputs(
    acceptance_result: object,
    selected_hypothesis: object,
) -> None:
    if type(acceptance_result) is not EventIntelligenceAcceptanceResult:
        raise TypeError(
            "acceptance_result must have exact type "
            "EventIntelligenceAcceptanceResult"
        )
    if type(selected_hypothesis) is not EventUnderlyingHypothesis:
        raise TypeError(
            "selected_hypothesis must have exact type EventUnderlyingHypothesis"
        )
    if any(
        field_name not in vars(acceptance_result)
        for field_name in ("submission", "status", "issues", "assessment_version")
    ):
        raise ValueError("acceptance_result is malformed")

    try:
        status = acceptance_result.status
        issues = acceptance_result.issues
        assessment_version = acceptance_result.assessment_version
        submission = acceptance_result.submission
    except AttributeError as error:
        raise ValueError("acceptance_result is malformed") from error

    if type(status) is not EventIntelligenceAcceptanceStatus:
        raise TypeError(
            "acceptance_result.status must have exact type "
            "EventIntelligenceAcceptanceStatus"
        )
    if status is not EventIntelligenceAcceptanceStatus.ACCEPTED:
        raise ValueError("acceptance_result must be accepted")
    if type(issues) is not tuple:
        raise TypeError("acceptance_result.issues must have exact type tuple")
    if issues:
        raise ValueError("accepted handoff requires no acceptance issues")
    if type(assessment_version) is not str:
        raise TypeError("acceptance_result.assessment_version must have exact type str")
    if assessment_version != _ACCEPTANCE_VERSION:
        raise ValueError(
            f"acceptance_result.assessment_version must be {_ACCEPTANCE_VERSION!r}"
        )
    if type(submission) is not EventIntelligenceSubmission:
        raise TypeError(
            "acceptance_result.submission must have exact type "
            "EventIntelligenceSubmission"
        )

    try:
        rebuilt_submission = EventIntelligenceSubmission(
            submission.submission_id,
            submission.event_id,
            submission.producer_id,
            submission.producer_version,
            submission.observed_at,
            submission.event_description,
            submission.event_date_range,
            submission.sources,
            submission.statements,
            submission.hypotheses,
        )
    except AttributeError as error:
        raise ValueError("acceptance_result.submission is malformed") from error
    if rebuilt_submission != submission:
        raise ValueError("acceptance_result.submission is not intrinsically valid")
    if not any(
        selected_hypothesis is hypothesis
        for hypothesis in submission.hypotheses
    ):
        raise ValueError(
            "selected_hypothesis must be retained by identity in the submission"
        )


@dataclass(frozen=True)
class DiscoveryEntryHandoff:
    """One explicit accepted hypothesis selected for later discovery."""

    acceptance_result: EventIntelligenceAcceptanceResult
    selected_hypothesis: EventUnderlyingHypothesis

    def __post_init__(self) -> None:
        _validate_handoff_inputs(
            self.acceptance_result,
            self.selected_hypothesis,
        )


def create_discovery_entry_handoff(
    acceptance_result: EventIntelligenceAcceptanceResult,
    selected_hypothesis: EventUnderlyingHypothesis,
) -> DiscoveryEntryHandoff:
    """Retain one caller-selected accepted hypothesis without semantic replay."""

    _validate_handoff_inputs(acceptance_result, selected_hypothesis)
    return DiscoveryEntryHandoff(acceptance_result, selected_hypothesis)
