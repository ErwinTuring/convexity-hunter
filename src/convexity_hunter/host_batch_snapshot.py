"""Closed, immutable World/Event batch snapshots and normalized EI audit data.

This module projects existing application and Core records.  It does not
construct a CoreCaseContext on reads or add an EI acceptance authority.
"""

from __future__ import annotations

import datetime
import hashlib
import re
from decimal import Decimal
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from .core_application import (
    CoreCaseRecord,
    CoreCaseSet,
    CoreRunResult,
    CoreUnavailableCase,
    SourceSubmissionBatch,
)
from .core_presentation import CoreCompactCase, CoreCompactLeg, CoreCompactSummary, compact_summary
from .core_research import CoreDisposition, CoreResearchResult
from .event_entry import UserEventInput
from .event_intelligence import (
    DistributionChangeMode,
    EventIntelligenceAcceptanceResult,
    EventIntelligenceAcceptanceStatus,
    EventIntelligenceSubmission,
    EventStatementKind,
    EventUnderlyingHypothesis,
    HypothesisReassessment,
    MethodologizedDateRange,
    ReassessmentBasisKind,
    assess_event_intelligence_submission,
)
from .host_core_snapshot import decode_core_result, encode_core_result
from .host_profile import STANDARD_RESEARCH_PROFILE
from .market_data import UnderlyingSecurityType
from .option_chain_discovery import HypothesisMaturityAlignment, OptionMaturityAuthority


SCHEMA_VERSION = "host-batch-snapshot-v0.1"
OUTCOME_SCHEMA_VERSION = "host-batch-outcome-v0.1"
AUDIT_SCHEMA_VERSION = "host-ei-batch-audit-v0.1"
_CASE_KEY_RE = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_LIMIT_REASON_RE = re.compile(
    r"(submissions|hypotheses|browser_rows|cases):([1-9][0-9]*)>(0|[1-9][0-9]*)\Z",
    re.ASCII,
)
_SUMMARY_FIELDS = frozenset(
    (
        "entry_origin",
        "case_count",
        "unavailable_count",
        "disposition_counts",
        "case_ids",
        "reasons",
        "case_summaries",
        "unavailable_case_ids",
        "unavailable_cases",
        "host_status",
    )
)
_CASE_SUMMARY_FIELDS = frozenset(
    (
        "case_id",
        "case_key",
        "disposition",
        "geometry_status",
        "ask_basis_per_underlying_unit",
        "reasons",
        "structure_kind",
        "legs",
        "budget_status",
        "single_cost_upper_bound",
        "repeated_cost_upper_bound",
        "single_loss_fraction",
        "repeated_loss_fraction",
    )
)
_LEG_FIELDS = frozenset(
    (
        "leg_id",
        "underlying",
        "option_type",
        "expiration",
        "strike",
        "quantity",
        "contract_multiplier",
    )
)
_UNAVAILABLE_FIELDS = frozenset(
    ("case_id", "case_key", "classification", "reasons", "lineage")
)
_BATCH_CASE_FIELDS = frozenset(
    (
        "case_id",
        "case_key",
        "classification",
        "reasons",
        "application_reasons",
        "lineage",
        "disclosures",
        "core_snapshot",
        "core_sha256",
    )
)
_LINEAGE_FIELDS = frozenset(("submission_id", "hypothesis_id"))
_DISCLOSURE_FIELDS = frozenset(
    (
        "maturity_authority",
        "hypothesis_maturity_alignment",
        "quote_reference_temporal_alignment",
        "cross_structure_quote_synchronicity",
    )
)
_ARCHIVE_FIELDS = frozenset(
    (
        "schema_version",
        "run_id",
        "mode",
        "input_sha256",
        "profile_snapshot",
        "outcome",
        "case_set_reasons",
        "summary",
        "event_input_audit",
        "ei_audit",
        "cases",
        "unavailable",
    )
)


def _keys(value: Any, expected: frozenset, label: str) -> None:
    if type(value) is not dict or set(value) != expected:
        raise ValueError("{} has unknown or missing fields".format(label))


def _text(value: Any, label: str, *, nonempty: bool = True) -> str:
    if type(value) is not str or (nonempty and not value):
        raise TypeError("{} must be {}text".format(label, "non-empty " if nonempty else ""))
    value.encode("utf-8", "strict")
    return value


def case_key(case_id: str) -> str:
    """Return the batch-only navigation key for an unmodified Core ID."""

    value = _text(case_id, "case_id")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_case_key(value: Any) -> str:
    if type(value) is not str or _CASE_KEY_RE.fullmatch(value) is None:
        raise ValueError("batch case_key must be lowercase SHA-256 hex")
    return value


def _strings(value: Any, label: str, *, nonempty: bool = False) -> List[str]:
    if type(value) not in (tuple, list):
        raise TypeError("{} must be a string sequence".format(label))
    result = [_text(item, label, nonempty=nonempty) for item in value]
    return result


def _decimal(value: Any, label: str) -> Optional[str]:
    if value is None:
        return None
    if type(value) is not Decimal or not value.is_finite():
        raise TypeError("{} must be a finite Decimal or None".format(label))
    return str(value)


def _date(value: Any, label: str) -> Optional[str]:
    if value is None:
        return None
    if type(value) is not datetime.date:
        raise TypeError("{} must be a date or None".format(label))
    return value.isoformat()


def _datetime(value: Any, label: str) -> Optional[str]:
    if value is None:
        return None
    if type(value) is not datetime.datetime or value.tzinfo is None or value.utcoffset() is None:
        raise TypeError("{} must be a timezone-aware datetime or None".format(label))
    return value.isoformat()


def _reason_tuple(value: Any, label: str) -> Tuple[str, ...]:
    if type(value) is not tuple:
        raise TypeError("{} must have exact tuple type".format(label))
    return tuple(_text(item, label, nonempty=False) for item in value)


def _bounds(value: Any) -> Dict[str, Any]:
    fields = {
        "max_submissions",
        "max_hypotheses",
        "max_browser_rows",
        "max_cases",
        "quote_timeout_seconds",
    }
    _keys(value, frozenset(fields), "run bounds")
    for name in fields - {"quote_timeout_seconds"}:
        if type(value[name]) is not int or value[name] < 0:
            raise ValueError("{} must be a non-negative integer".format(name))
    timeout = value["quote_timeout_seconds"]
    if type(timeout) not in (int, float) or timeout <= 0:
        raise ValueError("quote_timeout_seconds must be positive")
    return value


def _enum_text(value: Any, label: str) -> str:
    result = getattr(value, "value", None)
    if type(result) is not str:
        raise TypeError("{} must be a closed enum value".format(label))
    return result


