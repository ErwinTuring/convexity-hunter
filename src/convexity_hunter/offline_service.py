"""Deterministic offline orchestration for one reviewed candidate structure."""

import datetime
from dataclasses import dataclass
from typing import Optional, Tuple, Union

from .candidate_assembly import CandidateResearchRecordAssemblyResult
from .position_management import (
    PositionManagementPlanResult,
    QualitativePositionManagementCondition,
    QuantitativePositionManagementCondition,
    create_position_management_plan,
)
from .report import render_candidate_markdown
from .scanner import ScreeningDecision, ScreeningPolicy, screen_candidate


__all__ = (
    "PositionManagementPlanRequest",
    "OfflineSingleStructureServiceResult",
    "run_offline_single_structure_service",
)


@dataclass(frozen=True)
class PositionManagementPlanRequest:
    calculation_id: str
    conditions: Tuple[
        Union[
            QuantitativePositionManagementCondition,
            QualitativePositionManagementCondition,
        ],
        ...,
    ]
    calculated_at: datetime.datetime


@dataclass(frozen=True)
class OfflineSingleStructureServiceResult:
    assembly_result: CandidateResearchRecordAssemblyResult
    screening_decision: ScreeningDecision
    position_management_plan_result: Optional[PositionManagementPlanResult]
    report_markdown: str


def run_offline_single_structure_service(
    assembly_result: CandidateResearchRecordAssemblyResult,
    screening_policy: ScreeningPolicy,
    position_management_plan_request: Optional[PositionManagementPlanRequest] = None,
) -> OfflineSingleStructureServiceResult:
    if type(assembly_result) is not CandidateResearchRecordAssemblyResult:
        raise TypeError(
            "assembly_result must have exact type CandidateResearchRecordAssemblyResult"
        )
    if type(screening_policy) is not ScreeningPolicy:
        raise TypeError("screening_policy must have exact type ScreeningPolicy")
    if (
        position_management_plan_request is not None
        and type(position_management_plan_request) is not PositionManagementPlanRequest
    ):
        raise TypeError(
            "position_management_plan_request must have exact type "
            "PositionManagementPlanRequest or be None"
        )

    screening_decision = screen_candidate(
        assembly_result.record,
        screening_policy,
    )

    position_management_plan_result = None
    if position_management_plan_request is not None:
        position_management_plan_result = create_position_management_plan(
            position_management_plan_request.calculation_id,
            assembly_result,
            position_management_plan_request.conditions,
            position_management_plan_request.calculated_at,
        )

    report_markdown = render_candidate_markdown(
        assembly_result.record,
        locale="zh-CN",
        screening_decision=screening_decision,
        position_management_plan_result=position_management_plan_result,
    )
    return OfflineSingleStructureServiceResult(
        assembly_result,
        screening_decision,
        position_management_plan_result,
        report_markdown,
    )
