"""Deterministic direct-entry reviewed-research service orchestration."""

from dataclasses import dataclass as _dataclass
from typing import Optional as _Optional

from .candidate_assembly import (
    assemble_candidate_research_record as _assemble_candidate_research_record,
)
from .direct_entry_verification import (
    DirectEntryExactContractVerification as _DirectEntryExactContractVerification,
    DirectEntryResearchReadinessVerification as _DirectEntryResearchReadinessVerification,
    verify_direct_entry_exact_contracts as _verify_direct_entry_exact_contracts,
    verify_direct_entry_research_readiness as _verify_direct_entry_research_readiness,
)
from .offline_service import (
    OfflineSingleStructureServiceResult as _OfflineSingleStructureServiceResult,
    PositionManagementPlanRequest as _PositionManagementPlanRequest,
    run_offline_single_structure_service as _run_offline_single_structure_service,
)
from .option_chain_discovery import (
    OptionResearchMaturityContext as _OptionResearchMaturityContext,
)
from .option_chain_discovery import (
    _validate_option_research_maturity_context as _validate_option_research_maturity_context,
)
from .scanner import ScreeningPolicy as _ScreeningPolicy


__all__ = (
    "DirectEntryReviewedResearchServiceResult",
    "run_direct_entry_reviewed_research_service",
)


@_dataclass(frozen=True)
class DirectEntryReviewedResearchServiceResult:
    exact_contract_verification: _DirectEntryExactContractVerification
    research_readiness_verification: _Optional[
        _DirectEntryResearchReadinessVerification
    ]
    offline_service_result: _OfflineSingleStructureServiceResult
    maturity_context: _Optional[_OptionResearchMaturityContext]


def run_direct_entry_reviewed_research_service(
    calculation_id: object,
    candidate_id: object,
    state: object,
    state_rationale: object,
    as_of_date: object,
    hypothesis: object,
    structure: object,
    contract_references: object,
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
    *,
    maturity_context: _Optional[_OptionResearchMaturityContext],
) -> DirectEntryReviewedResearchServiceResult:
    if maturity_context is not None:
        _validate_option_research_maturity_context(maturity_context)
        if maturity_context.structure is not structure:
            raise ValueError("maturity_context_structure_mismatch")
    exact_contract_verification = _verify_direct_entry_exact_contracts(
        structure,
        contract_references,
    )
    research_readiness_verification = None
    if (
        structure_costs_result is not None
        and structure_liquidity_result is not None
    ):
        research_readiness_verification = (
            _verify_direct_entry_research_readiness(
                exact_contract_verification.structure,
                structure_costs_result,
                structure_liquidity_result,
            )
        )
    assembly_result = _assemble_candidate_research_record(
        calculation_id,
        candidate_id,
        state,
        state_rationale,
        as_of_date,
        hypothesis,
        exact_contract_verification.structure,
        volatility_environment_result,
        tail_pricing_result,
        structure_liquidity_result,
        structure_costs_result,
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
        maturity_context=maturity_context,
    )
    return DirectEntryReviewedResearchServiceResult(
        exact_contract_verification,
        research_readiness_verification,
        offline_service_result,
        maturity_context,
    )
