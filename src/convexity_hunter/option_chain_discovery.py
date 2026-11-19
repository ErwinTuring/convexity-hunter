"""Provider-neutral option-chain discovery request boundary."""

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from typing import Tuple

from .discovery_entry import DiscoveryEntryHandoff
from .evidence import OptionStructure
from .event_intelligence import (
    DistributionChangeMode,
    EventSourceReference,
    EventStatement,
    EventStatementKind,
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
    "ExplorationLead",
    "ExploratoryOptionChainRequest",
    "validate_exploration_lead",
    "validate_exploratory_option_chain_request",
)


_MINIMUM_DTE_DAYS = 30
_MAXIMUM_DTE_DAYS = 150
_EVENT_BUFFER_DAYS = 30


class OptionMaturityAuthority(str, Enum):
    """Closed authority for option-discovery maturity boundaries."""

    HYPOTHESIS_ALIGNED = "hypothesis_aligned"
    NEUTRAL_STRUCTURAL_RESEARCH = "neutral_structural_research"
    EXPLORATORY_STRUCTURE_RESEARCH = "exploratory_structure_research"


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
    if maturity_authority not in {
        OptionMaturityAuthority.HYPOTHESIS_ALIGNED,
        OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
    }:
        raise ValueError(
            "OptionChainDiscoveryRequest does not accept "
            "EXPLORATORY_STRUCTURE_RESEARCH"
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
    elif maturity_authority is OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH:
        if type(event_window_end) is datetime.date:
            raise ValueError(
                "neutral_structural_research_requires_absent_expected_window"
            )
        if hypothesis.reassessment is None:
            raise ValueError("discovery_entry_handoff is not intrinsically valid")
    else:  # Explicit closed dispatch; the third authority has its own request.
        raise ValueError("unsupported OptionChainDiscoveryRequest authority")

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


def _validate_exploration_lead_fields(value: object) -> None:
    for name in (
        "lead_id",
        "event_description",
        "underlying_reference",
        "validation_reference",
    ):
        item = getattr(value, name)
        if type(item) is not str or not item.strip():
            raise ValueError(f"{name} must be a non-empty string")

    observed_at = value.observed_at
    if type(observed_at) is not datetime.datetime:
        raise TypeError("observed_at must have exact type datetime")
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")

    underlying_key = value.underlying_key
    if type(underlying_key) is not UnderlyingKey:
        raise TypeError("underlying_key must have exact type UnderlyingKey")
    try:
        rebuilt_key = UnderlyingKey(
            underlying_key.symbol,
            underlying_key.listing_mic,
            underlying_key.security_type,
            underlying_key.currency,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("underlying_key is malformed") from error
    if rebuilt_key != underlying_key:
        raise ValueError("underlying_key is not intrinsically valid")

    if type(value.sources) is not tuple or not value.sources:
        raise TypeError("sources must be a non-empty tuple")
    sources = {}
    for source in value.sources:
        if type(source) is not EventSourceReference:
            raise TypeError("sources must contain EventSourceReference values")
        try:
            rebuilt_source = EventSourceReference(
                source.source_id,
                source.locator,
                source.title,
                source.published_at,
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("source is malformed") from error
        if rebuilt_source != source or source.source_id in sources:
            raise ValueError("sources must be intrinsically valid and unique")
        if type(source.locator) is not str or not source.locator.strip():
            raise ValueError("every retained source locator must be non-empty")
        sources[source.source_id] = source

    if type(value.statements) is not tuple or not value.statements:
        raise TypeError("statements must be a non-empty tuple")
    statements = {}
    for statement in value.statements:
        if type(statement) is not EventStatement:
            raise TypeError("statements must contain EventStatement values")
        try:
            rebuilt_statement = EventStatement(
                statement.statement_id,
                statement.kind,
                statement.text,
                statement.source_ids,
                statement.dependency_statement_ids,
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("statement is malformed") from error
        if rebuilt_statement != statement or statement.statement_id in statements:
            raise ValueError("statements must be intrinsically valid and unique")
        if type(statement.text) is not str or not statement.text.strip():
            raise ValueError("every retained statement text must be non-empty")
        statements[statement.statement_id] = statement

    if type(value.uncertainties) is not tuple or any(
        type(item) is not str or not item.strip() for item in value.uncertainties
    ):
        raise TypeError("uncertainties must be a tuple of non-empty strings")

    for statement in statements.values():
        if set(statement.source_ids) - set(sources):
            raise ValueError("statement references an unretained source")
        if set(statement.dependency_statement_ids) - set(statements):
            raise ValueError("statement references an unretained dependency")

    states = {statement_id: 0 for statement_id in statements}
    for root_id in statements:
        if states[root_id] == 2:
            continue
        stack = [(root_id, False)]
        while stack:
            statement_id, exiting = stack.pop()
            if exiting:
                states[statement_id] = 2
                continue
            if states[statement_id] == 2:
                continue
            if states[statement_id] == 1:
                raise ValueError("statement dependencies must not contain a cycle")
            states[statement_id] = 1
            stack.append((statement_id, True))
            for dependency_id in reversed(
                statements[statement_id].dependency_statement_ids
            ):
                if states[dependency_id] == 1:
                    raise ValueError("statement dependencies must not contain a cycle")
                if states[dependency_id] == 0:
                    stack.append((dependency_id, False))

    event_statement = statements.get(value.event_statement_id)
    exposure_statement = statements.get(value.exposure_statement_id)
    if type(value.event_statement_id) is not str or not value.event_statement_id:
        raise ValueError("event_statement_id must be a non-empty string")
    if type(value.exposure_statement_id) is not str or not value.exposure_statement_id:
        raise ValueError("exposure_statement_id must be a non-empty string")
    if event_statement is None or (
        event_statement.kind is not EventStatementKind.OBSERVED_FACT
        or not event_statement.source_ids
    ):
        raise ValueError("event statement must be a source-backed observed fact")
    if exposure_statement is None:
        raise ValueError("exposure statement is not retained")
    if exposure_statement.kind is EventStatementKind.OBSERVED_FACT:
        if not exposure_statement.source_ids:
            raise ValueError(
                "observed-fact exposure statement must be source-backed"
            )
    elif exposure_statement.kind is EventStatementKind.INTERPRETATION:
        closure = set()
        pending = [exposure_statement.statement_id]
        while pending:
            statement_id = pending.pop()
            if statement_id in closure:
                continue
            closure.add(statement_id)
            pending.extend(statements[statement_id].dependency_statement_ids)
        if not any(
            statements[statement_id].kind is EventStatementKind.OBSERVED_FACT
            and bool(statements[statement_id].source_ids)
            for statement_id in closure
        ):
            raise ValueError(
                "interpretive exposure statement requires a source-backed "
                "observed-fact dependency closure"
            )
    else:
        raise ValueError("exposure statement kind is unsupported")


@dataclass(frozen=True)
class ExplorationLead:
    """Host-projected evidence for neutral structure exploration.

    Intrinsic reconstruction validates the retained evidence graph only. It
    does not authenticate source truth, admission, receipt, or listing checks;
    those remain Host-owned trust boundaries.
    """

    lead_id: str
    event_description: str
    observed_at: datetime.datetime
    underlying_key: UnderlyingKey
    sources: Tuple[EventSourceReference, ...]
    statements: Tuple[EventStatement, ...]
    event_statement_id: str
    exposure_statement_id: str
    underlying_reference: str
    validation_reference: str
    uncertainties: Tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_exploration_lead_fields(self)


def validate_exploration_lead(value: object) -> ExplorationLead:
    """Reconstruct one lead at a trust boundary without authenticating it."""

    if type(value) is not ExplorationLead:
        raise TypeError("lead must have exact type ExplorationLead")
    try:
        rebuilt = ExplorationLead(
            value.lead_id,
            value.event_description,
            value.observed_at,
            value.underlying_key,
            value.sources,
            value.statements,
            value.event_statement_id,
            value.exposure_statement_id,
            value.underlying_reference,
            value.validation_reference,
            value.uncertainties,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("exploration lead is malformed") from error
    if rebuilt != value:
        raise ValueError("exploration lead is not intrinsically valid")
    return value


def _validate_exploratory_request_inputs(
    lead: object, evaluation_date: object
) -> None:
    validate_exploration_lead(lead)
    evaluation_date = _validate_date_only("evaluation_date", evaluation_date)
    try:
        observed_utc_date = lead.observed_at.astimezone(
            datetime.timezone.utc
        ).date()
    except (OverflowError, ValueError) as error:
        raise ValueError("exploration lead observed_at is invalid") from error
    if observed_utc_date > evaluation_date:
        raise ValueError("exploration lead observed_at is after evaluation_date")
    try:
        minimum = evaluation_date + datetime.timedelta(days=_MINIMUM_DTE_DAYS)
        maximum = evaluation_date + datetime.timedelta(days=_MAXIMUM_DTE_DAYS)
    except (OverflowError, ValueError) as error:
        raise ValueError("exploration expiration date arithmetic failed") from error
    if minimum > maximum:
        raise ValueError("exploration expiration interval is empty")


@dataclass(frozen=True)
class ExploratoryOptionChainRequest:
    """Explicit 30–150 calendar-DTE request without an EI hypothesis."""

    lead: ExplorationLead
    evaluation_date: datetime.date

    def __post_init__(self) -> None:
        _validate_exploratory_request_inputs(self.lead, self.evaluation_date)

    @property
    def underlying_key(self) -> UnderlyingKey:
        return self.lead.underlying_key

    @property
    def maturity_authority(self) -> OptionMaturityAuthority:
        return OptionMaturityAuthority.EXPLORATORY_STRUCTURE_RESEARCH

    @property
    def hypothesis_maturity_alignment(self) -> HypothesisMaturityAlignment:
        return HypothesisMaturityAlignment.NOT_ESTABLISHED

    @property
    def event_window_end_date(self) -> None:
        return None

    @property
    def minimum_expiration_date(self) -> datetime.date:
        return self.evaluation_date + datetime.timedelta(days=_MINIMUM_DTE_DAYS)

    @property
    def maximum_expiration_date(self) -> datetime.date:
        return self.evaluation_date + datetime.timedelta(days=_MAXIMUM_DTE_DAYS)


def validate_exploratory_option_chain_request(
    value: object,
) -> ExploratoryOptionChainRequest:
    """Reconstruct the closed exploratory request at every provider boundary."""

    if type(value) is not ExploratoryOptionChainRequest:
        raise TypeError(
            "request must have exact type ExploratoryOptionChainRequest"
        )
    try:
        rebuilt = ExploratoryOptionChainRequest(value.lead, value.evaluation_date)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("exploratory option-chain request is malformed") from error
    if rebuilt != value:
        raise ValueError("exploratory option-chain request is not intrinsically valid")
    return value