def _date_range_projection(value: Any, label: str) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if type(value) is not MethodologizedDateRange:
        raise TypeError("{} must be MethodologizedDateRange or None".format(label))
    return {
        "start_date": _date(value.start_date, label + ".start_date"),
        "end_date": _date(value.end_date, label + ".end_date"),
        "methodology": value.methodology,
    }


def _hypothesis_projection(value: EventUnderlyingHypothesis) -> Dict[str, Any]:
    value.__post_init__()
    underlying = value.underlying_key
    underlying_projection = None
    if underlying is not None:
        underlying_projection = {
            "symbol": underlying.symbol,
            "listing_mic": underlying.listing_mic,
            "security_type": _enum_text(underlying.security_type, "underlying security_type"),
            "currency": underlying.currency,
        }
    reassessment = value.reassessment
    reassessment_projection = None
    if reassessment is not None:
        reassessment_projection = {
            "reassessment_by": _date(reassessment.reassessment_by, "reassessment_by"),
            "methodology": reassessment.methodology,
            "basis_kind": _enum_text(reassessment.basis_kind, "basis_kind"),
            "basis_statement_ids": list(reassessment.basis_statement_ids),
        }
    return {
        "hypothesis_id": value.hypothesis_id,
        "underlying_key": underlying_projection,
        "impact_path": value.impact_path,
        "distribution_mode": None if value.distribution_mode is None else _enum_text(value.distribution_mode, "distribution_mode"),
        "distribution_hypothesis": value.distribution_hypothesis,
        "expected_window": _date_range_projection(value.expected_window, "expected_window"),
        "reassessment": reassessment_projection,
        "supporting_statement_ids": list(value.supporting_statement_ids),
        "contradicting_statement_ids": list(value.contradicting_statement_ids),
        "contradiction_review": value.contradiction_review,
        "uncertainties": list(value.uncertainties),
        "falsification_conditions": list(value.falsification_conditions),
    }


def _submission_projection(
    submission: EventIntelligenceSubmission,
    assessment: EventIntelligenceAcceptanceResult,
) -> Dict[str, Any]:
    submission.__post_init__()
    assessment.__post_init__()
    if assessment.submission is not submission:
        raise ValueError("assessment must retain the exact submitted EI object")
    return {
        "submission_id": submission.submission_id,
        "event_id": submission.event_id,
        "producer_id": submission.producer_id,
        "producer_version": submission.producer_version,
        "observed_at": _datetime(submission.observed_at, "observed_at"),
        "event_description": submission.event_description,
        "event_date_range": _date_range_projection(submission.event_date_range, "event_date_range"),
        "sources": [
            {
                "source_id": source.source_id,
                "locator": source.locator,
                "title": source.title,
                "published_at": _datetime(source.published_at, "published_at"),
            }
            for source in submission.sources
        ],
        "statements": [
            {
                "statement_id": statement.statement_id,
                "kind": _enum_text(statement.kind, "statement.kind"),
                "text": statement.text,
                "source_ids": list(statement.source_ids),
                "dependency_statement_ids": list(statement.dependency_statement_ids),
            }
            for statement in submission.statements
        ],
        "hypotheses": [_hypothesis_projection(item) for item in submission.hypotheses],
        "assessment": {
            "assessment_version": assessment.assessment_version,
            "status": _enum_text(assessment.status, "assessment.status"),
            "issues": [
                {"code": _enum_text(issue.code, "assessment issue code"), "subject_id": issue.subject_id}
                for issue in assessment.issues
            ],
        },
    }


