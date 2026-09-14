"""Small immutable application composition for one research investigation.

This module coordinates existing domain boundaries.  It does not own event
acceptance, maturity rules, market-data normalization, discrimination math,
candidate assembly, screening, position management, or report economics.
Every numerical or reviewed artifact is retained by reference in an existing
domain result or in the existing reviewed-research service result.
"""

import datetime as _datetime
from dataclasses import dataclass as _dataclass
from dataclasses import replace as _replace
from enum import Enum as _Enum
from typing import Optional as _Optional
from typing import Tuple as _Tuple
from typing import Union as _Union

from . import direct_entry_reviewed_research_service as _reviewed_service
from . import discovery_entry as _discovery_entry
from . import event_discovery as _event_discovery
from . import event_intelligence as _event_intelligence
from . import event_entry_preparation as _event_entry_preparation
from . import convexity_discrimination as _discrimination
from . import convexity_presentation as _presentation
from . import direct_entry_verification as _direct_verification
from . import option_chain_discovery as _option_chain_discovery
from .providers import futu as _futu
from .event_entry import (
    EventEntryResearchContext as _EventEntryResearchContext,
    UserEventInput as _UserEventInput,
)
from .event_entry_preparation import (
    EventEntryHypothesisSelection as _EventEntryHypothesisSelection,
    EventEntryPreparation as _EventEntryPreparation,
    EventEntryTranslation as _EventEntryTranslation,
)
from .event_intelligence import (
    EventIntelligenceAcceptanceResult as _AcceptanceResult,
    EventIntelligenceAcceptanceStatus as _AcceptanceStatus,
    EventUnderlyingHypothesis as _EventUnderlyingHypothesis,
)
from .event_discovery import (
    EventCandidateBatch as _EventCandidateBatch,
    EventCandidateSelection as _EventCandidateSelection,
    EventCandidateTranslation as _EventCandidateTranslation,
)
from .offline_service import (
    PositionManagementPlanRequest as _PositionManagementPlanRequest,
)
from .option_chain_discovery import (
    OptionChainDiscoveryRequest as _OptionChainDiscoveryRequest,
    OptionMaturityAuthority as _OptionMaturityAuthority,
)
from .evidence import OptionStructure as _OptionStructure
from .market_data import OptionContractReference as _OptionContractReference


__all__ = (
    "ResearchCaseEntryOrigin",
    "ResearchCaseStage",
    "ResearchCase",
    "ResearchCaseResearchInput",
    "start_autonomous_discovery_case",
    "continue_autonomous_discovery_case",
    "attach_discovery_submission",
    "select_discovery_hypothesis",
    "start_event_entry_case",
    "attach_event_entry_preparation",
    "continue_event_entry_case",
    "start_direct_entry_case",
    "attach_browser_evidence",
    "attach_discrimination_evidence",
    "select_exact_structure",
    "verify_exact_structure",
    "run_research_case",
    "render_research_case_markdown",
)


class ResearchCaseEntryOrigin(str, _Enum):
    """The product entry lane that created the case."""

    AUTONOMOUS_DISCOVERY = "AUTONOMOUS_DISCOVERY"
    EVENT_ENTRY = "EVENT_ENTRY"
    DIRECT_ENTRY = "DIRECT_ENTRY"


class ResearchCaseStage(str, _Enum):
    """Application state, intentionally separate from CandidateState."""

    DISCOVERY_SELECTION = "discovery_selection"
    EVENT_PREPARATION = "event_preparation"
    EVENT_INTELLIGENCE = "event_intelligence"
    OPTION_DISCOVERY = "option_discovery"
    AWAITING_RTH_EVIDENCE = "awaiting_rth_evidence"
    NO_OPTION_RESEARCH_SURFACE = "no_option_research_surface"
    GEOMETRY_COMPARISON = "geometry_comparison"
    AWAITING_STRUCTURE_SELECTION = "awaiting_structure_selection"
    EXACT_VERIFICATION = "exact_verification"
    ENGINE_RESEARCH = "engine_research"
    SCREENING = "screening"
    COMPLETED = "completed"
    STOPPED_NONE = "stopped_none"


def _required_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must have exact type str")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _require_exact(name: str, value: object, expected_type: type) -> None:
    if type(value) is not expected_type:
        raise TypeError(f"{name} must have exact type {expected_type.__name__}")


