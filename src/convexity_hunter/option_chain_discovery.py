"""Provider-neutral option-chain discovery request boundary."""

import datetime
from dataclasses import dataclass

from .discovery_entry import DiscoveryEntryHandoff
from .event_intelligence import (
    DistributionChangeMode,
    EventUnderlyingHypothesis,
    HypothesisReassessment,
    MethodologizedDateRange,
)
from .market_data import UnderlyingKey


__all__ = (
    "OptionChainDiscoveryRequest",
    "create_option_chain_discovery_request",
)


_MINIMUM_DTE_DAYS = 30
_MAXIMUM_DTE_DAYS = 150
_EVENT_BUFFER_DAYS = 30


def _validate_date_only(name: str, value: object) -> datetime.date:
    if type(value) is not datetime.date:
        raise TypeError(f"{name} must have exact type date")
    return value


def _complete_expected_window_end(
    value: object,
) -> object:
    if type(value) is not MethodologizedDateRange:
        return None
    if (
        type(value.start_date) is not datetime.date
        or type(value.end_date) is not datetime.date
        or type(value.methodology) is not str
        or not value.methodology
    ):
        return None
    return value.end_date


def _validate_request_inputs(
    discovery_entry_handoff: object,
    evaluation_date: object,
) -> None:
    if type(discovery_entry_handoff) is not DiscoveryEntryHandoff:
        raise TypeError(
            "discovery_entry_handoff must have exact type DiscoveryEntryHandoff"
        )
    evaluation_date = _validate_date_only("evaluation_date", evaluation_date)
    try:
        rebuilt_handoff = DiscoveryEntryHandoff(
            discovery_entry_handoff.acceptance_result,
            discovery_entry_handoff.selected_hypothesis,
        )
    except AttributeError as error:
        raise ValueError("discovery_entry_handoff is malformed") from error
    if rebuilt_handoff != discovery_entry_handoff:
        raise ValueError("discovery_entry_handoff is not intrinsically valid")

    hypothesis = discovery_entry_handoff.selected_hypothesis
    if type(hypothesis) is not EventUnderlyingHypothesis:
        raise TypeError(
            "selected hypothesis must have exact type EventUnderlyingHypothesis"
        )
    if type(hypothesis.underlying_key) is not UnderlyingKey:
        raise ValueError("selected hypothesis requires an underlying_key")
    if type(hypothesis.distribution_mode) is not DistributionChangeMode:
        raise ValueError("selected hypothesis requires a distribution_mode")
    if hypothesis.reassessment is not None and type(
        hypothesis.reassessment
    ) is not HypothesisReassessment:
        raise TypeError(
            "selected hypothesis reassessment must have exact type "
            "HypothesisReassessment"
        )
    event_window_end = _complete_expected_window_end(hypothesis.expected_window)
    applicability_boundaries = []
    if type(event_window_end) is datetime.date:
        applicability_boundaries.append(event_window_end)
    if hypothesis.reassessment is not None:
        applicability_boundaries.append(hypothesis.reassessment.reassessment_by)
    if applicability_boundaries and evaluation_date > min(applicability_boundaries):
        raise ValueError("selected hypothesis is expired for evaluation_date")
    if type(event_window_end) is not datetime.date:
        raise ValueError("missing_authoritative_maturity_anchor")

    try:
        minimum_expiration = max(
            evaluation_date + datetime.timedelta(days=_MINIMUM_DTE_DAYS),
            event_window_end + datetime.timedelta(days=_EVENT_BUFFER_DAYS),
        )
        maximum_expiration = evaluation_date + datetime.timedelta(
            days=_MAXIMUM_DTE_DAYS
        )
    except (OverflowError, ValueError) as error:
        raise ValueError("discovery expiration date arithmetic failed") from error
    if minimum_expiration > maximum_expiration:
        raise ValueError("discovery expiration interval is empty")


@dataclass(frozen=True)
class OptionChainDiscoveryRequest:
    """One accepted hypothesis plus a caller-supplied evaluation date."""

    discovery_entry_handoff: DiscoveryEntryHandoff
    evaluation_date: datetime.date

    def __post_init__(self) -> None:
        _validate_request_inputs(
            self.discovery_entry_handoff,
            self.evaluation_date,
        )

    @property
    def underlying_key(self) -> UnderlyingKey:
        """Return the exact underlying retained by the selected hypothesis."""

        return self.discovery_entry_handoff.selected_hypothesis.underlying_key

    @property
    def distribution_mode(self) -> DistributionChangeMode:
        """Return the exact distribution mode retained by the hypothesis."""

        return self.discovery_entry_handoff.selected_hypothesis.distribution_mode

    @property
    def event_window_end_date(self) -> datetime.date:
        """Return the accepted inclusive event-window end date."""

        return (
            self.discovery_entry_handoff.selected_hypothesis.expected_window.end_date
        )

    @property
    def minimum_expiration_date(self) -> datetime.date:
        """Return the inclusive lower expiration boundary."""

        return max(
            self.evaluation_date + datetime.timedelta(days=_MINIMUM_DTE_DAYS),
            self.event_window_end_date
            + datetime.timedelta(days=_EVENT_BUFFER_DAYS),
        )

    @property
    def maximum_expiration_date(self) -> datetime.date:
        """Return the inclusive 150-calendar-day expiration boundary."""

        return self.evaluation_date + datetime.timedelta(days=_MAXIMUM_DTE_DAYS)


def create_option_chain_discovery_request(
    discovery_entry_handoff: DiscoveryEntryHandoff,
    *,
    evaluation_date: datetime.date,
) -> OptionChainDiscoveryRequest:
    """Create a bounded request without provider access or contract selection."""

    _validate_request_inputs(discovery_entry_handoff, evaluation_date)
    return OptionChainDiscoveryRequest(discovery_entry_handoff, evaluation_date)