def _event_input_projection(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if type(value) is not UserEventInput:
        raise TypeError("Event raw_input must have exact UserEventInput type")
    value.__post_init__()
    return {
        "evidence_role": "unverified_user_input",
        "description": value.description,
        "provisional_symbols": list(value.provisional_symbols),
        "source_locators": list(value.source_locators),
        "event_date": _date(value.event_date, "event_date"),
    }


def _lineage(context: Any, submissions: Optional[SourceSubmissionBatch]) -> Dict[str, Optional[str]]:
    if context is None:
        return {"submission_id": None, "hypothesis_id": None}
    assessment = context.assessment
    hypothesis = context.hypothesis
    submission_id = None
    hypothesis_id = None
    if assessment is not None:
        if submissions is None or not any(assessment.submission is item for item in submissions.submissions):
            raise ValueError("case assessment is not bound to the run submission batch")
        submission_id = assessment.submission.submission_id
    if hypothesis is not None:
        if assessment is None or not any(hypothesis is item for item in assessment.submission.hypotheses):
            raise ValueError("case hypothesis is not bound to its submitted assessment")
        hypothesis_id = hypothesis.hypothesis_id
    return {"submission_id": submission_id, "hypothesis_id": hypothesis_id}


def _disclosures(record: CoreCaseRecord) -> Dict[str, str]:
    alignment = (
        "unknown"
        if record.discovery_request is None
        else _enum_text(record.discovery_request.hypothesis_maturity_alignment, "hypothesis_maturity_alignment")
    )
    return {
        "maturity_authority": _enum_text(record.maturity_authority, "maturity_authority"),
        "hypothesis_maturity_alignment": alignment,
        "quote_reference_temporal_alignment": record.quote_reference_temporal_alignment,
        "cross_structure_quote_synchronicity": record.cross_structure_quote_synchronicity,
    }


def _profile_check(result: CoreResearchResult) -> None:
    request = result.request
    risk = request.risk_policy
    approved = STANDARD_RESEARCH_PROFILE.to_core_risk_policy(request.structure)
    if risk is None or type(risk) is not type(approved) or risk != approved:
        raise ValueError("Core risk inputs differ from the approved Standard Research Profile")
    if request.cost_ledger is not None or request.sensitivity is not None:
        raise ValueError("batch Core request must retain the approved absent cost and sensitivity inputs")


def _compact_case(
    case_id: str,
    result: CoreResearchResult,
    application_reasons: Tuple[str, ...],
) -> Dict[str, Any]:
    geometry = result.geometry
    budget = result.budget_stress
    kernel_reasons = tuple(item.value for item in result.reasons)
    reasons = kernel_reasons + application_reasons
    legs = tuple(
        CoreCompactLeg(
            leg_id=leg.leg_id,
            underlying=leg.underlying,
            option_type=leg.option_type.value,
            expiration=leg.expiration,
            strike=leg.strike,
            quantity=leg.quantity,
            contract_multiplier=leg.contract_multiplier,
        )
        for leg in result.request.structure.legs
    )
    if len(legs) == 1:
        structure_kind = legs[0].option_type
    elif len(legs) == 2 and {leg.option_type for leg in legs} == {"CALL", "PUT"}:
        structure_kind = "STRADDLE"
    else:
        structure_kind = "UNSUPPORTED"
    compact = CoreCompactCase(
        case_id=case_id,
        disposition=result.disposition.value,
        geometry_status=geometry.status.value,
        ask_basis_per_underlying_unit=geometry.ask_basis_per_underlying_unit,
        reasons=reasons,
        structure_kind=structure_kind,
        legs=legs,
        budget_status=budget.status.value,
        single_cost_upper_bound=budget.single_cost_upper_bound,
        repeated_cost_upper_bound=budget.repeated_cost_upper_bound,
        single_loss_fraction=budget.single_loss_fraction,
        repeated_loss_fraction=budget.repeated_loss_fraction,
    )
    return _compact_case_projection(compact, case_key(case_id))


def _compact_case_projection(value: CoreCompactCase, navigation_key: str) -> Dict[str, Any]:
    return {
        "case_id": value.case_id,
        "case_key": navigation_key,
        "disposition": value.disposition,
        "geometry_status": value.geometry_status,
        "ask_basis_per_underlying_unit": _decimal(value.ask_basis_per_underlying_unit, "ask_basis_per_underlying_unit"),
        "reasons": list(value.reasons),
        "structure_kind": value.structure_kind,
        "legs": [
            {
                "leg_id": leg.leg_id,
                "underlying": leg.underlying,
                "option_type": leg.option_type,
                "expiration": _date(leg.expiration, "leg.expiration"),
                "strike": _decimal(leg.strike, "leg.strike"),
                "quantity": leg.quantity,
                "contract_multiplier": leg.contract_multiplier,
            }
            for leg in value.legs
        ],
        "budget_status": value.budget_status,
        "single_cost_upper_bound": _decimal(value.single_cost_upper_bound, "single_cost_upper_bound"),
        "repeated_cost_upper_bound": _decimal(value.repeated_cost_upper_bound, "repeated_cost_upper_bound"),
        "single_loss_fraction": _decimal(value.single_loss_fraction, "single_loss_fraction"),
        "repeated_loss_fraction": _decimal(value.repeated_loss_fraction, "repeated_loss_fraction"),
    }


def _summary_projection(value: CoreCompactSummary) -> Dict[str, Any]:
    if type(value) is not CoreCompactSummary:
        raise TypeError("compact must have exact CoreCompactSummary type")
    return {
        "entry_origin": value.entry_origin,
        "case_count": value.case_count,
        "unavailable_count": value.unavailable_count,
        "disposition_counts": dict(value.disposition_counts),
        "case_ids": list(value.case_ids),
        "reasons": list(value.reasons),
        "case_summaries": [
            _compact_case_projection(item, case_key(item.case_id))
            for item in value.case_summaries
        ],
        "unavailable_case_ids": list(value.unavailable_case_ids),
    }


def _summary_from_archived(
    entry_origin: str,
    case_set_reasons: List[str],
    cases: List[Dict[str, Any]],
    unavailable: List[Dict[str, Any]],
) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    reasons = list(case_set_reasons)
    case_summaries = []
    for item in cases:
        decoded = decode_core_result(item["core_snapshot"])
        projection = _compact_case(
            item["case_id"], decoded, tuple(item["application_reasons"])
        )
        case_summaries.append(projection)
        disposition = decoded.disposition.value
        counts[disposition] = counts.get(disposition, 0) + 1
        reasons.extend(projection["reasons"])
    if not case_set_reasons:
        for item in unavailable:
            reasons.extend(item["reasons"])
    return {
        "entry_origin": entry_origin,
        "case_count": len(cases),
        "unavailable_count": len(unavailable),
        "disposition_counts": dict(sorted(counts.items())),
        "case_ids": [item["case_id"] for item in cases],
        "reasons": reasons,
        "case_summaries": case_summaries,
        "unavailable_case_ids": [item["case_id"] for item in unavailable],
    }


def _outcome(
    case_count: int,
    unavailable_count: int,
    *,
    has_valid_submission: bool,
    limit_exceeded: bool,
) -> Dict[str, Any]:
    if not has_valid_submission or limit_exceeded:
        status = "BLOCKED"
    elif unavailable_count:
        status = "PARTIAL"
    else:
        status = "COMPLETED"
    return {
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "case_count": case_count,
        "unavailable_count": unavailable_count,
        "status": status,
    }


def _validate_limit_diagnostics(
    reasons: List[str],
    *,
    submission_count: int,
    hypothesis_count: int,
    bounds: Dict[str, Any],
    case_count: int,
    unavailable_count: int,
) -> bool:
    """Validate Core's exact over-bound diagnostic and require no prefix."""

    has_limit = "LIMIT_EXCEEDED" in reasons
    submission_over = submission_count > bounds["max_submissions"]
    hypotheses_over = hypothesis_count > bounds["max_hypotheses"]
    if not has_limit:
        if submission_over or hypotheses_over:
            raise ValueError("oversized Core input counts lack Core LIMIT_EXCEEDED diagnostics")
        if case_count > bounds["max_cases"]:
            raise ValueError("Core case count exceeds the immutable max_cases bound")
        if any(_LIMIT_REASON_RE.fullmatch(reason) for reason in reasons):
            raise ValueError("Core bound diagnostic must be paired with LIMIT_EXCEEDED")
        return False
    if (
        case_count != 0
        or unavailable_count != 0
        or len(reasons) != 2
        or reasons[0] != "LIMIT_EXCEEDED"
    ):
        raise ValueError("LIMIT_EXCEEDED must retain its exact Core reason and no case prefix")
    match = _LIMIT_REASON_RE.fullmatch(reasons[1])
    if match is None:
        raise ValueError("LIMIT_EXCEEDED reason is not a closed Core bound diagnostic")
    name, observed_text, limit_text = match.groups()
    observed, recorded_limit = int(observed_text), int(limit_text)
    bound_name = {
        "submissions": "max_submissions",
        "hypotheses": "max_hypotheses",
        "browser_rows": "max_browser_rows",
        "cases": "max_cases",
    }[name]
    if recorded_limit != bounds[bound_name] or observed <= recorded_limit:
        raise ValueError("LIMIT_EXCEEDED diagnostic does not exceed the immutable run bound")
    if submission_over:
        if name != "submissions" or observed != submission_count:
            raise ValueError("submission overflow differs from Core's first exceeded bound")
    elif hypotheses_over:
        if name != "hypotheses" or observed != hypothesis_count:
            raise ValueError("hypothesis overflow differs from Core's first exceeded bound")
    elif name in ("submissions", "hypotheses"):
        raise ValueError("Core source-count diagnostic does not match archived submissions")
    if name == "cases" and observed <= bounds["max_cases"]:
        raise ValueError("Core case-count diagnostic does not exceed max_cases")
    return True


def build_batch_archive(
    *,
    run_id: str,
    mode: str,
    run_input: str,
    input_sha256: str,
    bounds: Any,
    profile_snapshot: Dict[str, Any],
    metadata: Dict[str, Any],
    result: Any,
    canonical_json: Callable[[Any, str], str],
    validate_locator: Callable[[Any], None],
    validate_source_uris: Callable[[Any], None],
) -> Dict[str, Any]:
    """Build one complete archive or reject it; never emit a partial prefix."""

    if type(result) is not CoreRunResult:
        raise TypeError("batch save requires exact CoreRunResult")
    result.__post_init__()
    case_set = result.case_set
    case_set.__post_init__()
    if type(mode) is not str or mode not in ("world", "event"):
        raise ValueError("batch archive requires a World or Event run")
    if type(case_set.entry_origin) is not str or case_set.entry_origin.upper() != mode.upper():
        raise ValueError("Core entry_origin does not match the immutable run mode")
    if type(run_input) is not str or type(input_sha256) is not str:
        raise TypeError("run snapshot input binding is malformed")
    if metadata["execution_snapshot"].get(mode + "_executor") != {
        "status": "CONFIGURED",
        "version": "host-batch-executor-v0.1",
    }:
        raise ValueError("matching batch executor was not recorded as configured at run start")
    _bounds(bounds)

    raw_input = case_set.raw_input
    if mode == "world":
        if type(raw_input) is not str or raw_input != run_input:
            raise ValueError("World raw_input must exactly match the immutable run input")
        event_input = None
    else:
        if type(raw_input) is not UserEventInput:
            raise TypeError("Event raw_input must have exact UserEventInput type")
        raw_input.__post_init__()
        if raw_input.description != run_input:
            raise ValueError("Event description must exactly match the immutable run input")
        event_input = _event_input_projection(raw_input)
        for locator in raw_input.source_locators:
            validate_locator(locator)

    batch = case_set.submissions
    if batch is not None:
        if type(batch) is not SourceSubmissionBatch:
            raise TypeError("submissions must have exact SourceSubmissionBatch type")
        batch.__post_init__()
        if batch.raw_input is not raw_input:
            raise ValueError("SourceSubmissionBatch must retain the exact original raw_input")
        for submission in batch.submissions:
            submission.__post_init__()
    submissions = () if batch is None else batch.submissions
    hypothesis_count = sum(len(submission.hypotheses) for submission in submissions)
    limit_exceeded = _validate_limit_diagnostics(
        list(case_set.reasons),
        submission_count=len(submissions),
        hypothesis_count=hypothesis_count,
        bounds=bounds,
        case_count=len(case_set.cases),
        unavailable_count=len(case_set.unavailable),
    )
    unavailable_limit = (
        bounds["max_submissions"]
        + bounds["max_hypotheses"]
        + bounds["max_browser_rows"]
        + bounds["max_cases"]
    )
    if len(case_set.unavailable) > unavailable_limit:
        raise ValueError("unavailable branch count exceeds the bound-derived archive limit")
    expected_compact = compact_summary(case_set)
    if type(result.compact) is not CoreCompactSummary or result.compact != expected_compact:
        raise ValueError("CoreRunResult compact summary differs from deterministic recomputation")

    by_identity = {}
    for record in tuple(case_set.cases) + tuple(case_set.unavailable):
        context = record.context
        if context is not None:
            context.__post_init__()
            if context.raw_input is not raw_input:
                raise ValueError("case lineage does not retain the exact Core raw_input")
            if context.submissions is not batch:
                raise ValueError("case lineage does not retain the exact submission batch")
            if context.assessment is not None:
                context.assessment.__post_init__()
                submission = context.assessment.submission
                if batch is None or not any(submission is item for item in submissions):
                    raise ValueError("assessment submission is not the original batch object")
                prior = by_identity.get(id(submission))
                if prior is not None and prior != context.assessment:
                    raise ValueError("one submission has inconsistent retained assessments")
                by_identity[id(submission)] = context.assessment
            if context.hypothesis is not None:
                context.hypothesis.__post_init__()
        if type(record) is CoreCaseRecord:
            record.__post_init__()
        elif type(record) is CoreUnavailableCase:
            record.__post_init__()

    audit_submissions = []
    accepted_submission = False
    for submission in submissions:
        # Reuse the existing deterministic EI assessor only where a submission
        # has no case context to retain its assessment (for example, an empty
        # Browser result). This adds no acceptance rule or authority.
        assessment = by_identity.get(id(submission))
        if assessment is None:
            assessment = assess_event_intelligence_submission(submission)
        if assessment.submission is not submission:
            raise ValueError("EI assessment lost exact submission identity")
        accepted_submission = accepted_submission or (
            assessment.status is EventIntelligenceAcceptanceStatus.ACCEPTED
        )
        audit_submissions.append(_submission_projection(submission, assessment))

    core_cases = []
    unavailable = []
    all_ids = set()
    all_keys = set()
    from .host_core_snapshot import encode_core_result

    for record in case_set.cases:
        if type(record) is not CoreCaseRecord:
            raise TypeError("case set contains a non-CoreCaseRecord")
        if record.context.kernel_request is not record.kernel_request or record.context.kernel_result is not record.kernel_result:
            raise ValueError("Core case context lost request/result identity")
        if record.case_id != record.kernel_request.case_id:
            raise ValueError("Core case ID differs from its exact request ID")
        case_id = _text(record.case_id, "case_id")
        key = case_key(case_id)
        if case_id in all_ids or key in all_keys:
            raise ValueError("batch case IDs and navigation keys must be unique")
        all_ids.add(case_id)
        all_keys.add(key)
        if type(record.kernel_result) is not CoreResearchResult:
            raise TypeError("evaluated case must retain exact CoreResearchResult")
        _profile_check(record.kernel_result)
        snapshot = encode_core_result(record.kernel_result)
        validate_source_uris(snapshot)
        digest = hashlib.sha256(canonical_json(snapshot, "Core snapshot").encode("utf-8")).hexdigest()
        application_reasons = _reason_tuple(record.reasons, "case reasons")
        reasons = list(dict.fromkeys(application_reasons + tuple(item.value for item in record.kernel_result.reasons)))
        lineage = _lineage(record.context, batch)
        if lineage["submission_id"] is None or lineage["hypothesis_id"] is None:
            raise ValueError("evaluated World/Event case must retain its submitted hypothesis lineage")
        core_cases.append(
            {
                "case_id": case_id,
                "case_key": key,
                "classification": record.kernel_result.disposition.value,
                "reasons": reasons,
                "application_reasons": list(application_reasons),
                "lineage": lineage,
                "disclosures": _disclosures(record),
                "core_snapshot": snapshot,
                "core_sha256": digest,
            }
        )

    for record in case_set.unavailable:
        if type(record) is not CoreUnavailableCase:
            raise TypeError("unavailable contains a non-CoreUnavailableCase")
        if record.context is not None and record.context.kernel_request is not None:
            request = record.context.kernel_request
            if request.case_id != record.case_id:
                raise ValueError("unavailable case ID differs from its retained request")
        case_id = _text(record.case_id, "unavailable case_id")
        key = case_key(case_id)
        if case_id in all_ids or key in all_keys:
            raise ValueError("batch case IDs and navigation keys must be unique")
        all_ids.add(case_id)
        all_keys.add(key)
        unavailable.append(
            {
                "case_id": case_id,
                "case_key": key,
                "classification": "UNAVAILABLE",
                "reasons": list(_reason_tuple(record.reasons, "unavailable reasons")),
                "lineage": _lineage(record.context, batch),
            }
        )

    compact_fields = _summary_projection(result.compact)
    if compact_fields != _summary_from_archived(
        case_set.entry_origin,
        list(case_set.reasons),
        core_cases,
        unavailable,
    ):
        raise ValueError("normalized compact summary differs from per-case Core records")
    outcome = _outcome(
        len(core_cases),
        len(unavailable),
        has_valid_submission=accepted_submission,
        limit_exceeded=limit_exceeded,
    )
    summary = dict(compact_fields)
    summary["host_status"] = outcome["status"]
    summary["unavailable_cases"] = [
        {key: item[key] for key in ("case_id", "case_key", "reasons")}
        for item in unavailable
    ]
    archive = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "mode": mode,
        "input_sha256": input_sha256,
        "profile_snapshot": profile_snapshot,
        "outcome": outcome,
        "case_set_reasons": list(_reason_tuple(case_set.reasons, "case-set reasons")),
        "summary": summary,
        "event_input_audit": event_input,
        "ei_audit": {"schema_version": AUDIT_SCHEMA_VERSION, "submissions": audit_submissions},
        "cases": core_cases,
        "unavailable": unavailable,
    }
    for submission in audit_submissions:
        for source in submission["sources"]:
            validate_locator(source["locator"])
    canonical_json(archive, "Host batch archive")
    return archive


