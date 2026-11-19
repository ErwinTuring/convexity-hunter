"""Explicit adapter from a prepared Event batch to the existing Core path."""

import datetime as _datetime
from dataclasses import replace as _replace
from typing import Callable as _Callable

from .core_application import (
    CoreOperationalBounds,
    CoreRunResult,
    SourceSubmissionBatch,
    run_event_core,
)
from .event_entry import UserEventInput
from .host_profile import (
    APPROVED_STANDARD_RESEARCH_PROFILE,
    create_core_research_policy,
)
from .option_chain_discovery import (
    OptionMaturityAuthority,
    validate_exploration_lead,
)


__all__ = ("create_event_core_executor",)


def create_event_core_executor(
    *,
    evaluation_date: _datetime.date,
    maturity_authority: OptionMaturityAuthority,
    market_bridge: object,
    exploration_enabled: bool = False,
) -> _Callable[..., CoreRunResult]:
    """Bind explicit Event Core authorities without acquiring source evidence."""

    if type(evaluation_date) is not _datetime.date:
        raise TypeError("evaluation_date must have exact type date")
    if type(maturity_authority) is not OptionMaturityAuthority:
        raise TypeError("maturity_authority must be OptionMaturityAuthority")
    if type(exploration_enabled) is not bool:
        raise TypeError("exploration_enabled must be a Boolean")

    def execute_event_core(
        raw_input: str,
        *,
        bounds: CoreOperationalBounds,
        source_batch: SourceSubmissionBatch,
    ) -> CoreRunResult:
        if type(raw_input) is not str:
            raise TypeError("raw_input must be a string")
        if not raw_input.strip():
            raise ValueError("raw_input must not be blank")
        if type(bounds) is not CoreOperationalBounds:
            raise TypeError("bounds must be CoreOperationalBounds")
        if type(source_batch) is not SourceSubmissionBatch:
            raise TypeError("source_batch must be SourceSubmissionBatch")

        user_input = source_batch.raw_input
        if type(user_input) is not UserEventInput:
            raise TypeError("source_batch.raw_input must be UserEventInput")
        if (
            type(user_input.description) is not str
            or not user_input.description.strip()
        ):
            raise ValueError("source_batch.raw_input must retain a valid description")
        if user_input.description != raw_input:
            raise ValueError("source_batch description must match raw_input")

        submissions = source_batch.submissions
        if type(submissions) is not tuple:
            raise TypeError("source_batch.submissions must be a tuple")
        leads = source_batch.exploration_leads
        if type(leads) is not tuple:
            raise TypeError("source_batch.exploration_leads must be a tuple")
        if leads and not exploration_enabled:
            raise ValueError("exploration is disabled for this Event executor")
        if not submissions and not (exploration_enabled and leads):
            raise ValueError("source_batch must contain at least one submission")
        SourceSubmissionBatch(user_input, submissions, leads).__post_init__()
        for lead in leads:
            validate_exploration_lead(lead)

        def grounder(candidate: UserEventInput) -> SourceSubmissionBatch:
            if candidate is not user_input:
                raise ValueError("grounder input must retain the batch UserEventInput")
            return source_batch

        policy = create_core_research_policy(
            profile=APPROVED_STANDARD_RESEARCH_PROFILE,
            evaluation_date=evaluation_date,
            maturity_authority=maturity_authority,
            bounds=bounds,
        )
        if exploration_enabled:
            policy = _replace(policy, exploration_enabled=True)
        return run_event_core(
            user_input,
            grounder=grounder,
            market_bridge=market_bridge,
            policy=policy,
        )

    return execute_event_core
