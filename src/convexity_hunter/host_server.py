"""Bounded loopback HTTP/CLI shell for the standalone Host.

World and Event research can be enabled only through explicitly injected,
trusted Python executors. Direct can be enabled only through an explicitly
injected executor; the CLI's opt-in Futu bridge is lazy and connects only when
a Direct request is executed.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import re
import secrets
import socket
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple
from urllib.parse import unquote_to_bytes, urlsplit

from .core_application import (
    CoreDirectResult,
    CoreOperationalBounds,
    CoreRunResult,
    SourceSubmissionBatch,
)
from .core_research import CoreDisposition, CoreReasonCode
from .host_direct import HostDirectBoundsError, HostDirectInputError
from .host_profile import PROFILE_ID, PROFILE_VERSION, STANDARD_RESEARCH_PROFILE


LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
REQUEST_TIMEOUT_SECONDS = 5.0
MAX_REQUEST_BODY_BYTES = 64 * 1024
CSRF_HEADER = "X-CH-CSRF"
BLOCKED_REASON = "HOST_EXECUTOR_NOT_CONFIGURED"
HOST_SHELL_VERSION = "host-server-v0.1"
ARCHITECTURE_VERSION = "standalone-mvp-architecture-v0.1"
_MODES = frozenset(("world", "event", "direct"))
_BOUNDS_FIELDS = frozenset(
    (
        "max_submissions",
        "max_hypotheses",
        "max_browser_rows",
        "max_cases",
        "quote_timeout_seconds",
    )
)
_RUN_ID_RE = re.compile(r"[A-Za-z0-9._~-]{1,128}\Z", re.ASCII)
_CASE_ID_RE = re.compile(r"[A-Za-z0-9._:~-]{1,256}\Z", re.ASCII)
_CASE_KEY_RE = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_BAD_PERCENT_ESCAPE_RE = re.compile(r"%(?![0-9A-Fa-f]{2})", re.ASCII)
_CONTENT_LENGTH_RE = re.compile(r"[0-9]+\Z", re.ASCII)
_INLINE_TAG_RE = re.compile(r"<(script|style)\b([^>]*)>", re.IGNORECASE)
_DIAGNOSTIC_CODE_RE = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z", re.ASCII)
_TIMESTAMP_RE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.+-]+(?:Z|[+-][0-9]{2}:[0-9]{2})\Z",
    re.ASCII,
)
_RUN_STATUSES = frozenset(
    ("QUEUED", "RUNNING", "COMPLETED", "PARTIAL", "BLOCKED", "FAILED", "INTERRUPTED")
)
_STAGE_EVENTS = frozenset(
    ("stage_started", "stage_outcome", "stage_finished", "stage_succeeded", "stage_failed")
)
_STAGE_NAMES = frozenset(("executor", "grounder"))
_CORE_CLASSIFICATIONS = frozenset(item.value for item in CoreDisposition)
_PUBLIC_DIRECT_REASONS = frozenset(item.value for item in CoreReasonCode) | frozenset(
    ("missing_direct_quote_evidence",)
)
_DIRECT_EXECUTOR_VERSION = "host-direct-input-v0.1"
_BATCH_EXECUTOR_VERSION = "host-batch-executor-v0.1"
_BATCH_OUTCOME_VERSION = "host-batch-outcome-v0.1"
_BATCH_REASON_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
_BATCH_LIMIT_REASON_RE = re.compile(
    r"(?:submissions|hypotheses|browser_rows|cases):[0-9]+>[0-9]+\Z",
    re.ASCII,
)
_GROUNDER_SUBMISSION_PUBLIC_FIELDS = frozenset((
    "schema_version", "grounder_status", "source_status", "semantic_status",
    "builder_status", "submission_status", "ei_status", "counts",
    "diagnostic_counts", "coverage", "provenance", "submission_sha256",
    "source_batch_count", "ei_assessment_status",
))
_GROUNDER_BUDGET_ERROR_CODES = frozenset((
    "REQUEST_BUDGET_EXHAUSTED",
    "CREDIT_BUDGET_EXHAUSTED",
    "TIME_BUDGET_EXHAUSTED",
    "BYTE_BUDGET_EXHAUSTED",
))


class _DiscardingTextStream:
    """Persistent sink safe for SDK handlers that retain their stream object."""

    encoding = "utf-8"
    errors = "replace"
    closed = False

    def write(self, value: str) -> int:
        return len(value) if type(value) is str else 0

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def close(self) -> None:
        # Never invalidate a StreamHandler that may retain this sink.
        return None


_SDK_OUTPUT_SINK = _DiscardingTextStream()
_SDK_OUTPUT_LOCK = threading.RLock()


@contextlib.contextmanager
def _discard_sdk_output():
    """Discard synchronous SDK stdout/stderr without closing captured streams."""

    with _SDK_OUTPUT_LOCK:
        with contextlib.redirect_stdout(_SDK_OUTPUT_SINK):
            with contextlib.redirect_stderr(_SDK_OUTPUT_SINK):
                yield


class RequestPayloadError(ValueError):
    """An untrusted request failed the closed local API schema."""


@dataclass(frozen=True)
class ValidatedRunRequest:
    mode: str
    input: str
    bounds: CoreOperationalBounds

    def bounds_snapshot(self) -> Dict[str, Any]:
        return {
            "max_submissions": self.bounds.max_submissions,
            "max_hypotheses": self.bounds.max_hypotheses,
            "max_browser_rows": self.bounds.max_browser_rows,
            "max_cases": self.bounds.max_cases,
            "quote_timeout_seconds": self.bounds.quote_timeout_seconds,
        }


def _reject_json_constant(_value: str) -> None:
    raise RequestPayloadError("non-finite JSON number")


def _unique_object_pairs(pairs: list[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RequestPayloadError("duplicate JSON key")
        result[key] = value
    return result


def _strict_json_loads(body: bytes) -> Any:
    try:
        decoded = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise RequestPayloadError("request body is not UTF-8") from error
    try:
        return json.loads(
            decoded,
            object_pairs_hook=_unique_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except RequestPayloadError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        raise RequestPayloadError("malformed JSON") from error


def validate_run_request(body: bytes) -> ValidatedRunRequest:
    """Parse the exact POST /api/runs shape without retaining or echoing input."""

    value = _strict_json_loads(body)
    if type(value) is not dict or set(value) != {"mode", "input", "bounds"}:
        raise RequestPayloadError("request fields do not match the run schema")

    mode = value["mode"]
    if type(mode) is not str or mode not in _MODES:
        raise RequestPayloadError("mode is invalid")

    raw_input = value["input"]
    if type(raw_input) is not str or not raw_input.strip():
        raise RequestPayloadError("input must be a non-empty string")

    raw_bounds = value["bounds"]
    if type(raw_bounds) is not dict or set(raw_bounds) != _BOUNDS_FIELDS:
        raise RequestPayloadError("bounds fields do not match the operational schema")
    for name in (
        "max_submissions",
        "max_hypotheses",
        "max_browser_rows",
        "max_cases",
    ):
        if type(raw_bounds[name]) is not int:
            raise RequestPayloadError("operational integer bound is invalid")
    timeout = raw_bounds["quote_timeout_seconds"]
    try:
        timeout_is_finite = type(timeout) in (int, float) and math.isfinite(timeout)
    except (OverflowError, TypeError, ValueError):
        timeout_is_finite = False
    if not timeout_is_finite:
        raise RequestPayloadError("operational timeout is invalid")
    try:
        bounds = CoreOperationalBounds(
            max_submissions=raw_bounds["max_submissions"],
            max_hypotheses=raw_bounds["max_hypotheses"],
            max_browser_rows=raw_bounds["max_browser_rows"],
            max_cases=raw_bounds["max_cases"],
            quote_timeout_seconds=timeout,
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise RequestPayloadError("operational bounds are invalid") from error
    return ValidatedRunRequest(mode=mode, input=raw_input, bounds=bounds)


def _origin_for_port(port: int) -> str:
    if port == 80:
        return "http://127.0.0.1"
    return "http://127.0.0.1:{}".format(port)


def _configuration_snapshot() -> Dict[str, Any]:
    """Required frozen Store payload, not a claim that host config was inspected."""

    return {"models": [], "sources": [], "skills": []}


def _version_snapshot() -> Dict[str, str]:
    """Real contract versions known to this shell, never guessed from config."""

    return {
        "architecture": ARCHITECTURE_VERSION,
        "host_shell": HOST_SHELL_VERSION,
        "standard_research_profile": "{}:{}".format(PROFILE_ID, PROFILE_VERSION),
    }


def _run_start_metadata(
    *,
    world_configured: bool = False,
    event_configured: bool = False,
    direct_configured: bool = False,
    configuration_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    execution_snapshot: Dict[str, Any] = {}
    if world_configured:
        execution_snapshot["world_executor"] = {
            "status": "CONFIGURED",
            "version": _BATCH_EXECUTOR_VERSION,
        }
    if event_configured:
        execution_snapshot["event_executor"] = {
            "status": "CONFIGURED",
            "version": _BATCH_EXECUTOR_VERSION,
        }
    if direct_configured:
        execution_snapshot["direct_executor"] = {
            "status": "CONFIGURED",
            "version": _DIRECT_EXECUTOR_VERSION,
        }
    return {
        "configuration_snapshot": (
            _configuration_snapshot()
            if configuration_snapshot is None
            else configuration_snapshot
        ),
        "execution_snapshot": execution_snapshot,
        "contract_versions": _version_snapshot(),
    }


def _public_diagnostics(value: Any) -> list[str]:
    if type(value) is not list:
        raise ValueError("stored diagnostics are malformed")
    if any(
        type(item) is not str or _DIAGNOSTIC_CODE_RE.fullmatch(item) is None
        for item in value
    ):
        raise ValueError("stored diagnostics are malformed")
    return list(value)


def _grounder_failure_status(error: Exception) -> Tuple[str, str]:
    """Map typed Grounder/source failures to Store-admitted closed codes."""

    from .host_grounder_runtime import HostGrounderRuntimeError
    from .host_model import ModelTransportError
    from .host_sources import TavilyCredentialError, TavilyTransportError

    if type(error) is HostGrounderRuntimeError:
        from .host_store import _GROUNDER_FAILURE_DIAGNOSTIC_CODES

        if type(error.code) is str and error.code in _GROUNDER_FAILURE_DIAGNOSTIC_CODES:
            return "BLOCKED", error.code
        return "FAILED", "RUN_CONTEXT_INVALID"
    if type(error) is TavilyTransportError:
        if type(error.status) is int and error.status == 401:
            return "BLOCKED", "SOURCE_CREDENTIAL_UNAVAILABLE"
        diagnostic = (
            "OPERATIONAL_LIMIT"
            if error.code in _GROUNDER_BUDGET_ERROR_CODES
            else "SOURCE_TRANSPORT_FAILURE"
        )
        return "BLOCKED", diagnostic
    if type(error) is TavilyCredentialError:
        return "BLOCKED", "SOURCE_CREDENTIAL_UNAVAILABLE"
    if type(error) is ModelTransportError and error.code in _GROUNDER_BUDGET_ERROR_CODES:
        return "BLOCKED", "OPERATIONAL_LIMIT"
    return "FAILED", "RUN_CONTEXT_INVALID"


def _public_outcome(value: Any) -> Optional[Dict[str, Any]]:
    if type(value) is str:
        return {"status": value} if value in _RUN_STATUSES else None
    if type(value) is not dict:
        return None
    if value.get("schema_version") == "host-grounder-stage-outcome-v0.1":
        try:
            from .host_store import _validate_grounder_stage_outcome

            return _validate_grounder_stage_outcome(value)
        except (TypeError, ValueError):
            return None
    if value.get("schema_version") == "host-grounder-submission-stage-outcome-v0.1":
        try:
            if "submission" in value:
                from .host_store import _grounder_public_stage_outcome

                projected = _grounder_public_stage_outcome(value)
            else:
                projected = value
            if (
                type(projected) is not dict
                or set(projected) != _GROUNDER_SUBMISSION_PUBLIC_FIELDS
            ):
                return None
            fixed = {
                "schema_version": "host-grounder-submission-stage-outcome-v0.1",
                "grounder_status": "COMPLETED",
                "source_status": "UNKNOWN",
                "semantic_status": "RECEIPT_VALIDATED",
                "builder_status": "COMPLETED",
                "submission_status": "PRESENT",
                "ei_status": "ASSESSED",
            }
            if any(
                projected.get(key) != expected_value
                for key, expected_value in fixed.items()
            ):
                return None
            # EI wire values are lowercase enum values. Never normalize an
            # untrusted value into an acceptance state.
            if (
                type(projected.get("ei_assessment_status")) is not str
                or projected["ei_assessment_status"] not in ("accepted", "incomplete")
            ):
                return None
            counts = projected.get("counts")
            if (
                type(counts) is not dict
                or set(counts) != {
                    "source_body_count", "claim_count", "hypothesis_count",
                    "field_binding_count", "coverage_count",
                }
                or any(type(count) is not int or count < 0 for count in counts.values())
                or type(projected.get("source_batch_count")) is not int
                or projected["source_batch_count"] != 1
                or type(projected.get("submission_sha256")) is not str
                or re.fullmatch(
                    r"[0-9a-f]{64}", projected["submission_sha256"], re.ASCII
                ) is None
                or type(projected.get("diagnostic_counts")) is not list
                or type(projected.get("coverage")) is not list
                or type(projected.get("provenance")) is not dict
            ):
                return None
            return {
                key: projected[key] for key in _GROUNDER_SUBMISSION_PUBLIC_FIELDS
            }
        except (AttributeError, TypeError, ValueError):
            return None
    if (
        set(value) == {"schema_version", "case_id", "classification"}
        and value.get("schema_version") == "host-direct-outcome-v0.1"
        and type(value.get("case_id")) is str
        and _CASE_ID_RE.fullmatch(value["case_id"]) is not None
        and type(value.get("classification")) is str
        and value["classification"] in _CORE_CLASSIFICATIONS
    ):
        return {
            "schema_version": value["schema_version"],
            "case_id": value["case_id"],
            "classification": value["classification"],
        }
    if (
        set(value)
        == {"schema_version", "case_count", "unavailable_count", "status"}
        and value.get("schema_version") == _BATCH_OUTCOME_VERSION
        and type(value.get("case_count")) is int
        and value["case_count"] >= 0
        and type(value.get("unavailable_count")) is int
        and value["unavailable_count"] >= 0
        and type(value.get("status")) is str
        and value["status"] in ("COMPLETED", "PARTIAL", "BLOCKED")
    ):
        return {
            "schema_version": _BATCH_OUTCOME_VERSION,
            "case_count": value["case_count"],
            "unavailable_count": value["unavailable_count"],
            "status": value["status"],
        }
    allowed_values = {
        "executor_status": frozenset(("NOT_CONFIGURED",)),
        "reason": frozenset((BLOCKED_REASON,)),
        "host_shell_version": frozenset((HOST_SHELL_VERSION,)),
    }
    projected = {
        key: item
        for key, item in value.items()
        if key in allowed_values
        and type(item) is str
        and item in allowed_values[key]
    }
    return projected or None


def _public_direct_case_summary(value: Any) -> Dict[str, Any]:
    if type(value) is not dict:
        raise ValueError("stored Direct case summary is malformed")
    case_id = value.get("case_id")
    classification = value.get("classification")
    reasons = value.get("reasons")
    if (
        type(case_id) is not str
        or _CASE_ID_RE.fullmatch(case_id) is None
        or type(classification) is not str
        or classification not in _CORE_CLASSIFICATIONS
        or type(reasons) is not list
        or any(type(reason) is not str or reason not in _PUBLIC_DIRECT_REASONS for reason in reasons)
    ):
        raise ValueError("stored Direct case summary is malformed")
    return {
        "case_id": case_id,
        "classification": classification,
        "reasons": list(reasons),
    }


def _public_direct_case_detail(value: Any, requested_case_id: str) -> Dict[str, Any]:
    if type(value) is not dict or value.get("case_id") != requested_case_id:
        raise ValueError("stored Direct case detail is malformed")
    summary = _public_direct_case_summary(value)
    report_cache = value.get("report_cache")
    if report_cache is None:
        report = None
    elif (
        type(report_cache) is dict
        and set(report_cache) == {"renderer_version", "core_sha256", "text"}
        and type(report_cache.get("text")) is str
    ):
        report = report_cache["text"]
    else:
        raise ValueError("stored Direct report cache is malformed")
    return {
        "case_id": summary["case_id"],
        "classification": summary["classification"],
        "reasons": summary["reasons"],
        "report": report,
    }


def _public_batch_reasons(value: Any) -> list[str]:
    if type(value) is not list or any(
        type(reason) is not str
        or (
            _BATCH_REASON_RE.fullmatch(reason) is None
            and _BATCH_LIMIT_REASON_RE.fullmatch(reason) is None
        )
        for reason in value
    ):
        raise ValueError("stored batch reasons are malformed")
    return list(value)


def _batch_case_key(case_id: str) -> str:
    return hashlib.sha256(case_id.encode("utf-8", errors="strict")).hexdigest()


def _public_batch_case_summary(value: Any) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != {
        "case_id", "case_key", "classification", "reasons"
    }:
        raise ValueError("stored batch case summary is malformed")
    case_id = value.get("case_id")
    case_key = value.get("case_key")
    classification = value.get("classification")
    if (
        type(case_id) is not str
        or not case_id
        or type(case_key) is not str
        or _CASE_KEY_RE.fullmatch(case_key) is None
        or case_key != _batch_case_key(case_id)
        or type(classification) is not str
        or classification not in _CORE_CLASSIFICATIONS | {"UNAVAILABLE"}
    ):
        raise ValueError("stored batch case summary is malformed")
    return {
        "case_id": case_id,
        "case_key": case_key,
        "classification": classification,
        "reasons": _public_batch_reasons(value["reasons"]),
    }


def _public_compact_leg(value: Any) -> Dict[str, Any]:
    fields = {
        "leg_id", "underlying", "option_type", "expiration", "strike",
        "quantity", "contract_multiplier",
    }
    if type(value) is not dict or set(value) != fields:
        raise ValueError("stored compact leg is malformed")
    if (
        type(value["leg_id"]) is not str
        or not value["leg_id"]
        or type(value["underlying"]) is not str
        or not value["underlying"]
        or value["option_type"] not in ("CALL", "PUT")
        or type(value["expiration"]) is not str
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value["expiration"]) is None
        or type(value["strike"]) is not str
        or re.fullmatch(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?", value["strike"]) is None
        or type(value["quantity"]) is not int
        or type(value["contract_multiplier"]) is not int
    ):
        raise ValueError("stored compact leg is malformed")
    return dict(value)


def _public_compact_case(value: Any) -> Dict[str, Any]:
    fields = {
        "case_id", "case_key", "disposition", "geometry_status", "ask_basis_per_underlying_unit",
        "reasons", "structure_kind", "legs", "budget_status",
        "single_cost_upper_bound", "repeated_cost_upper_bound",
        "single_loss_fraction", "repeated_loss_fraction",
    }
    if type(value) is not dict or set(value) != fields:
        raise ValueError("stored compact case is malformed")
    if (
        type(value["case_id"]) is not str
        or not value["case_id"]
        or type(value["case_key"]) is not str
        or _CASE_KEY_RE.fullmatch(value["case_key"]) is None
        or value["case_key"] != _batch_case_key(value["case_id"])
        or type(value["disposition"]) is not str
        or value["disposition"] not in _CORE_CLASSIFICATIONS
        or any(
            type(value[name]) is not str
            for name in ("geometry_status", "structure_kind", "budget_status")
        )
        or any(
            value[name] is not None and type(value[name]) is not str
            for name in (
                "ask_basis_per_underlying_unit", "single_cost_upper_bound",
                "repeated_cost_upper_bound", "single_loss_fraction",
                "repeated_loss_fraction",
            )
        )
        or type(value["legs"]) is not list
    ):
        raise ValueError("stored compact case is malformed")
    return {
        "case_id": value["case_id"],
        "case_key": value["case_key"],
        "disposition": value["disposition"],
        "geometry_status": value["geometry_status"],
        "ask_basis_per_underlying_unit": value["ask_basis_per_underlying_unit"],
        "reasons": _public_batch_reasons(value["reasons"]),
        "structure_kind": value["structure_kind"],
        "legs": [_public_compact_leg(item) for item in value["legs"]],
        "budget_status": value["budget_status"],
        "single_cost_upper_bound": value["single_cost_upper_bound"],
        "repeated_cost_upper_bound": value["repeated_cost_upper_bound"],
        "single_loss_fraction": value["single_loss_fraction"],
        "repeated_loss_fraction": value["repeated_loss_fraction"],
    }


def _public_unavailable_batch_case(value: Any) -> Dict[str, Any]:
    if type(value) is not dict or not {"case_id", "case_key", "reasons"}.issubset(value):
        raise ValueError("stored unavailable batch case is malformed")
    case_id = value["case_id"]
    case_key = value["case_key"]
    if (
        type(case_id) is not str
        or not case_id
        or type(case_key) is not str
        or _CASE_KEY_RE.fullmatch(case_key) is None
        or case_key != _batch_case_key(case_id)
    ):
        raise ValueError("stored unavailable batch case identity is malformed")
    return {
        "case_id": case_id,
        "case_key": case_key,
        "reasons": _public_batch_reasons(value["reasons"]),
    }


def _public_batch_summary(value: Any) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    if type(value) is not dict:
        raise ValueError("stored batch summary is malformed")
    required = {
        "entry_origin", "case_count", "unavailable_count", "disposition_counts",
        "case_ids", "reasons", "case_summaries", "unavailable_case_ids",
        "unavailable_cases", "host_status",
    }
    if not required.issubset(value):
        raise ValueError("stored batch summary is incomplete")
    entry_origin = value["entry_origin"]
    counts = value["disposition_counts"]
    if type(counts) is not dict:
        raise ValueError("stored disposition counts are malformed")
    count_items = list(counts.items())
    public_counts: Dict[str, int] = {}
    for item in count_items:
        if type(item) not in (tuple, list) or len(item) != 2:
            raise ValueError("stored disposition counts are malformed")
        classification, count = item
        if (
            type(classification) is not str
            or classification not in _CORE_CLASSIFICATIONS
            or type(count) is not int
            or count <= 0
            or classification in public_counts
        ):
            raise ValueError("stored disposition counts are malformed")
        public_counts[classification] = count

    def case_ids(field: str) -> list[str]:
        ids = value[field]
        if type(ids) is not list or any(
            type(case_id) is not str or not case_id
            for case_id in ids
        ):
            raise ValueError("stored compact case identifiers are malformed")
        return list(ids)

    case_count = value["case_count"]
    unavailable_count = value["unavailable_count"]
    cases = value["case_summaries"]
    unavailable_cases = value["unavailable_cases"]
    public_case_summaries = (
        [_public_compact_case(item) for item in cases]
        if type(cases) is list
        else None
    )
    public_unavailable_cases = (
        [_public_unavailable_batch_case(item) for item in unavailable_cases]
        if type(unavailable_cases) is list
        else None
    )
    public_case_ids = case_ids("case_ids")
    public_unavailable_ids = case_ids("unavailable_case_ids")
    host_status = value["host_status"]
    if (
        type(entry_origin) is not str
        or entry_origin not in ("WORLD", "EVENT")
        or type(case_count) is not int
        or case_count < 0
        or type(unavailable_count) is not int
        or unavailable_count < 0
        or type(host_status) is not str
        or host_status not in ("COMPLETED", "PARTIAL", "BLOCKED")
        or public_case_summaries is None
        or public_unavailable_cases is None
        or len(public_case_summaries) != case_count
        or len(public_unavailable_cases) != unavailable_count
        or [item["case_id"] for item in public_case_summaries] != public_case_ids
        or [item["case_id"] for item in public_unavailable_cases] != public_unavailable_ids
        or sum(public_counts.values()) != case_count
        or len(set(public_case_ids + public_unavailable_ids)) != case_count + unavailable_count
    ):
        raise ValueError("stored compact summary is malformed")
    public = {
        "entry_origin": entry_origin,
        "case_count": case_count,
        "unavailable_count": unavailable_count,
        "disposition_counts": public_counts,
        "case_ids": public_case_ids,
        "reasons": _public_batch_reasons(value["reasons"]),
        "case_summaries": public_case_summaries,
        "unavailable_case_ids": public_unavailable_ids,
        "unavailable_cases": public_unavailable_cases,
        "host_status": host_status,
    }
    return public


def _public_batch_case_detail(value: Any, requested_case_id: str) -> Dict[str, Any]:
    if type(value) is not dict or not {
        "case_id", "case_key", "classification", "reasons", "report"
    }.issubset(value):
        raise ValueError("stored batch case detail is malformed")
    summary = _public_batch_case_summary(
        {key: value[key] for key in ("case_id", "case_key", "classification", "reasons")}
    )
    if summary["case_key"] != requested_case_id:
        raise ValueError("stored batch case identity is malformed")
    report = value["report"]
    if report is not None and type(report) is not str:
        raise ValueError("stored batch report is malformed")
    return {**summary, "report": report}


def _decode_batch_case_key_segment(segment: str) -> Optional[str]:
    if _BAD_PERCENT_ESCAPE_RE.search(segment) is not None:
        return None
    try:
        decoded = unquote_to_bytes(segment).decode("ascii", errors="strict")
    except (UnicodeDecodeError, ValueError):
        return None
    return decoded if _CASE_KEY_RE.fullmatch(decoded) is not None else None


def _validate_batch_result(result: Any, request: ValidatedRunRequest) -> CoreRunResult:
    """Bind one exact, current application result to its immutable POST input."""

    if type(result) is not CoreRunResult:
        raise ValueError("executor did not return CoreRunResult")
    result.__post_init__()
    case_set = result.case_set
    case_set.__post_init__()
    expected_origin = request.mode.upper()
    if case_set.entry_origin != expected_origin:
        raise ValueError("Core entry origin differs from the run mode")

    if request.mode == "world":
        if type(case_set.raw_input) is not str or case_set.raw_input != request.input:
            raise ValueError("World Core input differs from the original request")
    else:
        from .event_entry import UserEventInput

        event_input = case_set.raw_input
        if (
            type(event_input) is not UserEventInput
            or event_input.description != request.input
        ):
            raise ValueError("Event Core input differs from the original request")

    for case in case_set.cases:
        case.context.__post_init__()
        case.__post_init__()
    for unavailable in case_set.unavailable:
        if unavailable.context is not None:
            unavailable.context.__post_init__()
        unavailable.__post_init__()

    from .core_presentation import compact_summary

    if compact_summary(case_set) != result.compact:
        raise ValueError("Core compact summary is stale or malformed")
    return result


def _batch_status_from_store(journal: Any, result: CoreRunResult, summary: Any) -> str:
    if type(summary) is dict and "host_status" in summary:
        status = summary["host_status"]
    else:
        helper = getattr(journal, "batch_host_status", None)
        if not callable(helper):
            try:
                from .host_store import batch_host_status as helper
            except ImportError:
                helper = None
        if not callable(helper):
            raise ValueError("Store did not return batch status")
        status = helper(result)
    if type(status) is not str or status not in ("COMPLETED", "PARTIAL", "BLOCKED"):
        raise ValueError("Store returned an invalid batch status")
    return status


def _public_event(value: Any) -> Optional[Dict[str, Any]]:
    if type(value) is not dict:
        return None
    event_name = value.get("event")
    if type(event_name) is not str or event_name not in _STAGE_EVENTS:
        return None
    projected: Dict[str, Any] = {"event": event_name}
    stage = value.get("stage")
    if type(stage) is str and stage in _STAGE_NAMES:
        projected["stage"] = stage
    stage_id = value.get("stage_id")
    if type(stage_id) is str and _RUN_ID_RE.fullmatch(stage_id) is not None:
        projected["stage_id"] = stage_id
    status = value.get("status")
    if type(status) is str and status in _RUN_STATUSES:
        projected["status"] = status
    outcome = _public_outcome(value.get("outcome"))
    if outcome is not None:
        projected["outcome"] = outcome
    if "diagnostics" in value:
        projected["diagnostics"] = _public_diagnostics(value["diagnostics"])
    for field in ("started_at", "completed_at"):
        timestamp = value.get(field)
        if type(timestamp) is str and _TIMESTAMP_RE.fullmatch(timestamp) is not None:
            projected[field] = timestamp
    return projected


def _public_run(value: Any) -> Dict[str, Any]:
    """Project an internal Store snapshot onto the deliberately small HTTP view."""

    if type(value) is not dict:
        raise ValueError("stored run is malformed")
    run_id = value.get("run_id")
    mode = value.get("mode")
    status = value.get("status")
    if (
        type(run_id) is not str
        or _RUN_ID_RE.fullmatch(run_id) is None
        or type(mode) is not str
        or mode not in _MODES
        or type(status) is not str
        or status not in _RUN_STATUSES
    ):
        raise ValueError("stored run identity or status is malformed")
    projected: Dict[str, Any] = {"run_id": run_id, "mode": mode, "status": status}
    for field in ("created_at", "updated_at"):
        timestamp = value.get(field)
        if type(timestamp) is str and _TIMESTAMP_RE.fullmatch(timestamp) is not None:
            projected[field] = timestamp
    if "diagnostics" in value:
        projected["diagnostics"] = _public_diagnostics(value["diagnostics"])
    if "events" in value:
        events = value["events"]
        if type(events) not in (list, tuple):
            raise ValueError("stored run events are malformed")
        projected["events"] = [
            safe_event
            for item in events
            if (safe_event := _public_event(item)) is not None
        ]
    return projected


def _constant_time_text_match(actual: str, expected: str) -> bool:
    return secrets.compare_digest(actual.encode("utf-8"), expected.encode("utf-8"))


def _host_matches(value: str, port: int) -> bool:
    """Accept only the numeric loopback authority for this listener."""

    try:
        parsed = urlsplit("//" + value)
        return (
            parsed.hostname == LOOPBACK_HOST
            and parsed.port == port
            and parsed.username is None
            and parsed.password is None
            and parsed.path == ""
            and parsed.query == ""
            and parsed.fragment == ""
        )
    except ValueError:
        return False


def _request_route(path: str) -> Tuple[str, ...]:
    """Return a closed route tuple; reject absolute-form and query-string URLs."""

    if not path.startswith("/") or path.startswith("//"):
        return ()
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return ()
    return tuple(parsed.path.split("/"))


def _decode_case_id_segment(segment: str) -> Optional[str]:
    """Strictly percent-decode an ASCII Store case identifier path segment."""

    if _BAD_PERCENT_ESCAPE_RE.search(segment) is not None:
        return None
    try:
        decoded = unquote_to_bytes(segment).decode("ascii", errors="strict")
    except (UnicodeDecodeError, ValueError):
        return None
    if _CASE_ID_RE.fullmatch(decoded) is None:
        return None
    return decoded


def _read_json_body(handler: BaseHTTPRequestHandler) -> bytes:
    transfer_encodings = handler.headers.get_all("Transfer-Encoding", [])
    if transfer_encodings:
        raise RequestPayloadError("transfer encoding is unsupported")
    content_encodings = handler.headers.get_all("Content-Encoding", [])
    if content_encodings and (
        len(content_encodings) != 1
        or content_encodings[0].strip().lower() != "identity"
    ):
        raise RequestPayloadError("content encoding is unsupported")

    lengths = handler.headers.get_all("Content-Length", [])
    if len(lengths) != 1 or _CONTENT_LENGTH_RE.fullmatch(lengths[0].strip()) is None:
        raise RequestPayloadError("content length is invalid")
    try:
        length = int(lengths[0].strip(), 10)
    except (ValueError, OverflowError) as error:
        raise RequestPayloadError("content length is invalid") from error
    if length > MAX_REQUEST_BODY_BYTES:
        raise OverflowError("request body exceeds the configured transport limit")

    content_types = handler.headers.get_all("Content-Type", [])
    if len(content_types) != 1:
        raise RequestPayloadError("content type is invalid")
    media_type, separator, parameters = content_types[0].partition(";")
    if media_type.strip().lower() != "application/json":
        raise RequestPayloadError("content type is invalid")
    if separator and parameters.strip().lower() not in (
        "charset=utf-8",
        "charset=\"utf-8\"",
    ):
        raise RequestPayloadError("content type is invalid")

    try:
        body = handler.rfile.read(length)
    except (OSError, socket.timeout) as error:
        raise TimeoutError("request body read timed out") from error
    if len(body) != length:
        raise RequestPayloadError("request body is incomplete")
    return body


def _content_security_policy(nonce: str) -> str:
    return "; ".join(
        (
            "default-src 'none'",
            "script-src 'nonce-{}'".format(nonce),
            "style-src 'nonce-{}'".format(nonce),
            "connect-src 'self'",
            "img-src 'self'",
            "font-src 'self'",
            "base-uri 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "object-src 'none'",
        )
    )


def _nonce_inline_assets(markup: str, nonce: str) -> str:
    """Nonce trusted renderer inline blocks so CSP does not permit inline JS."""

    def add_nonce(match: re.Match[str]) -> str:
        tag_name = match.group(1).lower()
        attributes = match.group(2)
        if tag_name == "script" and re.search(r"(?:^|\s)src\s*=", attributes, re.IGNORECASE):
            return match.group(0)
        if re.search(r"(?:^|\s)nonce\s*=", attributes, re.IGNORECASE):
            attributes = re.sub(
                r"(?:^|\s)nonce\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
                "",
                attributes,
                count=1,
                flags=re.IGNORECASE,
            )
        return '<{} nonce="{}"{}>'.format(tag_name, nonce, attributes)

    return _INLINE_TAG_RE.sub(add_nonce, markup)


class HostRequestHandler(BaseHTTPRequestHandler):
    """HTTP API; dependencies are attached by ``create_server``."""

    protocol_version = "HTTP/1.1"
    server_version = "ConvexityHunterLocal"
    sys_version = ""

    journal: Any
    render_workbench: Callable[[str], str]

    def log_message(self, _format: str, *args: Any) -> None:
        # Request targets and headers are attacker-controlled and are never logged.
        return

    def send_error(self, code: int, message: Optional[str] = None, explain: Optional[str] = None) -> None:
        del message, explain
        self.close_connection = True
        status = code if code in (400, 404, 405, 408, 413, 415, 417, 421, 431, 500, 501) else 400
        self._send_json(status, {"error": _ERROR_TEXT.get(status, "request rejected")})

    def handle_expect_100(self) -> bool:
        self.send_error(417)
        return False

    def do_GET(self) -> None:
        if not self._validate_local_authority():
            return
        route = _request_route(self.path)
        if route == ("", ""):
            self._serve_workbench()
            return
        if route == ("", "api", "status"):
            self._send_json(
                200,
                {
                    "host": "READY",
                    "journal": "READY",
                    "ui": "READY",
                    "configuration": "NOT_INSPECTED",
                    "executors": {
                        "world": (
                            "CONFIGURED"
                            if self.server.world_executor is not None
                            else "NOT_CONFIGURED"
                        ),
                        "event": (
                            "CONFIGURED"
                            if (
                                self.server.event_executor is not None
                                or self.server.event_grounder is not None
                            )
                            else "NOT_CONFIGURED"
                        ),
                        "direct": (
                            "CONFIGURED"
                            if self.server.direct_executor is not None
                            else "NOT_CONFIGURED"
                        ),
                    },
                },
            )
            return
        if route == ("", "api", "profile"):
            self._send_json(200, STANDARD_RESEARCH_PROFILE.snapshot())
            return
        if route == ("", "api", "runs"):
            self._get_runs()
            return
        if len(route) == 4 and route[:2] == ("", "api") and route[2] == "runs":
            if _RUN_ID_RE.fullmatch(route[3]) is None:
                self._send_json(404, {"error": "run not found"})
                return
            self._get_run(route[3])
            return
        if (
            len(route) == 6
            and route[:2] == ("", "api")
            and route[2] == "runs"
            and route[4] == "cases"
        ):
            if _RUN_ID_RE.fullmatch(route[3]) is None:
                self._send_json(404, {"error": "case not found"})
                return
            self._get_case(route[3], route[5])
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._validate_local_authority():
            return
        if _request_route(self.path) != ("", "api", "runs"):
            self._send_json(404, {"error": "not found"})
            return
        csrf_values = self.headers.get_all(CSRF_HEADER, [])
        if (
            len(csrf_values) != 1
            or not _constant_time_text_match(csrf_values[0], self.server.csrf_token)
        ):
            self._send_json(403, {"error": "request rejected"})
            return
        try:
            body = _read_json_body(self)
        except OverflowError:
            self._send_json(413, {"error": "request body too large"})
            return
        except TimeoutError:
            self._send_json(408, {"error": "request timed out"})
            return
        except RequestPayloadError:
            self._send_json(400, {"error": "invalid request"})
            return
        try:
            request = validate_run_request(body)
        except RequestPayloadError:
            self._send_json(400, {"error": "invalid request"})
            return
        self._post_run(request)

    def do_HEAD(self) -> None:
        self._method_not_allowed()

    def do_OPTIONS(self) -> None:
        self._method_not_allowed()

    def do_PUT(self) -> None:
        self._method_not_allowed()

    def do_PATCH(self) -> None:
        self._method_not_allowed()

    def do_DELETE(self) -> None:
        self._method_not_allowed()

    def _method_not_allowed(self) -> None:
        if not self._validate_local_authority():
            return
        self.send_response(405)
        self.send_header("Allow", "GET, POST")
        body = b'{"error":"method not allowed"}'
        self._write_common_headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _validate_local_authority(self) -> bool:
        self.close_connection = True
        host_values = self.headers.get_all("Host", [])
        if len(host_values) != 1 or not _host_matches(
            host_values[0].strip(), self.server.server_port
        ):
            self._send_json(421, {"error": "request rejected"})
            return False
        origin_values = self.headers.get_all("Origin", [])
        if len(origin_values) > 1 or (
            origin_values
            and not _constant_time_text_match(
                origin_values[0], _origin_for_port(self.server.server_port)
            )
        ):
            self._send_json(403, {"error": "request rejected"})
            return False
        return True

    def _serve_workbench(self) -> None:
        try:
            markup = self.server.render_workbench(self.server.csrf_token)
            if type(markup) is not str:
                raise TypeError("renderer returned non-text")
        except Exception:
            self._send_json(500, {"error": "workbench unavailable"})
            return
        nonce = secrets.token_urlsafe(18)
        markup = _nonce_inline_assets(markup, nonce)
        self.send_response(200)
        self.send_header("Content-Security-Policy", _content_security_policy(nonce))
        self._write_common_headers("text/html; charset=utf-8", len(markup.encode("utf-8")))
        self.end_headers()
        self.wfile.write(markup.encode("utf-8"))

    def _get_runs(self) -> None:
        try:
            result = self.server.journal.list_runs()
            if type(result) is not list:
                raise ValueError("journal returned malformed run list")
            public_runs = [_public_run(item) for item in result]
        except Exception:
            self._send_json(500, {"error": "journal unavailable"})
            return
        self._send_json(200, {"runs": public_runs})

    def _get_run(self, run_id: str) -> None:
        try:
            result = self.server.journal.get_run(run_id)
            public_run = None if result is None else _public_run(result)
            if public_run is not None:
                mode = result["mode"]
                if mode == "direct":
                    direct_cases = self.server.journal.list_direct_cases(run_id)
                    if type(direct_cases) is not list:
                        raise ValueError("journal returned malformed Direct case list")
                    public_run["cases"] = [
                        _public_direct_case_summary(item) for item in direct_cases
                    ]
                else:
                    summary_getter = getattr(
                        self.server.journal, "get_batch_summary", None
                    )
                    cases_getter = getattr(
                        self.server.journal, "list_batch_cases", None
                    )
                    if callable(summary_getter) and callable(cases_getter):
                        summary = summary_getter(run_id)
                        public_summary = _public_batch_summary(summary)
                        if public_summary is not None:
                            if public_summary["entry_origin"] != mode.upper():
                                raise ValueError("batch summary mode does not match the run")
                            lifecycle_status = public_run["status"]
                            if lifecycle_status == "QUEUED":
                                raise ValueError("queued run cannot have a batch archive")
                            if (
                                lifecycle_status in ("COMPLETED", "PARTIAL", "BLOCKED")
                                and public_summary["host_status"] != lifecycle_status
                            ):
                                raise ValueError("batch summary status does not match the run")
                        batch_cases = cases_getter(run_id)
                        if type(batch_cases) is not list:
                            raise ValueError("journal returned malformed batch case list")
                        public_cases = [
                            _public_batch_case_summary(item) for item in batch_cases
                        ]
                        if public_summary is None:
                            if public_cases:
                                raise ValueError("batch cases exist without a saved summary")
                        else:
                            if len(public_cases) != (
                                public_summary["case_count"]
                                + public_summary["unavailable_count"]
                            ):
                                raise ValueError("batch case archive is incomplete")
                            evaluated_ids = [
                                item["case_id"] for item in public_cases
                                if item["classification"] != "UNAVAILABLE"
                            ]
                            unavailable_ids = [
                                item["case_id"] for item in public_cases
                                if item["classification"] == "UNAVAILABLE"
                            ]
                            if (
                                evaluated_ids != public_summary["case_ids"]
                                or unavailable_ids != public_summary["unavailable_case_ids"]
                            ):
                                raise ValueError(
                                    "batch case archive order differs from its summary"
                                )
                    else:
                        has_batch_outcome = any(
                            type(event) is dict
                            and type(event.get("outcome")) is dict
                            and event["outcome"].get("schema_version")
                            == _BATCH_OUTCOME_VERSION
                            for event in result.get("events", ())
                        )
                        if has_batch_outcome:
                            raise ValueError("batch archive APIs are unavailable")
                        public_summary = None
                        public_cases = []
                    public_run["batch_summary"] = public_summary
                    public_run["cases"] = public_cases
        except Exception:
            self._send_json(500, {"error": "journal unavailable"})
            return
        if public_run is None:
            self._send_json(404, {"error": "run not found"})
            return
        self._send_json(200, public_run)

    def _get_case(self, run_id: str, segment: str) -> None:
        try:
            run = self.server.journal.get_run(run_id)
            if run is None:
                self._send_json(404, {"error": "case not found"})
                return
            mode = run.get("mode") if type(run) is dict else None
            if mode == "direct":
                case_id = _decode_case_id_segment(segment)
                if case_id is None:
                    self._send_json(404, {"error": "case not found"})
                    return
                result = self.server.journal.get_direct_case(run_id, case_id)
                public_case = (
                    None
                    if result is None
                    else _public_direct_case_detail(result, case_id)
                )
            elif mode in ("world", "event"):
                case_key = _decode_batch_case_key_segment(segment)
                if case_key is None:
                    self._send_json(404, {"error": "case not found"})
                    return
                get_batch_case = getattr(self.server.journal, "get_batch_case", None)
                if not callable(get_batch_case):
                    self._send_json(404, {"error": "case not found"})
                    return
                result = get_batch_case(run_id, case_key)
                public_case = (
                    None
                    if result is None
                    else _public_batch_case_detail(result, case_key)
                )
            else:
                self._send_json(404, {"error": "case not found"})
                return
        except Exception:
            self._send_json(500, {"error": "journal unavailable"})
            return
        if public_case is None:
            self._send_json(404, {"error": "case not found"})
            return
        self._send_json(200, public_case)

    def _post_run(self, request: ValidatedRunRequest) -> None:
        try:
            # Capture the injected callbacks once. The same captured callable
            # whose version is recorded below is the only one this run may use.
            world_executor = self.server.world_executor
            event_executor = self.server.event_executor
            event_grounder = self.server.event_grounder
            event_core_executor = self.server.event_core_executor
            direct_executor = self.server.direct_executor
            staged_event_configured = (
                request.mode == "event" and event_grounder is not None
            )
            direct_configured = (
                request.mode == "direct" and direct_executor is not None
            )
            configuration_snapshot = _configuration_snapshot()
            if staged_event_configured:
                snapshot_callback = getattr(
                    event_grounder, "configuration_snapshot", None
                )
                if not callable(snapshot_callback):
                    raise ValueError("Event Grounder has no safe configuration snapshot")
                configuration_snapshot = snapshot_callback()
                if type(configuration_snapshot) is not dict:
                    raise ValueError("Event Grounder configuration snapshot is invalid")
        except Exception:
            self._send_json(500, {"error": "event configuration unavailable"})
            return

        try:
            run_id = self.server.journal.create_run(
                mode=request.mode,
                input=request.input,
                bounds=request.bounds,
                profile_snapshot=STANDARD_RESEARCH_PROFILE.snapshot(),
                metadata=_run_start_metadata(
                    world_configured=world_executor is not None,
                    event_configured=(
                        event_executor is not None or staged_event_configured
                    ),
                    direct_configured=direct_executor is not None,
                    configuration_snapshot=configuration_snapshot,
                ),
            )
            if type(run_id) is not str or _RUN_ID_RE.fullmatch(run_id) is None:
                raise ValueError("journal returned an invalid run identifier")
            stage_id = self.server.journal.start_stage(
                run_id, "grounder" if staged_event_configured else "executor"
            )
        except Exception:
            self._send_json(500, {"error": "journal unavailable"})
            return

        if staged_event_configured:
            self._post_grounded_event_run(
                request,
                run_id,
                stage_id,
                event_grounder,
                event_core_executor,
            )
            return

        if request.mode in ("world", "event"):
            batch_executor = (
                world_executor if request.mode == "world" else event_executor
            )
            if batch_executor is None:
                self._finish_unconfigured_run(run_id, stage_id)
                return
            self._post_batch_run(request, run_id, stage_id, batch_executor)
            return

        if not direct_configured:
            diagnostics = (BLOCKED_REASON,)
            outcome: Any = {
                "executor_status": "NOT_CONFIGURED",
                "reason": BLOCKED_REASON,
                "host_shell_version": HOST_SHELL_VERSION,
            }
            try:
                self.server.journal.finish_stage(
                    run_id,
                    stage_id,
                    status="BLOCKED",
                    outcome=outcome,
                    diagnostics=diagnostics,
                )
                self.server.journal.finish_run(
                    run_id, status="BLOCKED", diagnostics=diagnostics
                )
            except Exception:
                self._send_json(500, {"error": "journal unavailable"})
                return
            self._send_json(
                201,
                {"run_id": run_id, "status": "BLOCKED", "reason": BLOCKED_REASON},
            )
            return

        try:
            result = direct_executor(request.input, bounds=request.bounds)
        except HostDirectInputError:
            if not self._complete_terminal_run(
                run_id,
                stage_id,
                status="BLOCKED",
                outcome="BLOCKED",
                diagnostics=("HOST_DIRECT_INPUT_REJECTED",),
            ):
                return
            self._send_json(
                201,
                {
                    "run_id": run_id,
                    "status": "BLOCKED",
                    "reason": "HOST_DIRECT_INPUT_REJECTED",
                },
            )
            return
        except HostDirectBoundsError:
            if not self._complete_terminal_run(
                run_id,
                stage_id,
                status="BLOCKED",
                outcome="BLOCKED",
                diagnostics=("HOST_DIRECT_BOUNDS_REJECTED",),
            ):
                return
            self._send_json(
                201,
                {
                    "run_id": run_id,
                    "status": "BLOCKED",
                    "reason": "HOST_DIRECT_BOUNDS_REJECTED",
                },
            )
            return
        except Exception:
            if not self._complete_terminal_run(
                run_id,
                stage_id,
                status="FAILED",
                outcome="FAILED",
                diagnostics=("HOST_DIRECT_EXECUTOR_FAILED",),
            ):
                return
            self._send_json(
                201,
                {
                    "run_id": run_id,
                    "status": "FAILED",
                    "reason": "HOST_DIRECT_EXECUTOR_FAILED",
                },
            )
            return

        if type(result) is not CoreDirectResult:
            if not self._complete_terminal_run(
                run_id,
                stage_id,
                status="FAILED",
                outcome="FAILED",
                diagnostics=("HOST_DIRECT_EXECUTOR_FAILED",),
            ):
                return
            self._send_json(
                201,
                {
                    "run_id": run_id,
                    "status": "FAILED",
                    "reason": "HOST_DIRECT_EXECUTOR_FAILED",
                },
            )
            return

        if result.kernel_result is None:
            if not self._complete_terminal_run(
                run_id,
                stage_id,
                status="BLOCKED",
                outcome="BLOCKED",
                diagnostics=("HOST_DIRECT_CORE_BLOCKED",),
            ):
                return
            self._send_json(
                201,
                {
                    "run_id": run_id,
                    "status": "BLOCKED",
                    "reason": "HOST_DIRECT_CORE_BLOCKED",
                },
            )
            return

        try:
            case_id = self.server.journal.save_direct_result(run_id, result)
            classification = result.kernel_result.disposition.value
            if (
                type(case_id) is not str
                or _CASE_ID_RE.fullmatch(case_id) is None
                or case_id != result.kernel_request.case_id
                or type(classification) is not str
                or classification not in _CORE_CLASSIFICATIONS
            ):
                raise ValueError("Direct archive identity is malformed")
        except Exception:
            if not self._complete_terminal_run(
                run_id,
                stage_id,
                status="FAILED",
                outcome="FAILED",
                diagnostics=("HOST_DIRECT_ARCHIVE_FAILED",),
            ):
                return
            self._send_json(
                201,
                {
                    "run_id": run_id,
                    "status": "FAILED",
                    "reason": "HOST_DIRECT_ARCHIVE_FAILED",
                },
            )
            return

        pointer = {
            "schema_version": "host-direct-outcome-v0.1",
            "case_id": case_id,
            "classification": classification,
        }
        if not self._complete_terminal_run(
            run_id,
            stage_id,
            status="COMPLETED",
            outcome=pointer,
            diagnostics=(),
        ):
            return
        self._send_json(
            201,
            {
                "run_id": run_id,
                "status": "COMPLETED",
                "case_id": case_id,
                "classification": classification,
            },
        )

    def _finish_unconfigured_run(self, run_id: str, stage_id: str) -> None:
        diagnostics = (BLOCKED_REASON,)
        outcome = {
            "executor_status": "NOT_CONFIGURED",
            "reason": BLOCKED_REASON,
            "host_shell_version": HOST_SHELL_VERSION,
        }
        try:
            self.server.journal.finish_stage(
                run_id,
                stage_id,
                status="BLOCKED",
                outcome=outcome,
                diagnostics=diagnostics,
            )
            self.server.journal.finish_run(
                run_id, status="BLOCKED", diagnostics=diagnostics
            )
        except Exception:
            self._send_json(500, {"error": "journal unavailable"})
            return
        self._send_json(
            201,
            {"run_id": run_id, "status": "BLOCKED", "reason": BLOCKED_REASON},
        )

    def _post_batch_run(
        self,
        request: ValidatedRunRequest,
        run_id: str,
        stage_id: str,
        executor: Callable[..., CoreRunResult],
        *,
        source_batch: Optional[SourceSubmissionBatch] = None,
    ) -> None:
        try:
            # One trusted callback only. It runs after run_start and stage_started.
            if source_batch is None:
                result = executor(request.input, bounds=request.bounds)
            else:
                result = executor(
                    request.input,
                    bounds=request.bounds,
                    source_batch=source_batch,
                )
        except Exception:
            if not self._complete_terminal_run(
                run_id,
                stage_id,
                status="FAILED",
                outcome="FAILED",
                diagnostics=("HOST_BATCH_EXECUTOR_FAILED",),
            ):
                return
            self._send_json(
                201,
                {
                    "run_id": run_id,
                    "status": "FAILED",
                    "reason": "HOST_BATCH_EXECUTOR_FAILED",
                },
            )
            return

        try:
            result = _validate_batch_result(result, request)
            if source_batch is not None and result.case_set.submissions is not source_batch:
                raise ValueError("Core result did not preserve the Grounder source batch")
        except Exception:
            if not self._complete_terminal_run(
                run_id,
                stage_id,
                status="FAILED",
                outcome="FAILED",
                diagnostics=("HOST_BATCH_RESULT_INVALID",),
            ):
                return
            self._send_json(
                201,
                {
                    "run_id": run_id,
                    "status": "FAILED",
                    "reason": "HOST_BATCH_RESULT_INVALID",
                },
            )
            return

        case_count = len(result.case_set.cases)
        unavailable_count = len(result.case_set.unavailable)
        try:
            save = getattr(self.server.journal, "save_batch_result", None)
            get_summary = getattr(self.server.journal, "get_batch_summary", None)
            if not callable(save) or not callable(get_summary):
                raise ValueError("batch archive APIs are unavailable")
            saved = save(run_id, result)
            if saved is not None:
                raise ValueError("batch archive API returned an unexpected value")
            summary = get_summary(run_id)
            public_summary = _public_batch_summary(summary)
            if public_summary is None:
                raise ValueError("batch archive summary is unavailable after save")
            if (
                public_summary["entry_origin"] != request.mode.upper()
                or public_summary["case_count"] != case_count
                or public_summary["unavailable_count"] != unavailable_count
            ):
                raise ValueError("batch archive summary differs from the Core result")
            status = _batch_status_from_store(self.server.journal, result, summary)
            if public_summary["host_status"] != status:
                raise ValueError("batch archive status is inconsistent")
        except Exception:
            if not self._complete_terminal_run(
                run_id,
                stage_id,
                status="FAILED",
                outcome="FAILED",
                diagnostics=("HOST_BATCH_ARCHIVE_FAILED",),
            ):
                return
            self._send_json(
                201,
                {
                    "run_id": run_id,
                    "status": "FAILED",
                    "reason": "HOST_BATCH_ARCHIVE_FAILED",
                },
            )
            return

        outcome = {
            "schema_version": _BATCH_OUTCOME_VERSION,
            "case_count": case_count,
            "unavailable_count": unavailable_count,
            "status": status,
        }
        diagnostics = () if status == "COMPLETED" else ("HOST_BATCH_{}".format(status),)
        if not self._complete_terminal_run(
            run_id,
            stage_id,
            status=status,
            outcome=outcome,
            diagnostics=diagnostics,
        ):
            return
        self._send_json(201, {"run_id": run_id, "status": status})

    def _post_grounded_event_run(
        self,
        request: ValidatedRunRequest,
        run_id: str,
        grounder_stage_id: str,
        event_grounder: Callable[..., Any],
        event_core_executor: Callable[..., CoreRunResult],
    ) -> None:
        """Run Grounder first, then persist and execute its exact source batch."""

        try:
            result = event_grounder(
                request.input, run_id=run_id, bounds=request.bounds
            )
        except Exception as error:
            status, diagnostic = _grounder_failure_status(error)
            if not self._complete_terminal_run(
                run_id,
                grounder_stage_id,
                status=status,
                outcome=status,
                diagnostics=(diagnostic,),
            ):
                return
            self._send_json(
                201,
                {"run_id": run_id, "status": status, "reason": diagnostic},
            )
            return

        try:
            from .host_grounder_builder import HostBuildResult
            from .host_grounder_runtime import HostGrounderEvidenceCatalogRuntimeResult

            if type(result) is not HostGrounderEvidenceCatalogRuntimeResult:
                raise ValueError("Grounder must return the exact v0.7 runtime result")
            build = result.build_result
            if type(build) is not HostBuildResult:
                raise ValueError("Grounder result has no exact HostBuildResult")
        except Exception:
            if not self._complete_terminal_run(
                run_id,
                grounder_stage_id,
                status="FAILED",
                outcome="FAILED",
                diagnostics=("RUN_CONTEXT_INVALID",),
            ):
                return
            self._send_json(
                201,
                {"run_id": run_id, "status": "FAILED", "reason": "RUN_CONTEXT_INVALID"},
            )
            return

        if build.submission is None:
            if build.source_batch is not None:
                self._finish_grounder_error(
                    run_id, grounder_stage_id, "FAILED", "RUN_CONTEXT_INVALID"
                )
                return
            try:
                save_grounder = getattr(
                    self.server.journal, "save_grounder_stage_result", None
                )
                if not callable(save_grounder):
                    raise ValueError("Grounder negative-stage writer is unavailable")
                saved = save_grounder(run_id, grounder_stage_id, result)
                if saved is not None:
                    raise ValueError("Grounder negative-stage writer returned invalid value")
            except Exception:
                self._finish_grounder_error(
                    run_id, grounder_stage_id, "FAILED", "AUDIT_RETENTION_FAILED"
                )
                return
            self._send_json(
                201,
                {
                    "run_id": run_id,
                    "status": "BLOCKED",
                    "reason": "GROUNDING_NO_SUBMISSION",
                },
            )
            return

        source_batch = build.source_batch
        try:
            if type(source_batch) is not SourceSubmissionBatch:
                raise ValueError("Grounder result has no exact SourceSubmissionBatch")
            source_batch.__post_init__()
            if (
                not source_batch.submissions
                or len(source_batch.submissions) != 1
                or source_batch.raw_input is not build.raw_input
                or source_batch.submissions[0] is not build.submission
            ):
                raise ValueError("Grounder source batch is not bound to its submission")
        except Exception:
            self._finish_grounder_error(
                run_id, grounder_stage_id, "FAILED", "RUN_CONTEXT_BINDING_INVALID"
            )
            return

        try:
            save_grounder = getattr(
                self.server.journal, "save_grounder_submission_stage_result", None
            )
            if not callable(save_grounder):
                raise ValueError("Grounder submission-stage writer is unavailable")
            saved = save_grounder(run_id, grounder_stage_id, result)
            if saved is not None:
                raise ValueError("Grounder submission-stage writer returned invalid value")
        except Exception:
            self._finish_grounder_error(
                run_id, grounder_stage_id, "FAILED", "AUDIT_RETENTION_FAILED"
            )
            return

        try:
            executor_stage_id = self.server.journal.start_stage(run_id, "executor")
        except Exception:
            # The durable positive Grounder stage is retained. Recovery will
            # mark this still-running run INTERRUPTED; no Core call is made.
            self._send_json(500, {"error": "journal unavailable"})
            return
        self._post_batch_run(
            request,
            run_id,
            executor_stage_id,
            event_core_executor,
            source_batch=source_batch,
        )

    def _finish_grounder_error(
        self, run_id: str, stage_id: str, status: str, diagnostic: str
    ) -> None:
        if not self._complete_terminal_run(
            run_id,
            stage_id,
            status=status,
            outcome=status,
            diagnostics=(diagnostic,),
        ):
            return
        self._send_json(
            201,
            {"run_id": run_id, "status": status, "reason": diagnostic},
        )

    def _complete_terminal_run(
        self,
        run_id: str,
        stage_id: str,
        *,
        status: str,
        outcome: Any,
        diagnostics: Tuple[str, ...],
    ) -> bool:
        try:
            self.server.journal.finish_stage(
                run_id,
                stage_id,
                status=status,
                outcome=outcome,
                diagnostics=diagnostics,
            )
            self.server.journal.finish_run(
                run_id, status=status, diagnostics=diagnostics
            )
        except Exception:
            self._send_json(500, {"error": "journal unavailable"})
            return False
        return True

    def _send_json(self, status: int, payload: Mapping[str, Any]) -> None:
        try:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            status = 500
            body = b'{"error":"response unavailable"}'
        self.send_response(status)
        self._write_common_headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _write_common_headers(self, content_type: str, content_length: int) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(content_length))
        self.send_header("Connection", "close")


_ERROR_TEXT = {
    400: "invalid request",
    404: "not found",
    405: "method not allowed",
    408: "request timed out",
    413: "request body too large",
    415: "unsupported media type",
    417: "expectation failed",
    421: "request rejected",
    431: "request headers too large",
    500: "internal error",
}


def create_server(
    journal: Any,
    *,
    render_workbench: Callable[[str], str],
    world_executor: Optional[Callable[..., CoreRunResult]] = None,
    event_executor: Optional[Callable[..., CoreRunResult]] = None,
    event_grounder: Optional[Callable[..., Any]] = None,
    event_core_executor: Optional[Callable[..., CoreRunResult]] = None,
    direct_executor: Optional[Callable[..., CoreDirectResult]] = None,
    port: int = DEFAULT_PORT,
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
) -> HTTPServer:
    """Create an HTTP server bound exclusively to numeric IPv4 loopback."""

    if type(port) is not int or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("port must be an integer in the TCP port range")
    if direct_executor is not None and not callable(direct_executor):
        raise TypeError("direct_executor must be callable or None")
    if world_executor is not None and not callable(world_executor):
        raise TypeError("world_executor must be callable or None")
    if event_executor is not None and not callable(event_executor):
        raise TypeError("event_executor must be callable or None")
    if event_grounder is not None and not callable(event_grounder):
        raise TypeError("event_grounder must be callable or None")
    if event_core_executor is not None and not callable(event_core_executor):
        raise TypeError("event_core_executor must be callable or None")
    if (event_grounder is None) != (event_core_executor is None):
        raise ValueError(
            "event_grounder and event_core_executor must be configured together"
        )
    if event_executor is not None and event_grounder is not None:
        raise ValueError(
            "event_executor is mutually exclusive with the staged Event callbacks"
        )
    if event_grounder is not None and not callable(
        getattr(event_grounder, "configuration_snapshot", None)
    ):
        raise TypeError(
            "event_grounder must expose a callable configuration_snapshot()"
        )
    if (
        type(request_timeout_seconds) not in (int, float)
        or not math.isfinite(request_timeout_seconds)
        or request_timeout_seconds <= 0
    ):
        raise ValueError("request timeout must be a finite positive number")

    class _LoopbackHTTPServer(HTTPServer):
        allow_reuse_address = False

        def handle_error(self, _request: Any, _client_address: Any) -> None:
            # Never print tracebacks that may include request-adjacent data.
            return

        def get_request(self) -> Tuple[socket.socket, Any]:
            request, client_address = super().get_request()
            request.settimeout(float(request_timeout_seconds))
            return request, client_address

    server = _LoopbackHTTPServer(
        (LOOPBACK_HOST, port),
        HostRequestHandler,
        bind_and_activate=True,
    )
    server.journal = journal
    server.render_workbench = render_workbench
    server.world_executor = world_executor
    server.event_executor = event_executor
    server.event_grounder = event_grounder
    server.event_core_executor = event_core_executor
    server.direct_executor = direct_executor
    server.csrf_token = secrets.token_urlsafe(32)
    return server


def _open_store(db_path: Path) -> Any:
    """Open the worker-owned Store, which enforces the external-path boundary."""

    from .host_store import HostStore  # Imported lazily to keep CLI imports inert.

    return HostStore(db_path)


def _load_workbench_renderer() -> Callable[[str], str]:
    from .host_workbench import render_workbench

    return render_workbench


def _positive_cli_port(value: str) -> int:
    try:
        port = int(value, 10)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _open_suppressed_futu_quote_context(port: int) -> object:
    """Open only the quote context after disabling the installed SDK logger."""

    from .providers import futu as futu_provider

    try:
        sdk = futu_provider._load_futu_sdk()
    except SystemExit:
        # The SDK package can sys.exit during its dependency check; never let
        # that escape a request thread or reveal SDK diagnostics.
        raise RuntimeError("Futu SDK is unavailable.") from None

    try:
        import importlib

        sdk_logger = importlib.import_module("futu.common.ft_logger").logger
        # Futu's CRITICAL threshold still emits CRITICAL records. The supported
        # level setters with a higher level disable file writes entirely.
        sdk_logger.file_level = sys.maxsize
        sdk_logger.console_level = sys.maxsize
        sdk_logger.enable_console_log(False)
    except SystemExit:
        raise RuntimeError("Futu SDK logging suppression is unavailable.") from None
    except Exception:
        raise RuntimeError("Futu SDK logging suppression is unavailable.") from None

    try:
        return sdk.OpenQuoteContext(host=LOOPBACK_HOST, port=port)
    except Exception:
        raise RuntimeError("Futu OpenD quote-context initialization failed.") from None


def _make_futu_direct_executor(port: int) -> Callable[..., CoreDirectResult]:
    """Return an executor whose SDK import and localhost connection are lazy."""

    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Futu quote port must be between 1 and 65535")

    def execute(raw_input: str, *, bounds: CoreOperationalBounds) -> CoreDirectResult:
        # This one serialized Host request is synchronous. Keep the discard
        # stream active through SDK imports, operations, and bridge-owned close.
        with _discard_sdk_output():
            from .core_futu import FutuMarketBridge
            from .host_direct import run_direct_input

            bridge = FutuMarketBridge(
                quote_context_factory=lambda: _open_suppressed_futu_quote_context(
                    port
                )
            )
            return run_direct_input(
                raw_input,
                bounds=bounds,
                exact_provider_bridge=bridge,
            )

    return execute


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Convexity Hunter local Host.")
    parser.add_argument("--db", required=True, type=Path, help="external SQLite journal path")
    parser.add_argument(
        "--port",
        type=_positive_cli_port,
        default=DEFAULT_PORT,
        help="loopback TCP port (default: 8080)",
    )
    parser.add_argument(
        "--enable-direct",
        action="store_true",
        help="enable explicit Direct research through a local Futu quote service",
    )
    parser.add_argument(
        "--futu-port",
        type=_positive_cli_port,
        help="explicit localhost Futu OpenD quote port (required with --enable-direct)",
    )
    args = parser.parse_args(argv)
    if args.enable_direct and args.futu_port is None:
        parser.error("--futu-port is required when --enable-direct is set")
    if not args.enable_direct and args.futu_port is not None:
        parser.error("--futu-port requires --enable-direct")

    journal = None
    server = None
    try:
        journal = _open_store(args.db)
        direct_executor = (
            _make_futu_direct_executor(args.futu_port)
            if args.enable_direct
            else None
        )
        server = create_server(
            journal,
            render_workbench=_load_workbench_renderer(),
            direct_executor=direct_executor,
            port=args.port,
        )
        print("Convexity Hunter local Host: http://127.0.0.1:{}".format(server.server_port))
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except Exception:
        # Do not expose the database path or low-level filesystem exception.
        print("local Host could not start", file=sys.stderr)
        return 2
    finally:
        if server is not None:
            server.server_close()
        if journal is not None:
            close = getattr(journal, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