def _parse_date(value: Any, label: str, *, optional: bool = False) -> Optional[datetime.date]:
    if optional and value is None:
        return None
    if type(value) is not str:
        raise TypeError("{} must be an ISO date string".format(label))
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("{} must be an ISO date string".format(label)) from error
    if parsed.isoformat() != value:
        raise ValueError("{} must use canonical ISO date format".format(label))
    return parsed


def _parse_datetime(value: Any, label: str, *, optional: bool = False) -> Optional[datetime.datetime]:
    if optional and value is None:
        return None
    if type(value) is not str:
        raise TypeError("{} must be an ISO datetime string".format(label))
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("{} must be an ISO datetime string".format(label)) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.isoformat() != value:
        raise ValueError("{} must be canonical and timezone-aware".format(label))
    return parsed


def _parse_date_range(value: Any, label: str) -> Optional[MethodologizedDateRange]:
    if value is None:
        return None
    _keys(value, frozenset(("start_date", "end_date", "methodology")), label)
    return MethodologizedDateRange(
        _parse_date(value["start_date"], label + ".start_date", optional=True),
        _parse_date(value["end_date"], label + ".end_date", optional=True),
        _optional_text(value["methodology"], label + ".methodology"),
    )


def _optional_text(value: Any, label: str) -> Optional[str]:
    if value is None:
        return None
    return _text(value, label)


