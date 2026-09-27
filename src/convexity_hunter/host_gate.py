"""Pre-Core validation of a prepared batch; no semantic assessment or I/O."""

from dataclasses import dataclass, replace
from typing import Optional, Tuple

from .core_application import (
    CoreResearchPolicy, CoreRunResult, SourceSubmissionBatch,
    run_event_core, run_world_core,
)
from .event_entry import UserEventInput
from .event_intelligence import EventIntelligenceSubmission


@dataclass(frozen=True)
class GateResult:
    """Retain original objects, including invalid inputs, for diagnostics."""

    raw_input: object
    batch: object
    allowed: bool
    reason_codes: Tuple[str, ...]


def validate_source_batch(raw_input: object, batch: object) -> GateResult:
    """Check intrinsic validity only; INCOMPLETE is the Core's decision.

    Reconstructed records are validation probes and are never forwarded.
    The original batch, submissions, hypotheses and their order are retained.
    """
    def blocked(reason: str) -> GateResult:
        return GateResult(raw_input, batch, False, ("BLOCKED", reason))

    if type(batch) is not SourceSubmissionBatch:
        return blocked("INVALID_BATCH_TYPE")
    try:
        if batch.raw_input is not raw_input:
            return blocked("RAW_INPUT_IDENTITY_MISMATCH")
        # Reuse the batch constructor for tuple/exact-type/source/ID checks.
        SourceSubmissionBatch(batch.raw_input, batch.submissions)
        if not batch.submissions:
            return blocked("EMPTY_BATCH")
        for submission in batch.submissions:
            if type(submission) is not EventIntelligenceSubmission:
                return blocked("INVALID_BATCH")
            # Existing constructors recursively validate nested records and
            # reject forged/dangling records without assessing completeness.
            if replace(submission) != submission:
                return blocked("INVALID_BATCH")
    except (AttributeError, TypeError, ValueError):
        return blocked("INVALID_BATCH")
    return GateResult(raw_input, batch, True, ())


def run_event_core_gated(
    user_input: object, *, batch: object, market_bridge: object,
    policy: CoreResearchPolicy,
) -> Tuple[GateResult, Optional[CoreRunResult]]:
    """Return (gate, None) when blocked, otherwise the untouched Core result.

    The caller supplies an already prepared batch; no grounder is rerun.
    """
    try:
        if type(user_input) is not UserEventInput:
            raise TypeError
        UserEventInput.__post_init__(user_input)
    except (AttributeError, TypeError, ValueError):
        return GateResult(
            user_input, batch, False, ("BLOCKED", "INVALID_EVENT_INPUT")
        ), None
    gate = validate_source_batch(user_input, batch)
    if not gate.allowed:
        return gate, None
    return gate, run_event_core(
        user_input, grounder=lambda _input: batch,
        market_bridge=market_bridge, policy=policy,
    )


def run_world_core_gated(
    raw_request: object, *, batch: object, market_bridge: object,
    policy: CoreResearchPolicy,
) -> Tuple[GateResult, Optional[CoreRunResult]]:
    """World input is opaque, matching run_world_core's existing contract."""
    gate = validate_source_batch(raw_request, batch)
    if not gate.allowed:
        return gate, None
    return gate, run_world_core(
        raw_request, source_producer=lambda _input: batch,
        market_bridge=market_bridge, policy=policy,
    )
