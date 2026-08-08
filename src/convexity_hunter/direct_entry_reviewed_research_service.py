"""Deterministic direct-entry reviewed-research service orchestration."""

from dataclasses import dataclass as _dataclass
from typing import Optional as _Optional

from .candidate_assembly import (
    assemble_candidate_research_record as _assemble_candidate_research_record,
)
from .direct_entry_verification import (
    DirectEntryExactStructureVerification as _DirectEntryExactStructureVerification,
    verify_direct_entry_exact_structure as _verify_direct_entry_exact_structure,
)
from .offline_service import (
    OfflineSingleStructureServiceResult as _OfflineSingleStructureServiceResult,
    PositionManagementPlanRequest as _PositionManagementPlanRequest,
    run_offline_single_structure_service as _run_offline_single_structure_service,
)
from .scanner import ScreeningPolicy as _ScreeningPolicy


__all__ = (
    "DirectEntryReviewedResearchServiceResult",
    "run_direct_entry_reviewed_research_service",
)


@_dataclass(frozen=True)
class DirectEntryReviewedResearchServiceResult:
    direct_entry_verification: _DirectEntryExactStructureVerification
    offline_service_result: _OfflineSingleStructureServiceResult


def run_direct_entry_reviewed_research_service(
    calculation_id: object,
    candidate_id: object,
    state: object,
    state_rationale: object,
    as_of_date: object,
    hypothesis: object,
    structure: object,
    volatility_environment_result: object,
    tail_pricing_result: object,
    structure_liquidity_result: object,
    structure_costs_result: object,
    scenario_valuation_result: object,
    expiration_payoff_threshold_result: object,
    structure_affordability_result: object,
    evidence: object,
    falsification_conditions: object,
    missing_data: object,
    false_positive_reasons: object,
    ai_interpretation: object,
    human_review_questions: object,
    calculated_at: object,
    screening_policy: _ScreeningPolicy,
    position_management_plan_request: _Optional[_PositionManagementPlanRequest] = None,
) -> DirectEntryReviewedResearchServiceResult:
    direct_entry_verification = _verify_direct_entry_exact_structure(
        structure,
        structure_costs_result,
        structure_liquidity_result,
    )
    assembly_result = _assemble_candidate_research_record(
        calculation_id,
        candidate_id,
        state,
        state_rationale,
        as_of_date,
        hypothesis,
        direct_entry_verification.structure,
        volatility_environment_result,
        tail_pricing_result,
        direct_entry_verification.liquidity_result,
        direct_entry_verification.costs_result,
        scenario_valuation_result,
        expiration_payoff_threshold_result,
        structure_affordability_result,
        evidence,
        falsification_conditions,
        missing_data,
        false_positive_reasons,
        ai_interpretation,
        human_review_questions,
        calculated_at,
    )
    offline_service_result = _run_offline_single_structure_service(
        assembly_result,
        screening_policy,
        position_management_plan_request,
    )
    return DirectEntryReviewedResearchServiceResult(
        direct_entry_verification,
        offline_service_result,
    )