def _decode_submission(value: Any) -> Tuple[EventIntelligenceSubmission, EventIntelligenceAcceptanceResult]:
    fields = frozenset(
        (
            "submission_id", "event_id", "producer_id", "producer_version", "observed_at",
            "event_description", "event_date_range", "sources", "statements", "hypotheses", "assessment",
        )
    )
    _keys(value, fields, "EI submission audit")
    if type(value["sources"]) is not list or type(value["statements"]) is not list or type(value["hypotheses"]) is not list:
        raise TypeError("EI audit records must be arrays")
    from .event_intelligence import EventSourceReference, EventStatement, UnderlyingKey

    sources = []
    for source in value["sources"]:
        _keys(source, frozenset(("source_id", "locator", "title", "published_at")), "EI source")
        sources.append(
            EventSourceReference(
                _text(source["source_id"], "source_id"),
                _optional_text(source["locator"], "source locator"),
                _optional_text(source["title"], "source title"),
                _parse_datetime(source["published_at"], "published_at", optional=True),
            )
        )
    statements = []
    for statement in value["statements"]:
        _keys(statement, frozenset(("statement_id", "kind", "text", "source_ids", "dependency_statement_ids")), "EI statement")
        if type(statement["kind"]) is not str:
            raise TypeError("statement kind must be text")
        try:
            kind = EventStatementKind(statement["kind"])
        except ValueError as error:
            raise ValueError("unknown EI statement kind") from error
        statements.append(
            EventStatement(
                _text(statement["statement_id"], "statement_id"),
                kind,
                _optional_text(statement["text"], "statement text"),
                tuple(_strings(statement["source_ids"], "statement source_ids")),
                tuple(_strings(statement["dependency_statement_ids"], "statement dependencies")),
            )
        )
    hypotheses = []
    for hypothesis in value["hypotheses"]:
        _keys(
            hypothesis,
            frozenset((
                "hypothesis_id", "underlying_key", "impact_path", "distribution_mode",
                "distribution_hypothesis", "expected_window", "reassessment",
                "supporting_statement_ids", "contradicting_statement_ids", "contradiction_review",
                "uncertainties", "falsification_conditions",
            )),
            "EI hypothesis",
        )
        underlying_value = hypothesis["underlying_key"]
        underlying = None
        if underlying_value is not None:
            _keys(underlying_value, frozenset(("symbol", "listing_mic", "security_type", "currency")), "underlying key")
            underlying = UnderlyingKey(
                _text(underlying_value["symbol"], "underlying symbol"),
                _optional_text(underlying_value["listing_mic"], "underlying listing MIC"),
                UnderlyingSecurityType(_text(underlying_value["security_type"], "underlying security type")),
                _text(underlying_value["currency"], "underlying currency"),
            )
        mode_value = hypothesis["distribution_mode"]
        try:
            mode = None if mode_value is None else DistributionChangeMode(_text(mode_value, "distribution_mode"))
        except ValueError as error:
            raise ValueError("unknown EI distribution mode") from error
        reassessment_value = hypothesis["reassessment"]
        reassessment = None
        if reassessment_value is not None:
            _keys(reassessment_value, frozenset(("reassessment_by", "methodology", "basis_kind", "basis_statement_ids")), "hypothesis reassessment")
            try:
                basis_kind = ReassessmentBasisKind(_text(reassessment_value["basis_kind"], "basis_kind"))
            except ValueError as error:
                raise ValueError("unknown reassessment basis kind") from error
            reassessment = HypothesisReassessment(
                _parse_date(reassessment_value["reassessment_by"], "reassessment_by"),
                _text(reassessment_value["methodology"], "reassessment methodology"),
                basis_kind,
                tuple(_strings(reassessment_value["basis_statement_ids"], "reassessment basis IDs")),
            )
        hypotheses.append(
            EventUnderlyingHypothesis(
                _text(hypothesis["hypothesis_id"], "hypothesis_id"),
                underlying,
                _optional_text(hypothesis["impact_path"], "impact_path"),
                mode,
                _optional_text(hypothesis["distribution_hypothesis"], "distribution_hypothesis"),
                _parse_date_range(hypothesis["expected_window"], "expected_window"),
                reassessment,
                tuple(_strings(hypothesis["supporting_statement_ids"], "supporting statement IDs")),
                tuple(_strings(hypothesis["contradicting_statement_ids"], "contradicting statement IDs")),
                _optional_text(hypothesis["contradiction_review"], "contradiction_review"),
                tuple(_strings(hypothesis["uncertainties"], "uncertainties")),
                tuple(_strings(hypothesis["falsification_conditions"], "falsification_conditions")),
            )
        )
    submission = EventIntelligenceSubmission(
        _text(value["submission_id"], "submission_id"),
        _optional_text(value["event_id"], "event_id"),
        _optional_text(value["producer_id"], "producer_id"),
        _optional_text(value["producer_version"], "producer_version"),
        _parse_datetime(value["observed_at"], "observed_at", optional=True),
        _optional_text(value["event_description"], "event_description"),
        _parse_date_range(value["event_date_range"], "event_date_range"),
        tuple(sources),
        tuple(statements),
        tuple(hypotheses),
    )
    assessment_value = value["assessment"]
    _keys(assessment_value, frozenset(("assessment_version", "status", "issues")), "EI assessment")
    actual_assessment = assess_event_intelligence_submission(submission)
    if assessment_value != {
        "assessment_version": actual_assessment.assessment_version,
        "status": actual_assessment.status.value,
        "issues": [
            {"code": issue.code.value, "subject_id": issue.subject_id}
            for issue in actual_assessment.issues
        ],
    }:
        raise ValueError("EI assessment audit differs from the existing deterministic assessor")
    if _submission_projection(submission, actual_assessment) != value:
        raise ValueError("EI audit is not the canonical normalized submission projection")
    return submission, actual_assessment