def _require_case(value: object) -> "ResearchCase":
    if type(value) is not ResearchCase:
        raise TypeError("case must have exact type ResearchCase")
    # Re-run the case's own boundary without creating a replacement object.
    # This catches constructor-bypassed top-level fields before a transition.
    try:
        ResearchCase.__post_init__(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("case is malformed") from error
    return value


def _require_research_input(value: object) -> "ResearchCaseResearchInput":
    if type(value) is not ResearchCaseResearchInput:
        raise TypeError(
            "research_input must have exact type ResearchCaseResearchInput"
        )
    try:
        ResearchCaseResearchInput.__post_init__(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("research_input is malformed") from error
    return value


def _selection_matches_discrimination(case: "ResearchCase") -> bool:
    selection = case.exact_structure_selection
    discrimination = case.discrimination
    if selection is None or discrimination is None:
        return False
    selected_rows = selection.selected_contracts
    return any(
        tuple(comparison.structure.rows) == selected_rows
        for comparison in discrimination.comparisons
    )


def _assessment_blockers(assessment: _AcceptanceResult) -> _Tuple[str, ...]:
    if assessment.status is _AcceptanceStatus.ACCEPTED:
        return ("awaiting_human_hypothesis_selection",)
    return (
        "event_intelligence_not_accepted",
        *tuple(issue.code.value for issue in assessment.issues),
    )


@_dataclass(frozen=True)
class ResearchCaseResearchInput:
    """Caller-supplied narrative, reviewed artifacts, and screening policy.

    The structure, exact contract references, and maturity context are
    deliberately absent.  ``run_research_case`` injects those from the case's
    retained verification sidecar so a caller cannot substitute them at the
    downstream trust boundary.  The seven reviewed artifact fields accept
    ``None`` exactly as the existing candidate assembler does, which supports
    both partial and full research.
    """

    calculation_id: object
    candidate_id: object
    state: object
    state_rationale: object
    as_of_date: object
    hypothesis: object
    volatility_environment_result: object
    tail_pricing_result: object
    structure_liquidity_result: object
    structure_costs_result: object
    scenario_valuation_result: object
    expiration_payoff_threshold_result: object
    structure_affordability_result: object
    evidence: object
    falsification_conditions: object
    missing_data: object
    false_positive_reasons: object
    ai_interpretation: object
    human_review_questions: object
    calculated_at: object
    screening_policy: object
    position_management_plan_request: _Optional[_PositionManagementPlanRequest] = None

    def __post_init__(self) -> None:
        # Domain producers remain responsible for their exact input contracts.
        # This record only prevents the app request itself from being replaced
        # by a subclass or a mutable top-level plan request.
        if self.position_management_plan_request is not None:
            _require_exact(
                "position_management_plan_request",
                self.position_management_plan_request,
                _PositionManagementPlanRequest,
            )


@_dataclass(frozen=True)
class ResearchCase:
    """One immutable in-memory investigation and its retained sidecars."""

    case_id: str
    entry_origin: ResearchCaseEntryOrigin
    original_input: object
    stage: ResearchCaseStage
    discovery_selection: _Optional[_EventCandidateSelection] = None
    discovery_translation: _Optional[_EventCandidateTranslation] = None
    event_entry_preparation: _Optional[_EventEntryPreparation] = None
    event_entry_selection: _Optional[_EventEntryHypothesisSelection] = None
    event_entry_translation: _Optional[_EventEntryTranslation] = None
    event_entry_context: _Optional[_EventEntryResearchContext] = None
    event_intelligence_assessment: _Optional[_AcceptanceResult] = None
    selected_hypothesis: _Optional[_EventUnderlyingHypothesis] = None
    option_research_request: _Optional[_OptionChainDiscoveryRequest] = None
    browser: _Optional[_futu.FutuExactContractBrowser] = None
    discrimination: _Optional[
        _discrimination.ProbabilityFreeConvexityDiscriminationResult
    ] = None
    exact_structure_selection: _Optional[_futu.FutuExactContractSelection] = None
    futu_selection_verification: _Optional[
        _futu.FutuExactContractSelectionVerification
    ] = None
    direct_contract_references: _Optional[
        _Tuple[_OptionContractReference, ...]
    ] = None
    direct_entry_exact_contract_verification: _Optional[
        _direct_verification.DirectEntryExactContractVerification
    ] = None
    downstream_result: _Optional[
        _reviewed_service.DirectEntryReviewedResearchServiceResult
    ] = None
    blocking_reasons: _Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        case_id = _required_text("case_id", self.case_id)
        _require_exact("entry_origin", self.entry_origin, ResearchCaseEntryOrigin)
        _require_exact("stage", self.stage, ResearchCaseStage)
        if type(self.blocking_reasons) is not tuple:
            raise TypeError("blocking_reasons must have exact type tuple")
        blocking_reasons = tuple(
            _required_text("blocking reason", value)
            for value in self.blocking_reasons
        )
        if len(set(blocking_reasons)) != len(blocking_reasons):
            raise ValueError("blocking_reasons must not contain duplicates")

        if self.entry_origin is ResearchCaseEntryOrigin.AUTONOMOUS_DISCOVERY:
            _require_exact("original_input", self.original_input, _EventCandidateBatch)
            if self.event_entry_preparation is not None:
                raise ValueError("autonomous discovery cannot retain Event Entry preparation")
            if self.event_entry_selection is not None:
                raise ValueError("autonomous discovery cannot retain Event Entry selection")
            if self.event_entry_translation is not None:
                raise ValueError("autonomous discovery cannot retain Event Entry translation")
            if self.event_entry_context is not None:
                raise ValueError("autonomous discovery cannot retain Event Entry context")
            if self.direct_contract_references is not None:
                raise ValueError("autonomous discovery cannot retain direct-entry references")
            if self.direct_entry_exact_contract_verification is not None:
                raise ValueError("autonomous discovery cannot retain direct-entry verification")
            if self.discovery_selection is not None:
                _require_exact(
                    "discovery_selection",
                    self.discovery_selection,
                    _EventCandidateSelection,
                )
                if self.discovery_selection.batch is not self.original_input:
                    raise ValueError("discovery selection must retain the case batch")
            if self.discovery_translation is not None:
                _require_exact(
                    "discovery_translation",
                    self.discovery_translation,
                    _EventCandidateTranslation,
                )
                if self.discovery_selection is None:
                    raise ValueError("discovery translation requires selection")
                if self.discovery_translation.selection is not self.discovery_selection:
                    raise ValueError("discovery translation must retain the exact selection")
            if (
                self.event_intelligence_assessment is not None
                and self.discovery_translation is None
            ):
                raise ValueError("autonomous assessment requires discovery translation")
        elif self.entry_origin is ResearchCaseEntryOrigin.EVENT_ENTRY:
            _require_exact("original_input", self.original_input, _UserEventInput)
            if self.event_entry_preparation is None:
                if self.stage is not ResearchCaseStage.EVENT_PREPARATION:
                    raise ValueError(
                        "raw Event Entry input must await preparation"
                    )
            else:
                _require_exact(
                    "event_entry_preparation",
                    self.event_entry_preparation,
                    _EventEntryPreparation,
                )
                if self.event_entry_preparation.user_input is not self.original_input:
                    raise ValueError("Event Entry preparation must retain the user input")
            if self.discovery_selection is not None:
                raise ValueError("Event Entry cannot retain discovery selection")
            if self.discovery_translation is not None:
                raise ValueError("Event Entry cannot retain discovery translation")
            if self.direct_contract_references is not None:
                raise ValueError("Event Entry cannot retain direct-entry references")
            if self.direct_entry_exact_contract_verification is not None:
                raise ValueError("Event Entry cannot retain direct-entry verification")
            if self.event_entry_selection is not None:
                if self.event_entry_preparation is None:
                    raise ValueError("Event Entry selection requires preparation")
                _require_exact(
                    "event_entry_selection",
                    self.event_entry_selection,
                    _EventEntryHypothesisSelection,
                )
                if self.event_entry_selection.preparation is not self.event_entry_preparation:
                    raise ValueError("Event Entry selection must retain preparation")
                if (
                    self.event_entry_selection.hypothesis is not None
                    and self.selected_hypothesis is not self.event_entry_selection.hypothesis
                ):
                    raise ValueError("Event Entry selection must retain selected hypothesis")
            if (
                self.event_intelligence_assessment is not None
                and self.event_entry_translation is None
            ):
                raise ValueError("Event Entry assessment requires translation")
        else:
            _require_exact("original_input", self.original_input, _OptionStructure)
            if self.discovery_selection is not None:
                raise ValueError("Direct Entry cannot retain discovery selection")
            if self.discovery_translation is not None:
                raise ValueError("Direct Entry cannot retain discovery translation")
            if self.event_entry_preparation is not None:
                raise ValueError("Direct Entry cannot retain Event Entry preparation")
            if self.event_entry_selection is not None:
                raise ValueError("Direct Entry cannot retain Event Entry selection")
            if self.event_entry_translation is not None:
                raise ValueError("Direct Entry cannot retain Event Entry translation")
            if self.event_entry_context is not None:
                raise ValueError("Direct Entry cannot retain Event Entry context")
            if self.option_research_request is not None:
                raise ValueError("Direct Entry cannot retain an option research request")
            if self.browser is not None or self.discrimination is not None:
                raise ValueError("Direct Entry cannot retain Browser evidence")
            if self.exact_structure_selection is not None:
                raise ValueError("Direct Entry cannot retain Futu selection")
            if self.futu_selection_verification is not None:
                raise ValueError("Direct Entry cannot retain Futu selection verification")
            if self.selected_hypothesis is not None:
                raise ValueError("Direct Entry cannot retain an event hypothesis")
            if self.event_intelligence_assessment is not None:
                raise ValueError("Direct Entry cannot retain an event assessment")

        if self.event_entry_translation is not None:
            _require_exact(
                "event_entry_translation",
                self.event_entry_translation,
                _EventEntryTranslation,
            )
            if self.event_entry_selection is None:
                raise ValueError("Event Entry translation requires selection")
            if self.event_entry_translation.selection is not self.event_entry_selection:
                raise ValueError("Event Entry translation must retain selection")

        if self.event_entry_context is not None:
            _require_exact(
                "event_entry_context",
                self.event_entry_context,
                _EventEntryResearchContext,
            )
            if self.entry_origin is not ResearchCaseEntryOrigin.EVENT_ENTRY:
                raise ValueError("only Event Entry can retain Event Entry context")
            if self.event_entry_context.user_input is not self.original_input:
                raise ValueError("Event Entry context must retain user input")
            if self.event_entry_translation is None:
                raise ValueError("Event Entry context requires translation")
            if self.event_entry_context.assessment is not self.event_intelligence_assessment:
                raise ValueError("Event Entry context must retain the case assessment")
            if self.event_entry_context.option_request is not self.option_research_request:
                raise ValueError("Event Entry context must retain the case request")

        if self.event_intelligence_assessment is not None:
            _require_exact(
                "event_intelligence_assessment",
                self.event_intelligence_assessment,
                _AcceptanceResult,
            )
            if self.discovery_translation is not None and (
                self.event_intelligence_assessment.submission
                is not self.discovery_translation.submission
            ):
                raise ValueError("assessment must retain discovery translation submission")
            if self.event_entry_translation is not None and (
                self.event_intelligence_assessment.submission
                is not self.event_entry_translation.submission
            ):
                raise ValueError("assessment must retain Event Entry translation submission")

        if self.selected_hypothesis is not None:
            _require_exact(
                "selected_hypothesis",
                self.selected_hypothesis,
                _EventUnderlyingHypothesis,
            )
            if self.event_intelligence_assessment is None:
                raise ValueError("selected hypothesis requires an assessment")
            if not any(
                self.selected_hypothesis is hypothesis
                for hypothesis in self.event_intelligence_assessment.submission.hypotheses
            ):
                raise ValueError("selected hypothesis must be retained by the assessment")
            if self.entry_origin is ResearchCaseEntryOrigin.AUTONOMOUS_DISCOVERY:
                if self.discovery_translation is None:
                    raise ValueError("autonomous hypothesis requires discovery translation")
            elif self.entry_origin is ResearchCaseEntryOrigin.EVENT_ENTRY:
                if self.event_entry_selection is None:
                    raise ValueError("Event Entry hypothesis requires selection")
                if self.event_entry_selection.hypothesis is not self.selected_hypothesis:
                    raise ValueError("selected hypothesis must retain Event Entry selection")
            if self.event_entry_selection is not None and (
                self.event_entry_selection.hypothesis is not self.selected_hypothesis
            ):
                raise ValueError("selected hypothesis must retain Event Entry selection")

        if self.option_research_request is not None:
            _require_exact(
                "option_research_request",
                self.option_research_request,
                _OptionChainDiscoveryRequest,
            )
            if self.entry_origin is ResearchCaseEntryOrigin.DIRECT_ENTRY:
                raise ValueError("Direct Entry cannot retain an option research request")
            if self.event_intelligence_assessment is None or self.selected_hypothesis is None:
                raise ValueError("option research request requires selected accepted hypothesis")
            handoff = self.option_research_request.discovery_entry_handoff
            if handoff.acceptance_result is not self.event_intelligence_assessment:
                raise ValueError("option research request must retain the case assessment")
            if handoff.selected_hypothesis is not self.selected_hypothesis:
                raise ValueError("option research request must retain selected hypothesis")

        if self.browser is not None:
            _require_exact("browser", self.browser, _futu.FutuExactContractBrowser)
            if self.option_research_request is None:
                raise ValueError("Browser evidence requires an option research request")
            request = self.browser.discovery_evidence.discovery_request
            if request is not self.option_research_request:
                raise ValueError("Browser must retain the exact option research request")

        if self.discrimination is not None:
            _require_exact(
                "discrimination",
                self.discrimination,
                _discrimination.ProbabilityFreeConvexityDiscriminationResult,
            )
            if self.browser is None:
                raise ValueError("discrimination requires Browser evidence")
            if self.discrimination.browser is not self.browser:
                raise ValueError("discrimination must retain the exact Browser")

        if self.exact_structure_selection is not None:
            _require_exact(
                "exact_structure_selection",
                self.exact_structure_selection,
                _futu.FutuExactContractSelection,
            )
            if self.browser is None or self.discrimination is None:
                raise ValueError("exact structure selection requires Browser discrimination")
            if self.exact_structure_selection.browser is not self.browser:
                raise ValueError("exact structure selection must retain the exact Browser")
            try:
                rebuilt_selection = _futu.FutuExactContractSelection(
                    self.exact_structure_selection.browser,
                    self.exact_structure_selection.selected_contracts,
                    self.exact_structure_selection.structure,
                )
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError("exact structure selection is malformed") from error
            if rebuilt_selection != self.exact_structure_selection:
                raise ValueError("exact structure selection is not intrinsically valid")
            if not _selection_matches_discrimination(self):
                raise ValueError("exact structure selection must match a discrimination comparison")

        if self.futu_selection_verification is not None:
            _require_exact(
                "futu_selection_verification",
                self.futu_selection_verification,
                _futu.FutuExactContractSelectionVerification,
            )
            if self.exact_structure_selection is None:
                raise ValueError("Futu verification requires exact structure selection")
            if self.futu_selection_verification.selection is not self.exact_structure_selection:
                raise ValueError("Futu verification must retain exact selection")
            if self.browser is None or (
                self.futu_selection_verification.selection.browser is not self.browser
            ):
                raise ValueError("Futu verification must retain exact Browser")
            try:
                rebuilt_verification = _futu.FutuExactContractSelectionVerification(
                    self.futu_selection_verification.selection,
                    self.futu_selection_verification.contract_verifications,
                    self.futu_selection_verification.direct_entry_exact_contract_verification,
                    self.futu_selection_verification.maturity_context,
                )
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError("Futu selection verification is malformed") from error
            if rebuilt_verification != self.futu_selection_verification:
                raise ValueError("Futu selection verification is not intrinsically valid")
            if self.option_research_request is None or (
                self.futu_selection_verification.maturity_context.discovery_request
                is not self.option_research_request
            ):
                raise ValueError("Futu verification must retain exact maturity request")

        if self.entry_origin is ResearchCaseEntryOrigin.DIRECT_ENTRY:
            if type(self.direct_contract_references) is not tuple:
                raise TypeError("direct_contract_references must have exact type tuple")
            if any(
                type(reference) is not _OptionContractReference
                for reference in self.direct_contract_references
            ):
                raise TypeError("direct contract references have wrong exact type")
            if self.direct_entry_exact_contract_verification is not None:
                _require_exact(
                    "direct_entry_exact_contract_verification",
                    self.direct_entry_exact_contract_verification,
                    _direct_verification.DirectEntryExactContractVerification,
                )
                verification = self.direct_entry_exact_contract_verification
                if verification.structure is not self.original_input:
                    raise ValueError("Direct Entry verification must retain exact structure")
                if verification.contract_references is not self.direct_contract_references:
                    raise ValueError("Direct Entry verification must retain exact references")
        elif self.direct_contract_references is not None:
            raise ValueError("only Direct Entry can retain direct contract references")

        if self.downstream_result is not None:
            _require_exact(
                "downstream_result",
                self.downstream_result,
                _reviewed_service.DirectEntryReviewedResearchServiceResult,
            )
            current_verification = self.exact_contract_verification
            if current_verification is None:
                raise ValueError("downstream result requires exact verification")
            if (
                self.downstream_result.exact_contract_verification.structure
                is not current_verification.structure
            ):
                raise ValueError("downstream result must retain exact verified structure")
            if self.futu_selection_verification is not None and (
                self.downstream_result.maturity_context
                is not self.futu_selection_verification.maturity_context
            ):
                raise ValueError("downstream result must retain maturity context")
            if self.direct_entry_exact_contract_verification is not None and (
                self.downstream_result.maturity_context is not None
            ):
                raise ValueError("Direct Entry downstream result cannot retain maturity context")

        if self.stage is ResearchCaseStage.COMPLETED and self.downstream_result is None:
            raise ValueError("terminal research stage requires downstream result")
        if self.stage is ResearchCaseStage.AWAITING_STRUCTURE_SELECTION and (
            self.discrimination is None
        ):
            raise ValueError("awaiting structure selection requires discrimination")
        if self.stage is ResearchCaseStage.STOPPED_NONE and self.downstream_result is not None:
            raise ValueError("NONE case cannot retain downstream research")

        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "blocking_reasons", blocking_reasons)

    @property
    def event_grounding(self) -> object:
        """Return retained preparation/translation evidence, if applicable."""

        if self.event_entry_preparation is not None:
            return self.event_entry_preparation
        return self.discovery_translation

    @property
    def browser_evidence(self) -> object:
        """Return the retained neutral Browser sidecar."""

        return self.browser

    @property
    def discrimination_result(self) -> object:
        """Return the retained probability-free comparison sidecar."""

        return self.discrimination

    @property
    def exact_contract_verification(self) -> object:
        """Return the existing provider-neutral exact verification proof."""

        if self.futu_selection_verification is not None:
            return self.futu_selection_verification.direct_entry_exact_contract_verification
        return self.direct_entry_exact_contract_verification

    @property
    def maturity_context(self) -> object:
        """Return the retained maturity context without copying its fields."""

        if self.futu_selection_verification is not None:
            return self.futu_selection_verification.maturity_context
        if self.downstream_result is not None:
            return self.downstream_result.maturity_context
        return None

    @property
    def assembly_result(self) -> object:
        """Return the existing assembly result after research has run."""

        if self.downstream_result is None:
            return None
        return self.downstream_result.offline_service_result.assembly_result

    @property
    def candidate_record(self) -> object:
        """Return the existing CandidateResearchRecord, if assembled."""

        assembly = self.assembly_result
        if assembly is None:
            return None
        return assembly.record

    @property
    def screening_decision(self) -> object:
        """Return the existing independent ScreeningDecision, if available."""

        if self.downstream_result is None:
            return None
        return self.downstream_result.offline_service_result.screening_decision

    @property
    def position_management_plan(self) -> object:
        """Return the existing optional plan result, if available."""

        if self.downstream_result is None:
            return None
        return (
            self.downstream_result.offline_service_result
            .position_management_plan_result
        )

    @property
    def report_markdown(self) -> object:
        """Return the existing Chinese downstream report, if available."""

        if self.downstream_result is None:
            return None
        return self.downstream_result.offline_service_result.report_markdown

    @property
    def retained_lineage(self) -> _Tuple[object, ...]:
        """Return retained sidecars in composition order, without duplication."""

        values = [self.original_input]
        values.extend(
            value
            for value in (
                self.discovery_selection,
                self.discovery_translation,
                self.event_entry_preparation,
                self.event_entry_selection,
                self.event_entry_translation,
                self.event_entry_context,
                self.event_intelligence_assessment,
                self.option_research_request,
                self.browser,
                self.discrimination,
                self.exact_structure_selection,
                self.futu_selection_verification,
                self.direct_entry_exact_contract_verification,
                self.downstream_result,
            )
            if value is not None
        )
        return tuple(values)


def start_autonomous_discovery_case(
    case_id: str,
    batch: _EventCandidateBatch,
) -> ResearchCase:
    """Start at the explicit Event Discovery candidate checkpoint."""

    _require_exact("batch", batch, _EventCandidateBatch)
    return ResearchCase(
        case_id,
        ResearchCaseEntryOrigin.AUTONOMOUS_DISCOVERY,
        batch,
        ResearchCaseStage.DISCOVERY_SELECTION,
        blocking_reasons=("awaiting_human_discovery_selection",),
    )


def continue_autonomous_discovery_case(
    case: ResearchCase,
    *,
    candidate_id: _Optional[str],
    submission: object = None,
    supplemental_sources: _Tuple[object, ...] = (),
) -> ResearchCase:
    """Record candidate selection and optionally attach explicit EI input.

    A selected candidate still does not auto-select an Event Intelligence
    hypothesis.  With no submission, the returned case waits for
    ``attach_discovery_submission`` and performs no EI work.
    ``None`` is an explicit human NONE and stops before assessment.
    """

    case = _require_case(case)
    if case.entry_origin is not ResearchCaseEntryOrigin.AUTONOMOUS_DISCOVERY:
        raise ValueError("case is not an autonomous discovery case")
    if case.stage is not ResearchCaseStage.DISCOVERY_SELECTION:
        raise ValueError("case is not awaiting discovery selection")
    selection = _event_discovery.select_event_candidate(
        case.original_input,
        candidate_id=candidate_id,
    )
    if selection.selected_candidate is None:
        return _replace(
            case,
            discovery_selection=selection,
            stage=ResearchCaseStage.STOPPED_NONE,
            blocking_reasons=("human_selected_none",),
        )
    selected_case = _replace(
        case,
        discovery_selection=selection,
        stage=ResearchCaseStage.EVENT_INTELLIGENCE,
        blocking_reasons=("awaiting_event_intelligence_submission",),
    )
    if submission is None:
        return selected_case
    return attach_discovery_submission(
        selected_case,
        submission=submission,
        supplemental_sources=supplemental_sources,
    )


def attach_discovery_submission(
    case: ResearchCase,
    *,
    submission: object,
    supplemental_sources: _Tuple[object, ...] = (),
) -> ResearchCase:
    """Translate and assess an explicitly supplied Discovery EI submission."""

    case = _require_case(case)
    if case.entry_origin is not ResearchCaseEntryOrigin.AUTONOMOUS_DISCOVERY:
        raise ValueError("case is not an autonomous discovery case")
    if case.stage is not ResearchCaseStage.EVENT_INTELLIGENCE:
        raise ValueError("case is not awaiting discovery EI submission")
    if case.discovery_selection is None or (
        case.discovery_selection.selected_candidate is None
    ):
        raise ValueError("discovery EI submission requires a selected candidate")
    if case.discovery_translation is not None or case.event_intelligence_assessment is not None:
        raise ValueError("discovery EI submission is already attached")
    translation = _event_discovery.translate_event_candidate_selection(
        case.discovery_selection,
        submission=submission,
        supplemental_sources=supplemental_sources,
    )
    assessment = _event_intelligence.assess_event_intelligence_submission(
        translation.submission
    )
    return _replace(
        case,
        discovery_translation=translation,
        event_intelligence_assessment=assessment,
        stage=ResearchCaseStage.EVENT_INTELLIGENCE,
        blocking_reasons=_assessment_blockers(assessment),
    )


def select_discovery_hypothesis(
    case: ResearchCase,
    *,
    hypothesis_id: _Optional[str],
    evaluation_date: _datetime.date,
    maturity_authority: _OptionMaturityAuthority = (
        _OptionMaturityAuthority.HYPOTHESIS_ALIGNED
    ),
) -> ResearchCase:
    """Make the autonomous path's explicit hypothesis/NONE checkpoint."""

    case = _require_case(case)
    if case.entry_origin is not ResearchCaseEntryOrigin.AUTONOMOUS_DISCOVERY:
        raise ValueError("case is not an autonomous discovery case")
    if case.stage is not ResearchCaseStage.EVENT_INTELLIGENCE:
        raise ValueError("case is not awaiting discovery hypothesis selection")
    if case.event_intelligence_assessment is None or case.discovery_translation is None:
        raise ValueError("discovery hypothesis selection requires an EI assessment")
    if hypothesis_id is None:
        return _replace(
            case,
            selected_hypothesis=None,
            option_research_request=None,
            stage=ResearchCaseStage.STOPPED_NONE,
            blocking_reasons=("human_selected_none",),
        )
    if case.event_intelligence_assessment.status is not _AcceptanceStatus.ACCEPTED:
        raise ValueError("event intelligence must be accepted before hypothesis selection")
    if type(hypothesis_id) is not str or not hypothesis_id.strip():
        raise ValueError("hypothesis_id must be a nonempty string or None")
    selected = next(
        (
            hypothesis
            for hypothesis in case.event_intelligence_assessment.submission.hypotheses
            if hypothesis.hypothesis_id == hypothesis_id.strip()
        ),
        None,
    )
    if selected is None:
        raise ValueError("hypothesis_id must identify a submitted hypothesis")
    handoff = _discovery_entry.create_discovery_entry_handoff(
        case.event_intelligence_assessment,
        selected,
    )
    request = _option_chain_discovery.create_option_chain_discovery_request(
        handoff,
        evaluation_date=evaluation_date,
        maturity_authority=maturity_authority,
    )
    return _replace(
        case,
        selected_hypothesis=selected,
        option_research_request=request,
        stage=ResearchCaseStage.OPTION_DISCOVERY,
        blocking_reasons=("awaiting_browser_evidence",),
    )


def start_event_entry_case(
    case_id: str,
    preparation: _Union[_UserEventInput, _EventEntryPreparation],
) -> ResearchCase:
    """Start from raw Event Entry input or caller-prepared grounding."""

    if type(preparation) is _UserEventInput:
        return ResearchCase(
            case_id,
            ResearchCaseEntryOrigin.EVENT_ENTRY,
            preparation,
            ResearchCaseStage.EVENT_PREPARATION,
            blocking_reasons=("awaiting_event_grounding_preparation",),
        )

    _require_exact("preparation", preparation, _EventEntryPreparation)
    return ResearchCase(
        case_id,
        ResearchCaseEntryOrigin.EVENT_ENTRY,
        preparation.user_input,
        ResearchCaseStage.EVENT_PREPARATION,
        event_entry_preparation=preparation,
        blocking_reasons=("awaiting_human_hypothesis_selection",),
    )


def attach_event_entry_preparation(
    case: ResearchCase,
    preparation: _EventEntryPreparation,
) -> ResearchCase:
    """Attach caller-prepared grounding to a raw Event Entry case."""

    case = _require_case(case)
    _require_exact("preparation", preparation, _EventEntryPreparation)
    if case.entry_origin is not ResearchCaseEntryOrigin.EVENT_ENTRY:
        raise ValueError("case is not an Event Entry case")
    if case.stage is not ResearchCaseStage.EVENT_PREPARATION:
        raise ValueError("case is not awaiting Event Entry preparation")
    if case.event_entry_preparation is not None:
        raise ValueError("Event Entry preparation is already attached")
    if preparation.user_input is not case.original_input:
        raise ValueError("Event Entry preparation must retain the raw user input")
    return _replace(
        case,
        event_entry_preparation=preparation,
        blocking_reasons=("awaiting_human_hypothesis_selection",),
    )


def continue_event_entry_case(
    case: ResearchCase,
    *,
    hypothesis_id: _Optional[str],
    submission_id: object = None,
    event_id: object = None,
    observed_at: object = None,
    event_description: object = None,
    event_date_range: object = None,
    evaluation_date: object = None,
    maturity_authority: _OptionMaturityAuthority = (
        _OptionMaturityAuthority.HYPOTHESIS_ALIGNED
    ),
) -> ResearchCase:
    """Apply the Event Entry human hypothesis/NONE checkpoint then existing EI."""

    case = _require_case(case)
    if case.entry_origin is not ResearchCaseEntryOrigin.EVENT_ENTRY:
        raise ValueError("case is not an Event Entry case")
    if case.stage is not ResearchCaseStage.EVENT_PREPARATION:
        raise ValueError("case is not awaiting Event Entry hypothesis selection")
    preparation = case.event_entry_preparation
    if preparation is None:
        raise ValueError("Event Entry preparation is missing")
    selection = _event_entry_preparation.select_event_entry_hypothesis(
        preparation,
        hypothesis_id=hypothesis_id,
    )
    if selection.hypothesis is None:
        return _replace(
            case,
            event_entry_selection=selection,
            stage=ResearchCaseStage.STOPPED_NONE,
            blocking_reasons=("human_selected_none",),
        )
    if evaluation_date is None:
        raise TypeError("evaluation_date is required for a selected hypothesis")
    translation = _event_entry_preparation.translate_event_entry_selection(
        selection,
        submission_id=submission_id,
        event_id=event_id,
        observed_at=observed_at,
        event_description=event_description,
        event_date_range=event_date_range,
    )
    context = translation.prepare_research(
        evaluation_date=evaluation_date,
        maturity_authority=maturity_authority,
    )
    assessment = context.assessment
    if assessment is None:
        blockers = context.blocking_reasons or ("event_intelligence_not_accepted",)
        stage = ResearchCaseStage.EVENT_INTELLIGENCE
        request = None
    elif context.option_request is None:
        blockers = context.blocking_reasons or _assessment_blockers(assessment)
        stage = ResearchCaseStage.EVENT_INTELLIGENCE
        request = None
    else:
        blockers = ("awaiting_browser_evidence",)
        stage = ResearchCaseStage.OPTION_DISCOVERY
        request = context.option_request
    return _replace(
        case,
        event_entry_selection=selection,
        event_entry_translation=translation,
        event_entry_context=context,
        event_intelligence_assessment=assessment,
        selected_hypothesis=selection.hypothesis,
        option_research_request=request,
        stage=stage,
        blocking_reasons=blockers,
    )


def start_direct_entry_case(
    case_id: str,
    structure: _OptionStructure,
    contract_references: _Tuple[_OptionContractReference, ...],
) -> ResearchCase:
    """Start from a user-supplied exact structure and its source references."""

    _require_exact("structure", structure, _OptionStructure)
    if type(contract_references) is not tuple:
        raise TypeError("contract_references must have exact type tuple")
    if any(type(reference) is not _OptionContractReference for reference in contract_references):
        raise TypeError("every contract reference must have exact type OptionContractReference")
    return ResearchCase(
        case_id,
        ResearchCaseEntryOrigin.DIRECT_ENTRY,
        structure,
        ResearchCaseStage.EXACT_VERIFICATION,
        direct_contract_references=contract_references,
        blocking_reasons=("awaiting_exact_contract_verification",),
    )


def attach_browser_evidence(
    case: ResearchCase,
    browser: _futu.FutuExactContractBrowser,
) -> ResearchCase:
    """Attach an existing Browser without making a provider call."""

    case = _require_case(case)
    _require_exact("browser", browser, _futu.FutuExactContractBrowser)
    if case.entry_origin is ResearchCaseEntryOrigin.DIRECT_ENTRY:
        raise ValueError("Direct Entry has no Browser stage")
    if case.stage is not ResearchCaseStage.OPTION_DISCOVERY:
        raise ValueError("case is not awaiting Browser evidence")
    if case.option_research_request is None:
        raise ValueError("Browser attachment requires an option research request")
    if case.browser is not None:
        raise ValueError("Browser evidence is already attached")
    if browser.discovery_evidence.discovery_request is not case.option_research_request:
        raise ValueError("Browser must retain the exact option research request")
    try:
        rebuilt = _futu.FutuExactContractBrowser(browser.discovery_evidence)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("browser is malformed") from error
    if rebuilt != browser:
        raise ValueError("browser is not intrinsically valid")
    if not browser.rows:
        return _replace(
            case,
            browser=browser,
            stage=ResearchCaseStage.NO_OPTION_RESEARCH_SURFACE,
            blocking_reasons=("no_option_research_surface",),
        )
    return _replace(
        case,
        browser=browser,
        stage=ResearchCaseStage.AWAITING_RTH_EVIDENCE,
        blocking_reasons=("awaiting_rth_quote_and_reference_evidence",),
    )


def attach_discrimination_evidence(
    case: ResearchCase,
    result: _discrimination.ProbabilityFreeConvexityDiscriminationResult,
) -> ResearchCase:
    """Attach an offline discrimination result while retaining Browser identity."""

    case = _require_case(case)
    _require_exact(
        "result",
        result,
        _discrimination.ProbabilityFreeConvexityDiscriminationResult,
    )
    if case.browser is None:
        raise ValueError("discrimination attachment requires Browser evidence")
    if case.stage is not ResearchCaseStage.AWAITING_RTH_EVIDENCE:
        raise ValueError("case is not awaiting discrimination evidence")
    if result.browser is not case.browser:
        raise ValueError("discrimination must retain the exact Browser")
    try:
        rebuilt = _discrimination.ProbabilityFreeConvexityDiscriminationResult(
            result.browser,
            result.quote_batch,
            result.reference_price,
            result.comparisons,
            result.non_comparison_rows,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("discrimination result is malformed") from error
    if rebuilt != result:
        raise ValueError("discrimination result is not intrinsically valid")
    if not result.comparisons:
        return _replace(
            case,
            discrimination=result,
            stage=ResearchCaseStage.NO_OPTION_RESEARCH_SURFACE,
            blocking_reasons=("no_option_research_surface",),
        )
    return _replace(
        case,
        discrimination=result,
        stage=ResearchCaseStage.AWAITING_STRUCTURE_SELECTION,
        blocking_reasons=("awaiting_human_structure_selection",),
    )


def select_exact_structure(
    case: ResearchCase,
    *,
    provider_identifiers: _Optional[_Tuple[str, ...]],
    assumed_portfolio_value: object = None,
    expected_holding_days: object = None,
    quantity: object = 1,
) -> ResearchCase:
    """Record one explicit Browser structure choice or an explicit NONE."""

    case = _require_case(case)
    if case.entry_origin is ResearchCaseEntryOrigin.DIRECT_ENTRY:
        raise ValueError("Direct Entry already starts with an explicit structure")
    if case.stage is not ResearchCaseStage.AWAITING_STRUCTURE_SELECTION:
        raise ValueError("case is not awaiting exact structure selection")
    if case.browser is None or case.discrimination is None:
        raise ValueError("structure selection requires Browser discrimination")
    if provider_identifiers is None:
        return _replace(
            case,
            exact_structure_selection=None,
            futu_selection_verification=None,
            stage=ResearchCaseStage.STOPPED_NONE,
            blocking_reasons=("human_selected_none",),
        )
    selection = _futu.select_futu_exact_contracts(
        case.browser,
        provider_identifiers=provider_identifiers,
        assumed_portfolio_value=assumed_portfolio_value,
        expected_holding_days=expected_holding_days,
        quantity=quantity,
    )
    if not _selection_matches_discrimination(
        _replace(case, exact_structure_selection=selection)
    ):
        raise ValueError("exact structure selection must match a discrimination comparison")
    return _replace(
        case,
        exact_structure_selection=selection,
        stage=ResearchCaseStage.EXACT_VERIFICATION,
        blocking_reasons=("awaiting_exact_contract_verification",),
    )


def verify_exact_structure(
    case: ResearchCase,
    *,
    selection_verification: object = None,
) -> ResearchCase:
    """Run or attach the existing exact-contract verification boundary.

    Discovery/Event Entry accepts only an already-created typed Futu bridge
    result.  Provider acquisition, including a future authorized RTH call, is
    outside this application boundary.  Direct Entry invokes the existing
    provider-neutral verifier.  This function never creates a replacement
    contract or picks a structure.
    """

    case = _require_case(case)
    if case.stage is not ResearchCaseStage.EXACT_VERIFICATION:
        raise ValueError("case is not awaiting exact verification")
    if case.entry_origin is ResearchCaseEntryOrigin.DIRECT_ENTRY:
        if selection_verification is not None:
            raise ValueError("Direct Entry accepts its retained references directly")
        verification = _direct_verification.verify_direct_entry_exact_contracts(
            case.original_input,
            case.direct_contract_references,
        )
        return _replace(
            case,
            direct_entry_exact_contract_verification=verification,
            stage=ResearchCaseStage.ENGINE_RESEARCH,
            blocking_reasons=("awaiting_reviewed_research_inputs",),
        )
    if case.exact_structure_selection is None:
        raise ValueError("exact verification requires an explicit structure selection")
    _require_exact(
        "selection_verification",
        selection_verification,
        _futu.FutuExactContractSelectionVerification,
    )
    verification = selection_verification
    if verification.selection is not case.exact_structure_selection:
        raise ValueError("selection verification must retain exact selection")
    return _replace(
        case,
        futu_selection_verification=verification,
        stage=ResearchCaseStage.ENGINE_RESEARCH,
        blocking_reasons=("awaiting_reviewed_research_inputs",),
    )


def run_research_case(
    case: ResearchCase,
    research_input: ResearchCaseResearchInput,
) -> ResearchCase:
    """Call the one existing reviewed-research service for the retained proof."""

    case = _require_case(case)
    research_input = _require_research_input(research_input)
    if case.stage is not ResearchCaseStage.ENGINE_RESEARCH:
        raise ValueError("case is not ready for Engine research")
    if case.downstream_result is not None:
        raise ValueError("research has already run for this case")
    exact_verification = case.exact_contract_verification
    if exact_verification is None:
        raise ValueError("research requires exact contract verification")
    structure = exact_verification.structure
    maturity_context = case.maturity_context
    result = _reviewed_service.run_direct_entry_reviewed_research_service(
        research_input.calculation_id,
        research_input.candidate_id,
        research_input.state,
        research_input.state_rationale,
        research_input.as_of_date,
        research_input.hypothesis,
        structure,
        exact_verification.contract_references,
        research_input.volatility_environment_result,
        research_input.tail_pricing_result,
        research_input.structure_liquidity_result,
        research_input.structure_costs_result,
        research_input.scenario_valuation_result,
        research_input.expiration_payoff_threshold_result,
        research_input.structure_affordability_result,
        research_input.evidence,
        research_input.falsification_conditions,
        research_input.missing_data,
        research_input.false_positive_reasons,
        research_input.ai_interpretation,
        research_input.human_review_questions,
        research_input.calculated_at,
        research_input.screening_policy,
        research_input.position_management_plan_request,
        maturity_context=maturity_context,
    )
    # Execution completion is an application fact; DATA_INSUFFICIENT remains
    # the downstream ScreeningDecision and is rendered independently.
    stage = ResearchCaseStage.COMPLETED
    blockers = ()
    return _replace(
        case,
        downstream_result=result,
        stage=stage,
        blocking_reasons=blockers,
    )


def render_research_case_markdown(case: ResearchCase) -> str:
    """Render one coherent Chinese case summary and retained audit outputs."""

    case = _require_case(case)
    event_none = (
        case.entry_origin is ResearchCaseEntryOrigin.AUTONOMOUS_DISCOVERY
        and case.discovery_selection is not None
        and case.discovery_selection.selected_candidate is None
    ) or (
        case.entry_origin is ResearchCaseEntryOrigin.EVENT_ENTRY
        and case.event_entry_selection is not None
        and case.event_entry_selection.hypothesis is None
    )
    structure_none = (
        case.entry_origin is not ResearchCaseEntryOrigin.DIRECT_ENTRY
        and case.stage is ResearchCaseStage.STOPPED_NONE
        and case.browser is not None
        and case.discrimination is not None
        and case.exact_structure_selection is None
    )
    lines = [
        "# 研究案例",
        "",
        f"- 案例 ID：{case.case_id}",
        f"- 入口：{case.entry_origin.value}",
        f"- 当前阶段：{case.stage.value}",
    ]
    if case.entry_origin is not ResearchCaseEntryOrigin.DIRECT_ENTRY:
        if case.event_intelligence_assessment is not None:
            assessment = case.event_intelligence_assessment
            lines.append(f"- EI：{assessment.status.value}")
            if assessment.issues:
                lines.append(
                    "- EI 缺失原因："
                    + ", ".join(issue.code.value for issue in assessment.issues)
                )
        if case.selected_hypothesis is not None:
            lines.append(
                f"- 已选事件假设：{case.selected_hypothesis.hypothesis_id}"
            )
        elif event_none:
            lines.append("- 人工事件选择：NONE")
        elif (
            case.entry_origin is ResearchCaseEntryOrigin.AUTONOMOUS_DISCOVERY
            and case.stage is ResearchCaseStage.STOPPED_NONE
            and case.discovery_translation is not None
            and case.selected_hypothesis is None
        ):
            lines.append("- 人工事件假设选择：NONE")
    if case.option_research_request is not None:
        request = case.option_research_request
        lines.append(
            "- 到期日 authority："
            f"{request.maturity_authority.value}；"
            f"maturity alignment：{request.hypothesis_maturity_alignment.value}"
        )
    elif case.maturity_context is not None:
        context = case.maturity_context
        lines.append(
            "- 到期日 authority："
            f"{context.maturity_authority.value}；"
            f"maturity alignment：{context.hypothesis_maturity_alignment.value}"
        )
    if case.exact_structure_selection is not None:
        lines.append(
            "- 精确结构选择："
            + ", ".join(
                row.provider_identifier
                for row in case.exact_structure_selection.selected_contracts
            )
        )
    elif case.entry_origin is ResearchCaseEntryOrigin.DIRECT_ENTRY:
        lines.append("- 精确结构选择：用户直接输入")
    elif structure_none:
        lines.append("- 人工结构选择：NONE")
    if case.stage is ResearchCaseStage.NO_OPTION_RESEARCH_SURFACE:
        lines.append("- 选项研究面：不存在")
    if case.exact_contract_verification is not None:
        lines.append("- 精确合约验证：已保留现有验证证明")
    if case.blocking_reasons:
        lines.append("- 阻塞原因：" + ", ".join(case.blocking_reasons))
    lines.extend(
        [
            "",
            "本案例只保留现有领域对象和审计 sidecar；不复制经济数值，"
            "不自动选择结构，也不把条件式几何比较解释为概率、便宜程度或建议。",
            "",
            "## 保留的审计对象",
            "",
            "、".join(type(value).__name__ for value in case.retained_lineage),
        ]
    )
    if case.discrimination is not None:
        lines.extend(
            [
                "",
                "## 条件式凸性比较",
                "",
                _presentation.render_convexity_comparison_markdown(
                    case.discrimination
                ),
            ]
        )
    if case.downstream_result is not None:
        lines.extend(
            [
                "",
                "## 下游中文研究报告",
                "",
                case.downstream_result.offline_service_result.report_markdown,
            ]
        )
        decision = case.downstream_result.offline_service_result.screening_decision
        lines.extend(
            [
                "",
                "## ScreeningDecision",
                "",
                f"proposed_state = {decision.proposed_state.value}",
                "reason_codes = "
                + ", ".join(reason.value for reason in decision.reason_codes),
            ]
        )
    return "\n".join(lines)
