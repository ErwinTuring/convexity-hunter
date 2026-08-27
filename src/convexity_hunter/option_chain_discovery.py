"""Provider-neutral option-chain discovery request boundary."""

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .discovery_entry import DiscoveryEntryHandoff
from .evidence import OptionStructure
from .event_intelligence import (
    DistributionChangeMode,
    EventUnderlyingHypothesis,
    HypothesisReassessment,
    MethodologizedDateRange,
)
from .market_data import UnderlyingKey


__all__ = (
    "OptionMaturityAuthority",
    "HypothesisMaturityAlignment",
    "OptionChainDiscoveryRequest",
    "OptionResearchMaturityContext",
    "create_option_chain_discovery_request",
)


_MINIMUM_DTE_DAYS = 30
_MAXIMUM_DTE_DAYS = 150
_EVENT_BUFFER_DAYS = 30


class OptionMaturityAuthority(str, Enum):
    """Closed authority for option-discovery maturity boundaries."""

    HYPOTHESIS_ALIGNED = "hypothesis_aligned"
    NEUTRAL_STRUCTURAL_RESEARCH = "neutral_structural_research"


class HypothesisMaturityAlignment(str, Enum):
    """Whether option maturity is aligned to an expected impact window."""

    ESTABLISHED = "established"
    NOT_ESTABLISHED = "not_established"


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
    maturity_authority: object,
) -> None:
    if type(discovery_entry_handoff) is not DiscoveryEntryHandoff:
        raise TypeError(
            "discovery_entry_handoff must have exact type DiscoveryEntryHandoff"
        )
    evaluation_date = _validate_date_only("evaluation_date", evaluation_date)
    if type(maturity_authority) is not OptionMaturityAuthority:
        raise TypeError(
            "maturity_authority must have exact type OptionMaturityAuthority"
        )
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

    if maturity_authority is OptionMaturityAuthority.HYPOTHESIS_ALIGNED:
        if type(event_window_end) is not datetime.date:
            raise ValueError("missing_authoritative_maturity_anchor")
    else:
        if type(event_window_end) is datetime.date:
            raise ValueError(
                "neutral_structural_research_requires_absent_expected_window"
            )
        if hypothesis.reassessment is None:
            raise ValueError("discovery_entry_handoff is not intrinsically valid")

    try:
        minimum_expiration = evaluation_date + datetime.timedelta(
            days=_MINIMUM_DTE_DAYS
        )
        if maturity_authority is OptionMaturityAuthority.HYPOTHESIS_ALIGNED:
            minimum_expiration = max(
                minimum_expiration,
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
    maturity_authority: OptionMaturityAuthority = (
        OptionMaturityAuthority.HYPOTHESIS_ALIGNED
    )

    def __post_init__(self) -> None:
        _validate_request_inputs(
            self.discovery_entry_handoff,
            self.evaluation_date,
            self.maturity_authority,
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
    def hypothesis_maturity_alignment(self) -> HypothesisMaturityAlignment:
        """Return the alignment state derived from the retained authority."""

        if self.maturity_authority is OptionMaturityAuthority.HYPOTHESIS_ALIGNED:
            return HypothesisMaturityAlignment.ESTABLISHED
        return HypothesisMaturityAlignment.NOT_ESTABLISHED

    @property
    def event_window_end_date(self) -> Optional[datetime.date]:
        """Return the accepted impact-window end, absent for neutral research."""

        if (
            self.maturity_authority
            is OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH
        ):
            return None
        return self.discovery_entry_handoff.selected_hypothesis.expected_window.end_date

    @property
    def minimum_expiration_date(self) -> datetime.date:
        """Return the inclusive lower expiration boundary."""

        lower = self.evaluation_date + datetime.timedelta(days=_MINIMUM_DTE_DAYS)
        if self.maturity_authority is OptionMaturityAuthority.HYPOTHESIS_ALIGNED:
            return max(
                lower,
                self.event_window_end_date
                + datetime.timedelta(days=_EVENT_BUFFER_DAYS),
            )
        return lower

    @property
    def maximum_expiration_date(self) -> datetime.date:
        """Return the inclusive 150-calendar-day expiration boundary."""

        return self.evaluation_date + datetime.timedelta(days=_MAXIMUM_DTE_DAYS)


def _validate_maturity_context_request(
    value: object,
) -> OptionChainDiscoveryRequest:
    if type(value) is not OptionChainDiscoveryRequest:
        raise TypeError(
            "discovery_request must have exact type OptionChainDiscoveryRequest"
        )
    try:
        rebuilt = OptionChainDiscoveryRequest(
            value.discovery_entry_handoff,
            value.evaluation_date,
            value.maturity_authority,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("discovery_request is malformed") from error
    if rebuilt != value:
        raise ValueError("discovery_request is not intrinsically valid")
    return value


@dataclass(frozen=True)
class OptionResearchMaturityContext:
    """Bind one discovery request to one exact human-selected structure."""

    discovery_request: OptionChainDiscoveryRequest
    structure: OptionStructure

    def __post_init__(self) -> None:
        request = _validate_maturity_context_request(self.discovery_request)
        if type(self.structure) is not OptionStructure:
            raise TypeError("structure must have exact type OptionStructure")
        try:
            rebuilt_structure = OptionStructure(
                self.structure.legs,
                self.structure.assumed_portfolio_value,
                self.structure.expected_holding_days,
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("maturity_context_structure_mismatch") from error
        if rebuilt_structure != self.structure:
            raise ValueError("maturity_context_structure_mismatch")
        if any(
            leg.underlying != request.underlying_key.symbol
            or leg.expiration < request.minimum_expiration_date
            or leg.expiration > request.maximum_expiration_date
            for leg in self.structure.legs
        ):
            raise ValueError("maturity_context_structure_mismatch")

    @property
    def maturity_authority(self) -> OptionMaturityAuthority:
        """Return the exact authority retained by the request."""

        return self.discovery_request.maturity_authority

    @property
    def hypothesis_maturity_alignment(self) -> HypothesisMaturityAlignment:
        """Return the exact alignment derived by the request."""

        return self.discovery_request.hypothesis_maturity_alignment


def _validate_option_research_maturity_context(
    value: object,
) -> OptionResearchMaturityContext:
    """Revalidate one exact context at every downstream trust boundary."""

    if type(value) is not OptionResearchMaturityContext:
        raise TypeError(
            "maturity_context must have exact type OptionResearchMaturityContext"
        )
    try:
        rebuilt = OptionResearchMaturityContext(
            value.discovery_request,
            value.structure,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("maturity_context is malformed") from error
    if rebuilt != value:
        raise ValueError("maturity_context is not intrinsically valid")
    return value


def create_option_chain_discovery_request(
    discovery_entry_handoff: DiscoveryEntryHandoff,
    *,
    evaluation_date: datetime.date,
    maturity_authority: OptionMaturityAuthority = (
        OptionMaturityAuthority.HYPOTHESIS_ALIGNED
    ),
) -> OptionChainDiscoveryRequest:
    """Create a bounded request without provider access or contract selection."""

    _validate_request_inputs(
        discovery_entry_handoff,
        evaluation_date,
        maturity_authority,
    )
    return OptionChainDiscoveryRequest(
        discovery_entry_handoff,
        evaluation_date,
        maturity_authority,
    )