def _validate_event_input_audit(value: Any, mode: str, run_input: str, validate_locator: Callable[[Any], None]) -> None:
    if mode == "world":
        if value is not None:
            raise ValueError("World archive must not contain an Event input audit")
        return
    _keys(value, frozenset(("evidence_role", "description", "provisional_symbols", "source_locators", "event_date")), "Event input audit")
    if value["evidence_role"] != "unverified_user_input":
        raise ValueError("Event input hints must remain explicitly unverified")
    if _text(value["description"], "Event input description") != run_input:
        raise ValueError("Event input description differs from the immutable run input")
    symbols = _strings(value["provisional_symbols"], "provisional_symbols")
    locators = _strings(value["source_locators"], "source_locators")
    for locator in locators:
        validate_locator(locator)
    event_date = _parse_date(value["event_date"], "event_date", optional=True)
    rebuilt = UserEventInput(
        value["description"], tuple(symbols), tuple(locators), event_date
    )
    if _event_input_projection(rebuilt) != value:
        raise ValueError("Event input audit is not the canonical unverified input projection")


def _validate_ei_audit(
    value: Any,
    validate_locator: Callable[[Any], None],
) -> List[Tuple[EventIntelligenceSubmission, EventIntelligenceAcceptanceResult]]:
    _keys(value, frozenset(("schema_version", "submissions")), "EI audit")
    if value["schema_version"] != AUDIT_SCHEMA_VERSION or type(value["submissions"]) is not list:
        raise ValueError("EI audit schema or submissions array is invalid")
    decoded = []
    submission_ids = set()
    for item in value["submissions"]:
        submission, assessment = _decode_submission(item)
        if submission.submission_id in submission_ids:
            raise ValueError("EI audit has duplicate submission IDs")
        submission_ids.add(submission.submission_id)
        for source in submission.sources:
            validate_locator(source.locator)
        decoded.append((submission, assessment))
    return decoded


def _validate_summary_shape(value: Any) -> None:
    _keys(value, _SUMMARY_FIELDS, "compact summary")
    _text(value["entry_origin"], "entry_origin")
    for name in ("case_count", "unavailable_count"):
        if type(value[name]) is not int or value[name] < 0:
            raise ValueError("{} must be a non-negative integer".format(name))
    if type(value["host_status"]) is not str or value["host_status"] not in ("COMPLETED", "PARTIAL", "BLOCKED"):
        raise ValueError("host_status is not a batch Host status")
    counts = value["disposition_counts"]
    if type(counts) is not dict:
        raise TypeError("disposition_counts must be an object")
    for disposition, count in counts.items():
        if disposition not in {item.value for item in CoreDisposition} or type(count) is not int or count <= 0:
            raise ValueError("disposition_counts contains an invalid Core classification")
    for name in ("case_ids", "reasons", "unavailable_case_ids"):
        if type(value[name]) is not list:
            raise TypeError("{} must be an array".format(name))
        if name == "reasons":
            _strings(value[name], name, nonempty=False)
        else:
            for case_id in value[name]:
                _text(case_id, name)
    if type(value["case_summaries"]) is not list:
        raise TypeError("case_summaries must be an array")
    for case in value["case_summaries"]:
        _keys(case, _CASE_SUMMARY_FIELDS, "compact case")
        _text(case["case_id"], "compact case_id")
        validate_case_key(case["case_key"])
        for name in ("disposition", "geometry_status", "structure_kind", "budget_status"):
            _text(case[name], name)
        _strings(case["reasons"], "compact reasons", nonempty=False)
        for name in (
            "ask_basis_per_underlying_unit", "single_cost_upper_bound", "repeated_cost_upper_bound",
            "single_loss_fraction", "repeated_loss_fraction",
        ):
            if case[name] is not None:
                _validate_decimal_string(case[name], name)
        if type(case["legs"]) is not list:
            raise TypeError("compact legs must be an array")
        for leg in case["legs"]:
            _keys(leg, _LEG_FIELDS, "compact leg")
            for name in ("leg_id", "underlying", "option_type"):
                _text(leg[name], name)
            _parse_date(leg["expiration"], "leg.expiration")
            _validate_decimal_string(leg["strike"], "leg.strike")
            for name in ("quantity", "contract_multiplier"):
                if type(leg[name]) is not int or leg[name] <= 0:
                    raise ValueError("{} must be a positive integer".format(name))
    if type(value["unavailable_cases"]) is not list:
        raise TypeError("unavailable_cases must be an array")
    for item in value["unavailable_cases"]:
        _keys(item, frozenset(("case_id", "case_key", "reasons")), "unavailable summary sidecar")
        _text(item["case_id"], "unavailable case_id")
        validate_case_key(item["case_key"])
        _strings(item["reasons"], "unavailable reasons", nonempty=False)


def _validate_decimal_string(value: Any, label: str) -> None:
    if type(value) is not str:
        raise TypeError("{} must be a Decimal string".format(label))
    try:
        parsed = Decimal(value)
    except Exception as error:
        raise ValueError("{} is not a Decimal string".format(label)) from error
    if not parsed.is_finite() or str(parsed) != value:
        raise ValueError("{} must be a canonical finite Decimal string".format(label))


def validate_batch_archive(
    archive: Any,
    *,
    run_id: str,
    mode: str,
    run_input: str,
    input_sha256: str,
    bounds: Any,
    profile_snapshot: Dict[str, Any],
    metadata: Dict[str, Any],
    canonical_json: Callable[[Any, str], str],
    validate_locator: Callable[[Any], None],
    validate_source_uris: Callable[[Any], None],
) -> Tuple[Dict[str, Any], Dict[str, CoreResearchResult]]:
    """Validate every closed field and recompute compact data from numeric snapshots."""

    _keys(archive, _ARCHIVE_FIELDS, "Host batch archive")
    if (
        archive["schema_version"] != SCHEMA_VERSION
        or archive["run_id"] != run_id
        or archive["mode"] != mode
        or mode not in ("world", "event")
        or archive["input_sha256"] != input_sha256
        or archive["profile_snapshot"] != profile_snapshot
    ):
        raise ValueError("batch archive does not match its immutable run snapshot")
    if metadata["execution_snapshot"].get(mode + "_executor") != {
        "status": "CONFIGURED", "version": "host-batch-executor-v0.1"
    }:
        raise ValueError("batch archive has no matching configured executor snapshot")
    bounds = _bounds(bounds)
    if type(archive["case_set_reasons"]) is not list:
        raise TypeError("case_set_reasons must be an array")
    _strings(archive["case_set_reasons"], "case_set_reasons", nonempty=False)
    _validate_summary_shape(archive["summary"])
    _validate_event_input_audit(archive["event_input_audit"], mode, run_input, validate_locator)
    decoded_submissions = _validate_ei_audit(archive["ei_audit"], validate_locator)

    if type(archive["cases"]) is not list or type(archive["unavailable"]) is not list:
        raise TypeError("batch cases and unavailable sidecars must be arrays")
    if len(archive["cases"]) != archive["summary"]["case_count"]:
        raise ValueError("case count differs from compact summary")
    if len(archive["unavailable"]) != archive["summary"]["unavailable_count"]:
        raise ValueError("unavailable count differs from compact summary")
    unavailable_limit = (
        bounds["max_submissions"] + bounds["max_hypotheses"]
        + bounds["max_browser_rows"] + bounds["max_cases"]
    )
    if len(archive["unavailable"]) > unavailable_limit:
        raise ValueError("archived unavailable branches exceed the bound-derived limit")

    submission_map = {
        submission.submission_id: (submission, assessment)
        for submission, assessment in decoded_submissions
    }
    key_map: Dict[str, str] = {}
    decoded_cases: Dict[str, CoreResearchResult] = {}
    canonical_case_entries = []
    for item in archive["cases"]:
        _keys(item, _BATCH_CASE_FIELDS, "batch Core case")
        case_id = _text(item["case_id"], "case_id")
        key = validate_case_key(item["case_key"])
        if key != case_key(case_id) or key in key_map:
            raise ValueError("batch navigation key mismatch or collision")
        key_map[key] = case_id
        if type(item["classification"]) is not str:
            raise TypeError("case classification must be text")
        _strings(item["reasons"], "case reasons", nonempty=False)
        _strings(item["application_reasons"], "application reasons", nonempty=False)
        _keys(item["lineage"], _LINEAGE_FIELDS, "case lineage")
        submission_id = _optional_text(item["lineage"]["submission_id"], "lineage.submission_id")
        hypothesis_id = _optional_text(item["lineage"]["hypothesis_id"], "lineage.hypothesis_id")
        if submission_id is None or hypothesis_id is None:
            raise ValueError("evaluated case must retain actual submission and hypothesis IDs")
        submission_entry = submission_map.get(submission_id)
        if submission_entry is None:
            raise ValueError("evaluated case lineage does not resolve to audited EI IDs")
        submission, assessment = submission_entry
        if (
            assessment.status is not EventIntelligenceAcceptanceStatus.ACCEPTED
            or hypothesis_id not in {h.hypothesis_id for h in submission.hypotheses}
        ):
            raise ValueError("case lineage does not resolve to audited EI IDs")
        _keys(item["disclosures"], _DISCLOSURE_FIELDS, "case disclosures")
        if item["disclosures"]["maturity_authority"] not in {e.value for e in OptionMaturityAuthority}:
            raise ValueError("unknown case maturity authority")
        if item["disclosures"]["hypothesis_maturity_alignment"] not in {"unknown"} | {e.value for e in HypothesisMaturityAlignment}:
            raise ValueError("unknown hypothesis maturity alignment")
        if item["disclosures"]["quote_reference_temporal_alignment"] != "not_established" or item["disclosures"]["cross_structure_quote_synchronicity"] != "not_established":
            raise ValueError("batch authority disclosures are invalid")
        if type(item["core_sha256"]) is not str or re.fullmatch(r"[0-9a-f]{64}", item["core_sha256"], re.ASCII) is None:
            raise ValueError("invalid Core snapshot digest")
        validate_source_uris(item["core_snapshot"])
        digest = hashlib.sha256(canonical_json(item["core_snapshot"], "Core snapshot").encode("utf-8")).hexdigest()
        if digest != item["core_sha256"]:
            raise ValueError("Core snapshot digest mismatch")
        core_result = decode_core_result(item["core_snapshot"])
        if type(core_result) is not CoreResearchResult or core_result.request.case_id != case_id:
            raise ValueError("Core snapshot does not retain its exact case ID")
        if item["classification"] != core_result.disposition.value:
            raise ValueError("case classification differs from Core disposition")
        _profile_check(core_result)
        expected_reasons = list(dict.fromkeys(
            tuple(item["application_reasons"]) + tuple(reason.value for reason in core_result.reasons)
        ))
        if item["reasons"] != expected_reasons:
            raise ValueError("case reasons differ from the retained Core/application reasons")
        decoded_cases[case_id] = core_result
        canonical_case_entries.append(item)

    canonical_unavailable = []
    for item in archive["unavailable"]:
        _keys(item, _UNAVAILABLE_FIELDS, "unavailable sidecar")
        case_id = _text(item["case_id"], "unavailable case_id")
        key = validate_case_key(item["case_key"])
        if key != case_key(case_id) or key in key_map:
            raise ValueError("unavailable navigation key mismatch or collision")
        key_map[key] = case_id
        if item["classification"] != "UNAVAILABLE":
            raise ValueError("unavailable branch classification must remain host-only")
        if type(item["reasons"]) is not list or not item["reasons"]:
            raise ValueError("unavailable branch must retain its reasons")
        _strings(item["reasons"], "unavailable reasons", nonempty=False)
        _keys(item["lineage"], _LINEAGE_FIELDS, "unavailable lineage")
        submission_id = _optional_text(item["lineage"]["submission_id"], "lineage.submission_id")
        hypothesis_id = _optional_text(item["lineage"]["hypothesis_id"], "lineage.hypothesis_id")
        if submission_id is None:
            if hypothesis_id is not None:
                raise ValueError("hypothesis lineage requires a submission ID")
        else:
            submission_entry = submission_map.get(submission_id)
            if submission_entry is None:
                raise ValueError("unavailable lineage does not resolve to audited EI IDs")
            submission, _assessment = submission_entry
            if hypothesis_id is not None and hypothesis_id not in {h.hypothesis_id for h in submission.hypotheses}:
                raise ValueError("unavailable lineage does not resolve to audited EI IDs")
        canonical_unavailable.append(item)

    compact_fields = _summary_from_archived(
        archive["summary"]["entry_origin"],
        archive["case_set_reasons"],
        canonical_case_entries,
        canonical_unavailable,
    )
    limit_exceeded = _validate_limit_diagnostics(
        archive["case_set_reasons"],
        submission_count=len(decoded_submissions),
        hypothesis_count=sum(
            len(submission.hypotheses) for submission, _ in decoded_submissions
        ),
        bounds=bounds,
        case_count=len(archive["cases"]),
        unavailable_count=len(archive["unavailable"]),
    )
    has_valid_submission = any(
        assessment.status is EventIntelligenceAcceptanceStatus.ACCEPTED
        for _submission, assessment in decoded_submissions
    )
    if limit_exceeded and (archive["cases"] or archive["unavailable"]):
        raise ValueError("LIMIT_EXCEEDED archive must not contain a partial prefix")
    expected_outcome = _outcome(
        len(archive["cases"]),
        len(archive["unavailable"]),
        has_valid_submission=has_valid_submission,
        limit_exceeded=limit_exceeded,
    )
    unavailable_projection = [
        {key: item[key] for key in ("case_id", "case_key", "reasons")}
        for item in archive["unavailable"]
    ]
    expected_summary = dict(compact_fields)
    expected_summary["host_status"] = expected_outcome["status"]
    expected_summary["unavailable_cases"] = unavailable_projection
    actual_summary = dict(archive["summary"])
    if actual_summary != expected_summary:
        raise ValueError("compact summary does not recompute from all archived Core cases")
    if expected_summary["entry_origin"].upper() != mode.upper():
        raise ValueError("compact entry_origin does not match run mode")
    if expected_summary["case_ids"] != [item["case_id"] for item in archive["cases"]]:
        raise ValueError("compact cases differ from archive case order")
    if expected_summary["unavailable_case_ids"] != [item["case_id"] for item in archive["unavailable"]]:
        raise ValueError("compact unavailable IDs differ from archive order")

    if archive["outcome"] != expected_outcome:
        raise ValueError("batch outcome differs from its validated records")
    canonical_json(archive, "Host batch archive")
    return actual_summary, decoded_cases


def validate_outcome(value: Any) -> Dict[str, Any]:
    _keys(value, frozenset(("schema_version", "case_count", "unavailable_count", "status")), "batch outcome")
    if type(value["schema_version"]) is not str or value["schema_version"] != OUTCOME_SCHEMA_VERSION:
        raise ValueError("unsupported batch outcome schema")
    for name in ("case_count", "unavailable_count"):
        if type(value[name]) is not int or value[name] < 0:
            raise ValueError("{} must be a non-negative integer".format(name))
    if type(value["status"]) is not str or value["status"] not in ("BLOCKED", "PARTIAL", "COMPLETED"):
        raise ValueError("batch outcome has an invalid Host status")
    return dict(value)


def public_summary(archive: Dict[str, Any]) -> Dict[str, Any]:
    # The caller has decoded a fresh immutable JSON value from SQLite.
    return {key: value for key, value in archive["summary"].items()}


def public_cases(archive: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = [
        {
            "case_id": item["case_id"],
            "case_key": item["case_key"],
            "classification": item["classification"],
            "reasons": list(item["reasons"]),
        }
        for item in archive["cases"]
    ]
    result.extend(
        {
            "case_id": item["case_id"],
            "case_key": item["case_key"],
            "classification": "UNAVAILABLE",
            "reasons": list(item["reasons"]),
        }
        for item in archive["unavailable"]
    )
    return result


def public_case(archive: Dict[str, Any], key: str, decoded_cases: Mapping[str, CoreResearchResult]) -> Optional[Dict[str, Any]]:
    validate_case_key(key)
    for item in archive["cases"]:
        if item["case_key"] == key:
            from .core_presentation import _render_core_report

            result = decoded_cases[item["case_id"]]
            disclosure = (
                "maturity_authority=" + item["disclosures"]["maturity_authority"] + "; "
                "hypothesis_maturity_alignment=" + item["disclosures"]["hypothesis_maturity_alignment"]
                if item["disclosures"]["hypothesis_maturity_alignment"] != "unknown"
                else "hypothesis_maturity_alignment=unknown"
            )
            return {
                "case_id": item["case_id"],
                "case_key": item["case_key"],
                "classification": item["classification"],
                "reasons": list(item["reasons"]),
                "report": _render_core_report(
                    item["case_id"], result, tuple(item["reasons"]), disclosure
                ),
            }
    for item in archive["unavailable"]:
        if item["case_key"] == key:
            return {
                "case_id": item["case_id"],
                "case_key": item["case_key"],
                "classification": "UNAVAILABLE",
                "reasons": list(item["reasons"]),
                "report": None,
            }
    return None
